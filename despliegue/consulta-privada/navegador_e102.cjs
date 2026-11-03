// Fase 10 (E10.2): la SPA en Chromium (Playwright) a traves del proxy, con el certificado de cliente de una
// persona sintetica. El conector de certificados de cliente de Playwright verifica el servidor REAL con las
// CA de Node: la CA de prueba se anade de forma explicita con NODE_EXTRA_CA_CERTS (sin ignorar errores TLS).
// El nombre de la demostracion se resuelve a 127.0.0.1 solo dentro de este proceso.
//
// Uso: node navegador_e102.cjs <origen> <cert.pem|-> <clave.pem|-> <salida sin extension>
// La resolucion se sustituye ANTES de cargar Playwright (su conector la toma al importarse).
const dns = require("node:dns");
const fs = require("node:fs");

const [origen, certPath, keyPath, salida] = process.argv.slice(2);
const nombre = new URL(origen).hostname;
const original = dns.lookup;
dns.lookup = (host, opciones, llamada) => {
  if (host !== nombre) return original(host, opciones, llamada);
  const fin = typeof opciones === "function" ? opciones : llamada;
  const todas = typeof opciones === "object" && opciones && opciones.all;
  return process.nextTick(() => (todas ? fin(null, [{ address: "127.0.0.1", family: 4 }]) : fin(null, "127.0.0.1", 4)));
};
const promesa = dns.promises.lookup;
dns.promises.lookup = (host, opciones) => (host === nombre
  ? Promise.resolve(opciones && opciones.all ? [{ address: "127.0.0.1", family: 4 }] : { address: "127.0.0.1", family: 4 })
  : promesa(host, opciones));
const { chromium } = require("playwright");

(async () => {
  const navegador = await chromium.launch({ args: [`--host-resolver-rules=MAP ${nombre} 127.0.0.1`] });
  const certificados = certPath !== "-" ? [{ origin: origen, certPath, keyPath }] : [];
  const contexto = await navegador.newContext({ clientCertificates: certificados, ignoreHTTPSErrors: false });
  const pagina = await contexto.newPage();
  const respuestas = [];
  pagina.on("response", (r) => respuestas.push({ ruta: new URL(r.url()).pathname, estado: r.status() }));
  let resultado;
  try {
    await pagina.goto(`${origen}/servicio`, { waitUntil: "networkidle", timeout: 30000 });
    await pagina.waitForSelector("[data-base]", { timeout: 20000 });
    const base = await pagina.getAttribute("[data-base]", "data-base");
    const titulo = (await pagina.textContent("h1")).trim();
    await pagina.screenshot({ path: `${salida}-servicio.png`, fullPage: true });
    await pagina.goto(`${origen}/juegos/BALOTO/modelos`, { waitUntil: "networkidle", timeout: 30000 });
    await pagina.waitForTimeout(500);
    await pagina.screenshot({ path: `${salida}-modelos.png`, fullPage: true });
    resultado = { ok: true, base, titulo, respuestas };
  } catch (error) {
    resultado = { ok: false, error: String(error.message).split("\n")[0].slice(0, 300), respuestas };
  }
  fs.writeFileSync(`${salida}.json`, JSON.stringify(resultado, null, 1));
  await navegador.close();
})();
