"""Interfaz del conciliador de ingresos (Streamlit).

Funciona igual en Streamlit Community Cloud y en local (streamlit run app.py).
Los archivos cargados se procesan en memoria/temporal durante la sesión y no se guardan.
El diccionario RUT -> depto se carga y descarga como CSV, porque el disco de la nube
no es persistente; en modo local, además, se lee y actualiza datos/diccionario_pagadores.csv.
"""
from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from conciliador import Config, ParametrosCorrida, ejecutar
from conciliador.cartola import leer_cartola, ubicar_punto_inicio
from conciliador.planilla import leer_planilla, sufijo_desde_hoja, ultimo_registrado_sugerido

BASE = Path(__file__).resolve().parent
RUTA_DICCIONARIO = BASE / "datos" / "diccionario_pagadores.csv"
COLORES = {"ALTA": "#E2EFDA", "MEDIA": "#FFF2CC", "BAJA": "#FCE4D6", "SIN MATCH": "#F8CBAD", "—": "#DDEBF7"}

st.set_page_config(page_title="Conciliador de ingresos", layout="wide")
st.title("Conciliación de ingresos – cuenta corriente vs. planilla")
st.caption("Pasos 1 a 3 del proceso: lectura de la cartola, registro de ingresos y asignación por depto. "
           "El ingreso en Comunidad Feliz sigue siendo manual.")


def _guardar_temporal(archivo) -> Path:
    carpeta = Path(st.session_state.setdefault("tmpdir", tempfile.mkdtemp(prefix="conciliador_")))
    ruta = carpeta / archivo.name
    ruta.write_bytes(archivo.getvalue())
    return ruta


@st.cache_data(show_spinner=False)
def _cargar(ruta_cartola: str, ruta_madre: str, hoja: str, firma: tuple):
    cfg = Config()
    txns = leer_cartola(ruta_cartola, cfg)
    datos = leer_planilla(ruta_madre, hoja, cfg)
    return txns, ultimo_registrado_sugerido(datos), datos.hoja_anterior


def _fmt(m: int) -> str:
    return f"${m:,.0f}".replace(",", ".")


# ---------------------------------------------------------------- 1. archivos
c1, c2, c3 = st.columns(3)
f_cartola = c1.file_uploader("Cartola detallada del banco (.xlsx)", type=["xlsx", "xls", "csv"])
f_madre = c2.file_uploader("Planilla madre de ingresos (.xlsx)", type=["xlsx"])
f_dic = c3.file_uploader("Diccionario de pagadores (.csv, opcional)", type=["csv"],
                         help="RUT → depto. Descárguelo al final de cada corrida y vuelva a cargarlo "
                              "la próxima vez: así el sistema aprende de un mes a otro.")
if not (f_cartola and f_madre):
    st.info("Cargue la cartola y la planilla madre para comenzar.")
    st.stop()

ruta_cartola, ruta_madre = _guardar_temporal(f_cartola), _guardar_temporal(f_madre)
if f_dic:
    ruta_dic = _guardar_temporal(f_dic)
elif RUTA_DICCIONARIO.exists():
    ruta_dic = RUTA_DICCIONARIO           # modo local con diccionario en disco
else:
    ruta_dic = Path(st.session_state["tmpdir"]) / "diccionario_pagadores.csv"

from openpyxl import load_workbook  # noqa: E402

hojas = [h for h in load_workbook(ruta_madre, read_only=True).sheetnames if h != Config().layout.hoja_residentes]

# ---------------------------------------------------------------- 2. parámetros
st.subheader("Parámetros")
c1, c2, c3 = st.columns([1, 1, 2])
hoja = c1.selectbox("Hoja a rellenar (período)", hojas, index=len(hojas) - 1)
try:
    sufijo_defecto = sufijo_desde_hoja(hoja)
except ValueError:
    sufijo_defecto = ""
sufijo = c2.text_input("Sufijo de ID", value=sufijo_defecto, help="Ej. 1026 genera IDs 01-1026, 02-1026, …")

firma = (f_cartola.name, f_cartola.size, f_madre.name, f_madre.size)
try:
    txns, sugerido, hoja_anterior = _cargar(str(ruta_cartola), str(ruta_madre), hoja, firma)
except Exception as e:  # noqa: BLE001
    st.error(f"No se pudieron leer los archivos: {e}")
    st.stop()

# Lista de ingresos de la cartola (más recientes primero) para elegir el último ya registrado
opciones = [-1] + [t.posicion for t in reversed(txns)]
etiquetas = {-1: "— Procesar la cartola completa —"}
for t in txns:
    etiquetas[t.posicion] = f"{t.fecha:%d/%m/%Y} {t.hora} | {_fmt(t.monto)} | {t.nombre_banco}"
