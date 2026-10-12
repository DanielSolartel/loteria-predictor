"""Fase 3 (cierre): aclaraciones de presentacion tras la revision de la interfaz
con el historico real en Windows. Solo cambia lo que se muestra; los
artefactos, sus huellas, versiones y fechas, y el contrato de la API no
cambian.

A. La ficha de una version distingue la evaluacion de SU receta de la lectura
   general del informe de procedencia (ganador, empate, uniforme mejor o
   comparacion incompleta), leida del informe guardado sin recalcular ni
   reordenar. Caso real revisado (Baloto, corte 2714): Logistica AE-36 0.35942
   primera, uniforme 0.35945 segunda, Random Forest 0.35947 tercera.
B. La ficha de un modelo Poisson no le atribuye una calibracion que no tiene;
   los clasificadores calibrados conservan la explicacion de sus etapas.
C. En `/resultados/colorloto`, los aciertos se rotulan como pares
   numero-color; los demas juegos conservan su etiqueta.
Datos sinteticos; nada es real."""
from __future__ import annotations

import hashlib
from collections import Counter

import pytest
from markupsafe import escape

from app.application.ml import laboratorio_modelos as lm
from app.application.ml import modelos_registrados as mr
from app.application.ml.pronostico_colorloto import coincidencias
from app.application.use_cases.laboratorio import LaboratorioError
from tests.unit import fixtures_fase3 as f3
from tests.unit import fixtures_producto6 as f6

RF = lm.CATALOGO["random_forest_clasificador"].nombre
AE36 = lm.CATALOGO["actual_logistica_ae36"].nombre


@pytest.fixture
def entorno(tmp_path):
    e = f3.entorno(tmp_path)
    yield e
    f3.limpiar()


