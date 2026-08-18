"""Tests del nucleo canonico de La Caja -- modelo multi-pertenencia +
arista estricta (fusion del single-membership abandonado con el prototipo
multi-pertenencia, 16/8/2026).

Cubren los comportamientos del modelo unico: filtro ontologico, nodo
unitario, fusion nuevo+nuevo, nodo compartido nuevo+existente (nunca
absorcion, nunca exilio), refuerzo de peso, ventana secuencial,
conectividad estricta por aristas explicitas (membresia compartida NO
conecta), navegacion multi-salto, cajas sin estado y optimizacion.
"""
from la_caja import LaCaja, Piscina, Caja, Nodo, VENTANA_COOCURRENCIA
import sqlite3


def _reset_id_sequence():
    """Simula un proceso realmente nuevo: Nodo._seq es una variable de
    clase, en un proceso fresco arranca en 0."""
    Nodo._seq = 0


def test_brand_new_term_gets_own_unitary_node():
    la = LaCaja()
    la.procesar_consulta("gravedad")

    assert la.piscina.existe("gravedad")
    assert len(la.piscina.nodos_de("gravedad")) == 1


def test_two_new_terms_cooccurring_fuse_into_one_node():
    la = LaCaja()
    la.procesar_consulta("masa sol")

    nodo_masa = la.piscina.nodos_de("masa")
    nodo_sol = la.piscina.nodos_de("sol")

    assert nodo_masa == nodo_sol, "dos terminos nuevos co-ocurriendo deben compartir nodo"
    assert len(nodo_masa) == 1


def test_three_new_cooccurring_terms_all_gain_membership():
    """El caso que rompia el modelo single-membership (core.py viejo):
    con tres terminos nuevos co-ocurriendo, el tercero ya no queda
    relegado a una simple arista -- gana membresia real."""
    la = LaCaja()
    la.procesar_consulta("gravedad masa energia")

    assert len(la.piscina.nodos_de("energia")) == 3
    assert la.consultar("gravedad", "energia") == 1.0
    assert la.consultar("masa", "energia") == 1.0


def test_no_exile_term_participates_in_multiple_groups():
    la = LaCaja()
    la.procesar_consulta("gravedad")
    la.procesar_consulta("gravedad masa energia")

    nodos = la.piscina.nodos_de("gravedad")
    assert len(nodos) >= 2, f"nodos={sorted(nodos)}"


def test_new_plus_existing_shares_context_without_absorption_or_exile():
    """nuevo+existente: el nuevo conserva su unitario, no se absorbe en
    el nodo del existente, y ambos ganan un nodo compartido nuevo."""
    la = LaCaja()
    la.procesar_consulta("masa sol")
    la.declarar_relacion("luna", "sol")

    nodo_luna = la.piscina.nodos_de("luna")
    nodo_sol = la.piscina.nodos_de("sol")

    assert len(nodo_luna) == 2, "unitario propio + nodo compartido con sol"
    assert len(nodo_luna & nodo_sol) == 1, "comparten exactamente el nodo nuevo"
    assert len(nodo_luna - nodo_sol) == 1, "luna conserva su unitario (no absorbida)"
    assert len(nodo_sol - nodo_luna) == 1, "sol conserva su unitario (no exiliado)"


def test_term_accumulates_three_memberships_across_queries():
    la = LaCaja()
    la.procesar_consulta("sol")
    la.procesar_consulta("sol masa")
    la.procesar_consulta("sol luna")

    nodos = la.piscina.nodos_de("sol")
    assert len(nodos) == 3, f"nodos={sorted(nodos)}"
    assert la.consultar("sol", "masa") == 1.0
    assert la.consultar("sol", "luna") == 1.0


def test_repeated_term_reinforces_weight_without_creating_new_nodes():
    la = LaCaja()
    la.procesar_consulta("gravedad")
    nodos_antes = la.piscina.nodos_de("gravedad")

    la.procesar_consulta("gravedad")

    assert la.piscina.burbujas["gravedad"].peso == 2
    assert la.piscina.nodos_de("gravedad") == nodos_antes, "no debe crear nodos nuevos"


def test_ontological_filter_discards_function_words():
    la = LaCaja()
    la.procesar_consulta("¿Qué masa tiene el Sol?")

    assert la.piscina.existe("masa")
    assert la.piscina.existe("sol")
    for palabra_funcional in ("qué", "tiene", "el"):
        assert not la.piscina.existe(palabra_funcional)


