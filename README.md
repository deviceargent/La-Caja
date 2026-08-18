# La Caja

Memoria contextual asociativa para modelos de lenguaje: lo que el modelo
**observó** en su vida, con olvido, discriminación entre recuerdo e
inferencia, y primado de contexto.

Este repositorio contiene la **implementación** (no solo la spec) y su
**falsación empírica**. El estado del arte de la arquitectura está en
`docs/` (spec v2.0 + addendum); la especificación y los resultados
criteriales están en `experiments/falsacion.md`.

## Qué hace

- **Multi-pertenencia**: los conceptos (burbujas) viven en nodos
  compartidos; un término puede participar en varios contextos.
- **Confianza observado/inferido**: la navegación distingue lo
  co-ocurrido (1.0) del cierre transitivo (`0.5^puentes`). Compartir un
  término en consultas distintas NO conecta: no se inventan puentes.
- **Olvido**: decaimiento por consolidación; las asociaciones que no se
  repiten mueren. El primado de contexto resucita temas dormidos
  (recuperación temporal).
- **Persistencia event-sourced** (opt-in): `PiscinaPersistente` registra
  cada mutación; un snapshot replayable reconstruye el estado exacto.

## Estado del proyecto

La falsación (pre-registrada en `falsacion.md`) corre dos corrientes
orgánicas de registro opuesto — **Enron** (corriente laboral, ~3.8 años)
y **Blog** (cocina diaria). Resultados canónicos (F=3) en
`experiments/results/`:

| Test | Enron | Blog |
|------|-------|------|
| A. discriminación (no densificación) | ok (todo) | **A1 FALSA**, A2/A3 ok |
| B. fidelidad al corpus | ok (todo) | **B1 FALSA**, B2/B3 ok |
| C. recuperación temporal (primado) | ok (C1 2.2×, C2 64% techo) | ok (C1, C2 70% techo) |

- **Enron pasa todo**; en Blog se refutan A1 y B1 (con la causa
  documentada: el cierre transitivo del núcleo sostenido de 500 términos
  conecta pares ajenos y el `optimize` colapsa la multi-pertenencia a
  un gigante único).
- Límite honesto reportado: el primado no recupera temas dormidos ≥ 1
  mes (Enron: techo ≤ 0.006 sin señal).

La falsación es una **afirmación mecánica** (qué hace la memoria), no de
utilidad aguas abajo. El acceso de agentes a La Caja y el protocolo de
debate agente-agente-humano viven en el repo hermano
[la-caja-mcp](https://github.com/deviceargent/la-caja-mcp).

## Uso

```
pip install .
```

```python
from la_caja import LaCaja

caja = LaCaja()                       # o LaCaja(db_path="memoria.db")
caja.procesar_consulta("el sol tiene masa")
caja.consultar("sol", "masa")         # 1.0 (observado)
caja.contexto_primado("sol", 10)      # contexto asociativo a inyectar
caja.stats()                          # terminos / nodos / aristas
```

## Estructura

```
src/la_caja/        implementación (core.py)
tests/              suite de determinismo y propiedades (46 tests)
experiments/        falsación: exp_memoria.py + criterios + resultados
docs/               spec v2.0, addendum v2.1, acceso MCP
```

## Reproducir

```
$env:PYTHONPATH="src"; python -m pytest tests -q        # 46/46
python experiments/exp_memoria.py enron|blog            # ver falsacion.md
```

Los experimentos necesitan los corpus (parquet de Enron y Blog
Authorship). Apuntá con `MEMORIA_DATOS=<dir>` al directorio con
`enron_00000.parquet` y `blogs/blogs/`; los resultados canónicos van a
`MEMORIA_RESULTADOS` (default `experiments/results/`).

## Licencia

MIT — ver [LICENSE](LICENSE).