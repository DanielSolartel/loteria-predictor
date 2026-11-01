/**
 * F95-NAT-01: regresiones de la observación de la impresión (e2e/impresion.mjs).
 *
 * 1. Unitarias (sin navegador): la clasificación distingue restauración correcta, afterprint
 *    presente sin restauración, afterprint ausente, beforeprint sin preparar y fallo del clic o
 *    ausencia de beforeprint; ninguna ausencia de eventos se acepta de forma genérica.
 * 2. Navegador real (opcional, --navegador): una página de prueba local con variantes correcta y
 *    defectuosas del manejo beforeprint/afterprint, observadas con clic real, page.pdf y control
 *    negativo sintético. --perfil fija el comportamiento esperado del navegador:
 *      afterprint-sincrono  headless antiguo (chrome-headless-shell): afterprint dentro de print();
 *      afterprint-ausente   headless nuevo (Chromium completo, Brave): print() retorna sin afterprint.
 *    Contraste: la comparación de la v1 (50 ms tras el clic) se reproduce para mostrar dónde falla
 *    o aprueba sin evaluar nada.
 *
 * Uso (desde frontend/):
 *   node e2e/impresion-regresiones.mjs --salida <carpeta nueva>
 *   node e2e/impresion-regresiones.mjs --salida <carpeta nueva> --navegador <ejecutable> --perfil afterprint-ausente
 * Devuelve 0 sólo si todos los casos dan exactamente el resultado esperado.
 */
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import {
  casoJunit, clasificarClic, clasificarControlNegativo, clasificarPdf, controlNegativo, instrumentarImpresion,
  observarClic, observarPdf, prepararMixto,
} from "./impresion.mjs";

const opciones = {};
for (let i = 2; i < process.argv.length; i += 2) opciones[process.argv[i].replace(/^--/, "")] = process.argv[i + 1];
if (!opciones.salida) throw new Error("Falta --salida");
if (opciones.navegador && !["afterprint-sincrono", "afterprint-ausente"].includes(opciones.perfil)) throw new Error("--perfil afterprint-sincrono|afterprint-ausente");
await mkdir(opciones.salida, { recursive: false });
const informe = { unitarias: [], navegador: null, ok: false };

