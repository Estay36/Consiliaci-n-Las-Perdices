"""Lectura de la planilla madre: layout de la hoja a rellenar e historial de pagos."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from .config import MESES, Config
from .modelos import EntradaHistorial
from .normalizacion import clave_depto, normalizar_rut, normalizar_texto, parsear_monto


@dataclass
class Cupo:
    fila: int
    etiqueta: str        # valor de la columna A tal como aparece
    clave: str           # clave canónica
    ocupado: bool = False


@dataclass
class LayoutHoja:
    nombre: str
    cupos_depto: dict[str, list[Cupo]] = field(default_factory=dict)
    cupos_quincho: list[Cupo] = field(default_factory=list)
    fila_siguiente_cronologico: int = 5
    ultimo_id: int = 0
    ultimo_registrado: tuple | None = None  # (id, fecha, monto, nombre)

    @property
    def deptos_validos(self) -> set[str]:
        return set(self.cupos_depto)


@dataclass
class RegistroCronologico:
    id: str
    fecha: datetime | None
    monto: int | None
    nombre: str
    hoja: str


@dataclass
class DatosPlanilla:
    hojas_mensuales: list[str]
    layout: LayoutHoja
    historial: list[EntradaHistorial]
    cronologico_previo: list[RegistroCronologico]
    hoja_anterior: str | None


def _es_hoja_mensual(ws: Worksheet, cfg: Config) -> bool:
    lay = cfg.layout
    for r in range(1, lay.fila_encabezado + 3):
        v = ws.cell(r, lay.col_depto).value
        if isinstance(v, str) and v.strip().upper() == "DEPARTAMENTO":
            return True
    return False


def _num_id(id_texto) -> int:
    m = re.match(r"\s*(\d+)", str(id_texto or ""))
    return int(m.group(1)) if m else 0


def _a_entero(v) -> int | None:
    """Convierte montos numéricos o de texto ('$141.245', '141.245', '141245,0') a entero."""
    return parsear_monto(v)


def sufijo_desde_hoja(nombre_hoja: str) -> str:
    """'Oct26' -> '1026'. Se usa como sufijo del ID interno."""
    m = re.match(r"([A-Za-z]{3})\D*(\d{2})", nombre_hoja.strip())
    if not m or m.group(1).lower() not in MESES:
        raise ValueError(f"No se pudo inferir mes/año desde el nombre de hoja '{nombre_hoja}'. "
                         "Indique el sufijo de ID manualmente (ej. 1026).")
    return f"{MESES[m.group(1).lower()]:02d}{m.group(2)}"


def leer_layout(ws: Worksheet, cfg: Config) -> LayoutHoja:
    lay = cfg.layout
    layout = LayoutHoja(nombre=ws.title)
    en_otros = False
    for r in range(lay.fila_inicio, min(ws.max_row, lay.max_filas) + 1):
        etiqueta = ws.cell(r, lay.col_depto).value
        if etiqueta is None:
            continue
        clave = clave_depto(etiqueta)
        if clave == lay.marcador_otros.upper():
            en_otros = True
            continue
        ocupado = ws.cell(r, lay.col_id).value not in (None, "")
        cupo = Cupo(fila=r, etiqueta=str(etiqueta), clave=clave, ocupado=ocupado)
        if en_otros:
            if any(k in normalizar_texto(etiqueta) for k in cfg.etiquetas_quincho):
                layout.cupos_quincho.append(cupo)
        else:
            layout.cupos_depto.setdefault(clave, []).append(cupo)

    # Bloque cronológico ya existente (si la hoja se está completando por segunda vez)
    ultima_fila = lay.fila_inicio - 1
    mejor = None
    for r in range(lay.fila_inicio, min(ws.max_row, lay.max_filas) + 1):
        idv = ws.cell(r, lay.col_c_id).value
        if idv in (None, ""):
            continue
        ultima_fila = r
        layout.ultimo_id = max(layout.ultimo_id, _num_id(idv))
        fecha = ws.cell(r, lay.col_c_fecha).value
        reg = (str(idv), fecha, _a_entero(ws.cell(r, lay.col_c_monto).value),
               str(ws.cell(r, lay.col_c_nombre).value or ""))
        if isinstance(fecha, datetime) and (mejor is None or (fecha, _num_id(idv)) >= (mejor[1], _num_id(mejor[0]))):
            mejor = reg
    layout.fila_siguiente_cronologico = ultima_fila + 1
    layout.ultimo_registrado = mejor
    return layout


def _leer_historial_hoja(ws: Worksheet, cfg: Config, validos: set[str]):
    lay = cfg.layout
    entradas: list[EntradaHistorial] = []
    crono: list[RegistroCronologico] = []
    en_otros = False
    for r in range(lay.fila_inicio, min(ws.max_row, lay.max_filas) + 1):
        etiqueta = ws.cell(r, lay.col_depto).value
        if etiqueta is not None and clave_depto(etiqueta) == lay.marcador_otros.upper():
            en_otros = True
        nombre = ws.cell(r, lay.col_nombre).value
        if not en_otros and etiqueta is not None and nombre:
            clave = clave_depto(etiqueta)
            if clave in validos:
                fecha = ws.cell(r, lay.col_fecha).value
                entradas.append(EntradaHistorial(
                    depto=clave, nombre=str(nombre).strip(),
                    monto=_a_entero(ws.cell(r, lay.col_monto).value),
                    fecha=fecha if isinstance(fecha, datetime) else None,
                    hoja=ws.title, fuente="historial"))
        # Lista "Encontrados" (nombre -> depto)
        enc_nombre = ws.cell(r, lay.col_enc_nombre).value
        enc_depto = ws.cell(r, lay.col_enc_depto).value
        if enc_nombre and enc_depto is not None and clave_depto(enc_depto) in validos:
            entradas.append(EntradaHistorial(
                depto=clave_depto(enc_depto), nombre=str(enc_nombre).strip(), monto=None,
                fecha=None, hoja=ws.title, fuente="encontrados"))
        # Bloque cronológico (para detectar duplicados)
        idv = ws.cell(r, lay.col_c_id).value
        if idv not in (None, ""):
            fecha = ws.cell(r, lay.col_c_fecha).value
            crono.append(RegistroCronologico(
                id=str(idv), fecha=fecha if isinstance(fecha, datetime) else None,
                monto=_a_entero(ws.cell(r, lay.col_c_monto).value),
                nombre=str(ws.cell(r, lay.col_c_nombre).value or ""), hoja=ws.title))
    return entradas, crono


def _leer_residentes(ws: Worksheet, validos: set[str]) -> list[EntradaHistorial]:
    """Hoja 'Datos Residentes': Unidad | Nombre y apellido | Rol | Correo | Teléfono | RUT."""
    encabezado = None
    for r in range(1, 10):
        fila = [normalizar_texto(ws.cell(r, c).value) for c in range(1, 15)]
        if "unidad" in fila:
            encabezado = (r, {v: i + 1 for i, v in enumerate(fila) if v})
            break
    if not encabezado:
        return []
    r0, cols = encabezado
    c_unidad = cols.get("unidad")
    c_nombre = next((i for k, i in cols.items() if k.startswith("nombre")), None)
    c_rut = cols.get("rut")
    salida = []
    for r in range(r0 + 1, ws.max_row + 1):
        unidad = ws.cell(r, c_unidad).value
        if unidad is None or clave_depto(unidad) not in validos:
            continue
        nombre = ws.cell(r, c_nombre).value if c_nombre else ""
        rut = normalizar_rut(ws.cell(r, c_rut).value) if c_rut else ""
        salida.append(EntradaHistorial(
            depto=clave_depto(unidad), nombre=str(nombre or "").strip(), monto=None,
            fecha=None, hoja=ws.title, fuente="residentes", rut=rut))
    return salida


def leer_planilla(ruta, hoja_objetivo: str, cfg: Config | None = None) -> DatosPlanilla:
    cfg = cfg or Config()
    wb = load_workbook(ruta, data_only=False)
    if hoja_objetivo not in wb.sheetnames:
        raise ValueError(f"La hoja '{hoja_objetivo}' no existe. Hojas: {wb.sheetnames}")
    mensuales = [ws.title for ws in wb.worksheets if _es_hoja_mensual(ws, cfg)]
    layout = leer_layout(wb[hoja_objetivo], cfg)
    validos = layout.deptos_validos

    historial: list[EntradaHistorial] = []
    crono: list[RegistroCronologico] = []
    for nombre in mensuales:
        ents, cr = _leer_historial_hoja(wb[nombre], cfg, validos)
        if nombre != hoja_objetivo:
            historial.extend(e for e in ents if e.fuente == "historial")
            crono.extend(cr)
        historial.extend(e for e in ents if e.fuente == "encontrados")
    if cfg.layout.hoja_residentes in wb.sheetnames:
        historial.extend(_leer_residentes(wb[cfg.layout.hoja_residentes], validos))

    # Hoja anterior = la hoja mensual (distinta de la objetivo) con la fecha más reciente
    fechas_por_hoja: dict[str, datetime] = {}
    for reg in crono:
        if reg.fecha and (reg.hoja not in fechas_por_hoja or reg.fecha > fechas_por_hoja[reg.hoja]):
            fechas_por_hoja[reg.hoja] = reg.fecha
    hoja_anterior = max(fechas_por_hoja, key=fechas_por_hoja.get) if fechas_por_hoja else None

    return DatosPlanilla(hojas_mensuales=mensuales, layout=layout, historial=historial,
                         cronologico_previo=crono, hoja_anterior=hoja_anterior)


def ultimo_registrado_sugerido(datos: DatosPlanilla):
    """Sugiere el último pago registrado: primero en la hoja objetivo, si no en la anterior."""
    if datos.layout.ultimo_registrado:
        return datos.layout.ultimo_registrado
    regs = [r for r in datos.cronologico_previo if r.hoja == datos.hoja_anterior and r.fecha]
    if not regs:
        return None
    r = max(regs, key=lambda x: (x.fecha, _num_id(x.id)))
    return (r.id, r.fecha, r.monto, r.nombre)
