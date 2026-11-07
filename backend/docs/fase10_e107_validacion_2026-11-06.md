# Validacion E10.7 v3 — 6 de noviembre de 2026

Base integrada: `4aaca446c5ea79975683220da0037e2569fbe28e` (PR #111).
La correccion conserva los archivos de `backend/app`, Alembic, locks e imagenes.

## Resultado nativo confirmado

El ensayo v3 en el PC del operador termino con codigo 0 y **27/27 controles
aprobados**, incluidos importacion D07, comparacion de consultas R08,
activacion local mTLS, rechazo sin certificado y metricas de loopback. La
restauracion quedo completa en una base nueva. Los servicios se detuvieron y
los recursos se conservaron.

Se verificaron CRC, SHA-256 del ZIP recibido y SHA-256 interno del JSON. El
informe con identificadores, huellas y alcance esta en
[fase10_e107_validacion_nativa_2026-11-06.md](fase10_e107_validacion_nativa_2026-11-06.md).

El diagnostico del intento v2 situo el primer fallo en D07. La validacion
interna utilizaba TestClient, cuya dependencia httpx pertenece al lock de
pruebas y no al lock de servicio de la imagen auxiliar. La v3 usa Uvicorn/h11
en loopback, dentro del mismo proceso que audita las aperturas de archivos.
La ejecucion nativa confirma que D07 y R08 aprobaron con esa correccion.

## Comprobaciones locales ejecutadas

Entorno local: Linux/Python 3.12.14; los resultados nativos anteriores proceden
del PC y se registran por separado.

- 30 pruebas del perfil y paquete: permiso propio, persistencia, entradas
  invalidas, extraccion confinada, integridad de fuentes, protocolo stdin,
  evidencia y mTLS real, incluida validacion X.509 estricta.
- 10 pruebas del diagnostico: comandos de lectura, identidad del ensayo,
  salida filtrada, OOM, logs truncados y montajes de Docker Desktop.
- 10 regresiones de las consultas HTTP y el preparador: HTTP real sin
  TestClient/httpx/httpcore, autenticacion, query string, rechazo de rutas
  externas, manejo de estados/no-JSON, cierre del servidor ante errores,
  auditoria de archivos desde el hilo HTTP y rechazo de escrituras. Incluyen
  el corte inmediato en el primer fallo y la conservacion de controles previos
  en la evidencia si una fase posterior falla.
- 8 comprobaciones de la demostracion E10.5/E10.6, con HTTP real y servicios
  sustitutos: activacion, mantenimiento, lectores coherentes, reversion,
  recuperacion, conservacion de generaciones y vencimiento de metricas.

Total local: **50 pruebas unittest y 8 comprobaciones de demostracion**.
Las pruebas HTTP locales cargaron Uvicorn 0.54.0, h11 0.16.0 y Click 8.5.0
(versiones de los locks) desde sus fuentes oficiales, cuyos 73 blobs se
verificaron. Esas fuentes temporales no se incluyen en el repositorio ni en
el paquete nativo; el PC reutiliza las librerias de su imagen existente.

## Integridad de la entrega

Las fuentes incluidas contienen los 961 archivos versionados de backend/ y
despliegue/ de la base integrada, con sus bytes originales. Se contrastaron
los blobs de Git y los subarboles reconstruidos:

- backend: `ae33c618ca11b562d13a71a4f95bbfa7e4c9ab46`.
- despliegue: `95195eb1ecc90f5bfb9b1a150a2f12942a7db22a`.
- SHA-256 de fuentes.zip: `9ccaf8f9a9bd573d67d20e4454d9c535d71ed1dbbbb4e34d6794cd63e6d9011e`.

El lanzador no requiere Git ni la carpeta de proyecto del operador. Se probo
el protocolo Python por stdin con los ZIP completos, desde una carpeta vacia
y sin Git en PATH, verificando su evidencia y rechazo previo a recursos en el
entorno local Python 3.12. El recorrido real Docker/PostgreSQL/nginx/mTLS se
acredita con la evidencia nativa recibida.

## Limites

La suite anterior de 136 pruebas pytest no se reejecuto en el entorno local,
donde pytest no esta disponible. El estado del CI corresponde al commit del
PR y se consulta por separado. Permanecen pendientes datos reales D10,
activacion real D11, drenaje y reversion nativos, R-W, custodia externa y
Brave/confianza de CA. `produccion_autorizada` permanece en `false`.
