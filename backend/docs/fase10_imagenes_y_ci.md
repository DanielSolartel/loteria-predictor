# Fase 10 — E10.3: lock de Python, imágenes y CI de seguridad

Estado (2026-11-04): **integrado en `main`** (PR #109, merge `4aa24b85`; 11 checks del head `f219e499`
aprobados: Python `41758396786`, frontend `41758396837`, seguridad `41758396770`). **Grype real:** 8 avisos
High por imagen aceptados temporalmente (16 entradas exactas, caducidad 2026-11-17) y **0 graves abiertos**;
siguen siendo avisos no corregidos y la aceptación no se amplía ni se renueva. E10.4 añade el trabajo
`generaciones` (sección 3). Pendiente: producción y la revisión de los avisos antes de su caducidad.

Estado anterior (2026-11-03, histórico): implementado y validado en Linux aislado y en Windows nativo; en el
primer CI del PR #109 el check de imágenes estaba abierto. Consulta privada (E10.2):
[fase10_consulta_privada.md](fase10_consulta_privada.md).

## 1. Lock de Python

| Archivo | Contenido | Uso |
|---|---|---|
| `backend/requirements.lock` | `requirements.txt` + `requirements-pruebas.in` (httpx 0.28.1), **universal** (Linux y Windows, marcadores), 59 paquetes con sus SHA-256 | CI, PC de desarrollo |
| `backend/requirements-servicio.lock` | `requirements-servicio.in` (= `requirements.txt` sin pytest/pytest-cov), Linux x86_64 (manylinux_2_28), 48 paquetes | Imágenes |
| `backend/requirements-auditoria.lock` | `pip-audit==2.10.1`, 28 paquetes | Job de auditoría |

- **Combinación acreditada:** las versiones son exactamente las que instaló el CI verde del PR #108 (ejecuciones
  41559392449/41559392408: Linux 3.14.9 y Windows 3.14.10; 59 paquetes en la unión, `colorama` y `tzdata` solo
  en Windows, `uvloop` fuera de Windows). Ninguna actualización ajena.
- **Instalación estricta** (sin tocar el entorno ya instalado de Daniel; siempre en un entorno nuevo):
  `python -m pip install --require-hashes --no-deps --only-binary :all: -r requirements.lock` y `pip check`.
- **Generación / actualización** (uv 0.11; fuera del entorno operativo):
  ```
  uv pip compile requirements.txt requirements-pruebas.in --universal --python-version 3.14 --generate-hashes --no-annotate -o requirements.lock
  uv pip compile requirements-servicio.in --python-version 3.14 --python-platform x86_64-manylinux_2_28 --generate-hashes --no-annotate -o requirements-servicio.lock
  ```
  La primera generación fijó además `--constraint` con el conjunto instalado por el CI acreditado. Una
  actualización (también de seguridad) es un cambio revisado: nuevo lock, sus regresiones y el CI completo.
- **Comprobado:** dos instalaciones limpias en Linux (Python 3.14.6) → mismo `pip freeze` (57 paquetes) y mismas
  huellas de cada `RECORD` (sin las entradas `bin/`, que llevan la ruta del venv en el shebang). En Windows
  nativo, Python 3.14.6 x64: instalación estricta en un venv nuevo, **58 paquetes aplicables** (59 en la unión
  universal; `pip` queda fuera del lock), versiones exactas y `pip check` sin requisitos rotos. Las 206 pruebas
  seleccionadas pasan, sin omisiones. Se conservó el entorno anterior. Informe: [fase10_e102_e103_validacion_operador_2026-11-03.md](fase10_e102_e103_validacion_operador_2026-11-03.md).
  El primer job remoto `lock-windows` del PR #109 también pasó (run `41623345120`). Ese resultado
  corresponde al commit `8dad5919`; la nueva corrección aún debe validarse en CI.
