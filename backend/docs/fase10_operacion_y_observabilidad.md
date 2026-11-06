# Fase 10: operación y observabilidad de la consulta privada

Estado: candidato de ensayo de E10.5/E10.6 sobre el merge de PR #110
(`e154a1364f5efaf80895746fa3790f4b30a0176d`). Incluye la preparación de la auditoría
de E10.7. Ensayo nativo aislado aprobado el 2026-11-05: 15/15 casos en Ubuntu/WSL
sobre Windows, con PostgreSQL, nginx, API/pasarela y mTLS reales. Véase el
[acta del operador](fase10_e105_e106_validacion_operador_2026-11-05.md).
La integración y el CI de este candidato siguen pendientes. La fase sigue abierta:
esto no es un despliegue ni una autorización de producción.
No inicia Actions ni modifica sus workflows.

## 1. Alcance y separación

`despliegue/operacion_consulta` añade un controlador local, infraestructura Compose
generada, observación, exportador interno y un informe de preparación. Usa Python y
las dependencias ya presentes; no añade instalaciones, tareas programadas, cuentas
ni certificados al sistema. No toca Fase 6, la consola, el contrato `/api/v1`, las
imágenes, los locks ni las excepciones de vulnerabilidades.

La estrategia de **ensayo** es drenaje y reversión. Es una candidata para D11;
Daniel todavía debe decidir la activación real. No hay un modo `produccion` ni una
opción para saltar esa separación. D1/D5–D8/D10/D11 siguen pendientes.

## 2. Plan e infraestructura

[plan.ejemplo.json](../../despliegue/operacion_consulta/plan.ejemplo.json) es una
plantilla con rutas y digests de relleno. No es ejecutable con recursos reales.
Cada plan fija generación, SHA-256 del manifiesto, huella de `app/`, tres imágenes
por digest, rutas de archivos, host/puerto y redes. Su identificador cubre todos
los campos. Otro digest, ruta o límite produce otro proyecto.

Cada proyecto contiene una API, una pasarela y un proxy. El par queda ligado a
una generación E10.4; no se cambia su URL de base ni su montaje en marcha.

- Sin construcción ni descarga implícita: `--no-build --pull never`.
- UID 10001 en API/pasarela, UID 101 en proxy, raíz de solo lectura, sin capacidades,
  sin nuevos privilegios y con límites de memoria, CPU, procesos y temporales.
- Las redes de API y pasarela son internas, RFC 1918, distintas por generación.
  La red de PostgreSQL es externa al proyecto, interna, con nombre `e105ensayo…`
  y etiqueta `es.loteria.e105.modo=ensayo`. No se crea ni modifica aquí.
- Solo se publica el proxy, en `127.0.0.1`; nunca se publica PostgreSQL, API o
  pasarela. El acceso mediante la red privada todavía requiere infraestructura.
- Los secretos se referencian como archivos montados en ejecución, de solo
  lectura. No van en el JSON, argumentos, entorno, imágenes ni métricas.
- El controlador no usa `down`, `rm`, `prune`, borrado de volúmenes o borrado SQL.
  Conserva los contenedores detenidos y todas las generaciones. La retención de
  E10.4 solo trata pares de respaldos cifrados; aquí no se añade poda de
  generaciones publicadas ni borrado de sus bases.

Se necesita una generación ya importada, una base `pub_<G>` con su rol lector y
la red de ensayo preparada por separado. `secretos/` contiene `api_database_url`,
`api_claves` (huellas), `pasarela_ingreso`, `pasarela_clave_api` y
`proxy_ingreso.conf`, con los formatos del [perfil privado](fase10_consulta_privada.md).
`pki_proxy/` contiene `servidor.crt`, `servidor.key`, `ca-consulta.crt` y `crl.pem`.
`pki_sonda/` contiene `ca-servidor.crt`, `cliente.crt` y `cliente.key` para una
identidad de prueba autorizada. No se crean, exportan ni instalan desde este módulo.

Los archivos deben ser legibles por el UID del contenedor que los monta. Los
directorios montados deben permitir atravesarlos: el directorio de configuración
del proxy es 0755 y sus archivos 0644, bajo el control padre 0700. La carpeta PKI
montada y sus permisos son responsabilidad del ensayo; la clave del servidor debe
ser legible por UID 101. No se cambian los permisos de secretos ajenos para lograrlo.

