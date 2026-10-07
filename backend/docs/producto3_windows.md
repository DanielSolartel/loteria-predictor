# Producto 3 en Windows: panel diario, operación y rendimiento

Esta guía usa el equipo del operador:

- worktree de Producto 3: `C:\GitHub\loteria-predictor-producto3`;
- intérprete: `$env:LOCALAPPDATA\loteria-predictor-venvs\ae68\Scripts\python.exe`.

La instalación del parche y las pruebas están en la guía de entrega
(`producto3-guia-windows.md`). Todas las órdenes se ejecutan en PowerShell
desde `backend\` del worktree.

Cada ventana de PowerShell que uses para Producto 3 debe fijar sus rutas de
almacenamiento. Tu sesión puede traer `DIRECTORIO_PRONOSTICOS_EXPERIMENTALES`
apuntando a Producto 2, y las variables de entorno prevalecen sobre `.env`.

```powershell
$wt = 'C:\GitHub\loteria-predictor-producto3'
$p2 = 'C:\GitHub\loteria-predictor-producto2'
$py = Join-Path $env:LOCALAPPDATA 'loteria-predictor-venvs\ae68\Scripts\python.exe'
function Revisar([string]$paso) { if ($LASTEXITCODE -ne 0) { throw "$paso falló (código $LASTEXITCODE)" } }
$env:PYTHONIOENCODING = 'utf-8'
$env:DIRECTORIO_PRONOSTICOS_EXPERIMENTALES = 'C:\GitHub\loteria-predictor-producto3\backend\storage\pronosticos'
$env:DIRECTORIO_OPERACION = 'C:\GitHub\loteria-predictor-producto3\backend\storage\operacion'
Set-Location (Join-Path $wt 'backend')
$rutas = (& $py -m scripts.operacion_diaria rutas | Out-String) | ConvertFrom-Json   # solo rutas, sin credenciales
Revisar 'rutas'
foreach ($clave in 'directorio_pronosticos_experimentales', 'directorio_operacion') {
    $ruta = $rutas.$clave; "${clave}: $ruta"
    if ($ruta.StartsWith($p2, [StringComparison]::OrdinalIgnoreCase)) { throw "${clave} apunta a Producto 2" }
    if (-not $ruta.StartsWith("$wt\backend\storage\", [StringComparison]::OrdinalIgnoreCase)) { throw "${clave} sale del worktree" }
}
```

## 1. Panel diario y rendimiento

Arranca la aplicación en el puerto 8002 desde una ventana con la cabecera
anterior: `& $py -m uvicorn app.main:app --host 127.0.0.1 --port 8002`. Así
no choca con los servidores de Productos 1 y 2. Luego abre en esta misma
máquina:

- **http://localhost:8002/operacion (Panel diario):** cada uno de los cuatro juegos muestra:
  - último sorteo y fecha, frescura y huecos;
  - pronóstico actual y su resultado (pendiente o conocido);
  - comparación del histórico hasta el corte;
  - última ejecución y avisos.

  Los botones **Generar con datos locales** y **Actualizar datos y generar** funcionan por juego o para todos. Abrir la página no ejecuta nada.
- **http://localhost:8002/rendimiento (Rendimiento):** por juego, objetivos incluidos, pendientes y excluidos, aciertos, Log Loss y Brier frente a la uniforme, y la gráfica de la diferencia acumulada con su tabla. Las reconstrucciones retrospectivas y el seguimiento se muestran por separado.

Al pulsar un botón, la página pasa a la ejecución (`/operacion/ejecuciones/<id>`) y
muestra el progreso. Puedes recargarla, o cerrarla y volver: el estado queda
guardado en `storage\operacion\ejecuciones\`. No arranques uvicorn con varios
trabajadores para operar.

## 2. Comando de operación diaria

```powershell
& $py -m scripts.operacion_diaria ejecutar --juego todos --modo local;        $LASTEXITCODE
& $py -m scripts.operacion_diaria ejecutar --juego MILOTO --modo local;       $LASTEXITCODE
& $py -m scripts.operacion_diaria ejecutar --juego todos --modo actualizar;   $LASTEXITCODE
& $py -m scripts.operacion_diaria ejecuciones --limite 5;                     Revisar 'ejecuciones'
$ultima = ((& $py -m scripts.operacion_diaria ejecuciones --limite 1 | Out-String) | ConvertFrom-Json).ejecuciones[0].id
Revisar 'ultima ejecucion'
& $py -m scripts.operacion_diaria consultar --id $ultima;                     Revisar 'consultar'
& $py -m scripts.operacion_diaria rendimiento --juego BALOTO --emision todas; Revisar 'rendimiento'
& $py -m scripts.operacion_diaria recuperar;                                  Revisar 'recuperar'
```

- **Modos:**
  - `--modo local`: usa solo el histórico cargado, en una transacción de solo lectura; no escribe sorteos.
  - `--modo actualizar`: ejecuta antes la importación incremental existente, la misma de **Importación**.
- **Códigos de salida:**

  | Código | Significado |
  |---|---|
  | `0` | Éxito |
  | `2` | Uso incorrecto o ejecución no encontrada |
  | `3` | Base o registro no disponibles |
  | `5` | Resultado parcial |
  | `6` | Ya hay una ejecución activa para ese juego (web o comando) |
  | `7` | Fallo |

  Un resultado parcial nunca devuelve `0`.
- **Interrupción:** la ejecución aparece como «interrumpida» si su trabajador deja de existir antes de escribir el cierre (cierre de la ventana, reinicio, corte, disco lleno al cerrar, o un hilo que no se pudo lanzar). Se reconoce porque ya no tiene tomado su cerrojo de ejecución, aunque sus juegos hubieran terminado.
  - Los juegos que sí terminaron conservan su resultado, y nunca se anota un éxito que no llegó a registrarse.
  - Para recuperarla, vuelve a ejecutar: lo ya publicado se reutiliza y no se duplica.
  - `recuperar` solo deja anotado el estado.
- **Cerrojos:** si falla algo al adquirirlos (por ejemplo, disco lleno), se liberan todos los tomados. Solo un cerrojo realmente ocupado se informa como ejecución activa; los demás errores del sistema se muestran como tales.
- **Temporales:** si quedaron temporales `.*.tmp` en `storage\pronosticos\<JUEGO>\` por una escritura interrumpida, el panel los cuenta bajo «Trazabilidad». No son pronósticos. Se pueden borrar a mano cuando no haya ninguna ejecución activa.

## 3. Demostración

Sintética, sin base de datos ni Internet:

```powershell
& $py -m tests.demostracion_producto3; Revisar 'demostracion'
```

Con tu histórico real (actualiza tu base desde el origen y escribe pronósticos en el worktree):

```powershell
& $py -m scripts.operacion_diaria ejecutar --juego todos --modo local;      $LASTEXITCODE   # 0 esperado
& $py -m scripts.operacion_diaria ejecutar --juego todos --modo local;      $LASTEXITCODE   # reutiliza
& $py -m scripts.operacion_diaria ejecutar --juego todos --modo actualizar; $LASTEXITCODE   # 0, 5 o 7: revisa el JSON
& $py -m scripts.operacion_diaria rendimiento --juego MILOTO;               Revisar 'rendimiento'
```

Cuando el origen publique un sorteo nuevo, `--modo actualizar` lo
incorpora. El pronóstico que lo tenía como objetivo pasa a «observado» en el
panel y en Rendimiento (tipo seguimiento). El siguiente objetivo se genera
en la misma ejecución.

## 4. Ejecución periódica (opcional) con el Programador de tareas

La aplicación no programa nada por sí misma: no hay ningún programador
dentro de uvicorn, y con `--reload` o varios trabajadores no se duplica
ninguna tarea. Si quieres una ejecución diaria, créala tú en el
Programador de tareas. Esta guía no crea ni activa ninguna tarea.

1. Abre el **Programador de tareas** y elige **Crear tarea básica**. Ponle un nombre, por ejemplo `Loteria - operacion diaria`, y un desencadenador **Diariamente** a la hora que prefieras.
2. En **Acción**, elige **Iniciar un programa** y rellena:
   - **Programa:** `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`
   - **Argumentos:** `-NoProfile -ExecutionPolicy Bypass -Command "& { $env:DIRECTORIO_PRONOSTICOS_EXPERIMENTALES = 'C:\GitHub\loteria-predictor-producto3\backend\storage\pronosticos'; $env:DIRECTORIO_OPERACION = 'C:\GitHub\loteria-predictor-producto3\backend\storage\operacion'; Set-Location 'C:\GitHub\loteria-predictor-producto3\backend'; New-Item -ItemType Directory -Force 'storage\operacion' | Out-Null; & (Join-Path $env:LOCALAPPDATA 'loteria-predictor-venvs\ae68\Scripts\python.exe') -m scripts.operacion_diaria ejecutar --juego todos --modo actualizar *>> 'C:\GitHub\loteria-predictor-producto3\backend\storage\operacion\tarea.log'; exit $LASTEXITCODE }"`
   - **Iniciar en:** `C:\GitHub\loteria-predictor-producto3\backend`
3. En las propiedades de la tarea, marca **Ejecutar solo cuando el usuario haya iniciado sesión**. Así usa tu perfil, con el mismo `LOCALAPPDATA` y la misma configuración.
4. **Resultado:** la columna **Resultado de la última ejecución** muestra el código de salida (`0x0` éxito; `0x5` parcial; `0x6` ya activa; `0x7` fallo). El detalle queda en el panel y en `storage\operacion\tarea.log`.
   - El registro contiene el JSON de la ejecución y los avisos, nunca la cadena de conexión.
   - Si la base no está disponible, solo se anota «Sin conexion con la base de datos».

Si la tarea coincide con una ejecución lanzada desde la web, el comando
termina con `6` sin tocar nada.

## 5. Validación registrada en Windows

**Estado:** validado localmente en Windows con histórico real, en el equipo del operador (Python 3.14.6, OpenSSL de Git 3.5.6). Los pronósticos siguen `experimental_no_acreditado`, con `AUTORIZA_EVALUACION = False`.

- **Pruebas:**
  - Producto 3 `62 passed`, Producto 2 `61 passed`, Producto 1 `102 passed` y selección `1773 passed`;
  - OpenSSL `SUPERADOS 7/7` (`exigir`) y `pip check` limpio;
  - demostración sintética 6/6;
  - un aviso de Starlette por `httpx` en `TestClient`, que no es un fallo.

  La suite completa no se ejecutó en Windows.
- **Datos locales:**
  - Dos ejecuciones correctas; la segunda reutilizó los cuatro pronósticos.
  - La reproducción fue exacta en los cuatro juegos, con los pronósticos anteriores a la actualización.
  - Los archivos copiados o comprobados desde Producto 2 se conservaron byte a byte.
- **Actualizar datos y generar** (6 de octubre de 2026, hora de Colombia; las marcas UTC muestran el 7):
  - resultado `exito`, código 0;
  - un sorteo nuevo por juego, con objetivos 2719, 2719, 619 y 225;
  - los 10 pronósticos JSON previos se conservaron.
  - En MiLoto, el conector emitió `DATOS_INCOMPLETOS` porque no encontró la tabla del desglose de premios. Esa ejecución no acredita un desglose completo de premios para ese sorteo, y la causa no se comprobó.
- **Interfaz:** se revisó el panel y el rendimiento en el puerto 8002, con PDF en Carta vertical sin solapamientos. No se revisaron la vista móvil ni la Carta horizontal.
- **No validado:**
  - la tarea del Programador de tareas de la sección 4: no se creó ninguna;
  - una pérdida de energía durante la publicación;
  - la detección de correcciones de sorteos antiguos.
