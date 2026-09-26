"""Tests de `application/ml/inferencia.py` -Etapa AE-43, validada.

Todos los historicos son SINTETICOS. La fuente usa numeracion
`2081..2713` solo para reproducir la forma de los tramos reales; la
funcion unicamente recibe recortes dentro de DESARROLLO (`<= 2589`).
Cubre: fronteras del corte, rechazo de lo que se pasa, invariancia
ante lo que no se pasa (con control positivo), ausencia de etiquetas
y paridad con las filas etiquetadas de `construir_dataset_binario`."""
from __future__ import annotations

import dataclasses
import random
from datetime import date, timedelta

import pytest

from app.application.estadisticas.tipos import ResultadoNumerico
from app.application.ml.dataset import construir_dataset_binario
from app.application.ml.inferencia import CorteInferenciaInvalidoError, construir_filas_inferencia
from app.application.ml.modelo import NOMBRES_FEATURES
from app.application.ml.tipos import FilaCandidato, FilaCandidatoInferencia, FilasInferenciaJuego

PRIMER_SORTEO = 2081
ULTIMO_SORTEO_FUENTE = 2713
BASE = date(2010, 1, 1)


def _resultado(n: int, numeros: tuple[int, ...]) -> ResultadoNumerico:
    return ResultadoNumerico(
        numero_sorteo=n, fecha=BASE + timedelta(days=n), dia_semana="lunes",
        numeros=numeros, superbalota=1,
    )


def _fuente_sintetica(semilla: int = 43) -> list[ResultadoNumerico]:
    rng = random.Random(semilla)
    return [
        _resultado(n, tuple(sorted(rng.sample(range(1, 44), 5))))
        for n in range(PRIMER_SORTEO, ULTIMO_SORTEO_FUENTE + 1)
    ]


def _recortar(fuente: list[ResultadoNumerico], hasta: int) -> list[ResultadoNumerico]:
    """Recorte hecho por el LLAMADOR de la prueba, nunca por la funcion."""
    return [r for r in fuente if r.numero_sorteo <= hasta]


def _construir(historico, hasta, codigo="BALOTO"):
    return construir_filas_inferencia(historico, 1, 43, 5, codigo, hasta)


def _alterar(resultado: ResultadoNumerico, numeros=(39, 40, 41, 42, 43)) -> ResultadoNumerico:
    return _resultado(resultado.numero_sorteo, numeros)


@pytest.fixture(scope="module")
def fuente():
    return _fuente_sintetica()


class TestFronteras:
    def test_corte_maximo_2589_produce_objetivo_2590(self, fuente):
        salida = _construir(_recortar(fuente, 2589), 2589)
        assert salida.sorteo_objetivo == 2590 and salida.calculado_hasta_sorteo == 2589
        assert salida.total_sorteos_historico == 2589 - PRIMER_SORTEO + 1

    def test_primer_objetivo_posible_2131_con_50_sorteos(self, fuente):
        historico = _recortar(fuente, 2130)
        assert len(historico) == 50
        assert _construir(historico, 2130).sorteo_objetivo == 2131

    @pytest.mark.parametrize("hasta", [2590, 2600, 2705, 2706, 2710])
    def test_cortes_fuera_de_desarrollo_se_rechazan_aunque_el_historico_sea_coherente(self, fuente, hasta):
        with pytest.raises(CorteInferenciaInvalidoError):
            _construir(_recortar(fuente, hasta), hasta)

    @pytest.mark.parametrize("hasta", [True, 2589.0, "2589", None])
    def test_corte_no_entero_se_rechaza(self, fuente, hasta):
        with pytest.raises(CorteInferenciaInvalidoError):
            _construir(_recortar(fuente, 2589), hasta)

    def test_fila_con_objetivo_2591_no_se_puede_construir(self):
        with pytest.raises(ValueError):
            FilaCandidatoInferencia(
                codigo_juego="BALOTO", sorteo_objetivo=2591, calculado_hasta_sorteo=2590,
                numero_candidato=1, frecuencia_acumulada=0.1, frecuencia_ventana_10=0.1,
                frecuencia_ventana_20=0.1, frecuencia_ventana_50=0.1,
                sorteos_desde_ultima_aparicion=0, aparecio_en_sorteo_anterior=1,
            )

    def test_fila_con_objetivo_no_consecutivo_no_se_puede_construir(self):
        with pytest.raises(ValueError):
            FilaCandidatoInferencia(
                codigo_juego="BALOTO", sorteo_objetivo=2500, calculado_hasta_sorteo=2498,
                numero_candidato=1, frecuencia_acumulada=0.1, frecuencia_ventana_10=0.1,
                frecuencia_ventana_20=0.1, frecuencia_ventana_50=0.1,
                sorteos_desde_ultima_aparicion=0, aparecio_en_sorteo_anterior=1,
            )


