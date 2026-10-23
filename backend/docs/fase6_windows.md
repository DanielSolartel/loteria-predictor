# Fase 6: actualización y operación automática en Windows

La entrega v3.3 (`fase6-operacion-automatica-v3.3.zip`) es **incremental sobre v3.2 exacta**, árbol `8c1fb9f6b88397b3b0ace8b059fc10ae1e5d488c`, ya aplicada en `C:\GitHub\loteria-predictor-fase6`, rama `feature/fase6-operacion-automatica`, HEAD `2ac4d110b7d721e544f5588e9754230eef28184d`. No revertir versiones, recrear el worktree o aplicar un parche completo. Conservar entregas anteriores, datos e índice. La guía del ZIP acepta v3.2 exacta o v3.3 idéntica y rechaza estados ajenos antes de modificar.

**Etapas separadas: aplicación → dirigidas → devolver evidencia y detenerse.** El nuevo ensayo real del Programador será posterior a la revisión, sin orden de ejecución en esta guía. Las secciones operativas con destinos reales siguientes son referencia futura, no autorización para activarlas. No se activan ni retiran tareas del equipo del operador en esta entrega. Se conservan las raíces pendientes `C:\Users\danie\AppData\Local\Temp\f6t b08b6182` y `C:\Users\danie\AppData\Local\Temp\f6t 381c1b8b`, las tareas `LP6-f03df678192ac201` y `LP6-ae2dda9494895571` y los demás restos históricos. Su limpieza será una etapa posterior separada: verificar existencia, identidad/propiedad y ausencia de ejecución, archivar evidencia y comprobar la retirada antes de borrar una raíz. Consulta o permisos fallidos, tarea ajena/viva o retirada no verificable obligan a conservar y comunicar el pendiente; no autorizan elevar permisos.

El estado inicial es **sin configurar/en pausa**. El panel nuevo está en `/automatizacion`, integrado en la navegación. Consultarlo o abrir un historial no consulta proveedor/BD, sincroniza, genera ni inicializa almacenes. La comprobación manual es un POST local protegido que ejecuta el mismo núcleo que la CLI; no es un planificador por cada proceso Uvicorn.

## Entorno separado y conservación de versiones

El entorno Fase 6 **ya existe** en `C:\GitHub\venvs\loteria-fase6\Scripts\python.exe`, Python 3.14.6. Daniel verificó versiones numéricas/ML idénticas al entorno anterior `C:\GitHub\venvs\loteria-ml-cierre\Scripts\python.exe`, `tzdata==2026.5` y Bogotá. No recrear ni actualizar el entorno ML previo. La guía v3.3 comprueba metadatos del existente sin importar/entrenar modelos, instalar paquetes o recrear el entorno.

Las pruebas TestClient necesitan `httpx==0.28.1` y `httpcore==1.0.9`, ya añadidos y utilizados por Daniel. La guía comprueba los paquetes existentes y `pip check`; si falta algo o una versión no coincide, se detiene sin instalar, actualizar o retirar restricciones. Esta corrección no necesita cambios de dependencias.
## Validación por etapas y exportaciones nativas

Daniel completó en Windows nativo la v3.1: **7.243 aprobadas**, cero fallos, errores u omisiones; OpenSSL `exigir` 7/7, demostración sintética de cuatro juegos y `pip check` limpio. Las **47 dirigidas Linux de v3.2** conservan su evidencia propia. Son antecedentes de esas versiones, no resultados v3.3, y no se suman grupos solapados.

El ensayo nativo v3.2 ya superó el error de codificación: `Instalar` registró la tarea y falló después en `Assert-TareaPropia`. La tarea `LP6-f03df678192ac201` permanece `Disabled`, con `Enabled=false`; no hubo activación ni disparo. El ZIP del ensayo conserva planes; el segundo ZIP aporta el XML realmente exportado y CIM. De los 14 campos comparados, coinciden 11: Windows omite `RunLevel` y `WakeToRun` y expresa el usuario del desencadenador de sesión como cuenta local, mientras el plan usa SID. CIM informa `Limited` (0) y `WakeToRun=false`.

