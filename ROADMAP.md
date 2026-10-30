# Hoja de ruta

Prioridad ordenada por riesgo tecnico y valor de informacion. No convertir cada idea historica en trabajo: solo se implementan mecanismos con un caso de uso y un criterio de verificacion.

## P0 — Cerrar el ciclo de instalacion y persistencia

- [x] Declarar dependencias de cartografia como extra opcional.
- [x] Corregir CI para instalar la extra y ejecutar la suite real.
- [x] Construir e instalar un wheel en un entorno limpio.
- [x] Exponer cierre explicito y context manager para SQLite.
- [ ] Verificar la rama en GitHub Actions y mergear el PR.
- [ ] Revisar el diff de los artefactos HTML/GEXF regenerados y decidir si son resultados canonicos.

## P1 — Aislamiento y robustez del nucleo

- [x] Encapsular la secuencia de IDs por Piscina y probar independencia entre instancias.
- [x] Aislar alias runtime por instancia.
- [ ] Decidir y probar persistencia de alias declarados en SQLite.
- [ ] Definir y probar comportamiento ante error SQLite despues de una mutacion en memoria.
- [ ] Agregar pruebas de concurrencia y documentar si una instancia es thread-safe.
- [ ] Probar recuperacion ante terminacion abrupta durante commit/snapshot.

## P2 — Producto utilizable

- [x] Agregar una CLI para observar, ingerir, consultar, primar, inspeccionar y exportar cartografia.
- [ ] Proveer ejemplos ejecutables de memoria efimera, persistente, lote y rehidratacion.
- [ ] Definir formato de importacion/exportacion portatil para respaldar una Piscina.
- [ ] Probar instalacion en Python 3.10–3.13 y Windows/Linux.
- [ ] Publicar una version nueva solo despues de probar wheel, sdist y CI.

## P3 — Validacion empirica

- [ ] Ejecutar cartografia sobre una memoria organica con datos autorizados y registrar escala/tiempos.
- [ ] Diseñar el control de inyeccion lexical/frecuencia para el benchmark pareado.
- [ ] Reportar resultados por documento y no solo por consulta cuando exista dependencia entre consultas.
- [ ] Separar explicitamente evidencia de utilidad downstream de evidencia de calidad estructural.
- [ ] Mantener resultados falsos y nulos en el registro canonico.

## P4 — Integracion externa

- [ ] Auditar el contrato del repositorio hermano `la-caja-mcp` contra la API actual.
- [ ] Verificar persistencia compartida y ciclo de vida desde los servidores MCP.
- [ ] Mantener Cloudflare como transporte opcional, no como dependencia del nucleo.

## Fuera de alcance hasta nueva evidencia

- Reinstaurar Super Index/Boxes/Trunk como arquitectura obligatoria.
- Incorporar embeddings o un LLM dentro del nucleo.
- Convertir trazas dormidas en prediccion sin un experimento que lo justifique.
