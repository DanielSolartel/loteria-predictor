# Fase 8 — API pública de solo lectura

**Estado:** v2 sobre `f15f513b431dd9a5dc3a2fb148a63a82a11405b5` (merge del PR #98, que integró la Fase 7), implementada y validada localmente en Linux y Windows con datos sintéticos y bases aisladas. La v2 corrige F8-SEC-01, F8-SEC-02, F8-LIM-01 y F8-OBS-01 y añade la API pública a la selección de Windows. El operador completó las 92 pruebas, cuatro sondas y PostgreSQL 16.14 aislado; la evidencia fue auditada. [Cierre local](fase8_validacion_operador_2026-10-24.md). Publicación manual y CI del PR pendientes; despliegue en Fase 10. [Protocolo nativo](fase8_windows.md). Se mantienen `experimental_no_acreditado`, el NO-GO de AE-39 y `AUTORIZA_EVALUACION = False`.

## Qué es

Una entrada FastAPI **separada** de la aplicación local: `app.api.publica.aplicacion:app`.

- Expone consultas de los cuatro juegos (Baloto, Baloto Revancha, MiLoto y ColorLoto) bajo `/api/v1`: juegos, sorteos, estadísticas, predicciones guardadas y simulaciones guardadas.
- Reutiliza los casos de uso existentes: `ListarJuegos`, `ObtenerJuego`, `ListarSorteos`, `ConsultarResumenJuego`, `ConsultarEstadisticasDescriptivas`, `CentroDePredicciones.consultar` y `SimulacionesFase7.listar/obtener`. No reconstruye estadísticas, predicciones, simulaciones ni lógica ML.
- **No monta** la web administrativa, los estáticos ni ningún router REST interno. Las escrituras de `/api/sorteos` (POST y DELETE) y los POST de la web no existen en esta entrada; tampoco hay una ruta alternativa a ellas.
- Todas las rutas son GET. Las consultas no entrenan, simulan, generan, sincronizan, recuperan trabajos ni modifican datos o artefactos del producto.

## Arranque aislado (Linux o Windows)

Desde `backend/`, en un entorno de pruebas:

1. Generar una clave: `python -m scripts.api_publica_claves generar --id pruebas`. Imprime la clave **una sola vez** y la entrada `pruebas:sha256:<huella>`.
2. Definir `API_PUBLICA_CLAVES` con esa entrada, en el entorno o en `.env`. `DATABASE_URL` debe apuntar a una base **de pruebas**.
3. Comprobar la configuración: `python -m scripts.api_publica_claves comprobar`. Informa los identificadores, sin mostrar huellas.
4. Arrancar: `uvicorn app.api.publica.aplicacion:app --host 127.0.0.1 --port 8010 --no-access-log --no-proxy-headers`. La aplicación local sigue siendo `app.main:app`.
5. Consultar: `curl -H "X-API-Key: <clave>" http://127.0.0.1:8010/api/v1/juegos`. Documentación interactiva: `http://127.0.0.1:8010/api/v1/docs`.

El paso 4 es el **único arranque soportado**; `python -m uvicorn` con los mismos argumentos es equivalente. Las dos opciones son obligatorias:
- `--no-access-log`: el registro de acceso de Uvicorn escribe la URL completa con su consulta. Una clave enviada por error en `?api_key=` recibe 401, pero quedaría en ese registro. El registro propio `app.api.publica` sigue activo: método, plantilla, estado, latencia, identificador de la clave e identificador de la solicitud, sin consulta.
- `--no-proxy-headers`: sin ella, Uvicorn reescribe la IP del cliente con `X-Forwarded-For` en las conexiones desde `127.0.0.1`, y una sola conexión local eludiría el límite por IP variando esa cabecera. Hasta que la Fase 10 defina proxies fiables, la API usa siempre la IP del socket.

Las pruebas `tests/unit/api_publica/test_api_publica_arranque.py` ejecutan este paso tal cual, leído de esta guía, como proceso Uvicorn real; solo cambian el puerto y, para provocar un fallo, la aplicación.

La configuración se lee **al arrancar**: cambiar claves, límites o CORS exige reiniciar el proceso.

## Autenticación

- **Cabecera:** `X-API-Key`. La clave no se acepta en la URL, en cookies ni en `Authorization`.
- **Configuración:** `API_PUBLICA_CLAVES` contiene una lista separada por comas de `id:sha256:<64 hex>`. Son **huellas**, nunca claves en claro; `id` usa minúsculas, dígitos, `_` o `-` (1–32 caracteres).
- **Sin claves predeterminadas:** si la variable falta, está vacía o tiene **cualquier** entrada no válida (formato, huella de la cadena vacía, duplicados), la API queda **cerrada**: toda ruta protegida responde `503 no_configurada`.
- **Errores:** una clave ausente o no válida recibe `401 no_autenticado`, con el mismo mensaje en ambos casos y `WWW-Authenticate: ApiKey header="X-API-Key"`.
- **Comparación:** se compara el SHA-256 de la clave con cada huella mediante `hmac.compare_digest`, recorriendo todas. El servidor no guarda ni registra la clave, solo el identificador de la clave aceptada.
- **Generar:** `python -m scripts.api_publica_claves generar --id <id>`. La clave tiene la forma `lpk_` + 43 caracteres aleatorios de `secrets.token_urlsafe(32)`.
- **Huella de una clave existente:** `python -m scripts.api_publica_claves huella --id <id> < archivo`. Se lee por la entrada estándar, nunca como argumento.
- **Sustituir:**
  1. generar una clave con otro `id` y añadir su entrada a la lista;
  2. reiniciar la API;
  3. cambiar el consumidor;
  4. quitar la entrada antigua y reiniciar.
- **Revocar:** quitar su entrada de `API_PUBLICA_CLAVES` y reiniciar. Desde ese momento responde 401.

## Límites de uso

- **Algoritmo:** cubeta de fichas que se recarga de forma continua.
  - **Por clave válida:** `API_PUBLICA_FICHAS_POR_MINUTO`, 60 por defecto y mínimo 5.
  - **Por IP:** `API_PUBLICA_FICHAS_POR_MINUTO_IP`, 120 por defecto. Se aplica antes de enrutar y cubre también la salud, la documentación y los intentos con claves inventadas.
- **Coste por consulta:** 1 consultas ligeras, 2 listados, 3 predicciones, 5 estadísticas (recorren el histórico).
- **Al agotarse:** `429 limite_excedido` con `Retry-After` en segundos (entero ≥ 1). Las respuestas autenticadas llevan `X-RateLimit-Limit` y `X-RateLimit-Remaining`.
- **El límite es por proceso.** Cada proceso de Uvicorn lleva su propia cuenta en memoria: con N trabajadores, la cuota efectiva puede llegar a N veces la configurada. No es un límite global. Para uno global, ejecutar un solo trabajador (recomendado para este uso personal) o limitar en el proxy de la Fase 10. El estado se pierde al reiniciar.
- **Memoria acotada:**
  - una clave inventada no crea estado de cuota, porque la cuota se descuenta después de autenticar;
  - el seguimiento por IP guarda como mucho `API_PUBLICA_MAX_CLIENTES_IP` orígenes (1024 por defecto) y descarta el menos reciente;
  - la IP es la del socket (`request.client`), no una cabecera que el cliente pueda inventar. Lo garantiza `--no-proxy-headers` en el arranque soportado: sin esa opción, Uvicorn reescribe `request.client` con `X-Forwarded-For` (F8-LIM-01 de la auditoría de la v1).

## Matriz de endpoints

Prefijo `/api/v1`. Todas requieren `X-API-Key` salvo `/salud` y la documentación.

| Ruta | Parámetros | Coste | Respuesta | Errores |
|---|---|---:|---|---|
| `/salud` | — | — (límite por IP) | `{"estado": "ok", "api": "v1"}` | 429 |
| `/estado` | — | 1 | monitoreo de este proceso | 401, 429, 503 |
| `/juegos` | — | 1 | los cuatro juegos y sus reglas | 401, 429, 503 |
| `/juegos/{codigo}` | `codigo`: BALOTO, BALOTO_REVANCHA, MILOTO, COLORLOTO | 1 | juego, espacio muestral y dimensiones | 401, 404, 429, 503 |
| `/juegos/{codigo}/sorteos` | `pagina` 1–10.000 (1); `por_pagina` 1–100 (20); `desde`, `hasta` (fecha); `numero_desde`, `numero_hasta`; `orden` fecha_desc, fecha_asc, numero_desc o numero_asc | 2 | página con `total` y `paginas` | 401, 404, 422, 429, 503 |
| `/juegos/{codigo}/sorteos/{numero_sorteo}` | `numero_sorteo` ≥ 1 | 1 | un sorteo | 401, 404, 422, 429, 503 |
| `/juegos/{codigo}/estadisticas` | — | 1 | métricas disponibles y su parámetro | 401, 404, 429, 503 |
| `/juegos/{codigo}/estadisticas/resumen` | `hasta_numero_sorteo` | 5 | resumen del juego (Producto 1) | 401, 404, 422, 429, 503 |
| `/juegos/{codigo}/estadisticas/panel` | `hasta_numero_sorteo` | 5 | panel descriptivo (Fase 5) | 401, 404, 422, 429, 503 |
| `/juegos/{codigo}/estadisticas/{metrica}` | `hasta_numero_sorteo`, y según la métrica `anio`, `mes`, `dia_semana` o `ventana` | 5 | una métrica (Fase 5) | 401, 404, 422, 429, 503 |
| `/juegos/{codigo}/predicciones` | `cartera` (64 hex, opcional); `historial` 0–50 (20) | 3 | predicción guardada (la última o la indicada) e historial acotado | 401, 404, 409, 422, 429, 503 |
| `/juegos/{codigo}/simulaciones` | `limite` 1–50 (20) | 2 | simulaciones guardadas con su integridad | 401, 404, 422, 429, 503 |
| `/simulaciones/{identificador}` | UUID de la fila | 2 | identidad, contenido y `contenido_sha256`, verificados | 401, 404, 409, 422, 429, 503 |

Los contratos (pydantic) están en `app/api/publica/esquemas.py` y en el OpenAPI.

- **Sin identificadores internos:** los juegos y los sorteos omiten los UUID internos y la fuente de importación.
- **Predicciones:** se proyectan sin enlaces web internos, identificadores de ejecución ni configuración completa.
- **Simulaciones:** se publican sin los metadatos de ejecución (lote, entorno y origen). Un tercero puede recomputar la `clave` desde `parametros` y `contenido_sha256` desde `contenido`.

## Errores

Formato único: `{"error": {"codigo", "mensaje", "solicitud"[, "detalles"]}}`. `solicitud` coincide con la cabecera `X-Request-ID`.

| Estado | Código | Cuándo |
|---|---|---|
| 401 | `no_autenticado` | clave ausente o no válida |
| 404 | `no_encontrado` | juego, sorteo, métrica, simulación, predicción o ruta inexistentes |
| 405 | `metodo_no_permitido` | cualquier método distinto de GET, también los inventados |
| 409 | `alterado` y otros códigos de los casos de uso | artefacto guardado no íntegro |
| 422 | `parametro_no_valido`, `no_valido` | parámetro fuera de rango o incompatible; `detalles` indica la ubicación sin repetir la entrada |
| 429 | `limite_excedido` | cuota agotada (`Retry-After`) |
| 500 | `error_interno` | fallo inesperado: sin traza ni mensaje interno |
| 503 | `no_configurada`, `base_no_disponible` | sin claves válidas o base no disponible, sin detalles de conexión |

Nunca se devuelven claves, cabeceras, rutas de archivos, trazas ni mensajes de la base. Todas las respuestas llevan `Cache-Control: no-store`, también los 500.

**Fallo inesperado.** El middleware de la API lo convierte en el 500 sanitizado **antes** de que llegue a Uvicorn, que imprimiría su traza y su mensaje (F8-SEC-01). El 500 lleva `X-Request-ID`, que coincide con `solicitud`. El registro guarda solo la clase de la excepción y la solicitud (`error_interno=RuntimeError solicitud=…`), y el monitoreo lo cuenta una vez. Se captura `Exception`, no `BaseException`: las cancelaciones, `KeyboardInterrupt` y `SystemExit` siguen su curso. Los errores de dominio, los de la base (503) y los de validación conservan sus manejadores específicos.

## Documentación y excepciones de acceso

- `/api/v1/docs` (Swagger UI con botón «Authorize» para `X-API-Key`), `/api/v1/openapi.json` y `/api/v1/salud` no requieren clave. El límite por IP sí se les aplica.
- `API_PUBLICA_DOCUMENTACION=false` desactiva la documentación y el OpenAPI (404).
- Cada operación protegida declara el esquema `ClaveDeAPI` y sus respuestas 401, 429 y 503 con ejemplos.

## Monitoreo

`/estado` (protegido) informa, para **este proceso**:
- inicio y tiempo activo;
- solicitudes por clase (2xx, 4xx…);
- por ruta: solicitudes, errores 4xx y 5xx, y latencia media y máxima;
- límites (alcance `por_proceso`, costes, rechazos, IP seguidas);
- número de claves configuradas;
- base `disponible` o `no_disponible`, sin motivo.

Se agrupa por plantilla de ruta, no por URL real, y por método estándar (los de RFC 9110 y `PATCH`). Las rutas inexistentes cuentan juntas en `sin_ruta` y los métodos no estándar en `OTRO`, que siguen recibiendo 405 (F8-OBS-01). Así, el estado no crece con lo que envíe un cliente.

Cada solicitud deja una línea en el registro `app.api.publica`: método acotado, plantilla, estado, latencia, identificador de la clave aceptada (nunca la clave) e identificador de la solicitud. No incluye la consulta ni la URL real. Es memoria del proceso, separada de la base, los históricos, los modelos y los almacenes.

## CORS

**Deshabilitado** por defecto. `API_PUBLICA_CORS_ORIGENES` admite una lista explícita de orígenes `http(s)://host[:puerto]`; `*` o un comodín impiden arrancar.

Con origen configurado solo se permite GET y la cabecera `X-API-Key`, sin credenciales. Se exponen `Retry-After`, `X-Request-ID` y `X-RateLimit-*`.

## Consumo desde el futuro frontend (Fase 9)

**Ninguna clave va en el código distribuido**: un paquete de React es público y cualquier secreto incluido en él queda expuesto. Opciones, de más a menos recomendable:

1. **Mismo origen con un intermediario del servidor** (Fase 10): el proxy o el servidor que sirve el frontend añade `X-API-Key` desde su propia configuración. El navegador nunca ve la clave y CORS puede seguir deshabilitado.
2. **Aplicación personal en el propio equipo** (Fase 11): la clave se introduce en tiempo de ejecución y se guarda solo en memoria de la sesión. CORS se limita al origen local del frontend, por ejemplo `API_PUBLICA_CORS_ORIGENES=http://localhost:5173`.

En ambos casos el frontend debe usar `/api/v1/openapi.json` para generar tipos, respetar `Retry-After` y mostrar el aviso `experimental_no_acreditado`.

## Decisiones

- **Entrada propia dentro de `app/api/publica/`:** las salvaguardas existentes de AE-49, AE-52, la auditoría operativa y la autorización operativa, que revisan `app/api/**`, también la cubren.
- **Huellas en lugar de claves en claro:** la configuración no contiene secretos utilizables. La rotación no requiere tocar código.
- **Límite en memoria por proceso:** es la solución mínima que cumple el alcance sin añadir Redis ni otra infraestructura. Su alcance se declara en `/estado` y aquí.
- **Sesión propia de solo lectura** para juegos, sorteos y estadísticas: `SET TRANSACTION READ ONLY` en PostgreSQL y siempre ROLLBACK. Predicciones y simulaciones ya leen con sus transacciones de solo lectura.
- **Contratos públicos proyectados** en lugar de devolver tal cual los diccionarios internos, para no exponer enlaces web internos, identificadores de ejecución, configuración completa ni metadatos de entorno.
- **Configuración:** sin dependencias nuevas. Ajustes nuevos en `app/core/config.py` (`API_PUBLICA_*`) y entradas en `.env.example` sin valores secretos.
- **v2, arranque:** las garantías de registro y de IP del servidor se fijan con dos opciones de Uvicorn en el único arranque soportado, sin lanzador nuevo. Guía, ejemplos, docstrings, la prueba del proceso real y `tests/postgres_fase8.py` usan ese mismo arranque.
- **v2, fallos inesperados:** se convierten en el middleware propio, que ya asigna la solicitud y anota el monitoreo; así el 500 conserva las cabeceras y no se cuenta dos veces.

## Limitaciones

- El límite no es global entre procesos (ver arriba). Tampoco persiste entre reinicios.
- La IP es la del socket. Detrás de un proxy todas las solicitudes compartirían una IP; la Fase 10 debe decidir si confiar en `X-Forwarded-For` desde un proxy conocido. Hasta entonces el arranque soportado ignora esa cabecera (`--no-proxy-headers`).
- Arrancar sin las dos opciones del paso 4 no está soportado: Uvicorn volvería a escribir las consultas en su registro de acceso y a confiar en `X-Forwarded-For` desde `127.0.0.1`.
- Si fallara el propio middleware, el 500 lo genera el manejador global, que tampoco devuelve detalles, pero Starlette entrega esa excepción al servidor.
- La cuota cuenta solicitudes, no tiempo de CPU. Las estadísticas tienen coste 5, pero no hay un límite de concurrencia por consulta.
- Las lecturas de predicciones y simulaciones usan `SET TRANSACTION READ ONLY` sin variante SQLite. Su cableado predeterminado se verifica con PostgreSQL (`tests/postgres_fase8.py`); en SQLite se usan sustitutos.
- Sin despliegue ni HTTPS: los aporta la Fase 10. No exponer este proceso directamente a Internet.

## Verificación en Linux (Cloud) de la v2

Solo Cloud/Linux; no sustituye la validación nativa. Se repitieron solo las comprobaciones que justifican los archivos cambiados; las demás conservan su atribución a la v1 (siguiente apartado).

- **Entorno:** Python 3.14.9, FastAPI 0.162.0, Starlette 1.9.0, Uvicorn 0.54.0, pydantic 2.14.1, httpx 0.28.1 y SQLAlchemy 2.1.6. `pip check` y `git diff --check` limpios. RTK no estaba disponible y no se usó.
- **Antes:** extracción limpia de la base, con el parche v1 y las pruebas finales de la v2 (producto y documentos idénticos a la v1). `tests/unit/api_publica`: `6 failed, 86 passed`. Fallan las seis regresiones: error inesperado, métodos, proceso real (registro y excepción), `X-Forwarded-For`, ejemplos de arranque y selección de Windows. Pasan las 79 pruebas de la v1 y las 7 guardias.
- **Después:** `tests/unit/api_publica`, `92 passed` (79 de la v1 y 13 de la v2).
- **Pruebas existentes que leen archivos cambiados** (documentos, `seleccion_windows.txt`, `.env.example` o el árbol `app/`; 44 archivos): `3739 passed`.
- **Selección de Windows, solo recolección en Linux:** `3285 tests collected`, de ellas 92 de `tests/unit/api_publica`; la base recolecta 3193. No es una ejecución en Windows.
- **Sonda del auditor sin cambiar sus criterios:**
  - con el arranque soportado (`--uvicorn-opciones-seguras`, las mismas dos opciones del paso 4), `4/4`, código 0;
  - con Uvicorn sin esas opciones, que no está soportado, `2/4`: los dos criterios del middleware se cumplen y los dos del arranque no, como se esperaba.
  - Sobre la v1, en este entorno: `0/4` y `2/4`, igual que en la auditoría.
- **PostgreSQL 16.13 de pruebas aislado**, base recreada y revisión `0006`: `tests/postgres_fase8.py` cumple A–F. F usa el arranque de esta guía (`--no-access-log --no-proxy-headers`), da 200/401/401/404/404 y deja 5 líneas de monitoreo, sin la clave, su huella ni la clave enviada en la URL.
- **No repetido**, porque los archivos cambiados no lo justifican: la suite completa, las 535 regresiones de interfaces, OpenSSL y las siete demostraciones. Sus resultados se atribuyen a la v1. Tampoco se repitieron las mediciones de un millón, las capturas de Brave ni las baterías operativas de la Fase 6.

## Validación nativa del operador (24 de octubre de 2026)

Windows 11, PowerShell 5.1 y Python 3.14.6: `tests/unit/api_publica` dio 92 aprobadas sin fallos, errores ni omisiones; las cuatro sondas del auditor cumplieron sus criterios. La selección de Windows solo se recolectó (3285 casos, 92 de API); la ejecución amplia queda para el CI del PR.

En un contenedor temporal propio, PostgreSQL 16.14 y Alembic `0006` cumplieron A–F y A2: 14 consultas 200, transacción de solo lectura, filas y almacenes conservados, 10 respuestas 200 y 14 respuestas 429 con cuota 10, métodos de escritura rechazados y Uvicorn real con las dos opciones soportadas. El contenedor operativo y los archivos protegidos se conservaron; el contenedor y el temporal propios se eliminaron. [Evidencias, huellas y alcance](fase8_validacion_operador_2026-10-24.md).

## Verificación en Linux (Cloud) de la v1 (entrega original)

Resultados de la v1, sin repetir en la v2. Solo Cloud/Linux; no sustituye la validación nativa. Las baterías se solapan (la suite completa incluye las anteriores): no se suman.

- **Entorno:** Python 3.14.9, FastAPI 0.162.0, Starlette 1.9.0, pydantic 2.14.1, httpx 0.28.1, NumPy 2.5.4, SQLAlchemy 2.1.6; PowerShell 7.5.4 en el `PATH`, como en el runner Ubuntu de CI. `pip check` y `git diff --check` limpios. RTK no estaba disponible y no se usó.
- **Pruebas:**
  - API pública (`tests/unit/api_publica`): `79 passed`, en seguridad, límites y concurrencia, consultas, contrato e inventario, y preservación;
  - regresiones dirigidas de las interfaces existentes (web, REST interno y comandos de Productos 1–6 y Fases 4–7, 41 archivos): `535 passed`;
  - suite completa: `7517 passed`, sin fallos ni omisiones, en 26 min 35 s;
  - pasos del job Linux de CI: OpenSSL `--modo exigir` da `SUPERADOS 7/7`, y las siete demostraciones salen con código 0.
- **PostgreSQL 16.13 de pruebas aislado** (socket privado, base recreada desde cero, revisión `0006`, solo datos sintéticos): `tests/postgres_fase8.py` cumple A–F.
  - A: el cableado predeterminado responde 200 en las 14 consultas.
  - A2: un histórico inconsistente devuelve 500 sin detalles.
  - B: PostgreSQL rechaza escribir en la sesión de la API (`read-only transaction`).
  - C: filas de todas las tablas y almacenes intactos.
  - D: 24 solicitudes simultáneas con cuota 10 dan 10 × 200 y 14 × 429 con `Retry-After`.
  - E: POST/PUT/PATCH/DELETE responden 404/405.
  - F: un proceso Uvicorn real configurado por entorno responde 200/401/404/404 y su registro no contiene la clave ni su huella. En la v1 ese proceso no usaba aún las opciones del arranque soportado.
- **No repetido** (fuera de alcance): mediciones de un millón, capturas de Brave y baterías operativas de la Fase 6.
