# Fase 9 en Windows — 9.1–9.5 integradas; Fase 9 cerrada

**Estado de 9.5:** validación nativa en Windows 11 con Brave y auditoría completadas el 1 de noviembre de 2026; integrada en PR #105 (merge `bad7c8d5bb913d3d780dd4dfa3b6cdcd9f2dad3e`), con los cinco trabajos aprobados (workflows `41327381044` y `41327381002`). [Resumen](#entrega-95-validación-nativa-completada); [validación del operador](fase9_5_validacion_operador_2026-11-01.md). Fase 9 cerrada en su alcance de consulta ([cierre global](fase9_cierre_global_2026-11-01.md)).

**Estado de 9.4 v2:** validada en Linux y Windows nativo con Brave y aprobada por auditoría; integrada en PR #104 (merge `9fde216c5667bd7a1ddb8553a73857f5cfb07e61`); CI bloqueado por facturación, con sus cinco jobs sin ejecutar. [Validación del operador](fase9_4_validacion_operador_2026-10-28.md). El producto continúa siendo v2; las revisiones del supervisor externo no son otra entrega. No repetir baterías, recrear el entorno o reaplicar el parche completo por este cierre documental.

**Estado de la 9.3:** v2 validada en Linux y Windows nativo con Brave y aprobada por la auditoría; integrada en PR #102 (merge `4f4dd639581168b08c95816660f80fc4f735b1ac`), con los cinco trabajos aprobados: Node 22, Node 24, Chromium/Linux, Python/Linux y Python/Windows (workflows `40589232731` y `40589232763`). Son antecedentes de la 9.3, no resultados de la 9.4. [Validación del operador](fase9_3_validacion_operador_2026-10-27.md). El [protocolo dirigido](#entrega-93-protocolo-dirigido) se conserva como referencia: no recrear worktree/entorno ni repetir baterías o aplicar de nuevo el parche completo por este cierre.

**Estado de la 9.2:** validada en Windows 11 nativo por Daniel y aprobada por la auditoría independiente el 26 de octubre de 2026, incluido el ensayo nativo B con el Programador de tareas real. Entonces quedaban pendientes la publicación manual, el CI del nuevo PR y la migración controlada de `LP6-01023009031fcabd`. *Actualización:* la 9.2 se integró en el PR #101 (merge `ed0ee427f7a6fcd2a33cbc538435a3df2e299710`, cinco checks aprobados, con el arreglo de pruebas `e38362bf2341cb30389141c67eb37b5b89a6e2fe`). Daniel migró y activó en Windows `LP6-01023009031fcabd` con el horario por juego. Según la confirmación del auditor (no son pruebas de esta entrega), en la captura del 27 de octubre de 2026 a las 00:11, hora de Colombia, quedaron verificadas nueve ejecuciones programadas y quince consultas en sus franjas: siete de MiLoto, tres de Baloto, tres de Revancha y dos de ColorLoto, sin consultas duplicadas ni fallos de sincronización reportados. Aquella captura no tenía resultados nuevos. La observación posterior del 27 de octubre a las 10:21, auditada sobre la captura de Daniel, acredita una novedad incorporada automáticamente y su siguiente predicción con explicación guardada en cada juego: 20 ciclos conservados, 33 consultas (8 de MiLoto, 9 de Baloto, 9 de Revancha y 7 de ColorLoto), sin parejas juego/oportunidad repetidas ni fallos de sincronización reportados; los 29 intentos sin novedad no emitieron otra predicción. Configuración, selecciones de modelos, tarea versión 2 y plan conservados. El último inicio informado es 09:24:45: no acredita disparo exacto a las 09:00 ni recuperación matinal con resultados pendientes, pues los cuatro juegos terminaron de madrugada. Esa recuperación y la limpieza histórica siguen pendientes. Es operación real observada, separada de las pruebas sintéticas 9.3; Codex no ejecutó ciclos ni SQL operativo. [Actualización real de Fase 6](fase9_3_validacion_operador_2026-10-27.md#actualizacion-real-de-fase-6-del-27-de-octubre). Fase 9 cerrada el 1 de noviembre de 2026 ([cierre global](fase9_cierre_global_2026-11-01.md)); los pendientes operativos de Fase 6 citados siguen abiertos. [Informe de cierre](fase9_2_validacion_operador_2026-10-26.md).

**Estado de la 9.1:** entrega 9.1 v2 validada en Windows 11 nativo por Daniel y auditada el 25 de octubre de 2026. Python 3.14.6, Node 24.15.0, npm 11.12.1 y Brave instalado (motor 156.0.8078.48), con datos sintéticos. Los seis escenarios se consolidan desde dos corridas; no es una nueva batería completa. Publicación manual y checks del PR pendientes; Fase 9 global abierta. *Actualización posterior:* la 9.1 se integró en PR #100 (merge `9966a4b`), con sus cinco checks aprobados (workflows `40170056131` y `40170056088`); la Fase 9 quedó cerrada el 1 de noviembre de 2026 ([cierre global](fase9_cierre_global_2026-11-01.md)). [Detalle de la evidencia](fase9_validacion_operador_2026-10-25.md); [diseño](fase9_frontend.md).


