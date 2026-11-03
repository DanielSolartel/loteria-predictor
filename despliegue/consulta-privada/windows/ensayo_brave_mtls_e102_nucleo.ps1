<#
  Fase 10 (E10.2, v4): NUCLEO del ensayo focal Brave/mTLS. Solo define funciones; cargarlo no hace nada.
  Lo usa `ensayo_brave_mtls_e102.ps1` (con la plataforma Windows real) y las pruebas (con sustitutos).
  Compatible con Windows PowerShell 5.1 y PowerShell 7 (modo estricto 2.0).

  Garantias de la finalizacion (F1023-WIN-02/WIN-03):
  - cada limpieza es un paso aislado: un fallo se anota, se acumula y NO impide las siguientes;
  - el resumen se escribe siempre en una finalizacion exterior (Salida, alternativa en TEMP o, en ultimo
    caso, la consola) y el codigo de salida nunca es 0 con una limpieza incompleta o sin verificar; el codigo
    final (incluido el 6, resumen no guardado) se decide ANTES de emitir el JSON, que siempre coincide con el
    codigo de salida (F1023-WIN-05);
  - una consulta de procesos que falla NO cuenta como cero procesos; las colecciones se materializan en el
    punto de consumo (`@(...)`), sin desactivar el modo estricto;
  - las claves privadas creadas por esta ejecucion se eliminan explicitamente (no solo los certificados) y
    se verifica su ausencia por su identificador EXACTO; nunca se enumeran almacenes ni claves ajenas;
  - la limpieza usa SOLO los identificadores creados en memoria por esta misma ejecucion. No existe
    recuperacion automatica (retirada en v4, F1023-WIN-04): ningun archivo externo se lee para borrar nada.
    Un REGISTRO DIAGNOSTICO (identificadores y residuos, sin secretos) queda solo para revisar a mano un
    residuo antes de una accion manual concreta; el ensayo nunca lo lee ni lo ejecuta.
#>

$script:E102_PatronCarpeta = '^e102-mtls-[0-9a-f]{12}$'
$script:E102_UsoDiagnostico = "solo diagnostico: identificadores y residuos para revision manual; no es una autorizacion ni instrucciones de borrado y el ensayo nunca lo lee"


function Nuevo-EstadoE102 {
    param([Parameter(Mandatory = $true)][hashtable]$Opciones, [string]$Id = "")
    if (-not $Id) { $Id = [guid]::NewGuid().ToString("N").Substring(0, 12) }
    $temporal = Join-Path $Opciones.Temp ("e102-mtls-" + $Id)
    $resumen = [ordered]@{
        ensayo = "E10.2 Brave mTLS v4"
        alcance = "seleccion y verificacion del certificado de cliente en Brave"
        inicio = (Get-Date).ToString("o")
        pasos = (New-Object System.Collections.ArrayList)
    }
    return @{
        Id = $Id; Temporal = $temporal; Perfil = (Join-Path $temporal "perfil-brave")
        Resultado = (Join-Path $temporal "resultado.json"); Parar = (Join-Path $temporal "parar")
        Marca = ("E10.2 ensayo Brave mTLS " + $Id)
        Propios = (New-Object System.Collections.ArrayList)
        Objetos = @{}
        Errores = (New-Object System.Collections.ArrayList)
        Servidor = $null; Codigo = 1; CarpetaCreada = $false
        Diagnostico = [string]$Opciones.Diagnostico
        Resumen = $resumen
    }
}

function Anotar-E102 {
    param([hashtable]$Estado, [string]$Paso, [bool]$Ok, [string]$Detalle = "")
    [void]$Estado.Resumen.pasos.Add([ordered]@{ paso = $Paso; ok = $Ok; detalle = $Detalle })
    $marca = "[FALLO]"
    if ($Ok) { $marca = "[OK]" }
    Write-Host "$marca $Paso $Detalle"
}

function Invoke-PasoE102 {
    <# Ejecuta UN paso aislado: devuelve $true/$false y anota; nunca deja escapar la excepcion. #>
    param([hashtable]$Estado, [string]$Nombre, [scriptblock]$Accion, $Argumento = $null)
    try {
        $detalle = (@(& $Accion $Argumento) | ForEach-Object { [string]$_ }) -join " "
        Anotar-E102 $Estado $Nombre $true $detalle
        return $true
    } catch {
        $mensaje = $_.Exception.Message
        [void]$Estado.Errores.Add([ordered]@{ paso = $Nombre; error = $mensaje })
        Anotar-E102 $Estado $Nombre $false $mensaje
        return $false
    }
}