indice = 0
if sugerido:
    try:
        t_sug = ubicar_punto_inicio(txns, sugerido[1], sugerido[2], sugerido[3])
        indice = opciones.index(t_sug.posicion)
    except Exception as e:  # noqa: BLE001 - la sugerencia nunca debe botar la app
        st.warning(f"No se pudo ubicar automáticamente el último pago registrado: {e} "
                   "Selecciónelo manualmente en la lista.")
inicio = c3.selectbox("Último pago ya registrado (punto de inicio)", opciones, index=indice,
                      format_func=etiquetas.get,
                      help="Se procesan los ingresos posteriores a este movimiento.")
if sugerido:
    st.caption(f"Sugerido desde la planilla: {sugerido[0]} · "
               f"{sugerido[1]:%d/%m/%Y} · {_fmt(sugerido[2] or 0)} · {sugerido[3]}")

c1, c2 = st.columns(2)
usar_hasta = c1.checkbox("Limitar hasta una fecha")
hasta = c2.date_input("Hasta", value=txns[-1].fecha.date(), format="DD/MM/YYYY") if usar_hasta else None
colorear = st.checkbox("Colorear en la hoja las filas a revisar", value=True)

# ---------------------------------------------------------------- 3. ejecución
if st.button("Conciliar", type="primary"):
    salida = Path(st.session_state["tmpdir"]) / f"Conciliacion_{hoja}_{datetime.now():%Y-%m-%d_%H%M}.xlsx"
    with st.spinner("Conciliando…"):
        try:
            res = ejecutar(ParametrosCorrida(
                ruta_cartola=ruta_cartola, ruta_madre=ruta_madre, hoja=hoja,
                inicio_posicion=inicio, sufijo_id=sufijo or None,
                hasta=datetime.combine(hasta, datetime.min.time()) if hasta else None,
                ruta_diccionario=ruta_dic, ruta_salida=salida, colorear=colorear))
        except Exception as e:  # noqa: BLE001
            st.error(str(e))
            st.stop()
    st.session_state["resultado"] = res

res = st.session_state.get("resultado")
if res:
    r = res.resumen
    st.subheader("Resultado")
    m = st.columns(6)
    m[0].metric("Ingresos", r["Ingresos totales"])
    m[1].metric("Monto total", _fmt(r["Monto total"]))
    m[2].metric("Asignados ALTA", r["   · confianza ALTA"])
    m[3].metric("A revisar", r["   · confianza MEDIA (revisar)"] + r["   · confianza BAJA (revisar)"])
    m[4].metric("Sin match", r["   · sin match (asignar a mano)"])
    m[5].metric("Comunidad Feliz", r["Pagos vía Comunidad Feliz"])
    st.caption(f"Período: {r['Período procesado']} · IDs: {r['IDs asignados']} · "
               f"Punto de inicio: {r['Último pago ya registrado (punto de inicio)']}")
    for alerta in r["Alertas"]:
        st.warning(alerta)

    filas = [{
        "ID": a.id_interno, "Fecha": a.txn.fecha.strftime("%d/%m/%Y"), "Monto": _fmt(a.txn.monto),
        "Nombre cartola": a.txn.nombre_banco, "Comentario": a.txn.comentario,
        "Depto": a.depto, "Confianza": a.confianza, "Método": a.metodo,
        "Nombre planilla": a.nombre_planilla, "Observaciones": "; ".join(a.observaciones),
    } for a in res.asignaciones]
    df = pd.DataFrame(filas)
    solo_revisar = st.toggle("Mostrar solo los que requieren revisión")
    if solo_revisar:
        df = df[df["Confianza"].isin(["MEDIA", "BAJA", "SIN MATCH"])]
    st.dataframe(df.style.map(lambda v: f"background-color: {COLORES.get(v, '')}", subset=["Confianza"]),
                 width="stretch", hide_index=True)

    st.download_button("Descargar Excel", data=Path(res.ruta_salida).read_bytes(),
                       file_name=Path(res.ruta_salida).name, type="primary",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if res.nuevos_en_diccionario:
        st.success(f"Se agregaron {res.nuevos_en_diccionario} RUT al diccionario de pagadores.")
    if Path(ruta_dic).exists():
        st.download_button("Descargar diccionario de pagadores actualizado (.csv)",
                           data=Path(ruta_dic).read_bytes(), file_name="diccionario_pagadores.csv",
                           mime="text/csv",
                           help="Cárguelo en la próxima corrida para que el RUT se use como señal.")
