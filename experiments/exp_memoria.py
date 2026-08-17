"""Experimento de memoria de largo plazo (ver falsacion.md).

Corre los tests A (discriminacion/no-densificacion), B (fidelidad al
corpus) y C (recuperacion temporal) sobre dos corrientes organicas:
la bandeja de salida de un usuario de Enron y el autor con mas posts
del Blog Authorship Corpus. Criterios pre-registrados en falsacion.md.

Uso:
  python experiments/exp_memoria.py enron
  python experiments/exp_memoria.py blog
"""
import json
import os
import random
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from la_caja import LaCaja  # noqa: E402

DATOS = r"C:\Users\Agentic\AppData\Local\Temp\opencode\memoria_exp"
ENRON_PARQUET = os.path.join(DATOS, "enron_00000.parquet")
ENRON_REMITENTE = "jeff.dasovich@enron.com"
BLOGS_DIR = os.path.join(DATOS, "blogs", "blogs")

VENTANA_GT = 4  # co-ocurrencia del ground truth = ventana del modelo
OPTIMIZAR_CADA = 200
TOP_FREC = 500
MUESTRA_PARES = 400

# Filtro ontologico en ingles (el default del modelo es espanol).
# Lista amplia: los hubs de uso frecuente (like, got, time...) deben
# filtrarse o acumulan membresias gigantes que explotan el grafo.
INGLES = set("""
a an and or but if then else for nor not no so yet both either neither
of to in on at by with from into through during before after above below
between out off over under again further then once here there when where why
how all any both each few more most other some such only own same too very
can will just should now is are was were be been being am has have had do
does did doing would could shall may might must about against among as per
than that this these those it its this that you your yours he him his she
her hers we our ours they them their theirs i me my myself up down out in
off over under again further then once here there what which who whom whose
the and but or so because while although if unless since
of in on at by with from into through during before after above below
between out off over under again then once here there when where why how
like just got get know now time day days week weeks month months year years
one two three way ways things thing something anything everything nothing
much many little bit big small good bad great really very quite well make
made making take took taking going go went get got getting see saw seen
want wanted want really right back still even another other some someone
anyone everybody everyone nobody never always sometimes often already also
too though think thought think about about
hey hi hello oh yeah ok okay uhh uh
im ive id youll youve dont doesnt didnt cant wont wouldnt couldnt isnt
arent wasnt werent hasnt havent hadnt its itd theyd well well lets let
need needed needs come came coming home back maybe perhaps probably sure
feel felt feeling feel today tonight tomorrow yesterday morning night
there their theyre there were been being thing things stuff people person
man woman guy guys girl friend friends family work school day school
new old first last next again ever never once twice anytime
""".split())

TOKEN_RE = re.compile(r"[a-záéíóúñü]+")


def tokenizar(texto):
    return TOKEN_RE.findall(texto.lower())


def filtrar(tokens):
    return [t for t in tokens if t not in INGLES]


# ----------------------------------------------------------------------
# Carga de datos
# ----------------------------------------------------------------------

def cargar_enron():
    """Parquet -> lista [(fecha_iso, texto)] de la bandeja de salida del
    remitente, dedupe por cuerpo normalizado, fecha real."""
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    import pyarrow as pa
    dates = pc.cast(
        pq.read_table(ENRON_PARQUET, columns=["date"]).column("date"), pa.string()
    ).to_pylist()
    t = pq.read_table(ENRON_PARQUET, columns=["from", "body"])
    d = t.to_pydict()
    docs = []
    vistos = set()
    for f, ds, b in zip(d["from"], dates, d["body"]):
        if (f or "").lower() != ENRON_REMITENTE:
            continue
        if ds[:4] < "1998":
            continue
        b = (b or "").strip()
        if not b:
            continue
        clave = re.sub(r"\s+", " ", b.lower())
        if clave in vistos:
            continue
        if len(filtrar(tokenizar(b))) < 3:
            continue
        vistos.add(clave)
        docs.append((ds, b))
    docs.sort(key=lambda x: x[0])
    return docs


def _fecha_blog(s):
    for fmt in ("%d,%B,%Y", "%d,%b,%Y"):
        try:
            return time.strftime("%Y-%m-%d", time.strptime(s.strip(), fmt))
        except ValueError:
            continue
    return None


