"""Tests de la Etapa AE-78, validada localmente como trabajo preparatorio:
expediente portable de la recepcion por objetivo y su verificacion offline.

G1  funcionalidad nueva, importada dentro de cada prueba (sobre la base falla
    con `ModuleNotFoundError`): formato versionado, lectura endurecida,
    evaluacion reproducible de AE-77, informe JSON determinista, codigos de
    salida y escenarios adversarios.
G2  invariantes de AE-52 y AE-74 a AE-77: huellas, hashes y estados.
G3  premisas sobre el codigo existente que el expediente reutiliza.

Todo sintetico; la politica del verificador es de fixture y se suministra
aparte del expediente. Ningun resultado autoriza evaluacion."""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import importlib
import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from app.application.ml import contrato_vinculo_r0 as cv
from app.application.ml import especificacion_condiciones_del_protocolo as ec
from app.application.ml import expediente_r0_recepcion as ex
from app.application.ml import propuesta_inferencia_prospectiva as pi
from app.application.ml import recepcion_por_objetivo as ro
from app.application.ml import registro_prospectivo as rp
from app.application.ml import sello_temporal_r0 as st
from tests.unit.ml import fixtures_expediente_portable as fp
from tests.unit.ml import fixtures_expediente_r0 as fx
from tests.unit.ml import fixtures_recepcion_por_objetivo as fo


def _m():
    return importlib.import_module("app.application.ml.expediente_portable")


def _plano(valor):
    if dataclasses.is_dataclass(valor):
        return {f.name: _plano(getattr(valor, f.name)) for f in dataclasses.fields(valor)}
    if isinstance(valor, Mapping):
        return {str(k): _plano(v) for k, v in valor.items()}
    if isinstance(valor, (tuple, list, set, frozenset)):
        return [_plano(v) for v in (sorted(valor) if isinstance(valor, (set, frozenset)) else valor)]
    return valor


