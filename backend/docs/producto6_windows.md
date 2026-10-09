# Producto 6 en Windows: centro de resultados y evaluación continua de modelos

**Estado: validado localmente en Windows con histórico real** (versión v2), con
la revisión de los PDF reales adjuntos (resumen al final). GitHub Actions
todavía no lo ha ejecutado. Los pronósticos siguen
`experimental_no_acreditado`, con el NO-GO vigente y
`AUTORIZA_EVALUACION = False`. Las cifras de `/resultados` describen objetivos
ya observados: no son una recomendación de apuesta ni demuestran ventaja futura.
En la evaluación real de Producto 5 la uniforme tuvo menor pérdida que el modelo
combinado en los cuatro juegos; esta página no cambia esa conclusión.

Esta guía usa el equipo del operador:

- worktree de Producto 6: `C:\GitHub\loteria-predictor-producto6`;
- intérprete: `$env:LOCALAPPDATA\loteria-predictor-venvs\ae68\Scripts\python.exe`;
- puerto sugerido: **8005** (Producto 5 puede seguir en 8004).

La instalación, los tamaños y los SHA-256 están en la guía de entrega externa
y en `aplicar-producto6-windows.ps1`. Este documento forma parte del parche,
así que no repite esas cifras.

## Qué lee y qué escribe

`/resultados` LEE los almacenes de Productos 1-3 (`DIRECTORIO_PRONOSTICOS_EXPERIMENTALES`),
4 (`DIRECTORIO_LABORATORIO_MODELOS`) y 5 (`DIRECTORIO_CARTERAS_MODELOS`) y el
histórico de PostgreSQL con una transacción de solo lectura. Solo escribe en
dos casos, siempre por un botón o una orden explícitos:

- «Guardar informe»: en `DIRECTORIO_RESULTADOS_MODELOS` (por defecto
  `storage\resultados`), su almacén propio;
- «Usar esta configuración»: una versión nueva de la configuración de carteras
  de Producto 5, con su propio caso de uso.

## Dos ventanas y el bloque de sesión

Usa dos ventanas de Windows PowerShell 5.1:

- **Ventana A (servidor):** solo mantiene Uvicorn en marcha; no la uses para
  comandos.
- **Ventana B (comandos):** la línea de comandos `scripts.resultados_modelos`.

Las variables de entorno prevalecen sobre `.env`, y tu sesión puede traer rutas
de productos anteriores. Pega este bloque en las DOS ventanas antes de nada:
fija las cinco rutas DENTRO del worktree de Producto 6 (rutas absolutas), la
codificación UTF-8 y dos funciones de apoyo.

```powershell
$wt = 'C:\GitHub\loteria-predictor-producto6'
$py = Join-Path $env:LOCALAPPDATA 'loteria-predictor-venvs\ae68\Scripts\python.exe'
$env:PYTHONIOENCODING = 'utf-8'; $env:PYTHONUTF8 = '1'
[Console]::OutputEncoding = [Text.Encoding]::UTF8; $OutputEncoding = [Text.Encoding]::UTF8
$env:DIRECTORIO_PRONOSTICOS_EXPERIMENTALES = Join-Path $wt 'backend\storage\pronosticos'
$env:DIRECTORIO_OPERACION = Join-Path $wt 'backend\storage\operacion'
$env:DIRECTORIO_LABORATORIO_MODELOS = Join-Path $wt 'backend\storage\laboratorio'
$env:DIRECTORIO_CARTERAS_MODELOS = Join-Path $wt 'backend\storage\carteras'
$env:DIRECTORIO_RESULTADOS_MODELOS = Join-Path $wt 'backend\storage\resultados'
Set-Location (Join-Path $wt 'backend')
function Revisar([string]$paso) { if ($LASTEXITCODE -ne 0) { throw ('{0} falló (código {1})' -f $paso, $LASTEXITCODE) } }
function Resultados([string[]]$argumentos, [int[]]$admitidos = @(0)) {
    # Ejecuta el comando, comprueba su código ANTES de leer el JSON y devuelve código y datos
    $salida = & $py -m scripts.resultados_modelos @argumentos
    $codigo = $LASTEXITCODE
    if ($admitidos -notcontains $codigo) { throw ('resultados_modelos {0} terminó con el código {1}' -f ($argumentos -join ' '), $codigo) }
    return [pscustomobject]@{ Codigo = $codigo; Datos = (($salida | Out-String) | ConvertFrom-Json) }
}
$rutas = (Resultados @('rutas')).Datos
$rutas
foreach ($propiedad in $rutas.PSObject.Properties) {
    if ($propiedad.Name -like 'directorio_*_modelos' -or $propiedad.Name -eq 'directorio_pronosticos_experimentales') {
        if (-not "$($propiedad.Value)".StartsWith((Join-Path $wt 'backend\storage'), [StringComparison]::OrdinalIgnoreCase)) {
            throw ('{0} sale del worktree de Producto 6' -f $propiedad.Name)
        }
    }
}
'Rutas dentro de {0}' -f $wt
```

