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
 * Fase 9.3 (escenario `fiabilidad`, incluido tambien en `normal`): explicacion,
 * clasificacion de candidatos y fiabilidad de los cuatro juegos en cada ancho,
 * con todas las consultas automaticas, incluido el catalogo (1 + 3 = 4), y la
 * consulta explicita de fiabilidad (3) por separado; cartera y corte, URL y
 * teclado. `cuota_fiabilidad`: la carga inicial cabe en seis; solo la accion
 * explicita posterior recibe 429, conserva la prediccion y permite reintento manual.
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
// Fase 9.2: paginas de la Fase 5 y anteriores aplicables (indice real de la API).
const METRICAS_ESPERADAS = { BALOTO: 30, BALOTO_REVANCHA: 30, MILOTO: 22, COLORLOTO: 36 };
const PLATAFORMA = process.platform === "linux" ? "linux" : process.platform;
const CAPTURAS = new Set(["inicio", "ficha-BALOTO", "sorteos-COLORLOTO", "metrica-BALOTO-correlaciones",
  "metrica-COLORLOTO-pruebas-uniformidad", "prediccion-MILOTO", "prediccion-COLORLOTO", "servicio",
  "estadisticas-COLORLOTO", "sorteo-COLORLOTO", "metrica-COLORLOTO-frecuencia-pares-numero-color",
  "metrica-COLORLOTO-coocurrencia-trios-colores", "metrica-BALOTO-coocurrencia-trios", "metrica-MILOTO-atrasos-numeros",
  "metrica-paginada-BALOTO-2", "metrica-color-COLORLOTO-ROJO",
  "prediccion-explicacion-BALOTO", "prediccion-explicacion-COLORLOTO", "prediccion-explicacion-BALOTO_REVANCHA",
  "fiabilidad-BALOTO", "fiabilidad-COLORLOTO"]);
