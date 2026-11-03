# Fase 10 · E10.1 — Protocolo de validación nativa (Windows 11, PowerShell 5.1, Brave) · v2

Responsables: Daniel y Codex. Estado (2 de noviembre de 2026): **protocolo histórico de referencia**. Lo que
efectivamente se ejecutó en Windows —validación automática consolidada y recorrido guiado Brave r3, auditados
por Codex dentro de su alcance— se resume en [Ejecución efectiva](#ejecución-efectiva-r3-2-de-noviembre-de-2026)
y se detalla en la [validación del operador y auditoría](fase10_e101_validacion_operador_2026-11-02.md). Publicación manual, integración y CI
pendientes. **No vuelva a copiar estos bloques sobre el almacén de ensayo ya existente.** La v2 corrige
E101-VAL-01 de la auditoría de v1: ninguna contraseña se escribe en el texto de un comando, en argumentos, en el
historial ni en evidencias, y cada terminal nueva se inicializa sola.

## Reglas del ensayo

- **Solo cuentas y contraseñas SINTÉTICAS**, inventadas para este ensayo y distintas de cualquier contraseña
  real. Se teclean únicamente en solicitudes ocultas (`getpass` de la CLI y del ayudante de búsqueda) o en el
  formulario de Brave. Nunca se pegan en PowerShell.
- **Nada operativo:** backend de ensayo (`tests/ensayo_consola_e101.py`, servicios sustituidos, cero ciclos) en
  el puerto 8765, almacén en una carpeta temporal nueva. No se usa `backend\privado\`, PostgreSQL operativo,
  Fase 6, el Programador ni la tarea `LP6-01023009031fcabd`, y no se arranca la consola operativa.
- Las comprobaciones de secretos informan solo booleanos y recuentos.
- Requisitos: Windows PowerShell 5.1 **x64**, Python 3.14 del entorno virtual del proyecto, Brave actual. Las
  rutas pueden tener espacios: todas van entre comillas o con `-LiteralPath`.
- Cada comando nativo se ejecuta con `Invoke-E101`, que comprueba `$LASTEXITCODE` frente al código esperado y
  detiene el bloque si no coincide.

## Prólogo (copiar al INICIO de cada terminal nueva, incluida la primera tras el bloque A)

```powershell
# --- PRÓLOGO E10.1 v2 ---
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -ne 5 -or -not [Environment]::Is64BitProcess) { throw 'Se requiere Windows PowerShell 5.1 de 64 bits.' }
$ConfigE101 = Join-Path $env:TEMP 'e101-ensayo-v2.json'
if (-not (Test-Path -LiteralPath $ConfigE101)) { throw "Falta ${ConfigE101}: ejecute primero el bloque A." }
$Cfg = Get-Content -Raw -LiteralPath $ConfigE101 | ConvertFrom-Json
$Backend = [string]$Cfg.Backend; $Python = [string]$Cfg.Python; $Prueba = [string]$Cfg.Prueba; $Almacen = [string]$Cfg.Almacen
foreach ($Ruta in @($Backend, $Python, $Prueba)) { if (-not (Test-Path -LiteralPath $Ruta)) { throw "No existe: ${Ruta}" } }
Set-Location -LiteralPath $Backend
function Invoke-E101 {
    param([Parameter(Mandatory = $true)][string[]]$Argumentos, [int[]]$Esperados = @(0))
    & $Python @Argumentos | Out-Host
    $Codigo = $LASTEXITCODE
    if (@($Esperados) -notcontains $Codigo) { throw "Salida ${Codigo}; se esperaba $(@($Esperados) -join ' o ')." }
    Write-Host "[OK] código ${Codigo}"
}
function Get-Sha256Hex([string]$Ruta) {
    $Sha = [System.Security.Cryptography.SHA256]::Create(); $Fs = [System.IO.File]::OpenRead($Ruta)
    try { ([System.BitConverter]::ToString($Sha.ComputeHash($Fs))).Replace('-', '').ToLowerInvariant() } finally { $Fs.Dispose(); $Sha.Dispose() }
}
# --- fin del prólogo ---
```

## A. Preparación (terminal 1; una sola vez)

Ajuste solo `$BackendA`. El archivo de configuración no contiene secretos.

```powershell
$ErrorActionPreference = 'Stop'
$BackendA = 'C:\ruta\a\loteria-predictor\backend'   # ajustar
$PythonA  = Join-Path $BackendA '.venv\Scripts\python.exe'
$PruebaA  = Join-Path $env:TEMP 'e101 ensayo v2 con espacios'
$ConfigA  = Join-Path $env:TEMP 'e101-ensayo-v2.json'
if (Test-Path -LiteralPath $PruebaA) { throw "Ya existe ${PruebaA}; elija otra carpeta o conserve la anterior para revisión." }
if (Test-Path -LiteralPath $ConfigA) { throw "Ya existe ${ConfigA}; es de un ensayo anterior." }
if (-not (Test-Path -LiteralPath $PythonA)) { throw "No existe ${PythonA}" }
New-Item -ItemType Directory -Path $PruebaA | Out-Null
[ordered]@{ Backend = $BackendA; Python = $PythonA; Prueba = $PruebaA; Almacen = (Join-Path $PruebaA 'seguridad') } |
    ConvertTo-Json | Set-Content -LiteralPath $ConfigA -Encoding UTF8
