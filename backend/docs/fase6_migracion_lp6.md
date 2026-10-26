# Fase 6: migración de la tarea `LP6-01023009031fcabd` al horario por juego

**Estado: plan y procedimiento preparados; la migración real NO está aplicada.**

- **Protocolo nativo:** el de la [sección 0](#0-antes-de-migrar-protocolo-nativo-con-una-tarea-de-ensayo-aislada), con una tarea de ensayo aislada, se ejecutó y la auditoría independiente lo aprobó el 26 de octubre de 2026 ([validación del operador](fase9_2_validacion_operador_2026-10-26.md)).
- **La tarea real:** durante la implementación, la auditoría y ese ensayo no se registró, habilitó, deshabilitó, borró ni disparó. Sigue habilitada con su programación anterior (versión 1), y su XML conserva el SHA-256 `61190fa7263750ae8434f9d7052adbc077a77ed0146a8fe52eb56ac29ce7c296`.
- **Lo que no se tocó:** no se consultó SQL operativo, no se ejecutaron ciclos reales y no se tocaron el worktree ni el entorno privado del origen operativo.
- **Lo que falta:** la migración real se preparará después de la publicación y del CI del nuevo PR, como un bloque separado con respaldo y reversión que Daniel revisa y ejecuta. No se ejecuta ni se deja automatizada.

**Datos de partida (encargo del 25 de octubre de 2026):**

| Dato | Valor |
|---|---|
| Tarea | `LP6-01023009031fcabd`, versión 1 |
| Origen operativo | `C:\GitHub\loteria-predictor-fase6` |
| Intérprete | `C:\GitHub\venvs\loteria-fase6\Scripts\python.exe` |
| Acción actual | `-m scripts.operacion_automatica --config "<config>" ciclo` |
| Desencadenadores | `TimeTrigger` PT5M sin duración y `LogonTrigger`; `StartWhenAvailable=true` |

El código nuevo rechaza un `ciclo` sin modo (código 2, sin consultar). Por eso **cambiar solo el código del origen operativo con la tarea antigua habilitada deja de consultar, pero sigue abriendo una consola cada cinco minutos**. Y cambiar solo la tarea no sirve si el Programador sigue llamando al código antiguo, que no conoce `--programado`. Por eso la migración deshabilita la tarea antes de tocar el código y la sustituye en el mismo paso controlado.

## 0. Antes de migrar: protocolo nativo con una tarea de ensayo aislada

Se hace en un checkout de auditoría con el parche aplicado, **no** en `C:\GitHub\loteria-predictor-fase6`.

1. Pruebas dirigidas con el Python del checkout de auditoría:

   ```powershell
   python -m pytest tests/unit/test_fase6_horario.py tests/unit/test_fase6_horario_regresiones.py tests/unit/test_fase6_auditoria_v1.py tests/unit/test_fase6_tarea_windows.py tests/unit/test_fase6_xml_windows.py tests/unit/test_fase6_exportacion_windows.py tests/unit/test_fase6_ensayo_limpieza_windows.py tests/unit/test_fase6_cli.py tests/unit/test_fase6_ciclo.py tests/unit/test_fase6_web.py --junitxml "<evidencia>\f6-dirigidas.xml"
   ```

   En Windows con PowerShell, las baterías de la tarea se ejecutan de verdad, con los cmdlets del Programador simulados.

2. Plan de ensayo en un archivo UTF-8 nuevo, generado con la función pura (no lee configuración ni base de datos):

   ```powershell
   python -c "import json,sys; from app.application import operacion_horario as h; open(sys.argv[1],'x',encoding='utf-8',newline='\n').write(json.dumps(h.plan_windows(h.propuesta_inicial()),ensure_ascii=False,indent=2)+'\n')" "C:\GitHub\evidencias\f92\plan-ensayo.json"
   ```

   No uses `>` ni `Out-File` en PowerShell 5.1: escriben UTF-16 o UTF-8 con BOM, y el controlador exige UTF-8 estricto.

3. Ensayo nativo aislado. Crea un worktree testigo en `%TEMP%`, con otro nombre de tarea:

   ```powershell
   & .\tests\ensayar_tarea_fase6_windows.ps1 -PythonExe "<python del checkout>" -Evidencia "C:\GitHub\evidencias\f92\ensayo-nativo" -PlanHorario "C:\GitHub\evidencias\f92\plan-ensayo.json" -Ejecutar
   ```

   El ensayo hace lo siguiente:
   - registra la versión 2 deshabilitada y comprueba que solo tiene `CalendarTrigger` y `StartWhenAvailable` en false. El Programador puede omitir ese elemento al exportarlo: su ausencia vale el predeterminado documentado `false`;
   - la habilita y anota `NextRunTime` y la zona del equipo;
   - la arranca a demanda una vez, con un testigo que anota que recibió `ciclo --programado --plan <huella>`;
   - la pausa y la retira;
   - instala una versión 1 con el script anterior archivado (`tests/fixtures/fase6/fase6_tarea_v1.ps1`) y la habilita;
   - comprueba que el controlador nuevo se niega a activarla;
   - la migra (`-Migrar`) a la versión 2 deshabilitada, con su XML de reversión;
   - la revierte (`-Revertir`) a la versión 1 deshabilitada y la retira.

   No toca `LP6-01023009031fcabd`. La protección contra duplicados solo considera tareas propias sobre la misma configuración o el mismo backend, así que la tarea real (habilitada) y los restos de ensayos anteriores (`LP6-f03df678192ac201`, `LP6-ae2dda9494895571`) se registran en el resultado sin modificarse.

4. Devolver `resultado-tarea-nativa.json`, las exportaciones, los diagnósticos, el JUnit y los registros, y comparar a mano `NextRunTime` con la próxima oportunidad del panel. **Detenerse** hasta la revisión.

**Resultado (26 de octubre de 2026, aprobado por la auditoría).** Windows 11, Python 3.14.6, Windows PowerShell 5.1.26100.9711 y zona `SA Pacific Standard Time`.

- **Pruebas dirigidas:** 121 casos únicos aprobados, por consolidación de dos corridas (117 sobre v3 y 4 revalidados sobre v4).
- **Ensayo nativo B,** con el testigo sintético `LP6-aa9dcee442bf1e45`:
  - 14 pasos. El intento de activar la versión 1 con el controlador nuevo termina con código 1, como se espera; los otros 13, con código 0;
  - 16 mutaciones, todas sobre el testigo: Register 4, Enable 2, Start 1, Disable 5 y Unregister 4;
  - el Programador omitió `StartWhenAvailable` en la exportación, y el diagnóstico lo registró como `predeterminado_documentado` con valor false;
  - el único inicio fue manual, con `Start-ScheduledTask`, y el testigo recibió `ciclo --programado --plan <huella>`;
  - `NextRunTime` coincidió con el plan;
  - la migración a la versión 2 deshabilitada y la reversión a la versión 1 deshabilitada no tuvieron activación intermedia;
  - la limpieza fue completa.
- **Tarea real:** `LP6-01023009031fcabd` conservó su XML y siguió habilitada.

No se observó un disparo automático futuro ni se ejecutó un ciclo del producto con datos reales. Evidencias y huellas: [validación del operador](fase9_2_validacion_operador_2026-10-26.md).

## 1. Plan de la migración real (posterior a la auditoría y a la publicación)

Este plan es la base del bloque separado de migración. Ese bloque se prepara después de la publicación y del CI del nuevo PR, con respaldo y reversión verificados, y Daniel lo revisa antes de ejecutarlo.

Cada paso guarda su evidencia en una carpeta nueva fuera de los worktrees. Si un paso falla, se detiene la migración y se conservan sus registros. Variables:

```powershell
$ErrorActionPreference = 'Stop'
$wt = 'C:\GitHub\loteria-predictor-fase6'
$py = 'C:\GitHub\venvs\loteria-fase6\Scripts\python.exe'
$cfg = '<ruta absoluta del archivo de arranque, EXACTAMENTE como figura en los argumentos de la tarea actual>'
$ev = 'C:\GitHub\evidencias\lp6-migracion-<fecha>'
$ctl = Join-Path $wt 'backend\scripts\windows\fase6_tarea.ps1'   # tras el paso 1.4
```

**1.1 Propiedad y versión antigua (solo lectura).**

```powershell
& '<checkout auditado>\backend\scripts\windows\fase6_tarea.ps1' -Worktree $wt -PythonExe $py -Configuracion $cfg -Evidencia "$ev\01-estado" -Estado
```

Debe ocurrir todo lo siguiente:
- el resultado nombra `LP6-01023009031fcabd` (el nombre se deriva del worktree y del SID; no se buscan nombres por prefijo);
- `version_tarea` vale `1`;
- la exportación queda archivada en UTF-16LE con BOM y la validación consta como aprobada: marca `LoteriaPredictor/Fase6/tarea/1`, vinculación con PT5M, usuario, intérprete, argumentos, backend, límites y los dos desencadenadores auditados.

Una tarea ajena o alterada se rechaza sin cambios y **la migración no sigue**. Esa exportación es la primera copia de reversión.

**1.2 Deshabilitar la tarea antigua y esperar a que no haya ciclo vivo.**

```powershell
& '<checkout auditado>\backend\scripts\windows\fase6_tarea.ps1' -Worktree $wt -PythonExe $py -Configuracion $cfg -Evidencia "$ev\02-pausar" -Pausar
```

`estado_programador` no puede ser `Running`. Con el código actual del origen operativo, `python -m scripts.operacion_automatica --config $cfg estado` no debe mostrar ejecuciones `en_curso`. Si las hay, esperar y repetir; nunca matar el proceso.

**1.3 Copia de la configuración operativa versión 1.** Copiar `configuracion.json` del directorio de automatización a `configuracion.v1-<fecha>.json` **en el mismo directorio**. Comprobar el SHA-256 de ambas copias. No se copian almacenes entre worktrees.

**1.4 Llevar el código auditado al origen operativo.** Son pasos revisables y no cambian destinos:

```powershell
git -C $wt status --porcelain          # debe estar limpio (los almacenes son ignorados)
git -C $wt rev-parse HEAD              # anotar: es el punto de reversión del código
git -C $wt fetch origin
git -C $wt merge --ff-only <commit del merge publicado de esta entrega>
git -C $wt rev-parse HEAD
```

Comprobar que los SHA-256 de estos archivos coinciden con el manifiesto de la entrega:
- `backend/app/application/operacion_horario.py`;
- `backend/app/application/use_cases/operacion_automatica.py`;
- `backend/scripts/operacion_automatica.py`;
- `backend/app/infrastructure/storage/automatizacion_file_store.py`;
- `backend/scripts/windows/fase6_tarea.ps1`.

El intérprete `$py` no cambia y no hay dependencias nuevas; `pip check` debe seguir limpio. Si `merge --ff-only` no es posible, detenerse.

**1.5 Destinos y estado con el código nuevo (solo lectura).**

```powershell
& $py -m scripts.operacion_automatica --config $cfg rutas
& $py -m scripts.operacion_automatica --config $cfg estado
```

Los destinos deben ser idénticos a los de 1.1 y `horario.estado` debe valer `sin_migrar`. Leer no escribe: el SHA-256 de `configuracion.json` no cambia.

**1.6 Migrar la configuración (escritura explícita).**

```powershell
& $py -m scripts.operacion_automatica --config $cfg horario migrar --confirmar
```

Debe responder `migrada`, con `anterior` 1, `activada` y `pausada` sin cambios y `huella_plan` = `a56306a3700c8363657b1ef150dc2c0b834d5cab01be391cf1f519cd6a9e4f6b`, si la política es la propuesta inicial. Se rechaza si hay un ciclo activo.

**1.7 Plan de la tarea.**

```powershell
& $py -m scripts.operacion_automatica --config $cfg horario plan --salida "$ev\plan.json"
```

Su `huella` debe coincidir con la de 1.6.

**1.8 Sustituir la tarea en el mismo nombre (sin duplicado).**

```powershell
& $ctl -Worktree $wt -PythonExe $py -Configuracion $cfg -Evidencia "$ev\08-migrar" -PlanHorario "$ev\plan.json" -Migrar
```

El controlador hace esta secuencia:
1. vuelve a validar la versión 1 propia;
2. rechaza el cambio si hay un ciclo vivo o si otra tarea propia sobre la misma configuración o backend está activa;
3. deshabilita la tarea;
4. revalida la exportación;
5. la elimina y registra la versión 2 **deshabilitada** con el mismo nombre;
6. valida la exportación nueva disparador a disparador.

Si el registro de la versión 2 falla, restaura la exportación anterior deshabilitada e informa del error. El resultado debe ser `migrada_deshabilitada` e incluir `xml_reversion` (la exportación de la versión 1, en UTF-16LE con BOM).

**1.9 Verificación posterior (plan, XML registrado y comprobación, por separado).**
- **Plan:** `$ev\08-migrar\tarea.xml`.
- **XML registrado:** la exportación archivada por el controlador en `$ev\08-migrar\exportada-*.xml`.
- **Comprobación:** `-Estado -PlanHorario "$ev\plan.json"` debe dar `version_tarea` 2 y `habilitada` false.

Revisar en la exportación lo siguiente:
- cinco `CalendarTrigger` y ningún `LogonTrigger` ni `TimeTrigger`;
- `StartWhenAvailable` en false. El Programador puede omitir el elemento, y el diagnóstico de `-Estado` lo registra como `predeterminado_documentado`;
- la acción `ciclo --programado --plan <huella>`;
- `Get-ScheduledTaskInfo -TaskName LP6-01023009031fcabd` muestra `NextRunTime` igual a la próxima oportunidad que indica `/automatizacion`.

**1.10 Activación: decisión explícita y separada.** Solo cuando Daniel lo decida:

```powershell
& $ctl -Worktree $wt -PythonExe $py -Configuracion $cfg -Evidencia "$ev\10-activar" -PlanHorario "$ev\plan.json" -Activar
```

Observar la primera franja: consolas solo en sus slots; los juegos y motivos del panel; ninguna consola fuera de franja ni al iniciar sesión.

## 2. Reversión

En cualquier punto posterior a 1.8:

1. Ejecutar `-Pausar -PlanHorario "$ev\plan.json"` y esperar a que no haya un ciclo vivo.
2. Ejecutar `-Revertir -XmlAnterior "<xml_reversion de 1.8>" -PlanHorario "$ev\plan.json"`. El controlador solo acepta una exportación de la **versión 1 propia** de este worktree, usuario e intérprete. Esa exportación puede ser la de la tarea habilitada, y no se modifica. Lo que se registra con el mismo nombre es una copia con `Settings/Enabled=false`, validada otra vez y guardada en la evidencia (`reversion-v1-deshabilitada.xml`) antes de tocar el Programador. Así no hay ningún instante con una tarea habilitada.
   - Después de pausar la versión 2 y antes de retirarla, se comprueba otra vez que es la misma tarea propia y que no empezó un ciclo. Si empezó uno, la versión 2 queda deshabilitada, no se retira y no se registra nada.
   - Antes de retirarla se guarda también una copia deshabilitada de la versión 2 (`restauracion-v2-deshabilitada.xml`). Si falla el registro de la versión 1, se restaura esa versión 2 deshabilitada y la acción termina en error. Si fallan los dos registros, no queda tarea, nada se activa y el error cita los dos XML para restaurarla a mano.
   - Repetir la reversión sobre una versión 1 ya registrada no la reescribe (`ya_version_anterior_sin_reescribir`).
3. Restaurar `configuracion.json` desde `configuracion.v1-<fecha>.json`. El código anterior no lee la versión 2: la rechaza y no consulta.
4. Restaurar el código con `git -C $wt checkout <HEAD anotado en 1.4>`, o volver a la rama anterior.
5. Reactivar la versión 1, si se desea, con el controlador **anterior** del worktree ya restaurado (`-Activar`). El controlador nuevo se niega a activar una versión 1.

Si la reversión falla, se conservan la tarea deshabilitada y toda la evidencia; no se elevan permisos.

## 3. Rechazos garantizados por el controlador

- Tarea ajena o alterada, en cualquier campo auditado de la versión 1 o de la 2: se conserva sin cambios.
- Plan cuyo texto, huella o XML no corresponden a sus disparadores: se rechaza antes de tocar el Programador.
- Sustitución o reversión con un ciclo vivo (`Running`), comprobado también después de pausar y antes de retirar.
- Otra tarea propia **activa** sobre la misma configuración o el mismo backend. Se identifica por la marca exacta en `Source` y por los argumentos o el directorio, nunca por un prefijo del nombre. Así no se crea ni se activa un duplicado.
- Activar una versión 1: hay que migrarla antes.
- Las acciones sobre una versión 2 sin `-PlanHorario`: no se pueden verificar sus disparadores.
