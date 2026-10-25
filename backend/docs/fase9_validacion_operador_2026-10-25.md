# Fase 9.1 v2 — validación del operador, 25 de octubre de 2026

**Estado:** validación local completada y auditoría aprobada. Publicación manual,
PR y sus checks de Python y frontend pendientes. La Fase 9 global sigue abierta;
esta entrega solo cubre consultas existentes de `/api/v1` y su matriz de huecos.

Se mantienen `experimental_no_acreditado`, el NO-GO de AE-39 y
`AUTORIZA_EVALUACION = False`. No hay acreditación de capacidad predictiva.

## Entrega y procedencia

- Base: `615f3832296d74a7acea44e5ecdf7dc84a11d70a` (merge PR #99).
- Entrega de Claude: `fase9-1-entrega-v2.zip`, 8.336.830 bytes, SHA-256
  `f29988beb22194f8b7f9c094e2f81183b7cc66823d7417e379c6859c01b26cce`.
- Parche completo: `fase9-1-completo-v2.patch`, 1.020.406 bytes, SHA-256
  `8b94ae661e742242a7843eef3625231f881258ecbe41dca3c17ccfe021341659`.
- Fuente validada: 904 archivos, sobre la base anterior; índice sin cambios
  preparados. Este cierre solo actualiza cinco documentos y añade este informe:
  el inventario final tiene 905 archivos. No cambia código ejecutable.
- Worktree de Daniel: `C:\GitHub\loteria-predictor-f91-v2`.
- Entorno nativo: Windows 11 10.0.26200, Python 3.14.6 AMD64, pytest 9.1.1,
  Node 24.15.0, npm 11.12.1, Brave instalado, motor 156.0.8078.48.
- Ejecutó Daniel; auditó ChatGPT. Los resultados Linux/Cloud de Claude y del
  auditor conservan su procedencia y no se presentan como resultados Windows.

## Evidencias nativas recibidas

| Archivo | Bytes | SHA-256 |
| --- | ---: | --- |
| `f91-validacion-v2-bc77eede.zip` | 4556339 | `07c25eab7165360c61a55a2d392e18b1303774d325375ca2447739715464296a` |
| `f91-vite-v2-d4fc3522.zip` | 57760 | `7761fe732883df5a09c4e0ccaf785d2de26834ded96d300f6cc0984efb59cb38` |

CRC, rutas e inventarios completos verificados: 120 archivos de evidencia en
la primera captura y 15 en la reanudación, más sus manifiestos. El resultado
previo incluido en la segunda conserva exactamente sus bytes. La referencia,
versiones y ejecutable de Brave coinciden entre ambas corridas.

## Resultados

| Comprobación | Resultado nativo |
| --- | --- |
| `pip check` | Sin requisitos rotos; sin instalar paquetes Python |
| Instalación del frontend | `npm ci --ignore-scripts`, código 0, dependencias del worktree |
| Tipos, TypeScript, compilación y canario | Código 0 |
| Vitest | 379 aprobadas; cero fallos, errores u omisiones |
| Pasarela | 186 aprobadas; cero fallos, errores u omisiones |
| API pública | 92 aprobadas; cero fallos, errores u omisiones |
| Sonda original F9-LIM-01 | Dos respuestas 504 dentro del margen: 0,0520 y 0,0551 s con plazo de 0,05 s |
| Intercambio HTTP real con API sintética | 14/14; diez consultas concurrentes con cuatro huecos, todas 200 en 0,465 s |
| Brave normal | 297/297 visitas; 24/24 criterios; 11 controles directos |
| Cuota | 429 con cuenta atrás, reintento manual y sin reintentos automáticos |
| API caída, falta de clave y clave incorrecta | Estados esperados y sin reintentos automáticos |
| Brave Vite, reanudación | 12/12 visitas; StrictMode con una llamada a `/juegos`; Host ajeno 403, Origin ajeno 403 y ruta desconocida 404 |

Las 379, 186 y 92 pruebas se verificaron en sus XML originales. En la segunda
corrida solo se ejecutaron versiones y Vite: se retuvieron los resultados
anteriores después de comprobar su ZIP y sus 120 huellas. La consolidación no
es una nueva batería completa. La selección amplia de Windows queda para el
CI del PR; no se repitieron Fase 6, ML, mediciones ni PostgreSQL.

Los recorridos usan 360, 390 y 1280 px (cuota: 1280 px). El normal incluye los
cuatro juegos, las métricas del índice 18/18/11/5 por juego, filtros, teclado,
foco, errores esperados y simulación alterada. La revisión independiente de
las 297 geometrías confirma página contenida y regiones de tabla enfocables;
el almacenamiento del navegador quedó vacío. Las comprobaciones no detectaron
credenciales, canarios ni tráfico de terceros en el navegador.

El auditor revisó las 40 capturas previas y la captura de Vite: 41 en total,
sin hallazgos visuales bloqueantes. Son capturas de Brave automatizado con
perfiles temporales; no se afirma una sesión manual interactiva de Daniel.

## Corrección del supervisor y límites de reproducción

El primer intento de Vite agotó la espera aunque el servidor había anunciado
`ready in 523 ms`. Los códigos ANSI alrededor del puerto interrumpían la
dirección literal que buscaba el orquestador. El adaptador externo
`color-vite-r1` propaga `NO_COLOR=1` a sus hijos. Conserva las comprobaciones,
los procesos reales y las fuentes del producto. La reanudación arrancó Vite
en 698 ms y completó el recorrido en 48,74 s.

La corrección pertenece al supervisor externo. El orquestador versionado
`tests/recorrido_fase9.py` sigue descartando `NO_COLOR` de su entorno hijo;
su orden directa de Vite puede fallar por la misma causa en Windows. Para
reproducir esta evidencia se usa el adaptador documentado, sin modificar el
producto. No se presenta ese comando directo como validado en Windows.

La sonda original del plazo conserva una descripción fija que dice Linux.
Se preservaron sus bytes; la plataforma Windows se acredita por el resultado
padre, el intérprete `.exe`, las órdenes y la consola nativa.

## Conservación y alcance

Las dos corridas acreditan fuente de 904 archivos e índice conservados. La
segunda verificó además la evidencia anterior y versiones sin cambios.
Los orígenes protegidos conservaron sus controles de fuente y configuración.
No se invocó la tarea `LP6-01023009031fcabd`, no se ejecutaron ciclos operativos
ni se consultó el PostgreSQL operativo. La API del recorrido es la real con
proveedores sintéticos, SQLite y almacenes temporales: no es PostgreSQL.

El frontend y la pasarela siguen siendo locales y de solo consulta. HTTPS,
despliegue y autenticación de escritura quedan en Fase 10. La matriz de huecos
y el criterio final de Fase 9 no se cambian con este cierre.

**Siguiente paso:** revisión del cierre, commit y publicación manual de Daniel,
PR y checks de Python y frontend. No hay commit, push, PR ni despliegue desde
los supervisores de validación o de cierre.