`rutas` muestra las carpetas efectivas (nunca `DATABASE_URL` ni `.env`); el
bloque se detiene si alguna sale del worktree de Producto 6.

### Partir de las emisiones que ya tienes (copia, nunca mover)

Un worktree nuevo empieza con los almacenes vacíos. Para ver tus emisiones
reales sin tocar las de Producto 5, COPIA sus almacenes al worktree de
Producto 6 solo si las carpetas de destino están vacías (los artefactos son
inmutables y llevan su huella, así que la copia se verifica igual):

```powershell
$origen = 'C:\GitHub\loteria-predictor-producto5\backend\storage'
foreach ($nombre in @('pronosticos', 'operacion', 'laboratorio', 'carteras')) {
    $de = Join-Path $origen $nombre
    $a = Join-Path "$wt\backend\storage" $nombre
    $hay = @(Get-ChildItem -LiteralPath $a -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne '.gitkeep' })
    if ($hay.Count -gt 0) { "${nombre}: el destino ya tiene datos; no se copia"; continue }
    if (-not (Test-Path -LiteralPath $de)) { "${nombre}: no existe en Producto 5"; continue }
    New-Item -ItemType Directory -Force -Path $a | Out-Null
    Copy-Item -Path (Join-Path $de '*') -Destination $a -Recurse
    "${nombre}: copiado"
}
```

El worktree de Producto 5 no cambia. Desde aquí, la operación diaria, el
laboratorio y las carteras de este worktree escriben en sus propias copias.

Si el worktree de Producto 5 no tiene alguno de esos almacenes, los informes
salen parciales. En el recorrido real faltaban artefactos de la operación diaria
y del laboratorio: se completaron copiando 28 archivos de pronósticos desde el
worktree de Producto 3 y 30 de laboratorio desde el de Producto 4, con la misma
regla (copiar, nunca mover; comprobar el SHA-256 de origen y destino; no
sobrescribir un archivo distinto).

## Arranque (ventana A)

En la ventana A, después del bloque de sesión:

```powershell
& $py -m uvicorn app.main:app --host 127.0.0.1 --port 8005
```

Déjala abierta. Abre `http://localhost:8005/resultados` en esta misma máquina
(los botones que escriben solo funcionan desde `localhost` y con el token de la
página). Para detener el servidor, `Ctrl+C` en la ventana A.

## Recorrido visual

1. **Índice** (`/resultados`): por juego, último sorteo cargado y su fecha,
   emisiones de seguimiento incluidas, pendientes y excluidas, y la
   disponibilidad de las tres procedencias. Si la base no responde, lo dice y no
   inventa un último resultado.
2. **Detalle** (`/resultados/miloto`, `/resultados/colorloto`, `/resultados/baloto`,
   `/resultados/baloto-revancha`):
   - filtros: procedencias, líneas (versión y configuración), tipo de emisión,
     intervalo «desde/hasta» u objetivo concreto, y carteras;
   - si el tipo seguimiento no tiene resultados, un aviso con el enlace a
     «retrospectiva» (el tipo no cambia solo);
   - resumen por línea, comparación directa sobre la muestra común (con la
     uniforme en la clasificación, también cuando gana) o «sin muestra común»;
   - evolución (gráfica y tabla con los mismos puntos), calibración (curva con
     diagonal y tabla con predicciones y sorteos distintos), historial paginado
     con enlace al artefacto original, y la sección de carteras;
   - «Exportar CSV/JSON» (todas las emisiones filtradas, no solo la página) y
     «Guardar informe».
3. **Informe guardado**: filtros, base al guardar, cálculos congelados
   (probabilidades, resultados observados y combinaciones de las carteras) y
   artefactos de origen; «Verificar» separa integridad, reproducción por partes
   (modelos y carteras) y coincidencia con la consulta actual, que compara
   también el resultado observado y cada cartera. Tras cargar o corregir un
   sorteo, un informe anterior sigue íntegro y reproducible, pero «la consulta
   actual cambió».
4. **Usar esta configuración** (sección Carteras): vista previa con la
   configuración propuesta y la vigente; «Guardar como configuración vigente»
   crea una versión nueva en Producto 5 sin entrenar. Repetirlo dice «ya es la
   vigente».

