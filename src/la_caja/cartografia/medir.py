"""Etapa A -- medicion estructural de la piscina.

Funciones puras de lectura sobre una Piscina. No mutan el estado vivo,
no inventan aristas y no mezclan capas:

  - Grafo de NAVEGACION: vertices = nodos de la piscina, aristas = las
    ARISTAS EXPLICITAS (la unica conectividad que el modelo admite como
    ruta). El peso de cada arista es la fuerza acumulada de las
    relaciones observadas que la materializan.
  - Grafo de CONCEPTOS: vertices = burbujas, aristas OBSERVADAS = las
    relaciones (confianza 1.0, peso = fuerza de co-ocurrencia). La
    co-membresia se agrega como capa de ACTIVACION con tipo propio:
    jamas se confunde con navegacion (regla de oro del nucleo).
  - La inferencia (0.5^k via cerrar transitivo) NO se materializa como
    arista: se consulta bajo demanda con piscina.relacion().

Distancias que este modulo NO equipara (ver docs/cartografia.md):
distancia de grafo (saltos), distancia ponderada (fuerza), distancia
semantica (no existe aqui) y distancia de visualizacion (solo en el
HTML, producto del layout).

Dependencia: networkx. Es opcional para el nucleo de la_caja (que sigue
sin dependencias externas) y requerida solo por la cartografia.
"""
from __future__ import annotations

import networkx as nx


# ---------------------------------------------------------------- extraccion

def grafo_navegacion(piscina):
    """Red de navegacion: vertices = nodos de la piscina, aristas =
    aristas explicitas entre nodos. peso = fuerza acumulada de las
    relaciones observadas que materializan la arista; n_relaciones =
    cuantas relaciones la sostienen."""
    g = nx.Graph()
    for nid, nodo in piscina.nodos.items():
        g.add_node(
            nid,
            terminos="|".join(sorted(nodo.burbujas)),
            n_terminos=len(nodo.burbujas),
            peso=sum(piscina.burbujas[t].peso for t in nodo.burbujas),
        )
    # indice inverso: arista de nodos -> (fuerza acumulada, n_relaciones)
    fuerza_por_arista = {}
    for (a, b), aristas in piscina.aristas_por_relacion.items():
        if (a, b) not in piscina.relaciones:
            continue
        f = piscina.relaciones[(a, b)]["fuerza"]
        for x, y in aristas:
            if x not in piscina.nodos or y not in piscina.nodos:
                continue
            clave = tuple(sorted((x, y)))
            prev = fuerza_por_arista.get(clave)
            fuerza_por_arista[clave] = (prev[0] + f, prev[1] + 1) if prev else (f, 1)
    for nid, nodo in piscina.nodos.items():
        for vecino in nodo.aristas:
            if nid < vecino and vecino in piscina.nodos:
                f, k = fuerza_por_arista.get(tuple(sorted((nid, vecino))), (1, 0))
                g.add_edge(nid, vecino, peso=f, n_relaciones=k)
    return g


def grafo_conceptos(piscina, incluir_activacion=True):
    """Red de conceptos: vertices = burbujas con sus atributos vivos
    (peso, nivel, membresias, ultimo_evento). Aristas OBSERVADAS =
    relaciones (peso = fuerza). Opcionalmente agrega la capa de
    ACTIVACION (co-membresia de nodos compartidos) como aristas de tipo
    propio: activacion NO es navegacion."""
    g = nx.Graph()
    for t, b in piscina.burbujas.items():
        g.add_node(
            t,
            peso=b.peso,
            nivel=piscina.nivel_promocion(t),
            membresias=len(b.nodos),
            ultimo_evento=b.ultimo_evento,
        )
    for (a, b), datos in piscina.relaciones.items():
        g.add_edge(
            a, b,
            tipo="observada",
            peso=datos["fuerza"],
            refuerzos=datos["refuerzos"],
            ultimo_evento=datos["ultimo_evento"],
        )
    if incluir_activacion:
        por_nodo = {}
        for t, b in piscina.burbujas.items():
            for nid in b.nodos:
                por_nodo.setdefault(nid, []).append(t)
        pares = {}
        for terminos in por_nodo.values():
            terminos = sorted(terminos)
            for i in range(len(terminos)):
                for j in range(i + 1, len(terminos)):
                    clave = (terminos[i], terminos[j])
                    pares[clave] = pares.get(clave, 0) + 1
        for (a, b), k in pares.items():
            if not g.has_edge(a, b):
                g.add_edge(a, b, tipo="activacion", peso=k)
    return g


def grafo_observado(g_conceptos):
    """Subgrafo solo con aristas OBSERVADAS (la capa de navegacion
    conceptual), conservando todos los vertices. Es la base de las
    metricas estructurales: la activacion no cuenta como conexion."""
    g = nx.Graph(
        (u, v, d) for u, v, d in g_conceptos.edges(data=True)
        if d.get("tipo") == "observada"
    )
    g.add_nodes_from(g_conceptos.nodes(data=True))
    return g


# ---------------------------------------------------------------- utilidades

def _gini(valores):
    """Indice de Gini (0 = uniforme, 1 = concentracion maxima)."""
    valores = sorted(valores)
    n = len(valores)
    total = sum(valores)
    if n == 0 or total == 0:
        return 0.0
    acum = 0.0
    for i, v in enumerate(valores, 1):
        acum += i * v
    return (2 * acum) / (n * total) - (n + 1) / n


def _comunidades(g_conceptos):
    """Comunidades por modularidad greedy (determinista) sobre la capa
    observada. Devuelve (particion nodo->id, lista de comunidades)."""
    obs = grafo_observado(g_conceptos)
    if obs.number_of_edges() == 0:
        return {n: i for i, n in enumerate(sorted(obs.nodes()))}, []
    comunidades = nx.community.greedy_modularity_communities(obs, weight="peso")
    particion = {}
    listas = []
    for i, c in enumerate(comunidades):
        listas.append(sorted(c))
        for n in c:
            particion[n] = i
    return particion, listas