## Entrega 9.5: validación nativa completada

Daniel ejecutó en Windows 11 (Python 3.14.6, Node 24.15.0, npm 11.12.1, Brave instalado con motor 156.0.8078.74 y ejecutable `040bddd110b2f39a5855431e88935f137d909fd6a2a55479c52364a475362f8a`) y Codex auditó. Los resultados no se suman entre sí ni con Linux:

| Ejecución nativa | Fuente | Resultado |
|---|---|---|
| Frontend | v1 | 864 Vitest, tipos, TypeScript, build y canario correctos; retenidos |
| Recorrido normal | v1 | 177 visitas, 193 descargas, 12 PDF; 68/92 comprobaciones: 24 fallos de restauración tras `window.print()` sin `afterprint`, conservados |
| F95-NAT-01, focal | v1 + ensayo | 56 visitas; 227 criterios: 167 aprobados, 0 fallidos, 60 no evaluables |
| F95-PDF-01 | fuente final | 36/36 criterios, 12/12 PDF (63 páginas), supervisor con código 0 |
| Cinco escenarios | fuente final | 21 visitas; 64 criterios: 45 aprobados, 19 no evaluables; 50 descargas; 0 fallos |

El recorrido normal completo no se repitió sobre la fuente final `d68cdc1983e3015f4da4871285647615bc9b9e5b`. Los no evaluables (`ok: null`, `skipped` en JUnit) no son aprobaciones. La conservación acreditada es la de la copia de revisión: 1043 archivos, HEAD, índice y SPA compilada. Evidencias, huellas, alcance efectivo de cada escenario y límites en la [validación del operador](fase9_5_validacion_operador_2026-11-01.md).

*Actualización (1 de noviembre de 2026):* la 9.5 se integró en PR #105 (merge `bad7c8d5bb913d3d780dd4dfa3b6cdcd9f2dad3e`) y su CI terminó con los cinco trabajos aprobados (workflows `41327381044` y `41327381002`). Son checks de GitHub Actions, no ejecuciones nativas de Daniel. [Cierre global de la Fase 9](fase9_cierre_global_2026-11-01.md).

## Entrega 9.5: validación nativa pendiente

