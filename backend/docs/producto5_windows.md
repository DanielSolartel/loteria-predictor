# Producto 5 en Windows: modelo combinado, carteras y simulación

**Estado:** validado localmente en Windows con tu histórico real (resumen al
final), incluida la revisión de impresión en Carta vertical y horizontal.
GitHub Actions todavía no ha ejecutado Producto 5. Los pronósticos siguen
`experimental_no_acreditado`, con el NO-GO vigente y
`AUTORIZA_EVALUACION = False`. Una cartera no es una lista de
números garantizados ni una recomendación de apuesta; una simulación da
frecuencias bajo hipótesis declaradas, no probabilidades reales, dinero ni
premios.

Esta guía usa el equipo del operador:

- worktree de Producto 5: `C:\GitHub\loteria-predictor-producto5`;
- intérprete: `$env:LOCALAPPDATA\loteria-predictor-venvs\ae68\Scripts\python.exe`;
- puerto sugerido: **8004** (Producto 4 puede seguir en 8003).

La instalación, los tamaños y los SHA-256 están en la guía de entrega externa
y en sus scripts (`aplicar-producto5-windows.ps1` para una instalación nueva,
`continuar-producto5-validacion.ps1` para un worktree con el parche original
ya aplicado y `validar-producto5-historico-real.ps1`). Este documento forma
parte del parche, así que no repite esas cifras.

## Almacenamiento aislado en cada ventana

Las variables de entorno prevalecen sobre `.env`, y tu sesión puede traer
rutas de Productos 2 a 4. Cada ventana de PowerShell que use Producto 5 debe
fijar las cuatro rutas y comprobarlas antes de escribir; ninguna escritura
puede ir al almacén de Producto 4:

```powershell
$wt = 'C:\GitHub\loteria-predictor-producto5'
$py = Join-Path $env:LOCALAPPDATA 'loteria-predictor-venvs\ae68\Scripts\python.exe'
function Revisar([string]$paso) { if ($LASTEXITCODE -ne 0) { throw "$paso falló (código $LASTEXITCODE)" } }
$env:PYTHONIOENCODING = 'utf-8'; [Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:DIRECTORIO_PRONOSTICOS_EXPERIMENTALES = 'C:\GitHub\loteria-predictor-producto5\backend\storage\pronosticos'
$env:DIRECTORIO_OPERACION = 'C:\GitHub\loteria-predictor-producto5\backend\storage\operacion'
$env:DIRECTORIO_LABORATORIO_MODELOS = 'C:\GitHub\loteria-predictor-producto5\backend\storage\laboratorio'
$env:DIRECTORIO_CARTERAS_MODELOS = 'C:\GitHub\loteria-predictor-producto5\backend\storage\carteras'
Set-Location (Join-Path $wt 'backend')
$rutas = (& $py -m scripts.carteras_modelos rutas | Out-String) | ConvertFrom-Json   # solo rutas, sin credenciales
Revisar 'rutas'
foreach ($clave in 'directorio_pronosticos_experimentales', 'directorio_operacion', 'directorio_laboratorio_modelos',
                   'directorio_carteras_modelos') {
    $ruta = $rutas.$clave
    "{0}: {1}" -f $clave, $ruta
    if (-not $ruta.StartsWith("$wt\backend\storage\", [StringComparison]::OrdinalIgnoreCase)) { throw "$clave sale del worktree de Producto 5" }
}
"tiempo maximo por juego: {0} s" -f $rutas.tiempo_maximo_trabajador_carteras
```

`TIEMPO_MAXIMO_TRABAJADOR_CARTERAS` (300 s por defecto) limita cada trabajo
del proceso trabajador por juego. Si tu equipo es más lento, súbelo en la
ventana antes de arrancar; si un juego queda en `tiempo_agotado`, no se
publicó nada.

## Uso

- **Interfaz:** `& $py -m uvicorn app.main:app --host 127.0.0.1 --port 8004`, desde una ventana con la cabecera anterior. Después abre:
  - http://localhost:8004/carteras: los cuatro juegos, su corte y objetivo, la configuración vigente, la última comparación, **Comparar el modelo combinado (los cuatro)** y **Generar carteras configuradas**. Los trabajos corren en segundo plano con progreso por juego; la página de progreso se puede recargar sin iniciar otro trabajo.
  - `/carteras/<juego>`: modelos con sus requisitos, **Generar cartera** (modelo, combinaciones, diversidad y semilla), configuración versionada, carteras por línea y comparaciones.
  - `/carteras/comparaciones/<clave>`: ranking exterior, pesos por bloque (gráfica y tabla), evaluación interna y exterior por separado y superbalota aparte.
  - `/carteras/guardadas/<clave>`: combinaciones, resultado observado, cobertura y coincidencias, **Simular**, exportación CSV/JSON y Trazabilidad con **Verificar**.
  - `/carteras/simulaciones/<clave>`: los dos escenarios, la comparación emparejada y los controles exactos.
  - `/carteras/<juego>/seguimiento`: aciertos observados por línea.
  - `/operacion` enlaza `/carteras` y ofrece **Generar carteras configuradas**.