// Fase 9.3: lo que el escenario sintetico debe mostrar en cada juego.
const ESPERADO_93 = {
  BALOTO: { clasificacion: "numeros", explicacion: "guardada", importancias: "disponible", superbalota: true },
  BALOTO_REVANCHA: { clasificacion: "numeros", explicacion: "ausente", importancias: null, superbalota: true },
  MILOTO: { clasificacion: "numeros", explicacion: "guardada", importancias: "no_disponible", superbalota: false },
  COLORLOTO: { clasificacion: "pares", explicacion: "guardada", importancias: "no_disponible", superbalota: false },
};

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
    // Celdas de formato `color` de las tablas de metrica (ColorLoto): muestra oculta y codigo en texto.
    const colores = [...document.querySelectorAll("main table[data-tabla] td .color-swatch")].map((m) => ({
      texto: (m.parentElement?.textContent ?? "").trim(),
      oculta: m.getAttribute("aria-hidden") === "true",
    }));
    return { ventana, documento: document.documentElement.scrollWidth, cuerpo: document.body.scrollWidth, tablas, colores };
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
async function visitar(ancho, nombre, ruta, { esperarError = null, admitidos = [], captura = CAPTURAS.has(nombre), consultarFiabilidad = false } = {}) {
  const permitidos = new Set([...(esperarError ? [esperarError] : []), ...admitidos]);
  const { contexto, pagina, registro } = await nuevaPestana(ancho);
  const visita = { ancho, nombre, ruta, ok: true, motivos: [] };
  try {
    await pagina.goto(BASE + ruta, { waitUntil: "networkidle" });
    await esperarContenido(pagina);
    await pagina.waitForLoadState("networkidle");
    // La foto automatica se toma antes de cualquier accion explicita: no se
    // descarta el catalogo ni se oculta una consulta extra de la SPA.
    visita.peticiones_api_automaticas = rutasApi(await Promise.all(registro.peticiones));
    if (consultarFiabilidad) {
      visita.fiabilidad_inicial_sin_tabla = await pagina.locator("main [data-fiabilidad-corte] table").count() === 0;
      await pagina.getByRole("button", { name: "Consultar fiabilidad", exact: true }).click();
      await pagina.waitForSelector("main [data-fiabilidad-corte] table", { timeout: 30000 });
      await pagina.waitForLoadState("networkidle");
      visita.peticiones_api_explicitas = rutasApi(await Promise.all(registro.peticiones))
        .slice(visita.peticiones_api_automaticas.length);
    }
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
    if (g.colores.some((c) => !c.oculta || !/^[A-Z][A-Z_]*$/.test(c.texto))) {
      visita.motivos.push("celda de color sin codigo en texto o con muestra anunciada");
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
        ["prediccion", "frescura", "observado", "frente", "integridad", "configuracion", "estado", "base", "salud", "metrica", "paginacion",
          "clasificacion", "explicacion", "importancias", "superbalota", "fiabilidad-corte", "evaluacion", "hasta", "receta", "linea"]
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

/** Todas las consultas a la API, incluido el catalogo de una memoria vacia. */
function rutasApi(peticiones) {
  return peticiones.filter((p) => new URL(p.url).pathname.startsWith("/api/v1/"))
    .map((p) => new URL(p.url).pathname + new URL(p.url).search);
}

function mismasConsultas(actuales, esperadas) {
  const a = [...actuales].sort();
  const b = [...esperadas].sort();
  return a.length === b.length && a.every((ruta, i) => ruta === b[i]);
}

/** Costes existentes de las rutas del recorrido dirigido; una ruta extra falla. */
function fichas93(rutas) {
  return rutas.reduce((total, ruta) => {
    const path = new URL(ruta, BASE).pathname;
    if (path === "/api/v1/juegos") return total + 1;
    if (/^\/api\/v1\/juegos\/[A-Z_]+\/(predicciones|fiabilidad)$/.test(path)) return total + 3;
    throw new Error(`consulta fuera del presupuesto dirigido: ${ruta}`);
  }, 0);
}

/** Fase 9.3: carga automatica y accion explicita se registran por separado. */
async function pantallasFiabilidad(ancho) {
  for (const juego of JUEGOS) {
    const e = ESPERADO_93[juego];
    const v = await visitar(ancho, `prediccion-explicacion-${juego}`, `/juegos/${juego}/prediccion`, { consultarFiabilidad: true });
    const m = v.marcas ?? {};
    const corte = (m["fiabilidad-corte"] ?? [])[0];
    const automaticas = v.peticiones_api_automaticas ?? [];
    const explicitas = v.peticiones_api_explicitas ?? [];
    comprobar(`prediccion-9-3-${juego}-${ancho}`,
      v.ok && m.clasificacion?.[0] === e.clasificacion && m.explicacion?.[0] === e.explicacion &&
        (m.importancias?.[0] ?? null) === e.importancias && ((m.superbalota ?? []).length > 0) === e.superbalota &&
        corte !== undefined && v.fiabilidad_inicial_sin_tabla &&
        mismasConsultas(automaticas, ["/api/v1/juegos", `/api/v1/juegos/${juego}/predicciones`]) &&
        fichas93(automaticas) === 4 && fichas93(automaticas) <= 6 &&
        mismasConsultas(explicitas, [`/api/v1/juegos/${juego}/fiabilidad?hasta=${corte}`]) && fichas93(explicitas) === 3,
      { marcas: m, automaticas, fichas_automaticas: fichas93(automaticas), explicitas, fichas_accion_explicita: fichas93(explicitas) });
    const f = await visitar(ancho, `fiabilidad-${juego}`, `/juegos/${juego}/fiabilidad`);
    const consultas = f.peticiones_api_automaticas ?? [];
    comprobar(`fiabilidad-9-3-${juego}-${ancho}`,
      f.ok && mismasConsultas(consultas, ["/api/v1/juegos", `/api/v1/juegos/${juego}/fiabilidad`]) &&
        fichas93(consultas) === 4 && f.marcas?.hasta?.[0] === "todos" &&
        (f.marcas?.receta ?? []).length === 1 && (f.marcas?.evaluacion ?? []).includes("evaluacion_de_receta"),
      { marcas: f.marcas, automaticas: consultas, fichas_automaticas: fichas93(consultas) });
  }
  const corte = await visitar(ancho, "fiabilidad-corte-BALOTO", "/juegos/BALOTO/fiabilidad?hasta=2190");
  const consultas = corte.peticiones_api_automaticas ?? [];
  comprobar(`fiabilidad-corte-url-${ancho}`, corte.ok && corte.marcas?.hasta?.[0] === "2190" &&
    mismasConsultas(consultas, ["/api/v1/juegos", "/api/v1/juegos/BALOTO/fiabilidad?hasta=2190"]) && fichas93(consultas) === 4,
    { marcas: corte.marcas?.hasta, automaticas: consultas, fichas_automaticas: fichas93(consultas) });
  await visitar(ancho, "fiabilidad-corte-no-valido", "/juegos/BALOTO/fiabilidad?hasta=0", { esperarError: "parametro_no_valido" });
  await tecladoFiabilidad(ancho);
}

/** Teclado: la consulta explicita y el universo plegado admiten Enter; tabla enfocable. */
async function tecladoFiabilidad(ancho) {
  const { contexto, pagina } = await nuevaPestana(ancho);
  await pagina.goto(`${BASE}/juegos/BALOTO/prediccion`, { waitUntil: "networkidle" });
  await esperarContenido(pagina);
  const consulta = pagina.getByRole("button", { name: "Consultar fiabilidad", exact: true });
  await consulta.focus();
  const botonEnfocado = await pagina.evaluate(() => document.activeElement?.textContent?.trim());
  await pagina.keyboard.press("Enter");
  await pagina.waitForSelector("main [data-fiabilidad-corte] table", { timeout: 30000 });
  const resumen = pagina.locator("main [data-clasificacion] details > summary").first();
  await resumen.focus();
  await pagina.keyboard.press("Enter");
  const abierto = await pagina.locator("main [data-clasificacion] details").first().evaluate((d) => d.open);
  const enfocado = await pagina.evaluate(() => {
    const e = document.activeElement;
    const s = e ? getComputedStyle(e) : null;
    return { etiqueta: e?.tagName, visible: Boolean(s && (s.outlineStyle !== "none" || s.boxShadow !== "none")) };
  });
  await pagina.locator("main [data-fiabilidad-corte] .tabla-desplazable").first().focus();
  const region = await pagina.evaluate(() => document.activeElement?.getAttribute("aria-label"));
  await pagina.keyboard.press("Tab");
  const siguiente = await pagina.evaluate(() => document.activeElement?.tagName);
  comprobar(`teclado-fiabilidad-${ancho}`, botonEnfocado === "Consultar fiabilidad" && abierto &&
    enfocado.etiqueta === "SUMMARY" && enfocado.visible && region === "Fiabilidad hasta el sorteo 2192" && Boolean(siguiente),
    { botonEnfocado, abierto, enfocado, region, siguiente });
  await contexto.close();
}

/** La identidad/corte siguen la cartera; cada seleccion vuelve a consulta explicita. */
async function carteraYCorte() {
  const { contexto, pagina, registro } = await nuevaPestana(1280);
  const api = async () => rutasApi(await Promise.all(registro.peticiones));
  async function manual(corte) {
    await pagina.waitForSelector(`main [data-fiabilidad-corte='${corte}']`, { timeout: 30000 });
    await esperarContenido(pagina);
    await pagina.waitForLoadState("networkidle");
    return await pagina.getByRole("button", { name: "Consultar fiabilidad", exact: true }).count() === 1 &&
      await pagina.locator("main [data-fiabilidad-corte] table").count() === 0;
  }
  async function consultar(corte) {
    await pagina.getByRole("button", { name: "Consultar fiabilidad", exact: true }).click();
    await pagina.waitForSelector(`main [data-fiabilidad-corte='${corte}'] table`, { timeout: 30000 });
    await pagina.waitForLoadState("networkidle");
  }
  await pagina.goto(`${BASE}/juegos/BALOTO/prediccion`, { waitUntil: "networkidle" });
  const inicioManual = await manual(2192);
  const iniciales = await api();
  await consultar(2192);
  const inicio = (await api()).length;
  await pagina.click("main a[aria-label='Ver la predicción del objetivo 2191']");
  await pagina.waitForURL(/cartera=[0-9a-f]{64}/);
  const seleccionManual = await manual(2190);
  const entrada = await pagina.locator("main [data-corte=entrada] td.text-end").innerText();
  const clave = new URL(pagina.url()).searchParams.get("cartera");
  const alElegir = (await api()).slice(inicio);
  const antesExplicita = (await api()).length;
  await consultar(2190);
  const explicitas = (await api()).slice(antesExplicita);
  const antesAtras = (await api()).length;
  await pagina.goBack();
  await pagina.waitForURL((u) => !/cartera=/.test(u.toString()));
  const atrasManual = await manual(2192);
  const alVolver = (await api()).slice(antesAtras);
  const antesAdelante = (await api()).length;
  await pagina.goForward();
  const adelanteManual = await manual(2190);
  const alAvanzar = (await api()).slice(antesAdelante);
  const antesRecarga = (await api()).length;
  await pagina.reload({ waitUntil: "networkidle" });
  const recargaManual = await manual(2190);
  const alRecargar = (await api()).slice(antesRecarga);
  const prediccionElegida = `/api/v1/juegos/BALOTO/predicciones?cartera=${clave}`;
  comprobar("cartera-actualiza-el-corte", entrada === "2190" && inicioManual && seleccionManual && atrasManual &&
    adelanteManual && recargaManual && new URL(pagina.url()).searchParams.get("cartera") === clave &&
    mismasConsultas(iniciales, ["/api/v1/juegos", "/api/v1/juegos/BALOTO/predicciones"]) && fichas93(iniciales) === 4 &&
    mismasConsultas(alElegir, [prediccionElegida]) && fichas93(alElegir) === 3 &&
    mismasConsultas(explicitas, ["/api/v1/juegos/BALOTO/fiabilidad?hasta=2190"]) &&
    mismasConsultas(alVolver, ["/api/v1/juegos/BALOTO/predicciones"]) && mismasConsultas(alAvanzar, [prediccionElegida]) &&
    mismasConsultas(alRecargar, ["/api/v1/juegos", prediccionElegida]) && fichas93(alRecargar) === 4,
    { entrada, iniciales, alElegir, explicitas, alVolver, alAvanzar, alRecargar,
      manual: { inicioManual, seleccionManual, atrasManual, adelanteManual, recargaManual } });
  await pagina.getByRole("link", { name: "Fiabilidad general de la configuración actual", exact: true }).click();
  await pagina.waitForURL(/\/juegos\/BALOTO\/fiabilidad$/);
  await pagina.waitForSelector("main [data-hasta='todos']", { timeout: 30000 });
  await pagina.fill("#corte", "2190");
  await pagina.click("form[aria-label='Corte de la muestra'] button[type=submit]");
  await pagina.waitForURL(/hasta=2190/);
  await pagina.waitForSelector("main [data-hasta='2190']", { timeout: 30000 });
  await pagina.goBack();
  await pagina.waitForSelector("main [data-hasta='todos']", { timeout: 30000 });
  await pagina.goForward();
  await pagina.waitForSelector("main [data-hasta='2190']", { timeout: 30000 });
  await pagina.reload({ waitUntil: "networkidle" });
  await pagina.waitForSelector("main [data-hasta='2190']", { timeout: 30000 });
  const valor = await pagina.inputValue("#corte");
  const todas = await api();
  comprobar("fiabilidad-corte-en-la-url", valor === "2190" && todas.includes("/api/v1/juegos/BALOTO/fiabilidad?hasta=2190") &&
    todas.includes("/api/v1/juegos/BALOTO/fiabilidad"), { valor, api: todas.slice(-6) });
  await contexto.close();
}

async function recorridoFiabilidad() {
  for (const ancho of ANCHOS) {
    await pantallasFiabilidad(ancho);
  }
  await carteraYCorte();
}

/** Cuota 6: carga inicial 1+3; el 429 solo ocurre tras consultar fiabilidad a mano. */
async function recorridoCuotaFiabilidad() {
  const { contexto, pagina, registro } = await nuevaPestana(1280);
  const deFiabilidad = async () => rutasApi(await Promise.all(registro.peticiones)).filter((p) => new URL(p, BASE).pathname.endsWith("/fiabilidad")).length;
  await pagina.goto(`${BASE}/juegos/BALOTO/prediccion`, { waitUntil: "networkidle" });
  await esperarContenido(pagina);
  await pagina.waitForLoadState("networkidle");
  const automaticas = rutasApi(await Promise.all(registro.peticiones));
  const sinFiabilidadAutomatica = await deFiabilidad() === 0;
  const sinErrorInicial = await pagina.locator("main [role=alert][data-codigo]").count() === 0;
  const prediccionVisible = await pagina.locator("main [data-clasificacion]").count();
  comprobar("cuota-carga-inicial-dentro-de-seis", mismasConsultas(automaticas, ["/api/v1/juegos", "/api/v1/juegos/BALOTO/predicciones"]) &&
    fichas93(automaticas) === 4 && sinFiabilidadAutomatica && sinErrorInicial && prediccionVisible === 1,
    { automaticas, fichas_automaticas: fichas93(automaticas), sinFiabilidadAutomatica, sinErrorInicial, prediccionVisible });
  await pagina.getByRole("button", { name: "Consultar fiabilidad", exact: true }).click();
  await pagina.waitForSelector("main [data-fiabilidad-corte] [role=alert][data-codigo=limite_excedido]", { timeout: 30000 });
  const texto = await pagina.locator("main [data-fiabilidad-corte] [role=alert]").innerText();
  const deshabilitado = await pagina.locator("main [data-fiabilidad-corte] [role=alert] button").isDisabled();
  await pagina.screenshot({ path: join(opciones.salida, "capturas", `chromium-${PLATAFORMA}-1280-cuota-fiabilidad-429.png`), fullPage: true });
  const antes = await deFiabilidad();
  await pagina.waitForFunction(() => !document.querySelector("main [data-fiabilidad-corte] [role=alert] button")?.hasAttribute("disabled"), null, { timeout: 90000 });
  const durante = await deFiabilidad();
  await pagina.click("main [data-fiabilidad-corte] [role=alert] button");
  await pagina.waitForSelector("main [data-fiabilidad-corte] table", { timeout: 30000 });
  const despues = await deFiabilidad();
  comprobar("cuota-fiabilidad-429", /Podrás reintentar en \d+ s/.test(texto) && deshabilitado && prediccionVisible === 1 &&
    antes === 1 && durante === 1 && despues === 2, {
    texto: texto.slice(0, 300), boton_deshabilitado: deshabilitado, prediccion_visible: prediccionVisible,
    peticiones_de_fiabilidad: { antes, durante, despues },
  });
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
        const v = await visitar(ancho, `metrica-${juego}-${m.split("/").pop()}`, m);
        // Presupuesto por pantalla: una sola consulta de estadisticas (la metrica), sin indice ni panel.
        const deEstadisticas = (v.peticiones_api ?? []).filter((x) => x.includes("/estadisticas"));
        if (deEstadisticas.length !== 1 || deEstadisticas[0] !== `/api/v1${m}`) {
          fallo(`${ancho} ${m}`, `consultas de estadisticas: ${JSON.stringify(deEstadisticas)}`);
        }
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
    // Fase 9.2: tabla paginada, filtro de color, color no valido y tabla de ColorLoto con colores.
    await visitar(ancho, "metrica-paginada-BALOTO-2", "/juegos/BALOTO/estadisticas/coocurrencia-trios?pagina=2");
    await visitar(ancho, "metrica-color-COLORLOTO-ROJO", "/juegos/COLORLOTO/estadisticas/distribucion-conteo-color?color=ROJO");
    await visitar(ancho, "metrica-color-no-valido", "/juegos/COLORLOTO/estadisticas/distribucion-conteo-color?color=MORADO",
      { esperarError: "parametro_no_valido" });
    await visitar(ancho, "metrica-pagina-fuera", "/juegos/BALOTO/estadisticas/coocurrencia-trios?pagina=999",
      { esperarError: "parametro_no_valido" });
    await teclado(ancho);
    await pantallasFiabilidad(ancho);  // Fase 9.3
  }
  await historialYRecarga();
  await llamadasEnNavegacion();
  await carteraYCorte();
  // Estados informados que el escenario sintetico debe mostrar.
  const ver = (n) => resultados.visitas.filter((v) => v.nombre === n);
  comprobar("simulacion-alterada-vista", ver("simulacion-alterada").length === ANCHOS.length && ver("simulacion-alterada").every((v) => v.ok));
  comprobar("simulacion-verificada-vista", ver("simulacion-verificada").length >= ANCHOS.length);
  const pares = ver("metrica-COLORLOTO-frecuencia-pares-numero-color");
  comprobar("colorloto-pares-con-color", pares.length === ANCHOS.length && pares.every((v) => v.ok && v.geometria.colores.length === 42),
    { colores: pares.map((v) => v.geometria?.colores?.length) });
  const paginadas = ver("metrica-paginada-BALOTO-2");
  comprobar("tabla-paginada-pagina-2", paginadas.length === ANCHOS.length && paginadas.every((v) => v.ok && (v.marcas?.paginacion ?? [])[0] === "2/6"),
    { marcas: paginadas.map((v) => v.marcas?.paginacion) });
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
  } else if (opciones.escenario === "fiabilidad") {
    await recorridoFiabilidad();
  } else if (opciones.escenario === "cuota_fiabilidad") {
    await recorridoCuotaFiabilidad();
  } else {
    fallo("recorrido", `escenario desconocido: ${opciones.escenario}`);
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
