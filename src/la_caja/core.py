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
    establecidos. Es la UNICA forma de crear aristas. Presupuesto de
    navegacion: se conectan los contextos mas reforzados de cada
    termino, acotado a ventana x ventana aristas por observacion (el
    bipartito completo entre todas las membresias explotaba a millones
    de aristas en corpus reales).
  - repetido -> refuerza peso de la burbuja.
  - relacion(a, b): confianza en [0, 1]. 1.0 = OBSERVADO (termino
    identico, co-ocurrencia directa, arista explicita entre los
    conceptos); 0.5^puentes = INFERIDO por cierre transitivo (cada
    puente observado cruzado divide la confianza a la mitad); 0.0 =
    sin relacion. Compartir termino en consultas distintas NO conecta.
    conectados() es su wrapper booleano.

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
    arista_entre, fisionar_nodo, fijar_peso) son el unico punto de
    entrada de mutacion.
  - El log es tambien el soporte del criterio temporal de la arista
    estricta: el orden global de nacimiento de burbujas queda persistido.

Fision de membresia (fusion 16/8/2026):
  - Los nodos NO crecen (cap-2 estructural: ningun nodo supera 2
    burbujas), asi que el sustrato de fision no es el nodo sino la
    MEMBRESIA ACUMULADA DE UN TERMINO: con el tiempo un termino se
    vuelve un hub de activacion ('masa' alcanzo 17 contextos en 15
    consultas). Activar el termino prima todos esos contextos a la vez.
  - optimizar() fisiona un termino sobrecargado: demote sus membresias
    compartidas MAS DEBILES (menor peso combinado) partiendo el nodo
    {t,u,...} en unitarios + ARISTAS DE PAR PRECISAS entre esos
    unitarios (sin fan-out). Principio: ACTIVACION para lo reforzado,
    NAVEGACION para lo debil -- la regla de oro como consolidacion.
  - Las aristas de fision son honestas (la pareja co-ocurrio; por eso
    existia el nodo): no son puentes espurios ni fan-out, y el BFS
    multi-salto sobre ellas es la navegacion normal del modelo.
  - fisionar_nodo(nid) es un evento del log: el replay lo repite, el
    estado no diverge.

Criterio de capacidad de caja (fusion 16/8/2026):
  - La capacidad de la caja es la ventana de co-ocurrencia: el
    presupuesto de asociacion POR TERMINO (cuantos predecesores ve cada
    termino). Decide cuantas asociaciones crea una consulta.
  - Criterio del codo: sobre un corpus con asociaciones verdaderas
    conocidas, se mide la curva de asociaciones genuinas marginales por
    ventana; la capacidad es la MENOR ventana donde la ganancia marginal
    colapsa por debajo del 5% de la ganancia maxima (el recall ya
    saturado), punto a partir del cual ventanas mayores solo suman
    asociaciones espurias. El numero deja de ser arbitrario.
  - Validacion: corpus sintetico (6 temas x 10 terminos, mensajes largos
    con intrusiones) -> el criterio da 4, la constante adoptada
    (VENTANA_COOCURRENCIA). Ahi recall = 0.97; mas ventana no suma
    genuinas, solo espurias.

