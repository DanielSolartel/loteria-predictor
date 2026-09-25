"""Prueba estructural (AST) de los cortes temporales de los casos de
uso de ML existentes -mantenimiento posterior a AE-42, validado.

Limitada DELIBERADAMENTE a los tres casos de uso que entrenan con
historico real (AE-36, AE-37, AE-38): fija el corte congelado de
AE-36 (`2705`) y verifica los cortes ya existentes de AE-37/AE-38
(`2590`). No impone ningun corte a casos de uso futuros -una
evaluacion prerregistrada del holdout tendra su propio contrato
temporal, definido y probado en su propia etapa."""
from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

DIRECTORIO_CASOS_USO = Path(__file__).resolve().parents[3] / "app" / "application" / "use_cases"

CONTRATOS = [
    ("evaluar_baseline_ml_probabilidad_numeros", "CORTE_CONTRATO_AE36", 2705),
    ("evaluar_robustez_ml_probabilidad_numeros", "CORTE_DESARROLLO_AE37", 2590),
    ("comparar_familias_ml_probabilidad_numeros", "CORTE_DESARROLLO_AE38", 2590),
]


def _llamadas_listar(arbol: ast.AST) -> list[ast.Call]:
    return [
        nodo for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Call)
        and isinstance(nodo.func, ast.Attribute)
        and nodo.func.attr == "listar_resultados_numericos"
    ]


@pytest.mark.parametrize("modulo, constante, valor", CONTRATOS)
def test_cada_consulta_de_historico_pasa_el_corte_con_nombre(modulo, constante, valor):
    arbol = ast.parse((DIRECTORIO_CASOS_USO / f"{modulo}.py").read_text(encoding="utf-8"))
    llamadas = _llamadas_listar(arbol)
    assert llamadas, f"{modulo} no consulta listar_resultados_numericos"
    for llamada in llamadas:
        corte = [k for k in llamada.keywords if k.arg == "hasta_numero_sorteo"]
        assert len(corte) == 1, f"{modulo}:{llamada.lineno} no pasa hasta_numero_sorteo"
        assert isinstance(corte[0].value, ast.Name) and corte[0].value.id == constante, (
            f"{modulo}:{llamada.lineno} debe pasar hasta_numero_sorteo={constante}"
        )


@pytest.mark.parametrize("modulo, constante, valor", CONTRATOS)
def test_valor_del_corte(modulo, constante, valor):
    mod = importlib.import_module(f"app.application.use_cases.{modulo}")
    assert getattr(mod, constante, None) == valor
