"""Tests de la Etapa AE-81, validada localmente como trabajo preparatorio:
publicacion sintetica y monitoreo cruzado de constancias AE-80.

G1  funcionalidad nueva, importada dentro de cada prueba (sobre la base falla
    con `ModuleNotFoundError`): formatos con separacion de dominio, lectura
    estricta, politicas por rol, inventario, recalculo AE-79 -> AE-80 ->
    checkpoints -> observaciones, bifurcaciones, observaciones
    incompatibles, progresiones, discrepancias sin contexto, evidencia
    ausente, adversarios (duplicados, claves reutilizadas, orden, versiones,
    JSON no canonico o no finito, alteraciones de un byte) y planos.
G2  invariantes de AE-52 y AE-74 a AE-80: huellas y estados.
G3  premisas sobre el informe de AE-80 que la verificacion reutiliza.

Todo sintetico y de fixture. Ningun resultado autoriza evaluacion."""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import importlib
import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from app.application.ml import auditoria_cruzada as ac
from app.application.ml import constancias_auditoria as ca
from app.application.ml import contrato_vinculo_r0 as cv
from app.application.ml import expediente_portable as ep
from app.application.ml import expediente_r0_recepcion as ex
from app.application.ml import propuesta_inferencia_prospectiva as pi
from app.application.ml import registro_prospectivo as rp
from tests.unit.ml import fixtures_constancias_auditoria as fc
from tests.unit.ml import fixtures_publicacion_constancias as fpc


def _m():
    return importlib.import_module("app.application.ml.publicacion_constancias")


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


def _verificar(m, **kw):
    return m.verificar(**fpc.entradas(**kw))


def _todos(informe) -> set:
    return {x for grupo in informe["motivos"].values() for x in grupo} | {h["motivo"] for h in informe["hallazgos"]}


def _fila(informe, clave, objeto):
    return next(f for f in informe[clave] if f["id"] == fpc.id_(objeto))


# ===========================================================================
# G1: formatos, separacion de dominio y lectura estricta
# ===========================================================================

def test_g1_checkpoint_y_observacion_comprometen_politica_cabezas_posicion_y_bytes():
    m = _m()
    c1, c2 = fpc.c1(), fpc.c2()
    pieza = m.leer_checkpoint(c2.datos)
    assert tuple(sorted(pieza)) == tuple(sorted(m.CLAVES_DEL_CHECKPOINT)) and c2.datos == ex.bytes_canonicos(pieza)
    assert (pieza["esquema"], pieza["dominio"], pieza["naturaleza"]) == (
        "checkpoint-publicacion-constancias/1", m.DOMINIO_CHECKPOINT, "fixture_de_prueba")
    assert (pieza["registro"], pieza["posicion"], pieza["anterior"]) == (fpc.REGISTRO, 2, fpc.id_(c1))
    assert pieza["sha256_politica_de_constancias"] == fpc.sha_politica_de_constancias()
    assert pieza["dominio_de_constancias"] == ca.DOMINIO_DE_PRUEBA and pieza["cabezas"] == sorted(fpc.cabezas_c2())
    observacion = m.leer_observacion(fpc.observacion(c2, "m1").datos)
    assert observacion["sha256_checkpoint"] == fpc.id_(c2) == hashlib.sha256(c2.datos).hexdigest()
    assert (observacion["publicador"], observacion["registro"], observacion["posicion"]) == (
        fpc.huella("p"), fpc.REGISTRO, 2)
    assert observacion["dominio"] == m.DOMINIO_OBSERVACION != m.DOMINIO_CHECKPOINT
    for lector, datos in ((m.leer_checkpoint, fpc.observacion(c2, "m1").datos),
                          (m.leer_observacion, c2.datos), (m.leer_checkpoint, fpc.constancias()[0].datos)):
        with pytest.raises(ex.ExpedienteInvalido) as error:
            lector(datos)
        assert error.value.motivo == "version_desconocida"
    with pytest.raises(ValueError, match="encadenamiento_mal_formado"):
        m.construir_checkpoint(cabezas=[], sha256_politica_de_constancias="0" * 64, registro=fpc.REGISTRO, posicion=2,
                               anterior=None, clave_publica=fpc.clave_publica("p"))


