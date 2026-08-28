# Roadmap del proyecto

> **Nota sobre el orden de las fases:** en esta versión del roadmap, Machine Learning (Fase 3) y Predicciones (Fase 4) aparecen antes de Estadísticas descriptivas (Fase 5). El orden técnicamente más habitual es Estadísticas → Ingeniería de características → ML → Predicciones, ya que los modelos de ML normalmente se construyen sobre features derivadas del análisis estadístico. Si se prefiere ese orden, es un cambio puramente de secuencia (no de alcance) y se puede reordenar antes de iniciar la Fase 3 sin ningún impacto en lo ya construido.

---

## ✅ Fase 1 — Dominio + MVP HTML

**Objetivo:** modelar las reglas de los tres juegos conocidos en ese momento (MiLoto, Baloto Revancha, ColorLoto) con Clean Architecture, y exponer un dashboard funcional para gestión manual de datos.

**Dependencias:** ninguna.

**Entregables:**
- Dominio: `LotteryGame`, entidades, value objects, reglas de validación de los 3 juegos.
- Base de datos PostgreSQL con esquema normalizado + migraciones Alembic.
- CRUD completo de sorteos vía formulario web (HTML + HTMX).
- Gestión de la paleta de colores de ColorLoto.
- API REST equivalente (puente hacia una futura UI en React).

**Criterios de finalización:** cumplidos — dominio con tests unitarios, dashboard operativo, arquitectura en capas verificada.

---

## ✅ Fase 2 — Adquisición automática de datos

**Objetivo:** poblar la base de datos automáticamente desde el sitio oficial, con una arquitectura de conectores desacoplada, sincronización incremental resiliente, y trazabilidad completa.

**Dependencias:** Fase 1 (reutiliza `RegistrarSorteo`, `LotteryGame`, el esquema de base de datos).

**Entregables:**
- Arquitectura de conectores (`DrawSourceConnector`) con implementaciones para scraping, CSV y entrada manual.
- Scraper con descubrimiento automático de páginas, reintentos con backoff, y tolerancia a fallos.
- Parsers HTML a DTO, separados de los conectores y testeables sin red.
- Sincronización incremental verificada contra el estado real de la base de datos.
- Persistencia incremental real (`UnitOfWork`): cada sorteo se confirma individualmente, un fallo a mitad de un lote no pierde lo ya procesado.
- Almacenamiento del HTML crudo (`storage/html/`) y reprocesamiento sin red.
- Registro de cada ejecución de sincronización + Data Quality Report.
- Panel de administración (Importación) con estado diferido vía HTMX, validación de integridad y logs.
- Documentación de resiliencia + auditoría técnica completa.
- Corrección arquitectónica: se agregó el juego `BALOTO` (clásico), que había quedado sin modelar desde la Fase 1 -Baloto y Revancha se relacionan por `numero_sorteo` sin cambios de esquema (ver ARCHITECTURE.md).

**Criterios de finalización:** cumplidos — 89/89 tests pasando, incluyendo pruebas que demuestran la persistencia incremental ante fallos en el primer/intermedio/último sorteo de un lote de 1000, duplicados, y reanudación.

---

## 🔜 Fase 3 — Machine Learning

**Objetivo:** entrenar y comparar modelos de Machine Learning (Random Forest, XGBoost, LightGBM, redes neuronales, modelos bayesianos, Markov) sobre los datos históricos, con validación rigurosa que evite sobreajuste.

**Dependencias:** Fase 2 (requiere datos históricos suficientes y confiables — el Data Quality Report de Fase 2 es el gate de entrada: no se entrena sobre datos con baja cobertura o alta tasa de incompletos).

**Entregables:**
- Pipeline de features derivadas de los datos crudos.
- Entrenamiento y comparación de múltiples modelos con Time Series Split / Walk Forward Validation.
- Métricas: Accuracy, Precision, Recall, F1, Log Loss, Brier Score.
- Registro de modelos entrenados y sus métricas (tablas `modelos`, `metricas_modelo`, ya presentes en el esquema desde la Fase 1).
- Comparación explícita contra un baseline simple (frecuencia/azar uniforme).

**Criterios de finalización:** modelos entrenados y versionados, métricas registradas y consultables, comparación contra baseline documentada, sin overfitting demostrable en validación fuera de muestra.