## 3. Activación y límites

1. Verificar firma, archivos y huellas de la candidata; comprobar la red y propiedad.
2. Arrancar su API/pasarela sin ingreso publicado. Comprobar `/estado` y el vínculo
   de generación, manifiesto, código, esquema, base y solo lectura del perfil E10.4.
3. Escribir el diario antes de cerrar el ingreso anterior. Recargar nginx con
   mantenimiento 503 y `Retry-After: 30`. Confirmar ese 503 mediante TLS mutuo antes
   de empezar a contar el drenaje, porque la recarga de nginx es asíncrona.
4. Esperar el límite de los trabajadores anteriores y detener solo el conjunto
   propio. El límite de ensayo por defecto es 30 s, con un presupuesto de corte de
   120 s. Son parámetros del ensayo, no un SLA adoptado.
5. Publicar el nuevo proxy inicialmente cerrado; abrir, comprobar por TLS mutuo
   `/api/v1/estado` y registrar el cambio de generación activa.
6. Ante un fallo, cerrar y drenar la candidata si tiene ingreso, detenerla,
   arrancar/verificar la anterior y volver a abrirla. Si cualquier comprobación
   falla, conservar la transacción como pendiente y devolver error.

La comprobación del vínculo ejecuta el perfil E10.4 en un **segundo proceso** de
la misma imagen/montajes/configuración. No lee la memoria del trabajador vivo.
Se combina con salud HTTP, `/estado` y la inspección del contenedor: imágenes,
entrypoint/comando, entorno fijado por el plan, redes, puertos y montajes.
No se añade un identificador de generación al contrato público.

Una petición ya admitida pertenece a su par inmutable. El ensayo nativo comprobó
una petición HTTP demorada en la última línea de cabeceras, admitida antes del
reload: terminó con la generación anterior mientras los nuevos lectores recibían
503. También acreditó las esperas de drenaje de 25 s. No ejerció un cliente que
agotase el límite del trabajador; los clientes demasiado lentos pueden perder la
conexión al vencerlo. Reiniciar el par reinicia las cuotas por proceso y los
contadores de `/estado`.

## 4. Estado, interrupciones y propiedad

El control exige POSIX, carpeta 0700 del usuario actual, archivos regulares 0600
con un solo enlace y un bloqueo exclusivo. Rechaza enlaces, FIFO, JSON ambiguo,
planes alterados y un estado copiado desde otra carpeta: dispositivo/inodo de la
raíz forman parte del vínculo. Guarda por renombrado atómico y `fsync`; antes de
cada efecto normal queda su fase pendiente. El historial conserva los últimos
100 eventos y los contadores acumulados se guardan por separado.

Antes de detener **uno** de los contenedores se comprueba el conjunto completo:
propietario aleatorio, proyecto, plan, generación, imagen, UID, proceso, entorno,
montajes de solo lectura, redes y puertos. Un ajeno impide detener todo el conjunto.
Los comandos tienen plazo; al vencerlo se mata exclusivamente el grupo de
procesos de esa invocación de la CLI, incluidos sus hijos. Docker puede haber
aceptado ya una operación: por eso se conserva el diario y se inspecciona de nuevo.

`recuperar` vuelve a la generación anterior; nunca continúa a ciegas la activación
incompleta. Es idempotente una vez resuelta. `revertir` inicia una nueva transacción
hacia el plan anterior y comprueba que la activa no cambió desde la lectura.

Si el disco deja de aceptar escrituras, se intenta igualmente la reversión
física usando el diario ya persistido. No se afirma éxito si no se pudo guardar
el resultado: queda código 4 y se requiere recuperación explícita después de
resolver el almacenamiento. No debe borrarse el control para quitar ese estado.

El JSON privado de control es información de un **operador local de confianza**,
no un archivo de recuperación recibido de terceros. No protege contra root ni
contra un proceso con los mismos permisos que controle todo el directorio y el
daemon. No se importan diagnósticos externos como órdenes de borrado.

El registro del controlador representa el par que ha arrancado este ensayo.
No reescribe `activa.json` de E10.4, que es un selector para el próximo arranque y
por sí solo no cambia procesos. La coordinación de ese selector, los nuevos
paquetes importados y el controlador debe validarse en el flujo nativo antes de
producción; no se habilita un disparador automático del importador.

