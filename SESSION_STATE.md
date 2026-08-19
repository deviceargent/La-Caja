# La Caja — Session State (handoff)

## Objetivo de este archivo

Registrar para el próximo agente (Claude) todo lo que ocurrió **después
de `e0c5fd6`** ("Iteracion 2d", 2026-08-18 05:33 -0300, cierre de las
condiciones 2 y 3 de la falsación). El agente que continúe debe leer esto
como reemplazo del contexto que no vio.

## Estado actual (heads verificados)

- Repo A (La-Caja, `C:\Users\Agentic\AppData\Local\Temp\opencode\La-Caja-testing`):
  main `b8598ea` — **53/53 tests verdes** (`$env:PYTHONPATH="src"; python -m pytest tests -q`).
- Repo B (la-caja-mcp, `...\Temp\opencode\la-caja-mcp`): main `823f076` —
  **29/29 tests verdes**.
- Git remoto: `https://github.com/deviceargent/La-Caja` / `.../la-caja-mcp`;
  identidad `deviceargent` / `deviceargent@users.noreply.github.com`.

## Línea de tiempo: todo lo que Claude NO vio (después de e0c5fd6)

### 18/8 — cierre y reorganización
- `75e64da` Cierre de falsación: resultados canónicos finales (F=3) y
  conclusión en `experiments/falsacion.md`. Tesis sobrevive en Enron
  (A/B/C ok); en Blog A1 (cordura de navegación) y B1 (optimize único)
  refutadas. Límite reportado: sin señal para temas dormidos ≥ 1 mes.
- `a89373d` docs de acceso de agentes (transportes MCP, decisión de despliegue).
- `695f359` + `f1a5804` pyproject mínimo `la-caja` + README honesto +
  CI para la memoria.
- `7025afb` mover MCP de deliberación a `la-caja-mcp/legacy`.
- `4797a20` main pasa a ser el proyecto de memoria (hereda de testing).
- `8bccdff` licencia MIT (2026 Miguel Okstein).

### 18-19/8 — capa de traza dormida (v0.7.0) + rehidratación
- `fb5edfa` **traza dormida**: `historial(termino)` devuelve partners
  olvidados (fuerza pico, último evento, capturas); `_capturar_traza` en
  el olvido; capa inerte (no participa en navegación ni primado).
  Rehidratación opt-in (`rehidratar=True`, `MEDIA_VIDA_REHIDRATACION=1500`);
  al re-observar una pareja trazada la restaura en la capa viva. 53 tests.
- `0a85949` validación rehidratación Enron (harness `--rehidratar`,
  resultado en `experiments/results/resultado_enron_rehidratar.json`):
  `hit5_modelo` 0.064→0.070 (+10%), rango 1-6m 0.0058→0.0082 (**+41%**),
  techo 0.100→0.126, C2 0.64→0.56, sin regresión B; ingesta 1289s→1657s.
- `23b5014` réplica Blog: **nula** (0.08502→0.08497) — mecanismo
  evento-denso, 203 docs demasiado escasos
  (`experiments/results/resultado_blog_rehidratar.json`).

### 19/8 — evaluaciones contra modelo (pre-registradas en falsacion.md)
- `61c185d` **eval contra modelo** (`experiments/eval_modelo.py`, Enron,
  400 consultas, 0 fallidas, `experiments/results/eval_modelo_enron.json`):
  hit@5 — modelo+memoria 0.027 < modelo_sin_memoria 0.041 < memoria_alone
  0.045 < **frecuencia 0.102**; hit@1 0.28 vs 0.49; techo 0.204; victorias
  emparejadas 60/204, 84/152, 16/339. **V1/V2/V3 FALSA**: en cloze
  co-ocurrencial el modelo *resta*, no amplifica. No falsifica la memoria
  (C1/C2 ok) — falsifica la hipótesis de amplificación.
- `81a98c0` **eval de temas dormidos** (`experiments/eval_dormidos.py`,
  400 consultas con historial no vacío, 0 fallidas,
  `experiments/results/eval_dormidos_enron.json`): frecuencia 0.1022 >
  memoria_alone_viva 0.045 > modelo_sin_memoria 0.0403 > modelo+traza
  0.0186 > memoria_alone_traza 0.0132; hit@1 modelo+traza 0.16 vs
  sin_memoria 0.49; **techo_hist 0.0298**, techo_pool 0.1848. **V1-V4
  FALSA**: la traza no predice la co-ocurrencia futura (los partners
  olvidados aparecen en ~3% de la respuesta). Rol honesto de la traza:
  inercia + clave de rehidratación por re-observación, NO predictor.
  Consistente con `0a85949` (la rehidratación actúa sobre re-observación).

