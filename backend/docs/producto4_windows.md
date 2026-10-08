# Producto 4 en Windows: laboratorio de modelos

**Estado:** validado localmente en Windows con tu histórico real (resumen al
final), incluida la impresión ajustada en Carta vertical. La impresión
horizontal no se ha revalidado en Windows. Los pronósticos siguen `experimental_no_acreditado`, con el NO-GO
vigente y `AUTORIZA_EVALUACION = False`; ningún modelo se promueve
automáticamente a la operación diaria.

Esta guía usa el equipo del operador:

- worktree de Producto 4: `C:\GitHub\loteria-predictor-producto4`;
- intérprete: `$env:LOCALAPPDATA\loteria-predictor-venvs\ae68\Scripts\python.exe`;
- puerto sugerido: **8003** (Producto 3 puede seguir en 8002).

La instalación, los tamaños y los SHA-256 están en la guía de entrega externa
y en su script de aplicación. Este documento forma parte del parche, así que
no repite esas cifras. Un worktree que ya tiene el parche completo y la
corrección de la prueba de configuración recibe solo el incremental de
presentación y cierre; el parche completo final sirve para reconstruir y
auditar desde la base, no para aplicarlo encima.

## Almacenamiento aislado en cada ventana

Las variables de entorno prevalecen sobre `.env`, y tu sesión puede traer
rutas de Producto 2 o 3. Cada ventana de PowerShell que use Producto 4 debe
fijar las tres rutas y comprobarlas antes de escribir:

```powershell
$wt = 'C:\GitHub\loteria-predictor-producto4'
$py = Join-Path $env:LOCALAPPDATA 'loteria-predictor-venvs\ae68\Scripts\python.exe'
function Revisar([string]$paso) { if ($LASTEXITCODE -ne 0) { throw "$paso falló (código $LASTEXITCODE)" } }
$env:PYTHONIOENCODING = 'utf-8'; [Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:DIRECTORIO_PRONOSTICOS_EXPERIMENTALES = 'C:\GitHub\loteria-predictor-producto4\backend\storage\pronosticos'
$env:DIRECTORIO_OPERACION = 'C:\GitHub\loteria-predictor-producto4\backend\storage\operacion'
$env:DIRECTORIO_LABORATORIO_MODELOS = 'C:\GitHub\loteria-predictor-producto4\backend\storage\laboratorio'
Set-Location (Join-Path $wt 'backend')
$rutas = (& $py -m scripts.laboratorio_modelos rutas | Out-String) | ConvertFrom-Json   # solo rutas, sin credenciales
Revisar 'rutas'
foreach ($clave in 'directorio_pronosticos_experimentales', 'directorio_operacion', 'directorio_laboratorio_modelos') {
    $ruta = $rutas.$clave
    "{0}: {1}" -f $clave, $ruta
    if (-not $ruta.StartsWith("$wt\backend\storage\", [StringComparison]::OrdinalIgnoreCase)) { throw "$clave sale del worktree de Producto 4" }
}
```

## Uso

- **Interfaz:** `& $py -m uvicorn app.main:app --host 127.0.0.1 --port 8003`, desde una ventana con la cabecera anterior. Después abre:
  - http://localhost:8003/laboratorio: los cuatro juegos, su muestra y el botón **Comparar modelos**. La comparación corre en segundo plano: la página de progreso se puede recargar o abrir en otra pestaña sin iniciar otro trabajo.
  - El informe (`/laboratorio/experimentos/<clave>`) muestra el ranking sobre la muestra común, las tablas por bloque, la gráfica y el diagnóstico de calibración. Cada modelo disponible tiene el botón **Generar pronóstico con este modelo**.
  - `/laboratorio/pronosticos/<clave>` muestra la sugerencia, el ranking completo y la clasificación del objetivo.
  - `/laboratorio/<juego>/seguimiento` muestra los resultados observados por línea de modelo.
- **Comando** (mismos casos de uso):

  ```powershell
  & $py -m scripts.laboratorio_modelos catalogo;                     Revisar 'catalogo'
  & $py -m scripts.laboratorio_modelos diagnostico --juego MILOTO;   $LASTEXITCODE
  & $py -m scripts.laboratorio_modelos comparar --juego todos;       $LASTEXITCODE
  & $py -m scripts.laboratorio_modelos ejecuciones --limite 5;       Revisar 'ejecuciones'
  ```

  `generar --experimento <clave> --modelo <id>`, `verificar --experimento <clave>`, `verificar --pronostico <clave>` y `seguimiento --juego <JUEGO>` toman las claves de la salida JSON de `comparar` o `consultar`.
