# E10.7: ensayo local en el PC, con datos sinteticos

Base: PR #111, commit `4aaca446c5ea79975683220da0037e2569fbe28e`.
Destino elegido: PC Windows del usuario, Ubuntu/WSL y Docker Desktop.

La revision del 6 de noviembre de 2026 termino con codigo 0, Docker y Compose
disponibles, 18443/9125 libres y sin avisos. Esa evidencia solo acredita la
revision de lectura. No acredita activacion, respaldo restaurable ni produccion.

## Alcance de esta entrega

El formato `operacion-consulta-local/1` exige `modo=ensayo`, `host=localhost`,
IDs completos `sha256` de imagenes ya locales y un permiso independiente del CI.
El registro `autorizacion-local.json`, dentro de un control POSIX privado NUEVO,
queda ligado a todos los campos del plan. Cambiar imagen, puerto, montaje o
generacion invalida el permiso. Los planes E10.5 anteriores conservan su formato,
serializacion e identidad. La aceptacion B de Grype no sirve como permiso local.

El permiso del perfil se crea exclusivamente al ejecutar el lanzador con
`-AutorizarEnsayoSintetico`. Este archivo es un registro local de la decision;
no es una firma de identidad del usuario ni una aprobacion para datos reales.

El lanzador lee el commit integrado mediante `git archive` y trabaja con una
copia en una carpeta nueva de Ubuntu. No incorpora el arbol de trabajo, archivos
sin versionar, la base real, SQLite privado, `.env` locales ni el Programador.
Los cambios E10.7 se aplican a esa copia; nunca modifican `backend/app`.

El ensayo ejecuta:

1. Comprobacion actual de puertos en Windows y Ubuntu, espacio libre, Python 3.14
   sin privilegios y disponibilidad de las cinco imagenes locales fijadas.
2. PostgreSQL nuevo en una red interna nueva, sin publicar su puerto; roles de
   propietario, lector, importador y captura en ESA base sintetica.
3. Productores sinteticos existentes, captura G1, verificacion e importacion,
   recorrido de la API ligada y respaldo cifrado E10.4 restaurado en una base y
   carpeta nuevas; sus comprobaciones deben aprobarse todas.
4. PKI temporal para localhost, proxy mTLS en `127.0.0.1:18443`, comprobacion de
   la generacion y de `/estado`, rechazo sin certificado y metricas por HTTP
   en `127.0.0.1:9125` durante la prueba.
5. Detencion de sus servicios y contenedores auxiliares, conservando recursos
   y archivos de ensayo para diagnostico. No hay `down`, `rm`, `prune` ni borrado
   de bases externas. La retencion E10.4 solo actua dentro del respaldo sintetico.

La imagen auxiliar no recibe el socket Docker; solo accede a la red de datos
propia y a la carpeta nueva del ensayo. Las fuentes se montan de solo lectura.
La API y la pasarela conservan usuario sin privilegios y sistema de archivos de
solo lectura. No se construyen ni descargan imagenes, se instalan paquetes,
se instala una CA, se cambia la visibilidad del repositorio ni se habilita un
servicio persistente. Fase 6 permanece fuera del alcance del ejecutor.

## Ejecucion

El ZIP de entrega contiene `ensayo_pc.ps1`, `ensayo.py`, `cambios.zip`,
`LEEME.md`, `VALIDACION.md` y `SHA256SUMS`. Verificar la huella del ZIP entregado
antes de extraerlo. Desde PowerShell 5.1, ejecutar el lanzador extraido:

```powershell
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File '<carpeta extraida>\ensayo_pc.ps1' `
  -Repositorio 'C:\GitHub\loteria-predictor' `
  -DirectorioSalida '<carpeta existente para la evidencia>' `
  -AutorizarEnsayoSintetico
```

El cambio de politica solo afecta ese proceso. El repositorio debe contener la
base integrada; no se cambia de rama, descarga ni modifica Git. No se requiere
un checkout limpio porque se archiva el commit, no los archivos actuales.

El preparador puede tardar varios minutos. El lanzador muestra las etapas y
entrega un ZIP nuevo `e107-ensayo-pc-evidencia-<id>.zip`. Compartir ese ZIP y el
JSON final. El ZIP solo contiene el resultado y su SHA-256: nunca claves, URLs
con contrasenas, la PKI ni archivos de la base. Si falla, compartir la evidencia
sin repetir el bloque; un nuevo intento crearia otros recursos.

## Limites y pendientes

`produccion_autorizada` permanece en `false`, incluso con todas las pruebas
aprobadas. El respaldo/restauracion de este recorrido usa datos sinteticos.
No acredita captura real D10, activacion real D11, drenaje y reversion nativos
entre generaciones, recuperacion operativa R-W, custodia externa de respaldos,
acceso de Brave con confianza en una CA, disponibilidad del PC ni monitor externo.
Las excepciones B del CI y su vencimiento del 17 de noviembre no se modifican.

No se ha ejecutado este paquete en el PC al redactar la entrega. Su ejecucion
nativa queda pendiente de recibir la evidencia. El PR se prepara en borrador.

## Verificacion reproducible

```bash
python -B -m unittest discover -s backend/tests/unit/operacion_consulta -p test_perfil_local.py -v
python -B -m despliegue.operacion_consulta.demostracion
```

La primera orden prueba el perfil, permiso, persistencia, aislamiento de archivos,
protocolo stdin, evidencia y mTLS real sobre loopback, incluida validacion X.509
estricta. La segunda conserva las ocho comprobaciones de la demostracion
E10.5/E10.6, con servicios sustitutos y HTTP real. Ninguna equivale al ensayo
Docker/PostgreSQL/nginx ni a PowerShell 5.1.
