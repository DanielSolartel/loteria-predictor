"""Contrato XML portable con PowerShell real y Programador simulado.

No reproduce Register-ScheduledTask nativo, COM ni MSXML de Windows. La
instalación nativa se verifica mediante el ensayo aislado del operador.
"""
from __future__ import annotations

import codecs
import xml.etree.ElementTree as ET

import pytest

from tests.unit.test_fase6_tarea_windows import (
    NS, PLAN, _llamar, _sesion, tarea,
)


@pytest.fixture
def tarea_unicode(tarea):
    # Ampersand y apóstrofo prueban también el escape XML y literal PowerShell.
    repo = tarea["raiz"] / "worktree ñ 漢字 & O'Neil"
    (repo / "backend/scripts").mkdir(parents=True)
    (repo / "backend/scripts/operacion_automatica.py").write_text(
        "raise AssertionError('No ejecutar producto en pruebas del XML')\n", encoding="utf-8")
    python = tarea["raiz"] / "venv ñ 漢字 & O'Neil/python.exe"
    python.parent.mkdir()
    python.write_bytes(b"INTERPRETE_FICTICIO_NO_EJECUTABLE")
    config = tarea["raiz"] / "configuración ñ 漢字 & O'Neil.json"
    config.write_text('{"solo_testigo": true}\n', encoding="utf-8")
    tarea.update(repo=repo, python=python, config=config)
    tarea["originales"] = {p: p.read_bytes() for p in tarea["raiz"].rglob("*") if p.is_file()}
    return tarea


def _xml_unicode(contenido):
    assert contenido.startswith(codecs.BOM_UTF16_LE), "tarea.xml debe declarar y persistir UTF-16LE con BOM"
    texto = contenido.decode("utf-16", errors="strict")
    assert texto.startswith('<?xml version="1.0" encoding="UTF-16"?>')
    assert codecs.BOM_UTF16_LE + texto.encode("utf-16le", errors="strict") == contenido
    return texto, ET.fromstring(contenido)


def _assert_contenido(x, tarea):
    val = lambda n: x.findtext("t:" + n.replace("/", "/t:"), namespaces=NS)
    assert val("Actions/Exec/Command") == str(tarea["python"])
    assert val("Actions/Exec/WorkingDirectory") == str(tarea["repo"] / "backend")
    assert val("Actions/Exec/Arguments") == ('-m scripts.operacion_automatica --config "' + str(tarea["config"])
                                             + '" ciclo --programado --plan ' + PLAN["huella"])
    assert val("Principals/Principal/RunLevel") == "LeastPrivilege"
    assert val("Principals/Principal/LogonType") == "InteractiveToken"
    assert val("Settings/Enabled") == "false"
    assert val("Settings/MultipleInstancesPolicy") == "IgnoreNew"
    assert val("Settings/ExecutionTimeLimit") == "PT2H"
    assert val("Settings/WakeToRun") == "false"
    assert val("Settings/StartWhenAvailable") == "false"
    disparadores = x.findall("t:Triggers/*", NS)
    assert [d.tag.split("}")[1] for d in disparadores] == ["CalendarTrigger"] * len(PLAN["disparadores"])
    assert x.find("t:Triggers/t:LogonTrigger", NS) is None and x.find("t:Triggers/t:TimeTrigger", NS) is None
    assert val("RegistrationInfo/Source") == "LoteriaPredictor/Fase6/tarea/2"


def test_plan_xml_unicode_cabecera_bytes_y_contenido_coherentes(tarea_unicode):
    p, r, e = _llamar(tarea_unicode, previo="function Get-ScheduledTask { throw 'PLAN NO CONSULTA PROGRAMADOR' }")
    assert p.returncode == 0, p.stdout + p.stderr
    assert r["estado"] == "plan_no_instalado" and not r["tarea_modificada"]
    texto, xml = _xml_unicode((e / "tarea.xml").read_bytes())
    assert "ñ 漢字 &amp; O&apos;Neil" in texto
    _assert_contenido(xml, tarea_unicode)


def test_registro_recibe_misma_cadena_unicode_que_xml_persistido(tarea_unicode):
    # La función captura la cadena de -Xml antes de almacenarla. No es el
    # Programador real: verifica el contrato string/bytes, sin registrar tareas.
    _sesion(tarea_unicode, r'''
function Register-ScheduledTask {
    [CmdletBinding()]param([string]$TaskName,[string]$TaskPath,[string]$Xml)
    [void]$global:Llamadas.Add('Register')
    if($global:Tareas.ContainsKey($TaskName)){throw 'TAREA EXISTENTE NO SE SOBRESCRIBE'}
    if(-not $Xml.StartsWith('<?xml version="1.0" encoding="UTF-16"?>')){throw 'DECLARACION INCOMPATIBLE CON CADENA UNICODE'}
    $unicode=New-Object Text.UnicodeEncoding($false,$true,$true)
    [IO.File]::WriteAllText((Join-Path $raizPrueba 'cadena-registrada.xml'),$Xml,$unicode)
    $global:Tareas[$TaskName]=[xml]$Xml
}
$r=Invoke-Caso 'registro-unicode' 'Instalar'
if($r.estado -ne 'instalada_deshabilitada' -or $r.habilitada){throw 'ACTIVACION IMPLICITA'}
$nombre=$r.tarea
$persistida=[IO.File]::ReadAllText($r.plan_xml,[Text.Encoding]::Unicode)
if($persistida -cne [IO.File]::ReadAllText((Join-Path $raizPrueba 'cadena-registrada.xml'),[Text.Encoding]::Unicode)){throw 'CADENA REGISTRADA DISTINTA DEL ARCHIVO'}
$antes=$global:Tareas[$nombre].OuterXml
$r=Invoke-Caso 'repetir-unicode' 'Instalar'
if($r.estado -ne 'ya_instalada_sin_reescribir' -or $global:Tareas[$nombre].OuterXml -cne $antes){throw 'REESCRITURA DE TAREA EXISTENTE'}
if(@($global:Llamadas | Where-Object {$_ -eq 'Register'}).Count -ne 1){throw 'MAS DE UN REGISTRO'}
''')
    capturada = (tarea_unicode["raiz"] / "cadena-registrada.xml").read_bytes()
    persistida = (tarea_unicode["raiz"] / "registro-unicode/tarea.xml").read_bytes()
    assert capturada == persistida
    _, xml = _xml_unicode(capturada)
    _assert_contenido(xml, tarea_unicode)
