"""Corpus de prueba reproducible para la cartografia (fixture declarado).

Dos dominios conceptualmente distintos con estructura de ramificacion
analoga (botanica y teoria de grafos), mas material de control. Todo
patron "plantado" esta documentado en PATRONES_ESPERADOS: sirven para
validar que la medicion recupera propiedades conocidas, pero NO son
observaciones genuinas de un corpus real (la directiva exige que los
fixtures queden separados de los hallazgos).

Cobertura exigida por la directiva (seccion 10):
  - referencias directas y co-ocurrencia repetida (dentro de cada dominio);
  - pasajes semanticamente relacionados con vocabulario distinto
    (nutricion vegetal vs flujo de recursos; caminos vs recorridos);
  - estructuras similares en dominios distintos (ramificacion: raiz/hoja
    aparecen como terminos en AMBOS dominios, conectando solo si se
    observan juntos);
  - material no relacionado (clima / cocina);
  - conexiones esparcias entre grupos separados (una sola consulta
    cruza explicitamente los dos dominios).
"""

# (texto, etiqueta de fixture) -- el orden es el orden de ingesta.
CORPUS = [
    # ---- Dominio A: botanica (estructura reforzada por repeticion)
    ("el arbol crece desde la raiz y se divide en ramas", "botanica"),
    ("la raiz absorbe agua y sostiene el tallo del arbol", "botanica"),
    ("cada rama del arbol termina en hojas verdes", "botanica"),
    ("la hoja captura luz y produce savia para el arbol", "botanica"),
    ("la savia circula desde la raiz hasta la copa del arbol", "botanica"),
    ("la semilla germina y brota una raiz nueva", "botanica"),
    ("la flor del arbol se convierte en fruto con semillas", "botanica"),
    ("el tallo sostiene las ramas y transporta savia", "botanica"),
    ("la copa del arbol es el conjunto de ramas altas", "botanica"),
    ("arbol raiz rama hoja savia", "botanica"),  # refuerzo concentrado

    # ---- Dominio B: teoria de grafos (estructura analoga)
    ("un grafo se compone de nodos unidos por aristas", "grafos"),
    ("el nodo raiz del arbol de expansion conecta todos los caminos", "grafos"),
    ("cada hoja del arbol de expansion es un nodo terminal", "grafos"),
    ("un camino recorre nodos consecutivos por sus aristas", "grafos"),
    ("el subgrafo inducido conserva los nodos y sus aristas", "grafos"),
    ("el recorrido en profundidad visita cada nodo una vez", "grafos"),
    ("la arista conecta dos nodos del grafo", "grafos"),
    ("un grafo conexo tiene un camino entre cualquier par de nodos", "grafos"),
    ("grafo nodo arista camino raiz hoja", "grafos"),  # refuerzo concentrado

    # ---- Vocabulario distinto, estructura semantica analoga
    ("los nutrientes fluyen desde la base hacia los brotes de la planta", "analogia"),
    ("los recursos fluyen desde el origen hacia los destinos de la red", "analogia"),

    # ---- Material no relacionado (control de aislamiento)
    ("el pronostico anuncia lluvias y viento para el fin de semana", "ruido_clima"),
    ("la sopa de verduras se cocina a fuego lento con sal", "ruido_cocina"),

    # ---- Puente esparcido: UNA sola consulta cruza los dominios.
    # Ambos terminos ya estan establecidos, asi que el nucleo crea una
    # arista observada honesta (y solo esta).
    ("la raiz del arbol botanico y la raiz del grafo se ramifican igual", "puente"),
]

# Patrones plantados que la cartografia deberia poder recuperar (cada
# uno con su criterio). No son hipotesis del sistema: son la vara de
# validacion del fixture.
PATRONES_ESPERADOS = [
    {
        "patron": "dos comunidades principales (botanica vs grafos)",
        "criterio": "modularidad > 0 y particion con >= 2 comunidades no triviales",
    },
    {
        "patron": "puente entre dominios via 'raiz' y 'arbol' (co-ocurrencia observada)",
        "criterio": "relacion observada (fuerza >= 1) entre terminos de ambos dominios",
    },
    {
        "patron": "material de ruido aislado del resto",
        "criterio": "'lluvias'/'sopa' sin relaciones con los dominios principales",
    },
    {
        "patron": "'hoja' y 'raiz' como terminos de doble membresia (multi-dominio)",
        "criterio": "membresias > 1 en ambos terminos",
    },
]


def ingestar(caja):
    """Procesa el corpus completo en orden, usando el lote persistente si
    la caja lo soporta. Devuelve la lista de eventos por consulta."""
    resultados = []
    try:
        gestor = caja.lote()
    except TypeError:
        gestor = None
    if gestor is not None:
        with gestor:
            for texto, _etiq in CORPUS:
                resultados.append(caja.procesar_consulta(texto))
    else:
        for texto, _etiq in CORPUS:
            resultados.append(caja.procesar_consulta(texto))
    return resultados