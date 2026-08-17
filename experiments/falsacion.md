# Experimento de memoria de largo plazo — criterios pre-registrados

Fecha de pre-registro: 17/8/2026.
Estado: este documento se fija **antes** de correr cualquier test. Los
resultados se juzgan contra estos criterios, no al reves.

## Pregunta

Tras anos de interaccion, la memoria de La Caja:

1. ¿Conserva discriminacion entre lo OBSERVADO y lo INFERIDO, o el
   cierre transitivo densifica el grafo hasta "saber todo conectado"
   (alucinacion)?
2. ¿Es fiel a la realidad observada (las asociaciones que el modelo
   marca como observadas son las que realmente co-ocurren en la vida
   del sujeto)?
3. ¿Recupera temas dormidos? Cuando un tema vuelve a aparecer despues
   de tiempo, ¿el primado de contexto resucita los conceptos del tema?

## Datos (organicos, no sinteticos)

Dos corrientes de registro opuesto:

- **Corriente laboral — Enron:** la bandeja de SALIDA de un usuario
  real (jeff.dasovich, 1998-12 a 2002-09, ~3.8 anos), ordenada por
  fecha. Emails tal cual, con sus ruidos (quotes, firmas, reenvios).
- **Corriente personal/online — Blog Authorship Corpus (Schler et
  al.):** el autor con mas posts del corpus (blogger.com, 2004),
  monologo en primera persona, ordenado por fecha.

Higiene (pre-registrada):
- Dedupe exacto de cuerpos (los reenvios inflan duplicados).
- Se descartan documentos con menos de 3 tokens no-funcionales.
- Filtro ontologico en INGLES (el default del modelo es espanol).
- Las fechas placeholder de Enron (1980-01-01) se descartan.
- Se corre `optimizar()` cada 200 documentos (la consolidacion natural
  decay+fision que un companero real haria).

## Setup del modelo

- `LaCaja(filtro_ontologico=INGLES)`, constantes por defecto
  (VENTANA_COOCURRENCIA=4, UMBRAL_DECAY_EVENTOS=50, etc.).
- Una consulta = un documento (email / post), en orden temporal.

## Test A — discriminacion / no-densificacion

Sobre el estado final (y como serie temporal en 25/50/75/100% de la
corriente):

- **A1. Conectividad aleatoria:** fraccion de pares aleatorios con
  `consultar(a, b) > 0`, sobre (i) todo el vocabulario y (ii) los 500
  terminos mas frecuentes.
  - FALSA si fraccion > 0.10 (la memoria "sabe todo conectado").
- **A2. Confianza de pares aleatorios:** media y percentil 95 de la
  confianza sobre los mismos pares.
  - FALSA si media > 0.01 o p95 > 0.25.
- **A3. Componente gigante:** mayor componente conexo del grafo de
  nodos (DSU sobre aristas).
  - FALSA si contiene > 50% de los nodos (la estructura se fundio).

## Test B — fidelidad al corpus

Ground truth = co-ocurrencia dentro de la MISMA ventana que el modelo
(VENTANA_COOCURRENCIA=4), sobre el corpus completo (contra del
corpus, no del modelo):

- **B1. Precision:** percentil medio de rango de co-ocurrencia de los
  pares OBSERVADOS (self.relaciones) entre todos los pares.
  - FALSA si percentil medio < 50 (el modelo marcaria como observado
    lo que no co-ocurre especialmente).
- **B2. Recall:** fraccion de los top-K pares co-ocurrentes del corpus
  (K = numero de relaciones) que son relaciones del modelo.
  - FALSA si recall < 0.30.
- **B3. Discriminacion:** co-ocurrencia media de pares observados (1.0)
  > pares inferidos (0.5/0.25) > pares aleatorios.
  - FALSA si observado <= inferido (la confianza no ordena nada).

## Test C — recuperacion temporal

Corte temporal en 60% (pasado) / 40% (futuro). La memoria se construye
con el pasado. Para cada documento futuro, y cada termino `t` del
documento conocido en el pasado, se consulta `contexto_primado(t, 5)`
ANTES de ingerir el documento; acierto = terminos del MISMO documento
futuro (conocidos) que aparecen en el primado.

- **C1. hit@5** medio sobre documentos futuros con >= 2 terminos
  conocidos.
  - Baselines: (a) terminos aleatorios conocidos, (b) terminos mas
    frecuentes de la memoria.
  - FALSA si hit@5 <= max(aleatorio, frecuencia).
- **C2. Umbral absoluto:** hit@5 >= 0.15 (la recuperacion debe ser
  materialmente util, no solo mejor que el azar).
  - FALSA si hit@5 < 0.15.

## Correcciones post-harness (17/8/2026, antes de los runs finales)

Dos errores de DISEÑO del harness (no de umbrales) detectados al correr
el piloto sobre el blog. Se corrigen documentandolos aqui; ningun
umbral de falsacion cambia:

1. **Baseline aleatorio del Test C (trampa):** muestreaba los 5
   terminos de `conocidos` — los terminos del propio documento futuro
   que se busca recuperar. El azar "sabia la respuesta". Corregido a
   muestrear del VOCABULARIO de la memoria (lo que el primado podria
   devolver de verdad).
2. **Orden de B3 (logicamente imposible):** el criterio exigia
   observado > inferido > aleatorio. Pero los pares INFERIDOS son por
   definicion los que NO co-ocurrieron, asi que su co-ocurrencia media
   es ~0 siempre, mientras el azar co-ocurre una fraccion positiva del
   tiempo (algunos pares aleatorios co-ocurren de verdad). Exigir
   inferido > aleatorio es imposible de satisfacer. El criterio
   correcto es observado > max(inferido, aleatorio): lo observado debe
   co-ocurrir de verdad; lo inferido no. Que inferido <= aleatorio es
   la discriminacion trabajando, no un fallo.

## Decisicion

Los criterios estan fijados aqui y no se ajustaran a la vista de los
resultados. Se reportan por corriente. Si una corriente falla un
criterio, el claim correspondiente queda REFUTADO para ese registro;
si sobrevive en ambas, la tesis es robusta al registro.

## Fuentes

- Enron Email Dataset (CMU), version limpia `corbt/enron-emails`
  (Hugging Face), parquet `train-00000-of-00003.parquet`.
- Blog Authorship Corpus (Schler, Koppel, Argamon, Pennebaker 2006),
  mirror `barilan/blog_authorship_corpus` (Hugging Face), `blogs.zip`.
- Solo uso local, sin publicar los datos.