"""Tests de la Etapa AE-79, validada localmente como trabajo preparatorio:
auditoria cruzada de expedientes portables y capturas de observadores de
prueba.

G1  funcionalidad nueva, importada dentro de cada prueba (sobre la base falla
    con `ModuleNotFoundError`): formato de captura, conjuntos de capturas,
    politica de auditoria, firmas, cadenas y bifurcaciones, discrepancias
    entre firmantes, claves duplicadas con nombres distintos, alteracion
    coherente frente a una captura firmada, expediente ausente, lectura
    rechazada, procedencia, limites, orden determinista y no promocion de
    pendientes.
G2  invariantes de AE-52 y AE-74 a AE-78: huellas y estados.
G3  premisas sobre el codigo existente que la auditoria reutiliza.

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

from app.application.ml import contrato_vinculo_r0 as cv
from app.application.ml import expediente_portable as ep
from app.application.ml import expediente_r0_recepcion as ex
from app.application.ml import propuesta_inferencia_prospectiva as pi
from app.application.ml import recepcion_por_objetivo as ro
from app.application.ml import registro_prospectivo as rp
from app.application.ml import sello_temporal_r0 as st
from tests.unit.ml import fixtures_auditoria_cruzada as fa
from tests.unit.ml import fixtures_expediente_r0 as fx


def _m():
    return importlib.import_module("app.application.ml.auditoria_cruzada")


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


def _auditar(m, expedientes, capturas=(), *, politica=None, politica_auditoria=None, referencias=None,
             conjuntos=None):
    conjuntos = conjuntos if conjuntos is not None else ([("capturas", m.componer_capturas(list(capturas)))]
                                                         if capturas else [])
    return m.auditar(expedientes=[(f"e{i}", e) for i, e in enumerate(expedientes, start=1)],
                     politica_del_verificador=politica or fa.politica_del_verificador(),
                     politica_de_auditoria=politica_auditoria or fa.politica_de_auditoria(), capturas=conjuntos,
                     referencias=referencias or m.ReferenciasExternas())


def _captura(informe, objeto):
    return next(c for c in informe["capturas"] if c["id"] == fa.id_(objeto))


def _expediente(informe, archivos):
    return next(e for e in informe["expedientes"] if e.get("sha256_manifiesto") == fa.sha(archivos))


# ===========================================================================
# G1: formato de captura
# ===========================================================================

def test_g1_captura_vincula_manifiesto_politica_protocolo_canal_corte_y_posicion():
    m = _m()
    e2 = fa.e2()
    a1 = fa.capturar(fa.e1(), "a")
    a2 = fa.capturar(e2, "a", 2, a1)
    pieza = m.leer_captura(a2.datos)
    assert tuple(sorted(pieza)) == tuple(sorted(m.CLAVES_DE_LA_CAPTURA))
    assert a2.datos == ex.bytes_canonicos(pieza)
    leido = ep.leer_expediente(e2)
    entradas = list(leido.entradas)
    assert pieza["esquema"] == m.ESQUEMA_CAPTURA == "captura-observador-expediente/1"
    assert pieza["sha256_manifiesto"] == fa.sha(e2) == leido.sha256_manifiesto
    assert pieza["sha256_politica"] == fa.sha256_politica()
    assert pieza["protocolo_hash"] == rp.validar_registro(entradas).hash_protocolo
    assert (pieza["canal"], pieza["corte_sintetico"], pieza["alcance_de_corte"]) == (fx.CANAL, 2716, ["BALOTO"])
    assert (pieza["secuencia"], pieza["anterior"]) == (2, fa.id_(a1))
    assert pieza["objetivos_esperados"] == [["BALOTO", 2714], ["BALOTO", 2715], ["BALOTO", 2716]]
    assert [a[0] for a in pieza["acuses"]] == [ex.hash_de_pieza(a.datos) for a in leido.acuses]
    assert pieza["conjunto_esperado"] == ex.hash_de_pieza(leido.conjunto_esperado.datos)
    assert pieza["huella_de_clave"] == ex.huella_de_clave(fa.clave_publica("a"))
    assert {k: pieza[k] for k in m.CAMPOS_DEL_EXPEDIENTE} == m.resumen_del_expediente(leido)


@pytest.mark.parametrize("cambios, motivo", [
    ({"secuencia": 0}, "pieza_mal_formada"),
    ({"anterior": "0" * 64}, "pieza_mal_formada"),
    ({"sha256_manifiesto": "X" * 64}, "pieza_mal_formada"),
    ({"objetivos_esperados": [["BALOTO", 2715], ["BALOTO", 2714]]}, "pieza_mal_formada"),
    ({"objetivos_esperados": [["BALOTO", 2714], ["BALOTO", 2714]]}, "pieza_mal_formada"),
    ({"acuses": [["0" * 64, "BALOTO"]]}, "pieza_mal_formada"),
    ({"alcance_de_corte": []}, "pieza_mal_formada"),
    ({"extra": 1}, "pieza_ilegible"),
    ({"esquema": "captura-observador-expediente/2"}, "version_desconocida"),
])
def test_g1_lectura_estricta_de_la_captura(cambios, motivo):
    m = _m()
    pieza = m.leer_captura(fa.capturar(fa.e1(), "a").datos)
    pieza.update(cambios)
    with pytest.raises(ex.ExpedienteInvalido) as error:
        m.leer_captura(ex.bytes_canonicos(pieza))
    assert error.value.motivo == motivo
    with pytest.raises(ex.ExpedienteInvalido) as error:
        m.leer_captura(fa.capturar(fa.e1(), "a").datos.replace(b"\n", b" \n"))
    assert error.value.motivo == "pieza_no_canonica"


def test_g1_conjunto_de_capturas_y_politica_de_auditoria_con_lectura_endurecida():
    m = _m()
    capturas = [fa.capturar(fa.e1(), "a"), fa.capturar(fa.e2(), "b")]
    archivos = m.componer_capturas(capturas)
    assert m.leer_capturas(archivos) == tuple(capturas)
    manifiesto = json.loads(archivos["capturas.json"])
    assert manifiesto["esquema"] == m.ESQUEMA_CAPTURAS == "capturas-de-observador/1"
    for mutacion, motivo in ((lambda a: a.update({"capturas/001/extra.bin": b"x"}), "archivo_no_declarado"),
                             (lambda a: a.update({"capturas/001/firma.bin": b"0" * 64}), "sha256_incorrecto"),
                             (lambda a: a.pop("capturas/002/datos.json"), "archivo_faltante")):
        copia = dict(archivos)
        mutacion(copia)
        with pytest.raises(ep.ExpedienteIlegible) as error:
            m.leer_capturas(copia)
        assert error.value.motivo == motivo
    demasiadas = m.componer_capturas([capturas[0]] * (m.MAXIMO_DE_CAPTURAS + 1))
    with pytest.raises(ep.ExpedienteIlegible) as error:
        m.leer_capturas(demasiadas)
    assert error.value.motivo == "demasiadas_capturas"
    politica = m.leer_politica_de_auditoria(fa.politica_de_auditoria())
    assert politica.cortes_admitidos == (2715, 2716)
    assert [c.clave_publica for c in politica.capturadores] == [fa.clave_publica(n) for n in "abc"]
    cabecera = json.loads(fa.politica_de_auditoria()["politica_auditoria.json"])
    assert cabecera["esquema"] == m.ESQUEMA_POLITICA_AUDITORIA and cabecera["naturaleza"] == "fixture_de_prueba"
    otra = dict(cabecera, naturaleza="operativa")
    with pytest.raises(ep.ExpedienteIlegible) as error:
        m.leer_politica_de_auditoria({**fa.politica_de_auditoria(), "politica_auditoria.json":
                                      rp.serializar_entrada(otra)})
    assert error.value.motivo == "naturaleza_no_admitida"


def test_g1_misma_clave_con_dos_etiquetas_no_es_otro_firmante():
    m = _m()
    duplicada = fa.politica_de_auditoria(("a", "a"), etiquetas=["capturador uno", "capturador dos"])
    with pytest.raises(ep.ExpedienteIlegible) as error:
        m.leer_politica_de_auditoria(duplicada)
    assert error.value.motivo == "clave_duplicada"
    e1, e2 = fa.e1(), fa.e2()
    uno = fa.capturar(e1, "a", observador="nombre-uno")
    dos = fa.capturar(e2, "a", observador="nombre-dos")
    informe = _auditar(m, [e1, e2], [uno, dos])
    assert _captura(informe, uno)["firmante"] == _captura(informe, dos)["firmante"]
    assert "equivocacion_del_firmante" in informe["entre_expedientes"]["motivos"]
    assert informe["resultado"] == "contradiccion_comprobada" and m.codigo_de_salida(informe) == 1
    assert len(informe["politicas"]["de_auditoria"]["capturadores"]) == 3


# ===========================================================================
# G1: firmas y politica externa
# ===========================================================================

def test_g1_firmas_y_politica_externa_de_capturas():
    m = _m()
    e1, e2 = fa.e1(), fa.e2()
    ajena = fa.capturar(e1, "ajeno")
    buena = fa.capturar(e2, "b")
    pieza = m.leer_captura(buena.datos)
    alterada = ex.ObjetoFirmado(ex.bytes_canonicos(dict(pieza, corte_sintetico=2799)), buena.firma,
                                buena.clave_publica)
    del_canal = fa.firmar(dict(m.leer_captura(fa.capturar(e1, "a").datos),
                               huella_de_clave=ex.huella_de_clave(fx.clave_publica("canal"))), "canal")
    otra_politica = fa.capturar(e1, "c", sha256_politica="0" * 64)
    informe = _auditar(m, [e1, e2], [ajena, buena, alterada, del_canal, otra_politica],
                       politica_auditoria=fa.politica_de_auditoria(("a", "b", "c")))
    assert "clave_no_admitida" in _captura(informe, ajena)["motivos"]
    assert "firma_no_coincide" in _captura(informe, alterada)["motivos"]
    assert "clave_no_admitida" in _captura(informe, del_canal)["motivos"]
    assert "capturador_no_independiente_del_canal" in _captura(informe, del_canal)["motivos"]
    assert _captura(informe, otra_politica)["motivos"] == ["politica_distinta_de_la_capturada"]
    assert _captura(informe, buena)["estado"] == "coincide"
    assert informe["resultado"] == "evidencia_no_coincide" and m.codigo_de_salida(informe) == 4
    # Una firma no valida no entra en las comparaciones: la captura alterada
    # (corte 2799) no produce contradicciones.
    todas = [c for comp in informe["entre_expedientes"]["capturas"]["comparaciones"] for c in comp["capturas"]]
    assert fa.id_(alterada) not in todas and fa.id_(ajena) not in todas and fa.id_(otra_politica) not in todas
    admitidas = {c["id"] for c in informe["capturas"] if c["admitida_para_comparar"]}
    assert admitidas == {fa.id_(buena)}
    assert len(m.CRITERIO_DE_ADMISION) == 4
    # La politica de capturas la suministra quien audita: sin "b" admitido,
    # su captura deja de valer.
    sin_b = _auditar(m, [e1, e2], [buena], politica_auditoria=fa.politica_de_auditoria(("a", "c")))
    assert "clave_no_admitida" in _captura(sin_b, buena)["motivos"]


def test_g1_una_copia_con_firma_invalida_no_oculta_la_valida():
    m = _m()
    e1, e2 = fa.e1(), fa.e2()
    a1 = fa.capturar(e1, "a")
    a2 = fa.capturar(e2, "a", 2, a1)
    falsa = ex.ObjetoFirmado(a2.datos, bytes(64), a2.clave_publica)
    uno = _auditar(m, [e1, e2], [a1, falsa, a2])
    dos = _auditar(m, [e1, e2], [a2, a1, falsa])
    assert m.informe_json(uno) == m.informe_json(dos)
    assert uno["entre_expedientes"]["estado"] == "progresion_demostrable"
    filas = [c for c in uno["capturas"] if c["id"] == fa.id_(a2)]
    assert sorted(c["estado"] for c in filas) == ["coincide", "no_coincide"]
    assert m.codigo_de_salida(uno) == 4


def test_g1_captura_con_otra_politica_no_entra_en_la_comparacion_cruzada():
    """Regresion: una captura firmada con la politica del verificador
    equivocada queda como evidencia individual que no coincide y no provoca
    una equivocacion del firmante en la auditoria hecha con la correcta."""
    m = _m()
    e1, e2 = fa.e1(), fa.e2()
    buena = fa.capturar(e1, "a")
    otra = fa.capturar(e1, "a", sha256_politica="0" * 64)
    informe = _auditar(m, [e1, e2], [buena, otra])
    fila = _captura(informe, otra)
    assert fila["firma"]["estado"] == "superada"
    assert fila["motivos"] == ["politica_distinta_de_la_capturada"] and fila["estado"] == "no_coincide"
    assert fila["admitida_para_comparar"] is False and _captura(informe, buena)["admitida_para_comparar"] is True
    assert "equivocacion_del_firmante" not in informe["entre_expedientes"]["motivos"]
    assert informe["entre_expedientes"]["motivos"] == []
    todas = [c for comp in informe["entre_expedientes"]["capturas"]["comparaciones"] for c in comp["capturas"]]
    assert fa.id_(otra) not in todas
    assert informe["resultado"] == "evidencia_no_coincide" and m.codigo_de_salida(informe) == 4


def test_g1_captura_que_no_coincide_con_su_expediente_no_entra_en_la_comparacion():
    m = _m()
    e1, e2 = fa.e1(), fa.e2()
    buena = fa.capturar(e1, "a")
    falsa = fa.capturar(e2, "a", objetivos_esperados=[["BALOTO", 2714]])
    informe = _auditar(m, [e1, e2], [buena, falsa])
    fila = _captura(informe, falsa)
    assert fila["motivos"] == ["captura_no_coincide_con_el_expediente"] and fila["admitida_para_comparar"] is False
    assert informe["entre_expedientes"]["motivos"] == []
    assert m.codigo_de_salida(informe) == 4
    # Con su expediente sin presentar, la captura firmada con la politica
    # correcta si se admite: es una declaracion firmada que puede
    # contradecir a otras, y su comprobacion frente a los bytes queda
    # pendiente.
    ausente = _auditar(m, [e1, fa.e4()], [buena, fa.capturar(e2, "a")])
    assert "equivocacion_del_firmante" in ausente["entre_expedientes"]["motivos"]
    assert all(c["admitida_para_comparar"] for c in ausente["capturas"])


def test_g1_captura_de_un_expediente_presentado_pero_no_resumible_no_se_admite():
    m = _m()
    e1, e2 = fa.e1(), fa.e2()
    roto = dict(e2)
    roto["conjunto_esperado/datos.json"] = b"{}\n"
    manifiesto = json.loads(roto["manifiesto.json"])
    for entrada in manifiesto["archivos"]:
        if entrada["ruta"] == "conjunto_esperado/datos.json":
            entrada.update(bytes=3, sha256=hashlib.sha256(b"{}\n").hexdigest())
    roto["manifiesto.json"] = rp.serializar_entrada(manifiesto)
    pieza = m.leer_captura(fa.capturar(e2, "b").datos)
    captura = fa.firmar(dict(pieza, sha256_manifiesto=fa.sha(roto)), "b")
    informe = _auditar(m, [e1, roto], [fa.capturar(e1, "a"), captura])
    fila = _captura(informe, captura)
    assert fila["expediente"] == "presentado_no_resumible"
    assert fila["motivos"] == ["captura_no_verificable_frente_al_expediente"]
    assert fila["admitida_para_comparar"] is False
    assert _expediente(informe, roto)["resumible"] is False
    assert m.codigo_de_salida(informe) == 4


def test_g1_captura_que_no_coincide_con_el_expediente_referido():
    m = _m()
    e1, e2 = fa.e1(), fa.e2()
    falsa = fa.capturar(e2, "a", objetivos_esperados=[["BALOTO", 2714]])
    informe = _auditar(m, [e1, e2], [falsa])
    fila = _captura(informe, falsa)
    assert fila["motivos"] == ["captura_no_coincide_con_el_expediente"]
    assert fila["campos_que_no_coinciden"] == ["objetivos_esperados"]
    assert m.codigo_de_salida(informe) == 4


# ===========================================================================
# G1: cadenas, bifurcaciones y discrepancias
# ===========================================================================

def test_g1_progresion_demostrable_y_evolucion_legitima():
    m = _m()
    e1, e2 = fa.e1(), fa.e2()
    a1 = fa.capturar(e1, "a")
    b1 = fa.capturar(e2, "b")
    a2 = fa.capturar(e2, "a", 2, a1)
    compatibles = _auditar(m, [e1, e2], [a1, b1])
    assert compatibles["entre_expedientes"]["estado"] == "compatibles"
    assert compatibles["resultado"] == "sin_contradiccion_detectable" and m.codigo_de_salida(compatibles) == 0
    informe = _auditar(m, [e1, e2], [a1, b1, a2])
    assert informe["entre_expedientes"]["estado"] == "progresion_demostrable"
    assert informe["entre_expedientes"]["capturas"]["progresiones"] == [
        {"capturas": [fa.id_(a1), fa.id_(a2)], "firmante": ex.huella_de_clave(fa.clave_publica("a"))}]
    assert informe["entre_expedientes"]["motivos"] == []
    for fila in informe["expedientes"]:
        assert fila["ae78"]["resultado"] == "sin_rechazos"
    assert _expediente(informe, e1)["corte_esperado"] == {
        "valor": 2715, "origen": "cortes_admitidos_de_la_politica_de_auditoria"}


def test_g1_cadenas_rotas_bifurcaciones_y_anterior_no_presentado():
    m = _m()
    e1, e2, e3 = fa.e1(), fa.e2(), fa.e3()
    a1 = fa.capturar(e1, "a")
    otra = fa.capturar(e3, "b")
    roto = fa.capturar(e2, "a", 2, otra)
    informe = _auditar(m, [e1, e2], [a1, roto])
    assert "vinculo_roto" in informe["entre_expedientes"]["motivos"]
    rama_1 = fa.capturar(e2, "a", 2, a1)
    rama_2 = fa.capturar(e3, "a", 2, a1)
    informe = _auditar(m, [e1, e2, e3], [a1, rama_1, rama_2])
    assert "equivocacion_del_firmante" in informe["entre_expedientes"]["motivos"]
    solo = _auditar(m, [e1, e2], [rama_1])
    assert solo["entre_expedientes"]["capturas"]["pendientes"] == [
        {"captura": fa.id_(rama_1), "motivo": "anterior_no_presentado"}]
    assert solo["resultado"] == "sin_contradiccion_detectable"


def test_g1_retirada_retroceso_y_reescritura_del_mismo_firmante():
    m = _m()
    e1, e2 = fa.e1(), fa.e2()
    a1 = fa.capturar(e2, "a")
    a2 = fa.capturar(e1, "a", 2, a1)
    informe = _auditar(m, [e1, e2], [a1, a2])
    motivos = informe["entre_expedientes"]["motivos"]
    assert {"corte_retrocede", "objetivo_retirado", "historia_reescrita"} <= set(motivos)
    # Con el corte retrocediendo no se afirma ademas una omision: el
    # retroceso ya es la contradiccion comprobada.
    assert "omision_comprobable" not in motivos
    assert m.codigo_de_salida(informe) == 1
    assert all(f["ae78"]["resultado"] == "sin_rechazos" for f in informe["expedientes"])


def test_g1_discrepancia_entre_firmantes_sin_adjudicar():
    m = _m()
    e2, e3 = fa.e2(), fa.e3()
    b1 = fa.capturar(e2, "b")
    c1 = fa.capturar(e3, "c")
    informe = _auditar(m, [e2, e3], [b1, c1])
    comparacion = next(c for c in informe["entre_expedientes"]["capturas"]["comparaciones"]
                       if c["tipo"] == "firmantes_distintos")
    assert {"discrepancia_entre_firmantes", "omision_comprobable"} <= set(comparacion["motivos"])
    assert _captura(informe, b1)["estado"] == _captura(informe, c1)["estado"] == "coincide"
    assert "verdad" not in json.dumps(informe) and "adjudic" not in json.dumps(informe["capturas"])
    assert informe["resultado"] == "contradiccion_comprobada"


def test_g1_contradicciones_entre_expedientes_sin_capturas():
    m = _m()
    e2, e3 = fa.e2(), fa.e3()
    informe = _auditar(m, [e2, e3])
    assert all(f["ae78"]["resultado"] == "sin_rechazos" for f in informe["expedientes"])
    hallazgos = informe["entre_expedientes"]["por_posicion"]["hallazgos"]
    assert {h["motivo"] for h in hallazgos} == {"acuses_contradictorios_del_canal",
                                                "declaraciones_contradictorias_del_observador"}
    acuses = next(h for h in hallazgos if h["motivo"] == "acuses_contradictorios_del_canal")
    assert acuses["secuencia"] == 2 and len(acuses["contenidos"]) == 2
    assert informe["resultado"] == "contradiccion_comprobada"
    assert _auditar(m, [fa.e1(), e2])["entre_expedientes"]["por_posicion"]["hallazgos"] == []


def test_g1_alcances_distintos_son_incomparables_no_contradiccion():
    m = _m()
    e1, e4 = fa.e1(), fa.e4()
    informe = _auditar(m, [e1, e4], [fa.capturar(e1, "a"), fa.capturar(e4, "c")])
    assert informe["entre_expedientes"]["estado"] == "incomparables"
    assert informe["entre_expedientes"]["capturas"]["incomparables"][0]["motivos"] == [
        "protocolo_distinto_sin_base_comun"]
    assert informe["resultado"] == "sin_contradiccion_detectable"
    cambio = _auditar(m, [e1, e4], [fa.capturar(e1, "a"), fa.capturar(e4, "a", 2, fa.capturar(e1, "a"))])
    assert "cadena_cambia_de_alcance" in cambio["entre_expedientes"]["motivos"]


# ===========================================================================
# G1: alteracion coherente, expediente ausente y lectura rechazada
# ===========================================================================

def test_g1_alteracion_coherente_de_archivo_y_manifiesto_frente_a_captura_firmada():
    m = _m()
    e1, e2, sustituto = fa.e1(), fa.e2(), fa.e2_sin_un_sello()
    assert fa.sha(sustituto) != fa.sha(e2)
    solo = ep.evaluar(ep.leer_expediente(sustituto), ep.leer_politica(fa.politica_del_verificador()))
    assert solo["resultado_de_la_auditoria"] == "sin_rechazos"
    b1 = fa.capturar(e2, "b")
    informe = _auditar(m, [e1, sustituto], [fa.capturar(e1, "a"), b1])
    fila = _captura(informe, b1)
    assert fila["expediente"] == "manifiesto_distinto_del_capturado"
    assert "manifiesto_distinto_del_capturado" in fila["motivos"]
    assert _expediente(informe, sustituto)["capturado"] is False
    assert informe["resultado"] == "evidencia_no_coincide" and m.codigo_de_salida(informe) == 4


def test_g1_expediente_de_la_captura_no_presentado():
    m = _m()
    e1, e2, e4 = fa.e1(), fa.e2(), fa.e4()
    b1 = fa.capturar(e2, "b")
    informe = _auditar(m, [e1, e4], [b1])
    assert _captura(informe, b1)["expediente"] == "no_presentado"
    assert "expediente_de_la_captura_no_presentado" in _captura(informe, b1)["motivos"]
    assert informe["resultado"] == "sin_contradiccion_detectable"
    con_huella = _auditar(m, [e1, e4], [b1], referencias=m.ReferenciasExternas(manifiestos=frozenset({fa.sha(e2)})))
    comprobacion = con_huella["procedencia"]["comprobaciones"][0]
    assert comprobacion == {"objeto": "manifiesto", "huella": fa.sha(e2), "estado": "no_coincide",
                            "motivos": ["manifiesto_esperado_no_presentado"]}
    assert m.codigo_de_salida(con_huella) == 4


def test_g1_lectura_rechazada_no_inventa_planos():
    m = _m()
    e1, e2 = fa.e1(), fa.e2()
    roto = {**e2, "manifiesto.json": b"[]\n"}
    informe = _auditar(m, [e1, roto], [fa.capturar(e1, "a")])
    rechazado = next(f for f in informe["expedientes"] if f["lectura"]["estado"] == "rechazada")
    assert rechazado == {"nombre": "e2", "lectura": {"estado": "rechazada", "motivos": ["manifiesto_ilegible"]}}
    assert _expediente(informe, e1)["ae78"]["r0_final"]["estado"] == "rechazada"
    assert informe["resultado"] == "lectura_rechazada" and m.codigo_de_salida(informe) == 3
    ilegible = ep.ExpedienteIlegible("enlace_simbolico")
    con_error = _auditar(m, [e1, ilegible], conjuntos=[("capturas", ep.ExpedienteIlegible("directorio_invalido"))])
    assert {f.get("nombre") for f in con_error["expedientes"]} >= {"e2"}
    assert con_error["conjuntos_de_capturas"][0]["lectura"]["motivos"] == ["directorio_invalido"]
    # Una contradiccion comprobada entre las entradas legibles tiene
    # prioridad sobre la lectura rechazada de otra.
    prioridad = _auditar(m, [fa.e2(), fa.e3(), roto])
    assert prioridad["resultado"] == "contradiccion_comprobada"


def test_g1_politica_ilegible_detiene_la_auditoria():
    m = _m()
    e1, e2 = fa.e1(), fa.e2()
    politica = {**fa.politica_del_verificador(), "politica.json": b"{}\n"}
    informe = _auditar(m, [e1, e2], politica=politica)
    assert informe["lectura"] == {"estado": "rechazada", "objeto": "politica_del_verificador",
                                  "motivos": ["version_desconocida"]}
    assert informe["expedientes"] == [] and informe["capturas"] == []
    assert informe["resultado"] == "lectura_rechazada" and m.codigo_de_salida(informe) == 3
    assert "r0_final" not in m.informe_json(informe).decode("utf-8")
    auditoria = _auditar(m, [e1, e2], politica_auditoria={**fa.politica_de_auditoria(),
                                                          "politica_auditoria.json": b"[]\n"})
    assert auditoria["lectura"]["objeto"] == "politica_de_auditoria"


def test_g1_limites_de_entradas():
    m = _m()
    e1 = fa.e1()
    for n in (1, m.MAXIMO_DE_EXPEDIENTES + 1):
        with pytest.raises(ValueError, match="numero_de_expedientes"):
            _auditar(m, [e1] * n)
    with pytest.raises(ValueError, match="conjuntos_de_capturas"):
        _auditar(m, [e1, e1], conjuntos=[(str(i), {}) for i in range(m.MAXIMO_DE_CONJUNTOS_DE_CAPTURAS + 1)])
    assert (m.MINIMO_DE_EXPEDIENTES, m.MAXIMO_DE_EXPEDIENTES, m.MAXIMO_DE_CAPTURAS) == (2, 8, 64)
    assert m.BYTES_AGREGADOS == 64 << 20 and m.ARCHIVOS_AGREGADOS == 4096
    repetido = _auditar(m, [e1, e1])
    assert repetido["expedientes"][0]["presentado_mas_de_una_vez"] is True and len(repetido["expedientes"]) == 1


def test_g1_cortes_admitidos_los_decide_quien_audita():
    m = _m()
    e1, e2 = fa.e1(), fa.e2()
    informe = _auditar(m, [e1, e2], politica_auditoria=fa.politica_de_auditoria(cortes=(2716,)))
    fila = _expediente(informe, e1)
    assert fila["corte_esperado"] == {"valor": 2716, "origen": "politica_del_verificador"}
    assert fila["ae78"]["resultado"] == "con_rechazos"
    assert "corte_distinto_del_esperado" in fila["ae78"]["planos"][
        "completitud_respecto_del_manifiesto_presentado"]["motivos"]
    assert m.codigo_de_salida(informe) == 4


# ===========================================================================
# G1: procedencia, cabezas y pendientes
# ===========================================================================

def test_g1_procedencia_aportada_y_faltante():
    m = _m()
    e1, e2 = fa.e1(), fa.e2()
    a1 = fa.capturar(e1, "a")
    a2 = fa.capturar(e2, "a", 2, a1)
    sin = _auditar(m, [e1, e2], [a1, a2])
    assert set(sin["procedencia"]["faltan"]) == {"politica_del_verificador", "politica_de_auditoria",
                                                 "manifiestos", "capturas"}
    assert sin["procedencia"]["cabezas"][0]["estado"] == "cabeza_sin_referencia_externa"
    assert "publicacion independiente" in sin["procedencia"]["limite"]
    referencias = m.ReferenciasExternas(
        politica_del_verificador=fa.sha256_politica(),
        politica_de_auditoria=hashlib.sha256(fa.politica_de_auditoria()["politica_auditoria.json"]).hexdigest(),
        manifiestos=frozenset({fa.sha(e1), fa.sha(e2)}), capturas=frozenset({fa.id_(a2)}))
    con = _auditar(m, [e1, e2], [a1, a2], referencias=referencias)
    assert con["procedencia"]["faltan"] == []
    assert all(c["estado"] == "coincide" for c in con["procedencia"]["comprobaciones"])
    assert con["procedencia"]["cabezas"][0]["estado"] == "coincide_con_referencia_aportada"
    assert m.codigo_de_salida(con) == 0
    mala = _auditar(m, [e1, e2], [a1], referencias=m.ReferenciasExternas(politica_del_verificador="0" * 64))
    assert mala["procedencia"]["comprobaciones"][0]["motivos"] == ["huella_de_politica_no_coincide"]
    assert m.codigo_de_salida(mala) == 4
    with pytest.raises(ValueError):
        m.ReferenciasExternas(manifiestos=frozenset({"no-es-una-huella"}))


def test_g1_la_coincidencia_de_todos_los_firmantes_no_promueve_pendientes():
    m = _m()
    e1, e2 = fa.e1(), fa.e2()
    todos = [fa.capturar(e2, n) for n in "abc"]
    informe = _auditar(m, [e1, e2], todos)
    assert informe["resultado"] == "sin_contradiccion_detectable"
    planos = informe["pendientes"]["planos"]
    assert {p: v["estado"] for p, v in planos.items()} == {
        "autoridad_del_manifiesto": "pendiente", "completitud_global": "pendiente",
        "completitud_respecto_de_lo_que_debio_existir": "pendiente"}
    assert "coincidencia_de_firmantes_no_es_autoridad" in planos["completitud_global"]["motivos"]
    assert informe["pendientes"]["decisiones_sin_tomar"] == ["A1", "A2", "A3", "C1", "C2", "C3", "D8_operativa",
                                                             "D9_definitiva"]
    assert informe["autorizacion_operativa"] == {"estado": "denegada", "AUTORIZA_EVALUACION": False}
    for fila in informe["expedientes"]:
        assert fila["ae78"]["r0_final"]["estado"] == "rechazada"
        assert fila["ae78"]["planos"]["completitud_global"]["estado"] == "pendiente"
    texto = json.dumps(informe)
    assert "quorum" not in texto.replace("ni quorum", "") and "mayoria" not in texto.replace("mayoria ni", "")


# ===========================================================================
# G1: determinismo, material privado, codigos y pureza
# ===========================================================================

def test_g1_informe_determinista_e_independiente_del_orden():
    m = _m()
    e1, e2, e3 = fa.e1(), fa.e2(), fa.e3()
    capturas = [fa.capturar(e1, "a"), fa.capturar(e2, "b"), fa.capturar(e3, "c")]
    uno = m.informe_json(_auditar(m, [e1, e2, e3], capturas))
    otro = m.auditar(expedientes=[("x", e3), ("y", e1), ("z", e2)],
                     politica_del_verificador=fa.politica_del_verificador(),
                     politica_de_auditoria=fa.politica_de_auditoria(),
                     capturas=[("capturas", m.componer_capturas(capturas[::-1]))])
    assert m.informe_json(otro) == uno
    assert uno.endswith(b"\n") and json.loads(uno)["esquema"] == "informe-auditoria-cruzada/1"
    resumen = m.resumen_legible(json.loads(uno))
    for fragmento in ("== Expedientes", "== Capturas", "== Entre expedientes: contradiccion_comprobada",
                      "== Procedencia", "Autorizacion operativa: DENEGADA", "AUTORIZA_EVALUACION = False"):
        assert fragmento in resumen, fragmento


def test_g1_sin_claves_privadas_en_capturas_politicas_ni_informes():
    m = _m()
    e1, e2 = fa.e1(), fa.e2()
    capturas = [fa.capturar(e1, "a"), fa.capturar(e2, "b")]
    informe = m.informe_json(_auditar(m, [e1, e2], capturas))
    for archivos in (m.componer_capturas(capturas), fa.politica_de_auditoria(), e1, e2):
        for datos in archivos.values():
            for privada in fa.claves_privadas():
                assert privada not in datos
            assert b"PRIVATE KEY" not in datos
    for privada in fa.claves_privadas():
        assert privada.hex() not in informe.decode("utf-8") and privada not in informe
    material = ex.ObjetoFirmado(b"-----BEGIN PRIVATE KEY-----\n", b"x", b"y")
    with pytest.raises(ValueError):
        m.componer_capturas([material])


def test_g1_codigos_limites_y_pureza():
    m = _m()
    assert dict(m.CODIGOS_DE_SALIDA) == {"sin_contradiccion_detectable": 0, "contradiccion_comprobada": 1,
                                         "uso_incorrecto": 2, "lectura_rechazada": 3, "evidencia_no_coincide": 4}
    assert "no autoriza evaluacion" in m.SIGNIFICADO_DE_LOS_CODIGOS[0]
    assert "no adjudica" in m.SIGNIFICADO_DE_LOS_CODIGOS[1]
    texto = " ".join(m.LIMITES)
    for fragmento in ("no acredita fecha de publicacion", "no se usa mayoria ni quorum",
                      "una etiqueta distinta con la misma clave no es otro firmante",
                      "no puede llamarse ultima sin una referencia externa",
                      "no es una publicacion independiente", "AUTORIZA_EVALUACION es False"):
        assert fragmento in texto, fragmento
    assert "9162" not in texto
    assert set(m.CONTRADICCIONES).isdisjoint(m.NO_COINCIDENCIAS)
    assert m.CAPTURADORES_OPERATIVOS_ADMITIDOS == () and m.NATURALEZAS_DE_CAPTURADOR == ("fixture_de_prueba",)
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


def test_g1_premisa_corregida_de_ae78_marcas_privadas_tambien_en_el_manifiesto():
    """AE-78 documentaba que compositor y lector rechazan las marcas
    `PRIVATE KEY`, pero solo miraban los archivos declarados: una etiqueta
    del manifiesto de la politica podia llevarlas. Sobre la base esta prueba
    falla; AE-79 extiende la comprobacion al propio manifiesto."""
    marca = "-----BEGIN PRIVATE KEY----- sintetico -----END PRIVATE KEY-----"
    with pytest.raises(ValueError):
        ep.componer_politica(anclas=[], politicas_admitidas=[], margen="0",
                             claves=[(fx.clave_publica("canal"), "canal", marca)], observadores=[], canal=fx.CANAL,
                             corte_esperado=2716)
    limpia = fa.politica_del_verificador()
    cabecera = json.loads(limpia["politica.json"])
    cabecera["claves"][0]["etiqueta"] = marca
    with pytest.raises(ep.ExpedienteIlegible) as error:
        ep.leer_politica({**limpia, "politica.json": rp.serializar_entrada(cabecera)})
    assert error.value.motivo == "material_privado_detectado"
    assert ep.leer_politica(limpia).canal == fx.CANAL


# ===========================================================================
# G2: invariantes de AE-52 y AE-74 a AE-78 (pasan sobre la base)
# ===========================================================================

def test_g2_huellas_de_ae52_y_ae74_a_ae78():
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


def test_g2_estados_del_expediente_sin_cambios():
    assert pi.AUTORIZA_EVALUACION is False
    assert cv.DECISIONES_DEL_CONTRATO["D8"]["estado"] == "aprobada_solo_para_el_modelo_sintetico"
    assert cv.DECISIONES_DEL_CONTRATO["D9"]["estado"] == "espera_provisional_aprobada"
    assert all(v["estado"] == "sin_decidir" for v in ro.DECISIONES_OPERATIVAS_PENDIENTES.values())
    assert sorted(ro.DECISIONES_OPERATIVAS_PENDIENTES) == ["A1", "A2", "A3", "C1", "C2", "C3"]


# ===========================================================================
# G3: premisas sobre el codigo existente (pasan sobre la base)
# ===========================================================================

def test_g3_las_historias_sinteticas_comparten_prefijo_de_bytes():
    """La evolucion legitima de la demostracion descansa en que el registro,
    los acuses y la vista de una historia mas corta son prefijo de los de la
    historia mas larga del mismo protocolo."""
    corto, bd_corto = fx.registro((2714, 2715))
    largo, bd_largo = fx.registro((2714, 2715, 2716))
    divergente, _ = fx.registro((2714, 2716))
    assert largo[:3] == corto and bd_corto == bd_largo
    assert divergente[:2] == largo[:2] and divergente[2] != largo[2]
    assert [a.datos for a in fx.acuses(ex, corto, (2714, 2715))] == [
        a.datos for a in fx.acuses(ex, largo, (2714, 2715, 2716))][:2]


def test_g3_primitivas_de_firma_y_lectura_reutilizadas():
    pieza = {"esquema": ex.ESQUEMA_ACUSE}
    objeto = fx.firmar(ex, pieza, "canal")
    planos = ex._firma(objeto, None, fx.politica(ex), "canal")
    assert planos["integridad_de_la_firma"].estado == "superada"
    assert planos["clave_admitida_de_prueba"].estado == "superada"
    assert planos["huella_declarada"].estado == "no_evaluable"
    assert ex._firma(objeto, None, fx.politica(ex), "firmante_r0")["clave_admitida_de_prueba"].estado == "rechazada"
    with pytest.raises(ValueError):
        ep._con_manifiesto("m.json", {}, {"a/b.bin": b"-----BEGIN PRIVATE KEY-----"})
    with pytest.raises(ep.ExpedienteIlegible) as error:
        ep._leer_json_canonico(b'{"a":1,"a":2}\n')
    assert error.value.motivo == "manifiesto_ilegible"
