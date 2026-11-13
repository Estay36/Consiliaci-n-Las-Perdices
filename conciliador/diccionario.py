"""Diccionario persistente RUT -> depto.

Se alimenta automáticamente con las asignaciones de confianza ALTA y puede
editarse a mano (Excel o cualquier editor). Con el tiempo, la mayoría de los
pagos se resuelve por RUT, que es la señal más confiable.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .normalizacion import clave_depto, normalizar_rut

COLUMNAS = ["rut", "depto", "nombre_referencia", "fuente", "actualizado"]


@dataclass
class FilaDiccionario:
    rut: str
    depto: str
    nombre_referencia: str = ""
    fuente: str = ""
    actualizado: str = ""


def cargar(ruta: str | Path) -> list[FilaDiccionario]:
    ruta = Path(ruta)
    if not ruta.exists():
        return []
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        lector = csv.DictReader(f, delimiter=";")
        filas = []
        for r in lector:
            rut = normalizar_rut(r.get("rut"))
            depto = clave_depto(r.get("depto"))
            if rut and depto:
                filas.append(FilaDiccionario(rut, depto, r.get("nombre_referencia", ""),
                                             r.get("fuente", ""), r.get("actualizado", "")))
        return filas


def guardar(ruta: str | Path, filas: list[FilaDiccionario]) -> None:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    filas = sorted(filas, key=lambda f: (f.depto, f.rut))
    with ruta.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.writer(f, delimiter=";")
        escritor.writerow(COLUMNAS)
        for x in filas:
            escritor.writerow([x.rut, x.depto, x.nombre_referencia, x.fuente, x.actualizado])


def incorporar(filas: list[FilaDiccionario], nuevas: list[tuple[str, str, str]]) -> int:
    """Agrega pares (rut, depto, nombre) que no existan. Retorna cuántos se agregaron."""
    existentes = {(f.rut, f.depto) for f in filas}
    hoy = date.today().isoformat()
    agregados = 0
    for rut, depto, nombre in nuevas:
        rut = normalizar_rut(rut)
        if rut and depto and (rut, depto) not in existentes:
            filas.append(FilaDiccionario(rut, depto, nombre, "auto", hoy))
            existentes.add((rut, depto))
            agregados += 1
    return agregados
