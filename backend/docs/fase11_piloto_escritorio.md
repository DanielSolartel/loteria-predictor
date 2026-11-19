# Fase 11. Lotería Predictor para Windows

El visor sirve React y las consultas de FastAPI desde un único origen en `127.0.0.1`. La versión operativa lee las carteras y los resultados de Fase 6. La v2 añade el registro local de jugadas con su modelo de origen y sus aciertos por juego.

## Uso del visor con datos de Fase 6

El instalador operativo requiere Windows x64, el entorno Python de Fase 6, la tarea programada de ese entorno y el rol PostgreSQL `loteria_visor_lector`. El lanzador entregado localiza la tarea `LP6-01023009031fcabd` y comprueba su configuración antes de abrir el navegador. El acceso a PostgreSQL usa transacciones de solo lectura. La tarea programada mantiene su propio ciclo de actualización.

1. En el equipo validado, abre Docker Desktop y espera a que PostgreSQL de Fase 6 esté disponible.
2. Si vas a actualizar desde la v1, cierra el visor. Comprueba el SHA-256 del ZIP, extrae el ejecutable y abre `Instalar-Loteria-Predictor-v2.exe` con doble clic desde tu cuenta normal. El instalador admite instalación nueva o actualización desde la v1 comprobada.
3. Abre **Lotería Predictor** desde **Inicio**. Escribe la contraseña del rol lector en la consola. En el navegador debe aparecer **Datos reales de Fase 6**.
4. Pulsa **Cerrar piloto** para liberar las conexiones del visor y retirar su carpeta temporal. Un cierre normal desde la versión instalada termina con código `0`.

En el primer arranque de la v2 se registró `OperationalError` al verificar el lector. El operador volvió a abrir el visor tras iniciar Docker Desktop y accedió a los datos reales. La evidencia inicial registra que se retiró la carpeta temporal y hubo cero intentos de escritura en las fuentes de Fase 6.

La v1 operativa se verificó en Windows el 12 de noviembre de 2026. El JSON `evidencia-f11-fase6-aa150fcdf167.json` registró las consultas de los cuatro juegos, comparación y sincronización con PostgreSQL 16.14 y Alembic `0006`. El rol lector tenía `SELECT` en ocho tablas. El cierre liberó el puerto y las conexiones. La desinstalación retiró el programa, su entrada de Windows y el acceso de Inicio. El JSON conservó el SHA-256 `8294afb29ed65b0cc9207cccfd0cc6896f73ee7e46570e5ecbaa07f1736cd4ba`.

### Mis apuestas en la v2

Elige **Registrar apuesta** junto a una línea en **Predicciones** o **Historial de aciertos**. El formulario trae la combinación de la cartera guardada y propone su sorteo objetivo. Confirma el sorteo y los juegos en los que usaste esa combinación. Si eliges Baloto y Revancha en el mismo registro, la jugada conserva un único modelo de origen y cada juego recibe sus propios aciertos. **Recargar resultados** vuelve a consultar los sorteos en Fase 6. Una participación aparece como **Pendiente** hasta que esté disponible su resultado completo.

En Windows, el operador registró una jugada de Baloto y otra de Baloto Revancha, cerró el visor con código `0` y comprobó que ambas reaparecieron con los mismos aciertos y procedencia.

La prueba aislada cubrió una sola jugada de Markov con dos participaciones, incluido el paso de pendiente a evaluada. La actualización y la desinstalación con reinstalación de la v2 se probaron con el gestor extraído del ejecutable y el registro de Windows simulado. En ese ensayo, las apuestas y los JSON conservaron sus huellas.

| Contenido | Ruta en el perfil de Windows |
| --- | --- |
| Programa y desinstalador | `%LOCALAPPDATA%\Programs\LP11-Operativo` |
| Apuestas | `%LOCALAPPDATA%\LP11-Operativo\apuestas.sqlite3` |
| Evidencias del visor | `%LOCALAPPDATA%\LP11-Operativo\evidencias` |

El instalador y el desinstalador administran la carpeta del programa. Las apuestas y las evidencias se conservan en el perfil. Para copiar el archivo de apuestas, cierra el visor primero.

### Paquete operativo v2

