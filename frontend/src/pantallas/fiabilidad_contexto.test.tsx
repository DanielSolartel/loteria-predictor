/** Regresiones F93-REL-01/F93-LIM-01 por la pantalla pública, con datos sintéticos. */
import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { type Fiabilidad, type Predicciones } from "../api/presentacion";
import { diferida, instalarServidor, muestra, renderizar, type Respuesta } from "../pruebas/servidor";

const RUTA_P = "/api/v1/juegos/BALOTO/predicciones";
const RUTA_F = "/api/v1/juegos/BALOTO/fiabilidad?hasta=2192";
const prediccion = () => muestra("BALOTO--predicciones").cuerpo as Predicciones;
const fiabilidad = () => muestra("BALOTO--fiabilidad--corte-2192").cuerpo as Fiabilidad;
const respuesta = (cuerpo: unknown): Respuesta => ({ estado: 200, cuerpo });
const tabla = () => screen.queryByRole("region", { name: /Fiabilidad hasta el sorteo/ });
const llamadasDeFiabilidad = (urls: string[]) => urls.filter((url) => /\/fiabilidad(?:\?|$)/.test(url));
function fichas(urls: string[]) {
  return urls.reduce((suma, url) => {
    if (url === "/api/v1/juegos") return suma + 1;
    if (/\/predicciones(?:\?|$)|\/fiabilidad(?:\?|$)/.test(url)) return suma + 3;
    throw new Error(`Consulta automática sin coste contabilizado: ${url}`);
  }, 0);
}
async function cargada() {
  await screen.findByText(/Clasificación de candidatos/);
  await act(async () => { await new Promise((resolver) => setTimeout(resolver, 15)); });
}
/** También permite ejecutar las regresiones de atribución sobre v1, que consultaba automáticamente. */
async function consultarSiEsManual() {
  const boton = screen.queryByRole("button", { name: "Consultar fiabilidad" });
  if (boton) fireEvent.click(boton);
}
async function ausenciaExplicita() {
  await screen.findByText(/La fiabilidad no está disponible para esta cartera/);
  expect(tabla()).toBeNull();
  expect(screen.queryByText("Receta en su informe")).toBeNull();
  expect(document.querySelector("[data-fiabilidad-contexto=no_correspondiente]")).not.toBeNull();
  const enlace = screen.getByRole("link", { name: "Fiabilidad general de la configuración actual" });
  expect(enlace.getAttribute("href")).toBe("/juegos/BALOTO/fiabilidad");
}

