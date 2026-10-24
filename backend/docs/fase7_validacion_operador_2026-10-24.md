# Fase 7: validación local del operador y cierre técnico

**Estado al 24-10-2026:** implementación y validación local completadas; lista para la publicación manual, revisión del PR y sus checks de GitHub Actions, todavía pendientes. Base exacta: `605afe8c2bb3b38d0fa3abdb6a5d14ba2002b5a6` (PR #97). Entrega: Fase 7 v2 más el ajuste de presentación F7-VIS-01.

La evidencia de Windows fue ejecutada por Daniel y revisada por ChatGPT; no se atribuye a Claude una ejecución nativa. Las validaciones Linux de la entrega v2 conservan la procedencia registrada en [fase7_simulaciones.md](fase7_simulaciones.md). Las baterías se solapan y sus recuentos no se suman.

## Entorno y conservación

Windows 11 `10.0.26200`, PowerShell 5.1 y Python 3.14.6 de `C:\GitHub\venvs\loteria-fase6\Scripts\python.exe`. NumPy 2.5.3, SciPy 1.18.1, SQLAlchemy 2.1.1, pytest 9.1.1, FastAPI 0.141.1, httpx 0.28.1 y tzdata 2026.5; para PostgreSQL, psycopg 3.3.6 y Alembic 1.20.0. No se instalaron ni actualizaron dependencias durante estas capturas. El aviso conocido de Starlette sobre httpx no impidió las pruebas.

Trabajo en `C:\GitHub\loteria-predictor-fase7-v2`, separado de F6 y UI93. Los supervisores comprobaron sus orígenes y archivos privados sin exportar `.env` ni credenciales. Pruebas y capturas sobre copias públicas verificadas y datos sintéticos; PostgreSQL en una instancia de prueba separada. Los supervisores no dispararon manualmente tareas ni ciclos de adquisición de F6. Los temporales de las ejecuciones satisfactorias se eliminaron; los históricos de diagnósticos anteriores no se limpiaron de forma general.

## Pruebas de Windows y sondas

- **Selección v2: 3183 pruebas únicas aprobadas**, consolidación de dos corridas: 3158 resultados retenidos de la selección inicial y 25 revalidados. No es una segunda selección completa. Los dos fallos iniciales eran rutas de almacenes del arnés de validación; se corrigió el arnés sin cambiar el producto. El caso inicialmente omitido de enlace simbólico se ejecutó con permiso nativo y pasó.
- **OpenSSL `exigir`: 7/7**, con OpenSSL 3.5.6. Las cuatro sondas de concurrencia e integridad de la auditoría original dieron **4/4**. La huella de referencia fijada de Fase 7 pasó en Windows/NumPy 2.5.3.
- Después de F7-VIS-01: **52 pruebas dirigidas aprobadas**, cero fallos, errores u omisiones: diez nuevas de presentación, once de interfaces y 31 regresiones de v2. Se ejecutaron también de forma independiente en Linux durante la auditoría del parche; no se atribuyen a esta corrección nuevas suites completas.
- **Sonda visual independiente: 8/8** en Windows. Comprueba página y fragmento en estados vivo, interrumpido con avance, interrumpido antes de empezar y terminado; todos los GET conservan los bytes de los registros.

## Rendimiento nativo: 20/20 puntos

Cada juego se midió con 100, 1000, 10.000, 100.000 y 1.000.000 de iteraciones, un proceso nuevo por punto y un hilo numérico configurado. Históricos sintéticos de 645, 645, 97 y 229 sorteos. Equipo AMD64 con 16 procesadores lógicos; cifras de este equipo y entorno.

| Juego | Tiempo de cálculo con 1.000.000 | Pico del proceso (MiB) | Base previa al cálculo (MiB) | Lote | Lotes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baloto | 111,793 s | 182,5 | 126,3 | 516 | 1938 |
| Baloto Revancha | 111,296 s | 183,2 | 127,0 | 516 | 1938 |
| MiLoto | 15,676 s | 189,6 | 127,1 | 4123 | 243 |
| ColorLoto | 60,905 s | 239,5 | 126,8 | 1455 | 688 |

El pico incluye las importaciones: no es consumo incremental del motor. `base_mb` registra el pico anterior al cálculo. Los campos históricos `*_mb` se expresan aquí en **MiB (bytes / 2²⁰)**. El máximo de los veinte puntos fue 239,7 MiB en ColorLoto con 100.000 iteraciones. Ningún lote superó los 2.000.000 de uniformes. El supervisor declaró las firmas ctypes de WinAPI antes de invocar el medidor original, sin modificar sus bytes ni los del motor.

El ajuste visual y este cierre documental conservan el motor y los componentes de persistencia, por lo que no se repitieron la medición ni PostgreSQL por estos cambios.

## PostgreSQL aislado: nueve controles

Cliente y procesos Python en Windows; servidor **PostgreSQL 16.14 en contenedor Linux de Docker Desktop**, revisión Alembic `0006`, con 1616 sorteos sintéticos. Se reutilizó una imagen local y se creó un contenedor propio, volumen separado y puerto aleatorio publicado en `127.0.0.1`. No se consultó por SQL el servidor operativo; sus metadatos anteriores y posteriores coinciden. El contenedor temporal fue eliminado.

Pasaron A, B, C, E, F, G, H, I y J del script de PostgreSQL: JSONB y reutilización, lectura de solo lectura, exclusión, espera acotada, independencia del advisory de datos, rechazo de filas alteradas, CLI, trabajador web y comprobación por fila. Ocho publicadores dejaron una fila; la espera del recurso retenido fue de 10,01 s; los cuatro comandos devolvieron 0. D es un control informativo, no un décimo criterio obligatorio. Los errores de solo lectura y timeout del registro se provocan deliberadamente en B y E.

## Brave y F7-VIS-01

Brave de Windows, motor `Chrome/156.0.8078.48`, con perfil temporal y recursos locales. La primera revisión produjo doce vistas a 360, 390 y 1280 px: **36 capturas y 516/516 criterios automáticos**. La auditoría de imágenes identificó F7-VIS-01: el aviso global decía «Interrumpida» mientras la tarjeta conservaba «en curso» y «Simulando». El sondeo ya se detenía; el registro no se reescribía.

Claude corrigió únicamente la plantilla y añadió diez casos de regresión. Con estado global interrumpido, los juegos pendientes o activos se presentan como interrumpidos y sin barra activa; el avance anterior se muestra como dato histórico. Los juegos terminados y reutilizados mantienen sus estados y enlaces. La sonda sobre la v2 daba 4/8, control negativo esperado; tras la corrección da 8/8.

La revalidación nativa cubrió cinco estados a los mismos tres anchos: **15 capturas y 228/228 criterios**, cero POST ejecutados por el servidor de capturas. La auditoría posterior de las quince imágenes confirma la corrección y cierra F7-VIS-01. Los JSON originales mantienen su texto «pendiente de auditoría» porque se produjeron antes de esta revisión; este documento registra la revisión posterior, sin alterar esas evidencias.

La instantánea al 40 % es sintética; HTMX consulta su fragmento realmente, pero la captura no ejecuta otro millón de iteraciones. El trabajador real en segundo plano quedó comprobado en el ensayo PostgreSQL. Estas pruebas no acreditan Google Chrome por separado. El título fijo «Simulación en curso» de la pestaña se conserva como observación menor fuera de F7-VIS-01 y no impide el cierre técnico de la tarjeta.

## Evidencias conservadas

| Archivo | SHA-256 |
| --- | --- |
| `fase7-entrega-v2.zip` | `309f62aaea9a1d996bc857c52b1a942c2e356d79025b2a90f68432d593409fca` |
| `f7-reanudacion-v2-a77d69af.zip` | `b10c52e72a39f2c11fa99efdc51da05cac664c824b8f94035491c6a3b3ea0d4e` |
| `f7-medicion-v2-012701f5.zip` | `2c3cc6ab1122cd08538b80579367455c9198a21e1d32aba534205abcae7c185a` |
| `f7-postgresql-docker-v2-66f2c18c.zip` | `e90c54f6b6e222c47640deb878ea692553d411a5e8f24fd7c2d9db1a496e2084` |
| `f7-visual-brave-v2-836726b7.zip` | `72ac0ecb20cf3abf15bc64b01b2cc5df91c405a855fa81e58f0afac9996e2129` |
| `fase7-ajuste-estado-visual-v2.zip` | `015924586ba89d08b76d82bfa2457a43fff04f307416fbf898d98ee825fd9406` |
| `f7-ajuste-visual-301d65cd.zip` | `cb2971c399331116046a388aac0716e17d31da495a3f25fae30322b0e13394ea` |

Los inventarios, JUnit, logs, mediciones y capturas son la evidencia primaria; este documento los resume. La selección inicial fallida sigue conservada en la reanudación y mantiene su propio resultado histórico.

## Alcance del cierre y publicación pendiente

Tras el ajuste de presentación se verificaron 759 archivos públicos. El cierre actualiza cinco documentos y añade este informe, sin modificar código ejecutable, pruebas, dependencias, esquema ni configuración: inventario resultante de 760 archivos. F6, UI93 y sus estados operativos conservan su ubicación.

Pendientes: commit y push manuales de Daniel, PR, revisión y sus checks de Linux y Windows; después, integración en main. La evidencia local y los checks de PR #97 no sustituyen los del nuevo PR de Fase 7. El uso de simulaciones sobre la base real es una decisión operativa aparte y no se ejecutó durante estas validaciones sintéticas.

Se conserva el orden **7 Simulaciones → 8 API pública → 9 React → 10 Despliegue → 11 Aplicación personal**. Las fases siguientes continúan planificadas. La validación técnica mantiene `experimental_no_acreditado`, el NO-GO de AE-39 y `AUTORIZA_EVALUACION = False`; no acredita capacidad predictiva.