function Obtener-ProcesosPropiosE102 {
    <# Consulta los procesos y devuelve SOLO los del perfil temporal. Consultado=$false si la consulta fallo:
       un fallo de lectura no significa cero procesos. Procesos siempre es una coleccion. #>
    param([Parameter(Mandatory = $true)][scriptblock]$Consultar, [Parameter(Mandatory = $true)][string]$Perfil)
    try {
        $todos = @(& $Consultar)
    } catch {
        return [pscustomobject]@{ Consultado = $false; Procesos = @(); Error = $_.Exception.Message }
    }
    $propios = @($todos | Where-Object {
        ($null -ne $_) -and (@($_.PSObject.Properties | Where-Object { $_.Name -eq "CommandLine" }).Count -eq 1) -and
        $_.CommandLine -and ([string]$_.CommandLine).Contains($Perfil)
    })
    return [pscustomobject]@{ Consultado = $true; Procesos = $propios; Error = "" }
}

function Guardar-DiagnosticoE102 {
    <# Registro DIAGNOSTICO: identificadores de esta ejecucion y, al final, sus residuos. Sin claves ni
       contrasenas. Solo se ESCRIBE; ninguna funcion del ensayo lo lee. #>
    param([hashtable]$Estado, $Residuos = $null)
    if (-not $Estado.Diagnostico) { return }
    $datos = [ordered]@{
        version = 2; uso = $script:E102_UsoDiagnostico; ensayo = "E10.2 Brave mTLS"; id = $Estado.Id
        marca = $Estado.Marca; temporal = $Estado.Temporal; perfil = $Estado.Perfil; propios = @($Estado.Propios)
        servidor = "no arrancado"; residuos = $null; actualizado = (Get-Date).ToString("o")
    }
    if ($null -ne $Estado.Servidor) {
        try { if ($Estado.Servidor.HasExited) { $datos.servidor = "terminado" } else { $datos.servidor = "en ejecucion" } }
        catch { $datos.servidor = "estado no verificado" }
    }
    if ($null -ne $Residuos) { $datos.residuos = @($Residuos) }
    $temporal = $Estado.Diagnostico + ".tmp"
    [IO.File]::WriteAllText($temporal, ($datos | ConvertTo-Json -Depth 5))
    Move-Item -LiteralPath $temporal -Destination $Estado.Diagnostico -Force
}

function Registrar-PropioE102 {
    param([hashtable]$Estado, [string]$Rol, $Creado)
    $registro = [ordered]@{
        rol = $Rol; huella = [string]$Creado.Huella; clave = $Creado.Clave; sujeto = [string]$Creado.Sujeto
        marca = $Estado.Marca; en_raiz = $false
    }
    [void]$Estado.Propios.Add($registro)
    $Estado.Objetos[$Rol] = $Creado.Objeto
    try { Guardar-DiagnosticoE102 $Estado }
    catch { [void]$Estado.Errores.Add([ordered]@{ paso = "registro diagnostico"; error = $_.Exception.Message }) }
    if (-not $Creado.Clave) {
        Anotar-E102 $Estado ("identificador de la clave privada de " + $Rol) $false "no se obtuvo: su eliminacion no podra verificarse"
    }
    return $registro
}

function Leer-ResultadoE102 {
    param([hashtable]$Estado)
    if (-not (Test-Path -LiteralPath $Estado.Resultado)) { return $null }
    try { return (Get-Content -LiteralPath $Estado.Resultado -Raw | ConvertFrom-Json) } catch { return $null }
}

function Contrasena-AleatoriaE102 {
    $bytes = New-Object byte[] 32
    $generador = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generador.GetBytes($bytes) } finally { $generador.Dispose() }
    return [Convert]::ToBase64String($bytes).Replace("+", "A").Replace("/", "B").Replace("=", "")
}