def test_unrelated_terms_are_not_connected():
    la = LaCaja()
    la.procesar_consulta("gravedad")
    la.procesar_consulta("banana")

    assert la.consultar("gravedad", "banana") == 0


def test_cooccurrence_window_does_not_directly_connect_distant_terms():
    """Ventana secuencial (VENTANA_COOCURRENCIA=4): un termino a mas de
    4 posiciones de distancia en la misma consulta no comparte nodo con
    el otro."""
    la = LaCaja()
    la.procesar_consulta("primero ta tb tc td te ultimo")

    g_primero = la.piscina.nodos_de("primero")
    g_ultimo = la.piscina.nodos_de("ultimo")
    assert not (g_primero & g_ultimo)


def test_cross_query_shared_term_bridge_does_not_connect():
    """Hallazgo central: compartir un termino entre dos consultas
    separadas (via un hub) NO alcanza para conectar. Es estructuralmente
    el mismo caso que una cadena espuria -- se resuelve exigiendo arista
    explicita, no membresia compartida."""
    la = LaCaja()
    la.procesar_consulta("primero td")
    la.procesar_consulta("ultimo td")

    assert la.consultar("primero", "ultimo") == 0


def test_navigation_requires_explicit_edge_between_established_concepts():
    """Ruta multi-salto SOLO via aristas explicitas, creadas cuando dos
    conceptos YA ESTABLECIDOS co-ocurren -- nunca por compartir un
    termino."""
    la = LaCaja()
    la.procesar_consulta("rojo")
    la.procesar_consulta("verde")
    la.procesar_consulta("azul")
    assert la.consultar("rojo", "azul") == 0, "sin relacion observada deben estar aislados"

    la.declarar_relacion("rojo", "verde")
    la.declarar_relacion("verde", "azul")

    assert la.consultar("rojo", "verde") == 1.0, "la arista explicita es una observacion"
    assert la.consultar("verde", "azul") == 1.0
    assert la.consultar("rojo", "azul") == 0.25, "dos puentes cruzados = inferencia, jamas 1.0"


def test_relacion_distingue_observado_de_inferido():
    """El caso motor+piano: la asociacion abstracta es MEMORIA (1.0),
    pero el par nunca vinculado (cilindro-nota) es INFERENCIA por
    cierre transitivo (0.5) -- recuperable, jamas igual a un recuerdo."""
    la = LaCaja()
    la.procesar_consulta("motor cilindro bujia")
    la.procesar_consulta("piano escala nota")
    assert la.consultar("cilindro", "nota") == 0, "topicos aislados antes del cruce"

    la.procesar_consulta("motor del piano")

    assert la.consultar("motor", "piano") == 1.0, "el cruce honesto es una observacion"
    assert la.consultar("cilindro", "nota") == 0.5, "cilindro-nota cruza el puente observado: inferida"


def test_relacion_multi_salto_decrece_con_la_distancia():
    """Cada puente observado cruzado divide la confianza por 2."""
    la = LaCaja()
    for t in ["alfa", "beta", "gamma", "delta"]:
        la.procesar_consulta(t)
    la.declarar_relacion("alfa", "beta")
    la.declarar_relacion("beta", "gamma")
    la.declarar_relacion("gamma", "delta")

    assert la.consultar("alfa", "beta") == 1.0
    assert la.consultar("beta", "gamma") == 1.0
    assert la.consultar("alfa", "gamma") == 0.25
    assert la.consultar("alfa", "delta") == 0.125


def test_relacion_directa_por_membresia_es_observada():
    """La co-ocurrencia directa (membresia compartida) es tan observada
    como la arista explicita: confianza 1.0, sin inferencia."""
    la = LaCaja()
    la.procesar_consulta("masa energia")
    assert la.consultar("masa", "energia") == 1.0


def test_caja_holds_no_state_the_pool_does():
    """Las cajas son procesadores de transito, sin estado propio."""
    piscina = Piscina()
    caja_uno = Caja(piscina)
    caja_dos = Caja(piscina)

    caja_uno.procesar_terminos(["gravedad"])
    caja_dos.procesar_terminos(["gravedad"])

    assert piscina.burbujas["gravedad"].peso == 2, "el refuerzo vive en la piscina, no en la caja"


