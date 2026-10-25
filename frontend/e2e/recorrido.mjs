/**
 * Recorrido de Chromium (Playwright) sobre la SPA servida por la pasarela (o por
 * Vite en modo desarrollo). Lo lanza `backend/tests/recorrido_fase9.py`, que
 * arranca los procesos con datos sinteticos.
 *
 * Por cada ancho (360, 390 y 1280 px) visita todas las pantallas de los cuatro
 * juegos, todas las metricas que enlaza el panel (segun el indice real) y los
 * detalles de sorteos, predicciones y simulaciones. Comprueba: que no hay
 * desbordamiento de pagina (las tablas se desplazan dentro de su region), los
 * errores de consola, que el trafico es solo del mismo origen y sin
 * `X-API-Key`, que el almacenamiento queda vacio, el aviso experimental y, en
 * pantallas concretas, el teclado y el foco, la navegacion atras/adelante y el
 * numero de llamadas. Escribe `resultados.json` y capturas etiquetadas
 * Chromium/Linux.
 *
 * Uso: node e2e/recorrido.mjs --base URL --escenario normal --salida DIR [--anchos 360,390,1280] [--cuerpos DIR]
 */
import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { chromium } from "playwright";

function argumentos() {
  const salida = { anchos: "360,390,1280", escenario: "normal" };
  const lista = process.argv.slice(2);
  for (let i = 0; i < lista.length; i += 2) {
    salida[lista[i].replace(/^--/, "")] = lista[i + 1];
  }
  if (!salida.base || !salida.salida) {
    throw new Error("faltan --base y --salida");
  }
  return salida;
}

const opciones = argumentos();
const BASE = opciones.base.replace(/\/$/, "");
const ORIGEN = new URL(BASE).origin;
const ANCHOS = opciones.anchos.split(",").map(Number);
const JUEGOS = ["BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO"];
const METRICAS_ESPERADAS = { BALOTO: 18, BALOTO_REVANCHA: 18, MILOTO: 11, COLORLOTO: 5 };
const PLATAFORMA = process.platform === "linux" ? "linux" : process.platform;
const CAPTURAS = new Set(["inicio", "ficha-BALOTO", "sorteos-COLORLOTO", "metrica-BALOTO-correlaciones",
  "metrica-COLORLOTO-pruebas-uniformidad", "prediccion-MILOTO", "prediccion-COLORLOTO", "servicio",
  "estadisticas-COLORLOTO", "sorteo-COLORLOTO"]);

await mkdir(join(opciones.salida, "capturas"), { recursive: true });
const navegador = await chromium.launch();
const resultados = {
  escenario: opciones.escenario,
  navegador: { nombre: "Chromium", version: navegador.version(), plataforma: PLATAFORMA, playwright: "1.56.1" },
  base_origen: ORIGEN,
  visitas: [],
  comprobaciones: [],
  metricas: {},
};
const fallos = [];
let volcadas = 0;

function fallo(donde, motivo) {
  fallos.push({ donde, motivo });
}

async function nuevaPestana(ancho) {
  const contexto = await navegador.newContext({ viewport: { width: ancho, height: 900 }, serviceWorkers: "block" });
  const pagina = await contexto.newPage();
  const registro = { peticiones: [], consola: [], errores: [], respuestas: [] };
  if (opciones.cuerpos) {
    // Volcado temporal de cada respuesta (cabeceras y cuerpo) para que el orquestador busque el canario.
    pagina.on("response", (r) => {
      registro.respuestas.push(
        (async () => {
          const cabeceras = await r.allHeaders();
          const cuerpo = await r.body().catch(() => Buffer.alloc(0));
          volcadas += 1;
          const meta = Buffer.from(`${JSON.stringify({ url: r.url(), estado: r.status(), cabeceras })}\n`);
          await writeFile(join(opciones.cuerpos, `${volcadas}.bin`), Buffer.concat([meta, cuerpo]));
        })().catch(() => undefined),
      );
    });
  }
  pagina.on("request", (r) => {
    registro.peticiones.push(
      r.allHeaders().then((cabeceras) => ({ url: r.url(), metodo: r.method(), cabeceras })),
    );
  });
  pagina.on("console", (m) => {
    if (m.type() === "error" || m.type() === "warning") {
      registro.consola.push({ tipo: m.type(), texto: m.text() });
    }
  });
  pagina.on("pageerror", (e) => registro.errores.push(String(e)));
  return { contexto, pagina, registro };
}