function Invoke-EnsayoE102 {
    <# Flujo del ensayo. Lanza ante cualquier fallo; la limpieza la hace Invoke-EnsayoCompletoE102. #>
    param([hashtable]$Estado, [hashtable]$Plataforma, [hashtable]$Opciones)
    $braveExe = & $Plataforma.BuscarBrave $Opciones.Brave
    New-Item -ItemType Directory -Path $Estado.Temporal | Out-Null
    $Estado.CarpetaCreada = $true
    $titular = & $Plataforma.PrepararCarpeta $Estado.Temporal
    Anotar-E102 $Estado "carpeta temporal privada" $true ([string]$titular)

    $validez = (Get-Date).AddHours(2)
    $ca = & $Plataforma.CrearCertificado "ca" $null $Estado.Marca $validez
    [void](Registrar-PropioE102 $Estado "ca" $ca)
    $cliente = & $Plataforma.CrearCertificado "cliente" $ca.Objeto $Estado.Marca $validez
    [void](Registrar-PropioE102 $Estado "cliente" $cliente)
    $servidor = & $Plataforma.CrearCertificado "servidor" $ca.Objeto $Estado.Marca $validez
    [void](Registrar-PropioE102 $Estado "servidor" $servidor)
    Anotar-E102 $Estado "certificados de prueba creados" $true "CA, invitado-brave (no exportable), localhost; validez 2 h"

    $clave = Contrasena-AleatoriaE102
    $pfx = Join-Path $Estado.Temporal "servidor.pfx"
    & $Plataforma.ExportarPfx $servidor.Objeto $pfx $clave
    $caPem = Join-Path $Estado.Temporal "ca.pem"
    [IO.File]::WriteAllText($caPem, (& $Plataforma.CaEnPem $ca.Objeto))

    foreach ($r in @($Estado.Propios)) { if ($r.rol -eq "ca") { $r.en_raiz = $true } }  # antes de agregarla
    try { Guardar-DiagnosticoE102 $Estado }
    catch { [void]$Estado.Errores.Add([ordered]@{ paso = "registro diagnostico"; error = $_.Exception.Message }) }
    & $Plataforma.AgregarARaiz $ca.Objeto
    Anotar-E102 $Estado "CA de prueba de confianza para el usuario (temporal)" $true $ca.Huella

    $escucha = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, 0)
    $escucha.Start(); $puerto = $escucha.LocalEndpoint.Port; $escucha.Stop()
    $plazoServidor = $Opciones.PlazoArranque + $Opciones.PlazoHumano + $Opciones.PlazoSalida + 30
    $Estado.Servidor = & $Plataforma.ArrancarServidor @{
        Python = $Opciones.Python; Servidor = $Opciones.Servidor; Pfx = $pfx; Ca = $caPem; Puerto = $puerto
        Resultado = $Estado.Resultado; Parar = $Estado.Parar; Plazo = $plazoServidor; Contrasena = $clave
    }
    $clave = $null

    $limite = (Get-Date).AddSeconds($Opciones.PlazoArranque)
    $lectura = $null
    while ((Get-Date) -lt $limite -and -not $Estado.Servidor.HasExited) {
        $lectura = Leer-ResultadoE102 $Estado
        if ($lectura -and $lectura.estado -eq "escuchando") { break }
        & $Plataforma.Pausa 200
    }
    if (-not ($lectura -and $lectura.estado -eq "escuchando")) {
        $Estado.Codigo = 3
        $visto = "sin resultado"
        if ($lectura) { $visto = [string]$lectura.estado }
        throw ("El servidor no quedo escuchando en {0} s (estado: {1})" -f $Opciones.PlazoArranque, $visto)
    }
    Anotar-E102 $Estado "servidor mTLS local" $true "https://localhost:$puerto/"

    & $Plataforma.AbrirBrave $braveExe $Estado.Perfil "https://localhost:$puerto/"
    Write-Host ("En Brave (perfil temporal): elija el certificado 'invitado-brave'. Espera maxima: {0} s." -f $Opciones.PlazoHumano)
    $limite = (Get-Date).AddSeconds($Opciones.PlazoHumano)
    while ((Get-Date) -lt $limite -and -not $Estado.Servidor.HasExited) {
        $lectura = Leer-ResultadoE102 $Estado
        if ($lectura -and $lectura.estado -eq "verificado") { break }
        & $Plataforma.Pausa 500
    }
    $verificado = [bool]($lectura -and $lectura.estado -eq "verificado" -and (@($lectura.cn) -contains "invitado-brave"))
    if ($verificado) {
        Anotar-E102 $Estado "Brave presento el certificado y el servidor lo verifico" $true "CN=invitado-brave"
    } else {
        $rechazos = ""
        if ($lectura) { $rechazos = "CN rechazados: " + (@($lectura.rechazos_cn) -join ",") + "; handshakes fallidos: " + $lectura.handshakes_fallidos }
        Anotar-E102 $Estado "sin certificado valido dentro del plazo" $false $rechazos
    }

    New-Item -ItemType File -Path $Estado.Parar | Out-Null
    if (-not $Estado.Servidor.WaitForExit($Opciones.PlazoSalida * 1000)) {
        Anotar-E102 $Estado "el servidor no termino de forma cooperativa; fin forzado" $false ""
        $Estado.Servidor.Kill(); [void]$Estado.Servidor.WaitForExit(5000)
        $salidaServidor = -1
    } else {
        $salidaServidor = $Estado.Servidor.ExitCode
        Anotar-E102 $Estado "cierre cooperativo del servidor" $true ("codigo " + $salidaServidor)
    }
    $final = Leer-ResultadoE102 $Estado
    $persistido = [bool]($final -and (@($final.cn) -contains "invitado-brave"))
    if ($verificado -and $persistido -and $salidaServidor -eq 0) { $Estado.Codigo = 0 }
    elseif ($verificado) { $Estado.Codigo = 1 }
    else { $Estado.Codigo = 2 }
}

