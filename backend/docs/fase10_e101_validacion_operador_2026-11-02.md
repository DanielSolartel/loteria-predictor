# Fase 10 · E10.1 — validación del operador y auditoría (2 de noviembre de 2026)

**Estado:** validación automática nativa consolidada y recorrido guiado Brave auditados por Codex dentro de su
alcance; **publicación manual, integración y CI pendientes**. E10.1 no está publicada ni integrada. La Fase 10
global sigue abierta y E10.2 no comienza con este informe.

Este informe consolida la evidencia de E10.1 por procedencia. Las corridas y plataformas **no se suman**: cada
recuento se atribuye a su corrida. Diseño y decisiones: [documento técnico](fase10_e101_seguridad_consola.md).
Protocolo de referencia y lo que se ejecutó: [protocolo Windows/Brave](fase10_e101_windows_brave.md#ejecución-efectiva-r3-2-de-noviembre-de-2026).

## Fuente

| Árbol | Contenido | Archivos |
|---|---|---:|
| `5e2d7df8c73498b3f2e924354de662fd2c9c8d5b` | Base integrada `75facfe55eed1952e917351a9623b5935c744651` | 1048 |
| `b4076bb7d465721ab930be96a0d30ce27c76b3e2` | E10.1 v1 | 1069 |
| `37aef4859f67c1c1d594c6d47bf90d8e8d29f77c` | v2: corrección de los cinco hallazgos de la auditoría de v1 | 1073 |
| `e5fa8854fc2898386d7b6d75e2beb571e5e0cab6` | v3: ajuste de prueba E101-TEST-01; **fuente validada** | 1073 |

La v3 se entregó como ZIP de 262956 bytes, SHA-256 `95976c6223f956eb643d51152580e188990f83c551b844c9fb7e50867b171cb8`.
Este cierre documental modifica solo los dos documentos de E10.1 y añade este informe. No cambia código, pruebas,
configuración, dependencias, workflows, contratos ni tipos.

## Entorno nativo

Windows 11 (10.0.26200), PowerShell 5.1.26100.9711 x64, Python 3.14.6 (MSC v.1944, 64 bits), SQLite 3.50.4.
Brave: versión de archivo 156.1.98.62, ejecutable SHA-256
`040bddd110b2f39a5855431e88935f137d909fd6a2a55479c52364a475362f8a`. Paquetes consignados en el resumen nativo:
fastapi 0.162.0, starlette 1.10.0, httpx 0.28.1, pytest 9.2.0, sqlalchemy 2.1.6, pydantic 2.14.2, jinja2 3.1.6,
python-multipart 0.0.32, uvicorn 0.54.0, psycopg 3.3.6. Sin instalaciones durante los ensayos.

## 1. Windows automático (consolidado)

| Concepto | Resultado |
|---|---|
| Casos únicos consolidados | **264**: **261 aprobados**, **3 omitidos** POSIX, **0 fallos**, **0 errores** |
| Atribución | 260 aprobaciones retenidas de la corrida nativa sobre v2 + 1 del caso corregido en v3 (`test_almacen_corrupto_o_ajeno_esta_cerrado`) |
| ACL nativas | 3/3 aprobadas (`test_permisos_windows_nativo.py`), **incluidas en las 260**; no se suman aparte |
| Omisiones | `test_permisos_del_propietario_y_permisos_abiertos_cierran` y las dos regresiones POSIX de v2 |
| JUnit | previo (v2) SHA-256 `b0cdedfd1be0ab6edab0762e62714d3d4c464cfe7e29ef94ab22a53acc76a930`; caso corregido (v3) `f904207a7ad03a4f0a5c2fc32dad42d98893084a96e1872d91bed4a339ef9db9` |
| Sonda original (`sonda_e101_independiente.py`, SHA-256 `985cf939…596466770`) | modo `despues`, **5/5**, código 0, plataforma `win32`, Python 3.14.6 |

No hubo una batería completa nueva de 264 casos: es una consolidación de dos corridas distintas. La sonda conserva
su leyenda fija («Linux aislado; no acredita Windows…»), que es texto constante del JSON original; la plataforma
real de esa ejecución, `win32`, consta en el propio JSON y en su encuadre. El encuadre registra solo un cierre de
recursos al final (dos conexiones directas), sin cambios en la fuente ni en la lógica de la sonda.

Evidencia de la reanudación automática: `e101-v3-reanudacion-ec95ba78.zip`, 6043 bytes, SHA-256
`6403de7bdf8aad62a73e62eed661b00df11adf96b71cf4e99574abd30befbd24`, CRC correcto y 10 huellas internas.

## 2. Recorrido guiado Brave r3 (nativo)

Corrida del 2 de noviembre de 2026, 22:22:37–22:39:38 UTC (17:22:37–17:39:38, hora de Bogotá). Consola real con sus
guardas, sesiones y CSRF; servicios de negocio y lanzadores **ficticios** y rutas acotadas; servidor de ensayo en
un puerto dinámico de loopback (no el 8765 fijo del ejemplo del protocolo).

- **14 pasos guiados**, cada uno con declaración manual y traza HTTP coincidentes.
- **45 + 6 eventos HTTP** de dos procesos del servidor (antes y después del reinicio): 51 eventos observados, no 51
  pruebas.
- Fuente de 1073 archivos (`e5fa8854…`) idéntica antes y después, sin normalización; índice y referencias
  conservados según el supervisor nativo.
- Evidencia final `e101-v3-brave-r3-1dcd599f.zip`: 18926 bytes, SHA-256
  `490f19c7eb8ca65c07499b873994f0707dc770d0715fba355229ee49e7523d3d`, CRC correcto, 9 huellas internas.

| Comprobación | Resultado observado |
|---|---|
| Lectora | `lectora · lector`, sin Comprobar, Pausar, Reanudar ni Recuperar |
| Salir | POST `/salir` autorizado y con CSRF, 303 al acceso, cookie retirada; **sesiones 1→0** leídas por el supervisor nativo; después, una visita explícita a una URL protegida (Automatización) devuelve 303 al formulario de acceso. Las **9 condiciones** de salida, acreditadas |
| Operadora | `operadora · operador`, solo Comprobar; tres POST de Comprobar con **tres lanzamientos sustituidos**, ningún ciclo ejecutado |
| Permiso administrativo | POST de operadora a Pausar **con CSRF válido**: 403, motivo `permiso`; sin acción de pausa registrada |
| Permiso HTMX | POST de operadora a Colores con CSRF y `HX-Request`: 403, motivo `permiso` |
| Administrador | `daniel-prueba · administrador`, cuatro tipos de acción visibles |
| Alta y retiro HTMX | alta del color ficticio `E101PRUEBA`, 200 y visible; retiro (DELETE) 200 con vigencia cerrada en el servicio ficticio. **No se afirma que el color desaparezca**: el ficticio cierra la vigencia y puede seguir mostrándolo |
| Acciones administrativas | Pausar, Reanudar y Recuperar: POST con CSRF, 303 y registro en los sustitutos; no son operaciones reales |
| CSRF ausente | POST de administrador a Colores **sin token**: 403, motivo `csrf` |
| Revocación | CLI `revocar-sesiones` código 0; la siguiente visita protegida, 303; administrador con 0 sesiones |
| Cambio de rol | CLI `cambiar-rol` código 0; la sesión previa se pierde, se pide acceso y la nueva sesión de operadora es de lector, sin acciones |
| Reinicio | segundo proceso del servidor, misma escucha loopback; la operadora sigue dentro como lector y el administrador sigue rechazado, sin un nuevo inicio de sesión |
| Cookies | `HttpOnly`, `SameSite=Strict`, `Path=/`; `Secure=false` **solo** porque el ensayo es HTTP local |
| Documentación | `/docs` y `/openapi.json`: 404 |

**Revisión visual (Codex):** 12 capturas aportadas por Daniel e inspeccionadas por Codex: identidades y controles de
los tres roles (lectora: 3; operadora: 3; administrador: 3), el rechazo 403 por permiso, el alta del color ficticio y
el rechazo 403 sin CSRF. Se conservan por nombre y huella en el inventario de la auditoría; no se redistribuyen.

## 3. Evidencia Linux (separada; no acredita Windows)

| Corrida (Claude, Linux, Python 3.14.6) | Resultado |
|---|---|
| Suite completa del backend sobre v1 | 8287 aprobadas, 122 omitidas, 0 fallos (tras corregir una primera ronda con 18 fallos) |
| Suite completa del backend sobre v2 | 8371 aprobadas, 125 omitidas, 0 fallos |
| Sonda original | `antes` sobre v1: 5/5 defectos reproducidos; `despues` sobre v2: 5/5 condiciones seguras; contrastes cruzados 0/5 |
| v3 | caso corregido 1 aprobado; módulo `test_almacen_y_credenciales.py` 26 aprobados; contraste con capa de descriptores Windows simulada 2 aprobados |

La auditoría de v1 de Codex repitió además 177 pruebas dirigidas en Linux (Python 3.12.14). Ninguno de estos
resultados se convierte en una prueba de Windows ni se suma a los 264 casos nativos o a los 14 pasos de Brave.

## 4. Intentos anteriores y salvedades

- **r2 sigue incompleto**: hubo salida y retirada de cookie, pero faltó la visita protegida posterior. r3 acredita
  una secuencia nueva y no aprueba retrospectivamente r2.
- La prueba de salida que se ejecutó usa una **URL protegida explícita** tras Salir; el botón Atrás no bastaba como
  comprobación (puede mostrar una página en caché del navegador).
- El PDF anterior **omitía la identidad** (la impresión no incluía la barra de usuario) y no sustituía una captura;
  las capturas de r3 sí la muestran.
- Los rechazos de contraseña corta o no coincidente y los de preparación (carpeta con modo 0o777 rechazada,
  preparación privada 0o700 verificada) pertenecen a intentos previos de aprovisionamiento del ensayo; **no son
  fallos nuevos del producto**. r3 reutilizó las tres cuentas sin pedir contraseñas en PowerShell ni reaplicar
  permisos. El campo histórico `vacia` de la preparación no describe el estado actual del almacén.
- El protocolo histórico de 18 pasos **no se ejecutó completo como recorrido manual**. Los fallos de acceso, la
  admisión concurrente, los límites y las entradas malformadas tienen evidencia automática retenida, no visual.
- **No se acredita**: HTTPS, VPN real, acceso desde otro dispositivo, todas las rutas o tamaños de pantalla por
  inspección manual, ni la búsqueda manual de contraseñas en Windows.
- El 403 de `favicon` procede de la envoltura de rutas acotadas del ensayo; el rótulo «Desconectado» de la
  pantalla de colores no acredita un fallo de la base operativa.
- La consola servida es la real; los servicios de negocio no: no se acredita la operación productiva de esos
  servicios ni una comprobación con datos reales.

## 5. Estado final del ensayo (conservado)

Las cuentas son **sintéticas y temporales del ensayo**; no son cuentas operativas aprovisionadas.

| Cuenta | Rol final | Sesiones |
|---|---|---:|
| `daniel-prueba` | administrador | 0 |
| `lectora` | lector | 0 |
| `operadora` | lector (antes operador; cambiado en el paso de cambio de rol) | 1 persistente de prueba |

No se recrean, restablecen, revocan ni borran para devolver el ensayo a su estado inicial. Los procesos del
servidor de ensayo se cerraron; una sesión persistente en el almacén no equivale a un servidor abierto. Este
informe no incluye SQLite, perfiles, contraseñas, cookies, tokens, HTML ni rutas privadas.

## 6. Conservación

- Decisiones D2 (consulta remota privada por VPN, solo lectura), D3 (Daniel e invitados con consulta), D4 (consola y
  administración solo en el PC) y D12 (almacén privado independiente de cuentas y sesiones), sin cambios;
  identidades de consulta remota y de administración separadas.
- F10-DAT-02 sigue abierto para E10.4 y el protocolo de captura B no queda autorizado.
- Fase 9 e issue #103 permanecen cerrados. Se mantienen `experimental_no_acreditado`, AE-39 **NO-GO** y
  `AUTORIZA_EVALUACION = False`.
- Sin PostgreSQL operativo, Programador, tarea `LP6-01023009031fcabd`, horarios, modelos, fuentes, ciclos ni
  publicación durante los ensayos y esta auditoría.

## Pendiente

Revisión de Codex de este cierre documental; aplicación en Windows, publicación manual e integración por Daniel; CI
del repositorio. Después, la Fase 10 continúa con E10.2 cuando se encargue.
