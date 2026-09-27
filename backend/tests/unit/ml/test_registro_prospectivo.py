"""Tests de `app/application/ml/registro_prospectivo.py` -Etapa AE-52,
validada: registro prospectivo encadenado (protocolo congelado,
salidas registradas antes de cada sorteo y resultados incorporados
despues). Todo sintetico: historicos generados con formulas y salidas
fabricadas solo para probar el mecanismo; nunca PostgreSQL, datos
reales ni predicciones reales."""
from __future__ import annotations

import ast
import dataclasses
import json
from pathlib import Path

import pytest

from app.application.ml import registro_prospectivo as rp
from app.application.ml.incertidumbre import MINIMO_SORTEOS_NUEVOS_PROXIMO_HOLDOUT
from tests.unit.simulaciones import sinteticos

ARCHIVO = Path(rp.__file__)
PROBABILIDADES = [0.1] * 43
"""Salida fabricada: solo prueba el formato, nunca es una prediccion."""


def _estrategia(huella="a" * 64, nombre="estrategia_sintetica"):
    return {
        "nombre": nombre, "descripcion": "estrategia sintetica solo para pruebas", "huella_codigo": huella,
        "archivos_codigo": ["sintetico.py"], "parametros": {"semilla": 1},
        "entorno": {"python": "3.x", "scikit_learn": "0.0"},
    }


def _protocolo(cortes=None, pendientes=(), sintetico=True, estrategia=None, protocolo_id="sintetico-1"):
    return rp.construir_protocolo(
        protocolo_id=protocolo_id, estrategia=estrategia or _estrategia(),
        cortes=cortes if cortes is not None else {"BALOTO": 2713, "BALOTO_REVANCHA": 2713},
        pendientes=list(pendientes), sintetico=sintetico,
    )


def _historico(hasta, a=7, b=9, c=5):
    return sinteticos.historico(2081, hasta, a=a, b=b, c=c)


class _Registro:
    """Registro en memoria: lista de bytes canonicos de cada entrada."""

    def __init__(self, protocolo=None):
        self.entradas = [rp.serializar_entrada(protocolo or _protocolo())]

    @property
    def estado(self):
        return rp.validar_registro(self.entradas)

    def predecir(self, juego="BALOTO", objetivo=2714, historico=None, probabilidades=None):
        entrada = rp.nueva_prediccion(
            self.estado, juego, objetivo, historico if historico is not None else _historico(objetivo - 1),
            probabilidades if probabilidades is not None else PROBABILIDADES,
        )
        self.entradas.append(rp.serializar_entrada(entrada))
        return entrada

    def resultado(self, juego="BALOTO", objetivo=2714, numeros=(1, 2, 3, 4, 5)):
        entrada = rp.nuevo_resultado(self.estado, juego, objetivo, numeros)
        self.entradas.append(rp.serializar_entrada(entrada))
        return entrada


def _mutar(entrada_bytes: bytes, funcion) -> bytes:
    datos = json.loads(entrada_bytes)
    funcion(datos)
    return rp.serializar_entrada(datos)


# ---------------------------------------------------------------------------
# Reglas fijas y protocolo
# ---------------------------------------------------------------------------

