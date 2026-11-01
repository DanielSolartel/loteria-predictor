# Issue #103: descripciones HTTP 422 del OpenAPI público

Investigación y validación de mantenimiento previa a la Fase 10, sobre `49689bb6976cfedefea791e7ef20ba5c3ad70565` (merge del PR #106; árbol `5294d6b0b7422fe345263d79cd90a10411421e9c`, 1045 archivos). La Fase 9 sigue cerrada en su alcance acordado. Este documento **no cambia** la API, el OpenAPI versionado, los tipos, las dependencias, los modelos, los históricos ni la operación de la Fase 6. La salvedad documental de la 9.4 ([guía de API](fase8_api_publica.md#cierre-de-validación-94-salvedad-documental-de-http-422)) conserva su texto y su atribución.

**Estado vigente (2026-11-01):** la validación nativa Windows y la auditoría de Codex están completadas, y la vía A queda validada.

- **Fuente validada:** la v2 del comparador, con el árbol `bf326bd7b873b46ab43a111b06beb104df8e2972` y 1048 archivos.
- **Pendientes:** la publicación manual, la integración, el CI y el cierre manual del issue en GitHub. Este cambio todavía no tiene PR ni merge.
- **Fases:** la Fase 9 sigue cerrada en su alcance de consulta y la Fase 10 aún no comienza.

## Entradas verificadas

| Entrada | Bytes | SHA-256 |
|---|---|---|
| `f94-reanudacion-v2-f758ca05.zip` (evidencia nativa original de Daniel) | 55.662 | `245c6185ce411cafc20507de9f560b818fc11ff15e1b7087662852c5f39ac326` |
| `openapi/openapi-versionado.json` del ZIP, igual a `frontend/src/api/openapi.json` | 201.622 | `e8c879b4c329defa329915b215b64ede55cd5f05e3c87e6a8378be342ba181a5` |
| `openapi/openapi-generado.json` del ZIP (Windows nativo, `win32`) | 201.627 | `c03e5c523f09522960a358a8382326f10b774a6bea22333a89c0c9344ccf85aa` |

El entorno nativo del ZIP (`versiones-python-conservadas.log`, dato histórico de la 9.4) es Python 3.14.6 en `win32`, con FastAPI 0.162.0, Starlette 1.10.0 y Pydantic 2.14.1. Su `comparacion.json` (versión `f94-openapi-documento-completo/1`) informa cinco diferencias, sin campos excluidos, con `codigo` 1.

## Las cinco diferencias

Todas son de clase `valor` en `get/responses/422/description`:

| Ruta | Versionado | Generado |
|---|---|---|
| `/api/v1/juegos/{codigo}/modelos-guardados` | `Unprocessable Entity` | `Unprocessable Content` |
| `/api/v1/juegos/{codigo}/modelos-guardados/{clave}` | `Unprocessable Entity` | `Unprocessable Content` |
| `/api/v1/juegos/{codigo}/carteras-guardadas` | `Unprocessable Entity` | `Unprocessable Content` |
| `/api/v1/juegos/{codigo}/carteras-guardadas/{clave}` | `Unprocessable Entity` | `Unprocessable Content` |
| `/api/v1/juegos/{codigo}/resultados` | `Unprocessable Entity` | `Unprocessable Content` |

### Causa

**Hechos demostrados:**

1. **Origen del texto.** `app/api/publica/guardados.py` declara `_ERRORES = {s: {"model": ErrorRespuesta} …}` sin `description`, y las cinco rutas lo usan. Cuando una respuesta declarada no tiene descripción, FastAPI 0.162.0 toma `http.client.responses[estado]` (`fastapi/openapi/utils.py`, línea 500). Las otras 11 respuestas 422 del documento no dependen de ello: 9 fijan «Parámetro no válido» (`rutas.py`) y 2 usan el texto fijo de FastAPI «Validation Error».
2. **La leyenda depende de la versión de CPython y no del sistema operativo.** La biblioteca estándar da «Unprocessable Entity» en 3.11.17 y 3.12.3, y «Unprocessable Content» en 3.13.17 y 3.14.6 (Linux). Las leyendas de 401, 404, 409, 429 y 503, que esas rutas también toman de la biblioteca estándar, son iguales en las cuatro versiones.
3. **Linux reproduce Windows byte a byte.** En Linux, con Python 3.14.6 y las mismas versiones de FastAPI, Starlette y Pydantic, el exportador versionado genera 201.627 bytes con SHA-256 `c03e5c52…`, idénticos al documento nativo Windows.
4. **Es la única entrada que varía.** En ese mismo proceso Linux, sustituir solo `http.client.responses[422]` por «Unprocessable Entity» produce 201.622 bytes con SHA-256 `e8c879b4…`, idénticos al versionado.

**Hipótesis (no demostrada):** el versionado se generó con CPython 3.12 o anterior. Es coherente con los hechos, pero no hay registro del intérprete que lo produjo. No se atribuye la variación a Windows.

### Compatibilidad

- **Qué cambia:** solo el texto documental `description`.
- **Qué no cambia:**
  - el código 422;
  - el esquema `ErrorRespuesta` y el cuerpo real de error;
  - las rutas, los métodos, los parámetros, las restricciones y la seguridad.
- **Tipos del frontend:** las cinco frases aparecen en `frontend/src/api/esquema.d.ts` solo como comentarios `@description`; los tipos no cambian.
- **Control de deriva:** `tests/unit/pasarela/test_pasarela_contrato.py` compara una proyección contractual que no incluye descripciones, por eso el CI (Python 3.14) sigue verde. En cambio, `scripts.exportar_openapi_publica --comprobar` compara texto de forma estricta y, con CPython ≥ 3.13, sale con 1 («openapi: DISTINTO»). Ese comportamiento se conserva sin cambios.

## Comparador del documento completo

**Comparador previo:** el que usó el auditor en la 9.4 (y que registró `cinco_descripciones_422_auditadas_aceptadas=true`) es **externo**: no está en el repositorio ni en el ZIP. El ZIP solo trae su resultado `f94-openapi-documento-completo/1`, que rechaza.

**Comparador nuevo:** para que el cotejo sea reproducible se añade `backend/scripts/comparar_openapi_publica.py` (`issue103-openapi-comparador/2`). Es solo lectura, no escribe en el repositorio y no sustituye al exportador. Con `--generado` solo usa la biblioteca estándar.

- **Lectura estricta (v2):** antes de comparar, cada texto debe ser UTF-8 y JSON válido.
  - Una clave repetida en un mismo objeto, a cualquier profundidad, invalida la entrada. No se elige ninguna de las dos apariciones.
  - `NaN`, `Infinity` y `-Infinity` no son JSON e invalidan la entrada.
  - Una entrada no válida produce un informe `entrada_no_valida` con el puntero de cada problema y el código 3, sin traza ni comparación. No declara compatibilidad.
- **Igualdad textual:** bytes idénticos (`texto_igual`).
- **Igualdad semántica:** mismo JSON (`documentos_json_iguales`). Solo ignora el formato y el orden de claves de los objetos. Las listas se comparan por posición y longitud.
  - **Tipos:** se distinguen exactamente. `1` es entero, `1.0` o `1e2` son números con parte decimal o exponente, y `true` es booleano: son valores distintos.
  - **Números (v2):** se comparan por su valor decimal exacto, leído del texto original y nunca convertido a `float`. `1.0` y `1.00` son el mismo número. En cambio, `1.0000000000000000` y `1.0000000000000001`, o `1e400` y `2e400`, son distintos.
- **Sin exclusiones:** `campos_excluidos` es siempre `[]` y ninguna descripción se ignora.
- **Única excepción:**
  - Solo esos cinco punteros exactos, con «Unprocessable Entity» en el versionado y «Unprocessable Content» en el generado.
  - Cuando el documento se genera en el mismo proceso, la leyenda 422 del intérprete también debe ser «Unprocessable Content».
  - La excepción **no** declara iguales los documentos: el informe mantiene `documentos_json_iguales=false` y conserva las cinco diferencias.
- **Rechazos:** cualquier otra diferencia, la dirección inversa, una sexta ruta con el mismo par de leyendas o una leyenda runtime distinta.
- **Clasificaciones:**
  - `identicos_texto`;
  - `iguales_json_formato_distinto`;
  - `solo_excepcion_422_auditada`;
  - `diferencias_no_aceptadas`.
  - `entrada_no_valida` (v2).
- **Códigos de salida:** 0 para las tres primeras clasificaciones, 1 para `diferencias_no_aceptadas` y 3 para `entrada_no_valida`.
- **Informe (v2):** los números se escriben con su literal original, sin redondear. Cada diferencia lleva sus tipos explícitos (`tipos` o `tipo`) y, si hay números, sus `literales` como texto.
- **Salidas:** `comparacion.json`, `diferencia-texto.diff` y, si genera el documento, `openapi-generado.json` con su entorno (Python, plataforma, FastAPI, Starlette, Pydantic y leyenda 422), todo en una carpeta nueva que nunca se sobrescribe.

**Pruebas y controles negativos:** `tests/unit/pasarela/test_openapi_comparador.py` contiene 97 pruebas: las 60 de v1 sin cambios y 37 regresiones v2. Mutan copias en memoria y no tocan el versionado. Incluyen 25 mutaciones, cada una sola y sobre la excepción, que se rechazan:

- rutas o métodos añadidos o quitados;
- la seguridad de una operación o del esquema;
- los parámetros (patrón, máximo, obligatorio, orden y eliminación);
- los esquemas (tipo, `required`, propiedades y `additionalProperties`);
- las respuestas y el esquema de la 422;
- las descripciones de otras respuestas, operaciones, parámetros o esquemas;
- `info.version`;
- tipos numéricos y booleanos.

**Regresiones v2:** parten de **textos JSON literales**, porque un diccionario serializado no puede contener una clave duplicada ni un literal que `float` no distinga. Cubren:

- claves duplicadas a cualquier profundidad, en uno o en ambos documentos, incluida una `security` duplicada sobre la excepción;
- `NaN`, `Infinity` y `-Infinity` en cada documento;
- texto no JSON y UTF-8 no válido;
- números que `float` confunde (`1.0000000000000000`/`1.0000000000000001`, `±1e400`/`±2e400`, `1e-400`/`2e-400` y `0.1`/`0.10000000000000001`) y un entero largo;
- la misma cifra escrita de otro modo y la distinción entre entero, real, booleano y texto;
- el informe exacto, la CLI con código 3 sin traza y la excepción histórica leída desde texto.

Una prueba adicional genera el documento con el intérprete en curso y exige `identicos_texto` con CPython ≤ 3.12, o exactamente la excepción con ≥ 3.13. La carpeta `tests/unit/pasarela` ya está en el CI y en `tests/seleccion_windows.txt`, así que esas pruebas también corren en Windows sin tocar la selección.

## Procedimiento reproducible

Ejecútalo desde `backend/`, con el entorno del proyecto y una carpeta de salida nueva.

**Prerrequisito:** un entorno de pruebas con `httpx`.

- **Por qué:** las pruebas de la pasarela usan `TestClient`, que necesita `httpx`, y `httpx` no es una dependencia declarada.
- **Cómo lo hace el CI:** instala `httpx==0.28.1` aparte de `requirements.txt`.
- **Sin él:** la ejecución se detiene antes de las pruebas.
- **Requisitos:** este procedimiento no los cambia.

**Linux:**

```
python -E -s -B -m scripts.comparar_openapi_publica --versionado ../frontend/src/api/openapi.json --salida ../salidas/i103-$(date -u +%Y%m%dT%H%M%SZ)
python -E -s -B -m scripts.comparar_openapi_publica --versionado <versionado.json> --generado <generado.json> --salida <carpeta nueva>
python -B -m pytest -p no:cacheprovider -q tests/unit/pasarela/test_openapi_comparador.py tests/unit/pasarela/test_pasarela_contrato.py
python -B -m scripts.exportar_openapi_publica ../frontend/src/api/openapi.json --comprobar
```

**Windows (PowerShell 5.1):**

```
$salida = "..\salidas\i103-" + (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
python -E -s -B -m scripts.comparar_openapi_publica --versionado ..\frontend\src\api\openapi.json --salida $salida
python -B -m pytest -p no:cacheprovider -q tests\unit\pasarela\test_openapi_comparador.py tests\unit\pasarela\test_pasarela_contrato.py
python -B -m scripts.exportar_openapi_publica ..\frontend\src\api\openapi.json --comprobar
```

**Resultados esperados:**

| CPython | Comparador | Pruebas afectadas | `--comprobar` |
|---|---|---|---|
| ≤ 3.12 | `identicos_texto`, código 0 | 101 aprobadas | 0, «openapi: igual» |
| ≥ 3.13 | `solo_excepcion_422_auditada`, 5 aplicadas, `documentos_json_iguales=false`, código 0 | 101 aprobadas | 1, «openapi: DISTINTO» (esperado, sin cambios) |

- **Qué se ejecutó:** ver el detalle por entorno en la [validación nativa y auditoría](#validación-nativa-y-auditoría-completadas).
  - **Fila ≥ 3.13:** con 3.14.6 en Linux Cloud (Claude) y en Windows nativo (Daniel).
  - **Fila ≤ 3.12:** la ejecutó el auditor en Linux con 3.12.14, así que ya no es solo una deducción. En la copia Linux de Claude no se instaló el proyecto con esa versión; ahí 3.12.3 solo ejecutó la sonda.
- **Saltos de línea:** el versionado tiene finales LF. Si una copia Windows lo convierte a CRLF, el texto deja de coincidir, pero el JSON no cambia. En ese caso, el comparador clasifica según el contenido, y `--comprobar` no se ve afectado porque lee con traducción de saltos de línea.
- **Otros resultados:** cualquier otro resultado es un hallazgo. Revisa `diferencias_no_aceptadas` en `comparacion.json` o, con el código 3, `problemas`.

## Validación realizada (Linux Cloud)

**Corrección v2:** la auditoría de Codex sobre v1 encontró dos bloqueos en la lectura del JSON.

- **I103-ROB-01:** v1 aceptaba claves duplicadas y constantes no JSON.
- **I103-ROB-02:** v1 declaraba iguales números distintos por convertirlos a `float`.

Las sondas originales del auditor reprodujeron los cuatro defectos sobre v1 (5/5 en modo `antes`). Sobre v2, en modo `despues` y con CPython 3.14.6 y 3.12.3, dan 5/5:

- los dos casos no válidos se rechazan con el código 3, sin traza;
- los dos cambios numéricos se rechazan con el código 1, registrados como diferencias;
- el control histórico sigue aceptado, con sus cinco diferencias.

La explicación de las cinco descripciones 422 no cambia.

- **Pruebas afectadas** (`test_openapi_comparador.py` y `test_pasarela_contrato.py`, en una copia desechable):
  - 101 aprobadas: 97 del comparador y 4 del contrato existente, sin cambios.
  - Las pruebas v2 ejecutadas contra el comparador v1 dan 28 fallos, por la aceptación de entradas no válidas, la pérdida numérica y los campos nuevos del informe.
    - **Fuente del recuento:** la consola de esa ejecución. Su JUnit empaquetado está mal formado y no sirve como evidencia de aprobación; ver la [observación de auditoría](#validación-nativa-y-auditoría-completadas).
  - Se ejecutan solo estas porque el cambio añade un script y su prueba en `tests/unit/pasarela`, y no toca el producto.
- **Exportador estricto `--comprobar`:** código 1, «openapi: DISTINTO», como se esperaba con Python 3.14.6. Se ejecutó en v1; v2 no lo modifica.
- **Comparador:**
  - Sobre la generación Linux 3.14.6 y sobre los dos documentos del ZIP nativo: `solo_excepcion_422_auditada`, 5 aplicadas, 0 no aceptadas y código 0.
  - Con el ZIP, `leyenda_runtime` no es verificable, porque los archivos ya estaban generados.
- **Controles de mutación del comparador:**
  - **En v1:** detectaron sus 7 relajaciones (ignorar descripciones, listas sin orden, tipos laxos, cualquier 422, no verificar la leyenda runtime, aceptar la dirección inversa y cualquier valor en las cinco rutas). La primera pasada no detectó «cualquier 422»; se añadió la prueba de la sexta ruta y la segunda pasada detectó las 7.
  - **En v2:** se detectan esas 7, trasladadas con el mismo alcance, y 7 nuevas: admitir duplicadas, buscarlas solo en la raíz, admitir constantes no JSON, leer números con `float`, redondear el informe, omitir los tipos y no usar un código propio para el rechazo.

## Validación nativa y auditoría completadas

**Cada resultado pertenece a su entorno:** los recuentos no se suman entre entornos. Las 101 pruebas son los mismos casos ejecutados en cada uno.

| Entorno | Quién y cuándo | Python y paquetes | Resultado |
|---|---|---|---|
| Histórico 9.4, Windows nativo | Daniel, validación de 9.4 (ZIP `f758ca05`) | 3.14.6 `win32`; FastAPI 0.162.0, Starlette 1.10.0, Pydantic 2.14.1 | Generado `c03e5c52…` con las cinco diferencias; cotejo con el comparador externo de la 9.4 |
| Linux Cloud | Claude, 2026-11-01 | 3.14.6; FastAPI 0.162.0, Starlette 1.10.0, Pydantic 2.14.1. La sonda también se ejecutó con 3.12.3 | Ver la [validación realizada](#validación-realizada-linux-cloud) |
| Linux, auditoría v2 | Codex, 2026-11-01 | 3.12.14; FastAPI 0.162.0, Starlette 1.10.0, Pydantic 2.14.1, pytest 9.1.1 | 101 aprobadas; generación real idéntica en texto al versionado (201.622 bytes, `e8c879b4c329defa329915b215b64ede55cd5f05e3c87e6a8378be342ba181a5`); `--comprobar` 0 |
| Windows nativo, v2 | Daniel, 2026-11-01, 22:46:14–22:47:01 UTC | PowerShell 5.1.26100.9711; 3.14.6 `win32`; FastAPI 0.162.0, Starlette 1.10.0, Pydantic 2.14.2, pytest 9.2.0, SQLAlchemy 2.1.6 | Ver la lista siguiente |

La corrida Windows v2 usa Pydantic 2.14.2 y genera exactamente el mismo documento. El dato histórico de la 9.4 (Pydantic 2.14.1) no se sustituye.

**Resultados Windows nativo v2** (evidencia `i103-reanudacion-r1-c5a59ae8.zip`, 399.989 bytes, SHA-256 `d68bc5b7cc964dbfe708aab932204c2fb3241bed3de80b04e01b9641c5872cab`):

- **Pruebas:** 101 aprobadas, 97 del comparador y 4 del contrato existente, sin fallos, errores ni omitidas.
- **Sonda original de Codex:** sin modificar, 5/5 en modo `despues`.
  - El control histórico se acepta con código 0.
  - La `security` duplicada y la constante `Infinity` se rechazan con código 3, `entrada_no_valida`.
  - Los dos cambios numéricos se rechazan con código 1, con literales y tipos exactos.
  - Las entradas quedan intactas y no hay trazas.
- **Comparador sobre la generación real:**
  - clasificación `solo_excepcion_422_auditada`, con 5 aplicadas y ninguna diferencia no aceptada;
  - `campos_excluidos=[]` y `documentos_json_iguales=false`;
  - leyenda runtime verificada.
- **Generado:** 201.627 bytes, SHA-256 `c03e5c523f09522960a358a8382326f10b774a6bea22333a89c0c9344ccf85aa`.
- **Exportador estricto, sin cambios:** código 1, el esperado, con `openapi: DISTINTO`.
- **Conservación:**
  - **Fuente:** las 1048 huellas coinciden con el inventario v2.
  - **Copia de pruebas y clon de origen:** el código, el índice y las referencias se conservan.
  - **Reanudación:** no repitió la clonación ni la aplicación del parche.

**Auditoría de Codex sobre la evidencia nativa:**

- **Dictamen:** validación nativa aprobada.
- **Método:** fue una lectura de evidencia; no repitió las pruebas del producto.
- **Lo que verificó:** el CRC y las 1048 huellas, y que las 101 identidades de casos fueran únicas.
- **Contraste independiente:** comparó el versionado con el generado nativo sin usar el comparador del producto. Encontró exactamente los cinco cambios Entity → Content y ningún otro cambio de valores, tipos, listas o claves.
- **Lectura de los límites numéricos:** los leyó con `Decimal`.

**Incidencia de supervisión, resuelta fuera del repositorio:**

- **Qué pasó:** la primera validación nativa se detuvo al consultar metadatos, antes de ejecutar la sonda y las pruebas, porque el entorno de revisión no tenía `httpx`. Su evidencia, `i103-validacion-v2-7c700c8c.zip` (269.010 bytes, SHA-256 `1e8ab7d63e08bd08f4fad01eaac79b49a2359708a936046cf2f1b41ba3edaa64`), se conserva sin cambios.
- **Cómo se reanudó:** con un entorno auxiliar que lee los paquetes del existente. Solo en ese auxiliar se instalaron `httpx` 0.28.1, `httpcore` 1.0.9 y `h11` 0.16.0.
- **Entorno original:** sigue sin `httpx`. Sus metadatos y su `pyvenv.cfg` coinciden antes y después; no se comprobaron byte a byte todos sus binarios.
- **Repositorio:** no se incorporan supervisores, entornos, archivos `.pth`, XML nativos ni ZIP de ejecución. Los requisitos no cambian.

**Observación de auditoría conservada:**

- **El defecto:** en el ZIP v2 de Claude, `evidencias/regresiones-v2-sobre-v1/junit.xml` (las pruebas v2 contra el comparador v1, en rojo) es XML mal formado. Al sanear las trazas se insertó la etiqueta `<python-uv>` sin escapar.
- **Qué se hace:** no se repara ni se reescribe, y no se usa como evidencia de aprobación.
- **Lo que acredita lo necesario:** la sonda original ejecutada de nuevo sobre v1, en rojo, y los JUnit válidos de las 101 aprobadas.

## Decisión propuesta

**Vía A, validada:**

- Se conservan la API, el OpenAPI versionado y los tipos.
- Se adoptan el comparador acotado y sus pruebas, como procedimiento reproducible de la salvedad 9.4.
- El exportador `--comprobar` sigue siendo estricto.
- **Cierre del issue #103:** la validación nativa y la auditoría ya están completadas. El cierre llega después de la publicación manual, la integración y el CI, y se hace a mano en GitHub.

**Alternativa (B), sin aplicar, solo como propuesta separada para revisión previa:**

- Fijar `description` en la 422 de `_ERRORES` de `guardados.py` para que la generación no dependa de la versión de CPython.
- Exige regenerar el OpenAPI versionado y los comentarios de `esquema.d.ts`, por lo que **no se aplica aquí**.
- Se presenta en un documento aparte de la entrega del issue.

## Validación nativa (Daniel): completada

Estos eran los pasos previstos; se cumplieron como recoge la [validación nativa y auditoría](#validación-nativa-y-auditoría-completadas).

1. Sobre la fuente con este parche, en Windows nativo y PowerShell 5.1: ejecutar los tres comandos de Windows del procedimiento (versión v2 del comparador) y conservar la carpeta de salida, la consola y `python --version`.
2. Comprobar que el resultado coincide con la fila de su versión de CPython en la tabla de resultados esperados.
3. Con CPython 3.14.6, confirmar que `openapi-generado.json` vuelve a tener SHA-256 `c03e5c52…`, o registrar la nueva huella y la clasificación si cambian las dependencias.
4. Entregar la evidencia a Codex para su auditoría. La publicación y el cierre del issue son manuales.

## Limitaciones conservadas

- **Lo que no prueba la reproducción Linux:** acredita la causa, pero no sustituye a la validación nativa. Los resultados Linux de Claude o de Codex no se atribuyen a Windows, y la validación Windows es de Daniel.
- **Pendientes:** la publicación manual, la integración, el CI y el cierre manual del issue en GitHub.
- **Salvedad documental de la 9.4:** sigue vigente con su atribución.
- **Estados vigentes:** se mantienen `experimental_no_acreditado`, AE-39 **NO-GO** y `AUTORIZA_EVALUACION = False`.
- **Qué no se ejecutó:** las suites completas, Vitest, Brave, PostgreSQL, SQL operativo, el Programador, los ciclos, Actions ni ningún despliegue.
- **Fases:** la Fase 9 sigue cerrada en su alcance de consulta y la Fase 10 aún no comienza.