- **Frontend (v2):** `frontend/package-lock.json` sí cambia por la actualización revisada de Vitest
  3.2.7 a 4.1.12 que resuelve los críticos de tinypool (sección 3). `npm ci` conserva su uso; no hay excepciones
  críticas aceptadas.

## 2. Imágenes (`despliegue/imagenes/Dockerfile`)

- Etapas: `base-dependencias` (venv desde `requirements-servicio.lock`), `spa` (`npm ci --ignore-scripts` y
  `npm run build`), `ejecucion` (usuario 10001), y los objetivos `api` y `pasarela` (este con `dist/`).
- Bases por **digest**: `python:3.14-slim@sha256:930e1abb…`, `node:22-alpine@sha256:fe4f6d74…`; en la demostración,
  `nginx:1.29-alpine@sha256:56168782…` y `postgres:16-alpine@sha256:0cefaabd…`.
- `.dockerignore` deja pasar solo `backend/app`, el lock de servicio y lo necesario del frontend; nunca `.git`,
  `.env`, `*.privado.env`, SQLite, `storage/`, `privado/`, perfiles ni datos.
- Secretos **solo en ejecución** (archivos montados). Una CA adicional del entorno de construcción (proxy con
  inspección TLS) puede pasarse como secreto de BuildKit (`--secret id=ca_extra,...`): no queda en ninguna capa
  y la verificación TLS no se desactiva.
- **Importador = E10.4:** la etapa `base-dependencias` es la base compartible que reutilizará; aquí no existe
  ningún importador, ni vacío ni simulado (fila «pendiente» en la matriz). **2026-11-04:** el importador existe
  como CLI (`scripts.generaciones importar`, [generaciones](fase10_generaciones.md)), que se ejecuta con el
  código y Alembic del mismo commit. **No** se añade una imagen de importador: sería un artefacto nuevo con su
  propio escaneo Grype, y las 16 excepciones no se amplían a otros artefactos. Su imagen queda para E10.5.
- Demostración local con límites y solo lectura: `despliegue/consulta-privada/compose.yml` (no toca
  `docker-compose.yml`).

### Reproducibilidad

| Qué | Resultado (Linux, Docker 29.9.2, dos construcciones `--no-cache`) |
|---|---|
| Dependencias | Iguales: mismo `pip freeze`, mismas huellas de `RECORD` y del código (550 líneas idénticas) |
| Bytes OCI | **Distintos**: dos identificadores de imagen; 5 de 9 capas difieren (marcas de tiempo de los `RUN`) |

La reproducibilidad de **dependencias** está acreditada; la igualdad **byte a byte** de la imagen no (exigiría
`SOURCE_DATE_EPOCH`, reescritura de marcas de tiempo y un constructor fijado). Se registran los digest de cada
construcción.

## 3. CI de seguridad (`.github/workflows/seguridad-consulta-privada.yml`)

Workflow nuevo; los 5 jobs existentes y el comprobador OpenSSL no cambian salvo el fijado de sus acciones (v2,
F1023-CI-02: las 10 referencias por etiqueta de `validacion-frontend.yml` y `validacion-python-314.yml` pasan a
`@<sha> # vN`, sin tocar nombres de jobs, disparadores, permisos ni pruebas; una prueba exige SHA de 40 caracteres
en **todos** los `uses:` remotos de todos los workflows). Acciones fijadas por el SHA que GitHub
resolvió para sus etiquetas en las ejecuciones verdes del PR #108 (checkout `11d5960a…`, setup-python `a26af69b…`,
setup-node `49933ea5…`, upload-artifact `ea165f8d…`); herramientas en contenedor por digest (syft 1.55.0,
grype 0.121.0 y gitleaks 8.30.1, versiones de al menos dos semanas). Sin secretos del repositorio, sin
publicar imágenes, sin `continue-on-error`.

