# Producto 2 en Windows: MiLoto, ColorLoto y resultados observados

Esta guía explica cómo entrenar y consultar los pronósticos experimentales
de MiLoto y ColorLoto y cómo comparar los pronósticos guardados de los cuatro
juegos con los resultados observados, sobre **tu base PostgreSQL real**. El
entorno Cloud donde se preparó el cambio solo usó historiales sintéticos: la
demostración con el histórico real solo puede correr en tu máquina.

Las órdenes son de PowerShell y usan el equipo del operador:

- checkout `C:\GitHub\loteria-predictor-update`, sin modificarlo: se trabaja en un worktree aislado;
- intérprete `$env:LOCALAPPDATA\loteria-predictor-venvs\ae68\Scripts\python.exe`;
- una configuración propia del worktree (`backend\.env` o `$env:DATABASE_URL`) que apunte a tu base real; ver el paso 0.

El archivo no seguido `storage/logs/sync.log` del checkout no se toca. La
guía de Producto 1 (`producto1_windows.md`) sigue valiendo para Baloto y
Revancha y para la protección local del botón de entrenar.

## 0. Sesión, worktree y pruebas

```powershell
$repo = 'C:\GitHub\loteria-predictor-update'
$wt   = 'C:\GitHub\loteria-predictor-producto2'
$py   = Join-Path $env:LOCALAPPDATA 'loteria-predictor-venvs\ae68\Scripts\python.exe'
function Revisar([string]$paso) { if ($LASTEXITCODE -ne 0) { throw "$paso falló (código $LASTEXITCODE)" } }
$env:PYTHONIOENCODING = 'utf-8'

git -C $repo fetch origin main;                         Revisar 'fetch'
git -C $repo worktree add --detach $wt origin/main;     Revisar 'worktree add'
# aplicar aquí el parche de Producto 2 en $wt (git -C $wt apply ...) o usar la rama que lo contenga
Set-Location (Join-Path $wt 'backend')
# Configuración propia del worktree (ver la nota de abajo); no se muestra ninguna credencial
if (-not (Test-Path .env) -and -not $env:DATABASE_URL) { throw 'Falta la configuración de la base: crea backend\.env o define $env:DATABASE_URL' }

& $py -m pip check;                                     Revisar 'pip check'
& $py -m pytest -q -p no:cacheprovider tests/unit/ml/test_pronostico_miloto.py tests/unit/ml/test_pronostico_colorloto.py tests/unit/test_producto2.py
Revisar 'pruebas nuevas'

$gitRaiz = Split-Path (Split-Path (Get-Command git).Source)
$opensslDir = @("$gitRaiz\usr\bin", "$gitRaiz\mingw64\bin") | Where-Object { Test-Path "$_\openssl.exe" } | Select-Object -First 1
$env:PATH = "$opensslDir;$env:PATH";  openssl version;  Revisar 'openssl'
$seleccion = Get-Content tests\seleccion_windows.txt | ForEach-Object { $_.Trim() } | Where-Object { $_ -and -not $_.StartsWith('#') }
& $py -m pytest -q -p no:cacheprovider --junitxml=..\resultados-windows.xml @seleccion;  Revisar 'selección'
& $py scripts\ci_contrastes_openssl.py ..\resultados-windows.xml --modo exigir;           Revisar 'OpenSSL'   # SUPERADOS 7/7
```

**Configuración del worktree.** El worktree nuevo no hereda archivos no
versionados. No presupongas que el checkout original tiene `backend\.env`.
El worktree necesita su propia configuración válida, de una de estas dos
formas:

- crea `backend\.env` a partir de `backend\.env.example` y pon tu
  `DATABASE_URL` real;
- define `$env:DATABASE_URL` solo en esta sesión.

`backend\.env` está en `.gitignore`. No escribas la cadena de conexión en
la guía, en los registros ni en lo que compartas.

## 1. Comprobar cuántos sorteos tienes

```powershell
& $py -m scripts.pronostico_experimental resultados --juego todos;  Revisar 'resultados'
```