H = "0" * 64


@pytest.mark.parametrize("cambios, motivo", [
    ({"posicion": 0}, "pieza_mal_formada"),
    ({"anterior": H}, "pieza_mal_formada"),
    ({"cabezas": [[H, "serie-b", 1, H], [H, "serie-a", 1, H]]}, "pieza_mal_formada"),
    ({"cabezas": [[H, "serie-a", 1, H], [H, "serie-a", 2, H]]}, "pieza_mal_formada"),
    ({"cabezas": [[H, "serie-a", 1, H], [H, 7, 1, H]]}, "pieza_mal_formada"),
    ({"cabezas": [[H, "serie-a", 1, H], 5]}, "pieza_mal_formada"),
    ({"sha256_politica_de_constancias": "X" * 64}, "pieza_mal_formada"),
    ({"dominio": "loteria-predictor/observacion-checkpoint/fixture"}, "dominio_no_admitido"),
    ({"naturaleza": "operativa"}, "naturaleza_no_admitida"),
    ({"extra": 1}, "pieza_ilegible"),
    ({"esquema": "checkpoint-publicacion-constancias/2"}, "version_desconocida"),
])
def test_g1_lectura_estricta_del_checkpoint(cambios, motivo):
    m = _m()
    pieza = m.leer_checkpoint(fpc.c1().datos)
    pieza.update(cambios)
    with pytest.raises(ex.ExpedienteInvalido) as error:
        m.leer_checkpoint(ex.bytes_canonicos(pieza))
    assert error.value.motivo == motivo


@pytest.mark.parametrize("literal", [b"NaN", b"Infinity", b"-Infinity", b"1e999"])
def test_g1_json_no_canonico_o_no_finito(literal):
    m = _m()
    datos = fpc.c1().datos
    with pytest.raises(ex.ExpedienteInvalido) as error:
        m.leer_checkpoint(datos.replace(b"\n", b" \n"))
    assert error.value.motivo == "pieza_no_canonica"
    malo = datos.replace(b'"posicion":1,', b'"posicion":' + literal + b",")
    assert malo != datos
    with pytest.raises(ex.ExpedienteInvalido) as error:
        m.leer_checkpoint(malo)
    assert error.value.motivo == "pieza_ilegible"
    observacion = fpc.observacion(fpc.c2(), "m1").datos
    with pytest.raises(ex.ExpedienteInvalido) as error:
        m.leer_observacion(observacion.replace(b'"posicion":2,', b'"posicion":' + literal + b","))
    assert error.value.motivo == "pieza_ilegible"