## 5. Observación, métricas y alertas

El colector `observar` verifica la generación activa y consulta `/estado` con
certificado de cliente. Escribe una muestra acotada sin claves, URLs de base,
identidades, rutas de disco, consultas, números de lotería ni etiquetas por
usuario. Solo exporta agregados de solicitudes, 4xx/5xx, latencia máxima y tiempo
activo. Son gauges por proceso: un reinicio puede ponerlos a cero.

El exportador sirve exclusivamente en **127.0.0.1**: `GET /metricas` y `GET /salud`.
No forma parte de `/api/v1` ni se configura en nginx. Una muestra vencida o
inválida nunca se presenta como sana; `/salud` devuelve 503 y la métrica de
consulta verificada vale 0. Un colector detenido se detecta aunque el exportador
siga vivo. Si todo el host cae, hará falta el monitor externo de D7.

| Señal | Fuente y criterio |
|---|---|
| Antigüedad de captura | `creada_en` del manifiesto firmado y verificado de la generación activa |
| Fecha del último sorteo | Fecha por juego del manifiesto; se compara solo con un calendario explícito y su plazo |
| Contacto del PC | Señal local explícita; sin señal significa desconocido, no que el PC esté caído |
| Capturas rechazadas | Registro explícito de cada intento; una generación antigua no borra rechazos posteriores |
| Generación no activada | Transacción de activación pendiente |
| Activación revertida | Última transición terminal; permanece visible hasta otra activación correcta |

Los umbrales predeterminados son de **ensayo**: captura 36 h, contacto 48 h,
muestra 120 s y 3 rechazos consecutivos. Se sustituyen juntos por un JSON con
`captura_max_s`, `contacto_max_s`, `muestra_max_s`, `rechazos_consecutivos`.
No fijan RPO/RTO. No se deduce actualización a partir de la fecha del sorteo.

`registrar` permite `contacto_pc` o `captura_rechazada`, con hora ISO-8601 y zona.
El colector solo reinicia rechazos tras verificar una captura que no sea anterior
al último rechazo. La conexión automática con el capturador y el monitor externo
no se habilitan: siguen pendientes D7/D10. No existe señal de pausa
persistente, porque aquí no se implementa el protocolo de captura B.

El calendario es un JSON por código de juego con `fecha_sorteo_esperado` y
`resultado_esperado_antes_de` (ISO-8601 con zona). Sin él se informa
`calendario_incompleto`; no se inventa la hora de publicación.

## 6. Uso local y códigos

Desde la raíz del repositorio, con el Python/dependencias ya disponibles y un
directorio padre propio. Estos comandos inicializan y renderizan, sin Docker:

```sh
PYTHONPATH=backend python -B -m despliegue.operacion_consulta --control /ruta/privada/control inicializar
PYTHONPATH=backend python -B -m despliegue.operacion_consulta --control /ruta/privada/control renderizar --plan /ruta/privada/plan.json
PYTHONPATH=backend python -B -m despliegue.operacion_consulta --control /ruta/privada/control auditar
```

El último comando devuelve 3 mientras la autorización de producción siga pendiente.
Para un **ensayo nativo ya preparado y autorizado**, `activar --plan …
--confirmar-ensayo`, `revertir --confirmar-ensayo` y `recuperar --confirmar-ensayo`
usan el daemon local `/var/run/docker.sock`. No se hereda un contexto Docker remoto.
No ejecutar estos pasos sobre la instalación operativa de Fase 6.

Observación puntual: `observar [--reglas …]`; exportación: `exportar --puerto 9125`.
El colector no se programa automáticamente. Un supervisor de ensayo debe
ejecutarlo con una frecuencia menor que la caducidad de muestra. Cada observación
consume una petición de la identidad de prueba y su cuota.

| Código | Significado |
|---|---|
| 0 | Operación completada; en `observar`, muestra escrita (consultar `servicio_verificado`) |
| 1 | Activación fallida y reversión completada, o demostración fallida |
| 2 | Entrada rechazada o error de CLI; no se imprimen secretos ni traceback |
| 3 | Auditoría de preparación: producción sigue sin autorizar |
| 4 | Reversión incompleta o resultado no persistido; conservar diario y recuperar |

Una activación repetida de un plan ya registrado no modifica procesos ni declara
una salud nueva; hay que observarlo para comprobar su estado actual.

