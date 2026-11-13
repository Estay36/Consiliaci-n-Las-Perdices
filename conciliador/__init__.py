"""Conciliación de ingresos de cuenta corriente contra la planilla de ingresos del condominio."""
from .config import Config
from .pipeline import ParametrosCorrida, ResultadoCorrida, ejecutar

__all__ = ["Config", "ParametrosCorrida", "ResultadoCorrida", "ejecutar"]
__version__ = "1.0.0"
