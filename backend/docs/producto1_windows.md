# Producto 1 en Windows: interfaz, entrenamiento y pronóstico

Esta guía explica cómo usar las estadísticas y el pronóstico experimental
sobre **tu base PostgreSQL real**. El entorno Cloud donde se preparó el
cambio no tiene acceso a esa base ni a `baloto.com`, así que la demostración
con el histórico real solo puede correr en tu máquina.

Todas las órdenes se ejecutan en PowerShell desde `backend\`, con el entorno
virtual activado y `DATABASE_URL` (en `backend\.env`) apuntando a tu base.

## 0. Aplicar y validar el parche

```powershell
cd C:\ruta\loteria-predictor
git status                                   # árbol limpio, HEAD en a628c18
(Get-FileHash .\producto1-estadisticas-pronosticos.patch -Algorithm SHA256).Hash
git apply --check .\producto1-estadisticas-pronosticos.patch
git apply .\producto1-estadisticas-pronosticos.patch
git apply --reverse --check .\producto1-estadisticas-pronosticos.patch
cd backend
.venv\Scripts\activate
pip install -r requirements.txt
python -m pip install httpx==0.28.1  # TestClient en las pruebas HTTP
pip check
alembic current                              # 0006; el cambio no añade migraciones
python -m pytest -q tests/unit/ml/test_pronostico_experimental.py tests/unit/test_producto1_estadisticas.py tests/unit/test_producto1_pronosticos.py tests/unit/test_producto1_correcciones.py tests/unit/test_producto1_versiones.py tests/unit/test_producto1_presentacion.py
python -m pytest -q (Get-Content tests\seleccion_windows.txt)
```

## 1. Actualizar el histórico (recomendado)

Abre la aplicación (paso 2) y, en **Importación**, pulsa *Sincronizar ahora*
para cada juego. Las estadísticas y los pronósticos muestran **Histórico
desactualizado** cuando el último sorteo cargado tiene más de 7 días.

## 2. Abrir la interfaz

```powershell
uvicorn app.main:app --reload
```

Abre **http://localhost:8000** (o http://127.0.0.1:8000) en el navegador de
esta misma máquina.

| Página | Qué muestra |
|---|---|
| `/estadisticas` | Los cuatro juegos: último sorteo, cantidad y período, frescura |
| `/estadisticas/baloto/resumen` (también `baloto-revancha`, `miloto`, `colorloto`) | Corte, frecuencias, atrasos y distribuciones; superbalota solo en Baloto y Revancha; colores en ColorLoto |
| `/pronosticos` | Último pronóstico de Baloto y Revancha, su clasificación temporal y el NO-GO de AE-39 |
| `/pronosticos/baloto` | Botón **Entrenar y generar**, ranking, probabilidades, trazabilidad, versiones y rendimiento histórico frente a la referencia uniforme |
| `/api/pronosticos/BALOTO`, `/api/estadisticas/MILOTO/resumen` | Los mismos datos en JSON |

### Por qué el botón solo funciona en tu máquina

La aplicación no tiene usuarios ni contraseñas, y cualquier página web que
abras podría enviar un formulario a `localhost:8000`. Por eso entrenar y
verificar exigen todas estas condiciones:

- la petición sale de esta misma máquina;
- se usa la dirección `localhost`, `127.0.0.1` o `[::1]`;
- el formulario lleva el token de la propia página;
- el navegador no indica un origen ajeno.

En el uso normal no tienes que hacer nada: abre la página y pulsa el botón.
Si reiniciaste el servidor, **recarga la página** antes de pulsar, porque el
token cambia en cada arranque.

Una petición desde otro equipo de la red o desde otra web recibe `403` y no
entrena. Si arrancas uvicorn con `--host 0.0.0.0`, los otros equipos pueden
ver las páginas, pero no entrenar. Para entrenar sin navegador, usa el
comando del paso 3.

Se ejecuta un entrenamiento a la vez: un segundo clic mientras el primero
sigue en curso recibe `429` y no lanza otro.

## 3. Entrenar y generar desde la línea de comandos

```powershell
python -m scripts.pronostico_experimental entrenar --juego todos
python -m scripts.pronostico_experimental entrenar --juego BALOTO --hasta-sorteo 2705
python -m scripts.pronostico_experimental listar --juego BALOTO_REVANCHA
python -m scripts.pronostico_experimental verificar --juego BALOTO --id <clave_de_entrada>
```

- **`entrenar`:**
  - lee el histórico en una transacción `READ ONLY` que termina en `ROLLBACK`: no escribe en PostgreSQL;
  - entrena la regresión logística calibrada de AE-36 (semilla 42);
  - evalúa 10 bloques walk-forward de 20 sorteos frente a la referencia uniforme;
  - guarda el artefacto en `storage\pronosticos\<JUEGO>\<objetivo>-<clave>.json`.
- **Salida de `entrenar`:** indica la clasificación temporal, la frescura del histórico y si el artefacto se reutilizó (`"reutilizado": true`).
- **Clasificación temporal:**
  - **`simulacion_retrospectiva`:** el objetivo ya figura en la base (por ejemplo, `--hasta-sorteo 2705` cuando ya cargaste el 2706). El pronóstico usa solo datos hasta el corte y se compara con el resultado observado.
  - **`pronostico_sobre_el_ultimo_dato_disponible`:** el objetivo es el siguiente al último sorteo cargado. Eso no prueba que el sorteo no se haya celebrado: sincroniza antes si quieres un objetivo real pendiente.
  - **`objetivo_no_cargado_con_sorteos_posteriores`:** el objetivo es un hueco del histórico.
- **Idempotencia:** repetir `entrenar` con el mismo juego, corte, histórico, configuración y versión devuelve el artefacto ya guardado, con su fecha original, sin reentrenar ni crear otro archivo. Si el histórico hasta el corte cambió (por ejemplo, tras corregir un sorteo), se guarda otra versión del mismo objetivo. Las anteriores se conservan, y la pantalla las numera («versión 1 de 2») y permite elegirlas.
- **Orden de las versiones:** sale de una secuencia sellada en cada artefacto, reservada de forma atómica con un archivo `<objetivo>-<secuencia>.secuencia`, y no de la fecha ni del nombre. Copiar la carpeta `storage\pronosticos` a otro sitio conserva el orden.
- **Límites del orden:**
  - no pongas el almacén en una carpeta de red;
  - si se corta la luz entre la reserva y la escritura, queda un hueco en la secuencia, sin efecto en la numeración.
- **`verificar`:** vuelve a entrenar (unos segundos de CPU) con el histórico actual hasta el corte y compara la huella. En la web, `GET /pronosticos/<juego>/verificar` solo muestra el botón; la verificación se lanza por `POST`, con la misma protección que entrenar.
- **Códigos de salida:**
  - `0`: correcto;
  - `2`: uso incorrecto;
  - `3`: falla la conexión con la base;
  - `4`: histórico insuficiente, pronóstico no disponible o artefacto alterado.

## Qué es y qué no es

- **Estado:** el pronóstico es `experimental_no_acreditado`. No es un resultado acreditado ni una recomendación de apuesta.
- **Lo que no cambia:**
  - el NO-GO de AE-39;
  - el estado operativo de AE-41;
  - `AUTORIZA_EVALUACION = False`.
- **Rendimiento:** si el modelo pierde frente a la referencia uniforme (lo que AE-36 a AE-39 observaron), la pantalla lo dice y el flujo sigue funcionando.
- **Holdout:** los sorteos desde `2706` (holdout reservado desde AE-39) se leen como histórico en este uso experimental. Un pronóstico que los usa no constituye evidencia prospectiva.
- **Fecha de generación:** es la del reloj local y no prueba anterioridad.
- **Integridad:** ningún archivo se sobrescribe. Si se altera uno (incluida su fecha), aparece como alterado y no se reutiliza.