- **Códigos de salida:**

  | Código | Significado |
  |---|---|
  | `0` | Éxito |
  | `2` | Uso incorrecto o identificador no encontrado |
  | `3` | Base o almacén no disponibles |
  | `4` | Muestra insuficiente o modelo que no se pudo ajustar |
  | `5` | Resultado parcial o verificación sin reproducción exacta |
  | `6` | Comparación ya activa |
  | `7` | Fallo |
  | `8` | Archivo alterado |

- **Dónde entrena:** cada comparación, generación o verificación arranca un proceso Python trabajador (verás un `python.exe` adicional mientras dura). El servidor y la operación diaria no cambian sus hilos numéricos. Si cierras o matas ese proceso, el juego queda en `fallo` sin publicar nada; repetir la comparación funciona.
- **Imprimir o guardar como PDF:** Trazabilidad (informe y pronóstico) y Parámetros de las recetas (catálogo) se imprimen completos aunque el desplegable esté cerrado en pantalla. Las tarjetas no dejan su comienzo al pie de una página separado de su tabla; las tablas largas se fragmentan con la cabecera repetida. Imprimir no entrena ni escribe.
- **Qué escribe:** `comparar` y `generar` escriben solo en `storage\laboratorio`. Ninguna orden del laboratorio importa sorteos ni escribe en PostgreSQL; la actualización sigue en el panel diario de Producto 3.

## Límites

- Comparación exploratoria sobre sorteos ya usados como histórico: elegir un modelo después de verla no acredita ventaja futura.
- La reproducción exacta se exige en el mismo entorno. Otro sistema o versión de NumPy, SciPy o scikit-learn da otra identidad; no se promete igualdad bit a bit entre Linux y Windows.
- El seguimiento separa reconstrucciones retrospectivas y emisiones con el objetivo no cargado al generar. Esto último describe la base local, no que la emisión precediera al sorteo real.
- Requiere disco local NTFS (enlaces duros y creación exclusiva de archivos).
- El modelo de la operación diaria no cambia: elegir otro requiere una decisión explícita posterior.

## Validación

- **Windows con tu histórico real:** aceptado. Cuatro comparaciones (22.8 s; repetirlas reutilizó los informes en 3.6 s) y ocho pronósticos, todos con integridad correcta, reproducción exacta y coincidencia del histórico hasta el corte. Los 28 archivos anteriores de Producto 3 quedaron intactos. Ninguna ventaja predictiva demostrada: AE-36 tuvo la menor pérdida en Baloto, la logística regularizada nueva en Revancha y la uniforme en MiLoto y ColorLoto. Detalle y límites en `README.md`.
- **Pruebas en Windows:** Producto 4 `77 passed`, Productos 1 a 3 `225 passed`, selección filtrada `1850 passed`, OpenSSL 7/7 y `pip check` limpio, después de corregir solo una prueba de configuración que leía `DIRECTORIO_LABORATORIO_MODELOS` del proceso. La suite completa no se ejecutó en Windows.
- **Demostración sintética en Windows:** 8/8, con fixtures; sus cifras no son sorteos reales.
- **Impresión ajustada:** revalidada en Windows con Chrome 154, Carta vertical, mediante el catálogo de Baloto (2 páginas), el pronóstico de MiLoto 619 (3) y el informe de ColorLoto corte 224 (11). Las recetas y Trazabilidad aparecen completas, se conservan las 39 filas de MiLoto y los 60 objetivos por candidato de ColorLoto, la sugerencia sigue en la primera página y no hay solapamientos visibles ni contenido cortado. No hay evidencia nueva de horizontal en Windows.
- **Revalidación final de pruebas en Windows** (2026-10-07): Producto 4 `94 passed`, Productos 1 a 3 `225 passed`, selección filtrada de 67 archivos `1867 passed`, demostración sintética 8/8, OpenSSL `SUPERADOS 7/7` en modo `exigir` y `pip check` limpio. Los 51 archivos coinciden con el manifiesto, con normalización CRLF/LF solo en memoria; espacios limpios y ningún archivo preparado en el índice real. Un aviso conocido de Starlette, sin fallos ni omisiones. No se ejecutó la suite completa en Windows.
- **Linux:** ver el borrador del PR.
- **GitHub Actions:** todavía no ha ejecutado Producto 4.

Este cierre final registra la evidencia ya obtenida. No repite importaciones,
entrenamientos, generaciones ni pruebas; solo actualiza documentación.
