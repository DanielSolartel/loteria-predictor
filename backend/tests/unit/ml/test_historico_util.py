"""Tests de `application/ml/historico_util.py` -Etapa AE-36."""
from __future__ import annotations

from datetime import date

import pytest

from app.application.ml.historico_util import HistoricoInconsistenteError, validar_y_ordenar_historico
from app.application.estadisticas.tipos import ResultadoNumerico


def _r(n: int, dia: int) -> ResultadoNumerico:
    return ResultadoNumerico(numero_sorteo=n, fecha=date(2026, 1, dia), dia_semana="lunes", numeros=(1, 2, 3, 4, 5), superbalota=None)


class TestValidarYOrdenarHistorico:
    def test_ya_ordenado_se_conserva(self):
        h = [_r(1, 1), _r(2, 2), _r(3, 3)]
        out = validar_y_ordenar_historico(h, "BALOTO")
        assert [x.numero_sorteo for x in out] == [1, 2, 3]

    def test_desordenado_se_ordena_ascendente(self):
        h = [_r(3, 3), _r(1, 1), _r(2, 2)]
        out = validar_y_ordenar_historico(h, "BALOTO")
        assert [x.numero_sorteo for x in out] == [1, 2, 3]

    def test_orden_de_entrada_no_altera_el_resultado(self):
        h_a = [_r(1, 1), _r(2, 2), _r(3, 3)]
        h_b = [_r(3, 3), _r(1, 1), _r(2, 2)]
        h_c = [_r(2, 2), _r(3, 3), _r(1, 1)]
        salidas = [tuple(x.numero_sorteo for x in validar_y_ordenar_historico(h, "BALOTO")) for h in (h_a, h_b, h_c)]
        assert salidas[0] == salidas[1] == salidas[2]

    def test_no_muta_la_entrada(self):
        h = [_r(3, 3), _r(1, 1), _r(2, 2)]
        copia = list(h)
        validar_y_ordenar_historico(h, "BALOTO")
        assert h == copia

    def test_devuelve_lista_nueva(self):
        h = [_r(1, 1)]
        out = validar_y_ordenar_historico(h, "BALOTO")
        assert out is not h

    def test_numero_sorteo_duplicado_se_rechaza(self):
        with pytest.raises(HistoricoInconsistenteError):
            validar_y_ordenar_historico([_r(1, 1), _r(1, 2)], "BALOTO")

    def test_inconsistencia_fecha_vs_numero_sorteo_se_rechaza(self):
        with pytest.raises(HistoricoInconsistenteError):
            validar_y_ordenar_historico([_r(1, 5), _r(2, 1)], "BALOTO")

    def test_historico_vacio_no_falla(self):
        assert validar_y_ordenar_historico([], "BALOTO") == []

    def test_un_solo_sorteo_no_falla(self):
        out = validar_y_ordenar_historico([_r(1, 1)], "BALOTO")
        assert len(out) == 1
