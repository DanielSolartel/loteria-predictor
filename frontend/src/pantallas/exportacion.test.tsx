/** Integration through loaded SPA queries; these are simulated HTTP, not the real browser walk. */
import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { diferida, instalarServidor, muestra, renderizar, type Respuesta } from "../pruebas/servidor";
import type { CarterasGuardadas, FichaCarteraGuardada, ModelosGuardados } from "../api/guardados";
import type { Fiabilidad, Predicciones } from "../api/presentacion";
import { rutaDeRetorno } from "../usos/retorno";

afterEach(() => vi.restoreAllMocks());
function descargas() {
  const archivos: Blob[] = [];
  const ClaseURL = URL;
  class ConDescargas extends ClaseURL {
    static override createObjectURL = vi.fn((b: Blob) => { archivos.push(b); return `blob:prueba-${archivos.length}`; });
    static override revokeObjectURL = vi.fn();
  }
  vi.stubGlobal("URL", ConDescargas);
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
  const imprimir = vi.spyOn(window, "print").mockImplementation(() => undefined);
  async function texto(b: Blob) { return new Promise<string>((resolve, reject) => { const f = new FileReader(); f.onload = () => resolve(String(f.result)); f.onerror = reject; f.readAsText(b, "utf-8"); }); }
  return { archivos, imprimir, json: async () => { fireEvent.click(await screen.findByRole("button", { name: "Exportar JSON" })); return JSON.parse(await texto(archivos.at(-1)!)); }, csv: async () => { fireEvent.click(await screen.findByRole("button", { name: "Exportar CSV" })); return texto(archivos.at(-1)!); } };
}
const rutaFicha = (tipo: "modelo" | "cartera") => muestra(`BALOTO--${tipo}`).url.replace("/api/v1", "").replace("modelos-guardados", "modelos").replace("carteras-guardadas", "carteras");
const rutas = [
  ["resumen", "/juegos/BALOTO"], ["sorteos", "/juegos/BALOTO/sorteos"], ["sorteo", muestra("BALOTO--sorteo").url.replace("/api/v1", "")],
  ["estadisticas", "/juegos/BALOTO/estadisticas"], ["metrica", "/juegos/BALOTO/estadisticas/coocurrencia-trios"],
  ["prediccion", "/juegos/BALOTO/prediccion"], ["fiabilidad", "/juegos/BALOTO/fiabilidad"], ["modelos", "/juegos/BALOTO/modelos"], ["modelo", rutaFicha("modelo")],
  ["carteras", "/juegos/BALOTO/carteras"], ["cartera", rutaFicha("cartera")], ["resultados", "/juegos/BALOTO/resultados"],
  ["simulaciones", "/juegos/COLORLOTO/simulaciones"], ["simulacion", muestra("COLORLOTO--simulacion--verificada").url.replace("/api/v1", "")],
] as const;

/** Parser de comprobación RFC4180: no reutiliza el serializador del producto. */
function leerCsv(texto: string): string[][] {
  const filas: string[][] = []; let fila: string[] = [], celda = "", dentro = false;
  const entrada = texto.replace(/^\ufeff/, "");
  for (let i = 0; i < entrada.length; i++) {
    const c = entrada[i]!;
    if (c === '"') {
      if (dentro && entrada[i + 1] === '"') { celda += '"'; i++; }
      else dentro = !dentro;
    } else if (c === "," && !dentro) { fila.push(celda); celda = ""; }
    else if ((c === "\r" || c === "\n") && !dentro) {
      if (c === "\r" && entrada[i + 1] === "\n") i++;
      fila.push(celda); filas.push(fila); fila = []; celda = "";
    } else celda += c;
  }
  if (celda || fila.length) { fila.push(celda); filas.push(fila); }
  expect(dentro).toBe(false);
  expect(filas.every((f) => f.length === filas[0]!.length)).toBe(true);
  return filas;
}