| Archivo | SHA-256 |
| --- | --- |
| `fase11-instalador-operativo-windows-x64-v2.zip` | `60cd233f71ed4e2b470e2f053546c874b6bd1708c7962663d4ee8b21a0288d07` |
| `Instalar-Loteria-Predictor-v2.exe` | `108eb87e4cd21fc37efab091afff5190441740a1a802e59aad2bd3ba9c5ed881` |
| `visor-v2.zip` | `3c1b79f6296c1e122ceac676b145d78b3ce9506a7f7fbbcd3b863d8041e91447` |

El ejecutable se compiló sin firma Authenticode. Para empaquetar el visor desde la raíz del repositorio, compila primero `frontend/dist-escritorio` con `npm run build:escritorio` desde `frontend/`. La carpeta `gestor` se obtiene de la distribución ya verificada del piloto de Windows. Registra el SHA-256 al reconstruir el visor y pásalo al empaquetador. Si se omite `--visor-sha256`, se usa la huella del ZIP original de la v2. El constructor comprueba las huellas del ZIP y del gestor antes de invocar NSIS.

Prueba un instalador reconstruido en un perfil limpio. El gestor identifica una instalación por la versión y la huella de su manifiesto.

```bash
python despliegue/escritorio_windows/construir_operativo.py \
  --salida /ruta/visor-v2.zip
fase11_visor_sha256=$(sha256sum /ruta/visor-v2.zip | cut -d ' ' -f 1)
python despliegue/escritorio_windows/construir_instalador_operativo.py \
  --visor /ruta/visor-v2.zip \
  --visor-sha256 "$fase11_visor_sha256" \
  --bootstrap /ruta/gestor \
  --makensis /ruta/makensis \
  --nsis-dir /ruta/share/nsis \
  --salida /ruta/Instalar-Loteria-Predictor-v2.exe
```

## Referencia sintética

El piloto genera la referencia con las herramientas sintéticas de E10.2 y Fase 9.4, las migraciones de Alembic y los productores y lectores de carteras. Baloto incluye dos modelos para el mismo objetivo pendiente. Las cuatro series incluyen resultados observados. Sincronización lee los registros preparados para el ensayo.

## Ensayo de desarrollo

Requiere Python 3.14 con las dependencias del `requirements.lock`, Node para la compilación y una distribución local de PostgreSQL con `initdb` y `pg_ctl`. El lanzador usa un directorio de salida nuevo con un padre que ya existe. En Windows conviene reservar una ruta corta para las carpetas de artefactos.

Desde `frontend/`, ejecutar `npm run build:escritorio` después de instalar las dependencias fijadas con `npm ci`. La salida es `dist-escritorio/`.

Desde `backend/`, el comando de desarrollo es:

```text
python -m scripts.piloto_escritorio --postgres-bin <carpeta-bin-de-postgresql> --salida <carpeta-nueva>
```

El lanzador inicializa un clúster propio, publica la referencia, comprueba sus huellas y abre el navegador. La base del visor usa un rol lector. El estado sintético aparece en la cabecera. `Ctrl+C` en la consola cierra el servidor del visor y el PostgreSQL del ensayo. `preparacion.log`, `postgres.log` y `referencia/` quedan en la salida indicada. Cada ejecución exige una carpeta nueva.

## Criterios de revisión

- Las cuatro vistas conservan el juego y la identidad de las emisiones. Historial distingue el resultado pendiente, los cero aciertos y la base no disponible. Baloto muestra la superbalota aparte y ColorLoto conserva los pares con multiplicidad.
- La comparación usa los objetivos comunes calculados por Producto 6. Ordena los aciertos de sugerencias cuando ambas líneas tienen ese conteo en toda la muestra común. Una línea que solo aporta el vector de probabilidades puede consultarse con los datos de su muestra. Los aciertos por combinación de las carteras se consultan en Historial.
- Recargar Sincronización consulta el estado persistido de los cuatro juegos. La operación existente usa sus propios recursos y su horario.
- El manifiesto y `esperado-consultas.json` permiten contrastar la publicación. Las pruebas `tests/unit/test_piloto_escritorio.py` cubren sesión, frontera local y rechazo de un archivo alterado.

## Validación en Linux

