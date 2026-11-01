/** 9.5: navegador real, API/pasarela/SPA reales; sin interceptar HTTP. */
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { chromium } from "playwright";
import { casoJunit, controlNegativo, deshacerMixto, instrumentarImpresion, observarClic, observarPdf, PLAZO_IMPRESION_MS, prepararMixto } from "./impresion.mjs";

const opciones = { escenario: "normal", anchos: "360,390,1280" };
for (let i = 2; i < process.argv.length; i += 2) opciones[process.argv[i].replace(/^--/, "")] = process.argv[i + 1];
if (!opciones.base || !opciones.salida) throw new Error("Faltan --base y --salida");
// --solo-impresion revalida sólo los criterios de impresión (clic real, page.pdf y cero red/fichas)
// sin descargas ni la matriz PDF; no sustituye el recorrido completo.
const SOLO_IMPRESION = opciones["solo-impresion"] === "true";
const PLAZO = Number(opciones["plazo-impresion"] ?? PLAZO_IMPRESION_MS);
if (SOLO_IMPRESION && (opciones.escenario !== "normal" || opciones["solo-pdf"] === "true")) throw new Error("--solo-impresion requiere el escenario normal y excluye --solo-pdf");
if (!Number.isFinite(PLAZO) || PLAZO < 100 || PLAZO > 60000) throw new Error("--plazo-impresion fuera de 100..60000 ms");
const BASE = opciones.base.replace(/\/$/, ""), ORIGEN = new URL(BASE).origin;
const ANCHOS = opciones.anchos.split(",").map(Number), JUEGOS = ["BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO"];
for (const d of ["descargas", "pdf", "capturas"]) await mkdir(join(opciones.salida, d), { recursive: true });
const navegador = await chromium.launch(opciones.navegador ? { executablePath: opciones.navegador } : {});
const resultados = {
  escenario: opciones.escenario, alcance: opciones["solo-pdf"] === "true" ? "solo_pdf" : SOLO_IMPRESION ? "solo_impresion" : "completo", anchos: ANCHOS,
  plazo_impresion_ms: PLAZO,
  navegador: { nombre: "Chromium", version: navegador.version(), plataforma: process.platform, playwright: "1.56.1",
    ejecutable_externo: Boolean(opciones.navegador), identidad_sha256: opciones.navegador ? createHash("sha256").update(await readFile(opciones.navegador)).digest("hex") : null },
  transporte: "HTTP real API→pasarela→SPA compilada; sin route/fulfill/fetch interceptado",
  visitas: [], comprobaciones: [], descargas: [], pdf: [], fallos: [], no_evaluables: [],
};
let secuencia = 0, cuerpo = 0;
const seguro = (s) => String(s).replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 100);
const huella = (b) => createHash("sha256").update(b).digest("hex");
function verificar(nombre, ok, detalle = {}) {
  const fila = { nombre, ok: Boolean(ok), estado: ok ? "aprobada" : "fallida", ...detalle }; resultados.comprobaciones.push(fila);
  if (!ok) resultados.fallos.push({ donde: nombre, motivo: JSON.stringify(detalle).slice(0, 1200) });
}
// Impresión (F95-NAT-01): aprobada, fallida o no_evaluable. Una no evaluable no es aprobada (ok: null),
// no es un fallo genérico aceptado: lleva el mecanismo observado y queda en resultados.no_evaluables.
function registrar(nombre, estado, detalle = {}) {
  if (!["aprobada", "fallida", "no_evaluable"].includes(estado)) throw new Error(`Estado de comprobación desconocido ${estado}`);
  const fila = { ...detalle, nombre, estado, ok: estado === "aprobada" ? true : estado === "fallida" ? false : null };
  resultados.comprobaciones.push(fila);
  if (estado === "fallida") resultados.fallos.push({ donde: nombre, motivo: JSON.stringify({ resultado: detalle.resultado, ruta: detalle.ruta, inicial: detalle.inicial, final: detalle.final }).slice(0, 1200) });
  if (estado === "no_evaluable") resultados.no_evaluables.push({ donde: nombre, resultado: detalle.resultado, motivo: detalle.motivo });
}

