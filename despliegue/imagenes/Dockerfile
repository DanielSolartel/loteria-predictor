# Fase 10 (E10.3): imagenes de la consulta privada (API publica y pasarela con la SPA), en varias etapas.
# Contexto de construccion: la raiz del repositorio (`.dockerignore` deja pasar solo lo necesario).
#
#   docker build -f despliegue/imagenes/Dockerfile --target api      -t <nombre>:<etiqueta> .
#   docker build -f despliegue/imagenes/Dockerfile --target pasarela -t <nombre>:<etiqueta> .
#
# - Bases fijadas por DIGEST (indice multiplataforma de docker.io). Actualizarlas es un cambio revisado.
# - Dependencias de Python desde `backend/requirements-servicio.lock` con `--require-hashes` y solo ruedas.
# - SPA con `npm ci --ignore-scripts` desde `frontend/package-lock.json`.
# - Usuario sin privilegios (10001); el codigo y el entorno virtual son de root y de solo lectura para el.
# - Ningun secreto en la imagen: claves, URL de la base y secreto del proxy son ARCHIVOS montados al ejecutar.
# - CA adicional OPCIONAL del entorno de construccion (proxy con inspeccion TLS): `--secret id=ca_extra,src=<pem>`.
#   Se monta solo durante el RUN (BuildKit) y no queda en ninguna capa; la verificacion TLS nunca se desactiva.
# - `base-dependencias` es la base de construccion COMPARTIBLE. El importador de la generacion (E10.4) la
#   reutilizara; aqui no existe ni se simula ninguna etapa de importador.
ARG PYTHON_IMAGEN=docker.io/library/python:3.14-slim@sha256:930e1abba7c4e8f96ed93e8012c35d174d7732752731bbd5e8e757d7ec6f3966
ARG NODE_IMAGEN=docker.io/library/node:22-alpine@sha256:fe4f6d74e20370acb04ad889077d14d0f64a9c8ea6a42bc60cddf1e844699914

# ---------------------------------------------------------------------------
FROM ${PYTHON_IMAGEN} AS base-dependencias
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
COPY backend/requirements-servicio.lock /tmp/requirements-servicio.lock
RUN --mount=type=secret,id=ca_extra,required=false \
    if [ -f /run/secrets/ca_extra ]; then export PIP_CERT=/run/secrets/ca_extra; fi \
 && python -m venv /opt/venv \
 && /opt/venv/bin/python -m pip install --require-hashes --no-deps --only-binary :all: --no-compile \
        -r /tmp/requirements-servicio.lock \
 && /opt/venv/bin/python -m pip check \
 && rm /tmp/requirements-servicio.lock

# ---------------------------------------------------------------------------
FROM ${NODE_IMAGEN} AS spa
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=secret,id=ca_extra,required=false \
    if [ -f /run/secrets/ca_extra ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/ca_extra; fi \
 && npm ci --no-audit --no-fund --ignore-scripts
COPY frontend/index.html frontend/tsconfig.json frontend/vite.config.ts ./
COPY frontend/public ./public
COPY frontend/src ./src
RUN npm run build

# ---------------------------------------------------------------------------
FROM ${PYTHON_IMAGEN} AS ejecucion
RUN groupadd --system --gid 10001 consulta \
 && useradd --system --uid 10001 --gid consulta --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin consulta
COPY --from=base-dependencias /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/backend
COPY backend/app/__init__.py ./app/__init__.py

# ---------------------------------------------------------------------------
FROM ejecucion AS api
COPY backend/app ./app
USER 10001:10001
EXPOSE 8010
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8010/api/v1/salud', timeout=2).status == 200 else 1)"]
CMD ["uvicorn", "app.api.publica.privada:app", "--host", "0.0.0.0", "--port", "8010", "--workers", "1", \
     "--no-access-log", "--no-proxy-headers"]

# ---------------------------------------------------------------------------
FROM ejecucion AS pasarela
COPY backend/app/pasarela ./app/pasarela
COPY --from=spa /src/frontend/dist /srv/frontend/dist
ENV PASARELA_PERFIL=privado PASARELA_DIST=/srv/frontend/dist
USER 10001:10001
EXPOSE 8020
CMD ["uvicorn", "app.pasarela.aplicacion:app", "--host", "0.0.0.0", "--port", "8020", "--workers", "1", \
     "--no-access-log", "--no-proxy-headers"]