class TestReglasYProtocolo:
    def test_reglas_fijas_reutilizan_el_minimo_vigente_de_100(self):
        assert rp.REGLAS_EVALUACION_AE52["minimo_sorteos_resueltos_por_juego"] == 100
        assert rp.REGLAS_EVALUACION_AE52["minimo_sorteos_resueltos_por_juego"] == MINIMO_SORTEOS_NUEVOS_PROXIMO_HOLDOUT
        assert rp.REGLAS_EVALUACION_AE52["metricas_principales"] == ["log_loss", "brier_score"]
        assert rp.REGLAS_EVALUACION_AE52["metricas_secundarias"] == ["precision_en_5", "recall_en_5"]
        assert rp.REGLAS_EVALUACION_AE52["referencia_azar"] == "uniforme_cantidad_numeros_sobre_tamano_rango"
        assert rp.REGLAS_EVALUACION_AE52["orientacion_diferencia"] == "uniforme_menos_estrategia"
        assert rp.REGLAS_EVALUACION_AE52["juegos_por_separado"] is True

    @pytest.mark.parametrize("minimo", [99, 50, 101, 0])
    def test_protocolo_con_otro_minimo_se_rechaza(self, minimo):
        alterado = _mutar(rp.serializar_entrada(_protocolo()),
                          lambda d: d["reglas"].update(minimo_sorteos_resueltos_por_juego=minimo))
        with pytest.raises(rp.EntradaRegistroInvalidaError, match="reglas"):
            rp.validar_registro([alterado])

    def test_juego_no_autorizado(self):
        with pytest.raises(rp.EntradaRegistroInvalidaError):
            _protocolo(cortes={"MILOTO": 601})

    def test_corte_anterior_al_contrato_de_ae36_se_rechaza(self):
        with pytest.raises(rp.EntradaRegistroInvalidaError, match="2705"):
            _protocolo(cortes={"BALOTO": 2704})
        _protocolo(cortes={"BALOTO": 2705})

    def test_borrador_admite_corte_nulo_solo_si_esta_pendiente(self):
        borrador = _protocolo(cortes={"BALOTO": None}, pendientes=["corte_temporal_por_juego"])
        assert borrador["juegos"] == {"BALOTO": {"ultimo_sorteo_conocido": None}}
        with pytest.raises(rp.EntradaRegistroInvalidaError, match="corte"):
            _protocolo(cortes={"BALOTO": None})

    def test_pendiente_desconocido_se_rechaza(self):
        with pytest.raises(rp.EntradaRegistroInvalidaError):
            _protocolo(pendientes=["decision_inventada"])

    def test_borrador_ae52_lista_todas_las_decisiones_pendientes(self):
        borrador = rp.construir_protocolo_borrador(_estrategia())
        assert borrador["pendientes"] == list(rp.PENDIENTES_BORRADOR_AE52)
        assert set(rp.PENDIENTES_BORRADOR_AE52) == {
            "aprobacion_de_la_estrategia_a_congelar", "tramo_de_entrenamiento",
            "contrato_de_inferencia_prospectiva", "autorizacion_ae41_para_prerregistro",
            "corte_temporal_por_juego", "regla_estadistica_de_decision", "mecanismo_de_sellado_temporal_externo",
        }
        assert borrador["sintetico"] is False
        assert borrador["juegos"] == {
            "BALOTO": {"ultimo_sorteo_conocido": None}, "BALOTO_REVANCHA": {"ultimo_sorteo_conocido": None},
        }
        estado = rp.validar_registro([rp.serializar_entrada(borrador)])
        assert estado.protocolo_en_borrador is True

    def test_estrategia_con_claves_o_huella_invalidas(self):
        with pytest.raises(rp.EntradaRegistroInvalidaError):
            _protocolo(estrategia={**_estrategia(), "extra": 1})
        with pytest.raises(rp.EntradaRegistroInvalidaError):
            _protocolo(estrategia=_estrategia(huella="xyz"))


# ---------------------------------------------------------------------------
# Sin salidas reales en AE-52: AE-41 no autoriza operaciones predictivas
# ---------------------------------------------------------------------------

