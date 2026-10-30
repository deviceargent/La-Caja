# La Caja — arquitectura vigente

Estado de referencia: implementacion Python del modelo multi-pertenencia, actualmente version 0.7.0. Este documento describe el codigo ejecutable de `src/la_caja/`; las especificaciones historicas v2.0 y v2.1 se conservan en `docs/` como registro de ideas y decisiones previas, no como contrato de implementacion vigente.

## 1. Modelo de ejecucion

La implementacion se organiza en cuatro piezas:

- **Burbuja**: un termino canonico con peso y marca temporal de ultimo refuerzo.
- **Nodo**: un contexto de co-ocurrencia que agrupa burbujas. Un termino puede pertenecer a varios nodos.
- **Piscina**: estado vivo compartido: burbujas, nodos, relaciones observadas, indices de primado y trazas dormidas.
- **Caja**: procesador transitorio de una consulta. No tokeniza; recibe terminos ya normalizados, filtra y emite mutaciones hacia la Piscina.
- **LaCaja**: API de alto nivel: tokenizacion, normalizacion, orquestacion y acceso a la Piscina.

La persistencia es una implementacion alternativa de la Piscina: `PiscinaPersistente` agrega event sourcing sobre SQLite. LaCaja elige Piscina en memoria cuando no se pasa `db_path`, y PiscinaPersistente cuando se pasa.

## 2. Invariantes estructurales

1. Una burbuja representa un termino y puede pertenecer a multiples nodos; no hay exilio por cambio de contexto.
2. La pertenencia expresa activacion/primado. No constituye por si misma una ruta de navegacion.
3. Las rutas se materializan mediante aristas explicitas entre conceptos establecidos. Compartir un termino en consultas distintas no crea un puente.
4. La co-ocurrencia de terminos nuevos crea contexto compartido; la co-ocurrencia de terminos ya establecidos puede reforzar una relacion observada.
5. La ventana de co-ocurrencia por defecto es 4 terminos previos por termino de la secuencia. No es una comparacion todos-contra-todos.
6. La confianza de una relacion observada es 1.0. Una ruta inferida se calcula bajo demanda y decrece como `0.5 ** puentes`; la busqueda tiene un maximo de 10 saltos por defecto.
7. La capa de activacion y la capa de navegacion permanecen separadas.

## 3. Identidad, ingesta y consolidacion

`LaCaja.procesar_consulta(texto)` tokeniza, canoniza alias y morfologia derivativa segura, y delega el procesamiento en una Caja transitoria. El filtro ontologico elimina palabras funcionales y numeros puros; los tokens alfanumericos como `pc98` y `h264` se conservan.

La capacidad de asociacion se controla mediante `VENTANA_COOCURRENCIA = 4`. `optimizar()` aplica olvido y fision de membresias sobrecargadas. El umbral de fision por defecto es 8 membresias por termino.

### Olvido

El reloj del modelo es el conteo de eventos de mutacion, no el tiempo de pared. Esto permite replay determinista.

- Los pesos de terminos decaen tras 50 eventos de no-uso hacia un piso de 1.
- Las relaciones tienen una escala propia, mas lenta, y una gracia multiplicativa basada en el numero de refuerzos: `400 * 3 ** refuerzos`.
- Una relacion que llega a fuerza cero se poda junto con las aristas exactas que materializaba.
- La traza dormida conserva informacion historica de relaciones olvidadas, pero no participa en navegacion ni primado.
- La rehidratacion es opt-in y solo ocurre cuando la pareja vuelve a co-ocurrir; la traza no predice asociaciones futuras.

### Promocion y primado

El nivel de promocion se deriva del peso de una burbuja. No crea rutas ni modifica el grafo. `contexto_primado()` devuelve un paquete acotado de relaciones observadas y contexto de activacion.

## 4. Persistencia

