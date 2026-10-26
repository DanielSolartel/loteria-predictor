# Windows PowerShell 5.1. La accion predeterminada solo prepara un plan.
# Version 2 de la tarea (Fase 6, horario por juego): disparadores semanales derivados del plan que
# imprime `python -m scripts.operacion_automatica --config ... horario plan --salida <archivo>`; sin
# disparo al iniciar sesion ni repeticion continua; StartWhenAvailable=false. La accion llama a
# `ciclo --programado --plan <huella>`. La version 1 (repeticion PT5M e inicio de sesion) se reconoce
# con sus comprobaciones exactas solo para pausarla, consultarla, desinstalarla o migrarla.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Worktree,
    [Parameter(Mandatory=$true)][string]$PythonExe,
    [Parameter(Mandatory=$true)][string]$Configuracion,
    [string]$Evidencia,
    [string]$PlanHorario,
    [string]$XmlAnterior,
    [switch]$Plan,
    [switch]$Instalar,
    [switch]$Activar,
    [switch]$Pausar,
    [switch]$Reanudar,
    [switch]$Estado,
    [switch]$Desinstalar,
    [switch]$Migrar,
    [switch]$Revertir
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$Utf8 = New-Object System.Text.UTF8Encoding($false, $true)
# Register-ScheduledTask -Xml recibe una cadena Unicode, no bytes UTF-8.
# El archivo de evidencia usa la misma declaracion y UTF-16LE con BOM.
$UnicodeXml = New-Object System.Text.UnicodeEncoding($false, $true, $true)
$Marca1 = 'LoteriaPredictor/Fase6/tarea/1'
$Marca2 = 'LoteriaPredictor/Fase6/tarea/2'
# URI del espacio de nombres de Task Scheduler. Su nombre no debe coincidir, sin distinguir mayusculas,
# con ninguna variable local: PowerShell no las distingue (F92-PS-01: `$ns` local tapaba la URI).
$UriTarea = 'http://schemas.microsoft.com/windows/2004/02/mit/task'
$DiasWindows = @('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday')
$PlanCargado = $null
$Codigo = 1
$RutaResultado = $null
$RutaRegistro = $null
$Resultado = [ordered]@{
    version = 2; componente = 'fase6_tarea'; estado = 'error'; codigo = 1
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
            } elseif($Ruta -eq '/t:Task/t:Settings/t:StartWhenAvailable') {
                # F92-NAT-01: el Programador omite el elemento al exportar su predeterminado.
                $fila.fundamento='Settings.StartWhenAvailable: predeterminado false del esquema Task Scheduler; el Programador puede omitirlo al exportar'
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
            try { $actual=[Xml.XmlConvert]::ToBoolean($valor.Trim()) } catch { throw ('Valor no booleano en la tarea: ' + $Ruta) }
            $objetivo=[Xml.XmlConvert]::ToBoolean($Esperado)
            $fila.valor_semantico=$actual; $coincide=$actual -eq $objetivo
        } elseif ($Tipo -eq 'duracion') {
            $actual=[Xml.XmlConvert]::ToTimeSpan($valor.Trim())
            $objetivo=[Xml.XmlConvert]::ToTimeSpan($Esperado)
            $fila.valor_semantico=$actual.ToString(); $coincide=$actual.Ticks -eq $objetivo.Ticks
        } elseif ($Tipo -eq 'instante') {
            # Instante del disparador de la version 2: el plan lleva el desfase fijo de Bogota. Una
            # exportacion sin desfase se interpreta en la zona del equipo; si no es Bogota, no coincide.
            $actual=[DateTimeOffset]::Parse($valor.Trim(),[Globalization.CultureInfo]::InvariantCulture)
            $objetivo=[DateTimeOffset]::Parse($Esperado,[Globalization.CultureInfo]::InvariantCulture)
            $fila.valor_semantico=$actual.ToString('o'); $coincide=$actual.UtcTicks -eq $objetivo.UtcTicks
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

function Get-DisparadoresXml($Lista) {
    # Mismo texto que `operacion_horario.xml_disparadores` (se compara con el del plan).
    $sb=New-Object Text.StringBuilder
    foreach($d in $Lista) {
        [void]$sb.Append('<CalendarTrigger>')
        if($null -ne $d.intervalo) { [void]$sb.Append('<Repetition><Interval>'+$d.intervalo+'</Interval><Duration>'+$d.duracion+'</Duration><StopAtDurationEnd>false</StopAtDurationEnd></Repetition>') }
        [void]$sb.Append('<StartBoundary>'+$d.inicio+'</StartBoundary><Enabled>true</Enabled><ScheduleByWeek><DaysOfWeek>')
        foreach($n in @($d.dias)) { [void]$sb.Append('<'+$n+' />') }
        [void]$sb.Append('</DaysOfWeek><WeeksInterval>1</WeeksInterval></ScheduleByWeek></CalendarTrigger>')
    }
    return $sb.ToString()
}
function Restore-TextoLiteral($Valor,[string]$Prefijo) {
    if ($Valor -is [Management.Automation.PSCustomObject]) {
        foreach ($p in @($Valor.PSObject.Properties)) {
            if ($p.Value -is [string]) { if ($p.Value.StartsWith($Prefijo,[StringComparison]::Ordinal)) { $p.Value=$p.Value.Substring($Prefijo.Length) } }
            else { Restore-TextoLiteral $p.Value $Prefijo }
        }
    } elseif ($Valor -is [Array]) {
        for ($i=0; $i -lt $Valor.Count; $i++) {
            if ($Valor[$i] -is [string]) { if ($Valor[$i].StartsWith($Prefijo,[StringComparison]::Ordinal)) { $Valor[$i]=$Valor[$i].Substring($Prefijo.Length) } }
            else { Restore-TextoLiteral $Valor[$i] $Prefijo }
        }
    }
}
function ConvertFrom-JsonTextoLiteral([string]$Texto) {
    # ConvertFrom-Json de PowerShell 7 convierte en DateTime las cadenas ISO 8601 completas y pierde su
    # texto y su desfase (F92-PS-02); -DateKind String solo existe desde 7.5 y no en Windows PowerShell 5.1.
    # Las cadenas que empiezan como fecha ISO se marcan antes de convertir y se restauran despues, con el
    # mismo resultado en 5.1 y 7.x. Un texto que ya contiene el marcador reservado se rechaza.
    $prefijo='lp6-literal:'
    if ($Texto.Contains($prefijo)) { throw 'El plan contiene el marcador reservado de lectura; no se admite.' }
    $marcado=[regex]::Replace($Texto,'(?<!\\)"(?=[0-9]{4}-[0-9]{2}-[0-9]{2}T)',('"'+$prefijo))
    $objeto=$marcado | ConvertFrom-Json
    Restore-TextoLiteral $objeto $prefijo
    return $objeto
}
function Read-PlanHorario([string]$Ruta) {
    $Ruta=Get-Absoluta $Ruta 'PlanHorario'
    if (-not (Test-Path -LiteralPath $Ruta -PathType Leaf)) { throw 'No existe el plan de horario indicado.' }
    $bytes=[IO.File]::ReadAllBytes($Ruta)
    if ($bytes.Length -gt 262144) { throw 'El plan de horario supera el tamano admitido.' }
    $plan=ConvertFrom-JsonTextoLiteral $Utf8.GetString($bytes)
    $claves=@($plan.PSObject.Properties | ForEach-Object { $_.Name })
    foreach($c in @('version','zona','desfase','politica','disparadores','texto','huella','xml_disparadores')) {
        if ($claves -cnotcontains $c) { throw ('Plan de horario incompleto: falta ' + $c) }
    }
    if ($plan.version -ne 1 -or [string]$plan.zona -cne 'America/Bogota') { throw 'Version o zona del plan no admitidas.' }
    # Bogota no tiene horario de verano: todos los inicios llevan su desfase fijo, como en el nucleo.
    if (-not ($plan.desfase -is [string]) -or [string]$plan.desfase -cne '-05:00') { throw 'Desfase del plan no admitido.' }
    if ([string]$plan.huella -cnotmatch '^[0-9a-f]{64}$') { throw 'Huella del plan no valida.' }
    $lista=@($plan.disparadores)
    if ($lista.Count -lt 1 -or $lista.Count -gt 20) { throw 'El plan debe tener entre 1 y 20 disparadores.' }
    $lineas=New-Object Collections.Generic.List[string]
    $lineas.Add('LP6-HORARIO/1|America/Bogota')
    foreach($d in $lista) {
        $campos=@($d.PSObject.Properties | ForEach-Object { $_.Name })
        foreach($c in @('tipo','inicio','dias','intervalo','duracion')) { if ($campos -cnotcontains $c) { throw ('Disparador incompleto: falta ' + $c) } }
        if ([string]$d.tipo -cnotin @('franja','recuperacion')) { throw 'Tipo de disparador no admitido.' }
        if (-not ($d.inicio -is [string]) -or $d.inicio -cnotmatch '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:00[+-][0-9]{2}:[0-9]{2}$') { throw 'Inicio de disparador no valido.' }
        if (-not $d.inicio.EndsWith([string]$plan.desfase,[StringComparison]::Ordinal)) { throw 'Inicio de disparador con un desfase distinto del plan.' }
        $dias=@($d.dias)
        if ($dias.Count -lt 1 -or $dias.Count -gt 7 -or @($dias | Select-Object -Unique).Count -ne $dias.Count) { throw 'Dias del disparador vacios o repetidos.' }
        foreach($n in $dias) { if ([string]$n -cnotin $DiasWindows) { throw 'Dia del disparador no admitido.' } }
        if ($null -eq $d.intervalo) {
            if ($null -ne $d.duracion) { throw 'Duracion sin intervalo en el plan.' }
        } elseif ([string]$d.intervalo -cnotmatch '^PT([0-9]+H)?([0-9]+M)?$' -or [string]$d.duracion -cnotmatch '^PT([0-9]+H)?([0-9]+M)?$') {
            throw 'Intervalo o duracion del plan no validos.'
        }
        $intervalo=if ($null -eq $d.intervalo) { '-' } else { [string]$d.intervalo }
        $duracion=if ($null -eq $d.duracion) { '-' } else { [string]$d.duracion }
        $lineas.Add((@([string]$d.tipo,[string]$d.inicio,($dias -join ','),$intervalo,$duracion) -join '|'))
    }
    $canonico=($lineas -join "`n") + "`n"
    if ([string]$plan.texto -cne $canonico) { throw 'El texto del plan no corresponde a sus disparadores.' }
    if ((Get-Sha $canonico) -cne [string]$plan.huella) { throw 'La huella del plan no corresponde a su texto.' }
    $xmlDisparadores=Get-DisparadoresXml $lista
    if ([string]$plan.xml_disparadores -cne $xmlDisparadores) { throw 'El XML del plan no corresponde a sus disparadores.' }
    $alg=[Security.Cryptography.SHA256]::Create()
    try { $sha=([BitConverter]::ToString($alg.ComputeHash($bytes))).Replace('-','').ToLowerInvariant() } finally { $alg.Dispose() }
    return [pscustomobject]@{ Ruta=$Ruta; Huella=[string]$plan.huella; Disparadores=$lista; Xml=$xmlDisparadores; Sha256Archivo=$sha }
}
function Read-XmlSeguro([string]$Texto) {
    $lectura=New-Object Xml.XmlReaderSettings
    $lectura.DtdProcessing=[Xml.DtdProcessing]::Prohibit
    $lectura.XmlResolver=$null
    $entrada=New-Object IO.StringReader($Texto)
    $lector=$null
    try {
        $lector=[Xml.XmlReader]::Create($entrada,$lectura)
        $documento=New-Object Xml.XmlDocument
        $documento.PreserveWhitespace=$true; $documento.XmlResolver=$null
        $documento.Load($lector)
        # La coma impide que PowerShell desenrolle el documento (XmlNode es enumerable) al devolverlo.
        return ,$documento
    } finally { if($null -ne $lector){$lector.Dispose()}; $entrada.Dispose() }
}
function Assert-Hijos([xml]$Documento,[string]$Ruta,[string[]]$Admitidos,[string]$Mensaje) {
    $ns = New-Object Xml.XmlNamespaceManager($Documento.NameTable); $ns.AddNamespace('t',$UriTarea)
    foreach($nodo in $Documento.SelectNodes($Ruta+'/*',$ns)) {
        if($nodo.NamespaceURI -cne $UriTarea -or $nodo.LocalName -cnotin $Admitidos) { throw $Mensaje }
    }
}
function Assert-DocumentoPropio([xml]$xmlActual) {
    # Comprobaciones comunes y por version. Devuelve la version reconocida (1 o 2); cualquier otra
    # forma es ajena o esta modificada y se rechaza sin tocarla.
    $ns = New-Object Xml.XmlNamespaceManager($xmlActual.NameTable)
    $ns.AddNamespace('t',$UriTarea)
    foreach($ruta in @('/t:Task','/t:Task/t:RegistrationInfo','/t:Task/t:Principals','/t:Task/t:Principals/t:Principal','/t:Task/t:Settings','/t:Task/t:Actions','/t:Task/t:Triggers')) {
        if($xmlActual.SelectNodes($ruta,$ns).Count -ne 1){throw ('La tarea carece de una seccion unica requerida: '+$ruta)}
    }
    if ($xmlActual.SelectNodes('/t:Task/t:Principals/*',$ns).Count -ne 1 -or $xmlActual.SelectNodes('/t:Task/t:Principals/t:Principal/t:GroupId',$ns).Count -ne 0) { throw 'La tarea tiene principales ajenos; no se modifica.' }
    if ($xmlActual.SelectNodes('/t:Task/t:Actions/*',$ns).Count -ne 1 -or $xmlActual.SelectNodes('/t:Task/t:Actions/t:Exec',$ns).Count -ne 1) { throw 'La tarea tiene acciones ajenas; no se modifica.' }
    Assert-Hijos $xmlActual '/t:Task/t:Principals/t:Principal' @('UserId','LogonType','RunLevel') 'La tarea tiene opciones de principal ajenas; no se modifica.'
    Assert-Hijos $xmlActual '/t:Task/t:Actions/t:Exec' @('Command','Arguments','WorkingDirectory') 'La tarea tiene opciones de accion ajenas; no se modifica.'
    $principal=$xmlActual.SelectSingleNode('/t:Task/t:Principals/t:Principal',$ns)
    $acciones=$xmlActual.SelectSingleNode('/t:Task/t:Actions',$ns)
    if($principal.GetAttribute('id') -cne 'Usuario' -or $acciones.GetAttribute('Context') -cne $principal.GetAttribute('id')) { throw 'El contexto de acciones no identifica al principal propio; no se modifica.' }
    $fuente=Get-ValorXml $xmlActual '/t:Task/t:RegistrationInfo/t:Source'
    if ($fuente -ceq $Marca1) { $version=1 } elseif ($fuente -ceq $Marca2) { $version=2 } else { throw 'Tarea ajena o modificada; se conserva sin cambios: /t:Task/t:RegistrationInfo/t:Source' }
    if ($version -eq 2 -and $null -eq $PlanCargado) { throw 'La tarea es de la version 2: indique -PlanHorario para verificar sus disparadores.' }
    $campos=@(
        @('/t:Task/t:Principals/t:Principal/t:UserId',$Usuario.Id,'sid'),
        @('/t:Task/t:Principals/t:Principal/t:LogonType','InteractiveToken','texto'),
        @('/t:Task/t:Principals/t:Principal/t:RunLevel','LeastPrivilege','texto'),
        @('/t:Task/t:Actions/t:Exec/t:Command',$PythonExe,'ruta_windows'),
        @('/t:Task/t:Actions/t:Exec/t:WorkingDirectory',$Backend,'ruta_windows'),
        @('/t:Task/t:Settings/t:MultipleInstancesPolicy','IgnoreNew','texto'),
        @('/t:Task/t:Settings/t:ExecutionTimeLimit','PT2H','duracion'),
        @('/t:Task/t:Settings/t:WakeToRun','false','booleano')
    )
    if ($version -eq 1) {
        $campos+=@(
            @('/t:Task/t:RegistrationInfo/t:Source',$Marca1,'texto'),
            @('/t:Task/t:RegistrationInfo/t:Description',$DescripcionV1,'texto'),
            @('/t:Task/t:Actions/t:Exec/t:Arguments',$ArgumentosV1,'texto'),
            @('/t:Task/t:Settings/t:StartWhenAvailable','true','booleano'),
            @('/t:Task/t:Triggers/t:TimeTrigger/t:Repetition/t:Interval','PT5M','duracion'),
            @('/t:Task/t:Triggers/t:LogonTrigger/t:UserId',$Usuario.Id,'sid')
        )
    } else {
        $campos+=@(
            @('/t:Task/t:RegistrationInfo/t:Source',$Marca2,'texto'),
            @('/t:Task/t:RegistrationInfo/t:Description',$DescripcionV2,'texto'),
            @('/t:Task/t:Actions/t:Exec/t:Arguments',$ArgumentosV2,'texto'),
            @('/t:Task/t:Settings/t:StartWhenAvailable','false','booleano')
        )
    }
    # Campos que el esquema de Task Scheduler permite omitir, con su predeterminado DOCUMENTADO, nunca el valor
    # esperado: la omision toma ese valor y despues se compara con lo esperado (F92-NAT-01). Asi una v1, que
    # exige StartWhenAvailable=true, sigue rechazada si falta el campo. Tabla local: la sonda del auditor
    # evalua esta funcion fuera del script.
    $predeterminados=@{
        '/t:Task/t:Principals/t:Principal/t:RunLevel'='LeastPrivilege'
        '/t:Task/t:Settings/t:WakeToRun'='false'
        '/t:Task/t:Settings/t:StartWhenAvailable'='false'
    }
    foreach($campo in $campos) {
        $opcional=$predeterminados.ContainsKey($campo[0])
        $predeterminado=if ($opcional) { $predeterminados[$campo[0]] } else { '' }
        Comprobar-CampoTarea $xmlActual $campo[0] $campo[1] $campo[2] $opcional $predeterminado
    }
    if ($version -eq 1) {
        # Version anterior legitima: exactamente las comprobaciones auditadas, sin relajarlas.
        if ($xmlActual.SelectNodes('/t:Task/t:Triggers/*',$ns).Count -ne 2 -or $xmlActual.SelectNodes('/t:Task/t:Triggers/t:TimeTrigger',$ns).Count -ne 1 -or $xmlActual.SelectNodes('/t:Task/t:Triggers/t:LogonTrigger',$ns).Count -ne 1) { throw 'La tarea tiene acciones o desencadenadores ajenos; no se modifica.' }
        $hijosDisparo=@{
            '/t:Task/t:Triggers/t:TimeTrigger'=@('Enabled','StartBoundary','Repetition','RandomDelay')
            '/t:Task/t:Triggers/t:LogonTrigger'=@('Enabled','UserId','Delay')
            '/t:Task/t:Triggers/t:TimeTrigger/t:Repetition'=@('Interval','StopAtDurationEnd')
        }
        foreach($ruta in $hijosDisparo.Keys) { Assert-Hijos $xmlActual $ruta $hijosDisparo[$ruta] ('La tarea tiene opciones de disparo ajenas: '+$ruta) }
        foreach($ruta in @('/t:Task/t:Triggers/t:TimeTrigger/t:Enabled','/t:Task/t:Triggers/t:LogonTrigger/t:Enabled')) { Comprobar-CampoTarea $xmlActual $ruta 'true' 'booleano' $true 'true' }
        Comprobar-CampoTarea $xmlActual '/t:Task/t:Triggers/t:TimeTrigger/t:Repetition/t:StopAtDurationEnd' 'false' 'booleano' $true 'false'
        Comprobar-CampoTarea $xmlActual '/t:Task/t:Triggers/t:TimeTrigger/t:StartBoundary' 'fecha valida' 'fecha'
        Comprobar-CampoTarea $xmlActual '/t:Task/t:Triggers/t:TimeTrigger/t:RandomDelay' 'PT0M' 'duracion' $true 'PT0M'
        Comprobar-CampoTarea $xmlActual '/t:Task/t:Triggers/t:LogonTrigger/t:Delay' 'PT0M' 'duracion' $true 'PT0M'
        foreach($ruta in @('/t:Task/t:Triggers/*/t:EndBoundary','/t:Task/t:Triggers/t:TimeTrigger/t:Repetition/t:Duration','/t:Task/t:Triggers/t:LogonTrigger/t:Repetition')) {
            if($xmlActual.SelectNodes($ruta,$ns).Count -ne 0){throw ('La tarea tiene limites o repeticion de disparo ajenos: '+$ruta)}
        }
        return 1
    }
    # Version 2: solo los disparadores semanales del plan, en su orden, sin inicio de sesion.
    $lista=@($PlanCargado.Disparadores)
    if ($xmlActual.SelectNodes('/t:Task/t:Triggers/*',$ns).Count -ne $lista.Count -or $xmlActual.SelectNodes('/t:Task/t:Triggers/t:CalendarTrigger',$ns).Count -ne $lista.Count) { throw 'La tarea tiene desencadenadores distintos del plan; no se modifica.' }
    for ($i=0; $i -lt $lista.Count; $i++) {
        $d=$lista[$i]; $base='/t:Task/t:Triggers/t:CalendarTrigger['+($i+1)+']'
        Assert-Hijos $xmlActual $base @('Enabled','StartBoundary','Repetition','ScheduleByWeek') ('La tarea tiene opciones de disparo ajenas: '+$base)
        Comprobar-CampoTarea $xmlActual ($base+'/t:StartBoundary') ([string]$d.inicio) 'instante'
        Comprobar-CampoTarea $xmlActual ($base+'/t:Enabled') 'true' 'booleano' $true 'true'
        if ($null -ne $d.intervalo) {
            Assert-Hijos $xmlActual ($base+'/t:Repetition') @('Interval','Duration','StopAtDurationEnd') ('La tarea tiene una repeticion ajena: '+$base)
            Comprobar-CampoTarea $xmlActual ($base+'/t:Repetition/t:Interval') ([string]$d.intervalo) 'duracion'
            Comprobar-CampoTarea $xmlActual ($base+'/t:Repetition/t:Duration') ([string]$d.duracion) 'duracion'
            Comprobar-CampoTarea $xmlActual ($base+'/t:Repetition/t:StopAtDurationEnd') 'false' 'booleano' $true 'false'
        } elseif ($xmlActual.SelectNodes($base+'/t:Repetition',$ns).Count -ne 0) { throw ('La tarea repite un disparo que el plan no repite: '+$base) }
        Assert-Hijos $xmlActual ($base+'/t:ScheduleByWeek') @('DaysOfWeek','WeeksInterval') ('La tarea tiene una semana ajena: '+$base)
        Comprobar-CampoTarea $xmlActual ($base+'/t:ScheduleByWeek/t:WeeksInterval') '1' 'texto' $true '1'
        $dias=@($xmlActual.SelectNodes($base+'/t:ScheduleByWeek/t:DaysOfWeek/*',$ns))
        foreach($n in $dias) { if($n.NamespaceURI -cne $UriTarea -or $n.HasChildNodes){ throw ('Dia de disparo ajeno: '+$base) } }
        $exportados=@($dias | ForEach-Object { $_.LocalName } | Sort-Object)
        $esperados=@(@($d.dias) | ForEach-Object { [string]$_ } | Sort-Object)
        if (($exportados -join ',') -cne ($esperados -join ',')) { throw ('Dias de disparo distintos del plan: '+$base) }
    }
    return 2
}
function Assert-TareaPropia {
    $clave=[Guid]::NewGuid().ToString('N')
    $rutaExportada=Join-Path $Evidencia ('exportada-'+$clave+'.xml')
    $rutaDiagnostico=Join-Path $Evidencia ('validacion-'+$clave+'.json')
    $DiagnosticoActual=[ordered]@{version=2;tipo='validacion_tarea_exportada';estado='pendiente';error=$null;tarea=$NombreTarea;version_tarea=$null;exportacion_xml=$null;formato_exportacion='cadena original, UTF-16LE con BOM';bytes_exportacion=$null;sha256_exportacion=$null;campos=@()}
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
        $version=Assert-DocumentoPropio (Read-XmlSeguro $exportada)
        $DiagnosticoActual.estado='aprobada'; $DiagnosticoActual.version_tarea=$version
        return [pscustomobject]@{ Version=$version; Texto=$exportada; Ruta=$rutaExportada }
    } catch {
        $DiagnosticoActual.estado='rechazada'; $DiagnosticoActual.error=$_.Exception.Message
        throw
    } finally {
        [IO.File]::WriteAllText($rutaDiagnostico,(($DiagnosticoActual | ConvertTo-Json -Depth 12)+"`n"),$Utf8)
    }
}
function Get-CopiaDeshabilitada([string]$Texto,[int]$Version,[string]$Destino) {
    # Lo que se registra al revertir o restaurar: una copia del XML archivado con Settings/Enabled=false,
    # validada otra vez como propia de la misma version y guardada (UTF-16LE con BOM) antes de registrarla.
    # El archivo exportado original no se modifica (F92-REV-01: nunca se registra una tarea habilitada).
    $rutaDiagnostico=[IO.Path]::ChangeExtension($Destino,'.json')
    $DiagnosticoActual=[ordered]@{version=2;tipo='validacion_copia_deshabilitada';estado='pendiente';error=$null;xml=$Destino;version_tarea=$Version;campos=@()}
    try {
        if (Test-Path -LiteralPath $Destino) { throw 'La copia deshabilitada no debe sobrescribir evidencia previa.' }
        $documento=Read-XmlSeguro $Texto
        $gestor=New-Object Xml.XmlNamespaceManager($documento.NameTable); $gestor.AddNamespace('t',$UriTarea)
        $ajustes=$documento.SelectNodes('/t:Task/t:Settings',$gestor)
        if ($ajustes.Count -ne 1) { throw 'El XML no tiene una seccion Settings unica; no se registra.' }
        $habilitada=$ajustes[0].SelectNodes('t:Enabled',$gestor)
        if ($habilitada.Count -gt 1) { throw 'El XML repite Settings/Enabled; no se registra.' }
        if ($habilitada.Count -eq 1) { $habilitada[0].InnerText='false' }
        else { $nodo=$documento.CreateElement('Enabled',$UriTarea); $nodo.InnerText='false'; [void]$ajustes[0].AppendChild($nodo) }
        $copia=$documento.OuterXml
        if ((Assert-DocumentoPropio (Read-XmlSeguro $copia)) -ne $Version) { throw 'La copia deshabilitada no es de la version esperada; no se registra.' }
        if ((Get-ValorXml (Read-XmlSeguro $copia) '/t:Task/t:Settings/t:Enabled') -cne 'false') { throw 'La copia no quedo deshabilitada; no se registra.' }
        [IO.File]::WriteAllText($Destino,$copia,$UnicodeXml)
        $DiagnosticoActual.estado='aprobada'
        return $copia
    } catch {
        $DiagnosticoActual.estado='rechazada'; $DiagnosticoActual.error=$_.Exception.Message
        throw
    } finally {
        [IO.File]::WriteAllText($rutaDiagnostico,(($DiagnosticoActual | ConvertTo-Json -Depth 12)+"`n"),$Utf8)
    }
}
function Assert-XmlAnteriorPropio([string]$Ruta) {
    # Reversion: solo un XML exportado de la version 1 propia de este worktree, usuario e interprete.
    $Ruta=Get-Absoluta $Ruta 'XmlAnterior'
    if (-not (Test-Path -LiteralPath $Ruta -PathType Leaf)) { throw 'No existe el XML anterior indicado.' }
    $bytes=[IO.File]::ReadAllBytes($Ruta)
    if ($bytes.Length -lt 2 -or $bytes[0] -ne 0xFF -or $bytes[1] -ne 0xFE) { throw 'El XML anterior debe ser la exportacion archivada (UTF-16LE con BOM).' }
    $texto=[IO.File]::ReadAllText($Ruta,$UnicodeXml)
    $alg=[Security.Cryptography.SHA256]::Create()
    try { $sha=([BitConverter]::ToString($alg.ComputeHash($bytes))).Replace('-','').ToLowerInvariant() } finally { $alg.Dispose() }
    $rutaDiagnostico=Join-Path $Evidencia ('validacion-reversion-'+[Guid]::NewGuid().ToString('N')+'.json')
    $DiagnosticoActual=[ordered]@{version=2;tipo='validacion_xml_reversion';estado='pendiente';error=$null;xml=$Ruta;sha256=$sha;campos=@()}
    try {
        $version=Assert-DocumentoPropio (Read-XmlSeguro $texto)
        if ($version -ne 1) { throw 'El XML anterior no es de la version 1 de la tarea.' }
        $DiagnosticoActual.estado='aprobada'
        return [pscustomobject]@{ Ruta=$Ruta; Texto=$texto; Sha256=$sha }
    } catch {
        $DiagnosticoActual.estado='rechazada'; $DiagnosticoActual.error=$_.Exception.Message
        throw
    } finally {
        [IO.File]::WriteAllText($rutaDiagnostico,(($DiagnosticoActual | ConvertTo-Json -Depth 12)+"`n"),$Utf8)
    }
}
function Assert-SinDuplicado {
    # Otra tarea propia (marca exacta, nunca un prefijo del nombre) que actue sobre la MISMA configuracion
    # o el mismo backend no puede quedar activa a la vez: seria una segunda programacion del mismo almacen.
    # Las tareas propias de otros worktrees (p. ej. un ensayo aislado) se registran sin tocarlas.
    $accion='-m scripts.operacion_automatica --config ' + (Quote-Argument $Configuracion) + ' ciclo'
    $otras=@(Get-ScheduledTask -TaskPath '\' -ErrorAction Stop | Where-Object { $null -ne $_ -and [string]$_.TaskName -cne $NombreTarea -and ([string]$_.Source -ceq $Marca1 -or [string]$_.Source -ceq $Marca2) })
    $Resultado.otras_tareas_propias=@($otras | ForEach-Object { [string]$_.TaskName })
    $mismas=@($otras | Where-Object {
        $ejecuciones=@($_.Actions)
        @($ejecuciones | Where-Object { ([string]$_.Arguments).StartsWith($accion,[StringComparison]::OrdinalIgnoreCase) -or [string]::Equals([string]$_.WorkingDirectory,$Backend,[StringComparison]::OrdinalIgnoreCase) }).Count -gt 0
    })
    $activas=@($mismas | Where-Object { [bool]$_.Settings.Enabled -or [string]$_.State -eq 'Running' })
    if ($activas.Count -gt 0) { throw ('Otra tarea de la Fase 6 sobre la misma configuracion o backend esta activa (' + (@($activas | ForEach-Object { [string]$_.TaskName }) -join ', ') + '); no se crea ni activa un duplicado.') }
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
    $modos=@(@{nombre='Plan';valor=$Plan},@{nombre='Instalar';valor=$Instalar},@{nombre='Activar';valor=$Activar},@{nombre='Pausar';valor=$Pausar},@{nombre='Reanudar';valor=$Reanudar},@{nombre='Estado';valor=$Estado},@{nombre='Desinstalar';valor=$Desinstalar},@{nombre='Migrar';valor=$Migrar},@{nombre='Revertir';valor=$Revertir})
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
    if ($Accion -in @('Plan','Instalar','Migrar','Activar','Reanudar') -and [string]::IsNullOrWhiteSpace($PlanHorario)) { throw ('La accion ' + $Accion + ' requiere -PlanHorario (salida de `horario plan`).') }
    if ($Accion -eq 'Revertir' -and [string]::IsNullOrWhiteSpace($XmlAnterior)) { throw 'Revertir requiere -XmlAnterior (exportacion archivada de la version 1).' }
    if (-not [string]::IsNullOrWhiteSpace($PlanHorario)) {
        $PlanCargado=Read-PlanHorario $PlanHorario
        $Resultado.plan_horario=[ordered]@{archivo=$PlanCargado.Ruta;sha256_archivo=$PlanCargado.Sha256Archivo;huella=$PlanCargado.Huella;disparadores=@($PlanCargado.Disparadores).Count}
    }
    $Usuario=Get-UsuarioActual
    $NombreTarea='LP6-' + (Get-Sha ($Worktree.ToUpperInvariant()+"`n"+$Usuario.Id.ToUpperInvariant())).Substring(0,16)
    $ArgumentosV1='-m scripts.operacion_automatica --config ' + (Quote-Argument $Configuracion) + ' ciclo'
    $HuellaV1=Get-Sha ($Worktree.ToUpperInvariant()+"`n"+$PythonExe.ToUpperInvariant()+"`n"+$Configuracion.ToUpperInvariant()+"`n"+$Usuario.Id.ToUpperInvariant()+"`nPT5M`nPT2H")
    $DescripcionV1=$Marca1 + '; vinculacion=' + $HuellaV1
    $ArgumentosV2=$null; $DescripcionV2=$null; $Xml=$null
    if ($null -ne $PlanCargado) {
        $ArgumentosV2=$ArgumentosV1 + ' --programado --plan ' + $PlanCargado.Huella
        $HuellaV2=Get-Sha ($Worktree.ToUpperInvariant()+"`n"+$PythonExe.ToUpperInvariant()+"`n"+$Configuracion.ToUpperInvariant()+"`n"+$Usuario.Id.ToUpperInvariant()+"`n"+$PlanCargado.Huella+"`nPT2H")
        $DescripcionV2=$Marca2 + '; vinculacion=' + $HuellaV2
        $Resultado.huella_vinculacion=$HuellaV2
        $Xml=@"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Date>$([DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ'))</Date><Author>$(Escape-Xml $Usuario.Nombre)</Author><Description>$(Escape-Xml $DescripcionV2)</Description><Source>$(Escape-Xml $Marca2)</Source><URI>\$NombreTarea</URI></RegistrationInfo>
  <Triggers>$($PlanCargado.Xml)</Triggers>
  <Principals><Principal id="Usuario"><UserId>$(Escape-Xml $Usuario.Id)</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><AllowHardTerminate>true</AllowHardTerminate><StartWhenAvailable>false</StartWhenAvailable><RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable><AllowStartOnDemand>true</AllowStartOnDemand><Enabled>false</Enabled><Hidden>false</Hidden><WakeToRun>false</WakeToRun><ExecutionTimeLimit>PT2H</ExecutionTimeLimit><Priority>7</Priority></Settings>
  <Actions Context="Usuario"><Exec><Command>$(Escape-Xml $PythonExe)</Command><Arguments>$(Escape-Xml $ArgumentosV2)</Arguments><WorkingDirectory>$(Escape-Xml $Backend)</WorkingDirectory></Exec></Actions>
</Task>
"@
        [xml]$validacionXml=$Xml
        $RutaXml=Join-Path $Evidencia 'tarea.xml'; [IO.File]::WriteAllText($RutaXml,$Xml,$UnicodeXml)
        $Resultado.plan_xml=$RutaXml
    }
    $Resultado.tarea=$NombreTarea; $Resultado.usuario=$Usuario.Id; $Resultado.plataforma=$Usuario.Plataforma
    $Resultado.worktree=$Worktree; $Resultado.python=$PythonExe; $Resultado.configuracion=$Configuracion
    $Resultado.sesion='usuario actual con sesion abierta; no ejecuta con PC apagado o sesion cerrada; una oportunidad perdida no se recupera a otra hora'
    if ($Accion -eq 'Plan') {
        $Resultado.estado='plan_no_instalado'; $Codigo=0
        Registrar 'XML deshabilitado preparado; ningun cmdlet del Programador fue invocado.'
    } else {
        foreach ($cmd in @('Get-ScheduledTask','Export-ScheduledTask','Register-ScheduledTask','Enable-ScheduledTask','Disable-ScheduledTask','Unregister-ScheduledTask')) { [void](Get-Command $cmd -ErrorAction Stop) }
        $tarea=Get-Tarea
        $propia=$null
        if ($null -ne $tarea) { $propia=Assert-TareaPropia; $Resultado.version_tarea=$propia.Version }
        if ($Accion -eq 'Instalar') {
            if ($null -eq $tarea) {
                Assert-SinDuplicado
                [void](Register-ScheduledTask -TaskName $NombreTarea -TaskPath '\' -Xml $Xml -ErrorAction Stop)
                $Resultado.tarea_modificada=$true
                $tarea=Get-Tarea; $propia=Assert-TareaPropia
                if ($null -eq $tarea -or [bool]$tarea.Settings.Enabled -or $propia.Version -ne 2) { throw 'La tarea no quedo registrada deshabilitada; revisar antes de activar.' }
                $Resultado.estado='instalada_deshabilitada'
            } elseif ($propia.Version -eq 1) { $Resultado.estado='version_anterior_sin_reescribir_use_migrar' }
            else { $Resultado.estado='ya_instalada_sin_reescribir' }
        } elseif ($Accion -eq 'Migrar') {
            if ($null -eq $tarea) { throw 'No existe la tarea a migrar; para una instalacion nueva use -Instalar.' }
            if ($propia.Version -eq 2) { $Resultado.estado='ya_migrada_sin_reescribir' }
            else {
                $Resultado.xml_reversion=$propia.Ruta
                if ([string]$tarea.State -eq 'Running') { throw 'Hay un ciclo vivo: espere su cierre antes de migrar; la tarea anterior se conserva.' }
                Assert-SinDuplicado
                $Resultado.habilitada_antes=[bool]$tarea.Settings.Enabled
                [void](Disable-ScheduledTask -TaskName $NombreTarea -TaskPath '\' -ErrorAction Stop)
                $Resultado.tarea_modificada=$true
                $tarea=Get-Tarea; $anterior=Assert-TareaPropia
                if ($anterior.Version -ne 1) { throw 'La tarea cambio durante la migracion; queda deshabilitada y sin reemplazar.' }
                if ([string]$tarea.State -eq 'Running') { throw 'Un ciclo empezo durante la migracion: la tarea anterior queda deshabilitada y sin reemplazar.' }
                [void](Unregister-ScheduledTask -TaskName $NombreTarea -TaskPath '\' -Confirm:$false -ErrorAction Stop)
                try {
                    [void](Register-ScheduledTask -TaskName $NombreTarea -TaskPath '\' -Xml $Xml -ErrorAction Stop)
                } catch {
                    $fallo=$_.Exception.Message
                    [void](Register-ScheduledTask -TaskName $NombreTarea -TaskPath '\' -Xml $anterior.Texto -ErrorAction Stop)
                    [void](Disable-ScheduledTask -TaskName $NombreTarea -TaskPath '\' -ErrorAction Stop)
                    throw ('No se registro la version 2; se restauro la anterior deshabilitada: ' + $fallo)
                }
                $tarea=Get-Tarea; $propia=Assert-TareaPropia
                if ($null -eq $tarea -or [bool]$tarea.Settings.Enabled -or $propia.Version -ne 2) { throw 'La version 2 no quedo registrada deshabilitada; revisar antes de activar.' }
                $Resultado.estado='migrada_deshabilitada'
            }
        } elseif ($Accion -eq 'Revertir') {
            $anteriorV1=Assert-XmlAnteriorPropio $XmlAnterior
            $Resultado.xml_reversion=$anteriorV1.Ruta; $Resultado.xml_reversion_sha256=$anteriorV1.Sha256
            if ($null -ne $tarea -and $propia.Version -eq 1) { $Resultado.estado='ya_version_anterior_sin_reescribir' }
            else {
                # La version anterior vuelve deshabilitada: reactivarla es otra decision (con su codigo y
                # configuracion). Se registra una copia validada con Enabled=false, nunca la exportacion tal cual.
                $rutaCopia=Join-Path $Evidencia 'reversion-v1-deshabilitada.xml'
                $copiaV1=Get-CopiaDeshabilitada $anteriorV1.Texto 1 $rutaCopia
                $Resultado.xml_registrado=$rutaCopia
                $copiaV2=$null; $rutaRestauracion=$null
                if ($null -ne $tarea) {
                    if ([string]$tarea.State -eq 'Running') { throw 'Hay un ciclo vivo: espere su cierre antes de revertir.' }
                    [void](Disable-ScheduledTask -TaskName $NombreTarea -TaskPath '\' -ErrorAction Stop)
                    $Resultado.tarea_modificada=$true
                    # Tras pausar y antes de retirar: la misma tarea propia, sin un ciclo que empezara entretanto.
                    $tarea=Get-Tarea
                    if ($null -eq $tarea) { throw 'La tarea desaparecio durante la reversion; no se registra otra en su lugar.' }
                    $vigente=Assert-TareaPropia
                    if ($vigente.Version -ne 2) { throw 'La tarea cambio durante la reversion; queda deshabilitada y sin retirar.' }
                    if ([string]$tarea.State -eq 'Running') { throw 'Un ciclo empezo durante la reversion: la version 2 queda deshabilitada y sin retirar.' }
                    $rutaRestauracion=Join-Path $Evidencia 'restauracion-v2-deshabilitada.xml'
                    $copiaV2=Get-CopiaDeshabilitada $vigente.Texto 2 $rutaRestauracion
                    $Resultado.xml_restauracion=$rutaRestauracion
                    [void](Unregister-ScheduledTask -TaskName $NombreTarea -TaskPath '\' -Confirm:$false -ErrorAction Stop)
                }
                try {
                    [void](Register-ScheduledTask -TaskName $NombreTarea -TaskPath '\' -Xml $copiaV1 -ErrorAction Stop)
                } catch {
                    $fallo=$_.Exception.Message
                    if ($null -eq $copiaV2) { throw ('No se registro la version anterior: ' + $fallo) }
                    try { [void](Register-ScheduledTask -TaskName $NombreTarea -TaskPath '\' -Xml $copiaV2 -ErrorAction Stop) }
                    catch { throw ('No se registro la version anterior ni se restauro la version 2 (' + $fallo + '; ' + $_.Exception.Message + '). No queda tarea registrada; XML deshabilitados para restaurarla: ' + $rutaRestauracion + ' y ' + $rutaCopia) }
                    $tarea=Get-Tarea; $propia=Assert-TareaPropia
                    throw ('No se registro la version anterior; se restauro la version 2 deshabilitada: ' + $fallo)
                }
                $Resultado.tarea_modificada=$true
                $tarea=Get-Tarea; $propia=Assert-TareaPropia
                if ($null -eq $tarea -or [bool]$tarea.Settings.Enabled -or $propia.Version -ne 1) { throw 'La version anterior no quedo registrada deshabilitada.' }
                $Resultado.estado='revertida_deshabilitada'
            }
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
            else {
                if ($propia.Version -ne 2) { throw 'La tarea es de la version anterior (PT5M e inicio de sesion): migrela con -Migrar antes de activarla.' }
                Assert-SinDuplicado
                [void](Enable-ScheduledTask -TaskName $NombreTarea -TaskPath '\' -ErrorAction Stop); $Resultado.estado='tarea_habilitada'
            }
            $Resultado.tarea_modificada=$true; $tarea=Get-Tarea; $propia=Assert-TareaPropia
        }
        if ($null -ne $tarea) {
            $Resultado.habilitada=[bool]$tarea.Settings.Enabled; $Resultado.estado_programador=[string]$tarea.State
            # Version de la tarea tal como queda tras la accion (validada de nuevo), no la de antes.
            if ($null -ne $propia) { $Resultado.version_tarea=$propia.Version }
        }
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
