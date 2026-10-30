# La Caja

Memoria contextual asociativa para modelos de lenguaje: lo que el modelo
**observó** en su vida, con olvido, discriminación entre recuerdo e
inferencia, y primado de contexto. Arquitectura **falsable**: cada
mecanismo tiene un criterio pre-registrado y un experimento que puede
refutarlo.

Este repositorio contiene la **implementación**, su **falsación
empírica** y la **validación de la tesis**: *La Caja como soporte de
memoria mejora al modelo que la usa* (win_rate 0.60, p=9e-43). El acceso
de agentes y el protocolo de debate agente-agente-humano viven en el repo
hermano [la-caja-mcp](https://github.com/deviceargent/la-caja-mcp).

English: [README.md](README.md)

## Qué hace

- **Multi-pertenencia**: los conceptos (burbujas) viven en nodos
  compartidos; un término puede participar en varios contextos.
- **Confianza observado/inferido**: la navegación distingue lo
  co-ocurrido (1.0) del cierre transitivo (`0.5^puentes`). Compartir un
  término en consultas distintas NO conecta: no se inventan puentes.
- **Olvido**: decaimiento por consolidación; las asociaciones pierden fuerza con el desuso.
  El primado recupera asociaciones retenidas; en Enron no
  recuperó temas ausentes durante un mes o más.
- **Traza dormida (v0.7)**: lo olvidado no se borra — queda como traza
  inerte, clave de rehidratación por re-observación (rol honesto: NO
  predice el futuro).
- **Cartografía**: análisis estructural de solo lectura, descubrimiento de candidatos y exportación HTML/GEXF. Requiere la extra `cartografia`.
- **Persistencia event-sourced** (opt-in): `PiscinaPersistente` registra
  cada mutación; un snapshot replayable reconstruye el estado exacto. `LaCaja` ofrece `close()` y context manager para SQLite.

## Evidencia (resumen honesto)

Todos los veredictos en `experiments/falsacion.md`; los números en
`experiments/results/`.

| Criterio | Resultado |
|---|---|
| C1/C2 — recuperación temporal (primado) | **ok** (Enron 2.2×, Blog ok) |
| A/B — discriminación y fidelidad | **ok** en Enron; A1/B1 **FALSA** en Blog (causa documentada) |
| Rehidratación (Enron, 1-6m) | **+41%** |
| La traza dormida predice el futuro | **FALSA** (techo 0.03) — inercia, no predicción |
| Modelo re-ordenando la memoria (cloze) | **FALSA** — la frecuencia gana; el modelo resta |
| **La Caja como soporte de memoria (pareado)** | **OK** — recall ~19x, p=9e-43 |

![La Caja como soporte de memoria — recall con vs sin](https://raw.githubusercontent.com/deviceargent/La-Caja/main/docs/figures/tesis_pareada.png)
![Veredictos por consulta — win_rate](https://raw.githubusercontent.com/deviceargent/La-Caja/main/docs/figures/tesis_veredictos.png)
![Evidencia final — resumen de los criterios](https://raw.githubusercontent.com/deviceargent/La-Caja/main/docs/figures/resumen_evidencia.png)
![Rehidratación por re-observación](https://raw.githubusercontent.com/deviceargent/La-Caja/main/docs/figures/rehidratacion.png)

La tesis quedó validada sobre 400 consultas (gpt-4o-mini, Enron): el
mismo modelo con La Caja recupera el vocabulario real del corpus ~19x
mejor que sin ella. Los límites son parte del diseño: la memoria no
compite con la frecuencia en cloze co-ocurrencial, y no es una memoria de
largo plazo (el primado no resucita temas dormidos ≥ 1 mes).

El protocolo de acceso (repo B) quedó probado de punta a punta con LLM
reales: debate, solicitud de interferencia con deadline, escalada humana,
e **interrupción al medio del razonamiento** (el agente cede dentro de la
ronda).

## Uso

### Instalación

Paquete de Python estándar (`la-caja`):

```
# 1. Publicado (PyPI): una vez publicado, un solo comando
pip install "la-caja[cartografia]"

# 2. Directo del repositorio (funciona hoy, sin esperar publicación)
pip install "la-caja[cartografia] @ git+https://github.com/deviceargent/La-Caja.git"

# 3. Desarrollo local: instala la copia del directorio actual
pip install ".[cartografia]"
```

Publicar a PyPI se hace tagueando el repo (`v0.7.0`) — el workflow
`.github/workflows/pypi.yml` construye el wheel y lo sube automáticamente
(trusted publishing, sin tokens). El README se convierte en la página del
paquete.

### Código

```python
from la_caja import LaCaja

caja = LaCaja()                       # o LaCaja(db_path="memoria.db")
caja.procesar_consulta("el sol tiene masa")
caja.consultar("sol", "masa")         # 1.0 (observado)
caja.contexto_primado("sol", 10)      # contexto asociativo a inyectar
caja.stats()                          # terminos / nodos / aristas
```

## Línea de comandos

Después de instalar el paquete, el comando `la-caja` permite trabajar con una memoria SQLite:

```powershell
la-caja observe --db memoria.db "gravedad masa energia"
la-caja ingest --db memoria.db observaciones.txt
la-caja query --db memoria.db gravedad masa
la-caja prime --db memoria.db gravedad --budget 5
la-caja stats --db memoria.db
la-caja cartography --db memoria.db --html mapa.html --gexf mapa.gexf
```

`ingest` lee UTF-8, una observación por línea, y confirma en lote. La cartografía requiere la extra `[cartografia]`.

## Estructura

```
src/la_caja/        implementación (core.py)
tests/              suite de determinismo, propiedades y CLI (82 tests)
experiments/        falsación, evals y el writeup final (writeup.md)
docs/               spec v2.0, addendum v2.1, acceso MCP
docs/figures/       gráficos de barra de la evidencia (generados por experiments/graficos.py)
```

## Reproducir

```
python -m pytest tests -q        # 82 tests
python experiments/exp_memoria.py enron|blog            # ver falsacion.md
python experiments/eval_pareado_memoria.py              # la tesis (requiere OPENAI_API_KEY)
python experiments/exp_cartografia.py                   # demo cartografica (sin API key)
```

Los experimentos necesitan los corpus (parquet de Enron y Blog
Authorship). Apuntá con `MEMORIA_DATOS=<dir>` al directorio con
`enron_00000.parquet` y `blogs/blogs/`; los resultados canónicos van a
`MEMORIA_RESULTADOS` (default `experiments/results/`).

## Licencia

MIT — ver [LICENSE](LICENSE).