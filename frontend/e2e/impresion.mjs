/**
 * F95-NAT-01: observación de la impresión en el ensayo 9.5, sin intervenir en el producto.
 *
 * El clic real en «Imprimir» y `page.pdf` se observan por sus eventos y por los estados de
 * `main details`, con plazo acotado. La clasificación es pura y distingue:
 *  - restauración correcta (afterprint confiable y estado inicial recuperado);
 *  - afterprint presente sin restauración, o beforeprint sin abrir los desplegables (fallos);
 *  - afterprint no emitido tras un beforeprint confiable y la salida de print(): la restauración
 *    NO puede evaluarse por ese mecanismo y se registra como «no_evaluable», nunca como aprobada;
 *  - fallo del clic, print() no invocado, ausencia de beforeprint o página bloqueada (fallos).
 * Sólo dos ausencias son no evaluables, cada una con su causa observada: la del afterprint de un
 * ciclo propio (headless sin diálogo) y la de beforeprint en una pestaña cuyo ensayo ya registró
 * un ciclo sin afterprint. Cualquier otra ausencia de eventos es un fallo.
 * Los eventos sintéticos sólo se usan como control negativo y nunca acreditan el clic real.
 */

export const PLAZO_IMPRESION_MS = 3000;

/** Se instala con addInitScript: registra eventos, entrada/salida de print() y estados. */
export function instrumentarImpresion() {
  const t0 = performance.now();
  const estados = () => [...document.querySelectorAll("main details")].map((d) => d.open);
  const r = { antes: 0, despues: 0, eventos: [] };
  window.__ensayo_impresion = r;
  const reg = (tipo, extra = {}) => r.eventos.push({
    t: Math.round((performance.now() - t0) * 10) / 10, tipo, print: matchMedia("print").matches, details: estados(), ...extra,
  });
  // Registrados antes que los del producto: el evento ve el estado previo y su tarea, el posterior.
  addEventListener("beforeprint", (e) => {
    r.antes++; reg("beforeprint", { confiable: e.isTrusted });
    setTimeout(() => reg("beforeprint+tarea", { confiable: e.isTrusted }), 0);
  });
  addEventListener("afterprint", (e) => {
    r.despues++; reg("afterprint", { confiable: e.isTrusted });
    setTimeout(() => reg("afterprint+tarea", { confiable: e.isTrusted }), 0);
  });
  matchMedia("print").addEventListener("change", (e) => reg("matchMedia-print", { coincide: e.matches }));
  const original = window.print;
  window.print = function print() {
    reg("print:entrada");
    try { return original.call(window); } finally { reg("print:salida"); }
  };
}

const igual = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const todosAbiertos = (xs) => Array.isArray(xs) && xs.every(Boolean);
const confiables = (eventos, tipo) => eventos.filter((e) => e.tipo === tipo && e.confiable === true);
const fila = (estado, resultado, extra = {}) => ({ estado, resultado, ...extra });
// Restauración comprobada; si no había desplegables cerrados la comparación no discrimina y se dice.
const restaurada = (base) => fila("aprobada", base.vacia ? (base.desplegables ? "restaurado_sin_cerrados" : "sin_desplegables") : "restaurado",
  { ...base, restauracion: true });

/** Estado de los desplegables tras el beforeprint confiable: debe estar todo abierto. */
function preparados(eventos) {
  const tras = confiables(eventos, "afterprint")[0]?.details // visto antes de que actúe el producto
    ?? eventos.find((e) => e.tipo === "beforeprint+tarea" && e.confiable === true)?.details
    ?? eventos.find((e) => e.tipo === "print:salida")?.details;
  return { observado: tras ?? null, ok: todosAbiertos(tras) };
}

/**
 * Clasifica un clic real en «Imprimir».
 * @param o.inicial estados antes del clic; o.final estados al terminar la espera;
 *        o.eventos eventos registrados desde el clic; o.clic_error texto o null;
 *        o.bloqueada la página no respondió dentro del plazo; o.plazo_agotado no llegó afterprint+tarea;
 *        o.pestana_pendiente el ensayo registró antes en esta pestaña un ciclo sin afterprint.
 */