function Invoke-LimpiezaE102 {
    <# Todas las limpiezas, cada una aislada, y la verificacion final. Devuelve $true solo si todo se elimino
       Y se pudo verificar. Solo actua sobre los identificadores registrados por esta ejecucion. #>
    param([hashtable]$Estado, [hashtable]$Plataforma, [int]$PlazoSalida = 15)
    $ok = $true
    $ctx = @{ E = $Estado; P = $Plataforma; PlazoSalida = $PlazoSalida; R = $null }

    if ($null -ne $Estado.Servidor) {
        $ok = (Invoke-PasoE102 $Estado "limpieza: servidor local detenido" {
            param($c)
            $s = $c.E.Servidor
            if ($s.HasExited) { return "ya habia terminado" }
            if ((Test-Path -LiteralPath $c.E.Temporal) -and -not (Test-Path -LiteralPath $c.E.Parar)) {
                New-Item -ItemType File -Path $c.E.Parar | Out-Null
            }
            if ($s.WaitForExit($c.PlazoSalida * 1000)) { return "cierre cooperativo" }
            $s.Kill()
            if (-not $s.WaitForExit(5000)) { throw "el servidor sigue en ejecucion tras el fin forzado" }
            "fin forzado"
        } $ctx) -and $ok
    }

    $ok = (Invoke-PasoE102 $Estado "limpieza: procesos de Brave del perfil temporal" {
        param($c)
        $consulta = Obtener-ProcesosPropiosE102 -Consultar $c.P.ConsultarProcesos -Perfil $c.E.Perfil
        if (-not $consulta.Consultado) { throw ("no se pudo consultar los procesos: " + $consulta.Error) }
        $propios = @($consulta.Procesos)
        $fallos = New-Object System.Collections.ArrayList
        foreach ($p in $propios) {
            try { & $c.P.DetenerProceso $p.ProcessId } catch { [void]$fallos.Add(([string]$p.ProcessId + ": " + $_.Exception.Message)) }
        }
        if ($propios.Count -gt 0) { & $c.P.Pausa 500 }
        if ($fallos.Count -gt 0) { throw ("no se detuvieron: " + ($fallos -join "; ")) }
        "{0} procesos propios cerrados" -f $propios.Count
    } $ctx) -and $ok

    foreach ($r in @($Estado.Propios)) {
        if (-not $r.en_raiz) { continue }
        $ctx.R = $r
        $ok = (Invoke-PasoE102 $Estado ("limpieza: CA retirada de la raiz del usuario " + $r.huella) {
            param($c) & $c.P.QuitarDeRaiz $c.R; "retirada por huella"
        } $ctx) -and $ok
    }

    foreach ($r in @($Estado.Propios)) {
        $ctx.R = $r
        $ok = (Invoke-PasoE102 $Estado ("limpieza: certificado y clave privada de " + $r.rol) {
            param($c) & $c.P.BorrarCertificadoYClave $c.R; "huella y clave eliminadas"
        } $ctx) -and $ok
    }

    if ($Estado.CarpetaCreada -or (Test-Path -LiteralPath $Estado.Temporal)) {
        $ok = (Invoke-PasoE102 $Estado "limpieza: carpeta temporal y perfil de Brave" {
            param($c)
            if ((Split-Path -Leaf $c.E.Temporal) -notmatch $script:E102_PatronCarpeta) { throw "ruta temporal no reconocida: no se borra" }
            & $c.P.BorrarCarpeta $c.E.Temporal
            "borrada"
        } $ctx) -and $ok
    }

    # Verificacion final: cada comprobacion aislada; lo no verificable cuenta como residuo.
    $residuos = New-Object System.Collections.ArrayList
    $comprobaciones = @(@{ n = "certificado en Personal"; f = $Plataforma.ExisteEnPersonal },
                        @{ n = "CA en la raiz"; f = $Plataforma.ExisteEnRaiz },
                        @{ n = "clave privada"; f = $Plataforma.ExisteClave })
    foreach ($r in @($Estado.Propios)) {
        foreach ($k in $comprobaciones) {
            try {
                if (& $k.f $r) { [void]$residuos.Add(("{0}: {1} {2} {3}" -f $r.rol, $k.n, $r.huella, $r.clave)) }
            } catch {
                [void]$residuos.Add(("{0}: {1} no verificado ({2})" -f $r.rol, $k.n, $_.Exception.Message))
            }
        }
    }
    if ($null -ne $Estado.Servidor) {
        try { if (-not $Estado.Servidor.HasExited) { [void]$residuos.Add("servidor local: sigue en ejecucion") } }
        catch { [void]$residuos.Add("servidor local: estado no verificado") }
    }
    $consulta = Obtener-ProcesosPropiosE102 -Consultar $Plataforma.ConsultarProcesos -Perfil $Estado.Perfil
    if (-not $consulta.Consultado) { [void]$residuos.Add("procesos de Brave del perfil: consulta fallida (" + $consulta.Error + ")") }
    elseif (@($consulta.Procesos).Count -gt 0) { [void]$residuos.Add(("procesos de Brave del perfil: {0} siguen activos" -f @($consulta.Procesos).Count)) }
    try {
        if (Test-Path -LiteralPath $Estado.Temporal) { [void]$residuos.Add("carpeta temporal: sigue existiendo") }
    } catch { [void]$residuos.Add("carpeta temporal: no verificada") }

    $verificado = ($residuos.Count -eq 0)
    $detalle = "sin residuos propios"
    if (-not $verificado) { $detalle = ($residuos -join "; ") }
    Anotar-E102 $Estado "verificacion final de la limpieza" $verificado $detalle
    $Estado.Resumen.residuos = @($residuos)
    return ($ok -and $verificado)
}

