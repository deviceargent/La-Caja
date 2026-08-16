"""
Núcleo de La Caja — reescrito (31/7/2026) sobre el modelo real descrito
por Miguel, reemplazando el diseño anterior (Union-Find plano + cache con
capacidad fija). Ver /areas/la-caja.md para el historial de la iteración
anterior — este archivo implementa el modelo de nodos-burbuja.

Mecanismo:
  - Filtro ontológico: descarta metainformación universal (artículos,
    preposiciones, puntuación) antes de procesar. Solo sustantivos/
    términos con peso semántico propio generan estructura.
  - Término nuevo (nunca visto) -> nodo unitario.
  - Dos términos NUEVOS co-ocurriendo en la misma consulta -> se
    fusionan en un único nodo (cada uno queda como "burbuja" adentro).
  - Término nuevo + término YA EXISTENTE co-ocurriendo -> el nuevo se
    vuelve su propio nodo, y se CONECTA (edge) a la burbuja específica
    del término existente -- no se absorbe en el nodo viejo. Esto evita
    que todo termine fusionado en un nodo gigante con el tiempo.
  - Término repetido (ya existe) -> no crea nada nuevo, sube el peso de
    su burbuja. Repetición = señal de importancia, no de acumulación.
  - Fisión: cuando un nodo crece demasiado (peso total o cantidad de
    burbujas supera un umbral), se separa en un nodo hijo -- "banco
    cercano" -- conectado al padre, en vez de perder la relación. No
    implementado como automático todavía: es una pasada de optimización
    separada (piscina.optimizar()), no bloqueante, para correr entre
    consultas.
  - Las cajas NO son almacenamiento persistente. Son procesadores de
    tránsito ("procesadores suaves") que sostienen términos solo
    mientras los analizan (clasificar nuevo/existente, ajustar peso,
    detectar co-ocurrencia) y le informan el resultado a la piscina.
    No queda estado en la caja después de procesar una consulta.
  - La piscina es el índice persistente real -- mantiene los nodos, el
    mapeo término->nodo, y corre la optimización proactiva (fisión,
    consolidación) como algoritmo aparte, entre consultas.
"""
import re
import uuid
from collections import deque


