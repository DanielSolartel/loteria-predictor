"""Tests de la Etapa AE-71, validada: comparacion verificable de las
alternativas de declaracion previa R0 y de la distincion entre «sin fijar»,
«ausente» y «fijado».

Tres grupos:

G1  dependen del modulo nuevo, que se importa dentro de cada prueba; sobre
    la base cada una falla por separado con `ModuleNotFoundError`.
G2  invariantes sobre codigo existente (huellas de AE-52 y AE-63 a AE-70,
    estados y bloqueos); pasan sobre la base.
G3  integraciones contra la API publica real de AE-52, AE-69 y AE-70 (C1 a
    C6 y la premisa de C15); pasan sobre la base.

Se separan la dependencia entre bytes, una evidencia temporal sobre esos
bytes y la fijacion autenticada de R0: ni S5 ni un hash son prueba temporal.
El segundo manifiesto es solo un contraejemplo de un modelo sintetico, sin
formato ni garantia operativa. Nada se elige: D1-D9 siguen sin decidir, y
R0, R9, las ocho condiciones, las tres preguntas de AE-69 y las dos
elecciones de AE-70 no cambian. Todo sintetico: sin red, relojes o servicios
reales, datos reales, PostgreSQL ni predicciones reales."""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import importlib
import json
import re
from collections.abc import Mapping
from pathlib import Path

import pytest

from app.application.ml import auditoria_obligaciones_de_aplicacion as ao
from app.application.ml import diseno_regla_prospectiva as dr
from app.application.ml import especificacion_condiciones_del_protocolo as ec
from app.application.ml import inventario_declaracion_previa_del_protocolo as iv
from app.application.ml import propuesta_evidencia_temporal_externa as pe
from app.application.ml import propuesta_inferencia_prospectiva as pi
from app.application.ml import registro_prospectivo as rp
from app.application.ml import traslado_condiciones_inferenciales as tc
from app.application.ml import verificacion_primaria_choe_ramdas as vp
from app.application.ml import verificacion_primaria_rfc_sellado_y_transparencia as vr
from app.application.ml import vinculo_declaracion_previa_con_protocolo as vv
from app.application.ml.especificacion_evaluacion_prospectiva import ESPECIFICACION_CANDIDATA_AE53
from tests.unit.simulaciones import sinteticos

BASE = "@8137f93"
PROBABILIDADES = [0.1] * 43
"""Salida fabricada: solo prueba el formato, nunca es una prediccion."""
CAMPO = ("estrategia", "parametros", "clave_de_prueba")
"""Ruta de prueba: no es una eleccion."""
TOPOLOGIAS = tuple(vv.TOPOLOGIAS_DE_VINCULO)
DIRECTAS = ("directo_en_nuevo_esquema", "directo_en_campo_existente_no_previsto")
ELEMENTOS = tuple(iv.ELEMENTOS_DE_R0)


def _modulo():
    return importlib.import_module("app.application.ml.analisis_alternativas_de_declaracion_previa")


def _estrategia(parametros=None):
    return {
        "nombre": "estrategia_sintetica", "descripcion": "estrategia sintetica solo para pruebas",
        "huella_codigo": "a" * 64, "archivos_codigo": ["sintetico.py"],
        "parametros": parametros if parametros is not None else {"semilla": 1},
        "entorno": {"python": "3.x", "scikit_learn": "0.0"},
    }


def _protocolo(parametros=None):
    return rp.construir_protocolo(protocolo_id="sintetico-ae71", estrategia=_estrategia(parametros),
                                  cortes={"BALOTO": 2713, "BALOTO_REVANCHA": 2713}, pendientes=[], sintetico=True)


def _con_hash(h):
    return _protocolo({"semilla": 1, "clave_de_prueba": h})


def _declaracion(valor="valor-de-prueba", pendiente=None):
    """Declaracion sintetica de AE-69; los valores son datos de prueba."""
    d = {e: {"estado": "declarado_sintetico", "valor": {"sintetico": f"{valor}-{i}"}} for i, e in enumerate(ELEMENTOS)}
    if pendiente:
        d[pendiente] = {"estado": "pendiente"}
    return d


def _segundo_protocolo(bytes_primero, protocolo):
    segundo = {**protocolo, "secuencia": 2, "hash_anterior": rp.hash_entrada(bytes_primero)}
    return rp.serializar_entrada(segundo)


def _plano(valor):
    if dataclasses.is_dataclass(valor):
        return {f.name: _plano(getattr(valor, f.name)) for f in dataclasses.fields(valor)}
    if isinstance(valor, Mapping):
        return {str(k): _plano(v) for k, v in valor.items()}
    if isinstance(valor, (tuple, list)):
        return [_plano(v) for v in valor]
    return valor


