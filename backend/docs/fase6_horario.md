# Fase 6: horario de consulta automática por juego

**Estado:** implementado en la entrega 9.2 sobre `9966a4bbcb8d81953fb283b07544636f4c11fc95` (merge del PR #100).

- **En Linux:** comprobado con reloj inyectado y fuentes sintéticas.
- **En Windows nativo:** validado el 26 de octubre de 2026 y aprobado por la auditoría independiente:
  - pruebas dirigidas con Windows PowerShell 5.1;
  - ensayo nativo B con el Programador de tareas real y un testigo sintético ([validación del operador](fase9_2_validacion_operador_2026-10-26.md)).
- **Tarea real:** cuando se validó, el horario no estaba aplicado a `LP6-01023009031fcabd`, que seguía con la programación anterior; su migración era un procedimiento manual posterior, separado y con reversión ([plan y procedimiento](fase6_migracion_lp6.md)). *Actualización:* Daniel migró y activó en Windows `LP6-01023009031fcabd` con el horario por juego. Como antecedente, el auditor confirmó que la captura del 27 de octubre de 2026 a las 00:11, hora de Bogotá, registraba nueve ejecuciones programadas y quince consultas en sus franjas: siete de MiLoto, tres de Baloto, tres de Revancha y dos de ColorLoto, sin duplicados ni fallos de sincronización reportados. Todas fueron sin resultados nuevos; esa captura todavía no acreditaba la incorporación de una novedad real ni la recuperación matinal con pendientes.
- **Publicación:** integrado en el PR #101 (merge `ed0ee427f7a6fcd2a33cbc538435a3df2e299710`), con sus cinco checks aprobados; antes figuraban pendientes la publicación manual y el CI del nuevo PR.

**Observación posterior (27 de octubre de 2026, 10:21, America/Bogota).** La operación real de Daniel, auditada sobre sus registros, ya acredita una novedad automática en cada juego con el horario nuevo: BALOTO y BALOTO_REVANCHA 2726 → 2727 (646 → 647 sorteos cada uno), MILOTO 629 → 630 (98 → 99) y COLORLOTO 229 → 230 (229 → 230). Cada incorporación registra sincronización `completado`, `nuevos: 1` y la siguiente predicción con explicación `guardada`: objetivos 2728 de Baloto/Revancha (28-10-2026), 631 de MiLoto (27-10-2026) y 231 de ColorLoto (29-10-2026).

Los 20 ciclos conservados contienen 33 consultas programadas (8 MiLoto, 9 Baloto, 9 Revancha y 7 ColorLoto), sin parejas juego/oportunidad repetidas ni fallos de sincronización reportados. Los 29 intentos previos sin novedad no emitieron una predicción nueva; configuración y selecciones de modelos se conservan respecto de la observación anterior. Son hechos de operación real, separados de las pruebas sintéticas de 9.3; este cierre no ejecuta ciclos ni SQL operativo.

El Programador informó último inicio **09:24:45**: no acredita un disparo exactamente a las 09:00. Los cuatro juegos ya habían terminado de actualizarse durante la madrugada; la **recuperación matinal con resultados pendientes sigue sin observarse**. Se conserva la tarea **versión 2** y su plan, sin cambios; las versiones v3/v4 de las entregas no son versiones de la tarea. La limpieza histórica sigue pendiente y no queda resuelta por esta observación. Véase [observación real del 27 de octubre](fase9_3_validacion_operador_2026-10-27.md#actualizacion-real-de-fase-6-del-27-de-octubre).

Se mantienen `experimental_no_acreditado`, AE-39 **NO-GO** y `AUTORIZA_EVALUACION = False`.

## Qué cambia y por qué

La tarea anterior (versión 1) tenía dos desencadenadores: un `TimeTrigger` que se repetía cada `PT5M` sin duración y un `LogonTrigger` incondicional. Su acción era `ciclo`, sin juego ni modo. El núcleo decidía después qué juegos estaban debidos y fuera de franja seguía consultando cada 180 minutos (`intervalo_fuera_ventana_minutos`). En la práctica se abría una consola cada cinco minutos durante todo el día: 2016 aperturas por semana más una en cada inicio de sesión.

La versión 2 coordina el Programador y el núcleo a partir de **una sola política validada** (`app/application/operacion_horario.py`):

- **Programador.** Solo dispara en los slots de las franjas y en la recuperación. Para la propuesta inicial son 122 aperturas por semana y ninguna al iniciar sesión. Se mantiene `StartWhenAvailable=false`: una oportunidad perdida no se ejecuta al encender el equipo.
- **Núcleo.** Una invocación programada solo consulta los juegos habilitados cuya franja admite esa oportunidad y cuyo evento sigue pendiente. Revalida cada juego justo antes de empezarlo.

## Calendario de sorteo y horario de consulta: dos cosas distintas

`operacion_calendario.py` describe el sorteo y **cierra la emisión** a su hora. No cambia en esta entrega. Horarios oficiales, en `America/Bogota`:

| Juego | Días | Hora |
|---|---|---|
| Baloto y Revancha | lunes, miércoles y sábado | 23:00–23:15 |
| MiLoto | lunes, martes, jueves y viernes | 22:00–22:15 |
| ColorLoto | lunes / jueves | 23:40 / 23:00 |

Fuentes: <https://baloto.com/que-es-baloto>, <https://baloto.com/miloto/que-es-miloto/> y <https://baloto.com/colorloto>.

- El repositorio las consultó el 20 de octubre de 2026 (`CONSULTA_FUENTES`, [fuentes](fase6_fuentes.md)).
- El auditor las contrastó el 25 de octubre de 2026.
- En esta entrega no se pudieron consultar de nuevo: la política de red del contenedor deniega `baloto.com` (el proxy responde 403). Las horas anteriores son las del auditor y coinciden con las del repositorio.

Son horas de sorteo, no una garantía de publicación. Se conservan la discrepancia archivada de MiLoto y las excepciones verificadas; no se inventan festivos.

El horario de **consulta** es otra cosa: decide cuándo la tarea puede *iniciar* consultas. **Empezar a consultar más tarde nunca amplía el plazo de emisión.** Por ejemplo, si el resultado del lunes de MiLoto se carga en la franja del martes a las 22:40, el sorteo del martes ya empezó a las 22:00. El estado queda en `resultado_retrasado` y no se emite para ese sorteo.

Una política solo se acepta si no contradice el calendario de sorteo (`validar_con_calendario`): cada franja nace de un día de sorteo del juego y empieza después de la hora del sorteo.

## Propuesta inicial (configurable; no instalada)

Se conserva aquí la propuesta inicial del auditor para el entorno aislado, con su encabezado histórico. La migración posterior aplicó el horario a la tarea real versión 2, como se indica en el estado anterior. No son horas oficiales de publicación. El fin cae el día siguiente.

| Juego | Día del sorteo que origina la franja | Inicio | Fin (día siguiente) |
|---|---|---|---|
| MiLoto | lunes, martes, jueves y viernes | 22:30 | 02:00 |
| Baloto | lunes, miércoles y sábado | 23:30 | 02:30 |
| Baloto Revancha | lunes, miércoles y sábado | 23:30 | 02:30 |
| ColorLoto | lunes | 23:50 | 02:30 |
| ColorLoto | jueves | 23:15 | 02:30 |

- Cadencia de 15 minutos mientras el evento esté pendiente.
- **Recuperación a las 09:00 del día siguiente** al sorteo: una sola oportunidad (09:00–09:15) y solo para el evento que siga pendiente. No es un sondeo general.

### Reglas

- La franja es `[inicio, fin)`: el inicio se incluye y el fin no. Los slots se cuentan desde el inicio de la franja; el último es el anterior al fin.
- Una franja que termina a las 02:30 pertenece al sorteo del día anterior. El martes a la 01:00, las franjas activas son las del lunes y el evento sigue siendo el del lunes.
- La política se expresa siempre en Bogotá, sea cual sea la zona del equipo. Bogotá no tiene horario de verano; si la zona dejara de tener un desfase fijo, la política se rechazaría.

### Políticas rechazadas

Se rechaza, sin volver al sondeo continuo:

- una política vacía o con claves o tipos ajenos;
- un juego o día no admitido;
- un inicio igual al fin;
- una franja de más de 12 horas;
- franjas o recuperaciones solapadas de un mismo juego;
- un intervalo fuera de 5–60 minutos.

## Admisión de una oportunidad programada (`decidir`)

Se evalúa por juego y en este orden, solo con el estado guardado (sin red ni base de datos):

1. **Fuera de horario.** Ninguna franja ni recuperación está abierta, así que no se abren recursos ni se consulta al proveedor.
2. **Intentos agotados.** Se muestra el aviso. Ni la franja ni la recuperación de las 09:00 rearman los intentos; para eso está `recuperar`, de forma explícita.
3. **Evento completo.** El último ciclo terminó «correcto» con un resultado de la fecha del sorteo o posterior. «Correcto» significa resultado validado, conciliación hecha y predicción del objetivo siguiente publicada o reutilizada. «Sin error», «ya era la hora» o «resultado encontrado» no bastan.
4. **Requiere al operador.** El último estado de *este* evento es `revision_pendiente`, `modelo_no_congelado`, `calendario_no_verificado`, `generacion_bloqueada`, `sin_corte_admisible` o `reintentos_agotados`, registrado desde el inicio de su franja. Repetir la consulta no lo resuelve, así que el evento deja de consultarse y la recuperación tampoco lo reintenta. El evento siguiente se consulta con normalidad.
5. **Oportunidad usada.** La consulta de este slot ya se hizo.
6. **Espera por fallo o `Retry-After`.** La espera progresiva y `Retry-After` fijan el primer instante permitido. El reintento ocurre en la primera oportunidad posterior a ese instante, que puede ser la recuperación o la franja siguiente.
7. **Admitido.**

Huecos (`historico_incompleto`), resultado aún no publicado (`resultado_retrasado`) y fallos de red siguen pendientes y se consultan en cada slot permitido. No se marca al día un histórico incompleto ni se resuelven discrepancias para dejar de consultar.

Si coinciden varios juegos, se consultan por hora de inicio de su franja. El jueves a las 23:20 son MiLoto (desde las 22:30) y ColorLoto (desde las 23:15); Baloto y Revancha quedan fuera.

**La franja limita inicios.** Antes de empezar cada juego se decide de nuevo con el reloj de ese momento, de modo que un ciclo iniciado a tiempo no inicia la consulta de otro juego cuyo turno ya terminó: ese juego queda `omitido_horario`. Un paso que ya está escribiendo o publicando termina con seguridad; no se mata el proceso a la hora del fin. El límite de dos horas de la tarea se mantiene.

**Confirmación en el borde de la consulta (`confirmar`; corrección v2 de F92-HOR-01).** Entre la admisión y la consulta al proveedor se abren recursos, se lee la instantánea y se congela la configuración. Justo antes de `sincronizar` se decide otra vez con el reloj de ese momento, y solo se consulta si sigue admitido el **mismo** slot de la misma ventana. Si la preparación cruzó el fin del slot admitido (cierre de la franja, cierre de la recuperación o paso al slot siguiente):
- no se inicia la consulta y el juego queda `omitido_horario`, con `horario.consulta = no_iniciada` y el motivo `cierre_antes_de_consultar`;
- no se consume el slot siguiente: su propio disparo puede consultarlo;
- se conservan la espera, el error y los fallos consecutivos anteriores;
- el evento sigue pendiente para la siguiente oportunidad permitida, que puede ser la recuperación de las 09:00.

Una consulta que empezó a tiempo continúa aunque termine fuera de franja. La comprobación manual no pasa por esta confirmación.

## Invocación programada frente a manual

| | Programada (tarea) | Manual explícita |
|---|---|---|
| Orden | `ciclo --programado --plan <huella>` | `ciclo --manual [--juego J] [--forzar]`; botón «Comprobar» del panel local |
| Caso de uso | `ciclo(programado=InvocacionProgramada(huella))` | `ciclo(origen="comando" \| "web")` |
| Franjas | Sí (`decidir`, con revalidación por juego) | No: la decide quien la pide |
| Pausa, cerrojos, espera por fallo y `Retry-After`, cierre de emisión | Sí | Sí, igual que antes |

- La etiqueta `origen` no concede ni quita nada. `origen="programado"` sin la invocación con su plan se rechaza.
- Un `ciclo` sin modo, que es la acción de la tarea versión 1, sale con código 2 y no consulta nada.
- Ninguna ruta pública fuerza el calendario: la API `/api/v1` solo tiene GET y el panel de automatización es local y está protegido.

### Códigos de salida de la invocación programada

| Código | Situación |
|---|---|
| 0 | Sin nada debido (`sin_consultas_debidas`) o éxito |
| 2 | Modo ausente o parámetros incompatibles |
| 4 | Política ausente (configuración versión 1), política inválida o huella distinta (`plan_divergente`). No consulta |
| 5, 6, 7 | Igual que antes: parcial, ocupado y fallo |

## Una sola representación: configuración, plan y concordancia

La política vive en la configuración operativa (`configuracion.json` del almacén de automatización):

- **Versión 1:** la anterior, sin horario. Se sigue leyendo tal cual y la comprobación manual funciona como antes, pero la tarea programada no consulta.
- **Versión 2:** añade `horario`, que se valida al leer y al escribir. Una versión 1 con `horario`, una versión 2 sin él o con un horario inválido se rechazan (`ValueError`); nunca se vuelve al sondeo continuo.

Leer el estado, el panel o la CLI `estado` no escribe ni migra nada; está comprobado por bytes. La migración es una escritura explícita:

```powershell
python -m scripts.operacion_automatica --config "<arranque.json>" horario migrar --confirmar
python -m scripts.operacion_automatica --config "<arranque.json>" horario plan --salida "<archivo-nuevo.json>"
```

- `migrar` exige que no haya un ciclo vivo y no cambia `activada` ni `pausada`. Es idempotente: si la política ya es la misma, responde `reutilizada`.
- `plan` es solo lectura y escribe un archivo nuevo (no sobrescribe).

El plan (`plan_windows`) agrupa las franjas con el mismo inicio y duración en `CalendarTrigger` semanales. `StartBoundary` lleva el desfase fijo de Bogotá (`-05:00`) desde el lunes 5 de enero de 2026, de modo que la huella no depende de hoy. Además:

- la duración de repetición acaba un minuto después del último slot, así que el fin exclusivo no dispara;
- hay un disparo de recuperación a las 09:00 en los días siguientes a algún sorteo (martes a domingo).

El texto canónico del plan, con la propuesta inicial:

```text
LP6-HORARIO/1|America/Bogota
franja|2026-01-05T22:30:00-05:00|Monday,Tuesday,Thursday,Friday|PT15M|PT3H16M
franja|2026-01-05T23:15:00-05:00|Thursday|PT15M|PT3H1M
franja|2026-01-05T23:30:00-05:00|Monday,Wednesday,Saturday|PT15M|PT2H46M
franja|2026-01-05T23:50:00-05:00|Monday|PT15M|PT2H31M
recuperacion|2026-01-05T09:00:00-05:00|Tuesday,Wednesday,Thursday,Friday,Saturday,Sunday|-|-
```

Su SHA-256 es la **huella del plan**: `a56306a3700c8363657b1ef150dc2c0b834d5cab01be391cf1f519cd6a9e4f6b`. Se verifica en tres puntos:

1. **El script `fase6_tarea.ps1`** recompone el texto a partir de los disparadores del plan y comprueba la huella y el XML. Pone `--plan <huella>` en la acción de la tarea y en su huella de vinculación. Tras registrar la tarea, verifica la exportación disparador a disparador.
2. **El núcleo** recalcula la huella a partir de la política vigente en cada invocación programada y rechaza cualquier otra. Si la política cambia después de registrar la tarea, la tarea deja de consultar hasta que se registre el plan nuevo.
3. **Las pruebas** simulan los disparos del plan durante dos semanas y comprueban que coinciden, slot a slot, con las oportunidades del núcleo, sin disparos de más ni de menos. Esta simulación no acredita el Programador real.

**En el Programador real** (ensayo nativo B, 26 de octubre de 2026, con un testigo sintético):

- se registró el plan con sus cinco `CalendarTrigger`;
- el testigo recibió `ciclo --programado --plan` con esta huella;
- el siguiente inicio que informó el Programador coincidió con el calculado a partir del plan: el lunes a las 22:30 de Bogotá.

El único inicio fue manual. No se observó un disparo automático futuro ni un ciclo del producto con datos reales ([validación del operador](fase9_2_validacion_operador_2026-10-26.md)).

## Consolas que siguen apareciendo

La versión 2 **no suprime todas las ventanas de consola**: elimina las de fuera de horario. Con la propuesta inicial, cada semana se abren 122 consolas breves:

- en cada slot de las franjas, cada 15 minutos. Cuando varias franjas se solapan con rejillas distintas se abren más: el lunes, la de ColorLoto empieza a las 23:50 y la de MiLoto y Baloto va a :00/:15/:30/:45;
- a las 09:00 de martes a domingo.

Después de completarse todos los juegos de una franja, sus slots restantes **siguen abriendo una consola breve**. El proceso lee el estado, ve que el evento está completo y termina sin consultar la red ni abrir recursos, en uno o dos segundos. Lo mismo ocurre en la recuperación de las 09:00 cuando no queda nada pendiente. No hay consolas fuera de las franjas y de la recuperación, ni al iniciar sesión. Suprimir también esas aperturas exigiría un servicio permanente, un bucle de espera o reescribir la tarea desde el producto, y quedan fuera de alcance por diseño.

## Disponibilidad frente a horario estricto

Con el equipo apagado, suspendido o sin sesión en una franja o en la recuperación, esa oportunidad se pierde:

- `StartWhenAvailable=false` evita que se ejecute al encender;
- el núcleo rechaza cualquier hora fuera de horario;
- tampoco hay disparo al iniciar sesión.

El pendiente se conserva hasta la **siguiente oportunidad permitida**, normalmente la franja del sorteo siguiente. La sincronización incremental carga entonces todos los resultados que falten. Si un resultado se carga tarde, la emisión para el sorteo que ya empezó queda bloqueada (`resultado_retrasado`), y esa predicción se pierde. Es el precio de no ejecutar a horas arbitrarias. Una comprobación manual (`ciclo --manual`) sigue disponible para quien decida recuperar antes.

Al reanudar a mitad de franja solo cuenta el slot vigente: se hace una consulta, sin ponerse al día con los slots perdidos.

## Zona del equipo y excepciones

- **Núcleo.** Convierte el reloj inyectado a Bogotá con `ZoneInfo` y no usa la zona del equipo. Está comprobado con `TZ=Asia/Tokyo` y con instantes con otro desfase.
- **Plan.** Lleva `-05:00` en cada `StartBoundary`. El ensayo nativo B se hizo con la zona `SA Pacific Standard Time`, que tiene el mismo desfase que Bogotá, y `NextRunTime` coincidió con el plan. Queda pendiente verificar en Windows real cómo evalúa el Programador los días de la semana cuando la zona del equipo tiene otro desfase. La guarda del núcleo impide consultas fuera de franja aunque el Programador dispare en otro momento.
- **Excepciones de calendario.** No mueven las franjas, que son semanales. Afectan al cierre de emisión como antes: una excepción verificada fija el plazo y una sin verificar bloquea la emisión (`resultado_retrasado`, con el motivo «no está verificado»). Un sorteo extraordinario en un día sin franja se carga en la franja siguiente o con una comprobación manual.

## Panel local

`/automatizacion` añade «Horario de consulta automática», que solo lee y no consulta ni escribe:

- el estado de la política (`valida`, `sin_migrar` o `no_valida`);
- por juego: si el núcleo lo tiene habilitado o deshabilitado, sus franjas (hora de Bogotá, con «día siguiente»), el motivo de espera, la próxima oportunidad (franja o recuperación) y la huella del plan.

No hay administración de tareas desde React ni un endpoint público de escritura.

## Comprobaciones

| Archivo | Qué comprueba |
|---|---|
| `tests/unit/test_fase6_horario.py` (65) | Política, admisión con reloj inyectado (incluidos todos los casos del encargo), ciclo programado con proveedor sintético, panel, CLI, plan y su concordancia |
| `tests/unit/test_fase6_horario_regresiones.py` (5) | Fallan sobre la base por el comportamiento señalado por el auditor; pasan con el parche |
| `tests/unit/test_fase6_auditoria_v1.py` (12) | Regresiones de la auditoría v1. Fallan sobre v1 y pasan con la v2: cierre de franja, de recuperación y cambio de slot durante la preparación; el slot siguiente no se consume; la espera se conserva; controles con demora dentro del slot y manual; y la guarda estática contra variables de PowerShell que solo difieren en mayúsculas |
| Baterías de PowerShell (`test_fase6_tarea_windows.py`, `test_fase6_xml_windows.py`, `test_fase6_exportacion_windows.py`, `test_fase6_ensayo_limpieza_windows.py`) | Necesitan PowerShell (`LOTERIA_POWERSHELL`, `powershell` o `pwsh`); sin él se omiten. En Linux se ejecutaron con PowerShell 7.6.9 y 7.4.22 portátiles, con la identidad y los cmdlets del Programador simulados. En Windows PowerShell 5.1.26100.9711 dieron 121 casos únicos aprobados, por consolidación de dos corridas: 117 de la revalidación sobre v3 y 4 revalidados sobre v4. Falta su ejecución en el CI del nuevo PR |

Las dos primeras están en la selección Windows. PowerShell de Linux con cmdlets simulados no acredita el Programador, COM, permisos ni ventanas de Windows. Esos puntos los cubrió, para un testigo sintético, el ensayo nativo B. Allí aparecieron y se corrigieron dos hallazgos:

- **F92-NAT-01** (v3): el Programador omite `StartWhenAvailable` al exportar su predeterminado `false`. El controlador toma esa omisión como el predeterminado documentado, nunca como el valor esperado.
- **F92-TEST-01** (v4): incompatibilidad de un ayudante de prueba con Windows PowerShell 5.1.
