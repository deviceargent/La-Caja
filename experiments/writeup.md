# La Caja — writeup

Estado: **final** (19/8/2026). Todos los números verificados en
`experiments/results/` y `experiments/falsacion.md`. Este archivo es la
fuente del artículo/blog; el README del repo es su forma corta.

---

## 1. Título

*La Caja: una memoria contextual asociativa falsable para agentes — con
límites medidos y una tesis validada.*

## 2. Resumen

La Caja es una memoria contextual asociativa para modelos de lenguaje:
lo que el modelo observó en su vida, con olvido, discriminación entre
recuerdo e inferencia, y primado de contexto. A diferencia de los
sistemas de memoria actuales (vectores, RAG), La Caja es una
arquitectura *falsable*: cada mecanismo tiene un criterio pre-registrado
y un experimento que puede refutarlo.

Reportamos, sobre dos corpus orgánicos de registro opuesto (Enron
laboral y Blog doméstico): una falsación empírica criterial (C1/C2 ok,
con refutaciones parciales en Blog y su causa documentada), una
validación de la capa de rehidratación sobre temas dormidos (Enron
1-6m: **+41%**), y dos evaluaciones de la relación memoria-modelo con
veredictos distintos y complementarios: el **re-ranking cloze** queda
falsado (V1-V4 FALSA — el modelo que reordena la memoria le resta), pero
el **benchmark pareado con/sin memoria** (el mismo modelo, con La Caja
como soporte de contexto) queda **validado** (win_rate 0.60, p=9e-43,
recall ~19x). El protocolo de acceso agente-agente-humano queda probado
de punta a punta con LLM reales por MCP (debate, solicitud de
interferencia con deadline, y la base del protocolo: interrupción al
medio del razonamiento con cesión dentro de la ronda).

La contribución no es una memoria "mejor" que la frecuencia — la
frecuencia gana en co-ocurrencia cloze — sino un sistema de memoria con
**límites medidos y honestos**, más una validación de que **La Caja como
soporte de memoria mejora al modelo que la usa**.

## 3. Introducción

### 3.1 El problema

Los agentes (LLMs) no tienen estado propio de lo que observaron. El
contexto inyectado en cada llamada es efímero; el agente no distingue lo
que vio de lo que infirió; y olvidar no es una capacidad, es un error.
Sin memoria, cada sesión de agente empieza de cero, y los agentes que
comparten trabajo no comparten observación.

### 3.2 La apuesta

Una memoria *asociativa*: no guardar textos (como RAG) sino el *tejido
de co-ocurrencias* entre términos, con tres propiedades:
multi-pertenencia (una palabra en varios contextos), discriminación
observado/inferido, y olvido con primado de contexto.

### 3.3 La postura metodológica

Cada mecanismo es falsable: hay un criterio pre-registrado y un
experimento que puede refutarlo. La falsación es una afirmación
mecánica (qué hace la memoria), no de utilidad aguas abajo. Cuando una
hipótesis cae, se reporta FALSA con su techo medido — no se "arregla".

## 4. Método

### 4.1 Arquitectura (spec v2.0/v2.1, `docs/`)

- **Nodos compartidos**: los conceptos (burbujas) viven en nodos; un
  término participa en varios contextos (multi-pertenencia).
- **Confianza**: la navegación distingue lo co-ocurrido (1.0) del
  cierre transitivo (`0.5^puentes`); compartir un término en consultas
  distintas NO conecta.
- **Olvido**: decaimiento por consolidación; el primado de contexto
  resucita temas dormidos (recuperación temporal).
- **Persistencia event-sourced** (opt-in): `PiscinaPersistente` registra
  cada mutación; un snapshot replayable reconstruye el estado
  byte-idéntico.

### 4.2 Capa de traza dormida (v0.7)

Cuando una asociación muere por olvido, no se borra: se captura como
traza inerte (partner, fuerza pico, último evento). La traza no participa
en navegación ni primado. Rehidratación opt-in: al re-observar una pareja
trazada, la relación se restaura en la capa viva. Rol honesto
pre-registrado: inercia + clave de rehidratación por re-observación — NO
predictor del contenido futuro (ver §6.2).

### 4.3 Protocolo de acceso (repo B, `la-caja-mcp`)

Herramientas MCP de memoria (`procesar_consulta`, `declarar_relacion`,
`consultar`, `contexto_primado`, `historial`, `stats`) y un protocolo de
debate agente-agente-humano (claims, solicitud de interferencia, rondas
con deadline en turnos, escalada y adjudicación humana) determinista y
replayable. Transportes stdio (local) y streamable HTTP (remoto, + push
SSE). La máquina de estados es un contrato: en `disputed`, el autor solo
puede responder o escalar; si el deadline vence, el claim llega a
`unresolved` (deadlock) y **el humano puede desbloquearlo** — el único
terminal adjudicable (§6.5).

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

### 6.3 ¿El modelo amplifica la memoria por re-ranking? (cloze, `eval_modelo_enron.json`)

Pregunta: un LLM re-ordenando la memoria mejora la recuperación sobre la
frecuencia (hit@5 emparejado, gpt-4o-mini vía OpenRouter, 400 consultas,
0 fallidas).

| Condición | hit@5 | hit@1 |
|---|---|---|
| frecuencia | 0.102 | — |
| memoria_alone (primado) | 0.045 | — |
| modelo_sin_memoria | 0.041 | 0.49 |
| modelo+memoria | 0.027 | 0.28 |
| techo | 0.204 | — |

**Veredicto: V1-V3 FALSA** (victorias emparejadas 60/204, 84/152,
16/339). En cloze co-ocurrencial, la frecuencia es el ground truth más
fuerte; el modelo que reordena la memoria *le resta*. No falsifica la
memoria (C1/C2 ok) — falsifica la hipótesis de amplificación por
re-ranking.