describe("cada superficie exporta sólo su consulta cargada", () => {
  it.each(rutas)("%s: relee JSON y CSV y no solicita HTTP adicional al exportar/imprimir", async (recurso, ruta) => {
    const io = descargas(); const { deApi, llamadas } = instalarServidor(); renderizar(ruta + (ruta.includes("?") ? "&" : "?") + "token=no-copiar&origen=externo");
    await screen.findByRole("button", { name: "Exportar JSON" });
    const api = deApi().slice(), todas = llamadas.length;
    const documento = await io.json();
    expect(documento.esquema).toBe("loteria-predictor/consulta-publica/1");
    expect(documento.recurso).toBe(recurso);
    expect(documento.ruta_spa).not.toContain("token");
    expect(documento.ruta_spa).not.toContain("origen");
    expect(documento.ruta_spa.startsWith("/")).toBe(true);
    const csv = await io.csv();
    expect(csv).toContain('"tipo_fila","esquema"');
    expect(csv).toContain('"contexto","loteria-predictor/tabla-publica/1"');
    expect(csv).not.toContain("no-copiar");
    fireEvent.click(screen.getByRole("button", { name: "Imprimir" }));
    expect(io.imprimir).toHaveBeenCalledTimes(1);
    expect(deApi()).toEqual(api); expect(llamadas).toHaveLength(todas);
  });
  it.each(["/", "/servicio", "/no-existe"])("%s no ofrece una descarga sin datos útiles", async (ruta) => {
    instalarServidor(); renderizar(ruta); await act(async () => { await new Promise((r) => setTimeout(r, 10)); });
    expect(screen.queryByRole("button", { name: "Exportar JSON" })).toBeNull();
  });
  it.each(["/api/v1/juegos/BALOTO", "/api/v1/juegos/BALOTO/estadisticas/resumen"])("ficha/resumen no habilita una descarga parcial si falla %s", async (fallida) => {
    instalarServidor({ [fallida]: { estado: 500, cuerpo: { error: { codigo: "error_interno", mensaje: "Fallo sintético de una parte de la consulta", solicitud: null } } } });
    renderizar("/juegos/BALOTO");
    await screen.findByRole("alert");
    if (fallida === "/api/v1/juegos/BALOTO") await screen.findByText("Atrasado: 1945 días");
    else await screen.findByText("15.401.568 combinaciones");
    expect(screen.queryByRole("button", { name: "Exportar JSON" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Exportar CSV" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Imprimir" })).toBeNull();
  });
});