export function clasificarClic(o) {
  const ev = o.eventos ?? [];
  const base = { desplegables: o.inicial?.length ?? null, vacia: !(o.inicial ?? []).some((x) => !x) };
  if (o.clic_error) return fila("fallida", "fallo_clic", { ...base, detalle: String(o.clic_error).slice(0, 300) });
  if (o.bloqueada) return fila("fallida", "pagina_bloqueada", base);
  const entrada = ev.some((e) => e.tipo === "print:entrada"), salida = ev.some((e) => e.tipo === "print:salida");
  if (!entrada) return fila("fallida", "print_no_invocado", base);
  const antes = confiables(ev, "beforeprint"), despues = confiables(ev, "afterprint");
  if (!antes.length) {
    if (!despues.length && salida && o.pestana_pendiente === true) {
      return fila("no_evaluable", "impresion_pendiente_en_pestana", { ...base, restauracion: null,
        motivo: "print() retornó sin beforeprint en una pestaña con un ciclo anterior sin afterprint; el navegador no inicia otro" });
    }
    return fila("fallida", ev.some((e) => e.tipo === "beforeprint") ? "beforeprint_no_confiable" : "sin_beforeprint", base);
  }
  const prep = preparados(ev);
  if (!prep.ok) return fila("fallida", "beforeprint_sin_preparar", { ...base, preparados: prep.observado });
  if (despues.length) {
    return igual(o.final, o.inicial) ? restaurada(base)
      : fila("fallida", "afterprint_sin_restaurar", { ...base, restauracion: false, final: o.final });
  }
  if (!salida) return fila("fallida", "print_no_retorna", base);
  if (o.plazo_agotado !== true) return fila("fallida", "espera_incompleta", base);
  return fila("no_evaluable", "afterprint_no_emitido", { ...base, restauracion: null,
    motivo: "beforeprint confiable y print() retornó sin afterprint dentro del plazo: la restauración no puede evaluarse por el clic" });
}

/**
 * Clasifica `page.pdf` (eventos reales del navegador) sobre un estado inicial.
 * o.documento_pendiente: el documento ya tiene un beforeprint confiable sin afterprint (no se ejecuta).
 */
export function clasificarPdf(o) {
  const ev = o.eventos ?? [];
  const base = { desplegables: o.inicial?.length ?? null, vacia: !(o.inicial ?? []).some((x) => !x) };
  if (o.documento_pendiente) return fila("no_evaluable", "ciclo_pendiente_en_documento", { ...base, restauracion: null,
    motivo: "el documento conserva un beforeprint confiable sin afterprint; el estado de partida no es el de la consulta" });
  if (o.error) return fila("fallida", "fallo_pdf", { ...base, detalle: String(o.error).slice(0, 300) });
  if (!confiables(ev, "beforeprint").length) return fila("fallida", "sin_beforeprint", base);
  if (!confiables(ev, "afterprint").length) return fila("fallida", "pdf_sin_afterprint", base);
  const prep = preparados(ev);
  if (!prep.ok) return fila("fallida", "beforeprint_sin_preparar", { ...base, preparados: prep.observado });
  return igual(o.final, o.inicial) ? restaurada(base)
    : fila("fallida", "afterprint_sin_restaurar", { ...base, restauracion: false, final: o.final });
}

/** Control negativo sintético: beforeprint sin afterprint debe cambiar el estado; afterprint lo devuelve. */
export function clasificarControlNegativo({ inicial, tras_beforeprint, tras_afterprint, documento_pendiente = false }) {
  if (documento_pendiente) return fila("no_evaluable", "ciclo_pendiente_en_documento", { sintetico: true });
  if (!inicial?.some((x) => !x)) return fila("no_evaluable", "sin_desplegables_cerrados", { sintetico: true });
  if (igual(tras_beforeprint, inicial)) return fila("fallida", "comparacion_no_discrimina", { sintetico: true, tras_beforeprint });
  if (!igual(tras_afterprint, inicial)) return fila("fallida", "control_sin_limpieza", { sintetico: true, tras_afterprint });
  return fila("aprobada", "discrimina", { sintetico: true });
}

/** Promesa con plazo; nunca deja la espera abierta si la página no responde. */
export function conPlazo(promesa, ms, motivo = "plazo agotado") {
  let reloj;
  return Promise.race([promesa, new Promise((_, no) => { reloj = setTimeout(() => no(new Error(motivo)), ms); })])
    .finally(() => clearTimeout(reloj));
}

const leerEstados = (pagina) => pagina.locator("main details").evaluateAll((xs) => xs.map((x) => x.open));
const leerEventos = (pagina) => pagina.evaluate(() => window.__ensayo_impresion?.eventos.length ?? 0);
const desde = (pagina, i) => pagina.evaluate((n) => window.__ensayo_impresion?.eventos.slice(n) ?? [], i);
const pestanasPendientes = new WeakSet();

/** Indica si el documento tiene un beforeprint confiable sin su afterprint. */
export async function documentoPendiente(pagina, plazo = PLAZO_IMPRESION_MS) {
  const ev = await conPlazo(desde(pagina, 0), plazo, "pagina_bloqueada");
  return confiables(ev, "beforeprint").length > confiables(ev, "afterprint").length;
}

async function esperarAfterprint(pagina, i, plazo) {
  try {
    await pagina.waitForFunction((n) => (window.__ensayo_impresion?.eventos ?? []).slice(n)
      .some((e) => e.tipo === "afterprint+tarea" && e.confiable === true), i, { timeout: plazo, polling: 25 });
    return false;
  } catch { return true; }
}

