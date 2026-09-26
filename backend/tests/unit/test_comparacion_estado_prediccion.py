"""Tests de `scripts/comparacion_estado_prediccion.py` -Etapa AE-48,
validada: validacion estricta de reportes JSON 1.1/1.2, comparacion
descriptiva de progreso y escritor atomico de evidencia sin
sobrescritura. Todo sintetico: reportes construidos con las funciones
reales de AE-40/41/46 y archivos en `tmp_path` -nunca PostgreSQL."""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
from pathlib import Path

import pytest

from app.application.ml.autorizacion_operativa import (
    construir_reporte_bloqueado_por_numeracion_invalida,
    evaluar_autorizacion_operativa_desde_elegibilidad,
)
from app.application.ml.diagnostico_bloqueo import CONDICIONES_SIN_MECANISMO_AE46, CondicionDesbloqueoML, diagnosticar_bloqueo
from app.application.ml.prediccion_bloqueada import resolver_prediccion
from app.application.ml.reapertura import evaluar_elegibilidad_reapertura_ml
from app.application.ml.tipos import DecisionContinuidadML, EstadoPrediccionML, ResumenDisponibilidadHoldout
from scripts import comparacion_estado_prediccion as comp

NO_GO = DecisionContinuidadML.NO_GO_SIN_EVIDENCIA_SUFICIENTE
ARCHIVO = Path(comp.__file__)


def _catalogo() -> comp.CatalogoEstados:
    return comp.CatalogoEstados(
        estados=tuple(e.value for e in EstadoPrediccionML),
        condiciones=tuple(c.value for c in CondicionDesbloqueoML),
        condiciones_sin_mecanismo=frozenset(c.value for c in CONDICIONES_SIN_MECANISMO_AE46),
        condicion_numeracion=CondicionDesbloqueoML.NUMERACION_HOLDOUT_VALIDA.value,
        condicion_minimo=CondicionDesbloqueoML.MINIMO_SORTEOS_NUEVOS.value,
        condicion_evidencia=CondicionDesbloqueoML.EVIDENCIA_CIENTIFICA_AE39.value,
        estado_no_go=EstadoPrediccionML.BLOQUEADO_NO_GO_CIENTIFICO.value,
    )


def _autorizacion(codigo: str, total):
    if total is None:
        return construir_reporte_bloqueado_por_numeracion_invalida(codigo, "hueco sintetico")
    resumen = ResumenDisponibilidadHoldout(
        juego_codigo=codigo, desde_numero_sorteo=2706, total_registros=total, total_numeros_distintos=total,
        numero_sorteo_minimo=2706 if total else None, numero_sorteo_maximo=2705 + total if total else None,
    )
    return evaluar_autorizacion_operativa_desde_elegibilidad(evaluar_elegibilidad_reapertura_ml(resumen))


def _juego(codigo: str, total) -> dict:
    """Mismo formato que construye `consultar_estado_prediccion` (AE-47)."""
    autorizacion = _autorizacion(codigo, total)
    reporte = resolver_prediccion(autorizacion, NO_GO)
    d = diagnosticar_bloqueo(autorizacion, NO_GO)
    p = d.progreso
    return {
        "codigo": codigo, "estado": reporte.estado.value, "motivos": [m.value for m in reporte.motivos],
        "explicacion": reporte.explicacion, "disclaimer": reporte.disclaimer,
        "progreso": {"evaluable": p.evaluable, "desde_numero_sorteo": p.desde_numero_sorteo,
                     "total_sorteos_nuevos": p.total_sorteos_nuevos, "minimo_requerido": p.minimo_requerido,
                     "faltantes": p.faltantes, "numero_sorteo_objetivo_minimo": p.numero_sorteo_objetivo_minimo},
        "condiciones_pendientes": [c.value for c in d.condiciones_pendientes],
        "desbloqueable": d.desbloqueable,
    }


def _reporte_11(total_baloto=8, total_revancha=8, revision="0006") -> dict:
    return {"esquema": "1.1", "alembic_revision": revision,
            "juegos": [_juego("BALOTO", total_baloto), _juego("BALOTO_REVANCHA", total_revancha)]}


def _reporte_12(anterior: dict, actual: dict) -> dict:
    return {**actual, "esquema": "1.2", "comparacion": comp.comparar_reportes(anterior, actual, _catalogo())}


def _validar(reporte):
    return comp.validar_reporte_estado(reporte, _catalogo())


