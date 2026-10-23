# Fase 6: calendario y fuentes oficiales

Consulta documental de Codex: **20 de octubre de 2026**, mediante HTTPS con verificación TLS. Se utilizó el mismo dominio oficial de los conectores existentes, `baloto.com`. Esta consulta respalda la configuración inicial del calendario; no ejecutó sincronización, consulta a la BD del usuario, entrenamiento o emisión real.

## Información corroborada

Horas locales de **America/Bogota**. Cuando la fuente ofrece un intervalo, el calendario conserva inicio y fin. La emisión automática para ese evento se bloquea **desde el inicio**, aunque el sorteo no figure todavía en la BD local.

| Juego | Días | Hora/intervalo oficial publicado | Fuente y alcance |
|---|---|---|---|
| Baloto | Lunes, miércoles y sábado | 23:00–23:15 | [¿Qué es Baloto?](https://baloto.com/que-es-baloto): días y franja de transmisión/sorteos |
| Baloto Revancha | Lunes, miércoles y sábado | 23:00–23:15 | La misma página contiene la sección «¿Qué es Revancha?» y el bloque conjunto de sorteos Baloto/Revancha; no se mezclan sus identidades o numeraciones |
| MiLoto | Lunes, martes, jueves y viernes | 22:00–22:15 | [¿Qué es MiLoto?](https://baloto.com/miloto/que-es-miloto/): días/franja explícitos, corroborados por el pie de las páginas oficiales |
| ColorLoto | Lunes; jueves | Lunes 23:40; jueves 23:00 | [ColorLoto](https://baloto.com/colorloto): bloque «¿Dónde puedo ver los sorteos?» y pie de página |

Las páginas no fijan una **hora garantizada de publicación del resultado**. La ventana de observación, la frecuencia de consulta, el tiempo de espera y los reintentos son políticas operativas propias, separadas de la hora del sorteo; no se presentan como compromisos del proveedor. Una ausencia o una respuesta fallida no prueba que el evento siga en el futuro.

### Discrepancia de MiLoto conservada

La [portada](https://baloto.com) incluye un bloque que dice lunes, martes, jueves y viernes **23:00–23:15**, mientras su pie y la página específica de MiLoto dicen **22:00–22:15**. Se prioriza la página dedicada corroborada y se usa el inicio más temprano para la guarda de anterioridad. La discrepancia está archivada y debe revisarse si el operador cambia el calendario; no se silenció ni se convirtió en una garantía de publicación. La consulta a [Preguntas frecuentes](https://baloto.com/preguntas-frecuentes) corrobora días y cita cierres de venta; **esos cierres de venta no se usan como horarios de publicación**.

## Excepciones y confirmación del evento

No se inventa una regla especial de festivos ni se carga una lista supuesta de cancelaciones. Las excepciones son entradas explícitas con fecha local, motivo, referencia y estado de verificación. Pueden cancelar una fecha o añadir/reprogramar otra; la referencia queda unida al evento y las versiones de configuración deben conservarse en el registro operativo. Una excepción no verificada bloquea la emisión automática del juego hasta revisarla: una cancelación dudosa tampoco autoriza saltar al evento siguiente como si su cronología estuviera confirmada. Los cambios de fuente o calendario deben ser revisados explícitamente; consultar la web no cambia por sí mismo configuraciones/modelos.

`clasificar` distingue:

- `sorteo_previsto`: el reloj está antes del inicio y no consta resultado validado.
- `horario_alcanzado_sin_confirmar`: el inicio previsto ya pasó, pero el reloj **no demuestra celebración** ni publicación. La emisión para ese evento queda bloqueada.
- `celebrado_resultado_no_publicado`: se aportó confirmación independiente de celebración y aún no resultado validado.
- `resultado_detectado_validado`: la adquisición validó el resultado; el calendario no reemplaza la validación de identidad, fecha, juego, numeración o integridad.
- `fallo_consulta`: la consulta falló; no equivale a resultado no publicado ni a evento futuro.

Un resultado detectado tarde no reabre el plazo. Recuperar varios eventos usa rangos acotados de fechas, conservando el juego y las fechas locales; **no deduce números de sorteo a partir del calendario**. La numeración procede de datos validados. Baloto y Revancha conservan identidades separadas aunque coincidan los instantes.

## Zona y límites portables

El código usa `zoneinfo.ZoneInfo("America/Bogota")`, con instantes conscientes de zona y comparación en UTC. Rechaza relojes sin zona. Si el entorno no dispone de la base IANA —caso posible en Windows— devuelve un bloqueo accionable para instalar `tzdata` en el entorno operativo validado; no usa la zona local del equipo ni un desplazamiento fijo silencioso. El protocolo de entorno de Fase 6 detalla cualquier dependencia nueva sin actualizar el entorno ML previo por implicación.

La consulta de eventos permite como máximo 370 días por rango inclusivo. Las búsquedas de evento previo/próximo usan el mismo horizonte acotado. La recuperación/importación aplica además sus presupuestos de red y almacenamiento; un calendario no constituye un recorrido de todo el histórico.

## Evidencia de acceso y pruebas

El respaldo de Fase 6 conserva `evidencia/fuentes-oficiales/accesos.json`, HTML originales, texto extraído sin scripts/estilos/comentarios y sus tamaños/SHA-256. Los accesos válidos fueron HTTP 200. También se registraron HTTP 404 de rutas que se probaron y no se usaron como fuentes (`/baloto`, `/revancha`, `/que-es-revancha`, `/miloto/fechas-de-sorteos`); no se interpretaron como horarios faltantes cuando la página específica válida sí estaba disponible. La ruta `/miloto/preguntas-frecuentes` devuelve la página general y no se cuenta como fuente independiente.

Las pruebas de `test_fase6_calendario.py` usan un reloj fijo y datos controlados: días sin sorteo, cambio de fecha UTC/Bogotá, límite exacto de anterioridad, publicación tardía con BD aún atrasada, resultado ya conocido, cancelaciones/reprogramaciones, fuente sin verificar, varios eventos, configuración inválida y ausencia de tzdb. No consultan red ni BD ni dependen de esperar horas. Los resultados y JUnit son nuevos de Fase 6 y se distinguen de los antecedentes ML.