def _huella(valor):
    return hashlib.sha256(json.dumps(_plano(valor), sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


# ===========================================================================
# G1: dependen del modulo nuevo (fallan sobre la base con ModuleNotFoundError)
# ===========================================================================

def test_g1_fichas_decisiones_y_dependencias_completas():
    m = _modulo()
    assert tuple(m.FICHAS_POR_TOPOLOGIA) == TOPOLOGIAS
    campos = ("datos_a_fijar_antes_del_plazo", "bytes_verificados", "cambios_de_esquema_y_pruebas",
              "comprobable_por_un_tercero", "no_demostrado", "dependencia_de_bytes", "identificacion_de_la_regla",
              "consecuencia_de_cambiar_la_declaracion", "decisiones_del_operador")
    assert tuple(f.name for f in dataclasses.fields(m.FichaDeTopologia)) == ("topologia", *campos)
    assert tuple(m.DECISIONES_DEL_OPERADOR_AE71) == tuple(f"D{i}" for i in range(1, 10))
    assert {d["estado"] for d in m.DECISIONES_DEL_OPERADOR_AE71.values()} == {"sin_decidir"}
    for t, ficha in m.FICHAS_POR_TOPOLOGIA.items():
        assert ficha.topologia == t
        for campo in campos:
            assert getattr(ficha, campo), (t, campo)
        assert set(ficha.decisiones_del_operador) <= set(m.DECISIONES_DEL_OPERADOR_AE71), t
        assert set(m.DEPENDENCIAS_QUE_IMPIDEN_IMPLEMENTAR[t]) <= set(m.DECISIONES_DEL_OPERADOR_AE71), t
        assert {"D1", "D2", "D7"} <= set(m.DEPENDENCIAS_QUE_IMPIDEN_IMPLEMENTAR[t]), t
    assert "D3" in m.DEPENDENCIAS_QUE_IMPIDEN_IMPLEMENTAR["directo_en_campo_existente_no_previsto"]
    assert "D4" in m.DEPENDENCIAS_QUE_IMPIDEN_IMPLEMENTAR["directo_en_nuevo_esquema"]
    assert "D5" in m.DEPENDENCIAS_QUE_IMPIDEN_IMPLEMENTAR["inverso_desde_la_declaracion"]
    assert "D6" in m.DEPENDENCIAS_QUE_IMPIDEN_IMPLEMENTAR["manifiesto_externo"]
    assert vv.TOPOLOGIA_ELEGIDA is None and vv.REPRESENTACION_ELEGIDA is None
    assert not any(n.endswith("_ELEGIDA") for n in vars(m))


def test_g1_no_demostrado_incluye_cronologia_autenticacion_y_suficiencia():
    m = _modulo()
    for t, ficha in m.FICHAS_POR_TOPOLOGIA.items():
        texto = " ".join(ficha.no_demostrado)
        for palabra in ("cronologia", "autenticacion", "suficiencia"):
            assert palabra in texto, (t, palabra)
    inverso = " ".join(m.FICHAS_POR_TOPOLOGIA["inverso_desde_la_declaracion"].no_demostrado)
    assert "despues de las predicciones" in inverso and "designacion unica" in inverso
    assert "ambiguedad de la regla" in " ".join(
        m.FICHAS_POR_TOPOLOGIA["directo_en_campo_existente_no_previsto"].no_demostrado)


def test_g1_dependencia_de_bytes_acotada_y_sin_cronologia():
    m = _modulo()
    esperadas = {
        "directo_en_nuevo_esquema": {"protocolo_depende_de_declaracion", "prediccion_depende_de_protocolo"},
        "directo_en_campo_existente_no_previsto": {"protocolo_depende_de_declaracion",
                                                   "prediccion_depende_de_protocolo"},
        "inverso_desde_la_declaracion": {"declaracion_depende_de_protocolo", "protocolo_no_depende_de_declaracion",
                                         "prediccion_depende_de_protocolo"},
        "manifiesto_externo": {"manifiesto_depende_de_ambos", "protocolo_no_depende_de_declaracion",
                               "prediccion_depende_de_protocolo"},
    }
    for t in TOPOLOGIAS:
        r = m.dependencia_de_bytes(t)
        assert r[-1] == m.MARCA_SIN_CRONOLOGIA == "sin_cronologia_acreditada", t
        assert set(r[:-1]) == esperadas[t] and set(r[:-1]) <= set(m.RELACIONES_DE_BYTES), t
        assert r == m.FICHAS_POR_TOPOLOGIA[t].dependencia_de_bytes, t
    for rel in (*m.RELACIONES_DE_BYTES, m.MARCA_SIN_CRONOLOGIA):
        assert not re.search(r"anterior|antes|precede", rel), rel
        assert "cronologia_acreditada" not in rel or rel.startswith("sin_"), rel
    with pytest.raises(KeyError):
        m.dependencia_de_bytes("topologia_inventada")


def test_g1_s5_e_hipotesis_para_cronologia_pendientes():
    m = _modulo()
    assert tuple(m.SUPUESTOS_ADICIONALES_AE71) == ("S5",)
    s5 = m.SUPUESTOS_ADICIONALES_AE71["S5"]
    assert s5["estado"] == "supuesto_no_verificado" and "no es prueba temporal" in s5["texto"]
    assert tuple(vv.SUPUESTOS_DEL_MODELO) == ("S1", "S2", "S3", "S4")
    assert tuple(m.HIPOTESIS_PARA_CRONOLOGIA) == ("H-a", "H-b", "H-c", "H-d")
    assert {h["estado"] for h in m.HIPOTESIS_PARA_CRONOLOGIA.values()} == {"pendiente"}
    assert "S5" in m.HIPOTESIS_PARA_CRONOLOGIA["H-d"]["texto"]
    for frase in ("dependencia entre bytes", "evidencia temporal", "fijacion autenticada"):
        assert frase in m.SEPARACION_DE_PLANOS, frase


def test_g1_componentes_de_fijado_y_distincion_de_estados():
    m = _modulo()
    assert tuple(m.COMPONENTES_DE_FIJADO) == ("F-1", "F-2", "F-3", "F-4")
    assert {c["estado"] for c in m.COMPONENTES_DE_FIJADO.values()} == {"no_acreditado"}
    assert tuple(m.DISTINCION_DE_ESTADOS) == ("sin_fijar", "ausente", "declarado_sintetico", "fijado")
    fijado = m.DISTINCION_DE_ESTADOS["fijado"]
    assert fijado["exige"] == ("F-1", "F-2", "F-3", "F-4")
    assert fijado["bytes"] == "no_representable_en_los_bytes_de_ae69"
    assert m.DISTINCION_DE_ESTADOS["sin_fijar"]["bytes"] == "hasheable"
    assert m.DISTINCION_DE_ESTADOS["ausente"]["bytes"] == "incompleta_no_hasheable"
    assert tuple(m.LAGUNAS_DE_DISTINCION) == ("L1", "L2", "L3")


def test_g1_estado_verificable_de_elemento_nunca_da_fijado():
    m = _modulo()
    e = ELEMENTOS[0]
    completa = _declaracion()
    assert m.estado_verificable_de_elemento(completa, e) == "declarado_sintetico"
    assert m.estado_verificable_de_elemento(_declaracion(pendiente=e), e) == "sin_fijar_explicito"
    ausente = _declaracion()
    del ausente[e]
    assert m.estado_verificable_de_elemento(ausente, e) == "ausente"
    nulo = _declaracion()
    nulo[e] = {"estado": "declarado_sintetico", "valor": None}
    assert m.estado_verificable_de_elemento(nulo, e) == "forma_no_admitida"
    assert m.estado_verificable_de_elemento([], e) == "forma_no_admitida"
    assert m.ESTADOS_VERIFICABLES == ("sin_fijar_explicito", "ausente", "declarado_sintetico", "forma_no_admitida")
    assert "fijado" not in m.ESTADOS_VERIFICABLES
    with pytest.raises(ValueError):
        m.estado_verificable_de_elemento(completa, "elemento_inventado")


def test_g1_contraejemplo_l1_marcador_textual_pasa_como_declarado():
    m = _modulo()
    e = ELEMENTOS[0]
    d = _declaracion()
    d[e] = {"estado": "declarado_sintetico", "valor": "pendiente"}
    assert m.estado_verificable_de_elemento(d, e) == "declarado_sintetico"
    assert iv.comprobar_declaracion_sintetica(d) == "completa_sintetica_sin_autenticar"
    assert "L1" in m.LAGUNAS_DE_DISTINCION and "D9" in m.DECISIONES_DEL_OPERADOR_AE71


def test_g1_regla_externa_designaciones_por_ruta():
    m = _modulo()
    h1, h2 = iv.hash_de_declaracion_sintetica(_declaracion("uno")), iv.hash_de_declaracion_sintetica(_declaracion("dos"))
    b = rp.serializar_entrada(_protocolo({"clave_a": h1, "clave_b": h2}))
    rutas = (("estrategia", "parametros", "clave_a"), ("estrategia", "parametros", "clave_b"))
    r = m.designaciones_por_regla(b, rp.hash_entrada(b), rutas)
    assert r == {rutas[0]: h1, rutas[1]: h2}
    assert m.designaciones_por_regla(b, "0" * 64, rutas) == {rutas[0]: None, rutas[1]: None}
    identificacion = m.FICHAS_POR_TOPOLOGIA["directo_en_nuevo_esquema"].identificacion_de_la_regla
    assert "si D4" in identificacion and "no contienen por si solos toda la semantica" in identificacion
    for ficha in m.FICHAS_POR_TOPOLOGIA.values():
        assert "autodescrita" not in ficha.identificacion_de_la_regla
    assert "externa" in m.FICHAS_POR_TOPOLOGIA["directo_en_campo_existente_no_previsto"].identificacion_de_la_regla


def test_g1_c15_directo_cambiar_la_declaracion_exige_otro_protocolo():
    m = _modulo()
    d1, d2 = _declaracion("uno"), _declaracion("dos")
    p1, p2 = _con_hash(iv.hash_de_declaracion_sintetica(d1)), _con_hash(iv.hash_de_declaracion_sintetica(d2))
    b1, b2 = rp.serializar_entrada(p1), rp.serializar_entrada(p2)
    assert rp.hash_entrada(b1) != rp.hash_entrada(b2)
    with pytest.raises(rp.EntradaRegistroInvalidaError, match="segundo protocolo"):
        rp.validar_registro([b1, _segundo_protocolo(b1, p2)])
    for t in DIRECTAS:
        c = m.consecuencia_de_cambiar_la_declaracion(t)
        assert c["resultado"] == "otro_protocolo" and "otro registro" in c["texto"], t


def test_g1_c15_inverso_mismo_protocolo_y_declaraciones_coexisten():
    m = _modulo()
    b = rp.serializar_entrada(_protocolo())
    dg = rp.hash_entrada(b)
    candidatas = (vv.CandidataDeVinculo(_declaracion("uno"), dg), vv.CandidataDeVinculo(_declaracion("dos"), dg))
    assert len(vv.declaraciones_que_verifican("inverso_desde_la_declaracion", dg, candidatas)) == 2
    assert rp.hash_entrada(b) == dg
    c = m.consecuencia_de_cambiar_la_declaracion("inverso_desde_la_declaracion")
    assert c["resultado"] == "mismo_protocolo_declaraciones_coexisten"


def test_g1_c15_manifiesto_solo_modelo_sintetico():
    m = _modulo()
    b = rp.serializar_entrada(_protocolo())
    dg = rp.hash_entrada(b)
    d1, d2 = _declaracion("uno"), _declaracion("dos")
    h2 = iv.hash_de_declaracion_sintetica(d2)
    segundo = (vv.ManifiestoSintetico(dg, h2),)
    assert vv.declaraciones_que_verifican(
        "manifiesto_externo", dg, (vv.CandidataDeVinculo(d1), vv.CandidataDeVinculo(d2)), manifiestos=segundo) == (h2,)
    c = m.consecuencia_de_cambiar_la_declaracion("manifiesto_externo")
    assert c["resultado"] == "mismo_protocolo_otro_manifiesto_en_modelo_sintetico"
    assert "modelo sintetico" in c["texto"] and "sin formato ni garantia operativa" in c["texto"]
    assert "S4" in c["texto"]


def test_g1_c11_inverso_acepta_declaracion_construida_tras_la_prediccion():
    m = _modulo()
    b = rp.serializar_entrada(_protocolo())
    estado = rp.validar_registro([b])
    prediccion = rp.nueva_prediccion(estado, "BALOTO", 2714, sinteticos.historico(2081, 2713), PROBABILIDADES)
    tardia = vv.CandidataDeVinculo(_declaracion("tardia"), prediccion["protocolo_hash"])
    assert vv.declaraciones_que_verifican("inverso_desde_la_declaracion", estado.hash_protocolo, (tardia,))
    assert "protocolo_no_depende_de_declaracion" in m.dependencia_de_bytes("inverso_desde_la_declaracion")


def test_g1_un_digest_sin_bytes_coincidentes_no_designa_nada():
    m = _modulo()
    h = iv.hash_de_declaracion_sintetica(_declaracion())
    b = rp.serializar_entrada(_con_hash(h))
    assert m.designaciones_por_regla(b, rp.hash_entrada(rp.serializar_entrada(_con_hash("9" * 64))), (CAMPO,)) == \
        {CAMPO: None}


def test_g1_estados_y_resultados_sin_acreditacion():
    m = _modulo()
    resultados = [*m.ESTADOS_VERIFICABLES, *m.RELACIONES_DE_BYTES, m.MARCA_SIN_CRONOLOGIA]
    resultados += [m.consecuencia_de_cambiar_la_declaracion(t)["resultado"] for t in TOPOLOGIAS]
    resultados += [c["estado"] for c in m.COMPONENTES_DE_FIJADO.values()]
    for r in resultados:
        if r.startswith(("sin_", "no_")):
            continue
        assert not re.search(r"autenticad|acreditad|suficien|fijad", r), r
    for frase in ("no es prueba temporal", "no acredita", "suficiencia", "completitud"):
        assert frase in m.ALCANCE_DEL_ANALISIS_AE71, frase


def test_g1_c7_citado_y_c14_derivado_por_separado():
    m = _modulo()
    a = {x.id: x for x in m.CLASIFICACION_DE_AFIRMACIONES}
    assert a["C7"].clase == "hecho_citado_de_fuente"
    assert set(a["C7"].procedencia) == {f"AE-67:C{i}" for i in range(1, 8)}
    assert "manifiesto" not in a["C7"].texto
    assert a["C14"].clase == "derivacion_propia" and "premisa:C7" in a["C14"].procedencia
    assert "no se afirma que ese uso sea imposible" in a["C14"].texto


def test_g1_clasificacion_de_afirmaciones_con_procedencia_exacta():
    m = _modulo()
    ids = tuple(a.id for a in m.CLASIFICACION_DE_AFIRMACIONES)
    assert ids == tuple(f"C{i}" for i in range(1, 19))
    clases = {a.id: a.clase for a in m.CLASIFICACION_DE_AFIRMACIONES}
    for i in range(1, 7):
        assert clases[f"C{i}"] == "hecho_observado_en_codigo"
    for i in range(8, 16):
        assert clases[f"C{i}"] == "derivacion_propia"
    for i in (16, 17, 18):
        assert clases[f"C{i}"] == "hipotesis_de_aplicacion"
    afirmaciones_67 = {a.id for a in (*vr.AFIRMACIONES_RFC_3161, *vr.AFIRMACIONES_RFC_9162)}
    supuestos = {*vv.SUPUESTOS_DEL_MODELO, *m.SUPUESTOS_ADICIONALES_AE71}
    pruebas = {n for n in globals() if n.startswith("test_")}
    for a in m.CLASIFICACION_DE_AFIRMACIONES:
        assert a.texto.strip() and a.evidencia.strip() and a.procedencia, a.id
        if a.clase == "hecho_observado_en_codigo":
            assert any(p.endswith(BASE) and p.startswith("backend/app/") for p in a.procedencia), a.id
            citadas = [p.removeprefix("prueba:") for p in a.procedencia if p.startswith("prueba:")]
            assert citadas and set(citadas) <= pruebas, a.id
            assert a.estado == "observado_en_pruebas", a.id
        elif a.clase == "hecho_citado_de_fuente":
            for p in a.procedencia:
                coincide = re.fullmatch(r"AE-67:(C\d|T\d)", p)
                assert coincide and coincide.group(1) in afirmaciones_67, (a.id, p)
            assert a.estado == "citado_de_ae67", a.id
        elif a.clase == "derivacion_propia":
            for p in a.procedencia:
                assert p.startswith("premisa:"), (a.id, p)
                premisa = p.removeprefix("premisa:")
                if re.fullmatch(r"C\d+", premisa):
                    assert premisa in ids and premisa != a.id
                elif premisa.startswith("supuesto:"):
                    assert premisa.removeprefix("supuesto:") in supuestos
                elif premisa.startswith("AE-67:"):
                    assert premisa.removeprefix("AE-67:") in afirmaciones_67
                else:
                    modulo, simbolo = premisa.rsplit(".", 1)
                    assert hasattr(importlib.import_module(f"app.application.ml.{modulo}"), simbolo), p
            assert a.estado == "derivado", a.id
        else:
            assert a.estado == "pendiente", a.id


def test_g1_modulo_puro_sin_red_reloj_ni_archivos():
    m = _modulo()
    arbol = ast.parse(Path(m.__file__).read_text(encoding="utf-8"))
    prohibidos = {"socket", "urllib", "requests", "http", "time", "subprocess", "random", "os", "pathlib",
                  "sqlalchemy", "datetime"}
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            assert not {a.name.split(".")[0] for a in nodo.names} & prohibidos
        if isinstance(nodo, ast.ImportFrom):
            assert (nodo.module or "").split(".")[0] not in prohibidos
            assert not (nodo.module or "").startswith("app.infrastructure")
        if isinstance(nodo, ast.Attribute):
            assert nodo.attr not in {"now", "utcnow", "today"}, nodo.attr
        if isinstance(nodo, ast.Name):
            assert nodo.id not in {"open", "eval", "exec"}, nodo.id


_PROHIBIDAS = {"aprobado", "aprobada", "aprobados", "aprobadas", "go", "cumplido", "cumplida", "desbloqueado",
               "desbloqueada", "autorizado", "autorizada", "recomendado", "recomendada", "elegido", "elegida",
               "autenticado", "autenticada", "acreditado", "acreditada", "valido", "valida"}


def test_g1_textos_sin_aprobacion_autorizacion_ni_acreditacion():
    m = _modulo()
    textos = [m.ALCANCE_DEL_ANALISIS_AE71, m.SEPARACION_DE_PLANOS]
    for registro in (m.SUPUESTOS_ADICIONALES_AE71, m.HIPOTESIS_PARA_CRONOLOGIA, m.COMPONENTES_DE_FIJADO,
                     m.DECISIONES_DEL_OPERADOR_AE71, m.LAGUNAS_DE_DISTINCION):
        textos += [v["texto"] for v in registro.values()]
    textos += [v["representacion"] for v in m.DISTINCION_DE_ESTADOS.values()]
    for f in m.FICHAS_POR_TOPOLOGIA.values():
        for campo in ("datos_a_fijar_antes_del_plazo", "bytes_verificados", "cambios_de_esquema_y_pruebas",
                      "comprobable_por_un_tercero", "no_demostrado"):
            textos += list(getattr(f, campo))
        textos += [f.identificacion_de_la_regla, f.consecuencia_de_cambiar_la_declaracion["texto"]]
    for a in m.CLASIFICACION_DE_AFIRMACIONES:
        textos += [a.texto, a.evidencia]
    fijos = "|".join(sorted({m.MARCA_SIN_CRONOLOGIA, "fijacion autenticada"}, key=len, reverse=True))
    textos = [re.sub(fijos, " ", t) for t in textos]
    palabras = {p.lower() for t in textos for p in re.split(r"[^A-Za-z]+", t) if p}
    assert not palabras & _PROHIBIDAS, palabras & _PROHIBIDAS


# ===========================================================================
# G2: invariantes sobre codigo existente (pasan sobre la base)
# ===========================================================================

def test_g2_huellas_de_ae52_y_ae63_a_ae70():
    assert _huella((rp.ESQUEMA_ENTRADA, rp.TIPOS_ENTRADA, rp.REGLAS_EVALUACION_AE52, rp.PENDIENTES_BORRADOR_AE52,
                    rp.NOTA_PROTOCOLO, rp.ALCANCE_REGISTRO)) == (
        "4f31cdeb3c4d29b1740592d4d81de2f8f51305abf4a82743c49f12985621c50b")
    assert _huella((tc.CONDICIONES_DE_TRASLADO, tc.DECISIONES_DEL_OPERADOR_AE63,
                    tc.ENUNCIADOS_DE_FUENTE_NECESARIOS)) == (
        "2600313c17c65eab1b6f69c5a9abe3708f87f951df57edca6266ef46bc014186")
    assert _huella((vp.PROCEDENCIA_V6, vp.LECTURA_POR_PUNTO, vp.ENUNCIADOS_NULAS_Y_E_PROCESOS, vp.DISCREPANCIAS,
                    vp.DEPENDENCIAS_DE_N2, vp.DERIVACION_1_SOBRE_E_TEOREMA_3, vp.ESTADOS_TRAS_AE64)) == (
        "631091da5a81a5097ad2d840043085fd43cec1929dcddd17644222121e91e054")
    assert _huella((ao.OBLIGACIONES_AE65, ao.EVIDENCIA_REQUERIDA_O3, ao.ASPECTOS_DE_PREDICTIBILIDAD,
                    ao.COMPONENTES_DE_F2, ao.CONSECUENCIAS, ao.OBSERVACION_DEPENDENCIA_O3_COMUN,
                    ao.HIPOTESIS_UNIFORMIDAD_CONDICIONAL, ao.NIVELES_DE_ANTERIORIDAD, ao.USOS)) == (
        "209cf5282031f5489c5f75e7497cc680dd15f73b190144491e4fbea36ea03b7f")
    assert _huella((pe.REQUISITOS, pe.COLUMNAS_DE_LA_MATRIZ, pe.ESTADOS_DE_CELDA, pe.RESULTADOS_OMISION_DECLARADA,
                    pe.RESULTADOS_AUSENCIA_INFERIDA, pe.FUENTES_PRIMARIAS, pe.ALTERNATIVAS, pe.COMPLEMENTOS,
                    pe.CONDICIONES_PENDIENTES_DEL_PROTOCOLO, pe.NO_DEMUESTRA_NINGUNA, pe.PREGUNTAS_ABIERTAS,
                    pe.RECOMENDACION_CONDICIONAL)) == (
        "17f9e0ba301092c76fc412063d5ad5f764dd6412d8feaeb76cd307ef018c639a")
    assert _huella((vr.PROCEDENCIA_RFC, vr.ESTADOS_AFIRMACION, vr.AFIRMACIONES_RFC_3161, vr.AFIRMACIONES_RFC_9162,
                    vr.CONDICIONES_DEL_REPOSITORIO, vr.DISCREPANCIAS_CON_AE66, vr.DERIVACION_MARGEN_RFC_9162,
                    vr.RESULTADOS_SELLO)) == (
        "eb094cddc0659b3b4e015922025db9ca3327116d10677677a26224270da857c5")
    assert _huella((ec.ALCANCE_RFC_9162, ec.MODELO_DE_FIRMA, ec.AUTENTICACION_DE_R0, ec.REQUISITOS_PREVIOS,
                    ec.CONDICIONES_DEL_PROTOCOLO, ec.CORRESPONDENCIA_CON_AE66, ec.DEPENDENCIAS_NORMATIVAS,
                    ec.DEPENDENCIAS_DE_VERIFICACION, ec.INSTANTES, ec.HIPOTESIS_TEMPORALES,
                    ec.LIMITE_DE_COMPLETITUD, tuple(ec.REGLAS_DE_DUPLICADOS_CANDIDATAS),
                    ec.REGLA_DE_DUPLICADOS_ELEGIDA, ec.RESULTADOS_RELOJ, ec.REQUISITOS_DE_VIA,
                    ec.RESULTADOS_DE_VIA)) == (
        "03c83bb1719e68bc14744bde36971f92a7a0f45784512424566305c2f504b00d")
    assert _huella((iv.SITUACIONES_EN_AE52, iv.RELACION_CON_AE52, iv.ELEMENTOS_DE_R0, iv.ESTADO_ACTUAL_DE_R0,
                    iv.CORRESPONDENCIA_CON_PENDIENTES_AE52, iv.PREGUNTAS_ABIERTAS_AE69, iv.ESTADOS_DE_ELEMENTO,
                    iv.RESULTADOS_DECLARACION, iv.ALCANCE_DE_LA_COMPLETITUD, iv.TRATAMIENTO_DE_VALORES_VACIOS,
                    iv.CLASES_DE_AFIRMACION, iv.CLASIFICACION_DE_AFIRMACIONES)) == (
        "b5637fe7ee274d0a9b63d6a87837dd9d0e0a6a108772e10c26dde23c55d83a24")
    assert _huella((vv.SUPUESTOS_DEL_MODELO, vv.TOPOLOGIAS_DE_VINCULO, vv.CRITERIOS_DE_VINCULO, vv.ESTADOS_DE_CELDA,
                    vv.MATRIZ_DE_VINCULO, vv.TOPOLOGIA_ELEGIDA, vv.REPRESENTACIONES_DE_PENDIENTES,
                    vv.REPRESENTACION_ELEGIDA, vv.CONSECUENCIA_DE_COMPLETAR_DESPUES, vv.ALCANCE_DEL_ANALISIS,
                    vv.CLASIFICACION_DE_AFIRMACIONES)) == (
        "23c622009ec080a506d4f8f299b02382ff5229bb1a6aed162f88a7ab64648350")
    assert dr.huella_diseno() == "6743293d4e247c17ed5f9c098824caf4f740873f00a04d4e223f334874f8de3c"


def test_g2_estados_decisiones_y_bloqueos_sin_cambios():
    assert {r.estado for r in {**ec.REQUISITOS_PREVIOS, **ec.CONDICIONES_DEL_PROTOCOLO}.values()} == {"sin_fijar"}
    assert {v["estado"] for v in ec.AUTENTICACION_DE_R0.values()} == {"pendiente"}
    assert ec.REGLA_DE_DUPLICADOS_ELEGIDA is None
    assert {e.estado for e in iv.ELEMENTOS_DE_R0.values()} == {"pendiente"}
    assert {p["estado"] for p in iv.PREGUNTAS_ABIERTAS_AE69.values()} == {"sin_respuesta"}
    assert vv.TOPOLOGIA_ELEGIDA is None and vv.REPRESENTACION_ELEGIDA is None
    condiciones = {c.id: c.estado for c in tc.CONDICIONES_DE_TRASLADO}
    for id_ in ("F1_anterioridad", "F2_correspondencia_de_la_filtracion", "O3_tratamiento_de_omisiones",
                "N2_inversion_para_p1b", "U1_usos_de_1_sobre_E"):
        assert condiciones[id_] == "pendiente", id_
    for id_ in ("F2_correspondencia_de_la_filtracion", "N2_inversion_para_p1b", "U1_usos_de_1_sobre_E"):
        assert vp.ESTADOS_TRAS_AE64[id_]["estado"] == "pendiente", id_
    for o in ao.OBLIGACIONES_AE65.values():
        assert o.estado == "pendiente", o.id
    assert pi.ESTADO_EXPEDIENTE == "expediente_sin_eleccion"
    assert pi.AUTORIZA_EVALUACION is False
    for decision in (*pi.DECISIONES_INFERENCIALES_ABIERTAS.values(), *pi.DECISIONES_REQUERIDAS):
        assert decision.valor is None and decision.estado == "sin_decidir"
    pi.verificar_expediente()
    assert len(rp.PENDIENTES_BORRADOR_AE52) == 7
    assert ESPECIFICACION_CANDIDATA_AE53["estado"] == "candidata_no_aprobada"


# ===========================================================================
# G3: integraciones contra la API publica real (pasan sobre la base)
# ===========================================================================

def test_g3_c1_marcador_textual_en_valor_cuenta_como_declarado():
    d = _declaracion()
    d[ELEMENTOS[0]] = {"estado": "declarado_sintetico", "valor": "pendiente"}
    assert iv.comprobar_declaracion_sintetica(d) == "completa_sintetica_sin_autenticar"
    d[ELEMENTOS[0]] = {"estado": "declarado_sintetico", "valor": {"regla": "pendiente"}}
    assert iv.comprobar_declaracion_sintetica(d) == "completa_sintetica_sin_autenticar"


def test_g3_c2_ausente_no_se_hashea_y_pendiente_si():
    e = ELEMENTOS[0]
    ausente = _declaracion()
    del ausente[e]
    assert iv.comprobar_declaracion_sintetica(ausente) == "incompleta"
    with pytest.raises(iv.DeclaracionSinteticaInvalidaError):
        iv.hash_de_declaracion_sintetica(ausente)
    pendiente = _declaracion(pendiente=e)
    assert iv.comprobar_declaracion_sintetica(pendiente) == "parcial"
    assert iv.hash_de_declaracion_sintetica(pendiente) != iv.hash_de_declaracion_sintetica(_declaracion())


def test_g3_c3_no_existe_estado_fijado():
    assert iv.ESTADOS_DE_ELEMENTO == ("pendiente", "declarado_sintetico")
    assert "fijado" not in iv.ESTADOS_DE_ELEMENTO


def test_g3_c4_la_regla_determina_el_hash_designado():
    h1, h2 = iv.hash_de_declaracion_sintetica(_declaracion("uno")), iv.hash_de_declaracion_sintetica(_declaracion("dos"))
    b = rp.serializar_entrada(_protocolo({"clave_a": h1, "clave_b": h2}))
    t = "directo_en_campo_existente_no_previsto"
    designados = [vv.hash_designado(t, b, rp.hash_entrada(b), vv.ReglaDeVinculo(t, ("estrategia", "parametros", k)))
                  for k in ("clave_a", "clave_b")]
    assert designados == [h1, h2]


def test_g3_c5_inverso_acepta_declaracion_construida_tras_la_prediccion():
    b = rp.serializar_entrada(_protocolo())
    estado = rp.validar_registro([b])
    prediccion = rp.nueva_prediccion(estado, "BALOTO", 2714, sinteticos.historico(2081, 2713), PROBABILIDADES)
    assert rp.validar_registro([b, rp.serializar_entrada(prediccion)]).total == 2
    tardia = vv.CandidataDeVinculo(_declaracion("tardia"), prediccion["protocolo_hash"])
    assert vv.declaraciones_que_verifican("inverso_desde_la_declaracion", estado.hash_protocolo, (tardia,)) == (
        iv.hash_de_declaracion_sintetica(_declaracion("tardia")),)


def test_g3_c6_esquema_en_los_bytes_y_cambio_de_campo_cambia_el_hash():
    b = rp.serializar_entrada(_protocolo())
    assert rp.leer_entrada(b)["esquema"] == rp.ESQUEMA_ENTRADA
    assert rp.ESQUEMA_ENTRADA.encode("utf-8") in b
    modelo = {"esquema": "modelo-sintetico/1", "campo_de_prueba": "a" * 64}
    otro = {**modelo, "esquema": "modelo-sintetico/2"}
    assert rp.hash_entrada(rp.serializar_entrada(modelo)) != rp.hash_entrada(rp.serializar_entrada(otro))


def test_g3_c15_premisa_dos_protocolos_en_el_mismo_registro_se_rechazan():
    p1, p2 = _con_hash("1" * 64), _con_hash("2" * 64)
    b1, b2 = rp.serializar_entrada(p1), rp.serializar_entrada(p2)
    with pytest.raises(rp.EntradaRegistroInvalidaError, match="segundo protocolo"):
        rp.validar_registro([b1, _segundo_protocolo(b1, p2)])
    assert rp.validar_registro([b2]).total == 1