```

Después, en la misma terminal, pegue el **prólogo**.

## B. Pruebas automáticas (terminal 1)

```powershell
Invoke-E101 -Argumentos @('--version')
Invoke-E101 -Argumentos @('-m', 'pytest', '-p', 'no:cacheprovider', '-rsw', 'tests/unit/seguridad_consola', '--junitxml', (Join-Path $Prueba 'e101-v2-windows.xml'))
[xml]$Junit = Get-Content -Raw -LiteralPath (Join-Path $Prueba 'e101-v2-windows.xml')
$Nativos = @($Junit.SelectNodes('//testcase') | Where-Object { $_.classname -like '*test_permisos_windows_nativo*' })
$Omitidos = @($Nativos | Where-Object { $_.skipped })
"nativos: $($Nativos.Count); omitidos: $($Omitidos.Count)"
```

Esperado: código 0; 3 pruebas nativas de ACL; ninguna omitida salvo, como mucho,
`test_nativo_directorio_preexistente_no_se_modifica` si `%TEMP%` ya es exclusivo del usuario (anótelo).

## C. Aprovisionamiento y permisos (terminal 1)

Cada `crear` pide la contraseña sintética dos veces, **sin eco**.

```powershell
Invoke-E101 -Argumentos @('-m', 'scripts.consola_cuentas', '--directorio', $Almacen, 'crear', '--usuario', 'daniel-prueba', '--rol', 'administrador')
Invoke-E101 -Argumentos @('-m', 'scripts.consola_cuentas', '--directorio', $Almacen, 'crear', '--usuario', 'operadora', '--rol', 'operador')
Invoke-E101 -Argumentos @('-m', 'scripts.consola_cuentas', '--directorio', $Almacen, 'crear', '--usuario', 'lectora', '--rol', 'lector')
Invoke-E101 -Argumentos @('-m', 'scripts.consola_cuentas', '--directorio', $Almacen, 'comprobar')
Invoke-E101 -Argumentos @('-m', 'scripts.consola_cuentas', '--directorio', $Almacen, 'listar')
$Archivo = Join-Path $Almacen 'seguridad.sqlite3'
icacls "$Archivo"; icacls "$Almacen"
```

Esperado: `{"estado": "disponible"}`; `listar` sin hashes; propietario y única concesión del usuario actual
(sin `BUILTIN\Administradores`, `Usuarios`, `Todos`, `Usuarios autentificados`).

Contraste de permisos sobre el **archivo de ensayo** (no sobre carpetas ajenas):

```powershell
& icacls "$Archivo" /grant '*S-1-1-0:(R)' | Out-Host; if ($LASTEXITCODE -ne 0) { throw 'icacls /grant falló' }
Invoke-E101 -Argumentos @('-m', 'scripts.consola_cuentas', '--directorio', $Almacen, 'comprobar') -Esperados @(1)
& icacls "$Archivo" /remove:g '*S-1-1-0' | Out-Host; if ($LASTEXITCODE -ne 0) { throw 'icacls /remove falló' }
Invoke-E101 -Argumentos @('-m', 'scripts.consola_cuentas', '--directorio', $Almacen, 'comprobar')
```

Esperado: primero `{"estado": "no_disponible", "motivo": "permisos"}` (código 1) y, tras retirar la ACE,
`disponible` (código 0).

Directorio preexistente (debe rechazarse **sin modificarlo**):

```powershell
$Pre = Join-Path $Prueba 'directorio preexistente'
New-Item -ItemType Directory -Path $Pre | Out-Null
$SddlAntes = (Get-Acl -LiteralPath $Pre).Sddl
Invoke-E101 -Argumentos @('-m', 'scripts.consola_cuentas', '--directorio', $Pre, 'crear', '--usuario', 'otra', '--rol', 'lector') -Esperados @(1)
"ACL sin cambios: $((Get-Acl -LiteralPath $Pre).Sddl -eq $SddlAntes); archivos: $(@(Get-ChildItem -LiteralPath $Pre -Force).Count)"
```

Esperado: «no se modifica» en el mensaje; `ACL sin cambios: True; archivos: 0`.

Búsqueda de la contraseña sintética (entrada oculta; solo booleanos):

```powershell
$Historial = $null
if (Get-Command Get-PSReadLineOption -ErrorAction SilentlyContinue) { $Historial = (Get-PSReadLineOption).HistorySavePath }
$Busqueda = @('-m', 'tests.ensayo_e101_buscar_secreto', '--archivo', $Archivo)
if ($Historial -and (Test-Path -LiteralPath $Historial)) { $Busqueda += @('--archivo', $Historial) }
Invoke-E101 -Argumentos $Busqueda
```

Teclee en la solicitud oculta una de las contraseñas sintéticas usadas. Esperado: `"apariciones": 0` y código
0. Repita para las otras dos cuentas si lo desea.

## D. Backend de ensayo (terminal 2, nueva)

Pegue el **prólogo** y después:

```powershell
Invoke-E101 -Argumentos @('-m', 'tests.ensayo_consola_e101', '--directorio', $Almacen, '--puerto', '8765') -Esperados @(0, 1, 3221225786)
```

Queda en primer plano hasta Ctrl+C (los códigos admitidos cubren esa interrupción). Esperado:
`consola de ensayo en http://127.0.0.1:8765/`.

