# Fase 10 · E10.1 — Seguridad de la consola local

Estado (2 de noviembre de 2026): **v3** (v2 + ajuste de prueba E101-TEST-01). **Validación automática nativa
consolidada y recorrido guiado Brave auditados por Codex dentro de su alcance; publicación manual, integración y
CI pendientes.** E10.1 no está publicada ni integrada; la Fase 10 global sigue abierta y E10.2 no ha comenzado.
Resultados, atribución y salvedades: [validación del operador y auditoría](fase10_e101_validacion_operador_2026-11-02.md) (§10). La v2 corrige los
cinco hallazgos de la auditoría independiente de v1 (E101-SEC-01, E101-SEC-02, E101-ROB-01, E101-OBS-01,
E101-VAL-01; §9). Protocolo de referencia en `fase10_e101_windows_brave.md`. Alcance confirmado: consulta remota privada por VPN para Daniel e
invitados (solo consulta, por la API pública y la SPA, fuera de este paso); administración y ejecución
exclusivamente en el PC de Daniel; cuentas y sesiones de la consola en un almacén privado independiente;
identidades de consulta remota y de administración local separadas. F10-DAT-02 sigue abierto para E10.4. No se
implementa captura, copias de seguridad, VPN, infraestructura ni despliegue.

## 1. Arquitectura

La consola (`app.main:app`, HTMX y REST interno `/api/...`) queda protegida en dos capas, ambas activas por
defecto en cualquier `ENVIRONMENT` (también `development`):

1. **Límite local** (`LimiteLocal`, middleware ASGI exterior). Antes de cualquier ruta o archivo estático:
   - rechaza (403) toda solicitud con cabeceras de reenvío (`Forwarded`, `X-Forwarded-*`, `X-Real-IP`,
     `X-Client-IP`): la consola no está detrás de ningún proxy y no confía en ellas;
   - rechaza (403) toda conexión cuyo extremo real no sea loopback (`127.0.0.1`, `::1`): una conexión por VPN
     o LAN se rechaza **aunque traiga una sesión válida**;
   - exige exactamente una cabecera `Host` local (`localhost`, `127.0.0.1`, `[::1]`) contra *DNS rebinding*;
   - cierra los websockets; después de la respuesta registra la auditoría de las escrituras autorizadas.
2. **Autorización** (`autorizar_consola`, dependencia global de la app, que FastAPI ejecuta antes que las de la
   ruta). Con la plantilla efectiva de la ruta (`scope["route"].path`) y su método:
   1. busca la política en el registro; **sin política, 403 `sin_politica`, incluso para un administrador**;
   2. comprueba el almacén; si falta, no tiene cuentas, tiene permisos abiertos o está dañado: **503** con
      guía de aprovisionamiento, sin trazas ni rutas internas;
   3. métodos no seguros: `Origin`/`Referer` propios y `Sec-Fetch-Site` `same-origin`/`none`;
   4. CSRF: cabecera `X-CSRF-Token` o campo `csrf_token` (nunca de la URL); en `POST /acceso`, el de la
      presesión;
   5. sesión válida (si no: 303 a `/acceso?siguiente=…` en GET, 401 con `HX-Redirect` en HTMX, 401 JSON en
      `/api/`);
   6. rol mínimo; en las rutas por acción, el rol del valor concreto; **valor desconocido: 422 sin despacho**.

Ninguna dependencia de la ruta (servicios, lanzadores, sesión de base de datos) se construye si la
autorización rechaza: se comprueba con servicios sustituidos en `test_autorizacion_acciones.py`.

La API pública (`app.api.publica`) y la pasarela/SPA no montan nada de esto (comprobado en
`test_cobertura_politicas.py`); `/api/v1`, su OpenAPI y sus tipos no cambian.

## 2. Inventario y políticas

- 223 rutas `APIRoute` en la base (GET 184, POST 34, DELETE 4, PUT 1), más las 4 de documentación de FastAPI
  (ahora desactivadas) y el montaje `/static`. Se añaden `GET/POST /acceso` y `POST /salir`: **226 entradas**.
