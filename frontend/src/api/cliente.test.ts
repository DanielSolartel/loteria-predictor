/** Cliente de la pasarela: opciones de fetch, errores, peticiones compartidas y memoria de /juegos. */
import { describe, expect, it } from "vitest";
import { diferida, instalarServidor, muestra } from "../pruebas/servidor";
import { consolaLocal, consultar, ErrorDeConsulta, llamadasDeRed, obtenerJuegos, rutaApi } from "./cliente";
import { decJuegos, decSalud } from "./presentacion";

const senal = () => new AbortController().signal;

async function error(promesa: Promise<unknown>): Promise<ErrorDeConsulta> {
  try {
    await promesa;
  } catch (e) {
    if (e instanceof ErrorDeConsulta) {
      return e;
    }
    throw e;
  }
  throw new Error("se esperaba un error");
}

describe("peticiones", () => {
  it("solo GET del mismo origen, sin credenciales, cookies, cache ni redirecciones", async () => {
    const { llamadas } = instalarServidor();
    await consultar("/api/v1/salud", decSalud, senal());
    const init = llamadas[0]?.init;
    expect(llamadas[0]?.url).toBe("/api/v1/salud");
    expect(init).toMatchObject({ method: "GET", credentials: "omit", cache: "no-store", redirect: "error", referrerPolicy: "no-referrer" });
    const cabeceras = Object.keys((init?.headers ?? {}) as Record<string, string>).map((k) => k.toLowerCase());
    expect(cabeceras).toEqual(["accept"]);
  });

  it("rutaApi codifica segmentos y omite los filtros vacios", () => {
    expect(rutaApi(["juegos", "BALOTO", "sorteos"], { pagina: "2", desde: null, orden: "" })).toBe("/api/v1/juegos/BALOTO/sorteos?pagina=2");
    expect(rutaApi(["juegos", "../x"])).toBe("/api/v1/juegos/..%2Fx");
  });
});

describe("errores", () => {
  it("un error contractual conserva codigo, mensaje, solicitud y Retry-After", async () => {
    instalarServidor({ "/api/v1/juegos": muestra("global--error--429") });
    const e = await error(consultar("/api/v1/juegos", decJuegos, senal()));
    expect(e).toMatchObject({ estadoHttp: 429, codigo: "limite_excedido", reintentarEn: 12 });
    expect(e.solicitud).toMatch(/^[0-9a-f]{32}$/);
  });

  it("los detalles de un 422 llegan a la vista", async () => {
    instalarServidor({ "/api/v1/juegos": muestra("global--error--422") });
    const e = await error(consultar("/api/v1/juegos", decJuegos, senal()));
    expect(e.codigo).toBe("parametro_no_valido");
    expect(e.detalles?.[0]).toMatchObject({ ubicacion: ["query", "pagina"] });
  });

  it("una respuesta que no es JSON o un error sin contrato no se muestran", async () => {
    instalarServidor({ "/api/v1/juegos": { estado: 200, texto: "<html>", tipo: "text/html" } });
    expect((await error(consultar("/api/v1/juegos", decJuegos, senal()))).codigo).toBe("respuesta_no_valida");
    instalarServidor({ "/api/v1/juegos": { estado: 500, cuerpo: { detail: "traza" } } });
    expect((await error(consultar("/api/v1/juegos", decJuegos, senal()))).codigo).toBe("respuesta_no_valida");
  });

  it("una estructura no reconocida se informa sin mostrar datos a medias", async () => {
    instalarServidor({ "/api/v1/juegos": { estado: 200, cuerpo: { juegos: [{ codigo: 1 }] } } });
    const e = await error(consultar("/api/v1/juegos", decJuegos, senal()));
    expect(e.codigo).toBe("estructura_no_reconocida");
    expect(e.message).toContain("respuesta.juegos[0].codigo");
  });

  it("sin red: red_no_disponible", async () => {
    instalarServidor({ "/api/v1/juegos": () => Promise.reject(new TypeError("Failed to fetch")) });
    expect((await error(consultar("/api/v1/juegos", decJuegos, senal()))).codigo).toBe("red_no_disponible");
  });
});

describe("peticiones compartidas y memoria", () => {
  it("dos consultas iguales en curso hacen una sola peticion", async () => {
    const espera = diferida<ReturnType<typeof muestra>>();
    const { llamadas } = instalarServidor({ "/api/v1/salud": () => espera.promesa });
    const a = consultar("/api/v1/salud", decSalud, senal());
    const b = consultar("/api/v1/salud", decSalud, senal());
    espera.resolver(muestra("global--salud"));
    await expect(Promise.all([a, b])).resolves.toHaveLength(2);
    expect(llamadas).toHaveLength(1);
  });

  it("si una de dos se cancela, la otra recibe la respuesta; si se cancelan todas, se aborta", async () => {
    const espera = diferida<ReturnType<typeof muestra>>();
    const { llamadas } = instalarServidor({ "/api/v1/salud": () => espera.promesa });
    const control = new AbortController();
    const cancelada = consultar("/api/v1/salud", decSalud, control.signal);
    const viva = consultar("/api/v1/salud", decSalud, senal());
    control.abort();
    await expect(cancelada).rejects.toMatchObject({ name: "AbortError" });
    espera.resolver(muestra("global--salud"));
    await expect(viva).resolves.toEqual({ estado: "ok", api: "v1" });

    const nunca = diferida<ReturnType<typeof muestra>>();
    instalarServidor({ "/api/v1/estado": () => nunca.promesa });
    const otra = new AbortController();
    const sola = consultar("/api/v1/estado", decSalud, otra.signal);
    otra.abort();
    await expect(sola).rejects.toMatchObject({ name: "AbortError" });
    await new Promise((r) => setTimeout(r, 5));
    expect(llamadas).toHaveLength(1);
    const ultima = (fetch as unknown as { mock: { calls: [string, RequestInit][] } }).mock.calls.at(-1);
    expect(ultima?.[0]).toBe("/api/v1/estado");
    expect((ultima?.[1].signal as AbortSignal).aborted).toBe(true);
  });

  it("/juegos se pide una vez por carga de pagina y despues sale de memoria", async () => {
    const { llamadas } = instalarServidor();
    await obtenerJuegos(senal());
    await obtenerJuegos(senal());
    expect(llamadas).toHaveLength(1);
    expect(llamadasDeRed()).toBe(1);
  });
});

describe("enlace a la consola local", () => {
  it.each([
    ["http://127.0.0.1:8000/", "http://127.0.0.1:8000/"],
    ["http://localhost:8000/", "http://localhost:8000/"],
    [null, null],
    ["http://ejemplo.org:8000/", null],
    ["https://127.0.0.1:8000/", null],
    ["http://127.0.0.1/", null],
    ["http://u:p@127.0.0.1:8000/", null],
    ["http://127.0.0.1:8000/admin", null],
    ["http://127.0.0.1:8000/?x=1", null],
    ["javascript:alert(1)", null],
    ["no es una url", null],
  ])("%s -> %s", (valor, esperado) => {
    expect(consolaLocal(valor)).toBe(esperado);
  });
});