def test_fission_demotes_weak_memberships_to_precise_edges(tmp_path):
    """Un termino sobrecargado de membresias: optimizar() demote las
    mas debiles (menor peso combinado) partiendo el nodo compartido en
    unitarios + arista de par precisa. La relacion sigue navegable, pero
    la activacion conjunta (membresia) cede a la navegacion."""
    db_path = str(tmp_path / "piscina.db")
    _reset_id_sequence()
    la = LaCaja(db_path=db_path)
    la.procesar_consulta("masa del sol")
    la.procesar_consulta("masa de la tierra")
    la.procesar_consulta("masa del planeta")
    la.procesar_consulta("masa del cuerpo")
    la.procesar_consulta("masa del sol")
    la.procesar_consulta("masa del sol")

    antes = len(la.piscina.nodos_de("masa"))
    assert antes > 2, "masa debe tener multiples contextos de activacion"

    resultado = la.optimizar(max_membresias=2)
    despues = len(la.piscina.nodos_de("masa"))
    assert despues < antes
    assert despues <= 2
    assert len(resultado["fisionados"]) > 0

    # las relaciones demotadas siguen navegables por arista de par
    assert la.consultar("masa", "planeta") == 1.0
    assert la.consultar("masa", "tierra") == 1.0
    # pero ya no son activacion conjunta (membresia compartida)
    assert not la.piscina.comparten_nodo("masa", "planeta")


def test_fission_keeps_reinforced_memberships_as_activation():
    """La co-ocurrencia mas reforzada NO se demote: sigue como nodo
    compartido (activacion); solo las debiles se degradan a navegacion."""
    la = LaCaja()
    for q in ["masa del sol", "masa del sol", "masa de la tierra", "masa del planeta"]:
        la.procesar_consulta(q)
    la.optimizar(max_membresias=2)

    assert la.piscina.comparten_nodo("masa", "sol"), "el par reforzado conserva activacion conjunta"
    assert not la.piscina.comparten_nodo("masa", "planeta"), "el par debil se demote a navegacion"


def test_fission_survives_restart_byte_identical(tmp_path):
    """fisionar_nodo es un evento del log: tras reiniciar, el replay
    reconstruye el estado post-fision byte a byte."""
    db_path = str(tmp_path / "piscina.db")
    _reset_id_sequence()
    la1 = LaCaja(db_path=db_path)
    la1.procesar_consulta("masa del sol")
    la1.procesar_consulta("masa de la tierra")
    la1.procesar_consulta("masa del planeta")
    la1.procesar_consulta("masa del cuerpo")
    la1.procesar_consulta("masa del sol")
    la1.optimizar(max_membresias=2)
    estado = la1.piscina.a_dict()
    la1.piscina.db.close()

    _reset_id_sequence()
    la2 = LaCaja(db_path=db_path)
    assert la2.piscina.a_dict() == estado
    assert len(la2.piscina.nodos_de("masa")) <= 2


def test_replay_reconstructs_identical_state_after_restart(tmp_path):
    db_path = str(tmp_path / "piscina.db")

    _reset_id_sequence()
    la1 = LaCaja(db_path=db_path)
    la1.procesar_consulta("gravedad masa energia")
    la1.procesar_consulta("sol masa")
    la1.declarar_relacion("doom3", "idtech4")
    la1.declarar_relacion("idtech4", "netradiant")
    estado_original = la1.piscina.a_dict()
    la1.piscina.db.close()

    _reset_id_sequence()
    la2 = LaCaja(db_path=db_path)
    estado_reconstruido = la2.piscina.a_dict()

    assert estado_reconstruido == estado_original


def test_connectivity_and_weights_survive_restart(tmp_path):
    db_path = str(tmp_path / "piscina.db")

    _reset_id_sequence()
    la1 = LaCaja(db_path=db_path)
    la1.procesar_consulta("gravedad")
    la1.procesar_consulta("gravedad")
    la1.procesar_consulta("doom3")
    la1.procesar_consulta("idtech4")
    la1.procesar_consulta("netradiant")
    la1.declarar_relacion("doom3", "idtech4")
    la1.declarar_relacion("idtech4", "netradiant")
    la1.piscina.db.close()

    _reset_id_sequence()
    la2 = LaCaja(db_path=db_path)

    assert la2.piscina.burbujas["gravedad"].peso == 2
    assert la2.consultar("doom3", "netradiant") > 0, "la ruta inferida sobrevive al restart"
    assert la2.consultar("doom3", "idtech4") == 1.0, "la pareja observada se restaura desde el log"


