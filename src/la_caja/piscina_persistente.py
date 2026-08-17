"""
PROTOTIPO -- no reemplaza core.py todavia.

Persistencia de la Piscina via event-sourcing: cada mutacion se
registra como (metodo, argumentos) en un log append-only de SQLite
ANTES/junto con aplicarse en memoria. El estado se reconstruye
reproduciendo las mismas llamadas de metodo, nunca por un algoritmo de
reconstruccion separado -- evita que "como se escribe" y "como se
reconstruye" diverjan con el tiempo.

Requiere dos metodos nuevos en Piscina (crear_burbuja, reforzar) que
en core.py hoy Caja hace por acceso directo a piscina.burbujas -- ese
bypass rompe el event-sourcing si no se encapsula primero. Ese es el
unico cambio de forma que este prototipo le pide a core.py.
"""
import json
import sqlite3
import time
from collections import deque


FILTRO_ONTOLOGICO_DEFAULT = {
    "el", "la", "los", "las", "un", "una", "unos", "unas",
    "de", "del", "a", "al", "en", "con", "por", "para", "sin", "sobre",
    "entre", "hacia", "hasta", "desde", "durante",
    "y", "o", "u", "e", "ni", "que", "pero", "si", "porque",
    "qué", "cual", "cuál", "quien", "quién", "como", "cómo",
    "tiene", "es", "son", "esta", "está", "hay",
}

VENTANA_COOCURRENCIA = 4


def _ahora():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


class Burbuja:
    def __init__(self, termino):
        self.termino = termino
        self.peso = 1
        self.nodos = set()

    def reforzar(self):
        self.peso += 1


class Nodo:
    _seq = 0

    def __init__(self):
        Nodo._seq += 1
        self.id = f"n{Nodo._seq}"
        self.burbujas = set()
        self.aristas = set()

    def agregar(self, termino):
        self.burbujas.add(termino)

class Piscina:
    """Identico al core.py canonico, mas dos metodos (crear_burbuja,
    reforzar) que encapsulan lo que hoy Caja hace por acceso directo a
    self.burbujas -- necesarios para que TODA mutacion pase por un
    metodo interceptable."""

    UMBRAL_FISION_PESO = 50
    UMBRAL_FISION_BURBUJAS = 20

    def __init__(self):
        self.burbujas = {}
        self.nodos = {}

    def existe(self, termino):
        return termino in self.burbujas

    def crear_burbuja(self, termino):
        self.burbujas[termino] = Burbuja(termino)
        return self.burbujas[termino]

    def reforzar(self, termino):
        self.burbujas[termino].reforzar()

    def nodos_de(self, termino):
        b = self.burbujas.get(termino)
        return set(b.nodos) if b else set()

    def comparten_nodo(self, a, b):
        return bool(self.nodos_de(a) & self.nodos_de(b))

    def _nuevo_nodo(self, *terminos):
        n = Nodo()
        for t in terminos:
            n.agregar(t)
            self.burbujas[t].nodos.add(n.id)
        self.nodos[n.id] = n
        return n

    def crear_unitario(self, termino):
        return self._nuevo_nodo(termino)

    def crear_compartido(self, a, b):
        return self._nuevo_nodo(a, b)

    def fusionar(self, nodo_ids):
        nodo_ids = list(nodo_ids)
        nuevo = Nodo()
        for nid in nodo_ids:
            n = self.nodos[nid]
            for t in n.burbujas:
                nuevo.agregar(t)
                self.burbujas[t].nodos.discard(nid)
                self.burbujas[t].nodos.add(nuevo.id)
            for otro_id in n.aristas:
                if otro_id not in nodo_ids:
                    nuevo.aristas.add(otro_id)
                    self.nodos[otro_id].aristas.discard(nid)
                    self.nodos[otro_id].aristas.add(nuevo.id)
            del self.nodos[nid]
        self.nodos[nuevo.id] = nuevo
        return nuevo

    def arista_entre(self, a, b):
        na = sorted(self.nodos_de(a))
        nb = sorted(self.nodos_de(b))
        for na_id in na:
            for nb_id in nb:
                if na_id != nb_id:
                    self.nodos[na_id].aristas.add(nb_id)
                    self.nodos[nb_id].aristas.add(na_id)

    def conectados(self, a, b, max_saltos=10):
        if a == b:
            return True
        if self.comparten_nodo(a, b):
            return True
        na = self.nodos_de(a)
        nb = self.nodos_de(b)
        if not na or not nb:
            return False
        visitados = set(na)
        cola = deque((nid, 0) for nid in na)
        while cola:
            nid, saltos = cola.popleft()
            if saltos >= max_saltos:
                continue
            for vecino in self.nodos[nid].aristas:
                if vecino in nb:
                    return True
                if vecino not in visitados:
                    visitados.add(vecino)
                    cola.append((vecino, saltos + 1))
        return False

    def stats(self):
        return {
            "terminos": len(self.burbujas),
            "nodos": len(self.nodos),
            "aristas": sum(len(n.aristas) for n in self.nodos.values()) // 2,
        }

    # -- serializacion para snapshots --
    def a_dict(self):
        return {
            "burbujas": {t: {"peso": b.peso, "nodos": sorted(b.nodos)} for t, b in self.burbujas.items()},
            "nodos": {nid: {"burbujas": sorted(n.burbujas), "aristas": sorted(n.aristas)} for nid, n in self.nodos.items()},
        }

    def cargar_dict(self, data):
        self.burbujas = {}
        for t, bd in data["burbujas"].items():
            b = Burbuja(t)
            b.peso = bd["peso"]
            b.nodos = set(bd["nodos"])
            self.burbujas[t] = b
        self.nodos = {}
        max_seq = 0
        for nid, nd in data["nodos"].items():
            n = Nodo.__new__(Nodo)
            n.id = nid
            n.burbujas = set(nd["burbujas"])
            n.aristas = set(nd["aristas"])
            self.nodos[nid] = n
            if nid.startswith("n") and nid[1:].isdigit():
                max_seq = max(max_seq, int(nid[1:]))
        Nodo._seq = max_seq