---

## 🔜 Fase 4 — Predicciones

**Objetivo:** generar recomendaciones diarias (combinaciones, números fuertes/débiles, probabilidades estimadas) a partir de los modelos entrenados en la Fase 3, con explicabilidad y nivel de confianza.

**Dependencias:** Fase 3.

**Entregables:**
- Caso de uso `GenerarPredicciones` por juego.
- Top 5 combinaciones recomendadas, Top 10 números fuertes/débiles.
- Explicación de cómo se obtuvo cada recomendación.
- Nivel de confianza explícito, con disclaimer permanente de que es análisis estadístico, no garantía.
- Tabla `predicciones` (ya presente en el esquema desde la Fase 1).

**Criterios de finalización:** predicciones generadas diariamente, explicables, con nivel de confianza calibrado contra el desempeño histórico real del modelo.

---

## 🟡 Fase 5 — Estadísticas descriptivas (parcial)

**Objetivo:** análisis estadístico clásico sobre los datos históricos — frecuencias, intervalos entre apariciones, correlaciones, patrones temporales.

**Dependencias:** Fase 2. No depende de las Fases 3/4, aunque en la práctica sus resultados alimentan las features de la Fase 3.

**Estado por componente** (fase dividida deliberadamente: partes reales y verificadas conviven con partes todavía sin construir):

| Componente | Estado |
|---|---|
| Motor estadístico puro, agnóstico por juego (`application/estadisticas/motor/`) | ✅ Completo para frecuencia de números/superbalota, comparación observada vs. esperada, y distancia desde la última aparición |
| Orquestador con caché persistido (`CalcularYPersistirEstadistica`) | ✅ Completo |
| Persistencia de resultados calculados (tabla `estadisticas`, identidad por juego/tipo/corte/parámetros, hash canónico) | ✅ Completo |
| Invalidación selectiva al mutar sorteos (registrar/editar/eliminar) | ✅ Completo, aislada por juego |
| Upsert al recalcular una identidad existente (sin duplicados, atómico con la mutación) | ✅ Completo |
| Visualización: frecuencia de números principales | ✅ Baloto, Baloto Revancha, MiLoto |
| Visualización: frecuencia de superbalota | ✅ Baloto, Baloto Revancha (MiLoto no tiene superbalota, por diseño) |
| Visualización: frecuencia observada vs. esperada | ✅ Baloto, Baloto Revancha, MiLoto |
| Visualización: distancia desde la última aparición (Etapa W) | ✅ Baloto, Baloto Revancha, MiLoto — números principales únicamente, sin superbalota (alcance deliberado de esta etapa) |
| Estadísticas para ColorLoto | 🟡 Parcial -seis visualizaciones descriptivas conectadas (frecuencia de números, Etapa AE-1, validada; frecuencia de colores, Etapa AE-2, validada; frecuencia de pares número-color, Etapa AE-3, validada; atrasos de números, Etapa AE-4, validada; atrasos de colores, Etapa AE-5, validada; atrasos de pares número-color, Etapa AE-6, validada); el resto de las funciones de motor ya existentes (consecutivos, coocurrencia, etc.) siguen sin conectar |
| Intervalos entre apariciones, correlaciones (Chi cuadrado, Pearson, Spearman), patrones (consecutivos, suma total, decenas), coocurrencia | 🔜 Pendiente -el motor tiene módulos parciales para varios de estos análisis, pero ninguno está conectado al orquestador ni expuesto en la web todavía |
| Dashboard de estadísticas unificado (todas las métricas en una sola vista) | 🔜 Pendiente -hoy son páginas independientes por juego/métrica |
| Distancia desde la última aparición para superbalota | 🔜 No incluida en esta etapa (alcance deliberadamente limitado a números principales) |
| Control de corte temporal en la interfaz (formulario GET, navegación consciente del corte por juego) | ✅ Baloto, Baloto Revancha, MiLoto en las 4 visualizaciones previas -validado con pytest real y FastAPI/PostgreSQL reales en Etapa X |
| Visualización: distribución de números pares e impares | ✅ Baloto, Baloto Revancha, MiLoto -números principales únicamente, sin superbalota (alcance deliberado de esta etapa) |
| Visualización: distribución inferior/superior | ✅ Baloto, Baloto Revancha, MiLoto -grupos asimétricos (21/22 y 19/20), explicado explícitamente en la página, nunca presentados como mitades iguales |
| Visualización: distribución de pares consecutivos | ✅ Baloto, Baloto Revancha, MiLoto -pares adyacentes (diferencia 1), pueden solaparse, categorías 0..K-1, validación defensiva completa (cantidad/duplicados/rango) en Application, doble defensa deliberada con la validación de rango ya existente en el motor |
| Visualización: racha máxima de números consecutivos | ✅ Baloto, Baloto Revancha, MiLoto -longitud del bloque más largo de números consecutivos, categorías 1..K (nunca 0), distinta de "pares consecutivos" (1,2,3 → 2 pares pero racha=3), misma doble defensa reutilizada |
| Visualización: repeticiones entre sorteos consecutivos | ✅ Baloto, Baloto Revancha, MiLoto -transición estricta N→N+1, huecos nunca comparados, denominador = transiciones válidas (presentado como "Transiciones analizadas", nunca "Sorteos analizados"), categorías 0..K, misma doble defensa reutilizada |
| Validación defensiva de integridad histórica (cantidad, duplicados, rango) antes de calcular distribuciones que dependen de esos invariantes | ✅ Compartida entre `distribucion_pares_impares` y `distribucion_altos_bajos` vía un helper reutilizable -corrige una laguna real: la validación original de pares/impares (Etapa Y) no detectaba duplicados |