// ---------- 1. Unitarias ----------
const ev = (tipo, details, confiable) => ({ t: 0, tipo, print: false, details, ...(confiable === undefined ? {} : { confiable }) });
const C = [false, false, false], A = [true, true, true], M = [true, false, false];
const ciclo = (inicial, preparado, final, { after = true, salidaAntes = false } = {}) => [
  ev("print:entrada", inicial), ev("beforeprint", inicial, true),
  ...(salidaAntes ? [ev("print:salida", preparado)] : []),
  ...(after ? [ev("afterprint", preparado, true)] : []),
  ...(salidaAntes ? [] : [ev("print:salida", after ? final : preparado)]),
  ev("beforeprint+tarea", after ? final : preparado, true), ...(after ? [ev("afterprint+tarea", final, true)] : []),
];
const unitarias = [
  ["clic: restauración correcta (cerrados)", () => clasificarClic({ inicial: C, final: C, eventos: ciclo(C, A, C), plazo_agotado: false }), "aprobada", "restaurado"],
  ["clic: restauración correcta (mixto)", () => clasificarClic({ inicial: M, final: M, eventos: ciclo(M, A, M), plazo_agotado: false }), "aprobada", "restaurado"],
  ["clic: afterprint presente sin restauración", () => clasificarClic({ inicial: C, final: A, eventos: ciclo(C, A, A), plazo_agotado: false }), "fallida", "afterprint_sin_restaurar"],
  ["clic: afterprint ausente tras beforeprint confiable y salida de print()", () => clasificarClic({ inicial: C, final: A, eventos: ciclo(C, A, A, { after: false, salidaAntes: true }), plazo_agotado: true }), "no_evaluable", "afterprint_no_emitido"],
  ["clic: afterprint ausente sin agotar el plazo no se acepta", () => clasificarClic({ inicial: C, final: A, eventos: ciclo(C, A, A, { after: false, salidaAntes: true }), plazo_agotado: false }), "fallida", "espera_incompleta"],
  ["clic: afterprint ausente y print() sin retorno", () => clasificarClic({ inicial: C, final: A, eventos: [ev("print:entrada", C), ev("beforeprint", C, true), ev("beforeprint+tarea", A, true)], plazo_agotado: true }), "fallida", "print_no_retorna"],
  ["clic: beforeprint sin abrir desplegables (afterprint ausente)", () => clasificarClic({ inicial: C, final: C, eventos: ciclo(C, C, C, { after: false, salidaAntes: true }), plazo_agotado: true }), "fallida", "beforeprint_sin_preparar"],
  ["clic: beforeprint sin abrir desplegables (afterprint presente)", () => clasificarClic({ inicial: C, final: C, eventos: ciclo(C, C, C), plazo_agotado: false }), "fallida", "beforeprint_sin_preparar"],
  ["clic: fallo del clic", () => clasificarClic({ inicial: C, clic_error: "locator.click: Timeout" }), "fallida", "fallo_clic"],
  ["clic: página bloqueada", () => clasificarClic({ inicial: C, bloqueada: true }), "fallida", "pagina_bloqueada"],
  ["clic: print() no invocado", () => clasificarClic({ inicial: C, final: C, eventos: [], plazo_agotado: true }), "fallida", "print_no_invocado"],
  ["clic: ausencia de beforeprint sin ciclo previo en la pestaña", () => clasificarClic({ inicial: C, final: C, eventos: [ev("print:entrada", C), ev("print:salida", C)], plazo_agotado: true, pestana_pendiente: false }), "fallida", "sin_beforeprint"],
  ["clic: ausencia de beforeprint con ciclo previo sin afterprint en la pestaña", () => clasificarClic({ inicial: C, final: C, eventos: [ev("print:entrada", C), ev("print:salida", C)], plazo_agotado: true, pestana_pendiente: true }), "no_evaluable", "impresion_pendiente_en_pestana"],
  ["clic: pestaña pendiente sin salida de print() no se acepta", () => clasificarClic({ inicial: C, final: C, eventos: [ev("print:entrada", C)], plazo_agotado: true, pestana_pendiente: true }), "fallida", "sin_beforeprint"],
  ["clic: beforeprint sintético (no confiable) no acredita", () => clasificarClic({ inicial: C, final: C, eventos: [ev("print:entrada", C), ev("beforeprint", C, false), ev("afterprint", A, false), ev("print:salida", C)], plazo_agotado: false }), "fallida", "beforeprint_no_confiable"],
  ["clic: afterprint sintético no acredita la restauración", () => clasificarClic({ inicial: C, final: C, eventos: [ev("print:entrada", C), ev("beforeprint", C, true), ev("print:salida", A), ev("beforeprint+tarea", A, true), ev("afterprint", A, false), ev("afterprint+tarea", C, false)], plazo_agotado: true }), "no_evaluable", "afterprint_no_emitido"],
  ["clic: todo abierto al inicio no se presenta como restauración discriminante", () => clasificarClic({ inicial: A, final: A, eventos: ciclo(A, A, A), plazo_agotado: false }), "aprobada", "restaurado_sin_cerrados"],
  ["pdf: página sin desplegables", () => clasificarPdf({ inicial: [], final: [], eventos: [ev("beforeprint", [], true), ev("afterprint", [], true)] }), "aprobada", "sin_desplegables"],
  ["pdf: restauración correcta", () => clasificarPdf({ inicial: M, final: M, eventos: ciclo(M, A, M).filter((e) => !e.tipo.startsWith("print:")) }), "aprobada", "restaurado"],
  ["pdf: afterprint presente sin restauración", () => clasificarPdf({ inicial: C, final: A, eventos: ciclo(C, A, A).filter((e) => !e.tipo.startsWith("print:")) }), "fallida", "afterprint_sin_restaurar"],
  ["pdf: sin afterprint", () => clasificarPdf({ inicial: C, final: A, eventos: [ev("beforeprint", C, true), ev("beforeprint+tarea", A, true)] }), "fallida", "pdf_sin_afterprint"],
  ["pdf: sin beforeprint", () => clasificarPdf({ inicial: C, final: C, eventos: [] }), "fallida", "sin_beforeprint"],
  ["pdf: beforeprint sin preparar", () => clasificarPdf({ inicial: C, final: C, eventos: ciclo(C, C, C).filter((e) => !e.tipo.startsWith("print:")) }), "fallida", "beforeprint_sin_preparar"],
  ["pdf: error", () => clasificarPdf({ inicial: C, error: "page.pdf: Target closed" }), "fallida", "fallo_pdf"],
  ["pdf: documento con ciclo pendiente", () => clasificarPdf({ inicial: A, documento_pendiente: true }), "no_evaluable", "ciclo_pendiente_en_documento"],
  ["control negativo: discrimina", () => clasificarControlNegativo({ inicial: C, tras_beforeprint: A, tras_afterprint: C }), "aprobada", "discrimina"],
  ["control negativo: no discrimina", () => clasificarControlNegativo({ inicial: C, tras_beforeprint: C, tras_afterprint: C }), "fallida", "comparacion_no_discrimina"],
  ["control negativo: limpieza incompleta", () => clasificarControlNegativo({ inicial: C, tras_beforeprint: A, tras_afterprint: A }), "fallida", "control_sin_limpieza"],
  ["control negativo: sin desplegables cerrados", () => clasificarControlNegativo({ inicial: A }), "no_evaluable", "sin_desplegables_cerrados"],
];
for (const [nombre, f, estado, resultado] of unitarias) {
  const r = f();
  informe.unitarias.push({ nombre, esperado: `${estado}:${resultado}`, obtenido: `${r.estado}:${r.resultado}`, ok: r.estado === estado && r.resultado === resultado });
}
const esc = (s) => String(s).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll('"', "&quot;");
try {
  assert.equal(casoJunit({ nombre: "a", estado: "aprobada" }, esc), '<testcase name="a"></testcase>');
  assert.equal(casoJunit({ nombre: "a", estado: "fallida", motivo: "x" }, esc), '<testcase name="a"><failure message="x"/></testcase>');
  assert.equal(casoJunit({ nombre: "a", estado: "no_evaluable", motivo: "afterprint_no_emitido" }, esc), '<testcase name="a"><skipped message="afterprint_no_emitido"/></testcase>');
  informe.unitarias.push({ nombre: "junit: aprobada, failure y skipped", ok: true });
} catch (e) { informe.unitarias.push({ nombre: "junit: aprobada, failure y skipped", ok: false, error: String(e) }); }

