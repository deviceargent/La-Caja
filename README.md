# La Caja

Contextual associative memory for language models: what the model
**observed** during its lifetime, with forgetting, discrimination between
recall and inference, and context priming. **Falsifiable** architecture:
every mechanism has a pre-registered criterion and an experiment that can
refute it.

This repository contains the **implementation**, its **empirical
falsification**, and the **thesis validation**: *La Caja as a memory
support improves the model that uses it* (win_rate 0.60, p=9e-43). Agent
access and the agent–agent–human debate protocol live in the sibling repo
[la-caja-mcp](https://github.com/deviceargent/la-caja-mcp).

Español: [README.es.md](README.es.md)

## What it does

- **Multi-membership**: concepts (bubbles) live on shared nodes; one term
  can participate in several contexts.
- **Observed/inferred confidence**: navigation distinguishes co-occurrence
  (1.0) from transitive closure (`0.5^hops`). Sharing a term across
  different queries does NOT connect: no bridges are invented.
- **Forgetting**: decay through consolidation; associations weaken with non-use.
  Priming retrieves retained associations; it did not
  recover themes absent for a month or more in the tested Enron stream.
- **Dormant trace (v0.7)**: what was forgotten is not deleted — it stays
  as an inert trace, a key for rehydration by re-observation (honest
  role: it does NOT predict the future).
- **Event-sourced persistence** (opt-in): `PiscinaPersistente` records
  every mutation; replayable snapshots reconstruct the state. `LaCaja` supports `close()` and `with` for SQLite lifecycle.

## Evidence (honest summary)

All verdicts in `experiments/falsacion.md`; the numbers in
`experiments/results/`.

| Criterion | Result |
|---|---|
| C1/C2 — temporary recovery (priming) | **ok** (Enron 2.2×, Blog ok) |
| A/B — discrimination and fidelity | **ok** in Enron; A1/B1 **FALSE** in Blog (cause documented) |
| Rehydration (Enron, 1-6m) | **+41%** |
| The dormant trace predicts the future | **FALSE** (ceiling 0.03) — inertia, not prediction |
| Model re-ranking the memory (cloze) | **FALSE** — frequency wins; the model subtracts |
| **La Caja as memory support (paired)** | **OK** — recall ~19x, p=9e-43 |

![La Caja as memory support — recall with vs without](https://raw.githubusercontent.com/deviceargent/La-Caja/main/docs/figures/tesis_pareada.png)
![Per-query verdicts — win_rate](https://raw.githubusercontent.com/deviceargent/La-Caja/main/docs/figures/tesis_veredictos.png)
![Final evidence — criteria summary](https://raw.githubusercontent.com/deviceargent/La-Caja/main/docs/figures/resumen_evidencia.png)
![Rehydration by re-observation](https://raw.githubusercontent.com/deviceargent/La-Caja/main/docs/figures/rehidratacion.png)

The thesis was validated on 400 queries (gpt-4o-mini, Enron): the same
model with La Caja recovers the real corpus vocabulary ~19x better than
without it. The limits are part of the design: the memory does not compete
with frequency in co-occurrence cloze, and it is not a long-term memory
(priming does not revive topics dormant for ≥ 1 month).

The access protocol (repo B) was proven end to end with real LLMs: debate,
interference request with deadline, human escalation, and **interruption
mid-reasoning** (the agent yields within the round).

## Usage

### Installation

Standard Python package (`la-caja`):

```
# 1. Published (PyPI): a single command
pip install "la-caja[cartografia]"

# 2. Direct from the repository (works today)
pip install "la-caja[cartografia] @ git+https://github.com/deviceargent/La-Caja.git"

# 3. Local development: installs the current directory
pip install ".[cartografia]"
```

Publishing to PyPI is done by tagging the repo (`v0.7.0`) — the workflow
`.github/workflows/pypi.yml` builds the wheel and uploads it automatically
(trusted publishing, no tokens). The README becomes the package page.

### Code

```python
from la_caja import LaCaja

caja = LaCaja()                       # or LaCaja(db_path="memoria.db")
caja.procesar_consulta("el sol tiene masa")
caja.consultar("sol", "masa")         # 1.0 (observed)
caja.contexto_primado("sol", 10)      # associative context to inject
caja.stats()                          # terms / nodes / edges
```

## Command line

After installation, the `la-caja` command provides a persistent local workflow:

```powershell
la-caja observe --db memoria.db "gravedad masa energia"
la-caja ingest --db memoria.db observaciones.txt
la-caja query --db memoria.db gravedad masa
la-caja prime --db memoria.db gravedad --budget 5
la-caja stats --db memoria.db
la-caja cartography --db memoria.db --html mapa.html --gexf mapa.gexf
```

`ingest` reads UTF-8 text one observation per line and commits in a batch. Cartography commands require the `[cartografia]` extra.

## Graph Cartography (analytical layer)

A read-only structural analysis layer over the live pool. It measures
the graph's shape, surfaces candidate configurations worth examining,
and renders an interactive visualization — without mutating the pool or
converting hypotheses into relations.

```python
from la_caja import LaCaja
from la_caja.cartografia import medir, descubrir, comparar_subgrafos
from la_caja.cartografia.visualizar import exportar_html

caja = LaCaja(db_path="memoria.db")
medidas, estructuras = medir(caja.piscina)       # stage A: metrics
candidatos, resumen = descubrir(caja.piscina)    # stage B: candidates
comparaciones = comparar_subgrafos(caja.piscina) # stage B: cross-domain
exportar_html(caja.piscina, "mapa.html", candidatos=candidatos)
```

Full documentation: `docs/cartografia.md`.

## Structure

```
src/la_caja/            implementation (core.py)
src/la_caja/cartografia/  graph cartography (measurement, discovery, viz)
tests/                  determinism, property and CLI suite (82 tests)
experiments/            falsification, evals, cartography demo
docs/                   spec v2.0, addendum v2.1, MCP access, cartografia
docs/figures/           evidence bar charts (generated by experiments/graficos.py)
```

## Reproduce

```
python -m pytest tests -q        # 82 tests (after pip install -e ".[cartografia]")
python experiments/exp_memoria.py enron|blog            # see falsacion.md
python experiments/eval_pareado_memoria.py              # the thesis (needs OPENAI_API_KEY)
python experiments/exp_cartografia.py                   # cartography demo (no API key needed)
```

The experiments need the corpora (Enron and Blog Authorship parquet).
Point `MEMORIA_DATOS=<dir>` to the directory with `enron_00000.parquet`
and `blogs/blogs/`; canonical results go to `MEMORIA_RESULTADOS` (default
`experiments/results/`).

## License

MIT — see [LICENSE](LICENSE).