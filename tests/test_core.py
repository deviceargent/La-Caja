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
    assert la.consultar("gravedad", "energia") is True
    assert la.consultar("masa", "energia") is True


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
    assert la.consultar("sol", "masa") is True
    assert la.consultar("sol", "luna") is True


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

    assert la.consultar("gravedad", "banana") is False


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

    assert la.consultar("primero", "ultimo") is False


def test_navigation_requires_explicit_edge_between_established_concepts():
    """Ruta multi-salto SOLO via aristas explicitas, creadas cuando dos
    conceptos YA ESTABLECIDOS co-ocurren -- nunca por compartir un
    termino."""
    la = LaCaja()
    la.procesar_consulta("doom3")
    la.procesar_consulta("idtech4")
    la.procesar_consulta("netradiant")
    assert la.consultar("doom3", "netradiant") is False, "sin relacion observada deben estar aislados"

    la.declarar_relacion("doom3", "idtech4")
    la.declarar_relacion("idtech4", "netradiant")

    assert la.consultar("doom3", "idtech4") is True
    assert la.consultar("idtech4", "netradiant") is True
    assert la.consultar("doom3", "netradiant") is True, "ruta multi-salto por aristas observadas"


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
    assert la.consultar("masa", "planeta") is True
    assert la.consultar("masa", "tierra") is True
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
    assert la2.consultar("doom3", "netradiant") is True


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
    assert metodos <= {"crear_burbuja", "reforzar", "crear_unitario", "crear_compartido", "fusionar", "arista_entre", "fisionar_nodo", "fijar_peso"}


def test_in_memory_piscina_without_db_path_works_unpersisted():
    """LaCaja sin db_path sigue funcionando en memoria pura -- la
    persistencia es opt-in, no obligatoria."""
    la = LaCaja()
    la.procesar_consulta("gravedad masa")
    assert la.consultar("gravedad", "masa") is True


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