def test_g1_conjuntos_politicas_e_inventario_con_lectura_endurecida():
    m = _m()
    conjunto = m.componer_checkpoints([fpc.c1(), fpc.c2()])
    assert m.leer_checkpoints(conjunto) == (fpc.c1(), fpc.c2())
    for mutacion, motivo in ((lambda a: a.update({"checkpoints/001/extra.bin": b"x"}), "archivo_no_declarado"),
                             (lambda a: a.update({"checkpoints/001/firma.bin": b"0" * 64}), "sha256_incorrecto"),
                             (lambda a: a.pop("checkpoints/002/datos.json"), "archivo_faltante")):
        copia = dict(conjunto)
        mutacion(copia)
        with pytest.raises(ep.ExpedienteIlegible) as error:
            m.leer_checkpoints(copia)
        assert error.value.motivo == motivo
    manifiesto = json.loads(conjunto["checkpoints.json"])
    manifiesto["checkpoints"][0]["datos"] = "../fuera/datos.json"
    with pytest.raises(ep.ExpedienteIlegible) as error:
        m.leer_checkpoints({**conjunto, "checkpoints.json": rp.serializar_entrada(manifiesto)})
    assert error.value.motivo == "ruta_invalida"
    with pytest.raises(ep.ExpedienteIlegible) as error:
        m.leer_observaciones(m.componer_observaciones([fpc.observacion(fpc.c1(), "m1")] * (m.MAXIMO_DE_PIEZAS + 1)))
    assert error.value.motivo == "demasiadas_piezas"
    politica = m.leer_politica_de_rol(fpc.politica("monitor", ("m1", "m2")))
    assert politica.rol == "monitor" and politica.claves == (fpc.clave_publica("m1"), fpc.clave_publica("m2"))
    with pytest.raises(ep.ExpedienteIlegible) as error:
        m.leer_politica_de_rol(m.componer_politica_de_rol(rol="monitor", claves=[
            (fpc.clave_publica("m1"), "uno"), (fpc.clave_publica("m1"), "dos")]))
    assert error.value.motivo == "clave_duplicada"
    with pytest.raises(ep.ExpedienteIlegible) as error:
        m.leer_politica_de_rol(m.componer_politica_de_rol(rol="auditor", claves=[]))
    assert error.value.motivo == "rol_desconocido"
    inventario = m.leer_inventario(fpc.inventario())
    assert inventario.procedencia == "declarada_por_quien_verifica" and len(inventario.checkpoints) == 2
    cabecera = json.loads(fpc.inventario()["inventario.json"])
    for cambio in ({"procedencia": "publicada"}, {"monitores": cabecera["monitores"][::-1]},
                   {"checkpoints": [cabecera["checkpoints"][0]] * 2}):
        with pytest.raises(ep.ExpedienteIlegible) as error:
            m.leer_inventario({"inventario.json": rp.serializar_entrada({**cabecera, **cambio})})
        assert error.value.motivo == "estructura_invalida"


# ===========================================================================
# G1: politicas de rol y claves reutilizadas
# ===========================================================================

def test_g1_claves_reutilizadas_entre_roles_y_rol_no_coincidente():
    m = _m()
    reutilizada = _verificar(m, publicadores=("p", "m1"))
    assert "clave_reutilizada_entre_roles" in reutilizada["lectura"]["motivos"]
    assert reutilizada["resultado"] == "lectura_rechazada" and m.codigo_de_salida(reutilizada) == 3
    de_constancias = _verificar(m, publicadores=("p", "x"))
    assert "clave_reutilizada_entre_roles" in de_constancias["lectura"]["motivos"]
    cruzada = m.verificar(**{**fpc.entradas(), "politica_de_publicadores": fpc.politica("monitor", ("p",))})
    assert "rol_no_coincide" in cruzada["lectura"]["motivos"] and m.codigo_de_salida(cruzada) == 3
    assert all(f["admitida"] is False for f in reutilizada["checkpoints"])


def test_g1_firma_o_clave_incorrecta_y_alteracion_de_un_byte():
    m = _m()
    ajeno = fpc.checkpoint(fpc.cabezas_c2(), 2, fpc.c1(), publicador="ajeno")
    informe = _verificar(m, checkpoints=[fpc.c1(), ajeno])
    assert "clave_no_admitida" in _fila(informe, "checkpoints", ajeno)["motivos"]
    assert m.codigo_de_salida(informe) == 4
    c2 = fpc.c2()
    alterado = ex.ObjetoFirmado(c2.datos.replace(b'"posicion":2', b'"posicion":3'), c2.firma, c2.clave_publica)
    fila = next(f for f in _verificar(m, checkpoints=[fpc.c1(), alterado])["checkpoints"]
                if f["id"] == fpc.id_(alterado))
    assert "firma_no_coincide" in fila["motivos"] and fila["admitida"] is False
    obs = fpc.observacion(c2, "m1")
    mala = ex.ObjetoFirmado(obs.datos, bytes([obs.firma[0] ^ 1]) + obs.firma[1:], obs.clave_publica)
    informe = _verificar(m, observaciones=[mala, fpc.observacion(c2, "m2")])
    assert "firma_no_coincide" in _fila(informe, "observaciones", mala)["motivos"]
    sin_q = _verificar(m, checkpoints=[fpc.c1(), fpc.checkpoint(fpc.cabezas_c2(), 2, fpc.c1(), publicador="q")])
    assert m.codigo_de_salida(sin_q) in (4, 5)


