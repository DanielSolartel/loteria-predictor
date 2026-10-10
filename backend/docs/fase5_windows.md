# Fase 5 en Windows: estadísticas descriptivas completas y panel por juego

**Estado: completa; validada localmente en Windows con histórico real** (v2;
evidencia en «6. Validación registrada»). GitHub Actions todavía no la ha
ejecutado. Las cifras de Linux son de fixtures sintéticas y no acreditan Windows
ni el histórico real. Los pasos 1 a 5 sirven para repetir la validación.

Completar la fase descriptiva no cambia `experimental_no_acreditado`, el NO-GO
ni `AUTORIZA_EVALUACION = False`. Tampoco implica que las fases de ML,
predicción o evaluación estén completas. Frecuencias, atrasos, intervalos y
pruebas describen sorteos ya ocurridos: no son probabilidades del próximo
sorteo ni señales de apuesta.

## Qué añade y qué lee

- **Panel por juego:** `/estadisticas/{juego}/panel`, para `baloto`,
  `baloto-revancha`, `miloto` y `colorloto`.
  - Muestra todas las estadísticas del juego sobre la misma muestra.
  - Admite un corte opcional, `?hasta_numero_sorteo=N`, que se aplica antes de
    calcular.
  - Cada estadística aparece con su cifra clave. Las nuevas llevan la marca
    «Fase 5», y las que no aplican al juego, su motivo.
- **Páginas nuevas:** 18 en Baloto y Revancha, 11 en MiLoto y 5 en ColorLoto.
  - Cada página tiene su gráfica y una tabla con los mismos valores.
  - Algunas admiten un parámetro: `anio`, `mes`, `dia_semana` o `ventana`
    (5, 10, 20 o 50).
- **API JSON de solo lectura:**
  - `/api/estadisticas/{codigo}/panel`;
  - `/api/estadisticas/{codigo}/descriptivas/{metrica}`.
- **Navegación:** fila «Más estadísticas» en las 43 páginas anteriores (sus
  pestañas no cambian), y botón «Panel completo» en `/estadisticas`, en el
  resumen de cada juego y en el menú lateral.
- **Solo lectura:** se lee el histórico de PostgreSQL. No se escribe nada: ni
  la caché `estadisticas`, ni los almacenes, ni las configuraciones. No
  importa, no entrena y no cambia datos.

Unidades que no se mezclan:

| Unidad | Significado |
|---|---|
| % de sorteos | Sorteos que contienen el valor / sorteos de la muestra |
| % de números extraídos | Apariciones / (sorteos × números por sorteo) |
| Balotas por sorteo | ColorLoto; cada balota cuenta, también las repetidas |
| Sorteos de distancia | Diferencia de numeración entre dos sorteos |
| Puntos porcentuales | Diferencia entre dos porcentajes |

Pruebas y p-values (cada página dice cómo se obtiene el suyo):

- **Correlaciones:** los coeficientes de Pearson y Spearman son descriptivos y se
  muestran siempre que se puedan calcular.
  - **Entre mitades:** p-value por permutación sobre los números (7, 39 o 43
    categorías, no los sorteos). En ColorLoto se enumeran las 5040 ordenaciones
    (permutación exacta); en Baloto, Revancha y MiLoto, Monte Carlo con 9999
    ordenaciones y semilla fija 5, reproducible en cualquier versión de Python.
  - **Suma frente al sorteo anterior:** sin p-value. Las transiciones comparten
    sorteos y los pares no son independientes.
- **Chi-cuadrado** (uniformidad y número × color): p-value asintótico. El factor
  (N−1)/(N−K) sin reemplazo corrige la escala, pero no hace exacta la prueba;
  con frecuencias esperadas menores que 5 la página avisa.

## 1. Sesión (en las dos ventanas)

Abre dos ventanas de Windows PowerShell 5.1:

- **Ventana A:** solo mantiene Uvicorn en marcha.
- **Ventana B:** ejecuta los comandos.