# ---------------------------------------------------------------------------
# Validacion de reportes 1.1 y 1.2
# ---------------------------------------------------------------------------

class TestValidacionAceptada:
    @pytest.mark.parametrize("totales", [(8, 8), (0, 0), (100, 130), (None, 8)])
    def test_reportes_1_1_validos(self, totales):
        reporte = _reporte_11(*totales)
        assert _validar(reporte) == reporte

    def test_reporte_1_2_valido(self):
        reporte = _reporte_12(_reporte_11(8, 8), _reporte_11(15, 9))
        assert _validar(reporte) == reporte

    def test_reporte_1_2_encadenado(self):
        primero = _reporte_11(8, 8)
        segundo = _reporte_12(primero, _reporte_11(15, 9))
        tercero = _reporte_12(segundo, _reporte_11(20, 9))
        assert _validar(tercero)["comparacion"]["esquema_anterior"] == "1.2"


def _mutar(reporte: dict, funcion) -> dict:
    copia = copy.deepcopy(reporte)
    funcion(copia)
    return copia


MUTACIONES_1_1 = {
    "esquema_desconocido": lambda r: r.update(esquema="2.0"),
    "clave_extra_raiz": lambda r: r.update(extra=1),
    "sin_revision": lambda r: r.pop("alembic_revision"),
    "revision_vacia": lambda r: r.update(alembic_revision=""),
    "juego_faltante": lambda r: r["juegos"].pop(),
    "juego_sobrante": lambda r: r["juegos"].append(copy.deepcopy(r["juegos"][0])),
    "juegos_desordenados": lambda r: r["juegos"].reverse(),
    "juego_desconocido": lambda r: r["juegos"][0].update(codigo="MILOTO"),
    "clave_extra_juego": lambda r: r["juegos"][0].update(extra=1),
    "desbloqueable_true": lambda r: r["juegos"][0].update(desbloqueable=True),
    "estado_distinto_del_primer_motivo": lambda r: r["juegos"][0].update(estado="bloqueado_no_go_cientifico"),
    "estado_fuera_del_enum": lambda r: (r["juegos"][0].update(estado="habilitado"),
                                        r["juegos"][0]["motivos"].__setitem__(0, "habilitado")),
    "motivos_desordenados": lambda r: r["juegos"][0]["motivos"].reverse(),
    "condicion_fuera_del_enum": lambda r: r["juegos"][0]["condiciones_pendientes"].append("prediccion_lista"),
    "condicion_sin_mecanismo_resuelta": lambda r: r["juegos"][0]["condiciones_pendientes"].remove(
        "evaluacion_prospectiva_positiva"),
    "evidencia_resuelta_con_no_go": lambda r: r["juegos"][0]["condiciones_pendientes"].remove(
        "evidencia_cientifica_ae39"),
    "progreso_incoherente": lambda r: r["juegos"][0]["progreso"].update(faltantes=5),
    "progreso_clave_extra": lambda r: r["juegos"][0]["progreso"].update(extra=0),
    "progreso_bool_como_entero": lambda r: r["juegos"][0]["progreso"].update(total_sorteos_nuevos=True),
    "clave_predictiva_en_juego": lambda r: r["juegos"][0].update(probabilidades={}),
    "clave_predictiva_anidada": lambda r: r["juegos"][0]["progreso"].update(nivel_confianza=0.5),
    "disclaimer_vacio": lambda r: r["juegos"][0].update(disclaimer="  "),
    "1_1_con_comparacion": lambda r: r.update(comparacion={}),
}


