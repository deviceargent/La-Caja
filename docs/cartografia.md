# Cartografia de La Caja

Capa analitica SOLO LECTURA sobre la piscina viva: mide la forma del
grafo de memoria, superficie configuraciones que merecen examen y las
compara entre si, sin tocar el estado ni convertir hipotesis en
relaciones.

## Arquitectura de tres etapas

| Etapa | Modulo | Produce |
|---|---|---|
| A. Medicion | `la_caja.cartografia.medir` | propiedades estructurales reproducibles, sin etiquetas semanticas |
| B. Descubrimiento | `la_caja.cartografia.candidatos`, `comparacion` | candidatos con evidencia (mediciones que los dispararon) |
| C. Render | `la_caja.cartografia.visualizar` | HTML interactivo autocontenido + GEXF para Gephi |

La interpretacion semantica (etapa C de la directiva) queda fuera de
esta capa: nada aqui le pone significado a un patron, y nada escribe en
el grafo vivo.

## Los dos grafos extraidos

- **Navegacion** (`grafo_navegacion`): vertices = nodos de la piscina;
  aristas = las aristas explicitas (la unica conectividad de ruta que
  admite el nucleo). Peso = fuerza acumulada de las relaciones que la
  materializan.
- **Conceptos** (`grafo_conceptos`): vertices = burbujas. Dos capas de
  aristas que NO se mezclan (regla de oro del nucleo):
  - `observada`: relaciones con confianza 1.0 (peso = fuerza, con
    refuerzos y ultimo evento). Es la base de todas las metricas.
  - `activacion`: co-membresia en nodos compartidos. Se puede filtrar
    en la visualizacion; nunca cuenta como conexion estructural.

La inferencia (`0.5^k`) no se materializa: se consulta bajo demanda con
`piscina.relacion()` y se reporta aparte si hace falta.

## Cuatro distancias que no se equiparan

1. **Distancia de grafo**: saltos del camino mas corto (capa observada).
2. **Distancia ponderada**: fuerza de las relaciones observadas.
3. **Distancia semantica**: no existe en esta capa (no hay embeddings).
4. **Distancia de visualizacion**: posicion 2D del layout
   (`spring_layout`, semilla 0, determinista). Es una representacion,
   no una medida. El HTML lo declara explicitamente.

## Metricas implementadas (etapa A)

Global: terminos, nodos, relaciones observadas, aristas por capa,
componentes (tamanos), fraccion del gigante, densidad observada y de
navegacion, diametro del componente gigante (exacto hasta 400 nodos,
doble barrido despues; el metodo usado se reporta junto al valor),
longitud de camino promedio, modularidad (greedy determinista con
peso).

Distribuciones: grado medio/max, Gini de grado y de peso de burbujas,
histograma de grado.

Local: top-k grado, grado ponderado, intermediacion de nodos y de
aristas, clustering promedio, triangulos totales.

## Candidatos (etapa B)

Cada candidato lleva: `id`, `tipo`, `titulo`, `elementos` (terminos del
grafo vivo involucrados), `evidencia` (los numeros que lo dispararon),
`origen` (algoritmo + parametros). Tipos:

- `puente_nodo` / `puente_arista`: intermediacion desproporcionada
  (nodo que media sin concentrar; arista que sostiene trafico entre
  comunidades).
- `articulo`: nodos de corte (su ausencia desconecta).
- `frontera`: aristas observadas que cruzan la particion de
  comunidades.
- `isla`: componentes de 2..8 nodos. Lo esparcio tambien puede ser
  informativo: no se descarta por chico.
- `hub_anomalo`: grado con desviacion z >= 2 sobre la distribucion
  observada (descriptivo).
- `densidad_local`: clustering local muy por encima/debajo del global;
  cuando el grafo es chico enough se compara contra un modelo de
  configuracion (misma secuencia de grados, semilla fija); si no, el
  baseline queda `null` y el candidato se declara descriptivo.
- `traza_dormida`: parejas olvidadas con fuerza historica alta (capa
  inerte del nucleo): candidatas a rehidratacion SOLO si se re-observan.
- `motivo_recurrencia`: triangulos que cruzan comunidades.

Todos los umbrales viven en `CONFIG_DEFAULT` (documentados ahi); no hay
umbrales universales.

## Comparacion estructural entre subgrafos

`comparar_subgrafos` compara comunidades entre si aunque no exista
ninguna arista entre ellas: firma estructural (tamano, densidad,
clustering, histograma de grados normalizado, diametro) y similitud =
1 - promedio(distancia de Bhattacharyya de grados, distancia de forma).
La similitud estructural es un hallazgo a investigar, NO una relacion:
no crea aristas ni se interpreta semanticamente.

## Reproduccion

```powershell
$env:PYTHONPATH="src"
python -m pytest tests/test_cartografia.py -q     # tests de la capa
python experiments/exp_cartografia.py             # pipeline completo
# abre experiments/results/cartografia.html
```

## Limitaciones conocidas

- El layout es spring_layout 2D: para grafos grandes conviene el GEXF +
  Gephi (exportado incluido).
- La comparacion estructural usa firmas gruesas; subgrafos con el mismo
  histograma de grados pero topologia distinta pueden parecer similares.
- El diametro del componente gigante es aproximado arriba de 400 nodos
  (se reporta el metodo).
- El corpus de demo es un FIXTURE plantado
  (`experiments/corpus_cartografia.py`): sus patrones no son
  observaciones genuinas de un corpus real.
"""