El comando no entrena: compara los pronósticos ya guardados con la base y
termina con código `3` si no hay conexión. Para ver los sorteos cargados,
abre `/estadisticas`. MiLoto y ColorLoto necesitan al menos **30 sorteos
hasta el corte** (20 de entrenamiento mínimo y 10 objetivos evaluados). Con
menos, entrenar responde «Datos insuficientes» (código `4`) y no guarda nada.

## 2. Entrenar y generar

Desde la web: `& $py -m uvicorn app.main:app --reload` desde `$wt\backend`.
Abre **http://localhost:8000/pronosticos/miloto** (o `/pronosticos/colorloto`)
en esta misma máquina y pulsa **Entrenar y generar nuevo pronóstico**.

Desde la línea de comandos (comprueba `$LASTEXITCODE` tras cada orden):

```powershell
& $py -m scripts.pronostico_experimental entrenar --juego MILOTO;     Revisar 'entrenar MILOTO'
& $py -m scripts.pronostico_experimental entrenar --juego COLORLOTO;  Revisar 'entrenar COLORLOTO'
& $py -m scripts.pronostico_experimental entrenar --juego todos;      $LASTEXITCODE   # 4 si algún juego no tiene datos
& $py -m scripts.pronostico_experimental listar --juego COLORLOTO;    Revisar 'listar'
$id = ((& $py -m scripts.pronostico_experimental listar --juego MILOTO | Out-String) | ConvertFrom-Json).guardados[0].identificador
Revisar 'listar MILOTO'
& $py -m scripts.pronostico_experimental verificar --juego MILOTO --id $id;  Revisar 'verificar'
```

