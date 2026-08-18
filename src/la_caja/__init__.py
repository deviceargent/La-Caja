"""Paquete La Caja -- nucleo canonico: memoria multi-pertenencia con
nodos-burbuja, conectividad estricta por aristas observadas y
persistencia event-sourced (PiscinaPersistente, opt-in via db_path)."""
from .core import LaCaja, Piscina, PiscinaPersistente, Caja, Nodo, Burbuja, FILTRO_ONTOLOGICO_DEFAULT, VENTANA_COOCURRENCIA, ALIASES_SINONIMOS

__version__ = "0.6.0"
__all__ = ["LaCaja", "Piscina", "PiscinaPersistente", "Caja", "Nodo", "Burbuja", "FILTRO_ONTOLOGICO_DEFAULT", "VENTANA_COOCURRENCIA", "ALIASES_SINONIMOS"]
