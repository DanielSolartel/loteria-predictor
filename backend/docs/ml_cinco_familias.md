# Cinco familias ML: métodos, registro y continuación en Windows

Esta ampliación parte de `90e6ab06b2a188fde9416fb0aac9e7366b7b04a6` y conserva las capacidades de fases 1–5. Incorpora cinco familias reales en Baloto, Baloto Revancha, MiLoto y ColorLoto. Los seis candidatos anteriores por juego permanecen en su orden relativo: el catálogo ampliado contiene once por juego, 44 entradas juego-candidato. Hay diez identificadores nuevos porque los tres juegos numéricos comparten representación, sin compartir datos ni estimadores.

| Familia | Baloto, Revancha y MiLoto | ColorLoto |
|---|---|---|
| XGBoost CPU | `xgboost_binario` | `xgboost_poisson` |
| LightGBM CPU | `lightgbm_binario` | `lightgbm_poisson` |
| Red neuronal regularizada | `red_neuronal_binaria` | `red_neuronal_poisson` |
| Bayes jerárquico | `bayes_jerarquico_binario` | `bayes_jerarquico_pares` |
| Markov de orden uno | `markov_apariciones` | `markov_pares` |

El alcance es de ingeniería. Siguen `experimental_no_acreditado`, AE-39 **NO-GO** y `AUTORIZA_EVALUACION = False`. Ninguna prueba sintética, comparación retrospectiva o ampliación del catálogo acredita ventaja predictiva, dependencia entre sorteos o autorización prospectiva. No se reabre el análisis científico congelado de AE-39 sobre sus bloques ni se altera su protocolo. La evidencia de cada entorno se registra por separado en la guía externa de entrega, con sus JUnit; no se suman baterías solapadas.

## Validación local completada de ML v3.2

La implementación y la validación local de las fases 1–5 están completadas, incluidas Fase 3 Machine Learning, Fase 4 Predicciones y Fase 5 Estadísticas descriptivas. Daniel ejecutó Windows y operó la aplicación; ChatGPT auditó las evidencias y la impresión. Este cierre solo modifica documentación, sin repetir suites, entrenamiento, emisiones, consultas reales ni exportaciones.

**Windows nativo, ejecutado por Daniel:** Windows 11 AMD64, PowerShell 5.1 y Python 3.14.6 en `C:\GitHub\venvs\loteria-ml-cierre\Scripts\python.exe`. La suite completa de `backend/tests`, sin `seleccion_windows.txt`, terminó con **7.015 aprobadas, cero fallos, errores u omisiones** y seis avisos de deprecación registrados. Diagnóstico numérico: código 0; OpenSSL `exigir`: **7/7**; demostración ML sintética: **20/20**; `pip check`: correcto; 29 mediciones archivadas. La focal previa dio **109 aprobadas** y se solapa con la completa: no se suman. Fuentes: `ml-v32-completa-f8b812e2.zip` y `ml-v32-focal-0ce82e7e.zip`, con sus JSON, JUnit y registros. Las 7.015 son pruebas nativas Windows, no una nueva ejecución Cloud/Linux.

**Recorrido con histórico real, operado por Daniel:** once candidatos por juego, **44 entradas juego-candidato**, con muestra común de 60 objetivos en Baloto, Revancha y ColorLoto y 38 en MiLoto; sin selección automática de ganador. Se registraron **20 modelos reales nuevos**, cinco por juego, recargados en proceso nuevo sin reentrenar; repetir la entrada reutilizó la versión. Se verificaron **40 pronósticos de estimadores congelados**, dos cortes por modelo: no son 40 sorteos independientes ni evaluación prospectiva. ChatGPT contrastó los controles y recalculó 130 métricas observadas en su auditoría. Fuentes: los dos ZIP `ml-real-registro-*` y `ml-real-emisiones-c5228f45.zip`.

| Juego | Sorteos disponibles | Último cargado | Corte de ajuste/comparación | Objetivo retrospectivo | Siguiente al último cargado |
|---|---:|---:|---:|---:|---:|
| BALOTO | 642 | 2722 | 2717 | 2718 | 2723 |
| BALOTO_REVANCHA | 642 | 2722 | 2717 | 2718 | 2723 |
| MILOTO | 93 | 624 | 619 | 620 | 625 |
| COLORLOTO | 227 | 227 | 222 | 223 | 228 |

