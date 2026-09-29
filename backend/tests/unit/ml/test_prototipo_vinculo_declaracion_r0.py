"""Tests de la Etapa AE-72, validada: prototipo optativo y verificable de
extremo a extremo que vincula la declaracion sintetica R0 (once elementos)
con un protocolo y una prediccion sinteticos de AE-52 mediante una topologia
candidata.

Tres grupos:

G1  dependen del modulo nuevo, que se importa dentro de cada prueba; sobre
    la base cada una falla por separado con `ModuleNotFoundError`.
G2  invariantes sobre codigo existente (huellas de AE-52 y AE-63 a AE-71,
    estados, decisiones y bloqueos); pasan sobre la base.
G3  premisas de integracion contra la API publica real de AE-52, AE-69,
    AE-70 y AE-71; pasan sobre la base.

La topologia es `candidata`, de activacion optativa: `TOPOLOGIA_ELEGIDA` y
`REPRESENTACION_ELEGIDA` siguen en None y D1-D9 sin decidir. El verificador
solo comprueba integridad de bytes; la autenticacion de R0, la recepcion
antes del plazo, la completitud y unicidad del canal y la aptitud
inferencial quedan sin evidencia. Todo sintetico: sin sorteos reales,
entrenamiento, inferencia operativa, sello temporal real ni PostgreSQL."""
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

from app.application.ml import analisis_alternativas_de_declaracion_previa as aa
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

PROBABILIDADES = [0.1] * 43
"""Salida fabricada: solo prueba el formato, nunca es una prediccion."""
ELEMENTOS = tuple(iv.ELEMENTOS_DE_R0)
CORTES = {"BALOTO": 2713, "BALOTO_REVANCHA": 2713}


def _modulo():
    return importlib.import_module("app.application.ml.prototipo_vinculo_declaracion_r0")


def _estrategia(parametros=None):
    return {
        "nombre": "estrategia_sintetica", "descripcion": "estrategia sintetica solo para pruebas",
        "huella_codigo": "a" * 64, "archivos_codigo": ["sintetico.py"],
        "parametros": parametros if parametros is not None else {"semilla": 1},
        "entorno": {"python": "3.x", "scikit_learn": "0.0"},
    }


def _elementos(valor="valor-de-prueba", pendientes=()):
    """Elementos sinteticos de AE-69; los valores son datos de prueba."""
    d = {e: {"estado": "declarado_sintetico", "valor": {"sintetico": f"{valor}-{i}"}} for i, e in enumerate(ELEMENTOS)}
    for e in pendientes:
        d[e] = {"estado": "pendiente"}
    return d


def _recorrido(m, elementos=None, objetivos=(2714,)):
    """Recorrido completo con las API reales: declaracion -> bytes y hash ->
    protocolo candidato -> predicciones sinteticas -> registro."""
    declaracion = m.construir_declaracion(elementos if elementos is not None else _elementos())
    bytes_declaracion = m.bytes_de_declaracion(declaracion)
    protocolo = m.construir_protocolo_candidato(declaracion, protocolo_id="sintetico-ae72", estrategia=_estrategia(),
                                                cortes=CORTES)
    entradas = [rp.serializar_entrada(protocolo)]
    for objetivo in objetivos:
        estado = rp.validar_registro(entradas)
        prediccion = rp.nueva_prediccion(estado, "BALOTO", objetivo, sinteticos.historico(2081, objetivo - 1),
                                         PROBABILIDADES)
        entradas.append(rp.serializar_entrada(prediccion))
    return declaracion, bytes_declaracion, protocolo, entradas


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

# --- 1. Representacion versionada y estricta de la declaracion -------------

def test_g1_declaracion_versionada_canonica_y_estricta():
    m = _modulo()
    d = m.construir_declaracion(_elementos())
    assert set(d) == {"esquema", "elementos"} and d["esquema"] == m.ESQUEMA_DECLARACION == "declaracion-r0-sintetica/1"
    b = m.bytes_de_declaracion(d)
    assert b == rp.serializar_entrada(d) and rp.leer_entrada(b) == d
    assert m.hash_de_declaracion(d) == rp.hash_entrada(b)
    assert m.leer_declaracion(b) == d
    with pytest.raises(m.DeclaracionR0Invalida):
        m.leer_declaracion(json.dumps(d, indent=1).encode("utf-8") + b"\n")
    with pytest.raises(m.DeclaracionR0Invalida):
        m.leer_declaracion(rp.serializar_entrada({**d, "esquema": "declaracion-r0-sintetica/2"}))
    with pytest.raises(m.DeclaracionR0Invalida):
        m.leer_declaracion(rp.serializar_entrada({**d, "extra": 1}))
    with pytest.raises(m.DeclaracionR0Invalida):
        m.leer_declaracion(b"[1]\n")