def test_replay_determinista_con_piscina_previa_en_el_mismo_proceso(tmp_path):
    """Los ids del log son absolutos: reconstruir una piscina persistente
    no debe depender del contador Nodo._seq que hayan avanzado otras
    piscinas en el mismo proceso (sin _reset_id_sequence a proposito)."""
    la = LaCaja()
    la.procesar_consulta("basura calefactor")
    db_path = str(tmp_path / "piscina.db")

    la1 = LaCaja(db_path=db_path)
    la1.procesar_consulta("motor cilindro bujia")
    la1.procesar_consulta("piano escala nota")
    la1.procesar_consulta("motor del piano")
    la1.piscina.db.close()

    la2 = LaCaja(db_path=db_path)
    assert la2.consultar("motor", "piano") == 1.0, "la pareja observada se restaura desde el log"
    assert la2.consultar("cilindro", "nota") == 0.5, "la inferencia se reconstruye identica"


def test_snapshot_bounds_replay_to_events_after_it(tmp_path):
    db_path = str(tmp_path / "piscina.db")

    _reset_id_sequence()
    la1 = LaCaja(db_path=db_path)
    la1.procesar_consulta("gravedad masa energia")
    la1.piscina.snapshot()
    eventos_hasta_snapshot = la1.piscina.db.execute("SELECT COUNT(*) FROM eventos").fetchone()[0]

    la1.procesar_consulta("sol luna")
    estado_original = la1.piscina.a_dict()
    la1.piscina.db.close()

    verificacion = sqlite3.connect(db_path)
    ultimo_evento_snapshot = verificacion.execute(
        "SELECT ultimo_evento_id FROM snapshots ORDER BY id DESC LIMIT 1"
    ).fetchone()[0]
    verificacion.close()
    assert ultimo_evento_snapshot == eventos_hasta_snapshot, (
        "el snapshot debe apuntar exactamente al ultimo evento previo"
    )

    _reset_id_sequence()
    la2 = LaCaja(db_path=db_path)
    estado_reconstruido = la2.piscina.a_dict()

    assert estado_reconstruido == estado_original


def test_no_direct_bypass_of_piscina_internals(tmp_path):
    """Toda mutacion pasa por un metodo de Piscina -- Caja no toca
    piscina.burbujas directamente (ese bypass haria imposible el
    event-sourcing)."""
    db_path = str(tmp_path / "piscina.db")
    _reset_id_sequence()
    la = LaCaja(db_path=db_path)
    la.procesar_consulta("gravedad")

    metodos = {fila[0] for fila in la.piscina.db.execute("SELECT metodo FROM eventos").fetchall()}
    assert "crear_burbuja" in metodos
    assert metodos <= {"crear_burbuja", "reforzar", "crear_unitario", "crear_compartido", "fusionar", "arista_entre", "fisionar_nodo", "fijar_peso", "fijar_fuerza_relacion", "prune_relacion"}


def test_in_memory_piscina_without_db_path_works_unpersisted():
    """LaCaja sin db_path sigue funcionando en memoria pura -- la
    persistencia es opt-in, no obligatoria."""
    la = LaCaja()
    la.procesar_consulta("gravedad masa")
    assert la.consultar("gravedad", "masa") == 1.0


def _asociaciones(la, texto):
    evs = la.procesar_consulta(texto)["eventos"]
    return sum(1 for e in evs if e["tipo"] in ("fusion_nodo_unico", "nodo_compartido", "arista"))


def test_capacidad_ventana_respetada():
    """La ventana de co-ocurrencia ES la capacidad de la caja: a menor
    ventana, una consulta crea menos asociaciones."""
    texto = "primero segundo tercero cuarto quinto sexto septimo octavo noveno decimo onceavo doceavo"
    la_uno = LaCaja(ventana_coocurrencia=1)
    la_cuatro = LaCaja(ventana_coocurrencia=4)
    assert _asociaciones(la_cuatro, texto) > _asociaciones(la_uno, texto)