**Checkpoint de tests validado (Etapa V):** `904 passed` con `pytest` real contra PostgreSQL.
**Checkpoint de tests validado (Etapa W, distancia desde la última aparición):** `946 passed` con `pytest` real contra PostgreSQL.
**Checkpoint de tests validado (Etapa X, controles de corte temporal):** `986 passed` con `pytest` real contra PostgreSQL, FastAPI real.
**Checkpoint de tests validado (Etapa Y, distribución de números pares e impares):** `1053 passed` con `pytest` real, `pip check` limpio, contra PostgreSQL y FastAPI/Uvicorn reales, Python 3.14. Las tres rutas (histórico completo y con corte) respondieron 200 y se verificaron visualmente. Comparación independiente con SQL directo sobre `sorteos`/`sorteo_numeros` (36 categorías, 3 juegos × histórico/corte × 6 categorías), sin discrepancias contra las estadísticas cacheadas.
**Checkpoint de tests validado (Etapa Z, distribución inferior/superior + defensa de integridad histórica):** `1133 passed` con `pytest` real en Windows (Python 3.14, `pip check` limpio), FastAPI/Uvicorn y PostgreSQL reales. Corregido en esta validación un defecto de portabilidad real (`open()` sin `encoding="utf-8"` fallaba bajo cp1252 en Windows). Las seis rutas -histórico y los tres cortes- respondieron 200; corte inválido respondió 422. Las tres invariantes del histórico (cantidad, duplicados, rango) se verificaron directamente en PostgreSQL sin inconsistencias. Comparación independiente con SQL directo (36 categorías) contra las seis cachés, sin discrepancias. Toda esta evidencia fue producida por el usuario en Windows, no por Claude.
**Checkpoint de tests validado (Etapa AA, distribución de pares consecutivos):** `1195 passed` con `pytest` real en Windows (Python 3.14, `pip check` limpio), FastAPI/Uvicorn y PostgreSQL reales. Tests focalizados: `450 passed`. Las seis combinaciones juego/corte respondieron 200; cortes inválidos respondieron 422. Persistencia verificada: seis filas objetivo, parámetros exactos por juego. Validación SQL independiente completa (integridad histórica, 30 categorías recalculadas, comparación contra caché, verificación JSONB de parámetros) sin ninguna discrepancia.
**Checkpoint validado (Etapa AB, racha máxima de números consecutivos):** `1259 passed` con `pytest` real en Windows (Python 3.14, `pip check` limpio), FastAPI/Uvicorn y PostgreSQL reales. Tests focalizados: `514 passed`. Corregida antes del checkpoint una línea muerta e inalcanzable en la receta (sin efecto en comportamiento). Las seis combinaciones respondieron 200; cortes inválidos respondieron 422. Persistencia verificada: seis filas objetivo, parámetros exactos por juego. Validación SQL independiente mediante "islands and gaps" (integridad histórica, 30 categorías recalculadas, comparación contra caché, verificación JSONB de parámetros) sin ninguna discrepancia.
**Checkpoint validado (Etapa AC, repeticiones entre sorteos consecutivos):** `1321 passed` con `pytest` real en Windows (Python 3.14.6, `pip check` limpio), FastAPI/Uvicorn y PostgreSQL reales. Tests focalizados: `576 passed`. Las seis combinaciones respondieron 200; cortes inválidos respondieron 422. Persistencia verificada: seis filas objetivo, parámetros exactos por juego. Integridad histórica sin inconsistencias. Validación SQL independiente (self-join estricto, categoría cero preservada): 36 categorías recalculadas coincidiendo exactamente con lo cacheado, conservación de masa sin discrepancias, verificación JSONB de parámetros sin discrepancias.
**Checkpoint validado (Etapa AD, endurecimiento de integridad de `frecuencia_superbalota` -no una décima visualización):** `1343 passed` con `pytest` real en Windows (Python 3.14.6, `pip check` limpio), FastAPI/Uvicorn y PostgreSQL reales. Tests focalizados: `659 passed`. Endurece la receta ya existente (misma ruta, mismo `tipo_estadistica`, misma identidad de caché): rechazo total (`ResultadoHistoricoInconsistenteError`, 500) ante superbalota ausente o fuera de rango en Baloto/Revancha. Cuatro combinaciones válidas con 200; MiLoto y tres cortes inválidos con 422. Integridad verificada en PostgreSQL: cero ausencias, cero fuera de rango. Seis cachés vigentes con identidad exacta `{"rango_min": 1, "rango_max": 16}`. Comparación SQL independiente de 96 categorías sin discrepancias. Ninguno de estos números es un total permanente.
**Checkpoint validado (Etapa AE-0, catálogo completo y vigencia histórica de colores -infraestructura interna, no una décima visualización):** `1372 passed` con `pytest` real en Windows (Python 3.14.6, `pip check` limpio), PostgreSQL real disponible. Tests focalizados: `276 passed`. `ColorRepository` incorporó `listar_todos(juego_id)` (catálogo completo, sin filtrar por `activo` ni fecha, una consulta) y corrigió `listar_vigentes(juego_id, en_fecha)` para representar correctamente la paleta históricamente vigente en esa fecha, sin excluir por el estado actual de `activo` -sin cambio de comportamiento para el uso sin fecha ya existente en `GameFactory`. Orden determinista por `codigo`, sin N+1. **La visualización web de ColorLoto sigue pendiente**: sin receta, ruta, View Model, template, canvas ni navegación -AE-0 es exclusivamente la base de repositorio que una futura etapa necesitará. Toda esta evidencia fue producida y verificada por el usuario en Windows, no por Claude. Ninguno de estos números es un total permanente.
**Checkpoint validado (Etapa AE-1, primera visualización web de ColorLoto -frecuencia de números, décima visualización global, sin afectar la navegación 9/9/8 de los 3 juegos numéricos):** `1434 passed` con `pytest` real en Windows (Python 3.14.6, `pip check` limpio), FastAPI/Uvicorn y PostgreSQL reales. Tests focalizados (6 archivos): `659 passed`. Una auditoría posterior encontró y corrigió un **defecto crítico de orden de registro de rutas** (Starlette evalúa en orden de registro, no por especificidad; la ruta genérica numérica habría interceptado la URL de ColorLoto, dejando su handler dedicado inalcanzable) -confirmado corregido con el enrutador real: histórico completo y corte 100 responden 200, cortes inválidos 422, métrica incompatible 404. Conecta `frecuencia_numeros_colorloto` en `/estadisticas/colorloto/frecuencia-numeros`, ruta deliberadamente aislada de `SLUG_A_CODIGO` (compartido por las 9 rutas numéricas). Identidad de caché `{"rango_min", "rango_max", "cantidad_numeros"}` -dos cachés vigentes verificadas (histórico completo, corte 100), parámetros exactos. Integridad histórica sin inconsistencias (cantidad, rango, color por juego y vigencia). Cálculo SQL independiente de 14 categorías coincidiendo exactamente con lo cacheado, conservación de masa y comparación JSONB sin discrepancias. Endurecimiento de integridad con 3 tipos cerrados nuevos (cantidad de pares, rango de número, color inválido/no vigente en la fecha) -acepta explícitamente repetición de número/color/par exacto, ya permitida por el dominio. Toda esta evidencia fue producida y verificada por el usuario en Windows, no por Claude. **AE-2 (siguientes métricas de ColorLoto) continúa pendiente.** Ninguno de estos números es un total permanente.
**Checkpoint validado (Etapa AE-2, segunda visualización web de ColorLoto -frecuencia de colores, decimoprimera visualización global):** `1492 passed` con `pytest` real en Windows (Python 3.14.6, `pip check` limpio), FastAPI/Uvicorn y PostgreSQL reales. Tests focalizados (9 archivos): `780 passed`. Reconciliación exacta: `1434 + 58 = 1492` (`+25`/`+27`/`+5`/`+1` en los cuatro archivos afectados; no 59). Reutiliza el motor `calcular_frecuencia_colores` ya existente, sin modificarlo, y comparte el mismo envoltorio de histórico/validación de integridad que `frecuencia_numeros_colorloto`. Conecta `frecuencia_colores_colorloto` en `/estadisticas/colorloto/frecuencia-colores` -confirmado con el enrutador real: histórico completo y corte 100 responden 200, cortes inválidos 422, ruta incompatible `/estadisticas/baloto/frecuencia-colores` 404. ColorLoto con dos visualizaciones, sub-navegación propia preservando el corte; navegación numérica (9/9/8) intacta. Identidad de caché idéntica a AE-1, dos cachés vigentes verificadas con parámetros exactos. Integridad histórica sin inconsistencias, 12 categorías del cálculo SQL independiente coincidiendo exactamente con lo cacheado, conservación de masa y comparación JSONB sin discrepancias. Toda esta evidencia fue producida y verificada por el usuario en Windows, no por Claude. **AE-3 (siguientes métricas de ColorLoto) continúa pendiente.** Ninguno de estos números es un total permanente.
**Checkpoint validado (Etapa AE-3, tercera visualización web de ColorLoto -frecuencia de pares número-color, decimosegunda visualización global):** `1554 passed` con `pytest` real en Windows (Python 3.14.6, `pip check` limpio), FastAPI/Uvicorn y PostgreSQL reales. Tests focalizados (9 archivos): `842 passed`. Reconciliación exacta: `1492 + 62 = 1554` (`+28`/`+28`/`+5`/`+1`). Reutiliza el motor `calcular_frecuencia_pares_numero_color` ya existente, sin modificarlo, y comparte el mismo envoltorio de histórico/validación de integridad que las dos métricas anteriores de ColorLoto. Conecta `frecuencia_pares_colorloto` en `/estadisticas/colorloto/frecuencia-pares-numero-color` -confirmado con el enrutador real: histórico completo y corte 100 responden 200, cortes inválidos 422, ruta incompatible `/estadisticas/baloto/frecuencia-pares-numero-color` 404. 42 categorías (7 números × 6 colores), la unidad más granular: par exacto número-color, distinto de frecuencia de números y frecuencia de colores por separado. Codificación `f"{numero}-{color}"` deserializada de forma inequívoca con `split("-", maxsplit=1)`. ColorLoto con tres visualizaciones validadas, sub-navegación ampliada preservando el corte; navegación numérica (9/9/8) intacta. Identidad de caché idéntica a AE-1/AE-2, dos cachés vigentes verificadas con 42 categorías cada una y parámetros exactos. Integridad histórica sin inconsistencias, 84 categorías del cálculo SQL independiente coincidiendo exactamente con lo cacheado, conservación de masa y comparación JSONB sin discrepancias. Toda esta evidencia fue producida y verificada por el usuario en Windows, no por Claude. **AE-4 (siguientes métricas de ColorLoto) continúa pendiente.** Ninguno de estos números es un total permanente.
**Checkpoint validado (Etapa AE-4, cuarta visualización web de ColorLoto -atrasos de números, decimotercera visualización global):** `1614 passed` con `pytest` real en Windows (Python 3.14.6, `pip check` limpio), FastAPI/Uvicorn y PostgreSQL reales. Tests focalizados (9 archivos): `902 passed`. Reconciliación exacta: `1554 + 60 = 1614` (`+25`/`+29`/`+5`/`+1`). Reutiliza el motor `calcular_atrasos_numeros_colorloto` ya existente, sin modificarlo, y el serializador `_serializar_atrasos` ya validado desde la Etapa W. Conecta `atrasos_numeros_colorloto` en `/estadisticas/colorloto/atrasos-numeros` -confirmado con el enrutador real: histórico completo y corte 100 responden 200, la ruta genérica `/estadisticas/baloto/atrasos-numeros` preexistente sigue respondiendo 200 sin interferencia, cortes inválidos 422, métrica incompatible 404. El motor nunca recibe el corte directamente, mismo precedente ya validado por la receta numérica existente. Un número sin aparición se presenta como "N/D", nunca `0`. ColorLoto con cuatro visualizaciones validadas, sub-navegación ampliada preservando el corte; navegación numérica (9/9/8) intacta. Identidad de caché idéntica a las tres métricas anteriores, dos cachés vigentes verificadas con 7 categorías cada una y parámetros exactos. Integridad histórica sin inconsistencias, 14 categorías del cálculo SQL independiente coincidiendo exactamente con lo cacheado, comparación completa y JSONB sin discrepancias. Toda esta evidencia fue producida y verificada por el usuario en Windows, no por Claude. **AE-5 (siguientes métricas de ColorLoto) continúa pendiente.** Ninguno de estos números es un total permanente.