async function esperarContenido(pagina) {
  await pagina.waitForSelector("main h1", { timeout: 30000 });
  await pagina.waitForFunction(() => !document.querySelector("main [role=status]"), null, { timeout: 30000 });
}

async function geometria(pagina) {
  return pagina.evaluate(() => {
    const ventana = window.innerWidth;
    const tablas = [...document.querySelectorAll(".tabla-desplazable")].map((t) => {
      const r = t.getBoundingClientRect();
      return { izquierda: Math.round(r.left), derecha: Math.round(r.right), desplazaInterno: t.scrollWidth > t.clientWidth + 1, foco: t.tabIndex === 0 && t.getAttribute("role") === "region" && Boolean(t.getAttribute("aria-label")) };
    });
    return { ventana, documento: document.documentElement.scrollWidth, cuerpo: document.body.scrollWidth, tablas };
  });
}

async function almacenamiento(pagina) {
  return pagina.evaluate(async () => ({
    localStorage: localStorage.length,
    sessionStorage: sessionStorage.length,
    cookies: document.cookie.length,
    indexedDB: (await indexedDB.databases()).length,
    caches: "caches" in self ? (await caches.keys()).length : 0,
  }));
}

/** Visita `ruta` en una pestaña nueva (carga completa) y registra sus comprobaciones. */
async function visitar(ancho, nombre, ruta, { esperarError = null, admitidos = [], captura = CAPTURAS.has(nombre) } = {}) {
  const permitidos = new Set([...(esperarError ? [esperarError] : []), ...admitidos]);
  const { contexto, pagina, registro } = await nuevaPestana(ancho);
  const visita = { ancho, nombre, ruta, ok: true, motivos: [] };
  try {
    await pagina.goto(BASE + ruta, { waitUntil: "networkidle" });
    await esperarContenido(pagina);
    await pagina.waitForLoadState("networkidle");
    visita.titulo = await pagina.locator("main h1").first().innerText();
    const alerta = pagina.locator("main [role=alert][data-codigo]");
    visita.errores_mostrados = await alerta.evaluateAll((xs) => xs.map((x) => x.getAttribute("data-codigo")));
    const inesperados = visita.errores_mostrados.filter((c) => !permitidos.has(c));
    if (inesperados.length > 0) {
      visita.motivos.push(`error inesperado: ${inesperados.join(",")}`);
    }
    if (esperarError !== null && !visita.errores_mostrados.includes(esperarError)) {
      visita.motivos.push(`se esperaba ${esperarError}, se vio ${visita.errores_mostrados.join(",") || "nada"}`);
    }
    visita.geometria = await geometria(pagina);
    const g = visita.geometria;
    if (g.documento > g.ventana || g.cuerpo > g.ventana) {
      visita.motivos.push(`desbordamiento de pagina: ${g.documento}px > ${g.ventana}px`);
    }
    for (const t of g.tablas) {
      if (t.derecha > g.ventana + 1 || t.izquierda < -1) {
        visita.motivos.push(`tabla fuera de la ventana (${t.izquierda}..${t.derecha})`);
      }
      if (!t.foco) {
        visita.motivos.push("region de tabla sin foco o sin etiqueta");
      }
    }
    const pie = await pagina.locator("footer").innerText();
    if (!pie.includes("uso experimental no acreditado")) {
      visita.motivos.push("falta el aviso experimental del pie");
    }
    visita.almacenamiento = await almacenamiento(pagina);
    if (Object.values(visita.almacenamiento).some((n) => n !== 0)) {
      visita.motivos.push(`almacenamiento no vacio: ${JSON.stringify(visita.almacenamiento)}`);
    }
    if (captura) {
      const archivo = `chromium-${PLATAFORMA}-${ancho}-${nombre}.png`;
      await pagina.screenshot({ path: join(opciones.salida, "capturas", archivo), fullPage: true });
      visita.captura = archivo;
    }
    visita.marcas = await pagina.evaluate(() =>
      Object.fromEntries(
        ["prediccion", "frescura", "observado", "frente", "integridad", "configuracion", "estado", "base", "salud", "metrica"]
          .map((k) => [k, [...document.querySelectorAll(`[data-${k}]`)].map((e) => e.getAttribute(`data-${k}`))])
          .filter(([, v]) => v.length > 0),
      ),
    );
    visita.enlaces = await pagina.evaluate(() =>
      [...document.querySelectorAll("main a[href]")].map((a) => a.getAttribute("href")),
    );
  } catch (error) {
    visita.motivos.push(`excepcion: ${String(error).split("\n")[0]}`);
  }
  const peticiones = await Promise.all(registro.peticiones);
  await Promise.all(registro.respuestas);
  visita.peticiones_api = peticiones.filter((p) => new URL(p.url).pathname.startsWith("/api/v1/")).map((p) => new URL(p.url).pathname + new URL(p.url).search);
  visita.peticiones_total = peticiones.length;
  for (const p of peticiones) {
    if (new URL(p.url).origin !== ORIGEN && !p.url.startsWith("data:")) {
      visita.motivos.push(`peticion a otro origen: ${new URL(p.url).origin}`);
    }
    if (Object.keys(p.cabeceras).some((k) => k.toLowerCase() === "x-api-key" || k.toLowerCase() === "authorization")) {
      visita.motivos.push("peticion con credencial");
    }
    if (p.metodo !== "GET") {
      visita.motivos.push(`metodo ${p.metodo}`);
    }
  }
  // Chromium anota en la consola cada respuesta 4xx/5xx; solo se admite si la pantalla muestra ese error esperado.
  const errorPermitido = (visita.errores_mostrados ?? []).some((c) => permitidos.has(c));
  visita.consola = registro.consola.filter((c) => !(errorPermitido && /status of (4|5)\d\d/.test(c.texto)));
  if (visita.consola.some((c) => c.tipo === "error") || registro.errores.length > 0) {
    visita.motivos.push(`errores de consola: ${JSON.stringify([...visita.consola, ...registro.errores]).slice(0, 300)}`);
  }
  visita.ok = visita.motivos.length === 0;
  if (!visita.ok) {
    fallo(`${ancho} ${ruta}`, visita.motivos.join("; "));
  }
  resultados.visitas.push(visita);
  await contexto.close();
  return visita;
}

