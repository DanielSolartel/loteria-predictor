"""Tests de `scripts/registro_prospectivo_ml.py` -Etapa AE-52,
validada: CLI local, sin conexion a la base de datos, que inicia un
registro con el protocolo en borrador y verifica registros; y
`anexar_entrada`, que escribe cada entrada en un archivo nuevo sin
sobrescribir nunca. Todo sintetico en `tmp_path`: sin PostgreSQL, sin
datos reales y sin predicciones reales."""
from __future__ import annotations

import hashlib
import inspect
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from app.application.ml import registro_prospectivo as rp
from app.application.ml.modelo import (
    NOMBRES_FEATURES,
    SEMILLA_DEFECTO,
    VERSION_SKLEARN,
    construir_pipeline,
    entrenar_modelo_calibrado,
)
from scripts import registro_prospectivo_ml as cli
from scripts.comparacion_estado_prediccion import EscrituraEvidenciaError
from tests.unit.simulaciones import sinteticos

RAIZ_BACKEND = Path(cli.__file__).resolve().parents[1]
PATRON_SHA = "SHA-256 "


def _estrategia_sintetica():
    return {
        "nombre": "estrategia_sintetica", "descripcion": "solo pruebas", "huella_codigo": "c" * 64,
        "archivos_codigo": ["sintetico.py"], "parametros": {"semilla": 1},
        "entorno": {"python": "3.x", "scikit_learn": "0.0"},
    }


def _registro_sintetico(directorio: Path, con_resultado=True) -> Path:
    directorio.mkdir(exist_ok=True)
    cli.anexar_entrada(directorio, rp.construir_protocolo(
        protocolo_id="sintetico-cli", estrategia=_estrategia_sintetica(),
        cortes={"BALOTO": 2713, "BALOTO_REVANCHA": 2713}, pendientes=[], sintetico=True,
    ))
    estado = cli.leer_registro(directorio)
    cli.anexar_entrada(directorio, rp.nueva_prediccion(
        estado, "BALOTO", 2714, sinteticos.historico(2081, 2713), [0.1] * 43))
    if con_resultado:
        cli.anexar_entrada(directorio, rp.nuevo_resultado(cli.leer_registro(directorio), "BALOTO", 2714, (1, 2, 3, 4, 5)))
    return directorio


def _huellas(directorio: Path):
    return {p.name: (hashlib.sha256(p.read_bytes()).hexdigest(), os.stat(p).st_mtime_ns)
            for p in sorted(directorio.iterdir())}


# ---------------------------------------------------------------------------
# Estrategia candidata y huella del codigo
# ---------------------------------------------------------------------------

class TestEstrategiaCandidata:
    def test_parametros_leidos_del_codigo_validado_de_ae36(self):
        estrategia = cli.estrategia_candidata_ae36()
        parametros = construir_pipeline().get_params()
        assert estrategia["nombre"] == "regresion_logistica_calibrada_ae36"
        assert estrategia["parametros"] == {
            "semilla": SEMILLA_DEFECTO, "nombres_features": list(NOMBRES_FEATURES),
            "C": parametros["clf__C"], "solver": parametros["clf__solver"], "max_iter": parametros["clf__max_iter"],
            "proporcion_calibracion": inspect.signature(entrenar_modelo_calibrado).parameters[
                "proporcion_calibracion"].default,
            "periodo_calentamiento_minimo": 50, "tamanos_ventana": [10, 20, 50],
            "salida": "probabilidad_de_aparicion_por_numero_del_rango",
        }
        assert estrategia["entorno"]["scikit_learn"] == VERSION_SKLEARN
        assert estrategia["archivos_codigo"] == list(cli.ARCHIVOS_ESTRATEGIA_AE36)
        assert estrategia["huella_codigo"] == cli.huella_codigo(RAIZ_BACKEND, cli.ARCHIVOS_ESTRATEGIA_AE36)

    def test_huella_de_codigo_independiente_del_fin_de_linea(self, tmp_path):
        (tmp_path / "a.py").write_bytes(b"x = 1\ny = 2\n")
        lf = cli.huella_codigo(tmp_path, ["a.py"])
        (tmp_path / "a.py").write_bytes(b"x = 1\r\ny = 2\r\n")
        assert cli.huella_codigo(tmp_path, ["a.py"]) == lf
        (tmp_path / "a.py").write_bytes(b"x = 1\ny = 3\n")
        assert cli.huella_codigo(tmp_path, ["a.py"]) != lf

    def test_huella_incluye_la_ruta_y_el_orden(self, tmp_path):
        (tmp_path / "a.py").write_bytes(b"1\n")
        (tmp_path / "b.py").write_bytes(b"1\n")
        assert cli.huella_codigo(tmp_path, ["a.py"]) != cli.huella_codigo(tmp_path, ["b.py"])
        assert cli.huella_codigo(tmp_path, ["a.py", "b.py"]) == cli.huella_codigo(tmp_path, ["b.py", "a.py"])


