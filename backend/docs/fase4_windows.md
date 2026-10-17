# Fase 4 en Windows: predicciones explicables y fiabilidad observada

**Cierre local v3.4 (16 de octubre de 2026, Colombia).** La implementación y la validación local están completadas con los alcances del resumen consolidado aportado. Daniel ejecutó Windows nativo; Codex Cloud ejecutó Linux con datos sintéticos; ChatGPT auditó los archivos y la evidencia entregada y registró su revisión previa de PDF y capturas, que no están incluidos en los ZIP de este cierre. Este cierre documental no vuelve a ejecutar esas verificaciones ni convierte una auditoría en pruebas nuevas.

**Windows nativo v3.4, ejecutado por Daniel:** Windows 11 AMD64, Windows PowerShell 5.1, Python 3.14.6 y pytest 9.1.1. Focal **198 aprobadas**; regresiones: Fase 3 **81**, Producto 6 **73**, Producto 5 **96**, Producto 4 **94**, Fase 5 **94** y Productos 1–3 **229**. Demostración con datos sintéticos **8/8** y `pip check` correcto. ConEnlaces terminó con **217 aprobadas** en `fase4_sin_publicacion` y **2432** en `seleccion_windows_sin_publicacion` (100 entradas), sin fallos, errores ni omisiones; OpenSSL `exigir` **7/7** en el JUnit de esa selección. Consta el aviso conocido Starlette/httpx. Estas dos baterías son **reducidas**: excluyen las tres familias de publicación v3.3 y no equivalen a nuevas ejecuciones de toda Fase 4, de la selección completa ni de la suite completa Windows. Los grupos se solapan y no se suman. La bandera `validacion_completa: true` de `ConEnlaces/resumen.json` indica progreso del script; no acredita una ejecución completa nativa.

**Publicación nativa conservada de v3.3:** Daniel validó **82 aprobadas** en NTFS con `SetFileInformationByHandle(FileRenameInfoEx)`, clase **22**, flags **3**. La prueba real completó **120 publicaciones** con lectores en hilos y otro proceso, sin lecturas parciales, y verificó el destino retenido por otro proceso. Los cinco archivos de ese mecanismo permanecen byte-idénticos en v3.4; es evidencia nativa de **v3.3**, no una ejecución nueva de v3.4.

**Recorrido real y reproducción.** Daniel recuperó Baloto reutilizando la cartera publicada y completando su explicación en una ejecución nueva; conservó los registros fallidos y el temporal original, sin promocionarlos ni reescribirlos. Las cuatro emisiones de tres combinaciones y Baloto de cinco persistieron tras el reinicio, con integridad, reproducción exacta e importancias disponibles y páginas terminadas sin sondeo. Pedir cinco conservó en tres la configuración vigente; repetir Baloto de tres reutilizó cartera y explicación y añadió únicamente los dos registros de ejecución. La reproducción comprueba la huella del **vector fuente**, recalcula **rankings y variables** y los compara con la explicación guardada. La integridad de esta explicación cubre las importancias guardadas y la referencia SHA-256 del estimador. El cotejo directo del archivo del estimador se hace al emitir la explicación; la reproducción de una consulta GET **no lo abre ni lo carga, no ejecuta una nueva inferencia ni recalcula las importancias**.

**Instantáneas distintas, consultas de solo lectura.** Los PDF y las primeras **seis consultas de API** corresponden a la base anterior: **219 archivos** intactos antes/después; ChatGPT contrastó además 68 medias y límites con los PDF. Antes del último bloque se añadieron **12 archivos**, conservando los 219 originales: nueve HTML, un registro de operación y dos archivos de un pronóstico de ColorLoto. El primer intento del ayudante de parámetros se detuvo por su guarda, con cero consultas y 231 archivos intactos; se corrigió solo el ayudante. Las últimas **60 consultas**, sobre la base actualizada, dieron **28 HTTP 200 y 32 HTTP 422 esperados** en API y web: parámetros vacíos equivalentes a ausentes, GET repetidos idénticos, corte y selección conservados y rechazos de valores inválidos. Sus tres inventarios de **231 archivos** coinciden, sin alterados, ausentes ni nuevos; se verificó la cadena **219 → 231 → 231** y la conservación de los tres archivos del fallo original. No se exige igualdad de cifras o pendientes entre fechas. ChatGPT auditó JSON, huellas, formularios extraídos e inventarios; el último ZIP no incluye cada cuerpo HTML completo.

**Pantalla e impresión nativas revisadas.** Daniel produjo los PDF con Chrome 155/Windows y ChatGPT inspeccionó **27 PDF principales, 203 páginas**, en Carta vertical, Carta horizontal y A4 vertical: 15 predicciones (139 páginas) y 12 Fiabilidad (64). Las cinco predicciones conservan todas sus combinaciones en la primera página; se revisaron tablas, cabeceras, gráficas, avisos y trazas sin pérdidas ni solapamientos detectados. Un PDF de Fiabilidad Baloto uniforme, Carta vertical de **ocho páginas**, se revisó aparte y no se suma a los 27/203. Los multiconjuntos de cifras coinciden entre formatos como contraste auxiliar, sin validar el vector completo de API; las dimensiones del PDF no prueban la escala del diálogo. También se revisaron el formulario con corte 2719/línea uniforme y ColorLoto `pares`. La muestra estrecha Baloto de cinco, **390 × 648 píxeles CSS**, fue legible en los elementos inspeccionados, con desplazamiento horizontal de la tabla; es representativa, no exhaustiva de los cuatro juegos. Este cierre usa esa auditoría aportada y no vuelve a inspeccionar PDF ni capturas.

**Linux sintético, ejecutado por Codex Cloud:** suite completa **6759 aprobadas**, selección filtrada **2514**, sin fallos, errores ni omisiones; OpenSSL `exigir` **7/7 en ambos JUnit**, demostración **8/8** y `pip check` correcto. Se registraron seis avisos en la suite y uno en la selección. La comparación sintética propia de **54 PDF**, 473 filas y 207 grupos pertenece a Cloud/Linux; no se atribuye a Daniel, a Windows real ni a pruebas ejecutadas por ChatGPT. La auditoría separada de ChatGPT comprobó paquete/manifiestos, aplicación y reversión, contenido/espacios del incremental, sintaxis y controles estadísticos directos sin repetir la suite completa.

**v3.4** corrige el corte vacío y la selección persistente de Fiabilidad, el componente real de ColorLoto, la lectura numérica cerca de cero, el texto de MiLoto y el singular/plural, y la disposición de pantalla e impresión. Mantiene las probabilidades congeladas, las unidades por balota, las multiplicidades y las consultas de solo lectura. Añadir una línea sigue siendo aditivo y no modifica la configuración. La superbalota de `carteras:uniforme-v1` conserva su estrategia de frecuencia con suavizado de Laplace; el nombre de la línea no implica deltas nulos en todos sus componentes.

**Siguiente paso: cierre exclusivamente documental.** Aplicar `aplicar-fase4-cierre.ps1` en Windows PowerShell 5.1, consola normal, siguiendo `fase4-guia-cierre-windows.md`; verifica código y manifiestos y aplica únicamente los cuatro documentos. No requiere repetir pruebas, demostraciones, entrenamiento, generación, recuperación ni consultas o revisión visual. Daniel realizará después commit, push y PR desde Windows. Permanecen **pendientes separados** GitHub Actions sobre el PR final, la **suite completa nativa Windows** y la **acreditación prospectiva** con muestras suficientes por línea y tipo. La implementación y validación local completadas no acreditan ventaja predictiva: siguen `experimental_no_acreditado`, AE-39 **NO-GO** y `AUTORIZA_EVALUACION = False`.