Estos cortes describen la base local del recorrido, sin importación ni sincronización nueva. «Siguiente al último cargado» no certifica que el sorteo aún no haya ocurrido en el mundo real. Las comparaciones retrospectivas y los aciertos no acreditan ventaja futura.

El flujo web cubrió Baloto–XGBoost, Revancha–LightGBM, MiLoto–MLP, ColorLoto–Bayes y Baloto–Markov, con configuración elegida explícitamente por Daniel. Se cotejaron **cinco carteras y explicaciones**, 258 probabilidades frente a los pronósticos registrados y páginas terminales; repetir XGBoost reutilizó exactamente cartera y explicación. Tras reiniciar, los cinco casos conservaron respuestas API idénticas, páginas terminadas sin sondeo y sin nuevas escrituras. Los inventarios conservaron artefactos anteriores y siete orígenes; tras las operaciones explícitas quedaron 442 archivos. Esa cifra identifica una instantánea, no una exigencia fija sobre almacenes. La consulta histórica XGBoost no pierde validez por seleccionar después Markov para Baloto. Fuentes: `ml-web-antes-0d695d18.zip` y `ml-web-despues-9dd614de.zip`.

**Impresión nativa y auditoría:** Daniel exportó con Brave doce páginas web —informe, ficha y predicción de cada juego—, en Carta vertical, Carta horizontal y A4 vertical: **36 PDF y 600 páginas**, con medio `print` comprobado antes de cada archivo, perfil temporal propio y únicamente GET. ChatGPT auditó huellas y contenido de todos los PDF, incluidas 9.474 apariciones de filas y sus multiplicidades, y los renderizó todos. Los controles no detectaron páginas vacías, cajas de texto fuera del papel ni solapes por encima del umbral del comprobador; la inspección visual de hojas de contacto y páginas ampliadas fue representativa, sin defectos observados. **No hubo lectura manual ampliada individual de las 600 páginas.** El ZIP válido es `ml-impresion-v2-2a99ebfc.zip`, SHA-256 `329465285b0be263fa22102f3efb4433f047a2e121510d2cf0b039798fd7af3b`; los inventarios antes/después conservaron 442 archivos y siete orígenes. El primer exportador externo de ChatGPT mantuvo por error el medio `screen`: ese lote no acredita impresión y se corrigió en la v2 sin cambiar el producto. Las capturas de 390 px pertenecen al lote anterior; no se presentaron como capturas nuevas de la v2. Véase también la [matriz nativa validada](fase3_windows.md#matriz-nativa-de-impresión-y-ampliación-ml-validada).

**Antecedentes separados:** Linux v3 conservó completa 7.003 y selección Windows ejecutada en Linux 2.758 aprobadas; v3.1, 18 dirigidas; v3.2, 12 dirigidas. Son sus ejecuciones originales con datos sintéticos y JUnit propios, no nuevas ejecuciones de este cierre; los grupos se solapan. La focal Windows v3.1 de 97 aprobadas y tres fallidas queda como antecedente corregido por v3.2, no como estado vigente. Los checks del PR #94 corresponden a la base y no validan las nuevas familias.

**Pendientes separados:** aplicación/verificación de este cierre documental en Windows PowerShell 5.1 (`ml-guia-cierre-documental-windows.md` de la entrega), revisión y publicación manual por Daniel con Actions del futuro PR, y acreditación prospectiva por su cauce propio. Se mantienen `experimental_no_acreditado`, AE-39 **NO-GO** y `AUTORIZA_EVALUACION = False`. No queda pendiente repetir la suite nativa, el recorrido ni la impresión ya completados.

*Adenda del 23 de octubre de 2026:* la publicación manual y Actions de esta entrega se completaron en PR #95 (merge `2ac4d110b7d721e544f5588e9754230eef28184d`, Actions `39387775447`); la acreditación prospectiva sigue por su cauce propio.

## Datos, cortes y significado de la salida

### Continuación v3: evidencia Windows y comparación reproducible (antecedentes)

La v3 corrige la infraestructura de validación sobre la v2 exacta. Las mediciones de publicación se escriben bajo la raíz temporal privada corta del supervisor (`m <aleatorio>/e`). Cada nombre físico es `m-<SHA-256 completo>.json`; el objeto conserva todos sus campos y añade `_medicion.nombre` y `_medicion.prueba` con el nombre lógico y el nodo de pytest, incluida su parametrización. Antes de limpiar, incluso si pytest falla, el supervisor conserva los bytes en `mediciones-fase4.zip`, con inventario, tamaños y huellas en `resultado-validacion.json`. Si archivar falla, conserva el temporal y registra su ruta. No cambia TEMP/TMP ni exige habilitar rutas largas. La comprobación portable reproduce el presupuesto de la extracción larga de Downloads; no acredita Windows nativo.

La comparación exacta entre el trabajador y el evaluador directo requiere la misma instantánea, recetas, protocolo, bibliotecas y recursos numéricos. La referencia de prueba llama al evaluador directamente en un proceso independiente con el límite histórico `HILOS=2`; observa que el entorno y los pools del padre permanezcan intactos durante el cálculo. No usa el ejecutor del producto para producir esa referencia. La aserción sigue comparando los informes completos con igualdad exacta, incluidos los once candidatos de ColorLoto. No añade tolerancias, redondeos ni exclusiones. Las recetas, versiones, formatos y artefactos existentes permanecen compatibles: esta revisión no modifica código de producción ni sus límites de hilos.

La matriz diagnóstica ajusta la red real a uno y dos hilos, repite el ajuste a dos y realiza inferencia con ambos límites sobre cada estimador fijo. Guarda estados, pesos, salidas y pools efectivos. La focal nativa v3.1 de Daniel comprobó `red_neuronal_poisson` de ColorLoto con 90 sorteos sintéticos, corte 80 y perfil reducido: preparación idéntica, pesos distintos entre ajuste a uno/dos hilos, repetición a dos exactamente igual y salidas crudas y probabilidades idénticas al cambiar hilos sobre cada estimador fijo. En ese ensayo la diferencia apareció en el ajuste con recursos distintos, sin diferencia de inferencia del estimador fijo. Su contexto fue Windows 11, Python 3.14.6 AMD64, NumPy 2.5.3, SciPy 1.18.1 y scikit-learn 1.9.1; no demuestra determinismo universal entre plataformas, compilaciones o datos. Linux no había reproducido esa diferencia. El primer diagnóstico de ChatGPT consultó metadatos de `xgboost` en lugar de la distribución instalada `xgboost-cpu`; es una incidencia del diagnóstico, distinta del fallo original de igualdad. El diagnóstico incluido consulta `xgboost-cpu`.

La v3.1 conserva la matriz calculada **antes** de comunicar una repetición no exacta: `matriz-numerica.json` incluye los tres ajustes, las seis inferencias y `repeticion_2_hilos_exacta = false`; el diagnóstico termina con código distinto de cero y el supervisor detiene la batería sin borrar esa evidencia. La igualdad exacta sigue siendo obligatoria. Las regresiones con estimadores simulados comprueban este camino de error y el correcto; no constituyen una prueba de ML real ni de Windows. Las verificaciones dirigidas de v3.1 y las baterías completas anteriores de v3 se registran por separado. La focal nativa v3.1 terminó con 97 aprobadas, tres fallidas, cero errores y cero omisiones. Pasaron publicación (22), aislamiento (4), registro (23), recorridos ML (30) y recursos (7); las tres fallidas pertenecen a los manifiestos sintéticos de las pruebas del supervisor. Las 28 mediciones archivadas conservaron tamaños, SHA-256 y correspondencia con su inventario.

La v3.2 corrige únicamente la construcción de esos manifiestos sintéticos: las huellas declaradas como texto se calculan sobre contenido UTF-8 canónico con CRLF normalizado a LF en memoria; las escrituras usan codificación explícita. Se cubren LF y CRLF, la conservación de los bytes originales y el rechazo de contenido realmente alterado. No se debilita el preparador, cambia el tipo a binario ni normaliza físicamente el worktree. El incremental se aplica directamente sobre v3.1 exacta, ya presente en Windows, o reconoce v3.2 ya aplicada; no requiere revertir entregas anteriores. Producción, recetas, formatos, comparación exacta y límites del servidor permanecen intactos.

Los resultados y JUnit de cada entrega se conservan externamente. Al entregar v3.2 se exigió una focal nativa explícita antes de la completa: Daniel completó ambas después (109 y 7.015 aprobadas, grupos solapados), además del recorrido y la impresión con su evidencia propia descrita arriba. Las verificaciones dirigidas Linux v3.2, la focal Windows v3.1 y las baterías Linux anteriores mantienen sus versiones; no sustituyen ni se suman a Windows. Actions del futuro PR y la aplicación/verificación del nuevo cierre documental siguen pendientes, con acreditación prospectiva separada.

Cada juego se ajusta con su histórico independiente. Las filas corresponden a candidato y objetivo. En juegos numéricos la respuesta es aparición binaria del número; en ColorLoto es el conteo de un par número-color entre seis balotas, con multiplicidad. Superbalota conserva su referencia separada; estas cinco familias no aprenden un componente nuevo de superbalota. MiLoto no tiene ese componente.

Las métricas de las familias nuevas de ColorLoto ordenan el multiconjunto antes de acumular sus términos: conserva multiplicidades y evita que su orden de serialización cambie el último decimal. Las recetas históricas mantienen su cálculo anterior.

La evaluación reutiliza los bloques y objetivos comunes del laboratorio, incluida la uniforme: Log Loss y Brier principales, aciertos y métricas secundarias con su denominador. Un modelo insuficiente o que no converge comunica su estado; no bloquea los demás. Comparar no elige ganador, no activa una versión ni cambia la configuración de Carteras.

XGBoost, LightGBM y MLP reciben las ocho variables causales del laboratorio: identidad del candidato/par y siete valores numéricos previos al objetivo. Su preparación se ajusta exclusivamente con BASE: identidad mediante `OneHotEncoder(handle_unknown="ignore")`; valores numéricos mediante `StandardScaler`. Categorías, medias y escalas se guardan y quedan congeladas. Las filas de calibración y evaluación no ajustan esa preparación.

En los tres clasificadores nuevos, BASE precede a CALIBRACIÓN, un bloque cronológico posterior reservado: una regresión logística sigmoide sobre el logit de la probabilidad cruda se ajusta solo con ese bloque. La evaluación posterior no interviene. No hay selección aleatoria, parada temprana ni búsqueda de hiperparámetros sobre la evaluación. ColorLoto usa intensidad Poisson sin esa calibración.

Bayes y Markov utilizan sus estadísticas suficientes, identificadores y, para Markov, el conteo conocido del sorteo anterior; no se presentan como modelos que aprenden de las ocho variables. Ambos usan todo el prefijo de ajuste y no añaden una sigmoide. En ColorLoto el soporte de ajuste es la paleta conocida **al corte de ajuste**: las filas de sus objetivos anteriores representan también ceros de colores cuya primera aparición ocurre después de esa fila, pero antes o en ese corte. Esto conserva las seis balotas de cada objetivo dentro de un soporte fijo para estimar posterior/transiciones. No utiliza colores posteriores al corte de ajuste. Es distinto del soporte causal por fila usado por las otras familias y no debe describirse como si fueran la misma codificación. Cada evaluación se ajusta solo con su prefijo anterior al bloque evaluado.

Las salidas crudas se transforman con el contrato versionado común: marginales numéricas ajustadas por un desplazamiento común de logits para sumar cinco, o intensidades de pares normalizadas por balota para sumar uno. En ColorLoto la multiplicidad esperada es `6 × p`; las seis balotas de Carteras siguen una multinomial *plug-in* a partir del vector emitido. Eso no convierte la distribución conjunta integrada bayesiana en multinomial ni expresa una probabilidad de premio mayor. Estas transformaciones son posteriores a la predictiva del estimador, no una actualización de su posterior.

## XGBoost y LightGBM reales en CPU

Se usan `xgboost-cpu==3.4.1` y `lightgbm==4.7.0`. La distribución oficial `xgboost-cpu` proporciona el módulo `xgboost` sin añadir el entorno CUDA/NCCL. No se sustituye LightGBM por HistGradientBoosting. Las dependencias anteriores que condicionan modelos guardados no se actualizan por esta entrega.

| Parámetro | XGBoost | LightGBM |
|---|---|---|
| Objetivo numérico / ColorLoto | `binary:logistic` / `count:poisson` | `binary` / `poisson` |
| Semilla y ejecución | 42; `nthread=1`; `hist`, CPU | 42; `num_threads=1`; `deterministic`, `force_col_wise` |
| Regularización | profundidad 3; L2 5; `min_child_weight=20` | profundidad 3; 7 hojas; L2 5; `min_data_in_leaf=20` |
| Aprendizaje | tasa 0.08; 60 rondas | tasa 0.08; 60 rondas |
| Perfil reducido | 12 rondas del mismo algoritmo | 12 rondas del mismo algoritmo |
| Persistencia nativa | JSON de XGBoost | texto de LightGBM |

Se conservan preparación, calibración cuando aplica, parámetros y modelo nativo. Antes de cargarlo se comprueban el manifiesto, la procedencia y la integridad del contenido. Los motores nativos se importan en el proceso que los necesita, después de fijar sus límites de recursos; el servidor no cambia su entorno de hilos.

Las importancias son **ganancia total de particiones**: XGBoost `total_gain`; LightGBM `importance_type="gain"`. Se agregan las columnas de la preparación a la variable de origen. Son valores no negativos en las unidades de ganancia del motor, sin normalizarlos a suma uno. No son coeficientes lineales, contribuciones locales por candidato ni efectos causales; tampoco son comparables automáticamente entre familias.

## Red neuronal entrenable y regularizada

`MLPClassifier` con pérdida logarítmica en juegos numéricos y `MLPRegressor(loss="poisson")` en ColorLoto, de scikit-learn 1.9.1. Una capa oculta `tanh` de 12 neuronas; regularización `alpha=10`; `solver="lbfgs"`; semilla 42; `early_stopping=False`; tolerancia `1e-4`; máximo 600 iteraciones y 20 000 evaluaciones de función. El perfil reducido usa seis neuronas y máximo 300 iteraciones con el mismo método.

La preparación y calibración siguen los cortes anteriores. Los avisos de no convergencia producen un estado explícito. Se persisten matrices, sesgos, arquitectura y preparación en JSON; la carga e inferencia usan operaciones NumPy, salida sigmoide o exponencial según el objetivo, sin reconstruir un ajuste. No se publican pesos neuronales como importancias globales comparables: la explicación comunica el motivo de su ausencia.

## Bayes jerárquico genuino

### Apariciones numéricas

Para universo de `N` números, cada candidato `j` tiene sus apariciones Bernoulli anteriores al corte:

```text
mu ~ Beta(5, N - 5)
theta_j | mu ~ Beta(20 mu, 20 (1 - mu))
y_jt | theta_j ~ Bernoulli(theta_j)
```

La media poblacional `mu` es aleatoria y común: sus observaciones aportan información a la posterior de los candidatos. No se sustituye por una estimación puntual. Se integra la posterior marginal de `mu` mediante cuadratura determinista Gauss–Legendre de 32, 64, 128, 256 y hasta 512 nodos, con cálculo estable en logaritmos. La posterior condicional de cada candidato es beta; integrar sobre `mu` conserva una mezcla posterior, de la que se guardan cuentas, primeros y segundos momentos y diagnóstico.

La inferencia es **aproximada por cuadratura**, sin muestreo. Se exige refinamiento menor que `1e-9` en medias y segundos momentos, incluido `mu`; agotar el presupuesto produce `no_converge`. Ese criterio comprueba estabilidad numérica entre resoluciones, no es una garantía universal de error ni de convergencia científica. Un caso pequeño se contrasta con integración adaptativa independiente. La predictiva cruda es `E[theta_j | D]`; para un candidato sin observaciones, `E[mu | D]`. El ajuste común de cardinalidad se hace después y no se denomina posterior.

### Pares número-color de ColorLoto

Jerarquía conjugada: probabilidades de color `q ~ Dirichlet(1 por color del ajuste, más un depósito OTROS)` y, para cada color, probabilidades de los siete números `r_c ~ Dirichlet(1, …, 1)`. Cada balota elige color y después número. Las posteriores son exactas: `q | D ~ Dirichlet(1 + cuentas_color)` y `r_c | D ~ Dirichlet(1 + cuentas_par_c)`. Se conservan las seis apariciones, incluso pares repetidos; la intensidad predictiva cruda es `6 E[q_c | D] E[r_nc | D]`.

La predictiva conjunta de seis balotas integra las probabilidades aleatorias de color y de número. Se verifica mediante fórmulas beta/Dirichlet y ejemplos con multiplicidad; difiere de la multinomial *plug-in* que Carteras utiliza tras recibir el vector. Inferencia conjugada exacta no significa que las probabilidades aprendidas estén acreditadas para próximos sorteos.

El depósito OTROS permanece congelado. Ante colores no vistos al ajustar, su masa se reparte uniformemente entre los pares de esos colores de la paleta de entrada, **por objetivo**, sin ampliar parámetros posteriores ni aprender esos colores. Si un objetivo no incluye todos los colores del ajuste, la normalización de contrato condiciona al soporte de entrada y se distingue de la predictiva cruda. Un lote de objetivos no comparte accidentalmente la masa de colores nuevos entre sus paletas.

## Markov explícito y estimable

Una cadena independiente por candidato, de **orden uno**: estado conocido en el sorteo anterior, columna 5 de `X`, → estado en el objetivo `y`. Estados 0/1 para números y 0…6 para el conteo de cada par ColorLoto. No se construye un estado combinatorio para el sorteo entero ni se devuelve simplemente el último sorteo.

Se guardan cuentas de transiciones dirigidas. Cada fila tiene prior Dirichlet de fuerza 10 centrado en Bernoulli `5/N` para números o Binomial `n=6, p=1/K` para ColorLoto, donde `K` es la cantidad de pares del soporte de ajuste. La estimación es la media posterior de cada fila; su esperanza produce probabilidad de aparición o intensidad cruda. Un estado sin transiciones observadas emplea su prior; un candidato o estado desconocido utiliza el prior fijo, sin recalcularlo a partir de una paleta nueva.

Se verifican cuentas a mano, dirección temporal anterior → objetivo y casos no observados. Al inferir cambia el estado conocido de entrada; **transiciones, conteos y prior no se vuelven a estimar**. Siguen la transformación común del juego y la limitación científica de ausencia de evidencia de dependencia entre sorteos.

## Registro, recarga y consumidores

Los diez identificadores nuevos usan registro `ml-cinco-familias-1`, formato `json-nativo-ml-cinco-familias/1`, envoltura JSON canónica `ml-cinco-familias/1` y extensión `.mljson`. Guarda preparación y orden, calibración, parámetros y modelo nativo o matrices/posterior/transiciones, con validación de dimensión y finitud. En el registro sellado se mantienen identidad, receta, entorno, datos, corte y procedencia; una entrada idéntica reutiliza su versión.

La carga común `modelos_registrados.cargar_estimador(artefacto, contenido)` comprueba manifiesto y procedencia, esquema, receta, contratos, entorno, tamaño y SHA-256 **antes** de cargar formatos nativos. Un manifiesto incompleto, ajeno o alterado se rechaza con un estado explícito. No se amplía genéricamente el deserializador restringido para admitir módulos nuevos. La huella detecta alteraciones e inconsistencias; no autentica frente a quien pueda sustituir todo el almacén. Se cargan únicamente artefactos propios con sus rutas verificadas.

La v2 conecta la validación del estado interno con la receta antes del deserializador: compara los parámetros efectivos, soporte de categorías, dimensiones de entrada/salida y arquitectura MLP; contrasta objetivo, salidas escalares, agrupación y presupuesto de árboles nativos, y los parámetros que conserva el texto LightGBM. El JSON XGBoost no conserva todos los hiperparámetros de entrenamiento: se contrasta su declaración persistida con la receta, sin afirmar que sus árboles demuestren por sí solos la regularización usada. Bayes/Markov contrastan universo, soporte y paleta, hiperparámetros, dimensiones y cuentas del periodo; también se comprueban los diagnósticos, los momentos mediante identidades algebraicas, los priors Dirichlet y las transiciones. La recarga no ejecuta cuadratura, entrenamiento ni actualización posterior. Los formatos, recetas e identidades históricos permanecen; un estado internamente incompatible se rechaza aunque se hayan recalculado todas sus huellas.

| Formato | Compatibilidad que se exige antes de cargar |
|---|---|
| Histórico `.pkl`, registro `fase3-1` | Conserva misma versión de scikit-learn y mismas versiones menores de Python, NumPy y SciPy; lector restringido y recetas históricas |
| Nuevas familias `.mljson` | Versiones exactas de Python, NumPy, SciPy y scikit-learn; además XGBoost o LightGBM cuando corresponde; inventario y contratos completos |

El sistema operativo se registra e influye en la identidad, pero no impone por sí solo un bloqueo de carga. Esto no promete determinismo entre plataformas, versiones o compilaciones: la recarga se contrasta con el control guardado en el entorno compatible. Las versiones históricas no se reescriben ni se migran automáticamente. El formato nativo es adecuado para conservar el modelo, pero esta aplicación mantiene una política conservadora de versiones exactas para las familias nuevas.

Web, API y CLI comparten los casos de uso del laboratorio y sus consumidores: comparación → registro → control tras recarga en otro proceso sin `fit` → elección explícita de versión en Carteras → predicción explicada → Resultados y Fiabilidad. Una cantidad alternativa de combinaciones no cambia la configuración vigente. El seguimiento de un estimador congelado se distingue de la evaluación de una receta que se reajusta por bloque.

La **reproducción de explicación guardada** verifica la huella del vector fuente, recalcula rankings y variables y los contrasta con lo guardado. Su integridad incluye importancias y referencia SHA-256 del estimador; el cotejo directo del archivo de estimador se hace al emitir la explicación. Un GET no abre/carga el estimador, no ejecuta nueva inferencia ni recalcula importancias. Esto es distinto de verificar un pronóstico registrado, acción que sí recarga el modelo congelado y repite su inferencia de control.

La publicación mantiene el escritor atómico y su mecanismo Windows; el manifiesto se publica al final. `.mljson` añade tres caracteres respecto de `.pkl`; los nuevos identificadores y sus rutas finales/temporales se incluyen en las comprobaciones. No se promocionan ni eliminan temporales históricos automáticamente. Las pruebas de concurrencia y presupuestos de ruta en Linux no sustituyen su ejecución nativa Windows.

## Recursos y entorno aislado

El entorno de Cloud comprobado para las nuevas dependencias es Python 3.14.8, NumPy 2.5.4, SciPy 1.18.1 y scikit-learn 1.9.1; XGBoost CPU 3.4.1 y LightGBM 4.7.0. Se verifican fuentes oficiales y wheels CPU para Linux y Windows AMD64; disponer de un wheel no acredita una ejecución en Windows. La guía externa identifica los archivos y arquitecturas comprobados y los resultados nuevos reales. No se transfieren ejecuciones ML de sesiones interrumpidas sin sus artefactos de evidencia recuperados.

Los trabajadores `spawn` fijan sus límites de bibliotecas nativas y de `threadpoolctl` únicamente dentro del proceso dedicado, y los restauran al terminar; no mutan el entorno de hilos del servidor. XGBoost y LightGBM usan un hilo nativo. Se conservan los plazos del producto: laboratorio 1800 s, Carteras 300 s por juego, además de semillas y presupuestos acotados de cada familia. Progreso e interrupción siguen disponibles. Medir tiempos reales y diagnosticar bloqueos precede a cualquier cambio de presupuesto.

La instalación Windows original creó un entorno Python 3.14 **nuevo**, sin actualizar el anterior; ya está validado y este cierre lo conserva. La siguiente receta documenta aquella preparación, no una orden para reinstalar: Las restricciones para preservar sus versiones se obtienen de ese entorno **Windows**, con `python -m pip list --format=freeze`, no de un `pip freeze` Linux. Guardar el inventario fuera del repositorio, crear el entorno nuevo y resolver `requirements.txt` con esas restricciones; las dos nuevas bibliotecas están fijadas. Si la resolución revela un conflicto, detenerse y conservar el entorno anterior, sin quitar restricciones para ocultarlo. `pip check`, intérprete, arquitectura y versiones quedan en la evidencia nueva.

## Continuación nativa completada y cierre antes de Fase 6

Worktree ya validado: `C:\GitHub\loteria-predictor-ml-cierre`, rama `feature/ml-cinco-familias-cierre`. Se conserva junto con los worktrees y entornos anteriores. El aplicador de este cierre comprueba código y manifiestos; no instala dependencias, no lee `.env` o almacenes reales, no consulta la aplicación ni entrena, genera o ejecuta baterías. Su aplicación/verificación nativa en PowerShell 5.1 es el único paso técnico local nuevo pendiente.

La **suite completa nativa Windows sin filtrar por `seleccion_windows.txt`** ya terminó correctamente, con JUnit, cero omisiones, OpenSSL `exigir`, demostración sintética y `pip check`, según la evidencia v3.2 descrita arriba. El runner `backend/tests/ejecutar_ml_windows.py` aisló la ejecución, supervisó sus plazos y guardó resultados y mediciones antes de limpiar sus propios temporales. La selección Windows ejecutada en Linux y el check Windows selección previo de Actions siguen siendo baterías distintas. Este cierre no ordena repetirlas ni relaja guardas, omisiones o comparaciones exactas.

El permiso de creación de enlaces simbólicos se identifica para las pruebas que lo necesitan: habilitar Developer Mode o usar el permiso adecuado para la batería. **No elevar Uvicorn ni la aplicación real.** Se conserva la carpeta temporal normal del sistema; no se recorta `TEMP` para ocultar fallos de rutas. Si se incorpora una prueba que requiera PostgreSQL, usar una base exclusiva de pruebas, nunca la configuración ni los datos reales de Daniel.

En la v2, el supervisor crea `TEMP\m <8 caracteres>`, con espejo en `c` y pytest directamente bajo esa raíz privada; pytest conserva `pytest-of-<usuario>\pytest-0`. Las fixtures de las cinco familias usan `m <índice><contador>`, la concurrencia conserva `ml ruta` y la demostración usa `TEMP\d <8 caracteres>\<índice>`. Solo se acortan carpetas propias: se conservan aislamiento y espacios, sin cambiar `TEMP`/`TMP`, sin `--basetemp` y sin modificar Windows. El presupuesto portable contempla el TEMP representativo `C:\Users\danie\AppData\Local\Temp`, espejo, cuatro juegos, cinco familias, pronósticos registrados, carteras, reservas y temporales; no garantiza cualquier raíz o nombre de usuario arbitrariamente largo ni sustituye la batería nativa. La ruta concurrente auditada pasa de 271 a 208 caracteres. Los valores por juego quedan en los JUnit nuevos.

Daniel completó el recorrido con histórico real y eligió explícitamente las versiones nuevas, conservando los artefactos previos y las decisiones de configuración registradas. La [matriz de impresión de Fase 3](fase3_windows.md#matriz-nativa-de-impresión-y-ampliación-ml-validada) está validada en Carta vertical/horizontal y A4 con evidencia propia. No se entrena, emite ni repite impresión al aplicar este cierre.

Las fases futuras solo se planifican: **6 Actualización y operación automática → 7 Simulaciones → 8 API pública → 9 React → 10 Despliegue → 11 Aplicación personal**. Los detalles de objetivo, dependencias, entregables y aceptación de fases 6 y 11 están en [ROADMAP](../../ROADMAP.md). Las cinco familias y sus comprobaciones nativas están completadas localmente. Fase 6 queda como siguiente entrega planificada tras aplicar/verificar el cierre documental y revisar/publicar la ampliación; no se inicia aquí. La acreditación prospectiva mantiene su cauce y bloqueo propios.

## Fuentes primarias y correspondencia

- XGBoost [instalación 3.4.1](https://github.com/dmlc/xgboost/blob/v3.4.1/doc/install.rst), [parámetros](https://github.com/dmlc/xgboost/blob/v3.4.1/doc/parameter.rst) y [persistencia nativa](https://github.com/dmlc/xgboost/blob/v3.4.1/doc/tutorials/saving_model.rst): distribución CPU, objetivos, recursos y JSON de modelo frente a instantáneas de memoria.
- LightGBM [instalación 4.7.0](https://github.com/microsoft/LightGBM/blob/v4.7.0/docs/Installation-Guide.rst), [parámetros](https://github.com/microsoft/LightGBM/blob/v4.7.0/docs/Parameters.rst) y [Booster](https://github.com/microsoft/LightGBM/blob/v4.7.0/python-package/lightgbm/basic.py): CPU, semillas/hilos, formato texto y ganancia.
- scikit-learn [MLP 1.9.1](https://github.com/scikit-learn/scikit-learn/blob/1.9.1/doc/modules/neural_networks_supervised.rst), [implementación](https://github.com/scikit-learn/scikit-learn/blob/1.9.1/sklearn/neural_network/_multilayer_perceptron.py) y [persistencia](https://github.com/scikit-learn/scikit-learn/blob/1.9.1/doc/model_persistence.rst): escalado, regularización, pérdidas y límites de compatibilidad.
- Stan User’s Guide, [jerarquías](https://github.com/stan-dev/docs/blob/master/src/stan-users-guide/regression.qmd) y [conjugación](https://github.com/stan-dev/docs/blob/master/src/stan-users-guide/efficiency-tuning.qmd): estructura Beta/Bernoulli y Dirichlet/multinomial. La aplicación no usa Stan ni MCMC; implementa cuadratura o conjugación según lo descrito.
- SciPy [cuadratura Gauss–Legendre](https://github.com/scipy/scipy/blob/v1.18.1/scipy/special/_orthogonal.py), [cálculo logarítmico estable](https://github.com/scipy/scipy/blob/v1.18.1/scipy/special/_logsumexp.py) y [Dirichlet/multinomial](https://github.com/scipy/scipy/blob/v1.18.1/scipy/stats/_multivariate.py): normalizaciones y momentos que se contrastan con cálculos independientes. El prior Dirichlet por fila de Markov aplica esa conjugación a las cuentas de transición dirigidas, sin afirmar que los sorteos reales sigan una cadena dependiente.

Las fuentes de instalación y persistencia se contrastan con las versiones y wheels concretos en la evidencia de dependencias de la entrega. Los contratos previos al código y pruebas pequeñas vinculan formulación, implementación y resultados; la documentación no sustituye esos contrastes.
