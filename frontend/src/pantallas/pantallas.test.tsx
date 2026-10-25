/**
 * Pantallas completas en StrictMode con respuestas sinteticas de la API:
 * estados, errores, filtros en la URL, llamadas reales y avisos.
 */
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { diferida, instalarServidor, muestra, renderizar, type Respuesta } from "../pruebas/servidor";

const ubicacion = () => screen.getByTestId("ubicacion").textContent;
const alerta = async () => (await screen.findByRole("alert")) as HTMLElement;

describe("inicio y marco", () => {
  it("muestra los cuatro juegos con sus reglas y pide /juegos una sola vez en StrictMode", async () => {
    const { deApi } = instalarServidor();
    renderizar("/");
    const main = within(await screen.findByRole("main"));
    for (const nombre of ["Baloto", "Baloto Revancha", "MiLoto", "ColorLoto"]) {
      expect(await main.findByRole("link", { name: nombre })).toBeTruthy();
    }
    expect(main.getAllByText(/5 números de 1 a 43, sin repetición \+ superbalota de 1 a 16/)).toHaveLength(2);
    expect(deApi()).toEqual(["/api/v1/juegos"]);
    expect(screen.getByRole("link", { name: "Saltar al contenido" }).getAttribute("href")).toBe("#contenido");
    expect(screen.getByRole("contentinfo").textContent).toContain("uso experimental no acreditado");
  });

  it("el enlace a la consola solo aparece con un destino local valido", async () => {
    instalarServidor({ "/pasarela/configuracion": { estado: 200, cuerpo: { consola_local: "http://127.0.0.1:8000/", api: "v1" } } });
    renderizar("/");
    const enlace = await screen.findByRole("link", { name: "Consola local" });
    expect(enlace.getAttribute("href")).toBe("http://127.0.0.1:8000/");
    expect(enlace.getAttribute("rel")).toBe("noreferrer");
  });

  it("un destino de consola ajeno no se enlaza", async () => {
    instalarServidor({ "/pasarela/configuracion": { estado: 200, cuerpo: { consola_local: "http://ajeno.example:8000/", api: "v1" } } });
    renderizar("/");
    await within(screen.getByRole("main")).findByRole("link", { name: "Baloto Revancha" });
    expect(screen.queryByRole("link", { name: "Consola local" })).toBeNull();
  });

  it("una ruta desconocida de la SPA muestra no encontrada sin llamar a la API mas alla de /juegos", async () => {
    const { deApi } = instalarServidor();
    renderizar("/otra/cosa");
    expect(await screen.findByRole("heading", { name: "Página no encontrada" })).toBeTruthy();
    expect(deApi()).toEqual(["/api/v1/juegos"]);
  });
});

describe("ficha y resumen", () => {
  it("presenta la frescura informada (atrasado con sus dias) y pide cada recurso una vez", async () => {
    const { deApi } = instalarServidor();
    renderizar("/juegos/BALOTO");
    expect(await screen.findByText("Atrasado: 1945 días")).toBeTruthy();
    expect(screen.getByText(/15\.401\.568 combinaciones/)).toBeTruthy();
    expect(screen.getByText("Frecuencia de números (1–43)")).toBeTruthy();
    expect(deApi().sort()).toEqual(["/api/v1/juegos", "/api/v1/juegos/BALOTO", "/api/v1/juegos/BALOTO/estadisticas/resumen"]);
  });

  it("al dia y sin datos se presentan como los informa el backend", async () => {
    const resumen = muestra("BALOTO--resumen");
    const cuerpo = resumen.cuerpo as { frescura: Record<string, unknown> };
    // Variante derivada de la respuesta sintetica: solo cambia el bloque de frescura.
    cuerpo.frescura = { estado: "al_dia", dias_desde_el_ultimo_sorteo: 2, mensaje: "Último sorteo cargado hace 2 días." };
    instalarServidor({ "/api/v1/juegos/BALOTO/estadisticas/resumen": resumen });
    renderizar("/juegos/BALOTO");
    expect(await screen.findByText("Al día")).toBeTruthy();
    expect(screen.getByText("Último sorteo cargado hace 2 días.")).toBeTruthy();
  });

  it("el corte va en la URL; sin sorteos hasta el corte se dice", async () => {
    const { deApi } = instalarServidor({
      "/api/v1/juegos/BALOTO/estadisticas/resumen?hasta_numero_sorteo=1": muestra("BALOTO--resumen--sin_sorteos"),
    });
    renderizar("/juegos/BALOTO");
    await screen.findByText("Atrasado: 1945 días");
    fireEvent.change(screen.getByLabelText("Corte (hasta el sorteo)"), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "Aplicar" }));
    expect(await screen.findByText("No hay sorteos hasta el corte indicado.")).toBeTruthy();
    expect(ubicacion()).toBe("/juegos/BALOTO?hasta_numero_sorteo=1");
    expect(deApi()).toContain("/api/v1/juegos/BALOTO/estadisticas/resumen?hasta_numero_sorteo=1");
  });

  it("ColorLoto muestra los pares numero-color con el nombre del color", async () => {
    instalarServidor();
    renderizar("/juegos/COLORLOTO");
    expect(await screen.findByText("Frecuencia de colores")).toBeTruthy();
    const ultimo = screen.getByText("Último resultado analizado:").parentElement as HTMLElement;
    expect(ultimo.textContent).toMatch(/2 blanco/);
  });
});

