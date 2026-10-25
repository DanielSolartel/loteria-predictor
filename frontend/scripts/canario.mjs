/**
 * Canario de compilacion y escaneo del codigo cliente (Fase 9.1).
 *
 * 1. Compila la SPA en una carpeta temporal con un entorno que contiene una
 *    clave canario y su huella SHA-256 en las variables que podria tener un
 *    servidor (`PASARELA_CLAVE_API`, `API_PUBLICA_CLAVES`, `VITE_CLAVE`...) y
 *    comprueba que ninguna de las dos aparece en el resultado.
 * 2. Busca en el codigo propio (src/, sin el esquema generado ni las pruebas) y
 *    en el JavaScript compilado: envio de credenciales (cabecera X-API-Key o
 *    Authorization, `credentials: "include"`), almacenamiento del navegador y
 *    recursos de terceros. El nombre publico `X-API-Key` dentro del esquema
 *    generado (`esquema.d.ts`, solo tipos) o del OpenAPI no es una filtracion ni
 *    codigo que envie credenciales: esos dos archivos se excluyen a proposito.
 *
 * No imprime el canario ni su huella. Uso: `npm run canario`.
 */
import { createHash, randomBytes } from "node:crypto";
import { mkdtempSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "vite";

const raiz = join(dirname(fileURLToPath(import.meta.url)), "..");
const canario = `f9canario-${randomBytes(24).toString("hex")}`;
const huella = createHash("sha256").update(canario, "ascii").digest("hex");

function archivos(carpeta) {
  return readdirSync(carpeta).flatMap((n) => {
    const ruta = join(carpeta, n);
    return statSync(ruta).isDirectory() ? archivos(ruta) : [ruta];
  });
}

const temporal = mkdtempSync(join(tmpdir(), "f9-canario-"));
const resultado = { compilacion: {}, codigo_fuente: {}, compilado: {} };
let fallos = 0;
const anotar = (grupo, nombre, encontrados) => {
  resultado[grupo][nombre] = encontrados;
  fallos += encontrados.length;
};
try {
  const entorno = join(temporal, "entorno");
  const salida = join(temporal, "dist");
  await import("node:fs/promises").then((fs) => fs.mkdir(entorno));
  const lineas = [`PASARELA_CLAVE_API=${canario}`, `API_PUBLICA_CLAVES=f9:sha256:${huella}`, `VITE_CLAVE=${canario}`, `CLAVE=${canario}`, `HUELLA=${huella}`];
  writeFileSync(join(entorno, ".env"), `${lineas.join("\n")}\n`);
  const anteriores = { PASARELA_CLAVE_API: process.env.PASARELA_CLAVE_API, VITE_CLAVE: process.env.VITE_CLAVE };
  process.env.PASARELA_CLAVE_API = canario;
  process.env.VITE_CLAVE = canario;
  try {
    await build({ root: raiz, configFile: join(raiz, "vite.config.ts"), envDir: entorno, logLevel: "silent", build: { outDir: salida, emptyOutDir: true } });
  } finally {
    for (const [k, v] of Object.entries(anteriores)) {
      if (v === undefined) {
        delete process.env[k];
      } else {
        process.env[k] = v;
      }
    }
  }
  const compilados = archivos(salida);
  resultado.compilacion.archivos = compilados.length;
  anotar("compilacion", "canario_o_huella", compilados.filter((a) => {
    const datos = readFileSync(a);
    return datos.includes(canario) || datos.includes(huella);
  }).map((a) => relative(salida, a)));

  const EXCLUIDOS = new Set(["src/api/esquema.d.ts", "src/api/openapi.json"]);
  const fuentes = archivos(join(raiz, "src"))
    .map((a) => relative(raiz, a).split("\\").join("/"))
    .filter((a) => /\.(ts|tsx|css|html)$/.test(a) && !EXCLUIDOS.has(a) && !a.includes(".test.") && !a.startsWith("src/pruebas/"));
  resultado.codigo_fuente.archivos = fuentes.length;
  const patrones = {
    cabecera_de_credencial: /x-api-key|["']authorization["']/i,
    credenciales_incluidas: /credentials\s*:\s*["'](include|same-origin)["']/,
    almacenamiento: /localStorage|sessionStorage|indexedDB|document\.cookie|caches\.open|serviceWorker/,
    recurso_externo: /https?:\/\/(?!127\.0\.0\.1|localhost|\[::1\])[a-z0-9.-]+\.[a-z]{2,}/i,
  };
  // Autocomprobacion: cada patron detecta un ejemplo de lo que prohibe.
  const ejemplos = {
    cabecera_de_credencial: 'headers: { "X-API-Key": clave }',
    credenciales_incluidas: 'fetch(url, { credentials: "include" })',
    almacenamiento: 'localStorage.setItem("k", v)',
    recurso_externo: '<script src="https://cdn.ejemplo.com/x.js">',
  };
  for (const [nombre, ejemplo] of Object.entries(ejemplos)) {
    if (!patrones[nombre].test(ejemplo)) {
      throw new Error(`el patron ${nombre} no detecta su ejemplo`);
    }
  }
  for (const [nombre, patron] of Object.entries(patrones)) {
    anotar("codigo_fuente", nombre, fuentes.filter((a) => patron.test(readFileSync(join(raiz, a), "utf8"))));
  }
  const js = compilados.filter((a) => a.endsWith(".js"));
  const css = compilados.filter((a) => a.endsWith(".css"));
  const html = compilados.filter((a) => a.endsWith(".html"));
  anotar("compilado", "cabecera_de_credencial", js.filter((a) => /x-api-key/i.test(readFileSync(a, "utf8"))).map((a) => relative(salida, a)));
  anotar("compilado", "almacenamiento", js.filter((a) => /\b(localStorage|sessionStorage|indexedDB)\b|document\.cookie/.test(readFileSync(a, "utf8"))).map((a) => relative(salida, a)));
  anotar("compilado", "css_externo", css.filter((a) => /url\(\s*["']?https?:/i.test(readFileSync(a, "utf8")) || /@import/i.test(readFileSync(a, "utf8"))).map((a) => relative(salida, a)));
  anotar("compilado", "html_externo", html.filter((a) => /<(script|link)[^>]+(src|href)=["']?(https?:)?\/\//i.test(readFileSync(a, "utf8"))).map((a) => relative(salida, a)));
  anotar("compilado", "mapas_de_codigo", compilados.filter((a) => a.endsWith(".map")).map((a) => relative(salida, a)));
} finally {
  rmSync(temporal, { recursive: true, force: true });
}
console.log(JSON.stringify({ ...resultado, fallos }, null, 2));
process.exit(fallos === 0 ? 0 : 1);
