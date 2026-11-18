# syntax=docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
# Consulta privada para linux/amd64. Construir desde la raíz con --target api o pasarela.
# El contexto, el usuario de ejecución y los archivos de secretos se definen como en Compose.
ARG WOLFI_IMAGEN=cgr.dev/chainguard/wolfi-base@sha256:1e9962e1b5b2df9e572ba3ff1165904dc4675f2fd8d70b0c70011cff6aee3c8e
ARG NODE_IMAGEN=docker.io/library/node:22-alpine@sha256:fe4f6d74e20370acb04ad889077d14d0f64a9c8ea6a42bc60cddf1e844699914

FROM ${NODE_IMAGEN} AS paquetes
COPY despliegue/imagenes/descargar_wolfi.mjs despliegue/imagenes/wolfi-x86_64.lock /insumos/
RUN --mount=type=secret,id=ca_extra,required=false \
    if [ -f /run/secrets/ca_extra ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/ca_extra; fi \
 && node --use-env-proxy /insumos/descargar_wolfi.mjs /insumos/wolfi-x86_64.lock /paquetes

FROM ${WOLFI_IMAGEN} AS sistema
# APK autentica el índice con la clave fijada. El repositorio local contiene solo los APK del lock.
RUN --network=none --mount=type=bind,from=paquetes,source=/paquetes,target=/paquetes <<'SH'
set -eu
mkdir -p /raiz/etc/apk/keys
echo 'f0031424cf46f7db780ce63a45f0fd6aa6f85f601e6bb3b7a91fe3d4d5b7d2cc  /etc/apk/keys/wolfi-signing.rsa.pub' | sha256sum -c -
cp /etc/apk/keys/wolfi-signing.rsa.pub /raiz/etc/apk/keys/
apk --root /raiz --keys-dir /raiz/etc/apk/keys --initdb --no-network --no-scripts --repositories-file /dev/null --repository /paquetes add $(cat /paquetes/solicitados.txt)
SH

FROM scratch AS base-python
COPY --from=sistema /raiz/ /

FROM base-python AS base-dependencias
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN ["/usr/bin/python3", "-m", "venv", "/opt/venv"]
RUN --mount=type=secret,id=ca_extra,target=/etc/ssl/certs/ca-certificates.crt,required=false \
    --mount=type=bind,source=backend/requirements-servicio.lock,target=/tmp/requirements-servicio.lock \
    ["/opt/venv/bin/python", "-m", "pip", "install", "--cert", "/etc/ssl/certs/ca-certificates.crt", "--require-hashes", "--no-deps", "--only-binary", ":all:", "--no-compile", "-r", "/tmp/requirements-servicio.lock"]
RUN --network=none ["/opt/venv/bin/python", "-m", "pip", "check"]

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
FROM base-dependencias AS venv-ejecucion
RUN --network=none ["/opt/venv/bin/python", "-m", "pip", "uninstall", "--yes", "pip"]

FROM sistema AS raiz-ejecucion
RUN --network=none <<'SH'
set -eu
for modulo in _sqlite3 _curses _curses_panel readline _dbm _gdbm _uuid _tkinter; do
    rm -f /raiz/usr/lib/python3.14/lib-dynload/"$modulo".*.so
done
find /raiz/usr/bin -mindepth 1 -maxdepth 1 ! -name 'python' ! -name 'python3' ! -name 'python3.14' -exec rm -f '{}' ';'
rm -f /raiz/usr/share/python-wheels/pip-*.whl /raiz/etc/shadow /raiz/etc/gshadow
printf 'consulta:x:10001:10001::/nonexistent:/sbin/nologin\n' >> /raiz/etc/passwd
printf 'consulta:x:10001:\n' >> /raiz/etc/group
SH

FROM scratch AS ejecucion
COPY --from=raiz-ejecucion /raiz/ /
COPY --from=venv-ejecucion /opt/venv /opt/venv
RUN --network=none --mount=type=bind,source=despliegue/imagenes/comprobar_raiz_wolfi.py,target=/tmp/comprobar.py \
    ["/usr/bin/python3", "-B", "/tmp/comprobar.py"]
ENV PATH=/opt/venv/bin:/usr/local/bin PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONUTF8=1 LANG=C.UTF-8
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
