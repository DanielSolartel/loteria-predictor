# Fase 6 v3.4 — validación operativa en Windows

Fecha de revisión: **23 de octubre de 2026**, zona `America/Bogota`.

## Estado y alcance

La prueba operativa de incorporación automática de novedades queda verificada para **MiLoto y ColorLoto**. El Programador invocó la CLI, la operación incorporó un nuevo sorteo por juego y guardó la siguiente cartera con su explicación usando la configuración registrada que ya había elegido el operador. Las capturas de observación fueron de solo lectura y declararon cero ciclos manuales.

La tarea y el núcleo permanecen habilitados. Esta actualización documental prepara la publicación manual; no registra un commit, no acredita todavía un PR/merge ni nuevos resultados de Actions. El issue de UI #93 queda separado y pendiente.

Baloto y Baloto Revancha figuran correctos con último sorteo #2725 y objetivo #2726. Estas capturas no acreditan una incorporación nueva en esos dos juegos.

## Resultados observados

Horas locales de Colombia del **23 de octubre de 2026**:

| Juego | Ejecución operativa | Nuevo resultado | Histórico antes → después | Cartera y explicación siguientes | Finalización |
|---|---|---:|---:|---:|---|
| MiLoto | `20261023T051451Z-f3694141` | #628, fecha 2026-10-22 | 96 → 97 sorteos | #629, fecha objetivo 2026-10-23 | 00:15:16 |
| ColorLoto | `20261023T061453Z-489bb98c` | #229, fecha 2026-10-22 | 228 → 229 sorteos | #230, fecha objetivo 2026-10-26 | 01:15:25 |

Ambas sincronizaciones registran `completado`, un sorteo nuevo, cero fallidos, cero huecos y ninguna revisión pendiente. Los pasos posteriores incluyen actualización de Resultados/Fiabilidad, admisibilidad temporal y `prediccion_explicada` con estado `exito`, cartera `terminado` y explicación `guardada`.

Los informes conservan sus limitaciones: MiLoto y la comparación retrospectiva de ColorLoto indican falta de muestra común. La persistencia correcta de un informe no elimina esa limitación estadística.

### Selecciones conservadas

| Juego | Modelo registrado | Corte de entrenamiento | Versión de configuración |
|---|---|---:|---:|
| Baloto | `markov_apariciones` | 2717 | 3 |
| Baloto Revancha | `lightgbm_binario` | 2717 | 2 |
| MiLoto | `red_neuronal_binaria` | 619 | 2 |
| ColorLoto | `bayes_jerarquico_pares` | 222 | 2 |

Las selecciones coinciden entre las capturas examinadas. La operación reutilizó los estimadores registrados; esta revisión no ejecutó entrenamiento ni cambió las selecciones.

## Programador y código de salida

La captura final, a las **01:40:29**, informa tarea `LP6-01023009031fcabd` habilitada, estado `Ready`, último inicio 01:39:47 y último resultado **0**. El núcleo permanece `habilitada`; los cuatro juegos están `correcto`, sin avisos en el panel ni revisiones pendientes.

La captura anterior informaba último resultado **5**. Se cotejó la CLI con la huella Windows, admitiendo exclusivamente la representación LF/CRLF: el programa devuelve 5 para `estado == "parcial"`. El registro de esa invocación contiene únicamente ColorLoto en `resultado_retrasado`, con `error: null`. Por tanto, ese código corresponde al estado parcial del producto, no constituye por sí solo un diagnóstico del sistema operativo.

Las ejecuciones guardan `origen: "comando"` porque el Programador utiliza la CLI del producto. Ese campo se conserva tal como fue registrado; no se reetiqueta como una fuente de procedencia distinta.

La tarea requiere equipo encendido, despierto y sesión iniciada. La interfaz y Uvicorn no son el planificador. Los intervalos operativos por juego y las esperas pueden ser mayores que los cinco minutos del desencadenador Windows.

## Conservación y aviso de los HTML

En la captura final constan **611 archivos inventariados**, frente a 542 en la referencia de activación: **69 archivos nuevos**. Los cuatro estados operativos son mutables.

El aviso de conservación se mantiene y se explica: cambiaron las huellas de **doce HTML anteriores**, `html/miloto_616.html` a `html/miloto_627.html`. La reconciliación vuelve a consultar hasta doce resultados existentes; el conector guarda su respuesta mediante `HtmlFileStorage.guardar`, que escribe en la misma ruta. Las diferencias se identificaron en los inventarios. No se dispone en estos ZIP del contenido anterior y posterior de esos HTML para atribuir el cambio a una parte concreta de la página.

