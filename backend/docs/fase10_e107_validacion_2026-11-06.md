# Validacion E10.7 — 6 de noviembre de 2026

Base del producto: `4aaca446c5ea79975683220da0037e2569fbe28e` (PR #111).
La revision del PC recibida en `e107-revision-pc-evidencia-3440caf0865d4870b4d062cceb50f9ef.zip`
tiene codigo 0 y estado `revision_completada`. Su resultado se leyo directamente;
el SHA-256 de `resultado.json` coincide con el manifiesto de esa evidencia.

## Comprobaciones ejecutadas aqui

Entorno de esta entrega: Linux, Python 3.12.14. No es el PC Windows del usuario.

- 27 pruebas `unittest` aprobadas, con subcasos adicionales de entradas invalidas.
  Incluyen permiso propio, persistencia y rechazo antes de efectos; planes
  anteriores; montajes y loopback; extraccion de fuentes y rechazo de cambios a
  `backend/app`; evidencia con CRC/SHA-256; protocolo real por stdin; rechazo de
  detencion de un recurso ajeno; mTLS real sobre loopback con certificado valido,
  nombre incorrecto y ausencia de certificado; validacion X.509 estricta.
- 8 comprobaciones de la demostracion E10.5/E10.6 aprobadas. Usa HTTP real y
  servicios sustitutos: activacion, 503, lectores coherentes, reversion, diario,
  recuperacion, retencion de datos sinteticos y vencimiento de metricas.
- Sintaxis Python de los modulos nuevos y modificados verificada.

Ordenes:

```bash
python3 -B -m unittest discover -s backend/tests/unit/operacion_consulta -p test_perfil_local.py -q
python3 -B -m despliegue.operacion_consulta.demostracion
```

## Ejecuciones pendientes

No se dispone aqui de Docker, PostgreSQL, Python 3.14 ni Windows PowerShell 5.1.
No se ha ejecutado el ensayo nativo de este paquete. La suite anterior de 136
pruebas pytest no se reejecuto en este entorno, donde pytest no esta disponible.

El ejecutor entregado debe realizar en el PC los productores reales con datos
sinteticos, la captura/importacion, respaldo cifrado y restauracion E10.4 en una
base y carpeta nuevas, seguida de activacion local, mTLS, rechazo sin cliente y
metricas. Hasta recibir ese ZIP no se afirma que ese recorrido haya aprobado.

El ejecutor verifica las imagenes existentes y se detiene si falta alguna; no
instala dependencias, construye imagenes ni las descarga. Sus recursos se
conservan y sus servicios se detienen al terminar. Un error de detencion produce
codigo distinto de cero y `estado=detencion_pendiente`.

Se mantienen pendientes los datos reales D10, activacion real D11, drenaje y
reversion nativos, recuperacion R-W, custodia externa y acceso de Brave. La
autorizacion de produccion permanece en false. La evidencia no contiene claves.
