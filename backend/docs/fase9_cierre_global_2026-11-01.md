# Fase 9 — cierre global (1 de noviembre de 2026)

**Estado:** Fase 9 **cerrada** en su alcance de consulta acordado.
- **Integración:** las cinco entregas del plan aceptado están integradas en `main`: 9.1 en el PR #100, 9.2 en el #101, 9.3 en el #102, 9.4 en el #104 y 9.5 en el #105.
- **Fuera del alcance de consulta:**
  - administración y operación permanecen en la consola HTMX;
  - los gráficos nuevos y las fases 10–11 conservan su planificación.
- **Se mantienen:** `experimental_no_acreditado`, AE-39 **NO-GO** y `AUTORIZA_EVALUACION = False`. Ninguna consulta, exportación o impresión acredita ventaja predictiva.

Este documento consolida resultados ya acreditados en los informes de cada entrega, sin volver a ejecutarlos ni sumarlos:
- **Atribución:** las ejecuciones nativas son de Daniel en Windows; las auditorías, de los auditores indicados en cada informe; el CI, de GitHub Actions. Ninguna se atribuye al entorno que prepara este cierre.
- **Baterías:** las que se solapan no se suman.
- **No evaluables:** siguen siendo no evaluables.

## Fuente del cierre

- **Base:** `main` en `bad7c8d5bb913d3d780dd4dfa3b6cdcd9f2dad3e`, merge del PR #105. Árbol `e7092e157457530e6952cd5830f1484ad56aa34b`, 1044 archivos públicos.
- **Cabeza del PR:** `b3f78dd9725790d6a5a506ca5a98b0a8125e3d60`, con el mismo árbol.
- **Rama `feature/fase9-5-exportacion-impresion`:** retirada; ya no figura en el repositorio.
- **Alcance de este cierre:** solo cambia documentos de estado. No modifica código, pruebas, dependencias, workflows, comandos de arranque ni la operación de Fase 6.

## Integración y CI por entrega

| Entrega | PR y merge | CI del PR | Ejecuciones |
|---|---|---|---|
| 9.1 | #100, `9966a4bbcb8d81953fb283b07544636f4c11fc95` | Cinco trabajos aprobados: Node 22, Node 24, Chromium/Linux, Python/Linux y Python/Windows | `40170056131`, `40170056088` |
| 9.2 | #101, `ed0ee427f7a6fcd2a33cbc538435a3df2e299710` (incluye el arreglo de pruebas `e38362bf2341cb30389141c67eb37b5b89a6e2fe`) | Cinco checks aprobados | `40291140855`, `40291140889` |
| 9.3 | #102, `4f4dd639581168b08c95816660f80fc4f735b1ac` | Cinco trabajos aprobados | `40589232731`, `40589232763` |
| 9.4 | #104, `9fde216c5667bd7a1ddb8553a73857f5cfb07e61` | **Bloqueado por facturación:** los cinco trabajos figuran como `failure` sin haber arrancado; no son pruebas aprobadas ni fallidas | `40834824739`, `40834824733` |
| 9.5 | #105, `bad7c8d5bb913d3d780dd4dfa3b6cdcd9f2dad3e` | Cinco trabajos aprobados: Node 22, Node 24, Chromium/Linux, Python/Linux y Python/Windows | `41327381044`, `41327381002` |

- **CI de 9.4:** los checks del PR #105 son posteriores. Se ejecutaron sobre un árbol que ya contiene la 9.4, pero no convierten en aprobados los trabajos originales del #104, que no llegaron a ejecutarse.
- **CI de la 9.1:** sus checks del PR #100 no constaban en los documentos de la fase; se registran aquí tras consultarlos en GitHub.

## Matriz final de compromisos

Cada fila relaciona un compromiso del plan aceptado con su implementación, validación, auditoría e integración. El detalle y la procedencia de cada cifra están en los informes enlazados.