*Actualización (1 de noviembre de 2026):* este protocolo ya se ejecutó y la validación está [completada](#entrega-95-validación-nativa-completada). Se conserva como referencia histórica; no repetir baterías por el cierre documental.

La entrega de exportación JSON/CSV, impresión y revisión de navegación, móvil y accesibilidad parte de `9fde216c5667bd7a1ddb8553a73857f5cfb07e61` (PR #104), árbol `f9457d74310aa199f7a569ec0362c7a9acc4653e`, 1028 archivos públicos. [Formatos, matriz y procedimiento](fase9_5_exportacion_impresion.md). La evidencia nueva Linux no acredita Windows nativo; auditoría, publicación y CI de 9.5 siguen pendientes y la Fase 9 global permanece abierta.

Conservar worktrees y entornos anteriores, incluido el operativo de Fase 6. Aplicar el paquete 9.5 únicamente en una copia nueva de la base exacta, después de verificar manifiesto, inventarios y parche. El auditor debe utilizar Windows PowerShell 5.1 normal, Python 3.14.6 x64, Node 24.15.0/npm 11.12.1 y Brave instalado con perfil aislado. Las rutas con espacios se pasan como argumentos de archivo, sin código Python largo mediante `-c`. No usar otro navegador como sustituto silencioso de Brave.

Separar preparación/aplicación y pruebas frontend de los recorridos reales sintéticos y la revisión PDF/visual. Conservar JUnit, stdout/stderr, órdenes, versiones, códigos, duraciones, descargas y matrices de páginas; devolver evidencia y detenerse entre las etapas indicadas en la guía. No repetir baterías históricas completas ni lanzar la selección completa Python/Windows por este cambio de SPA. No consultar Programador, SQL, almacenes o servicios operativos. El arranque soportado de API/pasarela y la consola HTMX se conserva sin cambios.

Los resultados auditados de 9.4 que siguen son antecedentes. Sus workflows `40834824739` (Python) y `40834824733` (frontend) figuran como `failure`, pero sus cinco jobs no arrancaron: el aviso indica pagos recientes fallidos **o** necesidad de elevar el límite, sin determinar cuál aplica. No son resultados de pruebas ni CI verde. No cambiar facturación, workflows o protecciones, ni disparar o reintentar Actions.

## Entrega 9.4: validación nativa completada

**Corrección v2, F94-ROB-01:** las carteras con metadatos necesarios incompletos quedan como alteradas dentro del listado y su ficha devuelve 409, conservando las sanas. El nombre opcional ausente se publica como `null`. La sonda original, sin modificar, pasó de 1/3 (código 1) sobre v1 a 3/3 (código 0) en Linux v2; la ejecución nativa posterior confirmó 3/3. Su leyenda fija «Linux» se conserva: la atribución Windows procede de los metadatos del supervisor nativo.

La base exacta es `4f4dd639581168b08c95816660f80fc4f735b1ac` (PR #102; árbol `3aa63d583a9c4df7a139b7eafe5a161fadcbe441`, 976 archivos). La fuente v2 aprobada tiene árbol `8f5be63c3a8f5205356d40504cc426f3eacf06f5` y 1027 archivos públicos. Los cinco trabajos del PR #102 pertenecen a 9.3/base. El cierre documental se aplicó sobre v2 exacta antes de la integración en PR #104. CI de 9.4 bloqueado por facturación, con los cinco jobs sin ejecutar, sin lanzar Actions ni cambiar facturación.

**Ejecuciones nativas de Daniel, 28 de octubre de 2026, aprobadas por el auditor.** Windows 11/Python 3.14.6 x64; Node 24.15.0 y npm 11.12.1. La primera corrida `d5a768db` aprobó 173 pruebas API/pasarela y la sonda 3/3, retenidas sin repetir, y contención 2/2 (124 esperado en el ensayo de plazo). Tras la reanudación diagnóstica `f758ca05`, la continuación `1463b159` ejecutó 780 Vitest nuevos en Windows y completó tipos, TypeScript, compilación y canario, con código 0 y pip check correcto. Son tres corridas relacionadas, sin sumar baterías solapadas ni atribuir las 780 a una repetición Linux v2. [Tres ZIP, tamaños, huellas y procedencia](fase9_4_validacion_operador_2026-10-28.md).

**OpenAPI: cinco descripciones 422 aceptadas.** Los primeros dos bloqueos fueron del control del documento: `Unprocessable Entity` en el versionado y `Unprocessable Content` en el generado Windows, sólo en las cinco descripciones 422 nuevas; el resto del JSON completo coincide. El comparador externo conserva ambos documentos y sus cinco diferencias, reconoce exclusivamente esas leyendas auditadas y rechaza cambios adicionales. Informa `documentos_json_iguales=false` y `cinco_descripciones_422_auditadas_aceptadas=true`. Producto, contrato funcional, OpenAPI versionado y tipos permanecen intactos; la salvedad documental no crea una v3. La emulación Linux de la leyenda runtime que efectuó el auditor fue una reproducción aislada, sin atribuirla a Windows.

Brave instalado, motor 156.0.8078.48, Playwright 1.56.1, perfil temporal y plataforma `win32`. La etiqueta genérica Chromium se conserva; la huella del ejecutable externo acredita Brave, sin afirmar una validación de Google Chrome/Windows.

| Escenario Brave | Visitas | Comprobaciones de navegador | HTTP directo | Capturas |
|---|---:|---:|---:|---:|
| Normal, cuatro juegos | 60 | 5 | 8 | 60 |
| Vacío | 9 | 0 | 0 | 9 |
| Alterado | 12 | 6 | 0 | 12 |
| Incompatible | 6 | 3 | 0 | 6 |
| Cuota | 0 | 1 | 0 | 1 |
| **Total** | **87** | **15** | **8** | **88** |

El contador genérico de cuota declara cero visitas aunque sí hubo navegación, espera y acción manual. Se comprobó 429 con `Retry-After`, sin reintento automático y con recuperación por clic explícito. API/pasarela reales y SPA compilada, datos sintéticos, SQLite y almacenes aislados: costes fríos 3/6, ausencia de canario, huellas e índices/controles públicos conservados. Los 409 esperados de artefactos alterados no son fallos de las pruebas.

**Auditoría visual posterior:** 88 capturas aprobadas sin hallazgos bloqueantes. El campo pendiente de la salida original se conserva como histórico; el informe posterior acredita la aprobación. No es certificación general de accesibilidad. No se repitieron la selección completa Windows, suite completa, ML, PostgreSQL, mediciones ni otra observación F6. La revisión final de navegación, móvil y accesibilidad continúa planificada en 9.5.

### Protocolo conservado como referencia histórica

Los pasos siguientes conservan la preparación y las órdenes de referencia de la validación ya completada; el supervisor externo registró las etapas y resultados efectivos anteriores. No se ejecutan otra vez por este cierre ni se aplica de nuevo el parche completo. La carpeta Windows validada recibe únicamente el incremental documental sobre v2 exacta después de la revisión; se conservan worktree y entorno existentes.

1. **Revisar el paquete con el auditor.** Comprobar el SHA-256 completo del ZIP, `SHA256SUMS`, manifiesto y prueba de aplicación/reversión. Conservar las entregas y worktrees anteriores.
2. **Preparar una copia nueva**, desacoplada en esa base; por ejemplo `C:\GitHub\loteria-predictor-f94-v1`. No aplicar nada sobre el worktree operativo `C:\GitHub\loteria-predictor-fase6`, su Python `C:\GitHub\venvs\loteria-fase6\Scripts\python.exe` ni los worktrees ya validados. La tarea `LP6-01023009031fcabd`, versión 2, configuración, plan, almacenes y PostgreSQL operativo se conservan.
3. **Aplicar y comprobar**, comparando rutas y huellas con el manifiesto, sin modificar el índice real:

   ```
   git rev-parse HEAD
   git status --short
   Get-FileHash -Algorithm SHA256 <ruta>\fase9-4-completo-v2.patch
   git apply --check <ruta>\fase9-4-completo-v2.patch
   git apply <ruta>\fase9-4-completo-v2.patch
   git diff --check
   git status --short
   ```

4. **Entorno separado de pruebas.** Detectar Python/Node/npm antes de instalar. Puede reutilizarse un entorno de consulta/pruebas compatible conservando sus dependencias, nunca el de Fase 6. La entrega no cambia dependencias. Referencia nativa de Daniel: Windows 11, Python 3.14.6, Node 24.15.0, npm 11.12.1 y Brave instalado; no actualizar por rutina.
5. **Pruebas dirigidas de las consultas.** Ejecutar los módulos API pública/pasarela afectados, incluidos los nuevos de guardados y las regresiones de fiabilidad/contexto; frontend, contrato OpenAPI, tipos, TypeScript, compilación y canario. Guardar comandos, versiones, salidas, códigos y JUnit nuevos. La selección Windows ya incluye las carpetas API/pasarela; no ejecutar la suite completa, ML, demostraciones, PostgreSQL ni pruebas de Fase 6 por rutina.
6. **Recorrido sintético focal.** Usar el supervisor nuevo de 9.4 y Brave instalado con perfil temporal, con API sintética real, pasarela y SPA compilada. Revisar modelos, carteras y resultados a 360, 390 y 1280 px; ausencia, alteración, incompatibilidad, paginación/filtros en URL, enlace directo, recarga y atrás/adelante. ColorLoto debe conservar pares número-color legibles; un pendiente no puede verse como cero aciertos. Comprobar memoria vacía: catálogo + modelos/carteras = 3 fichas y catálogo + resultados = 6; detalles por acción explícita, 429/`Retry-After` sin reintentos automáticos. Conservar los controles de predicción/fiabilidad de 9.3.

   Desde `backend\`, usando el Python de pruebas y el ejecutable de Brave ya instalado (sustituir `<Brave>` por su ruta comprobada), conservar una carpeta de evidencia distinta por escenario:

   ```powershell
   python -m tests.recorrido_fase94 --escenario normal --anchos 360,390,1280 --navegador "<Brave>" --salida ..\f94-recorrido-windows\normal
   python -m tests.recorrido_fase94 --escenario vacio --anchos 360,390,1280 --navegador "<Brave>" --salida ..\f94-recorrido-windows\vacio
   python -m tests.recorrido_fase94 --escenario alterado --anchos 360,390,1280 --navegador "<Brave>" --salida ..\f94-recorrido-windows\alterado
   python -m tests.recorrido_fase94 --escenario incompatible --anchos 360,390,1280 --navegador "<Brave>" --salida ..\f94-recorrido-windows\incompatible
   python -m tests.recorrido_fase94 --escenario cuota --anchos 360,390,1280 --navegador "<Brave>" --salida ..\f94-recorrido-windows\cuota
   ```

   Cada orden crea sus propios almacenes sintéticos temporales, mantiene la clave en el proceso servidor y comprueba huellas antes/después. El supervisor inicia y termina solo sus procesos de ensayo; no consulta la base operativa ni ejecuta la tarea de Fase 6. El argumento del navegador cambia únicamente el ejecutable de este recorrido, sin cambiar la configuración del producto ni el navegador global. Un error conserva registros y devuelve una salida no cero; no continuar con otra etapa sin revisar la evidencia.
7. **Devolver evidencia y detenerse.** JUnit, logs, resultado e inventario del recorrido y capturas de Brave, más estado/índice del nuevo worktree y controles públicos de conservación. No publicar ni activar operaciones reales. La auditoría posterior aprobó la validación nativa y las 88 capturas de 9.4; los resultados de 9.3 conservan su atribución histórica. La integración posterior de 9.4 en PR #104 conserva esos antecedentes; el CI quedó bloqueado por facturación sin ejecutar pruebas.

La recuperación matinal de Fase 6 con resultados pendientes sigue sin acreditarse: el registro 09:24:45 no prueba el disparo de las 09:00. Esta validación no necesita ni autoriza otra observación operativa. Mantener `experimental_no_acreditado`, AE-39 **NO-GO** y `AUTORIZA_EVALUACION = False`.

## Entrega 9.2: validación nativa completada

La 9.1 se integró en PR #100 (merge `9966a4bbcb8d81953fb283b07544636f4c11fc95`). La entrega 9.2 contiene dos bloques: las páginas de las métricas anteriores y el horario de consulta de Fase 6. Daniel la validó en Windows 11 con Python 3.14.6 y Windows PowerShell 5.1.26100.9711, con datos sintéticos, y la auditoría independiente la aprobó ([informe de cierre](fase9_2_validacion_operador_2026-10-26.md)):

- **Etapa A sobre v2:**
  - 772 pruebas Python: 394 de Fase 6, 186 de API pública y 192 de pasarela;
  - 456 de Vitest;
  - tipos, TypeScript, compilación y canario correctos;
  - sonda de horario 3/3;
  - Brave: 507 visitas y 26 comprobaciones.
- **Ajustes v3 y v4:** v3 corrige F92-NAT-01 y v4 corrige F92-TEST-01. Se comprobaron de forma dirigida en Windows PowerShell 5.1:
  - 121 casos únicos aprobados, por consolidación de dos corridas (117 retenidos de v3 y 4 revalidados en v4);
  - cardinalidad 24/24;
  - sonda de documento 4/4;
  - lectura semántica 16/16.
- **Ensayo nativo B,** con un testigo sintético y el Programador real:
  - 14 pasos. El intento de activar una versión 1 termina con código 1, como se espera; los otros 13, con código 0;
  - 16 mutaciones, todas sobre el testigo;
  - siguiente inicio igual al plan;
  - limpieza completa.

  El único inicio del testigo fue manual: no se observó un disparo automático futuro. La tarea real no se tocó y sigue habilitada con su programación anterior.

Las baterías de la etapa A conservan su atribución a la corrida sobre v2; no se repitieron con v3 ni v4. El protocolo que se siguió se conserva como referencia y no se repite por rutina:

1. **Worktree nuevo** desacoplado en `9966a4bbcb8d81953fb283b07544636f4c11fc95`. Comprobar el SHA-256 del parche con el manifiesto y después ejecutar `git apply --check`, `git apply`, `git diff --check` y `git status --short`, contrastando con la lista del manifiesto. **No** se aplica en `C:\GitHub\loteria-predictor-fase6`: la tarea `LP6-01023009031fcabd` depende de él y el código nuevo rechaza su `ciclo` sin modo.
2. **Frontend**, desde `frontend\`, como en el paso 3 de la 9.1: `npm ci --no-audit --no-fund --ignore-scripts`, `npm run tipos:comprobar`, `npm run typecheck`, Vitest con JUnit, `npm run build` y `npm run canario`.
3. **API pública y pasarela**, desde `backend\` y con el venv existente, como en el paso 4. Incluye `tests\unit\api_publica\test_api_publica_metricas_anteriores.py`, que compara cada métrica anterior con la receta de la consola en los cuatro juegos.
4. **Recorrido** (opcional, como en el paso 5): el escenario `normal` visita todas las métricas del índice (30/30/22/36), la página 2 de la tabla paginada, el color `ROJO` y los parámetros no válidos.
5. **Brave** con perfil temporal, como en el paso 6. Revisar además:
   - en ColorLoto: colores, conteo por color con su selector y pares número-color, donde cada número debe ir con su color;
   - en Baloto: la coocurrencia de tríos, con la página 2 y los enlaces de paginación por teclado;
   - una métrica con selector de año o ventana, con atrás, adelante y recarga;
   - a 360, 390 y 1280 px.
6. **Fase 6 (horario):** pruebas dirigidas y ensayo nativo con una tarea de ensayo aislada, según la [sección 0 de la migración](fase6_migracion_lp6.md#0-antes-de-migrar-protocolo-nativo-con-una-tarea-de-ensayo-aislada). La migración real de `LP6-01023009031fcabd` es posterior a la auditoría y no forma parte de esta validación.

**v2 (auditoría v1).** La auditoría retuvo la v1 por cinco hallazgos (F92-PS-01, PS-02, HOR-01, REV-01 y EV-01) que la v2 corrige; al desbloquear la lectura del plan apareció un sexto (F92-PS-03). Las baterías de PowerShell de Fase 6 se ejecutaron primero en Linux, con PowerShell 7.6.9 y 7.4.22 portátiles y el Programador simulado. Después se ejecutaron en Windows con Windows PowerShell 5.1, junto con el ensayo nativo del paso 6. Allí aparecieron dos hallazgos:

- **F92-NAT-01:** el Programador omite `StartWhenAvailable` cuando vale su predeterminado `false`. Se corrigió en la v3.
- **F92-TEST-01:** un ayudante de prueba era incompatible con Windows PowerShell 5.1. Se corrigió en la v4.

La selección `tests\seleccion_windows.txt` incluye las pruebas nuevas de horario y `test_fase6_auditoria_v1.py`. Su ejecución completa quedaba para el CI del nuevo PR; *actualización:* el CI del PR #101 la aprobó (check «Windows - seleccion de tests/seleccion_windows.txt», ejecución `40291140855`). Las evidencias se devolvieron sin claves ni rutas privadas, y sus huellas constan en el informe de cierre.


## Entrega 9.3: protocolo dirigido

**Estado histórico v2:** validada por Daniel en Windows 11 con Brave el 27 de octubre y aprobada por el auditor; después integrada en PR #102 (`4f4dd639`) con los cinco trabajos aprobados. El protocolo y sus resultados se conservan como antecedentes de 9.3, sin atribuirlos a 9.4. El worktree `C:\GitHub\loteria-predictor-f93-v2` ya está validado. Los comandos siguientes son referencia del protocolo propuesto; la ejecución real comprendió 415 pruebas API/pasarela y 690 Vitest, sin repetir ahora esas baterías.

**Validación nativa v2 de Daniel, 27 de octubre de 2026 (11:18:23–11:29:15, America/Bogota), aprobada por el auditor.** Windows 11/Python 3.14.6: 415 pruebas API/pasarela; Node 24.15.0: 690 Vitest, sin fallos, errores u omisiones. Las 25 regresiones de contexto ya están incluidas en los 690. OpenAPI, tipos, TypeScript, compilación y canario correctos; pip check limpio y dos deprecaciones Python conocidas. Brave instalado, con perfil temporal y adaptador externo: 30 visitas y 32 comprobaciones correctas a 360, 390 y 1280 px, más seis controles HTTP; cuota: dos comprobaciones y cero visitas en el contador genérico, aunque sí hubo navegación. El auditor revisó 16 capturas sin bloqueos; el resultado original decía pendiente porque se generó antes de la auditoría y se conserva intacto. No es certificación general de accesibilidad. Fuente v2 de 975 archivos y seis controles públicos de worktrees conservados; contención 2/2 con código 124 esperado; no se ejecutó la selección completa de Windows. No hubo consultas o ciclos operativos. Son resultados nativos de Daniel, separados de Linux y de la observación real de Fase 6. [Insumos y límites](fase9_3_validacion_operador_2026-10-27.md).

**Reglas.**
- **Worktree NUEVO**, desacoplado en `ed0ee427f7a6fcd2a33cbc538435a3df2e299710` (merge del PR #101), con el parche completo de la 9.3.
- **No se tocan:** el checkout principal, los worktrees anteriores, `C:\GitHub\loteria-predictor-fase6` ni su venv `C:\GitHub\venvs\loteria-fase6`. Sostienen la tarea `LP6-01023009031fcabd` y la comprobación operativa del horario, que sigue en curso. Tampoco se tocan la tarea, su configuración ni sus horarios.
- **Datos:** solo sintéticos. Nada usa PostgreSQL, modelos ni almacenes operativos.
- **Claves:** solo de prueba, en variables de la sesión.

1. **Worktree y parche:**

   ```
   git -C <clon> worktree add --detach C:\GitHub\loteria-predictor-f93-v2 ed0ee427f7a6fcd2a33cbc538435a3df2e299710
   cd C:\GitHub\loteria-predictor-f93-v2
   Get-FileHash -Algorithm SHA256 <ruta>\fase9-3-completo-v2.patch
   git apply --check <ruta>\fase9-3-completo-v2.patch
   git apply <ruta>\fase9-3-completo-v2.patch
   git diff --check
   git status --short
   ```

   Comparar el SHA-256 y la lista de `git status` con el manifiesto de la entrega.
2. **Python:** un venv **nuevo** fuera del worktree, p. ej. `C:\GitHub\venvs\loteria-f93-v2`, con `pip install -r backend\requirements.txt`, `pip install httpx==0.28.1` y `pip check`. Si la ruta propuesta ya existe, conservarla y elegir otra nueva. No se usa el venv de Fase 6.
3. **Frontend**, desde `frontend\`, como en el paso 3 de la 9.1:
   - `npm ci --no-audit --no-fund --ignore-scripts`;
   - `npm run tipos:comprobar` y `npm run typecheck`;
   - Vitest con JUnit;
   - `npm run build` y `npm run canario`.
4. **Python dirigido**, desde `backend\`:

   ```
   python -m pytest -p no:cacheprovider -rsw tests\unit\api_publica\test_api_publica_fiabilidad.py tests\unit\api_publica\test_api_publica_preservacion.py tests\unit\pasarela\test_pasarela_contrato.py --junitxml=..\f93-dirigidas-windows.xml
   ```

   La ejecución nativa completada comprendió las carpetas API/pasarela (415 pruebas); se conserva este comando dirigido como referencia. La selección completa de Windows no se ejecutó y el CI del nuevo PR queda pendiente. No repetir baterías por el cierre documental.
5. **Recorrido**, con Brave mediante Playwright y perfil temporal, como en la validación de la 9.2. Desde `backend\`:

   ```
   python -m tests.recorrido_fase9 --escenario fiabilidad --salida ..\f93-recorrido-windows\fiabilidad
   python -m tests.recorrido_fase9 --escenario cuota_fiabilidad --anchos 1280 --salida ..\f93-recorrido-windows\cuota_fiabilidad
   ```

   `normal` es opcional: incluye `fiabilidad` y todas las métricas.
6. **Brave a mano**, con perfil temporal, como en el paso 6 de la 9.1. Revisar, a 360, 390 y 1280 px:
   - **Predicción de Baloto:** explicación, versión registrada, cortes 2192 (entrada) y 2185 (entrenamiento), importancias y superbalota aparte. Con memoria vacía, la carga inicial pide catálogo (1) y predicción (3): 4 fichas, sin fiabilidad automática. Pulsar «Consultar fiabilidad» solicita 3 fichas adicionales y muestra la evidencia solo si corresponde al contexto de la cartera; en otro caso, ausencia explícita y enlace «Fiabilidad general de la configuración actual».
   - **Cambio de cartera:** al elegir el objetivo 2191, la URL lleva `?cartera=` y conserva el corte 2190. Atrás, adelante y recarga conservan identidad/corte y dejan la fiabilidad sin consultar hasta pulsar de nuevo el botón; nunca muestran cifras de otra selección. `hasta` filtra objetivos, no la disponibilidad temporal de informes o emisiones.
   - **Baloto Revancha:** dice que no hay explicación guardada.
   - **ColorLoto:** pares número-color con su color en texto, y números y colores por separado.
   - **Pestaña «Fiabilidad»:** consulta general de la configuración actual, diferenciada de la cartera; seguimiento, retrospectiva y receta por separado; el filtro de objetivos `2190` en la URL; `?hasta=0` da 422.
   - **Lectura:** el texto sobre Δ positivo y negativo y «estimable» sin ventaja acreditada.
   - **Teclado:** «Universo completo» se abre con Enter, «Consultar fiabilidad» se activa con teclado y las tablas son enfocables.
   - **Cuota:** con seis fichas la carga inicial de predicción no recibe 429; la consulta explícita posterior puede recibirlo. No hay reintento automático; el botón de reintento respeta `Retry-After`.
   - **Comprobaciones generales:** sin desplazamiento horizontal de la página; consola sin errores; red solo a `127.0.0.1:8020`, sin `X-API-Key`; almacenamiento vacío.

**Evidencia a devolver.**
- Versiones.
- Salidas y códigos de salida de cada paso, JUnit, `recorrido.json` y `resultados.json`.
- Capturas de Brave.
- `git status --short` final del worktree nuevo, y que `C:\GitHub\loteria-predictor-fase6` no cambió.

No se incluyen claves, `.env` ni rutas privadas.


## Resultado auditado de la 9.1 (antecedente; no acredita la 9.3)

- Tipos, TypeScript, compilación y canario: correctos.
- Vitest 379, pasarela 186 y API pública 92: sin fallos, errores ni omisiones.
- Sonda original del plazo: dos 504 dentro del margen; intercambio HTTP: 14/14.
- Brave normal: 297/297 visitas, 24/24 criterios y 11 controles directos.
- Cuota, API caída, falta de clave y clave incorrecta: aprobados.
- Vite: 12/12 visitas en 360, 390 y 1280 px, StrictMode y tres controles directos.
- 41 capturas revisadas por el auditor; fuente v2 de 904 archivos e índice conservados.

El primer recorrido Vite falló en la detección del arranque: los colores ANSI
separaban el puerto de su dirección literal. El adaptador externo `color-vite-r1`
pasa `NO_COLOR=1` a los hijos del orquestador, sin cambiar código del producto
ni criterios. La reanudación solo ejecutó Vite y verificó la evidencia previa;
no reinstaló dependencias ni repitió los otros cinco escenarios. Brave se usó
mediante Playwright con un perfil temporal, sin descargar otro navegador.

## Protocolo de referencia

Los bloques siguientes describen la preparación y las alternativas de
verificación. No se deben repetir por rutina tras este cierre. La ejecución
real usó los supervisores auditados y el worktree
`C:\GitHub\loteria-predictor-f91-v2`.

## Reglas de seguridad

- **Dónde:** en un worktree NUEVO, desacoplado en `615f3832296d74a7acea44e5ecdf7dc84a11d70a`, con el parche completo de la 9.1. No se tocan `C:\GitHub\loteria-predictor-fase6` (la tarea `LP6-01023009031fcabd` depende de él), el checkout principal ni otros worktrees.
- **Operación automática:** la tarea, sus configuraciones, modelos, almacenes y el PostgreSQL operativo quedan fuera. Ninguna prueba los usa: la API del recorrido usa datos sintéticos en una carpeta temporal propia. La automatización puede seguir actualizando sus estados mientras tanto; eso no es un cambio de esta validación.
- **Python:** el venv existente (el de la validación de Fase 8). La 9.1 no añade dependencias de Python.
- **Claves:** solo de prueba, en variables de la sesión de PowerShell; nunca en archivos versionados, capturas ni chats. Cerrar la sesión las elimina. No se muestran `.env` ni `DATABASE_URL`.
- **Red:** los tres procesos escuchan solo en `127.0.0.1`. Si el cortafuegos pide permiso, se puede denegar.

## 1. Detectar Node antes de instalar nada

```
node --version
npm --version
where.exe node
```

- Si `node --version` es **22.12 o superior** (22.x o 24.x LTS), usarlo tal cual.
- Si no existe o es anterior, **detenerse y decidir** con Daniel: la recomendación es Node 24 LTS desde el instalador oficial de nodejs.org. Esta guía no instala nada por sí sola.

## 2. Worktree y parche

```
git -C C:\GitHub\loteria-predictor-fase8-v2 worktree add --detach C:\GitHub\loteria-predictor-f91-v2 615f3832296d74a7acea44e5ecdf7dc84a11d70a
cd C:\GitHub\loteria-predictor-f91-v2
Get-FileHash -Algorithm SHA256 <ruta>\fase9-1-completo-v2.patch
git apply --check <ruta>\fase9-1-completo-v2.patch
git apply <ruta>\fase9-1-completo-v2.patch
git diff --check
git status --short
```

Comparar el SHA-256 con el del manifiesto y `git status` con su lista de archivos.

## 3. Frontend: instalación reproducible, tipos, pruebas y compilación

Desde `frontend\`:

```
npm ci --no-audit --no-fund --ignore-scripts
npm run tipos:comprobar
npm run typecheck
npx vitest run --reporter=default --reporter=junit --outputFile.junit=..\f91-vitest-windows.xml
npm run build
npm run canario
```

`npm ci` crea `frontend\node_modules` dentro del worktree (no toca el entorno global). Anotar el código de salida de cada orden.

## 4. Pasarela y API pública

Con el venv activado, desde `backend\`:

```
python -m pytest -p no:cacheprovider -rsw tests\unit\pasarela --junitxml=..\f91-pasarela-windows.xml
python -m pytest -p no:cacheprovider -rsw tests\unit\api_publica --junitxml=..\f91-api-publica-windows.xml
```

- `test_pasarela_arranque.py` arranca procesos Uvicorn reales con el arranque documentado (`uvicorn app.pasarela.aplicacion:app --host 127.0.0.1 --port 8020 --no-access-log --no-proxy-headers`, cambiando solo el puerto).
- La prueba de archivos fuera de `dist\` usa un enlace simbólico de archivo si Windows lo permite; sin ese privilegio comprueba una carpeta mediante una unión (junction). La corrida auditada no tuvo omisiones de pytest.
- `tests\unit\pasarela` ya está en `tests\seleccion_windows.txt`; la selección amplia se reserva al CI del PR.

## 5. Recorrido automático (opcional, descarga Chromium)

Requiere el Chromium de Playwright (`npx playwright install chromium`, unos 150 MB en `%LOCALAPPDATA%\ms-playwright`, fuera del repositorio). **Preguntar antes de descargarlo.** Si se acepta, desde `backend\`:

```
python -m tests.recorrido_fase9 --salida ..\f91-recorrido-windows\normal
python -m tests.recorrido_fase9 --escenario cuota --salida ..\f91-recorrido-windows\cuota --anchos 1280
```

**Vite en Windows:** el orquestador actual no propaga `NO_COLOR` al proceso hijo. Su búsqueda literal puede fallar aunque Vite haya arrancado con códigos ANSI. Para reproducir el recorrido Vite se usa el supervisor externo `color-vite-r1` documentado en el cierre; establecer solo la variable en la consola no basta. La limitación está documentada y no se modificó el orquestador versionado.

Cada orden arranca la API pública real con datos sintéticos (`tests.fase9_api_sintetica:app`; no es PostgreSQL), la pasarela con una clave canario y la SPA, y termina los procesos al acabar. Devuelve 0 solo si no hay fallos ni aparece el canario.

## 6. Brave con un perfil temporal

En tres sesiones de PowerShell, desde `backend\` y con el venv activado:

1. Clave de prueba (sesión 1): `python -m scripts.api_publica_claves generar --id brave-prueba`. Copiar la entrada `brave-prueba:sha256:…` y la clave solo a las variables de las sesiones siguientes.
2. API sintética (sesión 2): `$env:F9_RAIZ = Join-Path $env:TEMP ("f91-brave-" + [guid]::NewGuid())`, `$env:API_PUBLICA_CLAVES = "<entrada>"` y `uvicorn tests.fase9_api_sintetica:app --host 127.0.0.1 --port 8010 --no-access-log --no-proxy-headers`.
3. Pasarela (sesión 3): `$env:PASARELA_CLAVE_API = "<clave>"` y `uvicorn app.pasarela.aplicacion:app --host 127.0.0.1 --port 8020 --no-access-log --no-proxy-headers`.
4. Brave con perfil temporal (comprobar antes la ruta con `Test-Path`):

```
$perfil = Join-Path $env:TEMP ("f91-brave-perfil-" + [guid]::NewGuid())
& "$env:ProgramFiles\BraveSoftware\Brave-Browser\Application\brave.exe" --user-data-dir="$perfil" --no-first-run http://127.0.0.1:8020/
```

Comprobar en los cuatro juegos (ficha, sorteos con filtros y detalle, estadísticas y varias métricas, predicción, simulaciones y la simulación alterada de ColorLoto) y en `/servicio`:
- a 360, 390 y 1280 px (herramientas de desarrollo, modo dispositivo): sin desplazamiento horizontal de la página; las tablas se desplazan dentro de su región;
- teclado: Tab muestra «Saltar al contenido» y el foco es visible;
- Consola sin errores; Red: solo `127.0.0.1:8020`, sin cabecera `X-API-Key` en las peticiones;
- Aplicación → almacenamiento local, de sesión, IndexedDB y cookies vacíos;
- atrás/adelante y recarga conservan los filtros.

Al terminar: cerrar Brave y las tres sesiones (la clave de prueba deja de existir) y borrar `$perfil` y `$env:F9_RAIZ`.

## Evidencia a devolver

Versiones (`node`, `npm`, `python`, Brave), salidas y códigos de salida de los pasos 2–6, los JUnit, los `recorrido.json` y `resultados.json` si se hizo el paso 5, capturas de Brave y `git status --short` final. No incluir claves, `.env` ni rutas privadas fuera del worktree.