# ===========================================================================
# G1: progresion, bifurcaciones, vinculos y observaciones
# ===========================================================================

def test_g1_continuidad_valida_y_progresion_observada():
    m = _m()
    informe = _verificar(m)
    assert informe["resultado"] == "coincidente_con_lo_suministrado" and m.codigo_de_salida(informe) == 0
    assert informe["registros"][0]["progresion"] == "progresion_demostrable_entre_lo_presentado"
    assert _fila(informe, "checkpoints", fpc.c2())["rol"] == "cabeza"
    assert _fila(informe, "checkpoints", fpc.c1())["estado"] == "predecesor"
    assert informe["planos"]["concordancia_con_referencias"]["estado"] == "coincide"
    assert informe["planos"]["cobertura_del_inventario"]["estado"] == "completa_respecto_del_inventario"
    progresion = _verificar(m, observaciones=[fpc.observacion(fpc.c1(), "m1"), fpc.observacion(fpc.c2(), "m2")],
                            inventario_=fpc.inventario(monitores=("m2",)))
    assert m.codigo_de_salida(progresion) == 0
    assert {f["estado"] for f in progresion["observaciones"]} == {"coincide_con_el_checkpoint"}


def test_g1_bifurcacion_vinculo_roto_retroceso_y_serie_retirada():
    m = _m()
    bifurcacion = _verificar(m, checkpoints=[fpc.c1(), fpc.c2(), fpc.c2_sustituto()])
    assert bifurcacion["motivos"]["contradicciones"] == ["bifurcacion_firmada_del_publicador"]
    assert m.codigo_de_salida(bifurcacion) == 1
    otro = fpc.checkpoint(fpc.cabezas_c1(), registro="otro-registro")
    roto = fpc.checkpoint(fpc.cabezas_c2(), 2, otro)
    assert "vinculo_roto" in _verificar(m, checkpoints=[fpc.c1(), roto])["motivos"]["contradicciones"]
    x1, x2, y1 = fpc.constancias()
    adelantado = fpc.checkpoint([fpc.cabeza(x2, "x", secuencia=2)])
    retrocede = fpc.checkpoint([fpc.cabeza(x1, "x")], 2, adelantado)
    assert "cabeza_retrocede" in _verificar(m, checkpoints=[adelantado, retrocede])["motivos"]["contradicciones"]
    con_y = fpc.checkpoint([fpc.cabeza(x1, "x"), fpc.cabeza(y1, "y")])
    retirada = fpc.checkpoint([fpc.cabeza(x2, "x", secuencia=2)], 2, con_y)
    assert "serie_retirada" in _verificar(m, checkpoints=[con_y, retirada])["motivos"]["contradicciones"]


def test_g1_observaciones_incompatibles_y_discrepancias_sin_contexto():
    m = _m()
    c2, sust = fpc.c2(), fpc.c2_sustituto()
    incompatible = fpc.observacion(c2, "m2", posicion=3)
    informe = _verificar(m, observaciones=[fpc.observacion(c2, "m1"), incompatible])
    assert _fila(informe, "observaciones", incompatible)["estado"] == "incompatible_con_el_checkpoint"
    assert informe["motivos"]["contradicciones"] == ["observacion_incompatible_con_el_checkpoint"]
    mismo = _verificar(m, observaciones=[fpc.observacion(c2, "m1"), fpc.observacion(sust, "m1")])
    assert "observaciones_incompatibles_del_mismo_monitor" in mismo["motivos"]["contradicciones"]
    discrepancia = _verificar(m, observaciones=[fpc.observacion(c2, "m1"), fpc.observacion(sust, "m2")])
    assert discrepancia["motivos"]["contradicciones"] == []
    assert "discrepancia_entre_monitores" in discrepancia["motivos"]["discrepancias"]
    assert discrepancia["resultado"] == "discrepancia_entre_actores" and m.codigo_de_salida(discrepancia) == 6
    # Sin checkpoints presentados no hay contexto: ninguna contradiccion.
    sin_contexto = _verificar(m, checkpoints=[], observaciones=[fpc.observacion(c2, "m1"),
                                                                 fpc.observacion(sust, "m2")])
    assert sin_contexto["motivos"]["contradicciones"] == []
    assert "checkpoint_observado_no_presentado" in sin_contexto["motivos"]["incompletas"]
    # Registros distintos no son comparables.
    otro = fpc.checkpoint(fpc.cabezas_c2(), registro="otro-registro")
    incomparable = _verificar(m, checkpoints=[fpc.c1(), c2, otro], inventario_=None)
    assert incomparable["motivos"]["contradicciones"] == []


