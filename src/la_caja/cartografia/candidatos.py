"""Etapa B -- descubrimiento de candidatos.

Superficie regiones, nodos y configuraciones que merecen examen, a
partir de MEDICIONES de la etapa A. No interpreta: cada candidato lleva
su evidencia (los numeros que lo dispararon), su origen (algoritmo y
parametros) y los elementos del grafo vivo involucrados. Nada de lo que
se produce aqui es una relacion del grafo: es una capa de reporte
separada y revisable (requisito 7/8 de la directiva).

Senales implementadas (cada una con su tipo):

  - puente_nodo        nodo cuya intermediacion es desproporcionada
                       respecto de su grado (conecta sin concentrar).
  - puente_arista      arista de intermediacion alta que une dos
                       comunidades distintas.
  - articulo           nodo de corte del grafo observado (su ausencia
                       desconecta).
  - frontera           aristas entre comunidades (limites medidos, no
                       semanticos).
  - isla               componente pequena (2..k nodos): estructura
                       esparcia que puede ser informativa; NO se asume
                       menos valiosa por ser chica.
  - hub_anomalo        grado fuera de lo esperado para su tamano de
                       vecindario (desviacion descriptiva).
  - densidad_local     nodos con clustering local muy por encima o muy
                       por debajo del promedio global (transicion de
                       regimen de conectividad).
  - traza_dormida      parejas olvidadas con fuerza historica alta:
                       candidatas a rehidratacion si se re-observan.
  - motivo_recurrencia triangulos/estrellas que aparecen en componentes
                       o comunidades distintas (configuracion repetida
                       en regiones desconectadas).

Linea base / modelo nulo:
  Cuando existe una comparacion defendible (clustering local vs modelo
  de configuracion con la misma secuencia de grados, sembrado y
  acotado), se reporta observado vs esperado. Donde no hay base, el
  candidato es DESCRIPTIVO y lo dice ("baseline": null). No se inventan
  umbrales universales: todo umbral vive en CONFIG_DEFAULT y esta
  documentado ahi.
"""
from __future__ import annotations

import math

import networkx as nx

from .medir import grafo_conceptos, grafo_observado, _comunidades


CONFIG_DEFAULT = {
    # Nodo puente: intermediacion normalizada sobre este percentil del
    # maximo Y grado bajo (< percentil_grado). Razon: un hub con
    # intermediacion alta no es un puente, es un concentrador; el
    # puente interesante es el que media sin absorber trafico propio.
    "puente_intermediacion_frac": 0.5,
    "puente_grado_frac": 0.3,
    # Arista puente: intermediacion de arista sobre esta fraccion del
    # maximo.
    "arista_puente_frac": 0.5,
    # Islas: componentes de entre 2 y este tamano (los nodos aislados
    # solos son triviales; las islas pequenas con estructura no).
    "isla_max": 8,
    # Densidad local: desviacion |clustering_local - clustering_global|
    # por encima de este valor dispara el candidato (descriptivo).
    "densidad_local_delta": 0.4,
    # Modelo nulo de clustering: maximo de nodos para correr el modelo
    # de configuracion (costo). Por encima, baseline = null.
    "nulo_max_nodos": 800,
    "nulo_seed": 0,
    # Top-k por senal (reporte acotado; el resto queda en las medidas).
    "top_k": 10,
    # Trayectoria dormida: fuerza_pico minima para reportar.
    "traza_fuerza_min": 2,
    "top_candidatos": 60,
}


def _desviacion_z(valores, v):
    n = len(valores)
    if n < 2:
        return 0.0
    media = sum(valores) / n
    var = sum((x - media) ** 2 for x in valores) / n
    sd = math.sqrt(var)
    return (v - media) / sd if sd > 0 else 0.0


def _clustering_nulo(obs, seed, max_nodos):
    """Clustering medio esperado bajo un modelo de configuracion con la
    misma secuencia de grados (determinista por semilla). Devuelve None
    si el grafo es demasiado grande o no tiene aristas: en ese caso los
    candidatos de densidad local quedan como descriptivos."""
    if obs.number_of_edges() == 0 or obs.number_of_nodes() > max_nodos:
        return None
    grados = [d for _, d in obs.degree()]
    if sum(grados) % 2 == 1:
        grados = grados[:-1]
        if not grados:
            return None
    try:
        nulo = nx.configuration_model(grados, seed=seed)
        nulo = nx.Graph(nulo)
        nulo.remove_edges_from(nx.selfloop_edges(nulo))
        return nx.average_clustering(nulo)
    except Exception:
        return None