describe("sorteos", () => {
  it("reenvia solo los filtros admitidos desde la URL y pagina con enlaces", async () => {
    const { deApi } = instalarServidor();
    renderizar("/juegos/BALOTO/sorteos?numero_desde=2130&orden=numero_asc&ajeno=1");
    await screen.findByRole("region", { name: "Sorteos" });
    expect(deApi()).toContain("/api/v1/juegos/BALOTO/sorteos?numero_desde=2130&orden=numero_asc");
    expect(deApi().some((u) => u.includes("ajeno"))).toBe(false);
    const siguiente = screen.getByRole("link", { name: "Página siguiente" });
    expect(siguiente.getAttribute("href")).toContain("pagina=2");
  });

  it("el formulario cambia la URL; atras y adelante restauran la vista", async () => {
    const { deApi } = instalarServidor();
    renderizar("/juegos/BALOTO/sorteos");
    await screen.findByRole("region", { name: "Sorteos" });
    fireEvent.change(screen.getByLabelText("Desde el sorteo n.º"), { target: { value: "2135" } });
    fireEvent.click(screen.getByRole("button", { name: "Filtrar" }));
    await waitFor(() => expect(ubicacion()).toBe("/juegos/BALOTO/sorteos?numero_desde=2135"));
    expect((screen.getByLabelText("Desde el sorteo n.º") as HTMLInputElement).value).toBe("2135");
    await waitFor(() => expect(deApi()).toContain("/api/v1/juegos/BALOTO/sorteos?numero_desde=2135"));
    fireEvent.click(screen.getByTestId("atras"));
    await waitFor(() => expect(ubicacion()).toBe("/juegos/BALOTO/sorteos"));
    expect((screen.getByLabelText("Desde el sorteo n.º") as HTMLInputElement).value).toBe("");
    fireEvent.click(screen.getByTestId("adelante"));
    await waitFor(() => expect(ubicacion()).toBe("/juegos/BALOTO/sorteos?numero_desde=2135"));
    expect((screen.getByLabelText("Desde el sorteo n.º") as HTMLInputElement).value).toBe("2135");
  });

  it("vacio: ningun sorteo cumple los filtros", async () => {
    instalarServidor({ "/api/v1/juegos/BALOTO/sorteos?numero_desde=999999": muestra("BALOTO--sorteos--vacio") });
    renderizar("/juegos/BALOTO/sorteos?numero_desde=999999");
    expect(await screen.findByText(/Ningún sorteo cumple los filtros/)).toBeTruthy();
  });

  it("una respuesta antigua no sobrescribe la vigente", async () => {
    const lenta = diferida<Respuesta>();
    const { deApi } = instalarServidor({ "/api/v1/juegos/BALOTO/sorteos?numero_desde=2081": () => lenta.promesa });
    renderizar("/juegos/BALOTO/sorteos?numero_desde=2081");
    await waitFor(() => expect(deApi()).toContain("/api/v1/juegos/BALOTO/sorteos?numero_desde=2081"));
    fireEvent.change(screen.getByLabelText("Desde el sorteo n.º"), { target: { value: "2135" } });
    fireEvent.click(screen.getByRole("button", { name: "Filtrar" }));
    await screen.findByRole("region", { name: "Sorteos" });
    const antes = screen.getByText(/sorteos · página/).textContent;
    const vieja = muestra("BALOTO--sorteos");
    (vieja.cuerpo as { total: number }).total = 999;
    lenta.resolver(vieja);
    await new Promise((r) => setTimeout(r, 20));
    expect(screen.getByText(/sorteos · página/).textContent).toBe(antes);
    expect(screen.queryByText(/999 sorteos/)).toBeNull();
  });

  it("detalle de un sorteo de ColorLoto con sus pares", async () => {
    instalarServidor();
    renderizar("/juegos/COLORLOTO/sorteos/45");
    expect(await screen.findByText("Pares número-color")).toBeTruthy();
    expect(screen.getByRole("main").textContent).toContain("5 amarillo");
  });
});

