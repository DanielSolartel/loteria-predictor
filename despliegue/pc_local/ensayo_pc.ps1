[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$DirectorioSalida,
    [Parameter(Mandatory=$true)][switch]$AutorizarEnsayoSintetico
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
if (-not $AutorizarEnsayoSintetico) { throw 'Falta la autorizacion del ensayo sintetico local.' }
if (-not (Test-Path -LiteralPath $DirectorioSalida -PathType Container)) { throw 'No existe la carpeta de salida.' }

$esperados = @('ensayo_pc.ps1', 'ensayo.py', 'fuentes.zip', 'ORIGEN_FUENTES.json', 'cambios.zip', 'LEEME.md', 'VALIDACION.md')
$vistos = @{}
foreach ($linea in [IO.File]::ReadAllLines((Join-Path $PSScriptRoot 'SHA256SUMS'))) {
    if ($linea -notmatch '^([0-9a-f]{64})  ([A-Za-z0-9_.-]+)$') { throw 'Manifiesto no valido.' }
    $huella = $Matches[1]
    $nombre = $Matches[2]
    if ($nombre -notin $esperados -or $vistos.ContainsKey($nombre)) { throw 'Archivo inesperado o repetido.' }
    $vistos[$nombre] = $true
    if ((Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $nombre) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $huella) {
        throw 'Una huella no coincide. No se inicia el ensayo.'
    }
}
if ($vistos.Count -ne $esperados.Count) { throw 'Faltan huellas en el manifiesto.' }
$wslLocal = Join-Path $env:WINDIR 'System32\wsl.exe'
if ([Environment]::Is64BitOperatingSystem -and -not [Environment]::Is64BitProcess) {
    $wslLocal = Join-Path $env:WINDIR 'Sysnative\wsl.exe'
}
if (-not (Test-Path -LiteralPath $wslLocal -PathType Leaf)) { throw 'No se encuentra WSL de Windows.' }
$ocupados = @(Get-NetTCPConnection -State Listen -ErrorAction Stop |
    Where-Object { $_.LocalPort -in @(18443, 9125) })
if ($ocupados.Count -ne 0) { throw '18443 o 9125 esta ocupado en Windows. No se inicia el ensayo.' }

$codificacionAnterior = $OutputEncoding
$paquetes = New-Object 'System.Collections.Generic.List[string]'
try {
    # Fuentes completas incluidas en el paquete. No se lee el proyecto del usuario.
    $fuentes = Join-Path $PSScriptRoot 'fuentes.zip'
    if ((Get-Item -LiteralPath $fuentes).Length -gt 67108864) { throw 'La copia de fuentes excede el limite.' }
    $fuente64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($fuentes))
    $cambios64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes((Join-Path $PSScriptRoot 'cambios.zip')))
    $ejecutor64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes((Join-Path $PSScriptRoot 'ensayo.py')))
    $codigo = "import base64`nexec(compile(base64.b64decode('" + $ejecutor64 +
        "'), '<e107>', 'exec'), {'__name__': '__main__', 'FUENTE_BASE64': '" + $fuente64 +
        "', 'CAMBIOS_BASE64': '" + $cambios64 + "'})`n"
    $OutputEncoding = New-Object System.Text.UTF8Encoding($false)
    Write-Host 'Ensayo local con datos sinteticos; las imagenes se reutilizan y los servicios se detienen al terminar.'
    $codigo | & $wslLocal --distribution Ubuntu --exec python3 -I -B - --autorizar-ensayo-sintetico | ForEach-Object {
        $linea = [string]$_
        if ($linea.StartsWith('E107_ETAPA:')) { Write-Host ('Etapa: ' + $linea.Substring(11)) }
        if ($linea.StartsWith('E107_RESULTADO_JSON:')) { $paquetes.Add($linea.Substring(20)) }
    }
    $codigoWsl = $LASTEXITCODE
} finally {
    $OutputEncoding = $codificacionAnterior
}
if ($paquetes.Count -ne 1) { throw 'Ubuntu no entrego la evidencia. Comparte la salida y no repitas el bloque.' }
$dato = $paquetes[0] | ConvertFrom-Json
$bytes = [Convert]::FromBase64String($dato.evidencia_base64)
$sha = [Security.Cryptography.SHA256]::Create()
try { $huellaFinal = ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant() }
finally { $sha.Dispose() }
if ($bytes.Length -ne $dato.evidencia_bytes -or $huellaFinal -ne $dato.evidencia_sha256) {
    throw 'La evidencia no coincide con su huella.'
}
$destino = Join-Path $DirectorioSalida ('e107-ensayo-pc-evidencia-' + [Guid]::NewGuid().ToString('N') + '.zip')
$flujo = [IO.File]::Open($destino, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
try { $flujo.Write($bytes, 0, $bytes.Length) } finally { $flujo.Dispose() }
$dato.resumen | ConvertTo-Json -Depth 12
Write-Host ('Archivo: ' + $destino)
Write-Host ('SHA256: ' + $huellaFinal)
if ($codigoWsl -ne 0 -or $dato.resumen.codigo -ne 0) {
    throw 'Ensayo detenido. Comparte el ZIP y la salida; no repitas el bloque.'
}
Write-Host 'Ensayo terminado con recursos conservados y servicios detenidos. Comparte el ZIP de evidencia.'
