# Fase 6: tarea de Windows independiente de la interfaz

`scripts/windows/fase6_tarea.ps1` prepara y controla una tarea del **usuario actual**, con Windows PowerShell 5.1 en consola normal. No inicia Uvicorn ni utiliza HTTP para ejecutar la operación. La acción usa el intérprete absoluto y llama directamente al ejecutor de Fase 6. En la **versión 2** (horario por juego, entrega 9.2) la acción es:

```text
python.exe -m scripts.operacion_automatica --config "ruta absoluta de configuracion.json" ciclo --programado --plan <huella del plan>
```

## Versión 2: horario por juego (entrega 9.2; validada en Windows y aplicada después a la tarea real)

- **Estado.** Validada en Windows 11 con Windows PowerShell 5.1.26100.9711 y aprobada por la auditoría independiente el 26 de octubre de 2026:
  - pruebas dirigidas: 121 casos únicos aprobados, por consolidación de dos corridas;
  - ensayo nativo B con el Programador real y un testigo sintético ([validación del operador](fase9_2_validacion_operador_2026-10-26.md)).

  Durante esa validación, la tarea real `LP6-01023009031fcabd` seguía en la versión 1, habilitada, y su migración era un bloque posterior y separado. *Actualización:* la entrega se integró en el PR #101; daniel migró y activó en Windows `LP6-01023009031fcabd` con el horario por juego. Como antecedente, el auditor confirmó que la captura del 27 de octubre de 2026 a las 00:11, hora de Bogotá, registraba nueve ejecuciones programadas y quince consultas en sus franjas: siete de MiLoto, tres de Baloto, tres de Revancha y dos de ColorLoto, sin duplicados ni fallos de sincronización reportados. Todas fueron sin resultados nuevos; esa captura todavía no acreditaba la incorporación de una novedad real ni la recuperación matinal con pendientes. Las versiones v3 y v4 de la entrega no son versiones de la tarea: el controlador sigue registrando la versión 2.

**Observación posterior (27 de octubre de 2026, 10:21, America/Bogota).** La operación real de Daniel, auditada sobre sus registros, ya acredita una novedad automática en cada juego con el horario nuevo: BALOTO y BALOTO_REVANCHA 2726 → 2727 (646 → 647 sorteos cada uno), MILOTO 629 → 630 (98 → 99) y COLORLOTO 229 → 230 (229 → 230). Cada incorporación registra sincronización `completado`, `nuevos: 1` y la siguiente predicción con explicación `guardada`: objetivos 2728 de Baloto/Revancha (28-10-2026), 631 de MiLoto (27-10-2026) y 231 de ColorLoto (29-10-2026).

Los 20 ciclos conservados contienen 33 consultas programadas (8 MiLoto, 9 Baloto, 9 Revancha y 7 ColorLoto), sin parejas juego/oportunidad repetidas ni fallos de sincronización reportados. Los 29 intentos previos sin novedad no emitieron una predicción nueva; configuración y selecciones de modelos se conservan respecto de la observación anterior. Son hechos de operación real, separados de las pruebas sintéticas de 9.3; este cierre no ejecuta ciclos ni SQL operativo.

