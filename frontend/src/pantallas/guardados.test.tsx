/** Fase 9.4 por las pantallas públicas y muestras de los lectores reales sintéticos. */
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { CarterasGuardadas, FichaCarteraGuardada, FichaModeloGuardado, ModelosGuardados, ResultadosGuardados } from "../api/guardados";
import { diferida, instalarServidor, muestra, renderizar, type Respuesta } from "../pruebas/servidor";

const JUEGOS = ["BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO"];
const GRUPOS = [
  { grupo: "modelos", api: "modelos-guardados", region: "Versiones de modelos registrados", coste: 2 },
  { grupo: "carteras", api: "carteras-guardadas", region: "Carteras de Producto 5", coste: 2 },
  { grupo: "resultados", api: "resultados", region: "Emisiones y resultados", coste: 5 },
] as const;
const respuesta = (cuerpo: unknown): Respuesta => ({ estado: 200, cuerpo });
const fichaModelo = () => muestra("BALOTO--modelo").cuerpo as FichaModeloGuardado;
const fichaCartera = () => muestra("BALOTO--cartera").cuerpo as FichaCarteraGuardada;
const resultados = () => muestra("BALOTO--resultados").cuerpo as ResultadosGuardados;
function rutaFicha(tipo: "modelo" | "cartera", juego = "BALOTO") {
  const f = muestra(`${juego}--${tipo}`);
  return f.url.replace("/api/v1", "").replace("modelos-guardados", "modelos").replace("carteras-guardadas", "carteras");
}
function coste(links: string[]) {
  return links.reduce((n, url) => {
    if (url === "/api/v1/juegos") return n + 1;
    const g = GRUPOS.find((g) => url.includes(`/${g.api}`));
    if (!g) throw new Error(`No se contabilizó el coste de ${url}`);
    return n + g.coste;
  }, 0);
}
async function asentada() { await act(async () => { await new Promise((r) => setTimeout(r, 15)); }); }

describe("consultas guardadas: carga fría y lectura explícita", () => {
  for (const juego of JUEGOS) {
    it.each(GRUPOS)(`${juego}: $grupo cuenta catálogo y no precarga fichas`, async ({ grupo, api, region, coste: esperado }) => {
      const { deApi, llamadas } = instalarServidor();
      renderizar(`/juegos/${juego}/${grupo}`);
      expect(await screen.findByRole("region", { name: region })).toBeTruthy();
      await asentada();
      expect(deApi()).toEqual(expect.arrayContaining(["/api/v1/juegos", `/api/v1/juegos/${juego}/${api}`]));
      expect(deApi()).toHaveLength(2);
      expect(coste(deApi())).toBe(1 + esperado);
      expect(coste(deApi())).toBeLessThanOrEqual(6);
      expect(llamadas.every((l) => l.init?.method === "GET")).toBe(true);
      expect(screen.getByRole("note").textContent).toContain("experimental no acreditado");
    });
  }
  it.each(["modelo", "cartera"] as const)("ficha directa de %s conserva presupuesto y no pide configuración actual", async (tipo) => {
    const { deApi } = instalarServidor(); renderizar(rutaFicha(tipo));
    await waitFor(() => expect(document.querySelector(`[data-${tipo}]`)).not.toBeNull()); await asentada();
    expect(deApi()).toHaveLength(2); expect(coste(deApi())).toBe(3);
    expect(deApi().some((u) => /predicciones|fiabilidad/.test(u))).toBe(false);
    expect(screen.queryByRole("button", { name: /Generar|Entrenar|Verificar|Simular|Guardar/ })).toBeNull();
  });
  it("solo el enlace explícito abre la versión histórica de modelo", async () => {
    const { deApi } = instalarServidor(); renderizar("/juegos/BALOTO/modelos");
    const link = await screen.findByRole("link", { name: "Ver modelo v1" });
    expect(deApi()).toHaveLength(2); fireEvent.click(link);
    await waitFor(() => expect(document.querySelector("[data-modelo]")?.getAttribute("data-modelo")).toBe((muestra("BALOTO--modelo--anterior").cuerpo as FichaModeloGuardado).modelo.clave));
    expect(document.querySelector("[data-corte=entrenamiento]")?.textContent).toContain("2184; 104");
    expect(deApi()).toHaveLength(3);
  });
});