**Checkpoint validado (Etapa AE-4P, endurecimiento transversal -no agrega ninguna visualización, permanecen 13 recetas/rutas/Query/canvas globales, 4 de ColorLoto):** `1678 passed` con `pytest` real en Windows (Python 3.14.6, `pip check` limpio), FastAPI/Uvicorn y PostgreSQL reales. Tests focalizados (8 archivos): `943 passed`. AE-4 permanece validada con `1614` reales. Reconciliación: `1614 + 64 = 1678`. Confirmado con el enrutador real: `4×200`, `3×422`, `1×404`; el usuario abrió las cuatro páginas válidas sin observar errores. PostgreSQL real mostró exactamente ocho filas relevantes -cuatro cachés antiguas sin marcador coexistiendo junto a cuatro nuevas con el marcador exacto (`{"rango_min":1,"rango_max":7,"cantidad_numeros":6,"politica_universo_colores":"vigentes_ultimo_sorteo_mas_observados_v1"}`), hashes distintos entre ambas identidades, exactamente una caché nueva vigente por tipo/escenario, parámetros incorrectos: 0 rows. Categorías 6/6/42/42 confirmadas, conservación de masa exacta en los cuatro escenarios (1254/600/1254/600). Comparación SQL independiente de frecuencia de colores y de las 84 categorías de pares número-color contra la caché nueva: 0 rows en ambos casos, sin ninguna escritura. Toda esta evidencia fue producida y verificada por el usuario en Windows, no por Claude. ColorLoto con cuatro visualizaciones validadas, contrato temporal e invalidación de paleta también validados. **AE-5 (siguientes métricas de ColorLoto) continúa pendiente.** Fase 5 continúa parcial. Ninguno de estos números es un total permanente.

