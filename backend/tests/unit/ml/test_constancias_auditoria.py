"""Tests de la Etapa AE-80, validada localmente como trabajo preparatorio:
constancias desprendidas y verificables de una auditoria cruzada AE-79.

G1  funcionalidad nueva, importada dentro de cada prueba (sobre la base falla
    con `ModuleNotFoundError`): formato estricto, politica de claves aparte,
    recalculo del informe AE-79, alteraciones de un byte, firmas y claves,
    claves repetidas con etiquetas distintas, continuidad, bifurcaciones,
    desacuerdos, predecesores omitidos, no presentado frente a presentado
    pero invalido, duplicados, procedencia, orden, material privado y no
    promocion de pendientes.
G2  invariantes de AE-52 y AE-74 a AE-79: huellas y estados.
G3  premisas sobre el codigo existente que la verificacion reutiliza.

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
from app.application.ml import contrato_vinculo_r0 as cv
from app.application.ml import expediente_portable as ep
from app.application.ml import expediente_r0_recepcion as ex
from app.application.ml import propuesta_inferencia_prospectiva as pi
from app.application.ml import recepcion_por_objetivo as ro
from app.application.ml import registro_prospectivo as rp
from app.application.ml import sello_temporal_r0 as st
from tests.unit.ml import fixtures_auditoria_cruzada as fa
from tests.unit.ml import fixtures_constancias_auditoria as fc
from tests.unit.ml import fixtures_expediente_r0 as fx


def _m():
    return importlib.import_module("app.application.ml.constancias_auditoria")


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


def _verificar(m, estado, constancias=(), *, politica=None, conjuntos=None, referencias=None, **cambios):
    entradas = {**fc.entradas(estado), **cambios}
    conjuntos = conjuntos if conjuntos is not None else ([m.componer_constancias(list(constancias))]
                                                         if constancias else [])
    return m.verificar(**entradas, politica_de_constancias=politica or fc.politica_de_constancias(),
                       constancias=conjuntos, referencias=referencias or m.ReferenciasDeConstancias())


def _fila(informe, objeto):
    return next(c for c in informe["constancias"] if c["id"] == fc.id_(objeto))


def _todos_los_motivos(informe) -> set:
    vistos = set(informe["entre_constancias"]["motivos"])
    for c in informe["constancias"]:
        vistos.update(c["motivos"])
        vistos.update(c.get("cotejo", []))
    for s in informe["series"]:
        vistos.update(p["motivo"] for p in s["pendientes"])
    return vistos


# ===========================================================================
# G1: formato y recalculo
# ===========================================================================

def test_g1_constancia_vincula_dominio_politicas_entradas_informe_y_posicion():
    m = _m()
    x1 = fc.constancia("s1")
    x2 = fc.constancia("s2", "x", 2, x1)
    pieza = m.leer_constancia(x2.datos)
    assert tuple(sorted(pieza)) == tuple(sorted(m.CLAVES_DE_LA_CONSTANCIA))
    assert x2.datos == ex.bytes_canonicos(pieza)
    assert pieza["esquema"] == m.ESQUEMA_CONSTANCIA == "constancia-auditoria-cruzada/1"
    assert pieza["dominio"] == m.DOMINIO_DE_PRUEBA and pieza["naturaleza"] == "fixture_de_prueba"
    assert (pieza["serie"], pieza["secuencia"], pieza["anterior"]) == (fc.SERIE, 2, fc.id_(x1))
    estado = fc.estado("s2")
    assert {c: pieza[c] for c in m.CAMPOS_DEL_ESTADO} == estado.campos()
    assert pieza["sha256_politica_del_verificador"] == fa.sha256_politica()
    assert pieza["entradas"]["expedientes"] == sorted([fa.sha(fa.e1()), fa.sha(fa.e2())])
    assert pieza["huella_de_clave"] == ex.huella_de_clave(fc.clave_publica("x"))
    with pytest.raises(ValueError, match="serie_mal_formada"):
        m.construir_constancia(estado, serie="Serie Mala", secuencia=1, anterior=None,
                               clave_publica=fc.clave_publica("x"))
    with pytest.raises(ValueError, match="encadenamiento_mal_formado"):
        m.construir_constancia(estado, serie=fc.SERIE, secuencia=2, anterior=None, clave_publica=fc.clave_publica("x"))


def test_g1_el_informe_ae79_se_recalcula_con_nombres_neutros_y_nunca_se_acepta_aportado():
    m = _m()
    entradas = fc.entradas("s1")
    estado = m.estado_auditado(**entradas)
    directo = ac.auditar(expedientes=[("cualquier-nombre", e) for e in entradas["expedientes"]],
                         politica_del_verificador=entradas["politica_del_verificador"],
                         politica_de_auditoria=entradas["politica_de_auditoria"],
                         capturas=[("otro-nombre", c) for c in entradas["capturas"]])
    neutro = ac.auditar(expedientes=[("entrada", e) for e in entradas["expedientes"]],
                        politica_del_verificador=entradas["politica_del_verificador"],
                        politica_de_auditoria=entradas["politica_de_auditoria"],
                        capturas=[("entrada", c) for c in entradas["capturas"]])
    assert estado.informe_ae79 == neutro
    assert estado.sha256_informe_ae79 == hashlib.sha256(ac.informe_json(neutro)).hexdigest()
    assert ac.informe_json(directo) != ac.informe_json(neutro)
    assert estado.resultado_ae79 == {"resultado": "sin_contradiccion_detectable", "entre_expedientes": "compatibles"}
    informe = _verificar(m, "s1", [fc.constancia("s1", sha256_informe_ae79=hashlib.sha256(b"{}").hexdigest())])
    assert informe["constancias"][0]["cotejo"] == ["informe_no_coincide"]
    assert informe["informe_ae79"] == neutro
    assert "verificar" in m.__dict__ and not any("informe_aportado" in a for a in m.verificar.__code__.co_varnames)


@pytest.mark.parametrize("cambios, motivo", [
    ({"secuencia": 0}, "pieza_mal_formada"),
    ({"anterior": "0" * 64}, "pieza_mal_formada"),
    ({"sha256_informe_ae79": "X" * 64}, "pieza_mal_formada"),
    ({"entradas": {"expedientes": ["b" * 64, "a" * 64], "conjuntos_de_capturas": []}}, "pieza_mal_formada"),
    ({"entradas": {"expedientes": ["a" * 64, "a" * 64], "conjuntos_de_capturas": []}}, "pieza_mal_formada"),
    ({"resultado_ae79": {"resultado": "x"}}, "pieza_mal_formada"),
    ({"dominio": "otro-dominio"}, "dominio_no_admitido"),
    ({"naturaleza": "operativa"}, "naturaleza_no_admitida"),
    ({"extra": 1}, "pieza_ilegible"),
    ({"esquema": "constancia-auditoria-cruzada/2"}, "version_desconocida"),
])
def test_g1_lectura_estricta_de_la_constancia(cambios, motivo):
    m = _m()
    pieza = m.leer_constancia(fc.constancia("s1").datos)
    pieza.update(cambios)
    with pytest.raises(ex.ExpedienteInvalido) as error:
        m.leer_constancia(ex.bytes_canonicos(pieza))
    assert error.value.motivo == motivo
    with pytest.raises(ex.ExpedienteInvalido) as error:
        m.leer_constancia(fc.constancia("s1").datos.replace(b"\n", b" \n"))
    assert error.value.motivo == "pieza_no_canonica"


H0 = "0" * 64


@pytest.mark.parametrize("alcance", [
    [[H0, "canal", []], [H0, 7, []]],
    [[H0, "canal", []], 5],
    [[H0, "canal", []], {"canal": "x"}],
    [[H0, "canal", ["BALOTO"]], [H0, "canal", [3]]],
])
def test_g1_alcance_mal_tipado_se_rechaza_sin_comparar_tipos_distintos(alcance):
    """Regresion: el orden de `alcance` se comprobaba antes de su forma y
    sus tipos, y `sorted` lanzaba `TypeError` con elementos no comparables
    en una pieza JSON canonica."""
    m = _m()
    pieza = m.leer_constancia(fc.constancia("s1").datos)
    pieza["alcance"] = alcance
    with pytest.raises(ex.ExpedienteInvalido) as error:
        m.leer_constancia(ex.bytes_canonicos(pieza))
    assert error.value.motivo == "pieza_mal_formada"
    firmada = fc.firmar(pieza, "x")
    informe = _verificar(m, "s1", [firmada])
    fila = informe["constancias"][0]
    assert fila["admitida"] is False and fila["motivos"] == ["pieza_mal_formada"]
    assert informe["resultado"] == "constancia_no_coincide" and m.codigo_de_salida(informe) == 4


@pytest.mark.parametrize("literal", [b"NaN", b"Infinity", b"-Infinity", b"1e999"])
def test_g1_constantes_no_estandar_se_rechazan_como_pieza_ilegible(literal):
    """Regresion: `json.loads` acepta NaN, Infinity y 1e999, pero la
    serializacion canonica de AE-52 no; el error escapaba de
    `leer_constancia` como `EntradaRegistroInvalidaError`."""
    m = _m()
    datos = fc.constancia("s1").datos.replace(b'"secuencia":1', b'"secuencia":' + literal)
    with pytest.raises(ex.ExpedienteInvalido) as error:
        m.leer_constancia(datos)
    assert error.value.motivo == "pieza_ilegible"
    firmada = ex.ObjetoFirmado(datos, fc.clave_privada("x").sign(datos), fc.clave_publica("x"))
    informe = _verificar(m, "s1", [firmada])
    assert informe["constancias"][0]["motivos"] == ["pieza_ilegible"]
    assert informe["constancias"][0]["admitida"] is False and m.codigo_de_salida(informe) == 4


def test_g1_alteracion_de_un_byte_y_firmas_incorrectas():
    m = _m()
    x1 = fc.constancia("s1")
    posicion = x1.datos.index(b'"secuencia":') + len(b'"secuencia":')
    alterada = ex.ObjetoFirmado(x1.datos[:posicion] + b"7" + x1.datos[posicion + 1:], x1.firma, x1.clave_publica)
    firma_mala = ex.ObjetoFirmado(x1.datos, bytes([x1.firma[0] ^ 1]) + x1.firma[1:], x1.clave_publica)
    for objeto in (alterada, firma_mala):
        informe = _verificar(m, "s1", [objeto])
        fila = informe["constancias"][0]
        assert "firma_no_coincide" in fila["motivos"] and fila["admitida"] is False
        assert informe["resultado"] == "constancia_no_coincide" and m.codigo_de_salida(informe) == 4
    otra_clave = ex.ObjetoFirmado(x1.datos, x1.firma, fc.clave_publica("y"))
    fila = _verificar(m, "s1", [otra_clave])["constancias"][0]
    assert {"firma_no_coincide", "huella_de_clave_no_coincide"} <= set(fila["motivos"])


# ===========================================================================
# G1: directorios y politica de claves aparte
# ===========================================================================

def test_g1_conjunto_de_constancias_y_politica_de_claves_con_lectura_endurecida():
    m = _m()
    constancias = [fc.constancia("s1"), fc.constancia("s1", "y")]
    archivos = m.componer_constancias(constancias)
    assert m.leer_constancias(archivos) == tuple(constancias)
    assert json.loads(archivos["constancias.json"])["esquema"] == "constancias-auditoria/1"
    for mutacion, motivo in ((lambda a: a.update({"constancias/001/extra.bin": b"x"}), "archivo_no_declarado"),
                             (lambda a: a.update({"constancias/001/firma.bin": b"0" * 64}), "sha256_incorrecto"),
                             (lambda a: a.pop("constancias/002/datos.json"), "archivo_faltante")):
        copia = dict(archivos)
        mutacion(copia)
        with pytest.raises(ep.ExpedienteIlegible) as error:
            m.leer_constancias(copia)
        assert error.value.motivo == motivo
    with pytest.raises(ep.ExpedienteIlegible) as error:
        m.leer_constancias(m.componer_constancias([constancias[0]] * (m.MAXIMO_DE_CONSTANCIAS + 1)))
    assert error.value.motivo == "demasiadas_constancias"
    manifiesto = json.loads(archivos["constancias.json"])
    manifiesto["constancias"][0]["datos"] = "../fuera/datos.json"
    with pytest.raises(ep.ExpedienteIlegible) as error:
        m.leer_constancias({**archivos, "constancias.json": rp.serializar_entrada(manifiesto)})
    assert error.value.motivo == "ruta_invalida"
    politica = m.leer_politica_de_constancias(fc.politica_de_constancias())
    assert [f.clave_publica for f in politica.firmantes] == [fc.clave_publica("x"), fc.clave_publica("y")]
    cabecera = json.loads(fc.politica_de_constancias()["politica_constancias.json"])
    assert cabecera["esquema"] == "politica-constancias-de-prueba/1" and cabecera["naturaleza"] == "fixture_de_prueba"
    with pytest.raises(ep.ExpedienteIlegible) as error:
        m.leer_politica_de_constancias({**fc.politica_de_constancias(), "politica_constancias.json":
                                        rp.serializar_entrada(dict(cabecera, naturaleza="operativa"))})
    assert error.value.motivo == "naturaleza_no_admitida"


def test_g1_misma_clave_con_dos_etiquetas_se_rechaza_y_no_es_otro_firmante():
    m = _m()
    duplicada = fc.politica_de_constancias(("x", "x"), etiquetas=["firmante uno", "firmante dos"])
    with pytest.raises(ep.ExpedienteIlegible) as error:
        m.leer_politica_de_constancias(duplicada)
    assert error.value.motivo == "clave_duplicada"
    informe = _verificar(m, "s1", [fc.constancia("s1")], politica=duplicada)
    assert informe["lectura"]["objeto"] == "politica_de_constancias"
    assert informe["resultado"] == "lectura_rechazada" and m.codigo_de_salida(informe) == 3
    # Dos series del mismo firmante con las mismas entradas e informes
    # incompatibles son una contradiccion del mismo firmante, no un acuerdo
    # entre dos firmantes.
    uno = fc.constancia("s1", serie="serie-uno")
    dos = fc.constancia("s1", serie="serie-dos", sha256_informe_ae79="0" * 64)
    informe = _verificar(m, "s1", [uno, dos])
    assert informe["entre_constancias"]["motivos"] == ["informes_incompatibles_del_mismo_firmante"]


def test_g1_politica_de_claves_suministrada_aparte_decide_que_firma_se_admite():
    m = _m()
    x1 = fc.constancia("s1")
    assert m.codigo_de_salida(_verificar(m, "s1", [x1])) == 0
    sin_x = _verificar(m, "s1", [x1], politica=fc.politica_de_constancias(("y",)))
    assert "clave_no_admitida" in sin_x["constancias"][0]["motivos"] and m.codigo_de_salida(sin_x) == 4
    ajena = _verificar(m, "s1", [fc.constancia("s1", "ajeno")])
    assert "clave_no_admitida" in ajena["constancias"][0]["motivos"]
    del_canal = _verificar(m, "s1", [fc.constancia("s1", "canal")],
                           politica=fc.politica_de_constancias(("x", "canal")))
    assert "firmante_no_independiente_del_canal" in del_canal["constancias"][0]["motivos"]
    for archivos in (fc.politica_de_constancias(), m.componer_constancias([x1])):
        assert "politica_constancias.json" not in m.componer_constancias([x1])
        assert all(not ruta.startswith("expediente") for ruta in archivos)
    assert "politica_constancias.json" not in fa.e1() and "constancias.json" not in fa.e1()


# ===========================================================================
# G1: series, bifurcaciones, desacuerdos y predecesores
# ===========================================================================

def test_g1_continuidad_valida_entre_lo_presentado():
    m = _m()
    x1 = fc.constancia("s1")
    x2 = fc.constancia("s2", "x", 2, x1)
    informe = _verificar(m, "s2", [x1, x2])
    assert informe["resultado"] == "constancia_y_auditoria_coincidentes" and m.codigo_de_salida(informe) == 0
    assert _fila(informe, x2)["rol"] == "cabeza" and _fila(informe, x2)["estado"] == "coincide"
    assert _fila(informe, x1)["rol"] == "predecesor" and _fila(informe, x1)["estado"] == "atestigua_otro_estado"
    serie = informe["series"][0]
    assert serie["continuidad"] == "enlazada_desde_la_primera_entre_lo_presentado"
    assert "no prueba que sea la ultima" in serie["nota"]
    assert informe["procedencia"]["cabezas"] == [{"constancia": fc.id_(x2), "estado": "cabeza_sin_referencia_externa"}]
    texto = json.dumps(informe)
    assert "cadena_integra" not in texto and "ultima_version" not in texto


def test_g1_bifurcacion_firmada_y_vinculo_roto():
    m = _m()
    x1 = fc.constancia("s1")
    x2 = fc.constancia("s2", "x", 2, x1)
    rama = fc.constancia("s1", "x", 2, x1)
    informe = _verificar(m, "s2", [x1, x2, rama])
    assert informe["entre_constancias"]["motivos"] == ["bifurcacion_firmada"]
    assert informe["series"][0]["continuidad"] == "contradiccion"
    assert informe["resultado"] == "contradiccion_comprobada" and m.codigo_de_salida(informe) == 1
    ajeno = fc.constancia("s1", "y")
    roto = fc.constancia("s2", "x", 2, ajeno)
    informe = _verificar(m, "s2", [x1, roto])
    assert informe["entre_constancias"]["motivos"] == ["vinculo_roto"]


def test_g1_desacuerdo_entre_firmantes_sin_adjudicar():
    m = _m()
    x1 = fc.constancia("s1")
    y1 = fc.constancia("s1", "y", resultado_ae79={"resultado": "contradiccion_comprobada",
                                                  "entre_expedientes": "contradiccion_comprobada"})
    informe = _verificar(m, "s1", [x1, y1])
    hallazgo = informe["entre_constancias"]["hallazgos"][0]
    assert hallazgo["motivo"] == "desacuerdo_entre_firmantes" and "no se adjudica" in hallazgo["nota"]
    assert informe["resultado"] == "contradiccion_comprobada"
    acuerdo = _verificar(m, "s1", [x1, fc.constancia("s1", "y")])
    assert acuerdo["entre_constancias"]["motivos"] == [] and m.codigo_de_salida(acuerdo) == 0
    # Mismas entradas pero otras politicas: incomparables, no desacuerdo.
    otra = fc.constancia("s1", "y", sha256_politica_de_auditoria="0" * 64, sha256_informe_ae79="1" * 64)
    assert _verificar(m, "s1", [x1, otra])["entre_constancias"]["motivos"] == []


def test_g1_predecesor_omitido_queda_pendiente_no_integro():
    m = _m()
    x1 = fc.constancia("s1")
    x2 = fc.constancia("s2", "x", 2, x1)
    informe = _verificar(m, "s2", [x2])
    serie = informe["series"][0]
    assert serie["continuidad"] == "pendiente"
    assert serie["pendientes"] == [{"constancia": fc.id_(x2), "motivo": "predecesor_no_presentado"}]
    assert m.codigo_de_salida(informe) == 0
    hueco = fc.constancia("s2", "x", 3, "0" * 64)
    con_hueco = _verificar(m, "s2", [x1, hueco])
    assert con_hueco["series"][0]["continuidad"] == "pendiente"


# ===========================================================================
# G1: sustitucion, no presentado frente a presentado pero invalido
# ===========================================================================

def test_g1_expediente_sustituido_y_entrada_no_presentada():
    m = _m()
    informe = _verificar(m, "sustituido", [fc.constancia("s1")])
    cotejo = informe["constancias"][0]["cotejo"]
    assert {"entrada_atestada_no_presentada", "entrada_presentada_no_atestada", "informe_no_coincide"} <= set(cotejo)
    assert informe["resultado"] == "constancia_no_coincide" and m.codigo_de_salida(informe) == 4
    ausente = _verificar(m, "s1", [fc.constancia("s1")], expedientes=[fa.e1(), fa.e4()])
    assert "entrada_atestada_no_presentada" in ausente["constancias"][0]["cotejo"]
    assert m.codigo_de_salida(ausente) == 4


def test_g1_entrada_atestada_presentada_pero_invalida_es_lectura_rechazada():
    m = _m()
    e2 = dict(fa.e2())
    e2["acuses/001/firma.bin"] = bytes([e2["acuses/001/firma.bin"][0] ^ 1]) + e2["acuses/001/firma.bin"][1:]
    informe = _verificar(m, "s1", [fc.constancia("s1")], expedientes=[fa.e1(), e2])
    cotejo = informe["constancias"][0]["cotejo"]
    assert "entrada_atestada_presentada_pero_ilegible" in cotejo and "entrada_atestada_no_presentada" not in cotejo
    assert informe["resultado"] == "lectura_rechazada" and m.codigo_de_salida(informe) == 3
    sin_bytes = _verificar(m, "s1", [fc.constancia("s1")],
                           expedientes=[fa.e1(), ep.ExpedienteIlegible("enlace_simbolico")])
    assert "entrada_presentada_ilegible_sin_huella" in sin_bytes["constancias"][0]["cotejo"]
    assert m.codigo_de_salida(sin_bytes) == 3
    ilegible = _verificar(m, "s1", conjuntos=[ep.ExpedienteIlegible("directorio_invalido")])
    assert ilegible["conjuntos_de_constancias"] == [{"lectura": {"estado": "rechazada",
                                                                 "motivos": ["directorio_invalido"]}}]
    assert m.codigo_de_salida(ilegible) == 3


def test_g1_sin_constancias_nada_queda_atestiguado():
    m = _m()
    informe = _verificar(m, "s1")
    assert informe["resultado"] == "sin_constancia_admitida" and m.codigo_de_salida(informe) == 5
    assert informe["informe_ae79"]["resultado"] == "sin_contradiccion_detectable"


def test_g1_duplicados_y_copias_con_firma_invalida():
    m = _m()
    x1 = fc.constancia("s1")
    falsa = ex.ObjetoFirmado(x1.datos, bytes(64), x1.clave_publica)
    uno = _verificar(m, "s1", conjuntos=[m.componer_constancias([x1, falsa]), m.componer_constancias([x1])])
    dos = _verificar(m, "s1", conjuntos=[m.componer_constancias([x1]), m.componer_constancias([falsa, x1])])
    assert m.informe_json(uno) != b"" and len(uno["constancias"]) == 2
    assert sorted(c["estado"] for c in uno["constancias"]) == ["coincide", "no_admitida"]
    assert [c["estado"] for c in uno["constancias"]] == [c["estado"] for c in dos["constancias"]]
    assert uno["series"] == dos["series"] and uno["resultado"] == dos["resultado"] == "constancia_no_coincide"


# ===========================================================================
# G1: procedencia, orden, material privado, pendientes y codigos
# ===========================================================================

def test_g1_procedencia_aportada_y_faltante():
    m = _m()
    x1 = fc.constancia("s1")
    sin = _verificar(m, "s1", [x1])
    assert set(sin["procedencia"]["faltan"]) == {"politica_de_constancias", "constancias"}
    assert sin["procedencia"]["publicacion_externa"] == "no_aportada"
    assert "publicacion independiente" in sin["procedencia"]["limite"]
    sha = hashlib.sha256(fc.politica_de_constancias()["politica_constancias.json"]).hexdigest()
    con = _verificar(m, "s1", [x1], referencias=m.ReferenciasDeConstancias(politica_de_constancias=sha,
                                                                           constancias=frozenset({fc.id_(x1)})))
    assert con["procedencia"]["faltan"] == [] and m.codigo_de_salida(con) == 0
    assert con["procedencia"]["cabezas"][0]["estado"] == "coincide_con_referencia_aportada"
    mala = _verificar(m, "s1", [x1], referencias=m.ReferenciasDeConstancias(constancias=frozenset({"0" * 64})))
    assert mala["procedencia"]["comprobaciones"][0]["motivos"] == ["constancia_esperada_no_presentada"]
    assert m.codigo_de_salida(mala) == 4
    with pytest.raises(ValueError):
        m.ReferenciasDeConstancias(politica_de_constancias="no-hex")


def test_g1_informe_determinista_e_independiente_del_orden():
    m = _m()
    x1 = fc.constancia("s1")
    x2 = fc.constancia("s2", "x", 2, x1)
    y2 = fc.constancia("s2", "y")
    entradas = fc.entradas("s2")
    uno = m.verificar(**entradas, politica_de_constancias=fc.politica_de_constancias(),
                      constancias=[m.componer_constancias([x1, x2]), m.componer_constancias([y2])])
    dos = m.verificar(expedientes=entradas["expedientes"][::-1],
                      politica_del_verificador=entradas["politica_del_verificador"],
                      politica_de_auditoria=entradas["politica_de_auditoria"], capturas=entradas["capturas"],
                      politica_de_constancias=fc.politica_de_constancias(),
                      constancias=[m.componer_constancias([y2]), m.componer_constancias([x1, x2])])
    assert m.informe_json(uno) == m.informe_json(dos) and m.informe_json(uno).endswith(b"\n")
    resumen = m.resumen_legible(uno)
    for fragmento in ("Auditoria AE-79 recalculada", "== Constancias", "Autorizacion operativa: DENEGADA",
                      "AUTORIZA_EVALUACION = False", "publicacion externa no_aportada"):
        assert fragmento in resumen, fragmento


def test_g1_cantidad_de_firmas_no_promueve_pendientes():
    m = _m()
    informe = _verificar(m, "s1", [fc.constancia("s1"), fc.constancia("s1", "y")])
    assert m.codigo_de_salida(informe) == 0
    planos = informe["pendientes"]["planos"]
    assert {p: v["estado"] for p, v in planos.items()} == {
        "publicacion_externa": "pendiente", "autoridad_del_conjunto_esperado": "pendiente",
        "completitud_global": "pendiente", "cronologia": "pendiente"}
    assert "cantidad_de_firmas_no_es_autoridad" in planos["autoridad_del_conjunto_esperado"]["motivos"]
    assert informe["autorizacion_operativa"] == {"estado": "denegada", "AUTORIZA_EVALUACION": False}
    assert informe["pendientes"]["decisiones_sin_tomar"] == list(ac.DECISIONES_ABIERTAS)
    assert set(informe["pendientes"]["decisiones_abiertas_ae80"]) == set(m.DECISIONES_ABIERTAS_AE80)


def test_g1_sin_claves_privadas_en_constancias_politicas_ni_informes():
    m = _m()
    constancias = [fc.constancia("s1"), fc.constancia("s1", "y")]
    informe = m.informe_json(_verificar(m, "s1", constancias))
    for archivos in (m.componer_constancias(constancias), fc.politica_de_constancias()):
        for datos in archivos.values():
            assert b"PRIVATE KEY" not in datos
            for privada in fc.claves_privadas():
                assert privada not in datos
    for privada in fc.claves_privadas():
        assert privada not in informe and privada.hex().encode() not in informe


def test_g1_codigos_limites_y_pureza():
    m = _m()
    assert dict(m.CODIGOS_DE_SALIDA) == {"constancia_y_auditoria_coincidentes": 0, "contradiccion_comprobada": 1,
                                         "uso_incorrecto": 2, "lectura_rechazada": 3, "constancia_no_coincide": 4,
                                         "sin_constancia_admitida": 5}
    assert all("autoriz" not in k for k in m.CODIGOS_DE_SALIDA)
    assert "no autoriza evaluacion" in m.SIGNIFICADO_DE_LOS_CODIGOS[0]
    texto = " ".join(m.LIMITES)
    for fragmento in ("no prueba que la clave pertenezca a una autoridad real", "publicacion fuera de banda",
                      "no prueban cronologia", "no se usa mayoria, quorum ni cantidad de firmas",
                      "nunca se acepta aportado", "no es una publicacion independiente",
                      "no heredan sus garantias", "AUTORIZA_EVALUACION es False"):
        assert fragmento in texto, fragmento
    assert set(m.CONTRADICCIONES).isdisjoint(m.NO_COINCIDENCIAS)
    assert set(m.LECTURAS_DE_ENTRADAS).isdisjoint(m.NO_COINCIDENCIAS)
    assert m.NATURALEZAS == ("fixture_de_prueba",)
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


# ===========================================================================
# G1: lector compartido de AE-76 ante constantes JSON no estandar
# (regresiones de AE-76, AE-79 y AE-80 incluidas en AE-80)
# ===========================================================================

LITERALES = [b"NaN", b"Infinity", b"-Infinity", b"1e999"]


def _con_literal(datos: bytes, literal: bytes) -> bytes:
    """Bytes con una constante no estandar, construidos sin pasar por el
    serializador canonico (que la rechazaria)."""
    assert datos.count(b'"secuencia":1,') == 1
    return datos.replace(b'"secuencia":1,', b'"secuencia":' + literal + b",")


def _captura_no_estandar(literal: bytes) -> ex.ObjetoFirmado:
    datos = _con_literal(fa.capturar(fa.e1(), "a").datos, literal)
    return ex.ObjetoFirmado(datos, fa.clave_privada("a").sign(datos), fa.clave_publica("a"))


@pytest.mark.parametrize("literal", LITERALES)
def test_g1_lector_de_ae76_y_captura_de_ae79_rechazan_constantes_no_estandar(literal):
    entradas, _ = fx.registro()
    acuse = fx.acuses(ex, entradas)[0]
    with pytest.raises(ex.ExpedienteInvalido) as error:
        ex.leer_acuse(_con_literal(acuse.datos, literal))
    assert error.value.motivo == "pieza_ilegible"
    with pytest.raises(ex.ExpedienteInvalido) as error:
        ac.leer_captura(_captura_no_estandar(literal).datos)
    assert error.value.motivo == "pieza_ilegible"


@pytest.mark.parametrize("literal", LITERALES)
def test_g1_auditoria_ae79_con_captura_firmada_no_estandar_da_evidencia_ilegible(literal):
    mala = _captura_no_estandar(literal)
    conjunto = ac.componer_capturas([*fc.capturas_s1(), mala])
    argumentos = {**fc.entradas("s1"), "capturas": [conjunto]}
    informes = [ac.auditar(expedientes=[("e", e) for e in argumentos["expedientes"]],
                           politica_del_verificador=argumentos["politica_del_verificador"],
                           politica_de_auditoria=argumentos["politica_de_auditoria"],
                           capturas=[("c", conjunto)]) for _ in range(2)]
    assert ac.informe_json(informes[0]) == ac.informe_json(informes[1])
    fila = next(c for c in informes[0]["capturas"] if c["id"] == ex.hash_de_pieza(mala.datos))
    assert fila["lectura"] == {"estado": "rechazada", "motivos": ["pieza_ilegible"]}
    assert fila["admitida_para_comparar"] is False and fila["estado"] == "no_coincide"
    assert informes[0]["resultado"] == "evidencia_no_coincide" and ac.codigo_de_salida(informes[0]) == 4


@pytest.mark.parametrize("literal", LITERALES)
def test_g1_recalculo_de_ae80_con_captura_no_estandar_no_coincide(literal):
    m = _m()
    conjunto = ac.componer_capturas([*fc.capturas_s1(), _captura_no_estandar(literal)])
    informe = _verificar(m, "s1", [fc.constancia("s1")], capturas=[conjunto])
    assert informe["informe_ae79"]["resultado"] == "evidencia_no_coincide"
    assert {"entrada_atestada_no_presentada", "entrada_presentada_no_atestada"} <= set(
        informe["constancias"][0]["cotejo"])
    assert informe["resultado"] == "constancia_no_coincide" and m.codigo_de_salida(informe) == 4


def test_g1_lectores_compartidos_sin_cambio_para_piezas_validas():
    """Las piezas validas de AE-76, AE-79 y AE-80 se leen igual: el
    resultado es el objeto JSON y sus bytes canonicos son los presentados."""
    m = _m()
    entradas, bd = fx.registro()
    acuses = fx.acuses(ex, entradas)
    sobre = fx.firmar(ex, ex.construir_sobre(entradas, bd, clave_publica=fx.clave_publica("firmante")), "firmante")
    piezas = [(ex.leer_acuse, acuses[0].datos), (ex.leer_sobre, sobre.datos),
              (ex.leer_cierre, fx.cierre(ex, entradas, acuses).datos),
              (ac.leer_captura, fa.capturar(fa.e1(), "a").datos), (m.leer_constancia, fc.constancia("s1").datos)]
    for lector, datos in piezas:
        pieza = lector(datos)
        assert pieza == json.loads(datos) and ex.bytes_canonicos(pieza) == datos
    with pytest.raises(ex.ExpedienteInvalido) as error:
        ex.leer_acuse(acuses[0].datos.replace(b"\n", b" \n"))
    assert error.value.motivo == "pieza_no_canonica"
    with pytest.raises(ex.ExpedienteInvalido) as error:
        ex.leer_acuse(acuses[0].datos.replace(ex.ESQUEMA_ACUSE.encode(), b"acuse-recepcion-prediccion/9"))
    assert error.value.motivo == "version_desconocida"


# ===========================================================================
# G1: lectores de AE-75, AE-77 y AE-78 ante constantes JSON no estandar
# ===========================================================================

def _primer_entero_a(datos: bytes, literal: bytes) -> bytes:
    """Sustituye el primer valor entero de un JSON canonico por `literal`,
    sin pasar por el serializador canonico."""
    import re
    nuevo = re.sub(rb'":(\d+)([,}])', b'":' + literal + rb"\2", datos, count=1)
    assert nuevo != datos
    return nuevo


def _reemplazar(archivos: dict, ruta: str, datos: bytes) -> dict:
    """Sustituye un archivo de un expediente y actualiza su entrada del
    manifiesto (tamano y SHA-256)."""
    copia = {**archivos, ruta: datos}
    manifiesto = json.loads(copia["manifiesto.json"])
    for entrada in manifiesto["archivos"]:
        if entrada["ruta"] == ruta:
            entrada.update(bytes=len(datos), sha256=hashlib.sha256(datos).hexdigest())
    copia["manifiesto.json"] = rp.serializar_entrada(manifiesto)
    return copia


@pytest.mark.parametrize("literal", LITERALES)
def test_g1_ae77_conjunto_esperado_y_compromiso_de_acuse_no_estandar(literal):
    from tests.unit.ml import fixtures_recepcion_por_objetivo as fo
    entradas, _ = fx.registro()
    datos = _primer_entero_a(fo.declaracion(ro, ex, entradas).datos, literal)
    with pytest.raises(ro.ConjuntoEsperadoInvalido) as error:
        ro.leer_conjunto_esperado(datos)
    assert error.value.motivo == "pieza_ilegible"
    firmada = ex.ObjetoFirmado(datos, fo.clave_privada("observador").sign(datos), fo.clave_publica("observador"))
    vistas = ro.verificar_vistas(entradas, [[firmada]], fo.politica_observadores(ro), fx.politica(ex))
    assert vistas.estado == "rechazada" and "pieza_ilegible" in vistas.motivos
    acuse = fx.acuses(ex, entradas)[0]
    evidencia = fo.sellar_acuse(ro, entradas, acuse)
    compromiso = _primer_entero_a(evidencia.bytes_compromiso, literal)
    with pytest.raises(ro.CompromisoDeAcuseInvalido) as error:
        ro.leer_compromiso_de_acuse(compromiso)
    assert error.value.motivo == "pieza_ilegible"
    informe = ro.verificar_tiempo_de_acuse(entradas, ro.EvidenciaDeSelloDeAcuse(acuse, evidencia.respuesta_der,
                                                                                compromiso),
                                           fo.politica_sello(), fx.politica(ex), canal=fx.CANAL)
    assert informe.estado == "rechazada" and "pieza_ilegible" in informe.motivos


@pytest.mark.parametrize("literal", LITERALES)
def test_g1_ae75_compromiso_no_estandar(literal):
    from tests.unit.ml import fixtures_recepcion_por_objetivo as fo
    entradas, bd = fx.registro()
    datos = st.bytes_de_compromiso(st.construir_compromiso(entradas, bd, codigo_juego="BALOTO", sorteo_objetivo=2714,
                                                           plazo_utc=fo.PLAZO))
    malo = datos.replace(b'"sorteo_objetivo":2714', b'"sorteo_objetivo":' + literal)
    assert malo != datos
    with pytest.raises(st.CompromisoInvalido) as error:
        st.leer_compromiso(malo)
    assert error.value.motivo == "compromiso_ilegible"
    archivos = fa.e1()
    evidencia = st.EvidenciaDeSello(archivos["sellos_r0/baloto-2714/respuesta.tsr"], malo)
    informe = st.verificar_sello(entradas, bd, evidencia, fo.politica_sello(), codigo_juego="BALOTO",
                                 sorteo_objetivo=2714)
    assert informe.vinculo_del_compromiso["compromiso_legible"].estado == "rechazada"
    assert informe.vinculo_del_compromiso["compromiso_legible"].motivos == ("compromiso_ilegible",)
    assert informe.estado_del_plano == "rechazada" and "compromiso_ilegible" in informe.motivos_del_plano


def test_g1_ae78_manifiesto_con_1e999_es_manifiesto_ilegible():
    """`parse_constant` ya rechazaba NaN e Infinity; 1e999 se convertia en
    infinito y escapaba al serializar el manifiesto."""
    for archivos, nombre, lector in ((fa.e1(), "manifiesto.json", ep.leer_expediente),
                                     (fa.politica_del_verificador(), "politica.json", ep.leer_politica)):
        malo = _primer_entero_a(archivos[nombre], b"1e999")
        with pytest.raises(ep.ExpedienteIlegible) as error:
            lector({**archivos, nombre: malo})
        assert error.value.motivo == "manifiesto_ilegible"
        for literal in (b"NaN", b"Infinity", b"-Infinity"):
            with pytest.raises(ep.ExpedienteIlegible) as error:
                lector({**archivos, nombre: _primer_entero_a(archivos[nombre], literal)})
            assert error.value.motivo == "manifiesto_ilegible"


def test_g1_lectores_de_ae75_ae77_y_ae78_sin_cambio_para_entradas_validas():
    from tests.unit.ml import fixtures_recepcion_por_objetivo as fo
    entradas, bd = fx.registro()
    compromiso = st.bytes_de_compromiso(st.construir_compromiso(entradas, bd, codigo_juego="BALOTO",
                                                                sorteo_objetivo=2714, plazo_utc=fo.PLAZO))
    declaracion = fo.declaracion(ro, ex, entradas).datos
    acuse = fo.sellar_acuse(ro, entradas, fx.acuses(ex, entradas)[0]).bytes_compromiso
    for lector, datos in ((st.leer_compromiso, compromiso), (ro.leer_conjunto_esperado, declaracion),
                          (ro.leer_compromiso_de_acuse, acuse)):
        pieza = lector(datos)
        assert pieza == json.loads(datos) and rp.serializar_entrada(pieza) == datos
    for lector, error_, datos, motivo in (
            (st.leer_compromiso, st.CompromisoInvalido, compromiso.replace(b"\n", b" \n"), "compromiso_no_canonico"),
            (st.leer_compromiso, st.CompromisoInvalido, compromiso.replace(st.ESQUEMA_COMPROMISO.encode(), b"x/9"),
             "version_de_compromiso_desconocida"),
            (ro.leer_conjunto_esperado, ro.ConjuntoEsperadoInvalido, declaracion.replace(b"\n", b" \n"),
             "pieza_no_canonica"),
            (ro.leer_conjunto_esperado, ro.ConjuntoEsperadoInvalido,
             declaracion.replace(ro.ESQUEMA_CONJUNTO.encode(), b"x/9"), "version_desconocida")):
        with pytest.raises(error_) as error:
            lector(datos)
        assert error.value.motivo == motivo
    archivos = fa.e1()
    leido = ep.leer_expediente(archivos)
    assert leido.sha256_manifiesto == hashlib.sha256(archivos["manifiesto.json"]).hexdigest()
    for contenido, motivo in ((archivos["manifiesto.json"].replace(b"\n", b" \n"), "manifiesto_no_canonico"),
                              (archivos["manifiesto.json"].replace(ep.ESQUEMA_EXPEDIENTE.encode(), b"x/9"),
                               "version_desconocida")):
        with pytest.raises(ep.ExpedienteIlegible) as error:
            ep.leer_expediente({**archivos, "manifiesto.json": contenido})
        assert error.value.motivo == motivo


# ===========================================================================
# G2: invariantes de AE-52 y AE-74 a AE-79 (pasan sobre la base)
# ===========================================================================

def test_g2_huellas_de_ae52_y_ae74_a_ae79():
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


def test_g2_estados_del_expediente_sin_cambios():
    assert pi.AUTORIZA_EVALUACION is False
    assert cv.DECISIONES_DEL_CONTRATO["D8"]["estado"] == "aprobada_solo_para_el_modelo_sintetico"
    assert cv.DECISIONES_DEL_CONTRATO["D9"]["estado"] == "espera_provisional_aprobada"
    assert all(v["estado"] == "sin_decidir" for v in ro.DECISIONES_OPERATIVAS_PENDIENTES.values())
    assert ac.DECISIONES_ABIERTAS == ("A1", "A2", "A3", "C1", "C2", "C3", "D8_operativa", "D9_definitiva")


# ===========================================================================
# G3: premisas sobre el codigo existente (pasan sobre la base)
# ===========================================================================

def test_g3_el_informe_ae79_depende_de_los_nombres_y_es_determinista_con_nombres_fijos():
    """Premisa de la normalizacion: el informe AE-79 incluye el nombre de
    los conjuntos de capturas (y de las entradas rechazadas), y con los
    mismos nombres y bytes es identico byte a byte."""
    entradas = fc.fa.e1(), fc.fa.e2()
    politicas = {"politica_del_verificador": fa.politica_del_verificador(),
                 "politica_de_auditoria": fa.politica_de_auditoria()}
    capturas = ac.componer_capturas([fa.capturar(fa.e1(), "a")])
    uno = ac.auditar(expedientes=[("a", entradas[0]), ("b", entradas[1])], capturas=[("c", capturas)], **politicas)
    dos = ac.auditar(expedientes=[("z", entradas[1]), ("y", entradas[0])], capturas=[("c", capturas)], **politicas)
    tres = ac.auditar(expedientes=[("a", entradas[0]), ("b", entradas[1])], capturas=[("otro", capturas)],
                      **politicas)
    assert ac.informe_json(uno) == ac.informe_json(dos)
    assert ac.informe_json(uno) != ac.informe_json(tres)


def test_g3_primitivas_reutilizadas():
    objeto = fx.firmar(ex, {"esquema": ex.ESQUEMA_ACUSE}, "canal")
    planos = ex._firma(objeto, None, fx.politica(ex), "canal")
    assert planos["integridad_de_la_firma"].estado == "superada"
    assert ac.es_huella("a" * 64) and not ac.es_huella("A" * 64)
    with pytest.raises(ep.ExpedienteIlegible) as error:
        ac._leer_manifiesto({"m.json": b"{}\n"}, "m.json", "x/1", ep.LIMITES_POR_DEFECTO)
    assert error.value.motivo == "version_desconocida"