| Job | Qué hace | Falla si |
|---|---|---|
| `lock-linux` | Instalación estricta del lock, `pip check`, pruebas de API/pasarela/umbral, SBOM del entorno | Un hash o una prueba |
| `lock-windows` | Igual en `windows-2025` (selección del perfil privado) | Ídem |
| `auditoria` | `pip-audit` (los tres locks + pins solo Windows), `npm audit` + umbral, gitleaks (historial y árbol, **ambos siempre**, con informes JSON redactados fuera del árbol y publicados aunque fallen) | Cualquier aviso Python; alto/crítico npm sin excepción vigente; un secreto no exceptuado; un informe ausente o no válido |
| `imagenes` | Construye `api` y `pasarela` (ejecución mínima), registra su identificación (id, usuario, SO, arquitectura, Python, base), comprueba usuario, contenido y que la raíz mínima basta al servicio, SBOM CycloneDX (2 imágenes + npm), grype + umbral de **las dos** imágenes, y publica siempre SBOM, informes e identificación | Alto/crítico sin excepción en cualquiera de las dos; un SBOM o informe ausente o no válido; fallo de descarga de la base de grype |
| `postgres` | Servicio PostgreSQL 16 por digest: roles, migraciones, `tests/postgres_fase8.py` y `tests/postgres_e102.py` | Cualquier comprobación |
| `demostracion` | La demostración completa de extremo a extremo | Cualquiera de las 32 comprobaciones; un fallo de fase o de limpieza (el informe se escribe igualmente) |

- **Críticos de tinypool resueltos por actualización (v2, F1023-SEC-01):** `vitest` 3.2.7 → **4.1.12** (solo
  desarrollo). Todos los cambios del lock quedan dentro del subárbol de vitest y tinypool desaparece; `npm audit`
  pasa de 2 críticos a **0 críticos/altos** (quedan 3 moderados de la cadena `openapi-typescript`/`minimatch`, que
  no bloquean). La suite completa de Vitest da el mismo resultado que con vitest 3 (13 archivos, 864 pruebas), y
  `typecheck`, `tipos:comprobar`, `build` y el canario siguen verdes. El lock se regeneró con npm 11.21.0 (npm
  10.9.4 falla con un error interno de arborist al actualizar vitest); `npm ci` con npm 10 lo instala sin cambios.
- **Excepciones:** solo activa una con `estado: "aceptada"`, `aceptada_por` no vacío, `fecha_aceptacion` no
  futura, sin caducar, del artefacto correcto e `id`/`paquete` concretos (sin comodines). En Grype exige además
  versión exacta y severidad aceptada; si hay varias versiones del mismo aviso/paquete, todas deben estar
  cubiertas. Un alto/crítico nuevo o sin cobertura mantiene el umbral en rojo. Las dos entradas de tinypool
  siguen `retirada_por_actualizacion`, sin aceptante. La aceptación temporal B de imágenes se documenta abajo.
- **Informes válidos o fallo (F1023-ROB-01):** el umbral exige `auditReportVersion` 2 y sin `error`; contadores
  completos que coincidan con los paquetes; `via` heredados que nombren paquetes existentes, con la gravedad
  efectiva calculada como el máximo de los avisos propios y heredados (igual que npm); y en grype, descriptor,
  `matches` como lista y cada coincidencia con id, gravedad válida, paquete y versión. Un informe incompleto o
  incoherente nunca se da por limpio.
- **Contenido de imagen (F1023-CI-01):** `despliegue/imagenes/comprobar_contenido_imagen.py`, el MISMO paso en CI
  y en local, dentro de cada imagen final con `--network none`. Admite el paquete de código
  `/srv/backend/app/infrastructure/storage` (solo `.py`) y falla por usuario root, `.env`, `*.privado.*`, SQLite
  (`.sqlite3` incluido), PFX/P12, `.git`, carpetas de datos, claves privadas PEM y archivos ilegibles. Control
  negativo con datos y secretos plantados: falla.