@pytest.mark.parametrize("caso, esperado", [
    ("pendiente", "sin_fijar_explicito"),
    ("ausente", "ausente"),
    ("declarado", "declarado_sintetico"),
    ("marcador", "declarado_con_marcador_textual"),
    ("marcador_anidado", "declarado_con_marcador_textual"),
    ("nulo", "formato_invalido"),
    ("float", "formato_invalido"),
    ("estado_desconocido", "formato_invalido"),
])
def test_g1_estado_por_elemento(caso, esperado):
    m = _modulo()
    e = ELEMENTOS[0]
    elementos = _elementos()
    if caso == "pendiente":
        elementos[e] = {"estado": "pendiente"}
    elif caso == "ausente":
        del elementos[e]
    elif caso == "marcador":
        elementos[e] = {"estado": "declarado_sintetico", "valor": "  TBD "}
    elif caso == "marcador_anidado":
        elementos[e] = {"estado": "declarado_sintetico", "valor": {"regla": ["x", "Pendiente"]}}
    elif caso == "nulo":
        elementos[e] = {"estado": "declarado_sintetico", "valor": None}
    elif caso == "float":
        elementos[e] = {"estado": "declarado_sintetico", "valor": 1.5}
    elif caso == "estado_desconocido":
        elementos[e] = {"estado": "fijado"}
    estados = m.estados_de_elementos({"esquema": m.ESQUEMA_DECLARACION, "elementos": elementos})
    assert estados[e] == esperado
    assert set(estados) == set(ELEMENTOS)
    assert set(estados.values()) <= set(m.ESTADOS_DE_ELEMENTO)
    assert not any("fijado" == s or s.startswith("fijad") for s in m.ESTADOS_DE_ELEMENTO)


def test_g1_resumen_de_declaracion_y_rechazos():
    m = _modulo()
    assert m.resumen_de_declaracion(m.construir_declaracion(_elementos())) == \
        "estructuralmente_completa_sin_autenticar"
    parcial = m.construir_declaracion(_elementos(pendientes=ELEMENTOS[:2]))
    assert m.resumen_de_declaracion(parcial) == "parcial_con_pendientes_explicitos"
    todos = m.construir_declaracion(_elementos(pendientes=ELEMENTOS))
    assert m.resumen_de_declaracion(todos) == "todos_pendientes"
    marcada = _elementos()
    marcada[ELEMENTOS[3]] = {"estado": "declarado_sintetico", "valor": "sin fijar"}
    d = m.construir_declaracion(marcada)
    assert m.resumen_de_declaracion(d) == "estructuralmente_completa_con_marcadores_textuales"
    assert m.elementos_con_marcador(d) == (ELEMENTOS[3],)
    ausente = _elementos()
    del ausente[ELEMENTOS[5]]
    with pytest.raises(m.DeclaracionR0Invalida, match="falta"):
        m.construir_declaracion(ausente)
    with pytest.raises(m.DeclaracionR0Invalida):
        m.construir_declaracion({**_elementos(), "elemento_inventado": {"estado": "pendiente"}})
    for r in m.RESUMENES_DE_DECLARACION:
        assert not re.search(r"fijad|acreditad|autenticad|valid", r.replace("sin_autenticar", "")), r


# --- 2. Regla candidata, versionada y optativa -----------------------------

