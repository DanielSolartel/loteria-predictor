$ErrorActionPreference = 'Stop'
$paquete = Join-Path $env:LP11_RAIZ 'abrir.zip'
if ((Get-FileHash -LiteralPath $paquete -Algorithm SHA256).Hash -ine '__PAQUETE_SHA256__') {
    throw 'La huella del lanzador instalado no coincide.'
}

$tarea = Get-ScheduledTask -TaskName 'LP6-01023009031fcabd' -TaskPath '\'
$acciones = @($tarea.Actions)
if ($acciones.Count -ne 1) { throw 'La tarea de Fase 6 no tiene una única acción.' }
$accion = $acciones[0]
$m = [regex]::Match(
    [string]$accion.Arguments,
    '(?i)^\s*-m\s+scripts\.operacion_automatica\s+--config\s+"([^"]+)"\s+ciclo(?:\s|$)'
)
if (-not $m.Success) { throw 'La acción registrada difiere del formato de Fase 6.' }
$python = [string]$accion.Execute
if ($python -notmatch '^[A-Za-z]:[\\/]' -or -not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'El Python registrado en la tarea de Fase 6 no está disponible.'
}
& $python -I -B $paquete ([string]$accion.WorkingDirectory) ($m.Groups[1].Value)
exit $LASTEXITCODE
