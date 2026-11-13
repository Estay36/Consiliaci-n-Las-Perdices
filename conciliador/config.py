"""Parámetros de configuración del conciliador.

Todo lo que puede cambiar entre condominios o bancos está centralizado aquí:
montos especiales, nombres de columnas de la cartola y layout de la planilla madre.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ColumnasCartola:
    """Nombres de columna de la cartola detallada (formato Banco de Chile)."""

    fecha: str = "Fecha de transacción"
    hora: str = "Hora transacción"
    codigo: str = "Código Transferencia"
    tipo: str = "Tipo de transacción"
    glosa: str = "Glosa detalle"
    ingreso: str = "Ingreso (+)"
    nombre: str = "Nombre"
    rut: str = "RUT"
    banco: str = "Banco"
    comentario: str = "Comentario transferencia"


@dataclass
class LayoutPlanilla:
    """Posición de los bloques dentro de cada hoja mensual (columnas 1-indexadas)."""

    fila_encabezado: int = 4
    fila_inicio: int = 5
    # Bloque "INGRESOS POR DEPTO"
    col_depto: int = 1   # A
    col_id: int = 2      # B
    col_fecha: int = 3   # C
    col_monto: int = 4   # D
    col_nombre: int = 5  # E
    col_coment: int = 6  # F
    # Bloque "INGRESOS CRONOLÓGICO"
    col_c_id: int = 9          # I
    col_c_fecha: int = 10      # J
    col_c_monto: int = 11      # K
    col_c_nombre: int = 12     # L
    col_c_encontrado: int = 13  # M
    # Bloque "Encontrados" (nombre -> depto)
    col_enc_nombre: int = 19  # S
    col_enc_depto: int = 21   # U
    marcador_otros: str = "OTROS"
    hoja_residentes: str = "Datos Residentes"
    max_filas: int = 1100


@dataclass
class Config:
    monto_quincho: int = 40000
    etiquetas_quincho: tuple = ("quincho", "reserva eventos", "sala de eventos")
    nombre_cf: str = "Comunidad Feliz"
    tipo_cf: str = "PAGO_MASIVO"
    texto_cf: str = "COMUNIDAD FELIZ"
    # Días hacia atrás para buscar posibles duplicados en hojas anteriores
    ventana_duplicados_dias: int = 45
    cartola: ColumnasCartola = field(default_factory=ColumnasCartola)
    layout: LayoutPlanilla = field(default_factory=LayoutPlanilla)


MESES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}

CONFIANZA_ALTA = "ALTA"
CONFIANZA_MEDIA = "MEDIA"
CONFIANZA_BAJA = "BAJA"
SIN_MATCH = "SIN MATCH"
