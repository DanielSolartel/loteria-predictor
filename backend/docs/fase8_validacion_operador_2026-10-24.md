# Fase 8 v2 — validación local del operador, 24 de octubre de 2026

**Estado:** implementación y validación técnica local completadas y auditadas.
Pendientes: publicación manual (commit, push y PR) y CI del PR.
El despliegue corresponde a Fase 10.
La siguiente fase de producto es Fase 9, frontend React.

La base es `f15f513b431dd9a5dc3a2fb148a63a82a11405b5`, merge del PR #98.
La entrega v2 original cambia 30 rutas: seis modificadas y 24 nuevas, con
784 archivos públicos resultantes. Este cierre cambia cinco documentos de
esa entrega y añade este registro: seis documentos, 31 rutas candidatas a
commit y 785 archivos públicos. Los otros 779 conservan sus bytes. El
supervisor comprueba ese alcance antes y después, sin modificar el índice.

## Alcance y atribución

Daniel ejecutó las comprobaciones desde Windows 11 con Python 3.14.6. Las
pruebas de API y las sondas usaron datos sintéticos y proveedores aislados.
PostgreSQL se ejecutó en un contenedor Linux de Docker local, separado del
operativo, y se verificó desde Windows; no es una instalación de PostgreSQL
nativa de Windows. ChatGPT auditó los ZIP, sus manifiestos y sus registros.

| Evidencia | Resultado |
|---|---|
| API pública v2, Windows | 92 pruebas únicas aprobadas, sin fallos, errores ni omisiones |
| Sondas del auditor, Windows | 4/4 con el arranque soportado; procesos propios cerrados |
| Selección de Windows | 3285 casos recolectados, incluidas las 92 de API; la selección completa no se ejecutó en esta validación dirigida |
| PostgreSQL 16.14 aislado | A–F y A2 cumplidos, Alembic `0006`, 1616 sorteos sintéticos |
| Conservación | Código y archivos privados F8 y worktrees protegidos conservados; metadatos operativos idénticos antes y después |
| Limpieza | Contenedor de PostgreSQL de prueba y temporal propio eliminados |

La corrida de pruebas y sondas ocurrió entre las 15:02:52 y las 15:04:37,
hora de Bogotá. PostgreSQL se verificó entre las 15:42:16 y las 15:43:03.
Los recibos originales conservan los instantes UTC completos.

Los resultados Linux de la entrega v2 conservan su atribución a Claude:
92 pruebas de la API, 3739 pruebas existentes justificadas y PostgreSQL 16.13
aislado. El auditor también verificó la misma v2 en Linux con 92 pruebas y
cuatro sondas. Las baterías se solapan y no se suman. La suite completa de
7517, las 535 regresiones, OpenSSL y las siete demostraciones documentadas
en la guía siguen atribuidas a la v1; no se repitieron en la v2 por rutina.

## PostgreSQL y proceso real

Se reutilizó la imagen local por su ID inmutable, sin descargar imágenes:
`sha256:33f923b05f64ca54ac4401c01126a6b92afe839a0aa0a52bc5aeb5cc958e5f20`.
Docker Desktop usó el contexto `desktop-linux`, servidor 29.6.2.
El contenedor de prueba fue `f8-prueba-d1ac9a35e21f`, con base
`f8_prueba_d1ac9a35e21f`, puerto `127.0.0.1:58465` y datos en tmpfs propio,
sin volúmenes ni carpetas compartidas. La preparación creó únicamente los
datos sintéticos de esa base de prueba.

| Criterio | Comprobación auditada |
|---|---|
| A | 14 consultas con el cableado predeterminado respondieron 200; simulación con integridad verificada y base disponible |
| A2 | Un histórico sintético inconsistente de ColorLoto recibió 500 genérico sin detalles internos |
| B | PostgreSQL rechazó `CREATE TABLE` dentro de la transacción de solo lectura; el error esperado consta en el registro del servidor |
| C | Las consultas conservaron las filas de todas las tablas y los almacenes de prueba |
| D | 24 solicitudes simultáneas con cuota 10: exactamente 10 respuestas 200 y 14 respuestas 429 con `Retry-After` |
| E | POST, PUT, PATCH y DELETE recibieron 404/405 y conservaron los datos |
| F | Uvicorn real respondió 200/401/401/404/404; cinco líneas de monitoreo propio, sin clave, huella o clave enviada en la URL |

El único arranque soportado se conserva en las guías y los ejemplos:

```text
uvicorn app.api.publica.aplicacion:app --host 127.0.0.1 --port 8010 --no-access-log --no-proxy-headers
```