describe("combinaciones y estados reales", () => {
  it("ColorLoto conserva los 18 pares con sus nombres y parámetros guardados", async () => {
    instalarServidor(); renderizar(rutaFicha("cartera", "COLORLOTO"));
    const tabla = await screen.findByRole("region", { name: "Combinaciones de la cartera" });
    expect(tabla.querySelectorAll(".color-swatch")).toHaveLength(18);
    expect(tabla.textContent).toContain("amarillo");
    expect(screen.getByText(/pueden repetirse números y pares/)).toBeTruthy();
    expect(screen.getByText(/abrir esta ficha no ejecuta una reproducción ni una nueva inferencia/)).toBeTruthy();
    expect(document.querySelector("[data-corte=entrada]")?.textContent).toBe("91");
    expect(document.querySelector("[data-corte=objetivo]")?.textContent).toBe("92");
  });
  it("Baloto muestra superbalota aparte de números", async () => {
    instalarServidor(); renderizar(rutaFicha("cartera"));
    const tabla = await screen.findByRole("region", { name: "Combinaciones de la cartera" });
    expect(tabla.querySelectorAll(".superbalota-bolita")).toHaveLength(3);
    expect(within(tabla).getAllByText("superbalota")).toHaveLength(3);
  });
  it.each(GRUPOS)("$grupo: ausencia real visible", async ({ grupo, api }) => {
    instalarServidor({ [`/api/v1/juegos/BALOTO/${api}`]: muestra(`BALOTO--${grupo}--vacio`) });
    renderizar(`/juegos/BALOTO/${grupo}`);
    await waitFor(() => expect(document.querySelector("[data-estado=vacio]")).not.toBeNull());
    expect(screen.queryByRole("button", { name: /Generar|Entrenar|Guardar|Reparar/ })).toBeNull();
  });
  it("incompatibilidad mantiene metadatos y no propone cargar o reparar", async () => {
    const incompatible = muestra("BALOTO--modelo--incompatible");
    instalarServidor({ [incompatible.url]: incompatible });
    renderizar(incompatible.url.replace("/api/v1", "").replace("modelos-guardados", "modelos"));
    await waitFor(() => expect(document.querySelector("[data-integridad=incompatible]")).not.toBeNull());
    expect(document.querySelector("[data-modelo]")?.getAttribute("data-modelo")).toBe((incompatible.cuerpo as FichaModeloGuardado).modelo.clave);
    expect(screen.getByText("Identidad registrada")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Cargar|Reparar|Entrenar/ })).toBeNull();
  });
  it.each([["modelo", "BALOTO"], ["cartera", "COLORLOTO"]] as const)("%s alterado no muestra contenido", async (tipo, juego) => {
    const m = muestra(`${juego}--${tipo}--alterado`);
    instalarServidor({ [m.url]: m }); renderizar(rutaFicha(tipo, juego));
    const alert = await screen.findByRole("alert"); expect(alert.dataset.codigo).toBe("alterado");
    expect(document.querySelector(`[data-${tipo}]`)).toBeNull();
  });
  it("dos artefactos ilegibles sin identidad no inventan enlaces ni colisionan filas", async () => {
    const m = muestra("BALOTO--modelos").cuerpo as ModelosGuardados;
    m.elementos = m.elementos.map((x) => ({ ...x, clave: "", estado: "alterado", numero: null, motivo: "identidad no acreditada" }));
    instalarServidor({ "/api/v1/juegos/BALOTO/modelos-guardados": respuesta(m) });
    renderizar("/juegos/BALOTO/modelos");
    expect(await screen.findAllByText("Ficha no disponible: identidad no acreditada")).toHaveLength(2);
    expect(screen.queryByRole("link", { name: /Ver modelo|Ver estado/ })).toBeNull();
  });
  it("pendiente y sin aciertos acreditados no se convierten en cero; mantiene observados", async () => {
    instalarServidor(); renderizar("/juegos/BALOTO/resultados");
    const tabla = await screen.findByRole("region", { name: "Emisiones y resultados" });
    const pendiente = tabla.querySelector("tr[data-estado=pendiente]")!;
    expect(pendiente.querySelector("[data-aciertos]")?.textContent).toBe("—");
    expect(pendiente.textContent).toContain("Pendiente de resultado");
    expect(pendiente.querySelector("[data-resultado]")?.getAttribute("data-resultado")).toBe("pendiente");
    expect(tabla.querySelector("tr[data-estado=incluido] [data-resultado]")?.getAttribute("data-resultado")).toBe("observado");
    expect(screen.getByText(/Unidades y denominadores/)).toBeTruthy();
    expect(screen.getByText(/1 incluidos · 1 pendientes · 0 excluidos/)).toBeTruthy();
  });
  it.each(["seguimiento", "retrospectiva"])("conserva una emisión sin clasificación excluida en la vista %s", async (tipo) => {
    // Producto 6 de_tipo incluye sin_clasificacion en ambas vistas; _cerrar
    // conserva esa categoría explícita como excluida y sin pérdidas.
    const d = resultados(), f = d.historial.filas[0]!;
    Object.assign(f, { tipo: "sin_clasificacion", estado: "excluido", motivo: "sin_clasificacion_temporal_al_generar",
      aciertos: null, metricas: null, superbalota: null });
    d.historial.filas = [f]; d.historial.total = 1;
    d.filtros.tipo = tipo; d.comparacion.tipo = tipo;
    const url = `/api/v1/juegos/BALOTO/resultados?tipo=${tipo}`;
    instalarServidor({ [url]: respuesta(d) }); renderizar(`/juegos/BALOTO/resultados?tipo=${tipo}`);
    const tabla = await screen.findByRole("region", { name: "Emisiones y resultados" });
    const fila = tabla.querySelector("tr[data-tipo=sin_clasificacion]")!;
    expect(fila.getAttribute("data-estado")).toBe("excluido");
    expect(fila.textContent).toContain("sin_clasificacion_temporal_al_generar");
    expect(fila.querySelector("[data-aciertos]")?.textContent).toBe("—");
    expect(screen.queryByRole("alert")).toBeNull();
  });
  it.each(["incluida", "pérdidas", "superbalota"])("rechaza una emisión sin clasificación indebidamente con %s", async (incompatible) => {
    const d = resultados(), f = d.historial.filas.find((e) => e.estado === "incluido")!;
    const metricas = f.metricas, superbalota = f.superbalota;
    Object.assign(f, { tipo: "sin_clasificacion", estado: "excluido", metricas: null, superbalota: null });
    if (incompatible === "incluida") f.estado = "incluido";
    if (incompatible === "pérdidas") { expect(metricas).not.toBeNull(); f.metricas = metricas; }
    if (incompatible === "superbalota") { expect(superbalota).not.toBeNull(); f.superbalota = superbalota; }
    d.historial.filas = [f];
    instalarServidor({ "/api/v1/juegos/BALOTO/resultados": respuesta(d) }); renderizar("/juegos/BALOTO/resultados");
    expect((await screen.findByRole("alert")).dataset.codigo).toBe("estructura_no_reconocida");
    expect(screen.queryByRole("region", { name: "Emisiones y resultados" })).toBeNull();
  });
});

