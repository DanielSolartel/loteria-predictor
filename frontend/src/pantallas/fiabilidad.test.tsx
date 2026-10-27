/**
 * Fase 9.3: explicacion, clasificacion de candidatos y fiabilidad observada en
 * pantallas completas (StrictMode) con las respuestas sinteticas de la API real.
 * Comprueba presupuesto de consultas, cartera seleccionada y su corte,
 * ausencias, alteraciones, base caida, estados y errores.
 */
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { instalarServidor, muestra, renderizar } from "../pruebas/servidor";

const ubicacion = () => screen.getByTestId("ubicacion").textContent;
const consultas = (lista: string[], ruta: string) => lista.filter((u) => new URL(u, "http://x").pathname === ruta);
const seccionFiabilidad = async () => {
  const control = await waitFor(() => screen.queryByRole("button", { name: "Consultar fiabilidad" }) ??
    screen.getByRole("region", { name: /Fiabilidad hasta el sorteo/ }));
  if (control.tagName === "BUTTON") fireEvent.click(control);
  return (await screen.findByRole("region", { name: /Fiabilidad hasta el sorteo/ })) as HTMLElement;
};

describe("prediccion: clasificacion y explicacion", () => {
  it("Baloto: explicación y corte; carga automática de cuatro fichas y fiabilidad explícita de tres", async () => {
    const { deApi } = instalarServidor();
    renderizar("/juegos/BALOTO/prediccion");
    expect(await screen.findByText(/Clasificación de candidatos/)).toBeTruthy();
    expect(document.querySelector("[data-clasificacion=numeros]")).not.toBeNull();
    expect(document.querySelector("[data-superbalota=aparte]")?.textContent).toContain("Superbalota (16 superbalotas; uniforme = 1/16)");
    expect(screen.getByRole("region", { name: /Números más probables \(10 de 43\)/ })).toBeTruthy();
    expect(screen.getByRole("region", { name: /Números menos probables \(10 de 43\)/ })).toBeTruthy();
    // Referencia uniforme junto a cada probabilidad emitida (formato de la consola).
    const superbalota = screen.getByRole("region", { name: /^Superbalota \(16/ });
    expect(within(superbalota).getAllByRole("row")[1]?.textContent).toContain("0.109375");
    expect(within(superbalota).getAllByRole("row")[1]?.textContent).toContain("0.062500");
    expect(within(superbalota).getAllByRole("row")[1]?.textContent).toContain("+0.046875");
    expect(within(superbalota).getAllByRole("row")[1]?.textContent).toContain("1.750");
    expect(document.querySelector("[data-importancias=disponible]")).not.toBeNull();
    expect(screen.getByText(/candidato \(identidad del candidato\)/)).toBeTruthy();
    expect(document.querySelector("[data-corte=entrada]")?.textContent).toContain("2192");
    expect(document.querySelector("[data-corte=entrenamiento]")?.textContent).toContain("2185");
    expect(document.querySelector("[data-corte=entrenamiento]")?.textContent).toContain("Versión registrada congelada");
    expect(document.querySelector("[data-registrado='1']")).not.toBeNull();
    expect(screen.getByText(/coinciden con los guardados/)).toBeTruthy();
    const automaticas = deApi().slice();
    expect(automaticas.sort()).toEqual(["/api/v1/juegos", "/api/v1/juegos/BALOTO/predicciones"]);
    expect(automaticas.reduce((n, u) => n + (u === "/api/v1/juegos" ? 1 : 3), 0)).toBe(4);
    const fiabilidad = await seccionFiabilidad();
    expect(document.querySelector("[data-fiabilidad-corte='2192']")).not.toBeNull();
    expect(within(fiabilidad).getAllByText("estimable").length).toBeGreaterThan(0);
    expect(screen.getByText(/Positivo: mayor pérdida que la uniforme; negativo: menor pérdida en esa/)).toBeTruthy();
    expect(screen.getByText(/no acredita ventaja/)).toBeTruthy();
    const api = deApi();
    expect(consultas(api, "/api/v1/juegos/BALOTO/predicciones")).toEqual(["/api/v1/juegos/BALOTO/predicciones"]);
    expect(consultas(api, "/api/v1/juegos/BALOTO/fiabilidad")).toEqual(["/api/v1/juegos/BALOTO/fiabilidad?hasta=2192"]);
    expect(api.slice(automaticas.length)).toEqual(["/api/v1/juegos/BALOTO/fiabilidad?hasta=2192"]); // acción explícita: 3
    expect(api).toHaveLength(3); // todas las consultas, incluido el catálogo
  });

  it("elegir otra cartera conserva su corte y exige otra consulta explícita de fiabilidad", async () => {
    const anterior = muestra("BALOTO--predicciones--anterior");
    const clave = (anterior.cuerpo as { prediccion: { clave: string } }).prediccion.clave;
    const { deApi } = instalarServidor();
    renderizar("/juegos/BALOTO/prediccion");
    await seccionFiabilidad();
    fireEvent.click(await screen.findByRole("link", { name: "Ver la predicción del objetivo 2191" }));
    await waitFor(() => expect(ubicacion()).toBe(`/juegos/BALOTO/prediccion?cartera=${clave}`));
    await waitFor(() => expect(document.querySelector("[data-fiabilidad-corte='2190']")).not.toBeNull());
    expect(consultas(deApi(), "/api/v1/juegos/BALOTO/fiabilidad")).toEqual(["/api/v1/juegos/BALOTO/fiabilidad?hasta=2192"]);
    expect(screen.queryByRole("region", { name: "Fiabilidad hasta el sorteo 2192" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Consultar fiabilidad" }));
    expect(await screen.findByRole("region", { name: "Fiabilidad hasta el sorteo 2190" })).toBeTruthy();
    expect(document.querySelector("[data-corte=entrada]")?.textContent).toContain("2190");
    const api = deApi();
    expect(api).toContain(`/api/v1/juegos/BALOTO/predicciones?cartera=${clave}`);
    expect(consultas(api, "/api/v1/juegos/BALOTO/fiabilidad")).toEqual([
      "/api/v1/juegos/BALOTO/fiabilidad?hasta=2192",
      "/api/v1/juegos/BALOTO/fiabilidad?hasta=2190",
    ]);
    // La evidencia al corte 2190 no incluye los resultados posteriores: 40 sorteos frente a 42.
    const fila = document.querySelector("[data-fiabilidad-corte='2190'] tr[data-evaluacion=seguimiento]");
    expect(fila?.textContent).toContain("40");
    fireEvent.click(screen.getByTestId("atras"));
    await waitFor(() => expect(ubicacion()).toBe("/juegos/BALOTO/prediccion"));
    await waitFor(() => expect(document.querySelector("[data-fiabilidad-corte='2192']")).not.toBeNull());
    expect(screen.getByRole("button", { name: "Consultar fiabilidad" })).toBeTruthy();
    expect(screen.queryByRole("region", { name: /Fiabilidad hasta el sorteo/ })).toBeNull();
  });

  it("ColorLoto: pares numero-color con su multiplicidad, numeros y colores aparte e importancias que no aplican", async () => {
    instalarServidor();
    renderizar("/juegos/COLORLOTO/prediccion");
    expect(await screen.findByText(/Clasificación de candidatos/)).toBeTruthy();
    expect(document.querySelector("[data-clasificacion=pares]")).not.toBeNull();
    const fuertes = screen.getByRole("region", { name: /^Pares más probables/ });
    expect(within(fuertes).getAllByRole("columnheader").map((c) => c.textContent)).toContain("En 6 balotas");
    expect(fuertes.querySelector(".color-swatch")).not.toBeNull();
    expect(within(fuertes).getAllByRole("row")[1]?.textContent).toMatch(/1\s*amarillo/);
    expect(screen.getByRole("region", { name: /^Números por separado/ })).toBeTruthy();
    expect(screen.getByRole("region", { name: /^Colores por separado/ })).toBeTruthy();
    expect(document.querySelector("[data-superbalota]")).toBeNull();
    expect(document.querySelector("[data-importancias=no_disponible]")?.textContent).toContain("no aplica");
    const fiabilidad = await seccionFiabilidad();
    expect(within(fiabilidad).getByText(/^0\.00000 \[0\.00000, 0\.00000\]$/)).toBeTruthy();
  });

  it("sin explicacion guardada: lo informa, mantiene la clasificacion de la cartera y no la genera", async () => {
    const { deApi } = instalarServidor();
    renderizar("/juegos/BALOTO_REVANCHA/prediccion");
    expect(await screen.findByText(/no tiene una explicación guardada vigente/)).toBeTruthy();
    expect(screen.getByText("sin explicación guardada")).toBeTruthy();
    expect(document.querySelector("[data-explicacion=ausente]")).not.toBeNull();
    expect(document.querySelector("[data-corte=entrenamiento]")?.textContent).toContain("No informado (sin explicación guardada)");
    expect(document.querySelector("[data-clasificacion=numeros]")).not.toBeNull();
    const fiabilidad = await seccionFiabilidad();
    expect(within(fiabilidad).getAllByText(/sin datos/).length).toBeGreaterThan(0);
    expect(deApi().every((u) => !u.includes("explicar"))).toBe(true);
  });

  it("explicacion alterada: no se muestra y se dice por que", async () => {
    instalarServidor({ "/api/v1/juegos/MILOTO/predicciones": muestra("MILOTO--predicciones--explicacion_alterada") });
    renderizar("/juegos/MILOTO/prediccion");
    const aviso = await screen.findByText(/porque su almacén no la verifica/);
    expect(aviso.textContent).toContain("contenido alterado");
    expect(document.querySelector("[data-explicacion=ausente]")).not.toBeNull();
    expect(document.querySelector("[data-importancias]")).toBeNull();
  });

  it("base de la Fase 4 caida: la prediccion guardada se sigue mostrando y la fiabilidad dice que no se sabe", async () => {
    instalarServidor({
      "/api/v1/juegos/MILOTO/predicciones": muestra("MILOTO--predicciones--sin_base"),
      "/api/v1/juegos/MILOTO/fiabilidad": muestra("MILOTO--fiabilidad--sin_base"),
    });
    renderizar("/juegos/MILOTO/fiabilidad");
    expect(await screen.findByText(/no disponible: no se sabe si las emisiones tienen resultado/)).toBeTruthy();
    expect(screen.getAllByText(/base no disponible: la base no respondió/).length).toBeGreaterThan(0);
    renderizar("/juegos/MILOTO/prediccion");
    expect((await screen.findAllByText(/base no disponible/)).length).toBeGreaterThan(0);
    expect(document.querySelector("[data-prediccion]")).not.toBeNull();
  });
});

describe("fiabilidad observada", () => {
  it("separa seguimiento, retrospectiva y receta; diferencias positiva y negativa, intervalos que cruzan 0 y ausentes", async () => {
    const { deApi } = instalarServidor();
    renderizar("/juegos/BALOTO/fiabilidad");
    expect(await screen.findByRole("heading", { name: "Fiabilidad observada" })).toBeTruthy();
    expect(await screen.findByText("Todos los resultados observados en la base consultada.")).toBeTruthy();
    const lineas = document.querySelectorAll("[data-linea]");
    expect(lineas).toHaveLength(2);
    const [carteras, laboratorio] = [...lineas] as HTMLElement[];
    const seg = carteras?.querySelector("[data-evaluacion=seguimiento]") as HTMLElement;
    expect(seg.dataset.estado).toBe("estimable");
    expect(seg.textContent).toContain("Media en esta muestra: mayor pérdida que la uniforme. El intervalo numérico no incluye 0: está por encima.");
    expect(seg.querySelector("[data-exclusiones='2']")?.textContent).toContain("vectores fuente distintos en el objetivo");
    expect(seg.querySelector("[data-componente=superbalota]")).not.toBeNull();
    const ret = carteras?.querySelector("[data-evaluacion=retrospectiva]") as HTMLElement;
    expect(ret.dataset.estado).toBe("muestra_insuficiente");
    expect(ret.textContent).toContain("Muestra insuficiente para un intervalo.");
    expect(within(ret).getAllByText("sin intervalo").length).toBeGreaterThan(0);
    const labSeg = laboratorio?.querySelector("[data-evaluacion=seguimiento]") as HTMLElement;
    expect(labSeg.textContent).toContain("Media en esta muestra: menor pérdida que la uniforme. El intervalo numérico no incluye 0: está por debajo.");
    expect(labSeg.textContent).toContain("No acredita ventaja futura");
    const labRet = laboratorio?.querySelector("[data-evaluacion=retrospectiva]") as HTMLElement;
    expect(labRet.querySelector("[data-metrica=diferencia_log_loss]")?.textContent).toContain("El intervalo numérico incluye 0.");
    const receta = document.querySelector("[data-receta]") as HTMLElement;
    expect(receta.dataset.receta).toBe("muestra_insuficiente");
    expect(receta.textContent).toContain("informe de procedencia de la versión registrada");
    expect(receta.querySelector("[data-componente=superbalota]")?.textContent).toContain("el informe solo guarda agregados de la superbalota");
    expect(screen.getByText(/Método \(fase4-fiabilidad-1\)/)).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/puntuación de confianza:|confianza alta|confianza media|confianza baja/);
    expect(deApi().filter((u) => u !== "/api/v1/juegos")).toEqual(["/api/v1/juegos/BALOTO/fiabilidad"]);
  });

  it("el corte va en la URL: aplicar, atras y quitar el corte", async () => {
    const { deApi } = instalarServidor();
    renderizar("/juegos/BALOTO/fiabilidad");
    await screen.findByText("Todos los resultados observados en la base consultada.");
    fireEvent.change(screen.getByLabelText("Corte (hasta el sorteo)"), { target: { value: "2190" } });
    fireEvent.click(screen.getByRole("button", { name: "Aplicar" }));
    await waitFor(() => expect(ubicacion()).toBe("/juegos/BALOTO/fiabilidad?hasta=2190"));
    expect(await screen.findByText(/Solo objetivos hasta el sorteo 2190. Este filtro no acredita/)).toBeTruthy();
    expect(deApi()).toContain("/api/v1/juegos/BALOTO/fiabilidad?hasta=2190");
    fireEvent.click(screen.getByTestId("atras"));
    await waitFor(() => expect(ubicacion()).toBe("/juegos/BALOTO/fiabilidad"));
    expect(await screen.findByText("Todos los resultados observados en la base consultada.")).toBeTruthy();
  });

  it("un corte no valido llega como 422 con el detalle del parametro", async () => {
    instalarServidor({ "/api/v1/juegos/BALOTO/fiabilidad?hasta=0": muestra("BALOTO--fiabilidad--error--422") });
    renderizar("/juegos/BALOTO/fiabilidad?hasta=0");
    const a = (await screen.findByRole("alert")) as HTMLElement;
    expect(a.dataset.codigo).toBe("parametro_no_valido");
    expect(a.textContent).toContain("query › hasta: Input should be greater than or equal to 1");
  });

  it("429 en la fiabilidad al corte: el resto de la prediccion se muestra y el reintento es manual", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { deApi } = instalarServidor({ "/api/v1/juegos/BALOTO/fiabilidad?hasta=2192": muestra("global--error--429") });
    renderizar("/juegos/BALOTO/prediccion");
    fireEvent.click(await screen.findByRole("button", { name: "Consultar fiabilidad" }));
    const a = (await screen.findByRole("alert")) as HTMLElement;
    expect(a.dataset.codigo).toBe("limite_excedido");
    expect(a.closest("[data-fiabilidad-corte]")).not.toBeNull();
    expect(document.querySelector("[data-clasificacion]")).not.toBeNull();
    const antes = consultas(deApi(), "/api/v1/juegos/BALOTO/fiabilidad").length;
    for (let s = 0; s < 13; s += 1) {
      await act(async () => {
        vi.advanceTimersByTime(1000);
      });
    }
    expect(consultas(deApi(), "/api/v1/juegos/BALOTO/fiabilidad").length).toBe(antes);
    instalarServidor();
    await waitFor(() => expect((within(a).getByRole("button", { name: "Reintentar" }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(within(a).getByRole("button", { name: "Reintentar" }));
    expect(await seccionFiabilidad()).toBeTruthy();
  });

  it("la pestaña Fiabilidad de cada juego lleva a su pantalla y las tablas son alcanzables con el teclado", async () => {
    instalarServidor();
    renderizar("/juegos/MILOTO/prediccion");
    const pestana = await screen.findByRole("link", { name: "Fiabilidad" });
    fireEvent.click(pestana);
    await waitFor(() => expect(ubicacion()).toBe("/juegos/MILOTO/fiabilidad"));
    expect(await screen.findByText("Todos los resultados observados en la base consultada.")).toBeTruthy();
    const regiones = screen.getAllByRole("region").filter((r) => r.classList.contains("tabla-desplazable"));
    expect(regiones.length).toBeGreaterThan(0);
    expect(regiones.every((r) => r.tabIndex === 0)).toBe(true);
  });
});
