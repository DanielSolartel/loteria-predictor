"""Notas de la proyección de carteras congeladas: no inventan componentes."""
import copy

import pytest

from app.application.ml import predicciones_explicacion as pe
from tests.unit import fixtures_producto5 as fx


@pytest.mark.parametrize('juego,nota', [
    ('BALOTO', 'números principales; la superbalota va aparte'),
    ('BALOTO_REVANCHA', 'números principales; la superbalota va aparte'),
    ('MILOTO', 'números principales'),
    ('COLORLOTO', 'pares número-color en ColorLoto'),
])
def test_proyeccion_respeta_componentes_del_juego_sin_mutar_cartera(juego, nota):
    fuente = fx.fuente_colorloto() if juego == 'COLORLOTO' else fx.fuente_numeros(juego)
    fuente.update(objetivo=51, calculado_hasta_sorteo=50)
    combinacion = {'pares': [[1, 'AZUL']] * 6} if juego == 'COLORLOTO' else {'numeros': [1, 2, 3, 4, 5]}
    if juego in ('BALOTO', 'BALOTO_REVANCHA'):
        combinacion['superbalota'] = 1
    cartera = {'juego': juego, 'fuente': fuente, 'datos': {'corte': 50},
               'linea': {'modelo': 'uniforme-v1', 'version': 1, 'semilla': 42, 'diversidad': 'libre'},
               'cartera': {'objetivo': 51, 'combinaciones': [combinacion]}}
    antes = copy.deepcopy(cartera)
    proyeccion = pe.proyeccion_tabla(cartera, None)
    assert proyeccion['notas']['numeros_fuertes'] == nota
    assert proyeccion['columnas']['combinaciones'] == [combinacion]
    assert proyeccion['columnas']['nivel_confianza'] is None
    assert proyeccion['escrita'] is False
    assert cartera == antes
