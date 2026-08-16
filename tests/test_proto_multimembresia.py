"""Tests for the multi-membership + strict-edge prototype
(la_caja.proto_multimembresia), formalizing the checks originally
written as a standalone script (main()/_check) into pytest functions.

This module is a PARALLEL, unmerged candidate model -- it does not
replace core.py's single-membership model, which remains the current
tested reference in test_core.py. Whether/how to merge the two is an
open decision recorded in the MCP deliberation log, not made here.
"""
from la_caja.proto_multimembresia import LaCaja


def test_no_exile_term_participates_in_multiple_groups():
    la = LaCaja()
    la.procesar_consulta("gravedad")
    la.procesar_consulta("gravedad masa energia")

    grupos = la.piscina.grupos_de("gravedad")
    assert len(grupos) >= 2, f"grupos={sorted(grupos)}"


def test_three_new_cooccurring_terms_all_gain_membership_not_just_two():
    """El caso que rompia el modelo de un-solo-nodo (core.py): con tres
    terminos nuevos co-ocurriendo, el tercero ya no queda relegado a
    una simple arista -- gana membresia real (multiple grupos)."""
    la = LaCaja()
    la.procesar_consulta("gravedad masa energia")

    assert len(la.piscina.grupos_de("energia")) == 3
    assert la.consultar("gravedad", "energia") is True
    assert la.consultar("masa", "energia") is True


def test_term_accumulates_three_group_memberships_across_queries():
    la = LaCaja()
    la.procesar_consulta("sol")
    la.procesar_consulta("sol masa")
    la.procesar_consulta("sol luna")

    grupos = la.piscina.grupos_de("sol")
    assert len(grupos) == 3, f"grupos={sorted(grupos)}"
    assert la.consultar("sol", "masa") is True
    assert la.consultar("sol", "luna") is True


def test_cross_query_shared_term_bridge_does_not_connect():
    """El hallazgo central de esta ronda: compartir un termino entre
    dos consultas separadas (via un hub) NO debe alcanzar para
    conectar -- es estructuralmente el mismo caso que una cadena
    espuria, y se resuelve exigiendo arista explicita, no membresia
    compartida."""
    la = LaCaja()
    la.procesar_consulta("primero td")
    la.procesar_consulta("ultimo td")

    assert la.consultar("primero", "ultimo") is False


def test_cooccurrence_window_within_one_query_still_holds():
    la = LaCaja()
    la.procesar_consulta("primero ta tb tc td te ultimo")

    g_primero = la.piscina.grupos_de("primero")
    g_ultimo = la.piscina.grupos_de("ultimo")
    assert not (g_primero & g_ultimo)
    assert la.consultar("primero", "ultimo") is False


def test_navigation_requires_explicit_edge_between_established_concepts():
    """Ruta multi-salto SOLO via aristas explicitas, creadas cuando
    dos conceptos YA EXISTENTES (declarados antes) co-ocurren -- nunca
    por el simple hecho de compartir un termino en algun grupo."""
    la = LaCaja()
    la.procesar_consulta("doom3")
    la.procesar_consulta("idtech4")
    la.procesar_consulta("netradiant")
    assert la.consultar("doom3", "netradiant") is False, "sin relacion observada, deben estar aislados"

    la.declarar_relacion("doom3", "idtech4")
    la.declarar_relacion("idtech4", "netradiant")

    assert la.consultar("doom3", "idtech4") is True
    assert la.consultar("idtech4", "netradiant") is True
    assert la.consultar("doom3", "netradiant") is True, "ruta multi-salto por aristas observadas"


def test_unrelated_terms_do_not_connect():
    la = LaCaja()
    la.procesar_consulta("gravedad")
    la.procesar_consulta("banana")

    assert la.consultar("gravedad", "banana") is False


def test_repeated_term_reinforces_weight_without_duplicating_groups():
    la = LaCaja()
    la.procesar_consulta("gravedad")
    la.procesar_consulta("gravedad")

    assert la.piscina.burbujas["gravedad"].peso == 2
    assert la.stats()["grupos"] == 1


def test_ontological_filter_discards_function_words():
    la = LaCaja()
    la.procesar_consulta("¿Qué masa tiene el Sol?")

    for palabra_funcional in ("qué", "tiene", "el"):
        assert not la.piscina.existe(palabra_funcional)
    assert la.piscina.existe("masa")
    assert la.piscina.existe("sol")


def test_caja_holds_no_state_the_pool_does():
    la = LaCaja()
    la.caja.procesar_terminos(["gravedad"])
    la.caja.procesar_terminos(["gravedad"])

    assert la.piscina.burbujas["gravedad"].peso == 2
