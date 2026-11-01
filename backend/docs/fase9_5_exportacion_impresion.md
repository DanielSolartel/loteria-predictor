# Fase 9.5 — Exportación e impresión de la consulta cargada

La SPA permite descargar JSON/CSV e imprimir por acción explícita, usando únicamente los datos públicos ya decodificados de la consulta visible. Descargar o imprimir añade **cero solicitudes de red y cero fichas**: no consulta fiabilidad, recopila páginas, ejecuta modelos ni guarda informes. La validación nativa en Windows con Brave y la auditoría están completadas ([validación del operador](fase9_5_validacion_operador_2026-11-01.md)); la publicación manual, la integración y el CI de 9.5 siguen pendientes, y la Fase 9 global sigue abierta.

Diseño y alcance general: [frontend](fase9_frontend.md#entrega-95-exportación-impresión-y-revisión-final). Validación nativa: [Windows](fase9_windows.md#entrega-95-validación-nativa-completada); protocolo ejecutado y conservado como referencia: [Windows](fase9_windows.md#entrega-95-validación-nativa-pendiente). Las descargas son representaciones de consulta, sin autenticidad canónica, sello temporal, nueva inferencia ni ventaja predictiva acreditada.

## Base y antecedentes integrados

Base exacta `9fde216c5667bd7a1ddb8553a73857f5cfb07e61`, merge del PR #104; árbol `f9457d74310aa199f7a569ec0362c7a9acc4653e`, **1028 archivos públicos**. Integra el producto y cierre de 9.4. Las entregas 9.1–9.4 están integradas en los PR #100, #101, #102 y #104; no se reaplican parches de fases anteriores.

9.4 conserva su aprobación Linux, Windows nativo con Brave y visual: 173 backend y sonda 3/3 con procedencias y retenciones separadas; 780 Vitest nuevos en Windows; 87 visitas Brave, 15 comprobaciones de navegador, ocho HTTP y 88 capturas aprobadas posteriormente. Esos grupos se solapan y no son ejecuciones nuevas de 9.5. [Informe histórico íntegro](fase9_4_validacion_operador_2026-10-28.md).

**CI de 9.4 bloqueado sin ejecutar pruebas.** Los workflows `40834824739` (Python) y `40834824733` (frontend) figuran como `failure`, pero sus cinco jobs no arrancaron. La anotación comunica pagos recientes fallidos **o** necesidad de elevar el límite de gasto; no se determinó cuál alternativa aplica. No son pruebas aprobadas ni fallidas del producto. No se cambian facturación, workflows o protecciones ni se disparan o reintentan Actions.

La aceptación externa de las cinco descripciones 422 `Unprocessable Entity`/`Unprocessable Content` conserva ambos documentos y sus diferencias; todo el resto del JSON coincide. Los JSON completos no son idénticos. 9.5 no cambia API, pasarela, OpenAPI/tipos, dependencias/lock, ML o los informes históricos auditados.

## Matriz de las consultas

Las acciones pertenecen al estado listo y a la identidad de la respuesta cargada. Al navegar, cambiar juego, filtros, página o cartera, el resultado anterior deja de habilitar descargas; carga, cancelación, error, 409/429 y estructura no reconocida no reutilizan datos de otra consulta. Un vacío válido sí se puede exportar, conservando cabeceras y contexto, sin filas de datos inventadas.

| Superficie | JSON e impresión | Tablas CSV de los datos cargados |
|---|---|---|
| Ficha y resumen del juego | Reglas/resumen y su muestra, corte y frescura | Frecuencias, atrasos y distribuciones disponibles |
| Sorteos: listado | Filtros, orden, página y total | Sólo los sorteos de la página actual |
| Sorteos: ficha | Identidad y resultado mostrado | El sorteo, con números o pares y superbalota cuando corresponde |
| Estadísticas: panel | Muestra y métricas del panel cargado | Indicadores con dimensión, unidad y estado informados |
| Estadísticas: métrica | Respuesta de la métrica y sus filtros efectivos | Selección explícita de tabla; columnas/unidades y página cuando existe |
| Predicción guardada y explicación | Contexto, cartera, explicación, clasificación e integridad cargados | Combinaciones y candidatos disponibles, mediante selección de tabla |
| Fiabilidad | Consulta general actual o evidencia ya acreditada de una cartera, identificadas por separado | Tablas cargadas de seguimiento, retrospectiva y receta, sin mezclarlas |
| Modelos registrados: listado | Filtros, versiones públicas, estados y página | Metadatos de la página actual, incluidos alterados/incompatibles |
| Modelos registrados: ficha | Identidad, receta, cortes y metadatos acreditados | Metadatos públicos; no estimadores, binarios o contenido privado |
| Carteras guardadas: listado | Filtros, página, total y estados | Sólo las carteras de la página actual |
| Carteras guardadas: ficha | Identidad histórica, cortes, objetivo y reproducción guardada | Combinaciones cargadas y su procedencia |
| Resultados de Producto 6 | Filtros de objetivos, líneas, estados, historial y agregados | Selección explícita de historial o agregados; el historial sólo incluye su página |
| Simulaciones: listado | Límite aplicado, procedencia e integridad | Sólo las simulaciones cargadas, sin atribuir todo el almacén |
| Simulaciones: ficha | Identidad, parámetros y contenido verificado cargado | Tablas comparadas disponibles, con valores y expresiones exactas informadas |

Son **14 superficies** de datos, además de Inicio, Servicio y errores, que se incluyen en navegación y accesibilidad pero no ofrecen descargas sin un conjunto útil. CSV no añade tablas, cálculos estadísticos ni objetos anidados opacos para completar la matriz. La elección concreta de tablas depende de los datos de la respuesta.

La predicción conserva las cuatro fichas automáticas de 9.3 (catálogo 1 + predicción 3). La fiabilidad cuesta otras tres sólo al pulsar su consulta explícita. Exportar e imprimir no la solicitan: si no está cargada o no acredita la misma línea, perfil, modelo y versión registrada, se informa el límite y no se atribuye a la cartera. `hasta` limita objetivos; no prueba disponibilidad histórica. F94-ROB-01 sigue aislando metadatos necesarios alterados por artefacto y conserva el nombre opcional ausente como `null`.

## JSON versionado y contexto

JSON usa UTF-8 y MIME `application/json`. Su envoltura identifica `esquema: "loteria-predictor/consulta-publica/1"`, `exportado_en`, `juego`, `recurso`, `ruta_spa`, `filtros`, `alcance`, `paginacion`, `identidad`, `estado_de_uso`, `autoriza_evaluacion`, `advertencias` y `datos`. La fecha de exportación es distinta de los cortes y fechas de generación/observación que conserva `datos`.

`ruta_spa` es relativa y canónica, con sólo parámetros permitidos; no copia origen, parámetros arbitrarios o credenciales. `identidad` repite los cortes, objetivo, línea, modelo/versión, referencias registradas e identificadores escalares que esta consulta acredita, cuando existen; no se añaden como filtros a la URL ni se completan desde otro contexto. Ese mismo contexto aparece en la impresión y en las columnas CSV `identidad_*`, acompañadas de su tipo. La envoltura de paginación contiene únicamente página, tamaño y total; el resto de la respuesta permanece en `datos`. `datos` procede de la proyección pública reconocida: no contiene React, errores crudos, cliente, configuración de la pasarela ni cabeceras. Conserva números y precisión recibidos, `null`, cero, falso, cadenas, listas y advertencias sin sustituir ausencias por ceros. No se aplica el redondeo del formato visual. ColorLoto mantiene la correspondencia y orden de cada par número-color, con nombre textual del color.

Las listas paginadas se anuncian como **«Exportar página actual»** e identifican página, tamaño, filas cargadas y total cuando existen. Detalle, muestra y agregado declaran su alcance real; no se presentan como exportación masiva de todo el histórico. Alteración, incompatibilidad, pendiente, retrospectiva y seguimiento conservan sus significados.

## CSV protegido y descarga local

CSV usa MIME `text/csv`, UTF-8 **con BOM**, delimitador coma y finales CRLF. Todas las celdas se citan y las comillas se duplican; comas y saltos no crean columnas o registros espurios. La primera fila de contenido tiene `tipo_fila=contexto` y no representa una observación; las siguientes tienen `tipo_fila=dato`. Un vacío válido contiene cabeceras y contexto, `filas_cargadas=0`, sin observaciones inventadas.

Las columnas estables incluyen la identidad de exportación, tabla, alcance, paginación, filtros permitidos y las columnas útiles de esa tabla. Cada valor de datos lleva su columna `_tipo` (`texto`, `numero`, `booleano` o `null`). `null` se representa como `null` con ese tipo; la cadena vacía mantiene tipo `texto`, cero es `numero` y falso es `booleano`. Así no se confunde ausencia con cero, falso o cadena vacía. Unidades, identificadores y cortes acreditados acompañan la tabla sin redondear cifras.

Las celdas compuestas de una métrica se expanden en columnas por sus hojas y posiciones, sin bloques JSON opacos. Se indican de forma distinta `campo ausente`, `lista vacía` y `objeto vacío`. Sorteos y combinaciones conservan una fila por balota con su posición y par número-color; una emisión sin resultado lleva una fila de estado explícita, sin inventar un resultado. Los agregados de Producto 6 declaran todo el filtro recibido de la API, separados del historial paginado y de la comparación sobre la muestra común.

La representación CSV **protege las cadenas textuales**, anteponiendo un apóstrofo a texto peligroso: comienzos con espacio, control, comilla o `=`, `+`, `-`, `@`, además de controles/saltos dentro del texto. Citar una celda por sí solo no neutraliza fórmulas. Un número negativo tipado sigue siendo número; la misma cadena peligrosa conserva su texto original en JSON. La protección se documenta porque el CSV no es una serialización literal de esas cadenas.

Los nombres están acotados y se construyen con códigos/segmentos saneados de juego, recurso y tabla más fecha UTC, nunca con rutas o nombres crudos del servidor. MIME y extensión coinciden. El navegador crea un `Blob`, inicia el enlace de descarga y libera su URL de objeto después de iniciarla; las descargas sucesivas no navegan a otra ruta ni persisten estado. No añaden recursos externos, conversores, almacenamiento ni dependencias.

## Impresión y navegación

Imprimir llama explícitamente a `window.print()` sobre la consulta actual. No usa `innerHTML`, ventanas con HTML concatenado, otra URL ni un motor PDF de servidor. Conserva juego, título, identidad, filtros efectivos, corte/objetivo/observación, página/alcance, unidades, estados y avisos experimentales. Las combinaciones llevan texto de sus colores y los resultados pendientes no se convierten en cero aciertos.

Los estilos de impresión ocultan navegación, acciones, filtros editables y paginación redundante; conservan un resumen legible del contexto. Las regiones de tabla dejan de truncar filas por scroll, sus cabeceras no se superponen y las tarjetas largas pueden fragmentarse. Se abren sólo detalles ya presentes y se restaura su estado al terminar o cancelar, sin cargar contenido. El ensayo genera PDF de **Carta vertical, Carta horizontal y A4 vertical**, además de controles del HTML impreso: una captura con CSS emulado no sustituye ese PDF.

### Observación de la impresión en el ensayo (F95-NAT-01)

El ensayo ya no compara los desplegables 50 ms después del clic. `frontend/e2e/impresion.mjs` registra `beforeprint`/`afterprint` (con `isTrusted`), la entrada y salida de `window.print()`, `matchMedia('print')` y los estados de `main details`, y espera condiciones observables con plazo acotado (`--plazo-impresion`, 3000 ms por defecto). Cada consulta exportable produce comprobaciones separadas:

- `imprimir-pdf-restaura-*-inicial` y `-mixto`: `page.pdf` con eventos reales del navegador acredita que se abren los desplegables y se restaura el estado, cerrado o con el primero abierto por clic real. Se ejecuta antes de cualquier clic.
- `imprimir-control-negativo-*`: `beforeprint` sintético sin `afterprint` debe cambiar el estado. Es sólo un control de la comparación; nunca acredita el clic.
- `imprimir-clic-real-*`: clic real en «Imprimir». Con `afterprint` confiable se exige restauración. Si hay `beforeprint` confiable, se abren los desplegables y `print()` retorna sin `afterprint` dentro del plazo (headless sin diálogo), queda **no evaluable** (`afterprint_no_emitido`), no aprobada. En una pestaña donde ya ocurrió eso, el navegador no inicia otro ciclo y el clic siguiente queda `impresion_pendiente_en_pestana`. Cualquier otra ausencia (sin `print()`, sin `beforeprint`, `beforeprint` sin preparar, `afterprint` sin restaurar, clic fallido, página bloqueada) es un fallo.
- `descargar-imprimir-sin-red-*` (o `imprimir-sin-red-*`): cero solicitudes y cero fichas, independiente del resultado del clic.

Las no evaluables tienen `ok: null`, se listan en `no_evaluables` y salen en JUnit como `skipped` con su mecanismo. Una restauración sin desplegables cerrados se rotula `sin_desplegables` o `restaurado_sin_cerrados`, porque no discrimina. `frontend/e2e/impresion-regresiones.mjs` contiene las regresiones: unitarias y, con `--navegador` y `--perfil afterprint-sincrono|afterprint-ausente`, una página local con variantes correctas y defectuosas. El supervisor admite `--solo-impresion` (escenario normal): revalida sólo estos criterios sin descargas ni matriz PDF. No sustituye el recorrido completo.

La revisión de navegación comprende URL directa, recarga, atrás/adelante, listado/ficha, filtros y paginación; los filtros permitidos se conservan al volver y no se atribuyen a otra pantalla incompatible. Se mantienen salto al contenido, `main`, títulos, foco visible, `aria-current`, etiquetas y asociaciones, carga/error anunciados y regiones de scroll nombradas accesibles por teclado. Las tablas anchas pueden desplazarse en su región; la página completa no debe desbordarse. La revisión usa los cuatro juegos a **360, 390 y 1280 px**, sin rediseño ni gráficos nuevos. Los controles automatizados y la revisión de imágenes no equivalen a certificación general WCAG.

## Verificación Linux y evidencia de revisión

Los resultados nuevos de 9.5 se identifican en el informe de la entrega y sus registros con orden, versiones, código, duración, stdout/stderr y JUnit. Se separan serializadores/adaptadores, estado/contexto, frontend completo sobre el código final y recorrido sintético API → pasarela → SPA compilada. Las descargas se vuelven a leer; el CSV se interpreta con un parser independiente. Se cotejan contenido, protección de texto, precisión, vacíos, nombres, ColorLoto y cero incremento de red/fichas al descargar o imprimir.

La evidencia PDF declara documento, formato, número de páginas, encabezados, unidades, filas/combinaciones y última fila comprobadas. Identifica qué páginas se inspeccionaron visualmente y cuáles sólo por contenido; no afirma inspección visual exhaustiva. Los fixtures, descargas, capturas y PDF son sintéticos y se distribuyen fuera del código, sin `node_modules`, venvs, datos reales o secretos. La prueba Git del paquete aplica y revierte el parche 9.5 desde/hasta la base exacta de 1028 archivos, preservando índices y contenido ajeno.

**Resultados nuevos Linux Cloud (30-10-2026):** Vitest completa sobre el código final: **864/864**, sin fallos, errores u omisiones; tipos, TypeScript, build y canario correctos. Recorrido normal `recorrido-normal-05`: **177 visitas** (59 por anchura), **92 comprobaciones separadas**, **193 descargas reales** (60 JSON y 133 CSV), doce capturas y doce PDF, sin fallos. Las focales unitarias están incluidas en la completa y no se suman.

Los escenarios vacío (12 visitas/12 comprobaciones/30 descargas), alterado (4/4/4), incompatible (2/3/4), cuota (0/3/12) y API caída (3/0/0) conservan su ejecución aprobada anterior al ajuste específico de impresión; no se presentan como reejecuciones del último CSS. El contador de cuota es cero aunque sí navega. Exportar/imprimir añadió cero solicitudes y cero fichas según los costes públicos de los GET observados; no se inspeccionó el bucket interno.

La revisión final de impresión `impresion-codigo-final` usa el modo explícito `--solo-pdf`: **12 PDF, 64 páginas, 24 comprobaciones**, sin sustituir las 177 visitas completas. Revalida Carta vertical/horizontal y A4 vertical tras evitar un rótulo `dt` aislado. Se inspeccionaron visualmente **siete páginas de seis PDF**, identificadas con huellas en `evidencias/revision-visual/revision-final.json`; las otras 57 páginas tienen controles de contenido, papel y posición, sin lectura visual acreditada. Cuatro recortes de tres pantallas a 390 px se revisaron visualmente; 360/1280 px conservan su matriz automatizada. No equivale a certificación WCAG ni a aprobación del auditor externo. Las once regresiones del comprobador PDF aprobaron; incluyen matrices incompletas, contenido esperado vacío, papel incompatible y el rechazo de los tres PDF anteriores con solapamiento real de superbalota.

Las dos guardas de ejemplos de arranque aprobaron **2/2**, registradas aparte con JUnit en `guardas-documentales-final`. Se conservan los intentos fallidos anteriores: no se convierten en aprobados al pasar una ejecución posterior. En aquella entrega, Windows/Brave, auditoría, publicación y CI seguían pendientes.

No se vuelven a ejecutar por rutina las baterías históricas 9.4, selección completa Windows, suite completa Python, PostgreSQL, ML, mediciones, OpenSSL o Fase 6. Los tipos/OpenAPI y demás archivos excluidos conservan sus bytes. Si aparece una deriva del runtime, se conserva el cotejo completo y se diagnostica sin sobrescribir el versionado ni excluir campos genéricamente.

**Ajuste F95-NAT-01 (Linux Cloud, 01-11-2026).** Sólo cambia el ensayo; `Marco.tsx` y el producto no cambian.
- **Evidencia nativa de partida (Brave 156.0.8078.74, Windows, auditada por Codex):** el clic real sin ventana emite `beforeprint` confiable, `print()` retorna y `afterprint` no llega en 5 ni en 30 s. `page.pdf` restaura los estados cerrado y mixto. Con ventana, Daniel comprobó la restauración al cancelar y al guardar un PDF.
- **Linux:** con Chromium 153 completo sin ventana, `--solo-impresion` a 390 px da 56 visitas. Hay 60 clics no evaluables (57 `afterprint_no_emitido` y 3 `impresion_pendiente_en_pestana`), 75 `page.pdf` aprobados (42 con restauración discriminante), 27 controles negativos y 60 comprobaciones sin red, sin fallos. Con chrome-headless-shell 153 los 60 clics se evalúan y se aprueban (27 con restauración discriminante). Una SPA mutante sin restauración da 26 fallos `afterprint_sin_restaurar`.
- **Revalidación nativa:** completada en Brave/Windows y aprobada por Codex: 167 criterios aprobados, 0 fallidos y 60 no evaluables ([detalle](fase9_5_validacion_operador_2026-11-01.md)). Los resultados anteriores conservan su atribución y no se suman como ejecuciones nuevas.

**Ajuste F95-PDF-01 (Linux Cloud, 01-11-2026).**
- **Hallazgo (auditoría de Codex sobre los PDF nativos de Brave):** en Carta vertical y A4, el par número/color de la tabla «Variables de los candidatos extremos» de ColorLoto invadía la columna «Emitida».
- **Corrección (solo en `@media print`):** dentro de una celda, el par puede pasar a otra línea por su espacio y, si es lo único en la celda, no suma su margen exterior. No cambia ningún ancho de columna, valor, color ni etiqueta; tampoco la pantalla.
- **Regresiones nuevas:**
  - `celdas-print-sin-desbordamiento-*` comprueba en el HTML impreso que el contenido de cada celda queda en su columna y que ningún valor numérico ni nombre de color se parte en dos líneas.
  - Con Poppler, el supervisor rechaza palabras solapadas en una misma línea y nombres de color pegados a cifras.
- **Resultados en Linux (Chromium 153, `--solo-pdf`):**
  - antes, 3 comprobaciones fallidas del HTML impreso y 7+6 (Carta vertical) y 12+2 (A4) colisiones en PDF;
  - después, 36/36 comprobaciones y 0 colisiones en los doce PDF, con los valores y colores conservados.
  - El supervisor daba `ok: false` antes y después en Linux porque su extractor portátil no encontraba algunos textos que Poppler sí encontraba; no se convierte en éxito.
- **Revalidación nativa:** completada en Brave/Windows y aprobada por Codex: supervisor con código 0, 36/36 criterios y 12/12 PDF, sin solapamientos en las 20 filas medidas por formato ([detalle](fase9_5_validacion_operador_2026-11-01.md)).

## Validación nativa y auditoría completadas

El 1 de noviembre de 2026, Codex aprobó la validación nativa en Windows 11 con Brave 156.0.8078.74 y cerró F95-NAT-01 y F95-PDF-01. Se consolidan, sin sumarse:
- las 864 Vitest y el recorrido normal de la v1, con sus 24 fallos históricos de restauración conservados;
- la revalidación focal de F95-NAT-01;
- la revalidación impresa de F95-PDF-01;
- la última tanda de cinco escenarios: 21 visitas y 64 criterios (45 aprobados y 19 no evaluables), con 50 descargas y 0 fallos.

El recorrido normal completo no se repitió sobre la fuente final y los no evaluables no son aprobaciones. Evidencias con nombre, bytes y SHA-256, alcance efectivo de cada escenario y límites: [validación del operador](fase9_5_validacion_operador_2026-11-01.md).

## Procedimiento nativo pendiente

*Actualización (1 de noviembre de 2026):* este procedimiento se ejecutó y la validación está completada. Se conserva como referencia histórica.

Lo siguiente es un procedimiento **para el auditor en Windows**, no una ejecución acreditada desde Linux. Usar PowerShell **5.1 normal**, Python **3.14.6 x64**, Node **24.15.0**, npm **11.12.1** y Brave instalado, con perfil temporal. Mantener el worktree operativo de Fase 6, su venv, tarea, configuración, plan y almacenes intactos. La carpeta de Fase 6 pertenece al mismo repositorio; no se consulta Programador, SQL ni servicio operativo.

**Etapa 1: revisar el ZIP y aplicar en copia separada.** Comprobar SHA-256 externo y `SHA256SUMS`. Elegir una raíz nueva con espacios; si existe, conservarla y escoger otra, sin borrar contenido. Extraer el ZIP en su subcarpeta `paquete revisado`. Comprobar primero `py -3.14 --version` y que corresponde a Python 3.14.6 x64; preparar sólo un venv propio, nunca el de Fase 6. La creación del venv no instala dependencias del proyecto:

```powershell
$origen = 'C:\GitHub\loteria-predictor'
$raiz = 'C:\GitHub\revision 9-5'
$repo = Join-Path $raiz 'codigo'
$paquete = Join-Path $raiz 'paquete revisado'
$python = Join-Path $raiz 'venv de pruebas\Scripts\python.exe'
$venvNuevo = Join-Path $raiz 'venv de pruebas'
if (Test-Path -LiteralPath $repo) { throw 'La carpeta de código ya existe; conservarla y escoger otra raíz.' }
if (Test-Path -LiteralPath $venvNuevo) { throw 'El venv ya existe; conservarlo y escoger otra raíz.' }
py -3.14 -m venv $venvNuevo
if ($LASTEXITCODE -ne 0) { throw 'No se pudo preparar el venv aislado; detenerse.' }
& $python --version
git -c core.autocrlf=false clone --no-hardlinks --no-checkout $origen $repo
if ($LASTEXITCODE -ne 0) { throw 'No se pudo preparar la copia; detenerse.' }
git --no-optional-locks -c core.autocrlf=false -C $repo checkout --detach 9fde216c5667bd7a1ddb8553a73857f5cfb07e61
if ($LASTEXITCODE -ne 0) { throw 'Falta la base exacta; detenerse.' }
& $python "$paquete\herramientas\comprobar_fuente95.py" --repo $repo --manifiesto "$paquete\fase9-5-manifiesto.json" --estado base --normalizar-crlf
if ($LASTEXITCODE -ne 0) { throw 'La fuente no coincide con la base; detenerse.' }
git --no-optional-locks -C $repo apply --check --ignore-space-change "$paquete\fase9-5.patch"
if ($LASTEXITCODE -ne 0) { throw 'El parche no se puede aplicar; detenerse.' }
git --no-optional-locks -C $repo apply --ignore-space-change "$paquete\fase9-5.patch"
if ($LASTEXITCODE -ne 0) { throw 'Aplicación fallida; conservar y detenerse.' }
& $python "$paquete\herramientas\comprobar_fuente95.py" --repo $repo --manifiesto "$paquete\fase9-5-manifiesto.json" --estado final --normalizar-crlf
if ($LASTEXITCODE -ne 0) { throw 'Contenido final distinto; detenerse.' }
git --no-optional-locks -C $repo diff --check
if ($LASTEXITCODE -ne 0) { throw 'Revisar el diff antes de continuar.' }
```

El verificador stdlib no importa la aplicación ni lee configuración privada. `--normalizar-crlf` actúa sólo en memoria; no reescribe la fuente. La acreditación completa precede a `--ignore-space-change`; ese argumento no permite aceptar cambios ajenos. Guardar estado, HEAD, árbol, inventarios e índice antes/después. Devolver esta evidencia y detenerse para revisión antes de preparar la siguiente etapa.

**Etapa 2: entorno y frontend aislados.** Comprobar las versiones anteriores. Preparar o reutilizar sólo un venv de pruebas compatible fuera del worktree, sin cambiar entornos operativos. Una instalación nueva usa los requisitos versionados y `pip check`; no modifica dependencias o lock del proyecto. El capturador externo `herramientas/ejecutar.py` guarda stdout/stderr separados y `ejecucion.json`; cada `--salida` debe ser una carpeta nueva. Resolver `node.exe` y el CLI npm existente evita invocar un archivo `.cmd` como si fuera ejecutable desde Python:

```powershell
$node = (Get-Command node.exe -ErrorAction Stop).Source
$npmCli = Join-Path (Split-Path (Get-Command npm.cmd -ErrorAction Stop).Source) 'node_modules\npm\bin\npm-cli.js'
if (-not (Test-Path -LiteralPath $npmCli -PathType Leaf)) { throw 'Localizar el CLI npm instalado antes de seguir.' }
$evidencia = Join-Path $raiz 'evidencia Windows'
$capturar = Join-Path $paquete 'herramientas\ejecutar.py'
& $python $capturar --cwd "$repo\backend" --salida "$evidencia\python-dependencias" --timeout 1200 -- $python -B -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Preparación Python fallida; conservar registros y detenerse.' }
& $python $capturar --cwd "$repo\backend" --salida "$evidencia\pip-check" --timeout 180 -- $python -B -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Dependencias incompatibles; detenerse.' }
& $python $capturar --cwd "$repo\frontend" --salida "$evidencia\npm-ci" --timeout 600 -- $node $npmCli ci --no-audit --no-fund
if ($LASTEXITCODE -ne 0) { throw 'npm ci falló; devolver evidencia.' }
& $python $capturar --cwd "$repo\frontend" --salida "$evidencia\tipos" --timeout 180 -- $node $npmCli run tipos:comprobar
if ($LASTEXITCODE -ne 0) { throw 'Tipos distintos; no regenerarlos.' }
& $python $capturar --cwd "$repo\frontend" --salida "$evidencia\typescript" --timeout 180 -- $node $npmCli run typecheck
if ($LASTEXITCODE -ne 0) { throw 'TypeScript falló; devolver evidencia.' }
& $python $capturar --cwd "$repo\frontend" --salida "$evidencia\vitest" --timeout 600 -- $node $npmCli test -- --reporter=default --reporter=junit --outputFile="$evidencia\vitest-junit.xml"
if ($LASTEXITCODE -ne 0) { throw 'Vitest falló; conservar JUnit y detenerse.' }
& $python $capturar --cwd "$repo\frontend" --salida "$evidencia\build" --timeout 180 -- $node $npmCli run build
if ($LASTEXITCODE -ne 0) { throw 'Compilación fallida; detenerse.' }
& $python $capturar --cwd "$repo\frontend" --salida "$evidencia\canario" --timeout 180 -- $node $npmCli run canario
if ($LASTEXITCODE -ne 0) { throw 'Canario falló; detenerse.' }
```

Guardar también versiones y huellas antes/después de OpenAPI, tipos y archivos protegidos. Devolver los registros y detenerse antes del recorrido nativo. No convertir esta etapa en la selección completa Python o en una nueva batería PostgreSQL/ML.

**Etapa 3: recorrido real sintético y revisión posterior.** Después de la revisión anterior, usar el supervisor 9.5 y Brave mediante su argumento `--navegador`, sólo con almacenes y perfil temporales propios. Revisar normal, vacío, alterado, incompatible, cuota y errores con HTTP real, descarga/lectura de JSON/CSV, cambios de contexto, cuatro juegos y tres anchuras. Generar Carta vertical/horizontal y A4 vertical, controlar contenido/paginación y revisar visualmente una muestra identificada. No sustituir Brave por Google Chrome ni simular HTTP para atribuirlo al recorrido real. Conservar descargas, matrices, logs, JUnit y capturas/PDF sintéticos, identificar páginas inspeccionadas y devolver evidencia antes de publicación.

El ensayo usa exclusivamente los datos sintéticos de sus fixtures. La ruta siguiente es una ubicación habitual del ejecutable instalado; si no corresponde, localizar Brave y acreditar su huella antes de continuar. No sustituirlo por otro navegador ni cambiar su instalación global. Cada escenario tiene carpetas de resultados y captura nuevas:

```powershell
$brave = 'C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe'
if (-not (Test-Path -LiteralPath $brave -PathType Leaf)) { throw 'Localizar y verificar el ejecutable Brave instalado; no continuar con otro navegador.' }
foreach ($escenario in @('normal', 'vacio', 'alterado', 'incompatible', 'cuota', 'api_caida')) {
    & $python $capturar --cwd "$repo\backend" --salida "$evidencia\supervisor-$escenario" --timeout 2400 -- $python -B -m tests.recorrido_fase95 --escenario $escenario --salida "$evidencia\recorrido-$escenario" --anchos '360,390,1280' --node $node --navegador $brave
    if ($LASTEXITCODE -ne 0) { throw "Falló $escenario; conservar toda su evidencia y detenerse." }
}
```

El modo opcional `--solo-pdf` se reserva para revalidar únicamente los doce PDF del escenario normal; no sustituye la matriz de navegación y exportación anterior.

El supervisor declara la plataforma que realmente ejecuta, conserva las respuestas esperadas y controla hashes, descargas, PDF y cero red adicional. Sus extractores de texto PDF son controles acotados a los documentos de Chromium de este ensayo; la revisión visual posterior sigue siendo necesaria. Devolver la matriz y los registros antes de autorizar una publicación. No ejecutar protocolos históricos de 9.4 ni operar Fase 6.

## Conservación y parada

Administración y operación permanecen en HTMX. Fase 6 no cambia ni añade observación: las novedades automáticas de los cuatro juegos conservan su atribución, y **09:24:45 no acredita disparo a las 09:00 ni recuperación matinal con resultados pendientes**. Continúan `experimental_no_acreditado`, **AE-39 NO-GO** y **`AUTORIZA_EVALUACION = False`**.

La entrega no cierra la Fase 9: la validación nativa con Brave y la auditoría de 9.5 están completadas, y siguen pendientes la publicación manual, la integración y el CI. No se inicia Fase 10/11, no se despliega y no se hacen commit, push, PR, merge o Actions. Daniel publicará manualmente después de la revisión de Codex del cierre documental.
