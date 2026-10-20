# Fase 3 en Windows: modelos entrenados, versionados y reutilizables

**Antecedente histórico:** la entrega original Fase 3 culminó en PR #92; Daniel validó en Windows sus ajustes de cierre (81 focales, selección 2215, OpenSSL 7/7 y PDF Legal vertical), según la evidencia ya registrada en README/ROADMAP. Las ejecuciones Actions 47, 48 y 49 fueron verdes. PR #94 incorporó después Fase 4 y su cierre: Actions `38982578601` pasó Linux completo y Windows selección, según lo aportado por Daniel. No equivale a suite completa Windows.

**Estado vigente ML v3.2:** cinco familias reales implementadas y validadas localmente en los cuatro juegos sobre base `90e6ab06b2a188fde9416fb0aac9e7366b7b04a6`. Daniel utilizó `C:\GitHub\loteria-predictor-ml-cierre` y `C:\GitHub\venvs\loteria-ml-cierre\Scripts\python.exe`: suite completa nativa sin selección **7.015 aprobadas, cero fallos, errores u omisiones**, focal previa **109** solapada, OpenSSL `exigir` **7/7**, demostración **20/20** y `pip check` correcto. El recorrido real registró 20 modelos, 40 pronósticos congelados y cinco carteras/explicaciones persistentes tras reiniciar. ChatGPT auditó las evidencias y la impresión indicada abajo. Véanse [métodos y validación local](ml_cinco_familias.md#validación-local-completada-de-ml-v32). Solo quedan aplicar/verificar el nuevo cierre documental en PowerShell 5.1 y Actions del futuro PR; la acreditación prospectiva permanece separada. La guía histórica siguiente conserva el entorno anterior como referencia; no es una orden para regenerar, reentrenar ni repetir baterías aprobadas.

Completar la ingeniería no acredita ventaja predictiva: los pronósticos siguen
`experimental_no_acreditado`, con el NO-GO vigente y
`AUTORIZA_EVALUACION = False`. Ningún modelo pasa solo a la operación diaria;
elegir una versión es una acción explícita.

Esta guía usa el equipo del operador:

- worktree de la Fase 3: `C:\GitHub\loteria-predictor-fase3`;
- intérprete: `$env:LOCALAPPDATA\loteria-predictor-venvs\ae68\Scripts\python.exe`;
- puerto sugerido: **8006** (Producto 6 puede seguir en 8005).

La instalación, los tamaños y los SHA-256 están en la guía de entrega externa
y en `aplicar-fase3-windows.ps1`. Este documento forma parte del parche, así
que no repite esas cifras.

## Qué añade

- **Random Forest y Extra Trees** en el laboratorio de Producto 4. En Baloto,
  Revancha y MiLoto predicen la aparición de cada número
  (`random_forest_clasificador`, `extra_trees_clasificador`). En ColorLoto
  predicen el conteo de cada par número-color, con multiplicidad
  (`random_forest_poisson`, `extra_trees_poisson`).
  - Eligen `max_depth` y `min_samples_leaf` con una validación cronológica
    interna, solo con objetivos anteriores al bloque evaluado.
  - La evaluación final no interviene en esa elección.
  - Se comparan con los demás candidatos sobre los mismos cortes y objetivos:
    Log Loss, Brier, métricas secundarias y la uniforme como referencia.
- **Registro de versiones** en `storage\laboratorio\modelos\<JUEGO>\`. Cada
  versión tiene tres archivos:
  - el estimador `estimadores\<sha256>.pkl`, que se publica primero;
  - la reserva del número `<modelo>-<NNNNNN>.version`;
  - el manifiesto sellado `<clave>.json`, que se publica al final.

  El manifiesto guarda la identidad, la receta, los parámetros elegidos, la
  semilla, el entorno, el periodo y el corte, la huella del histórico, la
  evaluación asociada y el pronóstico de control. Una entrada idéntica
  reutiliza la versión; cualquier cambio crea otra. La carga comprueba antes el
  tamaño y el SHA-256 del estimador, la compatibilidad del entorno y que el
  archivo lo haya producido la aplicación (deserializador restringido).
- **Flujo visible**: comparar → «Entrenar y guardar versión» → ficha de la
  versión → «Verificar» → «Generar con el modelo cargado» (sin reentrenar) →
  resultados observados. Opcionalmente, «Elegir para la operación diaria…»
  lleva a la configuración de carteras de Producto 5.
- **Contrato de inferencia**: con un corte de entrada C (igual o posterior al
  de entrenamiento), las variables del objetivo C + 1 usan solo sorteos ≤ C.
  El estimador, su calibración si la tiene (los modelos Poisson de ColorLoto
  no la tienen: normalizan sus intensidades con código versionado) y los
  parámetros quedan congelados. Un corte
  anterior al de entrenamiento se rechaza, porque el modelo ya vio esos
  resultados.

## Qué escribe y qué no

| Acción | Escribe en |
|---|---|
| `comparar` / «Iniciar comparación nueva» | `storage\laboratorio` (informe) |
| `entrenar` / «Entrenar y guardar versión» | `storage\laboratorio\modelos` (versión) |
| `generar-con-modelo` / «Generar con el modelo cargado» | `storage\laboratorio` (pronóstico de la línea `…-reg<N>`) |
| `carteras_modelos configurar --registrado` / «Guardar como versión nueva» | `storage\carteras` (versión nueva de la configuración) |

Las páginas de consulta (GET), `modelos`, `modelo`, `verificar`, `seguimiento`
y `rutas` no escriben. Ninguna orden importa sorteos ni escribe en PostgreSQL.
Las tablas `modelos` y `metricas_modelo` de la Fase 1 no se rellenan: la ficha
muestra la proyección a sus columnas, y el manifiesto sellado es la única
fuente de la versión.

## 1. Sesión (en las dos ventanas)

Usa dos ventanas de Windows PowerShell 5.1:

- **Ventana A (servidor):** solo mantiene Uvicorn en marcha.
- **Ventana B (comandos):** las órdenes del recorrido.

Las variables de entorno prevalecen sobre `.env`, y tu sesión puede traer rutas
de entregas anteriores. Pega este bloque en las DOS ventanas antes de nada. El
bloque:

- comprueba que el worktree contiene la Fase 3;
- fija los cinco almacenes DENTRO del worktree, solo para esta sesión;
- fija la codificación UTF-8;
- define las funciones de apoyo;
- se detiene si alguna ruta sale del worktree.

```powershell
$wt = 'C:\GitHub\loteria-predictor-fase3'
if (-not (Test-Path -LiteralPath (Join-Path $wt 'backend\app\application\ml\modelos_registrados.py'))) { throw ('{0} no contiene la Fase 3' -f $wt) }
$py = Join-Path $env:LOCALAPPDATA 'loteria-predictor-venvs\ae68\Scripts\python.exe'
$env:PYTHONIOENCODING = 'utf-8'; $env:PYTHONUTF8 = '1'
[Console]::OutputEncoding = [Text.Encoding]::UTF8; $OutputEncoding = [Text.Encoding]::UTF8
$raiz = Join-Path $wt 'backend\storage'
$env:DIRECTORIO_PRONOSTICOS_EXPERIMENTALES = Join-Path $raiz 'pronosticos'
$env:DIRECTORIO_OPERACION = Join-Path $raiz 'operacion'
$env:DIRECTORIO_LABORATORIO_MODELOS = Join-Path $raiz 'laboratorio'
$env:DIRECTORIO_CARTERAS_MODELOS = Join-Path $raiz 'carteras'
$env:DIRECTORIO_RESULTADOS_MODELOS = Join-Path $raiz 'resultados'
Set-Location (Join-Path $wt 'backend')
function Revisar([string]$paso) { if ($LASTEXITCODE -ne 0) { throw ('{0} falló (código {1})' -f $paso, $LASTEXITCODE) } }
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
function Lab([string[]]$argumentos, [int[]]$admitidos = @(0)) { Orden 'scripts.laboratorio_modelos' $argumentos $admitidos }
function Carteras([string[]]$argumentos, [int[]]$admitidos = @(0)) { Orden 'scripts.carteras_modelos' $argumentos $admitidos }
function Huellas([string]$carpeta) {
    # SHA-256 de cada archivo, por ruta relativa (solo lee)
    $mapa = @{}
    if (Test-Path -LiteralPath $carpeta) {
        $base = (Resolve-Path -LiteralPath $carpeta).ProviderPath.TrimEnd('\')
        foreach ($archivo in @(Get-ChildItem -LiteralPath $base -Recurse -File -Force)) {
            $mapa[$archivo.FullName.Substring($base.Length + 1)] = (Get-FileHash -LiteralPath $archivo.FullName -Algorithm SHA256).Hash
        }
    }
    return $mapa
}
$rutasLab = (Lab @('rutas')).Datos
$rutasCarteras = (Carteras @('rutas')).Datos
foreach ($objeto in @($rutasLab, $rutasCarteras)) {
    foreach ($propiedad in $objeto.PSObject.Properties) {
        if ($propiedad.Name -like 'directorio_*' -and $propiedad.Name -ne 'directorio_de_trabajo') {
            '{0}: {1}' -f $propiedad.Name, $propiedad.Value
            if (-not "$($propiedad.Value)".StartsWith($raiz + '\', [StringComparison]::OrdinalIgnoreCase)) { throw ('{0} sale del worktree de la Fase 3' -f $propiedad.Name) }
        }
    }
}
'Rutas dentro de {0}' -f $raiz
# Presupuesto de Windows sin rutas largas: el pronostico de una version registrada mide la carpeta del laboratorio + ~147
$largo = "$($rutasLab.directorio_laboratorio_modelos)".Length
if ($largo -gt 111) { throw ('La carpeta del laboratorio mide {0} caracteres (maximo 111): sus pronosticos no cabrian en 259' -f $largo) }
```

`rutas` muestra las carpetas efectivas, nunca `DATABASE_URL` ni `.env`.
`directorio_modelos_registrados` es la carpeta del registro de versiones. La
carpeta del laboratorio de este worktree mide 61 caracteres, lejos del máximo
de 111.

## 2. Artefactos previos: copia opcional e instantánea SHA-256 (ventana B)

### Partir de las emisiones que ya tienes (copia, nunca mover)

Un worktree nuevo empieza con los almacenes vacíos. Para usar tus artefactos
reales sin tocar los del worktree de Producto 6, cópialos. El bloque solo copia
las carpetas de destino vacías y comprueba el SHA-256 de cada archivo copiado
contra su origen. El origen no cambia; el bloque lo comprueba al final.

```powershell
$origen = 'C:\GitHub\loteria-predictor-producto6\backend\storage'
$huellasOrigen = Huellas $origen
$copiadas = @()
foreach ($nombre in @('pronosticos', 'operacion', 'laboratorio', 'carteras', 'resultados')) {
    $de = Join-Path $origen $nombre
    $a = Join-Path $raiz $nombre
    $hay = @(Get-ChildItem -LiteralPath $a -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne '.gitkeep' })
    if ($hay.Count -gt 0) { "${nombre}: el destino ya tiene datos; no se copia"; continue }
    if (-not (Test-Path -LiteralPath $de)) { "${nombre}: no existe en el origen"; continue }
    New-Item -ItemType Directory -Force -Path $a | Out-Null
    Copy-Item -Path (Join-Path $de '*') -Destination $a -Recurse
    $copiadas += $nombre
    "${nombre}: copiado"
}
$destino = Huellas $raiz
foreach ($relativa in @($huellasOrigen.Keys)) {
    $carpeta = $relativa.Split('\')[0]
    if ($copiadas -contains $carpeta -and $destino[$relativa] -ne $huellasOrigen[$relativa]) { throw ('Copia distinta del origen: {0}' -f $relativa) }
}
$origenDespues = Huellas $origen
if ($origenDespues.Count -ne $huellasOrigen.Count) { throw 'El origen cambió durante la copia' }
foreach ($relativa in @($huellasOrigen.Keys)) { if ($origenDespues[$relativa] -ne $huellasOrigen[$relativa]) { throw ('El origen cambió: {0}' -f $relativa) } }
'Copia comprobada ({0} archivos en el origen, intacto)' -f $huellasOrigen.Count
```

### Instantánea antes de escribir

Antes de cualquier orden que escriba, registra el SHA-256 de todo lo que ya hay
en los almacenes del worktree. La carpeta de evidencia queda en `%TEMP%`, y
desde aquí cada orden guarda en ella su código y su salida JSON.

```powershell
$global:evidencia = Join-Path $env:TEMP ('f3-real-{0}-{1}' -f (Get-Date -Format 'yyyyMMdd-HHmmss'), [guid]::NewGuid().ToString('N').Substring(0, 8))
$global:pasoEvidencia = 0
New-Item -ItemType Directory -Path $global:evidencia | Out-Null
$antes = Huellas $raiz
[IO.File]::WriteAllLines((Join-Path $global:evidencia 'antes.sha256'), [string[]]@($antes.Keys | Sort-Object | ForEach-Object { '{0}  {1}' -f $antes[$_], $_ }))
'{0} archivos previos registrados; evidencia en {1}' -f $antes.Count, $global:evidencia
```

## 3. Recorrido con el histórico real (ventana B)

Todo el recorrido usa órdenes de línea de comandos, y cada orden es un proceso
Python nuevo. Por eso «cargar la versión» después de entrenar ya ocurre en otro
proceso: nada queda en memoria entre una orden y la siguiente.

### 3.1 Cortes tomados de la base

El corte de entrenamiento de cada juego es el sorteo cargado que queda cinco
objetivos evaluables antes del último. Sale de `diagnostico`, es decir, de la
base; no se inventa. Así quedan sorteos posteriores ya observados para
comprobar el pronóstico retrospectivo con el modelo cargado.

```powershell
$juegos = @('BALOTO', 'BALOTO_REVANCHA', 'MILOTO', 'COLORLOTO')
$elegidos = @{ BALOTO = 'random_forest_clasificador'; BALOTO_REVANCHA = 'extra_trees_clasificador'; MILOTO = 'random_forest_clasificador'; COLORLOTO = 'random_forest_poisson' }
$recorrido = [ordered]@{}
foreach ($juego in $juegos) {
    $d = (Lab @('diagnostico', '--juego', $juego)).Datos
    $objetivos = @($d.muestra.objetivos)
    if ($objetivos.Count -lt 7) { throw ('{0}: menos de 7 objetivos evaluables en la base' -f $juego) }
    $recorrido[$juego] = [ordered]@{ sorteos = [int]$d.datos.sorteos; ultimo = [int]$d.datos.ultimo_sorteo; corte = [int]$objetivos[-6]; anterior = [int]$objetivos[-7] }
    '{0}: {1} sorteos, último {2} ({3}); corte de entrenamiento {4}' -f $juego, $d.datos.sorteos, $d.datos.ultimo_sorteo, $d.datos.ultima_fecha, $objetivos[-6]
}
```

### 3.2 Comparar con corte explícito

La comparación incluye los cuatro bosques junto a los candidatos de Producto 4.
Puede tardar varios minutos por juego. El código 5 (algún candidato sin
evaluación completa) es admisible y queda registrado. Las incidencias son por
candidato y no bloquean a los demás.

```powershell
foreach ($juego in $juegos) {
    $r = $recorrido[$juego]
    $c = Lab @('comparar', '--juego', $juego, '--corte', [string]$r['corte']) @(0, 5)
    $j = $c.Datos.juegos.$juego
    if (-not $j.experimento) { throw ('{0}: la comparación no produjo informe ({1}: {2})' -f $juego, $j.estado, $j.mensaje) }
    $r['experimento'] = $j.experimento
    $informe = (Lab @('consultar', '--id', $j.experimento)).Datos.informe
    '{0}: informe {1} ({2}, código {3})' -f $juego, $j.experimento.Substring(0, 12), $j.estado, $c.Codigo
    @($informe.candidatos) | Where-Object { $_.familia -eq 'bosques' } |
        Select-Object id, estado, @{ n = 'dif_log_loss_vs_uniforme'; e = { $_.agregado.diferencia_log_loss } } | Format-Table -AutoSize
}
```

Una diferencia negativa indica menor pérdida que la uniforme en esa muestra.
No acredita ventaja futura; con sorteos reales se espera que la uniforme sea
difícil de batir.

### 3.3 Entrenar y guardar una versión

```powershell
$carpetaModelos = $rutasLab.directorio_modelos_registrados
foreach ($juego in $juegos) {
    $r = $recorrido[$juego]
    $t = (Lab @('entrenar', '--experimento', $r['experimento'], '--modelo', $elegidos[$juego])).Datos.juegos.$juego
    if (@('terminado', 'reutilizado') -notcontains $t.estado) { throw ('{0}: entrenamiento {1}' -f $juego, $t.estado) }
    $r['clave'] = $t.modelo_registrado; $r['numero'] = [int]$t.numero; $r['entrenamiento'] = $t.estado
    '{0}: {1} versión {2} ({3}); corte {4}, {5} sorteos; clave {6}' -f $juego, $elegidos[$juego], $t.numero, $t.estado, $t.corte, $t.sorteos, $t.modelo_registrado
}
```

En la primera ejecución el estado es `terminado`. Si repites la guía con la
misma base, sale `reutilizado`, con la misma versión.

### 3.4 Repetir: la misma entrada reutiliza la versión

```powershell
$archivosAntes = @(Get-ChildItem -LiteralPath $carpetaModelos -Recurse -File -Force).Count
foreach ($juego in $juegos) {
    $r = $recorrido[$juego]
    $t = (Lab @('entrenar', '--experimento', $r['experimento'], '--modelo', $elegidos[$juego])).Datos.juegos.$juego
    if ($t.estado -ne 'reutilizado' -or [int]$t.numero -ne $r['numero'] -or $t.modelo_registrado -ne $r['clave']) { throw ('{0}: la repetición no reutilizó la versión' -f $juego) }
    '{0}: reutilizado, versión {1}' -f $juego, $t.numero
}
$archivosDespues = @(Get-ChildItem -LiteralPath $carpetaModelos -Recurse -File -Force).Count
if ($archivosDespues -ne $archivosAntes) { throw 'Repetir creó archivos en el registro' }
'Registro sin archivos nuevos ({0})' -f $archivosDespues
```

### 3.5 Cargar en otro proceso: lista, ficha, SHA-256 y verificación

```powershell
$lista = (Lab @('modelos')).Datos
foreach ($juego in $juegos) {
    $g = $lista.juegos.$juego
    '{0}: {1} versión(es); ilegibles {2}; reservas sin modelo {3}' -f $juego, @($g.versiones).Count, @($g.ilegibles).Count, @($g.reservas_sin_modelo).Count
}
foreach ($juego in $juegos) {
    $r = $recorrido[$juego]
    $ficha = (Lab @('modelo', '--clave', $r['clave'])).Datos
    $sha = $ficha.modelo.estimador.sha256
    $archivo = Join-Path $carpetaModelos ('{0}\estimadores\{1}.pkl' -f $juego, $sha)
    if ((Get-FileHash -LiteralPath $archivo -Algorithm SHA256).Hash -ne $sha) { throw ('{0}: el SHA-256 del estimador no coincide con el manifiesto' -f $juego) }
    $r['linea'] = $ficha.linea
    '{0}: versión {1}, corte {2}, compatible {3}, línea {4}; estimador {5} bytes, SHA-256 comprobado' -f $juego, $ficha.resumen.numero, $ficha.resumen.corte, $ficha.compatibilidad.compatible, $ficha.linea, $ficha.modelo.estimador.bytes
    $v = (Lab @('verificar', '--modelo', $r['clave'])).Datos
    '{0}: integridad {1}; carga {2} ({3}); control {4}; histórico hasta el corte {5}' -f $juego, $v.integridad, $v.carga.estado, $v.carga.clase, $(if ($v.reproduccion.exacta) { 'exacto' } else { 'DISTINTO' }), $v.base_actual.historico_hasta_el_corte
}
```

`verificar --modelo` sale con 0 solo si la integridad es correcta, el entorno
es compatible, la carga restringida funciona y el pronóstico de control
recalculado coincide con el guardado. No escribe nada.

### 3.6 Generar con el modelo cargado, sin reentrenar

Cada juego genera tres pronósticos. Antes, un corte anterior al de
entrenamiento debe rechazarse con el código 2, sin escribir nada.

- **Retrospectivo:** el corte de entrada es el de entrenamiento, y el objetivo
  (corte + 1) ya está en la base.
- **Repetido:** con la misma entrada, reutiliza el mismo pronóstico.
- **Siguiente sorteo:** el corte de entrada es el último cargado.

El número de archivos del registro no debe cambiar: generar no crea versiones.

```powershell
$archivosAntes = @(Get-ChildItem -LiteralPath $carpetaModelos -Recurse -File -Force).Count
foreach ($juego in $juegos) {
    $r = $recorrido[$juego]
    $rechazo = Lab @('generar-con-modelo', '--clave', $r['clave'], '--corte', [string]$r['anterior']) @(2)
    '{0}: corte {1} anterior al de entrenamiento rechazado (código {2})' -f $juego, $r['anterior'], $rechazo.Codigo
    $retro = (Lab @('generar-con-modelo', '--clave', $r['clave'], '--corte', [string]$r['corte'])).Datos
    $otra = (Lab @('generar-con-modelo', '--clave', $r['clave'], '--corte', [string]$r['corte'])).Datos
    if (-not $otra.reutilizado -or $otra.identificador -ne $retro.identificador) { throw ('{0}: repetir no reutilizó el pronóstico' -f $juego) }
    $siguiente = (Lab @('generar-con-modelo', '--clave', $r['clave'])).Datos
    $r['retrospectivo'] = $retro.identificador; $r['objetivo_retrospectivo'] = [int]$retro.objetivo; $r['objetivo_siguiente'] = [int]$siguiente.objetivo
    '{0}: retrospectivo objetivo {1} ({2}); siguiente objetivo {3}; versión {4}; ajuste: {5}' -f $juego, $retro.objetivo, $retro.pronostico.generacion.clasificacion_temporal.tipo, $siguiente.objetivo, $retro.pronostico.identidad.modelo_registrado.numero, $retro.pronostico.identidad.ajuste
    $vp = Lab @('verificar', '--pronostico', $retro.identificador)
    '{0}: pronóstico verificado con el modelo cargado (código {1}, huella exacta {2})' -f $juego, $vp.Codigo, $vp.Datos.reproduccion.huella_exacta
}
if (@(Get-ChildItem -LiteralPath $carpetaModelos -Recurse -File -Force).Count -ne $archivosAntes) { throw 'Generar creó archivos en el registro' }
'Generación sin versiones nuevas'
```

El campo `ajuste` del pronóstico dice «ninguno: modelo registrado congelado».
`verificar --pronostico` recalcula con el estimador guardado; no reentrena.

### 3.7 Resultados observados

```powershell
foreach ($juego in $juegos) {
    $r = $recorrido[$juego]
    $s = (Lab @('seguimiento', '--juego', $juego, '--linea', $r['linea'], '--tipo', 'retrospectiva')).Datos
    $fila = @($s.lineas.($r['linea']).filas) | Where-Object { $_.objetivo -eq $r['objetivo_retrospectivo'] } | Select-Object -First 1
    if (-not $fila) { 'AVISO {0}: el objetivo {1} no aparece en el seguimiento (¿hueco en la numeración?)' -f $juego, $r['objetivo_retrospectivo']; continue }
    if ($fila.estado -ne 'incluido') { 'AVISO {0}: objetivo {1} {2}' -f $juego, $fila.objetivo, $fila.estado; continue }
    $c = $fila.coincidencias
    $aciertos = if ($c.PSObject.Properties['pares']) { '{0} de {1} pares número-color (aparte: {2} números y {3} colores)' -f $c.pares, $c.de, $c.numeros, $c.colores } else { '{0} de {1} números' -f $c.numeros, $c.de }
    '{0}: objetivo {1} incluido; {2}; Log Loss {3:N5} frente a uniforme {4:N5}' -f $juego, $fila.objetivo, $aciertos, $fila.metricas.log_loss, $fila.metricas.log_loss_uniforme
    $todas = (Lab @('seguimiento', '--juego', $juego, '--linea', $r['linea'])).Datos
    $pendiente = @($todas.lineas.($r['linea']).filas) | Where-Object { $_.objetivo -eq $r['objetivo_siguiente'] } | Select-Object -First 1
    if ($pendiente) { '{0}: objetivo {1} {2} (aún no sorteado o no cargado)' -f $juego, $pendiente.objetivo, $pendiente.estado }
}
```

En ColorLoto, el acierto del pronóstico son los **pares número-color**
coincidentes, con multiplicidad. Es lo que `/resultados/colorloto` llama
«Aciertos (pares número-color)». Los números y los colores coincidentes son
otras intersecciones con el mismo sorteo y se muestran aparte. En el objetivo
221 del recorrido real hubo 1 de 6 pares, 5 de 6 números y 3 de 6 colores. Un
objetivo aislado no dice nada sobre ventaja: es una observación.

## 4. Reinicio del servidor y recorrido web

En la ventana A, después del bloque de sesión:

```powershell
& $py -m uvicorn app.main:app --host 127.0.0.1 --port 8006
```

Abre `http://localhost:8006` en esta misma máquina: los botones que escriben
solo funcionan desde `localhost` y con el token de la página.

**Las páginas de consulta no escriben.** En la ventana B, toma una instantánea
antes de navegar:

```powershell
$consulta = Huellas $raiz
```

Recorre solo páginas de consulta y no pulses ningún botón:

1. `/laboratorio/modelos`: las versiones de los cuatro juegos, con la
   compatibilidad, la evaluación asociada y el estado del almacén (ilegibles y
   reservas sin modelo).
2. La ficha de cada versión (`/laboratorio/modelo/<clave>`). Muestra:
   - los pasos del flujo;
   - la evaluación de **esta receta**: Log Loss, Brier y secundarias frente a
     la uniforme;
   - aparte, la lectura general del informe de procedencia: la clasificación
     guardada, con esta receta marcada, y quién tuvo la menor pérdida (otro
     modelo, la uniforme, un empate o una comparación incompleta);
   - la selección de hiperparámetros por bloque: antes de la calibración y del
     corte en los clasificadores, y antes del corte en Poisson, que no tiene
     calibración;
   - el pronóstico de control;
   - la compatibilidad y la proyección a las tablas de la Fase 1;
   - los pronósticos de la línea.
3. El informe de procedencia («Informe de procedencia»), con los bosques en el
   ranking, «Cómo se ordena», las métricas secundarias y el botón «Entrenar y
   guardar versión» en cada candidato registrable.
4. «Resultados observados» de la línea (`/laboratorio/<juego>/seguimiento`).
5. `/resultados/<juego>` (Producto 6): la línea aparece como «… · versión
   registrada N». Con una sola línea, «Sin muestra común» es el estado
   correcto. En ColorLoto, los aciertos se rotulan como pares número-color.

Después, en la ventana B:

```powershell
$trasConsulta = Huellas $raiz
$cambios = @($trasConsulta.Keys | Where-Object { $consulta[$_] -ne $trasConsulta[$_] }) + @($consulta.Keys | Where-Object { -not $trasConsulta.ContainsKey($_) })
if ($cambios.Count -gt 0) { throw ('Las páginas de consulta cambiaron archivos: {0}' -f ($cambios -join ', ')) }
'Consulta sin escrituras ({0} archivos)' -f $trasConsulta.Count
```

**Reinicio.** Detén el servidor con `Ctrl+C` en la ventana A y arráncalo otra
vez con la misma orden. En la ficha de una versión:

- «Verificar (integridad, compatibilidad, carga y control)» abre la página de
  verificación: integridad correcta, carga restringida correcta y control
  exacto.
- «Generar con el modelo cargado», con el corte vacío (último cargado),
  devuelve el MISMO pronóstico que la línea de comandos («reutilizado»). La
  versión no cambia y no aparece ninguna versión nueva en
  `/laboratorio/modelos`.
- Con el corte de entrada igual al de entrenamiento, también reutiliza el
  retrospectivo. Un corte anterior muestra el rechazo sin escribir.

## 5. Elegir la versión para la operación diaria (opcional; escribe)

Este paso escribe una versión NUEVA de la configuración de carteras de
Producto 5 en el worktree de la Fase 3. No entrena. Comparar no cambia la
configuración: solo este paso, o «Guardar como versión nueva» en
`/carteras/<juego>`, la cambia.

En la web, en la ficha, «Elegir para la operación diaria…» abre
`/carteras/<juego>` con el modelo y la versión preseleccionados, sin guardar.
Revisa «Versión registrada (opcional)» y pulsa «Guardar como versión nueva».

Por línea de comandos, con MiLoto como ejemplo:

```powershell
$previa = (Carteras @('configuracion', '--juego', 'MILOTO')).Datos.vigente
if ($previa) { 'Vigente antes: versión {0}, modelo {1}' -f $previa.version, $previa.modelo.id } else { 'Sin configuración previa' }
$cfg = (Carteras @('configurar', '--juego', 'MILOTO', '--modelo', $elegidos['MILOTO'], '--registrado', $recorrido['MILOTO']['clave'])).Datos
'Configuración versión {0}: {1}, versión registrada {2} (corte {3})' -f $cfg.version, $cfg.configuracion.modelo.id, $cfg.configuracion.modelo.registrado.numero, $cfg.configuracion.modelo.registrado.corte_de_entrenamiento
$gen = (Carteras @('generar', '--juego', 'MILOTO', '--configuradas')).Datos
$cartera = (Carteras @('consultar', '--id', $gen.juegos.MILOTO.resultado)).Datos.artefacto
'Cartera {0}: línea {1}; fuente con la versión registrada {2}' -f $gen.juegos.MILOTO.estado, $cartera.linea.id, ($cartera.fuente.detalle.modelo_registrado -eq $recorrido['MILOTO']['clave'])
```

La cartera usa el modelo congelado: la línea lleva `-reg<N>`, y la fuente
guarda la clave de la versión. Para volver a la configuración anterior, guarda
otra versión con los parámetros de `$previa`. Las versiones anteriores quedan
en el historial y no se borran.

## 6. Comparación final de los artefactos previos

```powershell
$despues = Huellas $raiz
$alterados = @(); $registros = @()
foreach ($relativa in @($antes.Keys)) {
    $igual = $despues.ContainsKey($relativa) -and $despues[$relativa] -eq $antes[$relativa]
    if (-not $igual) { if ($relativa -match '(^|\\)operacion\\') { $registros += $relativa } else { $alterados += $relativa } }
}
$nuevos = @($despues.Keys | Where-Object { -not $antes.ContainsKey($_) })
[IO.File]::WriteAllLines((Join-Path $global:evidencia 'despues.sha256'), [string[]]@($despues.Keys | Sort-Object | ForEach-Object { '{0}  {1}' -f $despues[$_], $_ }))
($recorrido | ConvertTo-Json -Depth 5) | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $global:evidencia 'recorrido.json')
'{0} previos: {1} intactos, {2} alterados o ausentes; {3} registros de ejecución previos cambiados; {4} archivos nuevos' -f $antes.Count, ($antes.Count - $alterados.Count - $registros.Count), $alterados.Count, $registros.Count, $nuevos.Count
if ($alterados.Count -gt 0) { throw ('Artefactos previos alterados: {0}' -f ($alterados -join ', ')) }
'Evidencia en {0}' -f $global:evidencia
```

Los artefactos previos (informes, pronósticos, carteras, configuraciones,
informes de resultados y versiones) deben quedar intactos. Las carpetas
`operacion` guardan registros de ejecución y cerrojos. Se cuentan aparte, y lo
normal es 0 cambios entre los previos.

## 7. Imprimir

Imprime o guarda como PDF:

- la ficha de una versión, en Carta vertical y en Carta horizontal;
- `/laboratorio/modelos`, en Carta horizontal;
- el informe de procedencia, en Carta vertical;
- la página de verificación de la versión.

En el recorrido real, el operador revisó estos PDF en **Legal vertical**
(612×1008 puntos, Chrome 155) sin solapamientos. Carta, A4 y horizontal siguen
sin validar en Windows; en Linux se revisaron Carta vertical y horizontal.

Revisa que las filas estén completas, que las cabeceras de tabla se repitan,
que no haya solapamientos ni páginas iniciales casi vacías, y que la clave y el
SHA-256 no se corten. Imprimir no entrena ni escribe.

## Códigos de salida de `scripts.laboratorio_modelos`

| Código | Significado |
|---|---|
| `0` | Éxito |
| `2` | Uso incorrecto, identificador no encontrado, modelo no registrable o corte de entrada no válido (también uno anterior al de entrenamiento) |
| `3` | Base o almacén no disponibles |
| `4` | Muestra insuficiente o modelo que no se pudo ajustar |
| `5` | Resultado parcial, o verificación sin reproducción exacta o con el histórico cambiado |
| `6` | Trabajo ya activo para ese juego |
| `7` | Fallo (también tiempo agotado del trabajador o fallo del proceso) |
| `8` | Archivo alterado o ilegible, o estimador alterado o no admitido |
| `9` | Versión registrada incompatible con este entorno: no se carga |

## Límites

- **Compatibilidad estricta.** Se exige la misma versión exacta de
  scikit-learn, la misma versión menor de Python, NumPy y SciPy, las mismas
  variables y la misma transformación. Con otro intérprete, la versión aparece
  como incompatible (código 9) y no se carga. Entrenar de nuevo crea otra
  versión, porque el entorno forma parte de la identidad. El sistema
  operativo se registra y se informa, pero no bloquea la carga. No se promete
  igualdad bit a bit entre Linux y Windows.
- **Solo archivos de la aplicación.** La carga comprueba el SHA-256 y el tamaño
  ANTES de deserializar, y el deserializador admite solo las clases de
  scikit-learn y NumPy necesarias. Aun así, no copies estimadores de fuentes
  ajenas al registro.
- **Evaluación asociada.** Es la del informe de procedencia: mide la receta,
  con reajustes por bloque antes del corte. El estimador congelado se ajustó
  después con todo el histórico hasta el corte, y su rendimiento propio se ve
  en el seguimiento de sus pronósticos.
- **Una observación no es evidencia.** Pocos objetivos no permiten distinguir
  una diferencia del azar. Una huella SHA-256 local no es una firma externa ni
  una prueba de anterioridad. Que el registro funcione y respete la disciplina
  temporal no demuestra ausencia de sobreajuste ni ventaja futura.
- **Persistencia.** El registro inmutable de archivos es la persistencia usada.
  La proyección a las columnas de `modelos` y `metricas_modelo` no significa
  que esas tablas se hayan poblado.
- **Tiempo máximo.** El trabajador de entrenamiento tiene un límite de 1800 s.
  Se ajusta con `TIEMPO_MAXIMO_TRABAJADOR_LABORATORIO`. Si se agota, el
  proceso se termina y no se publica nada.
- **Disco.** Requiere disco local NTFS (enlaces duros y creación exclusiva de
  archivos).
- **Rutas.** Sin rutas largas, Windows rechaza rutas de más de 259
  caracteres. Cada publicación usa un temporal corto
  (`.publicacion.<16 hex>.tmp`) en la carpeta de su destino, así que basta con
  que quepa el destino. El más largo es el pronóstico de una versión
  registrada: la carpeta del laboratorio más unos 147 caracteres. La carpeta
  admite como máximo 111; la de este worktree mide 61.

## Validación

- **Linux:** pruebas focales y de regresión, selección de Windows, suite
  completa, demostración sintética (7/7) y revisión visual e impresa. Las
  cifras de la entrega original (v1) y de la corrección de rutas (v2) están
  en el borrador del PR y en `README.md`. La demostración usa datos
  sintéticos, no el histórico real.
- **Windows, primera ejecución (v1)**, evidencia del operador:
  - parche de 477419 bytes aplicado, con sus 51 archivos iguales al manifiesto
    (CRLF/LF normalizado solo en memoria) y espacios limpios;
  - pruebas focales: `6 failed, 54 passed`. Cuatro trazas mostraban
    temporales de 262 o 264 caracteres para destinos de 240 o 242; las otras
    dos fueron un HTTP 500 y el código 3 de la línea de comandos al generar;
  - el script se detuvo ahí: no hay resultados de regresiones, demostración ni
    selección.

  La causa era el nombre del temporal del publicador del laboratorio
  (`.<nombre final>.<16 hex>.tmp`, 22 caracteres más que el destino).
- **Corrección (v2):** temporal corto `.publicacion.<16 hex>.tmp` (el de
  Producto 5), regresiones con el límite simulado y una simulación de las 60
  pruebas focales que reproduce `6 failed, 54 passed` con el código anterior y
  da `60 passed` con el corregido. Era una simulación en Linux; la v2 se
  validó después en Windows (siguiente punto).
- **Windows, v2** (evidencia del operador, Python 3.14.6, carpeta
  `%TEMP%\f3c-evidencia-20261011-002007-202b4aad`):
  - los 53 archivos coincidieron con el manifiesto v2 (CRLF/LF normalizado) y
    el índice real quedó vacío;
  - Fase 3: la primera pasada dio `1 failed, 68 passed`. La prueba
    `test_temporales_anteriores_y_nuevos_se_reconocen_y_se_conservan` creaba
    un temporal con el nombre anterior bajo la carpeta temporal larga de pytest
    y superaba 259 caracteres. Con la raíz corta de pytest
    `C:\GitHub\f3t-29c2818301a4` pasaron las 69;
  - Productos 6, 5 y 4: `73`, `96` y `94 passed`; Productos 1 a 3:
    `229 passed`; selección (89 entradas): `2203 passed`;
  - demostración sintética 7/7; OpenSSL `SUPERADOS 7/7` en modo `exigir`;
    `pip check` y espacios limpios; el aviso conocido de Starlette/httpx;
  - la suite completa no se ejecutó en Windows.
- **Windows, recorrido con el histórico real** (operador, carpeta
  `%TEMP%\f3-real-20261011-010241-7a44f090`):

  | Juego | Sorteos | Último cargado | Corte | Modelo registrado | Versión | Siguiente objetivo |
  |---|---:|---:|---:|---|---:|---:|
  | Baloto | 639 | 2719 | 2714 | `random_forest_clasificador` | 1 | 2720 |
  | Baloto Revancha | 639 | 2719 | 2714 | `extra_trees_clasificador` | 1 | 2720 |
  | MiLoto | 89 | 620 | 615 | `random_forest_clasificador` | 1 | 621 |
  | ColorLoto | 225 | 225 | 220 | `random_forest_poisson` | 1 | 226 |

  - Los seis candidatos de cada juego terminaron.
  - Las cuatro versiones se guardaron, se cargaron en otro proceso y
    reprodujeron su control exacto. Repetir las mismas entradas reutilizó los
    artefactos.
  - Los 136 artefactos previos se conservaron, comprobados por SHA-256.
  - No hubo importación ni cambio de configuración de modelos.

  Retrospectivos (el resultado ya existía al generarlos; no acreditan
  anterioridad prospectiva ni capacidad predictiva):

  | Juego | Objetivo | Aciertos | Log Loss | Uniforme |
  |---|---:|---|---:|---:|
  | Baloto | 2715 | 1 de 5 números | 0.35358 | 0.35945 |
  | Baloto Revancha | 2715 | 0 de 5 | 0.36386 | 0.35945 |
  | MiLoto | 616 | 1 de 5 | 0.37827 | 0.38296 |
  | ColorLoto | 221 | 1 de 6 pares número-color (5 de 6 números, aparte) | 3.71437 | 3.73767 |

- **Windows, revisión de la interfaz** (operador, con ayuda de ChatGPT):
  - lista de versiones, fichas y verificaciones de los cuatro juegos;
    pronósticos de Baloto 2715 y 2720 y de ColorLoto 221 y 226;
  - tras un reinicio real de Uvicorn, la verificación de MiLoto mantuvo la
    versión, la clave, el SHA-256 del estimador y el control exacto, y generar
    de nuevo Baloto 2720 reutilizó el mismo pronóstico, con su fecha original,
    su clave y su contenido;
  - Resultados integró las líneas registradas de Baloto y ColorLoto mediante
    filtros explícitos; «Sin muestra común» con una sola línea es correcto;
  - el informe de Baloto del corte 2714 (16 páginas) mostró los seis
    candidatos y 60 objetivos comunes;
  - PDF en Legal vertical (612×1008, Chrome 155), sin solapamientos. Carta, A4
    y horizontal no se validaron en Windows.
- **Ajustes de cierre históricos** (después validados en Windows y fusionados en PR #92). La revisión encontró tres ambigüedades de
  presentación, que el incremental corrige:
  - la ficha distingue la evaluación de su receta de la lectura general del
    informe de procedencia. En Baloto, corte 2714: Logística AE-36 0.35942
    primera, uniforme 0.35945 segunda y Random Forest 0.35947 tercero;
  - la ficha Poisson de ColorLoto ya no habla de calibración;
  - `/resultados/colorloto` rotula los aciertos como pares número-color.

  Además, la prueba de temporales usa su propia carpeta de raíz corta y ya no
  depende de `--basetemp`. No cambian modelos, probabilidades, la API ni los
  artefactos.
- **GitHub Actions histórico actualizado:** Fase 3 pasó las ejecuciones 47, 48 y 49; PR #94 pasó después Linux completo y Windows selección. La ampliación ML v3.2 no hereda esos checks: su suite completa nativa Windows y recorrido real tienen evidencia propia ya completada; Actions del futuro PR permanece pendiente.


## Matriz nativa de impresión y ampliación ML validada

Daniel completó el recorrido real de las cinco familias con decisiones explícitas de entrenamiento, registro y configuración. Repetir una entrada reutilizó su versión; los cinco casos web persistieron tras reiniciar, con respuestas de API idénticas y sin nuevas escrituras. La consulta histórica XGBoost conserva su validez aunque Baloto tenga después Markov como selección vigente.

| Página por cada uno de los cuatro juegos | Carta vertical | Carta horizontal | A4 vertical |
|---|---|---|---|
| Informe del laboratorio con once candidatos y objetivos comunes | Exportada y auditada | Exportada y auditada | Exportada y auditada |
| Ficha de versión de una familia nueva, componentes, contrato e importancias/motivo | Exportada y auditada | Exportada y auditada | Exportada y auditada |
| Predicción de esa versión: combinaciones, explicación, multiplicidad y advertencias | Exportada y auditada | Exportada y auditada | Exportada y auditada |

Fuente válida: `ml-impresion-v2-2a99ebfc.zip`. Daniel exportó doce páginas web con Brave, perfil temporal propio y únicamente GET; verificó medio `print` antes de cada uno de los **36 PDF, 600 páginas**. ChatGPT auditó sus huellas y contenido: 9.474 apariciones de filas con multiplicidades, renderizado de todos los PDF y controles de páginas vacías, cajas fuera del papel y solapes. La inspección visual de hojas de contacto y páginas ampliadas fue representativa: no hubo lectura manual ampliada individual de las 600 páginas. No se repite esa revisión en este cierre documental.

El primer exportador externo mantuvo por error el medio `screen`; ese lote no acredita impresión y fue sustituido por la v2 sin cambiar el producto. Las capturas de 390 px pertenecen al lote anterior y no son capturas nuevas de la v2. Los inventarios antes/después de la exportación conservaron 442 archivos y siete orígenes; son la instantánea de ese recorrido, no una guarda fija del aplicador. La [validación local consolidada](ml_cinco_familias.md#validación-local-completada-de-ml-v32) distingue impresión, pruebas nativas y antecedentes Linux. Aplicar este cierre no repite pruebas, entrenamiento, emisiones ni PDF.