function Ultimo-ValorE102 {
    <# Toma el valor de retorno de una funcion aunque algo hubiera emitido salida adicional. #>
    param($Salida, [string]$Tipo)
    # Sin un valor del tipo esperado, el resultado es el desfavorable: $false o el codigo 1 (nunca 0).
    $lista = @($Salida)
    $ultimo = $null
    if ($lista.Count -gt 0) { $ultimo = $lista[$lista.Count - 1] }
    if ($Tipo -eq "bool") { if ($ultimo -is [bool]) { return $ultimo }; return $false }
    if ($Tipo -eq "int") { if ($ultimo -is [int]) { return $ultimo }; return 1 }
    return $ultimo
}

function Serializar-ResumenE102 {
    param([System.Collections.IDictionary]$Resumen)
    try { return ($Resumen | ConvertTo-Json -Depth 6) }
    catch { return ('{"codigo": ' + [int]$Resumen.codigo + ', "error": "resumen no serializable"}') }
}

function Escribir-ResumenE102 {
    <# Intenta la ruta pedida y despues la alternativa en TEMP. Devuelve la ruta escrita o "" si ninguna
       pudo escribirse; NO emite el resumen en consola (eso lo decide el llamador con el codigo final). #>
    param([System.Collections.IDictionary]$Resumen, [string]$Salida, [string]$Alternativa)
    $texto = Serializar-ResumenE102 $Resumen
    foreach ($ruta in @($Salida, $Alternativa)) {
        if (-not $ruta) { continue }
        try { [IO.File]::WriteAllText($ruta, $texto); return $ruta } catch { Write-Host ("[FALLO] no se pudo escribir el resumen en {0}: {1}" -f $ruta, $_.Exception.Message) }
    }
    return ""
}