| Entrega | Compromiso | Implementación | Validación (Linux y Windows nativo con Brave) | Auditoría | Integración |
|---|---|---|---|---|---|
| 9.1 | SPA de consulta de `/api/v1` para los cuatro juegos: inicio, juegos y reglas, ficha y resumen con frescura, sorteos con filtros y detalle, panel y métricas del índice, predicción guardada, simulaciones y salud | `frontend/` (React 19, TypeScript, Vite) | Linux/Cloud y Windows 11 sobre datos sintéticos: 379 Vitest, 186 pruebas de pasarela y 92 de API; seis recorridos Brave (297 visitas del normal y 12 de Vite), sonda de plazo y 14 controles HTTP | Aprobada, con el ajuste v2 F9-LIM-01 ([informe](fase9_validacion_operador_2026-10-25.md)) | PR #100 |
| 9.1 | Pasarela local con la clave en el servidor, solo GET del OpenAPI versionado | `backend/app/pasarela/` | La misma cadena de 9.1 | La misma | PR #100 |
| 9.2 | Páginas de las métricas anteriores (12 en Baloto y Revancha, 11 en MiLoto, 31 en ColorLoto) en el mismo índice y ruta de métrica | Recetas existentes, contrato tipado y paginación de tríos | Windows: 772 pruebas Python, 456 Vitest y Brave con 507 visitas y 26 comprobaciones; ajustes v3/v4 con 121 casos únicos en PowerShell 5.1 | Aprobada el 26 de octubre de 2026 ([informe](fase9_2_validacion_operador_2026-10-26.md)) | PR #101 |
| 9.2 | Horario de consulta por juego de Fase 6 | Plan y tarea por juego | Ensayo nativo B con el Programador real y un testigo sintético; después Daniel lo aplicó a la tarea real | La misma | PR #101 |
| 9.3 | Explicación guardada, clasificación de candidatos con la referencia uniforme y pares número-color de ColorLoto | Pantalla de predicción y proyección compatible de `…/predicciones` | Windows: 415 pruebas API/pasarela y 690 Vitest; Brave con 30 visitas, 32 comprobaciones, 6 HTTP y 2 de cuota | Aprobada, con 16 capturas revisadas ([informe](fase9_3_validacion_operador_2026-10-27.md)) | PR #102 |
| 9.3 | Fiabilidad observada por consulta explícita, atribuida solo con contexto coincidente; carga automática de 4 fichas | `GET …/fiabilidad` (`hasta`) y pantalla propia | La misma cadena de 9.3, con 25 regresiones de contexto | La misma | PR #102 |
| 9.4 | Modelos realmente registrados, carteras de Producto 5 y resultados de Producto 6, solo de lectura, con filtros y paginación en la URL | Consultas `…/modelos-guardados`, `…/carteras-guardadas` y `…/resultados`; v2 con F94-ROB-01 | Windows: 173 pruebas backend y sonda 3/3; 780 Vitest; Brave con 87 visitas, 15 comprobaciones, 8 HTTP y 88 capturas | Aprobada, con revisión visual de las 88 capturas; aceptación documental de cinco descripciones 422 de OpenAPI ([informe](fase9_4_validacion_operador_2026-10-28.md)) | PR #104 (CI bloqueado; ver arriba) |
| 9.5 | Exportación JSON versionada y CSV de la consulta cargada, con precisión, ausencias explícitas, protección frente a fórmulas, contexto y página visible; cero solicitudes y cero fichas | `frontend/src/exportacion/` y barras de exportación | Windows v1: 864 Vitest y recorrido normal con 193 descargas; cinco escenarios finales con 50 descargas | Aprobada ([informe](fase9_5_validacion_operador_2026-11-01.md)) | PR #105 |
| 9.5 | Impresión explícita con restauración de desplegables, y pares número/color legibles en PDF | `window.print()`, estilos de impresión y ajuste F95-PDF-01 | Ensayo F95-NAT-01: 167 criterios aprobados, 0 fallidos y 60 no evaluables. F95-PDF-01: 36/36 criterios y 12/12 PDF. Prueba manual con ventana retenida | Hallazgos F95-NAT-01 y F95-PDF-01 cerrados | PR #105 |
| 9.5 | Revisión de navegación, móvil y accesibilidad (no es una certificación general) | Salto al contenido, nombres accesibles, foco y regiones de tabla | Recorridos a 360/390/1280 px con el alcance efectivo documentado | Aprobada con revisión visual de muestras identificadas | PR #105 |