# ---------------------------------------------------------------------------
# iniciar-borrador
# ---------------------------------------------------------------------------

class TestIniciarBorrador:
    def test_crea_la_primera_entrada_sin_sobrescribir(self, tmp_path, capsysbinary):
        directorio = tmp_path / "registro"
        directorio.mkdir()
        assert cli.main(["iniciar-borrador", str(directorio)]) == cli.EXIT_OK == 0
        salida = capsysbinary.readouterr()
        archivo = directorio / "000001.json"
        assert sorted(p.name for p in directorio.iterdir()) == ["000001.json"]
        assert salida.out == archivo.read_bytes()
        assert hashlib.sha256(archivo.read_bytes()).hexdigest().encode() in salida.err
        protocolo = json.loads(archivo.read_bytes())
        assert protocolo["tipo"] == "protocolo" and protocolo["pendientes"] == list(rp.PENDIENTES_BORRADOR_AE52)
        assert protocolo["estrategia"] == cli.estrategia_candidata_ae36()
        assert protocolo["sintetico"] is False

    def test_directorio_no_vacio_o_inexistente_codigo_9(self, tmp_path, capsysbinary):
        directorio = tmp_path / "registro"
        directorio.mkdir()
        (directorio / "000001.json").write_bytes(b"previo")
        antes = _huellas(directorio)
        assert cli.main(["iniciar-borrador", str(directorio)]) == cli.EXIT_RUTA_NO_PERMITIDA == 9
        assert _huellas(directorio) == antes
        assert cli.main(["iniciar-borrador", str(tmp_path / "no-existe")]) == 9
        assert capsysbinary.readouterr().out == b""

    def test_archivo_que_aparece_antes_de_publicar_codigo_8(self, tmp_path, capsysbinary, monkeypatch):
        from scripts import comparacion_estado_prediccion as escritor

        directorio = tmp_path / "registro"
        directorio.mkdir()
        publicar_real = escritor._publicar_exclusivo

        def intruso(temporal, destino):
            Path(destino).write_bytes(b"escrito por otro proceso")
            publicar_real(temporal, destino)

        monkeypatch.setattr(escritor, "_publicar_exclusivo", intruso)
        assert cli.main(["iniciar-borrador", str(directorio)]) == cli.EXIT_FALLO_ESCRITURA == 8
        assert (directorio / "000001.json").read_bytes() == b"escrito por otro proceso"
        assert capsysbinary.readouterr().out == b""


# ---------------------------------------------------------------------------
# anexar_entrada: solo anexa, nunca sobrescribe
# ---------------------------------------------------------------------------

