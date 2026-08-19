"""Benchmark pareado con/sin La Caja — la tesis central (pre-registrado en
falsacion.md, 19/8/2026).

LA prueba: el mismo modelo, en dos corridas (una con La Caja como soporte
de memoria, otra sin), responde preguntas de recall; se mide cuanto del
vocabulario REAL del corpus recupera cada respuesta. Es la validacion de
la tesis: "La Caja como memoria mejora al modelo que la usa".

ENMIENDA DE DISENO (19/8, del smoke test de 12 consultas): el judge de
preferencia tiene un sesgo de formato dominante — prefiere listas
genericas y coherentes (Estrategia, Compliance, Collaboration) sobre los
terminos crudos REALES del corpus que inyecta La Caja (pm, fyi,
metering, baseload). El judge no mide memoria, mide estetica de lista.
Por eso la metrica PRIMARIA es la coincidencia objetiva contra el ground
truth de cada consulta (los terminos que co-aparecen en el doc futuro):
recall = |respuesta ∩ tokens(respuesta_modelo)| / |respuesta|. El
veredicto del judge se reporta como secundario, con su sesgo documentado.

Diseno (reusa construccion de test_c / eval_modelo): corpus Enron,
memoria sobre el 60% pasado (rehidratar=False, F=3), consultas del 40%
futuro. Por consulta:
- Con La Caja: pregunta + contexto_primado de los terminos conocidos.
- Sin La Caja: la misma pregunta sin soporte.

Metricas primarias (objetivas, contra ground truth):
- recall_con / recall_sin por consulta (fraccion de terminos reales).
- gana_con / gana_sin / empate (pares estrictos).
- win_rate = gana_con / consultas.
- p_binominal (test de signo, H0 p=0.5 sobre pares sin empate).

Metricas secundarias (judge ciego de preferencia, sesgo documentado):
- judge_gana_memoria / judge_gana_sin / judge_empate.

Veredicto OK si win_rate > 0.5 y p < 0.05 (metrica objetiva). FALSA en
caso contrario. Se reporta todo, cualquiera sea el resultado.

Uso:
  python experiments/eval_pareado_memoria.py [--n 400] [--resume]
Env: OPENAI_API_KEY, EVAL_BASE_URL, EVAL_MODELO, EVAL_THREADS.
"""
import json
import math
import os
import random
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from eval_modelo import construir_memoria, muestrear_consultas, CreditError  # noqa: E402
import exp_memoria as ex  # noqa: E402

MODELO = os.environ.get("EVAL_MODELO", "openai/gpt-4o-mini")
BASE_URL = os.environ.get("EVAL_BASE_URL", "https://openrouter.ai/api/v1")

if not os.environ.get("OPENAI_API_KEY"):
    raise SystemExit("falta OPENAI_API_KEY")

from openai import OpenAI  # noqa: E402

cliente = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=BASE_URL, max_retries=2, timeout=30)

_TOKEN = re.compile(r"[a-z][a-z\-]*")


def _pregunta(t):
    return (
        f"In this company's internal documents, if the term '{t}' appears, "
        f"which other terms from the corporate vocabulary are most likely to "
        f"co-occur with it in the same document? Answer with a short list of "
        f"terms (up to 10)."
    )


def _tokens(texto):
    return set(_TOKEN.findall(texto.lower()))


def _recall(respuesta, texto):
    if not respuesta:
        return 0.0
    return len(set(respuesta) & _tokens(texto)) / len(respuesta)


