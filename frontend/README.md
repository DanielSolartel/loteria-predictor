# Frontend de consulta (Fase 9.1)

SPA React 19 + TypeScript + Vite que consulta la API pública `/api/v1` a través de la pasarela local (`backend/app/pasarela/`). No contiene claves ni lógica de negocio: presenta lo que informa la API. Diseño, decisiones, límites y verificación: [backend/docs/fase9_frontend.md](../backend/docs/fase9_frontend.md). Protocolo de Windows: [backend/docs/fase9_windows.md](../backend/docs/fase9_windows.md).

La entrega 9.3 v2 añade un botón «Consultar fiabilidad» en la predicción guardada. La carga automática nueva o recargada cuenta todas las peticiones, incluido el catálogo: 1 + 3 = 4 fichas (máximo autorizado 6); la fiabilidad cuesta 3 solo por acción explícita. Se muestra como evidencia de la cartera únicamente cuando corresponde su contexto de línea/perfil/versión registrada; en otro caso se informa la ausencia y se conserva la consulta general identificada como configuración actual. `hasta` filtra objetivos y no acredita disponibilidad temporal.

**Plan acordado de cinco partes, completado.** 9.1, 9.2, 9.3, 9.4 y 9.5 están integradas en los PR #100, #101, #102, #104 y #105. La 9.4 implementa consultas de modelos registrados, carteras de Producto 5 y resultados de Producto 6, solo de lectura, sobre el merge exacto del PR #102. La v2 está validada en Linux y Windows nativo con Brave y aprobada por auditoría e integrada en PR #104; CI bloqueado por facturación, con cinco jobs sin ejecutar. La 9.5 implementa exportación e impresión de la consulta ya cargada y revisa navegación, móvil y accesibilidad; validada en Windows con Brave, auditada e integrada en PR #105 con sus cinco trabajos aprobados. Administración y operación permanecen en HTMX; los gráficos nuevos quedan para después. La Fase 9 quedó cerrada el 1 de noviembre de 2026 en su alcance de consulta ([cierre global](../backend/docs/fase9_cierre_global_2026-11-01.md)).

**Validación 9.3 v2:** Daniel ejecutó en Windows 11/Python 3.14.6 las 415 pruebas API/pasarela y, con Node 24.15.0, 690 Vitest (incluidas las 25 regresiones de contexto), sin fallos, errores u omisiones. Brave: 30 visitas y 32 comprobaciones a 360/390/1280 px, seis controles HTTP y dos comprobaciones de cuota; contador genérico de cuota: cero visitas. El auditor revisó 16 capturas sin bloqueos visuales. Contrato, tipos, compilación y canario correctos; no se atribuyen estos resultados a Codex ni se suman a Linux. [Cierre y pendientes](../backend/docs/fase9_3_validacion_operador_2026-10-27.md).

## Consultas guardadas (Fase 9.4)

Base exacta `4f4dd639581168b08c95816660f80fc4f735b1ac`, merge del PR #102 que integró 9.3 con sus cinco checks aprobados. La 9.4 añade, para los cuatro juegos, modelos registrados y fichas de versiones, carteras guardadas de Producto 5 y emisiones/resultados de Producto 6 con sus filtros, paginación y agregados existentes. No se confunde el catálogo de candidatos con los modelos que realmente existen, ni una cartera de Producto 5 con la predicción de 9.3.

La SPA consulta `…/modelos-guardados`, `…/carteras-guardadas` y `…/resultados` por la misma pasarela, sin clave en navegador ni lecturas locales. Con catálogo frío, listados y fichas explícitas de modelos/carteras cuestan 3 fichas (1 + 2), y resultados 6 (1 + 5). No precarga detalles ni paneles secundarios. URL, cancelación/contexto, cuota y reintento manual se conservan; un resultado pendiente no se transforma en cero aciertos. No se genera, entrena, infiere, repara ni guarda un informe.

