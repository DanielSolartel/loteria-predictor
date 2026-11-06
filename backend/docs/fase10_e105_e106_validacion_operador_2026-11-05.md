# E10.5/E10.6: validación aislada del operador — 2026-11-05

Estado: **ensayo nativo aislado aprobado, 15/15 casos, código 0**. Integración y CI
de la entrega pendientes. La Fase 10 y los requisitos de producción siguen abiertos.

Daniel ejecutó el recorrido en Ubuntu/WSL sobre su equipo Windows, mediante el
lanzador de Windows PowerShell 5.1 y Docker Desktop con motor Linux. Codex revisó
la salida, el ZIP, las huellas, los registros de Docker y el diario; no repitió
la ejecución del operador. El cierre documental se prepara el 2026-11-06 UTC.

## Evidencia y versiones

| Elemento | Valor verificado |
|---|---|
| Base integrada de la implementación | PR #110, `e154a1364f5efaf80895746fa3790f4b30a0176d` |
| Candidato ensayado | Árbol `8a1a9a5dc7a6261d22ffb070c643b1e0ff3b27fb`, 1177 archivos públicos |
| Arnés | `e105-e106-activacion-nativa/4` |
| ZIP del arnés v4 | `e105-e106-activacion-aislada-v4-20261105.zip`, SHA-256 `4968852d48358fb55483a6bb4a1078ec03984ef582f606f70daa25c0120c1f98` |
| Evidencia nativa | `e105-activacion-evidencia-5cd9462aa03cc141387763daa60015bb.zip` |
| Tamaño y SHA-256 de evidencia | 363587 bytes; `cb8c02015d71ccb52b540d7a7ed8c86d9009359d06dc4813199863f4ce8e684f` |
| Integridad | CRC correcto en 172 entradas; 171 huellas de `SHA256SUMS` correctas |
| Runtime | Python 3.14.4; OpenSSL 3.5.5, 27 Jan 2026; servicios Linux en Docker Desktop |
| Resultado | `ensayo_completado`, código 0, 15 aprobados de 15, 277,6 s |

La salida de terminal aportada empieza dentro del final del diario: es parcial.
Todos sus campos JSON disponibles coinciden con el ZIP, incluidos tamaño y SHA-256.
El `resultado.json` íntegro del ZIP contiene los quince casos y los 43 eventos del motor.

## Quince casos de la ejecución nativa

| Caso | Resultado y alcance |
|---|---|
| TestClient antes de Docker | Solicitud ASGI correcta; Starlette 1.10.0, httpx 0.28.1 y httpcore 1.0.9 |
| PKI y mTLS estrictos antes de Docker | Cliente y servidor correctos; rechazo de cliente sin certificado y de host distinto del SAN; sonda original del producto correcta |
| Fuentes e imágenes preparadas | 1177 archivos y cinco identidades de imagen conservados, sin reconstrucción |
| Dos capturas e importaciones | E10.4 real en PostgreSQL propio: una y dos filas de sorteo por juego, generaciones firmadas e importadas |
| Primera activación | Motor real, mTLS y consulta correcta de los cuatro juegos |
| Cliente sin certificado | No obtiene el estado a través del proxy real |
| Mantenimiento | nginx devuelve 503 con `Retry-After: 30` para nuevas solicitudes |
| Solicitud anterior al reload | Petición HTTP demorada en la última línea de cabeceras: termina con la generación anterior |
| Lectores de la segunda generación | Los cuatro juegos muestran íntegramente la segunda generación |
| Rechazo de sonda | Rechazo inyectado por el arnés después de una sonda real correcta; motor devuelve 1 y restaura la generación anterior con salud comprobada |
| SIGKILL y recuperación | Interrupción del trabajador propio después de publicar y antes de abrir; candidata en 503; recuperación persistida vuelve a la generación anterior y devuelve 0 |
| Exportador | HTTP loopback real: muestra fresca 200 y vencida 503; vencimiento mediante adelanto de reloj inyectado de 121 s |
| Auditoría de preparación | Devuelve 3, sin transacción pendiente y con `produccion_autorizada=false` |
| Conservación de generaciones | Archivos y contenido lógico de ambas bases publicadas idénticos antes/después |
| Conservación final de fuentes | Los 1177 archivos del candidato siguen idénticos |

Los cuatro juegos son Baloto, Baloto Revancha, MiLoto y ColorLoto. Las generaciones
sintéticas son `1687eb881262f8383963bcc367d6d434` y
`7c950690d61d78fb2744b54b34e2575e`. No contienen carteras ni modelos poblados: el
ensayo mínimo acredita el flujo de generaciones y sus sorteos sintéticos.

## Ciclo, tiempos y finalización

