# Fase 9.4 v2 — validación del operador y cierre documental del 28 de octubre de 2026

**Estado:** v2 validada en Linux y Windows nativo con Brave y aprobada por auditoría. El cierre documental queda preparado para revisión; publicación manual de Daniel, integración y CI de 9.4 permanecen pendientes. La Fase 9 global sigue abierta.

Guías relacionadas: [consultas y alcance del frontend](fase9_frontend.md#entrega-94-modelos-carteras-y-resultados-guardados), [validación nativa completada](fase9_windows.md#entrega-94-validación-nativa-completada), [salvedad documental de HTTP 422](fase8_api_publica.md#cierre-de-validación-94-salvedad-documental-de-http-422) y [frontend](../../frontend/README.md). Los [antecedentes de 9.3](fase9_3_validacion_operador_2026-10-27.md) conservan su fecha y atribución.

## Fuente aprobada y procedencia

Repositorio `DanielSolartel/loteria-predictor`. Base integrada `4f4dd639581168b08c95816660f80fc4f735b1ac`, merge del PR #102, árbol `3aa63d583a9c4df7a139b7eafe5a161fadcbe441`, 976 archivos públicos. El PR #102 y sus cinco comprobaciones aprobadas corresponden a **9.3/base**. No son resultados de CI de 9.4.

La fuente aprobada de 9.4 v2 es el árbol `8f5be63c3a8f5205356d40504cc426f3eacf06f5`, **1027 archivos** y 71 rutas frente a la base: 51 añadidas, 20 modificadas y ninguna eliminada. Su parche completo mide 573.000 bytes y tiene SHA-256 `8ce3cd3acae37f29e6c8ebbe610f6e69524e2fdc54acd541c43e7d0c57694e70`. Este cierre es un incremental documental sobre esos bytes aprobados; el producto permanece en v2.

Las ejecuciones nativas fueron realizadas por **Daniel**, con datos sintéticos. La auditoría final del **28 de octubre de 2026, America/Bogota**, fue realizada por **Codex**. El paquete recibido para este cierre contiene dictamen, inventarios y evidencia textual saneada; no incluye los ZIP nativos completos ni las imágenes. La verificación de los originales y la revisión visual se atribuyen al auditor que los recibió. Este cierre no vuelve a ejecutar esas pruebas ni revisa otra vez las capturas.

Los JUnit entregados retiraron el atributo `hostname` de las suites y conservaron los casos y resultados. `auditoria/procedencia-junit.json` del paquete de evidencia identifica las huellas originales y las de las copias saneadas. Se mantienen ambas procedencias; el recuento de casos parametrizados no deduplica sus nombres.

## Implementación v2 y F94-ROB-01

9.4 consulta versiones de modelos realmente registrados, carteras guardadas de Producto 5 y emisiones/resultados de Producto 6 para BALOTO, BALOTO_REVANCHA, MILOTO y COLORLOTO. Reutiliza los lectores y agregaciones existentes mediante API pública y pasarela. La lectura de metadatos no deserializa un estimador para ejecutarlo, no entrena, no repara artefactos ni genera otra cartera. Los cortes de entrenamiento, entrada, objetivo y observación conservan sus significados; un filtro por objetivo no acredita disponibilidad anterior de una emisión.

F94-ROB-01 queda cerrado en v2. La sonda original sin modificar dio **1/3, código 1** sobre v1: pasaba el control completo y las dos carteras sin metadatos provocaban 500 en listado y ficha. En v2 dio **3/3, código 0**. Un corte necesario ausente produce un elemento `alterado` en el listado, conserva las carteras sanas y devuelve 409 `alterado` al abrir esa ficha. El nombre opcional ausente se publica como `null` con 200 y los demás datos acreditados. No se completan valores con la configuración actual, otra versión o un artefacto ajeno.

La validación de forma y tipos se contiene por artefacto en la proyección. Los errores ajenos mantienen su semántica. La sonda y las regresiones comprueban canon, huellas, lector real e identidades; durante los GET bloquean escrituras, entrenamiento, carga/inferencia y trabajadores y cotejan los almacenes antes/después.

## Cadena nativa de Daniel

| Archivo original | Bytes | SHA-256 | Resultado y procedencia |
| --- | ---: | --- | --- |
| `f94-validacion-v2-d5a768db.zip` | 15.812 | `1db678fa1c926a1e0bedda7f6e9ba703a94ec56d19ffae23bc9777370274be6a` | Fuente, contención, 173 pruebas backend y sonda 3/3 correctas; detención en la comparación textual de OpenAPI |
| `f94-reanudacion-v2-f758ca05.zip` | 55.662 | `245c6185ce411cafc20507de9f560b818fc11ff15e1b7087662852c5f39ac326` | Fuente y entorno conservados; captura de las cinco diferencias documentales de OpenAPI |
| `f94-continuacion-v2-1463b159.zip` | 8.065.139 | `b01863f316315ec507e18808a5b6022a85fb0ff79edcc5a80164dcd2f028f829` | Código 0; frontend y cinco escenarios Brave completados, con fuente y orígenes conservados |

El auditor comprobó CRC, rutas seguras, miembros únicos y las referencias entre los tres ZIP. El último contiene 149 miembros, incluidas 88 capturas. La primera corrida transcurrió de 21:48:28 a 21:54:31; la reanudación diagnóstica, de 22:12:25 a 22:14:10; y la continuación, de 22:22:10 a 22:28:42, todas el 28 de octubre en Bogotá. Los registros originales conservan instantes UTC del 29 de octubre. Son tres corridas relacionadas; las pruebas retenidas no se presentan como nuevas ejecuciones completas.

| Verificación nativa | Resultado y atribución |
| --- | --- |
| Backend API/pasarela | **173 aprobadas**, cero fallos, errores u omisiones; retenidas de d5a768db sin repetir |
| Sonda original | **3/3**, código 0, sin escrituras ni trabajos durante GET; retenida de d5a768db sin modificar |
| Contención de procesos | **2/2** de la primera corrida; código **124 esperado** en el ensayo deliberado de plazo |
| Entorno | Windows 11, Python 3.14.6 x64, 58 paquetes instalados contrastados y `pip check` correcto; Node 24.15.0 y npm 11.12.1 |
| Frontend Vitest | **780 aprobadas nuevas en Windows** en 1463b159, cero fallos, errores u omisiones |
| Tipos, TypeScript, compilación y canario | Correctos en 1463b159; el comprobador no detectó credenciales, almacenamiento ni recursos externos |
| Conservación | Los mismos 1027 archivos y árbol v2 antes/después; índice y controles públicos de ocho worktrees conservados |

La sonda original conserva una leyenda fija que dice «Linux». La atribución de esta ejecución a Windows procede de los registros y metadatos del supervisor nativo, sin modificar la sonda para cambiar esa leyenda.

Los ensayos usaron SQLite, almacenes sintéticos aislados, API y pasarela reales y SPA compilada. No constituyen una nueva batería de PostgreSQL, ML ni operación de Fase 6. Tampoco se ejecutaron la selección completa de Windows, la suite completa o mediciones por esta validación.

## Salvedad documental cerrada de OpenAPI

Los bloqueos de las primeras dos corridas pertenecieron al control documental de OpenAPI. El cotejo completo del auditor encontró **exactamente cinco diferencias**, todas en `get/responses/422/description` de estas rutas nuevas:

- `/api/v1/juegos/{codigo}/modelos-guardados`.
- `/api/v1/juegos/{codigo}/modelos-guardados/{clave}`.
- `/api/v1/juegos/{codigo}/carteras-guardadas`.
- `/api/v1/juegos/{codigo}/carteras-guardadas/{clave}`.
- `/api/v1/juegos/{codigo}/resultados`.

En esos cinco valores, el documento versionado dice `Unprocessable Entity` y el generado en Windows dice `Unprocessable Content`. **Todo el resto del documento completo coincide**, incluidos rutas, métodos, códigos, seguridad, esquemas y restricciones. Las descripciones proceden de `http.client.responses` cuando la ruta no las fija. El auditor reprodujo en un proceso aislado Linux la leyenda runtime y obtuvo los mismos bytes y huella del documento nativo; ese contraste conserva su atribución Linux.

El comparador **externo** conserva ambos documentos y su diferencia. Acepta exclusivamente las cinco leyendas auditadas con el valor runtime correspondiente y rechaza cualquier cambio adicional. Registra `documentos_json_iguales=false` y `cinco_descripciones_422_auditadas_aceptadas=true`; no declara igualdad completa de JSON ni excluye campos del cotejo. No se anuló una comprobación de deriva del contrato.

| Documento conservado | SHA-256 |
| --- | --- |
| OpenAPI versionado | `e8c879b4c329defa329915b215b64ede55cd5f05e3c87e6a8378be342ba181a5` |
| OpenAPI generado en Windows | `c03e5c523f09522960a358a8382326f10b774a6bea22333a89c0c9344ccf85aa` |

La aceptación cierra una salvedad documental de validación. El producto, el contrato funcional, el OpenAPI versionado y los tipos permanecen sin cambios; no se creó una entrega v3 por las revisiones del supervisor externo. La [guía de API](fase8_api_publica.md#cierre-de-validación-94-salvedad-documental-de-http-422) recoge esta misma delimitación.

## Brave nativo y revisión visual posterior

Daniel usó **Brave instalado**, motor **156.0.8078.48**, Playwright **1.56.1**, plataforma `win32` y perfil de ensayo aislado. El ejecutable externo conserva SHA-256 `70372e06eef532c7e89f13e17569d8f5793f13671b8607a242292f68d0a1cd25`. Los resultados originales emplean la etiqueta genérica `Chromium`; la identidad del ejecutable acredita Brave y no una validación de Google Chrome en Windows.

| Escenario | Visitas | Comprobaciones de navegador | HTTP directo | Capturas |
| --- | ---: | ---: | ---: | ---: |
| Normal, cuatro juegos | 60 | 5 | 8 | 60 |
| Vacío | 9 | 0 | 0 | 9 |
| Alterado | 12 | 6 | 0 | 12 |
| Incompatible | 6 | 3 | 0 | 6 |
| Cuota | 0 | 1 | 0 | 1 |
| **Totales del recorrido** | **87** | **15** | **8** | **88** |

El escenario normal cubre las cinco pantallas de los cuatro juegos a **360, 390 y 1280 px**. El contador genérico de cuota informa cero visitas, aunque sí hubo navegación, espera y una comprobación. Se observaron 429 y `Retry-After`, botón temporalmente deshabilitado, ausencia de bucles de reintento automático y recuperación por acción explícita. La espera sola no envió otra petición.

Las cargas con memoria vacía registran **3 fichas** para catálogo más modelos/carteras y **6 fichas** para catálogo más resultados. Los mapas de huellas de los almacenes sintéticos coinciden antes/después; el compilado de la SPA permaneció intacto durante cada recorrido. No se detectaron canarios ni almacenes ajenos. Los 409 de las fichas alteradas son respuestas esperadas y no fallos de las pruebas.

La auditoría visual **posterior** aprobó las **88 capturas nativas**, sin hallazgos bloqueantes. El auditor las revisó en 22 hojas de contacto internas y amplió dos originales de escritorio para modelos y resultados/colores. Se comprobaron navegación, filtros, estado activo, avisos, ausencia, alteración, incompatibilidad, combinaciones y resultados pendientes. Las tablas anchas mantienen su desplazamiento dentro de la región; se conservan los controles focales de foco por teclado. Los pares número-color llevan número y nombre del color, y los pendientes conservan la ausencia de resultados y métricas observadas, sin convertirse en cero aciertos.

El campo original `revision_humana_de_capturas` decía pendiente porque su ZIP precedía a la auditoría. Se conserva ese registro histórico; la aprobación posterior queda documentada aquí y en el dictamen. Este cierre no redistribuye las imágenes ni acredita otra inspección visual. La revisión de capturas y controles focales no es una certificación general de accesibilidad; su revisión final permanece en 9.5.

## Resultados Linux retenidos y alcance del cierre

La procedencia de las baterías se mantiene separada:

- **Implementación v1, Linux/Cloud:** selección dirigida de 150 backend, 780 frontend y cinco recorridos Chromium/Linux, conservados como evidencia v1.
- **Auditoría Linux de v1:** 150 backend y 89 frontend dirigidas, junto con la sonda 1/3 que identificó F94-ROB-01. Son ejecuciones del auditor y se solapan con las del implementador.
- **Corrección v2, Linux/Cloud:** 23 regresiones nuevas, incluidas en las 173 de la selección dirigida; la sonda original pasa de 1/3 sobre v1 a 3/3 sobre v2. Las 780 frontend y los cinco recorridos de v1 no se repitieron para esa corrección.
- **Validación nativa de Daniel:** 173 backend y sonda 3/3 retenidas de la primera corrida; 780 Vitest y los cinco escenarios Brave ejecutados en la continuación, con aprobación visual posterior del auditor.

Estos grupos no se suman como una suite completa del proyecto. El cierre documental sólo incorpora la evidencia recibida y sus verificaciones de archivos, enlaces y Git; las dos guardas documentales autorizadas se registran por separado en la entrega del cierre. No se repiten backend, sonda, frontend, navegador, mediciones, suite completa, PostgreSQL o Fase 6 por esta edición.

## Conservación, límites y siguiente etapa

Se mantienen los arreglos de contexto de 9.3: catálogo más predicción cuestan **cuatro fichas automáticas** y la fiabilidad requiere acción explícita y coincidencia completa de contexto para atribuirse a una cartera histórica. La administración y la operación permanecen en HTMX; este cierre no añade escrituras, gráficos, exportación, impresión, despliegue ni aplicación personal.

El worktree Windows `loteria-predictor-fase6` pertenece al mismo repositorio de GitHub. La validación no consultó el Programador ni SQL operativo ni ejecutó ciclos; se conservaron sus controles públicos y quedaron intactos la tarea, el entorno, la configuración, el plan y los almacenes operativos. Los antecedentes reales de Fase 6 conservan su atribución: los cuatro juegos incorporaron novedades automáticamente con el horario nuevo. **09:24:45 no acredita disparo exacto a las 09:00 ni recuperación matinal con resultados pendientes**. Esa recuperación continúa sin observarse y este cierre no añade otra comprobación operativa.

Siguen vigentes **`experimental_no_acreditado`**, **AE-39 NO-GO** y **`AUTORIZA_EVALUACION = False`**. La validación no acredita ventaja predictiva.

Quedan pendientes la revisión de este cierre, la publicación manual de Daniel, la integración y el CI de 9.4. No se creó un PR, commit, merge, ejecución de Actions o despliegue de 9.4 en este trabajo ni se cambió facturación. Después de integrar 9.4 queda **9.5: exportación, impresión y revisión final de navegación, móvil y accesibilidad**, todavía planificada. La Fase 9 global permanece abierta.