- **Comando** (mismos casos de uso):

  ```powershell
  & $py -m scripts.carteras_modelos catalogo;                     Revisar 'catalogo'
  & $py -m scripts.carteras_modelos diagnostico --juego MILOTO;   $LASTEXITCODE
  & $py -m scripts.carteras_modelos comparar --juego todos;       $LASTEXITCODE
  & $py -m scripts.carteras_modelos generar --juego BALOTO --modelo ensemble_temporal;   $LASTEXITCODE
  & $py -m scripts.carteras_modelos ejecuciones --limite 5;       Revisar 'ejecuciones'
  ```

  `simular --cartera`, `verificar --cartera|--comparacion|--simulacion`, `exportar --cartera ... --formato csv` y `consultar --id` toman las claves de la salida JSON de `generar`, `comparar` o `consultar`. `configurar --juego ... --modelo ... --cantidad 5 --diversidad limitada --semilla 42` guarda una versión nueva; `generar --juego todos --configuradas` usa la vigente de cada juego.
- **Códigos de salida:**

  | Código | Significado |
  |---|---|
  | `0` | Éxito |
  | `2` | Uso incorrecto, parámetro no válido o identificador no encontrado |
  | `3` | Base o almacén no disponibles |
  | `4` | Muestra insuficiente o modelo que no se pudo ajustar |
  | `5` | Resultado parcial (cartera parcial no publicada, sin configuración, comparación incompleta) o verificación sin reproducción exacta |
  | `6` | Trabajo ya activo para el juego |
  | `7` | Fallo |
  | `8` | Archivo alterado |
  | `9` | Tiempo agotado del proceso trabajador |

- **Dónde entrena y simula:** cada comparación, vector fuente o simulación arranca un proceso Python trabajador (un `python.exe` adicional mientras dura), con el tiempo máximo anterior. El servidor y la operación diaria no cambian sus hilos numéricos. Si el trabajador muere o se detiene, el juego queda en `fallo` o `tiempo_agotado` sin publicar nada; repetir funciona.
- **Imprimir o guardar como PDF:** la primera página de una cartera muestra juego, objetivo, combinaciones y un aviso breve. Trazabilidad, mezclas internas, tablas emparejadas y probabilidades del vector fuente se imprimen completas aunque estén plegadas. Imprimir no recalcula ni escribe.
- **Qué escribe:** `comparar`, `generar`, `simular` y `configurar` escriben solo en `storage\carteras`. Ninguna orden importa sorteos ni escribe en PostgreSQL ni en los almacenes de Productos 1 a 4.

## Límites

- La comparación del modelo combinado es exploratoria, sobre sorteos ya usados como histórico. Que el ajuste elija peso 1 para la uniforme es un resultado válido y se muestra como tal.
- El muestreo de las carteras no conserva las marginales como probabilidades de inclusión; la diversidad es una propiedad de construcción.
- La simulación con la hipótesis de muestreo ponderado usa el mismo vector fuente que construyó la cartera: una ventaja ahí no es una confirmación independiente. Cero apariciones simuladas no significan imposibilidad; los controles exactos (números) dan los valores de referencia.
- Una diferencia simulada puede venir de la estructura de la cartera (por ejemplo, menos pares repetidos en ColorLoto) y no de una ventaja del modelo.
- La reproducción exacta se exige en el mismo entorno; no se promete igualdad bit a bit entre Linux y Windows.
- Requiere disco local NTFS (enlaces duros y creación exclusiva de archivos).
- Cada publicación escribe primero un temporal de nombre corto y constante (`.publicacion.<16 hex>.tmp`, 33 caracteres) en la carpeta del destino. Sin rutas largas activadas, la ruta definitiva debe caber en el límite de Windows (259 caracteres); el temporal nunca es más largo que el nombre anterior de Producto 4.

## Validación