class TestValidacionRechazada:
    @pytest.mark.parametrize("nombre", list(MUTACIONES_1_1))
    def test_reporte_1_1_invalido(self, nombre):
        with pytest.raises(comp.ReporteAnteriorInvalidoError):
            _validar(_mutar(_reporte_11(), MUTACIONES_1_1[nombre]))

    @pytest.mark.parametrize("nombre, funcion", [
        ("sin_comparacion", lambda r: r.pop("comparacion")),
        ("clave_extra", lambda r: r["comparacion"].update(extra=1)),
        ("nota_distinta", lambda r: r["comparacion"].update(nota="Mejora predictiva detectada")),
        ("tipo_erroneo", lambda r: r["comparacion"].update(misma_revision_alembic="si")),
        ("juego_con_clave_extra", lambda r: r["comparacion"]["juegos"][0].update(probabilidad=0.1)),
        ("variacion_incoherente", lambda r: r["comparacion"]["juegos"][0].update(variacion_sorteos_nuevos=99)),
        ("actual_distinto_del_propio_reporte", lambda r: r["comparacion"]["juegos"][0].update(
            sorteos_nuevos_actual=3, variacion_sorteos_nuevos=-5, retroceso=True)),
        ("retroceso_incoherente", lambda r: r["comparacion"]["juegos"][0].update(retroceso=True)),
        ("juegos_desordenados", lambda r: r["comparacion"]["juegos"].reverse()),
        ("esquema_anterior_desconocido", lambda r: r["comparacion"].update(esquema_anterior="0.9")),
        ("misma_revision_true_con_revision_distinta", lambda r: r["comparacion"].update(
            revision_alembic_anterior="0005")),
        ("misma_revision_false_con_revision_igual", lambda r: r["comparacion"].update(
            misma_revision_alembic=False)),
    ])
    def test_reporte_1_2_invalido(self, nombre, funcion):
        valido = _reporte_12(_reporte_11(8, 8), _reporte_11(15, 9))
        with pytest.raises(comp.ReporteAnteriorInvalidoError):
            _validar(_mutar(valido, funcion))

    @pytest.mark.parametrize("valor", [None, [], "texto", 1])
    def test_raiz_que_no_es_objeto(self, valor):
        with pytest.raises(comp.ReporteAnteriorInvalidoError):
            _validar(valor)


class TestLecturaDelArchivoAnterior:
    def test_lee_y_valida(self, tmp_path):
        ruta = tmp_path / "anterior.json"
        ruta.write_bytes(comp.serializar_reporte(_reporte_11()))
        assert comp.leer_reporte_anterior(str(ruta), _catalogo()) == _reporte_11()

    @pytest.mark.parametrize("contenido", [b"{no es json", "á".encode("latin-1"), b""])
    def test_json_corrupto_o_no_utf8(self, tmp_path, contenido):
        ruta = tmp_path / "anterior.json"
        ruta.write_bytes(contenido)
        with pytest.raises(comp.ReporteAnteriorInvalidoError):
            comp.leer_reporte_anterior(str(ruta), _catalogo())

    def test_archivo_inexistente(self, tmp_path):
        with pytest.raises(comp.ReporteAnteriorInvalidoError):
            comp.leer_reporte_anterior(str(tmp_path / "no-existe.json"), _catalogo())


# ---------------------------------------------------------------------------
# Comparacion descriptiva
# ---------------------------------------------------------------------------

def _juego_cmp(anterior, actual, codigo="BALOTO"):
    comparacion = comp.comparar_reportes(anterior, actual, _catalogo())
    return next(j for j in comparacion["juegos"] if j["codigo"] == codigo), comparacion


class TestComparacion:
    def test_sin_cambio(self):
        juego, comparacion = _juego_cmp(_reporte_11(8, 8), _reporte_11(8, 8))
        assert juego["variacion_sorteos_nuevos"] == 0
        assert juego["estado_cambio"] is False and juego["retroceso"] is False
        assert juego["condiciones_resueltas"] == [] and juego["condiciones_nuevas"] == []
        assert comparacion["misma_revision_alembic"] is True
        assert comparacion["nota"] == comp.NOTA_COMPARACION

    def test_avance(self):
        juego, _ = _juego_cmp(_reporte_11(8, 8), _reporte_11(15, 8))
        assert (juego["sorteos_nuevos_anterior"], juego["sorteos_nuevos_actual"]) == (8, 15)
        assert juego["variacion_sorteos_nuevos"] == 7
        assert (juego["faltantes_anterior"], juego["faltantes_actual"]) == (92, 85)

    def test_alcanzar_cien_no_desbloquea(self):
        anterior, actual = _reporte_11(8, 8), _reporte_11(100, 8)
        juego, comparacion = _juego_cmp(anterior, actual)
        assert juego["condiciones_resueltas"] == ["minimo_sorteos_nuevos"]
        assert juego["estado_actual"] == "bloqueado_no_go_cientifico"
        assert juego["estado_cambio"] is True
        assert actual["juegos"][0]["desbloqueable"] is False
        assert "no es evidencia predictiva" in comparacion["nota"]
        assert "NO-GO" in comparacion["nota"]

    def test_retroceso_se_informa(self):
        juego, _ = _juego_cmp(_reporte_11(15, 8), _reporte_11(8, 8))
        assert juego["variacion_sorteos_nuevos"] == -7
        assert juego["retroceso"] is True

    def test_evaluable_a_no_evaluable(self):
        juego, _ = _juego_cmp(_reporte_11(8, 8), _reporte_11(None, 8))
        assert juego["sorteos_nuevos_actual"] is None and juego["variacion_sorteos_nuevos"] is None
        assert juego["retroceso"] is False
        assert juego["condiciones_nuevas"] == ["numeracion_holdout_valida"]

    def test_cambio_de_revision_alembic(self):
        _, comparacion = _juego_cmp(_reporte_11(revision="0006"), _reporte_11(revision="0007"))
        assert comparacion["misma_revision_alembic"] is False
        assert comparacion["revision_alembic_anterior"] == "0006"

    def test_no_copia_la_comparacion_anterior(self):
        anterior = _reporte_12(_reporte_11(8, 8), _reporte_11(15, 9))
        anterior["comparacion"]["juegos"][0]["marcador"] = "NO-COPIAR"
        comparacion = comp.comparar_reportes(anterior, _reporte_11(20, 9), _catalogo())
        assert "NO-COPIAR" not in json.dumps(comparacion)
        assert comparacion["esquema_anterior"] == "1.2"
        assert _juego_cmp(anterior, _reporte_11(20, 9))[0]["variacion_sorteos_nuevos"] == 5

    def test_determinismo_y_validez_del_resultado(self):
        anterior, actual = _reporte_11(8, 8), _reporte_11(15, 9)
        assert comp.comparar_reportes(anterior, actual, _catalogo()) == comp.comparar_reportes(anterior, actual, _catalogo())
        assert _validar(_reporte_12(anterior, actual))