En cada una, sitúate primero en la carpeta del worktree de esta entrega
(`Set-Location` a esa carpeta) y pega el bloque siguiente. El bloque toma el
worktree de Git y se detiene si la carpeta no contiene la Fase 5. Fija los
almacenes dentro del worktree, solo para esta sesión, y la codificación UTF-8.

```powershell
$wt = "$(& git rev-parse --show-toplevel)".Trim().Replace('/', '\')
if ($LASTEXITCODE -ne 0 -or -not $wt) { throw 'Esta carpeta no es un worktree de Git' }
if (-not (Test-Path -LiteralPath (Join-Path $wt 'backend\app\application\estadisticas\descriptivas.py'))) { throw ('{0} no contiene la Fase 5' -f $wt) }
$py = Join-Path $env:LOCALAPPDATA 'loteria-predictor-venvs\ae68\Scripts\python.exe'
$env:PYTHONIOENCODING = 'utf-8'; $env:PYTHONUTF8 = '1'
[Console]::OutputEncoding = [Text.Encoding]::UTF8; $OutputEncoding = [Text.Encoding]::UTF8
$env:DIRECTORIO_PRONOSTICOS_EXPERIMENTALES = Join-Path $wt 'backend\storage\pronosticos'
$env:DIRECTORIO_OPERACION = Join-Path $wt 'backend\storage\operacion'
$env:DIRECTORIO_LABORATORIO_MODELOS = Join-Path $wt 'backend\storage\laboratorio'
$env:DIRECTORIO_CARTERAS_MODELOS = Join-Path $wt 'backend\storage\carteras'
$env:DIRECTORIO_RESULTADOS_MODELOS = Join-Path $wt 'backend\storage\resultados'
Set-Location (Join-Path $wt 'backend')
'Worktree: {0}' -f $wt
```

## 2. Arranque (ventana A)

```powershell
& $py -m uvicorn app.main:app --host 127.0.0.1 --port 8005
```

Déjala abierta; para detener el servidor, `Ctrl+C`.

## 3. Comprobaciones con el histórico real (ventana B)

El bloque lee de la API la muestra real de cada juego. No presupone cantidades,
fechas ni cortes: el corte de prueba es el último sorteo cargado menos 10.

Con la respuesta de la API comprueba, una por una, cifras que también puedes
verificar a mano en las páginas. Antes de cada comprobación, el bloque revisa
que la respuesta HTTP sea 200, y se detiene en la primera discrepancia:

1. **Sumas:** con el corte, los sorteos del histograma suman los de la muestra,
   y la muestra termina en el corte.
2. **Decenas:** las apariciones suman sorteos × 5 números, y los porcentajes
   suman 100.
3. **Uniformidad:** el esperado por número es sorteos × K/N. El de la
   superbalota es sorteos/16, aparte de los números.
4. **Resumen de Producto 1:** las apariciones de cada número coinciden con las
   del resumen, que es un cálculo independiente que ya existía.
5. **Repetición de superbalota:** las transiciones válidas más las excluidas
   por hueco suman sorteos − 1.
6. **p-values:** la uniformidad declara p-value asintótico. En correlaciones, la
   suma no tiene p-value y las mitades usan permutación Monte Carlo (39 o 43
   números) o exacta (ColorLoto, 5040 ordenaciones). El número × color de
   ColorLoto declara p-value asintótico.
7. **ColorLoto:** las balotas de cada número suman 6 × los sorteos del año.
8. **No aplica:** la superbalota en MiLoto responde 404 con su motivo.