- Registro explícito en `app/seguridad_consola/politicas.py`; matriz completa en `matriz-politicas.md` (entrega).
- Escrituras: 39 de negocio (26 ya tenían `proteccion_local` + `TOKEN_LOCAL`; 13 no tenían ninguna guarda y
  quedan cubiertas: alta/edición/borrado de sorteos, colores web y REST, y las cuatro importaciones) + 2 de
  autenticación.
- GET: todos `lector`. Clasificados por semántica: `lectura`, `lectura_con_cache` (solo el router web de
  `/estadisticas/...`, que calcula y guarda caché derivada idempotente) y `exportacion`.
- Roles: `lector` < `operador` < `administrador`.
  - operador: ejecuciones, generación y verificación (pronósticos, laboratorio, carteras, predicciones,
    resultados, simulaciones, `operacion/ejecutar` con `modo=local`, `automatizacion/comprobar`).
  - administrador: histórico (sorteos, colores), importaciones, configuración (`carteras/{slug}/configurar`,
    `resultados/{slug}/configuracion`), `operacion/ejecutar` con `modo=actualizar` (consulta las fuentes e
    importa) y `automatizacion/{pausar,reanudar,recuperar}`.
- `/automatizacion/{accion}`: `comprobar`→operador; `pausar`, `reanudar`, `recuperar`→administrador; cualquier
  otro valor (incluidas variantes de mayúsculas o espacios) → 422 sin construir el servicio ni el lanzador.
- Excepciones mínimas: `GET /acceso`, `POST /acceso` (presesión + CSRF + límite de intentos) y `POST /salir`
  (sesión + CSRF). Archivos estáticos (`/static`), sin política de rol pero tras el límite local. Ningún prefijo
  queda exento.
- Daniel tiene la cuenta administradora; los invitados remotos no tienen cuenta de consola.

## 3. Almacén privado

- SQLite propio (`backend/privado/consola/seguridad.sqlite3` por defecto, `CONSOLA_SEGURIDAD_DIRECTORIO`; una
  ruta relativa se interpreta desde `backend/`). `backend/privado/` está en `.gitignore` **desde este cambio,
  antes de que exista ningún dato**; la CLI además se niega a crear el almacén dentro de un repositorio Git
  que no lo ignore (`git check-ignore`).
- Nada se crea al importar ni al arrancar: se abre con `mode=rw`; solo `consola_cuentas crear` lo crea.
- Permisos (v2, `app/seguridad_consola/permisos.py`): se verifican el archivo y su directorio **al crear y en
  cada apertura**; si no se pueden leer o interpretar, el acceso se cierra (503 `permisos_no_verificables`).
  POSIX: dueño = usuario efectivo, `mode & 0o077 == 0`, sin enlaces simbólicos. Windows: descriptor leído con
  `GetNamedSecurityInfoW` (ctypes, sin dependencias ni análisis de texto de `icacls`); propietario = usuario
  del proceso; DACL presente; concesiones solo al usuario y a `LocalSystem` (S-1-5-18, que ya tiene acceso
  total al sistema de archivos local); ninguna para Administradores, Usuarios, Todos, Usuarios autenticados,
  CREATOR OWNER u otro SID, tampoco heredada o solo de herencia; las denegaciones se admiten; otros tipos de ACE
  cierran. Al crear se fija propietario y DACL protegida (una concesión al usuario) solo en el directorio y el
  archivo que crea el propio proceso; un directorio preexistente **no se modifica**: si no cumple, se rechaza.
- Atomicidad entre CLI y servidor: transacciones `BEGIN IMMEDIATE` con `busy_timeout` (bloqueo de archivo de
  SQLite, válido entre procesos); prueba multiproceso incluida.
- No se migra la base operativa (PostgreSQL de Fase 6), ni se tocan sus tablas, horarios o la tarea
  `LP6-01023009031fcabd`.
