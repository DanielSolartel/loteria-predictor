# Fase 7 — Simulaciones bajo el mecanismo uniforme

**Estado:** implementada sobre `605afe8c2bb3b38d0fa3abdb6a5d14ba2002b5a6` (merge de PR #97) y verificada en Linux (Cloud) con datos sintéticos y un PostgreSQL 16 de pruebas aislado. La **v2** (24-10-2026) corrige los cuatro hallazgos de la auditoría de la v1 ([apartado](#v2-correcciones-de-la-auditoría-de-la-v1)); la v1 no se aplica. La validación nativa de Windows, PostgreSQL aislado y la auditoría visual están **completadas**, incluido el ajuste de presentación F7-VIS-01. La publicación manual, revisión del PR y sus Actions siguen pendientes ([cierre del operador](fase7_validacion_operador_2026-10-24.md); [procedimiento](fase7_windows.md)). Se mantienen `experimental_no_acreditado`, el NO-GO de AE-39 y `AUTORIZA_EVALUACION = False`.

## Qué responde y qué no

Para cada juego y corte, la Fase 7 pregunta si unas pocas estadísticas descriptivas, **fijadas en el diseño antes de observar ningún resultado**, son compatibles con su distribución cuando los sorteos se generan con el mecanismo uniforme del juego. Es una comparación **exploratoria**: no es confirmatoria, no es evidencia prospectiva ni predictiva, no genera combinaciones ni recomendaciones y no modifica el NO-GO de AE-39. «Supera el umbral exploratorio» señala una discrepancia descriptiva a revisar; lo contrario no demuestra aleatoriedad.

## Qué se reutiliza y qué se conserva

- **Motor de Fase 5:** las funciones de `app/application/estadisticas/motor` definen las estadísticas y calculan lo **observado**. La versión vectorizada que usan las simulaciones se contrasta con ellas en cada ejecución y, en las pruebas, sobre históricos simulados.
- **Reglas:** `laboratorio_variables.REGLAS` y su validación (`validar_instantanea`), la huella del histórico (AE-52) y la paleta del corte de ColorLoto, igual que en Productos 2 y 5.
- **Corrección de Bonferroni:** la función `aplicar_correccion_bonferroni` del motor.
- **Mecanismos de ejecución:**
  - primitivas de Producto 3: cerrojo por juego, cerrojo de la ejecución y registro de progreso con escritura atómica en Windows;
  - proceso trabajador `spawn` con tiempo máximo, como en Productos 4 y 5;
  - protección local de los POST y lectura en transacción `READ ONLY`.
- **Paquete propio:** los módulos puros viven en `app/application/fase7/` (`motor.py`, `artefacto.py`) y no en `app/application/simulaciones/`. La salvaguarda de AE-49 (`test_nada_en_web_main_ni_plantillas_expone_ae49`) impide que la web, `main` o las plantillas mencionen ese paquete, y se conserva intacta.
- **Se conservan sin cambios:** AE-49, AE-50 y AE-51 (referencia exploratoria sobre `2081..2705`, su contrato, sus evidencias y su revisión Alembic `0006`) y Producto 5 (simulación de carteras, su almacén y su intervalo de 1.000 a 50.000). No se importan ni migran sus evidencias o artefactos a la tabla.

## Mecanismo por juego

| Juego | Mecanismo simulado |
|---|---|
| BALOTO, BALOTO_REVANCHA | 5 números distintos de 1..43 sin reemplazo; superbalota uniforme 1..16, aparte e independiente |
| MILOTO | 5 números distintos de 1..39 sin reemplazo |
| COLORLOTO | 6 balotas, cada una un par (número 1..7, color de la paleta del corte) extraído uniformemente **con reemplazo**: los pares pueden repetirse y se cuentan con multiplicidad. Es el supuesto multinomial de Productos 2 y 5; el dominio documenta que el reglamento debe confirmarlo |

Cada histórico simulado conserva la numeración observada, huecos incluidos, de modo que las transiciones estrictas N−1→N son las mismas que en lo observado.

## Estadísticas fijadas

Se eligió un patrón por aspecto, con media analítica exacta cuando existe, para que la familia sea pequeña y Bonferroni conserve potencia. Todas son enteras sobre un denominador que solo depende de la numeración, de modo que las comparaciones (≥, ≤) son exactas.

| Juego | Estadística | Patrón de Fase 5 | Media exacta bajo el mecanismo |
|---|---|---|---|
| Numéricos | `dispersion_frecuencia_numeros` Σ(n·Oᵢ − N)²/(n·N) | `calcular_frecuencia_numeros` | n − k (38 en Baloto, 34 en MiLoto) |
| Numéricos | `rango_frecuencia_numeros` máx − mín | `calcular_frecuencia_numeros` | sin forma cerrada |
| Numéricos | `media_repeticiones_entre_sorteos` | `calcular_repeticiones_entre_sorteos` | k²/n (25/43; 25/39) |
| Numéricos | `media_suma` | `calcular_distribucion_sumas` | k(n+1)/2 (110; 100) |
| Numéricos | `media_pares_consecutivos` | `calcular_distribucion_pares_consecutivos` | k(k−1)/n (20/43; 20/39) |
| Baloto, Revancha | `dispersion_frecuencia_superbalota` | `calcular_frecuencia_superbalota` | m − 1 = 15 |
| ColorLoto | `dispersion_frecuencia_pares` (con multiplicidad) | `calcular_frecuencia_pares_numero_color` | P − 1 = 41 |
| ColorLoto | `dispersion_frecuencia_numeros` | `calcular_frecuencia_numeros_colorloto` | 6 |
| ColorLoto | `dispersion_frecuencia_colores` | `calcular_frecuencia_colores` | c − 1 = 5 |
| ColorLoto | `media_repeticiones_entre_sorteos` (multiconjuntos) | `calcular_repeticiones_entre_sorteos_colorloto` | exacta por enumeración binomial ≈ 2,8607 |
| ColorLoto | `media_maximo_repeticion_color` | `calcular_maximo_repeticion_color_por_sorteo` | exacta por enumeración multinomial ≈ 2,4082 |

## P-valores y familia

- **p bilateral empírico con corrección +1:** p = min(1, 2·min(p_sup, p_inf)), con p_sup = (1 + #sim ≥ obs)/(1 + B) y p_inf = (1 + #sim ≤ obs)/(1 + B). Nunca vale 0.
- **Percentil:** (2·#sim < obs + #sim = obs)/(2·B).
- **Bonferroni:** se aplica una vez sobre las comparaciones de **ese juego en esa ejecución** (6 en Baloto y Revancha, 5 en MiLoto y ColorLoto), con α = 0,05. No corrige otros juegos, cortes, semillas ni ejecuciones, ni la decisión de mirar estos datos.
- **Resolución mínima:** con 100 iteraciones el p mínimo es 2/101, y ajustado no puede bajar de 0,05; el resultado lo declara con `umbral_alcanzable = false`.
- **Exactitud:** los valores exactos (enteros y fracciones `a/b`) se guardan junto a su lectura decimal.

## Iteraciones, lotes y memoria

- **Iteraciones admitidas:** 100, 1.000, 10.000, 100.000 y 1.000.000; por defecto 10.000. La semilla predeterminada es `20261023` y admite cualquier entero de 0 a 2³²−1.
- **Lotes:** cada lote reserva como mucho `DOBLES_POR_LOTE = 2.000.000` uniformes (~16 MB) y sus derivados. Nunca se reservan todas las réplicas: los resultados se acumulan en flujo, con conteos frente a lo observado, sumas y sumas de cuadrados exactas, y mínimo y máximo.
- **Ejecución:** la web y el comando ejecutan siempre en el proceso trabajador, con progreso por lote (escrito como mucho una vez por segundo, más las fases) y tiempo máximo `TIEMPO_MAXIMO_TRABAJADOR_SIMULACIONES` (3.600 s por defecto).

### Medición en Linux (Cloud, datos sintéticos)

`python tests/medicion_fase7.py` mide cada punto en un proceso nuevo. Entorno: Linux x86_64, 4 CPU (Intel Xeon a 2,80 GHz), Python 3.14.9, NumPy 2.5.4, código final de la v1. La v2 no cambia el motor (`fase7/motor.py` idéntico byte a byte), así que la medición conserva su atribución a la v1 y no se repitió. Los históricos son sintéticos, con los tamaños documentados al 23-10-2026. Las cifras son de este entorno: no se trasladan a Windows ni al equipo del operador.

Segundos de cálculo (sin el arranque del proceso) · pico de memoria del proceso en MiB:

| Juego (sorteos, uniformes por iteración) | 100 | 1.000 | 10.000 | 100.000 | 1.000.000 | lote |
|---|---:|---:|---:|---:|---:|---:|
| Baloto (645, 3870) | 0,028 s · 163 | 0,244 s · 208 | 1,705 s · 209 | 14,8 s · 208 | 144,6 s · 208 | 516 |
| Baloto Revancha (645, 3870) | 0,028 s · 163 | 0,381 s · 208 | 1,529 s · 208 | 13,4 s · 209 | 140,6 s · 209 | 516 |
| MiLoto (97, 485) | 0,005 s · 153 | 0,024 s · 167 | 0,440 s · 214 | 2,063 s · 214 | 21,2 s · 214 | 4123 |
| ColorLoto (229, 1374) | 0,075 s · 157 | 0,532 s · 238 | 1,411 s · 278 | 8,890 s · 278 | 81,6 s · 277 | 1455 |

Tras las importaciones, la base del proceso ocupa 149–152 MiB. El pico **no crece con las iteraciones**: de 10.000 a 1.000.000 se mantiene en unos 209 MiB en Baloto, 214 MiB en MiLoto y 278 MiB en ColorLoto. Esto confirma que nunca se reservan todas las réplicas. El tiempo crece de forma lineal con las iteraciones: 1.000.000 tarda unos 2,4 min en Baloto y Revancha, 21 s en MiLoto y 1,4 min en ColorLoto. Una medición anterior, con el mismo motor, dio cifras equivalentes (Baloto 149,8 s; ColorLoto 87,5 s). La extrapolación previa de 2,7 h correspondía al motor de AE-49 en Python puro. La medición nativa en Windows se completó con veinte puntos, incluidos los cuatro de un millón; sus cifras y unidades se registran por separado en el [informe del operador](fase7_validacion_operador_2026-10-24.md).

Evidencia: `medicion-linux.json` de la entrega v1 (SHA-256 en su manifiesto de evidencias).

## Determinismo y su alcance

- **Generador:** `PCG64(SeedSequence([semilla, 7, índice del juego]))`, propio de la Fase 7 y distinto de los flujos de Producto 5.
- **Consumo fijo:** cada iteración consume exactamente H·(k + s) dobles de `random()` en orden, donde H son los sorteos, k los números o balotas y s = 1 con superbalota. Por eso **el resultado no depende del tamaño de lote**: los lotes solo reparten esa secuencia. Las pruebas comparan lotes de 1, 7, 64, 1.000 y el predeterminado.
- **Selección sin reemplazo:** el t-ésimo índice es floor(u·(n − t)) entre los restantes, la semántica de Fisher-Yates de AE-49. Una prueba enumera todos los índices de casos pequeños y comprueba que cada subconjunto sale exactamente k! veces. El único sesgo es el de convertir dobles, ≤ n/2⁵³; el producto nunca alcanza n.
- **Identidad de bytes:** la huella fijada en `test_huella_de_referencia_fijada` se obtuvo igual con NumPy 2.5.4 (Python 3.14.9) y NumPy 2.4.6 (Python 3.11) en Linux. La versión de NumPy forma parte de la identidad; entre versiones o plataformas la igualdad se **comprueba**, no se supone. La comprobación nativa en Windows está pendiente.
- **Qué queda fuera de la identidad:** el lote, la duración y el entorno. Se registran en `resultado_resumen.ejecucion`, fuera del contenido científico.

## Persistencia canónica: tabla `simulaciones`

La fila es la fuente canónica de cada resultado nuevo de la Fase 7. Las exportaciones JSON y CSV se derivan de ella, y el registro de progreso (`DIRECTORIO_SIMULACIONES/operacion`) solo la referencia.

| Columna existente | Uso |
|---|---|
| `juego_id` | juego (se comprueba contra `parametros.juego` al leer) |
| `num_iteraciones` | B (se comprueba contra la identidad) |
| `parametros` (JSONB) | **identidad completa**: esquema, versión del motor, juego, corte, histórico (sorteos, huecos, transiciones, SHA-256), reglas y mecanismo, algoritmo (incluida la versión de NumPy), semilla, iteraciones, estadísticas, familia, estado de uso y `clave` = SHA-256 canónico de todo lo anterior |
| `resultado_resumen` (JSONB) | `contenido` (resultado determinista) y `contenido_sha256`; `ejecucion` (lote, lotes, duración, entorno, origen, id de ejecución); `integridad_sha256` de parámetros + resultado |
| `ejecutado_en` | hora de publicación del servidor |
| `duracion_ms` | duración del cálculo |

**Garantías:**
- **Integridad:** listado, panel, lectura individual, reutilización y publicación concurrente usan **una sola comprobación** (`artefacto.verificar_fila`):
  - tipos de `parametros`, `resultado_resumen`, `contenido` y de los campos que leen la ficha, las exportaciones y `verificar`, antes de usarlos (las huellas no son una firma: quien edita la fila puede recalcularlas);
  - clave, huella del contenido e integridad recalculadas;
  - coherencia con `num_iteraciones` y del juego de la columna `juego_id` con el de la identidad.

  Una fila alterada no se sirve: la web y la API responden 409 y el comando sale con 8. En el listado y el panel se identifica (id, juego de su `juego_id`, hora y motivo) sin mostrar su identidad ni su umbral, y no impide listar las demás. Solo un fallo de lectura de la base se informa `base_no_disponible`. Nunca se sobrescribe. Una fila sin `parametros.clave` (no es de la Fase 7) no se lista y su lectura da «no encontrada».
- **Identidad y reutilización:** antes de simular se busca la clave. Si hay una fila íntegra, se reutiliza sin simular. Si hay duplicados idénticos (insertados fuera de este caso de uso), se usa la más antigua; si los duplicados tienen contenido distinto, el resultado es `alterado`.
- **Publicación transaccional:** el trabajador nunca escribe. El proceso padre abre una transacción propia, toma `pg_advisory_xact_lock` sobre un recurso propio de la clave (espacio `loteria:simulaciones:`, distinto del recurso de datos por juego de la Fase 6) con `lock_timeout = 10s`, busca la clave e inserta la fila **completa**. Después la relee y la verifica. Si otro publicador llegó antes, se conserva su fila (`reutilizado`). Un fallo antes de confirmar no deja nada.
- **Concurrencia de trabajos:** un cerrojo del sistema operativo por juego impide dos simulaciones simultáneas del mismo juego (web 409, comando 6). Repetir la entrada reutiliza lo que ya esté en la tabla.
- **Cierre e interrupción:** el trabajador escribe su cierre **antes** de soltar el cerrojo de la ejecución.
  - Una lectura (página, API, comando) observa una sola vez ese cerrojo. Si está tomado, `en_curso` es una instantánea válida y la página sigue sondeando. Si está libre, relee el registro: devuelve el cierre persistido o, solo si sigue `en_curso`, informa `interrumpida`. No escribe.
  - `recuperar` toma el cerrojo de la propia ejecución (no el del juego, para no esperar a otra simulación), relee y valida el registro bajo esa exclusión y persiste `interrumpida` solo si sigue `en_curso`. Nunca sobrescribe un cierre terminal ni marca una ejecución cuyo cerrojo sigue tomado.

**Sin cambio de esquema.** Un índice único sobre `parametros->>'clave'` sería defensa adicional, pero exigiría migrar la base real compartida. Además, los scripts de AE-49, AE-51, la auditoría operativa y la consulta de estado exigen que la revisión Alembic de la base coincida con el head local: una migración 0007 los haría fallar desde el worktree operativo de la Fase 6. Las columnas actuales bastan y la exclusión la da el advisory dentro de la transacción, verificado con 8 publicadores concurrentes sobre PostgreSQL 16 de pruebas. Si en el futuro se añade el índice, conviene hacerlo como entrega propia y con la migración coordinada.

## Interfaces (un único caso de uso: `SimulacionesFase7`)

- **Web `/simulaciones`:**
  - los cuatro juegos (corte, sorteos, frescura, mecanismo, estadísticas, simulaciones guardadas y su integridad), con formulario de iteraciones, semilla y corte opcional;
  - `POST /simulaciones/simular` (protegido; 303 al progreso, 409 si el juego está ocupado);
  - progreso con HTMX;
  - resultado con exportaciones y verificación de integridad y base.
- **API interna `/api/simulaciones` (solo lectura):** catálogo, panel, listado, fila, CSV, JSON, verificación y ejecuciones. Simular se lanza desde la web o el comando, como en Productos 4 y 5 y la Fase 4. No es la API pública de la Fase 8.
- **Comando `python -m scripts.simulaciones`:** `catalogo`, `diagnostico`, `simular`, `listar`, `ver`, `exportar`, `verificar [--reproducir]`, `consultar`, `ejecuciones`, `recuperar` y `rutas`, con códigos de salida documentados en el propio script.

**Configuración:**
- `DIRECTORIO_SIMULACIONES` (por defecto `storage/simulaciones`): solo para el progreso y los cerrojos.
- `TIEMPO_MAXIMO_TRABAJADOR_SIMULACIONES` (por defecto 3.600 s).

## v2: correcciones de la auditoría de la v1

La auditoría independiente de la v1 (23-10-2026) aprobó sus 94 pruebas y reprodujo cuatro casos con sondas sintéticas. La v2 reproduce primero esas sondas sobre la v1 (0/4), corrige y las vuelve a pasar (4/4). El motor científico (`fase7/motor.py`), las identidades, la clave, la huella de referencia y el esquema no cambian.

| | Hallazgo en la v1 | Corrección en la v2 |
|---|---|---|
| F1 | Una lectura `en_curso` anterior a un cierre correcto se derivaba `interrumpida`: la página dejaba de sondear y ocultaba el enlace al resultado | `_derivar` observa el cerrojo una vez y, si está libre, relee el registro; conserva el cierre persistido |
| F2 | `recuperar` podía sobrescribir ese éxito y perder la referencia al resultado (la fila SQL quedaba) | relectura y validación bajo el cerrojo de la propia ejecución; solo marca una interrupción confirmada |
| F3 | El listado no comparaba `juego_id` con el juego de la identidad y podía marcar `verificada` la fila de otro juego | comprobación única `verificar_fila` en listado, panel, lectura, reutilización y publicación concurrente; una fila alterada no expone su umbral |
| F4 | Un `resultado_resumen` como `[1]` provocaba `AttributeError` en el listado y el panel lo confundía con `base_no_disponible` | tipos comprobados antes de acceder; cada fila se marca por separado; `base_no_disponible` solo por un fallo de lectura de la base |

**Regresiones:** `tests/unit/simulaciones/test_fase7_regresiones_v2.py`, 31 pruebas deterministas, sin hilos ni esperas. Un punto de control hace que el trabajador cierre justo entre la lectura del registro y la observación del cerrojo, o mientras `recuperar` toma el recurso. Sobre la v1 fallan 28 por los defectos; las otras 3 son garantías que ya cumplía (sondeo con el trabajador vivo e interrupción realmente confirmada, en la lectura y en la recuperación). Las 94 pruebas de la v1 se conservan sin cambios.

## Verificación en Linux (Cloud) de esta entrega

Solo Cloud/Linux; no sustituye la validación nativa. Las baterías se solapan (la suite completa incluye las de la Fase 7): no se suman.

### v2 (base del cierre, antes del ajuste de presentación F7-VIS-01)

Mismo entorno que la v1: Python 3.14.9, NumPy 2.5.4 y PowerShell 7.5.4 en el `PATH`; `pip check` limpio. Ejecutado el 24-10-2026 sobre el código final de la v2.
- **Sondas de la auditoría** (`sondas_f7.py`, sin modificar): sobre la v1, `0 / 4` (código 1), igual que el auditor; sobre la v2, `4 / 4` (código 0).
- **Regresiones nuevas sobre la v1:** 28 fallan y 3 pasan (las garantías citadas arriba).
- **Fase 7 focal** (`tests/unit/simulaciones`): `274 passed`. De ellas, 125 son de la Fase 7: las 94 de la v1 sin cambios y las 31 regresiones.
- **Suite completa:** `7428 passed`, sin fallos ni omisiones, en 19 min 57 s.
- **Pasos del job Linux de CI:** `scripts/ci_contrastes_openssl.py --modo exigir` da `SUPERADOS 7/7`, y las siete demostraciones salen con código 0.
- **PostgreSQL 16.13 de pruebas aislado y nuevo** (socket privado, base `f7_pruebas` en `0006`, solo datos sintéticos): `tests/postgres_fase7.py` cumple A–C y E–J.
  - J, nuevo: con JSONB real, la fila de otro juego y un `resultado_resumen` lista quedan `alterada` en el listado y `alterado` en la lectura; unos `parametros` lista no se listan y su lectura da «no encontrada»; el panel del juego sigue `disponible`.
  - E: espera de 10,0 s. H: códigos `[0, 0, 0, 0]`. D, informativo: sin el advisory, la carrera dejó 6 filas con la misma clave.
  - Los dos errores del registro del servidor son los provocados por B (escritura en solo lectura) y E (`lock_timeout`).
- **Motor:** `fase7/motor.py` es idéntico byte a byte al de la v1, y `test_huella_de_referencia_fijada` pasa. La medición de rendimiento no se repitió y conserva su atribución a la v1.
- **No repetido en la v2:** revisión visual (no cambian plantillas ni estilos) y ejecución web de 1.000.000 de iteraciones (el motor no cambia).

### v1 (entrega original, antecedente)

Resultados de la v1, informados al entregarla; no se repiten como evidencia de la v2.
- **Entorno:** Python 3.14.9 (instalado con uv en el scratchpad) con las dependencias de `requirements.txt` y `httpx==0.28.1`; NumPy 2.5.4; `pip check` limpio. PowerShell 7.5.4 en el `PATH`, como en el runner Ubuntu de CI: descargado al scratchpad, sin instalar en el sistema. Sin él, las 74 pruebas de Fase 6 que lo necesitan se omiten, igual sobre la base `605afe8`.
- **Suite completa:** `7397 passed`, sin fallos ni omisiones, en 22 min 37 s. Incluye las **94 pruebas nuevas** de `tests/unit/simulaciones/test_fase7_*`: motor 44, persistencia 6, caso de uso 28, trabajador `spawn` real 5 e interfaces 11.
- **Pasos del job Linux de CI:** `scripts/ci_contrastes_openssl.py --modo exigir` da `SUPERADOS 7/7`, y las siete demostraciones (AE-79, AE-80, AE-81, Producto 6, Fases 5, 3 y 4) salen con código 0.
- **Primera suite completa:** se hizo antes de mover los módulos a `app/application/fase7/` y dio 2 fallos de salvaguardas existentes (AE-49 y la marca de impresión de las páginas), corregidos como se describe arriba y en la entrega. La suite que vale es la de este apartado.
- **Pruebas existentes ajustadas, sin debilitarlas:**
  - `test_fase4_web.py`: el orden del menú se comprueba frente al enlace de Simulaciones, porque desaparece «Próximamente»;
  - `test_producto1_presentacion.py`: añade `simulaciones/` a la lista de carpetas con la marca de impresión, como hicieron las Fases 4 y 6.
- **PostgreSQL 16.13 de pruebas aislado** (socket privado, base `f7_pruebas` en revisión `0006`, solo datos sintéticos): `tests/postgres_fase7.py` cumple A–C y E–I.
  - 8 publicadores concurrentes dejan 1 fila; sin el advisory, la misma carrera dejó 8 filas con la misma clave (apartado D, informativo).
  - El recurso retenido produce un error explícito a los 10,0 s.
  - El advisory de datos de la Fase 6 no bloquea la publicación.
  - El comando en procesos nuevos (`simular`, `listar`, `verificar --reproducir`, reutilizar) devuelve 0.
  - La web publica en segundo plano.
- **Ejecución web de 1.000.000 iteraciones** (Baloto, trabajador real): 2 min 36 s de principio a fin; integridad verificada; medias simuladas 38,0145, 0,5814, 109,9997, 0,4651 y 15,0022 frente a las referencias exactas 38, 0,5814, 110, 0,4651 y 15.
- **Revisión visual con Chromium** (Playwright 1.56.1), sobre el panel, dos resultados, una fila alterada (409) y una ejecución en curso:
  - a 1366, 390 y 360 px no hay desbordamiento horizontal y en móvil las tablas se desplazan por dentro;
  - se generó un PDF de impresión de cada página;
  - Bootstrap, los iconos y htmx se sirvieron desde los paquetes npm de las mismas versiones, porque cdnjs no es alcanzable en el sandbox.
- **Determinismo:** huella de referencia igual con NumPy 2.4.6 y 2.5.4; resultados idénticos con lotes de 1, 7, 64, 1.000 y el predeterminado.

## Límites

- Datos sintéticos únicamente; no se usó la base real ni se simularon históricos reales.
- PostgreSQL 16.13 de pruebas en Linux, no el servidor ni la versión del operador.
- Python 3.14.9 en Linux. Ni el kernel de Windows, ni PowerShell 5.1, ni NTFS, ni el `spawn` de Windows quedan acreditados desde Cloud.
- El supuesto de ColorLoto con reemplazo es el del proyecto, pendiente de confirmar contra el reglamento.


## Cierre local del operador y ajuste F7-VIS-01

Validado el 24-10-2026 en Windows/Python 3.14.6 y NumPy 2.5.3: selección v2 consolidada de dos corridas (3183 pruebas únicas), OpenSSL 7/7 y cuatro sondas 4/4; medición de veinte puntos; nueve controles con PostgreSQL 16.14 en contenedor Linux separado. Las pruebas, mediciones y entornos mantienen su procedencia.

La auditoría de las primeras 36 capturas de Brave (516/516 criterios automáticos) identificó una tarjeta que seguía anunciando actividad tras derivarse una interrupción. F7-VIS-01 modifica solo la plantilla y añade diez regresiones: el estado visual se vuelve interrumpido, el avance previo queda como información histórica y se conservan los estados cerrados. No persiste estados desde un GET ni cambia el caso de uso, los cerrojos, el motor o la identidad.

El ajuste pasó en Windows 52 pruebas dirigidas, la sonda independiente 8/8 y una revalidación de cinco estados por tres anchos (15 capturas, 228/228 criterios); el auditor revisó las imágenes y cerró el hallazgo. No se repitieron la selección completa, la medición o PostgreSQL por este cambio de presentación. Tampoco se atribuye al ajuste la suite completa Linux de la v2 original.

[Resultados, hashes, límites y publicación pendiente](fase7_validacion_operador_2026-10-24.md). El uso sobre la base real es una decisión operativa separada; la validación descrita usa datos sintéticos.