function comprobar(nombre, ok, detalle = {}) {
  resultados.comprobaciones.push({ nombre, ok, ...detalle });
  if (!ok) {
    fallo(nombre, JSON.stringify(detalle).slice(0, 400));
  }
}

async function teclado(ancho) {
  const { contexto, pagina } = await nuevaPestana(ancho);
  await pagina.goto(`${BASE}/`, { waitUntil: "networkidle" });
  await esperarContenido(pagina);
  await pagina.keyboard.press("Tab");
  const primero = await pagina.evaluate(() => ({ texto: document.activeElement?.textContent?.trim(), clase: document.activeElement?.className }));
  await pagina.keyboard.press("Enter");
  const tras = await pagina.evaluate(() => document.activeElement?.id);
  const recorrido = [];
  for (let i = 0; i < 6; i += 1) {
    await pagina.keyboard.press("Tab");
    recorrido.push(
      await pagina.evaluate(() => {
        const e = document.activeElement;
        const estilo = e ? getComputedStyle(e) : null;
        return {
          etiqueta: e?.tagName,
          texto: e?.textContent?.trim().slice(0, 40),
          visible: Boolean(estilo && (estilo.outlineStyle !== "none" || estilo.boxShadow !== "none")),
        };
      }),
    );
  }
  comprobar(`teclado-${ancho}`, primero.texto === "Saltar al contenido" && tras === "contenido" && recorrido.every((r) => r.etiqueta && r.visible), {
    primero,
    tras_enter: tras,
    recorrido,
  });
  // Region de tabla alcanzable con el teclado (pantalla de sorteos).
  await pagina.goto(`${BASE}/juegos/BALOTO/sorteos`, { waitUntil: "networkidle" });
  await esperarContenido(pagina);
  await pagina.locator(".tabla-desplazable").first().focus();
  const region = await pagina.evaluate(() => document.activeElement?.getAttribute("aria-label"));
  comprobar(`tabla-enfocable-${ancho}`, region === "Sorteos", { region });
  await contexto.close();
}