def seleccionar_autor_blog():
    """Escanee los 19k archivos y elige el autor con MAYOR rango temporal
    entre los que tienen volumen (>= 100 posts con fecha valida): el
    diario personal/online mas largo disponible. Cachea en JSON."""
    cache = os.path.join(DATOS, "autor_blog.json")
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as fh:
            d = json.load(fh)
        return d["autor"], [tuple(p) for p in d["posts"]]
    mejor, mejor_clave = None, (0, 0)  # (span_dias, posts)
    for nombre in os.listdir(BLOGS_DIR):
        if not nombre.endswith(".xml"):
            continue
        try:
            root = ET.parse(os.path.join(BLOGS_DIR, nombre)).getroot()
        except Exception:
            continue
        fechas = [f for f in (_fecha_blog((h.text or "").strip()) for h in root if h.tag.strip() == "date") if f]
        if len(fechas) < 100:
            continue
        span = (
            time.mktime(time.strptime(fechas[-1], "%Y-%m-%d"))
            - time.mktime(time.strptime(fechas[0], "%Y-%m-%d"))
        ) / 86400.0
        clave = (span, len(fechas))
        if clave > mejor_clave:
            mejor, mejor_clave = nombre, clave
    posts = []
    root = ET.parse(os.path.join(BLOGS_DIR, mejor)).getroot()
    fecha_actual = None
    for hijo in root:
        tag = hijo.tag.strip()
        if tag == "date":
            fecha_actual = _fecha_blog((hijo.text or "").strip())
        elif tag == "post":
            texto = (hijo.text or "").strip()
            if texto and fecha_actual and len(filtrar(tokenizar(texto))) >= 3:
                posts.append((fecha_actual, texto))
    posts.sort(key=lambda x: x[0])
    with open(cache, "w", encoding="utf-8") as fh:
        json.dump({"autor": mejor, "posts": posts}, fh, ensure_ascii=False)
    return mejor, posts


# ----------------------------------------------------------------------
# Ground truth de co-ocurrencia (Test B)
# ----------------------------------------------------------------------

def co_ocurrencia_corpus(docs):
    """Pares co-ocurrentes dentro de la ventana del modelo, sobre el
    corpus completo (filtrado igual que el modelo)."""
    par = Counter()
    por_doc = []
    for _, texto in docs:
        toks = filtrar(tokenizar(texto))
        if not toks:
            continue
        for i, t in enumerate(toks):
            for v in toks[max(0, i - VENTANA_GT):i]:
                if v != t:
                    a, b = (t, v) if t < v else (v, t)
                    par[(a, b)] += 1
        por_doc.append(toks)
    return par, por_doc


# ----------------------------------------------------------------------
# Metricas
# ----------------------------------------------------------------------

def dsu_componentes(la):
    """Mayor componente conexo del grafo de nodos (DSU sobre aristas)."""
    parent = {nid: nid for nid in la.piscina.nodos}
    size = {nid: 1 for nid in parent}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            if size[ra] < size[rb]:
                ra, rb = rb, ra
            parent[rb] = ra
            size[ra] += size[rb]

    for nid, n in la.piscina.nodos.items():
        for vecino in n.aristas:
            if vecino in parent:
                union(nid, vecino)
    if not size:
        return 0.0
    return max(size.values()) / len(size)


def muestreo_confianza(la, pares):
    confs = [la.consultar(a, b) for a, b in pares]
    if not confs:
        return {"n": 0, "frac_conect": 0.0, "media": 0.0, "p95": 0.0}
    confs.sort()
    n = len(confs)
    frac = sum(1 for c in confs if c > 0) / n
    media = sum(confs) / n
    p95 = confs[int(0.95 * (n - 1))]
    return {"n": n, "frac_conect": frac, "media": media, "p95": p95}


def metricas(la, terminos_frec):
    """Snapshot de Test A sobre el estado actual."""
    vocab = sorted(la.piscina.burbujas)
    rng = random.Random(17)
    uniformes = [(rng.choice(vocab), rng.choice(vocab)) for _ in range(MUESTRA_PARES)]
    top = [t for t in terminos_frec if t in la.piscina.burbujas]
    de_top = [(rng.choice(top), rng.choice(top)) for _ in range(MUESTRA_PARES)] if top else []
    return {
        "terminos": len(vocab),
        "nodos": len(la.piscina.nodos),
        "aristas": sum(len(n.aristas) for n in la.piscina.nodos.values()) // 2,
        "relaciones": len(la.piscina.relaciones),
        "A1_uniforme": muestreo_confianza(la, uniformes),
        "A1_top": muestreo_confianza(la, de_top) if de_top else None,
        "A3_comp_gigante": dsu_componentes(la),
    }