## 7. Validación local y preparación de E10.7

```sh
PYTHONPATH=backend python -B -m despliegue.operacion_consulta.demostracion
cd backend
python -B -m pytest -q tests/unit/operacion_consulta
```

La demostración ejerce ocho casos con HTTP loopback real: primera activación,
503/Retry-After durante el drenaje, lector abierto en G y nuevo lector en G+1,
reversión por fallo, interrupción modelada y recuperación persistida, conservación
de datos sintéticos, muestra fresca/vencida y auditoría aún abierta. **Los
servicios y la base son sustitutos**; no se ejecutan Docker, nginx o PostgreSQL.
Las pruebas de TLS usan PKI efímera en archivos locales, sin tocar almacenes de
certificados del sistema. Las de corte usan interrupciones modeladas, no un
ensayo de pérdida de energía ni SIGKILL de servicios nativos.

El módulo de pruebas comprueba también cada fase antes/después de un fallo,
concurrencia del control, corrupción, recursos ajenos, plazos, hijos de la CLI,
comportamiento del exportador y rechazo de configuración de producción.
Está destinado al ensayo **Linux/POSIX**; no se añade a la selección Windows.
El código de `app/`, el contrato OpenAPI y las suites de producto permanecen intactos.

`auditar` hace explícitos los pendientes de E10.7: D1/D5–D8/D10/D11, ensayo
Docker/nginx/mTLS/drenaje/reversión, restauración R-L en destino y R-W en Windows,
revisión SEC/DAT del destino, programación/verificación de respaldos y revisión
de las excepciones de Grype que vencen el 2026-11-17. También queda la coordinación
del selector de E10.4 con el ciclo real de importación/activación. No concede aceptaciones de
riesgo ni cierra la fase al encontrar pruebas locales correctas.

### Ensayo nativo aislado del 2026-11-05

El operador ejecutó `e105-e106-activacion-nativa/4` en Ubuntu/WSL, iniciado desde
Windows PowerShell 5.1. Finalizó con código 0 y 15/15 casos en 277,6 s. Las dos
capturas/importaciones de E10.4, el ciclo de activación y la observación usaron
PostgreSQL, nginx y servicios reales con datos sintéticos nuevos. El rechazo de
sonda, la barrera previa al SIGKILL y el adelanto del reloj son inyecciones
declaradas del arnés. Son resultados separados de las 136 pruebas locales y la
demostración 8/8 anteriores; no se suman entre sí.

El catálogo fijo de `auditar` todavía incluye
`ensayo_nativo_Docker_nginx_mTLS_drenaje_y_reversion`. Su realización en este alcance
consta en el acta; esta modificación documental no cambia el catálogo del código.
El auditor devolvió 3, `transaccion_pendiente=false` y
`produccion_autorizada=false`, como corresponde a los demás requisitos abiertos.
Los ocho contenedores propios quedaron detenidos y las fuentes, generaciones,
bases y recursos sintéticos se conservaron. Detalle, huellas, atribución y límites:
[acta nativa](fase10_e105_e106_validacion_operador_2026-11-05.md).

## 8. Runbooks del ensayo

- **Captura rechazada:** conservar su evidencia, registrar el intento, revisar
  firma/coherencia/código con la guía de [generaciones](fase10_generaciones.md).
  No habilitar captura real ni cambiar Fase 6 para resolverlo. Reintentar solo en
  el entorno y alcance autorizados.
- **Activación fallida:** leer `estado`; si el código fue 1, observar la anterior.
  Si fue 4 o se interrumpió el controlador, conservar control/planes/datos,
  resolver disponibilidad de Docker/almacenamiento y ejecutar `recuperar` dentro
  del mismo ensayo. No usar un control copiado ni borrar bases o carpetas.
- **Regresión posterior:** conservar ambas generaciones y usar `revertir` con el
  ingreso de ensayo; comprobar por observación. Una generación en uso queda fuera
  de cualquier eliminación manual. La retención cifrada de E10.4 no poda esas carpetas.
- **Muestra vencida:** revisar el colector antes de reiniciar la API. Un 503 del
  exportador no demuestra por sí solo que PostgreSQL o el PC estén caídos.
- **Restauración R-W:** sigue el protocolo y autorización nativa de E10.4;
  las pruebas POSIX de este módulo no la sustituyen.
