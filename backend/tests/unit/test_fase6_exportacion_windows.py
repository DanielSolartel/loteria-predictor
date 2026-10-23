"""Exportación nativa parametrizada; PS real con Programador/identidades simulados.

La fixture conserva la estructura observada en Windows, incluidos elementos
omitidos, pero sustituye nombres, SID, rutas y vinculación por valores del caso.
Solo la copia de ensayo reemplaza Get-UsuarioActual y Resolver-IdentidadSid por
AST. No se instala una tarea ni se acredita resolución nativa de Windows aquí.
"""
from __future__ import annotations

import codecs
import hashlib
import json
import os
from pathlib import Path
import zipfile

import pytest

from tests.unit.test_fase6_tarea_windows import _ejecutar_powershell, _ps_literal, tarea

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/windows/fase6_tarea.ps1"
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/fase6/tarea-exportada-nativa.xml"
SID = "S-1-5-21-101-202-303-1001"
OTRO_SID = "S-1-5-21-404-505-606-1002"

CABECERA = r'''
$ErrorActionPreference='Stop'
$global:SidSimulado=__SID__
$global:CuentaSimulada=__CUENTA__
$global:OtroSidSimulado=__OTRO_SID__
$global:XmlTarea=$null
$global:Viva=$false
$global:ExportacionMalformada=$false
$global:ErrorExportacion=$false
$global:Controles=New-Object Collections.Generic.List[string]
$global:Resultados=New-Object Collections.Generic.List[object]
$global:AlterarAlRegistrar=__ALTERAR__
$original=__SCRIPT__
$scriptPrueba=Join-Path __RAIZ__ 'controlador-parametrizado.ps1'
$tokens=$null;$errores=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($original,[ref]$tokens,[ref]$errores)
if(@($errores).Count){throw 'SINTAXIS DEL CONTROLADOR ORIGINAL'}
$reemplazos=@{
 'Get-UsuarioActual'=@'
function Get-UsuarioActual {
 return [pscustomobject]@{Id=$global:SidSimulado;Nombre=$global:CuentaSimulada;Plataforma='Windows_simulado_en_fixture'}
}
'@
 'Resolver-IdentidadSid'=@'
function Resolver-IdentidadSid([string]$Identidad) {
 if($Identidad -eq $global:SidSimulado -or $Identidad -eq $global:CuentaSimulada){return $global:SidSimulado}
 if($Identidad -eq $global:OtroSidSimulado -or $Identidad -eq 'OTROEQUIPO\otro'){return $global:OtroSidSimulado}
 throw 'Identidad no resoluble por el resolvedor simulado del ensayo'
}
'@
}
$texto=[IO.File]::ReadAllText($original)
$funciones=@($ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst]},$true) | Where-Object{$reemplazos.ContainsKey($_.Name)} | Sort-Object { $_.Extent.StartOffset } -Descending)
if(@($funciones|Where-Object{$_.Name -eq 'Get-UsuarioActual'}).Count -ne 1){throw 'FALTA SEAM DE IDENTIDAD EN FIXTURE'}
foreach($f in $funciones){$texto=$texto.Remove($f.Extent.StartOffset,$f.Extent.EndOffset-$f.Extent.StartOffset).Insert($f.Extent.StartOffset,[string]$reemplazos[$f.Name])}
[IO.File]::WriteAllText($scriptPrueba,$texto,(New-Object Text.UTF8Encoding($true,$true)))
$raiz=__RAIZ__
$comun=@{Worktree=__REPO__;PythonExe=__PYTHON__;Configuracion=__CONFIG__}
function Get-Ns([xml]$x){$n=New-Object Xml.XmlNamespaceManager($x.NameTable);$n.AddNamespace('t','http://schemas.microsoft.com/windows/2004/02/mit/task');return ,$n}
function Set-Campo([xml]$x,[string]$ruta,[string]$valor){$n=Get-Ns $x;$x.SelectSingleNode($ruta,$n).InnerText=$valor}
function Add-Campo([xml]$x,[string]$padre,[string]$nombre,[string]$valor){$n=Get-Ns $x;$e=$x.CreateElement($nombre,'http://schemas.microsoft.com/windows/2004/02/mit/task');$e.InnerText=$valor;[void]$x.SelectSingleNode($padre,$n).AppendChild($e)}
function Remove-Campo([xml]$x,[string]$ruta){$n=Get-Ns $x;$e=$x.SelectSingleNode($ruta,$n);[void]$e.ParentNode.RemoveChild($e)}
function New-Exportacion([string]$Plan){
 $p=[xml]$Plan
 $x=[xml][IO.File]::ReadAllText(__FIXTURE__,[Text.Encoding]::Unicode)
 $n=Get-Ns $x
 foreach($ruta in @('/t:Task/t:RegistrationInfo/t:Description','/t:Task/t:RegistrationInfo/t:URI','/t:Task/t:Actions/t:Exec/t:Command','/t:Task/t:Actions/t:Exec/t:Arguments','/t:Task/t:Actions/t:Exec/t:WorkingDirectory','/t:Task/t:Triggers/t:TimeTrigger/t:StartBoundary')){
  $pn=Get-Ns $p;Set-Campo $x $ruta ([string]$p.SelectSingleNode($ruta,$pn).InnerText)
 }
 Set-Campo $x '/t:Task/t:RegistrationInfo/t:Author' $global:CuentaSimulada
 Set-Campo $x '/t:Task/t:Principals/t:Principal/t:UserId' $global:SidSimulado
 Set-Campo $x '/t:Task/t:Triggers/t:LogonTrigger/t:UserId' $global:CuentaSimulada
 if($global:AlterarAlRegistrar){& ([scriptblock]::Create("param(`$x)`n"+$global:AlterarAlRegistrar)) $x}
 return $x.OuterXml
}
function Get-ScheduledTask {
 [CmdletBinding()]param([string]$TaskName,[string]$TaskPath)
 [void]$global:Controles.Add('Get')
 if($null -eq $global:XmlTarea){return $null}
 $x=[xml]$global:XmlTarea;$n=Get-Ns $x;$habilitada=[Xml.XmlConvert]::ToBoolean([string]$x.SelectSingleNode('/t:Task/t:Settings/t:Enabled',$n).InnerText)
 return [pscustomobject]@{TaskName=$TaskName;Settings=[pscustomobject]@{Enabled=$habilitada};State=$(if($global:Viva){'Running'}elseif($habilitada){'Ready'}else{'Disabled'})}
}
function Export-ScheduledTask {
 [CmdletBinding()]param([string]$TaskName,[string]$TaskPath)
 [void]$global:Controles.Add('Export')
 if($global:ErrorExportacion){throw 'PERMISO_EXPORTACION'}
 if($global:ExportacionMalformada){return '<Task><no-cerrado>'}
 return $global:XmlTarea
}
function Register-ScheduledTask {
 [CmdletBinding()]param([string]$TaskName,[string]$TaskPath,[string]$Xml)
 [void]$global:Controles.Add('Register')
 if($null -ne $global:XmlTarea){throw 'NO SOBRESCRIBIR TAREA'}
 $global:XmlTarea=New-Exportacion $Xml
}
function Disable-ScheduledTask {
 [CmdletBinding()]param([string]$TaskName,[string]$TaskPath)
 [void]$global:Controles.Add('Disable');$x=[xml]$global:XmlTarea;Set-Campo $x '/t:Task/t:Settings/t:Enabled' 'false';$global:XmlTarea=$x.OuterXml
}
function Enable-ScheduledTask {
 [CmdletBinding()]param([string]$TaskName,[string]$TaskPath)
 [void]$global:Controles.Add('Enable');$x=[xml]$global:XmlTarea;Set-Campo $x '/t:Task/t:Settings/t:Enabled' 'true';$global:XmlTarea=$x.OuterXml
}
function Unregister-ScheduledTask {
 [CmdletBinding(SupportsShouldProcess=$true)]param([string]$TaskName,[string]$TaskPath)
 [void]$global:Controles.Add('Unregister');$global:XmlTarea=$null
}
function Invoke-Caso([string]$Nombre,[string]$Accion,[int]$Esperado=0){
 $e=Join-Path (Join-Path $raiz 'puntos') $Nombre
 $a=@{};foreach($k in $comun.Keys){$a[$k]=$comun[$k]};$a.Evidencia=$e;$a[$Accion]=$true
 & $scriptPrueba @a | Out-Host
 $codigo=$LASTEXITCODE
 $r=Get-Content -LiteralPath (Join-Path $e 'resultado.json') -Raw -Encoding UTF8|ConvertFrom-Json
 [void]$global:Resultados.Add($r)
 if($codigo -ne $Esperado){throw ('CODIGO INESPERADO EN '+$Nombre+': '+$codigo+'; '+[string]$r.error)}
 return $r
}
'''