La v3.3 compara la semántica de la exportación: admite solo valores predeterminados documentados expresamente y resuelve las identidades mediante mecanismos nativos para comparar el SID esperado. Una omisión no autorizada, privilegio elevado, valor explícito incompatible o usuario distinto/no resoluble se rechaza. No usa nombre corto, sufijos ni excepciones por usuario. Revisa también vinculación, campos críticos, acciones y desencadenadores para conservar el rechazo de tareas ajenas o alteradas.

El XML exportado se archiva antes de validarlo, incluso cuando falla la comprobación posterior al registro, y se distingue del plan y del diagnóstico. Se conservan el contrato UTF-16LE con BOM, la captura binaria con decodificación estricta y las garantías de limpieza v3.2. La nueva evidencia Linux usa PowerShell real y simulaciones explícitas del Programador y la resolución nativa; no acredita Windows PowerShell 5.1, COM/MSXML, permisos o NTFS nativos.

Usar los cuatro bloques completos de `fase6-guia-windows.md`. La batería `--bateria dirigida` incluye captura/controlador, contrato XML, limpieza, exportación nativa parametrizada y supervisor en espejo público verificado y almacenes sintéticos; no registra tareas del sistema. Devuelve JUnit/logs/resultado y ZIP con hashes y se detiene. El nuevo ensayo real y la limpieza de restos pendientes tendrán protocolos posteriores separados, tras revisar esta evidencia.

