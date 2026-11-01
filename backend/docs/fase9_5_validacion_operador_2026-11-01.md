# Fase 9.5 — validación del operador y auditoría (1 de noviembre de 2026)

**Estado:** validación nativa y auditoría completadas; publicación manual, integración y CI pendientes. La Fase 9 global sigue abierta. Se mantienen `experimental_no_acreditado`, AE-39 **NO-GO** y `AUTORIZA_EVALUACION = False`.

Este informe consolida la evidencia de 9.5 por alcance y procedencia:
- Las baterías y recorridos se solapan: no se suman como casos únicos.
- Las omisiones (no evaluables) no son aprobaciones.
- **El recorrido normal completo no se volvió a ejecutar sobre la fuente final.** Su parte válida, retenida de la v1, se consolida con las revalidaciones dirigidas de los dos hallazgos y con la última tanda de cinco escenarios.

Diseño, formatos y matriz: [guía de exportación e impresión](fase9_5_exportacion_impresion.md). Protocolo y resumen nativo: [Windows](fase9_windows.md#entrega-95-validación-nativa-completada).

## Fuente

| Árbol | Contenido | Archivos |
|---|---|---:|
| `f9457d74310aa199f7a569ec0362c7a9acc4653e` | Base integrada, merge del PR #104 (`9fde216c5667bd7a1ddb8553a73857f5cfb07e61`) | 1028 |
| `10a1b0b403d8678698f1c848dc8ee4b8cfc83f80` | Entrega 9.5 v1 | 1041 |
| `cd4aa123763221654c194b480ff8e175bc7c8d06` | v1 + F95-NAT-01 (solo el ensayo) | 1043 |
| `d68cdc1983e3015f4da4871285647615bc9b9e5b` | + F95-PDF-01 (presentación impresa); fuente validada | 1043 |

Este cierre documental modifica solo documentos de 9.5 y añade este informe. No cambia código, pruebas, configuración, dependencias, workflows ni OpenAPI.

## Qué ofrece 9.5

- **Exportación:** JSON versionado o CSV de una tabla elegida, a partir de la consulta ya cargada y decodificada. Una lista paginada exporta solo la página visible.
- **Precisión y ausencias:** los números conservan su precisión y las ausencias son explícitas.
- **Protección del CSV:** las cadenas se protegen frente a fórmulas.
- **Contexto:** se conservan contexto, filtros, alcance e identidad.
- **Impresión:** por acción explícita, con `window.print()` y estilos locales. Abre solo los desplegables ya cargados y restaura su estado.
- **Pares número/color de ColorLoto:** se imprimen con el nombre del color como texto y, en tablas estrechas, pueden ocupar dos líneas dentro de su celda.
- **Coste:** descargar o imprimir añade **cero solicitudes y cero fichas**, y no consulta fiabilidad.
- **Límites:** las descargas son representaciones de consulta, no acreditan ventaja predictiva. La revisión de navegación, móvil y accesibilidad no es una certificación general de accesibilidad.

## Evidencia nativa (Windows 11, Brave)

**Entorno:** Python 3.14.6, Node 24.15.0 y npm 11.12.1. Brave instalado, con motor 156.0.8078.74 y ejecutable de SHA-256 `040bddd110b2f39a5855431e88935f137d909fd6a2a55479c52364a475362f8a`. Datos sintéticos.

| Evidencia | Bytes | SHA-256 | Atribución |
|---|---:|---|---|
| `f95-frontend-d185c6c8.zip` | 30.902 | `269d9000ea87b2d592e00adb72e830e825063f6b260e6c45cac4ec0a07dcf27e` | Frontend Windows v1 |
| `f95-brave-normal-79341ef2.zip` | 5.514.524 | `bdb39901ed2572152b7b9623f9aadbb662c63209ae4585709109eda064c9eca5` | Recorrido normal Windows v1, con 24 fallos históricos de impresión |
| `f95-revalidacion-v2-355b891a.zip` | 3.430.782 | `77c0bb5488195069410e4ccec3a14682546d8eff62f60a7b3d38105d7e21cb25` | Revalidación focal de F95-NAT-01 |
| `f95-pdf-nativo-ae6efbcf.zip` | 4.074.356 | `5475ed61df84983a1b47b7b24abf430fc0ac8943f7cc0fe23f1a86dc34af17f8` | Revalidación de F95-PDF-01 |
| `f95-cinco-escenarios-679d6d35.zip` | 434.888 | `6a2f80dc691e5bd8eec7189cad04a8db03ffa5a470fd4db60343795534ee73cf` | Última tanda de cinco escenarios |
| `prueba-manual-consulta.pdf` | 577.052 | `b27c1388812c8651831a98ee56754b849be8d8aa6e6d301379b35dec47436218` | PDF manual retenido |

Las evidencias se conservan fuera del repositorio con estos nombres y huellas. Sus rutas locales son privadas del operador y no se copian aquí.

### 1. Frontend Windows v1

- **Resultado:** 864 Vitest aprobadas, sin fallos, errores ni omisiones. Tipos, TypeScript, build y canario correctos.
- **Alcance:** se ejecutaron sobre la v1. No se repitieron tras los ajustes posteriores: los dos ajustes no cambian TS/TSX y F95-PDF-01 solo añade CSS de impresión. Se retienen con esa atribución.

### 2. Recorrido normal Windows v1 (retenido; no totalmente en verde)

- **Volumen:** 177 visitas, 193 descargas (60 JSON y 133 CSV), 12 PDF y 12 capturas.
- **Comprobaciones:** 68 de 92 aprobadas. Las **24 fallidas** lo fueron únicamente por `desplegables_restaurados=false`, en Resumen, Predicción, Fiabilidad, Ficha de modelo, Resultados y Ficha de simulación de los cuatro juegos.
- **Origen del fallo:** el ensayo antiguo comparaba los desplegables 50 ms después de `window.print()`. En Brave sin ventana no llega `afterprint`.
- **Sin cambio:** peticiones y fichas iguales antes y después de cada acción.
- **Atribución:** el fallo y su procedencia se conservan. Esta ejecución no se presenta como un normal aprobado.

### 3. F95-NAT-01: corrección exclusiva del ensayo (aprobada por Codex)

- **Causa:** sin diálogo, `window.print()` emite un `beforeprint` confiable y retorna sin `afterprint`. Además, la pestaña no inicia otro ciclo de impresión.
- **Cambio en el ensayo:**
  - observa los eventos con plazo acotado;
  - acredita la restauración con `page.pdf`, que usa eventos reales;
  - conserva las comprobaciones de cero red y fichas;
  - registra como **no evaluable** (`ok: null`, `skipped` en JUnit) solo esos dos mecanismos.
  - `Marco.tsx` no cambió.
- **Regresiones:** 30 unitarias y 20 de navegador adicionales, aprobadas. El pase de navegador repite las 30 unitarias; no son 80 casos únicos.
- **Recorrido focal nativo:**
  - 56 visitas y 227 criterios: 167 aprobados, 0 fallidos y 60 no evaluables (57 `afterprint_no_emitido` y 3 `impresion_pendiente_en_pestana`);
  - 75 `page.pdf`: 42 restauraciones desde estados cerrados y 33 superficies sin desplegables;
  - 27 controles negativos y 60 comprobaciones independientes sin red;
  - JUnit: 283 casos, 0 fallos/errores y 60 omitidos.
- **Conservación:** se aplicaron exactamente seis rutas (1041 → 1043). Las otras 1037 conservaron sus bytes y el índice no cambió.

### 4. Prueba manual con ventana (retenida)

- **Eventos aportados por el operador:** los desplegables se restauran al cancelar el diálogo y al guardar un PDF.
- **Destino Microsoft Print to PDF:** cambiar a él y cancelar no acredita haber guardado con ese destino.
- **PDF manual:** `prueba-manual-consulta.pdf`, de 11 páginas. Codex revisó visualmente las páginas 1, 3, 10 y 11.
- **Alcance:** es anterior al CSS final. No se afirma una nueva ejecución manual sobre `d68cdc19`.

### 5. F95-PDF-01: presentación impresa (aprobada por Codex)

- **Hallazgo:** en la tabla «Variables de los candidatos extremos» de ColorLoto, el par número/color invadía «Emitida» en Carta vertical y A4. Las filas afectadas eran 3 y 7; Carta horizontal servía de control.
- **Corrección:** solo en `@media print`. Dentro de una celda, el par puede pasar a otra línea y, si es lo único en la celda, no suma su margen exterior. Se añadieron regresiones del HTML impreso y del PDF.
- **Ejecución en Brave/Windows:**
  - build correcto y supervisor con código 0;
  - 36/36 criterios y 12/12 PDF, 63 páginas con controles de contenido y geometría.
- **Medición independiente:** 20 filas de la tabla de ColorLoto por formato, sin solapamiento ni contacto entre colores y cifras. Separación mínima de 12,55 pt (Carta vertical), 16,03 pt (A4) y 33,46 pt (Carta horizontal).
- **Revisión visual:**
  - seis páginas de ColorLoto y tres muestras de BALOTO;
  - para los seis PDF de Revancha y MiLoto se retuvo la revisión anterior, al comprobar que solo cambiaron sus fechas internas;
  - no es una inspección visual exhaustiva de las 63 páginas.
- **Conservación:** el ajuste cambió cuatro rutas y conservó las otras 1039, sin cambios en el índice.

### 6. Última tanda nativa de cinco escenarios (aprobada por Codex)

| Escenario | Alcance efectivo | Visitas | Criterios | Aprobados | No evaluables | Descargas | Casos JUnit |
|---|---|---:|---:|---:|---:|---:|---:|
| `vacio` | Cuatro superficies de BALOTO a 360/390/1280 px | 12 | 39 | 27 | 12 | 30 | 51 |
| `alterado` | Listado y ficha de modelos y carteras de BALOTO a 390 px | 4 | 8 | 6 | 2 | 4 | 12 |
| `incompatible` | Listado y ficha de modelos de BALOTO a 390 px | 2 | 8 | 6 | 2 | 4 | 10 |
| `cuota` | Predicción de BALOTO a 390 px | 0 | 9 | 6 | 3 | 12 | 9 |
| `api_caida` | Error de modelos de BALOTO a los tres anchos | 3 | 0 | 0 | 0 | 0 | 3 |
| **Total de esta tanda** | | **21** | **64** | **45** | **19** | **50** | **85** |

- **Totales:**
  - criterios: 64, de ellos 45 aprobados y 19 no evaluables;
  - descargas: 18 JSON y 32 CSV;
  - JUnit: 66 aprobados (21 visitas + 45 criterios), 19 omitidos y 0 fallos/errores;
  - no evaluables: 17 `afterprint_no_emitido`, 1 `ciclo_pendiente_en_documento` y 1 `impresion_pendiente_en_pestana`.
- **Cobertura:** no todos los escenarios cubren los cuatro juegos y las tres anchuras.
- **Cuota:**
  - el contador de visitas es 0, pero ejecuta 9 criterios y 12 descargas;
  - solicitudes a la API: 3 antes, 3 sin acción, 3 al acabar la espera y 4 tras el reintento manual;
  - son solicitudes, no coste ponderado en fichas.
- **Integridad:** sin canarios, sin cambios en almacenes sintéticos ni en la SPA y sin almacenes ajenos creados. Todas las ejecuciones terminaron con código 0 y dentro de plazo.
- **Conservación:** los inventarios antes y después coinciden (1043 rutas, huellas, HEAD e índice), y también los cuatro archivos compilados de la SPA con la referencia aprobada del PDF.

## Evidencia Linux Cloud (separada de Windows)

- **v1 (30-10-2026):**
  - 864 Vitest y recorrido `recorrido-normal-05` (177 visitas, 92 comprobaciones, 193 descargas, 12 PDF), sin fallos, con el Chromium del contenedor;
  - el ensayo antiguo aprobaba allí la restauración, pero no leía los eventos de impresión, así que ese verde no atribuía causa.
- **F95-NAT-01 (Chromium 153):**
  - completo sin ventana: 60 clics no evaluables y 0 fallos;
  - chrome-headless-shell: 60 clics evaluados y aprobados;
  - una SPA mutante sin restauración fue rechazada.
- **F95-PDF-01 (Chromium 153, `--solo-pdf`):**
  - las regresiones fallaban antes del arreglo y pasaban después: 36/36 criterios de navegador y 0 colisiones con Poppler;
  - **limitación declarada:** el extractor portátil del supervisor no encontraba algunos textos que Poppler sí encontraba, de modo que el supervisor daba `ok: false` antes y después. No se convierte en éxito.
  - en Brave/Windows, el supervisor completo y el extractor sí pasaron, con código 0.

## Conservación y límites

- **Conservación acreditada:** corresponde a la copia de revisión del operador. Sus 1043 archivos, HEAD, índice y los cuatro archivos de la SPA compilada coincidieron con la referencia aprobada.
- **Supervisores:** no consultaron el Programador ni SQL operativo.
- **Lo que no se afirma:** que este cierre haya inspeccionado la tarea operativa de Fase 6, sus horarios, SQL o cambios históricos ajenos a esa copia.
- **CI de otras fases:** los resultados de fases anteriores no acreditan 9.5. La integración de 9.4 y su bloqueo de facturación (cinco jobs sin ejecutar) conservan su significado y no son pruebas aprobadas.
- **Lo que no se hizo:**
  - nuevas funciones;
  - baterías del producto en este cierre;
  - commit, push, PR, merge, Actions ni despliegue;
  - cambios en Fase 6.

## Pendiente

- **Publicación:** revisión de Codex y aplicación del cierre documental en Windows; después, publicación manual por Daniel.
- **Integración y CI de 9.5:** pendientes.
- **Fase 9 global:** sigue abierta. No se inicia Fase 10/11.
