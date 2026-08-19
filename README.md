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
[la-caja-mcp](https://github.com/deviceargent/la-caja-mcp). El esqueleto
del artículo (con los números de todos los experimentos) está en
`experiments/writeup.md`.

## Uso

### Instalación

La Caja es un paquete de Python estándar (`la-caja`). Se puede instalar
de tres formas, según de dónde venga el código:

```
# 1. Publicado (PyPI): una vez publicado, un solo comando
pip install la-caja

# 2. Directo del repositorio (funciona hoy, sin esperar publicación)
pip install git+https://github.com/deviceargent/La-Caja.git

# 3. Desarrollo local: instala la copia del directorio actual
pip install .
```

Cómo funciona: `pyproject.toml` declara el paquete (nombre, versión,
dependencias, autor). `pip install <origen>` construye un wheel (el
archivo comprimido que Python instala) e instala el módulo `la_caja` en
tu entorno (venv, conda, o el Python del sistema). Con `pip install la-caja`
el origen es PyPI (el índice público de paquetes de Python); con `.` o
`git+...` el origen es código local o un repo. El nombre de importación
(`la_caja`, con guion bajo) no coincide con el de instalación (`la-caja`,
con guion): esa es la convención de Python. Publicar a PyPI se hace
tagueando el repo (`v0.7.0`) — el workflow `.github/workflows/pypi.yml`
construye el wheel y lo sube automáticamente (trusted publishing, sin
tokens). El README de este repo se convierte en la página del paquete.

### Código

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
tests/              suite de determinismo y propiedades (53 tests)
experiments/        falsación, evals y el esqueleto del writeup (writeup.md)
docs/               spec v2.0, addendum v2.1, acceso MCP
```

## Reproducir

```
$env:PYTHONPATH="src"; python -m pytest tests -q        # 53/53
python experiments/exp_memoria.py enron|blog            # ver falsacion.md
```

Los experimentos necesitan los corpus (parquet de Enron y Blog
Authorship). Apuntá con `MEMORIA_DATOS=<dir>` al directorio con
`enron_00000.parquet` y `blogs/blogs/`; los resultados canónicos van a
`MEMORIA_RESULTADOS` (default `experiments/results/`).

## Licencia

MIT — ver [LICENSE](LICENSE).