"""Asignación de cada ingreso a un depto.

Señales, en orden de fuerza:
  1. Comentario de la transferencia con número de depto ("GC depto 415", "Dp718", "dpto 1413 torre 2").
  2. RUT del pagador (diccionario persistente + hoja 'Datos Residentes').
  3. Nombre del pagador contra el historial de meses anteriores, la lista
     'Encontrados' y 'Datos Residentes', tolerando orden distinto de nombres y
     apellidos, nombres truncados por el banco y errores ortográficos menores.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from .config import CONFIANZA_ALTA, CONFIANZA_BAJA, CONFIANZA_MEDIA, SIN_MATCH, Config
from .diccionario import FilaDiccionario
from .modelos import CAT_CF, CAT_OTRO, CAT_QUINCHO, Asignacion, EntradaHistorial, Transaccion
from .normalizacion import comparar_nombres, formatear_nombre, normalizar_texto

_PAT_DEPTO = re.compile(
    r"\b(?:departamento|depart|depto|dpto|depa|dept|dto|dep|dp|d)\s*\.?\s*(?:n\s*[°º]?\s*\.?\s*)?(\d{3,4})",
    re.I)
_PAT_TORRE = re.compile(r"torre\s*(\d)|\bt\s*(\d)\b", re.I)
_PAT_ESTAC = re.compile(r"(?:estacionamiento|estac|est|bx|box)\s*\.?\s*(\d{2,4})", re.I)
_PAT_NUMERO = re.compile(r"(?<![\d.])(\d{3,4})(?![\d])")
_PALABRAS_RESERVA = ("garantia", "quincho", "salon", "evento", "reserva", "arriendo")

_PESO_FUENTE = {"historial": 3, "diccionario": 3, "residentes": 2, "encontrados": 1}


@dataclass
class CandidatoDepto:
    depto: str
    coincidencias: int
    cobertura: float
    soporte: int = 0                 # meses distintos del historial con este nombre
    ultima_fecha: datetime | None = None
    fuentes: set[str] = field(default_factory=set)
    nombre_ref: str = ""             # nombre más reciente usado en la planilla

    @property
    def tiene_historial(self) -> bool:
        return "historial" in self.fuentes

    def clave_orden(self):
        peso = max((_PESO_FUENTE.get(f, 0) for f in self.fuentes), default=0)
        return (self.coincidencias, peso, self.soporte, self.cobertura,
                self.ultima_fecha or datetime.min)


class Conciliador:
    def __init__(self, deptos_validos: set[str], historial: list[EntradaHistorial],
                 diccionario: list[FilaDiccionario] | None = None, cfg: Config | None = None):
        self.cfg = cfg or Config()
        self.validos = deptos_validos
        self.entradas = [e for e in historial if e.nombre and e.depto in deptos_validos]
        self.idx_rut: dict[str, set[str]] = {}
        for f in diccionario or []:
            if f.depto in deptos_validos:
                self.idx_rut.setdefault(f.rut, set()).add(f.depto)
        for e in self.entradas:
            if e.rut:
                self.idx_rut.setdefault(e.rut, set()).add(e.depto)
        self._estac = {self._num_estac(d): d for d in deptos_validos if self._num_estac(d)}

    # ------------------------------------------------------------------ señales
    @staticmethod
    def _num_estac(depto: str) -> str | None:
        m = re.search(r"BX\s*(\d+)", depto)
        return m.group(1) if m else None

    def _resolver_numero(self, numero: str, torre: str | None) -> str | None:
        if torre and torre != "3" and f"{numero} T{torre}" in self.validos:
            return f"{numero} T{torre}"
        if numero in self.validos:
            return numero
        alternativas = [d for d in self.validos if d.split(" ")[0] == numero]
        return alternativas[0] if len(alternativas) == 1 else None

    def depto_desde_comentario(self, comentario: str) -> tuple[str | None, bool]:
        """Retorna (depto, señal_fuerte). Fuerte = precedido de 'depto', 'dpto', etc."""
        if not comentario:
            return None, False
        texto = comentario.strip()
        m_t = _PAT_TORRE.search(texto)
        torre = (m_t.group(1) or m_t.group(2)) if m_t else None
        encontrados = {self._resolver_numero(m.group(1), torre) for m in _PAT_DEPTO.finditer(texto)}
        encontrados.discard(None)
        if len(encontrados) == 1:
            return encontrados.pop(), True
        if not encontrados:
            m_e = _PAT_ESTAC.search(texto)
            if m_e and m_e.group(1) in self._estac:
                return self._estac[m_e.group(1)], True
            if "ref" not in texto.lower():
                sueltos = {self._resolver_numero(n, torre) for n in _PAT_NUMERO.findall(texto)}
                sueltos.discard(None)
                if len(sueltos) == 1:
                    return sueltos.pop(), False
        return None, False

    def candidatos_por_nombre(self, nombre: str) -> list[CandidatoDepto]:
        por_depto: dict[str, CandidatoDepto] = {}
        meses: dict[str, set[str]] = {}
        for e in self.entradas:
            coinc, cob = comparar_nombres(nombre, e.nombre)
            if coinc < 2:
                continue
            c = por_depto.get(e.depto)
            if c is None:
                c = por_depto[e.depto] = CandidatoDepto(e.depto, coinc, cob)
            if (coinc, cob) > (c.coincidencias, c.cobertura):
                c.coincidencias, c.cobertura = coinc, cob
            c.fuentes.add(e.fuente)
            if e.fuente == "historial":
                meses.setdefault(e.depto, set()).add(e.hoja)
                if e.fecha and (c.ultima_fecha is None or e.fecha > c.ultima_fecha):
                    c.ultima_fecha = e.fecha
                    c.nombre_ref = e.nombre
        for d, c in por_depto.items():
            c.soporte = len(meses.get(d, ()))
        return sorted(por_depto.values(), key=CandidatoDepto.clave_orden, reverse=True)

    def nombre_para_planilla(self, nombre_banco: str, depto: str | None) -> str:
        """Usa el nombre que ya se viene usando en la planilla para ese pagador."""
        mejor, mejor_clave = None, None
        for e in self.entradas:
            if e.fuente != "historial" or (depto and e.depto != depto):
                continue
            coinc, cob = comparar_nombres(nombre_banco, e.nombre)
            if coinc < 2:
                continue
            clave = (coinc, e.fecha or datetime.min)
            if mejor_clave is None or clave > mejor_clave:
                mejor, mejor_clave = e.nombre.strip(), clave
        return mejor or formatear_nombre(nombre_banco)

    # --------------------------------------------------------------- decisión
    def asignar(self, txn: Transaccion) -> Asignacion:
        a = Asignacion(txn=txn)
        if txn.categoria == CAT_CF:
            a.nombre_planilla = self.cfg.nombre_cf
            a.confianza = "—"
            a.metodo = "Pago por Comunidad Feliz (se imputa automáticamente en CF)"
            return a
        if txn.categoria == CAT_QUINCHO:
            return self._asignar_quincho(txn, a)
        if txn.categoria == CAT_OTRO:
            a.nombre_planilla = formatear_nombre(txn.nombre_banco)
            a.confianza = SIN_MATCH
            a.metodo = f"Tipo de movimiento '{txn.tipo}'"
            a.observaciones.append("Ingreso que no es transferencia: revisar manualmente")
            return a
        return self._asignar_gasto_comun(txn, a)

    def _asignar_quincho(self, txn: Transaccion, a: Asignacion) -> Asignacion:
        a.depto = "QUINCHO"
        a.metodo = f"Monto ${self.cfg.monto_quincho:,.0f} = reserva de quincho".replace(",", ".")
        d_com, _ = self.depto_desde_comentario(txn.comentario)
        d_rut = self.idx_rut.get(txn.rut, set())
        cands = self.candidatos_por_nombre(txn.nombre_banco)
        d_ref = d_com or (next(iter(d_rut)) if len(d_rut) == 1 else None) or \
            (cands[0].depto if cands else None)
        a.nombre_planilla = self.nombre_para_planilla(txn.nombre_banco, None)
        if a.nombre_planilla == formatear_nombre(txn.nombre_banco) and len(d_rut) == 1:
            # Nombre truncado sin calce: usar el nombre con que se registra a ese RUT
            a.nombre_planilla = self.nombre_para_planilla(txn.nombre_banco, next(iter(d_rut)))
        if d_ref:
            a.observaciones.append(f"Reserva asociada a depto {d_ref}")
        coment = normalizar_texto(txn.comentario)
        if not txn.comentario or any(p in coment for p in _PALABRAS_RESERVA):
            a.confianza = CONFIANZA_ALTA
        else:
            a.confianza = CONFIANZA_MEDIA
            a.observaciones.append(f"El comentario no menciona reserva: '{txn.comentario}'")
        return a

    def _asignar_gasto_comun(self, txn: Transaccion, a: Asignacion) -> Asignacion:
        d_com, com_fuerte = self.depto_desde_comentario(txn.comentario)
        d_rut = self.idx_rut.get(txn.rut, set())
        cands = self.candidatos_por_nombre(txn.nombre_banco)
        deptos_nombre = [c.depto for c in cands]
        top = cands[0] if cands else None

        if d_com:
            a.depto = d_com
            apoyos = []
            if d_com in d_rut:
                apoyos.append("RUT")
            if d_com in deptos_nombre:
                apoyos.append("nombre")
            if apoyos:
                a.confianza, a.metodo = CONFIANZA_ALTA, "Comentario + " + " + ".join(apoyos)
            else:
                otros = sorted(d_rut | ({top.depto} if top else set()))
                if otros:
                    a.confianza, a.metodo = CONFIANZA_MEDIA, "Comentario"
                    a.observaciones.append(
                        f"El comentario indica {d_com}, pero el pagador figura en {', '.join(otros)}")
                    a.alternativas = otros
                else:
                    a.confianza = CONFIANZA_ALTA if com_fuerte else CONFIANZA_MEDIA
                    a.metodo = "Comentario" if com_fuerte else "Número en comentario"
                    a.observaciones.append("Pagador nuevo: sin historial ni RUT conocido")
        elif d_rut:
            if len(d_rut) == 1:
                a.depto = next(iter(d_rut))
                a.metodo = "RUT"
                if top and top.depto != a.depto and a.depto not in deptos_nombre:
                    a.confianza = CONFIANZA_MEDIA
                    a.observaciones.append(f"El nombre también calza con {top.depto}")
                    a.alternativas = [top.depto]
                else:
                    a.confianza = CONFIANZA_ALTA
                    if top and a.depto in deptos_nombre:
                        a.metodo = "RUT + nombre"
            else:
                comunes = [d for d in deptos_nombre if d in d_rut]
                a.depto = comunes[0] if comunes else sorted(d_rut)[0]
                a.confianza, a.metodo = CONFIANZA_BAJA, "RUT asociado a varios deptos"
                a.alternativas = sorted(d_rut - {a.depto})
                a.observaciones.append(f"El RUT figura en {', '.join(sorted(d_rut))}")
        elif top:
            a.depto = top.depto
            otros = [c for c in cands[1:] if c.depto != top.depto]
            empate = [c for c in otros if c.coincidencias == top.coincidencias]
            a.alternativas = [c.depto for c in otros]
            empate_hist = [c for c in empate if c.tiene_historial]
            if empate_hist or (empate and not top.tiene_historial):
                a.confianza = CONFIANZA_BAJA
                a.metodo = "Nombre (ambiguo)"
                a.observaciones.append(
                    f"El nombre calza igual de bien con {', '.join(c.depto for c in empate)}; "
                    f"se eligió {top.depto} por historial más frecuente/reciente")
            elif empate:
                a.confianza = CONFIANZA_MEDIA
                a.metodo = f"Nombre (historial, {top.soporte} mes(es))"
                a.observaciones.append(
                    f"Mismo nombre figura en Datos Residentes/Encontrados para "
                    f"{', '.join(c.depto for c in empate)}; se eligió {top.depto} por historial de pagos")
            elif not top.tiene_historial:
                a.confianza, a.metodo = CONFIANZA_MEDIA, "Nombre (solo Datos Residentes/Encontrados)"
            elif any(c.tiene_historial for c in otros):
                a.confianza, a.metodo = CONFIANZA_MEDIA, "Nombre (historial)"
                a.observaciones.append(
                    "El pagador también registra pagos en " +
                    ", ".join(c.depto for c in otros if c.tiene_historial))
            else:
                a.confianza, a.metodo = CONFIANZA_ALTA, f"Nombre (historial, {top.soporte} mes(es))"
        else:
            a.confianza = SIN_MATCH
            a.metodo = "Sin coincidencias"
            a.observaciones.append("No hay comentario, RUT ni nombre que permita identificar el depto")

        a.nombre_planilla = self.nombre_para_planilla(txn.nombre_banco, a.depto or None)
        return a