def test_g1_cabeza_omitida_sustitucion_y_politica_distinta():
    m = _m()
    sust = fpc.c2_sustituto()
    omitida = _verificar(m, checkpoints=[fpc.c1(), sust], observaciones=[fpc.observacion(sust, "m1"),
                                                                         fpc.observacion(sust, "m2")],
                         inventario_=fpc.inventario(checkpoints=[fpc.c1(), sust]))
    fila = _fila(omitida, "checkpoints", sust)
    assert fila["cotejo"] == ["cabeza_no_publicada"]
    assert fila["cabezas_no_publicadas"] == [fpc.id_(fpc.constancias()[2])]
    assert m.codigo_de_salida(omitida) == 4
    sustitucion = _verificar(m, checkpoints=[fpc.c1(), sust])
    referencia = sustitucion["planos"]["concordancia_con_referencias"]
    assert referencia["no_coinciden"] == [{"esperado": fpc.id_(fpc.c2()), "presentados": [fpc.id_(sust)],
                                           "posicion": 2, "registro": fpc.REGISTRO}]
    assert "observacion_de_otro_contenido" in sustitucion["motivos"]["discrepancias"]
    otra = fpc.checkpoint(fpc.cabezas_c2(), 2, fpc.c1(), sha256_politica_de_constancias="0" * 64)
    assert "politica_de_constancias_no_coincide" in _verificar(m, checkpoints=[fpc.c1(), otra])["motivos"][
        "no_coincide"]
    inventada = fpc.checkpoint([*fpc.cabezas_c2(), [fpc.huella("p"), "serie-inventada", 1, "1" * 64]], 2, fpc.c1())
    assert "cabeza_publicada_no_presentada" in _verificar(m, checkpoints=[fpc.c1(), inventada])["motivos"][
        "no_coincide"]


def test_g1_evidencia_ausente_e_inventario():
    m = _m()
    predecesor = _verificar(m, checkpoints=[fpc.c2()])
    assert predecesor["registros"][0]["progresion"] == "pendiente"
    assert {"predecesor_no_presentado", "checkpoint_esperado_no_presentado"} <= set(predecesor["motivos"]["incompletas"])
    assert m.codigo_de_salida(predecesor) == 5
    sin = _verificar(m, inventario_=None)
    assert sin["planos"]["concordancia_con_referencias"]["estado"] == "no_evaluable"
    assert sin["motivos"]["incompletas"] == ["inventario_no_aportado"] and m.codigo_de_salida(sin) == 5
    incompleto = _verificar(m, inventario_=fpc.inventario(monitores=("m1", "m2", "m3")))
    assert incompleto["planos"]["cobertura_del_inventario"]["monitores"]["faltan"] == [fpc.huella("m3")]
    sobra = _verificar(m, inventario_=fpc.inventario(monitores=("m1",)))
    assert sobra["planos"]["cobertura_del_inventario"]["monitores"]["sobran"] == [fpc.huella("m2")]
    assert m.codigo_de_salida(sobra) == 4
    sin_cabeza = _verificar(m, inventario_=fpc.inventario(cabezas=[fpc.cabezas_c2()[0][3], "2" * 64]))
    cobertura = sin_cabeza["planos"]["cobertura_del_inventario"]["cabezas"]
    assert cobertura["faltan"] == ["2" * 64] and cobertura["sobran"] == [fpc.cabezas_c2()[1][3]]
    ninguno = _verificar(m, checkpoints=[], observaciones=[])
    assert "sin_checkpoint_admitido" in ninguno["motivos"]["incompletas"]