class TestAnexar:
    def test_una_entrada_por_archivo_nuevo(self, tmp_path):
        directorio = _registro_sintetico(tmp_path / "registro")
        assert sorted(p.name for p in directorio.iterdir()) == ["000001.json", "000002.json", "000003.json"]
        estado = cli.leer_registro(directorio)
        assert estado.tipos == ("protocolo", "prediccion", "resultado")
        assert estado.cabeza == hashlib.sha256((directorio / "000003.json").read_bytes()).hexdigest()

    def test_entrada_invalida_no_escribe_nada(self, tmp_path):
        directorio = _registro_sintetico(tmp_path / "registro")
        antes = _huellas(directorio)
        with pytest.raises(rp.EntradaRegistroInvalidaError):
            cli.anexar_entrada(directorio, rp.nueva_prediccion(
                cli.leer_registro(directorio), "BALOTO", 2714, sinteticos.historico(2081, 2713), [0.1] * 43))
        assert _huellas(directorio) == antes

    def test_nunca_sobrescribe_un_archivo_existente(self, tmp_path):
        directorio = _registro_sintetico(tmp_path / "registro", con_resultado=False)
        estado = cli.leer_registro(directorio)
        siguiente = rp.nuevo_resultado(estado, "BALOTO", 2714, (1, 2, 3, 4, 5))
        (directorio / "000003.json").write_bytes(b"ocupado")
        antes = _huellas(directorio)
        with pytest.raises((EscrituraEvidenciaError, rp.CadenaRegistroInconsistenteError, rp.RegistroIlegibleError)):
            cli.anexar_entrada(directorio, siguiente)
        assert _huellas(directorio) == antes

    def test_archivo_que_aparece_entre_la_validacion_y_la_escritura_no_se_sobrescribe(self, tmp_path, monkeypatch):
        from scripts import comparacion_estado_prediccion as escritor

        directorio = _registro_sintetico(tmp_path / "registro", con_resultado=False)
        siguiente = rp.nuevo_resultado(cli.leer_registro(directorio), "BALOTO", 2714, (1, 2, 3, 4, 5))
        publicar_real = escritor._publicar_exclusivo

        def intruso(temporal, destino):
            Path(destino).write_bytes(b"escrito por otro proceso")
            publicar_real(temporal, destino)

        monkeypatch.setattr(escritor, "_publicar_exclusivo", intruso)
        with pytest.raises((EscrituraEvidenciaError, rp.RegistroProspectivoError)):
            cli.anexar_entrada(directorio, siguiente)
        assert (directorio / "000003.json").read_bytes() == b"escrito por otro proceso"
        assert sorted(p.name for p in directorio.iterdir()) == ["000001.json", "000002.json", "000003.json"]

    def test_entrada_construida_sobre_un_estado_anterior_se_rechaza(self, tmp_path):
        directorio = _registro_sintetico(tmp_path / "registro", con_resultado=False)
        estado_viejo = cli.leer_registro(directorio)
        cli.anexar_entrada(directorio, rp.nuevo_resultado(estado_viejo, "BALOTO", 2714, (1, 2, 3, 4, 5)))
        antes = _huellas(directorio)
        with pytest.raises((rp.CadenaRegistroInconsistenteError, rp.EntradaRegistroInvalidaError)):
            cli.anexar_entrada(directorio, rp.nuevo_resultado(estado_viejo, "BALOTO", 2714, (6, 7, 8, 9, 10)))
        assert _huellas(directorio) == antes

    def test_temporal_de_una_publicacion_en_curso_no_bloquea_el_anexado(self, tmp_path):
        directorio = _registro_sintetico(tmp_path / "registro", con_resultado=False)
        (directorio / ".evidencia-ae48-abc_123.tmp").write_bytes(b"publicacion en curso de otro proceso")
        estado = cli.leer_registro(directorio)
        assert estado.total == 2
        ruta = cli.anexar_entrada(directorio, rp.nuevo_resultado(estado, "BALOTO", 2714, (1, 2, 3, 4, 5)))
        assert ruta.name == "000003.json"
        assert cli.leer_registro(directorio).total == 3


# ---------------------------------------------------------------------------
# Anexado concurrente: dos operaciones que leen la misma cabeza
# ---------------------------------------------------------------------------

def _dos_entradas_sobre_la_misma_cabeza(directorio: Path):
    """Registro con protocolo (1) y prediccion de 2714 (2). Desde la
    misma cabeza se construyen dos entradas distintas con secuencia 3:
    la prediccion de 2715 y el resultado de 2714."""
    _registro_sintetico(directorio, con_resultado=False)
    estado = cli.leer_registro(directorio)
    prediccion = rp.nueva_prediccion(estado, "BALOTO", 2715, sinteticos.historico(2081, 2714), [0.1] * 43)
    resultado = rp.nuevo_resultado(estado, "BALOTO", 2714, (1, 2, 3, 4, 5))
    assert prediccion["secuencia"] == resultado["secuencia"] == 3
    assert prediccion["hash_anterior"] == resultado["hash_anterior"] == estado.cabeza
    return prediccion, resultado


