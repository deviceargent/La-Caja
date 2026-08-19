# La Caja — writeup

Estado: **esqueleto**. Las secciones marcadas `[PENDIENTE]` son prosa
por redactar; los números son los ya medidos y verificados en
`experiments/results/` y `experiments/falsacion.md`. Este archivo es la
fuente del futuro artículo/blog; el README del repo es su forma corta.

---

## 1. Título (PENDIENTE)

> Propuesta: *"La Caja: una memoria contextual asociativa falsable para
> agentes"* — con subtítulo honesto sobre los límites medidos.

## 2. Resumen

[PENDIENTE — bosquejo:]

> La Caja es una memoria contextual asociativa para modelos de lenguaje:
> lo que el modelo observó en su vida, con olvido, discriminación entre
> recuerdo e inferencia, y primado de contexto. A diferencia de los
> sistemas de memoria actuales (véctores, RAG), La Caja es una
> arquitectura *falsable*: cada mecanismo tiene un criterio pre-registrado
> y un experimento que puede refutarlo. Reportamos una falsación empírica
> sobre dos corpus orgánicos de registro opuesto (Enron laboral y Blog
> doméstico), una validación de la capa de rehidratación sobre temas
> dormidos, y dos evaluaciones de la hipótesis de que un modelo de
> lenguaje amplifica la memoria. Veredictos: la memoria cumple sus
> criterios mecánicos (C1/C2), la rehidratación mejora la recuperación en
> el rango 1-6 meses (+41%), pero la hipótesis de amplificación por modelo
> queda falsada en las tareas de cloze evaluadas: la frecuencia gana a la
> memoria y al modelo. La contribución no es una memoria "mejor" que la
> frecuencia, sino un sistema de memoria con límites medidos y honestos, y
> un protocolo de acceso agente-agente-humano listo para ser usado.

## 3. Introducción

### 3.1 El problema

Los agentes (LLMs) no tienen estado propio de lo que observaron. El
contexto inyectado en cada llamada es efímero; el agente no distingue lo
que vio de lo que infirió; y olvidar no es una capacidad, es un error.
[PENDIENTE — desarrollo.]

### 3.2 La apuesta

Una memoria *asociativa*: no guardar textos (como RAG) sino el *tejido de
co-ocurrencias* entre términos, con tres propiedades: multi-pertenencia
(una palabra en varios contextos), discriminación observado/inferido, y
olvido con primado de contexto. [PENDIENTE.]

### 3.3 La postura metodológica

Cada mecanismo es falsable: hay un criterio pre-registrado y un
experimento que puede refutarlo. La falsación es una afirmación mecánica
(qué hace la memoria), no de utilidad aguas abajo. [PENDIENTE.]

## 4. Método

### 4.1 Arquitectura (spec v2.0/v2.1, `docs/`)

- **Nodos compartidos**: los conceptos (burbujas) viven en nodos; un
  término participa en varios contextos (multi-pertenencia).
- **Confianza**: navegación distingue lo co-ocurrido (1.0) del cierre
  transitivo (`0.5^puentes`); compartir un término en consultas distintas
  NO conecta.
- **Olvido**: decaimiento por consolidación; el primado de contexto
  resucita temas dormidos (recuperación temporal).
- **Persistencia event-sourced** (opt-in): `PiscinaPersistente` registra
  cada mutación; snapshot replayable reconstruye el estado byte-idéntico.

### 4.2 Capa de traza dormida (v0.7)

Cuando una asociación muere por olvido, no se borra: se captura como
traza inerte (partner, fuerza pico, último evento). La traza no participa
en navegación ni primado. Rehidratación opt-in: al re-observar una pareja
trazada, la relación se restaura en la capa viva. Rol honesto pre-registrado:
inercia + clave de rehidratación por re-observación — NO predictor del
contenido futuro (ver §6.2).

### 4.3 Protocolo de acceso (repo B, `la-caja-mcp`)

Herramientas MCP de memoria (`procesar_consulta`, `declarar_relacion`,
`consultar`, `contexto_primado`, `historial`, `stats`) y un protocolo de
debate agente-agente-humano (claims, interferencia, rondas con deadline,
adjudicación) determinista y replayable. Transportes stdio (local) y
streamable HTTP (remoto, + push SSE).

## 5. Falsación (pre-registrada)

### 5.1 Criterios

| Test | Qué refuta |
|------|-----------|
| A. discriminación | la memoria densifica (todo conecta con todo) |
| B. fidelidad al corpus | la memoria inventa puentes que el corpus no sostiene |
| C. recuperación temporal | el primado no resucita temas dormidos |

Corpus: Enron (laboral, ~3.8 años) y Blog (doméstico). Memoria siempre
sobre el 60% pasado; evaluación sobre el 40% futuro (nunca ingerido).

### 5.2 Resultados canónicos (F=3)

| Test | Enron | Blog |
|------|-------|------|
| A1-A3 | ok | **A1 FALSA**, A2/A3 ok |
| B1-B3 | ok | **B1 FALSA**, B2/B3 ok |
| C1 | ok (2.2×) | ok |
| C2 | ok (64% techo) | ok (70% techo) |

