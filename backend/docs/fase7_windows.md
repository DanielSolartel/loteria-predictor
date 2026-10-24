# Fase 7 en Windows — validación local completada

**Validación local completada el 24-10-2026**, ejecutada por Daniel en Windows 11 / PowerShell 5.1 / Python 3.14.6 y auditada por ChatGPT. Resultados y evidencia: [cierre del operador](fase7_validacion_operador_2026-10-24.md). La publicación manual, revisión del PR y sus Actions están pendientes.

Esta guía conserva el procedimiento de referencia para una reproducción deliberada; no requiere repetir ahora las baterías aprobadas ni reaplicar la entrega sobre el worktree ya preparado.

**Entrega vigente: v2 más F7-VIS-01 y cierre documental.** El parche v2 completo se aplica una sola vez sobre `605afe8`; después, el ajuste incremental de presentación y los documentos de cierre. La v1 no se aplica. El worktree actual ya conserva esos cambios; la recreación desde cero corresponde a otra carpeta.

## Reglas de seguridad

- **Worktree nuevo:** se aplica la entrega en un worktree NUEVO desde `605afe8c2bb3b38d0fa3abdb6a5d14ba2002b5a6`. No se tocan `C:\GitHub\loteria-predictor-fase6` (la tarea `LP6-01023009031fcabd` depende de él) ni `C:\GitHub\loteria-predictor-ui93`.
- **Entorno:** no se instala ni actualiza nada en el entorno operativo; la Fase 7 no añade dependencias. Se puede usar el Python existente solo para ejecutar pruebas.
- **Base de datos:** las pruebas unitarias y visuales usan SQLite aislado. El paso 4 se validó en un contenedor PostgreSQL **separado** del operativo; el script se niega a correr si el nombre no contiene `prueba` o si hay sorteos no sintéticos.
- **Datos reales:** simular sobre la base real publica **una fila por identidad nueva en la tabla `simulaciones`** y reutiliza la existente cuando coincide. También registra progreso y usa cerrojos en su directorio propio; no modifica sorteos, modelos ni configuraciones. Es un paso aparte (5), decidido por el operador.
- No se muestran `.env` ni `DATABASE_URL`.

## 1. Aplicar sobre la base exacta

En un worktree nuevo, desacoplado en `605afe8`:

- comprobar el SHA-256 del parche;
- `git apply --check`, `git apply` y `git diff --check`;
- comprobar que `git status` muestra solo los archivos del manifiesto.

## 2. Pruebas de la Fase 7 y selección de Windows

Desde `backend`:

```
python -m pytest -p no:cacheprovider -rsw tests\unit\simulaciones --junitxml=..\f7-simulaciones-windows.xml
```

Sobre la v2 previa al ajuste, el directorio dio `274 passed` en Linux: 125 de Fase 7 (94 de v1 y 31 regresiones v2), más 149 anteriores. F7-VIS-01 añade diez pruebas. La revalidación del ajuste ejecutó 52 pruebas dirigidas en Windows (10 nuevas + 11 de interfaces + 31 regresiones), sin repetir el directorio completo. La selección Windows de v2 conserva 3183 pruebas únicas aprobadas mediante consolidación de dos corridas, no una segunda corrida completa.

Para una reproducción completa adicional, la selección habitual de `tests\seleccion_windows.txt` con el contraste OpenSSL (`scripts\ci_contrastes_openssl.py --modo exigir`). Ya incluye `tests/unit/simulaciones`, y por tanto las pruebas nuevas, sin cambiar la lista.

Atención en Windows:
- `test_fase7_trabajador.py` arranca procesos `spawn` reales (tiempo máximo, muerte del hijo);
- las regresiones de F1 y F2 usan los cerrojos reales (`msvcrt.locking` en Windows): son la evidencia nativa de que la recuperación respeta el cerrojo de la ejecución;
- `test_huella_de_referencia_fijada` compara bytes con la huella obtenida en Linux. Si difiere, **se informa tal cual**: es la evidencia de determinismo entre plataformas, no un fallo que se deba ocultar.

