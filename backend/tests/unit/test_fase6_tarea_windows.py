"""Plan XML y guardas con PowerShell real; ScheduledTasks se simula en Linux.

Estas pruebas no registran tareas de Windows ni ejecutan Python del producto.
La activacion nativa en aislamiento se acredita por el protocolo del operador.
Version 2 (horario por juego): el plan sale de `operacion_horario.plan_windows`; la
version 1 se instala con el script anterior archivado para ensayar su migracion.
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

from app.application import operacion_horario as horario

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/windows/fase6_tarea.ps1"
SCRIPT_V1 = Path(__file__).resolve().parents[2] / "tests/fixtures/fase6/fase6_tarea_v1.ps1"
PLAN = horario.plan_windows(horario.propuesta_inicial())
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
    for nombre_modulo, original, destino in (("SCRIPT", SCRIPT, "controlador-sid-simulado.ps1"),
                                             ("SCRIPT_V1", SCRIPT_V1, "controlador-v1-sid-simulado.ps1")):
        _sustituir_identidad(original, raiz / destino, nombre_modulo, monkeypatch)


def _sustituir_identidad(original, copia, nombre_modulo, monkeypatch):
    texto = original.read_text(encoding="utf-8")
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
    copia.write_text(texto, encoding="utf-8-sig")
    monkeypatch.setattr(sys.modules[__name__], nombre_modulo, copia)


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
    plan = raiz / "plan de horario.json"  # como `horario plan --salida`
    plan.write_text(json.dumps(PLAN, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return {"raiz": raiz, "repo": repo, "python": interprete, "config": config, "plan": plan, "originales": {
        p: p.read_bytes() for p in raiz.rglob("*") if p.is_file()
    }}


def _llamar(tarea, accion="", *, previo="", despues="", salida="e", ruta_repo=None, plan=True):
    e = tarea["raiz"] / salida
    argumentos = (
        " -Worktree " + _ps_literal(ruta_repo if ruta_repo is not None else tarea["repo"])
        + " -PythonExe " + _ps_literal(tarea["python"])
        + " -Configuracion " + _ps_literal(tarea["config"])
        + " -Evidencia " + _ps_literal(e)
        + (" -PlanHorario " + _ps_literal(tarea["plan"]) if plan else "")
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
    assert val("Actions/Exec/Arguments") == ('-m scripts.operacion_automatica --config "' + str(tarea["config"])
                                             + '" ciclo --programado --plan ' + PLAN["huella"])
    assert val("Principals/Principal/RunLevel") == "LeastPrivilege"
    assert val("Principals/Principal/LogonType") == "InteractiveToken"
    assert val("Settings/Enabled") == "false"
    assert val("Settings/MultipleInstancesPolicy") == "IgnoreNew"
    # Sin ejecuciones al arrancar fuera de horario, sin disparo al iniciar sesion ni repeticion continua.
    assert val("Settings/StartWhenAvailable") == "false" and val("Settings/WakeToRun") == "false"
    assert val("Settings/ExecutionTimeLimit") == "PT2H"
    assert val("RegistrationInfo/Source") == "LoteriaPredictor/Fase6/tarea/2"
    disparadores = x.findall("t:Triggers/*", NS)
    assert [d.tag.split("}")[1] for d in disparadores] == ["CalendarTrigger"] * len(PLAN["disparadores"])
    for d, esperado in zip(disparadores, PLAN["disparadores"]):
        assert d.findtext("t:StartBoundary", namespaces=NS) == esperado["inicio"]
        assert [n.tag.split("}")[1] for n in d.find("t:ScheduleByWeek/t:DaysOfWeek", NS)] == esperado["dias"]
        assert d.findtext("t:Repetition/t:Interval", namespaces=NS) == esperado["intervalo"]
        assert d.findtext("t:Repetition/t:Duration", namespaces=NS) == esperado["duracion"]
    assert r["plan_horario"]["huella"] == PLAN["huella"]


@pytest.mark.parametrize("alterar", ["huella", "texto", "xml", "dia"])
def test_plan_de_horario_alterado_se_rechaza_antes_del_programador(tarea, alterar):
    plan = json.loads(tarea["plan"].read_text(encoding="utf-8"))
    if alterar == "huella":
        plan["huella"] = "0" * 64
    elif alterar == "texto":
        plan["texto"] = plan["texto"].replace("PT15M", "PT5M", 1)
    elif alterar == "xml":
        plan["xml_disparadores"] = plan["xml_disparadores"].replace("<Monday />", "", 1)
    else:
        plan["disparadores"][0]["dias"].append("Sunday")
    alterado = tarea["raiz"] / "plan alterado.json"
    alterado.write_text(json.dumps(plan), encoding="utf-8")
    tarea["originales"][alterado] = alterado.read_bytes()
    previo = "function Get-ScheduledTask { throw 'PROGRAMADOR NO DEBE CONSULTARSE' }"
    original = tarea["plan"]
    tarea["plan"] = alterado
    try:
        p, r, e = _llamar(tarea, previo=previo, salida="alterado-" + alterar)
    finally:
        tarea["plan"] = original
    assert p.returncode != 0 and r["estado"] == "error" and not r["tarea_modificada"]
    assert not (e / "tarea.xml").exists()


def _plan_coherente(disparadores):
    """Plan con texto, huella y XML recalculados: solo lo rechazan las guardas de fecha y desfase."""
    plan = json.loads(json.dumps(PLAN))
    plan["disparadores"] = disparadores
    plan["texto"] = horario.texto_plan(disparadores)
    plan["huella"] = hashlib.sha256(plan["texto"].encode("utf-8")).hexdigest()
    plan["xml_disparadores"] = horario.xml_disparadores(disparadores)
    return plan


def _llamar_con_plan(tarea, plan, nombre, previo=""):
    ruta = tarea["raiz"] / (nombre + ".json")
    ruta.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    tarea["originales"][ruta] = ruta.read_bytes()
    original, tarea["plan"] = tarea["plan"], ruta
    try:
        return _llamar(tarea, previo=previo, salida=nombre)
    finally:
        tarea["plan"] = original


def test_plan_legitimo_conserva_el_texto_iso_y_su_desfase_al_leerlo(tarea):
    """F92-PS-02: PowerShell 7 convierte las cadenas ISO completas en DateTime al leer JSON; el plan
    legítimo debe leerse con su texto exacto (desfase incluido) en 5.1 y en 7.x."""
    previo = "function Get-ScheduledTask { throw 'PROGRAMADOR NO DEBE CONSULTARSE EN PLAN' }"
    p, r, e = _llamar(tarea, previo=previo, salida="iso")
    assert p.returncode == 0 and r["estado"] == "plan_no_instalado", r.get("error")
    assert r["plan_horario"]["huella"] == PLAN["huella"]
    x = ET.parse(e / "tarea.xml")
    inicios = [d.findtext("t:StartBoundary", namespaces=NS) for d in x.findall("t:Triggers/t:CalendarTrigger", NS)]
    assert inicios == [d["inicio"] for d in PLAN["disparadores"]]
    assert all(i.endswith("-05:00") for i in inicios)


@pytest.mark.parametrize("cambio", ["desfase_utc", "sin_desfase", "desfase_declarado", "marcador_reservado"])
def test_fechas_y_desfases_ajenos_se_rechazan_aunque_el_plan_sea_coherente(tarea, cambio):
    disparadores = json.loads(json.dumps(PLAN["disparadores"]))
    if cambio == "desfase_utc":
        disparadores[0]["inicio"] = disparadores[0]["inicio"].replace("-05:00", "+00:00")
        plan = _plan_coherente(disparadores)
    elif cambio == "sin_desfase":
        disparadores[0]["inicio"] = disparadores[0]["inicio"][:-6]
        plan = _plan_coherente(disparadores)
    elif cambio == "desfase_declarado":
        plan = json.loads(json.dumps(PLAN))
        plan["desfase"] = "+00:00"
    else:
        disparadores[0]["inicio"] = "lp6-literal:" + disparadores[0]["inicio"]
        plan = _plan_coherente(disparadores)
    previo = "function Get-ScheduledTask { throw 'PROGRAMADOR NO DEBE CONSULTARSE' }"
    p, r, e = _llamar_con_plan(tarea, plan, "fecha-" + cambio, previo)
    assert p.returncode != 0 and r["estado"] == "error" and not r["tarea_modificada"]
    assert not (e / "tarea.xml").exists()


def test_plan_sin_archivo_de_horario_se_rechaza(tarea):
    p, r, e = _llamar(tarea, plan=False)
    assert p.returncode != 0 and "-PlanHorario" in r["error"] and not (e / "tarea.xml").exists()


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
function Nueva-Vista([string]$Nombre) {
    $x=$global:Tareas[$Nombre]
    $enabled=$x.Task.Settings.Enabled -eq 'true'
    $exec=$x.Task.Actions.Exec
    return [pscustomobject]@{TaskName=$Nombre; Source=[string]$x.Task.RegistrationInfo.Source; Settings=[pscustomobject]@{Enabled=$enabled}; State=$(if($global:Viva){'Running'}elseif($enabled){'Ready'}else{'Disabled'}); Actions=@([pscustomobject]@{Arguments=[string]$exec.Arguments; WorkingDirectory=[string]$exec.WorkingDirectory})}
}
function Get-ScheduledTask {
    [CmdletBinding()]param([string]$TaskName,[string]$TaskPath)
    [void]$global:Llamadas.Add('Get')
    if ([string]::IsNullOrEmpty($TaskName)) { return @($global:Tareas.Keys | ForEach-Object { Nueva-Vista $_ }) }
    if (-not $global:Tareas.ContainsKey($TaskName)) { return $null }
    return (Nueva-Vista $TaskName)
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
        "SCRIPT": _ps_literal(SCRIPT), "SCRIPTV1": _ps_literal(SCRIPT_V1), "REPO": _ps_literal(tarea["repo"]),
        "PYTHON": _ps_literal(tarea["python"]), "CONFIG": _ps_literal(tarea["config"]),
        "RAIZ": _ps_literal(tarea["raiz"]), "PLAN": _ps_literal(tarea["plan"]),
    }
    p = tarea["raiz"] / "sesion-simulada.ps1"
    cabecera = r'''
$ErrorActionPreference='Stop'
$scriptPrueba=__SCRIPT__
$scriptV1=__SCRIPTV1__
$comun=@{Worktree=__REPO__;PythonExe=__PYTHON__;Configuracion=__CONFIG__}
$planPrueba=__PLAN__
$raizPrueba=__RAIZ__
function Invoke-Caso([string]$Nombre,[string]$Accion,[int]$Esperado=0,[hashtable]$Extra=@{},[string]$Script=$scriptPrueba) {
    $e=Join-Path $raizPrueba $Nombre
    $a=@{}; foreach($k in $comun.Keys){$a[$k]=$comun[$k]};$a.Evidencia=$e;$a[$Accion]=$true
    if($Script -eq $scriptPrueba){$a.PlanHorario=$planPrueba}
    foreach($k in $Extra.Keys){$a[$k]=$Extra[$k]}
    & $Script @a | Out-Host
    if($LASTEXITCODE -ne $Esperado){throw ('Codigo incorrecto en '+$Nombre)}
    return (Get-Content -LiteralPath (Join-Path $e 'resultado.json') -Raw -Encoding UTF8 | ConvertFrom-Json)
}
function Invoke-CasoV1([string]$Nombre,[string]$Accion) { return (Invoke-Caso $Nombre $Accion 0 @{} $scriptV1) }
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


@pytest.mark.parametrize("alteracion", ["descripcion", "programa", "intervalo", "usuario", "accion_extra",
                                        "inicio_de_sesion", "dias", "arranque_disponible"])
def test_tarea_ajena_o_modificada_rechazada_sin_perdida(tarea, alteracion):
    cambios = {
        "descripcion": "$x.Task.RegistrationInfo.Description='AJENA'",
        "programa": "$x.Task.Actions.Exec.Command='otro-programa.exe'",
        "intervalo": "$x.Task.Triggers.CalendarTrigger[0].Repetition.Interval='PT1M'",
        "usuario": "$x.Task.Principals.Principal.UserId='otro-usuario'",
        "accion_extra": "$nuevo=$x.Task.Actions.Exec.CloneNode($true);[void]$x.Task.Actions.AppendChild($nuevo)",
        "inicio_de_sesion": ("$l=$x.CreateElement('LogonTrigger',$x.Task.NamespaceURI);"
                             "[void]$x.Task.Triggers.AppendChild($l)"),
        "dias": ("$d=$x.CreateElement('Sunday',$x.Task.NamespaceURI);"
                 "[void]$x.Task.Triggers.CalendarTrigger[1].ScheduleByWeek.DaysOfWeek.AppendChild($d)"),
        "arranque_disponible": "$x.Task.Settings.StartWhenAvailable='true'",
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
        parametros={"PythonExe": tarea["python"], "Evidencia": evidencia, "PlanHorario": tarea["plan"]},
    )
    assert proceso.returncode != 0
    assert "-Ejecutar" in proceso.stdout + proceso.stderr
    assert not evidencia.exists()
    for p, b in tarea["originales"].items():
        assert p.read_bytes() == b


def test_parser_powershell_real_del_control_y_ensayo_nativo(tarea):
    wrapper = tarea["raiz"] / "analizar-scripts.ps1"
    cuerpo = "$ErrorActionPreference='Stop'\n"
    for p in (SCRIPT, ENSAYO_NATIVO, SCRIPT_V1):
        cuerpo += ("$t=$null;$e=$null;[void][Management.Automation.Language.Parser]::ParseFile("
                   + _ps_literal(p) + ",[ref]$t,[ref]$e);if(@($e).Count){throw 'SINTAXIS INCORRECTA'}\n")
    cuerpo += "'TRES SCRIPTS ANALIZADOS; NINGUNA TAREA EJECUTADA'\n"
    wrapper.write_text(cuerpo, encoding="utf-8-sig")
    proc = _ejecutar_powershell(tarea, wrapper, nombre="parser", timeout=30)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "TRES SCRIPTS ANALIZADOS" in proc.stdout



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


def test_migracion_desde_la_version_1_legitima_sin_duplicar_y_reversion(tarea):
    """La version 1 se instala con el script anterior archivado (PT5M e inicio de sesion) y se activa.
    El controlador nuevo la reconoce, no la activa ni la reinstala, la migra a la version 2 deshabilitada
    conservando su XML exportado (UTF-16LE con BOM) y la revierte deshabilitada desde ese XML."""
    _sesion(tarea, r'''
$r=Invoke-CasoV1 'v1-instalar' 'Instalar';$nombre=$r.tarea
$r=Invoke-CasoV1 'v1-activar' 'Activar';if(-not $r.habilitada){throw 'V1 NO ACTIVADA'}
$antes=$global:Tareas[$nombre].OuterXml
$r=Invoke-Caso 'no-activa-v1' 'Activar' 1
if($r.error -notmatch 'version anterior' -or $global:Tareas[$nombre].OuterXml -cne $antes){throw 'ACTIVA O CAMBIA LA V1'}
$r=Invoke-Caso 'no-instala-sobre-v1' 'Instalar'
if($r.estado -ne 'version_anterior_sin_reescribir_use_migrar' -or $global:Tareas[$nombre].OuterXml -cne $antes){throw 'REINSTALA SOBRE LA V1'}
$r=Invoke-Caso 'estado-v1' 'Estado';if($r.version_tarea -ne 1){throw 'V1 NO RECONOCIDA'}
$cuenta=$global:Llamadas.Count
$r=Invoke-Caso 'migrar' 'Migrar'
if($r.estado -ne 'migrada_deshabilitada' -or $r.habilitada -or $r.version_tarea -ne 2 -or -not $r.habilitada_antes){throw 'MIGRACION INCORRECTA'}
$despues=@($global:Llamadas | Select-Object -Skip $cuenta | Where-Object { $_ -in @('Enable','Disable','Register','Unregister') })
if(($despues -join ',') -ne 'Disable,Unregister,Register'){throw ('SECUENCIA '+($despues -join ','))}
$bytes=[IO.File]::ReadAllBytes([string]$r.xml_reversion)
if($bytes[0] -ne 0xFF -or $bytes[1] -ne 0xFE){throw 'XML DE REVERSION SIN BOM UTF-16LE'}
if($global:Tareas.Count -ne 1){throw 'DUPLICADO'}
$v2=$global:Tareas[$nombre]
if($v2.Task.Triggers.LogonTrigger -or $v2.Task.Triggers.TimeTrigger -or $v2.Task.Settings.StartWhenAvailable -ne 'false'){throw 'V2 CONSERVA DISPAROS ANTIGUOS'}
$r2=Invoke-Caso 'migrar-otra-vez' 'Migrar';if($r2.estado -ne 'ya_migrada_sin_reescribir'){throw 'NO IDEMPOTENTE'}
$r3=Invoke-Caso 'revertir' 'Revertir' 0 @{XmlAnterior=[string]$r.xml_reversion}
if($r3.estado -ne 'revertida_deshabilitada' -or $r3.habilitada -or $r3.version_tarea -ne 1){throw 'REVERSION INCORRECTA'}
$r4=Invoke-Caso 'desinstalar-v1' 'Desinstalar';if($global:Tareas.Count -ne 0){throw 'NO DESINSTALADA'}
''')


@pytest.mark.parametrize("caso", ["ciclo_vivo", "v1_alterada", "duplicado_activo", "xml_reversion_ajeno"])
def test_migracion_rechazada_sin_mutar(tarea, caso):
    preparar = {
        "ciclo_vivo": "$global:Viva=$true",
        "v1_alterada": "$global:Tareas[$nombre].Task.Triggers.TimeTrigger.Repetition.Interval='PT1M'",
        "duplicado_activo": ("$copia=[xml]$global:Tareas[$nombre].OuterXml;$copia.Task.Settings.Enabled='true';"
                             "$global:Tareas['LP6-otra-copia']=$copia"),
        "xml_reversion_ajeno": "",
    }[caso]
    accion = "Revertir" if caso == "xml_reversion_ajeno" else "Migrar"
    extra = ("@{XmlAnterior=(Join-Path $raizPrueba 'ajeno.xml')}" if caso == "xml_reversion_ajeno" else "@{}")
    _sesion(tarea, r'''
$r=Invoke-CasoV1 'v1-instalar' 'Instalar';$nombre=$r.tarea
[IO.File]::WriteAllText((Join-Path $raizPrueba 'ajeno.xml'),$global:Tareas[$nombre].OuterXml.Replace('ciclo<','ciclo --otro<'),(New-Object Text.UnicodeEncoding($false,$true,$true)))
''' + preparar + r'''
$antes=@{}; foreach($k in @($global:Tareas.Keys)){$antes[$k]=$global:Tareas[$k].OuterXml}
$cuenta=$global:Llamadas.Count
$r=Invoke-Caso 'rechazo' ''' + "'" + accion + "'" + r''' 1 ''' + extra + r'''
if($r.estado -ne 'error'){throw 'FALSO EXITO'}
foreach($k in $antes.Keys){if($global:Tareas[$k].OuterXml -cne $antes[$k]){throw 'TAREA MODIFICADA'}}
foreach($c in @($global:Llamadas | Select-Object -Skip $cuenta)){if($c -in @('Enable','Disable','Register','Unregister')){throw ('MUTACION '+$c)}}
''')


def test_tarea_v2_propia_se_reconoce_y_otro_espacio_de_nombres_se_rechaza(tarea):
    """F92-PS-01: el gestor de espacios de nombres usa la URI exacta de Task Scheduler (no una variable que
    PowerShell confunda con el propio gestor). Una tarea propia se reconoce; la misma con otra URI no."""
    _sesion(tarea, r'''
$r=Invoke-Caso 'instalar' 'Instalar';$nombre=$r.tarea
if($r.estado -ne 'instalada_deshabilitada' -or $r.version_tarea -ne 2){throw ('V2 NO RECONOCIDA: '+$r.error)}
$r=Invoke-Caso 'estado' 'Estado';if($r.version_tarea -ne 2){throw 'ESTADO SIN VERSION 2'}
$global:Tareas[$nombre]=[xml]$global:Tareas[$nombre].OuterXml.Replace('http://schemas.microsoft.com/windows/2004/02/mit/task','http://ejemplo.invalido/task')
$antes=$global:Tareas[$nombre].OuterXml;$cuenta=$global:Llamadas.Count
$r=Invoke-Caso 'otro-espacio' 'Activar' 1
if($r.error -notmatch 'seccion unica requerida: /t:Task'){throw ('RECHAZO INESPERADO: '+$r.error)}
if($global:Tareas[$nombre].OuterXml -cne $antes){throw 'TAREA AJENA MODIFICADA'}
foreach($c in @($global:Llamadas | Select-Object -Skip $cuenta)){if($c -in @('Enable','Disable','Register','Unregister')){throw ('MUTACION '+$c)}}
''')


# F92-CI-01: SHA-256 con .NET sobre los bytes originales del archivo, sin Get-FileHash, que el
# Windows PowerShell 5.1 del CI de Windows no resolvió. Devuelve el mismo texto que Get-FileHash
# (hexadecimal en mayúsculas) y libera el archivo y el algoritmo aunque falle la lectura.
_SHA256_ARCHIVO = r'''
function Get-Sha256Archivo([string]$Ruta) {
    if (-not [IO.Path]::IsPathRooted($Ruta)) { throw ('RUTA NO ABSOLUTA PARA SHA-256: ' + $Ruta) }
    $flujo=$null; $algoritmo=$null
    try {
        $flujo=[IO.File]::Open($Ruta,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
        $algoritmo=[Security.Cryptography.SHA256]::Create()
        return [BitConverter]::ToString($algoritmo.ComputeHash($flujo)).Replace('-','')
    } finally {
        if ($null -ne $algoritmo) { $algoritmo.Dispose() }
        if ($null -ne $flujo) { $flujo.Dispose() }
    }
}
'''


# F92-REV-01: la reversión registra siempre una copia validada y deshabilitada del XML archivado,
# vuelve a comprobar propiedad y ciclo vivo tras pausar y antes de retirar, y no activa tareas ni
# pierde la versión vigente si el registro falla. Los mocks anotan cada alta y cada baja.
_REVERSION = _SHA256_ARCHIVO + r'''
$global:Altas=@();$global:BajasVivas=@();$global:Carrera=$false;$global:FallarFuente=@()
function Register-ScheduledTask {
    [CmdletBinding()]param([string]$TaskName,[string]$TaskPath,[string]$Xml)
    [void]$global:Llamadas.Add('Register')
    $alta=[xml]$Xml
    $global:Altas+=@([pscustomobject]@{fuente=[string]$alta.Task.RegistrationInfo.Source;habilitada=([string]$alta.Task.Settings.Enabled -ne 'false')})
    if ([string]$alta.Task.RegistrationInfo.Source -in $global:FallarFuente) { throw 'REGISTRO RECHAZADO POR EL PROGRAMADOR SIMULADO' }
    if ($global:Tareas.ContainsKey($TaskName)) {throw 'TAREA EXISTENTE NO SE SOBRESCRIBE'}
    $global:Tareas[$TaskName]=$alta
}
function Disable-ScheduledTask {
    [CmdletBinding()]param([string]$TaskName,[string]$TaskPath)
    [void]$global:Llamadas.Add('Disable')
    $global:Tareas[$TaskName].Task.Settings.Enabled='false'
    if ($global:Carrera) { $global:Viva=$true }
}
function Unregister-ScheduledTask {
    [CmdletBinding(SupportsShouldProcess=$true)]param([string]$TaskName,[string]$TaskPath)
    [void]$global:Llamadas.Add('Unregister')
    $global:BajasVivas+=@([bool]$global:Viva)
    $global:Tareas.Remove($TaskName)
}
$r=Invoke-CasoV1 'v1-instalar' 'Instalar';$nombre=$r.tarea
$r=Invoke-CasoV1 'v1-activar' 'Activar';if(-not $r.habilitada){throw 'V1 NO ACTIVADA'}
$migrada=Invoke-Caso 'migrar' 'Migrar';$xmlV1=[string]$migrada.xml_reversion
if(([xml][IO.File]::ReadAllText($xmlV1,[Text.Encoding]::Unicode)).Task.Settings.Enabled -ne 'true'){throw 'LA EXPORTACION ARCHIVADA DEBIA SER LA V1 HABILITADA'}
$shaV1=Get-Sha256Archivo $xmlV1
$global:Altas=@();$global:BajasVivas=@();$cuenta=$global:Llamadas.Count
function Assert-SinAltaHabilitada { foreach($a in $global:Altas){ if($a.habilitada){ throw ('ALTA HABILITADA de '+$a.fuente) } } }
function Assert-OriginalIntacto { if((Get-Sha256Archivo $xmlV1) -ne $shaV1){ throw 'EXPORTACION ORIGINAL MODIFICADA' } }
'''


def test_reversion_desde_xml_habilitado_registra_una_copia_deshabilitada(tarea):
    _sesion(tarea, _REVERSION + r'''
$r=Invoke-Caso 'revertir' 'Revertir' 0 @{XmlAnterior=$xmlV1}
if($r.estado -ne 'revertida_deshabilitada' -or $r.habilitada -or $r.version_tarea -ne 1){throw ('REVERSION: '+$r.estado+' '+$r.error)}
Assert-SinAltaHabilitada; Assert-OriginalIntacto
if(@($global:Altas).Count -ne 1 -or $global:Altas[0].fuente -ne 'LoteriaPredictor/Fase6/tarea/1'){throw 'ALTAS INESPERADAS'}
if(@($global:BajasVivas) -contains $true){throw 'BAJA CON CICLO VIVO'}
$copia=[string]$r.xml_registrado
$bytes=[IO.File]::ReadAllBytes($copia);if($bytes[0] -ne 0xFF -or $bytes[1] -ne 0xFE){throw 'COPIA SIN UTF-16LE CON BOM'}
if(([xml][IO.File]::ReadAllText($copia,[Text.Encoding]::Unicode)).Task.Settings.Enabled -ne 'false'){throw 'COPIA NO DESHABILITADA'}
if([string]$r.xml_reversion -ne $xmlV1 -or $r.xml_reversion_sha256 -ne $shaV1.ToLowerInvariant()){throw 'ORIGEN NO DOCUMENTADO'}
$secuencia=@($global:Llamadas | Select-Object -Skip $cuenta | Where-Object { $_ -in @('Enable','Disable','Register','Unregister') })
if(($secuencia -join ',') -ne 'Disable,Unregister,Register'){throw ('SECUENCIA '+($secuencia -join ','))}
$r2=Invoke-Caso 'revertir-otra-vez' 'Revertir' 0 @{XmlAnterior=$xmlV1}
if($r2.estado -ne 'ya_version_anterior_sin_reescribir' -or $r2.habilitada){throw 'REVERSION NO IDEMPOTENTE'}
if(@($global:Altas).Count -ne 1){throw 'LA REPETICION REGISTRO OTRA VEZ'}
''')


def test_reversion_con_ciclo_que_arranca_al_pausar_no_retira_la_tarea_viva(tarea):
    _sesion(tarea, _REVERSION + r'''
$global:Carrera=$true
$r=Invoke-Caso 'revertir-carrera' 'Revertir' 1 @{XmlAnterior=$xmlV1}
if($r.error -notmatch 'ciclo empezo durante la reversion'){throw ('ERROR INESPERADO: '+$r.error)}
if(@($global:BajasVivas).Count -ne 0 -or @($global:Altas).Count -ne 0){throw 'RETIRO O REGISTRO CON CICLO VIVO'}
$v2=$global:Tareas[$nombre];if($v2.Task.RegistrationInfo.Source -ne 'LoteriaPredictor/Fase6/tarea/2' -or $v2.Task.Settings.Enabled -ne 'false'){throw 'LA V2 NO QUEDO DESHABILITADA Y CONSERVADA'}
Assert-OriginalIntacto
''')


def test_reversion_con_fallo_de_registro_restaura_la_v2_deshabilitada(tarea):
    _sesion(tarea, _REVERSION + r'''
$global:FallarFuente=@('LoteriaPredictor/Fase6/tarea/1')
$r=Invoke-Caso 'revertir-fallo' 'Revertir' 1 @{XmlAnterior=$xmlV1}
if($r.error -notmatch 'se restauro la version 2 deshabilitada'){throw ('ERROR INESPERADO: '+$r.error)}
Assert-SinAltaHabilitada; Assert-OriginalIntacto
if((@($global:Altas) | ForEach-Object { $_.fuente }) -join ',' -ne 'LoteriaPredictor/Fase6/tarea/1,LoteriaPredictor/Fase6/tarea/2'){throw 'ALTAS INESPERADAS'}
$v2=$global:Tareas[$nombre];if($v2.Task.RegistrationInfo.Source -ne 'LoteriaPredictor/Fase6/tarea/2' -or $v2.Task.Settings.Enabled -ne 'false'){throw 'V2 NO RESTAURADA DESHABILITADA'}
$e=Invoke-Caso 'estado-tras-fallo' 'Estado';if($e.version_tarea -ne 2 -or $e.habilitada){throw 'ESTADO TRAS EL FALLO'}
''')


def test_reversion_con_doble_fallo_de_registro_deja_los_xml_sin_activar_nada(tarea):
    _sesion(tarea, _REVERSION + r'''
$global:FallarFuente=@('LoteriaPredictor/Fase6/tarea/1','LoteriaPredictor/Fase6/tarea/2')
$r=Invoke-Caso 'revertir-doble-fallo' 'Revertir' 1 @{XmlAnterior=$xmlV1}
if($r.error -notmatch 'ni se restauro la version 2'){throw ('ERROR INESPERADO: '+$r.error)}
Assert-SinAltaHabilitada; Assert-OriginalIntacto
if($global:Tareas.ContainsKey($nombre)){throw 'TAREA INESPERADA'}
foreach($ruta in @([string]$r.xml_registrado,[string]$r.xml_restauracion)){
    if(-not (Test-Path -LiteralPath $ruta)){throw ('FALTA EVIDENCIA '+$ruta)}
    if($r.error -notmatch [regex]::Escape($ruta)){throw ('EL ERROR NO CITA '+$ruta)}
    if(([xml][IO.File]::ReadAllText($ruta,[Text.Encoding]::Unicode)).Task.Settings.Enabled -ne 'false'){throw ('EVIDENCIA HABILITADA '+$ruta)}
}
''')


def test_reversion_sin_tarea_registra_la_copia_deshabilitada(tarea):
    _sesion(tarea, _REVERSION + r'''
$global:Tareas.Remove($nombre)
$r=Invoke-Caso 'revertir-sin-tarea' 'Revertir' 0 @{XmlAnterior=$xmlV1}
if($r.estado -ne 'revertida_deshabilitada' -or $r.habilitada -or $r.version_tarea -ne 1){throw ('REVERSION: '+$r.estado+' '+$r.error)}
Assert-SinAltaHabilitada; Assert-OriginalIntacto
''')


# Sustituto que falla como cuando el CI de Windows no resolvió Get-FileHash: una función de la sesión
# tiene precedencia sobre el comando del módulo, así que cualquier uso restante lo delataría.
_SIN_GET_FILEHASH = "function Get-FileHash { throw 'GET-FILEHASH NO DISPONIBLE' }\n"


def test_sha256_de_prueba_coincide_con_hashlib_y_detecta_un_byte_alterado(tarea):
    """F92-CI-01: el ayudante da la misma huella que hashlib sobre los bytes del archivo, sin
    Get-FileHash. Un solo byte distinto cambia la huella; el archivo queda liberado y sin cambios."""
    carpeta = tarea["raiz"] / "huellas con espacios y ñ"
    carpeta.mkdir()
    binario = bytes(range(256)) * 300  # varios bloques de lectura
    alterado = bytearray(binario)
    alterado[40_000] ^= 0x01
    muestras = {"vacio.bin": b"", "exportada utf16.xml": "﻿<Task>ñ</Task>\r\n".encode("utf-16-le"),
                "binario.bin": binario, "binario alterado.bin": bytes(alterado)}
    for nombre, contenido in muestras.items():
        (carpeta / nombre).write_bytes(contenido)
    salida = tarea["raiz"] / "huellas.json"
    _sesion(tarea, _SIN_GET_FILEHASH + _SHA256_ARCHIVO + r'''
$huellas=[ordered]@{}
foreach($a in @(Get-ChildItem -LiteralPath ''' + _ps_literal(carpeta) + r''' -File | Sort-Object Name)){
    $huellas[$a.Name]=Get-Sha256Archivo $a.FullName
    $exclusivo=[IO.File]::Open($a.FullName,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None); $exclusivo.Dispose()
}
$relativa=$false; try { Get-Sha256Archivo 'relativa.bin' | Out-Null } catch { $relativa=$_.Exception.Message -match 'RUTA NO ABSOLUTA' }
if(-not $relativa){throw 'RUTA RELATIVA ACEPTADA'}
[IO.File]::WriteAllText(''' + _ps_literal(salida) + r''',($huellas | ConvertTo-Json),(New-Object Text.UTF8Encoding($false)))
''')
    huellas = json.loads(salida.read_text(encoding="utf-8"))
    assert huellas == {n: hashlib.sha256(c).hexdigest().upper() for n, c in muestras.items()}
    assert huellas["binario.bin"] != huellas["binario alterado.bin"]
    assert {n: (carpeta / n).read_bytes() for n in muestras} == muestras


def test_reversion_compara_el_xml_original_sin_get_filehash(tarea):
    """F92-CI-01: el preámbulo de la reversión no depende de Get-FileHash. La huella del XML original
    coincide con hashlib y Assert-OriginalIntacto detecta un byte alterado y acepta los bytes restaurados."""
    salida = tarea["raiz"] / "huella-v1.json"
    _sesion(tarea, _SIN_GET_FILEHASH + _REVERSION + r'''
Assert-OriginalIntacto
[IO.File]::WriteAllText(''' + _ps_literal(salida) + r''',(@{xml=$xmlV1;sha256=$shaV1} | ConvertTo-Json),(New-Object Text.UTF8Encoding($false)))
$original=[IO.File]::ReadAllBytes($xmlV1)
$alterado=[byte[]]$original.Clone(); $alterado[$alterado.Length-2]=$alterado[$alterado.Length-2] -bxor 1
[IO.File]::WriteAllBytes($xmlV1,$alterado)
$detectada=$false; try { Assert-OriginalIntacto } catch { $detectada=$_.Exception.Message -eq 'EXPORTACION ORIGINAL MODIFICADA' }
if(-not $detectada){throw 'ALTERACION DEL XML ORIGINAL NO DETECTADA'}
[IO.File]::WriteAllBytes($xmlV1,$original); Assert-OriginalIntacto
''')
    datos = json.loads(salida.read_text(encoding="utf-8"))
    assert datos["sha256"] == hashlib.sha256(Path(datos["xml"]).read_bytes()).hexdigest().upper()
    assert "Get-FileHash" not in _REVERSION


# F92-NAT-01: el Programador nativo registra la v2 con StartWhenAvailable=false y la exporta sin el
# elemento: el esquema permite omitirlo y su predeterminado documentado es false. La omisión vale ese
# false, nunca «el valor esperado»: una v1, que exige true, sigue rechazándose. Las exportaciones se
# archivan tal cual (UTF-16LE con BOM), sin insertar el campo.
_NATIVO_SWA = r'''
function Register-ScheduledTask {
    [CmdletBinding()]param([string]$TaskName,[string]$TaskPath,[string]$Xml)
    [void]$global:Llamadas.Add('Register')
    if ($global:Tareas.ContainsKey($TaskName)) {throw 'TAREA EXISTENTE NO SE SOBRESCRIBE'}
    $alta=[xml]$Xml
    if ($global:OmitirSwaFalse) {
        # Como el Programador nativo: el predeterminado false no aparece en la exportación.
        foreach($n in @($alta.Task.Settings.ChildNodes | Where-Object { $_.LocalName -eq 'StartWhenAvailable' -and $_.InnerText -eq 'false' })) { [void]$alta.Task.Settings.RemoveChild($n) }
    }
    $global:Tareas[$TaskName]=$alta
}
function Set-SwaExportado([string]$Nombre,[string[]]$Valores) {
    # Sin valores: omitido. Varios: duplicado. '__anidado__': elemento con un hijo.
    $doc=$global:Tareas[$Nombre]; $ajustes=$doc.Task.Settings; $uri=$doc.DocumentElement.NamespaceURI
    foreach($n in @($ajustes.ChildNodes | Where-Object { $_.LocalName -eq 'StartWhenAvailable' })) { [void]$ajustes.RemoveChild($n) }
    foreach($v in @($Valores)) {
        $e=$doc.CreateElement('StartWhenAvailable',$uri)
        if ($v -ceq '__anidado__') { $h=$doc.CreateElement('Valor',$uri); $h.InnerText='false'; [void]$e.AppendChild($h) } else { $e.InnerText=$v }
        [void]$ajustes.AppendChild($e)
    }
}
function Get-FilaSwa([string]$Carpeta) {
    $d=Get-Content -LiteralPath (@(Get-ChildItem -LiteralPath $Carpeta -Filter 'validacion-*.json')[-1].FullName) -Raw -Encoding UTF8 | ConvertFrom-Json
    return @($d.campos | Where-Object { $_.ruta -eq '/t:Task/t:Settings/t:StartWhenAvailable' })
}
function Assert-SinMutacion([string]$Nombre,[string]$Antes,[int]$Cuenta) {
    if (-not $global:Tareas.ContainsKey($Nombre) -or $global:Tareas[$Nombre].OuterXml -cne $Antes) { throw 'TAREA NO CONSERVADA' }
    foreach($c in @($global:Llamadas | Select-Object -Skip $Cuenta)) { if ($c -in @('Enable','Disable','Register','Unregister')) { throw ('MUTACION '+$c) } }
}
$global:OmitirSwaFalse=$false
'''


def test_v2_cuya_exportacion_omite_start_when_available_se_valida_consulta_y_retira(tarea):
    """F92-NAT-01: instalación, Estado y retirada de una v2 propia deshabilitada cuya exportación omite
    el campo, con el origen `predeterminado_documentado` y el valor `false` en el diagnóstico."""
    _sesion(tarea, _NATIVO_SWA + r'''
$global:OmitirSwaFalse=$true
$r=Invoke-Caso 'instalar' 'Instalar'
if($r.estado -ne 'instalada_deshabilitada' -or $r.version_tarea -ne 2 -or $r.habilitada){throw ('INSTALACION: '+$r.estado+' '+$r.error)}
$nombre=$r.tarea
if(@($global:Tareas[$nombre].Task.Settings.ChildNodes | Where-Object { $_.LocalName -eq 'StartWhenAvailable' }).Count -ne 0){throw 'EL SUSTITUTO NO OMITIO EL CAMPO'}
$e=Invoke-Caso 'estado' 'Estado'
if($e.estado -ne 'consultada' -or $e.version_tarea -ne 2 -or $e.habilitada){throw ('ESTADO: '+$e.estado+' '+$e.error)}
$f=@(Get-FilaSwa (Join-Path $raizPrueba 'estado'))
if($f.Count -ne 1 -or $f[0].origen -ne 'predeterminado_documentado' -or $f[0].valor_semantico -ne $false -or -not $f[0].coincide -or $null -ne $f[0].valor_xml){throw 'DIAGNOSTICO SIN PREDETERMINADO DOCUMENTADO FALSE'}
$exportada=@(Get-ChildItem -LiteralPath (Join-Path $raizPrueba 'estado') -Filter 'exportada-*.xml')[0].FullName
$bytes=[IO.File]::ReadAllBytes($exportada);if($bytes[0] -ne 0xFF -or $bytes[1] -ne 0xFE){throw 'EXPORTACION SIN UTF-16LE CON BOM'}
$texto=[IO.File]::ReadAllText($exportada,[Text.Encoding]::Unicode)
if($texto -cne $global:Tareas[$nombre].OuterXml -or $texto.Contains('StartWhenAvailable')){throw 'EXPORTACION NORMALIZADA O CON EL CAMPO INSERTADO'}
$d=Invoke-Caso 'desinstalar' 'Desinstalar'
if($d.estado -ne 'desinstalada' -or $global:Tareas.ContainsKey($nombre)){throw 'NO SE RETIRO LA V2 PROPIA'}
$a=Invoke-Caso 'ausente' 'Estado';if($a.estado -ne 'no_instalada'){throw 'AUSENCIA NO CONFIRMADA'}
''')


@pytest.mark.parametrize("caso", ["viva", "ajena"])
def test_v2_viva_o_ajena_que_omite_start_when_available_se_conserva(tarea, caso):
    preparar = {"viva": "$global:Viva=$true",
                "ajena": "$global:Tareas[$nombre].Task.Actions.Exec.Arguments=[string]$global:Tareas[$nombre].Task.Actions.Exec.Arguments+' --otro'"}[caso]
    error = {"viva": "ciclo vivo", "ajena": "ajena o modificada"}[caso]
    _sesion(tarea, _NATIVO_SWA + r'''
$global:OmitirSwaFalse=$true
$r=Invoke-Caso 'instalar' 'Instalar';$nombre=$r.tarea
''' + preparar + r'''
$antes=$global:Tareas[$nombre].OuterXml;$cuenta=$global:Llamadas.Count
$r=Invoke-Caso 'retirar' 'Desinstalar' 1
if($r.error -notmatch ''' + "'" + error + "'" + r'''){throw ('RECHAZO INESPERADO: '+$r.error)}
Assert-SinMutacion $nombre $antes $cuenta
''')


@pytest.mark.parametrize("valores, aceptado", [
    ([], True), (["false"], True), (["0"], True),
    (["true"], False), (["1"], False), (["false", "false"], False), ([""], False),
    (["__anidado__"], False), (["si"], False),
], ids=["omitido", "false", "cero", "true", "uno", "duplicado", "vacio", "anidado", "no_booleano"])
def test_valores_de_start_when_available_en_una_v2_exportada(tarea, valores, aceptado):
    """Ausencia, `false` y `0` valen false y se aceptan; `true`, `1`, duplicados, vacío, contenido no
    escalar y valores no booleanos se rechazan sin mutar la tarea (también al intentar activarla)."""
    lista = "@(" + ",".join("'" + v + "'" for v in valores) + ")"
    cuerpo = _NATIVO_SWA + r'''
$r=Invoke-Caso 'instalar' 'Instalar';$nombre=$r.tarea
Set-SwaExportado $nombre ''' + lista + r'''
$antes=$global:Tareas[$nombre].OuterXml;$cuenta=$global:Llamadas.Count
'''
    if aceptado:
        cuerpo += r'''
$e=Invoke-Caso 'estado' 'Estado'
if($e.version_tarea -ne 2 -or $e.habilitada){throw ('NO ACEPTADA: '+$e.error)}
$f=@(Get-FilaSwa (Join-Path $raizPrueba 'estado'))
if($f.Count -ne 1 -or $f[0].valor_semantico -ne $false -or -not $f[0].coincide){throw 'VALOR SEMANTICO DISTINTO DE FALSE'}
Assert-SinMutacion $nombre $antes $cuenta
'''
    else:
        cuerpo += r'''
$e=Invoke-Caso 'estado' 'Estado' 1
if($e.error -notmatch 'StartWhenAvailable'){throw ('RECHAZO INESPERADO: '+$e.error)}
$a=Invoke-Caso 'activar' 'Activar' 1
if($a.error -notmatch 'StartWhenAvailable'){throw ('ACTIVACION NO RECHAZADA POR EL CAMPO: '+$a.error)}
Assert-SinMutacion $nombre $antes $cuenta
'''
    _sesion(tarea, cuerpo)


def test_v1_que_omite_start_when_available_no_se_acepta_como_true(tarea):
    """La v1 exige StartWhenAvailable=true: si falta, vale el predeterminado false y no coincide."""
    _sesion(tarea, _NATIVO_SWA + r'''
$r=Invoke-CasoV1 'v1-instalar' 'Instalar';$nombre=$r.tarea
Set-SwaExportado $nombre @()
$antes=$global:Tareas[$nombre].OuterXml;$cuenta=$global:Llamadas.Count
foreach($accion in @('Estado','Migrar','Pausar')){
    $e=Invoke-Caso ('v1-'+$accion) $accion 1
    if($e.error -notmatch 'StartWhenAvailable'){throw ('V1 SIN EL CAMPO ACEPTADA EN '+$accion+': '+$e.error)}
}
Assert-SinMutacion $nombre $antes $cuenta
''')