- **Windows, primera ejecución (fallida, ya corregida):** el parche original se aplicó y coincidió con su manifiesto, pero las pruebas de Producto 5 dieron `13 failed, 77 passed`. El temporal de la publicación superaba el límite de rutas aunque el destino cupiera (temporal de 262 caracteres para un destino de 240). La corrección se comprobó primero en Linux con una simulación de ese límite, que no es Windows.
- **Pruebas en Windows tras la corrección** (operador; Git 2.54.0.windows.1, Python 3.14.6, OpenSSL 3.5.6; evidencia `%TEMP%\loteria-producto5-continuacion-20261008-145935-923912f3`): los 50 archivos coinciden con el manifiesto v2 (49 al normalizar CRLF/LF en memoria y 1 byte a byte), con el índice real vacío y los espacios limpios. Regresión de publicación y archivos de los fallos iniciales `28 passed`, Producto 5 `96 passed`, Producto 4 `94 passed`, Productos 1 a 3 `225 passed`, selección filtrada de 76 entradas `1963 passed`, demostración sintética 11/11, OpenSSL `SUPERADOS 7/7` en modo `exigir` sin omisiones, fallos ni errores, y `pip check` sin problemas. Aparece el aviso conocido de Starlette por `httpx` en `TestClient`. La suite completa no se ejecutó en Windows.
- **Windows con tu histórico real:** `ACEPTADO` (evidencia `%TEMP%\loteria-producto5-historico-real-20261008-151647-3abd3afc`). Leyó la base sin importar sorteos ni modificar PostgreSQL:
  - Baloto y Revancha con 638 sorteos y corte 2718, MiLoto con 87 y corte 618, y ColorLoto con 224 y corte 224. Siguientes objetivos 2719, 2719, 619 y 225; 60, 60, 27 y 60 objetivos exteriores. El último sorteo era del 2026-10-05 y el diagnóstico indicó `al_dia` en esa ejecución, no de forma permanente;
  - comparar los cuatro juegos tardó 24.7 s y repetirlo, 4.1 s, reutilizando los cuatro informes. Carteras de cinco combinaciones con semilla 42, con las mismas claves al repetir, y simulación de 10 000 sorteos con los escenarios uniforme y ponderado por separado;
  - integridad correcta, reproducción exacta e histórico coincidente en los cuatro juegos. Retrospectivas incluidas: 2717→2718 (Baloto y Revancha), 617→618 (MiLoto) y 223→224 (ColorLoto); los siguientes objetivos quedaron pendientes;
  - los 63 archivos originales de Producto 4 y los 31 de su copia aislada se conservaron byte a byte; se leyeron cinco experimentos de Producto 4 y se generaron 59 archivos en `storage\carteras`.
- **Resultado frente a la uniforme:** la uniforme obtuvo menor pérdida que el modelo combinado en la evaluación exterior de los cuatro juegos. Algunas variantes logísticas mejoraron ligeramente la pérdida retrospectiva en Baloto y Revancha; no es una ventaja prospectiva. En MiLoto, el vector fuente de la cartera actual es constante (peso 1 para la uniforme): sus cinco líneas son muestreadas, sin sugerencia del modelo.
- **Impresión** (operador; páginas revisadas con ChatGPT): cartera de MiLoto 619 (4 verticales / 6 horizontales), cartera de ColorLoto 225 (4/6), comparación de Baloto con corte 2718 (15/22), seguimiento de MiLoto (1/1) y simulación de MiLoto 619 (4/6).
  - Sin solapamientos, texto recortado ni filas perdidas; las cinco combinaciones están en la primera página en las dos orientaciones.
  - Se conservan los rankings completos (39 filas en MiLoto y 42 en ColorLoto), la trazabilidad, los bloques y pesos de la comparación, y los controles exactos y las matrices emparejadas de la simulación (10 000 empates en MiLoto).
  - El panel y los catálogos se revisaron solo en vertical.
- **Linux (Cloud, solo fixtures sintéticas):** Producto 5 `96 passed`, Producto 4 `94 passed`, Productos 1 a 3 `225 passed`, selección `1963 passed`, demostración 11/11, suite completa `6208 passed` sin fallos ni omisiones, OpenSSL `SUPERADOS 7/7` y `pip check` limpio.
- **GitHub Actions:** todavía no ha ejecutado Producto 5; los checks de Producto 4 o de la base no lo acreditan.

Este cierre registra la evidencia ya obtenida. No repite importaciones,
entrenamientos, simulaciones ni pruebas; solo actualiza documentación.