# ----------------------------------------------------------------------
# Tests finales
# ----------------------------------------------------------------------

def test_a(la, terminos_frec, serie):
    res = {"serie": serie, "final": metricas(la, terminos_frec)}
    f = res["final"]
    a1 = max(f["A1_uniforme"]["frac_conect"], (f["A1_top"] or {}).get("frac_conect", 0))
    a2 = max(f["A1_uniforme"]["media"], (f["A1_top"] or {}).get("media", 0))
    a2_p95 = max(f["A1_uniforme"]["p95"], (f["A1_top"] or {}).get("p95", 0))
    res["veredicto"] = {
        "A1": "FALSA" if a1 > 0.10 else "ok",
        "A2": "FALSA" if (a2 > 0.01 or a2_p95 > 0.25) else "ok",
        "A3": "FALSA" if f["A3_comp_gigante"] > 0.50 else "ok",
    }
    return res


def test_b(la, par_gt, total_pares, docs):
    """Fidelidad al corpus."""
    relaciones = la.piscina.relaciones
    if not relaciones:
        return {"error": "sin relaciones"}
    # rango percentil de cada relacion entre todos los pares con co>=1
    pares_gt = sorted(par_gt.items(), key=lambda kv: kv[1], reverse=True)
    rango = {p: i for i, (p, _) in enumerate(pares_gt)}
    n_gt = len(pares_gt)
    pcts = []
    for (a, b) in relaciones:
        clave = (a, b) if a < b else (b, a)
        r = rango.get(clave, n_gt)  # si no co-ocurre: al final
        pcts.append(1.0 - r / max(1, n_gt))
    prec = sum(pcts) / len(pcts) * 100.0
    # recall: top-K del corpus (K = #relaciones)
    k = len(relaciones)
    topk = set(p for p, _ in pares_gt[:k])
    capturados = sum(1 for (a, b) in relaciones if (min(a, b), max(a, b)) in topk)
    rec = capturados / k
    # discriminacion: co-ocurrencia media observado / inferido / aleatorio
    def media_par(claves):
        if not claves:
            return 0.0
        return sum(par_gt.get((min(a, b), max(a, b)), 0) for a, b in claves) / len(claves)

    rng = random.Random(5)
    todos = list(la.piscina.burbujas)
    aleatorios = [(rng.choice(todos), rng.choice(todos)) for _ in range(300)]
    inferidos = []
    for _ in range(300):
        a, b = rng.choice(todos), rng.choice(todos)
        if la.consultar(a, b) and (min(a, b), max(a, b)) not in relaciones and (max(a, b), min(a, b)) not in relaciones:
            inferidos.append((a, b))
    disc = {
        "obs": media_par(list(relaciones)),
        "inf": media_par(inferidos),
        "ale": media_par(aleatorios),
    }
    res = {"precision_pct": prec, "recall": rec, "n_gt": n_gt, "discriminacion": disc}
    res["veredicto"] = {
        "B1": "FALSA" if prec < 50 else "ok",
        "B2": "FALSA" if rec < 0.30 else "ok",
        # B3: lo OBSERVADO debe co-ocurrir de verdad en el corpus (mas
        # que el azar); lo INFERIDO NO debe co-ocurrir (los pares
        # inferidos son por definicion los que no co-ocurrieron, asi que
        # inf <= ale es esperado: es la discriminacion trabajando).
        "B3": "FALSA" if disc["obs"] <= max(disc["inf"], disc["ale"]) else "ok",
    }
    return res