El recorrido en Chromium, con Python 3.14.6 y PostgreSQL 17.11 aislado, comprobó las cuatro pantallas y los cuatro juegos. Se contrastaron las claves y combinaciones guardadas, los aciertos de sorteos observados, el empate y la falta de muestra común, y la recarga de sincronización. El navegador solo solicitó recursos del origen local.

En el ensayo de preservación coincidieron las huellas de las 13 tablas y los 234 archivos de la referencia. El rol lector rechazó `UPDATE` y `CREATE TABLE` por permisos, incluso al cambiar su valor de transacción de solo lectura para esa prueba. El cierre detuvo el visor y el clúster del ensayo.

## Ensayo portátil de Windows x64

`Abrir piloto.cmd` verifica el ZIP extraído, restaura un clúster sintético en el perfil del usuario y abre el navegador. Una segunda apertura comprueba el identificador de la instancia y la reutiliza. El botón «Cerrar piloto» solicita el cierre desde una sesión del mismo origen.

Con la corrección de cierre, el ensayo portátil de Windows x64 terminó con código `0` y `ensayo_completado`. Se verificaron la segunda apertura, las consultas de los cuatro juegos, la comparación, la sincronización y el historial sintético de Baloto para el sorteo 2192. Las huellas de 13 tablas y 99 archivos coincidieron. El lector recibió `42501` en las pruebas de `UPDATE` y `CREATE`. El visor y PostgreSQL se detuvieron y se retiró la carpeta temporal. `evidencia-f11-p-cf7e430905dc.json` tiene SHA-256 `bd3eb2f80af2f42e455cbdcb1f44647b71156960f2ed83687e36727330a71d38`.

## Instalador por usuario

`Instalar-Loteria-Predictor-Piloto-v1.exe` se compila con NSIS para Windows x64 y se ejecuta desde una cuenta normal. El instalador verifica la carga y la ubica en `%LOCALAPPDATA%\Programs\LP11-Piloto\app`. El acceso «Lotería Predictor (piloto)» del menú Inicio abre el visor. El lanzador usa un clúster sintético temporal bajo `%LOCALAPPDATA%\LP11` y escribe el JSON en `LP11\evidencias`.

La entrega `fase11-instalador-windows-x64-v1.zip` tiene SHA-256 `24827e06d216b35d585b8a4d289eefce0f1674d1cf1dcb5d01c497dfbab2053b`. El ejecutable incluido tiene SHA-256 `4c17e2dd955a1ab680ea593675f7caf67f1f32df4a231dfaeadb390b223e688e`. Se contrastaron las 8.963 huellas del contenido extraído. El recorrido del contenido instalado en Linux usó un registro y un acceso directo simulados para probar la reinstalación, retirada y reversión ante un fallo de integración.

En Windows x64 se verificaron la instalación por usuario, el inicio desde el acceso directo, la reutilización de la instancia y la consulta de los cuatro juegos. La ejecución instalada terminó con código `0` y `ensayo_completado`. Se detuvieron ambos servicios y se retiró la carpeta temporal. Las huellas de 13 tablas y 99 archivos coincidieron. El archivo `evidencia-f11-p-e7c1c17a4df5.json` quedó en `LP11\evidencias` con SHA-256 `8189fc6058203cb6ee7067e45498b7060ea0a4daea74c149cf14d653b7f3d80a`.

Tras la desinstalación nativa, `ProgramaRetirado`, `EntradaRetirada`, `AccesoInicioRetirado` y `EvidenciaConservada` devolvieron `True`. Se verificaron la retirada de la carpeta del programa y de su ruta de retirada, la eliminación de la entrada de Windows y del acceso original de Inicio, y el SHA-256 idéntico del JSON. Con esas comprobaciones se completó la aceptación del instalador del piloto sintético.

Para compilar desde la raíz del repositorio, usa Python 3.14, un compilador NSIS con soporte `amd64-unicode` y el ZIP portátil original.

```bash
python despliegue/escritorio_windows/construir.py \
  --portatil /ruta/fase11-piloto-windows-x64-v1.zip \
  --makensis /ruta/makensis \
  --nsis-dir /ruta/share/nsis \
  --salida /ruta/Instalar-Loteria-Predictor-Piloto-v1.exe
```
