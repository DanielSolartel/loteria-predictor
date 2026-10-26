# Fase 9.2 — validación del operador, 26 de octubre de 2026

**Estado:** la validación de la entrega 9.2 y el ensayo nativo B con el Programador
de tareas real están aprobados por la auditoría independiente. Quedan pendientes:

- la publicación manual;
- el CI del nuevo PR;
- la migración controlada de la tarea real `LP6-01023009031fcabd`.

La tarea real sigue habilitada con la programación anterior (versión 1) y el horario
nuevo **no está instalado**. La Fase 9 global sigue abierta.

Se mantienen `experimental_no_acreditado`, el NO-GO de AE-39 y
`AUTORIZA_EVALUACION = False`. No hay acreditación de capacidad predictiva.

La entrega 9.2 tiene dos bloques, sobre el merge del PR #100:

- las páginas de las métricas anteriores. El índice queda con 30, 30, 22 y 36
  métricas por juego ([diseño](fase9_frontend.md#entrega-92-páginas-de-las-métricas-anteriores));
- el horario de consulta por juego de Fase 6 ([horario](fase6_horario.md),
  [migración](fase6_migracion_lp6.md)).

## Entrega y procedencia

- **Base:** `9966a4bbcb8d81953fb283b07544636f4c11fc95`.
- **Cadena de la entrega.** Cada parche incremental se aplica sobre los bytes del anterior:

  | Versión | Paquete | SHA-256 del paquete | Parche | Alcance |
  | --- | --- | --- | --- | --- |
  | v2 | `fase9-2-entrega-v2.zip` | `700ce96dc169e7a569f0be488886e98e8abc41c584e8141a75b1a1ed544ab298` | completo sobre la base, `4cdd74aec328e6b3eaecae5b6527b65316a0914a64df37b96ef59356d3c17e0d` | Entrega 9.2 corregida tras la auditoría de la v1 |
  | v3 | `fase9-2-ajuste-nativo-v3.zip` | `99815eb85cefdff7e8c23f0bf9ea8cd432d8e36ad486bccdfa7b1d0fa2f64f4c` | incremental, `c941ec21cd0c4a9e00d468e280b0563b2f873ff35db220921e1d889ca068ddf2` | F92-NAT-01: controlador, ensayo y sus pruebas; 5 archivos |
  | v4 | `fase9-2-ajuste-pruebas-ps51-v4.zip` | `4fd33808b6a33721a41127c4c2d2446fb410ba63ca3cc7e0006210ffdc31f54a` | incremental, `494b1762022a91c0a811dc91150924d9bbe9a2c7ea3ebc7c206b1996b780ed06` | F92-TEST-01: dos líneas de una prueba |

- **Código validado (v4):** árbol `c0b01a01a6abea280590e2ab1edd3998eb975bc7`, 954 archivos.
  Este cierre solo actualiza ocho documentos y añade este informe, así que el inventario
  final tiene 955 archivos. No cambia código ejecutable, pruebas ni configuración.
- **Versiones:** v2, v3 y v4 son versiones de la **entrega**. El controlador sigue
  registrando la versión 2 de la tarea y de su XML; no hay una versión 3 ni 4 de la tarea.
- **Worktree de Daniel:** `C:\GitHub\loteria-predictor-f92-v2`.
- **Entorno nativo:** Windows 11 10.0.26200, Python 3.14.6 AMD64, pytest 9.1.1,
  Windows PowerShell 5.1.26100.9711 y zona del equipo `SA Pacific Standard Time`.
- **Reparto:** implementó Claude, ejecutó Daniel y auditó Codex. Los resultados
  Linux/Cloud de Claude y del auditor conservan su procedencia y no se presentan como
  resultados Windows.

## Evidencias nativas recibidas

| Archivo | Etapa | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `f92-validacion-v2-fec50189.zip` | Etapa A sobre v2 | — | `d699fb8465a51b54ec3d394d97ba373164c61eb1fa7b234ad50e47595770f6b5` |
| `f92-programador-v2-f66dfc34.zip` | Etapa B sobre v2 (fallida, F92-NAT-01) | 444069 | `c4978e64149e88117f7ad5fec14bbaab99d5b6b8e1fafb30e6adb4e02fc03bb4` |
| `f92-retiro-testigo-ea6ab2e8.zip` | Retirada del testigo de la etapa B fallida | 492771 | `68f705ba9c406999a0b36e33606ca9f35418ad878cbcb69990f0a3fd36bfa86d` |
| `f92-revalidacion-v3-57a1fcde.zip` | Pruebas dirigidas sobre v3 (F92-TEST-01) | 1495171 | `ed337dc66657d37479f2ce297003fc06d6efb976922efc908e37347e7a20a475` |
| `f92-reanudacion-v4-85962e55.zip` | Revalidación sobre v4 y ensayo nativo B | 703569 | `a41f767a20837b82db78f42273ead595cf60ccd3ae03c2afdc721290b005401d` |

La auditoría final verificó el último ZIP: CRC, rutas y entradas correctas, sin
duplicados ni enlaces. Volvió a calcular la consolidación y las comprobaciones del
ensayo desde los JUnit, XML, JSON y el registro de mutaciones originales, sin ejecutar
otra batería del producto.

Los XML nativos y los ZIP de ejecución **no se incorporan al repositorio**: se citan
por su huella y se conservan los originales.

## Resultados

### Etapa A sobre v2 (retenida con su atribución original)

| Comprobación | Resultado nativo |
| --- | --- |
| Python | 772 aprobadas: 394 de Fase 6, 186 de API pública y 192 de pasarela |
| Vitest | 456 aprobadas |
| Tipos, TypeScript, compilación y canario | Correctos |
| Sonda de horario | 3/3 |
| Brave, recorrido normal | 507 visitas y 26 comprobaciones; todas las métricas del índice (30/30/22/36) |

Estos resultados son de la corrida sobre v2. Los ajustes v3 y v4 no tocan el
frontend, la API ni la pasarela, y **no se repitieron** esas baterías: no se atribuyen
a una ejecución v3 ni v4.

### Etapa B sobre v2: fallo F92-NAT-01

- **Qué pasó:** el Programador registró deshabilitada la primera instalación de la
  versión 2. Al exportarla omitió `StartWhenAvailable`, porque su valor `false` es el
  predeterminado documentado.
- **Por qué falló:** el controlador exigía el elemento explícito. Se rechazó la
  instalación y quedó bloqueada la consulta `Estado`, y con ella la limpieza.
- **Alcance:** hubo un solo `Register`, sin activación ni ejecución.
- **Tarea real:** conservó su XML y siguió habilitada.
- **Retirada del testigo:** la hizo el bloque cerrado del auditor (`LP6-338d44802939082e`).
  Archivó los archivos del testigo, confirmó su ausencia y conservó el mismo XML operativo.

### Ajuste v3 y pruebas dirigidas en Windows PowerShell 5.1

- **El ajuste v3:** la omisión del campo vale el predeterminado documentado `false`,
  nunca «el valor esperado». Así una tarea versión 1, que exige `true`, sigue rechazada
  si falta el campo. El ensayo lee el campo de forma estricta, sin reescribir el XML exportado.
- **Revalidación sobre v3:** 121 casos, con 117 aprobados y 4 fallidos, sin errores ni omisiones.
- **Por qué fallaron los 4:** un ayudante de prueba devolvía una sola fila como objeto
  escalar, sin `Count` en Windows PowerShell 5.1 (F92-TEST-01). El ensayo B no empezó.

### Reanudación sobre v4

| Comprobación | Resultado nativo |
| --- | --- |
| Cuatro casos de F92-TEST-01 revalidados | 4/4 aprobados, sin fallos, errores ni omisiones |
| Consolidación de las pruebas dirigidas | 121 casos únicos aprobados: 117 retenidos de la corrida v3 y 4 revalidados en v4 |
| Control de cardinalidad | 24/24 (incluye controles con una emulación declarada) |
| Sonda de documento | 4/4 |
| Lectura semántica del ensayo | 16/16 |

La consolidación junta **dos corridas**. No es una ejecución completa nueva de 121
pruebas ni se suma con las baterías solapadas de la etapa A.

### Ensayo nativo B: Programador de tareas real con un testigo sintético

- **Testigo:** el ensayo usó un testigo propio, `LP6-aa9dcee442bf1e45`, en un worktree
  temporal con un programa de biblioteca estándar. No es la tarea real. No ejecutó el
  producto ni usó datos reales.
- **Pasos:** 14 en total:
  1. plan;
  2. instalación deshabilitada;
  3. activación;
  4. pausa;
  5. retirada;
  6. consulta de ausencia;
  7. instalación de una versión 1;
  8. activación de esa versión 1;
  9. intento de activar esa versión 1 con el controlador nuevo;
  10. migración;
  11. consulta tras migrar;
  12. reversión;
  13. retirada de la versión 1;
  14. consulta de ausencia.

  El paso 9 termina con código 1 **esperado**: el controlador nuevo se niega a activar
  una versión 1 y pide migrarla. Los otros 13 pasos terminan con código 0.
- **Mutaciones:** 16, todas sobre el testigo: Register 4, Enable 2, Start 1, Disable 5
  y Unregister 4.
- **Tarea registrada:**
  - cinco `CalendarTrigger`, sin inicio de sesión ni repetición continua;
  - el Programador omitió `StartWhenAvailable` en la exportación. El diagnóstico lo
    registra con `valor_xml` nulo, `valor_semantico` false, `origen`
    `predeterminado_documentado` y `coincide` true;
  - la exportación original se archivó sin normalizar.
- **Inicio del testigo:** fue **manual**, una sola vez, con `Start-ScheduledTask` a través
  del Programador real. El testigo recibió `ciclo --programado --plan` con la huella
  del plan `a56306a3700c8363657b1ef150dc2c0b834d5cab01be391cf1f519cd6a9e4f6b` y terminó
  con resultado 0.
- **Siguiente inicio:** el que informó el Programador coincide con el cálculo
  independiente del plan: `2026-10-27T03:30:00+00:00`, el lunes 26 de octubre a las
  22:30 de Bogotá. Corresponde al testigo, que ya se retiró.
- **Lo que no se observó:** no se esperó un disparo automático futuro ni se ejecutó un
  ciclo del producto contra datos reales.
- **Migración y reversión sintéticas:** pasaron de la versión 1 a la 2 deshabilitada y
  de vuelta a la 1 deshabilitada, sin activación intermedia implícita.
- **Limpieza:** completa, sin avisos ni tareas o temporales pendientes de este ensayo.

## Hallazgos cerrados

- **F92-NAT-01** (corregido en v3): el Programador omitió `StartWhenAvailable`, y la
  instalación y la consulta se validaron en Windows. El XML original no se normalizó.
- **F92-TEST-01** (corregido en v4): los consumidores del ayudante capturan la colección
  como arreglo y pasaron en Windows PowerShell 5.1. Las aserciones y los rechazos de
  valores no válidos siguen vigentes.

Los hallazgos de la auditoría de la v1 (F92-PS-01, PS-02, PS-03, HOR-01, REV-01 y
EV-01) quedaron corregidos en la v2, antes de esta validación nativa. Todas las etapas
nativas descritas aquí usaron ese código corregido.

## Conservación y límites

- **Fuente:** en Windows se comprobaron los inventarios v3 y v4, el HEAD y el índice.
  Solo cambió el archivo de pruebas autorizado; los otros 953 archivos quedaron iguales.
- **Referencias protegidas:** las seis conservaron su contenido, su HEAD y su índice.
- **Herramientas:** los scripts usados coinciden con las copias auditadas. Las fuentes
  del controlador, el ensayo y la referencia v1 coinciden con el inventario v4.
- **Tarea real `LP6-01023009031fcabd`:** sigue habilitada con su programación anterior.
  Los cuatro XML operativos archivados tienen el SHA-256
  `61190fa7263750ae8434f9d7052adbc077a77ed0146a8fe52eb56ac29ce7c296`.
- **Lo que no se hizo:** no hubo SQL operativo, ciclos operativos, commit, push ni PR,
  ni cambios a la tarea real desde los supervisores.
- **Contenido de este informe:** omite SID, nombres de usuario, rutas temporales y
  secretos.
- **Pendientes que este ensayo no resuelve:**
  - la limpieza separada de restos históricos de Fase 6;
  - la verificación con una zona del equipo distinta de la de Bogotá: el ensayo usó una
    zona con el mismo desfase;
  - el defecto conocido de `NO_COLOR` en el orquestador del recorrido Vite;
  - la acreditación prospectiva.

## Pendiente

1. Revisión de este cierre y publicación manual de Daniel: commit y PR.
2. El CI del nuevo PR, incluida la selección Windows. No hay checks aprobados todavía.
3. La migración controlada de `LP6-01023009031fcabd`. Se preparará después, como un
   bloque separado, con respaldo y reversión, a partir del
   [procedimiento](fase6_migracion_lp6.md#1-plan-de-la-migración-real-posterior-a-la-auditoría-y-a-la-publicación).
   Ni este cierre ni el ensayo la ejecutan ni la dejan automatizada. Activar la tarea
   migrada es una decisión aparte de Daniel.

Las horas de la propuesta inicial son configurables y no son horarios oficiales de
publicación. La matriz de huecos y el criterio final de la Fase 9 no cambian con
este cierre ([matriz](fase9_frontend.md#matriz-de-huecos-de-la-fase-9)).