class TestAnexadoConcurrente:
    def test_la_otra_operacion_publica_entre_la_lectura_y_la_escritura(self, tmp_path, monkeypatch):
        directorio = tmp_path / "registro"
        prediccion, resultado = _dos_entradas_sobre_la_misma_cabeza(directorio)
        escribir_real = cli.escribir_evidencia_atomica

        def la_otra_operacion_publica_antes(contenido, ruta):
            monkeypatch.setattr(cli, "escribir_evidencia_atomica", escribir_real)
            cli.anexar_entrada(directorio, resultado)
            return escribir_real(contenido, ruta)

        monkeypatch.setattr(cli, "escribir_evidencia_atomica", la_otra_operacion_publica_antes)
        try:
            cli.anexar_entrada(directorio, prediccion)
            error = None
        except Exception as capturado:  # noqa: BLE001 -se comprueba el tipo abajo
            error = capturado
        nombres = sorted(p.name for p in directorio.iterdir())
        assert error is not None, f"las dos operaciones avanzaron la cadena: {nombres}"
        assert type(error).__name__ == "SecuenciaOcupadaError", repr(error)
        assert isinstance(error, rp.RegistroProspectivoError) and error.codigo_salida == cli.EXIT_FALLO_ESCRITURA
        assert nombres == ["000001.json", "000002.json", "000003.json"]
        estado = cli.leer_registro(directorio)
        assert estado.total == 3 and estado.tipos[-1] == "resultado"
        assert (directorio / "000003.json").read_bytes() == rp.serializar_entrada(resultado)

    def test_dos_procesos_con_la_misma_cabeza_solo_uno_avanza(self, tmp_path):
        directorio = tmp_path / "registro"
        entradas = dict(zip(("prediccion", "resultado"), _dos_entradas_sobre_la_misma_cabeza(directorio)))
        hijo = tmp_path / "hijo.py"
        hijo.write_text(textwrap.dedent("""
            import json, sys, time
            from pathlib import Path
            from app.application.ml import registro_prospectivo as rp
            from scripts import registro_prospectivo_ml as cli

            directorio, archivo_entrada, propia, ajena = map(Path, sys.argv[1:5])
            entrada = json.loads(archivo_entrada.read_bytes())
            escribir_real = cli.escribir_evidencia_atomica

            def escribir_cuando_ambos_leyeron(contenido, ruta):
                propia.touch()
                limite = time.monotonic() + 60
                while not ajena.exists():
                    if time.monotonic() > limite:
                        sys.exit(90)
                    time.sleep(0.01)
                return escribir_real(contenido, ruta)

            cli.escribir_evidencia_atomica = escribir_cuando_ambos_leyeron
            try:
                ruta = cli.anexar_entrada(directorio, entrada)
            except rp.RegistroProspectivoError as error:
                print(type(error).__name__)
                sys.exit(error.codigo_salida)
            print("publicado " + ruta.name)
        """), encoding="utf-8")
        senales = {tipo: tmp_path / f"leyo-{tipo}" for tipo in entradas}
        procesos = {}
        for tipo, entrada in entradas.items():
            archivo = tmp_path / f"{tipo}.json"
            archivo.write_bytes(rp.serializar_entrada(entrada))
            otro = "resultado" if tipo == "prediccion" else "prediccion"
            procesos[tipo] = subprocess.Popen(
                [sys.executable, str(hijo), str(directorio), str(archivo), str(senales[tipo]), str(senales[otro])],
                cwd=RAIZ_BACKEND, env={**os.environ, "PYTHONPATH": str(RAIZ_BACKEND)},
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        salidas = {tipo: (*p.communicate(timeout=180), p.returncode) for tipo, p in procesos.items()}
        codigos = sorted(codigo for _, _, codigo in salidas.values())
        nombres = sorted(p.name for p in directorio.iterdir())
        assert codigos == [0, cli.EXIT_FALLO_ESCRITURA], (salidas, nombres)
        perdedor = next(tipo for tipo, (_, _, codigo) in salidas.items() if codigo != 0)
        assert salidas[perdedor][0].strip() == b"SecuenciaOcupadaError"
        assert nombres == ["000001.json", "000002.json", "000003.json"]
        ganador = "resultado" if perdedor == "prediccion" else "prediccion"
        assert (directorio / "000003.json").read_bytes() == rp.serializar_entrada(entradas[ganador])
        assert cli.leer_registro(directorio).total == 3


# ---------------------------------------------------------------------------
# verificar
# ---------------------------------------------------------------------------

class TestVerificar:
    def test_registro_valido_codigo_0_y_resumen(self, tmp_path, capsysbinary):
        directorio = _registro_sintetico(tmp_path / "registro")
        antes = _huellas(directorio)
        assert cli.main(["verificar", str(directorio)]) == 0
        salida = capsysbinary.readouterr()
        resumen = json.loads(salida.out)
        assert resumen["esquema"] == "verificacion-registro-prospectivo-ml/1.0"
        assert resumen["protocolo"]["sintetico"] is True
        assert resumen["total_entradas"] == 3
        assert resumen["cabeza_cadena"] == cli.leer_registro(directorio).cabeza
        assert [e["tipo"] for e in resumen["entradas"]] == ["protocolo", "prediccion", "resultado"]
        assert resumen["evaluacion"]["evaluable"] is False
        assert salida.err == b""
        assert _huellas(directorio) == antes

    def test_borrador_real_se_verifica(self, tmp_path, capsysbinary):
        directorio = tmp_path / "registro"
        directorio.mkdir()
        cli.main(["iniciar-borrador", str(directorio)])
        capsysbinary.readouterr()
        assert cli.main(["verificar", str(directorio)]) == 0
        resumen = json.loads(capsysbinary.readouterr().out)
        assert resumen["protocolo"]["estado"] == "borrador"
        assert resumen["protocolo"]["admite_salidas"] is False
        assert resumen["evaluacion"]["motivos"][0] == "protocolo_en_borrador"
        assert "no acumula evidencia prospectiva" in resumen["alcance"]
        assert all(j["predicciones_registradas"] == 0 and j["resultados_incorporados"] == 0
                   for j in resumen["juegos"])

    def test_temporal_de_una_publicacion_en_curso_no_es_una_inconsistencia(self, tmp_path, capsysbinary):
        directorio = _registro_sintetico(tmp_path / "registro")
        esperado = cli.serializar_informe(rp.resumir_registro(cli.leer_registro(directorio)))
        (directorio / ".evidencia-ae48-k2j_9x0q.tmp").write_bytes(b"publicacion en curso")
        assert cli.main(["verificar", str(directorio)]) == 0
        assert capsysbinary.readouterr().out == esperado

    def test_entrada_intermedia_modificada_codigo_5(self, tmp_path, capsysbinary):
        directorio = _registro_sintetico(tmp_path / "registro")
        archivo = directorio / "000002.json"
        datos = json.loads(archivo.read_bytes())
        datos["salida"]["probabilidades"][0] = 0.2
        archivo.write_bytes(rp.serializar_entrada(datos))
        assert cli.main(["verificar", str(directorio)]) == cli.EXIT_CADENA_INCONSISTENTE == 5
        assert capsysbinary.readouterr().out == b""

    @pytest.mark.parametrize("nombre", [
        "notas.txt", "000004.json.tmp", "000009.json", "000004-resultado.json", ".evidencia-ae48-x.json",
        "evidencia-ae48-x.tmp", ".evidencia-ae48-.tmp",
    ])
    def test_archivos_ajenos_o_fuera_de_secuencia_codigo_5(self, tmp_path, capsysbinary, nombre):
        directorio = _registro_sintetico(tmp_path / "registro")
        (directorio / nombre).write_bytes(b"{}\n")
        assert cli.main(["verificar", str(directorio)]) == 5
        assert capsysbinary.readouterr().out == b""

    def test_contenido_que_no_coincide_con_su_numero_codigo_5(self, tmp_path, capsysbinary):
        directorio = _registro_sintetico(tmp_path / "registro")
        segunda, tercera = (directorio / "000002.json").read_bytes(), (directorio / "000003.json").read_bytes()
        (directorio / "000002.json").write_bytes(tercera)
        (directorio / "000003.json").write_bytes(segunda)
        assert cli.main(["verificar", str(directorio)]) == 5
        assert capsysbinary.readouterr().out == b""

    def test_regla_violada_codigo_4(self, tmp_path, capsysbinary):
        directorio = _registro_sintetico(tmp_path / "registro", con_resultado=False)
        archivo = directorio / "000002.json"
        datos = json.loads(archivo.read_bytes())
        datos["entrada"].update(hasta=2714, total_sorteos=634)
        archivo.write_bytes(rp.serializar_entrada(datos))
        assert cli.main(["verificar", str(directorio)]) == cli.EXIT_ENTRADA_INVALIDA == 4

    def test_ilegible_o_inexistente_codigo_3(self, tmp_path, capsysbinary):
        directorio = _registro_sintetico(tmp_path / "registro", con_resultado=False)
        (directorio / "000002.json").write_bytes(b"{roto")
        assert cli.main(["verificar", str(directorio)]) == cli.EXIT_ILEGIBLE == 3
        assert cli.main(["verificar", str(tmp_path / "no-existe")]) == 3
        assert capsysbinary.readouterr().out == b""

    def test_directorio_vacio_codigo_4(self, tmp_path, capsysbinary):
        (tmp_path / "vacio").mkdir()
        assert cli.main(["verificar", str(tmp_path / "vacio")]) == 4

    def test_proceso_hijo_stdout_bytes(self, tmp_path):
        directorio = _registro_sintetico(tmp_path / "registro")
        proceso = subprocess.run(
            [sys.executable, "-m", "scripts.registro_prospectivo_ml", "verificar", str(directorio)],
            cwd=RAIZ_BACKEND, env={**os.environ, "PYTHONPATH": str(RAIZ_BACKEND)}, capture_output=True, timeout=120,
        )
        assert proceso.returncode == 0, proceso.stderr
        assert proceso.stdout == cli.serializar_informe(rp.resumir_registro(cli.leer_registro(directorio)))
        assert b"\r" not in proceso.stdout and proceso.stderr == b""


# ---------------------------------------------------------------------------
# Argumentos y estructura
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("argumentos", [
    [], ["predecir", "x"], ["verificar"], ["verificar", "a", "b"], ["iniciar-borrador"],
    ["iniciar-borrador", "x", "--sintetico"], ["verificar", "x", "--desde", "2706"],
])
def test_argumentos_invalidos_codigo_2(capsysbinary, argumentos):
    assert cli.main(argumentos) == cli.EXIT_ARGUMENTOS_INVALIDOS == 2
    assert capsysbinary.readouterr().out == b""


def test_codigos_de_salida():
    assert (cli.EXIT_OK, cli.EXIT_FALLO_INESPERADO, cli.EXIT_ARGUMENTOS_INVALIDOS, cli.EXIT_ILEGIBLE,
            cli.EXIT_ENTRADA_INVALIDA, cli.EXIT_CADENA_INCONSISTENTE, cli.EXIT_FALLO_ESCRITURA,
            cli.EXIT_RUTA_NO_PERMITIDA) == (0, 1, 2, 3, 4, 5, 8, 9)


def test_cli_sin_base_de_datos_ni_generacion_de_salidas():
    import ast

    texto = Path(cli.__file__).read_text(encoding="utf-8")
    assert 'if __name__ == "__main__":' in texto
    for prohibido in ("sqlalchemy", "engine", "Session", "connect(", "commit(", "INSERT", "UPDATE", "DELETE",
                      "inferencia", "prediccion_bloqueada", "ventanas_temporales", "resolver_estado_prediccion",
                      "diagnostico_bloqueo", "diagnosticar_estado_prediccion", "nueva_prediccion", "nuevo_resultado"):
        assert prohibido not in texto, prohibido
    llamadas = set()
    for nodo in ast.walk(ast.parse(texto)):
        if isinstance(nodo, ast.Call):
            funcion = nodo.func
            llamadas.add(funcion.id if isinstance(funcion, ast.Name) else getattr(funcion, "attr", ""))
    assert not {n for n in llamadas if n.startswith(("entrenar", "predecir", "fit", "predict"))}, llamadas


def test_nada_en_app_web_ni_plantillas_menciona_ae52():
    raiz = RAIZ_BACKEND / "app"
    rutas = [*(raiz / "api").rglob("*.py"), raiz / "main.py", *(raiz / "templates").rglob("*.html")]
    for ruta in rutas:
        contenido = ruta.read_text(encoding="utf-8")
        for nombre in ("registro_prospectivo", "registro_prospectivo_ml"):
            assert nombre not in contenido, (ruta, nombre)