Esta guía usa el equipo del operador:

- worktree de la Fase 4: `C:\GitHub\loteria-predictor-fase4`, rama
  `feature/fase4-predicciones-explicables`;
- intérprete: `$env:LOCALAPPDATA\loteria-predictor-venvs\ae68\Scripts\python.exe`;
- puerto sugerido: **8007** (la Fase 3 puede seguir en 8006).

El cierre vigente se aplica con `aplicar-fase4-cierre.ps1` y se documenta en
`fase4-guia-cierre-windows.md`; su manifiesto compara los 52 archivos antes y
después y conserva los otros 48 byte a byte. No consulta la app ni los almacenes.
Los paquetes anteriores se conservan intactos. La cadena histórica y sus
guías externas utilizan los scripts: `aplicar-fase4-windows-v2.ps1` (v2 completa sobre la
base), `continuar-fase4-windows-v3.1.ps1` (incremental v3.1 sobre v2) y
`continuar-fase4-windows-v3.2.ps1` (incremental sobre v3.1) y
`continuar-fase4-windows-v3.3.ps1` (incremental sobre v3.2) y
`continuar-fase4-windows-v3.4.ps1` (incremental directo sobre v3.3 exacta). Este documento forma parte del parche, así que no repite esas cifras.

## Qué corrige v3.4

- Fiabilidad acepta `hasta=` como ausencia de límite tanto en web como en API;
  una entrada no vacía inválida, cero o negativa conserva su error. El formulario
  mantiene corte y línea consultada. Añadir otra línea sigue siendo aditivo,
  sin cambiar la configuración ni eliminar sus líneas.
- ColorLoto clasifica la receta como pares número-color según el serializador
  real. El contraste sintético previo de 47 objetivos comprobó que renombrar
  también el token de la semilla cambiaría los intervalos Monte Carlo aunque
  las medias siguieran iguales. La respuesta identifica la clasificación
  `fase4-componentes-receta-2` y el token histórico `numeros` conservado solo
  para esa semilla de receta; se mantiene `fase4-fiabilidad-1`, las series,
  medias e intervalos, sin modificar informes ni probabilidades guardadas.
- Un residuo con magnitud hasta `1e-12` se describe como próximo a cero,
  conservando su signo. Es un criterio de lectura, no de igualdad ni de
  significación estadística. Todo valor no nulo menor que `0.00005` en magnitud
  se presenta con cinco cifras significativas; los restantes, con cinco
  decimales. Media y límites originales siguen en los datos y la pertenencia
  de cero al intervalo usa sus límites originales. Se aplica el mismo
  criterio a pérdidas y aciertos observados menos esperados. La superbalota
  uniforme conserva su estrategia separada de frecuencia con Laplace.
- MiLoto deja de mencionar superbalota; Baloto/Revancha la mantienen aparte
  y ColorLoto mantiene sus pares y multiplicidades. Fiabilidad distingue
  «1 sorteo» de «2 sorteos».
- La impresión prioriza la sugerencia junto al corte y objetivo, separa las
  cifras SVG de la referencia uniforme y mejora la fragmentación y el espacio
  de los metadatos. Conserva combinaciones, valores, tablas, avisos y trazas.

El detalle histórico de las regresiones y de la reproducción de pantalla e
impresión sintéticas está en `fase4-guia-windows-v3.4.md`. La revisión nativa
posterior de Daniel y la auditoría de ChatGPT constan arriba, con su propio
alcance; la evidencia sintética no se atribuye a Windows.

## Qué añade

- **Centro de predicciones** (`/predicciones`, «Centro de predicciones» en la
  navegación). Por juego muestra:
  - la configuración elegida en Carteras y su versión registrada, con su
    compatibilidad;
  - los cortes de entrenamiento y de entrada, el objetivo, la generación, la
    integridad y la frescura;
  - las combinaciones con su papel («sugerencia del modelo» o «línea
    muestreada»);
  - los fuertes y débiles, con sus unidades y denominadores, y la explicación;
  - la fiabilidad observada con su incertidumbre;
  - la proyección a la tabla `predicciones`, que no se escribe;
  - los enlaces a la cartera original, la ficha de la versión y los resultados
    observados.
- **Un solo caso de uso** para la web, la API y el comando. Generar usa el
  caso de uso de Producto 5 con la configuración vigente: mismo cerrojo, misma
  identidad y misma reutilización. Una versión registrada se recarga sin
  reentrenar, con las comprobaciones de la Fase 3. El centro nunca cambia de
  modelo por su cuenta.
- **Explicación** versionada e inmutable en `storage\predicciones`. Con una
  versión registrada incluye las importancias o coeficientes **globales** de
  su estimador, leídos en el proceso trabajador con la carga restringida. En
  los demás casos dice por qué no hay importancias.
- **Fiabilidad**: probabilidad emitida, rendimiento observado e incertidumbre
  por separado, con bootstrap de bloques móviles sobre la serie de sorteos.
  No hay etiquetas alta/media/baja.

## Qué escribe y qué no

| Acción | Escribe en |
|---|---|
| `predicciones generar` / «Generar con la configuración» | `storage\carteras` (cartera, si la entrada es nueva) y `storage\predicciones` (explicación y registro del paso) |
| `predicciones generar --cinco` / «Generar cinco combinaciones» | Lo mismo, en la línea `…-n5-…`; la configuración no cambia |
| `predicciones explicar` / «Explicar esta emisión» | `storage\predicciones` (explicación, si no existía) |
| `carteras_modelos configurar` (paso opcional 3.2) | `storage\carteras` (versión nueva de la configuración) |

Generar con una **receta no registrada** la ajusta al generar, igual que en
Producto 5. Con una versión registrada no se ajusta nada.

`indice`, `consultar`, `fiabilidad`, `ejecucion`, `rutas`, la API y todas las
páginas de consulta no escriben (tampoco al mostrar interrumpida una
generación sin trabajador: eso se deriva al leer). Ninguna orden importa sorteos, entrena una
versión registrada ni escribe en PostgreSQL. La tabla `predicciones` de la
Fase 1 queda reservada: la página muestra su proyección, y la fuente canónica
es el almacén inmutable (cartera y explicación).

## Validación real de la v2 y correcciones conservadas

**Lo que pasó en Windows con la v2** (Python 3.14.6, consola normal de
PowerShell, Uvicorn sin `--reload`):

1. Configuración de Baloto v1: `random_forest_clasificador`, versión
   registrada v1 (`05d1ae7f…`) entrenada hasta 2714, 3 combinaciones,
   diversidad libre, semilla 42. Entrada: 640 sorteos, corte 2720, objetivo
   2721. Ejecución `20261013T135713Z-dc2deb60`.
2. Carteras publicó la cartera `adce8ea74e670829…` (línea
   `random_forest_clasificador-v1-reg1-n3-libre-s42`) y, al registrar el
   juego como terminado, `os.replace` falló con `PermissionError [WinError 5]`
   (`carteras.py`, línea 278; `operacion_file_store.py`, línea 112). El hilo
   murió.
3. Quedaron el temporal `.20261013T135713Z-dc2deb60.8601c0ff.tmp` (juego
   terminado; estado global todavía `en_curso`), el JSON definitivo con el
   estado anterior (`en_curso`, fase `construccion`) y el registro del centro
   `en_curso` (fase `cartera`, sin cartera ni explicación).
4. La página mostraba «Interrumpido.» con «cartera: en curso» y «Explicación:
   pendiente», y seguía consultando cada 2 s indefinidamente.