describe("fiabilidad de predicción exportada respeta la consulta explícita y la identidad", () => {
  it.each([true, false])("sólo incluye el bloque consultado si acredita la cartera (%s)", async (corresponde) => {
    const p = muestra("BALOTO--predicciones").cuerpo as Predicciones;
    const f = muestra("BALOTO--fiabilidad--corte-2192").cuerpo as Fiabilidad;
    if (!corresponde) f.registrado!.clave = "e".repeat(64);
    const { deApi } = instalarServidor({ "/api/v1/juegos/BALOTO/predicciones": { estado: 200, cuerpo: p }, "/api/v1/juegos/BALOTO/fiabilidad?hasta=2192": { estado: 200, cuerpo: f } });
    const io = descargas(); renderizar("/juegos/BALOTO/prediccion");
    let d = await io.json(); expect(d.datos.fiabilidad).toBeNull(); expect(d.datos.estado_fiabilidad).toBe("no_consultada");
    expect(deApi()).toEqual(["/api/v1/juegos", "/api/v1/juegos/BALOTO/predicciones"]);
    fireEvent.click(screen.getByRole("button", { name: "Consultar fiabilidad" }));
    if (corresponde) await screen.findByRole("region", { name: "Fiabilidad hasta el sorteo 2192" });
    else await screen.findByText(/La fiabilidad no está disponible para esta cartera/);
    const llamadas = deApi().slice(); d = await io.json();
    expect(d.datos.estado_fiabilidad).toBe(corresponde ? "acreditada" : "no_acreditada");
    expect(d.datos.fiabilidad).toEqual(corresponde ? f : null);
    await io.csv(); fireEvent.click(screen.getByRole("button", { name: "Imprimir" })); expect(deApi()).toEqual(llamadas);
  });
  it("CSV de candidatos identifica corte, objetivo y versión sin consultarlos ni convertirlos en filtros", async () => {
    const io = descargas(); const { deApi } = instalarServidor();
    renderizar("/juegos/BALOTO/prediccion");
    const documento = await io.json();
    fireEvent.change(screen.getByRole("combobox", { name: "Tabla CSV" }), { target: { value: "ranking_numeros" } });
    const filas = leerCsv(await io.csv()), cabecera = filas[0]!, contexto = filas[1]!;
    const valor = (nombre: string) => contexto[cabecera.indexOf(nombre)];
    expect(valor("identidad_clave_cartera")).toBe(documento.datos.prediccion.clave);
    expect(valor("identidad_corte_entrada")).toBe("2192");
    expect(valor("identidad_objetivo")).toBe("2193");
    expect(valor("identidad_modelo")).toBe("random_forest_clasificador");
    expect(valor("identidad_version_receta")).toBe("1");
    expect(valor("identidad_version_registrada")).toBe("1");
    expect(valor("identidad_clave_registrada")).toBe(documento.datos.prediccion.registrado.clave);
    expect(valor("identidad_perfil")).toBe("reducido");
    expect(valor("ruta_spa")).not.toContain("corte_entrada");
    expect(filas[2]![cabecera.indexOf("identidad_objetivo")]).toBe("2193");
    expect(deApi()).toEqual(["/api/v1/juegos", "/api/v1/juegos/BALOTO/predicciones"]);
  });

  it("CSV de fiabilidad conserva registrado, límite observado y corte del informe por fila", async () => {
    const io = descargas(); instalarServidor(); renderizar("/juegos/BALOTO/fiabilidad");
    const documento = await io.json(), filas = leerCsv(await io.csv()), cabecera = filas[0]!;
    const contexto = filas[1]!;
    expect(contexto[cabecera.indexOf("identidad_version_registrada")]).toBe("1");
    expect(contexto[cabecera.indexOf("identidad_clave_registrada")]).toBe(documento.datos.registrado.clave);
    expect(contexto[cabecera.indexOf("identidad_corte_observacion")]).toBe("2192");
    const columnaCorte = cabecera.indexOf("dato_Corte del informe");
    expect(columnaCorte).toBeGreaterThan(-1);
    const primera = documento.datos.lineas[0].evaluaciones.find((e: { componentes: Record<string, { metricas?: Record<string, unknown> }> }) => Object.values(e.componentes).some((c) => Object.keys(c.metricas ?? {}).length));
    expect(filas[2]![columnaCorte]).toBe(primera.corte_del_informe === null ? "null" : String(primera.corte_del_informe));
  });
});

