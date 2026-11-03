# E10.2 + E10.3 — validación nativa del operador (3 de noviembre de 2026)

## Estado y alcance

La validación nativa de la v4 está **completada y auditada**. Daniel ejecutó el procedimiento en Windows;
Codex comprobó los archivos de evidencia sin repetir las ejecuciones. Quedan pendientes la publicación manual,
la integración, el CI remoto y el escaneo real de imágenes con Grype. E10.4 y la producción siguen pendientes;
la Fase 10 no está cerrada.

Se conserva la separación acordada: consulta privada de Daniel e invitados por VPN (D2/D3), administración
solo en su PC (D4), cuentas y sesiones de la consola en un almacén privado separado (D12). Este ensayo no
despliega la VPN ni acredita la topología de producción. F10-DAT-02 sigue abierto para E10.4; el protocolo B
de pausa operativa no está aprobado. Se conservan `experimental_no_acreditado`, AE-39 NO-GO y
`AUTORIZA_EVALUACION = False`. Fase 9 y el issue #103 siguen cerrados.

## Fuente y evidencia recibida

- Base integrada: `375fc8caf9ac7f901136c1f19acd6d5521a5a9a9`, árbol
  `32d155fa53bfdf5becc9fff043d3e74d7c13af99`, 1074 archivos.
- Fuente v4 aplicada y conservada durante toda la validación: árbol
  `d8b411c701c6d828f5c1c58e6c008fc00a220899`, 1116 archivos, bytes exactos sin normalización.
- Entrega v4: `fase10-e102-e103-entrega-v4-20261103.zip`, SHA-256
  `b042bb857d258af90de9fc5b288b45bf2966024f0ef1da97acb16d7fd6e731c8`.
- Evidencia nativa: `e102-v4-nativo-2bec6923802d-brave.zip`, **22309 bytes**, SHA-256
  `03a4ad0f4eaff274e698dec193c55a7170580958e53524958776ee26fa3a6ba5`. CRC correcto: 26 entradas y 25 huellas internas exactas, sin entradas sobrantes.
- Periodo UTC: 2026-11-03T10:28:07.717180+00:00 a 2026-11-03T10:32:48.698861+00:00. Los tiempos de Brave se registran aparte con offset -05:00.

| Archivo interno | SHA-256 |
|---|---|
| `resumen.json` | `68e3b81edc026abd920198bc3f58113eac9a5f2731a3e78522e02b726b8f1e4d` |
| `junit-windows.xml` | `8c4b18b3b32c4168b67eeeb29ae85ae1fa8e3bd9604a427f7cceba903578c474` |
| `brave-focal.json` | `a087b4e380ec25c130bebc3911df83a4cfafab8405030efb07d21eae3495f00c` |
| `ausencias-brave.json` | `8017f72d40cced4cff4cc2f13eb53b665d93d4c4917d7a47d6aa76d5db044e97` |

Los ZIP originales se conservan sin modificar. La evidencia distribuida excluye perfiles, material de claves,
PFX y almacenes privados; el informe usa resultados y huellas, sin reproducir identificadores personales.

## Windows: entorno, lock y pruebas

Windows 11 10.0.26200, Python **3.14.6 x64**, Windows PowerShell **5.1.26100.9711**, edición Desktop.
Se creó un clon separado y un venv nuevo. La instalación usó `--require-hashes --no-deps --only-binary :all:`;
`pip check` respondió `No broken requirements found`. Los **58 paquetes aplicables en Windows** coinciden
exactamente con el lock universal (59 en la unión de plataformas). `pip` es la herramienta de arranque del
venv, no un paquete del lock. No se instaló nada en el entorno anterior.

El JUnit registra **206 casos únicos: 206 aprobados, 0 fallos, 0 errores y 0 omisiones**.

| Módulo | Casos aprobados |
|---|---|
| `tests.unit.api_publica.test_api_publica_privada` | 45 |
| `tests.unit.pasarela.test_pasarela_aislamiento` | 3 |
| `tests.unit.pasarela.test_pasarela_privada` | 53 |
| `tests.unit.test_bloqueo_dependencias` | 6 |
| `tests.unit.test_ci_umbral_vulnerabilidades` | 48 |
| `tests.unit.test_comprobar_contenido_imagen` | 12 |
| `tests.unit.test_ensayo_brave_e102` | 29 |
| `tests.unit.test_servidor_mtls_e102` | 10 |

