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

Pendientes abiertos (no decididos por este archivo):
  - fision de nodos (optimizar() solo lista candidatos, no divide)
  - criterio de capacidad de caja
  - persistencia en disco (la Piscina event-sourced la resolveria)
"""
import re
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
                self.piscina.burbujas[t].reforzar()
                eventos.append({"tipo": "peso_reforzado", "termino": t})
            else:
                self.piscina.burbujas[t] = Burbuja(t)
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
    consultas completas (texto humano, no solo pares de terminos)."""

    def __init__(self, filtro_ontologico=None):
        self.piscina = Piscina()
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