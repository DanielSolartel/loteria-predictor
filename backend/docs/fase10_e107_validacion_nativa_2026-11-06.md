# E10.7 v3: validacion nativa del 6 de noviembre de 2026

Ensayo local completado en el PC del operador (Windows, Ubuntu/WSL y Docker
Desktop), con datos sinteticos. Resultado: `codigo=0`, `estado=ensayo_completado`
y **27 de 27 comprobaciones aprobadas**.

## Identidad de la evidencia

- Fecha del registro: 2026-11-06 18:33:05 (America/Bogota).
- Registro UTC: `2026-11-06T23:33:05.562503+00:00`.
- Base integrada: `4aaca446c5ea79975683220da0037e2569fbe28e`.
- Fuentes incluidas: SHA-256 `9ccaf8f9a9bd573d67d20e4454d9c535d71ed1dbbbb4e34d6794cd63e6d9011e`.
- Paquete ensayado: `fase10-e107-ensayo-pc-v3-20261106.zip`.
- SHA-256 del paquete: `24fcb359e8eba3b7f396a2af9df57a947354628e895d08886fb5e079661163e9`.
- Evidencia recibida: `e107-ensayo-pc-evidencia-d5556d0b8970448fb27786b470c53e98.zip`.
- SHA-256 del ZIP de evidencia: `003d0f608184cc6ff4d6a6a98b5b15409d07091c78b79159f03fe42b4ccd6913`.
- SHA-256 de `resultado.json`: `65bf5ebfc61c3d407ab5a0998b19fa3fc79b6a57ee3b9ca3f5dfd2f92dd05bbc`.
- Generacion sintetica: `0e59fed9df61dfa41996aaf246532dec`.

Se abrio el ZIP, se comprobo su CRC y se contrasto el SHA-256 interno del JSON.
Los archivos ejecutables de la correccion coinciden byte a byte con los del
paquete ensayado. Los registros de validacion se incorporan despues del ensayo;
el paquete distribuido conserva su huella original.

## Resultado observado

| Grupo | Identificadores | Aprobadas |
| --- | --- | ---: |
| Fuente, captura, firma, importacion y API ligada | D01-D13, incluido D12b | 14/14 |
| Respaldo, restauracion, comparacion y retencion | R01-R08 | 8/8 |
| Rechazo de respaldo alterado y truncado | N-respaldo-alterado, N-respaldo-truncado | 2/2 |
| Activacion mTLS, rechazo sin certificado y metricas | activacion_local_mtls, sin_certificado_cliente_rechazado, metricas_loopback | 3/3 |

D07 y R08 aprobaron tras reemplazar el cliente TestClient/httpx de las consultas
internas por HTTP de loopback con Uvicorn/h11, disponibles en la imagen de
servicio reutilizada. Se conserva la auditoria de archivos en el mismo proceso.

La restauracion reporta `estado=completa` y `base_nueva=true`. R06 comprueba
revision y huellas de filas; R07, coherencia; R08, los cuerpos de las consultas
contra G1. Los controles negativos tambien aprobaron: un respaldo alterado o
truncado fue rechazado.

El control D11 de esta demostracion registra el selector de la generacion
sintetica. No representa una autorizacion para la decision operativa D11 real.
La comprobacion `activacion_local_mtls` acredita la activacion temporal del
ensayo local y su sonda autenticada.

## Alcance conservado

- Exposicion: `127.0.0.1`.
- Servicios detenidos al terminar: `true`.
- Recursos de ensayo conservados: `true`.
- Fase 6 intervenida: `false`.
- Instalaciones: `false`.
- Imagenes descargadas o construidas: `false`.
- Autorizacion de produccion: **`false`**.

La evidencia recibida contiene solo el resultado y su huella, sin claves ni
URL con contrasenas. No se publican rutas personales del operador.

## Pendientes que este ensayo no cierra

1. Captura con datos reales (D10).
2. Activacion real (D11).
3. Drenaje y reversion nativos entre generaciones.
4. Recuperacion operativa de Windows (R-W).
5. Custodia externa de respaldos.
6. Acceso de Brave y confianza de la CA.

El resultado acredita el ensayo sintetico local de la v3; el PR permanece en
borrador y la autorizacion de produccion requiere su decision independiente.
