"""Eval de temas dormidos: donde la frecuencia no puede ganar, la traza
dormida (historial) es senal real, y un modelo + traza puede superar al
modelo sin memoria y a la frecuencia (ver falsacion.md, pre-registro
19/8/2026).

Reusa la construccion de memoria de test_c (Enron, filtro, F=3, 60%
pasado, rehidratar=False) y consultas del 40% futuro donde el termino
tiene historial NO vacio. Modelo: openai/gpt-4o-mini via OpenRouter,
temp 0, JSON mode. S = 400 por defecto.

Uso:
  python experiments/eval_dormidos.py [--n 400] [--resume]
Env: OPENAI_API_KEY, EVAL_BASE_URL, EVAL_MODELO, EVAL_THREADS.
"""
import json
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import exp_memoria as ex  # noqa: E402
from eval_modelo import construir_memoria, top_frec, hit, rerank, CreditError  # noqa: E402

K = 5
HIST_TOP = 15
MODELO = os.environ.get("EVAL_MODELO", "openai/gpt-4o-mini")
BASE_URL = os.environ.get("EVAL_BASE_URL", "https://openrouter.ai/api/v1")

if not os.environ.get("OPENAI_API_KEY"):
    raise SystemExit("falta OPENAI_API_KEY")

from openai import OpenAI  # noqa: E402

cliente = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=BASE_URL, max_retries=2, timeout=30)


def muestrear_dormidos(docs, la, ultima_fecha, k, s, seed):
    """Hasta 2 terminos por doc futuro con historial(t) NO vacio."""
    rng = random.Random(seed)
    consultas = []
    for fecha, texto in docs[k:]:
        toks = list(dict.fromkeys(ex.filtrar(ex.tokenizar(texto))))
        conocidos = [t for t in toks if t in la.piscina.burbujas]
        if len(conocidos) < 2:
            continue
        candidatos = [t for t in conocidos if la.historial(t)]
        if not candidatos:
            continue
        for t in rng.sample(candidatos, min(2, len(candidatos))):
            respuesta = set(conocidos) - {t}
            if not respuesta:
                continue
            last = ultima_fecha.get(t)
            gap = (ex._parse_fecha(fecha) - last).days if last else None
            consultas.append({"t": t, "respuesta": sorted(respuesta), "gap": gap})
            if len(consultas) >= s:
                return consultas
    return consultas


def partners_historial(la, t):
    return [d["partner"] for d in la.historial(t)][:HIST_TOP]


def pool_traza(la, t, rng):
    hist = partners_historial(la, t)
    prim = list(la.contexto_primado(t, presupuesto=ex.PRESUPUESTO_PRIMADO))[:10]
    frec = top_frec(la, 10)
    aleat = [rng.choice(list(la.piscina.burbujas)) for _ in range(10)]
    return list(dict.fromkeys(hist + prim + frec + aleat)), hist


def pool_sin_memoria(la, rng):
    frec = top_frec(la, 30)
    aleat = [rng.choice(list(la.piscina.burbujas)) for _ in range(20)]
    return list(dict.fromkeys(frec + aleat))