class TestSinSalidasRealesEnAE52:
    """Con AE-41 en `BLOQUEADO_DATOS_INSUFICIENTES` ninguna operacion
    predictiva nueva queda autorizada: un registro real solo puede
    contener el borrador, y los protocolos cerrados solo existen como
    registros sinteticos de prueba, que nunca cuentan."""

    @pytest.mark.parametrize("pendientes", [
        (),
        ("autorizacion_ae41_para_prerregistro",),
        tuple(p for p in rp.PENDIENTES_BORRADOR_AE52 if p != "autorizacion_ae41_para_prerregistro"),
        tuple(p for p in rp.PENDIENTES_BORRADOR_AE52 if p != "tramo_de_entrenamiento"),
    ])
    def test_protocolo_real_distinto_del_borrador_se_rechaza(self, pendientes):
        with pytest.raises(rp.EntradaRegistroInvalidaError, match="borrador"):
            _protocolo(pendientes=pendientes, sintetico=False)

    def test_protocolo_real_cerrado_fabricado_se_rechaza_al_verificar(self):
        fabricado = _mutar(rp.serializar_entrada(_protocolo()), lambda d: d.update(sintetico=False))
        with pytest.raises(rp.EntradaRegistroInvalidaError, match="borrador"):
            rp.validar_registro([fabricado])

    def test_el_borrador_real_nunca_admite_salidas(self):
        registro = _Registro(rp.construir_protocolo_borrador(_estrategia()))
        with pytest.raises(rp.EntradaRegistroInvalidaError, match="borrador"):
            registro.predecir("BALOTO", 2714)
        assert registro.estado.admite_salidas is False

    def test_resumen_declara_si_el_registro_admite_salidas(self):
        borrador = rp.resumir_registro(
            rp.validar_registro([rp.serializar_entrada(rp.construir_protocolo_borrador(_estrategia()))]))
        assert borrador["protocolo"]["admite_salidas"] is False
        assert borrador["protocolo"]["sintetico"] is False
        sintetico = rp.resumir_registro(_Registro().estado)
        assert sintetico["protocolo"]["admite_salidas"] is True
        assert sintetico["protocolo"]["sintetico"] is True
        assert "registro_sintetico" in sintetico["evaluacion"]["motivos"]
        assert sintetico["evaluacion"]["evaluable"] is False

    def test_alcance_aclara_que_el_borrador_no_acumula_evidencia(self):
        assert "no acumula evidencia prospectiva" in rp.ALCANCE_REGISTRO


# ---------------------------------------------------------------------------
# Serializacion canonica y lectura estricta
# ---------------------------------------------------------------------------

class TestSerializacion:
    def test_canonica_y_determinista(self):
        a = rp.serializar_entrada(_protocolo())
        assert a == rp.serializar_entrada(json.loads(a))
        assert a.endswith(b"\n") and b"\n" not in a[:-1] and b"\r" not in a

    @pytest.mark.parametrize("contenido", [b"\xff\xfe", b"{roto", b'{"a": NaN}'])
    def test_ilegible(self, contenido):
        with pytest.raises(rp.RegistroIlegibleError):
            rp.validar_registro([contenido])

    def test_no_canonica_o_con_claves_duplicadas(self):
        protocolo = rp.serializar_entrada(_protocolo())
        bonito = (json.dumps(json.loads(protocolo), indent=2, sort_keys=True) + "\n").encode()
        with pytest.raises(rp.EntradaRegistroInvalidaError, match="canonica"):
            rp.validar_registro([bonito])
        duplicada = protocolo.replace(b'{"', b'{"tipo":"x","', 1)
        with pytest.raises(rp.EntradaRegistroInvalidaError):
            rp.validar_registro([duplicada])

    def test_registro_vacio(self):
        with pytest.raises(rp.EntradaRegistroInvalidaError):
            rp.validar_registro([])


# ---------------------------------------------------------------------------
# Cadena: sin sobrescrituras ni reordenaciones
# ---------------------------------------------------------------------------

class TestCadena:
    def _registro_completo(self):
        registro = _Registro()
        registro.predecir("BALOTO", 2714)
        registro.predecir("BALOTO_REVANCHA", 2714, historico=_historico(2713, a=11, b=13, c=3))
        registro.resultado("BALOTO", 2714)
        return registro

    def test_registro_valido_y_cabeza(self):
        registro = self._registro_completo()
        estado = registro.estado
        assert estado.cabeza == rp.hash_entrada(registro.entradas[-1])
        assert [rp.hash_entrada(e) for e in registro.entradas] == list(estado.hashes)

    def test_modificar_una_entrada_intermedia_rompe_la_cadena(self):
        registro = self._registro_completo()
        registro.entradas[1] = _mutar(registro.entradas[1], lambda d: d["salida"]["probabilidades"].__setitem__(0, 0.2))
        with pytest.raises(rp.CadenaRegistroInconsistenteError):
            rp.validar_registro(registro.entradas)

    def test_modificar_la_ultima_entrada_solo_se_detecta_contra_una_cabeza_anclada(self):
        registro = self._registro_completo()
        cabeza_anclada = registro.estado.cabeza
        registro.entradas[-1] = _mutar(registro.entradas[-1], lambda d: d.update(numeros=[6, 7, 8, 9, 10]))
        assert rp.validar_registro(registro.entradas).cabeza != cabeza_anclada

    @pytest.mark.parametrize("operacion", ["quitar", "reordenar", "duplicar"])
    def test_quitar_reordenar_o_duplicar_entradas(self, operacion):
        entradas = self._registro_completo().entradas
        if operacion == "quitar":
            entradas = entradas[:1] + entradas[2:]
        elif operacion == "reordenar":
            entradas = [entradas[0], entradas[2], entradas[1], entradas[3]]
        else:
            entradas = entradas + [entradas[-1]]
        with pytest.raises(rp.CadenaRegistroInconsistenteError):
            rp.validar_registro(entradas)

    def test_la_primera_entrada_debe_ser_el_protocolo(self):
        registro = self._registro_completo()
        with pytest.raises(rp.EntradaRegistroInvalidaError, match="protocolo"):
            rp.validar_registro(registro.entradas[1:2])


