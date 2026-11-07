# E10.7: diagnostico de lectura del ensayo conservado

El ensayo v2 puede detenerse con `comando_local_rechazado` si un auxiliar
termina con error. Ese resultado no conserva por si solo la causa exacta.
Este lector consulta los recursos conservados para identificar el paso fallido.

El lanzador recibe `DirectorioEnsayo` del JSON de evidencia, por ejemplo una
ruta `/tmp/e107pc-<id>`, y una carpeta existente para la salida. No necesita Git
ni la carpeta local del proyecto. Docker se fija al socket local de Ubuntu.

Solo admite las consultas Docker `ps`, `inspect` y `logs`. Atribuye los
contenedores al ensayo por etiqueta, nombre, imagen, comando y montajes.
Contempla la traduccion de origenes de montajes de Docker Desktop. No inicia,
reinicia, detiene, ejecuta comandos dentro de contenedores, borra recursos ni
consulta PostgreSQL. Tampoco lee archivos de claves o URL de la base.

Procesa los logs localmente y exporta solo campos cerrados: identificadores de
pasos y su resultado, codigos de salida, indicador OOM, clases de excepciones,
modulos de una lista permitida, indicios predefinidos y archivo relativo/linea
de codigo si aparecen. No exporta logs crudos, mensajes de error libres,
variables de entorno ni valores de contrasenas. Los metadatos de rutas solo
incluyen existencia, propietario numerico y permisos; no su contenido.

El paquete contiene el lanzador PowerShell, el lector Python, sus pruebas,
validacion y SHA-256. Desde PowerShell 5.1:

```powershell
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File '<carpeta>\diagnosticar_pc.ps1' `
  -DirectorioEnsayo '/tmp/e107pc-<id del JSON>' `
  -DirectorioSalida '<carpeta existente>'
```

Entrega un ZIP nuevo `e107-diagnostico-evidencia-<id>.zip` con JSON y su SHA-256.
Compartir ese ZIP y la salida para decidir la correccion; esta lectura no
repite el ensayo ni acredita su activacion o su restauracion.

Si la excepcion fue descartada antes de imprimirse, los logs conservados pueden
no contenerla. El lector lo refleja sin inventar una causa. No modifica la
evidencia del intento original, Fase 6 ni el estado de autorizacion de produccion.