def test_g1_regla_candidata_versionada_y_elecciones_sin_valor():
    m = _modulo()
    assert m.TOPOLOGIA_CANDIDATA == "directo_en_campo_existente_no_previsto"
    assert m.TOPOLOGIA_CANDIDATA in vv.TOPOLOGIAS_DE_VINCULO
    assert m.ESTADO_DE_LA_TOPOLOGIA == "candidata" and m.ACTIVACION == "optativa"
    assert m.REGLA_CANDIDATA == "ae72-vinculo-r0-en-parametros/1"
    assert m.CLAVE_RESERVADA == "vinculo_r0_candidato"
    assert m.RUTA_DEL_HASH == ("estrategia", "parametros", "vinculo_r0_candidato", "hash_declaracion")
    assert vv.TOPOLOGIA_ELEGIDA is None and vv.REPRESENTACION_ELEGIDA is None
    assert {d["estado"] for d in aa.DECISIONES_DEL_OPERADOR_AE71.values()} == {"sin_decidir"}
    assert not any(n.endswith("_ELEGIDA") for n in vars(m))
    assert tuple(m.COMPARACION_DE_TOPOLOGIAS) == tuple(vv.TOPOLOGIAS_DE_VINCULO)
    for t, c in m.COMPARACION_DE_TOPOLOGIAS.items():
        assert c["efecto_en_ae52"] and c["viable_de_extremo_a_extremo_sin_cambiar_ae52"] in (True, False), t
    viables = [t for t, c in m.COMPARACION_DE_TOPOLOGIAS.items() if c["viable_de_extremo_a_extremo_sin_cambiar_ae52"]]
    assert viables == [m.TOPOLOGIA_CANDIDATA]


def test_g1_protocolo_candidato_optativo_sintetico_y_sin_efecto_predeterminado():
    m = _modulo()
    d = m.construir_declaracion(_elementos())
    estrategia = _estrategia()
    original = json.loads(json.dumps(estrategia))
    p = m.construir_protocolo_candidato(d, protocolo_id="s", estrategia=estrategia, cortes=CORTES)
    assert estrategia == original
    assert p["sintetico"] is True and p["pendientes"] == []
    vinculo = p["estrategia"]["parametros"][m.CLAVE_RESERVADA]
    assert vinculo == {"regla": m.REGLA_CANDIDATA, "esquema_declaracion": m.ESQUEMA_DECLARACION,
                       "hash_declaracion": m.hash_de_declaracion(d)}
    assert rp.validar_registro([rp.serializar_entrada(p)]).total == 1
    sin_candidata = rp.construir_protocolo(protocolo_id="s", estrategia=_estrategia(), cortes=CORTES, pendientes=[],
                                           sintetico=True)
    assert m.CLAVE_RESERVADA not in sin_candidata["estrategia"]["parametros"]
    informe = m.verificar_vinculo([rp.serializar_entrada(sin_candidata)], m.bytes_de_declaracion(d))
    assert informe.estado_de_bytes == "protocolo_sin_vinculo_candidato"
    with pytest.raises(ValueError, match="reservada"):
        m.construir_protocolo_candidato(d, protocolo_id="s", estrategia=_estrategia({m.CLAVE_RESERVADA: 1}),
                                        cortes=CORTES)
    with pytest.raises(m.DeclaracionR0Invalida):
        m.construir_protocolo_candidato({"esquema": m.ESQUEMA_DECLARACION, "elementos": {}}, protocolo_id="s",
                                        estrategia=_estrategia(), cortes=CORTES)


# --- 3. Recorrido de extremo a extremo con las API reales ------------------

def test_g1_recorrido_completo_verifica_el_vinculo_de_bytes():
    m = _modulo()
    declaracion, bytes_decl, protocolo, entradas = _recorrido(m, objetivos=(2714, 2715))
    informe = m.verificar_vinculo(entradas, bytes_decl, objetivos_esperados=(("BALOTO", 2714), ("BALOTO", 2715)),
                                  protocolo_hash_esperado=rp.hash_entrada(entradas[0]))
    assert informe.estado_de_bytes == "vinculo_de_bytes_verificado"
    assert informe.hash_declaracion == m.hash_de_declaracion(declaracion)
    assert informe.protocolo_hash == rp.hash_entrada(entradas[0])
    assert informe.predicciones_vinculadas == 2 and informe.omitidas == ()
    assert informe.resumen_de_declaracion == "estructuralmente_completa_sin_autenticar"
    assert informe.pendientes == () and informe.marcadores == ()