Imprime o guarda como PDF el detalle de un juego y un informe en Carta vertical,
Carta horizontal y A4 vertical, y revisa: filas completas, cabeceras de tabla
repetidas, gráficas legibles, sin solapamientos ni páginas iniciales casi vacías.

## Comandos con el histórico real (ventana B)

En la ventana B, después del bloque de sesión. Cada paso comprueba el código de
salida antes de interpretar el JSON y trata cada código según su contrato.

```powershell
# Índice: 0 correcto; 3 = la base no responde (se muestra lo guardado, sin inventar un último resultado)
$indice = Resultados @('indice') @(0, 3)
if ($indice.Codigo -eq 3) { 'AVISO: base no disponible; revisa DATABASE_URL en backend\.env' }
$indice.Datos.juegos | Select-Object juego, @{ n = 'ultimo_sorteo'; e = { $_.base.ultimo_sorteo } },
    @{ n = 'fecha'; e = { $_.base.fecha } }, @{ n = 'incluidas'; e = { $_.seguimiento.incluido } },
    @{ n = 'pendientes'; e = { $_.seguimiento.pendiente } } | Format-Table -AutoSize

# Consulta de MiLoto (primera página del historial) y retrospectiva por separado
$miloto = Resultados @('consultar', '--juego', 'MILOTO', '--por-pagina', '5') @(0, 3)
'MiLoto: líneas elegidas {0}; comparación {1}' -f (@($miloto.Datos.seleccion) -join ', '), $miloto.Datos.comparacion.estado
$retro = Resultados @('consultar', '--juego', 'MILOTO', '--tipo', 'retrospectiva', '--por-pagina', '5') @(0, 3)
'Retrospectiva: {0} fila(s)' -f $retro.Datos.historial.total

# Exportación CSV completa (todas las filas filtradas) a Descargas
$csv = Join-Path $env:USERPROFILE 'Downloads\resultados-colorloto.csv'
& $py -m scripts.resultados_modelos exportar --juego COLORLOTO --formato csv | Set-Content -Encoding UTF8 -LiteralPath $csv
Revisar 'exportar'
'CSV: {0}' -f $csv

# Guardar un informe y verificar ESA clave (no hay que copiarla a mano)
$guardado = Resultados @('guardar', '--juego', 'BALOTO') @(0, 5)
if ($guardado.Codigo -eq 5) { 'Informe PARCIAL (se conserva con sus limitaciones): {0}' -f (@($guardado.Datos.limitaciones) -join '; ') }
$clave = $guardado.Datos.clave
'Informe {0} (reutilizado: {1})' -f $clave, $guardado.Datos.reutilizado
$verificacion = Resultados @('verificar', '--clave', $clave) @(0, 5, 7, 8)
switch ($verificacion.Codigo) {
    0 { 'Íntegro, reproducción exacta y coincide con la consulta actual' }
    5 { 'Íntegro (no es una alteración); reproducción {0}; consulta actual: {1}' -f $verificacion.Datos.reproduccion.estado, $verificacion.Datos.base_actual.estado }
    7 { throw 'La reproducción del cálculo congelado NO es exacta: envía esta salida' }
    8 { throw 'El archivo del informe está alterado o ilegible' }
}

# El informe más reciente de un juego, desde la lista (sin copiar claves)
$lista = Resultados @('informes', '--juego', 'BALOTO')
$reciente = @($lista.Datos.informes | Where-Object { $_.integridad -eq 'correcta' }) | Select-Object -First 1
if ($reciente) { 'Más reciente: {0} ({1})' -f $reciente.clave, $reciente.guardado_en }

# Vista previa de «usar esta configuración» con una línea de cartera real (no escribe)
$colorloto = Resultados @('consultar', '--juego', 'COLORLOTO', '--procedencia', 'carteras', '--por-pagina', '1') @(0, 3)
$lineas = @($colorloto.Datos.carteras.disponibles | Where-Object { $_ })
if ($lineas.Count -eq 0) { 'ColorLoto no tiene carteras: genera una en /carteras antes de la vista previa' }
else {
    $previa = Resultados @('configuracion', '--juego', 'COLORLOTO', '--linea', $lineas[0])
    $previa.Datos.propuesta | Format-List
    'Compatible: {0}; ya vigente: {1}' -f $previa.Datos.compatible, $previa.Datos.ya_vigente
}
```

Para GUARDAR esa configuración como versión nueva (escribe en Producto 5, no
entrena; repetirlo responde `ya_vigente`), en la misma ventana B:

```powershell
$uso = Resultados @('configurar', '--juego', 'COLORLOTO', '--linea', $lineas[0])
'Configuración: {0} (versión {1}, línea {2})' -f $uso.Datos.estado, $uso.Datos.version, $uso.Datos.linea
```

Códigos de salida del comando: 0 éxito; 2 uso incorrecto o identificador no
encontrado; 3 base o almacén no disponibles (se muestra lo guardado); 5 informe
parcial, partes no verificables o consulta actual distinta, no disponible o no
comparable (no es una alteración); 7 reproducción no exacta; 8 archivo alterado.
`consultar`, `exportar`, `informes`, `informe`, `verificar` y `configuracion` no
escriben.

## Límites

- La unidad es la PRIMERA emisión sellada de cada procedencia, línea y objetivo;
  las versiones posteriores se ven en su flujo, pero no se evalúan.
- Una diferencia en pocos objetivos puede ser azar; el aviso «muestra pequeña»
  aparece por debajo de 10 objetivos. No hay pruebas de significación.
- «El objetivo no estaba cargado al emitir» describe la base local; no acredita
  que la emisión precediera al sorteo real. Una huella SHA-256 local no es una
  firma externa ni una prueba de anterioridad.
- La calibración y las diferencias frente a la uniforme son descriptivas y se
  calculan sobre muestras pequeñas; no autorizan un uso operativo nuevo.

## Validación en Windows (resumen)

Evidencia del operador sobre la v2 (parche de 338014 bytes; manifiesto de
10145 bytes). Separada de Linux y de GitHub Actions.

- **Entorno:** Git 2.54.0.windows.1, Python 3.14.6 y OpenSSL 3.5.6 de Git para
  Windows.
- **Aplicación:** parche y manifiesto comprobados por tamaño y SHA-256; los 44
  archivos coinciden con el manifiesto (43 equivalentes al normalizar CRLF/LF
  solo en memoria y 1 byte a byte); espacios limpios con índice temporal; índice
  real intacto y sin commits nuevos.
- **Pruebas:** Producto 6 `73 passed`, Producto 5 `96 passed`, Producto 4
  `94 passed`, Productos 1 a 3 `225 passed`, selección de Windows (81 entradas)
  `2036 passed`, OpenSSL `SUPERADOS 7/7` (`exigir`) y `pip check` limpio. La
  demostración (9/9) usa datos sintéticos, no el histórico real. Aparece el
  aviso conocido `StarletteDeprecationWarning` (httpx en `TestClient`), que no
  es un fallo. La suite completa no se ejecutó en Windows. Registro:
  `%TEMP%\p6-evidencia-20261009-005016-894e9b8e`.
- **Histórico real** (registro `%TEMP%\p6-real-20261009-012540-519844ea`):
  Baloto y Revancha con 639 sorteos (último 2719, 2026-10-07), MiLoto con 89
  (último 620, 2026-10-08) y ColorLoto con 225 (último 225, 2026-10-08); las tres
  procedencias disponibles en los cuatro juegos; el índice muestra por juego 7
  emisiones de seguimiento incluidas, 0 pendientes y 0 excluidas sobre 3
  objetivos distintos (emisiones, no sorteos independientes). Con la selección
  del recorrido, el seguimiento dio muestra común, informe completo,
  reproducción exacta y consulta actual coincidente (código 0) en los cuatro
  juegos; la retrospectiva dio «sin muestra común» e informe parcial,
  legítimamente, sin retirar líneas ni cambiar de tipo. Repetir la misma
  fotografía reutilizó el informe en las ocho consultas; los 128 archivos
  previos comprobados quedaron intactos; las vistas previas de configuración
  fueron compatibles y no vigentes, y no se aplicó ninguna. No se importó,
  entrenó ni reentrenó.
- **PDF reales** (Chrome 154; revisados por el operador y ChatGPT): índice,
  Baloto y ColorLoto en Carta vertical; informe de Baloto en Carta vertical,
  Carta horizontal y A4 vertical; verificación en Carta horizontal. Sin
  solapamientos, filas tapadas ni recortes. En Baloto (objetivo 2719) la
  uniforme fue mejor; en ColorLoto (objetivo 225) el modelo combinado tuvo menor
  pérdida solo en ese objetivo, sin ventaja demostrada. El informe
  `c0568aceb510def0280acb6cab7def694b8a8145c6ad8dc5aa86499ef387dc0a` verificó
  integridad, reproducción exacta (5 emisiones y 2 pares cartera-objetivo) y
  coincidencia con la consulta actual. No se revisaron aquí las pantallas de
  Revancha y MiLoto.
- **Pendiente:** la ejecución de GitHub Actions.