Las pruebas del arnés ejecutadas bajo PowerShell 5.1 usan sustitutos para los escenarios de error. El ensayo
de Brave descrito a continuación sí utiliza los almacenes de certificados y las claves CNG reales del
usuario. No se suman ambos tipos de comprobación como si fueran una misma prueba.

## Brave: certificado de cliente y finalización reales

Brave **156.1.98.62**, ejecutable SHA-256
`040bddd110b2f39a5855431e88935f137d909fd6a2a55479c52364a475362f8a`. La sesión usó un perfil temporal propio y un servidor local
en `https://localhost:56565/` (puerto dinámico). El servidor verificó `CN=invitado-brave`.

El resumen del ensayo contiene **15 pasos correctos**, `codigo_ensayo = 0`, `codigo = 0`,
`limpieza_completa = true`, `resumen_guardado = true`, sin errores ni residuos y sin diagnóstico pendiente:

- El servidor terminó cooperativamente con código 0.
- Se cerraron los **7 procesos propios** de Brave.
- Se retiró la CA temporal del almacén raíz del usuario por su huella exacta.
- Se eliminaron **3 certificados y sus 3 claves privadas** (CA, cliente y servidor).
- Se retiraron el perfil y la carpeta temporales de esta ejecución.

Después se ejecutó una comprobación independiente **de solo lectura**, limitada a los identificadores propios:
confirmó la ausencia de los 3 certificados y las 3 claves, sin hallazgos, junto con las ausencias del perfil y
de sus procesos. Esto acredita el funcionamiento real del proveedor de certificados, CNG y Brave en este
ensayo local; no demuestra el despliegue de la pasarela, el proxy y la API en una infraestructura de producción.

## Conservación y atribución

- El árbol de la fuente aplicada y final coincide exactamente; índice y referencias Git se conservaron.
- Las tres fotografías de metadatos del entorno anterior (antes, tras las pruebas y tras Brave) son iguales.
- No se accedió al origen operativo, PostgreSQL operativo, Programador, tarea ni ciclos de Fase 6.
- No hubo commit, push, PR ni Actions en el procedimiento nativo.
- La autoprueba de salida devolvió 7 y la autoprueba de plazo 124, ambos esperados. Los demás pasos dieron 0;
  no hubo cancelaciones ni plazos vencidos fuera de esa autoprueba.

Los resultados de Linux pertenecen a sus corridas previas, **no repetidas ni sumadas** a estas 206 pruebas:
la v2 conserva 1336 regresiones aprobadas y 3 omisiones nativas de Windows, 864 pruebas de Vitest, demostración
32/32 y sonda 11/11; la v4 conserva sus 54 comprobaciones del arnés bajo PowerShell 7.4/7.6 en Linux y sus
controles negativos. Sus informes son evidencia histórica; esta validación de Windows no los convierte en CI.

## Pendientes que se mantienen

- **CI remoto:** primera ejecución de los workflows sobre la publicación final, incluidos los cinco checks
  existentes y los seis jobs de seguridad nuevos. La validación nativa local no sustituye estos jobs.
- **Grype real:** sigue pendiente, sin informe limpio. El entorno de Claude denegó la descarga de su base
  (`grype.anchore.io`, 403); esto no demuestra que GitHub Actions tenga el mismo bloqueo. Sin un informe
  válido que cumpla el umbral, el escaneo no se considera aprobado. No se aceptan excepciones por esta nota.
- **E10.4:** importador y coherencia de la captura (F10-DAT-02) pendientes; no hay imagen de importador.
- **Producción:** proveedor, presupuesto, infraestructura, registro, secretos reales, respaldos, activación,
  CA real, VPN y límites globales entre réplicas continúan sujetos a las decisiones y entregas correspondientes.

El cierre de esta validación solo actualiza documentación; código, pruebas, locks, imágenes, workflows,
contratos y Fase 6 conservan los bytes de la v4.