Decay de peso / olvido (fusion 16/8/2026):
  - Cierra el hueco que la discusion dejo señalado: el peso solo subia,
    nunca bajaba. Para memoria humana, el olvido por no-uso es
    esencial: un termino no reforzado por demasiados eventos pierde
    peso hacia un piso.
  - Determinismo para el event-sourcing: la staleness se mide en
    CONTEO DE EVENTOS del log (n_eventos - ultimo_evento), no en reloj
    de pared, para que el replay reconstruya exactamente el mismo
    estado. Cada burbuja registra ultimo_evento (nacimiento o ultimo
    refuerzo); decaer() es pura lectura de estado y delega el cambio en
    fijar_peso, que el event-sourcing registra.
  - Piso: el peso nunca baja de 1 -- el rastro de que el termino existe
    no desaparece; solo se desactiva la fuerza de su asociacion.
  - Regla concreta: peso -> max(piso, peso - max(1, peso//2)) cuando
    la staleness supera UMBRAL_DECAY_EVENTOS. decaer() corre al inicio
    de optimizar() (consolidacion), antes de la fision, para que los
    pesos de la fision sean los efectivos.

Resolucion de sinonimos / identidad (fusion 16/8/2026):
  - Capa de identidad pre-caja en LaCaja: la piscina SOLO ve conceptos
    canonicos. 'masa del sol' y 'masa solar' convergen al mismo concepto
    (sol), que refuerza y navega como una sola entidad; 'sol' y 'solar'
    dejan de fragmentar la memoria.
  - Dos mecanismos deterministicos: (1) ALIASES_SINONIMOS, mapa
    declarativo extensible (solar->sol, lunar->luna); (2) morfologia
    derivativa SEGURA: un token con sufijo adjetival (-ar, -al, -ico,
    -ivo, -ino) se canoniza a su raiz SOLO si esa raiz ya existe como
    burbuja -- no inventa conceptos; si la raiz no existe, la forma
    nace normal. Con restauracion de vocal nominal (lunar->lun->luna).
  - La normalizacion vive en el orquestador (LaCaja), no en la Caja:
    la Caja sigue siendo un procesador transitorio puro. La resolucion
    es por consulta (contra el estado pre-consulta de la piscina).

Promocion jerarquica tipo HNSW (fusion 16/8/2026):
  - Mecanismo SEPARADO de la navegacion: la jerarquia es una funcion
    DERIVADA del peso (nivel_promocion), sin estado propio, luego
    trivualmente segura para el event-sourcing (no genera eventos).
    Promociona al reforzar, desciende al olvidar (decay): la promocion
    es bidireccional.
  - contexto_primado(termino, presupuesto) ordena el paquete de
    contexto: las RELACIONES OBSERVADAS del termino primero (memorias
    reforzadas, por fuerza de refuerzo) y luego el vecindario de
    ACTIVACION (co-membresia), ambos por relevancia (fuerza, nivel,
    peso) y acotado al presupuesto. NO toca aristas: el nivel es
    ortogonal a consultar() (no crea ni destruye navegacion).

Navegacion con consciencia de distancia (fusion 17/8/2026):
  - La regla estricta hizo las aristas HONESTAS (solo co-ocurrencia
    existente+existente), pero no las acoto en el tiempo: el cierre
    transitivo (BFS) sobre el grafo fabricaba pares que nadie observo
    -- 'motor del piano' conectaba cilindro y nota por encadenar
    motor->piano, y a escala de anos la densificacion monotonica hacia
    TODO alcanzable en pocos saltos: la memoria 'sabe todo conectado'
    (alucinacion). Podar aristas era falso remedio: mataba la
    asociacion abstracta legitima. Las personas piensan en abstracto y
    conectan dominios (motor+piano es MEMORIA, no error). La salida no
    es borrar asociaciones sino hacer VISIBLE la distancia de la
    inferencia.
  - relacion(a, b) devuelve CONFIANZA en [0, 1]: 1.0 SOLO para lo
    observado (identico, co-ocurrencia directa, o la pareja de
    conceptos de una arista explicita). Toda ruta inferida cruza
    puentes observados y cada puente divide la confianza por 2:
    motor-piano = 1.0 (observado); cilindro-nota via motor-piano =
    0.5 (inferido, recuperable pero jamas igual a un recuerdo);
    doom3-netradiant = 0.25 (dos puentes cruzados). La pareja
    observada vive en self.relaciones (CONCEPTOS, no nodos): el
    fan-out de nodos de arista_entre borraria quien fue realmente
    observado y el BFS no podria distinguir.

Relaciones con refuerzo y olvido (iteracion 2, 17/8/2026):
  - El experimento organico (experiments/falsacion.md) falsaco la
    tesis de no-densificacion: relaciones y aristas acumulaban todo
    monotonamente (componente gigante 86%, todo conectado). La salida
    es OLVIDO, no poda ajena: self.relaciones es ahora un dict de
    {par: fuerza, ultimo_evento}. Cada co-ocurrencia observada
    (arista_entre / fisionar_nodo) REFUERZA la relacion en vez de solo
    registrarla.
  - decaer() olvida relaciones: una relacion no reforzada por mas de
    UMBRAL_DECAY_EVENTOS pierde fuerza (mitad hacia el piso); en 0 se
    PODE la relacion y sus aristas exactas (aristas_por_relacion
    registra que aristas materializo cada relacion). Solo sobreviven
    las asociaciones reforzadas de verdad: el grafo se vuelve esparso,
    la escala 0.5^k vuelve a discriminar, y la selectividad (lo que
    queda como observado es lo que co-ocurre fuerte) sube.
  - La poda es evento del log (prune_relacion, fijar_fuerza_relacion):
    el replay reconstruye el olvido byte a byte.
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

# Sinonimos declarativos: forma superficial -> concepto canonico.
# Extensible en runtime via LaCaja.declarar_sinonimo().
ALIASES_SINONIMOS = {
    "solar": "sol",
    "lunar": "luna",
    "estelar": "estrella",
    "terrestre": "tierra",
    "gravitacional": "gravedad",
    "energetico": "energia",
}

# Sufijos adjetivales derivativos (espanol). La morfologia solo
# canoniza cuando la raiz ya existe como burbuja: nunca inventa.
SUFIJOS_ADJETIVALES = ("ar", "al", "ico", "ivo", "ino")


def _raices_derivativas(token):
    """Raices candidatas de un adjetivo derivado de sustantivo: el token
    menos el sufijo, y esa raiz con vocales nominales restauradas
    (solar->sol, lunar->lun->luna, musical->music->musica)."""
    for suf in SUFIJOS_ADJETIVALES:
        if token.endswith(suf) and len(token) - len(suf) >= 2:
            base = token[: -len(suf)]
            yield base
            for vocal in ("a", "o", "e"):
                yield base + vocal


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
        self.ultimo_evento = 0  # evento del log de nacimiento o ultimo refuerzo

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

    UMBRAL_FISION_MEMBRESIAS = 8
    UMBRAL_DECAY_EVENTOS = 50  # eventos de no-uso antes de olvidar
    FACTOR_DECAY = 2  # olvido: el peso se reduce a la mitad hacia el piso
    PISO_DECAY = 1  # el rastro del termino no desaparece nunca
    UMBRAL_DECAY_RELACION = 400  # eventos de no-uso antes de olvidar una relacion
    FACTOR_DECAY_RELACION = 4  # olvido de relaciones 4x mas suave que el de terminos
    UMBRALES_NIVEL = (1, 3, 10, 30)  # promocion: umbrales de peso por nivel

    def __init__(self):
        self.burbujas = {}  # termino -> Burbuja
        self.nodos = {}     # id -> Nodo
        self.relaciones = {}  # par (conceptos) -> {"fuerza", "ultimo_evento"}
        self.relaciones_por_termino = {}  # termino -> set(partners) (indice de primado)
        self.aristas_por_relacion = {}  # par -> set de aristas exactas que materializo
        self._n_eventos = 0  # contador de mutaciones (escala del olvido)

    def existe(self, termino):
        return termino in self.burbujas

    def crear_burbuja(self, termino):
        """Punto de entrada unico de creacion de burbuja (necesario
        para el event-sourcing: toda mutacion pasa por un metodo)."""
        self._n_eventos += 1
        b = Burbuja(termino)
        b.ultimo_evento = self._n_eventos
        self.burbujas[termino] = b
        return b

    def reforzar(self, termino):
        """Punto de entrada unico de refuerzo de burbuja."""
        self._n_eventos += 1
        b = self.burbujas[termino]
        b.ultimo_evento = self._n_eventos
        b.reforzar()

    def fijar_peso(self, termino, peso):
        """Fija el peso de una burbuja (consolidacion / olvido). NO
        cuenta como evento de uso: no avanza la staleness."""
        self.burbujas[termino].peso = peso

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
        self._n_eventos += 1
        return self._nuevo_nodo(termino)

    def crear_compartido(self, a, b):
        self._n_eventos += 1
        return self._nuevo_nodo(a, b)

    def fusionar(self, nodo_ids):
        """Une varios nodos en uno solo (caso nuevo+nuevo)."""
        self._n_eventos += 1
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
        """Registra y REFUERZA una relacion observada entre dos
        conceptos ya establecidos: la pareja sube su contador de
        co-ocurrencia en self.relaciones (confianza 1.0) y materializa
        aristas de navegacion entre los VENTANA_COOCURRENCIA contextos
        (nodos) MAS reforzados de cada termino. Presupuesto de
        navegacion: conectividad de par completa para grafos pequenos,
        acotada a K x K aristas por observacion (el bipartito completo
        entre TODAS las membresias llegaba a millones de aristas en
        corpus reales). Las aristas se registran por relacion para que
        el olvido las pode con exactitud. Unico lugar donde se crean
        aristas (con fisionar_nodo)."""
        self._n_eventos += 1
        na = sorted(
            self.nodos_de(a),
            key=lambda nid: (self._peso_nodo(nid), nid),
            reverse=True,
        )[:VENTANA_COOCURRENCIA]
        nb = sorted(
            self.nodos_de(b),
            key=lambda nid: (self._peso_nodo(nid), nid),
            reverse=True,
        )[:VENTANA_COOCURRENCIA]
        aristas = {(x, y) for x in na for y in nb if x != y}
        self._marcar_relacion(a, b, aristas)

    def _marcar_relacion(self, a, b, aristas):
        """Crea o refuerza una relacion observada y registra las
        aristas de navegacion que materializa (aristas_por_relacion,
        para la poda exacta del olvido). NO cuenta evento: el llamador
        (arista_entre / fisionar_nodo) lo hace una vez por operacion."""
        clave = tuple(sorted((a, b)))
        if clave in self.relaciones:
            self.relaciones[clave]["fuerza"] += 1
            self.relaciones[clave]["refuerzos"] += 1
            self.relaciones[clave]["ultimo_evento"] = self._n_eventos
        else:
            self.relaciones[clave] = {"fuerza": 1, "ultimo_evento": self._n_eventos, "refuerzos": 1}
            self.relaciones_por_termino.setdefault(a, set()).add(b)
            self.relaciones_por_termino.setdefault(b, set()).add(a)
            self.aristas_por_relacion[clave] = set()
        self.aristas_por_relacion[clave].update(aristas)
        for x, y in aristas:
            self.nodos[x].aristas.add(y)
            self.nodos[y].aristas.add(x)

    def fijar_fuerza_relacion(self, a, b, fuerza):
        """Fija la fuerza de una relacion observada (olvido gradual).
        NO cuenta como evento de uso: no avanza la staleness."""
        clave = tuple(sorted((a, b)))
        if clave in self.relaciones:
            self.relaciones[clave]["fuerza"] = fuerza

    def prune_relacion(self, a, b):
        """Olvido completo de una relacion observada: elimina la
        relacion y sus aristas de navegacion exactas. Se llama desde
        decaer() dentro de la pasada de consolidacion."""
        clave = tuple(sorted((a, b)))
        if clave not in self.relaciones:
            return
        for x, y in self.aristas_por_relacion.pop(clave, set()):
            if x in self.nodos and y in self.nodos:
                self.nodos[x].aristas.discard(y)
                self.nodos[y].aristas.discard(x)
        del self.relaciones[clave]
        for t in (a, b):
            partners = self.relaciones_por_termino.get(t)
            if partners is not None:
                partners.discard(a if t == b else b)
                if not partners:
                    del self.relaciones_por_termino[t]

    def relacion(self, a, b, max_saltos=10):
        """NAVEGACION con consciencia de distancia. Devuelve la confianza
        de la relacion entre a y b en [0, 1], distinguiendo lo OBSERVADO
        de lo INFERIDO (el cierre transitivo deja de alucinar invisible):
          - 1.0   termino identico, co-ocurrencia directa (membresia) o
                  la pareja observada de una arista explicita.
          - 0.5^k (k >= 1): INFERENCIA por cierre transitivo; k = numero
                  de puentes observados cruzados en el camino mas corto
                  de nodos. Recuperable, pero jamas igual a un recuerdo.
          - 0.0   sin relacion.
        Compartir termino en consultas distintas NO conecta."""
        if a == b:
            return 1.0
        if self.comparten_nodo(a, b):
            return 1.0
        if tuple(sorted((a, b))) in self.relaciones:
            return 1.0
        na = self.nodos_de(a)
        nb = self.nodos_de(b)
        if not na or not nb:
            return 0.0
        visitados = set(na)
        cola = deque((nid, 0) for nid in na)
        while cola:
            nid, saltos = cola.popleft()
            if saltos >= max_saltos:
                continue
            for vecino in self.nodos[nid].aristas:
                if vecino in nb:
                    return 0.5 ** (saltos + 1)
                if vecino not in visitados:
                    visitados.add(vecino)
                    cola.append((vecino, saltos + 1))
        return 0.0

    def conectados(self, a, b, max_saltos=10):
        """Wrapper booleano de relacion(): hay relacion cuando la
        confianza es mayor que cero."""
        return self.relacion(a, b, max_saltos) > 0

    def _peso_nodo(self, nid):
        return sum(self.burbujas[t].peso for t in self.nodos[nid].burbujas)

    def _unitario_de(self, termino):
        """Reusa el nodo unitario del termino si existe; si no, lo crea.
        Usa _nuevo_nodo (metodo base privado) en lugar de crear_unitario
        para no re-disparar el registro del event-sourcing cuando se
        llama dentro de fisionar_nodo."""
        for nid in self.nodos_de(termino):
            if self.nodos[nid].burbujas == {termino}:
                return nid
        return self._nuevo_nodo(termino).id

    def fisionar_nodo(self, nid):
        """Convierte un nodo de co-ocurrencia (activacion conjunta) en
        una red de navegacion: un unitario por burbuja + aristas de par
        PRECISAS entre esos unitarios (sin fan-out). La membresia
        compartida cede a la navegacion: es la regla de oro aplicada
        como consolidacion. Devuelve None si el nodo no era divisible."""
        n = self.nodos[nid]
        if len(n.burbujas) < 2:
            return None
        self._n_eventos += 1
        terminos = sorted(n.burbujas)
        unitarios = {v: self._unitario_de(v) for v in terminos}
        for v in terminos:
            self.burbujas[v].nodos.discard(nid)
        for otro_id in n.aristas:
            self.nodos[otro_id].aristas.discard(nid)
        del self.nodos[nid]
        for i in range(len(terminos)):
            for j in range(i + 1, len(terminos)):
                a = unitarios[terminos[i]]
                b = unitarios[terminos[j]]
                self._marcar_relacion(terminos[i], terminos[j], {(a, b)})
        return unitarios

    def decaer(self, umbral=None):
        """Olvido determinista por no-uso: un termino no reforzado por
        mas de `umbral` eventos pierde peso hacia el piso (nunca baja de
        PISO_DECAY). La staleness se mide en conteo de eventos del log
        (determinista para el replay), no en reloj de pared. Pura
        lectura de estado: cada cambio se delega en fijar_peso, que el
        event-sourcing registra. Tambien olvida RELACIONES con gracia
        PROPORCIONAL AL REFUERZO HISTORICO (UMBRAL_DECAY_RELACION x
        refuerzos): la fuerza decae suave hacia el piso 0 y, en 0, se
        PODE la relacion y sus aristas exactas (prune_relacion). Un tema
        muy reforzado aguanta vacios largos; la co-ocurrencia incidental
        de una sola vez muere rapido."""
        umbral = umbral if umbral is not None else self.UMBRAL_DECAY_EVENTOS
        decaidos = []
        for t, b in self.burbujas.items():
            if self._n_eventos - b.ultimo_evento > umbral and b.peso > self.PISO_DECAY:
                nuevo = max(self.PISO_DECAY, b.peso - max(1, b.peso // self.FACTOR_DECAY))
                self.fijar_peso(t, nuevo)
                decaidos.append(t)
        # Las relaciones se olvidan con su propia escala: mas lentas que
        # los terminos (FACTOR_DECAY_RELACION=4) y con una gracia de
        # no-uso PROPORCIONAL AL REFUERZO HISTORICO acumulado
        # (UMBRAL_DECAY_RELACION x refuerzos): un tema muy reforzado se
        # banca vacios largos antes de podarse (el historial lo
        # distingue de una coincidencia incidental), una relacion vista
        # una sola vez muere rapido. La fuerza decae suave y en 0 se
        # poda la relacion y sus aristas exactas.
        for clave, datos in list(self.relaciones.items()):
            refuerzos = datos.get("refuerzos", 1)
            gracia = self.UMBRAL_DECAY_RELACION * refuerzos
            if self._n_eventos - datos["ultimo_evento"] > gracia and datos["fuerza"] > 0:
                nueva = max(
                    0,
                    datos["fuerza"] - max(1, datos["fuerza"] // self.FACTOR_DECAY_RELACION),
                )
                self.fijar_fuerza_relacion(*clave, nueva)
                if nueva == 0:
                    self.prune_relacion(*clave)
        return {"decaidos": decaidos}

    def optimizar(self, max_membresias=None):
        """Pasada de consolidacion entre consultas, no bloqueante:
        1) olvido: decaer() los terminos no reforzados; 2) fision: para
        cada termino con membresias sobre el limite, demote las mas
        debiles hasta volver al limite. Devuelve decaidos y fisionados."""
        decaidos = self.decaer().get("decaidos", [])
        limite = max_membresias if max_membresias is not None else self.UMBRAL_FISION_MEMBRESIAS
        fisionados = []
        for t in sorted(self.burbujas):
            while len(self.nodos_de(t)) > limite:
                compartidos = [nid for nid in self.nodos_de(t) if len(self.nodos[nid].burbujas) > 1]
                if not compartidos:
                    break
                debil = min(compartidos, key=lambda nid: (self._peso_nodo(nid), nid))
                if self.fisionar_nodo(debil) is not None:
                    fisionados.append(debil)
        return {"decaidos": decaidos, "fisionados": fisionados}

    def stats(self):
        return {
            "terminos": len(self.burbujas),
            "nodos": len(self.nodos),
            "aristas": sum(len(n.aristas) for n in self.nodos.values()) // 2,
        }

    def nivel_promocion(self, termino):
        """Nivel de la jerarquia, DERIVADO del peso (sin estado propio):
        cuantos umbrales de peso supera. Promociona al reforzar,
        desciende al olvidar. No toca la navegacion."""
        b = self.burbujas.get(termino)
        if not b:
            return 0
        nivel = 0
        for u in self.UMBRALES_NIVEL:
            if b.peso >= u:
                nivel += 1
        return nivel

    def contexto_primado(self, termino, presupuesto=10):
        """Vista de primado de contexto: las RELACIONES OBSERVADAS del
        termino primero (memorias reforzadas, ordenadas por fuerza de
        refuerzo) y luego el vecindario de ACTIVACION (co-membresia),
        todos por relevancia (fuerza de relacion, nivel, peso) y
        acotados al presupuesto. Mecanismo SEPARADO de la navegacion:
        no usa aristas ni las modifica."""
        candidatos = {}
        for v in self.relaciones_por_termino.get(termino, ()):
            b = self.burbujas[v]
            candidatos[v] = (
                self.relaciones[tuple(sorted((termino, v)))]["fuerza"],
                self.nivel_promocion(v),
                b.peso,
            )
        for nid in self.nodos_de(termino):
            for otro in self.nodos[nid].burbujas:
                if otro != termino and otro not in candidatos:
                    candidatos[otro] = (0, self.nivel_promocion(otro), self.burbujas[otro].peso)
        ordenados = sorted(candidatos, key=lambda t: candidatos[t], reverse=True)
        return ordenados[:presupuesto]

    # -- serializacion para snapshots --
    def a_dict(self):
        return {
            "_n_eventos": self._n_eventos,
            "burbujas": {t: {"peso": b.peso, "nodos": sorted(b.nodos), "ultimo_evento": b.ultimo_evento} for t, b in self.burbujas.items()},
            "nodos": {nid: {"burbujas": sorted(n.burbujas), "aristas": sorted(n.aristas)} for nid, n in self.nodos.items()},
            "relaciones": [
                [a, b, d["fuerza"], d["ultimo_evento"], d["refuerzos"]] for (a, b), d in sorted(self.relaciones.items())
            ],
            "aristas_por_relacion": [
                [a, b, [[x, y] for x, y in sorted(es)]] for (a, b), es in sorted(self.aristas_por_relacion.items())
            ],
        }

    def cargar_dict(self, data):
        self._n_eventos = data.get("_n_eventos", 0)
        self.burbujas = {}
        for t, bd in data["burbujas"].items():
            b = Burbuja(t)
            b.peso = bd["peso"]
            b.nodos = set(bd["nodos"])
            b.ultimo_evento = bd.get("ultimo_evento", 0)
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
        self.relaciones = {}
        for fila in data.get("relaciones", []):
            a, b, fuerza, ultimo_evento = fila[:4]
            refuerzos = fila[4] if len(fila) > 4 else 1
            self.relaciones[tuple(sorted((a, b)))] = {
                "fuerza": fuerza,
                "ultimo_evento": ultimo_evento,
                "refuerzos": refuerzos,
            }
        self.aristas_por_relacion = {}
        for a, b, es in data.get("aristas_por_relacion", []):
            self.aristas_por_relacion[tuple(sorted((a, b)))] = {tuple(sorted((x, y))) for x, y in es}
        self.relaciones_por_termino = {}
        for (a, b) in self.relaciones:
            self.relaciones_por_termino.setdefault(a, set()).add(b)
            self.relaciones_por_termino.setdefault(b, set()).add(a)


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

    def fisionar_nodo(self, nid):
        resultado = super().fisionar_nodo(nid)
        if resultado is not None:
            self._registrar("fisionar_nodo", {"nid": nid})
        return resultado

    def fijar_peso(self, termino, peso):
        super().fijar_peso(termino, peso)
        self._registrar("fijar_peso", {"termino": termino, "peso": peso})

    def fijar_fuerza_relacion(self, a, b, fuerza):
        super().fijar_fuerza_relacion(a, b, fuerza)
        self._registrar("fijar_fuerza_relacion", {"a": a, "b": b, "fuerza": fuerza})

    def prune_relacion(self, a, b):
        super().prune_relacion(a, b)
        self._registrar("prune_relacion", {"a": a, "b": b})

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
        else:
            Nodo._seq = 0  # los ids del log son absolutos: el replay debe
            # regenerar n1, n2... aun con otras piscinas en el proceso

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
        elif metodo == "fisionar_nodo":
            Piscina.fisionar_nodo(self, argumentos["nid"])
        elif metodo == "fijar_peso":
            Piscina.fijar_peso(self, argumentos["termino"], argumentos["peso"])
        elif metodo == "fijar_fuerza_relacion":
            Piscina.fijar_fuerza_relacion(self, argumentos["a"], argumentos["b"], argumentos["fuerza"])
        elif metodo == "prune_relacion":
            Piscina.prune_relacion(self, argumentos["a"], argumentos["b"])
        else:
            raise ValueError(f"evento desconocido en el log: {metodo}")


class Caja:
    """Procesador transitorio, sin estado persistente. Recibe los
    terminos de UNA consulta, los clasifica contra la piscina, detecta
    co-ocurrencias, e informa los eventos resultantes. No guarda nada
    despues de retornar.

    Capacidad de caja = ventana de co-ocurrencia: el presupuesto de
    asociacion POR TERMINO (cuantos predecesores inmediatos ve cada
    termino). Es el parametro que decide cuantas asociaciones crea una
    consulta; se elige por el criterio del codo sobre la curva de
    asociaciones marginales (ver docstring del modulo).
    """

    def __init__(self, piscina, filtro_ontologico=None, ventana_coocurrencia=None):
        self.piscina = piscina
        self.filtro = filtro_ontologico or FILTRO_ONTOLOGICO_DEFAULT
        self.ventana = ventana_coocurrencia if ventana_coocurrencia is not None else VENTANA_COOCURRENCIA

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
            for vecino in terminos[max(0, i - self.ventana):i]:
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

    def __init__(self, filtro_ontologico=None, db_path=None, ventana_coocurrencia=None):
        self.piscina = PiscinaPersistente(db_path) if db_path else Piscina()
        self.caja = Caja(self.piscina, filtro_ontologico, ventana_coocurrencia)

    def normalizar_termino(self, termino):
        """Resuelve una forma superficial a su concepto canonico: alias
        declarados primero; si no, morfologia derivativa segura (solo
        canoniza si la raiz ya existe como burbuja)."""
        if termino in ALIASES_SINONIMOS:
            return ALIASES_SINONIMOS[termino]
        for raiz in _raices_derivativas(termino):
            if self.piscina.existe(raiz):
                return raiz
        return termino

    def declarar_sinonimo(self, forma, canon):
        """Registra un alias forma->canon en runtime (extiende
        ALIASES_SINONIMOS)."""
        ALIASES_SINONIMOS[forma] = canon

    def procesar_consulta(self, texto):
        """Entrada principal: una consulta humana completa (ej:
        'Que masa tiene el Sol?'). Tokeniza, normaliza a conceptos
        canonicos, filtra, procesa con una Caja transitoria."""
        terminos = _tokenizar(texto)
        terminos = [self.normalizar_termino(t) for t in terminos]
        eventos = self.caja.procesar_terminos(terminos)
        return {"terminos_procesados": terminos, "eventos": eventos}

    def declarar_relacion(self, a, b):
        """API de bajo nivel: declara relacion entre dos terminos ya
        dados (no texto crudo). Normaliza a conceptos canonicos antes
        de procesar. Util para el bridge MCP / tests."""
        a = self.normalizar_termino(a)
        b = self.normalizar_termino(b)
        return self.caja.procesar_terminos([a, b])

    def consultar(self, a, b):
        """Confianza de la relacion: 1.0 = observada (co-ocurrencia o
        arista explicita), 0.5^puentes = inferida por cierre transitivo,
        0.0 = sin relacion."""
        return self.piscina.relacion(a, b)

    def nivel(self, termino):
        return self.piscina.nivel_promocion(termino)

    def contexto_primado(self, termino, presupuesto=5):
        return self.piscina.contexto_primado(termino, presupuesto)

    def stats(self):
        return self.piscina.stats()

    def optimizar(self, max_membresias=None):
        return self.piscina.optimizar(max_membresias)