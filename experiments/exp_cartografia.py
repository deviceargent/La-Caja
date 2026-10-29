"""Pipeline de cartografia de punta a punta sobre el corpus fixture.

Uso:
    $env:PYTHONPATH="src"; python experiments/exp_cartografia.py

Produce (en experiments/results/):
    cartografia_demo.db   -- piscina persistente con el corpus fixture
                             (se recrea en cada corrida: reproducible)
    cartografia_mediciones.json   -- etapa A: mediciones estructurales
    cartografia_candidatos.json   -- etapa B: candidatos con evidencia
    cartografia_comparaciones.json -- etapa B: similitud estructural
    cartografia.html              -- visualizacion interactiva

Todo se genera desde el mecanismo real de construccion del grafo
(LaCaja + PiscinaPersistente): no hay grafo fabricado aparte. La capa
analitica es SOLO LECTURA sobre la piscina.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from la_caja import LaCaja
from la_caja.cartografia import medir, descubrir, comparar_subgrafos
from la_caja.cartografia.visualizar import exportar_html, exportar_gexf
from corpus_cartografia import CORPUS, PATRONES_ESPERADOS, ingestar


DIRECTORIO_RESULTADOS = os.path.join(os.path.dirname(__file__), "results")


def validar(medidas, candidatos, comparaciones):
    """Compara los patrones plantados del fixture contra lo medido.
    Devuelve una lista de (patron, ok, observacion)."""
    from la_caja.cartografia import grafo_conceptos
    import la_caja.cartografia as cart
    verdictos = []

    # 1. comunidades
    mod = medidas["global"]["modularidad"]
    n_com = len(medidas["comunidades"])
    ok = mod > 0 and n_com >= 2
    verdictos.append(("dos comunidades principales", ok,
                      f"modularidad={mod:.3f}, comunidades={n_com}"))

    return verdictos


def main():
    os.makedirs(DIRECTORIO_RESULTADOS, exist_ok=True)
    db = os.path.join(DIRECTORIO_RESULTADOS, "cartografia_demo.db")
    if os.path.exists(db):
        os.remove(db)

    print("1/5 ingesta del corpus fixture via LaCaja (PiscinaPersistente)")
    caja = LaCaja(db_path=db)
    eventos = ingestar(caja)
    n_eventos = sum(len(r["eventos"]) for r in eventos)
    print(f"    {len(CORPUS)} consultas -> {n_eventos} eventos")
    print(f"    stats: {caja.stats()}")

    print("2/5 etapa A: medicion estructural")
    medidas, estructuras = medir(caja.piscina)
    g = medidas["global"]
    print(f"    terminos={g['terminos']} relaciones_observadas={g['relaciones_observadas']} "
          f"componentes={g['n_componentes']} gigante={g['fraccion_componente_gigante']:.2f} "
          f"modularidad={g['modularidad']:.3f}")

    print("3/5 etapa B: descubrimiento de candidatos + comparacion estructural")
    candidatos, resumen = descubrir(caja.piscina)
    comparaciones = comparar_subgrafos(caja.piscina)
    print(f"    candidatos: {resumen}")
    print(f"    comparaciones entre comunidades: {len(comparaciones)}")

    print("4/5 escritura de reportes JSON + HTML interactivo + GEXF")
    with open(os.path.join(DIRECTORIO_RESULTADOS, "cartografia_mediciones.json"), "w", encoding="utf-8") as f:
        json.dump(medidas, f, ensure_ascii=False, indent=1)
    with open(os.path.join(DIRECTORIO_RESULTADOS, "cartografia_candidatos.json"), "w", encoding="utf-8") as f:
        json.dump({"capa": "candidatos", "resumen": resumen, "candidatos": candidatos},
                  f, ensure_ascii=False, indent=1)
    with open(os.path.join(DIRECTORIO_RESULTADOS, "cartografia_comparaciones.json"), "w", encoding="utf-8") as f:
        json.dump({"capa": "comparaciones", "comparaciones": comparaciones},
                  f, ensure_ascii=False, indent=1)
    html = exportar_html(caja.piscina,
                         os.path.join(DIRECTORIO_RESULTADOS, "cartografia.html"),
                         candidatos=candidatos + comparaciones)
    exportar_gexf(caja.piscina, os.path.join(DIRECTORIO_RESULTADOS, "cartografia.gexf"))
    print(f"    -> {html}")

    print("5/5 validacion contra los patrones plantados del fixture")
    from la_caja.cartografia import grafo_conceptos
    g_con = grafo_conceptos(caja.piscina)
    obs_t = [d["tipo"] for _, _, d in g_con.edges(data=True)]

    def relacion_observada_entre(a, b):
        clave = tuple(sorted((a, b)))
        return clave in caja.piscina.relaciones

    chequeos = [
        ("modularidad > 0 con >= 2 comunidades",
         medidas["global"]["modularidad"] > 0 and len(medidas["comunidades"]) >= 2,
         f"mod={medidas['global']['modularidad']:.3f}, comunidades={len(medidas['comunidades'])}"),
        ("puente entre dominios (arbol-grafo via consulta de cruce)",
         relacion_observada_entre("arbol", "grafo") or relacion_observada_entre("arbol", "ramifican"),
         "relaciones observadas que cruzan dominios"),
        ("ruido aislado (lluvias sin relacion con botanica)",
         not caja.consultar("lluvias", "arbol"),
         f"confianza(lluvias, arbol)={caja.consultar('lluvias', 'arbol')}"),
        ("'raiz' con multi-membresia",
         g_con.nodes["raiz"]["membresias"] > 1 if g_con.has_node("raiz") else False,
         f"membresias(raiz)={g_con.nodes['raiz']['membresias'] if g_con.has_node('raiz') else 'n/a'}"),
    ]
    for nombre, ok, obs in chequeos:
        print(f"    [{'OK ' if ok else 'NO '}] {nombre} -- {obs}")

    print("\nPatrones esperados documentados en corpus_cartografia.PATRONES_ESPERADOS.")
    print("Los candidatos son HIPOTESIS de examen: ninguna se escribio en el grafo vivo.")


if __name__ == "__main__":
    main()