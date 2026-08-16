"""
Prototipo independiente (16/8/2026) — modelo de pertenencia multiple + 
conectividad estricta para La Caja.

Corrige el bug del "exilio" del modelo termino_a_nodo 1:1:
  - un termino puede participar en varios agrupamientos a la vez sin
    abandonar ninguno (burbujas dentro de/acopladas a burbujas).
  - conectividad (navegacion) usa SOLO aristas explicitas registradas
    por co-ocurrencia observada entre conceptos ya establecidos, nunca
    el simple overlap de membresia ("compartir termino" no es vecino).

Reglas:
  - Termino nuevo -> grupo unitario {t} + burbuja persistente.
  - nuevo+nuevo co-ocurriendo en la ventana -> se fusionan en UN grupo.
  - nuevo+existente co-ocurriendo -> el nuevo conserva su unitario y se
    crea un grupo compartido {nuevo, existente}; ambos pertenecen a el
    (acumulacion de membresia, no exilio). Sin arista.
  - existente+existente co-ocurriendo sin grupo comun -> ARISTA explicita
    entre sus grupos (relacion observada entre conceptos establecidos).
  - repetido -> refuerza peso de la burbuja.
  - conectados(a,b): mismo grupo -> True. Si no, BFS sobre ARISTAS.
"""
from collections import deque


FILTRO_ONTOLOGICO = {
    "el", "la", "los", "las", "un", "una", "unos", "unas",
    "de", "del", "a", "al", "en", "con", "por", "para", "sin", "sobre",
    "entre", "hacia", "hasta", "desde", "durante",
    "y", "o", "u", "e", "ni", "que", "pero", "si", "porque",
    "qué", "cual", "cuál", "quien", "quién", "como", "cómo",
    "tiene", "es", "son", "esta", "está", "hay",
}

VENTANA_COOCURRENCIA = 4


class Burbuja:
    """Un termino. Entidad persistente: vive una sola vez, con su peso y
    el conjunto de agrupamientos a los que pertenece (multi-membresia)."""

    def __init__(self, termino):
        self.termino = termino
        self.peso = 1
        self.grupos = set()  # ids de agrupamientos

    def reforzar(self):
        self.peso += 1


class Grupo:
    """Un contexto de co-ocurrencia. Referencia burbujas (muchos-a-muchos)
    y tiene aristas explicitas hacia otros grupos (navegacion)."""

    _seq = 0

    def __init__(self):
        Grupo._seq += 1
        self.id = f"g{Grupo._seq}"
        self.terminos = set()
        self.aristas = set()  # ids de otros grupos (SIN transitividad de membresia)

    def agregar(self, termino):
        self.terminos.add(termino)


class Piscina:
    def __init__(self):
        self.burbujas = {}  # termino -> Burbuja
        self.grupos = {}    # id -> Grupo

    def existe(self, termino):
        return termino in self.burbujas

    def grupos_de(self, termino):
        b = self.burbujas.get(termino)
        return set(b.grupos) if b else set()

    def comparten_grupo(self, a, b):
        return bool(self.grupos_de(a) & self.grupos_de(b))

    def _nuevo_grupo(self, *terminos):
        g = Grupo()
        for t in terminos:
            g.agregar(t)
            self.burbujas[t].grupos.add(g.id)
        self.grupos[g.id] = g
        return g

    def crear_unitario(self, termino):
        return self._nuevo_grupo(termino)

    def crear_compartido(self, a, b):
        return self._nuevo_grupo(a, b)

    def fusionar(self, grupo_ids):
        """Une varios grupos en uno solo (caso nuevo+nuevo)."""
        nuevo = Grupo()
        for gid in grupo_ids:
            g = self.grupos[gid]
            for t in g.terminos:
                nuevo.agregar(t)
                self.burbujas[t].grupos.discard(gid)
                self.burbujas[t].grupos.add(nuevo.id)
            for otro_id in g.aristas:
                if otro_id not in grupo_ids:
                    nuevo.aristas.add(otro_id)
                    self.grupos[otro_id].aristas.discard(gid)
                    self.grupos[otro_id].aristas.add(nuevo.id)
            del self.grupos[gid]
        self.grupos[nuevo.id] = nuevo
        return nuevo

    def arista_entre(self, a, b):
        """Registra una relacion observada entre dos conceptos ya
        establecidos: arista explicita entre TODOS los pares de sus
        grupos. El unico lugar donde se crean aristas."""
        gs_a = sorted(self.grupos_de(a))
        gs_b = sorted(self.grupos_de(b))
        for ga in gs_a:
            for gb in gs_b:
                if ga != gb:
                    self.grupos[ga].aristas.add(gb)
                    self.grupos[gb].aristas.add(ga)

    def conectados(self, a, b, max_saltos=10):
        """NAVEGACION: mismo grupo (co-ocurrencia directa) -> True.
        Si no, BFS sobre ARISTAS explicitas. Compartir termino en
        eventos distintos NO conecta."""
        if a == b:
            return True
        if self.comparten_grupo(a, b):
            return True
        ga = self.grupos_de(a)
        gb = self.grupos_de(b)
        if not ga or not gb:
            return False
        visitados = set(ga)
        cola = deque((gid, 0) for gid in ga)
        while cola:
            gid, saltos = cola.popleft()
            if saltos >= max_saltos:
                continue
            for vecino in self.grupos[gid].aristas:
                if vecino in gb:
                    return True
                if vecino not in visitados:
                    visitados.add(vecino)
                    cola.append((vecino, saltos + 1))
        return False

    def stats(self):
        return {
            "terminos": len(self.burbujas),
            "grupos": len(self.grupos),
            "aristas": sum(len(g.aristas) for g in self.grupos.values()) // 2,
        }