## E. Comprobaciones de red y entradas malformadas (terminal 1)

```powershell
$Escucha = @(Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue)
"escuchas: $($Escucha.Count); direcciones: $(@($Escucha | ForEach-Object { $_.LocalAddress }) -join ', ')"
function Send-Crudo([byte[]]$Solicitud) {
    $Tcp = New-Object System.Net.Sockets.TcpClient('127.0.0.1', 8765)
    try {
        $Flujo = $Tcp.GetStream(); $Flujo.Write($Solicitud, 0, $Solicitud.Length); $Flujo.Flush()
        $Lector = New-Object System.IO.StreamReader($Flujo, [System.Text.Encoding]::ASCII)
        $Lector.ReadLine()
    } finally { $Tcp.Close() }
}
$Ascii = [System.Text.Encoding]::ASCII
"Host '[': " + (Send-Crudo $Ascii.GetBytes("GET /acceso HTTP/1.1`r`nHost: [`r`nConnection: close`r`n`r`n"))
"Host local: " + (Send-Crudo $Ascii.GetBytes("GET /acceso HTTP/1.1`r`nHost: 127.0.0.1:8765`r`nConnection: close`r`n`r`n"))
"X-Forwarded-For: " + (Send-Crudo $Ascii.GetBytes("GET /acceso HTTP/1.1`r`nHost: 127.0.0.1:8765`r`nX-Forwarded-For: 10.8.0.2`r`nConnection: close`r`n`r`n"))
$Cabeza = $Ascii.GetBytes("POST /acceso HTTP/1.1`r`nHost: 127.0.0.1:8765`r`nContent-Type: application/x-www-form-urlencoded`r`nContent-Length: 0`r`nConnection: close`r`nCookie: lp_consola_presesion=")
$Cola = $Ascii.GetBytes("`r`n`r`n")
"Cookie no ASCII: " + (Send-Crudo ([byte[]]($Cabeza + [byte[]](0xFF) + $Cola)))
```