Por ello **no se afirma conservación byte a byte de todos los archivos previos** ni se elimina el aviso del recolector. Las copias HTML anteriores sí cambiaron. Los históricos canónicos previos de PostgreSQL, las selecciones/modelos, las carteras y los demás artefactos previos fuera de esos HTML y estados operativos conservan las huellas comprobadas en las capturas.

La comparación entre las dos últimas capturas detecta solo un estado operativo modificado (ColorLoto), nueve archivos nuevos y ningún archivo desaparecido. Las doce huellas HTML de MiLoto no volvieron a cambiar entre esas dos capturas. Los controles protegidos de índice Git, `.env`, arranque, scripts operativos y `.gitignore` coinciden entre capturas; no se incluye el contenido de `.env`.

## Evidencias y verificaciones

| ZIP del operador | Bytes | SHA-256 |
|---|---:|---|
| `f6-observacion-7762dbe5.zip` | 169990 | `9be628c5043a29321509162d81d20589ac5915eeeed885a49a45dbaffaa2fee6` |
| `f6-observacion-bb7a737c.zip` | 185924 | `da1c625efd209ea17489aaf2e7e32ecdb264022149f88492d1ef188b362a6163` |
| `f6-observacion-239bf889.zip` | 190376 | `25752e27622b63277130a31f893e11d93116dc8990f6eff741040741527711c8` |

La revisión verificó bytes, SHA-256, CRC y rutas de los ZIP; coherencia entre registros, estados e inventarios; conservación de los controles; y diferencias entre capturas. La evidencia operativa procede de Windows, aportada por el operador. El revisor no ejecutó esos ciclos desde Linux, no abrió la BD del usuario ni deserializó estimadores para esta revisión.

Las cifras anteriores de pruebas conservan su versión y atribución. La suite completa Windows v3.1 y las dirigidas v3.2/v3.3 no se presentan como una nueva suite ejecutada durante este cierre documental. El ensayo nativo aislado `f6-tarea-v33-7f1a7164` consta aprobado, con limpieza completa de su propio testigo; eso no demuestra la limpieza de otros restos históricos.

## Pendientes separados

1. Verificar el estado y el contenido público del worktree `feature/fase6-operacion-automatica`, aplicar este cierre documental y preparar la selección explícita del commit.
2. Publicar manualmente la rama y el PR; revisar sus Actions antes del merge. `main` y `develop` seguían en `2ac4d110b7d721e544f5588e9754230eef28184d` al preparar esta documentación.
3. La limpieza de las tareas/raíces históricas mencionadas en las guías anteriores no queda acreditada por las capturas de observación. Conservar ese pendiente por separado hasta verificar existencia, propiedad, ausencia de ejecución y retirada.
4. El issue #93 de desbordamiento móvil conserva su entrega independiente y revisión en Windows pendiente; no se incorpora a este cierre.

Se mantienen `experimental_no_acreditado`, AE-39 **NO-GO** y `AUTORIZA_EVALUACION = False`. La anterioridad operativa y la incorporación automática no constituyen acreditación prospectiva de ventaja. Las fases 7–11 continúan con su planificación propia.

Los protocolos de las entregas anteriores se conservan como antecedentes. Sus instrucciones de aplicar, activar o ensayar no se repiten por rutina al preparar este commit. El recolector de observación existente fija HEAD, rama e índice previos; después de un commit puede rechazar su referencia antigua. Ese rechazo requiere actualizar la referencia mediante una nueva revisión, no forzar o alterar sus controles.

## Adenda del 23 de octubre de 2026 (posterior a la publicación)

Este registro se conserva como se redactó al prepararse la publicación manual. Después:
- PR #96 se integró (merge `fcadea6a08e8e6b52386a9055be16bb1873b9a29`; Actions `39939306600`, `push`, aprobado);
- PR #97 cerró el issue #93 (merge `605afe8c2bb3b38d0fa3abdb6a5d14ba2002b5a6`; Actions `40020240159` del PR y `40023629982` del merge, informado correcto en Linux y Windows por el operador).

Las frases «no acredita todavía un PR/merge» y «#93 pendiente» describen el estado de entonces. Sigue pendiente la limpieza verificable de restos históricos y la comprobación específica en Google Chrome de Windows del arreglo #93; el resto de salvedades no cambia.