Enron pasa todo. Blog refuta A1 y B1 con causa documentada: el cierre
transitivo del núcleo sostenido de 500 términos conecta pares ajenos y el
`optimize` colapsa la multi-pertenencia. La refutación parcial es parte
del método, no un fallo: la memoria se comporta distinto según el registro.

### 5.3 Límite honesto de la recuperación

El primado NO recupera temas dormidos ≥ 1 mes en Enron (techo ≤ 0.006 sin
señal). La memoria viva es una memoria de corto plazo con primado, no una
memoria de largo plazo.

## 6. Validaciones posteriores

### 6.1 Rehidratación (Enron, `resultado_enron_rehidratar.json`)

Con rehidratación opt-in sobre el 60% pasado: `hit5_modelo` 0.064 → 0.070
(+10%), rango 1-6m 0.0058 → 0.0082 (**+41%**), techo 0.100 → 0.126. C2
baja 0.64 → 0.56 (coste de revivir aristas). Sin regresión en B. Blog
(`resultado_blog_rehidratar.json`): nulo (0.08502 → 0.08497) — mecanismo
evento-denso, corpus demasiado escaso.

### 6.2 ¿La traza predice el futuro? (eval de dormidos, `eval_dormidos_enron.json`)

Pregunta: cuando un tema dormido reaparece, ¿su traza (partners olvidados)
contiene la co-ocurrencia futura? 400 consultas con historial no vacío, 0
fallidas.

| Condición | hit@5 |
|---|---|
| frecuencia | **0.102** |
| memoria_alone_viva (primado) | 0.045 |
| modelo_sin_memoria | 0.040 |
| modelo+traza | 0.019 |
| memoria_alone_traza (historial) | 0.013 |
| techo_hist | 0.030 |
| techo_pool | 0.185 |

**Veredicto: V1-V4 FALSA.** `techo_hist` 0.030: los partners olvidados
aparecen en ~3% del contenido de la respuesta. La traza es inercia +
clave de rehidratación, NO señal predictiva. Esto delimita el rol honesto
de la capa dormida y no contradice §6.1: la rehidratación actúa sobre la
re-observación real, no sobre la predicción.

### 6.3 ¿El modelo amplifica la memoria? (eval contra modelo, `eval_modelo_enron.json`)

Pregunta: un LLM re-ordenando la memoria mejora la recuperación sobre la
frecuencia (cloze, hit@5 emparejado, gpt-4o-mini vía OpenRouter, 400
consultas, 0 fallidas).

| Condición | hit@5 | hit@1 |
|---|---|---|
| frecuencia | 0.102 | — |
| memoria_alone (primado) | 0.045 | — |
| modelo_sin_memoria | 0.041 | 0.49 |
| modelo+memoria | 0.027 | 0.28 |
| techo | 0.204 | — |

**Veredicto: V1-V3 FALSA** (victorias emparejadas 60/204, 84/152, 16/339).
En cloze co-ocurrencial, la frecuencia es el ground truth más fuerte; el
modelo *resta* a la memoria, no la amplifica. No falsifica la memoria
(C1/C2 ok) — falsifica la hipótesis de amplificación.

## 7. Límites honestos

1. La memoria NO supera a la frecuencia en las tareas de co-ocurrencia
   evaluadas (Enron, cloze). Su valor medido está en sus criterios
   mecánicos (C), la rehidratación por re-observación (1-6m), y la
   discriminación recuerdo/inferencia.
2. No hay aún uso real: los evals son de laboratorio. El caso de uso real
   (dos agentes compartiendo memoria y debatiendo por MCP) está
   [PENDIENTE — ver §8].
3. Blog refutó A1/B1: la arquitectura depende del registro.
4. Los evals de modelo usaron un solo LLM (gpt-4o-mini) y un solo corpus
   (Enron); generalizar es trabajo futuro.

## 8. Trabajo futuro

- **Caso de uso real (PENDIENTE):** dos agentes consumiendo la memoria y
  el protocolo de debate por MCP (repo B) contra un worker compartido.
  Objetivo medible: si el primado de la memoria cambia cómo un agente
  interfiere un claim, y si el consenso emerge más rápido con memoria
  compartida que sin ella.
- **Publicación y empaquetado:** publicar `la-caja` y `la-caja-mcp` a
  PyPI (workflow listo en `.github/workflows/pypi.yml`; falta taguear y
  vincular el trusted publishing en PyPI).
- **Generalización del eval de modelo:** más LLMs, más corpus, tareas no
  co-ocurrenciales (p.ej. anáfora, planificación con contexto).

## 9. Reproducibilidad

- `pip install .` en repo A; `pip install .[dev]` en repo B.
- `python experiments/exp_memoria.py enron|blog` (ver falsacion.md).
- `python experiments/eval_modelo.py` y `python experiments/eval_dormidos.py`
  (requieren `OPENAI_API_KEY`; ver `falsacion.md` para la infra usada).
- Suite A: 53 tests de determinismo y propiedades; suite B: 29 tests
  (protocolo + integración MCP real).
- Replay byte-idéntico garantizado por la persistencia event-sourced.