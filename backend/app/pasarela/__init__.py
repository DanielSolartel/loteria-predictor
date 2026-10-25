"""
Fase 9.1: pasarela local entre la SPA y la API publica `/api/v1`.

Proceso propio, separado de la API y de la aplicacion local. Sirve
exclusivamente la SPA compilada (`frontend/dist`) y reenvia una lista cerrada
de consultas GET a `/api/v1`, anadiendo la clave de API que solo conoce el
servidor. Es un cliente HTTP de la API: no importa casos de uso, dominio,
repositorios ni la base de datos.

- `configuracion.py`: ajustes `PASARELA_*` (destino loopback fijo, hosts y
  origenes admitidos, clave, `dist/`, enlace opcional a la consola local).
- `rutas.py`: lista cerrada de plantillas `/api/v1` y de sus parametros.
- `cliente.py`: consulta a la API con `http.client`, en un hilo, con tiempo,
  tamano y concurrencia acotados; sin redirecciones.
- `aplicacion.py`: aplicacion ASGI (controles locales, cabeceras, estaticos y
  errores sanitizados). Su docstring fija el unico arranque soportado.
"""
