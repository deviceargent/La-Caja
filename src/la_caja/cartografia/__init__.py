"""Cartografia de La Caja -- medicion estructural, descubrimiento de
candidatos y visualizacion del grafo de memoria.

Protocolo de tres etapas (separadas por diseno):

  A. MEDICION      (medir.py)      -- propiedades reproducibles del grafo,
                                       sin etiquetas semanticas.
  B. DESCUBRIMIENTO (candidatos.py, comparacion.py) -- regiones y
                                       configuraciones que merecen examen,
                                       cada una con su evidencia.
  C. INTERPRETACION -- fuera de esta capa; nada aqui convierte una
                       hipotesis en relacion del grafo vivo.

Reglas heredadas del nucleo:
  - ARISTA = navegacion; PERTENENCIA = activacion (no mezclar).
  - Lo observado (confianza 1.0) nunca se confunde con lo inferido
    (0.5^k): la capa de inferencia se reporta aparte.
  - La medicion es SOLO LECTURA: nunca muta la piscina ni fabrica
    relaciones. Las hipotesis viven en el reporte, no en el grafo.
"""
from .medir import grafo_navegacion, grafo_conceptos, grafo_observado, medir
from .candidatos import descubrir, CONFIG_DEFAULT
from .comparacion import comparar_subgrafos

__all__ = [
    "grafo_navegacion",
    "grafo_conceptos",
    "grafo_observado",
    "medir",
    "descubrir",
    "comparar_subgrafos",
    "CONFIG_DEFAULT",
]
