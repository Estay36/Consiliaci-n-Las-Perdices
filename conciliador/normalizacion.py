"""Normalización de textos, RUT, etiquetas de depto y comparación de nombres."""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

CONECTORES = {"de", "del", "la", "las", "los", "y", "da", "van", "von", "san", "e"}
# Largo a partir del cual el banco puede haber truncado el nombre del pagador
# (Banco de Chile corta en 22 o 30 caracteres según el canal de origen)
LARGO_TRUNCADO = 20


def sin_tildes(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def normalizar_texto(texto) -> str:
    if texto is None:
        return ""
    texto = sin_tildes(str(texto)).lower()
    texto = re.sub(r"[^a-z0-9ñ ]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def tokens_nombre(nombre) -> list[str]:
    """Tokens significativos de un nombre (sin conectores ni números)."""
    return [t for t in normalizar_texto(nombre).split()
            if t not in CONECTORES and not t.isdigit() and len(t) > 1]


def normalizar_rut(rut) -> str:
    if rut is None:
        return ""
    rut = str(rut).strip().upper().replace(".", "").replace(" ", "")
    if not rut or rut in {"NAN", "NONE"}:
        return ""
    if "-" not in rut and len(rut) > 1:
        rut = f"{rut[:-1]}-{rut[-1]}"
    cuerpo, _, dv = rut.partition("-")
    cuerpo = cuerpo.lstrip("0")
    return f"{cuerpo}-{dv}" if cuerpo else ""


def clave_depto(valor) -> str:
    """Clave canónica de una etiqueta de unidad: 316 -> '316', '612 t2' -> '612 T2'."""
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    texto = re.sub(r"\s+", " ", str(valor)).strip().upper()
    return texto


def formatear_nombre(nombre: str) -> str:
    """'PAULA DEL CARMEN GONZALEZ' -> 'Paula del Carmen Gonzalez'."""
    palabras = re.sub(r"\s+", " ", str(nombre or "")).strip().split(" ")
    salida = []
    for i, p in enumerate(palabras):
        baja = p.lower()
        if i > 0 and baja in CONECTORES:
            salida.append(baja)
        else:
            salida.append("-".join(s[:1].upper() + s[1:] for s in baja.split("-")))
    return " ".join(salida).strip()


def _tokens_iguales(a: str, b: str, a_trunc: bool, b_trunc: bool) -> bool:
    if a == b:
        return True
    # Token truncado por el banco (último token de un nombre largo)
    if a_trunc and len(a) >= 2 and b.startswith(a):
        return True
    if b_trunc and len(b) >= 2 and a.startswith(b):
        return True
    # Diferencias ortográficas menores (Gonzales/Gonzalez, Chamorroo/Chamorro)
    if min(len(a), len(b)) >= 4 and SequenceMatcher(None, a, b).ratio() >= 0.85:
        return True
    return False


def comparar_nombres(nombre_banco: str, nombre_ref: str) -> tuple[int, float]:
    """Compara el nombre de la cartola con un nombre de referencia.

    Retorna (tokens_coincidentes, cobertura), donde cobertura es la fracción de
    tokens del nombre de referencia presentes en el nombre del banco. El orden de
    los tokens no importa, por lo que 'MORA RIOSECO KARINA' calza con 'Karina Mora'.
    """
    tb = tokens_nombre(nombre_banco)
    tr = tokens_nombre(nombre_ref)
    if not tb or not tr:
        return 0, 0.0
    banco_trunc = len(str(nombre_banco).strip()) >= LARGO_TRUNCADO
    ref_trunc = len(str(nombre_ref).strip()) >= LARGO_TRUNCADO
    usados: set[int] = set()
    coincidencias = 0
    for j, r in enumerate(tr):
        for i, b in enumerate(tb):
            if i in usados:
                continue
            if _tokens_iguales(b, r,
                               a_trunc=banco_trunc and i == len(tb) - 1,
                               b_trunc=(ref_trunc or j == len(tr) - 1) and len(r) >= 3 and r != tr[0]):
                usados.add(i)
                coincidencias += 1
                break
    return coincidencias, coincidencias / len(tr)


def parsear_monto(valor) -> int | None:
    """Monto en pesos chilenos desde número o texto.

    Acepta 141245, 141245.0, '$141.245', '$ 141.245', '141.245', '141245,00', '-$1.000'.
    En CLP no hay decimales: el punto es separador de miles y la coma, decimal.
    Retorna None si el valor está vacío o no es interpretable.
    """
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return None if valor != valor else int(round(valor))  # NaN
    texto = str(valor).strip().replace("$", "").replace(" ", "").replace("\u00a0", "")
    if not texto or texto in {"-", "nan", "None"}:
        return None
    negativo = texto.startswith("-") or (texto.startswith("(") and texto.endswith(")"))
    texto = texto.strip("-()")
    if "," in texto:
        texto = texto.split(",")[0]            # descarta decimales
    texto = texto.replace(".", "")
    if not texto.isdigit():
        return None
    return -int(texto) if negativo else int(texto)
