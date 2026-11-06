[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$DirectorioEnsayo,
    [Parameter(Mandatory=$true)][string]$DirectorioSalida
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
if ($DirectorioEnsayo -notmatch '^/tmp/e107pc-[a-z0-9_-]{8,40}$') { throw 'La ruta no corresponde a un ensayo E107.' }
if (-not (Test-Path -LiteralPath $DirectorioSalida -PathType Container)) { throw 'No existe la carpeta de salida.' }
$esperados = @('diagnosticar_pc.ps1', 'diagnosticar.py', 'LEEME.md', 'VALIDACION.md', 'pruebas.py')
$vistos = @{}
foreach ($linea in [IO.File]::ReadAllLines((Join-Path $PSScriptRoot 'SHA256SUMS'))) {
    if ($linea -notmatch '^([0-9a-f]{64})  ([A-Za-z0-9_.-]+)$') { throw 'Manifiesto no valido.' }
    $h = $Matches[1]; $n = $Matches[2]
    if ($n -notin $esperados -or $vistos.ContainsKey($n)) { throw 'Archivo inesperado o repetido.' }
    $vistos[$n] = $true
    if ((Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $n) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $h) {
        throw 'Una huella no coincide. No se ejecuta el diagnostico.'
    }
}
if ($vistos.Count -ne $esperados.Count) { throw 'Faltan huellas en el manifiesto.' }
$wslLocal = Join-Path $env:WINDIR 'System32\wsl.exe'
if ([Environment]::Is64BitOperatingSystem -and -not [Environment]::Is64BitProcess) {
    $wslLocal = Join-Path $env:WINDIR 'Sysnative\wsl.exe'
}
if (-not (Test-Path -LiteralPath $wslLocal -PathType Leaf)) { throw 'No se encuentra WSL.' }
$codigo = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'diagnosticar.py'))
$anterior = $OutputEncoding
try {
    $OutputEncoding = New-Object System.Text.UTF8Encoding($false)
    Write-Host 'Diagnostico de lectura: consulta metadatos y registros del ensayo conservado.'
    $lineas = @($codigo | & $wslLocal --distribution Ubuntu --exec python3 -I -B - --directorio-ensayo $DirectorioEnsayo)
    $codigoWsl = $LASTEXITCODE
} finally { $OutputEncoding = $anterior }
$paquetes = @($lineas | Where-Object { ([string]$_).StartsWith('E107_DIAGNOSTICO_JSON:') })
if ($paquetes.Count -ne 1) { throw 'Ubuntu no entrego el diagnostico esperado. Comparte esta salida.' }
$dato = ([string]$paquetes[0]).Substring('E107_DIAGNOSTICO_JSON:'.Length) | ConvertFrom-Json
$bytes = [Convert]::FromBase64String($dato.evidencia_base64)
$sha = [Security.Cryptography.SHA256]::Create()
try { $h = ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant() }
finally { $sha.Dispose() }
if ($bytes.Length -ne $dato.evidencia_bytes -or $h -ne $dato.evidencia_sha256) { throw 'Evidencia incompleta.' }
$destino = Join-Path $DirectorioSalida ('e107-diagnostico-evidencia-' + [Guid]::NewGuid().ToString('N') + '.zip')
$flujo = [IO.File]::Open($destino, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try { $flujo.Write($bytes, 0, $bytes.Length) } finally { $flujo.Dispose() }
$dato.resumen | ConvertTo-Json -Depth 12
Write-Host ('Archivo: ' + $destino)
Write-Host ('SHA256: ' + $h)
if ($codigoWsl -ne 0 -or $dato.resumen.codigo -ne 0) {
    throw 'Diagnostico incompleto. Comparte el ZIP y la salida.'
}
Write-Host 'Lectura terminada. Comparte el ZIP nuevo de diagnostico.'