/** Observa un clic real en el botón «Imprimir» indicado y lo clasifica. */
export async function observarClic(pagina, boton, plazo = PLAZO_IMPRESION_MS) {
  const o = { pestana_pendiente: pestanasPendientes.has(pagina), plazo_ms: plazo };
  try {
    o.inicial = await conPlazo(leerEstados(pagina), plazo, "pagina_bloqueada");
    const i = await conPlazo(leerEventos(pagina), plazo, "pagina_bloqueada");
    try { await boton.click({ timeout: plazo }); } catch (e) { o.clic_error = String(e).split("\n")[0]; }
    if (!o.clic_error) {
      o.plazo_agotado = await conPlazo(esperarAfterprint(pagina, i, plazo), plazo * 2, "pagina_bloqueada");
      o.final = await conPlazo(leerEstados(pagina), plazo, "pagina_bloqueada");
    }
    o.eventos = await conPlazo(desde(pagina, i), plazo, "pagina_bloqueada");
  } catch { o.bloqueada = true; }
  const c = { ...clasificarClic(o), inicial: o.inicial ?? null, final: o.final ?? null, eventos: o.eventos ?? [],
    plazo_ms: plazo, plazo_agotado: o.plazo_agotado ?? null, pestana_pendiente_previa: o.pestana_pendiente };
  if (c.resultado === "afterprint_no_emitido") pestanasPendientes.add(pagina);
  return c;
}

/** Genera un PDF en memoria (eventos reales del navegador) y clasifica la restauración. */
export async function observarPdf(pagina, plazo = PLAZO_IMPRESION_MS) {
  const o = {};
  o.inicial = await conPlazo(leerEstados(pagina), plazo, "pagina_bloqueada");
  o.documento_pendiente = await documentoPendiente(pagina, plazo);
  if (!o.documento_pendiente) {
    const i = await conPlazo(leerEventos(pagina), plazo, "pagina_bloqueada");
    try { await conPlazo(pagina.pdf({ printBackground: true }), plazo * 10, "pdf sin respuesta"); } catch (e) { o.error = String(e).split("\n")[0]; }
    if (!o.error) await esperarAfterprint(pagina, i, plazo);
    o.final = await conPlazo(leerEstados(pagina), plazo, "pagina_bloqueada");
    o.eventos = await conPlazo(desde(pagina, i), plazo, "pagina_bloqueada");
  }
  return { ...clasificarPdf(o), inicial: o.inicial, final: o.final ?? null, eventos: o.eventos ?? [] };
}

/** Control negativo con eventos SINTÉTICOS (no confiables): sólo prueba que la comparación discrimina. */
export async function controlNegativo(pagina, plazo = PLAZO_IMPRESION_MS) {
  const inicial = await conPlazo(leerEstados(pagina), plazo, "pagina_bloqueada");
  const documento_pendiente = await documentoPendiente(pagina, plazo);
  if (documento_pendiente || !inicial.some((x) => !x)) return { ...clasificarControlNegativo({ inicial, documento_pendiente }), inicial };
  await pagina.evaluate(() => dispatchEvent(new Event("beforeprint")));
  const tras_beforeprint = await leerEstados(pagina);
  await pagina.evaluate(() => dispatchEvent(new Event("afterprint")));
  const tras_afterprint = await leerEstados(pagina);
  return { ...clasificarControlNegativo({ inicial, tras_beforeprint, tras_afterprint }), inicial, tras_beforeprint, tras_afterprint };
}

/** Abre con un clic real el primer desplegable cerrado si hay al menos dos y todos están cerrados. */
export async function prepararMixto(pagina, plazo = PLAZO_IMPRESION_MS) {
  const inicial = await conPlazo(leerEstados(pagina), plazo, "pagina_bloqueada");
  if (inicial.length < 2 || inicial.some(Boolean)) return { aplicable: false, inicial };
  await pagina.locator("main details > summary").first().click({ timeout: plazo });
  const mixto = await leerEstados(pagina);
  return { aplicable: mixto[0] === true && mixto.slice(1).every((x) => !x), inicial, mixto };
}

/** Deshace el estado mixto con un clic real en el mismo resumen. */
export async function deshacerMixto(pagina, plazo = PLAZO_IMPRESION_MS) {
  await pagina.locator("main details > summary").first().click({ timeout: plazo });
  return leerEstados(pagina);
}

/** Caso JUnit: aprobada, fallida (failure) o no evaluable (skipped con su motivo). */
export function casoJunit({ nombre, estado, motivo }, esc) {
  const n = esc(nombre);
  if (estado === "fallida") return `<testcase name="${n}"><failure message="${esc(motivo)}"/></testcase>`;
  if (estado === "no_evaluable") return `<testcase name="${n}"><skipped message="${esc(motivo)}"/></testcase>`;
  return `<testcase name="${n}"></testcase>`;
}
