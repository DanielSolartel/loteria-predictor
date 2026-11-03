<#
  Fase 10 (E10.2, v4): ejecuta el NUCLEO real del ensayo Brave/mTLS con una plataforma SUSTITUTA en memoria
  (almacen Personal, raiz, contenedores de clave -incluido uno AJENO sintetico-, procesos y servidor simulados;
  carpeta temporal real) y escribe un informe JSON. Lo invoca `test_ensayo_brave_e102.py`. No toca
  certificados, claves, procesos ni navegadores reales: acredita la LOGICA de finalizacion, no el proveedor de
  certificados de Windows. El borrado sustituto reproduce la semantica del adaptador real: si el certificado
  existe se comprueba su marca y -DeleteKey borra el certificado y SU clave; despues, si existe un contenedor
  con el nombre registrado, se borra ese nombre.
#>
param(
    [Parameter(Mandatory = $true)][string]$Nucleo,
    [Parameter(Mandatory = $true)][string]$Escenario,
    [Parameter(Mandatory = $true)][string]$Trabajo,
    [Parameter(Mandatory = $true)][string]$Informe
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
. $Nucleo

$partes = $Escenario.Split("+")
function Tiene([string]$n) { return ($script:partes -contains $n) }
function Valor([string]$prefijo, $defecto) {
    foreach ($p in $script:partes) { if ($p.StartsWith($prefijo + "=")) { return $p.Substring($prefijo.Length + 1) } }
    return $defecto
}

$AJENA = "clave-ajena-sintetica-0001"
$script:F = @{
    personal = @{}; raiz = @{}; claves = @{ "clave-ajena-sintetica-0001" = "ajena" }
    procesos = (New-Object System.Collections.ArrayList)
    llamadas = (New-Object System.Collections.ArrayList)
    pid = 1000; terminado = $false; verificado = $false; servidor = $null
    fallo = (Valor "fallo" ""); propios = [int](Valor "procesos" "0")
}
function Llamada([string]$t) { [void]$script:F.llamadas.Add($t) }
function Huella-Falsa { return (-join (1..40 | ForEach-Object { "0123456789ABCDEF"[(Get-Random -Maximum 16)] })) }
function Escribir-Resultado([string]$ruta, [string]$estado, $cn) {
    $d = [ordered]@{ version = 2; estado = $estado; cn = @($cn); rechazos_cn = @(); handshakes_fallidos = 0; fin = $null }
    [IO.File]::WriteAllText($ruta, ($d | ConvertTo-Json -Depth 3))
}
if (Tiene "proceso_ajeno") {
    [void]$F.procesos.Add([pscustomobject]@{ ProcessId = 1; Name = "brave.exe"; CommandLine = "brave.exe --user-data-dir=C:\Users\otro\perfil-normal" })
}

$plataforma = @{
    BuscarBrave = { param($indicado) Llamada "buscar_brave"; "/brave-sustituto" }
    PrepararCarpeta = { param($ruta) Llamada "preparar_carpeta"; "usuario-sustituto" }
    CrearCertificado = {
        param($rol, $firmante, $marca, $validez)
        Llamada ("crear:" + $rol)
        if ($script:F.fallo -eq ("crear_" + $rol)) { throw "fallo inyectado al crear $rol" }
        $h = Huella-Falsa
        $clave = [guid]::NewGuid().ToString()
        if ((Tiene "sin_nombre_clave") -and $rol -eq "cliente") { $nombre = $null } else { $nombre = $clave }
        $script:F.personal[$h] = @{ rol = $rol; marca = $marca; clave = $clave }
        $script:F.claves[$clave] = $rol
        [pscustomobject]@{ Huella = $h; Clave = $nombre; Sujeto = ("CN=" + $rol); Objeto = [pscustomobject]@{ Huella = $h } }
    }
    ExportarPfx = { param($c, $ruta, $clave) Llamada "exportar_pfx"; [IO.File]::WriteAllText($ruta, "pfx-sustituto") }
    CaEnPem = { param($c) "-----BEGIN CERTIFICATE-----`nU1VTVElUVVRP`n-----END CERTIFICATE-----`n" }
    AgregarARaiz = { param($c) Llamada "agregar_raiz"; $script:F.raiz[$c.Huella] = $true }
    ArrancarServidor = {
        param($a)
        Llamada "arrancar_servidor"
        $s = New-Object PSObject
        $s | Add-Member -MemberType ScriptProperty -Name HasExited -Value { $script:F.terminado }
        $s | Add-Member -MemberType ScriptProperty -Name ExitCode -Value { if (Tiene "arranque_falla") { 3 } elseif ($script:F.verificado) { 0 } else { 2 } }
        $s | Add-Member -MemberType NoteProperty -Name Resultado -Value $a.Resultado
        $s | Add-Member -MemberType NoteProperty -Name Parar -Value $a.Parar
        $s | Add-Member -MemberType ScriptMethod -Name WaitForExit -Value {
            param($ms)
            Llamada "esperar_servidor"
            if ($script:F.terminado) { return $true }
            if ($script:F.fallo -eq "servidor") { return $false }
            if (Test-Path -LiteralPath $this.Parar) {
                $cn = @(); if ($script:F.verificado) { $cn = @("invitado-brave") }
                $fin = "sin_resultado"; if ($script:F.verificado) { $fin = "verificado" }
                Escribir-Resultado $this.Resultado $fin $cn
                $script:F.terminado = $true
                return $true
            }
            return $false
        }
        $s | Add-Member -MemberType ScriptMethod -Name Kill -Value {
            Llamada "matar_servidor"
            if ($script:F.fallo -eq "servidor") { throw "fallo inyectado al detener el servidor" }
            $script:F.terminado = $true
        }
        if (Tiene "arranque_falla") {
            Escribir-Resultado $a.Resultado "arranque_fallido" @()
            $script:F.terminado = $true
        } else {
            Escribir-Resultado $a.Resultado "escuchando" @()
        }
        $script:F.servidor = $s
        $s
    }
    AbrirBrave = {
        param($exe, $perfil, $url)
        Llamada "abrir_brave"
        for ($i = 0; $i -lt $script:F.propios; $i++) {
            $script:F.pid++
            [void]$script:F.procesos.Add([pscustomobject]@{ ProcessId = $script:F.pid; Name = "brave.exe"; CommandLine = ("brave.exe --user-data-dir=`"" + $perfil + "`" --type=renderer") })
        }
        if (-not (Tiene "sin_interaccion")) {
            $script:F.verificado = $true
            Escribir-Resultado $script:F.servidor.Resultado "verificado" @("invitado-brave")
        }
    }
    ConsultarProcesos = {
        Llamada "consultar_procesos"
        if (Tiene "consulta_falla") { throw "Acceso denegado (sustituto de Get-CimInstance)" }
        @($script:F.procesos | ForEach-Object { [pscustomobject]@{ ProcessId = $_.ProcessId; Name = $_.Name; CommandLine = $_.CommandLine } })
    }
    DetenerProceso = {
        param($id)
        Llamada ("detener:" + $id)
        if ($script:F.fallo -eq "detener") { throw "fallo inyectado al detener $id" }
        foreach ($p in @($script:F.procesos)) { if ($p.ProcessId -eq $id) { $script:F.procesos.Remove($p) } }
    }
    QuitarDeRaiz = {
        param($r)
        Llamada ("quitar_raiz:" + $r.rol)
        if ($script:F.fallo -eq "raiz") { throw "fallo inyectado al retirar la CA" }
        $script:F.raiz.Remove($r.huella)
    }
    BorrarCertificadoYClave = {
        param($r)
        Llamada ("borrar:" + $r.rol + ":" + $r.huella + ":" + [string]$r.clave)
        if ($script:F.fallo -eq ("borrar_" + $r.rol)) { throw ("fallo inyectado al borrar " + $r.rol) }
        if ($script:F.personal.ContainsKey($r.huella)) {
            $c = $script:F.personal[$r.huella]
            if ($c.marca -ne $r.marca) { throw "marca distinta: no se toca" }
            $script:F.personal.Remove($r.huella)
            if (-not (Tiene "clave_huerfana")) { $script:F.claves.Remove($c.clave) }   # -DeleteKey
        }
        if (-not (Tiene "clave_huerfana") -and $r.clave -and $script:F.claves.ContainsKey([string]$r.clave)) {
            $script:F.claves.Remove([string]$r.clave)                                  # CngKey por nombre
        }
    }
    BorrarCarpeta = {
        param($ruta)
        Llamada "borrar_carpeta"
        if ($script:F.fallo -eq "carpeta") { throw "fallo inyectado al borrar la carpeta" }
        Remove-Item -LiteralPath $ruta -Recurse -Force
    }
    ExisteEnPersonal = { param($r) $script:F.personal.ContainsKey($r.huella) }
    ExisteEnRaiz = { param($r) $script:F.raiz.ContainsKey($r.huella) }
    ExisteClave = {
        param($r)
        if ($script:F.fallo -eq "verificacion") { throw "fallo inyectado al verificar" }
        if (-not $r.clave) { throw "sin identificador de clave: no verificable" }
        $script:F.claves.ContainsKey([string]$r.clave)
    }
    Pausa = { param($ms) Start-Sleep -Milliseconds ([Math]::Min([int]$ms, 20)) }
}

$temp = Join-Path $Trabajo "temp"
New-Item -ItemType Directory -Path $temp -Force | Out-Null
$salida = Join-Path $Trabajo "resumen.json"
$alternativa = Join-Path $temp "ensayo-brave-mtls-e102-resumen-0123456789ab.json"
if ((Tiene "salida_invalida") -or (Tiene "salidas_invalidas")) { $salida = Join-Path $Trabajo (Join-Path "no-existe" "resumen.json") }
if (Tiene "salidas_invalidas") { New-Item -ItemType Directory -Path $alternativa | Out-Null }  # tampoco la alternativa
$diagnostico = Join-Path $Trabajo "resumen.json.diagnostico.json"
$opciones = @{ Python = "python"; Brave = ""; PlazoArranque = 2; PlazoHumano = 2; PlazoSalida = 1; Temp = $temp
               Servidor = "servidor-sustituto.py"; Salida = $salida; Diagnostico = $diagnostico
               # Solo para poder cargar el nucleo v3 como control negativo (v4 no usa esta clave).
               Recuperacion = (Join-Path $Trabajo "control-v3-recuperacion.json") }

function Foto {
    return [ordered]@{
        personal = $script:F.personal.Count; raiz = $script:F.raiz.Count
        claves = @($script:F.claves.Values | Where-Object { $_ -ne "ajena" }).Count
        clave_ajena = $script:F.claves.ContainsKey($script:AJENA)
        procesos_propios = @($script:F.procesos | Where-Object { $_.CommandLine.Contains("e102-mtls-0123456789ab") }).Count
        procesos_ajenos = @($script:F.procesos | Where-Object { -not $_.CommandLine.Contains("e102-mtls-0123456789ab") }).Count
    }
}

function Ejecutar($rep) {
    $excepcion = $null
    $flujo = @()
    try {
        $flujo = @(Invoke-EnsayoCompletoE102 -Plataforma $plataforma -Opciones $opciones -Id "0123456789ab" 6>&1)
        $codigo = Ultimo-ValorE102 $flujo "int"
    } catch {
        $codigo = $null
        $excepcion = $_.Exception.GetType().FullName + ": " + $_.Exception.Message
    }
    $consola = @($flujo | Where-Object { $_ -is [System.Management.Automation.InformationRecord] } | ForEach-Object { [string]$_.MessageData })
    $rep.codigo = $codigo
    $rep.excepcion_escapada = $excepcion
    $rep.resumen_en = $null
    foreach ($r in @($salida, $alternativa)) { if ((Test-Path -LiteralPath $r -PathType Leaf)) { $rep.resumen_en = $r; break } }
    $rep.resumen = $null
    if ($rep.resumen_en) { $rep.resumen = Get-Content -LiteralPath $rep.resumen_en -Raw | ConvertFrom-Json }
    $json = @($consola | Where-Object { $_.TrimStart().StartsWith("{") })
    $rep.resumen_consola = $null
    if ($json.Count -ge 1) { $rep.resumen_consola = $json[$json.Count - 1] | ConvertFrom-Json }
    $rep.ultima_linea_consola = $null
    if ($consola.Count -gt 0) { $rep.ultima_linea_consola = $consola[$consola.Count - 1] }
    $rep.diagnostico_existe = (Test-Path -LiteralPath $diagnostico)
    $rep.diagnostico = $null
    if ($rep.diagnostico_existe) { $rep.diagnostico = Get-Content -LiteralPath $diagnostico -Raw | ConvertFrom-Json }
    $rep.temporal_existe = (Test-Path -LiteralPath (Join-Path $temp "e102-mtls-0123456789ab"))
    $rep.almacen = Foto
    $rep.llamadas = @($script:F.llamadas)
}

$rep = [ordered]@{ escenario = $Escenario; powershell = $PSVersionTable.PSVersion.ToString(); edicion = $PSVersionTable.PSEdition }
Ejecutar $rep

if (Tiene "diagnostico_manipulado") {
    # El registro de la primera ejecucion se manipula para que apunte a la clave AJENA y a otra huella; una
    # segunda ejecucion normal no debe leerlo ni usarlo para borrar nada.
    $d = Get-Content -LiteralPath $diagnostico -Raw | ConvertFrom-Json
    $d.propios[0].clave = $AJENA
    $d.propios[1].huella = "0000000000000000000000000000000000000000"
    [IO.File]::WriteAllText($diagnostico, ($d | ConvertTo-Json -Depth 5))
    $rep.diagnostico_manipulado = $d
    $script:F.fallo = ""; $script:F.terminado = $false; $script:F.verificado = $false
    $script:F.llamadas.Clear()
    $segunda = [ordered]@{}
    Ejecutar $segunda
    $rep.segunda = $segunda
}
[IO.File]::WriteAllText($Informe, ($rep | ConvertTo-Json -Depth 8))
