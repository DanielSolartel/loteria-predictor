# Fase 9.1 y 9.2 en Windows — validación nativa completada

**Estado de la 9.2:** validada en Windows 11 nativo por Daniel y aprobada por la auditoría independiente el 26 de octubre de 2026, incluido el ensayo nativo B con el Programador de tareas real. Quedan pendientes la publicación manual, el CI del nuevo PR y la migración controlada de `LP6-01023009031fcabd`; Fase 9 global abierta. [Informe de cierre](fase9_2_validacion_operador_2026-10-26.md).

**Estado de la 9.1:** entrega 9.1 v2 validada en Windows 11 nativo por Daniel y auditada el 25 de octubre de 2026. Python 3.14.6, Node 24.15.0, npm 11.12.1 y Brave instalado (motor 156.0.8078.48), con datos sintéticos. Los seis escenarios se consolidan desde dos corridas; no es una nueva batería completa. Publicación manual y checks del PR pendientes; Fase 9 global abierta. *Actualización posterior:* la 9.1 se integró en PR #100 (merge `9966a4b`). [Detalle de la evidencia](fase9_validacion_operador_2026-10-25.md); [diseño](fase9_frontend.md).


## Entrega 9.2: validación nativa completada

La 9.1 se integró en PR #100 (merge `9966a4bbcb8d81953fb283b07544636f4c11fc95`). La entrega 9.2 contiene dos bloques: las páginas de las métricas anteriores y el horario de consulta de Fase 6. Daniel la validó en Windows 11 con Python 3.14.6 y Windows PowerShell 5.1.26100.9711, con datos sintéticos, y la auditoría independiente la aprobó ([informe de cierre](fase9_2_validacion_operador_2026-10-26.md)):

- **Etapa A sobre v2:**
  - 772 pruebas Python: 394 de Fase 6, 186 de API pública y 192 de pasarela;
  - 456 de Vitest;
  - tipos, TypeScript, compilación y canario correctos;
  - sonda de horario 3/3;
  - Brave: 507 visitas y 26 comprobaciones.
- **Ajustes v3 y v4:** v3 corrige F92-NAT-01 y v4 corrige F92-TEST-01. Se comprobaron de forma dirigida en Windows PowerShell 5.1:
  - 121 casos únicos aprobados, por consolidación de dos corridas (117 retenidos de v3 y 4 revalidados en v4);
  - cardinalidad 24/24;
  - sonda de documento 4/4;
  - lectura semántica 16/16.
- **Ensayo nativo B,** con un testigo sintético y el Programador real:
  - 14 pasos. El intento de activar una versión 1 termina con código 1, como se espera; los otros 13, con código 0;
  - 16 mutaciones, todas sobre el testigo;
  - siguiente inicio igual al plan;
  - limpieza completa.

  El único inicio del testigo fue manual: no se observó un disparo automático futuro. La tarea real no se tocó y sigue habilitada con su programación anterior.

Las baterías de la etapa A conservan su atribución a la corrida sobre v2; no se repitieron con v3 ni v4. El protocolo que se siguió se conserva como referencia y no se repite por rutina:

