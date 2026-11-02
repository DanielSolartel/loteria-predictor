#!/usr/bin/env bash
# Levanta el sistema completo con un único comando:
#   1. Postgres vía Docker Compose
#   2. Migraciones Alembic (crea esquema + siembra los 3 juegos)
#   3. Servidor FastAPI con recarga automática
#
# Uso: ./run.sh
set -euo pipefail

cd "$(dirname "$0")"

echo "==> Levantando PostgreSQL..."
docker compose up -d postgres

echo "==> Esperando a que PostgreSQL acepte conexiones..."
until docker compose exec -T postgres pg_isready -U loteria > /dev/null 2>&1; do
    sleep 1
done

cd backend

if [ ! -d ".venv" ]; then
    echo "==> Creando entorno virtual..."
    python3 -m venv .venv
fi
source .venv/bin/activate

echo "==> Instalando dependencias..."
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
    cp .env.example .env
fi

echo "==> Aplicando migraciones..."
alembic upgrade head

if ! python -m scripts.consola_cuentas comprobar > /dev/null 2>&1; then
    echo "==> AVISO: la consola no tiene cuentas; responderá 503 hasta crear una (solo en este equipo):"
    echo "    python -m scripts.consola_cuentas crear --usuario daniel --rol administrador"
fi

# E10.1: solo loopback y sin confiar en cabeceras X-Forwarded-* (la consola rechaza conexiones remotas o por VPN).
echo "==> Iniciando servidor en http://localhost:8000 ..."
uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-proxy-headers --reload