Referencias oficiales: [esquema del Programador](https://learn.microsoft.com/en-us/windows/win32/taskschd/task-scheduler-schema), [nivel de ejecución del principal](https://learn.microsoft.com/en-us/windows/win32/taskschd/principal-runlevel) y [traducción de cuenta a SID](https://learn.microsoft.com/en-us/dotnet/api/system.security.principal.ntaccount.translate). Los valores por defecto no convierten en opcionales los campos que el contrato de propiedad exige presentes.

## Destinos explícitos antes de operar con datos reales

La CLI se ejecuta desde el backend nuevo, con rutas e intérprete absolutos. El proveedor y la BD no se consultan al pedir `rutas`, preparar el arranque o consultar `estado`. La carga normal de Settings usa la configuración de la aplicación; ni el aplicador ni la validación sintética copian o leen el `.env` real. No copiar rutas absolutas de worktrees antiguos sin revisarlas, ni cambiar configuraciones vigentes para hacer pasar una prueba.

Después de auditar y validar, Daniel decide qué destinos de aplicación corresponden al worktree nuevo. No se migra automáticamente ningún almacén. El archivo de arranque operativo fija backend absoluto, destinos y SHA-256 de la conexión, sin guardar DSN/credenciales. Por defecto vive bajo `directorio_automatizacion` como `config-ejecucion.json`; puede elegirse una ruta absoluta con `--config` o `ARCHIVO_OPERACION_AUTOMATICA`. `DIRECTORIO_AUTOMATIZACION` controla el nuevo almacén operativo, separado de la elección de modelos.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $worktree = 'C:\GitHub\loteria-predictor-fase6'
    $pythonF6 = 'C:\GitHub\venvs\loteria-fase6\Scripts\python.exe'
    $config = 'C:\GitHub\loteria-config\fase6.json'
    if (-not (Test-Path -LiteralPath $pythonF6 -PathType Leaf)) { throw 'No existe el interprete Fase 6.' }
    if (-not (Test-Path -LiteralPath (Join-Path $worktree 'backend') -PathType Container)) { throw 'No existe el backend Fase 6.' }
    Push-Location (Join-Path $worktree 'backend')
    try {
        & $pythonF6 -m scripts.operacion_automatica --config $config rutas
        if ($LASTEXITCODE -ne 0) { throw 'No se pudieron resolver los destinos.' }
        # Revisar primero las rutas mostradas y su correspondencia con la app.
        & $pythonF6 -m scripts.operacion_automatica --config $config preparar --confirmar-destinos
        if ($LASTEXITCODE -ne 0) { throw 'Preparacion rechazada; no activar.' }
        & $pythonF6 -m scripts.operacion_automatica --config $config estado
        if ($LASTEXITCODE -ne 0) { throw 'Estado no disponible; conservar evidencia.' }
    } finally {
        Pop-Location
    }
}
```

`preparar` deja la operación pausada; repetir con los mismos destinos reutiliza el arranque y conserva excepciones. Un destino diferente requiere revisión y `--reemplazar` explícito, sin un ciclo activo. Si faltan o no coinciden los destinos, el panel muestra un bloqueo y reanudar/ciclo se rechazan. La selección ML se hace en Carteras: por juego, escoger una versión registrada compatible, revisar configuración/corte y conservar su identificación. El ejecutor no entrena, elige ganadores, cambia la selección ni sustituye un modelo faltante.

## Calendario, novedad y emisión admisible

[Fuentes oficiales y evidencia de acceso](fase6_fuentes.md) documentan las franjas por juego, consulta y discrepancia de MiLoto. El calendario usa `America/Bogota`, no la zona del equipo. Una hora prevista alcanzada no demuestra celebración; un resultado no publicado y una consulta fallida tampoco son lo mismo. No hay hora garantizada de publicación. Excepciones explícitas se guardan en `excepciones` del arranque por código de juego, con fecha local, hora o cancelación, motivo, URL y verificación. Una excepción sin verificar bloquea la emisión automática hasta revisar su fuente, incluso si propone cancelar una fecha.

Cada comprobación respeta inicialmente tres páginas, reconciliación de doce resultados, cursor de recuperación persistente e intervalos de quince minutos cerca del evento y hasta tres horas fuera de ventana. Los fallos aplican espera exponencial de cinco minutos hasta una hora, respetando como mínimo `Retry-After` del proveedor; el máximo de reintentos y límites se guardan como política operativa separada. Tras agotar reintentos queda un bloqueo visible que exige revisión. `--forzar` anticipa una consulta manual ordinaria; no salta el tiempo de espera de un fallo.

La secuencia es validar destino/selección → consultar y validar identidad/juego/fecha/numeración/integridad → importar → asociar emisiones y resultados por juego → guardar o reutilizar informes → generar siguiente cartera y explicación, si aún es admisible. Baloto y Revancha no se confunden por compartir numeración. El objetivo sale del último resultado validado y el evento siguiente a su fecha: si ese evento ya alcanzó su inicio se bloquea, aunque la BD aún no conozca el resultado. Se vuelven a comprobar plazo, objetivo e integridad justo antes de publicar. Los huecos bloquean emisiones hasta completar recuperación.

Una versión incompatible o no congelada produce un bloqueo accionable. Repetir entradas reutiliza cartera/explicación e informes sin reentrenar. Las actualizaciones de resultados no modifican transiciones/posteriores de un modelo registrado ni reescriben pronósticos anteriores. Una operación anterior al evento sigue siendo experimental y no acredita ventaja predictiva.

## Correcciones e informes conservados

La v3 mantiene una política de orden común a consulta, panel y admisión: si todas las decisiones de la revisión tienen `en` válido con zona, se compara su instante UTC; si alguna no lo tiene, se conserva compatibilidad por mtime para toda la revisión. Un máximo empatado entre contenidos distintos se proyecta con `orden_ambiguo=True` y bloquea emisión; el nombre SHA solo ordena la presentación. La ambigüedad se calcula antes de aplicar límites. Propuestas y decisiones previas conservan sus bytes y fechas, sin migración; una nueva decisión explícita vigente puede resolver el bloqueo.

Una diferencia en un resultado ya existente no se importa como nuevo ni se sobrescribe automáticamente. Se archiva una propuesta inmutable con estado anterior/propuesto, clave, fecha y procedencia. Después de importar y reconciliar, la emisión consulta todas las propuestas persistidas pertinentes al juego y al rango del histórico usado, con sus decisiones. No depende de las cien entradas visibles del panel ni de las páginas o doce resultados recientes: una revisión antigua pendiente sigue bloqueando, incluso si el proveedor ya no la devuelve en ese ciclo. Revisiones de otros juegos o fuera del corte no bloquean esta emisión. La importación y reconciliación admisibles continúan; solo una decisión explícita aceptada o rechazada resuelve el bloqueo, sin cambiar modelos o pronósticos históricos. Daniel coteja la fuente y decide en CLI con nota explícita:

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $config = 'C:\GitHub\loteria-config\fase6.json'
    $worktree = 'C:\GitHub\loteria-predictor-fase6'
    $pythonF6 = 'C:\GitHub\venvs\loteria-fase6\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $pythonF6 -PathType Leaf)) { throw 'No existe el interprete Fase 6.' }
    if (-not (Test-Path -LiteralPath (Join-Path $worktree 'backend') -PathType Container)) { throw 'No existe el backend Fase 6.' }
    Push-Location (Join-Path $worktree 'backend')
    try {
        $claveRevision = 'SUSTITUIR_POR_LA_CLAVE_SHA256_DEL_AVISO'
        & $pythonF6 -m scripts.operacion_automatica --config $config revision --clave $claveRevision --nota 'Fuente y comprobacion realizadas por el operador' --aceptar
        if ($LASTEXITCODE -ne 0) { throw 'Revision no aplicada; conservar evidencia.' }
    } finally {
        Pop-Location
    }
}
```