**Checkpoint validado (Etapa AE-5, quinta visualización web de ColorLoto -atrasos de colores, decimocuarta visualización global):** `1747 passed` con `pytest` real en Windows (Python 3.14.6, `pip check` limpio), FastAPI/Uvicorn y PostgreSQL reales. Tests focalizados (9 archivos): `1025 passed`. AE-4 permanece validada con `1614` reales, AE-4P con `1678` reales. Reconciliación: `1678 + 69 = 1747`. Confirmado con el enrutador real: `2×200`, `3×422`, `1×404`; el usuario abrió las dos páginas válidas y reportó "no vi errores en las páginas". PostgreSQL real: las cuatro comprobaciones de integridad devolvieron `0 rows`; dos cachés vigentes con 6 categorías cada una y parámetros exactos con el marcador; cálculo SQL independiente de 12 filas (histórico completo: atraso 0 para cinco colores, ROJO con atraso 1; corte 100: atraso 0 para cuatro colores, AMARILLO con atraso 2, NEGRO con atraso 3) -en estos datos reales ningún color quedó sin observar, por lo que no apareció `N/D`, sin que esto cambie el contrato ya validado por tests para un color vigente nunca observado. Comparación `FULL JOIN` SQL vs JSONB en ambos escenarios: `0 rows`. ColorLoto con cinco visualizaciones validadas, sub-navegación preservando el corte; navegación numérica (9/9/8) intacta. Toda esta evidencia fue producida y verificada por el usuario en Windows, no por Claude. **AE-6 (siguientes métricas de ColorLoto) continúa pendiente.** Ninguno de estos números es un total permanente.