def test_c(docs, corte=0.60):
    """Recuperacion temporal: memoria = 60% pasado, recuperacion sobre
    40% futuro (score contra memoria previa)."""
    n = len(docs)
    k = int(n * corte)
    la = LaCaja(filtro_ontologico=INGLES)
    for fecha, texto in docs[:k]:
        la.procesar_consulta(texto)
    # frecuencia global de la memoria (baseline)
    frec = Counter()
    for t in la.piscina.burbujas:
        frec[t] = la.piscina.burbujas[t].peso
    top_frec = [t for t, _ in frec.most_common(5)]
    rng = random.Random(7)
    modelo_hits, freq_hits, rand_hits = [], [], []
    con_cover = 0
    doc_scores = 0
    for fecha, texto in docs[k:]:
        toks = list(dict.fromkeys(filtrar(tokenizar(texto))))
        conocidos = [t for t in toks if t in la.piscina.burbujas]
        if len(conocidos) < 2:
            continue
        con_cover += 1
        for t in conocidos:
            respuesta = set(conocidos) - {t}
            prim = set(la.contexto_primado(t, presupuesto=5))
            modelo_hits.append(len(prim & respuesta) / len(respuesta))
            freq_hits.append(len(set(top_frec) & respuesta) / len(respuesta))
            # baseline honesto: 5 terminos al azar del VOCABULARIO de la
            # memoria (muestrear de `conocidos` seria trampa: el azar
            # sabria la respuesta)
            r5 = {rng.choice(list(la.piscina.burbujas)) for _ in range(5)}
            rand_hits.append(len(r5 & respuesta) / len(respuesta))
            doc_scores += 1
        la.procesar_consulta(texto)
    if not modelo_hits:
        return {"error": "sin cobertura"}
    res = {
        "docs_futuros_con_tema": con_cover,
        "consultas": doc_scores,
        "hit5_modelo": sum(modelo_hits) / len(modelo_hits),
        "hit5_frecuencia": sum(freq_hits) / len(freq_hits),
        "hit5_aleatorio": sum(rand_hits) / len(rand_hits),
    }
    res["veredicto"] = {
        "C1": "FALSA" if res["hit5_modelo"] <= max(res["hit5_frecuencia"], res["hit5_aleatorio"]) else "ok",
        "C2": "FALSA" if res["hit5_modelo"] < 0.15 else "ok",
    }
    return res


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def run(corpus):
    t0 = time.time()
    if corpus == "enron":
        docs = cargar_enron()
        nombre = "enron (jeff.dasovich, trabajo)"
    elif corpus == "blog":
        autor, docs = seleccionar_autor_blog()
        nombre = f"blog ({autor}, personal/online)"
    else:
        raise SystemExit("corpus debe ser 'enron' o 'blog'")

    print(f"[{nombre}] documentos: {len(docs)}", flush=True)

    # ground truth de co-ocurrencia (Test B) y frecuencias
    par_gt, _ = co_ocurrencia_corpus(docs)
    docfrec = Counter()
    for _, texto in docs:
        for t in set(filtrar(tokenizar(texto))):
            docfrec[t] += 1
    terminos_frec = [t for t, _ in docfrec.most_common(TOP_FREC)]

    la = LaCaja(filtro_ontologico=INGLES)
    n = len(docs)
    serie = {}
    for i, (fecha, texto) in enumerate(docs):
        la.procesar_consulta(texto)
        if (i + 1) % OPTIMIZAR_CADA == 0:
            la.optimizar()
        for pct in (0.25, 0.50, 0.75):
            if abs((i + 1) / n - pct) < 0.005 and pct not in serie:
                serie[pct] = metricas(la, terminos_frec)
    serie[1.0] = metricas(la, terminos_frec)

    print(f"ingesta: {time.time()-t0:.1f}s", flush=True)
    a = test_a(la, terminos_frec, serie)
    b = test_b(la, par_gt, None, docs)
    print(f"tests A/B: {time.time()-t0:.1f}s", flush=True)
    c = test_c(docs)
    print(f"tests C: {time.time()-t0:.1f}s", flush=True)

    resultado = {
        "corpus": corpus,
        "nombre": nombre,
        "documentos": n,
        "test_a": a,
        "test_b": b,
        "test_c": c,
        "falsacion": {
            "A": a["veredicto"],
            "B": b.get("veredicto", {}),
            "C": c.get("veredicto", {}),
        },
    }
    salida = os.path.join(DATOS, f"resultado_{corpus}.json")
    with open(salida, "w", encoding="utf-8") as fh:
        json.dump(resultado, fh, ensure_ascii=False, indent=2)
    print(json.dumps(resultado["falsacion"], indent=2))
    print(f"guardado en {salida}")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "enron")