**Matriz de huecos:** la de la [guía de la Fase 9](fase9_frontend.md#matriz-de-huecos-de-la-fase-9) conserva lo que queda fuera:
- escrituras administrativas, generación, entrenamiento y automatización, que siguen en HTMX y requieren la autenticación de escritura de la Fase 10;
- gráficas nuevas, que se sustituyen por tablas;
- operación automática y panel diario.

## Criterios de finalización

El ROADMAP fijó como criterio completar y auditar las cinco partes aceptadas, sin duplicar lógica de negocio en el frontend y sin sustituir la administración de HTMX.

**Evaluación:**
- Las cinco partes están implementadas, validadas en Linux y en Windows nativo con Brave, auditadas e integradas.
- La SPA presenta lo que informa la API, sin recalcular probabilidades, posiciones, variables ni importancias.
- La administración sigue en HTMX.

**Bloqueos:** **no se detectó ningún bloqueo del alcance acordado.** Se examinaron las salvedades siguientes; ninguna es un compromiso incumplido:

- **CI original de 9.4:** el CI no es un criterio por entrega. La validación y auditoría de 9.4 están completas y el CI posterior de #105, sobre un árbol que contiene la 9.4, terminó aprobado. Aun así, los trabajos del #104 siguen constando como no ejecutados.
- **No evaluables de impresión** (60 en el focal de F95-NAT-01 y 19 en la tanda final): son el mecanismo de Brave sin ventana (`afterprint_no_emitido`, `impresion_pendiente_en_pestana`, `ciclo_pendiente_en_documento`). La restauración se acreditó con `page.pdf` y con la prueba manual retenida. Siguen siendo no evaluables.
- **Recorrido normal completo de 9.5:** no se repitió sobre la fuente final. Su parte válida de la v1 se consolidó con revalidaciones dirigidas y con la tanda final de cinco escenarios, cuyo alcance efectivo consta en el [informe](fase9_5_validacion_operador_2026-11-01.md).
- **Supervisor 9.5 en Linux (Chromium 153):** daba `ok: false` por su extractor portátil, antes y después de F95-PDF-01. En Brave/Windows pasó con código 0. No se convierte en éxito.

## Limitaciones y pendientes conservados

- **Supervisor Vite/NO_COLOR:** el orquestador versionado `tests/recorrido_fase9.py` no propaga `NO_COLOR` a Vite. En Windows, los códigos ANSI pueden impedir reconocer la dirección de arranque. La validación de 9.1 lo sorteó con un supervisor externo. El defecto sigue sin corregir y se trata aparte.
- **Fase 6 (operativo, fuera de la Fase 9):** el último inicio informado, 09:24:45, no acredita un disparo exacto a las 09:00. La recuperación matinal con resultados pendientes sigue sin observarse y la limpieza histórica de tareas y raíces sigue pendiente. Este cierre no consulta el Programador, SQL ni servicios, ni ejecuta ciclos.
- **OpenAPI:** la aceptación de cinco descripciones 422 es documental; los JSON completos no son idénticos.
- **Revisión visual y accesibilidad:** la revisión visual de capturas y PDF cubre muestras identificadas, no todas las páginas. No es una certificación general de accesibilidad.
- **Otras limitaciones de la guía:** cuota y monitoreo por proceso, pasarela solo de loopback, colores fuera de la paleta y formato `texto`/`tipo_p` ([limitaciones conocidas](fase9_frontend.md#limitaciones-conocidas)).
- **Fases siguientes:** la Fase 10 (despliegue) y la Fase 11 (aplicación personal) conservan su planificación; este cierre no las inicia.

## Verificación de este cierre

Se verificaron codificación, enlaces y anclas nuevos, coherencia de estados y diff. Se ejecutaron solo las guardas documentales afectadas y se comprobaron la aplicación y reversión del parche en una copia limpia.

Los enlaces rotos heredados identificados en el cierre de 9.5 (anclas de 9.3 y de ARCHITECTURE) se conservan sin corregir. No hubo commit, push, PR, merge, Actions, SQL, Programador, ciclos operativos ni despliegue; Daniel publicará manualmente tras la revisión de Codex.
