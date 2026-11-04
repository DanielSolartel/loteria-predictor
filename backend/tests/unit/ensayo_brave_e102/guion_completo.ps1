<#
  Fase 10 (E10.2, v4): ejecuta el GUION PRINCIPAL completo (`ensayo_brave_mtls_e102.ps1`, o el de otra version
  como control negativo) sustituyendo, con funciones del mismo nombre, los cmdlets de Windows que alcanza en los
  caminos sin certificados: la consulta de procesos (Get-CimInstance), Stop-Process y el almacen X509 de la raiz.
  No instala certificados, no abre Brave ni toca procesos reales. Escribe un informe JSON.
  Escenarios: `sin_brave` (fallo temprano: coleccion de procesos vacia), `consulta_falla` (la consulta lanza) y
  `recuperar` (v4: `-Recuperar` con un registro de formato v3 bien formado debe rechazarse sin tocar nada; el
  guion v3 lo aceptaba y ejecutaba una limpieza a partir del JSON). Cada cmdlet sustituido anota su uso.
#>
param(
    [Parameter(Mandatory = $true)][string]$Guion,
    [Parameter(Mandatory = $true)][string]$Escenario,
    [Parameter(Mandatory = $true)][string]$Trabajo,
    [Parameter(Mandatory = $true)][string]$Informe
)
$ErrorActionPreference = "Stop"
$global:E102EscenarioGuion = $Escenario
$global:E102Llamadas = New-Object System.Collections.ArrayList

function Get-CimInstance {
    param([string]$ClassName, [string]$Filter, $ErrorAction)
    [void]$global:E102Llamadas.Add("Get-CimInstance")
    if ($global:E102EscenarioGuion -eq "consulta_falla") { throw "Acceso denegado (sustituto de Get-CimInstance)" }
    # sin procesos: no emite nada
}
function Stop-Process { param($Id, [switch]$Force, $ErrorAction) [void]$global:E102Llamadas.Add("Stop-Process") }
# Salvaguardas para ejecutarlo tambien en un Windows real (p. ej. el runner de CI): nunca crea certificados
# y las rutas por defecto de Brave apuntan a una carpeta vacia, de modo que el ensayo falla antes de instalar.
function New-SelfSignedCertificate { [void]$global:E102Llamadas.Add("New-SelfSignedCertificate"); throw "el arnes de pruebas no crea certificados" }
function New-Object {
    param([Parameter(Position = 0)][string]$TypeName, [Parameter(Position = 1)][object[]]$ArgumentList)
    if ($TypeName -like "*X509Store") {
        [void]$global:E102Llamadas.Add("X509Store")
        $almacen = Microsoft.PowerShell.Utility\New-Object PSObject
        $almacen | Add-Member -MemberType NoteProperty -Name Certificates -Value @()
        $almacen | Add-Member -MemberType ScriptMethod -Name Open -Value { param($m) }
        $almacen | Add-Member -MemberType ScriptMethod -Name Close -Value { }
        $almacen | Add-Member -MemberType ScriptMethod -Name Remove -Value { param($c) }
        $almacen | Add-Member -MemberType ScriptMethod -Name Add -Value { param($c) }
        return $almacen
    }
    # Como el cmdlet real, el objeto creado se emite sin enumerar (p. ej. un ArrayList vacio).
    if ($null -ne $ArgumentList) { return ,(Microsoft.PowerShell.Utility\New-Object -TypeName $TypeName -ArgumentList $ArgumentList) }
    return ,(Microsoft.PowerShell.Utility\New-Object -TypeName $TypeName)
}

$temp = Join-Path $Trabajo "temp"
Microsoft.PowerShell.Management\New-Item -ItemType Directory -Path $temp -Force | Out-Null
$env:TEMP = $temp
$env:ProgramFiles = $temp
${env:ProgramFiles(x86)} = $temp
$env:LOCALAPPDATA = $temp
$salida = Join-Path $Trabajo "resumen.json"
$rep = [ordered]@{ escenario = $Escenario; guion = (Split-Path -Leaf $Guion); powershell = $PSVersionTable.PSVersion.ToString() }
$excepcion = $null
$global:LASTEXITCODE = $null
$registro = Join-Path $Trabajo "registro-formato-v3.json"
if ($Escenario -eq "recuperar") {
    # Registro bien formado segun el lector v3 (id, marca, carpeta y perfil coherentes; sin recursos).
    $id = "0123456789ab"; $tmpEnsayo = Join-Path $temp ("e102-mtls-" + $id)
    $d = [ordered]@{ version = 1; ensayo = "E10.2 Brave mTLS"; id = $id; marca = ("E10.2 ensayo Brave mTLS " + $id)
                     temporal = $tmpEnsayo; perfil = (Join-Path $tmpEnsayo "perfil-brave"); propios = @() }
    [IO.File]::WriteAllText($registro, ($d | ConvertTo-Json -Depth 4))
}
$antes = @(Get-ChildItem -LiteralPath $Trabajo -Recurse -Force | ForEach-Object { $_.FullName })
try {
    if ($Escenario -eq "recuperar") {
        & $Guion -Recuperar $registro -Confirmar -Python "python" -Salida $salida -PlazoArranque 1 -PlazoHumano 1 -PlazoSalida 1
    } else {
        & $Guion -Confirmar -Brave "" -Python "python" -Salida $salida -PlazoArranque 1 -PlazoHumano 1 -PlazoSalida 1
    }
    $rep.codigo = $LASTEXITCODE
} catch {
    $rep.codigo = $LASTEXITCODE
    $excepcion = $_.Exception.GetType().FullName + ": " + $_.Exception.Message
}
$rep.excepcion_escapada = $excepcion
$rep.llamadas = @($global:E102Llamadas)
$rep.archivos_nuevos = @(Get-ChildItem -LiteralPath $Trabajo -Recurse -Force | ForEach-Object { $_.FullName } | Where-Object { $antes -notcontains $_ })
$rep.registro_existe_tras = (Test-Path -LiteralPath $registro)
$rep.resumen_existe = (Test-Path -LiteralPath $salida)
$rep.resumen = $null
if ($rep.resumen_existe) { $rep.resumen = Get-Content -LiteralPath $salida -Raw | ConvertFrom-Json }
[IO.File]::WriteAllText($Informe, ($rep | ConvertTo-Json -Depth 8))
