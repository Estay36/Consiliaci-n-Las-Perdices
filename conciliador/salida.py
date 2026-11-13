"""Escritura del Excel de salida.

Hoja 1 (mismo nombre que la hoja objetivo): copia exacta de la hoja de la planilla
madre con los bloques A:F e I:M rellenados, lista para copiar y pegar.
Hoja 'Revisión': detalle de cada ingreso con el método y la confianza de la asignación.
Hoja 'Resumen': totales y alertas de la corrida.
"""
from __future__ import annotations

from copy import copy
from datetime import datetime

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .config import CONFIANZA_ALTA, CONFIANZA_BAJA, CONFIANZA_MEDIA, SIN_MATCH, Config
from .modelos import CAT_CF, Asignacion

FORMATO_FECHA = "dd-mm-yyyy"
FORMATO_MONTO = '_ "$"* #,##0_ ;_ "$"* \\-#,##0_ ;_ "$"* "-"_ ;_ @_ '

RELLENOS = {
    CONFIANZA_ALTA: PatternFill("solid", fgColor="E2EFDA"),
    CONFIANZA_MEDIA: PatternFill("solid", fgColor="FFF2CC"),
    CONFIANZA_BAJA: PatternFill("solid", fgColor="FCE4D6"),
    SIN_MATCH: PatternFill("solid", fgColor="F8CBAD"),
    "—": PatternFill("solid", fgColor="DDEBF7"),
}
ENCABEZADO = PatternFill("solid", fgColor="1F3864")


def _formato_desde(ws, fila_ref: int, col: int, por_defecto: str) -> str:
    fmt = ws.cell(fila_ref, col).number_format
    return fmt if fmt and fmt != "General" else por_defecto


def escribir_salida(ruta_madre, hoja: str, asignaciones: list[Asignacion], resumen: dict,
                    ruta_salida, cfg: Config | None = None, colorear: bool = True) -> None:
    cfg = cfg or Config()
    lay = cfg.layout
    wb = load_workbook(ruta_madre)
    for nombre in list(wb.sheetnames):
        if nombre != hoja:
            del wb[nombre]
    ws = wb[hoja]

    fmt_fecha = _formato_desde(ws, lay.fila_inicio, lay.col_fecha, FORMATO_FECHA)
    fmt_monto = _formato_desde(ws, lay.fila_inicio, lay.col_monto, FORMATO_MONTO)

    for a in asignaciones:
        fecha = datetime(a.txn.fecha.year, a.txn.fecha.month, a.txn.fecha.day)
        # Bloque por depto
        if a.fila_depto:
            r = a.fila_depto
            ws.cell(r, lay.col_id, a.id_interno).number_format = "@"
            c = ws.cell(r, lay.col_fecha, fecha)
            c.number_format = fmt_fecha
            ws.cell(r, lay.col_monto, a.txn.monto).number_format = fmt_monto
            ws.cell(r, lay.col_nombre, a.nombre_planilla)
            if a.confianza in (CONFIANZA_MEDIA, CONFIANZA_BAJA):
                ws.cell(r, lay.col_coment, "REVISAR: " + "; ".join(a.observaciones or [a.metodo]))
            if colorear and a.confianza in (CONFIANZA_MEDIA, CONFIANZA_BAJA):
                for col in range(lay.col_id, lay.col_coment + 1):
                    ws.cell(r, col).fill = RELLENOS[a.confianza]
        # Bloque cronológico
        r = a.fila_cronologico
        ws.cell(r, lay.col_c_id, a.id_interno).number_format = "@"
        ws.cell(r, lay.col_c_fecha, fecha).number_format = fmt_fecha
        ws.cell(r, lay.col_c_monto, a.txn.monto).number_format = fmt_monto
        ws.cell(r, lay.col_c_nombre, a.nombre_planilla)
        if ws.cell(r, lay.col_c_encontrado).value in (None, ""):
            ws.cell(r, lay.col_c_encontrado,
                    f'=IF(COUNTIF($B${lay.fila_inicio}:$B$1016,I{r})>0,"Sí","No")')
        if colorear and not a.fila_depto and a.txn.categoria != CAT_CF:
            for col in range(lay.col_c_id, lay.col_c_nombre + 1):
                ws.cell(r, col).fill = RELLENOS[SIN_MATCH]

    _hoja_revision(wb, asignaciones)
    _hoja_resumen(wb, resumen)
    wb.active = 0
    wb.save(ruta_salida)


def _encabezados(ws, titulos: list[str], anchos: list[int]) -> None:
    for i, (t, w) in enumerate(zip(titulos, anchos), start=1):
        c = ws.cell(1, i, t)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = ENCABEZADO
        c.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    ws.row_dimensions[1].height = 30


def _hoja_revision(wb, asignaciones: list[Asignacion]) -> None:
    ws = wb.create_sheet("Revisión")
    titulos = ["ID", "Fecha", "Hora", "Monto", "Nombre en cartola", "RUT", "Comentario transferencia",
               "Categoría", "Depto asignado", "Confianza", "Método", "Nombre en planilla",
               "Observaciones", "Alternativas", "Fila depto", "Fila cronológico", "Código transferencia"]
    anchos = [10, 11, 7, 12, 34, 12, 40, 16, 12, 11, 30, 30, 55, 14, 9, 9, 18]
    _encabezados(ws, titulos, anchos)
    for i, a in enumerate(asignaciones, start=2):
        t = a.txn
        fila = [a.id_interno, datetime(t.fecha.year, t.fecha.month, t.fecha.day), t.hora, t.monto,
                t.nombre_banco, t.rut, t.comentario, t.categoria, a.depto, a.confianza, a.metodo,
                a.nombre_planilla, "; ".join(a.observaciones), ", ".join(a.alternativas),
                a.fila_depto or "", a.fila_cronologico or "", t.codigo]
        for j, v in enumerate(fila, start=1):
            c = ws.cell(i, j, v)
            c.alignment = Alignment(vertical="top", wrap_text=j in (7, 13))
        ws.cell(i, 2).number_format = FORMATO_FECHA
        ws.cell(i, 4).number_format = FORMATO_MONTO
        relleno = RELLENOS.get(a.confianza)
        if relleno:
            ws.cell(i, 10).fill = relleno
            ws.cell(i, 9).fill = copy(relleno)
    ws.auto_filter.ref = f"A1:{get_column_letter(len(titulos))}{max(2, len(asignaciones) + 1)}"


def _hoja_resumen(wb, resumen: dict) -> None:
    ws = wb.create_sheet("Resumen")
    ws.column_dimensions["A"].width = 42
    ws.column_dimensions["B"].width = 70
    ws.cell(1, 1, "Resumen de la conciliación").font = Font(bold=True, size=13)
    r = 3
    for clave, valor in resumen.items():
        if isinstance(valor, list):
            ws.cell(r, 1, clave).font = Font(bold=True)
            r += 1
            for item in valor or ["(ninguna)"]:
                ws.cell(r, 2, item).alignment = Alignment(wrap_text=True)
                r += 1
        else:
            ws.cell(r, 1, clave).font = Font(bold=True)
            c = ws.cell(r, 2, valor)
            if isinstance(valor, int) and "Monto" in clave:
                c.number_format = FORMATO_MONTO
            c.alignment = Alignment(horizontal="left")
            r += 1