/** Espera a que `selector` exista, no haya nada cargando y su texto sea `igual` (o distinto de `distinto`). */
async function esperarTexto(pagina, selector, { igual, distinto } = {}) {
  await pagina.waitForFunction(
    ([s, i, d]) => {
      const e = document.querySelector(s);
      if (!e || document.querySelector("main [role=status]")) {
        return false;
      }
      return i !== null ? e.textContent === i : d !== null ? e.textContent !== d : true;
    },
    [selector, igual ?? null, distinto ?? null],
    { timeout: 30000 },
  );
  return pagina.locator(selector).first().evaluate((e) => e.textContent);
}

async function historialYRecarga() {
  const { contexto, pagina, registro } = await nuevaPestana(1280);
  const RESUMEN = "main p[aria-live]";
  const PRIMERA = "main tbody tr td a";
  await pagina.goto(`${BASE}/juegos/BALOTO/sorteos`, { waitUntil: "networkidle" });
  const totalSinFiltro = await esperarTexto(pagina, RESUMEN);
  await pagina.fill("#filtro-numero_desde", "2130");
  await pagina.selectOption("#filtro-orden", "numero_asc");
  await pagina.fill("#filtro-por_pagina", "5");
  await pagina.click("form[aria-label='Filtros de sorteos'] button[type=submit]");
  await pagina.waitForURL(/numero_desde=2130/);
  const conFiltro = await esperarTexto(pagina, RESUMEN, { distinto: totalSinFiltro });
  const primeraFila = await esperarTexto(pagina, PRIMERA);
  await pagina.click("nav[aria-label='Paginación'] a[aria-label='Página siguiente']");
  await pagina.waitForURL(/pagina=2/);
  const segunda = await esperarTexto(pagina, PRIMERA, { distinto: primeraFila });
  const urlPagina = pagina.url();
  await pagina.goBack();
  await pagina.waitForURL((u) => !/pagina=2/.test(u.toString()));
  const primeraTrasAtras = await esperarTexto(pagina, PRIMERA, { igual: primeraFila });
  const trasAtras = pagina.url();
  await pagina.goBack();
  await pagina.waitForURL((u) => !/numero_desde/.test(u.toString()));
  const sinFiltro = await esperarTexto(pagina, RESUMEN, { igual: totalSinFiltro });
  const urlInicial = pagina.url();
  await pagina.goForward();
  await pagina.waitForURL(/numero_desde=2130/);
  await esperarTexto(pagina, RESUMEN, { igual: conFiltro });
  const trasAdelante = pagina.url();
  await pagina.reload({ waitUntil: "networkidle" });
  const conFiltroTrasRecarga = await esperarTexto(pagina, RESUMEN, { igual: conFiltro });
  const valorTrasRecarga = await pagina.inputValue("#filtro-numero_desde");
  comprobar(
    "filtros-en-la-url",
    /numero_desde=2130/.test(trasAdelante) && !/numero_desde/.test(urlInicial) && valorTrasRecarga === "2130" &&
      conFiltroTrasRecarga === conFiltro && sinFiltro === totalSinFiltro && primeraFila === "2130" && segunda === "2135" &&
      primeraTrasAtras === primeraFila && !/pagina=2/.test(trasAtras),
    { totalSinFiltro, conFiltro, primeraFila, segunda, urlPagina, trasAtras, urlInicial, trasAdelante, valorTrasRecarga },
  );
  // Acceso directo: la misma URL en una pestaña nueva da la misma vista.
  const directa = await nuevaPestana(1280);
  await directa.pagina.goto(trasAdelante, { waitUntil: "networkidle" });
  const textoDirecto = await esperarTexto(directa.pagina, RESUMEN);
  comprobar("acceso-directo-con-filtros", textoDirecto === conFiltro, { textoDirecto });
  await directa.contexto.close();
  const peticiones = await Promise.all(registro.peticiones);
  resultados.comprobaciones.push({ nombre: "peticiones-historial", ok: true, api: peticiones.filter((p) => p.url.includes("/api/v1/")).map((p) => new URL(p.url).pathname + new URL(p.url).search) });
  await contexto.close();
}

