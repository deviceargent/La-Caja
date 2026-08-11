# La Caja — Addendum: Troncal, Piscina y Cache Nodal
*Borrador — sesión del 26/7/2026. Complementa v2.0, no lo reemplaza.*

## Filosofía (resumen de v2.0 §1, para referencia rápida)

La Caja existe porque los mecanismos actuales de memoria inter-sesión en LLMs
(inyección de texto crudo, resumen con pérdida, truncado duro, o RAG puro)
tratan el contexto como un buffer plano, no como una estructura navegable.
Ninguno permite **navegar** — habitar momentáneamente un estado de contexto
previo, extraer lo relevante, y volver al contexto activo sin fusionar ambos.
La Caja está diseñada alrededor de la navegación como operación de primera clase,
no como efecto secundario de la recuperación.

## 1. El Troncal como bus lógico único (analogía FSB)

El troncal no transporta contenido — arbitra acceso. Igual que un Front-Side
Bus de una motherboard vieja: técnicamente son varios canales físicos, pero
lógicamente es **un solo canal arbitrado**, accedido de a un componente por
vez. Ningún componente individual necesita (ni debería) saturar el ancho de
banda completo en un uso normal.

Función real del troncal: servir de intercambio entre nodos de distinto nivel
o distancia topológica cuando la conexión directa nodo-a-nodo no existe
todavía o es ineficiente. Nodos con proximidad física/topológica se conectan
directo, sin pasar por el troncal. Nodos lejanos lo atraviesan.

El troncal también es el canal por el cual las **devoluciones de inferencias
con datasets grandes** llegan a la piscina — con margen de ancho de banda de
sobra, porque no compite con tráfico de cómputo (las cajas no infieren, ver
§2).

## 2. Las cajas no son mini-modelos — son diccionarios locales

Corrección respecto a una lectura anterior de esta arquitectura: las cajas
**no ejecutan inferencia**. No son mini-modelos de lenguaje resolviendo
lógica. Son resolutores de vecindad local — almacenan términos accedidos
recientemente, no distinto de un diccionario. Resuelven cuestiones
**inter-nodales locales** (¿está este término en un nodo vecino? ¿hay una
conexión ya formada?) sin generar contenido nuevo.

Esto las hace baratas: el costo por caja es de almacenamiento y lookup, no de
cómputo de modelo.

## 3. Vida del cache nodal: por consulta, no persistente

El cache de cada caja dura **el contexto de la consulta actual** — a nivel
usuario, una sola pregunta, independientemente de su peso — no persiste entre
sesiones.

**⚠ Contradice v2.0 §3.5.2**, que describe el cache de la caja como
*no-volátil*, análogo a cache de resolución DNS, persistente entre consultas.
Son dos modelos de vida útil incompatibles. Falta decidir cuál rige — quedó
sin resolver hoy.

Ventaja de la versión volátil (si es la que rige): evita por completo el
problema de invalidación de cache — no hay ventana de tiempo donde un término
cacheado pueda quedar desactualizado respecto a la piscina, porque el cache
muere antes de que eso importe.

## 4. La Piscina vive del lado del modelo, no distribuida

Corrección de encuadre: la piscina (el índice dinámico, escrito con mayúscula
cuando "La Caja" refiere al sistema completo) **no vive repartida en los
nodos** — vive centralizada del lado del modelo que accede a La Caja. El
modelo tiene la piscina como fuente principal de verdad.

Esto reencuadra la pregunta de diseño pendiente: ya no es "¿cuánto cómputo
tolera cada nodo?" — es **¿cuánto ancho de banda necesita el troncal para que
las devoluciones de inferencia lleguen a la piscina sin cuello de botella?**
Pregunta de ingeniería de redes (throughput agregado), no de arquitectura de
IA (latencia de procesamiento por nodo).

## 5. Redundancia índice-nodo vs índice-piscina: justificada

La duplicación de datos entre el cache de una caja y el índice dinámico de la
piscina no es accidental — es el mismo trade-off que justifica cualquier
jerarquía de cache en hardware real (L1/L2/L3 vs RAM). Se paga el costo de
duplicar a propósito para evitar un viaje redondo por el troncal en cada
reuso de término dentro de la misma consulta.

Vale la pena solo si el mismo término se re-consulta *dentro de la misma
consulta* (razonamiento multi-hop). Si las consultas son de un solo salto, el
cache nodal es overhead sin beneficio.

---
*Preguntas abiertas para la próxima sesión: (1) resolver la contradicción del
§3; (2) definir si el cache tiene alcance de nodo individual o de vecindario;
(3) diseñar el programa de prueba (alimentador de diccionario + alimentador
de consultas) para medir si La Caja acelera o cuella de botella la resolución
de relaciones sin inferencia avanzada.*
