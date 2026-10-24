"""
Fase 8: API publica de solo lectura, versionada bajo `/api/v1`.

Composicion propia (`aplicacion.py`; su docstring fija el unico arranque soportado,
con `--no-access-log --no-proxy-headers`)
separada de `app.main`: no monta la web, los estaticos ni los routers REST
internos. Reutiliza los casos de uso existentes (juegos, sorteos, estadisticas,
predicciones guardadas y simulaciones guardadas) con lecturas de solo lectura;
no entrena, simula, sincroniza, recupera trabajos ni escribe.

- `configuracion.py`: claves (huellas SHA-256), limites, CORS y documentacion.
- `seguridad.py`: verificacion de la clave `X-API-Key` y cuota por clave.
- `limites.py`: cubeta de fichas acotada y segura entre hilos, POR PROCESO.
- `monitoreo.py`: solicitudes, latencia y estado en memoria, sin datos sensibles.
- `errores.py`, `esquemas.py`: contratos de error y de respuesta.
- `dependencias.py`, `rutas.py`: lecturas y endpoints.
"""