def _responder(t, primado, con_memoria):
    """Respuesta del modelo con o sin soporte de memoria. temp 0."""
    sys_prompt = (
        "Eres un agente corporativo que recupera vocabulario de documentos "
        "internos de una empresa. Responde con una lista breve de terminos, "
        "sin rodeos."
    )
    mensajes = [{"role": "system", "content": sys_prompt}]
    if con_memoria:
        ctx = ", ".join(primado[:15])
        mensajes.append({
            "role": "user",
            "content": (
                f"Memoria asociativa de La Caja (terminos que co-aparecieron "
                f"con '{t}' en el pasado): [{ctx}].\n\n" + _pregunta(t)
            ),
        })
    else:
        mensajes.append({"role": "user", "content": _pregunta(t)})
    for intento in range(3):
        try:
            r = cliente.chat.completions.create(
                model=MODELO,
                temperature=0,
                max_tokens=150,
                messages=mensajes,
            )
            return (r.choices[0].message.content or "").strip()
        except Exception as e:
            if _es_credito(e):
                raise CreditError(f"resp-{t}")
            if intento == 2:
                return None
            time.sleep(2 ** intento)
    return None


def _juzgar(t, r_con, r_sin, con_izq):
    """Judge ciego: decide cual respuesta tiene mejor recall. Devuelve
    'con'/'sin'/'empate' respecto a la memoria, sin importar el lado."""
    sys_prompt = (
        "Eres un evaluador imparcial de recuperacion de memoria. Dada una "
        "pregunta y dos respuestas (A y B), decide cual demuestra MEJOR "
        "recall del vocabulario corporativo de la empresa: mas terminos "
        "especificos y relevantes, coherentes entre si. Responde SOLO con "
        "JSON: {\"ganador\": \"A\" | \"B\" | \"empate\"}."
    )
    user = (
        f"Pregunta: {_pregunta(t)}\n\n"
        f"Respuesta A: {r_con if con_izq else r_sin}\n\n"
        f"Respuesta B: {r_sin if con_izq else r_con}"
    )
    for intento in range(3):
        try:
            r = cliente.chat.completions.create(
                model=MODELO,
                temperature=0,
                max_tokens=80,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
            )
            datos = json.loads(r.choices[0].message.content or "{}")
            ganador = datos.get("ganador", "empate")
            if con_izq:
                return {"A": "con", "B": "sin", "empate": "empate"}.get(ganador, "empate")
            return {"A": "sin", "B": "con", "empate": "empate"}.get(ganador, "empate")
        except Exception as e:
            if _es_credito(e):
                raise CreditError(f"judge-{t}")
            if intento == 2:
                return None
            time.sleep(2 ** intento)
    return None


def _es_credito(e):
    s = str(e)
    return ("剩余积分不足" in s) or ("-14" in s and "403" in s) or ("insufficient" in s.lower() and "credit" in s.lower()) or ("402" in s) or ("quota" in s.lower())


def p_binominal(k, n):
    """P-value bilateral del test de signo (H0: p=0.5)."""
    if n == 0:
        return 1.0
    # suma de colas: P(X>=max(k,n-k)) * 2 (aprox; n pequeno exacto)
    m = max(k, n - k)
    acum = 0.0
    for x in range(m, n + 1):
        c = math.comb(n, x)
        acum += c * (0.5 ** n)
    return min(1.0, 2.0 * acum)