def _archivar(tarea):
    """Conservar diagnóstico/XML aunque una aserción posterior falle."""
    carpeta = Path(os.environ.get("FASE4_EVIDENCIA") or tarea["raiz"])
    carpeta.mkdir(parents=True, exist_ok=True)
    clave = hashlib.sha256(os.environ.get("PYTEST_CURRENT_TEST", "sin_pytest").encode("utf-8")).hexdigest()[:16]
    contenido = {}
    for p in (tarea["raiz"] / "puntos").rglob("*"):
        if p.is_file() and p.suffix in (".xml", ".json", ".log"):
            contenido["puntos/" + p.relative_to(tarea["raiz"] / "puntos").as_posix()] = p.read_bytes()
    traza = tarea["raiz"] / "traza-exportacion.json"
    if traza.exists():
        contenido[traza.name] = traza.read_bytes()
    inv = {"tipo": "exportacion_nativa_parametrizada_con_controlador_simulado", "caso": os.environ.get("PYTEST_CURRENT_TEST"),
           "archivos": [{"ruta": n, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()} for n, b in sorted(contenido.items())]}
    contenido["inventario.json"] = (json.dumps(inv, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with zipfile.ZipFile(carpeta / ("export-" + clave + ".zip"), "w", zipfile.ZIP_DEFLATED) as z:
        for n, b in sorted(contenido.items()):
            z.writestr(n, b)


def _ejecutar(tarea, cuerpo, *, cuenta="EQUIPO-A\\ana", sid=SID, alteracion=""):
    fuente = Path(os.environ.get("FASE6_CONTROLADOR_PRUEBAS") or SCRIPT)
    cabecera = CABECERA
    valores = {"SID": sid, "CUENTA": cuenta, "OTRO_SID": OTRO_SID, "ALTERAR": alteracion,
               "SCRIPT": fuente, "RAIZ": tarea["raiz"], "REPO": tarea["repo"], "PYTHON": tarea["python"],
               "CONFIG": tarea["config"], "FIXTURE": FIXTURE}
    for nombre, valor in valores.items():
        cabecera = cabecera.replace("__" + nombre + "__", _ps_literal(valor))
    wrapper = tarea["raiz"] / "exportacion-simulada.ps1"
    wrapper.write_text(cabecera + "\ntry {\n" + cuerpo + r'''
} finally {
 $r=@{resultados=@($global:Resultados.ToArray());controles=@($global:Controles.ToArray());xml_final=$global:XmlTarea;limite='Programador y SID simulados; no Windows nativo'}
 [IO.File]::WriteAllText((Join-Path $raiz 'traza-exportacion.json'),(($r|ConvertTo-Json -Depth 24)+"`n"),(New-Object Text.UTF8Encoding($false,$true)))
}
exit 0
''', encoding="utf-8-sig")
    p = _ejecutar_powershell(tarea, wrapper, nombre="exportacion", timeout=90)
    _archivar(tarea)
    assert p.returncode == 0, p.stdout + p.stderr
    return json.loads((tarea["raiz"] / "traza-exportacion.json").read_text(encoding="utf-8"))


def _assert_exportaciones(tarea, resultados, *, algun_rechazo=False):
    exportaciones = []
    for resultado in resultados:
        for fila in resultado.get("exportaciones", []):
            archivo = Path(fila["xml"])
            diagnostico = Path(fila["diagnostico"])
            raw = archivo.read_bytes()
            assert raw.startswith(codecs.BOM_UTF16_LE)
            texto = raw.decode("utf-16", errors="strict")
            assert raw == codecs.BOM_UTF16_LE + texto.encode("utf-16le", errors="strict")
            d = json.loads(diagnostico.read_text(encoding="utf-8"))
            assert d["tipo"] == "validacion_tarea_exportada"
            assert d["exportacion_xml"] == str(archivo)
            assert d["bytes_exportacion"] == len(raw)
            assert d["sha256_exportacion"] == hashlib.sha256(raw).hexdigest()
            assert d["estado"] in ("aprobada", "rechazada")
            exportaciones.append((archivo, texto, d))
    assert exportaciones, "Cada consulta/registro debe conservar su exportación real antes de validarla"
    assert len({str(p) for p, _, _ in exportaciones}) == len(exportaciones), "No sobrescribir exportaciones anteriores"
    if algun_rechazo:
        assert any(d["estado"] == "rechazada" for _, _, d in exportaciones)
    return exportaciones


@pytest.mark.parametrize(("cuenta", "sid"), [("EQUIPO-A\\ana", SID), ("MÁQUINA-B\\zoë", "S-1-5-21-909-808-707-1003")])
def test_exportacion_nativa_equivalente_instala_deshabilitada_y_ciclo_idempotente(tarea, cuenta, sid):
    traza = _ejecutar(tarea, r'''
$r=Invoke-Caso 'instalar' 'Instalar';if($r.habilitada -or $r.estado -ne 'instalada_deshabilitada'){throw 'NO INSTALA DESHABILITADA'}
$antes=$global:XmlTarea
$r=Invoke-Caso 'repetir' 'Instalar';if($r.estado -ne 'ya_instalada_sin_reescribir' -or $global:XmlTarea -cne $antes){throw 'REESCRITURA'}
$r=Invoke-Caso 'consulta' 'Estado';if($r.estado -ne 'consultada' -or $r.habilitada){throw 'CONSULTA INCOHERENTE'}
$r=Invoke-Caso 'pausa' 'Pausar';if($r.habilitada){throw 'NO PAUSADA'}
$r=Invoke-Caso 'retirada' 'Desinstalar';if($r.estado -ne 'desinstalada' -or $null -ne $global:XmlTarea){throw 'NO RETIRADA'}
$r=Invoke-Caso 'ausencia' 'Estado';if($r.estado -ne 'no_instalada'){throw 'NO CONFIRMA AUSENCIA'}
$r=Invoke-Caso 'retirada-repetida' 'Desinstalar';if($r.estado -ne 'ya_ausente'){throw 'RETIRADA NO IDEMPOTENTE'}
if(@($global:Controles|Where-Object{$_ -eq 'Register'}).Count -ne 1 -or @($global:Controles|Where-Object{$_ -eq 'Enable'}).Count){throw 'REGISTRO DUPLICADO O ACTIVACION'}
''', cuenta=cuenta, sid=sid)
    exportaciones = _assert_exportaciones(tarea, traza["resultados"])
    assert traza["controles"].count("Register") == 1 and "Enable" not in traza["controles"]
    planes = list((tarea["raiz"] / "puntos").glob("*/tarea.xml"))
    assert planes and all(p.read_bytes().startswith(codecs.BOM_UTF16_LE) for p in planes)
    for _, texto, d in exportaciones:
        assert "<RunLevel>" not in texto and "<WakeToRun>" not in texto
        assert cuenta in texto
        assert d["estado"] == "aprobada"
        predeterminados = {x["ruta"] for x in d["campos"] if x["origen"] == "predeterminado_documentado"}
        assert any(x.endswith("RunLevel") for x in predeterminados)
        assert any(x.endswith("WakeToRun") for x in predeterminados)


ALTERACIONES = {
    "privilegios_elevados": "Add-Campo $x '/t:Task/t:Principals/t:Principal' 'RunLevel' 'HighestAvailable'",
    "despertar_equipo": "Add-Campo $x '/t:Task/t:Settings' 'WakeToRun' 'true'",
    "principal_distinto": "Set-Campo $x '/t:Task/t:Principals/t:Principal/t:UserId' $global:OtroSidSimulado",
    "logon_distinto": "Set-Campo $x '/t:Task/t:Triggers/t:LogonTrigger/t:UserId' 'OTROEQUIPO\\otro'",
    "logon_no_resoluble": "Set-Campo $x '/t:Task/t:Triggers/t:LogonTrigger/t:UserId' 'DESCONOCIDO\\sin_cuenta'",
    "principal_no_resoluble": "Set-Campo $x '/t:Task/t:Principals/t:Principal/t:UserId' 'DESCONOCIDO\\sin_cuenta'",
    "nombre_corto": "Set-Campo $x '/t:Task/t:Triggers/t:LogonTrigger/t:UserId' 'ana'",
    "mismo_sufijo": "Set-Campo $x '/t:Task/t:Triggers/t:LogonTrigger/t:UserId' 'OTRODOMINIO\\ana'",
    "principal_omitido": "Remove-Campo $x '/t:Task/t:Principals/t:Principal/t:UserId'",
    "logon_omitido": "Remove-Campo $x '/t:Task/t:Triggers/t:LogonTrigger/t:UserId'",
    "runlevel_vacio": "Add-Campo $x '/t:Task/t:Principals/t:Principal' 'RunLevel' ''",
    "wake_vacio": "Add-Campo $x '/t:Task/t:Settings' 'WakeToRun' ''",
    "origen_omitido": "Remove-Campo $x '/t:Task/t:RegistrationInfo/t:Source'",
    "vinculacion_alterada": "Set-Campo $x '/t:Task/t:RegistrationInfo/t:Description' 'VINCULACION_AJENA'",
    "programa_alterado": "Set-Campo $x '/t:Task/t:Actions/t:Exec/t:Command' 'otro-programa.exe'",
    "argumentos_alterados": "Set-Campo $x '/t:Task/t:Actions/t:Exec/t:Arguments' 'orden-ajena'",
    "directorio_omitido": "Remove-Campo $x '/t:Task/t:Actions/t:Exec/t:WorkingDirectory'",
    "intervalo_alterado": "Set-Campo $x '/t:Task/t:Triggers/t:TimeTrigger/t:Repetition/t:Interval' 'PT1M'",
    "intervalo_omitido": "Remove-Campo $x '/t:Task/t:Triggers/t:TimeTrigger/t:Repetition/t:Interval'",
    "accion_extra": "$n=Get-Ns $x;$p=$x.SelectSingleNode('/t:Task/t:Actions',$n);[void]$p.AppendChild($p.FirstChild.CloneNode($true))",
    "desencadenador_extra": "$n=Get-Ns $x;$p=$x.SelectSingleNode('/t:Task/t:Triggers',$n);[void]$p.AppendChild($p.LastChild.CloneNode($true))",
    "principal_extra": "$n=Get-Ns $x;$p=$x.SelectSingleNode('/t:Task/t:Principals',$n);[void]$p.AppendChild($p.FirstChild.CloneNode($true))",
    "contexto_ajeno": "$x.Task.Actions.SetAttribute('Context','Ajeno')",
    "logon_type_incompatible": "Set-Campo $x '/t:Task/t:Principals/t:Principal/t:LogonType' 'Password'",
    "inicio_no_disponible": "Set-Campo $x '/t:Task/t:Settings/t:StartWhenAvailable' 'false'",
    "limite_incompatible": "Set-Campo $x '/t:Task/t:Settings/t:ExecutionTimeLimit' 'PT72H'",
    "politica_incompatible": "Set-Campo $x '/t:Task/t:Settings/t:MultipleInstancesPolicy' 'Parallel'",
    "time_deshabilitado": "Add-Campo $x '/t:Task/t:Triggers/t:TimeTrigger' 'Enabled' 'false'",
    "logon_deshabilitado": "Add-Campo $x '/t:Task/t:Triggers/t:LogonTrigger' 'Enabled' 'false'",
    "parar_al_final": "Add-Campo $x '/t:Task/t:Triggers/t:TimeTrigger/t:Repetition' 'StopAtDurationEnd' 'true'",
    "fin_anadido": "Add-Campo $x '/t:Task/t:Triggers/t:TimeTrigger' 'EndBoundary' '2099-01-01T00:00:00'",
    "duracion_anadida": "Add-Campo $x '/t:Task/t:Triggers/t:TimeTrigger/t:Repetition' 'Duration' 'PT1H'",
    "retardo_logon": "Add-Campo $x '/t:Task/t:Triggers/t:LogonTrigger' 'Delay' 'PT1M'",
    "retardo_time": "Add-Campo $x '/t:Task/t:Triggers/t:TimeTrigger' 'RandomDelay' 'PT1M'",
    "limite_extra_disparo": "Add-Campo $x '/t:Task/t:Triggers/t:TimeTrigger' 'ExecutionTimeLimit' 'PT1M'",
    "inicio_extra_logon": "Add-Campo $x '/t:Task/t:Triggers/t:LogonTrigger' 'StartBoundary' '2099-01-01T00:00:00'",
    "repeticion_logon": "Add-Campo $x '/t:Task/t:Triggers/t:LogonTrigger' 'Repetition' 'alterada'",
}


@pytest.mark.parametrize("alteracion", list(ALTERACIONES))
def test_exportacion_alterada_rechazada_sin_modificar_tarea(tarea, alteracion):
    cambio = ALTERACIONES[alteracion]
    traza = _ejecutar(tarea, r'''
$r=Invoke-Caso 'instalar' 'Instalar'
$x=[xml]$global:XmlTarea
''' + cambio + r'''
$global:XmlTarea=$x.OuterXml
$antes=$global:XmlTarea;$numero=$global:Controles.Count
$r=Invoke-Caso 'rechazo' 'Activar' 1
if($r.tarea_modificada -or $global:XmlTarea -cne $antes){throw 'MODIFICA TAREA ALTERADA'}
foreach($c in @($global:Controles|Select-Object -Skip $numero)){if($c -in @('Enable','Disable','Register','Unregister')){throw 'MUTACION TRAS RECHAZO'}}
''')
    _assert_exportaciones(tarea, traza["resultados"], algun_rechazo=True)


def test_rechazo_posterior_registro_guarda_exportacion_y_diagnostico(tarea):
    traza = _ejecutar(tarea, r'''
$r=Invoke-Caso 'instalar-incompatible' 'Instalar' 1
if(-not $r.tarea_modificada -or $null -eq $global:XmlTarea){throw 'NO SE CONSERVA REGISTRO RECHAZADO'}
if(@($global:Controles|Where-Object{$_ -in @('Enable','Disable','Unregister')}).Count){throw 'MUTA TRAS RECHAZO POSTREGISTRO'}
''', alteracion=ALTERACIONES["privilegios_elevados"])
    exportaciones = _assert_exportaciones(tarea, traza["resultados"], algun_rechazo=True)
    assert any("HighestAvailable" in texto for _, texto, _ in exportaciones)
    assert traza["resultados"][0]["codigo"] == 1


def test_tarea_viva_equivalente_no_se_retira_ni_modifica(tarea):
    traza = _ejecutar(tarea, r'''
$r=Invoke-Caso 'instalar' 'Instalar';$global:Viva=$true
$antes=$global:XmlTarea;$numero=$global:Controles.Count
$r=Invoke-Caso 'viva' 'Desinstalar' 1
if($r.error -notmatch 'ciclo vivo' -or $r.tarea_modificada -or $global:XmlTarea -cne $antes){throw 'MODIFICA CICLO VIVO'}
foreach($c in @($global:Controles|Select-Object -Skip $numero)){if($c -in @('Enable','Disable','Register','Unregister')){throw 'INTERRUMPE CICLO VIVO'}}
''')
    _assert_exportaciones(tarea, traza["resultados"])


def test_equivalencias_explicitas_booleanas_duraciones_e_identidades(tarea):
    alteracion = r'''
Add-Campo $x '/t:Task/t:Principals/t:Principal' 'RunLevel' 'LeastPrivilege'
Add-Campo $x '/t:Task/t:Settings' 'WakeToRun' '0'
Set-Campo $x '/t:Task/t:Settings/t:StartWhenAvailable' '1'
Set-Campo $x '/t:Task/t:Settings/t:ExecutionTimeLimit' 'PT120M'
Set-Campo $x '/t:Task/t:Triggers/t:TimeTrigger/t:Repetition/t:Interval' 'PT300S'
Set-Campo $x '/t:Task/t:Principals/t:Principal/t:UserId' $global:CuentaSimulada
Set-Campo $x '/t:Task/t:Triggers/t:LogonTrigger/t:UserId' $global:SidSimulado
Add-Campo $x '/t:Task/t:Triggers/t:TimeTrigger' 'Enabled' '1'
Add-Campo $x '/t:Task/t:Triggers/t:LogonTrigger' 'Enabled' 'true'
Add-Campo $x '/t:Task/t:Triggers/t:TimeTrigger/t:Repetition' 'StopAtDurationEnd' '0'
Add-Campo $x '/t:Task/t:Triggers/t:TimeTrigger' 'RandomDelay' 'PT0S'
Add-Campo $x '/t:Task/t:Triggers/t:LogonTrigger' 'Delay' 'PT0M'
'''
    traza = _ejecutar(tarea, "$r=Invoke-Caso 'equivalente' 'Instalar'\nif($r.habilitada){throw 'ACTIVACION'}\n", alteracion=alteracion)
    exportaciones = _assert_exportaciones(tarea, traza["resultados"])
    assert all(d["estado"] == "aprobada" for _, _, d in exportaciones)


def test_exportacion_malformada_se_guarda_antes_de_parsear(tarea):
    traza = _ejecutar(tarea, r'''
$r=Invoke-Caso 'instalar' 'Instalar'
$global:ExportacionMalformada=$true
$r=Invoke-Caso 'xml-invalido' 'Estado' 1
if($r.tarea_modificada){throw 'MODIFICA TAREA CON EXPORTACION INVALIDA'}
''')
    exportaciones = _assert_exportaciones(tarea, traza["resultados"], algun_rechazo=True)
    assert any(texto == "<Task><no-cerrado>" and d["estado"] == "rechazada" for _, texto, d in exportaciones)


def test_exportar_fallido_conserva_diagnostico_sin_fabricar_xml_vacio(tarea):
    traza = _ejecutar(tarea, r'''
$r=Invoke-Caso 'instalar' 'Instalar'
$global:ErrorExportacion=$true
$r=Invoke-Caso 'export-error' 'Estado' 1
if($r.tarea_modificada){throw 'MODIFICA TAREA TRAS ERROR EXPORT'}
''')
    fallido = traza["resultados"][-1]
    fila = fallido["exportaciones"][-1]
    assert fila["xml"] is None
    diagnostico = json.loads(Path(fila["diagnostico"]).read_text(encoding="utf-8"))
    assert diagnostico["estado"] == "rechazada" and "PERMISO_EXPORTACION" in diagnostico["error"]
    assert not list(Path(fila["diagnostico"]).parent.glob("exportada-*.xml"))


def test_resolvedor_sid_original_con_api_nativa_o_indisponibilidad_explicita(tarea):
    """En Windows ejercita SID/NTAccount reales; en Linux confirma el límite."""
    programa = tarea["raiz"] / "resolver-original.ps1"
    programa.write_text(r'''
$ErrorActionPreference='Stop'
$tokens=$null;$errores=$null
$ast=[Management.Automation.Language.Parser]::ParseFile(__SCRIPT__,[ref]$tokens,[ref]$errores)
if(@($errores).Count){throw 'SINTAXIS'}
$f=@($ast.FindAll({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Resolver-IdentidadSid'},$true))
if($f.Count -ne 1){throw 'NO SE ENCUENTRA EL RESOLVEDOR ORIGINAL'}
. ([scriptblock]::Create($f[0].Extent.Text))
if([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT){
 $identidad=[Security.Principal.WindowsIdentity]::GetCurrent()
 try{
  $sid=$identidad.User.Value;$cuenta=$identidad.Name
  if((Resolver-IdentidadSid $sid) -cne $sid){throw 'SID NATIVO NO COINCIDE'}
  if((Resolver-IdentidadSid $cuenta) -cne $sid){throw 'CUENTA NATIVA NO COINCIDE'}
  $r=@{plataforma='Windows';SID_y_NTAccount_nativos_validados=$true;Programador_invocado=$false}
 }finally{$identidad.Dispose()}
}else{
 foreach($valor in @('S-1-5-21-101-202-303-1001','EQUIPO-FICTICIO\usuario')){
  $fallo=$false
  try{[void](Resolver-IdentidadSid $valor)}catch{if($_.Exception.Message -notmatch 'No se pudo resolver'){throw};$fallo=$true}
  if(-not $fallo){throw 'NO DEBE SIMULAR EXITO DE SID NATIVO EN LINUX'}
 }
 $r=@{plataforma='no_Windows';SID_y_NTAccount_nativos_validados=$false;indisponibilidad_explicita_comprobada=$true;Programador_invocado=$false}
}
[IO.File]::WriteAllText(__TRAZA__,(($r|ConvertTo-Json)+"`n"),(New-Object Text.UTF8Encoding($false,$true)))
$r|ConvertTo-Json -Compress
exit 0
'''.replace("__SCRIPT__", _ps_literal(SCRIPT)).replace("__TRAZA__", _ps_literal(tarea["raiz"] / "traza-exportacion.json")), encoding="utf-8-sig")
    p = _ejecutar_powershell(tarea, programa, nombre="resolver-original", timeout=30)
    _archivar(tarea)
    assert p.returncode == 0, p.stdout + p.stderr
    resultado = json.loads(p.stdout)
    assert resultado["Programador_invocado"] is False
    if os.name == "nt":
        assert resultado["plataforma"] == "Windows" and resultado["SID_y_NTAccount_nativos_validados"] is True
    else:
        assert resultado["plataforma"] == "no_Windows" and resultado["SID_y_NTAccount_nativos_validados"] is False
        assert resultado["indisponibilidad_explicita_comprobada"] is True