def test_g1_recalculo_de_ae80_y_ae79_sin_informe_aportado():
    m = _m()
    informe = _verificar(m)
    directo = ca.verificar(**fc.entradas("s2"), politica_de_constancias=fc.politica_de_constancias(),
                           constancias=[ca.componer_constancias(list(fpc.constancias()))])
    assert informe["ae80"]["cabezas"] == m.cabezas_de_constancias(directo)
    assert informe["ae80"]["sha256_informe_ae79"] == directo["estado_recalculado"]["sha256_informe_ae79"]
    assert "informe" not in m.verificar.__code__.co_varnames[:m.verificar.__code__.co_kwonlyargcount]
    x1, x2, y1 = fpc.constancias()
    rama = fc.constancia("s1", "x", 2, x1)
    bifurcado = m.verificar(**{**fpc.entradas(), "constancias": [ca.componer_constancias([x1, x2, y1, rama])]})
    assert "contradiccion_en_constancias_ae80" in bifurcado["motivos"]["contradicciones"]


def test_g1_duplicados_copias_invalidas_y_orden():
    m = _m()
    c2 = fpc.c2()
    falsa = ex.ObjetoFirmado(c2.datos, bytes(64), c2.clave_publica)
    base = fpc.entradas()
    uno = m.verificar(**{**base, "checkpoints": [m.componer_checkpoints([fpc.c1(), c2, c2, falsa])]})
    dos = m.verificar(**{**base, "checkpoints": [m.componer_checkpoints([falsa, fpc.c1()]),
                                                 m.componer_checkpoints([c2])]})
    assert len([f for f in uno["checkpoints"] if f["id"] == fpc.id_(c2)]) == 2
    assert uno["registros"] == dos["registros"] and uno["resultado"] == dos["resultado"] == "no_coincide"
    permutado = m.verificar(**{**base, "expedientes": base["expedientes"][::-1],
                               "observaciones": base["observaciones"][::-1]})
    assert m.informe_json(permutado) == m.informe_json(m.verificar(**base))


def test_g1_planos_separados_y_sin_promocion_en_todos_los_escenarios():
    m = _m()
    casos = [fpc.entradas(), fpc.entradas(inventario_=fpc.inventario(procedencia="copiada_de_lo_presentado")),
             fpc.entradas(checkpoints=[fpc.c1(), fpc.c2(), fpc.c2_sustituto()]), fpc.entradas(inventario_=None)]
    for entradas in casos:
        informe = m.verificar(**entradas)
        planos = informe["planos"]
        assert set(planos) == {"integridad_de_bytes_y_firmas", "concordancia_con_referencias",
                               "cobertura_del_inventario", "publicacion_externa",
                               "autoridad_de_claves_y_del_conjunto_esperado", "cronologia", "completitud_global",
                               "autorizacion_operativa"}
        assert planos["publicacion_externa"]["estado"] == "no_acreditada"
        assert planos["autoridad_de_claves_y_del_conjunto_esperado"]["estado"] == "pendiente"
        assert planos["cronologia"]["estado"] == planos["completitud_global"]["estado"] == "pendiente"
        assert planos["autorizacion_operativa"] == {"estado": "denegada", "AUTORIZA_EVALUACION": False,
                                                    "r0_final": "no_se_promociona"}
    copiada = m.verificar(**casos[1])
    assert "referencias_copiadas_de_lo_presentado" in copiada["planos"]["publicacion_externa"]["motivos"]
    assert copiada["planos"]["concordancia_con_referencias"]["procedencia"] == "copiada_de_lo_presentado"
    texto = json.dumps(m.verificar(**casos[0]))
    assert "publicada_externamente" not in texto and "completitud_global_superada" not in texto