**Checkpoint validado (Etapa AE-6, sexta visualización web de ColorLoto -atrasos de pares número-color, decimoquinta visualización global):** `1810 passed` con `pytest` real en Windows (Python 3.14.6, `pip check` limpio), FastAPI/Uvicorn y PostgreSQL 16 reales. Tests focalizados (4 archivos): `994 passed`. AE-4 permanece validada con `1614` reales, AE-4P con `1678` reales, AE-5 con `1747` reales. Reconciliación: `1747 + 63 = 1810`. Confirmado con el enrutador real: `2×200`, `3×422`, `1×404`; el usuario reportó "No vi errores en las páginas." PostgreSQL real: las cuatro comprobaciones de integridad devolvieron `0 rows`; dos cachés vigentes con 42 categorías cada una y parámetros exactos con el marcador; cálculo SQL independiente de 84 filas (42 pares × 2 escenarios: histórico completo referencia 209/209 sorteos, corte 100 referencia 100/100 sorteos), 42 valores distintos, 0 sin aparición y 6 con atraso 0 en cada escenario. Comparación `FULL JOIN` SQL vs JSONB en ambos escenarios: `0 rows`. En estos datos reales todos los pares habían aparecido, por lo que no se observó un `N/D` real -la semántica queda cubierta por los tests reales, no por observación visual en estos datos. ColorLoto con seis visualizaciones validadas, sub-navegación preservando el corte; navegación numérica (9/9/8) intacta. Toda esta evidencia fue producida y verificada por el usuario en Windows, no por Claude. La siguiente etapa continúa pendiente de definición. Ninguno de estos números es un total permanente.