Esperado: una única escucha en `127.0.0.1`; `Host '['` → `403`; `Host local` → `200`; `X-Forwarded-For` →
`403`; `Cookie no ASCII` → `403`. Si el propio servidor HTTP rechaza antes una solicitud malformada, `400` es
igualmente correcto. Nunca `500`.

## F. Recorrido en Brave, un perfil temporal por rol (terminal 1)

```powershell
$Brave = @("$env:ProgramFiles\BraveSoftware\Brave-Browser\Application\brave.exe",
           "${env:ProgramFiles(x86)}\BraveSoftware\Brave-Browser\Application\brave.exe",
           "$env:LOCALAPPDATA\BraveSoftware\Brave-Browser\Application\brave.exe") |
         Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $Brave) { throw 'No se encontró brave.exe.' }
foreach ($Rol in @('lectora', 'operadora', 'daniel-prueba')) {
    $Perfil = Join-Path $Prueba "brave-$Rol"
    Start-Process -FilePath $Brave -ArgumentList @("--user-data-dir=`"$Perfil`"", '--no-first-run', '--no-default-browser-check', 'http://127.0.0.1:8765/acceso')
}
```

Cada ventana usa un perfil (`--user-data-dir`) propio: cookies y sesiones no se comparten entre roles (las
ventanas privadas de un mismo perfil sí las comparten, por eso no se usan). Use cada ventana solo con su
cuenta y anote estado y captura de cada paso:

| # | Ventana | Acción | Esperado |
|---|---|---|---|
| 1 | lectora | Abrir `/` sin sesión | Redirige a `/acceso?siguiente=%2F` |
| 2 | lectora | Contraseña errónea para `lectora` y para el usuario inexistente `fantasma` | Mismo mensaje genérico |
| 3 | lectora | Cinco fallos seguidos con `fantasma` | Esperas crecientes y bloqueo temporal (429) |
| 4 | lectora | Doble clic rápido en «Entrar» con la contraseña correcta | Una sola sesión; el segundo envío, si llega, pide repetir (formulario caducado o espera) |
| 5 | lectora | `/automatizacion` | Sin botones de acciones; nota de acciones restringidas |
| 6 | operadora | Acceso; `/automatizacion` → «Comprobar» | Solo «Comprobar»; el ensayo imprime `lanzamiento SUSTITUIDO` |
| 7 | operadora | DevTools: `fetch('/automatizacion/pausar',{method:'POST',headers:{'X-CSRF-Token':document.querySelector('meta[name=csrf-token]').content},body:new URLSearchParams({juego:'todos'})}).then(r=>r.status)` | `403`; el ensayo no registra «pausar» |
| 8 | operadora | `/colores`: añadir un color | Rechazado (403) |
| 9 | daniel-prueba | `/colores`: añadir y borrar un color | Funciona por HTMX (memoria del ensayo) |
| 10 | daniel-prueba | `/automatizacion`: pausar, reanudar, recuperar | El ensayo imprime cada `acción … SUSTITUIDA` |
| 11 | cualquiera | DevTools → Application → Cookies | `lp_consola_sesion`: HttpOnly, SameSite Strict, Path `/`; sin Secure en http |
| 12 | daniel-prueba | DevTools: `fetch('/colores',{method:'POST',body:new URLSearchParams({codigo:'QQ',nombre:'x'})}).then(r=>r.status)` | `403` (sin CSRF) |
| 13 | daniel-prueba | «Salir», Atrás y recargar | `/acceso` |
| 14 | daniel-prueba | Entrar; en terminal 1: `Invoke-E101 -Argumentos @('-m','scripts.consola_cuentas','--directorio',$Almacen,'revocar-sesiones')`; recargar | `/acceso` |
| 15 | operadora | Con sesión: `Invoke-E101 -Argumentos @('-m','scripts.consola_cuentas','--directorio',$Almacen,'cambiar-rol','--usuario','operadora','--rol','lector')`; recargar | Pide acceso; después, sin «Comprobar» |
| 16 | — | Ctrl+C en terminal 2; nueva terminal 2 con prólogo y bloque D; entrar | Cuentas conservadas; sesiones revocadas siguen revocadas |
| 17 | cualquiera | `/docs`, `/openapi.json` | 404 |
| 18 | otro equipo / VPN | `http://<IP-del-PC>:8765/` | No conecta (solo loopback) |