def _huella(valor):
    return hashlib.sha256(json.dumps(_plano(valor), sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _archivos(m, nombre="integro"):
    return m.componer_expediente(**fp.escenario(nombre))


def _evaluar(m, archivos, politica=None):
    return m.evaluar(m.leer_expediente(archivos), m.leer_politica(politica or fp.politica(m)))


def _manifiesto(archivos):
    return json.loads(archivos["manifiesto.json"])


def _recomponer(m, archivos, manifiesto):
    """Sustituye el manifiesto por uno canonico (para probar el contenido,
    no la forma)."""
    return {**archivos, "manifiesto.json": rp.serializar_entrada(manifiesto)}


# ===========================================================================
# G1: formato y composicion
# ===========================================================================

def test_g1_formato_versionado_con_referencias_por_nombre_tamano_y_hash():
    m = _m()
    archivos = _archivos(m)
    manifiesto = _manifiesto(archivos)
    assert archivos["manifiesto.json"] == rp.serializar_entrada(manifiesto)
    assert manifiesto["esquema"] == m.ESQUEMA_EXPEDIENTE == "expediente-portable-recepcion/1"
    assert set(manifiesto) == {"esquema", "archivos", "piezas"}
    declarados = {a["ruta"]: a for a in manifiesto["archivos"]}
    assert set(declarados) == set(archivos) - {"manifiesto.json"}
    assert [a["ruta"] for a in manifiesto["archivos"]] == sorted(declarados)
    for ruta, datos in archivos.items():
        if ruta != "manifiesto.json":
            assert declarados[ruta]["bytes"] == len(datos)
            assert declarados[ruta]["sha256"] == hashlib.sha256(datos).hexdigest()
    piezas = manifiesto["piezas"]
    assert set(piezas) == {"registro", "declaracion_r0", "sobre", "sellos_r0", "acuses", "sellos_de_acuses", "cierre",
                           "conjunto_esperado", "vistas"}
    assert len(piezas["registro"]) == 4 and len(piezas["acuses"]) == 3 and len(piezas["sellos_de_acuses"]) == 3
    leido = m.leer_expediente(archivos)
    escena = fp.escenario()
    assert leido.entradas == tuple(escena["entradas"]) and leido.bytes_declaracion == escena["bytes_declaracion"]
    assert leido.acuses == tuple(escena["acuses"]) and leido.cierre == escena["cierre"]
    assert leido.sobre == escena["sobre"] and leido.conjunto_esperado == escena["conjunto_esperado"]


def test_g1_el_expediente_exportado_no_contiene_claves_privadas():
    m = _m()
    privadas = fp.claves_privadas_de_fixture()
    for archivos in (_archivos(m), fp.politica(m)):
        for ruta, datos in archivos.items():
            assert b"PRIVATE KEY" not in datos, ruta
            for privada in privadas:
                assert privada not in datos, ruta
    material = {**_archivos(m)}
    material["piezas/ajeno.pem"] = b"-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----\n"
    manifiesto = _manifiesto(material)
    with pytest.raises(m.ExpedienteIlegible):
        m.leer_expediente(material)
    manifiesto["archivos"].append({"ruta": "piezas/ajeno.pem", "bytes": len(material["piezas/ajeno.pem"]),
                                   "sha256": hashlib.sha256(material["piezas/ajeno.pem"]).hexdigest()})
    manifiesto["archivos"].sort(key=lambda a: a["ruta"])
    with pytest.raises(m.ExpedienteIlegible) as error:
        m.leer_expediente(_recomponer(m, material, manifiesto))
    assert error.value.motivo == "material_privado_detectado"


def test_g1_la_politica_del_verificador_va_aparte_y_solo_es_de_prueba():
    m = _m()
    politica = fp.politica(m)
    manifiesto = json.loads(politica["politica.json"])
    assert manifiesto["esquema"] == m.ESQUEMA_POLITICA == "politica-verificador-de-prueba/1"
    assert manifiesto["naturaleza"] == "fixture_de_prueba"
    leida = m.leer_politica(politica)
    assert leida.sello.politicas_admitidas == ("2.999.75.1",) and leida.sello.margen == "0"
    assert {c.rol for c in leida.claves.claves} == {"firmante_r0", "canal"}
    assert (leida.canal, leida.corte_esperado) == (fx.CANAL, 2716)
    assert manifiesto["auditoria"] == {"canal": fx.CANAL, "corte_esperado": 2716}
    otra = dict(manifiesto, naturaleza="operativa")
    with pytest.raises(m.ExpedienteIlegible) as error:
        m.leer_politica({**politica, "politica.json": rp.serializar_entrada(otra)})
    assert error.value.motivo == "naturaleza_no_admitida"
    assert "politica.json" not in _archivos(m) and "manifiesto.json" not in politica


# ===========================================================================
# G1: lectura endurecida (API pura)
# ===========================================================================

@pytest.mark.parametrize("mutar, motivo", [
    (lambda a, man: man.update(esquema="expediente-portable-recepcion/2"), "version_desconocida"),
    (lambda a, man: man["archivos"][0].update(sha256="0" * 64), "sha256_incorrecto"),
    (lambda a, man: man["archivos"][0].update(bytes=man["archivos"][0]["bytes"] + 1), "tamano_incorrecto"),
    (lambda a, man: man["archivos"].append(dict(man["archivos"][0])), "referencia_duplicada"),
    (lambda a, man: man["piezas"]["registro"].append(man["piezas"]["registro"][0]), "referencia_duplicada"),
    (lambda a, man: man["piezas"].update(declaracion_r0="piezas/no-existe.json"), "referencia_no_declarada"),
    (lambda a, man: man["archivos"].pop(), "archivo_no_declarado"),
    (lambda a, man: man.update(extra=1), "estructura_invalida"),
    (lambda a, man: man["piezas"].update(sellos_de_acuses=[{"acuse": 9, "respuesta": "x", "compromiso": "y"}]),
     "estructura_invalida"),
])
def test_g1_lectura_rechaza_manifiestos_incoherentes(mutar, motivo):
    m = _m()
    archivos = _archivos(m)
    manifiesto = _manifiesto(archivos)
    mutar(archivos, manifiesto)
    with pytest.raises(m.ExpedienteIlegible) as error:
        m.leer_expediente(_recomponer(m, archivos, manifiesto))
    assert error.value.motivo == motivo


def test_g1_lectura_rechaza_archivos_faltantes_adicionales_y_sin_referencia():
    m = _m()
    archivos = _archivos(m)
    faltante = dict(archivos)
    faltante.pop(_manifiesto(archivos)["piezas"]["declaracion_r0"])
    with pytest.raises(m.ExpedienteIlegible) as error:
        m.leer_expediente(faltante)
    assert error.value.motivo == "archivo_faltante"
    with pytest.raises(m.ExpedienteIlegible) as error:
        m.leer_expediente({**archivos, "piezas/extra.json": b"{}\n"})
    assert error.value.motivo == "archivo_no_declarado"
    manifiesto = _manifiesto(archivos)
    datos = b"sin referencia\n"
    manifiesto["archivos"].append({"ruta": "piezas/zz-sin-referencia.bin", "bytes": len(datos),
                                   "sha256": hashlib.sha256(datos).hexdigest()})
    manifiesto["archivos"].sort(key=lambda a: a["ruta"])
    with pytest.raises(m.ExpedienteIlegible) as error:
        m.leer_expediente(_recomponer(m, {**archivos, "piezas/zz-sin-referencia.bin": datos}, manifiesto))
    assert error.value.motivo == "archivo_sin_referencia"


@pytest.mark.parametrize("ruta", ["/etc/passwd", "C:/Windows/win.ini", "c:/x", "..", "../fuera.json",
                                  "piezas/../../fuera.json", "piezas/./a.json", "piezas//a.json", "\\\\srv\\x",
                                  "piezas\\a.json", "Piezas/A.json", ".oculto", "piezas/", "a" * 300])
def test_g1_rutas_absolutas_escapes_y_no_canonicas(ruta):
    m = _m()
    archivos = _archivos(m)
    manifiesto = _manifiesto(archivos)
    original = manifiesto["piezas"]["declaracion_r0"]
    datos = archivos.pop(original)
    manifiesto["piezas"]["declaracion_r0"] = ruta
    for entrada in manifiesto["archivos"]:
        if entrada["ruta"] == original:
            entrada["ruta"] = ruta
    with pytest.raises(m.ExpedienteIlegible) as error:
        m.leer_expediente(_recomponer(m, {**archivos, ruta: datos}, manifiesto))
    assert error.value.motivo == "ruta_invalida", ruta


def test_g1_limites_de_tamano_y_numero():
    m = _m()
    archivos = _archivos(m)
    for limites, motivo in ((dict(bytes_por_archivo=64), "archivo_demasiado_grande"),
                            (dict(bytes_totales=1024), "expediente_demasiado_grande"),
                            (dict(archivos=5), "demasiados_archivos"),
                            (dict(bytes_manifiesto=100), "manifiesto_demasiado_grande")):
        with pytest.raises(m.ExpedienteIlegible) as error:
            m.leer_expediente(archivos, limites=m.Limites(**limites))
        assert error.value.motivo == motivo
    assert m.LIMITES_POR_DEFECTO.bytes_por_archivo == 1 << 20
    assert m.LIMITES_POR_DEFECTO.bytes_totales == 16 << 20 and m.LIMITES_POR_DEFECTO.archivos == 512


@pytest.mark.parametrize("contenido, motivo", [
    (b'{"esquema": "expediente-portable-recepcion/1"}', "manifiesto_no_canonico"),
    (b'{"esquema":"x","esquema":"expediente-portable-recepcion/1"}\n', "manifiesto_ilegible"),
    (b"\xff\xfe", "manifiesto_ilegible"),
    (b"[]\n", "manifiesto_ilegible"),
    (b'{"a":NaN}\n', "manifiesto_ilegible"),
])
def test_g1_manifiesto_ilegible_duplicado_o_no_canonico(contenido, motivo):
    m = _m()
    archivos = {**_archivos(m), "manifiesto.json": contenido}
    with pytest.raises(m.ExpedienteIlegible) as error:
        m.leer_expediente(archivos)
    assert error.value.motivo == motivo
    with pytest.raises(m.ExpedienteIlegible) as error:
        m.leer_expediente({k: v for k, v in archivos.items() if k != "manifiesto.json"})
    assert error.value.motivo == "manifiesto_ausente"


# ===========================================================================
# G1: evaluacion reproducible y escenarios
# ===========================================================================

def test_g1_evaluacion_offline_reproduce_ae77_sin_promover():
    m = _m()
    escena = fp.escenario()
    informe = _evaluar(m, m.componer_expediente(**escena))
    directo = ro.evaluar_recepcion_por_objetivo(
        escena["entradas"], escena["bytes_declaracion"], sellos_de_acuses=escena["sellos_de_acuses"],
        declaracion=escena["conjunto_esperado"], vistas=escena["vistas"],
        politica_de_observadores=fo.politica_observadores(ro), corte_esperado=2716,
        evidencias_de_sello=escena["sellos_r0"], politica_de_sello=fo.politica_sello(), sobre=escena["sobre"],
        acuses=escena["acuses"], cierre=escena["cierre"], politica_de_claves=fx.politica(ex), canal=fx.CANAL)
    assert informe["secciones"]["integridad_y_firmas"]["planos"]["integridad_de_bytes_de_las_piezas"]["estado"] == (
        directo.planos_ae77["integridad_de_bytes_de_las_piezas"])
    for plano, estado in directo.planos_ae77.items():
        assert m.estado_de_plano(informe, plano) == estado, plano
    assert m.estado_de_plano(informe, "sello_temporal_de_r0") == directo.expediente.planos["sello_temporal_de_r0"]
    assert m.estado_de_plano(informe, "autenticacion_preparatoria_de_r0") == "pendiente"
    autorizacion = informe["secciones"]["autorizacion_operativa"]
    assert autorizacion["estado"] == "denegada" and autorizacion["AUTORIZA_EVALUACION"] is False
    assert autorizacion["r0_final"]["estado"] == "rechazada"
    assert autorizacion["planos_ae74"]["autenticacion_de_r0"] == "sin_evidencia"
    assert autorizacion["decisiones"] == {"D8": "aprobada_solo_para_el_modelo_sintetico",
                                          "D9": "espera_provisional_aprobada"}
    pendientes = informe["secciones"]["pendientes"]["planos"]
    assert {k: v["estado"] for k, v in pendientes.items()} == {
        "autoridad_del_manifiesto": "pendiente", "completitud_global": "pendiente",
        "completitud_respecto_de_lo_que_debio_existir": "pendiente"}
    assert informe["secciones"]["pendientes"]["decisiones_sin_tomar"] == ["A1", "A2", "A3", "C1", "C2", "C3"]
    assert informe["resultado_de_la_auditoria"] == "sin_rechazos"
    assert m.codigo_de_salida(informe) == m.CODIGOS_DE_SALIDA["sin_rechazos"] == 0


@pytest.mark.parametrize("nombre, seccion, plano, motivo", [
    ("acuse_alterado", "integridad_y_firmas", "firmas_y_roles_de_prueba", "firma_no_coincide"),
    ("acuse_alterado", "tiempo", "tiempo_por_acuse", "firma_no_coincide"),
    ("sello_de_otro_acuse", "tiempo", "tiempo_por_acuse", "compromiso_de_otro_acuse"),
    ("sello_de_otro_acuse", "integridad_y_firmas", "integridad_de_bytes_de_las_piezas", "compromiso_de_otro_acuse"),
    ("objetivo_omitido", "completitud_presentada", "completitud_respecto_del_manifiesto_presentado",
     "objetivo_esperado_sin_acuse"),
    ("vistas_contradictorias", "completitud_presentada", "completitud_respecto_del_manifiesto_presentado",
     "vistas_contradictorias"),
    ("vistas_contradictorias", "integridad_y_firmas", "vistas_del_observador", "vistas_contradictorias"),
])
def test_g1_escenarios_adversarios_conservan_plano_y_motivo(nombre, seccion, plano, motivo):
    m = _m()
    informe = _evaluar(m, _archivos(m, nombre))
    resultado = informe["secciones"][seccion]["planos"][plano]
    assert resultado["estado"] == "rechazada" and motivo in resultado["motivos"], (nombre, resultado)
    assert informe["resultado_de_la_auditoria"] == "con_rechazos"
    assert m.codigo_de_salida(informe) == 1
    for pendiente in ("autoridad_del_manifiesto", "completitud_global", "completitud_respecto_de_lo_que_debio_existir"):
        assert informe["secciones"]["pendientes"]["planos"][pendiente]["estado"] == "pendiente"
    assert informe["secciones"]["autorizacion_operativa"]["estado"] == "denegada"
    assert informe["secciones"]["autorizacion_operativa"]["r0_final"]["estado"] == "rechazada"


def test_g1_canal_y_corte_esperados_los_fija_el_verificador_no_el_expediente():
    m = _m()
    archivos = _archivos(m)
    informe = _evaluar(m, archivos, fp.politica(m, corte_esperado=2715))
    plano = informe["secciones"]["completitud_presentada"]["planos"]["completitud_respecto_del_manifiesto_presentado"]
    assert plano["estado"] == "rechazada" and "corte_distinto_del_esperado" in plano["motivos"]
    manifiesto = _manifiesto(archivos)
    manifiesto["parametros"] = {"canal": fx.CANAL, "corte_esperado": 2715}
    with pytest.raises(m.ExpedienteIlegible) as error:
        m.leer_expediente(_recomponer(m, archivos, manifiesto))
    assert error.value.motivo == "estructura_invalida"


def test_g1_ningun_escenario_convierte_pendientes_en_superados():
    m = _m()
    for nombre in fp.ESCENARIOS:
        informe = _evaluar(m, _archivos(m, nombre))
        assert m.estado_de_plano(informe, "tiempo_por_acuse") != "superada", nombre
        assert m.estado_de_plano(informe, "recepcion_preparatoria_antes_del_plazo") == "pendiente", nombre
        assert m.estado_de_plano(informe, "autenticacion_preparatoria_de_r0") in ("pendiente", "rechazada"), nombre
        assert m.estado_de_plano(informe, "sello_temporal_de_r0") in ("pendiente", "rechazada", "no_concluyente")
        assert informe["secciones"]["autorizacion_operativa"]["AUTORIZA_EVALUACION"] is False


def test_g1_informe_json_determinista_y_resumen_legible():
    m = _m()
    archivos = _archivos(m)
    uno = m.informe_json(_evaluar(m, archivos))
    dos = m.informe_json(_evaluar(m, dict(reversed(list(archivos.items())))))
    assert uno == dos and uno.endswith(b"\n")
    informe = json.loads(uno)
    assert list(informe) == sorted(informe)
    assert informe["esquema"] == "informe-expediente-recepcion/1"
    assert informe["expediente"]["sha256_manifiesto"] == hashlib.sha256(archivos["manifiesto.json"]).hexdigest()
    assert informe["politica_del_verificador"]["origen"] == "suministrada_al_verificador_no_al_expediente"
    resumen = m.resumen_legible(informe)
    for fragmento in ("Integridad y firmas", "Tiempo por acuse", "Completitud respecto del conjunto presentado",
                      "Pendientes", "Autorizacion operativa: DENEGADA", "AUTORIZA_EVALUACION = False",
                      "r0_final: rechazada", "no autoriza evaluacion"):
        assert fragmento in resumen, fragmento


def test_g1_codigos_de_salida_nunca_significan_autorizacion():
    m = _m()
    assert m.CODIGOS_DE_SALIDA == {"sin_rechazos": 0, "con_rechazos": 1, "uso_incorrecto": 2, "expediente_ilegible": 3}
    assert all("autoriz" not in k for k in m.CODIGOS_DE_SALIDA)
    assert "no autoriza evaluacion" in m.SIGNIFICADO_DE_LOS_CODIGOS[0]
    for codigo, texto in m.SIGNIFICADO_DE_LOS_CODIGOS.items():
        assert "autoriza evaluacion" not in texto.replace("no autoriza evaluacion", ""), codigo


def test_g1_lectura_rechazada_no_evalua_r0_final_y_la_evaluacion_lo_rechaza():
    """Regresion: con lectura rechazada `r0_final` no se evalua ni se
    menciona como estado; cuando se evalua, sale rechazada. El texto de
    LIMITES vale en ambos casos."""
    m = _m()
    archivos = _archivos(m)
    with pytest.raises(m.ExpedienteIlegible) as error:
        m.leer_expediente({**archivos, "manifiesto.json": b"[]\n"})
    rechazado = m.informe_de_lectura_rechazada("expediente", error.value)
    assert rechazado["lectura"] == {"estado": "rechazada", "motivos": ["manifiesto_ilegible"], "objeto": "expediente"}
    assert rechazado["secciones"] == {} and rechazado["resultado_de_la_auditoria"] == "expediente_ilegible"
    assert rechazado["autorizacion_operativa"] == {"estado": "denegada", "AUTORIZA_EVALUACION": False}
    assert "r0_final" not in m.informe_json(rechazado).decode("utf-8")
    resumen = m.resumen_legible(rechazado)
    assert "r0_final" not in resumen and "Autorizacion operativa: DENEGADA" in resumen
    assert m.codigo_de_salida(rechazado) == 3
    limites = " ".join(m.LIMITES)
    assert "no autoriza evaluacion ni convierte R0 en final" in limites
    assert "r0_final" not in limites and "sigue rechazad" not in limites
    evaluado = _evaluar(m, archivos)
    assert evaluado["secciones"]["autorizacion_operativa"]["r0_final"]["estado"] == "rechazada"
    assert evaluado["limites"] == rechazado["limites"] == list(m.LIMITES)


def test_g1_limites_vocabulario_y_pureza():
    m = _m()
    texto = " ".join((*m.LIMITES, *m.SIGNIFICADO_DE_LOS_CODIGOS.values()))
    assert "9162" not in texto
    assert "no descart" in texto or "historias ocultas" in texto
    arbol = ast.parse(Path(m.__file__).read_text(encoding="utf-8"))
    prohibidos = {"socket", "urllib", "requests", "http", "time", "subprocess", "random", "os", "pathlib",
                  "sqlalchemy", "datetime", "secrets", "pickle", "marshal", "shelve", "yaml"}
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            assert not {a.name.split(".")[0] for a in nodo.names} & prohibidos
        if isinstance(nodo, ast.ImportFrom):
            assert (nodo.module or "").split(".")[0] not in prohibidos
        if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name):
            assert nodo.func.id not in {"open", "eval", "exec", "__import__"}
        if isinstance(nodo, ast.Attribute):
            assert nodo.attr not in {"now", "today", "utcnow"}


# ===========================================================================
# G2: invariantes de AE-52 y AE-74 a AE-77 (pasan sobre la base)
# ===========================================================================

def test_g2_huellas_de_ae52_y_ae74_a_ae77():
    assert _huella((rp.ESQUEMA_ENTRADA, rp.TIPOS_ENTRADA, rp.REGLAS_EVALUACION_AE52, rp.PENDIENTES_BORRADOR_AE52,
                    rp.NOTA_PROTOCOLO, rp.ALCANCE_REGISTRO)) == (
        "4f31cdeb3c4d29b1740592d4d81de2f8f51305abf4a82743c49f12985621c50b")
    assert _huella(cv.DECISIONES_DEL_CONTRATO) == "56cc40d8af732aea86ca88dc3a16ee64254212a1e40ae7e51a75eafe05c554ea"
    assert _huella((st.ESQUEMA_COMPROMISO, st.CLAVES_DEL_COMPROMISO, st.PROCEDENCIAS_DEL_PLAZO,
                    st.RESULTADOS_TEMPORALES, st.NATURALEZAS_DE_ANCLA, st.ANCLAS_OPERATIVAS_APROBADAS,
                    st.ESTADOS_DE_COMPROBACION, st.COMPROBACIONES_DEL_VINCULO, st.COMPROBACIONES_CRIPTOGRAFICAS,
                    st.HERRAMIENTAS, st.ESTADOS_DEL_PLANO, st.LIMITES_OPERATIVOS, st.NO_PRUEBA, st.MOTIVOS,
                    st.FUENTES_PRIMARIAS, st.POLITICA_ELEGIDA, st.REQUISITOS_PARA_USO_OPERATIVO,
                    st.PLANO_TEMPORAL)) == "155e541d1715ff9f41dfa302d97c9634eaddc27e451f3a20560a0189ab773034"
    assert _huella((ex.ESQUEMA_SOBRE, ex.ESQUEMA_ACUSE, ex.ESQUEMA_CIERRE, ex.ALCANCE_DE_LA_FIRMA, ex.ALGORITMO_DE_FIRMA,
                    ex.CLAVES_DEL_SOBRE, ex.CLAVES_DEL_ACUSE, ex.CLAVES_DEL_CIERRE, ex.ROLES_DE_CLAVE,
                    ex.NATURALEZAS_DE_CLAVE, ex.CLAVES_OPERATIVAS_ADMITIDAS, ex.PLANOS_DE_AUTENTICACION,
                    ex.PENDIENTES_DE_AUTENTICACION, ex.NIVELES_DE_COMPLETITUD, ex.EVIDENCIA_EXTERNA_FALTANTE,
                    ex.PENDIENTES_DE_RECEPCION, ex.PLANOS_PREPARATORIOS, ex.ESTADOS_PREPARATORIOS,
                    ex.DECISIONES_PENDIENTES_AE76, ex.LIMITES)) == (
        "8bd133290bec6bc4b439902109f4d7850c2b7cb4f323ff8a5fd4c042b9cba22b")
    assert _huella((ro.ESQUEMA_COMPROMISO_ACUSE, ro.CLAVES_DEL_COMPROMISO_ACUSE, ro.ESQUEMA_CONJUNTO,
                    ro.CLAVES_DEL_CONJUNTO, ro.NATURALEZAS_DE_OBSERVADOR, ro.OBSERVADORES_OPERATIVOS_ADMITIDOS,
                    ro.PLANOS_DE_TIEMPO, ro.PLANOS_DEL_CONJUNTO, ro.LIMITES_DE_LAS_VISTAS, ro.PLANOS_COMPUESTOS,
                    ro.MOTIVOS, ro.DECISIONES_OPERATIVAS_PENDIENTES, ro.LIMITES)) == (
        "f8fc51a8c3c55d9fb4d8a548efaef9da2f36d5235f9239d96f08b7725022176d")


def test_g2_hashes_literales_y_estados():
    entradas, bd = fx.registro()
    assert rp.hash_entrada(entradas[0]) == "f59365c837c52771007f71ac0ac8bd41b576cc810edbf9596b745412272fe2f6"
    acuses = fx.acuses(ex, entradas)
    assert ex.hash_de_pieza(acuses[0].datos) == "f45622a4de632fe20bb811a25c1e9d087391349fc5d2449dca852c4f16d22972"
    assert ex.hash_de_pieza(fx.cierre(ex, entradas, acuses).datos) == (
        "1dfef4149723d51623965ee77689c9a1d045c169a2010fd6910283190c40abd8")
    assert pi.AUTORIZA_EVALUACION is False
    assert {r.estado for r in ec.CONDICIONES_DEL_PROTOCOLO.values()} == {"sin_fijar"}
    assert {r.estado for r in ec.REQUISITOS_PREVIOS.values()} == {"sin_fijar"}
    assert {d["estado"] for d in ro.DECISIONES_OPERATIVAS_PENDIENTES.values()} == {"sin_decidir"}
    assert ro.OBSERVADORES_OPERATIVOS_ADMITIDOS == () and ex.CLAVES_OPERATIVAS_ADMITIDAS == ()
    assert st.ANCLAS_OPERATIVAS_APROBADAS == ()


# ===========================================================================
# G3: premisas sobre el codigo existente
# ===========================================================================

def test_g3_las_piezas_de_ae76_y_ae77_se_reconstruyen_desde_sus_bytes():
    escena = fp.escenario()
    for objeto in (escena["sobre"], escena["cierre"], escena["conjunto_esperado"], *escena["acuses"]):
        copia = ex.ObjetoFirmado(bytes(objeto.datos), bytes(objeto.firma), bytes(objeto.clave_publica))
        assert copia == objeto
    ev = escena["sellos_de_acuses"][0]
    assert ro.EvidenciaDeSelloDeAcuse(ev.acuse, bytes(ev.respuesta_der), bytes(ev.bytes_compromiso)) == ev
    assert st.EvidenciaDeSello(b"r", b"c") == st.EvidenciaDeSello(b"r", b"c")


def test_g3_la_evaluacion_de_ae77_es_funcion_de_bytes_y_politicas():
    escena = fp.escenario()
    argumentos = dict(sellos_de_acuses=escena["sellos_de_acuses"], declaracion=escena["conjunto_esperado"],
                      vistas=escena["vistas"], politica_de_observadores=fo.politica_observadores(ro),
                      corte_esperado=2716, evidencias_de_sello=escena["sellos_r0"],
                      politica_de_sello=fo.politica_sello(), sobre=escena["sobre"], acuses=escena["acuses"],
                      cierre=escena["cierre"], politica_de_claves=fx.politica(ex), canal=fx.CANAL)
    uno = ro.evaluar_recepcion_por_objetivo(escena["entradas"], escena["bytes_declaracion"], **argumentos)
    dos = ro.evaluar_recepcion_por_objetivo(escena["entradas"], escena["bytes_declaracion"], **argumentos)
    assert _plano(uno) == _plano(dos)
    assert uno.planos_ae77["autoridad_del_manifiesto"] == "pendiente"