Opcional: las sondas de la auditoría (`sondas_f7.py` del ZIP de auditoría), ejecutadas desde `backend` con `--backend .` y `--salida` en una carpeta temporal. Sobre la v2 se espera `4 / 4` y código 0.

## 3. Medición nativa (datos sintéticos)

**Completada: 20/20 puntos en Windows**, incluidos los cuatro de un millón. Tiempos y picos en MiB, con sus límites, en el [cierre del operador](fase7_validacion_operador_2026-10-24.md).

```
python tests\medicion_fase7.py > ..\f7-medicion-windows.json
```

Mide tiempo y pico de memoria (`PeakWorkingSetSize`) por juego y por iteraciones, cada punto en un proceso nuevo. Con 1.000.000 de iteraciones tarda varios minutos por juego. Se devuelve el JSON completo, para compararlo con la medición Linux de [fase7_simulaciones.md](fase7_simulaciones.md).

## 4. PostgreSQL aislado del operador

**Completado:** Python y procesos en Windows, PostgreSQL 16.14 en un contenedor Linux propio de Docker Desktop, nueve controles aprobados y revisión `0006`. Volumen y puerto locales separados; el contenedor operativo se conservó y el de prueba se eliminó. El intento inicial que buscaba binarios nativos se detuvo antes de ejecutar PostgreSQL: no correspondía al entorno Docker del operador. Las instrucciones generales siguientes requieren siempre una instancia propia de pruebas.

1. Crear una base **separada** cuyo nombre contenga `prueba`, por ejemplo `loteria_f7_pruebas`.
2. Aplicar `alembic upgrade head`: queda en `0006`, porque **no hay migración nueva**.
3. Desde `backend`, con `DATABASE_URL` apuntando **solo** a esa base y `DIRECTORIO_SIMULACIONES` en una carpeta temporal:

```
python tests\postgres_fase7.py > ..\f7-postgres-windows.json
```

Comprueba, entre otras cosas:
- ida y vuelta por JSONB con integridad;
- solo lectura de la lectura;
- 8 publicadores concurrentes que dejan una sola fila;
- espera acotada (`lock_timeout`);
- independencia del advisory de datos de la Fase 6;
- fila alterada que no se sirve;
- comando en procesos nuevos;
- web en segundo plano;
- comprobación por fila con JSONB real: fila de otro juego, `resultado_resumen` y `parametros` que no son objetos (apartado J, nuevo en la v2).

Código 0 significa que todo se cumple; el apartado D es informativo.

## 5. Uso con la base real (decisión del operador, después de 1–4)

`python -m scripts.simulaciones simular --juego MILOTO --iteraciones 10000`, o la página `/simulaciones`, publica una fila en `simulaciones` si la identidad es nueva; la misma identidad reutiliza la existente. El registro de progreso y los cerrojos se guardan en su directorio propio. `verificar --id <uuid> --reproducir` vuelve a simular y compara la huella. No cambia AE-49–51, Producto 5, modelos ni la operación automática.

## 6. Revisión visual

**Completada y auditada:** doce vistas a 360, 390 y 1280 px en Brave (36 capturas, 516/516 criterios automáticos). F7-VIS-01 se corrigió y revalidó con cinco estados a esos mismos anchos (15 capturas, 228/228 criterios), revisados después por el auditor. Los GET conservan los registros y las interrupciones detienen el sondeo. Google Chrome no se acredita por separado. [Evidencias y alcance](fase7_validacion_operador_2026-10-24.md).

## Evidencia conservada o a devolver al reproducir

- salidas y JUnit de los pasos 2 y 3 (y de las sondas, si se ejecutan);
- JSON del paso 4, si se ejecuta;
- versiones de Python, NumPy y PostgreSQL;
- `git status` y `git diff --stat` del worktree nuevo;
- capturas del paso 6.
