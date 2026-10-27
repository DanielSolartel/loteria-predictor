# Fase 9.3 v2 — validación del operador y cierre documental del 27 de octubre de 2026

**Estado:** v2 validada en Linux y Windows nativo con Brave y aprobada por la auditoría; cierre documental preparado. Quedan pendientes la revisión de este incremental documental, la publicación manual de Daniel, la integración y el CI del nuevo PR. No se ha creado un PR, commit o ejecución de CI de 9.3. La Fase 9 global sigue abierta.

## Insumos y procedencia

Base inmutable del merge PR #101: `ed0ee427f7a6fcd2a33cbc538435a3df2e299710`, árbol `4361ce10e8424dc7d7c00f31b52946546c2132b1`, 955 archivos. Fuente v2 aprobada: árbol `099f1aea8d5f2f873d81e16fe40ea361d9c6eb15`, 975 archivos y 60 rutas frente a esa base. El cierre es incremental sobre los bytes de esa v2, no un nuevo parche completo sobre la base.

| Insumo | Bytes | SHA-256 | Atribución y alcance |
| --- | ---: | --- | --- |
| `fase9-3-entrega-v2.zip` | 5.407.988 | `48fc0a947f24aa1dd9c398620d8fdbe09f1487d8704ae49fb58cfe502594594c` | Implementación Linux/Cloud y sus evidencias; se conserva intacta |
| `f93-validacion-v2-6b70ed16.zip` | 6.017.391 | `38926b543dfc81be2d7015be1162e7558f264a422d208ecb9ffb4d76853f5563` | Ejecución nativa de Daniel, auditada posteriormente; el dictamen acredita CRC de 63 entradas y 16 capturas |
| `fase9-3-auditoria-nativa-y-encargo-cierre.zip` | 364.284 | `407b70b9e577791dea146f9433383d5d63288911567fe51ab3a19fd737c32015` | Dictámenes y copias textuales saneadas recibidas para este cierre; 26 huellas SHA256SUMS y 20 copias de procedencia contrastadas |
| `f92-observacion-horario-737f2a0d.zip` | 37.824 | `2e2367cf1041b8de61da58d0e5413b3e0dcc67e928c2bf51de154feaf7fa090f` | Captura de operación real de Fase 6; datos resumidos y verificados por el auditor, separados de las pruebas sintéticas |

El cierre leyó íntegramente los dictámenes, JSON, los dos JUnit y los resultados textuales incluidos. Las copias saneadas identifican por separado su hash original y el de la copia en `PROCEDENCIA-EVIDENCIAS.json`. Los ZIP originales nativo y operativo y las imágenes no se redistribuyen en esta entrega: sus CRC y la inspección visual se atribuyen al auditor que recibió los originales, sin fingir una nueva revisión de imágenes o un nuevo acceso a Windows.

Huellas de las tres referencias v2 coincidentes entre Linux, ejecución nativa y este cierre:

- Parche completo de referencia: `6980e2541f47a7cae54690734fc335f7c2cbbdaf2af80be8906bf04100c5be8b`.
- Manifiesto v2: `79f3e9c605025537a5f9fa1951e94fc592dc9d05a91286ddbb6db090c0bbf574`.
- Inventario de 975 archivos: `3f6157b35bdbbd2b8bd6f9ee1c0fa39d4591b773dbcc43bae3693923a3d2c138`.

## Validación nativa ejecutada por Daniel

Ejecución del **27 de octubre de 2026, 11:18:23–11:29:15, America/Bogota**, terminada con código cero. Windows 11, Python 3.14.6 y Node 24.15.0. Datos sintéticos, SQLite y almacenes temporales propios; API y pasarela reales con el frontend compilado. No es una nueva comprobación de PostgreSQL operativo o de la tarea de Fase 6.

| Grupo | Resultado contrastado en los archivos recibidos |
| --- | --- |
| API pública y pasarela | 415 casos aprobados; cero fallos, errores u omisiones. El auditor identifica dos advertencias conocidas: TestClient y cookies por petición |
| Frontend Vitest | 690 casos aprobados; cero fallos, errores u omisiones. Incluyen las 25 regresiones de contexto; no se suman otra vez ni se deduplican los nombres de casos parametrizados |
| OpenAPI, tipos, TypeScript, compilación y canario | Correctos; `pip check` limpio |
| Brave, escenario de fiabilidad | 30 visitas y 32 comprobaciones correctas a 360, 390 y 1280 px; seis controles HTTP directos correctos |
| Brave, escenario de cuota | Dos comprobaciones correctas. El contador genérico informa cero visitas, aunque hubo navegación; no se inventa otra cantidad |
| Autoprueba de contención | 2/2; el caso deliberado de plazo agotado obtiene código 124, esperado por la autoprueba, no un fallo del producto |
| Conservación | Los mismos 975 archivos y árbol v2 antes/después; índice real intacto y seis controles públicos de worktrees idénticos |