def test_g1_declaracion_ausente_o_alterada():
    m = _modulo()
    _, bytes_decl, _, entradas = _recorrido(m)
    assert m.verificar_vinculo(entradas, None).estado_de_bytes == "declaracion_ausente"
    assert m.verificar_vinculo(entradas, b"no es json\n").estado_de_bytes == "declaracion_invalida"
    otra = m.bytes_de_declaracion(m.construir_declaracion(_elementos("alterada")))
    informe = m.verificar_vinculo(entradas, otra)
    assert informe.estado_de_bytes == "hash_de_declaracion_no_coincide"
    datos = json.loads(bytes_decl)
    del datos["elementos"][ELEMENTOS[0]]
    informe = m.verificar_vinculo(entradas, rp.serializar_entrada(datos))
    assert informe.estado_de_bytes == "declaracion_invalida" and "falta" in informe.detalle


def test_g1_regla_equivocada():
    m = _modulo()
    _, bytes_decl, protocolo, entradas = _recorrido(m)
    assert m.verificar_vinculo(entradas, bytes_decl, regla="otra-regla/1").estado_de_bytes == "regla_distinta"
    alterado = json.loads(json.dumps(protocolo))
    alterado["estrategia"]["parametros"][m.CLAVE_RESERVADA]["regla"] = "ae72-vinculo-r0-en-parametros/2"
    informe = m.verificar_vinculo([rp.serializar_entrada(alterado)], bytes_decl)
    assert informe.estado_de_bytes == "regla_distinta"
    mal = json.loads(json.dumps(protocolo))
    mal["estrategia"]["parametros"][m.CLAVE_RESERVADA] = "texto"
    assert m.verificar_vinculo([rp.serializar_entrada(mal)], bytes_decl).estado_de_bytes == "vinculo_mal_formado"


def test_g1_hash_de_protocolo_incorrecto():
    m = _modulo()
    _, bytes_decl, _, entradas = _recorrido(m)
    informe = m.verificar_vinculo(entradas, bytes_decl, protocolo_hash_esperado="0" * 64)
    assert informe.estado_de_bytes == "protocolo_hash_no_coincide"
    prediccion = rp.leer_entrada(entradas[1])
    alterada = rp.serializar_entrada({**prediccion, "protocolo_hash": "f" * 64})
    informe = m.verificar_vinculo([entradas[0], alterada], bytes_decl)
    assert informe.estado_de_bytes == "registro_invalido" and "protocolo distinto" in informe.detalle
    assert m.verificar_vinculo([], bytes_decl).estado_de_bytes == "registro_invalido"


def test_g1_cambio_de_declaracion_tras_el_registro():
    m = _modulo()
    _, bytes_decl, _, entradas = _recorrido(m, elementos=_elementos("original"))
    posterior = m.bytes_de_declaracion(m.construir_declaracion(_elementos("posterior")))
    assert m.verificar_vinculo(entradas, bytes_decl).estado_de_bytes == "vinculo_de_bytes_verificado"
    assert m.verificar_vinculo(entradas, posterior).estado_de_bytes == "hash_de_declaracion_no_coincide"


def test_g1_omision_de_prediccion():
    m = _modulo()
    _, bytes_decl, _, entradas = _recorrido(m, objetivos=(2714,))
    informe = m.verificar_vinculo(entradas, bytes_decl, objetivos_esperados=(("BALOTO", 2714), ("BALOTO", 2715)))
    assert informe.estado_de_bytes == "prediccion_omitida"
    assert informe.omitidas == (("BALOTO", 2715),)
    assert informe.completitud_y_unicidad_del_canal == "sin_evidencia"


def test_g1_completar_un_pendiente_exige_otro_protocolo_y_otro_registro():
    m = _modulo()
    e = ELEMENTOS[2]
    antes = _elementos(pendientes=(e,))
    d_antes, b_antes, p_antes, entradas = _recorrido(m, elementos=antes)
    informe = m.verificar_vinculo(entradas, b_antes)
    assert informe.estado_de_bytes == "vinculo_de_bytes_verificado" and informe.pendientes == (e,)
    assert "elementos_pendientes_en_la_declaracion" in informe.falta
    despues = _elementos()
    d_despues, b_despues, p_despues, entradas_nuevas = _recorrido(m, elementos=despues)
    assert m.verificar_vinculo(entradas, b_despues).estado_de_bytes == "hash_de_declaracion_no_coincide"
    assert rp.hash_entrada(rp.serializar_entrada(p_antes)) != rp.hash_entrada(rp.serializar_entrada(p_despues))
    with pytest.raises(rp.EntradaRegistroInvalidaError, match="segundo protocolo"):
        rp.validar_registro([entradas[0], _segundo_protocolo(entradas[0], p_despues)])
    assert m.verificar_vinculo(entradas_nuevas, b_despues).estado_de_bytes == "vinculo_de_bytes_verificado"
    assert rp.leer_entrada(entradas[1])["protocolo_hash"] != rp.leer_entrada(entradas_nuevas[1])["protocolo_hash"]
    assert "otro registro" in m.CONSECUENCIA_DE_COMPLETAR_UN_PENDIENTE