class Caja:
    """Procesador transitorio sin estado propio."""

    def __init__(self, piscina):
        self.piscina = piscina

    def _filtrar(self, terminos):
        vistos = []
        for t in terminos:
            if t not in FILTRO_ONTOLOGICO and t not in vistos:
                vistos.append(t)
        return vistos

    def procesar_terminos(self, terminos):
        terminos = self._filtrar(terminos)
        eventos = []
        recien_creados = set()  # terminos cuyo unitario se creo en esta consulta

        # Pass 1: burbujas + unitarios
        for t in terminos:
            if self.piscina.existe(t):
                self.piscina.burbujas[t].reforzar()
                eventos.append({"tipo": "peso_reforzado", "termino": t})
            else:
                self.piscina.burbujas[t] = Burbuja(t)
                self.piscina.crear_unitario(t)
                recien_creados.add(t)
                eventos.append({"tipo": "nodo_creado", "termino": t})

        # Pass 2: co-ocurrencia por ventana secuencial
        # nuevo = la burbuja se creo EN ESTA consulta. Solo un termino que
        # ya existia ANTES de la consulta puede generar aristas (relacion
        # observada entre conceptos establecidos).
        def unitario_fresco(x):
            gs = self.piscina.grupos_de(x)
            return len(gs) == 1 and len(self.piscina.grupos[next(iter(gs))].terminos) == 1

        for i, t in enumerate(terminos):
            for vecino in terminos[max(0, i - VENTANA_COOCURRENCIA):i]:
                if vecino == t:
                    continue
                if self.piscina.comparten_grupo(t, vecino):
                    continue
                nuevo_t = t in recien_creados
                nuevo_v = vecino in recien_creados
                if nuevo_t and nuevo_v and unitario_fresco(t) and unitario_fresco(vecino):
                    gs = self.piscina.grupos_de(t) | self.piscina.grupos_de(vecino)
                    self.piscina.fusionar(gs)
                    eventos.append({"tipo": "fusion_nodo_unico", "terminos": [vecino, t]})
                elif nuevo_t or nuevo_v:
                    self.piscina.crear_compartido(vecino, t)
                    eventos.append({"tipo": "grupo_compartido", "terminos": [vecino, t]})
                else:
                    self.piscina.arista_entre(t, vecino)
                    eventos.append({"tipo": "arista", "terminos": [vecino, t]})
        return eventos


class LaCaja:
    def __init__(self):
        self.piscina = Piscina()
        self.caja = Caja(self.piscina)

    def procesar_consulta(self, texto):
        import re
        terminos = re.findall(r"[a-záéíóúñü]+", texto.lower())
        return self.caja.procesar_terminos(terminos)

    def declarar_relacion(self, a, b):
        return self.caja.procesar_terminos([a, b])

    def consultar(self, a, b):
        return self.piscina.conectados(a, b)

    def stats(self):
        return self.piscina.stats()


def _check(nombre, cond, detalle=""):
    estado = "PASS" if cond else "FAIL"
    print(f"[{estado}] {nombre}" + (f"  -- {detalle}" if detalle else ""))
    return cond