La primera activación informa 1,371 s de corte y el cambio a la segunda generación,
28,273 s. El rechazo inyectado y su reversión informan 72,713 s, sin exceder el
presupuesto de 180 s de ese plan. Los tres pares de eventos `drenar` → `detener`
registran 25,101 s, 25,096 s y 25,104 s. Son mediciones del ensayo, no un SLA.

El diario final registra dos activaciones, una rechazada y dos reversiones; no
hay bloqueos ni transacción pendiente. Una de las reversiones corresponde a la
recuperación posterior al SIGKILL. Los códigos 1 del rechazo y 3 de la auditoría
son resultados esperados dentro de casos aprobados; el proceso completo terminó en 0.

Las últimas inspecciones acreditan **ocho contenedores detenidos**: PostgreSQL,
el relevo TCP y las dos ternas API/pasarela/proxy. PostgreSQL y las seis instancias
de servicio tienen salida 0. El relevo termina en 137 tras la parada con plazo;
`OOMKilled=false`. Los comandos de parada terminan en 0 y no hay errores de
finalización. No queda servicio del ensayo en marcha.

Se conservan los contenedores detenidos, redes, volumen, datos sintéticos,
generaciones, archivos de control y la preparación previa. No se ejecutaron
`down`, `rm`, `prune` ni borrado de bases. PostgreSQL permaneció sin publicación
directa en su red interna; el relevo TCP propio publicó exclusivamente en loopback.

## Atribución de antecedentes y correcciones del arnés

Los resultados se conservan por ejecución y no se suman:

| Evidencia anterior | Atribución y límite |
|---|---|
| 136 pruebas focales y demostración 8/8 | Codex, Linux/Python 3.12.14; adaptadores de servicios y base sustituidos, HTTP real; evidencia original de la implementación |
| 24 controles del arnés v4 | Codex, Python 3.12.14 con TLS estricto explícito y OpenSSL; Docker sustituido; no son una ejecución nativa de PostgreSQL/nginx |
| Preparación de imágenes | Operador, ejecución previa independiente; imágenes y dependencias privadas reutilizadas sin instalar ni reconstruir en esta ejecución |
| 15 casos nativos de este acta | Operador, Ubuntu/WSL y servicios reales; no se atribuyen a Codex ni a CI |

Los tres intentos anteriores terminaron detenidos y se conservan. La v1 detectó
la ausencia de publicación efectiva desde una red exclusivamente interna; la v2
introdujo un relevo propio en loopback. La v2 llegó a la migración `0006` y falló
por los clientes HTTP ausentes del entorno de prueba; la v3 añadió únicamente
las dos ruedas puras ya fijadas en el lock. La v3 completó las importaciones y se
detuvo durante la activación, sin registrar la excepción TLS concreta.

Sobre la función PKI v3 exacta se reprodujo localmente `Missing Authority Key
Identifier` con verificación estricta. La v4 añadió los identificadores de clave,
el control mTLS previo a Docker y el diagnóstico de sondas. La ejecución v4 de
este acta completó el recorrido. Estas correcciones pertenecen al arnés: no
cambiaron las 1177 fuentes del candidato ni sus imágenes de servicio.

## Pendientes y alcance del cierre

- Integración y nueva CI del candidato: pendientes. Los checks de PR #110 son de
  la base y no validan esta entrega; no se ejecutan Actions con la cuota agotada.
- D1, D5–D8, D10 y D11: decisiones de infraestructura, RPO/RTO, custodia, monitor
  externo, registro/secretos y uso de captura/activación reales siguen pendientes.
- R-L en el destino, R-W nativo Windows, auditoría SEC/DAT del destino y
  programación/verificación de respaldos: no cubiertos por este ensayo.
- Coordinación del selector E10.4, el importador y un disparador automático:
  pendiente; no se instala ninguno.
- Se probó una petición demorada anterior al reload y el drenaje de 25 s; no se
  provocó un cliente que agotase el límite del trabajador ni una pérdida de energía.
- La caducidad de muestra se ensayó con reloj inyectado, sin esperar 121 s reales
  ni modificar el reloj del equipo. No se ensayó la caída de todo el host.
- Las 16 excepciones exactas de Grype conservan su caducidad del 2026-11-17; no
  se amplían ni se presentan como vulnerabilidades corregidas.

El auditor E10.7 conserva un catálogo fijo que aún enumera el ensayo nativo entre
sus pendientes. Este acta acredita su realización en el alcance aislado; el
cierre documental no modifica ese código ni concede autorizaciones restantes.
Fase 6, sus cuentas, tareas y bases operativas quedaron sin intervención. No se
ejecutaron instalaciones globales, Brave, Git, Actions, commit, push o PR.

Guía vigente: [operación y observabilidad](fase10_operacion_y_observabilidad.md).