class Caja:
    def __init__(self, piscina, filtro_ontologico=None):
        self.piscina = piscina
        self.filtro = filtro_ontologico or FILTRO_ONTOLOGICO_DEFAULT

    def _filtrar(self, terminos):
        vistos = []
        for t in terminos:
            if t not in self.filtro and t not in vistos:
                vistos.append(t)
        return vistos

    def procesar_terminos(self, terminos):
        terminos = self._filtrar(terminos)
        eventos = []
        recien_creados = set()

        for t in terminos:
            if self.piscina.existe(t):
                self.piscina.reforzar(t)
                eventos.append({"tipo": "peso_reforzado", "termino": t})
            else:
                self.piscina.crear_burbuja(t)
                self.piscina.crear_unitario(t)
                recien_creados.add(t)
                eventos.append({"tipo": "nodo_creado", "termino": t})

        def unitario_fresco(x):
            ns = self.piscina.nodos_de(x)
            return len(ns) == 1 and len(self.piscina.nodos[next(iter(ns))].burbujas) == 1

        for i, t in enumerate(terminos):
            for vecino in terminos[max(0, i - VENTANA_COOCURRENCIA):i]:
                if vecino == t:
                    continue
                if self.piscina.comparten_nodo(t, vecino):
                    continue
                nuevo_t = t in recien_creados
                nuevo_v = vecino in recien_creados
                if nuevo_t and nuevo_v and unitario_fresco(t) and unitario_fresco(vecino):
                    ns = self.piscina.nodos_de(t) | self.piscina.nodos_de(vecino)
                    self.piscina.fusionar(ns)
                    eventos.append({"tipo": "fusion_nodo_unico", "terminos": [vecino, t]})
                elif nuevo_t or nuevo_v:
                    self.piscina.crear_compartido(vecino, t)
                    eventos.append({"tipo": "nodo_compartido", "terminos": [vecino, t]})
                else:
                    self.piscina.arista_entre(t, vecino)
                    eventos.append({"tipo": "arista", "terminos": [vecino, t]})
        return eventos