```powershell
function Leer([string]$ruta) {
    # GET a la API local; el JSON se decodifica como UTF-8 (la respuesta no declara charset)
    $r = Invoke-WebRequest -UseBasicParsing -Uri ('http://127.0.0.1:8005{0}' -f $ruta)
    if ($r.StatusCode -ne 200) { throw ('{0} respondió {1}' -f $ruta, $r.StatusCode) }
    return ([Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()) | ConvertFrom-Json)
}
function Comprobar([string]$texto, [bool]$correcto) {
    if (-not $correcto) { throw ('REVISAR: {0}' -f $texto) }
    'OK  {0}' -f $texto
}
function Tabla($metrica, [string]$id) { return @($metrica.tablas | Where-Object { $_.id -eq $id })[0] }

$codigos = @('BALOTO', 'BALOTO_REVANCHA', 'MILOTO', 'COLORLOTO')
$muestras = @{}
foreach ($c in $codigos) {
    $m = (Leer "/api/estadisticas/$c/panel").muestra
    $muestras[$c] = $m
    if ($m.total_sorteos -lt 1) { throw ('{0} no tiene sorteos cargados: sincroniza antes de validar' -f $c) }
    '{0}: {1} sorteos ({2}-{3}, {4} a {5}); huecos: {6}; {7}' -f $c, $m.total_sorteos, $m.periodo.primer_sorteo,
        $m.periodo.ultimo_sorteo, $m.periodo.primera_fecha, $m.periodo.ultima_fecha, $m.huecos.cantidad, $m.frescura.mensaje
}

foreach ($c in @('BALOTO', 'BALOTO_REVANCHA', 'MILOTO')) {
    $total = [int]$muestras[$c].total_sorteos
    $corte = [int]$muestras[$c].periodo.ultimo_sorteo - 10
    $sumas = Leer "/api/estadisticas/$c/descriptivas/distribucion-sumas?hasta_numero_sorteo=$corte"
    $enHistograma = (@((Tabla $sumas.metrica 'histograma').filas | ForEach-Object { [int]$_.sorteos }) | Measure-Object -Sum).Sum
    Comprobar ('{0} sumas, corte {1}: {2} sorteos en la muestra y en el histograma; último {3}' -f $c, $corte,
        $sumas.muestra.total_sorteos, $sumas.muestra.periodo.ultimo_sorteo) (($enHistograma -eq $sumas.muestra.total_sorteos) -and ($sumas.muestra.periodo.ultimo_sorteo -le $corte))

    $decenas = (Leer "/api/estadisticas/$c/descriptivas/distribucion-decenas").metrica
    $filas = @((Tabla $decenas 'decenas').filas)
    $apariciones = ($filas | ForEach-Object { [int]$_.apariciones } | Measure-Object -Sum).Sum
    $porcentaje = ($filas | ForEach-Object { [double]$_.pct_extraidos } | Measure-Object -Sum).Sum
    Comprobar ('{0} decenas: {1} apariciones = {2} sorteos x 5; % suma {3:N2}' -f $c, $apariciones, $total, $porcentaje) (($apariciones -eq 5 * $total) -and ([math]::Abs($porcentaje - 100) -lt 1e-6))

    $unif = (Leer "/api/estadisticas/$c/descriptivas/pruebas-uniformidad").metrica
    $resumen = @((Tabla $unif 'resumen').filas)
    $n = if ($c -eq 'MILOTO') { 39 } else { 43 }
    Comprobar ('{0} uniformidad: esperado por número {1:N3} = {2} x 5/{3}' -f $c, $resumen[0].esperado, $total, $n) ([math]::Abs($resumen[0].esperado - $total * 5 / $n) -lt 1e-9)
    '    chi2 = {0:N2}, gl = {1}, p = {2:N4}' -f $resumen[0].estadistico, $resumen[0].grados_libertad, $resumen[0].p_value
    Comprobar ('{0} uniformidad: p-value asintótico declarado en las {1} filas' -f $c, $resumen.Count) (@($resumen | Where-Object { $_.tipo_p_value -ne 'asintotico' }).Count -eq 0)
    $fc = @((Tabla (Leer "/api/estadisticas/$c/descriptivas/correlaciones").metrica 'correlaciones').filas)
    Comprobar ('{0} correlación de la suma: coeficiente {1:N3} y sin p-value (transiciones que comparten sorteos)' -f $c, $fc[0].coeficiente) ((@($fc[0..1] | Where-Object { $null -ne $_.p_value }).Count -eq 0) -and ($fc[0].motivo_p_value -like '*comparten*'))
    Comprobar ('{0} mitades: permutación Monte Carlo sobre {1} números; p Pearson {2:N4}, p Spearman {3:N4}' -f $c, $fc[2].n, $fc[2].p_value, $fc[3].p_value) ((@($fc[2..3] | Where-Object { $_.contraste -ne 'permutacion_monte_carlo' -or $_.permutaciones -ne 9999 }).Count -eq 0) -and ($fc[2].n -eq $n))
    if ($c -ne 'MILOTO') {
        Comprobar ('{0} uniformidad superbalota aparte: esperado {1:N3} = {2}/16' -f $c, $resumen[1].esperado, $total) ([math]::Abs($resumen[1].esperado - $total / 16) -lt 1e-9)
        $rep = (Leer "/api/estadisticas/$c/descriptivas/repeticion-superbalota").metrica
        $transiciones = (@((Tabla $rep 'repeticion').filas | ForEach-Object { [int]$_.transiciones }) | Measure-Object -Sum).Sum
        $excluidas = [int](@($rep.indicadores | Where-Object { $_.etiqueta -like 'Excluidas*' })[0].valor)
        Comprobar ('{0} repetición de superbalota: {1} transiciones + {2} excluidas = {3} - 1' -f $c, $transiciones, $excluidas, $total) (($transiciones + $excluidas) -eq ($total - 1))
    }

    $p1 = Leer "/api/estadisticas/$c/resumen"
    $observados = @{}
    foreach ($f in (Tabla $unif 'numeros').filas) { $observados["$($f.valor)"] = [int]$f.observado }
    $distintos = @($p1.estadisticas.frecuencia_numeros.todas | Where-Object { $observados["$($_.valor)"] -ne [int]$_.apariciones })
    Comprobar ('{0}: apariciones por número iguales a las del resumen de Producto 1 ({1} números)' -f $c, $observados.Count) ($distintos.Count -eq 0)
}

$anio = ([datetime]$muestras['COLORLOTO'].periodo.ultima_fecha).Year
$cl = (Leer "/api/estadisticas/COLORLOTO/descriptivas/frecuencia-numeros-por-anio?anio=$anio").metrica
$balotas = (@((Tabla $cl 'frecuencia').filas | ForEach-Object { [int]$_.apariciones }) | Measure-Object -Sum).Sum
$sorteosAnio = [int](@($cl.indicadores | Where-Object { $_.etiqueta -eq 'Sorteos en el periodo' })[0].valor)
Comprobar ('COLORLOTO {0}: {1} balotas = 6 x {2} sorteos del año' -f $anio, $balotas, $sorteosAnio) ($balotas -eq 6 * $sorteosAnio)
$ccl = (Leer '/api/estadisticas/COLORLOTO/descriptivas/correlaciones').metrica
$fcl = @((Tabla $ccl 'correlaciones').filas)
Comprobar ('COLORLOTO mitades: permutación exacta de {0} ordenaciones (7 números); p Spearman {1:N4}' -f $fcl[3].permutaciones, $fcl[3].p_value) (@($fcl[2..3] | Where-Object { $_.contraste -ne 'permutacion_exacta' -or $_.permutaciones -ne 5040 }).Count -eq 0)
Comprobar 'COLORLOTO numero x color: p-value asintótico declarado' ((Tabla $ccl 'contingencia').nota -like '*asint*')

try {
    Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8005/api/estadisticas/MILOTO/descriptivas/atrasos-superbalota' | Out-Null
    throw 'REVISAR: la superbalota de MiLoto no respondió 404'
} catch [System.Net.WebException] {
    Comprobar 'MiLoto sin superbalota: 404 con motivo' ([int]$_.Exception.Response.StatusCode -eq 404)
} catch {
    if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 404) { Comprobar 'MiLoto sin superbalota: 404 con motivo' $true } else { throw }
}
'Comprobaciones terminadas. Corte de prueba usado: último sorteo de cada juego menos 10.'
```

