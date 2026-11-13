"""Orquestación de una corrida completa de conciliación."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from . import diccionario as dic
from .cartola import filtrar_desde, leer_cartola, ubicar_punto_inicio
from .config import CONFIANZA_ALTA, SIN_MATCH, Config
from .matching import Conciliador
from .modelos import CAT_CF, CAT_GC, CAT_QUINCHO, Asignacion
from .planilla import leer_planilla, sufijo_desde_hoja, ultimo_registrado_sugerido
from .salida import escribir_salida


@dataclass
class ParametrosCorrida:
    ruta_cartola: str | Path
    ruta_madre: str | Path
    hoja: str
    ultimo_fecha: datetime | None = None
    ultimo_monto: int | None = None
    ultimo_nombre: str = ""
    # Alternativa al trío fecha/monto/nombre: posición del último pago registrado en la
    # cartola ordenada (Transaccion.posicion). -1 = procesar la cartola completa.
    inicio_posicion: int | None = None
    hasta: datetime | None = None
    sufijo_id: str | None = None
    id_inicial: int | None = None
    ruta_diccionario: str | Path | None = None
    ruta_salida: str | Path | None = None
    actualizar_diccionario: bool = True
    colorear: bool = True


@dataclass
class ResultadoCorrida:
    asignaciones: list[Asignacion]
    resumen: dict
    ruta_salida: Path
    nuevos_en_diccionario: int


def _fmt_monto(m: int) -> str:
    return f"${m:,.0f}".replace(",", ".")


def ejecutar(p: ParametrosCorrida, cfg: Config | None = None) -> ResultadoCorrida:
    cfg = cfg or Config()
    datos = leer_planilla(p.ruta_madre, p.hoja, cfg)
    layout = datos.layout
    txns = leer_cartola(p.ruta_cartola, cfg)
    if not txns:
        raise ValueError("La cartola no contiene ingresos.")

    # 1. Punto de inicio
    if p.inicio_posicion is not None:
        inicio = None if p.inicio_posicion < 0 else txns[p.inicio_posicion]
    else:
        if p.ultimo_fecha is None or p.ultimo_monto is None:
            sugerido = ultimo_registrado_sugerido(datos)
            if not sugerido:
                raise ValueError("Indique el último pago registrado (fecha y monto).")
            _, p.ultimo_fecha, p.ultimo_monto, p.ultimo_nombre = sugerido
        inicio = ubicar_punto_inicio(txns, p.ultimo_fecha, p.ultimo_monto, p.ultimo_nombre)
    nuevos = filtrar_desde(txns, inicio, p.hasta)

    # 2. Asignación
    filas_dic = dic.cargar(p.ruta_diccionario) if p.ruta_diccionario else []
    motor = Conciliador(layout.deptos_validos, datos.historial, filas_dic, cfg)
    sufijo = p.sufijo_id or sufijo_desde_hoja(p.hoja)
    siguiente_id = p.id_inicial or (layout.ultimo_id + 1)
    fila_crono = layout.fila_siguiente_cronologico
    alertas: list[str] = []

    ref_fecha = inicio.fecha if inicio else (nuevos[0].fecha if nuevos else datetime.now())
    limite_dup = ref_fecha - timedelta(days=cfg.ventana_duplicados_dias)
    previos = {(r.fecha.date(), r.monto): r for r in datos.cronologico_previo
               if r.fecha and r.fecha >= limite_dup and r.monto}

    asignaciones: list[Asignacion] = []
    for t in nuevos:
        a = motor.asignar(t)
        a.id_interno = f"{siguiente_id:02d}-{sufijo}"
        siguiente_id += 1
        a.fila_cronologico = fila_crono
        fila_crono += 1

        previo = previos.get((t.fecha.date(), t.monto))
        if previo and t.categoria != CAT_CF:
            a.observaciones.append(f"Posible duplicado: ya registrado como {previo.id} en {previo.hoja}")
            alertas.append(f"{a.id_interno}: posible duplicado de {previo.id} ({previo.hoja})")

        # Ubicación en el bloque por depto
        if t.categoria == CAT_QUINCHO:
            cupos = layout.cupos_quincho
        elif t.categoria == CAT_GC and a.depto:
            cupos = layout.cupos_depto.get(a.depto, [])
        else:
            cupos = None
        if cupos is not None:
            libre = next((c for c in cupos if not c.ocupado), None)
            if libre:
                libre.ocupado = True
                a.fila_depto = libre.fila
            else:
                destino = "Arriendo quincho" if t.categoria == CAT_QUINCHO else f"depto {a.depto}"
                a.observaciones.append(f"Sin fila libre para {destino}: insertar una fila en la planilla madre")
                alertas.append(f"{a.id_interno}: sin fila libre para {destino} ({_fmt_monto(t.monto)})")
        asignaciones.append(a)

    # 3. Diccionario RUT -> depto (solo asignaciones de alta confianza)
    agregados = 0
    if p.ruta_diccionario and p.actualizar_diccionario:
        pares = [(a.txn.rut, a.depto, a.txn.nombre_banco) for a in asignaciones
                 if a.txn.categoria == CAT_GC and a.confianza == CONFIANZA_ALTA and a.txn.rut]
        agregados = dic.incorporar(filas_dic, pares)
        if agregados:
            dic.guardar(p.ruta_diccionario, filas_dic)

    # 4. Resumen
    conf = Counter(a.confianza for a in asignaciones if a.txn.categoria == CAT_GC)
    cat = Counter(a.txn.categoria for a in asignaciones)
    sin_match = [f"{a.id_interno} | {a.txn.fecha:%d/%m} | {_fmt_monto(a.txn.monto)} | {a.txn.nombre_banco}"
                 f" | {a.txn.comentario or '-'}"
                 for a in asignaciones if a.confianza == SIN_MATCH]
    revisar = [f"{a.id_interno} → {a.depto} ({a.confianza}): {'; '.join(a.observaciones)}"
               for a in asignaciones if a.confianza in ("MEDIA", "BAJA")]
    resumen = {
        "Hoja rellenada": p.hoja,
        "Último pago ya registrado (punto de inicio)":
            (f"{inicio.fecha:%d/%m/%Y} {inicio.hora} | {_fmt_monto(inicio.monto)} | {inicio.nombre_banco}"
             if inicio else "(se procesó la cartola completa)"),
        "Período procesado": (f"{nuevos[0].fecha:%d/%m/%Y} a {nuevos[-1].fecha:%d/%m/%Y}" if nuevos else "sin ingresos nuevos"),
        "IDs asignados": (f"{asignaciones[0].id_interno} a {asignaciones[-1].id_interno}" if asignaciones else "-"),
        "Ingresos totales": len(asignaciones),
        "Monto total": sum(a.txn.monto for a in asignaciones),
        "Gastos comunes (transferencias)": cat.get(CAT_GC, 0),
        "   · confianza ALTA": conf.get("ALTA", 0),
        "   · confianza MEDIA (revisar)": conf.get("MEDIA", 0),
        "   · confianza BAJA (revisar)": conf.get("BAJA", 0),
        "   · sin match (asignar a mano)": conf.get(SIN_MATCH, 0),
        "Reservas de quincho ($40.000)": cat.get(CAT_QUINCHO, 0),
        "Pagos vía Comunidad Feliz": cat.get(CAT_CF, 0),
        "Monto Comunidad Feliz": sum(a.txn.monto for a in asignaciones if a.txn.categoria == CAT_CF),
        "RUT nuevos agregados al diccionario": agregados,
        "Sin match (asignar a mano)": sin_match,
        "Asignaciones a revisar": revisar,
        "Alertas": alertas,
    }

    ruta_salida = Path(p.ruta_salida or Path(p.ruta_madre).with_name(
        f"Conciliacion_{p.hoja}_{datetime.now():%Y-%m-%d_%H%M}.xlsx"))
    escribir_salida(p.ruta_madre, p.hoja, asignaciones, resumen, ruta_salida, cfg, p.colorear)
    return ResultadoCorrida(asignaciones, resumen, ruta_salida, agregados)