class TestRechazoDeLoQueSePasa:
    @pytest.mark.parametrize("extra", [2590, 2591, 2705, 2706, 2713])
    @pytest.mark.parametrize("al_principio", [True, False])
    def test_un_solo_sorteo_posterior_al_corte_se_rechaza(self, fuente, extra, al_principio):
        historico = _recortar(fuente, 2589)
        sorteo_extra = next(r for r in fuente if r.numero_sorteo == extra)
        historico = [sorteo_extra, *historico] if al_principio else [*historico, sorteo_extra]
        with pytest.raises(CorteInferenciaInvalidoError) as excinfo:
            _construir(historico, 2589)
        mensaje = str(excinfo.value)
        assert str(extra) in mensaje
        if extra >= 2706:
            assert "HOLDOUT" in mensaje
        elif extra >= 2591:
            assert "CONSUMIDO_AE36" in mensaje

    def test_rechazo_por_tramo_aunque_el_corte_sea_bajo(self, fuente):
        historico = [*_recortar(fuente, 2200), next(r for r in fuente if r.numero_sorteo == 2710)]
        with pytest.raises(CorteInferenciaInvalidoError, match="HOLDOUT"):
            _construir(historico, 2200)

    def test_hueco_final_se_rechaza(self, fuente):
        with pytest.raises(CorteInferenciaInvalidoError):
            _construir(_recortar(fuente, 2588), 2589)

    def test_hueco_interno_se_rechaza(self, fuente):
        historico = [r for r in _recortar(fuente, 2589) if r.numero_sorteo != 2400]
        with pytest.raises(CorteInferenciaInvalidoError):
            _construir(historico, 2589)

    def test_historico_anterior_a_2081_se_rechaza(self, fuente):
        previo = _resultado(2080, (1, 2, 3, 4, 5))
        with pytest.raises(CorteInferenciaInvalidoError):
            _construir([previo, *_recortar(fuente, 2589)], 2589)


class TestInvarianciaAnteLoQueNoSePasa:
    def test_alterar_objetivo_consumido_y_holdout_en_la_fuente_no_cambia_la_salida(self, fuente):
        salida_original = _construir(_recortar(fuente, 2589), 2589)

        fuente_alterada = [
            _alterar(r) if r.numero_sorteo >= 2590 else r
            for r in fuente
        ]
        assert any(a != b for a, b in zip(fuente, fuente_alterada) if a.numero_sorteo >= 2590)

        salida_alterada = _construir(_recortar(fuente_alterada, 2589), 2589)
        assert salida_alterada == salida_original

    def test_control_positivo_alterar_un_sorteo_dentro_del_corte_si_cambia_la_salida(self, fuente):
        salida_original = _construir(_recortar(fuente, 2589), 2589)
        original_2589 = next(r for r in fuente if r.numero_sorteo == 2589)
        nuevos = tuple(n for n in range(1, 44) if n not in original_2589.numeros)[:5]
        fuente_alterada = [_alterar(r, nuevos) if r.numero_sorteo == 2589 else r for r in fuente]

        salida_alterada = _construir(_recortar(fuente_alterada, 2589), 2589)
        assert salida_alterada != salida_original

    def test_orden_de_entrada_no_afecta(self, fuente):
        historico = _recortar(fuente, 2589)
        barajado = list(historico)
        random.Random(7).shuffle(barajado)
        assert _construir(barajado, 2589) == _construir(historico, 2589)


class TestSinEtiquetas:
    def test_campos_son_los_de_fila_candidato_sin_etiqueta(self):
        campos_inferencia = {f.name for f in dataclasses.fields(FilaCandidatoInferencia)}
        campos_etiquetados = {f.name for f in dataclasses.fields(FilaCandidato)}
        assert campos_inferencia == campos_etiquetados - {"etiqueta"}
        assert not any("etiqueta" in c or "resultado" in c for c in campos_inferencia)

    def test_nombres_features_del_modelo_existen_en_la_fila_de_inferencia(self):
        campos = {f.name for f in dataclasses.fields(FilaCandidatoInferencia)}
        assert set(NOMBRES_FEATURES) <= campos


def _sin_etiqueta(fila: FilaCandidato) -> dict:
    datos = dataclasses.asdict(fila)
    datos.pop("etiqueta")
    return datos


