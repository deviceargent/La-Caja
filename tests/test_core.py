"""Tests for the bubble-node model (core.py), replacing the earlier
SuperIndex/Box/Node-era suite. Exercises the mechanism as described in
core.py's own docstring: ontological filter, unitary node creation,
new+new fusion, new+existing edge connection (never absorption), weight
reinforcement on repetition, sequential co-occurrence window, and
transitive connectivity via BFS over the node graph.
"""
from la_caja import LaCaja, Piscina, Caja, Nodo, Burbuja


def test_brand_new_term_gets_its_own_unitary_node():
    la = LaCaja()
    la.procesar_consulta("gravedad")

    assert la.piscina.existe("gravedad")
    nodo = la.piscina.nodo_de("gravedad")
    assert list(nodo.burbujas.keys()) == ["gravedad"]


def test_two_new_terms_co_occurring_fuse_into_one_node():
    la = LaCaja()
    la.procesar_consulta("masa sol")

    nodo_masa = la.piscina.nodo_de("masa")
    nodo_sol = la.piscina.nodo_de("sol")

    assert nodo_masa is not None
    assert nodo_masa.id == nodo_sol.id
    assert set(nodo_masa.burbujas.keys()) == {"masa", "sol"}


def test_new_term_plus_existing_term_connects_by_edge_not_absorption():
    la = LaCaja()
    la.procesar_consulta("masa sol")
    nodo_sol_id = la.piscina.nodo_de("sol").id

    # "luna" es un termino nuevo en esta llamada; "sol" ya existe.
    la.declarar_relacion("luna", "sol")

    nodo_luna = la.piscina.nodo_de("luna")
    nodo_sol = la.piscina.nodo_de("sol")

    assert nodo_luna.id != nodo_sol.id, "el termino nuevo no debe absorberse en el nodo existente"
    assert nodo_sol.id in nodo_luna.conexiones
    assert nodo_luna.id in nodo_sol.conexiones
    assert nodo_sol.id == nodo_sol_id, "el nodo existente no debe reemplazarse"


def test_repeated_term_reinforces_weight_without_creating_a_new_node():
    la = LaCaja()
    la.procesar_consulta("gravedad")
    nodo_id_antes = la.piscina.nodo_de("gravedad").id

    la.procesar_consulta("gravedad")

    nodo = la.piscina.nodo_de("gravedad")
    assert nodo.id == nodo_id_antes, "un termino repetido no debe crear un nodo nuevo"
    assert nodo.burbujas["gravedad"].peso == 2


def test_ontological_filter_discards_function_words():
    la = LaCaja()
    la.procesar_consulta("¿Qué masa tiene el Sol?")

    assert la.piscina.existe("masa")
    assert la.piscina.existe("sol")
    for palabra_funcional in ("qué", "tiene", "el"):
        assert not la.piscina.existe(palabra_funcional)


def test_transitive_connectivity_resolves_via_bfs_over_node_graph():
    la = LaCaja()
    la.declarar_relacion("doom3", "idtech4")
    la.declarar_relacion("idtech4", "netradiant")

    conectado, metodo = la.consultar("doom3", "netradiant")

    assert conectado is True
    assert metodo == "grafo_de_nodos"


def test_unrelated_terms_are_not_connected():
    la = LaCaja()
    la.procesar_consulta("gravedad")
    la.procesar_consulta("banana")

    conectado, _ = la.consultar("gravedad", "banana")
    assert conectado is False


def test_cooccurrence_window_does_not_connect_terms_outside_the_window():
    """Regresion del bugfix de escala (02/8/2026): comparacion todos-
    contra-todos (O(n^2)) reemplazada por ventana secuencial. Con
    VENTANA_COOCURRENCIA=4, un termino a mas de 4 posiciones de
    distancia en la misma consulta no debe conectarse directamente."""
    la = LaCaja()
    terminos_relleno = ["ta", "tb", "tc", "td", "te"]  # 5 > ventana (4)
    texto = "primero " + " ".join(terminos_relleno) + " ultimo"
    la.procesar_consulta(texto)

    nodo_primero = la.piscina.nodo_de("primero")
    nodo_ultimo = la.piscina.nodo_de("ultimo")

    assert nodo_primero is not None
    assert nodo_ultimo is not None
    assert nodo_primero.id != nodo_ultimo.id
    assert nodo_ultimo.id not in nodo_primero.conexiones


def test_caja_holds_no_state_between_calls():
    """Las cajas son procesadores de transito, sin estado propio --
    dos instancias sobre la misma piscina no deben interferir ni
    acumular estado propio."""
    piscina = Piscina()
    caja_uno = Caja(piscina)
    caja_dos = Caja(piscina)

    caja_uno.procesar_terminos(["gravedad"])
    caja_dos.procesar_terminos(["gravedad"])

    nodo = piscina.nodo_de("gravedad")
    assert nodo.burbujas["gravedad"].peso == 2, "el refuerzo debe verse en la piscina, no en la caja"


def test_optimizar_flags_fission_candidates_without_splitting():
    """Fision no esta implementada todavia -- optimizar() solo debe
    devolver candidatos por umbral, sin modificar la estructura."""
    la = LaCaja()
    la.piscina.UMBRAL_FISION_PESO = 2
    la.procesar_consulta("gravedad")
    la.procesar_consulta("gravedad")
    la.procesar_consulta("gravedad")

    resultado = la.optimizar()
    nodo = la.piscina.nodo_de("gravedad")

    assert nodo.id in resultado["candidatos_fision"]
    assert nodo.id in la.piscina.nodos, "optimizar() no debe borrar ni dividir nodos todavia"