/** Navegacion dentro de la SPA: `/juegos` se pide una vez y se reutiliza en memoria. */
async function llamadasEnNavegacion() {
  const { contexto, pagina, registro } = await nuevaPestana(1280);
  await pagina.goto(`${BASE}/`, { waitUntil: "networkidle" });
  await esperarContenido(pagina);
  await pagina.click("main a[href='/juegos/MILOTO']");
  await pagina.waitForURL(/\/juegos\/MILOTO$/);
  await pagina.waitForSelector("main [data-frescura]", { timeout: 30000 });
  await pagina.waitForLoadState("networkidle");
  await pagina.click("nav[aria-label^='Secciones'] a[href='/juegos/MILOTO/sorteos']");
  await pagina.waitForURL(/\/juegos\/MILOTO\/sorteos$/);
  await pagina.waitForSelector("main [role=region][aria-label='Sorteos']", { timeout: 30000 });
  await pagina.waitForLoadState("networkidle");
  await pagina.goBack();
  await pagina.waitForURL(/\/juegos\/MILOTO$/);
  await pagina.waitForSelector("main [data-frescura]", { timeout: 30000 });
  await pagina.waitForLoadState("networkidle");
  const api = (await Promise.all(registro.peticiones)).filter((p) => p.url.includes("/api/v1/")).map((p) => new URL(p.url).pathname + new URL(p.url).search);
  const cuenta = (r) => api.filter((x) => x === r).length;
  comprobar("llamadas-navegacion-spa", cuenta("/api/v1/juegos") === 1 && cuenta("/api/v1/juegos/MILOTO") === 2 && cuenta("/api/v1/juegos/MILOTO/sorteos") === 1, { api });
  await contexto.close();
}