- Gitleaks: dos huellas exactas en `.gitleaksignore` (literales sintéticos de pruebas existentes).
- **Grype en el primer CI del PR #109 (CI109-03): ejecutó y falló por hallazgos altos.** En GitHub Actions,
  grype 0.121.0 descargó su base y analizó `imagen-api`. Resultado: 182 hallazgos (60 high, 64 medium, 12 low y
  46 negligible), con 60 pares ID/paquete altos (18 IDs, 22 paquetes del sistema base Debian 13). Ninguno tenía
  excepción, y el umbral falló correctamente. El bucle se detuvo ahí y `imagen-pasarela` quedó sin evaluar; la
  subida de informes se omitió.
  - **Job corregido:** se escanean y evalúan siempre las dos imágenes y se acumulan los fallos. El paso termina en
    fallo si falta un informe válido o queda un alto/crítico. SBOM, informes de grype e identificación de las
    imágenes se publican con `if: always()` y una lista explícita de archivos (sin imágenes tar ni carpetas de
    trabajo). No hay `continue-on-error` y el umbral no se rebaja.
  - **Estado de esos 60 pares (diagnóstico, no el umbral).** Se contrastaron con los datos de Debian incluidos en
    la base de Trivy, instantánea del 2026-11-03T07:14Z. Se descargó de `mirror.gcr.io/aquasec/trivy-db:2` y se
    usó sin red sobre las dos imágenes construidas con la base Trixie fijada. Resultado:
    - los 60 pares están presentes en `api` y en `pasarela`;
    - en esa instantánea, **ninguno tiene versión corregida en Debian 13.7**: 59 `affected` y 1 `fix_deferred`;
    - `python:3.14-slim` y `3.14-slim-trixie` apuntan al mismo índice que la base fijada
      (`sha256:930e1abb…`, Docker Hub, 2026-11-03).
  - **Alternativas evaluadas el 2026-11-03.** Ninguna elimina los hallazgos altos/críticos en ese diagnóstico;
    Bookworm reduce su número total respecto a Trixie, pero introduce dos críticos. No se afirma nada fuera
    de esas bases e instantánea ni se presenta el diagnóstico como un resultado de Grype.
    - **`python:3.14.10-slim-bookworm`** (Debian 12.15). Su índice es `sha256:516b51cb…` (amd64
      `sha256:47d41ea4…`), el mismo que `3.14-slim-bookworm`.
      - Construye `api` y `pasarela` con los locks vigentes: hashes, solo ruedas y `pip check` correctos.
      - Imports y librerías compartidas iguales que Trixie; usuario 10001, contenido sin hallazgos y
        demostración completa **32/32**.
      - Pero en la misma instantánea de Trivy su capa del SO tiene 38 altos/críticos, ninguno con versión
        corregida, entre ellos **2 críticos**: `CVE-2025-7458` en `libsqlite3-0` (`affected`) y
        `CVE-2023-45853` en `zlib1g` (`will_not_fix`). Trixie tiene 45 altos y ningún crítico.
      - **No se adopta**: no mejora el resultado y añade críticos. Su escaneo con grype no se ha podido
        ejecutar.
    - **Alpine** no es viable con el lock actual: `lightgbm`, `scikit-learn` y `xgboost-cpu` no publican ruedas
      musl para cp314, y la imagen instala solo ruedas.
- **Segundo CI del PR #109: informes reales de grype de las DOS imágenes.** Run `41644445657`, grype 0.121.0, base
  construida el 2026-11-03T06:20:47Z. Cada imagen tiene los mismos 60 pares altos: 18 CVE de 8 paquetes fuente
  (glibc, gcc-14, zlib, sqlite3, util-linux, ncurses, perl, acl), 59 `wont-fix` y 1 `not-fixed` (zlib), sin
  versión corregida.