Envíame la salida completa. Una línea `REVISAR` detiene el bloque: copia la
línea y lo anterior.

## 4. Recorrido en el navegador

Abre `http://localhost:8005/estadisticas` y, en cada juego, «Panel completo».
En cada panel:

1. **Muestra:** comprueba que las cifras de la cabecera coinciden con las de la
   salida del bloque: sorteos, período y frescura.
2. **Corte:** aplica el corte del bloque (último sorteo − 10). La cabecera debe
   decir «hasta el sorteo N» y todas las cifras deben cambiar a la vez.
   «Histórico completo» lo quita.
3. **Enlaces:** abre al menos una página «Fase 5» de cada grupo. Comprueba que
   la gráfica y la tabla tienen los mismos valores (la leyenda dice qué
   columna). Comprueba también que el corte se conserva al navegar dentro del
   juego y se pierde al cambiar de juego.
4. **Lo que no aplica:** en MiLoto, las filas de superbalota dicen «No aplica»
   con su motivo. En ColorLoto pasa lo mismo con las decenas, la independencia
   y la superbalota.
5. **Páginas anteriores:** abre, por ejemplo, `/estadisticas/baloto/frecuencia-numeros`
   y `/estadisticas/colorloto/frecuencia-colores`. Siguen iguales y muestran
   además la fila «Más estadísticas».