- Tablas (esquema 2): `meta`, `cuentas`, `sesiones`, `presesiones`, `intentos`, `auditoria` y `admisiones`
  (v2). Un almacén de esquema 1 (v1) queda cerrado (503 `esquema`): no hay almacenes reales de v1; se crea uno
  nuevo con la CLI. Crecimiento acotado: presesiones ≤ 200, sesiones ≤ 5 por cuenta, intentos ≤ 5000,
  admisiones ≤ 2 vigentes, auditoría ≤ 20000 filas (v2: poda en la misma transacción de cada evento, por las
  dos vías de `auditar`), y purga de caducadas.

## 4. Contraseñas

- scrypt (RFC 7914) de la biblioteca estándar (`hashlib.scrypt`, OpenSSL), N=2^17, r=8, p=1 (128 MiB), sal de
  16 bytes, clave de 32 bytes; formato `scrypt$1$N$r$p$sal$clave`; comparación en tiempo constante; un hash con
  parámetros por debajo de los mínimos no verifica. Sin dependencias nuevas ni criptografía propia.
- Justificación: OWASP *Password Storage Cheat Sheet* recomienda Argon2id y, si no está disponible, scrypt con
  coste mínimo N=2^17, r=8, p=1; la documentación de Python documenta `hashlib.scrypt` (OpenSSL ≥ 1.1). Desde este
  entorno no se pudieron consultar (red restringida); la auditoría independiente de v1 sí consultó ambas
  fuentes y confirma que N=2^17, r=8, p=1 coincide con una configuración publicada por OWASP. Argon2id exigiría una
  dependencia nueva (`argon2-cffi`) sin ganancia necesaria para una consola de un solo equipo.
- Política: 12–1024 caracteres, no solo espacios, sin caracteres de control. Se leen sin eco (`getpass`, dos
  veces) o de la entrada estándar (`--contrasena-stdin`); nunca en argumentos, URL ni registros.

## 5. Sesiones y CSRF

- Identificador de 256 bits (`secrets.token_urlsafe(32)`); en el almacén solo su SHA-256.
- Cookie `lp_consola_sesion`: `HttpOnly`, `SameSite=Strict`, `Path=/`. `Secure` y prefijo `__Host-` solo con
  `CONSOLA_COOKIE_SEGURA=true` (HTTPS real); en `http://localhost` no se aplican.
- Renovación al iniciar sesión (identificador nuevo; la presesión se consume y no se reutiliza), 30 min de inactividad y 12 h absolutas; el toque de
  actividad se escribe como mucho cada 60 s. Sobrevive a reinicios (está en el almacén). El sondeo HTMX del
  panel cuenta como actividad: una pestaña abierta en el panel mantiene viva la sesión hasta el límite de 12 h.
- Revocación efectiva: cerrar sesión, cambiar contraseña, cambiar rol o desactivar la cuenta borran sus
  sesiones; además cada solicitud re-evalúa el rol vivo y la versión de la cuenta.
- CSRF sincronizado sin almacenar: `HMAC-SHA256(id de sesión, "csrf:sesion")`; en el acceso,
  `HMAC-SHA256(id de presesión, "csrf:acceso")` con presesión de un solo uso y 10 min. La página lo lleva en
  `<meta name="csrf-token">`; `static/js/consola_csrf.js` lo añade como cabecera `X-CSRF-Token` a las
  solicitudes HTMX no GET (`htmx:configRequest`) y como campo oculto `csrf_token` a los formularios POST
  nativos (el `<body>` de las plantillas no cambia). Un token de otra sesión, ausente, erróneo o en la URL no
  vale.
- **Coexistencia con `TOKEN_LOCAL`**: no se elimina. Las 26 rutas que lo exigían lo siguen exigiendo (defensa
  preexistente, independiente de la sesión); el CSRF de sesión se añade delante para todas las escrituras,
  incluidas las 13 sin guarda. Un formulario necesita ambos; HTMX/JSON necesita el de sesión.
- Intentos: por usuario normalizado (no por cliente: todos los clientes son loopback); espera progresiva
  1, 2, 4, 8 s… (máx. 30) y bloqueo de 15 min tras 5 fallos en 15 min; la respuesta es la misma exista o no la
  cuenta (y se calcula un hash ficticio para igualar tiempos).