TEMAS_CORPUS = {
    "astronomia": ["sol", "luna", "planeta", "orbita", "masa", "estrella", "satelite", "cometa", "nebulosa", "galaxia"],
    "cocina": ["sarten", "horno", "receta", "harina", "fuego", "sal", "aceite", "levadura", "vapor", "azucar"],
    "fisica": ["gravedad", "energia", "fuerza", "particula", "campo", "velocidad", "carga", "onda", "nucleo", "foton"],
    "futbol": ["gol", "pelota", "arco", "delantero", "cancha", "tecnico", "arbitro", "defensa", "torneo", "equipo"],
    "musica": ["nota", "escala", "acorde", "ritmo", "melodia", "tono", "compas", "instrumento", "coro", "partitura"],
    "medicina": ["celula", "dolor", "tratamiento", "sintoma", "virus", "diagnostico", "pulmon", "dosis", "paciente", "clinica"],
}


def _generar_corpus(n_mensajes=40, semilla=7, largo=18, intrusiones=3, probabilidad_intrusion=0.8):
    import random
    rng = random.Random(semilla)
    temas = list(TEMAS_CORPUS)
    mensajes = []
    for _ in range(n_mensajes):
        tema = rng.choice(temas)
        msg = list(TEMAS_CORPUS[tema])
        rng.shuffle(msg)
        msg = msg[:largo]
        for _ in range(intrusiones):
            if rng.random() < probabilidad_intrusion:
                otro = rng.choice([t for t in temas if t != tema])
                msg.insert(rng.randrange(len(msg) + 1), rng.choice(TEMAS_CORPUS[otro]))
        mensajes.append(msg)
    return mensajes


def _pares_genuinos(mensajes):
    tema_por_termino = {t: tema for tema, ts in TEMAS_CORPUS.items() for t in ts}
    pares = set()
    for m in mensajes:
        for i in range(len(m)):
            for j in range(i + 1, len(m)):
                a, b = m[i], m[j]
                if tema_por_termino[a] == tema_por_termino[b]:
                    pares.add(frozenset((a, b)))
    return pares


def _genuinas_por_ventana(mensajes, genuinos, ventanas):
    curva = {}
    for w in ventanas:
        piscina = Piscina()
        caja = Caja(piscina, ventana_coocurrencia=w)
        capturadas = set()
        for m in mensajes:
            for ev in caja.procesar_terminos(m):
                if ev["tipo"] in ("fusion_nodo_unico", "nodo_compartido", "arista"):
                    par = frozenset(ev["terminos"])
                    if par in genuinos:
                        capturadas.add(par)
        curva[w] = len(capturadas)
    return curva


def test_capacidad_criterio_codo():
    """Criterio de capacidad de caja (codo de ganancia marginal): la
    capacidad es la menor ventana donde la ganancia marginal de
    asociaciones genuinas colapsa por debajo del 5% de la ganancia
    maxima. Sobre el corpus de validacion da exactamente la constante
    adoptada (VENTANA_COOCURRENCIA) -- el numero deja de ser
    arbitrario, es el resultado del principio. Ademas, en el codo el
    recall ya esta saturado (>= 0.95)."""
    import random
    random.seed(7)
    mensajes = _generar_corpus()
    genuinos = _pares_genuinos(mensajes)
    curva = _genuinas_por_ventana(mensajes, genuinos, range(1, 11))

    marginales = {}
    for w in range(2, 11):
        marginales[w] = curva[w] - curva[w - 1]
    max_marginal = max(marginales.values())

    codo = None
    for w in range(2, 11):
        if marginales[w] <= 0.05 * max_marginal:
            codo = w
            break
    assert codo is not None

    recall_en_codo = curva[codo] / len(genuinos)
    assert recall_en_codo >= 0.95, "en el codo el recall debe estar saturado"
    assert marginales[codo] <= 0.05 * max_marginal, "en el codo la ganancia marginal colapsa"
    assert codo == VENTANA_COOCURRENCIA, "la constante canonica debe coincidir con el criterio"