# --- 4. Verificador: estados precisos y limites de evidencia ---------------

def test_g1_planos_separados_y_nunca_acreditados():
    m = _modulo()
    _, bytes_decl, _, entradas = _recorrido(m)
    informe = m.verificar_vinculo(entradas, bytes_decl)
    assert tuple(m.PLANOS_DEL_INFORME) == ("integridad_de_bytes", "autenticacion_de_r0", "recepcion_antes_del_plazo",
                                           "completitud_y_unicidad_del_canal", "aptitud_inferencial")
    assert informe.autenticacion_de_r0 == "sin_evidencia"
    assert informe.recepcion_antes_del_plazo == "sin_evidencia"
    assert informe.completitud_y_unicidad_del_canal == "sin_evidencia"
    assert informe.aptitud_inferencial == "no_autorizada"
    for faltante in ("autenticacion_de_r0", "recepcion_antes_del_plazo", "completitud_y_unicidad_del_canal",
                     "decisiones_del_operador_d1_a_d9"):
        assert faltante in informe.falta, faltante
    for estado in (*m.ESTADOS_DE_BYTES, *m.ESTADOS_DE_PLANO):
        assert not re.search(r"fijad|acreditad|autenticad|aprobad|(?<!in)valid|apt[ao]", estado), estado
    assert set(dataclasses.asdict(informe)) >= set(m.PLANOS_DEL_INFORME) - {"integridad_de_bytes"}


def test_g1_informe_informa_marcadores_y_pendientes():
    m = _modulo()
    elementos = _elementos(pendientes=(ELEMENTOS[1],))
    elementos[ELEMENTOS[4]] = {"estado": "declarado_sintetico", "valor": "TODO"}
    _, bytes_decl, _, entradas = _recorrido(m, elementos=elementos)
    informe = m.verificar_vinculo(entradas, bytes_decl)
    assert informe.estado_de_bytes == "vinculo_de_bytes_verificado"
    assert informe.pendientes == (ELEMENTOS[1],) and informe.marcadores == (ELEMENTOS[4],)
    assert "valores_con_marcador_textual" in informe.falta
    assert informe.elementos[ELEMENTOS[4]] == "declarado_con_marcador_textual"


def test_g1_demostracion_sintetica_reproducible():
    m = _modulo()
    historico = sinteticos.historico(2081, 2713)
    a, b = m.demostrar_recorrido_sintetico(historico), m.demostrar_recorrido_sintetico(historico)
    assert a == b and a.estado_de_bytes == "vinculo_de_bytes_verificado"
    assert a.predicciones_vinculadas == 1 and a.aptitud_inferencial == "no_autorizada"
    with pytest.raises(rp.EntradaRegistroInvalidaError):
        m.demostrar_recorrido_sintetico(sinteticos.historico(2081, 2700))


# --- 5. Documentacion en registros y estilo --------------------------------

def test_g1_decisiones_criterios_y_compatibilidad():
    m = _modulo()
    assert set(m.DECISIONES_REQUERIDAS) == set(aa.DECISIONES_DEL_OPERADOR_AE71)
    assert m.CRITERIOS_PARA_PROMOVER and m.CRITERIOS_PARA_DESCARTAR
    assert any("D1" in c for c in m.CRITERIOS_PARA_PROMOVER)
    assert any("parametros" in c for c in m.CRITERIOS_PARA_DESCARTAR)
    for frase in ("no modifica AE-52", "optativa", "registros existentes"):
        assert frase in m.COMPATIBILIDAD, frase
    for frase in ("no es prueba temporal", "sin evidencia", "AUTORIZA_EVALUACION"):
        assert frase in m.LIMITES_DEL_PROTOTIPO, frase


