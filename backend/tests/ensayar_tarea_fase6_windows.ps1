# Ensayo NATIVO optativo del Programador. No usa la aplicacion ni datos reales.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PythonExe,
    [Parameter(Mandatory=$true)][string]$Evidencia,
    [switch]$Ejecutar
)
Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'
if (-not $Ejecutar) { throw 'Revise el archivo y use -Ejecutar explicitamente para registrar una tarea sintetica propia.' }
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'Este ensayo requiere Windows nativo; el parser de Linux no lo acredita.' }
$Utf8=New-Object Text.UTF8Encoding($false,$true)
$Raiz=$null; $NombreTarea=$null; $FuenteEvento=$null; $Watcher=$null; $Codigo=1
$Resultado=[ordered]@{version=1; tipo='programador_nativo_con_CLI_testigo'; estado='error'; codigo=1; error=$null; pasos=@(); estado_limpieza='no_necesaria'; avisos_limpieza=@(); producto_ejecutado=$false; datos_reales=$false}
function Escribir-Json([string]$Ruta,$Valor) { [IO.File]::WriteAllText($Ruta,(($Valor | ConvertTo-Json -Depth 12)+"`n"),$Utf8) }
function Control([string]$Accion,[string]$Paso) {
    $p=@{Worktree=$Raiz;PythonExe=$PythonExe;Configuracion=$Config;Evidencia=(Join-Path $Evidencia $Paso)}
    $p[$Accion]=$true
    & $ControlTarea @p | Out-Host
    $rc=$LASTEXITCODE
    $r=Get-Content -LiteralPath (Join-Path $p.Evidencia 'resultado.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $Resultado.pasos+=@{paso=$Paso;accion=$Accion;codigo=$rc;resultado=$r}
    if($rc -ne 0){throw ('Fallo en '+$Paso+': '+[string]$r.error+'; conservar sus registros.')}
    return $r
}
try {
    if(-not [IO.Path]::IsPathRooted($PythonExe) -or -not(Test-Path -LiteralPath $PythonExe -PathType Leaf)){throw 'PythonExe debe ser absoluto y existir.'}
    if(-not [IO.Path]::IsPathRooted($Evidencia)){throw 'Evidencia debe ser absoluta.'}
    $Evidencia=[IO.Path]::GetFullPath($Evidencia)
    if(Test-Path -LiteralPath $Evidencia){throw 'La evidencia debe ser nueva para no sobrescribir registros.'}
    [void][IO.Directory]::CreateDirectory($Evidencia)
    $Resultado.evidencia=$Evidencia
    $ControlTarea=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\scripts\windows\fase6_tarea.ps1'))
    $tokens=$null; $errores=$null
    $ast=[Management.Automation.Language.Parser]::ParseFile($ControlTarea,[ref]$tokens,[ref]$errores)
    if(@($errores).Count -ne 0){throw 'Sintaxis incorrecta en el controlador de tareas.'}
    foreach($cmd in @('Start-ScheduledTask','Get-ScheduledTask','Get-ScheduledTaskInfo','Export-ScheduledTask')){[void](Get-Command $cmd -ErrorAction Stop)}
    $Raiz=Join-Path ([IO.Path]::GetTempPath()) ('f6t '+[Guid]::NewGuid().ToString('N').Substring(0,8))
    [void][IO.Directory]::CreateDirectory((Join-Path $Raiz 'backend\scripts'))
    $Config=Join-Path $Raiz 'config-testigo.json'; $Marca=Join-Path $Raiz 'marca-testigo.json'
    $Programa=@'
"""Testigo sintetico: no importa la aplicacion, no usa BD ni red."""
import argparse, datetime, json, os, sys
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('--config', required=True)
p.add_argument('orden', choices=['ciclo'])
a = p.parse_args()
c = json.loads(Path(a.config).read_text(encoding='utf-8-sig'))
assert c['solo_testigo_sintetico'] is True
with Path(c['marca']).open('x', encoding='utf-8') as f:
    json.dump({'orden': a.orden, 'pid': os.getpid(), 'python': sys.executable,
               'momento': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'producto_ejecutado': False, 'datos_reales': False}, f)
'@
    [IO.File]::WriteAllText((Join-Path $Raiz 'backend\scripts\operacion_automatica.py'),$Programa,$Utf8)
    [IO.File]::WriteAllText((Join-Path $Raiz 'backend\scripts\__init__.py'),'',$Utf8)
    Escribir-Json $Config @{solo_testigo_sintetico=$true;marca=$Marca}
    $Resultado.raiz_sintetica=$Raiz
    $r=Control 'Plan' 'p';if($r.tarea_modificada){throw 'El plan modifico el Programador.'}
    # Conservar identidad ANTES de instalar: si un paso posterior al registro
    # falla, no borrar el testigo al que podria seguir apuntando una tarea.
    $NombreTarea=[string]$r.tarea
    $r=Control 'Instalar' 'i'
    if($r.habilitada){throw 'La tarea no quedo deshabilitada.'}
    $r=Control 'Activar' 'a';if(-not$r.habilitada){throw 'La tarea no quedo habilitada.'}
    $Watcher=New-Object IO.FileSystemWatcher($Raiz,'marca-testigo.json')
    $Watcher.EnableRaisingEvents=$true
    $FuenteEvento='LP6-testigo-'+[Guid]::NewGuid().ToString('N')
    [void](Register-ObjectEvent -InputObject $Watcher -EventName Created -SourceIdentifier $FuenteEvento)
    $reloj=[Diagnostics.Stopwatch]::StartNew()
    Start-ScheduledTask -TaskName $NombreTarea -TaskPath '\' -ErrorAction Stop
    if(-not(Test-Path -LiteralPath $Marca)){[void](Wait-Event -SourceIdentifier $FuenteEvento -Timeout 60)}
    if(-not(Test-Path -LiteralPath $Marca)){throw 'No aparecio la marca del proceso testigo dentro de60segundos.'}
    while(([string](Get-ScheduledTask -TaskName $NombreTarea -TaskPath '\' -ErrorAction Stop).State -eq 'Running') -and $reloj.Elapsed.TotalSeconds -lt 60){Start-Sleep -Milliseconds 100}
    $estado=Get-ScheduledTask -TaskName $NombreTarea -TaskPath '\' -ErrorAction Stop
    $info=Get-ScheduledTaskInfo -TaskName $NombreTarea -TaskPath '\' -ErrorAction Stop
    if([string]$estado.State -eq 'Running' -or [long]$info.LastTaskResult -ne 0){throw 'El proceso testigo no termino correctamente.'}
    $testigo=Get-Content -LiteralPath $Marca -Raw -Encoding UTF8 | ConvertFrom-Json
    if($testigo.producto_ejecutado -or $testigo.datos_reales -or $testigo.orden -ne 'ciclo'){throw 'Marca de testigo incoherente.'}
    Copy-Item -LiteralPath $Marca -Destination (Join-Path $Evidencia 'testigo.json')
    $xml=Export-ScheduledTask -TaskName $NombreTarea -TaskPath '\' -ErrorAction Stop
    [IO.File]::WriteAllText((Join-Path $Evidencia 'tarea-nativa.xml'),[string]$xml,[Text.Encoding]::Unicode)
    $Resultado.disparo=@{estado=[string]$estado.State;ultimo_resultado=[long]$info.LastTaskResult;ultimo_inicio=$info.LastRunTime.ToString('o');python_testigo=$testigo.python;pid_testigo=$testigo.pid;segundos=$reloj.Elapsed.TotalSeconds}
    $r=Control 'Pausar' 's';if($r.habilitada){throw 'La tarea no se pauso.'}
    $r=Control 'Desinstalar' 'd';if($r.estado -ne 'desinstalada'){throw 'La tarea no se retiro.'}
    $r=Control 'Estado' 'e-retirada';if($r.estado -ne 'no_instalada'){throw 'No se confirmo la ausencia de la tarea retirada; conservar el testigo.'}
    $NombreTarea=$null
    $Resultado.estado='aprobado';$Codigo=0
} catch {
    $Resultado.error=$_.Exception.Message
} finally {
    if($null -ne $FuenteEvento){
        try{Unregister-Event -SourceIdentifier $FuenteEvento -ErrorAction Stop;Get-Event | Where-Object{$_.SourceIdentifier -eq $FuenteEvento} | Remove-Event -ErrorAction Stop}catch{$Resultado.avisos_limpieza+=$_.Exception.Message}
    }
    if($null -ne $Watcher){try{$Watcher.Dispose()}catch{$Resultado.avisos_limpieza+=$_.Exception.Message}}
    if($null -ne $NombreTarea){
        try{
            # Estado verifica propiedad cuando la tarea existe. Un error de
            # consulta/permisos nunca equivale a ausencia ni autoriza borrar.
            $r=Control 'Estado' 'e-final'
            if($r.estado -eq 'no_instalada'){
                $NombreTarea=$null
            }elseif($r.estado -eq 'consultada'){
                if([string]$r.estado_programador -eq 'Running'){throw 'Hay un ciclo vivo; se conservan tarea y testigo para revision.'}
                $r=Control 'Pausar' 's-final'
                if($r.habilitada){throw 'La tarea no se pauso; se conserva el testigo.'}
                $r=Control 'Desinstalar' 'd-final'
                if($r.estado -ne 'desinstalada' -and $r.estado -ne 'ya_ausente'){throw 'No se confirmo la retirada de la tarea; conservar el testigo.'}
                $r=Control 'Estado' 'e-retirada-final'
                if($r.estado -ne 'no_instalada'){throw 'No se confirmo la ausencia de la tarea retirada; conservar el testigo.'}
                $NombreTarea=$null
            }else{throw 'La consulta no confirma presencia propia ni ausencia; conservar tarea y testigo.'}
        }catch{$Resultado.avisos_limpieza+=$_.Exception.Message}
    }
    if($null -ne $Raiz -and (Test-Path -LiteralPath $Raiz)){
        if($null -eq $NombreTarea){
            try{Remove-Item -LiteralPath $Raiz -Recurse -Force -ErrorAction Stop;$Resultado.estado_limpieza='completa'}catch{$Resultado.estado_limpieza='pendiente';$Resultado.avisos_limpieza+=$_.Exception.Message;$Resultado.temporal_pendiente=$Raiz}
        }else{$Resultado.estado_limpieza='pendiente';$Resultado.temporal_pendiente=$Raiz;$Resultado.tarea_pendiente=$NombreTarea}
    }
    $Resultado.codigo=$Codigo;$Resultado.finalizada_en=[DateTime]::UtcNow.ToString('o')
    if(Test-Path -LiteralPath $Evidencia -PathType Container){Escribir-Json (Join-Path $Evidencia 'resultado-tarea-nativa.json') $Resultado}
}
if($Codigo -ne 0){Write-Error -Message ([string]$Resultado.error) -ErrorAction Continue}
exit $Codigo
