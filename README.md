# Sistema Predictivo de Loterías Colombianas

Plataforma de análisis estadístico y adquisición de datos para MiLoto, Baloto, Baloto Revancha y ColorLoto. Construida con **Clean Architecture** sobre FastAPI + PostgreSQL, con un dashboard HTML/HTMX y una API REST equivalente.

> **Aviso importante:** este sistema analiza patrones estadísticos en resultados históricos de loterías genuinamente aleatorias. No predice, no garantiza, ni puede garantizar resultados futuros. El valor del proyecto está en el rigor del análisis y la calidad de la ingeniería, no en "ganar la lotería".

---

## Estado del proyecto

Las fases 1–5, incluidas las cinco familias ML, están integradas en PR #95, base `2ac4d110b7d721e544f5588e9754230eef28184d` (árbol `37380b32906dbc0ded73112d8bbd4f1d50659993`, 691 archivos públicos). El cierre documental ML se aplicó y verificó en PowerShell 5.1, con índice conservado. Actions `39387775447` aprobó Linux completo y Windows selección para esa base. Son antecedentes de PR #95, no resultados de Fase 6.

Daniel ejecutó previamente ML v3.2 en Windows nativo: **7.015 aprobadas**, sin fallos, errores ni omisiones, recorrido real de cuatro juegos y evidencia de impresión auditada por ChatGPT. La focal anterior se solapa y no se suma. Los resultados Cloud/Linux conservan su versión y recuento propios. Detalle: [validación local ML](backend/docs/ml_cinco_familias.md#validación-local-completada-de-ml-v32).

**Fase 6 v3.4 — validación operativa del 23 de octubre de 2026:** tarea Windows y núcleo habilitados. MiLoto incorporó automáticamente el #628 y guardó la cartera/explicación para el #629; ColorLoto incorporó el #229 y guardó las del #230. Histórico canónico previo y selecciones conservados; doce copias HTML anteriores de MiLoto sí cambiaron al reconciliar. La publicación manual y Actions se completaron después en PR #96 (merge `fcadea6a08e8e6b52386a9055be16bb1873b9a29`, Actions `39939306600`); queda la revisión separada de restos históricos. [Evidencias, alcance y salvedades](backend/docs/fase6_validacion_operativa_2026-10-23.md).

**Antecedente conservado de la entrega v3.3 (estado e instrucciones anteriores a la activación real):** operación con destinos reales sin activar. Daniel completó en Windows nativo la v3.1: **7.243 aprobadas**, cero fallos, errores u omisiones; OpenSSL `exigir` 7/7, demostración sintética de cuatro juegos y `pip check` limpio. Las **47 dirigidas Linux de v3.2** conservan su evidencia propia. Son antecedentes de esas versiones, no resultados v3.3, y no se suman grupos solapados. El ensayo nativo v3.2 ya superó el error de codificación: `Instalar` registró la tarea y falló después en `Assert-TareaPropia`. La tarea `LP6-f03df678192ac201` permanece `Disabled`, con `Enabled=false`; no hubo activación ni disparo. El ZIP del ensayo conserva planes; el segundo ZIP aporta el XML realmente exportado y CIM. De los 14 campos comparados, coinciden 11: Windows omite `RunLevel` y `WakeToRun` y expresa el usuario del desencadenador de sesión como cuenta local, mientras el plan usa SID. CIM informa `Limited` (0) y `WakeToRun=false`. La v3.3 compara la semántica de la exportación: admite solo valores predeterminados documentados expresamente y resuelve las identidades mediante mecanismos nativos para comparar el SID esperado. Una omisión no autorizada, privilegio elevado, valor explícito incompatible o usuario distinto/no resoluble se rechaza. No usa nombre corto, sufijos ni excepciones por usuario. Revisa también vinculación, campos críticos, acciones y desencadenadores para conservar el rechazo de tareas ajenas o alteradas. El XML exportado se archiva antes de validarlo, incluso cuando falla la comprobación posterior al registro, y se distingue del plan y del diagnóstico. Se conservan el contrato UTF-16LE con BOM, la captura binaria con decodificación estricta y las garantías de limpieza v3.2. La nueva evidencia Linux usa PowerShell real y simulaciones explícitas del Programador y la resolución nativa; no acredita Windows PowerShell 5.1, COM/MSXML, permisos o NTFS nativos. El protocolo de esta entrega termina en aplicar v3.3 sobre v3.2 exacta → pruebas dirigidas en PowerShell 5.1 → devolver evidencia y detenerse. Conservar el worktree y el Python existentes. El nuevo ensayo real del Programador será posterior a la revisión; esta guía no lo inicia ni incluye una orden para ejecutarlo ahora. No se repiten completa, ML, demostración o presentación/PDF por rutina. Operación con destinos reales, PostgreSQL, activación/novedad observada, publicación manual, Actions y acreditación prospectiva mantienen pendientes separados. Se mantienen `experimental_no_acreditado`, AE-39 **NO-GO** y `AUTORIZA_EVALUACION = False`. [Operación Fase 6](backend/docs/fase6_windows.md).

| Fase | Implementación | Validación y pendiente |
|---|---|---|
| 1. Dominio + MVP HTML/HTMX | Completa | Antecedentes Windows y GitHub Actions conservados |
| 2. Adquisición automática de datos | Completa; invocación e integración Fase 6 | Antecedentes conservados; validación nativa de la nueva operación separada |
| 3. Machine Learning | Cinco familias añadidas: XGBoost, LightGBM, red neuronal, Bayes jerárquico y Markov; conserva seis candidatos anteriores por juego | Registro/recarga de 20 modelos nuevos, recorrido e impresión nativa validados; cierre documental aplicado y PR #95 con Actions aprobados |
| 4. Predicciones | Centro de cuatro juegos, explicación y fiabilidad observada; integrado con las familias nuevas | Flujo de las cinco familias y persistencia validados en Windows; PR #95 con Actions aprobados, separado del antecedente PR #94 |
| 5. Estadísticas descriptivas | Completa | Antecedentes Windows con histórico real y Actions conservados |
| 6. Actualización y operación automática | Implementada y activada en Windows, v3.4. Horario de consulta por juego (entrega 9.2) integrado en PR #101 y aplicado por Daniel a la tarea real | Novedades automáticas de MiLoto y ColorLoto verificadas; integrada en PR #96 (Actions `39939306600`); limpieza histórica separada. [Detalle](backend/docs/fase6_validacion_operativa_2026-10-23.md). Horario: validado en Windows nativo y aprobado por la auditoría (pruebas dirigidas con Windows PowerShell 5.1 y ensayo nativo B con el Programador real y un testigo sintético; [validación](backend/docs/fase9_2_validacion_operador_2026-10-26.md)). Integrado en PR #101 (`ed0ee427`, cinco checks aprobados). Daniel migró y activó en Windows `LP6-01023009031fcabd` con el horario por juego. Según la confirmación del auditor (no son pruebas de esta entrega), en la captura del 27 de octubre de 2026 a las 00:11, hora de Colombia, quedaron verificadas nueve ejecuciones programadas y quince consultas en sus franjas: siete de MiLoto, tres de Baloto, tres de Revancha y dos de ColorLoto, sin consultas duplicadas ni fallos de sincronización reportados. Aquella captura no tenía resultados nuevos. La observación posterior del 27 de octubre a las 10:21, auditada sobre la captura de Daniel, acredita una novedad incorporada automáticamente y su siguiente predicción con explicación guardada en cada juego: 20 ciclos conservados, 33 consultas (8 de MiLoto, 9 de Baloto, 9 de Revancha y 7 de ColorLoto), sin parejas juego/oportunidad repetidas ni fallos de sincronización reportados; los 29 intentos sin novedad no emitieron otra predicción. Configuración, selecciones de modelos, tarea versión 2 y plan conservados. El último inicio informado es 09:24:45: no acredita disparo exacto a las 09:00 ni recuperación matinal con resultados pendientes, pues los cuatro juegos terminaron de madrugada. Esa recuperación y la limpieza histórica siguen pendientes. Es operación real observada, separada de las pruebas sintéticas 9.3; Codex no ejecutó ciclos ni SQL operativo. [Actualización real de Fase 6](backend/docs/fase9_3_validacion_operador_2026-10-27.md#actualizacion-real-de-fase-6-del-27-de-octubre). ([horario](backend/docs/fase6_horario.md), [migración](backend/docs/fase6_migracion_lp6.md)) |
| 7. Simulaciones | Implementada sobre `605afe8`: cuatro juegos, 100 a 1.000.000 de iteraciones, estadísticas fijadas de Fase 5, tabla `simulaciones` y web/API interna/comando; v2 más F7-VIS-01 | Validación local Linux y Windows, PostgreSQL aislado y Brave completados; integrada en PR #98 (merge `f15f513`) con checks de Linux y Windows aprobados. [Cierre local](backend/docs/fase7_validacion_operador_2026-10-24.md) |
| 8. API pública | v2: entrada separada `/api/v1` de solo lectura (juegos, sorteos, estadísticas, predicciones y simulaciones guardadas), claves de API por huella, límite por proceso con 429 y `Retry-After`, OpenAPI y monitoreo | Validada en Linux, Windows y PostgreSQL aislado; integrada en PR #99 (merge `615f383`) con CI `40133227968` aprobado en Linux y Windows; despliegue en Fase 10. [Detalle](backend/docs/fase8_api_publica.md) |
| 9. Frontend React | 9.1 integrada en PR #100 (`9966a4b`): SPA React/TypeScript/Vite de consulta de `/api/v1` a través de una pasarela local que guarda la clave en el servidor. Entrega 9.2 sobre ese merge, integrada en PR #101 (`ed0ee42`): páginas de las métricas anteriores en el mismo índice y la misma ruta de métrica. 9.3 integrada en PR #102 (`4f4dd639`): explicación, clasificación de candidatos y fiabilidad observada. 9.4 integrada en PR #104: consultas de modelos registrados, carteras y resultados guardados. 9.5 integrada en PR #105 (`bad7c8d5`): exportación local e impresión de la consulta cargada | 9.1 v2 validada en Linux y Windows nativo con Brave ([validación del operador](backend/docs/fase9_validacion_operador_2026-10-25.md)). 9.2 validada en Linux y en Windows nativo con Brave y aprobada por la auditoría, por la cadena v2 → ajuste nativo v3 → ajuste de pruebas v4 ([validación del operador](backend/docs/fase9_2_validacion_operador_2026-10-26.md)). La 9.2 se integró en PR #101 con sus cinco checks aprobados. La 9.3 v2 está validada en Linux y Windows nativo con Brave y aprobada por la auditoría; integrada en PR #102 (merge `4f4dd639581168b08c95816660f80fc4f735b1ac`), con los cinco trabajos aprobados: Node 22, Node 24, Chromium/Linux, Python/Linux y Python/Windows (workflows `40589232731` y `40589232763`). Son antecedentes de la 9.3, no resultados de la 9.4 ([cierre del operador](backend/docs/fase9_3_validacion_operador_2026-10-27.md)) ([detalle](backend/docs/fase9_frontend.md#entrega-93-explicación-clasificación-de-candidatos-y-fiabilidad)). La entrega 9.4 v2 está validada en Linux y Windows nativo con Brave y aprobada por auditoría; integrada en PR #104 (merge `9fde216c5667bd7a1ddb8553a73857f5cfb07e61`); CI bloqueado por facturación, con sus cinco jobs sin ejecutar. 9.5: validación nativa en Windows con Brave y auditoría completadas, con los hallazgos F95-NAT-01 y F95-PDF-01 cerrados ([validación del operador](backend/docs/fase9_5_validacion_operador_2026-11-01.md)); integrada en PR #105 (merge `bad7c8d5bb913d3d780dd4dfa3b6cdcd9f2dad3e`) con los cinco trabajos aprobados (workflows `41327381044` y `41327381002`). **Fase 9 cerrada** el 1 de noviembre de 2026 en su alcance de consulta ([cierre global](backend/docs/fase9_cierre_global_2026-11-01.md)) |
| 10. Despliegue | Planificada | Seguridad, operación y disponibilidad pendientes |
| 11. Aplicación personal | Planificada | Depende de Fase 6 y capacidades pertinentes de fases 8–10 |

**Orden: 6 Actualización y operación automática → 7 Simulaciones → 8 API pública → 9 React → 10 Despliegue → 11 Aplicación personal.** Fase 6 quedó integrada en PR #96 y el arreglo del issue #93 en PR #97 (`605afe8c2bb3b38d0fa3abdb6a5d14ba2002b5a6`). Fase 7 quedó integrada en PR #98 (`f15f513b431dd9a5dc3a2fb148a63a82a11405b5`) y Fase 8 en PR #99 (`615f3832296d74a7acea44e5ecdf7dc84a11d70a`; CI `40133227968`). La 9.1 quedó integrada en PR #100 (`9966a4bbcb8d81953fb283b07544636f4c11fc95`). La entrega 9.2 se implementó sobre ese merge, junto con el horario de consulta de Fase 6; validada y auditada, quedó integrada en PR #101 (`ed0ee427f7a6fcd2a33cbc538435a3df2e299710`). La entrega 9.3 quedó integrada en PR #102 (`4f4dd639`), con sus cinco comprobaciones aprobadas. La entrega 9.4 v2, sobre ese merge exacto, está validada en Linux y Windows nativo con Brave y aprobada por auditoría; integrada en PR #104 (merge `9fde216c5667bd7a1ddb8553a73857f5cfb07e61`); CI bloqueado por facturación, con sus cinco jobs sin ejecutar. La 9.5 quedó integrada en PR #105 (`bad7c8d5bb913d3d780dd4dfa3b6cdcd9f2dad3e`), con sus cinco trabajos aprobados, y la Fase 9 quedó cerrada el 1 de noviembre de 2026 en su alcance de consulta ([cierre global](backend/docs/fase9_cierre_global_2026-11-01.md)); las fases 10–11 conservan su planificación. Las fases 1–5 mantienen su número. En antecedentes, «Fase 6 — Simulaciones» usa la numeración original; hoy corresponde a Fase 7. Los Productos 1–6 y sus archivos, rutas, pruebas y artefactos históricos no se renombran.

**Cadena de base conservada:** PR #94 y sus checks `38982578601` son antecedentes de Fase 4. PR #95 incorpora la ampliación ML y el cierre documental ya verificado; su merge `2ac4d110b7d721e544f5588e9754230eef28184d` es la base exacta de Fase 6. No se atribuye a sus checks la nueva operación automática. PR #96 (`fcadea6a08e8e6b52386a9055be16bb1873b9a29`, Actions `39939306600`) integró Fase 6 y PR #97 (`605afe8c2bb3b38d0fa3abdb6a5d14ba2002b5a6`; Actions `40020240159` del PR y `40023629982` del merge) cerró el issue #93; ese merge fue la base exacta de Fase 7. PR #98 (`f15f513b431dd9a5dc3a2fb148a63a82a11405b5`) integró Fase 7 y fue la base exacta de Fase 8. PR #99 (merge `615f3832296d74a7acea44e5ecdf7dc84a11d70a`, implementación `b7ccd623006100e50bc307e020f525f570beb728`, CI `40133227968` aprobado en Linux y Windows) integró Fase 8 y es la base exacta de la 9.1. Daniel conserva la revisión y publicación manual de esta entrega.

**Historial de productos**, vinculados a sus fases (detalle al final de este documento y en el ROADMAP):

| Producto | Descripción | Fases | Estado |
|---|---|---|---|
| Producto 1 | Estadísticas por juego (`/estadisticas`) y pronóstico experimental de Baloto y Revancha (`/pronosticos`) | 5 y 4 | 🧪 Experimental, no acreditado; GitHub Actions en verde — ver `backend/docs/producto1_windows.md` |
| Producto 2 | Pronóstico experimental de MiLoto y ColorLoto y comparación con resultados observados de los cuatro juegos (`/pronosticos`) | 4 | 🧪 Experimental, no acreditado; validado en Windows; GitHub Actions en verde — ver `backend/docs/producto2_windows.md` |
| Producto 3 | Panel diario (`/operacion`), actualización y generación por juego, y seguimiento del rendimiento (`/rendimiento`) | 2 y 4 | 🧪 Experimental, no acreditado; validado en Windows con histórico real; GitHub Actions en verde — ver `backend/docs/producto3_windows.md` |
| Producto 4 | Laboratorio de modelos (`/laboratorio`): entrenar y comparar modelos nuevos por juego y generar con el elegido | 3 (y 4) | 🧪 Experimental, no acreditado; validado en Windows con histórico real e impresión en Carta vertical; GitHub Actions en verde — ver `backend/docs/producto4_windows.md` |
| Producto 5 | Modelo combinado con pesos aprendidos del pasado, carteras de combinaciones por modelo y simulación Monte Carlo frente a la uniforme (`/carteras`) | 3, 4 y 7 (antes 6) | 🧪 Experimental, no acreditado; validado en Windows con histórico real; GitHub Actions en verde — ver `backend/docs/producto5_windows.md` |
| Producto 6 | Centro de resultados y evaluación continua de modelos (`/resultados`): pronósticos ya emitidos de las tres procedencias frente a los sorteos reales, comparación sobre la muestra común, calibración e informes verificables | 4 (y 3) | 🧪 Experimental, no acreditado; validado en Windows con histórico real; GitHub Actions en verde — ver `backend/docs/producto6_windows.md` |

Para el diseño técnico completo (capas, diagramas de flujo, decisiones de arquitectura, motor estadístico) ver [ARCHITECTURE.md](./ARCHITECTURE.md).

---

## Estadísticas

Visualizaciones anteriores a la Fase 5: doce para **Baloto** y **Baloto Revancha**, once para **MiLoto** (sin superbalota) y treinta y una para **ColorLoto** (`/estadisticas/colorloto/...`, Etapas AE-1 a AE-31). Las de los juegos numéricos:

- Frecuencia de números principales.
- Frecuencia de superbalota (Baloto y Baloto Revancha — MiLoto no tiene superbalota, esa página lo indica explícitamente en vez de fallar).
- Frecuencia observada vs. esperada (comparación contra la probabilidad teórica uniforme).
- Distancia desde la última aparición (números principales, en numeración de sorteos, respecto del último sorteo real dentro del corte seleccionado — nunca respecto de un número de sorteo hipotético que no exista en el histórico. Es descriptiva, no predictiva: incluye un aviso explícito de que el tiempo transcurrido no cambia la probabilidad futura de un número).
- Distribución de números pares e impares (cuántos de los K números principales de cada sorteo son pares, tabulado sobre 0..K sorteos históricos — no es frecuencia individual de números ni coocurrencia de pares).
- Distribución inferior/superior (cuántos de los K números principales caen en la mitad inferior del rango del juego — 1–21/22–43 en Baloto y Revancha, 1–19/20–39 en MiLoto. Los dos grupos **no** tienen exactamente el mismo tamaño; la página lo explica junto a la definición de los grupos, nunca los presenta como mitades iguales).
- Distribución de pares consecutivos (cuántos pares de números adyacentes, con diferencia exactamente 1, aparecen en cada sorteo, tabulado 0..K-1. Los pares pueden solaparse: 1,2,3 contiene dos pares consecutivos. Descriptiva, no predictiva: no sugiere que los consecutivos sean menos probables o "menos aleatorios").
- Racha máxima de números consecutivos (la longitud del bloque más largo de números consecutivos dentro de cada sorteo, tabulado 1..K — nunca incluye la categoría 0, ya que todo sorteo válido tiene al menos una racha de longitud 1. **Distinta de "pares consecutivos"**: 1,2,3 tiene 2 pares consecutivos, pero su racha máxima es 3. Descriptiva, no predictiva: una racha larga o corta no hace que un sorteo sea anómalo ni permite predecir resultados futuros).
- Repeticiones entre sorteos consecutivos (cuántos números principales coinciden entre un sorteo y el número de sorteo inmediatamente siguiente — una "transición" solo es válida cuando `numero_sorteo_actual == numero_sorteo_anterior + 1`; un hueco en la numeración no genera ninguna transición, nunca se fabrica una comparación entre sorteos que no son consecutivos reales. El denominador de esta métrica **no** es la cantidad de sorteos, sino la cantidad de transiciones válidas — la página lo presenta explícitamente como "Transiciones analizadas", nunca "Sorteos analizados". Descriptiva, no predictiva: una repetición pasada no aumenta ni reduce la probabilidad de repetición futura).
- Coocurrencia de pares y de tríos de números (Etapas AE-32 y AE-33: sorteos en que aparecen juntos, solo lo observado; los tríos, paginados).
- Distribución de tríos consecutivos (Etapa AE-34).

```
/estadisticas/{juego_slug}/frecuencia-numeros
/estadisticas/{juego_slug}/frecuencia-superbalota
/estadisticas/{juego_slug}/frecuencia-observada-esperada
/estadisticas/{juego_slug}/atrasos-numeros
/estadisticas/{juego_slug}/distribucion-pares-impares
/estadisticas/{juego_slug}/distribucion-altos-bajos
/estadisticas/{juego_slug}/distribucion-pares-consecutivos
/estadisticas/{juego_slug}/distribucion-racha-maxima
/estadisticas/{juego_slug}/repeticiones-entre-sorteos
/estadisticas/{juego_slug}/coocurrencia-pares
/estadisticas/{juego_slug}/coocurrencia-trios
/estadisticas/{juego_slug}/distribucion-trios-consecutivos
```
donde `{juego_slug}` es `baloto`, `baloto-revancha` o `miloto`.

**ColorLoto** tiene sus propias treinta y una visualizaciones (números, colores y pares número-color, con multiplicidades) en `/estadisticas/colorloto/...`, y la Fase 5 completa el resto (ver abajo). El caché de resultados se invalida automáticamente al registrar, editar o eliminar un sorteo del juego correspondiente, sin afectar a los demás juegos. Antes de calcular una distribución que depende de la cantidad exacta de números por sorteo (pares/impares, inferior/superior), el sistema valida que el histórico persistido sea consistente (cantidad correcta, sin duplicados, dentro de rango) — si encuentra una inconsistencia, responde con un error controlado (500, sin exponer detalles internos) en vez de calcular sobre datos corruptos. Detalle técnico completo (motor, caché persistido, invalidación, upsert, validación de integridad) en [ARCHITECTURE.md](./ARCHITECTURE.md#motor-estadístico-y-caché-persistido).

Chart.js se sirve localmente (`app/static/vendor/chartjs/chart.umd.min.js`, versión 4.4.4, licencia MIT), no desde un CDN externo.

**Corte por número de sorteo (Etapa X):** las 4 visualizaciones incluyen un control `GET` (`?hasta_numero_sorteo=N`) para acotar el análisis hasta un sorteo específico. **El corte es específico del juego actual**: cambiar de métrica dentro del mismo juego lo conserva; cambiar de juego siempre vuelve al histórico completo, porque la numeración de sorteos de Baloto/Baloto Revancha no es comparable con la de MiLoto (series independientes, con rangos de numeración completamente distintos) — no es una limitación accidental, es la semántica correcta. `0` y valores negativos devuelven `422` (JSON, mecanismo de validación nativo de FastAPI); ningún valor inválido llega a calcularse ni a persistirse en caché.


### Fase 5 — estadísticas descriptivas completas

**Estado: completa; validada localmente en Windows con histórico real** (entrega v2; evidencia de cada entorno en «Validación», abajo, y en `backend/docs/fase5_windows.md`). GitHub Actions la ejecutó después en verde (ejecución 42 sobre `24c9861`, merge del PR #90, y de nuevo la 45 sobre `c7644c4`). Completar la fase descriptiva no cambia `experimental_no_acreditado`, el NO-GO ni `AUTORIZA_EVALUACION = False`, y no implica que las fases de ML, predicción o evaluación estén completas: frecuencias, atrasos, intervalos y pruebas describen sorteos ya ocurridos, no la probabilidad del próximo.

La auditoría sobre `9fab331` encontró terminadas las 43 visualizaciones anteriores (con esta sección del README atrasada) y, como huecos reales, las 17 funciones del motor sin conectar (7 familias: distribuciones adicionales, atrasos e intervalos, repetición de la superbalota, frecuencia temporal de números y de superbalota, comparación por ventana, e independencia y bondad de ajuste), el panel unificado y las correlaciones de Pearson y Spearman, que no existían. Todo queda conectado:

- **Panel unificado** `/estadisticas/{juego}/panel` (`baloto`, `baloto-revancha`, `miloto`, `colorloto`): todas las estadísticas del juego en una sola vista, sobre la misma muestra (corte opcional), con su cifra clave, la marca «Fase 5» en las páginas nuevas y el motivo de lo que no aplica. JSON: `/api/estadisticas/{codigo}/panel`.
- **Páginas nuevas** `/estadisticas/{juego}/{metrica}`: 18 en Baloto y Revancha, 11 en MiLoto y 5 en ColorLoto, con gráfica SVG y una tabla con los mismos valores (la gráfica se dibuja desde una columna de la tabla). JSON: `/api/estadisticas/{codigo}/descriptivas/{metrica}`.
- **Navegación:** fila «Más estadísticas» en las 43 páginas anteriores (sus pestañas no cambian), botón «Panel completo» en `/estadisticas`, enlace en el resumen de cada juego y en el menú lateral.

| Requisito (ROADMAP) | Juegos | Implementación | Acceso | Evidencia (Linux) |
|---|---|---|---|---|
| Frecuencias de números, superbalota, colores y pares; observada frente a esperada | 4 (superbalota: Baloto y Revancha; colores y pares: ColorLoto) | recetas anteriores | páginas anteriores y panel | pruebas anteriores; validación Windows de cada etapa AE |
| Patrones temporales: números por año, mes y día de la semana | 4 | `frecuencia_temporal` (con 3 funciones nuevas para los números de ColorLoto) | `frecuencia-numeros-por-anio`, `-por-mes`, `-por-dia-semana` | `test_fase5_motor`, `test_fase5_descriptivas`, `test_fase5_web` |
| Patrones temporales de la superbalota | Baloto, Revancha | `frecuencia_temporal` | `frecuencia-superbalota-por-anio`, `-por-mes`, `-por-dia-semana` | ídem |
| Atraso de la superbalota | Baloto, Revancha | `calcular_atrasos_superbalota` | `atrasos-superbalota` | ídem |
| Intervalos entre apariciones (números y superbalota) | Baloto, Revancha, MiLoto (ColorLoto: página anterior) | `calcular_intervalos_historicos_numeros` / `_superbalota` | `intervalos-historicos-numeros`, `intervalos-historicos-superbalota` | ídem |
| Repetición de la superbalota entre sorteos consecutivos | Baloto, Revancha | `calcular_repeticion_superbalota_entre_sorteos` | `repeticion-superbalota` | ídem |
| Suma total | Baloto, Revancha, MiLoto (ColorLoto: página anterior) | `calcular_distribucion_sumas` y `calcular_histograma_sumas` (nueva) | `distribucion-sumas` | ídem |
| Decenas | Baloto, Revancha, MiLoto; en ColorLoto (1 a 7) no aplica | `calcular_distribucion_decenas` | `distribucion-decenas` | ídem |
| Comparación con una ventana reciente (5, 10, 20 o 50 sorteos) | 4 (ColorLoto: páginas anteriores; superbalota: Baloto y Revancha) | `comparar_frecuencia_numeros_por_ventana` / `_superbalota_` | `comparacion-frecuencia-numeros-por-ventana`, `comparacion-frecuencia-superbalota-por-ventana` | ídem |
| Chi cuadrado de uniformidad | 4 | `chi_cuadrado_uniformidad` (nueva; corrección (N−1)/(N−K) sin reemplazo; p-value asintótico) | `pruebas-uniformidad` | ídem, con verificación Monte Carlo de la corrección y `test_fase5_pvalores` |
| Independencia de pares y tríos | Baloto, Revancha, MiLoto; en ColorLoto no aplica (motivo en `motor/independencia.py`) | `calcular_independencia_pares` / `_trios` y Benjamini-Hochberg | `independencia-pares`, `independencia-trios` | ídem |
| Correlaciones de Pearson y Spearman; chi cuadrado número × color | 4 (número × color: ColorLoto) | `motor/correlaciones.py` (nuevo; coeficientes descriptivos, p-value por permutación entre mitades, sin p-value en la serie de sumas; número × color asintótico) | `correlaciones` | ídem y `test_fase5_pvalores` |
| Consecutivos, coocurrencia, repeticiones, pares/impares, bajos/altos, máximo color, conteo por color | 4 | recetas anteriores | páginas anteriores y panel | pruebas anteriores |
| Panel unificado (todas las métricas en una sola vista) | 4 | `descriptivas.construir_panel` | `panel` | ídem y demostración `python -m tests.demostracion_fase5` |

- **Unidades:** «% de sorteos» (sorteos que contienen el valor / sorteos), «% de números extraídos» (apariciones / (sorteos × números por sorteo)), «balotas por sorteo» (ColorLoto, con repetición), «sorteos de distancia» (numeración) y «puntos porcentuales» (diferencia de porcentajes); nunca se intercambian.
- **Corte y filtros:** el corte se aplica antes de calcular; la cabecera de cada página (sorteos, período, frescura, huecos) describe exactamente la muestra de las cifras, tablas y gráficas. El año, mes o día elegido se aplica después del corte.
- **Estados:** sin base de datos la página lo dice (la API responde 503); sin sorteos o sin sorteos en el período elegido, se dice así, sin ceros inventados; con datos insuficientes (intervalos, correlaciones), «insuficiente»; un histórico inconsistente rechaza el cálculo completo, con los validadores de las recetas.
- **Solo lectura:** las estadísticas nuevas se calculan en memoria con el motor existente; no escriben la caché `estadisticas` ni nada en la base. Lo que no aplica a un juego responde 404 con su motivo.
- **Contrato que cambia a propósito:** `/estadisticas/{baloto|baloto-revancha|miloto}/comparacion-frecuencia-numeros-por-ventana` respondía 404 (la página era solo de ColorLoto) y ahora sirve la comparación de la Fase 5; la ruta de ColorLoto no cambia.
- **Reutilización:** ver ARCHITECTURE, «Fase 5». Las pruebas y correlaciones son descriptivas; un p-value bajo no indica qué saldrá.
- **p-values (cada página y cada fila de la API dicen cómo se obtienen):**
  - **Correlaciones:** los coeficientes de Pearson y Spearman (SciPy) son descriptivos y se publican siempre que se puedan calcular; un coeficiente que no se puede calcular no marca la página entera como insuficiente. El p-value no es el de SciPy (en `spearmanr` es una aproximación para muestras grandes y en `pearsonr` supone pares independientes y normales).
  - **Entre mitades:** contraste de permutación bilateral sobre los números (7, 39 o 43 categorías, no los sorteos). Con hasta 8 categorías se enumeran todas las ordenaciones (ColorLoto: 5040, permutación exacta); con más, Monte Carlo con 9999 ordenaciones y semilla fija 5, p = (1 + k)/(1 + B), reproducible en cualquier versión de Python. Se apoya en que, bajo H0 (sorteos independientes y simétricos respecto de los números), las apariciones de la segunda mitad son independientes de la primera e intercambiables.
  - **Suma frente al sorteo anterior:** sin p-value. Las transiciones comparten sorteos y los pares no son independientes; ni el p-value de SciPy ni una permutación de pares están justificados.
  - **Chi-cuadrado** (uniformidad y número × color): p-value asintótico. El factor (N−1)/(N−K) sin reemplazo corrige la escala, pero no convierte el contraste en una prueba exacta para muestras finitas; con frecuencias esperadas menores que 5 la página avisa.
  - **API:** cada fila de correlación lleva `contraste` (`permutacion_exacta`, `permutacion_monte_carlo` o `null`), `permutaciones`, `como_p_value`, `motivo` (sin coeficiente) y `motivo_p_value` (límites o motivo); cada fila de uniformidad, `tipo_p_value: "asintotico"`.
- **Validación** (cada entorno por separado; validar el funcionamiento no acredita ventaja predictiva, y un p-value alto no demuestra que el sorteo sea aleatorio):
  - **Windows** (operador, sobre la v2, Python 3.14.6): Fase 5 `94 passed`; Producto 6 `73 passed`, Producto 5 `96 passed`, Producto 4 `94 passed`, Productos 1 a 3 `225 passed`; selección filtrada `2130 passed`; demostraciones con datos sintéticos 8/8 (Fase 5) y 9/9 (Producto 6), que no son evidencia del histórico real; OpenSSL `SUPERADOS 7/7` en modo `exigir`; `pip check` y comprobación de espacios limpios. Aparece el aviso conocido `StarletteDeprecationWarning` (`httpx` en `TestClient`): es un aviso, no un fallo. La suite completa NO se ejecutó en Windows: los `6375 passed` son de Linux.
  - **Histórico real** (operador, en Windows; solo lectura): la comprobación de `backend/docs/fase5_windows.md` terminó correctamente sobre estas muestras, sin huecos de numeración dentro de ellas:

    | Juego | Sorteos | Numeración | Fechas |
    |---|---:|---|---|
    | Baloto y Baloto Revancha | 639 | 2081–2719 | 2021-05-01 a 2026-10-07 |
    | MiLoto | 89 | 532–620 | 2026-05-07 a 2026-10-08 |
    | ColorLoto | 225 | 1–225 | 2024-08-15 a 2026-10-08 |

    Se comprobaron los cortes reales, que los histogramas de sumas suman la muestra cortada, los denominadores de las decenas, los esperados de uniformidad (con la superbalota aparte), las transiciones y que las frecuencias coinciden con las del resumen de Producto 1. Interpretación: el chi-cuadrado da un p-value asintótico; la correlación de la suma con la del sorteo anterior es descriptiva y no tiene p-value; la comparación entre mitades usa permutación exacta en ColorLoto y Monte Carlo reproducible en los demás juegos. Ninguna de estas cifras es una probabilidad del próximo sorteo ni una ventaja predictiva.
  - **Impresión** (PDF generados por el operador en Windows, en A4 y Legal; ninguno en Carta): 14 PDF, cuyas 51 páginas se renderizaron y revisaron con ChatGPT sin encontrar recortes, filas ausentes ni solapamientos visibles.

    | Página | Formatos (páginas) |
    |---|---|
    | Panel de Baloto | A4 vertical (4), A4 horizontal (5), Legal vertical (3) |
    | Panel de ColorLoto | A4 vertical (4), Legal vertical (4), Legal horizontal (5) |
    | Uniformidad de Baloto | A4 vertical (4), A4 horizontal (6), Legal vertical (4) |
    | Decenas de Baloto | A4 vertical (2), A4 horizontal (3), Legal vertical (2) |
    | Correlaciones de ColorLoto | A4 horizontal (3) |
    | Correlaciones de MiLoto | A4 horizontal (2) |

    Las tablas de uniformidad conservan las 43 filas de números y las 16 de superbalota en los tres formatos, y las cinco franjas de decenas tienen valores idénticos en los tres y suman 3195 apariciones y 100 %. Cinco de esos PDF (las tres decenas y las dos correlaciones, 12 páginas) se cotejaron además con Claude: mismos formatos y páginas, las cifras de decenas (la tabla en Legal se parte con la cabecera repetida) y las columnas de la v2 («Cómo se obtiene el p-value»: permutación exacta en ColorLoto, Monte Carlo en MiLoto, «No se calcula» en la suma). La revisión se limita a esas páginas y formatos: no cubre Carta ni el resto de páginas de la aplicación.
  - **Linux** (Cloud, Python 3.11.15, NumPy 2.4.6 y SciPy 1.17.1, solo fixtures sintéticas; no es Windows ni el histórico real): pruebas de la Fase 5 `94 passed` (16 del motor, 27 del catálogo y el caso de uso, 30 de web y API y 21 de p-values); Producto 6 `73 passed`, Producto 5 `96 passed`, Producto 4 `94 passed`, Productos 1 a 3 `225 passed`; estadísticas anteriores (generalización, corte, recetas, visualizaciones) `3200 passed`; selección de Windows (85 entradas) `2130 passed`, sin omisiones; suite completa una vez sobre el código final `6375 passed`, sin fallos ni omisiones; OpenSSL `SUPERADOS 7/7` (`exigir`) en la selección y en la suite; demostraciones `tests.demostracion_fase5` 8/8 y `tests.demostracion_producto6` 9/9; `pip check` y espacios limpios. Antes de corregir los p-values, `test_fase5_pvalores.py` se ejecutó sobre la entrega anterior: 14 de 15 fallaron (9 reproducen el defecto, como Spearman p = 0 con 3 pares ordenados frente a 1/3 exacto o la suma con p-value, y 5 por la API nueva) y 1 guarda ya pasaba. Una simulación bajo H0 (2000 historias de 40 sorteos de Baloto) dio, con Monte Carlo, tasas de rechazo de 0,092 (Pearson) y 0,090 (Spearman) para α = 0,10 y de 0,047 y 0,046 para α = 0,05. En la entrega anterior, sobre la base, las tres primeras pruebas de la Fase 5 fallaban solo al importar los módulos que faltaban y la prueba de aislamiento de la ventana, con 404. Revisión visual en Chromium 141 con Bootstrap 5.3.3 local: 21 páginas a 1366 y 390 px y PDF en Carta vertical, Carta horizontal y A4 vertical; en esta revisión, además, las 7 páginas afectadas por los p-values, sin desbordes a 390 px. Las páginas estadísticas anteriores ya desbordaban a 390 px, sin relación con esta entrega.
  - **GitHub Actions:** ejecución 42 sobre `24c9861` (merge del PR #90): Linux, suite completa con 6375 superadas; Windows, selección con 2130 superadas; OpenSSL 7/7 en ambos. La 45 sobre `c7644c4` repitió en verde (6379 y 2134).


## Machine Learning: modelos entrenados y versionados (Fase 3)

**Antecedente histórico: ingeniería original cerrada con el PR #92 (base `8a53108`).** La v2 está validada por el operador en Windows nativo (Python 3.14.6) y recorrida con el histórico real de los cuatro juegos, y los ajustes de cierre se validaron después en Windows (ver «Cierre», abajo). GitHub Actions la ejecutó en verde (ejecuciones 47, 48 y 49). Guía: `backend/docs/fase3_windows.md`. *Estado anterior, al entregar los ajustes de cierre: «implementada; v2 validada en Windows; ajustes de cierre pendientes de validar en Windows; GitHub Actions todavía no ha ejecutado la Fase 3».* Es finalización técnica, no evidencia predictiva: siguen el NO-GO de AE-39, `experimental_no_acreditado` y `AUTORIZA_EVALUACION = False`.

**Informe frente a modelo registrado.**
- Un informe del laboratorio (Producto 4) guarda la receta, el histórico y las métricas de una comparación. Se reproduce reentrenando.
- Un modelo registrado guarda además el **estimador ya ajustado**, con su preparación de variables y, en los clasificadores, su calibración, y se **recarga para pronosticar sin volver a entrenar**.
- Cada versión procede de un informe: su corte explícito, su histórico y la evaluación de esa receta frente a la uniforme.

**Flujo en la web** (`/laboratorio`):
1. Comparar los candidatos de un juego (once por juego; seis históricos más las cinco familias de esta ampliación).
2. En el informe, «Entrenar y guardar versión»; la página de progreso muestra las fases: leyendo el informe, entrenando y publicando.
3. Abrir la ficha (`/laboratorio/modelo/<clave>`). Muestra el entrenamiento, las variables, los componentes, los parámetros elegidos, la evaluación de **esta receta** frente a la uniforme, el pronóstico de control y la procedencia. Aparte, con su nombre, muestra la lectura general del informe de procedencia: su clasificación guardada, con esta receta marcada, y quién tuvo la menor pérdida (otro modelo, la uniforme o un empate), sin recalcular ni reordenar.
4. «Verificar»: integridad, compatibilidad, carga restringida y pronóstico de control.
5. «Generar con el modelo cargado»: el sorteo siguiente al último cargado o a un corte de entrada; nunca anterior al de entrenamiento.
6. «Resultados observados» de su línea propia (`<modelo>-v<receta>-reg<n>`), separada de las líneas que reentrenan.

`/laboratorio/modelos` lista las versiones de cada juego con su compatibilidad. También informa de las versiones alteradas y de los números reservados sin publicar (interrupciones).

**Elegir una versión para la operación diaria** es una decisión explícita y única:
- En `/carteras/<juego>`, se guarda una versión nueva de la configuración con «Versión registrada». También se puede hacer desde «usar esta configuración» de `/resultados`.
- Las carteras configuradas recargan esa versión sin reentrenarla.
- Comparar o entrenar nunca cambia la configuración vigente.

**Comando** (mismos casos de uso; desde `backend`):

```powershell
# Acciones manuales: comparar/entrenar/generar/configurar escriben artefactos.
$corte = Read-Host 'Corte cargado de BALOTO'
python -m scripts.laboratorio_modelos comparar --juego BALOTO --corte $corte
$informe = Read-Host 'Clave del informe que acabas de comprobar'
python -m scripts.laboratorio_modelos entrenar --experimento $informe --modelo xgboost_binario
$modelo = Read-Host 'Clave de la version registrada'
python -m scripts.laboratorio_modelos modelos --juego BALOTO
python -m scripts.laboratorio_modelos modelo --clave $modelo
python -m scripts.laboratorio_modelos verificar --modelo $modelo
# Solo si decides emitir un pronostico y elegir esta version:
python -m scripts.laboratorio_modelos generar-con-modelo --clave $modelo
python -m scripts.carteras_modelos configurar --juego BALOTO --modelo xgboost_binario --registrado $modelo
```

API de solo lectura: `GET /api/laboratorio/modelos[?juego=]` y `GET /api/laboratorio/modelos/{clave}`. Ningún GET carga un estimador ni escribe.

**Garantías:**
- Cada versión son tres archivos en `storage/laboratorio/modelos/<JUEGO>/`: el estimador, con su SHA-256 como nombre; la reserva exclusiva de su número de versión, y el manifiesto sellado.
- El manifiesto se publica en último lugar, con el mismo mecanismo atómico de #83, así que un lector nunca ve una versión incompleta. Cada publicación usa un temporal de nombre corto (`.publicacion.<16 hex>.tmp`) en la misma carpeta que su destino.
- Una entrada idéntica reutiliza su versión, y un cambio de receta, datos, entrenamiento o entorno crea otra. Nada se sobrescribe ni se borra solo.
- Antes de cargar se comprueban la ruta, el sello, el entorno (misma scikit-learn; mismas versiones menores de Python, NumPy y SciPy), el SHA-256 y una lista cerrada de clases admitidas. Solo se cargan modelos producidos por la aplicación.

**Límites:**
- Las tablas `modelos` y `metricas_modelo` de la Fase 1 no se escriben. El registro inmutable de archivos es la persistencia usada y el manifiesto es la única fuente de cada versión. La ficha muestra su proyección a esas columnas, lo que no significa que las tablas SQL se hayan poblado.
- La evaluación asociada mide la receta con reajustes por bloque antes del corte. El estimador guardado se ajusta después con todo el histórico hasta el corte, y su rendimiento propio se observa en el seguimiento de sus pronósticos.
- Un modelo solo se carga con la misma scikit-learn y las mismas versiones menores de Python, NumPy y SciPy; si no, se entrena otra versión. El sistema operativo registrado es informativo: no bloquea la carga. Como forma parte del entorno y de la identidad, entrenar en otro sistema produce otra versión.
- En Windows sin rutas largas (límite de 259 caracteres), la ruta final más larga del laboratorio es la de un pronóstico de una versión registrada: la carpeta del laboratorio más unos 147 caracteres. Esa carpeta no debe medir más de 111 (la del worktree, `C:\GitHub\loteria-predictor-fase3\backend\storage\laboratorio`, mide 61).
- Que el registro funcione y respete la disciplina temporal no demuestra ausencia de sobreajuste ni ventaja futura.

**Verificación en Linux de la entrega original (v1)** (Cloud, Python 3.11.15, scikit-learn 1.9.1, fixtures sintéticas): Fase 3 `60 passed` (registro 33, bosques 13, integración 14); regresiones de Productos 1 a 6 (`85`, `39`, `66` con la cobertura de #83, `94`, `96` y `73 passed`) y de la Fase 5 (`94 passed`); selección de Windows ejecutada en Linux (88 entradas) `2194 passed`; una suite completa `6439 passed`; OpenSSL `SUPERADOS 7/7` en modo `exigir`; demostración sintética 7/7; `pip check` y espacios limpios. Revisión visual con Bootstrap real a 1366 y 390 px de ancho y PDF en Carta vertical y horizontal. Son cifras de Linux: no acreditan Windows ni el histórico real.

**Primera ejecución en Windows (v1) y corrección de rutas (v2).** El parche original se aplicó y sus 51 archivos coincidieron con el manifiesto, pero las pruebas focales dieron `6 failed, 54 passed` y el script se detuvo antes de las regresiones, la demostración y la selección. El publicador del laboratorio formaba el temporal con el nombre final entero (`.<nombre final>.<16 hex>.tmp`, 22 caracteres más): cuatro trazas mostraban destinos de 240 o 242 caracteres, que cabían, con temporales de 262 o 264, por encima del límite de Windows sin rutas largas (259). El HTTP 500 y el código 3 de la línea de comandos eran el mismo fallo al publicar el pronóstico de una versión registrada, la ruta más larga del almacén. La v2 publica con el temporal corto de Producto 5 (`.publicacion.<16 hex>.tmp`, en la misma carpeta; un solo publicador para Productos 4 a 6), reconoce los temporales con el nombre anterior y el nuevo, y añade regresiones que simulan el límite. No cambia modelos, fórmulas, contratos de inferencia, nombres finales ni el estado experimental. La simulación no es una ejecución en Windows: la validación de la v2 en Windows sigue pendiente. *Actualización (cierre): el operador la validó después en Windows nativo; ver abajo.*

**Verificación en Linux de la v2** (mismo entorno; no acredita Windows): Fase 3 `69 passed` (registro 33, bosques 13, integración 14 y rutas 9); Productos 1 a 6 (`85`, `39`, `66` con la cobertura de #83, `94`, `96` y `73 passed`) y Fase 5 (`94 passed`); selección de Windows ejecutada en Linux (89 entradas) `2203 passed`; una suite completa `6448 passed`; OpenSSL `SUPERADOS 7/7` en modo `exigir`; demostración sintética 7/7; `pip check` limpio; espacios limpios y cadena base → entrega original → incremental comprobada en una extracción limpia.

**Validación nativa de la v2 en Windows** (operador, Python 3.14.6; evidencia en `%TEMP%\f3c-evidencia-20261011-002007-202b4aad`):
- Los 53 archivos coincidieron con el manifiesto v2 (CRLF/LF normalizado) y el índice real quedó vacío.
- Fase 3: la primera pasada dio `1 failed, 68 passed`. `test_temporales_anteriores_y_nuevos_se_reconocen_y_se_conservan` creaba un temporal con el nombre anterior bajo la carpeta temporal larga de pytest y superaba el límite. Con la raíz corta de pytest `C:\GitHub\f3t-29c2818301a4` pasaron las 69. Los ajustes de cierre hacen que la prueba no dependa de esa raíz (abajo).
- Productos 6, 5 y 4: `73`, `96` y `94 passed`. Productos 1 a 3: `229 passed`.
- Selección de Windows (89 entradas): `2203 passed`.
- Demostración sintética 7/7; OpenSSL `SUPERADOS 7/7` en modo `exigir`; `pip check` y espacios limpios; el aviso conocido de Starlette/httpx.
- La suite completa no se ejecutó en Windows.

**Recorrido con el histórico real en Windows** (operador; evidencia en `%TEMP%\f3-real-20261011-010241-7a44f090`):

| Juego | Sorteos | Último cargado | Corte | Modelo registrado | Versión | Siguiente objetivo |
|---|---:|---:|---:|---|---:|---:|
| Baloto | 639 | 2719 | 2714 | `random_forest_clasificador` | 1 | 2720 |
| Baloto Revancha | 639 | 2719 | 2714 | `extra_trees_clasificador` | 1 | 2720 |
| MiLoto | 89 | 620 | 615 | `random_forest_clasificador` | 1 | 621 |
| ColorLoto | 225 | 225 | 220 | `random_forest_poisson` | 1 | 226 |

- Los seis candidatos de cada juego terminaron.
- Las cuatro versiones se guardaron, se cargaron en otro proceso y reprodujeron exactamente su pronóstico de control. Repetir las mismas entradas reutilizó los artefactos.
- Los 136 artefactos previos se conservaron, comprobados por SHA-256.
- No hubo importación ni cambio de configuración de modelos.

Pronósticos retrospectivos con esas versiones (el resultado ya existía al generarlos):

| Juego | Objetivo | Aciertos | Log Loss | Uniforme |
|---|---:|---|---:|---:|
| Baloto | 2715 | 1 de 5 números | 0.35358 | 0.35945 |
| Baloto Revancha | 2715 | 0 de 5 | 0.36386 | 0.35945 |
| MiLoto | 616 | 1 de 5 | 0.37827 | 0.38296 |
| ColorLoto | 221 | 1 de 6 pares número-color (5 de 6 números, aparte) | 3.71437 | 3.73767 |

Es una sola observación retrospectiva por juego: no acredita anterioridad prospectiva ni capacidad predictiva.

**Revisión de la interfaz en Windows** (operador, con ayuda de ChatGPT):
- Se revisaron la lista de versiones, las fichas y las verificaciones de los cuatro juegos, y los pronósticos de Baloto 2715 y 2720 y de ColorLoto 221 y 226.
- Tras un reinicio real de Uvicorn:
  - la verificación de MiLoto mantuvo la versión, la clave, el SHA-256 del estimador y el control exacto;
  - generar de nuevo Baloto 2720 reutilizó el mismo pronóstico, con su fecha original, su clave y su contenido.
- Resultados integró las líneas registradas de Baloto y ColorLoto mediante filtros explícitos. «Sin muestra común» con una sola línea es un estado correcto.
- El informe de Baloto del corte 2714 (16 páginas) mostró los seis candidatos y 60 objetivos comunes.
- PDF en **Legal vertical (612×1008 puntos, Chrome 155)**, sin solapamientos. Carta, A4 y horizontal no se validaron en Windows.

**Ajustes de cierre (este incremental; pendientes de validar en Windows).** Corrigen tres ambigüedades de presentación que encontró la revisión y la prueba de temporales. No cambian modelos, estimadores, parámetros, probabilidades, la API ni los artefactos (huellas, versiones, fechas y contenido).
- **Ficha: receta frente a informe.** En el caso real de Baloto (corte 2714), Logística AE-36 fue primera (0.35942), la uniforme segunda (0.35945) y Random Forest tercero (0.35947). La ficha del Random Forest mostraba la lectura general del informe sin nombrar a quién se refería. Ahora separa «Esta receta, Random Forest…» de «Informe de procedencia, lectura general», que nombra al de menor pérdida («no esta receta»), la victoria de la uniforme, el empate o la comparación incompleta. También lista la clasificación guardada con esta receta marcada, tal como está en el informe, sin recalcular ni reordenar.
- **Ficha Poisson de ColorLoto.** Ya no dice «siempre antes de la calibración»: describe la selección temporal y la transformación de intensidades en probabilidades. Los clasificadores calibrados conservan la explicación de sus etapas. El texto común del contrato sigue igual en los manifiestos.
- **`/resultados/colorloto`.** «Aciertos medios (pares número-color)» y «Aciertos (pares número-color)», con «N de 6 pares» y una nota. En el objetivo 221, la sugerencia (3 blanco, 4 rojo, 5 negro, 6 rojo, 7 amarillo, 7 rojo) y el resultado (2 amarillo, 3 azul, 4 azul, 7 rojo, 5 blanco, 6 blanco) comparten 1 de 6 pares. Las coincidencias de 5 de 6 números y 3 de 6 colores son otras intersecciones y no se muestran ahí. Los demás juegos conservan sus etiquetas, y la superbalota sigue aparte.
- **Prueba de temporales anteriores y nuevos.** Usa su propia carpeta temporal de raíz corta (la carpeta temporal del sistema con el prefijo `f3t`). No depende de `--basetemp` ni de `PYTEST_ADDOPTS` y borra solo lo que crea. Conserva los nombres representativos, las carpetas y todas sus comprobaciones.

**Verificación en Linux de los ajustes de cierre** (Cloud, Python 3.11.15; no acredita Windows): Fase 3 `81 passed` (registro 33, bosques 13, integración 14, rutas 9 y presentación 12) con invocación normal, sin `--basetemp` ni `PYTEST_ADDOPTS`; con el límite de 259 caracteres simulado (carpeta de pytest de 61 y `%TEMP%` de 34), `81 passed` y 0 rutas rechazadas; Productos 1 a 6 (`85`, `39`, `66`, `94`, `96` y `73 passed`), lista de Productos 1 a 3 del script `229 passed` y Fase 5 `94 passed`; selección de Windows ejecutada en Linux (90 entradas, sin comentarios ni líneas en blanco) `2215 passed`; una suite completa `6460 passed` (1200 s); OpenSSL `SUPERADOS 7/7` en modo `exigir` sobre la selección y sobre la suite; demostración sintética 7/7; `pip check` limpio; espacios limpios, incluidos los archivos nuevos; revisión visual con Bootstrap real (Chromium de Playwright, 1366 y 390 px; PDF en Carta vertical y horizontal, A4 y Legal vertical) sin solapamientos ni desbordamiento horizontal; cadena base → entrega original → rutas → cierre comprobada en una extracción limpia (árbol final idéntico, reversión exacta a la v2). Python 3.11.15, scikit-learn 1.9.1, NumPy 2.4.6, SciPy 1.17.1. Sobre la v2 exacta, las 12 pruebas de presentación dan `9 failed, 3 passed`: fallan por sus comprobaciones nuevas, y pasan las 3 que protegen lo que no debe cambiar (el cálculo del caso 221, la ficha del clasificador calibrado y las etiquetas de MiLoto). La prueba de temporales final pasa con el código de publicación de la v2, también con el límite simulado; la prueba anterior, con ese mismo límite, reproduce el fallo de Windows (`1 failed`).

**Cierre (PR #92 fusionado; nueva base `8a53108`):**
- **Windows (operador, Python 3.14.6):** Fase 3 `81 passed` con invocación normal, sin `--basetemp`; selección de Windows `2215 passed`; OpenSSL `SUPERADOS 7/7`. Las tres aclaraciones de presentación se revisaron en PDF **Legal vertical**.
- **GitHub Actions:** ejecución 47 (PR #92) en verde, con la suite completa en Linux y la selección en Windows; 48 (`main`) y 49 (`develop`) sobre `8a53108`, también en verde.
- **No ejecutado en Windows:** la suite completa. El PDF en Carta, A4 y horizontal solo se revisó en Linux.

**Pendientes de aquel cierre histórico:** la suite completa Windows y la impresión en Carta/A4/horizontal no se habían ejecutado entonces. Quedaron resueltos en la ampliación ML v3.2 descrita a continuación; las cifras y formatos anteriores conservan su alcance original.

### Ampliación ML de cinco familias y consolidación de fases 1–5

La entrega v2 corrige la comprobación del estado interno frente a su receta y acorta las carpetas propias de validación para el presupuesto Win32. Las regresiones usan la entrada pública de carga y huellas recalculadas; las comprobaciones portables de rutas no equivalen a ejecutar Windows. Sus resultados nuevos y JUnit se entregan separados de la v1, sin repetir la revisión visual o PDF.

Se incorporan XGBoost y LightGBM reales en CPU, una MLP regularizada, un modelo bayesiano jerárquico y una cadena de Markov explícita. Cada uno tiene una representación binaria para Baloto, Revancha y MiLoto, y una de conteos de pares número-color para ColorLoto. El catálogo conserva los seis candidatos históricos y añade cinco por juego: once por juego, 44 entradas juego-candidato. Las recetas e identidades anteriores se conservan; `FAMILIAS_FUTURAS` ya no enumera estas familias. La comprobación del catálogo y los entrenamientos reales se acreditan con la evidencia de la entrega, no con el número escrito en esta página.

El flujo común es comparar → entrenar/registrar → recargar en proceso nuevo sin `fit` → elegir explícitamente en Carteras → emitir Predicciones explicadas → consultar Resultados y Fiabilidad. No se elige ganador ni se cambia configuración por comparar. Las versiones nuevas guardan preparación, parámetros, calibración cuando aplica, posterior o transiciones y entorno en un envoltorio JSON versionado: XGBoost en JSON nativo, LightGBM en texto nativo y MLP en matrices JSON. La compatibilidad y procedencia se verifican antes de abrir un motor nativo. Los `.pkl` históricos mantienen su lector restringido y su contrato de compatibilidad.

El Bayes numérico integra una posterior jerárquica con cuadratura y diagnóstico; ColorLoto usa una jerarquía conjugada color → número con predictiva integrada. La transformación común de cardinalidad o normalización se distingue de esa predictiva. Markov estima transiciones por candidato de orden uno con suavizado Dirichlet: cambia el estado conocido de entrada, permanecen congeladas las transiciones. Una nueva observación no actualiza en secreto un modelo registrado. Los detalles, límites y fuentes primarias están en [la documentación de métodos](backend/docs/ml_cinco_familias.md).

XGBoost/LightGBM publican ganancia total de particiones, sin convertirla en coeficientes ni causalidad. La red y los modelos sin una importancia global comparable muestran el motivo. Reproducir una explicación guardada comprueba el vector fuente y recalcula rankings y variables; un GET no vuelve a inferir ni recalcula importancias.

**Validación local ML v3.2 completada.** Daniel utilizó `C:\GitHub\loteria-predictor-ml-cierre` y el entorno independiente `C:\GitHub\venvs\loteria-ml-cierre\Scripts\python.exe` (Windows 11 AMD64, PowerShell 5.1, Python 3.14.6). La suite completa de `backend/tests`, sin `seleccion_windows.txt`, terminó con **7.015 aprobadas y cero fallos, errores u omisiones**, con seis avisos de deprecación registrados; diagnóstico numérico correcto, OpenSSL `exigir` **7/7**, demostración sintética **20/20**, `pip check` correcto y 29 mediciones conservadas. La focal nativa previa dio **109 aprobadas**; se solapa y no se suma. Estas cifras son Windows, no una nueva ejecución Linux.

El recorrido real verificó once candidatos por juego, **20 versiones nuevas** recargadas en proceso nuevo y **40 pronósticos de estimadores congelados** (dos cortes por modelo, no sorteos independientes), más cinco carteras y explicaciones que persistieron tras reiniciar. Daniel eligió explícitamente la configuración; comparar no la cambia. ChatGPT auditó los registros y la impresión: **36 PDF, 600 páginas**, de doce páginas web en Carta vertical, Carta horizontal y A4 vertical. La revisión visual fue representativa y se apoyó en controles de contenido sobre todos los PDF; no se afirma lectura manual ampliada individual de las 600 páginas. Detalles, cortes y fuentes: [validación local ML v3.2](backend/docs/ml_cinco_familias.md#validación-local-completada-de-ml-v32).

El cierre ML fue exclusivamente documental y se aplicó/verificó en PowerShell 5.1; quedó integrado en PR #95 con sus Actions aprobados. No se repitieron pruebas de producto para ese cierre. Fase 6 se implementa ahora sobre ese merge, con validación y activación propias; la acreditación prospectiva sigue separada.



*Lista anterior, al entregar los ajustes de cierre: la validación en Windows de esos ajustes y GitHub Actions (ambas cumplidas con el cierre), la suite completa en Windows y la impresión en Carta, A4 y horizontal en Windows.*

---

## Predicciones explicables y fiabilidad observada (Fase 4)

**Estado: Fase 4 implementada y validada localmente, también con las cinco familias ML v3.2.** Su cierre anterior se fusionó mediante PR #94; la evidencia Fase 4 v3.4 siguiente es histórica y no acredita por sí sola las nuevas familias. El flujo real, la persistencia y la impresión ML tienen su [validación propia](backend/docs/ml_cinco_familias.md#validación-local-completada-de-ml-v32). Cierre ML aplicado y PR #95 con Actions aprobados; acreditación prospectiva separada. Guía histórica: `backend/docs/fase4_windows.md`.

**Cierre local v3.4 (16 de octubre de 2026, Colombia).** La implementación y la validación local están completadas con los alcances del resumen consolidado aportado. Daniel ejecutó Windows nativo; Codex Cloud ejecutó Linux con datos sintéticos; ChatGPT auditó los archivos y la evidencia entregada y registró su revisión previa de PDF y capturas, que no están incluidos en los ZIP de este cierre. Este cierre documental no vuelve a ejecutar esas verificaciones ni convierte una auditoría en pruebas nuevas.

**Windows nativo v3.4, ejecutado por Daniel:** Windows 11 AMD64, Windows PowerShell 5.1, Python 3.14.6 y pytest 9.1.1. Focal **198 aprobadas**; regresiones: Fase 3 **81**, Producto 6 **73**, Producto 5 **96**, Producto 4 **94**, Fase 5 **94** y Productos 1–3 **229**. Demostración con datos sintéticos **8/8** y `pip check` correcto. ConEnlaces terminó con **217 aprobadas** en `fase4_sin_publicacion` y **2432** en `seleccion_windows_sin_publicacion` (100 entradas), sin fallos, errores ni omisiones; OpenSSL `exigir` **7/7** en el JUnit de esa selección. Consta el aviso conocido Starlette/httpx. Estas dos baterías son **reducidas**: excluyen las tres familias de publicación v3.3 y no equivalen a nuevas ejecuciones de toda Fase 4, de la selección completa ni de la suite completa Windows. Los grupos se solapan y no se suman. La bandera `validacion_completa: true` de `ConEnlaces/resumen.json` indica progreso del script; no acredita una ejecución completa nativa.

**Publicación nativa conservada de v3.3:** Daniel validó **82 aprobadas** en NTFS con `SetFileInformationByHandle(FileRenameInfoEx)`, clase **22**, flags **3**. La prueba real completó **120 publicaciones** con lectores en hilos y otro proceso, sin lecturas parciales, y verificó el destino retenido por otro proceso. Los cinco archivos de ese mecanismo permanecen byte-idénticos en v3.4; es evidencia nativa de **v3.3**, no una ejecución nueva de v3.4.

**Recorrido real y reproducción.** Daniel recuperó Baloto reutilizando la cartera publicada y completando su explicación en una ejecución nueva; conservó los registros fallidos y el temporal original, sin promocionarlos ni reescribirlos. Las cuatro emisiones de tres combinaciones y Baloto de cinco persistieron tras el reinicio, con integridad, reproducción exacta e importancias disponibles y páginas terminadas sin sondeo. Pedir cinco conservó en tres la configuración vigente; repetir Baloto de tres reutilizó cartera y explicación y añadió únicamente los dos registros de ejecución. La reproducción comprueba la huella del **vector fuente**, recalcula **rankings y variables** y los compara con la explicación guardada. La integridad de esta explicación cubre las importancias guardadas y la referencia SHA-256 del estimador. El cotejo directo del archivo del estimador se hace al emitir la explicación; la reproducción de una consulta GET **no lo abre ni lo carga, no ejecuta una nueva inferencia ni recalcula las importancias**.

**Instantáneas distintas, consultas de solo lectura.** Los PDF y las primeras **seis consultas de API** corresponden a la base anterior: **219 archivos** intactos antes/después; ChatGPT contrastó además 68 medias y límites con los PDF. Antes del último bloque se añadieron **12 archivos**, conservando los 219 originales: nueve HTML, un registro de operación y dos archivos de un pronóstico de ColorLoto. El primer intento del ayudante de parámetros se detuvo por su guarda, con cero consultas y 231 archivos intactos; se corrigió solo el ayudante. Las últimas **60 consultas**, sobre la base actualizada, dieron **28 HTTP 200 y 32 HTTP 422 esperados** en API y web: parámetros vacíos equivalentes a ausentes, GET repetidos idénticos, corte y selección conservados y rechazos de valores inválidos. Sus tres inventarios de **231 archivos** coinciden, sin alterados, ausentes ni nuevos; se verificó la cadena **219 → 231 → 231** y la conservación de los tres archivos del fallo original. No se exige igualdad de cifras o pendientes entre fechas. ChatGPT auditó JSON, huellas, formularios extraídos e inventarios; el último ZIP no incluye cada cuerpo HTML completo.

**Pantalla e impresión nativas revisadas.** Daniel produjo los PDF con Chrome 155/Windows y ChatGPT inspeccionó **27 PDF principales, 203 páginas**, en Carta vertical, Carta horizontal y A4 vertical: 15 predicciones (139 páginas) y 12 Fiabilidad (64). Las cinco predicciones conservan todas sus combinaciones en la primera página; se revisaron tablas, cabeceras, gráficas, avisos y trazas sin pérdidas ni solapamientos detectados. Un PDF de Fiabilidad Baloto uniforme, Carta vertical de **ocho páginas**, se revisó aparte y no se suma a los 27/203. Los multiconjuntos de cifras coinciden entre formatos como contraste auxiliar, sin validar el vector completo de API; las dimensiones del PDF no prueban la escala del diálogo. También se revisaron el formulario con corte 2719/línea uniforme y ColorLoto `pares`. La muestra estrecha Baloto de cinco, **390 × 648 píxeles CSS**, fue legible en los elementos inspeccionados, con desplazamiento horizontal de la tabla; es representativa, no exhaustiva de los cuatro juegos. Este cierre usa esa auditoría aportada y no vuelve a inspeccionar PDF ni capturas.

**Linux sintético, ejecutado por Codex Cloud:** suite completa **6759 aprobadas**, selección filtrada **2514**, sin fallos, errores ni omisiones; OpenSSL `exigir` **7/7 en ambos JUnit**, demostración **8/8** y `pip check` correcto. Se registraron seis avisos en la suite y uno en la selección. La comparación sintética propia de **54 PDF**, 473 filas y 207 grupos pertenece a Cloud/Linux; no se atribuye a Daniel, a Windows real ni a pruebas ejecutadas por ChatGPT. La auditoría separada de ChatGPT comprobó paquete/manifiestos, aplicación y reversión, contenido/espacios del incremental, sintaxis y controles estadísticos directos sin repetir la suite completa.

**v3.4** corrige el corte vacío y la selección persistente de Fiabilidad, el componente real de ColorLoto, la lectura numérica cerca de cero, el texto de MiLoto y el singular/plural, y la disposición de pantalla e impresión. Mantiene las probabilidades congeladas, las unidades por balota, las multiplicidades y las consultas de solo lectura. Añadir una línea sigue siendo aditivo y no modifica la configuración. La superbalota de `carteras:uniforme-v1` conserva su estrategia de frecuencia con suavizado de Laplace; el nombre de la línea no implica deltas nulos en todos sus componentes.

**Cierre documental anterior completado (PR #94).** Daniel informa que el cierre se aplicó y verificó con PowerShell 5.1, sin reescribir el aplicador, conservando el índice y limpiando sus temporales; después se fusionó PR #94. La base vigente es `90e6ab06b2a188fde9416fb0aac9e7366b7b04a6`, árbol `e4aaa33ecdef1eea1b7162dcba3c0349ef7d6cd0`. Sus checks Actions `38982578601` fueron Linux suite completa (`117246604306`) y Windows selección (`117246604151`), ambos en verde según lo aportado por Daniel. No se inventan recuentos ni se acredita suite completa Windows. La ampliación ML v3.2 tiene su propia validación local completada: suite completa nativa Windows y recorrido real, auditados por ChatGPT; véase la sección vigente de cinco familias. El nuevo cierre documental ML se aplicó/verificó en PowerShell 5.1 y se integró en PR #95, con sus Actions aprobados; la acreditación prospectiva permanece separada. Se conservan `experimental_no_acreditado`, AE-39 **NO-GO** y `AUTORIZA_EVALUACION = False`.

**Un solo flujo para los cuatro juegos** (`/predicciones`, en la navegación como «Centro de predicciones»):
1. **Elegir** el modelo en `/carteras/<juego>`: receta o versión registrada, cantidad, diversidad y semilla. Es la configuración de Producto 5, la única elección del operador, y el centro nunca la cambia ni elige otro modelo por su cuenta.
2. **Generar** («Generar con la configuración» o el comando). Usa el mismo caso de uso de Producto 5: mismo cerrojo, misma identidad y misma reutilización. Una versión registrada se recarga con las comprobaciones de la Fase 3, sin reentrenar. Después se guarda la explicación. «Generar cinco combinaciones» es una petición aparte que no cambia la cantidad configurada.
3. **Consultar** `/predicciones/<juego>`. La página muestra:
   - la configuración, la versión registrada y su compatibilidad;
   - los cortes de entrenamiento y de entrada, el objetivo, la generación, la integridad y la frescura frente a la base;
   - las combinaciones, cada una con su papel: la «sugerencia del modelo», con la probabilidad de cada elemento, o la «línea muestreada», sin marginales;
   - los fuertes y débiles, la explicación, la fiabilidad disponible en el corte, la proyección a la tabla `predicciones` y los enlaces a la cartera original, la ficha de la versión y los resultados observados.
4. **Fiabilidad** en `/predicciones/<juego>/fiabilidad`: el rendimiento observado y su incertidumbre por línea y tipo de evaluación, más la evaluación de la receta en su informe del laboratorio. `?hasta=<sorteo>` filtra los objetivos hasta ese número; no acredita que un informe o una emisión existiera al generar una cartera.

**Fuertes y débiles** (la clasificación del modelo para ese objetivo; no son garantías ni causas):
- **Números:** 10 en cada extremo, con la probabilidad emitida, la uniforme, la diferencia y la razón. En Baloto y Revancha las marginales suman 5 y la uniforme es 5/43.
- **Superbalota:** en su propia sección (16 clases que suman 1).
- **ColorLoto:**
  - pares número-color, con la probabilidad por balota (suma 1) y la multiplicidad esperada en 6 balotas (6 × p);
  - aparte, los 7 números y los colores de la paleta, cada uno con su denominador. Nunca se listan 10 números en un universo de 7.
- **Empates:** si cortan un extremo, se dice.

**Explicación** (versionada e inmutable):
- el método: familia, versión de la receta, variables, periodo y corte de entrenamiento y transformación de salida;
- los valores de las variables de cada candidato, calculados con las funciones causales del motor y solo con los sorteos hasta el corte;
- las importancias o coeficientes **globales** del estimador persistido de una versión registrada, leídos en el proceso trabajador con la carga restringida, sin reajustar nada.

Lo que no hay se dice expresamente: HistGradientBoosting no expone importancias; XGBoost y LightGBM ofrecen ganancia total de particiones, con su unidad y alcance propios. La MLP no ofrece una importancia global comparable; Bayes y Markov describen sus parámetros, sin inventar importancias. Las recetas que se reajustan al generar no conservan su estimador; uniforme y frecuencias no tienen estimador. No se inventan contribuciones por candidato.

**Fiabilidad observada** (contrato `fase4-fiabilidad-1`). Tres cantidades separadas:
1. la probabilidad emitida;
2. el rendimiento observado: Δ Log Loss y Δ Brier frente a la uniforme del mismo artefacto y objetivo, y aciertos observados menos esperados en los extremos;
3. la incertidumbre: intervalo del 95 % por **bootstrap de bloques móviles** sobre la serie de sorteos, con bloque ceil(n^(1/3)) y 2000 remuestras.

Reglas del contrato:
- la unidad es el sorteo, y juegos, líneas, tipos y componentes van por separado;
- en ColorLoto se usa la multiplicidad sobre 6 balotas;
- cada estado se declara con su motivo: `estimable` (desde 30 sorteos), `muestra_insuficiente`, `sin_resultados`, `sin_base`, `excluidas`, `sin_datos`, `no_disponible` y `fallo_de_calculo`;
- el umbral de 30 solo decide si se calcula el intervalo: no es una validación;
- el diagnóstico de calibración de Producto 6 sigue siendo descriptivo.

Fuentes: Künsch (1989), Hall, Horowitz y Jing (1995), Diebold y Mariano (1995) y Gneiting y Raftery (2007), con sus DOI en la página.

**Comando** (mismo caso de uso; desde `backend`):

```powershell
python -m scripts.predicciones indice
python -m scripts.predicciones consultar --juego BALOTO
python -m scripts.predicciones fiabilidad --juego BALOTO
python -m scripts.predicciones rutas
# Acciones manuales que escriben cartera/explicacion:
python -m scripts.predicciones generar --juego BALOTO
$cartera = Read-Host 'Clave de la cartera publicada'
python -m scripts.predicciones explicar --cartera $cartera
$ejecucion = Read-Host 'Identificador de la ejecucion'
python -m scripts.predicciones ejecucion --id $ejecucion
python -m scripts.predicciones rutas
```

Códigos de salida:
- 0: éxito;
- 2: uso o identificador no válidos;
- 3: base o almacén no disponibles;
- 4: sin configuración;
- 5: resultado parcial;
- 6: otra ejecución en curso;
- 7: versión incompatible, sin sorteos o fallo del trabajador;
- 8: artefacto alterado.

API de solo lectura: `GET /api/predicciones`, `GET /api/predicciones/{codigo}[?cartera=]` y `GET /api/predicciones/{codigo}/fiabilidad[?linea=&hasta=]`.

**Tabla `predicciones`: decisión formal.** Queda reservada y no se escribe. La fuente canónica es el almacén inmutable: la cartera de Producto 5 y su explicación. Escribir también en PostgreSQL crearía un segundo registro sin una transacción común. La página, la API y el comando muestran la proyección a sus columnas, con `nivel_confianza` vacío a propósito.

**Garantías y límites:**
- Las explicaciones se guardan en `DIRECTORIO_PREDICCIONES_MODELOS` (por defecto `storage/predicciones`, ignorado por Git):
  - ruta `explicaciones/<JUEGO>/<16 hex de la cartera>-<clave>.json`, en JSON canónico;
  - publicación atómica con el publicador compartido, idempotente;
  - un archivo alterado se informa y nunca se sobrescribe.
- **Presupuesto de rutas:** la ruta más larga es la carpeta del almacén + 117 caracteres, y el temporal es más corto que el destino. En el worktree de Windows queda muy por debajo de 259.
- Los artefactos, almacenes, esquemas, secuencias, configuraciones y versiones anteriores no cambian.
- La fiabilidad no corrige la selección de un modelo después de ver una comparación ni los cambios de régimen. Con muestras pequeñas, la cobertura real puede quedar por debajo de la nominal.
- No hay recalibración. Si se propone, será otra versión, ajustada solo con el pasado y nunca aplicada a predicciones ya emitidas.

**Verificación histórica en Linux de la v2, informada por Claude** (Cloud, Python 3.11.15, scikit-learn 1.9.1, fixtures sintéticas; no son resultados de esta sesión ni acreditan Windows): Fase 4 `73 passed` (fiabilidad 23, explicación 16, caso de uso 14, almacén 9 y web, API y comando 11), también con el límite de 259 caracteres de Windows simulado (carpeta de pytest de 61 y `%TEMP%` de 34: 0 rutas rechazadas); Fase 3 `81 passed`; Productos 1 a 6 (`85`, `39`, `66`, `94`, `96` y `73 passed`), lista de Productos 1 a 3 del script `229 passed` y Fase 5 `94 passed`; selección de Windows ejecutada en Linux (95 entradas) `2288 passed`; una suite completa `6533 passed`; OpenSSL `SUPERADOS 7/7` en modo `exigir` sobre la selección y sobre la suite; demostración sintética 8/8; `pip check` limpio; espacios limpios, incluidos los archivos nuevos; revisión visual con Bootstrap real (Chromium de Playwright, 1366 y 390 px; PDF en Carta vertical y horizontal, A4 vertical y Legal vertical) sin desbordamiento horizontal; parche comprobado en una extracción limpia (aplicar, revertir y contenido final idéntico). La primera suite completa dio `9 failed`: 8 por una regla de arquitectura (solo `modelo.py` importa scikit-learn en `application/ml`) y 1 por la lista de páginas imprimibles. Se corrigieron moviendo la lectura del estimador a `modelo.py` y añadiendo `predicciones/` a esa lista, y después todo pasó. **v2:** una auditoría encontró que, si el lanzador del hilo fallaba, el registro propio del centro quedaba `en_curso`, sin fecha de finalización, y la página de estado seguía consultando. La regresión nueva por el POST real con un lanzador que falla falló sobre la v1 y pasa con la corrección; las cifras de este párrafo son las de la v2. La página de la ejecución interrumpida y la respuesta 500 se revisaron de nuevo a 1366 y 390 px, sin desbordamiento horizontal; las demás plantillas no cambiaron desde la revisión visual y los PDF de la v1.

**Validación real en Windows de la v2 (evidencia del operador, no ejecutada por Claude; Python 3.14.6):** la primera ejecución de Fase 4 en consola normal dio `72 passed, 1 skipped` por el enlace simbólico; la batería elevada dio `73 passed`. Uvicorn se inició después en consola normal. Selección de Windows `2288 passed`, OpenSSL `SUPERADOS 7/7` en modo `exigir` y `pip check` limpio. **La generación web real posterior falló.** Fue con Baloto, la versión registrada v1 y el corte 2720, en la ejecución `20261013T135713Z-dc2deb60`. Carteras publicó la cartera `adce8ea7…` y, al registrar el juego terminado, `os.replace` lanzó `PermissionError [WinError 5]`; no quedó identificado el actor que bloqueó la sustitución. El hilo murió y los dos registros quedaron `en_curso`. La página mostraba «Interrumpido» con «cartera: en curso» y seguía consultando cada 2 s. Los tres archivos descritos por el operador (dos registros definitivos y el temporal) se conservan como evidencia; el temporal no se promociona.

**v3 (corrección):**
- El registro de ejecuciones compartido (Productos 3 y 5, laboratorio y centro) mantiene el temporal completo, `fsync` y el reemplazo atómico. Reintenta de forma acotada (10 s en total) solo los bloqueos transitorios de Windows (WinError 5, 32 y 33). Un error permanente se propaga al primer intento, y nunca se escribe sobre el JSON definitivo.
- El centro toma su propio cerrojo de ejecución hasta terminar la explicación. Ante una excepción de Carteras, cierra su registro como `fallo` y valida en el almacén la cartera ya publicada. Una generación sin trabajador se muestra interrumpida, sin escribir, y la página deja de consultar. Mientras la explicación sigue activa, no se declara interrumpida.
- Repetir la misma entrada reutiliza la cartera y completa su explicación sin reentrenar.

**Verificación histórica en Linux de la v3, informada por Claude** (mismo entorno; no son resultados de esta sesión ni acreditan Windows): Fase 4 `96 passed`. La v3 añade 23 pruebas: 14 de publicación del registro y 9 de recuperación. El resultado se mantiene con el límite de 259 caracteres de Windows simulado (0 rutas rechazadas). Fase 3 `81 passed`; Productos 1 a 6 (`85`, `39`, `66`, `94`, `96` y `73 passed`), incluidos los consumidores del registro compartido; lista de Productos 1 a 3 del script `229 passed`; Fase 5 `94 passed`. Selección de Windows ejecutada en Linux (97 entradas): `2311 passed`. Una suite completa: `6556 passed`. OpenSSL `SUPERADOS 7/7` en modo `exigir` sobre la selección y sobre la suite; demostración sintética 8/8; `pip check` limpio; espacios limpios, incluidos los archivos nuevos. Los tres estados nuevos de la página de una generación se revisaron a 1366 y 390 px, sin desbordamiento horizontal. La cadena base → v2 → incremental se comprobó en una extracción limpia (aplicar, revertir, contenido y espacios). Antes de corregir, las simulaciones del registro fallaban sobre la v2. Una sonda con el constructor de la v2 y un solo WinError 5 simulado reprodujo el fallo de Windows: `PermissionError` al primer intento, definitivo en `construccion` y temporal huérfano. Además, 7 de las 8 pruebas iniciales de recuperación fallaban por comportamiento. En Linux, las pruebas de bloqueo real y de concurrencia real comprueban la semántica POSIX: el reemplazo no se bloquea (0 reintentos). En Windows exigen el bloqueo y el reintento reales, y su resultado está pendiente: no se atribuye a Windows nada ejecutado solo en Linux.

**v3.1 (corrección de la carrera de finalización):** la consulta del método real `CentroDePredicciones.ejecucion` observa una sola vez si el trabajador mantiene su cerrojo. Si lo observó vivo, `en_curso` sigue siendo una instantánea válida hasta el siguiente polling. Si lo observó libre, relee el registro antes de derivar una interrupción y conserva un cierre persistido como `exito`. Una regresión determinista, sin sleeps, reproduce la publicación de `exito` y la liberación del cerrojo entre las dos comprobaciones de la v3; esa secuencia no puede devolver `interrumpida`. Se conservan la lectura pura, el cierre ante fallos, la explicación activa y la reutilización de artefactos. El incremental v3.1 se aplica directamente sobre la v2; no requiere aplicar la v3 original.

**Procedimiento histórico de v3.1 (superado por la evidencia nativa v3.3 y el cierre local v3.4 anteriores):** la batería de Fase 4 y la selección que incluyen el caso de enlace simbólico se validaban en consola elevada en el Windows del operador. Las demás baterías y Uvicorn se ejecutan en consola normal. Repetir `generar`, aunque reutilice cartera y explicación, escribe registros de ejecución y crea o usa cerrojos; no es una consulta de solo lectura. En aquella entrega seguían pendientes su validación nativa, recorrido real e impresión; el cierre local v3.4 anterior registra los resultados posteriores. Actions de esa entrega se completó después con PR #94; los checks del futuro PR ML permanecen separados y pendientes.

**Estado histórico al entregar v3.1:** su validación real final estaba pendiente. **Estado vigente:** implementación, validación local v3.4 y cierre documental fusionados en PR #94. La ampliación ML v3.2 tiene suite completa nativa Windows y recorrido real completados con evidencia propia. El cierre ML se aplicó/verificó y quedó integrado en PR #95 con Actions aprobados; acreditación prospectiva separada.

**Pendientes vigentes separados:**
- Fase 9.4 v2 (modelos registrados, carteras y resultados guardados, solo de consulta): validada en Linux y Windows nativo con Brave y aprobada por auditoría, sobre el merge del PR #102; integrada en PR #104 (merge `9fde216c5667bd7a1ddb8553a73857f5cfb07e61`); CI bloqueado por facturación, con sus cinco jobs sin ejecutar. La 9.3 v2 está integrada en PR #102 con sus cinco trabajos aprobados ([cierre del operador](backend/docs/fase9_3_validacion_operador_2026-10-27.md)) ([detalle](backend/docs/fase9_frontend.md#entrega-94-modelos-carteras-y-resultados-guardados), [protocolo](backend/docs/fase9_windows.md#entrega-94-validación-nativa-completada)).
- Fase 9.2 (páginas de las métricas anteriores y horario de consulta): validada en Windows nativo con Brave y aprobada por la auditoría el 26 de octubre de 2026 ([validación del operador](backend/docs/fase9_2_validacion_operador_2026-10-26.md)). Después se integró en PR #101 (`ed0ee427`), con sus cinco checks aprobados e incluido el arreglo de pruebas `e38362bf`. La 9.1 se integró en PR #100 y la 9.5 en PR #105; la Fase 9 quedó cerrada el 1 de noviembre de 2026 ([cierre global](backend/docs/fase9_cierre_global_2026-11-01.md)). Fase 8 se integró en PR #99 (CI `40133227968`); Fase 7, en PR #98 ([cierre local](backend/docs/fase7_validacion_operador_2026-10-24.md)); Fase 6, en PR #96;
- Fase 6, horario de consulta por juego (entrega 9.2): validado en Windows y auditado. La v2 corrigió los hallazgos de la auditoría de la v1: lectura de fechas del plan, espacio de nombres XML, confirmación del slot antes de consultar y reversión sin activar ni retirar tareas vivas. La v3 corrigió F92-NAT-01: `StartWhenAvailable` omitido por el Programador vale su predeterminado `false`. La v4 corrigió F92-TEST-01: un ayudante de prueba en Windows PowerShell 5.1. El ensayo nativo B con un testigo sintético está aprobado. *Actualización:* Daniel migró y activó en Windows `LP6-01023009031fcabd` con el horario por juego. Según la confirmación del auditor (no son pruebas de esta entrega), en la captura del 27 de octubre de 2026 a las 00:11, hora de Colombia, quedaron verificadas nueve ejecuciones programadas y quince consultas en sus franjas: siete de MiLoto, tres de Baloto, tres de Revancha y dos de ColorLoto, sin consultas duplicadas ni fallos de sincronización reportados. Aquella captura no tenía resultados nuevos. La observación posterior del 27 de octubre a las 10:21, auditada sobre la captura de Daniel, acredita una novedad incorporada automáticamente y su siguiente predicción con explicación guardada en cada juego: 20 ciclos conservados, 33 consultas (8 de MiLoto, 9 de Baloto, 9 de Revancha y 7 de ColorLoto), sin parejas juego/oportunidad repetidas ni fallos de sincronización reportados; los 29 intentos sin novedad no emitieron otra predicción. Configuración, selecciones de modelos, tarea versión 2 y plan conservados. El último inicio informado es 09:24:45: no acredita disparo exacto a las 09:00 ni recuperación matinal con resultados pendientes, pues los cuatro juegos terminaron de madrugada. Esa recuperación y la limpieza histórica siguen pendientes. Es operación real observada, separada de las pruebas sintéticas 9.3; Codex no ejecutó ciclos ni SQL operativo. [Actualización real de Fase 6](backend/docs/fase9_3_validacion_operador_2026-10-27.md#actualizacion-real-de-fase-6-del-27-de-octubre). ([horario](backend/docs/fase6_horario.md), [migración](backend/docs/fase6_migracion_lp6.md)). El código nuevo rechaza el `ciclo` sin modo de la tarea versión 1: no se actualiza el origen operativo con esa tarea habilitada;
- limpieza verificable de tareas/raíces históricas, pendiente separado que no queda acreditado por las capturas de observación;
- acreditación prospectiva: muestras suficientes por línea y tipo, por su cauce propio.

---

## Actualización y operación automática (Fase 6)

**Fase 6 v3.4 — validación operativa del 23 de octubre de 2026:** tarea Windows y núcleo habilitados. MiLoto incorporó automáticamente el #628 y guardó la cartera/explicación para el #629; ColorLoto incorporó el #229 y guardó las del #230. Histórico canónico previo y selecciones conservados; doce copias HTML anteriores de MiLoto sí cambiaron al reconciliar. La publicación manual y Actions se completaron después en PR #96 (merge `fcadea6a08e8e6b52386a9055be16bb1873b9a29`, Actions `39939306600`); queda la revisión separada de restos históricos. [Evidencias, alcance y salvedades](backend/docs/fase6_validacion_operativa_2026-10-23.md).

La sección **Automatización** (`/automatizacion`) permite consultar estado, historial y avisos de los cuatro juegos, pausar/reanudar el núcleo, marcar ejecuciones interrumpidas y solicitar una comprobación acotada. Los GET leen registros: no sincronizan, generan, entrenan ni crean almacenes. Los POST conservan la protección local existente. La ejecución programada llama directamente a `python -m scripts.operacion_automatica --config RUTA ciclo`; no necesita navegador o Uvicorn ni crea un planificador por proceso web.

**Horario de consulta por juego (entrega 9.2; integrado en PR #101 y aplicado a la tarea real).** Separa el calendario de sorteo del horario de consulta. Hay franjas por juego y día en `America/Bogota`, cada 15 minutos, con inicio incluido y fin excluido. La recuperación de las 09:00 solo actúa para los juegos pendientes. La tarea versión 2 invoca `ciclo --programado --plan HUELLA` y solo tiene los desencadenadores semanales del plan, sin inicio de sesión ni repetición todo el día y con `StartWhenAvailable=false`. Una comprobación de una persona usa `ciclo --manual`. La política se valida una sola vez y la comparten el plan de Windows y la admisión del núcleo. La configuración pasa explícitamente a la versión 2 y el panel muestra franjas, próxima oportunidad y motivo. Durante la validación, la tarea activa seguía en la versión 1; después Daniel la migró y activó con el horario por juego (ver los pendientes vigentes). La v2 de la entrega corrige los hallazgos de la auditoría de la v1: fechas del plan en PowerShell 7, espacio de nombres XML, confirmación del slot justo antes de consultar y reversión segura. Con los ajustes v3 y v4, la validación nativa en Windows y el ensayo con el Programador real y un testigo sintético están aprobados ([validación del operador](backend/docs/fase9_2_validacion_operador_2026-10-26.md)). [Horario](backend/docs/fase6_horario.md), [migración de `LP6-01023009031fcabd`](backend/docs/fase6_migracion_lp6.md).

Cada ciclo valida los destinos explícitos, congela la configuración elegida y la versión registrada, recupera novedades mediante los conectores actuales y reconcilia Resultados. Solo emite la cartera y explicación siguientes antes del inicio del evento objetivo y con histórico íntegro. La BD atrasada no convierte un evento ya alcanzado en futuro. No se reentrena, elige ganador, cambia configuración o sustituye una versión ausente. Baloto y Revancha mantienen sus identidades.

El calendario usa `America/Bogota` y fuentes oficiales consultadas; la hora de publicación no está garantizada. Las correcciones del proveedor se conservan como propuestas inmutables y requieren decisión explícita. Antes de emitir se consultan todas las propuestas pendientes del juego dentro del histórico usado, aunque ya no entren en las páginas recientes ni en las cien entradas del panel; otros juegos o cortes no bloquean esa emisión. Se sigue importando y reconciliando lo admisible, sin sustituir informes anteriores. Hay límites de páginas, recuperación persistente, espera progresiva y respeto de `Retry-After`, con fallo y bloqueo independientes por juego.

La consulta de ejecución relee el registro si desaparece el cerrojo vivo, para conservar un cierre ya publicado. Recuperar vuelve a validar estado y actividad bajo el recurso de la ejecución antes de registrar una interrupción: no sobrescribe cierres terminales ni elimina la detección de procesos realmente terminados.

**Antecedente del protocolo v3.3, anterior a la activación documentada arriba:** La operación con destinos reales se conserva **sin activar**. Daniel completó en Windows nativo la v3.1: **7.243 aprobadas**, cero fallos, errores u omisiones; OpenSSL `exigir` 7/7, demostración sintética de cuatro juegos y `pip check` limpio. Las **47 dirigidas Linux de v3.2** conservan su evidencia propia. Son antecedentes de esas versiones, no resultados v3.3, y no se suman grupos solapados. La tarea testigo v3.2 fue registrada deshabilitada y rechazada al comprobar la exportación; no hubo activación ni disparo. La v3.3 corrige la comparación semántica y conserva plan/exportación/diagnóstico antes de validar. El protocolo de esta entrega termina en aplicar v3.3 sobre v3.2 exacta → pruebas dirigidas en PowerShell 5.1 → devolver evidencia y detenerse. Conservar el worktree y el Python existentes. El nuevo ensayo real del Programador será posterior a la revisión; esta guía no lo inicia ni incluye una orden para ejecutarlo ahora. No se repiten completa, ML, demostración o presentación/PDF por rutina. Operación con destinos reales, PostgreSQL, activación/novedad observada, publicación manual, Actions y acreditación prospectiva mantienen pendientes separados. [Guía técnica Windows](backend/docs/fase6_windows.md), [calendario y fuentes](backend/docs/fase6_fuentes.md), [tarea y disponibilidad](backend/docs/fase6_tarea_windows.md). Se mantienen `experimental_no_acreditado`, AE-39 **NO-GO** y `AUTORIZA_EVALUACION = False`.

## Simulaciones bajo el mecanismo uniforme (Fase 7)

**Estado:** implementada sobre `605afe8c2bb3b38d0fa3abdb6a5d14ba2002b5a6` y verificada en Linux con datos sintéticos y un PostgreSQL de pruebas aislado. La v2 corrige los cuatro hallazgos de la auditoría de la v1 (cierre concurrente leído como interrupción, recuperación que lo sobrescribía, juego de la fila sin comprobar en el listado y tipos JSON sin validar); la v1 no se aplica. La validación nativa Windows, PostgreSQL aislado y la auditoría visual están completadas; F7-VIS-01 corrige la presentación de las interrupciones sin modificar el registro. El [cierre local](backend/docs/fase7_validacion_operador_2026-10-24.md) conserva la procedencia de pruebas y mediciones; integrada en PR #98 (merge `f15f513`) con checks de Linux y Windows aprobados. Diseño, estadísticas, determinismo, persistencia y mediciones: [backend/docs/fase7_simulaciones.md](backend/docs/fase7_simulaciones.md). Pasos nativos: [backend/docs/fase7_windows.md](backend/docs/fase7_windows.md).

**Qué hace.** Compara, por juego y corte, unas pocas estadísticas descriptivas fijadas de antemano con el motor de Fase 5 (frecuencias, repeticiones N−1→N, sumas, consecutivos, superbalota aparte; en ColorLoto pares, números y colores con multiplicidad) con su distribución cuando se simulan 100, 1.000, 10.000, 100.000 o 1.000.000 de históricos con el mecanismo uniforme del juego. Publica percentil, p-valor bilateral +1 y Bonferroni dentro del juego. Es **exploratoria**: no es confirmatoria, no es evidencia prospectiva ni predictiva, no genera combinaciones ni modifica el NO-GO de AE-39.

**Cómo se usa.**
- **Web:** `/simulaciones` (formulario por juego, progreso en segundo plano, resultado y exportaciones CSV/JSON).
- **API interna de solo lectura:** `/api/simulaciones`.
- **Comando:** `python -m scripts.simulaciones simular --juego BALOTO --iteraciones 100000`.

**Garantías.**
- **Fuente canónica:** la tabla `simulaciones`, con sus columnas actuales y sin migración. `parametros` guarda la identidad completa y su clave SHA-256; `resultado_resumen`, el contenido con su huella e integridad.
- **Reutilización:** la misma identidad (histórico, corte, reglas, algoritmo, versión de NumPy, semilla e iteraciones) reutiliza la fila sin simular.
- **Determinismo:** el resultado no depende del tamaño de lote.
- **Publicación:** una sola fila completa, en una transacción propia, protegida por un advisory PostgreSQL de la clave.
- **Ejecución:** proceso trabajador con tiempo máximo y progreso por lotes. Una interrupción solo se informa si el registro sigue `en_curso` al releerlo con el cerrojo libre, y `recuperar` la persiste bajo el cerrojo de la ejecución sin sobrescribir un cierre.
- **Filas:** una sola comprobación (tipos, integridad y juego de `juego_id`) en listado, panel, lectura y reutilización. Una fila alterada se marca sin derribar el panel ni atribuirse a la base, y nunca se sirve ni se sobrescribe.
- **Sin cambios:** AE-49–51 y Producto 5 conservan sus contratos.


## API pública (Fase 8)

**Estado:** v2 sobre `f15f513b431dd9a5dc3a2fb148a63a82a11405b5` (merge del PR #98), validada localmente en Linux y Windows e **integrada en PR #99** (merge `615f3832296d74a7acea44e5ecdf7dc84a11d70a`) con el CI `40133227968` aprobado en Linux y Windows. El 24 de octubre de 2026 se auditaron en Windows 92 pruebas de la API, cuatro sondas y PostgreSQL 16.14 aislado con datos sintéticos; se conservaron el código, los archivos privados y el contenedor operativo. La v2 corrige los cuatro hallazgos de la auditoría de la v1 y añade `tests/unit/api_publica` a la selección de Windows. El despliegue corresponde a Fase 10. [Cierre y evidencias](backend/docs/fase8_validacion_operador_2026-10-24.md). Diseño y limitaciones: [backend/docs/fase8_api_publica.md](backend/docs/fase8_api_publica.md). Protocolo nativo: [backend/docs/fase8_windows.md](backend/docs/fase8_windows.md).

**Arranque soportado** (desde `backend/`): `uvicorn app.api.publica.aplicacion:app --host 127.0.0.1 --port 8010 --no-access-log --no-proxy-headers`. Sin esas dos opciones, Uvicorn escribiría las URL con su consulta en su registro de acceso y reescribiría la IP del cliente con `X-Forwarded-For`.

**Qué hace.** Una entrada FastAPI separada de la aplicación local (`app.api.publica.aplicacion:app`) ofrece, bajo `/api/v1` y solo con GET, juegos, sorteos paginados, estadísticas descriptivas, predicciones guardadas y simulaciones guardadas de los cuatro juegos. Reutiliza los casos de uso existentes. No monta la web ni los routers internos, y no escribe, entrena, simula ni recupera trabajos.

**Garantías.**
- **Autenticación:** cabecera `X-API-Key` frente a huellas SHA-256 configuradas en `API_PUBLICA_CLAVES`. Sin claves predeterminadas: sin configuración válida, la API rechaza las consultas (503). Generación, sustitución y revocación con `python -m scripts.api_publica_claves`.
- **Límites:** cubeta de fichas **por proceso** (no global entre trabajadores), por clave y por IP, con memoria acotada; 429 con `Retry-After`.
- **Contratos:** OpenAPI/Swagger en `/api/v1/docs` con autenticación, ejemplos y un formato de error único que no expone claves, rutas, trazas ni detalles de la base. Un fallo inesperado se convierte dentro de la API en un 500 con `X-Request-ID` y `no-store`, sin llegar al servidor con su traza.
- **Monitoreo:** `/api/v1/estado` (solicitudes, latencia, límites y base) y `/api/v1/salud` sin clave, agrupados por plantilla de ruta y método estándar (los demás, como `OTRO`). CORS deshabilitado salvo lista explícita.
- **Frontend:** la 9.1 consume `/api/v1` a través de la pasarela local; la clave no llega al navegador ([Fase 9.1](#frontend-de-consulta-fase-91)).

## Frontend de consulta (Fase 9.1)

**Estado:** 9.1 integrada en PR #100 (`9966a4b`), con validación del operador en Windows nativo y Brave ([cierre](backend/docs/fase9_validacion_operador_2026-10-25.md)). La **entrega 9.2** añade las páginas de las métricas anteriores (12 en Baloto y en Revancha, 11 en MiLoto y 31 en ColorLoto, incluidos colores y pares número-color) en el mismo índice y la misma ruta de métrica. La coocurrencia de tríos de los juegos numéricos se pagina de forma explícita. Con datos sintéticos, está validada en Linux con Chromium de Playwright y en Windows nativo con Brave: 456 pruebas Vitest y 507 visitas con 26 comprobaciones sobre las métricas del índice (30/30/22/36), a 360, 390 y 1280 px. La auditoría la aprobó ([validación del operador](backend/docs/fase9_2_validacion_operador_2026-10-26.md)). Se integró en PR #101 (`ed0ee427`), con sus cinco checks aprobados. La **entrega 9.3** añade, solo de consulta, la explicación guardada, la clasificación de candidatos y la fiabilidad observada de los cuatro juegos, con una pantalla de fiabilidad propia; su v2 está validada en Linux y Windows nativo con Brave y aprobada por la auditoría; integrada en PR #102 (merge `4f4dd639581168b08c95816660f80fc4f735b1ac`), con los cinco trabajos aprobados: Node 22, Node 24, Chromium/Linux, Python/Linux y Python/Windows (workflows `40589232731` y `40589232763`). Son antecedentes de la 9.3, no resultados de la 9.4 ([cierre del operador](backend/docs/fase9_3_validacion_operador_2026-10-27.md)) ([detalle](backend/docs/fase9_frontend.md#entrega-93-explicación-clasificación-de-candidatos-y-fiabilidad)). La v2 corrige la atribución de fiabilidad: se consulta mediante «Consultar fiabilidad» y solo se muestra como evidencia de la cartera si acredita su contexto completo. En otro caso avisa de la ausencia y conserva el acceso a la fiabilidad general de la configuración actual. La carga inicial, incluido el catálogo sin caché, cuesta 4 fichas (1 + 3); la consulta explícita posterior cuesta 3. `hasta` filtra objetivos y no acredita que la evidencia existiera al emitir la cartera. La Fase 9 quedó cerrada el 1 de noviembre de 2026 en su alcance de consulta ([cierre global](backend/docs/fase9_cierre_global_2026-11-01.md)); su [matriz de huecos](backend/docs/fase9_frontend.md#matriz-de-huecos-de-la-fase-9) conserva lo que queda fuera. Se mantienen `experimental_no_acreditado`, AE-39 **NO-GO** y `AUTORIZA_EVALUACION = False`.

**Plan acordado de cinco partes, completado.** 9.1, 9.2, 9.3, 9.4 y 9.5 están integradas en los PR #100, #101, #102, #104 y #105. La 9.4 implementa consultas de modelos registrados, carteras de Producto 5 y resultados de Producto 6, solo de lectura, sobre el merge exacto del PR #102. Su v2 está validada en Linux y Windows nativo con Brave y aprobada por auditoría e integrada en PR #104; CI bloqueado por facturación, con cinco jobs sin ejecutar. La 9.5 implementa exportación e impresión de la consulta ya cargada y revisa navegación, móvil y accesibilidad; validada en Windows con Brave, auditada e integrada en PR #105 con sus cinco trabajos aprobados. Administración y operación permanecen en HTMX; los gráficos nuevos quedan para después. La Fase 9 quedó cerrada el 1 de noviembre de 2026 en su alcance de consulta ([cierre global](backend/docs/fase9_cierre_global_2026-11-01.md)).

**Entrega 9.4 v2:** consulta por juego de modelos realmente registrados (no el catálogo de candidatos), carteras guardadas de Producto 5 y emisiones/resultados de Producto 6. Listados paginados, fichas explícitas y filtros en la URL, con estados de ausencia, alteración o incompatibilidad y sin entrenar, inferir, reparar ni guardar informes. Carga fría con catálogo: 3 fichas en modelos/carteras y 6 en resultados. Se conservan los arreglos de contexto y cuota de 9.3. [Diseño y matriz](backend/docs/fase9_frontend.md#entrega-94-modelos-carteras-y-resultados-guardados); [validación nativa completada](backend/docs/fase9_windows.md#entrega-94-validación-nativa-completada); [cierre del operador y procedencia](backend/docs/fase9_4_validacion_operador_2026-10-28.md).

**Entrega 9.5:** La entrega 9.5 implementa exportación JSON/CSV local de la consulta cargada, impresión y revisión de navegación, móvil y accesibilidad. La validación nativa en Windows con Brave y la auditoría están completadas; la 9.5 quedó integrada en PR #105 (merge `bad7c8d5bb913d3d780dd4dfa3b6cdcd9f2dad3e`), con los cinco trabajos aprobados (workflows `41327381044` y `41327381002`), y la Fase 9 quedó cerrada ([cierre global](backend/docs/fase9_cierre_global_2026-11-01.md)). El recorrido normal completo no se repitió sobre la fuente final: su parte válida de la v1 se consolida con las revalidaciones dirigidas de F95-NAT-01 y F95-PDF-01 y con la última tanda de cinco escenarios; los no evaluables no son aprobaciones. Exportar o imprimir añade cero solicitudes de red y no consulta fiabilidad. Se conserva la carga automática de predicción de cuatro fichas y el contexto acreditado de la cartera. Las listas exportan sólo la página cargada. [Formatos, matriz y límites](backend/docs/fase9_5_exportacion_impresion.md); [validación nativa completada](backend/docs/fase9_windows.md#entrega-95-validación-nativa-completada); [validación del operador y procedencia](backend/docs/fase9_5_validacion_operador_2026-11-01.md).

La cadena nativa conserva las 173 pruebas backend y la sonda 3/3 de la primera corrida; la continuación ejecutó 780 Vitest nuevos en Windows y cinco escenarios Brave (87 visitas, 15 comprobaciones de navegador, 8 HTTP y 88 capturas). La auditoría posterior aprobó las 88 capturas, sin convertir esa revisión en certificación general de accesibilidad. El comparador externo aceptó exclusivamente cinco descripciones documentales de HTTP 422: el resto del JSON coincide, pero los documentos completos no son idénticos. Se conservan la procedencia de Linux y Windows y el producto v2, sin repetir baterías por este cierre. La 9.4 quedó integrada en PR #104; su CI no ejecutó pruebas por el bloqueo de facturación. La validación local y nativa no equivale a CI aprobado. Los checks posteriores del PR #105 corrieron sobre un árbol que ya contiene la 9.4, pero no convierten en aprobados aquellos trabajos.

**Qué hace.** `frontend/` es una SPA React + TypeScript + Vite (Bootstrap local, identidad visual de la consola) para consultar juegos y reglas, ficha y resumen con la frescura que informa el backend, sorteos con filtros y detalle, panel y métricas que declara el índice, predicción guardada, modelos registrados, carteras de Producto 5, resultados de Producto 6 y simulaciones guardadas, y salud y estado de la API. `backend/app/pasarela/` es un proceso separado que sirve la SPA compilada y reenvía solo GET de las rutas del OpenAPI versionado a la API pública con su propia clave; no usa casos de uso, dominio ni base. La consola HTMX sigue siendo la aplicación de escritura y ejecución.

**Arranque local** (desde `backend/`, tras `npm ci` y `npm run build` en `frontend/`):
- API: `uvicorn app.api.publica.aplicacion:app --host 127.0.0.1 --port 8010 --no-access-log --no-proxy-headers`
- Pasarela: `uvicorn app.pasarela.aplicacion:app --host 127.0.0.1 --port 8020 --no-access-log --no-proxy-headers` (clave en `PASARELA_CLAVE_API` o en `backend/pasarela.privado.env`, fuera de Git)
- Abrir `http://127.0.0.1:8020/`.

Diseño, controles, límites y verificación: [backend/docs/fase9_frontend.md](backend/docs/fase9_frontend.md). Protocolo nativo: [backend/docs/fase9_windows.md](backend/docs/fase9_windows.md). Órdenes del frontend: [frontend/README.md](frontend/README.md).

---

## Arquitectura (resumen)

Clean Architecture estricta en 4 capas, con dependencias apuntando siempre hacia adentro:

```
domain/          ← reglas de negocio puras (juegos, entidades, value objects). No importa nada de fuera.
application/     ← casos de uso + puertos (interfaces). Depende solo de domain/.
infrastructure/  ← implementaciones concretas (PostgreSQL, scraping, storage). Implementa los puertos de application/.
api/             ← adaptadores de entrada HTTP (web HTML+HTMX y REST JSON). Solo traduce, sin lógica de negocio.
```

Detalle completo con diagramas Mermaid en [ARCHITECTURE.md](./ARCHITECTURE.md).

---

## Stack técnico

| Componente | Tecnología |
|---|---|
| Backend | Python 3.11+, FastAPI |
| Base de datos | PostgreSQL 16 |
| ORM / Migraciones | SQLAlchemy 2.x + Alembic |
| Frontend | Jinja2 + HTMX + Bootstrap 5 (consola); consulta 9.1: React 19 + TypeScript + Vite, Bootstrap local |
| Scraping | requests + BeautifulSoup4 |
| Tests | pytest |
| Contenedores | Docker Compose (PostgreSQL) |

---

## Requisitos

- **Docker** y **Docker Compose** (para PostgreSQL)
- **Python 3.11+**
- **Git**

No se necesita instalar PostgreSQL en el sistema anfitrión — corre en un contenedor.

---

## Instalación y ejecución (desde cero)

### Opción 1 — Un solo comando

```bash
git clone <url-del-repositorio>
cd loteria-predictor
./run.sh
```

`run.sh` hace, en orden, todo lo necesario:
1. Levanta PostgreSQL vía Docker Compose y espera a que acepte conexiones.
2. Crea un entorno virtual de Python (`backend/.venv`) si no existe.
3. Instala las dependencias (`pip install -r requirements.txt`).
4. Copia `.env.example` a `.env` si no existe.
5. Aplica las migraciones de Alembic (crea el esquema completo y siembra los 4 juegos + la paleta de colores de ColorLoto).
6. Inicia el servidor en **http://localhost:8000** con recarga automática.

No hay pasos manuales ocultos: si `./run.sh` falla, el problema está indicado en la salida del propio script.

### Opción 2 — Paso a paso (para desarrollo)

```bash
# 1. Levantar PostgreSQL
docker compose up -d postgres

# 2. Crear entorno virtual e instalar dependencias
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Variables de entorno
cp .env.example .env
# Editar .env si tu configuración de PostgreSQL difiere de la de docker-compose.yml

# 4. Migraciones
alembic upgrade head

# 5. Levantar el servidor
uvicorn app.main:app --reload
```

Abre **http://localhost:8000**.

---

## Variables de entorno

Definidas en `backend/.env` (ver `backend/.env.example`):

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `DATABASE_URL` | Cadena de conexión a PostgreSQL (formato SQLAlchemy) | `postgresql+psycopg://loteria:loteria@localhost:5432/loteria_predictor` |
| `ENVIRONMENT` | Entorno de ejecución (`development`/`production`) | `development` |

---

## Base de datos y migraciones

El esquema se gestiona íntegramente con **Alembic**. Nunca se debe crear tablas manualmente.

```bash
cd backend
alembic upgrade head          # aplicar todas las migraciones pendientes
alembic downgrade -1          # revertir la última migración
alembic revision -m "mensaje" # crear una migración nueva (vacía, para editar a mano)
alembic history                # ver el historial de migraciones
```

Migraciones actuales:

| Revisión | Contenido |
|---|---|
| `0001` | Esquema inicial completo (juegos, sorteos, números, colores, estadísticas, modelos, predicciones, simulaciones) + siembra de MiLoto, Baloto Revancha y ColorLoto + la paleta de ColorLoto |
| `0002` | Tabla `sincronizaciones` (registro de cada ejecución del módulo de importación) |
| `0003` | Índice compuesto `(juego_id, fecha)` en `sorteos` (optimización de rendimiento) |
| `0004` | Siembra el juego `BALOTO` (clásico) -corrección arquitectónica: Baloto y Revancha son juegos independientes relacionados por `numero_sorteo`, ver [ARCHITECTURE.md](./ARCHITECTURE.md#baloto-y-revancha-por-qué-son-juegos-independientes) |
| `0005` | Columnas `hasta_numero_sorteo` y `parametros_hash` en `estadisticas`, con dos índices únicos parciales -soporte de caché persistido para el motor estadístico, ver [ARCHITECTURE.md](./ARCHITECTURE.md#motor-estadístico-y-caché-persistido) |

---

## Ejecución de pruebas

```bash
cd backend
source .venv/bin/activate
pytest                          # toda la suite
pytest tests/unit/connectors/   # solo el módulo de adquisición de datos
pytest -v                       # modo detallado
pytest --cov=app                # con cobertura (requiere pytest-cov, ya en requirements.txt)
```

La suite cubre dominio (reglas de los 4 juegos), casos de uso (con repositorios en memoria, sin necesidad de PostgreSQL), parsers de scraping (contra fixtures HTML), persistencia incremental de la sincronización (con un fake que simula transacciones reales de PostgreSQL, incluyendo rollback), y el motor/caché/rutas de estadísticas.

**Checkpoint validado (Etapa V, generalización a 3 juegos):** `904 passed` con `pytest` real contra PostgreSQL, Python 3.14.6, `pip check` limpio. **Checkpoint validado (Etapa W, distancia desde la última aparición):** `946 passed` con `pytest` real contra PostgreSQL, mismo entorno. **Checkpoint validado (Etapa X, controles de corte temporal):** `986 passed` con `pytest` real contra PostgreSQL, FastAPI real. **Checkpoint validado (Etapa Y, distribución de números pares e impares):** `1053 passed` con `pytest` real, `pip check` limpio, contra PostgreSQL y FastAPI/Uvicorn reales, Python 3.14. **Checkpoint validado (Etapa Z, distribución inferior/superior + defensa de integridad histórica):** `1133 passed` con `pytest` real en Windows (Python 3.14, `pip check` limpio) contra PostgreSQL y FastAPI/Uvicorn reales. La primera corrida detectó y corrigió un defecto de portabilidad real (un `open()` sin `encoding="utf-8"` fallaba con `UnicodeDecodeError` bajo la codificación por defecto de Windows, cp1252); tras la corrección, la suite completa pasó limpiamente. Las seis rutas (histórico completo y con los tres cortes) respondieron `200`; un corte inválido (`hasta_numero_sorteo=0`) respondió `422`. Validación visual confirmada en los tres juegos: rangos inferior/superior correctos, seis pestañas, gráfica y canvas correctos, seis categorías, tabla, avisos de asimetría y no predicción, navegación y corte correctos. Las tres invariantes del histórico (cantidad exacta, sin duplicados, dentro de rango) se verificaron directamente en PostgreSQL para los 3 juegos, sin ninguna inconsistencia. Se comparó de forma independiente, mediante SQL directo sobre `sorteos`/`sorteo_numeros` (sin usar el motor ni confiar en el JSON cacheado), un total de 36 categorías (3 juegos × histórico/corte × 6 categorías) contra las estadísticas cacheadas, con tolerancia `1e-12` — sin ninguna discrepancia. Toda esta evidencia de Etapa Z (pytest, FastAPI, PostgreSQL, SQL independiente) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **Checkpoint validado (Etapa AA, distribución de pares consecutivos):** `1195 passed` con `pytest` real en Windows (Python 3.14, entorno virtual corto para evitar `WinError 206`, `pip check` limpio), FastAPI/Uvicorn y PostgreSQL reales. Tests focalizados (`test_calcular_y_persistir_estadistica.py`, `test_generalizacion_juegos.py`, `test_registrar_sorteo.py`, `test_estadistica_repository.py`, `test_corte_temporal_navegacion.py`): `450 passed`. Las seis combinaciones juego/corte de la nueva métrica respondieron `200`; cortes inválidos (`0`, `-1`, texto) respondieron `422`. Validación visual confirmada en los tres juegos, incluida la conservación/eliminación correcta del corte. Persistencia verificada: exactamente las seis filas objetivo en PostgreSQL, parámetros exactos por juego, todas vigentes. Validación SQL independiente completa: integridad histórica sin inconsistencias, 30 categorías recalculadas de forma independiente (sin usar el motor ni la caché) coincidiendo exactamente con lo cacheado, y verificación JSONB exacta de parámetros sin discrepancias. **Checkpoint validado (Etapa AB, racha máxima de números consecutivos):** `1259 passed` con `pytest` real en Windows (Python 3.14, `pip check` limpio), FastAPI/Uvicorn y PostgreSQL reales. Tests focalizados (mismos 5 archivos de Etapa AA): `514 passed`. Antes de este checkpoint se encontró y corrigió una línea muerta e inalcanzable dentro de la receta de racha máxima (un segundo `return` residual, sin ningún efecto en comportamiento — confirmado con los mismos 1259 tests en verde antes y después). Las seis combinaciones juego/corte respondieron `200`; los tres cortes inválidos (`0`, `-1`, texto) respondieron `422`. Validación visual confirmada en los tres juegos: categorías 1..5 sin categoría 0, explicación de la diferencia frente a pares consecutivos, advertencia no predictiva, navegación y corte correctos. Persistencia verificada: exactamente las seis filas objetivo, parámetros exactos por juego, todas vigentes. Validación SQL independiente mediante la técnica "islands and gaps" (sin usar el motor ni la caché): integridad histórica sin inconsistencias, 30 categorías recalculadas coincidiendo exactamente con lo cacheado, verificación JSONB exacta de parámetros sin discrepancias. Toda esta evidencia de Etapa AB fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **Checkpoint validado (Etapa AC, repeticiones entre sorteos consecutivos):** `1321 passed` con `pytest` real en Windows (Python 3.14.6, entorno virtual corto, `pip check` limpio), FastAPI/Uvicorn y PostgreSQL reales. Tests focalizados (mismos 5 archivos de etapas anteriores): `576 passed`. Las seis combinaciones juego/corte respondieron `200`; los tres cortes inválidos (`0`, `-1`, texto) respondieron `422`. Validación visual confirmada en los tres juegos: tarjeta "Transiciones analizadas", categorías 0..5, explicación de la transición estricta N→N+1, huecos no comparados, advertencia no predictiva, navegación y corte correctos, MiLoto sin la métrica de superbalota. Persistencia verificada: exactamente las seis filas objetivo, parámetros exactos por juego, todas vigentes. Integridad histórica sin inconsistencias. Validación SQL independiente (self-join estricto, `LEFT JOIN`/`COUNT` para preservar la categoría cero, escenario/corte separados explícitamente): 36 categorías recalculadas coincidiendo exactamente con lo cacheado, categoría cero con apariciones reales en los seis escenarios, conservación de masa (`suma_apariciones = total_transiciones`) sin discrepancias, verificación JSONB exacta de parámetros sin discrepancias. Toda esta evidencia de Etapa AC fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **Checkpoint validado (Etapa AD, endurecimiento de integridad de `frecuencia_superbalota`):** `1343 passed` con `pytest` real en Windows (Python 3.14.6, entorno virtual corto, `pip check` limpio), FastAPI/Uvicorn y PostgreSQL reales. Tests focalizados (9 archivos relevantes): `659 passed`. **Esta etapa no agregó una décima visualización** -endurece la receta ya existente `frecuencia_superbalota` (misma ruta, mismo `tipo_estadistica`, misma identidad de caché): un histórico con `superbalota=None` o fuera de `1..16` para Baloto/Revancha ahora se rechaza en su totalidad (`ResultadoHistoricoInconsistenteError`, 500 controlado; tipos cerrados `SUPERBALOTA_AUSENTE`/`RANGO_SUPERBALOTA`, aditivos y compatibles byte a byte con los 3 tipos previos) en vez de la exclusión silenciosa previa del motor. Las cuatro combinaciones válidas (Baloto/Revancha, histórico completo y corte 2694) respondieron `200`; MiLoto y los tres cortes inválidos respondieron `422`. Validación visual sin errores en las cuatro páginas. Integridad real verificada directamente en PostgreSQL: cero superbalotas ausentes y cero fuera de rango en Baloto/Revancha. Se encontraron seis cachés vigentes legítimas (Baloto y Revancha, cada una con histórico completo y dos cortes reales usados durante la validación), todas con la identidad exacta `{"rango_min": 1, "rango_max": 16}`, sin ninguna caché con parámetros distintos. Comparación SQL independiente de 96 categorías (6 escenarios × 16 valores de superbalota) contra las cachés, con tolerancia `1e-12`: sin ninguna discrepancia. Toda esta evidencia de Etapa AD fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **Checkpoint validado (Etapa AE-0, catálogo completo y vigencia histórica de colores):** `1372 passed` con `pytest` real en Windows (Python 3.14.6, entorno virtual corto, `pip check` limpio), PostgreSQL real disponible. Tests focalizados (5 archivos relevantes): `276 passed`. **AE-0 es una preparación interna de infraestructura, no una décima visualización** -no agregó receta, ruta, View Model, template, canvas ni navegación de ColorLoto; la sección de estadísticas sigue teniendo exactamente 9 visualizaciones. `ColorRepository` incorporó `listar_todos(juego_id)` (catálogo completo del juego, activos e inactivos, sin filtrar por fecha ni por `activo`, una sola consulta) y corrigió la semántica histórica de `listar_vigentes`: sin fecha sigue representando la paleta actual (sin cambios, compatible con `GameFactory`); con `en_fecha` explícita representa la paleta históricamente vigente en esa fecha, sin excluir por el estado actual de `activo` -un color hoy retirado pero vigente en esa fecha ya se incluye correctamente. Orden determinista por `codigo` en ambas rutas. Una sola consulta por operación pública, sin N+1, confirmado por auditoría estructural del código real y por los tests dedicados (SciPy/SQLAlchemy real no se ejecutó en el entorno de desarrollo, solo en la validación real de Windows del usuario). Toda esta evidencia de Etapa AE-0 fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **ColorLoto sigue sin ninguna visualización web conectada** -AE-0 es exclusivamente la base de datos/repositorio que una futura etapa de visualización necesitará. **Checkpoint validado (Etapa AE-1, primera visualización web de ColorLoto -frecuencia de números):** `1434 passed` con `pytest` real en Windows (Python 3.14.6, entorno virtual corto, `pip check` limpio), FastAPI/Uvicorn y PostgreSQL reales. Tests focalizados (los 6 archivos relevantes: `test_calcular_y_persistir_estadistica.py`, `test_generalizacion_juegos.py`, `test_registrar_sorteo.py`, `test_estadistica_repository.py`, `test_color_repository.py`, `test_colorloto_game.py`): `659 passed`. Una auditoría posterior a la implementación inicial encontró y corrigió un **defecto crítico real de orden de registro de rutas**: Starlette (el motor de enrutamiento de FastAPI) evalúa las rutas en el orden exacto en que se registran, no por especificidad -la ruta genérica `/estadisticas/{juego_slug}/frecuencia-numeros` estaba declarada antes que la ruta literal `/estadisticas/colorloto/frecuencia-numeros`, así que una petición real a la URL de ColorLoto habría sido interceptada por el handler numérico genérico (`juego_slug="colorloto"`), dejando el handler dedicado de ColorLoto inalcanzable. Corregido moviendo el handler de ColorLoto antes de la ruta genérica conflictiva -confirmado ahora con el enrutador real de FastAPI en Windows: `/estadisticas/colorloto/frecuencia-numeros` (histórico completo y con corte `100`) respondió `200`; los tres cortes inválidos (`0`, `-1`, texto) respondieron `422`; la métrica incompatible `/estadisticas/colorloto/distribucion-pares-impares` respondió `404` correctamente. Validación visual confirmada en ambos escenarios (histórico completo y corte 100): gráfica, tabla, categorías 1..7, navegación, control de corte y textos explicativos correctos, con "Apariciones promedio por sorteo" presentada consistentemente como promedio -nunca como porcentaje ni predicción. Integridad histórica verificada directamente en PostgreSQL: ningún sorteo con cantidad de pares distinta de 6, ningún número fuera de `1..7`, ningún color de otro juego, ningún color fuera de su vigencia histórica -las cuatro comprobaciones sin ninguna inconsistencia. Se encontraron exactamente las dos cachés vigentes esperadas (histórico completo y corte 100), ambas con la identidad exacta `{"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}`. Cálculo SQL independiente (sin usar el motor ni confiar en la caché) de las 14 categorías (7 números × 2 escenarios) coincidiendo exactamente con lo cacheado; conservación de masa confirmada (209×6=1254 en el histórico completo, 100×6=600 en el corte, suma de promedios = 6 en ambos escenarios); comparación SQL independiente contra las dos cachés vigentes con tolerancia `1e-12` y verificación JSONB exacta de parámetros, ambas sin ninguna discrepancia. Toda esta evidencia de Etapa AE-1 (pytest, FastAPI, PostgreSQL, HTTP real, SQL independiente) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **AE-3 (siguientes métricas de ColorLoto) continúa pendiente.** **Checkpoint validado (Etapa AE-2, segunda visualización web de ColorLoto -frecuencia de colores):** `1492 passed` con `pytest` real en Windows (Python 3.14.6, entorno virtual corto, `pip check` limpio), FastAPI/Uvicorn y PostgreSQL reales. Tests focalizados (9 archivos relevantes: `test_calcular_y_persistir_estadistica.py`, `test_generalizacion_juegos.py`, `test_estadistica_repository.py`, `test_registrar_sorteo.py`, `test_corte_temporal_navegacion.py`, `test_colorloto_game.py`, `test_color_repository.py`, `test_chartjs_local.py`, `test_editar_eliminar_sorteo_invalidacion.py`): `780 passed`. Reconciliación exacta: `1434 + 58 = 1492` -58 tests nuevos netos, distribuidos en `+25` (`test_calcular_y_persistir_estadistica.py`), `+27` (`test_generalizacion_juegos.py`), `+5` (`test_estadistica_repository.py`) y `+1` (`test_registrar_sorteo.py`). Reutiliza el motor `calcular_frecuencia_colores` ya existente (sin modificarlo), el mismo envoltorio de histórico y la misma validación de integridad que `frecuencia_numeros_colorloto`, sin duplicar ninguna regla. Conecta `frecuencia_colores_colorloto` en `/estadisticas/colorloto/frecuencia-colores`: cuenta apariciones de cada color observado en las 6 balotas de cada sorteo, ignorando el número -la magnitud se presenta igual que en AE-1, como "Apariciones promedio por sorteo" (nunca "porcentaje"), y puede legítimamente superar 1.0 porque un color puede repetirse dentro del mismo sorteo -confirmado con el cálculo SQL independiente real (BLANCO y ROJO ambos con promedio 1.08 en el histórico completo). Auditoría del orden de registro de rutas confirmada ahora con el enrutador real de FastAPI en Windows: `/estadisticas/colorloto/frecuencia-colores` (histórico completo y con corte `100`) respondió `200`; los tres cortes inválidos (`0`, `-1`, texto) respondieron `422`; la ruta incompatible `/estadisticas/baloto/frecuencia-colores` respondió `404` correctamente. Validación visual confirmada en ambos escenarios (histórico completo con 209 sorteos, corte con 100 sorteos): gráfica y tabla con los 6 colores, barras con colores coherentes, "Apariciones promedio por sorteo" sin `%`, explicación de repetición dentro del sorteo, aviso no predictivo, navegación entre las dos métricas de ColorLoto con el corte conservado al alternar. Integridad histórica verificada directamente en PostgreSQL: las cuatro comprobaciones (cantidad de pares, rango de número, color de otro juego, vigencia histórica) sin ninguna inconsistencia. Se encontraron exactamente las dos cachés vigentes esperadas (histórico completo y corte 100), ambas con la identidad exacta `{"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}`. Cálculo SQL independiente (sin usar el motor ni confiar en la caché) de las 12 categorías (6 colores × 2 escenarios) coincidiendo exactamente con lo cacheado; conservación de masa confirmada (209×6=1254 en el histórico completo, 100×6=600 en el corte, suma de promedios = 6 en ambos escenarios); comparación SQL independiente contra las dos cachés vigentes con tolerancia `1e-12` y verificación JSONB exacta de parámetros, ambas sin ninguna discrepancia. Toda esta evidencia de Etapa AE-2 (pytest, FastAPI, PostgreSQL, HTTP real, SQL independiente) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **AE-4 (siguientes métricas de ColorLoto) continúa pendiente.** **Checkpoint validado (Etapa AE-3, tercera visualización web de ColorLoto -frecuencia de pares exactos número-color):** `1554 passed` con `pytest` real en Windows (Python 3.14.6, entorno virtual corto, `pip check` limpio), FastAPI/Uvicorn y PostgreSQL reales. Tests focalizados (9 archivos relevantes: `test_calcular_y_persistir_estadistica.py`, `test_generalizacion_juegos.py`, `test_estadistica_repository.py`, `test_registrar_sorteo.py`, `test_corte_temporal_navegacion.py`, `test_colorloto_game.py`, `test_color_repository.py`, `test_chartjs_local.py`, `test_editar_eliminar_sorteo_invalidacion.py`): `842 passed`. Reconciliación exacta: `1492 + 62 = 1554` -62 tests nuevos netos, distribuidos en `+28` (`test_calcular_y_persistir_estadistica.py`), `+28` (`test_generalizacion_juegos.py`), `+5` (`test_estadistica_repository.py`) y `+1` (`test_registrar_sorteo.py`). Reutiliza el motor `calcular_frecuencia_pares_numero_color` ya existente (sin modificarlo), el mismo envoltorio de histórico y la misma validación de integridad que las dos métricas anteriores de ColorLoto, sin duplicar ninguna regla. Conecta `frecuencia_pares_colorloto` en `/estadisticas/colorloto/frecuencia-pares-numero-color`: cuenta apariciones de cada PAR EXACTO número-color (42 categorías con el catálogo actual, 7×6), la unidad más granular de las tres visualizaciones de ColorLoto -mismo criterio de "Apariciones promedio por sorteo", puede legítimamente superar 1.0 si el mismo par se repite dentro de un sorteo. El motor codifica cada categoría como `f"{numero}-{color}"` (contrato Paso 13, ya existente), deserializado de forma inequívoca con `valor.split("-", maxsplit=1)`. Confirmado ahora con el enrutador real de FastAPI en Windows: histórico completo y corte `100` respondieron `200`; los tres cortes inválidos (`0`, `-1`, texto) respondieron `422`; la ruta incompatible `/estadisticas/baloto/frecuencia-pares-numero-color` respondió `404` correctamente. Validación visual confirmada en ambos escenarios (histórico completo con 209 sorteos, corte con 100 sorteos): eje X con los números 1..7, seis datasets agrupados por color, tabla con las 42 categorías exactas correctamente diferenciadas (por ejemplo, `1-AMARILLO` frente a `1-AZUL`), "Apariciones promedio por sorteo" sin `%`, tres pestañas de ColorLoto operativas con el corte conservado al alternar, textos explicativos y aviso no predictivo presentes, sin errores visuales ni en Uvicorn. Integridad histórica verificada directamente en PostgreSQL: las cuatro comprobaciones (cantidad de pares, rango de número, color de otro juego, vigencia histórica) sin ninguna inconsistencia. Se encontraron exactamente las dos cachés vigentes esperadas (histórico completo y corte 100), ambas con exactamente 42 categorías y la identidad exacta `{"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}`. Cálculo SQL independiente (sin usar el motor ni confiar en la caché) de las 84 categorías (42 pares × 2 escenarios) coincidiendo exactamente con lo cacheado; conservación de masa confirmada (209×6=1254 en el histórico completo, 100×6=600 en el corte, suma de promedios = 6 en ambos escenarios); comparación SQL independiente contra las dos cachés vigentes con tolerancia `1e-12` y verificación JSONB exacta de parámetros, ambas sin ninguna discrepancia. Toda esta evidencia de Etapa AE-3 (pytest, FastAPI, PostgreSQL, HTTP real, validación visual, SQL independiente) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **ColorLoto tiene ahora tres visualizaciones validadas**; **AE-4 (siguientes métricas de ColorLoto) continúa pendiente.** **Checkpoint validado (Etapa AE-4, cuarta visualización web de ColorLoto -atrasos de números):** `1614 passed` con `pytest` real en Windows (Python 3.14.6, entorno virtual corto, `pip check` limpio), FastAPI/Uvicorn y PostgreSQL reales. Tests focalizados (9 archivos relevantes: `test_calcular_y_persistir_estadistica.py`, `test_generalizacion_juegos.py`, `test_estadistica_repository.py`, `test_registrar_sorteo.py`, `test_corte_temporal_navegacion.py`, `test_colorloto_game.py`, `test_color_repository.py`, `test_chartjs_local.py`, `test_editar_eliminar_sorteo_invalidacion.py`): `902 passed`. Reconciliación exacta: `1554 + 60 = 1614` -60 tests nuevos netos, distribuidos en `+25` (`test_calcular_y_persistir_estadistica.py`), `+29` (`test_generalizacion_juegos.py`), `+5` (`test_estadistica_repository.py`) y `+1` (`test_registrar_sorteo.py`). Reutiliza el motor `calcular_atrasos_numeros_colorloto` ya existente (sin modificarlo) y el serializador `_serializar_atrasos` ya validado en producción desde la Etapa W, sin duplicar ninguna regla. Conecta `atrasos_numeros_colorloto` en `/estadisticas/colorloto/atrasos-numeros`: mide cuántos sorteos han pasado desde la última aparición de cada número, ignorando el color -nunca se llama "frecuencia", "promedio" ni "porcentaje" a esta magnitud, distinta por naturaleza de las tres métricas anteriores. Confirmado ahora con el enrutador real de FastAPI en Windows: `/estadisticas/colorloto/atrasos-numeros` (histórico completo y con corte `100`) respondió `200`; `/estadisticas/baloto/atrasos-numeros` (la ruta genérica preexistente) siguió respondiendo `200` correctamente, confirmando que la ruta literal de ColorLoto -registrada antes de la genérica homónima, único caso de colisión real entre las cuatro métricas de ColorLoto- no interfirió con el handler numérico ya existente; los tres cortes inválidos (`0`, `-1`, texto) respondieron `422`; la métrica incompatible `/estadisticas/colorloto/distribucion-pares-impares` respondió `404` correctamente. El usuario inspeccionó las páginas de histórico completo y corte 100 y no encontró errores. Integridad histórica verificada directamente en PostgreSQL: las cuatro comprobaciones (cantidad de pares, rango de número, color de otro juego, vigencia histórica) sin ninguna inconsistencia. Se encontraron exactamente las dos cachés vigentes esperadas (histórico completo y corte 100), ambas con exactamente 7 categorías y la identidad exacta `{"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}`. Cálculo SQL independiente (sin usar el motor ni confiar en la caché) de las 14 categorías (7 números × 2 escenarios) coincidiendo exactamente con lo cacheado -atraso `= referencia − último_numero_sorteo_con_aparición`, con atraso `0` en la referencia (números 1, 3, 4 y 6 en el histórico completo) y valores positivos reales en el resto; comparación SQL independiente contra las dos cachés vigentes (número, atraso, último sorteo de aparición y total de sorteos) y verificación JSONB exacta de parámetros, ambas sin ninguna discrepancia. Toda esta evidencia de Etapa AE-4 (pytest, FastAPI, PostgreSQL, HTTP real, validación visual, SQL independiente) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **ColorLoto tiene ahora cuatro visualizaciones validadas**; **AE-5 (siguientes métricas de ColorLoto) continúa pendiente.** Ninguno de estos números es un total permanente — crecerá con cada etapa nueva.

**Checkpoint validado (Etapa AE-4P, endurecimiento transversal -contrato temporal e invalidación de caché de la paleta de ColorLoto):** `1678 passed` con `pytest` real en Windows (Python 3.14.6, entorno virtual corto, `pip check` limpio), FastAPI/Uvicorn y PostgreSQL reales. Tests focalizados (8 archivos: `test_calcular_y_persistir_estadistica.py`, `test_estadistica_repository.py`, `test_gestionar_paleta_colores.py`, `test_color_repository.py`, `test_registrar_sorteo.py`, `test_editar_eliminar_sorteo_invalidacion.py`, `test_generalizacion_juegos.py`, `test_corte_temporal_navegacion.py`): `943 passed`. AE-4 permanece validada con `1614 passed` reales; AE-4P **no** agregó ninguna quinta visualización de ColorLoto -permanecen 13 visualizaciones globales (9 numéricas + 4 de ColorLoto) y AE-5 continúa pendiente. Reconciliación exacta: `1614 + 64 = 1678`.

Confirmado ahora con el enrutador real de FastAPI en Windows: `/estadisticas/colorloto/frecuencia-colores` (histórico completo y con corte `100`) y `/estadisticas/colorloto/frecuencia-pares-numero-color` (histórico completo y con corte `100`) respondieron `200`; los tres cortes inválidos (`0`, `-1`, texto) respondieron `422`; la ruta incompatible `/estadisticas/baloto/frecuencia-colores` respondió `404` correctamente -resumen exacto `4×200`, `3×422`, `1×404`. El usuario abrió las cuatro páginas válidas (histórico completo y corte 100 de ambas métricas) y no observó errores.

PostgreSQL real mostró exactamente ocho filas relevantes de `frecuencia_colores_colorloto`/`frecuencia_pares_colorloto`: cuatro cachés antiguas sin el marcador (dos métricas × completo/corte 100, calculadas bajo la política anterior) coexistiendo junto a cuatro cachés nuevas con el marcador exacto -`{"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6, "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"}`-, confirmando que el propio mecanismo de `parametros_hash` produce hashes distintos entre ambas identidades sin ningún SQL manual ni migración; cada tipo/escenario tiene exactamente una caché nueva vigente; una consulta dirigida a detectar parámetros nuevos incorrectos devolvió `0 rows`; las filas antiguas permanecen en la tabla sin ser seleccionadas por la identidad nueva.

Categorías y conservación de masa confirmadas con datos reales: frecuencia de colores con 6 categorías en ambos escenarios (209 sorteos en el histórico completo, 100 en el corte), frecuencia de pares con 42 categorías en ambos escenarios; suma de apariciones exacta en los cuatro casos (1254 = 209×6 en el histórico completo, 600 = 100×6 en el corte, para ambas métricas) -conservación de masa exacta. La comparación SQL independiente de frecuencia de colores contra la caché nueva, para ambos escenarios, devolvió `0 rows`; la comparación de las 84 categorías de pares número-color (42 completo + 42 corte 100) contra la caché nueva, comparadas individualmente, también devolvió `0 rows`. Ninguna consulta ejecutó escrituras.

Toda esta evidencia de Etapa AE-4P (pytest, FastAPI, PostgreSQL, HTTP real, validación visual, SQL independiente) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **ColorLoto tiene ahora cuatro visualizaciones validadas, con el contrato temporal de colores y la invalidación de caché de paleta también validados**; **AE-5 (siguientes métricas de ColorLoto) continúa pendiente.** Fase 5 continúa parcial. Ninguno de estos números es un total permanente.

**Checkpoint validado (Etapa AE-5, quinta visualización web de ColorLoto -atrasos de colores, decimocuarta visualización global):** `1747 passed` con `pytest` real en Windows (Python 3.14.6, entorno virtual corto, `pip check` limpio), FastAPI/Uvicorn y PostgreSQL reales. Tests focalizados (9 archivos: `test_calcular_y_persistir_estadistica.py`, `test_generalizacion_juegos.py`, `test_estadistica_repository.py`, `test_gestionar_paleta_colores.py`, `test_registrar_sorteo.py`, `test_corte_temporal_navegacion.py`, `test_color_repository.py`, `test_editar_eliminar_sorteo_invalidacion.py`, `test_chartjs_local.py`): `1025 passed`. AE-4 permanece validada con `1614 passed` reales; AE-4P permanece validada con `1678 passed` reales. Reconciliación exacta: `1678 + 69 = 1747`.

Confirmado ahora con el enrutador real de FastAPI en Windows: `/estadisticas/colorloto/atrasos-colores` (histórico completo y con corte `100`) respondió `200`; los tres cortes inválidos (`0`, `-1`, texto) respondieron `422`; la ruta incompatible `/estadisticas/baloto/atrasos-colores` respondió `404` correctamente -resumen exacto `2×200`, `3×422`, `1×404`. El usuario abrió las dos páginas válidas y reportó explícitamente "no vi errores en las páginas".

PostgreSQL real: las cuatro comprobaciones de integridad histórica (cantidad de pares, rango de número, color de otro juego, vigencia temporal) devolvieron `0 rows`. Se encontraron exactamente las dos cachés vigentes esperadas de `atrasos_colores_colorloto` (histórico completo y corte 100), cada una con exactamente 6 categorías y los parámetros exactos `{"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6, "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"}`; la consulta de parámetros incorrectos devolvió `0 rows`. El cálculo SQL independiente produjo exactamente 12 filas (6 colores × 2 escenarios): en el histórico completo (referencia sorteo 209, 209 sorteos), AMARILLO/AZUL/BLANCO/NEGRO/VERDE con atraso 0 y ROJO con atraso 1; en el corte 100 (referencia sorteo 100, 100 sorteos), AZUL/BLANCO/ROJO/VERDE con atraso 0, AMARILLO con atraso 2 y NEGRO con atraso 3 -confirmando con datos reales que un atraso positivo mayor que 1 es un valor legítimo. En estos datos reales no apareció `N/D` porque los seis colores fueron observados en ambos escenarios -esto no cambia el contrato ni la cobertura automatizada de `N/D` para un color vigente nunca observado, que sigue siendo parte del diseño validado por tests. La comparación completa `FULL JOIN` entre el cálculo SQL independiente y las dos cachés JSONB (código, última aparición, atraso, total de sorteos, con `IS DISTINCT FROM` para comparar nulos de forma segura) devolvió `0 rows` en ambos escenarios, sin ninguna discrepancia.

Toda esta evidencia de Etapa AE-5 (pytest, FastAPI, PostgreSQL, HTTP real, validación visual, SQL independiente) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **ColorLoto tiene ahora cinco visualizaciones validadas**; **AE-6 (siguientes métricas de ColorLoto) continúa pendiente.** Fase 5 continúa parcial. Ninguno de estos números es un total permanente.

**Checkpoint validado (Etapa AE-6, sexta visualización web de ColorLoto -atrasos de pares número-color, decimoquinta visualización global):** `1810 passed` con `pytest` real en Windows (Python 3.14.6, `pip check` limpio), FastAPI/Uvicorn en `127.0.0.1:8000` y PostgreSQL 16 real en Docker. Tests focalizados (4 archivos: `test_calcular_y_persistir_estadistica.py`, `test_generalizacion_juegos.py`, `test_estadistica_repository.py`, `test_corte_temporal_navegacion.py`): `994 passed`. AE-4 permanece validada con `1614 passed` reales; AE-4P con `1678 passed` reales; AE-5 con `1747 passed` reales. Reconciliación exacta: `1747 + 63 = 1810`.
Confirmado con el enrutador real de FastAPI en Windows: `/estadisticas/colorloto/atrasos-pares-numero-color` (histórico completo y con corte `100`) respondió `200`; los tres cortes inválidos (`0`, `-1`, texto) respondieron `422`; la ruta incompatible `/estadisticas/baloto/atrasos-pares-numero-color` respondió `404` correctamente -resumen exacto `2×200`, `3×422`, `1×404`. El usuario abrió las páginas y reportó explícitamente "No vi errores en las páginas."
PostgreSQL real: las cuatro comprobaciones de integridad histórica (cantidad de pares, rango de número, color de otro juego, vigencia temporal) devolvieron `0 rows`. Se encontraron exactamente las dos cachés vigentes esperadas de `atrasos_pares_colorloto` (histórico completo y corte 100), cada una con exactamente 42 categorías y los parámetros exactos `{"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6, "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"}`; la consulta de parámetros distintos devolvió `0 rows`. El cálculo SQL independiente produjo exactamente 84 filas (42 pares × 2 escenarios): histórico completo con sorteo de referencia 209 y 209 sorteos totales; corte 100 con sorteo de referencia 100 y 100 sorteos totales -en ambos escenarios, 42 valores distintos, 0 pares sin aparición y 6 pares con atraso 0. La comparación completa `FULL JOIN` entre el cálculo SQL independiente y las dos cachés JSONB (`valor`, `ultimo_sorteo_aparicion`, `atraso`, `total_sorteos`) devolvió `0 rows` en ambos escenarios, sin ninguna discrepancia. En estos datos reales todos los 42 pares habían aparecido en ambos escenarios, por lo que no hubo ningún par con `sin_aparicion` -el usuario no pudo observar visualmente un `N/D` real en esas páginas con los datos históricos actuales; la semántica `None`/"N/D" frente a atraso `0` queda cubierta por los tests unitarios reales (`pytest`), no por una observación visual directa en este conjunto de datos.
Toda esta evidencia de Etapa AE-6 (pytest, FastAPI, PostgreSQL, HTTP real, validación visual, SQL independiente) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **ColorLoto tiene ahora seis visualizaciones validadas**; la siguiente etapa (más métricas de ColorLoto) continúa pendiente de definición. Fase 5 continúa parcial. Ninguno de estos números es un total permanente.

**Checkpoint validado (Etapa AE-7, séptima visualización web de ColorLoto -repeticiones entre sorteos, decimosexta visualización global):** `1871 passed` con `pytest` real en Windows (Python 3.14.6, `pip check` limpio, `PYTHONDONTWRITEBYTECODE=1`, `pytest -p no:cacheprovider`), FastAPI/Uvicorn en `127.0.0.1:8000` y PostgreSQL real en Docker. Tests focalizados (4 archivos: `test_calcular_y_persistir_estadistica.py`, `test_generalizacion_juegos.py`, `test_estadistica_repository.py`, `test_corte_temporal_navegacion.py`): `1055 passed`. AE-4 permanece validada con `1614 passed` reales; AE-4P con `1678 passed` reales; AE-5 con `1747 passed` reales; AE-6 con `1810 passed` reales. Reconciliación exacta: `1810 + 61 = 1871`.

Confirmado con el enrutador real de FastAPI en Windows: `/estadisticas/colorloto/repeticiones-entre-sorteos` (histórico completo y con corte `100`) respondió `200`; la ruta genérica preexistente `/estadisticas/baloto/repeticiones-entre-sorteos` respondió `200` sin ninguna interferencia, confirmando que la ruta literal nueva no rompió la ruta numérica ya validada; los tres cortes inválidos (`0`, `-1`, texto) respondieron `422`; la ruta inexistente `/estadisticas/colorloto/repeticiones-entre-sorteos-invalido` respondió `404` -resumen exacto `3×200`, `3×422`, `1×404`. El usuario abrió las páginas de histórico completo y corte 100 y declaró exactamente: "No vi errores en las páginas."

PostgreSQL real: las cuatro comprobaciones de integridad histórica (cantidad de pares, rango de número, color de otro juego, vigencia temporal) devolvieron `0 rows`. Se encontraron exactamente las dos cachés vigentes esperadas de `repeticiones_entre_sorteos_colorloto` (histórico completo y corte 100), cada una con exactamente 7 categorías y los parámetros exactos `{"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}`, sin el marcador `politica_universo_colores`; exactamente una caché vigente por escenario; la consulta de parámetros incorrectos devolvió `0 rows`. El cálculo SQL independiente, usando `SUM(LEAST(conteo_anterior, conteo_actual))` para preservar la semántica multiconjunto, produjo exactamente 14 filas (7 categorías × 2 escenarios): histórico completo con 208 transiciones válidas (0 repeticiones: 0 apariciones; 1: 8; 2: 46; 3: 83; 4: 57; 5: 12; 6: 2) y corte 100 con 99 transiciones válidas (0: 0; 1: 5; 2: 21; 3: 39; 4: 30; 5: 3; 6: 1). Conservación de masa y rango 0-6 verificados sin discrepancias. La comparación completa `FULL JOIN` entre el cálculo SQL independiente y las dos cachés JSONB devolvió `0 rows` en ambos escenarios, con apariciones, denominadores y frecuencias relativas coincidiendo con tolerancia `1e-12`, sin ninguna discrepancia.

Toda esta evidencia de Etapa AE-7 (pytest, FastAPI, PostgreSQL, HTTP real, validación visual, SQL independiente) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **ColorLoto tiene ahora siete visualizaciones validadas**; la siguiente etapa (más métricas de ColorLoto) continúa pendiente de definición. Fase 5 continúa parcial. Ninguno de estos números es un total permanente.

**Checkpoint validado (Etapa AE-8, octava visualización web de ColorLoto -distribución de números pares e impares, decimoséptima visualización global):** `1929 passed` con `pytest` real en Windows (Python 3.14.6, `pip check` limpio, `PYTHONDONTWRITEBYTECODE=1`, `pytest -p no:cacheprovider`), FastAPI/Uvicorn en `127.0.0.1:8000` y PostgreSQL real. Tests focalizados (4 archivos: `test_calcular_y_persistir_estadistica.py`, `test_generalizacion_juegos.py`, `test_estadistica_repository.py`, `test_corte_temporal_navegacion.py`): `1113 passed`. AE-4 permanece validada con `1614 passed` reales; AE-4P con `1678 passed` reales; AE-5 con `1747 passed` reales; AE-6 con `1810 passed` reales; AE-7 con `1871 passed` reales. Reconciliación exacta: `1871 + 58 = 1929`.

Confirmado con el enrutador real de FastAPI en Windows: `/estadisticas/colorloto/distribucion-pares-impares` (histórico completo y con corte `100`) respondió `200`; la ruta genérica preexistente `/estadisticas/baloto/distribucion-pares-impares` respondió `200` sin ninguna interferencia, confirmando que la ruta literal de ColorLoto no rompió la ruta numérica ya validada; los tres cortes inválidos (`0`, `-1`, texto) respondieron `422`; la ruta inexistente `/estadisticas/colorloto/distribucion-pares-impares-invalido` respondió `404` -resumen exacto `3×200`, `3×422`, `1×404`. El usuario abrió las páginas y declaró exactamente: "no vi errores en las paginas".

PostgreSQL real: las cuatro comprobaciones de integridad histórica (cantidad de pares, rango de número, color de otro juego, vigencia temporal) devolvieron `0 rows`. Se encontraron exactamente las dos cachés vigentes esperadas de `distribucion_pares_impares_colorloto` (histórico completo y corte 100), cada una con exactamente 7 categorías y los parámetros exactos `{"cantidad_numeros": 6}`; exactamente una caché vigente por escenario; la consulta de parámetros distintos devolvió `0 rows`. El cálculo SQL independiente produjo exactamente 14 filas (7 categorías × 2 escenarios): histórico completo con 209 sorteos (0 pares: 7 apariciones; 1: 34; 2: 59; 3: 71; 4: 29; 5: 9; 6: 0) y corte 100 con 100 sorteos (0: 4; 1: 15; 2: 29; 3: 31; 4: 15; 5: 6; 6: 0). Conservación de masa confirmada: completo `7+34+59+71+29+9+0=209`, corte 100 `4+15+29+31+15+6+0=100`; la consulta de rango y clasificación devolvió `0 rows` -todos los sorteos clasificados exactamente una vez dentro de 0..6. La comparación completa `FULL JOIN` entre el cálculo SQL independiente y las dos cachés JSONB devolvió `0 rows` en ambos escenarios, con tolerancia `1e-12` para `frecuencia_relativa`.

Después de detener Uvicorn, el usuario eliminó únicamente los residuos generados por las verificaciones (enviados a la Papelera de reciclaje); el resultado final no dejó directorios de caché ni archivos residuales, `storage/` quedó ausente, y `git diff --check` quedó limpio, conservando exactamente los 12 archivos esperados de AE-8 (11 modificados y el template nuevo).

Toda esta evidencia de Etapa AE-8 (pytest, FastAPI, PostgreSQL, HTTP real, validación visual, SQL independiente) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **ColorLoto tiene ahora ocho visualizaciones validadas**; la siguiente etapa (más métricas de ColorLoto) continúa pendiente de definición. Fase 5 continúa parcial. Ninguno de estos números es un total permanente.

**Checkpoint validado (Etapa AE-9, novena visualización web de ColorLoto -distribución de números bajos y altos, decimoctava visualización global):** `1994 passed` con `pytest` real en Windows (Python 3.14.6, `pip check` limpio, `PYTHONDONTWRITEBYTECODE=1`, `pytest -p no:cacheprovider`), FastAPI/Uvicorn en `127.0.0.1:8000` y PostgreSQL real. Tests focalizados (4 archivos: `test_calcular_y_persistir_estadistica.py`, `test_generalizacion_juegos.py`, `test_estadistica_repository.py`, `test_corte_temporal_navegacion.py`): `1178 passed`. AE-4 permanece validada con `1614 passed` reales; AE-4P con `1678 passed` reales; AE-5 con `1747 passed` reales; AE-6 con `1810 passed` reales; AE-7 con `1871 passed` reales; AE-8 con `1929 passed` reales. Reconciliación exacta: `1929 + 65 = 1994`.

Confirmado con el enrutador real de FastAPI en Windows: `/estadisticas/colorloto/distribucion-altos-bajos` (histórico completo y con corte `100`) respondió `200`; la ruta genérica preexistente `/estadisticas/baloto/distribucion-altos-bajos` respondió `200` sin ninguna interferencia, confirmando que la ruta literal de ColorLoto no rompió la ruta numérica ya validada; los tres cortes inválidos (`0`, `-1`, texto) respondieron `422`; la ruta inexistente `/estadisticas/colorloto/distribucion-altos-bajos-invalido` respondió `404` -resumen exacto `3×200`, `3×422`, `1×404`. El usuario abrió las páginas de histórico completo y corte 100 y declaró exactamente: "no vi errores en las paginas".

PostgreSQL real: las cuatro comprobaciones de integridad histórica (cantidad de pares, rango de número, color de otro juego, vigencia temporal) devolvieron `0 rows`. Se encontraron exactamente las dos cachés vigentes esperadas de `distribucion_altos_bajos_colorloto` (histórico completo y corte 100), cada una con exactamente 7 categorías y los parámetros exactos `{"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}`; exactamente una caché vigente por escenario; la consulta de parámetros distintos devolvió `0 rows`. El cálculo SQL independiente, contando por sorteo cuántos de los 6 números de `sorteo_color_numero.numero` son `<= 3`, produjo exactamente 14 filas (7 categorías × 2 escenarios): histórico completo con 209 sorteos (0 bajos: 3 apariciones; 1: 25; 2: 68; 3: 78; 4: 29; 5: 6; 6: 0) y corte 100 con 100 sorteos (0: 1; 1: 12; 2: 33; 3: 37; 4: 14; 5: 3; 6: 0). Conservación de masa confirmada: completo `3+25+68+78+29+6+0=209`, corte 100 `1+12+33+37+14+3+0=100`. La comparación completa `FULL JOIN` entre el cálculo SQL independiente y las dos cachés JSONB devolvió `0 rows` en ambos escenarios, con tolerancia `1e-12` para `frecuencia_relativa`.

Después de detener Uvicorn, el usuario eliminó únicamente los residuos generados por las verificaciones; el resultado final no dejó directorios de caché ni archivos residuales, y `git diff --check` quedó limpio salvo por las advertencias de `trailing whitespace` asociadas exclusivamente a los caracteres CR de CRLF -ya conocidas y no consideradas defecto-, conservando exactamente los 12 archivos esperados de AE-9 (11 modificados y el template nuevo).

Toda esta evidencia de Etapa AE-9 (pytest, FastAPI, PostgreSQL, HTTP real, validación visual, SQL independiente) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **ColorLoto tiene ahora nueve visualizaciones validadas**; la siguiente etapa (más métricas de ColorLoto) continúa pendiente de definición. Fase 5 continúa parcial. Ninguno de estos números es un total permanente.

**Checkpoint validado (Etapa AE-10, décima visualización web de ColorLoto -máximo color repetido por sorteo, decimonovena visualización global):** `2054 passed in 18.45s` con `pytest` real en Windows (Python 3.14.6, `pip check` limpio, `PYTHONDONTWRITEBYTECODE=1`, `pytest -p no:cacheprovider`), FastAPI/Uvicorn en `127.0.0.1:8000` y PostgreSQL real en Docker. Tests focalizados (4 archivos: `test_calcular_y_persistir_estadistica.py`, `test_generalizacion_juegos.py`, `test_estadistica_repository.py`, `test_corte_temporal_navegacion.py`): `1238 passed in 5.56s`. AE-4 permanece validada con `1614 passed` reales; AE-4P con `1678 passed` reales; AE-5 con `1747 passed` reales; AE-6 con `1810 passed` reales; AE-7 con `1871 passed` reales; AE-8 con `1929 passed` reales; AE-9 con `1994 passed` reales (focalizados `1178 passed in 5.15s`, suite completa `1994 passed in 10.87s`, reconciliación `1929 + 65 = 1994`). Reconciliación exacta de AE-10: `1994 + 60 = 2054` -60 tests nuevos netos, distribuidos en `+27` (`test_generalizacion_juegos.py`), `+23` (`test_calcular_y_persistir_estadistica.py`), `+10` (`test_estadistica_repository.py`) y `+0` en `test_corte_temporal_navegacion.py` (solo actualización 18→19, no cuenta como nuevo).

Reutiliza el motor `calcular_maximo_repeticion_color_por_sorteo` ya existente, sin modificarlo (hash idéntico confirmado antes/después), con exactamente 2 argumentos posicionales al motor, nunca el corte. La métrica cuenta, para cada sorteo, la mayor cantidad de balotas que compartieron un mismo color (1 a 6), usando el `Counter` ya existente en el motor. Conecta `maximo_repeticion_color_por_sorteo_colorloto` en `/estadisticas/colorloto/maximo-repeticion-color`. La ruta de AE-10 no tiene equivalente genérico -confirmado ahora con HTTP real en Windows: `/estadisticas/baloto/maximo-repeticion-color` y `/estadisticas/revancha/maximo-repeticion-color` respondieron `404` (antes de esta validación solo existía la simulación interna de resolución de rutas del turno de implementación). Identidad de caché con **una sola clave** (`cantidad_numeros`), decisión M1 confirmada con evidencia directa en la auditoría y su adenda correctiva: el motor sí lee y compara identidades de color mediante `Counter`, pero nunca construye su universo de categorías desde `colores_vigentes` -las categorías son siempre 1..6, derivadas únicamente de `cantidad_balotas`; el resultado nunca muestra el código del color que alcanzó el máximo, solo la multiplicidad; y una mutación de paleta sobre un color nunca observado no puede alterar el resultado matemático de ningún sorteo histórico ya calculado, ya que el motor opera exclusivamente sobre el histórico de sorteos ya registrado. La invalidación conservadora y agnóstica de `GestionarPaletaColores` (sin ningún cambio de código) sigue cubriendo esta receta automáticamente. `total_sorteos` del campo serializado es la cantidad real de sorteos analizados (nunca "transiciones"). Las seis categorías (1..6, sin la categoría 0) siempre existen completas; `apariciones=0` es un cero real.

Confirmado con el enrutador real de FastAPI en Windows: `/estadisticas/colorloto/maximo-repeticion-color` (histórico completo y con corte `100`) respondió `200`; los tres cortes inválidos (`0`, `-1`, texto) respondieron `422`; `/estadisticas/baloto/maximo-repeticion-color`, `/estadisticas/revancha/maximo-repeticion-color` y `/estadisticas/colorloto/maximo-repeticion-color-invalido` respondieron `404` -resumen exacto `2×200`, `3×422`, `3×404`. El usuario abrió las páginas y declaró exactamente: "no vi errores en las paginas".

PostgreSQL real: las cuatro comprobaciones de integridad histórica (cantidad de pares, rango de número, color de otro juego, vigencia temporal) devolvieron `0 rows`. Se encontraron exactamente las dos cachés vigentes esperadas de `maximo_repeticion_color_por_sorteo_colorloto` (histórico completo y corte 100), cada una con exactamente 6 categorías (1..6, sin la categoría 0) y los parámetros exactos `{"cantidad_numeros": 6}`; exactamente una caché vigente por escenario; la consulta de parámetros distintos devolvió `0 rows`. El cálculo SQL independiente, agrupando por sorteo y color y tomando el máximo `COUNT(*)` de color por sorteo, produjo exactamente 12 filas (6 categorías × 2 escenarios): histórico completo con 209 sorteos (1: 2 apariciones; 2: 136; 3: 70; 4: 1; 5: 0; 6: 0) y corte 100 con 100 sorteos (1: 1; 2: 64; 3: 35; 4: 0; 5: 0; 6: 0). Conservación de masa confirmada: completo `2+136+70+1+0+0=209`, corte 100 `1+64+35+0+0+0=100`; la consulta de rango y clasificación devolvió `0 rows`. La comparación completa `FULL JOIN` entre el cálculo SQL independiente y las dos cachés JSONB devolvió `0 rows` en ambos escenarios, con tolerancia `1e-12` para `frecuencia_relativa`.

El docstring desactualizado de `POLITICA_UNIVERSO_COLORES_ACTUAL` (que mencionaba "dos recetas" cuando en realidad ya eran cuatro -hallazgo confirmado en la adenda de la auditoría) fue corregido de forma general, sin fijar ningún número de recetas que pudiera volver a desactualizarse. `git diff --check` del usuario quedó limpio, conservando exactamente los 12 archivos esperados de AE-10 (11 modificados y el template nuevo). El único residuo encontrado antes de limpiar fue `backend/storage/logs/sync.log`, generado durante la ejecución; el usuario lo eliminó de forma recuperable, quedando `DirectoriosCache=0`, `ArchivosResiduales=0`, `ArchivosRuntimeStorage=0`. ColorLoto pasa de nueve a diez visualizaciones validadas, sub-navegación ampliada preservando el corte; navegación numérica (9/9/8) intacta -esta es la **decimonovena ruta/Query/canvas global**. Motores (incluido `distribuciones.py`, el propio motor reutilizado, permaneció sin cambios respecto de `ae9-validado`), `GestionarPaletaColores`, los casos de uso de registro/edición/eliminación de sorteos, `Color`/`ColorRepository`, ambos repositorios de estadística, `main.py`, 5 migraciones, `requirements.txt` y Chart.js confirmados con hash idéntico.

Toda esta evidencia de Etapa AE-10 (pytest, FastAPI, PostgreSQL, HTTP real, validación visual, SQL independiente) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **ColorLoto tiene ahora diez visualizaciones validadas**; la siguiente etapa (más métricas de ColorLoto) continúa pendiente de definición. Fase 5 continúa parcial. Ninguno de estos números es un total permanente.

**Checkpoint validado (Etapa AE-11, undécima visualización web de ColorLoto -distribución de pares consecutivos, vigésima visualización global):** `2115 passed in 6.92s` con `pytest` real en Windows (Python 3.14.6, `pip check` limpio -"No broken requirements found.", `PYTHONDONTWRITEBYTECODE=1`, `pytest -p no:cacheprovider`), FastAPI/Uvicorn en `127.0.0.1:8000` y PostgreSQL real en Docker. Tests focalizados (4 archivos: `test_calcular_y_persistir_estadistica.py`, `test_generalizacion_juegos.py`, `test_estadistica_repository.py`, `test_corte_temporal_navegacion.py`): `1299 passed in 2.82s`. AE-10 permanece validada con `2054 passed in 18.45s` (focalizados `1238 passed in 5.56s`, reconciliación `1994 + 60 = 2054`). Reconciliación exacta de AE-11: `2054 + 61 = 2115`. La primera corrida real detectó un falso positivo en `test_receta_usa_rango_real_colorloto_constante_para_validacion_y_motor`: la aserción textual sobre `inspect.getsource` coincidía con una cadena presente únicamente en el docstring explicativo de la receta, nunca en código ejecutable -corregido reemplazando la comprobación textual por una inspección AST real de los accesos a `parametros[...]` dentro del cuerpo de la función; la implementación funcional (receta y motor) era correcta desde el inicio, el defecto era exclusivamente del test. Tras la corrección, la prueba individual pasó `1 passed in 0.49s` y la suite completa quedó limpia.

Reutiliza el motor `calcular_distribucion_pares_consecutivos_colorloto` ya existente, sin modificar (hash idéntico antes/después, confirmado byte a byte), con exactamente 4 argumentos posicionales al motor (`resultados, rango_min, rango_max, cantidad_numeros`), nunca el corte. Conecta `distribucion_pares_consecutivos_colorloto` en `/estadisticas/colorloto/distribucion-pares-consecutivos`, registrada antes de la ruta genérica homónima preexistente -sexta colisión real de sufijo (grupo pasa de cinco a seis rutas), confirmada ahora con HTTP real en Windows. Identidad de caché de **una sola clave** (`cantidad_numeros`), decisión M1: el motor exige `rango_min`/`rango_max` como argumentos posicionales, pero únicamente para su validación interna -confirmado con evidencia directa; `_RANGO_REAL_COLORLOTO` alimenta ambas llamadas, ninguno de los dos límites entra en `parametros_metrica`. Seis categorías fijas `0..5` (a diferencia de AE-10, esta métrica sí incluye la categoría `0`). El motor deduplica los números de cada sorteo antes de contar rachas, comportamiento ya existente sin modificar.

Confirmado con el enrutador real de FastAPI en Windows (`TcpTestSucceeded=True`; un primer intento sin servidor iniciado produjo estados PowerShell `0` que solo significaban ausencia de conexión, no respuestas HTTP, y fueron descartados): `/estadisticas/colorloto/distribucion-pares-consecutivos` (histórico completo y con corte `100`) respondió `200`; las tres rutas genéricas reales -`/estadisticas/baloto/distribucion-pares-consecutivos`, `/estadisticas/baloto-revancha/distribucion-pares-consecutivos`, `/estadisticas/miloto/distribucion-pares-consecutivos`- también respondieron `200`, sin ninguna interferencia de la ruta literal nueva; los tres cortes inválidos (`0`, `-1`, texto) respondieron `422`; `/estadisticas/colorloto/distribucion-pares-consecutivos-invalido` respondió `404` -resumen exacto `5×200`, `3×422`, `1×404`. El usuario abrió las páginas y declaró exactamente: "no vi errores en las paginas".

PostgreSQL real: las cuatro comprobaciones de integridad histórica (cantidad de pares, rango de número, color de otro juego, vigencia temporal -una de las consultas se pegó dos veces por accidente, sin modificar datos ni agregar una quinta comprobación) devolvieron `0 rows`. Se encontraron exactamente las dos cachés vigentes esperadas de `distribucion_pares_consecutivos_colorloto` (histórico completo y corte 100), cada una con exactamente 6 categorías (`0..5`) y los parámetros exactos `{"cantidad_numeros": 6}`; exactamente una caché vigente por escenario; la consulta de parámetros distintos devolvió `0 rows`. El cálculo SQL independiente, deduplicando primero los números por sorteo y contando cada pareja distinta `(n, n+1)`, produjo exactamente 12 filas (6 categorías × 2 escenarios): histórico completo con 209 sorteos (0: 9; 1: 42; 2: 84; 3: 53; 4: 16; 5: 5) y corte 100 con 100 sorteos (0: 4; 1: 21; 2: 41; 3: 27; 4: 5; 5: 2). Conservación de masa confirmada: completo `9+42+84+53+16+5=209`, corte 100 `4+21+41+27+5+2=100`; la consulta de conservación con las seis categorías y rango `0..5` devolvió `0 rows`. La comparación completa `FULL JOIN` entre el cálculo SQL independiente y las dos cachés JSONB devolvió `0 rows` en ambos escenarios, con tolerancia `1e-12`.

`git diff --check` del usuario quedó en exit code `0` -las advertencias informativas `LF will be replaced by CRLF the next time Git touches it` para `ARCHITECTURE.md` y `test_generalizacion_juegos.py` no cambiaron el resultado ni requirieron normalizar el árbol. Conservando exactamente los 12 archivos esperados de AE-11 (11 modificados y el template nuevo). El único residuo encontrado antes de limpiar fue `backend/storage/logs/sync.log`, generado durante la ejecución; el usuario lo eliminó de forma recuperable, quedando `DirectoriosCache=0`, `ArchivosResiduales=0`, `ArchivosRuntimeStorage=0`. Conteos estructurales confirmados: `239` archivos totales, `174` Python, `20` recetas, `20` rutas, `20` Query, `20` canvas, `11` pestañas de ColorLoto; navegación numérica (9/9/8) intacta. `consecutivos.py` y el resto de archivos protegidos (motor, Chart.js, migraciones, repositorios, casos de uso de sorteos) confirmados con hash idéntico.

Toda esta evidencia de Etapa AE-11 (pytest, FastAPI, PostgreSQL, HTTP real, validación visual, SQL independiente) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **ColorLoto tiene ahora once visualizaciones validadas**; la siguiente etapa (más métricas de ColorLoto) continúa pendiente de definición. Fase 5 continúa parcial. Ninguno de estos números es un total permanente.

**Checkpoint validado (Etapa AE-12, duodécima visualización web de ColorLoto -distribución de racha máxima, vigesimoprimera visualización global):** implementada conforme al contrato exacto autorizado, heredado de la decisión A de la auditoría de AE-12 -candidata `calcular_distribucion_racha_maxima_colorloto`, motor reutilizado sin ninguna modificación (hash de `consecutivos.py` idéntico antes/después, confirmado byte a byte). Conecta `distribucion_racha_maxima_colorloto` en `/estadisticas/colorloto/distribucion-racha-maxima`, registrada en el bloque literal de ColorLoto **antes** de la ruta genérica homónima preexistente `/estadisticas/{juego_slug}/distribucion-racha-maxima` -séptima colisión real de sufijo del mismo tipo ya corregida en AE-1/AE-4/AE-7/AE-8/AE-9/AE-11 (grupo de colisión pasa de seis a siete rutas). Exactamente cuatro argumentos posicionales al motor (`resultados, rango_min, rango_max, cantidad_numeros`), `hasta_numero_sorteo` nunca pasado. Identidad de caché de **una sola clave** (`cantidad_numeros`), decisión M1: el motor exige `rango_min`/`rango_max` como argumentos posicionales, pero únicamente para su validación interna -confirmado por lectura directa del cuerpo del motor y por caracterización real- que la longitud de la racha máxima, las categorías y el denominador nunca dependen de esos límites; por eso `_RANGO_REAL_COLORLOTO` (la constante ya usada por AE-8/AE-10/AE-11, desempaquetada como `rango_min, rango_max = _RANGO_REAL_COLORLOTO`, nunca indexada) alimenta tanto la validación de integridad como la llamada al motor, sin leer `parametros["rango_min"]`/`parametros["rango_max"]`. Seis categorías fijas `1..6`, sin la categoría `0` (a diferencia de AE-11: un sorteo con al menos un número siempre tiene una racha de longitud mínima 1, el propio motor filtra la categoría "0" antes de devolver el resultado). El motor deduplica los números de cada sorteo antes de buscar rachas -comportamiento ya existente en el motor puro desde antes de esta etapa, no modificado ni reimplementado aquí; un número repetido con colores distintos nunca alarga artificialmente una racha. VM `distribucion_racha_maxima_colorloto_a_vm` reutiliza el helper `_etiqueta_racha_maxima` ya existente (Etapa AB, numérica) sin duplicar su lógica de singular/plural, tomando prestados los nombres de clave (`longitud_racha`, `racha_mas_frecuente`) de la VM numérica homónima para máxima coherencia entre ambas versiones de la misma métrica. Sin marcador `POLITICA_UNIVERSO_COLORES_ACTUAL` -el motor ignora el color por completo.

`2176 passed in 14.96s` con `pytest` real en Windows (Python 3.14.6, `pip check` limpio -"No broken requirements found.", `PYTHONDONTWRITEBYTECODE=1`). Tests focalizados (4 archivos): `1360 passed in 7.87s`. Reconciliación: `2115 + 61 = 2176` en la suite completa; focalizados `1299 + 61 = 1360`. La primera prueba puntual del test AST que verifica que la receta no lee `rango_min` ni `rango_max` desde `parametros` pasó `1 passed in 1.60s`. Las primeras corridas reales -focalizados `1 failed, 1359 passed in 8.99s`; suite completa `1 failed, 2175 passed in 29.64s`- encontraron exactamente un fallo: `TestColorLotoNavegacionCuatroMetricas.test_partial_tiene_exactamente_once_items_de_navegacion` con `assert 12 == 11`. La implementación funcional era correcta desde el inicio -la navegación de ColorLoto ya tenía las 12 pestañas correctas-; el defecto era exclusivamente un test heredado de una etapa anterior que conservaba el nombre `once` y la expectativa `== 11` sin haberse actualizado. Corrección exclusiva de esa prueba (nombre `test_partial_tiene_exactamente_doce_items_de_navegacion`, aserción `== 12`), sin tocar navegación, código funcional, template, receta, VM, caché ni motor. Prueba puntual corregida: `1 passed in 1.38s`. `git diff --check` de la corrección: exit code `0`.

Conecta `distribucion_racha_maxima_colorloto` -confirmado con el enrutador real: `5×200` (`/estadisticas/colorloto/distribucion-racha-maxima` histórico completo y con corte 100, `/estadisticas/baloto/distribucion-racha-maxima`, `/estadisticas/baloto-revancha/distribucion-racha-maxima`, `/estadisticas/miloto/distribucion-racha-maxima`), `3×422` (cortes `0`, `-1`, texto), `1×404` (`/estadisticas/colorloto/distribucion-racha-maxima-invalido`); conexión TCP confirmada (`TcpTestSucceeded: True`) sobre `127.0.0.1:8000`; el usuario reportó "no vi errores en las paginas". PostgreSQL real: las cuatro comprobaciones de integridad (balotas distintas de seis, números fuera de `1..7`, colores de otro juego, colores fuera de vigencia) devolvieron `0 rows`; dos cachés vigentes (histórico completo y corte 100) con 6 categorías cada una y parámetros exactos `{"cantidad_numeros": 6}` -agrupación confirmó una caché vigente por corte (`NULL → 1`, `100 → 1`); búsqueda de parámetros distintos devolvió `0 rows`. Cálculo SQL independiente (deduplicando números y formando islas consecutivas mediante `numero - ROW_NUMBER()`) produjo la distribución exacta de 12 filas: histórico completo con 209 sorteos (1: 9; 2: 66; 3: 85; 4: 32; 5: 12; 6: 5) y corte 100 con 100 sorteos (1: 4; 2: 30; 3: 44; 4: 16; 5: 4; 6: 2); conservación de masa confirmada (`9+66+85+32+12+5=209`, `4+30+44+16+4+2=100`); comparación `FULL JOIN` SQL vs JSONB: `0 rows` con tolerancia `1e-12`. Limpieza final: únicos residuos encontrados `backend/.pytest_cache` y `backend/storage/logs/sync.log`, ambos eliminados de forma recuperable; verificación final `DirectoriosCache=0`, `ArchivosResiduales=0`, `ArchivosRuntimeStorage=0`, `git diff --check` exit code `0`. Árbol con exactamente los 12 archivos esperados de AE-12; `consecutivos.py` y el resto de archivos protegidos con hash idéntico. Toda esta evidencia fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **ColorLoto tiene ahora doce visualizaciones validadas**; navegación numérica (9/9/8) intacta; la siguiente etapa continúa pendiente de definición. Fase 5 continúa parcial. Ninguno de estos números es un total permanente.

**Checkpoint validado (Etapa AE-13, decimotercera visualización web de ColorLoto -distribución de tríos consecutivos, vigesimosegunda visualización global):** implementada sobre la fuente `ae12-validado` conforme al contrato exacto autorizado, heredado de la decisión A de la auditoría de AE-13 -candidata `calcular_distribucion_trios_consecutivos_colorloto`, motor reutilizado sin ninguna modificación (hash de `consecutivos.py` idéntico antes/después, confirmado byte a byte). Conecta `distribucion_trios_consecutivos_colorloto` en `/estadisticas/colorloto/distribucion-trios-consecutivos`, registrada en el bloque literal de ColorLoto. A DIFERENCIA de las siete colisiones reales ya corregidas en AE-1/AE-4/AE-7/AE-8/AE-9/AE-11/AE-12, esta ruta NO colisiona con ninguna ruta genérica -confirmado por la auditoría de AE-13 (simulación con el motor real de `starlette.routing.Route`) que `/estadisticas/{juego_slug}/distribucion-trios-consecutivos` no existe entre las rutas registradas, ni siquiera para el motor numérico equivalente (nunca conectado a `_CATALOGO`); mismo caso que `maximo-repeticion-color` (Etapa AE-10). El grupo de rutas ColorLoto sin colisión pasa de cinco a seis; el grupo con colisión permanece en siete. Exactamente cuatro argumentos posicionales al motor (`resultados, rango_min, rango_max, cantidad_numeros`), `hasta_numero_sorteo` nunca pasado, desempaquetado como `rango_min, rango_max = _RANGO_REAL_COLORLOTO`, nunca indexado. Identidad de caché de **una sola clave** (`cantidad_numeros`), decisión M1: el motor exige `rango_min`/`rango_max` como argumentos posicionales, pero únicamente para su validación interna -confirmado por lectura directa del cuerpo del motor y por caracterización real- que la cantidad de tríos consecutivos, las categorías y el denominador nunca dependen de esos límites; nunca se lee `parametros["rango_min"]`/`parametros["rango_max"]`. Cinco categorías fijas `0..4` (a diferencia de AE-12: esta métrica SÍ incluye la categoría `0`, mismo criterio que AE-11: un sorteo sin ningún trío consecutivo es un valor real y posible). Un trío consecutivo son tres números adyacentes (n, n+1, n+2); los tríos superpuestos se cuentan por separado -una racha de longitud 4 aporta 2 tríos. El motor deduplica los números de cada sorteo antes de contar -comportamiento ya existente en el motor puro desde antes de esta etapa, no modificado ni reimplementado aquí. VM `distribucion_trios_consecutivos_colorloto_a_vm` con clave `cantidad_trios_consecutivos` (nunca `longitud_racha` ni `cantidad_pares_consecutivos`, para no confundir las tres semánticas distintas ya presentes en ColorLoto). Se agregó el helper `_etiqueta_trios_consecutivos` -la auditoría de AE-13 confirmó que no existía precedente, ni siquiera numérico- con las etiquetas "Sin tríos consecutivos" / "1 trío consecutivo" / "N tríos consecutivos", siguiendo el estilo real de `_etiqueta_pares_consecutivos` y `_etiqueta_racha_maxima`. Sin marcador `POLITICA_UNIVERSO_COLORES_ACTUAL` -el motor ignora el color por completo.

`2243 passed in 9.26s` con `pytest` real en Windows (Python 3.14.6, `pip check` limpio -"No broken requirements found."). Tests focalizados (4 archivos): `1427 passed in 5.26s`. Reconciliación: `2176 + 67 = 2243` en la suite completa; focalizados `1360 + 67 = 1427`, distribuidos en `+27`/`+30`/`+10`/`+0`. Las dos pruebas críticas iniciales -inspección AST de la receta de AE-13 y actualización heredada de navegación de 12 a 13 pestañas- pasaron `2 passed in 2.48s`. Las primeras corridas reales -focalizados `1 failed, 1426 passed in 7.60s`; suite completa `1 failed, 2242 passed in 19.87s`- encontraron exactamente un fallo: `TestRecetaDistribucionRachaMaximaColorloto.test_receta_registrada_exactamente_una_vez`, `TypeError: list.count() takes exactly one argument (2 given)`. La causa fue una sustitución textual demasiado amplia aplicada durante la implementación provisional, que además de extender correctamente las tuplas `recetas_colorloto` alteró accidentalmente esta línea heredada de AE-12, dejándola con dos argumentos en `list.count()` -inválido en Python. La implementación funcional (receta, motor, ruta, VM, caché) era correcta desde el inicio; el defecto era exclusivamente esa línea de test heredado. Corrección exclusiva de esa línea, restaurada a `list(_CATALOGO.keys()).count("distribucion_racha_maxima_colorloto") == 1`, sin tocar ninguna otra línea funcional o de test. Después de corregirla: `2 passed in 0.95s`, `1427 passed in 5.26s`, `2243 passed in 9.26s`. `git diff --check` final: exit code `0`.

Confirmado con el enrutador real (`TcpTestSucceeded: True` sobre `127.0.0.1:8000`): `200` en `/estadisticas/colorloto/distribucion-trios-consecutivos` (histórico completo y con corte 100); `404` en `/estadisticas/baloto/distribucion-trios-consecutivos`, `/estadisticas/baloto-revancha/distribucion-trios-consecutivos` y `/estadisticas/miloto/distribucion-trios-consecutivos` -confirmando en producción real la ausencia de colisión ya prevista: ningún handler genérico intercepta estas URLs; `422` en los tres cortes inválidos (`0`, `-1`, texto); `404` en el sufijo `-invalido` -resumen exacto `2×200`, `3×422`, `4×404`. El usuario declaró literalmente: "no vi errores en la pagina". PostgreSQL real: las cuatro comprobaciones de integridad (balotas distintas de seis, números fuera de `1..7`, colores de otro juego, colores fuera de vigencia) devolvieron `0 rows`. Se confirmaron las dos cachés vigentes esperadas (histórico completo y corte 100), cada una con 5 categorías y parámetros exactos `{"cantidad_numeros": 6}` -agrupación confirmó una caché vigente por escenario (histórico completo → 1, corte 100 → 1); búsqueda de parámetros distintos devolvió `0 rows`. El cálculo SQL independiente, deduplicando números antes de contar tríos superpuestos, produjo la distribución exacta de 10 filas: histórico completo con 209 sorteos (0: 75; 1: 83; 2: 34; 3: 12; 4: 5) y corte 100 con 100 sorteos (0: 34; 1: 44; 2: 16; 3: 4; 4: 2); conservación de masa confirmada (`75+83+34+12+5=209`, `34+44+16+4+2=100`); la verificación conjunta de conservación, cinco categorías, mínimo `0` y máximo `4` devolvió `0 rows`. La comparación `FULL JOIN` entre el cálculo SQL independiente y ambas cachés JSONB (corte, categoría, apariciones, total de sorteos, frecuencia relativa) devolvió `0 rows` con tolerancia `1e-12`.

Limpieza final: único residuo encontrado `backend/storage/logs/sync.log`, eliminado de forma recuperable; verificación final `DirectoriosCache=0`, `ArchivosResiduales=0`, `ArchivosRuntimeStorage=0`, `git diff --check` exit code `0`. Árbol con exactamente los 12 archivos esperados de AE-13; `consecutivos.py` y el resto de archivos protegidos con hash idéntico. Toda esta evidencia (pytest, HTTP, PostgreSQL, revisión visual) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **ColorLoto tiene ahora trece visualizaciones validadas**; navegación numérica (9/9/8) intacta; la siguiente etapa (AE-14) continúa pendiente de definición. Fase 5 continúa parcial. Ninguno de estos números es un total permanente.

**Checkpoint validado (Etapa AE-14, decimocuarta visualización web de ColorLoto -coocurrencia de pares, vigesimotercera visualización global):** implementada sobre la fuente `ae13-validado` conforme al contrato exacto autorizado, con la Decisión A corregida de la auditoría de AE-14 -candidata exacta `calcular_coocurrencia_pares_colorloto` (la auditoría había mencionado inicialmente por error de redacción `calcular_distribucion_conteo_color` en su sección de decisión; esa función NO fue implementada en esta etapa), motor reutilizado sin ninguna modificación (hash de `consecutivos.py` y de `coocurrencia.py` idénticos antes/después, confirmado byte a byte). Conecta `coocurrencia_pares_colorloto` en `/estadisticas/colorloto/coocurrencia-pares`, registrada en el bloque literal de ColorLoto. Mismo caso que `maximo-repeticion-color` (AE-10) y `distribucion-trios-consecutivos` (AE-13): esta ruta NO colisiona con ninguna ruta genérica -confirmado ahora con HTTP real, no solo simulación: `4×404` (`/estadisticas/baloto/coocurrencia-pares`, `/estadisticas/baloto-revancha/coocurrencia-pares`, `/estadisticas/miloto/coocurrencia-pares`, sufijo `-invalido`), ninguno interceptado por ningún handler genérico. El grupo de rutas ColorLoto sin colisión pasa de seis a **siete**; el grupo con colisión permanece en siete.

A DIFERENCIA de las trece visualizaciones anteriores (todas distribuciones categóricas por sorteo), esta es una **tabla de asociaciones** agregada sobre todo el histórico analizado -sin `<canvas>`, sin Chart.js, confirmado también visualmente por el usuario. El motor reporta únicamente pares observados al menos una vez; para ColorLoto (7 números posibles) el máximo teórico es C(7,2)=21 pares -confirmado con PostgreSQL real que ambos escenarios (histórico completo y corte 100) alcanzan exactamente ese máximo, 21 pares observados cada uno, manejable sin paginación. Conteo estructural separado explícitamente: **23 templates/páginas estadísticos, pero 22 con canvas** -la página tabular de AE-14 es la única excepción, sin mantener una igualdad artificial entre ambas cifras.

`2319 passed in 6.91s` con `pytest` real en Windows (Python 3.14.6, `pip check` limpio -"No broken requirements found."). Cinco pruebas críticas iniciales: `5 passed in 1.98s`. La primera corrida focalizada -`1 failed, 1502 passed in 3.79s`- y la primera suite completa -`1 failed, 2318 passed in 17.62s`- encontraron exactamente un fallo: `TestRecetaDistribucionTriosConsecutivosColorloto.test_receta_registrada_exactamente_una_vez`, `TypeError: list.count() takes exactly one argument (2 given)`. La causa fue -igual que en el cierre de AE-13- una sustitución textual demasiado amplia aplicada durante la implementación provisional al extender estructuras heredadas con `coocurrencia_pares_colorloto`, que alteró accidentalmente esta línea heredada de AE-13 dejándola con dos argumentos en `list.count()`. La implementación funcional (receta, motor, ruta, VM, template, caché) era correcta desde el inicio; el defecto era exclusivamente esa línea de test heredado. El usuario confirmó exactamente una coincidencia de la línea incorrecta, la sustituyó exclusivamente por la versión con un solo argumento, y verificó "Count inválidos restantes: 0" en todo el proyecto. Después de corregir: `2 passed in 0.67s`, `1503 passed in 4.55s`, `2319 passed in 6.91s`; `git diff --check`: exit code `0`. Reconciliaciones: `2243 + 76 = 2319` en la suite completa, `1427 + 76 = 1503` en focalizados, distribuidos en `+36` (`test_calcular_y_persistir_estadistica.py`), `+30` (`test_generalizacion_juegos.py`), `+10` (`test_estadistica_repository.py`) y `+0` en `test_corte_temporal_navegacion.py`.

Confirmado con el enrutador real (`TcpTestSucceeded: True` sobre `127.0.0.1:8000`): `2×200` (`/estadisticas/colorloto/coocurrencia-pares` histórico completo y con `?hasta_numero_sorteo=100`), `4×404` (los tres juegos genéricos para este sufijo más el sufijo inválido, confirmando en producción real la ausencia de colisión), `3×422` (cortes `0`, `-1`, texto). El usuario abrió ambas páginas y declaró literalmente: "no vi errores en las paginas".

PostgreSQL real: las cuatro comprobaciones de integridad (balotas distintas de seis, números fuera de `1..7`, colores de otro juego, colores fuera de vigencia) devolvieron `0 rows`. Se confirmaron exactamente dos cachés vigentes -histórico completo (corte `NULL`, parámetros `{}`, 21 pares observados) y corte 100 (corte `100`, parámetros `{}`, 21 pares observados)-, una caché vigente por escenario, búsqueda de parámetros distintos de `{}` en `0 rows`, y estructura JSONB inválida en `0 rows`; `elementos` confirmado como array de exactamente dos números, `frecuencia_esperada` y `lift` confirmados `null` en ambas cachés, soporte siempre mayor que cero y menor o igual al total de sorteos.

El cálculo SQL independiente (deduplicando números por sorteo, generando pares con `numero_2 > numero_1`) produjo 42 filas exactas (21 por escenario). **Histórico completo, 209 sorteos** -soportes exactos: `(3,5): 92`, `(2,5): 87`, `(3,7): 87`, `(2,3): 85`, `(3,4): 85`, `(1,3): 83`, `(5,7): 83`, `(3,6): 82`, `(2,6): 77`, `(2,7): 77`, `(1,5): 76`, `(4,5): 76`, `(1,4): 75`, `(5,6): 75`, `(2,4): 74`, `(1,7): 73`, `(4,7): 73`, `(4,6): 72`, `(6,7): 72`, `(1,6): 66`, `(1,2): 65` -par con mayor soporte `(3,5)`, 92 apariciones, frecuencia relativa exacta `0.44019138755980861244` (**esto es una cifra descriptiva de lo ya ocurrido, no una recomendación ni predicción**). **Corte 100, 100 sorteos** -soportes exactos: `(3,5): 45`, `(2,5): 44`, `(5,7): 44`, `(5,6): 41`, `(3,7): 40`, `(2,3): 39`, `(2,6): 38`, `(3,6): 38`, `(1,5): 37`, `(2,4): 37`, `(3,4): 37`, `(2,7): 35`, `(4,5): 34`, `(4,7): 33`, `(6,7): 33`, `(1,3): 32`, `(1,7): 31`, `(4,6): 31`, `(1,2): 30`, `(1,4): 29`, `(1,6): 28` -par con mayor soporte `(3,5)`, 45 apariciones, frecuencia relativa exacta `0.45000000000000000000`.

La comprobación conjunta de invariantes (21 pares observados por escenario, 21 pares distintos, números dentro de `1..7`, soporte mayor que cero, soporte menor o igual al total de sorteos) devolvió `0 rows`. La comparación `FULL JOIN` entre el cálculo SQL independiente y ambas cachés JSONB (corte, primer número, segundo número, soporte, total de sorteos, frecuencia relativa) devolvió `0 rows` con tolerancia `1e-12`. A diferencia de las distribuciones categóricas por sorteo de las trece etapas anteriores, aquí no aplica conservación de masa igual al número de sorteos: cada sorteo aporta a varios pares simultáneamente, y los números se deduplican antes de formar dichos pares.

Limpieza final: único residuo encontrado `backend/storage/logs/sync.log` (28986 bytes), eliminado de forma recuperable; verificación final `DirectoriosCache=0`, `ArchivosResiduales=0`, `ArchivosRuntimeStorage=0`, `git diff --check` exit code `0`. Árbol con exactamente los 12 archivos esperados de AE-14; `consecutivos.py` y `coocurrencia.py` con hash idéntico. Toda esta evidencia (pytest, HTTP, PostgreSQL, revisión visual) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **ColorLoto tiene ahora catorce visualizaciones validadas**; navegación numérica (9/9/8) intacta; la siguiente etapa (AE-15) continúa pendiente de definición. Fase 5 continúa parcial. Ninguno de estos números es un total permanente.

**Checkpoint validado (Etapa AE-15, decimoquinta visualización web de ColorLoto -coocurrencia de tríos, vigesimocuarta visualización global):** implementada sobre la fuente `ae14-validado` conforme al contrato exacto autorizado, reutilizando `calcular_coocurrencia_trios_colorloto` sin ninguna modificación (hash de `consecutivos.py` y de `coocurrencia.py` idénticos antes/después, confirmado byte a byte). Conecta `coocurrencia_trios_colorloto` en `/estadisticas/colorloto/coocurrencia-trios`, registrada en el bloque literal de ColorLoto, mismo patrón exacto que `coocurrencia-pares` (AE-14). Sin ninguna ruta genérica equivalente. El grupo de rutas ColorLoto sin colisión pasa de siete a **ocho**; el grupo con colisión permanece en siete.

Igual que AE-14, esta es una **tabla de asociaciones** (sin `<canvas>`, sin Chart.js, sin CDN, sin `|safe`). El motor reporta únicamente tríos observados al menos una vez; para ColorLoto (7 números posibles) el máximo teórico es C(7,3)=35 tríos -sin paginación, sin top-N, sin truncamiento. Conteo estructural: **24 templates/páginas estadísticos, 22 con canvas** (sin cambio respecto a AE-14, la excepción tabular no crece con esta etapa).

`2379 passed in 17.16s` con `pytest` real en Windows (Python 3.14.6, `pip check` limpio -"No broken requirements found."). Cinco pruebas críticas iniciales: `5 passed in 1.47s`. Tests focalizados (4 archivos): `1563 passed in 5.03s`. No hubo fallos iniciales ni correcciones funcionales posteriores. Reconciliación: `2319 + 60 = 2379` en la suite completa, `1503 + 60 = 1563` en los cuatro archivos focalizados, distribuidos en `+20` (`test_calcular_y_persistir_estadistica.py`), `+28` (`test_generalizacion_juegos.py`), `+12` (`test_estadistica_repository.py`) y `+0` en `test_corte_temporal_navegacion.py`.

Confirmado con el enrutador real (`TcpTestSucceeded: True`): `2×200` (`/estadisticas/colorloto/coocurrencia-trios` histórico completo y con `?hasta_numero_sorteo=100`), `4×404` (Baloto, Baloto Revancha, MiLoto y sufijo inválido, confirmando en producción real la ausencia de colisión), `3×422` (cortes `0`, `-1`, texto). El usuario abrió ambas páginas y declaró literalmente: "no veo errores en las paginas".

PostgreSQL real: las cuatro comprobaciones de integridad (balotas distintas de seis, números fuera de `1..7`, colores de otro juego, colores fuera de vigencia) devolvieron `0 rows`. Se confirmaron exactamente dos cachés vigentes -histórico completo (corte `NULL`, parámetros `{}`, 35 tríos observados) y corte 100 (corte `100`, parámetros `{}`, 35 tríos observados)-, una caché vigente por escenario, búsqueda de parámetros distintos de `{}` en `0 rows`, y estructura JSONB inválida en `0 rows`; `elementos` confirmado como array de exactamente tres enteros en orden estrictamente ascendente, `frecuencia_esperada` y `lift` confirmados `null` en ambas cachés, soporte siempre mayor que cero y menor o igual al total de sorteos.

El cálculo SQL independiente (deduplicando números por sorteo, generando tríos con `numero_2 > numero_1` y `numero_3 > numero_2`) produjo 70 filas exactas (35 por escenario). **Histórico completo, 209 sorteos** -trío con mayor soporte `(3,5,7)`, 54 apariciones, frecuencia relativa exacta `0.25837320574162679426` (**esto es una cifra descriptiva de lo ya ocurrido, no una recomendación ni predicción**). **Corte 100, 100 sorteos** -trío con mayor soporte `(3,5,7)`, 27 apariciones, frecuencia relativa exacta `0.27000000000000000000`.

La comprobación conjunta de invariantes (35 tríos observados por escenario, 35 tríos distintos, números dentro de `1..7`, soporte mayor que cero, soporte menor o igual al total de sorteos) devolvió `0 rows`. La comparación `FULL JOIN` entre el cálculo SQL independiente y ambas cachés JSONB (corte, primer número, segundo número, tercer número, soporte, total de sorteos, frecuencia relativa) devolvió `0 rows` con tolerancia `1e-12`. Igual que en AE-14, aquí no aplica conservación de masa igual al número de sorteos: cada sorteo aporta a varios tríos simultáneamente, y los números se deduplican antes de formar dichos tríos.

Limpieza final: único residuo encontrado `backend/storage/logs/sync.log` (14493 bytes), bloqueado porque Uvicorn seguía en ejecución; identificado y detenido exclusivamente el árbol de procesos Uvicorn del puerto 8000 (cero listeners tras detenerlo), archivo eliminado de forma recuperable; verificación final `DirectoriosCache=0`, `ArchivosResiduales=0`, `ArchivosRuntimeStorage=0`, `git diff --check` exit code `0`. Árbol con exactamente los 12 archivos esperados de AE-15; `consecutivos.py` y `coocurrencia.py` con hash idéntico. Toda esta evidencia (pytest, HTTP, PostgreSQL, revisión visual) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **ColorLoto tiene ahora quince visualizaciones validadas**; navegación numérica (9/9/8) intacta; la siguiente etapa (AE-16) continúa pendiente de definición. Fase 5 continúa parcial. Ninguno de estos números es un total permanente.

**Checkpoint validado (Etapa AE-16, decimosexta visualización web de ColorLoto -coocurrencia de pares de colores, vigesimoquinta visualización global):** implementada sobre la fuente `ae15-validado` conforme al contrato exacto autorizado por la auditoría previa (Decisión A). Reutiliza `calcular_coocurrencia_pares_colores` sin ninguna modificación (hash de `consecutivos.py` y `coocurrencia.py` idénticos antes/después, confirmado byte a byte). Conecta `coocurrencia_pares_colores_colorloto` en `/estadisticas/colorloto/coocurrencia-pares-colores`, registrada en el bloque literal de ColorLoto. A DIFERENCIA de AE-14/AE-15 (que calculan sobre los NÚMEROS de las balotas), esta receta calcula sobre los CÓDIGOS DE COLOR -el motor real solo acepta `(resultados, hasta_numero_sorteo=None)`, sin `rango_min`/`rango_max`/`cantidad_balotas`, confirmado por la firma real y por la auditoría previa. Sin ninguna ruta genérica equivalente. El grupo de rutas ColorLoto sin colisión pasa de ocho a **nueve**; el grupo con colisión permanece en siete. Identidad de caché **diccionario VACÍO `{}`**, cero lectura de parámetros -confirmado por AST real.

**Hallazgo crítico y su resolución:** la auditoría previa reprodujo `ValueError: invalid literal for int() with base 10: 'AMARILLO'` al intentar reutilizar `_serializar_metrica_asociacion` (AE-14) tal cual, porque esa función convierte incondicionalmente cada elemento con `int(e)`. Se agregó una función nueva y aislada, `_serializar_metrica_asociacion_texto`, que convierte con `str(e)` en su lugar -`_serializar_metrica_asociacion` **no fue modificada**: AE-14 y AE-15 siguen serializando enteros reales, confirmado con tests directos y ahora también con la caché real en PostgreSQL (`elementos` como array de dos strings JSON, orden canónico ascendente).

Igual que AE-14/AE-15, esta es una **tabla de asociaciones** (sin `<canvas>`, sin Chart.js, sin CDN, sin `|safe`). El motor reporta únicamente pares de colores observados al menos una vez; NO se fijó un límite de filas basado en C(6,2)=15 -la auditoría previa confirmó que la paleta de colores no está hardcodeada en el dominio (`ColorLotoGame`/`Color` permiten que el reglamento la modifique), y el histórico real confirmó exactamente seis colores y los 15 pares posibles, sin que el código impusiera ese máximo como regla fija. Conteo estructural: **25 templates/páginas estadísticos, 22 con canvas** (sin cambio respecto a AE-15, la excepción tabular no crece con esta etapa).

`2455 passed in 17.18s` con `pytest` real en Windows (Python 3.14.6, `pip check` limpio -"No broken requirements found."). Siete pruebas críticas iniciales: `7 passed in 3.17s`. Tests focalizados (4 archivos): `1639 passed in 7.43s`. No hubo fallos iniciales ni correcciones funcionales posteriores -la validación del usuario no encontró ningún defecto, por lo que no se generó una versión v2 del parche provisional. Reconciliación: `2379 + 76 = 2455` en la suite completa, `1563 + 76 = 1639` en los cuatro archivos focalizados, distribuidos en `+32` (`test_calcular_y_persistir_estadistica.py`: `669→701`), `+29` (`test_generalizacion_juegos.py`: `629→658`), `+15` (`test_estadistica_repository.py`: `225→240`) y `+0` en `test_corte_temporal_navegacion.py` (`40→40`).

Confirmado con HTTP real (`TcpTestSucceeded: True` en `127.0.0.1:8000`): `2×200` (`/estadisticas/colorloto/coocurrencia-pares-colores` histórico completo y con `?hasta_numero_sorteo=100`, ambas con `TieneTitulo=True`, `TieneTabla=True`, `TieneCanvas=False`, `TieneChartJS=False`), `4×404` (Baloto, Baloto Revancha, MiLoto y sufijo inválido, confirmando en producción real la ausencia de colisión), `3×422` (cortes `0`, `-1`, texto). El usuario abrió ambas páginas -histórico completo, corte 100, título, tabla, códigos textuales de colores, navegación, ausencia de gráfica- y declaró literalmente: "no vi errores en las paginas".

PostgreSQL real: las cuatro comprobaciones de integridad (balotas distintas de seis, números fuera de `1..7`, colores de otro juego, colores fuera de vigencia) devolvieron `0 rows`. Se confirmaron exactamente dos cachés vigentes -histórico completo (`c5c65717-6090-4e40-b0e2-105fd51e20f9`, corte `NULL`, parámetros `{}`, 15 pares observados) y corte 100 (`bca8f230-b48f-494f-b383-9a1e33dedc43`, corte `100`, parámetros `{}`, 15 pares observados)-, una caché vigente por escenario, búsqueda de parámetros distintos de `{}` en `0 rows`, y estructura JSONB inválida en `0 rows`; `elementos` confirmado como array de exactamente dos strings JSON en orden canónico ascendente, `frecuencia_esperada` y `lift` confirmados `null` en ambas cachés, soporte siempre mayor que cero y menor o igual al total de sorteos.

El cálculo SQL independiente (deduplicando colores por sorteo, generando pares con orden alfabético canónico) produjo 30 filas exactas (15 por escenario). **Histórico completo, 209 sorteos** -par con mayor soporte `BLANCO–ROJO`, 108 apariciones, frecuencia relativa exacta `0.51674641148325358852` (**esto es una cifra descriptiva de lo ya ocurrido, no una recomendación ni predicción**). **Corte 100, 100 sorteos** -mismo par de mayor soporte, `BLANCO–ROJO`, 59 apariciones, frecuencia relativa exacta `0.59000000000000000000`.

La comprobación conjunta de invariantes (pares observados sin duplicados, cantidad no superior al máximo combinatorio dinámico, orden canónico, soporte positivo, soporte no superior al total de sorteos) devolvió `0 rows`. La comparación `FULL JOIN` entre el cálculo SQL independiente y ambas cachés JSONB (corte, color 1, color 2, soporte, total de sorteos, frecuencia relativa) devolvió `0 rows` con tolerancia `1e-12`. Igual que en AE-14/AE-15, aquí no aplica conservación de masa igual al número de sorteos: cada sorteo aporta a varios pares simultáneamente.

Limpieza final: único residuo encontrado `backend/storage/logs/sync.log` (14493 bytes), bloqueado porque Uvicorn seguía en ejecución (PID raíz `1448`, PID hijo `22496`); identificados y detenidos exclusivamente esos dos procesos (cero listeners en el puerto 8000 tras detenerlos), archivo eliminado de forma recuperable; verificación final `DirectoriosCache=0`, `ArchivosResiduales=0`, `ArchivosRuntimeStorage=0`, `git diff --check` exit code `0`. Árbol con exactamente los 12 archivos esperados de AE-16; `consecutivos.py` y `coocurrencia.py` con hash idéntico. Toda esta evidencia (pytest, HTTP, PostgreSQL, revisión visual) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **ColorLoto tiene ahora dieciséis visualizaciones validadas**; navegación numérica (9/9/8) intacta; la siguiente etapa (AE-17) continúa pendiente de definición y no fue implementada. Fase 5 continúa parcial. Ninguno de estos números es un total permanente.

**Checkpoint validado (Etapa AE-17, decimoséptima visualización web de ColorLoto -coocurrencia de tríos de colores, vigesimosexta visualización global):** implementada sobre la fuente `ae16-validado` conforme al contrato exacto autorizado por la auditoría previa (Decisión A). Reutiliza `calcular_coocurrencia_trios_colores` sin ninguna modificación (hash de `consecutivos.py` y `coocurrencia.py` idénticos antes/después, confirmado byte a byte). Conecta `coocurrencia_trios_colores_colorloto` en `/estadisticas/colorloto/coocurrencia-trios-colores`, registrada en el bloque literal de ColorLoto. Mismo patrón exacto que AE-16, esta vez con tamaño de combinación 3 -el motor real tampoco acepta `rango_min`/`rango_max`/`cantidad_balotas`. Sin ninguna ruta genérica equivalente. El grupo de rutas ColorLoto sin colisión pasa de nueve a **diez**; el grupo con colisión permanece en siete. Identidad de caché **diccionario VACÍO `{}`**, cero lectura de parámetros -confirmado por AST real.

**Reutilización del serializador textual, sin ningún cambio:** esta etapa reutiliza `_serializar_metrica_asociacion_texto` (creado en AE-16) EXACTAMENTE COMO ESTÁ -su comprensión de lista genérica `[str(e) for e in f.elementos]` acepta tres elementos igual que dos, sin ningún supuesto de longitud fija. Se registró el hash AST de ambas funciones serializadoras (`_serializar_metrica_asociacion` y `_serializar_metrica_asociacion_texto`) antes y después de esta etapa, y **ambas permanecen idénticas** -confirmado, no asumido. AE-14/AE-15 siguen serializando enteros reales; AE-16 sigue serializando exactamente dos strings; AE-17 es la primera receta en usar tres.

Igual que AE-14/AE-15/AE-16, esta es una **tabla de asociaciones** (sin `<canvas>`, sin Chart.js, sin CDN, sin `|safe`). El motor reporta únicamente tríos de colores observados al menos una vez; NO se fijó un límite de filas basado en C(6,3)=20 -la auditoría previa demostró con un histórico sintético de siete códigos distribuidos entre sorteos que el número global de filas puede superar 20 (produjo 30), y esta receta nunca impone ese número como techo; el histórico real confirmó exactamente 20 tríos en ambos escenarios (histórico completo y corte 100), sin que el código impusiera ese máximo como regla fija. Conteo estructural: **26 templates/páginas estadísticos, 22 con canvas** (sin cambio respecto a AE-16, la excepción tabular no crece con esta etapa).

`2534 passed in 10.49s` con `pytest` real en Windows (Python 3.14.6, `pip check` limpio -"No broken requirements found."). Ocho pruebas críticas iniciales: `8 passed in 2.81s`. Tests focalizados (4 archivos): `1718 passed in 6.72s`. No hubo fallos iniciales ni correcciones funcionales posteriores -la validación del usuario no encontró ningún defecto, por lo que no se generó una versión v2 del parche provisional. Reconciliación: `2455 + 79 = 2534` en la suite completa, `1639 + 79 = 1718` en los cuatro archivos focalizados, distribuidos en `+33` (`test_calcular_y_persistir_estadistica.py`: `701→734`), `+31` (`test_generalizacion_juegos.py`: `658→689`), `+15` (`test_estadistica_repository.py`: `240→255`) y `+0` en `test_corte_temporal_navegacion.py` (`40→40`).

Confirmado con HTTP real (`TcpTestSucceeded: True` en `127.0.0.1:8000`): `2×200` (`/estadisticas/colorloto/coocurrencia-trios-colores` histórico completo y con `?hasta_numero_sorteo=100`, ambas con título y tabla presentes, columnas `Color 1`/`Color 2`/`Color 3` presentes, `<canvas>` y Chart.js ausentes), `4×404` (Baloto, Baloto Revancha, MiLoto y sufijo inválido de ColorLoto, confirmando en producción real la ausencia de colisión), `3×422` (cortes `0`, `-1`, texto). El usuario declaró literalmente: "no vi errores en las paginas".

PostgreSQL real: las cuatro comprobaciones de integridad (balotas distintas de seis, números fuera de `1–7`, colores de otro juego, colores fuera de vigencia) devolvieron `0 rows`. Se confirmaron exactamente dos cachés vigentes -histórico completo (`841c88b4-ef5c-4a0c-94c1-19b64140509f`, corte `NULL`, parámetros `{}`, 20 tríos observados, calculado `2026-09-02 14:01:49.472875+00`) y corte 100 (`55670b80-9f39-4603-8faf-15cfa76b07ce`, corte `100`, parámetros `{}`, 20 tríos observados, calculado `2026-09-02 14:01:49.816003+00`)-, una caché vigente por escenario, búsqueda de parámetros distintos de `{}` en `0 rows`, y estructura JSONB inválida en `0 rows`; cada fila con `elementos` como array de exactamente tres strings en orden canónico ascendente, `frecuencia_esperada`/`lift` confirmados `null`, soporte siempre mayor que cero y menor o igual al total, frecuencia coherente con tolerancia `1e-12`.

El cálculo SQL independiente produjo 40 filas exactas (20 por escenario). **Histórico completo, 209 sorteos** -trío con mayor soporte `AZUL–BLANCO–ROJO`, 69 apariciones, frecuencia relativa exacta `0.33014354066985645933` (**esto es una cifra descriptiva de lo ya ocurrido, no una recomendación ni predicción**). **Corte 100, 100 sorteos** -mismo trío de mayor soporte, `AZUL–BLANCO–ROJO`, 39 apariciones, frecuencia relativa exacta `0.39000000000000000000`.

La comprobación conjunta de invariantes (tríos sin duplicados, orden canónico `color_1 < color_2 < color_3`, cantidad no superior al máximo combinatorio dinámico, soporte positivo, soporte no superior al total de sorteos) devolvió `0 rows`. La comparación `FULL JOIN` entre el cálculo SQL independiente y ambas cachés JSONB (identidad del trío, soporte, total de sorteos, frecuencia relativa) devolvió `0 rows` con tolerancia `1e-12`. Igual que en AE-14/AE-15/AE-16, aquí no aplica conservación de masa igual al número de sorteos: cada sorteo aporta a varios tríos simultáneamente.

Limpieza final: no había procesos Uvicorn coincidentes al iniciar la limpieza (puerto 8000 con `0` procesos escuchando); único residuo encontrado `backend/storage/logs/sync.log` (14493 bytes), enviado a la Papelera de reciclaje; verificación final `DirectoriosCache=0`, `ArchivosResiduales=0`, `ArchivosRuntimeStorage=0`, `git diff --check` exit code `0`. Árbol con exactamente los 12 archivos esperados de AE-17; `consecutivos.py` y `coocurrencia.py` con hash idéntico. Toda esta evidencia (pytest, HTTP, PostgreSQL, revisión visual) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **ColorLoto tiene ahora diecisiete visualizaciones validadas**; navegación numérica (9/9/8) intacta; la siguiente etapa (AE-18) continúa pendiente de definición y no fue implementada. Fase 5 continúa parcial. Ninguno de estos números es un total permanente.

**Checkpoint validado (Etapa AE-18, decimoctava visualización web de ColorLoto -intervalos históricos de colores, vigesimoséptima visualización global):** implementada sobre la fuente `ae17-validado` conforme al contrato exacto autorizado por dos auditorías previas, la segunda de las cuales corrigió una contradicción real detectada entre la identidad de caché propuesta y la llamada a la receta. Reutiliza `calcular_intervalos_historicos_colores` sin ninguna modificación (hash de `consecutivos.py` y `coocurrencia.py` idénticos antes/después, confirmado byte a byte -este motor vive en `atrasos.py`, no en `coocurrencia.py`, pero ambos permanecen protegidos e intactos). Conecta `intervalos_historicos_colores_colorloto` en `/estadisticas/colorloto/intervalos-historicos-colores`, registrada en el bloque literal de ColorLoto. Sin ninguna ruta genérica equivalente. El grupo de rutas ColorLoto sin colisión pasa de diez a **once**; el grupo con colisión permanece en siete.

**Corrección de la contradicción detectada en la auditoría:** el flujo real (`ejecutar()` en `calcular_y_persistir_estadistica.py`) pasa `parametros_metrica` tal cual a la receta, sin agregar ninguna clave -confirmado trazando el código real, línea por línea. Por eso la receta de AE-18 usa las CONSTANTES de módulo `_RANGO_REAL_COLORLOTO`/`_CANTIDAD_NUMEROS_COLORLOTO` (mismo patrón ya establecido por AE-14 a AE-17), nunca lee `parametros[...]` -confirmado por AST y por ejecución real sin `KeyError` con la identidad mínima real de esta etapa. A diferencia de AE-14 a AE-17, esta receta SÍ deriva `colores_vigentes` -mismo patrón exacto ya validado por AE-5 (`_codigos_colores_vigentes_en_referencia`). Identidad de caché `{"politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL}` -demostrada, no copiada de AE-5: el motor de intervalos no recibe `rango_min`/`rango_max`/`cantidad_numeros` (a diferencia del motor de atrasos de AE-5), así que esas claves serían redundantes aquí; la política sí forma parte de la identidad porque versiona el algoritmo de derivación de `colores_vigentes`, no los datos.

**Reutilización de `_serializar_atrasos` (Etapa AE-4, protegida) sin ningún cambio:** `dataclasses.asdict` es genérico sobre cualquier dataclass -confirmado con ejecución real sobre una salida real de `IntervalosHistoricos`, incluida la tupla `intervalos` (se serializa como array JSON automáticamente vía `json.dumps`). Se registró el hash AST completo de las tres funciones serializadoras (`_serializar_atrasos`, `_serializar_metrica_asociacion`, `_serializar_metrica_asociacion_texto`) antes y después de esta etapa, y **las tres permanecen idénticas** -confirmado, no asumido. `intervalo_promedio`/`intervalo_mediana` pueden quedar como `int` o `float` real de Python en el JSON según el caso; la normalización a `float` para presentación es responsabilidad exclusiva del View Model (helper `_num_o_none`), nunca del serializador protegido.

**Tabla Y gráfica** -a diferencia de AE-14 a AE-17 (tabla pura), mismo patrón exacto que AE-5 (`atrasos-colores`): cada color tiene múltiples estadísticos numéricos, y una barra del intervalo promedio por color complementa la tabla completa. Conteo estructural: **27 templates/páginas estadísticos, 23 con canvas** -primer incremento de canvas desde AE-14. El View Model deliberadamente NO expone `total_sorteos` -`IntervalosHistoricos` no tiene ese campo (a diferencia de `AtrasoObservado`), y el corte (`hasta_numero_sorteo`) nunca se confunde con una cantidad de sorteos; en su lugar expone `cantidad_colores_analizados`.

`2608 passed in 11.88s` con `pytest` real en Windows (Python 3.14.6, `pip check` limpio -"No broken requirements found."). Ocho pruebas críticas iniciales: `8 passed in 2.11s`. Tests focalizados (4 archivos): `1792 passed in 4.72s`. No hubo fallos iniciales ni correcciones funcionales posteriores -la validación del usuario no encontró ningún defecto, por lo que no se generó una versión v2 del parche provisional. Reconciliación: `2534 + 74 = 2608` en la suite completa, `1718 + 74 = 1792` en los cuatro archivos focalizados, distribuidos en `+28` (`test_calcular_y_persistir_estadistica.py`: `734→762`), `+32` (`test_generalizacion_juegos.py`: `689→721`), `+14` (`test_estadistica_repository.py`: `255→269`) y `+0` en `test_corte_temporal_navegacion.py` (`40→40`).

Confirmado con HTTP real (`TcpTestSucceeded: True` en `127.0.0.1:8000`): `2×200` (`/estadisticas/colorloto/intervalos-historicos-colores` histórico completo y con `?hasta_numero_sorteo=100`, ambas con título y tabla presentes, exactamente 1 `<canvas>`, columnas Color/Apariciones/Intervalo mínimo/Intervalo máximo/Intervalo promedio/Intervalo mediana presentes, Chart.js local con datos JSON, sin CDN), `4×404` (Baloto, Baloto Revancha, MiLoto y sufijo inválido de ColorLoto, confirmando en producción real la ausencia de colisión), `3×422` (cortes `0`, `-1`, texto). Las páginas de histórico completo y corte 100 fueron abiertas manualmente por el usuario, quien declaró literalmente: "no vi errores en las paginas".

PostgreSQL real (contenedor `loteria-predictor-fase2-final-postgres-1`): las cuatro comprobaciones de integridad (seis balotas exactas, rango 1–7, colores de otro juego, colores fuera de vigencia) devolvieron `0 rows`. Se confirmaron exactamente dos cachés vigentes -histórico completo (`9ab76b3a-5e92-4dd1-aa57-fcff10397fc9`, corte `NULL`, parámetros `{"politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"}`, 6 colores analizados, calculado `2026-09-02 19:28:34.684018+00`) y corte 100 (`6d126ec2-6815-4f4a-a06f-15cf2a71e812`, corte `100`, mismos parámetros, 6 colores analizados, calculado `2026-09-02 19:28:34.904074+00`)-, una caché vigente por escenario. La primera versión de la comprobación de parámetros exactos falló con `ERROR: invalid input syntax for type json` -un problema exclusivamente de transporte/quoting del literal JSON entre PowerShell, Docker y `psql`, no un defecto de la aplicación ni de los datos; corregida usando `jsonb_build_object(...)`, la consulta devolvió `0 rows`. La validación de estructura JSONB también devolvió `0 rows`: `valor` como string, cantidades como números, `intervalos` como array de longitud igual a `cantidad_intervalos`, valores no negativos, estadísticos `null` cuando no hay intervalos y numéricos cuando sí los hay.

La reconstrucción SQL independiente produjo exactamente 6 colores por escenario (12 filas totales), con listas completas y ordenadas de intervalos. **Histórico completo**: ROJO con mayor cantidad de apariciones (156, 155 intervalos, mínimo 1, máximo 4, promedio `1.3354838709677419`, mediana 1); AMARILLO 129 apariciones (mínimo 1, máximo 5, promedio `1.6250000000000000`); AZUL 145 (máximo 6, promedio `1.4375000000000000`); BLANCO 149 (máximo 6, promedio `1.3986486486486486`); NEGRO 133 (máximo 5, promedio `1.5757575757575758`); VERDE 139 (máximo 6, promedio `1.5072463768115942`) (**estas cifras son descriptivas de lo ya ocurrido, no una recomendación ni predicción**). **Corte 100**: mismos seis colores con apariciones proporcionalmente menores (ROJO 79, AMARILLO 54, AZUL 71, BLANCO 75, NEGRO 61, VERDE 66), mismo patrón de mínimo 1 en todos.

La comprobación de invariantes (apariciones entre cero y el total de sorteos, `cantidad_intervalos = max(cantidad_apariciones - 1, 0)`, cardinalidad correcta del array, intervalos estrictamente positivos, nulabilidad correcta, suma de intervalos igual a último sorteo menos primero) devolvió `0 rows`. La comparación `FULL JOIN` entre el SQL independiente y ambas cachés JSONB (color, corte, apariciones, intervalos, mínimo, máximo, promedio, mediana, listas completas y ordenadas, paridad de `NULL`, tolerancia `0.000000001`) devolvió `0 rows` en ambos escenarios.

Limpieza final: procesos Uvicorn identificados y detenidos (PID raíz `14348`, PID hijo `9816`, cero procesos escuchando en el puerto 8000 tras detenerlos); único residuo encontrado `backend/storage/logs/sync.log` (14493 bytes), enviado a la papelera; verificación final `DirectoriosCache=0`, `ArchivosResiduales=0`, `ArchivosRuntimeStorage=0`, `git diff --check` exit code `0`. Árbol con exactamente los 12 archivos esperados de AE-18; `consecutivos.py` y `coocurrencia.py` con hash idéntico. Toda esta evidencia (pytest, HTTP, PostgreSQL, revisión visual) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **ColorLoto tiene ahora dieciocho visualizaciones validadas**; navegación numérica (9/9/8) intacta; la siguiente etapa (AE-19) continúa pendiente de definición y no fue implementada. `calcular_distribucion_conteo_color` sigue pendiente de una decisión de producto sobre el selector de color. Fase 5 continúa parcial. Ninguno de estos números es un total permanente.

**Checkpoint validado (Etapa AE-19, decimonovena visualización web de ColorLoto -distribución de sumas, vigesimoctava visualización global):** implementada sobre la fuente `ae18-validado` conforme al contrato exacto autorizado por tres auditorías previas (Decisión C: se pospuso `calcular_distribucion_conteo_color` -su `color_objetivo` exige una decisión de producto, selector explícito o receta agregadora, sin ningún precedente real en las 27 rutas ni en las 27 recetas existentes en el momento de la auditoría; **no se implementó ningún selector de color ni ninguna receta agregadora en esta etapa**). Reutiliza `calcular_distribucion_sumas_colorloto` sin ninguna modificación (hash de `consecutivos.py`, `coocurrencia.py`, `atrasos.py` y `distribuciones.py` idénticos antes/después, confirmado byte a byte). Conecta `distribucion_sumas_colorloto` en `/estadisticas/colorloto/distribucion-sumas`, registrada en el bloque literal de ColorLoto. Sin ninguna ruta genérica equivalente. El grupo de rutas ColorLoto sin colisión pasa de once a **doce**; el grupo con colisión permanece en siete.

**Identidad `{}`, demostrada, no copiada:** a diferencia de AE-5/AE-18 (que sí derivan `colores_vigentes`), esta receta NO recibe ningún parámetro de color -el motor ignora el color por completo, suma únicamente los NÚMEROS de las 6 balotas (confirmado por lectura directa y por ejecución real: el mismo histórico con colores distintos produce el mismo resultado). Receta con cero lectura de `parametros[...]` (AST real), 1 argumento posicional al motor, 0 kwargs, nunca `hasta_numero_sorteo` -mismo precedente que las 27 recetas anteriores, histórico ya filtrado dos veces (SQL + defensivo en memoria) antes de llegar aquí.

**Serializador nuevo `_serializar_distribucion_sumas`:** `DistribucionSumas` es un objeto ÚNICO -a diferencia de las 27 recetas anteriores, que devuelven listas de filas- por lo que NO usa `{"filas": [...]}"`. Las claves de `percentiles` se convierten a string explícitamente en el serializador (concern de esquema); `media`/`mediana`/`desviacion_estandar` se dejan sin normalizar -pueden llegar como `int` o `float` real de Python según el caso, responsabilidad exclusiva del View Model. **Reutiliza `_num_o_none` (Etapa AE-18) sin ningún cambio** -hash AST idéntico antes/después, junto con los otros tres serializadores protegidos y los cuatro motores.

**Tarjetas y gráfica** -a diferencia de AE-14 a AE-17 (tabla pura) y distinto también de AE-5/AE-18 (tabla y gráfica de filas): aquí son 7 tarjetas (sorteos analizados, corte, mínimo, máximo, media, mediana, desviación estándar) más 1 gráfica de barras de los 5 percentiles (P10/P25/P50/P75/P90). **Las tarjetas permanecen siempre visibles**, incluso con histórico vacío; el `<canvas>` (exactamente 1 en el código fuente) está condicionado a `estadistica.chart_labels`. Conteo estructural: **28 templates/páginas estadísticos, 24 con canvas** -segundo incremento de canvas desde AE-14.

`2636 passed in 7.87s` con `pytest` real en Windows (Python 3.14.6, `pip check` limpio -"No broken requirements found."). Veintiocho pruebas nuevas: `28 passed in 1.92s`. Tests focalizados (4 archivos): `1820 passed in 4.27s`. No hubo fallos iniciales ni correcciones funcionales posteriores -la validación del usuario no encontró ningún defecto, por lo que no se generó una versión v2 del parche provisional. Reconciliación: `2608 + 28 = 2636` en la suite completa, `1792 + 28 = 1820` en los cuatro archivos focalizados, distribuidos en `+14` (`test_calcular_y_persistir_estadistica.py`), `+10` (`test_generalizacion_juegos.py`), `+4` (`test_estadistica_repository.py`) y `+0` en `test_corte_temporal_navegacion.py`.

Confirmado con HTTP real (`127.0.0.1:8000`): `2×200` (`/estadisticas/colorloto/distribucion-sumas` histórico completo y con `?hasta_numero_sorteo=100`, ambas con título, "Sorteos analizados", "Corte temporal", "Suma mínima", "Suma máxima", "Media", "Mediana" y "Desviación estándar" presentes, exactamente 1 canvas, Chart.js local, bloque JSON y `new Chart(...)` presentes, ningún CDN de Chart.js), `4×404` (Baloto, Baloto Revancha, MiLoto y sufijo inválido de ColorLoto, confirmando en producción real la ausencia de colisión), `3×422` (cortes `0`, `-1`, texto). El usuario declaró literalmente: "no vi ningun error en las paginas".

PostgreSQL real (contenedor `loteria-predictor-fase2-final-postgres-1`, base `loteria_predictor`): las cuatro comprobaciones de integridad (seis balotas exactas, rango 1–7, colores de otro juego, colores fuera de vigencia) devolvieron `0 rows`. Se confirmaron exactamente dos cachés vigentes -histórico completo (`6d6decc5-2c56-4c27-bd29-34cbb5f1c41c`, corte `NULL`, parámetros `{}`, 209 sorteos, mínimo 14, máximo 38, media `24.401913875598087`, mediana 24, desviación `4.203119845159542`, P10/P25/P50/P75/P90 = 19.0/21.0/24.0/27.0/30.0) y corte 100 (`d4b8cc28-9748-4e2c-bc77-e8a4cc5b859b`, corte `100`, mismos parámetros, 100 sorteos, mínimo 15, máximo 34, media `24.74`, mediana 24.0, desviación `4.258215588717885`, P10/P25/P50/P75/P90 = 18.9/22.0/24.0/27.0/30.1)-, una caché vigente por escenario, búsqueda de parámetros distintos de `{}` en `0 rows`, y validación de esquema JSON (claves, tipos, rangos, orden de percentiles) en `0 rows`.

La reconstrucción SQL independiente (`SUM(scn.numero)` sobre las seis balotas físicas de cada sorteo -números repetidos contados individualmente, colores sin intervenir) coincidió exactamente: histórico completo 209 sorteos, mínimo 14, máximo 38, media `24.4019138755980861`, mediana 24, desviación `4.2031198451595423`, P10/P25/P50/P75/P90 = 19/21/24/27/30 (**cifras descriptivas de lo ya ocurrido, no una recomendación ni predicción**); corte 100, 100 sorteos, mínimo 15, máximo 34, media `24.7400000000000000`, mediana 24, desviación `4.2582155887178845`, P10/P25/P50/P75/P90 = 18.9/22/24/27/30.1. La consulta de invariantes matemáticas devolvió `0 rows`. La comparación `FULL JOIN` contra JSONB, con tolerancia `0.000000001`, devolvió `0 rows` en ambos escenarios. La primera versión de esa consulta falló con `ERROR: FULL JOIN is only supported with merge-joinable or hash-joinable join conditions` -causado por usar `cv.corte IS NOT DISTINCT FROM si.corte` como condición del `FULL JOIN`; no fue un defecto de AE-19 ni de la aplicación, sino una limitación de la consulta de validación en PostgreSQL, corregida con `COALESCE(cv.corte,-1)=COALESCE(si.corte,-1)` (centinela seguro porque FastAPI solo admite cortes `>= 1`); la consulta corregida devolvió `0 rows`.

Limpieza final: procesos Uvicorn identificados y detenidos (PID `8660`, `14024`, hijos `8608` y `9924`, cero procesos escuchando en el puerto 8000 tras detenerlos); único residuo encontrado `backend/storage/logs/sync.log` (14493 bytes, simultáneamente el único archivo residual y el único archivo runtime de storage), enviado a la papelera; verificación final `DirectoriosCache=0`, `ArchivosResiduales=0`, `ArchivosRuntimeStorage=0`, `git diff --check` exit code `0`. Árbol con exactamente los 12 archivos esperados de AE-19; los cuatro motores con hash idéntico. Toda esta evidencia (pytest, HTTP, PostgreSQL, revisión visual) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **ColorLoto tiene ahora diecinueve visualizaciones validadas**; navegación numérica (9/9/8) intacta; la siguiente etapa (AE-20) continúa pendiente de definición y no fue implementada. `calcular_distribucion_conteo_color` sigue pendiente de una decisión de producto sobre el selector de color. Fase 5 continúa parcial. Ninguno de estos números es un total permanente.

**Checkpoint validado (Etapa AE-20, vigésima visualización web de ColorLoto -intervalos históricos de números, vigesimonovena visualización global):** implementada sobre la fuente `ae19-validado` conforme al contrato exacto autorizado por tres auditorías correctivas sucesivas. Reutiliza `calcular_intervalos_historicos_numeros_colorloto` sin ninguna modificación (hash de los cuatro motores idénticos antes/después, confirmado byte a byte). Conecta `intervalos_historicos_numeros_colorloto` en `/estadisticas/colorloto/intervalos-historicos-numeros`, registrada en el bloque literal de ColorLoto. Sin ninguna ruta genérica equivalente. El grupo de rutas ColorLoto sin colisión pasa de doce a **trece**; el grupo con colisión permanece en siete.

**Identidad `{"rango_min": 1, "rango_max": 7}`, resuelta tras tres correcciones sucesivas:** a diferencia de AE-14/AE-15/AE-16/AE-17/AE-19 (identidad `{}`), este motor SÍ construye su universo de filas directamente desde `rango_min`/`rango_max` (`range(rango_min, rango_max+1)`, confirmado por lectura directa del motor real) -mismo criterio real ya demostrado por `frecuencia_numeros_colorloto` (AE-1) y `atrasos_numeros_colorloto` (AE-4), cuyos motores construyen su universo exactamente de la misma forma. `cantidad_numeros` NO forma parte de la identidad -el motor de esta etapa no la recibe en absoluto, solo se usa para validación defensiva. El router construye la identidad desde `juego.rango_min`/`juego.rango_max` (la entidad real, sembrada con `rango_min=1, rango_max=7` en la migración inicial) -nunca desde la constante privada `_RANGO_REAL_COLORLOTO`, que no está importada en el router.

**Validación defensiva reutilizada, no omitida:** auditoría AST de las 19 recetas ColorLoto ya conectadas confirmó que 18 de 19 llaman a `_validar_historico_colorloto_consistente` (la única excepción, AE-19, tiene un motor que no recibe ni rango ni cantidad). Esta receta también la reutiliza -demostrado por ejecución real que, sin este helper, una cantidad incorrecta de balotas o un color inválido pasarían silenciosamente al motor sin ningún aviso. La validación ocurre siempre antes del motor: si falla, ni el motor se invoca ni se persiste ninguna caché -confirmado por ejecución real con motor espiado.

**Corrección de un test engañosamente nombrado, incorporada antes de la validación en Windows:** el test `test_numero_fuera_de_rango_receta_propaga_value_error` afirmaba en su nombre que la receta propaga `ValueError`, pero un número fuera de 1–7 es interceptado **primero** por `_validar_historico_colorloto_consistente` (que también revisa el rango numérico), produciendo `ResultadoHistoricoInconsistenteError` -**el motor nunca llega a invocarse, no se persiste ninguna caché**. El `ValueError` propio del motor sigue existiendo y sigue cubierto, pero únicamente es alcanzable mediante una llamada directa al motor (fuera de la receta), protegido por su propio test de motor real (`test_numero_fuera_de_rango_lanza_value_error`, `test_atrasos.py`). El test se renombró a `test_validacion_ocurre_antes_del_motor_numero_fuera_de_rango` y ahora verifica, con el motor espiado, que este nunca se invoca -el nombre antiguo tiene cero ocurrencias, el nuevo existe exactamente una vez, reconfirmado por el usuario en Windows.

**Reutilización de `_serializar_atrasos` (Etapa AE-4, protegida) sin ningún cambio:** mismo tipo de retorno exacto que AE-18 (`list[IntervalosHistoricos]`), confirmado por ejecución real que el serializador funciona sin ninguna modificación. `cantidad_apariciones`/`cantidad_intervalos` son SIEMPRE enteros reales (`0` cuando corresponde, nunca `None`). Solo `intervalo_promedio`/`intervalo_mediana` pasan por `_num_o_none` (reutilizado sin ningún cambio); `intervalo_minimo`/`intervalo_maximo` se preservan como enteros reales o `None` literal, nunca normalizados a `float`.

**Tabla y gráfica**, mismo patrón que AE-5/AE-18: la tabla de 7 filas (números 1 a 7) permanece **siempre completa**, incluso con histórico vacío (universo fijo, no depende del histórico) -a diferencia de AE-19, el `<canvas>` (exactamente 1 en el código fuente) se muestra siempre que existe conexión y estadística, sin ninguna condición adicional de "datos insuficientes". Conteo estructural: **29 templates/páginas estadísticos, 25 con canvas** -tercer incremento de canvas desde AE-14.

`31 passed in 3.66s` con `pytest` real en Windows (Python 3.14.6, `pip check` limpio -"No broken requirements found."). Tests focalizados (4 archivos): `1851 passed in 7.79s`. Suite completa: `2667 passed in 16.23s`. No hubo fallos ni correcciones funcionales posteriores a la corrección de nomenclatura ya incorporada -no se generó una versión adicional del parche provisional. Reconciliación: `2636 + 31 = 2667` en la suite completa, `1820 + 31 = 1851` en los cuatro archivos focalizados, distribuidos en `+15` (`test_calcular_y_persistir_estadistica.py`), `+12` (`test_generalizacion_juegos.py`), `+4` (`test_estadistica_repository.py`) y `+0` en `test_corte_temporal_navegacion.py`. El usuario confirmó explícitamente: nombre de test antiguo con `0` ocurrencias, nombre corregido con `1` ocurrencia, `0` usos inválidos de `list.count()`, `git diff --check` en `0`, exactamente `12` entradas modificadas.

Aplicación real del parche en Windows: rama `feature/ae20-intervalos-historicos-numeros-colorloto` sobre el commit `d93fca0349365586f9850f447b9b7e0aa7685636` (`main` y tag `ae19-validado` coincidentes). Tamaño y hash del parche verificados correctos; `git apply --check`, `git apply` y `git apply --reverse --check` en `0`; produjo exactamente `12 files changed, 826 insertions(+), 57 deletions(-)`. Las advertencias de whitespace durante `git apply` (`121 lines add whitespace errors`) corresponden a CRLF deliberado -no fueron un error de aplicación, `git apply` terminó en `0` y `git diff --check` también en `0`.

Confirmado con HTTP real (`127.0.0.1:8000`, `TcpTestSucceeded: True`): `2×200` (`/estadisticas/colorloto/intervalos-historicos-numeros` histórico completo y con `?hasta_numero_sorteo=100`, ambas con título, tabla de 7 filas, exactamente 1 canvas, columnas Número/Apariciones/Cantidad de intervalos/Intervalo mínimo/Intervalo máximo/Intervalo promedio/Intervalo mediana presentes, Chart.js local con datos JSON, sin CDN, 7 etiquetas `1`-`7`, 7 promedios), `4×404` (Baloto, Baloto Revancha, MiLoto, sufijo inválido de ColorLoto), `3×422` (cortes `0`, `-1`, texto). Las páginas de histórico completo y corte 100 fueron abiertas manualmente por el usuario, quien declaró literalmente: "no vi errores en las paginas".

PostgreSQL real: las cuatro comprobaciones de integridad (seis balotas exactas, rango 1–7, colores de otro juego, colores fuera de vigencia) devolvieron `0 rows`. Se confirmaron exactamente dos cachés vigentes -histórico completo (`28d8db03-cf1c-4a76-8da8-9a1ff76cfd8b`, corte `NULL`, parámetros `{"rango_max": 7, "rango_min": 1}`, 7 números analizados, calculado `2026-09-03 07:31:56.348858+00`) y corte 100 (`9862ff0c-a5e1-48d1-899b-19eb64e64f75`, corte `100`, mismos parámetros, 7 números analizados, calculado `2026-09-03 07:31:56.976993+00`)-, una caché vigente por escenario, búsqueda de identidad distinta de `{"rango_min":1,"rango_max":7}` en `0 rows`, y validación de estructura JSON (siete filas únicas 1–7) en `0 rows`.

La reconstrucción SQL independiente produjo exactamente 14 filas (7 números × 2 escenarios). **Histórico completo** (209 sorteos): número 4 con mayor intervalo máximo (8), número 3 con mayor cantidad de apariciones (146, 145 intervalos, promedio `1.4344827586206897`); los siete números con mínimo 1 y mediana 1 (**cifras descriptivas de lo ya ocurrido, no una recomendación ni predicción**). **Corte 100** (100 sorteos): mismos siete números con apariciones proporcionalmente menores (54 a 72), número 1 con mediana 2 (único caso distinto de 1 entre las 14 filas). Se confirmó `cantidad_intervalos = cantidad_apariciones - 1`, listas de intervalos en orden cronológico, intervalos positivos, estadísticos dentro de sus límites, y suma de intervalos igual a último sorteo menos primero. La consulta de invariantes devolvió `0 rows`. La comparación `FULL JOIN` entre el SQL independiente y ambas cachés JSONB (universo de números, apariciones, intervalos, mínimo, máximo, promedio, mediana, listas completas en orden) devolvió `0 rows` en ambos escenarios.

Limpieza final: procesos Uvicorn identificados y detenidos (PID raíz `25032`, hijo `13748`, `taskkill /T /F` terminó el árbol completo incluido el proceso `20500`, cero procesos escuchando en el puerto 8000 tras detenerlos); único residuo encontrado `backend/storage/logs/sync.log` (14493 bytes), enviado a la papelera; verificación final `DirectoriosCache=0`, `ArchivosResiduales=0`, `ArchivosRuntimeStorage=0`, `git diff --check` exit code `0`. Árbol con exactamente los 12 archivos esperados de AE-20; los cuatro motores con hash idéntico. Toda esta evidencia (pytest, HTTP, PostgreSQL, revisión visual) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **ColorLoto tiene ahora veinte visualizaciones validadas**; navegación numérica (9/9/8) intacta; la siguiente etapa (AE-21) continúa pendiente de definición y no fue implementada. `calcular_distribucion_conteo_color` sigue pendiente de una decisión de producto sobre el selector de color. Fase 5 continúa parcial. Ninguno de estos números es un total permanente.

**Checkpoint validado (Etapa AE-21, vigesimoprimera visualización web de ColorLoto -intervalos históricos de pares número-color, trigésima visualización global):** implementada sobre la fuente `ae20-validado` conforme al contrato exacto autorizado por auditoría exhaustiva post-AE-20. Reutiliza `calcular_intervalos_historicos_pares_numero_color` sin ninguna modificación (hash de los cuatro motores idénticos antes/después, confirmado byte a byte). Conecta `intervalos_historicos_pares_numero_color_colorloto` en `/estadisticas/colorloto/intervalos-historicos-pares-numero-color`, registrada en el bloque literal de ColorLoto. Sin ninguna ruta genérica equivalente. El grupo de rutas ColorLoto sin colisión pasa de trece a **catorce**; el grupo con colisión permanece en siete.

**Identidad `{"rango_min": 1, "rango_max": 7, "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"}`:** a diferencia de AE-20 (identidad solo con rango), este motor construye su universo con el producto cartesiano `range(rango_min, rango_max+1) × colores_a_reportar` (confirmado por lectura directa del motor real, `atrasos.py:378`), por lo que la identidad incluye TANTO el rango COMO la política de universo de colores -combinación real de los criterios ya demostrados por AE-20 (rango, desde `juego.rango_min`/`juego.rango_max`) y AE-5/AE-18 (política de colores, desde `POLITICA_UNIVERSO_COLORES_ACTUAL`). `cantidad_numeros` sigue excluida -el motor no la recibe, solo se usa para validación defensiva. **Llamada al motor confirmada con exactamente 4 argumentos posicionales, cero kwargs, sin `hasta_numero_sorteo`; cero lectura de claves de `parametros`** -ambos confirmados por AST real.

**Validación defensiva reutilizada, no omitida:** reutiliza `_validar_historico_colorloto_consistente` y `_codigos_colores_vigentes_en_referencia` (ambos protegidos, hash AST idéntico antes/después). **Caracterización empírica realizada ANTES de escribir cualquier test** (evitando repetir la contradicción ya corregida en AE-20): confirmado por ejecución real con motor espiado que un número fuera de 1–7 es interceptado **primero** por la validación (`ResultadoHistoricoInconsistenteError`), el motor nunca se invoca -el test correspondiente se llama desde el inicio `test_validacion_ocurre_antes_del_motor_numero_fuera_de_rango`, sin ningún nombre engañoso que necesitara corrección posterior. Mismos controles verificados para cantidad de balotas incorrecta y color inválido: motor no invocado, caché no persistida en ambos casos.

**Reutilización de `_serializar_atrasos` (Etapa AE-4, protegida) y de `_deserializar_par_numero_color` (Etapa AE-6, protegida), ambos sin ningún cambio:** mismo tipo de retorno exacto que AE-18/AE-20 (`list[IntervalosHistoricos]`), `valor` con formato `"numero-color"` (p.ej. `"5-ROJO"`), deserializado con el único punto de parseo ya existente. `cantidad_apariciones`/`cantidad_intervalos` son SIEMPRE enteros reales (nunca `None`). Solo `intervalo_promedio`/`intervalo_mediana` pasan por `_num_o_none` (reutilizado sin ningún cambio).

**Tabla y gráfica**, mismo patrón que AE-5/AE-18/AE-20: la tabla de 42 pares (7 números × 6 colores, universo fijo) permanece **siempre completa**. El `<canvas>` (exactamente 1 en el código fuente, con exactamente 1 dataset `"Intervalo promedio"`, etiquetas `"<numero>-<color>"`) se muestra siempre que existe conexión y estadística, sin ninguna condición adicional de "datos insuficientes". JSON entregado de forma segura (`<script type="application/json">` + `JSON.parse`), sin CDN, sin `|safe`. Conteo estructural: **30 templates/páginas estadísticos, 26 con canvas** -cuarto incremento de canvas desde AE-14.

`31 passed in 2.55s` con `pytest` real en Windows (Python 3.14.6, `pip check` limpio -"No broken requirements found."). Tests focalizados (4 archivos): `1882 passed in 4.94s`. Suite completa: `2698 passed in 12.79s`. No hubo fallos ni correcciones posteriores -no se generó una versión adicional del parche provisional. Reconciliación: `2667 + 31 = 2698` en la suite completa, `1851 + 31 = 1882` en los cuatro archivos focalizados, distribuidos en `+15` (`test_calcular_y_persistir_estadistica.py`), `+12` (`test_generalizacion_juegos.py`), `+4` (`test_estadistica_repository.py`) y `+0` en `test_corte_temporal_navegacion.py`. El usuario confirmó explícitamente: `0` usos inválidos de `list.count()`, `git diff --check` en `0`, exactamente `12` entradas modificadas.

Confirmado con HTTP real (`127.0.0.1:8000`, `TcpTestSucceeded: True`): `2×200` (`/estadisticas/colorloto/intervalos-historicos-pares-numero-color` histórico completo y con `?hasta_numero_sorteo=100`, ambas con título, tabla de 42 filas, exactamente 1 canvas, columnas Número/Color/Apariciones/Cantidad de intervalos/Intervalo mínimo/Intervalo máximo/Intervalo promedio/Intervalo mediana presentes, Chart.js local con datos JSON, sin CDN, 42 etiquetas de gráfica válidas, 42 valores de gráfica, dataset exacto confirmado), `4×404` (Baloto, Baloto Revancha, MiLoto, sufijo inválido de ColorLoto), `3×422` (cortes `0`, `-1`, texto). El usuario abrió manualmente ambas páginas y declaró literalmente: "no veo errores en las paginas".

PostgreSQL real: las cuatro comprobaciones de integridad (seis balotas exactas, rango 1–7, colores de otro juego, colores fuera de vigencia) devolvieron `0 rows`. Se confirmaron exactamente dos cachés vigentes -histórico completo (`c6518feb-8656-48da-96e5-e2a7665e3aed`, corte `NULL`, parámetros `{"rango_max": 7, "rango_min": 1, "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"}`, 42 pares analizados, calculado `2026-09-03 20:40:42.15047+00`) y corte 100 (`eb0f6039-70e2-42ac-8c77-fabe8edb4340`, corte `100`, mismos parámetros, 42 pares analizados, calculado `2026-09-03 20:40:42.587379+00`)-, una caché vigente por escenario, búsqueda de parámetros distintos de la identidad exacta en `0 rows`, filas con estructura inválida en `0 rows`, diferencias en el universo rango × colores en `0 rows`, violaciones de invariantes matemáticas en `0 rows`, y comparación `FULL JOIN` entre el SQL independiente y ambas cachés JSONB (presencia del par, apariciones, intervalos, mínimo, máximo, promedio, mediana, lista completa y ordenada de intervalos) en `0 rows` para los 42 pares de ambos escenarios.

Limpieza final: procesos Uvicorn identificados y detenidos (PID raíz `27288`, hijo `8460`, `taskkill /T /F` terminó el árbol completo incluido el proceso `8804`, cero procesos escuchando en el puerto 8000 tras detenerlos); único residuo encontrado `backend/storage/logs/sync.log` (14493 bytes), enviado a la papelera; verificación final `DirectoriosCache=0`, `ArchivosResiduales=0`, `ArchivosRuntimeStorage=0`, `git diff --check` exit code `0`. Árbol con exactamente los 12 archivos esperados de AE-21; los cuatro motores con hash idéntico. Toda esta evidencia (pytest, HTTP, PostgreSQL, revisión visual) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **ColorLoto tiene ahora veintiuna visualizaciones validadas**; navegación numérica (9/9/8) intacta; la siguiente etapa (AE-22) continúa pendiente de definición y no fue implementada. `calcular_distribucion_conteo_color` sigue pendiente de una decisión de producto sobre el selector de color. Fase 5 continúa parcial. Ninguno de estos números es un total permanente.

**Checkpoint validado (Etapa AE-22, vigesimosegunda visualización web de ColorLoto -frecuencia de colores por año, trigesimoprimera visualización global):** primera página de ColorLoto con un control de interfaz adicional al corte temporal -selector visible de año, decisión de producto autorizada explícitamente tras la auditoría exhaustiva de las diez candidatas pendientes (ninguna otra podía resolverse sin un selector o un agregador de motor en bucle, ambos sin precedente real en las 30 recetas ya conectadas). Reutiliza `calcular_frecuencia_colores_por_anio` sin ninguna modificación (hash de los seis motores -incluidos `frecuencia_temporal.py` y `recencia.py`- idénticos antes/después, confirmado byte a byte). Conecta `frecuencia_colores_por_anio_colorloto` en `/estadisticas/colorloto/frecuencia-colores-por-anio`. Sin ninguna ruta genérica equivalente -ningún juego numérico tiene concepto de color. El grupo de rutas ColorLoto sin colisión pasa de catorce a **quince**; el grupo con colisión permanece en siete.

**Selector sin valor predeterminado:** sin `anio`, la ruta responde `200` mostrando únicamente el formulario, sin ejecutar el orquestador, sin invocar el motor, sin consultar ni persistir ninguna caché -confirmado por AST real sobre la función del router (bloque `if anio is None` con cero llamadas a `.ejecutar`) y reconfirmado con HTTP real: cachés antes `0`, cachés después `0`. Nunca se elige automáticamente un año "actual" ni "el último con datos" -cualquier valor por defecto sería arbitrario y quedaría obsoleto, decisión de producto explícita. Con `anio` fuera de `1..9999`, FastAPI responde `422` nativamente antes de que el handler se ejecute; confirmado con HTTP real para `anio=0`, `anio=-1`, `anio=10000` y `anio=texto`, además de los tres cortes inválidos (`0`, negativo, no numérico) -siete respuestas `422` correctas, cero fallos. La primera ejecución de esos controles produjo `-1` por una interpolación incorrecta de PowerShell (`"$baseAE22?anio=..."`, sin comillas explícitas alrededor del valor); corregido usando concatenación explícita, y los siete casos devolvieron `422` -error exclusivo del comando de validación del usuario, no de la aplicación. Con un año válido sin sorteos, la respuesta sigue siendo `200` -universo completo de colores en cero, nunca un `404`; confirmado con HTTP real para el año 1900: seis colores reportados, todos los promedios en cero, página respondida correctamente.

**Primera receta con lectura real de `parametros`, justificada por evidencia:** confirmado por lectura directa de `ejecutar()` -`receta.calcular(historico, parametros_metrica)` es el único canal por el que el año elegido por el usuario puede llegar hasta la receta, a diferencia de las 21 recetas anteriores (cuyos parámetros eran siempre constantes de juego o derivables de la fecha de referencia). La receta lee **únicamente** `parametros["anio"]` -confirmado por AST real, ningún parámetro oculto adicional. Identidad `{"anio": <entero>, "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"}` -solo existe cuando hay año seleccionado; `anio` cambia matemáticamente el resultado (determina el subconjunto exacto analizado), por lo que forma parte de la identidad. `hasta_numero_sorteo` permanece en su propia columna, nunca en la identidad; el corte general se aplica al histórico antes del filtro anual. Reutiliza `_validar_historico_colorloto_consistente` y `_codigos_colores_vigentes_en_referencia` (ambos protegidos, sin cambios) -misma validación defensiva antes del motor ya usada 19 veces; caracterización empírica confirmada con motor espiado: número fuera de rango, cantidad de balotas incorrecta y color inválido son interceptados antes del motor, con `ResultadoHistoricoInconsistenteError`, motor nunca invocado, caché nunca persistida. Llamada al motor con tres argumentos posicionales y cero kwargs, nunca `hasta_numero_sorteo`.

**Reutilización de `_serializar_frecuencia_observada` (protegida) sin ningún cambio:** mismo dataclass `FrecuenciaObservada` ya usado por `frecuencia_colores_colorloto` (Etapa AE-2). Semántica preservada exactamente: balotas físicas contadas individualmente sin deduplicar por sorteo (confirmado por ejecución real: 3 apariciones de ROJO en 2 sorteos de 2024, `frecuencia_relativa=1.5`, supera 1.0 legítimamente), denominador = sorteos del subconjunto anual, universo = colores vigentes en la fecha de referencia ∪ observados, año vacío devuelve las 6 filas en cero. VM sigue el mismo criterio semántico ya establecido por `frecuencia_colores_colorloto_a_vm` (AE-2): **"apariciones promedio por sorteo", nunca "porcentaje"** -expuesto como `apariciones_promedio` (float) y `apariciones_promedio_texto` (`.2f`), etiqueta de gráfica confirmada con HTTP real como "Apariciones promedio por sorteo" -corregida de una etiqueta inicial ambigua, "Frecuencia relativa", que sugería incorrectamente una proporción acotada a `[0,1]`; el nombre interno `frecuencia_relativa` del contrato serializado permanece intacto, la corrección fue exclusivamente de presentación.

**Preservación bidireccional año↔corte, corregida y confirmada con HTTP real:** el formulario de corte conserva `anio`; el formulario de año conserva `hasta_numero_sorteo`; "Histórico completo" elimina el corte y conserva el año; exactamente un enlace de la página propaga `anio`; las demás páginas de ColorLoto no reciben ni propagan el año; la navegación común continúa propagando únicamente el corte. El campo oculto `anio` en el partial compartido se emite únicamente cuando el contexto de la ruta actual lo define (`anio is defined and anio is not none`), sin alterar el comportamiento de las otras 30 páginas. Alcance ampliado de 12 a **13 archivos** -autorizado expresamente para esta corrección- incluyendo `control_corte_temporal.html`.

**Formulario y gráfica:** control HTML numérico visible (`type="number"`, `min="1"`, `max="9999"`); confirmado con HTTP real: canvas presente con año y datos, seis colores y seis promedios reportados, al menos un promedio mayor que cero; canvas ausente sin año seleccionado, sin `new Chart(`. Conteo estructural: **31 templates/páginas estadísticos, 27 con canvas** -quinto incremento de canvas desde AE-14.

**Reconciliación de pruebas -corregida sin mezclar métricas:** `43 passed in 3.77s` para las pruebas específicas de AE-22 en Windows (35 de la implementación inicial más 8 de la corrección de preservación bidireccional). Tests focalizados (4 archivos): `1925 passed in 7.47s`. Suite completa: `2741 passed in 11.63s`. Reconciliación: `2698 + 43 = 2741`; focalizados `1882 + 43 = 1925`. Inventario final por archivo: `test_calcular_y_persistir_estadistica.py` `820`, `test_generalizacion_juegos.py` `780`, `test_estadistica_repository.py` `285`, `test_corte_temporal_navegacion.py` `40` -distinguido explícitamente de las declaraciones `Query`: `31` rutas, `31` declaraciones de `hasta_numero_sorteo: int | None = Query(default=None, ge=1)`, `1` declaración de `anio: int | None = Query(default=None, ge=1, le=9999)`. Cero coincidencias de `list.count("...", "...")` inválido. Exactamente `13` entradas modificadas antes y después de las pruebas. `git diff --check` en `0`.

**Aislamiento de rutas confirmado con HTTP real:** Baloto, Baloto Revancha, MiLoto y un sufijo inexistente de ColorLoto -cuatro respuestas `404` correctas.

**Revisión visual humana**, cita literal del usuario: "no vi errores en las paginas".

**PostgreSQL real:** las cuatro comprobaciones de integridad del histórico (balotas distintas de seis, números fuera de 1–7, colores de otro juego, colores fuera de vigencia) devolvieron `0 rows`. Se observaron seis cachés vigentes, una por identidad: año 1900 (histórico completo), año 2024 (histórico completo), año 2025 (histórico completo), año 2026 (histórico completo), año 2026 (corte 100) y año 2027 (histórico completo) -las cachés de 2024, 2025 y 2027 se crearon legítimamente durante la revisión manual del selector, no son residuos ni identidades inesperadas. Las seis mantienen parámetros exactos (`anio`, `politica_universo_colores`), seis filas cada una, sin anomalías de estructura, tipos JSON correctos, valores no negativos, y cumplen `frecuencia_relativa = apariciones / total_sorteos` (cero cuando `total_sorteos = 0`). Comparación SQL independiente -reconstruyendo el universo vigente en la fecha de referencia ∪ observados, aplicando primero el corte general y después el filtro anual, contando balotas físicas sin deduplicar- contra las seis cachés: `0 rows`, cero diferencias en color, apariciones, total de sorteos o frecuencia. Invariante de balotas físicas (`SUM(apariciones) = 6 × total_sorteos` por identidad): `0 rows` de anomalías.

**Limpieza final real:** procesos Uvicorn identificados y detenidos (PID raíz `3284`, hijos `20556` y `536`, cero procesos escuchando en el puerto 8000 tras detenerlos); único residuo encontrado `backend/storage/logs/sync.log` (14493 bytes), enviado a la papelera; verificación final `DirectoriosCache=0`, `ArchivosResiduales=0`, `ArchivosRuntimeStorage=0`, `git diff --check` exit code `0`. Árbol con exactamente los 13 archivos esperados de AE-22; los seis motores con hash idéntico. Toda esta evidencia (pytest, HTTP, PostgreSQL, revisión visual) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **ColorLoto tiene ahora veintidós visualizaciones validadas**; navegación numérica (9/9/8) intacta; la siguiente etapa (AE-23) continúa pendiente de definición y no fue implementada. `calcular_distribucion_conteo_color`, la frecuencia de colores por mes, la frecuencia de colores por día de semana y las comparaciones por ventana siguen pendientes de decisión de producto. Fase 5 continúa parcial. Ninguno de estos números es un total permanente.

**Checkpoint validado (Etapa AE-23, vigesimotercera visualización web de ColorLoto -frecuencia de colores por mes, trigesimosegunda visualización global):** reutiliza exactamente el precedente validado por AE-22 (selector de año) para un selector de mes calendario -decisión de producto explícita, selector desplegable con los doce meses en español, sin valor por defecto. "Mes" combina el mismo mes calendario (enero, febrero, ...) a través de TODOS los años del histórico, nunca un año-mes concreto -confirmado por lectura directa del motor real (`_filtrar_por_mes`, `r.fecha.month == mes`, sin agrupar por año) y por ejecución real en sandbox. Reutiliza `calcular_frecuencia_colores_por_mes` sin ninguna modificación (hash de los seis motores idénticos antes/después, confirmado byte a byte -incluida una verificación adicional de que la etapa no modificó ni `_calcular_frecuencia_colores_por_anio_colorloto` ni `frecuencia_colores_por_anio_colorloto_a_vm` ni la rama condicional de `anio` del router, los tres reconfirmados con hash AST idéntico). Conecta `frecuencia_colores_por_mes_colorloto` en `/estadisticas/colorloto/frecuencia-colores-por-mes`. Sin ninguna ruta genérica equivalente. El grupo de rutas ColorLoto sin colisión pasa de quince a **dieciséis**; el grupo con colisión permanece en siete.

**Selector sin valor predeterminado:** sin `mes`, la ruta responde `200` mostrando únicamente el formulario, sin ejecutar el orquestador, sin invocar el motor, sin consultar ni persistir ninguna caché -confirmado por AST real sobre la función del router (bloque `if mes is None` con cero llamadas a `.ejecutar`) y reconfirmado con HTTP real: cachés antes `0`, cachés después `0`. Nunca se elige automáticamente el mes actual -cualquier valor por defecto sería arbitrario, decisión de producto explícita. Con `mes` fuera de `1..12`, FastAPI responde `422` nativamente antes de que el handler se ejecute; confirmado con HTTP real para `mes=0`, `mes=-1`, `mes=13` y `mes=texto`, además de los tres cortes inválidos (`0`, negativo, no numérico) -siete respuestas `422` correctas, cero fallos. Con un mes válido sin sorteos, la respuesta sigue siendo `200` -universo completo de colores en cero, nunca un `404`; confirmado con HTTP real: enero con corte `1` produjo `0` sorteos (mientras que enero en el histórico completo produjo `18`), demostrando correctamente que el corte temporal se aplica antes del filtro mensual.

**Misma justificación exacta de AE-22 para leer `parametros["mes"]`:** confirmado por lectura directa de `ejecutar()` -`receta.calcular(historico, parametros_metrica)` es el único canal por el que el mes elegido por el usuario puede llegar hasta la receta. La receta lee **únicamente** `parametros["mes"]` -confirmado por AST real. Identidad `{"mes": <entero>, "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"}` -solo existe cuando hay mes seleccionado; `mes` cambia matemáticamente el resultado, por lo que forma parte de la identidad. `hasta_numero_sorteo` permanece en su propia columna, nunca en la identidad. Reutiliza `_validar_historico_colorloto_consistente` y `_codigos_colores_vigentes_en_referencia` (protegidos, sin cambios) -misma validación defensiva antes del motor ya usada 21 veces; caracterización empírica confirmada con motor espiado: número fuera de rango, cantidad de balotas incorrecta y color inválido son interceptados antes del motor, motor nunca invocado, caché nunca persistida. Llamada al motor con tres argumentos posicionales y cero kwargs, nunca `hasta_numero_sorteo`.

**Reutilización de `_serializar_frecuencia_observada` (protegida) sin ningún cambio:** mismo dataclass `FrecuenciaObservada` ya usado por AE-2 y AE-22. Semántica preservada exactamente: balotas físicas contadas individualmente sin deduplicar por sorteo, denominador = sorteos del mes a través de todos los años, universo = colores vigentes ∪ observados, mes vacío devuelve las 6 filas en cero. VM sigue el mismo criterio semántico ya establecido por AE-2/AE-22: **"apariciones promedio por sorteo", nunca "porcentaje"** -expuesto como `apariciones_promedio` (float) y `apariciones_promedio_texto` (`.2f`), etiqueta de gráfica confirmada con HTTP real como "Apariciones promedio por sorteo". Se añade `_NOMBRES_MESES_ES` -mapeo interno de presentación exclusivamente, nunca usado en la identidad de caché ni en el cálculo, que siempre trabaja con el entero `1..12`.

**Preservación bidireccional mes↔corte, confirmada con HTTP real -no se repitió el defecto inicial descubierto en AE-22:** el formulario de corte conserva `mes`; el selector de mes conserva `hasta_numero_sorteo`; "Histórico completo" elimina el corte y conserva el mes; existe un único enlace que propaga `mes`; las demás páginas de ColorLoto no reciben ni propagan el mes; la navegación común continúa propagando únicamente el corte. El campo oculto `mes` en el partial compartido se emite únicamente cuando el contexto de la ruta actual lo define (`mes is defined and mes is not none`), mismo mecanismo exacto que `anio`, ambos bloques independientes -verificado que ninguna página real define los dos simultáneamente (confirmado por AST real sobre las 32 funciones de router). El comportamiento año↔corte de AE-22 permanece exactamente intacto.

**Formulario y gráfica:** selector desplegable con los doce meses en español, ningún mes preseleccionado por defecto; confirmado con HTTP real: canvas presente con mes y datos, seis colores y seis promedios reportados, al menos un promedio mayor que cero; canvas ausente sin mes seleccionado, sin `new Chart(`; mensaje de ausencia de sorteos presente cuando corresponde. Conteo estructural: **32 templates/páginas estadísticos, 28 con canvas** -sexto incremento de canvas desde AE-14.

**Reconciliación de pruebas -pytest real en Windows:** `47 passed in 2.76s` para las pruebas específicas de AE-23. Tests focalizados (4 archivos): `1972 passed in 5.36s`. Suite completa: `2788 passed in 9.23s`. Reconciliación: `2741 + 47 = 2788`; focalizados `1925 + 47 = 1972`. Distribución: `+15` (`test_calcular_y_persistir_estadistica.py`), `+28` (`test_generalizacion_juegos.py`), `+4` (`test_estadistica_repository.py`), `+0` en `test_corte_temporal_navegacion.py`. Cero usos inválidos de `list.count()`. Exactamente `13` entradas modificadas antes y después de las pruebas. `git diff --check` en `0`.

**Aislamiento de rutas confirmado con HTTP real:** Baloto, Baloto Revancha, MiLoto y un sufijo inexistente de ColorLoto -cuatro respuestas `404` correctas.

**Revisión visual humana**, cita literal del usuario: "no vi errores en las paginas".

**PostgreSQL real:** las cuatro comprobaciones de integridad del histórico (balotas distintas de seis, números fuera de 1–7, colores de otro juego, colores fuera de vigencia) devolvieron `0 rows`. Se observaron cinco cachés vigentes y legítimas: mes 1 histórico completo (18 sorteos), mes 1 con corte 1 (0 sorteos), mes 1 con corte 100 (9 sorteos), mes 5 histórico completo (17 sorteos) y mes 12 histórico completo (18 sorteos) -las de mayo y diciembre creadas legítimamente durante la revisión manual del selector, no residuos. Todas mantienen parámetros exactos (`mes`, `politica_universo_colores`), seis filas cada una, sin anomalías. Unicidad por `(mes, hasta_numero_sorteo)`: todas en `1`. Comparación SQL independiente contra las cinco cachés: `0 rows`, cero diferencias. Invariante de balotas físicas (`SUM(apariciones) = 6 × total_sorteos`): `0 rows` de anomalías. **Agregación mensual entre años confirmada directamente con PostgreSQL real:** enero de 2025 aportó 9 sorteos (54 balotas) y enero de 2026 aportó otros 9 sorteos (54 balotas), totalizando 18 sorteos y 108 balotas -exactamente `108 = 18 × 6`- demostrando con datos reales que `mes=1` agrega enero de varios años, nunca un año-mes aislado.

**Limpieza final real:** procesos Uvicorn identificados y detenidos (PID raíz `21260`, hijo `26252`, `taskkill /T /F` terminó el árbol completo incluido el proceso `19588`, cero procesos escuchando en el puerto 8000 tras detenerlos); único residuo encontrado `backend/storage/logs/sync.log` (14493 bytes), enviado a la papelera; verificación final `DirectoriosCache=0`, `ArchivosResiduales=0`, `ArchivosRuntimeStorage=0`, `git diff --check` exit code `0`. Árbol con exactamente los 13 archivos esperados de AE-23; los seis motores con hash idéntico. Toda esta evidencia (pytest, HTTP, PostgreSQL, revisión visual) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **ColorLoto tiene ahora veintitrés visualizaciones validadas**; navegación numérica (9/9/8) intacta; la siguiente etapa (AE-24) continúa pendiente de definición y no fue implementada. `calcular_distribucion_conteo_color`, la frecuencia de colores por día de semana, las frecuencias temporales de pares número-color y las comparaciones por ventana siguen pendientes de decisión de producto. Machine Learning (Fase 3) todavía no ha comenzado. Fase 5 continúa parcial. Ninguno de estos números es un total permanente.

**Checkpoint validado (Etapa AE-24, vigesimocuarta visualización web de ColorLoto -frecuencia de colores por día de semana, trigesimotercera visualización global):** reutiliza exactamente el precedente validado por AE-22 (selector de año) y AE-23 (selector de mes) para un selector de día de la semana -decisión de producto explícita, selector desplegable con los siete días en español, sin valor por defecto. **Auditoría obligatoria del motor, completada con evidencia real antes de escribir código:** `calcular_frecuencia_colores_por_dia_semana` existe en `motor/frecuencia_temporal.py:170`, firma `(resultados, colores_vigentes, dia_semana: str, hasta_numero_sorteo=None) -> list[FrecuenciaObservada]`, exactamente 3 argumentos obligatorios. **Hallazgo central de la auditoría:** el dominio real de `dia_semana` **no es un entero `0..6` ni `1..7`** -es un conjunto de **strings literales en español, minúsculas, sin tildes** (`lunes`, `martes`, `miercoles`, `jueves`, `viernes`, `sabado`, `domingo`, confirmado por lectura directa de `_DIAS_SEMANA_VALIDOS`), el mismo dominio exacto ya almacenado en `ResultadoColorLoto.dia_semana` (poblado una única vez, al registrar o editar un sorteo, mediante `DIAS_SEMANA_ES[fecha.weekday()]` en `registrar_sorteo.py`/`editar_sorteo.py` -`lunes` corresponde a `weekday()==0`, `domingo` a `weekday()==6`, confirmado por ejecución real). El motor de esta etapa **nunca** invoca `weekday()` -solo compara el string ya persistido por igualdad exacta (`_filtrar_por_dia_semana`, `r.dia_semana == dia_semana`). La **presentación visual** usa tildes correctas mediante `_NOMBRES_DIAS_SEMANA_ES` -"Miércoles" y "Sábado" en pantalla, nunca en la identidad ni en el cálculo, que siempre trabajan con el string crudo sin tilde. Conecta `frecuencia_colores_por_dia_semana_colorloto` en `/estadisticas/colorloto/frecuencia-colores-por-dia-semana`. Sin ninguna ruta genérica equivalente. El grupo de rutas ColorLoto sin colisión pasa de dieciséis a **diecisiete**; el grupo con colisión permanece en siete.

**Caracterización empírica real del motor, ejecutada antes de implementar:** mismo día combinado entre meses/años distintos, exclusión correcta de otro día, balotas físicas, histórico vacío y día válido sin sorteos (ambos devuelven las 6 filas en cero), límites del dominio (`lunes` y `domingo` aceptados), rechazos reales fuera de dominio, determinismo y no mutación -todos confirmados por ejecución real directa del motor, además de los 7 tests de motor ya existentes (`TestFrecuenciaColoresTemporal`).

**Selector sin valor predeterminado:** sin `dia_semana`, la ruta responde `200` mostrando únicamente el formulario, sin gráfica, sin ejecutar el orquestador, sin invocar el motor, sin consultar ni persistir ninguna caché -confirmado por AST real sobre la función del router (bloque `if dia_semana is None` con cero llamadas a `.ejecutar`) y reconfirmado con HTTP real por el usuario. Nunca se elige automáticamente el día actual -cualquier valor por defecto sería arbitrario, decisión de producto explícita. Los siete días válidos responden `200`, con la opción correcta seleccionada y la gráfica presente en los siete casos -confirmado con HTTP real. Con `dia_semana` fuera del dominio real, `Literal[...]` produce `422` nativo de FastAPI antes de que el handler se ejecute -sin necesidad de `ge`/`le`, que solo aplican a tipos numéricos; confirmado con HTTP real para `dia_semana=festivo`, `dia_semana=Lunes` (mayúscula), `dia_semana=miércoles` (con tilde) y `dia_semana=1` (numérico), además de los tres cortes inválidos (`0`, negativo, no numérico) -siete respuestas `422` correctas, cero fallos. Con un día válido sin sorteos, la respuesta sigue siendo `200` -universo completo de colores en cero, nunca un `404`; confirmado con HTTP real: con corte `1`, jueves tuvo datos mientras los otros seis días mostraron el estado sin sorteos.

**Misma justificación exacta de AE-22/AE-23 para leer `parametros["dia_semana"]`:** confirmado por lectura directa de `ejecutar()` -`receta.calcular(historico, parametros_metrica)` es el único canal por el que el día elegido por el usuario puede llegar hasta la receta. La receta lee **únicamente** `parametros["dia_semana"]` -confirmado por AST real. Identidad `{"dia_semana": <string>, "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"}` -solo existe cuando hay día seleccionado; `dia_semana` cambia matemáticamente el resultado, por lo que forma parte de la identidad. `hasta_numero_sorteo` permanece en su propia columna, nunca en la identidad. Reutiliza `_validar_historico_colorloto_consistente` y `_codigos_colores_vigentes_en_referencia` (protegidos, sin cambios) -misma validación defensiva antes del motor ya usada 22 veces; caracterización empírica confirmada con motor espiado: número fuera de rango, cantidad de balotas incorrecta y color inválido son interceptados antes del motor, motor nunca invocado, caché nunca persistida. Llamada al motor con tres argumentos posicionales y cero kwargs, nunca `hasta_numero_sorteo`.

**Reutilización de `_serializar_frecuencia_observada` (protegida) sin ningún cambio:** mismo dataclass `FrecuenciaObservada` ya usado por AE-2, AE-22 y AE-23. Semántica preservada exactamente: balotas físicas contadas individualmente sin deduplicar por sorteo, denominador = sorteos del día a través de todos los meses y años, universo = colores vigentes ∪ observados, día vacío devuelve las 6 filas en cero. VM sigue el mismo criterio semántico ya establecido por AE-2/AE-22/AE-23: **"Apariciones promedio por sorteo", nunca "porcentaje"** -expuesto como `apariciones_promedio` (float) y `apariciones_promedio_texto` (`.2f`), etiqueta de gráfica confirmada con HTTP real. Se añade `_NOMBRES_DIAS_SEMANA_ES` -mapeo interno de presentación exclusivamente, nunca usado en la identidad de caché ni en el cálculo; correspondencia exacta con `_DIAS_SEMANA_VALIDOS` confirmada por comparación directa de conjuntos.

**Preservación bidireccional día↔corte, confirmada con HTTP real -no se repitió el defecto inicial descubierto en AE-22:** el formulario de día conserva `hasta_numero_sorteo`; el formulario compartido de corte conserva `dia_semana`; en los siete escenarios con corte se conservaron correctamente `dia_semana` y `hasta_numero_sorteo` simultáneamente. Las demás 32 páginas no reciben ni propagan `dia_semana`; los comportamientos año↔corte de AE-22 y mes↔corte de AE-23 permanecen exactamente intactos.

**Formulario y gráfica:** selector desplegable con los siete días en español, ningún día preseleccionado por defecto; confirmado con HTTP real: canvas presente en los siete días válidos, ausente sin selector. Conteo estructural: **33 templates/páginas estadísticos, 29 con canvas** -séptimo incremento de canvas desde AE-14.

**Reconciliación de pruebas -pytest real en Windows:** `51 passed in 4.34s` para las pruebas específicas de AE-24. Tests focalizados (4 archivos): `2023 passed in 7.87s`. Suite completa: `2839 passed in 18.82s`. Reconciliación: `2788 + 51 = 2839`; focalizados `1972 + 51 = 2023`, distribuidos en `+16`/`+30`/`+5`/`+0`. Cero usos inválidos de `list.count()`. `git diff --check` en `0`. Exactamente `13` entradas modificadas.

**Aislamiento de rutas confirmado con HTTP real:** un sufijo inexistente, Baloto, MiLoto y `/estadisticas/colorloto/frecuencia-superbalota` -cuatro respuestas `404` correctas.

**Revisión visual humana**, cita literal del usuario: "no vi errores en las paginas".

**PostgreSQL real:** las cuatro comprobaciones de integridad del histórico devolvieron `0 rows`. Distribución independiente calculada desde `EXTRACT(ISODOW FROM s.fecha)`: `lunes` con `104` sorteos (2024-08-19 a 2026-08-10), `jueves` con `105` sorteos (2024-08-15 a 2026-08-13), sin otros días presentes en el histórico real -confirmando que el análisis agrega correctamente el mismo día a través de meses/años reales. Se observaron **15 cachés vigentes** (siete históricos completos, siete con corte `1`, y lunes con corte `100`), todas con seis colores reportados y la identidad exacta `{"dia_semana": <valor>, "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"}`; unicidad por día/corte confirmada (las 15 combinaciones con cantidad `1`); parámetros incorrectos, estructura inválida e invariantes matemáticos inválidos: `0 rows` en los tres controles. Comparación SQL independiente (reconstruyendo cada resultado desde `sorteos`/`sorteo_color_numero`/`colores` con `EXTRACT(ISODOW FROM s.fecha)`, sin leer la caché) mediante `FULL JOIN`: `0 rows` de diferencia -confirmando balotas físicas, denominador por sorteos del día, y suma de promedios igual a `6` cuando existen sorteos (jueves histórico completo: 105 sorteos, 630 apariciones, suma de promedios `6.000000000`; lunes con corte `100`: 50 sorteos, 300 apariciones, suma `6.000000000`) o `0` cuando no existen (martes, miércoles, viernes, sábado, domingo: `0` sorteos, suma `0.000000000`).

**Limpieza final real:** procesos Uvicorn identificados y detenidos (PID raíz `3244`, hijo `26052`, `taskkill /T /F` terminó el árbol completo incluido el proceso `19276`, cero procesos escuchando en el puerto 8000 tras detenerlos); único residuo encontrado `backend/storage/logs/sync.log` (14493 bytes), enviado a la papelera; verificación final `DirectoriosCache=0`, `ArchivosResiduales=0`, `ArchivosRuntimeStorage=0`, `git diff --check` exit code correcto. Árbol con exactamente los 13 archivos esperados de AE-24; los seis motores con hash idéntico. Toda esta evidencia (pytest, HTTP, PostgreSQL, revisión visual) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **ColorLoto tiene ahora veinticuatro visualizaciones validadas**; navegación numérica (9/9/8) intacta; la siguiente etapa (AE-25) continúa pendiente de definición y no fue implementada. `calcular_distribucion_conteo_color`, las frecuencias temporales de pares número-color y las comparaciones por ventana siguen pendientes de decisión de producto. Machine Learning (Fase 3) todavía no ha comenzado. Fase 5 continúa parcial. Ninguno de estos números es un total permanente.

**Checkpoint validado (Etapa AE-25, vigesimoquinta visualización web de ColorLoto -frecuencia de pares número-color por año, trigesimocuarta visualización global):** reutiliza exactamente el precedente de selector validado por AE-22 (año) sobre el PAR (número, color) como unidad atómica -mismo formato `valor=f"{numero}-{color}"` ya usado por `frecuencia_pares_colorloto` (AE-3), aplicado ahora restringido a un año. **Auditoría del motor, completada con evidencia real antes de escribir código:** `calcular_frecuencia_pares_numero_color_por_anio` existe en `motor/frecuencia_temporal.py:181` (ruta real -no `backend/app/motor/`, como sugería el prompt inicial; discrepancia menor de ruta, sin contradicción material), firma `(resultados, rango_min, rango_max, colores_vigentes, anio, hasta_numero_sorteo=None) -> list[FrecuenciaObservada]`, exactamente 5 argumentos obligatorios, delega sin modificar en `calcular_frecuencia_pares_numero_color` (la misma función base de AE-3). **Hallazgo confirmado por ejecución real**: a diferencia de `mes`/`dia_semana` (que sí tienen validación interna `_validar_mes`/`_validar_dia_semana`), el motor **no** valida `anio` internamente -`0`, `-1` y `10000` no producen ninguna excepción propia, solo devuelven el universo completo en cero (ningún sorteo real coincide); el dominio real `1..9999` se aplica exclusivamente en la capa `Query` del router, mismo comportamiento exacto ya documentado en AE-22. El motor SÍ valida internamente el rango de los números (`_validar_rango`, `ValueError`), pero la validación defensiva de la receta (`_validar_historico_colorloto_consistente`) lo intercepta primero -confirmado con motor espiado, mismo comportamiento exacto de AE-20/AE-21.

**Caracterización empírica real del motor:** agregación de sorteos del mismo año, exclusión de un sorteo de otro año, año válido sin sorteos e histórico vacío (ambos devuelven las 42 filas del universo completo, `1..7 × 6 colores`, en cero), balotas físicas (el mismo par exacto repetido dentro de un sorteo cuenta cada vez, confirmado real: `apariciones=2` para un par repetido en un único sorteo), límites `1` y `9999` aceptados, determinismo y no mutación -todos confirmados por ejecución real directa del motor, además de los 7 tests de motor ya existentes (`TestFrecuenciaParesNumeroColorTemporal`, incluido `test_numero_fuera_de_rango_lanza_value_error` y `test_anti_fuga`), ejecutados y confirmados en verde.

**Selector sin valor predeterminado:** sin `anio`, la ruta responde `200` mostrando únicamente el formulario, sin ejecutar el orquestador, sin invocar el motor, sin consultar ni persistir ninguna caché -confirmado por AST real sobre la función del router (bloque `if anio is None` con cero llamadas a `.ejecutar`) y reconfirmado con HTTP real: sin `anio`, `200`, sin gráfica, sin cálculo automático. Con `anio` fuera de `1..9999`, `422` nativo de FastAPI -confirmado con HTTP real para `anio=0`, `anio=-1`, `anio=10000`, `anio=texto` y los tres cortes inválidos (`0`, `-1`, no numérico): siete respuestas `422` correctas, cero fallos. Con un año válido sin sorteos, la respuesta sigue siendo `200` -universo completo de 42 pares en cero, nunca un `404`; confirmado con HTTP real: `anio=2027` respondió `200` con las 42 filas, 7 etiquetas, 6 datasets, 0 sorteos y universo en cero.

**Identidad de caché con CUATRO claves -a diferencia de AE-22/AE-23/AE-24:** `{"anio": <entero>, "rango_min": juego.rango_min, "rango_max": juego.rango_max, "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"}`. Este motor SÍ construye su universo con el producto cartesiano `range(rango_min, rango_max+1) × colores_a_reportar` -confirmado por lectura directa de `calcular_frecuencia_pares_numero_color`- por lo que el rango es matemáticamente determinativo y forma parte de la identidad, mismo criterio ya demostrado por AE-20/AE-21; construido en el router desde `juego.rango_min`/`juego.rango_max` (la entidad real, nunca la constante privada `_RANGO_REAL_COLORLOTO`, inaccesible fuera del caso de uso). `cantidad_numeros` excluida de la identidad -el motor no la recibe, solo se usa para validación defensiva. La receta lee **únicamente** `parametros["anio"]` -confirmado por AST real. `hasta_numero_sorteo` permanece en su propia columna, nunca en la identidad. Reutiliza `_validar_historico_colorloto_consistente` y `_codigos_colores_vigentes_en_referencia` (protegidos, sin cambios) -misma validación defensiva antes del motor ya usada 23 veces; caracterización con motor espiado: número fuera de rango, cantidad de balotas incorrecta y color inválido son interceptados antes del motor, motor nunca invocado, caché nunca persistida. Llamada al motor con cinco argumentos posicionales y cero kwargs, nunca `hasta_numero_sorteo`.

**Reutilización de `_serializar_frecuencia_observada` y `_deserializar_par_numero_color` (ambos protegidos) sin ningún cambio:** mismo dataclass `FrecuenciaObservada` y mismo formato de par ya usados por AE-3/AE-6/AE-21. VM replica de forma mínima el patrón de presentación ya validado por `frecuencia_pares_colorloto_a_vm` (AE-3, sin modificar esa función): datasets AGRUPADOS por color, construidos dinámicamente a partir de los colores REALES presentes en el resultado -nunca seis códigos fijados a mano-, eje X con los números del rango real; confirmado con HTTP real: `anio=2024` produjo 7 etiquetas, 6 datasets, 7 valores por dataset. Mismo criterio semántico ya establecido: **"Apariciones promedio por sorteo", nunca "porcentaje"** -puede legítimamente superar 1.0 porque el mismo par exacto puede repetirse dentro de un sorteo.

**Preservación bidireccional año↔corte, reutilizando sin cambios el mecanismo ya validado por AE-22:** `control_corte_temporal.html` **no fue modificado** -el bloque `anio is defined and anio is not none` ya existente desde AE-22 cubre esta etapa automáticamente; confirmado con HTTP real: `anio=2024&hasta_numero_sorteo=100` preservó ambos valores simultáneamente y el enlace "Histórico completo" conservó `anio=2024`. Las demás 33 páginas no reciben ni propagan `anio` de esta etapa; los comportamientos año↔corte de AE-22, mes↔corte de AE-23 y día↔corte de AE-24 permanecen exactamente intactos. Aislamiento `404` confirmado con HTTP real para Baloto, Baloto Revancha, MiLoto y un sufijo inválido en ColorLoto -cuatro respuestas correctas, cero fallos.

**Formulario y gráfica:** control HTML numérico visible (`type="number"`, `min="1"`, `max="9999"`), campo oculto que conserva `hasta_numero_sorteo`. El `<canvas>` (exactamente 1 en el código fuente, con datasets dinámicos -uno por color realmente presente, con leyenda) solo se renderiza cuando existe una estadística calculada (año válido) -nunca en el estado sin año ni sin conexión; confirmado con HTTP real en los cuatro escenarios (sin año, año con datos, año sin sorteos, año con corte). Conteo estructural: **34 templates/páginas estadísticos, 30 con canvas** -octavo incremento de canvas desde AE-14.

**Reconciliación de pruebas -pytest real en Windows:** `49 passed in 4.24s` para las pruebas específicas de AE-25. Tests focalizados (4 archivos): `2072 passed in 7.62s`. Suite completa: `2888 passed in 15.94s`. Reconciliación: `2839 + 49 = 2888`; focalizados `2023 + 49 = 2072`, distribuidos en `+14`/`+30`/`+5`/`+0`. Cero usos inválidos de `list.count()`. Después de las pruebas continuaron exactamente los 12 archivos autorizados.

**Aplicación real del parche en Windows:** base `HEAD`/`origin/main`/tag `ae24-validado` en el commit `3b52afd312c21bdeeed004bc509c6a981fc5dfb3`, repositorio inicialmente limpio, rama `feature/ae25-frecuencia-pares-numero-color-por-anio-colorloto`; `git apply --check`, aplicación real, `git apply --reverse --check` y `git diff --check` en `0`; alcance exactamente los 12 archivos autorizados, sin diferencias; las advertencias de `git apply` fueron exclusivamente por CRLF.

**Revisión visual humana**, cita literal del usuario: "no vi errores en las paginas".

**PostgreSQL real:** contenedor `loteria-predictor-fase2-final-postgres-1` activo. Los ocho controles de integridad (balotas, rango, colores de otro juego, vigencia, duplicidad de cachés, identidad de parámetros, estructura/tipos/fórmula, invariantes de 42 pares/balotas físicas/suma de promedios) devolvieron `0 rows`. Se observaron exactamente **tres cachés vigentes**: año 2024 histórico completo (42 pares, 240 apariciones, 40 sorteos, suma de promedios `6.000`), año 2024 con corte 100 (mismos valores, `240=6×40`) y año 2027 histórico completo (42 pares, 0 apariciones, 0 sorteos, suma `0.0`) -cada una con la identidad exacta de cuatro claves, cambiando únicamente `anio` a `2027` en el tercer caso. Comparación SQL independiente (reconstruida desde las tablas relacionales, comparada mediante `FULL JOIN` par por par contra las tres cachés, con tolerancia `0.000000001` en presencia, apariciones, sorteos y promedio): `0 rows` de diferencia. En el primer intento de esa consulta, una variable de PowerShell (`$pgContainer`) no estaba definida y Docker reportó un contenedor inexistente -error exclusivo del comando de validación, corregido restableciendo la variable; la misma consulta repetida devolvió `0 rows`. Las cachés reales de PostgreSQL no fueron alteradas ni eliminadas al documentar este cierre.

**Limpieza final real:** Uvicorn (PID `11480`) detenido, sin listeners restantes en el puerto `8000`; `.pytest_cache` y `backend/storage/logs/sync.log` eliminados; `git diff --check` correcto; exactamente 12 archivos modificados, cero diferencias de alcance. Toda esta evidencia (pytest, aplicación del parche, HTTP, PostgreSQL, revisión visual, limpieza) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **ColorLoto tiene ahora veinticinco visualizaciones validadas**; navegación numérica (9/9/8) intacta; la siguiente etapa (AE-26) continúa pendiente de definición y no fue implementada. `calcular_distribucion_conteo_color`, las frecuencias temporales de pares número-color por mes/día de semana y las comparaciones por ventana siguen pendientes de decisión de producto. Machine Learning (Fase 3) todavía no ha comenzado. Fase 5 continúa parcial. Ninguno de estos números es un total permanente.

**Checkpoint validado (Etapa AE-26, vigesimosexta visualización web de ColorLoto -frecuencia de pares número-color por mes, trigesimoquinta visualización global):** reutiliza exactamente el precedente de identidad con rango validado por AE-25 (pares) combinado con el selector de mes ya validado por AE-23. **Auditoría del motor, completada con evidencia real antes de escribir código:** `calcular_frecuencia_pares_numero_color_por_mes` existe en `motor/frecuencia_temporal.py:192`, firma `(resultados, rango_min, rango_max, colores_vigentes, mes, hasta_numero_sorteo=None) -> list[FrecuenciaObservada]`, exactamente 5 argumentos obligatorios, delega sin modificar en `calcular_frecuencia_pares_numero_color` (la misma función base de AE-3/AE-25). **Hallazgo confirmado por ejecución real, a diferencia de AE-25 (`anio` sin validación interna)**: el motor de esta etapa **SÍ** valida `mes` internamente (`_validar_mes` dentro de `_filtrar_por_mes`, `ValueError` real confirmado con `0`/`-1`/`13`), independiente de la validación defensiva de la receta (que actúa sobre el histórico, no sobre `mes`). El dominio real `1..12` se aplica también, de forma redundante pero consistente con el precedente de AE-23, en la capa `Query` del router.

**Caracterización empírica real del motor:** agregación del mismo mes entre dos años distintos, exclusión de sorteos de otro mes, mes sin sorteos e histórico vacío (ambos devuelven las 42 filas del universo completo en cero), balotas físicas (el mismo par exacto repetido dentro de un sorteo cuenta cada vez, confirmado real: `apariciones=3` para un par con una repetición en un sorteo de marzo), límites `1` y `12` aceptados, tres rechazos reales fuera de dominio (`0`, `-1`, `13`, los tres con `ValueError` real), `hasta_numero_sorteo` aplicado antes del filtro mensual (confirmado real: con corte, 2 sorteos de marzo; sin corte, 3), determinismo y no mutación -todos confirmados por ejecución real directa del motor, además de los 7 tests de motor ya existentes (`TestFrecuenciaParesNumeroColorTemporal`, incluido `test_por_mes_agrega_entre_anios`), ejecutados y confirmados en verde.

**Selector sin valor predeterminado:** sin `mes`, la ruta responde `200` mostrando únicamente el formulario, sin ejecutar el orquestador, sin invocar el motor, sin consultar ni persistir ninguna caché -confirmado por AST real sobre la función del router (bloque `if mes is None` con cero llamadas a `.ejecutar`) y reconfirmado con HTTP real: la petición sin mes dejó el conteo de cachés en `0 → 0`. Nunca se elige automáticamente el mes actual -decisión de producto explícita. Con `mes` fuera de `1..12`, `422` nativo de FastAPI -confirmado con HTTP real para `mes=0`, `mes=-1`, `mes=13`, `mes=texto` y los tres cortes inválidos (`0`, `-1`, no numérico): siete casos, cero fallos. Con un mes válido sin sorteos en el corte elegido, la respuesta sigue siendo `200` -universo completo de 42 pares en cero, nunca un `404`; confirmado con HTTP real: enero (`mes=1`) con corte `1` produjo las 42 filas en cero, `totalSorteos=0`, frente a `totalSorteos=18` en el histórico completo de enero.

**Identidad de caché con CUATRO claves -mismo criterio de AE-25 (no AE-22/AE-23/AE-24):** `{"mes": <entero>, "rango_min": juego.rango_min, "rango_max": juego.rango_max, "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"}`. Este motor SÍ construye su universo con el producto cartesiano `range(rango_min, rango_max+1) × colores_a_reportar` -confirmado por lectura directa de `calcular_frecuencia_pares_numero_color`- por lo que el rango es matemáticamente determinativo y forma parte de la identidad; construido en el router desde `juego.rango_min`/`juego.rango_max` (la entidad real, nunca la constante privada `_RANGO_REAL_COLORLOTO`, inaccesible fuera del caso de uso); confirmado por test real que el orden de las claves del diccionario no afecta la comparación de identidad, y por las tres cachés reales de PostgreSQL, todas con exactamente `{"mes": 1, "rango_max": 7, "rango_min": 1, "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"}`. `cantidad_numeros` excluida de la identidad -el motor no la recibe, solo se usa para validación defensiva. La receta lee **únicamente** `parametros["mes"]` -confirmado por AST real. `hasta_numero_sorteo` permanece en su propia columna, nunca en la identidad. Reutiliza `_validar_historico_colorloto_consistente` y `_codigos_colores_vigentes_en_referencia` (protegidos, sin cambios) -misma validación defensiva antes del motor ya usada 25 veces; caracterización con motor espiado: número fuera de rango, cantidad de balotas incorrecta y color inválido son interceptados antes del motor, motor nunca invocado, caché nunca persistida. Llamada al motor con cinco argumentos posicionales y cero kwargs, nunca `hasta_numero_sorteo`.

**Reutilización de `_serializar_frecuencia_observada` y `_deserializar_par_numero_color` (ambos protegidos) sin ningún cambio:** mismo dataclass `FrecuenciaObservada` y mismo formato de par ya usados por AE-3/AE-6/AE-21/AE-25. VM replica de forma mínima el patrón de presentación ya validado por `frecuencia_pares_numero_color_por_anio_colorloto_a_vm` (AE-25, sin modificar esa función), combinado con `_NOMBRES_MESES_ES` de AE-23 para la presentación: datasets AGRUPADOS por color, construidos dinámicamente a partir de los colores REALES presentes en el resultado -nunca seis códigos fijados a mano-, eje X con los números del rango real; confirmado con HTTP real: `mes=1` produjo 42 filas, 7 etiquetas, 6 datasets, 7 valores por dataset. Mismo criterio semántico ya establecido: **"Apariciones promedio por sorteo", nunca "porcentaje"** -puede legítimamente superar 1.0 porque el mismo par exacto puede repetirse dentro de un sorteo.

**Preservación bidireccional mes↔corte, reutilizando sin cambios el mecanismo ya validado por AE-23:** `control_corte_temporal.html` **no fue modificado** -el bloque `mes is defined and mes is not none` ya existente desde AE-23 cubre esta etapa automáticamente, confirmado con renderizado Jinja2 real (hash idéntico antes/después) y con HTTP real: `mes=1&hasta_numero_sorteo=100` conservó ambos valores simultáneamente y el enlace "Histórico completo" conservó el mes. Las demás 34 páginas no reciben ni propagan `mes` de esta etapa; los comportamientos año↔corte de AE-22, mes↔corte de AE-23, día↔corte de AE-24 y año↔corte de AE-25 permanecen exactamente intactos. Aislamiento `404` confirmado con HTTP real para Baloto, Baloto Revancha, MiLoto y un sufijo inexistente -cuatro respuestas correctas, cero fallos.

**Formulario y gráfica:** selector desplegable con los doce meses en español, opción inicial sin valor, ningún mes preseleccionado por defecto -confirmado por renderizado real de Jinja2 que el mes recibido queda correctamente marcado como `selected` (verificado dentro del bloque `<select>...</select>`). El `<canvas>` (exactamente 1 en el código fuente, con datasets dinámicos -uno por color realmente presente, con leyenda) solo se renderiza cuando existe una estadística calculada (mes válido) -nunca en el estado sin mes ni sin conexión, confirmado por renderizado real de Jinja2 en los cinco estados y reconfirmado con HTTP real en los cuatro escenarios (sin mes, mes con datos, mes sin sorteos en el corte, mes con corte). Conteo estructural: **35 templates/páginas estadísticos, 31 con canvas** -noveno incremento de canvas desde AE-14.

**Reconciliación de pruebas -pytest real en Windows:** `57 passed` para las pruebas específicas de AE-26. Tests focalizados (4 archivos): `2129 passed`. Suite completa: `2945 passed`. Reconciliación: `2888 + 57 = 2945`; focalizados `2072 + 57 = 2129`. Cero usos inválidos de `list.count()`. Después de las pruebas continuaron exactamente los 12 archivos autorizados, y `control_corte_temporal.html` permaneció sin cambios.

**Aplicación real del parche en Windows:** rama activa `feature/ae26-frecuencia-pares-numero-color-por-mes-colorloto`; `git diff --check` correcto; exactamente 12 archivos modificados, cero diferencias de alcance.

**Revisión visual humana**, cita literal del usuario: "no vi errores en las paginas".

**PostgreSQL real:** los cuatro controles de integridad del histórico (balotas distintas de seis, números fuera de rango, colores de otro juego, colores fuera de vigencia) devolvieron `0` incidencias. Escenarios elegidos dinámicamente desde los datos reales: enero (`mes=1`) con 18 sorteos históricos; con corte `100`, 9 sorteos; con corte `1`, 0 sorteos. Se observaron exactamente **tres cachés vigentes** (`mes=1` sin corte, con corte `1` y con corte `100`, las tres con 42 filas e identidad idéntica). Los siete controles estructurales de caché (duplicadas, parámetros inválidos, resultados sin 42 pares, filas con contrato inválido, totales de sorteos inconsistentes, sumas de balotas incorrectas, promedios incorrectos) devolvieron `0` incidencias -una primera consulta auxiliar de esta revisión falló por usar la función inexistente `jsonb_object_length()`, corregida para usar `jsonb_object_keys()`, error exclusivo del comando de validación, no de AE-26 ni de la aplicación. Comparación SQL independiente (reconstruyendo pares, apariciones, totales y promedios desde las tablas relacionales) mediante `FULL JOIN` contra las tres cachés: `(0 rows)`, exit `0` -sin diferencias de pares, apariciones, totales ni promedios.

**Limpieza final real:** Uvicorn detenido, puerto 8000 sin listeners; `.pytest_cache`, `sync.log` y los logs temporales de Uvicorn eliminados; rama activa `feature/ae26-frecuencia-pares-numero-color-por-mes-colorloto`; `git diff --check` correcto; 12 archivos modificados, 0 diferencias de alcance. Toda esta evidencia (pytest, HTTP, PostgreSQL, revisión visual, limpieza) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **ColorLoto tiene ahora veintiséis visualizaciones validadas**; navegación numérica (9/9/8) intacta; la siguiente etapa (AE-27) continúa pendiente de definición y no fue implementada. `calcular_distribucion_conteo_color`, la frecuencia temporal de pares número-color por día de semana y las comparaciones por ventana siguen pendientes de decisión de producto. Machine Learning (Fase 3) todavía no ha comenzado. Fase 5 continúa parcial. Ninguno de estos números es un total permanente.

**Checkpoint validado (Etapa AE-27, vigesimoséptima visualización web de ColorLoto -frecuencia de pares número-color por día de semana, trigesimosexta visualización global):** reutiliza exactamente el precedente de identidad con rango validado por AE-25/AE-26 (pares) combinado con el selector de día de la semana ya validado por AE-24. **Auditoría del motor, completada con evidencia real antes de escribir código:** `calcular_frecuencia_pares_numero_color_por_dia_semana` existe en `motor/frecuencia_temporal.py:201`, firma `(resultados, rango_min, rango_max, colores_vigentes, dia_semana, hasta_numero_sorteo=None) -> list[FrecuenciaObservada]`, exactamente 5 argumentos obligatorios, delega sin modificar en `calcular_frecuencia_pares_numero_color` (la misma función base de AE-3/AE-25/AE-26). **Hallazgo confirmado por ejecución real**: mismo dominio real ya usado por AE-24 -string literal en español, minúsculas, sin tildes (`lunes`, `martes`, `miercoles`, `jueves`, `viernes`, `sabado`, `domingo`, `_DIAS_SEMANA_VALIDOS`), NUNCA un entero. El motor de esta etapa SÍ valida `dia_semana` internamente (`_validar_dia_semana` dentro de `_filtrar_por_dia_semana`, `ValueError` real confirmado con `"Lunes"` mayúscula, `"miércoles"` con tilde y `"7"` numérico), mismo comportamiento exacto ya confirmado por AE-24 y por AE-26 con `mes` -independiente de la validación defensiva de la receta (que actúa sobre el histórico, no sobre `dia_semana`). El dominio real (los siete literales exactos) se aplica también, de forma redundante pero consistente con el precedente de AE-24, en la capa `Query` del router mediante `Literal[...]`. Sin contradicción material: se procedió directamente con la implementación.

**Caracterización empírica real del motor, ejecutada antes de implementar:** agregación del mismo día entre meses y años distintos (lunes de 2022-03 y 2023-06 agregados en un único subconjunto), exclusión de sorteos de otro día (martes excluido al filtrar por lunes), día sin sorteos e histórico vacío (ambos devuelven las 42 filas del universo completo en cero), balotas físicas (el mismo par exacto repetido dentro de un sorteo cuenta cada vez, confirmado real: `apariciones=3` para un par con una repetición en un sorteo de lunes), ambos límites del dominio (`lunes` y `domingo`) aceptados, tres rechazos reales fuera de dominio (`"Lunes"`, `"miércoles"`, `"7"`, los tres con `ValueError` real), `hasta_numero_sorteo` aplicado antes del filtro por día (confirmado real: con corte, 2 sorteos de lunes; sin corte, 3), determinismo y no mutación -todos confirmados por ejecución real directa del motor, además de los 7 tests de motor ya existentes (`TestFrecuenciaParesNumeroColorTemporal`, incluido `test_por_dia_semana`), ejecutados y confirmados en verde.

**Selector sin valor predeterminado:** sin `dia_semana`, la ruta responde `200` mostrando únicamente el formulario, sin ejecutar el orquestador, sin invocar el motor, sin consultar ni persistir ninguna caché -confirmado por AST real sobre la función del router (bloque `if dia_semana is None` con cero llamadas a `.ejecutar`). Nunca se elige automáticamente un día -decisión de producto explícita. Con `dia_semana` fuera del dominio real, `Literal[...]` produce `422` nativo de FastAPI antes de que el handler se ejecute -sin necesidad de `ge`/`le`, que solo aplican a tipos numéricos. Con un día válido sin sorteos, la respuesta sigue siendo `200` -universo completo de 42 pares en cero, nunca un `404`.

**Identidad de caché con CUATRO claves -mismo criterio de AE-25/AE-26 (no AE-22/AE-23/AE-24):** `{"dia_semana": <string>, "rango_min": juego.rango_min, "rango_max": juego.rango_max, "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"}`. Este motor SÍ construye su universo con el producto cartesiano `range(rango_min, rango_max+1) × colores_a_reportar` -confirmado por lectura directa de `calcular_frecuencia_pares_numero_color`- por lo que el rango es matemáticamente determinativo y forma parte de la identidad; construido en el router desde `juego.rango_min`/`juego.rango_max` (la entidad real, nunca la constante privada `_RANGO_REAL_COLORLOTO`, inaccesible fuera del caso de uso); confirmado por test real que el orden de las claves del diccionario no afecta la comparación de identidad. `cantidad_numeros` excluida de la identidad -el motor no la recibe, solo se usa para validación defensiva. La receta lee **únicamente** `parametros["dia_semana"]` -confirmado por AST real. `hasta_numero_sorteo` permanece en su propia columna, nunca en la identidad. Reutiliza `_validar_historico_colorloto_consistente` y `_codigos_colores_vigentes_en_referencia` (protegidos, sin cambios) -misma validación defensiva antes del motor ya usada 26 veces; caracterización con motor espiado: número fuera de rango, cantidad de balotas incorrecta y color inválido son interceptados antes del motor, motor nunca invocado, caché nunca persistida. Llamada al motor con cinco argumentos posicionales y cero kwargs, nunca `hasta_numero_sorteo`.

**Reutilización de `_serializar_frecuencia_observada`, `_deserializar_par_numero_color` y `_NOMBRES_DIAS_SEMANA_ES` (todos protegidos) sin ningún cambio:** mismo dataclass `FrecuenciaObservada` y mismo formato de par ya usados por AE-3/AE-6/AE-21/AE-25/AE-26; mapa de nombres de días en español ya introducido por AE-24, reutilizado tal cual para la presentación con tildes correctas -nunca usado en la identidad de caché ni en el cálculo, que siempre trabaja con el string crudo del dominio real. VM replica de forma mínima el patrón de presentación ya validado por `frecuencia_pares_numero_color_por_mes_colorloto_a_vm` (AE-26, sin modificar esa función): datasets AGRUPADOS por color, construidos dinámicamente a partir de los colores REALES presentes en el resultado -nunca seis códigos fijados a mano-, eje X con los números del rango real. Mismo criterio semántico ya establecido: **"Apariciones promedio por sorteo", nunca "porcentaje"** -puede legítimamente superar 1.0 porque el mismo par exacto puede repetirse dentro de un sorteo.

**Preservación bidireccional día↔corte, reutilizando sin cambios el mecanismo ya validado por AE-24:** `control_corte_temporal.html` **no fue modificado** -el bloque `dia_semana is defined and dia_semana is not none` ya existente desde AE-24 cubre esta etapa automáticamente, confirmado con renderizado Jinja2 real (hash idéntico antes/después, confirmado mediante diff completo del registro de hashes protegidos). Las demás 35 páginas no reciben ni propagan `dia_semana` de esta etapa; los comportamientos año↔corte de AE-22, mes↔corte de AE-23, día↔corte de AE-24, año↔corte de AE-25 y mes↔corte de AE-26 permanecen exactamente intactos, confirmados con pruebas de regresión explícitas para las cinco etapas anteriores. Aislamiento `404` confirmado por AST para Baloto, Baloto Revancha, MiLoto y un sufijo inexistente.

**Formulario y gráfica:** selector desplegable con los siete días en español, opción inicial sin valor, ningún día preseleccionado por defecto -confirmado por renderizado real de Jinja2 que el día recibido queda correctamente marcado como `selected` (verificado dentro del bloque `<select>...</select>`). El `<canvas>` (exactamente 1 en el código fuente, con datasets dinámicos -uno por color realmente presente, con leyenda) solo se renderiza cuando existe una estadística calculada (día válido) -nunca en el estado sin día ni sin conexión, confirmado por renderizado real de Jinja2 en los cinco estados requeridos (sin conexión, sin día, día con resultados, día sin resultados, día con corte temporal). Conteo estructural: **36 templates/páginas estadísticos, 32 con canvas** -décimo incremento de canvas desde AE-14.

`3007 passed` en la suite completa (`pytest -q` sin fallos, ejecutado realmente en este sandbox). Reconciliación: `2945 + 62 = 3007` en la suite completa, `2129 + 62 = 2191` en los cuatro archivos focalizados, distribuidos en `+18` (`test_calcular_y_persistir_estadistica.py`: `883→901`, incluidas pruebas de agregación entre meses/años, exclusión de otro día, par repetido físico e identidad independiente del orden de claves), `+38` (`test_generalizacion_juegos.py`: `901→939`, repartidos en 9 de ruta, 9 de VM, 7 de template y 13 de preservación bidireccional/regresión, incluidas regresiones explícitas para AE-22/AE-23/AE-24/AE-25/AE-26), `+6` (`test_estadistica_repository.py`: `305→311`, incluido el round-trip de 42 filas) y `+0` en `test_corte_temporal_navegacion.py` (`35→36` solo en la aserción, nombre heredado preservado). El número de pruebas no se fijó artificialmente: se derivó del contrato real. Conteo AST de tests confirmado independientemente del conteo de recolección de `pytest` (coinciden exactamente: `3007` en ambos). Cero coincidencias de `list.count("...", "...")` inválido en todo el proyecto. Round-trip JSON, determinismo y no mutación confirmados por ejecución real directa del motor.

**Reconciliación de pruebas -pytest real en Windows:** `17 passed` para las pruebas específicas de la migración; `62 passed` para las pruebas específicas funcionales de AE-27. Tests focalizados (4 archivos): `2191 passed`. Suite completa: `3024 passed`. `git diff --check`: exit `0`. Exactamente 15 archivos modificados/nuevos, cero diferencias frente a la lista autorizada. `control_corte_temporal.html` y las cinco migraciones históricas (`0001` a `0005`) permanecieron exactamente sin cambios.

**Estado real previo a la migración -PostgreSQL en Docker (contenedor `loteria-predictor-fase2-final-postgres-1`):** `alembic heads` mostró `0006 (head)` localmente mientras `alembic current` y la revisión física en PostgreSQL seguían en `0005`; longitud física de `estadisticas.tipo_estadistica`: `50`; longitud declarada por el modelo corregido: `100`; cachés existentes antes de migrar: `146`; longitud máxima almacenada antes de migrar: `50`; cero filas con identificador mayor de 50. Respaldo previo real: `loteria-predictor-antes-migracion-0006-20260906-011142.dump`, 401777 bytes, SHA-256 `4A7C010DA292BC2745013116751B72AA37D10FF04DA1175F3930D56E68F83A7A`.

**Migración real ejecutada por el usuario:** `alembic upgrade head` -registro real: `Running upgrade 0005 -> 0006, amplia tipo_estadistica de varchar(50) a varchar(100)`. Controles antes/después: revisión `0005 -> 0006`; longitud física `50 -> 100`; cantidad de cachés `146 -> 146` (sin pérdida); longitud máxima almacenada permaneció en `50`; checksum de la información almacenada permaneció exactamente en `84407e1553e11eb56e04d5c1ead4811d`; los cuatro índices protegidos (`ix_estadisticas_tipo`, `ix_estadisticas_juego_tipo_corte`, `uq_estadisticas_con_corte`, `uq_estadisticas_sin_corte`) permanecieron sin cambios. Estado final reconfirmado: cabeza local Alembic `0006`, revisión instalada en PostgreSQL `0006`, columna física `varchar(100)`, modelo con longitud `100`, respaldo presente con tamaño y hash exactos.

**HTTP real después de la corrección, con cachés AE-27 confirmadas en cero antes de repetir las solicitudes, escenarios elegidos dinámicamente desde PostgreSQL:** (1) sin selector: `200`, 0 filas/etiquetas/datasets, `totalSorteos=0`, sin crear caché; (2) jueves (día con datos): `200`, 42 filas, 7 etiquetas, 6 datasets, `totalSorteos=105`; (3) jueves con `hasta_numero_sorteo=100`: `200`, 42 filas, 7 etiquetas, 6 datasets, `totalSorteos=50`, selector y corte preservados en controles y enlaces; (4) domingo con `hasta_numero_sorteo=1` (sin datos para ese corte): `200`, 42 filas en cero, 7 etiquetas, 6 datasets, `totalSorteos=0`, mensaje de ausencia de datos presente. Se crearon exactamente 3 cachés válidas. **Cero HTTP 500, cero `StringDataRightTruncation`, cero `value too long for type`** -el defecto original quedó confirmado resuelto en un entorno real.

**Validaciones HTTP negativas y de aislamiento reales:** los siete casos inválidos (`Lunes` mayúscula, `miércoles` con tilde, `7` numérico, `festivo` desconocido, corte `0`, corte `-1`, corte no numérico) devolvieron `422`; los cuatro casos de aislamiento (Baloto, Baloto Revancha, MiLoto, ruta inexistente de ColorLoto) devolvieron `404`; los rechazos no crearon cachés (`3 -> 3`); cero errores 500. Revisión visual del usuario, cita literal: "no vi errores en las paginas".

**Integridad de las cachés y comparación SQL independiente:** los nueve controles estructurales sobre las tres cachés (cantidad distinta de 3, identificador incorrecto, duplicadas, parámetros inválidos, resultados sin 42 pares únicos, filas con contrato inválido, totales de sorteos inconsistentes, sumas de balotas incorrectas, frecuencias incorrectas) devolvieron `0` incidencias; el identificador completo de 54 caracteres quedó almacenado correctamente. Una consulta SQL independiente (recalculando el día desde `EXTRACT(ISODOW FROM s.fecha)`, reconstruyendo el universo de pares, contando balotas físicas y calculando frecuencias sin reutilizar el JSON de la caché) comparada contra las tres cachés devolvió `(0 rows)` con código de salida `0`.

**Limpieza final real:** Uvicorn detenido, puerto 8000 sin listener; rama activa `feature/ae27-frecuencia-pares-numero-color-por-dia-semana-colorloto`; `git diff --check` exit `0`; exactamente 15 archivos modificados/nuevos, 0 diferencias de alcance; Alembic local y PostgreSQL en `0006`; columna física y modelo en `100`; cachés AE-27 vigentes: `3`; respaldo reconfirmado con tamaño y hash exactos. Durante el bloque final de verificación apareció un mensaje de PowerShell porque `else` se interpretó como una instrucción interactiva separada -no fue un fallo del proyecto, del respaldo ni de la validación: la rama verdadera del `if` ya había definido el archivo y el hash porque el respaldo existía, y todos los controles posteriores, incluida la aserción final, pasaron correctamente, imprimiendo "Estado final corregido de AE-27 verificado correctamente."

Toda la evidencia de esta sección (pytest, migración real, HTTP, PostgreSQL, comparación SQL independiente, revisión visual, limpieza) fue producida y verificada por el usuario en su propio entorno de Windows con PostgreSQL en Docker, no por Claude. **Esta ejecución en este sandbox no dispone de PostgreSQL** (sin binario `psql`/`postgres`, sin servidor; el driver `psycopg` está instalado pero no hay ninguna base a la que conectarse) -las verificaciones propias de este sandbox se limitaron a: reconstrucción y aplicación real del parche corregido, ejecución real de `pytest` (17 + 62 + 2191 + 3024, todas en verde), inspección real de metadatos de SQLAlchemy (`EstadisticaORM.__table__.columns["tipo_estadistica"].type.length == 100`) y revisión estática real del código de la migración -nunca una ejecución real de `alembic upgrade`/`downgrade` contra PostgreSQL, nunca HTTP real, nunca revisión visual en navegador. Árbol final con exactamente 257 archivos, 176 Python, 6 migraciones -los 15 archivos autorizados modificados/creados (12 del alcance funcional original de AE-27 + `models.py`, `0006_amplia_tipo_estadistica.py` y el nuevo archivo de pruebas de esquema, los tres añadidos para corregir el defecto físico), 242 archivos anteriores sin cambios, incluido `control_corte_temporal.html` y las cinco migraciones históricas `0001` a `0005`, explícitamente **no** modificados (confirmado mediante diff completo del registro de hashes protegidos: 6 motores, `control_corte_temporal.html`, 5 migraciones históricas, 11 recetas, 8 VM y 5 rutas, todos idénticos antes/después). Con la migración real ejecutada y la validación HTTP/PostgreSQL real completada por el usuario sin ningún HTTP 500, **AE-27 queda validada.** **ColorLoto tiene ahora veintisiete visualizaciones validadas**; navegación numérica (9/9/8) intacta; la siguiente etapa (AE-28) continúa pendiente de definición y no fue implementada. `calcular_distribucion_conteo_color` y las comparaciones por ventana siguen pendientes de decisión de producto. Machine Learning (Fase 3) todavía no ha comenzado.

**Historia del defecto y corrección -el provisional original de AE-27 permanece invalidado, la corrección quedó validada:** la validación HTTP real del usuario en Windows/PostgreSQL, ejecutada sobre el parche provisional original (232400 bytes, SHA-256 `63ce3c1d...974ebb4f`), descubrió que **toda solicitud válida con selector fallaba con HTTP `500`** (`?dia_semana=jueves`, `?dia_semana=jueves&hasta_numero_sorteo=100`, `?dia_semana=domingo&hasta_numero_sorteo=1`), mientras la página sin selector seguía respondiendo `200` correctamente. Las tres solicitudes alcanzaban la receta, calculaban el resultado, y fallaban únicamente al persistir en `EstadisticaRepositorySQLAlchemy.guardar()` con `psycopg.errors.StringDataRightTruncation: value too long for type character varying(50)`. **Diagnóstico confirmado por auditoría real del esquema:** `estadisticas.tipo_estadistica` se declaró como `varchar(50)` desde la migración `0001_initial_schema.py` (línea 104) y en el modelo SQLAlchemy `EstadisticaORM` (`backend/app/infrastructure/db/models.py`, `String(50)`); el identificador real de AE-27, `frecuencia_pares_numero_color_por_dia_semana_colorloto`, mide **54 caracteres** -4 más de lo que la columna física admite. Auditoría del inventario completo (36 valores reales de `tipo_estadistica` en `_CATALOGO`): el segundo más largo, `intervalos_historicos_pares_numero_color_colorloto` (AE-21), mide exactamente 50 -el límite original ya no tenía ningún margen incluso antes de AE-27; ninguna otra declaración física del proyecto usa ese límite. **Ninguna prueba anterior detectaba esto** porque las pruebas de repositorio (`test_estadistica_repository.py`, `test_calcular_y_persistir_estadistica.py`) usan exclusivamente un repositorio en memoria sin restricción de longitud -el dominio físico de PostgreSQL nunca se comparó contra el catálogo real de identificadores en ninguna prueba, hasta esta corrección.

**Corrección implementada -migración aditiva, nunca reescritura del historial:** nueva migración Alembic `0006_amplia_tipo_estadistica.py` (`down_revision = "0005"`, la head real confirmada de AE-26; única head resultante del árbol de migraciones), que amplía `tipo_estadistica` de `varchar(50)` a **`varchar(100)`** mediante `ALTER COLUMN ... TYPE`. Capacidad elegida con evidencia, no arbitraria: dado el máximo real actual (54, incluido AE-27) y el candidato futuro más largo ya existente como función de motor sin conectar que sigue el patrón de nombres establecido (`comparar_frecuencia_pares_numero_color_por_ventana_colorloto`, 60 caracteres, sin `tipo_estadistica` asignado, pendiente de decisión de producto), `100` deja más de 40 caracteres de margen real sin ser un valor arbitrariamente grande. `models.py` se actualizó en paralelo a `String(100)`, confirmado por inspección real de metadatos de SQLAlchemy (`EstadisticaORM.__table__.columns["tipo_estadistica"].type.length == 100`, sin necesidad de conexión a PostgreSQL). Los cuatro índices que incluyen esta columna (`ix_estadisticas_tipo`, `ix_estadisticas_juego_tipo_corte`, `uq_estadisticas_con_corte`, `uq_estadisticas_sin_corte`, definidos en las migraciones `0001` y `0005`) permanecen exactamente intactos -ampliar la longitud de un `VARCHAR` en PostgreSQL nunca reescribe filas existentes ni invalida un índice btree ya construido; **las migraciones históricas `0001` a `0005` no fueron modificadas**, confirmado por diff completo. `downgrade()` reduce de vuelta a `varchar(50)`, pero primero verifica explícitamente que ninguna fila exceda 50 caracteres y aborta con un `RuntimeError` accionable en caso contrario, en vez de delegar en el mismo `StringDataRightTruncation` críptico que motivó esta corrección o arriesgar una truncación silenciosa.

**PostgreSQL no está disponible en este sandbox de cierre documental** (sin binario `psql`/`postgres`, sin servidor; el driver `psycopg` está instalado pero no hay ninguna base a la que conectarse) -en esta sesión, la validación de la corrección se repitió mediante inspección real de los metadatos de SQLAlchemy (columna, longitud, índice, nulabilidad) y por revisión estática real del código de la migración (AST/regex sobre `0006`, confirmando el encadenamiento correcto de revisiones y la ausencia de cambios a índices), no por una ejecución propia de la migración contra PostgreSQL. Cobertura de pruebas (`test_migracion_0006_amplia_tipo_estadistica.py`, 17 pruebas, reconfirmadas en verde en este sandbox): el modelo acepta el identificador exacto de AE-27 sin truncarlo; la columna es `varchar(100)`, sigue no nula e indexada; los 36 identificadores reales del catálogo caben en la nueva capacidad; el identificador de AE-27 mide exactamente 54 y **habría excedido el límite anterior de 50** (prueba que documenta el defecto real); `0006` es la única head del árbol de migraciones con `down_revision="0005"`; `upgrade()` amplía sin tocar índices; `downgrade()` verifica la precondición antes de reducir; las migraciones `0001` a `0005` permanecen sin cambios; los 36 contratos funcionales de `tipo_estadistica` permanecen intactos. Suite completa reconfirmada en este sandbox: `3024 passed` (`3007 + 17`), incluidas las 62 pruebas originales de AE-27 sin ningún cambio de comportamiento. Árbol final: 257 archivos, 176 Python, 6 migraciones -alcance ampliado de forma justificada más allá de los 12 archivos funcionales originales de AE-27 con exactamente `backend/app/infrastructure/db/models.py` (modificado), `backend/alembic/versions/0006_amplia_tipo_estadistica.py` (nuevo) y `backend/tests/unit/test_migracion_0006_amplia_tipo_estadistica.py` (nuevo, no existía un archivo de pruebas de esquema/migraciones previo). **La migración real (`alembic upgrade head`, `0005 -> 0006`) y la validación HTTP/PostgreSQL de cierre ya fueron ejecutadas realmente por el usuario en Windows con PostgreSQL en Docker -sin pérdida de las 146 cachés preexistentes, sin cambios en los cuatro índices protegidos, y sin ningún HTTP `500` en las solicitudes válidas con selector** (ver el bloque de evidencia real más arriba). Con esa evidencia real completada, **AE-27 queda validada.**

**Checkpoint validado (Etapa AE-28, vigesimooctava visualización web de ColorLoto -distribución del conteo por color, trigesimoséptima visualización global):** primera etapa cuya auditoría inicial se **detuvo** por una contradicción material real: `calcular_distribucion_conteo_color` exige `color_objetivo: str` obligatorio -un selector de dominio genuinamente **dinámico** (códigos de color reales de la base de datos), a diferencia de `anio`/`mes`/`dia_semana`, cuyos dominios son estáticos y validables con `Query`/`Literal` nativos de FastAPI. Autorizada explícitamente por el usuario a continuar con la **Opción A: selector explícito de color**, descartando expresamente la Opción B (receta agregadora en bucle sobre el motor, sin precedente en las 37 recetas conectadas).

**Auditoría real, completada antes de escribir código:** `calcular_distribucion_conteo_color` existe en `motor/distribuciones.py:254`, firma `(resultados, color_objetivo, cantidad_balotas, hasta_numero_sorteo=None) -> list[FrecuenciaObservada]`, exactamente 3 argumentos obligatorios, delega en `tabular_conteo_por_sorteo` (`motor/tabulacion.py`) sin modificar ninguno de los dos. **Hallazgo semántico central**, confirmado por ejecución real: `frecuencia_relativa` aquí es una partición REAL de los sorteos (las 7 filas suman `1.0` con sorteos) -genuinamente distinta del "apariciones promedio por sorteo" de AE-2/AE-22 a AE-27 (que puede superar 1.0 y nunca sumaría 1.0); la interfaz usa deliberadamente lenguaje de "porcentaje/proporción de sorteos", nunca la etiqueta de las seis etapas anteriores. Caracterización empírica real: universo completo `0..6` siempre presente incluso si el color nunca aparece; balotas físicas con multiplicidad real (3 balotas del mismo color en un sorteo → conteo 3, confirmado real); histórico vacío y color sin apariciones ambos devuelven las 7 categorías en cero; validación defensiva de integridad estructural (`_validar_historico_colorloto_consistente`, protegida, sin cambios) intercepta datos corruptos antes del motor, confirmado con motor espiado.

**Identidad de caché con DOS claves, no tres** -corrección justificada del contrato candidato original: `{"color_objetivo": <string>, "cantidad_balotas": <entero>}`. `cantidad_balotas` sí forma parte de la identidad (determina matemáticamente el universo `0..cantidad_balotas`, mismo criterio ya establecido por AE-20/AE-21/AE-25/AE-26/AE-27 para `rango_min`/`rango_max`), construida desde `juego.cantidad_numeros` (la entidad real). `politica_universo_colores` se **excluyó** deliberadamente, con evidencia: a diferencia de AE-2/AE-3/AE-5/AE-18/AE-21 a AE-27, el motor de esta etapa no recibe ni consume esa política en ningún punto de su firma ni de su cuerpo -nunca construye un universo multi-color; el resultado cacheado depende matemáticamente solo de `(historico.pares filtrado por corte, color_objetivo, cantidad_balotas)`, así que incluirla habría fragmentado la caché sin ningún efecto real sobre el resultado.

**Universo seleccionable dinámico, construido en el router**: vigentes en la fecha de referencia (`_codigos_colores_vigentes_en_referencia`, protegida, sin cambios) unión observados dentro del corte -mismo criterio de unión ya usado internamente por los motores de AE-2/AE-3/AE-5/AE-18/AE-21 a AE-27, aplicado aquí para construir la lista de opciones del selector (nunca el universo del motor, que solo recibe UN color). Esto exige que el router construya `historico` una vez para resolver el universo y validar/determinar el color efectivo antes de invocar al orquestador -que construye su propio `historico` internamente una segunda vez al ejecutar la receta-; costo arquitectónico honesto y documentado, específico de este primer selector con dominio dinámico. **Sin `color_objetivo` en la query string**: se elige automáticamente el primero en orden alfabético del universo seleccionable (mismo criterio de orden ya usado por `_codigos_colores_vigentes_en_referencia`, `sorted(...)`), regla determinista y explícita -nunca se inventa un color; universo vacío responde `200` con estado explícito, sin invocar el orquestador. **`color_objetivo` inválido** (sin normalizar mayúsculas, tildes ni alias): produce `ColorNoVigenteError` -excepción de dominio protegida, ya existente en `exceptions.py` y ya mapeada a HTTP `422` en `main.py`, nunca antes utilizada en el código real, reutilizada sin ningún cambio a esos dos archivos. El motor nunca se invoca y ninguna caché se persiste en este caso, confirmado por AST real.

**`control_corte_temporal.html` NO se incluye en esta página, deliberadamente**: su formulario, protegido y sin modificar, no tiene ningún mecanismo para conservar `color_objetivo` al enviarse (reemplaza toda la query string con sus propios campos, y solo conoce `anio`/`mes`/`dia_semana`) -usarlo tal cual habría violado el requisito de conservar el color al aplicar o retirar el corte. La plantilla nueva construye en su lugar su propio formulario combinado (corte + color) en un único `<form method="get">`, con el mismo campo `hasta_numero_sorteo`, la misma etiqueta y el mismo criterio de corte -mismo comportamiento funcional exacto, con ambos campos viajando juntos. Confirmado por hash idéntico que el partial compartido permanece exactamente sin cambios, y por pruebas de regresión explícitas que AE-22 a AE-27 siguen intactas.

**Formulario y gráfica:** selector desplegable construido dinámicamente desde el universo real (nunca una lista fija de colores, confirmado por barrido real del código de ruta/receta/VM/plantilla/pruebas). El `<canvas>` (exactamente 1) usa un único dataset -no datasets agrupados por color como AE-25/AE-26/AE-27, porque aquí el color es un escalar ya elegido, no una dimensión de la gráfica: eje X = conteo de apariciones del color por sorteo (`0..cantidad_balotas`), eje Y = porcentaje de sorteos. Conteo estructural: **37 templates/páginas estadísticos, 33 con canvas** -undécimo incremento de canvas desde AE-14; grupo de rutas sin colisión pasa de veinte a **veintiuno**.

`3085 passed` en la suite completa (`pytest -q` sin fallos, ejecutado realmente en este sandbox). Reconciliación: `3024 + 61 = 3085` en la suite completa, `2191 + 61 = 2252` en los cuatro archivos focalizados, distribuidos en `+20` (`test_calcular_y_persistir_estadistica.py`: `901→921`), `+35` (`test_generalizacion_juegos.py`: `939→974`, repartidos en 11 de ruta, 7 de VM, 9 de template y 8 de preservación/regresión, incluidas regresiones explícitas para AE-22 a AE-27), `+6` (`test_estadistica_repository.py`: `311→317`) y `+0` en `test_corte_temporal_navegacion.py` (`36→37` solo en la aserción). Un archivo adicional, fuera de los 12 originalmente autorizados, requirió un único ajuste numérico mecánico: `test_migracion_0006_amplia_tipo_estadistica.py` (creado en la corrección de AE-27, no en el contrato original de AE-28) declara su propia aserción `len(_CATALOGO) == 36` como parte de "contratos funcionales AE-22 a AE-27 intactos" -crecer el catálogo de forma legítima y autorizada la volvió obsoleta; se corrigió a `37` sin tocar ninguna otra línea de ese archivo. El número de pruebas no se fijó artificialmente: se derivó del contrato real. Conteo AST de tests confirmado independientemente del conteo de recolección de `pytest` (coinciden exactamente: `3085` en ambos). Cero coincidencias de `list.count("...", "...")` inválido en todo el proyecto.

**Reconciliación de pruebas -pytest real en Windows:** pruebas específicas de la corrección: `16 passed, 974 deselected`. Suite completa: `3101 passed` (`3085 + 16`). `git diff --check`: correcto. Exactamente 12 archivos modificados/nuevos. Aplicado sobre la rama `feature/ae28-distribucion-conteo-color-colorloto`; sin ningún commit todavía.

**PostgreSQL real** (contenedor `loteria-predictor-fase2-final-postgres-1`): revisión Alembic `0006`; `estadisticas.tipo_estadistica` en `varchar(100)`; 215 sorteos reales de ColorLoto; color usado dinámicamente en la validación: `BLANCO`; `cantidad_balotas`: `6`.

**HTTP real, todos los escenarios con el resultado exacto esperado:** ruta base `200`; corte vacío sin color `200`; caso exacto `color_objetivo=BLANCO&hasta_numero_sorteo=` `200`; solo color `200`; solo corte válido `200`; color y corte válidos `200`; corte `0` `422`; corte `-1` `422`; corte no numérico `422`; color en minúsculas `422`; color inexistente `422`; ruta de control AE-22 con corte vacío `422`; aislamiento Baloto `404`; aislamiento Baloto Revancha `404`; aislamiento MiLoto `404`.

**Revisión visual humana real**, cita literal del usuario: "no vi errores en la pagina".

**Auditoría real de caché**, con un corte antifuga real elegido dinámicamente (`numero_sorteo=108` sobre un histórico completo de 215 sorteos; histórico hasta el corte: 108 sorteos): exactamente dos identidades auditadas para `BLANCO` -una sin corte, una con corte `108`- `SinCorte=1`, `ConCorte=1`, `IdentidadCorrecta=True`, `ValoresCorrectos=True`, `TotalesCorrectos=True`, `FrecuenciasCorrectas=True`, `ValidezCorrecta=True`, `ResultadosDiferentes=True`. La identidad real contiene exactamente `{"color_objetivo": "BLANCO", "cantidad_balotas": 6}`, con `hasta_numero_sorteo` en su columna separada; las siete categorías `0..6` presentes; la suma de apariciones coincide con los sorteos analizados; la suma de `frecuencia_relativa` es `1.0`; la huella de ambas filas permaneció idéntica al repetir las solicitudes -cache hit real confirmado-; peticiones con color inválido no crearon caché (`FilasInvalidasEnCache=0`).

**Cierre real:** cero coincidencias de `Traceback`, `ERROR` o `Exception` en los logs; Uvicorn detenido correctamente; PostgreSQL continúa ejecutándose; la rama conserva exactamente los 12 archivos autorizados; sin commit ni push.

Durante la validación auxiliar ocurrieron dos incidentes exclusivamente en comandos de verificación, nunca en AE-28 ni en la aplicación: (1) se intentó usar la función inexistente `jsonb_object_length()`, el mismo incidente ya documentado en una etapa anterior; (2) un JSON construido por PowerShell perdió sus comillas dobles al atravesar PowerShell → Docker → `psql`. Ambos se corrigieron usando `jsonb_build_object()`, y la auditoría final pasó completamente -ninguno de los dos fue un defecto de AE-28.

Toda la evidencia de esta sección (pytest, PostgreSQL, HTTP, revisión visual, auditoría de caché, limpieza) fue producida y verificada por el usuario en su propio entorno de Windows, no por Claude. **Esta sesión no dispone de PostgreSQL ni de un navegador real** -las verificaciones propias de este sandbox se limitaron a: reconstrucción y aplicación real del parche corregido sobre el ZIP limpio de AE-27, ejecución real de `pytest` (`3101 passed`, `16 passed` específicas de la corrección) y revisión estática real del código, nunca una ejecución real de PostgreSQL, nunca HTTP real contra un servidor en ejecución, nunca revisión visual en navegador. Árbol de trabajo con exactamente 258 archivos, 176 Python -6 migraciones sin cambio, los 12 archivos del parche corregido de AE-28, 246 archivos anteriores sin cambios, incluido `control_corte_temporal.html`, `models.py` y las 6 migraciones, explícitamente **no** modificados (confirmado mediante diff completo del registro de hashes protegidos: 6 motores, `control_corte_temporal.html`, `models.py`, 6 migraciones, 36 recetas, 27 VM y 36 rutas, todos idénticos antes/después). Con la validación real completa del usuario en Windows, PostgreSQL y navegador, sin ningún HTTP 500 ni 422 inesperado, **AE-28 queda validada.** **ColorLoto tiene ahora veintiocho visualizaciones validadas**; la siguiente etapa (AE-29) continúa pendiente de definición y no fue implementada. Las comparaciones por ventana siguen pendientes de decisión de producto. Machine Learning (Fase 3) todavía no ha comenzado.

**Defecto real encontrado por validación visual en el navegador -el parche provisional original de AE-28 queda invalidado:** el usuario reprodujo en un navegador real que, al enviar el formulario combinado (color + corte) dejando el campo de corte vacío, la aplicación respondía `422` en vez de tratar el corte como ausente. Causa exacta: `hasta_numero_sorteo: int | None = Query(default=None, ge=1)` -la misma declaración nativa ya usada por las otras 36 rutas- NO trata una cadena vacía explícitamente presente en la query string como "parámetro ausente": Pydantic intenta convertir `""` a `int`, falla, y FastAPI responde `422` (`{"detail":[{"type":"int_parsing","loc":["query","hasta_numero_sorteo"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":""}]}`, reproducido real en este sandbox contra la aplicación real). Ninguna prueba anterior lo detectó porque todas construían la URL omitiendo el parámetro por completo cuando no había corte -nunca incluyéndolo vacío, que es exactamente lo que hace la serialización nativa de cualquier `<form method="get">` con un `<input name="hasta_numero_sorteo">`: el campo viaja SIEMPRE, incluso sin valor.

**Corrección aplicada, exclusivamente del lado del servidor, sin JavaScript:** nuevo `BeforeValidator` local (`_corte_vacio_a_none`, en `estadisticas.py`) que normaliza ÚNICAMENTE la cadena vacía exacta a `None` antes de que Pydantic intente el `int_parsing` -ningún otro valor se toca (`"0"`, `"-1"`, `"texto"`, `" "` con espacio pasan intactos a la validación normal, que los sigue rechazando con `422`). Aplicado mediante un nuevo alias de tipo local, `_CorteDesdeFormularioCombinado = Annotated[Annotated[int, Field(ge=1)] | None, BeforeValidator(_corte_vacio_a_none), Query()]`, usado ÚNICAMENTE en el parámetro `hasta_numero_sorteo` de la ruta de AE-28 -confirmado por AST real que las otras 36 rutas conservan exactamente su declaración `Query(default=None, ge=1)` nativa, sin ningún cambio de comportamiento. `int | None` se preserva en el router (la anotación subyacente sigue siendo esa unión, solo envuelta en metadatos `Annotated`); `ge=1` se preserva, aplicado exclusivamente sobre la rama `int`. No fue necesario retirar el campo del formulario con JavaScript -la solución del lado del servidor funcionó limpiamente con la versión real de FastAPI/Pydantic instalada en este sandbox (`fastapi 0.141.1`), confirmado por ejecución real.

**Regresión real, demostrada contra el estado defectuoso antes de corregir**: se revirtió temporalmente la declaración de la ruta al `Query` nativo original y se reejecutaron las pruebas nuevas -4 de ellas fallaron genuinamente, incluidas las dos más importantes (`test_reproduce_el_caso_exacto_reportado_color_blanco_corte_vacio`, que reproduce exactamente `?color_objetivo=BLANCO&hasta_numero_sorteo=` y exige `200`, y su variante sin color), confirmando que no son pruebas vacías. Restaurada la corrección, las 16 pruebas nuevas de esta corrección pasan (`test_corte_temporal_navegacion.py` no aparece en el parche corregido: su única línea afectada, un conteo de rutas con `Query` nativo, terminó siendo -por una coincidencia numérica real, no buscada- idéntica byte a byte a la versión de AE-27, confirmado con `diff` real contra una extracción limpia del ZIP). **Pruebas HTTP reales vía `TestClient`** (`httpx`/`fastapi.testclient`, disponibles en este sandbox aunque `httpx` no es una dependencia declarada del proyecto -las pruebas se omiten con `pytest.importorskip` si no está instalado, en vez de fallar la recolección) confirmaron los cuatro escenarios de envío real del formulario: cambiar solo el color con corte vacío, aplicar solo un corte, cambiar ambos simultáneamente, y "Histórico completo" (que nunca incluye el parámetro, ni siquiera vacío) -los cuatro responden `200`; los tres valores realmente inválidos (`0`, `-1`, `"texto"`) y una ruta anterior de control (AE-22) siguen respondiendo `422` exactamente como antes, confirmando que la corrección no se filtró a ninguna otra ruta. Suite completa tras la corrección: `3101 passed` (`3085 + 16`). **El parche provisional original de AE-28** (238556 bytes, SHA-256 `b300be59...40a623242`) **queda invalidado.** El parche corregido (254530 bytes, SHA-256 `57509be7...5c929dc83`) fue validado realmente por el usuario en Windows con PostgreSQL y navegador -ver el bloque de evidencia real más arriba.

**Corrección de mantenimiento global del corte vacío, previa a AE-29 -VALIDADA:** una auditoría previa de AE-29 descubrió, con HTTP real en este sandbox, que el defecto corregido en AE-28 (`hasta_numero_sorteo=""` → `422` en vez de tratarse como ausencia) era en realidad un patrón **latente en las 36 rutas restantes**, incluidas todas las que reutilizan `control_corte_temporal.html` -su campo de corte nunca tuvo `required`, así que cualquier usuario que pulsa "Aplicar corte" dejando el campo vacío dispara el mismo defecto en cualquier página. **AE-28 permanece validada y sin ningún cambio funcional** -no se tocó ninguna receta, VM, plantilla, motor, migración ni identidad de caché; el único cambio es la generalización, a las 37 rutas reales, del mismo mecanismo ya validado en AE-28 (`BeforeValidator` que normaliza EXCLUSIVAMENTE la cadena vacía a `None`, conservando `ge=1`). El alias de tipo, antes exclusivo del formulario combinado de AE-28 (`_CorteDesdeFormularioCombinado`), se renombró a `_CorteOpcional` -nombre general, ya no ligado a una sola etapa- y ahora es compartido por las 37 rutas reales; confirmado por AST real que las otras 36 declaraciones nativas `Query(default=None, ge=1)` desaparecieron por completo, y que ningún otro archivo (motores, `control_corte_temporal.html`, `models.py`, migraciones, recetas, VM, navegación) cambió -diff completo del registro de hashes protegidos idéntico antes/después. Contrato unificado confirmado con HTTP real, en este sandbox, sobre una muestra representativa de las distintas familias de rutas (numérica genérica, ColorLoto sin selector, ColorLoto con `anio`/`mes`/`dia_semana`): parámetro ausente y `""` responden ambos `200` (tratados de forma idéntica); `"0"`, negativo y texto no numérico siguen respondiendo `422` exactamente como antes; un corte válido sigue aceptado; `anio`/`mes`/`dia_semana` se siguen conservando correctamente junto con el corte. 14 pruebas nuevas -incluida una prueba estructural real sobre el AST completo que enumera las 37 rutas una por una, no solo dos representativas. Suite completa en este sandbox: `3115 passed` (`3101 + 14`).

**Validación real completa del usuario en Windows, PostgreSQL y navegador -evidencia atribuida al usuario, no ejecutada por Claude:** Python `3.14.6`, `pip check` limpio ("No broken requirements found."), imports reales confirmados (FastAPI, HTTPX, SQLAlchemy, Jinja2, pytest). Pruebas focalizadas (`test_corte_temporal_navegacion.py` + `test_generalizacion_juegos.py`): `1044 passed in 9.09s`. Suite completa: `3115 passed in 13.52s` -reconciliación `3101 + 14 = 3115`. Comprobación AST independiente sobre el router real: `RutasEncontradas: 37`, `ConteoCorrecto: True`, las 37 usando `_CorteOpcional`. **PostgreSQL real** (contenedor `loteria-predictor-fase2-final-postgres-1`, `pg_isready` aceptando conexiones, revisión Alembic `0006`, `estadisticas.tipo_estadistica` en `varchar(100)`) y **Uvicorn real en `127.0.0.1:8002`**: las 37 rutas reales enumeradas por AST (9 genéricas probadas con `baloto`, 28 de ColorLoto) -**37/37** sin `hasta_numero_sorteo` respondieron `200`; **37/37** con `?hasta_numero_sorteo=` respondieron `200`, **byte a byte idénticas** a la misma ruta sin el parámetro; **111/111** respuestas `422` para `0`/`-1`/`texto` en las 37 rutas; **6/6** cortes válidos representativos (Baloto genérico, ColorLoto sin selector, ColorLoto con `anio`, con `mes`, con `dia_semana`, y el formulario combinado de AE-28 con `color_objetivo`) respondieron `200`. Cero `Traceback`/`ERROR`/`Exception` en los logs de Uvicorn. **Caché PostgreSQL estable durante toda la validación**: `166` antes, `166` después de las 37 solicitudes sin parámetro, `166` después de las 37 con parámetro vacío, `166` después de las 111 inválidas, `166` después de los seis casos válidos -confirmando que el corte vacío comparte la identidad histórica ya existente, que los valores inválidos nunca alcanzan la caché, y que los seis casos válidos reutilizaron identidades ya existentes (no ausencia de uso de caché). **Revisión visual real** en cuatro páginas representativas con corte vacío (Baloto frecuencia de números; ColorLoto frecuencia de números; ColorLoto frecuencia de colores por año con `anio=2024`; AE-28 con `color_objetivo=BLANCO`), cita literal del usuario: "no vi errores en las paginas" -sin JSON `422` ni errores visuales. **Cierre real**: Uvicorn detenido correctamente (PID `9448`), puerto `8002` liberado, caché final `166`, PostgreSQL sigue ejecutándose, exactamente los seis archivos modificados, `0` diferencias de alcance, sin commit ni push.

Durante la preparación de esta validación hubo dos incidentes exclusivamente en comandos auxiliares del usuario, ninguno de la aplicación: un intento inicial de enumerar rutas vía `inspect.signature(r.endpoint)` sobre `app.routes` devolvió cero rutas (las firmas originales no quedaban expuestas de la forma asumida), corregido con la enumeración AST robusta ya descrita; y un intento inicial del extractor AST buscó por error el entorno virtual en `backend\.venv`, fallando en `Resolve-Path`, corregido apuntando al entorno real en `%LOCALAPPDATA%\loteria-predictor-ae28-venv`. Ninguno modificó archivos, hizo commit o invalidó evidencia posterior.

Con esta evidencia real completa del usuario -pytest, PostgreSQL, HTTP, caché, logs y revisión visual-, **la corrección de mantenimiento global del corte vacío queda VALIDADA.** AE-28 permanece validada e intacta funcionalmente. Este mantenimiento es un checkpoint independiente, previo a AE-29 -nunca renumerado como una etapa AE-N. AE-29 todavía no fue implementada; las comparaciones por ventana todavía no fueron implementadas. Machine Learning todavía no ha comenzado.

**Checkpoint validado (Etapa AE-29, vigesimonovena visualización web de ColorLoto -comparación de frecuencia de números por ventana reciente, trigesimoctava visualización global):** primera etapa que conecta `motor/recencia.py`, hasta ahora sin integración web -compara, para cada número del rango real (ignorando color), su frecuencia en TODO el histórico disponible contra su frecuencia en los últimos `ventana` sorteos reales de ese mismo histórico. Todas las decisiones de producto llegaron ya cerradas (ventanas `{5, 10, 20, 50}`, default `20`, etiqueta interna determinista, identidad de tres claves).

**Historia completa de los dos parches invalidados, conservada íntegramente:**

**Parche provisional original (262060 bytes, SHA-256 `bb95760d55a195fcb896e0d93b17f72ff5abc548e33e049571c2cca3e42afa54`) -INVALIDADO por auditoría independiente, dos defectos reales:** **Defecto A -decimales enteros aceptados, afirmación falsa:** la versión invalidada usaba `ventana: Annotated[int, AfterValidator(_validar_ventana), Query()]` y documentaba que "cualquier decimal produce 422" -afirmación **falsa**, confirmada real con `TestClient`: `ventana=5.0`, `ventana=5.00` y `ventana=20.0` respondían `200`, convertidos silenciosamente a `5`/`5`/`20`, porque `int` no es léxicamente estricto (Pydantic acepta primero como `float` y confirma que es un entero). **Defecto B -la receta ignoraba dos claves de su propia identidad:** la identidad de caché guardaba correctamente `{"ventana", "rango_min", "rango_max"}`, pero la receta leía únicamente `parametros["ventana"]` y rederivaba `rango_min`/`rango_max` desde la constante privada `_RANGO_REAL_COLORLOTO`, ignorando los dos valores reales de la identidad -confirmado real con histórico vacío y `{"rango_min": 2, "rango_max": 3}`, que producía incorrectamente las 7 filas de `1` a `7` en vez de únicamente `2` y `3`.

**Corrección real de ambos defectos**: `_validar_ventana` se convirtió en un `BeforeValidator` que compara la representación LÉXICA de la query string, ANTES de que Pydantic intente ninguna coacción de tipo, contra exactamente las cuatro cadenas canónicas `"5"`/`"10"`/`"20"`/`"50"` -cualquier otra representación de esos mismos números (`"5.0"`, `"05"`, `" 5"`, `"+5"`) se rechaza explícitamente con `422`. La receta pasó a leer exactamente `parametros["rango_min"]`/`parametros["rango_max"]`, usados tanto para la validación defensiva como para la llamada al motor -confirmado real con el mismo caso exacto de la auditoría, produciendo correctamente `["2", "3"]`; un motor espía confirmó que recibe exactamente el rango suministrado, nunca la constante `1..7`. Esta corrección es exclusiva de la receta nueva -ninguna receta anterior fue tocada. **El parche provisional original de AE-29 (262060 bytes, SHA-256 `bb95760d...3e42afa54`) queda invalidado.**

**Parche corregido intermedio (273900 bytes, SHA-256 `7f9989fc...19e9aa83f`) -también INVALIDADO, por seis afirmaciones desplazadas en una unidad:** una auditoría independiente adicional confirmó que la corrección funcional de ambos defectos anteriores era correcta (ventana léxica y rango consumido correctamente), pero encontró que, como AE-29 es el elemento número 38, seis docstrings que describían cuántos elementos **anteriores** existían decían incorrectamente "38" en vez de "37": una referencia a "38 VM anteriores" (`view_models.py`), tres a "38 recetas anteriores" (`calcular_y_persistir_estadistica.py`) y dos a "38 rutas anteriores" (`estadisticas.py`) -las seis frases envuelven línea dentro del docstring (word-wrap), por lo que una búsqueda de una sola línea no las encuentra todas. Ninguna afirmación sobre el total **posterior** a AE-29 (38 rutas, 38 recetas, 38 páginas) estaba mal -esas siempre fueron correctas. **Corrección real**: las seis frases exactas cambiadas de `38` a `37`, confirmado por AST real que las 37 recetas/VM/rutas anteriores permanecen byte a byte idénticas -solo los tres bloques docstring de AE-29 cambiaron; verificado por búsqueda lógica exacta: `38 VM anteriores: 0`, `37 VM anteriores: 1`, `38 recetas anteriores: 0`, `37 recetas anteriores: 3`, `38 rutas anteriores: 0`, `37 rutas anteriores: 2`. **El parche corregido intermedio de AE-29 (273900 bytes, SHA-256 `7f9989fc1395b8a026db459adb5190a05ed67c8bf104b7aadf0a93e19e9aa83f`) queda invalidado.** La comparación independiente entre ambos parches corregidos confirmó exactamente seis bytes de diferencia textual y ningún otro cambio -sin afectar ninguna prueba (`2376 passed`/`3192 passed` idénticos en ambos).

Motor real (`motor/recencia.py:124`) sin modificar, 5 argumentos posicionales/cero kwargs. `etiqueta_ventana` se sigue derivando siempre internamente (`f"ultimos_{ventana}"`), nunca aceptada desde HTTP ni parte de la identidad. Formulario combinado ventana + corte, sin incluir `control_corte_temporal.html` (mismo motivo que AE-28 con `color_objetivo`). Corrección textual menor en la plantilla: "Cada valor representa un promedio de apariciones por sorteo". Conteo estructural: 38 rutas/recetas/templates, 34 con canvas, 29 pestañas, grupo sin colisión 21→22; antes de AE-29 había 37 rutas/recetas/páginas.

**Reconciliación honesta de pruebas, sin forzar ninguna cifra**: se demostró que las pruebas nuevas fallan realmente contra cada código defectuoso reconstruido por separado -4 pruebas de receta y 5 pruebas HTTP contra el primer defecto. Suite completa final: **`3192 passed`** -reconciliado honestamente contra la base real: **`3115 + 77 = 3192`** (nunca se forzó `3184`, la cifra del primer parche defectuoso). AST y pytest coinciden exactamente en `3192`; focalizadas en `2376 passed`.

**Validación real completa del usuario en Windows, PostgreSQL y navegador -evidencia atribuida al usuario, no ejecutada por Claude:** Python `3.14.6`, `pip check` limpio. Auditoría AST/estructural real del usuario: 38 rutas GET, 38 rutas con corte, 38 con `_CorteOpcional`, 38 recetas, 38 plantillas, 34 con canvas, 29 pestañas, 6 migraciones, cabeza `0006`, `varchar(100)`, y los seis conteos textuales corregidos confirmados exactamente. Pruebas focalizadas reales: `2376 passed in 10.02s`. Suite completa real: `3192 passed in 12.59s`. Git permaneció con exactamente 13 archivos, sin commit ni push.

**PostgreSQL real** (contenedor `loteria-predictor-fase2-final-postgres-1`, `pg_isready` aceptando conexiones, revisión `0006`, `varchar(100)`): 215 sorteos reales de ColorLoto, número de sorteo máximo 215, corte medio empleado 108. Las pruebas HTTP de pytest, ejecutadas con PostgreSQL real disponible, crearon legítimamente cinco identidades antes del bloque HTTP manual (cuatro sin corte para las ventanas `5`/`10`/`20`/`50`, una con corte `100` y ventana `50`) -efecto esperado de pruebas reales contra PostgreSQL real, nunca contaminación.

**Contrato HTTP real**, Uvicorn en `127.0.0.1:8003`: las cuatro ventanas canónicas en `200`; la identidad existente `ventana=50&hasta_numero_sorteo=100` en `200`; la identidad nueva `ventana=20&hasta_numero_sorteo=108` en `200`, creada exactamente una vez; ausencia de corte y `hasta_numero_sorteo=` en `200` con HTML idéntico; **17 casos inválidos en `422`** (13 valores de ventana -incluidos `""`, `5.0`/`5.00`/`20.0`/`5.5`, `0`/`-5`/`7`/texto/`05`, espacio antes de `5`, `+5` y espacio solo codificado- más 4 cortes inválidos: `0`/`-1`/texto/espacio); las tres rutas equivalentes de Baloto/Revancha/MiLoto en `404`; los valores inválidos no alteraron la caché; las identidades existentes fueron cache hits con huella byte a byte estable; la caché total pasó de `171` a `172` únicamente por la identidad nueva con corte `108`; las identidades de AE-29 pasaron de cinco a seis; la repetición de la identidad nueva fue cache hit sin generar otra fila.

**Auditoría profunda real del JSON persistido** sobre las seis identidades reales: `IdentidadCorrecta`, `ResultadoExteriorCorrecto`, `ValoresCorrectos`, `EstructuraCorrecta`, `TotalesCorrectos`, `AparicionesCorrectas`, `FrecuenciasCorrectas`, `VentanasCorrectas` y `ValidezCorrecta`, todas `True`; caché final total `172`.

**Revisión visual real**, cita literal del usuario: "no vi errores en las paginas" -gráfica, tabla, cuatro opciones de ventana, combinación ventana+corte, enlace "Histórico completo", navegación y ausencia de porcentajes o errores visibles, todos comprobados. Cierre real: cero errores en logs de Uvicorn, Uvicorn detenido, puerto `8003` liberado, PostgreSQL en ejecución, árbol Git con exactamente 13 archivos, sin commit ni push.

**Dos incidentes reales, exclusivamente en comandos auxiliares de validación, ninguno de AE-29**: (1) el primer bloque operativo asumió incorrectamente que la caché debía comenzar en cero, deteniéndose de forma protectora antes de iniciar Uvicorn porque pytest ya había creado cinco identidades reales contra PostgreSQL -la validación se adaptó con huellas antes/después, sin borrar ninguna fila; (2) la primera consulta diagnóstica intentó usar `jsonb_object_length(parametros)`, inexistente en PostgreSQL -mismo incidente ya documentado en etapas anteriores-, corregida con `jsonb_build_object`, confirmando las cinco identidades.

**Evidencia propia del sandbox** (distinta de la evidencia real del usuario): aplicación limpia del parche final sobre la base (`--check`/aplicación real/`--reverse --check`/`diff --check`, todos exitosos), alcance de 13 archivos, árbol de 259 archivos/176 Python, mismos conteos estructurales confirmados de forma independiente, validación independiente 259/259 idénticos byte a byte, revisión de 34035 líneas sin espacios finales reales, sin BOM y sin finales de línea aislados.

Con esta evidencia real completa del usuario -pytest, PostgreSQL, HTTP, caché, auditoría profunda, revisión visual y cierre operativo-, **AE-29 queda validada.** AE-28 y el mantenimiento global del corte vacío permanecen validados e intactos funcionalmente. AE-30 no fue implementada; las comparaciones por ventana de colores y de pares número-color todavía no fueron implementadas. Machine Learning todavía no ha comenzado.

**Checkpoint validado (Etapa AE-30, trigésima visualización web de ColorLoto -comparación de frecuencia de colores por ventana reciente, trigesimonovena visualización global):** segunda etapa que conecta `motor/recencia.py`, tras AE-29 -compara, para cada color del universo real (vigentes en la fecha de referencia UNIÓN observados en el histórico ya filtrado), su frecuencia en TODO el histórico disponible contra su frecuencia en los últimos `ventana` sorteos reales de ese mismo histórico. Analiza el COLOR ignorando el número -sin selector individual de color, se comparan TODOS los colores del universo a la vez, a diferencia de AE-28 (`distribucion_conteo_color_colorloto`).

**Precedida por una auditoría previa que detectó y confirmó real un defecto material del motor candidato, corregido antes de conectar esta receta (Opción B autorizada por el usuario)**: `comparar_frecuencia_colores_por_ventana` y `comparar_frecuencia_pares_numero_color_por_ventana` construían universos divergentes entre la porción histórica y la reciente -causa raíz: `calcular_frecuencia_colores`/`calcular_frecuencia_pares_numero_color` construyen su universo dependiendo de qué se observa en la porción específica recibida, y como este motor llama a esas funciones DOS VECES con porciones distintas (`historico` completo vs. `reciente`, un subconjunto temporal siempre incluido en `historico`), un color observado en `historico` pero ausente de `colores_vigentes` Y ausente de `reciente` generaba universos divergentes -reproducido real antes de implementar: `KeyError: 'ROJO'` y `KeyError: '1-ROJO'`. **Corrección real aplicada a ambas funciones simétricamente**: se calcula un ÚNICO universo compartido -`colores_vigentes` unido con TODOS los colores observados en `historico`- y se pasa ESE MISMO universo, ordenado de forma determinista, a AMBAS llamadas; como `reciente ⊆ historico`, el universo que se calcularía internamente para la llamada reciente es siempre igual al compartido, garantizando universos idénticos por construcción, sin modificar `calcular_frecuencia_colores`, `calcular_frecuencia_pares_numero_color` ni `_construir_comparaciones`. Un color histórico ausente de la ventana reciente obtiene correctamente `apariciones=0` con el `total_sorteos` reciente real, nunca un error. **`comparar_frecuencia_pares_numero_color_por_ventana` fue corregida como mantenimiento del módulo dentro de esta misma etapa -su página web NO se conecta todavía**, sigue siendo trabajo de una etapa posterior explícita; se agregaron pruebas de regresión exactas para ambos `KeyError` directamente sobre el motor, demostradas primero fallando genuinamente contra el motor sin corregir (7 de 11 pruebas nuevas del motor) y luego pasando con la corrección restaurada. Reejecutadas las 32 pruebas preexistentes de `test_recencia.py` sin ningún cambio -ninguna cubría el defecto real, porque sus datasets siempre pasaban `colores_vigentes` como superconjunto de todo lo observado.

**Historia completa de los parches de AE-30, conservada íntegramente:** el **parche provisional original** (300235 bytes, SHA-256 `1cfd0c01db5fce2400620f2501cb4e58cceab3ef9db5d28f594c4541192e7472`) implementaba correctamente toda la funcionalidad anterior -incluida la corrección del motor-, pero **quedó INVALIDADO** por tres afirmaciones textuales desplazadas en una unidad: sus docstrings decían que existían "39 VM anteriores" y "39 recetas anteriores" a AE-30, cuando en realidad, al ser AE-30 el elemento número 39, existían exactamente **38** elementos anteriores -mismo patrón de error ya corregido antes para AE-29. El **parche corregido** (300345 bytes, SHA-256 `d5f9c7c1a30a7b409b8ee93b5b7de90393cc02f5a1e35f79e4375b05cf8f01c9`) corrigió exclusivamente esas tres referencias textuales (`39`→`38`), confirmado por AST real que las demás recetas/VM (incluida AE-29 completa) permanecen byte a byte idénticas, y es el artefacto funcional que fue validado realmente por el usuario. Las referencias históricas propias de AE-29 (`37 ... anteriores`, correctas porque antes de AE-29 había 37 elementos) permanecen intactas y sin tocar. **El parche provisional original de 300235 bytes permanece invalidado.**

**Identidad de caché con DOS claves, siguiendo el precedente real de AE-22/AE-23/AE-24 -nunca el de AE-2, identificado como una excepción temprana por lectura real de su propio código-**: `{"ventana": ventana, "politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL}`. `rango_min`/`rango_max`/`cantidad_numeros` se excluyen deliberadamente -el motor de esta etapa no los recibe como argumentos matemáticos en absoluto, y se rederivan en la receta desde las constantes privadas ya validadas. Ninguna lista dinámica de colores entra en la identidad. Motor real (`comparar_frecuencia_colores_por_ventana`) sin cambiar su firma, llamado con 4 argumentos posicionales y cero kwargs. `hasta_numero_sorteo` permanece en su propia columna, nunca dentro de `parametros` ni de `parametros_hash`. `etiqueta_ventana` se sigue derivando siempre internamente, nunca aceptada desde HTTP.

**View Model específico para colores, deliberadamente NO compartido con el de AE-29**: mismo formato `ComparacionRecencia`, pero orden alfabético por código de color (no numérico); la VM de AE-29 permanece exactamente intacta, confirmado por AST real. Orden determinista forzado por la propia VM, colores retirados realmente observados preservados en el resultado, un color ausente de la ventana reciente muestra frecuencia reciente en cero con el denominador real. Formulario combinado ventana + corte, sin incluir `control_corte_temporal.html` (mismo motivo que AE-28/AE-29), reutilizando exactamente `_VentanaValida`/`_validar_ventana`/`_CorteOpcional` sin duplicar ni relajar. Conteo estructural: **39 rutas/recetas/templates, 35 con canvas** -decimotercer incremento de canvas desde AE-14; **30 pestañas de navegación de ColorLoto**; grupo sin colisión pasa de veintidós a **veintitrés**.

**Reconciliación honesta de pruebas, sin forzar ninguna cifra**: se demostró que las pruebas nuevas fallan realmente contra cada código defectuoso reconstruido por separado -7 de 11 pruebas del motor. Suite completa final: **`3268 passed`** -reconciliado honestamente: **`3192 + 76 = 3268`**. AST y pytest coinciden exactamente en `3268`; focalizadas en `2484 passed`.

**Validación real completa del usuario en Windows, PostgreSQL y navegador -evidencia atribuida al usuario, no ejecutada por Claude:** entorno real confirmado -Python `3.14.6`, FastAPI `0.141.1`, Pydantic `2.13.5`, httpx `0.28.1`, pytest `9.1.1`, `pip check` limpio. Un primer comando auxiliar para mostrar versiones produjo un `SyntaxError` real por la forma en que PowerShell transmitió un `python -c` con f-string -corregido transmitiendo el script por entrada estándar; incidente exclusivamente de un comando auxiliar previo a las pruebas, sin modificar ningún archivo del proyecto. Pruebas focalizadas reales: `2484 passed in 14.75s`. Suite completa real: `3268 passed in 18.76s`. Auditoría AST/de plantillas real: `RutasGet: 39`, `RutasConCorte: 39`, `RutasConAlias: 39`, `Recetas: 39`, `Plantillas: 39`, `Canvas: 35`, `PestanasColorLoto: 30`. Alcance Git real: exactamente 15 archivos, sin diferencias de alcance ni residuos.

**PostgreSQL real** (contenedor `loteria-predictor-fase2-final-postgres-1`, base `loteria_predictor`, usuario `loteria`, revisión `0006`, `varchar(100)`): 215 sorteos reales de ColorLoto, corte mediano usado `108`. **Contrato HTTP real**, Uvicorn en `127.0.0.1:8004`: las cuatro ventanas canónicas en `200`; el corte existente `ventana=50&hasta_numero_sorteo=100` en `200`; la identidad nueva automatizada `ventana=20&hasta_numero_sorteo=108` en `200`, creada exactamente una vez, con repetición como cache hit estable; corte vacío en `200`, con contenido byte a byte idéntico a la ausencia del parámetro; **17 respuestas `422`** (trece valores de ventana no canónicos/inválidos más cuatro cortes inválidos); **3 respuestas `404`** para las rutas equivalentes de Baloto/Revancha/MiLoto; los cache hits no alteraron filas, timestamps ni huella de caché; **0** coincidencias de `Traceback`/`ERROR`/`Exception`/`KeyError` en los logs de Uvicorn.

**Evolución real de la caché, con dos incidentes protectores reales, ninguno un defecto de la aplicación**: (1) la primera prevalidación esperaba cero filas de AE-30 pero encontró cinco identidades preexistentes (ventanas `5`/`10`/`20`/`50` sin corte, más ventana `50` con corte `100`) -se detuvo de forma protectora sin modificar la caché; una auditoría de solo lectura confirmó las cinco filas válidas (`TotalIdentidades: 5`, `HashesDistintos: 4`, `SinCorte: 4`, `ConCorte: 1`, `MinimoFilasPorResultado: 6`, `MaximoFilasPorResultado: 6`, todas las comprobaciones de contenido en `True`). La validación HTTP automatizada creó únicamente la identidad `ventana=20`/corte `108`, caché global de `177` a `178`, identidades AE-30 de cinco a seis. Durante la revisión visual manual, el usuario probó además `ventana=50`/corte `108` -interacción válida que creó una séptima identidad, caché global a `179`. (2) Una primera auditoría final esperaba seis identidades y se detuvo de forma protectora al encontrar siete -ninguna comprobación de contenido falló; el diagnóstico identificó la fila adicional exactamente como `ventana=50`, `hasta_numero_sorteo=108`, `numero_filas=6`, clasificación `ADICIONAL_REVISION_MANUAL`. La auditoría final corregida conservó esa fila como evidencia real válida: `CacheTotal: 179`, `TotalIdentidadesAE30: 7`, `HashesDistintos: 4`, `SinCorte: 4`, `ConCorte: 3`, `IdentidadManualVentana50Corte108: True`, y las nueve comprobaciones de contenido (`IdentidadCorrecta`, `ResultadoExteriorCorrecto`, `ValoresCorrectos`, `EstructuraCorrecta`, `TotalesCorrectos`, `AparicionesCorrectas`, `FrecuenciasCorrectas`, `DiferenciasCorrectas`, `ValidezCorrecta`) en `True`, `CacheHitManualConfirmado: True`, `ErroresEnLogs: 0`. Los cuatro hashes de parámetros distintos son correctos: `parametros_hash` depende únicamente de las dos claves de `parametros` -el corte se almacena en su propia columna-, así que filas con la misma `ventana` y cortes distintos comparten correctamente el hash de parámetros sin colisionar en la identidad completa.

**Revisión visual real**, cita literal del usuario: "no vi errores en la pagina" -cambio entre las cuatro ventanas, corte vacío, cortes válidos `100` y `108`, "Histórico completo", tabla, gráfica, colores, textos, todos comprobados sin errores visibles. Cierre operativo real: `AE30ValidadaOperativamente: True`, `RevisionVisualAprobada: True`, Uvicorn detenido (PID `8888`), puerto `8004` liberado, PostgreSQL en ejecución, 15 archivos Git sin diferencias de alcance, sin commit ni push.

**Evidencia propia del sandbox** (distinta de la evidencia real del usuario): aplicación limpia del parche corregido sobre la base (`--check`/aplicación real/`--reverse --check`/`diff --check`, todos exitosos), alcance de 15 archivos, árbol de 260 archivos/176 Python, mismos conteos estructurales confirmados de forma independiente, validación independiente 260/260 idénticos byte a byte.

Con esta evidencia real completa del usuario -entorno, pytest, PostgreSQL, HTTP, evolución de caché con dos incidentes protectores documentados con honestidad, revisión visual y cierre operativo-, **AE-30 queda validada.** AE-28, el mantenimiento global y AE-29 permanecen validados e intactos funcionalmente. AE-31 no fue implementada; la comparación por ventana de pares número-color (motor ya corregido, página todavía sin conectar) sigue pendiente de una etapa posterior explícita. Machine Learning todavía no ha comenzado.

**Checkpoint validado (Etapa AE-31, trigésima primera visualización web de ColorLoto -comparación de frecuencia de pares número-color por ventana reciente, cuadragésima visualización global):** tercera etapa que conecta `motor/recencia.py`, tras AE-29 y AE-30 -compara, para cada par ATÓMICO (número, color), su frecuencia en TODO el histórico disponible (ya filtrado por el corte) contra su frecuencia en los últimos `ventana` sorteos reales de ese mismo histórico. Analiza el PAR completo -mismo alcance exacto que `frecuencia_pares_colorloto` (Etapa AE-3); ni el número ni el color por separado, ambas etapas distintas ya conectadas.

**El motor ya contiene la corrección de universo compartido de AE-30, auditada y confirmada real antes de escribir cualquier código de esta etapa -`recencia.py` y `test_recencia.py` no se modifican en absoluto**: `comparar_frecuencia_pares_numero_color_por_ventana` construye un único universo de colores -vigentes UNIÓN observados en el histórico ya filtrado- compartido entre la porción histórica y la reciente, eliminando el defecto real `KeyError: '1-ROJO'` que habría bloqueado esta misma conexión si se hubiera intentado antes de AE-30. Confirmado por diff completo del registro de hashes protegidos: los 6 motores (incluido `recencia.py`), `control_corte_temporal.html`, `models.py`, `main.py`, `exceptions.py`, `test_recencia.py`, las 6 migraciones y las 39 rutas/recetas/View Models anteriores (incluidas AE-29 y AE-30 completas) permanecen byte a byte idénticos.

**Identidad de caché con CUATRO claves, corrigiendo deliberadamente el defecto real que AE-29 tuvo que corregir después de implementar (rederivar el rango desde una constante privada en vez de leerlo de la identidad)**: `{"ventana": ventana, "rango_min": juego.rango_min, "rango_max": juego.rango_max, "politica_universo_colores": POLITICA_UNIVERSO_COLORES_ACTUAL}`. A diferencia de AE-30 (dos claves, sin rango porque su motor no lo recibe), el motor de AE-31 SÍ recibe `rango_min`/`rango_max` como argumentos matemáticos reales, así que la receta los lee directamente de la identidad -nunca de `_RANGO_REAL_COLORLOTO`- confirmado real con el caso exacto de la auditoría (`{"rango_min": 2, "rango_max": 3}` produce exclusivamente ese rango multiplicado por los colores reales, nunca el rango completo 1..7). `politica_universo_colores` se valida defensivamente contra `POLITICA_UNIVERSO_COLORES_ACTUAL` antes de invocar el motor -si no coincide, se rechaza con `ValueError` (nunca `ResultadoHistoricoInconsistenteError`, reservado exclusivamente para inconsistencias del histórico en sí; `exceptions.py` permanece protegido y sin cambios). `cantidad_numeros`, `etiqueta_ventana` y cualquier lista dinámica de colores se excluyen deliberadamente de la identidad.

**Motor real** (`comparar_frecuencia_pares_numero_color_por_ventana`) sin modificar su firma pública, llamado con exactamente 6 argumentos posicionales y cero kwargs. **Nuevo identificador de 63 caracteres** (`comparacion_frecuencia_pares_numero_color_por_ventana_colorloto`) -el más largo del catálogo, desplazando al de AE-27 (54 caracteres); cabe ampliamente en `varchar(100)` sin necesitar ninguna migración nueva.

**View Model específico para pares, deliberadamente NO compartido con los de AE-29/AE-30**: reutiliza `_deserializar_par_numero_color` como único punto de parseo (preserva códigos de color con guiones), orden determinista forzado por `(numero, codigo)` ascendente. Un par histórico ausente de la ventana reciente permanece con `apariciones_recientes=0` y el denominador real -nunca desaparece ni provoca un error. **Dos gráficos coordinados, decisión de producto cerrada**: nunca un único gráfico con doce datasets superpuestos ni 42 etiquetas ilegibles -`chart_datasets_historico`/`chart_datasets_reciente` construyen dinámicamente un dataset por color REAL, nunca fijando seis colores a mano, con el mismo orden de números y el mismo color visual en ambos gráficos.

**Hallazgo real durante la implementación, corregido antes de esta entrega**: la primera versión de la plantilla usaba `height="220"` en ambos `<canvas>`, en vez de la convención real `height="180"` que toda la suite existente usa para detectar plantillas con gráfica -confirmado real por una prueba estructural que falló genuinamente antes de la corrección; corregido a `height="180"` en los dos `<canvas>`, reverificado real.

Formulario combinado ventana + corte, sin incluir `control_corte_temporal.html` (mismo motivo que AE-28/AE-29/AE-30), reutilizando exactamente `_VentanaValida`/`_validar_ventana`/`_CorteOpcional` sin duplicar ni relajar. Conteo estructural: **40 rutas/recetas/templates, 36 con canvas, 37 etiquetas `<canvas>` totales** (AE-31 es la primera plantilla con dos); **31 pestañas de navegación de ColorLoto**; grupo sin colisión pasa de veintitrés a **veinticuatro**.

**Prevención explícita de errores de conteo documental**: antes de AE-31 había **39** rutas, recetas, páginas y View Models -confirmado real por AST antes de escribir cualquier docstring, nunca por aritmética textual. Los docstrings propios de esta etapa dicen consistentemente "39 anteriores", nunca "40 anteriores".

**Historia completa de los parches de AE-31, conservada íntegramente:** el **parche provisional original** (322355 bytes, SHA-256 `25137e4c71c1259de5e079006dad6cc082c41cf5ea4aa16b73eb59ac13d80ae0`) implementaba correctamente toda la funcionalidad -incluidas las cuatro claves de identidad y la reutilización del motor ya corregido en AE-30-, pero **quedó INVALIDADO** por una única afirmación textual desplazada: el docstring de la View Model (`comparacion_frecuencia_pares_numero_color_por_ventana_colorloto_a_vm`) decía "40 VM anteriores" cuando, al ser AE-31 el elemento número 40, existían exactamente **39** elementos anteriores -mismo patrón de error ya corregido antes para AE-29 y AE-30. El **parche corregido** (322355 bytes, SHA-256 `929b65833e1c736d5cef290bcab30f6766e37db38c7fc88b81d98306f11f75c7`) corrigió exclusivamente esa única referencia textual (`40`→`39`), confirmado por AST real que los otros 260 de los 261 archivos permanecen byte a byte idénticos -solo `view_models.py` difiere-, y es el artefacto funcional que fue validado realmente por el usuario. Las referencias históricas propias de AE-29 ("37 anteriores") y AE-30 ("38 anteriores") permanecen intactas y sin tocar. **El parche provisional original permanece invalidado.**

**Reconciliación honesta de pruebas, sin forzar ninguna cifra ni inflar conteos**: **72 pruebas nuevas** (`3268 + 72 = 3340`), repartidas en `+25` (`test_calcular_y_persistir_estadistica.py`: `966→991`, incluida una demostración real de que 3 pruebas nuevas fallan genuinamente si se reintroduce el defecto de rederivar el rango, como el que AE-29 tuvo que corregir), `+37` (`test_generalizacion_juegos.py`: `1088→1125`, Ruta/VM/Template/HTTP real/Preservación-regresión, incluidas regresiones explícitas de que AE-29 y AE-30 siguen intactas), `+9` (`test_estadistica_repository.py`: `330→339`, incluida una prueba explícita de que las identidades de AE-29/AE-30/AE-31 nunca colisionan para la misma ventana), `+1` (`test_migracion_0006_amplia_tipo_estadistica.py`: `17→18`, nueva prueba dedicada confirmando que el identificador de AE-31 es ahora el más largo real del catálogo, con la longitud máxima corregida de 54 a 63; la prueba histórica que demuestra que el identificador de AE-27 mide 54 permanece intacta), y `+0` en `test_corte_temporal_navegacion.py` (solo ajuste de conteo de rutas). AST y pytest coinciden exactamente: `3340` en ambos. **Focalizadas: `2556 passed`** -reconciliado honestamente `2484 + 72 = 2556`, incluyendo `test_recencia.py` en el conjunto focalizado (AE-31 reutiliza ese motor, aunque no lo modifica).

**Validación real completa del usuario en Windows, PostgreSQL y navegador -evidencia atribuida al usuario, no ejecutada por Claude:** entorno real confirmado -Python `3.14.6`, FastAPI `0.141.1`, Pydantic `2.13.5`, httpx `0.28.1`, pytest `9.1.1`, `pip check` limpio. Pruebas focalizadas reales: `2556 passed in 10.79s`. Suite completa real: `3340 passed in 11.98s`. Un primer bloque de PowerShell tenía una aserción auxiliar incorrecta que esperaba `2513` en vez de `2556` -pytest en sí terminó correctamente con `2556 passed`, sin ningún fallo de código; incidente exclusivamente de un comando auxiliar, sin modificar ningún archivo del proyecto. Auditoría estructural real: `RutasGet: 40`, `RutasConCorte: 40`, `RutasConAlias: 40`, `Recetas: 40`, `Plantillas: 40`, `Canvas: 36`, `EtiquetasCanvas: 37`, `PestanasColorLoto: 31`, migraciones `6`, revisión Alembic `0006`, `tipo_estadistica: character varying(100)`, longitud del identificador de AE-31 `63`; identidad declarada y las cuatro claves leídas por la receta confirmadas reales; conteo incorrecto del docstring de VM `0`, conteo correcto `1`. Alcance Git real: exactamente 13 archivos.

**PostgreSQL real** (contenedor `loteria-predictor-fase2-final-postgres-1`): al iniciar la prevalidación se encontraron **ocho identidades preexistentes de AE-31, cuyo origen no se determinó en esa medición** -sin atribuirlas a pytest, a una ejecución concreta ni a ninguna otra causa no demostrada. Estado inicial comprobado: caché global `187`, identidades AE-31 `8`, hashes distintos `4`, sin corte `4`, con corte `100` `4`, ventanas exactas `5`/`10`/`20`/`50` (cada una sin corte y con corte `100`), cada resultado con `42` filas; diagnóstico de solo lectura, sin modificar la caché.

**Contrato HTTP real**, Uvicorn en `127.0.0.1:8005`: las ocho identidades preexistentes respondieron `200` con selector correcto y los dos `<canvas>` presentes; las cuatro ventanas válidas en `200`; **17 respuestas `422`** (ventana vacía, `5.0`, `5.00`, `20.0`, `5.5`, `0`, `-5`, `7`, texto, `05`, espacio antes de `5`, `+5`, espacio, y cortes `0`/`-1`/texto/espacio); aislamiento de Baloto/Revancha/MiLoto: **3 respuestas `404`**; corte vacío byte a byte igual a la ausencia de corte; cache hits sin cambios; creación controlada de una única identidad nueva (ventana `20`, corte `108`, `42` filas), identidades AE-31 `8→9`, caché global `187→188`, segundo acceso confirmado como cache hit; **0** errores en logs.

**Auditoría final independiente real** del JSON de las nueve identidades: `TotalIdentidades: 9`, `HashesDistintos: 4`, `SinCorte: 4`, `ConCorte: 5`, y las catorce comprobaciones de contenido (`IdentidadesExactas`, `IdentidadCorrecta`, `ResultadoExteriorCorrecto`, `ValoresCorrectos`, `TotalesCorrectos`, `AparicionesCorrectas`, `FrecuenciasCorrectas`, `DiferenciasCorrectas`, `VentanasCorrectas`, `ConservacionMasaCorrecta`, `ValidezCorrecta`) en `True`; `FilasEsperadas: 378`, `FilasCacheadas: 378`; cache hit final confirmado; caché global final `188`.

**Dos incidentes reales, exclusivamente en comandos auxiliares de PowerShell, ninguno un defecto de la aplicación**: (1) un primer intento de arranque/comprobación de Uvicorn construyó incorrectamente una URL por interpolación de PowerShell -Uvicorn sí llegó a iniciar, pero la comprobación de disponibilidad falló y el bloque se detuvo de forma protectora; (2) otro bloque comparó el PID lanzador `19008` con el PID que realmente escuchaba el puerto -la comprobación corregida confirmó `PIDLanzadorReportado: 19008`, `PIDQueEscucha: 12136`, proceso `python.exe`, puerto `8005`, `UvicornConfirmado: True`.

**Revisión visual real**, cita literal del usuario: "no vi errores en la pagina". Cierre operativo real: PID real `12136` detenido, puerto `8005` liberado, PostgreSQL en ejecución, 13 archivos Git sin diferencias de alcance, sin commit ni push.

**Evidencia propia del sandbox** (distinta de la evidencia real del usuario): aplicación limpia del parche corregido sobre la base (`--check`/aplicación real/`--reverse --check`/`diff --check`, todos exitosos), alcance de 13 archivos, árbol de 261 archivos/176 Python, mismos conteos estructurales confirmados de forma independiente.

Con esta evidencia real completa del usuario -entorno, pytest, PostgreSQL, HTTP, evolución de caché con dos incidentes protectores documentados con honestidad, revisión visual y cierre operativo-, **AE-31 queda validada.** AE-28, el mantenimiento global, AE-29 y AE-30 permanecen validados e intactos funcionalmente. AE-32 no fue implementada. Machine Learning todavía no ha comenzado.

**Checkpoint validado (Etapa AE-32, décima visualización genérica de los tres juegos numéricos -coocurrencia de pares de números, cuadragésima primera visualización global):** primera etapa que conecta capacidad estadística a los juegos numéricos genéricos (Baloto, Baloto Revancha, MiLoto) desde la Etapa Z -reutiliza `calcular_coocurrencia_pares` (`motor/coocurrencia.py`), sin modificarlo, el mismo motor cuyo equivalente exacto para ColorLoto ya está conectado desde AE-14 (números) y AE-16 (colores). Compara qué pares de números principales aparecieron JUNTOS dentro del mismo sorteo, y con qué frecuencia -solo se reportan los pares observados al menos una vez (soporte > 0), nunca el universo teórico completo (hasta 903 combinaciones en Baloto/Revancha, 741 en MiLoto), decisión ya tomada por el propio motor desde su diseño original.

**Auditado y confirmado que el motor es genuinamente distinto del de ColorLoto, sin copiar ningún supuesto exclusivo**: para Baloto/Revancha/MiLoto (selección sin reemplazo), `calcular_coocurrencia_pares` SÍ calcula `frecuencia_esperada`/`lift` reales vía distribución hipergeométrica segura -a diferencia de `calcular_coocurrencia_pares_colorloto`, que los deja en `None` porque la combinatoria con repetición de ColorLoto sigue sin verificar contra el reglamento oficial (Acuerdo 02 de 2024, Coljuegos). Esta etapa no toca esa pregunta pendiente en absoluto.

**Hallazgo real confirmado por lectura directa del motor antes de escribir la VM, y reconfirmado por auditoría SQL independiente del usuario**: `_tabular_coocurrencia` solo garantiza orden por soporte descendente, sin ningún criterio de desempate -un empate en soporte queda en el orden de iteración interno del motor si la VM no lo corrige. La VM de esta etapa (`coocurrencia_pares_a_vm`) fuerza explícitamente el desempate por los propios números del par en orden ascendente, nunca confiando en el orden implícito del motor. **La auditoría SQL real del usuario confirmó esta separación de responsabilidades de forma contundente**: un primer criterio de auditoría exigía al JSON de caché tanto soporte descendente como desempate numérico -exigencia incorrecta, ya que el propio motor y la caché NUNCA garantizan el desempate; la auditoría corregida encontró **2160 casos reales de desempates fuera de orden numérico dentro de la caché**, confirmando exactamente el hallazgo original: el orden numérico no puede asumirse desde el motor ni desde el JSON persistido. Las siete páginas HTML renderizadas, auditadas después, SÍ mostraron soporte descendente y desempate numérico ascendente en las siete -confirmando que la VM corrige realmente el desempate en el momento de presentación, no que lo documenta sin aplicarlo.

**Identidad de caché con EXACTAMENTE tres claves** `{"rango_min": rango_min, "rango_max": rango_max, "cantidad_numeros": cantidad_numeros}`, construida desde `juego_dominio.number_range`/`juego_dominio.numbers_to_pick`, nunca hardcodeada -mismo contrato exacto ya validado por `distribucion_altos_bajos` (Etapa Z). Ninguna clave de presentación, orden, paginación ni exclusiva de ColorLoto (`politica_universo_colores`, `color_objetivo`). `hasta_numero_sorteo` permanece en su propia columna, nunca dentro de `parametros_metrica`.

**Nuevo `tipo_estadistica`**: `coocurrencia_pares` (**18 caracteres**, longitud real confirmada por cálculo directo y por auditoría estructural independiente del usuario), cabe ampliamente en `varchar(100)`, sin necesitar ninguna migración nueva. **Sin canvas ni gráfica**: decisión de producto explícita de esta etapa -la escala de hasta 903 pares hace una gráfica completa poco legible, y no existe autorización para truncar a un top-N; tabla completa con cabecera fija y contenedor desplazable, reutilizando estilos ya existentes, sin JavaScript nuevo.

**Ruta genérica única** `/estadisticas/{juego_slug}/coocurrencia-pares`, cuyo RESOLVER interno acepta únicamente `baloto`/`baloto-revancha`/`miloto` -cualquier slug realmente desconocido produce `404` mediante ese resolver (conjunto cerrado `SLUG_A_CODIGO`, confirmado real). **El resultado HTTP global de la aplicación para "colorloto" es distinto y debe distinguirse explícitamente del resolver genérico**: la ruta dedicada de ColorLoto (`/estadisticas/colorloto/coocurrencia-pares`, AE-14) ya existía como ruta LITERAL, registrada antes que el patrón genérico `{juego_slug}` -Starlette evalúa las rutas en el orden exacto de registro, así que esa URL nunca llega a entrar en el resolver ni en la receta genérica de AE-32: responde `200` a través del handler literal de ColorLoto, no `404` -confirmado real con simulación fiel del algoritmo de enrutamiento, con HTTP real en sandbox y con HTTP real del usuario en Windows (ver evidencia real más abajo: las identidades de caché de AE-32 permanecieron en `6` durante esa solicitud, confirmando que la receta genérica nunca fue invocada). El grupo de sufijos ColorLoto "sin colisión con ninguna ruta genérica" pasa de veinticuatro a **veintitrés** -`coocurrencia-pares` sale de ese grupo, mismo caso ya establecido por `distribucion-pares-consecutivos`.

**Historia completa de los parches de AE-32, conservada íntegramente**: el **parche provisional original** (266140 bytes, SHA-256 `c303d8fdd380e363eaeaf12df215213fecbbda49827faa66669662af897629d0`) implementaba correctamente toda la funcionalidad, pero **quedó INVALIDADO** por dos afirmaciones documentales incorrectas: (1) afirmaba que `coocurrencia_pares` tenía 17 caracteres, cuando su longitud real es 18; (2) agrupaba ambiguamente a ColorLoto con los slugs desconocidos como si ambos produjeran `404`, cuando en realidad `/estadisticas/colorloto/coocurrencia-pares` es la ruta literal preexistente de AE-14 y responde `200`. El **parche corregido** (267185 bytes, SHA-256 `ac8563749f2129f70cc47348e855e1f0b0ba1b8ebe2d3d1c2cde7ff81ebeb52c`) corrigió exclusivamente esas dos afirmaciones documentales -confirmado por comparación byte a byte que 260 de los 262 archivos permanecen idénticos, solo `README.md` y `ROADMAP.md` difieren- y es el artefacto funcional que fue validado realmente por el usuario. **El parche provisional original permanece invalidado.**

**Reconciliación honesta de pruebas**: **41 pruebas nuevas** (`3340 + 41 = 3381`), repartidas en `+29` (`test_generalizacion_juegos.py`) y `+12` (`test_estadistica_repository.py`). AST y pytest coinciden exactamente: `3381` en ambos. **Focalizadas: `2604 passed`** -conjunto correcto para esta etapa: los cinco archivos habituales más `test_coocurrencia.py` (motor reutilizado por AE-32), en vez de `test_recencia.py` (usado en el conjunto focalizado de AE-31, motor no tocado por esta etapa).

**Validación real completa del usuario en Windows, PostgreSQL y navegador -evidencia atribuida al usuario, no ejecutada por Claude:** entorno real confirmado -Python `3.14.6`, FastAPI `0.141.1`, Pydantic `2.13.5`, httpx `0.28.1`, pytest `9.1.1`, `pip check` limpio. Pruebas focalizadas reales: `2604 passed`. Suite completa real: `3381 passed`. Un primer comando auxiliar para consultar versiones produjo un `SyntaxError` por interpolación incorrecta de comillas en PowerShell -incidente exclusivo del comando auxiliar, nunca del código; el comando corregido confirmó el entorno y todas las pruebas limpiamente. Auditoría estructural real: `RutasGet: 41`, `RutasConCorte: 41`, `RutasConAlias: 41`, `Recetas: 41`, `Plantillas: 41`, `PlantillasConCanvas: 36`, `EtiquetasCanvas: 37`, `PestanasColorLoto: 31`, `RutaGenericaAE32: 1`, `RutaLiteralColorLoto: 1`, `TipoAE32Longitud: 18`, migraciones `6`, revisión Alembic `0006`, `tipo_estadistica: character varying(100)`; caché global inicial `188`, identidades iniciales de AE-32 `0`, PostgreSQL disponible, puerto `8006` inicialmente libre. Alcance Git real: exactamente 12 archivos, sin commit ni push.

**Contrato HTTP real**, Uvicorn en `127.0.0.1:8006`: seis solicitudes iniciales válidas (Baloto histórico/corte `2694`, Baloto Revancha histórico/corte `2694`, MiLoto histórico/corte `588`) en `200`, las seis con título correcto, tabla correcta, selector de corte presente, ausencia de canvas y contenido no vacío; los seis cache hits posteriores no crearon filas nuevas; corte vacío y ausencia del parámetro ambos en `200` con contenido HTML idéntico y caché sin cambios. **Aislamiento de ColorLoto confirmado real**: `/estadisticas/colorloto/coocurrencia-pares` respondió `200`, atendida por su ruta literal preexistente -las identidades de AE-32 permanecieron en `6` durante esa solicitud, confirmando que la receta genérica de AE-32 nunca la atendió. Cortes inválidos (`0`, `-1`, texto, espacio codificado) en `422`. Slugs realmente desconocidos (`desconocido`, `colorloto-desconocido`, `otro-juego`) en `404`. Creación controlada de una séptima identidad (Baloto, corte `2693`, `200`, segundo acceso confirmado como cache hit): identidades AE-32 `0→7`, caché global `188→195`; **0** errores en logs.

**Estado final de la caché**: siete identidades (Baloto histórico `902` filas, Baloto corte `2693` `902` filas, Baloto corte `2694` `902` filas, Baloto Revancha histórico `902` filas, Baloto Revancha corte `2694` `902` filas, MiLoto histórico `446` filas, MiLoto corte `588` `395` filas) -tres juegos distintos, dos hashes distintos, tres sin corte, cuatro con corte, `5351` filas auditadas en total, caché global final `195`.

**Auditoría matemática y del JSON**, todas las comprobaciones en `True`: identidades exactas, identidad de tres claves correcta, hashes correctos, estructura exterior e interior del resultado correcta, valores y rangos correctos, totales correctos, frecuencia relativa = soporte / total_sorteos, frecuencia esperada hipergeométrica correcta, lift correcto, soporte descendente en la caché, ausencia de pares duplicados, conservación de masa, límites teóricos de filas, vigencia correcta, cache hit final confirmado -la suma del soporte de cada resultado coincide con `total_sorteos × C(5,2)`, y la suma de frecuencias relativas es `10`.

**Incidente real de auditoría, documentado con honestidad, nunca presentado como defecto de AE-32**: el primer comando SQL de auditoría de orden exigía al JSON de caché tanto soporte descendente como desempate numérico simultáneamente -exigencia incorrecta, ya que el motor y la caché únicamente garantizan soporte descendente; el View Model es la única capa responsable del desempate numérico. La auditoría corregida confirmó `orden_soporte_cache_correcto: True` junto con `2160` desempates reales fuera de orden numérico dentro de la propia caché -esos 2160 casos no son errores: demuestran exactamente por qué el desempate explícito en el View Model es necesario y no redundante. Las siete páginas HTML, auditadas después, confirmaron soporte descendente y desempate numérico ascendente en las siete, número de filas HTML idéntico a la caché, ausencia de canvas en las siete -`OrdenPresentacionCorrecto: True`.

**Revisión visual real**, cita literal del usuario: "no vi errores en las paginas". Cierre operativo real: `AE32ValidadaOperativamente: True`; PID lanzador reportado `8548`, PID real que escuchaba `22172` -diferencia diagnosticada como comportamiento operativo normal, nunca como defecto de la aplicación-, PID real detenido correctamente, puerto `8006` liberado, PostgreSQL en ejecución, 12 archivos Git sin diferencias de alcance, sin commit ni push.

**Evidencia propia del sandbox** (distinta de la evidencia real del usuario): aplicación limpia del parche corregido sobre la base (`--check`/aplicación real/`--reverse --check`/`diff --check`, todos exitosos), alcance de 12 archivos, árbol de 262 archivos/176 Python, mismos conteos estructurales confirmados de forma independiente, longitud 18 reconfirmada por cálculo directo.

Con esta evidencia real completa del usuario -entorno, pytest, PostgreSQL, HTTP, aislamiento de ColorLoto, auditoría matemática y del JSON, corrección honesta del criterio de orden SQL, revisión visual y cierre operativo-, **AE-32 queda validada.** AE-28, el mantenimiento global, AE-29, AE-30 y AE-31 permanecen validados e intactos. AE-33 no fue implementada; la coocurrencia de tríos para juegos numéricos continúa pendiente. Machine Learning todavía no ha comenzado.

**Checkpoint validado (Etapa AE-33, decimoprimera visualización genérica de los tres juegos numéricos -coocurrencia de tríos de números, cuadragésima segunda visualización global):** segunda etapa de coocurrencia para juegos numéricos genéricos, mismo patrón exacto que AE-32 -reutiliza `calcular_coocurrencia_trios` (`motor/coocurrencia.py`), sin modificarlo, el mismo motor cuyo equivalente exacto para ColorLoto ya está conectado desde AE-15. Compara qué tríos de números principales aparecieron JUNTOS dentro del mismo sorteo -solo se reportan los tríos observados al menos una vez, nunca el universo teórico completo (`C(43,3) = 12341` para Baloto/Revancha, `C(39,3) = 9139` para MiLoto).

**Escala genuinamente distinta de AE-32, por eso esta etapa introduce paginación -nunca simplemente copiado el diseño de pares**: el universo de tríos es entre 13 y 14 veces mayor que el de pares para el mismo rango, y el propio motor sigue devolviendo únicamente lo observado (nunca inventa filas en cero) -la paginación es exclusivamente de presentación, servidor sin JavaScript, tamaño fijo de 100 filas, nunca configurable en esta etapa. El resultado completo se calcula y persiste una única vez por identidad y corte; cambiar de página nunca crea una identidad de caché nueva ni modifica el hash -confirmado real con una prueba dedicada, y reconfirmado con la validación matemática real del usuario.

**Orden de caché frente a orden de presentación, mismo hallazgo real que AE-32, reconfirmado aquí porque es la MISMA función compartida (`_tabular_coocurrencia`)**: el motor y el resultado persistido solo garantizan soporte descendente, sin ningún desempate -el View Model aplica el orden GLOBAL completo (soporte descendente, luego los tres números del trío en orden ascendente) sobre TODAS las filas ANTES de aplicar cualquier segmento de página, nunca pagina primero y ordena después. **La auditoría matemática real del usuario confirmó esta separación de responsabilidades de forma contundente**: sobre 25526 filas reales repartidas en siete identidades, se encontraron **4525 desempates de caché genuinamente fuera de orden numérico**, corregidos correctamente por el View Model -ese número no es un error, es la prueba directa de que el orden global del View Model no es redundante.

**Identidad de caché con EXACTAMENTE tres claves**, idéntica a AE-32: `{"rango_min": rango_min, "rango_max": rango_max, "cantidad_numeros": cantidad_numeros}` -`pagina` NUNCA forma parte de la identidad, nunca se pasa al orquestador ni a la receta; se aplica exclusivamente en el View Model, sobre el resultado ya recuperado completo.

**`pagina` validado con disciplina léxica propia de esta etapa, auditado el comportamiento real de Pydantic antes de escribir el validador**: por defecto, Pydantic acepta silenciosamente `"1.0"`, `"01"` y `"+1"` como equivalentes a `1` -confirmado real con `TestClient` antes de implementar, nunca asumido. `_pagina_lexica_estricta` (helper pequeño y específico, nunca alterando `_CorteOpcional`) exige la forma canónica exacta de un entero positivo; ausencia y cadena vacía son equivalentes al valor por defecto `1`, mismo criterio de `_corte_vacio_a_none` adaptado a un valor por defecto real en vez de `None`.

**Página fuera de rango**: sin precedente real en el proyecto -se evitó deliberadamente una excepción de dominio de texto libre. `PaginaFueraDeRangoError`, una excepción pequeña y específica de esta etapa, se traduce a `422` con un mensaje estable únicamente en el router.

**Nuevo `tipo_estadistica`**: `coocurrencia_trios` (**18 caracteres**, idéntica longitud que `coocurrencia_pares` pero cadena distinta, sin colisión), cabe ampliamente en `varchar(100)`, sin necesitar ninguna migración nueva. **Sin canvas ni gráfica**, misma decisión de producto que AE-32.

**Ruta genérica** `/estadisticas/{juego_slug}/coocurrencia-trios`, mismo aislamiento exacto que AE-32: el resolver genérico (`SLUG_A_CODIGO`) nunca reconoce "colorloto", pero la ruta literal preexistente de ColorLoto (`/estadisticas/colorloto/coocurrencia-trios`, AE-15) responde `200` real a través de su propio handler -nunca `404`, nunca la receta genérica de esta etapa. El grupo de sufijos ColorLoto "sin colisión con ninguna ruta genérica" pasa de veintitrés a **veintidós**.

Entrada de navegación añadida exactamente una vez para cada uno de los tres juegos compatibles -Baloto y Baloto Revancha pasan de diez a **once** métricas, MiLoto de nueve a **diez**. **Ninguna de las 31 pestañas de ColorLoto se modificó.**

**Historia completa de los parches de AE-33, conservada íntegramente**: el **parche provisional original** (276120 bytes, SHA-256 `d9e903e314136a9c743701596dd4e5f53918b267871e73c6b1f84274ed9bd461`) implementaba correctamente toda la funcionalidad, pero **quedó INVALIDADO** por una afirmación visible no demostrada, copiada sin corregir desde AE-32: tanto la plantilla de pares como la de tríos afirmaban "el número total de [pares/tríos] posibles es mucho mayor y en su mayoría nunca se ha observado" -contradicho directamente por la evidencia real de AE-32 (Baloto/Revancha `902/903`≈99,9%, MiLoto histórico `446/741`≈60,2%, MiLoto con corte `395/741`≈53,3%, en los cuatro casos MÁS de la mitad observado). El **parche corregido** (281301 bytes, SHA-256 `8adc0aa7f4260c6b8b69e461c114c455adda83188e9c37f84d54ee73491efff5`) sustituyó esa afirmación por redacción neutral en ambas plantillas ("...no forman parte de esta tabla"), sin afectar ningún contrato funcional -confirmado por comparación byte a byte que 257 de los 263 archivos permanecen idénticos frente al parche invalidado, solo los 3 documentos, las 2 plantillas y el archivo de pruebas con la regresión textual difieren- y es el artefacto funcional que fue validado realmente por el usuario. **La corrección de la plantilla de pares es exclusivamente textual, mantenimiento autorizado dentro de AE-33: no modifica el motor, la caché, el View Model, la ruta ni los cálculos de AE-32, y no reescribe ni mueve el tag `ae32-validado`, su release ni su commit histórico -AE-32 permanece validada íntegramente.** **El parche provisional original permanece invalidado.**

**Reconciliación honesta de pruebas**: **44 pruebas nuevas** (`3381 + 44 = 3425`). AST y pytest coinciden exactamente: `3425` en ambos. **Focalizadas: `2648 passed`** -conjunto de seis archivos: `test_coocurrencia.py`, `test_calcular_y_persistir_estadistica.py`, `test_corte_temporal_navegacion.py`, `test_estadistica_repository.py`, `test_generalizacion_juegos.py`, `test_migracion_0006_amplia_tipo_estadistica.py`.

**Validación real completa del usuario en Windows, PostgreSQL y navegador -evidencia atribuida al usuario, no ejecutada por Claude:** entorno real confirmado -Python `3.14.6`, FastAPI `0.141.1`, Pydantic `2.13.5`, httpx `0.28.1`, pytest `9.1.1`, `pip check` limpio, compile-check superado. Pruebas focalizadas reales: `2648 passed`. Suite completa real: `3425 passed`. Auditoría estructural real: 42 rutas/recetas/plantillas, 36 con canvas, 37 etiquetas `<canvas>`, 31 pestañas ColorLoto, 6 migraciones, revisión Alembic `0006`, `tipo_estadistica: character varying(100)`, longitud `18`, ruta genérica y literal de ColorLoto confirmadas cada una exactamente una vez, cero afirmaciones falsas y redacción neutral confirmada en ambas plantillas. PostgreSQL real disponible: caché global inicial `195`, identidades iniciales de AE-33 `0`, puerto `8007` inicialmente libre, prevalidación de solo lectura sin modificar la caché. Alcance Git real: exactamente 13 archivos, sin commit ni push.

**Contrato HTTP real**, Uvicorn en `127.0.0.1:8007` (PID lanzador reportado `14712`, PID real que escuchaba `13984`, proceso `python.exe`): seis solicitudes iniciales válidas (Baloto histórico 49 páginas, Baloto corte `2694` 49 páginas, Baloto Revancha histórico 50 páginas, Baloto Revancha corte `2694` 49 páginas, MiLoto histórico 7 páginas, MiLoto corte `588` 6 páginas) en `200`, las seis con 100 filas, sin canvas, corte y paginación correctos; seis cache hits posteriores sin filas nuevas; página 2 de las seis identidades en `200` con navegación correcta; `pagina=` vacía idéntica a su ausencia. **Nueve páginas inválidas en `422`** (`1.0`, `01`, `+1`, espacio antes de `1`, `0`, `-1`, texto, espacio, y página fuera de rango `999999`). Cuatro cortes inválidos en `422` (`0`, `-1`, texto, espacio). **Aislamiento de ColorLoto confirmado real**: la ruta literal respondió `200`, atendida por su propio handler -las identidades de AE-33 permanecieron en `6` durante esa solicitud. Tres slugs realmente desconocidos en `404`. Creación controlada de una séptima identidad (Baloto, corte `2693`, página 1 y 2 en `200`, cache hit posterior confirmado): identidades AE-33 `0→7`, caché global `195→202`; **0** errores en logs.

**Auditoría independiente real del JSON y del View Model** sobre las siete identidades finales (Baloto corte `2693`/`2694`/histórico, Baloto Revancha corte `2694`/histórico, MiLoto corte `588`/histórico; dos hashes distintos, uno compartido por Baloto y Baloto Revancha y otro por MiLoto), con **todas** las comprobaciones en `True`: identidades exactas, identidad correcta, `pagina` fuera de la identidad, hashes correctos, estructura exterior e interior correcta, valores y totales correctos, frecuencias y frecuencias esperadas hipergeométricas correctas, lift correcto, orden por soporte de la caché correcto, orden global del View Model correcto, paginación correcta, reconstrucción completa de páginas correcta, excepción de página fuera de rango correcta, sin tríos duplicados, conservación de masa correcta, límites de filas correctos, vigencia correcta. Totales auditados: **25526 filas, 259 páginas reconstruidas**, mínimo `554` filas por identidad, máximo `4903`, y los **4525 desempates de caché fuera de orden numérico** ya mencionados arriba, corregidos correctamente por el View Model. Cache hit HTTP final confirmado sin crear filas.

**Cinco incidentes reales, exclusivamente en comandos auxiliares, ninguno un defecto de AE-33, documentados con honestidad**: (1) una primera consulta de versiones produjo `SyntaxError` por el tratamiento de comillas de PowerShell en Windows -las pruebas se ejecutaron después correctamente; (2) una primera auditoría de la redacción neutral informó erróneamente cero apariciones en la plantilla de tríos por una comparación textual frágil con caracteres acentuados -una comprobación corregida confirmó 1 aparición real en cada plantilla; (3) un primer bloque HTTP completo no se ejecutó porque PowerShell no admitió un `if/else` dentro de una propiedad de `[PSCustomObject]` con esa sintaxis -los fragmentos ejecutados fuera de ese bloque no constituyeron evidencia y no se usan aquí; (4) una consulta de caché produjo `NameError: coocurrencia_trios is not defined` porque PowerShell eliminó las comillas del literal -corregido enviando el código por entrada estándar; (5) un primer intento de limpieza recibió un PID lanzador nulo de `Get-Process` porque el listener ya había sido detenido -un bloque final independiente confirmó caché, logs, PostgreSQL, alcance Git, detención de Uvicorn y liberación del puerto.

**Revisión visual real**, cita literal del usuario: "no vi errores en las paginas". Cierre operativo real: Uvicorn detenido (PID real `13984`), puerto `8007` liberado, PostgreSQL en ejecución, caché global final `202`, siete identidades conservadas como evidencia, cero errores en logs, 13 archivos Git sin diferencias de alcance, sin commit ni push.

**Evidencia propia del sandbox** (distinta de la evidencia real del usuario): aplicación limpia del parche corregido sobre la base (`--check`/aplicación real/`--reverse --check`/`diff --check`, todos exitosos), alcance de 13 archivos, árbol de 263 archivos/176 Python, mismos conteos estructurales confirmados de forma independiente.

Con esta evidencia real completa del usuario -entorno, pytest, PostgreSQL, HTTP, paginación, orden global, aislamiento de ColorLoto, auditoría matemática y del JSON, cinco incidentes operativos documentados con honestidad, revisión visual y cierre operativo-, **AE-33 queda validada.** AE-28, el mantenimiento global, AE-29, AE-30, AE-31 y AE-32 permanecen validados e intactos -incluida la corrección exclusivamente textual autorizada sobre la plantilla de pares de AE-32, que no modifica su historia Git ni su contrato funcional. AE-34 no fue implementada. Machine Learning todavía no ha comenzado.

**Checkpoint validado (Etapa AE-34, decimosegunda visualización genérica de los tres juegos numéricos -distribución de tríos consecutivos, cuadragésima tercera visualización global):** tercera capacidad genérica conectada desde AE-32, con el motor más simple y de menor riesgo de todo el inventario pendiente -reutiliza `calcular_distribucion_trios_consecutivos` (`motor/consecutivos.py`), sin modificarlo, el mismo motor cuyo equivalente exacto para ColorLoto ya está conectado desde AE-13. Clasifica cada sorteo según la cantidad de tríos de números consecutivos que contiene -en una secuencia como 1,2,3,4 se cuentan dos tríos (1,2,3) y (2,3,4), los tríos pueden solaparse.

**Motor confirmado como el de menor complejidad de todo el catálogo de capacidades pendientes**: devuelve `list[FrecuenciaObservada]` -el mismo tipo ya usado por `distribucion_altos_bajos`/`frecuencia_superbalota`- vía `tabular_conteo_por_sorteo`, que **garantiza por diseño** el orden ascendente, sin ninguna ambigüedad de desempate que resolver en el View Model -a diferencia de AE-32/AE-33. Solo **4 categorías reales** (`0,1,2,3` para los tres juegos de 5 números) -tabla completa pura, sin canvas, sin paginación, sin filtros ni límite de filas.

**Contrato real de serialización, confirmado por la auditoría del usuario y documentado con precisión**: en el JSON de caché, `valor` se serializa como **string** (`"0"`, `"1"`, `"2"`, `"3"`) -esto no es un defecto, es el contrato real del serializador genérico `_serializar_frecuencia_observada` (`dataclasses.asdict`), el mismo ya usado por dos recetas conectadas previamente. El View Model convierte defensivamente esos strings a enteros mediante `int(f["valor"])`, preservando el orden numérico `0, 1, 2, 3` en la presentación.

**Identidad de caché con EXACTAMENTE tres claves**, idéntica a AE-32/AE-33: `{"rango_min": rango_min, "rango_max": rango_max, "cantidad_numeros": cantidad_numeros}` -obtenidas de `juego_dominio.number_range`/`numbers_to_pick`, nunca hardcodeadas ni rederivadas.

**Conservación de masa**: `Σ apariciones = total_sorteos`, `Σ frecuencia_relativa = 1.0`, cada frecuencia = `apariciones / total_sorteos` -confirmada tanto en sandbox como en la auditoría matemática real del usuario sobre las siete identidades finales.

**Nuevo `tipo_estadistica`**: `distribucion_trios_consecutivos` (**31 caracteres**), cabe ampliamente en `varchar(100)`, sin necesitar ninguna migración nueva. **Sin canvas, sin paginación, sin filtros, sin límite de filas**: decisión de producto explícita -las 4 categorías reales no justifican ninguna de esas complejidades.

**Ruta genérica** `/estadisticas/{juego_slug}/distribucion-trios-consecutivos`, mismo aislamiento exacto que AE-32/AE-33: la ruta literal preexistente de ColorLoto (AE-13) responde `200` real a través de su propio handler -nunca `404`, nunca la receta genérica de esta etapa.

**Reconciliación honesta de pruebas**: **35 pruebas nuevas** (`3425 + 35 = 3460`). AST y pytest coinciden exactamente: `3460` en ambos. **Focalizadas: `2712 passed`** -conjunto de siete archivos: los cinco archivos centrales modificados (`test_calcular_y_persistir_estadistica.py`, `test_corte_temporal_navegacion.py`, `test_estadistica_repository.py`, `test_generalizacion_juegos.py`, `test_migracion_0006_amplia_tipo_estadistica.py`) más los dos precedentes relevantes (`test_consecutivos.py`, `test_coocurrencia.py`).

**Validación real completa del usuario en Windows, PostgreSQL y navegador -evidencia atribuida al usuario, no ejecutada por Claude:** entorno real confirmado -Python `3.14.6`, FastAPI `0.141.1`, Pydantic `2.13.5`, httpx `0.28.1`, pytest `9.1.1`, `pip check` limpio. Pruebas focalizadas reales: `2712 passed`. Suite completa real: `3460 passed`. Auditoría estructural real: `RutasGet: 43`, `Recetas: 43`, **plantillas directas de páginas estadísticas: `43`** (una auditoría auxiliar obtuvo inicialmente `45` al contar recursivamente los dos parciales `control_corte_temporal.html` y `navegacion_colorloto.html` -error del comando auxiliar, corregido excluyendo los parciales, nunca un defecto del código), `36` con canvas, `37` etiquetas `<canvas>`, `31` pestañas ColorLoto, `6` migraciones, revisión Alembic `0006`, `tipo_estadistica: character varying(100)`, longitud `31`, ruta genérica y literal de ColorLoto confirmadas cada una exactamente una vez. PostgreSQL real: se reutilizó el contenedor persistente ya activo en el puerto 5432 (`loteria-predictor-fase2-final-postgres-1`, PostgreSQL 16) -el servicio `postgres` del Compose actual no estaba ejecutándose, y un intento auxiliar de iniciarlo creó un contenedor transitorio que falló porque el puerto ya estaba ocupado por el contenedor persistente correcto; se identificó el contenedor correcto y se eliminó únicamente el transitorio en estado `created`, sin tocar el persistente. Caché global inicial `202`, identidades iniciales de AE-34 `0`. Alcance Git real: exactamente 12 archivos, sin commit ni push.

**Contrato HTTP real**, Uvicorn en `127.0.0.1:8008` (PID lanzador reportado `6088`, PID real que escuchaba `20656`): seis solicitudes iniciales válidas en `200`, las seis con título correcto, tabla correcta, exactamente cuatro filas, sin canvas, selector de corte correcto y corte preservado; seis cache hits posteriores sin filas nuevas; corte vacío idéntico a ausencia; cuatro cortes inválidos (`0`, `-1`, texto, espacio) en `422`. **Aislamiento de ColorLoto confirmado real**: la ruta literal respondió `200`, atendida por su propio handler, sin crear ni modificar identidades de AE-34, nunca a través de la receta genérica. Tres slugs realmente desconocidos en `404`. Creación controlada de una séptima identidad (Baloto, corte `2693`, cache hit confirmado): caché global `202→209`; **0** errores reales en logs.

**Siete identidades finales exactas**: `BALOTO` histórico/corte `2693`/corte `2694`, `BALOTO_REVANCHA` histórico/corte `2694`, `MILOTO` histórico/corte `588` -3 juegos distintos, 2 hashes distintos, 3 sin corte, 4 con corte, 28 filas auditadas, caché final `209`. **Auditoría matemática y del JSON real**, todas las comprobaciones en `True`: identidades exactas, identidad correcta, hashes correctos, estructura exterior e interior correcta, **valores de caché como strings correctos** (`"0"`…`"3"`, confirmado como contrato real, no defecto), orden de caché correcto, **conversión entera del View Model correcta**, totales correctos, frecuencias correctas, conservación de masa correcta, validez correcta, cache hit HTTP confirmado.

**Diez incidentes reales, exclusivamente en comandos auxiliares, ninguno un defecto de AE-34, documentados con honestidad**: (1) error de comillas/Python en una consulta de dependencias; (2) el servicio `postgres` del Compose actual no estaba activo; (3) el intento de iniciarlo falló por el puerto 5432 ya ocupado por el contenedor persistente correcto; (4) se creó y eliminó únicamente un contenedor transitorio en estado `created`, sin tocar el persistente; (5) una auditoría estructural contó inicialmente 45 plantillas al incluir recursivamente los dos parciales -corregido a 43 páginas directas; (6) un bloque se ejecutó accidentalmente desde una carpeta antigua de AE-5 y falló antes de actuar; (7) un bloque eligió el intérprete Python global sin Uvicorn instalado -error de selección, no de código; (8) una auditoría SQL usó la función inexistente `jsonb_object_length`, corregida comparando claves exactas con `jsonb_object_keys`; (9) una primera auditoría del JSON asumió incorrectamente que `valor` era un número JSON -el contrato real y correcto lo serializa como string, documentado arriba con precisión; (10) un traceback de Python no se mostró con claridad en PowerShell, sustituido por una auditoría SQL explícita.

**Revisión visual real**, cita literal del usuario: "no vi errores en las paginas". Cierre operativo real: Uvicorn ya había sido detenido por un bloque auxiliar anterior a la comprobación final -el puerto `8008` estaba libre y no existía ningún proceso que detener en ese momento, comportamiento operativo normal, no un problema; PostgreSQL persistente continuó activo, las siete identidades se conservaron como evidencia, 12 archivos Git sin diferencias de alcance, sin commit ni push.

**Evidencia propia del sandbox** (distinta de la evidencia real del usuario): aplicación limpia del parche provisional sobre la base (`--check`/aplicación real/`--reverse --check`/`diff --check`, todos exitosos), alcance de 12 archivos, árbol de 264 archivos/176 Python, mismos conteos estructurales confirmados de forma independiente.

Con esta evidencia real completa del usuario -entorno, pytest, PostgreSQL, HTTP, aislamiento de ColorLoto, auditoría matemática y del JSON, diez incidentes operativos documentados con honestidad, revisión visual y cierre operativo-, **AE-34 queda validada.** AE-28, el mantenimiento global, AE-29, AE-30, AE-31, AE-32 y AE-33 permanecen validados e intactos. AE-35 no fue implementada. Machine Learning todavía no ha comenzado.

**Checkpoint validado (Etapa AE-35, Data Quality Gate para Machine Learning -primer checkpoint exclusivamente documental de todo el proyecto, sin conectar ninguna visualización nueva):** formaliza la transición controlada hacia Machine Learning autorizada por el usuario, resolviendo con evidencia real una contradicción existente en la propia documentación del proyecto.

**Contradicción documental real, encontrada y resuelta**: `ROADMAP.md` declaraba formalmente que la Fase 3 (Machine Learning) depende únicamente de la Fase 2 (adquisición de datos) -el Data Quality Report de Fase 2 como gate de entrada, nunca de completar la Fase 5 (estadísticas descriptivas)-, mientras una sección informal, redactada en una etapa muy anterior (Etapa W/Y, cuando solo existían dos métricas numéricas conectadas) y nunca reevaluada desde entonces, seguía recomendando implícitamente "una estadística más" en cada etapa reciente. **`GenerarReporteCalidadDatos` (`application/use_cases/generar_reporte_calidad_datos.py`) ya existía en el código, con su propio docstring declarando explícitamente que sirve como validación de calidad antes de entrenar modelos** -confirmando en el propio código, no por interpretación, que el gate real siempre fue este reporte, nunca la Fase 5. Las 17 funciones estadísticas todavía no conectadas (agrupables en 7 familias reales: distribuciones adicionales, atrasos/intervalos, repetición de superbalota, frecuencia temporal de números, frecuencia temporal de superbalota, comparación por ventana, e independencia/bondad de ajuste) quedan documentadas como backlog descriptivo -**ninguna es prerequisito técnico de Machine Learning**.

**Data Quality Gate real, ejecutado por el usuario en Windows con PostgreSQL real -evidencia atribuida al usuario, no ejecutada por Claude:** PostgreSQL real disponible (contenedor `loteria-predictor-fase2-final-postgres-1`), revisión Alembic `0006`, rama `develop`, HEAD `1772605b78dead389533426514a46ecf382439ec`, árbol Git limpio, transacción de diagnóstico exclusivamente de solo lectura -caché global antes y después idéntica (`209 → 209`), PostgreSQL/caché/árbol Git sin modificar, Uvicorn nunca iniciado.

**Reporte oficial de calidad real**: BALOTO 625 sorteos (`2081`-`2705`, `2021-05-01` a `2026-09-05`), BALOTO_REVANCHA 625 sorteos (mismo rango de números y fechas que Baloto, juego independiente), COLORLOTO 215 sorteos (`1`-`215`, `2024-08-15` a `2026-09-03`), MILOTO 70 sorteos (`532`-`601`, `2026-05-07` a `2026-09-04`) -los cuatro juegos con **cero huecos y 100% de cobertura** en su rango real. Once controles independientes del histórico (grupos duplicados, cantidades incorrectas de números/colores, números fuera de rango, superbalota mal ubicada o fuera de rango, colores de otro juego, inversiones de fecha, días de semana incorrectos, fechas futuras) terminaron **todos en cero**. Estado inicial de Machine Learning: `0` modelos, `0` métricas, `0` predicciones -el subsistema arranca desde un estado limpio real.

**Interpretación precisa de `sorteos_incompletos`, verificada directamente en el código, no asumida**: `SincronizarSorteos` incrementa este contador cuando `DrawDetail.advertencias` no está vacío (`if draw.advertencias: incompletos += 1`) -una advertencia puede ser información auxiliar (p. ej. no poder extraer la tabla de premios), nunca necesariamente un defecto del sorteo en sí. **Confirmado leyendo el código real**: un sorteo con advertencia todavía debe pasar la validación de dominio de `RegistrarSorteo` (`SorteoInvalidoError`/`ValueError` lo desvían a `errores`/fallidos, nunca a `importados`) antes de contar como importado -los once controles independientes de estructura confirman que los registros efectivamente persistidos tienen cantidades, rangos, superbalota, fechas y orden temporal correctos. **Limitación real, documentada con honestidad**: el texto exacto de cada advertencia de parseo (`advertencias_parseo`) se genera solo como valor de retorno transitorio de `SincronizarSorteos.ejecutar()` -verificado directamente que `EjecucionSincronizacion.detalle_errores` únicamente recibe los `errores` de obtención/validación de dominio, nunca el contenido de `advertencias_parseo`- así que el contenido concreto de esas advertencias pasadas no puede recuperarse ni se inventa aquí. Conclusión autorizada: estos contadores no bloquean AE-35 ni un primer modelo basado en los campos estructuralmente auditados; AE-36 no debe usar tablas de premios, acumulados u otros datos auxiliares sin una auditoría específica adicional propia.

**Decisión: GO CONDICIONAL para Machine Learning.** **GO** para iniciar AE-36 con modelos independientes de Baloto y Baloto Revancha -nunca mezclados como si fueran un único histórico, pese a compartir fechas de sorteo. **NO-GO temporal para MiLoto**, por insuficiencia real de histórico (70 sorteos). **POSPUESTO para ColorLoto** (215 sorteos y una representación del objetivo estructuralmente distinta a los juegos numéricos). Esta decisión significa preparación aprobada, no que Machine Learning ya esté implementado.

**Contrato recomendado para AE-36, documentado aquí sin implementar**: probabilidad marginal de aparición por número, clasificadores binarios calibrados y regularizados, un modelo independiente por juego, primera implementación limitada a Baloto y Baloto Revancha, Regresión Logística regularizada y calibrada como primer candidato -`scikit-learn` **no se instala en esta etapa**; su incorporación y la verificación real de compatibilidad con Python `3.14.6` pertenecen a AE-36. Baselines obligatorios: probabilidad uniforme, frecuencia histórica acumulada, frecuencia en ventana reciente, sorteo anterior como control ingenuo. Evaluación obligatoria: división estrictamente cronológica, características calculadas exclusivamente con sorteos anteriores al objetivo, validación walk-forward (o equivalente temporal), test final completamente intacto hasta el final del proceso. Log Loss y Brier Score como métricas principales; Precision@K y Recall@K como métricas secundarias -**`accuracy` global nunca como métrica principal**, dado el desbalance extremo del problema. Ninguna afirmación de capacidad predictiva, ventaja económica ni mejora real hasta superar los cuatro baselines fuera de muestra.

**Alcance exclusivamente documental**: README.md, ROADMAP.md, ARCHITECTURE.md -ningún código Python, plantilla, migración, dependencia ni prueba fue modificado. Confirmado por diff completo del registro de hashes: los otros 261 archivos permanecen byte a byte idénticos, incluidos los 6 motores, `models.py`, `main.py`, `exceptions.py`, las 6 migraciones y las 43 rutas/recetas/View Models/plantillas de AE-1 a AE-34. Suite completa reconfirmada sin cambios: `3460 passed`; focalizada previa: `2712 passed`. AE-34 y todos los checkpoints anteriores permanecen validados e intactos. **AE-35 queda validada.** Machine Learning todavía no fue implementado -**AE-36 será la primera etapa con implementación real de Machine Learning**, comenzando exclusivamente con Baloto y Baloto Revancha.

**Checkpoint validado (Etapa AE-36, primera implementación real de Machine Learning de todo el proyecto):** primer baseline entrenable para estimar la probabilidad marginal de aparición de cada número principal, evaluado en memoria, sin persistir nada y sin generar ninguna predicción futura ni recomendación de apuesta. **La validación confirma la corrección metodológica, la reproducibilidad y la infraestructura experimental del pipeline -nunca capacidad predictiva.**

**Entorno real del usuario, validado en Windows -evidencia atribuida al usuario, no ejecutada por Claude:** Python `3.14.6`, NumPy `2.5.3`, SciPy `1.18.1`, scikit-learn `1.9.1`, pytest `9.1.1`, FastAPI `0.141.1`, Pydantic `2.13.5`, httpx `0.28.1`. `scikit-learn>=1.9` instalado mediante wheel precompilado CPython 3.14 para Windows AMD64 -sin compilación local; `pip check` sin dependencias rotas. Ajuste real de Regresión Logística, calibración real con `CalibratedClassifierCV` y `PredefinedSplit` real, probabilidades finitas, Log Loss y Brier Score calculados correctamente -microajuste real del gate: Log Loss `0.18260354`, Brier Score `0.02791585`, calibración real `True`, probabilidades finitas `True`.

**Pruebas automatizadas reales**: focalizadas de Machine Learning `80 passed`; suite completa `3540 passed`. Reconciliación (`3460 + 80 = 3540`) reconfirmada también por AST en el sandbox.

**PostgreSQL real**: contenedor persistente reutilizado `loteria-predictor-fase2-final-postgres-1`, `/var/run/postgresql:5432 - accepting connections`, revisión Alembic `0006`. Toda la evaluación se ejecutó dentro de transacciones de **solo lectura** (`transaction_read_only=on`). Caché `209 → 209`; `modelos` `0 → 0`; `metricas_modelo` `0 → 0`; `predicciones` `0 → 0` -**PostgreSQL permaneció exactamente sin cambios**, ningún modelo, métrica ni predicción fue persistida, ningún binario de modelo fue generado.

**Dataset e histórico reales, Baloto y Baloto Revancha siempre evaluados por separado**: 625 sorteos originales cada uno (`2081`-`2705`, rango `1..43`, 5 números principales), 575 sorteos elegibles, 24725 filas del dataset, calentamiento hasta el sorteo `2130` (primer sorteo elegible `2131`), test final `2591..2705` (115 sorteos, 4945 filas), 45 bloques walk-forward, semilla `42`. Confirmado real: orden temporal correcto, test final intacto hasta la evaluación, ningún sorteo dividido entre particiones, entrenamiento expansivo, calibración posterior al bloque base, dataset candidato-etiqueta correcto, las siete features exactas, los cuatro baselines exactos, métricas finitas, dos ejecuciones completas por juego con resultados idénticos, Baloto y Baloto Revancha nunca mezclados, MiLoto y ColorLoto rechazados explícitamente.

**Resultado científico real -negativo, conservado sin reinterpretaciones promocionales**:

| Juego | Log Loss modelo | Log Loss uniforme | Brier modelo | Brier uniforme | Mejora Log Loss | Mejora Brier |
|---|---:|---:|---:|---:|---|---|
| BALOTO | 0.35946103 | 0.35944515 | 0.10276211 | 0.10275825 | **False** | **False** |
| BALOTO_REVANCHA | 0.36131846 | 0.35944515 | 0.10315531 | 0.10275825 | **False** | **False** |

**El baseline uniforme fue mejor que el modelo logístico calibrado en Log Loss y Brier Score -las dos métricas principales- para ambos juegos.** Precision@5 y Recall@5 (secundarias) no cambian esta conclusión: Baloto `0.1009`/`0.1009` (modelo) vs. `0.0957`/`0.0957` (uniforme); Baloto Revancha `0.0870`/`0.0870` (modelo) vs. `0.1113`/`0.1113` (uniforme) -tampoco constituyen evidencia de señal, y nunca sustituyen a Log Loss/Brier. **No se observó evidencia de mejora conjunta fuera de muestra para Baloto ni para Baloto Revancha.**

**Rendimiento real**: tiempo de pipeline `2.502 s` (Baloto) / `2.526 s` (Baloto Revancha). Memoria física relevante: **pico de Working Set** `189.18 MB` (Baloto) / `188.27 MB` (Baloto Revancha) -medido dentro del proceso real de Python mediante `K32GetProcessMemoryInfo`. El `Private Usage` (~`1.14 GB` en ambos) es memoria virtual/pagefile comprometida, **no RAM física residente** -se documenta como información complementaria, nunca como el consumo físico real.

**Siete incidentes reales, exclusivamente en comandos auxiliares de validación, ninguno un defecto de AE-36**: (1) un arreglo anidado de PowerShell contó el estado Git como un solo elemento; (2) un primer script temporal no encontró `app` por faltar `backend` en `PYTHONPATH`; (3) PowerShell 5.1 rechazó un `if/else` embebido en una propiedad; (4) `Start-Process` no entregó correctamente `ExitCode` en el primer medidor externo; (5) una medición externa inicial produjo `4.42 MB` por medir el proceso lanzador, no el proceso real de Python -descartada, nunca una medición válida; (6) la medición final dentro del proceso real corrigió el dato a los ~189 MB de pico ya reportados arriba; (7) un primer medidor interno basado en `psapi` sin firmas explícitas devolvió `None`, presentado erróneamente como `0.00 MB` -también descartado.

**Nota metodológica obligatoria para AE-37**: el test final `2591..2705` ya quedó **consumido** por esta evaluación -no debe reutilizarse como holdout intacto para seleccionar features, hiperparámetros o modelos en ninguna etapa futura; una etapa posterior deberá usar evaluación anidada/walk-forward correctamente preregistrada o reservar sorteos futuros como un nuevo holdout genuino.

**Cierre exclusivamente de estado**: únicamente se actualizaron marcadores de estado en los docstrings de los 9 módulos funcionales de `application/ml/` y del caso de uso (`PROVISIONAL` → `validada`), además de esta documentación -confirmado que el AST ejecutable de los 10 archivos Python permanece idéntico antes y después (solo cambió el texto de los docstrings), y que los 10 archivos de prueba permanecen byte a byte idénticos al parche provisional. Suite completa reconfirmada sin cambios: `3540 passed`.

Con esta evidencia real completa del usuario -entorno, PostgreSQL, dataset, métricas completas, rendimiento y reproducibilidad-, **AE-36 queda validada como primer baseline de Machine Learning: metodología, reproducibilidad y ausencia de fuga temporal confirmadas; ausencia de señal predictiva fuera de muestra también confirmada, y conservada como resultado científico válido.** AE-35 y checkpoints anteriores permanecen validados e intactos. MiLoto continúa en NO-GO temporal. ColorLoto continúa pospuesto. AE-37 no fue implementada -y no podrá reutilizar el test `2591..2705` de esta etapa como holdout intacto.

**Checkpoint validado (Etapa AE-37, evaluación temporal anidada y ablación controlada del baseline de AE-36):** motivada directamente por el resultado negativo de AE-36 -el baseline uniforme superó al modelo logístico calibrado en Log Loss y Brier Score para ambos juegos-, AE-37 exploró honestamente si, bajo regularización controlada y ablación de features, existía alguna señal exploratoria consistente. **La validación confirma la corrección metodológica, el aislamiento temporal, la evaluación anidada y la reproducibilidad del pipeline -vuelve a obtener un resultado científico negativo, y eso es exactamente lo que queda validado, no una mejora predictiva.**

**Entorno real del usuario, validado en Windows -evidencia atribuida al usuario, no ejecutada por Claude:** Python `3.14.6`, pytest `9.1.1`, httpx `0.28.1`, scikit-learn `1.9.1`, NumPy `2.5.3`, SciPy `1.18.1`. PostgreSQL real, contenedor `loteria-predictor-fase2-final-postgres-1`, puerto `5432`, revisión Alembic `0006`, rama `feature/ae37-evaluacion-temporal-anidada-robustez-ml`.

**Contrato temporal real confirmado, ejecutado dos veces por juego**: la consulta al repositorio recibió exclusivamente `hasta_numero_sorteo=2590`; máximo sorteo devuelto `2590`; `510` sorteos recibidos (`2081`-`2590`); `460` elegibles; `19780` filas del dataset; `18` bloques externos; `360` sorteos externos evaluados; `15480` filas externas; primer sorteo externo `2231`, último `2590`. El intervalo consumido por AE-36 (`2591..2705`) **no fue cargado, consultado ni reutilizado**. El próximo holdout genuino permanece definido desde `2706`, intacto hasta acumular al menos **100 sorteos nuevos** por juego -no se consumió en esta etapa.

**Aislamiento real de scikit-learn, validado con AST**: `modelo.py` es el único archivo de `application/ml/` que importa scikit-learn (`ast.Import`/`ast.ImportFrom`, nunca coincidencia de texto); `evaluacion.py` ya no importa `sklearn` y obtiene `VERSION_SKLEARN` desde `modelo.py`, con el mismo valor de versión que antes. Las 80 pruebas originales de AE-36 permanecen pasando sin ninguna modificación.

**Resultados reales agregados -negativos para ambos juegos, conservados sin reinterpretación**:

| Juego | Log Loss modelo | Log Loss uniforme | Brier modelo | Brier uniforme | Bloques ganados (ambas métricas) | Bloques perdidos |
|---|---:|---:|---:|---:|---:|---:|
| BALOTO | 0.35960515 | 0.35944515 | 0.10279144 | 0.10275825 | 6 | 12 |
| BALOTO_REVANCHA | 0.35968580 | 0.35944515 | 0.10280523 | 0.10275825 | 9 | 9 |

**El modelo fue ligeramente peor que el uniforme en las dos métricas principales agregadas para ambos juegos.** Baloto ganó solo 6 de 18 bloques -sin evidencia de mejora robusta. Baloto Revancha dividió 9/9 en bloques ganados/perdidos, pero **el agregado permanece ligeramente por debajo del uniforme en ambas métricas** -la división 9/9 no se convierte en una afirmación positiva.

**Frecuencia de selección real**: Baloto -`completo_C_0_1`: 6 bloques, `frecuencias_C_0_1`: 12 bloques, los otros cuatro candidatos: 0. Baloto Revancha -`completo_C_0_1`: 5, `completo_C_1`: 1, `completo_C_10`: 1, `frecuencias_C_0_1`: 9, `frecuencias_C_1`: 1, `frecuencias_C_10`: 1.

**Reproducibilidad real confirmada**: cada juego ejecutado dos veces con semilla `42` -selecciones idénticas, métricas idénticas, fronteras temporales idénticas, reportes idénticos, en ambos juegos.

**Tiempo y memoria reales** (medidos dentro de cada proceso Python real mediante una corrección de interoperabilidad Win32 de 64 bits): Baloto -primera ejecución `9.797 s`, segunda `8.570 s`, pico Working Set `183.23 MB`, memoria privada `182.15 MB`. Baloto Revancha -primera `10.418 s`, segunda `9.721 s`, pico Working Set `182.68 MB`, memoria privada `178.89 MB`. La memoria privada es la del proceso completo, no un consumo adicional exclusivo del modelo.

**PostgreSQL real, sin persistencia ni efectos colaterales**: ambos juegos ejecutados dentro de transacciones `transaction_read_only=on`; revisión Alembic `0006`; caché `209 → 209`; `modelos` `0 → 0`; `metricas_modelo` `0 → 0`; `predicciones` `0 → 0`; PostgreSQL modificado `False`; Uvicorn iniciado `False`.

**Cinco incidentes reales, exclusivamente en comandos auxiliares de validación, ninguno un defecto de AE-37**: (1) el primer parche provisional de AE-37 incumplía el aislamiento declarado porque `evaluacion.py` todavía importaba `sklearn` -invalidado antes de la validación real, corregido centralizando la versión en `modelo.py`; (2) una colección vacía de `Get-StatusLines` se convirtió en `$null` bajo `Set-StrictMode`, provocando un error al consultar `.Count`; (3) la salida vacía de `git diff --cached --name-only` se convirtió en `$null`, provocando un error al ejecutar `.Trim()`; (4) el conteo físico inicial incluyó 43 archivos locales ignorados por Git (`.pytest_cache`, evidencia HTML histórica de sincronizaciones), produciendo un total superior a 290 -el conteo correcto se rehízo con archivos visibles para Git; (5) el medidor Win32 inicial no declaró `GetCurrentProcess.restype`, produciendo `WinError 6` -corregidos los tipos de interoperabilidad de 64 bits antes de ejecutar los modelos. Ninguno modificó el código fuente, alteró PostgreSQL o cambió las métricas; las ejecuciones fallidas terminaron antes del experimento o hicieron rollback; los entornos y diagnósticos temporales fueron eliminados al finalizar correctamente.

**Cierre exclusivamente de estado**: se actualizaron marcadores `PROVISIONAL` → `validada` en comentarios/docstrings de 4 archivos Python (`modelo.py`, `tipos.py`, `evaluacion_anidada.py`, el caso de uso) -AST ejecutable idéntico confirmado, ignorando únicamente comentarios y docstrings- además de esta documentación. Los tres archivos de prueba nuevos y las 80 pruebas originales de AE-36 permanecen byte a byte idénticos. `evaluacion.py` no fue tocado durante este cierre -su corrección funcional ya pertenece al parche provisional corregido. Suite completa reconfirmada: `3588 passed`.

Con esta evidencia real completa del usuario -entorno, PostgreSQL, contrato temporal, métricas agregadas completas por bloque, frecuencia de selección, reproducibilidad, rendimiento-, **AE-37 queda validada como protocolo de evaluación temporal anidada y ablación controlada: metodología, aislamiento temporal y reproducibilidad confirmados -nunca capacidad predictiva.** No se observó evidencia de mejora agregada frente al baseline uniforme para ningún juego. No se generaron ni persistieron predicciones, modelos o métricas. AE-36 y checkpoints anteriores permanecen validados e intactos -incluido su resultado científico negativo, que esta etapa no reinterpreta. MiLoto continúa en NO-GO temporal, ColorLoto continúa pospuesto. El próximo holdout genuino (`2706` en adelante) permanece intacto. AE-38 no fue implementada.

**Checkpoint validado (Etapa AE-38, comparación exploratoria prerregistrada entre Regresión Logística y Random Forest, misma evaluación temporal anidada de AE-37):** motivada por AE-37, que no encontró mejora agregada frente al baseline uniforme; AE-38 comprobó si Random Forest aporta alguna señal exploratoria adicional, reutilizando exclusivamente los datos de desarrollo ya permitidos (`2081..2590`). **La validación confirma la corrección metodológica y operativa del protocolo -no demuestra capacidad predictiva.**

**Entorno real del usuario, validado en Windows -evidencia atribuida al usuario, no ejecutada por Claude:** Python `3.14.6`, pytest `9.1.1`, httpx `0.28.1`, scikit-learn `1.9.1`, NumPy `2.5.3`, SciPy `1.18.1`, `pip check` limpio. Pruebas reales: nuevas de AE-38 `46 passed`; suite completa `3634 passed`; reconciliación AST `3588 + 46 = 3634`.

**Contrato temporal real confirmado, verificado directamente sobre el JSON de resultados completos del usuario, con una sola consulta al repositorio por ejecución** (`hasta_numero_sorteo=2590` exclusivamente): `510` sorteos recibidos (`2081`-`2590`), `460` elegibles, `19780` filas, `18` bloques externos contiguos y sin solapamiento desde `2231` hasta `2590` (`20` sorteos y `860` filas por bloque), `360` sorteos externos, `15480` filas externas, entrenamiento estrictamente expansivo entre bloques, los doce candidatos preregistrados presentes en cada una de las 18 selecciones internas de ambos juegos. **Ningún sorteo posterior a `2590` aparece en ningún bloque, frontera de entrenamiento o consulta** -confirmado verificando cada uno de los 18 bloques de ambos juegos, no solo el agregado. El intervalo `2591..2705` permaneció completamente excluido. PostgreSQL real: `transaction_read_only=on`; caché `209 → 209`; `modelos`/`metricas_modelo`/`predicciones` `0 → 0` -idénticos antes y después en ambas ejecuciones de ambos juegos.

**Reproducibilidad real confirmada de forma exacta, verificada por hash, no solo por igualdad de campos**: dos ejecuciones completas por juego produjeron el **mismo hash de reporte exacto** -BALOTO `9ebdaa50f580f5e52d85d04a98162425372c51c57069e6d22b21a0ea4f23d08f`, BALOTO_REVANCHA `38d48657b1078d7970bd7d51972c669f2e34db8b81a366ae4eb55c4099bcca4f`, confirmados en ambas ejecuciones de cada juego.

**Resultados científicos reales -negativos para ambos juegos, recalculados de forma independiente desde el JSON crudo y coincidentes hasta la duodécima cifra decimal con lo reportado**:

| Juego | Log Loss modelo | Log Loss uniforme | Brier modelo | Brier uniforme | Ganados | Perdidos | Mixto |
|---|---:|---:|---:|---:|---:|---:|---:|
| BALOTO | 0.359581731744 | 0.359445147513 | 0.102784721114 | 0.102758247701 | 2 | 15 | 1 |
| BALOTO_REVANCHA | 0.360092882013 | 0.359445147513 | 0.102895901497 | 0.102758247701 | 5 | 12 | 1 |

**El modelo seleccionado dinámicamente no superó al baseline uniforme de forma agregada fuera de muestra en ninguno de los dos juegos** -Precision@5/Recall@5 del modelo (BALOTO `0.113888888889`, Revancha `0.108888888889`) tampoco superaron al uniforme (`0.123333333333`/`0.120000000000` respectivamente), y son métricas secundarias que en ningún caso alteran la conclusión principal.

**Frecuencia de selección real -Random Forest fue seleccionado con frecuencia por la evaluación interna, lo cual nunca se interpreta aquí como evidencia de capacidad predictiva**: BALOTO -Random Forest 15/18 bloques, logística 3/18 (`rf_frecuencias_n100_d5`:9, `rf_completo_n100_d5`:5, `rf_completo_n200_d10`:1, `frecuencias_C_0_1`:3). BALOTO_REVANCHA -Random Forest 14/18, logística 4/18 (`rf_completo_n100_d5`:5, `rf_frecuencias_n100_d5`:4, `rf_frecuencias_n200_d10`:2, `rf_completo_n200_d10`:3, `completo_C_10`:1, `completo_C_1`:1, `frecuencias_C_10`:1, `frecuencias_C_1`:1).

**Baselines agregados completos** -BALOTO: frecuencia acumulada `0.362214690687`/`0.103243499897`, ventana 20 `0.403457105475`/`0.107435206832`, sorteo anterior `1.497988794102`/`0.193245603643` (Log Loss/Brier). BALOTO_REVANCHA: `0.361482865204`/`0.103107974926`, `0.401569221175`/`0.107242759291`, `1.495342867430`/`0.192898810293`.

**Tiempo y memoria reales -medición válida del árbol completo de procesos Python, corrigiendo una medición anterior inválida de ~4.51 MB que solo observaba el lanzador del entorno virtual, expresamente descartada**: BALOTO -tiempo Python `557.9587288999464 s`, pico de Working Set del árbol `373.15234375 MB` (individual `369.671875 MB`), 556 muestras, máximo 2 procesos simultáneos. BALOTO_REVANCHA -tiempo Python `568.4538222999545 s`, pico de Working Set del árbol `374.2890625 MB` (individual `369.8125 MB`), 566 muestras, máximo 2 procesos simultáneos. El Working Set es la evidencia real de RAM física residente; el espacio privado/virtual (~1.33 GB) se menciona únicamente como memoria virtual comprometida, nunca como RAM física.

**Cierre exclusivamente de estado**: se actualizaron marcadores `PROVISIONAL` → `validada` en comentarios/docstrings de 4 archivos Python (`modelo.py`, `tipos.py`, `comparacion_familias.py`, el caso de uso) -AST ejecutable idéntico confirmado, ignorando únicamente comentarios y docstrings. Los tres archivos de prueba nuevos, las 48 pruebas de AE-37 y las 80 pruebas originales de AE-36 permanecen byte a byte idénticos. `evaluacion.py`, `evaluacion_anidada.py`, el caso de uso original de AE-37, los repositorios e interfaces de resultados históricos, `models.py`, las seis migraciones, `main.py` y `requirements.txt` no fueron tocados. **Confirmado con AST, no solo documentado**: `modelo.py` sigue siendo el único archivo de `application/ml/` que importa scikit-learn.

Con esta evidencia real completa del usuario -entorno, PostgreSQL, contrato temporal verificado bloque a bloque, métricas agregadas recalculadas de forma independiente, frecuencia de selección, reproducibilidad por hash exacto, tiempo y memoria reales-, **AE-38 queda validada como protocolo de comparación exploratoria: metodología, aislamiento temporal, calibración por familia y reproducibilidad confirmados -nunca capacidad predictiva.** No se observó evidencia de mejora agregada frente al baseline uniforme para ningún juego. No se generaron ni persistieron predicciones, modelos o métricas. AE-37 y checkpoints anteriores permanecen validados e intactos -esta etapa no reescribe ni reinterpreta su resultado científico negativo. El holdout genuino (`2706` en adelante, mínimo 100 sorteos nuevos) permanece completamente intacto -nunca consultado ni cargado. MiLoto continúa en NO-GO temporal, ColorLoto continúa pospuesto. AE-39 no fue implementada.

**Checkpoint validado (Etapa AE-39, cuantificación de incertidumbre y regla de parada científica):** después de tres resultados negativos consecutivos (AE-36, AE-37, AE-38), AE-39 no prueba ninguna familia nueva de modelos -hacerlo sin antes cuantificar la incertidumbre constituiría *model chasing*. Analiza estadísticamente las diferencias externas ya obtenidas en AE-38 y formaliza una regla de parada de desarrollo reproducible. **La validación confirma la metodología del análisis de incertidumbre y su reproducibilidad -no demuestra capacidad predictiva.**

**Entorno real del usuario, validado en Windows -evidencia atribuida al usuario, no ejecutada por Claude:** Python `3.14.6`, pytest `9.1.1`, httpx `0.28.1`, scikit-learn `1.9.1`, NumPy `2.5.3`, SciPy `1.18.1`, `pip check` limpio. Pruebas reales: nuevas de AE-39 `47 passed`; suite completa `3681 passed`, `0` omitidas; reconciliación AST `3634 + 47 = 3681`. AE-39 **no consultó PostgreSQL y no reentrenó ningún modelo** -analizó exclusivamente el JSON ya validado de AE-38.

**Configuración real aplicada**: unidad de remuestreo -18 bloques externos completos por juego, nunca las 15480 filas candidato-sorteo tratadas como observaciones independientes; orientación `uniforme - modelo` (positivo favorece al modelo); bootstrap percentil bilateral del 95%; `10000` réplicas; semilla `42`; prueba de signos binomial exacta bilateral; dos ejecuciones reales e idénticas de AE-38 analizadas por juego.

**Resultados científicos reales, completos**:

| Juego | Diferencia LL (uniforme-modelo) | IC 95% LL | Valor p (signos) | Diferencia Brier | IC 95% Brier | Valor p (signos) |
|---|---:|---|---:|---:|---|---:|
| BALOTO | `-0.00013658423122096653` | `[-0.00021660263564396667, -0.000051182433795544704]` | `0.007537841796875` | `-0.000026473412656978655` | `[-0.000043538774653204215, -0.000007742476328112663]` | `0.001312255859375` |
| BALOTO_REVANCHA | `-0.0006477345004085466` | `[-0.0011084023404096485, -0.0002306965245045197]` | `0.09625244140625` | `-0.0001376537952658554` | `[-0.00023711527779795777, -0.00005015728660637066]` | `0.237884521484375` |

**Los cuatro estimadores principales son negativos y sus cuatro intervalos del 95% quedan completamente por debajo de cero: con la orientación `uniforme - modelo`, esto favorece al baseline uniforme en ambos juegos y en ambas métricas principales.** Métricas secundarias -BALOTO: Precision@5/Recall@5 modelo `0.1138888888888889` frente a uniforme `0.12333333333333335`; BALOTO_REVANCHA: modelo `0.1088888888888889` frente a uniforme `0.12000000000000001`. Hashes de reproducibilidad de los reportes de AE-38 analizados: BALOTO `9ebdaa50f580f5e52d85d04a98162425372c51c57069e6d22b21a0ea4f23d08f`, BALOTO_REVANCHA `38d48657b1078d7970bd7d51972c669f2e34db8b81a366ae4eb55c4099bcca4f`.

**Decisión, por juego, sin mezclar históricos**: `BALOTO: NO_GO_SIN_EVIDENCIA_SUFICIENTE` -- `BALOTO_REVANCHA: NO_GO_SIN_EVIDENCIA_SUFICIENTE`.

**Cinco incidentes reales, exclusivamente en comandos auxiliares de validación, ninguno un defecto de AE-39**: (1) fragmentación de un bloque PowerShell que separó `elseif`, `try` y `finally`; (2) una expresión PowerShell inválida al consultar una rama local; (3) un `python -c` afectado por el manejo de comillas de PowerShell; (4) el primer intento del auditor sin `PYTHONPATH`, que produjo `ModuleNotFoundError: No module named 'app'`; (5) corregido posteriormente con `PYTHONPATH=backend`, sin modificar el proyecto. Ninguno cambió código, métricas, Git, PostgreSQL ni resultados científicos.

**Cierre exclusivamente de estado**: se actualizaron marcadores `PROVISIONAL` → `validada` en comentarios/docstrings de los 2 archivos Python que aún los contenían (`incertidumbre.py`, `tipos.py`) -AST ejecutable idéntico confirmado, ignorando únicamente docstrings. Las 47 pruebas nuevas de AE-39 y todas las pruebas anteriores permanecen byte a byte idénticas. `modelo.py`, `evaluacion.py`, `evaluacion_anidada.py`, `comparacion_familias.py` y los casos de uso validados de AE-36/AE-37/AE-38 no fueron tocados. **Confirmado con AST, no solo documentado**: `modelo.py` sigue siendo el único archivo de `application/ml/` que importa scikit-learn.

**Sin persistencia, sin predicciones, sin capacidad predictiva declarada**: no se escribió en `modelos`/`metricas_modelo`/`predicciones`; no se generó ningún archivo `.pkl`/`.pickle`/`.joblib`/`.onnx`; no se creó ninguna ruta HTTP, plantilla ni migración.

**La expansión de familias de modelos sobre `2081..2590` queda congelada**: como ningún juego obtuvo evidencia exploratoria de mejora, no se prueba ninguna familia adicional sobre estos mismos bloques observados. Una decisión NO-GO no demuestra que predecir sea matemáticamente imposible -significa que no existe evidencia suficiente en el protocolo evaluado. El desarrollo predictivo solo podrá reabrirse acumulando al menos 100 sorteos nuevos por juego desde `2706`, o mediante una hipótesis nueva y prerregistrada que no se seleccione retrospectivamente a partir de estos mismos resultados.

Con esta evidencia real completa del usuario -entorno, reproducibilidad exacta del bootstrap, intervalos y valores p completos, hashes de los reportes de AE-38 analizados-, **AE-39 queda validada como cuantificación de incertidumbre y regla de parada científica: metodología y reproducibilidad confirmadas -nunca capacidad predictiva.** El intervalo `2591..2705` no fue reutilizado; el próximo holdout genuino permanece intacto desde `2706`. AE-38 y checkpoints anteriores permanecen validados e intactos -ningún resultado negativo previo fue reescrito ni suavizado. MiLoto continúa en NO-GO temporal, ColorLoto continúa pospuesto. AE-40 no fue implementada.

**Checkpoint validado (Etapa AE-40, gate operativo de elegibilidad para la reapertura del holdout de Machine Learning):** tras el NO-GO de AE-39 en ambos juegos, AE-40 implementa exclusivamente un gate determinista que responde una única pregunta: ¿existen al menos 100 sorteos nuevos, completos en numeración y separados por juego, desde el sorteo `2706`, para permitir que una etapa **futura** prerregistre un protocolo antes de observar sus resultados? **La validación confirma el funcionamiento metodológico y operativo del gate -el resultado del gate en sí es negativo: no existen todavía sorteos cargados desde `2706` en la instantánea real evaluada.**

**Entorno real del usuario, validado en Windows -evidencia atribuida al usuario, no ejecutada por Claude:** Python `3.14.6`, PostgreSQL real reutilizado (sin contenedor nuevo), revisión Alembic `0006`, `transaction_read_only=on`. Pruebas reales: `63 passed` (AE-40), `47 passed` (AE-39), suite completa `3744 passed`; reconciliación AST `3681 + 63 = 3744`; `pip check` limpio.

**Consulta real confirmada, verificada directamente contra la sentencia SQL compilada de producción**: exactamente dos consultas agregadas totales -una por juego, cada caso de uso con dos consultas en total (resolución del juego más la consulta agregada). Confirmado sobre el SQL real: `select count(sorteos.numero_sorteo)... count(distinct(sorteos.numero_sorteo))... min(sorteos.numero_sorteo)... max(sorteos.numero_sorteo)... from sorteos where sorteos.juego_id = ... and sorteos.numero_sorteo >= 2706` -solo agregados, filtro exacto por `juego_id`, filtro `numero_sorteo >= 2706`, sin `JOIN`, sin ninguna columna de números ganadores, superbalota, colores, fechas como señal, features ni targets.

**Resultado real, negativo para ambos juegos -recalculado de forma independiente ejecutando la función real de producción con los datos exactos reportados, y coincidente exactamente**:

| Juego | Estado | Total sorteos nuevos | Mínimo | Máximo | Consultas agregadas | Tiempo |
|---|---|---:|---|---|---:|---:|
| BALOTO | `no_elegible_datos_insuficientes` | `0` | `null` | `null` | `1` | `0.0402 s` |
| BALOTO_REVANCHA | `no_elegible_datos_insuficientes` | `0` | `null` | `null` | `1` | `0.0039 s` |

**No existen sorteos cargados desde `2706` en la instantánea real evaluada -no se alcanzó el mínimo de 100 sorteos, no existe todavía una secuencia `2706..2805`.** `numeracion_contigua=true` con cero registros significa exclusivamente que no se detectó ninguna contradicción de continuidad en un conjunto vacío -**nunca** que exista una secuencia real de sorteos. Working Set pico total: `78.49 MB` -medición real del proceso completo, nunca evidencia de Claude.

**PostgreSQL real, sin cambios**: caché `estadisticas` `209 → 209`; `modelos`/`metricas_modelo`/`predicciones` `0 → 0 → 0 → 0`, idénticos antes y después. No se persistieron modelos, métricas ni predicciones. No se generaron predicciones. No se observaron resultados ganadores. **El holdout no fue consumido.**

**Cierre exclusivamente de estado**: se actualizaron marcadores `PROVISIONAL` → `validada` en comentarios/docstrings de los 5 archivos Python de AE-40 (`reapertura.py`, `disponibilidad_holdout_repository.py`, `disponibilidad_holdout_repository_sqlalchemy.py`, el caso de uso, `tipos.py`) -AST ejecutable idéntico confirmado, ignorando únicamente docstrings; el contenido añadido a `tipos.py` en el cierre permanece puramente LF, igual que en el parche provisional corregido. Las 63 pruebas de AE-40 y todas las pruebas anteriores permanecen byte a byte idénticas. Los once archivos protegidos de AE-36/37/38/39 permanecen byte a byte idénticos. **Confirmado con AST, no solo documentado**: `modelo.py` sigue siendo el único archivo de `application/ml/` que importa scikit-learn.

**No se habilita todavía un nuevo prerregistro**: `ELEGIBLE_PARA_PRERREGISTRO` nunca significa GO, evidencia predictiva, autorización para entrenar, para mirar resultados, para consumir el holdout, ni para desplegar -y en esta instantánea real, ni siquiera se alcanzó ese estado. El desarrollo predictivo **no se reabre**.

Con esta evidencia real completa del usuario -entorno, SQL de producción verificado, resultado negativo honesto, PostgreSQL sin cambios-, **AE-40 queda validada como gate operativo de elegibilidad: metodología y funcionamiento confirmados -el resultado del gate en esta instantánea es `NO_ELEGIBLE_DATOS_INSUFICIENTES` para ambos juegos.** AE-39 y checkpoints anteriores permanecen validados e intactos. El histórico `2081..2590` continúa congelado; el intervalo `2591..2705` no fue reutilizado; el holdout desde `2706` no fue consumido. MiLoto continúa en NO-GO temporal, ColorLoto continúa pospuesto. AE-41 no fue implementada.

**Checkpoint validado (Etapa AE-41, bloqueo operativo centralizado del desarrollo predictivo):** implementa una política pura que traduce el resultado del gate ya validado de AE-40 en tres estados operativos explícitos: `BLOQUEADO_DATOS_INSUFICIENTES`, `BLOQUEADO_NUMERACION_INVALIDA` y `AUTORIZADO_PARA_PRERREGISTRO`. **La validación confirma el funcionamiento metodológico y operativo del bloqueo -ambos juegos permanecen bloqueados por ausencia de sorteos nuevos desde `2706` en la instantánea real evaluada. No hay autorización para prerregistro nuevo, observación de resultados, entrenamiento, predicción ni despliegue.**

**Entorno real del usuario, validado en Windows -evidencia atribuida al usuario, no ejecutada por Claude:** Python `3.14.6`, PostgreSQL real reutilizado (contenedor existente `loteria-predictor-fase2-final-postgres-1`, sin contenedor nuevo), revisión Alembic `0006`, `transaction_read_only=on`. Pruebas reales: `45 passed` (AE-41), `63 passed` (AE-40), `47 passed` (AE-39), `pip check` limpio. **Reconciliación honesta entre dos ejecuciones**: una primera corrida completa dio `3739 passed, 50 skipped` -los 50 omitidos en `test_generalizacion_juegos.py` por falta de `httpx`; tras instalar `httpx==0.28.1`, ese archivo completo dio `1213 passed, 0 skipped` (incluidos los 50 antes omitidos). Las `3789` pruebas recolectadas quedaron cubiertas entre ambas ejecuciones -**nunca `3789 passed` en una sola corrida del usuario.** En el sandbox de Claude, la partición completa sin superposición (`45+63+47+142+1213+2279`) sí sumó `3789 passed, 0 skipped` en una sola sesión, con `httpx==0.28.1` instalado explícitamente como dependencia de validación temporal -`requirements.txt` permanece intacto.

**Consideración CRLF en Windows -documentada, no ocultada**: con `core.autocrlf=true`, el parche (generado con terminadores LF) falló con `git apply` simple en los tres documentos, y aplicó limpio con `git apply --ignore-whitespace --whitespace=nowarn`; `git apply --reverse --check --ignore-whitespace --whitespace=nowarn` y `git diff --check` terminaron en código `0`. En Linux, sin `core.autocrlf`, el mismo parche aplica limpio con `git apply` simple y `git diff --check` estándar sin ninguna opción adicional -la diferencia proviene de la conversión de línea que Windows aplica al extraer y confirmar el ZIP base, nunca de un defecto del parche en sí.

**Consulta real confirmada, verificada directamente contra el SQL registrado**: exactamente `4` consultas totales -`2` por juego (resolución del juego más la consulta agregada de disponibilidad), con el parámetro de corte `2706` confirmado explícitamente. El SQL de disponibilidad proyecta únicamente `COUNT`, `COUNT DISTINCT`, `MIN` y `MAX` de `numero_sorteo`, filtra por `juego_id` y `numero_sorteo >= 2706`, sin `JOIN` ni columnas de resultados ganadores.

**Resultado real, negativo para ambos juegos -recalculado de forma independiente ejecutando la función real de producción con los datos exactos reportados, coincidente palabra por palabra en el motivo**: BALOTO y BALOTO_REVANCHA obtuvieron por separado `estado="bloqueado_datos_insuficientes"`, con el reporte de AE-40 anidado en `estado="no_elegible_datos_insuficientes"`, `total_sorteos_nuevos=0`, mínimo y máximo `null`, próximo holdout `2706`, mínimo requerido `100`, objetivo `2805`. **`numeracion_contigua=true` con 0 registros es un resultado vacuo -nunca afirma que exista una secuencia `2706..2805` real.**

**Distinción explícita entre lo que las consultas SQL y el estado de las tablas demuestran, y lo que las banderas del programa reflejan**: las consultas agregadas y las instantáneas de PostgreSQL (`estadisticas=209`, `modelos=0`, `metricas_modelo=0`, `predicciones=0`, idénticas antes y después) son evidencia directa de que no se leyeron números ganadores ni se escribió nada; las banderas `resultados_observados`, `modelos_entrenados`, `predicciones_generadas` y `holdout_consumido` -todas `False`- son afirmaciones del propio programa sobre su comportamiento, corroboradas por, pero no idénticas a, la evidencia de las tablas.

**Medición del proceso, no del árbol completo**: tiempo total `0.1469 s`, pico Working Set del proceso `78.52 MB` -medición del proceso que ejecutó la validación, nunca una afirmación sobre el árbol completo de procesos del sistema.

**Cierre exclusivamente de estado**: se actualizaron marcadores `PROVISIONAL` → `validada` en comentarios/docstrings de los 3 archivos Python de AE-41 (`autorizacion_operativa.py`, el caso de uso, `tipos.py`) -AST ejecutable idéntico confirmado, ignorando únicamente docstrings; el contenido de cierre añadido a `tipos.py` permanece puramente LF. Las 45 pruebas de AE-41 y todas las pruebas anteriores permanecen byte a byte idénticas. El algoritmo de traducción de numeración inválida a bloqueo -incluida la delegación completa al gate de AE-40- no fue modificado en este cierre. Los doce archivos protegidos de AE-36/37/38/39/40 permanecen byte a byte idénticos. **Confirmado con AST, no solo documentado**: `modelo.py` sigue siendo el único archivo de `application/ml/` que importa scikit-learn.

Con esta evidencia real completa del usuario -entorno, SQL registrado verificado, reconciliación honesta de pruebas entre dos ejecuciones, consideración CRLF documentada, resultado negativo honesto, PostgreSQL sin cambios-, **AE-41 queda validada como bloqueo operativo centralizado: metodología y funcionamiento confirmados -ambos juegos permanecen bloqueados por datos insuficientes.** AE-40 y checkpoints anteriores permanecen validados e intactos, incluido el NO-GO de AE-39. El histórico `2081..2590` continúa congelado; el intervalo `2591..2705` no fue reutilizado; el holdout desde `2706` no fue consumido. MiLoto continúa en NO-GO temporal, ColorLoto continúa pospuesto. AE-42 no fue implementada.

**Checkpoint validado (Etapa AE-42, auditoría ejecutable del bloqueo operativo):** comando de solo lectura, ejecutado únicamente por petición explícita del operador -nunca una tarea periódica, endpoint, pantalla ni disparador automático-, que invoca los casos de uso reales de producción de AE-40/41 (`EvaluarElegibilidadReaperturaML`, `EvaluarAutorizacionOperativaML`) para BALOTO y BALOTO_REVANCHA por separado, dentro de una transacción PostgreSQL de solo lectura verificada explícitamente, y escribe un reporte JSON versionado fuera del repositorio. No cambia la decisión de AE-41 ni inventa una regla de elegibilidad nueva. **La validación confirma el funcionamiento metodológico y operativo de la auditoría; su resultado real es negativo: ambos juegos siguen `bloqueado_datos_insuficientes`, con `0` sorteos cargados desde `2706` en la instantánea evaluada.**

**Historia de la corrección**: el primer parche provisional (SHA-256 `5960e20901844a04d46bae9596dd445dcc249b95082e8e51a2c6140fb85debbd`) quedó invalidado tras detectarse dos defectos en `construir_reporte_auditoria_operativa`, reproducidos con pruebas que fallaban antes de corregirlos: el estado global daba prioridad a una autorización detectada sobre el bloqueo por numeración inválida, y no se comprobaban la identidad ni la coherencia de estado entre el reporte exterior de AE-41 y el anidado de AE-40. El parche corregido (SHA-256 `9729d0ffbf5a5826728be09474efbdf2624a2d50fdce4b3940d206370b0903d3`), única base de esta validación, aplica la prioridad `bloqueado_numeracion_invalida` > `autorizado_para_prerregistro_detectado` > `bloqueado_datos_insuficientes` y rechaza cualquier incoherencia con código `5`, sin escribir JSON.

**Diseño validado**: núcleo puro (`application/ml/auditoria_operativa_bloqueo.py`) que traduce dos reportes ya construidos y comprueba su coherencia reutilizando la única función de traducción de AE-41; orquestación comprobable (`ejecutar_auditoria_con_sesion`) que usa las clases reales de producción; y adaptador CLI (`scripts/auditoria_operativa_bloqueo.py`) que verifica `transaction_read_only='on'` y la revisión Alembic derivada de `alembic/` antes de cualquier consulta de negocio, cierra siempre con `ROLLBACK` y nunca hace `commit` ni `flush`. Siete códigos de salida (`0` éxito; `1` a `6` fallos). `auditoria_correcta` y `autorizacion_para_prerregistro_detectada` son campos independientes: el segundo es solo informativo y nunca dispara una acción. Escritura atómica del JSON: un fallo nunca deja un reporte parcial. Consultas: `2` por juego del caso de uso de AE-40/41 más `2` auxiliares de metadatos (`SHOW transaction_read_only`, `SELECT version_num FROM alembic_version`).

**Ejecución real del usuario -evidencia atribuida al usuario, no ejecutada por Claude**: Windows, Python `3.14.6`, contenedor PostgreSQL existente (sin contenedor nuevo), `pg_isready` comprobado, código de salida `0`. Pruebas locales: `209 passed` (54 de AE-42 + 155 de AE-39/40/41) y `3843` pruebas recolectadas -recolectadas, no ejecutadas en una única corrida local-, con cinco `DeprecationWarning` preexistentes de Alembic por la falta de `path_separator` en `alembic.ini`. En el sandbox de Claude, la partición completa sin solapamiento (`54+155+1213+142+2279`) dio `3843 passed, 0 skipped` en cada reconstrucción del cierre, con `httpx==0.28.1` solo en los entornos de verificación.

**JSON real auditado directamente** (`ae42-auditoria-real.json`, 1820 bytes, SHA-256 `18707ea8d73bebd4a21126f3581dbdcd74a624f3679c7148c03cf8df4cdcff29`, evidencia externa fuera del repositorio): esquema `1.0`, etapa `AE-42`, instante `2026-09-25T02:55:37.732774+00:00` (UTC), revisión Alembic `0006`, corte `2706`, exactamente BALOTO y BALOTO_REVANCHA, `estado_global="bloqueado_datos_insuficientes"`, `auditoria_correcta=true` y `autorizacion_para_prerregistro_detectada=false`. Por juego: `estado="bloqueado_datos_insuficientes"`, `reporte_elegibilidad_disponible=true`, `total_sorteos_nuevos=0`, mínimo y máximo `null`, mínimo requerido `100`, objetivo `2805`, `numeracion_contigua=true`, motivo `0 sorteos nuevos, por debajo del minimo requerido de 100 -ninguna operacion predictiva nueva queda autorizada.`, y `resultados_observados`, `modelos_entrenados`, `predicciones_generadas` y `holdout_consumido` en `false`. Sin UUID, credenciales, cadena de conexión ni datos de resultados. Claude regeneró el reporte con el código real de producción -casos de uso reales de AE-40/41, cero registros, el mismo instante y el mismo serializador del CLI- y obtuvo un contenido **idéntico salvo los 48 terminadores CRLF** que Windows añade al escribir en modo texto (1772 bytes con LF frente a 1820 con CRLF): equivalencia por CRLF, no coincidencia byte a byte. **`numeracion_contigua=true` con cero registros es vacuo**: no existe todavía ninguna secuencia real `2706..2805`.

**Límites de la evidencia -qué respalda cada afirmación**: el JSON registra estados, metadatos agregados y la revisión Alembic leída de la base por el programa; las cuatro banderas `false` son afirmaciones del propio programa, coherentes con su código pero no mediciones independientes. El JSON **no** contiene la sentencia SQL ejecutada, el valor de `transaction_read_only`, conteos de consultas, instantáneas de `estadisticas`, `modelos`, `metricas_modelo` y `predicciones`, ni tiempos o memoria. Que la transacción fuera de solo lectura y que solo se consultaran agregados de AE-40 se deduce del código revisado (el CLI sale con `4` si `transaction_read_only` no es `on`, delega en la consulta agregada de AE-40, nunca hace `commit` ni `flush` y cierra con `ROLLBACK`) junto con la salida `0` reportada por el usuario -no de una medición registrada en el JSON.

**Cierre exclusivamente de estado**: `PROVISIONAL` → `validada` en los docstrings de módulo de `auditoria_operativa_bloqueo.py` y `scripts/auditoria_operativa_bloqueo.py`, con AST ejecutable idéntico. **La descripción de `--help` del CLI sigue diciendo "PROVISIONAL"**: es una cadena ejecutable (argumento de `ArgumentParser`), no un docstring, y las reglas de este cierre prohíben modificar código ejecutable; queda como pendiente menor para un cambio futuro con su propia validación. Las 54 pruebas de AE-42 y todas las anteriores permanecen byte a byte idénticas, igual que los quince archivos protegidos; solo `modelo.py` importa scikit-learn. En Linux el parche aplica con `git apply` simple; en Windows con `core.autocrlf=true` puede requerir `--ignore-whitespace --whitespace=nowarn`, como en AE-41/42.

Con esta evidencia, **AE-42 queda validada como auditoría operativa del bloqueo**: BALOTO y BALOTO_REVANCHA siguen bloqueados por datos insuficientes en la instantánea evaluada, con `0` sorteos cargados desde `2706`. No se habilita ningún prerregistro nuevo ni se reabre el desarrollo predictivo. AE-41 y checkpoints anteriores permanecen validados, incluidos el gate de AE-40 y el NO-GO de AE-39. El histórico `2081..2590` continúa congelado; el intervalo `2591..2705` no fue reutilizado; el holdout desde `2706` no fue consumido. MiLoto continúa en NO-GO temporal, ColorLoto continúa pospuesto. AE-43 no fue implementada.

**Mantenimiento posterior a AE-42 -corte congelado de AE-36, validado:** una revisión del código tras la sincronización incremental informada por el operador detectó que `EvaluarBaselineMLProbabilidadNumeros` (AE-36) consultaba `listar_resultados_numericos(juego.id)` **sin** `hasta_numero_sorteo`. Recorrido: sin corte, el repositorio SQLAlchemy trae todo el histórico del juego; `evaluar_juego` construye el dataset y `construir_particion_walk_forward` reserva como test final el último 20% de los sorteos elegibles. Con `2081..2705` (625 sorteos, 575 elegibles) el test es `2591..2705`, el contrato validado; con `2081..2713` (633 sorteos, 583 elegibles) pasaría a ser `2597..2713`, evaluando modelo y baselines contra etiquetas del holdout desde `2706`. AE-37/AE-38 no estaban afectados (corte `2590` en SQL más comprobación en Python); AE-39 no consulta la base y AE-40/41/42 solo leen metadatos agregados. Ningún script, ruta ni tarea invocaba AE-36: el riesgo solo se materializaba con una ejecución manual.

**Corrección mínima**: nueva constante `CORTE_CONTRATO_AE36 = 2705` (último sorteo del contrato ya validado, no un valor nuevo), pasada como `hasta_numero_sorteo` para filtrar en SQL, y una segunda capa en Python que lanza `ResultadoPosteriorAlCorteError` antes de llamar a `evaluar_juego` si llega cualquier sorteo posterior -sin reporte parcial ni filtrado silencioso. Es una **excepción explícita y documentada** a la lista de archivos protegidos: solo cambia ese caso de uso; `evaluacion.py`, `particion.py`, `dataset.py`, `modelo.py`, `baselines.py`, `tipos.py`, el repositorio, las migraciones y las pruebas existentes no se tocan. **Los resultados de AE-36 a AE-42 no cambian**: la ejecución real validada de AE-36 usó exactamente `2081..2705`.

**Pruebas nuevas, todas sintéticas** (numeración `2081..2713` elegida solo para reproducir la forma del caso real): `tests/unit/test_evaluar_baseline_ml_corte_holdout.py` (corte `2705` solicitado y test final `2591..2705`; rechazo ante un repositorio que ignora el corte, sin llegar a `evaluar_juego`; reporte idéntico con `2081..2705` y `2081..2713`; regresiones) y `tests/unit/ml/test_corte_casos_uso_ml.py` (AST limitado a los tres casos de uso existentes: `CORTE_CONTRATO_AE36=2705`, `CORTE_DESARROLLO_AE37=2590`, `CORTE_DESARROLLO_AE38=2590`; no impone ningún corte a casos de uso futuros, cuyo contrato temporal se definirá en su propia etapa). Sobre `05e8041`, sin la corrección: `9 failed, 7 passed` en esas pruebas -el caso de uso pedía corte `None` y producía test `2597..2713`. Tras la corrección: `16 passed`. Suite completa en el sandbox de Claude (Linux, Python `3.11.15`, scikit-learn `1.9.1`, `httpx==0.28.1` solo en el entorno de verificación), una única corrida tras la corrección: `3859 passed, 0 skipped` (`3843 + 16`), cinco `DeprecationWarning` preexistentes de Alembic; `pip check` limpio.

**Evidencia atribuida al operador, no medida por Claude**: sincronización incremental oficial con 8 sorteos nuevos por juego (`2706..2713`, 0 fallidos) y nueva auditoría AE-42 `ae42-auditoria-real-tras-sincronizacion.json` (SHA-256 `3b5113252a5f422c64226d837d1449a00bec7d8143a5ffdc90228d0612954d82`) con `bloqueado_datos_insuficientes` en ambos juegos y `autorizacion_para_prerregistro_detectada=false`. Faltan 92 sorteos por juego para el mínimo de 100; alcanzarlo no garantiza mejora predictiva. No se consultó PostgreSQL ni se ejecutó ninguna evaluación real de ML. AE-39 sigue en NO-GO, MiLoto en NO-GO temporal, ColorLoto pospuesto. AE-43 no fue implementada.

**Validación real del operador -evidencia atribuida al usuario, no ejecutada por Claude**: fusionado en `main` y `develop` mediante `cc3273a25639b6c14be3f30b2b71f1adb6b9c214` (PR #40, commit `115551b`), cuyo diff coincide con el parche revisado (SHA-256 `84fd2f05ffab7350b06c79825a590326445437a0ea96c04bb0809505d04fe74d`). Windows/Python `3.14.6`: `16` pruebas nuevas y `32` existentes pasadas; `pip check` limpio. La suite completa `3859 passed` corresponde únicamente al sandbox de Claude. PostgreSQL, en transacción de solo lectura: BALOTO y BALOTO_REVANCHA tienen cada uno `625` números de sorteo distintos en `2081..2705` y `8` en `2706..2713` (solo metadatos). El repositorio real, llamado con `hasta_numero_sorteo=2705`, emitió en cada juego una consulta SQL con ese corte y devolvió `625` registros con máximo `2705`. No se ejecutó ML, no se reevaluó AE-36 y no se calcularon métricas sobre `2706..2713`. Con esta evidencia el mantenimiento queda **validado**: el caso de uso de AE-36 solicita el corte `2705` al repositorio y rechaza antes de evaluar cualquier sorteo posterior que este devuelva. AE-42 no cambia: ambos juegos siguen en `bloqueado_datos_insuficientes` con 8 de 100 sorteos. El NO-GO de AE-39 se mantiene; no se habilita prerregistro, entrenamiento ni predicción. MiLoto sigue en NO-GO temporal y ColorLoto pospuesto. AE-43 no fue implementada.

**Etapa AE-43 -núcleo puro de inferencia bloqueada, validada:** prepara dos piezas de la Fase 4 sin producir ninguna predicción. Tres módulos puros nuevos en `application/ml/`, sin conexión con repositorios, casos de uso, scripts ni rutas (confirmado con AST): `ventanas_temporales.py` (fuente única de tramos: `DESARROLLO` `2081..2590`, `CONSUMIDO_AE36` `2591..2705`, `HOLDOUT` desde `2706`; solo biblioteca estándar, y una prueba verifica que coincide con las constantes ya validadas de AE-36/37/38/39/40), `inferencia.py` (`construir_filas_inferencia`: filas `FilaCandidatoInferencia` **sin etiqueta**, mismas features que `dataset.py`) y `prediccion_bloqueada.py` (`resolver_prediccion`). `tipos.py` solo recibe un añadido al final.

**Tramo permitido -solo `DESARROLLO`**: objetivo `<= 2590` y corte `<= 2589`. Cualquier sorteo recibido `>= 2591` (tramo consumido de AE-36 o holdout) se **rechaza** con `CorteInferenciaInvalidoError`, nunca se filtra en silencio; también se rechazan sorteos posteriores al corte, huecos, históricos anteriores a `2081` o con menos de 50 sorteos. El `2705` del contrato de AE-36 solo aparece en la prueba de coherencia de constantes. Ningún objetivo ni feature de AE-43 usa `2591..2705` ni `2706` en adelante.

**Resolvedor bloqueado**: `EstadoPrediccionML` tiene exactamente cuatro estados, todos de bloqueo (`BLOQUEADO_NUMERACION_INVALIDA` > `BLOQUEADO_DATOS_INSUFICIENTES` > `BLOQUEADO_NO_GO_CIENTIFICO` > `BLOQUEADO_SIN_EVALUACION_HOLDOUT`); no existe ningún estado habilitado. `ReportePrediccionJuego` rechaza en su propio `__post_init__` combinaciones, números, probabilidades, confianza o banderas en `True`, y exige el disclaimer permanente. `motivos` lista todos los bloqueos aplicables. Con el estado actual (datos insuficientes + NO-GO de AE-39) el resultado es `BLOQUEADO_DATOS_INSUFICIENTES` con motivos datos insuficientes, NO-GO y sin evaluación del holdout. Limitación explícita: `DecisionContinuidadML` es solo un `Enum` sin identidad de juego, así que el resolvedor no verifica a qué juego corresponde la decisión.

**Pruebas, todas sintéticas** (108 nuevas en cuatro archivos de `tests/unit/ml/`): fronteras de tramos y topes; rechazo de lo que se pasa (`2590`, `2591`, `2705`, `2706`, `2713`, al principio o al final); invariancia ante lo que no se pasa -alterar en la fuente `2590`, `2591..2705` y `2706..2713` no cambia la salida-, con control positivo (alterar `2589` sí la cambia); campos sin etiqueta; paridad campo por campo con las filas etiquetadas de `construir_dataset_binario` para todos los objetivos `2131..2590`; etiqueta intocable, comparando solo las filas del mismo objetivo N; producto cartesiano de los 3 estados de AE-41 por las 2 decisiones de AE-39, construido con las funciones reales; y pureza estructural. Suite completa en el sandbox de Claude: `3967 passed, 0 skipped` (`3859 + 108`) en una única corrida (Linux, Python `3.11.15`, scikit-learn `1.9.1`, `httpx==0.28.1` solo en el entorno de verificación), cinco `DeprecationWarning` preexistentes de Alembic; `pip check` limpio.

No se consultó PostgreSQL, no se entrenó, no se evaluó el holdout ni se generaron predicciones. AE-42 y el corte congelado de AE-36 no cambian; AE-39 sigue en NO-GO, MiLoto en NO-GO temporal y ColorLoto pospuesto. Alcanzar 100 sorteos nuevos solo permitiría reconsiderar la elegibilidad de AE-40/41; cualquier evaluación futura deberá ser prospectiva, prerregistrada antes de observar sorteos posteriores a ese prerregistro, sin tratar `2706..2805` como un holdout ciego.

**Validación real del operador -evidencia atribuida al usuario, no ejecutada por Claude**: en Windows/Python `3.14.6`, las `108` pruebas nuevas de AE-43 y `493` pruebas focalizadas pasaron, con los cinco `DeprecationWarning` de Alembic ya conocidos; `pip check`, `git diff --check` y la comprobación de los `11` archivos del cambio fueron correctos. En Windows no se ejecutó la suite completa: la cifra `3967 passed` corresponde únicamente al sandbox de Claude. No se consultó PostgreSQL, no se entrenó ningún modelo, no se evaluó el holdout ni se generaron predicciones. Con esta evidencia, **AE-43 queda validada como núcleo puro de inferencia bloqueada**: las filas de inferencia solo admiten `DESARROLLO` (objetivo `<= 2590`) y el resolvedor solo produce estados bloqueados. No se habilita ningún estado de predicción, prerregistro ni evaluación. AE-42, el corte congelado de AE-36 y el NO-GO de AE-39 no cambian; MiLoto sigue en NO-GO temporal y ColorLoto pospuesto. AE-44 no fue implementada.

**Etapa AE-44 -caso de uso `ResolverEstadoPrediccion`, validada:** primer caso de uso de la Fase 4. Es el punto de entrada por juego que el roadmap nombra `GenerarPredicciones`; ese nombre queda reservado para una etapa futura con evidencia prospectiva. `ResolverEstadoPrediccion.ejecutar(codigo_juego)` une, sin reevaluarlos, el estado operativo real de AE-41 (`EvaluarAutorizacionOperativaML`, que solo consulta metadatos agregados desde `2706`), la decisión validada de AE-39 y el resolvedor puro de AE-43 (`resolver_prediccion`). Siempre devuelve un `ReportePrediccionJuego` bloqueado: no lee números ganadores, no construye filas de inferencia, no entrena, no predice ni persiste, y no está expuesto en rutas, plantillas ni scripts (confirmado con pruebas estructurales).

**Decisión de AE-39 por juego, sin valor por defecto**: `DECISIONES_CONTINUIDAD_AE39` es un registro inmutable (`MappingProxyType`) con `NO_GO_SIN_EVIDENCIA_SUFICIENTE` para BALOTO y BALOTO_REVANCHA. Su docstring documenta la procedencia: las diferencias de Log Loss y Brier con sus IC 95% de la sección de AE-39, calculadas sobre los 18 bloques externos de AE-38 (`2081..2590`). Si falta la clave de un juego autorizado se lanza `DecisionContinuidadAusenteError` antes de consultar AE-41; nunca se usa `.get()` ni una decisión por defecto. Como la decisión se toma por `codigo_juego` y se comprueba que AE-41 devolvió un reporte del mismo juego, este caso de uso cierra la limitación de identidad de juego documentada en AE-43 sin modificar el resolvedor.

**Resultado esperado con el estado actual informado** (8 sorteos nuevos por juego): `BLOQUEADO_DATOS_INSUFICIENTES` con motivos datos insuficientes, NO-GO y sin evaluación del holdout. Con 100 sorteos contiguos (`2706..2805`), AE-41 pasaría a `AUTORIZADO_PARA_PRERREGISTRO`, pero el resultado seguiría bloqueado por el NO-GO de AE-39 y por la ausencia de una evaluación prospectiva.

**Excepción estructural acotada en AE-43**: `tests/unit/ml/test_ae43_estructura.py` prohibía que cualquier archivo fuera de `application/ml/` importara los módulos de AE-43. Con autorización expresa del usuario, se añadió una única excepción: `use_cases/resolver_estado_prediccion.py` puede importar `prediccion_bloqueada`. Siguen prohibidos, para ese archivo, `inferencia` y `ventanas_temporales`, y para cualquier otro archivo, los tres módulos. Ningún archivo de `application/ml/` cambió.

**Pruebas, todas sintéticas** (26 nuevas en `tests/unit/test_resolver_estado_prediccion.py`, con las clases reales de AE-40/41 y repositorios fake de metadatos): seis escenarios por juego (0, 8, 99 y 100 sorteos, hueco en la numeración, inicio distinto de `2706`), todos bloqueados y sin salidas predictivas; registro exacto, inmutable y con procedencia; clave ausente sin consultar AE-41; rechazo de MiLoto y ColorLoto antes de consultar; juego inexistente; reporte de otro juego; constructor mínimo; pureza de importaciones y ausencia de exposición. Suite completa en el sandbox de Claude: `3993 passed, 0 skipped` (`3967 + 26`) en una única corrida (Linux, Python `3.11.15`, scikit-learn `1.9.1`, `httpx==0.28.1` solo en el entorno de verificación), cinco `DeprecationWarning` preexistentes de Alembic; `pip check` limpio.

**Validación del operador en Windows/Python `3.14.6`:** `26` pruebas nuevas y `519` focalizadas pasaron; aparecieron los cinco avisos conocidos de Alembic. `pip check` y `git diff --check` fueron correctos, y el cambio abarca los seis archivos previstos. La suite completa (`3993 passed, 0 skipped`) se ejecutó únicamente en el entorno Linux de Claude. En esta validación no se consultó PostgreSQL ni se ejecutó ML real. AE-44 queda validada como caso de uso que solo devuelve estados bloqueados.

No se consultó PostgreSQL, no se entrenó, no se evaluó el holdout ni se generaron predicciones. AE-39 sigue en NO-GO; AE-40 a AE-43 no cambian. MiLoto sigue en NO-GO temporal y ColorLoto pospuesto. Cualquier evaluación futura deberá ser prospectiva y prerregistrada; `2706` en adelante no se trata como un holdout ciego.

**Etapa AE-45 -consulta manual de estado bloqueado, validada:** Primer adaptador manual del estado bloqueado de AE-44: `python -m scripts.consultar_estado_prediccion` desde `backend/`. Para BALOTO y BALOTO_REVANCHA, construye los repositorios reales de AE-40/41 y llama a `ResolverEstadoPrediccion` una vez por juego. Abre una transaccion PostgreSQL `READ ONLY`, confirma `transaction_read_only=on` y la revision Alembic mediante las comprobaciones existentes de AE-42, y termina con `ROLLBACK`. Solo entonces publica en stdout un JSON completo (esquema `1.0`, revision y dos juegos con estado, todos los motivos, explicacion y disclaimer). No imprime un reporte parcial si falla uno de los juegos; un bloqueo valido termina con codigo `0`, los fallos con codigos distintos de cero. No lee numeros ganadores, no produce combinaciones, probabilidades ni confianza, no entrena, no persiste y no se ejecuta automaticamente. No hay ruta web, API ni tarea periodica. El roadmap de la Fase 4 sigue sin cumplir sus criterios predictivos.

**Evidencia real anterior de AE-44, atribuida al operador:** en Windows/Python `3.14.6` y transaccion verificada como `transaction_read_only=on`, ambos juegos devolvieron `bloqueado_datos_insuficientes` con los tres motivos: datos insuficientes, NO-GO cientifico y ausencia de evaluacion prospectiva; no aparecieron salidas predictivas. AE-45 no consulta PostgreSQL en el sandbox; su ejecucion real, atribuida al operador, se registra mas abajo.

**Pruebas sinteticas nuevas:** `tests/unit/test_consultar_estado_prediccion_script.py` comprueba orden de los dos juegos, JSON sin campos predictivos, rechazo de tipo o juego incorrecto, segundo juego fallido sin JSON parcial, verificacion de solo lectura y Alembic antes de evaluar, y `ROLLBACK` incluso ante fallos. La prueba estructural de AE-44 autoriza exclusivamente `scripts/consultar_estado_prediccion.py` a importarlo; routers, plantillas y los otros scripts siguen sin acceso. Ningun archivo de `application/ml/` cambia. Suite completa en el sandbox: `4003 passed, 0 skipped` (`3993 + 10`) en una sola corrida (Linux, Python `3.12.14`, scikit-learn `1.9.1`, `httpx==0.28.1` solo en el entorno de verificacion), con cinco `DeprecationWarning` conocidos de Alembic; `uv pip check` limpio.

**Validacion real del operador -evidencia atribuida al usuario, no ejecutada por Claude**: en Windows/Python `3.14.6`, las `10` pruebas nuevas y `529` pruebas focalizadas pasaron, con los cinco `DeprecationWarning` conocidos de Alembic; `pip check` y `git diff --check` limpios, con exactamente seis archivos de AE-45. El operador ejecuto `python -m scripts.consultar_estado_prediccion` contra su PostgreSQL: termino con codigo `0` y un JSON valido con esquema `1.0` y revision Alembic `0006`. BALOTO y BALOTO_REVANCHA devolvieron cada uno `bloqueado_datos_insuficientes`, con los motivos en este orden: `bloqueado_datos_insuficientes`, `bloqueado_no_go_cientifico`, `bloqueado_sin_evaluacion_holdout`; ambos incluyeron el disclaimer. El JSON no registra el valor de `transaction_read_only`: que la transaccion fuera de solo lectura se deduce del codigo, que confirma `transaction_read_only=on` antes de cualquier consulta de negocio y sale con codigo `4` si no se cumple, junto con la salida `0` reportada. La suite completa `4003 passed` corresponde unicamente al sandbox; en Windows no se ejecuto la suite completa. No se entreno ni evaluo ML, no se leyeron numeros ganadores y no se generaron predicciones. Con esta evidencia, **AE-45 queda validada como consulta manual y de solo lectura del estado bloqueado**: no habilita predicciones, prerregistro ni evaluacion. AE-39 sigue en NO-GO y AE-40 a AE-44 no cambian. AE-46 no fue implementada.

**Etapa AE-46 -diagnóstico estructurado del bloqueo, validada:** concreta, en forma bloqueada, el entregable de la Fase 4 "explicación de cómo se obtuvo cada recomendación". Hasta AE-45 el bloqueo solo se explicaba con una frase de texto; AE-46 añade un diagnóstico por juego que dice qué condiciones faltan y cuánto progreso hay, sin habilitar ninguna predicción. Dos piezas nuevas, sin conexión con rutas, plantillas, scripts ni `main` (confirmado con pruebas estructurales): el módulo puro `application/ml/diagnostico_bloqueo.py` (`diagnosticar_bloqueo`) y el caso de uso `DiagnosticarEstadoPrediccion` (`application/use_cases/diagnosticar_estado_prediccion.py`). Ningún archivo validado cambia: ni `tipos.py`, ni los módulos o pruebas de AE-39 a AE-45.

**Contrato**: `DiagnosticoBloqueoJuego` lleva `estado` y `motivos` obtenidos llamando a `resolver_prediccion` de AE-43, de modo que nunca discrepan del reporte de AE-44; un `ProgresoSorteosNuevos` copiado del reporte de elegibilidad de AE-40 (total desde `2706`, mínimo requerido, objetivo `2805`), del que solo se deriva `faltantes = max(0, mínimo - total)`; y una condición por cada miembro del enum cerrado `CondicionDesbloqueoML`, en orden: numeración válida, mínimo de sorteos nuevos, evidencia científica de AE-39, protocolo prospectivo prerregistrado y evaluación prospectiva positiva. Las dos últimas no tienen mecanismo en AE-46 y su `__post_init__` impide marcarlas como cumplidas; `desbloqueable` es siempre `False`. Las invariantes exigen además coherencia entre condiciones, progreso y motivos, y el cumplimiento del mínimo se toma del estado de AE-40, no de una regla duplicada. No hay campos de números, combinaciones, probabilidades ni confianza.

**Caso de uso**: una sola llamada a AE-41 por ejecución (solo metadatos agregados). Reutiliza, sin copiarlos, el registro inmutable `DECISIONES_CONTINUIDAD_AE39` y los errores de AE-44, leyendo el registro del módulo de AE-44 en cada ejecución y sin decisión por defecto; rechaza MiLoto y ColorLoto antes de consultar y comprueba que AE-41 devuelva el mismo juego. Con el estado informado por el operador (8 sorteos nuevos por juego), el resultado esperado es `BLOQUEADO_DATOS_INSUFICIENTES`, `8` de `100`, faltan `92`, con cuatro condiciones pendientes. Con 100 sorteos el mínimo queda cumplido, pero el diagnóstico sigue bloqueado por el NO-GO de AE-39 y por las dos condiciones sin mecanismo.

**Pruebas, todas sintéticas** (66 nuevas: `tests/unit/ml/test_diagnostico_bloqueo.py` y `tests/unit/test_diagnosticar_estado_prediccion.py`, con las funciones y clases reales de AE-40/41/43/44 y repositorios fake de metadatos): progreso para 0, 8, 99, 100 y 130 sorteos y para numeración inválida; orden y conjunto cerrado de condiciones; alcanzar 100 no desbloquea; ni con toda condición evaluable cumplida se desbloquea; estado y motivos idénticos a `resolver_prediccion` y a `ResolverEstadoPrediccion` en todos los escenarios; invariantes; una sola consulta de metadatos por ejecución; reutilización del registro de AE-44 sin copia ni `.get()`; clave ausente sin consultar AE-41; aislamiento y ausencia de exposición. Suite completa en el sandbox de Claude: `4069 passed, 0 skipped` (`4003 + 66`) en una única corrida (Linux, Python `3.11.15`, scikit-learn `1.9.1`, `httpx==0.28.1` solo en el entorno de verificación), cinco `DeprecationWarning` conocidos de Alembic; `pip check` limpio.

En el sandbox de Claude no se consultó PostgreSQL; la ejecución real contra PostgreSQL la hizo el operador (ver abajo). En ningún caso se entrenó, se evaluó el holdout ni se generaron predicciones. AE-39 sigue en NO-GO y los bloqueos de AE-40 a AE-45 no cambian. MiLoto sigue en NO-GO temporal y ColorLoto pospuesto. Cualquier evaluación futura deberá ser prospectiva y prerregistrada; `2706` en adelante no se trata como un holdout ciego.

**Validación real del operador -evidencia atribuida al usuario, no ejecutada por Claude**: en Windows/Python `3.14.6`, las `66` pruebas nuevas y `595` pruebas focalizadas pasaron, con los cinco `DeprecationWarning` conocidos de Alembic; `pip check` y `git diff --check` limpios, con exactamente siete archivos de AE-46. El operador ejecutó el caso de uso real `DiagnosticarEstadoPrediccion` para ambos juegos contra su PostgreSQL, en una transacción verificada de solo lectura cerrada con `ROLLBACK`, con revisión Alembic `0006`. BALOTO y BALOTO_REVANCHA devolvieron cada uno `bloqueado_datos_insuficientes`, con los motivos en este orden: `bloqueado_datos_insuficientes`, `bloqueado_no_go_cientifico`, `bloqueado_sin_evaluacion_holdout`; `8` sorteos nuevos de un mínimo de `100`, faltan `92`, objetivo `2805`; cuatro condiciones pendientes: `minimo_sorteos_nuevos`, `evidencia_cientifica_ae39`, `protocolo_prospectivo_prerregistrado` y `evaluacion_prospectiva_positiva`; `desbloqueable=False`. La suite completa `4069 passed` corresponde únicamente al sandbox de Claude; en Windows no se ejecutó la suite completa. No se entrenó ni evaluó ML, no se leyeron números ganadores y no se generaron predicciones. Con esta evidencia, **AE-46 queda validada como diagnóstico estructurado del bloqueo**: no habilita predicciones, prerregistro ni evaluación. AE-39 sigue en NO-GO y los bloqueos de AE-40 a AE-45 no cambian. AE-47 no fue implementada.

**Etapa AE-47 -diagnóstico en la consulta manual (JSON 1.1), validada:** amplía el único punto de consulta real, `python -m scripts.consultar_estado_prediccion` (AE-45), para que el operador vea también el diagnóstico de AE-46. No se crea un segundo script ni una ruta web. Por cada juego, el JSON pasa del esquema `1.0` al `1.1`: conserva `codigo`, `estado`, `motivos`, `explicacion` y `disclaimer`, y añade `progreso` (evaluable, desde `2706`, total, mínimo, faltantes y objetivo), `condiciones_pendientes` y `desbloqueable` (siempre `false`). No incluye combinaciones, números, probabilidades ni confianza.

**Una sola consulta agregada por juego**: el script envuelve el caso de uso real de AE-41 en un adaptador (`_AutorizacionUnaVezPorJuego`) que lo consulta una vez por juego y entrega el mismo reporte a `ResolverEstadoPrediccion` (AE-44) y a `DiagnosticarEstadoPrediccion` (AE-46). Ninguno de los dos casos de uso cambia, y el script sigue sin importar `prediccion_bloqueada`, `inferencia`, `modelo`, `dataset` ni repositorios de resultados. Antes de emitir el JSON, el script comprueba que el diagnóstico sea del tipo esperado y del mismo juego, que su `estado` y sus `motivos` coincidan exactamente con los del reporte de predicción bloqueada y que no sea desbloqueable; si no, sale con código `5` sin JSON. Se conservan la transacción `READ ONLY` verificada, la comprobación de la revisión Alembic, el `ROLLBACK`, la ausencia de reportes parciales y los siete códigos de salida (`0` a `6`).

**Cambios en pruebas validadas, acotados**: las pruebas de AE-45 se adaptan al esquema `1.1` y a la nueva firma `construir_reporte(resolver, diagnosticador, revision)`, conservando todas sus comprobaciones. La prueba estructural de AE-46 que prohibía a cualquier script mencionar su caso de uso autoriza ahora únicamente a `scripts/consultar_estado_prediccion.py`, con el mismo patrón que AE-45 aplicó a AE-44; rutas, plantillas, `main` y los demás scripts siguen sin acceso. Ningún archivo de `application/` cambia.

**Pruebas, todas sintéticas** (`tests/unit/test_consultar_estado_prediccion_script.py`, de 10 a 23 pruebas): esquema `1.1` completo con progreso `8` de `100`, faltan `92`, y las cuatro condiciones pendientes; ninguna clave predictiva en todo el JSON; una sola consulta agregada por juego con los casos de uso reales de AE-40/41/44/46 y un repositorio fake de metadatos que cuenta consultas; el adaptador comparte el mismo reporte y no guarda fallos; diagnóstico de otro tipo, de otro juego, con otro estado o con otros motivos se rechaza con código `5`; fallos del reporte o del diagnóstico en el segundo juego sin JSON parcial; `main()` mantiene el orden solo lectura, revisión y consultas, el `ROLLBACK` y los códigos; ausencia de exposición web. Suite completa en el sandbox de Claude: `4082 passed, 0 skipped` (`4069 + 13`) en una única corrida (Linux, Python `3.11.15`, scikit-learn `1.9.1`, `httpx==0.28.1` solo en el entorno de verificación), cinco `DeprecationWarning` conocidos de Alembic; `pip check` limpio. En el sandbox Linux de Claude, AE-47 no se ejecutó contra PostgreSQL; la ejecución real la hizo el operador (ver abajo).

Las validaciones reales de AE-45 y AE-46 son evidencia del operador, registrada en sus secciones. No se entrenó ni evaluó ML, no se leyeron números ganadores y no se generaron predicciones. AE-39 sigue en NO-GO y los bloqueos de AE-40 a AE-46 no cambian; `2706` en adelante no se trata como un holdout ciego.

**Validación real del operador -evidencia atribuida al usuario, no ejecutada por Claude**: el operador aplicó el parche original de AE-47 (`ae47-consulta-diagnostico-json-1-1.patch`, 41 950 bytes, SHA-256 `1db0395953453db4364a240bb430d434048343b0b04e6a5388aa8771d017c5a9`) sobre `54661c3` en Windows/Python `3.14.6`; los cambios locales fueron exactamente los seis archivos de AE-47. En Windows pasaron las `48` pruebas afectadas y `608` pruebas focalizadas, con los cinco `DeprecationWarning` conocidos de Alembic; `pip check` y `git diff --check` limpios. En Windows no se ejecutó la suite completa: la cifra `4082 passed` corresponde únicamente al sandbox Linux de Claude. El operador ejecutó `python -m scripts.consultar_estado_prediccion` contra su PostgreSQL: terminó con código `0` y produjo un JSON de esquema `1.1` con revisión Alembic `0006`. BALOTO y BALOTO_REVANCHA devolvieron cada uno `bloqueado_datos_insuficientes`, con los motivos datos insuficientes, NO-GO científico y sin evaluación del holdout; progreso `8` de `100`, faltan `92`, objetivo `2805`; cuatro condiciones pendientes (mínimo de sorteos nuevos, evidencia científica de AE-39, protocolo prospectivo prerregistrado y evaluación prospectiva positiva); `desbloqueable=false`; sin campos predictivos. El JSON no registra `transaction_read_only` ni el `ROLLBACK`: que la consulta fuera de solo lectura se deduce del código, que confirma `transaction_read_only=on` antes de cualquier consulta de negocio (sale con código `4` si no se cumple) y cierra siempre con `ROLLBACK`, junto con la salida `0` observada. No se entrenó ni evaluó ML, no se leyeron números ganadores y no se generaron predicciones. Con esta evidencia, **AE-47 queda validada como diagnóstico en la consulta manual (JSON 1.1)**: no habilita predicciones, prerregistro ni evaluación. AE-39 sigue en NO-GO y los bloqueos de AE-40 a AE-46 no cambian. AE-48 no fue implementada.

**Etapa AE-48 -evidencia y comparación de la consulta manual, validada:** añade dos flags opcionales a `python -m scripts.consultar_estado_prediccion`. Sin flags, la salida es idéntica a la de AE-47 (esquema `1.1`), comprobado con una prueba de regresión. No hay rutas web, tareas periódicas, tablas ni migraciones, y ningún archivo de `app/` cambia.

**`--salida RUTA`**: el JSON se serializa una sola vez en bytes UTF-8 con LF. Esos mismos bytes se guardan en el archivo, se escriben en stdout y se usan para la huella SHA-256, que se informa solo en stderr (`SHA-256 <hex>  <ruta>  (<n> bytes)`); stdout contiene únicamente el JSON. Para conservar evidencia exacta se usa `--salida`. La huella se verifica sobre el archivo guardado: en PowerShell con `Get-FileHash -Algorithm SHA256 <ruta>` y en Linux con `sha256sum <ruta>`. La publicación es exclusiva: los bytes se escriben en un temporal del mismo directorio (modo binario, `fsync`) y se publican con un enlace duro (`os.link`), que falla si el destino ya existe (POSIX `link`; en Windows, `CreateHardLinkW`). Nunca se sobrescribe un archivo existente, tampoco si aparece justo antes de publicar. Si el sistema de archivos no admite enlaces duros (por ejemplo FAT32, exFAT o algunos recursos de red), el script sale con código `8` sin publicar nada. Tras publicar, se relee el archivo y se comprueba la huella. No se reutiliza la escritura atómica de AE-42, porque escribe en modo texto (en Windows convierte LF en CRLF), serializa por su cuenta y sobrescribe el destino; AE-42 no cambia.

**`--comparar RUTA`**: antes de abrir la conexión se lee (UTF-8 estricto) y se valida un reporte anterior `1.1` o `1.2`, con claves exactas, los dos juegos en orden, estados y condiciones del catálogo real, progreso y condiciones coherentes, `desbloqueable=false` y ninguna clave predictiva en ningún nivel. En un `1.2` se valida también su `comparacion` (claves, tipos, coherencia con su propio reporte y nota fija), pero nunca se reutiliza ni se copia: la comparación nueva se recalcula siempre desde los juegos y la revisión de ambos reportes. El resultado es el esquema `1.2`: el `1.1` actual más `comparacion`, con sorteos nuevos anteriores y actuales, variación, faltantes, estados, condiciones resueltas y nuevas, `retroceso` (anomalía informada si baja el total, no corregida) y una nota fija. **La comparación es descriptiva**: una variación de sorteos nuevos no es evidencia predictiva ni modifica el NO-GO de AE-39, y alcanzar 100 sorteos solo resuelve la condición de mínimo; el estado sigue bloqueado. La cifra 8/100 de AE-47 es evidencia histórica del operador y no aparece en el código.

**Rutas y códigos de salida**: antes de abrir la conexión, `--salida` se rechaza con código `9` si apunta al mismo archivo que `--comparar` (misma ruta literal, relativa frente a absoluta, con `..`, enlaces simbólicos y, si ambos existen, enlaces duros), si ya existe o si su directorio no existe; el archivo anterior queda intacto. Un archivo anterior inválido da código `7` y un fallo al publicar la salida da código `8`, sin JSON en stdout. Los códigos `0` a `6` conservan su significado. Se mantienen la transacción `READ ONLY` verificada, la revisión Alembic, una consulta de AE-41 por juego, la coherencia entre diagnóstico y reporte y el `ROLLBACK`.

**Archivos**: nuevo `scripts/comparacion_estado_prediccion.py`, solo con biblioteca estándar, que recibe del script el catálogo de estados y condiciones construido desde los enums reales. Se amplía `scripts/consultar_estado_prediccion.py`. Las 23 pruebas existentes del script no cambian y se añaden pruebas al final del archivo. No hace falta ninguna excepción en las pruebas estructurales validadas.

**Pruebas, todas sintéticas** (`tests/unit/test_comparacion_estado_prediccion.py`, 73 pruebas, y pruebas añadidas a `tests/unit/test_consultar_estado_prediccion_script.py`): validación estricta de 1.1 y 1.2, con rechazo de mutaciones concretas, incluida una `comparacion.misma_revision_alembic` que no coincide con comparar `comparacion.revision_alembic_anterior` con el `alembic_revision` del mismo reporte (código `7` sin abrir la conexión); comparación de 8→8, 8→15, 8→100 (sigue bloqueado), 15→8 (retroceso) y evaluable a no evaluable; no copia de la comparación anterior; escritor atómico con destino existente, destino que aparece justo antes de publicar, sistema sin enlaces duros, fallo de `fsync`, verificación de la huella y fallo al releer el destino ya publicado (código `8` sin JSON en stdout ni traceback; el destino publicado no se borra); bytes de stdout capturados directamente de un proceso hijo iguales a los del archivo, con la huella de stderr igual al SHA-256 de los bytes guardados; códigos `7` y `9` sin abrir la conexión y con el archivo anterior intacto (SHA-256 y fecha de modificación); código `8` ante un destino concurrente. Suite completa en el sandbox Linux de Claude: `4166 passed, 0 skipped` (`4082 + 84`), medida únicamente con el parche v1 (`ae48-evidencia-comparacion.patch`, 76 292 bytes, SHA-256 `16bcea9855076bada70d3a6d067655833de9097f7c8cce12e0a65c199ff223b0`), anterior a estas dos correcciones, en una única corrida (Linux, Python `3.11.15`, scikit-learn `1.9.1`, `httpx==0.28.1` solo en el entorno de verificación), cinco `DeprecationWarning` conocidos de Alembic; `pip check` limpio. Las dos correcciones posteriores (coherencia de `misma_revision_alembic` y fallo al releer) añaden 5 pruebas (`84 + 5 = 89`) y solo cambian el módulo de comparación, que únicamente importan el script y sus dos archivos de pruebas; se validaron en el sandbox con esos archivos (`112 passed`) y las pruebas estructurales (`233 passed` y `99 passed`), sin repetir la suite completa: no existe una suite completa del parche v2. En el sandbox Linux de Claude, AE-48 no se ejecutó contra PostgreSQL ni en Windows; la validación real la hizo el operador (ver abajo).

**Validación real del operador -evidencia atribuida al usuario, no ejecutada por Claude**: el operador aplicó el parche completo v2 (`ae48-evidencia-comparacion-v2.patch`, 82 203 bytes, SHA-256 `9191dd88fa81253c7e03223ee87502cdd3c57de1cbcf80fddb29a86503c39d58`) sobre `effe31a` en Windows/Python `3.14.6`; `git apply --reverse --check` y `git diff --check` pasaron y los cambios locales fueron exactamente los siete archivos de AE-48. En Windows pasaron las `112` pruebas afectadas y `697` pruebas focalizadas, con los cinco `DeprecationWarning` conocidos de Alembic; `pip check`: `No broken requirements found`. En Windows no se ejecutó la suite completa, y tampoco existe una suite completa del parche v2: la cifra `4166 passed` corresponde únicamente al sandbox Linux de Claude con el parche v1. El operador ejecutó contra su PostgreSQL el script, que exige una transacción de solo lectura verificada:

- Con `--salida` obtuvo un JSON `1.1` en el que BALOTO y BALOTO_REVANCHA quedaron en `bloqueado_datos_insuficientes`, con `8` sorteos nuevos y `92` faltantes. La huella impresa en stderr y la calculada con `Get-FileHash` coincidieron: `bc6660fbae9e72c4a72f9e34473d64dd835dbfe445c52bcf98f8a47d6069be85` (`2414` bytes).
- Con `--comparar` sobre esa evidencia y una `--salida` nueva obtuvo un JSON `1.2` con variación `0` en ambos juegos, sin cambio de estado ni retroceso. La evidencia anterior conservó su huella y su fecha de modificación, y la segunda huella impresa coincidió con `Get-FileHash`: `937a40767ea0c2d317bedd4cdbb452b4c02d69a122149d0c0fff8f8abcaf3554` (`3641` bytes).
- Reutilizar un destino existente, o usar la misma ruta en `--salida` y `--comparar`, devolvió código `9` y conservó el archivo.
- Se simuló en Windows que otro proceso creaba el destino justo antes de `os.link`: la publicación falló, el destino conservó sus bytes y el temporal se eliminó. La evidencia no registra el tipo de sistema de archivos.
- Una copia `1.2` con `misma_revision_alembic` incoherente devolvió código `7`, con stdout vacío y la evidencia original intacta.

El fallo al releer el destino tras publicar (código `8`) solo está cubierto por la prueba sintética incluida en las `112`; no se provocó en una ejecución real. La variación `0` es una comparación descriptiva de metadatos, no evidencia predictiva. Con esta evidencia, **AE-48 queda validada como evidencia persistible y comparación descriptiva de la consulta manual (JSON 1.1 y 1.2)**: no habilita predicciones, prerregistro ni evaluación.

No se entrenó ni evaluó ML, no se leyeron números ganadores y no se generaron predicciones. AE-39 sigue en NO-GO y los bloqueos de AE-40 a AE-47 no cambian; `2706` en adelante no se trata como un holdout ciego.

**Etapa AE-49 -referencia Monte Carlo exploratoria bajo azar uniforme, validada (primera etapa de la Fase 6):** `python -m scripts.simular_azar_uniforme`, ejecutado desde `backend/`, compara, para BALOTO y BALOTO_REVANCHA por separado, cuatro estadísticas descriptivas fijadas de antemano con su distribución bajo azar uniforme. Esa distribución se simula con el mismo mecanismo de sorteo (5 números sin reemplazo de 1..43 y superbalota de 1..16) y conservando la numeración observada. **Es un análisis exploratorio sobre datos reutilizados**: el rango `2081..2705` ya fue examinado en AE-36 a AE-39, así que el resultado no es confirmatorio, no está prerregistrado, no es evidencia prospectiva ni predictiva, no genera combinaciones ni recomendaciones y no modifica el NO-GO de AE-39.

**Rango fijo**: `2081..2705`, el contrato congelado de AE-36; una prueba lo ata a `ventanas_temporales` y no hay ninguna opción para cambiarlo. `2591..2705` se incluye, pero no se analiza por separado. `2706` en adelante no se lee (la consulta SQL corta en `2705`), no se simula y no entra en la huella: no es un holdout ciego y AE-49 no lo convierte en uno. El histórico leído debe ser exactamente `2081..2705`, con 625 sorteos, sin huecos ni duplicados, cada uno válido según el dominio y con superbalota. Además, los parámetros del juego en la base de datos deben coincidir con el dominio. Si algo de esto falla, el script devuelve el código `5`. **MiLoto queda fuera**: su rango (`532..601`, 70 sorteos) solo consta en la documentación de AE-35, sin una constante validada en el código ni una huella de contenido, y la serie sigue creciendo.

**Estadísticas y familia**: son cuatro por juego:
- `dispersion_frecuencia_numeros` (Σ(O−E)²/E). Bajo azar uniforme su media es n−k = 38, no 42, porque la chi-cuadrado clásica con gl = N−1 está mal calibrada cuando no hay reemplazo.
- `rango_frecuencia_numeros`.
- `media_repeticiones_entre_sorteos`, sobre transiciones estrictas N→N+1 (referencia 25/43).
- `dispersion_frecuencia_superbalota` (referencia 15).

Para cada una se publican el p-valor empírico bilateral con corrección +1 (nunca vale 0), el percentil y la media y la desviación simuladas. Bonferroni se aplica una sola vez sobre las ocho comparaciones de la ejecución (2 juegos × 4), con α = 0,05 y la función existente del motor. El resultado se publica en el campo `supera_umbral_exploratorio`: `true` señala una discrepancia descriptiva que hay que revisar, no un hallazgo establecido, y `false` no demuestra aleatoriedad. **El ajuste cubre solo estas ocho comparaciones; no corrige la selección ni la inspección previa de datos y análisis en AE-36 a AE-39.** La semilla (`20260926`) y las iteraciones (`10 000`) están fijas en el código.

**Reproducibilidad**: cada juego lleva `entrada_sha256`, calculada sobre la entrada normalizada (numeración, números ordenados y superbalota), sin fechas y sin publicar números ganadores. El generador es propio: un Fisher–Yates parcial que solo usa `Random(semilla).random()`, con una semilla derivada por juego mediante SHA-256. La aritmética es exacta, con enteros y `Fraction`, sin `sum()` de floats (que cambió en Python 3.12), y los valores solo se convierten a `float` al construir el reporte. Con la misma huella de entrada, los mismos parámetros y el mismo código se obtienen los mismos bytes **en las versiones verificadas**: la prueba de referencia SHA-256 de extremo a extremo (`99fb194bd0b94719bfbeb84526b2bc346f30b45140833fee4b38552083b2295f`) pasó en el sandbox Linux de Claude con Python `3.11.15`, `3.12.3` y `3.13.12`. No se promete esa identidad para otras plataformas, porque el cálculo usa `math.sqrt`; el operador la verificó después en Windows/Python `3.14.6` (ver abajo).

**Salida y códigos**: JSON `simulacion-azar-uniforme/1.0`, con `caracter: "exploratorio_sobre_datos_reutilizados"`, una nota fija y textos fijos de alcance y de cobertura del ajuste. El único argumento es `--salida RUTA`, con la publicación exclusiva y la huella de AE-48; cualquier otro argumento da el código `7` antes de abrir la conexión. Como en AE-45/47, se verifica la transacción `READ ONLY` y la revisión Alembic, y se cierra con `ROLLBACK`. Códigos de salida:

| Código | Significado |
|---|---|
| `0` | OK |
| `1` | Fallo inesperado |
| `2` | Conexión |
| `3` | Revisión Alembic |
| `4` | Transacción no `READ ONLY` |
| `5` | Entrada inválida |
| `6` | Fallo simulando |
| `7` | Argumentos inválidos |
| `8` | Fallo al escribir la salida |
| `9` | Ruta de salida no permitida |

No escribe en la base de datos (la tabla `simulaciones` todavía no se usa), no tiene web ni tareas automáticas y no necesita ninguna excepción estructural. En el sandbox, con los parámetros fijos y un histórico sintético de 625 sorteos por juego, tardó `96 s`; es una medición sintética, no el tiempo real.

**Archivos**: son nuevos `app/application/simulaciones/montecarlo_uniforme.py` (puro, sin SQLAlchemy ni `app.application.ml`), el caso de uso `SimularReferenciaAzarUniforme`, `scripts/simular_azar_uniforme.py` y sus pruebas. Reutiliza sin cambios:
- el dominio;
- las funciones del motor `calcular_frecuencia_numeros`, `calcular_frecuencia_superbalota`, `calcular_repeticiones_entre_sorteos` y `aplicar_correccion_bonferroni`;
- los repositorios;
- las verificaciones de AE-42;
- el escritor de AE-48.

**Pruebas, todas sintéticas** (`93` nuevas; históricos generados con fórmulas y repositorios fake): cubren
- el vínculo del rango con las ventanas de ML y el rechazo de cualquier desviación;
- la ausencia de flags de rango, semilla o iteraciones y la exclusión de MiLoto;
- la familia de 8 (con un p crudo que pasaría con 4 comparaciones y no pasa con 8) y las estadísticas fijadas;
- la huella de entrada (respuesta conocida, sensibilidad a cambios de datos e invariancia a fechas y orden);
- la calibración (media ≈ 38 y no 42, 25/43 y 15);
- la aritmética exacta, comprobada por AST, y la referencia de bytes independiente de `PYTHONHASHSEED`;
- la prueba anti-recomendaciones: solo descuenta las frases negativas fijas del disclaimer e incluye un control negativo;
- el script: solo lectura, `ROLLBACK`, códigos `2` a `9` y bytes de stdout iguales al archivo capturados de un proceso hijo.

Suite completa en el sandbox Linux de Claude (Python `3.11.15`), en una única corrida: `4264 passed, 0 skipped` (`4171 + 93`), código de salida de pytest `0`, cinco `DeprecationWarning` conocidos de Alembic; `pip check` código `0`. Las pruebas focalizadas (nuevas, ML, estadísticas y AE-40 a AE-48) dieron `1273 passed`. En el sandbox Linux de Claude, AE-49 no se ejecutó contra PostgreSQL ni sobre resultados reales; la validación real la hizo el operador (ver abajo).

**Validación real del operador -evidencia atribuida al usuario, no ejecutada por Claude**: el operador aplicó el parche original (`ae49-referencia-montecarlo-exploratoria.patch`, 103 048 bytes, SHA-256 `1a481f796afeabecb53de96bb9dfd2c97db8d0171b9736a8acb78a1c76b251f7`) sobre `eabbabd`, y el estado de Git mostró exactamente los 13 archivos previstos. En Windows/Python `3.14.6`:
- pasaron las `93` pruebas nuevas, incluida la referencia de bytes, así que el SHA-256 de referencia también coincide en esa plataforma y versión;
- pasaron `1273` pruebas focalizadas, con los cinco `DeprecationWarning` conocidos de Alembic;
- `pip check` y `git diff --check` salieron limpios.

En Windows no se ejecutó la suite completa: la cifra `4264 passed` corresponde únicamente al sandbox Linux de Claude.

El operador ejecutó dos veces `python -m scripts.simular_azar_uniforme --salida ...` contra su PostgreSQL, con archivos distintos fuera del repositorio:
- **Reproducibilidad:** ambas terminaron con código `0` y produjeron exactamente `5499` bytes con SHA-256 `b8b7b31a62ddb9bbdfd00936bf8ca8b846083c17e75d0de511baa35fbdafc4fb`. El SHA anunciado en stderr coincidió con `Get-FileHash`, y la primera evidencia quedó intacta tras la segunda ejecución.
- **Contenido:** cada reporte incluyó BALOTO y BALOTO_REVANCHA con `625` sorteos, `624` transiciones y cuatro estadísticas por juego, además de la familia de ocho comparaciones y `caracter: "exploratorio_sobre_datos_reutilizados"`.
- **Huellas de entrada:** BALOTO `09839571b3d9aab1e65de9823fe56ccbe4e119768e28b08e7835f47a7a246abe`; BALOTO_REVANCHA `42da6777ea61d859ddae762ea3baa03c14cb6d83173199192b2940c38b651f1c`.
- **Tiempos observados:** `128,6 s` y `129,0 s`, propios de ese equipo y de ese estado de datos.
- **Rechazos:** `--semilla 1` devolvió código `7` con stdout vacío, y reutilizar la primera ruta en `--salida` devolvió código `9` con stdout vacío; el archivo original conservó su SHA-256 y su fecha de modificación.

Esta documentación no transcribe los valores de las estadísticas ni de `supera_umbral_exploratorio`. El JSON no registra `transaction_read_only` ni el `ROLLBACK`. La lectura en solo lectura se deduce del código, que confirma `transaction_read_only=on` antes de leer (si no, sale con código `4`) y cierra siempre con `ROLLBACK`, junto con la salida `0` observada.

Estos resultados reales son exploratorios sobre datos reutilizados: no son evidencia confirmatoria ni prospectiva, no convierten `2706` en adelante en un holdout ciego y no modifican el NO-GO de AE-39. Con esta evidencia, **AE-49 queda validada como referencia Monte Carlo exploratoria y reproducible de la consulta manual**: no habilita predicciones, prerregistro ni evaluación.

No se entrenó ni evaluó ML y no se generaron predicciones. Claude no leyó números ganadores reales; la ejecución del operador leyó el histórico `2081..2705` solo para calcular estadísticas agregadas, y el JSON no publica números ganadores. AE-39 sigue en NO-GO y los bloqueos de AE-40 a AE-48 no cambian.

**Etapa AE-50 -verificación local de evidencias de AE-49, validada (Fase 6, preparatoria):** `python -m scripts.verificar_evidencia_montecarlo EVIDENCIA [EVIDENCIA_2]`, ejecutado desde `backend/`, hace una **validación de formato y coherencia interna** de una o dos evidencias JSON producidas por AE-49. Funciona sin conexión, sin base de datos y en solo lectura: los archivos se leen en binario y nunca se modifican.

**No es prueba de autenticidad ni de procedencia**: el SHA-256 identifica los bytes examinados, pero sin firma ni fuente externa de confianza un archivo fabricado y serializado de forma canónica podría pasar. Tampoco confirma que los datos provengan de PostgreSQL, no recalcula las estadísticas y no ejecuta Monte Carlo. Una evidencia válida sigue siendo exploratoria sobre datos reutilizados y no modifica el NO-GO de AE-39; `2706` en adelante sigue sin ser un holdout ciego.

**Qué comprueba.** La regla es estricta: solo acepta los parámetros fijos de AE-49 (semilla `20260926`, B = `10 000`, rango `2081..2705` y familia de 8).
- **Lectura (código `3`):** UTF-8 estricto y JSON estándar. `NaN`, `Infinity` y `-Infinity` se rechazan al leer.
- **Formato (código `4`):**
  - claves duplicadas y claves exactas en todos los niveles;
  - finitud de todos los números;
  - textos, parámetros, rango y familia fijos de AE-49;
  - juegos en orden, con `625`/`624`/`625`;
  - `entrada_sha256` hexadecimal de 64 caracteres (no se exige que difiera entre juegos);
  - tipos y rangos de cada estadística y referencias analíticas;
  - ninguna clave predictiva ni texto de recomendación fuera del disclaimer fijo.
- **Coherencia interna (código `5`):**
  - forma canónica de AE-48/49 (`serializar_reporte`);
  - percentil y p-valor alcanzables con B y compatibles entre sí según la aritmética de AE-49;
  - Bonferroni sobre 8 y `supera_umbral_exploratorio`, recalculados con la función existente del motor.

**Dos rutas**: cada archivo se valida por separado. Si alguno falla, se devuelve su código (primero el del primer archivo). Solo si ambos son válidos se comparan sus bytes reales, no sus huellas (el SHA-256 es solo informativo): si son idénticos, código `0` con `archivos_identicos`; si difieren, código `6`. Que los bytes coincidan no demuestra por sí solo que el proceso sea reproducible.

**Salida**: JSON `verificacion-evidencia-montecarlo/1.0` en stdout, con el SHA-256 y el tamaño de cada archivo, el código y la `entrada_sha256` de cada juego, la lista fija de comprobaciones y un texto fijo de alcance. No copia valores estadísticos ni `supera_umbral_exploratorio`. En caso de error, stdout queda vacío. Códigos de salida:

| Código | Significado |
|---|---|
| `0` | Evidencia válida |
| `1` | Fallo inesperado |
| `2` | Argumentos inválidos |
| `3` | Archivo ilegible |
| `4` | Formato inválido |
| `5` | Incoherencia interna |
| `6` | Dos evidencias válidas pero distintas |

**Archivos**: son nuevos `scripts/verificacion_evidencia_montecarlo.py` (puro) y `scripts/verificar_evidencia_montecarlo.py` (CLI). Viven en `scripts/`, igual que el validador de AE-48, para reutilizar `serializar_reporte` y `CLAVES_PREDICTIVAS`. También reutilizan las constantes y los textos de `app/application/simulaciones/montecarlo_uniforme.py` y `aplicar_correccion_bonferroni`. No cambian `app/`, AE-48, AE-49, las migraciones ni la base de datos, y no hace falta ninguna excepción estructural. Una posible persistencia futura en la tabla `simulaciones` no está decidida ni implementada.

**Pruebas, todas sintéticas** (`104` nuevas; eran `97` en el parche anterior):
- evidencia válida construida con la función real `construir_reporte` de AE-49, sin simular;
- una mutación por invariante, cada una con su código `3`, `4` o `5`;
- `NaN`, `Infinity`, `-Infinity` y `1e999`, más una clave duplicada;
- cinco formas no canónicas;
- incoherencias: p no alcanzable, percentil no múltiplo, p y percentil incompatibles, `supera` invertido y ajustado distinto de 8·p;
- huellas iguales entre juegos, que se aceptan;
- una evidencia real del caso de uso de AE-49 con B = 20, que falla solo por `parametros` y es coherente con sus propios parámetros;
- con dos rutas:
  - el código `6` solo aparece con dos JSON canónicos y válidos que difieren en la revisión Alembic;
  - el fallo individual tiene prioridad;
  - un byte alterado que invalida el archivo da `3`, `4` o `5`;
  - regresión: dos archivos válidos con bytes distintos dan `6` aunque sus resúmenes presenten artificialmente el mismo SHA-256, y `construir_informe` no declara `archivos_identicos` solo porque dos resúmenes tengan la misma huella;
- archivos intactos (SHA-256 y fecha), bytes de stdout capturados de un proceso hijo e informe sin valores estadísticos.

Como medición adicional del sandbox, se generó con el caso de uso de AE-49 una evidencia con sus parámetros fijos (B = 10 000) sobre el histórico sintético (`5598` bytes), y el verificador la aceptó con código `0`.

Mediciones en el sandbox Linux de Claude (Python `3.11.15`): pruebas focalizadas `1377 passed` (`1273 + 104`), con código de salida de pytest `0`. La suite completa se ejecutó una sola vez con el parche anterior, que tenía `97` pruebas nuevas: `4361 passed, 0 skipped` (`4264 + 97`), con código de salida de pytest `0` y los cinco `DeprecationWarning` conocidos de Alembic, y `pip check` con código `0`. No se repitió tras la corrección de la comparación de bytes. En el sandbox Linux de Claude no se usaron evidencias reales ni PostgreSQL; la validación real la hizo el operador (ver abajo).

**Validación real del operador -evidencia atribuida al usuario, no ejecutada por Claude**: el operador aplicó el parche v2 (`ae50-verificacion-evidencia-montecarlo-v2.patch`, 75 506 bytes, SHA-256 `239fa458f077e8dc99651bc58a1a3d48c89737a6efa4c48041943d96472d2e06`) sobre `190b30d`; pasaron la comprobación inversa del parche y `git diff --check`, y solo quedaron modificados los ocho archivos previstos. En Windows/Python `3.14.6`:
- pasaron las `104` pruebas afectadas;
- pasaron `1377` pruebas focalizadas, con los cinco `DeprecationWarning` conocidos de Alembic;
- `pip check`: `No broken requirements found`.

El operador ejecutó el verificador **de forma local y sin PostgreSQL** sobre sus dos evidencias reales de AE-49:
- **`sim-1.json` sola:** código `0`, `formato_y_coherencia_interna_validos` y `no_aplica`; `5499` bytes con SHA-256 `b8b7b31a62ddb9bbdfd00936bf8ca8b846083c17e75d0de511baa35fbdafc4fb`. El archivo quedó intacto.
- **`sim-1.json` y `sim-2.json` juntas:** código `0` y `archivos_identicos`. Ambas tienen `5499` bytes y la misma huella, y conservaron su contenido y su fecha de modificación.

**Límites**: la verificación valida formato y coherencia interna, no autenticidad ni procedencia. Que los bytes coincidan no prueba de dónde vienen los archivos ni que el proceso sea reproducible, y el verificador no confirma que los datos provengan de PostgreSQL ni recalcula estadísticas. La cifra `4361 passed` de la suite completa pertenece solo al parche v1 en el sandbox Linux de Claude: la suite completa de v2 no se ejecutó ni en Windows ni en Linux.

Con esta evidencia, **AE-50 queda validada como verificación local de formato y coherencia interna de evidencias de AE-49**: no habilita predicciones, prerregistro ni evaluación, y una posible persistencia futura en `simulaciones` sigue sin decidir.

No se entrenó ni evaluó ML, no se generaron predicciones y no se leyeron números ganadores. AE-39 sigue en NO-GO y los bloqueos de AE-40 a AE-49 no cambian.

**Etapa AE-51 -auditoría de una evidencia de AE-49 frente al histórico actual, validada (Fase 6):** `python -m scripts.auditar_evidencia_montecarlo EVIDENCIA`, ejecutado desde `backend/`, comprueba si una evidencia JSON de AE-49 corresponde a los datos que hay hoy en PostgreSQL para BALOTO y BALOTO_REVANCHA en `2081..2705`. El resultado es exploratorio sobre datos reutilizados y **no modifica el NO-GO de AE-39**.

**Flujo:**
1. Valida el archivo con AE-50 (formato y coherencia interna) **antes de abrir la conexión**. Si falla, devuelve el código de AE-50 (`3`, `4` o `5`).
2. Abre una transacción `READ ONLY`, la verifica y comprueba la revisión Alembic, reutilizando las funciones de AE-42.
3. Lee cada juego con corte `2705` en la consulta SQL; `2706` en adelante no se lee.
4. Exige con `verificar_rango_principal` de AE-49 que el histórico actual sea exactamente `2081..2705`, con sorteos válidos, y que los parámetros del juego en la base coincidan con el dominio.
5. Termina siempre con `ROLLBACK` y no escribe nada.

**Qué se compara** con la evidencia, por juego:
- la huella normalizada de entrada, calculada con `huella_entrada` de AE-49;
- los totales de sorteos, transiciones y superbalotas;
- las cuatro estadísticas **observadas**, recalculadas con `calcular_estadisticas` de AE-49 y serializadas igual que AE-49. La comparación distingue entero de real.

El informe (`auditoria-evidencia-montecarlo/1.0`) publica solo resultados booleanos por comprobación, junto con las huellas de la evidencia y actual, las listas fijas `comprobado` y `no_comprobado` y un texto fijo de alcance. No copia valores estadísticos. La revisión Alembic de la evidencia se compara con la actual solo a título informativo.

**Qué no se comprueba**: la auditoría **no repite Monte Carlo**. No verifica medias ni desviaciones simuladas, percentiles, p-valores ni Bonferroni frente a los datos, más allá de la coherencia interna de AE-50. Una coincidencia indica que los datos actuales producen la misma entrada y los mismos valores observados; **no prueba la procedencia histórica del archivo** ni cuándo se generó.

**Códigos de salida**:

| Código | Significado |
|---|---|
| `0` | Coincide |
| `1` | Fallo inesperado |
| `2` | Argumentos inválidos |
| `3` | Evidencia ilegible (AE-50) |
| `4` | Formato inválido (AE-50) |
| `5` | Incoherencia interna (AE-50) |
| `6` | Fallo de conexión |
| `7` | Revisión Alembic inesperada |
| `8` | Transacción no `READ ONLY` |
| `9` | Histórico actual o parámetros fuera del contrato de AE-49 |
| `10` | No coincide; el informe se publica igualmente en stdout |

Los códigos `3` y `4` de AE-42 se reasignan a `7` y `8` para no chocar con los de AE-50. En los demás errores, stdout queda vacío.

**Archivos**: son nuevos `scripts/auditoria_evidencia_montecarlo.py` (con repositorios inyectados, sin SQLAlchemy ni Monte Carlo) y `scripts/auditar_evidencia_montecarlo.py` (CLI). Reutilizan sin cambios:
- el validador de AE-50;
- las funciones de AE-49;
- las verificaciones de AE-42;
- los repositorios SQLAlchemy.

No cambian `app/`, AE-42, AE-49, AE-50, las migraciones ni la base de datos, y no hace falta ninguna excepción estructural. La comprobación de parámetros del juego frente al dominio replica en unas pocas líneas la del caso de uso de AE-49, que es privada, para no modificarlo.

**Pruebas, todas sintéticas** (`48` nuevas; repositorios, conexión y sesión fake, e históricos generados con fórmulas):
- evidencia que corresponde al histórico sintético: huella y observados calculados con AE-49, y p-valores coherentes fabricados sin simular;
- coincidencia completa;
- datos actuales distintos: huella y observados discrepan, con código `10` e informe;
- observado alterado con la huella intacta;
- huella alterada;
- distinción entre entero y real;
- histórico actual fuera de contrato, juego inexistente o parámetros distintos del dominio: código `9`;
- errores de AE-50 (`3`, `4` y `5`) y de argumentos (`2`) sin abrir la conexión;
- conexión (`6`) y fallos de AE-42 reasignados (`7` y `8`);
- fallo inesperado (`1`) sin informe parcial;
- orden solo lectura, revisión y consulta, seguido de `ROLLBACK`;
- archivo de evidencia intacto y bytes de stdout capturados de un proceso hijo;
- estructura: sin Monte Carlo, sin escrituras y nada en `app/` que lo mencione.

Como medición adicional del sandbox, la evidencia generada en AE-50 con el caso de uso real de AE-49 y sus parámetros fijos (B = 10 000) sobre el histórico sintético (`5598` bytes) se auditó con código `0` y `coincide` en ambos juegos.

Mediciones en el sandbox Linux de Claude (Python `3.11.15`): pruebas focalizadas `1425 passed` (`1377 + 48`); suite completa en una única corrida, `4416 passed, 0 skipped` (`4368 + 48`), con código de salida de pytest `0` y los cinco `DeprecationWarning` conocidos de Alembic; `pip check` con código `0`. En el sandbox Linux de Claude no se usaron PostgreSQL ni evidencias reales; la validación real la hizo el operador (ver abajo).

**Validación real del operador -evidencia atribuida al usuario, no ejecutada por Claude**: el operador aplicó el parche original (`ae51-auditoria-evidencia-montecarlo.patch`, 61 411 bytes, SHA-256 `19eee4ce3650f4c37889077ca832d637a589df36c2d81892f5051fe0f2e6d03c`) sobre `ab9f977`; pasaron la comprobación inversa y `git diff --check`, y solo cambiaron los ocho archivos previstos. En Windows/Python `3.14.6`:
- pasaron las `48` pruebas nuevas;
- pasaron `1425` pruebas focalizadas, con los cinco `DeprecationWarning` conocidos de Alembic;
- `pip check`: `No broken requirements found`.

En Windows no se ejecutó la suite completa: la cifra `4416 passed` corresponde solo al sandbox Linux de Claude.

El operador auditó `sim-1.json` frente a su PostgreSQL:
- código `0` y resultado `coincide`, con revisión Alembic `0006` tanto en la evidencia como en la base actual;
- en BALOTO y BALOTO_REVANCHA coincidieron la huella normalizada, los totales y las cuatro estadísticas observadas. Huellas de entrada: BALOTO `09839571b3d9aab1e65de9823fe56ccbe4e119768e28b08e7835f47a7a246abe`; BALOTO_REVANCHA `42da6777ea61d859ddae762ea3baa03c14cb6d83173199192b2940c38b651f1c`;
- `sim-1.json` conservó sus `5499` bytes, su SHA-256 `b8b7b31a62ddb9bbdfd00936bf8ca8b846083c17e75d0de511baa35fbdafc4fb` y su fecha de modificación.

**Límites**: la auditoría compara la evidencia con el histórico **actual**. No acredita cuándo ni de dónde se generó el archivo, no repite Monte Carlo y no verifica frente a los datos los valores simulados (medias, desviaciones, percentiles, p-valores ni Bonferroni). El JSON no registra `transaction_read_only` ni el `ROLLBACK`: la lectura en solo lectura se deduce del código, que verifica `transaction_read_only=on` antes de leer (si no, sale con código `8`) y cierra siempre con `ROLLBACK`, junto con la salida `0` observada.

Con esta evidencia, **AE-51 queda validada como auditoría de una evidencia de AE-49 frente al histórico actual `2081..2705`**. El resultado sigue siendo exploratorio sobre datos reutilizados, no habilita predicciones, prerregistro ni evaluación y no modifica el NO-GO de AE-39.

No se entrenó ni evaluó ML y no se generaron predicciones. Claude no leyó números ganadores reales; la auditoría del operador leyó el histórico `2081..2705` solo para calcular la huella y las estadísticas agregadas, y el informe no publica números ganadores. AE-39 sigue en NO-GO y los bloqueos de AE-40 a AE-50 no cambian.

**Etapa AE-52 -registro prospectivo de ML (preparación de una evaluación prospectiva), validada:** primera etapa para poder evaluar una estrategia de ML de forma prospectiva, como exige el NO-GO de AE-39: una evaluación prerregistrada antes de observar los sorteos posteriores a ese prerregistro. AE-52 **no genera predicciones**, no entrena ni carga modelos, no evalúa resultados y **no modifica el NO-GO**. Tampoco activa recomendaciones, apuestas ni predicciones para usuarios. **AE-52 no acumula evidencia prospectiva**: el único registro real que admite es un borrador sin salidas, y ningún sorteo cuenta todavía para ningún mínimo.

**Revisión de AE-39 a AE-51 (hechos del repositorio):**
- **Estrategia congelable:** la única configuración fija existente es la Regresión Logística L2 calibrada de AE-36 (`entrenar_modelo_calibrado` y `predecir_probabilidades` en `ml/modelo.py`): semilla `42`, `C = 1.0`, `lbfgs`, `2000` iteraciones, calibración con el `20 %` final, siete features retrospectivas y calentamiento de `50` sorteos. AE-37 y AE-38 eligen su configuración, e incluso su familia, dentro de cada bloque, así que no son congelables sin una decisión adicional. Que sea la única congelable no significa que esté aprobada ni validada como predictiva: falló en AE-36 a AE-39.
- **Salida:** una probabilidad de aparición por cada número del rango (43) para el sorteo siguiente.
- **Referencia de azar y métricas:** `baseline_uniforme` = `5/43`; Log Loss y Brier como métricas principales y Precision@5 y Recall@5 como secundarias (AE-36); diferencia orientada como uniforme − estrategia y cada juego por separado (AE-39).
- **Qué impide usarla:**
  - el NO-GO de AE-39 en ambos juegos;
  - AE-40/41 solo autorizan un prerregistro con al menos `100` sorteos nuevos contiguos desde `2706` (objetivo `2805`) y tras validación humana expresa. **`8`/`100` en la última medición registrada**: evidencia del operador en la validación de AE-48 (JSON `1.1` de `consultar_estado_prediccion`, `2414` bytes, SHA-256 `bc6660fbae9e72c4a72f9e34473d64dd835dbfe445c52bcf98f8a47d6069be85`, y comparación `1.2` con variación `0`). Ese formato no registra la fecha de la medición, y AE-52 no volvió a medir el contador;
  - AE-43 solo construye features de inferencia con cortes de DESARROLLO (`≤ 2589`): predecir un sorteo `≥ 2706` exige un contrato nuevo y validado;
  - los modelos nunca se persisten, y el tramo de entrenamiento de una versión congelada no está decidido;
  - las condiciones «protocolo prospectivo prerregistrado» y «evaluación prospectiva positiva» de AE-46 no tienen mecanismo.

**¿Se pueden guardar salidas antes de cada sorteo próximo? No, sin relajar las reglas.** Hay tres autorizaciones distintas:
1. **Reabrir el desarrollo predictivo (AE-39):** solo con al menos `100` sorteos nuevos por juego desde `2706`, o con una hipótesis nueva y prerregistrada que no se seleccione a partir de estos resultados (sección de AE-39; `PoliticaReaperturaML` en `ml/tipos.py`, con `minimo_sorteos_nuevos_requeridos` y `requiere_hipotesis_nueva_prerregistrada=True`). Reabrir no es un GO. La segunda vía no tiene mecanismo en el código: el bloqueo operativo de AE-41 solo traduce el conteo de AE-40.
2. **Prerregistro formal (AE-40/41):** `evaluar_elegibilidad_reapertura_ml` devuelve `ELEGIBLE_PARA_PRERREGISTRO` solo con `100` o más sorteos contiguos desde `2706`, y AE-41 lo traduce a `AUTORIZADO_PARA_PRERREGISTRO`, que «nunca significa autorizacion para entrenar, para observar resultados, para generar predicciones, ni para desplegar -unicamente que una etapa FUTURA e INDEPENDIENTE podria iniciar un prerregistro experimental, tras validacion humana expresa» (`ml/autorizacion_operativa.py`).
3. **Registro experimental en segundo plano:** por debajo de `100`, AE-41 devuelve `BLOQUEADO_DATOS_INSUFICIENTES` con el motivo «ninguna operacion predictiva nueva queda autorizada» (`evaluar_autorizacion_operativa_desde_elegibilidad`). Calcular una probabilidad por número para el sorteo siguiente es una operación predictiva nueva. Además, AE-41 coloca el «prerregistro experimental» detrás de la autorización, no fuera de ella: llamarlo experimental o de segundo plano no lo saca del bloqueo. También hay bloqueos técnicos:
   - `construir_filas_inferencia` (AE-43) rechaza cortes `> 2589` y cualquier sorteo de `CONSUMIDO_AE36` o `HOLDOUT` como feature;
   - el caso de uso de AE-36 pide y comprueba el corte `2705` (`CORTE_CONTRATO_AE36`);
   - `ReportePrediccionJuego` rechaza probabilidades en `__post_init__`;
   - una salida para `2714` necesitaría como entrada `2706..2713`, y AE-40/41 no autorizan observar esos resultados.

Por eso AE-52 **no habilita una vía experimental**:
- un protocolo real solo puede ser el borrador, con los siete pendientes;
- los protocolos cerrados solo existen con `sintetico: true`, que nunca cuenta;
- `verificar` lo declara con `admite_salidas: false` y con el texto de alcance «no admite salidas y no acumula evidencia prospectiva».

**Dos esperas sucesivas con las reglas vigentes:**
- **Primera espera:** `100` sorteos nuevos desde `2706` para que AE-41 autorice un prerregistro (objetivo `2805`).
- **Segunda espera:** `100` sorteos **prospectivos** por juego, posteriores al protocolo, para la evaluación (`REGLAS_EVALUACION_AE52`, con la constante vigente de AE-39).

No pueden solaparse: sin autorización no hay protocolo cerrado, y sin protocolo no cuenta ningún sorteo. `2706..2805` no cuenta para la segunda espera, porque esos sorteos ocurren antes del prerregistro. Los sorteos históricos y Monte Carlo sirven para pruebas y exploración, pero no cuentan como sorteos futuros: el corte los excluye y los registros de prueba llevan `sintetico: true`.

La única vía que podría acortar la espera es la hipótesis nueva prerregistrada de AE-39. Exigiría una decisión científica expresa del operador y una etapa que modifique el bloqueo validado de AE-41. AE-52 no toma esa decisión.

**Siguiente trabajo que sí puede hacerse ahora** (sin predicciones ni lectura de números ganadores):
1. **Medir el contador actual.** El operador puede hacerlo con la consulta de solo lectura ya validada, contra su PostgreSQL:

   ```
   python -m scripts.consultar_estado_prediccion --salida NUEVA.json --comparar ANTERIOR.json
   ```

   Esa consulta (AE-45/47/48) compara el contador actual con la evidencia de `8`/`100`.
2. **Fijar antes de cualquier dato prospectivo las decisiones que no dependen de datos:**
   - la regla estadística de decisión (unidad de remuestreo, nivel y condiciones);
   - el tramo de entrenamiento;
   - el mecanismo de sellado temporal.

   Hoy el protocolo solo marca pendientes y no guarda el valor decidido. Una etapa siguiente añadiría esos valores y la regla como código puro, probado con datos sintéticos. Requiere que el operador tome esas decisiones.
3. **Contrato de inferencia prospectiva.** Ampliaría AE-43 más allá de `DESARROLLO`, siempre detrás del bloqueo de AE-41. Puede escribirse y probarse con datos sintéticos, pero toca un contrato validado y necesita autorización expresa.

**Qué añade AE-52:** un registro de **solo anexado**, con una entrada por archivo `NNNNNN.json` en JSON canónico, nombrada solo por su secuencia y encadenada con el hash de la anterior (`app/application/ml/registro_prospectivo.py`, puro). Tiene tres tipos de entrada, siempre separados:
1. **`protocolo`** (la primera y única): versión exacta de la estrategia (huella SHA-256 del código con fines de línea normalizados, parámetros leídos del código validado y entorno), corte temporal por juego, reglas fijas y decisiones pendientes. Con pendientes es un **borrador** y no admite salidas. Un protocolo real solo puede ser ese borrador.
2. **`prediccion`**: salida registrada **antes** del sorteo, con la huella de su entrada (histórico contiguo que termina exactamente en el sorteo anterior al objetivo) y una probabilidad por número. En AE-52 solo existe en registros sintéticos.
3. **`resultado`**: números del sorteo, incorporados **después**, en otra entrada que referencia el hash de su predicción.

Reglas que se aplican al anexar y al verificar:
- un protocolo real distinto del borrador se rechaza;
- no se acepta ningún sorteo igual o posterior al objetivo como entrada;
- no cuenta ningún sorteo ya conocido al registrar el protocolo;
- solo hay un protocolo por registro y cada predicción debe llevar su hash, así que nunca se mezclan versiones;
- no se repite ni se retrocede un objetivo;
- no hay un resultado sin su predicción previa ni dos resultados para la misma predicción;
- una predicción no puede llevar el resultado.

**Anexado concurrente:** cada entrada se publica con el enlace duro exclusivo de AE-48 en `NNNNNN.json`, así que la exclusividad por nombre es también exclusividad por secuencia.
- Si dos operaciones leen la misma cabeza y construyen entradas distintas con la misma secuencia, solo la primera que publica avanza la cadena.
- La otra recibe `SecuenciaOcupadaError` (código `8`), no escribe nada y el registro queda válido.
- La lectura ignora los temporales `.evidencia-ae48-*.tmp` de una publicación en curso, que nunca son entradas; cualquier otro archivo ajeno sigue siendo una inconsistencia (código `5`).

**Reglas fijadas** (`REGLAS_EVALUACION_AE52`; un protocolo con otras se rechaza):
- mínimo de `100` resultados prospectivos por juego, reutilizando la constante vigente de AE-39, que no se cambia retroactivamente;
- Log Loss y Brier como métricas principales y Precision@5 y Recall@5 como secundarias;
- referencia uniforme `k/n`, con la diferencia orientada como uniforme − estrategia;
- juegos por separado;
- sorteos consecutivos sin sustitución: las omisiones se informan y no se sustituyen;
- ningún agregado antes de alcanzar el mínimo.

El corte temporal es el último sorteo conocido de cada juego al cerrar el protocolo (`≥ 2705`); solo cuentan objetivos posteriores.

**Pendientes** (el borrador los lista y no se cierran en AE-52):
- `aprobacion_de_la_estrategia_a_congelar`: evaluar prospectivamente una estrategia que ya falló es una decisión científica del operador;
- `tramo_de_entrenamiento`: `2081..2590`, `2081..2705` u otro;
- `contrato_de_inferencia_prospectiva`: ampliar AE-43 con su propia validación;
- `autorizacion_ae41_para_prerregistro`: no se cumplía en la última medición registrada (`8`/`100`);
- `corte_temporal_por_juego`: se fija al cerrar el protocolo;
- `regla_estadistica_de_decision`: unidad de remuestreo, nivel y condiciones; una adaptación candidata de la regla de seis condiciones de AE-39 con los sorteos como unidad no está aprobada;
- `mecanismo_de_sellado_temporal_externo`.

**Anterioridad**: la cadena prueba el **orden** interno y detecta cualquier cambio en una entrada que tenga otra detrás, pero **no acredita la fecha**: un registro completo podría fabricarse después, y la última entrada solo se comprueba frente a una cabeza anclada. Para que la anterioridad sea verificable, el hash de cada predicción (o la cabeza de la cadena) debe anclarse **antes del sorteo** en una fuente externa de confianza, y compararse con la hora oficial del sorteo. Opciones posibles:
- un sello de tiempo RFC 3161 de una autoridad de sellado;
- OpenTimestamps;
- una publicación en un registro externo de solo anexado con hora del servidor, por ejemplo un commit firmado y enviado a un repositorio remoto antes del sorteo.

La elección queda pendiente. `verificar` publica todos los hashes y la cabeza para facilitar ese anclaje.

**CLI** `python -m scripts.registro_prospectivo_ml`, local y sin base de datos:
- **`iniciar-borrador DIRECTORIO`:** crea `000001.json` con el borrador real de la estrategia candidata, en un directorio existente y vacío, y nunca sobrescribe.
- **`verificar DIRECTORIO`:** es de solo lectura y publica el resumen: protocolo (con `admite_salidas`), hashes, cabeza, progreso por juego con omisiones y faltantes, y `evaluable: false` con sus motivos. *Precisión de AE-58:* `faltantes` es un recuento descriptivo (100 menos todos los resultados incorporados, incluidos los posteriores a una omisión), no elegibilidad; `omisiones` son solo los huecos anteriores al último objetivo registrado.

No existe un comando para registrar predicciones o resultados: `anexar_entrada` solo se usa en pruebas sintéticas. Códigos de salida:

| Código | Significado |
|---|---|
| `0` | Correcto |
| `1` | Fallo inesperado |
| `2` | Argumentos inválidos |
| `3` | Registro ilegible |
| `4` | Entrada inválida o regla incumplida |
| `5` | Cadena o nombres inconsistentes |
| `8` | Fallo al escribir, incluida una secuencia ya publicada por otra operación |
| `9` | Directorio no permitido |

**Qué puede ejecutarse ya y qué no**:
- **Ya, sin conexión:** iniciar el borrador y verificar registros. Ninguna de las dos operaciones acumula evidencia.
- **Ya, solo el operador:** medir el contador con la consulta de solo lectura de AE-45/47/48.
- **Requiere decisión del operador:**
  - aprobar la estrategia;
  - el tramo de entrenamiento;
  - la regla estadística;
  - el mecanismo de sellado;
  - si se sigue la vía de la hipótesis nueva de AE-39.
- **Requiere otra etapa validada:**
  - el contrato de inferencia prospectiva;
  - la generación de salidas;
  - la incorporación de resultados desde la base con solo lectura;
  - el cierre del protocolo con los cortes reales cuando AE-41 lo autorice;
  - la evaluación.

**Archivos**: son nuevos `app/application/ml/registro_prospectivo.py` y `scripts/registro_prospectivo_ml.py`, junto con sus pruebas. El módulo es puro: sin reloj, azar, archivos ni base de datos, y sin importar el modelo, la inferencia ni el resolvedor. No cambian AE-36 a AE-51, las migraciones ni la base de datos, y no hace falta ninguna excepción estructural. La condición de AE-46 sigue sin cumplirse y `desbloqueable` sigue en `false`.

**Pruebas, todas sintéticas** (`110` nuevas; históricos generados con fórmulas y salidas fabricadas solo para probar el formato):
- reglas fijas: un mínimo distinto de `100` se rechaza;
- juegos y cortes;
- borrador con sus pendientes;
- un protocolo real distinto del borrador se rechaza, tanto al construirlo como si se fabrica; el resumen incluye `admite_salidas`;
- forma canónica, `NaN` y claves duplicadas;
- cadena: modificar, quitar, reordenar o duplicar entradas se detecta; la última entrada solo se detecta frente a una cabeza anclada;
- un segundo protocolo o una predicción de otra versión se rechazan;
- resultados futuros como entrada, sorteos ya conocidos, huecos, borrador, duplicados, retrocesos y salidas mal formadas se rechazan;
- resultado sin predicción, duplicado o con números inválidos se rechaza;
- resumen con omisiones y faltantes, y evaluación nunca disponible;
- anexado concurrente: desde la misma cabeza se construyen dos entradas con secuencia `3` (la predicción de `2715` y el resultado de `2714`). Se prueba en el mismo proceso y con dos procesos reales sincronizados. Solo una se publica; la otra falla con `SecuenciaOcupadaError` y el registro queda válido con tres archivos. El temporal de una publicación en curso no se confunde con una entrada;
- CLI:
  - parámetros leídos del código y huella independiente del fin de línea;
  - no sobrescribir: directorio no vacío, archivo que aparece antes de publicar o entre la validación y la escritura;
  - verificación con códigos `3`, `4` y `5`;
  - bytes de stdout capturados de un proceso hijo;
  - estructura sin base de datos ni llamadas de entrenamiento o predicción.

**Historia de la corrección (v1 → v2)**: el primer parche (`ae52-registro-prospectivo-ml.patch`, 110 369 bytes, SHA-256 `628fd29e4c4c40645b2f3d021158ad1e08bb6ac8dbd539d60c7cce7fe106a823`) tenía tres defectos:
- nombraba las entradas `NNNNNN-tipo.json`, así que dos operaciones con la misma cabeza podían publicar `000003-prediccion.json` y `000003-resultado.json`;
- aceptaba un protocolo real cerrado, lo que habría permitido registrar salidas reales desde la biblioteca;
- afirmaba «hoy `8`/`100`» sin medirlo.

Sobre v1, las pruebas de regresión dieron `21 failed, 89 passed` (código de pytest `1`); incluyen las pruebas existentes adaptadas al nuevo nombre de archivo. La prueba con dos procesos terminó con códigos `[0, 0]` y dejó ambos archivos `000003-*`.

**Mediciones en el sandbox Linux de Claude** (Python `3.11.15`, sin PostgreSQL ni datos reales):
- pruebas de AE-52: `110 passed`, código de pytest `0`; la prueba de dos procesos pasó en 15 de 15 repeticiones;
- focalizadas: `1535 passed` (`1425 + 110`), código `0`;
- suite completa en una única corrida: `4526 passed, 0 skipped` (`4416 + 110`), código `0`, con los cinco `DeprecationWarning` conocidos de Alembic;
- `pip check`: código `0`;
- borrador real: `iniciar-borrador` y `verificar` terminaron con código `0`, con `admite_salidas: false` y `huella_codigo` `917abfbc824cc64d215739a515271c81a0d0dc246e04f083f3b933c7973c0d87`. La entrada `000001.json` tiene los mismos bytes que en v1 (`2276` bytes, SHA-256 `edc866d68f1cfef5625a41308180564a915dbc10650f52d53addbaf4cc67f5c4`); solo cambia el nombre del archivo. Repetir `iniciar-borrador` sobre el mismo directorio dio `9`.

La huella del código debería coincidir en Windows, porque normaliza los fines de línea. El SHA-256 de la entrada no coincidirá, porque incluye la versión de Python. La validación del operador en Windows/Python `3.14.6` se registra a continuación.

**Validación real del operador -evidencia atribuida al usuario, no ejecutada por Claude**: en Windows/Python `3.14.6`, el operador aplicó el parche v2 (`ae52-registro-prospectivo-ml-v2.patch`, 143 973 bytes, SHA-256 `7f7331884e7c4b87431119340b4541a7d52ea50bd7e2b347c436ef714115b545`) sobre `3cb593d458548f1005559ce877e1b321ea3ed739`. `git apply --reverse --check` y `git diff --check` fueron correctos, y los cambios locales fueron exactamente los siete archivos previstos.
- **Pruebas:** las `110` pruebas nuevas de AE-52 pasaron, incluidas las de dos procesos concurrentes. Las `1535` pruebas focalizadas pasaron, con los cinco `DeprecationWarning` conocidos de Alembic. `pip check` informó `No broken requirements found`. En Windows no se ejecutó la suite completa: la cifra `4526 passed` corresponde únicamente al sandbox Linux de Claude con v2.
- **Borrador real:** `iniciar-borrador` y `verificar` terminaron con código `0`. La entrada `000001.json` tiene `2275` bytes y SHA-256 `7f5d7b19c87b48b2bfc3124c04d0b0e6aa16f02994ee30e71e84aa1b14d268ae`; difiere de la del sandbox (`2276` bytes) porque incluye la versión de Python. El resumen dio estado `borrador`, `admite_salidas: false` y `evaluable: false`, y la huella de código `917abfbc824cc64d215739a515271c81a0d0dc246e04f083f3b933c7973c0d87` coincidió con la del sandbox.
- **Rechazos:** repetir `iniciar-borrador` devolvió código `9` con stdout vacío y el archivo original intacto. Tras añadir `nota.txt` al directorio temporal, `verificar` devolvió código `5` con stdout vacío y conservó el archivo inicial.
- **Contador medido ahora por el operador:** la consulta real de solo lectura `python -m scripts.consultar_estado_prediccion` terminó con código `0`. BALOTO y BALOTO_REVANCHA quedaron cada uno en `bloqueado_datos_insuficientes`, con `8` sorteos nuevos y `92` faltantes. Es una medición nueva, distinta de la «última medición registrada» de AE-48 citada arriba, aunque da la misma cifra. El JSON de AE-48 no contiene fecha y en esta consulta no se guardó un archivo de evidencia nuevo, así que la fecha de la medición no queda registrada en el repositorio.

**Límites de esta validación**: «validada» se refiere a la herramienta de borrador y verificación del registro, a sus reglas y a su anexado concurrente probado con datos sintéticos. No hay un protocolo formal aprobado, no se inició ningún registro de predicciones, no hay una evaluación prospectiva, positiva ni negativa, y ningún sorteo cuenta todavía para ningún mínimo. AE-41 sigue en `bloqueado_datos_insuficientes` y ninguno de los siete pendientes se cerró. La anterioridad sigue sin sellado temporal externo.

Con esta evidencia, **AE-52 queda validada como herramienta local de borrador y verificación del registro prospectivo**: no habilita predicciones, prerregistro ni evaluación, y no acumula evidencia prospectiva.

No se entrenó ni evaluó ML, no se generaron predicciones y no se leyeron números ganadores. AE-39 sigue en NO-GO y los bloqueos de AE-40 a AE-51 no cambian.

**Etapa AE-53 -contrato preparatorio de evaluación prospectiva, validada:** prepara, antes de que exista cualquier dato prospectivo, tres piezas verificables en `app/application/ml/especificacion_evaluacion_prospectiva.py`, un módulo puro: sin reloj, azar, archivos ni base de datos.
- una especificación candidata;
- la clasificación de la secuencia de objetivos de un juego;
- las métricas de un único sorteo.

Queda **fuera** de AE-53: no hay bootstrap, prueba de signos, intervalos, agregados entre sorteos ni veredictos estadísticos. Los sorteos son independientes, pero eso no implica que lo sean las diferencias de pérdida entre predicciones sucesivas, porque cada predicción depende del histórico anterior. Tampoco puede presuponerse que un bootstrap iid o una prueba de signos exacta conserven su interpretación. La inferencia la elegirá y justificará una etapa posterior, antes de implementarla.

AE-53 no cierra ningún pendiente del borrador de AE-52, incluido `regla_estadistica_de_decision`. No modifica el NO-GO de AE-39, el bloqueo de AE-41 ni las condiciones de AE-46. No activa recomendaciones, apuestas ni predicciones para usuarios.

**Qué fija ya el repositorio** (AE-53 lo referencia y no lo redefine):
- `REGLAS_EVALUACION_AE52` (`registro_prospectivo.py`):
  - Log Loss y Brier como métricas principales; Precision@5 y Recall@5 como secundarias;
  - referencia uniforme `k/n`, con la diferencia orientada como uniforme − estrategia;
  - juegos por separado;
  - mínimo de `100` resultados por juego;
  - sorteos consecutivos sin sustitución;
  - ningún agregado antes del mínimo.
- Las definiciones de las métricas en `metricas.py` y de la referencia uniforme en `baselines.py`.
- Los siete pendientes del borrador de AE-52.
- Las seis condiciones de AE-39 (`incertidumbre.py`), que son **históricas**: se aplicaron a los 18 bloques de AE-38 y no forman parte de este contrato.

**Equivalencia Precision@5 = Recall@5** (`metricas.py`): en cada sorteo, Precision@5 es `aciertos / 5` (top-5 de 43 números) y Recall@5 es `aciertos / 5` (5 números extraídos). Son la misma cantidad sorteo a sorteo, y también en sus promedios; AE-39 ya las informó con un único valor. En la práctica, las condiciones 5 y 6 de AE-39 eran la misma desigualdad: **cinco condiciones distintas**, no seis. No cambia ninguna decisión histórica y AE-39 no se reescribe. `metricas_por_sorteo` comprueba esta identidad y lanza un error si no se cumple.

**Especificación candidata** (`ESPECIFICACION_CANDIDATA_AE53`, `estado: "candidata_no_aprobada"`). Tiene tres grupos separados:
- **`fijado_por_ae52`:** copia de `REGLAS_EVALUACION_AE52` tomada de la constante.
- **`propuestas`**, todas con `estado: "propuesta_no_aprobada"`:
  - `horizonte`: los primeros `100` objetivos posteriores al corte, con un único análisis al completarlos;
  - `omisiones`: cualquier omisión dentro del horizonte haría no evaluable ese juego, sin sustituirla ni ampliar la ventana;
  - `referencia_secundaria`: la definición vigente, es decir, la uniforme con el desempate determinista, lo que equivale al boleto `1..5`, pareada en los mismos sorteos. Reemplazarla por la esperanza analítica `5/43` compararía una realización con un valor poblacional.
- **`pendientes`**, todos con `valor: null`: `unidad_y_metodo_inferencial`, `tratamiento_dependencia_serial`, `nivel_y_umbral`, `efecto_minimo`, `multiplicidad_entre_juegos` y `mecanismo_de_sellado_temporal_externo`.

`huella_especificacion()` es el SHA-256 del JSON canónico, con el mismo formato que las entradas de AE-52. **Identifica la especificación exacta y detecta cambios, pero no es un sello temporal**: no prueba cuándo se fijó. La anterioridad exige un anclaje externo antes del primer dato prospectivo, y ese mecanismo sigue pendiente.

**`validar_secuencia_objetivos(corte, ultimo_sorteo_ocurrido, objetivos_con_prediccion, objetivos_con_resultado)`**, para un juego, clasifica la ventana `corte+1..corte+100` así:
- **resueltos:** con predicción y resultado;
- **resultado pendiente:** el sorteo ya se celebró y tiene predicción, pero falta su resultado;
- **futuros:** el sorteo aún no se celebró, tenga o no predicción; **nunca cuentan como omisión**. *Precisión de AE-58:* bajo AE-52 solo el sorteo `ultimo_sorteo_ocurrido + 1` puede tener predicción sin haber ocurrido; la función acepta un dominio más amplio que los estados posibles de AE-52;
- **omisiones:** el sorteo ya se celebró y no tiene predicción;
- **fuera de horizonte:** predicciones posteriores a la ventana, que no la extienden.

`ultimo_sorteo_ocurrido` (el último sorteo celebrado, tenga o no resultado incorporado) es la entrada que permite distinguir de forma inequívoca un objetivo futuro de una omisión. Por eso el contrato lo exige, además de las dos listas de objetivos.

El estado es estructural: `incompleta`, `completa` o `no_evaluable_por_omision`. `reglas_aplicadas` indica que el horizonte y las omisiones son propuestas no aprobadas.

Se rechazan:
- objetivos iguales o anteriores al corte;
- duplicados, `bool` o valores no enteros;
- resultados sin predicción;
- resultados de sorteos que aún no se celebraron;
- un `ultimo_sorteo_ocurrido` anterior al corte.

La función no puede comprobar que una predicción se registrara antes de su sorteo: eso depende del registro de AE-52 y de un sellado externo. Tampoco puede comprobar que `ultimo_sorteo_ocurrido` sea cierto.

**`metricas_por_sorteo(codigo_juego, sorteo_objetivo, probabilidades, numeros)`**:
- **qué calcula:** Log Loss, Brier y Precision@5/Recall@5 de la estrategia y de la uniforme para un único sorteo de BALOTO o BALOTO_REVANCHA, más las diferencias uniforme − estrategia de ese sorteo;
- **cómo:** con las funciones vigentes `metricas.evaluar` y `baselines.baseline_uniforme`, sin redefinirlas. El rango y la cantidad salen del dominio del juego, porque la identidad Precision@5 = Recall@5 solo vale con 5 de 43;
- **qué rechaza:** probabilidades que no sean exactamente 43 valores reales en `(0, 1)`, y números repetidos, fuera de rango o en cantidad distinta de 5;
- **qué no hace:** agregar entre sorteos; los valores son descriptivos.

**Procedencia**: el módulo no puede saber si los valores que recibe son sintéticos o reales. La barrera es estructural, no una etiqueta. No hay ningún llamador fuera de sus pruebas, ni conexión con el registro, los repositorios, los scripts o las rutas. Del registro solo importa la constante `REGLAS_EVALUACION_AE52`, y no importa `incertidumbre` ni sus funciones privadas.

**Archivos**: son nuevos `app/application/ml/especificacion_evaluacion_prospectiva.py` y `tests/unit/ml/test_especificacion_evaluacion_prospectiva.py`. No cambia ningún archivo de AE-39 a AE-52, y no hace falta ninguna excepción estructural.

**Pruebas, todas sintéticas y deterministas** (`59` nuevas, con números y probabilidades construidos a mano):
- **especificación:** grupos, estados, pendientes sin valor, ningún estado aprobado ni claves de inferencia, huella estable y sensible a cambios, nota sobre la huella, y siete pendientes de AE-52 intactos;
- **secuencia:**
  - ventana exacta, e `incompleta` con 0, 50 o 99 resueltos;
  - `completa` con 100;
  - un objetivo futuro con o sin predicción es pendiente, no omisión, y un sorteo celebrado con predicción sin resultado queda con resultado pendiente;
  - un sorteo celebrado sin predicción es omisión, incluso con el resto completo, y lo posterior al horizonte no amplía la ventana;
  - informe inmutable y rechazos;
- **métricas:** igualdad con `metricas.evaluar` y `baseline_uniforme` sobre filas construidas a mano, Log Loss y Brier analíticos de la uniforme, Precision@5 de la uniforme igual a la del boleto `1..5`, identidad Precision@5 = Recall@5 y error ante una discrepancia forzada, diferencias orientadas, rechazos y ausencia de agregados;
- **estructura:** sin sklearn, base de datos, reloj ni azar; sin importar `incertidumbre`, la inferencia, el resolvedor, el diagnóstico, el modelo ni nombres privados; sin bootstrap, percentiles, signos, intervalos ni veredictos; nada fuera de `ml/` lo usa.

**Mediciones en el sandbox Linux de Claude** (Python `3.11.15`, sin PostgreSQL ni datos reales): antes de implementar, las pruebas nuevas fallaron al recolectarse porque el módulo no existía (código de pytest `2`); después, `59 passed` (código `0`). Focalizadas: `318 passed` (código `0`), que son las nuevas más métricas, baselines, registro de AE-52 y su CLI, incertidumbre, diagnóstico, predicción bloqueada y estructura de AE-43. Suite completa en una única corrida: `4526 + 59 = 4585 passed`, `0 skipped`, código `0`, con los cinco `DeprecationWarning` conocidos de Alembic. `pip check` y `git diff --check`: código `0`. La validación del operador en Windows/Python `3.14.6` se registra a continuación.

**Validación real del operador -evidencia atribuida al usuario, no ejecutada por Claude**: el operador aplicó en Windows el parche completo `ae53-contrato-evaluacion-prospectiva.patch` (60 260 bytes, SHA-256 `7ce4f66745c1ab85f8c26c944b53dd1460646760c5d00ee17e39af1616824a56`) sobre `fa2df137b262501972e881a8fdef1405c766c673`. `git apply --check`, la aplicación, `git apply --reverse --check` y `git diff --check` fueron correctos, y los cambios locales fueron exactamente los cinco archivos previstos. En Windows/Python `3.14.6`, con el entorno virtual del proyecto:
- `59` pruebas nuevas de AE-53: `59 passed`, código `0`;
- conjunto focalizado: `318 passed`, código `0`;
- `pip check`: `No broken requirements found`, código `0`.

La suite completa `4585 passed, 0 skipped` corresponde únicamente al sandbox Linux de Claude con Python `3.11.15`; en Windows no se ejecutó completa. Un primer intento en Windows usó por error el Python global, sin pytest, y no llegó a ejecutar pruebas; fue un problema del entorno de la orden, no un fallo del código. En esta validación no se consultó PostgreSQL, no se entrenó ni cargó ningún modelo, no se generaron predicciones y no se leyeron números ganadores.

**Límites de esta validación**: «validada» se refiere a AE-53 como **herramienta preparatoria**, es decir, al contrato del módulo (especificación, huella, clasificación de la secuencia y métricas por sorteo) y a sus pruebas sintéticas.
- La especificación candidata sigue en `candidata_no_aprobada`.
- Sus propuestas (horizonte de `100`, efecto de las omisiones y referencia secundaria) siguen en `propuesta_no_aprobada`.
- Sus seis decisiones pendientes siguen sin valor.
- La huella no es un sello temporal y ninguna huella se ha anclado externamente.
- No se eligió ningún método inferencial.
- Los siete pendientes del borrador de AE-52 siguen abiertos, incluido `regla_estadistica_de_decision`.
- El NO-GO de AE-39, el bloqueo de AE-41 y las condiciones de AE-46 no cambian.

Con esta evidencia, **AE-53 queda validada como contrato preparatorio de evaluación prospectiva**: no aprueba una regla estadística, no habilita predicciones, prerregistro ni evaluación, y no acumula evidencia prospectiva.

No se entrenó ni evaluó ML, no se generaron predicciones y no se leyeron números ganadores. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos y los bloqueos de AE-40 a AE-52 sin cambios.

**Etapa AE-54 -banco de exploración sintética de métodos de inferencia, validada:** AE-53 dejó sin valor `unidad_y_metodo_inferencial` y `tratamiento_dependencia_serial`. La razón es que predicciones sucesivas pueden compartir histórico, así que las diferencias de pérdida por sorteo pueden tener dependencia serial. AE-54 aporta información para elegir **después** un método: un banco sintético y reproducible, en Python puro, que describe cómo reaccionan varios métodos **candidatos** sobre series `d_t` (uniforme − estrategia, positivo a favor de la estrategia) con `n = 100`, en escenarios cuya dependencia se conoce.

Lo que AE-54 no hace:
- **No elige ni aprueba ningún método.**
- No cierra `regla_estadistica_de_decision`.
- No cambia el borrador de AE-52 ni aprueba la especificación de AE-53.
- No modifica el NO-GO de AE-39 ni los bloqueos de AE-41 y AE-46.

Todas las hipótesis, niveles y reglas de rechazo que siguen son **experimentales, propias del banco**. Los resultados son exploratorios: no establecen el error tipo I real, la cobertura real ni la potencia del modelo, y no autorizan un GO.

**Hechos del repositorio que motivan el banco:**
- **AE-39.** Remuestreó 18 bloques externos completos, con un bootstrap iid de bloques y un percentil bilateral del 95 %. Su prueba de signos exacta se informó, pero no entró en la decisión. Nada de eso es trasladable tal cual a 100 sorteos prospectivos.
- **AE-49.** Compara cuatro estadísticas descriptivas observadas con su distribución simulada bajo el mecanismo de sorteo uniforme, y publica p-valores empíricos exploratorios sobre datos reutilizados. No establece ni prueba la compatibilidad con el azar, ni trata pérdidas de predicción ni la calibración de una prueba prospectiva.
- **AE-50 y AE-51.** Verifican y auditan esa evidencia, sin aportar nada a la inferencia prospectiva.
- **Log Loss y Brier son reglas de puntuación estrictamente propias.** Si los sorteos son uniformes, ninguna estrategia distinta de la uniforme tiene `E[d_t] ≥ 0`. Por eso la frontera `E[d] = 0` solo se estudia con series construidas.

**Parámetros fijos del banco** (`PARAMETROS_AE54`, solo exploratorios): `n = 100`, `B = 999`, `R = 2000` en cada escenario E, `R = 500` en cada escenario L, semilla `20261001`, `ℓ = 5` y `10`, `m = 4`.
- **Semillas:** se derivan con `semilla_por_juego` de AE-49 para cada escenario, réplica, métrica y método. Todos los métodos se aplican a la misma serie.
- **Innovación:** `z = (2k + 1 − 2⁵³) / 2⁵³ · √3`, con `k = int(random() · 2⁵³)`. Tiene soporte exactamente simétrico, así que **la media cero es una propiedad del generador**; ninguna muestra se centra.

**Escenarios:**

| Id | Generador | Media cero por construcción | H0 condicional de M4 |
|---|---|---|---|
| E1 | iid, `d_t = z_t` | sí | verdadera |
| E2 | iid con colas pesadas: factor 5 con probabilidad 0,1 | sí | verdadera |
| E3 | AR(1) con φ = 0,3 (200 pasos de calentamiento) | sí | falsa |
| E4 | AR(1) con φ = 0,6 | sí | falsa |
| E5 | MA de 5 ventanas solapadas | sí | falsa |
| E6 | heterocedástico sin autocorrelación, `√(0,2 + 0,7·d²_{t−1})·z_t` | sí | verdadera |
| L1 | sorteos uniformes sintéticos (5 de 43); estrategia fija `0,9·5/43 + 0,1·q` | no: nula interior, `E[d] < 0` | falsa |
| L2 | ídem con estrategia adaptativa: frecuencias de los 20 sorteos anteriores | no: nula interior | falsa |

En L, `d_t` (Log Loss y Brier por separado) se calcula con `metricas_por_sorteo` de AE-53. Los sorteos se generan con el mismo Fisher–Yates parcial de AE-49, reimplementado: la prueba compara su salida con el original privado, que solo importa la prueba.

**Métodos candidatos** (experimentales; en los direccionales, nivel unilateral `α = 0,025`, que es la convención del criterio histórico de AE-39):
- **M1, bootstrap iid percentil.** H0: `E[d] ≤ 0` frente a `E[d] > 0`. Estadístico: `d̄`. Intervalo: estadísticos de orden `(B+1)·0,025 = 25` (extremo inferior) y `(B+1)·0,975 = 975` (extremo superior) de las `999` medias bootstrap. Rechaza si el extremo inferior es > 0. La «anchura media del intervalo» que se informa es superior − inferior.
- **M2a y M2b, bootstrap de bloques circulares** con `ℓ = 5` y `ℓ = 10`, fijados de antemano. Mismas hipótesis, intervalo y regla que M1.
- **M3a, Diebold–Mariano con la corrección HLN a un paso.** `S = √((n−1)/n)·d̄/√(γ̂₀/n)`. Rechaza si `S > t₉₉;0,975 = 1,98422`.
- **M3b, Diebold–Mariano con HAC de Newey–West** (Bartlett, `m = ⌊4(n/100)^{2/9}⌋ = 4`). `S = d̄/√(V̂/n)`. Rechaza si `S > 1,98422`; ese valor crítico es una convención de muestra pequeña, no una distribución exacta.
- **M4, Giacomini–White condicional**, con `h = (1, d_{t−1})`. H0: `E[d_t | pasado] = 0`, que **no es direccional**. Rechaza si `GW > χ²₂;0,95 = 5,99146`. Una `Ω̂` singular se registra aparte y no cuenta como rechazo.
- **Excluidas:** la prueba de signos y Wilcoxon, porque exigen independencia (Wilcoxon, además, simetría) y contrastan la mediana.

**Supuestos y límites de cada método:**
- **M1** exige `d_t` independientes o intercambiables.
- **M2** exige dependencia débil, estacionariedad y una memoria menor que `ℓ`. Con `n = 100` solo hay 20 o 10 bloques.
- **Diebold–Mariano (M3a y M3b):**
  - compara pronósticos dados; con un modelo congelado, la incertidumbre de estimación (West, 1996) no entra;
  - supone estacionariedad en covarianza;
  - la corrección HLN a un paso presupone `d_t` sin autocorrelación;
  - la varianza HAC depende del ancho de banda;
  - ninguna de las dos correcciones garantiza el tamaño nominal con `n = 100`.
- **Giacomini–White (M4):**
  - contrasta una hipótesis condicional distinta de la de M1–M3, pensada para métodos de pronóstico adaptativos;
  - supone estimadores de memoria limitada o parámetros congelados; las features de AE-36 incluyen una frecuencia acumulada, cuya compatibilidad con ese marco está por analizar;
  - depende de la función de prueba `h`;
  - usa una aproximación asintótica χ²₂;
  - no indica dirección;
  - no garantiza el tamaño con `n = 100`;
  - sus frecuencias solo se leen en E1, E2 y E6, donde su H0 es verdadera.

**Salida:** `python -m scripts.explorar_inferencia_prospectiva [--salida RUTA]`. No usa base de datos y no admite opciones de parámetros. Publica el JSON en stdout y, con `--salida`, lo guarda en un archivo nuevo sin sobrescribir, con el escritor de AE-48. Códigos de salida: `0` correcto, `1` fallo inesperado, `2` argumentos inválidos, `8` fallo al escribir, `9` ruta no permitida.

El JSON contiene:
- `esquema` `exploracion-inferencia-prospectiva/1.0`;
- `caracter: "exploratorio_sintetico"`;
- los parámetros y la definición de cada método;
- por escenario: las hipótesis verdaderas y un diagnóstico (media y desviación de `d̄`, y autocorrelación media en los retardos 1 a 5);
- por método: rechazos, frecuencia `r̂`, error Monte Carlo `√(r̂(1−r̂)/R)` y casos degenerados.

**No contiene veredictos ni tiempos.** La duración se informa en stderr. **La reproducción byte a byte solo se espera en el mismo entorno de ejecución** (misma versión de Python y misma plataforma); no se promete igualdad entre plataformas ni entre versiones.

**Archivos**: son nuevos `app/application/simulaciones/exploracion_inferencia_prospectiva.py` (puro: sin numpy, scipy, base de datos ni reloj), `scripts/explorar_inferencia_prospectiva.py` y sus dos archivos de pruebas. No cambia ningún archivo de AE-39 a AE-53.

**Pruebas**: `55` nuevas, sintéticas y deterministas. Verifican la aritmética y la reproducibilidad, **no la validez estadística**; ninguna afirma tasas de rechazo, tamaño, cobertura ni potencia.
- **Métodos:** autocovarianzas, Diebold–Mariano con HLN y con HAC, y Giacomini–White, comparados con cálculos exactos en `Fraction`; casos degenerados y singulares; estadísticos de orden; índices de bloques circulares; valores críticos frente a `scipy.stats`.
- **Generadores:** simetría exacta del soporte de `z`; E1–E6 son los filtros declarados; igualdad del Fisher–Yates con el de AE-49; la estrategia de L2 solo usa sorteos previos; las series L coinciden con `metricas_por_sorteo`.
- **Reproducibilidad:** misma salida en el mismo entorno y sensibilidad a la semilla.
- **Reporte:** estructura e hipótesis por escenario, sin veredictos.
- **Estructura:** módulo puro, sin exposición web.
- **CLI:** bytes de stdout iguales a los del archivo, y los códigos `1`, `2`, `8` y `9`, con parámetros mínimos inyectados solo en las pruebas.

**Ejecución exploratoria única, sandbox Linux de Claude** (Python `3.11.15`; resultado **exploratorio sintético**, no evidencia sobre el modelo real): `python -m scripts.explorar_inferencia_prospectiva --salida …` terminó con código `0` en `662,9 s` y produjo un JSON de `22 938` bytes con SHA-256 `7d699f090e7dfdb4665e0aa048858f59d2f5ee07edcb049540a26cc5075facb0`, idéntico byte a byte a su stdout. Ese SHA-256 solo es reproducible en el mismo entorno de ejecución. Frecuencias de rechazo `r̂ ± error Monte Carlo` (`R = 2000` en E, `R = 500` en L) y autocorrelación media de retardo 1 de `d_t`:

| Escenario | ACF₁ media | M1 | M2a (ℓ=5) | M2b (ℓ=10) | M3a | M3b | M4 |
|---|---:|---:|---:|---:|---:|---:|---:|
| E1 | `-0.012` | `0.0260 ± 0.0036` | `0.0320 ± 0.0039` | `0.0375 ± 0.0042` | `0.0245 ± 0.0035` | `0.0315 ± 0.0039` | `0.0460 ± 0.0047` |
| E2 | `-0.010` | `0.0335 ± 0.0040` | `0.0365 ± 0.0042` | `0.0445 ± 0.0046` | `0.0265 ± 0.0036` | `0.0335 ± 0.0040` | `0.0435 ± 0.0046` |
| E3 | `+0.276` | `0.0730 ± 0.0058` | `0.0410 ± 0.0044` | `0.0430 ± 0.0045` | `0.0700 ± 0.0057` | `0.0385 ± 0.0043` | `0.7335 ± 0.0099` |
| E4 | `+0.564` | `0.1645 ± 0.0083` | `0.0690 ± 0.0057` | `0.0605 ± 0.0053` | `0.1555 ± 0.0081` | `0.0670 ± 0.0056` | `1.0000 ± 0.0000` |
| E5 | `+0.773` | `0.1900 ± 0.0088` | `0.0545 ± 0.0051` | `0.0445 ± 0.0046` | `0.1860 ± 0.0087` | `0.0550 ± 0.0051` | `1.0000 ± 0.0000` |
| E6 | `-0.007` | `0.0280 ± 0.0037` | `0.0335 ± 0.0040` | `0.0385 ± 0.0043` | `0.0250 ± 0.0035` | `0.0275 ± 0.0037` | `0.0400 ± 0.0044` |
| L1 LL | `-0.009` | `0.0000 ± 0.0000` | `0.0040 ± 0.0028` | `0.0060 ± 0.0035` | `0.0020 ± 0.0020` | `0.0060 ± 0.0035` | `0.0940 ± 0.0131` |
| L1 Brier | `-0.008` | `0.0000 ± 0.0000` | `0.0060 ± 0.0035` | `0.0060 ± 0.0035` | `0.0000 ± 0.0000` | `0.0060 ± 0.0035` | `0.0960 ± 0.0132` |
| L2 LL | `-0.011` | `0.0000 ± 0.0000` | `0.0000 ± 0.0000` | `0.0040 ± 0.0028` | `0.0000 ± 0.0000` | `0.0000 ± 0.0000` | `0.0900 ± 0.0128` |
| L2 Brier | `-0.011` | `0.0000 ± 0.0000` | `0.0000 ± 0.0000` | `0.0040 ± 0.0028` | `0.0000 ± 0.0000` | `0.0000 ± 0.0000` | `0.0980 ± 0.0133` |

Lectura descriptiva, sin elegir método. En E1, E2 y E6 (media cero, sin autocorrelación) las frecuencias de M1–M3 quedaron entre `0,0245` y `0,0445`. En E3–E5 (autocorrelación positiva conocida), M1 y M3a rechazaron entre `0,070` y `0,190`, mientras que M2a, M2b y M3b quedaron entre `0,0385` y `0,069`; ninguna variante reprodujo exactamente `0,025` en todos los escenarios. M4 contrasta otra hipótesis: en E1, E2 y E6, donde su H0 es verdadera, rechazó `0,040`–`0,046`; en E3–E5 su H0 es falsa y rechazó `0,73`–`1,00`, lo cual no es un tamaño. En L1 y L2 la nula es interior (`E[d] < 0`, media de `d̄` negativa en las cuatro series) y la estrategia adaptativa de L2, con contracción `0,1` y ventana `20`, no produjo autocorrelación apreciable en `d_t` (ACF₁ ≈ `−0,01`); esto describe solo esta configuración sintética y no indica cómo se comportaría la estrategia de AE-36. Estas cifras dependen de los escenarios, parámetros y `n = 100` fijados de antemano; no establecen el error tipo I real, la cobertura, la potencia ni la validez de ningún método para una evaluación prospectiva.

**Mediciones de pruebas en el sandbox Linux de Claude** (Python `3.11.15`): antes de implementar, las pruebas nuevas fallaron al recolectarse (código `2`); después, `55 passed` (código `0`). Focalizadas: `529 passed` (código `0`): las nuevas, `tests/unit/simulaciones`, los scripts de AE-49 a AE-51, la especificación de AE-53, el registro de AE-52, métricas, baselines, incertidumbre, estructura de AE-43 y comparación de AE-48. Suite completa en una única corrida: `4585 + 55 = 4640 passed`, `0 skipped`, código `0`, con los cinco `DeprecationWarning` conocidos de Alembic. `pip check` y `git diff --check`: código `0`. La validación del operador en Windows/Python `3.14.6` se registra a continuación.

**Validación real del operador en Windows/Python `3.14.6` -evidencia atribuida al usuario, no ejecutada por Claude**: el operador verificó el SHA-256 del parche completo `ae54-exploracion-inferencia-prospectiva.patch` (85 799 bytes, `d7bc9b393ad6b12583ac6e2b1a600e161ef47f0206515db2a69ac37f180b2ef8`) aplicado sobre `9ecdf9821f60f9f6a23d120bcee33dba79e38848`. `git apply --check`, la aplicación, `git apply --reverse --check` y `git diff --check` fueron correctos, y los cambios locales fueron exactamente los siete archivos previstos.
- **Pruebas nuevas:** las `55` de AE-54 pasaron.
- **Focalizadas:** una selección focalizada más amplia que la del sandbox dio `579 passed` en `26,54 s`.
- **`pip check`:** `No broken requirements found`.

La exploración completa **no se repitió en Windows**.

**Separación por entorno:**
- **Sandbox Linux de Claude (Python `3.11.15`):** `529` focalizadas, la suite completa `4640 passed, 0 skipped` y la ejecución exploratoria única de `662,9 s` (JSON de `22 938` bytes, SHA-256 `7d699f09…acb0`).
- **Windows:** no se ejecutó ni la suite completa ni la exploración.

**Límites de esta validación**: «validada» describe AE-54 como **herramienta**: el banco sintético, sus generadores, sus métodos implementados, el CLI, la reproducibilidad en el mismo entorno y sus pruebas. **No** aprueba ningún método candidato (M1–M4), ninguna longitud de bloque, ancho de banda, nivel, efecto mínimo ni regla de multiplicidad. Tampoco aprueba ninguna regla prospectiva, `regla_estadistica_de_decision` ni la especificación de AE-53. Las frecuencias de la exploración siguen siendo exploratorias y sintéticas: no establecen el error tipo I real, la cobertura, la potencia ni la validez de un método, y no autorizan un GO.

Con esta evidencia, **AE-54 queda validada como banco de exploración sintética de métodos de inferencia**; la elección del método de inferencia sigue pendiente.

No se usaron datos reales, PostgreSQL, entrenamiento ni predicciones reales. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 no aprobada y los bloqueos de AE-40 a AE-53 sin cambios.

**Etapa AE-55 -auditoría de factibilidad de una regla estadística prospectiva, validada:** establece qué información y qué supuestos faltan para que una regla prospectiva con `100` sorteos consecutivos por juego sea defendible. Añade una calculadora analítica pura, `app/application/simulaciones/factibilidad_regla_prospectiva.py`, sin simulación ni datos.

Lo que AE-55 no hace:
- no elige ni aprueba una regla, un método, un nivel, un efecto mínimo ni una regla de multiplicidad;
- no cierra `regla_estadistica_de_decision` ni ninguno de los siete pendientes de AE-52;
- no aprueba la especificación candidata de AE-53;
- no modifica el NO-GO de AE-39 ni los bloqueos de AE-41 y AE-46.

En lo que sigue, **[lit]** marca los resultados tomados de la literatura verificada al final de la sección; el resto son inferencias propias para este repositorio. El JSON exploratorio de AE-54 no forma parte del repositorio y AE-55 no depende de él.

**Tres preguntas que no son equivalentes.** «Modelo congelado» significa código, configuración y parámetros fijados; las predicciones `p_t` siguen cambiando con el histórico disponible antes de cada sorteo.
- **P1, mejora media incondicional.** El objetivo es el promedio de la ventana: `μ_W = (1/100)·Σ_{t∈W} E[d_t]`, con `d_t` = pérdida uniforme − pérdida estrategia y `W` los 100 objetivos del horizonte. H1: `μ_W > 0`, direccional.
  - Tratar `μ_W` como un parámetro constante, o extenderlo fuera de la ventana, exige supuestos adicionales como la estacionariedad, que el código congelado no garantiza.
  - Diebold–Mariano contrasta igual precisión con pérdidas dadas **[lit]**.
- **P2, capacidad predictiva condicional.** H0: `E[d_t | F_{t−1}] = 0` **[lit: Giacomini–White]**. No es direccional: rechazarla no implica mejora, porque también ocurre si la estrategia es peor en algunos estados.
- **P3, evidencia contra un mecanismo uniforme.** Es una pregunta sobre el proceso de sorteo, sin estrategia. AE-49 fue una exploración de ese tipo sobre datos reutilizados.

**Relación entre P1, P2 y P3.** Log Loss y Brier son reglas de puntuación estrictamente propias **[lit: Gneiting–Raftery]**. Aplicándolo aquí (salvo el recorte `1e-6` de LL): si los sorteos son uniformes y `p_t` se fija antes del sorteo, entonces `E[d_t | F_{t−1}] ≤ 0`, con igualdad solo cuando `p_t` es la uniforme. De ahí se sigue que:
- «P1 verdadera» implica un mecanismo no uniforme, pero lo contrario no se cumple;
- con una estrategia no uniforme, H0 de P2 es falsa aunque la estrategia sea peor;
- un rechazo en P3 no demuestra que exista una estrategia útil.

**Unidad y dependencia.** La unidad es el sorteo, cada juego por separado. Las 43 filas de un mismo sorteo no son independientes.
- **Descomposición:** `d_t = g_t + ε_t`, con `g_t = E[d_t | F_{t−1}]`. Con sorteos independientes y `p_t` conocida antes del sorteo, `ε_t` es una diferencia de martingala.
- **Dependencia serial bajo P1:** depende de cómo varíe y persista `g_t`. Las features solapadas de AE-36 **pueden** inducir persistencia, pero no la garantizan. La estacionariedad y la varianza de largo plazo son **supuestos**.
- **Reentrenamiento:** si se reentrenara, habría que tratar la incertidumbre de estimación **[lit: West]**.
- **Supuestos de cada método de AE-54:**
  - M1: independencia;
  - M2: estacionariedad, dependencia débil y memoria menor que `ℓ` **[lit: Künsch; Politis–Romano]**;
  - M3a: sin autocorrelación **[lit: Harvey–Leybourne–Newbold]**;
  - M3b: estacionariedad en covarianza y ancho de banda **[lit: Newey–West]**;
  - M4: función de prueba, memoria limitada o parámetros congelados, y aproximación asintótica **[lit: Giacomini–White]**.

  Diagnosticar esos supuestos con los mismos 100 sorteos evaluados sería elegir el método a posteriori.

**Qué aporta AE-54 y qué no.** Sus escenarios muestran el comportamiento de los métodos con `n = 100` y una dependencia **construida**: con autocorrelación positiva, M1 y M3a rechazaron por encima de `0,025`, y M2 y M3b se quedaron más cerca sin reproducirlo en todos los escenarios. No informan del proceso real de `d_t`, de la estrategia de AE-36, del tamaño, de la cobertura ni de la potencia reales, ni de P3. **No se elige el método con la tasa observada más baja**: sería una selección a posteriori, y una tasa baja puede reflejar un método conservador.

**Efecto mínimo detectable, en unidades de σ** (aproximación normal; σ es la desviación típica marginal de `d_t` y `κ` el cociente entre la varianza de largo plazo y σ², que es un supuesto). La fórmula es `EMD/σ ≈ (z_{1−α} + z_{potencia})·√(κ/n)`. Con `n = 100` y `α = 0,025` unilateral por métrica (la convención histórica de AE-39, no aprobada para uso prospectivo):

| Potencia | `κ = 1` (sin dependencia) | `κ ≈ 1,857` (AR(1) con ρ = 0,3) | `κ = 4` (AR(1) con ρ = 0,6) |
|---|---:|---:|---:|
| `0,8` | `0,2802` | `0,3818` | `0,5603` |
| `0,9` | `0,3242` | `0,4417` | `0,6483` |

`κ = (1+ρ)/(1−ρ)` solo vale si `d_t` fuera un AR(1) estacionario; es una aproximación bajo ese supuesto. La función `efecto_minimo_detectable` está definida para `n ≥ 2`, `0 < α < 0,5`, `α < potencia < 1` y `κ > 0`; en ese dominio el EMD es positivo. Rechaza una potencia igual o inferior a `α`, porque esa potencia ya la alcanza un efecto nulo o negativo. σ, κ y el efecto real son desconocidos. El efecto mínimo de interés, en unidades del problema, debe fijarlo el operador antes de ver datos, y AE-55 no lo traduce a un valor.

**Métricas principales y multiplicidad:**
- Exigir LL **y** Brier es un contraste de intersección-unión **[lit: Berger]**: la conjunción mantiene el nivel `α` de cada prueba y pierde potencia.
- Si solo se afirma algo por juego, cada juego se informa por separado. Si se quiere afirmar algo conjunto («en al menos un juego»), la probabilidad de error conjunta puede llegar a unos `2α`, y haría falta una corrección como la de Holm **[lit]**. Es una decisión abierta.

**Secundaria Precision@5 = Recall@5** (una sola condición; cálculo exacto bajo sorteos uniformes):
- **Aciertos del top-5:** siguen una hipergeométrica con `N = 43`, `K = 5` y `n = 5`, con probabilidades de 0 a 5 aciertos `11951/22919`, `17575/45838`, `14060/160433`, `3515/481299`, `95/481299` y `1/962598`.
- **Medias:** `E[aciertos] = 25/43` y **`E[P@5] = 5/43`**; la varianza de aciertos es `18050/38829`.
- **Diferencia pareada por sorteo.** La P@5 de la estrategia se compara con la de la uniforme de AE-53 (el boleto `1..5`). Su varianza depende del solape `j` entre los dos top-5:
  - en aciertos, `(5−j)·190/903`;
  - en P@5, `(5−j)·38/4515`, es decir, `38/903 ≈ 0,0421` sin solape, `0,0337`, `0,0253`, `0,0168`, `0,0084`, y `0` con solape total.

  Con solape total, los dos top son idénticos y la función devuelve `0` exacto sin evaluar la covarianza, que no está definida con un rango de 1 número.

  El solape puede cambiar de un sorteo a otro. La tabla describe esta variación **sin juzgar la tolerancia histórica de `0,02`**.

**Horizonte, omisiones, anterioridad, procedencia y sellado.** El horizonte de 100 y el efecto de las omisiones siguen siendo propuestas no aprobadas de AE-53. Qué garantiza cada mecanismo, y con qué condiciones:

| Mecanismo | Qué garantiza | Qué no garantiza, o qué falta |
|---|---|---|
| Cadena de hashes de AE-52 | Integridad y orden relativo **si la cabeza se ancla externamente** | Sin anclaje, el registro completo puede recrearse; no da fecha |
| `huella_codigo` (AE-52) | Identifica el contenido de los archivos de la estrategia | No cubre dependencias, plataforma, datos ni tramo de entrenamiento, ni el modelo resultante |
| `huella_entrada` (AE-52) | Identifica el histórico usado como entrada | No prueba que fuera el disponible antes del sorteo |
| Recomputación determinista | Una salida igual es consistente con ese código y esas entradas, en ese entorno | Exige un contrato de inferencia prospectiva, que **no existe**, más datos y tramo de entrenamiento con huella, semilla y entorno fijados; la coma flotante puede variar entre plataformas; no da fecha |
| Commit firmado y enviado | Autoría de la clave firmante | La fecha la fija el autor; **no es un sello temporal suficiente** |
| Sello RFC 3161 | Una autoridad de sellado atesta que el hash existía en el instante `T` | Depende de la confianza en la autoridad y su certificado; hay que conservar el token |

Para acreditar la anterioridad y la procedencia de cada predicción faltan:
- el contrato de inferencia;
- un manifiesto con las huellas de código, entorno, datos de entrenamiento, configuración, entrada y salida;
- un sello externo del manifiesto o de la cabeza antes de la hora oficial del sorteo, conservado y verificable;
- el registro de esa hora oficial.

**Factibilidad frente a autorización.** La factibilidad responde a «¿puede diseñarse una regla defendible e informativa?». La **autorización operativa** depende de AE-41 (al menos 100 sorteos nuevos más validación humana), del NO-GO de AE-39 y de AE-46, y AE-55 no la cambia.
- **Continuar hacia un preregistro** si el operador:
  - fija la pregunta;
  - acepta explícitamente los supuestos de un método;
  - fija un efecto mínimo de interés y juzga aceptable el EMD para valores plausibles de `κ`;
  - elige el sellado y los requisitos anteriores.
- **Rediseñar** si el EMD resulta inaceptable (ampliar el horizonte, nunca reducirlo, o cambiar la pregunta o las métricas) o si los supuestos no son defendibles.
- **Mantener el bloqueo** en cualquier caso hasta que AE-41 y la validación humana lo permitan.

**Decisiones abiertas tras AE-55:**
- la pregunta (P1, P2 o P3);
- el método, con `ℓ` o ancho de banda;
- `α` y dirección;
- el efecto mínimo de interés y la potencia objetivo;
- los supuestos sobre `κ` y la estacionariedad;
- la multiplicidad entre juegos;
- el papel y la tolerancia de la secundaria;
- el horizonte y las omisiones;
- el sellado y su manifiesto;
- el tramo de entrenamiento y el contrato de inferencia;
- `regla_estadistica_de_decision`;
- la autorización de AE-41 y la validación humana.

**Literatura verificada.** Claude comprobó el título, la revista, el volumen y las páginas en fuentes bibliográficas públicas. Se omitieron las fuentes que no pudo verificar.
- Diebold, F. X. y Mariano, R. S. (1995). «Comparing Predictive Accuracy». *Journal of Business & Economic Statistics*, 13(3), 253–263.
- Harvey, D., Leybourne, S. y Newbold, P. (1997). «Testing the equality of prediction mean squared errors». *International Journal of Forecasting*, 13(2), 281–291.
- Giacomini, R. y White, H. (2006). «Tests of Conditional Predictive Ability». *Econometrica*, 74(6), 1545–1578.
- West, K. D. (1996). «Asymptotic Inference about Predictive Ability». *Econometrica*, 64(5), 1067–1084.
- Newey, W. K. y West, K. D. (1987). «A Simple, Positive Semi-Definite, Heteroskedasticity and Autocorrelation Consistent Covariance Matrix». *Econometrica*, 55(3), 703–708.
- Künsch, H. R. (1989). «The Jackknife and the Bootstrap for General Stationary Observations». *The Annals of Statistics*, 17(3), 1217–1241.
- Politis, D. N. y Romano, J. P. (1994). «The Stationary Bootstrap». *Journal of the American Statistical Association*, 89(428), 1303–1313.
- Gneiting, T. y Raftery, A. E. (2007). «Strictly Proper Scoring Rules, Prediction, and Estimation». *Journal of the American Statistical Association*, 102(477), 359–378.
- Berger, R. L. (1982). «Multiparameter hypothesis testing and acceptance sampling». *Technometrics*, 24, 295–300.
- Holm, S. (1979). «A Simple Sequentially Rejective Multiple Test Procedure». *Scandinavian Journal of Statistics*, 6(2), 65–70.
- Adams, C., Cain, P., Pinkas, D. y Zuccherato, R. (2001). RFC 3161, «Internet X.509 Public Key Infrastructure Time-Stamp Protocol (TSP)». IETF.

**Archivos**: son nuevos `app/application/simulaciones/factibilidad_regla_prospectiva.py` (puro: solo `math`, `fractions` y `statistics`; sin simulación, base de datos, reloj ni azar) y `tests/unit/simulaciones/test_factibilidad_regla_prospectiva.py`. No cambia ningún archivo de AE-39 a AE-54, y no hay CLI ni rutas.

**Pruebas** (`49` nuevas, deterministas; verifican cálculos bajo supuestos declarados, no la validez de ninguna regla):
- la hipergeométrica, comprobada por enumeración exhaustiva de todos los sorteos en rangos pequeños, y la forma exacta para 43/5;
- la varianza de la diferencia pareada, comprobada por enumeración exhaustiva para cada solape y con la forma cerrada `(5−j)·190/903`;
- los cuantiles frente a `scipy.stats`, el EMD de referencia, su monotonía y que la potencia en el EMD sea la objetivo;
- la inflación AR(1) frente a la suma de autocorrelaciones;
- casos límite: el solape total da `0` exacto, incluido el rango unitario `(1, 1, 1)`; una potencia no mayor que `α` se rechaza; el EMD es positivo en todo el dominio;
- el rechazo de entradas inválidas;
- una tabla determinista y sin veredictos;
- un módulo puro, sin exposición web ni en scripts.

**Mediciones en el sandbox Linux de Claude** (Python `3.11.15`, sin datos reales): antes de crear el módulo, las pruebas nuevas fallaron al recolectarse (código de pytest `2`); después, `49 passed` (código `0`). Focalizadas: `404 passed` (código `0`): nuevas, `tests/unit/simulaciones`, CLI de AE-54, especificación de AE-53, registro de AE-52, métricas, baselines, incertidumbre, estructura de AE-43 y diagnóstico. Suite completa en una única corrida sobre el código final: `4640 + 49 = 4689 passed`, `0 skipped`, código `0`, con los cinco `DeprecationWarning` conocidos de Alembic. `pip check` y `git diff --check`: código `0`. La validación del operador en Windows/Python `3.14.6` se registra a continuación.

**Historia de la corrección (v1 → v2)**: la auditoría del operador del primer parche (`ae55-factibilidad-regla-prospectiva.patch`, 60 765 bytes, SHA-256 `445653a2707126a97d54e3c11d120f321fac51864d83e6539790209d73460d01`) detectó dos casos límite:
- `varianza_diferencia_aciertos(1, 1, 1)` dividía entre cero;
- `efecto_minimo_detectable` devolvía un EMD negativo o nulo cuando la potencia no superaba `α`.

Sobre v1, las 6 pruebas de regresión fallaron (`6 failed, 43 passed`, código `1`). La tabla 43/5 no cambia: su JSON es idéntico al de v1.

**Validación real del operador en Windows/Python `3.14.6` y pytest `9.1.1` -evidencia atribuida al usuario, no ejecutada por Claude**: rama `feature/ae55-factibilidad-regla-prospectiva`, con HEAD base `80d4ef2634d4ecb06171dd59057bbd394b017246`.
- **Parche aplicado:** el parche completo v2 `ae55-factibilidad-regla-prospectiva-v2.patch`, con SHA-256 verificado `924dddc3d4a6a43ee4af3e9e4f408f41ac4cfc672fa5377a7646b88f396c6376`.
- **Comprobaciones:** `git apply --check`, la aplicación, `git apply --reverse --check` y `git diff --check` fueron correctos.
- **Archivos:** exactamente cinco (el módulo y la prueba nuevos, README, ROADMAP y ARCHITECTURE).
- **Pruebas nuevas:** `49 passed` en `9,53 s`, código `0`.
- **Focalizadas:** `404 passed` en `16,20 s`, código `0`.
- **`pip check`:** `No broken requirements found`, código `0`.

**En Windows no se ejecutó la suite completa.** La cifra `4689 passed, 0 skipped` sobre v2 corresponde únicamente al sandbox Linux de Claude (Python `3.11.15`).

**Límites de esta validación**: «validada» se refiere a la **calculadora analítica** de AE-55 y a sus pruebas: el EMD en unidades de σ con su dominio, la inflación AR(1) como aproximación, la hipergeométrica exacta, la varianza pareada según el solape y la tabla fija. No aprueba `α`, potencia, efecto mínimo, supuestos sobre `κ`, método inferencial, regla de multiplicidad ni ninguna regla prospectiva. Tampoco cierra `regla_estadistica_de_decision`.

Siguen igual:
- los siete pendientes de AE-52, abiertos;
- la especificación candidata de AE-53, sin aprobar;
- el NO-GO de AE-39 y los bloqueos de AE-41 y AE-46.

Con esta evidencia, **AE-55 queda validada como calculadora analítica de factibilidad**; la factibilidad no equivale a autorización operativa.

No se usaron datos reales, PostgreSQL, entrenamiento ni predicciones reales. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-54 sin cambios.

**Etapa AE-56 -contrato de coherencia del diseño de una regla prospectiva, validada:** es un contrato preparatorio, **sin inferencia**, en `app/application/ml/diseno_regla_prospectiva.py`. Tiene dos piezas:
- un catálogo de las dimensiones de diseño de la futura regla;
- un validador que comprueba **solo la consistencia de los campos que declara** una especificación candidata.

AE-56 no elige ni aprueba ninguna pregunta, método, parámetro, nivel, horizonte ni mecanismo. No verifica supuestos, procedencia, sellado, token, manifiesto, hora oficial, custodia, anterioridad, autorización ni validez inferencial. No cierra `regla_estadistica_de_decision` ni ninguno de los siete pendientes de AE-52, y no modifica el NO-GO de AE-39 ni los bloqueos de AE-41 y AE-46.

**Por qué es preparatorio.** Con lo disponible no es defendible implementar una prueba ni fijar la regla:
- los supuestos de dependencia de `d_t` no son verificables antes de tener datos;
- no existe contrato de inferencia prospectiva;
- la cadena de procedencia está incompleta, porque no hay manifiesto ni sello externo;
- α, el efecto mínimo y la multiplicidad son decisiones humanas.

El manifiesto de procedencia queda como candidato para una etapa posterior. Un contraste formal queda descartado por ahora.

**Catálogo `DIMENSIONES_AE56`.** Es profundamente inmutable: `Dimension` es una `dataclass(frozen=True)` que solo contiene textos y tuplas ordenadas.

Cada dimensión puede pertenecer a **varias** categorías:
- `justificable_antes_de_datos`;
- `pendiente_bloqueado`;
- `requiere_decision_humana_o_mecanismo_externo`;
- `supuesto_no_verificable`.

Además, cada dimensión lleva:
- su base: `lit:<referencia>` para la literatura verificada en AE-55, o `inferencia_propia`;
- sus fuentes: los pendientes de AE-52 y AE-53 y las decisiones de AE-55. Todos los pendientes de AE-52 y AE-53 quedan cubiertos;
- sus dependencias, sin ciclos.

Las dimensiones son: pregunta, dirección y nivel, familia de método, parámetros, supuestos, métricas principales, secundaria, multiplicidad entre juegos, horizonte, omisiones, efecto mínimo y potencia, sellado, hora oficial, modelo congelado y autorización.

`huella_diseno()` es el SHA-256 de la serialización canónica del catálogo. Identifica el catálogo, pero no prueba cuándo se fijó.

**Especificación candidata y reglas.** Cada regla comprueba solo la forma y la consistencia de lo declarado.
- **R1, pregunta:** `P1`, `P2` o `P3`. P3 es incoherente con el registro de AE-52, porque trata del mecanismo de sorteo y no evalúa estrategias.
- **R2, nivel y dirección según la pregunta:**
  - P1: `nivel_unilateral` en (0, 0,5) y `direccion = "mejora"`;
  - P2: `nivel_contraste` en (0, 1) y `direccion = "no_direccional"`;
  - usar el campo de nivel de la otra pregunta es incoherente.
- **R3, familia de método:** se declara una familia descriptiva, no una variante del banco:
  - `remuestreo_iid_media`;
  - `remuestreo_bloques_media`;
  - `t_media_sin_autocorrelacion`;
  - `t_media_varianza_hac`;
  - `contraste_condicional`.

  P1 solo admite familias de media, y P2 solo `contraste_condicional`. Esta compatibilidad se deriva de las hipótesis de Diebold–Mariano y Giacomini–White **[lit]**. Las variantes M1–M4 de AE-54 son exploratorias y **no** forman un catálogo de métodos autorizados: el campo `referencia_banco_ae54` solo las anota y nunca decide.
- **R4, parámetros:** se valida solo su presencia, tipo y rango, **nunca su adecuación**:
  - remuestreo: `replicas` es un entero ≥ 1 y `semilla` un entero;
  - bloques: además, `variante` es un texto y `longitud_bloque` un entero ≥ 1;
  - HAC: `kernel` es un texto y `ancho_banda` un entero ≥ 0;
  - contraste condicional: `funcion_prueba` es una lista no vacía de nombres de instrumentos distintos. No es un entero, y su pertinencia no se juzga.
- **R5, supuestos:** `supuestos_declarados` debe incluir los que exige la familia según AE-55. Declararlos **no los verifica**.
- **R6, métricas principales:** exactamente LL y Brier en conjunción, como fija AE-52. Es un contraste de intersección-unión **[lit: Berger]**.
- **R7, secundaria:** una sola condición `precision_en_5`, porque P@5 = R@5 en cada sorteo, con un papel declarado. La identidad se cumple porque los juegos autorizados extraen 5 números y el top es de 5 (precisión de AE-57).
- **R8, multiplicidad:** si se declara una afirmación conjunta entre juegos, hace falta `holm` o `bonferroni` **[lit: Holm]**.
- **R9, horizonte.** Distingue tres casos:
  - **mínimo de AE-52:** al menos 100 objetivos, sin reducción retroactiva. Es una condición **necesaria, no suficiente**, del mínimo de 100 resultados **resueltos** (precisión de AE-58);
  - **propuesta de AE-53:** 100 objetivos con un solo análisis se informa en `coincide_con_propuesta_ae53`, sin aprobarla. Es una **coincidencia parcial**: no se comprueba desde qué objetivo empieza la ventana ni cuándo se analiza (aclaración de AE-57);
  - **cualquier otra ventana:** se informa como alternativa sin aprobar. Con **más de un análisis** exige además una decisión sobre análisis repetidos y control del error (`analisis_repetidos_y_control_de_error`), y mientras no se tome el diseño queda incompleto. Nunca se trata con el nivel de un único análisis.
- **R10, efecto mínimo y potencia:**
  - el efecto es > 0, con unidad `sigma` o `unidad_de_metrica`;
  - `calculado_con = "emd_ae55"` solo es coherente con P1 y una familia de media, y exige `nivel < potencia_objetivo < 1`, que es el **dominio de esa función de AE-55**, no una regla universal. Con P2 es incoherente;
  - `potencia_objetivo`, si se declara, está en (0, 1).
- **R11 y R12, sellado y hora oficial:** son textos declarados. Un commit firmado como único mecanismo es incoherente. No existe ninguna lista de mecanismos aprobados, y **nada de esto verifica** el sello, el token, el manifiesto, la hora oficial, la custodia ni la anterioridad.

**Semántica de estados** (`validar_especificacion_diseno` devuelve un `InformeDiseno` inmutable):
- **`incompleta`:** falta un campo requerido, vale `None` o queda una decisión adicional requerida. Por ejemplo, que falte `longitud_bloque`, `supuestos_declarados`, la fuente de hora, `efecto_minimo.unidad` o la `correccion` de una afirmación conjunta.
- **`incoherente`:** un campo **presente** tiene tipo, valor o combinación contradictorios. Incluye un `bool` donde se espera un número, `NaN` o infinito, una unidad o corrección no admitidas, y una lista de supuestos que omite uno exigido. Tiene prioridad sobre `incompleta`.
- **`coherente_no_aprobada`:** los campos declarados son consistentes entre sí, **y nada más**.

El informe incluye las violaciones, las decisiones sin tomar, las decisiones adicionales, la coincidencia con la propuesta de AE-53, las alternativas sin aprobar y la lista fija de lo que no verifica. También incluye `bloqueos_de_la_base_documentada`: el NO-GO de AE-39, AE-41 y AE-46 según la base documentada, sin consultar sus módulos, y los siete pendientes de AE-52 tal cual.

**Canonicidad de la candidata:**
- Solo se admiten objetos con claves textuales, listas, textos, enteros, reales, booleanos y `None`. Un `set`, bytes, otros objetos o claves no textuales se rechazan con `DisenoReglaInvalidoError`.
- La huella de la candidata es el SHA-256 de su JSON canónico y no depende del orden de las claves.
- Con valores que impiden la huella, el informe es `incoherente` y `huella = None`: no se serializa ese valor ni se inventa una huella. Impiden la huella `NaN`, los infinitos y los enteros que superan el límite de AE-57, que es de **más de 640 dígitos decimales** con cualquier configuración de CPython. En v2 el umbral era de más de 4300 dígitos, y no «4300 o más», como decía esta sección por error; AE-57 lo sustituye.
- Un entero es siempre finito. No se pasa por `math.isfinite`, que desborda con enteros enormes: `10**400` es un real válido y se compara exactamente con los rangos.
- Un valor **presente con tipo inválido** da siempre `incoherente` y nunca lanza `TypeError` ni `OverflowError`. Es el caso de una lista, un objeto o un número donde se espera un texto de un conjunto cerrado, o de elementos no textuales en las métricas. Las pertenencias a conjuntos cerrados solo se evalúan sobre textos, y las métricas solo se ordenan si todas son textos.
- Un anidamiento mayor que `PROFUNDIDAD_MAXIMA_CANDIDATA = 32` (la raíz es 0) se rechaza con `DisenoReglaInvalidoError`, en lugar de agotar la recursión.

**Límites**:
- La coherencia no es aprobación ni verificación de supuestos, procedencia, autorización o validez inferencial.
- El validador no juzga si una familia o sus parámetros son apropiados para el proceso real.
- Las frecuencias sintéticas de AE-54 y la factibilidad de AE-55 no intervienen en ninguna regla.
- La huella no es un sello temporal.

**Archivos**: son nuevos `app/application/ml/diseno_regla_prospectiva.py`, puro (solo biblioteca estándar y lectura de las constantes de AE-52 y AE-53), y `tests/unit/ml/test_diseno_regla_prospectiva.py`. No cambia ningún archivo de AE-39 a AE-55, y no hay CLI, rutas ni scripts.

**Pruebas** (`125` nuevas, sintéticas y deterministas): verifican la consistencia de los campos, no la validez estadística.
- **Catálogo:**
  - categorías ordenadas y múltiples;
  - inmutabilidad profunda;
  - dependencias sin ciclos;
  - cobertura de los pendientes de AE-52 y AE-53;
  - huella estable y sensible a cambios.
- **Canonicidad:**
  - rechazo de tipos no canónicos;
  - `bool` en campos numéricos tratado como incoherente; al ser serializable, el informe conserva su huella;
  - `NaN`, infinito y enteros por encima del límite (más de 4300 dígitos en v2; más de 640 desde AE-57) tratados como incoherentes, con `huella = None`;
  - regresiones v2: los cinco casos de la auditoría de v1, enteros enormes finitos, enteros por encima del límite y anidamiento excesivo;
  - barrido que sustituye cada campo de cuatro candidatas completas, y cada campo raíz, por 17 valores canónicos de tipo inesperado, sin excepción.
- **Ausencia frente a contradicción:** cada caso de ausencia da `incompleta`; cada contradicción da `incoherente`, con prioridad cuando conviven.
- **Reglas:** un caso incoherente por regla, de R1 a R12.
- **Distinciones:**
  - propuesta de AE-53 frente a alternativa sin aprobar, y dos análisis como decisión adicional;
  - la referencia a AE-54 no decide;
  - el EMD solo con P1 y familias de media;
  - el sellado declarado sigue sin verificarse.
- **Invariantes:**
  - estados cerrados, sin estado aprobado;
  - informe inmutable;
  - AE-52 y AE-53 intactos tras validar.
- **Estructura:** módulo aislado, sin exposición web ni en scripts.

**Historia de la corrección (v1 → v2).** El operador auditó el parche v1 (`ae56-diseno-regla-prospectiva.patch`, 81 154 bytes, SHA-256 `9a84b19aa3081d75b2eaa52f5937fca85ed92ec033755055180112300afa482c`) antes de aplicarlo en Windows. Reprodujo cinco excepciones con entradas canónicas:
- `TypeError` al ordenar métricas principales con un elemento no textual;
- `TypeError` por un valor no hashable en `referencia_banco_ae54`;
- lo mismo en `multiplicidad.correccion`;
- lo mismo en `efecto_minimo.unidad`;
- `OverflowError` de `math.isfinite` con `nivel_unilateral = 10**400`.

Al revisar las operaciones similares aparecieron dos fallos más de la misma clase: un entero de más de 4300 dígitos producía `ValueError` al calcular la huella, y un anidamiento profundo producía `RecursionError`. Las regresiones se escribieron antes de corregir. Sobre el código v1 dieron `17 failed, 108 passed` (código de pytest `1`). v2 no cambia el alcance estadístico, las reglas R1–R12, los estados ni los bloqueos.

**Mediciones en el sandbox Linux de Claude** (Python `3.11.15`, sin datos reales):
- **v1:** antes de crear el módulo, las pruebas nuevas fallaron al recolectarse (código de pytest `2`).
- **v2, sobre el código final:** `125 passed` (código `0`). Además, un barrido aleatorio ad hoc, que no forma parte de la suite, con unas 37 000 candidatas mutadas no produjo ninguna excepción.
- **Focalizadas:** `569 passed` (código `0`): nuevas, registro de AE-52 y su CLI, especificación de AE-53, `tests/unit/simulaciones` (AE-49, AE-54 y AE-55), CLI de AE-54, métricas, baselines, incertidumbre, estructura de AE-43 y diagnóstico. Suite completa en una única corrida: `4689 + 125 = 4814 passed`, `0 skipped`, código `0`, con los cinco `DeprecationWarning` conocidos de Alembic. `pip check` y `git diff --check`: código `0`.

**Validación real del operador en Windows/Python `3.14.6` y pytest `9.1.1` -evidencia atribuida al usuario, no ejecutada por Claude**: rama `feature/ae56-diseno-regla-prospectiva`, con HEAD base `ec3b5d69ecc089f7bdf94dc7e65327b74824ed09`.
- **Parche aplicado:** el parche completo v2 `ae56-diseno-regla-prospectiva-v2.patch`, con SHA-256 verificado `bc9b4b78a9df780b31052eeaf86c11f4f9cfe24de6cb713d45fd7529e1a0b7c9`.
- **Comprobaciones:** `git apply --check`, la aplicación, `git apply --reverse --check` y `git diff --check` fueron correctos.
- **Archivos:** exactamente cinco (el módulo y la prueba nuevos, README, ROADMAP y ARCHITECTURE).
- **Pruebas nuevas:** `125 passed` en `0,88 s`.
- **Focalizadas:** `569 passed` en `20,91 s`.
- **`pip check`:** sin problemas.

**En Windows no se ejecutó la suite completa.** La cifra `4814 passed, 0 skipped` sobre v2 corresponde únicamente al sandbox Linux de Claude (Python `3.11.15`).

**Límites de esta validación**: «validada» se refiere únicamente al **contrato preparatorio**, al **validador de coherencia** y a sus pruebas: el catálogo `DIMENSIONES_AE56`, las reglas R1–R12, la semántica de estados, la canonicidad y la huella. No aprueba ninguna pregunta, familia de método, parámetro, nivel, horizonte, efecto mínimo, mecanismo de sellado ni fuente de hora. Tampoco aprueba ninguna regla prospectiva, inferencia ni autorización. `coherente_no_aprobada` sigue significando solo consistencia de los campos declarados, y no se cierra `regla_estadistica_de_decision`.

Siguen igual:
- los siete pendientes de AE-52, abiertos;
- la especificación candidata de AE-53, sin aprobar;
- el NO-GO de AE-39 y los bloqueos de AE-41 y AE-46.

Con esta evidencia, **AE-56 queda validada como contrato preparatorio de coherencia del diseño**; la coherencia no equivale a aprobación ni a autorización operativa.

No se usaron datos reales, PostgreSQL, entrenamiento ni predicciones reales. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-55 sin cambios.

**Etapa AE-57 -auditoría del diseño prospectivo (AE-52 a AE-56), validada:** audita el estado real de AE-52 a AE-56, con especial atención al catálogo y al validador de AE-56 frente a sus pruebas y su documentación. Corrige solo los **defectos verificables**, cada uno reproducido primero con un caso mínimo. Clasifica el resto de hallazgos sin resolverlos. **No aprueba** ninguna pregunta, método, nivel, potencia, efecto, horizonte, tratamiento de omisiones ni regla prospectiva. No cambia el catálogo `DIMENSIONES_AE56` ni su huella, `huella_diseno() = 6743293d4e247c17ed5f9c098824caf4f740873f00a04d4e223f334874f8de3c`.

**Clase 1: defectos verificables, corregidos o aclarados en AE-57.** Cada caso se reprodujo sobre la base `0bdaf0bc`.
- **D1:** con `supuestos_declarados = 5` y sin `metodo`, el estado era `incompleta`, porque la regla retornaba antes de validar el tipo. **Ahora es `incoherente`.**
- **D2:** con `metodo = {"parametros": 5}` y sin familia, el estado era `incompleta`. **Ahora un `parametros` presente que no es un objeto es `incoherente`.** Sin una familia válida siguen sin juzgarse los valores de los parámetros.
- **D3:** sin pregunta, con `nivel_unilateral = -1`, el estado era `incompleta`: solo se comprobaba el tipo, mientras que `potencia_objetivo` sí tenía rango sin contexto. **Ahora, sin una pregunta válida, cada nivel presente se compara con el rango de su propio campo:** `nivel_unilateral` en (0, 0,5) y `nivel_contraste` en (0, 1). Un nivel dentro de rango sin pregunta sigue en `incompleta`.
- **D4:** `calculado_con = "emd_ae55"` con `unidad = "unidad_de_metrica"` daba `coherente_no_aprobada`. Sin embargo, el EMD de AE-55 se expresa «en unidades de sigma, nunca del problema», según el docstring de `efecto_minimo_detectable`. **Ahora es `incoherente`.** Si falta la unidad, sigue en `incompleta`.
- **D5 (texto):** la documentación, el comentario, el mensaje y el docstring de la prueba de AE-56 decían «4300 dígitos o más». El umbral de v2 era en realidad **más de 4300**: un entero de 4300 dígitos conservaba la huella. Fue un error de redacción, que se corrige.
- **D6 (comportamiento):** con `python -X int_max_str_digits=640`, un entero de 1000 dígitos hacía escapar un **`ValueError`**. El umbral fijo de v2 suponía el límite por defecto de CPython. **AE-57 define un límite propio, conservador y estable:**
  - un entero de **hasta 640 dígitos decimales** se admite con huella;
  - con **más de 640**, el informe es `incoherente` y `huella = None`, **con cualquier configuración de CPython** (la de por defecto, `640` o `0`);
  - 640 es el menor límite no nulo que CPython permite configurar (`sys.int_info.str_digits_check_threshold`). Es un límite de contrato, no una imposibilidad de serializar: con la configuración por defecto muchos enteros más largos sí se serializan;
  - la constante pública es `DIGITOS_MAXIMOS_ENTERO_CANDIDATA = 640`, y el mensaje, «entero con mas de 640 digitos decimales: fuera del limite de AE-57 para calcular la huella»;
  - **cambio deliberado:** los enteros de 641 a 4300 dígitos, que v2 admitía con huella, pasan a `incoherente` con `huella = None`.
- **D7 (aclaración documental; el código no cambia):** `coincide_con_propuesta_ae53` compara solo la cantidad de objetivos (100) y el número de análisis (1). La propuesta de AE-53 tiene tres componentes: `objetivos`, `desde = "primer_objetivo_posterior_al_corte"` y `analisis = "unico_al_completar_el_horizonte"`. La candidata no puede declarar desde qué objetivo empieza la ventana ni cuándo se analiza, y hacerlo es un campo desconocido, `incoherente`. Por eso la coincidencia es **parcial**: no certifica la propuesta completa ni la aprueba. **Límite residual:** el nombre público del campo se conserva por compatibilidad, aunque sugiere más de lo que comprueba.

**Clase 2: decisiones de diseño que requieren elección humana.** AE-57 no las resuelve.
- **Omisiones:** la dimensión `omisiones` existe en el catálogo, pero la candidata no tiene campo para ella. Una candidata puede quedar `coherente_no_aprobada` sin declarar cómo trata las omisiones.
- **Objetivos frente a resueltos:** R9 compara `ventana.objetivos` con el mínimo de AE-52, que cuenta sorteos **resueltos**. Con omisiones, 100 objetivos pueden dar menos de 100 resueltos. Solo coinciden bajo la propuesta de AE-53, que no está aprobada.
- **Contradicciones sin pregunta:** sin pregunta no se detectan combinaciones como `direccion = "mejora"` con `nivel_contraste`, ni que se declaren ambos niveles.
- **R11:** compara el literal exacto `commit_firmado`, sin distinguir mayúsculas. Variantes como `"commit firmado"` pasan. Normalizar texto libre sería heurístico.
- **Huella sintáctica:** `1` y `1.0`, o un texto en NFC y en NFD, dan huellas distintas. La huella identifica la declaración JSON, no su semántica.
- **Texto del catálogo:** la propuesta de horizonte del catálogo (`primeros_100_objetivos_un_analisis`) parafrasea la de AE-53. Cambiarla alteraría `huella_diseno`.

**Clase 3: cuestiones inferenciales que necesitan justificación posterior.**
- La validez de cada familia bajo la dependencia real de `d_t`: estacionariedad, κ, longitud de bloque y ancho de banda.
- La aproximación normal del EMD y los valores de σ y del efecto.
- El nivel de error con análisis repetidos.
- El papel y la tolerancia de la secundaria.
- Si la conjunción LL y Brier es la afirmación deseada.
- La identidad P@5 = R@5, que se cumple porque los juegos autorizados (BALOTO y BALOTO_REVANCHA) extraen 5 números y el top es de 5. No se cumpliría en un juego con otra cantidad.

**Clase 4: requisitos externos de anterioridad, procedencia o autorización.**
- Sellado temporal externo, token, manifiesto, hora oficial y custodia.
- Autorización de AE-41 con validación humana, el NO-GO de AE-39 y `desbloqueable=False` de AE-46.
- Los siete pendientes de AE-52, que siguen abiertos.

**Literatura:** no se añade. Ningún defecto de la clase 1 depende de ella, y D4 se apoya solo en el docstring de AE-55.

**Archivos:**
- `app/application/ml/diseno_regla_prospectiva.py`: correcciones D1–D4 y D6, docstrings y comentario de R9.
- `tests/unit/ml/test_diseno_regla_prospectiva.py`: solo la prueba de límite de enteros, ajustada a 640 por D6. Es la única aserción de AE-56 que cambia.
- `tests/unit/ml/test_auditoria_diseno_prospectivo.py`: nuevo.
- README, ROADMAP y ARCHITECTURE: esta sección y correcciones puntuales en la de AE-56 (umbral, coincidencia parcial y condición de P@5 = R@5).

No hay CLI, rutas ni scripts, y AE-39 a AE-55 no cambian.

**Pruebas** (`66` nuevas, sintéticas y deterministas):
- **D1–D4:** casos contradictorios que dan `incoherente` y sus variantes con el campo ausente, que siguen en `incompleta`.
- **Límite exacto:** 640 dígitos (y su negativo) conservan la huella; 641, 4300, 4301 y 5001 dígitos dan `incoherente` con `huella = None` y el mensaje exacto.
- **Independencia de la configuración:** subprocesos con la configuración por defecto, con `-X int_max_str_digits=640` y con `-X int_max_str_digits=0` dan el mismo resultado, sin excepción.
- **D7:** la coincidencia sigue siendo parcial y no aprueba nada; `desde` o el momento del análisis no pueden declararse, y el docstring dice «parcial».
- **Invariantes:**
  - `huella_diseno()` no cambia;
  - las huellas de las candidatas pequeñas de referencia (P1, P2, EMD y bloques), calculadas sobre la base antes de corregir, no cambian;
  - no hay ningún estado aprobado;
  - los siete pendientes, el mínimo de 100 y la especificación de AE-53 siguen intactos.

**Mediciones en el sandbox Linux de Claude** (Python `3.11.15`, sin datos reales):
- **Sobre la base, antes de corregir:** las regresiones (archivo nuevo y prueba de límite ajustada) dieron `48 failed, 143 passed` (código de pytest `1`). Un primer intento falló al recolectarse (código `2`), porque pytest intentaba mostrar `10**5000` como identificador; se corrigió con `ids` explícitos antes de corregir el módulo.
- **Sobre el código final:** `66 passed` en las pruebas nuevas y `191 passed` junto con las de AE-56 (código `0`).
- **Focalizadas:** `635 passed` (código `0`): las de AE-56 más las `66` nuevas.
- **Suite completa en una única corrida:** `4814 + 66 = 4880 passed`, `0 skipped`, código `0`, con los cinco `DeprecationWarning` conocidos de Alembic.
- `pip check` y `git diff --check`: código `0`.

**Validación real del operador en Windows/Python `3.14.6` y pytest `9.1.1` -evidencia atribuida al usuario, no ejecutada por Claude**: rama `feature/ae57-auditoria-diseno-prospectivo`, con HEAD base `0bdaf0bc9df50bee462d2b4b6f11008ee61fc013`.
- **Parche aplicado:** el parche completo `ae57-auditoria-diseno-prospectivo.patch`, con SHA-256 verificado `b61e761b8efc575a75177e0dd4b39916572a751aa0b1358b5ba3f094cd794736`.
- **Comprobaciones:** `git apply --check`, la aplicación, `git apply --reverse --check` y `git diff --check` fueron correctos.
- **Archivos:** exactamente seis (el módulo, las dos pruebas, README, ROADMAP y ARCHITECTURE).
- **Pruebas de AE-57 junto con AE-56:** `191 passed` en `1,74 s`.
- **Focalizadas:** `635 passed` en `21,37 s`.
- **`pip check`:** sin problemas.

**En Windows no se ejecutó la suite completa.** La cifra `4880 passed, 0 skipped` corresponde únicamente al sandbox Linux de Claude (Python `3.11.15`).

**Límites de esta validación**: «validada» se refiere únicamente a **esta auditoría**, a sus correcciones D1–D6, a la aclaración D7 y a sus pruebas. No aprueba ningún diseño, pregunta, familia de método, parámetro, nivel, potencia, efecto, horizonte, tratamiento de omisiones ni regla prospectiva, y no cierra `regla_estadistica_de_decision`. Quedan explícitos:
- **Cambio deliberado del límite de enteros:** hasta 640 dígitos decimales se admite la huella; con más de 640 el informe es `incoherente` con `huella = None`, con cualquier configuración de CPython. Los enteros de 641 a 4300 dígitos, que AE-56 v2 admitía, ya no tienen huella.
- **Coincidencia solo parcial con AE-53:** `coincide_con_propuesta_ae53` compara únicamente la cantidad de objetivos y el número de análisis. No comprueba desde qué objetivo empieza la ventana ni cuándo se analiza, y no certifica ni aprueba la propuesta de AE-53.
- **Nombre público residual:** `coincide_con_propuesta_ae53` se conserva por compatibilidad, aunque sugiere más de lo que comprueba.
- **Decisiones pendientes:** siguen abiertas las de las clases 2 (omisiones, objetivos frente a resueltos, contradicciones sin pregunta, literal de R11, huella sintáctica, texto del catálogo), 3 (inferenciales) y 4 (anterioridad, procedencia y autorización).

Siguen igual:
- el catálogo `DIMENSIONES_AE56` y `huella_diseno()`;
- los siete pendientes de AE-52, abiertos;
- la especificación candidata de AE-53, sin aprobar;
- el NO-GO de AE-39 y los bloqueos de AE-41 y AE-46.

Con esta evidencia, **AE-57 queda validada como auditoría del diseño prospectivo con sus correcciones verificables**; la auditoría no equivale a aprobación de ningún diseño ni a autorización operativa.

No se usaron datos reales, PostgreSQL, entrenamiento ni predicciones reales. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-56 sin cambios.

**Etapa AE-58 -semántica de omisiones prospectivas, validada:** audita la relación entre tres piezas:
- el mínimo de AE-52 de 100 sorteos **resueltos**;
- la propuesta **no aprobada** de AE-53: los primeros 100 **objetivos** tras el corte, con cualquier omisión dejando el juego no evaluable;
- `validar_secuencia_objetivos` de AE-53 y R9 de AE-56 con las precisiones de AE-57.

Formaliza cuatro nociones distintas:
- **objetivo:** posición `C+1..C+100` de la ventana propuesta;
- **predicción registrada;**
- **sorteo ocurrido:** `≤ ultimo_sorteo_ocurrido`;
- **resultado resuelto.**

Con ellas, informa los hechos y las **consecuencias hipotéticas** de cada alternativa ante una omisión, **sin elegir, aprobar ni recomendar ninguna** y **sin autorizar ninguna evaluación**.

**Qué está fijado, qué está propuesto y qué sigue sin decidir:**
- **Fijado por AE-52** (`REGLAS_EVALUACION_AE52`):
  - mínimo de 100 resultados resueltos por juego, sin reducción retroactiva;
  - «sorteos consecutivos sin sustitución: las omisiones se informan y no se sustituyen»;
  - ningún agregado antes del mínimo;
  - además, por código, predecir el sorteo `o` exige una entrada que termina en `o − 1`, así que `o − 1` ya ocurrió, y los objetivos son estrictamente crecientes.
- **Propuesto por AE-53, sin aprobar:**
  - ventana de los primeros 100 objetivos tras el corte con un único análisis;
  - cualquier omisión en la ventana deja el juego no evaluable, sin sustituir ni ampliar.
- **Sin decidir:**
  - el tratamiento de omisiones;
  - si ampliar la ventana equivale a sustituir;
  - si podría contar una serie consecutiva que empiece después del corte.

**Casos sintéticos** (corte `C = 2713`), reproducidos antes de implementar:
- **C1:** 100 predicciones, 97 resueltos y 3 pendientes → `incompleta`. Todavía no hay 100 resueltos, pero puede haberlos.
- **C2:** `ultimo = C+60` y predicciones de 1 a 61 → 60 resueltos y 40 futuros. Los futuros no son omisiones.
- **C3:** `ultimo = C` con predicciones de 1 a 100. AE-53 lo clasifica como 100 futuros, pero es **imposible bajo AE-52**, que rechaza predecir `C+5` sin la entrada hasta `C+4`. **Defecto verificable de dominio:** AE-53 acepta estados que AE-52 no puede producir y los llama «aún no ocurridos». AE-53 no se modifica, porque una aserción validada fija ese dominio amplio; el módulo nuevo rechaza esas entradas.
- **C4:** omisión en `C+50` y resultados de 1 a 101 salvo 50. AE-53 da `no_evaluable_por_omision`. En el resumen de AE-52, BALOTO da `resultados_incorporados = 100`, `omisiones = [C+50]` y **`faltantes = 0`**. Ese contador incluye `C+101`: **no significa que el mínimo se alcance sin sustitución**. Es una afirmación excesiva de texto; AE-52 no cambia.
- **C5:** última predicción en `C+50` y `ultimo = C+60` → AE-53 ve las omisiones `C+51..C+60`. AE-52 da `omisiones = []`, porque solo ve huecos anteriores a su último objetivo; la anterioridad sigue siendo un requisito externo.
- **R9:** `objetivos ≥ 100` es una condición **necesaria, no suficiente**, del mínimo de AE-52. Solo cambia el mensaje, a «condicion necesaria, no suficiente, del minimo de AE-52 de 100 resueltos». El comportamiento, el catálogo y `huella_diseno()` no cambian.

**Hechos** (`app/application/ml/semantica_omisiones_prospectivas.py`, `analizar_omisiones`). Con `W = C+1..C+100`, `P` las predicciones, `R` los resueltos y `U` el último sorteo ocurrido:
- **Omisiones en la ventana:** `{o ∈ W : o ≤ U, o ∉ P}`.
- **`resueltos_consecutivos_desde_el_corte`:** el mayor `m` con `C+1..C+m ⊆ R`, sin tope.
- **`cien_consecutivos_desde_el_corte`:** `W ⊆ R`. Es el único hecho que satisface a la vez el mínimo y «consecutivos sin sustitución» leídos desde el corte.
- **`total_resueltos_descriptivo = |R|`:** incluye los resueltos posteriores a la ventana. No incluye objetivos `≤ C` ni sorteos no ocurridos, que se rechazan en la entrada. Es el mismo recuento que `resultados_incorporados` de AE-52.
- **`faltantes_como_en_resumen_ae52 = max(0, 100 − |R|)`:** es **descriptivo, no elegibilidad**.
- **`estado_segun_propuesta_ae53`:** la llamada sin cambios a `validar_secuencia_objetivos`.

**Consecuencias hipotéticas de cada alternativa.** Cada una separa el conjunto que contaría, el estado aritmético del recuento y su relación con las reglas vigentes de AE-52:
- **`no_evaluable`** (propuesta de AE-53, no aprobada): cuenta `R ∩ W`. Con omisión, `no_puede_alcanzar_100` y `sin_conflicto_conocido`, porque informa la omisión y no cuenta ni evalúa.
- **`ventana_fija_sin_ampliar`** (sin decidir): cuenta `R ∩ W`. Con omisión, `no_puede_alcanzar_100` y `incompatible_con_minimo`.
- **`ampliar_ventana`** (sin decidir): cuenta los resueltos de la ventana ampliada **solo por omisiones**: los primeros 100 sorteos posteriores al corte que no son omisiones, donde los pendientes y los futuros ocupan su lugar (definición corregida por AE-59; antes decía «los primeros 100 resueltos», lo que saltaba resultados pendientes). Con omisión, `alcanza_100_hipotetico` si los hay y `no_establecida_requiere_interpretacion`. **No es un permiso operativo**:
  - la interpretación no está decidida;
  - el resultado es observacionalmente igual a una sustitución;
  - las reglas vigentes (el NO-GO de AE-39, AE-41 y `regla_estadistica_de_decision`) siguen impidiendo evaluar.
- **`reemplazar_objetivo`** (sin decidir): cuenta **el mismo conjunto** que `ampliar_ventana`. Con omisión, `incompatible_con_sin_sustitucion`, frente al texto fijado por AE-52.
- **Sin omisión**, las cuatro coinciden: `puede_alcanzar_100` con pendientes o futuros, o `alcanza_100_hipotetico` con 100 consecutivos, y siempre `sin_conflicto_conocido`, que no afirma que las reglas se cumplan.
- `autoriza_evaluacion` es siempre `False`, y `decision` es siempre `sin_decidir`.

**Base verificada explícitamente.** `verificar_base_ae52_ae53()` comprueba cada vez que las tres reglas de AE-52 existen con su valor exacto (sin aceptar, por ejemplo, `100.0` ni `1`). También comprueba que las propuestas `horizonte` y `omisiones` de AE-53 existen con su valor exacto y en estado `propuesta_no_aprobada`. Cualquier divergencia lanza `BaseDivergenteError`, nunca se filtra en silencio.

**Precisiones puntuales en secciones anteriores:**
- **AE-52:** `faltantes` es un recuento descriptivo, y `omisiones` son solo los huecos anteriores al último objetivo registrado.
- **AE-53:** el dominio de `validar_secuencia_objetivos` es más amplio que los estados posibles de AE-52.
- **AE-56:** R9 es una condición necesaria, no suficiente.

**Archivos:**
- nuevos: `app/application/ml/semantica_omisiones_prospectivas.py`, puro (biblioteca estándar y lectura de las constantes de AE-52 y AE-53, reutilizando `validar_secuencia_objetivos`), y `tests/unit/ml/test_semantica_omisiones_prospectivas.py`;
- modificado: `app/application/ml/diseno_regla_prospectiva.py`, solo el mensaje de R9;
- README, ROADMAP y ARCHITECTURE.

No cambian `registro_prospectivo.py`, `especificacion_evaluacion_prospectiva.py` ni ninguna prueba existente, y no hay CLI, rutas ni scripts.

**Pruebas** (`49` nuevas, sintéticas):
- **Casos:** C1–C5, con valores exactos.
- **Consecuencias:** las de los tres momentos (pendientes o futuros, 100 consecutivos, y omisión con resultados posteriores que suman 100); `ampliar_ventana` y `reemplazar_objetivo` con el mismo conjunto; tope de 100 en el recuento hipotético.
- **Entradas:** rechazo de C3 y propagación de los errores de AE-53.
- **Coherencia con AE-52:** un registro sintético en memoria da, en C4, los mismos `faltantes` y `resultados_incorporados`.
- **Vocabulario cerrado:** valores exactos, sin estados aprobados y sin autorización.
- **Divergencias forzadas:** cada regla de AE-52 ausente o con otro valor, y cada propuesta de AE-53 ausente, aprobada o con otro valor.
- **R9:** mensaje exacto y comportamiento sin cambios.
- **Invariantes:** constantes de AE-52 y AE-53 intactas, `huella_diseno()` sin cambios, y módulo aislado.

**Mediciones en el sandbox Linux de Claude** (Python `3.11.15`, sin datos reales):
- **Sobre la base, antes de crear el módulo:** las pruebas nuevas fallaron al recolectarse (código de pytest `2`).
- **Tras una corrección pedida por el operador durante la implementación:** las constantes dejaron de filtrar en silencio claves de AE-52 y propuestas de AE-53, y se sustituyeron por `verificar_base_ae52_ae53()`.
- **Sobre el código final:** `49 passed` (código `0`).
- **Focalizadas:** `684 passed` (código `0`): las de AE-57 más las `49` nuevas.
- **Suite completa en una única corrida:** `4880 + 49 = 4929 passed`, `0 skipped`, código `0`, con los cinco `DeprecationWarning` conocidos de Alembic.
- `pip check` y `git diff --check`: código `0`.

**Validación real del operador en Windows/Python `3.14.6` y pytest `9.1.1` -evidencia atribuida al usuario, no ejecutada por Claude**: rama `feature/ae58-semantica-omisiones-prospectivas`, con HEAD base `1e6f60f046ef61fc7b40cebeb5fb14c7562d3692`.
- **Parche aplicado:** el parche completo `ae58-semantica-omisiones-prospectivas.patch`, con SHA-256 verificado `f0009eddeac01123eb7d53a17b8db70d379e69a66c331c74142848b7bc8feef8`.
- **Comprobaciones:** `git apply --check`, la aplicación, `git apply --reverse --check` y `git diff --check` fueron correctos.
- **Archivos:** exactamente seis (el módulo y la prueba nuevos, `diseno_regla_prospectiva.py`, README, ROADMAP y ARCHITECTURE).
- **Pruebas nuevas:** `49 passed` en `1,29 s`.
- **Focalizadas:** `684 passed` en `21,87 s`.
- **`pip check`:** sin problemas.

**En Windows no se ejecutó la suite completa.** La cifra `4929 passed, 0 skipped` corresponde exclusivamente al sandbox Linux de Claude (Python `3.11.15`).

**Límites de esta validación**: «validada» cubre únicamente la **semántica descriptiva** (objetivo, predicción registrada, sorteo ocurrido y resultado resuelto, y los recuentos y consecuencias hipotéticas), la **detección explícita de divergencias** de la base de AE-52 y AE-53 (`verificar_base_ae52_ae53`) y sus **pruebas**. **No aprueba**:
- ninguna alternativa ante omisiones, sea `no_evaluable`, `ventana_fija_sin_ampliar`, `ampliar_ventana` o `reemplazar_objetivo`;
- el horizonte propuesto por AE-53;
- ninguna regla inferencial;
- la evaluación operativa.

`decision` sigue en `sin_decidir` y `autoriza_evaluacion` sigue en `False`.

Siguen igual:
- los siete pendientes de AE-52, abiertos;
- la especificación candidata de AE-53, sin aprobar;
- el NO-GO de AE-39 y los bloqueos de AE-41 y AE-46.

Con esta evidencia, **AE-58 queda validada como semántica descriptiva de omisiones prospectivas**; no equivale a elegir un tratamiento de omisiones ni a autorizar ninguna evaluación.

**Límites:**
- AE-58 no decide si una omisión invalida el juego, amplía el horizonte o permite reemplazar un objetivo, ni si ampliar es sustituir.
- No aprueba la propuesta de AE-53.
- No verifica la anterioridad.

No se usaron datos reales, PostgreSQL, entrenamiento ni predicciones reales. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-57 sin cambios.

**Etapa AE-59 -auditoría de la semántica de omisiones prospectivas, validada:** audita el módulo y las pruebas de AE-58 frente a los contratos reales de AE-52, AE-53 y AE-56. Todas las comprobaciones previas fueron de solo lectura, con números de sorteo sintéticos (corte `C = 2713`). Encuentra **dos defectos comprobados**, los corrige con regresiones escritas antes y deja sin cambios todo lo demás.

**H1 -`ampliar_ventana` y `reemplazar_objetivo` saltaban resultados pendientes como si fueran omisiones (gravedad alta).**
- **Entrada mínima:** `ultimo = C+101`, predicciones de `C+1` a `C+101` y resultados en todas salvo `C+50`. No hay omisión: `C+50` es un resultado **pendiente**.
- **Antes:** ampliar y reemplazar daban `(100, alcanza_100_hipotetico, sin_conflicto_conocido)`, contando `C+101` en lugar del pendiente. Contradecía la frase de AE-58 «sin omisión, las cuatro coinciden».
- **Ahora:** las cuatro alternativas dan `(99, puede_alcanzar_100, sin_conflicto_conocido)`.
- **Variante con omisión en `C+50`, pendiente en `C+60` y resueltos hasta `C+102`:**
  - antes, `100 / alcanza_100_hipotetico`;
  - ahora, `99 / puede_alcanzar_100`: la ventana ampliada es `W∖{C+50} ∪ {C+101}` y contiene el pendiente;
  - `no_evaluable` y `ventana_fija_sin_ampliar` siguen en `98`.
- **Causa:** `ampliado = resueltos[:100]` tomaba los primeros 100 **resueltos**. La corrección cuenta los resueltos de la **ventana ampliada solo por omisiones** (`_ventana_ampliada`):
  - la ventana son los primeros 100 sorteos posteriores al corte que no son omisiones: primero los ocurridos con predicción y después los futuros;
  - los pendientes y los futuros ocupan su lugar;
  - sin omisiones, la ventana ampliada es `W`.
- **Trabajo acotado:** la función solo ordena las predicciones y completa con, como máximo, 100 futuros desde `max(corte+1, ultimo+1)`. Nunca recorre el intervalo `corte..ultimo`. Una prueba con `ultimo = C + 10**12` y tres predicciones comprueba la ventana exacta y los recuentos. No hay aserciones de tiempo, que dependerían de la máquina. Otra prueba verifica la equivalencia con un recorrido ingenuo en intervalos pequeños.

**H2 -`verificar_base_ae52_ae53()` no detectaba cambios de estado, estructura y tipo de la especificación candidata (gravedad media; tipos, baja).** Casos reproducidos sustituyendo la constante en memoria, que antes pasaban sin error:
- estado global `"aprobada"`;
- una clave extra (`"aprobada_por"`) en una propuesta usada;
- la copia `fijado_por_ae52` de AE-53 con el mínimo en `50`, con otro valor o con claves de más o de menos.

Además, una especificación o unas reglas que no fueran `dict` provocaban `AttributeError` o `TypeError`. Ahora todos estos casos lanzan `BaseDivergenteError`. `pendientes` de AE-53 queda fuera: AE-58 no depende de ellos y ya los prueba AE-53.

**Observaciones sin defecto**, que no se cambian:
- **Recuentos:** `total_resueltos_descriptivo` y `faltantes_como_en_resumen_ae52` coinciden con AE-52 e incluyen los resultados posteriores a la ventana.
  - El total **puede superar 100** y no tiene tope; `faltantes` tiene piso cero.
  - Solo los conjuntos hipotéticos de ampliar y reemplazar se limitan a 100; los de `no_evaluable` y `ventana_fija_sin_ampliar` están acotados por `W`.
  - Las omisiones finales dentro de `W` y los resueltos consecutivos son correctos.
- **Invariante:** `o ≤ ultimo + 1` representa fielmente la regla de entrada de AE-52. El módulo no puede verificar:
  - la anterioridad;
  - la veracidad de `ultimo_sorteo_ocurrido`;
  - el orden de registro;
  - la procedencia.
- **Dominio:** acepta cualquier corte entero, igual que AE-53. Es una limitación compartida.
- **Propiedades:** los errores de AE-53 se propagan y el resultado es determinista. `hash(informe)` lanza `TypeError` por el `MappingProxyType` de AE-53, pero ningún contrato exige que sea hasheable.
- **Documentación de AE-58:** atribuía bien las mediciones de Linux y Windows. Su única frase incorrecta era la definición de ampliar y reemplazar, que se corrige.

**Decisiones abiertas, no defectos:**
- el tratamiento de omisiones;
- si ampliar equivale a sustituir;
- si podría contar una serie consecutiva que empiece más tarde;
- la regla inferencial y la autorización.

**Archivos:**
- `app/application/ml/semantica_omisiones_prospectivas.py`: `_ventana_ampliada`, recuento de ampliar y reemplazar, verificación de la base y docstrings;
- `tests/unit/ml/test_auditoria_omisiones_prospectivas.py`: nuevo;
- README, ROADMAP y ARCHITECTURE: esta sección y la definición corregida en la sección de AE-58.

No cambian las 49 pruebas de AE-58, `registro_prospectivo.py`, `especificacion_evaluacion_prospectiva.py` ni `diseno_regla_prospectiva.py`. Los vocabularios, las firmas, los campos del informe, R9 y `huella_diseno()` tampoco cambian.

**Pruebas** (`56` nuevas, sintéticas):
- **H1:** la variante con omisión, la ventana que llega a sorteos futuros, el último sorteo muy distante y la equivalencia con el recorrido ingenuo.
- **Propiedad:** «sin omisión, las cuatro coinciden», con pendientes en varias posiciones, futuros y más de 100 resueltos.
- **AE-58:** sus casos sin cambios (C4, C5, 100 consecutivos y tope).
- **H2:** estado global, estructura, `fijado_por_ae52` y tipos.
- **Invariantes:** sin decisión ni autorización, constantes intactas y `huella_diseno()` sin cambios.

**Mediciones en el sandbox Linux de Claude** (Python `3.11.15`, sin datos reales):
- **Sobre la base, antes de corregir:** las regresiones dieron `36 failed, 20 passed` (código de pytest `1`).
- **Al corregir, un fallo era de la propia prueba:** en la variante H1b el plan esperaba `98` para ampliar y reemplazar, pero la ventana ampliada `W∖{C+50} ∪ {C+101}` contiene `99` resueltos (98 en `W` más `C+101`). Se corrigió la aserción; el `98` sigue siendo correcto para `no_evaluable` y `ventana_fija_sin_ampliar`.
- **Sobre el código final:** `56 passed` en las nuevas y `105 passed` junto con las `49` de AE-58, sin cambios (código `0`).
- **Focalizadas:** `740 passed` (código `0`): las de AE-58 más las `56` nuevas.
- **Suite completa en una única corrida:** `4929 + 56 = 4985 passed`, `0 skipped`, código `0`, con los cinco `DeprecationWarning` conocidos de Alembic.
- `pip check` y `git diff --check`: código `0`.

**Validación real del operador en Windows/Python `3.14.6` y pytest `9.1.1` -evidencia atribuida al usuario, no ejecutada por Claude**: rama `feature/ae59-auditoria-omisiones-prospectivas`, con HEAD base `7ffdaf908ca38b19e73cde1048f339a2801b3ba5`.
- **Parche aplicado:** el parche completo `ae59-auditoria-omisiones-prospectivas.patch`, con SHA-256 verificado `3df260a22dfdde1e672f47cc832543b4e328275d4de8cd5aa7451c5a07c9c9dc`.
- **Comprobaciones:** `git apply --check`, la aplicación, `git apply --reverse --check` y `git diff --check` fueron correctos.
- **Archivos:** exactamente cinco (el módulo de AE-58, la prueba nueva, README, ROADMAP y ARCHITECTURE).
- **Pruebas de AE-59 junto con AE-58:** `105 passed` en `1,38 s`.
- **Focalizadas:** `740 passed` en `16,03 s`.
- **`pip check`:** sin problemas.

**En Windows no se ejecutó la suite completa.** La cifra `4985 passed, 0 skipped` corresponde únicamente al sandbox Linux de Claude (Python `3.11.15`).

**Límites de esta validación**: «validada» cubre únicamente las **correcciones comprobadas H1 y H2 y sus pruebas**:
- **H1:** la ventana ampliada solo por omisiones, con trabajo acotado, que ya no salta resultados pendientes;
- **H2:** la detección de divergencias de estado, estructura, copia `fijado_por_ae52` y tipo en `verificar_base_ae52_ae53()`.

Queda explícita la **corrección aritmética de H1b**: con omisión en `C+50`, pendiente en `C+60` y resueltos hasta `C+102`, la ventana ampliada `W∖{C+50} ∪ {C+101}` contiene **99** resueltos. Dentro de `W` hay **98**, que es lo que cuentan `no_evaluable` y `ventana_fija_sin_ampliar`.

**No aprueba**:
- ampliar ni reemplazar objetivos;
- el horizonte de AE-53;
- ninguna regla inferencial;
- ninguna evaluación operativa.

Ningún recuento hipotético es un mínimo cumplido; `decision` sigue en `sin_decidir` y `autoriza_evaluacion` en `False`.

Siguen igual:
- los siete pendientes de AE-52, abiertos;
- la especificación candidata de AE-53, sin aprobar;
- el NO-GO de AE-39 y los bloqueos de AE-41 y AE-46.

Con esta evidencia, **AE-59 queda validada como auditoría de la semántica de omisiones prospectivas con sus correcciones H1 y H2**; no equivale a elegir un tratamiento de omisiones ni a autorizar ninguna evaluación.

**Límites:**
- AE-59 no decide el tratamiento de omisiones y no aprueba la propuesta de AE-53 ni ninguna alternativa.
- Ningún recuento hipotético es un mínimo cumplido, una decisión ni una autorización.
- No verifica la anterioridad ni la procedencia.

No se usaron datos reales, PostgreSQL, entrenamiento ni predicciones reales. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-58 sin cambios.

**Etapa AE-60 -expediente preparatorio de inferencia prospectiva, validada:** determina si los contratos de AE-52 a AE-59 permiten formular una regla inferencial candidata para comparar prospectivamente una estrategia con la referencia uniforme.

**Conclusión:** **no hay fundamento suficiente para escoger** una regla. AE-60 es preparatoria. Añade el expediente puro `app/application/ml/propuesta_inferencia_prospectiva.py`, **sin valores de decisión y sin elección**, con:
- las preguntas y las familias de métodos, con su garantía;
- los escenarios de un estudio sintético **posterior**;
- las decisiones requeridas y los criterios para detenerse sin elección.

El estudio, la elección humana y cualquier implementación de la regla son etapas separadas. El estado es fijo, `expediente_sin_eleccion`, y `AUTORIZA_EVALUACION = False`.

**Inventario:**
- **Fijado por AE-52:**
  - mínimo de 100 resultados **resueltos** por juego;
  - LL y Brier principales; P@5 y R@5 secundarias;
  - orientación «uniforme − estrategia»;
  - juegos por separado;
  - consecutivos sin sustitución;
  - ningún agregado antes del mínimo;
  - una entrada que termina en `o−1`;
  - los siete pendientes.
- **Propuesto por AE-53, sin aprobar:** horizonte de 100 objetivos con análisis único y tratamiento de omisiones.
- **Exploratorio o analítico:** el banco AE-54 y la factibilidad AE-55, sin valor de decisión.
- **Coherencia:** el catálogo y el validador de AE-56/57.
- **Semántica descriptiva:** omisiones de AE-58/59.

**Hallazgo de contrato:** en P@5, que es una ganancia, `d = uniforme − estrategia > 0` favorece a la uniforme, así que la mejora es `d < 0`. En LL y Brier la mejora es `d > 0`. `ORIENTACION_MEJORA_POR_METRICA` lo declara y una prueba lo comprueba con `metricas_por_sorteo`.

**Preguntas.** Con `g_t = E[d_t | F_{t−1}]` y `Δ_n = (1/n)Σ g_t`:
- **P1a:** `μ_W ≤ 0` frente a `> 0`, para las familias de media.
- **P1b-único:** nula terminal `Δ_100 ≤ 0`, que admite prefijos positivos.
- **P1b-supervisión:** nula `Δ_t ≤ 0` para todo `t ∈ T`, con `T` contenido en la ventana de 100 objetivos. Es una nula **sobre `T`** y no restringe los prefijos fuera de `T`.
  - `Δ_t` se definió sobre esa ventana: tiempos `t > 100` exigen una extensión del horizonte decidida por el operador.
  - Hay conflicto con AE-52 si algún tiempo tiene menos de 100 resueltos, así que con las reglas vigentes solo cabe `T = {100}`, que coincide con la nula terminal.
- **P2:** `E[d_t | F_{t−1}] = 0`. No es direccional: con sorteos uniformes y una estrategia no uniforme, un rechazo no indica mejora.
- **P3:** el mecanismo de sorteo, que no se responde con el registro.

Hechos relacionados (inferencia propia):
- `ε_t = d_t − g_t` es una diferencia de martingala por construcción. La anterioridad es lo que hace de `g_t` una ventaja **predictiva**.
- `E[Δ_100] = μ_W` solo vale con la ventana fijada antes de los datos y sus 100 objetivos resueltos. Con omisiones, sustitución, selección o parada dependiente de los datos queda **pendiente**.

**Familias.** Cada una declara garantía, exigencia sobre la media, valor p, parámetros a fijar (solo nombres) y evidencia que falta.
- **Catálogo de AE-56:**
  - M1, M2, M3a y M3b responden a P1a y exigen una media común (estacionariedad, independencia o ausencia de autocorrelación según el caso) **[lit]**;
  - GW responde a P2 **[lit]**.
- **Fuera del catálogo de AE-56**, incorporarlas sería una decisión humana:
  - **`cota_martingala_tiempo_fijo`:** P1b-único mediante la desigualdad de Azuma. Admite `g_t` variables y da un valor p válido **solo** en `n = 100`.
  - **`secuencia_confianza_uniforme_martingala`:** tiene cobertura uniforme en el tiempo y admite medias condicionales variables en promedio (precisión de AE-61: descripción general apoyada por el README de los autores de Choe–Ramdas; condiciones de los teoremas, pendientes de lectura primaria; Howard et al., sin verificación primaria). Precisión de AE-62: los teoremas 1–2 de Choe–Ramdas `arXiv:2110.00115v6` establecen la cobertura simultánea bajo sus condiciones, según la revisión de otro auditor del proyecto; el teorema 4 de Howard et al. (`arXiv:1810.08240v9`) no tuvo revisión específica; la aplicación a este repositorio no está demostrada.
    - Responde a P1b-supervisión **invirtiendo la secuencia simultánea**: se rechaza si `inf C_t > 0` para algún `t ∈ T`. Si se cumplen las condiciones de un teorema de cobertura simultánea (precisión de AE-62: `PREMISA_DE_LA_INVERSION`), `P(∃t: Δ_t ∉ C_t) ≤ α` y, bajo la nula sobre `T`, el rechazo exige que algún `Δ_t` quede fuera de `C_t`. El valor p es el menor α con ese rechazo, si la familia es monótona en α.
    - Responde a P1b-único **solo** invirtiendo `C_100`.
    - Las fórmulas con e-procesos, `min(1, 1/sup_T E_t)` y `min(1, 1/E_100)`, quedan **pendientes de demostración** bajo la nula sobre `T` y bajo la terminal. Un e-proceso construido desde el inicio puede exigir restricciones en prefijos fuera de `T`, así que no se atribuye a Ville una garantía no demostrada para esas nulas. Precisión de AE-64: para el proceso exponencial del teorema 3 de Choe–Ramdas v6 existe una derivación propia de cotas conjuntas bajo la nula terminal y sobre `T`, condicionada a las hipótesis de la supermartingala; su aplicación al repositorio sigue pendiente, así que estas fórmulas siguen pendientes de demostración.
  - **`secuencia_confianza_apuesta_media_comun`:** exige una media condicional común, así que **no es aplicable** a P1b con `g_t` variable (precisión de AE-62: esta familia concreta corresponde al modelo básico con `E[X_t | F_{t−1}] = μ` constante, §2 y proposición 2 de `arXiv:2010.09686v7` según la revisión de otro auditor; no se afirma que toda apuesta exija una media común).

La validez de un método secuencial **no** cambia el mínimo ni la prohibición de agregados de AE-52.

**Conjunción y juegos.**
- **LL y Brier por juego:** intersección-unión **[lit: Berger]**, con `p_juego = max(p_LL, p_Brier)` y `E_juego = min(E_LL, E_Brier)`. Precisión de AE-61: `E_juego` está condicionado a e-valores válidos por métrica, que hoy están pendientes.
- **«Ambos juegos»:** otra intersección-unión.
- **«Al menos uno»:** Holm **[lit]**.
- **Informes solo por juego:** no controlan el error familiar.
- **Secundaria:** fuera de la conjunción, con mejora negativa.

**Estudio sintético posterior (solo especificado).** Hay siete escenarios (A0–A4, L-unif y L-sint), con el estado de la nula **por pregunta** y su realizabilidad con sorteos uniformes.
- El error tipo I solo se calcula donde la nula de esa pregunta es verdadera (`escenarios_nulos`). Por ejemplo, A1 es nulo para P1b-único y, para la supervisión, depende de `T` (`segun_T`): con `T = {100}` es nulo, y con tiempos intermedios de prefijo positivo es alternativa. L-unif y A2 son nulos de P1 y alternativas de P2.
- Con sorteos uniformes, la frontera no degenerada de P1 no es realizable.
- **Salidas sin fijar α:** distribuciones completas de valores p, trayectorias de e-procesos con el proceso, `T` y la regla declarados, y la cobertura uniforme.
- El operador fija los efectos, `T`, las cotas y los criterios **antes** de ejecutarlo; si no, no se ejecuta.

**Decisiones requeridas:**
- **humanas:** pregunta, α, efecto mínimo, forma de la afirmación entre juegos, corrección, potencia, momento y tiempos del análisis, omisiones, familias externas, secundaria y criterios del estudio;
- **inferenciales:** memoria y estacionariedad de `g_t`, potencia, condiciones exactas, validez de `1/E_100` (precisión de AE-62: y de `1/sup_T E_t`) y reentrenamiento **[lit: West]**;
- **externas:** sellado, autorización de AE-41, estrategia, tramo y contrato de inferencia.

`DECISIONES_INFERENCIALES_ABIERTAS` (α, bloque, ancho de banda, efecto, potencia, corrección, tiempos y cota) tiene todos los valores en `None` y el estado en `sin_decidir`.

**Criterios de detención sin elección:** (a) faltan decisiones; (b) ningún par (pregunta, familia) cumple los criterios en todos sus escenarios nulos; (c) solo lo cumple una familia externa no incorporada; (d) supervisión con tiempos anteriores a 100 resueltos; (e) no hay sellado.

**Literatura verificada** (título, revista, volumen, páginas y DOI en índices o en las páginas de las editoriales; precisión de AE-62: verificación bibliográfica, no de los teoremas):
- Diebold–Mariano (1995), doi:10.1080/07350015.1995.10524599;
- Diebold (2015), doi:10.1080/07350015.2014.983236;
- Harvey–Leybourne–Newbold (1997), doi:10.1016/S0169-2070(96)00719-4;
- Giacomini–White (2006), doi:10.1111/j.1468-0262.2006.00718.x;
- West (1996), jstor 2171956;
- Newey–West (1987), jstor 1913610;
- Kiefer–Vogelsang (2005), doi:10.1017/S0266466605050565;
- Künsch (1989), doi:10.1214/aos/1176347265;
- Politis–Romano (1994), doi:10.1080/01621459.1994.10476870;
- Gneiting–Raftery (2007), doi:10.1198/016214506000001437;
- Berger (1982), doi:10.2307/1267823;
- Holm (1979), jstor 4615733;
- Azuma (1967), doi:10.2748/tmj/1178243286;
- Howard–Ramdas–McAuliffe–Sekhon (2021), doi:10.1214/20-AOS1991;
- Choe–Ramdas (2024), doi:10.1287/opre.2021.0792;
- Waudby-Smith–Ramdas (2024), doi:10.1093/jrsssb/qkad009;
- Ramdas–Grünwald–Vovk–Shafer (2023), doi:10.1214/23-STS894;
- Lan–DeMets (1983), doi:10.1093/biomet/70.3.659;
- RFC 3161.

arXiv y varias editoriales estaban bloqueadas en el sandbox. Las condiciones exactas de Howard et al., Choe–Ramdas y Waudby-Smith–Ramdas deben verificarse en el texto completo antes de cualquier uso.

**Lo que las fuentes no resuelven:**
- la memoria real de `g_t`;
- la potencia con 100 sorteos;
- α, el efecto y la multiplicidad;
- el conflicto entre la supervisión y AE-52;
- la anterioridad sin sellado;
- la ventana afectada por omisiones.

**Archivos:** son nuevos `app/application/ml/propuesta_inferencia_prospectiva.py` (puro: solo lee las constantes de AE-52, AE-53 y AE-56) y `tests/unit/ml/test_propuesta_inferencia_prospectiva.py`. No cambia ningún archivo de AE-39 a AE-59, ni el catálogo de AE-56.

**Pruebas** (`58` nuevas, sintéticas):
- **Base:** estado fijo y verificación, con divergencias forzadas de AE-52, AE-53 y AE-56, incluidos el contenido de los pendientes, las propuestas y sus estados, los pendientes de AE-53 y constantes que no son diccionarios.
- **Regresiones v2:** supervisión limitada a la ventana; inversión de la secuencia simultánea; ninguna familia declara válida una fórmula con `1/E`; A1 y L-sint `segun_T`; y la verificación ampliada.
- **Preguntas:** P1b-único frente a supervisión, direcciones y P3.
- **Familias:** coherencia con `SUPUESTOS_POR_FAMILIA`; externas marcadas; apuesta no aplicable; Azuma solo en tiempo fijo; secuencia de confianza solo por inversión en P1b-único, con `1/E_100` pendiente; valores p de e-procesos con el proceso, el tiempo, la regla y la nula.
- **Escenarios:** estados por pregunta, nulas de P2, realizabilidad y `escenarios_nulos`.
- **Orientación y conjunción:** orientación comprobada con `metricas_por_sorteo`; formas de conjunción.
- **Decisiones:** abiertas sin valor, parámetros solo como nombres, sin campos de valor elegido, decisiones por clase y criterios de detención.
- **Vocabulario cerrado:** sin aprobación, GO, cumplimiento ni desbloqueo.
- **Referencias:** con identificador verificable.
- **Invariantes:** inmutabilidad, constantes de AE-52/53/56 y `huella_diseno()` intactas, y aislamiento.

**Historia de la corrección (v1 → v2).** El operador auditó el parche v1 (`ae60-propuesta-inferencia-prospectiva.patch`, 69 645 bytes, SHA-256 `d24c60fccd011ae56f7fbd69bc486c9f383f54054b38bfda39fcdca821273674`) y encontró dos inconsistencias:
- **Supervisión y Ville.** v1 declaraba la nula de P1b-supervisión solo sobre `T` y afirmaba que `min(1, 1/sup_T E_t)` era válido por Ville bajo ella. Un e-proceso construido desde el inicio puede exigir restricciones en prefijos fuera de `T`, y con `T = {100}` reaparece la nula terminal, bajo la cual el propio expediente dejaba `1/E_100` pendiente. Precisión de AE-64: ese motivo general no impide la derivación propia, condicionada a las hipótesis de la supermartingala, para el proceso exponencial del teorema 3 de Choe–Ramdas v6 (sección de AE-64); los usos de `1/E` siguen pendientes por las dependencias del repositorio.
  - v2 contrasta la supervisión **invirtiendo la secuencia simultánea**, limita `T` a la ventana de 100 objetivos y deja **pendientes** todas las fórmulas con `1/E`.
  - A1 y L-sint pasan a `segun_T`, y `escenarios_nulos("P1b_supervision")` solo incluye los escenarios nulos para cualquier `T`.
- **Promesa de `verificar_expediente()`.** Prometía detectar «cualquier divergencia», pero de AE-52 solo comprobaba el número de pendientes, el mínimo y la orientación, y de AE-53 solo el estado global. Además, una constante que dejara de ser diccionario provocaba `AttributeError`.
  - v2 comprueba los siete pendientes exactos, las tres propuestas de AE-53 con su valor y estado, los seis pendientes de AE-53 sin valor, los tipos de las constantes y el catálogo de AE-56.
  - Su docstring acota la promesa a esos invariantes.

Las regresiones se escribieron antes de corregir. Sobre el código v1 dieron `16 failed, 42 passed` (código de pytest `1`). Cambió una aserción de v1 que era incorrecta por diseño: A1 ya no es siempre una alternativa de la supervisión.

**Mediciones en el sandbox Linux de Claude** (Python `3.11.15`, sin datos reales):
- **v1:** antes de crear el módulo, las pruebas nuevas fallaron al recolectarse (código de pytest `2`).
- **v2, sobre el código final:** `58 passed` (código `0`).
- **Focalizadas:** `798 passed` (código `0`): las de AE-59 más las `58` nuevas.
- **Suite completa en una única corrida:** `4985 + 58 = 5043 passed`, `0 skipped`, código `0`, con los cinco `DeprecationWarning` conocidos de Alembic.
- `pip check` y `git diff --check`: código `0`.

**Validación real del operador en Windows/Python `3.14.6` -evidencia atribuida al usuario, no ejecutada por Claude**: en `C:\GitHub\loteria-predictor-update`, rama `feature/ae60-propuesta-inferencia-prospectiva`, con HEAD base `a08c6342a83cf0e71b2e562702d5dcb1a65e2775` y árbol limpio antes de aplicar.
- **Parche aplicado:** el parche completo v2 `ae60-propuesta-inferencia-prospectiva-v2.patch`, con SHA-256 verificado `f486949fc0ddda1b6ff68e93d5dfd03a41e330e741cb30ec39a84a565348d451`.
- **Comprobaciones:** `git apply --check`, `git apply`, `git apply --reverse --check` y `git diff --check` fueron correctos.
- **Archivos:** exactamente cinco (ARCHITECTURE.md, README.md, ROADMAP.md, el módulo y la prueba nuevos).
- **Pruebas nuevas:** `58 passed` en `0,45 s`, código `0`.
- **Focalizadas:** `798 passed` en `23,43 s`, código `0`.
- **`pip check`:** `No broken requirements found.`, código `0`.

**En Windows no se ejecutó la suite completa.** La cifra `5043 passed, 0 skipped` corresponde únicamente al sandbox Linux de Claude (Python `3.11.15`).

**Límites de esta validación**: «validada» cubre solo el **expediente preparatorio** y sus pruebas. **No** elige pregunta, método ni familia, ni α, efecto, potencia, corrección de multiplicidad, tiempos de supervisión ni tratamiento de omisiones.
- Las fórmulas con `1/E` (`1/sup_T E_t` y `1/E_100`) siguen **pendientes de demostración**.
- La familia de secuencias de confianza queda descrita solo mediante **inversión**: de la secuencia simultánea para la supervisión y de `C_100` para la nula terminal.
- No cierra `regla_estadistica_de_decision` y no autoriza ninguna evaluación.

Siguen igual:
- los siete pendientes de AE-52, abiertos;
- la especificación candidata de AE-53, sin aprobar;
- el NO-GO de AE-39 y los bloqueos de AE-41 y AE-46.

Con esta evidencia, **AE-60 queda validada como expediente preparatorio de inferencia prospectiva**; no equivale a elegir una regla ni a autorizar ninguna evaluación.

**Límites:**
- AE-60 no elige pregunta, familia ni valor alguno, y no cierra `regla_estadistica_de_decision` ni ningún pendiente de AE-52.
- No aprueba la especificación de AE-53.
- No modifica el catálogo de AE-56.
- No verifica la anterioridad.
- No autoriza ninguna evaluación.

No se usaron datos reales, PostgreSQL, entrenamiento ni predicciones reales. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-59 sin cambios.

**Etapa AE-61 -auditoría del expediente de inferencia prospectiva (AE-60), validada:** audita `app/application/ml/propuesta_inferencia_prospectiva.py`, sus pruebas y la sección de AE-60. Contrasta sus garantías con las fuentes y separa tres clases de hallazgos:
- **errores demostrados** (E1–E3);
- **afirmaciones que requieren hipótesis o precisión adicionales** (H1–H4);
- **decisiones del operador** (D1–D2).

**No** convierte ninguna garantía pendiente en válida: todos los usos de `1/E` siguen como `pendiente_de_demostracion`. Tampoco elige pregunta, familia, α, potencia, efecto, horizonte, tratamiento de omisiones ni regla.

**Fuentes: qué se verificó y qué no.** En el sandbox están bloqueados arXiv, Project Euclid, OUP, INFORMS y los sitios de los autores.
- **(a) Material de los autores de Choe–Ramdas:**
  - el resumen de arXiv 2110.00115 no fue accesible; solo hubo fragmentos de índices de búsqueda;
  - el README de los autores (github.com/yjchoe/ComparingForecasters), leído directamente, dice que las secuencias de confianza estiman «the average score difference between forecasters A and B (which may vary over time)» y que los e-procesos contrastan «forecaster A scores no better than forecaster B *on average*»;
  - el README no enuncia supuestos de acotación ni números de teoremas. Apoya la descripción general, pero **no verifica** las condiciones de los teoremas.
- **(b) Paquete de terceros `seqcomp`:** es ajeno a los autores; no es una fuente de las condiciones de los teoremas.
- **(c) Howard et al. (2021):** solo hay un fragmento de un trabajo que los cita. **No verificado.**
- **(d) Waudby-Smith y Ramdas (2024):** solo hay un fragmento de una contribución a su discusión. **No verificado.**
- **Precisión de AE-62:** estas categorías describen el acceso desde el sandbox de Claude. Otro auditor del proyecto revisó después los preprints; el registro por fuente, versión y campo está en la sección de AE-62.

**Errores demostrados, ya corregidos:**
- **E1.** La fórmula de inversión de P1b-único (`p` = menor nivel con `inf C_100 > 0`) se daba sin la hipótesis que la justifica.
  - El anidamiento de las secuencias en el nivel es una **condición suficiente** para esa fórmula; no se afirma que sea necesaria para cualquier valor p.
  - Se añade al `valor_p`.
- **E2.** A2 se describía como «`g_t ≤ 0` persistente», lo que admite `g_t ≡ 0`, y en ese caso la nula de P2 sería verdadera. Ahora dice «`g_t ≤ 0` en toda `t` de `W`, con `g_t < 0` en alguna».
- **E3.** `E_juego = min(E_LL, E_Brier)` se presentaba sin condición, aunque ninguna familia del expediente ofrece hoy e-valores válidos: P1a y P2 no los usan y los de P1b están pendientes. Se añade `CONJUNCION["por_juego_e_estado"] = "condicionado_a_e_valores_validos_por_metrica_hoy_pendientes"`.

**Precisiones:**
- **H1. Garantía conjunta frente a garantía clásica.** Nueva constante `SENTIDO_DE_LA_GARANTIA_P1B`.
  - `Δ_100` y `Δ_t` dependen de la trayectoria.
  - Con las cotas de incrementos (`|ε_t| ≤ c`) y la estructura predictible (`p_t` fijada antes del sorteo) que la familia ya exige, Azuma y la inversión dan `P(rechazo ∩ evento nulo) ≤ nivel` en cualquier ley (precisión de AE-62: Azuma, por derivación propia; la inversión, solo bajo `PREMISA_DE_LA_INVERSION`). Esa cota conjunta **no** es, por sí sola, una garantía condicional dado el evento nulo.
  - La lectura clásica solo vale para la clase de leyes en que la nula se cumple casi seguro.
  - Los `valor_p` de Azuma y de inversión remiten a esta constante.
- **H2. Construcción de L-sint.** Se define con una construcción explícita: `p_t` y `q_t` fijadas de antemano y elegidas para que la suma de `g_t` en `W` sea exactamente cero. Es una **condición suficiente** para la frontera; no se afirma que sea necesaria.
- **H3. Etiqueta [lit] de las secuencias de confianza.** Se sustituye en la sección de AE-60 por una atribución precisa: descripción general apoyada por el README de los autores de Choe–Ramdas, condiciones de los teoremas pendientes de lectura primaria, y Howard et al. sin verificación primaria.
- **H4. Nula de los e-procesos.** El README de los autores no precisa si «no better on average» se exige en todo tiempo, lo que sería una nula más fuerte que la nula sobre `T` y que la terminal. Queda como candidata **pendiente de lectura primaria**, sin cambiar ningún uso de `1/E`. Precisión de AE-62: en `arXiv:2110.00115v6`, §4.4, según la revisión de otro auditor, `H₀ʷ` exige `Δ_t ≤ 0` para todo `t ≥ 1`; las nulas del expediente son distintas y `1/E_100` y `1/sup_T E_t` siguen pendientes.

**Decisiones:**
- **D1.** Se añade la decisión humana `multiplicidad_entre_preguntas_o_familias`, sin valor.
- **D2.** La lectura primaria de Choe–Ramdas, Howard et al. y Waudby-Smith–Ramdas sigue pendiente, fuera del sandbox. Hasta entonces, sus condiciones no se usan como garantías. Precisión de AE-62: queda reducido a la decisión `lectura_primaria_pendiente_de_fuentes_secuenciales` para lo que sigue sin examinar.

**Revisado sin hallazgos:**
- las nulas de P1a, P1b-único, P1b-supervisión y P2;
- la inversión simultánea para la supervisión;
- los usos de `1/E`, todos pendientes;
- `escenarios_nulos`;
- la orientación por métrica;
- la multiplicidad entre métricas y entre juegos;
- `verificar_expediente`.

**Archivos:**
- **`propuesta_inferencia_prospectiva.py`:** E1, E2, E3, H1, H2 y D1, sin cambiar vocabularios, estados de nula, estados de `1/E`, familias, preguntas ni garantías.
- **`tests/unit/ml/test_auditoria_inferencia_prospectiva.py`:** nuevo.
- **`tests/unit/ml/test_propuesta_inferencia_prospectiva.py`:** solo la aserción del diccionario exacto de `CONJUNCION`, por E3.
- **README, ROADMAP y ARCHITECTURE:** esta sección y dos precisiones en la de AE-60 (E3 y H3).

No cambian AE-52 a AE-59 ni el catálogo de AE-56.

**Pruebas** (`11` nuevas, sintéticas):
- **Regresiones:** E1, E2, E3, H1, H2 y D1.
- **Invariantes:**
  - estados de los siete escenarios y garantías y modos de las ocho familias, idénticos a la base;
  - decisiones sin valor, estado fijo y `AUTORIZA_EVALUACION=False`;
  - textos nuevos sin aprobación ni autorización;
  - verificación de la base, constantes de AE-52/53 y `huella_diseno()` intactas.

Las regresiones se escribieron antes de corregir. Sobre la base `6ac3fdd` dieron `7 failed, 4 passed` (código de pytest `1`). La única aserción de AE-60 que cambia es el diccionario exacto de `CONJUNCION`, por E3.

**Mediciones en el sandbox Linux de Claude** (Python `3.11.15`, sin datos reales):
- **Sobre el código final:** `11 passed` (código `0`), y `69 passed` junto con las `58` de AE-60.
- **Focalizadas:** `809 passed` (código `0`): las de AE-60 más las `11` nuevas.
- **Suite completa en una única corrida:** `5043 + 11 = 5054 passed`, `0 skipped`, código `0`, con los cinco `DeprecationWarning` conocidos de Alembic.
- `pip check` y `git diff --check`: código `0`.

**Validación real del operador en Windows/Python `3.14.6` y pytest `9.1.1` -evidencia atribuida al usuario, no ejecutada por Claude**: rama `feature/ae61-auditoria-inferencia-prospectiva`, sobre la base `6ac3fddb0b4901b872657b570a6b7d8bc4532598`.
- **Parche aplicado:** el parche completo `ae61-auditoria-inferencia-prospectiva.patch`, con SHA-256 verificado `8afdf712c3ea631fd23402e9b65d74539ade3f1e14b03ff572975b282275d3cd`.
- **Comprobaciones:** `git apply --check`, la aplicación, `git apply --reverse --check` y `git diff --check` fueron correctos.
- **Archivos:** exactamente los seis esperados (ARCHITECTURE.md, README.md, ROADMAP.md, el módulo, la prueba nueva y la prueba de AE-60).
- **Pruebas de AE-61 y AE-60:** `69 passed` en `0,25 s`, código `0`.
- **Focalizadas:** `809 passed` en `17,01 s`, código `0`.
- **`pip check`:** `No broken requirements found.`, código `0`.

**En Windows no se ejecutó la suite completa.** La cifra `5054 passed, 0 skipped` corresponde únicamente al sandbox Linux de Claude (Python `3.11.15`).

**Límites de esta validación**: «validada» cubre solo **esta auditoría**, sus correcciones y precisiones (E1–E3, H1–H3, D1) y sus pruebas. Siguen **pendientes**:
- la lectura primaria de los teoremas de Choe–Ramdas, Howard et al. y Waudby-Smith–Ramdas;
- H4, la cuantificación temporal de la nula de los e-procesos;
- D2, la decisión del operador sobre esa lectura primaria;
- todos los usos de `1/E`, que siguen `pendiente_de_demostracion`.

La validación **no** aprueba pregunta, familia, α, potencia, efecto, horizonte, tratamiento de omisiones ni regla, y no autoriza ninguna evaluación operativa. El expediente sigue en `expediente_sin_eleccion` con `AUTORIZA_EVALUACION = False`.

Siguen igual:
- los siete pendientes de AE-52, abiertos;
- la especificación candidata de AE-53, sin aprobar;
- el NO-GO de AE-39 y los bloqueos de AE-41 y AE-46.

Con esta evidencia, **AE-61 queda validada como auditoría del expediente de inferencia prospectiva**; no equivale a elegir una regla ni a autorizar ninguna evaluación.

**Límites:**
- AE-61 no elige ninguna regla ni valor.
- No verifica los teoremas no leídos.
- No autoriza ninguna evaluación.

No se usaron datos reales, PostgreSQL, entrenamiento ni predicciones reales. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-60 sin cambios.

**Etapa AE-62 -verificación de fuentes primarias y condiciones inferenciales pendientes, validada:** registra, fuente por fuente y versión por versión, qué enunciados de Choe–Ramdas, Howard et al., Waudby-Smith–Ramdas y Ramdas et al. están comprobados y quién los comprobó. Los separa de lo que falta para aplicarlos a este repositorio y corrige las afirmaciones de AE-60/AE-61 que no hacían esa separación.

**No** elige pregunta, familia, α, potencia, efecto, horizonte, multiplicidad, omisiones ni regla. Todos los usos de `1/E` siguen como `pendiente_de_demostracion`.

**Acceso del sandbox frente a verificación del proyecto.**
- Desde el sandbox de Claude están bloqueados arXiv, Project Euclid, INFORMS, OUP, la RSS, NSF-PAR y los sitios de los autores. **Claude no leyó ningún PDF.**
- **Otro auditor del proyecto** abrió los preprints primarios. Sus hallazgos se registran **atribuidos a esa revisión y a la versión indicada**.
- Claude solo consultó material no primario, que se registra aparte (`MATERIAL_NO_PRIMARIO_CONSULTADO`) y **no completa ningún campo**:
  - README y código de `yjchoe/ComparingForecasters@52748c86e0429a9612dc79892c3be6156a524132`;
  - README de `gostevehoward/confseq@5ffe733ca2447a2e28c2c91f3b00086173f2ab2c`;
  - README de `WannabeSmith/betting-paper-simulations@cb05eef4d49336f114cff15f39bcaca74996843f`;
  - el paquete de terceros `seqcomp`, que no se usa.

**Estados por campo** (`ESTADOS_VERIFICACION_FUENTE`):
- **(a) `enunciado_comprobado_en_preprint_identificado`:** comprobado en un preprint identificado por la revisión atribuida.
- **(b) `aplicacion_al_repositorio_sin_verificar`:** falta demostrar que se aplica con las métricas, cotas, filtración, predicciones, omisiones y nulas del repositorio.
- **(c) `texto_no_examinado`:** nadie en el proyecto lo ha contrastado. No se completa por analogía.

Cada fuente registra diez campos (`CAMPOS_VERIFICACION_TEOREMA`). Ningún `trasladable_al_contrato` está en (a).

**Registro** (`VERIFICACION_FUENTES_SECUENCIALES`):
- **Choe y Ramdas, *Comparing Sequential Forecasters*, `arXiv:2110.00115v6`.** Versión y contenido, según la revisión del preprint por el otro auditor. Nueve campos en (a):
  - **Secciones y teoremas:** §4.2 distingue la filtración observable F de la filtración G, que incluye la información previa al resultado.
  - **Teorema 1** (p. 13 del PDF): cobertura simultánea para la media condicional variable `Δ_t`, con diferenciales condicionalmente subgaussianos.
  - **Teorema 2** (p. 14): secuencia empírica de Bernstein, con diferenciales acotados y secuencia auxiliar predecible. Se identifica como extensión del teorema 4 de Howard et al.
  - **Garantía de ambos:** `P(∀t ≥ 1: Δ_t ∈ C_t) ≥ 1 − α` bajo sus condiciones.
  - **Log Loss:** la fuente advierte que **su** puntuación logarítmica sin truncar es no acotada y que truncarla altera su propiedad de ser estrictamente propia. Precisión de AE-64: en el PDF v6, leído por Claude a partir del archivo aportado por el operador, la truncada «is no longer proper» (p. 13) y es «improper» (p. 14): deja de ser propia, no solo estrictamente propia. Se conserva la atribución de este campo a la revisión externa (`DISCREPANCIAS`).
  - **§4.4:** `H₀ʷ` exige `Δ_t ≤ 0` **para todo `t ≥ 1`**; el teorema 3 construye un e-proceso para `H₀ʷ` bajo las condiciones del teorema 2.
  - **`trasladable_al_contrato` en (b):** falta demostrar que las métricas, cotas, filtración, anterioridad de `p_t` y omisiones del repositorio cumplen esas condiciones.
  - El Log Loss del repositorio recorta las probabilidades con `EPSILON_CLIP` (`metricas.py`). Está **por comprobar** su relación con el truncamiento que describe la fuente, la cota que resulta y su propiedad de ser propia; no se afirma ninguna consecuencia. Precisión de AE-63: la cota y la propiedad quedan resueltas en el dominio declarado del contrato (acotación demostrada; propia para verdades reportables `q ∈ (0, 1)`; estrictamente propia solo con `q` y reporte en `[ε, 1−ε]`); la relación con el truncamiento de la fuente sigue pendiente, y si las marginales reales están en ese intervalo sigue pendiente de evidencia sobre el mecanismo o de una hipótesis declarada y justificada. Precisión de AE-64: la relación con el truncamiento de la fuente queda resuelta: no son equivalentes (contraejemplo exacto; C4 refutada) y la equivalencia no es requisito de validez, que depende solo de la acotación. Las marginales reales siguen pendientes.
  - `H₀ʷ` no es la nula terminal ni la nula sobre `T`.
- **Howard, Ramdas, McAuliffe y Sekhon, `arXiv:1810.08240v9`.** Versión identificada por el otro auditor en la ficha original de arXiv.
  - `fuente_y_version` en (a); los otros nueve campos en (c).
  - El teorema 4 no tuvo revisión específica: conocer la versión no demuestra sus condiciones.
- **Waudby-Smith y Ramdas, *Estimating means of bounded random variables by betting*, `arXiv:2010.09686v7`.** Versión identificada en la ficha original; contenido según la revisión externa.
  - **En (a):** versión, secciones y medias condicionales. La §2 define el modelo básico con `E[X_t | F_{t−1}] = μ` constante, condición que la proposición 2 hace explícita. El modelo de muestreo sin reemplazo tiene media condicional variable determinada por su diseño.
  - **`trasladable_al_contrato` en (b):** la exclusión se limita a la familia concreta de AE-60. No se afirma que toda apuesta exija una media común, y no se examinó si otras variantes son aplicables.
  - Los demás campos en (c).
- **Ramdas, Grünwald, Vovk y Shafer, `arXiv:2210.01948v2`.** Versión identificada por el otro auditor en la ficha original, sin revisión de contenido.
  - `fuente_y_version` en (a); los otros nueve campos en (c), sin completarlos por analogía.
- **Versiones publicadas** (`REFERENCIAS`): sin revisión de contenido.

**Hallazgos y correcciones:**
- **F1. Registro por fuente, versión y campo.** Es el registro anterior, con la atribución de cada campo.
- **F2. Cobertura simultánea.** El `valor_p` de la secuencia de confianza la presentaba como hecho («como P(…) ≤ nivel»).
  - Ahora dice «si se cumplen las condiciones de un teorema de cobertura simultánea (`PREMISA_DE_LA_INVERSION`)».
  - La nueva constante `PREMISA_DE_LA_INVERSION` recoge el enunciado atribuido a los teoremas 1–2 de v6, sus condiciones y lo que falta demostrar para el repositorio.
- **F3. Azuma frente a inversión.**
  - **Azuma** es una derivación propia, con `|ε_t| ≤ c` y `p_t` fijada antes del sorteo. No cambia.
  - **La inversión** (supervisión y `C_100`) solo da la garantía conjunta bajo `PREMISA_DE_LA_INVERSION`. El `valor_p` lo dice, y el docstring de `SENTIDO_DE_LA_GARANTIA_P1B` separa ambas premisas; su diccionario no cambia.
- **F4. H4 identificado para ese teorema y esa versión.** Las nulas del expediente (la terminal `Δ_100 ≤ 0` y la nula sobre `T`) son distintas de `H₀ʷ` y contienen más leyes. `1/E_100` y `1/sup_T E_t` siguen **pendientes de demostración**.
  - **Contraejemplo exacto de dos pasos** (derivación propia):
    - con `d_t ∈ [−1, 1]`, `E_1 = 1 + d_1` y `E_2 = E_1` es una supermartingala no negativa bajo la nula fuerte `Σ_{s≤t} g_s ≤ 0` (`t = 1, 2`);
    - bajo la ley con `P(d_1 = 1) = 3/4` y `P(d_2 = 1 | F_1) = 1/4` se tiene `g_1 = 1/2`, `g_2 = −1/2`, `Δ_2 = 0` y `E[E_2] = 3/2`;
    - con `p = min(1, 1/E_2)` y la convención `p = 1` en el evento `E_2 = 0`, en el evento `E_2 = 2` se obtiene `p = 1/2`, y `P(p ≤ 1/2) = 3/4 > 1/2`;
    - con `T = {1, 2}`, esa ley viola la nula sobre `T`.
  - Demuestra la **falta de traslado automático** desde una nula más fuerte. **No refuta el teorema 3.**
- **F5. Decisiones nuevas, sin valor:**
  - las inferenciales `validez_de_1_sobre_sup_e_contra_la_nula_sobre_T` y `aplicacion_de_condiciones_de_cobertura_al_repositorio`;
  - la humana `lectura_primaria_pendiente_de_fuentes_secuenciales`.
- **F6. Familia de apuesta.** Su `valor_p` precisa que la exclusión afecta a **esta familia concreta** (modelo básico de media constante) y que no se afirma que toda apuesta exija una media común. `media`, `aplicable_a_p1b` y `preguntas` no cambian.
- **F7. Precisiones en AE-60 y AE-61**, marcadas «precisión de AE-62».

**Clasificación:**
- **(a) Comprobado en un preprint identificado** (revisión externa):
  - Choe–Ramdas v6: §4.2; teoremas 1–3; advertencia sobre el Log Loss truncado; `H₀ʷ` para todo `t ≥ 1`; vínculo con el teorema 4 de Howard.
  - Waudby-Smith–Ramdas v7: §2, proposición 2 y modelo sin reemplazo.
  - Las cuatro versiones.
- **Derivación propia:** la cota de Azuma; la inversión condicionada a `PREMISA_DE_LA_INVERSION`; el contraejemplo F4.
- **(b) Aplicación sin verificar:**
  - las condiciones de los teoremas 1–2 con las métricas del repositorio (incluidos `EPSILON_CLIP` y Brier), las cotas, la filtración, la anterioridad sin sellado y las omisiones;
  - `1/E_100` y `1/sup_T E_t` bajo las nulas del expediente;
  - la exclusión de la apuesta, limitada a la familia concreta.
- **Incompatible con el contrato:**
  - secuencias, e-procesos o supervisión con menos de 100 resueltos (AE-52);
  - usar `H₀ʷ` como si fuera la terminal o la nula sobre `T`;
  - la familia concreta de apuesta de media constante con `g_t` variable.
- **(c) No examinado:**
  - de Howard v9, todo salvo la versión;
  - de Waudby-Smith–Ramdas v7, los campos no citados;
  - de Ramdas et al. v2, todo salvo la versión;
  - las versiones publicadas.

**Archivos:**
- **`propuesta_inferencia_prospectiva.py`:** el registro, el material no primario, `PREMISA_DE_LA_INVERSION`, los textos de F2, F3 y F6 y las decisiones de F5. No cambian vocabularios, estados, familias, preguntas, garantías, medias, modos, usos de `1/E`, `SENTIDO_DE_LA_GARANTIA_P1B` ni `REFERENCIAS`.
- **`tests/unit/ml/test_verificacion_fuentes_inferencia.py`:** nuevo.
- **README, ROADMAP y ARCHITECTURE:** esta sección y las precisiones de F7.

No cambian las pruebas de AE-60 y AE-61, AE-52 a AE-59 ni el catálogo de AE-56.

**Pruebas** (`16` nuevas, sintéticas):
- **Regresiones:**
  - estados y campos;
  - registro por fuente, versión y revisión;
  - Choe–Ramdas v6, con `EPSILON_CLIP` solo en el traslado;
  - Howard v9 y Ramdas et al. v2: versión en (a) y los otros nueve campos en (c);
  - Waudby-Smith–Ramdas v7;
  - ningún traslado comprobado;
  - premisa y `valor_p` condicional;
  - apuesta concreta;
  - decisiones nuevas;
  - textos sin aprobación.
- **Invariantes:**
  - Azuma y `SENTIDO_DE_LA_GARANTIA_P1B` idénticos a la base;
  - familias, usos de `1/E` y escenarios sin cambios;
  - estado, bloqueos, constantes de AE-52/53 y `huella_diseno()` intactos.
- **Derivación:** el contraejemplo F4, con aritmética exacta (`fractions.Fraction`).

Las regresiones se escribieron antes de corregir. Sobre la base `805209e` dieron `12 failed, 4 passed` (código de pytest `1`). El plan preveía 13 fallos: `test_azuma_separada_de_la_inversion` ya pasaba sobre la base porque comprueba que Azuma y `SENTIDO_DE_LA_GARANTIA_P1B` sigan idénticos a ella; es un invariante, no una regresión.

**Mediciones en el sandbox Linux de Claude** (Python `3.11.15`, sin datos reales):
- **Sobre el código final:** `16 passed` (código `0`), y `85 passed` junto con las `11` de AE-61 y las `58` de AE-60, sin cambiar ninguna de ellas.
- **Focalizadas:** `809 + 16 = 825 passed` (código `0`).
- **Suite completa en una única corrida:** `5054 + 16 = 5070 passed`, `0 skipped`, código `0`, con los cinco `DeprecationWarning` conocidos de Alembic.
- `pip check` y `git diff --check`: código `0`.

**Validación real del operador en Windows/Python `3.14.6` y pytest `9.1.1` -evidencia atribuida al usuario, no ejecutada por Claude**: en `C:\GitHub\loteria-predictor-update\backend`, rama `feature/ae62-verificacion-fuentes-inferencia`, sobre la base `805209e21e40e306255af65ba36e66e3fd37a836`.
- **Parche aplicado:** el parche completo `ae62-verificacion-fuentes-inferencia.patch`, con SHA-256 verificado `42659a83f17336868d159ddff06ea89940a5756e0e7237099b08c251b0344183`.
- **Comprobaciones:** `git apply --check`, la aplicación, `git apply --reverse --check` y `git diff --check` terminaron correctamente.
- **Archivos:** exactamente los cinco previstos (ARCHITECTURE.md, README.md, ROADMAP.md, el módulo y la prueba nueva).
- **Pruebas de AE-62, AE-61 y AE-60 juntas:** `85 passed` en `1,28 s`, código `0`.
- **Focalizadas:** `825 passed` en `30,73 s`, código `0`.
- **`python -m pip check`:** `No broken requirements found`, código `0`.

**En Windows no se ejecutó la suite completa.** La cifra `5070 passed, 0 skipped` corresponde únicamente al sandbox Linux de Claude (Python `3.11.15`).

**Límites de esta validación**: «validada» cubre solo el **registro preparatorio** de fuentes, sus precisiones y sus pruebas.
- **No** demuestra que las condiciones de los teoremas se apliquen a este repositorio: métricas (incluido `EPSILON_CLIP`), cotas, filtración, anterioridad y omisiones siguen en `aplicacion_al_repositorio_sin_verificar`.
- **No** aprueba ninguna inferencia ni elige pregunta, familia, α, potencia, efecto, horizonte, multiplicidad, omisiones ni regla, y no autoriza ninguna evaluación.
- Todos los usos de `1/E` (`1/E_100` y `1/sup_T E_t`) siguen `pendiente_de_demostracion`. Las decisiones siguen sin valor. El expediente sigue en `expediente_sin_eleccion` con `AUTORIZA_EVALUACION = False`.
- Los enunciados en `enunciado_comprobado_en_preprint_identificado` siguen atribuidos a la revisión del otro auditor. Los campos en `texto_no_examinado` (Howard et al. v9 salvo la versión, Ramdas et al. v2 salvo la versión, los no citados de Waudby-Smith–Ramdas v7 y las versiones publicadas) siguen sin examinar.

Siguen igual:
- los siete pendientes de AE-52, abiertos;
- la especificación candidata de AE-53, sin aprobar;
- el NO-GO de AE-39 y los bloqueos de AE-41 y AE-46.

Con esta evidencia, **AE-62 queda validada como registro preparatorio de verificación de fuentes**; no equivale a demostrar la aplicación de los teoremas ni a aprobar una inferencia.

**Límites:**
- AE-62 no verifica por sí misma ningún teorema: los enunciados en (a) dependen de la revisión externa atribuida.
- No demuestra la aplicación al repositorio ni valida ningún uso de `1/E`.
- No elige ninguna regla ni valor y no autoriza ninguna evaluación.
- `ESTADO_EXPEDIENTE` sigue en `expediente_sin_eleccion` y `AUTORIZA_EVALUACION = False`.

No se usaron datos reales, PostgreSQL, entrenamiento ni predicciones reales. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-61 sin cambios.

**Etapa AE-63 -traslado de condiciones inferenciales al contrato del repositorio, validada:** AE-62 dejó el traslado de las fuentes al contrato en `aplicacion_al_repositorio_sin_verificar`. AE-63 audita, condición por condición, si las hipótesis se cumplen en el contrato concreto y clasifica cada una como **demostrada** (derivación propia sobre el código), **refutada** (contraejemplo exacto) o **pendiente** (falta un enunciado exacto de la fuente o una decisión del operador).

**Ninguna condición global de traslado queda demostrada.** Una garantía bajo una nula más fuerte (`H₀ʷ` para todo `t ≥ 1`) no se convierte en garantía para P1b. Todos los usos de `1/E` siguen `pendiente_de_demostracion`.

El registro está en el nuevo módulo puro `app/application/ml/traslado_condiciones_inferenciales.py`. No modifica ningún archivo validado.

**Dominio del contrato** (`DOMINIO_DEL_CONTRATO`):
- **Reportes:** `metricas_por_sorteo` exige 43 probabilidades `float` finitas en el intervalo abierto `(0, 1)` y **no impone ninguna restricción conjunta**: ni suma fija ni normalización.
  - Se aceptaron, por ejemplo, 43 valores `1e−9` (suma `4,3e−8`), 43 valores `1−1e−9` (suma `43 − 4,3e−8`, próxima a 43 y menor que 43) y cinco en `1e−9` con 38 en `1−1e−9` (suma `38 − 3,3e−8`).
  - Los extremos citados como «alcanzables» lo son en este dominio. Una restricción como `Σ p_i = 5` sería una decisión del operador y los cambiaría.
- **Resultados:** 5 números distintos en `1..43`. Las marginales reales `q_i` están en `[0, 1]` y suman 5; esa restricción afecta a `q`, no a los reportes.
- **Desempate del Top-5:** probabilidad descendente y número ascendente. La uniforme empata y elige `1..5`.

**Hallazgos** (`CONDICIONES_DE_TRASLADO`):
- **Log Loss:**
  - **Acotación, demostrada:** `d_t^LL ∈ [LL_u + log ε, LL_u + log(1−ε)] = [−13,4560654104, 0,359444147512]`, de ancho `log((1−ε)/ε) ≈ 13,8155`, con `ε = EPSILON_CLIP = 1e−6` y `LL_u = 0,359445147513`.
  - **Propia para verdades reportables `q ∈ (0, 1)`, demostrada:** el reporte veraz `p = q` es admisible y alcanza el óptimo.
  - **Verdades de frontera `q ∈ {0, 1}`, demostrado:** no hay reporte veraz admisible, porque `p = q` está fuera del dominio `(0, 1)`. El mínimo de la pérdida esperada, `−log(1−ε)`, se alcanza mediante el recorte, y los minimizadores admisibles son exactamente `0 < p ≤ ε` (si `q = 0`) y `1−ε ≤ p < 1` (si `q = 1`); `p = 0` y `p = 1` quedan fuera del dominio `(0, 1)`.
  - **Estrictamente propia en todo el dominio de verdades reportables, refutada:** con `q = 1e−7`, los reportes `1e−7` y `1e−8` tienen la misma pérdida esperada.
  - **Estrictamente propia relativa a `D`, demostrada**, donde `D` exige que **tanto** `q` **como** el reporte estén en `[ε, 1−ε]`. Restringir solo los reportes no basta: con `q < ε`, el óptimo es `ε`.
  - **Si las marginales reales `q_i` están en ese intervalo: pendiente de evidencia sobre el mecanismo de sorteo (P3) o de una hipótesis declarada y justificada.** Es una cuestión distinta de la decisión sobre reportes: `rango_admisible_de_probabilidades_de_la_estrategia` solo restringe los reportes y no es evidencia sobre las `q_i` (`ALCANCE_DE_LA_DECISION_SOBRE_REPORTES`).
- **Brier:**
  - **Acotación, demostrada:** `d_t^B` en el intervalo abierto `(B_u − 1, B_u)`, con `B_u = 0,102758247701` y ancho supremo 1. El intervalo abierto describe los **valores matemáticos ideales**: `diferencias["brier_score"]`, calculado en coma flotante, puede coincidir numéricamente con un extremo por redondeo. Por ejemplo, con reportes a `1e−9` del extremo, la distancia ideal al supremo es `1e−18`, menor que media ulp de `B_u` (≈ `1,39e−17`).
  - **Estrictamente propia con `q ∈ (0, 1)`, demostrada:** `E[(p−Y)²] = (p−q)² + q(1−q)`. Con `q ∈ {0, 1}`, el ínfimo no se alcanza en el dominio abierto.
- **P@5** (secundaria, ganancia):
  - **Acotación, demostrada:** `d_t ∈ [−1, 1]`, con ambos extremos alcanzables.
  - **Propia no estricta, demostrada:** `E[P@5(A)] = (1/5) Σ_{i∈A} q_i`. Por intercambio, cinco marginales máximas maximizan esa suma, y el Top-5 del reporte veraz las toma, porque el desempate solo elige entre marginales iguales.
  - **Estricta, refutada:** otro reporte con el mismo Top-5 obtiene la misma esperanza.
  - **Aplicabilidad de los teoremas de Choe–Ramdas a P@5:** cuestión distinta, **pendiente**.
- **Signo de `d_t`:** uniforme − estrategia en las tres métricas, **demostrado en el código**. La correspondencia con el signo de la fuente queda **pendiente**.
- **Cotas de incrementos, demostradas:** `|ε_t| ≤` ancho de `d_t`, es decir `≈ 13,8155` (LL), 1 (Brier) y 2 (P@5). Son anchos derivados, **no** el valor de la decisión `cota`.
- **Subgaussianidad por acotación, demostrada:** lema de Hoeffding, derivación estándar. Su correspondencia con el teorema 1 queda **pendiente**.
- **Filtración y anterioridad, pendientes:** la cadena de hashes no acredita la fecha, el sellado externo sigue pendiente y la correspondencia de la filtración G tampoco está establecida.
- **Nulas:**
  - el traslado automático desde `H₀ʷ` queda **refutado** (contraejemplo de AE-62);
  - la inversión para P1b solo vale bajo `PREMISA_DE_LA_INVERSION` y queda **pendiente**;
  - `1/E_100` y `1/sup_T E_t` siguen **pendientes**.
- **Omisiones:**
  - omisión predecible (`I_t` medible en `F_{t−1}`): conserva la estructura de martingala, **demostrada**;
  - omisión dependiente del resultado: **refutada** (contraejemplo exacto);
  - tratamiento aplicable y tiempos `T`: **pendientes**.

**Precisión de AE-64:** los seis enunciados siguientes se leyeron en el PDF v6 (sección de AE-64). Con esa lectura, `ESTADOS_TRAS_AE64` deriva: C1, C2, C3 y C5 demostradas; C4 (equivalencia con `EPSILON_CLIP`) refutada, sin ser requisito de cobertura; F2, N2 y U1 pendientes. El texto de N2 remite ahora a `DEPENDENCIAS_DE_N2`, desglosadas por vía inferencial, métrica, interpretación y requisitos operativos. `CONDICIONES_DE_TRASLADO` conserva sus estados.

**Enunciados primarios necesarios** (`ENUNCIADOS_DE_FUENTE_NECESARIOS`, `arXiv:2110.00115v6`, ausentes del registro de AE-62):
1. la hipótesis exacta de acotación del teorema 2;
2. la parametrización subgaussiana del teorema 1;
3. la definición y el signo de los diferenciales y de `Δ_t`;
4. la filtración G y la predictibilidad;
5. la fórmula del truncamiento logarítmico;
6. si los teoremas exigen una regla de puntuación de probabilidades o cualquier diferencial acotado.

**Decisiones del operador** (`DECISIONES_DEL_OPERADOR_AE63`, todas sin valor):
- `cota`;
- `rango_admisible_de_probabilidades_de_la_estrategia`, la única nueva: solo restringe los reportes; no es evidencia sobre las marginales reales `q_i`, que siguen pendientes;
- `tratamiento_de_omisiones` y `mecanismo_de_sellado_temporal_externo`;
- `lectura_primaria_pendiente_de_fuentes_secuenciales`;
- `papel_y_direccion_de_la_secundaria` y `tiempos_supervision`.

**Archivos:**
- nuevo `app/application/ml/traslado_condiciones_inferenciales.py`;
- nuevo `tests/unit/ml/test_traslado_condiciones_inferenciales.py`;
- README, ROADMAP y ARCHITECTURE: esta sección y una precisión en la de AE-62.

No cambian el expediente (`propuesta_inferencia_prospectiva.py`), el registro de AE-62, `metricas.py` ni las pruebas anteriores.

**Pruebas** (`20` nuevas, sintéticas):
- **Regresiones:**
  - dominio sin restricción conjunta;
  - intervalos de LL, Brier y P@5, comparados con `metricas_por_sorteo` en entradas extremas. En Brier, la comparación estricta usa reportes a `1e−5` del extremo, con una distancia representable (`1e−10` al supremo), y la distinción entre valores ideales y valores en coma flotante tiene su propia prueba;
  - cota de incrementos;
  - propiedad de LL (propia para `q ∈ (0, 1)`, no estricta en ese dominio, estricta en `D`), verdades de frontera `q ∈ {0, 1}` sin reporte veraz admisible, separación entre la decisión sobre reportes y las marginales reales, y propiedad de Brier y de P@5. Para P@5 se usan marginales factibles, con `0 < q_i < 1` y `Σ q_i = 5`, construidas como mezcla de una componente uniforme y dos sorteos fijos; la prueba cubre el orden y el empate del quinto puesto;
  - signo de `d_t`;
  - omisiones;
  - clasificación de las condiciones;
  - símbolos citados que existen;
  - nulas y `1/E`;
  - decisiones y vocabulario.
- **Invariante:** estado, bloqueos, AE-52/53, `huella_diseno()` y el registro de AE-62 intactos.

**v1** (parche `ae63-traslado-condiciones-inferenciales.patch`, SHA-256 `43c229c4947fd5aa5f3a5f8b48d63d98cbc97c21b52a860b89fbb961d7af2f01`). Las regresiones se escribieron antes del módulo. Sobre la base `ef5250d` dieron `16 failed, 1 passed` (código de pytest `1`): las 16 regresiones fallan por separado con `ModuleNotFoundError` y el invariante pasa. Durante la implementación, la prueba de vocabulario detectó «aprobada» en la condición de omisiones; el texto pasó a «sin aprobar».

**Mediciones de v1 en el sandbox Linux de Claude** (Python `3.11.15`, sin datos reales):
- **Sobre el código de v1:** `17 passed` (código `0`), y `102 passed` junto con las `16` de AE-62, las `11` de AE-61 y las `58` de AE-60.
- **Focalizadas:** `825 + 17 = 842 passed` (código `0`).
- **Suite completa en una única corrida:** `5070 + 17 = 5087 passed`, `0 skipped`, código `0`, con los cinco `DeprecationWarning` conocidos de Alembic.
- `pip check` y `git diff --check`: código `0`.

**v2** (dos precisiones de dominio tras la auditoría del operador):
- `L2_log_loss_propia` se limita a verdades reportables `q ∈ (0, 1)`, y la nueva `L2_log_loss_verdades_de_frontera` describe `q ∈ {0, 1}` sin llamar veraz a un reporte prohibido.
- `L2_marginales_reales_en_el_intervalo` pasa a exigir evidencia sobre el mecanismo o una hipótesis declarada y justificada (nuevo sustento `requiere_evidencia_o_hipotesis_declarada`), sin la decisión sobre reportes, cuyo alcance fija `ALCANCE_DE_LA_DECISION_SOBRE_REPORTES`.

Las regresiones de v2 se escribieron antes de corregir. Contra el módulo de v1 dieron `5 failed, 14 passed` (código de pytest `1`).

**Mediciones de v2 en el sandbox Linux de Claude:**
- **Nuevas:** `19 passed` (código `0`).
- **Junto con AE-62, AE-61 y AE-60:** `104 passed` (código `0`).
- `git diff --check`: código `0`.
- **No se repitieron** la suite completa ni las focalizadas: v2 solo cambia textos del registro, un vocabulario, las pruebas nuevas y la documentación. Las cifras de suite y focalizadas son las de v1.

**v3** (parche v2 previo: SHA-256 `5bc3b90db33e067a8916d66c55c725ff2c3623616567df9f7cf1d4c19b9ae457`). Precisa `L2_log_loss_verdades_de_frontera`: los minimizadores admisibles son exactamente `0 < p ≤ ε` (`q = 0`) y `1−ε ≤ p < 1` (`q = 1`), con los extremos `p = 0` y `p = 1` excluidos del dominio `(0, 1)`. El mínimo se alcanza mediante el recorte.

La regresión ajustada (`test_log_loss_verdades_de_frontera_sin_reporte_veraz`) comprueba que el contrato rechaza `p = 0` y `p = 1`, el valor de la pérdida en los minimizadores, los extremos abiertos mediante `math.nextafter` y el recorte, y el texto exacto. Contra el módulo de v2 dio `1 failed, 18 passed` (código de pytest `1`).

**Mediciones de v3 en el sandbox Linux de Claude:**
- **Nuevas:** `19 passed` (código `0`).
- **Junto con AE-62, AE-61 y AE-60:** `104 passed` (código `0`).
- `git diff --check`: código `0`.
- **No se repitieron** la suite completa ni las focalizadas: v3 solo cambia un texto del registro, una prueba y la documentación. Las cifras de suite y focalizadas siguen siendo las de v1.

**Validación de v3 en Windows** (operador, Python `3.14.6`, pytest `9.1.1`; parche v3 con SHA-256 `936e55de22e5e40740a96a1a919ae5c68dbaf17bd3dd2204f821fd35e056c191`):
- **Aplicación correcta:** `git apply --check`, aplicación, `--reverse --check` y `git diff --check`, con los cinco archivos esperados.
- **Pruebas de AE-63: `1 failed, 18 passed`.** Falló `test_intervalo_brier_abierto_y_supremos`: con reportes `1−1e−9` y `1e−9`, la diferencia calculada y el supremo coincidieron en `0.10275824770146025`, y la prueba exigía una desigualdad estricta.
- **No se ejecutaron** las focalizadas ni `pip check`.
- **No es una validación superada.**

**v4.** Corrige la prueba sin debilitar la afirmación matemática:
- **Causa:** la distancia ideal `1e−18` es menor que media ulp de `B_u`, así que el valor en coma flotante puede redondearse al extremo.
- **Por qué pasó en Linux:** en Linux la prueba pasó por un margen accidental. El supremo en forma cerrada (`0.10275824770146025`) quedó unas 17 ulp por encima de la suma de 43 términos de `metricas_por_sorteo` (`0.10275824770146001`), a la que la diferencia se redondea.
- **Comparación estricta:** ahora usa reportes a `1e−5` del extremo (distancia `1e−10`).
- **Caso con `1e−9`:** solo se exige cercanía dentro del error de redondeo.
- **Texto:** `intervalo_diferencia_brier` y `B1_acotacion_brier` distinguen los valores matemáticos ideales de los calculados en coma flotante.

La regresión nueva (`test_brier_distingue_valores_ideales_de_coma_flotante`) dio, contra el módulo de v3, `1 failed, 19 passed` (código de pytest `1`). La prueba numérica ajustada también pasa en Linux con v3; el fallo de Windows no se reproduce en Linux.

**Mediciones de v4 en el sandbox Linux de Claude:**
- **Nuevas:** `20 passed` (código `0`).
- **Junto con AE-62, AE-61 y AE-60:** `105 passed` (código `0`).
- `git diff --check`: código `0`.
- **No se repitieron** la suite completa ni las focalizadas: v4 no cambia el código de producción que calcula métricas, solo un docstring y un texto del registro, las pruebas nuevas y la documentación. Las cifras de suite y focalizadas siguen siendo las de v1.

**Validación real del operador en Windows con v4** (Python `3.14.6`, pytest `9.1.1`; evidencia atribuida al usuario, no ejecutada por Claude): rama `feature/ae63-traslado-condiciones-inferenciales`, base `ef5250dc3b8832e5b60417c9df5d31a722d2de05`.
- **Parche:** el completo v4 `ae63-traslado-condiciones-inferenciales-v4.patch`, con SHA-256 verificado `9c44b6cb56a6d298ea5a643d732f5e6f846cf448e4e7ee4031c0e650994e0ff9`.
- **Aplicación:** se revirtió exactamente v3 y el árbol quedó limpio. `git apply --check`, la aplicación de v4, `git apply --reverse --check` y `git diff --check` fueron correctos, con exactamente los cinco archivos esperados.
- **Pruebas de AE-63:** `20 passed` en `0,36 s`.
- **Focalizadas:** `845 passed` en `30,58 s`.
- **`pip check`:** `No broken requirements found`.

**En Windows no se ejecutó la suite completa.** La cifra `5087 passed, 0 skipped` corresponde únicamente a la corrida de v1 en el sandbox Linux de Claude. Las pruebas de v4 en Linux fueron `20` nuevas y `105` junto con AE-60 a AE-62.

**Antecedente:** el fallo de v3 en Windows (`1 failed, 18 passed`, descrito arriba) queda registrado como tal. El resultado aprobado es el de v4.

**Límites de esta validación**: «validada» cubre solo **esta auditoría del traslado**, sus condiciones y sus pruebas.
- **No** demuestra que los teoremas de las fuentes sean aplicables al repositorio.
- **No** aprueba ninguna inferencia ni evaluación operativa.
- Siguen pendientes los enunciados exactos de las fuentes (`ENUNCIADOS_DE_FUENTE_NECESARIOS`), si las marginales reales están en `[ε, 1−ε]`, la anterioridad, el tratamiento de omisiones y todos los usos de `1/E` (`pendiente_de_demostracion`).
- Las decisiones siguen sin valor. El expediente sigue en `expediente_sin_eleccion` con `AUTORIZA_EVALUACION = False`.

Siguen igual:
- los siete pendientes de AE-52, abiertos;
- la especificación candidata de AE-53, sin aprobar;
- el NO-GO de AE-39 y los bloqueos de AE-41 y AE-46.

Con esta evidencia, **AE-63 queda validada como auditoría del traslado de condiciones inferenciales**; no equivale a demostrar el traslado ni a aprobar una inferencia.

La validación del operador en Windows/Python `3.14.6` ya se realizó con v4 (descrita arriba); corrección de AE-64 a una frase obsoleta.

**Límites:**
- AE-63 no demuestra el traslado de ningún teorema al contrato.
- No valida ningún uso de `1/E`.
- No fija ninguna decisión, no elige pregunta, familia ni regla y no autoriza ninguna evaluación.
- `ESTADO_EXPEDIENTE` sigue en `expediente_sin_eleccion` y `AUTORIZA_EVALUACION = False`.

No se usaron datos reales, PostgreSQL, entrenamiento ni predicciones reales. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-62 sin cambios.

**Etapa AE-64 -verificación primaria de los enunciados inferenciales pendientes en Choe–Ramdas v6, validada:** AE-63 dejó seis enunciados de la fuente por verificar (`ENUNCIADOS_DE_FUENTE_NECESARIOS`). AE-64 los lee en el PDF de `arXiv:2110.00115v6` aportado por el operador y los registra en el nuevo módulo puro `app/application/ml/verificacion_primaria_choe_ramdas.py`, separando tres clases:
1. **Lo que afirma el artículo** (`el_articulo_afirma`), con página y teorema, ecuación o sección.
2. **Derivaciones propias** (`derivacion_propia`) sobre el código o sobre los enunciados. No se atribuyen al artículo.
3. **Aplicación al repositorio** (`aplicacion_al_repositorio`): condiciones cuya aplicación a este repositorio sigue sin verificarse o exige una decisión.

También separa el **enunciado de la fuente verificado** (`ESTADOS_ENUNCIADO`: `verificado_en_pdf_v6`, `discrepancia_con_registro_previo`, `no_encontrado_en_v6`) de la **hipótesis satisfecha en el repositorio** (`ESTADOS_HIPOTESIS`: `demostrada`, `refutada`, `pendiente`).

**No** elige pregunta, familia, cota, λ, α ni regla, y no autoriza ninguna evaluación. Todos los usos de `1/E` siguen `pendiente_de_demostracion`.

**Procedencia del texto primario** (`PROCEDENCIA_V6`):
- **Archivo:** PDF aportado por el operador, de `6 089 652` bytes y 61 páginas, con SHA-256 `fd87e23a30c6657fd8dd272f671d0bd8a3aa469f5aafbec85a00bb9501764286`. **No** se añade al repositorio.
- **Versión, comprobada en el propio archivo:** la p. 1 lleva el sello «arXiv:2110.00115v6 [stat.ME] 9 Nov 2023» y la portada, la fecha «November 10, 2023».
- **Método:** extracción de texto propia (flujos Flate, flujos de objetos y mapas ToUnicode) y comprobación visual, en páginas renderizadas fuera del repositorio, de los símbolos que la extracción separaba. Páginas comprobadas: 1, 8, 9, 10, 11, 13, 14, 16, 17, 18, 26, 32, 33, 34, 47, 48, 50 y 51. Los 29 enunciados citados llevan comprobación visual.
- **HTML de v6:** no consultado, porque arXiv está bloqueado desde el sandbox. No se le atribuye nada ni se evalúan discrepancias entre PDF y HTML.
- **Coincidencia byte a byte con el archivo de arXiv:** no comprobable desde el sandbox. La versión queda acreditada por el sello impreso.

**Lectura por punto** (`LECTURA_POR_PUNTO`: 23 enunciados y 16 hipótesis; de ellas, 12 de derivación propia, 11 demostradas y 1 refutada, y 4 de aplicación al repositorio, todas pendientes):
1. **Acotación del teorema 2.**
   - **El artículo afirma:**
     - teorema 2 (p. 14, ec. 15): si `|δ̂_i| ≤ c/2` para todo `i ≥ 1`, con `c ∈ (0, ∞)`, y `V̂_t = Σ (δ̂_i − γ_i)²`, con `γ_i` predecible respecto de G y valores en `[−c/2, c/2]`, entonces `C^EB_t = Δ̂_t ± u(V̂_t)/t` es una `(1−α)`-CS para `Δ_t`;
     - F.2 (p. 48, ec. 103): la cota es una constante fija; con la proposición 7 (p. 50, ec. 108–111) se admiten cotas predecibles `c_i`;
     - la proposición 1 (p. 32, ec. 27–32) da la supermartingala de prueba.
   - **Derivación propia:**
     - los límites de `d_t` son constantes conocidas antes de los datos, así que `c = 2·max(|a|, |b|)`: LL `26,9121308208`, Brier `1,794483504598` (supremo) y P@5 `2`. **Demostrada**;
     - restando la constante conocida `m = (a+b)/2`, `c = b − a`: LL `13,8155`, Brier `1` y P@5 `2`; el estimando se desplaza en `m`. **Demostrada.** Ninguna de las dos fija la decisión `cota`.
   - **Aplicación al repositorio:** la sucesión `γ_i` depende del procedimiento, que sigue sin decidir (el artículo usa por defecto `Δ̂_{i−1}`, p. 14). **Pendiente.**
2. **Subgaussianidad del teorema 1.**
   - **El artículo afirma:**
     - teorema 1 (p. 13, ec. 13–14): si `E_{i−1}[e^{λ(δ̂_i − δ_i)}] ≤ e^{λ²c²/2}` para todo λ real, `C^H_t = Δ̂_t ± u(t)/t` es una `(1−α)`-CS;
     - condición suficiente (p. 13): `|δ̂_i| ≤ c` implica que `δ̂_i` es c-subgaussiano (Hoeffding).
   - **Derivación propia:**
     - por esa condición, `c = max(|a|, |b|)`: LL `13,4560654104`, Brier `0,8972417523` y P@5 `1`. **Demostrada**;
     - el proxy `w²/4` de K2 (AE-63) equivale a `c = w/2` tras centrar por una constante. **Demostrada.**
3. **Definición y signo de los diferenciales.**
   - **El artículo afirma:**
     - las reglas se toman positivamente orientadas (p. 8); Brier `S = 1 − (p−y)²` y logarítmica `S = y log p + (1−y) log(1−p)` (p. 9);
     - `δ̂_i = S(p_i, y_i) − S(q_i, y_i)` y `Δ_t` promedia sus esperanzas condicionales respecto de G (ec. 8–10, p. 11);
     - `H₀ʷ(p, q)`: `Δ_t ≤ 0` para todo `t ≥ 1` (ec. 18, p. 16).
   - **Derivación propia:** con `p` = estrategia, `q` = uniforme y `S` = −pérdida, en LL y Brier `δ̂ = d_t`, y la nula P1b en `d` es `H₀ʷ(estrategia, uniforme)` restringida a la ventana. En P@5, que es ganancia, `δ̂ = −d_t`. **Demostrada.**
4. **Filtraciones y predictibilidad.**
   - **El artículo afirma:**
     - F es la filtración observable; G, la «oráculo», incluye `F_{t−1}` y la información de la realidad antes de `y_t`; `p_t`, `q_t` y `r_t` son predecibles respecto de G (§4.2, pp. 10–11);
     - la cobertura vale en tiempos de parada arbitrarios (ec. 3, p. 8);
     - con subsucesiones predecibles `ξ_t ∈ {0, 1}`, la CS y el e-proceso siguen siendo válidos, pero el estimando pasa a ser `Δ_t(ξ)` (F.1, pp. 47–48, ec. 96–102);
     - los pronósticos con rezago `h > 1` requieren la sección E (p. 26).
   - **Derivación propia:** la uniforme es determinista y los límites de `d_t` son constantes, así que ambos son predecibles. **Demostrada.**
   - **Aplicación al repositorio:**
     - que `p_t` se fije antes del sorteo (rezago 1) no es demostrable en el código: exige la decisión `mecanismo_de_sellado_temporal_externo`. **Pendiente**;
     - solo una omisión predecible conserva la validez, con estimando `Δ_t(ξ)`: exige `tratamiento_de_omisiones` y, en supervisión, `tiempos_supervision`. **Pendiente.**
5. **Log Loss truncado frente a `EPSILON_CLIP`.**
   - **El artículo afirma:**
     - truncada `S(p, y) = y log(p ∨ ϵ) + (1−y) log((1−p) ∨ ϵ)`: «although the score is no longer proper, our methods remain valid» (p. 13); «truncated logarithmic score (improper)» (p. 14);
     - con diferenciales no acotados: CS asintótica (sección C) o puntuación de Winkler (sección D) (p. 26).
   - **Derivación propia:**
     - equivalencia con la puntuación del repositorio (recorte a `[ε, 1−ε]`, `ε = 1e−6`): **refutada**. Con `y = 1` y `p = 1 − 1e−9`, el artículo da `log(1 − 1e−9)` y el repositorio `log(1 − 1e−6)`;
     - la truncada del artículo es impropia (con verdad `q = ϵ/2`, el reporte `ϵ/4` supera al veraz); la del repositorio es propia no estricta (L2 de AE-63). **Demostrada**;
     - la validez depende solo de la acotación (L1 de AE-63), no de la equivalencia. **Demostrada.**
6. **Alcance: regla probabilística o diferencial acotado.**
   - **El artículo afirma:**
     - resumen (p. 1): «our main theorems apply to any bounded scores»;
     - una regla es cualquier función real extendida `S: P × Y → ℝ` (p. 8);
     - los teoremas 2 y 3 requieren reglas acotadas (sección 6, p. 26);
     - la proposición 1 vale para cualquier proceso con medias condicionales (p. 32);
     - la sección G (ec. 114, p. 51) los aplica cuando los diferenciales están acotados;
     - la nota 5 (p. 10) separa la comparación de la elicitación.
   - **Derivación propia:**
     - LL recortada, Brier y P@5 tienen diferenciales acotados; la propiedad no es requisito de validez. **Demostrada**;
     - los reportes son 43 marginales, no una distribución sobre los resultados; la validez descansa en la generalidad de la proposición 1. **Demostrada.**
   - **Aplicación al repositorio:** leer una diferencia como «mejor pronóstico probabilístico» depende de la propiedad de la regla y de las marginales reales (L2 de AE-63), y P@5 mide aciertos del Top-5. Exige evidencia sobre las marginales reales y la decisión `papel_y_direccion_de_la_secundaria`. **Pendiente.**

**Discrepancia con AE-62** (`DISCREPANCIAS`): el registro de AE-62, atribuido a la revisión externa, dice que truncar la logarítmica «altera su propiedad de puntuación estrictamente propia». El PDF v6 dice «no longer proper» (p. 13) e «improper» (p. 14): la truncada deja de ser propia, no solo estrictamente propia. Se conserva la atribución original y prevalece la lectura del PDF.

**Nulas y e-procesos del artículo** (`ENUNCIADOS_NULAS_Y_E_PROCESOS`):
- `H₀ʷ(p, q)`: `Δ_t ≤ 0` para todo `t ≥ 1` (ec. 18, p. 16). `H₀ˢ(p, q)`: `δ_t ≤ 0` para todo `t` (ec. 21, p. 17). `H₀ˢ` implica `H₀ʷ`, no al revés.
- Corolario 1 (ec. 19–20, p. 16): rechazar si `L_t > 0` es una prueba secuencial de nivel α; se admite probar una sola vez en un tiempo designado.
- Teorema 3 (ec. 24, p. 17): con las condiciones del teorema 2 y `λ ∈ [0, 1/c)`, `E_t(λ)` es un e-proceso para `H₀ʷ`, y también su mezcla. Un e-proceso cumple `E_P[E_τ] ≤ 1` para toda `P` de la nula y todo tiempo de parada τ (ec. 23, p. 17).
- En la prueba de la proposición 2 (ec. 38–40, pp. 33–34), bajo `H₀ʷ`, `E_t(λ) ≤ L_t(λ)`, con `L_t` supermartingala de prueba.
- p-proceso `p_t = 1/sup_{i≤t} E_i` para la nula del e-proceso (ec. 25–26, p. 18).
- **El artículo demuestra el e-proceso solo para `H₀ʷ` en todo tiempo.** No afirma nada sobre la nula terminal ni sobre la nula sobre `T` del expediente.

**Derivación propia para `1/E`, condicionada a las hipótesis de la supermartingala** (`DERIVACION_1_SOBRE_E_TEOREMA_3`). No es un enunciado del artículo:
- **Hipótesis:** las del teorema 2 (cota constante y `γ_i` predecible) y el marco G, bajo las cuales `L_t(λ)` es supermartingala de prueba respecto de G (proposición 1). `λ ∈ [0, 1/c)`, o la mezcla, y el conjunto `T` se fijan antes de los datos; aquí no se elige ninguno.
- **Identidad:** `E_t(λ) = L_t(λ)·exp(λ t Δ_t)`, así que `E_t ≤ L_t` en el evento `{Δ_t ≤ 0}`.
- **Nula terminal:** cota conjunta `P(E_100 ≥ 1/α y Δ_100 ≤ 0) ≤ P(L_100 ≥ 1/α) ≤ α`, por Markov. Para las leyes en que `Δ_100 ≤ 0` casi seguro, `P(E_100 ≥ 1/α) ≤ α`.
- **Nula sobre `T`:** cota conjunta `P(sup_{t∈T} E_t ≥ 1/α y Δ_t ≤ 0 para todo t ∈ T) ≤ P(sup_t L_t ≥ 1/α) ≤ α`, por Ville, con `T` fijado antes de los datos.
- Son cotas **conjuntas**, no probabilidades condicionales al evento nulo.
- **Limitación:** `1/sup_{i≤100} E_i` **no** queda cubierto bajo la nula terminal, porque el supremo recorre tiempos en que `Δ_i` puede ser positiva. La derivación es propia de esta construcción exponencial y no contradice el contraejemplo de AE-62 para e-procesos arbitrarios.
- **Estado:** la derivación está `demostrada_bajo_las_hipotesis_de_la_supermartingala`; su aplicación al repositorio sigue **pendiente**. Depende de C1, `P1_gamma_predecible`, C3, F1, F2 y O3. `1/E` sigue pendiente de aplicación mientras no estén verificadas la anterioridad de las predicciones, la filtración y el tratamiento de omisiones.

**Dependencias de `N2_inversion_para_p1b`** (`DEPENDENCIAS_DE_N2`):
- **Cobertura, vía teorema 1:** C2, C3, F1, F2 y O3.
- **Cobertura, vía teorema 2:** C1, `P1_gamma_predecible`, C3, F1, F2 y O3.
- **Cobertura, por métrica:** LL necesita L1; Brier, B1; P@5, P1 y el signo `δ̂ = −d_t`. C4 **no** es requisito de cobertura: la validez depende de la acotación, no de la equivalencia con la truncada del artículo.
- **Interpretación de la puntuación, no cobertura:** L2 (LL propia), `L2_marginales_reales_en_el_intervalo` y P2 (P@5 propia no estricta). La propiedad estricta y las marginales reales no son requisitos de cobertura.
- **Requisitos operativos:** `mecanismo_de_sellado_temporal_externo`, `tratamiento_de_omisiones`, `tiempos_supervision`, `cota` y α, todos sin decidir.
- **Estado global: pendiente**, porque ambas vías dependen de F1 y O3.

**Estados tras AE-64** (`ESTADOS_TRAS_AE64`, derivados de sus dependencias por `recalcular_estados()`; no modifican `CONDICIONES_DE_TRASLADO`):
- C1 (acotación del teorema 2), C2 (subgaussianidad del teorema 1) y C3 (signo): **demostradas**.
- C5 (aplicabilidad a P@5): **demostrada** en cuanto a la hipótesis de acotación; la interpretación sigue aparte.
- C4 (equivalencia del truncamiento con `EPSILON_CLIP`): **refutada**, sin ser requisito de validez.
- F2 (filtración), N2 (inversión para P1b) y U1 (usos de `1/E`): **pendientes**.
- Pendiente si alguna dependencia lo está; la regla no impide una demostración futura cuando todas lo estén.

**Correcciones a registros y secciones previas:**
- **R1:** el texto de N2 en `traslado_condiciones_inferenciales.py` («depende de C1, C3, F1 y F2») remite ahora a `verificacion_primaria_choe_ramdas.DEPENDENCIAS_DE_N2`. Su estado sigue pendiente. Es el único cambio en ese módulo.
- **R2:** precisión en la sección de AE-62 sobre la discrepancia de propiedad y la relación con el truncamiento.
- **R3:** precisión en AE-60 y AE-61. El motivo general para dejar `1/E` pendiente («un e-proceso construido desde el inicio puede exigir restricciones en prefijos fuera de `T`») no impide la derivación condicionada para el proceso exponencial del teorema 3; los usos siguen pendientes por las dependencias del repositorio.
- **AE-63:** precisión sobre los enunciados respondidos y los estados de C1–C5, F2, N2 y U1.

**Archivos** (exactamente seis):
- nuevo `app/application/ml/verificacion_primaria_choe_ramdas.py`;
- nuevo `tests/unit/ml/test_verificacion_primaria_choe_ramdas.py`;
- `app/application/ml/traslado_condiciones_inferenciales.py`: solo R1;
- README, ROADMAP y ARCHITECTURE: esta sección y las precisiones.

No cambian el expediente (`propuesta_inferencia_prospectiva.py`), el registro de AE-62, los estados de AE-63, `metricas.py` ni las pruebas anteriores.

**Pruebas** (`17` nuevas, sintéticas):
- **Regresiones:**
  - procedencia v6 exacta, sin nada atribuido al HTML;
  - todo enunciado con página, referencia y comprobación visual en una página de la lista;
  - tres clases separadas: ninguna hipótesis figura como afirmación del artículo, toda hipótesis `pendiente` nombra la decisión o evidencia que exige y todo símbolo citado existe;
  - valores de `c` de los puntos 1 y 2, recalculados desde `intervalo_diferencia_*`, y coherencia con K2;
  - signo frente a la orientación positiva, con `metricas_por_sorteo` (LL y Brier `δ̂ = d_t`; P@5 `δ̂ = −d_t`);
  - filtración, anterioridad y omisiones;
  - contraejemplo exacto de no equivalencia del truncamiento y truncada del artículo impropia;
  - alcance de los teoremas;
  - discrepancia con el registro de AE-62;
  - dependencias de N2 por vía y métrica (C2 solo en la vía del teorema 1; C4, L2 y las marginales reales fuera de la cobertura);
  - estados derivados de sus dependencias;
  - derivación de `1/E`: identidad `E_t = L_t·exp(λ t Δ_t)` con la ley de AE-62 (`c = 2`, `γ = 0`, `Δ_2 = 0`) para λ en `{0,1; 0,25; 0,4; 0,49}`, `E[E_2] ≤ E[L_2] ≤ 1`, y `E[E_1] > 1` con λ = 0,4 como ejemplo de la limitación;
  - U1 pendiente por sus dependencias;
  - texto de N2 en AE-63 (R1);
  - vocabulario sin aprobación ni autorización.
- **Invariante:** `expediente_sin_eleccion`, `AUTORIZA_EVALUACION = False`, decisiones sin valor, usos de `1/E` pendientes, los siete pendientes de AE-52, AE-53 sin aprobar, `huella_diseno()` y los registros de AE-62 y AE-63 intactos.

**Regresiones primero.** Las 17 pruebas se escribieron antes del módulo. Sobre la base `2c8f530` dieron `16 failed, 1 passed` (código de pytest `1`): las 16 regresiones fallan por separado con `ModuleNotFoundError` y el invariante pasa. Con la versión final de las pruebas, en una extracción limpia de la base, el resultado se repite: `16 failed, 1 passed`, código `1`. Durante la implementación:
- la prueba de vocabulario detectó «elegido» en `P1_gamma_predecible`; el texto pasó a «sigue sin decidir»;
- tras comprobar a la vista las pp. 1 y 26, la prueba de enunciados se reforzó para exigir comprobación visual en todo enunciado citado. Contra el módulo anterior dio `2 failed, 15 passed` (código `1`).

**Mediciones en el sandbox Linux de Claude** (Python `3.11.15`, sin datos reales), en una única corrida:
- **Nuevas:** `17 passed` (código `0`).
- **AE-62 a AE-64:** `53 passed` (código `0`).
- **AE-60 a AE-64:** `122 passed` (código `0`).
- **Focalizadas:** `845 + 17 = 862 passed` (código `0`).
- **Suite completa:** `5090 + 17 = 5107 passed`, `0 skipped`, código `0`, con los cinco `DeprecationWarning` conocidos de Alembic.
- `pip check` y `git diff --check`: código `0`.

**Límites:**
- AE-64 verifica enunciados de la fuente en el PDF v6 y deriva condiciones; **no** demuestra que la inferencia sea aplicable al repositorio.
- La derivación de `1/E` es propia y está condicionada a las hipótesis de la supermartingala. No cambia ningún uso de `1/E`, que sigue `pendiente_de_demostracion`.
- Siguen pendientes la anterioridad de `p_t`, la filtración, el tratamiento de omisiones, `γ_i`, las marginales reales y todas las decisiones.
- No fija ninguna decisión, no elige pregunta, familia, cota, λ, α ni regla y no autoriza ninguna evaluación. `ESTADO_EXPEDIENTE` sigue en `expediente_sin_eleccion` y `AUTORIZA_EVALUACION = False`.

**Validación real del operador en Windows** (Python `3.14.6`, pytest `9.1.1`; evidencia atribuida al usuario, no ejecutada por Claude): rama `feature/ae64-verificacion-primaria-choe-ramdas`, base `2c8f5304bc2cb1d144ad5a31e2320dca2d2c2124`.
- **Parche:** el completo `ae64-verificacion-primaria-choe-ramdas.patch`, con SHA-256 verificado `23542024fae1cc3ffe17bf1ab1fb750605ba1e462f65ca38b75db93dd93c472c`.
- **Aplicación:** `git apply --check`, la aplicación, `git apply --reverse --check` y `git diff --check` fueron correctos, con exactamente los seis archivos esperados.
- **Pruebas de AE-64:** `17 passed` en `0,18 s`.
- **AE-60 a AE-64:** `122 passed` en `0,35 s`.
- **`pip check`:** `No broken requirements found`.

**En Windows no se ejecutaron las focalizadas ni la suite completa.** Las cifras `862 passed` (focalizadas) y `5107 passed, 0 skipped` (suite completa) corresponden únicamente al sandbox Linux de Claude.

**Límites de esta validación**: «validada» cubre solo **esta verificación primaria preparatoria** de los enunciados de Choe–Ramdas v6 y sus pruebas.
- **No** demuestra que los teoremas sean aplicables al repositorio.
- Siguen pendientes la anterioridad de `p_t`, la filtración, el tratamiento de omisiones, `γ_i` y las marginales reales.
- Todo uso de `1/E` sigue `pendiente_de_demostracion`; la derivación condicionada a las hipótesis de la supermartingala no cambia su aplicación al repositorio.
- **No** se elige ni se autoriza ninguna inferencia ni evaluación. Las decisiones siguen sin valor y el expediente sigue en `expediente_sin_eleccion` con `AUTORIZA_EVALUACION = False`.

Siguen igual:
- los siete pendientes de AE-52, abiertos;
- la especificación candidata de AE-53, sin aprobar;
- el NO-GO de AE-39 y los bloqueos de AE-41 y AE-46.

Con esta evidencia, **AE-64 queda validada como verificación primaria preparatoria**; no equivale a aplicar los teoremas al repositorio ni a aprobar una inferencia.

No se usaron datos reales, PostgreSQL, entrenamiento ni predicciones reales. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-63 sin cambios.

**Etapa AE-65 -auditoría de las obligaciones de aplicación F1, F2 y O3, validada:** AE-64 dejó pendientes tres obligaciones para aplicar al repositorio las garantías de Choe–Ramdas v6: la anterioridad de las predicciones (F1), la correspondencia de `p_t` con la filtración G (F2) y el tratamiento de omisiones (O3). AE-65 las audita sobre el código actual en el nuevo módulo puro `app/application/ml/auditoria_obligaciones_de_aplicacion.py`. Para cada una registra:
1. qué garantiza hoy el código;
2. qué depende de evidencia temporal o externa que el repositorio no posee;
3. qué decisiones siguen abiertas;
4. qué contraejemplos sintéticos detectan una conclusión indebida.

**La posibilidad estructural no es anterioridad acreditada.** F1, F2, O3, N2 y U1 siguen **pendientes**. No se modifican los registros de AE-63 ni de AE-64. No elige método, α, λ, tratamiento de omisiones, mecanismo ni regla, y no autoriza ninguna evaluación.

**Hallazgos de la lectura:**
- **Registro** (`registro_prospectivo.py`):
  - ninguna entrada lleva fecha, hora ni sello, y el módulo es puro, sin reloj;
  - la cadena de hashes fija el orden interno;
  - las predicciones exigen objetivo posterior al corte, entrada declarada hasta `objetivo−1`, sin sobrescritura y con objetivos crecientes;
  - el resultado va detrás de su predicción;
  - el resumen declara siempre `sellado_temporal_externo_no_verificado` y `evaluable: False`;
  - un protocolo real queda en borrador y no admite salidas.
- **Secuencia** (`validar_secuencia_objetivos`): clasifica la ventana dado `ultimo_sorteo_ocurrido`, que es un entero aportado por quien llama, no una fecha verificada. Cualquier omisión da `no_evaluable_por_omision` (propuesta de AE-53, sin aprobar).
- **Omisiones:** nada registra la causa ni el momento de una omisión. O1 y O2 de AE-63 son derivaciones sobre la ley, no comprobaciones sobre un registro.

**Matriz de obligaciones** (`OBLIGACIONES_AE65`, todas `pendiente`, con nivel `posibilidad_estructural`):
- **F1, anterioridad de `p_t`:**
  - **Hoy:** orden interno y detección de cambios; objetivo posterior al corte; entrada declarada hasta `objetivo−1`; sin sobrescritura ni retroceso; resultado detrás de su predicción **en la cadena**; protocolo real sin salidas.
  - **Evidencia externa:** sello de cada salida, o de la cabeza, anterior a cada sorteo; hora oficial del sorteo; anclaje de la última entrada; unicidad y completitud de la cabeza.
  - **Decisión abierta:** `mecanismo_de_sellado_temporal_externo`.
  - **Contraejemplos:** F1a (registro honesto y retroactivo idénticos byte a byte), F1b (oráculo retroactivo que valida) y F1c (bifurcación de salidas).
- **F2, `p_t` predecible respecto de G:**
  - **Hoy:** uniforme determinista y límites constantes (P4 de AE-64); rezago 1 estructural por la entrada declarada.
  - **Evidencia externa:** anterioridad temporal de la salida (F1) o dependencia funcional acreditada. La segunda exigiría recomputar de forma determinista la salida con el código congelado sobre la entrada declarada, con el código fijado antes de los sorteos. La huella de la entrada no la acredita.
  - **Decisiones abiertas:** `mecanismo_de_sellado_temporal_externo` y `aprobacion_de_la_estrategia_a_congelar`.
  - **Contraejemplos:** F2a (misma huella con salida dependiente de `y_t`), F2b (Brier) y F2c (uniformidad solo marginal).
- **O3, tratamiento de omisiones:**
  - **Hoy:** clasificación de la ventana; toda omisión da no evaluable (propuesta sin aprobar); no se rellena un hueco tras un objetivo posterior; O1 y O2 como derivaciones.
  - **Evidencia externa** (`EVIDENCIA_REQUERIDA_O3`, sin elegir mecanismo): una cabeza sellada antes del plazo de cada sorteo; acreditación de que esa cabeza representa el registro **completo y único** en ese momento; el calendario oficial; la ausencia de una predicción válida para ese objetivo al vencer el plazo.
  - **Decisiones abiertas:** `tratamiento_de_omisiones`, `tiempos_supervision`, `momento_y_tiempos_de_analisis`, `ampliar_equivale_a_sustituir`, `serie_consecutiva_posterior_al_corte` y el mecanismo de sellado.
  - **Contraejemplos:** O3a (momento de la omisión indistinguible), O3b (bifurcación con cabezas selladas) y O3c (resultados retenidos y omisiones finales).
  - **O3 no se reduce a F1:** la anterioridad de las salidas no cubre la unicidad, el calendario ni la ausencia de predicción.

**Aspectos de predictibilidad, por vía y por uso** (`ASPECTOS_DE_PREDICTIBILIDAD`; usos: CS por el teorema 1, CS por el teorema 2, e-proceso del teorema 3 y subsucesión por omisiones):
- **Anterioridad temporal** (`F1_anterioridad`, `P4_anterioridad_de_p_t`): todos los usos.
- **Dependencia funcional de la salida** (`F2_correspondencia_de_la_filtracion`): todos los usos. F2 se compone solo de estos dos aspectos (`COMPONENTES_DE_F2`).
- **γ predecible** (`P1_gamma_predecible`): solo la vía del teorema 2 y el e-proceso del teorema 3.
- **ξ predecible** (`O3_tratamiento_de_omisiones`, `P4_omisiones_predecibles`): solo el uso con una subsucesión por omisiones, cuyo estimando pasa a `Δ_t(ξ)`.
- γ y ξ **no** son requisitos para que `p_t` corresponda a G; se añaden según la vía y el uso.
- **Dependencia O3 común de AE-64** (`OBSERVACION_DEPENDENCIA_O3_COMUN`): `DEPENDENCIAS_DE_N2` incluye O3 en ambas vías como dependencia común. AE-65 la documenta como requisito del uso con omisiones, que no puede excluirse mientras `tratamiento_de_omisiones` siga sin decidir. **El registro de AE-64 no se modifica.**

**Contraejemplos sintéticos** (registros construidos con un protocolo cerrado `sintetico: true`, nunca evidencia):
- **F1a:** un registro construido antes de cada sorteo y otro construido tras conocerlos son idénticos byte a byte, con el mismo resumen. Ninguna entrada tiene claves de fecha.
- **F1b:** un registro fabricado tras conocer los resultados, con `0,9` en los números sorteados y `0,1` en el resto, supera `validar_registro`. El resumen sigue en `evaluable: False` con el motivo de sellado, y `d_t^Brier > 0,09` en cada sorteo.
- **F1c:** dos ramas con salidas distintas para el mismo objetivo, ambas con cabeza sellada antes del sorteo. Ambas validan y contienen una cabeza sellada. Revelar después la favorable deja cada salida anterior, pero la salida revelada depende del resultado.
- **F2a:** dos predicciones con la misma entrada declarada y salidas construidas a partir de resultados distintos validan ambas.
- **F2b, hipótesis exacta** (`HIPOTESIS_UNIFORMIDAD_CONDICIONAL`): cada sorteo es uniforme **condicionalmente a la información disponible antes de predecir**, es decir, `P(y_t = A | G_{t−1}) = 1/C(43, 5)`. De ahí `P(i ∈ y_t | G_{t−1}) = C(42, 4)/C(43, 5) = 5/43`. Es una suposición sobre el mecanismo, no un hecho establecido.
  - **Vector `p` fijado antes de `y_t`:** `E[d_t | G_{t−1}] = −(1/43)·Σ (p_i − 5/43)² ≤ 0` (`esperanza_diferencia_brier_bajo_uniformidad_condicional`, con fracciones exactas). Con `0,9` en cinco números fijos y `0,1` en el resto da `−13249/184900 ≈ −0,0717`.
  - **Oráculo que observa `y_t` antes de producir la salida:** `0,9` en los sorteados y `0,1` en el resto da `B_s = 0,01` y `d_t = B_u − 0,01 ≈ 0,0928 > 0` en todo sorteo probado.
  - Se usan probabilidades interiores y una separación holgada.
- **F2c:** con `y_t = σ(y_{t−1})` y `σ(n) = n mod 43 + 1`, los sorteos son marginalmente uniformes y un `p` fijado antes de `y_t` obtiene `d_t > 0,09`. El resultado de F2b exige uniformidad condicional, no solo marginal.
- **O3a:** una omisión decidida antes del sorteo y otra decidida tras ver un resultado desfavorable dan registros idénticos y la misma clasificación (`no_evaluable_por_omision`). Un registro retroactivo simplemente no tiene omisiones.
- **O3b:** una rama con predicción y otra sin ella para el mismo objetivo, ambas con cabeza sellada antes del plazo, validan las dos. Cualquiera puede revelarse después. **Un sello de cabeza sin unicidad y completitud acreditadas no resuelve O3.**
- **O3c:**
  - retener un resultado deja la ventana `incompleta`, no `completa`, con ese objetivo en `resultado_pendiente`;
  - el resumen lista las predicciones sin resultado;
  - `resumir_registro` **no** lista las omisiones posteriores al último objetivo registrado, pero `validar_secuencia_objetivos` sí.

**Estados sin cambios:**
- En `CONDICIONES_DE_TRASLADO`: F1, F2, O3, N2 y U1 `pendiente`, O1 demostrada y O2 refutada.
- En `ESTADOS_TRAS_AE64`: F2, N2 y U1 `pendiente`; ese catálogo no contiene F1 ni O3.
- `recalcular_estados()` no cambia, ninguna obligación tiene el nivel `acreditada_con_evidencia_externa` y `CONSECUENCIAS` deja N2 y U1 pendientes.

**Archivos** (exactamente cinco):
- nuevo `app/application/ml/auditoria_obligaciones_de_aplicacion.py`;
- nuevo `tests/unit/ml/test_auditoria_obligaciones_de_aplicacion.py`;
- README, ROADMAP y ARCHITECTURE: esta sección.

No cambian los registros de AE-62, AE-63 ni AE-64, `registro_prospectivo.py`, `especificacion_evaluacion_prospectiva.py` ni las pruebas anteriores.

**Pruebas** (`19` nuevas, sintéticas):
- **Regresiones:**
  - registro de obligaciones con cuatro apartados y pendientes;
  - símbolos citados que existen;
  - decisiones abiertas que existen y siguen sin valor;
  - evidencia de O3;
  - aspectos por vía y uso;
  - identificadores en su catálogo;
  - dependencia O3 común documentada sin reescribirla;
  - F1a, F1b y F1c; F2a, F2b y F2c; O3a, O3b y O3c;
  - estados sin cambios en cada catálogo;
  - vocabulario sin aprobación ni autorización.
- **Invariante:** `expediente_sin_eleccion`, `AUTORIZA_EVALUACION = False`, decisiones sin valor, usos de `1/E` pendientes, los siete pendientes de AE-52, AE-53 sin aprobar, `huella_diseno()`, y huellas SHA-256 de los registros de AE-63 y AE-64 iguales a las de la base.

**Regresiones primero.** Las 19 pruebas se escribieron antes del módulo. Sobre la base `dcda4a5` dieron `18 failed, 1 passed` (código de pytest `1`): las 18 regresiones fallan por separado con `ModuleNotFoundError` y el invariante pasa.

**Mediciones en el sandbox Linux de Claude** (Python `3.11.15`, sin datos reales), en una única corrida:
- **Nuevas:** `19 passed` (código `0`).
- **AE-60 a AE-65:** `141 passed` (código `0`).
- **Focalizadas:** `862 + 19 = 881 passed` (código `0`).
- **Suite completa:** `5107 + 19 = 5126 passed`, `0 skipped`, código `0`, con los cinco `DeprecationWarning` conocidos de Alembic.
- `pip check` y `git diff --check`: código `0`.

**Límites:**
- AE-65 audita obligaciones y construye contraejemplos; **no** acredita la anterioridad ni la dependencia funcional, ni resuelve el tratamiento de omisiones.
- La uniformidad condicional es una hipótesis del contraejemplo, no un hecho sobre el mecanismo de sorteo.
- Siguen pendientes F1, F2, O3, N2, U1, `γ_i`, las marginales reales y todas las decisiones. Todo uso de `1/E` sigue `pendiente_de_demostracion`.
- No se elige método, α, λ, tratamiento de omisiones, mecanismo ni regla, y no se autoriza ninguna evaluación. `ESTADO_EXPEDIENTE` sigue en `expediente_sin_eleccion` y `AUTORIZA_EVALUACION = False`.

**Validación real del operador en Windows** (Python `3.14.6`, pytest `9.1.1`; evidencia atribuida al usuario, no ejecutada por Claude): rama `feature/ae65-auditoria-obligaciones-de-aplicacion`, base `dcda4a58e7e7c162f5231d0480f628b25fa017b0`.
- **Parche:** el completo `ae65-auditoria-obligaciones-de-aplicacion.patch`, con SHA-256 verificado `9e28c0f8b6f186241f8de98ea8afc441452acc41fd5bed3fffe56321400387a9`.
- **Aplicación:** `git apply --check`, la aplicación, `git apply --reverse --check` y `git diff --check` fueron correctos; el estado muestra exactamente los cinco archivos previstos.
- **Pruebas de AE-65:** `19 passed` en `0,72 s`.
- **AE-60 a AE-65:** `141 passed` en `1,00 s`.
- **`pip check`:** `No broken requirements found`.

**En Windows no se ejecutaron las focalizadas ni la suite completa.** Las cifras `881 passed` (focalizadas) y `5126 passed, 0 skipped` (suite completa) corresponden únicamente al sandbox Linux de Claude.

**Límites de esta validación**: «validada» cubre solo **esta auditoría de obligaciones** y sus pruebas.
- F1, F2, O3, N2 y U1 siguen **pendientes**.
- Que las pruebas pasen **no** acredita la anterioridad de las predicciones, la correspondencia de la filtración ni la unicidad y completitud del registro.
- Todo uso de `1/E` sigue `pendiente_de_demostracion`.
- **No** se elige ni se autoriza ninguna inferencia ni evaluación. Las decisiones siguen sin valor y el expediente sigue en `expediente_sin_eleccion` con `AUTORIZA_EVALUACION = False`.

Siguen igual:
- los siete pendientes de AE-52, abiertos;
- la especificación candidata de AE-53, sin aprobar;
- el NO-GO de AE-39 y los bloqueos de AE-41 y AE-46.

Con esta evidencia, **AE-65 queda validada como auditoría de obligaciones de aplicación**; no equivale a acreditar la anterioridad, la filtración ni el tratamiento de omisiones, ni a aprobar una inferencia.

No se usaron datos reales, PostgreSQL, entrenamiento ni predicciones reales. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-64 sin cambios.

**Etapa AE-66 -propuesta revisable de evidencia temporal externa, validada:** AE-65 dejó F1, F2 y O3 pendientes. Sus contraejemplos mostraron tres cosas: la cadena no acredita la fecha; la huella de la entrada no acredita la dependencia funcional; y una cabeza sellada sin unicidad ni completitud no resuelve O3. AE-66 registra, en el nuevo módulo puro `app/application/ml/propuesta_evidencia_temporal_externa.py`, una propuesta **revisable** que compara alternativas para acreditar, antes del plazo oficial de cada sorteo:
- **(a)** la salida y su vínculo con la entrada y el código declarados;
- **(b)** un conjunto de predicciones único y completo;
- **(c)** la ausencia de predicción cuando hay omisión;
- **(d)** la procedencia del calendario y de la hora oficial.

**No elige mecanismo**: `mecanismo_de_sellado_temporal_externo` sigue sin valor. Ningún resultado afirma una acreditación operativa. F1, F2, O3, N2 y U1 siguen **pendientes**. No se modifica ningún módulo existente ni el formato del registro de AE-52.

**Fuentes primarias** (`FUENTES_PRIMARIAS`):
- **RFC 3161 y RFC 9162:** inaccesibles desde el sandbox (rfc-editor.org, ietf.org y datatracker bloqueados). Sus propiedades atribuidas quedan **pendientes de verificación primaria** y no se usan como hechos:
  - RFC 3161: instante y precisión del token, reloj de la autoridad, sellado de un hash sin examinar el contenido;
  - RFC 9162: puntos de control, pruebas de inclusión y consistencia, retraso de incorporación, vistas divididas.
- **OpenTimestamps**, en la documentación de sus autores en GitHub:
  - verificado:
    - la prueba queda pendiente al sellar;
    - «It takes a few hours for the timestamp to get confirmed … we're not doing one transaction per timestamp»;
    - una prueba completa indica que un bloque «attests existence as of» una fecha;
    - los calendarios hacen agregación;
  - pendiente: la precisión del tiempo de bloque.

**Alternativas** (`ALTERNATIVAS`), cada una con instante, precisión, latencia, supuestos, pruebas verificables, fallos posibles y costo:
- **A1. Sello de una autoridad de tiempo (RFC 3161).**
  - Instante y precisión: los que declara la autoridad, pendientes de verificación primaria.
  - Latencia: la de una solicitud, que debe completarse antes del plazo.
  - Fallo principal: se pueden sellar muchas cabezas en privado.
  - Costo: bajo.
- **A2. Anclaje agregado en un libro público (tipo OpenTimestamps).**
  - Instante: el del bloque, «a few hours» después del sellado; puede ser posterior al plazo.
  - Los compromisos quedan ocultos, así que las bifurcaciones son invisibles.
  - Costo: bajo, con latencia incierta.
- **A3. Canal público con controles de modificación** (por ejemplo, una rama protegida).
  - **No** es criptográficamente de solo anexado: el propietario puede cambiar los controles.
  - La hora es la de la plataforma.
  - Costo: medio.
- **A4. Bitácora de transparencia** con puntos de control firmados y testigos independientes.
  - **La consistencia de la bitácora es distinta de la unicidad y completitud de las predicciones.**
  - Costo: medio-alto.
- **A5. Custodio humano independiente.**
  - Costo: alto.

**Complementos** (`COMPLEMENTOS`):
- **M. Manifiesto:** huellas de código, entorno, dependencias, entrada, estado auxiliar, semillas y salida.
- **R. Recomputación conforme a los artefactos declarados.**
  - Solo reproduce la salida si también están fijados el entorno, las dependencias, el estado auxiliar, la aleatoriedad y la ausencia de accesos externos no declarados.
  - Demuestra **consistencia**, no anterioridad ni ausencia de fuga.
- **C. Declaración de cierre por objetivo,** anterior al plazo.
- **K. Calendario y hora oficiales,** con zona explícita (America/Bogota, UTC−5, sin horario de verano). La definición del plazo sigue pendiente.

**Reglas pendientes del protocolo** (`CONDICIONES_PENDIENTES_DEL_PROTOCOLO`): identidad autorizada, canal canónico exclusivo, clave única por `(protocolo_hash, juego, objetivo)`, regla de duplicados, recepción antes del plazo (reloj y margen de incorporación) y revisión completa.

**Dos conclusiones distintas sobre (c):**
- **Vía 1, omisión declarada antes del plazo, sin conflicto de clave.** Es verificable solo bajo las reglas pendientes. `evaluar_omision_declarada` devuelve uno de estos resultados:
  - `omision_declarada_sujeta_a_reglas_pendientes`;
  - `conflicto_de_clave`;
  - `declaracion_recibida_despues_del_plazo`;
  - `sin_declaracion`.
- **Vía 2, ausencia inferida de una vista sin entrada.** Permanece pendiente mientras no estén fijados y verificados el reloj de recepción, el margen de incorporación y la revisión completa. `evaluar_ausencia_inferida` devuelve uno de estos resultados:
  - `entrada_recibida_antes_del_plazo`;
  - `vista_no_concluyente_anterior_a_plazo_mas_margen`;
  - `ausencia_inferida_pendiente_de_reloj_margen_y_revision`;
  - `ausencia_inferida_pendiente_sin_margen`.
- Los dos vocabularios son disjuntos, y **ningún resultado afirma acreditación ni ausencia.**

**Matriz de lo que demostraría cada alternativa:**
- **(a)** Todas son `parcial`: que el hash existía antes de un instante; no la dependencia funcional.
- **(b)**
  - A1 y A2: `no_demuestra`;
  - A3: `parcial`;
  - A4 y A5: `condicionado` a las reglas pendientes.
- **(c), vía 1:**
  - A1 y A2: `no_demuestra`;
  - A3: `parcial`;
  - A4 y A5: `condicionado`.
- **(c), vía 2:** `pendiente` en todas.
- **(d)** Todas son `parcial`: instante o constancia, no el calendario, que corresponde a K.

**Lo que ninguna demuestra** (`NO_DEMUESTRA_NINGUNA`):
- la fuga anticipada de `y_t`: los sellos acotan cuándo existía la salida, no qué información tenía;
- la integridad del sorteo (la uniformidad condicional sigue siendo una hipótesis);
- la corrección del código;
- la validez inferencial.

**Recomendación condicional para decisión del operador** (`RECOMENDACION_CONDICIONAL`, no registrada como elegida):
- **Si** el operador acepta los supuestos de A4 y fija las reglas, el reloj de recepción, el margen de incorporación y la definición del plazo, A4 con C, M y K podría cubrir (b) bajo esos supuestos, y (c) **solo por la vía 1**. La vía 2 sigue pendiente.
- Refuerzo opcional: A1 sobre los puntos de control.
- Otras combinaciones podrían cubrirlos bajo supuestos distintos.
- R solo con un contrato de inferencia y los artefactos plenamente fijados.

**Preguntas abiertas** (`PREGUNTAS_ABIERTAS`, no registradas como decisiones del expediente): definición del plazo, reloj de recepción, margen de incorporación, procedimiento de revisión completa, canal, identidad, regla de duplicados, testigos, custodia y fuente del calendario.

**Contraejemplos sintéticos.** Se construyen con HMAC de prueba, instantes con zona, bitácoras como listas y registros de protocolo cerrado `sintetico: true`. Para cada uno se indica qué afirmación refuta y qué supuestos usa:
- **B1:** dos ramas selladas antes del plazo son ambas válidas. Refuta «un sello anterior al plazo acredita unicidad».
- **B2a:** dos predicciones incompatibles para `(BALOTO, 2715)` en una sola bitácora; las vistas de los testigos son consistentes. Refuta «la consistencia acredita la unicidad».
- **B2b:** `claves_duplicadas` detecta la clave repetida sin elegir la regla de aceptación.
- **B2c:** una rama sellada fuera del canal no aparece en la bitácora. Refuta «cualquier sello anterior al plazo cuenta».
- **B3:** dos vistas incompatibles de la bitácora, cada una sin duplicados; solo la comparación entre testigos lo detecta.
- **B4a:** entrada recibida antes del plazo e incluida después; la vista del plazo es `vista_no_concluyente_anterior_a_plazo_mas_margen`. Refuta «un punto de control en el plazo prueba la ausencia».
- **B4b:** tras el plazo más el margen, la vista da `entrada_recibida_antes_del_plazo`.
- **B4c:** una vista posterior sin la clave da `ausencia_inferida_pendiente_de_reloj_margen_y_revision`.
- **B4d:** sin margen o sin reloj, `ausencia_inferida_pendiente_sin_margen`.
- **B4e:** declaración sin conflicto, en conflicto, tardía o inexistente; cada caso da el resultado de la vía 1 que le corresponde.
- **B5:** oráculo con `y_t` filtrado, sellado y publicado a tiempo y sin duplicados, con `d_t^Brier > 0,09`. Refuta «la evidencia temporal excluye la fuga».
- **B6a:** una recomputación conforme reproduce la salida; la del oráculo no coincide.
- **B6b:** un estado auxiliar declarado que contiene `y_t` hace que la recomputación coincida con `d_t > 0,09`. Refuta «recomputación conforme ⇒ ausencia de fuga» y «sellar el código excluye la dependencia de `y_t`».
- **B7:** un sello una hora posterior al sorteo parece anterior si se compara la hora local sin zona con UTC; las funciones rechazan instantes sin zona.

**Archivos** (exactamente cinco):
- nuevo `app/application/ml/propuesta_evidencia_temporal_externa.py`;
- nuevo `tests/unit/ml/test_propuesta_evidencia_temporal_externa.py`;
- README, ROADMAP y ARCHITECTURE: esta sección.

**Pruebas** (`24` nuevas, sintéticas):
- **Regresiones:**
  - catálogo completo;
  - matriz con las dos vías;
  - fuentes y su verificación;
  - lo que ninguna demuestra y las reglas pendientes;
  - recomendación condicional limitada a la vía 1, con el mecanismo sin valor;
  - vocabulario exacto de resultados, sin acreditación;
  - B1 a B7;
  - pureza del módulo, comprobada con AST: sin red, `time`, `subprocess` ni `now`;
  - estados sin cambios;
  - vocabulario sin aprobación ni autorización.
- **Invariante:** expediente y bloqueos sin cambios; huellas SHA-256 de los registros de AE-63, AE-64 y AE-65 iguales a las de la base.

**Regresiones primero.** Las 24 pruebas se escribieron antes del módulo. Sobre la base `576bf92` dieron `23 failed, 1 passed` (código de pytest `1`): las 23 regresiones fallan por separado con `ModuleNotFoundError` y el invariante pasa. Durante la implementación, la prueba de vocabulario detectó «autorizada» en un texto de `PREGUNTAS_ABIERTAS`; el texto pasó a «quien puede publicar y con que firma».

**Mediciones en el sandbox Linux de Claude** (Python `3.11.15`, sin datos reales), en una única corrida:
- **Nuevas:** `24 passed` (código `0`).
- **AE-60 a AE-66:** `165 passed` (código `0`).
- **Focalizadas:** `881 + 24 = 905 passed` (código `0`).
- **Suite completa:** `5126 + 24 = 5150 passed`, `0 skipped`, código `0`, con los cinco `DeprecationWarning` conocidos de Alembic.
- `pip check` y `git diff --check`: código `0`.

**Límites:**
- AE-66 es una propuesta: no acredita la anterioridad, la unicidad, la ausencia ni la procedencia del calendario, y no contacta con ningún servicio de sellado.
- Las garantías de RFC 3161 y RFC 9162 siguen pendientes de verificación primaria.
- No se elige mecanismo, regla de duplicados, reloj, margen ni plazo, y no se autoriza ninguna inferencia ni evaluación. `ESTADO_EXPEDIENTE` sigue en `expediente_sin_eleccion` y `AUTORIZA_EVALUACION = False`.

**Validación real del operador en Windows** (Python `3.14.6`, pytest `9.1.1`; evidencia atribuida al usuario, no ejecutada por Claude):
- **Entorno:** ruta `C:\GitHub\loteria-predictor-update`, rama `feature/ae66-propuesta-evidencia-temporal-externa`, base `576bf9229467fe4035e00811c3038830a3b33dba`; árbol limpio antes de aplicar.
- **Parche:** el completo `ae66-propuesta-evidencia-temporal-externa.patch`, con SHA-256 confirmado `06d18253910c876b97787794cfff4f488c706b53b059664909b5d9b739202217`.
- **Aplicación:** `git apply --check`, la aplicación, `git apply --reverse --check` y `git diff --check` fueron correctos, con exactamente los cinco archivos previstos.
- **Pruebas de AE-66:** `24 passed` en `0,25 s`.
- **AE-60 a AE-66:** `165 passed` en `0,71 s`.
- **`pip check`:** sin problemas.

**En Windows no se ejecutaron las focalizadas ni la suite completa.** Las cifras `905 passed` (focalizadas) y `5150 passed, 0 skipped` (suite completa) corresponden únicamente al sandbox Linux de Claude.

**Límites de esta validación**: «validada» cubre solo **el expediente preparatorio de AE-66 y sus pruebas**. No aprueba ningún mecanismo y no acredita operativamente F1, F2 ni O3.
- RFC 3161 y RFC 9162 siguen pendientes de verificación primaria en el expediente.
- Siguen pendientes las reglas de identidad, canal, duplicados, reloj, margen y revisión completa.
- La omisión declarada sigue sujeta a reglas pendientes, y una vista sin entrada no acredita la ausencia.
- F1, F2, O3, N2 y U1 siguen **pendientes**. Todas las decisiones siguen sin decidir, incluido `mecanismo_de_sellado_temporal_externo`. El expediente sigue en `expediente_sin_eleccion` con `AUTORIZA_EVALUACION = False`.

Siguen igual:
- el NO-GO de AE-39 y los bloqueos de AE-41 y AE-46;
- los siete pendientes de AE-52, abiertos;
- la especificación candidata de AE-53, sin aprobar.

Con esta evidencia, **AE-66 queda validada como expediente preparatorio de evidencia temporal externa**; no equivale a elegir un mecanismo ni a acreditar la anterioridad, la unicidad, la ausencia o la procedencia del calendario.

No se usaron datos reales, PostgreSQL, entrenamiento ni predicciones reales. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-65 sin cambios.

**Etapa AE-67 -verificación primaria de RFC 3161, RFC 5816 y RFC 9162 frente a AE-66, validada:** AE-66 dejó las garantías de RFC 3161 y RFC 9162 como atribuidas y pendientes de verificación primaria. AE-67 las contrasta con los archivos oficiales aportados por el operador y lo registra en el nuevo módulo puro `app/application/ml/verificacion_primaria_rfc_sellado_y_transparencia.py`.
- Separa lo que sostiene el estándar de las **ocho condiciones del repositorio**, que siguen **sin fijar**: identidad autorizada, canal canónico, unicidad por objetivo, regla de duplicados, reloj de recepción, margen de incorporación, revisión completa y calendario oficial.
- **No** elige proveedor ni mecanismo, **no** cambia decisiones ni estados, y no modifica el módulo ni la sección de AE-66.

**Procedencia** (`PROCEDENCIA_RFC`; ningún archivo se añade al repositorio):

| Archivo recibido | Formato | Bytes | SHA-256 de la copia | Cabecera leída en el archivo | Lectura |
|---|---|---|---|---|---|
| `rfc3161.txt` | TXT (ASCII) | 54 585 | `39fd17644ff2d654bc83814a78b1c5b5e7517f496741f34ead5064943eb98240` | RFC 3161, Standards Track, agosto de 2001 | sección y líneas del archivo fuente |
| `rfc5816.txt` | TXT (ASCII) | 10 216 | `9a3eba6ecf14afc7820c51034a608d54d188344a43e9189b0e023d4a6a98f649` | RFC 5816, **`Updates: 3161`**, Standards Track, marzo de 2010 | sección y líneas del archivo fuente |
| `rfc9162.pdf` | PDF (xml2rfc), 53 páginas | 665 522 | `f0fafb9ef6f0555fc9ea5a65fb3552dea5957999aeb04162b2e8d0a748b1a89d` | RFC 9162, `Obsoletes: 6962`, **Category: Experimental**, diciembre de 2021 | sección y página con comprobación visual |

- **Alcance del hash:** cada SHA-256 identifica la copia recibida. Se atribuye a la procedencia que declara el operador y no autentica por sí solo su origen.
- **«Updated by: 5816» en RFC 3161:** es metadata derivada de la cabecera de RFC 5816 (línea 9). RFC 3161 es anterior y no la declara.
- **Impresiones previas:** las impresiones en PDF de los TXT (`53c70b02…` y `591addd4…`) quedan solo como apoyo de lectura, nunca como fuente de una cita.
- **Páginas de RFC 9162 comprobadas visualmente:** 1, 5, 6, 9, 10, 15, 16, 20, 21, 22, 38, 46 y 47.
- **Erratas:** no consultadas.
- **Control de las citas, fuera del repositorio:**
  - las 24 citas de los TXT aparecen en las líneas indicadas del archivo fuente;
  - las 19 citas del PDF aparecen en el texto de su página una vez retiradas las palabras normativas, que la extracción separa, y además se comprobaron a la vista.

**Afirmaciones de AE-66 frente al texto oficial** (`AFIRMACIONES_RFC_3161` y `AFIRMACIONES_RFC_9162`, en correspondencia uno a uno con lo que AE-66 atribuía a cada RFC y con las alternativas A1 y A4):

| Id | Afirmación de AE-66 | Referencia oficial | Estado | Qué sostiene | Condición del repositorio |
|---|---|---|---|---|---|
| T1 | instante del token (`genTime`) | RFC 3161 §2.4.2, líneas 478–480; §1, líneas 42–43 | verificada | instante UTC de **creación del token**, no de la solicitud | calendario oficial y plazo |
| T2 | precisión (`accuracy`) | §2.4.2, líneas 426, 527–528, 535–536, 538–542 y 547–548 | verificada | opcional; `genTime ± accuracy` acota la creación; los campos ausentes valen cero; si falta el campo entero, puede venir por otros medios (no vale cero) | trato de un intervalo que cruza el plazo |
| T3 | fuente de tiempo fiable | §2.1, líneas 103–107; §1, líneas 84–90 | **matizada** | se exige, pero el estándar no fija requisitos generales de seguridad: la confianza descansa en la política de la autoridad | identidad autorizada |
| T4 | se sella un hash sin examinarlo | §2.1, líneas 126–138; §2.4.1, líneas 298–302 | verificada | el token no identifica al solicitante | identidad autorizada |
| T5 | firma, certificado, revocación | §2.3, líneas 195–203; §2.2, líneas 185–187; §4, líneas 791–797 y 805–810; **RFC 5816** §2.2.1, líneas 159–163, y §2.2.2, líneas 203–208 | verificada | clave reservada con `id-kp-timeStamping` crítico; firmante identificado por ESSCertID o ESSCertIDv2; la revocación por compromiso invalida los tokens | custodia y elección de la autoridad |
| T6 | muchas cabezas selladas en privado | §4, líneas 824–829; §2.4.2, líneas 471–476 y 462–465 | **matizada** | admite varios tokens y exige un número de serie único por token; el registro de tokens es opcional de la política; no hay publicidad ni unicidad del contenido | canal canónico, unicidad y duplicados |
| T7 | latencia de una solicitud | §3, líneas 592–594; §3.3, líneas 721–723; §2.4.2, línea 333 (`waiting`); §4, líneas 814–818 | **matizada** | sin transporte obligatorio; admite respuestas diferidas y sondeo; una solicitud anterior al plazo **no** implica un `genTime` anterior | margen de incorporación |
| C1 | puntos de control firmados | RFC 9162 §4.9 y §4.10, p. 22 | verificada | el STH firma tamaño, raíz y marca de tiempo; el último STH servido puede tener hasta un MMD de antigüedad | margen de incorporación |
| C2 | pruebas de inclusión | §2.1.3, p. 9 | verificada | una hoja está en el árbol de ese tamaño | revisión completa |
| C3 | pruebas de consistencia | §2.1.4, p. 10; §1, p. 6 | verificada | propiedad de solo anexado entre dos STH | la consistencia no implica unicidad por objetivo |
| C4 | retraso máximo de incorporación | §4 y §4.1, p. 16; §4.7, p. 20; §4.8, p. 21; §11.1, p. 46 | verificada | el SCT promete incorporar la entrada dentro del MMD, cuyo valor no se limita; la marca de tiempo es la de aceptación según el registro | reloj de recepción y margen |
| C5 | vistas divididas | §1, p. 6; §8.3, p. 38; §11.3, p. 47 | **matizada** | el estándar reconoce el problema, no lo resuelve y exige tratar el registro como tercero de confianza; el gossip «not defined here» | revisión completa |
| C6 | testigos que cofirman | §11.3, p. 47; §1, p. 6 | **no en la fuente** | RFC 9162 no define testigos: la comparación queda fuera de su alcance | condición del protocolo |
| C7 | duplicados | §1, p. 5; §4, p. 15; §11.3, p. 47 | **matizada** | un mismo envío «SHOULD return the same SCT» y puede generar varias entradas; no hay unicidad por clave de la aplicación | unicidad por objetivo y regla de duplicados |

**Discrepancias con AE-66** (`DISCREPANCIAS_CON_AE66`; se registran aquí y AE-66 no se modifica):
- **T3:** la confianza depende de la política de la autoridad.
- **T7:** la latencia no está acotada y `genTime` es el instante de creación del token.
- **C5:** el registro debe tratarse como tercero de confianza y el gossip no está definido.
- **C6:** los testigos de A4 son una condición del protocolo, no del estándar.
- **C7:** coincide con B2a de AE-66.
- **Categoría de RFC 9162:** es Experimental, algo que AE-66 no indicaba.

**Derivación propia sobre el margen** (`DERIVACION_MARGEN_RFC_9162`), a partir de §11.1 (p. 46) y §4.10 (p. 22):
- si el registro opera correctamente, una entrada aceptada antes del plazo queda incorporada a más tardar en `plazo + MMD`;
- un STH servido puede tener hasta un MMD de antigüedad;
- por tanto, una vista basada en un STH servido solo cubre esa entrada si se obtiene después de `plazo + 2·MMD`.

El margen de incorporación del repositorio sigue sin fijar.

**Intervalo del sello** (depende solo de T2; C4 se verifica aparte):
- `PrecisionSello` valida `millis` y `micros` entre 1 y 999 y trata los campos ausentes como cero.
- `intervalo_del_sello` devuelve `None` si falta `accuracy`.
- `sello_anterior_al_plazo` devuelve uno de estos resultados:
  - `anterior_con_margen_de_precision`;
  - `no_concluyente_por_precision`;
  - `posterior_al_plazo_con_margen_de_precision` (añadido al plan para cubrir un intervalo entero posterior al plazo);
  - `precision_ausente_pendiente`.
- Ningún resultado afirma acreditación ni unicidad, y los instantes sin zona se rechazan.

**Archivos** (exactamente cinco):
- nuevo `app/application/ml/verificacion_primaria_rfc_sellado_y_transparencia.py`;
- nuevo `tests/unit/ml/test_verificacion_primaria_rfc_sellado_y_transparencia.py`;
- README, ROADMAP y ARCHITECTURE: esta sección.

No se modifican AE-66 ni ningún otro módulo.

**Pruebas** (`21` nuevas, sintéticas):
- **Regresiones:**
  - procedencia de los tres archivos;
  - `Updates: 3161` derivado de RFC 5816;
  - impresiones solo como apoyo;
  - forma de las citas según el formato (líneas y `texto_fuente_txt` en los TXT; página y `pdf_visual` en el PDF);
  - inventario uno a uno con AE-66;
  - estados y referencias;
  - T5 apoyada en RFC 5816;
  - testigos y duplicados como condiciones del protocolo;
  - ocho condiciones sin fijar;
  - discrepancias sin reescribir AE-66;
  - derivación del margen;
  - intervalo y comparación del sello con el plazo;
  - una solicitud anterior al plazo con `genTime` posterior;
  - un sello anterior que no implica unicidad (bifurcación de AE-66);
  - C4 con las funciones de AE-66;
  - instantes sin zona;
  - estados y decisiones sin cambios;
  - pureza del módulo;
  - vocabulario.
- **Invariante:** expediente y bloqueos sin cambios, con las huellas SHA-256 de los registros de AE-63 a AE-66 iguales a las de la base.

**Regresiones primero.** Las 21 pruebas se escribieron antes del módulo. Sobre la base `31cdc50` dieron `20 failed, 1 passed` (código de pytest `1`): las 20 regresiones fallan por separado con `ModuleNotFoundError` y el invariante pasa. Con la versión final de las pruebas, en una extracción limpia de la base, el resultado se repite: `20 failed, 1 passed`, código `1`.

**Ajuste durante la implementación:** la prueba de vocabulario detectaba «autorizada» dentro del identificador obligatorio `identidad_autorizada`. Se ajustó para excluir los identificadores fijos de las ocho condiciones antes de buscar palabras prohibidas; la comprobación del resto de los textos no cambia.

**Mediciones en el sandbox Linux de Claude** (Python `3.11.15`, sin datos reales), en una única corrida:
- **Nuevas:** `21 passed` (código `0`).
- **AE-60 a AE-67:** `186 passed` (código `0`).
- **Focalizadas:** `905 + 21 = 926 passed` (código `0`).
- **Suite completa:** `5150 + 21 = 5171 passed`, `0 skipped`, código `0`, con los cinco `DeprecationWarning` conocidos de Alembic.
- `pip check` y `git diff --check`: código `0`.

**Límites:**
- AE-67 verifica afirmaciones del estándar; **no** acredita la anterioridad, la unicidad, la ausencia ni la procedencia del calendario, y no fija ninguna condición del repositorio.
- RFC 9162 es **Experimental**. Las erratas no se consultaron.
- No se elige proveedor, mecanismo, reloj, margen ni plazo, y no se autoriza ninguna inferencia ni evaluación.
- F1, F2, O3, N2 y U1 siguen pendientes. `ESTADO_EXPEDIENTE` sigue en `expediente_sin_eleccion` y `AUTORIZA_EVALUACION = False`.

**Validación real del operador en Windows** (Python `3.14.6`, pytest `9.1.1`; evidencia atribuida al usuario, no ejecutada por Claude):
- **Entorno:** repositorio `C:\GitHub\loteria-predictor-update`, rama `feature/ae67-verificacion-primaria-rfc-sellado-y-transparencia`, base `31cdc50f0b312c2ad09f9fd7922d36fec5c371c5`; árbol limpio antes de aplicar.
- **Parche:** el completo `ae67-verificacion-primaria-rfc-sellado-y-transparencia.patch`, de `82 390` bytes y SHA-256 `ae7d0139c023f29818dd11849a26955b0be9297fc1caf4050a8316bd600429b0`.
- **Aplicación:** `git apply --check`, la aplicación, `git apply --reverse --check` y `git diff --check` fueron correctos, con exactamente los cinco archivos esperados.
- **Pruebas nuevas de AE-67:** `21 passed in 0.19s`.
- **AE-60 a AE-67:** `186 passed in 0.66s`.
- **`pip check`:** `No broken requirements found.`

**En Windows no se ejecutaron las focalizadas ni la suite completa.** Las cifras `926 passed` (focalizadas) y `5171 passed, 0 skipped` (suite completa) corresponden únicamente al sandbox Linux de Claude.

**Límites de esta validación**: «validada» cubre solo **el expediente preparatorio de verificación primaria y sus pruebas**.
- La verificación de los RFC **no** acredita su aplicación operativa al repositorio.
- Las ocho condiciones del protocolo siguen sin fijar: identidad autorizada, canal canónico, unicidad por objetivo, regla de duplicados, reloj de recepción, margen de incorporación, revisión completa y calendario oficial.
- F1, F2, O3, N2 y U1 siguen **pendientes**.
- **No** se elige mecanismo ni se autoriza ninguna inferencia ni evaluación. Todas las decisiones siguen sin decidir, incluido `mecanismo_de_sellado_temporal_externo`. El expediente sigue en `expediente_sin_eleccion` con `AUTORIZA_EVALUACION = False`.

Siguen igual:
- el NO-GO de AE-39 y los bloqueos de AE-41 y AE-46;
- los siete pendientes de AE-52, abiertos;
- la especificación candidata de AE-53, sin aprobar.

Con esta evidencia, **AE-67 queda validada como expediente preparatorio de verificación primaria de RFC 3161, RFC 5816 y RFC 9162**; no equivale a aplicar esas garantías al repositorio ni a elegir un mecanismo.

No se usaron datos reales, PostgreSQL, entrenamiento ni predicciones reales. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-66 sin cambios.

**Etapa AE-68 -especificación verificable de las condiciones del protocolo, validada:** AE-66 y AE-67 dejaron sin fijar ocho condiciones del protocolo. AE-68 las especifica de forma verificable en el nuevo módulo puro `app/application/ml/especificacion_condiciones_del_protocolo.py` y separa tres planos:
- **(E) Estándar:** solo afirmaciones de AE-67. Lo que procede de RFC 9162 lleva la marca `solo_certificados`, porque ese RFC describe registros de certificados y precertificados: sus SCT, su MMD y sus pruebas **no** se atribuyen a nuestras predicciones ni omisiones.
- **(P) Protocolo hipotético:** lo que tendría que garantizar el protocolo de este repositorio.
- **(O) Evidencia operativa:** lo que exigiría pruebas de la operación real.

**Nada queda fijado:** las ocho condiciones, R0 y R9 siguen `sin_fijar`. No se elige mecanismo, esquema de firma ni regla, y ningún registro de AE-63 a AE-67 cambia.

**Requisitos previos** (`REQUISITOS_PREVIOS`; no amplían la lista de ocho):
- **R0 `declaracion_previa_del_protocolo`, única raíz de confianza.** Es el protocolo de AE-52, fijado antes del corte. Declara:
  - claves, canal y clave de unicidad;
  - regla de duplicados, y reloj con su cota de error;
  - margen, revisión completa y política ante vistas divididas;
  - fuente del calendario y definición del plazo.

  Su autenticación (`AUTENTICACION_DE_R0`) exige tres elementos, todos pendientes: un sello externo anterior al corte, publicación fuera de banda con copias de terceros y reconocimiento explícito del operador. Sin este último, un sello o una publicación no excluyen protocolos alternativos (T6).
- **R9 `puente_entrada_canal`:** cómo se codifican nuestras entradas en el canal que se designe y qué recibo firmado emite ese canal (hash canónico, `t_rec` y promesa de incorporación).

**Grafos acíclicos:**
- **Normativo:** R0 declara todas las condiciones y R9.
- **De verificación:**
  - identidad, canal y calendario ← R0;
  - R9 ← canal;
  - reloj ← canal, R9 y calendario;
  - margen ← canal, R9 y reloj;
  - revisión completa ← canal y margen;
  - duplicados ← reloj y revisión completa;
  - unicidad ← identidad, duplicados y revisión completa.

**Correspondencia con AE-66** (`CORRESPONDENCIA_CON_AE66`, sin renombrar nada):
- `recepcion_antes_del_plazo` se reparte entre `reloj_de_recepcion` y `margen_de_incorporacion`;
- `calendario_oficial` procede del complemento K y de las preguntas abiertas;
- la definición del plazo es una decisión dentro del calendario.

**Condiciones** (`CONDICIONES_DEL_PROTOCOLO`, con los nombres de AE-67; todas `sin_fijar`):

| Condición | Definición verificable (P) | Estándar (E) | Evidencia operativa (O) |
|---|---|---|---|
| `identidad_autorizada` | firma verificada con una clave declarada en R0 y vigente en `t_rec` | T4, T5; C7 (solo certificados) | custodia y revocaciones |
| `canal_canonico` | solo cuentan las entradas del canal declarado en R0 | T6; C5 (solo certificados) | operación del canal |
| `unicidad_por_objetivo` | tras la revisión completa, cada clave está vacía, contiene solo reintentos idénticos o tiene un conflicto registrado; la unicidad se comprueba como ausencia de conflictos, no se afirma | C3, C7 (solo certificados) | revisión completa |
| `regla_de_duplicados` | detectar y registrar primero (reintento idéntico o contenidos incompatibles, por hash canónico); después, una regla declarada que solo usa hash, tipo, firmante y `t_rec`; el registro se conserva | C7 (solo certificados) | revisión completa |
| `reloj_de_recepcion` | `t_rec` con zona, resolución y **cota declarada del error frente a UTC**; ordenar por `t_rec`, nunca por índice | T1, T2; C4 (solo certificados) | recibos y comprobación de la cota |
| `margen_de_incorporacion` | umbrales condicionados a H1–H5 (ver abajo) | C1, C4 (solo certificados) | auditoría de recibos con pruebas de inclusión |
| `revision_completa` | todas las entradas hasta un punto que cumple el margen, más consistencia y política ante vistas divididas | C2, C5, C6 (solo certificados) | copia completa y comparación entre partes |
| `calendario_oficial` | plazo en UTC por `(juego, objetivo)` a partir de la fuente y la definición declaradas en R0 | ninguno | archivo por terceros |

**Instantes** (`INSTANTES`):
- `t_rec`: recepción por nuestro canal;
- `t_sct`: aceptación que representa un SCT, solo en RFC 9162;
- `t_sth`: marca del punto de control;
- `t_consulta`: hora de consulta.

**Hipótesis temporales** (`HIPOTESIS_TEMPORALES`): son requisitos de un **canal sintético**, no garantías de RFC 9162 para predicciones. Todas `sin_fijar`.
- **H1:** recibo firmado que vincula el hash canónico con `t_rec` y promete la incorporación.
- **H2:** compromiso verificable: todo punto de control con `t_sth ≥ t_rec + MMD` contiene la entrada con recibo; se audita con el recibo.
- **H3:** coherencia de cada punto de control: contiene toda entrada incorporada en un instante `≤ t_sth` y ninguna posterior. No se puede fechar un punto reciente sobre una vista antigua incompleta.
- **H4:** un punto servido tiene como máximo un MMD de antigüedad respecto de `t_consulta`.
- **H5:** relojes con zona, resolución y una cota declarada y comprobable del error frente a UTC. **Una marca en formato UTC no prueba exactitud temporal.**

**Efecto de la cota de reloj** (`RelojDeclarado`, `comparar_con_plazo`, `umbral_de_punto_de_control`). La incertidumbre `u` es la cota de error más la resolución.
- **Frente al plazo:** `t_rec` queda `anterior_con_margen_de_reloj` solo si `t_rec + u < plazo`, y `posterior_con_margen_de_reloj` si `t_rec − u ≥ plazo`. En el resto de casos, incluido un intervalo que cruza el plazo, `no_concluyente_por_error_de_reloj`. Sin cota declarada, `cota_de_error_sin_declarar_pendiente`.
- **Umbrales medidos:**
  - bajo H1, H2, H3 y H5: `t_sth ≥ plazo + MMD + u`;
  - con solo la hora de consulta y H4: `t_consulta ≥ plazo + 2·MMD + u`.
- **Límite de completitud** (`LIMITE_DE_COMPLETITUD`): un punto de control reciente no acredita que el canal recibiera todas las entradas pertinentes. Solo cubre las que tienen recibo; un envío censurado sin recibo no aparece nunca.

**Omisión declarada frente a ausencia inferida** (`REQUISITOS_DE_VIA`, `estado_hipotetico_de_via`):
- **Vía 1, omisión declarada:** es una entrada positiva, pero excluir una predicción incompatible exige R0, R9, las ocho condiciones y una política ante vistas divididas.
- **Vía 2, ausencia inferida:** exige además tratar los envíos sin recibo.
- **La función solo evalúa escenarios hipotéticos de prueba** y nunca lee ni modifica los estados reales. Con todo supuesto fijado devuelve:
  - vía 1: `hipotesis_completa_sin_evidencia_operativa_ni_resolucion_de_vistas_divididas`;
  - vía 2: `hipotesis_completa_pendiente_de_envios_sin_recibo_y_vistas_divididas`.
- Si falta cualquier requisito, `pendiente`. Ningún resultado afirma acreditación.

**Modelos sintéticos**, que reutilizan AE-66 sin modificarlo:
- `entradas_admisibles`: la verificación de firma se inyecta; el HMAC de las pruebas solo modela firmas (`MODELO_DE_FIRMA`).
- `registrar_conflictos` y `aplicar_regla`: el registro se devuelve intacto.
- `REGLAS_DE_DUPLICADOS_CANDIDATAS` (`primera_recibida`, `invalidar_objetivo`, `invalidar_protocolo`): ninguna elegida, `REGLA_DE_DUPLICADOS_ELEGIDA = None`.
- `es_regla_admisible`: una regla solo puede recibir las entradas y el registro.
- `ordenar_por_recepcion`.
- Recibos y puntos de control sintéticos, con `punto_de_control_es_coherente` (H3) y `cumple_compromiso_de_incorporacion` (H2).

**Archivos** (exactamente cinco):
- nuevo `app/application/ml/especificacion_condiciones_del_protocolo.py`;
- nuevo `tests/unit/ml/test_especificacion_condiciones_del_protocolo.py`;
- README, ROADMAP y ARCHITECTURE: esta sección.

No se modifica ningún otro módulo.

**Pruebas** (`22` nuevas, sintéticas, por comportamiento observable):
- **Registro, referencias y correspondencia:**
  - ocho condiciones, R0 y R9 `sin_fijar`;
  - referencias solo a AE-67, con RFC 9162 marcado `solo_certificados`;
  - correspondencia con AE-66.
- **Grafos:** aciclicidad y R0 como única raíz; autenticación de R0 pendiente; hipótesis como requisitos del canal sintético.
- **Identidad:** verificador inyectado, con una clave desconocida, una revocada y una firma inválida.
- **Conflictos y reglas:**
  - reintento idéntico frente a contenidos incompatibles, incluidas una predicción y una omisión con la misma clave;
  - el conflicto persiste tras invalidar el objetivo;
  - la primera recibida se elige por `t_rec` y no por índice;
  - las reglas candidatas no cambian con el resultado del sorteo;
  - un contraejemplo que elige por puntuación queda excluido.
- **Puntos de control:**
  - un **punto de control fechado sobre una vista antigua incompleta** se detecta (H3 y H2);
  - umbrales por marca y por consulta;
  - un envío censurado sin recibo;
  - una incorporación tardía que viola H2 solo se detecta con el recibo.
- **Reloj:**
  - **desfase cercano a la cota**: una marca un segundo antes del plazo, con el reloj adelantado 1,9 s dentro de una cota de 2 s, da `no_concluyente_por_error_de_reloj`;
  - una marca en formato UTC sin cota queda pendiente.
- **Vías:** evaluadas en escenarios hipotéticos, sin cambiar los estados reales.
- **Estados, pureza y vocabulario:** estados y decisiones sin cambios; pureza comprobada con AST; vocabulario sin términos de aprobación ni autorización.
- **Invariante:** huellas SHA-256 de los registros de AE-63 a AE-67 iguales a las de la base.

**Regresiones primero.** Las 22 pruebas se escribieron antes del módulo. Sobre la base `828b887` dieron `21 failed, 1 passed` (código de pytest `1`): las 21 regresiones fallan por separado con `ModuleNotFoundError` y el invariante pasa. Durante la implementación, dos pruebas detectaron textos del módulo que no se ajustaban a lo especificado, y se corrigieron sin cambiar las pruebas:
- la formulación de H3 («toda entrada incorporada en un instante `<=` t_sth y ninguna posterior»);
- «canal elegido», que pasó a «canal que se designe».

**Mediciones en el sandbox Linux de Claude** (Python `3.11.15`, sin datos reales), en una única corrida:
- **Nuevas:** `22 passed` (código `0`).
- **AE-60 a AE-68:** `208 passed` (código `0`).
- **Focalizadas:** `926 + 22 = 948 passed` (código `0`).
- **Suite completa:** `5171 + 22 = 5193 passed`, `0 skipped`, código `0`, con los cinco `DeprecationWarning` conocidos de Alembic.
- `pip check` y `git diff --check`: código `0`.

**Límites:**
- AE-68 especifica las condiciones y construye modelos sintéticos; **no** fija ninguna condición, R0 ni R9, y **no** acredita anterioridad, unicidad, ausencia, reloj ni calendario.
- Los recibos, los puntos de control y el HMAC son analogías de prueba, no una implementación conforme a RFC 9162 ni un esquema real.
- F1, F2, O3, N2 y U1 siguen pendientes. Todas las decisiones siguen sin valor. `ESTADO_EXPEDIENTE` sigue en `expediente_sin_eleccion` y `AUTORIZA_EVALUACION = False`.

**Validación real del operador en Windows** (Python `3.14.6`, pytest `9.1.1`; evidencia atribuida al usuario, no ejecutada por Claude):
- **Entorno:** repositorio `C:\GitHub\loteria-predictor-update`, rama `feature/ae68-especificacion-condiciones-del-protocolo`, base `828b887c6c36c99682532344fc9e68667e7e5177`; árbol limpio antes de aplicar.
- **Parche:** el completo `ae68-especificacion-condiciones-del-protocolo.patch`, de `88 508` bytes y SHA-256 `0878d91817ca2e9a190762d9761720abde9beed435cad9b38d48e6b0f0dfd735`.
- **Aplicación:** `git apply --check`, la aplicación, `git apply --reverse --check` y `git diff --check` fueron correctos, con exactamente los cinco archivos previstos.
- **Incidencia de validación, resuelta:** el entorno virtual anterior, guardado en una ruta temporal de AE-41, estaba incompleto y no podía ejecutar pytest. No es atribuible al parche. Se creó uno nuevo fuera del repositorio, en `%LOCALAPPDATA%\loteria-predictor-venvs\ae68`, instalando `backend\requirements.txt`.
- **Pruebas de AE-68, en el entorno nuevo:** `22 passed in 0.40s`.
- **AE-60 a AE-68:** `208 passed in 1.17s`.
- **`pip check`:** `No broken requirements found`.

**En Windows no se ejecutaron las focalizadas ni la suite completa.** Las cifras `948 passed` (focalizadas) y `5193 passed, 0 skipped` (suite completa) corresponden únicamente al sandbox Linux de Claude.

**Límites de esta validación**: «validada» cubre solo **el expediente preparatorio de especificación de las condiciones del protocolo y sus pruebas**.
- R0, R9 y las ocho condiciones siguen `sin_fijar`.
- Las funciones temporales modelan hipótesis de un canal sintético y **no** trasladan automáticamente las garantías de RFC 9162 a entradas de predicción.
- **No** se elige mecanismo, esquema de firma ni regla.
- F1, F2, O3, N2 y U1 siguen **pendientes**.
- Todas las decisiones siguen sin valor. El expediente sigue en `expediente_sin_eleccion` con `AUTORIZA_EVALUACION = False`.

Siguen igual:
- el NO-GO de AE-39 y los bloqueos de AE-41 y AE-46;
- los siete pendientes de AE-52, abiertos;
- la especificación candidata de AE-53, sin aprobar.

Con esta evidencia, **AE-68 queda validada como expediente preparatorio de especificación de las condiciones del protocolo**; no equivale a fijar ninguna condición, elegir un mecanismo ni acreditar la aplicación operativa.

No se usaron datos reales, PostgreSQL, entrenamiento ni predicciones reales. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-67 sin cambios.

**Etapa AE-69 -inventario verificable del contenido de R0 frente al formato del protocolo de AE-52, validada:** AE-68 dejó R0 (`declaracion_previa_del_protocolo`) como única raíz de confianza. Dijo que R0 es el protocolo de AE-52 y que declara claves, canal, clave de unicidad, regla de duplicados, reloj, margen, revisión completa, política ante vistas divididas, calendario y plazo. AE-69 comprueba que **el formato vigente de AE-52 no admite ninguna de esas declaraciones**:
- no como campo, porque el protocolo exige un conjunto exacto de claves;
- no como pendiente, porque la lista solo admite los siete identificadores de AE-52.

El nuevo módulo puro `app/application/ml/inventario_declaracion_previa_del_protocolo.py` inventaría los once elementos del contenido de R0 y ofrece un comprobador sintético de completitud. **No se decide nada:**
- ni la ubicación ni el formato de la declaración;
- ni mecanismo, esquema de firma, regla o valor.

AE-52 y AE-63 a AE-68 no cambian.

**R0, R9 y las ocho condiciones:**
- **R0:** se separa su **contenido**, objeto de AE-69, de su **autenticación**. Los tres elementos de `AUTENTICACION_DE_R0` siguen pendientes, y un contenido completo no autentica R0.
- **R9 `puente_entrada_canal`:** es un elemento declarado por R0 (`formato_de_entrada_y_recibo`), pero se verifica contra `canal_canonico`.
- **Las ocho condiciones:** siguen `sin_fijar` y cada una recibe al menos un elemento.

**Inventario** (`ELEMENTOS_DE_R0`, los once `pendiente`):

| Elemento | Alimenta | Situación en AE-52 |
|---|---|---|
| `conjunto_de_claves_y_revocacion` | `identidad_autorizada` | sin campo |
| `identidad_del_canal` | `canal_canonico` | sin campo |
| `composicion_de_la_clave_de_unicidad` | `unicidad_por_objetivo` | componentes en la predicción, sin declaración de la clave |
| `regla_de_duplicados` | `regla_de_duplicados` | sin campo |
| `reloj_zona_resolucion_cota_y_trato_del_intervalo` | `reloj_de_recepcion` | sin campo |
| `margen_delta_y_mmd` | `margen_de_incorporacion` | sin campo |
| `procedimiento_de_revision_completa` | `revision_completa` | sin campo |
| `politica_ante_vistas_divididas` | `revision_completa` | sin campo |
| `fuente_del_calendario` | `calendario_oficial` | sin campo |
| `definicion_del_plazo` | `calendario_oficial` | sin campo |
| `formato_de_entrada_y_recibo` | R9 | sin campo |

**Contenido de cada elemento:**
- las referencias al estándar, solo de AE-67; lo que procede de RFC 9162 lleva `solo_certificados` porque ese RFC cubre certificados y precertificados, **no** nuestras entradas;
- la evidencia que lo resolvería;
- el criterio para mantenerlo pendiente.

**Registros auxiliares:**
- **`CORRESPONDENCIA_CON_PENDIENTES_AE52`**:
  - `mecanismo_de_sellado_temporal_externo` toca a la autenticación de R0, no a su contenido;
  - `corte_temporal_por_juego` está relacionado con `definicion_del_plazo`, sin identificarse con ella.
- **`PREGUNTAS_ABIERTAS_AE69`**, todas sin respuesta:
  - la ubicación de la declaración;
  - el plazo frente al corte;
  - cómo expresar un pendiente de R0 sin romper la regla de AE-52.

**Comprobador sintético** (`comprobar_declaracion_sintetica`, `motivos_de_incompletitud`). Nunca lanza excepciones.
- **Forma:** la declaración de prueba debe ser un `dict` con exactamente las once claves. Cada elemento es `{"estado": "pendiente"}` o `{"estado": "declarado_sintetico", "valor": …}`.
- **Valores admitidos:** solo texto, enteros, booleanos, listas y objetos con claves de texto. Se rechazan `float`, tuplas, conjuntos, `bytes`, mapeos que no son `dict` y claves no textuales, porque el serializador de AE-52 confunde algunos de ellos: `{1: "x"}` y `{"1": "x"}` dan los mismos bytes, y una tupla da lo mismo que una lista.
- **Valores vacíos o nulos** (`TRATAMIENTO_DE_VALORES_VACIOS`): `None`, un texto vacío o solo con espacios, una lista vacía o un objeto vacío, también anidados, **no** cuentan como declaración sustantiva. La declaración queda `incompleta` y no se hashea. Los enteros y booleanos, incluidos `0` y `false`, cuentan como valores.
- **Resultados:** `incompleta`, `todos_pendientes`, `parcial` o `completa_sintetica_sin_autenticar`.
- **Alcance** (`ALCANCE_DE_LA_COMPLETITUD`): **`completa_sintetica_sin_autenticar` solo indica completitud estructural de los once elementos. No acredita suficiencia de sus valores, autenticación, fijación de R0 ni cumplimiento de ninguna condición.**
- **Estado actual:** `ESTADO_ACTUAL_DE_R0` tiene los once elementos `pendiente` y da `todos_pendientes`.

**Hash** (`hash_de_declaracion_sintetica`):
- Reutiliza `serializar_entrada` y `hash_entrada` de AE-52 y exige que `leer_entrada` reproduzca la declaración.
- Una declaración incompleta lanza `DeclaracionSinteticaInvalidaError` y no se hashea.
- La declaración **no** es una entrada de AE-52: no pasa por `validar_registro`, y no se atribuye a AE-52 ningún formato de declaración.
- Las pruebas solo muestran que, **en los ejemplos probados**, cambiar un elemento cambia el hash. No se afirma ninguna propiedad universal contra colisiones.

**Clasificación de afirmaciones** (`CLASIFICACION_DE_AFIRMACIONES`, A1–A11), con procedencia exacta:

| Clase | Afirmaciones | Procedencia |
|---|---|---|
| Hechos observados en el código | A1, A2, A4, A10, A11 | archivo y símbolo `@9cd222c` más la prueba que lo observa |
| Hechos citados de fuente | A8 | identificadores `AE-67:C1`…`C7`, cuyas páginas registra AE-67; sin cita nueva |
| Derivaciones propias | A3, A6, A7 | premisas resolubles en los registros |
| Hipótesis de aplicación | A5, A9 | quedan `pendiente` |

**Contenido de las afirmaciones:**
- **A1:** una clave adicional en un protocolo sintético se rechaza.
- **A2:** un identificador de R0 en `pendientes` se rechaza.
- **A4:** la predicción contiene `protocolo_hash`, `codigo_juego` y `sorteo_objetivo`.
- **A5:** que esos campos sean la clave de unicidad es la propuesta de AE-66, no una declaración de R0.
- **A9:** el plazo y el corte están relacionados, sin identificarse.
- **A11:** comportamiento observado del serializador de AE-52.

**Archivos** (exactamente cinco):
- nuevo `app/application/ml/inventario_declaracion_previa_del_protocolo.py`;
- nuevo `tests/unit/ml/test_inventario_declaracion_previa_del_protocolo.py`;
- README, ROADMAP y ARCHITECTURE: esta sección.

No se modifica ningún otro módulo.

**Pruebas** (`42` casos sintéticos en tres grupos; el módulo nuevo se importa dentro de cada prueba de G1):
- **G1 (`35` casos en 14 funciones), dependen del módulo nuevo:**
  - inventario y cobertura;
  - disjunción con los pendientes de AE-52;
  - formas inválidas;
  - valores vacíos o nulos, definidos y probados antes del resultado completo;
  - resultados y su alcance;
  - estado actual;
  - hash en ejemplos concretos;
  - el contenido completo no autentica R0;
  - referencias a AE-67;
  - clasificación con procedencia;
  - vías de AE-68 que siguen `pendiente`;
  - pureza por AST y vocabulario.
- **G2 (`3`), invariantes sobre código existente:**
  - huellas SHA-256 de AE-63 a AE-67 y de AE-68 (`03c83bb1…04b00d`);
  - huella de AE-52 (`4f31cdeb…21c50b`);
  - estados, decisiones y bloqueos sin cambios.
- **G3 (`4`), integraciones contra la API pública real de AE-52:** A1, A2, A4 y A11.

**Pruebas primero, sobre la base `9cd222c`.** Antes de escribir el módulo se ejecutaron los tres grupos. El resultado fue `35 failed, 7 passed`, con código de pytest `1`:
- **G1:** los `35` casos fallan por separado, **todos** con `ModuleNotFoundError: No module named 'app.application.ml.inventario_declaracion_previa_del_protocolo'`.
- **G2 (`3`) y G3 (`4`):** pasan, lo que confirma sobre el código existente las premisas A1, A2, A4 y A11 y los invariantes.

Las huellas de AE-52 y de AE-63 a AE-68 se calcularon en la base antes de implementar y se fijaron como literales en G2.

**Mediciones en el sandbox Linux de Claude** (Python `3.11.15`, sin datos reales), en una única corrida:
- **Nuevas:** `42 passed` (código `0`).
- **AE-60 a AE-69:** `250 passed` (código `0`).
- **Focalizadas:** `948 + 42 = 990 passed` (código `0`).
- **Suite completa:** `5193 + 42 = 5235 passed`, `0 skipped`, código `0`, con los cinco `DeprecationWarning` conocidos de Alembic.
- **`pip check` y `git diff --check`:** código `0`.

**Límites:**
- AE-69 inventaría y comprueba estructura. **No** fija R0, R9 ni ninguna condición, **no** autentica R0 y **no** elige ubicación, formato, mecanismo, esquema de firma, regla ni valor.
- Los valores de las declaraciones sintéticas son datos de prueba, no propuestas.
- F1, F2, O3, N2 y U1 siguen pendientes. Todas las decisiones siguen sin valor. `ESTADO_EXPEDIENTE` sigue en `expediente_sin_eleccion` y `AUTORIZA_EVALUACION = False`.

**Validación real del operador en Windows** (Python `3.14.6`, pytest `9.1.1`; evidencia atribuida al usuario, no ejecutada por Claude):
- **Entorno:** rama `feature/ae69-inventario-declaracion-previa-del-protocolo`; base y HEAD antes de aplicar `9cd222c9b825c99cc2925b0c4c41bb867df113c1`.
- **Parche:** el completo `ae69-inventario-declaracion-previa-del-protocolo.patch`, SHA-256 `3df6a8399421e9d04fe44838a17dd1c8c9d504c2e6f34c6b254862ea5f8d2822`, con el hash comprobado.
- **Aplicación:** `git apply --check`, la aplicación, `git apply --reverse --check` y `git diff --check` fueron correctos, con exactamente los cinco archivos previstos.
- **Pruebas de AE-69:** `42 passed in 0.39s`.
- **AE-60 a AE-69:** `250 passed in 1.13s`.
- **`pip check`:** `No broken requirements found`.

**En Windows no se ejecutaron las focalizadas ni la suite completa.** Las cifras `990 passed` (focalizadas) y `5235 passed, 0 skipped` (suite completa) corresponden únicamente al sandbox Linux de Claude.

**Límites de esta validación**: «validada» cubre solo **el inventario preparatorio del contenido de R0 y sus pruebas**.
- `completa_sintetica_sin_autenticar` solo acredita la presencia estructural de los once elementos: **no** valida la suficiencia de sus valores, **no** autentica ni fija R0 y **no** satisface ninguna condición del protocolo.
- Los once elementos siguen `pendiente`, y R0, R9 y las ocho condiciones siguen `sin_fijar`; los tres elementos de autenticación de R0 siguen pendientes.
- **No** se elige ubicación ni formato de la declaración, mecanismo, esquema de firma, regla ni valor, y AE-52 no cambia.
- Lo que procede de RFC 9162 conserva el alcance de certificados y precertificados registrado en AE-67; no se atribuye al RFC ninguna garantía para nuestras entradas.
- F1, F2, O3, N2 y U1 siguen **pendientes**.
- Todas las decisiones siguen sin valor. El expediente sigue en `expediente_sin_eleccion` con `AUTORIZA_EVALUACION = False`.

Siguen igual:
- el NO-GO de AE-39 y los bloqueos de AE-41 y AE-46;
- los siete pendientes de AE-52, abiertos;
- la especificación candidata de AE-53, sin aprobar.

Con esta evidencia, **AE-69 queda validada como inventario preparatorio del contenido de R0 y sus pruebas**; no equivale a declarar, autenticar ni fijar R0, a fijar ninguna condición ni a elegir un mecanismo.

No se usaron datos reales, PostgreSQL, entrenamiento ni predicciones reales. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-68 sin cambios.

**Etapa AE-70 -criterios verificables de vinculación entre el contenido de R0 y el protocolo de AE-52, validada:** AE-69 inventarió los once elementos del contenido de R0 y aportó el hash de una declaración sintética. Dejó sin respuesta dónde viviría esa declaración y cómo se expresarían sus pendientes. AE-70 **no responde esas preguntas**. En el nuevo módulo puro `app/application/ml/vinculo_declaracion_previa_con_protocolo.py` registra:
- las topologías candidatas de vínculo;
- los criterios K1–K7;
- los supuestos S1–S4;
- una matriz topología × criterio cuyas celdas exponen sus supuestos.

Las tres preguntas de AE-69 siguen `sin_respuesta`, `TOPOLOGIA_ELEGIDA = None` y `REPRESENTACION_ELEGIDA = None`. AE-52 y AE-63 a AE-69 no cambian.

**Hallazgos sobre AE-52**, observados en el código de `b278d88` y comprobados con su API pública:
- Cada predicción exige un `protocolo_hash` igual al hash de los bytes canónicos del protocolo.
- `estrategia.parametros` solo se comprueba como objeto, así que hoy admitiría una clave con un hash. Un valor distinto ahí se conserva en los bytes canónicos, cambia el hash del protocolo y llega al `protocolo_hash` de la predicción reconstruida. Esto está comprobado en ejemplos.
- Un segundo protocolo en el mismo registro se rechaza.
- El protocolo real es un borrador con los siete pendientes y no admite predicciones.

**Supuestos** (`SUPUESTOS_DEL_MODELO`), visibles en cada conclusión que depende de ellos:
- **S1:** SHA-256 se trata como resistente a colisiones. Se **supone**, no se verifica.
- **S2:** el verificador dispone de los bytes canónicos del protocolo y comprueba su hash.
- **S3:** la regla de vínculo está declarada. En AE-70 es un parámetro de prueba, no una decisión.
- **S4:** existe un único manifiesto reconocido por protocolo. Es un requisito pendiente.

**Topologías** (`TOPOLOGIAS_DE_VINCULO`, ninguna elegida):
- `directo_en_nuevo_esquema`: un campo nuevo; exige cambiar el formato de AE-52.
- `directo_en_campo_existente_no_previsto`: el hash en `estrategia.parametros`; el formato lo admite hoy, pero reinterpreta el campo.
- `inverso_desde_la_declaracion`: la declaración lleva el `protocolo_hash`.
- `manifiesto_externo`: un tercer documento enlaza ambos hashes.

**Criterios** (`CRITERIOS_DE_VINCULO`):
- **K1 `compromiso_transitivo_verificable`:** exige los **bytes canónicos del protocolo** y la **regla declarada**. **El `protocolo_hash` aislado no basta**: es un digest y no permite obtener nada. Ninguna función pública recibe solo el digest.
- **K2 `designacion_unica_por_el_vinculo`:** el vínculo designa **como máximo un hash de declaración** bajo el modelo. **No afirma unicidad de las declaraciones existentes ni ausencia de colisiones**, que dependen de S1.
- **K3** sin cambio de formato de AE-52.
- **K4** sin reinterpretar campos.
- **K5** pendientes explícitos.
- **K6** no implica autenticación.
- **K7** no aporta anterioridad.

**Matriz** (`MATRIZ_DE_VINCULO`; cada celda tiene estado, supuestos, afirmaciones y alcance):

| Topología | K1 | K2 | K3 | K4 |
|---|---|---|---|---|
| directo, nuevo esquema | cumple en el modelo bajo S1, S2, S3 | cumple en el modelo bajo S2, S3 (S1 para el contenido) | no cumple por definición | cumple por definición |
| directo, campo no previsto | cumple en el modelo bajo S1, S2, S3; propagación observada con AE-52 real | cumple en el modelo bajo S2, S3 (S1 para el contenido) | cumple por definición | no cumple por definición |
| inverso | no cumple (contraejemplo: los bytes no designan nada) | no cumple (contraejemplo: dos declaraciones distintas aceptadas) | cumple por definición | cumple por definición |
| manifiesto externo | depende de S4 | depende de S4 (dos manifiestos designan dos hashes) | cumple por definición | cumple por definición |

- **K5** es independiente de la topología y se evalúa sobre `REPRESENTACIONES_DE_PENDIENTES`.
- **K6 y K7** se cumplen por definición: ninguna topología pretende autenticar ni fechar.
- **Cumplir en el modelo no significa acreditación, suficiencia ni conformidad** (`ALCANCE_DEL_ANALISIS`).

**Representación de pendientes** (`REPRESENTACIONES_DE_PENDIENTES`, ninguna elegida):
- `estado_pendiente_por_elemento`: las formas de AE-69; se hashea.
- `ampliar_pendientes_de_ae52`: exige cambiar el formato, porque hoy se rechaza.
- `ausencia_implicita`: AE-69 la trata como `incompleta`.

**Consecuencia** (`CONSECUENCIA_DE_COMPLETAR_DESPUES`): bajo vínculo directo, completar un pendiente después cambia el hash designado y el del protocolo. El resultado es otro protocolo, que no cabe en el mismo registro de AE-52; las predicciones previas siguen ligadas a la versión anterior.

**Funciones puras** (el campo lo aporta quien llama; nada se fija):
- `hash_designado(topologia, bytes_protocolo, protocolo_hash, regla)`;
- `declaraciones_que_verifican(...)`;
- `celda(topologia, criterio)`.

**Afirmaciones** (`CLASIFICACION_DE_AFIRMACIONES`, B1–B15), con procedencia exacta:
- **Hechos observados en el código** (`@b278d88` y la prueba que los observa): B1–B6.
- **Derivaciones propias** (premisas resolubles, incluidos los supuestos): B7–B12 y B15.
- **Hipótesis de aplicación** (pendiente): B13.
- **Hecho citado de fuente:** B14, *AE-67 verificó RFC 9162 para registros de certificados y precertificados*, con `AE-67:C1`…`C7`.
- **Derivación separada:** B15 se deriva de B14, **sin atribuirla al RFC**. Lo verificado **no aporta una garantía** aplicable a un manifiesto de predicciones ni a nuestras entradas, y no se afirma que ese uso sea imposible.

No hay citas primarias nuevas.

**Archivos** (exactamente cinco):
- nuevo `app/application/ml/vinculo_declaracion_previa_con_protocolo.py`;
- nuevo `tests/unit/ml/test_vinculo_declaracion_previa_con_protocolo.py`;
- README, ROADMAP y ARCHITECTURE: esta sección.

**Pruebas** (`21` sintéticas en tres grupos; el módulo nuevo se importa dentro de cada prueba de G1):
- **G1 (`13`), dependen del módulo nuevo:**
  - registros y matriz;
  - celdas esperadas;
  - K1 sin el digest aislado;
  - K1 con AE-52 real en ejemplos;
  - K2 con sus contraejemplos inverso y manifiesto;
  - K6 y K7;
  - completar después;
  - representaciones;
  - preguntas de AE-69 sin respuesta;
  - B14 separado de B15;
  - clasificación con procedencia;
  - pureza por AST y vocabulario.
- **G2 (`2`), invariantes:**
  - huellas de AE-52 y de AE-63 a AE-68 sin cambios;
  - huella de AE-69 calculada en la base (`b5637fe7…d83a24`);
  - estados, decisiones y bloqueos.
- **G3 (`6`), integraciones contra la API pública de AE-52 y AE-69:**
  - B1–B6, incluida la propagación de `parametros` a los bytes, al hash y a la predicción reconstruida;
  - el rechazo por `protocolo_hash` aislado, con la cadena correcta.

**Pruebas primero, sobre la base `b278d88`.** Antes de escribir el módulo se ejecutaron los tres grupos. El resultado fue `13 failed, 8 passed`, con código de pytest `1`:
- **G1:** las `13` fallan por separado, **todas** con `ModuleNotFoundError: No module named 'app.application.ml.vinculo_declaracion_previa_con_protocolo'`.
- **G2 (`2`) y G3 (`6`):** pasan. En particular, G3 confirma sobre AE-52 real que el cambio en `estrategia.parametros` se conserva en los bytes canónicos, cambia el hash del protocolo y llega al `protocolo_hash` de la predicción reconstruida.

Las huellas de AE-52 y de AE-63 a AE-69 se calcularon en la base antes de implementar y se fijaron como literales en G2.

**Mediciones en el sandbox Linux de Claude** (Python `3.11.15`, sin datos reales), en una única corrida:
- **Nuevas:** `21 passed` (código `0`).
- **AE-60 a AE-70:** `271 passed` (código `0`).
- **Focalizadas:** `990 + 21 = 1011 passed` (código `0`).
- **Suite completa:** `5235 + 21 = 5256 passed`, `0 skipped`, código `0`, con los cinco `DeprecationWarning` conocidos de Alembic.
- **`pip check` y `git diff --check`:** código `0`.

**Límites:**
- AE-70 especifica criterios y los prueba sobre modelos sintéticos. **No** elige topología, representación, campo ni mecanismo, **no** fija R0 y **no** aporta autenticación, anterioridad ni suficiencia.
- `completa_sintetica_sin_autenticar` sigue indicando solo completitud estructural.
- RFC 9162 conserva el alcance de certificados y precertificados.
- R0, R9 y las ocho condiciones siguen `sin_fijar`; F1, F2, O3, N2 y U1 siguen pendientes.
- Todas las decisiones siguen sin valor. `ESTADO_EXPEDIENTE` sigue en `expediente_sin_eleccion` y `AUTORIZA_EVALUACION = False`.

**Validación real del operador en Windows** (Python `3.14.6`, pytest `9.1.1`; evidencia atribuida al usuario, no ejecutada por Claude):
- **Entorno:** rama `feature/ae70-vinculo-declaracion-previa-con-protocolo`; HEAD y base `b278d883752d1f1101544c093baec2044cda860d`.
- **Parche:** el completo `ae70-vinculo-declaracion-previa-con-protocolo.patch`, SHA-256 `109a4f1b348a723e2951073b6a421993bb1f196252bdc392b04c57c4fbb0b549`, con el hash comprobado.
- **Aplicación:** la aplicación, `git apply --reverse --check` y `git diff --check` fueron correctos, con exactamente los cinco archivos previstos.
- **Pruebas de AE-70:** `21 passed in 0.57s`.
- **AE-60 a AE-70:** `271 passed in 3.12s`.
- **`pip check`:** `No broken requirements found`.

**En Windows no se ejecutaron las focalizadas ni la suite completa.** Las cifras `1011 passed` (focalizadas) y `5256 passed, 0 skipped`, con los cinco avisos conocidos de Alembic (suite completa), corresponden únicamente al sandbox Linux de Claude y no se repitieron para este cierre.

**Límites de esta validación**: «validada» cubre solo **el modelo preparatorio de vinculación y sus pruebas**.
- S1 sigue siendo una hipótesis: SHA-256 se trata como resistente a colisiones, sin verificarlo.
- K1 requiere los bytes canónicos del protocolo y una regla declarada; el `protocolo_hash` aislado no basta.
- K2 solo dice que el vínculo designa como máximo un hash de declaración bajo el modelo.
- **No** se acredita unicidad de las declaraciones existentes, suficiencia, autenticación, anterioridad ni aplicación operativa.
- `TOPOLOGIA_ELEGIDA` y `REPRESENTACION_ELEGIDA` siguen en `None`, y las tres preguntas de AE-69 siguen abiertas.
- RFC 9162 conserva el alcance de certificados y precertificados registrado en AE-67.
- R0, R9 y las ocho condiciones siguen `sin_fijar`; F1, F2, O3, N2 y U1 siguen **pendientes**.
- No se elige ni autoriza inferencia o evaluación. Todas las decisiones siguen sin valor, y el expediente sigue en `expediente_sin_eleccion` con `AUTORIZA_EVALUACION = False`.

Siguen igual:
- el NO-GO de AE-39 y los bloqueos de AE-41 y AE-46;
- los siete pendientes de AE-52, abiertos;
- la especificación candidata de AE-53, sin aprobar.

Con esta evidencia, **AE-70 queda validada como modelo preparatorio de vinculación y sus pruebas**; no equivale a elegir topología, representación, campo ni mecanismo, ni a fijar o autenticar R0.

No se usaron datos reales, PostgreSQL, entrenamiento ni predicciones reales. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-69 sin cambios.

**Etapa AE-71 -comparación verificable de las alternativas de declaración previa R0 y de la distinción «sin fijar / ausente / fijado», validada:** AE-69 dejó tres preguntas abiertas (ubicación de la declaración, representación de sus pendientes y regla de vínculo), y AE-70 registró cuatro topologías de vínculo. AE-71 **compara esas topologías sin elegir ninguna**, en el nuevo módulo puro `app/application/ml/analisis_alternativas_de_declaracion_previa.py`. También examina si la representación de AE-69 distingue de forma verificable «sin fijar», «ausente» y «fijado».

**No se implementa** ninguna topología ni representación. **No se responden** las preguntas de AE-69. D1–D9 siguen `sin_decidir`, `TOPOLOGIA_ELEGIDA` y `REPRESENTACION_ELEGIDA` siguen en `None`, y AE-52 y AE-63 a AE-70 no cambian.

**Tres planos separados** (`SEPARACION_DE_PLANOS`):
1. **Dependencia entre bytes:** un protocolo que contiene `H(D)` depende de los bytes de `D`, y lo comprueba un tercero que tenga ambos.
2. **Evidencia temporal sobre esos bytes:** un sello o una recepción externa con reloj y margen. Está pendiente.
3. **Fijación autenticada de R0:** pendiente.

El primer plano no implica los otros dos:
- **S5** (`SUPUESTOS_ADICIONALES_AE71`) es la resistencia a preimagen y a segunda preimagen de SHA-256, supuesta y no verificada. Solo sostiene que no es factible presentar después otra declaración distinta con el mismo hash designado. **No es prueba temporal.**
- **Pasar a una cronología** exige H-a a H-d (`HIPOTESIS_PARA_CRONOLOGIA`), todas `pendiente`: sello o recepción externa previa al plazo, autenticación de la declaración, definición del plazo y del corte, y S5.

**Fichas por topología** (`FICHAS_POR_TOPOLOGIA`). Para cada topología de AE-70 registran:
- qué fijar antes del plazo;
- qué bytes se verifican;
- qué cambios de esquema y de pruebas exigiría;
- qué comprueba un tercero y qué no queda demostrado;
- la dependencia entre bytes;
- cómo se identifica la regla;
- la consecuencia de cambiar la declaración;
- las decisiones pendientes.

| | Nuevo esquema | `estrategia.parametros` | Inverso | Manifiesto (modelo sintético) |
|---|---|---|---|---|
| Dependencia entre bytes | el protocolo depende de la declaración, y la predicción del protocolo | igual | la declaración depende del protocolo; el protocolo **no** depende de la declaración | el manifiesto depende de ambos; el protocolo no depende de la declaración |
| Identificación de la regla | la versión incluida en los bytes **puede** identificarla **si D4** fija la definición y su correspondencia; los bytes no contienen por sí solos toda la semántica | externa a los bytes (S3) | no aplica | dentro del manifiesto, sujeta a S4 |
| Cambiar la declaración vinculada | otro protocolo, que AE-52 no admite en el mismo registro; hace falta otro registro | igual | el protocolo no cambia y las declaraciones coexisten | en el modelo sintético de AE-70, sin formato ni garantía operativa: otro manifiesto designa el hash nuevo según S4 |
| Además no demuestra | — | ambigüedad de la regla | designación única; nada en los bytes impide construir la declaración después de las predicciones | lo mismo, trasladado al manifiesto |

Todas las fichas dejan fuera de lo demostrado:
- la **cronología**: cuándo existió, se publicó o se recibió la declaración;
- la autenticación;
- la unicidad del protocolo;
- la suficiencia de los valores;
- la completitud de las predicciones.

`dependencia_de_bytes` siempre devuelve la marca `sin_cronologia_acreditada`.

**Distinción de estados** (`DISTINCION_DE_ESTADOS`, `estado_verificable_de_elemento`):
- **Sin fijar:** `{"estado": "pendiente"}`, explícito y hasheable.
- **Ausente:** clave omitida; da `incompleta` y no se hashea.
- **Declarado sintético:** `declarado_sintetico` con un valor sustantivo.
- **Fijado:** **no es representable en los bytes sintéticos de AE-69**. Exige cuatro componentes (`COMPONENTES_DE_FIJADO`), todos `no_acreditado`:
  - F-1, integridad y autenticación de la declaración;
  - F-2, regla de vínculo;
  - F-3, recepción previa al plazo con reloj, margen y canal;
  - F-4, definición del corte y del plazo.

La función nunca devuelve «fijado».

**Lagunas observadas** (`LAGUNAS_DE_DISTINCION`; AE-71 no las corrige):
- **L1:** un texto marcador dentro de `valor` («pendiente», «TBD») cuenta como declarado.
- **L2:** AE-69 no tiene un estado para «fijado».
- **L3:** AE-69 no comprueba la estructura interna de cada valor.

**Decisiones del operador** (`DECISIONES_DEL_OPERADOR_AE71`, todas `sin_decidir`):
- **D1:** topología.
- **D2:** representación de pendientes.
- **D3:** campo o ruta.
- **D4:** definición del esquema o de la regla y su correspondencia con la versión.
- **D5:** envoltorio para el vínculo inverso.
- **D6:** manifiesto.
- **D7:** pendientes al registrar.
- **D8:** plazo frente a corte.
- **D9:** rechazo de textos marcadores.

`DEPENDENCIAS_QUE_IMPIDEN_IMPLEMENTAR`: toda topología requiere al menos D1, D2 y D7. Una etapa que implemente cualquiera de ellas requiere decisiones explícitas del operador.

**Afirmaciones** (`CLASIFICACION_DE_AFIRMACIONES`, C1–C18), con procedencia exacta:
- **Hechos observados en el código** (`@8137f93`, cada uno con su prueba G3): C1–C6.
- **Hecho citado:** C7, AE-67 verificó RFC 9162 para certificados y precertificados.
- **Derivaciones propias:** C8–C15. C14 se deriva de C7 **sin atribuirla al RFC**: no aporta una garantía aplicable a un manifiesto de predicciones, y no se afirma que ese uso sea imposible.
- **Hipótesis de aplicación pendientes:** C16–C18.

**Archivos** (exactamente cinco):
- nuevo `app/application/ml/analisis_alternativas_de_declaracion_previa.py`;
- nuevo `tests/unit/ml/test_analisis_alternativas_de_declaracion_previa.py`;
- README, ROADMAP y ARCHITECTURE: esta sección.

**Pruebas** (`27` sintéticas en tres grupos; el módulo nuevo se importa dentro de cada prueba de G1):
- **G1 (`18`), dependen del módulo nuevo:**
  - fichas y decisiones;
  - límites de lo no demostrado;
  - dependencia entre bytes sin cronología;
  - S5 e hipótesis;
  - componentes de «fijado»;
  - estados verificables y el contraejemplo L1;
  - regla externa;
  - C15 por topología;
  - C11;
  - digest sin bytes coincidentes;
  - vocabulario de resultados;
  - C7 separado de C14;
  - clasificación;
  - pureza por AST y textos.
- **G2 (`2`), invariantes:**
  - huellas de AE-52 y de AE-63 a AE-69 sin cambios;
  - huella de AE-70 calculada en la base (`23c62200…648350`);
  - estados, decisiones y bloqueos.
- **G3 (`7`), integraciones contra la API pública de AE-52, AE-69 y AE-70:** C1–C6 y la premisa de C15. Comprueban que AE-52 rechaza un segundo protocolo en el mismo registro y que un registro distinto admite el protocolo nuevo.

**Pruebas primero, sobre la base `8137f93`.** Antes de escribir el módulo se ejecutaron los tres grupos. El resultado fue `18 failed, 9 passed`, con código de pytest `1`:
- **G1:** las `18` fallan por separado, **todas** con `ModuleNotFoundError: No module named 'app.application.ml.analisis_alternativas_de_declaracion_previa'`.
- **G2 (`2`) y G3 (`7`):** pasan. G3 confirma en AE-52 real la premisa de C15: un segundo protocolo en el mismo registro se rechaza y un registro distinto admite el protocolo nuevo.

Durante la implementación, tres pruebas de G1 fallaron y se corrigieron:
- **Texto del módulo:** S5 decía «No es prueba temporal» con mayúscula; se ajustó el texto del módulo, no la prueba.
- **Montaje de dos pruebas:**
  - la comprobación de resultados no excluía los marcadores negados (`sin_…`, `no_…`);
  - la de vocabulario no quitaba los identificadores fijos `sin_cronologia_acreditada` y «fijacion autenticada», como AE-68 hacía con `identidad_autorizada`.

Con el archivo de pruebas final se repitió la comprobación sobre una copia limpia de la base sin el módulo. El resultado volvió a ser `18 failed` (todas `ModuleNotFoundError`) y `9 passed`, con código `1`.

Las huellas de AE-52 y de AE-63 a AE-70 se calcularon en la base antes de implementar y se fijaron como literales en G2.

**Mediciones en el sandbox Linux de Claude** (Python `3.11.15`, sin datos reales), en una única corrida:
- **Nuevas:** `27 passed` (código `0`).
- **AE-60 a AE-71:** `298 passed` (código `0`).
- **Focalizadas:** `1011 + 27 = 1038 passed` (código `0`).
- **Suite completa:** `5256 + 27 = 5283 passed`, `0 skipped`, código `0`, con los cinco `DeprecationWarning` conocidos de Alembic.
- **`pip check` y `git diff --check`:** código `0`.

**Límites:**
- AE-71 compara alternativas y modela. **No** elige topología, representación, campo ni mecanismo, y **no** implementa ninguna.
- Una dependencia entre bytes, S5 o un hash **no** son prueba temporal, y **no** acreditan autenticación, suficiencia ni completitud.
- «Fijado» exige F-1 a F-4, ninguno disponible.
- RFC 9162 conserva el alcance de certificados y precertificados.
- R0, R9 y las ocho condiciones siguen `sin_fijar`; las tres preguntas de AE-69 siguen abiertas; F1, F2, O3, N2 y U1 siguen pendientes.
- Todas las decisiones siguen sin valor. `ESTADO_EXPEDIENTE` sigue en `expediente_sin_eleccion` y `AUTORIZA_EVALUACION = False`.

**Validación real del operador en Windows** (Python `3.14.6`, pytest `9.1.1`; evidencia atribuida al usuario, no ejecutada por Claude):
- **Entorno:** rama `feature/ae71-analisis-alternativas-de-declaracion-previa`; base y HEAD `8137f937b4851b0c671756fce231fe13a3479450`.
- **Parche:** el completo `ae71-analisis-alternativas-de-declaracion-previa.patch`, SHA-256 `5c44463a7511f246dad1831f5042763ea27bbcd26c384999cf17c8271d9af964`, con el hash comprobado.
- **Aplicación:** la aplicación, `git apply --reverse --check` y `git diff --check` fueron correctos, con exactamente los cinco archivos previstos.
- **Pruebas de AE-71:** `27 passed in 0.30s`.
- **AE-60 a AE-71:** `298 passed in 1.51s`.
- **`pip check`:** `No broken requirements found`.

**En Windows no se ejecutaron las focalizadas ni la suite completa.** Las cifras `1038 passed` (focalizadas) y `5283 passed, 0 skipped`, con los cinco avisos conocidos de Alembic (suite completa), corresponden únicamente al sandbox Linux de Claude y no se repitieron para este cierre.

**Límites de esta validación**: «validada» cubre solo **el análisis preparatorio de alternativas y sus pruebas**.
- La dependencia entre bytes y S5 **no** acreditan cronología. H-a a H-d siguen pendientes, y ninguno de los cuatro componentes F-1 a F-4 está acreditado.
- «Fijado» **no** se obtiene de la declaración sintética de AE-69.
- El segundo manifiesto es solo un contraejemplo del modelo sintético; no se ha adoptado formato ni garantía operativa.
- D1–D9 siguen `sin_decidir`, y las tres preguntas de AE-69 siguen abiertas. `TOPOLOGIA_ELEGIDA` y `REPRESENTACION_ELEGIDA` siguen en `None`.
- R0, R9 y las ocho condiciones siguen `sin_fijar`; F1, F2, O3, N2 y U1 siguen **pendientes**.
- RFC 9162 conserva el alcance de certificados y precertificados registrado en AE-67.
- No se elige ni autoriza inferencia o evaluación. Todas las decisiones siguen sin valor, y el expediente sigue en `expediente_sin_eleccion` con `AUTORIZA_EVALUACION = False`.

Siguen igual:
- el NO-GO de AE-39 y los bloqueos de AE-41 y AE-46;
- los siete pendientes de AE-52, abiertos;
- la especificación candidata de AE-53, sin aprobar.

Con esta evidencia, **AE-71 queda validada como análisis preparatorio de alternativas y sus pruebas**; no equivale a elegir topología, representación, campo ni mecanismo, ni a fijar, fechar o autenticar R0.

No se usaron datos reales, PostgreSQL, entrenamiento ni predicciones reales. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-70 sin cambios.

**Etapa AE-72 -prototipo optativo de vínculo entre la declaración R0 y el protocolo de AE-52, validada:** es el primer recorrido de extremo a extremo con las API reales de AE-52: declaración R0 sintética versionada (`declaracion-r0-sintetica/1`) → bytes y hash → protocolo sintético candidato → predicción sintética → verificación del vínculo. Está en el nuevo módulo puro `app/application/ml/prototipo_vinculo_declaracion_r0.py` y sus `34` pruebas.

**Topología y verificador:**
- La topología es la **candidata** `directo_en_campo_existente_no_previsto` de AE-70, con regla `ae72-vinculo-r0-en-parametros/1` y activación **optativa**.
- No se elige nada: `TOPOLOGIA_ELEGIDA` y `REPRESENTACION_ELEGIDA` siguen en `None`, D1–D9 `sin_decidir`, y AE-52 y AE-63 a AE-71 no cambian.
- El verificador solo comprueba **integridad de bytes**. La autenticación de R0, la recepción antes del plazo y la completitud y unicidad del canal quedan `sin_evidencia`, y la aptitud inferencial `no_autorizada`.

La arquitectura, el uso, la compatibilidad, las decisiones todavía requeridas, los criterios para promover o descartar la candidata y las mediciones están en la sección AE-72 de `ARCHITECTURE.md`.

R0, R9 y las ocho condiciones siguen `sin_fijar`; F1, F2, O3, N2 y U1 siguen pendientes; `expediente_sin_eleccion` y `AUTORIZA_EVALUACION = False`.

AE-72 queda **validada solo como prototipo sintético optativo y sus pruebas**. La clave en `estrategia.parametros` sigue siendo una candidata optativa, no una decisión adoptada, y D1–D9 siguen sin decidir.

**Validación del operador en Windows** (atribuida al usuario): rama `feature/ae72-prototipo-vinculo-declaracion-r0`, base y HEAD `60cde6d`, SHA-256 del parche completo comprobado, cinco archivos. Con Python `3.14.6` y pytest `9.1.1`: `34 passed in 0.34s` (AE-72), `332 passed in 0.97s` (AE-60 a AE-72) y `pip check` sin problemas. Las focalizadas (`1072 passed`) y la suite completa (`5317 passed, 0 skipped`) solo se ejecutaron en Linux. El detalle y los límites están en la sección AE-72 de `ARCHITECTURE.md`.

No se usaron sorteos reales, PostgreSQL, entrenamiento, inferencia operativa ni sello temporal real. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-71 sin cambios.

**Etapa AE-73 -campo explícito y versionado para vincular la declaración R0 en el protocolo de AE-52, validada:** AE-52 admite ahora, de forma optativa, la versión `registro-prospectivo-ml/1.1` de la entrada `protocolo`.
- **El campo:** `declaracion_r0` guarda la regla `ae73-vinculo-r0-campo-explicito/1`, el esquema de la declaración, el hash designado y los pendientes explícitos. Así el vínculo con la declaración R0 no ocupa `estrategia.parametros`.
- **Validación:** es estricta y cada rechazo lleva un `motivo` distinguible.
- **Solo sintético:** la versión 1.1 solo se admite en protocolos sintéticos.
- **Compatibilidad:** los protocolos 1.0, las predicciones, los resultados y la ruta candidata de AE-72 no cambian.
- **Código:** el nuevo módulo `app/application/ml/vinculo_r0_campo_explicito.py` verifica las dos rutas de extremo a extremo con datos sintéticos, compara ambas y documenta la migración sin ejecutarla. Lo acompañan `52` pruebas.

**Límites:**
- Las dos rutas son candidatas: D1–D9 siguen `sin_decidir`, sobre todo D1, D2 y D7.
- Solo se comprueba integridad de bytes. La autenticación de R0, la recepción anterior al plazo y la completitud y unicidad del canal quedan `sin_evidencia`, y la aptitud inferencial `no_autorizada`.

El detalle, la comparación, la compatibilidad y las mediciones están en la sección AE-73 de `ARCHITECTURE.md`.

R0, R9 y las ocho condiciones siguen `sin_fijar`; F1, F2, O3, N2 y U1 siguen pendientes; `expediente_sin_eleccion` y `AUTORIZA_EVALUACION = False`.

AE-73 queda **validada solo como extensión optativa y sintética del esquema, su verificador y sus pruebas**. La versión 1.1 sigue siendo optativa, D1–D9 siguen sin decidir y no se ejecutó migración.

**Validación del operador en Windows** (atribuida al usuario): rama `feature/ae73-vinculo-r0-campo-explicito`, HEAD y base `46815bf`, SHA-256 del parche completo comprobado, seis archivos. Con Python `3.14.6` y pytest `9.1.1`: `52 passed in 0.51s` (AE-73), `110 passed in 12.06s` (AE-52), `384 passed in 1.41s` (AE-60 a AE-73) y `pip check` sin problemas. Las focalizadas (`1124 passed`) y la suite completa (`5369 passed, 0 skipped`) solo se ejecutaron en Linux. El detalle y los límites están en la sección AE-73 de `ARCHITECTURE.md`.

No se usaron sorteos reales, PostgreSQL, entrenamiento, inferencia operativa ni sello temporal real. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-72 sin cambios.

**Etapa AE-74 -contrato de vinculación R0 elegido por el operador (versión 1.2 de AE-52), validada:** el operador aprobó tres decisiones:
- **D1:** el campo explícito versionado es la única ruta del contrato, con el contrato `contrato-vinculo-r0/1` y la regla `ae74-vinculo-r0-contrato/1` escritos en los bytes mediante la versión `registro-prospectivo-ml/1.2`.
- **D2:** estados por elemento y lista ordenada de pendientes comprobada contra la declaración.
- **D7:** pendientes solo en borradores sintéticos.

D9 queda en espera provisional y D8 sigue abierta.

**Cómo responde el contrato:** el nuevo módulo `app/application/ml/contrato_vinculo_r0.py` evalúa cuatro puertas independientes, con motivos precisos: borrador sintético, vínculo íntegro, declaración estructuralmente completa y R0 final.
- Un borrador con pendientes puede tener un vínculo íntegro sin ser completo.
- La puerta R0 final no puede superarse con la evidencia existente.

**Compatibilidad:** 1.0, AE-72 y 1.1 conservan bytes y comportamiento, pero el contrato no las admite. Hay `41` pruebas nuevas.

El detalle, la demostración reproducible de los estados, la compatibilidad y los requisitos faltantes están en la sección AE-74 de `ARCHITECTURE.md`.

R0, R9 y las ocho condiciones siguen `sin_fijar`; F1, F2, O3, N2 y U1 siguen pendientes; `expediente_sin_eleccion` y `AUTORIZA_EVALUACION = False`.

AE-74 queda **validada solo como contrato versionado sintético, con sus puertas de admisión y sus pruebas**. La versión 1.2 solo admite protocolos sintéticos, D8 sigue abierta, D9 solo tiene la espera provisional y `r0_final` no puede superarse con la evidencia actual.

**Validación del operador en Windows** (atribuida al usuario): rama `feature/ae74-contrato-vinculo-r0`, HEAD y base `9a6740e`, SHA-256 del parche completo comprobado, siete archivos. Con Python `3.14.6` y pytest `9.1.1`: `41 passed in 0.51s` (AE-74), `110 passed in 4.89s` (AE-52), `425 passed in 1.63s` (AE-60 a AE-74) y `pip check` sin problemas. Las focalizadas (`1165 passed`) y la suite completa (`5410 passed, 0 skipped`) solo se ejecutaron en Linux. El detalle y los límites están en la sección AE-74 de `ARCHITECTURE.md`.

No se usaron sorteos reales, PostgreSQL, entrenamiento, inferencia operativa, sellos, firmas, relojes ni canales reales. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-73 sin cambios.

**Etapa AE-75 -sello temporal RFC 3161 del compromiso R0 por objetivo, validada:** el operador aprobó D8 y la política de confianza temporal con seis ajustes.
- **Compromiso por objetivo:** `compromiso-sello-r0-objetivo/1` sella la versión, el contrato, la regla, `protocolo_hash`, `hash_declaracion`, el juego, el objetivo y un plazo UTC sintético. Un sello de un objetivo no sirve para otro.
- **Regla estricta:** «anterior» solo si `genTime + accuracy + margen < plazo`. La igualdad no pasa, cruzar el plazo no es concluyente y sin `accuracy` queda pendiente.
- **Criptografía con bibliotecas mantenidas:**
  - `rfc3161-client` 1.0.9, con OpenSSL incorporado, hace la verificación integral frente a un ancla explícita;
  - `cryptography` 50.0.1 comprueba certificados y firma, y su decodificador DER lee `genTime` exacto y `SigningCertificateV2`.
- **Anclas y políticas:** solo de prueba. La revocación sin comprobar deja todo `pendiente`.

El nuevo plano `sello_temporal_de_r0` se añade al informe de AE-74 sin tocar `evaluar_admision` ni `r0_final`. **No prueba autenticación de R0, recepción de predicciones ni completitud o unicidad del canal.** D8 queda aprobada solo para el modelo sintético; el plazo operativo y `calendario_oficial` siguen sin fijar.

El detalle, lo que comprueba cada herramienta, las citas de RFC 3161 y RFC 5816, los resultados por caso, las pruebas y los límites están en la sección AE-75 de `ARCHITECTURE.md`.

R0, R9 y las ocho condiciones siguen `sin_fijar`; F1, F2, O3, N2 y U1 siguen pendientes; `expediente_sin_eleccion` y `AUTORIZA_EVALUACION = False`.

AE-75 queda **validada solo como implementación y verificación preparatoria sobre datos, anclas y plazos sintéticos**. D8 está aprobada solo para el modelo sintético, el calendario y el plazo operativos no están fijados, la revocación no se comprobó, el ancla es de prueba, el plano temporal no llega a `superada` y `r0_final` sigue rechazada.

**Validación del operador en Windows** (atribuida al usuario): rama `feature/ae75-sello-temporal-r0`, HEAD y base `d4c7da6`, SHA-256 del parche completo comprobado, nueve archivos. Con Python `3.14.6`, pytest `9.1.1` y las dependencias instaladas desde ruedas: `68 passed, 7 skipped in 2.74s` (AE-75), `110 passed in 6.80s` (AE-52), `493 passed, 7 skipped in 3.23s` (AE-60 a AE-75) y `pip check` sin problemas. Las siete omisiones son los contrastes con `openssl ts -verify`, sin OpenSSL en `PATH`: no se ejecutaron en Windows. Esos siete contrastes solo pasaron en el sandbox Linux, igual que las focalizadas (`1240 passed`) y la suite completa (`5485 passed, 0 skipped`). El detalle y los límites están en la sección AE-75 de `ARCHITECTURE.md`.

No se usaron sorteos reales, PostgreSQL, entrenamiento, inferencia operativa, sellos ni autoridades operativas, relojes locales como prueba ni canales reales. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-74 sin cambios.

**Etapa AE-76 -expediente preparatorio de autenticación de R0 y recepción de predicciones, validada localmente como trabajo preparatorio:** añade tres piezas versionadas y firmadas con Ed25519 (`cryptography`).
- **`sobre-autenticacion-r0/1`:** vincula R0, el protocolo 1.2, el contrato y el alcance de la firma.
- **`acuse-recepcion-prediccion/1`:** un acuse por predicción, encadenado.
- **`cierre-canal-predicciones/1`:** el manifiesto del canal.

**Qué detecta y qué no concluye:**
- Detecta una clave no admitida, una firma alterada, un R0 o un protocolo equivocados, un acuse reutilizado en otro objetivo, duplicados, omisiones, reordenamientos, un cierre manipulado y un manifiesto que se declara completo de forma falsa.
- Distingue la completitud respecto del manifiesto, la del registro presentado y la de lo que debió existir; esta última queda pendiente sin evidencia externa.
- Una firma de fixture no prueba identidad, y la hora o la secuencia del canal no prueban recepción antes del plazo.
- El informe conjunto lee AE-74 y AE-75 sin cambiar sus puertas: `r0_final` sigue rechazada.

**Validación automática:** el nuevo workflow `validacion-python-314.yml` usa Python 3.14.
- En Linux ejecuta la suite completa y exige los siete contrastes con `openssl ts -verify`.
- En Windows ejecuta una selección de AE-52 a AE-76 y acepta solo los siete contrastes superados o los siete omitidos, con estado explícito.

El detalle, las decisiones pendientes y los límites están en la sección AE-76 de `ARCHITECTURE.md`.

R0, R9 y las ocho condiciones siguen `sin_fijar`; F1, F2, O3, N2 y U1 siguen pendientes; D8 sigue aprobada solo para el modelo sintético y D9 con su espera provisional; `expediente_sin_eleccion` y `AUTORIZA_EVALUACION = False`.

AE-76 queda **validada localmente como trabajo preparatorio**: el expediente sintético y sus pruebas. **Validación del operador en Windows** (Python `3.14.6`, atribuida al usuario): parche completo comprobado y diez archivos; `40 passed` (AE-76); selección `1273 passed, 7 skipped`, con `OMITIDOS 7/7` sin OpenSSL en `PATH` y cero contrastes superados allí; `1218 passed` en los dos módulos que fallaron con `3.14.0rc2`; `pip check` limpio. Los siete contrastes superados y la suite completa (`5525 passed`) son solo del sandbox Linux con Python `3.11.15`; los `58 failed` de la simulación con `3.14.0rc2` se deben a pydantic con ese candidato. No se afirma que la suite completa haya pasado con Python 3.14 final, y **el workflow todavía no se había ejecutado en GitHub Actions** (después sí: ver AE-77 y, por ejemplo, la ejecución 45). El detalle y los límites están en la sección AE-76 de `ARCHITECTURE.md`.

No se usaron sorteos reales, PostgreSQL, entrenamiento, inferencia operativa, claves, sellos, autoridades ni canales operativos, red ni el reloj local como evidencia. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-75 sin cambios.

**Etapa AE-77 -recepción por objetivo: tiempo por acuse y conjunto esperado externo, validada localmente como trabajo preparatorio:** añade dos piezas independientes.
- **Tiempo por acuse (C2):** `compromiso-sello-acuse/1` sella un acuse firmado concreto. Su token RFC 3161 se verifica con la misma ruta criptográfica de AE-75 (`verificar_token_sobre_bytes`). Se separan sello, impronta, anterioridad respecto del plazo, confianza en el ancla y revocación. Un sello de R0 nunca cuenta como sello de un acuse, y la hora del canal no es prueba.
- **Conjunto esperado (C3):** `conjunto-esperado-observador/1`, firmado por un observador de fixture independiente del canal, declara los objetivos esperados para un corte sintético. Se compara con el registro, los acuses y el cierre de AE-76, y detecta omisiones, extras, duplicados, vínculos incorrectos, firmas alteradas y cambios de corte. Las vistas encadenadas se comprueban por continuidad y contradicciones, sin descartar historias ocultas.

El informe compuesto separa seis planos. La autoridad del manifiesto y la completitud global quedan pendientes, y los estados de AE-74 a AE-76 no cambian: `r0_final` sigue rechazada.

El detalle, la reutilización controlada de AE-75 y los límites están en la sección AE-77 de `ARCHITECTURE.md`.

A1–A3 y C1–C3 siguen sin decidir; D8 sigue limitada al modelo sintético y D9 con su espera provisional. R0, R9 y las ocho condiciones siguen `sin_fijar`; F1, F2, O3, N2 y U1 siguen pendientes; `expediente_sin_eleccion` y `AUTORIZA_EVALUACION = False`.

AE-77 queda **validada localmente como trabajo preparatorio** (piezas y pruebas con fixtures). **Validación del operador en Windows** (Python `3.14.6`, atribuida al usuario): parche completo comprobado y ocho archivos; `29 passed` (AE-77), `110 passed` (AE-52), selección `1302 passed, 7 skipped` y `pip check` limpio. El comprobador informó `OMITIDOS 7/7` sin OpenSSL en `PATH`: esos siete contrastes no se ejecutaron en Windows y no cuentan como éxitos. Solo en el sandbox Linux: `569 passed` (AE-60 a AE-77), `1309 passed` en las focalizadas, suite completa `5554 passed, 0 skipped` y `SUPERADOS 7/7`. **GitHub Actions todavía no ha ejecutado AE-77.** *Actualización: después sí lo ejecutó (ver «Evidencia previa, en CI», sobre `e71a4f5`).* La autoridad del conjunto esperado y la completitud global siguen pendientes. El detalle y los límites están en la sección AE-77 de `ARCHITECTURE.md`.

No se usaron sorteos reales, PostgreSQL, entrenamiento, inferencia operativa, claves, sellos, autoridades, observadores ni canales operativos, red, secretos ni el reloj local como evidencia. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-76 sin cambios.

**Etapa AE-78 -expediente portable y verificador offline de la recepción por objetivo, validada localmente como trabajo preparatorio:** el formato `expediente-portable-recepcion/1` es un directorio con un manifiesto canónico y archivos referenciados por ruta, tamaño y SHA-256.
- **Qué contiene:** registro, declaración, sobre, sellos de R0, acuses con sus sellos, cierre, conjunto esperado y vistas.
- **Qué hace el comando de solo lectura:** `python -m scripts.verificar_expediente_recepcion EXPEDIENTE --politica POLITICA` reproduce offline la evaluación de AE-77 con una política de prueba del verificador suministrada aparte (su ubicación separada no acredita por sí misma custodia ni autoridad independiente), y emite un informe JSON determinista y un resumen.
- **Códigos de salida:** `0` sin rechazos, `1` con rechazos, `2` uso incorrecto, `3` lectura rechazada. Ninguno autoriza evaluación. Con lectura rechazada no se evalúa ningún plano, tampoco `r0_final`: el informe registra el fallo y deniega la autorización.
- **Lectura endurecida:** rechaza versiones desconocidas, archivos faltantes o no declarados, duplicados, hashes o tamaños incorrectos, rutas absolutas o con escapes, enlaces y tamaños excesivos. Las comprobaciones en disco cubren un directorio estable, sin garantía frente a cambios concurrentes durante la lectura, y la detección de material privado es textual (`PRIVATE KEY`): no reconoce cualquier clave privada en bytes crudos.
- **CI:** el trabajo de Windows pasa a llamarse `Windows - seleccion de tests/seleccion_windows.txt`.

**Evidencia previa, en CI:** el operador comprobó AE-77 en GitHub Actions sobre `e71a4f5`: ambos trabajos correctos y `SUPERADOS 7/7` de OpenSSL en cada uno. No se atribuyen cifras de pytest.

El formato, el uso, el significado de los resultados y los límites están en la sección AE-78 de `ARCHITECTURE.md`.

A1–A3 y C1–C3 siguen sin decidir; D8 sigue limitada al modelo sintético y D9 con su espera provisional. La autoridad del conjunto esperado y la completitud global siguen pendientes. R0, R9 y las ocho condiciones siguen `sin_fijar`; F1, F2, O3, N2 y U1 siguen pendientes; `r0_final` sigue rechazada cuando se evalúa, `expediente_sin_eleccion` y `AUTORIZA_EVALUACION = False`.

AE-78 queda **validada localmente como trabajo preparatorio** (formato, lectura endurecida, verificador offline y pruebas con fixtures). **Validación del operador en Windows** (Python `3.14.6`, atribuida al usuario): parche completo comprobado y diez archivos; `64 passed` (AE-78), `110 passed` (AE-52), selección `1366 passed, 7 skipped` y `pip check` limpio. En esa selección, sin OpenSSL en `PATH`, el comprobador informó `OMITIDOS 7/7`: esos siete contrastes no se ejecutaron en ella y no cuentan como éxitos. En una ejecución posterior y separada, con el OpenSSL `3.5.6` incluido con Git añadido temporalmente al `PATH`, `test_sello_temporal_r0.py` dio `75 passed, 0 skipped` y el comprobador `SUPERADOS 7/7`; la selección completa no se repitió con OpenSSL. Solo en el sandbox Linux: `185 passed` (AE-74 a AE-77), `633 passed` (AE-60 a AE-78), `1373 passed` en las focalizadas y la selección, suite completa `5618 passed, 0 skipped` y `SUPERADOS 7/7`; no se repitió la suite para este cierre. Después de esas validaciones, el cierre corrige un texto de `LIMITES` en el código, que afirmaba que `r0_final` «sigue rechazada» también en informes de lectura rechazada, donde no se evalúa. Ahora dice que la auditoría no autoriza evaluación ni convierte R0 en final. Una prueba de regresión nueva lo comprueba (AE-78 pasa de 64 a 65 pruebas); después se revalidó la corrección en Windows: `65 passed in 3.20s` en las pruebas AE-78. **GitHub Actions:** la ejecución `36741015148` del workflow «Validacion Python 3.14» sobre el push de `44b927b` terminó con Success, con los dos trabajos correctos y `SUPERADOS 7/7` en cada uno (captura del operador, sin cifras de pytest). Este cierre no autoriza inferencia ni evaluación.

No se usaron sorteos reales, PostgreSQL, entrenamiento, inferencia operativa, claves, sellos, autoridades, observadores ni canales operativos, red, secretos ni el reloj local como evidencia. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-77 sin cambios.

**Etapa AE-79 -auditoría cruzada de expedientes portables y capturas de observadores, validada localmente como trabajo preparatorio:** compara entre 2 y 8 expedientes AE-78 entre sí y con capturas firmadas fuera de cada expediente.
- **Capturas:** `captura-observador-expediente/1`, firmada con Ed25519 mediante las primitivas de AE-76. Vincula el SHA-256 del manifiesto y de la política del verificador, el protocolo, el canal, el alcance y el corte, las historias de acuses y vistas, la posición del firmante y su captura anterior.
- **Política de auditoría:** la suministra quien audita (`politica-auditoria-cruzada-de-prueba/1`) con capturadores admitidos y cortes sintéticos admitidos. Un firmante es una clave pública, no una etiqueta.
- **Auditoría:** conserva el resultado AE-78 de cada expediente y no inventa planos si su lectura se rechaza. Detecta, entre otros:
  - `equivocacion_del_firmante` y `vinculo_roto`;
  - `historia_reescrita`, `corte_retrocede` y `objetivo_retirado`;
  - `discrepancia_entre_firmantes` (sin adjudicar) y `omision_comprobable`;
  - acuses del canal y declaraciones del observador contradictorios entre expedientes.

  Los alcances distintos son `incomparables`.
- **Comando:** `python -m scripts.auditar_expedientes_cruzados`, de solo lectura, con límites agregados y huellas esperadas aportadas desde fuera. Códigos: `0` sin contradicción detectable, `1` contradicción comprobada, `2` uso incorrecto, `3` lectura rechazada, `4` evidencia que no coincide. Ninguno autoriza evaluación.
- **Demostración:** `python -m tests.demostracion_auditoria_cruzada` ejecuta el comando real en cinco escenarios; también se ejecuta en los dos trabajos del workflow.
- **Premisa corregida de AE-78:** las marcas `PRIVATE KEY` en el propio manifiesto no se detectaban; ahora se rechazan.

Una captura solo prueba que una clave de prueba firmó esos bytes. La coincidencia de firmantes, aunque sean todos, no es una fuente autorizada: `autoridad_del_manifiesto` y `completitud_global` siguen pendientes. El formato, el modelo de amenaza, los escenarios y la tabla de decisiones abiertas están en la sección AE-79 de `ARCHITECTURE.md`.

A1–A3, C1–C3, D8 operativa y D9 definitiva siguen sin decidir; D8 sigue limitada al modelo sintético y D9 con su espera provisional. R0, R9 y las ocho condiciones siguen `sin_fijar`; F1, F2, O3, N2 y U1 siguen pendientes; `r0_final` sigue rechazada cuando se evalúa, `expediente_sin_eleccion` y `AUTORIZA_EVALUACION = False`.

AE-79 queda **validada localmente como trabajo preparatorio** (capturas, claves y políticas de prueba). **Validación del operador en Windows** (Python `3.14.6`, OpenSSL `3.5.6`, atribuida al usuario): parche completo corregido comprobado y doce archivos; `51 passed` (AE-79), `65 passed` (AE-78), `110 passed` (AE-52), selección `1425 passed` sin omisiones, `SUPERADOS 7/7` en modo `exigir`, demostración `5/5` y `pip check` limpio; la suite completa no se repitió en Windows. Solo en el sandbox Linux: `185 passed` (AE-74 a AE-77), `685 passed` (AE-60 a AE-79), suite completa `5670 passed, 0 skipped` y `SUPERADOS 7/7`. **GitHub Actions:** la captura del workflow posterior al merge del PR #78 (`5015841`) muestra Linux y Windows correctos, sin cifras de pytest ni recuento de OpenSSL atribuibles; la ejecución sobre `44b927b` corresponde a AE-78. Solo una captura con firma superada y política coincidente y, si se presenta su expediente, con todos sus campos coincidentes entra en la comparación cruzada; una no admitida nunca produce por sí sola una contradicción. No se acredita la autoridad operativa del conjunto esperado, la completitud global ni la autenticidad operativa de R0. Este cierre no autoriza inferencia ni evaluación.

No se usaron sorteos reales, PostgreSQL, entrenamiento, inferencia operativa, claves, sellos, autoridades, observadores, monitores ni canales operativos, red, secretos ni el reloj local como evidencia. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-78 sin cambios.

**Etapa AE-80 -constancias externas y verificables de una auditoría cruzada, validada localmente como trabajo preparatorio:** un tercero puede conservar una constancia firmada (`constancia-auditoria-cruzada/1`, con las primitivas de AE-76) del estado exacto de una auditoría AE-79 y presentarla después.
- **Qué vincula:**
  - el dominio de fixture;
  - la serie, la posición y la constancia anterior;
  - las huellas de las políticas y de las entradas;
  - el alcance y la huella del informe AE-79 normalizado.
- **Comando:** `python -m scripts.verificar_constancias_auditoria`, de solo lectura. Recalcula la auditoría AE-79 (nunca acepta un informe aportado) y la coteja con las constancias y con una política de claves suministrada aparte (`politica-constancias-de-prueba/1`).
- **Detecta:**
  - sustitución de informe o expediente;
  - bifurcaciones firmadas del mismo firmante y desacuerdos entre firmantes (sin adjudicar);
  - predecesores omitidos (pendiente, nunca «cadena íntegra»).
- **No presentado frente a inválido:** distingue la entrada no presentada de la presentada pero inválida.
- **Corrección de lectores de AE-75 a AE-78:** una constante JSON no estándar (`NaN`, `Infinity`, `1e999`) en una pieza, un compromiso o un manifiesto da un motivo de lectura (`pieza_ilegible`, `compromiso_ilegible` o `manifiesto_ilegible`) en lugar de terminar con un error.
- **Códigos:** `0` coincidentes, `1` contradicción, `2` uso incorrecto, `3` lectura rechazada, `4` no coincide, `5` sin constancia admitida. Ninguno autoriza evaluación.
- **Demostración:** `python -m tests.demostracion_constancias_auditoria` ejecuta el comando real en ocho escenarios; también se ejecuta en los dos trabajos del workflow.

Una firma válida solo prueba la firma de esos bytes frente a una clave admitida. No prueba autoridad real, publicación fuera de banda, custodia independiente, cronología, completitud global ni que R0 sea final, y no se usa mayoría ni quorum. El detalle y la evidencia que faltaría para A2 y C3 están en la sección AE-80 de `ARCHITECTURE.md`.

A1–A3, C1–C3, D8 operativa y D9 definitiva siguen sin decidir. R0, R9 y las ocho condiciones siguen `sin_fijar`; F1, F2, O3, N2 y U1 siguen pendientes; `expediente_sin_eleccion` y `AUTORIZA_EVALUACION = False`.

AE-80 queda **validada localmente como trabajo preparatorio** (claves y políticas de prueba). **Validación del operador en Windows** (Python `3.14.6`, OpenSSL `3.5.6`, atribuida al usuario): parche completo de 157378 bytes comprobado y quince archivos; `79 passed` (AE-80), `110 passed` (AE-52), selección `1504 passed` sin omisiones, `SUPERADOS 7/7` en modo `exigir`, demostraciones `5/5` y `8/8` y `pip check` limpio; la suite completa no se ejecutó en Windows. Solo en el sandbox Linux: `764 passed` (AE-60 a AE-80) y suite completa `5749 passed, 0 skipped`. **GitHub Actions todavía no ha ejecutado AE-80.** *Actualización (Fase 3): las ejecuciones posteriores de Actions (p. ej. la 45 sobre `c7644c4`) incluyen sus pruebas y su demostración, en verde.* No se acredita autoridad operativa, completitud global, cronología ni R0 final. Esta validación local no autoriza inferencia ni evaluación.

No se usaron sorteos reales, PostgreSQL, entrenamiento, inferencia operativa, claves, sellos, autoridades, observadores, monitores ni canales operativos, red, secretos ni el reloj local como evidencia. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-79 sin cambios.

**Etapa AE-81 -publicación y monitoreo cruzado de constancias (modelo sintético), validada localmente como trabajo preparatorio:** sobre las constancias de AE-80, un publicador firma checkpoints y unos monitores firman observaciones de los bytes exactos de esos checkpoints.
- **Formatos:**
  - `checkpoint-publicacion-constancias/1`: registro, posición, checkpoint anterior, huella de la política de AE-80 y cabezas AE-80;
  - `observacion-checkpoint/1`: SHA-256 del checkpoint visto y su contexto;
  - `politica-rol-de-prueba/1`: una política de claves por rol, sin claves compartidas entre roles;
  - `inventario-esperado-de-prueba/1`: checkpoints, cabezas y monitores esperados, con procedencia etiquetada.
  - Todos son JSON canónico con separación de dominio; ninguno usa números de posición ni reloj como prueba de anterioridad.
- **Comando:** `python -m scripts.verificar_publicacion_constancias`, de solo lectura. Recalcula AE-79 y AE-80 (nunca acepta un informe aportado) y coteja checkpoints y observaciones con las políticas por rol y el inventario, que suministra aparte quien verifica. Enumera lo que falta, sobra o no coincide.
- **Distingue:** bifurcación firmada del mismo publicador, observación incompatible con el checkpoint, progresión válida, evidencia ausente y mera discrepancia entre actores. Sin contexto no declara contradicción.
- **Planos separados:** integridad, referencias, cobertura del inventario, publicación externa (siempre `no_acreditada`), autoridad, cronología y completitud global (`pendiente`) y autorización operativa (`denegada`).
- **Códigos:** `0` coincidente con lo suministrado, `1` contradicción, `2` uso incorrecto, `3` lectura rechazada, `4` no coincide, `5` evidencia incompleta, `6` discrepancia entre actores. Ninguno autoriza evaluación.
- **Demostración:** `python -m tests.demostracion_publicacion_constancias` ejecuta el comando real en diez escenarios; también se ejecuta en los dos trabajos del workflow.

Un archivo local, dos firmas o una huella copiada no acreditan publicación externa, independencia de los monitores, cronología ni completitud; no se usa mayoría ni quorum, y no se afirma ninguna garantía de RFC 9162 para estas piezas. El detalle, el modelo de amenaza y el cuadro de decisiones A1–A3 y C1–C3 están en la sección AE-81 de `ARCHITECTURE.md`.

A1–A3, C1–C3, D8 operativa y D9 definitiva siguen sin decidir. R0, R9 y las ocho condiciones siguen `sin_fijar`; F1, F2, O3, N2 y U1 siguen pendientes; `expediente_sin_eleccion` y `AUTORIZA_EVALUACION = False`; `r0_final` no se promociona.

AE-81 queda **validada localmente como trabajo preparatorio** (claves, políticas e inventarios de prueba). **Validación del operador en Windows** (Python `3.14.6`, OpenSSL `3.5.6`, atribuida al usuario): parche completo de 137563 bytes comprobado y once archivos; `44 passed` (AE-81), `110 passed` (AE-52), selección `1548 passed` sin omisiones, `SUPERADOS 7/7` en modo `exigir`, demostraciones `5/5`, `8/8` y `10/10` y `pip check` limpio; la suite completa no se ejecutó en Windows. Solo en el sandbox Linux: `808 passed` (AE-60 a AE-81) y suite completa `5793 passed, 0 skipped`. **GitHub Actions todavía no ha ejecutado AE-81.** *Actualización (Fase 3): las ejecuciones posteriores de Actions (p. ej. la 45 sobre `c7644c4`) incluyen sus pruebas y su demostración, en verde.* La publicación externa sigue no acreditada; autoridad, cronología y completitud global siguen pendientes. Esta validación local no autoriza inferencia ni evaluación.

No se usaron sorteos reales, PostgreSQL, entrenamiento, inferencia operativa, claves, sellos, autoridades, publicadores, monitores ni canales operativos, red, servicios de publicación, secretos ni el reloj local como evidencia. AE-39 sigue en NO-GO, AE-41 bloqueado, los siete pendientes de AE-52 abiertos, la especificación de AE-53 sin aprobar y los bloqueos de AE-40 a AE-80 sin cambios.

**Producto 1 -estadísticas y pronósticos experimentales:** primera entrega orientada al usuario. Añade funciones visibles sin abrir otra etapa AE.
- **Estadísticas por juego:**
  - `/estadisticas` presenta los cuatro juegos;
  - `/estadisticas/{baloto|baloto-revancha|miloto|colorloto}/resumen` muestra el último sorteo, la cantidad y el período, el corte, la frescura y los huecos, además de frecuencias, atrasos y distribuciones;
  - las reglas salen de cada clase de dominio: MiLoto `1..39` sin superbalota, Baloto y Revancha `1..43` con superbalota `1..16`, ColorLoto con sus colores;
  - el historial vacío y los datos antiguos tienen mensajes claros.
- **Pronóstico experimental de Baloto y Revancha:** sigue la línea histórico real → features sin fuga de AE-36 → regresión logística calibrada (semilla 42) → walk-forward frente a la referencia uniforme (Log Loss, Brier, aciertos top-5) → artefacto JSON canónico de AE-52 con SHA-256 → pronóstico experimental del sorteo siguiente al corte (clasificado como se indica abajo). La superbalota es un objetivo separado. Se accede por la pantalla `/pronosticos`, por JSON en `/api/pronosticos/{JUEGO}` y por el comando `python -m scripts.pronostico_experimental`.
- **Clasificación temporal:** al generarlo, el objetivo se compara con todo el histórico cargado, sin el corte pedido, y se clasifica en uno de tres tipos:
  - **simulación retrospectiva (replay):** el objetivo ya figura en la base y se muestra el resultado observado con los aciertos;
  - **pronóstico sobre el último dato disponible:** el objetivo es el siguiente al último sorteo cargado, lo que no prueba que no se haya celebrado;
  - **objetivo no cargado con sorteos posteriores:** un hueco del histórico.

  Un histórico con más de 7 días sin sorteos produce un aviso visible. Las pantallas y la API muestran también el estado actual frente a la base.
- **Identidad e idempotencia:** el identificador es la `clave_de_entrada`, que resume juego, reglas, corte, SHA-256 del histórico, configuración, versión de la línea y versiones de scikit-learn y NumPy.
  - Repetir la misma entrada, por ejemplo con dos clics, devuelve el artefacto ya guardado sin reentrenar ni cambiar su fecha.
  - Si el histórico se corrigió, se guarda otra versión del mismo objetivo y las anteriores se conservan.
  - Las versiones se numeran por un orden de emisión persistente, nunca por la fecha declarada, el hash, el orden del directorio ni las fechas del sistema de archivos. Cada artefacto lleva sellados `secuencia_en_el_objetivo` y `version_anterior` (la clave de la versión previa). La secuencia se reserva de forma atómica con un archivo `<objetivo>-<secuencia>.secuencia` creado en modo exclusivo.
  - El orden se conserva al reconstruir el almacén desde los JSON. Límites:
    - la creación exclusiva atómica exige un disco local; no se garantiza en carpetas de red;
    - un proceso interrumpido entre la reserva y la escritura deja un hueco en la secuencia, sin alterar la numeración de las versiones;
    - mientras otro proceso escribe, un lector puede ver un instante el archivo nuevo como ilegible.
  - Los archivos se escriben en `backend/storage/pronosticos/<JUEGO>/<objetivo>-<clave>.json` en modo `xb`, con un sello SHA-256 que cubre todo el artefacto, incluida la fecha. Una alteración se informa.
- **Presentación:**
  - «Números por decena» muestra el porcentaje de todos los números extraídos: apariciones / (sorteos × números por sorteo) × 100, con el denominador visible. Los campos previos de la API se conservan.
  - En ColorLoto, la frecuencia de colores y de números se rotula como promedio de apariciones por sorteo, que puede superar 1 y no es una probabilidad.
  - Al imprimir o guardar como PDF las páginas de Producto 1, las tablas con desplazamiento salen completas, los nombres de color aparecen como texto y la tabla por bloque del pronóstico se imprime abierta. Las reglas se limitan a esas páginas, marcadas con `body.producto1-impresion`: no afectan a formularios ni a `<details>` de otras páginas ni cambian la vista en pantalla.
- **Acceso:** la aplicación no tiene autenticación. Entrenar (`POST /pronosticos/{juego}/generar`) y verificar (`POST /pronosticos/{juego}/verificar`, que reentrena) solo se aceptan con todas estas condiciones:
  - desde la propia máquina;
  - con `Host` local;
  - sin origen ajeno;
  - con el token del formulario.

  Se ejecuta un entrenamiento a la vez. El comando de línea sigue disponible en local.
- **Contrato explícito:** el estado es `experimental_no_acreditado` (`CONTRATO_DE_USO_EXPERIMENTAL`). No es un resultado acreditado ni una recomendación. No modifica el NO-GO de AE-39, el estado operativo de AE-41 ni `AUTORIZA_EVALUACION = False`. Lee como histórico los sorteos desde `2706`, que no se convierten en evidencia prospectiva. Si el modelo pierde frente a la referencia uniforme, la pantalla lo muestra.
- **Datos y validación:** sin escrituras en PostgreSQL. Las fixtures son sintéticas y solo sirven para pruebas. El histórico real solo existe en la base del operador. Las instrucciones de Windows están en `backend/docs/producto1_windows.md` y el inventario en `backend/docs/producto1_inventario.md`.

**Producto 2 -pronósticos de MiLoto y ColorLoto y resultados observados:** amplía Producto 1 sin abrir otra etapa AE. Todo pronóstico nuevo es `experimental_no_acreditado`. El NO-GO de AE-39, el NO-GO temporal de MiLoto y el aplazamiento de ColorLoto de AE-35, los bloqueos R0, el estado de AE-41 y `AUTORIZA_EVALUACION = False` siguen igual.
- **MiLoto** (`app/application/ml/pronostico_miloto.py`): cinco números distintos `1..39`, sin superbalota.
  - La logística de AE-36 no se usa, porque exige 50 sorteos de calentamiento y 100 objetivos de entrenamiento y la muestra de MiLoto es corta.
  - El estimador es la frecuencia de cada número contraída hacia la uniforme: `p(n) = (c_n + β·5/39) / (T + β)`, con `β = 39` fijado de antemano.
  - Los cinco sugeridos son los de mayor `p(n)`; la referencia es la uniforme 5/39.
  - La evaluación usa ventana creciente: cada sorteo con al menos 20 anteriores es un objetivo predicho solo con ellos. Hacen falta 10 objetivos evaluados, es decir, 30 sorteos hasta el corte.
  - Con menos datos se responde «Datos insuficientes» (HTTP 422, código de salida 4) y no se guarda nada.
  - Los bloques de 8 objetivos solo agrupan la presentación; no se reutilizan los 10 bloques de 20 de Baloto.
- **ColorLoto** (`app/application/ml/pronostico_colorloto.py`): seis pares (número `1..7`, color) con repetición.
  - El orden de extracción no forma parte del objetivo, así que cada sorteo se trata como un multiconjunto. La huella del histórico ordena los pares de cada sorteo.
  - La paleta se toma solo de los sorteos anteriores al corte; ninguna regla oficial de colores se fija en el código.
  - El modelo (`pares_multinomial_con_suavizado_aditivo`) es una multinomial de 6 balotas independientes sobre los `7·K` pares de la paleta, con probabilidades suavizadas `p(n,c) = (conteo + α) / (6T + α·7K)` y `α = 1` para los pares escasos o nunca vistos.
  - Esas probabilidades son la media a posteriori de una Dirichlet(α), usada como estimación puntual. La probabilidad de un multiconjunto es la multinomial `6!/∏m! · ∏p^m`. No es la distribución predictiva Dirichlet-multinomial; una prueba fija esta elección.
  - La combinación sugerida es el multiconjunto exacto más probable, que puede repetir un par. Se añade una muestra reproducible con semilla (42), etiquetada como sorteo simulado.
  - Un objetivo con un color ausente de la paleta de su corte se excluye de la evaluación; el total y los primeros excluidos se informan con su motivo.
  - Métricas, con sus denominadores (sorteos y balotas):
    - Log Loss y Brier por balota;
    - Log Loss del multiconjunto;
    - coincidencias de pares por sorteo, como intersección con repetición.
  - La referencia es la uniforme `1/(7K)`. Si faltan datos no se recurre a ella en silencio: se informa «Datos insuficientes».
- **Comparación honesta:** cada juego se compara solo con su propia referencia uniforme.
  - Las métricas de juegos distintos no comparten escala y no se comparan entre sí.
  - El veredicto `el_modelo_no_supera_a_la_referencia_uniforme` aparece en la página y en el JSON cuando el modelo no gana en las dos métricas principales.
  - Ganar en un histórico corto no acredita ventaja: no hay prueba de significancia.
- **Resultados observados** (`app/application/ml/resultados_observados.py`): cada pronóstico guardado de los cuatro juegos se compara en lectura con su sorteo objetivo en la base actual, sin cambiar los bytes del artefacto.
  - **Estado:**
    - `observado`, con fecha, resultado y coincidencias;
    - `pendiente`, si el objetivo es posterior al último cargado;
    - `no_corresponde`, si hay un hueco o no hay histórico.
  - **Coincidencias:**
    - Baloto y Revancha: números y superbalota;
    - MiLoto: números de 5;
    - ColorLoto: pares de 6 con repetición, y aparte números y colores.
  - **Emisión:** `emitido_sin_el_resultado_en_la_base_local` frente a `reconstruccion_retrospectiva`. La fecha de generación es del reloj local y no acredita anterioridad.
  - **Correcciones del histórico:** se informan como `historico_hasta_el_corte_cambio` y `resultado_observado_cambio`.
  - **Verificación de la entrada:** `historico_hasta_el_corte` vale `coincide`, `cambio` o `no_disponible`. Vale `no_disponible` si ya no queda ningún sorteo hasta el corte en la base: la entrada no se puede verificar, lo que no es una coincidencia ni un cambio demostrado. Se muestra en la página y en la API.
- **Pantallas, API y comando:**
  - `/pronosticos` muestra los cuatro juegos;
  - `/pronosticos/miloto` y `/pronosticos/colorloto` muestran:
    - estrategia, referencia, corte, fecha, versión y configuración;
    - métricas agregadas y por bloque, y tamaño de muestra;
    - versiones, resultados observados y avisos;
  - las páginas de Baloto y Revancha también muestran los resultados observados;
  - API: `GET /api/pronosticos/{BALOTO|BALOTO_REVANCHA|MILOTO|COLORLOTO}`, que incluye `resultado_observado`, y `GET /api/resultados-observados/{JUEGO}`. Responde 404 si el juego no se admite y 503 si la base no está disponible;
  - comando: `python -m scripts.pronostico_experimental {entrenar|listar|verificar|resultados} --juego {JUEGO|todos}`. Con `todos`, un juego sin datos no impide los demás. `corte-retrospectivo --juego {MILOTO|COLORLOTO}` propone, desde la base y en solo lectura, un corte existente con al menos 30 sorteos hasta él y cuyo objetivo también está cargado.
  - Se mantienen la protección local de los POST y el CSS de impresión acotado a `body.producto1-impresion`.
- **Artefactos:**
  - Baloto y Revancha siguen con `pronostico-experimental/1`, sin cambios en su módulo ni en el almacén (huellas fijadas en las pruebas).
  - MiLoto y ColorLoto usan el esquema explícito `pronostico-experimental/2`, con las mismas claves de primer nivel, que el mismo almacén lee sin cambios.
  - Se conservan el SHA-256, el sello, la inmutabilidad, la idempotencia, la secuencia por objetivo y `version_anterior`.
- **Datos y validación:** sin escrituras en PostgreSQL. En Cloud solo se usaron fixtures sintéticas; el histórico real (MiLoto y ColorLoto incluidos) solo existe en la base del operador. Las instrucciones de Windows están en `backend/docs/producto2_windows.md`.
- **Validación y evidencia.** Cada entorno se registra por separado.
  - **Linux (Cloud, fixtures sintéticas), antes de la corrección de impresión:**
    - pruebas: Producto 2 `55 passed`, Producto 1 `102 passed`;
    - selección de Windows `1705 passed`;
    - suite completa `5950 passed`;
    - OpenSSL `SUPERADOS 7/7` en modo exigir.
  - **Windows (operador, Python 3.14.6, OpenSSL 3.5.6), antes de la corrección de impresión:**
    - pruebas: Producto 2 `55 passed`, Producto 1 `102 passed`;
    - selección `1705 passed` sin omisiones;
    - OpenSSL `SUPERADOS 7/7` en modo exigir;
    - `pip check` limpio;
    - un único aviso de deprecación de Starlette/TestClient, que no es un fallo.

    La suite completa no se ejecutó en Windows.
  - **Demostración con el histórico real (Windows):**
    - Baloto 636 sorteos y Revancha 636, ambos con corte 2716 y objetivo 2717;
    - MiLoto 84 sorteos, corte 615, objetivo 616;
    - ColorLoto 222 sorteos, corte 222, objetivo 223.

    En MiLoto y ColorLoto, repetir la entrada devuelve el mismo identificador. La verificación dio `huella_exacta`, `mismos_datos` y `mismos_numeros_sugeridos` verdaderos, y `maxima_diferencia_de_probabilidad = 0`.
  - **Reconstrucciones retrospectivas verificadas (Windows):** en las dos, `historico_hasta_el_corte.estado = coincide` y `discrepancias` vacío.
    - MiLoto: corte 614, objetivo 615 (2026-09-29), `observado`, 1 de 5 números;
    - ColorLoto: corte 221, objetivo 222 (2026-09-28), `observado`, 0 de 6 pares.
  - **Después, con los objetivos nuevos ya cargados (PDF de Windows):** los resultados anteriores siguen visibles.
    - Baloto 2717: 0 de 5, superbalota no;
    - Revancha 2717: 1 de 5, superbalota no;
    - MiLoto 616: 0 de 5;
    - ColorLoto 223: 1 de 6 pares.

    Estos aciertos no demuestran capacidad predictiva ni anterioridad frente al sorteo real. Que el resultado faltara en la base local al generar no prueba que el sorteo no se hubiera celebrado.
  - **Evaluación histórica con datos reales:**
    - MiLoto y ColorLoto: la referencia uniforme gana;
    - Baloto: mejora las dos métricas principales, sin significancia estadística evaluada;
    - Revancha: no supera a la uniforme.
  - **Corrección de impresión (`producto2-impresion-cierre.patch`), validación visual parcial en Windows:** los PDF anteriores y nuevos usan el mismo formato, Carta horizontal (792 × 612 pt).
    - Baloto y MiLoto ya muestran la sugerencia en la primera página.
    - ColorLoto pasó de 7 a 6 páginas y conserva las 42 filas, pero sus seis pares sugeridos seguían en la segunda página, después de los avisos.
  - **Ajuste de ColorLoto (`producto2-colorloto-impresion.patch`), validado en Windows:** Python 3.14.6, OpenSSL 3.5.6.
    - Pruebas: Producto 2 `60 passed`, Producto 1 `102 passed`, selección `1710 passed` sin omisiones.
    - OpenSSL `SUPERADOS 7/7` en modo exigir; `pip check` limpio; un aviso de Starlette, sin fallos.
    - La suite completa no se ejecutó en Windows.
    - Las sugerencias de MiLoto y ColorLoto aparecen junto al objetivo en la primera página.
    - Defecto observado en el PDF de MiLoto en Carta vertical: «Trazabilidad» tapaba las filas 38 y 39 del ranking.
  - **Altura de las tarjetas al imprimir (`producto2-impresion-alturas.patch`), validada en Windows (2026-10-06):**
    - Python 3.14.6 y OpenSSL 3.5.6. Producto 2: `61 passed`; Producto 1: `102 passed`; selección: `1711 passed`, sin omisiones.
    - OpenSSL `SUPERADOS 7/7` en modo exigir; `pip check` limpio; un aviso de deprecación de Starlette, sin fallos.
    - PDF de Windows revisados en Carta vertical: MiLoto conserva las 39 filas y ColorLoto las 42, sin solapamientos. Las sugerencias aparecen en la primera página y se conservan avisos, trazabilidad, métricas, resultados observados y versiones.
    - Esta revisión visual cubre esos dos PDF en Carta vertical. No hay evidencia de ejecución de la suite completa en Windows.
  - **GitHub Actions:** todavía no había validado esa rama. *Actualización (Fase 3):* la ejecución 45 de GitHub Actions (push a `main` de `c7644c4`, merge del PR #91) lo cubrió en verde: Linux, suite completa con 6379 superadas; Windows, selección con 2134 superadas; OpenSSL 7/7 en ambos.
- **Impresión de las páginas de pronóstico.**
  - **Causa:** la regla `break-inside: avoid` se aplicaba a todas las tarjetas. La del pronóstico, con el ranking de 39 o 42 filas, no cabía en el espacio que quedaba en la primera página, así que el navegador la empujaba entera a la segunda. La primera página quedaba con solo el título, los avisos y la introducción.
  - **Corrección:** las tarjetas largas (`impresion-fragmentable`) pueden fragmentarse. Esto cubre el pronóstico, la evaluación, los resultados observados y las versiones.
  - **Lo que no cambia:**
    - filas, avisos y títulos siguen sin cortarse;
    - las cabeceras de tabla se repiten en cada página;
    - la regla sigue limitada a `body.producto1-impresion` y la pantalla no cambia;
    - las columnas de Bootstrap, las filas flex y `h-100` no eran la causa: al ancho de impresión las columnas ya se apilan.
  - **Orden de la sugerencia:** al imprimir, la sugerencia va justo después del objetivo y antes de los avisos. Es la combinación de ColorLoto y los cinco números de MiLoto.
    - Con el histórico desactualizado y el resultado ya observado, los avisos llenaban la primera página en Carta horizontal.
    - Solo cambia el `order` dentro de la columna flex de la tarjeta, y solo en `@media print`.
    - Los avisos se conservan completos y la pantalla no cambia.
  - **Altura de las tarjetas:** al imprimir, `h-100` deja de fijar la altura de las tarjetas de producto.
    - **Causa:** fijaba la altura a la de la columna, calculada antes de fragmentar. Al partirse entre páginas, el contenido crecía más que la caja y la tarjeta siguiente se pintaba encima.
    - **Casos encontrados:** «Trazabilidad» sobre las últimas filas del ranking de MiLoto, Baloto y Revancha en Carta vertical. También, en el índice y en las estadísticas, una tarjeta sobre la anterior.
    - **Pantalla:** sin cambios.


**Producto 3 -panel diario, actualización de pronósticos y seguimiento del rendimiento:** conecta lo construido con el uso diario, sin abrir otra etapa AE. Los pronósticos siguen siendo `experimental_no_acreditado` y `AUTORIZA_EVALUACION = False`.
- **Publicación del almacén (issue #83):**
  - Cada JSON se escribe en un temporal de la misma carpeta, con `fsync`, y se publica con `os.link`. Crear un enlace duro es atómico y no sobrescribe un destino existente, en Linux y en NTFS; `os.replace` no sirve porque sustituye el destino en silencio.
  - Un lector nunca ve un JSON final a medio escribir, y dos escritores (hilos o procesos: el comando y el servidor) no se pisan.
  - Una interrupción antes de publicar deja solo un temporal y una reserva de secuencia. No son pronósticos ni errores de integridad, y no se borran automáticamente.
  - Se conservan los bytes de los artefactos existentes, la idempotencia, la secuencia y `version_anterior`.
  - Ante un corte de energía solo se promete lo que da el sistema: `fsync` del contenido antes de publicar y, en POSIX, del directorio.
  - Requiere enlaces duros: disco local NTFS o POSIX.
  - Cobertura (`backend/tests/unit/test_producto3_almacen.py`, 14 pruebas con sincronización determinista): lector en el mismo proceso y en otro proceso mientras el escritor está detenido a mitad de escritura; proceso escritor terminado de golpe a mitad de escritura; temporal de un escritor activo que otro escritor no toca; escritores simultáneos (hilos y procesos, misma clave y claves distintas); dos generaciones simultáneas de la misma entrada en el caso de uso, que devuelven el mismo pronóstico; y conservación de bytes, huellas y orden de versiones. Sobre el almacén anterior a Producto 3, que escribía el JSON final directamente, las pruebas de lectura a mitad de escritura, proceso terminado y temporal activo fallan.
- **Operación diaria (`OperacionDiaria`):** un caso de uso común a la web y al comando. Por cada juego:
  1. estado inicial;
  2. con «Actualizar datos y generar», la importación incremental existente (`SincronizarSorteos`);
  3. validación del histórico con las reglas actuales;
  4. resultados observados;
  5. generación o reutilización del pronóstico del corte actual;
  6. resumen registrado.
  - «Generar con datos locales» usa una transacción de solo lectura y no escribe sorteos.
  - Si la actualización de un juego falla, ese juego no se genera con su histórico anterior; los demás siguen.
  - Estado global: `exito`, `parcial` o `fallo`.
- **Ejecuciones:**
  - La web responde en seguida con un identificador y el trabajo sigue en un hilo. Cada juego usa su propia sesión de base de datos.
  - El progreso queda en `storage/operacion/ejecuciones/<id>.json`, separado de los artefactos, sin credenciales ni HTML.
  - Un cerrojo del sistema operativo por juego (`flock` / `msvcrt.locking`) impide dos ejecuciones simultáneas del mismo juego, aunque una venga de la web y otra del comando.
  - Cada ejecución mantiene además su propio cerrojo hasta terminar de escribir el cierre global. Sin ese cerrojo (proceso muerto, disco lleno al cerrar, hilo que no se pudo lanzar), la ejecución se muestra como `interrumpida` aunque sus juegos hubieran terminado.
    - Los juegos completados conservan su resultado, y nunca se anota un éxito no registrado.
    - Volver a ejecutar reutiliza lo ya publicado.
  - La adquisición de cerrojos es «todos o ninguno» y segura frente a excepciones: si algo falla, libera lo propio. Solo la contención real se informa como «ocupado».
  - El comando `rutas` muestra solo las rutas de almacenamiento resueltas, para comprobar el aislamiento frente a Producto 2. Las guías fijan `DIRECTORIO_PRONOSTICOS_EXPERIMENTALES` y `DIRECTORIO_OPERACION` en cada ventana.
  - No hay programador dentro de uvicorn.
- **Panel diario (`/operacion`):** muestra los cuatro juegos, con estos datos en cada tarjeta:
  - último sorteo y fecha, frescura y huecos;
  - objetivo y combinación del pronóstico actual;
  - resultado pendiente o conocido;
  - comparación del histórico hasta el corte;
  - última ejecución, ejecución activa y avisos.

  Tiene acciones por juego y para todos, con la protección local de los POST. Una tarjeta con error no oculta las demás.
- **Rendimiento (`/rendimiento`):** desde los pronósticos guardados y el histórico actual, sin copias de resultados.
  - **Selección:** una emisión por objetivo, la primera según la secuencia sellada. No se reemplaza por otra más favorable si es ilegible, ambigua o su histórico cambió.
  - **Tipos:** las reconstrucciones retrospectivas y el seguimiento de emisiones con objetivo no cargado se muestran por separado.
  - **Métricas:** aciertos, Log Loss y Brier frente a la uniforme del artefacto, con las métricas del dominio; superbalota aparte; ColorLoto por balota y por multiconjunto.
  - **Gráfica:** diferencia acumulada en SVG local, con su tabla.
  - **Filtros:** juego, tipo y período (por fecha de generación), aplicados igual en JSON, tabla y gráfica.
  - Es descriptivo: no demuestra ventaja.
- **Comando y API:**
  - `python -m scripts.operacion_diaria {ejecutar|consultar|ejecuciones|recuperar|rendimiento|rutas}`, con códigos de salida: 0 éxito, 2 uso, 3 base, 5 parcial, 6 ya activa, 7 fallo.
  - API de solo lectura: `GET /api/operacion/panel`, `/api/operacion/ejecuciones[/{id}]` y `/api/rendimiento/{JUEGO}`.
  - La guía del Programador de tareas de Windows está en `backend/docs/producto3_windows.md`.
- **Pantalla e impresión:** en pantallas estrechas, las páginas de producto ya no desbordan en horizontal (`@media screen and (max-width: 767.98px)`). El escritorio y la impresión no cambian, y se conservan las correcciones de impresión de Producto 2.
- **Validación: validado localmente en Windows con histórico real.** Los pronósticos siguen `experimental_no_acreditado`, con el NO-GO vigente y `AUTORIZA_EVALUACION = False`. Validar el funcionamiento no acredita ninguna ventaja predictiva.
  - **Pruebas en Windows (operador; Python 3.14.6, OpenSSL 3.5.6):**
    - el parche completo (234715 bytes) se aplicó tras comprobar tamaño, SHA-256, rama, base y el alcance de 38 archivos;
    - Producto 3 `62 passed`, Producto 2 `61 passed`, Producto 1 `102 passed` y selección de Windows `1773 passed`;
    - OpenSSL `SUPERADOS 7/7` (`exigir`) y `pip check` limpio;
    - demostración 6/6, con fixtures sintéticas, no con la base real;
    - un aviso de Starlette por usar `httpx` en `TestClient`, que es un aviso, no un fallo.

    La suite completa no se ejecutó en Windows.
  - **Generación local con el histórico real:**
    - Dos ejecuciones de los cuatro juegos, ambas correctas.
    - La segunda reutilizó los cuatro pronósticos con los mismos identificadores y objetivos: 2718 en Baloto y Revancha, 618 en MiLoto y 224 en ColorLoto.
    - La verificación reprodujo exactamente esos cuatro pronósticos, anteriores a la actualización: huella exacta, mismos datos y diferencia máxima de probabilidad 0.
    - Se copiaron o comprobaron 12 archivos desde el almacén de Producto 2, incluidos auxiliares. Se conservaron byte a byte en el origen y en el almacén separado de Producto 3.
  - **Actualización desde el origen** (6 de octubre de 2026, hacia las 20:02 hora de Colombia; las marcas UTC de la interfaz muestran el 7 de octubre):
    - resultado `exito`, código 0;
    - cada juego, con 1 sorteo nuevo y 0 fallidos:

      | Juego | Último antes → después | Objetivo nuevo |
      |---|---|---|
      | Baloto y Revancha | 2717 → 2718 | 2719 |
      | MiLoto | 617 → 618 | 619 |
      | ColorLoto | 223 → 224 | 225 |

    - los 10 pronósticos JSON previos se conservaron byte a byte.
    - **Aviso de MiLoto:** el conector emitió `DATOS_INCOMPLETOS` porque no encontró una etiqueta `table` para el desglose de premios. La sincronización y la generación terminaron bien, pero esta ejecución no acredita un desglose completo de premios para ese sorteo. La causa no se comprobó.
  - **Panel e impresión:**
    - El panel funcionó en el puerto 8002. Una generación local de MiLoto desde la interfaz reutilizó el objetivo 618.
    - Se revisaron los PDF del panel y del rendimiento de MiLoto y ColorLoto tras la actualización: tres páginas cada uno, en Carta vertical, sin solapamientos.
    - Esta revisión no cubre la vista móvil, la Carta horizontal ni otras resoluciones.
  - **Rendimiento tras la actualización:** la muestra es muy pequeña, y en estos promedios la referencia uniforme tiene menor pérdida.
    - **MiLoto:**
      - 1 reconstrucción retrospectiva;
      - seguimiento: 616 y 618 incluidos, 619 pendiente, 0 excluidos;
      - Log Loss 0.38710 frente a 0.38296 de la uniforme (+0.00414), y Brier 0.11289 frente a 0.11177;
      - walk-forward del último artefacto: 0.38697 frente a 0.38296, en 67 sorteos.
    - **ColorLoto:**
      - 1 reconstrucción retrospectiva;
      - seguimiento: 223 y 224 incluidos, 225 pendiente, 0 excluidos;
      - por balota, Log Loss 3.81323 frente a 3.73767 (+0.07556) y Brier 0.97972 frente a 0.97619;
      - multiconjunto: 16.30014 frente a 15.84677;
      - walk-forward: 3.76537 frente a 3.73767, en 204 sorteos.
    - **Lectura de las categorías:**
      - «Objetivo no cargado al generar» describe la base local, no que la emisión precediera al sorteo real; hay emisiones generadas después de la fecha del resultado.
      - Los «observados» que informa el comando incluyen las reconstrucciones retrospectivas, así que no equivalen a los objetivos incluidos en seguimiento.
  - **Linux (Cloud, solo fixtures sintéticas):** son los resultados de la entrega del parche completo:
    - Producto 3 `62 passed`, Producto 2 `61 passed` y Producto 1 `102 passed`;
    - selección `1773 passed`, sin omisiones;
    - suite completa `6018 passed`, sin omisiones ni fallos, con cinco avisos conocidos de Alembic;
    - OpenSSL 7/7 y demostración 6/6;
    - `pip check` y la comprobación de espacios, limpios;
    - extracción limpia con los 38 archivos idénticos y 225 pruebas focales.
  - **GitHub Actions:** todavía no había ejecutado Producto 3 en esa entrega. *Actualización (Fase 3):* la ejecución 45 de GitHub Actions (push a `main` de `c7644c4`, merge del PR #91) lo cubrió en verde: Linux, suite completa con 6379 superadas; Windows, selección con 2134 superadas; OpenSSL 7/7 en ambos.
  - **Límites:**
    - Las regresiones de publicación atómica y de lectura parcial pasaron en Windows, pero no se ensayó una pérdida de energía, así que no se acredita una durabilidad absoluta en NTFS.
    - No se creó ninguna tarea real del Programador de tareas.
    - La sincronización incremental no prueba que se detecten correcciones de sorteos antiguos.
    - Las métricas de distintos juegos no se fusionan en una precisión global.


**Producto 4 -laboratorio de modelos y pronósticos comparables:** entrena modelos nuevos con el histórico de cada juego, los compara en una pantalla y genera un pronóstico con el modelo elegido (`/laboratorio`). Estado: **validado localmente en Windows con el histórico real**; la impresión ajustada en Carta vertical también quedó validada; GitHub Actions no lo había ejecutado en esa entrega; después lo cubrió en verde la ejecución 45 (push a `main` de `c7644c4`). La impresión horizontal no se ha revalidado en Windows. Los pronósticos siguen `experimental_no_acreditado`, con el NO-GO vigente y `AUTORIZA_EVALUACION = False`; nada de esto acredita ventaja predictiva.
- **Modelos nuevos** (catálogo explícito con identidad, versión, parámetros y requisitos; las referencias están rotuladas como tales):
  - Baloto, Revancha y MiLoto: regresión logística regularizada (C=1) y `HistGradientBoostingClassifier` (80 iteraciones, profundidad 3, 7 hojas, L2=1, sin parada temprana), con calibración sigmoide sobre un bloque cronológico posterior al ajuste. Aprenden la aparición de cada número. Después, un ajuste de cardinalidad (desplazamiento común de logits por bisección, épsilon 1e-6) hace que las marginales sumen 5 sin superar 1. El producto de cinco marginales no es la probabilidad del premio mayor.
  - ColorLoto: `PoissonRegressor` (alpha=1) y `HistGradientBoostingRegressor` con pérdida Poisson. Aprenden cuántas veces aparece cada par número-color (0 a 6) y sus intensidades se normalizan a una distribución de pares (protección fija 1e-6). La combinación se mide y se genera con la suposición multinomial de Producto 2 (6 balotas independientes e idénticamente distribuidas dada la distribución estimada); el modelo no la demuestra y no es una predictiva Dirichlet-multinomial. Sin calibración sigmoide.
  - Superbalota: sigue con la estrategia suavizada de Producto 1, evaluada aparte; los modelos nuevos no la aprenden. MiLoto y ColorLoto no tienen superbalota.
  - Referencias: la uniforme del juego y la estrategia actual (logística calibrada de AE-36, frecuencia contraída de MiLoto, multinomial suavizada de ColorLoto), con sus probabilidades originales.
- **Variables** (`producto4-variables-1`), calculadas solo con los sorteos anteriores a cada objetivo: frecuencias (o conteos medios) en ventanas de 5, 10 y 20, acumulada, aparición en el sorteo anterior, atraso con indicador explícito de «nunca apareció» e identidad categórica del candidato o del par. Escalado y codificación se ajustan solo con el entrenamiento.
- **Evaluación temporal común:** la unidad es el sorteo. Ventana creciente: 20 sorteos de calentamiento y al menos 30 objetivos de ajuste (20 base + 10 de calibración); hasta 6 bloques recientes de 10 objetivos (el último puede ser parcial) y al menos 10 evaluables.
  - Se reentrena al inicio de cada bloque y los parámetros quedan fijos durante el bloque. Las variables de un objetivo usan los resultados anteriores ya observados, también dentro del bloque.
  - Todos los candidatos se miden sobre la misma muestra (objetivos exactos registrados) y frente a la misma uniforme. Un candidato que no completa la muestra (p. ej. AE-36 con su mínimo de 100 objetivos) queda «parcial» y fuera del resumen principal.
  - Métricas: Log Loss y Brier, aciertos top-5 o coincidencias con multiplicidad, y diferencia emparejada frente a la uniforme, agregadas desde las observaciones. Además, gráfica local, tablas por bloque y diagnóstico de calibración descriptivo. El resumen dice «menor pérdida en esta evaluación», «la uniforme fue mejor», «empate» o «comparación incompleta». Es exploratorio: elegir un modelo después de verlo no acredita ventaja futura.
- **Experimentos y pronósticos:** cada comparación congela el histórico en una sola lectura de solo lectura. El informe guarda una copia canónica del histórico y su huella; los esquemas son nuevos (`laboratorio-experimento/1`, `laboratorio-pronostico/1`).
  - La identidad determinista cubre juego, reglas, paleta, corte, huella, variables, candidatos y parámetros, protocolo, transformaciones, implementación y entorno numérico. Repetir la misma entrada devuelve lo guardado; otro corte, histórico, receta o entorno da otra identidad.
  - Verificar distingue integridad del archivo, reproducción con la instantánea guardada y coincidencia con la base actual. No se promete identidad bit a bit entre Linux y Windows.
  - Almacenamiento propio (`DIRECTORIO_LABORATORIO_MODELOS`, por defecto `storage/laboratorio`, ignorado por Git), con la publicación atómica de Producto 3 (temporal, `fsync`, `os.link`, sin sobrescritura). El orden de emisión va por línea de modelo y objetivo, con secuencia sellada. No toca los almacenes de Productos 1-3 ni cambia la primera emisión que usa `/rendimiento`. No se promueve ningún modelo al panel diario.
- **Seguimiento por línea de modelo:** la primera emisión sellada de cada objetivo; si no es evaluable, se excluye sin avanzar a otra. Reconstrucciones retrospectivas, seguimiento (objetivo no cargado al generar, que no acredita anterioridad), pendientes y excluidos van por separado. Entre líneas solo se compara la intersección de objetivos.
- **Rutas y comando:**
  - Web: `/laboratorio`, `/laboratorio/{juego}`, `/laboratorio/experimentos/{ejecución o clave}`, `/laboratorio/pronosticos/{clave}` y `/laboratorio/{juego}/seguimiento`. Comparar, generar y verificar son POST locales protegidos; la comparación corre en otro hilo, con progreso persistente, cerrojo por juego y recuperación de ejecuciones interrumpidas.
  - API de solo lectura en `/api/laboratorio/...`.
  - Comando `python -m scripts.laboratorio_modelos {catalogo|diagnostico|comparar|consultar|experimentos|generar|verificar|seguimiento|ejecuciones|recuperar|rutas}`. Códigos de salida: 0, 2, 3, 4 (muestra insuficiente o modelo no ajustable), 5, 6, 7 y 8 (archivo alterado).
- **Proceso trabajador:** cada comparación, generación o verificación entrena en un proceso dedicado creado con `spawn` (igual en Windows). El proceso de la web y de la operación diaria nunca cambia sus hilos numéricos; solo el trabajador se limita a 2.
  - El trabajador recibe la instantánea ya congelada (ninguna sesión SQL) e informa el progreso.
  - Devuelve el resultado; la publicación inmutable la hace el proceso principal.
  - Si el trabajador muere, el juego queda en `fallo` sin publicar nada y los cerrojos se liberan.
  - Una probabilidad cruda no finita se rechaza antes del ajuste de cardinalidad.
  - Implementación `producto4-2`.
- **Coste medido** (Linux, Python 3.11, históricos sintéticos de tamaño real): unos 17 s para comparar los cuatro juegos con las recetas predeterminadas, incluido el arranque de los trabajadores (sin él, unos 13 s; Baloto unos 5 s, de ellos AE-36 unos 2,6 s). Un informe ocupa 40-90 KB y un pronóstico unos 10 KB. Requiere disco local NTFS o POSIX.
- **Impresión** (ajuste revalidado en Windows en Carta vertical):
  - Trazabilidad (informe y pronóstico) y Parámetros de las recetas (catálogo de cada juego) siguen plegados en pantalla. Al imprimir sale una copia abierta con el mismo contenido: la plantilla lo genera una vez y lo muestra dos veces. Imprimir no entrena, no recalcula y no escribe artefactos.
  - El comienzo de una tarjeta ya no queda al pie de una página separado de su título o de su primera tabla. Las tarjetas de candidato, de muestra común y del catálogo se imprimen como bloque y su cabecera (título, explicación y aviso) sigue a su tabla. Cada receta se imprime sin partirse.
  - Las tablas largas se siguen fragmentando, con la cabecera repetida y todas sus filas. La sugerencia del pronóstico sigue en la primera página.
  - Las reglas nuevas usan solo clases `laboratorio-*`, que solo aparecen en `templates/laboratorio/`, dentro del bloque de impresión existente. La pantalla y las demás páginas no cambian, y se conservan las protecciones de impresión de Productos 1 a 3.
- **Validación: validado localmente en Windows con el histórico real.** Los pronósticos siguen `experimental_no_acreditado`, con el NO-GO vigente y `AUTORIZA_EVALUACION = False`. Ningún modelo se promueve automáticamente a la operación diaria. Validar el funcionamiento no acredita ninguna ventaja predictiva.
  - **Pruebas en Windows** (operador; Python 3.14.6, OpenSSL 3.5.6):
    - se aplicó el parche completo (359997 bytes, 49 archivos). Sus 49 archivos coincidieron con el manifiesto: 1 byte a byte y 48 al normalizar CRLF a LF en memoria, sin reescribirlos;
    - el primer intento dio `75 passed` y `1 failed` en `test_almacen_propio_por_defecto`. `Settings(_env_file=None)` sigue leyendo las variables del proceso, y el script había fijado `DIRECTORIO_LABORATORIO_MODELOS` para aislar Producto 4. No era un defecto del producto: se corrigió solo la prueba, que quita esa variable con `monkeypatch` antes de comprobar el valor por defecto, y se añadió una prueba de que la variable se respeta. No se cambió `Settings` ni se borra la variable de forma global;
    - con esa corrección: Producto 4 `77 passed`, Productos 1 a 3 `225 passed` y selección filtrada (66 archivos) `1850 passed`, sin omisiones ni fallos;
    - OpenSSL `SUPERADOS 7/7` (`exigir`), `pip check` limpio y comprobación de espacios con archivos nuevos limpia;
    - un aviso conocido de Starlette por usar `httpx` en `TestClient`, que es un aviso, no un fallo.

    La suite completa no se ejecutó en Windows.
  - **Demostración sintética en Windows:** 8/8 pasos, incluidos el aislamiento de los hilos del proceso principal y la interrupción y recuperación del trabajador. Usa fixtures sintéticas: sus cifras no son sorteos reales.
  - **Histórico real** (script de aceptación: `ACEPTADO`):
    - la configuración y los tres almacenes efectivos apuntan al worktree de Producto 4 (`backend/storage/pronosticos`, `backend/storage/operacion` y `backend/storage/laboratorio`). Las credenciales no se imprimieron;
    - se copiaron 28 archivos anteriores de Producto 3; el origen y la copia se conservaron byte a byte al terminar;
    - datos usados (los últimos sorteos cargados tienen fecha 2026-10-05):

      | Juego | Sorteos | Último cargado | Objetivo | Objetivos de evaluación |
      |---|---:|---:|---:|---:|
      | Baloto | 638 | 2718 | 2719 | 60 |
      | Revancha | 638 | 2718 | 2719 | 60 |
      | MiLoto | 87 | 618 | 619 | 37 |
      | ColorLoto | 224 | 224 | 225 | 60 |

    - comparar los cuatro juegos tardó 22.8 s; repetir la comparación tardó 3.6 s y reutilizó los mismos cuatro informes. Todos los candidatos quedaron completos;
    - se generaron ocho pronósticos, dos modelos nuevos por juego, y repetir las entradas los reutilizó;
    - los cuatro experimentos y los ocho pronósticos dieron integridad correcta, reproducción exacta y coincidencia del histórico hasta el corte.
  - **Resultados de la evaluación real** (Log Loss agregado sobre la muestra común de cada juego; menor es mejor; ColorLoto, por balota):

    | Juego | Uniforme | Estrategia actual | Modelo lineal nuevo | Modelo de árboles nuevo |
    |---|---:|---:|---:|---:|
    | Baloto | 0.359445147513 | 0.359304564307 (AE-36) | 0.359424073003 (logística regularizada) | 0.359613609266 (HGB clasificador) |
    | Revancha | 0.359445147513 | 0.359652186736 (AE-36) | 0.359386252343 (logística regularizada) | 0.359548260626 (HGB clasificador) |
    | MiLoto | 0.382960430768 | 0.387894755517 (frecuencias) | 0.385416160425 (logística regularizada) | 0.385691469946 (HGB clasificador) |
    | ColorLoto | 3.737669618283 | 3.755328569885 (multinomial suavizada) | 3.738047884145 (Poisson regularizado) | 3.784794532888 (HGB Poisson) |

    - Baloto: AE-36 tuvo la menor pérdida en esta evaluación. No implica más aciertos: el informe muestra 0.45 aciertos top-5 por sorteo para AE-36 frente a 0.53 de la uniforme. La clasificación sigue el criterio declarado de Log Loss.
    - Revancha: la nueva logística regularizada tuvo la menor pérdida.
    - MiLoto y ColorLoto: la uniforme fue mejor.
    - No hay ventaja predictiva demostrada: los objetivos ya eran histórico y la comparación es exploratoria. Las pérdidas de juegos distintos usan métricas distintas y no se comparan entre sí.
    - Retrospectiva de MiLoto: corte 617 y objetivo existente 618, incluida como retrospectiva, 0 aciertos, Log Loss 0.38856 frente a 0.38296 de la uniforme. El panel muestra ese corte 617 como último experimento de MiLoto porque se ejecutó después del de corte 618; es coherente.
    - Seguimiento: el objetivo 619 está pendiente en las dos líneas. Que sea el siguiente al último cargado no acredita que el pronóstico se emitiera antes del sorteo real.
  - **PDF reales, primera revisión** (Chrome 154, Carta vertical):
    - revisados: el panel del laboratorio, Baloto y ColorLoto (2 páginas cada uno), el seguimiento de MiLoto (1), el informe de Baloto con corte 2718 (12), el de ColorLoto con corte 224 (11) y el pronóstico de MiLoto 619 (2);
    - sin solapamientos visibles, con gráficas y tablas legibles. Cada candidato no uniforme tiene sus 60 objetivos exactos en los dos informes, sin filas faltantes ni duplicadas, y las medias y los finales de las gráficas coinciden con sus tablas dentro del redondeo de cinco decimales;
    - el pronóstico de MiLoto lista los 39 números de mayor a menor probabilidad, con la sugerencia 9, 10, 23, 24, 33 en la primera página. Las marginales impresas suman 5.00003 por redondeo, coherente con el total 5 del artefacto;
    - motivaron el ajuste de impresión: Trazabilidad y Parámetros de las recetas no se imprimían (solo el título del desplegable), los catálogos de Baloto y ColorLoto dejaban una segunda página casi vacía con la tabla de experimentos, y algunos comienzos de tarjeta quedaban separados de su tabla, como el primer candidato de ColorLoto;
    - no cubren la vista móvil, la Carta horizontal ni los botones.
  - **Revalidación final en Windows** (operador, 2026-10-07; Python 3.14.6 y OpenSSL 3.5.6):
    - `aplicar-producto4-presentacion-cierre.ps1` comprobó los 49 archivos previos y, tras aplicar el incremental, los 51 archivos finales frente al manifiesto; CRLF/LF se comparó solo en memoria. El índice real quedó vacío y los espacios, incluidos los archivos nuevos, limpios;
    - Producto 4 `94 passed`, Productos 1 a 3 `225 passed` y selección filtrada de 67 archivos `1867 passed`, sin fallos ni omisiones. Demostración sintética 8/8, OpenSSL `SUPERADOS 7/7` en modo `exigir` y `pip check` limpio. Se conserva el aviso conocido de Starlette. La suite completa no se ejecutó en Windows;
    - se revisaron las 16 páginas de tres PDF nuevos, generados en Chrome 154, Carta vertical: catálogo de Baloto (2), pronóstico de MiLoto 619 (3) e informe de ColorLoto con corte 224 (11);
    - las cuatro recetas del catálogo se imprimen completas, sin partir una receta entre páginas. MiLoto conserva las 39 filas y la sugerencia 9, 10, 23, 24, 33 en la primera página; Trazabilidad se imprime completa en la tercera;
    - ColorLoto conserva los 60 objetivos de cada candidato no uniforme, sus gráficas y la trazabilidad. Los títulos acompañan sus tablas; no se observaron solapamientos ni contenido cortado;
    - esta revalidación cubre Carta vertical con esos tres documentos reales. No acredita la impresión horizontal, la vista móvil ni pruebas nuevas de los botones en Windows. Los resultados Linux se mantienen como evidencia separada;
    - esta actualización final solo cambia documentación: no repite importaciones, comparaciones, generaciones ni la suite, y no cambia modelos, artefactos o autorización.
  - **Linux** (Cloud, solo fixtures sintéticas):
    - la entrega del parche completo dio `6094 passed` en la suite completa, antes de añadir la prueba de la variable de entorno;
    - con la corrección de la prueba y el ajuste de impresión, sobre el código final:
      - suite completa, una vez: `6112 passed`, sin omisiones ni fallos, con cinco avisos conocidos de Alembic;
      - Producto 4 `94 passed`, con 17 pruebas nuevas de impresión (14 de ellas fallan sobre el estado anterior al ajuste) y Productos 1 a 3 `225 passed`;
      - selección filtrada (67 entradas) `1867 passed`, sin omisiones; OpenSSL `SUPERADOS 7/7` (`exigir`) en la selección y en la suite; demostración 8/8; `pip check` y espacios limpios;
      - impresión comprobada en Chromium 141 con Bootstrap 5.3.3 y fixtures de tamaño real, en Carta vertical y horizontal: Trazabilidad y Parámetros impresos, ninguna tarjeta separada de su tabla ni título al pie, las mismas filas que antes, y la pantalla y las páginas ajenas al laboratorio idénticas píxel a píxel. No sustituye la revisión en Windows con los informes reales.
  - **GitHub Actions:** todavía no había ejecutado Producto 4 en esa entrega. *Actualización (Fase 3):* la ejecución 45 de GitHub Actions (push a `main` de `c7644c4`, merge del PR #91) lo cubrió en verde: Linux, suite completa con 6379 superadas; Windows, selección con 2134 superadas; OpenSSL 7/7 en ambos.
- **Pendiente en esa entrega:** la ejecución de GitHub Actions; quedó cubierta por la ejecución 45. La impresión horizontal no se ha revalidado en Windows; la evidencia real de impresión cubre Carta vertical. Ver `backend/docs/producto4_windows.md`.

**Producto 5 -modelo combinado, carteras y simulación:** combina la uniforme y las dos familias nuevas de Producto 4 con pesos aprendidos solo del pasado, genera carteras de combinaciones válidas y reproducibles para los cuatro juegos, las simula frente a una cartera uniforme y sigue sus aciertos observados (`/carteras`). Estado: **validado localmente en Windows con histórico real**, incluida la revisión de impresión de carteras, comparación, seguimiento y simulación en Carta vertical y horizontal; GitHub Actions no lo había ejecutado en esa entrega; después lo cubrió en verde la ejecución 45 (push a `main` de `c7644c4`). Los pronósticos siguen `experimental_no_acreditado`, con el NO-GO vigente y `AUTORIZA_EVALUACION = False`; nada de esto acredita ventaja predictiva ni es una recomendación de apuesta.
- **Modelo combinado** (`ensemble_temporal` v1, protocolo `producto5-protocolo-1`): mezcla convexa de las probabilidades finales de tres componentes fijos, sin reentrenarlos ni cambiar sus recetas: uniforme + logística regularizada + HGB clasificador (Baloto, Revancha y MiLoto) y uniforme de la paleta + Poisson regularizado + HGB Poisson (ColorLoto). La mezcla conserva marginales en (0, 1) que suman 5, o una distribución de pares con masa 1.
  - Pesos: malla fija de 66 mezclas (i/10, j/10, k/10) evaluadas sobre predicciones ya calculadas (un ajuste por componente y corte, no 66 reentrenamientos). Criterio: Log Loss media por sorteo en un bloque interno de 10 objetivos (números: binaria por fila; ColorLoto: por balota con multiplicidades). Desempate: mínima pérdida; entre las mezclas a 1e-12 del mínimo, mayor peso de la uniforme y después del componente lineal.
  - Particiones causales para un bloque exterior que empieza en la posición s: bloque interno s-10..s-1; componentes ajustados (con su base y calibración) solo con objetivos anteriores a s-10; pesos elegidos con esas predicciones; componentes reajustados antes de s con los pesos fijos; bloque exterior evaluado sin usar sus etiquetas para nada. Mínimos: 20 de calentamiento + 30 de ajuste + 10 internos (60 sorteos para generar) y al menos 10 objetivos exteriores (70 para comparar; MiLoto con 87 sorteos tiene 27). Hasta 6 bloques exteriores.
  - Si el ajuste elige peso 1 para la uniforme, el informe lo dice («peso 1 para la uniforme») y el modelo coincide con la referencia en ese bloque. Un componente que no se puede ajustar deja el bloque no disponible y el modelo combinado parcial, fuera del ranking; nunca se sustituye por la uniforme con su nombre.
  - La superbalota sigue aparte con la estrategia suavizada de Producto 1.
- **Comparación exterior:** el modelo combinado, las dos familias nuevas, la estrategia actual y la uniforme sobre los mismos objetivos exteriores, con las métricas de Producto 4 agregadas por objetivo (los bloques desiguales pesan por sus objetivos). Pesos por bloque (gráfica y tabla), evaluación interna (solo para elegir pesos) y exterior por separado. Es un informe nuevo: no cambia los experimentos de Producto 4. Resultado honesto: «menor pérdida en esta evaluación», «la uniforme fue mejor», «empate» o «comparación incompleta».
- **Carteras** (`producto5-cartera-1`): 1 a 20 combinaciones (5 por defecto), semilla 42 por defecto y diversidad `libre` (sin duplicados completos) o `limitada` (como máximo 3 números principales compartidos entre dos líneas; en ColorLoto, 4 coincidencias con multiplicidad; la superbalota no cuenta).
  - Reglas: 5 números distintos de 1-43 más superbalota 1-16 (Baloto y Revancha; la identidad incluye la superbalota y se informan las líneas que repiten los cinco principales), 5 de 1-39 (MiLoto) y 6 pares de la paleta con repetición (ColorLoto, multiconjunto). Todo se canoniza.
  - La primera combinación es la sugerencia del modelo. La uniforme no tiene, ni un vector fuente constante (p. ej. el modelo combinado con peso 1 para la uniforme): entonces todas las líneas se muestrean y la cartera lo dice.
  - Las demás se obtienen por muestreo secuencial ponderado sin reemplazo (claves de Gumbel) o multinomial con reemplazo (ColorLoto), con generadores PCG64 locales (`SeedSequence([semilla, 5, flujo, juego])`) que no tocan el estado aleatorio global. Ese muestreo no conserva las marginales como probabilidades de inclusión: es una regla de construcción. La diversidad es una propiedad de construcción, no una mejora predictiva.
  - Presupuesto de 5000 intentos: si se agota, la cartera queda **parcial**, no se publica y no se relaja la diversidad. Métricas: cobertura, frecuencia de uso y coincidencias entre líneas. No se presenta ninguna probabilidad del premio mayor.
  - La uniforme puede generar carteras en Producto 5 (es la referencia de la simulación).
- **Simulación Monte Carlo** (`producto5-simulacion-1`): 10 000 sorteos por defecto (1000-50 000), en lotes que no cambian el resultado. Compara la cartera elegida con la cartera uniforme guardada del mismo juego, objetivo, tamaño, diversidad y semilla, sobre los MISMOS sorteos sintéticos en cada escenario; por sorteo se mide el máximo de la cartera.
  - Escenarios separados: sorteos uniformes (superbalota uniforme e independiente) e hipótesis de muestreo ponderado con el vector fuente congelado (aviso: no es una confirmación independiente).
  - Métricas: aciertos por combinación, distribución del máximo, «al menos» 2-5 (2-6 en ColorLoto), superbalota aparte con su relación con el máximo, comparación emparejada, medias y gráfica. Controles exactos para números: hipergeométrica, tamaño del espacio y distribución exacta del máximo por enumeración (unos 0,8 s en Baloto). Cero apariciones no significa imposibilidad. Sin dinero, premios ni retorno; la simulación no reentrena.
  - Una diferencia también puede venir de la estructura de la cartera y no del modelo: en ColorLoto, bajo sorteos uniformes, una cartera con menos pares repetidos tiene más coincidencias esperadas. Si el modelo combinado eligió peso 1 para la uniforme, su cartera coincide con la uniforme y la simulación empata en todos los sorteos.
- **Uso diario:** configuración versionada e inmutable por juego (modelo, cantidad, diversidad y semilla), sin elegir el modelo con menor pérdida ni cambiar Producto 3. El panel `/operacion` enlaza `/carteras` y ofrece «Generar carteras configuradas», con progreso por juego (una lectura consistente por juego; los juegos sin configuración se indican).
- **Seguimiento observado:** por línea (modelo, versión y parámetros) y objetivo, la primera emisión sellada; seguimiento, retrospectiva, pendiente y excluida por separado; histórico hasta el corte «coincide», «cambió» o «no disponible». Nunca se mezcla con frecuencias simuladas ni con pérdidas del modelo.
- **Rutas y comando:**
  - Web: `/carteras`, `/carteras/{juego}`, `/carteras/ejecuciones/{id}`, `/carteras/comparaciones/{clave}`, `/carteras/guardadas/{clave}`, `/carteras/simulaciones/{clave}` y `/carteras/{juego}/seguimiento`, con exportación CSV (UTF-8, sin fórmulas) y JSON canónico. Los GET no escriben; comparar, generar, simular, configurar y verificar son POST locales protegidos, en segundo plano con progreso, cerrojo por juego y recuperación.
  - API de solo lectura en `/api/carteras/...`.
  - Comando `python -m scripts.carteras_modelos {catalogo|diagnostico|comparar|configurar|configuracion|generar|simular|consultar|exportar|verificar|seguimiento|ejecuciones|recuperar|rutas}`. Códigos de salida: 0, 2, 3, 4, 5, 6, 7, 8 y 9 (tiempo agotado).
- **Identidad y almacén:** esquemas nuevos `carteras-comparacion/1`, `carteras-cartera/1`, `carteras-simulacion/1` y `carteras-configuracion/1` (implementación `producto5-1`). La clave de entrada se calcula antes del trabajo costoso (juego, reglas y paleta, corte y objetivo, huella del histórico, recetas, componentes y protocolo, parámetros de cartera, semillas y algoritmos, escenarios y entorno numérico); pesos, probabilidades y resultados quedan cubiertos por la huella del cuerpo y el sello. Repetir una entrada devuelve lo guardado sin entrenar ni simular. Almacén propio `DIRECTORIO_CARTERAS_MODELOS` (por defecto `storage/carteras`, ignorado por Git) con la publicación atómica y la secuencia sellada de Producto 4; el temporal de cada publicación tiene un nombre corto de longitud constante (`.publicacion.<16 hex>.tmp`, 33 caracteres), porque el de Producto 4 añade 23 caracteres al nombre final y en Windows sin rutas largas no se podía crear aunque el destino cupiera. Verificar separa integridad, reproducción y coincidencia con la base actual; no se promete identidad bit a bit entre sistemas.
- **Proceso trabajador:** comparar, calcular el vector fuente y simular corren en un proceso `spawn` dedicado con tiempo máximo configurable (`TIEMPO_MAXIMO_TRABAJADOR_CARTERAS`, 300 s por juego): si se supera, el proceso se detiene, el juego queda `tiempo_agotado` y no se publica nada. El proceso de la web no cambia sus hilos numéricos y se lanza un trabajador a la vez por trabajo.
- **Coste medido** (Linux, Python 3.11, históricos sintéticos de tamaño real, recetas predeterminadas y trabajadores reales): comparar los cuatro juegos unos 16-17 s; cinco combinaciones por juego con el modelo combinado unos 7,5 s en total; simular las dos hipótesis con 10 000 sorteos, unos 7 s para los cuatro juegos; repetir, unos 0,1 s sin lanzar trabajadores; verificar una cartera, una simulación y una comparación, unos 6 s. Una comparación ocupa 55-130 KB, una cartera 10-40 KB y una simulación 10-15 KB. Requiere disco local NTFS o POSIX.
- **Impresión:** las páginas nuevas usan solo clases `carteras-*` dentro del bloque de impresión existente. La primera página de una cartera muestra juego, objetivo, combinaciones y un aviso breve; Trazabilidad, pesos, supuestos y tablas plegadas se imprimen en una copia abierta. Las páginas de Productos 1 a 4 no cambian, salvo el enlace nuevo del menú.
- **Validación: validado localmente en Windows con histórico real.** Los pronósticos siguen `experimental_no_acreditado`, con el NO-GO vigente y `AUTORIZA_EVALUACION = False`. Validar el funcionamiento no acredita ninguna ventaja predictiva.
  - **Primera ejecución en Windows (fallida, ya corregida):** el parche original se aplicó y coincidió con su manifiesto, pero las pruebas de Producto 5 dieron `13 failed, 77 passed`. El temporal de publicación heredado de Producto 4 añadía 23 caracteres al nombre final y superaba el límite de rutas de Windows sin rutas largas: carpeta de 167 caracteres, destino de 240 y temporal de 262 (el límite es 259). La corrección (temporal `.publicacion.<16 hex>.tmp`, 33 caracteres) se comprobó primero en Linux con una simulación de ese límite, que no es una ejecución de Windows: el código original reproducía los 13 fallos y el corregido los pasaba.
  - **Pruebas en Windows tras la corrección** (operador; Git 2.54.0.windows.1, Python 3.14.6, OpenSSL 3.5.6):
    - el contenido final coincide con los 50 archivos del manifiesto v2: 49 al normalizar CRLF/LF en memoria y 1 byte a byte. El índice real quedó vacío y los espacios, limpios;
    - regresión de publicación y archivos de los fallos iniciales `28 passed`, Producto 5 `96 passed`, Producto 4 `94 passed`, Productos 1 a 3 `225 passed` y selección filtrada de 76 entradas `1963 passed`. Demostración sintética 11/11, con fixtures: sus cifras no son sorteos reales;
    - OpenSSL `SUPERADOS 7/7` en modo `exigir`, sin omisiones, fallos ni errores, y `pip check` sin problemas («No broken requirements found»);
    - aparece el aviso conocido de Starlette por usar `httpx` en `TestClient`: es un aviso, no un fallo, y no se cambian dependencias para silenciarlo.

    La suite completa no se ejecutó en Windows.
  - **Histórico real** (script de aceptación: `ACEPTADO`; lee la base sin importar sorteos ni modificar PostgreSQL). En esa ejecución, el último sorteo cargado de los cuatro juegos era del 2026-10-05 y el diagnóstico indicó `al_dia`; la frescura cambia con cada sorteo nuevo:

    | Juego | Sorteos | Corte | Siguiente objetivo | Objetivos exteriores |
    |---|---:|---:|---:|---:|
    | Baloto | 638 | 2718 | 2719 | 60 |
    | Revancha | 638 | 2718 | 2719 | 60 |
    | MiLoto | 87 | 618 | 619 | 27 |
    | ColorLoto | 224 | 224 | 225 | 60 |

    - comparar los cuatro juegos tardó 24.7 s; repetir la comparación tardó 4.1 s y reutilizó los cuatro informes;
    - carteras de cinco combinaciones con semilla 42; repetir las entradas devolvió las mismas claves. Simulación Monte Carlo de 10 000 sorteos, con comparación emparejada y los escenarios uniforme y ponderado por separado;
    - integridad correcta, reproducción exacta e histórico coincidente en los cuatro juegos;
    - retrospectivas incluidas: Baloto y Revancha 2717→2718, MiLoto 617→618 y ColorLoto 223→224. Los siguientes objetivos (2719, 2719, 619 y 225) quedaron pendientes; que un objetivo sea el siguiente al último cargado no acredita que la cartera se emitiera antes del sorteo real;
    - los 63 archivos originales de Producto 4 y los 31 de su copia aislada se conservaron byte a byte; se leyeron cinco experimentos de Producto 4 y se generaron 59 archivos en el almacén propio de carteras.
  - **Resultado frente a la uniforme:** en la evaluación exterior, la uniforme obtuvo menor pérdida que el modelo combinado en los cuatro juegos. Algunas variantes logísticas mejoraron ligeramente la pérdida retrospectiva en Baloto y Revancha; eso no es una ventaja prospectiva ni una superioridad del modelo combinado. En MiLoto, el vector fuente de la cartera actual es constante (el modelo combinado eligió peso 1 para la uniforme): las cinco líneas son muestreadas y no hay sugerencia diferenciada del modelo.
  - **PDF reales** (operador; las páginas renderizadas se revisaron con ChatGPT), páginas en Carta vertical / horizontal:
    - cartera de MiLoto 619, 4/6; cartera de ColorLoto 225, 4/6; comparación de Baloto con corte 2718, 15/22; seguimiento de MiLoto, 1/1; simulación de MiLoto 619, 4/6. En total, 28 verticales y 41 horizontales;
    - sin solapamientos, texto recortado ni filas perdidas. Las cinco combinaciones de MiLoto y de ColorLoto aparecen en la primera página en las dos orientaciones; se conservan las 39 filas del ranking de MiLoto y las 42 de ColorLoto, las frecuencias, los solapamientos, los nombres de color y la trazabilidad;
    - la comparación de Baloto conserva los seis bloques, los pesos internos, las métricas, las gráficas, los objetivos exteriores y la superbalota aparte. El seguimiento distingue las retrospectivas incluidas de los objetivos actuales pendientes;
    - la simulación conserva histogramas, umbrales, matrices emparejadas y controles exactos. En la comparación emparejada de MiLoto las dos carteras coinciden y hay 10 000 empates. Cero aciertos completos en una muestra Monte Carlo no equivalen a una probabilidad exacta cero;
    - ColorLoto identifica los pares repetidos y distingue la repetición de un número de la repetición de un par número-color;
    - el panel y los catálogos se revisaron antes, solo en Carta vertical.
  - **Linux** (Cloud, solo fixtures sintéticas; no es el histórico real), sobre la v2: Producto 5 `96 passed`, Producto 4 `94 passed`, Productos 1 a 3 `225 passed`, selección filtrada (76 entradas) `1963 passed`, demostración 11/11, suite completa una vez `6208 passed` sin fallos ni omisiones, OpenSSL `SUPERADOS 7/7` (`exigir`) en la selección y en la suite, y `pip check` limpio. Las dos cadenas de parches (base → original → corrección y base → completo v2) dan el mismo contenido final.
  - **GitHub Actions:** todavía no había ejecutado Producto 5 en esa entrega. *Actualización (Fase 3):* la ejecución 45 de GitHub Actions (push a `main` de `c7644c4`, merge del PR #91) lo cubrió en verde: Linux, suite completa con 6379 superadas; Windows, selección con 2134 superadas; OpenSSL 7/7 en ambos.
- **Pendiente en esa entrega:** la ejecución de GitHub Actions; quedó cubierta por la ejecución 45. Ver `backend/docs/producto5_windows.md`.

**Producto 6 -centro de resultados y evaluación continua de modelos:** reúne en `/resultados` los pronósticos ya emitidos por la operación diaria (Productos 1-3), el laboratorio (Producto 4) y el vector fuente de las carteras (Producto 5), los compara con los sorteos reales cargados y conserva fotografías verificables de cada consulta. Estado: **validado localmente en Windows con histórico real** (versión v2), con la revisión de los PDF reales adjuntos; GitHub Actions no lo había ejecutado en esa entrega; después lo cubrió en verde la ejecución 45 (push a `main` de `c7644c4`). Los pronósticos siguen `experimental_no_acreditado`, con el NO-GO vigente y `AUTORIZA_EVALUACION = False`. La conclusión real de Producto 5 (la uniforme tuvo menor pérdida que el modelo combinado en los cuatro juegos de aquella evaluación) no se convierte aquí en una victoria predictiva: las cifras describen objetivos ya observados.
- **Unidad de evaluación:** una emisión por procedencia, línea y objetivo, la PRIMERA según el orden sellado de su procedencia (`secuencia_en_el_objetivo` de Productos 1-3 con la política de `/rendimiento`; `secuencia_en_la_linea` de Productos 4 y 5). Nunca la fecha, el nombre del archivo, el mtime ni la versión con más aciertos. Si la primera no es evaluable, el objetivo se excluye sin pasar a otra versión; un archivo ilegible que hace ambiguo el orden excluye el objetivo.
  - Una **línea** identifica versión y configuración: Productos 1-3 por versión de la línea y huella de la configuración; Producto 4 por su línea (`modelo-vN-perfil`); Producto 5 por modelo, versión y perfil del vector fuente. No se agrupan modelos distintos por familia.
  - Se separan siempre integridad y legibilidad del artefacto, histórico hasta el corte («coincide», «cambio», «no disponible»), resultado observado (pendiente, observado, hueco) y admisión. Un histórico cambiado o no disponible, o un resultado fuera del universo congelado, no produce evaluación; una base que no responde deja las emisiones «sin base» (no son ceros ni pendientes confirmados) y no se inventa un último resultado.
  - Seguimiento y retrospectiva nunca se mezclan; el tipo inicial es seguimiento y, si no tiene resultados, la página lo dice y ofrece elegir retrospectiva sin cambiar de tipo sola. Simulaciones y evaluaciones walk-forward no entran. Una emisión antigua sin clasificación temporal aparece en las dos vistas, siempre excluida.
- **Vector fuente de Producto 5:** se evalúa como probabilidades del modelo (marginales que suman 5, o distribución de pares de ColorLoto), nunca como probabilidades de inclusión de las líneas muestreadas, con los valores guardados (sin renormalizar) y la uniforme exacta del mismo universo. Se evalúa una vez por objetivo aunque lo usen varias carteras y se registra qué carteras lo usan; dos vectores distintos para el mismo modelo y objetivo excluyen el objetivo en lugar de elegir uno.
- **Métricas y comparación:** Log Loss y Brier de `rendimiento_observado` (las de Productos 3 y 4) con las probabilidades congeladas; ColorLoto conserva Log Loss por balota y por multiconjunto; la superbalota va aparte y nunca se suma a los números; no se agregan juegos distintos. Diferencia = modelo − uniforme (negativa = menor pérdida en esa muestra); |diferencia| ≤ 1e-9 es empate (por debajo de la precisión de 12 decimales con que se guardan las probabilidades).
  - Comparación directa: la intersección exacta de los objetivos incluidos de TODAS las líneas elegidas, con el total individual, el común y los objetivos que quedaron fuera con su motivo; universos incompatibles salen de la muestra con su motivo. Sin muestra común se muestra «sin muestra común» y no hay clasificación. La uniforme figura en la clasificación y se ve cuando gana.
  - Evolución: diferencia por objetivo y acumulada sobre la misma serie de la muestra común, con gráfica SVG y la tabla equivalente.
- **Calibración** (descriptiva; no recalibra ni reentrena): intervalos fijos [0, 0.01), [0.01, 0.02), [0.02, 0.03), [0.03, 0.05), [0.05, 0.075), [0.075, 0.1), [0.1, 0.125), [0.125, 0.15), [0.15, 0.2), [0.2, 0.3), [0.3, 0.5) y [0.5, 1]; 0 cae en el primero y 1 en el último. Por intervalo: predicciones, sorteos distintos, probabilidad media y valor observado medio; un intervalo vacío no tiene valor (nunca 0). Números: 0/1 por presencia; superbalota en un diagnóstico aparte; ColorLoto: multiplicidad del par / 6, etiquetada como fracción de balotas (no «aparecer al menos una vez»). Curva con diagonal y tabla; aviso de muestra pequeña y de que las predicciones de un mismo sorteo no son ensayos independientes.
- **Carteras** (sección aparte del vector): aciertos observados del seguimiento de Producto 5 (máximo por cartera, superbalota aparte, multiplicidades de ColorLoto), con modelo, versión, perfil, combinaciones, diversidad y semilla visibles; solo se comparan carteras con el mismo número de combinaciones. «Usar esta configuración» muestra antes la configuración completa y la vigente, y guarda una versión nueva con el caso de uso versionado de Producto 5 (POST local con token, idempotente: si ya es la vigente no crea otra; no entrena ni genera carteras ni elige el modelo de menor pérdida). Las líneas de Productos 1-4 enlazan su flujo actual.
- **Informes guardados** (`resultados-informe/2`, implementación `producto6-2`; los `resultados-informe/1` se siguen leyendo sin reescribirlos): fotografía de la consulta con filtros (selección fijada), política, procedencias, artefactos de origen, el resultado observado de cada emisión, las probabilidades congeladas, las combinaciones de cada cartera incluida y los cálculos. JSON canónico; clave = SHA-256 del contenido; publicación atómica con el temporal corto de Producto 5 en `DIRECTORIO_RESULTADOS_MODELOS` (por defecto `storage/resultados`, ignorado por Git); nunca se sobrescribe y la misma fotografía reutiliza el informe. Una huella local no es una firma externa ni una prueba de anterioridad. Con la base caída el informe queda «parcial» con sus limitaciones. La verificación separa tres comprobaciones:
  - integridad del archivo (bytes canónicos, sello y clave);
  - reproducción del cálculo congelado, por partes y sin reentrenar ni consultar la base ni los almacenes: métricas por emisión, resúmenes, comparación y calibración de los modelos, y aciertos por combinación, máximo, superbalota, resumen por cartera y comparación entre carteras (con la función de aciertos de Producto 5). Resultado `exacta`, `no_exacta` o `parcial`: un informe `/1` no congela las combinaciones, así que sus carteras quedan «no verificables», nunca exactas;
  - coincidencia con la consulta actual: estado, motivo, histórico hasta el corte, resultado observado (por su contenido: otro orden de los mismos números o de los mismos pares no es otro sorteo; otra multiplicidad de un par sí, y la superbalota cuenta), métricas y cada fila de las carteras elegidas. Unas pérdidas iguales no bastan para coincidir. Sin base: «no disponible»; sin acceso a una procedencia o a las carteras: «no comparable», nunca «coincide».
- **Rutas y comando** (un solo caso de uso, `CentroDeResultados`):
  - Web: `/resultados`, `/resultados/{juego}` (filtros `procedencia`, `linea`, `tipo`, `desde`, `hasta`, `objetivo`, `cartera`; historial paginado), `exportar.csv` y `exportar.json` del conjunto filtrado completo, `POST /resultados/{juego}/informes`, `/resultados/informes/{clave}` (y `exportar.json`), `POST .../verificar`, `GET`/`POST /resultados/{juego}/configuracion?linea=`. Enlaces en la navegación y en el panel diario.
  - API de solo lectura en `/api/resultados/...`.
  - Comando `python -m scripts.resultados_modelos {indice|consultar|exportar|guardar|informes|informe|verificar|configuracion|configurar|rutas}`. Códigos de salida: 0, 2 (uso), 3 (base o almacén no disponibles), 5 (informe parcial, partes no verificables o consulta actual distinta, no disponible o no comparable; no es una alteración), 7 (reproducción no exacta), 8 (alterado).
  - Ningún GET entrena, importa, inicia trabajadores ni escribe; solo «guardar informe» y «usar esta configuración» escriben, cada uno en su almacén. CSV en UTF-8 sin fórmulas.
- **Impresión:** clases `resultados-*` dentro del bloque de impresión existente (cabeceras pegadas a su contenido, cada diagnóstico de calibración entero, gráficas de media página como máximo, pares de ColorLoto con color) y, en pantalla, una regla que solo afecta a páginas con `resultados-tarjeta` para que el historial ancho se desplace dentro de su tarjeta.
- **Validación: validado localmente en Windows con histórico real** (v2). Validar el funcionamiento no acredita ventaja predictiva, significación ni rendimiento futuro, ni autoriza un uso operativo nuevo.
  - **Revisión de la entrega v1, antes de aplicarla en Windows** (v1: parche de 298804 bytes, SHA-256 `c9dabc25…7dbe`; sustituida por la versión corregida, sin incrementales porque no se aplicó):
    - `comparar_con_consulta` no comparaba el resultado observado: con un vector fuente uniforme, un resultado distinto con las mismas pérdidas (y sin sugerencia propia) se verificaba como «coincide»;
    - `reproducir` no recalculaba las carteras: cambiar `maximo_medio` de una cartera, recomponer y sellar seguía dando «exacta». Tampoco se comparaban las carteras con la consulta actual;
    - las guías tenían marcadores `<clave>` y `<linea de cartera>` que el parser de PowerShell rechaza.
    Las regresiones se escribieron primero: de las 12 iniciales, 9 fallaron sobre v1 por esas causas y 3 son controles que ya pasaban (resultado idéntico, base no disponible y carteras ilegibles); después se añadieron 2 pruebas de los códigos del comando y de la conservación byte a byte de informes guardados. Las 14 pasan con la corrección. Las guías obtienen ahora la clave y la línea de las respuestas de `guardar`, `informes` y `consultar`, comprueban el código antes de leer el JSON y separan la ventana del servidor de la de comandos.
  - **Linux** (Cloud, solo fixtures sintéticas; no es el histórico real), versión corregida: Producto 6 `73 passed` (incluidas las 14 de `test_producto6_verificacion.py`); invariantes de Producto 1 y AE-52 `52 passed`; regresiones Producto 5 `96 passed`, Producto 4 `94 passed` y Productos 1 a 3 `225 passed`; selección filtrada (81 entradas) `2036 passed`, sin omisiones; demostración 9/9 en los cuatro juegos (con casos en que la uniforme tiene menor pérdida); suite completa una vez sobre el código final `6281 passed` sin fallos ni omisiones; OpenSSL `SUPERADOS 7/7` (`exigir`) en la selección y en la suite; `pip check` y espacios limpios. Los bloques PowerShell de las dos guías y el script pasan el parser oficial con cero errores, y los recorridos de las guías se ensayaron con pwsh 7 en Linux contra el comando real sobre fixtures (clave de `guardar` y línea de cartera auténticas, también con la base caída); ese ensayo no acredita Windows PowerShell 5.1. Página de verificación revisada en Chromium 141 con Bootstrap 5.3.3 local en Carta vertical, Carta horizontal y A4 vertical. La primera suite completa de v1 dio `2 failed` por dos invariantes existentes (la carpeta `resultados/` en la prueba de clases de impresión y el JSON canónico fuera de la capa web por AE-52), corregidas ya en v1.
  - **Windows** (operador, sobre la v2; Git 2.54.0.windows.1, Python 3.14.6, OpenSSL 3.5.6 de Git para Windows):
    - parche y manifiesto comprobados por tamaño y SHA-256 (338014 bytes, `f2847e80…6f06`; 10145 bytes, `3b216777…a3f4`); los 44 archivos coinciden exactamente con el manifiesto: 43 equivalentes al normalizar CRLF/LF solo en memoria y 1 byte a byte. Espacios limpios con índice temporal; índice real intacto y sin commits nuevos;
    - Producto 6 `73 passed`, Producto 5 `96 passed`, Producto 4 `94 passed`, Productos 1 a 3 `225 passed`, selección filtrada de Windows (81 entradas) `2036 passed`; demostración de Producto 6 9/9 con datos sintéticos (no es evidencia del histórico real); OpenSSL `SUPERADOS 7/7` en modo `exigir` sobre el JUnit; `pip check` sin problemas («No broken requirements found»);
    - aparece el aviso conocido `StarletteDeprecationWarning` por usar `httpx` en `TestClient`: es un aviso, no un fallo, y no se cambian dependencias por él;
    - la suite completa NO se ejecutó en Windows: los `6281 passed` son de Linux. Registro: `%TEMP%\p6-evidencia-20261009-005016-894e9b8e`.
  - **Histórico real** (operador; lee la base y los almacenes sin importar, entrenar ni reentrenar; sin commit ni push). Registro final: `%TEMP%\p6-real-20261009-012540-519844ea`.
    - El primer recorrido dio informes parciales porque al worktree nuevo le faltaban artefactos de la operación diaria y del laboratorio. Se completó copiando 28 archivos de pronósticos desde Producto 3 y 30 de laboratorio desde Producto 4 (58 en total), con origen y destino comprobados por SHA-256, sin mover ni sobrescribir archivos distintos.
    - Base de la ejecución final:

      | Juego | Sorteos | Último | Fecha |
      |---|---:|---:|---|
      | Baloto | 639 | 2719 | 2026-10-07 |
      | Revancha | 639 | 2719 | 2026-10-07 |
      | MiLoto | 89 | 620 | 2026-10-08 |
      | ColorLoto | 225 | 225 | 2026-10-08 |

    - Las tres procedencias (operación diaria, laboratorio y vector fuente de carteras) están disponibles en los cuatro juegos.
    - Índice (todas las líneas, tipo seguimiento): 7 emisiones incluidas, 0 pendientes y 0 excluidas por juego, sobre 3 objetivos distintos. Son emisiones por procedencia, línea y objetivo: NO son siete sorteos independientes.
    - Seguimiento con la selección del recorrido, en los cuatro juegos: `con_muestra_comun`, informe completo, reproducción exacta, consulta actual coincidente y código 0. Los objetivos comunes salen de la comparación, no del agregado del índice: en los PDF de Baloto y ColorLoto la comparación tiene un único objetivo común (2719 y 225) con aviso de muestra pequeña; los de Revancha y MiLoto no figuran en la evidencia adjunta.
    - Reconstrucción retrospectiva, en los cuatro juegos: `sin_muestra_comun` e informe parcial, con reproducción exacta y consulta actual coincidente. Es un estado legítimo por falta de intersección: no se retiraron líneas ni se cambió automáticamente el tipo de evaluación para inventar una muestra común. Filas retrospectivas incluidas en la selección del recorrido: 1 en Baloto, 1 en Revancha, 3 en MiLoto y 2 en ColorLoto (no son totales agregados de todas las líneas).
    - Repetir la misma fotografía reutilizó el informe en las ocho consultas (cuatro juegos por dos tipos). Se conservaron byte a byte los 128 archivos previos comprobados por el recorrido.
    - Vistas previas de «usar esta configuración»: compatibles y no vigentes en los cuatro juegos; no se aplicó ninguna configuración.
  - **PDF reales** (Chrome 154 sobre Windows, servidor `http://localhost:8005`; revisados por el operador y ChatGPT renderizando todas sus páginas):
    - Resultados de los modelos, 2 páginas en Carta vertical; Resultados — Baloto, 7 en Carta vertical; Resultados — ColorLoto, 5 en Carta vertical; Informe de resultados — Baloto, 6 en Carta vertical, 11 en Carta horizontal y 6 en A4 vertical; Verificación del informe, 1 en Carta horizontal;
    - sin solapamientos, filas tapadas ni tablas o gráficas recortadas; se conservan cabeceras, puntos y leyendas, intervalos de calibración, la superbalota aparte, los colores como texto, las carteras y los artefactos de origen;
    - la calibración distingue sorteos de predicciones: Baloto, 129 predicciones de números y 48 de superbalota sobre 3 sorteos; ColorLoto, 126 predicciones sobre 3 sorteos, con la fracción observada de balotas (no «aparecer al menos una vez»); los intervalos vacíos muestran «—»;
    - comparaciones directas visibles, ambas con un único objetivo común y aviso de muestra pequeña. Baloto, objetivo 2719: uniforme 0.35945; boosting y modelo combinado 0.36266; logística 0.36337: la uniforme fue mejor en ese objetivo. ColorLoto, objetivo 225: modelo combinado 3.73031 frente a uniforme 3.73767 (diferencia −0.00736): menor pérdida solo en ese objetivo, sin ventaja predictiva, significación ni rendimiento futuro demostrados;
    - informe guardado de Baloto `c0568aceb510def0280acb6cab7def694b8a8145c6ad8dc5aa86499ef387dc0a`, con 5 emisiones y 5 artefactos de origen congelados. Su verificación confirma por separado integridad correcta (bytes canónicos, sello y clave), reproducción exacta (métricas por emisión, resúmenes, comparación de modelos, calibración y cálculos de carteras: 5 emisiones y 2 pares cartera-objetivo, sin reentrenar ni consultar la base) y coincidencia con la consulta actual;
    - las dos carteras de Baloto tienen 5 combinaciones y se comparan sobre el objetivo 2719, con un máximo de 1 acierto cada una; ese máximo no se mezcla con el Log Loss y el vector fuente se cuenta una vez por objetivo, no una vez por cartera;
    - comprobación ligera en Linux (extracción de texto, sin repetir la revisión visual) de los cinco PDF adjuntos a esta revisión: el informe de Baloto recibido es el de A4 vertical (6 páginas); formatos, páginas, clave y cifras coinciden con lo anterior. Los PDF del informe en Carta vertical y horizontal no se recibieron aquí. La revisión no se extiende a las pantallas de Revancha y MiLoto, que no se adjuntaron, ni a todos los formatos de cada pantalla.
  - **GitHub Actions:** todavía no había ejecutado Producto 6 en esa entrega (sin PR ni ejecución presentada). *Actualización (Fase 3):* la ejecución 45 de GitHub Actions (push a `main` de `c7644c4`, merge del PR #91) lo cubrió en verde: Linux, suite completa con 6379 superadas; Windows, selección con 2134 superadas; OpenSSL 7/7 en ambos.
- **Pendiente en esa entrega:** la ejecución de GitHub Actions; quedó cubierta por la ejecución 45, tras el PR #89. Ver `backend/docs/producto6_windows.md`.


---







## Sincronización de datos históricos

El sistema obtiene resultados oficiales de `baloto.com` mediante una arquitectura de **conectores** desacoplados (`domain/application` no sabe si el origen es scraping, CSV, o una futura API oficial — todos implementan el mismo contrato `DrawSourceConnector`).

Desde el dashboard (`/importacion`):

- **Sincronizar ahora** — trae solo los sorteos nuevos desde el último almacenado (incremental real, verificado contra la base de datos en cada corrida, no contra un log de la corrida anterior).
- **Reimportar todo** — recorre el histórico completo desde el origen.
- **Reprocesar desde HTML** — reconstruye los datos usando únicamente el HTML ya guardado en `backend/storage/html/`, sin tocar la red.
- **Validar integridad** — detecta huecos en la numeración de sorteos.
- **Reporte de calidad de datos** — resumen de cada sincronización (encontrados, importados, duplicados, fallidos, incompletos, cobertura histórica).
- **Ver logs** — últimas líneas de `backend/storage/logs/sync.log`.

Cada sorteo se confirma individualmente en la base de datos (no en un solo lote gigante): si la sincronización falla a mitad de camino, todo lo ya procesado permanece guardado. Ver el detalle completo en [ARCHITECTURE.md](./ARCHITECTURE.md#resiliencia-de-la-sincronización) y `backend/docs/resiliencia_sincronizacion.md`.

---

## Estructura del proyecto

```
loteria-predictor/
├── docker-compose.yml          # PostgreSQL
├── run.sh                      # arranque con un solo comando
├── README.md
├── ARCHITECTURE.md
├── ROADMAP.md
└── backend/
    ├── requirements.txt
    ├── alembic.ini
    ├── alembic/versions/        # migraciones
    ├── docs/
    │   └── resiliencia_sincronizacion.md
    ├── app/
    │   ├── main.py              # composición raíz (FastAPI)
    │   ├── core/config.py       # configuración (pydantic-settings)
    │   ├── domain/               # entidades, value objects, reglas de los 4 juegos
    │   ├── application/          # casos de uso + puertos (interfaces)
    │   │   ├── use_cases/
    │   │   ├── interfaces/
    │   │   ├── mappers/
    │   │   └── estadisticas/motor/  # motor estadístico puro, agnóstico por juego
    │   ├── infrastructure/       # SQLAlchemy, conectores, parsers, storage, logging
    │   │   ├── connectors/       # BaseConnector + conectores concretos por juego
    │   │   ├── parsers/          # HTML -> DTO, sin HTTP, testeables sin red
    │   │   ├── db/                # modelos ORM, sesión, unit of work
    │   │   ├── repositories/
    │   │   └── storage/           # almacenamiento de HTML crudo
    │   ├── api/
    │   │   ├── web/               # routers HTML + HTMX
    │   │   └── rest/              # routers JSON (puente hacia una futura UI en React)
    │   ├── templates/             # Jinja2 (incluye templates/estadisticas/)
    │   └── static/                # CSS + vendor/chartjs/ (Chart.js servido localmente)
    └── tests/
        ├── unit/                 # tests de dominio y casos de uso
        │   └── connectors/       # tests del módulo de adquisición de datos
        └── fixtures/html/        # HTML de ejemplo para tests de parsers
```

---

## Capturas de pantalla

*(placeholder — agregar capturas del dashboard, panel de importación y detalle de sorteo antes de una release pública)*

- `docs/screenshots/dashboard.png`
- `docs/screenshots/importacion.png`
- `docs/screenshots/sorteo-detalle.png`

---

## Roadmap

Ver [ROADMAP.md](./ROADMAP.md) para el detalle de cada fase (objetivo, dependencias, entregables, criterios de finalización).

**Fase 10 (en curso, no cerrada; 2026-11-04):**

- **E10.1** (seguridad de la consola local): integrado en el PR #108.
- **E10.2** (consulta privada: proxy con certificado de cliente por persona, pasarela y API en perfil privado,
  cuotas, claves y tiempos máximos) y **E10.3** (lock con hashes, imágenes y CI de seguridad): **integrados** en
  el PR #109 (`main` `4aa24b85`), con los 11 checks aprobados.
- **Grype real:** 8 avisos High por imagen **aceptados temporalmente** (caducan el 2026-11-17) y 0 graves
  abiertos; no son avisos corregidos.
- **E10.4** (generaciones, captura coherente, importación, validación y respaldos): implementado y demostrado
  en Linux con PostgreSQL y datos sintéticos; escenarios C1–C10 como pruebas de comportamiento. El uso con datos
  reales está **bloqueado** hasta D10 y F10-DAT-02 sigue abierto. La recuperación operativa en Windows (R-W) está
  pendiente.
- **Pendientes:** E10.5–E10.7 y producción.

Guías: [consulta privada](backend/docs/fase10_consulta_privada.md), [imágenes y CI](backend/docs/fase10_imagenes_y_ci.md),
[generaciones](backend/docs/fase10_generaciones.md) e
[informe nativo](backend/docs/fase10_e102_e103_validacion_operador_2026-11-03.md) (este último, histórico).

---

## Licencia

Uso educativo/personal. Este proyecto no está afiliado a Baloto, Coljuegos, ni a ningún operador oficial de loterías. Los datos se obtienen de la información pública disponible en el sitio oficial únicamente con fines de análisis estadístico.