- **Remediación: imagen de ejecución mínima (misma base, sin cambio de distribución).**
  - La etapa `raiz-ejecucion` (`despliegue/imagenes/raiz_minima.py`) arma la raíz con **solo los 12 paquetes**
    que el servicio carga de verdad, cada uno con su ficha dpkg real en `/var/lib/dpkg/status.d/` (visible para
    SBOM y escáneres). Son `libc6`, `libgcc-s1`, `libstdc++6`, `zlib1g`, `libssl3t64`, `libzstd1`, `libffi8`,
    `libbz2-1.0`, `liblzma5`, `tzdata`, `netbase` y `base-files`.
  - Python va sin `sqlite3`, `curses`/`readline`, `dbm`, `_uuid` ni `tkinter`, y el entorno de ejecución sin
    `pip`. La imagen final parte de `scratch`: sin shell ni utilidades.
  - En la construcción se comprueba que cada ELF de Python resuelve sus bibliotecas dentro de la raíz.
- **Verificado sobre las imágenes finales.**
  - Locks con hashes y `pip check` en la etapa de construcción.
  - 48 distribuciones importadas y los módulos retirados ausentes (`comprobar_ejecucion_imagen.py`, también en
    CI). Cada una de las 313 extensiones se juzga por separado con el código de salida y toda la salida del
    cargador de la imagen (CI109-MIN-01): 305 resuelven sus dependencias; 7 son objetos sin dependencias
    (`statically linked`, confirmado en el propio ELF: ET_DYN x86-64 sin DT_NEEDED), y la única tolerancia,
    exacta y registrada, es `lightgbm/lib/lib_lightgbm.so` sin `libgomp.so.1`. Cualquier otro código, ELF
    inválido, diagnóstico o biblioteca ausente hace fallar el paso.
  - Usuario 10001, contenido sin hallazgos y arranque con fallo cerrado sin configuración.
  - Demostración completa **32/32**. Su T11 hace las mismas comprobaciones con Python porque ya no hay shell.
- **Tercer CI del PR #109: reducción confirmada por Grype real.** Run `41741191802`, commit `93e62d1a`, árbol
  `95bc1ef8`, Grype 0.121.0 y DB válida construida el 2026-11-03T06:20:47Z. En cada imagen hay 37 coincidencias:
  **8 High, 0 Critical**, 18 Medium, 4 Low y 7 Negligible. Los ocho pares corresponden a **6 CVE únicos** en
  cuatro paquetes binarios: `libc6`, `libgcc-s1`, `libstdc++6` y `zlib1g` (7 `wont-fix`, 1 `not-fixed`).
  - La reducción **60 → 8 pares por imagen y 18 → 6 CVE** ya está comprobada por CI; doce CVE se retiraron con
    sus paquetes. Trivy sigue siendo un diagnóstico complementario.
  - El job falló correctamente: aún no había excepciones aceptadas. Construcción, contenido, comprobador y
    demostración pasan; los diez checks restantes están verdes.
  - Después de revisar ese resultado, el usuario confirmó expresamente la **opción B**. Su alcance y límites
    figuran en la aceptación temporal siguiente; no se consideran corregidos los avisos que cubre.
- **`lightgbm` no carga** (ni en Trixie, ni en Bookworm, ni en la imagen mínima) porque falta `libgomp.so.1`.
  Ninguno de los módulos que sirven la API o la pasarela lo importa. Es preexistente y no se cambia aquí; la
  comprobación de ejecución lo informa como única tolerancia explícita.
- **Grype en el entorno de Claude:** sigue sin poder descargar su base (`grype.anchore.io`, 403). Esto no
  afecta a GitHub Actions, donde sí funcionó.
- **Gitleaks en el segundo CI:** un `generic-api-key` en un literal sintético de una prueba nueva
  (`test_demostracion_e102_arnes.py:218`, commit `3a68d7fe`).
  - La prueba ahora genera el valor en cada ejecución.
  - La copia histórica queda cubierta solo por su huella exacta en `.gitleaksignore`; el historial no se
    reescribe.
  - Los dos escaneos se ejecutan siempre y publican sus informes redactados.