**Criterios de finalización de la fase completa:** todos los cálculos verificados contra los datos reales (cumplido para lo ya implementado), resultados cacheados para no recalcular en cada request (cumplido), cobertura de ColorLoto y del resto de análisis listados en "Entregables" originales (pendiente).


---

## 🔜 Fase 6 — Simulaciones

**Objetivo:** simulaciones Monte Carlo para estimar el comportamiento esperado bajo el modelo de azar uniforme, y contrastarlo contra los patrones detectados en la Fase 5.

**Dependencias:** Fase 5.

**Entregables:**
- Simulador configurable (100 / 1.000 / 10.000 / 100.000 / 1.000.000 de iteraciones).
- Comparación estadística entre lo simulado (azar puro) y lo observado (datos reales).
- Tabla `simulaciones` (ya presente en el esquema desde la Fase 1).

**Criterios de finalización:** simulaciones reproducibles, resultados persistidos, comparación honesta contra el azar uniforme documentada.

---

## 🔜 Fase 7 — API pública

**Objetivo:** exponer una API REST pública, documentada y con límites de uso, para que terceros puedan consumir estadísticas y predicciones.

**Dependencias:** Fases 3-6.

**Entregables:**
- Autenticación (API keys o similar) — ausente hoy, ver limitaciones de seguridad en el informe de auditoría.
- Rate limiting.
- Documentación OpenAPI/Swagger ampliada (FastAPI ya la genera automáticamente en `/docs`, pero sin autenticación ni límites de uso todavía).
- Versionado de la API.

**Criterios de finalización:** API pública con autenticación, límites de uso, y documentación completa, corriendo en un entorno con monitoreo básico.

---

## 🔜 Fase 8 — Frontend React

**Objetivo:** reemplazar o complementar el frontend Jinja2+HTMX por una aplicación React/Next.js más rica para visualización de estadísticas, modelos y predicciones.

**Dependencias:** Fase 7.