// ---------- 2. Navegador real con página de prueba local ----------
const PAGINA = (variante) => `<!doctype html><html lang="es"><head><meta charset="utf-8"><title>F95 impresión</title>
<style>#tapa{position:fixed;inset:0;background:rgba(0,0,0,.01);z-index:9}</style></head><body><main>
<details><summary>Uno</summary><p>a</p></details><details><summary>Dos</summary><p>b</p></details><details><summary>Tres</summary><p>c</p></details>
<button id="imprimir" type="button">Imprimir</button></main>${variante === "boton_cubierto" ? '<div id="tapa"></div>' : ""}
<script>
const variante = ${JSON.stringify(variante)};
let guardados = null;
const preparar = () => { if (guardados !== null) return; guardados = [...document.querySelectorAll("main details")].map((d) => [d, d.open]);
  if (variante !== "sin_preparar") for (const [d] of guardados) d.open = true; };
const restaurar = () => { if (variante !== "sin_restaurar") for (const [d, o] of guardados ?? []) d.open = o; guardados = null; };
addEventListener("beforeprint", preparar); addEventListener("afterprint", restaurar);
document.getElementById("imprimir").addEventListener("click", () => { if (variante !== "sin_print") window.print(); });
</script></body></html>`;

async function navegador() {
  const { chromium } = await import("playwright");
  const servidor = createServer((pet, res) => {
    const v = new URL(pet.url, "http://127.0.0.1").searchParams.get("v") ?? "correcto";
    res.writeHead(200, { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" }); res.end(PAGINA(v));
  });
  await new Promise((ok) => servidor.listen(0, "127.0.0.1", ok));
  const BASE = `http://127.0.0.1:${servidor.address().port}/`;
  const nav = await chromium.launch(opciones.navegador ? { executablePath: opciones.navegador } : {});
  const plazo = Number(opciones.plazo ?? 3000);
  const sincrono = opciones.perfil === "afterprint-sincrono";
  const resultado = { navegador: { version: nav.version(), ejecutable_externo: Boolean(opciones.navegador), perfil: opciones.perfil ?? null, plataforma: process.platform }, plazo_ms: plazo, casos: [] };
  const pagina = async (variante) => {
    const contexto = await nav.newContext(); const p = await contexto.newPage();
    await p.addInitScript(instrumentarImpresion); await p.goto(BASE + "?v=" + variante); return { contexto, p };
  };
  const boton = (p) => p.locator("#imprimir");
  const caso = async (nombre, esperado, f) => {
    let r; try { r = await f(); } catch (e) { r = { estado: "excepcion", resultado: String(e).split("\n")[0] }; }
    resultado.casos.push({ nombre, esperado, obtenido: `${r.estado}:${r.resultado}`, ok: `${r.estado}:${r.resultado}` === esperado, detalle: r });
  };
  const clicEn = (variante, mixto = false) => async () => {
    const { contexto, p } = await pagina(variante);
    try { if (mixto) { const m = await prepararMixto(p, plazo); if (!m.aplicable) throw new Error("mixto no aplicable"); } return await observarClic(p, boton(p), plazo); }
    finally { await contexto.close(); }
  };
  const pdfEn = (variante, mixto = false) => async () => {
    const { contexto, p } = await pagina(variante);
    try { if (mixto) { const m = await prepararMixto(p, plazo); if (!m.aplicable) throw new Error("mixto no aplicable"); } return await observarPdf(p, plazo); }
    finally { await contexto.close(); }
  };
  const ausente = (r) => sincrono ? "aprobada:restaurado" : r;
  await caso("clic real, correcto, cerrados", ausente("no_evaluable:afterprint_no_emitido"), clicEn("correcto"));
  await caso("clic real, correcto, mixto", ausente("no_evaluable:afterprint_no_emitido"), clicEn("correcto", true));
  await caso("clic real, afterprint sin restaurar", sincrono ? "fallida:afterprint_sin_restaurar" : "no_evaluable:afterprint_no_emitido", clicEn("sin_restaurar"));
  await caso("clic real, beforeprint sin preparar", "fallida:beforeprint_sin_preparar", clicEn("sin_preparar"));
  await caso("clic real, botón sin print()", "fallida:print_no_invocado", clicEn("sin_print"));
  await caso("clic real, botón cubierto", "fallida:fallo_clic", clicEn("boton_cubierto"));
  await caso("clic real, segundo clic en la misma pestaña", ausente("no_evaluable:impresion_pendiente_en_pestana"), async () => {
    const { contexto, p } = await pagina("correcto");
    try { await observarClic(p, boton(p), plazo); return await observarClic(p, boton(p), plazo); } finally { await contexto.close(); }
  });
  await caso("clic real, tras navegar en la misma pestaña", ausente("no_evaluable:impresion_pendiente_en_pestana"), async () => {
    const { contexto, p } = await pagina("correcto");
    try { await observarClic(p, boton(p), plazo); await p.goto(BASE + "?v=correcto&otra=1"); return await observarClic(p, boton(p), plazo); } finally { await contexto.close(); }
  });
  await caso("page.pdf, correcto, cerrados", "aprobada:restaurado", pdfEn("correcto"));
  await caso("page.pdf, correcto, mixto", "aprobada:restaurado", pdfEn("correcto", true));
  await caso("page.pdf, afterprint sin restaurar", "fallida:afterprint_sin_restaurar", pdfEn("sin_restaurar"));
  await caso("page.pdf, beforeprint sin preparar", "fallida:beforeprint_sin_preparar", pdfEn("sin_preparar"));
  await caso("page.pdf, tras un clic en el mismo documento", sincrono ? "aprobada:restaurado" : "no_evaluable:ciclo_pendiente_en_documento", async () => {
    const { contexto, p } = await pagina("correcto");
    try { await observarClic(p, boton(p), plazo); return await observarPdf(p, plazo); } finally { await contexto.close(); }
  });
  await caso("page.pdf, tras navegar en la pestaña de un clic sin afterprint", "aprobada:restaurado", async () => {
    const { contexto, p } = await pagina("correcto");
    try { await observarClic(p, boton(p), plazo); await p.goto(BASE + "?v=correcto&otra=1"); return await observarPdf(p, plazo); } finally { await contexto.close(); }
  });
  await caso("control negativo sintético, correcto", "aprobada:discrimina", async () => {
    const { contexto, p } = await pagina("correcto"); try { return await controlNegativo(p, plazo); } finally { await contexto.close(); }
  });
  await caso("control negativo sintético, beforeprint sin preparar", "fallida:comparacion_no_discrimina", async () => {
    const { contexto, p } = await pagina("sin_preparar"); try { return await controlNegativo(p, plazo); } finally { await contexto.close(); }
  });
  // Contraste con la comprobación de la v1: estados iguales 50 ms después del clic.
  const v1 = (variante, segundo = false) => async () => {
    const { contexto, p } = await pagina(variante);
    try {
      if (segundo) { await boton(p).click(); await p.waitForTimeout(plazo); }
      const antes = await p.locator("main details").evaluateAll((xs) => xs.map((x) => x.open));
      await boton(p).click(); await p.waitForTimeout(50);
      const despues = await p.locator("main details").evaluateAll((xs) => xs.map((x) => x.open));
      const igual = JSON.stringify(antes) === JSON.stringify(despues);
      return { estado: "v1", resultado: igual ? "aprobaria" : "fallaria", antes, despues };
    } finally { await contexto.close(); }
  };
  await caso("contraste v1: correcto", sincrono ? "v1:aprobaria" : "v1:fallaria", v1("correcto"));
  await caso("contraste v1: beforeprint sin preparar (defecto)", "v1:aprobaria", v1("sin_preparar"));
  await caso("contraste v1: botón sin print() (defecto)", "v1:aprobaria", v1("sin_print"));
  await caso("contraste v1: segundo clic en la misma pestaña", "v1:aprobaria", v1("correcto", true));
  await nav.close(); servidor.close();
  return resultado;
}

if (opciones.navegador || opciones.perfil) informe.navegador = await navegador();
const todos = [...informe.unitarias, ...(informe.navegador?.casos ?? [])];
informe.ok = todos.every((c) => c.ok);
informe.resumen = { unitarias: informe.unitarias.length, unitarias_ok: informe.unitarias.filter((c) => c.ok).length,
  navegador: informe.navegador?.casos.length ?? 0, navegador_ok: informe.navegador?.casos.filter((c) => c.ok).length ?? 0 };
await writeFile(join(opciones.salida, "regresiones-impresion.json"), JSON.stringify(informe, null, 2) + "\n");
await writeFile(join(opciones.salida, "junit.xml"), `<?xml version="1.0" encoding="utf-8"?><testsuite name="F95-NAT-01-regresiones-${esc(informe.navegador?.navegador.perfil ?? "unitarias")}" tests="${todos.length}" failures="${todos.filter((c) => !c.ok).length}" errors="0" skipped="0">${todos.map((c) => casoJunit({ nombre: c.nombre, estado: c.ok ? "aprobada" : "fallida", motivo: `esperado ${c.esperado}; obtenido ${c.obtenido}` }, esc)).join("")}</testsuite>\n`);
for (const c of todos) if (!c.ok) console.log("FALLO", c.nombre, c.esperado ?? "", c.obtenido ?? c.error ?? "");
console.log(JSON.stringify({ ok: informe.ok, ...informe.resumen }));
process.exitCode = informe.ok ? 0 : 1;
