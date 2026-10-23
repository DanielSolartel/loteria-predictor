# Windows PowerShell 5.1. La accion predeterminada solo prepara un plan.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Worktree,
    [Parameter(Mandatory=$true)][string]$PythonExe,
    [Parameter(Mandatory=$true)][string]$Configuracion,
    [string]$Evidencia,
    [switch]$Plan,
    [switch]$Instalar,
    [switch]$Activar,
    [switch]$Pausar,
    [switch]$Reanudar,
    [switch]$Estado,
    [switch]$Desinstalar
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$Utf8 = New-Object System.Text.UTF8Encoding($false, $true)
# Register-ScheduledTask -Xml recibe una cadena Unicode, no bytes UTF-8.
# El archivo de evidencia usa la misma declaracion y UTF-16LE con BOM.
$UnicodeXml = New-Object System.Text.UnicodeEncoding($false, $true, $true)
$Marca = 'LoteriaPredictor/Fase6/tarea/1'
$Codigo = 1
$RutaResultado = $null
$RutaRegistro = $null
$Resultado = [ordered]@{
    version = 1; componente = 'fase6_tarea'; estado = 'error'; codigo = 1
    accion = $null; inicio_utc = [DateTime]::UtcNow.ToString('o'); error = $null
    tarea_modificada = $false; producto_ejecutado = $false; exportaciones = @()
}

