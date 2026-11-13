"""Pruebas de las funciones de normalización (ejecutar con: python -m pytest)."""
from conciliador.normalizacion import clave_depto, comparar_nombres, normalizar_rut, parsear_monto


def test_parsear_monto_texto_clp():
    # Caso que botaba la app: montos pegados como texto con formato chileno
    assert parsear_monto("$141.245") == 141245
    assert parsear_monto("$ 40.000") == 40000
    assert parsear_monto("141245,00") == 141245
    assert parsear_monto(141245.0) == 141245
    assert parsear_monto(None) is None
    assert parsear_monto("") is None
    assert parsear_monto("abc") is None


def test_normalizar_rut():
    assert normalizar_rut("13.255.917-1") == "13255917-1"
    assert normalizar_rut("18339066-k") == "18339066-K"


def test_clave_depto():
    assert clave_depto(316) == "316"
    assert clave_depto(" 612  t2 ") == "612 T2"


def test_comparar_nombres_orden_y_truncado():
    assert comparar_nombres("MORA RIOSECO KARINA GEORGINA", "Karina Mora Rioseco") == (3, 1.0)
    coinc, _ = comparar_nombres("Gabriela Alejandra Val", "Gabriela Valderrama Carrasco")
    assert coinc == 2