Los cuatro hallazgos de la v1 quedan cubiertos por las sondas nativas de la
v2: 500 sanitizado con cabeceras y monitoreo coherentes (F8-SEC-01), clave
rechazada en URL ausente del registro de acceso (F8-SEC-02), cuota por IP
conservada al variar `X-Forwarded-For` (F8-LIM-01) y métodos no estándar
agrupados en `OTRO` con 405 (F8-OBS-01).

## Conservación y corrección del supervisor

El contenedor operativo `loteria-predictor-fase2-final-postgres-1` mantuvo el
ID `48a929eb0a177c14b2dfd511448f4e718030244a9ec4975e5e246d40ede820e5`,
el arranque `2026-10-20T02:34:49.377082931Z`, cero reinicios, el volumen
`loteria-predictor-fase2-final_postgres_data` y su configuración. Los archivos
`operativo-antes.json` y `operativo-despues.json` son idénticos byte a byte.
La verificación no consultó por SQL la base operativa, no cambió servicios
ni la tarea `LP6-01023009031fcabd`, y no ejecutó ciclos operativos manuales.
Las claves se generaron para las pruebas y no se guardan en el repositorio.

Una primera corrida del supervisor se detuvo al consultar el campo opcional
`HostConfig.Tmpfs`, antes de crear un contenedor o ejecutar SQL. La revisión
r1 corrigió esa consulta y manejó los campos opcionales ausentes o nulos,
sin cambiar el producto. El fallo se reprodujo con un cliente Docker real
contra un Engine HTTP sintético; la corrección pasó cinco casos y los 15
controles del supervisor. La corrida nativa posterior completó PostgreSQL.
Las 92 pruebas y las cuatro sondas no se repitieron durante esta corrección.

## Entorno nativo

| Componente | Versión |
|---|---|
| Python | 3.14.6, Windows 11 |
| FastAPI / Starlette | 0.141.1 / 1.7.0 |
| Pydantic / Uvicorn | 2.13.5 / 0.54.0 |
| HTTPX / pytest | 0.28.1 / 9.1.1 |
| SQLAlchemy / psycopg / Alembic | 2.1.1 / 3.3.6 / 1.20.0 |
| NumPy / SciPy / tzdata | 2.5.3 / 1.18.1 / 2026.5 |
| PostgreSQL | 16.14 (Debian 16.14-1.pgdg13+1), contenedor Linux |

Se conserva el aviso conocido de deprecación de HTTPX en TestClient. Las
dependencias coincidieron entre ambas corridas nativas y no se modificaron.

## Evidencias y SHA-256

| Archivo | Bytes | SHA-256 |
|---|---:|---|
| `fase8-entrega-v2.zip` | 465842 | `4841ad9bc7e90233b110cfe95f5bda6a6a9682976400ebbc6994fab48ee212d4` |
| `fase8-api-publica-v2.patch` | 193415 | `8013cdb0054570d8dd7f35abdcc13ff49d5d0f174731e31f7112271354c741c6` |
| `f8-validacion-v2-0e73c2b4.zip` | 101082 | `c1a5d7a7375b047e0f9a08729ee8cbe11502904b7d320ae15f6d5ac16f50358e` |
| `f8-postgresql-v2-bc5755d7.zip` (primer intento del supervisor) | 2220 | `542bbb33f9a5fa988129fdcce9871ce94530a256aa22d9b5cb7f1a223eb42861` |
| `f8-postgresql-v2-1ee1f63f.zip` (r1, aprobado) | 11738 | `fbe901a5e70782ec3d69ae767115d837878bc66a87070deda16a451196ff3381` |

El primer ZIP nativo contiene el JUnit de las 92 pruebas, las cuatro sondas,
el inventario de los 784 archivos y las 30 rutas originales. El ZIP de
PostgreSQL r1 contiene 17 entradas verificadas por manifiesto, además del
propio manifiesto: resultados A–F/A2, base vacía, migraciones, datos finales,
registros de Uvicorn y PostgreSQL, versiones y metadatos operativos.

La aplicación del cierre es documental: no ejecuta pruebas ni PostgreSQL.
La auditoría del cierre verificó los dos controles existentes de alineación
del arranque soportado y de la selección de Windows; las 92 pruebas completas,
las cuatro sondas y PostgreSQL conservan sus corridas previas.
Se mantienen `experimental_no_acreditado`, AE-39 **NO-GO** y
`AUTORIZA_EVALUACION = False`. Esta validación de ingeniería no acredita
ventaja predictiva ni rendimiento futuro. Los pendientes de Fase 10 incluyen
HTTPS, proxies fiables, operación y disponibilidad; Fase 11 conserva su orden.
