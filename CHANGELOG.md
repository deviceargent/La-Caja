# Changelog

## Unreleased — rama work/functionalize-core

- Se declara la extra opcional `cartografia` con NetworkX y NumPy.
- CI instala el paquete con extras y deja de usar un conteo de tests obsoleto.
- Se agrega cierre explicito/context manager a las piscinas persistentes y a LaCaja.
- Se agregan pruebas para cierre, reapertura, idempotencia y cierre durante lotes.
- Se incorpora la CLI `la-caja` y `python -m la_caja`.
- Las rutas de lectura de LaCaja canonizan alias como lo hace la ingesta.
- Los IDs de nodo se asignan por Piscina, no desde un contador global compartido.
- Los alias declarados en runtime quedan aislados por instancia; un filtro ontologico vacio permite desactivar el filtro.
- Se amplía la suite a 82 pruebas; se prueba el aislamiento de alias y el filtro configurable.
- Se actualizan instrucciones de instalacion, CLI y reproduccion.

## 0.7.0 — 19 ago 2026

- Traza dormida inerte y rehidratacion opt-in por re-observacion.
- Evaluaciones sobre Enron/Blog y benchmark pareado con/sin La Caja.
- Empaquetado Python, licencia MIT, writeup y README bilingue.
- Se separa el protocolo MCP del repositorio del nucleo.

## Cambios posteriores a 0.7.0

### 24–26 ago 2026 — PR #3

- Ingesta por lotes con snapshot al finalizar; benchmark reportado de 77x en el corpus medido.
- Tokenizador conserva digitos internos y descarta numeros puros.
- Filtro ontologico ampliado.
- Retencion de los dos snapshots mas recientes para evitar crecimiento ilimitado.

### 28 oct 2026 — PR #4

- Capa de cartografia de solo lectura: medicion, descubrimiento, comparacion de subgrafos.
- Exportacion HTML autocontenida y GEXF.
- Fixture y experimento reproducible; 12 pruebas nuevas.