**Validación 9.4 v2 aprobada.** Daniel completó Windows 11/Python 3.14.6, Node 24.15.0 y npm 11.12.1: 173 pruebas API/pasarela y sonda 3/3 retenidas de la primera corrida, sin repetir, y 780 Vitest nuevos en la continuación Windows, con tipos, TypeScript, build y canario correctos. Brave instalado (motor 156.0.8078.48, Playwright 1.56.1) recorrió cinco escenarios a 360/390/1280 px: 87 visitas, 15 comprobaciones de navegador, ocho controles HTTP y 88 capturas. Cuota tiene cero visitas en el contador genérico aunque sí navega y aporta una comprobación, con 429/`Retry-After`, sin bucle automático y recuperación explícita. La auditoría visual posterior aprobó las 88 capturas; el pendiente del registro original se conserva como histórico. No es certificación general de accesibilidad.

El control externo de OpenAPI aceptó exclusivamente cinco descripciones de respuesta 422: `Unprocessable Entity` en el versionado y `Unprocessable Content` en el generado Windows; el resto del JSON completo coincide. Conserva ambos documentos y la diferencia, con `documentos_json_iguales=false`, sin cambios del contrato funcional, OpenAPI versionado o tipos. La entrega sigue siendo v2. Los resultados Linux y las baterías/capturas de 9.3 conservan su procedencia, sin sumarse a Windows. La 9.4 está integrada en PR #104; sus cinco jobs de CI no arrancaron por el bloqueo de facturación. *Actualización (1 de noviembre de 2026):* la 9.5 se integró en PR #105 y la Fase 9 quedó cerrada ([cierre global](../backend/docs/fase9_cierre_global_2026-11-01.md)); los checks de #105 no convierten en aprobados los trabajos originales de #104. Se mantienen `experimental_no_acreditado`, AE-39 **NO-GO** y `AUTORIZA_EVALUACION = False`. [Validación y límites](../backend/docs/fase9_4_validacion_operador_2026-10-28.md); [diseño y matriz](../backend/docs/fase9_frontend.md#entrega-94-modelos-carteras-y-resultados-guardados); [validación nativa](../backend/docs/fase9_windows.md#entrega-94-validación-nativa-completada).

## Exportación e impresión (Fase 9.5)

Base exacta `9fde216c5667bd7a1ddb8553a73857f5cfb07e61`, merge del PR #104; árbol `f9457d74310aa199f7a569ec0362c7a9acc4653e`, 1028 archivos públicos. Los workflows de 9.4 `40834824739` y `40834824733` figuran como `failure` porque sus cinco jobs no arrancaron por facturación; no acreditan pruebas aprobadas o fallidas y no se modifican ni reintentan aquí.

Descargas JSON/CSV por acción explícita e impresión con los datos de la consulta ya cargada: cero solicitudes de red o fichas adicionales. Exportar una lista significa sólo la página visible. Se conserva la precisión y el contexto del dato público decodificado; CSV ofrece selección de tablas y protección de cadenas frente a fórmulas, sin ejecutar ni cargar estimadores. La fiabilidad mantiene la atribución completa de 9.3 y nunca se consulta al exportar o imprimir. Se revisan las 14 superficies de datos y las rutas sin descarga útil, los cuatro juegos y las anchuras móvil/escritorio, sin convertir los controles automatizados en certificación general de accesibilidad.

Validación nueva Linux: 864/864 Vitest, recorrido normal de 177 visitas y 193 descargas reales; doce PDF finales con revisión visual de siete páginas identificadas. Los escenarios y las revisiones parciales conservan su atribución en la guía.

**Validación nativa y auditoría completadas (1 de noviembre de 2026).** En Windows con Brave 156.0.8078.74 se retienen de la v1 las 864 Vitest y el recorrido normal (177 visitas y 193 descargas), con sus 24 fallos históricos de restauración tras `window.print()` sin `afterprint`. F95-NAT-01 corrigió solo el ensayo: las restauraciones se acreditan con `page.pdf` y los clics sin `afterprint` quedan como no evaluables, no como aprobados. F95-PDF-01 corrigió la impresión de los pares número/color de ColorLoto en tablas estrechas. Ambos, y la última tanda de cinco escenarios, están aprobados por Codex. El recorrido normal completo no se repitió sobre la fuente final. [Evidencia y límites](../backend/docs/fase9_5_validacion_operador_2026-11-01.md).