def test_g1_sin_claves_privadas_en_piezas_politicas_inventario_ni_informe():
    m = _m()
    entradas = fpc.entradas()
    informe = m.informe_json(m.verificar(**entradas))
    archivos = [*entradas["checkpoints"], *entradas["observaciones"], entradas["politica_de_publicadores"],
                entradas["politica_de_monitores"], entradas["inventario"]]
    for conjunto in archivos:
        for datos in conjunto.values():
            assert b"PRIVATE KEY" not in datos
            for privada in fpc.claves_privadas():
                assert privada not in datos
    for privada in fpc.claves_privadas():
        assert privada not in informe and privada.hex().encode() not in informe


def test_g1_codigos_limites_y_pureza():
    m = _m()
    assert dict(m.CODIGOS_DE_SALIDA) == {"coincidente_con_lo_suministrado": 0, "contradiccion_comprobada": 1,
                                         "uso_incorrecto": 2, "lectura_rechazada": 3, "no_coincide": 4,
                                         "evidencia_incompleta": 5, "discrepancia_entre_actores": 6}
    assert all("autoriz" not in k for k in m.CODIGOS_DE_SALIDA)
    assert "no acredita publicacion externa" in m.SIGNIFICADO_DE_LOS_CODIGOS[0]
    for a, b in ((m.CONTRADICCIONES, m.NO_COINCIDENCIAS), (m.CONTRADICCIONES, m.DISCREPANCIAS),
                 (m.NO_COINCIDENCIAS, m.DISCREPANCIAS), (m.INCOMPLETAS, m.CONTRADICCIONES)):
        assert set(a).isdisjoint(b)
    texto = " ".join(m.LIMITES)
    for fragmento in ("no acreditan publicacion externa", "no prueban anterioridad", "no se usa mayoria, quorum",
                      "asi se etiquetan", "ningun informe aportado", "no heredan sus garantias",
                      "AUTORIZA_EVALUACION es False"):
        assert fragmento in texto, fragmento
    arbol = ast.parse(Path(m.__file__).read_text(encoding="utf-8"))
    prohibidos = {"socket", "urllib", "requests", "http", "time", "subprocess", "random", "os", "pathlib",
                  "sqlalchemy", "datetime", "secrets", "pickle", "marshal", "shelve", "yaml", "cryptography"}
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            assert not {a.name.split(".")[0] for a in nodo.names} & prohibidos
        if isinstance(nodo, ast.ImportFrom):
            assert (nodo.module or "").split(".")[0] not in prohibidos
        if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name):
            assert nodo.func.id not in {"open", "eval", "exec", "__import__"}
        if isinstance(nodo, ast.Attribute):
            assert nodo.attr not in {"now", "today", "utcnow"}


def test_g1_limite_de_conjuntos():
    m = _m()
    with pytest.raises(ValueError, match="numero_de_conjuntos"):
        m.verificar(**{**fpc.entradas(), "observaciones": [{}] * (m.MAXIMO_DE_CONJUNTOS + 1)})


# ===========================================================================
# G2: invariantes de AE-52 y AE-74 a AE-80 (pasan sobre la base)
# ===========================================================================

