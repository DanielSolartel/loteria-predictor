# Producto 1 — inventario de datos y código (base `a628c18`)

Inventario breve hecho antes de implementar las estadísticas visibles y el
pronóstico experimental. Las rutas son relativas a `backend/`.

## Fuente real de sorteos

| Aspecto | Dónde | Estado |
|---|---|---|
| Almacenamiento | PostgreSQL (`app/core/config.py`, `DATABASE_URL`); tablas `juegos`, `sorteos`, `sorteo_numeros`, `sorteo_superbalota`, `sorteo_color_numero`, `colores` (`app/infrastructure/db/models.py`, migraciones `alembic/versions/0001`–`0006`) | solo existe en la máquina del operador (Windows) |
| Origen | `https://baloto.com`, por conectores de scraping (`app/infrastructure/connectors/{baloto,baloto_revancha,miloto,colorloto}_connector.py`, registro en `connectors/registry.py`); también CSV y manual (`csv_connector.py`, `manual_connector.py`) | inaccesible desde el entorno Cloud (el proxy responde 403) |
| Actualización | panel `/importacion` (`app/api/web/routers/importacion.py`): sincronizar (incremental), reimportar todo, reprocesar desde HTML guardado en `storage/html/`, validar integridad (huecos), reporte de calidad | manual, desde la interfaz |
| Lectura para análisis | `ResultadosHistoricosRepository` (`app/application/interfaces/resultados_historicos_repository.py`, implementación `app/infrastructure/repositories/resultados_historicos_repository_sqlalchemy.py`): `ResultadoNumerico` (MiLoto, Baloto, Revancha) y `ResultadoColorLoto` (pares número-color), ordenados por `numero_sorteo`, con corte `hasta_numero_sorteo` en el SQL | reutilizado tal cual |
| Rango conocido | Baloto y Revancha: `2081..2705` (625 sorteos cada uno) validados en AE-36 a AE-41; ningún sorteo `>= 2706` en la instantánea de AE-40/AE-41. MiLoto y ColorLoto: rango no registrado en el repositorio | la frescura real solo se puede medir en Windows |
| Integridad | `RegistrarSorteo` valida contra las reglas del dominio; `detectar_huecos_serie_historica` y `validar_consistencia_temporal` (`app/application/estadisticas/motor/generales.py`); `validar_y_ordenar_historico` (`app/application/ml/historico_util.py`) rechaza duplicados y desorden | reutilizado |

En Cloud no hay base de datos poblada ni acceso al origen: **no se inventan
sorteos**. Las fixtures de las pruebas son sintéticas y solo sirven para
probar. La demostración con histórico real queda lista para Windows.

## Reglas de dominio por juego (`app/domain/games/`)

| Juego | Clase | Reglas |
|---|---|---|
| Baloto | `BalotoGame` | 5 números distintos de 1..43, superbalota 1..16 |
| Baloto Revancha | `BalotoRevanchaGame` | igual mecánica, sorteo independiente (nunca se mezcla con Baloto) |
| MiLoto | `MiLotoGame` | 5 números distintos de 1..39, sin superbalota |
| ColorLoto | `ColorLotoGame` | 6 balotas (número 1..7, color de la paleta vigente en `colores`), con repetición |

## Estadísticas existentes

- Motor puro: `app/application/estadisticas/motor/*.py` (frecuencia, atrasos,
  distribuciones, repeticiones, coocurrencia, generales).
- Caché persistente: `CalcularYPersistirEstadistica`
  (`app/application/use_cases/calcular_y_persistir_estadistica.py`, tabla
  `estadisticas`).
- Páginas: `app/api/web/routers/estadisticas.py` con 12 vistas por slug
  (`baloto`, `baloto-revancha`, `miloto`) y 31 de ColorLoto; plantillas en
  `app/templates/estadisticas/`.
- Faltaba: una entrada por juego con último sorteo, cantidad, período, corte,
  frescura y un resumen; el menú lateral solo enlazaba Baloto y ColorLoto
  bajo «Próximamente».

## ML histórico reutilizable (AE-36 a AE-41)

| Pieza | Archivo | Uso en Producto 1 |
|---|---|---|
| Dataset sin fuga (features solo con el prefijo anterior al objetivo) | `app/application/ml/dataset.py`, `features.py` | reutilizado |
| Regresión logística calibrada, semilla 42 (único módulo con sklearn) | `app/application/ml/modelo.py` | reutilizado |
| Log Loss, Brier, Precision@5 (aciertos top-5 / 5) | `app/application/ml/metricas.py` | reutilizado |
| Referencia uniforme `5/43` | `app/application/ml/baselines.py` | reutilizado |
| NO-GO de AE-39 por juego | `DECISIONES_CONTINUIDAD_AE39` en `app/application/use_cases/resolver_estado_prediccion.py` | se muestra, no se cambia |
| Bloqueo operativo de AE-41 | `app/application/ml/autorizacion_operativa.py` | no se modifica; el uso experimental tiene su propio contrato |
| Serialización canónica y SHA-256 de AE-52 | `serializar_entrada`, `hash_entrada` en `app/application/ml/registro_prospectivo.py` | formato de los artefactos persistidos |

Resultados históricos: en AE-36 a AE-39 el modelo nunca superó a la
referencia uniforme (NO-GO para ambos juegos).
