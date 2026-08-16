"""Tests del nucleo canonico de La Caja -- modelo multi-pertenencia +
arista estricta (fusion del single-membership abandonado con el prototipo
multi-pertenencia, 16/8/2026).

Cubren los comportamientos del modelo unico: filtro ontologico, nodo
unitario, fusion nuevo+nuevo, nodo compartido nuevo+existente (nunca
absorcion, nunca exilio), refuerzo de peso, ventana secuencial,
conectividad estricta por aristas explicitas (membresia compartida NO
conecta), navegacion multi-salto, cajas sin estado y optimizacion.
"""
from la_caja import LaCaja, Piscina, Caja


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


def test_optimizar_flags_fission_candidates_without_splitting():
    """Fision no implementada todavia -- optimizar() solo devuelve
    candidatos por umbral, sin modificar la estructura."""
    la = LaCaja()
    la.piscina.UMBRAL_FISION_PESO = 2
    la.procesar_consulta("gravedad")
    la.procesar_consulta("gravedad")
    la.procesar_consulta("gravedad")

    resultado = la.optimizar()
    nodo = next(iter(la.piscina.nodos_de("gravedad")))

    assert nodo in resultado["candidatos_fision"]
    assert nodo in la.piscina.nodos, "optimizar() no debe borrar ni dividir nodos todavia"