# ---------------------------------------------------------------------------
# Una sola version de la estrategia por registro
# ---------------------------------------------------------------------------

class TestSinMezclaDeVersiones:
    def test_un_segundo_protocolo_se_rechaza(self):
        registro = _Registro()
        segundo = _protocolo(estrategia=_estrategia(huella="b" * 64), protocolo_id="sintetico-2")
        segundo.update(secuencia=2, hash_anterior=registro.estado.cabeza)
        with pytest.raises(rp.EntradaRegistroInvalidaError, match="version"):
            rp.validar_registro(registro.entradas + [rp.serializar_entrada(segundo)])

    def test_prediccion_de_otra_version_no_entra(self):
        version_a = _Registro()
        version_b = _Registro(_protocolo(estrategia=_estrategia(huella="b" * 64), protocolo_id="sintetico-2"))
        prediccion_b = rp.nueva_prediccion(version_b.estado, "BALOTO", 2714, _historico(2713), PROBABILIDADES)
        prediccion_b.update(hash_anterior=version_a.estado.cabeza)
        with pytest.raises(rp.EntradaRegistroInvalidaError, match="version"):
            rp.validar_registro(version_a.entradas + [rp.serializar_entrada(prediccion_b)])


# ---------------------------------------------------------------------------
# Salidas antes del sorteo: nunca con resultados futuros como entrada
# ---------------------------------------------------------------------------