def _arbol(raiz) -> dict:
    return {str(p.relative_to(raiz)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(raiz.rglob("*")) if p.is_file()}


class _InformeGuardado:
    def __init__(self, resumen: dict):
        self.artefacto = {"resumen": resumen}


def _resumen(estado: str, filas: list[tuple[str, str, float]], incompletos: tuple[str, ...] = ()) -> dict:
    return {"estado": estado, "criterio": "Log Loss agregado sobre la muestra comun (menor es mejor)",
            "ranking": [{"posicion": i, "id": id_, "nombre": nombre, "tipo": "-", "log_loss": ll,
                         "diferencia_log_loss": 0.0, "veredicto": "-"} for i, (id_, nombre, ll) in enumerate(filas, 1)],
            "incompletos": [{"id": x, "estado": "parcial", "incidencias": []} for x in incompletos]}


def _ficha(entorno, monkeypatch, informe=None, juego="BALOTO", modelo=None):
    """Registra una version y devuelve el HTML de su ficha. `informe`: resumen guardado que se le da a la
    ficha (o una excepcion); None = el informe real guardado. La ficha no escribe nada."""
    lab = entorno.laboratorio()
    r = entorno.registrar(lab, juego, modelo)
    if informe is not None:
        original = lab.experimento

        def experimento(clave):
            if clave != r["experimento"]:
                return original(clave)
            if isinstance(informe, Exception):
                raise informe
            return _InformeGuardado(informe)
        monkeypatch.setattr(lab, "experimento", experimento)
    c = f3.cliente(entorno, laboratorio=lab)
    antes = _arbol(entorno.directorio)
    respuesta = c.get(f"/laboratorio/modelo/{r['modelo_registrado']}")
    assert respuesta.status_code == 200
    assert _arbol(entorno.directorio) == antes  # GET de solo lectura: artefactos intactos
    return respuesta.text, r, lab


# ---------------------------------------------------------------------------
# A. Receta de la ficha frente al ganador del informe
# ---------------------------------------------------------------------------

def test_caso_real_la_ficha_no_presenta_como_suyo_el_ganador_del_informe(entorno, monkeypatch):
    informe = _resumen("menor_perdida_en_esta_evaluacion",
                       [("actual_logistica_ae36", AE36, 0.35942), ("uniforme", "Uniforme", 0.35945),
                        ("random_forest_clasificador", RF, 0.35947)])
    html, _, _ = _ficha(entorno, monkeypatch, informe)
    assert f"<strong>Esta receta, {RF}:</strong>" in html
    assert f"menor pérdida en esa evaluación: <strong>{AE36}</strong>, no esta receta." in html
    assert f"1. {AE36} — Log Loss 0.35942" in html and "2. Uniforme — Log Loss 0.35945" in html
    assert f'3. {RF} — Log Loss 0.35947 <span class="badge bg-primary">esta receta</span>' in html
    assert "Resumen del informe:" not in html  # el resumen general ya no aparece sin nombre


@pytest.mark.parametrize("estado, filas, incompletos, esperado", [
    ("la_uniforme_fue_mejor", [("uniforme", "Uniforme", 0.3594), ("random_forest_clasificador", RF, 0.3596)], (),
     "la <strong>uniforme</strong> tuvo la menor pérdida; ningún modelo la superó en esa evaluación."),
    ("empate", [("actual_logistica_ae36", AE36, 0.35945), ("uniforme", "Uniforme", 0.35945),
                ("random_forest_clasificador", RF, 0.35947)], (),
     f"empate en la primera posición entre <strong>{AE36}, Uniforme</strong>."),
    ("menor_perdida_en_esta_evaluacion", [("random_forest_clasificador", RF, 0.3590), ("uniforme", "Uniforme", 0.3594)],
     (), f"menor pérdida en esa evaluación: <strong>{RF}</strong> (esta receta)."),
    ("comparacion_incompleta", [("uniforme", "Uniforme", 0.3594)], ("random_forest_clasificador",),
     "comparación incompleta: no hay un modelo y la uniforme con evaluación completa para compararlos."),
])
def test_lectura_del_informe_en_cada_estado(entorno, monkeypatch, estado, filas, incompletos, esperado):
    html, _, _ = _ficha(entorno, monkeypatch, _resumen(estado, filas, incompletos))
    assert esperado in html
    assert f"<strong>Esta receta, {RF}:</strong>" in html
    if incompletos:
        assert "Sin evaluación completa en el informe: random_forest_clasificador (parcial)." in html


def test_informe_de_procedencia_no_disponible(entorno, monkeypatch):
    html, r, _ = _ficha(entorno, monkeypatch, LaboratorioError("no_encontrado", "No existe el experimento X"))
    assert "lectura general:</strong>" in html and "no disponible (No existe el experimento X)" in html
    assert f"<strong>Esta receta, {RF}:</strong>" in html  # la evaluacion guardada en la version sigue visible


def test_la_clasificacion_es_la_del_informe_guardado_sin_reordenar(entorno, monkeypatch):
    html, r, lab = _ficha(entorno, monkeypatch)
    ranking = lab.experimento(r["experimento"]).artefacto["resumen"]["ranking"]
    lista = html.split('ficha-clasificacion">', 1)[1].split("</ul>", 1)[0]
    filas = [x.split("</li>", 1)[0] for x in lista.split("<li>")[1:]]
    assert len(filas) == len(ranking) >= 2
    for fila, x in zip(filas, ranking):  # mismo orden, posiciones, nombres y Log Loss que el informe guardado
        assert fila.startswith(f"{x['posicion']}. {x['nombre']} — Log Loss {x['log_loss']:.5f}")
        assert ("esta receta" in fila) == (x["id"] == "random_forest_clasificador")
    guardada = lab.modelo(r["modelo_registrado"]).artefacto["procedencia"]["evaluacion"]["posicion_en_el_ranking"]
    assert [x["posicion"] for x in ranking if x["id"] == "random_forest_clasificador"] == [guardada]


# ---------------------------------------------------------------------------
# B. Calibracion: Poisson frente a clasificadores calibrados
# ---------------------------------------------------------------------------

def test_ficha_poisson_no_atribuye_una_calibracion_inexistente(entorno, monkeypatch):
    html, r, lab = _ficha(entorno, monkeypatch, juego="COLORLOTO", modelo="random_forest_poisson")
    assert "siempre antes de la calibración" not in html and "calibracion y parametros elegidos" not in html
    assert "siempre antes del corte; este modelo no tiene calibración" in html
    assert "estimador y parametros elegidos quedan congelados (no se reajustan); este modelo no tiene calibracion" in html
    assert "p = (lambda + delta) / suma por objetivo" in html
    assert "ninguna (conteos Poisson normalizados)" in html
    assert "El manifiesto guarda el texto común del contrato" in html
    guardado = lab.modelo(r["modelo_registrado"]).artefacto
    assert guardado["contrato_de_inferencia"] == mr.CONTRATO_DE_INFERENCIA  # el artefacto no cambia
    assert [c["paso"] for c in guardado["componentes"]] == ["preparacion_de_variables", "estimador"]


def test_ficha_de_un_clasificador_calibrado_conserva_sus_etapas(entorno, monkeypatch):
    html, r, lab = _ficha(entorno, monkeypatch)
    assert "siempre antes de la calibración y del corte" in html
    assert str(escape(mr.CONTRATO_DE_INFERENCIA)) in html  # contrato tal como se guardo (escapado en HTML)
    assert "El manifiesto guarda el texto común del contrato" not in html
    assert "<strong>calibración</strong>:" in html  # el paso de calibracion sigue entre los componentes


# ---------------------------------------------------------------------------
# C. Unidad de los aciertos de ColorLoto en Resultados
# ---------------------------------------------------------------------------

def test_caso_real_221_los_aciertos_son_pares_numero_color():
    sugerencia = [(3, "BLANCO"), (4, "ROJO"), (5, "NEGRO"), (6, "ROJO"), (7, "AMARILLO"), (7, "ROJO")]
    resultado = [(2, "AMARILLO"), (3, "AZUL"), (4, "AZUL"), (7, "ROJO"), (5, "BLANCO"), (6, "BLANCO")]
    assert coincidencias(sugerencia, resultado) == 1  # lo que muestra Resultados: 1 de 6 pares
    numeros = sum((Counter(n for n, _ in sugerencia) & Counter(n for n, _ in resultado)).values())
    colores = sum((Counter(c for _, c in sugerencia) & Counter(c for _, c in resultado)).values())
    assert (numeros, colores) == (5, 3)  # otras intersecciones, con su propio denominador; no se muestran ahi


@pytest.fixture
def resultados(tmp_path):
    e = f6.entorno(tmp_path)
    e.poblar(("MILOTO", "COLORLOTO"))
    e.llega_el_resultado("COLORLOTO")
    e.llega_el_resultado("MILOTO")
    yield e
    f6.limpiar()


def test_resultados_de_colorloto_rotulan_los_aciertos_como_pares(resultados):
    c = f6.cliente(resultados)
    api_antes = c.get("/api/resultados/COLORLOTO").json()
    html = c.get("/resultados/colorloto").text
    assert "Aciertos medios (pares número-color)" in html and "Aciertos (pares número-color)" in html
    nota = '<p class="small mb-1 resumen-unidad-aciertos">En ColorLoto, los aciertos son <strong>pares número-color'
    assert nota in html  # visible encima de la tabla, no en su leyenda desplazable
    assert "«Aciertos» cuenta <strong>pares número-color</strong>" in html
    filas = [f for f in api_antes["historial"]["filas"] if f.get("aciertos") is not None]
    assert filas and all(f"{f['aciertos']} de {f['de']} pares" in html for f in filas)
    assert c.get("/api/resultados/COLORLOTO").json() == api_antes  # mismo contrato y mismos valores


def test_los_demas_juegos_conservan_su_etiqueta(resultados):
    c = f6.cliente(resultados)
    html = c.get("/resultados/miloto").text
    assert "Aciertos medios</th>" in html and ">Aciertos</th>" in html
    assert "pares número-color" not in html