def _diametro(obs):
    """Diametro del componente mas grande del grafo observado: exacto
    hasta 400 nodos; doble barrido (cota inferior) si es mayor. Se
    documenta el metodo usado junto al valor."""
    if obs.number_of_nodes() == 0:
        return 0, "vacio"
    comp = max(nx.connected_components(obs), key=len)
    h = obs.subgraph(comp)
    if h.number_of_nodes() < 2:
        return 0, "trivial"
    if h.number_of_nodes() <= 400:
        return nx.diameter(h), "exacto"
    v0 = max(h.nodes(), key=lambda n: h.degree(n))
    lejos = nx.single_source_shortest_path_length(h, v0)
    extremo = nx.single_source_shortest_path_length(h, max(lejos, key=lejos.get))
    return max(extremo.values()), "aproximado_doble_barrido"


# ---------------------------------------------------------------- medicion

def medir(piscina):
    """Mediciones reproducibles del estado vivo de la piscina.

    Devuelve (medidas, estructuras):
      medidas    -- dict serializable con secciones global,
                    distribuciones, local y comunidades.
      estructuras -- {"navegacion", "conceptos", "particion"}: los
                    grafos extraidos (networkx) y la particion de
                    comunidades, para etapas posteriores.

    SOLO LECTURA: el estado de la piscina no se altera (los tests lo
    verifican comparando a_dict() antes y despues).
    """
    g_nav = grafo_navegacion(piscina)
    g_con = grafo_conceptos(piscina)
    obs = grafo_observado(g_con)
    n_activacion = sum(
        1 for _, _, d in g_con.edges(data=True) if d.get("tipo") == "activacion"
    )

    particion, comunidades = _comunidades(g_con)
    diametro, metodo_diametro = _diametro(obs)

    grados = [d for _, d in obs.degree()]
    fuerza_total = sum(d["peso"] for _, _, d in obs.edges(data=True))
    componentes = sorted((len(c) for c in nx.connected_components(obs)), reverse=True)
    gigante = componentes[0] if componentes else 0

    long_camino = 0.0
    if gigante >= 2:
        gc = max(nx.connected_components(obs), key=len)
        long_camino = nx.average_shortest_path_length(obs.subgraph(gc))

    medidas = {
        "capa": "medicion",
        "global": {
            "terminos": len(piscina.burbujas),
            "nodos_navegacion": len(piscina.nodos),
            "relaciones_observadas": len(piscina.relaciones),
            "aristas_navegacion": g_nav.number_of_edges(),
            "aristas_activacion": n_activacion,
            "eventos_log": piscina._n_eventos,
            "fuerza_total_observada": fuerza_total,
            "componentes_conceptos": componentes[:50],
            "n_componentes": len(componentes),
            "fraccion_componente_gigante": (
                gigante / len(piscina.burbujas) if piscina.burbujas else 0.0
            ),
            "densidad_observada": nx.density(obs) if obs.number_of_nodes() > 1 else 0.0,
            "densidad_navegacion": nx.density(g_nav) if g_nav.number_of_nodes() > 1 else 0.0,
            "diametro_componente_gigante": diametro,
            "metodo_diametro": metodo_diametro,
            "longitud_camino_promedio_gigante": long_camino,
            "modularidad": 0.0,
        },
        "distribuciones": {
            "grado_medio_observado": (sum(grados) / len(grados)) if grados else 0.0,
            "grado_max_observado": max(grados) if grados else 0,
            "gini_grado_observado": _gini(grados),
            "gini_peso_burbujas": _gini([b.peso for b in piscina.burbujas.values()]),
            "histograma_grado": {
                str(k): v for k, v in sorted(
                    {g: list(grados).count(g) for g in set(grados)}.items()
                )
            } if grados else {},
        },
        "local": {},
        "comunidades": [
            {"id": i, "tamano": len(c), "terminos": c[:50]}
            for i, c in enumerate(comunidades)
        ],
    }

    if comunidades and obs.number_of_edges():
        medidas["global"]["modularidad"] = nx.community.modularity(
            obs, comunidades, weight="peso"
        )

    # listas locales destacadas (top-k por metrica; listas [elemento, valor])
    k = 10
    entre_nodos = nx.betweenness_centrality(obs) if obs.number_of_nodes() else {}
    entre_aristas = nx.edge_betweenness_centrality(obs) if obs.number_of_edges() else {}
    medidas["local"] = {
        "top_grado": sorted(
            [[n, d] for n, d in obs.degree()], key=lambda x: x[1], reverse=True
        )[:k],
        "top_grado_ponderado": sorted(
            [
                [n, sum(dd["peso"] for _, _, dd in obs.edges(n, data=True))]
                for n in obs.nodes()
            ],
            key=lambda x: x[1],
            reverse=True,
        )[:k],
        "top_intermediacion_nodos": sorted(
            [[n, v] for n, v in entre_nodos.items()], key=lambda x: x[1], reverse=True
        )[:k],
        "top_intermediacion_aristas": sorted(
            [[[u, v], val] for (u, v), val in entre_aristas.items()],
            key=lambda x: x[1],
            reverse=True,
        )[:k],
        "clustering_promedio": nx.average_clustering(obs) if obs.number_of_nodes() else 0.0,
        "triangulos_totales": sum(nx.triangles(obs).values()) // 3 if obs.number_of_nodes() else 0,
    }

    estructuras = {"navegacion": g_nav, "conceptos": g_con, "particion": particion}
    return medidas, estructuras