[Formato, matriz, evidencia Linux y límites](../backend/docs/fase9_5_exportacion_impresion.md). Integrada en PR #105 (merge `bad7c8d5bb913d3d780dd4dfa3b6cdcd9f2dad3e`), con los cinco trabajos aprobados (workflows `41327381044` y `41327381002`); Fase 9 cerrada en su alcance de consulta ([cierre global](../backend/docs/fase9_cierre_global_2026-11-01.md)). Las baterías y aprobación visual de 9.4 conservan su atribución histórica; no acreditan el código nuevo. Administración y operación siguen en HTMX. No se inicia Fase 10 ni se altera Fase 6.

## Requisitos

Node ≥ 22.12 (LTS 22 o 24) y npm. Comprobar con `node --version` antes de instalar nada.

## Órdenes

| Orden | Qué hace |
|---|---|
| `npm ci --no-audit --no-fund --ignore-scripts` | instalación reproducible desde `package-lock.json` |
| `npm run tipos:comprobar` | `src/api/esquema.d.ts` coincide con la generación desde `src/api/openapi.json` |
| `npm run typecheck` | TypeScript estricto |
| `npm test` | pruebas de componentes (Vitest + Testing Library, en StrictMode) |
| `npm run build` | compila en `dist/` (sin mapas de código ni recursos externos) |
| `npm run canario` | compila con un canario en el entorno y comprueba que no llega al bundle; busca envío de credenciales, almacenamiento y recursos de terceros |
| `npm run tipos` | regenera `src/api/esquema.d.ts` (tras exportar el OpenAPI con `python -m scripts.exportar_openapi_publica ../frontend/src/api/openapi.json` desde `backend/`) |
| `npm run dev` | Vite en `127.0.0.1:5173`, con reenvío a la pasarela (ver abajo) |

## Uso local

Desde `backend/`:

1. API pública: `uvicorn app.api.publica.aplicacion:app --host 127.0.0.1 --port 8010 --no-access-log --no-proxy-headers` (con la huella de la clave en `API_PUBLICA_CLAVES`).
2. Pasarela: `uvicorn app.pasarela.aplicacion:app --host 127.0.0.1 --port 8020 --no-access-log --no-proxy-headers` (con la clave en `PASARELA_CLAVE_API` o en `backend/pasarela.privado.env`, fuera de Git).
3. Abrir `http://127.0.0.1:8020/`.

**Modo desarrollo:** `npm run dev` reenvía `/api/v1` y `/pasarela` a `PASARELA_URL` (por defecto `http://127.0.0.1:8020`) sin cambiar `Host`. La pasarela solo lo acepta si se añaden de forma explícita `127.0.0.1:5173` a `PASARELA_HOSTS` y `http://127.0.0.1:5173` a `PASARELA_ORIGENES`.

## Estructura

- `src/api/` — OpenAPI versionado y tipos generados, decodificadores de presentación (`presentacion.ts`), cliente de la pasarela (`cliente.ts`) y formato (`formatos.ts`).
- `src/usos/consulta.ts` — carga con cancelación; descarta respuestas antiguas.
- `src/componentes/`, `src/pantallas/` — marco, estados y errores, tablas y pantallas.
- `src/pruebas/` — respuestas SINTÉTICAS producidas por la API real (`python -m tests.generar_respuestas_fase9 ../frontend/src/pruebas/respuestas` desde `backend/`) y casos de formato de la consola HTMX. Al regenerarlas cambian también la fecha de consulta, los días de frescura, UUID, horas y latencias; la 9.3 solo incorporó las respuestas que cambian por su contrato (predicciones y fiabilidad) y `formatos.json`.
- `scripts/` — comprobación de tipos y canario. `e2e/recorrido.mjs` — recorrido de Chromium que lanza `python -m tests.recorrido_fase9` desde `backend/`. `e2e/exportacion.mjs` — recorrido 9.5 que lanza `python -m tests.recorrido_fase95`; observa la impresión con `e2e/impresion.mjs` (regresiones: `node e2e/impresion-regresiones.mjs --salida <carpeta nueva>`).
