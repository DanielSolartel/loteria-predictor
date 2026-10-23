"""Plan XML y guardas con PowerShell real; ScheduledTasks se simula en Linux.

Estas pruebas no registran tareas de Windows ni ejecutan Python del producto.
La activacion nativa en aislamiento se acredita por el protocolo del operador.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sys
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/windows/fase6_tarea.ps1"
ENSAYO_NATIVO = Path(__file__).resolve().parents[2] / "tests/ensayar_tarea_fase6_windows.ps1"
NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}


def _powershell():
    ruta = os.environ.get("LOTERIA_POWERSHELL") or shutil.which("powershell") or shutil.which("pwsh")
    if not ruta:
        pytest.skip("Este ensayo del adaptador requiere PowerShell real; disponible en Windows o pwsh en Linux.")
    return ruta


def _ps_literal(p):
    return "'" + str(p).replace("'", "''") + "'"


def _entorno_powershell(tarea):
    # PowerShell 7 inicializa su cache aun con -NoProfile. Solo el proceso
    # hijo usa carpetas propias: no se alteran HOME, TEMP/TMP ni el servidor.
    entorno = os.environ.copy()
    for tipo in ("CACHE", "CONFIG", "DATA"):
        entorno["XDG_" + tipo + "_HOME"] = str(tarea["raiz"] / ("pwsh-" + tipo.lower()))
    return entorno


class CapturaPowerShellInvalida(UnicodeError):
    """El proceso terminó, pero incumplió UTF-8; sus bytes siguen archivados."""
    def __init__(self, proceso, captura, stream, error):
        self.proceso = proceso
        self.captura = captura
        self.stream = stream
        super().__init__(f"PowerShell devolvió {stream} no UTF-8 (código {proceso.returncode}); "
                         f"bytes y diagnóstico conservados en {captura}: {error.reason}.")


def _ejecutar_powershell(tarea, script, *, nombre, timeout, parametros=None):
    """UTF-8 solo en el hijo; persistir ambas capturas antes de decodificar.

    -EncodedCommand transporta el arranque como UTF-16LE también en PS5.1.
    -OutputFormat Text evita serializar los streams como CLIXML. El progreso
    de inicialización se desactiva antes del primer cmdlet, solo en el hijo.
    Los .ps1 invocados se mantienen UTF-8 con BOM. Console.OutputEncoding
    gobierna la salida del host y OutputEncoding sus tuberías a nativos;
    ninguna de esas variables pertenece a la consola o servidor del padre.
    """
    argumentos = ""
    for clave, valor in (parametros or {}).items():
        if not clave.isidentifier() or not clave.isascii():
            raise ValueError("Nombre de parámetro PowerShell no válido.")
        argumentos += " -" + clave + " " + _ps_literal(valor)
    arranque = (
        "$ProgressPreference='SilentlyContinue'\n"
        "$ErrorActionPreference='Stop'\n"
        "$utf8Hijo=New-Object System.Text.UTF8Encoding($false,$true)\n"
        "[Console]::OutputEncoding=$utf8Hijo\n$OutputEncoding=$utf8Hijo\n"
        "try {\n& " + _ps_literal(script) + argumentos + "\n"
        "if ($null -ne $LASTEXITCODE) { exit $LASTEXITCODE }\n"
        "} catch { [Console]::Error.WriteLine($_.ToString()); exit 1 }\nexit 0\n"
    )
    comando = [_powershell(), "-NoLogo", "-NoProfile", "-NonInteractive", "-OutputFormat", "Text", "-EncodedCommand",
               base64.b64encode(arranque.encode("utf-16le")).decode("ascii")]
    proceso = subprocess.run(comando, capture_output=True, timeout=timeout,
                             env=_entorno_powershell(tarea))
    # subprocess no decodifica en hilos: incluso una salida inválida conserva
    # ambos streams y el código real. No convertir None ni reemplazar bytes.
    if not isinstance(proceso.stdout, bytes) or not isinstance(proceso.stderr, bytes):
        raise TypeError("La captura binaria de PowerShell debe devolver ambos streams como bytes.")
    carpeta = Path(os.environ.get("FASE4_EVIDENCIA") or tarea["raiz"])
    carpeta.mkdir(parents=True, exist_ok=True)
    caso = os.environ.get("PYTEST_CURRENT_TEST", "sin_identificador_pytest")
    clave = hashlib.sha256((caso + "\n" + nombre + "\n" + str(script)).encode("utf-8")).hexdigest()
    prefijo = "ps-" + clave
    captura = carpeta / (prefijo + ".json")
    registro = {"version": 1, "tipo": "captura_powershell_sintetica", "caso": caso,
                "nombre": nombre, "script": str(script), "comando": comando,
                "codigo": proceso.returncode,
                "decodificacion": {"codificacion": "utf-8", "errores": "strict", "estado": "pendiente"}}
    for stream in ("stdout", "stderr"):
        contenido = getattr(proceso, stream)
        archivo = prefijo + "." + stream + ".bin"
        (carpeta / archivo).write_bytes(contenido)
        registro[stream] = {"archivo": archivo, "bytes": len(contenido),
                            "sha256": hashlib.sha256(contenido).hexdigest()}
    def guardar():
        captura.write_text(json.dumps(registro, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    guardar()
    textos = {}
    for stream in ("stdout", "stderr"):
        try:
            textos[stream] = getattr(proceso, stream).decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            registro["decodificacion"].update(estado="error", stream=stream,
                                             inicio=error.start, fin=error.end, razon=error.reason)
            guardar()
            raise CapturaPowerShellInvalida(proceso, captura, stream, error) from error
    registro["decodificacion"]["estado"] = "correcta"
    guardar()
    (tarea["raiz"] / (nombre + "-powershell.log")).write_text(
        textos["stdout"] + textos["stderr"], encoding="utf-8", newline="")
    resultado = subprocess.CompletedProcess(proceso.args, proceso.returncode,
                                           textos["stdout"], textos["stderr"])
    resultado.captura = captura
    resultado.stdout_bytes = proceso.stdout
    resultado.stderr_bytes = proceso.stderr
    return resultado


def _controlador_con_identidad_simulada_linux(raiz, monkeypatch):
    """Solo fixture: sustituye resolución Windows en una copia, jamás en producción.

    Las aserciones/capturas del controlador siguen ejecutándose completas.
    Windows usa siempre el controlador y la resolución nativa originales.
    """
    if os.name == "nt":
        return
    texto = SCRIPT.read_text(encoding="utf-8")
    reemplazos = {
        "Get-UsuarioActual": r"""function Get-UsuarioActual {
    return [pscustomobject]@{Id='S-1-5-21-100-200-300-1001';Nombre='LP6-FIXTURE\usuario';Plataforma='Linux_identidad_simulada_sin_Programador'}
}
""",
        "Resolver-IdentidadSid": r"""function Resolver-IdentidadSid([string]$Identidad) {
    if($Identidad -ceq 'S-1-5-21-100-200-300-1001' -or $Identidad -ceq 'LP6-FIXTURE\usuario') { return 'S-1-5-21-100-200-300-1001' }
    throw 'Identidad no resoluble por el resolver simulado de la fixture.'
}
""",
    }
    for nombre, codigo in reemplazos.items():
        patron = r"(?ms)^function " + re.escape(nombre) + r"(?=[\s(]).*?(?=^function )"
        texto, cantidad = re.subn(patron, lambda _: codigo + "\n", texto)
        assert cantidad == 1, nombre
    copia = raiz / "controlador-sid-simulado.ps1"
    copia.write_text(texto, encoding="utf-8-sig")
    monkeypatch.setattr(sys.modules[__name__], "SCRIPT", copia)


@pytest.fixture
def tarea(tmp_path, monkeypatch):
    raiz = tmp_path / "tarea con espacios y ñ"
    raiz.mkdir()
    _controlador_con_identidad_simulada_linux(raiz, monkeypatch)
    repo = raiz / "worktree"
    (repo / "backend/scripts").mkdir(parents=True)
    (repo / "backend/scripts/operacion_automatica.py").write_text(
        "raise AssertionError('El adaptador no debe ejecutar Python durante el control de tareas')\n",
        encoding="utf-8",
    )
    interprete = raiz / "venv con espacios/python.exe"
    interprete.parent.mkdir()
    interprete.write_bytes(b"INTERPRETE_FICTICIO_NO_EJECUTABLE")
    config = raiz / "configuracion explicita.json"
    config.write_text('{"no_abrir": "contenido sintético"}\n', encoding="utf-8")
    return {"raiz": raiz, "repo": repo, "python": interprete, "config": config, "originales": {
        p: p.read_bytes() for p in raiz.rglob("*") if p.is_file()
    }}


def _llamar(tarea, accion="", *, previo="", despues="", salida="e", ruta_repo=None):
    e = tarea["raiz"] / salida
    argumentos = (
        " -Worktree " + _ps_literal(ruta_repo if ruta_repo is not None else tarea["repo"])
        + " -PythonExe " + _ps_literal(tarea["python"])
        + " -Configuracion " + _ps_literal(tarea["config"])
        + " -Evidencia " + _ps_literal(e)
    )
    wrapper = tarea["raiz"] / (salida + "-invocar.ps1")
    wrapper.write_text(
        "$ErrorActionPreference='Stop'\n" + previo + "\n& " + _ps_literal(SCRIPT)
        + argumentos + " " + accion + "\n$codigo=$LASTEXITCODE\n" + despues + "\nexit $codigo\n",
        encoding="utf-8-sig",
    )
    proceso = _ejecutar_powershell(tarea, wrapper, nombre=salida, timeout=60)
    resultado = json.loads((e / "resultado.json").read_text(encoding="utf-8"))
    for p, b in tarea["originales"].items():
        assert p.read_bytes() == b
    return proceso, resultado, e


def test_plan_predeterminado_no_activa_y_conserva_rutas_con_espacios(tarea):
    # Si el plan accidentalmente toca el programador, falla el ensayo.
    previo = "function Get-ScheduledTask { throw 'PROGRAMADOR NO DEBE CONSULTARSE EN PLAN' }"
    p, r, e = _llamar(tarea, previo=previo)
    assert p.returncode == 0, p.stdout + p.stderr
    assert r["estado"] == "plan_no_instalado" and r["accion"] == "Plan"
    assert not r["tarea_modificada"] and not r["producto_ejecutado"]
    x = ET.parse(e / "tarea.xml")
    val = lambda n: x.findtext("t:" + n.replace("/", "/t:"), namespaces=NS)
    assert val("Actions/Exec/Command") == str(tarea["python"])
    assert val("Actions/Exec/WorkingDirectory") == str(tarea["repo"] / "backend")
    assert val("Actions/Exec/Arguments") == '-m scripts.operacion_automatica --config "' + str(tarea["config"]) + '" ciclo'
    assert val("Principals/Principal/RunLevel") == "LeastPrivilege"
    assert val("Principals/Principal/LogonType") == "InteractiveToken"
    assert val("Settings/Enabled") == "false"
    assert val("Settings/MultipleInstancesPolicy") == "IgnoreNew"
    assert val("Settings/StartWhenAvailable") == "true" and val("Settings/WakeToRun") == "false"
    assert val("Settings/ExecutionTimeLimit") == "PT2H"
    assert val("Triggers/TimeTrigger/Repetition/Interval") == "PT5M"
    assert len(x.findall("t:Triggers/*", NS)) == 2
    assert x.find("t:Triggers/t:LogonTrigger", NS) is not None


@pytest.mark.parametrize("accion", ["-Plan -Instalar", "-Pausar -Reanudar", "-Estado -Desinstalar"])
def test_acciones_incompatibles_fallan_antes_del_programador_y_guardan_evidencia(tarea, accion):
    p, r, e = _llamar(tarea, accion)
    assert p.returncode != 0 and r["estado"] == "error"
    assert "una sola accion" in r["error"]
    assert not (e / "tarea.xml").exists()
    assert "Fallo:" in (e / "registro.log").read_text(encoding="utf-8")


def test_ruta_relativa_rechazada_con_diagnostico(tarea):
    p, r, _ = _llamar(tarea, ruta_repo="worktree relativo")
    assert p.returncode != 0 and "ruta absoluta" in r["error"]
    assert not r["tarea_modificada"]


MOCKS = r'''
$global:Tareas = @{}
$global:Llamadas = New-Object Collections.Generic.List[string]
$global:Viva = $false
function Get-ScheduledTask {
    [CmdletBinding()]param([string]$TaskName,[string]$TaskPath)
    [void]$global:Llamadas.Add('Get')
    if (-not $global:Tareas.ContainsKey($TaskName)) { return $null }
    $x=$global:Tareas[$TaskName]
    $enabled=$x.Task.Settings.Enabled -eq 'true'
    return [pscustomobject]@{TaskName=$TaskName; Settings=[pscustomobject]@{Enabled=$enabled}; State=$(if($global:Viva){'Running'}elseif($enabled){'Ready'}else{'Disabled'})}
}
function Export-ScheduledTask {
    [CmdletBinding()]param([string]$TaskName,[string]$TaskPath)
    [void]$global:Llamadas.Add('Export')
    return $global:Tareas[$TaskName].OuterXml
}
function Register-ScheduledTask {
    [CmdletBinding()]param([string]$TaskName,[string]$TaskPath,[string]$Xml)
    [void]$global:Llamadas.Add('Register')
    if ($global:Tareas.ContainsKey($TaskName)) {throw 'TAREA EXISTENTE NO SE SOBRESCRIBE'}
    $global:Tareas[$TaskName]=[xml]$Xml
}
function Enable-ScheduledTask {
    [CmdletBinding()]param([string]$TaskName,[string]$TaskPath)
    [void]$global:Llamadas.Add('Enable')
    $global:Tareas[$TaskName].Task.Settings.Enabled='true'
}
function Disable-ScheduledTask {
    [CmdletBinding()]param([string]$TaskName,[string]$TaskPath)
    [void]$global:Llamadas.Add('Disable')
    $global:Tareas[$TaskName].Task.Settings.Enabled='false'
}
function Unregister-ScheduledTask {
    [CmdletBinding(SupportsShouldProcess=$true)]param([string]$TaskName,[string]$TaskPath)
    [void]$global:Llamadas.Add('Unregister')
    $global:Tareas.Remove($TaskName)
}
'''


def _sesion(tarea, cuerpo):
    datos = {
        "SCRIPT": _ps_literal(SCRIPT), "REPO": _ps_literal(tarea["repo"]),
        "PYTHON": _ps_literal(tarea["python"]), "CONFIG": _ps_literal(tarea["config"]),
        "RAIZ": _ps_literal(tarea["raiz"]),
    }
    p = tarea["raiz"] / "sesion-simulada.ps1"
    cabecera = r'''
$ErrorActionPreference='Stop'
$scriptPrueba=__SCRIPT__
$comun=@{Worktree=__REPO__;PythonExe=__PYTHON__;Configuracion=__CONFIG__}
$raizPrueba=__RAIZ__
function Invoke-Caso([string]$Nombre,[string]$Accion,[int]$Esperado=0) {
    $e=Join-Path $raizPrueba $Nombre
    $a=@{}; foreach($k in $comun.Keys){$a[$k]=$comun[$k]};$a.Evidencia=$e;$a[$Accion]=$true
    & $scriptPrueba @a | Out-Host
    if($LASTEXITCODE -ne $Esperado){throw ('Codigo incorrecto en '+$Nombre)}
    return (Get-Content -LiteralPath (Join-Path $e 'resultado.json') -Raw -Encoding UTF8 | ConvertFrom-Json)
}
'''
    for k, v in datos.items():
        cabecera = cabecera.replace("__" + k + "__", v)
    p.write_text(cabecera + MOCKS + cuerpo + "\nexit 0\n", encoding="utf-8-sig")
    proc = _ejecutar_powershell(tarea, p, nombre="sesion", timeout=90)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    for p, b in tarea["originales"].items():
        assert p.read_bytes() == b


def test_ciclo_tarea_propietaria_instala_deshabilitada_y_repite_sin_sobrescribir(tarea):
    _sesion(tarea, r'''
$r=Invoke-Caso 'instalar' 'Instalar'
if($r.estado -ne 'instalada_deshabilitada' -or $r.habilitada){throw 'ACTIVACION IMPLICITA'}
$nombre=$r.tarea;$antes=$global:Tareas[$nombre].OuterXml
$r=Invoke-Caso 'reinstalar' 'Instalar'
if($r.estado -ne 'ya_instalada_sin_reescribir' -or $global:Tareas[$nombre].OuterXml -cne $antes){throw 'REESCRITURA'}
$r=Invoke-Caso 'activar' 'Activar';if(-not $r.habilitada){throw 'NO ACTIVADA'}
$r=Invoke-Caso 'pausar' 'Pausar';if($r.habilitada){throw 'NO PAUSADA'}
$r=Invoke-Caso 'reanudar' 'Reanudar';if(-not $r.habilitada){throw 'NO REANUDADA'}
$r=Invoke-Caso 'estado' 'Estado';if($r.estado_programador -ne 'Ready'){throw 'ESTADO INCORRECTO'}
$r=Invoke-Caso 'desinstalar' 'Desinstalar';if($global:Tareas.Count -ne 0){throw 'NO DESINSTALADA'}
$r=Invoke-Caso 'ausente' 'Desinstalar';if($r.estado -ne 'ya_ausente'){throw 'NO IDEMPOTENTE'}
if(@($global:Llamadas | Where-Object{$_ -eq 'Register'}).Count -ne 1){throw 'REGISTRO DUPLICADO'}
''')


@pytest.mark.parametrize("alteracion", ["descripcion", "programa", "intervalo", "usuario", "accion_extra"])
def test_tarea_ajena_o_modificada_rechazada_sin_perdida(tarea, alteracion):
    cambios = {
        "descripcion": "$x.Task.RegistrationInfo.Description='AJENA'",
        "programa": "$x.Task.Actions.Exec.Command='otro-programa.exe'",
        "intervalo": "$x.Task.Triggers.TimeTrigger.Repetition.Interval='PT1M'",
        "usuario": "$x.Task.Principals.Principal.UserId='otro-usuario'",
        "accion_extra": "$nuevo=$x.Task.Actions.Exec.CloneNode($true);[void]$x.Task.Actions.AppendChild($nuevo)",
    }
    _sesion(tarea, r'''
$r=Invoke-Caso 'instalar' 'Instalar';$nombre=$r.tarea
$x=$global:Tareas[$nombre]
''' + cambios[alteracion] + r'''
$antes=$global:Tareas[$nombre].OuterXml;$cuenta=$global:Llamadas.Count
$r=Invoke-Caso 'rechazo' 'Activar' 1
if($r.estado -ne 'error' -or $r.tarea_modificada){throw 'FALSO EXITO'}
if($global:Tareas[$nombre].OuterXml -cne $antes){throw 'TAREA AJENA MODIFICADA'}
foreach($c in @($global:Llamadas | Select-Object -Skip $cuenta)){if($c -in @('Enable','Disable','Register','Unregister')){throw 'MUTACION AJENA'}}
''')


def test_desinstalar_no_interrumpe_ciclo_vivo(tarea):
    _sesion(tarea, r'''
$r=Invoke-Caso 'instalar' 'Instalar';$nombre=$r.tarea
$global:Viva=$true;$antes=$global:Tareas[$nombre].OuterXml;$cuenta=$global:Llamadas.Count
$r=Invoke-Caso 'viva' 'Desinstalar' 1
if($r.error -notmatch 'ciclo vivo' -or $r.tarea_modificada){throw 'NO RECHAZA TRABAJO VIVO'}
if($global:Tareas[$nombre].OuterXml -cne $antes){throw 'MUTACION'}
foreach($c in @($global:Llamadas | Select-Object -Skip $cuenta)){if($c -in @('Enable','Disable','Register','Unregister')){throw 'TRABAJO VIVO INTERRUMPIDO'}}
''')


def test_ensayo_nativo_exige_accion_explicita_antes_de_crear_o_consultar(tarea):
    evidencia = tarea["raiz"] / "no-debe-crearse"
    proceso = _ejecutar_powershell(
        tarea, ENSAYO_NATIVO, nombre="ensayo-sin-activar", timeout=30,
        parametros={"PythonExe": tarea["python"], "Evidencia": evidencia},
    )
    assert proceso.returncode != 0
    assert "-Ejecutar" in proceso.stdout + proceso.stderr
    assert not evidencia.exists()
    for p, b in tarea["originales"].items():
        assert p.read_bytes() == b


def test_parser_powershell_real_del_control_y_ensayo_nativo(tarea):
    wrapper = tarea["raiz"] / "analizar-scripts.ps1"
    cuerpo = "$ErrorActionPreference='Stop'\n"
    for p in (SCRIPT, ENSAYO_NATIVO):
        cuerpo += ("$t=$null;$e=$null;[void][Management.Automation.Language.Parser]::ParseFile("
                   + _ps_literal(p) + ",[ref]$t,[ref]$e);if(@($e).Count){throw 'SINTAXIS INCORRECTA'}\n")
    cuerpo += "'DOS SCRIPTS ANALIZADOS; NINGUNA TAREA EJECUTADA'\n"
    wrapper.write_text(cuerpo, encoding="utf-8-sig")
    proc = _ejecutar_powershell(tarea, wrapper, nombre="parser", timeout=30)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "DOS SCRIPTS ANALIZADOS" in proc.stdout



def test_captura_utf8_preserva_ambos_streams_y_codigo_con_rutas_no_ascii(tarea):
    antes = dict(os.environ)
    programa = tarea["raiz"] / "emisión con ñ y espacios.ps1"
    programa.write_text('[Console]::Out.Write("salida: ñ con espacios`r`n")\n'
                        '[Console]::Error.Write("error: ñ con espacios`r`n")\nexit 7\n', encoding="utf-8-sig")
    original = programa.read_bytes()
    proc = _ejecutar_powershell(tarea, programa, nombre="utf8", timeout=30)
    assert proc.returncode == 7
    assert proc.stdout == "salida: ñ con espacios\r\n"
    assert proc.stderr == "error: ñ con espacios\r\n"
    assert proc.stdout_bytes == proc.stdout.encode("utf-8")
    assert proc.stderr_bytes == proc.stderr.encode("utf-8")
    assert (tarea["raiz"] / "utf8-powershell.log").read_bytes() == proc.stdout_bytes + proc.stderr_bytes
    r = json.loads(proc.captura.read_text(encoding="utf-8"))
    assert r["codigo"] == 7 and r["decodificacion"] == {
        "codificacion": "utf-8", "errores": "strict", "estado": "correcta"}
    for stream in ("stdout", "stderr"):
        raw = (proc.captura.parent / r[stream]["archivo"]).read_bytes()
        assert raw == getattr(proc, stream + "_bytes")
        assert r[stream]["bytes"] == len(raw) and r[stream]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert dict(os.environ) == antes and programa.read_bytes() == original


@pytest.mark.parametrize("invalido", ["stdout", "stderr"])
def test_captura_invalida_archiva_bytes_y_codigo_antes_de_fallar(tarea, invalido):
    programa = tarea["raiz"] / "error de contrato ñ.ps1"
    metodo = "OpenStandardOutput" if invalido == "stdout" else "OpenStandardError"
    otro = "Error" if invalido == "stdout" else "Out"
    programa.write_text(
        "[byte[]]$raw=@(0x61,0xa4,0x62)\n"
        f"$destino=[Console]::{metodo}();$destino.Write($raw,0,$raw.Length);$destino.Flush()\n"
        f"[Console]::{otro}.Write('válido ñ')\nexit 23\n", encoding="utf-8-sig")
    with pytest.raises(CapturaPowerShellInvalida) as atrapado:
        _ejecutar_powershell(tarea, programa, nombre="invalido-" + invalido, timeout=30)
    error = atrapado.value
    assert error.proceso.returncode == 23 and error.stream == invalido
    r = json.loads(error.captura.read_text(encoding="utf-8"))
    assert r["codigo"] == 23 and r["decodificacion"]["estado"] == "error"
    assert r["decodificacion"]["stream"] == invalido and r["decodificacion"]["inicio"] == 1
    for stream in ("stdout", "stderr"):
        raw = (error.captura.parent / r[stream]["archivo"]).read_bytes()
        assert raw == getattr(error.proceso, stream)
        assert raw == (b"a\xa4b" if stream == invalido else "válido ñ".encode("utf-8"))
        assert r[stream]["bytes"] == len(raw) and r[stream]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert not (tarea["raiz"] / ("invalido-" + invalido + "-powershell.log")).exists()


def test_arranque_declara_texto_y_suprime_progreso_antes_de_inicializar_hijo(tarea, monkeypatch):
    """Guardas portables del contrato de lanzamiento; no simula PS5.1 nativo."""
    entorno_padre = dict(os.environ)
    programa = tarea["raiz"] / "contrato del hijo.ps1"
    programa.write_text("exit 19\n", encoding="utf-8-sig")
    # Un prefijo CLIXML escrito deliberadamente por el programa es contenido:
    # debe conservarse byte a byte, nunca eliminarse durante la captura.
    stdout = b"#< CLIXML\r\nsalida literal\r\n"
    stderr = "#< CLIXML\r\nerror literal ñ\r\n".encode("utf-8")

    def ejecutar(comando, **opciones):
        assert comando[comando.index("-OutputFormat") + 1] == "Text"
        arranque = base64.b64decode(comando[comando.index("-EncodedCommand") + 1]).decode("utf-16le")
        lineas = arranque.splitlines()
        assert lineas[0] == "$ProgressPreference='SilentlyContinue'"
        assert arranque.index("$ProgressPreference=") < arranque.index("New-Object")
        assert opciones["capture_output"] is True
        assert "text" not in opciones and "encoding" not in opciones and "errors" not in opciones
        assert dict(os.environ) == entorno_padre
        return subprocess.CompletedProcess(comando, 19, stdout, stderr)

    monkeypatch.setattr(subprocess, "run", ejecutar)
    p = _ejecutar_powershell(tarea, programa, nombre="contrato", timeout=30)
    assert p.returncode == 19 and p.stdout_bytes == stdout and p.stderr_bytes == stderr
    assert p.stdout == stdout.decode("utf-8") and p.stderr == stderr.decode("utf-8")
    registro = json.loads(p.captura.read_text(encoding="utf-8"))
    for stream, raw in (("stdout", stdout), ("stderr", stderr)):
        assert (p.captura.parent / registro[stream]["archivo"]).read_bytes() == raw
        assert registro[stream]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert dict(os.environ) == entorno_padre


def test_progreso_del_hijo_no_contamina_y_conserva_prefijos_literales(tarea):
    """PowerShell real disponible; el progreso automático PS5.1 queda para Windows."""
    entorno_padre = dict(os.environ)
    programa = tarea["raiz"] / "progreso con ñ.ps1"
    programa.write_text(
        "if ($ProgressPreference -ne 'SilentlyContinue') { throw 'Progreso no aislado al inicio' }\n"
        "Write-Progress -Activity 'Preparing modules for first use.' -Status 'ensayo explicito'\n"
        "[Console]::Out.Write(\"#< CLIXML`r`nsalida literal ñ`r`n\")\n"
        "[Console]::Error.Write(\"#< CLIXML`r`nerror literal ñ`r`n\")\nexit 19\n",
        encoding="utf-8-sig",
    )
    p = _ejecutar_powershell(tarea, programa, nombre="progreso", timeout=30)
    assert p.returncode == 19, p.stdout + p.stderr
    assert p.stdout_bytes == "#< CLIXML\r\nsalida literal ñ\r\n".encode("utf-8")
    assert p.stderr_bytes == "#< CLIXML\r\nerror literal ñ\r\n".encode("utf-8")
    registro = json.loads(p.captura.read_text(encoding="utf-8"))
    assert registro["decodificacion"]["estado"] == "correcta"
    for stream in ("stdout", "stderr"):
        raw = getattr(p, stream + "_bytes")
        assert (p.captura.parent / registro[stream]["archivo"]).read_bytes() == raw
        assert registro[stream]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert dict(os.environ) == entorno_padre
