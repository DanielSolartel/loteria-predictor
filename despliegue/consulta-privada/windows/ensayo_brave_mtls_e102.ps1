<#
.SYNOPSIS
  Fase 10 (E10.2, v4): ensayo FOCAL en Windows de la seleccion y verificacion del certificado de cliente en Brave.

.DESCRIPTION
  ALCANCE: acredita solo que Brave, con el almacen de certificados del usuario de Windows, presenta un certificado
  de cliente y que un servidor local que lo exige lo verifica. NO acredita la topologia de la consulta privada
  (proxy, pasarela, API, base) ni produccion. No usa datos, la base, la tarea LP6-01023009031fcabd, cuentas o
  perfiles del ensayo E10.1 ni ninguna configuracion de Fase 6.

  QUE HACE (antes de instalar nada pide confirmacion, salvo -Confirmar):
  1. Carpeta temporal privada (solo el usuario actual) y, con validez de 2 horas: una CA de prueba, un
     certificado de cliente CN=invitado-brave (clave NO exportable) y uno de servidor para localhost, en
     Cert:\CurrentUser\My, con claves CNG (Microsoft Software Key Storage Provider) y una marca propia.
  2. AGREGA TEMPORALMENTE la CA de prueba al almacen de confianza del usuario (Cert:\CurrentUser\Root).
     Windows pide confirmacion: pulse Si. Se retira al final (Windows vuelve a pedir confirmacion).
  3. Exporta el certificado del servidor a un PFX temporal con una contrasena ALEATORIA que solo viaja por la
     entrada estandar del servidor local (Daniel no crea ninguna contrasena; no se guarda ni se muestra).
  4. Arranca `servidor_mtls_e102.py` en 127.0.0.1 y abre Brave con un PERFIL NUEVO en la carpeta temporal.
     En Brave: elija el certificado `invitado-brave`. No hace falta volver a PowerShell: el guion detecta el
     resultado solo (el servidor lo guarda antes de responder).
  5. Finalizacion (siempre, aunque un paso falle): cierre cooperativo del servidor (el fin forzado es el
     ultimo recurso); cierre SOLO de los procesos de Brave de su perfil temporal; retirada de la CA de la raiz
     por huella; eliminacion de los tres certificados JUNTO CON SUS CLAVES PRIVADAS (-DeleteKey y, si quedara,
     el contenedor CNG exacto registrado); borrado de la carpeta. Cada paso esta aislado y sus errores se
     acumulan; despues se verifica por identificador exacto que no queda nada. Todo ello usa SOLO los
     identificadores que esta misma ejecucion creo y guarda en memoria. El resumen JSON se escribe siempre
     (si no se puede en -Salida, en TEMP y, si tampoco, en la consola) y lleva el mismo codigo que devuelve
     el proceso.

  REGISTRO DIAGNOSTICO (v4): mientras existan recursos propios, `<Salida>.diagnostico.json` guarda sus
  identificadores (huellas, nombres de contenedor de clave, carpeta, estado del servidor) y, al final, los
  residuos. Es SOLO para revisar a mano: no es una autorizacion ni instrucciones de borrado, el guion nunca lo
  lee y no existe recuperacion automatica. Si la limpieza es completa, se borra; si queda algo, se conserva,
  el guion termina con el codigo 4 y los identificadores se revisan antes de cualquier accion manual concreta.

  PLAZOS: arranque del servidor (-PlazoArranque), espera humana (-PlazoHumano) y salida (-PlazoSalida).

  CODIGOS DE SALIDA: 0 verificado y limpieza completa y verificada; 1 fallo; 2 sin interaccion/plazo vencido o
  certificado ausente/incorrecto; 3 el servidor no arranco; 4 limpieza incompleta o no verificable (ver el
  resumen y el registro diagnostico); 5 cancelado antes de instalar nada; 6 sin poder guardar el resumen en
  ningun archivo (solo consola). Una limpieza incompleta nunca da 0.

.PARAMETER Python
  Python con `cryptography` (por ejemplo el del entorno del backend). Por defecto, `python`.
.PARAMETER Brave
  Ruta de brave.exe. Por defecto se busca en las rutas habituales.
.PARAMETER Salida
  Archivo JSON del resumen (sin secretos). Por defecto, en el Escritorio.
#>
[CmdletBinding()]
param(
    [string]$Python = "python",
    [string]$Brave = "",
    [int]$PlazoArranque = 30,
    [int]$PlazoHumano = 180,
    [int]$PlazoSalida = 15,
    [switch]$Confirmar,
    [string]$Salida = (Join-Path ([Environment]::GetFolderPath("Desktop")) ("ensayo-brave-mtls-e102-{0:yyyyMMddTHHmmss}.json" -f (Get-Date)))
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "ensayo_brave_mtls_e102_nucleo.ps1")
$plataforma = Nueva-PlataformaWindowsE102
$opciones = @{
    Python = $Python; Brave = $Brave; PlazoArranque = $PlazoArranque; PlazoHumano = $PlazoHumano; PlazoSalida = $PlazoSalida
    Temp = $env:TEMP; Servidor = (Join-Path $PSScriptRoot "servidor_mtls_e102.py"); Salida = $Salida
    Diagnostico = ($Salida + ".diagnostico.json")
}

Write-Host "Ensayo focal E10.2: Brave y certificado de cliente."
Write-Host "Agregara TEMPORALMENTE una CA de prueba (validez 2 h) al almacen de confianza de su usuario y la retirara"
Write-Host "al terminar; Windows pedira confirmacion las dos veces. Brave se abre con un perfil nuevo y temporal."
Write-Host "Al final se eliminan los certificados de prueba y sus claves privadas, y se verifica que no queda nada."
if (-not $Confirmar) {
    $respuesta = Read-Host "Escriba SI para continuar (cualquier otra respuesta cancela sin instalar nada)"
    if ($respuesta -ne "SI") { Write-Host "Cancelado: no se instalo nada."; exit 5 }
}

exit ([int](Ultimo-ValorE102 (Invoke-EnsayoCompletoE102 -Plataforma $plataforma -Opciones $opciones) "int"))