`PiscinaPersistente` registra las mutaciones como pares metodo/argumentos en una tabla append-only de SQLite. La reconstruccion carga el snapshot mas reciente y reproduce los eventos posteriores usando los mismos metodos base de Piscina.

- Snapshot automatico cada 1000 eventos por defecto.
- Se conservan los dos snapshots mas recientes.
- `lote()` difiere commits y toma un snapshot al salir; los lotes anidados quedan bajo el control del externo.
- `LaCaja.close()` confirma eventos pendientes y cierra SQLite. `LaCaja` tambien implementa el protocolo de context manager.
- Cerrar dentro de un lote activo esta prohibido. Reutilizar una piscina persistente cerrada produce RuntimeError.

La persistencia es opt-in; el modo en memoria no crea archivos.

## 5. Cartografia

`la_caja.cartografia` es una capa analitica de solo lectura. Construye grafos de navegacion y conceptos, mide propiedades, descubre candidatos con evidencia y exporta HTML autocontenido o GEXF. Los candidatos son hipotesis para examen; no mutan la Piscina.

Instalacion: `pip install "la-caja[cartografia]"`. La extra instala NetworkX y NumPy, necesarios para analisis y layout.

La validacion automatizada usa un fixture sintetico con patrones plantados. No equivale a validar la cartografia sobre una memoria organica real.

## 6. API publica principal

- `LaCaja()`: memoria efimera en proceso.
- `LaCaja(db_path="memoria.db")`: memoria persistente.
- `procesar_consulta(texto)`: ingesta de texto.
- `declarar_relacion(a, b)`: ingesta de un par de conceptos.
- `consultar(a, b)`: confianza observada/inferida.
- `contexto_primado(termino, presupuesto)`: contexto asociado.
- `historial(termino)`: trazas dormidas.
- `stats()`: conteos de terminos, nodos y aristas.
- `optimizar()`: olvido y fision.
- `lote()`: ingesta por lotes; requiere persistencia.
- `close()` / `with LaCaja(...) as caja`: ciclo de vida de SQLite.

Las rutas de lectura de `LaCaja` (`consultar`, `nivel`, `contexto_primado`, `historial`) canonizan los terminos mediante el mismo mapa de alias que la ingesta.

La CLI `la-caja` cubre observacion, ingesta por archivo, relaciones, consultas, primado, estadisticas, historial, optimizacion y exportacion cartografica. La API Python sigue siendo la interfaz completa.

## 7. Componentes historicos o externos

- **Super Index, Access Pillars, Trunk/Branches y Boxes**: arquitectura de referencia inicial del 11 de agosto. Fue reemplazada por el modelo burbuja-nodo el 15 de agosto; no son modulos pendientes de implementar en el nucleo actual.
- **Cache nodal**: discutido en el addendum v2.1, sin implementacion en el codigo vigente.
- **MCP y protocolo de deliberacion**: viven en el repositorio hermano `la-caja-mcp`; no forman parte del paquete Python de este repositorio.
- **Cloudflare MCP**: linea de transporte historica; no es requisito para usar la biblioteca local.

## 8. Limites conocidos y trabajo pendiente

- No hay pruebas de concurrencia multi-hilo ni de multiples escritores SQLite.
- Los IDs de nodo se asignan con una secuencia local a cada Piscina; los snapshots reconstruyen el contador desde los IDs vigentes.
- Los alias declarados en runtime son locales a cada instancia de LaCaja. No se guardan en SQLite; al reabrir una memoria se usan los alias declarativos por defecto.
- La cartografia esta probada con fixtures, no con una memoria organica de escala real.
- Los resultados experimentales no demuestran superioridad general sobre frecuencia ni recuperacion de temas de largo plazo. Ver `experiments/falsacion.md` y `experiments/writeup.md`.

## 9. Verificacion

La suite actual contiene 82 tests. CI instala el paquete con la extra cartografica y ejecuta `python -m pytest tests -q`. La prueba de empaquetado debe instalar el wheel en un entorno limpio, no solo importar desde el checkout.