# ---------------------------------------------------------------------------
# Serializacion y escritor atomico
# ---------------------------------------------------------------------------

class TestSerializacion:
    def test_mismo_texto_que_el_print_de_ae47(self):
        reporte = _reporte_11()
        esperado = json.dumps(reporte, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        assert comp.serializar_reporte(reporte) == esperado.encode("utf-8")
        assert b"\r" not in comp.serializar_reporte(reporte)


class TestEscritorAtomico:
    def test_escribe_bytes_exactos_y_devuelve_la_huella(self, tmp_path):
        contenido = comp.serializar_reporte(_reporte_11())
        destino = tmp_path / "evidencia.json"
        huella = comp.escribir_evidencia_atomica(contenido, str(destino))
        assert destino.read_bytes() == contenido
        assert huella == hashlib.sha256(destino.read_bytes()).hexdigest()
        assert sorted(p.name for p in tmp_path.iterdir()) == ["evidencia.json"]

    def test_destino_existente_no_se_sobrescribe(self, tmp_path):
        destino = tmp_path / "evidencia.json"
        destino.write_bytes(b"evidencia previa")
        with pytest.raises(comp.EscrituraEvidenciaError):
            comp.escribir_evidencia_atomica(b"nuevo", str(destino))
        assert destino.read_bytes() == b"evidencia previa"
        assert sorted(p.name for p in tmp_path.iterdir()) == ["evidencia.json"]

    def test_destino_que_aparece_justo_antes_de_publicar_no_se_sobrescribe(self, tmp_path, monkeypatch):
        destino = tmp_path / "evidencia.json"
        publicar_real = comp._publicar_exclusivo

        def intruso_y_publicar(temporal, ruta_destino):
            Path(ruta_destino).write_bytes(b"escrito por otro proceso")
            publicar_real(temporal, ruta_destino)

        monkeypatch.setattr(comp, "_publicar_exclusivo", intruso_y_publicar)
        with pytest.raises(comp.EscrituraEvidenciaError, match="ya existe"):
            comp.escribir_evidencia_atomica(b"nuevo", str(destino))
        assert destino.read_bytes() == b"escrito por otro proceso"
        assert sorted(p.name for p in tmp_path.iterdir()) == ["evidencia.json"]

    def test_sistema_sin_enlaces_duros_falla_sin_publicar(self, tmp_path, monkeypatch):
        def no_soportado(temporal, ruta_destino):
            raise OSError(95, "Operation not supported")

        monkeypatch.setattr(comp, "_publicar_exclusivo", no_soportado)
        destino = tmp_path / "evidencia.json"
        with pytest.raises(comp.EscrituraEvidenciaError, match="exclusiva"):
            comp.escribir_evidencia_atomica(b"nuevo", str(destino))
        assert list(tmp_path.iterdir()) == []

    def test_fallo_de_fsync_no_deja_archivos(self, tmp_path, monkeypatch):
        def fsync_que_falla(fd):
            raise OSError(5, "fallo sintetico de fsync")

        monkeypatch.setattr(comp.os, "fsync", fsync_que_falla)
        with pytest.raises(comp.EscrituraEvidenciaError):
            comp.escribir_evidencia_atomica(b"nuevo", str(tmp_path / "evidencia.json"))
        assert list(tmp_path.iterdir()) == []

    def test_huella_verificada_tras_releer(self, tmp_path, monkeypatch):
        publicar_real = comp._publicar_exclusivo

        def publicar_y_corromper(temporal, ruta_destino):
            publicar_real(temporal, ruta_destino)
            os.chmod(ruta_destino, 0o644)
            with open(ruta_destino, "ab") as f:
                f.write(b"corrupcion")

        monkeypatch.setattr(comp, "_publicar_exclusivo", publicar_y_corromper)
        with pytest.raises(comp.EscrituraEvidenciaError, match="huella"):
            comp.escribir_evidencia_atomica(b"nuevo", str(tmp_path / "evidencia.json"))

    def test_fallo_al_releer_tras_publicar_no_borra_el_destino(self, tmp_path, monkeypatch):
        destino = tmp_path / "evidencia.json"
        publicar_real = comp._publicar_exclusivo

        def open_que_falla(*args, **kwargs):
            raise OSError(5, "fallo sintetico de relectura")

        def publicar_y_romper_la_relectura(temporal, ruta_destino):
            publicar_real(temporal, ruta_destino)
            monkeypatch.setattr(comp, "open", open_que_falla, raising=False)

        monkeypatch.setattr(comp, "_publicar_exclusivo", publicar_y_romper_la_relectura)
        with pytest.raises(comp.EscrituraEvidenciaError, match="releer"):
            comp.escribir_evidencia_atomica(b"nuevo", str(destino))
        assert destino.read_bytes() == b"nuevo"
        assert sorted(p.name for p in tmp_path.iterdir()) == ["evidencia.json"]


class TestRutaDeSalida:
    def test_ruta_nueva_en_directorio_existente(self, tmp_path):
        comp.validar_ruta_salida(str(tmp_path / "nueva.json"), None)

    def test_directorio_inexistente(self, tmp_path):
        with pytest.raises(comp.RutaSalidaNoPermitidaError):
            comp.validar_ruta_salida(str(tmp_path / "no-existe" / "nueva.json"), None)

    def test_salida_existente(self, tmp_path):
        existente = tmp_path / "ya.json"
        existente.write_bytes(b"x")
        with pytest.raises(comp.RutaSalidaNoPermitidaError):
            comp.validar_ruta_salida(str(existente), None)

    def test_misma_ruta_que_comparar_aunque_no_exista(self, tmp_path):
        ruta = str(tmp_path / "a.json")
        with pytest.raises(comp.RutaSalidaNoPermitidaError, match="--comparar"):
            comp.validar_ruta_salida(ruta, os.path.join(str(tmp_path), "sub", "..", "a.json"))


# ---------------------------------------------------------------------------
# Estructura
# ---------------------------------------------------------------------------

def test_modulo_solo_usa_biblioteca_estandar():
    arbol = ast.parse(ARCHIVO.read_text(encoding="utf-8"))
    permitidos = {"__future__", "dataclasses", "hashlib", "json", "os", "tempfile", "typing"}
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            assert all(a.name.split(".")[0] in permitidos for a in nodo.names), [a.name for a in nodo.names]
        elif isinstance(nodo, ast.ImportFrom):
            assert (nodo.module or "").split(".")[0] in permitidos, nodo.module


def test_modulo_no_menciona_piezas_predictivas_ni_web():
    texto = ARCHIVO.read_text(encoding="utf-8")
    for prohibido in ("resolver_estado_prediccion", "diagnostico_bloqueo", "diagnosticar_estado_prediccion",
                      "sqlalchemy", "resultados_historicos", "prediccion_bloqueada", "inferencia"):
        assert prohibido not in texto


def test_nada_en_app_menciona_el_modulo():
    raiz = ARCHIVO.resolve().parents[1] / "app"
    for ruta in raiz.rglob("*.py"):
        assert "comparacion_estado_prediccion" not in ruta.read_text(encoding="utf-8"), ruta