### 6.4 ¿La Caja como soporte de memoria mejora al modelo? (pareado, `eval_pareado_memoria_enron.json`) — **la tesis**

Pregunta distinta a §6.3: el mismo modelo (gpt-4o-mini), en dos corridas
— una con La Caja como soporte de contexto (la pregunta + el primado
`contexto_primado`), otra sin — responde preguntas de recall sobre el
vocabulario del corpus (Enron, memoria 60% pasado, consultas 40% futuro).
Se mide cuánto del vocabulario REAL de la consulta recupera cada
respuesta (recall contra ground truth). 400 consultas, 0 fallidas.

| Métrica | Valor |
|---|---|
| recall_medio con La Caja | **0.0626** |
| recall_medio sin La Caja | 0.0033 |
| gana_con / gana_sin / empate | 241 / 29 / 130 |
| win_rate | 0.6025 |
| p (test de signo) | 9.2e-43 |

**Veredicto: OK.** La Caja como soporte de memoria mejora la
recuperación del vocabulario real del corpus en ~19x, con significancia
sin margen. Esto es la tesis central: la memoria no compite con el
modelo (como en el cloze re-ranking de §6.3), **lo asiste** — el modelo
que recibe el contexto de La Caja responde mejor que el mismo modelo sin
él.

Hallazgo metodológico del mismo benchmark: el judge de preferencia
(estilo Elo/arena) mostró un sesgo de formato dominante — prefiere
listas genéricas coherentes (Estrategia, Compliance) sobre los términos
crudos REALES del corpus (metering, baseload) — y quedó descartado como
instrumento (7/390 en contra). El veredicto se basa en la coincidencia
objetiva contra ground truth, no en opinión.

### 6.5 El protocolo de acceso, probado de punta a punta (repo B)

Tres validaciones con LLM reales (gpt-4o-mini, OpenRouter) como clientes
MCP por streamable HTTP, fuera del unit test:

1. **Caso de uso real** (dos agentes compartiendo memoria + debatiendo):
   ingesta visible entre agentes, debate → `consensus`, replay
   determinista, push SSE — OK.
2. **Solicitud de interferencia completa**: interferir → ronda con
   deadline → el autor no responde (charla consume turnos) → `escalar` →
   `unresolved` → el humano desbloquea → `consensus`/`rejected` — OK.
   Destapó y resolvió una inconsistencia entre la docstring del protocolo
   y el código: `unresolved` es el único terminal que el humano puede
   adjudicar (el deadlock no es un callejón sin salida).
3. **La base del protocolo** (interrupción al medio del razonamiento): el
   autor expone sus conclusiones por etapas con `manifestar` (el medio de
   interrupción), consulta el estado entre etapas, el interferente
   solicita `interferir` al medio, y el autor **cede** respondiendo
   dentro de la ronda (vence_en_turnos intacto) — secuencia
   `proponer → manifestar → interferir → responder → aceptar`, OK.

La viabilidad en la práctica: la interrupción ocurre en las **fronteras
entre etapas** (los LLM no permiten pausar una generación a mitad de
token); el cómputo descartado por el cambio de rumbo es costo acotado e
invisible del protocolo, que opera sobre eventos committeados, no sobre
el stream.

## 7. Límites honestos

1. La memoria NO supera a la frecuencia en las tareas de co-ocurrencia
   cloze evaluadas (Enron). Su valor medido está en sus criterios
   mecánicos (C), la rehidratación por re-observación (1-6m), la
   discriminación recuerdo/inferencia, y — ahora validado — el soporte de
   contexto que mejora al modelo que la usa (win_rate 0.60).
2. La amplificación depende de CÓMO se usa el modelo: re-ranking cloze
   FALSA (§6.3), soporte de contexto pareado OK (§6.4). No contradicen:
   miden usos distintos.
3. Blog refutó A1/B1: la arquitectura depende del registro.
4. Los evals de modelo usaron un solo LLM (gpt-4o-mini) y un solo corpus
   (Enron); generalizar es trabajo futuro.
5. El judge de preferencia (Elo/arena) no sirve para recall co-ocurrencial
   en esta forma: sesgo de formato dominante, documentado.

## 8. Trabajo futuro

- **Publicación:** publicar `la-caja` y `la-caja-mcp` a PyPI (workflow
  listo en `.github/workflows/pypi.yml`; falta crear la cuenta en PyPI y
  vincular el trusted publishing, luego taguear `v0.7.0` / `v0.1.0`).
- **Generalización del pareado:** más LLMs (gpt-4o, claude, deepseek),
  más corpus (Blog), y tareas no co-ocurrenciales (anáfora, planificación
  con contexto, preguntas cuya respuesta vive en el corpus y no en el
  modelo).
- **Judge utilizable:** o jurados humanos con rúbrica, o métricas
  objetivas (como la usada en §6.4); descartar judges LLM de preferencia
  para recall.
- **El benchmark de interrupción como instrumento:** usar la tensión
  robustez/eficiencia (§6.5) como métrica de sistema agente + memoria +
  protocolo, estratificada por tipo de pregunta.

## 9. Reproducibilidad

- `pip install .` en repo A; `pip install .[dev]` en repo B.
- `python experiments/exp_memoria.py enron|blog` (ver falsacion.md).
- `python experiments/eval_modelo.py`, `eval_dormidos.py` y
  `eval_pareado_memoria.py` (requieren `OPENAI_API_KEY`; ver
  `falsacion.md` para la infra usada). El pareado es el veredicto final.
- Suite A: 53 tests de determinismo y propiedades; suite B: 31 tests
  (protocolo + integración MCP real + deadlock adjudicable).
- Replay byte-idéntico garantizado por la persistencia event-sourced.