# Estado del proyecto

Fecha de auditoria: 2026-10-30. Rama de trabajo: `work/functionalize-core`. Este archivo es el punto de entrada para cualquier agente o colaborador que retome el proyecto sin historial conversacional.

## Estado actual

La Caja es una biblioteca Python instalable para memoria contextual asociativa, con persistencia event-sourced opcional y una capa de cartografia estructural de solo lectura. La version publicada/documentada en el repositorio es 0.7.0.

- Nucleo: implementado.
- Persistencia SQLite y replay: implementados y cubiertos por pruebas.
- Ingesta por lotes: implementada.
- Olvido, fision, promocion, traza dormida y rehidratacion opt-in: implementados.
- Cartografia: implementada; validacion actual limitada a fixtures sinteticos.
- MCP y deliberacion agente-agente-humano: proyecto hermano, no parte de este paquete.
- CLI: implementada con observe, ingest, relate, query, prime, stats, history, optimize y cartography.
- Concurrencia: no validada.

## Linea de evolucion reconstruida

| Periodo / commits | Cambio | Estado actual |
|---|---|---|
| 11-12 ago, commits iniciales | Spec Super Index/Box/Node y primer MCP de deliberacion | Referencia historica; MCP se separo |
| 15 ago, `f8c292b` | Reemplazo del modelo inicial por burbuja-nodo | Base conceptual vigente |
| 16 ago, `0643f55`–`fd2f3d9` | Multi-pertenencia, aristas estrictas y event sourcing | Vigente |
| 16-17 ago, `41e09e5`–`c895a6e` | Fision, capacidad por ventana, olvido, sinonimos, promocion, confianza por distancia | Vigente, con parametros empiricos |
| 17-18 ago, `978291f`–`75e64da` | Refuerzo/olvido de relaciones, repeticion espaciada y cierre de falsacion | Vigente |
| 18 ago, `fb5edfa`–`0a85949` | Traza dormida y rehidratacion por re-observacion | Vigente, opt-in para rehidratacion |
| 19 ago, `61c185d`–`97dd7aa` | Evals contra modelo y benchmark pareado | Evidencia historica; interpretar con limites documentados |
| 19 ago, `adb2523`–`96891d6` | Empaquetado, writeup, README bilingue y graficos | Vigente, requiere mantener metadatos |
| 24-26 ago, PR #3 | Lotes, digitos internos, filtro ampliado, poda de snapshots | Integrado en main |
| 28 oct, PR #4 | Cartografia: medicion, descubrimiento, comparacion, HTML/GEXF | Integrado en main |

## Evidencia tecnica verificada en esta auditoria

- Checkout original: `main`, limpio y sincronizado con `origin/main` en `38ee46c` antes de crear esta rama.
- Suite base: 72/72.
- Entorno limpio sin extras: importacion del nucleo posible; importacion de cartografia falla por falta de dependencias declaradas en el paquete.
- Se reprodujo el fallo de CI: con solo pytest y `PYTHONPATH=src`, los tests de cartografia fallaban por ausencia de NetworkX.
- Se agrego la extra `cartografia = [networkx, numpy]` y CI ahora instala `.[cartografia]`.
- Wheel 0.7.0 construido e instalado en un entorno virtual limpio con extra; 82/82 tests pasaron y el entry point `la-caja --help` funciona.
- Se agrego cierre explicito y context manager para SQLite, con tres pruebas nuevas. La CLI y la canonizacion de rutas de lectura suman cuatro pruebas; el aislamiento de IDs suma una mas: suite actual 82/82.
- La demo de cartografia se ejecuto dos veces y valido los cuatro patrones. Los artefactos HTML/GEXF no se incluyen en esta rama porque contienen metadatos de ejecucion y difieren entre corridas.

## Cambios de esta rama aun no integrados

1. Extra de dependencias cartograficas en `pyproject.toml`.
2. CI instala el paquete y la extra antes de ejecutar tests; se elimino el contador obsoleto de 46.
3. README ingles/espanol actualizados para instalacion, dependencias y conteo de pruebas.
4. `.gitignore` actualizado para entornos virtuales locales.
5. `PiscinaPersistente.close()`, `LaCaja.close()` y soporte de context manager.
6. Pruebas de cierre, reapertura, idempotencia y prohibicion de cierre dentro de lote.
7. CLI `la-caja`, `python -m la_caja` y pruebas de comandos.
8. Canonizacion de alias en las rutas de lectura.
9. Documentos de arquitectura, estado, decisiones, changelog y roadmap.

## Riesgos que deben resolverse

- Identificadores de nodo: secuencia ahora local a Piscina; falta probar replay con bases de datos de corpus grandes.
- Los alias runtime ya son locales por instancia; aun no se persisten al reabrir SQLite.
- Contrato de excepciones y durabilidad de `lote()`.
- Reproducibilidad del layout cartografico entre versiones de NetworkX/NumPy.
- Integracion organica de cartografia y pruebas de escala.
- Evaluacion causal: separar aporte estructural de La Caja de simple inyeccion lexical.

## Proximo hito

Cerrar esta rama con una revision independiente, validar wheel limpio + CI, crear PR y mergear cuando este verde. Luego abordar aislamiento de IDs y configuracion de alias como cambios separados, cada uno con pruebas de regresion.