- **Lectura:** igual que en Producto 1, el histórico se lee en una transacción `READ ONLY` que termina en `ROLLBACK`.
- **Almacén:** el artefacto se guarda en `storage\pronosticos\<JUEGO>\` del worktree, sin sobrescribir nada. Lleva el esquema `pronostico-experimental/2` y el estado `experimental_no_acreditado`.
- **`todos`:** entrena los cuatro juegos. Si uno no tiene datos suficientes, su entrada lleva `error`, los demás se generan y el código de salida es `4`.
- **Idempotencia y versiones:** repetir la misma entrada devuelve el artefacto guardado. Un histórico corregido crea otra versión del mismo objetivo y las anteriores se conservan.

## 3. Páginas

| Página | Qué muestra |
|---|---|
| `/pronosticos` | Los cuatro juegos: último pronóstico, estrategia, objetivos evaluados, veredicto frente a la uniforme y resultado observado |
| `/pronosticos/miloto` | Cinco números sugeridos, ranking con la uniforme 5/39, trazabilidad (corte, fecha, versión, configuración), walk-forward con tamaño de muestra y mínimos, resultados observados y versiones |
| `/pronosticos/colorloto` | Combinación más probable (multiconjunto de 6 pares, con repetición), probabilidad del multiconjunto, muestra con semilla, paleta del corte, ranking de pares, métricas por balota y por multiconjunto, objetivos excluidos por color nuevo, resultados observados y versiones |
| `/pronosticos/baloto`, `/pronosticos/baloto-revancha` | Lo de Producto 1, más la tabla de resultados observados |
| `/api/pronosticos/MILOTO`, `/api/pronosticos/COLORLOTO` | Los artefactos en JSON, con `estado_actual` y `resultado_observado` |
| `/api/resultados-observados/{BALOTO,BALOTO_REVANCHA,MILOTO,COLORLOTO}` | Cada pronóstico guardado frente a su objetivo |

## 4. Comprobar un resultado observado

El corte no se supone: `corte-retrospectivo` lo toma de tu histórico. Elige
el mayor corte con al menos 30 sorteos hasta él cuyo objetivo (corte + 1)
también esté cargado, e informa su número y fecha reales.

```powershell
$c = (& $py -m scripts.pronostico_experimental corte-retrospectivo --juego MILOTO | Out-String) | ConvertFrom-Json
Revisar 'corte-retrospectivo'
"corte $($c.corte) ($($c.sorteos_hasta_el_corte) sorteos) -> objetivo $($c.objetivo) del $($c.fecha_objetivo)"
& $py -m scripts.pronostico_experimental entrenar --juego MILOTO --hasta-sorteo $c.corte;  Revisar 'entrenar'
& $py -m scripts.pronostico_experimental resultados --juego MILOTO;                       Revisar 'resultados'
```

1. En la salida, el pronóstico con ese corte debe tener `estado` `observado`, el `objetivo` y la `fecha` que informó `corte-retrospectivo`, y la emisión *reconstrucción retrospectiva*. Si no hay un corte así, el comando termina con código `4` y no hay nada que comprobar.
2. Abre `/pronosticos/miloto` y compara la tabla **Resultados observados** con `/sorteos`.
3. El pronóstico del sorteo siguiente al último cargado aparece como `pendiente`. Cuando sincronices y entre ese sorteo, pasará a `observado` con la emisión *emitido sin el resultado en la base local*. Eso no acredita que se emitiera antes del sorteo real: la fecha es del reloj local.

Repite los pasos con `--juego COLORLOTO`.

Estados posibles:

- **`observado`:** el objetivo figura en la base.
- **`pendiente`:** el objetivo es posterior al último sorteo cargado.
- **`no_corresponde`:** puede deberse a cualquiera de estos casos:
  - hay un hueco: faltan el objetivo y hay sorteos posteriores;
  - no hay histórico;
  - el artefacto está alterado.

Verificación de la entrada (`historico_hasta_el_corte`):

- **`coincide`:** la entrada se verificó.
- **`cambio`:** el histórico hasta el corte se corrigió después de generar el pronóstico. El aviso también aparece en `discrepancias`.
- **`no_disponible`:** ya no queda ningún sorteo hasta el corte en la base, así que la entrada no se puede verificar. No es una coincidencia ni un cambio demostrado.

El artefacto guardado nunca cambia.

## 5. Verificar la reproducción

```powershell
foreach ($juego in 'MILOTO', 'COLORLOTO') {
    $id = ((& $py -m scripts.pronostico_experimental listar --juego $juego | Out-String) | ConvertFrom-Json).guardados[0].identificador
    Revisar "listar ${juego}"
    & $py -m scripts.pronostico_experimental verificar --juego $juego --id $id
    Revisar "verificar ${juego}"
}
```

Recalcula con el histórico actual hasta el corte. `huella_exacta: true`
indica una reproducción idéntica. La muestra con semilla de ColorLoto también
se reproduce: depende de la semilla y del objetivo.

## 6. Imprimir o guardar como PDF

Abre la página (`/pronosticos`, `/pronosticos/miloto` o `/pronosticos/colorloto`)
y pulsa Ctrl+P. Comprueba lo siguiente:

- el pronóstico empieza en la primera página cuando cabe, y la sugerencia (los pares de ColorLoto o los números de MiLoto) aparece junto al objetivo, antes de los avisos;
- el ranking sale completo, con 39 filas en MiLoto y `7·K` en ColorLoto (42 con 6 colores), y la cabecera repetida en cada página;
- salen todos los bloques de evaluación, los resultados observados y las versiones;
- los colores aparecen escritos como texto.
- ninguna tarjeta tapa a otra; en particular, «Trazabilidad» no cubre las últimas filas del ranking.

El número de páginas depende del papel, los márgenes y los datos. Esta
última corrección (`producto2-impresion-alturas.patch`) está **validada funcionalmente en Windows**. La revisión visual documentada cubre los PDF de MiLoto y ColorLoto en Carta vertical, sin solapamientos.

## Evidencia registrada

- **Linux (Cloud, fixtures sintéticas), antes de la corrección de impresión:**
  - pruebas: Producto 2 `55 passed`, Producto 1 `102 passed`;
  - selección de Windows `1705 passed`;
  - suite completa `5950 passed`;
  - OpenSSL `SUPERADOS 7/7` en modo exigir.
- **Windows (operador, Python 3.14.6, OpenSSL 3.5.6), antes de la corrección de impresión:**
  - pruebas: Producto 2 `55 passed`, Producto 1 `102 passed`;
  - selección `1705 passed` sin omisiones;
  - OpenSSL `SUPERADOS 7/7` en modo exigir;
  - `pip check` limpio;
  - un único aviso de deprecación de Starlette/TestClient, que no es un fallo.

  La suite completa no se ejecutó en Windows.
- **Demostración con el histórico real (Windows):**
  - Baloto 636 sorteos y Revancha 636, ambos con corte 2716 y objetivo 2717;
  - MiLoto 84 sorteos, corte 615, objetivo 616;
  - ColorLoto 222 sorteos, corte 222, objetivo 223.

  En MiLoto y ColorLoto, repetir la entrada devuelve el mismo identificador. La verificación dio `huella_exacta`, `mismos_datos` y `mismos_numeros_sugeridos` verdaderos, y `maxima_diferencia_de_probabilidad = 0`.
- **Reconstrucciones retrospectivas verificadas (Windows):** en las dos, `historico_hasta_el_corte.estado = coincide` y `discrepancias` vacío.
  - MiLoto: corte 614, objetivo 615 (2026-09-29), `observado`, 1 de 5 números;
  - ColorLoto: corte 221, objetivo 222 (2026-09-28), `observado`, 0 de 6 pares.
- **Después, con los objetivos nuevos ya cargados (PDF de Windows):** los resultados anteriores siguen visibles.
  - Baloto 2717: 0 de 5, superbalota no;
  - Revancha 2717: 1 de 5, superbalota no;
  - MiLoto 616: 0 de 5;
  - ColorLoto 223: 1 de 6 pares.

  Estos aciertos no demuestran capacidad predictiva ni anterioridad frente al sorteo real. Que el resultado faltara en la base local al generar no prueba que el sorteo no se hubiera celebrado.
- **Evaluación histórica con datos reales:**
  - MiLoto y ColorLoto: la referencia uniforme gana;
  - Baloto: mejora las dos métricas principales, sin significancia estadística evaluada;
  - Revancha: no supera a la uniforme.
- **Corrección de impresión (`producto2-impresion-cierre.patch`), validación visual parcial en Windows:** los PDF anteriores y nuevos usan el mismo formato, Carta horizontal (792 × 612 pt).
  - Baloto y MiLoto ya muestran la sugerencia en la primera página.
  - ColorLoto pasó de 7 a 6 páginas y conserva las 42 filas, pero sus seis pares sugeridos seguían en la segunda página, después de los avisos.
- **Ajuste de ColorLoto (`producto2-colorloto-impresion.patch`), validado en Windows:** Python 3.14.6, OpenSSL 3.5.6.
  - Pruebas: Producto 2 `60 passed`, Producto 1 `102 passed`, selección `1710 passed` sin omisiones.
  - OpenSSL `SUPERADOS 7/7` en modo exigir; `pip check` limpio; un aviso de Starlette, sin fallos.
  - La suite completa no se ejecutó en Windows.
  - Las sugerencias de MiLoto y ColorLoto aparecen junto al objetivo en la primera página.
  - Defecto observado en el PDF de MiLoto en Carta vertical: «Trazabilidad» tapaba las filas 38 y 39 del ranking.
- **Altura de las tarjetas al imprimir (`producto2-impresion-alturas.patch`), validada en Windows (2026-10-06):**
  - Python 3.14.6 y OpenSSL 3.5.6. Producto 2: `61 passed`; Producto 1: `102 passed`; selección: `1711 passed`, sin omisiones.
  - OpenSSL `SUPERADOS 7/7` en modo exigir; `pip check` limpio; un aviso de deprecación de Starlette, sin fallos.
  - PDF de Windows revisados en Carta vertical: MiLoto conserva las 39 filas y ColorLoto las 42, sin solapamientos. Las sugerencias aparecen en la primera página y se conservan avisos, trazabilidad, métricas, resultados observados y versiones.
  - Esta revisión visual cubre esos dos PDF en Carta vertical. No hay evidencia de ejecución de la suite completa en Windows.
- **GitHub Actions:** todavía no ha validado esta rama.
- **Impresión de las páginas de pronóstico.**
  - **Causa:** la regla `break-inside: avoid` se aplicaba a todas las tarjetas. La del pronóstico, con el ranking de 39 o 42 filas, no cabía en el espacio que quedaba en la primera página, así que el navegador la empujaba entera a la segunda. La primera página quedaba con solo el título, los avisos y la introducción.
  - **Corrección:** las tarjetas largas (`impresion-fragmentable`) pueden fragmentarse. Esto cubre el pronóstico, la evaluación, los resultados observados y las versiones.
  - **Lo que no cambia:**
    - filas, avisos y títulos siguen sin cortarse;
    - las cabeceras de tabla se repiten en cada página;
    - la regla sigue limitada a `body.producto1-impresion` y la pantalla no cambia;
    - las columnas de Bootstrap, las filas flex y `h-100` no eran la causa: al ancho de impresión las columnas ya se apilan.
  - **Orden de la sugerencia:** al imprimir, la sugerencia va justo después del objetivo y antes de los avisos. Es la combinación de ColorLoto y los cinco números de MiLoto.
    - Con el histórico desactualizado y el resultado ya observado, los avisos llenaban la primera página en Carta horizontal.
    - Solo cambia el `order` dentro de la columna flex de la tarjeta, y solo en `@media print`.
    - Los avisos se conservan completos y la pantalla no cambia.
  - **Altura de las tarjetas:** al imprimir, `h-100` deja de fijar la altura de las tarjetas de producto.
    - **Causa:** fijaba la altura a la de la columna, calculada antes de fragmentar. Al partirse entre páginas, el contenido crecía más que la caja y la tarjeta siguiente se pintaba encima.
    - **Casos encontrados:** «Trazabilidad» sobre las últimas filas del ranking de MiLoto, Baloto y Revancha en Carta vertical. También, en el índice y en las estadísticas, una tarjeta sobre la anterior.
    - **Pantalla:** sin cambios.

## Qué significan las métricas

- **MiLoto:** las métricas se calculan sobre las 39 filas número-sorteo de cada objetivo.
  - Log Loss y Brier: menor es mejor.
  - Aciertos de los 5 sugeridos por sorteo: de 5.
  - Los denominadores (sorteos y filas) aparecen en la página.
- **ColorLoto** (modelo `pares_multinomial_con_suavizado_aditivo`: multinomial con probabilidades suavizadas `(conteo + α)/(6T + α·7K)`, que no es la predictiva Dirichlet-multinomial):
  - Log Loss y Brier por balota, promediados sobre las 6 balotas de cada sorteo.
  - Log Loss del multiconjunto: `−log P(multiconjunto observado)`.
  - Coincidencias de pares por sorteo: intersección con repetición, de 6.
- **Comparación:** cada juego se compara solo con su propia referencia uniforme. Las métricas de juegos distintos no comparten escala.
- **Veredicto:** si el modelo no gana en Log Loss y Brier, la página y el JSON dicen `el_modelo_no_supera_a_la_referencia_uniforme`. Ganar en un histórico corto no prueba ventaja.

## Qué es y qué no es

- **Estado:** `experimental_no_acreditado`. No es un resultado acreditado ni una recomendación de apuesta.
- **Lo que no cambia:**
  - el NO-GO de AE-39;
  - el NO-GO temporal de MiLoto y el aplazamiento de ColorLoto de AE-35;
  - los bloqueos R0;
  - el estado de AE-41;
  - `AUTORIZA_EVALUACION = False`.
- **Uso del historial:** usar todo el historial, holdout incluido, para explorar no es evidencia prospectiva.
- **Paleta de ColorLoto:** sale de tus datos anteriores al corte; la aplicación no fija ninguna regla oficial de colores.
