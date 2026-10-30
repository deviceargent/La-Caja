# Registro de decisiones tecnicas

Este archivo registra decisiones que cambiaron el modelo o el alcance. Las fechas y commits permiten volver a la evidencia original.

| Fecha / commit | Decision | Motivo / consecuencia |
|---|---|---|
| 11 ago, `bfce7d4` | Arquitectura inicial Super Index / Access Pillars / Trunk / Branches / Node / Box | Primera hipotesis arquitectonica; se conserva en docs como historia |
| 15 ago, `f8c292b` | Sustituir la referencia inicial por burbujas y nodos | La arquitectura anterior no resolvia adecuadamente identidad multi-contexto y conectividad |
| 16 ago, `efcfcf4` | Multi-pertenencia y aristas explicitas como modelo canonico | Evitar exilio de terminos y puentes espurios por membresia |
| 16 ago, `fd2f3d9` | Event sourcing dentro del nucleo | Un solo camino de mutacion y replay determinista |
| 16 ago, `41e09e5` | Fision sobre membresias acumuladas | Activacion para asociaciones reforzadas; navegacion explicita para las debiles |
| 16 ago, `9d23148` | Capacidad por ventana de co-ocurrencia | Elegir presupuesto mediante ganancia marginal, no por intuicion |
| 16 ago, `0688747` | Olvido por conteo de eventos | Replay determinista independiente del reloj de pared |
| 17 ago, `dc68544` | Exponer distancia de inferencia | Diferenciar recuerdo observado de cierre transitivo |
| 17 ago, `978291f` y `8e74a05` | Refuerzo de relaciones y gracia multiplicativa | Reducir densificacion sin borrar asociaciones reforzadas |
| 18 ago, `fb5edfa` | Traza dormida inerte; rehidratacion solo por re-observacion | Preservar historial sin convertirlo en predictor |
| 18-19 ago, `61c185d`, `81a98c0`, `97dd7aa` | Mantener resultados negativos y positivos separados | El reranking y la traza predictiva fallaron; el benchmark pareado dio resultado positivo |
| 18 ago, `7025afb` | Separar el MCP del repositorio del nucleo | El paquete Python queda centrado en memoria; transporte y deliberacion pasan al repo hermano |
| 24-26 ago, PR #3 | Agregar lotes, tokenizacion alfanumerica y retencion de snapshots | Rendimiento y calidad de ingesta |
| 28 oct, PR #4 | Agregar cartografia como capa de solo lectura | Medir y descubrir patrones sin mutar memoria |

## Decision nueva — 30 oct 2026

Los identificadores de nodo pertenecen a cada Piscina. El contador global de `Nodo` no debe afectar la identidad local ni el replay de otra instancia. Los IDs mantienen el formato `nN`, y el contador local se reconstruye desde los nodos presentes en el snapshot.

## Decision nueva — 30 oct 2026

Los alias agregados mediante `declarar_sinonimo()` son estado de configuracion de una instancia de LaCaja, no un cambio al mapa global del modulo. En esta iteracion son runtime-only; la persistencia de esa configuracion queda pendiente.

## Decisiones vigentes

- La pertenencia activa contexto; la arista explicita habilita navegacion.
- La inferencia transitiva se consulta, no se materializa como relacion observada.
- El tiempo de olvido es el conteo de eventos.
- La traza dormida no alimenta primado ni navegacion.
- La rehidratacion requiere re-observacion real.
- Cartografia no escribe sobre la Piscina.
- Las especificaciones v2.0/v2.1 son documentos historicos; el contrato actual es `ARCHITECTURE.md` + codigo + tests.