### 19/8 — empaquetado real + esqueleto del writeup
- `adb2523` pyproject completo (A y B), wheel verificado en venv limpio
  (`la-caja-0.7.0`, `la-caja-mcp-0.1.0`), `.github/workflows/pypi.yml`
  (trusted publishing, publica al taguear `v*`), README con instalación
  explicada (PyPI / git+ / local), **`experiments/writeup.md`**: esqueleto
  del artículo con todos los números medidos; secciones de prosa marcadas
  `[PENDIENTE]`.
- `f45e988` / `b8598ea` / B `c0040e5` / B `823f076`: gitignore (build/,
  egg-info/, *.egg-info/, corrección de líneas concatenadas por Add-Content).

### Repo B completo (todo posterior a e0c5fd6)
- `3d75317` prototipo debate; `03ac82f` un server FastMCP dos transportes
  (stdio + streamable HTTP); `1d802d7` worker ASGI (uvicorn + Dockerfile);
  `fe82014` tools de memoria de La Caja como consumidor vía API;
  `3e816db` legacy MCP deliberación (Cloudflare) movido a `legacy/`;
  `38f4fe3` CI 29 tests; `2a3bb0c` **push SSE** `/caja/push` (discusión en
  vivo, streamable HTTP); `e3be2de` licencia MIT; `871ab8a` tool
  `historial` (traza dormida). Herramientas MCP: debate
  (`crear_sesion`, `mover`, `estado`, `ultimos_eventos`, `reproducir_sesion`)
  + memoria (`procesar_consulta`, `declarar_relacion`, `consultar`,
  `contexto_primado`, `historial`, `stats`).

## Infraestructura de evaluaciones (crítica para continuar)

- Hardware: Intel HD 620, 4GB RAM — **no hay inferencia local**.
- Vías de API probadas: gptgod (créditos agotados), Naga (cuota diaria),
  aihubmix (free-tier 10 usos). **Ruta ganadora: OpenRouter**
  (`https://openrouter.ai/api/v1`) con `openai/gpt-4o-mini` (el modelo
  del pre-registro), free tier, ~2-4s/llamada, sin límites duros
  (400 consultas en 536s con EVAL_THREADS=4).
- Key en `C:\Users\Agentic\AppData\Local\Temp\opencode\openai_key.txt`
  (no loguear).
- Env: `$env:OPENAI_API_KEY = Get-Content "<key>" -Raw;`
  `$env:MEMORIA_DATOS="C:\Users\Agentic\AppData\Local\Temp\opencode\memoria_exp";`
  `$env:PYTHONPATH="src"`; opcional `EVAL_THREADS`, `EVAL_MODELO`, `EVAL_BASE_URL`.
- Datos Enron/Blog en `memoria_exp` (`enron_00000.parquet`, `blogs/`).
  Memoria de test_c = 60% pasado (3025 docs, ~130-150s).
- Eval_modelo.py y eval_dormidos.py: guardado incremental JSONL
  (`experiments/results/*_partial.jsonl`, ignorado por git) + `--resume`
  (reintenta fallidas) + aborto por crédito. Nota: la primera corrida
  colgó en las 3 primeras consultas (0-2); `--resume` las resolvió.

## Deliberadamente NO hecho todavía

- **Caso de uso real**: dos agentes compartiendo memoria y debatiendo por
  MCP (repo B) contra un worker compartido; objetivo medible si el primado
  cambia la interferencia y si el consenso emerge más rápido. Es el paso
  propuesto para generar evidencia nueva.
- **Publicación a PyPI**: workflow listo, falta cuenta en pypi.org y
  vincular trusted publisher por proyecto; luego `git tag v0.7.0`.
- **Prosa del writeup**: `experiments/writeup.md` tiene las secciones
  `[PENDIENTE]` por redactar (intro, discusión, etc.).
- **Generalización de evals de modelo**: un solo LLM (gpt-4o-mini), un
  solo corpus (Enron) en las dos evaluaciones.

## Notas para el próximo agente

- El repo A es el "motor de memoria"; el B es el consumidor MCP. B no
  toca el núcleo de memoria.
- Los veredictos FALSA de los evals de modelo son **el resultado
  esperado y honesto**, no un fallo: acotan la contribución (la memoria
  no supera a la frecuencia en co-ocurrencia; el valor medido está en
  C1/C2, la rehidratación por re-observación y la discriminación
  recuerdo/inferencia). No "arreglar" esto como si fuera un bug.
- Si se corre un eval de nuevo, respetar los pre-registros de
  `falsacion.md` (modelo, seeds, tamaño S, condiciones) para no
  p-hackear.
- Convención del proyecto: afirmaciones pre-registradas y resultados
  medidos antes que narrativa. Escribir en `falsacion.md` antes de medir,
  y documentar el resultado (incluso negativo) en el commit.

Última actualización: 2026-08-19.