describe("fiabilidad de la cartera seleccionada: identidad completa", () => {
  it("contexto constante: conserva la cartera, su corte y la evidencia de la misma versión", async () => {
    const p = prediccion();
    instalarServidor({ [RUTA_P]: respuesta(p), [RUTA_F]: respuesta(fiabilidad()) });
    renderizar("/juegos/BALOTO/prediccion?cartera=" + p.prediccion!.clave);
    await cargada();
    await consultarSiEsManual();
    const region = await screen.findByRole("region", { name: "Fiabilidad hasta el sorteo 2192" });
    expect(region.textContent).toContain("Random Forest");
    expect(region.textContent).toContain("Receta en su informe");
    expect(document.querySelector("[data-prediccion]")?.getAttribute("data-prediccion")).toBe(p.prediccion!.clave);
    expect(document.querySelector("[data-corte=entrada]")?.textContent).toContain("2192");
  });

  const casos: { nombre: string; cambiar: (p: Predicciones, f: Fiabilidad) => void }[] = [
    { nombre: "otro modelo aunque el corte siga siendo el mismo", cambiar: (_p, f) => {
      f.registrado = null;
      f.lineas.forEach((l) => { l.linea = l.linea.replace("random_forest_clasificador-v1-reg1", "uniforme-v1"); l.nombre = "Uniforme ajena"; });
    } },
    { nombre: "otra receta de la misma familia", cambiar: (_p, f) => { f.lineas.forEach((l) => { l.linea = l.linea.replace("-v1-", "-v2-"); }); } },
    { nombre: "otro perfil de la misma receta", cambiar: (_p, f) => { f.lineas.forEach((l) => { l.linea = l.linea.replace("-reducido", "-predeterminado"); }); } },
    { nombre: "otro número registrado", cambiar: (_p, f) => { f.registrado!.numero = 2; f.lineas.forEach((l) => { l.linea = l.linea.replace("-reg1-", "-reg2-"); }); } },
    { nombre: "otra clave con el mismo número registrado y las mismas líneas", cambiar: (_p, f) => { f.registrado!.clave = "a".repeat(64); } },
    { nombre: "referencia registrada ausente en la consulta", cambiar: (_p, f) => { f.registrado = null; } },
    { nombre: "versión registrada incompatible", cambiar: (_p, f) => { f.registrado!.estado = "incompatible"; } },
    { nombre: "versión registrada no encontrada", cambiar: (_p, f) => { f.registrado!.estado = "no_encontrado"; } },
    { nombre: "otro juego", cambiar: (_p, f) => { f.juego = "BALOTO_REVANCHA"; } },
    { nombre: "otro filtro de objetivos", cambiar: (_p, f) => { f.hasta = 2190; } },
    { nombre: "línea de cartera ausente", cambiar: (_p, f) => { f.lineas = f.lineas.filter((l) => l.linea.startsWith("laboratorio:")); } },
    { nombre: "una línea correcta acompañada por otra ajena", cambiar: (_p, f) => {
      f.lineas.push({ ...structuredClone(f.lineas[0]!), linea: "carteras:uniforme-v1-reducido", nombre: "Uniforme ajena" });
    } },
    { nombre: "identidad de línea no informada por la cartera histórica", cambiar: (p) => { p.prediccion!.linea_de_modelo = null; } },
    { nombre: "perfil de la cartera incoherente con su identificador", cambiar: (p) => { p.prediccion!.linea_de_modelo!.perfil = "predeterminado"; } },
    { nombre: "versión de la cartera incoherente con su identificador", cambiar: (p) => { p.prediccion!.linea_de_modelo!.version = "2"; } },
    { nombre: "modelo de la cartera incoherente con su identidad de línea", cambiar: (p) => { p.prediccion!.modelo.id = "uniforme"; } },
  ];
  it.each(casos)("no atribuye cifras ni receta: $nombre", async ({ cambiar }) => {
    const p = prediccion(); const f = fiabilidad();
    cambiar(p, f);
    instalarServidor({ [RUTA_P]: respuesta(p), [RUTA_F]: respuesta(f) });
    renderizar("/juegos/BALOTO/prediccion?cartera=" + p.prediccion!.clave);
    await cargada();
    await consultarSiEsManual();
    await ausenciaExplicita();
    expect(document.querySelector("[data-prediccion]")?.getAttribute("data-prediccion")).toBe(p.prediccion!.clave);
  });

  it.each(["reducido", "predeterminado"])("acepta la identidad completa no registrada de ColorLoto, perfil %s", async (perfil) => {
    const p = muestra("COLORLOTO--predicciones").cuerpo as Predicciones;
    const f = muestra("COLORLOTO--fiabilidad--corte-90").cuerpo as Fiabilidad;
    if (perfil === "predeterminado") {
      p.prediccion!.linea_de_modelo!.perfil = perfil;
      p.prediccion!.linea_de_modelo!.id = p.prediccion!.linea_de_modelo!.id.replace("-reducido", "");
      p.prediccion!.linea = p.prediccion!.linea.replace("-reducido", "");
      p.prediccion!.explicacion!.metodo.perfil = perfil;
      f.lineas.forEach((l) => { l.linea = l.linea.replace("-reducido", ""); });
    }
    instalarServidor({
      "/api/v1/juegos/COLORLOTO/predicciones": respuesta(p),
      "/api/v1/juegos/COLORLOTO/fiabilidad?hasta=90": respuesta(f),
    });
    renderizar("/juegos/COLORLOTO/prediccion");
    await cargada();
    await consultarSiEsManual();
    const region = await screen.findByRole("region", { name: "Fiabilidad hasta el sorteo 90" });
    expect(region.textContent).toContain("uniforme");
    expect(document.querySelector("[data-fiabilidad-contexto=no_correspondiente]")).toBeNull();
  });

  it("cambio de configuración entre las respuestas: conserva la cartera y rechaza la evidencia nueva", async () => {
    const pendiente = diferida<Respuesta>();
    const p = prediccion(); const f = fiabilidad();
    const { deApi } = instalarServidor({ [RUTA_P]: respuesta(p), [RUTA_F]: () => pendiente.promesa });
    renderizar("/juegos/BALOTO/prediccion");
    await cargada();
    await consultarSiEsManual();
    await waitFor(() => expect(deApi()).toContain(RUTA_F));
    // La respuesta de predicción ya llegó; la de fiabilidad observa ahora otra configuración.
    f.registrado = null;
    f.lineas.forEach((l) => { l.linea = l.linea.replace("random_forest_clasificador-v1-reg1", "uniforme-v1"); });
    await act(async () => { pendiente.resolver(respuesta(f)); });
    await ausenciaExplicita();
    expect(document.querySelector("[data-prediccion]")?.getAttribute("data-prediccion")).toBe(p.prediccion!.clave);
    expect(document.querySelector("[data-corte=entrada]")?.textContent).toContain("2192");
  });
});

