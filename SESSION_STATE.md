# Session handoff

Ultima actualizacion: 2026-10-30. Commit de implementacion: `16deec5d98930bdb29de45541d2380b4e70a9bf6`.

## Fuente de verdad

1. `PROJECT_STATE.md` — estado verificado, lineage y riesgos.
2. `ARCHITECTURE.md` — arquitectura que realmente implementa el codigo.
3. `DECISIONS.md` — decisiones y reemplazos historicos.
4. `ROADMAP.md` — siguiente trabajo ordenado.
5. `CHANGELOG.md` — cambios integrados y no publicados.
6. `CONTRIBUTING.md` — entorno y reglas publicas de desarrollo.
7. `AGENTS.md` local (si existe) — reglas privadas de trabajo.

No asumir que el chat anterior existe. No asumir que una spec antigua describe el codigo vigente. Antes de modificar, leer estos archivos, revisar `git status`, `git log` y la suite.

## Estado de trabajo

Rama: `work/functionalize-core`.

Trabajo local sin integrar:
- Extra `cartografia` con NetworkX y NumPy.
- CI corregido para instalar la extra.
- README y .gitignore actualizados.
- API de cierre/context manager para SQLite.
- CLI funcional (`la-caja` y `python -m la_caja`); siete pruebas nuevas adicionales; suite actual 82/82 en el entorno de desarrollo.

## Siguiente accion

Revisar el diff completo, reconstruir wheel desde el codigo actualizado, instalarlo en un entorno virtual limpio y ejecutar 82 tests. Luego revisar el diff de HTML/GEXF, crear PR y esperar CI antes del merge.

## Regla de continuidad

Actualizar `PROJECT_STATE.md`, `CHANGELOG.md` y este handoff al cerrar cada hito. Los documentos de estado deben indicar fecha y commit exacto una vez que exista commit; no copiar resultados no verificados.