def test_decay_reduces_weight_of_unused_term():
    """Olvido por no-uso: un termino no reforzado por demasiados
    eventos pierde peso; el reforzado recientemente lo conserva."""
    la = LaCaja()
    la.piscina.UMBRAL_DECAY_EVENTOS = 5
    la.procesar_consulta("alfa")   # nace
    la.procesar_consulta("beta")   # nace
    la.procesar_consulta("beta")   # refuerza
    la.procesar_consulta("gamma")
    la.procesar_consulta("gamma")
    la.procesar_consulta("alfa")   # refuerza alfa recientemente
    la.procesar_consulta("delta")

    la.optimizar()

    assert la.piscina.burbujas["beta"].peso == 1, "beta sin uso reciente debe decaer"
    assert la.piscina.burbujas["alfa"].peso == 2, "alfa reforzado recientemente conserva peso"
    assert la.piscina.burbujas["gamma"].peso == 2, "gamma con uso reciente conserva peso"


def test_decay_never_drops_below_floor():
    """El piso de olvido: un termino de peso 1 (solo su rastro) nunca
    desaparece del indice -- el peso no baja de 1."""
    la = LaCaja()
    la.piscina.UMBRAL_DECAY_EVENTOS = 2
    la.procesar_consulta("x")
    la.procesar_consulta("y")
    la.procesar_consulta("y")
    la.procesar_consulta("z")
    la.procesar_consulta("z")
    la.procesar_consulta("z")

    la.optimizar()

    assert la.piscina.burbujas["x"].peso == 1
    assert la.piscina.burbujas["z"].peso == 3, "z usado al final no decae"


def test_decay_survives_restart_byte_identical(tmp_path):
    """decay se registra en el log (fijar_peso): tras reiniciar, el
    replay reconstruye el estado post-olvido byte a byte."""
    db_path = str(tmp_path / "piscina.db")
    _reset_id_sequence()
    la1 = LaCaja(db_path=db_path)
    la1.piscina.UMBRAL_DECAY_EVENTOS = 5
    la1.procesar_consulta("alfa")
    la1.procesar_consulta("beta")
    la1.procesar_consulta("beta")
    la1.procesar_consulta("gamma")
    la1.procesar_consulta("gamma")
    la1.procesar_consulta("alfa")
    la1.procesar_consulta("delta")
    la1.optimizar()
    estado = la1.piscina.a_dict()
    la1.piscina.db.close()

    _reset_id_sequence()
    la2 = LaCaja(db_path=db_path)
    assert la2.piscina.a_dict() == estado
    assert la2.piscina.burbujas["beta"].peso == 1


def test_sinonimo_canoniza_y_refuerza_mismo_concepto():
    """'masa del sol' y 'masa solar' convergen al mismo concepto: la
    piscina solo ve conceptos canonicos, y 'sol' refuerza una sola
    entidad -- 'solar' no fragmenta la memoria."""
    la = LaCaja()
    la.procesar_consulta("masa del sol")
    la.procesar_consulta("masa solar")

    assert "solar" not in la.piscina.burbujas, "la forma superficial no debe quedar en el indice"
    assert la.piscina.burbujas["sol"].peso == 2, "sol se refuerza por ambas formas"
    assert la.consultar("masa", "sol") == 1.0


def test_sinonimo_morfologico_seguro():
    """Morfologia derivativa: 'lunar' se canoniza a 'luna' (raiz con
    vocal restaurada) SOLO porque la raiz ya existe. No inventa."""
    la = LaCaja()
    la.procesar_consulta("luna")
    la.procesar_consulta("masa lunar")

    assert "lunar" not in la.piscina.burbujas
    assert la.piscina.burbujas["luna"].peso == 2
    assert la.consultar("masa", "luna") == 1.0


def test_sinonimo_no_inventa_si_raiz_no_existe():
    """La morfologia NO fabrica conceptos: si la raiz no existe, la
    forma nace normal -- 'musical' sin 'musica' previa queda como
    burbuja propia. (Los alias, en cambio, son identidad declarada y
    aplican incondicionalmente.)"""
    la = LaCaja()
    la.procesar_consulta("nota musical")

    assert "musical" in la.piscina.burbujas
    assert "musica" not in la.piscina.burbujas


def test_sinonimo_declarable_en_runtime():
    """Los alias son extensibles en runtime via declarar_sinonimo."""
    la = LaCaja()
    la.declarar_sinonimo("vela", "bujia")
    la.procesar_consulta("masa del sol")
    la.procesar_consulta("la vela")

    assert "vela" not in la.piscina.burbujas
    assert "bujia" in la.piscina.burbujas


