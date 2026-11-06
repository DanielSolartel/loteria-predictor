# Validacion E10.7 v2 — 6 de noviembre de 2026

Base del producto: `4aaca446c5ea79975683220da0037e2569fbe28e` (PR #111).
La revision del PC recibida en `e107-revision-pc-evidencia-3440caf0865d4870b4d062cceb50f9ef.zip`
tiene codigo 0 y estado `revision_completada`. Su resultado se leyo directamente;
el SHA-256 de `resultado.json` coincide con el manifiesto de esa evidencia.

## Comprobaciones ejecutadas aqui

Entorno de esta entrega: Linux, Python 3.12.14. No es el PC Windows del usuario.

- 30 pruebas `unittest` aprobadas, con subcasos adicionales de entradas invalidas.
  Incluyen permiso propio, persistencia y rechazo antes de efectos; planes
  anteriores; montajes y loopback; extraccion de fuentes y rechazo de cambios a
  `backend/app`; evidencia con CRC/SHA-256; protocolo real por stdin; rechazo de
  detencion de un recurso ajeno; mTLS real sobre loopback con certificado valido,
  nombre incorrecto y ausencia de certificado; validacion X.509 estricta.
  Las tres regresiones v2 comprueban el rechazo de fuentes incorrectas antes
  de crear recursos, la conservacion de bytes UTF-16 al extraer en una carpeta
  sin Git con espacios, y el rechazo al cambiar un byte del archivo de fuentes.
- 8 comprobaciones de la demostracion E10.5/E10.6 aprobadas. Usa HTTP real y
  servicios sustitutos: activacion, 503, lectores coherentes, reversion, diario,
  recuperacion, retencion de datos sinteticos y vencimiento de metricas.
- Sintaxis Python de los modulos nuevos y modificados verificada.
- Los 961 archivos de las fuentes incluidas coinciden byte a byte con sus blobs
  del commit base. Los dos subarboles reconstruidos coinciden exactamente:
  `backend=ae33c618ca11b562d13a71a4f95bbfa7e4c9ab46` y
  `despliegue=95195eb1ecc90f5bfb9b1a150a2f12942a7db22a`.
  El ZIP de fuentes tiene SHA-256
  `9ccaf8f9a9bd573d67d20e4454d9c535d71ed1dbbbb4e34d6794cd63e6d9011e`.
- El protocolo Python real por stdin se ejecuto desde una carpeta vacia con
  espacios y sin Git en PATH, usando el ZIP completo. Verifico las fuentes y
  devolvio el rechazo esperado del entorno Python 3.12, con evidencia integra y
  sin efectos en esa carpeta. Esta prueba no ejecuta PowerShell ni Docker.

El lanzador v2 no recibe `Repositorio`, no invoca Git y no necesita leer el
proyecto local. Las fuentes se entregan completas y verificadas en el paquete.

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