describe("presupuesto completo y consulta explícita", () => {
  it.each(["directa", "enlace guardado"])("carga %s con memoria vacía: cuenta catálogo y no supera seis fichas", async (entrada) => {
    const { deApi, llamadas } = instalarServidor();
    const clave = prediccion().prediccion!.clave;
    renderizar("/juegos/BALOTO/prediccion" + (entrada === "directa" ? "" : "?cartera=" + clave));
    await cargada();
    expect(deApi()).toContain("/api/v1/juegos");
    expect(fichas(deApi())).toBeLessThanOrEqual(6);
    expect(fichas(deApi())).toBe(4);
    expect(llamadasDeFiabilidad(deApi())).toEqual([]);
    expect(tabla()).toBeNull();
    expect(screen.getByRole("button", { name: "Consultar fiabilidad" })).toBeTruthy();
    expect(llamadas.every((l) => l.init?.method === "GET")).toBe(true);
  });

  it("la acción explícita posterior añade sólo las tres fichas de fiabilidad", async () => {
    const { deApi } = instalarServidor();
    renderizar("/juegos/BALOTO/prediccion");
    await cargada();
    const iniciales = deApi().slice();
    fireEvent.click(screen.getByRole("button", { name: "Consultar fiabilidad" }));
    await screen.findByRole("region", { name: "Fiabilidad hasta el sorteo 2192" });
    expect(fichas(iniciales)).toBe(4);
    expect(deApi().slice(iniciales.length)).toEqual([RUTA_F]);
    expect(fichas(deApi().slice(iniciales.length))).toBe(3);
    expect(screen.queryByText(/evidencia que existía al emitir/)).toBeNull();
  });

  it("navegación histórica y atrás: cada selección pide sólo su predicción hasta otra acción explícita", async () => {
    const { deApi } = instalarServidor();
    const anterior = muestra("BALOTO--predicciones--anterior").cuerpo as Predicciones;
    renderizar("/juegos/BALOTO/prediccion");
    await cargada();
    const iniciales = deApi().length;
    fireEvent.click(screen.getByRole("link", { name: "Ver la predicción del objetivo 2191" }));
    await waitFor(() => expect(document.querySelector("[data-prediccion]")?.getAttribute("data-prediccion")).toBe(anterior.prediccion!.clave));
    expect(deApi().slice(iniciales)).toEqual([RUTA_P + "?cartera=" + anterior.prediccion!.clave]);
    expect(fichas(deApi().slice(iniciales))).toBe(3);
    expect(llamadasDeFiabilidad(deApi())).toEqual([]);
    fireEvent.click(screen.getByRole("button", { name: "Consultar fiabilidad" }));
    await screen.findByRole("region", { name: "Fiabilidad hasta el sorteo 2190" });
    expect(document.querySelector("[data-fiabilidad-corte='2190'] tr[data-evaluacion=seguimiento]")?.textContent).toContain("40");
    fireEvent.click(screen.getByTestId("atras"));
    await waitFor(() => expect(document.querySelector("[data-fiabilidad-corte='2192']")).not.toBeNull());
    expect(tabla()).toBeNull();
    expect(screen.getByRole("button", { name: "Consultar fiabilidad" })).toBeTruthy();
    expect(llamadasDeFiabilidad(deApi())).toEqual(["/api/v1/juegos/BALOTO/fiabilidad?hasta=2190"]);
  });

  it("una respuesta antigua pendiente no se presenta bajo otra selección", async () => {
    const pendiente = diferida<Respuesta>();
    const { deApi } = instalarServidor({ [RUTA_F]: () => pendiente.promesa });
    renderizar("/juegos/BALOTO/prediccion");
    await cargada();
    await consultarSiEsManual();
    await waitFor(() => expect(deApi()).toContain(RUTA_F));
    fireEvent.click(screen.getByRole("link", { name: "Ver la predicción del objetivo 2191" }));
    await waitFor(() => expect(document.querySelector("[data-fiabilidad-corte='2190']")).not.toBeNull());
    expect(tabla()).toBeNull();
    expect(llamadasDeFiabilidad(deApi())).toEqual([RUTA_F]);
    fireEvent.click(screen.getByRole("button", { name: "Consultar fiabilidad" }));
    await screen.findByRole("region", { name: "Fiabilidad hasta el sorteo 2190" });
    await act(async () => { pendiente.resolver(respuesta(fiabilidad())); });
    expect(screen.getByRole("region", { name: "Fiabilidad hasta el sorteo 2190" })).toBeTruthy();
    expect(screen.queryByRole("region", { name: "Fiabilidad hasta el sorteo 2192" })).toBeNull();
  });
});