class TestParidadConFilasEtiquetadas:
    def test_paridad_para_todos_los_objetivos_2131_a_2590(self, fuente):
        desarrollo = _recortar(fuente, 2590)
        dataset = construir_dataset_binario(desarrollo, 1, 43, 5, "BALOTO")
        assert dataset.sorteos_objetivo[0] == 2131 and dataset.sorteos_objetivo[-1] == 2590

        etiquetadas_por_objetivo: dict[int, list[dict]] = {}
        for fila in dataset.filas:
            etiquetadas_por_objetivo.setdefault(fila.sorteo_objetivo, []).append(_sin_etiqueta(fila))

        for objetivo in dataset.sorteos_objetivo:
            salida = _construir(_recortar(desarrollo, objetivo - 1), objetivo - 1)
            inferencia = [dataclasses.asdict(f) for f in salida.filas]
            esperadas = sorted(etiquetadas_por_objetivo[objetivo], key=lambda d: d["numero_candidato"])
            assert inferencia == esperadas, f"sin paridad en el objetivo {objetivo}"


class TestEtiquetaIntocable:
    def test_alterar_el_resultado_de_n_solo_afecta_etiquetas_de_n(self, fuente):
        objetivo = 2400
        desarrollo = _recortar(fuente, 2590)
        original_n = next(r for r in desarrollo if r.numero_sorteo == objetivo)
        nuevos = tuple(n for n in range(1, 44) if n not in original_n.numeros)[:5]
        alterado = [_alterar(r, nuevos) if r.numero_sorteo == objetivo else r for r in desarrollo]

        inferencia_original = _construir(_recortar(desarrollo, objetivo - 1), objetivo - 1)
        inferencia_alterada = _construir(_recortar(alterado, objetivo - 1), objetivo - 1)
        assert inferencia_alterada == inferencia_original

        def filas_de_n(historico):
            ds = construir_dataset_binario(historico, 1, 43, 5, "BALOTO")
            return sorted((f for f in ds.filas if f.sorteo_objetivo == objetivo), key=lambda f: f.numero_candidato)

        etiquetadas_original = filas_de_n(desarrollo)
        etiquetadas_alterada = filas_de_n(alterado)
        assert [_sin_etiqueta(f) for f in etiquetadas_alterada] == [_sin_etiqueta(f) for f in etiquetadas_original]
        assert [f.etiqueta for f in etiquetadas_alterada] != [f.etiqueta for f in etiquetadas_original]


class TestContrato:
    def test_un_candidato_por_numero_del_rango(self, fuente):
        salida = _construir(_recortar(fuente, 2589), 2589)
        assert isinstance(salida, FilasInferenciaJuego)
        assert [f.numero_candidato for f in salida.filas] == list(range(1, 44))
        assert all(f.sorteo_objetivo == 2590 and f.calculado_hasta_sorteo == 2589 for f in salida.filas)
        assert all(f.codigo_juego == "BALOTO" for f in salida.filas)

    def test_baloto_revancha_autorizado(self, fuente):
        salida = _construir(_recortar(fuente, 2589), 2589, codigo="BALOTO_REVANCHA")
        assert salida.codigo_juego == "BALOTO_REVANCHA"

    def test_menos_de_50_sorteos_se_rechaza(self, fuente):
        with pytest.raises(CorteInferenciaInvalidoError):
            _construir(_recortar(fuente, 2129), 2129)

    @pytest.mark.parametrize("codigo", ["MILOTO", "COLORLOTO"])
    def test_juegos_no_autorizados_se_rechazan_antes_de_validar_el_historico(self, codigo):
        with pytest.raises(CorteInferenciaInvalidoError, match=codigo):
            construir_filas_inferencia(None, 1, 43, 5, codigo, 2589)

    def test_numero_fuera_de_rango_se_rechaza(self, fuente):
        historico = _recortar(fuente, 2589)
        historico[-1] = _alterar(historico[-1], (1, 2, 3, 4, 44))
        with pytest.raises(CorteInferenciaInvalidoError):
            _construir(historico, 2589)

    def test_cantidad_incorrecta_de_numeros_se_rechaza(self, fuente):
        historico = _recortar(fuente, 2589)
        historico[-1] = _alterar(historico[-1], (1, 2, 3, 4))
        with pytest.raises(CorteInferenciaInvalidoError):
            _construir(historico, 2589)

    def test_duplicados_en_el_historico_se_rechazan(self, fuente):
        historico = _recortar(fuente, 2589)
        with pytest.raises(ValueError):
            _construir([*historico, historico[-1]], 2589)

    def test_determinismo(self, fuente):
        historico = _recortar(fuente, 2589)
        assert _construir(historico, 2589) == _construir(list(historico), 2589)