6. **p-values:** en `/estadisticas/baloto/correlaciones`, la columna «Cómo se
   obtiene el p-value» dice «No se calcula» en la suma y «Permutación Monte
   Carlo, B = 9999, semilla 5» en las mitades; en ColorLoto, «Permutación
   exacta, 5040 ordenaciones». En `pruebas-uniformidad`, la
   columna «Tipo de p-value» dice «asintótico (chi-cuadrado límite)».

Páginas para revisar a fondo (con el histórico real):

- `/estadisticas/baloto/pruebas-uniformidad`
- `/estadisticas/baloto/distribucion-decenas`
- `/estadisticas/baloto-revancha/atrasos-superbalota`
- `/estadisticas/miloto/frecuencia-numeros-por-mes`
- `/estadisticas/miloto/correlaciones`
- `/estadisticas/colorloto/correlaciones`
- `/estadisticas/colorloto/frecuencia-numeros-por-anio`
- `/estadisticas/baloto/comparacion-frecuencia-numeros-por-ventana?ventana=50`

## 5. Impresión

Usa la vista previa de impresión del navegador con márgenes por defecto. Imprime
a PDF el panel de Baloto, el de ColorLoto y las páginas de uniformidad y
decenas de Baloto en tres formatos:

- Carta vertical;
- Carta horizontal;
- A4 vertical.

Comprueba en cada PDF:

- no se imprimen la navegación ni los formularios;
- cada título va con su tabla;
- las cabeceras de tabla se repiten al pasar de página;
- ninguna gráfica pasa de media página;
- no hay filas tapadas ni recortadas.

La revisión registrada en el apartado 6 se hizo con PDF en A4 y Legal; Carta no
se revisó en Windows.

## 6. Validación registrada (v2)

Cada entorno por separado. Validar el funcionamiento no acredita ventaja
predictiva, y un p-value alto no demuestra que el sorteo sea aleatorio.

**Windows** (operador, Python 3.14.6):

- Fase 5: `94 passed`.
- Producto 6 `73 passed`, Producto 5 `96 passed`, Producto 4 `94 passed` y
  Productos 1 a 3 `225 passed`.
- Selección filtrada de Windows: `2130 passed`.
- Demostraciones con datos sintéticos (no son evidencia del histórico real):
  Fase 5 8/8 y Producto 6 9/9.
- OpenSSL en modo `exigir`: `SUPERADOS 7/7`.
- `pip check` y comprobación de espacios limpios.
- Aviso conocido `StarletteDeprecationWarning` (`httpx` en `TestClient`): es un
  aviso, no un fallo.
- La suite completa no se ejecutó en Windows.

**Histórico real** (operador, en Windows; solo lectura). El bloque de
comprobaciones del apartado 3 terminó correctamente sobre estas muestras, sin
huecos de numeración dentro de ellas:

| Juego | Sorteos | Numeración | Fechas |
|---|---:|---|---|
| Baloto y Baloto Revancha | 639 | 2081–2719 | 2021-05-01 a 2026-10-07 |
| MiLoto | 89 | 532–620 | 2026-05-07 a 2026-10-08 |
| ColorLoto | 225 | 1–225 | 2024-08-15 a 2026-10-08 |