1. **Worktree nuevo** desacoplado en `9966a4bbcb8d81953fb283b07544636f4c11fc95`. Comprobar el SHA-256 del parche con el manifiesto y después ejecutar `git apply --check`, `git apply`, `git diff --check` y `git status --short`, contrastando con la lista del manifiesto. **No** se aplica en `C:\GitHub\loteria-predictor-fase6`: la tarea `LP6-01023009031fcabd` depende de él y el código nuevo rechaza su `ciclo` sin modo.
2. **Frontend**, desde `frontend\`, como en el paso 3 de la 9.1: `npm ci --no-audit --no-fund --ignore-scripts`, `npm run tipos:comprobar`, `npm run typecheck`, Vitest con JUnit, `npm run build` y `npm run canario`.
3. **API pública y pasarela**, desde `backend\` y con el venv existente, como en el paso 4. Incluye `tests\unit\api_publica\test_api_publica_metricas_anteriores.py`, que compara cada métrica anterior con la receta de la consola en los cuatro juegos.
4. **Recorrido** (opcional, como en el paso 5): el escenario `normal` visita todas las métricas del índice (30/30/22/36), la página 2 de la tabla paginada, el color `ROJO` y los parámetros no válidos.
5. **Brave** con perfil temporal, como en el paso 6. Revisar además:
   - en ColorLoto: colores, conteo por color con su selector y pares número-color, donde cada número debe ir con su color;
   - en Baloto: la coocurrencia de tríos, con la página 2 y los enlaces de paginación por teclado;
   - una métrica con selector de año o ventana, con atrás, adelante y recarga;
   - a 360, 390 y 1280 px.
6. **Fase 6 (horario):** pruebas dirigidas y ensayo nativo con una tarea de ensayo aislada, según la [sección 0 de la migración](fase6_migracion_lp6.md#0-antes-de-migrar-protocolo-nativo-con-una-tarea-de-ensayo-aislada). La migración real de `LP6-01023009031fcabd` es posterior a la auditoría y no forma parte de esta validación.

**v2 (auditoría v1).** La auditoría retuvo la v1 por cinco hallazgos (F92-PS-01, PS-02, HOR-01, REV-01 y EV-01) que la v2 corrige; al desbloquear la lectura del plan apareció un sexto (F92-PS-03). Las baterías de PowerShell de Fase 6 se ejecutaron primero en Linux, con PowerShell 7.6.9 y 7.4.22 portátiles y el Programador simulado. Después se ejecutaron en Windows con Windows PowerShell 5.1, junto con el ensayo nativo del paso 6. Allí aparecieron dos hallazgos:

- **F92-NAT-01:** el Programador omite `StartWhenAvailable` cuando vale su predeterminado `false`. Se corrigió en la v3.
- **F92-TEST-01:** un ayudante de prueba era incompatible con Windows PowerShell 5.1. Se corrigió en la v4.

La selección `tests\seleccion_windows.txt` incluye las pruebas nuevas de horario y `test_fase6_auditoria_v1.py`. Su ejecución completa queda para el CI del nuevo PR. Las evidencias se devolvieron sin claves ni rutas privadas, y sus huellas constan en el informe de cierre.


## Resultado auditado

- Tipos, TypeScript, compilación y canario: correctos.
- Vitest 379, pasarela 186 y API pública 92: sin fallos, errores ni omisiones.
- Sonda original del plazo: dos 504 dentro del margen; intercambio HTTP: 14/14.
- Brave normal: 297/297 visitas, 24/24 criterios y 11 controles directos.
- Cuota, API caída, falta de clave y clave incorrecta: aprobados.
- Vite: 12/12 visitas en 360, 390 y 1280 px, StrictMode y tres controles directos.
- 41 capturas revisadas por el auditor; fuente v2 de 904 archivos e índice conservados.

El primer recorrido Vite falló en la detección del arranque: los colores ANSI
separaban el puerto de su dirección literal. El adaptador externo `color-vite-r1`
pasa `NO_COLOR=1` a los hijos del orquestador, sin cambiar código del producto
ni criterios. La reanudación solo ejecutó Vite y verificó la evidencia previa;
no reinstaló dependencias ni repitió los otros cinco escenarios. Brave se usó
mediante Playwright con un perfil temporal, sin descargar otro navegador.

## Protocolo de referencia

Los bloques siguientes describen la preparación y las alternativas de
verificación. No se deben repetir por rutina tras este cierre. La ejecución
real usó los supervisores auditados y el worktree
`C:\GitHub\loteria-predictor-f91-v2`.

## Reglas de seguridad

- **Dónde:** en un worktree NUEVO, desacoplado en `615f3832296d74a7acea44e5ecdf7dc84a11d70a`, con el parche completo de la 9.1. No se tocan `C:\GitHub\loteria-predictor-fase6` (la tarea `LP6-01023009031fcabd` depende de él), el checkout principal ni otros worktrees.
- **Operación automática:** la tarea, sus configuraciones, modelos, almacenes y el PostgreSQL operativo quedan fuera. Ninguna prueba los usa: la API del recorrido usa datos sintéticos en una carpeta temporal propia. La automatización puede seguir actualizando sus estados mientras tanto; eso no es un cambio de esta validación.
- **Python:** el venv existente (el de la validación de Fase 8). La 9.1 no añade dependencias de Python.
- **Claves:** solo de prueba, en variables de la sesión de PowerShell; nunca en archivos versionados, capturas ni chats. Cerrar la sesión las elimina. No se muestran `.env` ni `DATABASE_URL`.
- **Red:** los tres procesos escuchan solo en `127.0.0.1`. Si el cortafuegos pide permiso, se puede denegar.

## 1. Detectar Node antes de instalar nada

```
node --version
npm --version
where.exe node
```

- Si `node --version` es **22.12 o superior** (22.x o 24.x LTS), usarlo tal cual.
- Si no existe o es anterior, **detenerse y decidir** con Daniel: la recomendación es Node 24 LTS desde el instalador oficial de nodejs.org. Esta guía no instala nada por sí sola.

## 2. Worktree y parche

```
git -C C:\GitHub\loteria-predictor-fase8-v2 worktree add --detach C:\GitHub\loteria-predictor-f91-v2 615f3832296d74a7acea44e5ecdf7dc84a11d70a
cd C:\GitHub\loteria-predictor-f91-v2
Get-FileHash -Algorithm SHA256 <ruta>\fase9-1-completo-v2.patch
git apply --check <ruta>\fase9-1-completo-v2.patch
git apply <ruta>\fase9-1-completo-v2.patch
git diff --check
git status --short
```

Comparar el SHA-256 con el del manifiesto y `git status` con su lista de archivos.

## 3. Frontend: instalación reproducible, tipos, pruebas y compilación

Desde `frontend\`:

```
npm ci --no-audit --no-fund --ignore-scripts
npm run tipos:comprobar
npm run typecheck
npx vitest run --reporter=default --reporter=junit --outputFile.junit=..\f91-vitest-windows.xml
npm run build
npm run canario
```

`npm ci` crea `frontend\node_modules` dentro del worktree (no toca el entorno global). Anotar el código de salida de cada orden.

## 4. Pasarela y API pública

Con el venv activado, desde `backend\`:

```
python -m pytest -p no:cacheprovider -rsw tests\unit\pasarela --junitxml=..\f91-pasarela-windows.xml
python -m pytest -p no:cacheprovider -rsw tests\unit\api_publica --junitxml=..\f91-api-publica-windows.xml
```

- `test_pasarela_arranque.py` arranca procesos Uvicorn reales con el arranque documentado (`uvicorn app.pasarela.aplicacion:app --host 127.0.0.1 --port 8020 --no-access-log --no-proxy-headers`, cambiando solo el puerto).
- La prueba de archivos fuera de `dist\` usa un enlace simbólico de archivo si Windows lo permite; sin ese privilegio comprueba una carpeta mediante una unión (junction). La corrida auditada no tuvo omisiones de pytest.
- `tests\unit\pasarela` ya está en `tests\seleccion_windows.txt`; la selección amplia se reserva al CI del PR.

## 5. Recorrido automático (opcional, descarga Chromium)

Requiere el Chromium de Playwright (`npx playwright install chromium`, unos 150 MB en `%LOCALAPPDATA%\ms-playwright`, fuera del repositorio). **Preguntar antes de descargarlo.** Si se acepta, desde `backend\`:

```
python -m tests.recorrido_fase9 --salida ..\f91-recorrido-windows\normal
python -m tests.recorrido_fase9 --escenario cuota --salida ..\f91-recorrido-windows\cuota --anchos 1280
```

**Vite en Windows:** el orquestador actual no propaga `NO_COLOR` al proceso hijo. Su búsqueda literal puede fallar aunque Vite haya arrancado con códigos ANSI. Para reproducir el recorrido Vite se usa el supervisor externo `color-vite-r1` documentado en el cierre; establecer solo la variable en la consola no basta. La limitación está documentada y no se modificó el orquestador versionado.

Cada orden arranca la API pública real con datos sintéticos (`tests.fase9_api_sintetica:app`; no es PostgreSQL), la pasarela con una clave canario y la SPA, y termina los procesos al acabar. Devuelve 0 solo si no hay fallos ni aparece el canario.

## 6. Brave con un perfil temporal

En tres sesiones de PowerShell, desde `backend\` y con el venv activado:

1. Clave de prueba (sesión 1): `python -m scripts.api_publica_claves generar --id brave-prueba`. Copiar la entrada `brave-prueba:sha256:…` y la clave solo a las variables de las sesiones siguientes.
2. API sintética (sesión 2): `$env:F9_RAIZ = Join-Path $env:TEMP ("f91-brave-" + [guid]::NewGuid())`, `$env:API_PUBLICA_CLAVES = "<entrada>"` y `uvicorn tests.fase9_api_sintetica:app --host 127.0.0.1 --port 8010 --no-access-log --no-proxy-headers`.
3. Pasarela (sesión 3): `$env:PASARELA_CLAVE_API = "<clave>"` y `uvicorn app.pasarela.aplicacion:app --host 127.0.0.1 --port 8020 --no-access-log --no-proxy-headers`.
4. Brave con perfil temporal (comprobar antes la ruta con `Test-Path`):

```
$perfil = Join-Path $env:TEMP ("f91-brave-perfil-" + [guid]::NewGuid())
& "$env:ProgramFiles\BraveSoftware\Brave-Browser\Application\brave.exe" --user-data-dir="$perfil" --no-first-run http://127.0.0.1:8020/
```

Comprobar en los cuatro juegos (ficha, sorteos con filtros y detalle, estadísticas y varias métricas, predicción, simulaciones y la simulación alterada de ColorLoto) y en `/servicio`:
- a 360, 390 y 1280 px (herramientas de desarrollo, modo dispositivo): sin desplazamiento horizontal de la página; las tablas se desplazan dentro de su región;
- teclado: Tab muestra «Saltar al contenido» y el foco es visible;
- Consola sin errores; Red: solo `127.0.0.1:8020`, sin cabecera `X-API-Key` en las peticiones;
- Aplicación → almacenamiento local, de sesión, IndexedDB y cookies vacíos;
- atrás/adelante y recarga conservan los filtros.

Al terminar: cerrar Brave y las tres sesiones (la clave de prueba deja de existir) y borrar `$perfil` y `$env:F9_RAIZ`.

## Evidencia a devolver

Versiones (`node`, `npm`, `python`, Brave), salidas y códigos de salida de los pasos 2–6, los JUnit, los `recorrido.json` y `resultados.json` si se hizo el paso 5, capturas de Brave y `git status --short` final. No incluir claves, `.env` ni rutas privadas fuera del worktree.
