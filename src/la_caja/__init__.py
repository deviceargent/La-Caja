"""Paquete La Caja -- nucleo canonico: memoria multi-pertenencia con
nodos-burbuja y conectividad estricta por aristas observadas."""
from .core import LaCaja, Piscina, Caja, Nodo, Burbuja, FILTRO_ONTOLOGICO_DEFAULT, VENTANA_COOCURRENCIA

__version__ = "0.4.0"
__all__ = ["LaCaja", "Piscina", "Caja", "Nodo", "Burbuja", "FILTRO_ONTOLOGICO_DEFAULT", "VENTANA_COOCURRENCIA"]