describe("la exportación no sobrevive como un resultado ajeno", () => {
  it("cambio rápido de juego y respuesta tardía: no exporta el juego anterior", async () => {
    const pendiente = diferida<Respuesta>(); const { deApi } = instalarServidor({ "/api/v1/juegos/BALOTO/modelos-guardados": () => pendiente.promesa });
    const io = descargas(); renderizar("/juegos/BALOTO/modelos", "/juegos/MILOTO/modelos");
    expect((await io.json()).juego).toBe("MILOTO");
    fireEvent.click(screen.getByTestId("atras")); await waitFor(() => expect(deApi()).toContain("/api/v1/juegos/BALOTO/modelos-guardados"));
    expect(screen.queryByRole("button", { name: "Exportar JSON" })).toBeNull();
    fireEvent.click(screen.getByTestId("adelante")); expect((await io.json()).juego).toBe("MILOTO");
    await act(async () => { pendiente.resolver(muestra("BALOTO--modelos")); });
    expect((await io.json()).datos.juego).toBe("MILOTO");
  });
  it.each(["modelos", "carteras"] as const)("%s: cambio de filtro, vacío válido y respuesta tardía", async (grupo) => {
    const io = descargas(), pendiente = diferida<Respuesta>();
    const inicial = muestra(`BALOTO--${grupo}`), vacio = muestra(`BALOTO--${grupo}--vacio`);
    const api = `/api/v1/juegos/BALOTO/${grupo}-guardadas`.replace("modelos-guardadas", "modelos-guardados");
    const campo = grupo === "modelos" ? "Perfil" : "Objetivo desde", valor = grupo === "modelos" ? "reducido" : "999999";
    const query = grupo === "modelos" ? "perfil=reducido" : "desde=999999";
    if (grupo === "modelos") (vacio.cuerpo as ModelosGuardados).perfil = valor; else (vacio.cuerpo as CarterasGuardadas).desde = Number(valor);
    instalarServidor({ [api]: inicial, [`${api}?${query}`]: () => pendiente.promesa }); renderizar(`/juegos/BALOTO/${grupo}`);
    await io.json(); fireEvent.change(screen.getByLabelText(campo), { target: { value: valor } }); fireEvent.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    expect(screen.queryByRole("button", { name: "Exportar JSON" })).toBeNull();
    await act(async () => { pendiente.resolver(vacio); });
    const d = await io.json(); expect(d.datos.elementos).toEqual([]); expect(d.paginacion.total).toBe(0);
    expect(await io.csv()).not.toContain('"dato","loteria-predictor/tabla-publica/1"');
  });
  it.each([409, 429, 500])("ficha cambia a error HTTP %s: retira la descarga anterior", async (estado) => {
    const actual = muestra("BALOTO--cartera"), previa = muestra("BALOTO--cartera--anterior");
    instalarServidor({ [previa.url]: { estado, cuerpo: { error: { codigo: estado === 409 ? "alterado" : estado === 429 ? "limite_excedido" : "error_interno", mensaje: "Error de la prueba", solicitud: null } }, ...(estado === 429 ? { retry_after: "1" } : {}) } });
    const io = descargas(); renderizar(previa.url.replace("/api/v1", "").replace("carteras-guardadas", "carteras"), rutaFicha("cartera"));
    expect((await io.json()).datos.cartera.clave).toBe((actual.cuerpo as FichaCarteraGuardada).cartera.clave);
    fireEvent.click(screen.getByTestId("atras")); await screen.findByRole("alert");
    expect(screen.queryByRole("button", { name: "Exportar JSON" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Imprimir" })).toBeNull();
  });
});

describe("volver a listado conserva sólo su contexto permitido", () => {
  it.each([
    { retornoListado: "https://otro.invalid/juegos/BALOTO/sorteos?pagina=2" }, { retornoListado: "/juegos/MILOTO/sorteos?pagina=2" },
    { retornoListado: "//otro.invalid/juegos/BALOTO/sorteos" }, { retornoListado: "/juegos/BALOTO/sorteos#secreto" }, { retornoListado: "/\\otro.invalid/sorteos" }, null,
  ])("rechaza origen ajeno o no reconocido: %o", (origen) => {
    expect(rutaDeRetorno(origen, "/juegos/BALOTO/sorteos", ["pagina", "orden"])).toBe("/juegos/BALOTO/sorteos");
  });
  it("mantiene filtros/página y elimina los arbitrarios", () => {
    expect(rutaDeRetorno({ retornoListado: "/juegos/BALOTO/sorteos?orden=numero_desc&pagina=3&token=no" }, "/juegos/BALOTO/sorteos", ["pagina", "orden"])).toBe("/juegos/BALOTO/sorteos?pagina=3&orden=numero_desc");
  });
  it("el enlace a la ficha y el retorno mantienen la página de modelos", async () => {
    instalarServidor(); renderizar("/juegos/BALOTO/modelos?pagina=1&por_pagina=20&token=no");
    fireEvent.click(await screen.findByRole("link", { name: "Ver modelo v1" }));
    const volver = await screen.findByRole("link", { name: "Volver a los modelos registrados" });
    expect(volver.getAttribute("href")).toBe("/juegos/BALOTO/modelos?pagina=1&por_pagina=20");
    fireEvent.click(volver); await screen.findByRole("button", { name: "Exportar JSON" });
    expect(screen.getByTestId("ubicacion").textContent).toBe("/juegos/BALOTO/modelos?pagina=1&por_pagina=20");
  });
});