El Programador informó último inicio **09:24:45**: no acredita un disparo exactamente a las 09:00. Los cuatro juegos ya habían terminado de actualizarse durante la madrugada; la **recuperación matinal con resultados pendientes sigue sin observarse**. Se conserva la tarea **versión 2** y su plan, sin cambios; las versiones v3/v4 de las entregas no son versiones de la tarea. La limpieza histórica sigue pendiente y no queda resuelta por esta observación. Véase [observación real del 27 de octubre](fase9_3_validacion_operador_2026-10-27.md#actualizacion-real-de-fase-6-del-27-de-octubre).

- **Disparadores.** Solo los `CalendarTrigger` semanales del plan que imprime `horario plan --salida` (franjas cada 15 minutos y recuperación a las 09:00). No hay `LogonTrigger` ni repetición sin fin, y `StartWhenAvailable=false`.
- **Exportación nativa (corrección v3 de F92-NAT-01).** El Programador puede omitir `StartWhenAvailable` al exportar su predeterminado `false`.
  - El controlador toma la omisión como el predeterminado **documentado** del esquema, nunca como el valor esperado. Así una versión 1, que exige `true`, sigue rechazada si falta el campo.
  - El diagnóstico registra `origen = predeterminado_documentado`.
  - La exportación original se archiva sin normalizar.
  - El ensayo lee el campo de forma estricta, sin acceder a una propiedad XML ausente.
- **Parámetros nuevos.**
  - `-PlanHorario <archivo>`: obligatorio para `-Plan`, `-Instalar`, `-Migrar`, `-Activar` y `-Reanudar`, y para cualquier acción sobre una tarea de la versión 2.
  - `-Migrar`: sustituye una versión 1 propia, en el mismo nombre y sin duplicado.
  - `-Revertir -XmlAnterior <exportación archivada>`: vuelve a la versión 1 deshabilitada. Registra una copia validada con `Enabled=false`, nunca la exportación tal cual, y conserva el original. Tras pausar, vuelve a comprobar la propiedad y que no haya un ciclo vivo. Si falla el registro, restaura la versión 2 deshabilitada ([detalle](fase6_migracion_lp6.md#2-reversión)).
- **Lectura del plan (corrección v2 de F92-PS-02).** PowerShell 7 convierte las cadenas ISO completas en `DateTime` al leer JSON y pierde su texto y su desfase; `-DateKind String` solo existe desde la 7.5. El controlador protege esas cadenas antes de convertir y las restaura después, igual en Windows PowerShell 5.1 y en PowerShell 7.x. Siguen las comprobaciones de patrón, texto canónico, huella y XML, y además cada inicio debe llevar el desfase `-05:00` del plan.
- **Espacio de nombres (corrección v2 de F92-PS-01).** La URI de Task Scheduler vive en `$UriTarea`. Antes se llamaba `$NS`, y PowerShell la confundía con el gestor local `$ns`, porque no distingue mayúsculas. Una guarda estática de las pruebas impide que una función tape así un valor del script que también lee.
- **Resultado.** `version_tarea` informa la versión con la que queda la tarea después de la acción (corrección v2 de F92-PS-03).
- **Versión 1.** La versión anterior (PT5M e inicio de sesión) se reconoce con sus comprobaciones exactas auditadas, solo para consultarla, pausarla, desinstalarla o migrarla. El controlador nuevo no la activa ni instala otra encima.
- **Más información.**
  - Política, admisión, consolas que siguen apareciendo y compromiso entre disponibilidad y horario: [horario de consulta](fase6_horario.md).
  - Plan y procedimiento de la migración manual de `LP6-01023009031fcabd`, con su reversión y el protocolo nativo previo con una tarea de ensayo aislada: [migración](fase6_migracion_lp6.md).

Las secciones siguientes describen la **versión 1** y sus validaciones v3.x. Se conservan como antecedente. Donde dicen «cada cinco minutos», «inicio de sesión» o `StartWhenAvailable=true` se refieren a esa versión.

El directorio de trabajo es el `backend` absoluto del worktree indicado. No programa la CLI histórica `scripts.operacion_diaria`: esa operación de Producto 3 no acredita por sí sola el enlace con las versiones y configuraciones ML vigentes. El núcleo de Fase 6 resuelve ese enlace mediante los casos de uso actuales.

## Validación de exportaciones Windows v3.3

El ensayo nativo v3.2 ya superó el error de codificación: `Instalar` registró la tarea y falló después en `Assert-TareaPropia`. La tarea `LP6-f03df678192ac201` permanece `Disabled`, con `Enabled=false`; no hubo activación ni disparo. El ZIP del ensayo conserva planes; el segundo ZIP aporta el XML realmente exportado y CIM. De los 14 campos comparados, coinciden 11: Windows omite `RunLevel` y `WakeToRun` y expresa el usuario del desencadenador de sesión como cuenta local, mientras el plan usa SID. CIM informa `Limited` (0) y `WakeToRun=false`.

La v3.3 compara la semántica de la exportación: admite solo valores predeterminados documentados expresamente y resuelve las identidades mediante mecanismos nativos para comparar el SID esperado. Una omisión no autorizada, privilegio elevado, valor explícito incompatible o usuario distinto/no resoluble se rechaza. No usa nombre corto, sufijos ni excepciones por usuario. Revisa también vinculación, campos críticos, acciones y desencadenadores para conservar el rechazo de tareas ajenas o alteradas.

El XML exportado se archiva antes de validarlo, incluso cuando falla la comprobación posterior al registro, y se distingue del plan y del diagnóstico. Se conservan el contrato UTF-16LE con BOM, la captura binaria con decodificación estricta y las garantías de limpieza v3.2. La nueva evidencia Linux usa PowerShell real y simulaciones explícitas del Programador y la resolución nativa; no acredita Windows PowerShell 5.1, COM/MSXML, permisos o NTFS nativos. Referencias oficiales: [esquema del Programador](https://learn.microsoft.com/en-us/windows/win32/taskschd/task-scheduler-schema), [nivel de ejecución del principal](https://learn.microsoft.com/en-us/windows/win32/taskschd/principal-runlevel) y [traducción de cuenta a SID](https://learn.microsoft.com/en-us/dotnet/api/system.security.principal.ntaccount.translate). Los valores por defecto no convierten en opcionales los campos que el contrato de propiedad exige presentes.

Se conserva de v3.2 la cadena XML con declaración UTF-16 y archivo UTF-16LE con BOM, JSON/logs/huellas UTF-8 y consulta de ausencia antes de limpiar el testigo nuevo. Un fallo original de instalación conserva su código no cero aunque una limpieza posterior termine correctamente.

No se activan ni retiran tareas del equipo del operador en esta entrega. Se conservan las raíces pendientes `C:\Users\danie\AppData\Local\Temp\f6t b08b6182` y `C:\Users\danie\AppData\Local\Temp\f6t 381c1b8b`, las tareas `LP6-f03df678192ac201` y `LP6-ae2dda9494895571` y los demás restos históricos. Su limpieza será una etapa posterior separada: verificar existencia, identidad/propiedad y ausencia de ejecución, archivar evidencia y comprobar la retirada antes de borrar una raíz. Consulta o permisos fallidos, tarea ajena/viva o retirada no verificable obligan a conservar y comunicar el pendiente; no autorizan elevar permisos.

El protocolo de esta entrega termina en aplicar v3.3 sobre v3.2 exacta → pruebas dirigidas en PowerShell 5.1 → devolver evidencia y detenerse. Conservar el worktree y el Python existentes. El nuevo ensayo real del Programador será posterior a la revisión; esta guía no lo inicia ni incluye una orden para ejecutarlo ahora. No se repiten completa, ML, demostración o presentación/PDF por rutina. Operación con destinos reales, PostgreSQL, activación/novedad observada, publicación manual, Actions y acreditación prospectiva mantienen pendientes separados. Los bloques de operación real siguientes son referencia futura, no instrucciones de esta entrega.

## Instalación, validación y activación son pasos diferentes

Aplicar el parche o arrancar la web **no instala ni activa tareas**. La acción predeterminada del script es `-Plan`: crea XML deshabilitado y evidencia propia, sin consultar siquiera al Programador y sin ejecutar Python. `-Instalar` es una decisión explícita posterior de Daniel y registra una tarea deshabilitada. Solo `-Activar` o `-Reanudar` la habilitan.

Antes de registrar una tarea con datos reales deben estar revisados el manifiesto, la focal operativa, las regresiones y la validación nativa previstas en la guía de la entrega. La configuración operativa debe haberse preparado y cotejado con los destinos de la aplicación; no copiar rutas absolutas de otro worktree ni asumir que su `.env` sirve para este. El adaptador no abre la configuración ni `.env`, no importa modelos ni llama a la aplicación para verificarlas: esa validación pertenece al ejecutor y al protocolo previo.

Parámetros obligatorios:

| Parámetro | Significado |
|---|---|
| `-Worktree` | Raíz absoluta del checkout Fase 6; debe existir `backend/scripts/operacion_automatica.py` |
| `-PythonExe` | Intérprete absoluto del entorno Fase 6 independiente, validado según la guía; conservar el entorno ML anterior sin actualizarlo |
| `-Configuracion` | JSON operativo absoluto ya preparado y verificado; no contiene la elección automática de modelos |
| `-Evidencia` | Opcional: carpeta nueva absoluta fuera del worktree; por defecto se crea una carpeta propia corta bajo el temporal normal |

No combina acciones. El intérprete de esta entrega es `C:\GitHub\venvs\loteria-fase6\Scripts\python.exe`, en su entorno Fase 6 existente, que incorpora `tzdata==2026.5` en Windows para `America/Bogota`. Su preparación y conservación de versiones de modelos se detallan en la guía Windows de entrega. El entorno ML anterior `C:\GitHub\venvs\loteria-ml-cierre\Scripts\python.exe` permanece intacto; no se autoriza actualizarlo. El worktree existente de código es `C:\GitHub\loteria-predictor-fase6`. Los worktrees anteriores se conservan.

```powershell
$ErrorActionPreference = 'Stop'
$worktree = 'C:\GitHub\loteria-predictor-fase6'
$pythonF6 = 'C:\GitHub\venvs\loteria-fase6\Scripts\python.exe'
$config = 'C:\GitHub\loteria-config\fase6.json'
$control = Join-Path $worktree 'backend\scripts\windows\fase6_tarea.ps1'
$tokens = $null
$errores = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($control, [ref]$tokens, [ref]$errores)
if (@($errores).Count -ne 0) { $errores | Format-List; throw 'Sintaxis de tarea incorrecta.' }
$parametros = @{ Worktree=$worktree; PythonExe=$pythonF6; Configuracion=$config }
& $control @parametros -Plan
if ($LASTEXITCODE -ne 0) { throw 'Revisar el resultado del plan.' }
```

El plan deja `tarea.xml`, `resultado.json` y `registro.log` en la carpeta indicada por la salida. Su contenido identifica intérprete, configuración, directorio de trabajo, principal, desencadenadores y límites, sin imprimir credenciales. Cotejar el script con el manifiesto de entrega antes de ejecutarlo. Una política local puede impedir registrar tareas de usuario: conservar el error, sin cambiar permisos o políticas globales para ocultarlo.

Después de auditar y validar, **instalar deshabilitada**:

```powershell
& $control @parametros -Instalar
if ($LASTEXITCODE -ne 0) { throw 'No activar: revisar evidencia de instalacion.' }
& $control @parametros -Estado
if ($LASTEXITCODE -ne 0) { throw 'No se pudo consultar la tarea.' }
```

La repetición de `-Instalar` sobre la misma tarea exacta la reconoce sin sobrescribirla ni cambiar su estado habilitado. No se añade un programador en cada proceso web. La tarea tiene un nombre corto `LP6-<16 hex>` derivado del usuario y worktree; se muestra en el plan y en los resultados. Antes de modificar una tarea existente se contrastan su marcador de procedencia, usuario, comando, argumentos, directorio, intervalos y límites. Una tarea ajena o alterada se rechaza sin sustituirla.

## Activación y pausa

Hay dos capas diferentes: la tarea del sistema determina **cuándo se invoca** el proceso; la configuración y el estado del núcleo determinan **si puede operar** y qué destinos/modelos tiene autorizados. `-Activar` no cambia configuraciones ni modelos y no elimina una pausa operativa. La preparación real y la reanudación del núcleo son decisiones explícitas del operador mediante la CLI/panel de Fase 6.

Una vez validado ese estado, habilitar la tarea:

```powershell
& $control @parametros -Activar
if ($LASTEXITCODE -ne 0) { throw 'Activacion fallida: revisar el resultado.' }
& $control @parametros -Estado
if ($LASTEXITCODE -ne 0) { throw 'Estado del programador no disponible.' }
```

Para impedir nuevas invocaciones del Programador:

```powershell
& $control @parametros -Pausar
if ($LASTEXITCODE -ne 0) { throw 'Pausa fallida: revisar el resultado.' }
```

`-Pausar` deshabilita futuras activaciones, **sin matar un ciclo vivo entre sus pasos**. La pausa del núcleo y sus controles de recuperación se consultan por separado en el panel/CLI. `-Reanudar` vuelve a habilitar únicamente la tarea. `-Estado` solo consulta el Programador; no certifica conectividad del proveedor/BD ni éxito del último ciclo.

## Sesión, suspensión, reinicio y límites

- Principal `InteractiveToken`, usuario actual y `LeastPrivilege`: no solicita ni guarda contraseña y no pide «privilegios más altos». **Requiere una sesión abierta de ese usuario**; puede funcionar con pantalla bloqueada. Cerrar navegador, terminal o Uvicorn no la detiene. Cerrar sesión impide nuevas ejecuciones hasta el próximo inicio de sesión.
- Desencadenadores (versión 1): inicio de sesión del usuario y repetición **cada cinco minutos**. En la versión 2 se sustituyen por las franjas del plan y la recuperación de las 09:00, sin inicio de sesión ([horario](fase6_horario.md)). Son ventanas de invocación, no horarios oficiales de sorteo ni garantía de publicación. La aplicación decide en `America/Bogota` si corresponde consultar y respeta sus ventanas, espera progresiva y límites del proveedor.
- `IgnoreNew` evita tareas periódicas simultáneas. La exclusión con invocaciones manuales y otras instancias pertenece además a los cerrojos del núcleo; esta política del Programador, por sí sola, no coordina todos los escritores.
- `StartWhenAvailable=true` (versión 1) permite retomar tras una oportunidad perdida; no promete ejecutar cada intervalo ausente ni autoriza emisiones retroactivas. La versión 2 usa `false`: una oportunidad perdida no se ejecuta a otra hora y el pendiente espera a la siguiente oportunidad permitida. El núcleo reconcilia de forma acotada y bloquea emisiones cuyo evento ya no sea temporalmente admisible.
- `WakeToRun=false`: no despierta el equipo ni altera sus opciones de energía. Un PC apagado o suspendido no ejecuta tareas. Tras encender, reanudar e iniciar sesión, los ciclos recuperan novedades conforme a su política; disponibilidad continua requiere un equipo/servicio disponible.
- Límite de tarea **dos horas**, sin modificar límites de los trabajadores ML existentes. Si el Programador termina un proceso excedido o el equipo se apaga, la consulta y recuperación del núcleo distinguen actividad viva de ejecución interrumpida. Los registros persistentes se conservan; no se promocionan ni borran temporales históricos.
- La tarea puede invocarse sin red: el núcleo registra la indisponibilidad y aplica la espera progresiva. No depende de «red disponible» como sustituto de un diagnóstico real.

## Desinstalación controlada

Pausar antes de retirar una tarea que ya no se desea utilizar. Esperar a que termine cualquier ciclo vivo; `-Desinstalar` rechaza una tarea cuyo estado es `Running`, para no interrumpir una escritura. Sobre una tarea propia inactiva, la deshabilita y elimina su registro; no borra configuración, sorteos, pronósticos, evidencias o modelos. Repetir con tarea ausente es idempotente.

```powershell
& $control @parametros -Pausar
if ($LASTEXITCODE -ne 0) { throw 'No se pudo pausar la tarea.' }
& $control @parametros -Desinstalar
if ($LASTEXITCODE -ne 0) { throw 'Conservar evidencia y revisar si existe un ciclo vivo.' }
```

## Alcance de las comprobaciones

Las pruebas `test_fase6_tarea_windows.py` inspeccionan el plan con rutas que contienen espacios y Unicode, instalación deshabilitada, activación/pausa/reanudación, repetición, identidad y rechazo de una tarea ajena/alterada y de retirada con ciclo vivo. Ejecutan **PowerShell real**; los cmdlets `ScheduledTasks` se simulan expresamente, por lo que no registran tareas del sistema ni ejecutan Python del producto. En Cloud usan PowerShell 7 Linux, no Windows PowerShell 5.1 ni NTFS. El parser y estos ensayos no acreditan registro, permisos o disparo nativo.

El protocolo Windows exige, en recursos y datos sintéticos propios, el registro inicialmente deshabilitado, la habilitación explícita, al menos un disparo real, la repetición/solapamiento, la pausa y la desinstalación, conservando los resultados del ejecutor y del Programador. El ensayo nativo B de la entrega 9.2 ya tiene su evidencia histórica. La incorporación automática de una novedad y su siguiente predicción explicada en cada juego quedó acreditada por los registros reales de Daniel del 27 de octubre a las 10:21 ([observación real del 27 de octubre](fase9_3_validacion_operador_2026-10-27.md#actualizacion-real-de-fase-6-del-27-de-octubre)); no constituye una nueva ejecución de este cierre ni acredita la recuperación matinal con pendientes. La programación no cambia `experimental_no_acreditado`, AE-39 **NO-GO** ni `AUTORIZA_EVALUACION = False`.

## Baterías nativas por etapas y evidencia

Seguir `fase6-guia-windows.md` v3.3: conservar worktree/Python existentes, aplicar incremental sobre v3.2 exacta y ejecutar solo `--bateria dirigida` en espejo público verificado, con almacenes sintéticos y sin registrar tareas. Devuelve JUnit/logs/ZIP y hashes; detenerse para revisión. No cambia `.env`, TEMP/TMP, rutas largas, perfiles o permisos globales. El supervisor archiva evidencia antes de limpiar; si no puede, comunica y conserva el temporal.

Daniel completó en Windows nativo la v3.1: **7.243 aprobadas**, cero fallos, errores u omisiones; OpenSSL `exigir` 7/7, demostración sintética de cuatro juegos y `pip check` limpio. Las **47 dirigidas Linux de v3.2** conservan su evidencia propia. Son antecedentes de esas versiones, no resultados v3.3, y no se suman grupos solapados. No se repiten completa, entrenamiento, demostración o revisión visual/PDF por rutina. Las regresiones Linux usan simulaciones expresas y no acreditan el Programador o resolución nativa de identidades.

## Ensayo optativo del Programador real, completamente aislado

**Versión 2 (entrega 9.2):** el ensayo nativo B con este script se ejecutó y la auditoría lo aprobó el 26 de octubre de 2026, con el testigo sintético `LP6-aa9dcee442bf1e45`. Dio 14 pasos y 16 mutaciones acotadas al testigo. El intento de activar una versión 1 con el controlador nuevo termina con código 1, como se espera. El único inicio del testigo fue manual, y la limpieza fue completa. La tarea real no se tocó ([validación del operador](fase9_2_validacion_operador_2026-10-26.md)). Los párrafos siguientes describen las etapas v3.x de la versión 1 y se conservan como antecedente.

`tests/ensayar_tarea_fase6_windows.ps1` requiere Windows y la opción explícita `-Ejecutar`. Daniel debe revisarlo y ejecutarlo después de las baterías sintéticas. Crea un worktree testigo temporal propio con un programa Python de biblioteca estándar; ese programa solo escribe una marca de ejecución y nunca importa la aplicación, abre BD, consulta proveedor o carga modelos. El controlador real registra una tarea propia deshabilitada, la activa explícitamente, solicita un disparo real, conserva XML, identidad del intérprete, PID y resultado del Programador, la pausa y la desinstala. La espera se liga a la creación de la marca y al estado del proceso, con límite de 60 segundos.

El nuevo ensayo nativo se acordará después de revisar la evidencia dirigida v3.3. Esta entrega no incluye un bloque para ejecutarlo. En esa etapa se distinguirá el testigo nuevo de los restos anteriores y se archivarán plan, exportación real, diagnóstico, resultado y limpieza antes de comunicar un fallo; será evidencia propia y no sustituirá el recorrido con datos reales.

No se activan ni retiran tareas del equipo del operador en esta entrega. Se conservan las raíces pendientes `C:\Users\danie\AppData\Local\Temp\f6t b08b6182` y `C:\Users\danie\AppData\Local\Temp\f6t 381c1b8b`, las tareas `LP6-f03df678192ac201` y `LP6-ae2dda9494895571` y los demás restos históricos. Su limpieza será una etapa posterior separada: verificar existencia, identidad/propiedad y ausencia de ejecución, archivar evidencia y comprobar la retirada antes de borrar una raíz. Consulta o permisos fallidos, tarea ajena/viva o retirada no verificable obligan a conservar y comunicar el pendiente; no autorizan elevar permisos.

Este ensayo acredita el mecanismo nativo de tarea, rutas, permisos y disparo para el usuario actual; el flujo completo del producto se acredita por separado con sus pruebas de integración y demostración. La activación final con los destinos reales sigue siendo una decisión explícita de Daniel. Si no se puede retirar una tarea o el testigo continúa vivo, se conserva la raíz temporal y se indica su ruta; no se borra código al que aún pueda apuntar una tarea. Los errores de limpieza se registran separados del resultado principal.