describe("estadisticas", () => {
  it("el panel enlaza solo las metricas del indice; las anteriores quedan pendientes", async () => {
    instalarServidor();
    renderizar("/juegos/COLORLOTO/estadisticas");
    expect(await screen.findByText("5 métricas con página propia según el índice de la API.")).toBeTruthy();
    const enlazadas = screen.getAllByRole("link").filter((a) => /\/juegos\/COLORLOTO\/estadisticas\/[a-z-]+$/.test(a.getAttribute("href") ?? ""));
    expect(enlazadas).toHaveLength(5);
    expect(screen.getAllByText("Página de detalle pendiente (no está en el índice v1).").length).toBeGreaterThan(0);
  });

  it("la tabla generica conserva los datos adicionales de cada fila", async () => {
    instalarServidor();
    renderizar("/juegos/BALOTO/estadisticas/correlaciones");
    const region = await screen.findByRole("region", { name: "Tabla: Correlaciones de Pearson y Spearman" });
    expect(within(region).getByRole("columnheader", { name: "Datos adicionales" })).toBeTruthy();
    expect(region.textContent).toContain("motivo_p_value");
    expect(region.textContent).toContain("las transiciones N → N+1 comparten sorteos");
  });

  it("el selector de la metrica y el corte van a la URL", async () => {
    const { deApi } = instalarServidor();
    renderizar("/juegos/BALOTO/estadisticas/frecuencia-numeros-por-anio");
    const selector = (await screen.findByLabelText("anio")) as HTMLSelectElement;
    expect(selector.value).toBe("2021");
    fireEvent.change(screen.getByLabelText("Corte (hasta el sorteo)"), { target: { value: "2100" } });
    fireEvent.click(screen.getByRole("button", { name: "Aplicar" }));
    await waitFor(() => expect(ubicacion()).toBe("/juegos/BALOTO/estadisticas/frecuencia-numeros-por-anio?hasta_numero_sorteo=2100&anio=2021"));
    await waitFor(() => expect(deApi()).toContain("/api/v1/juegos/BALOTO/estadisticas/frecuencia-numeros-por-anio?hasta_numero_sorteo=2100&anio=2021"));
  });
});

describe("prediccion guardada", () => {
  it("MiLoto: observado, aciertos, frente a la base, integridad y frescura no informada", async () => {
    instalarServidor();
    renderizar("/juegos/MILOTO/prediccion");
    expect(await screen.findByText(/Predicciones experimentales: describen/)).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Aciertos observados" })).toBeTruthy();
    expect(screen.getByText(/la base avanzó 1 sorteo\(s\) desde el corte/)).toBeTruthy();
    expect(screen.getByText("no informada por esta consulta")).toBeTruthy();
    expect(screen.getByText(/«Base disponible» indica que la base respondió, no que los datos estén al día/)).toBeTruthy();
    expect(screen.getByText(/correcta \(verificada por la API al leerla\)/)).toBeTruthy();
    expect(screen.getByText("Referencia uniforme", { exact: false })).toBeTruthy();
  });

  it("la seleccion del historial va en la URL", async () => {
    const clave = (muestra("MILOTO--predicciones").cuerpo as { prediccion: { clave: string } }).prediccion.clave;
    const { deApi } = instalarServidor();
    renderizar(`/juegos/MILOTO/prediccion?cartera=${clave}`);
    expect(await screen.findByText("seleccionada")).toBeTruthy();
    expect(deApi()).toContain(`/api/v1/juegos/MILOTO/predicciones?cartera=${clave}`);
  });

  it("sin configuracion: lo dice y mantiene el aviso", async () => {
    instalarServidor({ "/api/v1/juegos/BALOTO_REVANCHA/predicciones": muestra("BALOTO_REVANCHA--predicciones--sin_configuracion") });
    renderizar("/juegos/BALOTO_REVANCHA/prediccion");
    expect(await screen.findByText(/el juego no tiene configuración de predicción vigente/)).toBeTruthy();
    expect(screen.getByRole("note").textContent).toContain("experimental no acreditado");
  });
});