FILTRO_ONTOLOGICO_DEFAULT = {
    # artículos
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


def _tokenizar(texto):
    """Extrae palabras, sin puntuación, en minúsculas."""
    return re.findall(r"[a-záéíóúñü]+", texto.lower())


class Burbuja:
    """Un término, con su peso (cuántas veces reforzado)."""

    def __init__(self, termino):
        self.termino = termino
        self.peso = 1

    def reforzar(self):
        self.peso += 1


class Nodo:
    """Contenedor de una o más burbujas relacionadas por co-ocurrencia.
    Puede tener nodos hijos (fisión) y un padre si él mismo es resultado
    de una fisión."""

    def __init__(self, nodo_id=None):
        self.id = nodo_id or str(uuid.uuid4())[:8]
        self.burbujas = {}  # termino -> Burbuja
        self.conexiones = set()  # ids de otros nodos conectados (edges)
        self.nodo_padre = None
        self.nodos_hijos = set()

    def agregar_burbuja(self, termino):
        self.burbujas[termino] = Burbuja(termino)

    def peso_total(self):
        return sum(b.peso for b in self.burbujas.values())


class Piscina:
    """Índice persistente: nodos + mapeo término->nodo. Mantiene y
    optimiza la estructura; las cajas solo le informan eventos."""

    UMBRAL_FISION_PESO = 50  # placeholder, ajustable
    UMBRAL_FISION_BURBUJAS = 20

    def __init__(self):
        self.nodos = {}  # nodo_id -> Nodo
        self.termino_a_nodo = {}  # termino -> nodo_id

    def existe(self, termino):
        return termino in self.termino_a_nodo

    def nodo_de(self, termino):
        nodo_id = self.termino_a_nodo.get(termino)
        return self.nodos.get(nodo_id) if nodo_id else None

    def crear_nodo_unitario(self, termino):
        nodo = Nodo()
        nodo.agregar_burbuja(termino)
        self.nodos[nodo.id] = nodo
        self.termino_a_nodo[termino] = nodo.id
        return nodo

    def reforzar_termino(self, termino):
        nodo = self.nodo_de(termino)
        if nodo and termino in nodo.burbujas:
            nodo.burbujas[termino].reforzar()

    def fusionar_en_nodo_unico(self, termino_a, termino_b):
        """Caso: ambos términos son nuevos. Se crea UN nodo con ambos
        como burbujas."""
        nodo = Nodo()
        nodo.agregar_burbuja(termino_a)
        nodo.agregar_burbuja(termino_b)
        self.nodos[nodo.id] = nodo
        self.termino_a_nodo[termino_a] = nodo.id
        self.termino_a_nodo[termino_b] = nodo.id
        return nodo

    def conectar_termino_nuevo_a_existente(self, termino_nuevo, termino_existente):
        """Caso: uno es nuevo, el otro ya vive en algún nodo. El nuevo
        se vuelve su propio nodo unitario, conectado (edge) al nodo del
        existente -- sin absorberse en él."""
        nodo_nuevo = self.crear_nodo_unitario(termino_nuevo)
        nodo_existente = self.nodo_de(termino_existente)
        if nodo_existente:
            nodo_nuevo.conexiones.add(nodo_existente.id)
            nodo_existente.conexiones.add(nodo_nuevo.id)
        return nodo_nuevo

    def conectar_existentes(self, termino_a, termino_b):
        """Caso: ambos ya existen (en el mismo nodo o distintos). Si
        están en nodos distintos, se conectan por edge (no se fusionan)."""
        nodo_a = self.nodo_de(termino_a)
        nodo_b = self.nodo_de(termino_b)
        if nodo_a and nodo_b and nodo_a.id != nodo_b.id:
            nodo_a.conexiones.add(nodo_b.id)
            nodo_b.conexiones.add(nodo_a.id)

    def conectados(self, termino_a, termino_b, max_saltos=10):
        """BFS sobre el grafo de NODOS (no de términos crudos) --
        atraviesa tanto burbujas-dentro-del-mismo-nodo como edges entre
        nodos distintos, y la jerarquía de fisión (padre/hijos)."""
        nodo_a = self.nodo_de(termino_a)
        nodo_b = self.nodo_de(termino_b)
        if not nodo_a or not nodo_b:
            return False
        if nodo_a.id == nodo_b.id:
            return True

        visitados = {nodo_a.id}
        cola = deque([(nodo_a.id, 0)])
        while cola:
            actual_id, saltos = cola.popleft()
            if saltos >= max_saltos:
                continue
            actual = self.nodos[actual_id]
            vecinos = actual.conexiones | actual.nodos_hijos
            if actual.nodo_padre:
                vecinos = vecinos | {actual.nodo_padre}
            for vecino_id in vecinos:
                if vecino_id == nodo_b.id:
                    return True
                if vecino_id not in visitados:
                    visitados.add(vecino_id)
                    cola.append((vecino_id, saltos + 1))
        return False

    def optimizar(self):
        """Pasada de optimización proactiva -- fisión de nodos que
        crecieron demasiado, consolidación. Pensada para correr entre
        consultas, no bloqueante. Placeholder: implementación real
        pendiente, requiere criterio de cuándo/cómo dividir un nodo sin
        perder las relaciones (banco cercano conectado al padre)."""
        candidatos_fision = [
            n for n in self.nodos.values()
            if n.peso_total() > self.UMBRAL_FISION_PESO
            or len(n.burbujas) > self.UMBRAL_FISION_BURBUJAS
        ]
        return {"candidatos_fision": [n.id for n in candidatos_fision]}

    def stats(self):
        return {
            "nodos_totales": len(self.nodos),
            "terminos_indexados": len(self.termino_a_nodo),
            "peso_promedio_por_nodo": (
                sum(n.peso_total() for n in self.nodos.values()) / len(self.nodos)
                if self.nodos else 0
            ),
        }


class Caja:
    """Procesador transitorio, sin estado persistente. Recibe los
    términos de UNA consulta, los clasifica contra la piscina, detecta
    co-ocurrencias, e informa los eventos resultantes. No guarda nada
    después de retornar -- por eso es un método, no un objeto que vive
    entre llamadas."""

    def __init__(self, piscina, filtro_ontologico=None):
        self.piscina = piscina
        self.filtro = filtro_ontologico or FILTRO_ONTOLOGICO_DEFAULT

    def _filtrar(self, terminos):
        vistos = []
        for t in terminos:
            if t not in self.filtro and t not in vistos:
                vistos.append(t)
        return vistos

    VENTANA_COOCURRENCIA = 4  # cuantos terminos previos revisa cada termino, no todo el mensaje

    def procesar_terminos(self, terminos):
        """terminos: lista de strings ya tokenizados.

        BUGFIX (02/8/2026): procesamiento SECUENCIAL por ventana, no
        todos-contra-todos. El diseño anterior comparaba cada termino
        contra TODOS los demas del mismo mensaje (O(n^2)) -- confirmado
        con datos reales: 72 mensajes de un export real de ChatGPT
        generaron 324.677 eventos, dejando solo 72 nodos para 2164
        terminos indexados (la mayoria nunca formo nodo propio).
        Ahora cada termino se compara solo contra los N terminos
        inmediatamente anteriores en la secuencia (ventana), como
        describio Miguel: las cajitas "estampan" termino por termino,
        de forma secuencial, no en barrido exhaustivo.
        """
        terminos = self._filtrar(terminos)
        eventos = []
        clasificacion = {}  # termino -> "nuevo" | "existente", solo para esta consulta

        for t in terminos:
            if self.piscina.existe(t):
                self.piscina.reforzar_termino(t)
                eventos.append({"tipo": "peso_reforzado", "termino": t})
                clasificacion[t] = "existente"
            else:
                self.piscina.crear_nodo_unitario(t)
                eventos.append({"tipo": "nodo_creado", "termino": t})
                clasificacion[t] = "nuevo"

        for i, t in enumerate(terminos):
            ventana = terminos[max(0, i - self.VENTANA_COOCURRENCIA):i]
            for vecino in ventana:
                if vecino == t:
                    continue
                nodo_t = self.piscina.nodo_de(t)
                nodo_vecino = self.piscina.nodo_de(vecino)
                if not nodo_t or not nodo_vecino or nodo_t.id == nodo_vecino.id:
                    continue

                ambos_nuevos = clasificacion.get(t) == "nuevo" and clasificacion.get(vecino) == "nuevo"
                if ambos_nuevos:
                    self._fusionar_nodos_unitarios_recien_creados(t, vecino)
                    eventos.append({"tipo": "fusion_nodo_unico", "terminos": [vecino, t]})
                    clasificacion[t] = "existente"
                    clasificacion[vecino] = "existente"
                else:
                    self.piscina.conectar_existentes(t, vecino)
                    eventos.append({"tipo": "conexion", "terminos": [vecino, t]})

        return eventos

    def _fusionar_nodos_unitarios_recien_creados(self, a, b):
        """Ambos términos acaban de crear nodo unitario propio en esta
        misma consulta -- los fusiona en un solo nodo con dos burbujas,
        descartando los dos nodos unitarios previos."""
        nodo_a = self.piscina.nodo_de(a)
        nodo_b = self.piscina.nodo_de(b)
        if not nodo_a or not nodo_b or nodo_a.id == nodo_b.id:
            return
        del self.piscina.nodos[nodo_a.id]
        del self.piscina.nodos[nodo_b.id]
        self.piscina.fusionar_en_nodo_unico(a, b)


class LaCaja:
    """Orquestador de alto nivel: piscina + filtro + procesamiento de
    consultas completas (texto humano, no solo pares de términos)."""

    def __init__(self, filtro_ontologico=None):
        self.piscina = Piscina()
        self.filtro = filtro_ontologico or FILTRO_ONTOLOGICO_DEFAULT

    def procesar_consulta(self, texto):
        """Entrada principal: una consulta humana completa (ej:
        '¿Qué masa tiene el Sol?'). Tokeniza, filtra, procesa con una
        Caja transitoria."""
        terminos = _tokenizar(texto)
        caja = Caja(self.piscina, self.filtro)
        eventos = caja.procesar_terminos(terminos)
        return {"terminos_procesados": terminos, "eventos": eventos}

    def declarar_relacion(self, a, b):
        """API de bajo nivel: declara relación entre dos términos ya
        dados (no texto crudo). Útil para el bridge MCP / tests."""
        caja = Caja(self.piscina, self.filtro)
        eventos = caja.procesar_terminos([a, b])
        return {"eventos": eventos}

    def consultar(self, a, b):
        conectado = self.piscina.conectados(a, b)
        return conectado, "grafo_de_nodos"

    def stats(self):
        return self.piscina.stats()

    def optimizar(self):
        return self.piscina.optimizar()