Usar `--rechazar` en lugar de `--aceptar` para conservar una decisión negativa; no ejecutar ambos comandos por rutina. Aceptar verifica contenido actual y huellas, actualiza mediante el caso de uso existente y registra una decisión separada. La creación original del sorteo y las emisiones permanecen. La siguiente reconciliación publica o reutiliza informes inmutables: seguimiento y retrospectiva se mantienen separados, sin sustituir el anterior ni mezclar sus clases de evidencia. Una interrupción después del commit permite completar la decisión sin aplicar otra vez el cambio.

## Pausa, recuperación y disponibilidad

`estado` y GET del panel muestran última comprobación/actualización, último sorteo, evento/consulta siguientes, selección congelada, pasos, avisos e historial. Un juego con fallo no oculta el resto. El núcleo distingue un proceso con cerrojo vivo, una ejecución terminal y una interrupción sin cierre. Si la consulta leyó `en_curso` y después observa el cerrojo liberado, relee el registro para conservar el cierre publicado por el escritor antes de liberar. Recuperar valida otra vez el estado y la actividad bajo el recurso de escritura de la ejecución y solo persiste una interrupción confirmada; conserva los terminales aunque coincidan cierres o dos recuperaciones. La detección de procesos realmente muertos permanece. También rearma explícitamente los contadores de reintentos agotados, adquiriendo el cerrojo de cada juego y sin interferir con uno ocupado. No sincroniza, emite, borra o promociona temporales ajenos. Repetir luego un ciclo explícito conserva publicaciones ya válidas.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    $config = 'C:\GitHub\loteria-config\fase6.json'
    $worktree = 'C:\GitHub\loteria-predictor-fase6'
    $pythonF6 = 'C:\GitHub\venvs\loteria-fase6\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $pythonF6 -PathType Leaf)) { throw 'No existe el interprete Fase 6.' }
    if (-not (Test-Path -LiteralPath (Join-Path $worktree 'backend') -PathType Container)) { throw 'No existe el backend Fase 6.' }
    Push-Location (Join-Path $worktree 'backend')
    try {
        & $pythonF6 -m scripts.operacion_automatica --config $config pausar
        if ($LASTEXITCODE -ne 0) { throw 'Revisar la pausa del nucleo.' }
        & $pythonF6 -m scripts.operacion_automatica --config $config recuperar
        if ($LASTEXITCODE -ne 0) { throw 'Revisar los registros de recuperacion.' }
    } finally {
        Pop-Location
    }
}
```

La pausa se revisa entre pasos y antes de emitir; no mata un proceso a mitad de una escritura. Los cerrojos locales coordinan procesos que comparten almacén. El protocolo advisory PostgreSQL coordina por juego a los escritores que usan repositorios de la aplicación, incluso entre instancias; no bloquea SQL externo que lo ignore. SQLite de pruebas no acredita exclusión PostgreSQL. No modificar/borrar registros para simular un cierre.

El control de tarea está en [fase6_tarea_windows.md](fase6_tarea_windows.md): plan predeterminado, instalación deshabilitada, activación y pausa explícitas, comprobación de identidad y desinstalación solo de la tarea propia inactiva. El núcleo y el Programador son dos capas: habilitar una no elimina la pausa de la otra. Tras autorizar el recorrido real, `reanudar` y `ciclo --juego todos` permiten una ejecución controlada previa a la programación; estos comandos sí pueden consultar/importar/generar con los destinos elegidos y no forman parte de la aplicación o validación sintética.

El mecanismo usa usuario actual y privilegio mínimo, sin administrador ni contraseña guardada. Exige sesión abierta y equipo despierto; pantalla bloqueada es compatible. Cerrar navegador/Uvicorn no lo detiene; cerrar sesión, apagar o suspender sí impide nuevas ejecuciones. No despierta el PC ni cambia opciones de energía. La recuperación al volver no autoriza emisiones retroactivas.

## Evidencia y pendientes

Daniel completó en Windows nativo la v3.1: **7.243 aprobadas**, cero fallos, errores u omisiones; OpenSSL `exigir` 7/7, demostración sintética de cuatro juegos y `pip check` limpio. Las **47 dirigidas Linux de v3.2** conservan su evidencia propia. Son antecedentes de esas versiones, no resultados v3.3, y no se suman grupos solapados.

Se mantiene la captura v3.1: `-OutputFormat Text` y `$ProgressPreference='SilentlyContinue'` solo en el hijo, bytes de ambos streams y códigos antes de decodificar UTF-8 estricto. Los errores de decodificación/código23 deliberados se contrastan con su caso aprobado en JUnit. XML Unicode, limpieza v3.2 y bloqueos científicos permanecen. Los mocks Linux no acreditan traducción nativa de identidades o Programador Windows.

No se activan ni retiran tareas del equipo del operador en esta entrega. Se conservan las raíces pendientes `C:\Users\danie\AppData\Local\Temp\f6t b08b6182` y `C:\Users\danie\AppData\Local\Temp\f6t 381c1b8b`, las tareas `LP6-f03df678192ac201` y `LP6-ae2dda9494895571` y los demás restos históricos. Su limpieza será una etapa posterior separada: verificar existencia, identidad/propiedad y ausencia de ejecución, archivar evidencia y comprobar la retirada antes de borrar una raíz. Consulta o permisos fallidos, tarea ajena/viva o retirada no verificable obligan a conservar y comunicar el pendiente; no autorizan elevar permisos.

El protocolo de esta entrega termina en aplicar v3.3 sobre v3.2 exacta → pruebas dirigidas en PowerShell 5.1 → devolver evidencia y detenerse. Conservar el worktree y el Python existentes. El nuevo ensayo real del Programador será posterior a la revisión; esta guía no lo inicia ni incluye una orden para ejecutarlo ahora. No se repiten completa, ML, demostración o presentación/PDF por rutina. Operación con destinos reales, PostgreSQL, activación/novedad observada, publicación manual, Actions y acreditación prospectiva mantienen pendientes separados. Mantener `experimental_no_acreditado`, AE-39 **NO-GO** y `AUTORIZA_EVALUACION = False`. Fases 7–11 solo planificadas.
