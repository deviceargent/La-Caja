"""Eval contra modelo: la memoria (primado) ayuda a un modelo a recuperar
los terminos que co-ocurren? (ver falsacion.md, pre-registro 18/8/2026).

Reusa EXACTA la construccion de memoria de test_c (mismo corpus, filtro,
F=3, 60% pasado) y muestrea consultas del 40% futuro. Modelo: GPT-4o-mini
(temperature 0, seed fija). S = 400 consultas por defecto.

Resiliencia: guarda parcial en JSONL despues de cada consulta; con
--resume retoma desde el parcial (no vuelve a gastar consultas ya
hechas). Una consulta que falla por limite de credito del proxy aborta
guardando el parcial.

Uso:
  python experiments/eval_modelo.py enron [--n 400] [--resume]
  python experiments/eval_modelo.py blog [--n 400] [--resume]
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

from la_caja import LaCaja  # noqa: E402

K = 5  # hit@K
MODELO = os.environ.get("EVAL_MODELO", "openai/gpt-4o-mini")
BASE_URL = os.environ.get("EVAL_BASE_URL", "https://openrouter.ai/api/v1")

if not os.environ.get("OPENAI_API_KEY"):
    raise SystemExit("falta OPENAI_API_KEY")

from openai import OpenAI  # noqa: E402

cliente = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=BASE_URL, max_retries=2, timeout=30)


class CreditError(Exception):
    """El proxy quedo sin creditos; abortar guardando lo hecho."""


def construir_memoria(docs, corte=0.60):
    """Idem test_c: 60% pasado, optimizar cada OPTIMIZAR_CADA."""
    n = len(docs)
    k = int(n * corte)
    la = LaCaja(filtro_ontologico=ex.INGLES, rehidratar=False)
    la.piscina.FACTOR_CONSOLIDACION = ex.FACTOR_CONSOLIDACION
    ultima_fecha = {}
    for i, (fecha, texto) in enumerate(docs[:k]):
        la.procesar_consulta(texto)
        for t in set(ex.filtrar(ex.tokenizar(texto))):
            if t in la.piscina.burbujas:
                ultima_fecha[t] = ex._parse_fecha(fecha)
        if (i + 1) % ex.OPTIMIZAR_CADA == 0:
            la.optimizar()
    return la, ultima_fecha, k


def muestrear_consultas(docs, la, ultima_fecha, k, s, seed):
    """S consultas del 40% futuro: (t, respuesta, gap). Solo t conocidos
    de docs con >= 2 conocidos (igual cobertura que test_c)."""
    rng = random.Random(seed)
    consultas = []
    for fecha, texto in docs[k:]:
        toks = list(dict.fromkeys(ex.filtrar(ex.tokenizar(texto))))
        conocidos = [t for t in toks if t in la.piscina.burbujas]
        if len(conocidos) < 2:
            continue
        for t in rng.sample(conocidos, min(2, len(conocidos))):
            respuesta = set(conocidos) - {t}
            if not respuesta:
                continue
            last = ultima_fecha.get(t)
            gap = (ex._parse_fecha(fecha) - last).days if last else None
            consultas.append({"t": t, "respuesta": sorted(respuesta), "gap": gap})
            if len(consultas) >= s:
                return consultas
    return consultas


def top_frec(la, n):
    from collections import Counter
    frec = Counter()
    for t in la.piscina.burbujas:
        frec[t] = la.piscina.burbujas[t].peso
    return [t for t, _ in frec.most_common(n)]


def pool_memoria(la, t, rng):
    """Primado (presupuesto 50) + 10 top-frecuencia + 10 aleatorios."""
    prim = list(la.contexto_primado(t, presupuesto=ex.PRESUPUESTO_PRIMADO))
    frec = top_frec(la, 10)
    aleat = [rng.choice(list(la.piscina.burbujas)) for _ in range(10)]
    pool = list(dict.fromkeys(prim + frec + aleat))
    return pool, prim


def pool_sin_memoria(la, rng):
    """30 top-frecuencia + 20 aleatorios (sin primado)."""
    frec = top_frec(la, 30)
    aleat = [rng.choice(list(la.piscina.burbujas)) for _ in range(20)]
    return list(dict.fromkeys(frec + aleat))


def _es_credito(e):
    s = str(e)
    return ("剩余积分不足" in s) or ("-14" in s and "403" in s) or ("insufficient" in s.lower() and "credit" in s.lower()) or ("402" in s) or ("quota" in s.lower())


def rerank(t, pool, pool_id):
    """Top-K del modelo sobre el pool (JSON). temp 0. Devuelve (ranked, ok).
    Fallas transitorias: reintentos; falla no-credito persistente: ok=False;
    falla de credito: CreditError."""
    sys_prompt = (
        "Eres un evaluador de recuperacion de memoria. Dado un termino "
        "foco y una lista de terminos candidatos, ordena los MAS "
        "probables de co-ocurrir con el termino foco en el mismo "
        "documento. Devuelve JSON: {\"ranked\": [\"t1\", \"t2\", ...]} "
        "con hasta 20 terminos, en orden de probabilidad."
    )
    user = json.dumps({"foco": t, "candidatos": pool}, ensure_ascii=False)
    for intento in range(3):
        try:
            r = cliente.chat.completions.create(
                model=MODELO,
                temperature=0,
                max_tokens=300,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
            )
            datos = json.loads(r.choices[0].message.content or "{}")
            ranked = [str(x) for x in datos.get("ranked", [])]
            ranked = [x for x in ranked if x in set(pool)][:K]
            return ranked, True
        except Exception as e:
            if _es_credito(e):
                raise CreditError(f"{pool_id}: {e}")
            if intento == 2:
                print(f"  [falla no-credito {pool_id}] {e}", flush=True)
                return [], False
            time.sleep(2 ** intento)


def hit(ranked, respuesta):
    if not ranked:
        return 0.0
    n = len(respuesta)
    return len(set(ranked) & set(respuesta)) / n


def run(corpus, s):
    t0 = time.time()
    if corpus == "enron":
        docs = ex.cargar_enron()
    elif corpus == "blog":
        _, docs = ex.seleccionar_autor_blog()
    else:
        raise SystemExit("corpus: enron | blog")

    la, ultima_fecha, k = construir_memoria(docs)
    print(f"[{corpus}] docs {len(docs)}, memoria sobre {k}, {time.time()-t0:.1f}s", flush=True)

    consultas = muestrear_consultas(docs, la, ultima_fecha, k, s, seed=13)
    print(f"consultas: {len(consultas)}", flush=True)

    frec_global = top_frec(la, 10 ** 6)
    th = int(os.environ.get("EVAL_THREADS", "8"))
    parcial = os.path.join(ROOT, "experiments", "results", f"eval_modelo_{corpus}_partial.jsonl")

    slots = [None] * len(consultas)
    if "--resume" in sys.argv and os.path.exists(parcial):
        for line in open(parcial, encoding="utf-8"):
            line = line.strip()
            if line:
                d = json.loads(line)
                if d.get("ok"):
                    slots[d["i"]] = d
        print(f"[resume] {sum(1 for s in slots if s)} consultas validas ya registradas; las fallidas se reintentan", flush=True)

    pendientes = [i for i in range(len(consultas)) if slots[i] is None]

    def procesar(i):
        c = consultas[i]
        t, respuesta = c["t"], set(c["respuesta"])
        rng = random.Random(i * 7919 + 23)  # por-consulta, determinista y thread-safe
        pool, prim = pool_memoria(la, t, rng)
        mm, ok_mm = rerank(t, pool, f"con-memoria-{i}")
        sm, ok_sm = rerank(t, pool_sin_memoria(la, rng), f"sin-memoria-{i}")
        mo = prim[:K]
        fr = frec_global[:K]
        al = [rng.choice(list(la.piscina.burbujas)) for _ in range(K)]
        r = {"i": i, "t": t, "gap": c["gap"], "ok": ok_mm and ok_sm}
        for clave, ranked in (("modelo+memoria", mm), ("modelo_sin_memoria", sm), ("memoria_alone", mo), ("frecuencia", fr), ("aleatorio", al)):
            r[clave] = hit(ranked, respuesta)
        r["hit1_mm"] = 1.0 if mm and mm[0] in respuesta else 0.0
        r["hit1_sm"] = 1.0 if sm and sm[0] in respuesta else 0.0
        r["techo"] = len(set(pool) & respuesta) / len(respuesta)
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
                print(f"[parcial guardado en {parcial}] {sum(1 for s2 in slots if s2)} consultas", flush=True)
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

    hits = {clave: [s[clave] for s in ok] for clave in ("modelo+memoria", "modelo_sin_memoria", "memoria_alone", "frecuencia", "aleatorio")}
    h1 = {"modelo+memoria": [s["hit1_mm"] for s in ok], "modelo_sin_memoria": [s["hit1_sm"] for s in ok]}
    techo_pool = [s["techo"] for s in ok]
    gaps = [s["gap"] for s in ok]

    res = {clave: sum(v) / n for clave, v in hits.items()}
    res["hit@1"] = {clave: sum(v) / n for clave, v in h1.items()}
    res["techo_pool"] = sum(techo_pool) / n
    res["n"] = n
    res["fallidas"] = len(fallidas)
    res["modelo"] = MODELO

    def mayor(a, b):
        return sum(1 for x, y in zip(hits[a], hits[b]) if x > y), sum(1 for x, y in zip(hits[a], hits[b]) if x < y)

    res["victorias_emparejadas"] = {
        "modelo+memoria > modelo_sin_memoria": mayor("modelo+memoria", "modelo_sin_memoria"),
        "modelo+memoria > memoria_alone": mayor("modelo+memoria", "memoria_alone"),
        "modelo+memoria > frecuencia": mayor("modelo+memoria", "frecuencia"),
    }
    res["veredicto"] = {
        "V1_modelo_sobre_memoria": "ok" if res["modelo+memoria"] > res["memoria_alone"] else "FALSA",
        "V2_memoria_ayuda_al_modelo": "ok" if res["modelo+memoria"] > res["modelo_sin_memoria"] else "FALSA",
        "V3_vence_a_frecuencia": "ok" if res["modelo+memoria"] > res["frecuencia"] else "FALSA",
    }
    gaps_validos = [g for g in gaps if g is not None]
    res["gaps_dias"] = {"media": sum(gaps_validos) / max(1, len(gaps_validos)), "sin_gap": gaps.count(None)}

    salida = os.path.join(ROOT, "experiments", "results", f"eval_modelo_{corpus}.json")
    with open(salida, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=2)
    print(json.dumps({"hit@5": {k: round(v, 4) for k, v in res.items() if k in hits}, "hit@1": res["hit@1"], "techo": round(res["techo_pool"], 4), "n": n, "fallidas": len(fallidas), "veredicto": res["veredicto"]}, indent=2))
    print(f"guardado en {salida}")


if __name__ == "__main__":
    n = 400
    if "--n" in sys.argv:
        i = sys.argv.index("--n")
        n = int(sys.argv[i + 1])
        del sys.argv[i:i + 2]
    run(sys.argv[1] if len(sys.argv) > 1 else "enron", n)