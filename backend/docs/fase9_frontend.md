# Fase 9.1 — Frontend de consulta (React) y pasarela local

**Entrega 9.4 (sobre `4f4dd639581168b08c95816660f80fc4f735b1ac`, merge del PR #102):** consultas de modelos registrados, carteras de Producto 5 y resultados de Producto 6. V2 validada en Linux y Windows nativo con Brave y aprobada por auditoría; publicación manual, integración y CI pendientes. [Validación del operador](fase9_4_validacion_operador_2026-10-28.md); [diseño](#entrega-94-modelos-carteras-y-resultados-guardados); [protocolo nativo](fase9_windows.md#entrega-94-validación-nativa-completada).

**Entrega 9.3 (sobre `ed0ee427f7a6fcd2a33cbc538435a3df2e299710`, merge del PR #101 que integró la 9.2):** explicación guardada, clasificación de candidatos y fiabilidad observada, solo de consulta.

- **Validación 9.3 v2:** Linux/Cloud y Windows 11 nativo con Brave; auditoría aprobada ([cierre del operador](fase9_3_validacion_operador_2026-10-27.md)).
- **Integración 9.3:** integrada en PR #102 (merge `4f4dd639581168b08c95816660f80fc4f735b1ac`), con los cinco trabajos aprobados: Node 22, Node 24, Chromium/Linux, Python/Linux y Python/Windows (workflows `40589232731` y `40589232763`). Son antecedentes de la 9.3, no resultados de la 9.4.

[Detalle de la entrega](#entrega-93-explicación-clasificación-de-candidatos-y-fiabilidad). La Fase 9 global sigue abierta.

**Entrega 9.2 (sobre `9966a4bbcb8d81953fb283b07544636f4c11fc95`, merge del PR #100 que integró la 9.1):** páginas de las métricas anteriores en el mismo índice y la misma ruta de métrica.

- **Validación:** en Linux y en Windows 11 nativo con Brave, sobre datos sintéticos.
- **Auditoría:** aprobada el 26 de octubre de 2026 ([validación del operador](fase9_2_validacion_operador_2026-10-26.md)).
- **Integración:** PR #101, merge `ed0ee427f7a6fcd2a33cbc538435a3df2e299710`, con sus cinco checks aprobados (ejecuciones de Actions `40291140855` y `40291140889`); incluye el arreglo de pruebas `e38362bf2341cb30389141c67eb37b5b89a6e2fe`. Hasta entonces figuraba como pendiente de publicación manual y del CI del nuevo PR.

[Detalle de la entrega](#entrega-92-páginas-de-las-métricas-anteriores).

**Estado:** entrega 9.1 v2 implementada sobre `615f3832296d74a7acea44e5ecdf7dc84a11d70a` (merge del PR #99, Fase 8; CI `40133227968` corresponde a esa base). Auditoría local y validaciones Linux/Cloud y Windows nativo con Brave instalado completadas sobre datos sintéticos. La evidencia Windows fue ejecutada por Daniel y auditada por ChatGPT; no se atribuye a Claude ni al CI. *Actualización posterior:* la 9.1 se integró en PR #100 (merge `9966a4b`). La **Fase 9 global sigue abierta**: la 9.1 cubre las consultas existentes de `/api/v1`; el alcance restante sigue el plan de cinco partes aceptado ([matriz de huecos](#matriz-de-huecos-de-la-fase-9)). Se mantienen `experimental_no_acreditado`, AE-39 **NO-GO** y `AUTORIZA_EVALUACION = False`. [Validación del operador](fase9_validacion_operador_2026-10-25.md).

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
| Métrica `/juegos/:codigo/estadisticas/:metrica` (corte y `anio`, `mes`, `dia_semana`, `ventana` o `color` según el selector; `pagina` si el índice la declara) | `…/estadisticas/{metrica}` | 5 |
| Predicción guardada `/juegos/:codigo/prediccion` (`?cartera`) | `…/predicciones`; `…/fiabilidad?hasta=<corte>` solo al pulsar «Consultar fiabilidad» | carga automática 4 con catálogo sin caché (1 + 3); acción explícita posterior 3 |
| Fiabilidad `/juegos/:codigo/fiabilidad` (`?hasta`), 9.3 | `…/fiabilidad` | 3 |
| Modelos registrados `/juegos/:codigo/modelos` (página, modelo y perfil) | `…/modelos-guardados` | 2; 3 con catálogo frío |
| Modelo registrado `/juegos/:codigo/modelos/:identificador` | `…/modelos-guardados/{clave}` | 2; 3 con catálogo frío |
| Carteras Producto 5 `/juegos/:codigo/carteras` (página, línea e intervalo de objetivos) | `…/carteras-guardadas` | 2; 3 con catálogo frío |
| Cartera Producto 5 `/juegos/:codigo/carteras/:identificador` | `…/carteras-guardadas/{clave}` | 2; 3 con catálogo frío |
| Resultados Producto 6 `/juegos/:codigo/resultados` (procedencia, línea, tipo, objetivos y página) | `…/resultados` | 5; 6 con catálogo frío |
| Simulaciones `/juegos/:codigo/simulaciones` (`?limite`) | `…/simulaciones` | 2 |
| Simulación `/simulaciones/:id` | `simulaciones/{id}` | 2 |
| Servicio `/servicio` | `salud` y `estado` | 0 + 1 |

- **Frescura:** la informan el resumen, el panel y cada métrica (`al_dia`, `desactualizado` con sus días, `sin_datos`). La consulta de predicciones no la informa: la pantalla muestra corte, última fecha y el estado de la base, marca la frescura como «no informada por esta consulta» y advierte que «base disponible» no equivale a «datos al día». Un campo ausente se muestra como «no informado».
- **Métricas:** solo tienen página las que declara el índice real. En la 9.1 eran 18 en Baloto y Revancha, 11 en MiLoto y 5 en ColorLoto. Con la 9.2 son 30, 30, 22 y 36, porque se suman las métricas anteriores; las cuentas se comprueban en el recorrido. Las que no aplican muestran su motivo. La tabla genérica muestra columnas, unidades y formatos declarados y, si una fila trae claves no declaradas (p. ej. `contraste`, `motivo_p_value` en correlaciones), una columna «Datos adicionales»: no se pierde contenido. La gráfica de la consola HTMX se sustituye por una nota con su tabla y su referencia.
- **Predicción:** historial con selección por `?cartera=`, modelo proyectado, clasificación temporal, integridad informada, combinaciones (números y superbalota o pares número-color), resultado observado con aciertos por línea y frente a la base. En la 9.1 y la 9.2 quedaban pendientes la explicación, la clasificación de candidatos y la fiabilidad; la 9.3 las añade ([detalle](#entrega-93-explicación-clasificación-de-candidatos-y-fiabilidad)).
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
- **Rutas cerradas:** solo GET y las plantillas del OpenAPI versionado (13 en la 9.1/9.2, 14 en la 9.3 y 19 en la 9.4, con los cinco GET de modelos, carteras y resultados guardados), con su lista de parámetros; excluidas `/api/v1/docs` y `/api/v1/openapi.json`. Rechaza rutas ambiguas, `..`, separadores codificados, caracteres de control, barra final y rutas de más de 512 caracteres (400 `ruta_no_valida`); una ruta de API desconocida es 404 `ruta_no_disponible`.
- **Parámetros:** como máximo 16, consulta ≤ 512 caracteres, valores ≤ 80 caracteres de `[A-Za-z0-9_.:-]`, sin repetir ni nombres no admitidos (422).
- **Acceso:** cliente loopback; `Host` exacto entre `PASARELA_HOSTS` (una sola cabecera); en `/api` y `/pasarela/`, `Origin` (si viene) entre `PASARELA_ORIGENES` y `Sec-Fetch-Site` (si viene) `same-origin` o `none`. CORS deshabilitado. `X-Forwarded-For` se ignora.
- **Cabeceras:** a la API solo `Accept`, `X-API-Key` propia, `User-Agent` y `Connection: close`; nunca cookies ni credenciales del cliente. Al navegador solo `Content-Type`, `X-Request-ID`, `Retry-After` (429/503) y `X-RateLimit-*`, más las de seguridad: CSP `default-src 'self'` (sin recursos externos, `frame-ancestors 'none'`), `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: no-referrer`, COOP/CORP `same-origin`, `Permissions-Policy` y `Cache-Control: no-store`.
- **Límites concretos:** 4 consultas simultáneas a la API; quien no obtiene hueco en 2 s recibe 503 `pasarela_ocupada` con `Retry-After: 1`; 15 s para toda la consulta —conexión, envío, estado y cabeceras, cuerpo y EOF— y, dentro de ese plazo, 10 s por operación de socket: cada espera usa el menor de los dos y al vencer responde 504 `api_sin_respuesta`; 4 MiB por cuerpo (502 `respuesta_demasiado_grande`). La lectura usa `http.client` en un hilo (`anyio.to_thread`) sin bloquear el bucle; la consulta termina al vencer su espera (no queda trabajo bloqueado), cierra la conexión —también la que cede a la respuesta con `Connection: close`— y solo entonces libera su hueco.
- **Errores propios:** formato único `{"error": {codigo, mensaje, solicitud}}`, con `X-Request-ID` y `no-store`, sin rutas, claves ni trazas. Un fallo inesperado se convierte en 500 `error_interno` y el registro solo anota su clase. Los errores contractuales de la API (401, 404, 409, 422, 429, 500, 503) pasan con su código y `Retry-After`.
- **Estáticos:** solo archivos dentro de `dist/` (rutas resueltas, sin enlaces que salgan) y extensiones conocidas; un recurso inexistente es 404 y no recibe `index.html`.
- **Secreto:** la clave es `SecretStr` y no aparece en `repr`, registros, respuestas ni errores. Ni la clave ni su huella llegan al bundle, al tráfico del navegador, a sus respuestas, al almacenamiento, a la URL ni a los registros: lo comprueban un canario de compilación (`npm run canario`), las pruebas de la pasarela y el recorrido real, que busca el canario en todas las respuestas recibidas por el navegador y en los registros de los tres procesos. La presencia del nombre público `X-API-Key` en el esquema generado no es una filtración: el escaneo excluye `esquema.d.ts` y `openapi.json` y busca código que envíe la cabecera.

## Entrega 9.2: páginas de las métricas anteriores

**Base:** `9966a4bbcb8d81953fb283b07544636f4c11fc95`, merge del PR #100.

**Estado:** implementada y validada con datos sintéticos, en Linux y en Windows 11 nativo con Brave. La auditoría independiente la aprobó ([validación del operador](fase9_2_validacion_operador_2026-10-26.md)). *Actualización:* integrada en el PR #101 (merge `ed0ee427f7a6fcd2a33cbc538435a3df2e299710`), con sus cinco checks aprobados e incluido el arreglo de pruebas `e38362bf2341cb30389141c67eb37b5b89a6e2fe`; antes figuraban pendientes la publicación manual y el CI del nuevo PR.

**Alcance.** El índice declara las métricas anteriores de la consola: 12 en Baloto y en Revancha, 11 en MiLoto y 31 en ColorLoto, incluidos colores, conteo por color y pares número-color. Lo hace con `titulo`, `grupo`, `origen` (`fase5` o `anterior`), `parametro` y `paginada`. Todas se consultan en `GET /api/v1/juegos/{codigo}/estadisticas/{metrica}`; no hay una ruta por métrica.

**Cálculo y contrato.**
- El backend calcula con la misma receta que la consola HTMX (`calcular_sin_persistir`) y no escribe en `estadisticas`.
- `RespuestaDeMetrica` es tipada:
  - indicadores;
  - tablas con columnas (formato y unidad), filas y `paginacion`;
  - notas;
  - selector de filtro con sus opciones;
  - corte, frescura y aplicabilidad.
- El frontend no calcula: presenta.

**Filtros.**
- `anio`, `mes` y `dia_semana` valen por defecto lo del último sorteo; `ventana`, una de las existentes (20 por defecto).
- `color` es el código exacto de un color vigente u observado; por defecto, el primero.
- Un parámetro que la métrica no declara, un valor fuera de las opciones o una página fuera de rango dan 422 `parametro_no_valido`.

**Paginación explícita.** La coocurrencia de tríos de los juegos numéricos se pagina en 100 filas, con `pagina`, total de filas y total de páginas. Es la única tabla que crece con el histórico (hasta 12 341 tríos en Baloto), y la consola también la pagina en 100. Las demás están acotadas por las reglas del juego (como mucho 903 pares en Baloto y 42 pares número-color en ColorLoto) y se envían completas. La muestra sintética de pares de Baloto, con 443 filas, ocupa 83 KB, frente al límite de 4 MiB de la pasarela. La pantalla muestra «N filas en total · página X de Y · 100 por página» y su paginación accesible. No se recorta en silencio ni se suben los límites de la pasarela.

**ColorLoto.**
- Cada par número-color se separa en una columna `numero` y otra `color`.
- El color se muestra con la muestra y el nombre de la convención existente de la consola (`<Color>`).
- Un color fuera de la paleta conocida conserva su nombre, sin muestra.

**Estados.**

| Situación | Código | Qué devuelve |
|---|---|---|
| Sin sorteos | 200 | `sin_datos` |
| Periodo vacío | 200 | `sin_sorteos_en_el_periodo` |
| Histórico no válido | 409 | `historico_no_valido` («el histórico cargado no es consistente; no se calcula la estadística») |
| Parámetros no válidos | 422 | `parametro_no_valido` |
| Base no disponible | 503 | `base_no_disponible` |

**Presupuesto.** Una consulta de métrica por pantalla, con el mismo coste de cuota que las demás (5 fichas). Se conservan cuotas, `Retry-After`, 429, la lista de la pasarela y el plazo total de 15 s de la 9.1 v2. La pasarela solo añade `color` y `pagina` a los parámetros admitidos de esa ruta. Siguen siendo 13 plantillas (la 9.3 añade la decimocuarta, la de fiabilidad).

**Accesibilidad y móvil.** Se mantienen las tablas de la 9.1 (encabezados, desplazamiento propio y alineación). La paginación es la de Sorteos: `nav` «Paginación», enlaces con nombre accesible y `aria-current` en la página actual. El foco pasa al contenido al cambiar de ruta, como en la 9.1; cambiar filtro o página no lo mueve.

**Evidencia en Linux** (Cloud, Python 3.14.9, pytest 9.1.1, Node 22.22.2, Chromium de Playwright; no acredita Windows ni Brave):

| Comprobación | Resultado |
|---|---|
| `test_api_publica_metricas_anteriores.py` (comparación con la receta de la consola en los cuatro juegos, con y sin corte, filtros, número-color, paginación, estados y cuota) | 94 aprobadas |
| `tests/unit/api_publica` y `tests/unit/pasarela` | 186 y 192 aprobadas |
| Vitest · `tipos:comprobar` · `typecheck` · `build` · `canario` | 456 aprobadas · igual · sin errores · correcto · 0 hallazgos |
| Suite completa del backend | 7812 aprobadas y 87 omitidas (baterías de PowerShell de Fase 6), sin fallos |
| Recorrido `normal` a 360, 390 y 1280 px | 507/507 visitas y 26/26 comprobaciones: todas las métricas del índice (30/30/22/36) en los tres anchos, página 2 de la tabla paginada, color `ROJO`, color y página no válidos, 42 muestras de color en `frecuencia-pares-numero-color`; 11 controles HTTP directos sin fallos; canario ausente en 3144 respuestas |

Los registros, los JUnit y el resultado del recorrido están en el ZIP de evidencias de la entrega.

**Evidencia en Windows.** Daniel ejecutó la etapa A sobre la v2 de la entrega en Windows 11 nativo con Brave instalado (Python 3.14.6 y datos sintéticos):

- 456 pruebas Vitest;
- 186 pruebas de API pública y 192 de pasarela, dentro de 772 pruebas Python;
- tipos, TypeScript, compilación y canario correctos;
- el recorrido `normal` en Brave, con 507 visitas y 26 comprobaciones sobre todas las métricas del índice (30/30/22/36).

Los ajustes posteriores v3 y v4 solo tocan Fase 6 (controlador de la tarea, ensayo y sus pruebas), no el frontend, la API ni la pasarela. Por eso estas baterías conservan su atribución a la corrida sobre v2 y no se repitieron. Son resultados del operador, separados de la evidencia Linux anterior. [Validación del operador](fase9_2_validacion_operador_2026-10-26.md).

## Entrega 9.3: explicación, clasificación de candidatos y fiabilidad

**Base:** `ed0ee427f7a6fcd2a33cbc538435a3df2e299710`, merge del PR #101, que integró la 9.2 con sus cinco checks aprobados e incluye el arreglo de pruebas `e38362bf2341cb30389141c67eb37b5b89a6e2fe`.

**Estado:** 9.3 v2 validada en Linux y Windows nativo con Brave y aprobada por la auditoría; integrada en PR #102 (merge `4f4dd639581168b08c95816660f80fc4f735b1ac`), con los cinco trabajos aprobados: Node 22, Node 24, Chromium/Linux, Python/Linux y Python/Windows (workflows `40589232731` y `40589232763`). Son antecedentes de la 9.3, no resultados de la 9.4. [Cierre del operador](fase9_3_validacion_operador_2026-10-27.md). El [protocolo dirigido](fase9_windows.md#entrega-93-protocolo-dirigido) se conserva como referencia ya ejecutada, sin repetirlo por rutina. Fase 9 global abierta: 9.3 integrada en PR #102; 9.4 v2 validada en Linux y Windows/Brave y aprobada por auditoría, con publicación manual, integración y CI pendientes; 9.5 planificada.

**Alcance (solo consulta, cuatro juegos).**
- **Predicción guardada** (`/juegos/:codigo/prediccion`). Añade:
  - la explicación guardada o el aviso de que falta o de que su almacén no la verifica;
  - método y versión registrada;
  - los cortes en filas separadas: entrada de la cartera, vector fuente y variables, y entrenamiento del estimador (solo existe aparte en las versiones registradas);
  - las variables de los candidatos extremos y las importancias o coeficientes globales, cuando el estimador persistido los tiene;
  - la clasificación de candidatos con su referencia uniforme: emitida, uniforme, diferencia y razón, con los formatos de la consola.

  La superbalota va en una sección aparte. En ColorLoto se clasifican pares número-color, con su color en texto y su multiplicidad esperada en 6 balotas, y además números y colores por separado. Se conservan el historial y la selección por `?cartera=`.
- **Fiabilidad para la cartera seleccionada**, en la misma pantalla: el botón accesible «Consultar fiabilidad» pide `GET …/fiabilidad?hasta=<corte de la cartera mostrada>`. La v2 contrasta el contexto de modelo, línea/perfil y versión registrada de la respuesta con el de la cartera; no basta compartir familia de modelo o corte. Si no acredita correspondencia, muestra de forma explícita que esa fiabilidad no está disponible para la cartera y no presenta filas o receta ajenas. Siempre conserva el enlace «Fiabilidad general de la configuración actual» a la pantalla general. Elegir otra cartera, volver por el historial o recargar conserva su identidad/corte y vuelve al estado manual, sin mostrar respuestas de otra selección. `hasta` solo filtra objetivos hasta ese número: no acredita que un informe o una emisión existiera al generar la cartera.
- **Fiabilidad completa** (`/juegos/:codigo/fiabilidad`, pestaña «Fiabilidad»): con todos los resultados observados o, con `?hasta=`, los de un corte. Presenta por separado:
  - las líneas: el vector fuente de la configuración y, si hay versión registrada, su línea de laboratorio;
  - en cada línea, seguimiento y retrospectiva;
  - la evaluación de la receta en su informe del laboratorio.

  Muestra la muestra (sorteos incluidos, periodo, emisiones, pendientes y sin base), las exclusiones con su motivo y cuatro cifras por sorteo: Δ Log Loss, Δ Brier y aciertos observados − esperados en los extremos. Cada cifra lleva su media, su intervalo bootstrap al 95 % o la falta de intervalo, y la lectura del backend. Incluye los extremos y el método, con sus supuestos, limitaciones y fuentes.

**Lectura.**
- Δ es modelo − uniforme por sorteo. Positivo significa mayor pérdida que la uniforme; negativo, menor pérdida en esa muestra.
- «Estimable» solo indica que hay sorteos suficientes (30) para calcular el intervalo. No significa ventaja acreditada.
- No hay puntuación de confianza ni probabilidad de premio.
- Un resultado ausente en la base se muestra como pendiente. No se deduce que el sorteo no haya ocurrido ni ninguna anterioridad.
- Que la base esté disponible o haya respondido no equivale a datos al día.

Se mantienen `experimental_no_acreditado`, AE-39 **NO-GO** y `AUTORIZA_EVALUACION = False`.

**Contrato.**
- **Ruta nueva:** `GET /api/v1/juegos/{codigo}/fiabilidad`, con `hasta` ≥ 1 opcional; cuesta 3 fichas. Reutiliza `CentroDePredicciones.fiabilidad` (Fase 4) y proyecta `Fiabilidad`:
  - no expone el motivo de la base, que puede contener el mensaje de conexión, ni las líneas disponibles, ni el parámetro `linea` de la consola;
  - la semilla del bootstrap, de hasta 60 bits, va como texto decimal para que JavaScript no la redondee;
  - un `fallo_de_calculo` lleva un texto fijo en lugar del detalle interno.
- **`GET …/predicciones`** añade, de forma compatible:
  - `linea_de_modelo`;
  - `registrado`, la versión registrada que usó la cartera;
  - `explicacion`, la explicación guardada vigente, sin sello, contexto ni rankings repetidos;
  - `explicaciones_ilegibles`, con la clave y el código fijo del almacén (p. ej. `contenido_alterado`);
  - `reproduccion`: el caso de uso existente recalcula rankings y variables desde la cartera y los compara con los guardados.

  `rankings` mantiene su contenido, pero pasa de objeto genérico a forma tipada. Por eso las filas de los juegos numéricos llevan `multiplicidad_esperada: null` y las secciones que no aplican llegan como `null`.
- **Solo lectura:** ningún GET genera explicaciones, entrena, infiere, importa, recupera trabajos, guarda informes ni escribe. Si falta la explicación, la respuesta lo dice (`explicacion: null`).
- **Pasarela:** 14 plantillas; la nueva solo admite `hasta`. No cambian la autenticación, la clave en el servidor, las cuotas, los errores, el tamaño máximo (4 MiB), la concurrencia ni el plazo total. La respuesta mayor de los datos sintéticos ocupa menos de 30 KB.
- **Frontend:** OpenAPI, `esquema.d.ts` y decodificadores actualizados. La compilación comprueba que los tipos de presentación encajan en el contrato generado.

**Presupuesto de fichas por carga de pantalla.**

| Pantalla | Consultas | Fichas |
|---|---|---|
| Predicción: carga directa o recarga sin memoria | catálogo y predicciones; sin fiabilidad automática | 1 + 3 = 4, máximo autorizado 6 |
| Predicción: navegación posterior con catálogo en memoria | predicciones; sin fiabilidad automática | 3 |
| Predicción: acción explícita «Consultar fiabilidad» | fiabilidad con el filtro de objetivos de la cartera | 3 adicionales, fuera de la carga automática |
| Fiabilidad general: carga directa o recarga sin memoria | catálogo y fiabilidad de la configuración actual | 1 + 3 = 4 |

Todas las peticiones automáticas, incluido `/juegos` cuando la memoria está vacía, entran en el presupuesto. El catálogo solo se conserva en memoria durante esa página. No se precarga fiabilidad, no se añaden reintentos automáticos y las cuotas y costes no cambian. Con saldo de seis fichas, la carga inicial de predicción cabe; una acción explícita posterior de fiabilidad puede recibir 429 si no hay saldo suficiente y conserva el reintento manual con `Retry-After`.

**Datos sintéticos.** `tests/fase9_api_sintetica.py` amplía su escenario:
- Baloto usa una versión registrada sintética: bosque aleatorio, perfil reducido y corte de entrenamiento 2185. Tiene tres carteras con cortes 2190, 2191 y 2192; la última queda pendiente.
- La cartera de Baloto Revancha no tiene explicación guardada.
- La fiabilidad lee Producto 6 con series sintéticas, construidas con sus propias funciones. Cubren:
  - diferencia positiva con el intervalo por encima de 0;
  - retrospectiva con muestra insuficiente;
  - diferencia negativa con el intervalo por debajo de 0;
  - un intervalo que cruza 0;
  - exclusiones;
  - pares de ColorLoto uniformes, con diferencia exactamente 0.

No es PostgreSQL ni usa modelos o almacenes operativos.

**Muestras de las pruebas de componentes.**
- `generar_respuestas_fase9.py` añade 14 respuestas:
  - la fiabilidad de cada juego con y sin corte;
  - la cartera anterior de Baloto con su corte;
  - un 422;
  - la explicación alterada;
  - la base de la Fase 4 caída.
- Se regeneran las cuatro respuestas de predicciones y `formatos.json`, que incorpora las cifras de fiabilidad, las especificaciones de formato y las etiquetas de la consola.
- Las otras 88 no se reemplazan. Regeneradas, solo cambiarían la fecha de consulta, los días de frescura, UUID, horas y latencias, lo mismo que al regenerarlas sobre la base.

**Antecedentes de la v1 en Linux/Cloud, ejecutados por Claude.** Estas cifras y recorridos corresponden a la v1 anterior a F93-REL-01/F93-LIM-01, no a ejecuciones nuevas de la v2. Verificación del 27 de octubre de 2026 con:
- Python 3.14.6, pytest 9.1.1, Node 22.22.0 y npm 10.9.4;
- Chromium 153.0.8010.12, preinstalado en el contenedor, con Playwright 1.56.1. Se usó mediante un adaptador externo, fuera del parche, que solo fija `executablePath`.

No acredita Windows ni Brave.

| Comprobación | Resultado |
|---|---|
| `test_api_publica_fiabilidad.py` (correspondencia con los casos de uso en los cuatro juegos, con y sin corte; corte por cartera; ausencias; explicación alterada; base caída; exclusiones; fallo de cálculo; privacidad; coste; 401, 404, 422 y 429; GET sin escrituras ni trabajadores) | 30 aprobadas |
| `tests/unit/api_publica` y `tests/unit/pasarela` completas | 216 y 197 aprobadas (186 y 192 en la 9.2) |
| Regresiones afectadas: 59 archivos que recorren árboles del repositorio o leen `seleccion_windows.txt` | 1415 aprobadas y 106 omitidas (ensayos de PowerShell de Fase 6 sin `pwsh` en el contenedor), sin fallos |
| Vitest · `tipos:comprobar` · `typecheck` · `build` · `canario` | 665 aprobadas · igual · sin errores · correcto (JS 365,0 kB y CSS 232,9 kB) · 0 hallazgos |
| Recorrido `fiabilidad` (360, 390 y 1280 px) | 30/30 visitas y 32/32 comprobaciones (4 juegos por ancho, cartera y corte, corte en la URL, 422 y teclado); su conteo v1 de 3 + 3 omitía el catálogo y consumía realmente 7 fichas; 6/6 controles directos de la ruta nueva; canario ausente en 286 respuestas |
| Recorrido `normal`, que incluye el anterior | 537/537 visitas y 58/58 comprobaciones; 17/17 controles directos (los 11 de la 9.1 y los 6 de la fiabilidad); canario ausente en 3982 respuestas |
| `cuota_fiabilidad` | 1/1: 429 en la fiabilidad al corte con la predicción visible, sin reintentos automáticos y reintento manual correcto |
| `cuota` · `api_caida` · `sin_clave` · `clave_incorrecta` · `vite` | 1/1 · 3/3 visitas y 1/1 · 3/3 y 1/1 · 3/3 y 1/1 · 12/12 visitas, 1/1 y 3/3 controles directos |

El primer intento del recorrido `fiabilidad` falló antes de abrir el navegador: faltaba el ejecutable que espera Playwright. Tras usar el adaptador, todos los escenarios pasaron a la primera. Registros, JUnit, códigos de salida y capturas están en el ZIP de la entrega.

Las pruebas nuevas de Python están en `tests/unit/api_publica` y `tests/unit/pasarela`, que ya figuran en `tests/seleccion_windows.txt`. Entran en la selección de Windows sin cambiarla: 35 casos. El CI del frontend añade el escenario `cuota_fiabilidad`; `normal` ya incluye el recorrido dirigido.

**Correcciones v2 (F93-REL-01 y F93-LIM-01).** La auditoría independiente de ChatGPT ejecutó sobre v1 otras 413 pruebas de API/pasarela y 665 de frontend, además de contrato, tipos, compilación y canario, en Linux/Python 3.12.14. Reprodujo las dos incidencias con sondas adicionales. Son antecedentes separados: no se suman a las cifras anteriores ni se presentan como validación nativa. La v2 conserva sus propios registros dirigidos y controles negativos/positivos en el ZIP de entrega. No se repiten por rutina los recorridos completos o las baterías grandes.

**Validación nativa v2 de Daniel, 27 de octubre de 2026 (11:18:23–11:29:15, America/Bogota), aprobada por el auditor.** Windows 11/Python 3.14.6: 415 pruebas API/pasarela; Node 24.15.0: 690 Vitest, sin fallos, errores u omisiones. Las 25 regresiones de contexto ya están incluidas en los 690. OpenAPI, tipos, TypeScript, compilación y canario correctos; pip check limpio y dos deprecaciones Python conocidas. Brave instalado, con perfil temporal y adaptador externo: 30 visitas y 32 comprobaciones correctas a 360, 390 y 1280 px, más seis controles HTTP; cuota: dos comprobaciones y cero visitas en el contador genérico, aunque sí hubo navegación. El auditor revisó 16 capturas sin bloqueos; el resultado original decía pendiente porque se generó antes de la auditoría y se conserva intacto. No es certificación general de accesibilidad. Fuente v2 de 975 archivos y seis controles públicos de worktrees conservados; contención 2/2 con código 124 esperado; no se ejecutó la selección completa de Windows. No hubo consultas o ciclos operativos. Son resultados nativos de Daniel, separados de Linux y de la observación real de Fase 6. [Insumos y límites](fase9_3_validacion_operador_2026-10-27.md).

**Linux v2 (Codex Cloud, antecedente de implementación; no se repite en el cierre):** 37 pruebas Python, 36 frontend y tres genéricas, con otras 34 deseleccionadas por filtro; las 25 nuevas están incluidas en las 36. Sondas de pantalla 3/3 y cuatro fichas automáticas; diagnóstico API 3/4 esperado, por su semántica de configuración actual. Contrato/tipos/build/canario y dos recorridos focales Chromium/Linux a 1280 px acreditados. No se suman estos grupos con Windows o v1.


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

## Entrega 9.4: modelos, carteras y resultados guardados

**Base:** `4f4dd639581168b08c95816660f80fc4f735b1ac`, merge del PR #102; árbol de 976 archivos `3aa63d583a9c4df7a139b7eafe5a161fadcbe441`. El código y cierre de la 9.3 están integrados. Sus cinco checks de Actions (Node 22/24, Chromium/Linux, Python/Linux y Python/Windows; workflows `40589232731` y `40589232763`) son antecedentes de la base. No se ejecutan Actions ni se modifica facturación en esta entrega.

**Estado de 9.4 v2:** validada en Linux y Windows nativo con Brave y aprobada por auditoría. Publicación manual, integración y CI pendientes. [Evidencia y límites](fase9_4_validacion_operador_2026-10-28.md); los cinco checks del PR #102 siguen atribuidos exclusivamente a 9.3/base.

**Alcance implementado.** Para BALOTO, BALOTO_REVANCHA, MILOTO y COLORLOTO:

| Consulta pública y pantalla | Lector/HTMX existente | Contrato y coste |
|---|---|---|
| `…/modelos-guardados` y `…/modelos-guardados/{clave}` | `LaboratorioFileStore.modelos/obtener_modelo`, `modelos_registrados.resumen/compatibilidad`; `laboratorio/modelos.html` y `modelo.html` | Listado paginado y ficha de versiones realmente registradas, separados del catálogo de candidatos. Identidad, familia, perfil, versión, cortes y metadatos disponibles. 2 fichas; 3 con catálogo frío |
| `…/carteras-guardadas` y `…/carteras-guardadas/{clave}` | `CarterasDeModelos.lineas/carteras_de_linea/cartera`; `carteras/juego.html` y `cartera.html` | Carteras Producto 5, distintas de la predicción de 9.3: combinaciones, objetivo/corte, método/modelo/versiones y reproducción guardada. 2 fichas; 3 con catálogo frío |
| `…/resultados` | `CentroDeResultados.consultar`, `Filtros`; `resultados/juego.html` y sus parciales de resumen/comparación/carteras | Emisiones y observados, líneas/procedencias, muestra, exclusiones y referencia uniforme, con filtros y paginación actuales. 5 fichas; 6 con catálogo frío |

No se deserializa ni ejecuta el estimador al leer metadatos; el lector valida el manifiesto canónico, su reserva y las huellas/tamaños. Ausencia, alteración e incompatibilidad se informan y no se reparan. Los detalles verifican el juego y la identidad del artefacto; no atribuyen otra versión, la configuración actual ni una receta ajena a una cartera histórica. No se guardan informes ni marcas. Las agregaciones de Producto 6 vienen del caso de uso existente, no de un nuevo motor en la API o React. Un resultado pendiente conserva valores no observados, nunca cero aciertos inventados. Superbalota y pares número-color mantienen su representación.

**F94-ROB-01 cerrado en v2.** La proyección contiene los metadatos necesarios incompletos por artefacto: el listado conserva la cartera como alterada y las sanas siguen disponibles; la ficha afectada devuelve 409. El nombre opcional ausente se publica como `null`, sin completar con la configuración actual. La sonda original, sin modificar, pasó de 1/3 (código 1) sobre v1 a 3/3 (código 0) sobre v2.

**Filtros y contexto.** Modelos admite `pagina`, `por_pagina`, `modelo` y `perfil`; carteras, `pagina`, `por_pagina`, `linea`, `desde` y `hasta`; resultados, `procedencia`, `linea`, `tipo`, `desde`, `hasta`, `objetivo`, `pagina` y `por_pagina`. `desde`/`hasta` se refieren a números objetivo, no a fecha de disponibilidad de la emisión. La URL conserva filtros, navegación directa, recarga y atrás/adelante. Un cambio de juego/filtro/selección invalida la respuesta anterior; las tardías incompatibles no se muestran. Los detalles se consultan mediante acción explícita, sin precarga de paneles secundarios.

**Presupuesto y conservación.** Toda carga automática nueva incluye el catálogo en su coste: modelos/carteras 1 + 2 = 3; resultados 1 + 5 = 6. No se reducen costes ni aumentan cuotas. Se conservan la carga de predicción de 9.3 (1 + 3 = 4), la fiabilidad por acción explícita y su acreditación de contexto, 429/`Retry-After` sin reintentos automáticos, autenticación, clave en servidor, proyección pública, errores saneados, `no-store`, `X-Request-ID`, límites, concurrencia y plazo total.

**Validación y atribución.** Daniel completó la validación nativa de v2 el 28 de octubre de 2026 en Windows 11/Python 3.14.6. Las 173 pruebas API/pasarela y la sonda 3/3 proceden de la primera corrida `d5a768db` y se retuvieron sin repetir; contención 2/2, con código 124 esperado en el ensayo de plazo. La continuación `1463b159` ejecutó 780 Vitest nuevos en Windows y completó tipos, TypeScript, compilación y canario. Node 24.15.0, npm 11.12.1, Brave instalado (motor 156.0.8078.48) y Playwright 1.56.1. Los resultados llevan la etiqueta genérica Chromium; la identidad del ejecutable externo acredita Brave. Los registros Linux del implementador y del auditor conservan su atribución, incluidos los frontend/recorridos v1 retenidos durante el ajuste Linux v2; no se suman grupos solapados.

Los cinco escenarios Brave suman 87 visitas, 15 comprobaciones de navegador, ocho controles HTTP y 88 capturas a 360, 390 y 1280 px. Cuota registra cero visitas en su contador genérico aunque sí hubo navegación, y una comprobación: 429/`Retry-After`, sin reintento automático y recuperación por acción explícita. La auditoría visual posterior aprobó las 88 capturas sin bloqueos; el campo pendiente de la salida original se conserva como histórico. No es una certificación general de accesibilidad. [Cadena nativa, tabla por escenario y procedencia](fase9_4_validacion_operador_2026-10-28.md).

**Salvedad documental de OpenAPI aceptada.** El generado en Windows usa `Unprocessable Content` donde el versionado dice `Unprocessable Entity`, exclusivamente en las cinco descripciones de respuesta 422 de los endpoints nuevos. El resto del JSON completo coincide. El comparador externo conserva ambos documentos y su diferencia, acepta sólo ese conjunto auditado y rechaza cualquier cambio adicional; declara `documentos_json_iguales=false` y `cinco_descripciones_422_auditadas_aceptadas=true`. No se modificaron el producto, OpenAPI versionado, tipos o contrato funcional. Es una salvedad de validación del producto v2, sin entrega v3.

**Límites conservados.** Datos sintéticos, SQLite y almacenes aislados; API y pasarela reales y SPA compilada, con presupuestos fríos 3/6, canario ausente, mapas de huellas e índices/controles públicos conservados. Los ajustes reducidos preparan versiones sintéticas antes de los GET, durante los cuales se bloquean escritura, entrenamiento, carga/inferencia y trabajadores; no son una batería ML. Las carpetas API/pasarela siguen incluidas en `tests/seleccion_windows.txt`, pero no se ejecutaron la selección completa Windows, suite completa, mediciones, PostgreSQL, otra batería ML ni operación u observación de Fase 6. Este cierre sólo verifica documentos. La Fase 9 global continúa abierta; publicación manual, integración y CI de 9.4 permanecen pendientes.

La operación de Fase 6 y sus documentos históricos se conservan: tarea versión 2, novedades automáticas observadas en los cuatro juegos y límite explícito de la recuperación matinal con pendientes. El inicio registrado 09:24:45 no acredita un disparo a las 09:00. No se consulta SQL operativo ni se ejecutan ciclos. Continúan `experimental_no_acreditado`, AE-39 **NO-GO** y `AUTORIZA_EVALUACION = False`. La 9.5, despliegue y aplicación personal no forman parte de esta entrega.

## Matriz de huecos de la Fase 9

| Función de la consola HTMX | 9.1–9.4 | Plan acordado o fuera del alcance actual |
|---|---|---|
| Juegos y reglas | Cubierto | — |
| Resumen con frescura y corte | Cubierto | Gráficas de barras |
| Sorteos: filtros, paginación y detalle | Cubierto | — |
| Panel de Fase 5 y métricas con página (18/18/11/5) | Cubierto | Gráficas nuevas |
| Páginas de las métricas anteriores: 12 en Baloto y en Revancha, 11 en MiLoto y 31 en ColorLoto. *Corrección:* la 9.1 decía «30 en Baloto», que es el total con las de Fase 5 | Cubierto en la entrega 9.2, validada en Windows con Brave, auditada e integrada en el PR #101 | Gráficas de la consola (se sustituyen por tablas) |
| Predicción guardada | Cubierto (historial, modelo, clasificación temporal, integridad, combinaciones, observado, frente a la base). La 9.3 añade explicación guardada, método y versión registrada, cortes de entrada y de entrenamiento, variables e importancias, y la clasificación de candidatos con la referencia uniforme: validada en Linux y Windows/Brave, auditada e integrada en PR #102 | Gráficas de la consola (se sustituyen por tablas); generar o explicar una predicción (escritura) |
| Fiabilidad de las predicciones | 9.3 v2: consulta explícita para la cartera solo si corresponde su contexto; ausencia explícita en otro caso y acceso a la fiabilidad general de la configuración actual. Seguimiento, retrospectiva y receta por separado; `hasta` filtra objetivos. Validada, auditada e integrada en PR #102 | Resultados de Producto 6 con línea explícita cubiertos por 9.4; gráficas nuevas para después |
| Simulaciones guardadas | Cubierto | Lanzar simulaciones (escritura) |
| Salud y estado de la API | Cubierto | — |
| Modelos y laboratorio (Fase 3) | 9.4: listado y ficha de versiones realmente registradas; estados íntegro/ausente/alterado/incompatible, sin deserializar para ejecutar. V2 validada en Linux y Windows/Brave y aprobada por auditoría; publicación manual, integración y CI pendientes | Entrenar, comparar, registrar o reparar (escritura) |
| Carteras (Producto 5) y resultados avanzados (Producto 6) | 9.4: listado/detalle de carteras y emisiones/resultados, filtros/paginación y agregados existentes. V2 validada en Linux y Windows/Brave y aprobada por auditoría; publicación manual, integración y CI pendientes | Generar carteras, verificar/persistir seguimiento o informes (escritura) |
| Exportaciones e impresión | — | 9.5: exportación, impresión y revisión final de navegación, móvil y accesibilidad; no implementadas aquí |
| Importación, generación, configuración y automatización | — | Acciones administrativas; requieren autenticación de escritura (Fase 10) |
| Operación automática y panel diario | — | Sin consulta en la API v1; siguen en la consola local |

**Plan acordado de cinco partes.** 9.1, 9.2 y 9.3 están integradas en los PR #100, #101 y #102. La 9.4 implementa consultas de modelos registrados, carteras de Producto 5 y resultados de Producto 6, solo de lectura, sobre el merge exacto del PR #102. La v2 está validada en Linux y Windows nativo con Brave y aprobada por auditoría; publicación manual, integración y CI permanecen pendientes. La 9.5 conserva exportación, impresión y revisión final de navegación, móvil y accesibilidad, sin implementarse aquí. Administración y operación permanecen en HTMX; los gráficos nuevos quedan para después. La Fase 9 global continúa abierta.

## Limitaciones conocidas

- La cuota y el monitoreo de la API son por proceso (Fase 8); la pasarela no añade una cuota propia.
- La pasarela solo admite destinos y clientes loopback: no es un proxy para red ni despliegue.
- Los colores de ColorLoto fuera de la paleta conocida se muestran con su nombre y sin muestra de color.
- **Fuera del alcance de la 9.2:** el orquestador del recorrido (`tests/recorrido_fase9.py`) no propaga `NO_COLOR` a Vite. En Windows, los códigos ANSI pueden impedir que reconozca la dirección de arranque. La validación de la 9.1 lo sorteó con el supervisor externo `color-vite-r1`. El defecto sigue sin corregir en el orquestador versionado y se trata aparte.
- Con formato `texto`/`tipo_p`, un número puede verse distinto que en la consola HTMX (JSON no conserva `100.0` ni la notación exponencial de Python).