class TestPrediccion:
    def test_prediccion_valida_registra_entrada_salida_y_version(self):
        registro = _Registro()
        prediccion = registro.predecir("BALOTO", 2714)
        assert prediccion["protocolo_hash"] == rp.hash_entrada(registro.entradas[0])
        assert prediccion["entrada"] == {
            "desde": 2081, "hasta": 2713, "total_sorteos": 633,
            "huella": rp.huella_entrada("BALOTO", _historico(2713)),
        }
        assert prediccion["salida"] == {"probabilidades": PROBABILIDADES}
        assert "numeros" not in prediccion

    @pytest.mark.parametrize("hasta", [2714, 2715, 2720])
    def test_resultados_futuros_no_se_aceptan_como_entrada(self, hasta):
        with pytest.raises(rp.EntradaRegistroInvalidaError, match="futuro"):
            _Registro().predecir("BALOTO", 2714, historico=_historico(hasta))

    def test_entrada_que_no_termina_justo_antes_del_objetivo(self):
        with pytest.raises(rp.EntradaRegistroInvalidaError):
            _Registro().predecir("BALOTO", 2714, historico=_historico(2712))

    def test_entrada_con_huecos_o_sorteos_invalidos(self):
        historico = _historico(2713)
        with pytest.raises(rp.EntradaRegistroInvalidaError, match="hueco"):
            _Registro().predecir("BALOTO", 2714, historico=[r for r in historico if r.numero_sorteo != 2500])
        invalido = [dataclasses.replace(r, numeros=(1, 1, 2, 3, 4)) if r.numero_sorteo == 2500 else r
                    for r in historico]
        with pytest.raises(rp.EntradaRegistroInvalidaError):
            _Registro().predecir("BALOTO", 2714, historico=invalido)

    @pytest.mark.parametrize("objetivo", [2713, 2706, 2600])
    def test_sorteos_conocidos_al_registrar_el_protocolo_no_cuentan(self, objetivo):
        with pytest.raises(rp.EntradaRegistroInvalidaError, match="conocido"):
            _Registro().predecir("BALOTO", objetivo, historico=_historico(objetivo - 1))

    def test_protocolo_en_borrador_no_admite_predicciones(self):
        registro = _Registro(rp.construir_protocolo_borrador(_estrategia()))
        with pytest.raises(rp.EntradaRegistroInvalidaError, match="borrador"):
            registro.predecir("BALOTO", 2714)

    def test_juego_fuera_del_protocolo(self):
        registro = _Registro(_protocolo(cortes={"BALOTO": 2713}))
        with pytest.raises(rp.EntradaRegistroInvalidaError):
            registro.predecir("BALOTO_REVANCHA", 2714)

    def test_no_se_sobrescribe_ni_se_retrocede(self):
        registro = _Registro()
        registro.predecir("BALOTO", 2715)
        with pytest.raises(rp.EntradaRegistroInvalidaError, match="ya registrada"):
            registro.predecir("BALOTO", 2715)
        with pytest.raises(rp.EntradaRegistroInvalidaError, match="creciente"):
            registro.predecir("BALOTO", 2714)

    @pytest.mark.parametrize("probabilidades", [
        [0.1] * 42, [0.1] * 44, [0.0] + [0.1] * 42, [1.0] + [0.1] * 42, [1] * 43, [True] + [0.1] * 42,
        [float("nan")] + [0.1] * 42,
    ])
    def test_salida_con_formato_invalido(self, probabilidades):
        with pytest.raises(rp.EntradaRegistroInvalidaError):
            _Registro().predecir("BALOTO", 2714, probabilidades=probabilidades)

    def test_prediccion_fabricada_con_entrada_futura_se_rechaza_al_verificar(self):
        registro = _Registro()
        registro.predecir("BALOTO", 2714)
        registro.entradas[-1] = _mutar(registro.entradas[-1], lambda d: d["entrada"].update(hasta=2714, total_sorteos=634))
        with pytest.raises(rp.EntradaRegistroInvalidaError):
            rp.validar_registro(registro.entradas)

    def test_prediccion_no_puede_llevar_el_resultado(self):
        registro = _Registro()
        registro.predecir("BALOTO", 2714)
        registro.entradas[-1] = _mutar(registro.entradas[-1], lambda d: d.update(numeros=[1, 2, 3, 4, 5]))
        with pytest.raises(rp.EntradaRegistroInvalidaError):
            rp.validar_registro(registro.entradas)


# ---------------------------------------------------------------------------
# Resultados incorporados despues, separados de las salidas
# ---------------------------------------------------------------------------

class TestResultado:
    def test_resultado_referencia_a_su_prediccion(self):
        registro = _Registro()
        registro.predecir("BALOTO", 2714)
        resultado = registro.resultado("BALOTO", 2714, (5, 4, 3, 2, 1))
        assert resultado["prediccion_hash"] == rp.hash_entrada(registro.entradas[1])
        assert resultado["numeros"] == [1, 2, 3, 4, 5]
        assert "probabilidades" not in json.dumps(resultado)

    def test_resultado_sin_prediccion_previa(self):
        with pytest.raises(rp.EntradaRegistroInvalidaError, match="prediccion"):
            _Registro().resultado("BALOTO", 2714)

    def test_resultado_duplicado(self):
        registro = _Registro()
        registro.predecir("BALOTO", 2714)
        registro.resultado("BALOTO", 2714)
        with pytest.raises(rp.EntradaRegistroInvalidaError, match="ya incorporado"):
            registro.resultado("BALOTO", 2714)

    @pytest.mark.parametrize("numeros", [(1, 2, 3, 4), (1, 1, 2, 3, 4), (0, 1, 2, 3, 4), (1, 2, 3, 4, 44)])
    def test_numeros_invalidos(self, numeros):
        registro = _Registro()
        registro.predecir("BALOTO", 2714)
        with pytest.raises(rp.EntradaRegistroInvalidaError):
            registro.resultado("BALOTO", 2714, numeros)

    def test_resultado_de_otro_juego_o_sorteo(self):
        registro = _Registro()
        prediccion = registro.predecir("BALOTO", 2714)
        registro.resultado("BALOTO", 2714)
        registro.entradas[-1] = _mutar(registro.entradas[-1], lambda d: d.update(codigo_juego="BALOTO_REVANCHA"))
        with pytest.raises(rp.EntradaRegistroInvalidaError):
            rp.validar_registro(registro.entradas)
        assert prediccion["codigo_juego"] == "BALOTO"

    def test_prediccion_posterior_a_un_resultado_mas_reciente_no_es_posible(self):
        registro = _Registro()
        registro.predecir("BALOTO", 2716)
        registro.resultado("BALOTO", 2716)
        with pytest.raises(rp.EntradaRegistroInvalidaError):
            registro.predecir("BALOTO", 2715)