Estos grupos no se suman como una batería única del proyecto. **No se ejecutó la selección completa de Windows.** No se atribuye la ejecución de Daniel al auditor o a Codex.

Los nombres de archivo y el campo original del recorrido dicen Chromium. El adaptador externo y las dos identidades nativas acreditan **Brave instalado**, plataforma `win32`, motor 156.0.8078.48 y huella de identidad coincidente `70372e06eef532c7e89f13e17569d8f5793f13671b8607a242292f68d0a1cd25`. No se presenta como Google Chrome ni se modifica la evidencia para renombrarla.

## Revisión visual del auditor

El auditor revisó las **16 capturas nativas originales** y no encontró bloqueos visuales. Incluyen tamaños 360, 390 y 1280 px, explicación guardada o ausente, pendientes, muestra insuficiente, seguimiento, retrospectiva, receta y aviso 429. Las tablas se desplazan dentro de regiones enfocables sin desbordar la página; la superbalota permanece aparte y los colores llevan texto.

El resultado original de la ejecución decía que esa revisión estaba pendiente porque fue generado antes del dictamen. Se conserva ese dato original; la auditoría posterior acredita la revisión terminada. Codex no repitió esa inspección ni generó capturas nuevas. Esto no es una certificación general de accesibilidad: la revisión final de navegación, móvil y accesibilidad sigue en 9.5.

## Correcciones F93-REL-01 y F93-LIM-01

**Correspondencia de fiabilidad.** La cartera elegida conserva identidad y corte. Antes de mostrar sus cifras o receta se contrasta juego, filtro de objetivos, línea completa, modelo, versión, perfil y referencia registrada por clave y número compatibles. Si no se acredita la correspondencia, se informa explícitamente la ausencia sin mostrar cifras ajenas y se conserva «Fiabilidad general de la configuración actual». Cambiar de selección invalida respuestas anteriores y vuelve al estado manual.

**Presupuesto.** La carga automática en frío solicita catálogo (una ficha) y predicción (tres): **cuatro fichas**, dentro del máximo de seis. La fiabilidad añade tres solo mediante acción explícita. Con cuota de seis, la carga inicial cabe; si la acción posterior recibe 429, conserva la predicción visible, deshabilita el reintento durante la espera y no consulta automáticamente. Se comprobó un reintento explícito posterior.

`hasta` filtra objetivos; no acredita que una emisión o un informe estuvieran disponibles al generar la cartera. La consulta general conserva su semántica de configuración actual. El diagnóstico API **3/4 esperado** pertenece a la investigación anterior y no es una prueba nativa fallida; no se convierte artificialmente en 4/4. La explicación y las importancias siguen siendo las guardadas, no nueva inferencia o recálculo.

## Antecedentes Linux separados