def test_sinonimo_en_declarar_relacion():
    """declarar_relacion normaliza a conceptos canonicos antes de
    procesar: 'solar' se resuelve a 'sol'."""
    la = LaCaja()
    la.procesar_consulta("sol")
    la.declarar_relacion("solar", "masa")

    assert "solar" not in la.piscina.burbujas
    assert la.consultar("masa", "sol") == 1.0


def test_nivel_promocion_deriva_del_peso():
    """La jerarquia es una funcion derivada del peso, sin estado
    propio: promociona al reforzar y desciende con el olvido."""
    la = LaCaja()
    assert la.nivel("gravedad") == 0
    la.procesar_consulta("gravedad")
    assert la.nivel("gravedad") == 1
    la.procesar_consulta("gravedad")
    la.procesar_consulta("gravedad")
    assert la.nivel("gravedad") == 2


def test_nivel_desciende_con_decay():
    """La promocion es bidireccional: el olvido des-promueve."""
    la = LaCaja()
    la.piscina.UMBRAL_DECAY_EVENTOS = 2
    for _ in range(3):
        la.procesar_consulta("gravedad")
    assert la.nivel("gravedad") == 2
    for q in ["alfa", "beta", "gamma", "delta", "epsilon"]:
        la.procesar_consulta(q)
    la.optimizar()

    assert la.piscina.burbujas["gravedad"].peso == 2
    assert la.nivel("gravedad") == 1, "el olvido baja de nivel al termino"


def test_contexto_primado_ordena_por_nivel():
    """La vista de primado ordena el vecindario de activacion por nivel
    (los mas reforzados primero) y respeta el presupuesto."""
    la = LaCaja()
    la.procesar_consulta("masa energia fuerza")
    la.procesar_consulta("masa energia")
    la.procesar_consulta("masa energia")
    la.procesar_consulta("masa fuerza")

    primado = la.contexto_primado("masa", presupuesto=5)
    assert primado and primado[0] == "energia", "el co-miembro mas reforzado encabeza el primado"
    assert len(primado) <= 5
    assert set(primado) <= {"energia", "fuerza"}


def test_nivel_es_ortogonal_a_la_navegacion():
    """La jerarquia NO altera la conectividad: un termino que sube de
    nivel no gana ni pierde navegacion por ello."""
    la = LaCaja()
    la.procesar_consulta("doom3")
    la.procesar_consulta("idtech4")
    la.declarar_relacion("doom3", "idtech4")
    for _ in range(5):
        la.procesar_consulta("gravedad")
    la.procesar_consulta("otro")

    assert la.nivel("gravedad") > la.nivel("doom3")
    assert la.consultar("doom3", "idtech4") == 1.0, "el nivel no destruye navegacion real"
    assert la.consultar("gravedad", "otro") == 0, "el nivel no fabrica navegacion"


def test_jerarquia_no_muta_estado(tmp_path):
    """Leer la jerarquia y el primado no genera eventos ni cambia el
    estado: es puramente derivado (seguro para el event-sourcing)."""
    db_path = str(tmp_path / "piscina.db")
    _reset_id_sequence()
    la = LaCaja(db_path=db_path)
    la.procesar_consulta("masa energia")
    antes = la.piscina.a_dict()

    la.nivel("masa")
    la.contexto_primado("masa")

    assert la.piscina.a_dict() == antes


# ----------------------------------------------------------------------
# Iteracion 2: relaciones con refuerzo y olvido (poda selectiva)
# ----------------------------------------------------------------------

def test_relacion_se_refuerza_con_cada_co_ocurrencia():
    """Cada co-ocurrencia observada REFUERZA la relacion (no solo la
    registra): la fuerza es el contador de refuerzos."""
    la = LaCaja()
    la.procesar_consulta("alfa")
    la.procesar_consulta("beta")
    la.declarar_relacion("alfa", "beta")
    la.declarar_relacion("alfa", "beta")
    la.declarar_relacion("alfa", "beta")

    assert la.piscina.relaciones[("alfa", "beta")]["fuerza"] == 3
    assert la.consultar("alfa", "beta") == 1.0