describe("simulaciones", () => {
  it("el listado distingue la alterada y el detalle verificado muestra huella y parametros", async () => {
    instalarServidor();
    renderizar("/juegos/COLORLOTO/simulaciones");
    expect(await screen.findByText(/el contenido no corresponde a su huella/)).toBeTruthy();
    expect(document.querySelector("[data-integridad=alterada]")).not.toBeNull();
    const verificada = muestra("COLORLOTO--simulacion--verificada");
    instalarServidor();
    renderizar(verificada.url.replace("/api/v1", ""));
    expect(await screen.findByText("Parámetros (identidad completa)")).toBeTruthy();
    expect(screen.getByText((verificada.cuerpo as { contenido_sha256: string }).contenido_sha256)).toBeTruthy();
  });

  it("integridad alterada (409): no muestra el contenido", async () => {
    const alterada = muestra("COLORLOTO--simulacion--alterada");
    instalarServidor();
    renderizar(alterada.url.replace("/api/v1", ""));
    const a = await alerta();
    expect(a.dataset.codigo).toBe("alterado");
    expect(a.textContent).toContain("Integridad alterada");
    expect(screen.queryByText("Estadísticas comparadas")).toBeNull();
    expect(within(a).queryByRole("button", { name: "Reintentar" })).toBeNull();
  });
});

describe("servicio", () => {
  it("salud y estado del proceso, separados de la automatizacion", async () => {
    instalarServidor();
    renderizar("/servicio");
    expect(await screen.findByText(/No/, { selector: "strong" })).toBeTruthy();
    expect(screen.getByRole("note").textContent).toContain("operación automática");
    expect(await screen.findByRole("region", { name: "Solicitudes por ruta" })).toBeTruthy();
    expect(document.querySelector("[data-salud=ok]")).not.toBeNull();
  });
});

describe("errores", () => {
  it.each([
    ["global--error--401", "no_autenticado", "configuración privada del servidor"],
    ["global--error--404", "no_encontrado", "Juego no admitido"],
    ["global--error--500", "error_interno", "identificador de solicitud"],
    ["global--error--503", "base_no_disponible", "base de datos de la API no está disponible"],
  ])("%s se presenta con su codigo y su solicitud", async (nombre, codigo, texto) => {
    instalarServidor({ "/api/v1/juegos": muestra(nombre) });
    renderizar("/");
    const a = await alerta();
    expect(a.dataset.codigo).toBe(codigo);
    expect(a.textContent).toContain(texto);
    expect(a.textContent).toMatch(/Solicitud: [0-9a-f]{32}/);
  });

  it("422 con los detalles del parametro", async () => {
    instalarServidor({ "/api/v1/juegos/BALOTO/sorteos?pagina=0": muestra("global--error--422") });
    renderizar("/juegos/BALOTO/sorteos?pagina=0");
    const a = await alerta();
    expect(a.textContent).toContain("query › pagina: Input should be greater than or equal to 1");
  });

  it("429: muestra Retry-After, no reintenta solo y deja reintentar a mano tras la espera", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { deApi } = instalarServidor({ "/api/v1/juegos/BALOTO/simulaciones": muestra("global--error--429") });
    renderizar("/juegos/BALOTO/simulaciones");
    const a = await alerta();
    expect(a.textContent).toContain("Podrás reintentar en 12 s.");
    expect(a.textContent).toContain("otras pestañas");
    const boton = within(a).getByRole("button", { name: "Reintentar" }) as HTMLButtonElement;
    expect(boton.disabled).toBe(true);
    const antes = deApi().filter((u) => u.includes("simulaciones")).length;
    for (let s = 0; s < 13; s += 1) {
      await act(async () => {
        vi.advanceTimersByTime(1000);
      });
    }
    expect(deApi().filter((u) => u.includes("simulaciones")).length).toBe(antes);
    await waitFor(() => expect((within(a).getByRole("button", { name: "Reintentar" }) as HTMLButtonElement).disabled).toBe(false));
    instalarServidor();
    fireEvent.click(within(a).getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByRole("region", { name: "Simulaciones guardadas" })).toBeTruthy();
    expect(antes).toBe(1);
  });

  it("estructura no reconocida: no se muestra a medias", async () => {
    instalarServidor({ "/api/v1/juegos/BALOTO/estadisticas/panel": { estado: 200, cuerpo: { juego: {}, grupos: [] } } });
    renderizar("/juegos/BALOTO/estadisticas");
    const a = await alerta();
    expect(a.dataset.codigo).toBe("estructura_no_reconocida");
  });
});