function Get-Sha([string]$Texto) {
    $alg = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($alg.ComputeHash($Utf8.GetBytes($Texto)))).Replace('-','').ToLowerInvariant() }
    finally { $alg.Dispose() }
}
function Escape-Xml([string]$Texto) { return [Security.SecurityElement]::Escape($Texto) }
function Quote-Argument([string]$Texto) {
    # Reglas de CommandLineToArgvW para un argumento literal; no hay cmd.exe.
    return '"' + ([regex]::Replace([regex]::Replace($Texto, '(\\*)"', '$1$1\"'), '(\\+)$', '$1$1')) + '"'
}
function Get-Absoluta([string]$Ruta, [string]$Etiqueta) {
    if ([string]::IsNullOrWhiteSpace($Ruta) -or -not [IO.Path]::IsPathRooted($Ruta)) { throw ($Etiqueta + ' debe ser una ruta absoluta.') }
    if ($Ruta -match '[\x00-\x1f]') { throw ($Etiqueta + ' contiene caracteres de control.') }
    return [IO.Path]::GetFullPath($Ruta)
}
function Registrar([string]$Texto) {
    if ($null -ne $RutaRegistro) { [IO.File]::AppendAllText($RutaRegistro,([DateTime]::UtcNow.ToString('o') + ' ' + $Texto + "`n"),$Utf8) }
}
function Guardar-Resultado {
    if ($null -ne $RutaResultado) { [IO.File]::WriteAllText($RutaResultado,(($Resultado | ConvertTo-Json -Depth 12) + "`n"),$Utf8) }
}
function Get-UsuarioActual {
    if ([Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT) {
        $identidad = [Security.Principal.WindowsIdentity]::GetCurrent()
        return [pscustomobject]@{ Id=$identidad.User.Value; Nombre=$identidad.Name; Plataforma='Windows' }
    }
    # Permite inspeccionar el XML en Linux. Los cmdlets nativos se requieren
    # para actuar; este plan no acredita una instalacion de Windows.
    return [pscustomobject]@{ Id=[Environment]::UserName; Nombre=[Environment]::UserName; Plataforma='no_Windows_plan_portable' }
}
function Get-Tarea {
    try { return Get-ScheduledTask -TaskName $NombreTarea -TaskPath '\' -ErrorAction Stop }
    catch {
        if ($_.CategoryInfo.Category -eq [Management.Automation.ErrorCategory]::ObjectNotFound -or $_.FullyQualifiedErrorId -match 'CmdletizationQuery_NotFound') { return $null }
        throw
    }
}
function Get-ValorXml([xml]$Documento, [string]$Ruta) {
    $ns = New-Object Xml.XmlNamespaceManager($Documento.NameTable)
    $ns.AddNamespace('t','http://schemas.microsoft.com/windows/2004/02/mit/task')
    $nodos = $Documento.SelectNodes($Ruta,$ns)
    if ($nodos.Count -ne 1) { throw ('La tarea carece de un campo unico requerido: ' + $Ruta) }
    return [string]$nodos[0].InnerText
}
function Resolver-IdentidadSid([string]$Identidad) {
    if ([string]::IsNullOrWhiteSpace($Identidad)) { throw 'La identidad de la tarea esta vacia.' }
    $valor = $Identidad.Trim()
    try {
        if ($valor -match '^S-[0-9]+-[0-9]+(-[0-9]+)+$') {
            $sid = New-Object Security.Principal.SecurityIdentifier($valor)
        } else {
            $cuenta = New-Object Security.Principal.NTAccount($valor)
            $sid = $cuenta.Translate([Security.Principal.SecurityIdentifier])
        }
        return [string]$sid.Value
    } catch { throw ('No se pudo resolver la identidad de la tarea a SID: ' + $Identidad + '; ' + $_.Exception.Message) }
}
function Comprobar-CampoTarea([xml]$Documento,[string]$Ruta,[string]$Esperado,[string]$Tipo,[bool]$PermitirAusente=$false,[string]$Predeterminado='') {
    $ns = New-Object Xml.XmlNamespaceManager($Documento.NameTable)
    $ns.AddNamespace('t','http://schemas.microsoft.com/windows/2004/02/mit/task')
    $nodos = $Documento.SelectNodes($Ruta,$ns)
    $fila = [ordered]@{ruta=$Ruta;tipo=$Tipo;esperado=$Esperado;valor_xml=$null;valor_semantico=$null;origen='explicito';fundamento=$null;coincide=$false;error=$null}
    try {
        if ($nodos.Count -gt 1) { throw ('Campo duplicado en la tarea: ' + $Ruta) }
        if ($nodos.Count -eq 0) {
            if (-not $PermitirAusente) { throw ('La tarea carece del campo requerido: ' + $Ruta) }
            $valor=$Predeterminado; $fila.origen='predeterminado_documentado'
            if($Ruta -eq '/t:Task/t:Principals/t:Principal/t:RunLevel') {
                # El XSD permite la omision; el valor minimo corresponde a
                # Principal.RunLevel TASK_RUNLEVEL_LUA (0), no a un default XSD.
                $fila.fundamento='Principal.RunLevel: TASK_RUNLEVEL_LUA (0); omision admitida por el esquema'
            } else { $fila.fundamento='Predeterminado explicito del esquema Task Scheduler para este campo' }
        } else {
            if ($nodos[0].ChildNodes | Where-Object { $_ -is [Xml.XmlElement] }) { throw ('Campo no escalar en la tarea: ' + $Ruta) }
            $valor=[string]$nodos[0].InnerText; $fila.valor_xml=$valor
        }
        if ([string]::IsNullOrWhiteSpace($valor)) { throw ('Campo vacio en la tarea: ' + $Ruta) }
        if ($Tipo -eq 'sid') {
            $actual=Resolver-IdentidadSid $valor
            $objetivo=Resolver-IdentidadSid $Esperado
            $fila.valor_semantico=$actual; $coincide=$actual -ceq $objetivo
        } elseif ($Tipo -eq 'booleano') {
            $actual=[Xml.XmlConvert]::ToBoolean($valor.Trim())
            $objetivo=[Xml.XmlConvert]::ToBoolean($Esperado)
            $fila.valor_semantico=$actual; $coincide=$actual -eq $objetivo
        } elseif ($Tipo -eq 'duracion') {
            $actual=[Xml.XmlConvert]::ToTimeSpan($valor.Trim())
            $objetivo=[Xml.XmlConvert]::ToTimeSpan($Esperado)
            $fila.valor_semantico=$actual.ToString(); $coincide=$actual.Ticks -eq $objetivo.Ticks
        } elseif ($Tipo -eq 'fecha') {
            $actual=[Xml.XmlConvert]::ToDateTime($valor.Trim(),[Xml.XmlDateTimeSerializationMode]::RoundtripKind)
            $fila.valor_semantico=$actual.ToString('o'); $coincide=$true
        } elseif ($Tipo -eq 'ruta_windows') {
            $fila.valor_semantico=$valor; $coincide=[string]::Equals($valor,$Esperado,[StringComparison]::OrdinalIgnoreCase)
        } else {
            $fila.valor_semantico=$valor; $coincide=$valor -ceq $Esperado
        }
        $fila.coincide=$coincide
        if (-not $coincide) { throw ('Tarea ajena o modificada; se conserva sin cambios: ' + $Ruta) }
    } catch {
        $fila.error=$_.Exception.Message
        throw
    } finally { $DiagnosticoActual.campos+=@([pscustomobject]$fila) }
}
function Assert-TareaPropia {
    $clave=[Guid]::NewGuid().ToString('N')
    $rutaExportada=Join-Path $Evidencia ('exportada-'+$clave+'.xml')
    $rutaDiagnostico=Join-Path $Evidencia ('validacion-'+$clave+'.json')
    $DiagnosticoActual=[ordered]@{version=1;tipo='validacion_tarea_exportada';estado='pendiente';error=$null;tarea=$NombreTarea;exportacion_xml=$null;formato_exportacion='cadena original, UTF-16LE con BOM';bytes_exportacion=$null;sha256_exportacion=$null;campos=@()}
    $Resultado.exportaciones+=@([ordered]@{xml=$null;diagnostico=$rutaDiagnostico})
    $referencia=$Resultado.exportaciones[-1]
    try {
        $exportada=[string](Export-ScheduledTask -TaskName $NombreTarea -TaskPath '\' -ErrorAction Stop)
        if (Test-Path -LiteralPath $rutaExportada) { throw 'La exportacion no debe sobrescribir evidencia previa.' }
        # Archivar la cadena recibida ANTES del parseo y de cualquier validacion.
        # La declaracion y espacios originales no se reescriben para diagnosticar.
        [IO.File]::WriteAllText($rutaExportada,$exportada,$UnicodeXml)
        $DiagnosticoActual.exportacion_xml=$rutaExportada; $referencia.xml=$rutaExportada
        $bytesExportados=[IO.File]::ReadAllBytes($rutaExportada)
        $DiagnosticoActual.bytes_exportacion=$bytesExportados.Length
        $algExportada=[Security.Cryptography.SHA256]::Create()
        try { $DiagnosticoActual.sha256_exportacion=([BitConverter]::ToString($algExportada.ComputeHash($bytesExportados))).Replace('-','').ToLowerInvariant() }
        finally { $algExportada.Dispose() }
        [IO.File]::WriteAllText($rutaDiagnostico,(($DiagnosticoActual | ConvertTo-Json -Depth 12)+"`n"),$Utf8)
        Guardar-Resultado
        $lectura=New-Object Xml.XmlReaderSettings
        $lectura.DtdProcessing=[Xml.DtdProcessing]::Prohibit
        $lectura.XmlResolver=$null
        $entrada=New-Object IO.StringReader($exportada)
        $lector=$null
        try {
            $lector=[Xml.XmlReader]::Create($entrada,$lectura)
            $xmlActual=New-Object Xml.XmlDocument
            $xmlActual.PreserveWhitespace=$true; $xmlActual.XmlResolver=$null
            $xmlActual.Load($lector)
        } finally { if($null -ne $lector){$lector.Dispose()}; $entrada.Dispose() }
        $ns = New-Object Xml.XmlNamespaceManager($xmlActual.NameTable)
        $ns.AddNamespace('t','http://schemas.microsoft.com/windows/2004/02/mit/task')
        foreach($ruta in @('/t:Task','/t:Task/t:RegistrationInfo','/t:Task/t:Principals','/t:Task/t:Principals/t:Principal','/t:Task/t:Settings','/t:Task/t:Actions','/t:Task/t:Triggers')) {
            if($xmlActual.SelectNodes($ruta,$ns).Count -ne 1){throw ('La tarea carece de una seccion unica requerida: '+$ruta)}
        }
        if ($xmlActual.SelectNodes('/t:Task/t:Principals/*',$ns).Count -ne 1 -or $xmlActual.SelectNodes('/t:Task/t:Principals/t:Principal/t:GroupId',$ns).Count -ne 0) { throw 'La tarea tiene principales ajenos; no se modifica.' }
        if ($xmlActual.SelectNodes('/t:Task/t:Actions/*',$ns).Count -ne 1 -or $xmlActual.SelectNodes('/t:Task/t:Actions/t:Exec',$ns).Count -ne 1 -or $xmlActual.SelectNodes('/t:Task/t:Triggers/*',$ns).Count -ne 2 -or $xmlActual.SelectNodes('/t:Task/t:Triggers/t:TimeTrigger',$ns).Count -ne 1 -or $xmlActual.SelectNodes('/t:Task/t:Triggers/t:LogonTrigger',$ns).Count -ne 1) { throw 'La tarea tiene acciones o desencadenadores ajenos; no se modifica.' }
        foreach($nodo in $xmlActual.SelectNodes('/t:Task/t:Principals/t:Principal/*',$ns)) {
            if($nodo.NamespaceURI -cne 'http://schemas.microsoft.com/windows/2004/02/mit/task' -or $nodo.LocalName -cnotin @('UserId','LogonType','RunLevel')) { throw 'La tarea tiene opciones de principal ajenas; no se modifica.' }
        }
        foreach($nodo in $xmlActual.SelectNodes('/t:Task/t:Actions/t:Exec/*',$ns)) {
            if($nodo.NamespaceURI -cne 'http://schemas.microsoft.com/windows/2004/02/mit/task' -or $nodo.LocalName -cnotin @('Command','Arguments','WorkingDirectory')) { throw 'La tarea tiene opciones de accion ajenas; no se modifica.' }
        }
        $hijosDisparo=@{
            '/t:Task/t:Triggers/t:TimeTrigger'=@('Enabled','StartBoundary','Repetition','RandomDelay')
            '/t:Task/t:Triggers/t:LogonTrigger'=@('Enabled','UserId','Delay')
            '/t:Task/t:Triggers/t:TimeTrigger/t:Repetition'=@('Interval','StopAtDurationEnd')
        }
        foreach($ruta in $hijosDisparo.Keys) {
            foreach($nodo in $xmlActual.SelectNodes($ruta+'/*',$ns)) {
                if($nodo.NamespaceURI -cne 'http://schemas.microsoft.com/windows/2004/02/mit/task' -or $nodo.LocalName -cnotin $hijosDisparo[$ruta]) { throw ('La tarea tiene opciones de disparo ajenas: '+$ruta) }
            }
        }
        $principal=$xmlActual.SelectSingleNode('/t:Task/t:Principals/t:Principal',$ns)
        $acciones=$xmlActual.SelectSingleNode('/t:Task/t:Actions',$ns)
        if($principal.GetAttribute('id') -cne 'Usuario' -or $acciones.GetAttribute('Context') -cne $principal.GetAttribute('id')) { throw 'El contexto de acciones no identifica al principal propio; no se modifica.' }
        $campos=@(
            @('/t:Task/t:RegistrationInfo/t:Source',$Marca,'texto'),
            @('/t:Task/t:RegistrationInfo/t:Description',$Descripcion,'texto'),
            @('/t:Task/t:Principals/t:Principal/t:UserId',$Usuario.Id,'sid'),
            @('/t:Task/t:Principals/t:Principal/t:LogonType','InteractiveToken','texto'),
            @('/t:Task/t:Principals/t:Principal/t:RunLevel','LeastPrivilege','texto'),
            @('/t:Task/t:Actions/t:Exec/t:Command',$PythonExe,'ruta_windows'),
            @('/t:Task/t:Actions/t:Exec/t:Arguments',$Argumentos,'texto'),
            @('/t:Task/t:Actions/t:Exec/t:WorkingDirectory',$Backend,'ruta_windows'),
            @('/t:Task/t:Settings/t:MultipleInstancesPolicy','IgnoreNew','texto'),
            @('/t:Task/t:Settings/t:ExecutionTimeLimit','PT2H','duracion'),
            @('/t:Task/t:Settings/t:WakeToRun','false','booleano'),
            @('/t:Task/t:Settings/t:StartWhenAvailable','true','booleano'),
            @('/t:Task/t:Triggers/t:TimeTrigger/t:Repetition/t:Interval','PT5M','duracion'),
            @('/t:Task/t:Triggers/t:LogonTrigger/t:UserId',$Usuario.Id,'sid')
        )
        foreach($campo in $campos) {
            $opcional=$campo[0] -eq '/t:Task/t:Principals/t:Principal/t:RunLevel' -or $campo[0] -eq '/t:Task/t:Settings/t:WakeToRun'
            Comprobar-CampoTarea $xmlActual $campo[0] $campo[1] $campo[2] $opcional $campo[1]
        }
        # Valores fijos del disparo y sus predeterminados publicados en el XSD.
        foreach($ruta in @('/t:Task/t:Triggers/t:TimeTrigger/t:Enabled','/t:Task/t:Triggers/t:LogonTrigger/t:Enabled')) { Comprobar-CampoTarea $xmlActual $ruta 'true' 'booleano' $true 'true' }
        Comprobar-CampoTarea $xmlActual '/t:Task/t:Triggers/t:TimeTrigger/t:Repetition/t:StopAtDurationEnd' 'false' 'booleano' $true 'false'
        Comprobar-CampoTarea $xmlActual '/t:Task/t:Triggers/t:TimeTrigger/t:StartBoundary' 'fecha valida' 'fecha'
        Comprobar-CampoTarea $xmlActual '/t:Task/t:Triggers/t:TimeTrigger/t:RandomDelay' 'PT0M' 'duracion' $true 'PT0M'
        Comprobar-CampoTarea $xmlActual '/t:Task/t:Triggers/t:LogonTrigger/t:Delay' 'PT0M' 'duracion' $true 'PT0M'
        foreach($ruta in @('/t:Task/t:Triggers/*/t:EndBoundary','/t:Task/t:Triggers/t:TimeTrigger/t:Repetition/t:Duration','/t:Task/t:Triggers/t:LogonTrigger/t:Repetition')) {
            if($xmlActual.SelectNodes($ruta,$ns).Count -ne 0){throw ('La tarea tiene limites o repeticion de disparo ajenos: '+$ruta)}
        }
        $DiagnosticoActual.estado='aprobada'
        return $xmlActual
    } catch {
        $DiagnosticoActual.estado='rechazada'; $DiagnosticoActual.error=$_.Exception.Message
        throw
    } finally {
        [IO.File]::WriteAllText($rutaDiagnostico,(($DiagnosticoActual | ConvertTo-Json -Depth 12)+"`n"),$Utf8)
    }
}

try {
    # Evidencia propia, conservada incluso cuando falla una guarda posterior.
    if ([string]::IsNullOrWhiteSpace($Evidencia)) { $Evidencia=Join-Path ([IO.Path]::GetTempPath()) ('lp6-tarea-' + [Guid]::NewGuid().ToString('N')) }
    $Evidencia=Get-Absoluta $Evidencia 'Evidencia'
    if (Test-Path -LiteralPath $Evidencia) { throw 'La carpeta de evidencia debe ser nueva para no sobrescribir registros.' }
    [void][IO.Directory]::CreateDirectory($Evidencia)
    $RutaResultado=Join-Path $Evidencia 'resultado.json'; $RutaRegistro=Join-Path $Evidencia 'registro.log'
    $Resultado.evidencia=$Evidencia
    Guardar-Resultado; Registrar 'Inicio del control explicito de la tarea; no se ejecuta Python ni el producto.'
    $modos=@(@{nombre='Plan';valor=$Plan},@{nombre='Instalar';valor=$Instalar},@{nombre='Activar';valor=$Activar},@{nombre='Pausar';valor=$Pausar},@{nombre='Reanudar';valor=$Reanudar},@{nombre='Estado';valor=$Estado},@{nombre='Desinstalar';valor=$Desinstalar})
    $pedidos=@($modos | Where-Object { $_.valor })
    if ($pedidos.Count -gt 1) { throw 'Seleccione una sola accion de tarea.' }
    $Accion=if ($pedidos.Count -eq 0) { 'Plan' } else { $pedidos[0].nombre }
    $Resultado.accion=$Accion
    $Worktree=(Get-Absoluta $Worktree 'Worktree').TrimEnd([IO.Path]::DirectorySeparatorChar)
    $PythonExe=Get-Absoluta $PythonExe 'PythonExe'; $Configuracion=Get-Absoluta $Configuracion 'Configuracion'
    if ($Evidencia -eq $Worktree -or $Evidencia.StartsWith($Worktree+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'La evidencia debe quedar fuera del worktree.' }
    $Backend=Join-Path $Worktree 'backend'
    if (-not (Test-Path -LiteralPath (Join-Path $Backend 'scripts/operacion_automatica.py') -PathType Leaf)) { throw 'Falta el ejecutor Fase 6 en el backend indicado.' }
    if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) { throw 'No existe PythonExe; use el interprete validado sin actualizarlo.' }
    if (-not (Test-Path -LiteralPath $Configuracion -PathType Leaf)) { throw 'No existe la configuracion operativa explicita; preparela y verifique sus destinos primero.' }
    $Usuario=Get-UsuarioActual
    $NombreTarea='LP6-' + (Get-Sha ($Worktree.ToUpperInvariant()+"`n"+$Usuario.Id.ToUpperInvariant())).Substring(0,16)
    $Argumentos='-m scripts.operacion_automatica --config ' + (Quote-Argument $Configuracion) + ' ciclo'
    $huella=Get-Sha ($Worktree.ToUpperInvariant()+"`n"+$PythonExe.ToUpperInvariant()+"`n"+$Configuracion.ToUpperInvariant()+"`n"+$Usuario.Id.ToUpperInvariant()+"`nPT5M`nPT2H")
    $Descripcion=$Marca + '; vinculacion=' + $huella
    $inicio=[DateTime]::Now.AddMinutes(5).ToString('yyyy-MM-ddTHH:mm:ss')
    $Xml=@"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Date>$([DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ'))</Date><Author>$(Escape-Xml $Usuario.Nombre)</Author><Description>$(Escape-Xml $Descripcion)</Description><Source>$(Escape-Xml $Marca)</Source><URI>\$NombreTarea</URI></RegistrationInfo>
  <Triggers>
    <TimeTrigger><Repetition><Interval>PT5M</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition><StartBoundary>$inicio</StartBoundary><Enabled>true</Enabled></TimeTrigger>
    <LogonTrigger><Enabled>true</Enabled><UserId>$(Escape-Xml $Usuario.Id)</UserId></LogonTrigger>
  </Triggers>
  <Principals><Principal id="Usuario"><UserId>$(Escape-Xml $Usuario.Id)</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><AllowHardTerminate>true</AllowHardTerminate><StartWhenAvailable>true</StartWhenAvailable><RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable><AllowStartOnDemand>true</AllowStartOnDemand><Enabled>false</Enabled><Hidden>false</Hidden><WakeToRun>false</WakeToRun><ExecutionTimeLimit>PT2H</ExecutionTimeLimit><Priority>7</Priority></Settings>
  <Actions Context="Usuario"><Exec><Command>$(Escape-Xml $PythonExe)</Command><Arguments>$(Escape-Xml $Argumentos)</Arguments><WorkingDirectory>$(Escape-Xml $Backend)</WorkingDirectory></Exec></Actions>
</Task>
"@
    [xml]$validacionXml=$Xml
    $RutaXml=Join-Path $Evidencia 'tarea.xml'; [IO.File]::WriteAllText($RutaXml,$Xml,$UnicodeXml)
    $Resultado.tarea=$NombreTarea; $Resultado.usuario=$Usuario.Id; $Resultado.plataforma=$Usuario.Plataforma
    $Resultado.worktree=$Worktree; $Resultado.python=$PythonExe; $Resultado.configuracion=$Configuracion
    $Resultado.plan_xml=$RutaXml; $Resultado.huella_vinculacion=$huella
    $Resultado.sesion='usuario actual con sesion abierta; no ejecuta con PC apagado o sesion cerrada'
    if ($Accion -eq 'Plan') {
        $Resultado.estado='plan_no_instalado'; $Codigo=0
        Registrar 'XML deshabilitado preparado; ningun cmdlet del Programador fue invocado.'
    } else {
        foreach ($cmd in @('Get-ScheduledTask','Export-ScheduledTask','Register-ScheduledTask','Enable-ScheduledTask','Disable-ScheduledTask','Unregister-ScheduledTask')) { [void](Get-Command $cmd -ErrorAction Stop) }
        $tarea=Get-Tarea
        if ($null -ne $tarea) { [void](Assert-TareaPropia) }
        if ($Accion -eq 'Instalar') {
            if ($null -eq $tarea) {
                [void](Register-ScheduledTask -TaskName $NombreTarea -TaskPath '\' -Xml $Xml -ErrorAction Stop)
                $Resultado.tarea_modificada=$true
                $tarea=Get-Tarea; [void](Assert-TareaPropia)
                if ($null -eq $tarea -or [bool]$tarea.Settings.Enabled) { throw 'La tarea no quedo registrada deshabilitada; revisar antes de activar.' }
                $Resultado.estado='instalada_deshabilitada'
            } else { $Resultado.estado='ya_instalada_sin_reescribir' }
        } elseif ($Accion -eq 'Estado') {
            $Resultado.estado=if ($null -eq $tarea) { 'no_instalada' } else { 'consultada' }
        } elseif ($Accion -eq 'Desinstalar') {
            if ($null -eq $tarea) { $Resultado.estado='ya_ausente' }
            else {
                if ([string]$tarea.State -eq 'Running') { throw 'Hay un ciclo vivo: pause futuras ejecuciones y espere su cierre antes de desinstalar.' }
                [void](Disable-ScheduledTask -TaskName $NombreTarea -TaskPath '\' -ErrorAction Stop)
                [void](Unregister-ScheduledTask -TaskName $NombreTarea -TaskPath '\' -Confirm:$false -ErrorAction Stop)
                $Resultado.tarea_modificada=$true; $tarea=$null; $Resultado.estado='desinstalada'
            }
        } else {
            if ($null -eq $tarea) { throw 'La tarea no existe: audite el plan e instale deshabilitada antes de activarla.' }
            if ($Accion -eq 'Pausar') { [void](Disable-ScheduledTask -TaskName $NombreTarea -TaskPath '\' -ErrorAction Stop); $Resultado.estado='tarea_pausada' }
            else { [void](Enable-ScheduledTask -TaskName $NombreTarea -TaskPath '\' -ErrorAction Stop); $Resultado.estado='tarea_habilitada' }
            $Resultado.tarea_modificada=$true; $tarea=Get-Tarea; [void](Assert-TareaPropia)
        }
        if ($null -ne $tarea) { $Resultado.habilitada=[bool]$tarea.Settings.Enabled; $Resultado.estado_programador=[string]$tarea.State }
        $Codigo=0; Registrar ('Accion completada: '+$Resultado.estado)
    }
} catch {
    $Codigo=1; $Resultado.estado='error'; $Resultado.error=$_.Exception.Message
    Registrar ('Fallo: '+$Resultado.error)
} finally {
    $Resultado.codigo=$Codigo; $Resultado.fin_utc=[DateTime]::UtcNow.ToString('o')
    Guardar-Resultado
}
if ($null -ne $RutaResultado) { Write-Output ('Evidencia: '+$RutaResultado) }
if ($Codigo -ne 0) { Write-Error -Message ([string]$Resultado.error) -ErrorAction Continue }
exit $Codigo