describe("identidad, filtros y navegación", () => {
  it.each(["modelo", "cartera"] as const)("rechaza ficha de %s de otro juego o identidad", async (tipo) => {
    const d = tipo === "modelo" ? fichaModelo() : fichaCartera();
    d.juego = "MILOTO";
    const url = muestra(`BALOTO--${tipo}`).url;
    instalarServidor({ [url]: respuesta(d) }); renderizar(rutaFicha(tipo));
    const a = await screen.findByRole("alert"); expect(a.dataset.codigo).toBe("estructura_no_reconocida");
    expect(document.querySelector(`[data-${tipo}]`)).toBeNull();
  });
  it("no atribuye a una identidad la ficha de otra versión", async () => {
    const d = fichaModelo(); d.modelo.clave = "b".repeat(64);
    instalarServidor({ [muestra("BALOTO--modelo").url]: respuesta(d) }); renderizar(rutaFicha("modelo"));
    expect((await screen.findByRole("alert")).dataset.codigo).toBe("estructura_no_reconocida");
  });
  it.each(["modelos", "carteras"] as const)("rechaza un elemento de otro juego en %s", async (grupo) => {
    const d = muestra(`BALOTO--${grupo}`).cuerpo as ModelosGuardados | CarterasGuardadas;
    d.elementos[0]!.juego = "MILOTO";
    const api = grupo === "modelos" ? "modelos-guardados" : "carteras-guardadas";
    instalarServidor({ [`/api/v1/juegos/BALOTO/${api}`]: respuesta(d) }); renderizar(`/juegos/BALOTO/${grupo}`);
    expect((await screen.findByRole("alert")).dataset.codigo).toBe("estructura_no_reconocida");
  });
  it.each(["otra línea", "otro juego", "otro tipo", "otro filtro"])("no atribuye resultados de %s", async (caso) => {
    const d = resultados();
    if (caso === "otra línea") d.historial.filas[0]!.clave_linea = "laboratorio:ajeno-v1";
    if (caso === "otro juego") d.historial.filas[0]!.juego = "MILOTO";
    if (caso === "otro tipo") d.historial.filas[0]!.tipo = "retrospectiva";
    if (caso === "otro filtro") d.filtros.hasta = 2180;
    instalarServidor({ "/api/v1/juegos/BALOTO/resultados": respuesta(d) }); renderizar("/juegos/BALOTO/resultados");
    expect((await screen.findByRole("alert")).dataset.codigo).toBe("estructura_no_reconocida");
    expect(screen.queryByRole("region", { name: "Emisiones y resultados" })).toBeNull();
  });
  it.each(GRUPOS)("$grupo: página en enlace directo y atrás/adelante mantienen URL y filas", async ({ grupo, api, region }) => {
    const { deApi } = instalarServidor(); renderizar(`/juegos/BALOTO/${grupo}?por_pagina=1&pagina=1`);
    await screen.findByRole("region", { name: region });
    fireEvent.click(screen.getByRole("link", { name: "Página siguiente" }));
    await waitFor(() => expect(screen.getByTestId("ubicacion").textContent).toBe(`/juegos/BALOTO/${grupo}?por_pagina=1&pagina=2`));
    await screen.findByRole("region", { name: region });
    expect(deApi()).toContain(`/api/v1/juegos/BALOTO/${api}?pagina=2&por_pagina=1`);
    fireEvent.click(screen.getByTestId("atras"));
    await waitFor(() => expect(screen.getByTestId("ubicacion").textContent).toContain("pagina=1"));
    await screen.findByRole("region", { name: region });
    fireEvent.click(screen.getByTestId("adelante"));
    await waitFor(() => expect(screen.getByTestId("ubicacion").textContent).toContain("pagina=2"));
    await screen.findByRole("region", { name: region });
  });
  it.each(GRUPOS)("$grupo: respuesta tardía de otro juego no sustituye la vigente", async ({ grupo, api, region }) => {
    const pendiente = diferida<Respuesta>();
    const { deApi } = instalarServidor({ [`/api/v1/juegos/BALOTO/${api}`]: () => pendiente.promesa });
    renderizar(`/juegos/BALOTO/${grupo}`, `/juegos/MILOTO/${grupo}`);
    await screen.findByRole("region", { name: region });
    fireEvent.click(screen.getByTestId("atras"));
    await waitFor(() => expect(deApi()).toContain(`/api/v1/juegos/BALOTO/${api}`));
    fireEvent.click(screen.getByTestId("adelante"));
    await screen.findByRole("region", { name: region });
    await act(async () => { pendiente.resolver(muestra(`BALOTO--${grupo}`)); });
    expect(screen.getByTestId("ubicacion").textContent).toBe(`/juegos/MILOTO/${grupo}`);
    expect(screen.getByRole("region", { name: region })).toBeTruthy();
    expect(document.querySelector("[data-clave]")?.getAttribute("data-clave")).not.toBe((muestra("BALOTO--modelos").cuerpo as ModelosGuardados).elementos[0]?.clave);
  });
  it.each(GRUPOS)("$grupo: aplicar un filtro descarta la respuesta anterior todavía pendiente", async ({ grupo, api }) => {
    const pendiente = diferida<Respuesta>();
    const url = `/api/v1/juegos/BALOTO/${api}`;
    const vacio = muestra(`BALOTO--${grupo}--vacio`);
    let etiqueta: string, valor: string, consulta: string;
    if (grupo === "modelos") {
      etiqueta = "Perfil"; valor = "reducido"; consulta = "perfil=reducido";
      (vacio.cuerpo as ModelosGuardados).perfil = valor;
    } else if (grupo === "carteras") {
      etiqueta = "Objetivo desde"; valor = "999999"; consulta = "desde=999999";
      (vacio.cuerpo as CarterasGuardadas).desde = Number(valor);
    } else {
      etiqueta = "Objetivo exacto (prioritario)"; valor = "999999"; consulta = "objetivo=999999";
      (vacio.cuerpo as ResultadosGuardados).filtros.objetivo = Number(valor);
    }
    const { deApi } = instalarServidor({ [url]: () => pendiente.promesa, [`${url}?${consulta}`]: vacio });
    renderizar(`/juegos/BALOTO/${grupo}`);
    await waitFor(() => expect(deApi()).toContain(url));
    fireEvent.change(screen.getByLabelText(etiqueta), { target: { value: valor } });
    fireEvent.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    await waitFor(() => expect(document.querySelector("[data-estado=vacio]")).not.toBeNull());
    expect(screen.getByTestId("ubicacion").textContent).toBe(`/juegos/BALOTO/${grupo}?${consulta}`);
    await act(async () => { pendiente.resolver(muestra(`BALOTO--${grupo}`)); });
    expect(document.querySelector("[data-estado=vacio]")).not.toBeNull();
    expect(document.querySelector("[data-clave]")).toBeNull();
    expect(document.querySelector("tr[data-estado=incluido]")).toBeNull();
    expect(deApi().filter((u) => u === `${url}?${consulta}`)).toHaveLength(1);
  });
  it.each(["modelo", "cartera"] as const)("ficha de %s: cambiar de versión descarta una respuesta tardía", async (tipo) => {
    const actual = muestra(`BALOTO--${tipo}`), anterior = muestra(`BALOTO--${tipo}--anterior`);
    const pendiente = diferida<Respuesta>();
    const { deApi } = instalarServidor({ [anterior.url]: () => pendiente.promesa });
    const ruta = (url: string) => url.replace("/api/v1", "").replace("modelos-guardados", "modelos").replace("carteras-guardadas", "carteras");
    renderizar(ruta(anterior.url), ruta(actual.url));
    const clave = tipo === "modelo" ? (actual.cuerpo as FichaModeloGuardado).modelo.clave : (actual.cuerpo as FichaCarteraGuardada).cartera.clave;
    await waitFor(() => expect(document.querySelector(`[data-${tipo}]`)?.getAttribute(`data-${tipo}`)).toBe(clave));
    fireEvent.click(screen.getByTestId("atras"));
    await waitFor(() => expect(deApi()).toContain(anterior.url));
    fireEvent.click(screen.getByTestId("adelante"));
    await waitFor(() => expect(document.querySelector(`[data-${tipo}]`)?.getAttribute(`data-${tipo}`)).toBe(clave));
    await act(async () => { pendiente.resolver(anterior); });
    expect(document.querySelector(`[data-${tipo}]`)?.getAttribute(`data-${tipo}`)).toBe(clave);
    expect(screen.getByTestId("ubicacion").textContent).toBe(ruta(actual.url));
  });
  it.each(GRUPOS)("$grupo: 429 conserva Retry-After y solo reintenta por acción", async ({ grupo, api }) => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const url = `/api/v1/juegos/BALOTO/${api}`;
    const { deApi } = instalarServidor({ [url]: muestra("global--error--429") });
    renderizar(`/juegos/BALOTO/${grupo}`);
    const a = await screen.findByRole("alert"); expect(a.dataset.codigo).toBe("limite_excedido");
    expect(a.textContent).toContain("Podrás reintentar en 12 s.");
    for (let n = 0; n < 13; n++) await act(async () => { vi.advanceTimersByTime(1000); });
    expect(deApi().filter((u) => u === url)).toHaveLength(1);
    const boton = within(a).getByRole("button", { name: "Reintentar" }) as HTMLButtonElement;
    expect(boton.disabled).toBe(false);
    fireEvent.click(boton);
    await waitFor(() => expect(deApi().filter((u) => u === url)).toHaveLength(2));
  });
});