// Parser independiente RFC4180; no importa el serializador de producto.
function leerCsv(texto) {
  if (texto.charCodeAt(0) === 0xfeff) texto = texto.slice(1);
  const filas = []; let fila = [], celda = "", comillas = false;
  for (let i = 0; i < texto.length; i++) {
    const c = texto[i];
    if (comillas) {
      if (c === '"' && texto[i + 1] === '"') { celda += '"'; i++; }
      else if (c === '"') comillas = false;
      else celda += c;
    } else if (c === '"' && !celda.length) comillas = true;
    else if (c === ",") { fila.push(celda); celda = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && texto[i + 1] === "\n") i++;
      fila.push(celda); filas.push(fila); fila = []; celda = "";
    } else celda += c;
  }
  if (comillas) throw new Error("CSV con comillas sin cerrar");
  if (fila.length || celda.length) { fila.push(celda); filas.push(fila); }
  if (!filas.length || filas.some((f) => f.length !== filas[0].length)) throw new Error("CSV no rectangular");
  const [cabecera, ...datos] = filas;
  if (new Set(cabecera).size !== cabecera.length) throw new Error("Columnas CSV repetidas");
  return { cabecera, filas: datos.map((f) => Object.fromEntries(cabecera.map((n, i) => [n, f[i]]))) };
}
function hojas(v, lista = []) {
  if (v === null || ["string", "number", "boolean"].includes(typeof v)) lista.push(v);
  else if (Array.isArray(v)) for (const x of v) hojas(x, lista);
  else if (v && typeof v === "object") for (const x of Object.values(v)) hojas(x, lista);
  return lista;
}
// Esperados independientes: se cotejan los campos públicos exportados contra
// las respuestas HTTP reales, sin importar decodificadores o serializadores.
function cotejarProyeccion(actual, fuente, ruta = "datos") {
  if (actual === null && fuente === undefined) return; // propiedad pública opcional ausente
  if (actual === null || typeof actual !== "object") {
    if (actual === fuente || typeof actual === "string" && typeof fuente === "number" && actual === String(fuente)) return;
    throw new Error(`Proyección distinta de la respuesta HTTP en ${ruta}`);
  }
  if (Array.isArray(actual)) {
    if (!Array.isArray(fuente) || actual.length !== fuente.length) throw new Error(`Lista distinta de la respuesta HTTP en ${ruta}`);
    actual.forEach((v, i) => cotejarProyeccion(v, fuente[i], `${ruta}[${i}]`));
    return;
  }
  if (!fuente || typeof fuente !== "object" || Array.isArray(fuente)) throw new Error(`Objeto no acreditado en ${ruta}`);
  for (const [k, v] of Object.entries(actual)) {
    // La proyección pública de combinaciones agrupa sus balotas en resultado;
    // el contrato HTTP las entrega en la propia combinación. Se acredita esa
    // transformación conocida sin permitir otras propiedades inventadas.
    const resultadoAgrupado = k === "resultado" && /^datos\.prediccion\.combinaciones\[\d+\]$/.test(ruta)
      && !Object.hasOwn(fuente, "resultado") && (Object.hasOwn(fuente, "numeros") || Object.hasOwn(fuente, "pares"));
    const tipoResumen = k === "tipo" && ruta === "datos.resumen" && !Object.hasOwn(fuente, "tipo");
    const literalExacto = k === "exacto" && /^datos\.contenido\.estadisticas\[\d+\]\.(observado|referencia_analitica|percentil_observado|p_valor_empirico|p_valor_ajustado_bonferroni)$/.test(ruta);
    const contenidoCompleto = k === "completo" && ruta === "datos.contenido" && !Object.hasOwn(fuente, "completo");
    const esperado = resultadoAgrupado || contenidoCompleto ? fuente : tipoResumen ?
      fuente.reglas?.tipo === "colorloto" ? "colorloto" : "numeros" : literalExacto ? fuente.exacto ?? fuente.exacta : fuente[k];
    cotejarProyeccion(v, esperado, `${ruta}.${k}`);
  }
}
function fuenteDeExportacion(j, respuestas) {
  const ultima = (ruta) => {
    const candidatas = respuestas.filter((r) => r.estado === 200 && r.ruta?.split("?")[0] === ruta);
    if (!candidatas.length) throw new Error(`No se capturó la fuente HTTP ${ruta}`);
    return candidatas.at(-1).datos;
  };
  const p = `/api/v1/juegos/${j.juego}`;
  switch (j.recurso) {
    case "resumen": return { ficha: ultima(p), resumen: ultima(p + "/estadisticas/resumen") };
    case "estadisticas": return { indice: ultima(p + "/estadisticas"), panel: ultima(p + "/estadisticas/panel") };
    case "prediccion": {
      const { fiabilidad, estado_fiabilidad, ...datos } = j.datos;
      cotejarProyeccion(datos, ultima(p + "/predicciones"));
      if (fiabilidad !== null) {
        if (estado_fiabilidad !== "acreditada") throw new Error("Fiabilidad exportada sin acreditación de contexto");
        cotejarProyeccion(fiabilidad, ultima(p + "/fiabilidad"), "fiabilidad");
      }
      return null;
    }
    case "simulacion": return ultima("/api/v1" + new URL(j.ruta_spa, BASE).pathname);
    default: {
      let ruta = new URL(j.ruta_spa, BASE).pathname.replace(/^\/juegos/, "/api/v1/juegos");
      ruta = ruta.replace(/\/modelos(?=\/|$)/, "/modelos-guardados").replace(/\/carteras(?=\/|$)/, "/carteras-guardadas");
      return ultima(ruta);
    }
  }
}
function coste(ruta) {
  const p = new URL(ruta, BASE).pathname;
  if (p.includes("/estadisticas/") || p.endsWith("/resultados")) return 5;
  if (p.endsWith("/predicciones") || p.endsWith("/fiabilidad")) return 3;
  if (/\/(sorteos|simulaciones|modelos-guardados|carteras-guardadas)(\/|$)/.test(p)) return /\/(modelos-guardados|carteras-guardadas)(\/|$)/.test(p) || /\/(sorteos|simulaciones)$/.test(p) ? 2 : 1;
  return 1;
}
async function abrir(ancho) {
  const contexto = await navegador.newContext({ viewport: { width: ancho, height: 900 }, acceptDownloads: true, serviceWorkers: "block" });
  const pagina = await contexto.newPage();
  const registro = { peticiones: [], respuestas: [], errores: [], consola: [] };
  pagina.on("request", (r) => registro.peticiones.push({ url: r.url(), metodo: r.method(), cabeceras: r.allHeaders() }));
  pagina.on("response", (r) => registro.respuestas.push((async () => {
    const u = new URL(r.url()), cabeceras = await r.allHeaders();
    const b = await r.body().catch(() => Buffer.alloc(0));
    if (opciones.cuerpos) await writeFile(join(opciones.cuerpos, `${++cuerpo}.bin`), Buffer.concat([Buffer.from(JSON.stringify({ ruta: u.pathname + u.search, estado: r.status(), cabeceras }) + "\n"), b]));
    let datos = null; if (u.pathname.startsWith("/api/v1/")) try { datos = JSON.parse(b.toString("utf8")); } catch { /* Se espera rechazo del cliente. */ }
    return { ruta: u.pathname + u.search, estado: r.status(), cabeceras, datos };
  })().catch((e) => ({ error_captura: String(e) }))));
  pagina.on("pageerror", (e) => registro.errores.push(String(e)));
  pagina.on("console", (m) => { if (["error", "warning"].includes(m.type())) registro.consola.push({ tipo: m.type(), texto: m.text() }); });
  await pagina.addInitScript(instrumentarImpresion);
  return { contexto, pagina, registro };
}
async function listo(pagina) {
  await pagina.waitForSelector("main h1", { timeout: 30000 });
  await pagina.waitForFunction(() => !document.querySelector("main [role=status]"), null, { timeout: 30000 });
  await pagina.waitForLoadState("networkidle");
}
function api(registro) { return registro.peticiones.filter((p) => new URL(p.url).pathname.startsWith("/api/v1/")); }
async function geometria(pagina) {
  return pagina.evaluate(async () => ({
    ventana: innerWidth, documento: document.documentElement.scrollWidth, cuerpo: document.body.scrollWidth,
    h1: document.querySelectorAll("main h1").length,
    tablas: [...document.querySelectorAll(".tabla-desplazable")].map((t) => { const r = t.getBoundingClientRect(); return { izquierda: r.left, derecha: r.right, teclado: t.tabIndex === 0 && t.getAttribute("role") === "region" && Boolean(t.getAttribute("aria-label")) }; }),
    acciones: [...document.querySelectorAll('[data-testid="exportacion"] button, [data-testid="exportacion"] select')].map((t) => { const r = t.getBoundingClientRect(); return { izquierda: r.left, derecha: r.right, nombre: t.getAttribute("aria-label") || t.textContent?.trim() }; }),
    almacenamiento: { local: localStorage.length, sesion: sessionStorage.length, cookies: document.cookie.length, indexedDB: (await indexedDB.databases()).length, caches: "caches" in self ? (await caches.keys()).length : 0 },
    colores: [...document.querySelectorAll("main .color-swatch")].map((e) => ({ texto: e.parentElement?.textContent?.trim(), oculta: e.getAttribute("aria-hidden") === "true" })),
  }));
}
async function descargar(pagina, barra, tipo, detalle) {
  const boton = barra.getByRole("button", { name: tipo === "json" ? "Exportar JSON" : "Exportar CSV", exact: true });
  const evento = pagina.waitForEvent("download"); await boton.click(); const descarga = await evento;
  const nombre = descarga.suggestedFilename();
  if (!/^[a-zA-Z0-9_.-]{1,160}$/.test(nombre) || !nombre.endsWith(`.${tipo}`) || /[/\\]/.test(nombre)) throw new Error(`Nombre inseguro ${nombre}`);
  const archivo = `descargas/${String(++secuencia).padStart(4, "0")}-${nombre}`;
  await descarga.saveAs(join(opciones.salida, archivo));
  if (await descarga.failure()) throw new Error("Descarga real fallida");
  const b = await readFile(join(opciones.salida, archivo));
  resultados.descargas.push({ ...detalle, archivo, nombre_sugerido: nombre, bytes: b.length, sha256: huella(b), formato: tipo });
  // Ritmo de acciones explícitas del ensayo, sin cambiar permisos, CSP o la
  // protección del navegador frente a ráfagas de múltiples descargas.
  await pagina.waitForTimeout(150);
  return { b, nombre, archivo };
}
async function exportaciones(pagina, registro, juego, ruta) {
  const barras = pagina.getByTestId("exportacion");
  const cantidad = await barras.count();
  if (!cantidad) throw new Error("No hay consulta cargada exportable");
  const fichasDe = () => api(registro).reduce((n, p) => n + coste(p.url), 0), porBarra = [];
  const respuestas = await Promise.all(registro.respuestas), apiDatos = respuestas.filter((x) => x.estado === 200 && x.ruta?.startsWith("/api/v1/")).map((x) => x.datos);
  const numeros = new Set(hojas(apiDatos).filter((v) => typeof v === "number"));
  const textos = new Set(hojas(apiDatos).filter((v) => typeof v === "string"));
  for (let i = 0; i < cantidad; i++) {
    const barra = barras.nth(i), recurso = await barra.getAttribute("data-recurso");
    const antes = registro.peticiones.length, fichas = fichasDe();
    porBarra.push({ barra, recurso, antes, fichas });
    if (SOLO_IMPRESION) continue;
    const d = await descargar(pagina, barra, "json", { juego, ruta, recurso });
    const j = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(d.b));
    if (j.esquema !== "loteria-predictor/consulta-publica/1" || j.juego !== juego || j.recurso !== recurso || j.estado_de_uso !== "experimental_no_acreditado" || j.autoriza_evaluacion !== false || !j.exportado_en || !j.datos || !j.ruta_spa?.startsWith("/") || j.ruta_spa.startsWith("//") || /https?:|clave=|token=|secreto=/.test(j.ruta_spa)) throw new Error("Sobre JSON incoherente o privado");
    const rutaVista = new URL(ruta, BASE);
    if (!j.ruta_spa.startsWith(rutaVista.pathname)) throw new Error("Identidad SPA exportada no corresponde a la pantalla");
    const fuente = fuenteDeExportacion(j, respuestas);
    if (fuente !== null) cotejarProyeccion(j.datos, fuente);
    const exportados = hojas(j.datos);
    for (const n of exportados.filter((v) => typeof v === "number" && !Number.isInteger(v))) if (!numeros.has(n)) throw new Error(`Precisión alterada o número no procedente de API: ${n}`);
    for (const texto of textos) if (/^[\s\x00-\x1f]*[=+@-]/.test(texto) && JSON.stringify(j.datos).includes(texto.slice(0, 3)) && !exportados.includes(texto)) throw new Error("JSON no conserva texto histórico original");
    // La etiqueta separada del select conserva un nombre accesible exacto,
    // independiente de sus opciones y de la tabla seleccionada.
    const selector = barra.getByRole("combobox", { name: "Tabla CSV", exact: true });
    const tablas = await selector.count() ? await selector.locator("option").evaluateAll((xs) => xs.map((x) => ({ id: x.value, titulo: x.textContent }))) : [{ id: null, titulo: (await barra.locator("span").filter({ hasText: /^CSV:/ }).innerText()).replace(/^CSV:\s*/, "") }];
    for (const tabla of tablas) {
      if (tabla.id !== null) await selector.selectOption(tabla.id);
      const csv = await descargar(pagina, barra, "csv", { juego, ruta, recurso, tabla: tabla.id });
      if (!csv.b.subarray(0, 3).equals(Buffer.from([0xef, 0xbb, 0xbf]))) throw new Error("CSV sin BOM UTF-8 documentado");
      const leido = leerCsv(new TextDecoder("utf-8", { fatal: true }).decode(csv.b));
      const contexto = leido.filas.filter((f) => f.tipo_fila === "contexto"), datos = leido.filas.filter((f) => f.tipo_fila === "dato");
      if (contexto.length !== 1 || contexto[0].juego !== juego || contexto[0].ruta_spa !== j.ruta_spa || Number(contexto[0].filas_cargadas) !== datos.length || datos.length + 1 !== leido.filas.length) throw new Error("Contexto/filas CSV incoherentes");
      if (contexto[0].tabla !== tabla.titulo) throw new Error("CSV corresponde a otra tabla");
      const columnas = leido.cabecera.filter((n) => n.startsWith("dato_") && !n.endsWith("_tipo"));
      if (!columnas.length) throw new Error("CSV sin columnas tabulares útiles");
      for (const f of datos) for (const c of columnas) {
        const v = f[c], tipo = f[c + "_tipo"];
        if (tipo === "null") { if (v !== "null") throw new Error("Ausente CSV sustituido por un valor"); }
        else if (tipo === "numero") {
          if (!Number.isFinite(Number(v))) throw new Error("Número CSV inválido");
          if (!Number.isInteger(Number(v)) && !numeros.has(Number(v))) throw new Error(`CSV redondeó precisión: ${v}`);
        } else if (tipo === "booleano") { if (!["true", "false"].includes(v)) throw new Error("Booleano CSV coaccionado"); }
        else if (tipo === "texto") {
          if (!v.startsWith("'") && (/^[\s\"=+@-]/.test(v) || /[\x00-\x1f\x7f]/.test(v))) throw new Error("Texto CSV permite fórmula o control sin protección");
          for (const original of textos) if (v === original && /^[\s\x00-\x1f]*[=+@-]/.test(original)) throw new Error("Fórmula no protegida");
        } else throw new Error(`Tipo de celda desconocido ${tipo}`);
      }
      resultados.descargas.at(-1).columnas = leido.cabecera;
      resultados.descargas.at(-1).filas_datos = datos.length;
    }
  }
  // Restauración acreditada con page.pdf (eventos reales) antes de cualquier clic, que en headless
  // puede dejar el ciclo de impresión abierto. Después, el clic real en cada «Imprimir».
  await imprimirDocumento(pagina, juego, porBarra[0].recurso, ruta);
  for (const { barra, recurso, antes, fichas } of porBarra) {
    const clic = await observarClic(pagina, barra.getByRole("button", { name: "Imprimir", exact: true }), PLAZO);
    registrar(`imprimir-clic-real-${juego}-${recurso}`, clic.estado, { ruta, mecanismo: "clic real en Imprimir", ...clic });
    // Comprobación independiente: cero solicitudes y cero fichas, con cualquier resultado del clic.
    verificar(`${SOLO_IMPRESION ? "imprimir" : "descargar-imprimir"}-sin-red-${juego}-${recurso}`, registro.peticiones.length === antes && fichasDe() === fichas,
      { ruta, peticiones_antes: antes, peticiones_despues: registro.peticiones.length, fichas_antes: fichas, fichas_despues: fichasDe(),
        desplegables_restaurados: clic.restauracion ?? null, restauracion_clic: clic.resultado });
  }
}
async function imprimirDocumento(pagina, juego, recurso, ruta) {
  const id = `${juego}-${recurso}`;
  const inicial = await observarPdf(pagina, PLAZO);
  const fila = { ruta, mecanismo: "page.pdf (eventos reales del navegador)", ...inicial };
  if (inicial.resultado === "ciclo_pendiente_en_documento") { registrar(`imprimir-pdf-restaura-${id}-inicial`, inicial.estado, fila); return; }
  const m = await prepararMixto(pagina, PLAZO);
  fila.mixto = m.aplicable ? "evaluado aparte" : `no aplicable: ${m.inicial.length} desplegables, ${m.inicial.filter(Boolean).length} abiertos`;
  registrar(`imprimir-pdf-restaura-${id}-inicial`, inicial.estado, fila);
  if (m.aplicable) {
    const mixto = await observarPdf(pagina, PLAZO);
    const deshecho = await deshacerMixto(pagina, PLAZO);
    const limpio = JSON.stringify(deshecho) === JSON.stringify(m.inicial);
    registrar(`imprimir-pdf-restaura-${id}-mixto`, limpio ? mixto.estado : "fallida",
      { ruta, mecanismo: "page.pdf (eventos reales del navegador)", ...mixto, ...(limpio ? {} : { resultado: "mixto_no_deshecho", estado_tras_deshacer: deshecho }) });
  }
  const control = await controlNegativo(pagina, PLAZO);
  if (control.resultado !== "sin_desplegables_cerrados") registrar(`imprimir-control-negativo-${id}`, control.estado, { ruta, mecanismo: "eventos sintéticos; sólo control, no acredita el clic", ...control });
}
async function visitar(ancho, juego, superficie, ruta, { exportar = false, error = null, vacio = false } = {}) {
  const { contexto, pagina, registro } = await abrir(ancho);
  const v = { ancho, juego, superficie, ruta, ok: false, motivos: [] };
  try {
    await pagina.goto(BASE + ruta, { waitUntil: "networkidle" }); await listo(pagina);
    v.titulo = await pagina.locator("main h1").innerText(); v.geometria = await geometria(pagina);
    const g = v.geometria;
    if (g.documento > ancho || g.cuerpo > ancho || g.h1 !== 1 || g.tablas.some((t) => !t.teclado || t.izquierda < -1 || t.derecha > ancho + 1) || g.acciones.some((a) => !a.nombre || a.izquierda < -1 || a.derecha > ancho + 1)) v.motivos.push("geometría/landmarks/nombres/región de tabla");
    if (Object.values(g.almacenamiento).some((n) => n !== 0) || g.colores.some((c) => !c.oculta || !c.texto)) v.motivos.push("almacenamiento/color sin texto");
    v.errores = await pagina.locator("main [role=alert][data-codigo]").evaluateAll((xs) => xs.map((x) => x.getAttribute("data-codigo")));
    if (error ? !v.errores.includes(error) : v.errores.length) v.motivos.push(`errores ${v.errores.join(",")}`);
    if (vacio && await pagina.locator('main [data-estado="vacio"]').count() === 0) v.motivos.push("vacío no explícito");
    const barras = await pagina.getByTestId("exportacion").count();
    if (error && barras) v.motivos.push("error habilita exportación");
    if (exportar && !error) await exportaciones(pagina, registro, juego, ruta);
    v.enlaces = await pagina.locator("main a[href]").evaluateAll((xs) => xs.map((a) => ({ ruta: a.getAttribute("href"), texto: a.textContent, estado: a.closest("tr")?.querySelector("[data-integridad]")?.getAttribute("data-integridad"), integridad: a.closest("tr")?.getAttribute("data-integridad") })));
    v.elementos = await pagina.locator("main tr[data-clave]").evaluateAll((xs) => xs.map((x) => ({ clave: x.getAttribute("data-clave"), estado: x.getAttribute("data-integridad") })));
    if (ancho === 390 && ["resumen", "prediccion", "resultados"].includes(superficie)) {
      v.captura = `capturas/${juego}-${superficie}.png`; await pagina.screenshot({ path: join(opciones.salida, v.captura), fullPage: true });
    }
  } catch (e) { v.motivos.push(String(e).split("\n")[0]); }
  const peticiones = registro.peticiones;
  v.solicitudes_api = api(registro).map((p) => new URL(p.url).pathname + new URL(p.url).search);
  v.fichas = v.solicitudes_api.reduce((n, p) => n + coste(p), 0);
  for (const p of peticiones) {
    if (new URL(p.url).origin !== ORIGEN || p.metodo !== "GET") v.motivos.push("petición externa o método distinto de GET");
    if (Object.keys(await p.cabeceras).some((k) => ["authorization", "x-api-key"].includes(k.toLowerCase()))) v.motivos.push("credencial en navegador");
  }
  if (superficie === "prediccion" && !error && (v.fichas !== 4 || v.solicitudes_api.some((p) => p.includes("fiabilidad")))) v.motivos.push("predicción no conserva cuatro fichas automáticas");
  if (registro.errores.length) v.motivos.push("error JavaScript: " + registro.errores.join(";"));
  const noEsperados = registro.consola.filter((x) => x.tipo === "error" && !(error && /status of (4|5)\d\d/.test(x.texto)));
  if (noEsperados.length) v.motivos.push("error consola: " + noEsperados.map((x) => x.texto).join(";"));
  v.ok = !v.motivos.length; resultados.visitas.push(v);
  if (!v.ok) resultados.fallos.push({ donde: ruta, ancho, motivo: v.motivos.join("; ") });
  await contexto.close(); return v;
}

async function pdfs() {
  const casos = [
    ["BALOTO", "/juegos/BALOTO/sorteos?por_pagina=100", "tabla-larga"],
    ["BALOTO_REVANCHA", "/juegos/BALOTO_REVANCHA/resultados", "tabla-ancha-identificadores"],
    ["MILOTO", "/juegos/MILOTO/resultados", "valores-ausentes"],
    ["COLORLOTO", "/juegos/COLORLOTO/prediccion", "combinaciones-numero-color"],
  ];
  for (const [juego, ruta, cobertura] of casos) {
    const { contexto, pagina, registro } = await abrir(1280);
    await pagina.goto(BASE + ruta, { waitUntil: "networkidle" }); await listo(pagina);
    for (const [formato, opcionesPdf] of [["carta-vertical", { format: "Letter" }], ["carta-horizontal", { format: "Letter", landscape: true }], ["a4-vertical", { format: "A4" }]]) {
      const antes = registro.peticiones.length;
      const papel = formato === "carta-horizontal" ? [792, 612] : formato === "a4-vertical" ? [595.2756, 841.8898] : [612, 792];
      // @page conserva márgenes de 14 mm. La comprobación DOM usa el ancho
      // imprimible nominal; el archivo PDF se controla además por sus cajas reales.
      await pagina.setViewportSize({ width: Math.round(papel[0] * 96 / 72 - 28 * 96 / 25.4), height: 900 });
      await pagina.emulateMedia({ media: "print" });
      await pagina.evaluate(() => dispatchEvent(new Event("beforeprint")));
      const superbalotas = await pagina.evaluate(() => [...document.querySelectorAll("main .etiqueta-superbalota")].map((etiqueta) => {
        const r = etiqueta.getBoundingClientRect(), estilo = getComputedStyle(etiqueta);
        const grupo = etiqueta.closest(".grupo-superbalota");
        const contenedor = grupo?.parentElement ?? etiqueta.parentElement;
        const intersecciones = [...(contenedor?.querySelectorAll(".numero-bolita") ?? [])].map((bola) => {
          const b = bola.getBoundingClientRect();
          return Math.max(0, Math.min(r.right, b.right) - Math.max(r.left, b.left)) *
            Math.max(0, Math.min(r.bottom, b.bottom) - Math.max(r.top, b.top));
        });
        return { posicion: estilo.position, ancho: r.width, alto: r.height,
          grupo_explicito: Boolean(grupo), interseccion_maxima_px2: Math.max(0, ...intersecciones) };
      }));
      verificar(`superbalota-print-visible-sin-solapamiento-${juego}-${formato}`,
        superbalotas.every((e) => e.posicion === "static" && e.ancho > 1 && e.alto > 1 && e.grupo_explicito && e.interseccion_maxima_px2 <= 0.01),
        { papel_nominal_pt: papel, ancho_imprimible_css_px: pagina.viewportSize().width, etiquetas: superbalotas });
      // F95-PDF-01: el contenido de cada celda (texto, muestras de color, bolitas) debe quedar dentro de
      // su propia columna en el HTML impreso (un desbordamiento invade la celda vecina en el PDF), y los
      // valores numéricos y nombres de color de las celdas de datos no se parten en dos líneas.
      const desbordes = await pagina.evaluate(() => {
        const fuera = [];
        const oculto = (n) => { const e = n.closest(".visually-hidden"); return e && getComputedStyle(e).position === "absolute"; };
        for (const celda of document.querySelectorAll("main table td, main table th")) {
          const c = celda.getBoundingClientRect();
          if (!c.width || !c.height) continue;
          const cajas = [];
          const recorrido = document.createTreeWalker(celda, NodeFilter.SHOW_TEXT);
          for (let t = recorrido.nextNode(); t; t = recorrido.nextNode()) {
            if (!t.textContent.trim() || oculto(t.parentElement)) continue;
            const r = document.createRange(); r.selectNodeContents(t); cajas.push(...r.getClientRects());
          }
          for (const e of celda.querySelectorAll(".color-swatch, .numero-bolita")) if (!oculto(e)) cajas.push(e.getBoundingClientRect());
          const exceso = Math.max(0, ...cajas.filter((r) => r.width && r.height).map((r) => Math.max(r.right - c.right, c.left - r.left)));
          // Un valor numérico o el nombre de un color no se parte en dos líneas dentro de su celda.
          if (celda.tagName === "TD") {
            const recorrido2 = document.createTreeWalker(celda, NodeFilter.SHOW_TEXT);
            for (let t = recorrido2.nextNode(); t; t = recorrido2.nextNode()) {
              const token = t.textContent.trim();
              if (!/^([+-]?[0-9][0-9.,]*%?|amarillo|azul|blanco|negro|rojo|verde)$/i.test(token) || oculto(t.parentElement)) continue;
              const r = document.createRange(); r.selectNodeContents(t);
              const lineas = new Set([...r.getClientRects()].filter((x) => x.width > 0.5).map((x) => Math.round(x.top)));
              if (lineas.size > 1) fuera.push({ tabla: celda.closest("table")?.closest("[aria-label]")?.getAttribute("aria-label") ?? null,
                texto: token, partido_en_lineas: lineas.size, ancho_celda_px: Math.round(c.width * 100) / 100 });
            }
          }
          if (exceso > 0.5) fuera.push({ tabla: celda.closest("table")?.closest("[aria-label]")?.getAttribute("aria-label") ?? null,
            texto: celda.textContent.trim().slice(0, 60), exceso_px: Math.round(exceso * 100) / 100, ancho_celda_px: Math.round(c.width * 100) / 100 });
        }
        return fuera;
      });
      verificar(`celdas-print-sin-desbordamiento-${juego}-${formato}`, desbordes.length === 0,
        { ancho_imprimible_css_px: pagina.viewportSize().width, celdas_desbordadas: desbordes.length, ejemplos: desbordes.slice(0, 20) });
      const esperados = await pagina.evaluate((codigoJuego) => {
        const textos = [codigoJuego, document.querySelector("main h1")?.textContent.trim()];
        // Contexto, identidad, filtros, unidades y avisos deben sobrevivir a
        // la impresión, además de las filas/cabeceras de todas las columnas.
        for (const e of document.querySelectorAll("main .contexto-exportacion p, main .aviso-experimental, main [data-leyenda], footer p")) {
          if (e.getBoundingClientRect().height) textos.push(e.textContent.trim());
        }
        for (const tabla of document.querySelectorAll("main table")) {
          if (!tabla.getBoundingClientRect().height) continue;
          const cabeceras = [...tabla.querySelectorAll("thead th")];
          textos.push(...cabeceras.map((e) => e.textContent.trim()));
          const ultima = [...tabla.querySelectorAll("tbody tr")].at(-1);
          if (ultima) for (const celda of ultima.querySelectorAll("td")) {
            const t = celda.textContent.trim(); if (t && t !== "—") textos.push(t);
          }
        }
        return [...new Set(textos.filter(Boolean))];
      }, juego);
      const archivo = `pdf/${juego}-${formato}.pdf`;
      await pagina.pdf({ path: join(opciones.salida, archivo), ...opcionesPdf, printBackground: true,
        margin: { top: "12mm", bottom: "12mm", left: "10mm", right: "10mm" }, displayHeaderFooter: false });
      await pagina.evaluate(() => dispatchEvent(new Event("afterprint")));
      await pagina.emulateMedia({ media: "screen" });
      verificar(`pdf-sin-red-${juego}-${formato}`, registro.peticiones.length === antes, { antes, despues: registro.peticiones.length });
      resultados.pdf.push({ archivo, juego, ruta, formato, cobertura, textos_obligatorios: esperados,
        superbalotas_html_print: superbalotas, celdas_desbordadas_html_print: desbordes.length,
        red_adicional: registro.peticiones.length - antes, revision_visual: "pendiente" });
    }
    await contexto.close();
  }
}
async function navegacion() {
  const { contexto, pagina, registro } = await abrir(390);
  await pagina.goto(BASE + "/juegos/BALOTO/modelos?por_pagina=1", { waitUntil: "networkidle" }); await listo(pagina);
  const inicial = await pagina.locator("main tr[data-clave]").getAttribute("data-clave");
  await pagina.getByRole("link", { name: "Página siguiente", exact: true }).click(); await listo(pagina);
  const segunda = await pagina.locator("main tr[data-clave]").getAttribute("data-clave");
  await pagina.goBack(); await listo(pagina); const vuelta = await pagina.locator("main tr[data-clave]").getAttribute("data-clave");
  await pagina.goForward(); await listo(pagina); const avance = await pagina.locator("main tr[data-clave]").getAttribute("data-clave");
  await pagina.reload(); await listo(pagina); const recarga = await pagina.locator("main tr[data-clave]").getAttribute("data-clave");
  verificar("atras-adelante-recarga-pagina", inicial !== segunda && vuelta === inicial && avance === segunda && recarga === segunda, { inicial, segunda, vuelta, avance, recarga });
  await exportaciones(pagina, registro, "BALOTO", new URL(pagina.url()).pathname + new URL(pagina.url()).search);
  await pagina.locator("main tr[data-clave] a").first().click(); await listo(pagina);
  const volver = pagina.getByRole("link", { name: /Volver.*modelos/i }).first();
  if (!await volver.count()) throw new Error("La ficha no conserva un enlace para volver al listado de modelos");
  await volver.click(); await listo(pagina); verificar("volver-conserva-filtro-pagina", new URL(pagina.url()).searchParams.get("pagina") === "2" && new URL(pagina.url()).searchParams.get("por_pagina") === "1");
  await pagina.goto(BASE + "/juegos/BALOTO/prediccion", { waitUntil: "networkidle" }); await listo(pagina);
  const fuente = api(registro).filter((x) => x.url.includes("fiabilidad")).length;
  await exportaciones(pagina, registro, "BALOTO", "/juegos/BALOTO/prediccion");
  verificar("exportar-no-consulta-fiabilidad", api(registro).filter((x) => x.url.includes("fiabilidad")).length === fuente);
  const boton = pagina.getByRole("button", { name: "Consultar fiabilidad", exact: true });
  if (await boton.count()) { await boton.click(); await listo(pagina); await exportaciones(pagina, registro, "BALOTO", "/juegos/BALOTO/prediccion"); }
  // El historial automático pertenece a la configuración vigente. La clave de
  // otra configuración se acredita en el listado público de carteras de 9.4
  // y se consulta expresamente, sin cambiar esa identidad ni el backend.
  await pagina.goto(BASE + "/juegos/BALOTO/carteras", { waitUntil: "networkidle" }); await listo(pagina);
  const historica = pagina.locator('main tr[data-clave][data-integridad="disponible"]').filter({ hasText: "random_forest_clasificador" }).last();
  if (!await historica.count()) throw new Error("Falta una cartera histórica de otra configuración en el listado público");
  const claveHistorica = await historica.getAttribute("data-clave");
  const rutaHistorica = "/juegos/BALOTO/prediccion?cartera=" + encodeURIComponent(claveHistorica);
  await pagina.goto(BASE + rutaHistorica, { waitUntil: "networkidle" }); await listo(pagina);
  await pagina.getByRole("button", { name: "Consultar fiabilidad", exact: true }).click(); await listo(pagina);
  const avisoContexto = pagina.getByText(/La fiabilidad no está disponible para esta cartera/);
  verificar("cartera-historica-rechaza-fiabilidad-de-configuracion-actual", await avisoContexto.count() === 1,
    { clave_historica: claveHistorica, atribucion_ajena_rechazada: await avisoContexto.count() === 1 });
  const nAntesHistorica = resultados.descargas.length;
  await exportaciones(pagina, registro, "BALOTO", rutaHistorica);
  if (!SOLO_IMPRESION) {
  const jsonHistorica = resultados.descargas.slice(nAntesHistorica).find((d) => d.formato === "json");
  if (!jsonHistorica) throw new Error("Falta la descarga histórica real");
  const textoHistorico = JSON.parse(await readFile(join(opciones.salida, jsonHistorica.archivo), "utf8"));
  verificar("exportacion-historica-conserva-identidad-sin-fiabilidad-ajena",
    textoHistorico.datos.prediccion?.clave === claveHistorica && textoHistorico.datos.fiabilidad === null &&
    textoHistorico.datos.estado_fiabilidad === "no_acreditada",
    { clave_historica: claveHistorica, clave_exportada: textoHistorico.datos.prediccion?.clave,
      estado_fiabilidad: textoHistorico.datos.estado_fiabilidad });
  }
  await contexto.close();
  for (const ancho of ANCHOS) {
    const t = await abrir(ancho); await t.pagina.goto(BASE + "/juegos/COLORLOTO/resultados", { waitUntil: "networkidle" }); await listo(t.pagina);
    await t.pagina.keyboard.press("Tab"); const primero = await t.pagina.evaluate(() => document.activeElement?.textContent.trim());
    await t.pagina.keyboard.press("Enter"); const destino = await t.pagina.evaluate(() => document.activeElement?.id);
    const region = t.pagina.locator(".tabla-desplazable").first(); await region.focus();
    verificar(`teclado-salto-scroll-${ancho}`, primero === "Saltar al contenido" && destino === "contenido" && await region.evaluate((e) => e === document.activeElement));
    await t.contexto.close();
  }
}
async function cuota() {
  const { contexto, pagina, registro } = await abrir(390);
  await pagina.goto(BASE + "/juegos/BALOTO/prediccion", { waitUntil: "networkidle" }); await listo(pagina);
  await exportaciones(pagina, registro, "BALOTO", "/juegos/BALOTO/prediccion");
  await pagina.getByRole("button", { name: "Consultar fiabilidad", exact: true }).click();
  const alerta = pagina.locator('main [role="alert"][data-codigo="limite_excedido"]'); await alerta.waitFor();
  const antes = api(registro).length, texto = await alerta.innerText(), boton = alerta.getByRole("button", { name: "Reintentar", exact: true });
  const deshabilitado = await boton.isDisabled(); await pagina.waitForTimeout(1200); const sinAccion = api(registro).length;
  // La predicción ya cargada sigue exportable; no incorpora la fiabilidad con 429.
  await exportaciones(pagina, registro, "BALOTO", "/juegos/BALOTO/prediccion");
  await pagina.waitForFunction(() => !document.querySelector('main [role="alert"] button')?.disabled, null, { timeout: 75000 });
  const trasEspera = api(registro).length; await boton.click(); await listo(pagina);
  verificar("cuota-cuatro-fichas-descargas-cero-red-reintento-manual", deshabilitado && /Retry|reintentar/.test(texto) && antes === sinAccion && antes === trasEspera && api(registro).length === antes + 1, { antes, sinAccion, trasEspera, trasManual: api(registro).length });
  await contexto.close();
}

try {
  if (opciones.escenario === "normal") {
    // PDF es una comprobación independiente: se conserva incluso si después
    // falla una sonda JSON o de navegación. No se condiciona a otras aserciones.
    if (!SOLO_IMPRESION) try { await pdfs(); } catch (e) { resultados.fallos.push({ donde: "pdf", motivo: String(e) }); }
    if (opciones["solo-pdf"] !== "true") {
    for (const ancho of ANCHOS) for (const juego of JUEGOS) {
      const prefijo = `/juegos/${juego}`, ex = ancho === 390 || !ANCHOS.includes(390);
      await visitar(ancho, juego, "resumen", prefijo, { exportar: ex });
      const sorteos = await visitar(ancho, juego, "sorteos", prefijo + "/sorteos?por_pagina=20", { exportar: ex });
      const sorteo = sorteos.enlaces?.find((x) => new RegExp(`/juegos/${juego}/sorteos/\\d+`).test(x.ruta));
      if (!sorteo) throw new Error(`Falta detalle sorteo ${juego}`); await visitar(ancho, juego, "sorteo", sorteo.ruta, { exportar: ex });
      await visitar(ancho, juego, "estadisticas", prefijo + "/estadisticas", { exportar: ex });
      await visitar(ancho, juego, "metrica", prefijo + "/estadisticas/frecuencia-numeros", { exportar: ex });
      await visitar(ancho, juego, "prediccion", prefijo + "/prediccion", { exportar: ex });
      await visitar(ancho, juego, "fiabilidad", prefijo + "/fiabilidad", { exportar: ex });
      for (const grupo of ["modelos", "carteras"]) {
        const v = await visitar(ancho, juego, grupo, prefijo + "/" + grupo, { exportar: ex });
        const detalle = v.enlaces?.find((x) => new RegExp(`/juegos/${juego}/${grupo}/[a-f0-9]{64}`).test(x.ruta));
        if (!detalle) throw new Error(`Falta detalle ${grupo} ${juego}`); await visitar(ancho, juego, grupo.slice(0, -1), detalle.ruta, { exportar: ex });
      }
      await visitar(ancho, juego, "resultados", prefijo + "/resultados", { exportar: ex });
      const sims = await visitar(ancho, juego, "simulaciones", prefijo + "/simulaciones", { exportar: ex });
      const sim = sims.enlaces?.find((x) => /^\/simulaciones\//.test(x.ruta) && x.estado === "verificada");
      if (!sim) throw new Error(`Falta simulación íntegra ${juego}`); await visitar(ancho, juego, "simulacion", sim.ruta, { exportar: ex });
    }
    if (!SOLO_IMPRESION) for (const ancho of ANCHOS) for (const [superficie, ruta] of [["inicio", "/"], ["servicio", "/servicio"], ["error-ruta", "/no-existe"]]) await visitar(ancho, null, superficie, ruta);
    await navegacion();
    }
  } else if (opciones.escenario === "vacio") {
    for (const ancho of ANCHOS) for (const grupo of ["modelos", "carteras", "resultados", "simulaciones"]) await visitar(ancho, "BALOTO", grupo, `/juegos/BALOTO/${grupo}`, { exportar: true, vacio: true });
  } else if (opciones.escenario === "alterado") {
    for (const grupo of ["modelos", "carteras"]) {
      const v = await visitar(390, "BALOTO", grupo, `/juegos/BALOTO/${grupo}`, { exportar: true });
      const clave = v.elementos?.find((x) => x.estado === "alterado")?.clave;
      verificar(`fila-alterada-aislada-${grupo}`, Boolean(clave));
      if (clave) await visitar(390, "BALOTO", grupo.slice(0, -1), `/juegos/BALOTO/${grupo}/${clave}`, { error: "alterado" });
    }
  } else if (opciones.escenario === "incompatible") {
    const v = await visitar(390, "BALOTO", "modelos", "/juegos/BALOTO/modelos", { exportar: true });
    const clave = v.elementos?.find((x) => x.estado === "incompatible")?.clave;
    verificar("fila-incompatible-preservada", Boolean(clave));
    if (clave) await visitar(390, "BALOTO", "modelo", `/juegos/BALOTO/modelos/${clave}`, { exportar: true });
  } else if (opciones.escenario === "cuota") await cuota();
  else if (opciones.escenario === "api_caida") for (const ancho of ANCHOS) await visitar(ancho, "BALOTO", "error-api", "/juegos/BALOTO/modelos", { error: "api_no_disponible" });
  else throw new Error("Escenario no reconocido");
} catch (e) { resultados.fallos.push({ donde: "recorrido", motivo: String(e) }); }
finally {
  await navegador.close();
  resultados.ok = resultados.fallos.length === 0;
  resultados.resumen = { visitas: resultados.visitas.length, comprobaciones: resultados.comprobaciones.length,
    comprobaciones_aprobadas: resultados.comprobaciones.filter((c) => c.estado === "aprobada").length,
    comprobaciones_fallidas: resultados.comprobaciones.filter((c) => c.estado === "fallida").length,
    no_evaluables: resultados.no_evaluables.length, descargas: resultados.descargas.length, pdfs: resultados.pdf.length, capturas: resultados.visitas.filter((v) => v.captura).length, fallos: resultados.fallos.length };
  await writeFile(join(opciones.salida, "resultados.json"), JSON.stringify(resultados, null, 2) + "\n");
  await writeFile(join(opciones.salida, "matriz-pdf.json"), JSON.stringify(resultados.pdf, null, 2) + "\n");
  const esc = (s) => String(s).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll('"', "&quot;");
  const casos = [...resultados.visitas.map((v) => ({ nombre: `${v.ancho} ${v.ruta}`, estado: v.ok ? "aprobada" : "fallida", motivo: v.motivos.join("; ") })),
    ...resultados.comprobaciones.map((c) => ({ nombre: c.nombre, estado: c.estado, motivo: c.estado === "no_evaluable" ? `${c.resultado}: ${c.motivo}` : JSON.stringify(c).slice(0, 4000) }))];
  if (resultados.fallos.some((f) => f.donde === "recorrido")) casos.push({ nombre: "recorrido", estado: "fallida", motivo: resultados.fallos.find((f) => f.donde === "recorrido").motivo });
  await writeFile(join(opciones.salida, "junit.xml"), `<?xml version="1.0" encoding="utf-8"?><testsuite name="Fase9.5-${esc(opciones.escenario)}-${esc(process.platform)}" tests="${casos.length}" failures="${casos.filter((c) => c.estado === "fallida").length}" errors="0" skipped="${casos.filter((c) => c.estado === "no_evaluable").length}">${casos.map((c) => casoJunit(c, esc)).join("")}</testsuite>\n`);
  console.log(JSON.stringify({ ok: resultados.ok, ...resultados.resumen })); process.exitCode = resultados.ok ? 0 : 1;
}
