"""Línea de comandos del conciliador.

Ejemplo:
    python conciliar.py --cartola cartola.xlsx --madre Ingresos_Las_Perdices.xlsx --hoja Oct26 \
        --ultimo-fecha 10/10/2026 --ultimo-monto 120645 --ultimo-nombre "María Cecilia Salazar"

Si se omite el último pago, se toma el más reciente registrado en la hoja anterior
(o en la misma hoja, si ya tiene ingresos).
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from conciliador import ParametrosCorrida, ejecutar

BASE = Path(__file__).resolve().parent


def _fecha(texto: str) -> datetime:
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            return datetime.strptime(texto, fmt)
        except ValueError:
            pass
    raise argparse.ArgumentTypeError(f"Fecha inválida: {texto} (use dd/mm/aaaa)")


def _monto(texto: str) -> int:
    return int(texto.replace("$", "").replace(".", "").replace(",", "").strip())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Concilia la cartola con la planilla de ingresos.")
    ap.add_argument("--cartola", required=True, help="Cartola detallada (.xlsx)")
    ap.add_argument("--madre", required=True, help="Planilla madre de ingresos (.xlsx)")
    ap.add_argument("--hoja", required=True, help="Hoja a rellenar, ej. Oct26")
    ap.add_argument("--ultimo-fecha", type=_fecha, help="Fecha del último pago registrado (dd/mm/aaaa)")
    ap.add_argument("--ultimo-monto", type=_monto, help="Monto del último pago registrado")
    ap.add_argument("--ultimo-nombre", default="", help="Nombre del último pago registrado (desempate)")
    ap.add_argument("--hasta", type=_fecha, help="Procesar solo hasta esta fecha (opcional)")
    ap.add_argument("--sufijo-id", help="Sufijo del ID, ej. 1026 (por defecto se infiere de la hoja)")
    ap.add_argument("--id-inicial", type=int, help="Número del primer ID (por defecto, continúa la hoja)")
    ap.add_argument("--diccionario", default=str(BASE / "datos" / "diccionario_pagadores.csv"),
                    help="CSV RUT -> depto")
    ap.add_argument("--salida", help="Ruta del Excel de salida")
    ap.add_argument("--sin-colores", action="store_true", help="No colorear filas a revisar")
    a = ap.parse_args(argv)

    res = ejecutar(ParametrosCorrida(
        ruta_cartola=a.cartola, ruta_madre=a.madre, hoja=a.hoja,
        ultimo_fecha=a.ultimo_fecha, ultimo_monto=a.ultimo_monto, ultimo_nombre=a.ultimo_nombre,
        hasta=a.hasta, sufijo_id=a.sufijo_id, id_inicial=a.id_inicial,
        ruta_diccionario=a.diccionario, ruta_salida=a.salida, colorear=not a.sin_colores))

    for k, v in res.resumen.items():
        if isinstance(v, list):
            print(f"\n{k}:")
            for item in v or ["(ninguna)"]:
                print(f"  - {item}")
        else:
            print(f"{k}: {v}")
    print(f"\nArchivo generado: {res.ruta_salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