def main():
    ok = True

    # --- Caso clave: exilio (bug original) ---
    la = LaCaja()
    la.procesar_consulta("gravedad")
    la.procesar_consulta("gravedad masa energia")
    solido = la.piscina.grupos_de("gravedad")
    ok &= _check("gravedad participa en >1 grupo (sin exilio)", len(solido) >= 2,
                 f"grupos={sorted(solido)}")

    # --- Multi-membresia: sol en 3 nodos (comportamiento reportado por Claude) ---
    la = LaCaja()
    la.procesar_consulta("sol")
    la.procesar_consulta("sol masa")
    la.procesar_consulta("sol luna")
    n_sol = la.piscina.grupos_de("sol")
    ok &= _check("sol en 3 agrupamientos (unitario + sol-masa + sol-luna)",
                 len(n_sol) == 3, f"grupos={sorted(n_sol)}")
    ok &= _check("sol sigue conectado a masa", la.consultar("sol", "masa"))
    ok &= _check("sol sigue conectado a luna", la.consultar("sol", "luna"))

    # --- FIX estricto: puente entre consultas distintas NO conecta ---
    # Consulta A: primero+td co-ocurren. Consulta B: ultimo+td co-ocurren.
    # Bajo conectividad laxa (compartir termino = vecino) conectarian via td.
    la = LaCaja()
    la.procesar_consulta("primero td")
    la.procesar_consulta("ultimo td")
    ok &= _check("puente cross-consulta NO conecta (td en medio)",
                 la.consultar("primero", "ultimo") is False,
                 f"stats={la.stats()}")

    # --- FIX estricto: ventana dentro de la misma consulta ---
    la = LaCaja()
    la.procesar_consulta("primero ta tb tc td te ultimo")
    g_primero = la.piscina.grupos_de("primero")
    g_ultimo = la.piscina.grupos_de("ultimo")
    ok &= _check("primero y ultimo no comparten grupo (ventana=4)",
                 not (g_primero & g_ultimo), f"p={sorted(g_primero)} u={sorted(g_ultimo)}")
    ok &= _check("primero y ultimo NO conectados (sin aristas en consulta all-nuevo)",
                 la.consultar("primero", "ultimo") is False)

    # --- Navegacion real: arista explicita entre conceptos establecidos ---
    # Se establecen tres conceptos por separado, y luego se observa la
    # co-ocurrencia existente+existente -> arista -> ruta navegable.
    la = LaCaja()
    la.procesar_consulta("doom3")
    la.procesar_consulta("idtech4")
    la.procesar_consulta("netradiant")
    ok &= _check("sin relacion observada, conceptos aislados",
                 la.consultar("doom3", "netradiant") is False)
    la.declarar_relacion("doom3", "idtech4")
    la.declarar_relacion("idtech4", "netradiant")
    ok &= _check("con co-ocurrencia existente+existente, arista creada",
                 la.consultar("doom3", "idtech4") and la.consultar("idtech4", "netradiant"),
                 f"stats={la.stats()}")
    ok &= _check("ruta multi-salto por aristas observadas (doom3->netradiant)",
                 la.consultar("doom3", "netradiant") is True,
                 f"stats={la.stats()}")

    # --- No relacion: gravedad vs banana ---
    la = LaCaja()
    la.procesar_consulta("gravedad")
    la.procesar_consulta("banana")
    ok &= _check("terminos sin relacion no conectan",
                 la.consultar("gravedad", "banana") is False)

    # --- Refuerzo de peso sin duplicar ---
    la = LaCaja()
    la.procesar_consulta("gravedad")
    la.procesar_consulta("gravedad")
    ok &= _check("repetido refuerza peso (peso=2, sin nodo nuevo)",
                 la.piscina.burbujas["gravedad"].peso == 2 and la.stats()["grupos"] == 1)

    # --- Filtro ontologico ---
    la = LaCaja()
    la.procesar_consulta("¿Qué masa tiene el Sol?")
    ok &= _check("filtro ontologico descarta funcionales",
                 all(not la.piscina.existe(w) for w in ("qué", "tiene", "el"))
                 and la.piscina.existe("masa") and la.piscina.existe("sol"))

    # --- Caja sin estado entre llamadas ---
    la = LaCaja()
    la.caja.procesar_terminos(["gravedad"])
    la.caja.procesar_terminos(["gravedad"])
    ok &= _check("caja transitoria, refuerzo vive en la piscina",
                 la.piscina.burbujas["gravedad"].peso == 2)

    print(f"\n{'TODOS LOS TESTS PASAN' if ok else 'HAY FALLOS'}  |  stats finales "
          f"terminos={la.stats()['terminos']} grupos={la.stats()['grupos']} aristas={la.stats()['aristas']}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
