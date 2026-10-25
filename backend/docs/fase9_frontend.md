# Fase 9.1 — Frontend de consulta (React) y pasarela local

**Estado:** entrega 9.1 v2 implementada sobre `615f3832296d74a7acea44e5ecdf7dc84a11d70a` (merge del PR #99, Fase 8; CI `40133227968` corresponde a esa base). Auditoría local y validaciones Linux/Cloud y Windows nativo con Brave instalado completadas sobre datos sintéticos. La evidencia Windows fue ejecutada por Daniel y auditada por ChatGPT; no se atribuye a Claude ni al CI. **Pendientes:** publicación manual y checks del PR de la 9.1. La **Fase 9 global sigue abierta**: la 9.1 cubre las consultas existentes de `/api/v1` y su criterio final se decide después ([matriz de huecos](#matriz-de-huecos-de-la-fase-9)). Se mantienen `experimental_no_acreditado`, AE-39 **NO-GO** y `AUTORIZA_EVALUACION = False`. [Validación del operador](fase9_validacion_operador_2026-10-25.md).

**v2 (auditoría de la v1, F9-LIM-01):** el plazo total del cliente de la pasarela cubre ahora toda la consulta y la conexión se cierra también en las salidas por error; el resto de la 9.1 no cambia ([verificación de la v2](#v2-plazo-total-del-cliente-f9-lim-01)).

## Arquitectura

```
navegador ──(mismo origen, sin credenciales)──► pasarela 127.0.0.1:8020 ──(X-API-Key del servidor)──► API pública 127.0.0.1:8010
             SPA compilada (frontend/dist)          app.pasarela.aplicacion:app                         app.api.publica.aplicacion:app
```

- **`frontend/`** — React 19 + TypeScript + Vite 7, Bootstrap 5.3 servido desde `dist/` (sin CDN) y la identidad visual de la consola HTMX (colores de marca, tarjetas, bolitas y colores de ColorLoto). Solo presenta lo que informa la API: no calcula estadísticas, vigencia, integridad ni aciertos.
- **`backend/app/pasarela/`** — proceso Python separado. Sirve únicamente los archivos compilados y es un cliente HTTP de `/api/v1`: no importa casos de uso, dominio, repositorios ni la base (lo comprueba `tests/unit/pasarela/test_pasarela_aislamiento.py`). Añade la clave en el servidor; la clave no existe en el navegador.
- La consola HTMX (`app.main:app`) sigue siendo la aplicación de escritura y ejecución. El enlace a ella desde la SPA es opcional, desactivado por defecto (`PASARELA_CONSOLA_LOCAL`) y solo admite `http://` en loopback con puerto.
- Despliegue, HTTPS y autenticación de escritura son de la Fase 10.

## Arranque local (Linux o Windows)

Tres procesos en `127.0.0.1`; ninguno se expone a la red.

1. Generar una clave para el frontend: `python -m scripts.api_publica_claves generar --id frontend`. Imprime la clave **una sola vez** y su entrada `frontend:sha256:<huella>`.
2. API pública (Fase 8), con la **huella** en `API_PUBLICA_CLAVES`. Arrancar la API: `uvicorn app.api.publica.aplicacion:app --host 127.0.0.1 --port 8010 --no-access-log --no-proxy-headers`.
3. Pasarela, con la **clave** en `PASARELA_CLAVE_API`, en el entorno de la sesión o en `backend/pasarela.privado.env`; ese archivo queda fuera de Git (`*.privado.env`). Arrancar la pasarela: `uvicorn app.pasarela.aplicacion:app --host 127.0.0.1 --port 8020 --no-access-log --no-proxy-headers`.
4. Abrir `http://127.0.0.1:8020/`. La aplicación local HTMX (`app.main:app`) sigue siendo la consola de escritura y ejecución.

Antes, una sola vez por cambio del frontend: `npm ci` y `npm run build` en `frontend/`. Sin `frontend/dist`, la pasarela responde 503 `frontend_no_compilado` en las rutas de la SPA. Plantilla sin secretos: `backend/pasarela.ejemplo.env`.

**Modo desarrollo (Vite).** `npm run dev` escucha solo en `127.0.0.1:5173` (`VITE_PUERTO` lo cambia, `strictPort`), sin CORS, y reenvía `/api/v1` y `/pasarela` a la pasarela (`PASARELA_URL`, por defecto `http://127.0.0.1:8020`, validada como loopback) sin cambiar `Host`, sin `X-Forwarded-*` y sin seguir redirecciones. La pasarela no relaja ningún control: para aceptar este modo hay que añadir de forma explícita `127.0.0.1:5173` a `PASARELA_HOSTS` y `http://127.0.0.1:5173` a `PASARELA_ORIGENES`. La clave nunca pasa por Vite.

## Pantallas y consultas

| Pantalla (ruta de la SPA) | Consultas `/api/v1` | Fichas por visita |
|---|---|---|
| Inicio `/` | `juegos` | 1 la primera vez por carga de página; después, en memoria |
| Ficha y resumen `/juegos/:codigo` (`?hasta_numero_sorteo`) | `juegos/{codigo}`, `…/estadisticas/resumen` | 1 + 5 |
| Sorteos `/juegos/:codigo/sorteos` (`?desde&hasta&numero_desde&numero_hasta&orden&por_pagina&pagina`) | `…/sorteos` | 2 |
| Sorteo `/juegos/:codigo/sorteos/:numero` | `…/sorteos/{n}` | 1 |
| Estadísticas `/juegos/:codigo/estadisticas` (`?hasta_numero_sorteo`) | `…/estadisticas` (índice) y `…/panel` | 1 + 5 |
| Métrica `/juegos/:codigo/estadisticas/:metrica` (corte y `anio`, `mes`, `dia_semana` o `ventana` según el selector) | `…/estadisticas/{metrica}` | 5 |
| Predicción guardada `/juegos/:codigo/prediccion` (`?cartera`) | `…/predicciones` | 3 |
| Simulaciones `/juegos/:codigo/simulaciones` (`?limite`) | `…/simulaciones` | 2 |
| Simulación `/simulaciones/:id` | `simulaciones/{id}` | 2 |
| Servicio `/servicio` | `salud` y `estado` | 0 + 1 |

- **Frescura:** la informan el resumen, el panel y cada métrica (`al_dia`, `desactualizado` con sus días, `sin_datos`). La consulta de predicciones no la informa: la pantalla muestra corte, última fecha y el estado de la base, marca la frescura como «no informada por esta consulta» y advierte que «base disponible» no equivale a «datos al día». Un campo ausente se muestra como «no informado».
- **Métricas:** solo tienen página las que declara el índice real (18 en Baloto y Revancha, 11 en MiLoto y 5 en ColorLoto, comprobadas en el recorrido). Las anteriores muestran sus indicadores en el panel con «página de detalle pendiente»; las que no aplican, su motivo. La tabla genérica muestra columnas, unidades y formatos declarados y, si una fila trae claves no declaradas (p. ej. `contraste`, `motivo_p_value` en correlaciones), una columna «Datos adicionales»: no se pierde contenido. La gráfica de la consola HTMX se sustituye por una nota con su tabla y su referencia.
- **Predicción:** historial con selección por `?cartera=`, modelo proyectado, clasificación temporal, integridad informada, combinaciones (números y superbalota o pares número-color), resultado observado con aciertos por línea y frente a la base. Explicación, clasificación de candidatos y fiabilidad quedan pendientes.
- **Simulaciones:** listado con integridad y motivo; detalle con parámetros (identidad completa), integridad, huella del contenido, estadísticas comparadas y familia. Una simulación alterada llega como 409 `alterado` y no se muestra su contenido.
- **Servicio:** salud y estado **del proceso de la API**; la página dice que no informa de la operación automática ni de sus tareas.
- **Avisos:** el pie de todas las pantallas recuerda que las estadísticas describen sorteos ocurridos y que predicciones y simulaciones son de uso experimental no acreditado; las pantallas de predicción y simulación muestran además el aviso y el contexto del backend.

## Decisiones y versiones

- **Node:** `engines` `>=22.12.0`. Según el calendario oficial (`nodejs/Release`, consultado el 2026-10-25), 22 y 24 son LTS en mantenimiento (hasta 2027-04-30 y 2028-04-30) y 26 pasa a LTS activa el 2026-10-28. Verificado en Cloud con Node 22.22.2 y npm 10.9.7; el CI prueba 22 y 24. Si hay que instalar Node, se recomienda 24 LTS; si ya hay un Node ≥ 22.12, no hace falta cambiarlo.
- **Dependencias exactas** (cada versión con más de dos semanas), fijadas en `package.json` y `package-lock.json` (lockfile v3), instaladas con `npm ci --ignore-scripts`: react y react-dom 19.3.0, react-router-dom 7.18.4, bootstrap 5.3.8; vite 7.3.7, @vitejs/plugin-react 5.2.0, typescript 5.9.3, vitest 3.2.7, jsdom 26.1.0, @testing-library/react 16.3.3, @testing-library/dom 10.4.2, @types/node 22.20.5, @types/react y @types/react-dom 19.3.0, openapi-typescript 7.13.0 y playwright 1.56.1.
- **Contrato:** `frontend/src/api/openapi.json` es la exportación versionada de la app pública de la base (`python -m scripts.exportar_openapi_publica`, con `--comprobar`); `esquema.d.ts` se genera con openapi-typescript (`npm run tipos`; `npm run tipos:comprobar` exige igualdad). `test_pasarela_contrato.py` compara la proyección contractual con la app de la base sin consultar ninguna base. Las zonas genéricas (`{[key]: unknown}`) se describen y validan en ejecución en `src/api/presentacion.ts` (decodificadores sin `any`); una estructura distinta se informa como `estructura_no_reconocida` sin mostrar datos a medias.
- **Formato:** `formatear` reproduce el de la consola HTMX, incluidos el redondeo al par en empates exactos y el signo de `-0`; `src/pruebas/formatos.json` lo genera el `formatear` real del backend y lo comprueban Vitest y pytest. Diferencia documentada: con formato `texto` o `tipo_p` un número se muestra con `String` de JS.
- **Datos y cuota:** sin sondeo ni reintentos automáticos; las peticiones idénticas en curso se comparten (StrictMode no duplica llamadas) y una respuesta antigua no sobrescribe la vigente. Solo `/api/v1/juegos` se guarda, en memoria y durante la vida de la página; todo lo demás es `no-store`; nada va a almacenamiento persistente. Ante 429 la vista muestra `Retry-After`, deshabilita «Reintentar» hasta que pasa la espera y advierte que esperar no garantiza la cuota si otras pestañas la consumen. «Reintentar» solo aparece en errores transitorios (red, 429 y 5xx). Las cuotas predeterminadas de la API (60/min por clave y 120/min por IP) no cambian.
- **Filtros en la URL:** la consulta del navegador es la única fuente; recargar, entrar por enlace o usar atrás/adelante reproduce la vista. Solo se reenvían los nombres admitidos por cada ruta; la validación semántica es de la API (422 con sus detalles).

## Pasarela: controles y límites

- **Destino fijo:** `PASARELA_API_URL` solo `http://` sobre IP loopback con puerto, sin credenciales, ruta, consulta ni fragmento; nunca lo elige el navegador. No sigue redirecciones (un 3xx es 502 `respuesta_no_valida`).
- **Rutas cerradas:** solo GET y las 13 plantillas del OpenAPI versionado, con su lista de parámetros; excluidas `/api/v1/docs` y `/api/v1/openapi.json`. Rechaza rutas ambiguas, `..`, separadores codificados, caracteres de control, barra final y rutas de más de 512 caracteres (400 `ruta_no_valida`); una ruta de API desconocida es 404 `ruta_no_disponible`.
- **Parámetros:** como máximo 16, consulta ≤ 512 caracteres, valores ≤ 80 caracteres de `[A-Za-z0-9_.:-]`, sin repetir ni nombres no admitidos (422).
- **Acceso:** cliente loopback; `Host` exacto entre `PASARELA_HOSTS` (una sola cabecera); en `/api` y `/pasarela/`, `Origin` (si viene) entre `PASARELA_ORIGENES` y `Sec-Fetch-Site` (si viene) `same-origin` o `none`. CORS deshabilitado. `X-Forwarded-For` se ignora.
- **Cabeceras:** a la API solo `Accept`, `X-API-Key` propia, `User-Agent` y `Connection: close`; nunca cookies ni credenciales del cliente. Al navegador solo `Content-Type`, `X-Request-ID`, `Retry-After` (429/503) y `X-RateLimit-*`, más las de seguridad: CSP `default-src 'self'` (sin recursos externos, `frame-ancestors 'none'`), `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: no-referrer`, COOP/CORP `same-origin`, `Permissions-Policy` y `Cache-Control: no-store`.
- **Límites concretos:** 4 consultas simultáneas a la API; quien no obtiene hueco en 2 s recibe 503 `pasarela_ocupada` con `Retry-After: 1`; 15 s para toda la consulta —conexión, envío, estado y cabeceras, cuerpo y EOF— y, dentro de ese plazo, 10 s por operación de socket: cada espera usa el menor de los dos y al vencer responde 504 `api_sin_respuesta`; 4 MiB por cuerpo (502 `respuesta_demasiado_grande`). La lectura usa `http.client` en un hilo (`anyio.to_thread`) sin bloquear el bucle; la consulta termina al vencer su espera (no queda trabajo bloqueado), cierra la conexión —también la que cede a la respuesta con `Connection: close`— y solo entonces libera su hueco.
- **Errores propios:** formato único `{"error": {codigo, mensaje, solicitud}}`, con `X-Request-ID` y `no-store`, sin rutas, claves ni trazas. Un fallo inesperado se convierte en 500 `error_interno` y el registro solo anota su clase. Los errores contractuales de la API (401, 404, 409, 422, 429, 500, 503) pasan con su código y `Retry-After`.
- **Estáticos:** solo archivos dentro de `dist/` (rutas resueltas, sin enlaces que salgan) y extensiones conocidas; un recurso inexistente es 404 y no recibe `index.html`.
- **Secreto:** la clave es `SecretStr` y no aparece en `repr`, registros, respuestas ni errores. Ni la clave ni su huella llegan al bundle, al tráfico del navegador, a sus respuestas, al almacenamiento, a la URL ni a los registros: lo comprueban un canario de compilación (`npm run canario`), las pruebas de la pasarela y el recorrido real, que busca el canario en todas las respuestas recibidas por el navegador y en los registros de los tres procesos. La presencia del nombre público `X-API-Key` en el esquema generado no es una filtración: el escaneo excluye `esquema.d.ts` y `openapi.json` y busca código que envíe la cabecera.

## Verificación

### v2: plazo total del cliente (F9-LIM-01)

La auditoría de la v1 reprodujo con una sonda que el plazo total solo se comprobaba tras recibir bytes: unas cabeceras por fragmentos o un cuerpo con cierre tardío superaban el plazo, y el segundo caso se aceptaba como 200. La v2 aplica a cada operación de socket (conexión, envío y cada lectura de estado, cabeceras, cuerpo o EOF) el menor entre el tiempo por operación y lo que queda del plazo, comprueba el plazo también tras las lecturas servidas desde el búfer y cierra la respuesta cuando `http.client` le cede el socket. Interfaz, errores, límites, concurrencia y arranques no cambian.

| Comprobación (Linux/Cloud, 25 de octubre de 2026) | v1 | v2 |
|---|---|---|
| Sonda del auditor, sin cambios (`sonda-plazo-pasarela.py`, plazo 0,05 s) | código 1: 504 a 0,20 s y 200 a 0,20 s | código 0: 504 a 0,05 s en ambos casos |
| `test_pasarela_plazo_total.py` (8 pruebas: cabeceras por fragmentos, EOF tardío, goteo del cuerpo, plazo agotado antes de conectar, huecos de concurrencia, cierre tras el límite de tamaño; respuesta rápida y timeout por operación como controles) | 6 fallan, 2 pasan | 8 aprueban |
| `tests/unit/pasarela` completa | 178 aprobadas | 186 aprobadas |
| Intercambio HTTP real a través de la pasarela con la API sintética (consultas normales, 404, 409, 422 y 10 consultas concurrentes con 4 huecos) | — | 14/14 comprobaciones; sin canario en los registros |

La SPA, la API pública y las dependencias no cambian. En la entrega Cloud v2 sus resultados se retuvieron de la v1 (tabla siguiente), sin repetirlos. La validación Windows posterior ejecutó por separado las 379 pruebas Vitest y las 92 de la API pública sobre la v2; se documenta en el cierre del operador.

### Evidencia de la v1

**Linux (Cloud, Python 3.14.9, Node 22.22.2, Chromium 141 de Playwright 1.56.1), datos sintéticos.** Detalle, comandos, códigos de salida, JUnit y capturas en el ZIP de evidencias de la entrega v1.

| Comprobación | Resultado (25 de octubre de 2026) |
|---|---|
| `npm ci --no-audit --no-fund --ignore-scripts` | 187 paquetes desde `package-lock.json`, código 0 |
| `npm run tipos:comprobar` · `npm run typecheck` | igual · sin errores |
| Vitest (componentes en StrictMode, cliente, decodificadores, formato, configuración de Vite) | 379 aprobadas |
| `npm run build` | `dist/`: JS 329,8 kB y CSS 232,9 kB (sin mapas ni recursos externos) |
| `npm run canario` | 0 hallazgos (canario y huella ausentes del bundle; sin envío de credenciales, almacenamiento ni terceros) |
| `python -m scripts.exportar_openapi_publica … --comprobar` | igual a la app pública de la base |
| `tests/unit/pasarela` | 178 aprobadas |
| `tests/unit/api_publica` | 92 aprobadas |
| Regresiones afectadas: 58 archivos, los que recorren árboles del repositorio (escáneres de `app/`, `scripts/` y `tests/`) y los lectores de `seleccion_windows.txt` | 1350 aprobadas y 66 omitidas (ensayos de Fase 6 que requieren PowerShell real) |
| `pip check` | sin problemas |
| Recorrido `normal` (360, 390 y 1280 px) | 297 visitas y 24 comprobaciones correctas: cuatro juegos, 52 métricas del índice por ancho (18/18/11/5), detalles, errores 404 y 422 reales, simulación alterada (409), teclado y foco, filtros con atrás/adelante/recarga/acceso directo, llamadas en navegación; controles HTTP directos 11/11; canario ausente en 1884 respuestas al navegador y en los registros |
| `cuota` · `api_caida` · `sin_clave` · `clave_incorrecta` | 429 con cuenta atrás y reintento manual sin reintentos automáticos · 503 `api_no_disponible` · 503 `pasarela_no_configurada` · 401 `no_autenticado`; sin reintentos automáticos |
| `vite` | 12 visitas correctas en modo desarrollo; StrictMode con una sola llamada a `/juegos`; `Host` ajeno rechazado por Vite y `Origin` ajeno por la pasarela |

Los grupos no se suman: son baterías distintas. El primer intento del recorrido `normal` falló en una comprobación de la propia prueba (una espera que se cumplía con el título de la página anterior); se endurecieron sus esperas, sin cambios del producto, y el segundo intento pasó completo. Ambos constan en las evidencias.

**Recorrido HTTP completo.** `python -m tests.recorrido_fase9 --salida <carpeta> [--escenario …]` arranca la API pública **real** (`crear_app`) con proveedores **sintéticos** (`tests.fase9_api_sintetica:app`: SQLite de la Fase 7 y almacenes temporales de la Fase 4), la pasarela real con una clave canario y la SPA compilada, con las opciones documentadas y puertos libres. **No es una prueba de PostgreSQL.** Escenarios: `normal` (todas las pantallas de los cuatro juegos a 360, 390 y 1280 px, todas las métricas del índice, teclado y foco, filtros con atrás/adelante y recarga, llamadas, tráfico, almacenamiento, consola y controles HTTP directos), `cuota`, `api_caida`, `sin_clave`, `clave_incorrecta` y `vite`.

**Windows y Brave:** validación nativa completada y auditada el 25 de octubre de 2026: 379 pruebas Vitest, 186 de pasarela y 92 de API pública sin fallos, errores ni omisiones; seis escenarios Brave, incluido Vite mediante el adaptador externo corregido. Son resultados propios del operador, separados de los antecedentes Linux anteriores. [Evidencia y límites](fase9_validacion_operador_2026-10-25.md); [protocolo](fase9_windows.md).

## Matriz de huecos de la Fase 9

| Función de la consola HTMX | 9.1 | Pendiente para otra decisión |
|---|---|---|
| Juegos y reglas | Cubierto | — |
| Resumen con frescura y corte | Cubierto | Gráficas de barras |
| Sorteos: filtros, paginación y detalle | Cubierto | — |
| Panel de Fase 5 y métricas con página (18/18/11/5) | Cubierto | Gráficas nuevas |
| Páginas de las métricas anteriores (30 en Baloto) | Indicadores en el panel | Página de detalle (no hay consulta v1) |
| Predicción guardada | Cubierto (historial, modelo, clasificación temporal, integridad, combinaciones, observado, frente a la base) | Explicación, clasificación de candidatos, fiabilidad |
| Simulaciones guardadas | Cubierto | Lanzar simulaciones (escritura) |
| Salud y estado de la API | Cubierto | — |
| Modelos y laboratorio (Fase 3) | — | Modelos completos |
| Carteras (Producto 5) y resultados avanzados (Producto 6) | — | Pendiente |
| Exportaciones e impresión | — | Pendiente |
| Importación, generación, configuración y automatización | — | Acciones administrativas; requieren autenticación de escritura (Fase 10) |
| Operación automática y panel diario | — | Sin consulta en la API v1; siguen en la consola local |

El criterio final de la Fase 9 (paridad, alcance o sustitución de la consola) se decide después; esta entrega no lo cierra.

## Limitaciones conocidas

- La cuota y el monitoreo de la API son por proceso (Fase 8); la pasarela no añade una cuota propia.
- La pasarela solo admite destinos y clientes loopback: no es un proxy para red ni despliegue.
- Los colores de ColorLoto fuera de la paleta conocida se muestran con su nombre y sin muestra de color.
- Con formato `texto`/`tipo_p`, un número puede verse distinto que en la consola HTMX (JSON no conserva `100.0` ni la notación exponencial de Python).
