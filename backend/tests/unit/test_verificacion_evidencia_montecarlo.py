"""Tests de `scripts/verificacion_evidencia_montecarlo.py` -Etapa AE-50,
validada: validacion de formato y coherencia interna de una
evidencia JSON de AE-49. No es prueba de autenticidad ni de
procedencia. Todo sintetico: evidencia construida con la funcion real
`construir_reporte` de AE-49, sin simular y sin PostgreSQL."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from app.application.simulaciones import montecarlo_uniforme as mc
from app.application.use_cases.simular_referencia_azar_uniforme import SimularReferenciaAzarUniforme
from scripts import verificacion_evidencia_montecarlo as verif
from scripts.comparacion_estado_prediccion import serializar_reporte
from tests.unit.simulaciones import evidencia_sintetica as ev
from tests.unit.simulaciones import sinteticos

ARCHIVO = Path(verif.__file__)


def _mutar(funcion) -> bytes:
    reporte = ev.copia(ev.reporte_valido())
    funcion(reporte)
    return ev.recodificar(reporte)


def _estadistica(reporte, juego=0, indice=0):
    return reporte["juegos"][juego]["estadisticas"][indice]


# ---------------------------------------------------------------------------
# Evidencia valida
# ---------------------------------------------------------------------------

class TestEvidenciaValida:
    def test_acepta_y_resume_sin_valores_estadisticos(self):
        contenido = ev.evidencia_valida()
        resumen = verif.validar_evidencia(contenido)
        assert resumen == {
            "sha256": hashlib.sha256(contenido).hexdigest(),
            "bytes": len(contenido),
            "juegos": [
                {"codigo": "BALOTO", "entrada_sha256": ev.HUELLA_BALOTO},
                {"codigo": "BALOTO_REVANCHA", "entrada_sha256": ev.HUELLA_REVANCHA},
            ],
        }

    def test_incluye_un_caso_que_supera_el_umbral_exploratorio(self):
        reporte = ev.reporte_valido()
        banderas = [e["supera_umbral_exploratorio"] for j in reporte["juegos"] for e in j["estadisticas"]]
        assert True in banderas and False in banderas
        verif.validar_evidencia(ev.evidencia_valida())

    def test_huellas_de_entrada_iguales_entre_juegos_no_se_exigen_distintas(self):
        verif.validar_evidencia(ev.evidencia_valida(huella_revancha=ev.HUELLA_BALOTO))

    def test_cualquier_revision_alembic_no_vacia_es_valida(self):
        verif.validar_evidencia(ev.evidencia_valida(revision="0007"))

    def test_determinista(self):
        contenido = ev.evidencia_valida()
        assert verif.validar_evidencia(contenido) == verif.validar_evidencia(contenido)


@pytest.fixture(scope="module")
def evidencia_real_b20():
    """Evidencia generada por el caso de uso real de AE-49 (repositorios
    fake con historicos sinteticos, B = 20). El verificador no ejecuta
    Monte Carlo: esta evidencia solo sirve para comprobar que la
    reconstruccion de p, percentil y Bonferroni coincide con lo que AE-49
    serializa de verdad."""
    caso = SimularReferenciaAzarUniforme(sinteticos.JuegoRepositoryFake(), sinteticos.ResultadosRepositoryFake(),
                                         iteraciones=20)
    return serializar_reporte(caso.ejecutar("0006"))


class TestCoherenciaConLaSerializacionRealDeAe49:
    def test_con_b_pequeno_falla_solo_por_parametros(self, evidencia_real_b20):
        with pytest.raises(verif.EvidenciaInvalidaError, match="parametros"):
            verif.validar_evidencia(evidencia_real_b20)

    def test_misma_evidencia_es_coherente_con_sus_propios_parametros(self, evidencia_real_b20):
        reporte = json.loads(evidencia_real_b20)
        verif._validar_reporte(reporte, evidencia_real_b20, semilla=mc.SEMILLA_AE49, iteraciones=20)


# ---------------------------------------------------------------------------
# Codigo 3: ilegible
# ---------------------------------------------------------------------------

class TestIlegible:
    @pytest.mark.parametrize("contenido", [
        b"", b"{no es json", "á".encode("latin-1"), b"\xff\xfe{}",
    ])
    def test_no_utf8_o_no_json(self, contenido):
        with pytest.raises(verif.EvidenciaIlegibleError):
            verif.validar_evidencia(contenido)

    @pytest.mark.parametrize("constante", [b"NaN", b"Infinity", b"-Infinity"])
    def test_rechaza_constantes_no_estandar_al_leer(self, constante):
        texto = ev.evidencia_valida()
        valor = json.dumps(_estadistica(ev.reporte_valido())["media_simulada"]).encode()
        mutado = texto.replace(b'"media_simulada": ' + valor, b'"media_simulada": ' + constante, 1)
        assert mutado != texto
        with pytest.raises(verif.EvidenciaIlegibleError, match="no estandar"):
            verif.validar_evidencia(mutado)


# ---------------------------------------------------------------------------
# Codigo 4: estructura, textos, constantes, tipos y finitud
# ---------------------------------------------------------------------------

MUTACIONES_INVALIDAS = {
    "raiz_vacia": lambda r: r.clear(),
    "clave_extra_raiz": lambda r: r.update(extra=1),
    "clave_faltante_raiz": lambda r: r.pop("nota"),
    "esquema": lambda r: r.update(esquema="simulacion-azar-uniforme/2.0"),
    "caracter": lambda r: r.update(caracter="confirmatorio"),
    "nota_alterada": lambda r: r.update(nota=r["nota"] + " recomendamos jugar"),
    "revision_vacia": lambda r: r.update(alembic_revision=""),
    "revision_no_texto": lambda r: r.update(alembic_revision=6),
    "semilla_distinta": lambda r: r["parametros"].update(semilla=1),
    "iteraciones_distintas": lambda r: r["parametros"].update(iteraciones=20),
    "generador_distinto": lambda r: r["parametros"].update(generador="otro"),
    "estadisticas_desordenadas": lambda r: r["parametros"]["estadisticas"].reverse(),
    "rango_distinto": lambda r: r["rango_principal"].update(desde=2080),
    "tramos_alterados": lambda r: r["rango_principal"].update(tramos="2706 es holdout ciego"),
    "familia_de_cuatro": lambda r: r["familia_comparaciones"].update(tamano=4),
    "alpha_distinto": lambda r: r["familia_comparaciones"].update(alpha=0.1),
    "cobertura_alterada": lambda r: r["familia_comparaciones"].update(cobertura="controla todo el proceso"),
    "juegos_desordenados": lambda r: r["juegos"].reverse(),
    "juego_faltante": lambda r: r["juegos"].pop(),
    "clave_extra_juego": lambda r: r["juegos"][0].update(probabilidades={}),
    "total_sorteos_624": lambda r: r["juegos"][0].update(total_sorteos=624),
    "transiciones_625": lambda r: r["juegos"][0].update(total_transiciones=625),
    "superbalotas_bool": lambda r: r["juegos"][0].update(total_superbalotas=True),
    "huella_mayusculas": lambda r: r["juegos"][0].update(entrada_sha256=ev.HUELLA_BALOTO.upper()),
    "huella_corta": lambda r: r["juegos"][0].update(entrada_sha256="abc"),
    "estadisticas_desordenadas_juego": lambda r: r["juegos"][0]["estadisticas"].reverse(),
    "clave_extra_estadistica": lambda r: _estadistica(r).update(combinacion=[1, 2, 3, 4, 5]),
    "significativo_en_vez_de_supera": lambda r: _estadistica(r).update(
        significativo=_estadistica(r).pop("supera_umbral_exploratorio")),
    "supera_no_bool": lambda r: _estadistica(r).update(supera_umbral_exploratorio=1),
    "rango_observado_float": lambda r: _estadistica(r, indice=1).update(observado=31.0),
    "dispersion_observado_entero": lambda r: _estadistica(r).update(observado=37),
    "referencia_alterada": lambda r: _estadistica(r).update(referencia_analitica=42.0),
    "referencia_del_rango_no_nula": lambda r: _estadistica(r, indice=1).update(referencia_analitica=0.0),
    "media_negativa": lambda r: _estadistica(r).update(media_simulada=-1.0),
    "desviacion_negativa": lambda r: _estadistica(r).update(desviacion_simulada=-0.5),
    "p_mayor_que_uno": lambda r: _estadistica(r).update(p_valor_empirico=1.5),
    "p_cero": lambda r: _estadistica(r).update(p_valor_empirico=0.0),
    "percentil_fuera_de_rango": lambda r: _estadistica(r).update(percentil_observado=1.2),
}


class TestInvalida:
    @pytest.mark.parametrize("nombre", list(MUTACIONES_INVALIDAS))
    def test_mutacion_rechazada_con_codigo_4(self, nombre):
        with pytest.raises(verif.EvidenciaInvalidaError):
            verif.validar_evidencia(_mutar(MUTACIONES_INVALIDAS[nombre]))

    def test_raiz_que_no_es_objeto(self):
        with pytest.raises(verif.EvidenciaInvalidaError):
            verif.validar_evidencia(b"[]\n")

    def test_numero_que_desborda_a_infinito(self):
        contenido = _mutar(lambda r: _estadistica(r).update(media_simulada=1.0)).replace(
            b'"media_simulada": 1.0', b'"media_simulada": 1e999', 1)
        with pytest.raises(verif.EvidenciaInvalidaError, match="finito"):
            verif.validar_evidencia(contenido)

    def test_clave_duplicada(self):
        contenido = ev.evidencia_valida().replace(b'"esquema": ', b'"esquema": "x", "esquema": ', 1)
        with pytest.raises(verif.EvidenciaInvalidaError, match="duplicada"):
            verif.validar_evidencia(contenido)

    def test_texto_que_recomienda_fuera_del_disclaimer(self):
        with pytest.raises(verif.EvidenciaInvalidaError):
            verif.validar_evidencia(_mutar(lambda r: r["familia_comparaciones"].update(
                cobertura=r["familia_comparaciones"]["cobertura"] + " Recomendacion: jugar.")))


# ---------------------------------------------------------------------------
# Codigo 5: coherencia interna y forma canonica
# ---------------------------------------------------------------------------

class TestIncoherente:
    @pytest.mark.parametrize("nombre, transformar", [
        ("espacio_extra", lambda b: b.replace(b"{\n", b"{ \n", 1)),
        ("fin_de_linea_crlf", lambda b: b.replace(b"\n", b"\r\n")),
        ("sin_salto_final", lambda b: b[:-1]),
        ("claves_sin_ordenar", lambda b: (json.dumps(dict(reversed(list(json.loads(b).items()))), indent=2,
                                                     ensure_ascii=False) + "\n").encode()),
        ("indentacion_distinta", lambda b: (json.dumps(json.loads(b), indent=4, sort_keys=True,
                                                       ensure_ascii=False) + "\n").encode()),
    ])
    def test_forma_no_canonica(self, nombre, transformar):
        mutado = transformar(ev.evidencia_valida())
        assert mutado != ev.evidencia_valida()
        with pytest.raises(verif.EvidenciaIncoherenteError, match="canonica"):
            verif.validar_evidencia(mutado)

    @pytest.mark.parametrize("nombre, mutar", [
        ("p_no_alcanzable", lambda r: _estadistica(r).update(p_valor_empirico=0.003)),
        ("percentil_no_multiplo", lambda r: _estadistica(r).update(percentil_observado=0.123456789)),
        ("p_y_percentil_incompatibles", lambda r: _estadistica(r).update(percentil_observado=0.5)),
        ("supera_invertido", lambda r: _estadistica(r, indice=2).update(
            supera_umbral_exploratorio=not _estadistica(r, indice=2)["supera_umbral_exploratorio"])),
        ("ajustado_igual_al_crudo", lambda r: _estadistica(r).update(
            p_valor_ajustado_bonferroni=_estadistica(r)["p_valor_empirico"])),
    ])
    def test_incoherencia_interna_codigo_5(self, nombre, mutar):
        with pytest.raises(verif.EvidenciaIncoherenteError):
            verif.validar_evidencia(_mutar(mutar))

    def test_umbral_depende_de_la_familia_de_ocho(self):
        # p crudo 22/10001: ajustado 8·p ~ 0.0176 supera; con 4 seria ~0.0088 y tambien.
        # Se comprueba que un ajustado recalculado con 4 comparaciones se rechaza.
        def con_cuatro(r):
            e = _estadistica(r, indice=2)
            e["p_valor_ajustado_bonferroni"] = min(1.0, e["p_valor_empirico"] * 4)

        with pytest.raises(verif.EvidenciaIncoherenteError):
            verif.validar_evidencia(_mutar(con_cuatro))


# ---------------------------------------------------------------------------
# Informe de salida
# ---------------------------------------------------------------------------

class TestInforme:
    def test_un_archivo(self):
        resumen = verif.validar_evidencia(ev.evidencia_valida())
        informe = verif.construir_informe([resumen])
        assert informe == {
            "esquema": "verificacion-evidencia-montecarlo/1.0",
            "resultado": "formato_y_coherencia_interna_validos",
            "archivos": [{"sha256": resumen["sha256"], "bytes": resumen["bytes"]}],
            "comparacion_de_archivos": "no_aplica",
            "juegos": resumen["juegos"],
            "comprobaciones": list(verif.COMPROBACIONES),
            "alcance": verif.ALCANCE_VERIFICACION,
        }

    def test_dos_archivos_identicos_segun_la_comparacion_de_bytes(self):
        resumen = verif.validar_evidencia(ev.evidencia_valida())
        informe = verif.construir_informe([resumen, resumen], bytes_identicos=True)
        assert informe["comparacion_de_archivos"] == "archivos_identicos"
        assert len(informe["archivos"]) == 2

    def test_dos_archivos_distintos_no_se_informan(self):
        a = verif.validar_evidencia(ev.evidencia_valida())
        b = verif.validar_evidencia(ev.evidencia_valida(revision="0007"))
        with pytest.raises(ValueError):
            verif.construir_informe([a, b], bytes_identicos=False)

    def test_regresion_la_misma_huella_no_basta_para_declarar_identicos(self):
        # Dos resumenes con el mismo SHA-256 no autorizan `archivos_identicos`:
        # solo lo hace la comparacion efectiva de bytes (`bytes_identicos=True`).
        resumen = verif.validar_evidencia(ev.evidencia_valida())
        with pytest.raises(ValueError, match="bytes"):
            verif.construir_informe([resumen, resumen])
        with pytest.raises(ValueError, match="bytes"):
            verif.construir_informe([resumen, dict(resumen)], bytes_identicos=False)

    @pytest.mark.parametrize("valor", [1, "si", 0])
    def test_bytes_identicos_debe_ser_booleano_estricto(self, valor):
        resumen = verif.validar_evidencia(ev.evidencia_valida())
        with pytest.raises(ValueError):
            verif.construir_informe([resumen, resumen], bytes_identicos=valor)

    def test_un_archivo_no_admite_comparacion(self):
        resumen = verif.validar_evidencia(ev.evidencia_valida())
        with pytest.raises(ValueError):
            verif.construir_informe([resumen], bytes_identicos=True)

    def test_alcance_niega_autenticidad_procedencia_y_reproducibilidad(self):
        texto = verif.ALCANCE_VERIFICACION
        for fragmento in ("formato y coherencia interna", "no es prueba de autenticidad ni de procedencia",
                          "un archivo fabricado", "no confirma que los datos provengan de PostgreSQL",
                          "no recalcula las estadisticas", "no demuestra por si sola la reproducibilidad",
                          "exploratoria", "no modifica el NO-GO de AE-39"):
            assert fragmento in texto, fragmento

    def test_informe_sin_valores_estadisticos(self):
        resumen = verif.validar_evidencia(ev.evidencia_valida())
        informe = verif.construir_informe([resumen])

        def claves(nodo):
            if isinstance(nodo, dict):
                for clave, valor in nodo.items():
                    yield clave
                    yield from claves(valor)
            elif isinstance(nodo, list):
                for valor in nodo:
                    yield from claves(valor)

        todas = set(claves(informe))
        assert todas == {"esquema", "resultado", "archivos", "sha256", "bytes", "comparacion_de_archivos",
                         "juegos", "codigo", "entrada_sha256", "comprobaciones", "alcance"}
        texto = json.dumps(informe)
        for valor in ("38.01", "0.0021997800219978", "supera_umbral_exploratorio\":"):
            assert valor not in texto, valor


# ---------------------------------------------------------------------------
# Estructura
# ---------------------------------------------------------------------------

def _importaciones(ruta: Path):
    salida = []
    for nodo in ast.walk(ast.parse(ruta.read_text(encoding="utf-8"))):
        if isinstance(nodo, ast.Import):
            salida.extend(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            salida.append(nodo.module or "")
    return salida


def test_modulo_sin_bd_ml_ni_escritura():
    for modulo in _importaciones(ARCHIVO):
        assert modulo.split(".")[0] not in {"sqlalchemy", "sklearn", "numpy"}, modulo
        assert not modulo.startswith(("app.infrastructure", "app.application.ml")), modulo
    texto = ARCHIVO.read_text(encoding="utf-8")
    for prohibido in ("open(", "engine", "connect(", "commit(", "resolver_estado_prediccion",
                      "diagnostico_bloqueo", "diagnosticar_estado_prediccion"):
        assert prohibido not in texto, prohibido


def test_reutiliza_constantes_y_bonferroni_existentes():
    texto = ARCHIVO.read_text(encoding="utf-8")
    for nombre in ("SEMILLA_AE49", "ITERACIONES_AE49", "RANGO_PRINCIPAL_AE49", "NOTA_AE49", "TEXTO_TRAMOS",
                   "COBERTURA_AJUSTE", "FRASES_NEGATIVAS_DISCLAIMER", "aplicar_correccion_bonferroni",
                   "serializar_reporte", "CLAVES_PREDICTIVAS"):
        assert nombre in texto, nombre