def test_g1_no_modifica_ae52_ni_anteriores():
    m = _modulo()
    arbol = ast.parse(Path(m.__file__).read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            objetivos = nodo.targets if isinstance(nodo, ast.Assign) else [nodo.target]
            for objetivo in objetivos:
                assert not isinstance(objetivo, ast.Attribute), ast.dump(objetivo)
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


_PROHIBIDAS = {"aprobado", "aprobada", "go", "cumplido", "cumplida", "desbloqueado", "desbloqueada", "autorizado",
               "autorizada", "recomendado", "recomendada", "elegido", "elegida", "autenticado", "autenticada",
               "acreditado", "acreditada", "fijado", "fijada", "valido", "valida"}


def test_g1_textos_sin_aprobacion_ni_acreditacion():
    m = _modulo()
    textos = [m.COMPATIBILIDAD, m.LIMITES_DEL_PROTOTIPO, m.CONSECUENCIA_DE_COMPLETAR_UN_PENDIENTE,
              *m.CRITERIOS_PARA_PROMOVER, *m.CRITERIOS_PARA_DESCARTAR]
    for c in m.COMPARACION_DE_TOPOLOGIAS.values():
        textos += [c["efecto_en_ae52"], c["motivo"]]
    palabras = {p.lower() for t in textos for p in re.split(r"[^A-Za-z]+", t) if p}
    assert not palabras & _PROHIBIDAS, palabras & _PROHIBIDAS


# ===========================================================================
# G2: invariantes sobre codigo existente (pasan sobre la base)
# ===========================================================================

def test_g2_huellas_de_ae52_y_ae63_a_ae71():
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
    assert _huella((aa.SEPARACION_DE_PLANOS, aa.SUPUESTOS_ADICIONALES_AE71, aa.HIPOTESIS_PARA_CRONOLOGIA,
                    aa.COMPONENTES_DE_FIJADO, aa.DISTINCION_DE_ESTADOS, aa.LAGUNAS_DE_DISTINCION,
                    aa.ESTADOS_VERIFICABLES, aa.DECISIONES_DEL_OPERADOR_AE71, aa.DEPENDENCIAS_QUE_IMPIDEN_IMPLEMENTAR,
                    aa.RELACIONES_DE_BYTES, aa.MARCA_SIN_CRONOLOGIA, aa.FICHAS_POR_TOPOLOGIA,
                    aa.ALCANCE_DEL_ANALISIS_AE71, aa.CLASIFICACION_DE_AFIRMACIONES)) == (
        "5f28e0924a986bbf157ad086333f940acf04becf9ccedbd0d22931eda75c8de7")
    assert dr.huella_diseno() == "6743293d4e247c17ed5f9c098824caf4f740873f00a04d4e223f334874f8de3c"


def test_g2_estados_decisiones_y_bloqueos_sin_cambios():
    assert {r.estado for r in {**ec.REQUISITOS_PREVIOS, **ec.CONDICIONES_DEL_PROTOCOLO}.values()} == {"sin_fijar"}
    assert {v["estado"] for v in ec.AUTENTICACION_DE_R0.values()} == {"pendiente"}
    assert {e.estado for e in iv.ELEMENTOS_DE_R0.values()} == {"pendiente"}
    assert {p["estado"] for p in iv.PREGUNTAS_ABIERTAS_AE69.values()} == {"sin_respuesta"}
    assert vv.TOPOLOGIA_ELEGIDA is None and vv.REPRESENTACION_ELEGIDA is None
    assert {d["estado"] for d in aa.DECISIONES_DEL_OPERADOR_AE71.values()} == {"sin_decidir"}
    assert {c["estado"] for c in aa.COMPONENTES_DE_FIJADO.values()} == {"no_acreditado"}
    condiciones = {c.id: c.estado for c in tc.CONDICIONES_DE_TRASLADO}
    for id_ in ("F1_anterioridad", "F2_correspondencia_de_la_filtracion", "O3_tratamiento_de_omisiones",
                "N2_inversion_para_p1b", "U1_usos_de_1_sobre_E"):
        assert condiciones[id_] == "pendiente", id_
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
# G3: premisas de integracion contra la API real (pasan sobre la base)
# ===========================================================================

def test_g3_parametros_admite_un_objeto_anidado_con_hash_y_lo_conserva():
    vinculo = {"regla": "regla-de-prueba/1", "esquema_declaracion": "esquema-de-prueba/1", "hash_declaracion": "1" * 64}
    p = rp.construir_protocolo(protocolo_id="s", estrategia=_estrategia({"semilla": 1, "clave_de_prueba": vinculo}),
                               cortes=CORTES, pendientes=[], sintetico=True)
    b = rp.serializar_entrada(p)
    estado = rp.validar_registro([b])
    assert estado.protocolo["estrategia"]["parametros"]["clave_de_prueba"] == vinculo
    prediccion = rp.nueva_prediccion(estado, "BALOTO", 2714, sinteticos.historico(2081, 2713), PROBABILIDADES)
    assert prediccion["protocolo_hash"] == rp.hash_entrada(b)


def test_g3_hash_designado_de_ae70_sigue_una_ruta_anidada():
    vinculo = {"hash_declaracion": "2" * 64}
    p = rp.construir_protocolo(protocolo_id="s", estrategia=_estrategia({"clave_de_prueba": vinculo}), cortes=CORTES,
                               pendientes=[], sintetico=True)
    b = rp.serializar_entrada(p)
    t = "directo_en_campo_existente_no_previsto"
    ruta = ("estrategia", "parametros", "clave_de_prueba", "hash_declaracion")
    assert vv.hash_designado(t, b, rp.hash_entrada(b), vv.ReglaDeVinculo(t, ruta)) == "2" * 64


def test_g3_prediccion_con_protocolo_hash_alterado_se_rechaza():
    p = rp.construir_protocolo(protocolo_id="s", estrategia=_estrategia(), cortes=CORTES, pendientes=[],
                               sintetico=True)
    b = rp.serializar_entrada(p)
    prediccion = rp.nueva_prediccion(rp.validar_registro([b]), "BALOTO", 2714, sinteticos.historico(2081, 2713),
                                     PROBABILIDADES)
    with pytest.raises(rp.EntradaRegistroInvalidaError, match="protocolo distinto"):
        rp.validar_registro([b, rp.serializar_entrada({**prediccion, "protocolo_hash": "f" * 64})])


def test_g3_segundo_protocolo_en_el_registro_se_rechaza():
    p1 = rp.construir_protocolo(protocolo_id="s", estrategia=_estrategia({"a": 1}), cortes=CORTES, pendientes=[],
                                sintetico=True)
    p2 = rp.construir_protocolo(protocolo_id="s", estrategia=_estrategia({"a": 2}), cortes=CORTES, pendientes=[],
                                sintetico=True)
    b1 = rp.serializar_entrada(p1)
    with pytest.raises(rp.EntradaRegistroInvalidaError, match="segundo protocolo"):
        rp.validar_registro([b1, _segundo_protocolo(b1, p2)])


def test_g3_ausencia_marcador_y_estados_de_ae69_y_ae71():
    d = _elementos()
    del d[ELEMENTOS[0]]
    assert iv.comprobar_declaracion_sintetica(d) == "incompleta"
    assert aa.estado_verificable_de_elemento(d, ELEMENTOS[0]) == "ausente"
    marcada = _elementos()
    marcada[ELEMENTOS[0]] = {"estado": "declarado_sintetico", "valor": "TBD"}
    assert iv.comprobar_declaracion_sintetica(marcada) == "completa_sintetica_sin_autenticar"
    assert aa.estado_verificable_de_elemento(marcada, ELEMENTOS[0]) == "declarado_sintetico"


def test_g3_construir_protocolo_no_anade_claves_a_parametros():
    parametros = {"semilla": 1}
    p = rp.construir_protocolo(protocolo_id="s", estrategia=_estrategia(parametros), cortes=CORTES, pendientes=[],
                               sintetico=True)
    assert p["estrategia"]["parametros"] == {"semilla": 1}


def test_g3_protocolo_real_en_borrador_no_admite_predicciones():
    borrador = rp.construir_protocolo_borrador(_estrategia())
    estado = rp.validar_registro([rp.serializar_entrada(borrador)])
    assert estado.admite_salidas is False
    with pytest.raises(rp.EntradaRegistroInvalidaError):
        rp.nueva_prediccion(estado, "BALOTO", 2714, sinteticos.historico(2081, 2713), PROBABILIDADES)