def descubrir(piscina, config=None):
    """Descubre candidatos de examen sobre el estado vivo de la piscina.

    Devuelve (candidatos, resumen):
      candidatos -- lista de dicts; cada uno: id, tipo, titulo,
                    elementos, evidencia, origen, capa="candidato".
      resumen    -- conteos por tipo.

    SOLO LECTURA sobre la piscina. Los candidatos NO tocan el grafo.
    """
    cfg = dict(CONFIG_DEFAULT)
    if config:
        cfg.update(config)

    g_con = grafo_conceptos(piscina)
    obs = grafo_observado(g_con)
    particion, comunidades = _comunidades(g_con)

    candidatos = []
    k = cfg["top_k"]

    def agregar(tipo, titulo, elementos, evidencia):
        candidatos.append({
            "id": f"{tipo}-{len([c for c in candidatos if c['tipo'] == tipo]) + 1}",
            "tipo": tipo,
            "capa": "candidato",
            "titulo": titulo,
            "elementos": elementos,
            "evidencia": evidencia,
            "origen": {
                "algoritmo": "cartografia.candidatos.descubrir",
                "parametros": cfg,
                "capa_grafo": "observada",
            },
        })

    if obs.number_of_nodes() == 0:
        return [], {}

    # ------------------------------------------------ puentes (nodos)
    entre = nx.betweenness_centrality(obs)
    grados = dict(obs.degree())
    max_entre = max(entre.values()) if entre else 0.0
    max_grado = max(grados.values()) if grados else 0
    if max_entre > 0 and max_grado > 0:
        puentes = [
            (n, e) for n, e in entre.items()
            if e >= cfg["puente_intermediacion_frac"] * max_entre
            and grados[n] <= cfg["puente_grado_frac"] * max_grado
        ]
        puentes.sort(key=lambda x: x[1], reverse=True)
        for n, e in puentes[:k]:
            agregar(
                "puente_nodo",
                f"'{n}' media entre regiones con grado bajo",
                {"terminos": [n]},
                {
                    "intermediacion": round(e, 4),
                    "grado": grados[n],
                    "comunidad": particion.get(n),
                    "nota": "intermediacion alta + grado bajo: conecta sin concentrar",
                },
            )

    # ------------------------------------------------ aristas puente
    if obs.number_of_edges():
        eb = nx.edge_betweenness_centrality(obs)
        max_eb = max(eb.values()) if eb else 0.0
        if max_eb > 0:
            aristas = sorted(eb.items(), key=lambda x: x[1], reverse=True)
            for (u, v), val in aristas[:k]:
                if val < cfg["arista_puente_frac"] * max_eb:
                    continue
                cu, cv = particion.get(u), particion.get(v)
                agregar(
                    "puente_arista",
                    f"'{u}'-'{v}' sostiene trafico entre regiones",
                    {"terminos": [u, v]},
                    {
                        "intermediacion_arista": round(val, 4),
                        "fuerza_observada": obs[u][v].get("peso"),
                        "comunidades": [cu, cv],
                        "cruza_comunidades": cu != cv,
                    },
                )

    # ------------------------------------------------ nodos de corte
    for n in sorted(nx.articulation_points(obs))[:k]:
        agregar(
            "articulo",
            f"quitar '{n}' desconecta el grafo observado",
            {"terminos": [n]},
            {"grado": grados[n], "intermediacion": round(entre.get(n, 0.0), 4)},
        )

    # ------------------------------------------------ fronteras
    frontera = [
        (u, v, d) for u, v, d in obs.edges(data=True)
        if particion.get(u) != particion.get(v)
    ]
    frontera.sort(key=lambda x: x[2].get("peso", 0), reverse=True)
    for u, v, d in frontera[:k]:
        agregar(
            "frontera",
            f"limite de comunidades: '{u}' ({particion.get(u)}) - '{v}' ({particion.get(v)})",
            {"terminos": [u, v]},
            {
                "fuerza_observada": d.get("peso"),
                "comunidades": [particion.get(u), particion.get(v)],
                "nota": "arista observada que cruza una particion de modularidad",
            },
        )

    # ------------------------------------------------ islas
    componentes = sorted(nx.connected_components(obs), key=len)
    for c in componentes:
        if 2 <= len(c) <= cfg["isla_max"]:
            terminos = sorted(c)
            agregar(
                "isla",
                f"isla de {len(c)} conceptos sin conexion al resto",
                {"terminos": terminos},
                {
                    "tamano": len(c),
                    "aristas_internas": obs.subgraph(c).number_of_edges(),
                    "nota": "estructura esparcia: candidata a examen, no a descarte",
                },
            )
        if len(candidates := [x for x in candidatos if x["tipo"] == "isla"]) >= cfg["top_candidatos"]:
            break

    # ------------------------------------------------ hubs anomalos
    lista_grados = list(grados.values())
    hubs = sorted(grados.items(), key=lambda x: x[1], reverse=True)
    for n, g in hubs[:k]:
        z = _desviacion_z(lista_grados, g)
        if z >= 2.0:
            agregar(
                "hub_anomalo",
                f"'{n}' concentra grado (z={z:.1f})",
                {"terminos": [n]},
                {"grado": g, "z_grado": round(z, 2), "baseline": "distribucion de grados observada"},
            )

    # ------------------------------------------------ densidad local
    clus_global = nx.average_clustering(obs) if obs.number_of_nodes() else 0.0
    esperado = _clustering_nulo(obs, cfg["nulo_seed"], cfg["nulo_max_nodos"])
    clus_local = nx.clustering(obs)
    deltas = sorted(
        ((n, clus_local[n] - clus_global) for n in obs.nodes()),
        key=lambda x: abs(x[1]),
        reverse=True,
    )
    for n, delta in deltas[:k]:
        if abs(delta) < cfg["densidad_local_delta"]:
            continue
        evidencia = {
            "clustering_local": round(clus_local[n], 3),
            "clustering_global": round(clus_global, 3),
            "delta": round(delta, 3),
            "clustering_esperado_nulo": round(esperado, 3) if esperado is not None else None,
            "baseline": "modelo de configuracion (misma secuencia de grados)"
            if esperado is not None else None,
        }
        agregar(
            "densidad_local",
            f"'{n}': regimen de conectividad local {'denso' if delta > 0 else 'esparcido'}",
            {"terminos": [n]},
            evidencia,
        )

    # ------------------------------------------------ trazas dormidas
    vistos_traza = set()
    for t in sorted(piscina.burbujas):
        for registro in piscina.historial(t):
            p = registro["partner"]
            clave = tuple(sorted((t, p)))
            if clave in vistos_traza:
                continue
            vistos_traza.add(clave)
            if registro["fuerza_pico"] >= cfg["traza_fuerza_min"]:
                agregar(
                    "traza_dormida",
                    f"'{t}'~'{p}': co-ocurrencia olvidada con fuerza historica {registro['fuerza_pico']}",
                    {"terminos": [t, p]},
                    {
                        "fuerza_pico": registro["fuerza_pico"],
                        "ultimo_evento": registro["ultimo_evento"],
                        "capturas": registro["capturas"],
                        "nota": "capa inerte: candidata a rehidratacion solo si se re-observa",
                    },
                )
        if len([x for x in candidatos if x["tipo"] == "traza_dormida"]) >= cfg["top_candidatos"]:
            break

    # ------------------------------------------------ recurrencia de motivos
    tri = nx.triangles(obs) if obs.number_of_nodes() else {}
    por_componente = {}
    for i, c in enumerate(nx.connected_components(obs)):
        por_componente[i] = c
    triangulos_con_multicomunidad = 0
    for u, v, w in _triangulos(obs):
        comunidades_tri = {particion.get(u), particion.get(v), particion.get(w)}
        if len(comunidades_tri) > 1:
            triangulos_con_multicomunidad += 1
    if triangulos_con_multicomunidad:
        agregar(
            "motivo_recurrencia",
            f"triangulos observados cruzan comunidades ({triangulos_con_multicomunidad})",
            {"terminos": []},
            {
                "triangulos_totales": sum(tri.values()) // 3,
                "triangulos_multicomunidad": triangulos_con_multicomunidad,
                "nota": "configuracion repetida en regiones separadas: descriptivo",
            },
        )

    resumen = {}
    for c in candidatos:
        resumen[c["tipo"]] = resumen.get(c["tipo"], 0) + 1
    return candidatos, resumen


def _triangulos(obs):
    """Itera triangulos una sola vez (determinista por orden de nodos)."""
    if obs.number_of_nodes() == 0:
        return
    vecinos = {n: set(obs.neighbors(n)) for n in obs.nodes()}
    vistos = set()
    for u in sorted(obs.nodes()):
        for v in sorted(vecinos[u]):
            if v <= u:
                continue
            for w in sorted(vecinos[u] & vecinos[v]):
                if w <= v:
                    continue
                clave = (u, v, w)
                if clave not in vistos:
                    vistos.add(clave)
                    yield clave