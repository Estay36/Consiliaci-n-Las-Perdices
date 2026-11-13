"""Lectura de la cartola bancaria y selección del período a registrar."""
from __future__ import annotations

import re
from datetime import datetime

import pandas as pd

from .config import Config
from .modelos import CAT_CF, CAT_GC, CAT_OTRO, CAT_QUINCHO, Transaccion
from .normalizacion import comparar_nombres, normalizar_rut, parsear_monto


def _texto(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def _nombre_desde_glosa(glosa: str) -> str:
    m = re.search(r"(?:recibida de|recibido de)\s+(.*)$", glosa, re.I)
    return m.group(1).strip() if m else glosa


def leer_cartola(ruta, cfg: Config | None = None) -> list[Transaccion]:
    """Retorna los ingresos de la cartola en orden cronológico ascendente."""
    cfg = cfg or Config()
    c = cfg.cartola
    if str(ruta).lower().endswith(".csv"):
        df = pd.read_csv(ruta, dtype=str)
    else:
        df = pd.read_excel(ruta, dtype={c.codigo: str, c.rut: str, c.hora: str})
    faltantes = [col for col in (c.fecha, c.ingreso, c.glosa) if col not in df.columns]
    if faltantes:
        raise ValueError(f"La cartola no tiene las columnas esperadas: {faltantes}")

    df = df.dropna(how="all")
    df["_monto"] = pd.to_numeric(df[c.ingreso].map(parsear_monto), errors="coerce")
    df = df[df["_monto"] > 0].copy()
    df["_fecha"] = pd.to_datetime(df[c.fecha], errors="coerce", dayfirst=True)
    df["_hora"] = df.get(c.hora, "").fillna("00:00").astype(str)
    df["_orden_original"] = range(len(df))
    # La cartola viene de más reciente a más antigua: se invierte el orden original
    # como desempate para movimientos con misma fecha y hora.
    df = df.sort_values(["_fecha", "_hora", "_orden_original"],
                        ascending=[True, True, False]).reset_index(drop=True)

    txns: list[Transaccion] = []
    for pos, fila in df.iterrows():
        glosa = _texto(fila.get(c.glosa))
        tipo = _texto(fila.get(c.tipo)).upper()
        nombre = _texto(fila.get(c.nombre)) or _nombre_desde_glosa(glosa)
        monto = int(round(fila["_monto"]))
        t = Transaccion(
            fecha=fila["_fecha"].to_pydatetime(),
            hora=fila["_hora"],
            monto=monto,
            nombre_banco=nombre,
            rut=normalizar_rut(fila.get(c.rut)),
            comentario=_texto(fila.get(c.comentario)),
            tipo=tipo,
            glosa=glosa,
            codigo=_texto(fila.get(c.codigo)),
            banco_origen=_texto(fila.get(c.banco)),
            posicion=pos,
        )
        if tipo == cfg.tipo_cf or cfg.texto_cf in glosa.upper():
            t.categoria = CAT_CF
            t.nombre_banco = cfg.nombre_cf
        elif monto == cfg.monto_quincho:
            t.categoria = CAT_QUINCHO
        elif tipo and tipo != "TRANSFERENCIA":
            t.categoria = CAT_OTRO
        else:
            t.categoria = CAT_GC
        txns.append(t)
    return txns


def ubicar_punto_inicio(txns: list[Transaccion], fecha: datetime, monto: int,
                        nombre: str = "") -> Transaccion:
    """Encuentra en la cartola el último pago ya registrado."""
    if fecha is None:
        raise ValueError("El último pago registrado no tiene fecha válida en la planilla.")
    candidatos = [t for t in txns if t.fecha.date() == fecha.date()
                  and (monto is None or t.monto == int(monto))]
    if monto is None and nombre:
        # Sin monto legible: se exige calce de nombre
        candidatos = [t for t in candidatos if comparar_nombres(t.nombre_banco, nombre)[0] >= 2]
    if not candidatos:
        if monto is None:
            raise ValueError(f"No se pudo ubicar en la cartola el último pago del {fecha:%d/%m/%Y} "
                             f"({nombre}): su monto en la planilla no es legible.")
        raise ValueError(
            f"No se encontró en la cartola un ingreso de ${monto:,.0f} el "
            f"{fecha:%d/%m/%Y}. Revise el punto de inicio o que la cartola cubra esa fecha."
            .replace(",", "."))
    if len(candidatos) > 1 and nombre:
        candidatos.sort(key=lambda t: comparar_nombres(t.nombre_banco, nombre), reverse=True)
    return candidatos[0]


def filtrar_desde(txns: list[Transaccion], inicio: Transaccion | None,
                  hasta: datetime | None = None) -> list[Transaccion]:
    """Ingresos posteriores al punto de inicio (exclusivo) y hasta una fecha opcional."""
    salida = [t for t in txns if inicio is None or t.posicion > inicio.posicion]
    if hasta is not None:
        salida = [t for t in salida if t.fecha.date() <= hasta.date()]
    return salida