class PiscinaPersistente(Piscina):
    """Piscina con event-sourcing: cada metodo mutante se registra en
    SQLite (metodo, argumentos) ademas de aplicarse en memoria. Al
    construirse, carga el ultimo snapshot (si hay) y repite solo los
    eventos posteriores -- nunca deserializa el estado directo salvo
    en el punto de snapshot."""

    def __init__(self, db_path, snapshot_cada=1000):
        super().__init__()
        self.db = sqlite3.connect(db_path)
        self.snapshot_cada = snapshot_cada
        self._eventos_desde_snapshot = 0
        self._crear_tablas()
        self._cargar()

    def _crear_tablas(self):
        self.db.execute("""CREATE TABLE IF NOT EXISTS eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metodo TEXT NOT NULL,
            argumentos TEXT NOT NULL,
            creado_en TEXT NOT NULL
        )""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ultimo_evento_id INTEGER NOT NULL,
            estado TEXT NOT NULL,
            creado_en TEXT NOT NULL
        )""")
        self.db.commit()

    def _registrar(self, metodo, argumentos):
        self.db.execute(
            "INSERT INTO eventos (metodo, argumentos, creado_en) VALUES (?, ?, ?)",
            (metodo, json.dumps(argumentos), _ahora()),
        )
        self.db.commit()
        self._eventos_desde_snapshot += 1
        if self._eventos_desde_snapshot >= self.snapshot_cada:
            self.snapshot()

    def crear_burbuja(self, termino):
        resultado = super().crear_burbuja(termino)
        self._registrar("crear_burbuja", {"termino": termino})
        return resultado

    def reforzar(self, termino):
        super().reforzar(termino)
        self._registrar("reforzar", {"termino": termino})

    def crear_unitario(self, termino):
        resultado = super().crear_unitario(termino)
        self._registrar("crear_unitario", {"termino": termino})
        return resultado

    def crear_compartido(self, a, b):
        resultado = super().crear_compartido(a, b)
        self._registrar("crear_compartido", {"a": a, "b": b})
        return resultado

    def fusionar(self, nodo_ids):
        nodo_ids = list(nodo_ids)
        resultado = super().fusionar(nodo_ids)
        self._registrar("fusionar", {"nodo_ids": nodo_ids})
        return resultado

    def arista_entre(self, a, b):
        super().arista_entre(a, b)
        self._registrar("arista_entre", {"a": a, "b": b})

    def snapshot(self):
        ultimo = self.db.execute("SELECT MAX(id) FROM eventos").fetchone()[0] or 0
        self.db.execute(
            "INSERT INTO snapshots (ultimo_evento_id, estado, creado_en) VALUES (?, ?, ?)",
            (ultimo, json.dumps(self.a_dict()), _ahora()),
        )
        self.db.commit()
        self._eventos_desde_snapshot = 0

    def _cargar(self):
        fila = self.db.execute(
            "SELECT ultimo_evento_id, estado FROM snapshots ORDER BY id DESC LIMIT 1"
        ).fetchone()
        desde_id = 0
        if fila:
            desde_id, estado_json = fila
            self.cargar_dict(json.loads(estado_json))

        filas = self.db.execute(
            "SELECT metodo, argumentos FROM eventos WHERE id > ? ORDER BY id ASC",
            (desde_id,),
        ).fetchall()
        for metodo, argumentos_json in filas:
            argumentos = json.loads(argumentos_json)
            self._aplicar_sin_registrar(metodo, argumentos)

    def _aplicar_sin_registrar(self, metodo, argumentos):
        """Re-ejecuta un evento del log llamando a los metodos de la
        clase BASE (Piscina) -- si llamara a los de esta clase,
        volveria a registrar el evento que ya esta siendo repetido."""
        if metodo == "crear_burbuja":
            Piscina.crear_burbuja(self, argumentos["termino"])
        elif metodo == "reforzar":
            Piscina.reforzar(self, argumentos["termino"])
        elif metodo == "crear_unitario":
            Piscina.crear_unitario(self, argumentos["termino"])
        elif metodo == "crear_compartido":
            Piscina.crear_compartido(self, argumentos["a"], argumentos["b"])
        elif metodo == "fusionar":
            Piscina.fusionar(self, argumentos["nodo_ids"])
        elif metodo == "arista_entre":
            Piscina.arista_entre(self, argumentos["a"], argumentos["b"])
        else:
            raise ValueError(f"evento desconocido en el log: {metodo}")


class LaCaja:
    def __init__(self, filtro_ontologico=None, db_path=None):
        self.piscina = PiscinaPersistente(db_path) if db_path else Piscina()
        self.caja = Caja(self.piscina, filtro_ontologico)

    def procesar_consulta(self, texto):
        import re
        terminos = re.findall(r"[a-záéíóúñü]+", texto.lower())
        eventos = self.caja.procesar_terminos(terminos)
        return {"terminos_procesados": terminos, "eventos": eventos}

    def declarar_relacion(self, a, b):
        return self.caja.procesar_terminos([a, b])

    def consultar(self, a, b):
        return self.piscina.conectados(a, b)

    def stats(self):
        return self.piscina.stats()