- Admisión (v2, E101-SEC-02): en una sola transacción `BEGIN IMMEDIATE` —que serializa solicitudes, hilos y
  procesos— se consume la presesión (borrado condicionado: solo una solicitud la obtiene), se comprueban
  espera y bloqueo y se reserva la verificación: como mucho **una en curso por usuario** y **dos en total**. Sin
  reserva no se calcula ningún hash (respuesta 429). La verificación scrypt se hace fuera de la transacción; su
  resolución (fallo o sesión) libera la reserva en otra transacción, también si la verificación lanza una
  excepción; si el proceso muere, la reserva caduca a los 30 s. Si la cuenta cambia durante la verificación,
  no se crea sesión.
- Entradas HTTP (v2, E101-ROB-01): `Host` con gramática cerrada (`localhost`, `127.0.0.1` o `[::1]`, puerto
  opcional 1–65535), sin `urlsplit`; cookie de presesión validada en forma y tamaño antes de derivar el CSRF;
  `Referer` no interpretable → origen no acreditado. Respuestas 403/400, nunca 500, sin captura global.
- Un solo *worker*: la caducidad de la sesión no cancela trabajos ya autorizados (lanzados en segundo plano).
- Documentación de la consola (`/docs`, `/redoc`, `/openapi.json`) desactivada siempre.

## 6. Auditoría

Accesos, salidas, fallos, bloqueos, rechazos (CSRF, permiso, acción no reconocida) y escrituras autorizadas
(usuario, acción, plantilla de ruta y valor de acción, hora UTC, resultado HTTP). Nunca contraseñas, cookies,
identificadores de sesión, tokens CSRF, claves ni secretos. Entradas saneadas (caracteres de control y
longitud) contra inyección en registros; la interfaz escapa con Jinja. Consulta: `consola_cuentas auditoria`.
Retención (v2, E101-OBS-01): cada inserción, dentro de su transacción (atómica con la operación auditada),
elimina las filas que exceden `MAX_AUDITORIA`. Se mide en filas; no promete reducir de inmediato el tamaño
físico del archivo SQLite.

## 7. Aprovisionamiento y recuperación (solo en el PC de Daniel)

Desde `backend/`, con el entorno virtual activo:

```
python -m scripts.consola_cuentas crear --usuario daniel --rol administrador
python -m scripts.consola_cuentas comprobar
uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Otras órdenes: `cambiar-contrasena --usuario U`, `cambiar-rol --usuario U --rol R` (no deja el sistema sin
administrador activo), `desactivar`/`activar --usuario U`, `revocar-sesiones [--usuario U]`, `listar`,
`auditoria --limite N`. Códigos de salida: 0 correcto, 1 rechazado, 2 uso incorrecto.

Recuperación (contraseña olvidada, cuenta bloqueada o sesión sospechosa): solo con la CLI local —
`cambiar-contrasena` (revoca sus sesiones; el bloqueo de intentos caduca en 15 min) o `revocar-sesiones`. Si el
almacén se daña, la consola responde 503 (`corrupta`): renombrar el archivo (no borrarlo, para análisis) y
volver a `crear`. No hay recuperación por la web.

Arranque soportado: solo `--host 127.0.0.1`, `--no-proxy-headers`, un *worker* (`run.sh` lo usa). La consola no
debe publicarse por la VPN ni detrás de un proxy: la consulta remota de invitados es la API pública/SPA.

## 8. Validación

- Linux: pruebas nuevas en `tests/unit/seguridad_consola` (añadidas a `tests/seleccion_windows.txt`) y suite
  completa del backend (resultados y JUnit en la entrega).
- Pruebas preexistentes: sus fixtures obtienen una sesión legítima por el flujo real con el ayudante explícito
  `tests/consola_sesion.py` (`cliente_de_consola`); se conservan sus aserciones; no hay desactivación global ni
  fixture *autouse* que anule la seguridad. El cliente por defecto de `fixtures_producto1` pasa de
  `testclient` a `127.0.0.1` (la consola ya no atiende a clientes no locales ni en GET).
- v2: regresiones nuevas en `tests/unit/seguridad_consola/test_regresiones_v2.py` (incluida concurrencia entre
  procesos) y `test_permisos_windows_nativo.py` (solo Windows; en Linux se omite). La sonda independiente de
  la auditoría se ejecuta sin modificar en modo `antes` (v1) y `despues` (v2).
- v3 (E101-TEST-01): solo la preparación de `test_almacen_corrupto_o_ajeno_esta_cerrado` (crea el archivo de
  esquema ajeno con permisos admitidos antes de alterar `meta`); producto idéntico a v2.
- Validación nativa Windows 11 / PowerShell 5.1 / Brave: realizada y auditada por Codex dentro de su alcance; ver
  §10 y el [informe](fase10_e101_validacion_operador_2026-11-02.md).

## 9. Correcciones de la v2 (auditoría independiente de v1)

| Hallazgo | Corrección | Regresiones |
|---|---|---|
| E101-SEC-01 · permisos Windows | `permisos.py`: verificación de propietario y DACL de archivo y directorio al crear y abrir; fallo cerrado si no es verificable; directorio preexistente sin modificar | contrato con descriptores sintéticos, Windows simulado (apertura, cambio posterior, lectura fallida, preexistente, aplicación incompleta), POSIX real, ensayo nativo |
| E101-SEC-02 · admisión y presesión | consumo condicionado de presesión y reserva de verificación en una transacción, límites por usuario y global, liberación y caducidad | hilos y procesos (`spawn`) sobre el flujo real, límite global, excepción, reserva huérfana, cambio de cuenta, HTTP |
| E101-ROB-01 · entradas HTTP | gramática de `Host`, validación de presesión antes del CSRF, `Referer` no interpretable | variantes malformadas y legítimas de Host, cookies de presesión y sesión, Referer |
| E101-OBS-01 · retención | poda en la misma transacción por ambas vías de `auditar` | accesos, salidas y operaciones de cuentas reales; atomicidad |
| E101-VAL-01 · procedimiento | protocolo v2: entrada oculta (`tests/ensayo_e101_buscar_secreto.py`), solo booleanos, prólogo autocontenido, perfiles de Brave por rol, códigos de salida | ayudante de búsqueda y revisión automática del procedimiento |

Fuentes (citadas por la auditoría y no reconsultadas desde este entorno, cuya red las bloquea): OWASP *Password
Storage Cheat Sheet*, documentación de `hashlib` de Python 3.14 y la de `icacls` de Microsoft (`/grant:r`
reemplaza los permisos explícitos del SID indicado; no elimina los de otros SID, por eso v2 fija la DACL
completa con `SetNamedSecurityInfoW` y la comprueba después).

## 10. Validación nativa y estado (2 de noviembre de 2026)

Detalle, entornos, huellas y salvedades: [validación del operador y auditoría](fase10_e101_validacion_operador_2026-11-02.md). Resumen, sin sumar
corridas ni plataformas:

- **Windows automático (consolidado):** 264 casos únicos, 261 aprobados (260 retenidos de la corrida sobre v2 + 1
  del caso corregido en v3), 3 omitidos POSIX, 0 fallos y 0 errores; las 3 pruebas nativas de ACL están dentro de
  las 260. Sonda original nativa 5/5 (plataforma `win32`). No es una batería completa nueva.
- **Brave r3 (nativo):** 14 pasos guiados coincidentes y 45 + 6 eventos de dos procesos; roles, rechazos por
  permiso (con CSRF válido) y por CSRF ausente, alta y retiro HTMX del color ficticio, salida (9 condiciones,
  sesiones 1→0), revocación, cambio de rol y persistencia tras reinicio. Revisión visual de 12 capturas por Codex.
- **No acreditado:** HTTPS, VPN real, acceso desde otro dispositivo, inspección manual de todas las rutas ni
  búsqueda manual de contraseñas en Windows. Los servicios de negocio del ensayo eran ficticios.
- **Pendiente:** publicación manual, integración y CI. D2/D3/D4/D12 sin cambios; F10-DAT-02 abierto para E10.4.