**Entregables:**
- Aplicación React/Next.js consumiendo `api/rest/`.
- Los casos de uso y el backend no deberían requerir ningún cambio — esa es la garantía explícita de la arquitectura actual (`api/web` y `api/rest` ya comparten los mismos casos de uso).

**Criterios de finalización:** paridad funcional con el dashboard HTMX actual, sin duplicar lógica de negocio en el frontend.

---

## 🔜 Fase 9 — Despliegue

**Objetivo:** llevar el sistema a un entorno de producción real, con las prácticas de seguridad y operación que un MVP interno no necesita pero un sistema público sí.

**Dependencias:** todas las anteriores.

**Entregables:**
- Autenticación y autorización en todas las rutas de escritura (hoy no existen — ver informe de auditoría).
- CI/CD.
- Observabilidad (métricas, alertas, no solo el log de archivo actual).
- Backups automáticos de PostgreSQL.
- Revisión de seguridad completa (hoy: sin auth, sin rate limiting).
- Infraestructura como código.

**Criterios de finalización:** sistema corriendo en producción con monitoreo, backups verificados, y una auditoría de seguridad aprobada.

---

## Siguiente decisión recomendada

> **Actualización (Etapa W):** la recomendación de esta sección (opción 2 — conectar una nueva métrica numérica ya existente en el motor) fue ejecutada: se agregó "Distancia desde la última aparición" (`atrasos_numeros`) para números principales de Baloto, Baloto Revancha y MiLoto. Se conserva el análisis original abajo como registro de la decisión tomada. La siguiente decisión de esta misma naturaleza (qué conectar después) no ha sido evaluada todavía.
>
> **Actualización (Etapa Y):** siguiendo la misma lógica de reutilización de motor ya existente, se agregó una segunda métrica numérica -"Distribución de números pares e impares" (`distribucion_pares_impares`)- para los mismos 3 juegos. La siguiente decisión de esta naturaleza sigue sin evaluarse.

> Esta sección es una recomendación de análisis, no una decisión tomada ni una etapa iniciada.

**Opciones evaluadas** (de las planteadas para esta decisión):

1. Extender estadísticas a ColorLoto con métricas propias de colores.
2. Agregar una nueva métrica numérica a los tres juegos actuales (Baloto, Baloto Revancha, MiLoto).
3. Mejorar filtros/cortes temporales en la interfaz.
4. Empezar modelos predictivos (Fase 3).
5. Otra necesidad demostrada por el roadmap real.

**Recomendación: opción 2 — agregar una nueva métrica numérica a los tres juegos actuales.**

**Justificación basada en el estado real del código, no en preferencia:**

- El motor estadístico (`application/estadisticas/motor/`) ya contiene módulos para varios análisis más allá de los tres conectados hoy -atrasos, distribuciones, coocurrencia, patrones temporales, entre otros- pero ninguno está integrado al orquestador ni expuesto en la web. El patrón para conectar uno nuevo (receta en el catálogo + ruta + View Model + plantilla) ya se probó tres veces con las visualizaciones actuales, y toda la capa de caché/invalidación/upsert ya es agnóstica de qué `tipo_estadistica` se agregue -es la extensión de menor riesgo y menor esfuerzo disponible ahora mismo.
- ColorLoto (opción 1) es una extensión legítima pero de mayor alcance: requiere trabajar con una estructura de datos distinta (pares número-color en vez de números simples) y probablemente motor nuevo, no solo conexión de motor existente -mayor incertidumbre que la opción 2.
- Filtros/cortes temporales en la interfaz (opción 3) son una mejora de UX de bajo riesgo -el backend ya soporta `hasta_numero_sorteo` como parámetro en las tres rutas actuales-, pero su valor es limitado si todavía hay una sola métrica numérica por tipo de análisis para filtrar.
- Modelos predictivos (opción 4) dependen, según la nota al inicio de este documento, de un trabajo de estadísticas descriptivas más completo del que existe hoy -la Fase 5 sigue parcial (ver arriba), y empezar Fase 3 antes de agotar el análisis exploratorio que debía alimentarla sería adelantarse al propio orden que este roadmap ya reconoce como el técnicamente más habitual.

No se ha iniciado ningún trabajo de esta recomendación.
