# Fase 8 en Windows — validación dirigida completada

El 24 de octubre de 2026 Daniel completó y ChatGPT auditó la validación dirigida de la API pública v2 en Windows 11 / PowerShell 5.1 / Python 3.14.6: 92 pruebas, cuatro sondas y PostgreSQL 16.14 aislado con datos sintéticos. Código, archivos privados y contenedor operativo conservados; limpieza propia verificada. [Registro del operador y huellas](fase8_validacion_operador_2026-10-24.md). La publicación manual y el CI del PR están pendientes.

Esta guía conserva el protocolo para reproducir comprobaciones justificadas. La selección amplia se recolectó (3285 casos, incluidas las 92 de API); su ejecución completa se reserva al CI del PR. Los resultados de Linux conservan su atribución y sus versiones propias.

## Reglas de seguridad

- **Dónde aplicar:** en un worktree NUEVO desacoplado en `f15f513b431dd9a5dc3a2fb148a63a82a11405b5`, con el parche **completo de la v2** (la v1 no se aplica). No se tocan `C:\GitHub\loteria-predictor-fase6` (la tarea `LP6-01023009031fcabd` depende de él) ni otros worktrees.
- **Sin cambios de entorno:** no se instala ni actualiza nada en el entorno operativo; la Fase 8 no añade dependencias.
- **Claves de prueba:** se generan solo para la validación y se revocan al terminar. No se copian a archivos versionados ni a capturas, y no se pegan en chats.
- **Base de datos:** las pruebas de `pytest` no conectan con PostgreSQL; las que arrancan Uvicorn usan una base SQLite temporal propia. El paso 4 usa una base **de pruebas separada**, y el script se niega a correr si el nombre no contiene `prueba` o si hay sorteos no sintéticos.
- **Ninguna escritura:** la API pública no escribe en la base ni en los almacenes; aun así, no se arranca contra la base operativa durante la validación.
- No se muestran `.env` ni `DATABASE_URL`.

## 1. Aplicar sobre la base exacta

En un worktree nuevo, desacoplado en `f15f513`:

- comprobar el SHA-256 del parche completo de la v2;
- `git apply --check`, `git apply` y `git diff --check`;
- comprobar que `git status` muestra solo los archivos del manifiesto de la v2.

## 2. Pruebas de la Fase 8 y selección de Windows

Desde `backend`:

```
python -m pytest -p no:cacheprovider -rsw tests\unit\api_publica --junitxml=..\f8-api-publica-windows.xml
```

Incluye las regresiones de la v2: errores inesperados, métodos del monitoreo y arranque soportado.

La corrida dirigida ejecutó las 92 pruebas de `tests/unit/api_publica` y recolectó la selección habitual de `tests\seleccion_windows.txt`: 3285 casos, incluidas esas 92. La carpeta completa contiene las pruebas de la v1 y las regresiones de la v2. La selección amplia y el contraste OpenSSL (`scripts\ci_contrastes_openssl.py --modo exigir`) quedan pendientes para el CI del PR; la recolección no se presenta como ejecución completa.

Atención en Windows:
- las pruebas de concurrencia usan hilos y `httpx.ASGITransport` (sin red);
- `test_api_publica_arranque.py` arranca dos procesos Uvicorn reales con el arranque del paso 3, leído de `docs\fase8_api_publica.md`. Escuchan solo en `127.0.0.1`, con puerto 0 elegido por el sistema, y se terminan al acabar cada prueba. Si el cortafuegos pidiera permiso, se puede denegar: las conexiones son locales;
- la prueba de inventario de rutas admite routers planos o perezosos, según la versión de FastAPI instalada (`requirements.txt` exige `fastapi>=0.115`).

## 3. Arranque aislado con una clave de prueba

```
python -m scripts.api_publica_claves generar --id prueba-windows
```

1. Copiar solo la línea `entrada para API_PUBLICA_CLAVES` a la variable de la sesión de PowerShell, no a archivos.
2. Comprobar con `python -m scripts.api_publica_claves comprobar`.
3. Arrancar, contra la base de pruebas, con el único arranque soportado: `uvicorn app.api.publica.aplicacion:app --host 127.0.0.1 --port 8010 --no-access-log --no-proxy-headers`.
4. Verificar:
   - `/api/v1/salud` responde 200 sin clave;
   - `/api/v1/juegos` responde 401 sin clave y 200 con ella;
   - `/api/v1/juegos?api_key=<valor inventado>` responde 401 y ese valor no aparece en la consola de Uvicorn;
   - `POST /api/sorteos` responde 404;
   - 70 solicitudes seguidas con la misma clave reciben 429 con `Retry-After`;
   - variar `X-Forwarded-For` no evita el 429 por IP (con `API_PUBLICA_FICHAS_POR_MINUTO_IP` bajo, solo para esta comprobación);
   - `/api/v1/docs` abre Swagger con «Authorize».
5. Al terminar, cerrar la sesión de PowerShell; la clave de prueba deja de existir con ella.

## 4. PostgreSQL de pruebas del operador (completado)

La corrida auditada usó un contenedor Docker propio con la imagen local de PostgreSQL 16.14, puerto efímero de `127.0.0.1` y datos en tmpfs. La base empezó vacía; las migraciones llegaron a `0006` y los 1616 sorteos finales fueron sintéticos. El script cumplió A–F y A2. El contenedor operativo conservó ID, arranque, volumen y configuración; el contenedor y el temporal propios se eliminaron. El supervisor r1 corrigió una consulta a un campo opcional de Docker; ese ajuste no cambió el producto ni repitió las 92 pruebas o las cuatro sondas.

Con `DATABASE_URL` apuntando **solo** a una base cuyo nombre contenga `prueba`, en la revisión `0006`:

```
python tests\postgres_fase8.py > ..\f8-postgres-windows.json
```

Comprueba:
- consultas con el cableado predeterminado;
- un histórico inconsistente devuelve 500 sin detalles;
- transacción de solo lectura;
- preservación de filas y almacenes;
- 24 solicitudes simultáneas con cuota 10;
- ausencia de escrituras;
- un proceso Uvicorn real, con el arranque soportado, cuyos registros no contienen la clave, su huella ni una clave enviada en la URL.

Código 0 significa que todo se cumple.

## Evidencia conservada y futuras comprobaciones

- salidas y JUnit de los pasos 2 y 4;
- resultado del paso 3 (códigos HTTP), sin la clave;
- versiones de Python, FastAPI, Starlette, Uvicorn, pydantic y PostgreSQL;
- `git status` y `git diff --stat` del worktree nuevo.

La publicación (commit, push y PR) la hace Daniel manualmente. El despliegue es de la Fase 10.
