"""Estructuras de datos compartidas."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

# Categorías de ingreso
CAT_GC = "GASTO COMÚN"
CAT_QUINCHO = "QUINCHO"
CAT_CF = "COMUNIDAD FELIZ"
CAT_OTRO = "OTRO"


@dataclass
class Transaccion:
    fecha: datetime
    hora: str
    monto: int
    nombre_banco: str
    rut: str
    comentario: str
    tipo: str
    glosa: str
    codigo: str
    banco_origen: str
    categoria: str = CAT_GC
    posicion: int = 0  # orden cronológico dentro de la cartola


@dataclass
class Asignacion:
    txn: Transaccion
    id_interno: str = ""
    depto: str = ""            # clave de depto (o etiqueta OTROS) asignada
    confianza: str = ""
    metodo: str = ""
    nombre_planilla: str = ""
    observaciones: list[str] = field(default_factory=list)
    alternativas: list[str] = field(default_factory=list)
    fila_depto: int | None = None    # fila en bloque por depto
    fila_cronologico: int | None = None


@dataclass
class EntradaHistorial:
    depto: str
    nombre: str
    monto: int | None
    fecha: datetime | None
    hoja: str
    fuente: str  # 'historial' | 'residentes' | 'encontrados' | 'diccionario'
    rut: str = ""