- `tests/postgres_fase8.py`: A2 esperaba 500; desde la Fase 9 la API responde el 409 `historico_no_valido` que
  declara su OpenAPI (la base 375fc8ca también). Se alinea la expectativa al contrato vigente.

- **Trabajo `generaciones` (E10.4, 2026-11-04).** PostgreSQL 16 de servicio por digest; roles de consulta,
  captura e importación con contraseñas generadas y enmascaradas, y URL en archivos 0600. Ejecuta los
  escenarios C1–C10 sobre PostgreSQL real (`tests/unit/generaciones`) y la demostración
  `despliegue/generaciones/demostracion_e104.py`. Publica siempre el JUnit y `demostracion.json` (sin URL ni
  claves) y no tiene `continue-on-error`. No cambia los demás trabajos ni sus umbrales. Detalle:
  [generaciones](fase10_generaciones.md).
- **Imagen de la API y generación (E10.4 v2, E104-GEN-02).** La imagen `--target api` no cambia: el perfil
  ligado recalcula al arrancar la huella de su propio `app/` (la imagen no lleva `alembic/`) y contrasta la
  revisión exigida con `alembic_version` de la base conectada. Comprobado con la imagen real y su orden por
  defecto: mismo código arranca; otro `app/` u otra revisión, código 3.

### Aceptación temporal B (3 de noviembre de 2026)

El usuario responsable del proyecto confirmó expresamente «confirmo B» en esta conversación, tras revisar las
opciones, el residual y sus límites. Se registran **16 entradas exactas**, ocho por imagen, en
`despliegue/seguridad/excepciones-vulnerabilidades.json`. Solo autorizan **CI e integración del PR #109**;
no autorizan despliegue, publicación de imágenes ni exposición a Internet. La aceptación no resuelve los CVE
ni demuestra inalcanzabilidad en todo el código nativo.

| CVE | Paquete(s) | Versión exacta | Pares por imagen |
|---|---|---|---:|
| CVE-2026-19499, CVE-2026-5435, CVE-2026-84243 | libc6 | 2.41-12+deb13u4 | 3 |
| CVE-2026-102010, CVE-2026-95619 | libgcc-s1 y libstdc++6 | 14.2.0-19 | 4 |
| CVE-2026-85091 | zlib1g | 1:1.3.dfsg+really1.3.1-1+b1 | 1 |

- Aceptación: **2026-11-03**. Caduca: **2026-11-17 inclusive**, según la fecha UTC que evalúa el CI.
- Solo formato Grype, artefacto `imagen-api` o `imagen-pasarela`, id, paquete, versión y severidad `high`
  exactos. No se interpretan rangos ni comodines. Cada versión observada necesita cobertura propia; una
  versión adicional, un CVE nuevo o una subida a `critical` hacen fallar el umbral si no tienen otra aceptación
  expresa y vigente.
- Sin renovación automática. Revisar ante corrección disponible, cambio de versión o exposición, o evidencia
  nueva de explotación. Los informes completos de ambas imágenes siguen generándose y publicándose.
- El resumen identifica las versiones y los avisos aceptados temporalmente; no los etiqueta como corregidos.
- La nueva CI sobre este registro aún está pendiente (2026-11-03). **Resultado 2026-11-04:** el CI del head
  `f219e499` pasó con Grype real: 8 High por imagen aceptados temporalmente y 0 graves abiertos. Los ensayos
  del umbral con los informes reales de entonces eran validación local del comparador.
- Un futuro despliegue conserva las decisiones de acceso privado por VPN y mTLS, invitados de solo lectura y
  administración local; su autorización sigue siendo independiente. Fase 6 y E10.4 no cambian.