# ---------------------------------------------------------------------------
# Resumen: progreso, omisiones y evaluacion no disponible
# ---------------------------------------------------------------------------

class TestResumen:
    def test_progreso_por_juego_y_omisiones(self):
        registro = _Registro()
        registro.predecir("BALOTO", 2714)
        registro.predecir("BALOTO", 2716, historico=_historico(2715))
        registro.resultado("BALOTO", 2714)
        resumen = rp.resumir_registro(registro.estado)
        baloto, revancha = resumen["juegos"]
        assert baloto == {
            "codigo": "BALOTO", "ultimo_sorteo_conocido": 2713, "predicciones_registradas": 2,
            "resultados_incorporados": 1, "predicciones_sin_resultado": [2716], "omisiones": [2715],
            "minimo_resultados_requeridos": 100, "faltantes": 99,
        }
        assert revancha["predicciones_registradas"] == 0 and revancha["faltantes"] == 100

    def test_evaluacion_nunca_disponible_en_ae52(self):
        resumen = rp.resumir_registro(_Registro().estado)
        assert resumen["evaluacion"]["evaluable"] is False
        assert resumen["evaluacion"]["motivos"] == [
            "registro_sintetico", "faltan_resultados_minimos", "regla_estadistica_no_implementada_en_ae52",
            "sellado_temporal_externo_no_verificado", "no_go_ae39_vigente",
        ]
        assert "metricas" not in json.dumps(resumen["evaluacion"])

    def test_borrador_real(self):
        estado = rp.validar_registro([rp.serializar_entrada(rp.construir_protocolo_borrador(_estrategia()))])
        resumen = rp.resumir_registro(estado)
        assert resumen["protocolo"]["estado"] == "borrador"
        assert resumen["protocolo"]["sintetico"] is False
        assert resumen["protocolo"]["pendientes"] == list(rp.PENDIENTES_BORRADOR_AE52)
        assert resumen["evaluacion"]["motivos"][0] == "protocolo_en_borrador"
        assert all(j["ultimo_sorteo_conocido"] is None and j["omisiones"] == [] for j in resumen["juegos"])

    def test_alcance_explica_que_la_huella_no_acredita_la_fecha(self):
        for fragmento in ("orden", "no acredita la fecha", "sellado temporal externo", "antes del sorteo",
                          "no genera predicciones", "NO-GO de AE-39"):
            assert fragmento in rp.ALCANCE_REGISTRO, fragmento


# ---------------------------------------------------------------------------
# Estructura: modulo puro, sin reloj ni conexion con inferencia o modelo
# ---------------------------------------------------------------------------

def _importaciones():
    salida = []
    for nodo in ast.walk(ast.parse(ARCHIVO.read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.Import):
            salida.extend(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            salida.append(nodo.module or "")
    return salida


def test_modulo_puro_sin_reloj_ni_azar():
    for modulo in _importaciones():
        raiz = modulo.split(".")[0]
        assert raiz not in {"sklearn", "numpy", "scipy", "pandas", "sqlalchemy", "fastapi", "random", "time",
                            "datetime", "os", "pathlib"}, modulo
    atributos = {n.attr for n in ast.walk(ast.parse(ARCHIVO.read_text(encoding="utf-8"))) if isinstance(n, ast.Attribute)}
    assert not atributos & {"now", "utcnow", "today", "time"}


def test_no_conecta_inferencia_resolvedor_ni_modelo():
    for modulo in _importaciones():
        for prohibido in ("inferencia", "prediccion_bloqueada", "modelo", "resolver_estado_prediccion",
                          "diagnostico_bloqueo", "infrastructure"):
            assert prohibido not in modulo, modulo