def run(s):
    t0 = time.time()
    docs = ex.cargar_enron()
    la, ultima_fecha, k = construir_memoria(docs)
    print(f"[enron] docs {len(docs)}, memoria sobre {k}, {time.time()-t0:.1f}s", flush=True)

    consultas = muestrear_consultas(docs, la, ultima_fecha, k, s, seed=13)
    print(f"consultas: {len(consultas)}", flush=True)

    th = int(os.environ.get("EVAL_THREADS", "8"))
    parcial = os.path.join(ROOT, "experiments", "results", "eval_pareado_memoria_enron_partial.jsonl")

    slots = [None] * len(consultas)
    if "--resume" in sys.argv and os.path.exists(parcial):
        for line in open(parcial, encoding="utf-8"):
            line = line.strip()
            if line:
                d = json.loads(line)
                if d.get("ok"):
                    slots[d["i"]] = d
        print(f"[resume] {sum(1 for x in slots if x)} validas; fallidas se reintentan", flush=True)
    pendientes = [i for i in range(len(consultas)) if slots[i] is None]

    def procesar(i):
        c = consultas[i]
        t = c["t"]
        respuesta = set(c["respuesta"])
        rng = random.Random(i * 7919 + 23)
        primado = list(la.contexto_primado(t, presupuesto=ex.PRESUPUESTO_PRIMADO))
        r_con = _responder(t, primado, True)
        r_sin = _responder(t, primado, False)
        if r_con is None or r_sin is None:
            return {"i": i, "t": t, "ok": False}
        con_izq = rng.random() < 0.5
        v = _juzgar(t, r_con, r_sin, con_izq)
        if v is None:
            return {"i": i, "t": t, "ok": False}
        return {
            "i": i,
            "t": t,
            "gap": c["gap"],
            "ok": True,
            "veredicto": v,
            "recall_con": _recall(respuesta, r_con),
            "recall_sin": _recall(respuesta, r_sin),
            "respuesta": sorted(respuesta),
            "r_con": r_con,
            "r_sin": r_sin,
        }

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def guardar():
        with open(parcial, "w", encoding="utf-8") as fh:
            for x in slots:
                if x is not None:
                    fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    n_hechos = sum(1 for x in slots if x is not None)
    with ThreadPoolExecutor(max_workers=th) as executor:
        futuros = {executor.submit(procesar, i): i for i in pendientes}
        for fut in as_completed(futuros):
            i = futuros[fut]
            try:
                slots[i] = fut.result()
            except CreditError as e:
                guardar()
                print(f"[creditos agotados en consulta {i}] {e}", flush=True)
                print(f"[parcial guardado] {sum(1 for x in slots if x)} consultas", flush=True)
                sys.exit(2)
            guardar()
            n_hechos += 1
            if n_hechos % 25 == 0:
                print(f"  {n_hechos}/{len(consultas)} ({time.time()-t0:.1f}s)", flush=True)

    ok = [x for x in slots if x is not None and x["ok"]]
    fallidas = [x for x in slots if x is not None and not x["ok"]]
    if not ok:
        raise SystemExit("sin consultas validas")
    n = len(ok)

    # Metrica primaria: recall objetivo contra el ground truth de la consulta.
    gana_con = sum(1 for x in ok if x["recall_con"] > x["recall_sin"])
    gana_sin = sum(1 for x in ok if x["recall_con"] < x["recall_sin"])
    empate_obj = sum(1 for x in ok if x["recall_con"] == x["recall_sin"])
    win_rate = gana_con / n
    p = p_binominal(gana_con, n - empate_obj) if n > empate_obj else 1.0
    recall_medio_con = sum(x["recall_con"] for x in ok) / n
    recall_medio_sin = sum(x["recall_sin"] for x in ok) / n

    # Metrica secundaria: judge de preferencia (sesgo de formato documentado).
    j_con = sum(1 for x in ok if x["veredicto"] == "con")
    j_sin = sum(1 for x in ok if x["veredicto"] == "sin")
    j_emp = sum(1 for x in ok if x["veredicto"] == "empate")

    veredicto = "OK" if (win_rate > 0.5 and p < 0.05) else "FALSA"

    res = {
        "n": n,
        "fallidas": len(fallidas),
        "recall_medio_con": recall_medio_con,
        "recall_medio_sin": recall_medio_sin,
        "gana_con": gana_con,
        "gana_sin": gana_sin,
        "empate": empate_obj,
        "win_rate": win_rate,
        "p_binominal": p,
        "judge": {"gana_memoria": j_con, "gana_sin": j_sin, "empate": j_emp},
        "veredicto": veredicto,
        "modelo": MODELO,
    }
    salida = os.path.join(ROOT, "experiments", "results", "eval_pareado_memoria_enron.json")
    with open(salida, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=2)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    print(f"guardado en {salida}")


if __name__ == "__main__":
    n = 400
    if "--n" in sys.argv:
        i = sys.argv.index("--n")
        n = int(sys.argv[i + 1])
        del sys.argv[i:i + 2]
    run(n)