def run(s):
    t0 = time.time()
    docs = ex.cargar_enron()
    la, ultima_fecha, k = construir_memoria(docs)
    print(f"[enron] docs {len(docs)}, memoria sobre {k}, {time.time()-t0:.1f}s", flush=True)

    consultas = muestrear_dormidos(docs, la, ultima_fecha, k, s, seed=13)
    print(f"consultas (termino con historial): {len(consultas)}", flush=True)
    if not consultas:
        raise SystemExit("sin consultas con historial")

    frec_global = top_frec(la, 10 ** 6)
    th = int(os.environ.get("EVAL_THREADS", "4"))
    parcial = os.path.join(ROOT, "experiments", "results", "eval_dormidos_enron_partial.jsonl")

    slots = [None] * len(consultas)
    if "--resume" in sys.argv and os.path.exists(parcial):
        for line in open(parcial, encoding="utf-8"):
            line = line.strip()
            if line:
                d = json.loads(line)
                if d.get("ok"):
                    slots[d["i"]] = d
        print(f"[resume] {sum(1 for s2 in slots if s2)} validas; fallidas se reintentan", flush=True)
    pendientes = [i for i in range(len(consultas)) if slots[i] is None]

    def procesar(i):
        c = consultas[i]
        t, respuesta = c["t"], set(c["respuesta"])
        rng = random.Random(i * 7919 + 23)
        pool, hist = pool_traza(la, t, rng)
        mm, ok_mm = rerank(t, pool, f"traza-{i}")
        sm, ok_sm = rerank(t, pool_sin_memoria(la, rng), f"sin-{i}")
        prim = list(la.contexto_primado(t, presupuesto=ex.PRESUPUESTO_PRIMADO))
        r = {"i": i, "t": t, "gap": c["gap"], "ok": ok_mm and ok_sm}
        r["modelo+traza"] = hit(mm, respuesta)
        r["modelo_sin_memoria"] = hit(sm, respuesta)
        r["hit1_traza"] = 1.0 if mm and mm[0] in respuesta else 0.0
        r["hit1_sin"] = 1.0 if sm and sm[0] in respuesta else 0.0
        r["memoria_alone_traza"] = hit(list(dict.fromkeys(hist + prim))[:K], respuesta)
        r["memoria_alone_viva"] = hit(prim[:K], respuesta)
        r["frecuencia"] = hit(frec_global[:K], respuesta)
        r["aleatorio"] = hit([rng.choice(list(la.piscina.burbujas)) for _ in range(K)], respuesta)
        r["techo_hist"] = hit(hist, respuesta)
        r["techo_pool"] = hit(pool, respuesta)
        return r

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def guardar():
        with open(parcial, "w", encoding="utf-8") as fh:
            for s2 in slots:
                if s2 is not None:
                    fh.write(json.dumps(s2, ensure_ascii=False) + "\n")

    n_hechos = sum(1 for s2 in slots if s2 is not None)
    with ThreadPoolExecutor(max_workers=th) as executor:
        futuros = {executor.submit(procesar, i): i for i in pendientes}
        for fut in as_completed(futuros):
            i = futuros[fut]
            try:
                slots[i] = fut.result()
            except CreditError as e:
                guardar()
                print(f"[creditos agotados en consulta {i}] {e}", flush=True)
                print(f"[parcial guardado] {sum(1 for s2 in slots if s2)} consultas", flush=True)
                sys.exit(2)
            guardar()
            n_hechos += 1
            if n_hechos % 25 == 0:
                print(f"  {n_hechos}/{len(consultas)} ({time.time()-t0:.1f}s)", flush=True)

    ok = [s for s in slots if s is not None and s["ok"]]
    fallidas = [s for s in slots if s is not None and not s["ok"]]
    if not ok:
        raise SystemExit("sin consultas validas")
    n = len(ok)

    claves = ("modelo+traza", "modelo_sin_memoria", "memoria_alone_traza", "memoria_alone_viva", "frecuencia", "aleatorio")
    vals = {c: [s[c] for s in ok] for c in claves}
    res = {c: sum(v) / n for c, v in vals.items()}
    res["hit@1"] = {"modelo+traza": sum(s["hit1_traza"] for s in ok) / n,
                    "modelo_sin_memoria": sum(s["hit1_sin"] for s in ok) / n}
    res["techo_hist"] = sum(s["techo_hist"] for s in ok) / n
    res["techo_pool"] = sum(s["techo_pool"] for s in ok) / n
    res["n"] = n
    res["fallidas"] = len(fallidas)
    res["modelo"] = MODELO

    def mayor(a, b):
        return (sum(1 for x, y in zip(vals[a], vals[b]) if x > y), sum(1 for x, y in zip(vals[a], vals[b]) if x < y))

    res["victorias_emparejadas"] = {
        "modelo+traza > modelo_sin_memoria": mayor("modelo+traza", "modelo_sin_memoria"),
        "modelo+traza > memoria_alone_traza": mayor("modelo+traza", "memoria_alone_traza"),
        "modelo+traza > frecuencia": mayor("modelo+traza", "frecuencia"),
        "memoria_alone_traza > frecuencia": mayor("memoria_alone_traza", "frecuencia"),
        "memoria_alone_traza > memoria_alone_viva": mayor("memoria_alone_traza", "memoria_alone_viva"),
    }
    res["veredicto"] = {
        "V1_traza_senal": "ok" if res["memoria_alone_traza"] > res["frecuencia"] else "FALSA",
        "V2_traza_sobre_viva": "ok" if res["memoria_alone_traza"] > res["memoria_alone_viva"] else "FALSA",
        "V3_modelo_amplifica": "ok" if (res["modelo+traza"] > res["memoria_alone_traza"] and res["modelo+traza"] > res["modelo_sin_memoria"]) else "FALSA",
        "V4_vence_a_frecuencia": "ok" if res["modelo+traza"] > res["frecuencia"] else "FALSA",
    }
    gaps = [s["gap"] for s in ok if s["gap"] is not None]
    res["gaps_dias"] = {"media": sum(gaps) / max(1, len(gaps)), "sin_gap": sum(1 for s in ok if s["gap"] is None)}

    salida = os.path.join(ROOT, "experiments", "results", "eval_dormidos_enron.json")
    with open(salida, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=2)
    print(json.dumps({**{k: round(v, 4) for k, v in res.items() if k in claves},
                      "hit@1": res["hit@1"], "techo_hist": round(res["techo_hist"], 4),
                      "techo_pool": round(res["techo_pool"], 4), "n": n, "fallidas": len(fallidas),
                      "veredicto": res["veredicto"]}, indent=2))
    print(f"guardado en {salida}")


if __name__ == "__main__":
    n = 400
    if "--n" in sys.argv:
        i = sys.argv.index("--n")
        n = int(sys.argv[i + 1])
        del sys.argv[i:i + 2]
    run(n)