- Claude ejecutó sobre v1 las baterías y recorridos descritos en la [guía de frontend](fase9_frontend.md#entrega-93-explicación-clasificación-de-candidatos-y-fiabilidad).
- El auditor ejecutó sobre v1 otras 413 pruebas API/pasarela y 665 de frontend en Linux/Python 3.12.14 y reprodujo los dos hallazgos con sondas. No se suman con Claude ni con Windows.
- Codex Cloud verificó la v2 con 37 pruebas Python, 36 frontend (incluidas las 25 nuevas) y tres genéricas; otras 34 quedaron deseleccionadas por filtro. Sondas originales de pantalla 3/3 y cuatro fichas automáticas; contrato/tipos/build/canario correctos y dos recorridos focales Chromium/Linux solo a 1280 px. El diagnóstico API conservó el 3/4 esperado.

Estos son antecedentes de implementación, no nuevas ejecuciones de este cierre. El cierre solo verifica documentos, sus guardas existentes afectadas y el parche. No repite las 415/690 nativas, las baterías Linux, navegador, entrenamiento, mediciones, SQL, ciclos ni esperas operativas.

<a id="actualizacion-real-de-fase-6-del-27-de-octubre"></a>

## Actualización real de Fase 6 del 27 de octubre

Captura de Daniel del **27 de octubre de 2026, 10:21:37, America/Bogota**, auditada en modo de solo lectura. Resuelve la observación de incorporación de novedades reales con el horario nuevo en los cuatro juegos, posterior al antecedente de las 00:11 que aún no tenía novedades. No es parte de las pruebas sintéticas de 9.3 ni fue ejecutada por Codex.

| Juego | Último anterior → nuevo | Cantidad anterior → final | Incorporación (Bogotá) | Nuevo objetivo | Fecha del objetivo |
| --- | --- | --- | --- | --- | --- |
| BALOTO | 2726 → 2727 | 646 → 647 | 01:30:22 | 2728 | 2026-10-28 |
| BALOTO_REVANCHA | 2726 → 2727 | 646 → 647 | 01:30:49 | 2728 | 2026-10-28 |
| MILOTO | 629 → 630 | 98 → 99 | 00:15:21 | 631 | 2026-10-27 |
| COLORLOTO | 229 → 230 | 229 → 230 | 01:20:22 | 231 | 2026-10-29 |

Cada incorporación registra sincronización `completado` con `nuevos: 1` y la siguiente `prediccion_explicada` en `exito`, cartera `terminado` y explicación `guardada`. Los cuatro estados finales son `correcto`, sin error ni fallos consecutivos reportados.

En los **20 ciclos automáticos conservados** hay **33 consultas programadas**: ocho de MILOTO, nueve de BALOTO, nueve de BALOTO_REVANCHA y siete de COLORLOTO. No se repiten parejas juego/oportunidad ni constan fallos de sincronización o huecos reportados. Los **29 intentos anteriores sin novedad no emitieron una predicción nueva**. No se presentan los 20 ciclos como todos los posibles inicios del Programador.

La configuración operativa y las selecciones de modelos se conservan frente a la observación anterior. La tarea **`LP6-01023009031fcabd`, versión 2**, conserva su plan, está habilitada en `Ready` y tiene último resultado cero. Las revisiones históricas v3/v4 de entrega no son versiones de esa tarea. Huella del plan: `a56306a3700c8363657b1ef150dc2c0b834d5cab01be391cf1f519cd6a9e4f6b`. Próximo inicio informado en la captura: 27 de octubre a las 22:30.

**Límite pendiente:** el último inicio informado es **09:24:45**. No se acreditó un disparo exactamente a las **09:00**, ni un caso de **recuperación matinal con resultados pendientes**: los cuatro juegos habían terminado de actualizarse durante la madrugada y no hay consultas de recuperación en esos ciclos conservados. Tampoco se declara resuelta la limpieza histórica de tareas o raíces pendientes.

El dictamen acredita estados y registros de las capturas recibidas, no un nuevo volcado completo de PostgreSQL o una exportación de todos los artefactos para verificar cada fila histórica. No se ejecutaron ciclos manuales ni se alteró tarea, plan, código, configuración o almacenes. La observación de Fase 6 sigue separada del cierre sintético de 9.3.

## Conservación y próximos pasos

El código de producto, pruebas, snapshots, OpenAPI, tipos, configuración, dependencias, lockfiles y workflows de la v2 aprobada permanecen byte idénticos. Solo cambian los diez documentos autorizados y se añade este informe. El cierre conserva el checkout principal y la referencia v2; el informe histórico de 9.2 mantiene su cuerpo completo y recibe una actualización posterior fechada. Inventario, huellas, árbol final y aplicación/reversión figuran en la entrega documental, sin preparar un commit en el índice real.

Daniel publicará manualmente después de revisar este cierre. No hay PR, commit o checks nuevos de 9.3 que citar. El CI del nuevo PR y la integración siguen pendientes. El plan aceptado conserva cinco partes: 9.1 y 9.2 integradas; 9.3 validada y auditada, pendiente de integración; 9.4 consultas de modelos, carteras y resultados guardados; 9.5 exportación, impresión y revisión final de navegación, móvil y accesibilidad. Administración y operación continúan en HTMX; gráficos nuevos después. No se inicia 9.4 ni 9.5 y la Fase 9 global sigue abierta.

Se mantienen `experimental_no_acreditado`, AE-39 **NO-GO** y `AUTORIZA_EVALUACION = False`. La aprobación técnica y funcional no acredita ventaja predictiva ni acreditación prospectiva. Sin commit, push, PR, merge o despliegue, ni acceso a la operación real de Daniel.