- **Esta aceptación es solo de vulnerabilidades (opción B del PR #109).** No autoriza el protocolo B de captura
  de la enmienda 01, que pausaría Fase 6: D10 y D11 siguen pendientes.

### PR #111: TLS de prueba y ampliación B (6 de noviembre de 2026)

El run `42253840876` falló en dos pruebas de `operacion_consulta/test_sonda_tls.py`: los certificados
sintéticos carecían de Authority Key Identifier, exigido por la validación estricta de Python 3.14.
La PKI efímera de prueba incorpora SKI, AKI y Key Usage; el servidor de prueba también valida con
`VERIFY_X509_STRICT`. Se mantienen las comprobaciones de nombre, cadena y certificado cliente. No cambia
el TLS del producto. En Python 3.14.9 local se reprodujeron los dos fallos originales y, con la corrección,
pasaron las 136 pruebas de operación, incluidos los intercambios mTLS reales en loopback. El runner que
originó el fallo usaba Python 3.14.10; la suite remota corregida queda pendiente.

El run de imágenes `42253840794`, job `128015614560`, informó de un alto nuevo por imagen:
`CVE-2026-76844` en `zlib1g` **`1:1.3.dfsg+really1.3.1-1+b1`**, estado Grype `not-fixed`.
El [registro de Debian](https://security-tracker.debian.org/tracker/CVE-2026-76844) sigue considerando
vulnerable Trixie; la versión corregida publicada pertenece a forky/sid. Se conservan las bases fijadas.

Tras revisar el aviso y el alcance, el usuario confirmó expresamente «confirmo» a la ampliación B:

- Se añaden **solo dos entradas**: el CVE, paquete, versión y severidad `high` exactos anteriores para
  `imagen-api` y `imagen-pasarela`. Las 16 aceptaciones anteriores y las dos retiradas se conservan.
- Fecha de esta ampliación: **2026-11-06**. Caducidad: **2026-11-17 inclusive, UTC**, sin renovación
  automática. Total: 18 aceptaciones temporales, nueve por imagen.
- Solo **CI e integración del PR #111**. No autoriza despliegue, publicación de imágenes ni exposición
  a Internet. El aviso permanece presente; la aceptación no es una corrección.
- Un CVE, paquete, versión, artefacto o severidad diferente sigue sin cobertura. Se conserva el comprobador
  del umbral y la generación y publicación de informes completos.

El comparador real acepta los dos informes conservados de ese run con este registro y bloquea de nuevo
al caducar las aceptaciones. Esto verifica la política sobre los informes existentes; la construcción y
el escaneo de las imágenes en la nueva CI quedan pendientes.

## 4. Propuesta de protección de `main` (sin aplicar)

No se cambia ninguna configuración de GitHub ni se configura CD. Propuesta para que Daniel la decida:

- Regla de protección (o *ruleset*) en `main`: PR obligatorio, 1 aprobación, descartar aprobaciones al
  empujar, conversaciones resueltas, historial lineal opcional, sin *force push* ni borrado, también para
  administradores.
- **Checks requeridos:** los 5 existentes (`Linux - suite completa`, `Windows - seleccion…`,
  `Frontend - Node 22`, `Frontend - Node 24`, `Navegador - Chromium/Linux…`) y, tras su primera ejecución
  verde, los 6 nuevos (`Lock Python - instalacion estricta (Linux)`, `… (Windows)`,
  `Auditoria de dependencias y secretos`, `Imagenes - construccion, SBOM y escaneo (sin publicar)`,
  `PostgreSQL de pruebas - Fase 8 y perfil privado`, `Demostracion de extremo a extremo…`).
- Ramas al día con `main` antes de fusionar; acciones solo fijadas por SHA (política de Actions:
  «Allow actions … pinned to a full-length commit SHA»); `permissions: contents: read` por defecto.
- Revisión periódica (mensual) de las excepciones y de los digest de las bases.
