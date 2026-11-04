# Fase 10 — E10.2: consulta privada (API y pasarela para invitados de solo lectura)

Estado (2026-11-04): **integrado en `main`** con el PR #109 (merge `4aa24b85`). Los 11 checks del head
`f219e499` terminaron correctamente (Python `41758396786`, frontend `41758396837` y seguridad `41758396770`).
Grype real sobre ambas imágenes: **8 avisos High por imagen aceptados temporalmente** (caducan el 2026-11-17,
sin renovación automática) y **0 graves abiertos**; no son avisos corregidos. E10.4 añade el **perfil ligado a
una generación** (`GENERACION_DIRECTORIO`, ver [generaciones](fase10_generaciones.md)). Pendientes: activación
con drenaje (E10.5, D11) y producción. La Fase 10 **no** está cerrada.

Estado anterior (2026-11-03, histórico): implementado y demostrado en Linux aislado; validación nativa de
Windows y ensayo focal de Brave v4 completados y auditados; publicación, CI remoto, Grype e importador pendientes. Se conservan D2/D3/D4/D12, F10-DAT-02 para E10.4, `experimental_no_acreditado`, AE-39 NO-GO y
`AUTORIZA_EVALUACION = False`. E10.1 está integrado (PR #108).

Imágenes, lock y CI de seguridad (E10.3): [fase10_imagenes_y_ci.md](fase10_imagenes_y_ci.md).

## 1. Topología y frontera de confianza

```
invitado (VPN, D2) --TLS + certificado de cliente--> proxy --red interna--> pasarela + SPA --red de servicio--> API pública --red de datos--> PostgreSQL (rol lector)
                                                                                                                      \--> generación publicada (solo lectura)
```

| Tramo | Quién se autentica | Cómo | Qué NO se cree |
|---|---|---|---|
| Invitado → proxy | La **persona** | Certificado de cliente X.509 emitido por la **CA de consulta** (`ssl_verify_client on`, CRL); identidad = CN exacto (`CN=<identidad>`, sin otros atributos) | La IP de la VPN, cabeceras del navegador |
| Proxy → pasarela | El **proxy** | IP exacta del socket (`PASARELA_PROXIES_FIABLES`) **y** secreto compartido `X-Consulta-Ingreso` comparado en tiempo constante | `X-Forwarded-For`, `Forwarded`, `X-Real-IP`, una IP privada cualquiera |
| Pasarela → API | La **pasarela** | IP exacta del socket (`API_PUBLICA_CLIENTES`), `Host` exacto (`API_PUBLICA_HOSTS`) y clave de API (huella SHA-256) | Cualquier otro cliente, aunque tenga una clave válida |
| API → PostgreSQL | La **API** | Rol `consulta_lector` (solo `SELECT`, transacciones de solo lectura por defecto, límites propios) | Escrituras |

- **Solo el proxy autenticado afirma una identidad.** El proxy *reemplaza* `X-Consulta-Identidad` y
  `X-Consulta-Ingreso` (nginx no reenvía la cabecera del cliente con el mismo nombre que `proxy_set_header`) y
  vacía `X-Forwarded-For`, `Forwarded`, `X-Real-IP`, `X-Forwarded-Host/Proto`. La pasarela rechaza (403) toda
  solicitud que no llegue del socket del proxy con el secreto, con una identidad ausente, repetida o con otro
  formato; también la SPA y `/pasarela/configuracion`.
- **Identidad y cuentas de la consola son mecanismos separados** (D3/D4): la CA de consulta no comparte almacén,
  sesiones, roles ni cuentas de prueba con E10.1. La VPN nunca da administración: la consola sigue solo en el
  PC de Daniel y `PASARELA_CONSOLA_LOCAL` no se admite en el perfil privado.
- **Ningún puerto de aplicación hacia Internet** (D2): en la demostración solo el proxy publica `127.0.0.1:18443`;
  las redes de la pasarela, la API y la base son `internal`.

### Por qué certificados de cliente (mTLS) por persona

- **Autenticación real y verificable** en el borde: clave privada en el equipo de la persona; el proxy verifica
  la cadena, la vigencia y la revocación antes de que nada llegue a la aplicación. No es una cabecera arbitraria.
- **Compatible con la VPN** (sobre cualquier túnel; no depende de la IP ni del proveedor, que siguen sin decidir).
- **Sin contraseñas** que gestionar ni almacén de cuentas nuevo; los navegadores (Brave/Chromium en Windows,
  almacén del usuario) seleccionan el certificado.
- **Revocación inmediata y local:** CRL nueva + `nginx -s reload`, sin reiniciar (medido: 0,53 s hasta tres
  rechazos seguidos).
- Alternativas descartadas para esta etapa: un IdP/OIDC (decisión de proveedor no tomada), contraseñas en el
  proxy (otro almacén de credenciales), la identidad por IP de la VPN (una IP no es una persona).

## 2. Configuración por entorno

El modo **local** no cambia (`app.api.publica.aplicacion:app`, `app.pasarela.aplicacion:app`, loopback,
`--no-proxy-headers`). El perfil **privado** tiene puntos de entrada y reglas propios y **no arranca** si falta
algo (cerrado ante el fallo). Ejemplo completo sin secretos:
[`despliegue/consulta-privada/ejemplo.env`](../../despliegue/consulta-privada/ejemplo.env).

**API** — `uvicorn app.api.publica.privada:app --host <IP interna> --port 8010 --workers 1 --no-access-log --no-proxy-headers`

| Variable | Perfil privado |
|---|---|
| `DATABASE_URL_ARCHIVO`, `API_PUBLICA_CLAVES_ARCHIVO` | Obligatorias; archivos montados en ejecución. Si `DATABASE_URL` o `API_PUBLICA_CLAVES` llegan por el entorno, no arranca |
| `API_PUBLICA_HOSTS`, `API_PUBLICA_CLIENTES` | Obligatorias y exactas (`host:puerto`; IP sin redes) |
| `API_PUBLICA_CORS_ORIGENES` | Debe quedar vacía |
| `API_PUBLICA_CONCURRENCIA_COSTOSAS` (> 0), `API_PUBLICA_ESPERA_COSTOSAS` | Semáforo de las consultas de coste 5 |
| `BASE_TIEMPO_MAXIMO_CONSULTA_MS`, `BASE_TIEMPO_MAXIMO_INACTIVA_MS` (> 0), `BASE_POOL_*` | Límites de cada conexión y del pool |
| `DIRECTORIO_{LABORATORIO_MODELOS,CARTERAS_MODELOS,PREDICCIONES_MODELOS,PRONOSTICOS_EXPERIMENTALES}` | Deben existir y ser legibles; si no, no arranca (código 3) |
| Usuario | No arranca como root |

**Pasarela** — `PASARELA_PERFIL=privado` con el mismo módulo (`--workers 1`): `PASARELA_PROXIES_FIABLES`,
`PASARELA_SECRETO_PROXY_ARCHIVO`, `PASARELA_CLAVE_API_ARCHIVO` (y `PASARELA_CLAVE_API` vacía),
`PASARELA_API_URL` (`http://` sobre IP literal), `PASARELA_HOSTS` y `PASARELA_ORIGENES` (`https://`) exactos,
cuotas `PASARELA_FICHAS_PERSONA_POR_MINUTO`, `PASARELA_FICHAS_AGREGADAS_POR_MINUTO`, `PASARELA_MAX_PERSONAS`.

## 3. Cuotas por persona y agregadas (SEC-07)

- La pasarela descuenta el **coste de la API** (1 ligera, 2 listado/guardado, 3 predicciones/fiabilidad,
  5 estadísticas/resultados; `/salud` 1) de la cubeta **de la persona** y de la **agregada** a la vez, solo si
  ambas lo admiten: A no gasta la cuota de B y la suma queda bajo el agregado. 429 con `Retry-After` y
  `X-RateLimit-*` de la persona (`limite_excedido` o `limite_agregado_excedido`).
- **Memoria acotada sin olvidar deudas (v2, F1023-LIM-01).** Se siguen como mucho `PASARELA_MAX_PERSONAS`
  identidades. Una identidad nueva solo entra si alguna cubeta seguida ya se ha recuperado del todo (se descarta
  la menos reciente de esas, que no debe nada). Si todas tienen deuda, la nueva recibe 429
  `limite_identidades_excedido` con `Retry-After` hasta que la primera se recupere; las ya seguidas conservan su
  cuota. Expulsar una cubeta agotada ya no la devuelve a su capacidad (en v1 sí: hallazgo de Codex). El ajuste
  recomendado es `PASARELA_MAX_PERSONAS` mayor que el número de invitados, de modo que el rechazo por capacidad
  solo aparezca ante identidades inesperadas.
- **Un trabajador por servicio.** Las cubetas viven en la memoria del proceso: con N trabajadores la cuota
  efectiva sería N×Q, y un reinicio las devuelve a su capacidad (demostrado, T07). El proxy añade un límite
  grueso por certificado (`limit_req`, 20/s). La clave compartida pasarela→API debe tener una cuota por clave y
  por IP **mayor** que el agregado, para que decida la pasarela.
- **Sin caché de respuestas:** nada que mezclar entre personas ni que sobreviva a una revocación.

## 4. Claves de API: emisión, solapamiento, rotación y revocación (SEC-05)

La clave queda en el servidor (archivo de la pasarela); la API solo conoce huellas. Procedimiento ensayado
(T16, sintético):
1. Emitir `clave_2` (`python -m scripts.api_publica_claves generar --id <id>`) y añadir su huella al archivo de
   la API **junto a** la de `clave_1`; **reiniciar la API** (ventana medida en la demostración: 6,63 s sin
   respuesta a `/api/v1/salud`, sondeo cada 0,1 s).
2. Poner `clave_2` en el archivo de la pasarela y **reiniciar la pasarela** (2,66 s hasta servir de nuevo).
3. Quitar la huella de `clave_1` y reiniciar la API: `clave_1` → 401, `clave_2` → 200.

Las claves se leen al arrancar: **rotar o revocar exige reinicio**; no se promete cero cortes antes de D11. Sin
huellas válidas la API no arranca y la pasarela responde 503/504 controlado; sin clave válida la pasarela no
arranca (el proxy, 502/504). Caducidad recomendada: rotar al menos cada 90 días y al dar de baja a un invitado
con acceso al servidor.

## 5. Recursos: tiempos máximos, semáforo y pool (SEC-08)

- **Rol lector** (`despliegue/consulta-privada/postgres/roles.sql`): `default_transaction_read_only = on`,
  `statement_timeout = 2s`, `idle_in_transaction_session_timeout = 5s`, solo `SELECT`.
- **Conexiones de la API** (`BASE_*`): `statement_timeout` 1,5 s, `idle_in_transaction_session_timeout` 5 s,
  pool 4+2 con espera 2 s. Sin `BASE_*` (consola, CLI, Fase 6) el motor es exactamente el de siempre.
- **Cancelación controlada:** `57014` → 503 `consulta_cancelada` con `Retry-After: 5`; la sesión termina en
  ROLLBACK y la conexión vuelve sana al pool (P3 de `tests/postgres_e102.py`).
- **Semáforo de coste 5** (`API_PUBLICA_CONCURRENCIA_COSTOSAS`): se toma y se libera **dentro del hilo** que
  ejecuta la consulta; si el cliente se desconecta, la capacidad no vuelve hasta que el trabajo termina (T14).
  Sin hueco: 503 `consultas_ocupadas` con `Retry-After: 1`.
- Ningún cambio en rutas, parámetros ni respuestas del OpenAPI; `/api/v1/estado` conserva acceso y cuerpo.

## 6. Solo lectura efectiva y matriz de datos (SEC-10, DAT-07)

- Publicación preparada **antes** del montaje (escritura) y montada `:ro`; contenedores con raíz de solo
  lectura, sin capacidades, usuario 10001; `/tmp` en memoria.
- **Hallazgo DAT-07 corregido:** `app/api/dependencies.py` construía `HtmlFileStorage()` al importarse y creaba
  `storage/html` (y `storage/logs/sync.log`) en el directorio de trabajo; la API privada no arrancaba con la raíz
  de solo lectura. El registro de conectores se crea ahora la primera vez que se pide (mismo singleton para la
  aplicación local). Sonda antes/después y regresión en `test_api_publica_privada.py`.
- Un almacén de consulta **ausente** impide arrancar (no se sirve vacío como válido).
- **Las tres procedencias de Producto 6 presentes (v2, F1023-DAT-01).** La preparación sintética emite, con los
  productores reales y sobre el mismo histórico que guarda en PostgreSQL, la operación diaria de Producto 3
  (`storage/pronosticos`), los pronósticos del laboratorio (`laboratorio/pronosticos`) y las carteras de
  Producto 5; después llega el sorteo objetivo, de modo que cada juego tiene emisiones y resultados observados
  en las tres. Calcula además `esperado-consultas.json` con los mismos casos de uso antes de publicar.
- **Matriz estricta:** cada uno de los 19 endpoints × 4 juegos tiene su comprobación de contrato y contenido
  (procedencias, emisiones, claves de líneas, objetivos observados, totales de sorteos, claves de modelos y
  carteras, ficha de simulación); además, cada procedencia por separado. Una API que lea un almacén vaciado o
  mal apuntado responde 200 (`sin_artefactos`), pero la matriz lo **rechaza** (control negativo T24).
- Ausencias deliberadas, aparte: tres juegos sin simulaciones (lista vacía declarada) y su simulación
  inexistente (404).
- El estimador `.pkl` se relee y se vuelve a hashear en solo lectura: alterado antes del montaje → 409 `alterado`.

## 7. Demostración automática (inicio, parada y reversión)

```
python despliegue/consulta-privada/demostracion.py --salida <carpeta nueva> \
    --python-preparacion <python con backend/requirements.lock> [--ca-extra <pem>] [--conservar]
```

- Requiere Docker, OpenSSL y Node con Playwright (`NODE_PATH` al `node_modules` del frontend). Crea su propio
  proyecto (`e102demo<hex>`), PKI de prueba de 2 días, secretos sintéticos en archivos, la publicación y la base;
  ejecuta 32 comprobaciones; **detiene y borra solo** sus contenedores, redes y volumen (etiqueta
  `e102.demostracion=<proyecto>`). `--conservar` deja la pila para inspección; se detiene con
  `docker compose -p <proyecto> -f despliegue/consulta-privada/compose.yml down` y
  `docker volume rm <proyecto>-pgdatos`.
- No toca `docker-compose.yml` (PostgreSQL de Fase 6) ni sus credenciales, puertos, volúmenes o redes.
- **Revertir** la entrega: `git apply -R` del parche; la demostración no deja estado fuera de su carpeta.

## 8. Procedimiento focal en Windows (Brave)

**Alcance:** acredita solo que Brave, con el almacén de certificados del usuario de Windows, presenta un
certificado de cliente y que un servidor local que lo exige lo verifica; no la topología de producción.
[`ensayo_brave_mtls_e102.ps1`](../../despliegue/consulta-privada/windows/ensayo_brave_mtls_e102.ps1), con la
lógica en [`ensayo_brave_mtls_e102_nucleo.ps1`](../../despliegue/consulta-privada/windows/ensayo_brave_mtls_e102_nucleo.ps1)
(v4, F1023-WIN-01..05; Windows PowerShell 5.1 o PowerShell 7, modo estricto 2.0):

- **Antes de instalar nada explica y pide confirmación** (`SI`, o `-Confirmar`): agrega TEMPORALMENTE una CA de
  prueba (validez 2 h) al almacén de confianza del usuario; Windows pide confirmación al agregarla y al retirarla.
  No usa credenciales reales ni pide contraseñas: la del PFX del servidor es aleatoria y solo viaja por la
  entrada estándar del servidor local.
- Carpeta temporal con permisos solo del usuario; Brave con un **perfil nuevo** en ella.
- El servidor (`servidor_mtls_e102.py`, sin cambios en v3) **guarda el resultado de forma atómica antes de
  responder** a la petición válida (sobrevive a un fin forzado), solo acepta el CN esperado (otro CN → 403),
  cuenta los handshakes fallidos y para de forma **cooperativa** con un archivo de parada; el fin forzado es el
  último recurso.
- **Plazos** para arranque, espera humana (sin `Read-Host` tras instalar: detecta el resultado solo) y salida.
- **Finalización resistente a errores (v3, WIN-02).** Cada limpieza es un paso aislado y sus errores se
  acumulan sin saltarse los siguientes:
  1. servidor;
  2. procesos de Brave de **su** perfil, nunca por nombre;
  3. CA de la raíz por huella;
  4. cada certificado con su clave;
  5. carpeta;
  6. verificación final.

  Las colecciones de procesos se materializan donde se consultan (`@(...)`). Una consulta de procesos que falla
  **no** cuenta como cero procesos: queda como residuo no verificado. El resumen JSON se escribe siempre: en
  `-Salida`, si no en `TEMP` y, en último caso, en la consola.
- **Resumen y código coherentes (v4, WIN-05).** El código final, incluido el 6, se decide **antes** de emitir
  el JSON. El resumen emitido, también el de consola, lleva siempre el mismo código que devuelve el proceso, y
  `resumen_guardado` indica si llegó a un archivo.
- **Claves privadas (v3, WIN-03).** Las claves se crean en el proveedor CNG *Microsoft Software Key Storage
  Provider* y cada certificado lleva una marca propia de la ejecución.
  - Se registra solo la huella y el **nombre exacto del contenedor de clave**, sin leer ni exportar material.
  - La retirada usa `Remove-Item -DeleteKey`. Si el contenedor siguiera existiendo, se borra ese mismo nombre
    con `CngKey.Delete()`.
  - Un certificado cuya marca no coincide no se toca.
  - El certificado del servidor ya no se retira justo tras exportar el PFX (eso dejaba su clave): se elimina
    con su clave en la finalización.
  - La verificación comprueba, por identificador exacto, certificado, CA en la raíz y clave. Nunca recorre
    almacenes ni enumera claves ajenas.
- **Sin recuperación automática (v4, WIN-04).** En v3 había una opción `-Recuperar` que borraba a partir de
  un JSON; se ha retirado. El motivo: un JSON modificable no demuestra a quién pertenecen los identificadores
  que lleva. La limpieza usa **solo** los identificadores que la propia ejecución creó y guarda en memoria.
  - `<Salida>.diagnostico.json` es un **registro diagnóstico**. Contiene:
    - los identificadores propios;
    - el estado del servidor;
    - al final, los residuos.

    No guarda secretos. Ningún código del ensayo lo lee y no es una autorización ni instrucciones de borrado.
  - Si la limpieza es completa, se borra. Si queda algo, se conserva y el ensayo termina con el código 4. Sus
    identificadores se revisan antes de cualquier acción manual concreta.
  - El parámetro `-Recuperar` ya no existe: PowerShell rechaza la llamada antes de ejecutar nada.
- **Códigos:**
  - 0: verificado, con limpieza completa y verificada;
  - 1: fallo;
  - 2: sin interacción, plazo vencido o certificado ausente/incorrecto;
  - 3: el servidor no arrancó;
  - 4: limpieza incompleta o no verificable;
  - 5: cancelado sin instalar nada;
  - 6: el resumen no pudo guardarse en ningún archivo (solo en la consola), si no había ya otro error.

  Una limpieza incompleta nunca da 0.
- **Acreditado en Linux.**
  - **Servidor real con CA sintética** (`test_servidor_mtls_e102.py`, v2): éxito, fin forzado tras el GET,
    parada cooperativa, sin interacción, CN incorrecto, sin certificado u otra CA, handshake colgado y arranque
    fallido.
  - **Comportamiento del guion con PowerShell 7.4 y 7.6** (`test_ensayo_brave_e102.py`, v4). El núcleo real se
    ejecuta con una plataforma sustituta, que incluye una clave ajena sintética, en estos casos:
    - colección vacía;
    - uno o varios procesos propios junto a uno ajeno;
    - consulta de procesos fallida;
    - fallo de arranque y fallo al crear un certificado;
    - sin interacción;
    - excepción en cada fase de limpieza;
    - clave huérfana y clave sin identificador;
    - una salida no escribible, y ambas no escribibles (JSON de consola y código, los dos en 6);
    - registro diagnóstico con sus identificadores y residuos, y registro manipulado, que nunca se consume.

    Además, el guion principal completo se ejecuta con los cmdlets de Windows sustituidos, y se comprueba que
    rechaza `-Recuperar` sin tocar nada.
  - **Controles negativos:** sobre v2 fallan las pruebas del guion completo; sobre v3, las de `-Recuperar` y de
    ambos destinos.
  - **Compatibilidad sintáctica con Windows PowerShell 5.1:** PSScriptAnalyzer 1.23.0, con el perfil de 5.1, da
    0 avisos de sintaxis. Solo informa de `-DeleteKey`, que es un parámetro dinámico del proveedor `Cert:`,
    invisible para el análisis estático.
  - En CI, el job `lock-windows` ejecuta las pruebas también con Windows PowerShell 5.1.
- **Acreditado en Windows nativo (2026-11-03):** Python 3.14.6 x64 y Windows PowerShell 5.1.26100.9711;
  206 pruebas seleccionadas aprobadas, sin fallos, errores ni omisiones. Incluyen las pruebas de comportamiento
  del arnés con sustitutos bajo PowerShell 5.1. El ensayo focal con Brave 156.1.98.62 verificó el certificado
  `CN=invitado-brave` en un servidor local mTLS (puerto dinámico 56565), con salida 0 y 15 pasos correctos.
  Se retiraron la CA temporal, los tres certificados con sus tres claves privadas, los siete procesos propios
  de Brave y el perfil temporal; una segunda comprobación de solo lectura confirmó las ausencias por sus
  identificadores exactos. Esto acredita el proveedor de certificados y CNG en este ensayo, sin demostrar
  la topología de producción ni una VPN real. Evidencia y atribución: [fase10_e102_e103_validacion_operador_2026-11-03.md](fase10_e102_e103_validacion_operador_2026-11-03.md).

## 9. Pendientes y límites (no se declaran cumplidos)

- **Actualización 2026-11-04.** PR #109 integrado con los 11 checks aprobados; los puntos de abajo sobre el
  CI remoto son el registro histórico de cómo se llegó ahí. El importador de E10.4 ya existe
  ([generaciones](fase10_generaciones.md)): el proceso de la API puede quedar ligado a una sola generación
  aceptada; el compose de esta demostración sigue sirviendo la publicación sintética de E10.2 sin generación.
  Pendiente: que E10.5 arranque el par API/pasarela de cada generación con su configuración inmutable (D11).

- **CI remoto (PR #109):** el primer CI dio cuatro checks en rojo. La entrega conjunta corrige los fallos
  funcionales y el procesamiento de diagnósticos; la remediación de imágenes sigue abierta:
  - el test de acciones fijadas por SHA;
  - la demostración, que fallaba con la salida relativa y en su limpieza (ver abajo);
  - el job de imágenes.

  Grype sí ejecutó en GitHub Actions y encontró 60 pares altos del sistema base Debian 13.7. Ninguno tenía
  versión corregida en los datos de Debian consultados el 2026-11-03. Bookworm tampoco elimina los altos/
  críticos del diagnóstico, y su resultado de Grype es desconocido. Ese hallazgo sigue abierto:
  ver [imágenes y CI](fase10_imagenes_y_ci.md).
- **Arnés de la demostración (PR #109, CI109-02).**
  - `--salida` puede ser relativa o absoluta; se normaliza antes de derivar rutas, y los bind mounts reciben
    orígenes absolutos.
  - Un fallo en cualquier fase conserva su motivo original y no impide la limpieza.
  - Cada paso de limpieza está aislado y solo toca recursos con la etiqueta y el prefijo del proyecto.
  - El informe se escribe siempre, saneado, y termina en fallo ante cualquier error o residuo.
- **Windows nativo completado:** instalación estricta del lock en un venv nuevo, `pip check`, 206 pruebas y
  ensayo focal de Brave aprobados y auditados. El primer job remoto `lock-windows` del PR #109 pasó
  sobre `8dad5919` (run `41623345120`); la nueva corrección debe volver a pasar sus checks remotos.
- **Importador E10.4 (histórico 2026-11-03: «no existe»):** implementado el 2026-11-04 como CLI
  (`scripts.generaciones importar`) sobre la misma base de código; ver [generaciones](fase10_generaciones.md).
- **Producción:** proveedor, presupuesto, infraestructura, registro de imágenes, custodia de secretos reales,
  respaldos, activación, CA real y su custodia, VPN real (D2) y caducidad de certificados quedan sin decidir.
- Las cuotas y el semáforo son por proceso; un límite global entre réplicas exige otra decisión (D11).
