# Fase 10 — E10.4: generaciones, captura coherente, importación, validación y respaldos

Estado (2026-11-04): **implementado y demostrado en Linux con PostgreSQL 16 y datos sintéticos**. Base: `main`
`4aa24b85` (PR #109 integrado). La Fase 10 **no** está cerrada.

- **Método de captura (D10):** diseñado, implementado y validado con los escenarios C1–C10 de la enmienda 01
  sobre PostgreSQL real. **No está aprobado para datos reales:** D10 sigue pendiente de Daniel.
- **F10-DAT-02:** la propuesta quedó cumplida en el entorno sintético, pero **sigue abierto** hasta que Daniel
  apruebe el uso real (sección 13). El uso real está **bloqueado** en la CLI.
- **Windows:** la captura en el PC y la recuperación operativa R-W quedan **pendientes** de su ensayo nativo
  autorizado. Nada de esta entrega se ejecutó en Windows.
- **Lo que no cambia:** no se pausa Fase 6, no se toman sus cerrojos y no se modifica la tarea
  `LP6-01023009031fcabd`. Se conservan `experimental_no_acreditado`, AE-39 NO-GO y `AUTORIZA_EVALUACION = False`.
- **Grype:** la aceptación temporal de 16 avisos (PR #109, opción B) es solo de vulnerabilidades; no autoriza el
  protocolo B de captura.

Prevalece la enmienda 01 de la propuesta v2 (§3.4–3.5 y D2/D3/D4/D12) sobre los textos que sustituye.

## 1. Piezas

| Pieza | Dónde | Qué hace |
|---|---|---|
| Matriz de datos (DAT-01) | `app/infrastructure/generaciones/inventario.py` | Clasifica cada `DIRECTORIO_*`: publicable, interno, operativo; los transitorios y secretos nunca se copian |
| Volcado lógico | `base_logica.py` | Lee la base desde una instantánea `REPEATABLE READ`, calcula la huella de contenido y la de versiones de fila (`xmin`), la huella del esquema y restaura de forma exacta. No usa `pg_dump` |
| Fotografía de archivos | `archivos.py` | Inodo, tamaño, `mtime_ns` y `ctime_ns` de cada archivo y carpeta; copia verificada; reservas huérfanas |
| Escritores vivos | `escritores.py` | Cerrojos `.activo`, ejecuciones con trabajador, registros `en_curso`, advisory y transacciones que ya escribieron. **Solo observa** |
| Coherencia cruzada | `coherencia.py` | Comprueba el histórico de entrada y las referencias por tipo de artefacto con los **lectores de la aplicación** |
| Captura y sellado | `captura.py` | Método `observacion-doble-e104/1`, manifiesto firmado con Ed25519 y alerta `captura_rechazada` |
| Verificación | `verificacion.py` | Firma, identidad, conjunto exacto de archivos, huellas y coherencia |
| Importador | `importacion.py` | Preparación aislada, validación completa, aceptación o rechazo seguro y activación explícita |
| Consultas DAT-04 y R-L | `consultas.py` | 19 endpoints × 4 juegos más las tres procedencias, con criterios de contenido |
| Respaldo | `respaldo.py` | Cifrado, verificación, restauración aislada (R-L) y retención |
| Perfil privado ligado | `app/api/publica/perfil_privado.py` | `GENERACION_DIRECTORIO`: un proceso, una generación |
| CLI | `scripts/generaciones.py` | Órdenes `claves-*`, `capturar`, `verificar`, `importar`, `activar`, `respaldar`, `verificar-respaldo`, `restaurar` y `retener` |
| Roles SQL | `despliegue/generaciones/postgres/` | `generaciones_importador` (CREATEDB, sin superusuario) y `generaciones_captura` (solo lectura y `pg_read_all_stats`) |
| Demostración | `despliegue/generaciones/demostracion_e104.py` | De extremo a extremo con PostgreSQL y archivos sintéticos (sección 11) |

No se añaden dependencias: `cryptography`, `psycopg`, `alembic` y `sqlalchemy` ya estaban en los locks. No hay
migraciones nuevas ni cambios en la estructura de la base que usa Fase 6.

## 2. Requisito 1: escritores y cobertura

Capas del método (sección 3):

- **L1, archivos:** fotografía idéntica en t1 y t4 de TODOS los árboles observados, publicables y operativos.
- **L2, base:** las versiones de fila (`xmin` y contenido) de **todas** las tablas son idénticas en la instantánea
  t2 y en una transacción nueva en t4.
- **L3, evidencia viva:** en t0 y en t4.
- **L4, coherencia cruzada.**

| Escritor | Escribe | Cobertura | Evidencia |
|---|---|---|---|
| CRUD de sorteos y colores (consola web y REST, protegidos por E10.1) | `sorteos`, `sorteo_*` y `colores`, con advisory de transacción por juego | L2 (cualquier confirmación en la ventana); L3 (advisory o `xid` abierto) | C1, C2 |
| Importación y reimportación web/CLI y reproceso HTML | `sorteos` y tablas hijas | L2, L3 | C1, C2 |
| Sincronización: ciclo de Fase 6 y `scripts.operacion_automatica` | `sorteos` y `sincronizaciones`, con advisory de **sesión** por juego; `automatizacion/` | L3 (advisory de sesión), L2, L1 | C4 (advisory), C3 |
| Caché de estadísticas (GET de la consola) | `estadisticas` | L2: un GET de la consola durante la ventana provoca un **reintento** | C2/C3 (cualquier tabla) |
| Simulaciones de Fase 7 | tabla `simulaciones` y `simulaciones/operacion/` | L2, L1, L3 | C3, C4 |
| Tablas `modelos`, `metricas_modelo` y `predicciones` | sus tablas | L2 | C2/C3 (cualquier tabla) |
| Migraciones de Alembic | esquema y `alembic_version` | L2. Además, la revisión de la base debe ser la del código que captura | — |
| SQL externo (psql y otras herramientas, cualquier rol) | cualquier tabla | L2 (lo confirmado); L3 (`xid` abierto, visible con `pg_read_all_stats`) | C1 |
| Producto 1 y operación diaria (Producto 3) | `pronosticos/` y `operacion/` (registro y cerrojos) | L1, L3 (`.activo`, `ejecuciones/*.json` `en_curso`) | C4 (CLI en curso) |
| Laboratorio (Producto 4, procesos trabajadores) | `laboratorio/{experimentos,pronosticos,modelos}` y `operacion/` | L1, L3 | C4 (cerrojo de trabajador) |
| Carteras y configuraciones (Producto 5) | `carteras/*` | L1, L3 | C4, C5 |
| Predicciones y explicaciones (Fase 4) | `predicciones/` | L1, L3 | C7 (productor real) |
| Informes (Producto 6) | `resultados/` (interno) | L1 | — |
| Automatización de Fase 6 (`actualizar_configuracion`, `guardar_estado`, ciclos y propuestas) | `automatizacion/` | L1, L3 (`ciclos/cerrojos/*.activo`) | C5 |
| Cuentas y sesiones de la consola (E10.1, D12) | `privado/consola` | **Fuera de alcance:** secreto, ni se lee ni se copia; la captura se rechaza si un almacén lo contiene | `_validar_raices` |
| HTML de las fuentes (`storage/html`) | archivos de reproceso | No es publicable y no entra en la generación ni en este respaldo (la v2 lo deja opcional); su efecto en la base lo cubre L2 | — |

**Límite declarado:** un proceso que no tome ningún cerrojo, no tenga ningún `xid` abierto y deje un estado
intermedio **fuera** de la base y de los árboles observados no se detecta. En la base actual no existe ningún
escritor así: todos usan los cerrojos de Productos 3–5, Fase 4, Fase 6 o Fase 7, o confirman en una sola
transacción.

## 3. Requisitos 2 y 3: corte conjunto y observación final independiente

**Definición:** la generación representa el estado de la base y de los archivos en **un mismo instante t2**, y
ese estado se mantuvo idéntico durante toda la ventana de captura.

Pasos de cada intento (sin barrera ni pausa):

1. **t0:** evidencia viva. Si hay alguna, el intento se rechaza.
2. **t1:** fotografía de los árboles.
3. **t2:** transacción `REPEATABLE READ READ ONLY` y `pg_export_snapshot()`. En ella se leen el catálogo, la
   huella del esquema, la revisión de Alembic, los últimos sorteos y el volcado con sus huellas.
4. **t3:** copia verificada de los archivos fotografiados en t1. La coherencia cruzada se calcula contra la
   **misma** instantánea, que otra conexión importa con `SET TRANSACTION SNAPSHOT`.
5. **t4:** **transacción y conexión nuevas**, con su propia instantanea, para las huellas de versiones de todas
   las tablas; fotografía nueva; evidencia viva otra vez.

Se sella solo si L1, L2, L3 y L4 se cumplen.

**Garantías en las que se apoya:**

- **PostgreSQL 16:**
  - una transacción `REPEATABLE READ` ve una instantánea fija de lo confirmado;
  - una instantánea exportada se puede importar en otra conexión;
  - cada inserción o actualización confirmada crea una versión de fila con su `xmin`, y un borrado retira una
    versión visible.
- **Lo que detecta L2:** la igualdad de `(xmin, contenido)` en t2 y t4 excluye cualquier confirmación en la
  ventana:
  - también la de una transacción **iniciada antes** de t2 que confirma después (C1): sus versiones aparecen en
    t4 con su propio `xmin`;
  - y la de un cambio que **no altera recuentos ni máximos de `id`**, ni siquiera el contenido (C2).
- **POSIX:**
  - `st_ctime` cambia con cualquier cambio de contenido o metadatos y un proceso sin privilegios no puede
    fijarlo;
  - una carpeta cambia al crear, borrar o renombrar entradas. Por eso L1 detecta también la reescritura con el
    mismo contenido y la restauración de `mtime` (ABA), y un alta seguida de baja (pruebas
    `test_archivos_inventario`).

**La observación final no es la instantánea congelada.** La prueba C3 demuestra que la misma transacción
`REPEATABLE READ` sigue viendo el estado anterior tras un cambio confirmado, mientras que la observación
independiente sí lo ve. **No se usa** `pg_snapshot_xmax`, ningún recuento ni ningún máximo de `id` (F10-CAP-01).

**Qué no detecta:**

- un cambio deshecho por completo **antes de t1** (no forma parte de la ventana: es el pasado);
- un cambio del reloj del sistema hacia atrás o una escritura como superusuario con el mismo `ctime`;
- **en Windows**, `st_ctime` es la fecha de creación: L1 se apoya en el tamaño, `mtime` y el índice del archivo,
  y queda **pendiente** de su validación nativa. El manifiesto declara `deteccion_de_archivos`.

## 4. Requisito 4: coherencia temporal por tipo de artefacto (F10-CAP-02)

Los almacenes se recorren con **sus propios lectores**, los mismos que usa la API: bytes canónicos, sello,
huella, clave, ubicación y, en los modelos, el estimador `.pkl` **rehasheado sin deserializarlo**. Un
`Ilegible` se cuenta y se conserva.

| Tipo (esquema) | Entrada que se verifica | Referencias | Objetivo |
|---|---|---|---|
| Pronóstico experimental (`pronostico-experimental/1`, `storage/pronosticos`) | `datos.corte` presente en la instantánea de su juego y al menos `datos.sorteos` sorteos hasta el corte; huella con `huella_del_historico` de Producto 1 (ColorLoto, la suya) | — | Se registra y no se limita |
| Experimento del laboratorio (`laboratorio-experimento/1`) | Igual, con la huella de `Instantanea` del laboratorio | — | — |
| Pronóstico del laboratorio (`laboratorio-pronostico/1`) | Igual | su experimento | No se limita |
| Modelo registrado (`laboratorio-modelo/1`) | Igual (`datos` o `identidad`) | su experimento; el estimador lo comprueba su lector (`estimador_ausente`/`alterado`) | — |
| Cartera (`carteras-cartera/1`) | Igual | su modelo registrado, si lo declara | **`objetivo = corte + 1`: se publica** (C7) |
| Comparación y simulación de carteras | Igual | — | — |
| Configuración (`carteras-configuracion/1`) | Sin histórico propio | — | — |
| Explicación (`predicciones-explicacion/1`) | `cartera.corte` de su cartera | su cartera, con la **misma** huella de histórico | Igual que su cartera |

**Reglas:**

- **Histórico de entrada ausente:** si falta el sorteo `corte`, o hay menos sorteos hasta el corte de los
  declarados, se **rechaza la captura entera** (C8). No se filtra nada ni se reintenta (C9).
- **`cambio` y `no_valido`:** se publican con su estado, el mismo que muestra la aplicación.
- **El objetivo no es entrada:** borrar solo el sorteo objetivo no rechaza nada (prueba
  `test_c7_borrar_solo_el_sorteo_objetivo…`).

## 5. Requisito 5: exclusión y espera

**No hay barrera.** No se pausa Fase 6 ni se toman sus cerrojos o advisory; la captura solo observa.

**La espera es acotada:**

- `--intentos` (3), `--espera` (30 s) y `--plazo` total (900 s);
- tras agotarlos se escribe la alerta `captura_rechazada` y no hay generación nueva.

**Efectos operativos:**

- **Sobre Fase 6:** ninguno.
- **Sobre la captura:** si coincide con un ciclo, un trabajador o un GET de la consola que escribe caché, se
  rechaza y reintenta.
- **Recomendación:** capturar fuera de las franjas de Fase 6 y con la consola cerrada.
- **Protocolo B:** sigue **sin aprobar y sin implementar**.

## 6. Requisitos 6 y 7: fallo seguro y sin eliminar datos

**Fallo seguro:**

- **Preparación:** `.preparando-<aleatorio>` no tiene manifiesto hasta el final y se renombra a `<id>` solo al
  sellar.
- **Ante cualquier error:**
  - se borra la preparación **solo si se acredita como propia sobre los objetos abiertos** (§14, E104-LIM-03 y
    LIM-07): la marca hermana `.<nombre>.propietario-e104` guarda el intento y la identidad (dispositivo:inodo)
    del padre y de la carpeta; se abre el padre, se lee la marca relativa a ese descriptor y se exige que padre
    y carpeta abiertos (`O_NOFOLLOW`) sean los registrados. El recorrido parte de esos descriptores, nunca sigue
    enlaces (los quita) y solo cambia permisos de objetos propios abiertos así. Un padre o una carpeta
    sustituidos tras validar no se tocan (`NoPropia`). Sin `dir_fd` (Windows) se niega de forma explícita;
  - se cierran las conexiones, con lo que termina la instantánea exportada;
  - se suelta el cerrojo **propio** de captura (del sistema operativo, liberado también si el proceso muere).
- **Restos de una captura terminada a la fuerza:** se descartan bajo ese cerrojo si son propios; los demás se
  dejan intactos y se avisa en `alertas/restos_no_propios-*.json`.
- **Plazo total** (`--plazo`, E104-PLA-04): limita cada conexión (`connect_timeout`), cada consulta
  (`statement_timeout` y `lock_timeout` con lo que queda), cada bloque de la copia y el sellado: vencido, se
  rechaza con `plazo_total_agotado`, se cierran las conexiones y no se sella.
- **Pruebas:** C6, con fallo en los siete pasos, conexión cortada y `SIGKILL`.

**Sin eliminar datos:**

- **Lo que se copia:** todos los archivos de las clases publicables, salvo los temporales de publicación y las
  reservas huérfanas, que los almacenes nunca presentan como resultado.
- **Lo que no se hace:** ningún artefacto válido ni ilegible se omite para aprobar.

## 7. Generación sellada

Carpeta `<id>/`:

- `manifiesto.json`, JSON canónico;
- `manifiesto.firma`, firma Ed25519 del manifiesto;
- `coherencia.json`;
- `base/<tabla>.jsonl`;
- `archivos/<almacén>/…`.

El `id` es la huella del manifiesto. El manifiesto vincula:

- **código:** huella de `app/` y `alembic/`, huella de `app/` sola (`huella_app`, la que recalcula la API),
  commit y revisión de Alembic;
- **esquema:** revisión y huella de columnas, restricciones e índices;
- **datos:** filas y huella de contenido por tabla, y último sorteo por juego;
- **archivos:** el conjunto exacto con tamaño y SHA-256;
- **captura:** método, intento, instantes, plataforma y autorización;
- **coherencia:** su resumen;
- **firma:** el identificador de la clave.

La clave privada queda en el equipo que captura (0600) y el servidor solo tiene la pública. Custodia y
rotación: D6/D8, pendientes.

## 8. Importación, validación y perfil privado

| Paso | Rechazo seguro si… |
|---|---|
| 1. Verificación | la firma, la identidad, los archivos o las huellas no coinciden (archivo alterado, de más o de menos, o enlace) |
| 0. Exclusión y restos | otra importación o restauración tiene el advisory del servidor; `pub_<id>` existe aceptada en otra raíz o sin prueba de propiedad; queda una carpeta de preparación ajena |
| 2. Compatibilidad | la revisión de Alembic, la huella de las fuentes o la de `app/` difieren del código que importa |
| 3. `prep_<id>_<intento>` y migración | la huella del esquema migrado difiere |
| 4. Carga de filas en una transacción | la huella de contenido recalculada difiere |
| 5. Copia de `archivos/` (solo lectura) | alguna copia no coincide |
| 6. Coherencia contra la base restaurada | el resumen difiere o hay rechazos |
| 7. Permisos y consultas DAT-04 (rol lector, otro proceso) | DAÑO o PÉRDIDA (E104-DAT-06): estado fuera del contrato, ilegibles, lectura o escritura no declarada, o menos de lo sellado (sorteos y último sorteo distintos del manifiesto; menos modelos o carteras que en `coherencia.json`; una procedencia con artefactos sellados y 0 emisiones; una predicción sellada que no se sirve). Una ausencia legítima (sin carteras, sin predicción, `/fiabilidad` sin muestra) **no** rechaza; los detalles solo se piden con claves reales de su listado |
| 8. Aceptación | — (OID sin cambiar; `prep_<id>_<intento>` → `pub_<id>` con el comentario `loteria-generacion:<id>:<sha256>`, y `preparacion/<id>` → `generaciones/<id>`) |

**Aislamiento de la generación activa:**

- **Ante un fallo:** se borra lo creado en **esa** importación y solo con prueba de propiedad (§14, E104-IMP-01).
  Las generaciones aceptadas y `activa.json` no se tocan. **Nunca se borra una base por su nombre.**
- **Restos de un `SIGKILL`:** no son utilizables, porque falta la carpeta aceptada. La siguiente importación del
  mismo `id` **en la misma raíz** los retira si son suyos (registro `preparacion/<id>.intento`, ajuste de base y
  duena) y lo informa en `restos_recuperados`; si no puede acreditarlo, rechaza con el diagnóstico y no toca nada.

**Activación:** `activar` escribe `activa.json` (renombrado atómico) tras verificar la generación y su base.
**No arranca ni para procesos:** el par API/pasarela de cada generación se arranca con su configuración
inmutable en E10.5 (D11).

**Perfil privado:** con `GENERACION_DIRECTORIO` y `GENERACION_CLAVE_PUBLICA`, los cuatro almacenes de consulta
se fijan a la generación (otro valor impide arrancar). Al arrancar se verifican:

- la firma y cada archivo;
- que el **código de la API** sea el de la generación (E104-GEN-02): el proceso recalcula `huella_app` sobre los
  archivos de `app/` que ha cargado (la imagen mínima los lleva; no necesita `alembic/` ni el árbol del
  capturador) y la compara con la del manifiesto;
- que la revisión de esquema que exige este código (`REVISION_ESQUEMA`, igual a la cabeza de Alembic por prueba)
  sea la del manifiesto **y** la de la tabla `alembic_version` de la base conectada (no una etiqueta);
- que la base conectada sea `pub_<id>` con el comentario exacto y en solo lectura por defecto.

Si algo falla, código 3. Sin `GENERACION_DIRECTORIO`, el perfil se comporta como en E10.2.

**Pasarela:** no lee datos de la generación (solo sirve la SPA y reenvía a su API), así que no necesita ligarse.
**Imagen de la API:** recalcula `huella_app` al arrancar sobre su propio `app/` (comprobado en la imagen real
`--target api`, §14). El importador comprueba además la huella completa (`app/` y `alembic/`). La API conserva
`/api/v1`, `/estado` y el OpenAPI sin cambios; el comparador estricto no tiene diferencias nuevas.

## 9. Inventario transitivo de datos (DAT-01), revisado contra el código

Se midieron las aperturas de archivos de los 77 recorridos (19 endpoints × 4 juegos más las tres procedencias)
sobre una generación sintética, con un `audithook` en el proceso de la API:

| Subárbol | Lecturas | Clase |
|---|---:|---|
| `carteras/carteras` | 244 | publicable |
| `carteras/configuraciones` | 24 | publicable |
| `laboratorio/modelos` (manifiestos, reservas y estimadores rehasheados, sin deserializar) | 67 | publicable |
| `laboratorio/pronosticos` | 48 | publicable |
| `laboratorio/experimentos` | 8 | publicable |
| `predicciones/explicaciones` | 24 | publicable |
| `pronosticos` (Producto 1/3) | 48 | publicable |
| `carteras/operacion/cerrojos/<JUEGO>.lock` | 4 sondeos | **operativo, ausente por diseño** (ver abajo) |
| `carteras/comparaciones`, `carteras/simulaciones` | 0 | publicables mientras no se demuestre lo contrario: vacíos en los datos sintéticos, así que la medición no lo prueba |

- **Hallazgo sobre el cerrojo de carteras:** `CarterasDeModelos` consulta si hay una ejecución activa abriendo el
  cerrojo sin crearlo. En la generación ese archivo no existe, y la respuesta correcta es «sin ejecución activa».
  Publicar `operacion/` sería un error: en un montaje de solo lectura `O_RDWR` falla con otro error.
- **Estado operativo** (`operacion/`, `automatizacion/`, `simulaciones/`, los `*/operacion/`) e **informes**
  (`resultados/`): no se publican; van en el respaldo.
- **Secretos:** nunca se copian.
- **Tablas:** se publica la base completa, como fijó la v2.
- **Escrituras:** ninguna.
- **Mantenimiento:** `test_la_matriz_cubre_todos_los_directorios_de_la_aplicacion` falla si aparece un
  `DIRECTORIO_*` sin clasificar.

## 10. Respaldo cifrado, restauración R-L y retención

**Qué se respalda:** una captura con alcance `respaldo`, con el mismo método coherente. Incluye la base, los
publicables, los informes y el estado operativo. **Sin** secretos: las cuentas de la consola van en un
respaldo aparte (D12) que no es de esta entrega.

**Cifrado** (`.lpr`):

- X25519 efímera con la clave **pública** del receptor, HKDF-SHA256 y AES-256-GCM por bloques de 1 MiB, con el
  contador y la marca de bloque final autenticados;
- se detectan la alteración, el reordenamiento, la duplicación y el truncamiento, y los datos añadidos tras el
  final;
- el catálogo `.lpr.json` permite comprobar el archivo sin la clave privada.

**Restauración R-L:**

1. Toma la misma exclusión del servidor que el importador.
2. Crea la carpeta destino **nueva** con marca de propiedad y escribe `RESTAURACION.json` = `en_curso`.
3. Descifra, verifica la firma y las huellas.
4. Crea una base **nueva** (`rest_*`) marcada con `loteria.restauracion = <intento>`, la migra, carga las filas
   y las comprueba.
5. Copia los almacenes y, solo al final, `RESTAURACION.json` = `completa`.

**Cualquier fallo** (también en la copia final, E104-RES-05): estado `fallida` con el motivo; se borran la base
(mismo OID, duena y ajuste) y la carpeta propias; lo que no se pueda limpiar queda en `pendiente` del estado y en
el diagnóstico de `RestauracionFallida`. `comprobar_restauracion` es la única puerta para usar una restauración
(exige `completa`). Repetir sobre el mismo destino recupera un intento **propio** no completo; un destino ajeno o
una base ajena se rechazan explicando por qué, sin tocarlos.

Nunca toca la base ni los almacenes de origen, y **nunca registra, habilita ni ejecuta la tarea programada**.

**Retención:** GFS configurable (por defecto 14 diarios, 8 semanales y 12 mensuales, siempre al menos el más
reciente).

- `retener` sin `--aplicar` solo propone;
- solo borra pares `.lpr` + catálogo verificados;
- un archivo alterado o sin catálogo **nunca** se propone borrar.

| Probado aquí (local) | Depende del proveedor o de decisiones pendientes (no probado) |
|---|---|
| Cifrado y autenticación, verificación con y sin clave privada, restauración aislada, retención sobre una carpeta local, criterios R-L | Inmutabilidad o versiones del destino, copia fuera de ambas máquinas, credencial de subida sin borrado (DAT-06), custodia de la clave privada (D6), RPO/RTO (D5), proveedor (D1/D8) |

**R-W, recuperación operativa en Windows:** pendiente de su ensayo nativo autorizado. Restaurar nunca reactiva la
tarea: R-W la registra **deshabilitada** con el controlador existente y solo se activa a mano tras verificar
(v2, 5.4).

## 11. Pruebas y demostración (Linux)

**Pruebas sin base de datos** (`tests/unit/generaciones`):

- verificación y firma: alteraciones, otra clave, identificador de clave falsificado, coherencia con rechazos;
- respaldo: ida y vuelta, alteraciones del cifrado, catálogo y retención GFS;
- fotografía: ABA y alta/baja, matriz de datos;
- perfil privado ligado: vinculación, base equivocada y generación alterada;
- v2: `test_regresiones_e104_v2.py` (LIM-03, PLA-04, GEN-02 y DAT-06 con interfaces de la v1) y
  `test_propiedad_y_plazos.py` (propiedad, confinamiento y sustitución concurrente, plazo, huella de `app/`,
  `REVISION_ESQUEMA` = cabeza de Alembic, pérdidas frente a lo sellado);
- `test_ci_generaciones_e104` (estructura del trabajo de CI y permiso de los ajustes propios del importador).

**Pruebas con PostgreSQL real** (`test_captura_c1_c10.py`, con `E104_PG_SUPERUSUARIO_URL`; en CI, el trabajo
`generaciones`):

| Escenario | Pruebas |
|---|---|
| C1 | transacción anterior que confirma después (detectada por las versiones); transacción con escritura abierta en t0 |
| C2 | cambio sin variar recuentos ni máximos (se comprueba que no varían) |
| C3 | la instantánea congelada no ve el cambio y la observación independiente sí; cambio confirmado tras la instantánea |
| C4 | cerrojo de trabajador (3 intentos acotados); espera que sella cuando termina el trabajo; advisory de sesión de un ciclo; ejecución de la CLI en curso |
| C5 | `actualizar_configuracion`, `guardar_estado` y una configuración nueva de carteras durante la captura |
| C6 | fallo en t0, t1, instantánea, volcado, copia, coherencia y t4; conexión cortada; `SIGKILL`. En todos: sin generación ni conexiones y cerrojo libre |
| C7 | cartera con `objetivo = corte + 1` y su explicación publicadas byte a byte; borrar solo el objetivo no rechaza |
| C8/C9 | sorteo `corte` ausente y sorteo intermedio ausente: rechazo entero, nada filtrado, fuente intacta |
| C10 | control positivo sellado, verificado e importado (DAT-04) |
| v2: IMP-01, RES-05, PLA-04 (`test_propiedad_y_restauracion_pg.py`) | base aceptada y activa en otra raíz; bases ajenas con nombre de preparación; importaciones simultáneas desde dos raíces; carpeta de preparación ajena; restos propios tras `SIGKILL` con la activa conservada; fallo de la copia final de R-L, repetición, fallo de la propia limpieza, fallos en la base, destino y base ajenos, exclusión compartida; cerrojo que bloquea el volcado y copia lenta dentro del plazo, sin conexiones abiertas |

**Demostración** (`demostracion_e104.py`, comprobaciones D, R, N y F):

- **Fuente:** sintética con los productores reales, más una predicción nueva de BALOTO (C7).
- **G1:**
  - capturada con el rol de captura, sin cambiar la fuente;
  - verificada e importada sin daño ni pérdida frente a lo sellado y con DAT-01 medido. Además, solo en la
    demostración (D12b), los requisitos no vacíos: `/resultados` con resultado observado en las tres
    procedencias de los cuatro juegos, `/fiabilidad` con muestra, predicción, carteras y modelos;
  - activada;
  - servida por la **API privada ligada** por HTTP, con un usuario sin privilegios y el rol lector. En
    `/predicciones` de BALOTO sirve la cartera pendiente con su explicación.
- **Respaldo:**
  - captura con alcance `respaldo` en el mismo estado, cifrado y verificado;
  - alterado y truncado: rechazado;
  - restaurado en `rest_*`;
  - criterios R-L: huellas, Alembic y filas iguales, 0 ilegibles nuevos, **cuerpos idénticos a G1** en todas las
    rutas recorridas; estado `completa`;
  - retención en seco, con mínimo y aplicada.
- **Negativos:**
  - paquete con un byte alterado, archivo de más, tabla ausente, otra clave;
  - generación firmada pero de otra revisión de Alembic;
  - API ligada a otra base o a una generación con una explicación alterada: no arranca;
  - la generación activa sigue intacta.
- **Fallos:** inyectados en los nueve pasos de la importación de G2, más un importador terminado con `SIGKILL`.
  Nunca queda una base ni una carpeta parcial de G2, la API no puede ligarse a los restos, G1 sigue activa y
  verificable, y la reimportación acepta G2.

En un contenedor que solo tiene root, la API privada se arranca en un espacio de nombres de usuario (uid 10001),
porque el perfil no corre como root. En CI el ejecutor no es root.

## 12. Uso (desde `backend/`)

```bash
python -m scripts.generaciones claves-firma --privada <pem> --publica <pub>
python -m scripts.generaciones capturar --destino <dir> --clave-privada <pem>          # base «prueba»; real: D10
python -m scripts.generaciones verificar --paquete <dir>/<id> --clave-publica <pub>
python -m scripts.generaciones importar --paquete <dir>/<id> --clave-publica <pub> --raiz /srv/pub \
    --url-admin-archivo <f> --url-lector-archivo <f>
python -m scripts.generaciones activar --raiz /srv/pub --id <id> --clave-publica <pub> --url-admin-archivo <f>
python -m scripts.generaciones claves-respaldo --privada <pem> --publica <pub>
python -m scripts.generaciones respaldar --paquete <dir> --clave-publica-firma <pub> --clave-publica-respaldo <pub> --destino <dir>
python -m scripts.generaciones restaurar --archivo <.lpr> --clave-privada-respaldo <pem> --clave-publica-firma <pub> \
    --destino <dir nuevo> --url-admin-archivo <f>
python -m scripts.generaciones retener --destino <dir> [--diarios 14 --semanales 8 --mensuales 12] [--aplicar]
```

**Reversión de la entrega:** `git apply -R` del parche. No hay migraciones ni estado fuera de las carpetas y
bases que crean estas órdenes, y la demostración borra sus bases `prep_*`, `pub_*` y `rest_*`. El único cambio de
servidor nuevo de la v2 es `GRANT SET ON PARAMETER loteria.importacion, loteria.restauracion` al rol importador
(`despliegue/generaciones/postgres/roles.sql`); se retira con `REVOKE SET ON PARAMETER ...`.

## 14. Correcciones de la v2 (auditoría de Codex sobre la v1)

| Hallazgo | Corrección | Regresión que falla sobre la v1 |
|---|---|---|
| E104-IMP-01 | Exclusión con un advisory de sesión en la base de mantenimiento `postgres` (común a todas las raíces del servidor, también para R-L). Identidad de raíz `.raiz-e104`; registro `preparacion/<id>.intento` antes de crear; base `prep_<id>_<intento>` marcada con `loteria.importacion = <raíz>:<intento>`. Solo se borra con duena = rol actual, ajuste de esta raíz e intento y, en la llamada, el mismo OID. `pub_<id>` de otra raíz → `generacion_aceptada_en_otra_raiz`, intacta; `activar` exige además que la base sea de su raíz. | `test_propiedad_y_restauracion_pg.py`: base aceptada y activa en otra raíz; bases ajenas con nombre de preparación; importaciones simultáneas desde dos raíces; carpeta de preparación ajena |
| E104-GEN-02 | `codigo.huella_app` + `REVISION_ESQUEMA` contrastados al arrancar con el `app/` cargado y con `alembic_version` | `test_regresiones_e104_v2.py::test_gen02_*` |
| E104-LIM-03 | Marca hermana por intento; borrado y `solo_lectura` por descriptores con `O_NOFOLLOW`, comprobación de duena, enlaces duros rechazados; restos ajenos intactos con alerta | `test_regresiones_e104_v2.py::test_lim03_*`; sustitución concurrente en `test_propiedad_y_plazos.py` |
| E104-LIM-07 (v3) | Marca `e104-propia/2` con la identidad del padre y de la carpeta; autorización y recorrido sobre los MISMOS descriptores (`_abrir_propia`); la entrada solo se retira si el nombre sigue siendo ese objeto; `crear_propia` no adopta una carpeta sustituida entre `mkdir` y `open`; sin `dir_fd`, negativa explícita | `test_regresiones_e104_v3.py` (padre sustituido, carpeta sustituida, `solo_lectura` sustituida, preparación de captura sustituida) |
| E104-TEST-08 (v3) | El caso `otro_comentario` cambia siempre el último carácter por otro distinto; control determinista con clave fija y comentario terminado en 0 | `test_perfil_privado_generacion.py` |
| E104-PLA-04 | `Plazo` en cada conexión, consulta, bloque de copia y antes de sellar | `test_pla04_*` (servidor que no responde, cerrojo que bloquea el volcado, copia lenta, intento que agota el plazo) |
| E104-RES-05 | Todo R-L bajo la misma limpieza, estado `RESTAURACION.json`, recuperación de lo propio | `test_res05_*` (fallo de la copia final, repetición tras el fallo, fallo de la propia limpieza) |
| E104-DAT-06 | `recorrer(get, esperado)` solo falla por daño o pérdida frente a `consultas.esperado_de(manifiesto, coherencia)`; `requisitos_de_demostracion` aparte, solo en la demostración (D12b) | `test_regresiones_e104_v2.py::test_dat06_*` |

La sonda original de Codex se conserva sin cambios. Sobre la v2 da 0/6. En IMP-01 y RES-05 su adaptador SQL
responde `None` al advisory nuevo, así que la v2 rechaza por `exclusion` antes de la decisión corregida: es un
resultado correcto pero **no informativo** y no se cuenta como corrección. El contraste equivalente (adaptador que
responde al advisory, a los ajustes, a la duena y al OID) y las pruebas con PostgreSQL real son la evidencia de
esos dos hallazgos.

## 13. Pendiente y decisiones (nada se da por cerrado)

- **D10 (Daniel): aprobar el método `observacion-doble-e104/1` para datos reales.** Para el uso real, la
  intervención operativa concreta sería:
  1. crear en la base del PC el rol `generaciones_captura` con `despliegue/generaciones/postgres/rol-captura.sql`
     (solo lectura y `pg_read_all_stats`, sin escribir ni tomar cerrojos);
  2. ejecutar `capturar --autorizacion-d10 <referencia>` en el PC, fuera de las franjas de Fase 6;
  3. validar en Windows nativo la detección de archivos (`mtime` en lugar de `ctime`).

  Hasta entonces **F10-DAT-02 sigue abierto** para producción y la CLI rechaza las bases que no son de prueba.
- **D11:** activación con drenaje o en paralelo (E10.5); `activa.json` ya es la entrada.
- **D5/D6/D1/D8:** RPO/RTO, destino y custodia de respaldos y claves, proveedor, registro y secretos.
- **R-W:** recuperación operativa en Windows, pendiente de su ensayo nativo autorizado; nunca reactiva la tarea.
- **Respaldo aparte de los secretos de la consola (D12):** no se implementa aquí.
- **Comparaciones y simulaciones de carteras:** demostrar con datos que no se leen antes de excluirlas.
- **Límites de LIM-07 (v3):** dentro de la carpeta propia (0700) las subcarpetas no llevan marca: lo que otro
  proceso del mismo usuario mueva dentro pasa a ser su contenido; entre la última comprobación de identidad y
  `rmdir` solo podría retirarse una carpeta vacía. Las marcas de la v2 (sin identidades) ya no acreditan nada:
  sus restos se conservan con aviso. Windows: negativa explícita hasta su validación nativa.