Se comprobaron los cortes reales, los histogramas de sumas, los denominadores de
las decenas, los esperados de uniformidad, la superbalota separada, las
transiciones y la equivalencia de frecuencias con Producto 1. Interpretación:

- el chi-cuadrado (uniformidad y número × color) da un p-value asintótico;
- la correlación de la suma con la del sorteo anterior es descriptiva y no
  tiene p-value;
- la comparación entre mitades usa permutación exacta en ColorLoto y Monte
  Carlo reproducible (9999 ordenaciones, semilla 5) en Baloto, Revancha y
  MiLoto;
- ninguna de estas cifras es una probabilidad del próximo sorteo ni una
  ventaja predictiva.

**Impresión** (PDF generados por el operador en Windows, en A4 y Legal; ninguno
en Carta). Son 14 PDF; sus 51 páginas se renderizaron y revisaron con ChatGPT
sin encontrar recortes, filas ausentes ni solapamientos visibles:

| Página | Formatos (páginas) |
|---|---|
| Panel de Baloto | A4 vertical (4), A4 horizontal (5), Legal vertical (3) |
| Panel de ColorLoto | A4 vertical (4), Legal vertical (4), Legal horizontal (5) |
| Uniformidad de Baloto | A4 vertical (4), A4 horizontal (6), Legal vertical (4) |
| Decenas de Baloto | A4 vertical (2), A4 horizontal (3), Legal vertical (2) |
| Correlaciones de ColorLoto | A4 horizontal (3) |
| Correlaciones de MiLoto | A4 horizontal (2) |

- Las tablas de uniformidad conservan las 43 filas de números y las 16 de
  superbalota en los tres formatos.
- Las cinco franjas de decenas tienen valores idénticos en los tres formatos y
  suman 3195 apariciones y 100 %.
- Cinco de esos PDF (las tres decenas y las dos correlaciones, 12 páginas) se
  cotejaron además con Claude: mismos formatos y páginas, las cifras de
  decenas (en Legal la tabla se parte con la cabecera repetida) y las columnas
  de la v2 en las correlaciones.
- La revisión se limita a esas páginas y formatos: no cubre Carta ni el resto
  de páginas de la aplicación.

**Linux** (Cloud, Python 3.11.15, solo fixtures sintéticas): Fase 5 `94 passed`,
selección filtrada `2130 passed`, suite completa `6375 passed` sin fallos ni
omisiones, OpenSSL `SUPERADOS 7/7` y demostraciones 8/8 y 9/9.

**GitHub Actions:** todavía no ha ejecutado esta entrega.

Sigue vigente que las páginas estadísticas anteriores a la Fase 5 ya
desbordaban a 390 px de ancho, sin relación con esta fase. Este cierre no
cambia `experimental_no_acreditado`, el NO-GO ni `AUTORIZA_EVALUACION = False`.

## 7. Si repites la validación

La fase ya está completa con la evidencia del apartado 6. Si repites los pasos 1
a 5 (por ejemplo, con un histórico más reciente), envíame la salida del bloque
de comprobaciones, los PDF o capturas y cualquier diferencia que veas: se
registraría aparte, sin reescribir la evidencia anterior. GitHub Actions se
registrará por separado cuando haya una ejecución real.

## Límites

- **Pruebas estadísticas:** son descriptivas. Con varias pruebas a la vez,
  alguna sale con p bajo por azar.
- **Chi-cuadrado sin reemplazo:** en los juegos que sacan números distintos el
  estadístico se multiplica por (N−1)/(N−K), que corrige su escala frente a la
  aproximación multinomial. El p-value sigue siendo asintótico, no exacto para
  una muestra finita, y con frecuencias esperadas menores que 5 la página
  avisa.
- **ColorLoto:** las pruebas suponen balotas independientes y uniformes,
  supuesto que no se ha verificado con el reglamento.
- **Independencia de pares y tríos:** no se calcula en ColorLoto por la misma
  razón ya documentada en `motor/independencia.py`.
- **Distancias:** los intervalos y atrasos se miden en numeración de sorteos.
  Un hueco de importación alarga los que lo cruzan, y la página lo avisa.
