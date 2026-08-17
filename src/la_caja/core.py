"""
Nucleo de La Caja -- modelo canonico (fusion 16/8/2026).

Este archivo reemplaza al modelo single-membership (termino_a_nodo 1:1),
descartado por dos defectos estructurales que el modelo multi-pertenencia
corrige:

  1. Exilio: un termino solo podia pertenecer a un nodo; co-ocurrir con
     un segundo contexto lo "exiliaba" del primero, relegandolo a una
     simple arista.
  2. Conectividad espuria: la navegacion por membresia compartida
     conectaba contextos de consultas distintas que nunca co-ocurrieron
     (un termino-hub puenteando todo en pocos saltos).

Mecanismo del modelo canonico:
  - Burbuja: un termino, entidad persistente con peso propio y pertenencia
    a MULTIPLES nodos (burbujas dentro de/acopladas a burbujas). Nunca se
    exilia.
  - Nodo: un contexto de co-ocurrencia -- el conjunto de terminos que
    co-ocurrieron dentro de una misma ventana de consulta.
  - Termino nuevo -> nodo unitario {t}.
  - nuevo+nuevo co-ocurriendo en la ventana -> fusion en UN nodo.
  - nuevo+existente co-ocurriendo -> el nuevo conserva su unitario y
    ambos entran en un nodo compartido nuevo. Sin arista: un concepto
    recien nacido no fabrica rutas de navegacion.
  - existente+existente co-ocurriendo sin nodo comun -> ARISTA explicita
    entre sus nodos: una relacion observada entre conceptos ya
    establecidos. Es la UNICA forma de crear aristas.
  - repetido -> refuerza peso de la burbuja.
  - conectados(a, b): mismo nodo -> True. Si no, BFS sobre ARISTAS
    explicitas. Compartir termino en consultas distintas NO conecta.

Regla de oro (decision 16/8/2026, registrada en el MCP remoto):
  PERTENENCIA = activacion/primado de contexto. ARISTA = navegacion.
  No mezclar. Las dos nociones de "conectado" (cadena de terminos
  compartidos vs arista explicita) no conviven bajo ninguna regla
  consistente -- el caso doom3->idtech4->netradiant y el puente
  primero->td->ultimo son estructuralmente identicos. Se eligio arista
  explicita: rutas observadas y validadas, no atajos implicitos.

Persistencia (fusion 16/8/2026):
  - PiscinaPersistente (Piscina + event-sourcing sobre SQLite): cada
    mutacion se registra como (metodo, argumentos) en un log append-only
    ANTES/junto con aplicarse en memoria; el estado se reconstruye
    repitiendo los MISMOS metodos, nunca por un algoritmo separado.
  - Snapshots cada N eventos acotan el costo de replay.
  - Opt-in: LaCaja(db_path=None) usa Piscina en memoria pura; con
    db_path usa PiscinaPersistente. Todos los metodos mutantes de Piscina
    (crear_burbuja, reforzar, crear_unitario, crear_compartido, fusionar,
    arista_entre) son el unico punto de entrada de mutacion.
  - El log es tambien el soporte del criterio temporal de la arista
    estricta: el orden global de nacimiento de burbujas queda persistido.

Pendientes abiertos (no decididos por este archivo):
  - fision de nodos (optimizar() solo lista candidatos, no divide; al
    implementarla DEBE registrarse como evento del log o derivarse
    deterministicamente, o el replay divergira del estado canónico)
  - criterio de capacidad de caja
"""
import json
import re
import sqlite3
import time
from collections import deque


FILTRO_ONTOLOGICO_DEFAULT = {
    # articulos
    "el", "la", "los", "las", "un", "una", "unos", "unas",
    # preposiciones comunes
    "de", "del", "a", "al", "en", "con", "por", "para", "sin", "sobre",
    "entre", "hacia", "hasta", "desde", "durante",
    # conjunciones / conectores
    "y", "o", "u", "e", "ni", "que", "pero", "si", "porque",
    # pronombres interrogativos / auxiliares triviales
    "qué", "cual", "cuál", "quien", "quién", "como", "cómo",
    "tiene", "es", "son", "esta", "está", "hay",
}

VENTANA_COOCURRENCIA = 4


def _ahora():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _tokenizar(texto):
    """Extrae palabras, sin puntuacion, en minusculas."""
    return re.findall(r"[a-záéíóúñü]+", texto.lower())


class Burbuja:
    """Un termino. Entidad persistente: vive una sola vez, con su peso y
    el conjunto de nodos a los que pertenece (multi-membresia)."""

    def __init__(self, termino):
        self.termino = termino
        self.peso = 1
        self.nodos = set()  # ids de nodos a los que pertenece

    def reforzar(self):
        self.peso += 1


class Nodo:
    """Un contexto de co-ocurrencia. Referencia burbujas (muchos-a-muchos)
    y tiene aristas explicitas hacia otros nodos (navegacion)."""

    _seq = 0

    def __init__(self):
        Nodo._seq += 1
        self.id = f"n{Nodo._seq}"
        self.burbujas = set()  # terminos
        self.aristas = set()  # ids de otros nodos (sin transitividad de membresia)

    def agregar(self, termino):
        self.burbujas.add(termino)