def test_g2_huellas_de_ae52_ae74_y_ae78_a_ae80():
    assert _huella((rp.ESQUEMA_ENTRADA, rp.TIPOS_ENTRADA, rp.REGLAS_EVALUACION_AE52, rp.PENDIENTES_BORRADOR_AE52,
                    rp.NOTA_PROTOCOLO, rp.ALCANCE_REGISTRO)) == (
        "4f31cdeb3c4d29b1740592d4d81de2f8f51305abf4a82743c49f12985621c50b")
    assert _huella(cv.DECISIONES_DEL_CONTRATO) == "56cc40d8af732aea86ca88dc3a16ee64254212a1e40ae7e51a75eafe05c554ea"
    assert _huella((ep.ESQUEMA_EXPEDIENTE, ep.ESQUEMA_POLITICA, ep.ESQUEMA_INFORME, ep.NOMBRE_MANIFIESTO,
                    ep.NOMBRE_POLITICA, ep.NATURALEZAS_DE_POLITICA, ep.LIMITES_POR_DEFECTO, ep.CODIGOS_DE_SALIDA,
                    ep.SIGNIFICADO_DE_LOS_CODIGOS, ep.LIMITES)) == (
        "9b8c9fdbbde319849a4dcfe5978149700ab923bdc86c2af09d0b9b5b63b0f3f8")
    assert _huella((ac.ESQUEMA_CAPTURA, ac.ESQUEMA_CAPTURAS, ac.ESQUEMA_POLITICA_AUDITORIA, ac.ESQUEMA_INFORME,
                    ac.CLAVES_DE_LA_CAPTURA, ac.CAMPOS_DEL_EXPEDIENTE, ac.MINIMO_DE_EXPEDIENTES,
                    ac.MAXIMO_DE_EXPEDIENTES, ac.MAXIMO_DE_CONJUNTOS_DE_CAPTURAS, ac.MAXIMO_DE_CAPTURAS,
                    ac.BYTES_AGREGADOS, ac.ARCHIVOS_AGREGADOS, ac.CONTRADICCIONES, ac.NO_COINCIDENCIAS,
                    ac.CRITERIO_DE_ADMISION, ac.PENDIENTES, ac.CODIGOS_DE_SALIDA, ac.SIGNIFICADO_DE_LOS_CODIGOS,
                    ac.DECISIONES_ABIERTAS, ac.LIMITES)) == (
        "90431ebfa05f8e585035c0c0ea8a58b1a94330c5b4e5922ce289b25e4f163689")
    assert _huella((ca.ESQUEMA_CONSTANCIA, ca.ESQUEMA_CONSTANCIAS, ca.ESQUEMA_POLITICA_CONSTANCIAS, ca.ESQUEMA_INFORME,
                    ca.DOMINIO_DE_PRUEBA, ca.NATURALEZAS, ca.CLAVES_DE_LA_CONSTANCIA, ca.CAMPOS_DEL_ESTADO,
                    ca.DECISIONES_ABIERTAS_AE80, ca.CONTRADICCIONES, ca.NO_COINCIDENCIAS, ca.LECTURAS_DE_ENTRADAS,
                    ca.PENDIENTES, ca.CODIGOS_DE_SALIDA, ca.SIGNIFICADO_DE_LOS_CODIGOS, ca.LIMITES,
                    ca.MAXIMO_DE_CONSTANCIAS, ca.MAXIMO_DE_CONJUNTOS_DE_CONSTANCIAS)) == (
        "4f9c5bcb9824c88522a27feb11320b6e430560e83b9bca8f47dd207ba893e077")


def test_g2_estados_del_expediente_sin_cambios():
    assert pi.AUTORIZA_EVALUACION is False
    assert cv.DECISIONES_DEL_CONTRATO["D8"]["estado"] == "aprobada_solo_para_el_modelo_sintetico"
    assert cv.DECISIONES_DEL_CONTRATO["D9"]["estado"] == "espera_provisional_aprobada"
    assert ac.DECISIONES_ABIERTAS == ("A1", "A2", "A3", "C1", "C2", "C3", "D8_operativa", "D9_definitiva")


# ===========================================================================
# G3: premisas sobre el informe de AE-80 (pasan sobre la base)
# ===========================================================================

def test_g3_el_informe_de_ae80_identifica_cabezas_admitidas_y_su_politica():
    x1 = fc.constancia("s1")
    x2 = fc.constancia("s2", "x", 2, x1)
    informe = ca.verificar(**fc.entradas("s2"), politica_de_constancias=fc.politica_de_constancias(),
                           constancias=[ca.componer_constancias([x1, x2])])
    cabezas = [c for c in informe["constancias"] if c["admitida"] and c["rol"] == "cabeza"]
    assert [(c["serie"], c["secuencia"], c["id"]) for c in cabezas] == [(fc.SERIE, 2, ex.hash_de_pieza(x2.datos))]
    assert informe["politica_de_constancias"]["sha256"] == hashlib.sha256(
        fc.politica_de_constancias()["politica_constancias.json"]).hexdigest()
    assert ex.huella_de_clave(fc.clave_publica("x")) in informe["politica_de_constancias"]["firmantes"]