function Completar-ResumenE102 {
    param([hashtable]$Estado, [int]$CodigoEnsayo, [bool]$Limpio)
    $Estado.Resumen.codigo_ensayo = $CodigoEnsayo
    $Estado.Resumen.limpieza_completa = $Limpio
    $Estado.Resumen.propios = @($Estado.Propios | ForEach-Object { [ordered]@{ rol = $_.rol; huella = $_.huella; clave = $_.clave; en_raiz = $_.en_raiz } })
    $Estado.Resumen.errores = @($Estado.Errores)
    $Estado.Resumen.fin = (Get-Date).ToString("o")
    try { $Estado.Resumen.windows = [Environment]::OSVersion.VersionString } catch { $Estado.Resumen.windows = "" }
    $Estado.Resumen.powershell = $PSVersionTable.PSVersion.ToString()
}

function Cerrar-DiagnosticoE102 {
    <# Limpieza completa: el registro ya no hace falta y se borra. Si quedan residuos: se actualiza con ellos,
       se conserva para revision MANUAL y el ensayo termina con error. #>
    param([hashtable]$Estado, [bool]$Limpio)
    $Estado.Resumen.diagnostico = $null
    if (-not $Estado.Diagnostico) { return }
    if ($Limpio) {
        try { if (Test-Path -LiteralPath $Estado.Diagnostico) { Remove-Item -LiteralPath $Estado.Diagnostico -Force } }
        catch { [void]$Estado.Errores.Add([ordered]@{ paso = "registro diagnostico"; error = $_.Exception.Message }) }
        return
    }
    try {
        Guardar-DiagnosticoE102 $Estado @($Estado.Resumen.residuos)
        $Estado.Resumen.diagnostico = $Estado.Diagnostico
        Write-Host ("Quedan residuos: revise los identificadores de {0} antes de cualquier accion manual concreta. Ese archivo no autoriza ni ejecuta ningun borrado." -f $Estado.Diagnostico)
    } catch { [void]$Estado.Errores.Add([ordered]@{ paso = "registro diagnostico"; error = $_.Exception.Message }) }
}

function Invoke-EnsayoCompletoE102 {
    <# Codigos: 0 verificado y limpieza completa; 1 fallo; 2 sin interaccion/plazo o certificado incorrecto;
       3 el servidor no arranco; 4 limpieza incompleta o no verificable; 6 el resumen no pudo guardarse en
       ningun archivo (solo si no habia ya otro error). El JSON emitido siempre lleva el codigo devuelto. #>
    param([Parameter(Mandatory = $true)][hashtable]$Plataforma, [Parameter(Mandatory = $true)][hashtable]$Opciones, [string]$Id = "")
    $Estado = $null
    $codigo = 1
    $limpio = $false
    $alternativa = ""
    try {
        $Estado = Nuevo-EstadoE102 $Opciones $Id
        $alternativa = Join-Path $Opciones.Temp ("ensayo-brave-mtls-e102-resumen-" + $Estado.Id + ".json")
        try {
            $null = Invoke-EnsayoE102 $Estado $Plataforma $Opciones
        } catch {
            Anotar-E102 $Estado "excepcion" $false $_.Exception.Message
            if ($Estado.Codigo -eq 0) { $Estado.Codigo = 1 }
        }
        $codigoEnsayo = $Estado.Codigo
        try { $limpio = [bool](Ultimo-ValorE102 (Invoke-LimpiezaE102 $Estado $Plataforma $Opciones.PlazoSalida) "bool") }
        catch { Anotar-E102 $Estado "limpieza interrumpida" $false $_.Exception.Message; $limpio = $false }
        $codigo = $codigoEnsayo
        if (-not $limpio) { $codigo = 4 }
        Cerrar-DiagnosticoE102 $Estado $limpio
        Completar-ResumenE102 $Estado $codigoEnsayo $limpio
        Anotar-E102 $Estado "limpieza: certificados, claves privadas, CA, perfil de Brave y temporales" $limpio ("residuos: " + @($Estado.Resumen.residuos).Count)
    } catch {
        Write-Host ("[FALLO] finalizacion: " + $_.Exception.Message)
        $codigo = 4
    } finally {
        $resumen = [ordered]@{ ensayo = "E10.2 Brave mTLS v4"; error = "estado no disponible" }
        if ($null -ne $Estado) { $resumen = $Estado.Resumen }
        $resumen.codigo = $codigo
        $resumen.resumen_guardado = $true
        $escrito = ""
        try { $escrito = Escribir-ResumenE102 $resumen $Opciones.Salida $alternativa } catch { $escrito = "" }
        if (-not $escrito) {
            # Ningun destino: el codigo FINAL se decide antes de emitir el JSON en consola (WIN-05).
            if ($codigo -eq 0) { $codigo = 6 }
            $resumen.codigo = $codigo
            $resumen.resumen_guardado = $false
            Write-Host "Resumen (solo en consola, sin secretos):"
            Write-Host (Serializar-ResumenE102 $resumen)
        }
        Write-Host ("Resumen (sin secretos): {0}  -  codigo {1}" -f $(if ($escrito) { $escrito } else { "solo consola" }), $codigo)
    }
    return $codigo
}