class Piscina:
    """Indice persistente: burbujas + nodos + aristas. Mantiene y
    optimiza la estructura; las cajas solo le informan eventos."""

    UMBRAL_FISION_PESO = 50  # placeholder, ajustable
    UMBRAL_FISION_BURBUJAS = 20

    def __init__(self):
        self.burbujas = {}  # termino -> Burbuja
        self.nodos = {}     # id -> Nodo

    def existe(self, termino):
        return termino in self.burbujas

    def crear_burbuja(self, termino):
        """Punto de entrada unico de creacion de burbuja (necesario
        para el event-sourcing: toda mutacion pasa por un metodo)."""
        self.burbujas[termino] = Burbuja(termino)
        return self.burbujas[termino]

    def reforzar(self, termino):
        """Punto de entrada unico de refuerzo de burbuja."""
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
        """Une varios nodos en uno solo (caso nuevo+nuevo)."""
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
        """Registra una relacion observada entre dos conceptos ya
        establecidos: arista explicita entre TODOS los pares de sus
        nodos. Unico lugar donde se crean aristas."""
        na = sorted(self.nodos_de(a))
        nb = sorted(self.nodos_de(b))
        for na_id in na:
            for nb_id in nb:
                if na_id != nb_id:
                    self.nodos[na_id].aristas.add(nb_id)
                    self.nodos[nb_id].aristas.add(na_id)

    def conectados(self, a, b, max_saltos=10):
        """NAVEGACION: mismo nodo (co-ocurrencia directa) -> True. Si no,
        BFS sobre ARISTAS explicitas. Compartir termino en consultas
        distintas NO conecta."""
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

    def _peso_nodo(self, nid):
        return sum(self.burbujas[t].peso for t in self.nodos[nid].burbujas)

    def optimizar(self):
        """Pasada de optimizacion proactiva -- fision de nodos que
        crecieron demasiado, consolidacion. Pensada para correr entre
        consultas, no bloqueante. Placeholder: implementacion real
        pendiente, requiere criterio de cuando/como dividir un nodo sin
        perder las relaciones."""
        candidatos = [
            n.id for n in self.nodos.values()
            if self._peso_nodo(n.id) > self.UMBRAL_FISION_PESO
            or len(n.burbujas) > self.UMBRAL_FISION_BURBUJAS
        ]
        return {"candidatos_fision": candidatos}

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


class Caja:
    """Procesador transitorio, sin estado persistente. Recibe los
    terminos de UNA consulta, los clasifica contra la piscina, detecta
    co-ocurrencias, e informa los eventos resultantes. No guarda nada
    despues de retornar."""

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
        """terminos: lista de strings ya tokenizados.

        Procesamiento SECUENCIAL por ventana (no todos-contra-todos):
        cada termino se compara solo contra los N terminos inmediatamente
        anteriores en la secuencia (VENTANA_COOCURRENCIA). Esto evita la
        explosion O(n^2) que generaba cientos de miles de eventos.
        """
        terminos = self._filtrar(terminos)
        eventos = []
        recien_creados = set()  # terminos cuya burbuja se creo en esta consulta

        # Pass 1: burbujas + nodos unitarios
        for t in terminos:
            if self.piscina.existe(t):
                self.piscina.reforzar(t)
                eventos.append({"tipo": "peso_reforzado", "termino": t})
            else:
                self.piscina.crear_burbuja(t)
                self.piscina.crear_unitario(t)
                recien_creados.add(t)
                eventos.append({"tipo": "nodo_creado", "termino": t})

        # Pass 2: co-ocurrencia por ventana secuencial.
        # "nuevo" = la burbuja se creo EN ESTA consulta. Solo un termino
        # que ya existia ANTES de la consulta puede generar aristas.
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


class LaCaja:
    """Orquestador de alto nivel: piscina + filtro + procesamiento de
    consultas completas (texto humano, no solo pares de terminos). Con
    db_path usa PiscinaPersistente (event-sourcing sobre SQLite); sin
    el, Piscina en memoria pura."""

    def __init__(self, filtro_ontologico=None, db_path=None):
        self.piscina = PiscinaPersistente(db_path) if db_path else Piscina()
        self.caja = Caja(self.piscina, filtro_ontologico)

    def procesar_consulta(self, texto):
        """Entrada principal: una consulta humana completa (ej:
        'Que masa tiene el Sol?'). Tokeniza, filtra, procesa con una
        Caja transitoria."""
        terminos = _tokenizar(texto)
        eventos = self.caja.procesar_terminos(terminos)
        return {"terminos_procesados": terminos, "eventos": eventos}

    def declarar_relacion(self, a, b):
        """API de bajo nivel: declara relacion entre dos terminos ya
        dados (no texto crudo). Util para el bridge MCP / tests."""
        return self.caja.procesar_terminos([a, b])

    def consultar(self, a, b):
        return self.piscina.conectados(a, b)

    def stats(self):
        return self.piscina.stats()

    def optimizar(self):
        return self.piscina.optimizar()