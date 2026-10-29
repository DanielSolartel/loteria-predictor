/** Recorrido focal de 9.4 sin interceptar HTTP: API/pasarela/SPA reales y datos sintéticos. */
import { createHash } from "node:crypto";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { chromium } from "playwright";

const opciones = { escenario: "normal", anchos: "360,390,1280" };
for (let i = 2; i < process.argv.length; i += 2) opciones[process.argv[i].replace(/^--/, "")] = process.argv[i + 1];
if (!opciones.base || !opciones.salida) throw new Error("faltan --base y --salida");
const BASE = opciones.base.replace(/\/$/, ""), ORIGEN = new URL(BASE).origin;
const ANCHOS = opciones.anchos.split(",").map(Number);
const JUEGOS = ["BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO"];
const GRUPOS = ["modelos", "carteras", "resultados"];
const TITULOS = { modelos: "Modelos registrados", carteras: "Carteras guardadas", resultados: "Resultados observados" };
const API = { modelos: "modelos-guardados", carteras: "carteras-guardadas", resultados: "resultados" };
await mkdir(join(opciones.salida, "capturas"), { recursive: true });
const ejecutable = opciones.navegador;
const navegador = await chromium.launch(ejecutable ? { executablePath: ejecutable } : {});
const resultados = {
  escenario: opciones.escenario, anchos_solicitados: ANCHOS,
  navegador: { nombre: "Chromium", version: navegador.version(), plataforma: process.platform, playwright: "1.56.1",
    ejecutable_externo: Boolean(ejecutable), identidad_sha256: ejecutable ? createHash("sha256").update(await readFile(ejecutable)).digest("hex") : null },
  transporte: "HTTP real al mismo origen; sin route(), fulfill() ni respuestas interceptadas",
  visitas: [], comprobaciones: [], fallos: [],
};
let volcadas = 0;
function comprobar(nombre, ok, detalle = {}) {
  resultados.comprobaciones.push({ nombre, ok, ...detalle });
  if (!ok) resultados.fallos.push({ donde: nombre, motivo: JSON.stringify(detalle).slice(0, 1000) });
}
function coste(ruta) {
  const u = new URL(ruta, BASE);
  return u.pathname === "/api/v1/juegos" ? 1 : u.pathname.endsWith("/resultados") ? 5 :
    /\/(modelos-guardados|carteras-guardadas)(\/|$)/.test(u.pathname) ? 2 : Infinity;
}
async function abrir(ancho) {
  const contexto = await navegador.newContext({ viewport: { width: ancho, height: 900 }, serviceWorkers: "block" });
  const pagina = await contexto.newPage();
  const registro = { peticiones: [], respuestas: [], errores: [], consola: [] };
  pagina.on("request", (r) => registro.peticiones.push(r.allHeaders().then((cabeceras) => ({ url: r.url(), metodo: r.method(), cabeceras }))));
  pagina.on("response", (r) => registro.respuestas.push((async () => {
    const cabeceras = await r.allHeaders();
    const cuerpo = await r.body().catch(() => Buffer.alloc(0));
    if (opciones.cuerpos) {
      const n = ++volcadas;
      await writeFile(join(opciones.cuerpos, `${n}.bin`), Buffer.concat([Buffer.from(JSON.stringify({ url: r.url(), estado: r.status(), cabeceras }) + "\n"), cuerpo]));
    }
    const u = new URL(r.url());
    let datos = null;
    if (u.pathname.startsWith("/api/v1/")) {
      try { datos = JSON.parse(cuerpo.toString("utf8")); } catch { /* La pantalla debe rechazar un cuerpo ilegible. */ }
    }
    return { ruta: u.pathname + u.search, estado: r.status(), cabeceras, datos };
  })().catch((e) => ({ error_captura: String(e) }))));
  pagina.on("pageerror", (e) => registro.errores.push(String(e)));
  pagina.on("console", (m) => { if (["error", "warning"].includes(m.type())) registro.consola.push({ tipo: m.type(), texto: m.text() }); });
  return { contexto, pagina, registro };
}
async function listo(pagina) {
  await pagina.waitForSelector("main h1", { timeout: 30000 });
  await pagina.waitForFunction(() => !document.querySelector("main [role=status]"), null, { timeout: 30000 });
  await pagina.waitForLoadState("networkidle");
}
async function fotografia(pagina) {
  return pagina.evaluate(async () => ({
    ventana: innerWidth, documento: document.documentElement.scrollWidth, cuerpo: document.body.scrollWidth,
    tablas: [...document.querySelectorAll(".tabla-desplazable")].map((t) => {
      const r = t.getBoundingClientRect();
      return { izquierda: r.left, derecha: r.right, foco: t.tabIndex === 0 && t.getAttribute("role") === "region" && Boolean(t.getAttribute("aria-label")) };
    }),
    almacenamiento: { local: localStorage.length, sesion: sessionStorage.length, cookies: document.cookie.length,
      indexedDB: (await indexedDB.databases()).length, caches: "caches" in self ? (await caches.keys()).length : 0 },
    colores: [...document.querySelectorAll("main .color-swatch")].map((c) => ({ texto: c.parentElement?.textContent?.trim(), oculta: c.getAttribute("aria-hidden") === "true" })),
  }));
}
async function visitar(ancho, juego, grupo, { clave = null, error = null, estado = null, vacio = false, consulta = "" } = {}) {
  const ruta = `/juegos/${juego}/${grupo}${clave ? `/${clave}` : ""}${consulta}`;
  const { contexto, pagina, registro } = await abrir(ancho);
  const v = { ancho, juego, grupo, ruta, ok: false, motivos: [] };
  try {
    await pagina.goto(BASE + ruta, { waitUntil: "networkidle" }); await listo(pagina);
    v.titulo = await pagina.locator("main h1").innerText();
    const esperado = clave ? (grupo === "modelos" ? "Modelo registrado" : "Cartera guardada") : TITULOS[grupo];
    if (v.titulo !== esperado) v.motivos.push(`título ${v.titulo}, esperado ${esperado}`);
    v.errores = await pagina.locator("main [role=alert][data-codigo]").evaluateAll((xs) => xs.map((x) => x.getAttribute("data-codigo")));
    if (error ? !v.errores.includes(error) : v.errores.length) v.motivos.push(`errores mostrados ${v.errores.join(",")}`);
    v.foto = await fotografia(pagina);
    if (v.foto.documento > ancho || v.foto.cuerpo > ancho) v.motivos.push(`desbordamiento ${v.foto.documento}/${ancho}`);
    if (v.foto.tablas.some((t) => !t.foco || t.izquierda < -1 || t.derecha > ancho + 1)) v.motivos.push("región de tabla fuera de ventana o sin foco/etiqueta");
    if (Object.values(v.foto.almacenamiento).some((n) => n !== 0)) v.motivos.push("almacenamiento de navegador no vacío");
    if (v.foto.colores.some((c) => !c.oculta || !c.texto)) v.motivos.push("par de color sin texto o muestra anunciada");
    if (!(await pagina.locator("footer").innerText()).includes("uso experimental no acreditado")) v.motivos.push("aviso experimental ausente");
    v.elementos = await pagina.locator("main tr[data-clave]").evaluateAll((xs) => xs.map((x) => ({ clave: x.getAttribute("data-clave"), estado: x.getAttribute("data-integridad") })));
    v.estados = await pagina.locator("main tr[data-estado]").evaluateAll((xs) => xs.map((x) => ({ estado: x.getAttribute("data-estado"), tipo: x.getAttribute("data-tipo"), aciertos: x.querySelector("[data-aciertos]")?.getAttribute("data-aciertos"), resultado: x.querySelector("[data-resultado]")?.getAttribute("data-resultado"), texto: x.textContent })));
    v.enlaces = await pagina.locator("main a[href]").evaluateAll((xs) => xs.map((a) => a.getAttribute("href")));
    if (vacio && await pagina.locator("main [data-estado=vacio]").count() === 0) v.motivos.push("ausencia no explícita");
    if (estado && await pagina.locator(`main [data-integridad="${estado}"]`).count() === 0) v.motivos.push(`estado ${estado} ausente`);
    if (!error && clave && await pagina.locator(`[data-${grupo === "modelos" ? "modelo" : "cartera"}="${clave}"]`).count() !== 1) v.motivos.push("identidad de detalle no coincide");
    if (opciones.escenario === "normal" && grupo === "resultados") {
      if (!v.estados.some((e) => e.estado === "pendiente") || !v.estados.some((e) => e.estado === "incluido")) v.motivos.push("faltan observado/pendiente sintéticos");
      if (v.estados.some((e) => e.estado === "pendiente" && (e.aciertos !== "ausente" || e.resultado !== "pendiente"))) v.motivos.push("pendiente presentado como aciertos observados");
    }
    const nombre = `${process.platform}-${ancho}-${juego}-${grupo}${clave ? "-detalle" : ""}${estado ? `-${estado}` : ""}${error ? `-${error}` : ""}.png`;
    await pagina.screenshot({ path: join(opciones.salida, "capturas", nombre), fullPage: true }); v.captura = nombre;
  } catch (e) { v.motivos.push(String(e).split("\n")[0]); }
  const peticiones = await Promise.all(registro.peticiones), respuestas = await Promise.all(registro.respuestas);
  v.peticiones_api = peticiones.filter((p) => new URL(p.url).pathname.startsWith("/api/v1/")).map((p) => new URL(p.url).pathname + new URL(p.url).search);
  v.fichas_automaticas = v.peticiones_api.reduce((n, p) => n + coste(p), 0);
  if (v.fichas_automaticas > 6 || v.peticiones_api.filter((p) => p === "/api/v1/juegos").length !== 1 || v.peticiones_api.length !== 2) v.motivos.push(`presupuesto frío inválido: ${v.fichas_automaticas}, ${v.peticiones_api.join(",")}`);
  for (const p of peticiones) {
    if (new URL(p.url).origin !== ORIGEN || p.metodo !== "GET") v.motivos.push("tráfico externo o método distinto de GET");
    if (Object.keys(p.cabeceras).some((k) => ["x-api-key", "authorization"].includes(k.toLowerCase()))) v.motivos.push("credencial en navegador");
  }
  v.respuestas_api = respuestas.filter((r) => r.ruta?.startsWith("/api/v1/")).map(({ datos, ...r }) => r);
  if (v.respuestas_api.some((r) => r.cabeceras["cache-control"] !== "no-store" || !r.cabeceras["x-request-id"])) v.motivos.push("cabeceras de lectura ausentes");
  const fallosConsola = registro.consola.filter((c) => c.tipo === "error" && !(error && /status of (4|5)\d\d/.test(c.texto)));
  if (registro.errores.length || fallosConsola.length) v.motivos.push(`consola: ${JSON.stringify([...registro.errores, ...fallosConsola]).slice(0, 300)}`);
  v.ok = v.motivos.length === 0;
  if (!v.ok) resultados.fallos.push({ donde: ruta, ancho, motivo: v.motivos.join("; ") });
  resultados.visitas.push(v); await contexto.close(); return v;
}
async function historial() {
  const { contexto, pagina } = await abrir(390);
  await pagina.goto(BASE + "/juegos/BALOTO/modelos?por_pagina=1", { waitUntil: "networkidle" }); await listo(pagina);
  const inicial = await pagina.locator("main tr[data-clave]").getAttribute("data-clave");
  await pagina.getByRole("link", { name: "Página siguiente", exact: true }).click(); await listo(pagina);
  const segunda = await pagina.locator("main tr[data-clave]").getAttribute("data-clave");
  const url2 = new URL(pagina.url()).search;
  await pagina.goBack(); await listo(pagina); const vuelta = await pagina.locator("main tr[data-clave]").getAttribute("data-clave");
  await pagina.goForward(); await listo(pagina); const avance = await pagina.locator("main tr[data-clave]").getAttribute("data-clave");
  await pagina.reload(); await listo(pagina); const recarga = await pagina.locator("main tr[data-clave]").getAttribute("data-clave");
  comprobar("enlace-directo-paginacion-atras-adelante-recarga", inicial !== segunda && vuelta === inicial && avance === segunda && recarga === segunda && url2.includes("pagina=2"), { inicial, segunda, vuelta, avance, recarga, url2 });
  await pagina.getByLabel("Identificador de modelo", { exact: true }).fill("modelo_inexistente");
  await pagina.getByRole("button", { name: "Aplicar filtros", exact: true }).click(); await listo(pagina);
  const vacio = await pagina.locator("main [data-estado=vacio]").count() > 0;
  await pagina.reload(); await listo(pagina);
  comprobar("filtro-url-recarga-ausencia", vacio && new URL(pagina.url()).searchParams.get("modelo") === "modelo_inexistente" && await pagina.locator("main [data-estado=vacio]").count() > 0);
  await contexto.close();
}
async function teclado() {
  for (const ancho of ANCHOS) {
    const { contexto, pagina } = await abrir(ancho);
    await pagina.goto(BASE + "/juegos/COLORLOTO/resultados", { waitUntil: "networkidle" }); await listo(pagina);
    await pagina.keyboard.press("Tab"); const primero = await pagina.evaluate(() => document.activeElement?.textContent?.trim());
    await pagina.keyboard.press("Enter"); const destino = await pagina.evaluate(() => document.activeElement?.id);
    const region = pagina.getByRole("region", { name: "Emisiones y resultados", exact: true }); await region.focus();
    const foco = await region.evaluate((e) => e === document.activeElement);
    comprobar(`teclado-foco-tabla-${ancho}`, primero === "Saltar al contenido" && destino === "contenido" && foco, { primero, destino, foco });
    await contexto.close();
  }
}
async function cuota() {
  const { contexto, pagina, registro } = await abrir(1280);
  await pagina.goto(BASE + "/juegos/BALOTO/modelos", { waitUntil: "networkidle" }); await listo(pagina);
  const rutas = () => Promise.all(registro.peticiones).then((xs) => xs.filter((p) => new URL(p.url).pathname.startsWith("/api/v1/")).map((p) => new URL(p.url).pathname + new URL(p.url).search));
  const automaticas = await rutas();
  await pagina.locator("main tr[data-clave] a").first().click(); await listo(pagina);
  await pagina.locator("nav[aria-label^='Secciones'] a[href='/juegos/BALOTO/resultados']").click();
  await pagina.waitForSelector("main [role=alert][data-codigo=limite_excedido]", { timeout: 30000 }); await pagina.waitForLoadState("networkidle");
  const alerta = pagina.locator("main [role=alert][data-codigo=limite_excedido]");
  const texto = await alerta.innerText(); const boton = alerta.getByRole("button", { name: "Reintentar", exact: true });
  const deshabilitado = await boton.isDisabled();
  const antes = (await rutas()).filter((x) => x.endsWith("/resultados")).length;
  await pagina.waitForTimeout(1200);
  const sinAccion = (await rutas()).filter((x) => x.endsWith("/resultados")).length;
  await pagina.screenshot({ path: join(opciones.salida, "capturas", `chromium-${process.platform}-1280-cuota-429.png`), fullPage: true });
  await boton.waitFor({ state: "visible" }); await pagina.waitForFunction(() => !document.querySelector("main [role=alert] button")?.disabled, null, { timeout: 75000 });
  const trasEspera = (await rutas()).filter((x) => x.endsWith("/resultados")).length;
  await boton.click(); await listo(pagina);
  const trasManual = (await rutas()).filter((x) => x.endsWith("/resultados")).length;
  const contenido = await pagina.locator("main tr[data-estado=pendiente]").count() > 0;
  const respuestas = await Promise.all(registro.respuestas);
  const r429 = respuestas.find((r) => r.estado === 429);
  comprobar("cuota-fria-cabe-seis-429-sin-bucle-reintento-manual", automaticas.length === 2 && automaticas.reduce((n, p) => n + coste(p), 0) === 3 && deshabilitado && /Podrás reintentar en \d+ s/.test(texto) && antes === 1 && sinAccion === 1 && trasEspera === 1 && trasManual === 2 && contenido && Number(r429?.cabeceras?.["retry-after"]) > 0,
    { automaticas, fichas_automaticas: 3, boton_deshabilitado: deshabilitado, antes, sinAccion, trasEspera, trasManual, contenido, retry_after: r429?.cabeceras?.["retry-after"] });
  await contexto.close();
}
try {
  if (opciones.escenario === "normal") {
    for (const ancho of ANCHOS) for (const juego of JUEGOS) for (const grupo of GRUPOS) {
      const v = await visitar(ancho, juego, grupo);
      if (grupo !== "resultados" && v.elementos?.length) await visitar(ancho, juego, grupo, { clave: v.elementos[0].clave });
    }
    await historial(); await teclado();
  } else if (opciones.escenario === "vacio") {
    for (const ancho of ANCHOS) for (const grupo of GRUPOS) await visitar(ancho, "BALOTO", grupo, { vacio: true });
  } else if (opciones.escenario === "alterado") {
    for (const ancho of ANCHOS) for (const [juego, grupo] of [["BALOTO", "modelos"], ["COLORLOTO", "carteras"]]) {
      const v = await visitar(ancho, juego, grupo, { estado: "alterado" });
      const fila = v.elementos?.find((x) => x.estado === "alterado");
      comprobar(`alterado-presente-${ancho}-${grupo}`, Boolean(fila));
      if (fila) await visitar(ancho, juego, grupo, { clave: fila.clave, error: "alterado" });
    }
  } else if (opciones.escenario === "incompatible") {
    for (const ancho of ANCHOS) {
      const v = await visitar(ancho, "BALOTO", "modelos", { estado: "incompatible" });
      const fila = v.elementos?.find((x) => x.estado === "incompatible");
      comprobar(`incompatible-presente-${ancho}`, Boolean(fila));
      if (fila) await visitar(ancho, "BALOTO", "modelos", { clave: fila.clave, estado: "incompatible" });
    }
  } else if (opciones.escenario === "cuota") await cuota();
  else throw new Error("escenario desconocido");
} catch (e) { resultados.fallos.push({ donde: "recorrido", motivo: String(e) }); }
finally {
  await navegador.close();
  resultados.ok = resultados.fallos.length === 0;
  resultados.resumen = { visitas: resultados.visitas.length, comprobaciones: resultados.comprobaciones.length, fallos: resultados.fallos.length, capturas: resultados.visitas.filter((v) => v.captura).length + (opciones.escenario === "cuota" ? 1 : 0) };
  await writeFile(join(opciones.salida, "resultados.json"), JSON.stringify(resultados, null, 2) + "\n");
  const esc = (s) => String(s).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll('"', "&quot;");
  const casos = [...resultados.visitas.map((v) => ({ nombre: `${v.ancho} ${v.ruta}`, ok: v.ok, motivo: v.motivos.join("; ") })), ...resultados.comprobaciones.map((c) => ({ nombre: c.nombre, ok: c.ok, motivo: JSON.stringify(c) }))];
  if (resultados.fallos.some((f) => f.donde === "recorrido")) casos.push({ nombre: "recorrido", ok: false, motivo: resultados.fallos.find((f) => f.donde === "recorrido").motivo });
  await writeFile(join(opciones.salida, "junit.xml"), `<?xml version="1.0" encoding="utf-8"?><testsuite name="Fase9.4-${esc(opciones.escenario)}-${esc(process.platform)}" tests="${casos.length}" failures="${casos.filter((c) => !c.ok).length}" errors="0" skipped="0">${casos.map((c) => `<testcase name="${esc(c.nombre)}">${c.ok ? "" : `<failure message="${esc(c.motivo)}"/>`}</testcase>`).join("")}</testsuite>\n`);
  console.log(JSON.stringify({ ok: resultados.ok, ...resultados.resumen }));
  process.exitCode = resultados.ok ? 0 : 1;
}
