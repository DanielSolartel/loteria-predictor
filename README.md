# Sistema Predictivo de Loterías Colombianas

Plataforma de análisis estadístico y adquisición de datos para MiLoto, Baloto, Baloto Revancha y ColorLoto. Construida con **Clean Architecture** sobre FastAPI + PostgreSQL, con un dashboard HTML/HTMX y una API REST equivalente.

> **Aviso importante:** este sistema analiza patrones estadísticos en resultados históricos de loterías genuinamente aleatorias. No predice, no garantiza, ni puede garantizar resultados futuros. El valor del proyecto está en el rigor del análisis y la calidad de la ingeniería, no en "ganar la lotería".

---

## Estado del proyecto

| Fase | Descripción | Estado |
|---|---|---|
| 1 | Dominio + MVP HTML/HTMX | ✅ Completa |
| 2 | Adquisición automática de datos (scraping, sincronización, reprocesamiento) | ✅ Completa |
| 5 | Estadísticas descriptivas | 🟡 Parcial — ver [detalle abajo](#estadísticas) y [ROADMAP.md](./ROADMAP.md) |
| 3, 4, 6, 7, 8, 9 | Machine Learning, Predicciones, Simulaciones, API pública, Frontend React, Despliegue | 🔜 Ver [ROADMAP.md](./ROADMAP.md) |

Para el diseño técnico completo (capas, diagramas de flujo, decisiones de arquitectura, motor estadístico) ver [ARCHITECTURE.md](./ARCHITECTURE.md).

---

## Estadísticas

Nueve visualizaciones disponibles para **Baloto**, **Baloto Revancha** y **MiLoto** (ocho para MiLoto en la superbalota, ver más abajo):

- Frecuencia de números principales.
- Frecuencia de superbalota (Baloto y Baloto Revancha — MiLoto no tiene superbalota, esa página lo indica explícitamente en vez de fallar).
- Frecuencia observada vs. esperada (comparación contra la probabilidad teórica uniforme).
- Distancia desde la última aparición (números principales, en numeración de sorteos, respecto del último sorteo real dentro del corte seleccionado — nunca respecto de un número de sorteo hipotético que no exista en el histórico. Es descriptiva, no predictiva: incluye un aviso explícito de que el tiempo transcurrido no cambia la probabilidad futura de un número).
- Distribución de números pares e impares (cuántos de los K números principales de cada sorteo son pares, tabulado sobre 0..K sorteos históricos — no es frecuencia individual de números ni coocurrencia de pares).
- Distribución inferior/superior (cuántos de los K números principales caen en la mitad inferior del rango del juego — 1–21/22–43 en Baloto y Revancha, 1–19/20–39 en MiLoto. Los dos grupos **no** tienen exactamente el mismo tamaño; la página lo explica junto a la definición de los grupos, nunca los presenta como mitades iguales).
- Distribución de pares consecutivos (cuántos pares de números adyacentes, con diferencia exactamente 1, aparecen en cada sorteo, tabulado 0..K-1. Los pares pueden solaparse: 1,2,3 contiene dos pares consecutivos. Descriptiva, no predictiva: no sugiere que los consecutivos sean menos probables o "menos aleatorios").
- Racha máxima de números consecutivos (la longitud del bloque más largo de números consecutivos dentro de cada sorteo, tabulado 1..K — nunca incluye la categoría 0, ya que todo sorteo válido tiene al menos una racha de longitud 1. **Distinta de "pares consecutivos"**: 1,2,3 tiene 2 pares consecutivos, pero su racha máxima es 3. Descriptiva, no predictiva: una racha larga o corta no hace que un sorteo sea anómalo ni permite predecir resultados futuros).
- Repeticiones entre sorteos consecutivos (cuántos números principales coinciden entre un sorteo y el número de sorteo inmediatamente siguiente — una "transición" solo es válida cuando `numero_sorteo_actual == numero_sorteo_anterior + 1`; un hueco en la numeración no genera ninguna transición, nunca se fabrica una comparación entre sorteos que no son consecutivos reales. El denominador de esta métrica **no** es la cantidad de sorteos, sino la cantidad de transiciones válidas — la página lo presenta explícitamente como "Transiciones analizadas", nunca "Sorteos analizados". Descriptiva, no predictiva: una repetición pasada no aumenta ni reduce la probabilidad de repetición futura).

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
```
donde `{juego_slug}` es `baloto`, `baloto-revancha` o `miloto`.

**ColorLoto todavía no está incluido** en estas visualizaciones numéricas (estructura de datos distinta) — Fase 5 sigue parcial (ver [ROADMAP.md](./ROADMAP.md)). El caché de resultados se invalida automáticamente al registrar, editar o eliminar un sorteo del juego correspondiente, sin afectar a los demás juegos. Antes de calcular una distribución que depende de la cantidad exacta de números por sorteo (pares/impares, inferior/superior), el sistema valida que el histórico persistido sea consistente (cantidad correcta, sin duplicados, dentro de rango) — si encuentra una inconsistencia, responde con un error controlado (500, sin exponer detalles internos) en vez de calcular sobre datos corruptos. Detalle técnico completo (motor, caché persistido, invalidación, upsert, validación de integridad) en [ARCHITECTURE.md](./ARCHITECTURE.md#motor-estadístico-y-caché-persistido).

Chart.js se sirve localmente (`app/static/vendor/chartjs/chart.umd.min.js`, versión 4.4.4, licencia MIT), no desde un CDN externo.

**Corte por número de sorteo (Etapa X):** las 4 visualizaciones incluyen un control `GET` (`?hasta_numero_sorteo=N`) para acotar el análisis hasta un sorteo específico. **El corte es específico del juego actual**: cambiar de métrica dentro del mismo juego lo conserva; cambiar de juego siempre vuelve al histórico completo, porque la numeración de sorteos de Baloto/Baloto Revancha no es comparable con la de MiLoto (series independientes, con rangos de numeración completamente distintos) — no es una limitación accidental, es la semántica correcta. `0` y valores negativos devuelven `422` (JSON, mecanismo de validación nativo de FastAPI); ningún valor inválido llega a calcularse ni a persistirse en caché.


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
| Frontend | Jinja2 + HTMX + Bootstrap 5 |
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

---

## Licencia

Uso educativo/personal. Este proyecto no está afiliado a Baloto, Coljuegos, ni a ningún operador oficial de loterías. Los datos se obtienen de la información pública disponible en el sitio oficial únicamente con fines de análisis estadístico.