def test_relacion_debil_se_olvida_y_poda_sus_aristas():
    """Una relacion de fuerza 1 (co-ocurrencia incidental, nunca
    reforzada) se OLVIDA al consolidar: desaparece de relaciones y sus
    aristas de navegacion se podan con exactitud."""
    la = LaCaja()
    la.piscina.UMBRAL_DECAY_RELACION = 5
    la.procesar_consulta("alfa")
    la.procesar_consulta("beta")
    la.declarar_relacion("alfa", "beta")
    for _ in range(18):
        la.procesar_consulta("gamma")

    la.optimizar()

    assert ("alfa", "beta") not in la.piscina.relaciones
    assert la.consultar("alfa", "beta") == 0, "sin relacion ni arista: aislados otra vez"


def test_relacion_reforzada_sobrevive_el_olvido():
    """El historial amortigua el olvido: una relacion reforzada 2 veces
    (gracia 3^2=45) sobrevive la pasada; la incidental (refuerzos 1,
    gracia 15) muere."""
    la = LaCaja()
    la.piscina.UMBRAL_DECAY_RELACION = 5
    la.procesar_consulta("alfa")
    la.procesar_consulta("beta")
    la.procesar_consulta("zeta")
    la.procesar_consulta("eta")
    la.declarar_relacion("alfa", "beta")
    la.declarar_relacion("alfa", "beta")  # refuerzos 2
    la.declarar_relacion("zeta", "eta")   # refuerzos 1
    for _ in range(20):
        la.procesar_consulta("gamma")

    la.optimizar()

    assert ("alfa", "beta") in la.piscina.relaciones, "la reforzada sobrevive"
    assert la.piscina.relaciones[("alfa", "beta")]["fuerza"] == 2, "gracia 3^2: ni siquiera decae"
    assert ("zeta", "eta") not in la.piscina.relaciones, "la incidental muere"


def test_relacion_reforzada_aguanta_vacios_por_historial():
    """Propiedad del olvido de repeticion espaciada: una relacion vista
    una sola vez y otra reforzada 4 veces, ambas con vacio de no-uso --
    la reforzada (gracia 3^4=405) aguanta, la incidental (gracia 15) se
    poda."""
    la = LaCaja()
    la.piscina.UMBRAL_DECAY_RELACION = 5
    la.procesar_consulta("alfa")
    la.procesar_consulta("beta")
    for _ in range(4):
        la.declarar_relacion("alfa", "beta")  # refuerzos 4
    la.procesar_consulta("zeta")
    la.procesar_consulta("eta")
    la.declarar_relacion("zeta", "eta")       # refuerzos 1
    for _ in range(18):
        la.procesar_consulta("gamma")

    la.optimizar()

    assert la.piscina.relaciones[("alfa", "beta")]["fuerza"] == 4, "el historial aguanta el vacio"
    assert ("zeta", "eta") not in la.piscina.relaciones, "la incidental muere"


def test_olvido_de_relacion_replay_byte_identical(tmp_path):
    """La poda de relaciones se registra en el log (fijar_fuerza_relacion
    + prune_relacion): tras reiniciar, el replay reconstruye el olvido
    byte a byte."""
    db_path = str(tmp_path / "piscina.db")
    _reset_id_sequence()
    la1 = LaCaja(db_path=db_path)
    la1.piscina.UMBRAL_DECAY_RELACION = 5
    la1.procesar_consulta("alfa")
    la1.procesar_consulta("beta")
    la1.declarar_relacion("alfa", "beta")
    for _ in range(18):
        la1.procesar_consulta("gamma")
    la1.optimizar()
    estado = la1.piscina.a_dict()
    la1.piscina.db.close()

    _reset_id_sequence()
    la2 = LaCaja(db_path=db_path)
    assert la2.piscina.a_dict() == estado
    assert ("alfa", "beta") not in la2.piscina.relaciones


def test_primado_prefiere_relaciones_observadas():
    """La vista de primado resucita por lo OBSERVADO: una relacion
    reforzada encabeza sobre una co-membresia de activacion."""
    la = LaCaja()
    la.procesar_consulta("masa")
    la.procesar_consulta("energia")
    la.procesar_consulta("masa energia")  # establecidos -> relacion
    la.procesar_consulta("masa energia")  # refuerza
    la.procesar_consulta("masa energia")  # refuerza
    la.procesar_consulta("masa fuerza")   # fuerza nace junto a masa (membresia)
    la.procesar_consulta("masa fuerza")   # refuerza membresia, sin relacion

    primado = la.contexto_primado("masa", presupuesto=5)
    assert primado[0] == "energia", "la relacion observada reforzada encabeza"
    assert "energia" in primado and "fuerza" in primado