**Alcance de la evidencia.** El log confirma `WinError 5` en `os.replace`, pero no identifica al actor que bloqueó la sustitución. En Windows, un archivo abierto sin `FILE_SHARE_DELETE` puede impedir ese reemplazo; la consulta del servidor, el antivirus o el indexador son hipótesis, no causas demostradas. La v2 no reintentaba los bloqueos transitorios admitidos por el diseño, y el centro no manejaba la excepción ni sabía si su generación seguía viva.

**Qué conserva y corrige la v3.1:**

- **Publicación del progreso** (registro de ejecuciones compartido por
  Productos 3 y 5, el laboratorio y el centro): sigue siendo un temporal
  completo con `flush` y `fsync` y un reemplazo atómico. Los bloqueos
  transitorios de Windows (WinError 5, 32 y 33) se reintentan con esperas
  crecientes y acotadas (10 s en total). Un destino de solo lectura o que es
  una carpeta, y cualquier otro error, se propagan al primer intento. Si no se
  publica, el temporal se borra y el JSON definitivo conserva su último
  estado; nunca se escribe sobre él. El publicador no necesita privilegios de administrador.
- **Recuperación de Predicciones:** cada generación toma su propio cerrojo
  hasta terminar, incluida la explicación. Una excepción de Carteras cierra
  el registro del centro como `fallo`, con su motivo. Una generación «en
  curso» sin trabajador se muestra interrumpida al leerla, sin escribir, y la
  página deja de consultar. Mientras la explicación sigue activa, no se
  declara interrumpida aunque Carteras ya haya terminado.
- **Conservación:** la cartera publicada antes del fallo se busca y se valida
  en el almacén de Carteras. Repetir la misma entrada la reutiliza y completa
  su explicación, sin reentrenar, sin reescribirla y sin otra versión.

**Evidencia que se conserva tal cual:** el temporal no se promociona (su
estado global sigue `en_curso`) ni se borra; los tres registros originales
tampoco se reescriben. Ninguna orden de esta guía los modifica.

## Fallos nativos de v3.2 y corrección del escritor en v3.3

El diagnóstico nativo de Daniel corresponde a Windows PowerShell
5.1.26100.9711, Python 3.14.6, pytest 9.1.1, Windows
11-10.0.26200-SP0, AMD64 y consola elevada del mismo usuario, con Uvicorn
detenido. El enlace sintético se creó correctamente. La v3.2 exacta tenía
45 archivos cambiados, 27 nuevos y 18 modificados, sin commits posteriores ni
cambios preparados; 44 archivos contenían CRLF. La evidencia está en
`%TEMP%\f4v32-evidencia-20261015-002600-0be31c45` y en el diagnóstico
exportado, que no contiene `.env` ni los almacenes reales.

JUnit terminó con **116 aprobadas y 2 fallidas, sin errores ni omisiones**
en 37,79 s, código 1. Fallaron
`test_concurrencia_real_lectores_en_hilos_y_en_otro_proceso_mientras_se_publica`
y el control de handle externo retenido `[cooperante]`. Normales v3.2,
selección y OpenSSL no se ejecutaron en esa invocación. Los 667 verdes de
Normales v3.1 y los verdes Linux v3.2 no validan este nuevo escritor.

La concurrencia completó **2 de 120 publicaciones**: el intento `n = 3`
falló con WinError 5 en `os.replace`, con **45 reintentos acumulados** en el
tramo observado, no medidos exclusivamente para ese intento. El tramo de
publicación duró 10,032593 s; el total, 11,318169 s. Los tres hilos hicieron
34528, 34488 y 34506 lecturas; el proceso externo, 58894. Todos leyeron
estados coherentes y ordenados, sin errores, hasta `n = 2`; terminaron los
hilos y el proceso, este con salida 0 y stderr vacío. El fallo fue del
escritor, no una excepción de esos lectores.

El handle cooperante retenido impidió publicar: 0 publicaciones, 43
reintentos y **9,81 s de reloj simulado**, frente a **1,452861 s reales**.
El hijo cerró su handle, terminó sin errores y el JSON conservó `n = 0`.
El control ordinario fue un negativo aprobado con 0 publicaciones. El
bloqueo externo liberado al observar un reintento sí permitió publicar tras
un reintento. La evidencia no identifica antivirus ni permisos como causa;
la consola ya estaba elevada y crear enlaces funcionó.

### El lector cooperante y la primitiva de renombrado cumplen tareas distintas

Se conserva la apertura del lector con `CreateFileW` y
`FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE`, necesaria para
cooperar con el renombrado. Compartir eliminación no borra al cerrar y no
garantiza por sí solo que cualquier escritor pueda reemplazar un destino
abierto. En CPython 3.14.6, `os.replace` usa
`MoveFileExW(MOVEFILE_REPLACE_EXISTING)`. La limitación de ese reemplazo del
destino abierto concuerda con el control nativo cooperante fallido de v3.2.
La explicación primaria de CPython #90161 distingue origen y destino; no
convierte una fuente documental en una ejecución del kernel Windows.

La v3.3 cambia el escritor de Windows a `SetFileInformationByHandle`, clase
**Win32 `FileRenameInfoEx = 22`**, con
`FILE_RENAME_FLAG_REPLACE_IF_EXISTS | FILE_RENAME_FLAG_POSIX_SEMANTICS` (1 | 2).
No mezcla esa enumeración con la clase de información del kernel. La
semántica permite reemplazar el nombre mientras un lector cooperante termina
de leer el objeto anterior; las nuevas aperturas deben resolver al objeto
publicado. Todos los handles existentes sobre el destino deben compartir
eliminación: la apertura ordinaria retenida sigue siendo el control negativo.
En POSIX se conserva `os.replace`. Windows no vuelve
silenciosamente a `MoveFileExW` si no puede cumplir el contrato.

El buffer sigue la unión `BOOLEAN`/`DWORD` del SDK, seguida de `HANDLE`,
`DWORD` y ruta UTF-16: offsets de `RootDirectory`, `FileNameLength` y
`FileName` 4/8/12 en Win32 y 8/16/20 en Win64, con `Flags` en 0. La longitud
de nombre cuenta bytes UTF-16, sin terminador. El contraste portable con
declaraciones extraídas del SDK revisa esas expectativas, pero no acredita
el ABI nativo. Si la función o capacidad no está disponible se informa un
error explícito y se conserva el JSON previo. WinError 87 indica rechazo de
parámetro, clase, flags o buffer y se propaga sin reintentos; no demuestra por
sí solo falta de capacidad del sistema o volumen. La información de volumen
es diagnóstico de soporte, no sustituto del control real de publicación.

Se mantiene temporal completo, `flush` y `fsync` antes de publicar, JSON
anterior íntegro ante fallo y limpieza solo del temporal propio. No se borra
el destino, no se sobrescribe parcialmente y no se amplían los límites:
10 s para bloqueo transitorio de publicación y 2 s para lectura. Un tercero
que niega eliminación puede bloquear; el bloqueo persistente sigue siendo
un negativo acotado. Se conservan solo lectura, errores permanentes,
escritura temporal fallida, liberación coordinada y la regresión v3.1 que
impide derivar `interrumpida` cuando acaba de publicarse `exito`.

Las pruebas mantienen 120 publicaciones, tres lectores en hilos y un proceso
externo, además de los handles retenidos cooperante y ordinario, integridad,
orden, estado final, mediciones ante excepción y cierres propios acotados.
Los dobles portables revisan construcción de buffer, llamadas y errores; la
semántica de reemplazar un destino abierto y la ABI real requieren Windows.
Los JSON de medición deben identificar API, plataforma y volumen para
confirmar qué rama se ejecutó.

Fuentes primarias:

