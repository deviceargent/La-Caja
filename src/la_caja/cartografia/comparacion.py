"""Etapa B (parte 2) -- comparacion estructural entre subgrafos.

Compara regiones del grafo (comunidades o componentes) ENTRE SI aunque
no exista ninguna arista entre ellas y aunque usen vocabularios
distintos. La comparacion es ESTRUCTURAL: parte de mediciones que no
requieren interpretacion semantica.

Que se compara (firma estructural de cada subgrafo):
  - tamano (nodos, aristas);
  - densidad;
  - distribucion de grados (histograma normalizado);
  - clustering medio;
  - diametro aproximado del subgrafo (si es conexo).

Similitud:
  - dist_grados  : distancia de Bhattacharyya entre histogramas
                   normalizados de grado (0 = identicos).
  - dist_forma   : diferencia normalizada en densidad y clustering.
  - similitud    : 1 - promedio de las distancias (descriptivo, no es
                   una relacion).

Salida: lista de pares candidatos con su evidencia. NUNCA crea aristas
ni modifica la piscina: la similitud estructural es un hallazgo a
investigar, no un vinculo (requisito 5 de la directiva).
"""
from __future__ import annotations

import math

import networkx as nx

from .medir import grafo_conceptos, grafo_observado, _comunidades


def _firma(sub):
    """Firma estructural de un subgrafo observado (dict serializable)."""
    n = sub.number_of_nodes()
    m = sub.number_of_edges()
    grados = [d for _, d in sub.degree()]
    max_g = max(grados) if grados else 0
    hist = [0] * (max_g + 1)
    for g in grados:
        hist[g] += 1
    total = sum(hist) or 1
    hist_norm = [h / total for h in hist]
    conexo = nx.is_connected(sub) if n else False
    diametro = nx.diameter(sub) if conexo and n > 1 else None
    return {
        "nodos": n,
        "aristas": m,
        "densidad": nx.density(sub) if n > 1 else 0.0,
        "clustering": nx.average_clustering(sub) if n else 0.0,
        "histograma_grado_norm": hist_norm,
        "diametro": diametro,
        "conexo": conexo,
    }


def _bhattacharyya(p, q):
    """Distancia de Bhattacharyya entre dos histogramas normalizados
    (se alinean con ceros hasta el mismo largo)."""
    largo = max(len(p), len(q))
    p = list(p) + [0.0] * (largo - len(p))
    q = list(q) + [0.0] * (largo - len(q))
    bc = sum(math.sqrt(a * b) for a, b in zip(p, q))
    bc = min(1.0, max(0.0, bc))
    return math.sqrt(1.0 - bc)


def comparar_subgrafos(piscina, tamano_minimo=3, top=10):
    """Compara todas las comunidades detectadas (sobre la capa observada)
    entre si. Devuelve lista de dicts con: par de comunidades, firmas,
    distancias, similitud y origen. SOLO LECTURA."""
    g_con = grafo_conceptos(piscina)
    obs = grafo_observado(g_con)
    _, comunidades = _comunidades(g_con)

    regiones = []
    for i, terminos in enumerate(comunidades):
        sub = obs.subgraph(terminos)
        if sub.number_of_nodes() >= tamano_minimo:
            regiones.append({"comunidad": i, "terminos": terminos, "sub": sub})

    resultados = []
    for i in range(len(regiones)):
        for j in range(i + 1, len(regiones)):
            a, b = regiones[i], regiones[j]
            fa, fb = _firma(a["sub"]), _firma(b["sub"])
            d_grados = _bhattacharyya(fa["histograma_grado_norm"], fb["histograma_grado_norm"])
            d_forma = (abs(fa["densidad"] - fb["densidad"]) + abs(fa["clustering"] - fb["clustering"])) / 2
            sim = 1.0 - (d_grados + d_forma) / 2
            resultados.append({
                "id": f"comparacion-{len(resultados) + 1}",
                "tipo": "similitud_estructural",
                "capa": "candidato",
                "titulo": f"comunidad {a['comunidad']} ~ comunidad {b['comunidad']} (sim {sim:.2f})",
                "elementos": {
                    "comunidad_a": {"id": a["comunidad"], "terminos": a["terminos"][:20]},
                    "comunidad_b": {"id": b["comunidad"], "terminos": b["terminos"][:20]},
                },
                "evidencia": {
                    "firma_a": {k: v for k, v in fa.items() if k != "histograma_grado_norm"},
                    "firma_b": {k: v for k, v in fb.items() if k != "histograma_grado_norm"},
                    "dist_grados": round(d_grados, 3),
                    "dist_forma": round(d_forma, 3),
                    "similitud": round(sim, 3),
                    "aristas_entre_regiones": 0
                    if not any(
                        obs.has_edge(u, v)
                        for u in a["terminos"] for v in b["terminos"]
                    )
                    else sum(
                        1 for u in a["terminos"] for v in b["terminos"] if obs.has_edge(u, v)
                    ),
                    "nota": "similitud estructural: no implica relacion semantica ni crea aristas",
                },
                "origen": {
                    "algoritmo": "cartografia.comparacion.comparar_subgrafos",
                    "parametros": {"tamano_minimo": tamano_minimo, "top": top},
                    "capa_grafo": "observada",
                },
            })

    resultados.sort(key=lambda r: r["evidencia"]["similitud"], reverse=True)
    return resultados[:top]