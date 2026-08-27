# Resiliencia de la sincronización de datos

Este documento responde explícitamente a la pregunta: **¿qué pasa si
la sincronización se interrumpe a la mitad?** -proceso matado,
timeout, corte de red, error inesperado. La respuesta corta: nada se
corrompe, nada se pierde, nada se duplica, y la siguiente
sincronización retoma exactamente donde quedó. Esto no es una
promesa de diseño sin verificar: está cubierto por tests
(`tests/unit/connectors/test_sincronizar_sorteos.py`,
`test_base_connector.py`).

## 1. Cómo se determina el "último sorteo sincronizado"

Este es el punto que hace que todo lo demás funcione. `SincronizarSorteos.ejecutar()`
calcula el punto de partida así:

```python
ultimo_sorteo = None if forzar_completo else self._sorteos.ultimo_sorteo(juego.id)
ultimo_numero = ultimo_sorteo.numero_sorteo if ultimo_sorteo else None
```

`self._sorteos.ultimo_sorteo(juego.id)` es una consulta SQL directa
contra la tabla `sorteos` (`ORDER BY numero_sorteo DESC LIMIT 1`).

**Lo importante: este valor se recalcula desde la base de datos en
cada corrida.** No se lee de un archivo de progreso, no se lee de un
campo cacheado, no se lee del registro de la sincronización
anterior (`EjecucionSincronizacion`). Se lee de lo que realmente está
persistido, ahora mismo, en PostgreSQL.

Esto es deliberado: el registro `EjecucionSincronizacion` existe para
que el panel de Importación pueda *mostrarte* qué pasó, pero
`SincronizarSorteos` nunca lo usa como fuente de verdad para decidir
por dónde continuar. Si lo hiciera, un log de ejecución corrupto o
desactualizado podría hacer que el sistema saltara sorteos que en
realidad nunca se guardaron.

## 2. Por qué una interrupción no produce pérdida de información

Cada sorteo se persiste con su propia transacción de escritura
(`RegistrarSorteo` → `SorteoRepository.guardar()` → `session.flush()`,
con `commit()` automático al final del request/operación vía
`get_db()`). Dentro de `SincronizarSorteos.ejecutar()`, el bucle que
recorre los sorteos descubiertos hace lo siguiente por cada uno:

```python
for draw in resultado_conector.draws:
    try:
        combinacion = draw_detail_a_combination(draw, juego, colores_vigentes)
        registrar_sorteo.ejecutar(...)
        importados += 1
    except (SorteoInvalidoError, SorteoDuplicadoError, ValueError) as e:
        errores.append(...)
        continue  # nunca se detiene el resto del lote
```

Si el proceso muere entre el sorteo N y el N+1, **los sorteos 1..N ya
están confirmados en PostgreSQL** -no hay una transacción global que
envuelva todo el lote y pueda hacer rollback de lo ya guardado. Lo
único que se pierde es el registro de *qué pasó en esa corrida
específica* (`EjecucionSincronizacion` puede quedar en estado
`en_progreso` para siempre si el proceso muere en seco, sin
excepción que active `marcar_completada`/`marcar_fallida`) -pero eso
es solo un dato de auditoría, no la fuente de verdad de qué sorteos
existen.

La siguiente vez que se llame a `SincronizarSorteos.ejecutar()`, el
paso 1 (`ultimo_sorteo()`) verá correctamente que los sorteos 1..N ya
están ahí, y el conector (`fetch_draws`) se detendrá exactamente en
ese punto -no hay hueco, no hay pérdida.

## 3. Por qué no aparecen duplicados al reiniciar

Hay **tres capas independientes** de protección, cada una suficiente
por sí sola, para que nunca se guarde un sorteo dos veces:

1. **El conector nunca vuelve a ofrecer lo ya conocido.**
   `fetch_draws(ultimo_conocido=N)` se detiene en cuanto encuentra un
   `numero_sorteo <= N` (ver `BaseConnector.fetch_draws`). Un reinicio
   con el mismo `ultimo_conocido` produce el mismo corte, nunca una
   ventana más amplia.

2. **La capa de aplicación verifica antes de escribir.**
   `RegistrarSorteo.ejecutar()` llama a `SorteoRepository.existe(juego_id, numero_sorteo)`
   antes de intentar el `INSERT`, y lanza `SorteoDuplicadoError` si ya
   existe -sin tocar la base de datos.

3. **La base de datos es la última línea de defensa.** La tabla
   `sorteos` tiene `UniqueConstraint("juego_id", "numero_sorteo")`
   (`uq_sorteo_juego_numero`). Si dos escrituras llegan casi al mismo
   tiempo (p.ej. dos sincronizaciones del mismo juego lanzadas por
   error) y ambas pasan el chequeo de la capa 2 antes de que la
   primera confirme, PostgreSQL rechaza la segunda inserción con un
   `IntegrityError`. `SorteoRepositorySQLAlchemy.guardar()` captura
   ese error específico y lo traduce a `SorteoDuplicadoError`, la
   misma excepción que ya sabe manejar toda la cadena de arriba -así
   que el resultado para quien llama es idéntico sin importar cuál de
   las tres capas fue la que realmente detuvo el duplicado.

```python
# infrastructure/repositories/sorteo_repository_sqlalchemy.py
try:
    self._session.flush()
except IntegrityError as e:
    self._session.rollback()
    raise SorteoDuplicadoError(str(sorteo.juego_id), sorteo.numero_sorteo) from e
```

La capa 2 cubre el caso normal (secuencial). La capa 3 cubre el caso
de carrera (concurrente) que la capa 2, por sí sola, no puede
garantizar -hay una ventana entre el `SELECT EXISTS` y el `INSERT`
donde otra transacción podría colarse. Confiar solo en la capa 2
habría sido una falsa sensación de seguridad; la restricción `UNIQUE`
es la que realmente cierra esa ventana.

## 4. Reprocesamiento desde HTML: la misma garantía, sin red

`ReprocesarSorteosDesdeHtml` usa exactamente el mismo mecanismo de
upsert (intenta `RegistrarSorteo`; si ya existe, cae a `EditarSorteo`)
y el mismo mapper (`draw_detail_a_combination`) que `SincronizarSorteos`.
Reprocesar el mismo HTML dos veces no duplica nada -la segunda vez
simplemente actualiza el sorteo existente con el mismo resultado
(ver `test_reprocesar_un_sorteo_ya_existente_lo_actualiza_no_lo_duplica`).

## Resumen para quien audite esto más adelante

| Pregunta | Respuesta |
|---|---|
| ¿De dónde sale "el último sorteo conocido"? | `SELECT ... ORDER BY numero_sorteo DESC LIMIT 1` contra la tabla real, en cada corrida |
| ¿Se pierde algo si el proceso muere a mitad de camino? | No -cada sorteo se confirma individualmente; solo se pierde el registro de auditoría de esa corrida específica |
| ¿Puede haber duplicados si se reinicia? | No -tres capas independientes (conector, aplicación, restricción UNIQUE de BD) |
| ¿Qué pasa si dos sincronizaciones corren a la vez? | La restricción UNIQUE de PostgreSQL rechaza la segunda escritura del mismo sorteo; se traduce a `SorteoDuplicadoError` y se reporta como tal, sin corromper nada |
| ¿El reprocesamiento desde HTML puede desincronizarse de la sincronización en vivo? | No -reutiliza literalmente el mismo hook de parseo (`_parsear_pagina_detalle`) y el mismo mapper de dominio |