- [CPython #90161](https://github.com/python/cpython/issues/90161).
- [FILE_RENAME_INFORMATION](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_file_rename_information).
- [FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info).
- [SetFileInformationByHandle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle).
- [FILE_INFO_BY_HANDLE_CLASS](https://learn.microsoft.com/en-us/windows/win32/api/minwinbase/ne-minwinbase-file_info_by_handle_class).
- [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew).
- [Semántica de FileRenameInfoEx y handles existentes (eryksun)](https://discuss.python.org/t/adding-atomicwrite-in-stdlib/11899/16).

### Cierre documental actual: aplicar y devolver su comprobación

La implementación, las baterías locales y la revisión visual v3.4 descritas
arriba ya terminaron. Usa únicamente `aplicar-fase4-cierre.ps1`, desde una
**consola normal de Windows PowerShell 5.1**, siguiendo el inicio completo de
`fase4-guia-cierre-windows.md`. Ese aplicador acepta v3.4 exacta o el cierre ya
aplicado, comprueba base, rama, índice y contenido de los 52 archivos, compara
LF/CRLF solo en memoria y aplica únicamente los cuatro documentos. Rechaza
cambios ajenos antes de modificar y conserva el índice real y las variables
de entorno. No abre `.env`, no lee almacenes reales ni consulta la aplicación,
y no ejecuta pytest ni demostraciones.

Devuelve su comprobación documental; Daniel realizará después commit, push y
PR desde Windows. Las ejecuciones nuevas de GitHub Actions sobre ese PR, la
suite completa nativa Windows y la acreditación prospectiva permanecen
pendientes separados. No se repiten para este cierre las baterías Focal,
Regresiones o ConEnlaces, la publicación nativa v3.3 ni las consultas, PDF o
capturas ya auditados. Los recuentos 219/231 describen instantáneas históricas
de datos; no son guardas del aplicador.

`continuar-fase4-windows-v3.4.ps1` fue el procedimiento de validación anterior:
Focal y Regresiones en consola normal, ConEnlaces con el permiso de enlace
simbólico y Uvicorn en consola normal. Sus baterías reducidas conservaron por
separado la evidencia del escritor v3.3; no importaron sus verdes como pruebas
nuevas. El progreso estaba vinculado a contenido, manifiesto y entorno. Esa
continuación ya se ejecutó y no es el paso actual.

**Recorrido histórico ya completado: no ejecutar para este cierre.** Las
secciones 1–6 siguientes conservan instrucciones del producto, incluidas
acciones que escriben, generación, recuperación y preparación del servidor.
No son una orden para repetirlas. Los artefactos compatibles se reutilizaron;
el temporal original y sus registros permanecen intactos. No se requiere una
nueva consulta, generación, entrenamiento, recuperación, impresión ni captura.

## 1. Sesión (en las dos ventanas)

Usa dos ventanas de Windows PowerShell 5.1:

- **Ventana A (servidor, consola normal):** solo mantiene Uvicorn en marcha.
- **Ventana B (comandos):** las órdenes del recorrido.

Pega este bloque en las DOS ventanas antes de nada. El bloque:

- comprueba que el worktree contiene la Fase 4;
- fija los seis almacenes DENTRO del worktree, solo para esta sesión;
- fija la codificación UTF-8 y define las funciones de apoyo;
- se detiene si alguna ruta sale del worktree o no cabe sin rutas largas.

```powershell
$wt = 'C:\GitHub\loteria-predictor-fase4'
if (-not (Test-Path -LiteralPath (Join-Path $wt 'backend\app\application\use_cases\predicciones.py'))) { throw ('{0} no contiene la Fase 4' -f $wt) }
$py = Join-Path $env:LOCALAPPDATA 'loteria-predictor-venvs\ae68\Scripts\python.exe'
$env:PYTHONIOENCODING = 'utf-8'; $env:PYTHONUTF8 = '1'
[Console]::OutputEncoding = [Text.Encoding]::UTF8; $OutputEncoding = [Text.Encoding]::UTF8
$raiz = Join-Path $wt 'backend\storage'
$env:DIRECTORIO_PRONOSTICOS_EXPERIMENTALES = Join-Path $raiz 'pronosticos'
$env:DIRECTORIO_OPERACION = Join-Path $raiz 'operacion'
$env:DIRECTORIO_LABORATORIO_MODELOS = Join-Path $raiz 'laboratorio'
$env:DIRECTORIO_CARTERAS_MODELOS = Join-Path $raiz 'carteras'
$env:DIRECTORIO_RESULTADOS_MODELOS = Join-Path $raiz 'resultados'
$env:DIRECTORIO_PREDICCIONES_MODELOS = Join-Path $raiz 'predicciones'
Set-Location (Join-Path $wt 'backend')
function Orden([string]$modulo, [string[]]$argumentos, [int[]]$admitidos = @(0)) {
    # Ejecuta el comando, comprueba su código ANTES de leer el JSON y devuelve código y datos
    $salida = & $py -m $modulo @argumentos
    $codigo = $LASTEXITCODE
    $texto = ($salida | Out-String).Trim()
    if ($global:evidencia) {
        $global:pasoEvidencia = $global:pasoEvidencia + 1
        $nombre = '{0:D3}-{1}-{2}.txt' -f $global:pasoEvidencia, ($modulo -replace '^scripts\.', ''), $argumentos[0]
        [IO.File]::WriteAllText((Join-Path $global:evidencia $nombre), ('codigo {0}{1}{2}' -f $codigo, [Environment]::NewLine, $texto))
    }
    if ($admitidos -notcontains $codigo) { throw ('{0} {1} terminó con el código {2}' -f $modulo, ($argumentos -join ' '), $codigo) }
    $datos = $null
    if ($texto) { $datos = $texto | ConvertFrom-Json }
    return [pscustomobject]@{ Codigo = $codigo; Datos = $datos }
}
function Pred([string[]]$argumentos, [int[]]$admitidos = @(0)) { Orden 'scripts.predicciones' $argumentos $admitidos }
function Lab([string[]]$argumentos, [int[]]$admitidos = @(0)) { Orden 'scripts.laboratorio_modelos' $argumentos $admitidos }
function Carteras([string[]]$argumentos, [int[]]$admitidos = @(0)) { Orden 'scripts.carteras_modelos' $argumentos $admitidos }
function Huellas([string]$carpeta) {
    # SHA-256 de cada archivo conservable, por ruta relativa (solo lee). Excluye el estado vivo: los logs (Uvicorn
    # mantiene storage\logs\sync.log abierto para escribir) y los cerrojos (.lock con una region bloqueada y .activo).
    # Conserva JSON, estimadores, reservas de secuencia y los temporales que ya existian (p. ej. la evidencia).
    $mapa = @{}
    if (Test-Path -LiteralPath $carpeta) {
        $base = (Resolve-Path -LiteralPath $carpeta).ProviderPath.TrimEnd('\')
        foreach ($archivo in @(Get-ChildItem -LiteralPath $base -Recurse -File -Force)) {
            $relativa = $archivo.FullName.Substring($base.Length + 1)
            if ($relativa -match '(^|\\)(logs|cerrojos)(\\|$)' -or $archivo.Name -match '\.(log(\.\d+)?|lock|activo)$') { continue }
            try {
                $mapa[$relativa] = (Get-FileHash -LiteralPath $archivo.FullName -Algorithm SHA256 -ErrorAction Stop).Hash
            } catch {
                # Solo un temporal de una publicacion en curso puede desaparecer entre el listado y la lectura
                if (-not (Test-Path -LiteralPath $archivo.FullName) -and $archivo.Name -match '^\..+\.[0-9a-f]{8,16}\.tmp$') { continue }
                throw ('No se pudo leer {0}: {1}' -f $relativa, $_.Exception.Message)
            }
        }
    }
    return $mapa
}
$rutasPred = (Pred @('rutas')).Datos
foreach ($propiedad in $rutasPred.PSObject.Properties) {
    if ($propiedad.Name -like 'directorio_*' -and $propiedad.Name -ne 'directorio_de_trabajo') {
        '{0}: {1}' -f $propiedad.Name, $propiedad.Value
        if (-not "$($propiedad.Value)".StartsWith($raiz + '\', [StringComparison]::OrdinalIgnoreCase)) { throw ('{0} sale del worktree de la Fase 4' -f $propiedad.Name) }
    }
}
# Presupuesto de Windows sin rutas largas: explicacion = carpeta del almacen + 117; pronostico registrado = laboratorio + ~147
$largoPred = "$($rutasPred.directorio_predicciones_modelos)".Length
$largoLab = "$($rutasPred.directorio_laboratorio_modelos)".Length
if ($largoPred + 117 -gt 259) { throw ('La carpeta de predicciones mide {0} caracteres: sus explicaciones no cabrian en 259' -f $largoPred) }
if ($largoLab -gt 111) { throw ('La carpeta del laboratorio mide {0} caracteres (maximo 111)' -f $largoLab) }
'Rutas dentro de {0}; predicciones {1} + 117 = {2} caracteres' -f $raiz, $largoPred, ($largoPred + 117)
```

`rutas` muestra las carpetas efectivas, nunca `DATABASE_URL` ni `.env`. En
este worktree la carpeta de predicciones mide 62 caracteres, así que la ruta
más larga de una explicación queda en 179, lejos de 259.

## 2. Artefactos previos (ventana B)

### Copia exclusiva desde el worktree de la Fase 3 (escribe solo en este worktree)

**Ya hecha con la v2 en tu worktree: no se repite en la v3.3.** El script de
continuación no copia nada y conserva los artefactos, la configuración y
`.env`. Lo que sigue describe la copia de la v2, como referencia.

Un worktree nuevo empieza con los almacenes vacíos. Para recorrer tu histórico
real con las versiones registradas y las configuraciones de la Fase 3, copia
sus artefactos con el script de entrega (desde la carpeta de los adjuntos):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\aplicar-fase4-windows-v2.ps1 -CopiarArtefactos
```

El script:

- copia `pronosticos`, `operacion`, `laboratorio`, `carteras` y `resultados`
  desde `C:\GitHub\loteria-predictor-fase3\backend\storage`. Así llegan
  también los estimadores de las versiones a las que apuntan las
  configuraciones;
- no copia los archivos de cerrojo, que son estado de ejecución;
- se detiene, sin copiar nada, si el origen tiene temporales de publicación o
  un cerrojo abierto por otro proceso. Es lo que ocurre si la aplicación de la
  Fase 3 sigue generando: detenla antes. Un registro que quedó `en_curso` sin
  cerrojo abierto (un trabajo interrumpido) se informa y se copia tal cual,
  como historial;
- copia archivo por archivo. Si el destino existe con el mismo SHA-256, lo
  deja; si existe con otro contenido, se detiene sin sobrescribir;
- comprueba el SHA-256 de cada copia y que el origen no cambie;
- no importa sorteos, no entrena y no cambia ninguna configuración;
- al terminar, lista la configuración de cada juego y comprueba que cada
  versión registrada a la que apunta esté en el destino.

Ejecútalo después de aplicar el parche (la primera ejecución del script, sin
parámetros): exige el parche ya aplicado y no repite las pruebas.

### Instantánea antes de escribir

Registra el SHA-256 de todo lo que ya hay en los almacenes del worktree,
salvo los logs y los cerrojos (estado vivo). Funciona con Uvicorn en marcha.
La carpeta de evidencia queda en `%TEMP%`, y desde aquí cada orden guarda en
ella su código y su salida JSON.

```powershell
$global:evidencia = Join-Path $env:TEMP ('f4-real-{0}-{1}' -f (Get-Date -Format 'yyyyMMdd-HHmmss'), [guid]::NewGuid().ToString('N').Substring(0, 8))
$global:pasoEvidencia = 0
New-Item -ItemType Directory -Path $global:evidencia | Out-Null
$antes = Huellas $raiz
[IO.File]::WriteAllLines((Join-Path $global:evidencia 'antes.sha256'), [string[]]@($antes.Keys | Sort-Object | ForEach-Object { '{0}  {1}' -f $antes[$_], $_ }))
'{0} archivos previos registrados; evidencia en {1}' -f $antes.Count, $global:evidencia
```

## 3. Recorrido con el histórico real (ventana B)

Cada orden es un proceso Python nuevo: nada queda en memoria entre una orden y
la siguiente.

### 3.0 Instantánea previa de la v2 y la generación fallida (solo lee)

La línea base privada real es `%TEMP%\f4-real-20261013-085322-5b33289b\archivos-antes.csv` (184 archivos) y la copia del fallo es `%TEMP%\f4-fallo-9ff602c874d24a97a80f40db1d176714`. No están incluidos en los insumos de Cloud, y aquí no se afirma haberlos inspeccionado. Conserva el CSV original y compara sus rutas y SHA-256 con el estado actual; su esquema debe revisarse en Windows antes de convertirlo. No pases un CSV al lector de líneas SHA-256 siguiente.

Si también conservas una instantánea `antes.sha256` en el formato `SHA256  ruta_relativa`, usa este bloque sólo para ella. Se detiene si no contiene entradas válidas; los logs y cerrojos se ignoran.

```powershell
$previa = 'RUTA\antes.sha256'
$huellasPrevias = @{}
foreach ($linea in [IO.File]::ReadAllLines($previa)) {
    if ($linea -match '^([0-9A-Fa-f]{64})  (.+)$') {
        $relativa = $Matches[2]
        if ($relativa -match '(^|\\)(logs|cerrojos)(\\|$)' -or $relativa -match '\.(log(\.\d+)?|lock|activo)$') { continue }
        $huellasPrevias[$relativa] = $Matches[1].ToUpperInvariant()
    }
}
if ($huellasPrevias.Count -eq 0) { throw 'La instantanea no contiene entradas SHA256  ruta_relativa; no es el CSV original' }
$alteradosPrevios = @($huellasPrevias.Keys | Where-Object { -not $antes.ContainsKey($_) -or $antes[$_] -ne $huellasPrevias[$_] })
$nuevosTrasPrevia = @($antes.Keys | Where-Object { -not $huellasPrevias.ContainsKey($_) } | Sort-Object)
'{0} archivos en la instantánea previa (sin logs ni cerrojos); distintos o ausentes ahora: {1}' -f $huellasPrevias.Count, $alteradosPrevios.Count
$alteradosPrevios | ForEach-Object { '  distinto o ausente: {0}' -f $_ }
'Nuevos desde entonces ({0}), esperados de la generación fallida:' -f $nuevosTrasPrevia.Count
$nuevosTrasPrevia | ForEach-Object { '  {0}' -f $_ }
```

**Criterio:** ningún archivo previo distinto o ausente fuera de `operacion`.
Los nuevos son los de la generación fallida: la cartera `adce8ea7…` y su
reserva de secuencia en `carteras`, los dos registros
`20261013T135713Z-dc2deb60.json` y el temporal
`.20261013T135713Z-dc2deb60.8601c0ff.tmp`. Si aparece otra cosa, detente y
envíame la lista.

Con Uvicorn en marcha (ventana A), abre
`http://localhost:8007/predicciones/ejecuciones/20261013T135713Z-dc2deb60`:
debe decir «Interrumpido.», «Baloto · cartera: interrumpida», que la cartera
`adce8ea74e670829…` se publicó y se verificó, «Explicación: no se generó» y el
botón «Abrir la cartera publicada». En la ventana A no deben repetirse
peticiones `GET …/estado` cada 2 s. Abrirla no escribe: lo comprueba la
sección 4.

### 3.1 Estado de partida (solo lee)

```powershell
$juegos = @('BALOTO', 'BALOTO_REVANCHA', 'MILOTO', 'COLORLOTO')
$indice = (Pred @('indice') @(0, 3)).Datos
foreach ($j in @($indice.juegos)) {
    $c = $j.configuracion.artefacto
    $modeloTexto = 'sin configuración'
    if ($c) { $modeloTexto = '{0} v{1}, {2} combinaciones' -f $c.modelo.id, $c.modelo.version, $c.cantidad }
    $registradoTexto = '-'
    if ($j.registrado) { $registradoTexto = 'versión {0} ({1})' -f $j.registrado.numero, $j.registrado.estado }
    $ultimaTexto = 'ninguna'
    if ($j.ultima) { $ultimaTexto = 'objetivo {0}' -f $j.ultima.objetivo }
    '{0}: base {1} (último {2}); configuración: {3}; registrada: {4}; última predicción: {5}' -f $j.juego, $j.base.estado, $j.base.corte, $modeloTexto, $registradoTexto, $ultimaTexto
}
```

**Criterio:** cada juego con configuración muestra su modelo. Si apunta a una
versión registrada, esta debe salir `compatible`. Una versión `incompatible`
no se carga (código 7 al generar), y una `no_encontrado` indica que su estimador
no está disponible en el almacén del worktree. Revisa la evidencia conservada;
la continuación v3.3 no vuelve a copiar artefactos.

### 3.2 Elegir la versión registrada en la configuración (OPCIONAL; escribe)

Omite este paso si las configuraciones ya son las que quieres. Si no, guarda
una versión NUEVA de la configuración de un juego con su versión registrada de
la Fase 3. No entrena; las versiones anteriores de la configuración quedan en
el historial. Ejemplo con Baloto y ColorLoto, que recorriste con sus versiones
registradas en la Fase 3:

```powershell
$eleccion = @{ BALOTO = 'random_forest_clasificador'; COLORLOTO = 'random_forest_poisson' }
foreach ($juego in @($eleccion.Keys)) {
    $versiones = @((Lab @('modelos', '--juego', $juego)).Datos.juegos.$juego.versiones | Where-Object { $_.modelo -eq $eleccion[$juego] -and $_.compatible })
    if ($versiones.Count -eq 0) { '{0}: no hay una versión compatible de {1}; no se configura' -f $juego, $eleccion[$juego]; continue }
    $version = $versiones[-1]
    $cfg = (Carteras @('configurar', '--juego', $juego, '--modelo', $eleccion[$juego], '--cantidad', '3', '--semilla', '42', '--registrado', $version.clave)).Datos
    '{0}: configuración versión {1} con {2} versión registrada {3}' -f $juego, $cfg.version, $cfg.configuracion.modelo.id, $cfg.configuracion.modelo.registrado.numero
}
```

### 3.3 Generar con la configuración (escribe)

Genera la cartera de la configuración y su explicación. El código 5 (cartera
sin explicación, o sin cartera por la base) es admisible y queda registrado;
el 4 es un juego sin configuración, y se salta.

```powershell
$recorrido = [ordered]@{}
foreach ($juego in $juegos) {
    $g = Pred @('generar', '--juego', $juego) @(0, 4, 5)
    if ($g.Codigo -eq 4) { '{0}: sin configuración; se salta' -f $juego; continue }
    $p = $g.Datos.prediccion
    $recorrido[$juego] = [ordered]@{ cartera = $p.cartera.clave; linea = $p.cartera.linea; objetivo = $p.cartera.objetivo; estado = $p.estado; explicacion = $p.explicacion.clave }
    '{0}: {1}; cartera {2} ({3}, objetivo {4}); explicación {5}' -f $juego, $p.estado, $p.cartera.estado, $p.cartera.linea, $p.cartera.objetivo, $p.explicacion.estado
}
```

**Criterio:** `exito`, con la cartera `terminado` o `reutilizado`. Si generaste
ese objetivo antes con la misma configuración, sale `reutilizado`. La línea de
una versión registrada lleva `-reg<N>`, y la explicación queda `guardada` o
`reutilizada`.

**Solo después de revisar el histórico y autorizar la recuperación con Daniel:**
si se conserva la misma entrada de Baloto (corte 2720), la
cartera debe ser `adce8ea74e67082941cc26964662818cc5badf7411c4a8f2b05505f0d31b3f7b`,
`reutilizado`, con la explicación `guardada`. No se reentrena ni se reescribe
la cartera. Si el corte cambió porque importaste sorteos, la entrada es otra y
la cartera también.

```powershell
if ($recorrido.Contains('BALOTO') -and $recorrido['BALOTO']['cartera'] -eq 'adce8ea74e67082941cc26964662818cc5badf7411c4a8f2b05505f0d31b3f7b') { 'BALOTO: reutilizó la cartera publicada antes del fallo' }
```

Si una generación termina con el código 3 (`almacen no disponible`), conserva
la salida y el motivo. Puede ser un bloqueo que agotó el plazo de 10 s o un
error permanente que se propaga al primer intento; el código por sí solo no
identifica la causa. Lo ya publicado se conserva. Detente y entrega la salida
y la carpeta de evidencia.

### 3.4 Repetir: reutiliza cartera y explicación (acción generar: escribe registros y cerrojos)

Este bloque vuelve a invocar `generar`; no es una consulta pura. Cada intento crea registros nuevos en `carteras/operacion/ejecuciones/<id>.json` y `predicciones/operacion/ejecuciones/<id>.json`, actualiza su progreso y crea o usa cerrojos bajo `operacion/cerrojos` en ambos almacenes. Las carteras y explicaciones inmutables deben conservar su clave y contenido, sin reentrenar. El conteo siguiente excluye `operacion` y sólo verifica que no aparezcan explicaciones nuevas; no demuestra ausencia de escrituras. Para consultas puras usa 3.1, 3.6, 3.7 y los GET de la sección 4.

```powershell
$archivosPred = @(Get-ChildItem -LiteralPath $rutasPred.directorio_predicciones_modelos -Recurse -File -Force | Where-Object { $_.FullName -notlike '*\operacion\*' }).Count
foreach ($juego in @($recorrido.Keys)) {
    $p = (Pred @('generar', '--juego', $juego) @(0, 5)).Datos.prediccion
    if ($p.cartera.clave -ne $recorrido[$juego]['cartera'] -or $p.explicacion.estado -ne 'reutilizada') { throw ('{0}: la repetición no reutilizó' -f $juego) }
    '{0}: cartera y explicación reutilizadas' -f $juego
}
$archivosPredDespues = @(Get-ChildItem -LiteralPath $rutasPred.directorio_predicciones_modelos -Recurse -File -Force | Where-Object { $_.FullName -notlike '*\operacion\*' }).Count
if ($archivosPredDespues -ne $archivosPred) { throw 'Repetir creó explicaciones nuevas' }
```

### 3.5 Cinco combinaciones sin cambiar la configuración (escribe)

```powershell
$juegoCinco = @($recorrido.Keys)[0]
if (-not $juegoCinco) { throw 'Ningún juego tiene configuración: haz antes el paso 3.2' }
$cfgAntes = (Carteras @('configuracion', '--juego', $juegoCinco)).Datos.vigente
$cinco = (Pred @('generar', '--juego', $juegoCinco, '--cinco') @(0, 5)).Datos.prediccion
$cfgDespues = (Carteras @('configuracion', '--juego', $juegoCinco)).Datos.vigente
'{0}: {1} combinaciones en la línea {2}' -f $juegoCinco, $cinco.solicitud.combinaciones, $cinco.cartera.linea
if ($cfgDespues.version -ne $cfgAntes.version -or $cfgDespues.cantidad -ne $cfgAntes.cantidad) { throw 'La configuración cambió' }
'Configuración sin cambios (versión {0}, {1} combinaciones)' -f $cfgDespues.version, $cfgDespues.cantidad
```

Si la configuración ya pide 5, la petición es la misma que la de la
configuración y reutiliza su cartera.

### 3.6 Consultar: combinaciones, fuertes y débiles, explicación (solo lee)

```powershell
foreach ($juego in @($recorrido.Keys)) {
    $d = (Pred @('consultar', '--juego', $juego) @(0, 3)).Datos
    $p = $d.prediccion
    $rk = $p.rankings
    $principal = $rk.numeros
    if ($rk.pares) { $principal = $rk.pares }
    $papeles = (@($p.combinaciones) | ForEach-Object { $_.papel }) -join ', '
    '{0}: objetivo {1}, corte {2}; {3}' -f $juego, $p.objetivo, $p.datos.corte, $papeles
    '  fuertes ({0}): {1}' -f $principal.denominador, ((@($principal.fuertes) | ForEach-Object { ($_.candidato -join ' ') }) -join ', ')
    if ($rk.superbalota) { '  superbalota aparte ({0}): {1}' -f $rk.superbalota.denominador, ((@($rk.superbalota.fuertes) | ForEach-Object { $_.candidato }) -join ', ') }
    if ($rk.pares) { '  números aparte: {0}; colores aparte: {1}' -f $rk.numeros.denominador, $rk.colores.denominador }
    $imp = $p.explicacion.importancias
    if ($imp.estado -eq 'disponible') {
        $mayor = @($imp.valores | Where-Object { $null -ne $_.valor } | Sort-Object { [double]$_.valor } -Descending)[0]
        '  importancias globales de {0}: la mayor, {1} ({2})' -f $imp.estimador, $mayor.variable, $mayor.valor
    } else { '  importancias no disponibles: {0}' -f $imp.motivo }
    '  reproducción exacta: {0}; nivel_confianza en la proyección: {1}' -f $p.reproduccion.exacta, ($null -eq $p.proyeccion.columnas.nivel_confianza)
    if (-not $p.reproduccion.exacta) { throw ('{0}: la reproducción no es exacta' -f $juego) }
}
```

**Criterio:**

- la primera combinación es la «sugerencia del modelo» cuando el modelo la
  tiene, y las demás son «línea muestreada»;
- Baloto y Revancha muestran 43 números (uniforme 5/43) y la superbalota
  aparte (16); MiLoto, 39 números; ColorLoto, pares número-color y, aparte, 7
  números y los colores de la paleta;
- con una versión registrada, las importancias están disponibles; si no, su
  motivo;
- la reproducción es exacta y `nivel_confianza` está vacío.

### 3.7 Fiabilidad (solo lee)

```powershell
foreach ($juego in @($recorrido.Keys)) {
    $f = (Pred @('fiabilidad', '--juego', $juego) @(0, 3)).Datos
    foreach ($l in @($f.lineas)) {
        foreach ($ev in @($l.evaluaciones)) {
            $comp = $ev.componentes.numeros
            if ($ev.componentes.pares) { $comp = $ev.componentes.pares }
            $texto = 'sin cifras'
            if ($comp -and $comp.metricas) {
                $m = $comp.metricas.diferencia_log_loss
                $texto = 'Δ Log Loss {0} ({1})' -f $m.media, $m.estado
                if ($m.intervalo) { $texto = '{0} [{1}, {2}]' -f $texto, $m.intervalo[0], $m.intervalo[1] }
            }
            '{0} · {1} · {2}: {3}, {4} sorteos; {5}' -f $juego, $l.linea, $ev.tipo, $ev.estado, $ev.muestra.sorteos, $texto
        }
    }
    '{0} · receta en su informe: {1}' -f $juego, $f.receta.estado
}
```

**Criterio:** cada línea y tipo dice su estado y su muestra. Con pocas
emisiones resueltas lo normal es `sin_resultados`, `sin_datos` o
`muestra_insuficiente` (media sin intervalo). Un intervalo solo aparece desde
30 sorteos y no es una validación. Ninguna fila muestra «alta», «media» ni
«baja».

### 3.8 Explicar de nuevo: idempotente (escribe solo si faltara)

```powershell
foreach ($juego in @($recorrido.Keys)) {
    $e = (Pred @('explicar', '--cartera', $recorrido[$juego]['cartera'])).Datos
    if (-not $e.reutilizado -or $e.clave -ne $recorrido[$juego]['explicacion']) { throw ('{0}: explicar no reutilizó la explicación' -f $juego) }
    '{0}: explicación {1} reutilizada' -f $juego, $e.clave.Substring(0, 12)
}
```

## 4. Recorrido web

En la ventana A, después del bloque de sesión:

```powershell
& $py -m uvicorn app.main:app --host 127.0.0.1 --port 8007
```

Abre `http://localhost:8007` en esta misma máquina: los botones que escriben
solo funcionan desde `localhost` y con el token de la página.

**Las páginas de consulta no escriben.** En la ventana B, toma una instantánea
antes de navegar:

```powershell
$consulta = Huellas $raiz
```

Recorre solo páginas de consulta, sin pulsar ningún botón:

1. `http://localhost:8007/predicciones`: los cuatro juegos, con la
   configuración, la versión registrada, la base y la última predicción. Un
   juego sin configuración enlaza a Carteras.
2. `http://localhost:8007/predicciones/baloto` (y los demás juegos). Debe
   mostrar:
   - elección del operador y estado de los datos;
   - cortes de entrenamiento y de entrada, generación, integridad y frescura;
   - las combinaciones con su papel;
   - los fuertes y débiles (gráfica y tabla), con la superbalota aparte;
   - la explicación y la fiabilidad en el corte;
   - los enlaces a los artefactos originales y la proyección a la tabla;
   - el historial.
3. `http://localhost:8007/predicciones/colorloto`: los pares con su color en
   texto, y aparte los 7 números y los colores, cada uno con su denominador.
4. `http://localhost:8007/predicciones/baloto/fiabilidad`: «Qué se mide y qué
   no», el método, las fuentes y, por línea y tipo, la muestra, el estado y
   las cifras (gráfica y tabla). Prueba también «Evidencia hasta el sorteo» con
   un corte.
5. `http://localhost:8007/api/predicciones/BALOTO`: el mismo contenido en JSON.

Abre también la ejecución fallida de la v2 (paso 3.0) y la de una generación
de este recorrido: ninguna debe seguir consultando cuando ya terminó.

Después, en la ventana B:

```powershell
$trasConsulta = Huellas $raiz
$cambios = @($trasConsulta.Keys | Where-Object { $consulta[$_] -ne $trasConsulta[$_] }) + @($consulta.Keys | Where-Object { -not $trasConsulta.ContainsKey($_) })
if ($cambios.Count -gt 0) { throw ('Las páginas de consulta cambiaron archivos: {0}' -f ($cambios -join ', ')) }
'Consulta sin escrituras ({0} archivos)' -f $trasConsulta.Count
```

En la web, «Generar con la configuración» escribe y abre la página de
progreso; «Generar cinco combinaciones» no cambia la configuración. Si el
trabajo no se puede lanzar, la respuesta es un error 500 y la ejecución queda
«Interrumpido.» con su motivo y su fecha: la página deja de actualizarse y se
puede volver a generar. Si Carteras falla durante el trabajo, la página dice
«No se generó la predicción.» con el motivo y, si la cartera llegó a
publicarse, el enlace para abrirla; repetir la misma entrada la reutiliza.

## 5. Comparación final de los artefactos previos

```powershell
$despues = Huellas $raiz
$alterados = @(); $registros = @()
foreach ($relativa in @($antes.Keys)) {
    $igual = $despues.ContainsKey($relativa) -and $despues[$relativa] -eq $antes[$relativa]
    if (-not $igual) { if ($relativa -match '(^|\\)operacion\\') { $registros += $relativa } else { $alterados += $relativa } }
}
$nuevos = @($despues.Keys | Where-Object { -not $antes.ContainsKey($_) })
$porCarpeta = $nuevos | Group-Object { $_.Split('\')[0] } | ForEach-Object { '{0} {1}' -f $_.Name, $_.Count }
[IO.File]::WriteAllLines((Join-Path $global:evidencia 'despues.sha256'), [string[]]@($despues.Keys | Sort-Object | ForEach-Object { '{0}  {1}' -f $despues[$_], $_ }))
($recorrido | ConvertTo-Json -Depth 5) | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $global:evidencia 'recorrido.json')
'{0} previos: {1} intactos, {2} alterados o ausentes; {3} registros de ejecución previos cambiados; nuevos por carpeta: {4}' -f $antes.Count, ($antes.Count - $alterados.Count - $registros.Count), $alterados.Count, $registros.Count, (@($porCarpeta) -join ', ')
if ($alterados.Count -gt 0) { throw ('Artefactos previos alterados: {0}' -f ($alterados -join ', ')) }
'Evidencia en {0}' -f $global:evidencia
```

Los artefactos previos (informes, pronósticos, versiones, carteras,
configuraciones, informes de resultados y la evidencia de la generación
fallida) deben quedar intactos. Los archivos
nuevos van en `carteras` (carteras nuevas y sus ejecuciones), en
`predicciones` y, si hiciste el paso 3.2, en las configuraciones. Las carpetas
`operacion` se cuentan aparte.

## 6. Imprimir

Imprime o guarda como PDF `/predicciones/baloto`, `/predicciones/colorloto` y
`/predicciones/baloto/fiabilidad`. Comprueba:

- las tarjetas largas continúan en la página siguiente, sin dejar la primera
  casi vacía;
- las tablas imprimen todas sus filas y repiten la cabecera;
- las gráficas van con su tabla, y los colores de ColorLoto se leen como texto;
- la navegación interna y los botones no se imprimen;
- no hay solapamientos.

Anota los formatos que revises (por ejemplo, Legal vertical). En la revisión histórica de Claude en Linux se
revisaron Carta vertical y horizontal, A4 vertical y Legal vertical; esa
revisión no se atribuye a Windows. Imprimir no escribe.

## Códigos de salida de `scripts.predicciones`

| Código | Significado |
|---|---|
| `0` | Éxito |
| `2` | Uso incorrecto, o juego, línea, cartera o ejecución no válidos o no encontrados |
| `3` | Base de datos o almacén no disponibles (lo guardado se muestra igual); al generar, el almacén de operación siguió bloqueado y lo ya publicado se conserva |
| `4` | Sin configuración vigente para el juego (elígela en Carteras) |
| `5` | Resultado parcial: cartera sin explicación, o la generación no produjo cartera |
| `6` | Ya hay otra ejecución en curso para ese juego: no se inició nada |
| `7` | Versión registrada incompatible, sin sorteos cargados o fallo del proceso trabajador |
| `8` | Artefacto alterado o ilegible (nunca se sobrescribe) |

## Límites

- **Una predicción no es un resultado.** «Fuerte» y «débil» describen la
  clasificación del modelo para ese objetivo. Las importancias son globales
  del estimador: no explican por qué un candidato concreto ocupa su posición
  ni son causas.
- **La fiabilidad no es un nivel de confianza.** Separa la probabilidad
  emitida, el rendimiento observado y su incertidumbre. Con muestras pequeñas,
  la cobertura real del intervalo puede quedar por debajo del 95 %.
  - No corrige la selección de un modelo después de ver una comparación, ni
    los cambios de régimen.
  - El umbral de 30 sorteos solo decide si se calcula el intervalo.
- **Sin recalibración.** No se recalibra nada. Una recalibración sería otra
  versión, ajustada solo con el pasado y nunca aplicada a lo ya emitido.
- **Compatibilidad.** Una versión registrada solo se carga con la misma
  scikit-learn y las mismas versiones menores de Python, NumPy y SciPy (Fase
  3). Si no, se muestra como incompatible y no se genera con ella.
- **Rutas.** Sin rutas largas, Windows rechaza rutas de más de 259
  caracteres. Una explicación mide la carpeta del almacén más 117, y su
  temporal es más corto. La carpeta de este worktree mide 62.
- **Disco.** Requiere disco local NTFS (enlaces duros y creación exclusiva).

## Validación

El estado vigente y sus límites están en «Cierre local v3.4», al principio de
este documento. La documentación de cierre incorpora evidencia existente y no
declara nuevas ejecuciones del producto:

- **Codex Cloud, Linux sintético v3.4:** suite completa 6759 y selección
  filtrada 2514 aprobadas; OpenSSL `exigir` 7/7 en ambos JUnit, demostración
  8/8 y `pip check` correcto. La comparación sintética de 54 PDF, 473 filas y
  207 grupos es suya. No es Windows ni una prueba ejecutada por ChatGPT.
- **Daniel, Windows nativo v3.4:** Focal 198; Fase 3 81; Producto 6 73;
  Producto 5 96; Producto 4 94; Fase 5 94; Productos 1–3 229; demostración
  sintética 8/8 y `pip check` correcto. ConEnlaces: `fase4_sin_publicacion`
  217 y `seleccion_windows_sin_publicacion` 2432 (100 entradas); OpenSSL
  `exigir` 7/7 en el JUnit de la selección reducida. Cero fallos, errores u
  omisiones en las baterías finales; aviso conocido Starlette/httpx. Los
  grupos no se suman ni sustituyen una suite completa nativa.
- **Daniel, publicación nativa v3.3 conservada:** 82 aprobadas, NTFS, clase
  22 y flags 3, 120 publicaciones concurrentes y destino abierto verificados.
  Cinco fuentes byte-idénticas en v3.4. No se repitió automáticamente esa
  publicación ni se atribuye su evidencia a las baterías nuevas reducidas.
- **ChatGPT, auditoría de evidencia:** paquete/manifiestos y controles del
  incremental; 27 PDF/203 páginas principales y el PDF uniforme de ocho
  páginas aparte; muestra nativa móvil representativa de 390 × 648; JSON,
  formularios extraídos e inventarios de consultas. Los PDF y seis consultas
  corresponden a la base anterior con 219 archivos conservados; las últimas
  60 consultas corresponden a la base actualizada, 28 HTTP 200 y 32 rechazos
  HTTP 422 esperados, con 231 archivos intactos. Los 12 añadidos existían
  antes de ese bloque y preservaron los 219 originales. No se vuelven a
  revisar imágenes ni se leen aquí almacenes reales.
- **Historia conservada:** v2 tuvo una generación web real fallida; v3.1
  ConEnlaces dio 96 aprobadas y una fallida; v3.2 dio 116 aprobadas y dos
  fallidas. La corrección nativa fue v3.3. Esos intentos y temporales no se
  reescriben ni se presentan como éxitos. Las pruebas sintéticas de Claude
  v2/v3 siguen con esa atribución en README/ROADMAP.
- **Pendientes separados:** aplicar el cierre documental en Windows;
  commit/push/PR por Daniel y GitHub Actions sobre ese PR final; suite completa
  nativa Windows; acreditación prospectiva. Esta última requiere evidencia
  suficiente por línea y tipo. Siguen `experimental_no_acreditado`, AE-39
  NO-GO y `AUTORIZA_EVALUACION = False`.