async function recorridoNormal() {
  for (const ancho of ANCHOS) {
    await visitar(ancho, "inicio", "/");
    await visitar(ancho, "servicio", "/servicio");
    await visitar(ancho, "no-encontrada", "/no-existe");
    await visitar(ancho, "juego-inexistente", "/juegos/QUINELA", { esperarError: "no_encontrado" });
    await visitar(ancho, "parametro-no-valido", "/juegos/BALOTO/sorteos?pagina=0", { esperarError: "parametro_no_valido" });
    for (const juego of JUEGOS) {
      await visitar(ancho, `ficha-${juego}`, `/juegos/${juego}`);
      await visitar(ancho, `ficha-corte-${juego}`, `/juegos/${juego}?hasta_numero_sorteo=1`);
      const sorteos = await visitar(ancho, `sorteos-${juego}`, `/juegos/${juego}/sorteos`);
      await visitar(ancho, `sorteos-vacio-${juego}`, `/juegos/${juego}/sorteos?numero_desde=999999`);
      const detalle = (sorteos.enlaces ?? []).find((h) => /\/sorteos\/\d+$/.test(h));
      if (detalle) {
        await visitar(ancho, `sorteo-${juego}`, detalle);
      } else {
        fallo(`sorteos-${juego}`, "sin enlace de detalle");
      }
      const panel = await visitar(ancho, `estadisticas-${juego}`, `/juegos/${juego}/estadisticas`);
      const metricas = (panel.enlaces ?? []).filter((h) => new RegExp(`^/juegos/${juego}/estadisticas/[a-z0-9-]+$`).test(h));
      if (ancho === ANCHOS[ANCHOS.length - 1]) {
        resultados.metricas[juego] = metricas.map((h) => h.split("/").pop());
      }
      comprobar(`metricas-${juego}-${ancho}`, metricas.length === METRICAS_ESPERADAS[juego], { enlazadas: metricas.length, esperadas: METRICAS_ESPERADAS[juego] });
      for (const m of metricas) {
        await visitar(ancho, `metrica-${juego}-${m.split("/").pop()}`, m);
      }
      const prediccion = await visitar(ancho, `prediccion-${juego}`, `/juegos/${juego}/prediccion`);
      const clave = prediccion.marcas?.prediccion?.[0];
      if (clave) {  // seleccion explicita en el historial (la URL lleva la clave)
        await visitar(ancho, `prediccion-historial-${juego}`, `/juegos/${juego}/prediccion?cartera=${clave}`);
      }
      if (juego === "BALOTO") {
        await visitar(ancho, "prediccion-inexistente", `/juegos/${juego}/prediccion?cartera=${"0".repeat(64)}`, { esperarError: "no_encontrado" });
      }
      const simulaciones = await visitar(ancho, `simulaciones-${juego}`, `/juegos/${juego}/simulaciones`);
      const detalles = (simulaciones.enlaces ?? []).filter((x) => x.startsWith("/simulaciones/"));
      for (const [i, h] of detalles.entries()) {
        const v = await visitar(ancho, `simulacion-${juego}-${i + 1}`, h, { admitidos: ["alterado"], captura: juego === "COLORLOTO" });
        v.nombre = (v.errores_mostrados ?? []).includes("alterado") ? "simulacion-alterada" : "simulacion-verificada";
      }
    }
    await teclado(ancho);
  }
  await historialYRecarga();
  await llamadasEnNavegacion();
  // Estados informados que el escenario sintetico debe mostrar.
  const ver = (n) => resultados.visitas.filter((v) => v.nombre === n);
  comprobar("simulacion-alterada-vista", ver("simulacion-alterada").length === ANCHOS.length && ver("simulacion-alterada").every((v) => v.ok));
  comprobar("simulacion-verificada-vista", ver("simulacion-verificada").length >= ANCHOS.length);
}

async function recorridoCuota() {
  const { contexto, pagina, registro } = await nuevaPestana(1280);
  await pagina.goto(`${BASE}/juegos/BALOTO`, { waitUntil: "networkidle" });
  await esperarContenido(pagina);
  await pagina.click("nav[aria-label^='Secciones'] a[href='/juegos/BALOTO/sorteos']");
  await pagina.waitForSelector("main [role=alert][data-codigo=limite_excedido]", { timeout: 30000 });
  const texto = await pagina.locator("main [role=alert]").innerText();
  const deshabilitado = await pagina.locator("main [role=alert] button").isDisabled();
  await pagina.screenshot({ path: join(opciones.salida, "capturas", `chromium-${PLATAFORMA}-1280-cuota-429.png`), fullPage: true });
  const antes = (await Promise.all(registro.peticiones)).filter((p) => p.url.includes("/sorteos")).length;
  await pagina.waitForFunction(() => !document.querySelector("main [role=alert] button")?.hasAttribute("disabled"), null, { timeout: 90000 });
  const durante = (await Promise.all(registro.peticiones)).filter((p) => p.url.includes("/sorteos")).length;
  await pagina.click("main [role=alert] button");
  await pagina.waitForFunction(() => !document.querySelector("main [role=status]"), null, { timeout: 30000 });
  const despues = await pagina.evaluate(() => (document.querySelector("main [role=alert]")?.getAttribute("data-codigo") ?? "contenido"));
  comprobar("cuota-429", /Podrás reintentar en \d+ s/.test(texto) && deshabilitado && antes === 1 && durante === 1 && /otras pestañas/.test(texto), {
    texto: texto.slice(0, 400),
    boton_deshabilitado: deshabilitado,
    peticiones_de_sorteos_antes_de_esperar: antes,
    peticiones_durante_la_espera: durante,
    tras_reintento_manual: despues,
  });
  await contexto.close();
}

