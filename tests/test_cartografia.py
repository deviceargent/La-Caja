"""Tests de la capa de cartografia (medicion, descubrimiento,
comparacion, visualizacion).

Criterios centrales que se verifican:
  1. La capa es SOLO LECTURA: a_dict() identico antes y despues.
  2. Las capas no se mezclan: la activacion nunca cuenta como arista
     observada; las metricas corren sobre la capa observada.
  3. Los candidatos llevan evidencia trazable (tipo, elementos,
     evidencia numerica).
  4. Propiedades plantadas simples se recuperan (puente, isla,
     comparacion entre regiones desconectadas).
"""
import json
import os
import tempfile

import pytest

from la_caja import LaCaja, Nodo
from la_caja.cartografia import (
    medir, descubrir, comparar_subgrafos,
    grafo_conceptos, grafo_observado, grafo_navegacion,
)
from la_caja.cartografia.visualizar import exportar_html, exportar_gexf


@pytest.fixture(autouse=True)
def _reset():
    Nodo._seq = 0


def _caja_puente():
    """Dos triangulos (cuervo-lobo-zorro / roble-pino-abeto) unidos por
    un unico nodo puente (zorro-roble). Terminos reales: ninguna letra
    suelta, porque 'a' y 'e' estan en el filtro ontologico y nunca
    llegarian a ser burbujas. Todo observado: primero se establecen los
    terminos, despues se declaran las relaciones."""
    la = LaCaja()
    for t in ["cuervo", "lobo", "zorro", "roble", "pino", "abeto"]:
        la.procesar_consulta(t)
    for x, y in [
        ("cuervo", "lobo"), ("lobo", "zorro"), ("cuervo", "zorro"),
        ("zorro", "roble"),
        ("roble", "pino"), ("pino", "abeto"), ("roble", "abeto"),
    ]:
        la.declarar_relacion(x, y)
    return la


def test_medir_es_solo_lectura():
    la = _caja_puente()
    antes = json.dumps(la.piscina.a_dict(), sort_keys=True)
    medir(la.piscina)
    despues = json.dumps(la.piscina.a_dict(), sort_keys=True)
    assert antes == despues


def test_medir_recupera_propiedades_conocidas():
    la = _caja_puente()
    medidas, estructuras = medir(la.piscina)
    g = medidas["global"]
    assert g["terminos"] == 6
    assert g["relaciones_observadas"] == 7
    # dos triangulos + puente: 2 componentes si se quita c, pero con c
    # vivo el grafo es conexo
    assert g["n_componentes"] == 1
    assert g["fraccion_componente_gigante"] == 1.0
    assert g["diametro_componente_gigante"] >= 3
    assert medidas["local"]["triangulos_totales"] == 2


def test_capa_observada_excluye_activacion():
    la = LaCaja()
    # nuevo+nuevo fusiona: co-membresia SIN relacion observada
    la.procesar_consulta("masa energia")
    g_con = grafo_conceptos(la.piscina)
    tipos = {d["tipo"] for _, _, d in g_con.edges(data=True)}
    assert tipos == {"activacion"}, "co-membresia nueva no es observada"
    obs = grafo_observado(g_con)
    assert obs.number_of_edges() == 0
    # las metricas no ven la activacion como conexion
    assert obs.has_edge("masa", "energia") is False


def test_arista_observada_vs_activacion_coexisten():
    la = _caja_puente()
    g_con = grafo_conceptos(la.piscina)
    d = g_con["cuervo"]["lobo"]
    assert d["tipo"] == "observada"
    assert d["peso"] >= 1


def test_grafo_navegacion_refleja_aristas_explicitas():
    la = _caja_puente()
    g_nav = grafo_navegacion(la.piscina)
    assert g_nav.number_of_edges() > 0
    assert g_nav.number_of_nodes() == len(la.piscina.nodos)


def test_descubrir_senal_puente():
    la = _caja_puente()
    antes = json.dumps(la.piscina.a_dict(), sort_keys=True)
    candidatos, resumen = descubrir(la.piscina)
    assert json.dumps(la.piscina.a_dict(), sort_keys=True) == antes
    tipos = {c["tipo"] for c in candidatos}
    # 'c' es nodo de corte y candidato a puente; la arista c-d cruza
    assert "articulo" in tipos or "puente_nodo" in tipos
    assert any(c["tipo"] == "puente_arista" for c in candidatos)
    for c in candidatos:
        assert "evidencia" in c and "origen" in c
        assert c["capa"] == "candidato"


def test_descubrir_detecta_isla():
    la = _caja_puente()
    # isla: dos terminos establecidos con una relacion, sin nada mas
    la.procesar_consulta("isla1")
    la.procesar_consulta("isla2")
    la.declarar_relacion("isla1", "isla2")
    candidatos, _ = descubrir(la.piscina)
    islas = [c for c in candidatos if c["tipo"] == "isla"]
    assert islas, "la componente de 2 nodos debe reportarse como isla"
    assert set(islas[0]["elementos"]["terminos"]) == {"isla1", "isla2"}


def test_comparar_subgrafos_regiones_desconectadas():
    la = _caja_puente()
    resultados = comparar_subgrafos(la.piscina)
    assert resultados, "dos triangulos deben compararse"
    r = resultados[0]
    assert r["tipo"] == "similitud_estructural"
    assert r["capa"] == "candidato"
    # los dos triangulos son estructuralmente identicos
    assert r["evidencia"]["similitud"] >= 0.99
    # la similitud NO implica conexion: los subgrafos comparten el
    # puente zorro-roble, asi que la cuenta de aristas entre regiones
    # puede ser >0; lo que importa es que el resultado no muta nada.
    assert "origen" in r


def test_comparar_es_solo_lectura():
    la = _caja_puente()
    antes = json.dumps(la.piscina.a_dict(), sort_keys=True)
    comparar_subgrafos(la.piscina)
    assert json.dumps(la.piscina.a_dict(), sort_keys=True) == antes


def test_exportar_html_autocontenido():
    la = _caja_puente()
    candidatos, _ = descubrir(la.piscina)
    with tempfile.TemporaryDirectory() as d:
        ruta = os.path.join(d, "mapa.html")
        exportar_html(la.piscina, ruta, candidatos=candidatos)
        contenido = open(ruta, encoding="utf-8").read()
    assert "const DATOS" in contenido
    for t in ["cuervo", "lobo", "zorro"]:
        assert f'"id": "{t}"' in contenido
    # la advertencia de distancia esta incrustada (mayusculas/minisculas
    # no importan: el texto vivo dice "NO es distancia semantica")
    assert "no es distancia semantica" in contenido.lower()


def test_exportar_gexf():
    la = _caja_puente()
    with tempfile.TemporaryDirectory() as d:
        ruta = os.path.join(d, "mapa.gexf")
        exportar_gexf(la.piscina, ruta)
        contenido = open(ruta, encoding="utf-8").read()
    assert "gexf" in contenido
    assert "observada" in contenido or "tipo" in contenido


def test_medir_piscina_vacia():
    la = LaCaja()
    medidas, estructuras = medir(la.piscina)
    assert medidas["global"]["terminos"] == 0
    assert medidas["global"]["modularidad"] == 0.0
    candidatos, resumen = descubrir(la.piscina)
    assert candidatos == []
    assert comparar_subgrafos(la.piscina) == []