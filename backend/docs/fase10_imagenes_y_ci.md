# Fase 10 — E10.3: lock de Python, imágenes y CI de seguridad

Estado (2026-11-03): **implementado; validado en Linux aislado y con instalación estricta y selección de
pruebas en Windows nativo**. **Pendiente:** publicación e integración, primera ejecución del workflow en el
CI remoto (incluido su job de Windows y el escaneo real de imágenes con Grype), importador E10.4 y producción. Consulta privada (E10.2):
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
  El job remoto `lock-windows` sigue pendiente; la validación local no se le atribuye.
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
  ningún importador, ni vacío ni simulado (fila «pendiente» en la matriz).
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
| `auditoria` | `pip-audit` (los tres locks + pins solo Windows), `npm audit` + umbral, gitleaks (historial y árbol) | Cualquier aviso Python; alto/crítico npm sin excepción vigente; un secreto no exceptuado; un informe ausente o no válido |
| `imagenes` | Construye `api` y `pasarela`, comprueba usuario y contenido, SBOM CycloneDX (2 imágenes + npm), grype + umbral | Alto/crítico sin excepción; fallo de descarga de la base de grype |
| `postgres` | Servicio PostgreSQL 16 por digest: roles, migraciones, `tests/postgres_fase8.py` y `tests/postgres_e102.py` | Cualquier comprobación |
| `demostracion` | La demostración completa de extremo a extremo | Cualquiera de las 32 comprobaciones |

- **Críticos de tinypool resueltos por actualización (v2, F1023-SEC-01):** `vitest` 3.2.7 → **4.1.12** (solo
  desarrollo). Todos los cambios del lock quedan dentro del subárbol de vitest y tinypool desaparece; `npm audit`
  pasa de 2 críticos a **0 críticos/altos** (quedan 3 moderados de la cadena `openapi-typescript`/`minimatch`, que
  no bloquean). La suite completa de Vitest da el mismo resultado que con vitest 3 (13 archivos, 864 pruebas), y
  `typecheck`, `tipos:comprobar`, `build` y el canario siguen verdes. El lock se regeneró con npm 11.21.0 (npm
  10.9.4 falla con un error interno de arborist al actualizar vitest); `npm ci` con npm 10 lo instala sin cambios.
- **Excepciones:** solo activa una con `estado: "aceptada"`, `aceptada_por` no vacío, `fecha_aceptacion` no
  futura, sin caducar, del artefacto correcto e `id`/`paquete` concretos (sin comodines). Las dos de tinypool
  quedan `retirada_por_actualizacion`, sin aceptante: **nadie ha aceptado ningún riesgo** y no se atribuye
  ninguna decisión a Daniel. Un crítico sin excepción aceptada mantiene el umbral en rojo.
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
- **Grype pendiente:** no se pudo ejecutar aquí; la política de red de este entorno deniega `grype.anchore.io`
  (descarga de su base). Sin informe no hay escaneo limpio: el job `imagenes` fallaría.
- `tests/postgres_fase8.py`: A2 esperaba 500; desde la Fase 9 la API responde el 409 `historico_no_valido` que
  declara su OpenAPI (la base 375fc8ca también). Se alinea la expectativa al contrato vigente.

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