function Nueva-PlataformaWindowsE102 {
    <# Operaciones REALES de Windows. Cada una actua sobre un identificador exacto; ninguna enumera ni lee
       claves ajenas. Proveedor de claves fijo: Microsoft Software Key Storage Provider (CNG). #>
    return @{
        BuscarBrave = {
            param($indicado)
            if ($indicado -and (Test-Path -LiteralPath $indicado)) { return $indicado }
            foreach ($c in @("$env:ProgramFiles\BraveSoftware\Brave-Browser\Application\brave.exe",
                             "${env:ProgramFiles(x86)}\BraveSoftware\Brave-Browser\Application\brave.exe",
                             "$env:LOCALAPPDATA\BraveSoftware\Brave-Browser\Application\brave.exe")) {
                if ($c -and (Test-Path -LiteralPath $c)) { return $c }
            }
            throw "No se encontro brave.exe; indique -Brave <ruta>"
        }
        PrepararCarpeta = {
            param($ruta)
            $yo = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
            & icacls.exe $ruta /inheritance:r /grant:r ("{0}:(OI)(CI)F" -f $yo) | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "No se pudieron restringir los permisos de la carpeta temporal" }
            $yo
        }
        CrearCertificado = {
            param($rol, $firmante, $marca, $validez)
            $comun = @{ CertStoreLocation = "Cert:\CurrentUser\My"; NotAfter = $validez; FriendlyName = $marca
                        Provider = "Microsoft Software Key Storage Provider" }
            if ($rol -eq "ca") {
                $c = New-SelfSignedCertificate @comun -Subject "CN=CA de ensayo E10.2 (PRUEBA)" -KeyExportPolicy NonExportable `
                    -KeyUsage CertSign, CRLSign, DigitalSignature -TextExtension @("2.5.29.19={critical}{text}ca=1&pathlength=0")
            } elseif ($rol -eq "cliente") {
                $c = New-SelfSignedCertificate @comun -Subject "CN=invitado-brave" -Signer $firmante -KeyExportPolicy NonExportable `
                    -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.2")
            } else {
                $c = New-SelfSignedCertificate @comun -DnsName "localhost" -Signer $firmante -KeyExportPolicy Exportable `
                    -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.1")
            }
            $nombre = $null
            try {  # solo el NOMBRE del contenedor CNG; no se exporta ni se lee material de la clave
                $rsa = [System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($c)
                if ($rsa -is [System.Security.Cryptography.RSACng]) { $nombre = $rsa.Key.KeyName }
                $rsa.Dispose()
            } catch { $nombre = $null }
            [pscustomobject]@{ Huella = $c.Thumbprint; Clave = $nombre; Sujeto = $c.Subject; Objeto = $c }
        }
        ExportarPfx = {
            param($certificado, $ruta, $clave)
            Export-PfxCertificate -Cert $certificado -FilePath $ruta -Password (ConvertTo-SecureString -String $clave -AsPlainText -Force) | Out-Null
        }
        CaEnPem = {
            param($certificado)
            "-----BEGIN CERTIFICATE-----`r`n" + [Convert]::ToBase64String($certificado.RawData, [Base64FormattingOptions]::InsertLineBreaks) + "`r`n-----END CERTIFICATE-----`r`n"
        }
        AgregarARaiz = {
            param($certificado)
            $almacen = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root", "CurrentUser")
            $almacen.Open("ReadWrite")
            try { $almacen.Add((New-Object System.Security.Cryptography.X509Certificates.X509Certificate2(, $certificado.RawData))) }
            finally { $almacen.Close() }
        }
        ArrancarServidor = {
            param($a)
            $info = New-Object System.Diagnostics.ProcessStartInfo
            $info.FileName = $a.Python
            $info.Arguments = ('-B "{0}" --pfx "{1}" --ca "{2}" --puerto {3} --resultado "{4}" --parar "{5}" --plazo {6} --cn-esperado invitado-brave' -f $a.Servidor, $a.Pfx, $a.Ca, $a.Puerto, $a.Resultado, $a.Parar, $a.Plazo)
            $info.UseShellExecute = $false
            $info.RedirectStandardInput = $true
            $p = [System.Diagnostics.Process]::Start($info)
            $p.StandardInput.WriteLine($a.Contrasena)
            $p.StandardInput.Close()
            $p
        }
        AbrirBrave = {
            param($exe, $perfil, $url)
            Start-Process -FilePath $exe -ArgumentList @("--user-data-dir=`"$perfil`"", "--no-first-run", "--no-default-browser-check", "--new-window", $url) | Out-Null
        }
        ConsultarProcesos = { Get-CimInstance -ClassName Win32_Process -Filter "Name = 'brave.exe'" -ErrorAction Stop }
        DetenerProceso = {
            param($id)
            try { Stop-Process -Id $id -Force -ErrorAction Stop }
            catch { if (Get-Process -Id $id -ErrorAction SilentlyContinue) { throw } }  # ya terminado: correcto
        }
        QuitarDeRaiz = {
            param($r)
            $almacen = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root", "CurrentUser")
            $almacen.Open("ReadWrite")
            try {
                foreach ($c in @($almacen.Certificates.Find("FindByThumbprint", $r.huella, $false))) {
                    if ($c.Subject -eq $r.sujeto) { $almacen.Remove($c) }
                }
            } finally { $almacen.Close() }
        }
        BorrarCertificadoYClave = {
            param($r)
            $ruta = "Cert:\CurrentUser\My\" + $r.huella
            if (Test-Path -LiteralPath $ruta) {
                $c = Get-Item -LiteralPath $ruta
                if ($c.FriendlyName -ne $r.marca) { throw "el certificado con esa huella no lleva la marca de esta ejecucion; no se toca" }
                Remove-Item -LiteralPath $ruta -DeleteKey   # certificado Y su clave privada
            }
            $ksp = [System.Security.Cryptography.CngProvider]::MicrosoftSoftwareKeyStorageProvider
            if ($r.clave -and [System.Security.Cryptography.CngKey]::Exists([string]$r.clave, $ksp)) {
                $k = [System.Security.Cryptography.CngKey]::Open([string]$r.clave, $ksp)
                $k.Delete()   # contenedor registrado EN MEMORIA al crear el certificado de esta ejecucion
            }
        }
        BorrarCarpeta = {
            param($ruta)
            for ($i = 0; $i -lt 10 -and (Test-Path -LiteralPath $ruta); $i++) {
                Remove-Item -LiteralPath $ruta -Recurse -Force -ErrorAction SilentlyContinue
                if (Test-Path -LiteralPath $ruta) { Start-Sleep -Milliseconds 500 }
            }
            if (Test-Path -LiteralPath $ruta) { throw "no se pudo borrar la carpeta temporal" }
        }
        ExisteEnPersonal = { param($r) Test-Path -LiteralPath ("Cert:\CurrentUser\My\" + $r.huella) }
        ExisteEnRaiz = {
            param($r)
            $almacen = New-Object System.Security.Cryptography.X509Certificates.X509Store("Root", "CurrentUser")
            $almacen.Open("ReadOnly")
            try { @($almacen.Certificates.Find("FindByThumbprint", $r.huella, $false)).Count -gt 0 } finally { $almacen.Close() }
        }
        ExisteClave = {
            param($r)
            if (-not $r.clave) { throw "sin identificador de clave: no verificable" }
            [System.Security.Cryptography.CngKey]::Exists([string]$r.clave, [System.Security.Cryptography.CngProvider]::MicrosoftSoftwareKeyStorageProvider)
        }
        Pausa = { param($ms) Start-Sleep -Milliseconds $ms }
    }
}