async function recorridoErrorUnico(codigo) {
  for (const ancho of ANCHOS) {
    await visitar(ancho, `inicio-${codigo}`, "/", { esperarError: codigo, captura: ancho === 1280 });
  }
  const { contexto, pagina, registro } = await nuevaPestana(1280);
  await pagina.goto(`${BASE}/juegos/BALOTO`, { waitUntil: "networkidle" });
  await esperarContenido(pagina);
  const antes = (await Promise.all(registro.peticiones)).filter((p) => p.url.includes("/api/v1/")).length;
  await pagina.waitForTimeout(4000);
  const despues = (await Promise.all(registro.peticiones)).filter((p) => p.url.includes("/api/v1/")).length;
  comprobar(`sin-reintentos-automaticos-${codigo}`, antes === despues, { antes, despues });
  await contexto.close();
}

async function recorridoVite() {
  for (const ancho of ANCHOS) {
    await visitar(ancho, "vite-inicio", "/", { captura: ancho === 1280 });
    await visitar(ancho, "vite-ficha-COLORLOTO", "/juegos/COLORLOTO");
    await visitar(ancho, "vite-metrica-BALOTO", "/juegos/BALOTO/estadisticas/correlaciones");
    await visitar(ancho, "vite-prediccion-MILOTO", "/juegos/MILOTO/prediccion");
  }
  // Modo desarrollo: StrictMode monta dos veces y la peticion se comparte.
  const inicio = resultados.visitas.find((v) => v.nombre === "vite-inicio");
  comprobar("vite-strictmode-una-llamada", inicio?.peticiones_api.filter((x) => x === "/api/v1/juegos").length === 1, { api: inicio?.peticiones_api });
}

try {
  if (opciones.escenario === "normal") {
    await recorridoNormal();
  } else if (opciones.escenario === "cuota") {
    await recorridoCuota();
  } else if (opciones.escenario === "api_caida") {
    await recorridoErrorUnico("api_no_disponible");
  } else if (opciones.escenario === "sin_clave") {
    await recorridoErrorUnico("pasarela_no_configurada");
  } else if (opciones.escenario === "clave_incorrecta") {
    await recorridoErrorUnico("no_autenticado");
  } else if (opciones.escenario === "vite") {
    await recorridoVite();
  }
} catch (error) {
  fallo("recorrido", String(error).split("\n")[0]);
}
await navegador.close();
for (const v of resultados.visitas) {
  delete v.enlaces;
}
resultados.resumen = {
  visitas: resultados.visitas.length,
  visitas_correctas: resultados.visitas.filter((v) => v.ok).length,
  comprobaciones: resultados.comprobaciones.length,
  comprobaciones_correctas: resultados.comprobaciones.filter((c) => c.ok).length,
  fallos: fallos.length,
  respuestas_volcadas: volcadas,
};
resultados.fallos = fallos;
await writeFile(join(opciones.salida, "resultados.json"), `${JSON.stringify(resultados, null, 2)}\n`);
console.log(JSON.stringify(resultados.resumen));
process.exit(fallos.length === 0 ? 0 : 1);