## G. Auditoría y cierre (terminal 1)

```powershell
$Auditoria = Join-Path $Prueba 'auditoria.json'
& $Python -m scripts.consola_cuentas --directorio "$Almacen" auditoria --limite 200 | Out-File -LiteralPath $Auditoria -Encoding utf8
if ($LASTEXITCODE -ne 0) { throw "auditoria: código ${LASTEXITCODE}" }
"contiene el nombre de la cookie: " + ([System.IO.File]::ReadAllText($Auditoria)).Contains('lp_consola_sesion')
Invoke-E101 -Argumentos @('-m', 'tests.ensayo_e101_buscar_secreto', '--archivo', $Auditoria, '--archivo', $Archivo)
"JUnit sha256: " + (Get-Sha256Hex (Join-Path $Prueba 'e101-v2-windows.xml'))
```

Esperado: `contiene el nombre de la cookie: False`; búsqueda oculta con `"apariciones": 0`; eventos de acceso,
fallos, bloqueo, permisos, escrituras y revocaciones.

Cierre: Ctrl+C en la terminal 2 y cierre las ventanas de Brave. `$Prueba` y `e101-ensayo-v2.json` contienen solo
datos sintéticos; consérvelos para el informe y elimínelos cuando Daniel lo decida (son los únicos restos).
Registre: versión de Windows, PowerShell, Python y Brave; resultado de cada bloque y paso; JUnit y su SHA-256.

## Ejecución efectiva (r3, 2 de noviembre de 2026)

Los bloques A–G y la tabla de 18 pasos anteriores son el **protocolo histórico de referencia**: no se ejecutaron
completos como recorrido manual y sus pasos no se marcan como realizados. Lo ejecutado, con un supervisor nativo
y auditado por Codex, fue:

- **Automático:** consolidación nativa de 264 casos únicos (261 aprobados, 3 omitidos POSIX, 0 fallos) y la sonda
  original 5/5, sin batería completa nueva.
- **Brave r3:** 14 pasos guiados con perfiles separados por rol sobre el servidor de ensayo de la v3 (consola real,
  servicios ficticios). El servidor usó un **puerto dinámico de loopback**, no el 8765 fijo de los ejemplos D–F.
- **Salida:** la comprobación ejecutada fue Salir y después una **visita explícita a una URL protegida**, que
  redirigió al acceso (con sesiones 1→0 en el servidor); el botón Atrás no bastaba como prueba.
- Se reutilizaron el almacén y las tres cuentas sintéticas ya creadas en intentos anteriores, sin reaplicar
  permisos ni teclear contraseñas en PowerShell. Estado final conservado: administrador y lectora sin sesiones;
  operadora, ahora lector, con una sesión persistente de prueba. No se recrean ni se restablecen.
- r2 quedó incompleto (faltó la visita protegida tras Salir) y no se aprueba retrospectivamente.

Resultados, huellas y salvedades: [validación del operador y auditoría](fase10_e101_validacion_operador_2026-11-02.md).
