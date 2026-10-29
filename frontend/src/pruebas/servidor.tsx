/**
 * Servidor falso para las pruebas de componentes: responde con las respuestas
 * SINTETICAS de `respuestas/` (producidas por la API publica real, ver
 * backend/tests/generar_respuestas_fase9.py) y registra cada llamada a `fetch`.
 */
import { render } from "@testing-library/react";
import { StrictMode } from "react";
import { MemoryRouter, useLocation, useNavigate } from "react-router-dom";
import { vi } from "vitest";
import { App } from "../App";

export interface Muestra {
  escenario: string;
  url: string;
  estado: number;
  cuerpo: unknown;
  retry_after?: string;
}

const archivos = import.meta.glob<Muestra>("./respuestas/*.json", { eager: true, import: "default" });

/** Respuesta sintetica por nombre de archivo (sin `.json`). */
export function muestra(nombre: string): Muestra {
  const m = archivos[`./respuestas/${nombre}.json`];
  if (!m) {
    throw new Error(`no existe la respuesta ${nombre}`);
  }
  return structuredClone(m);
}

export function nombresDeMuestras(): string[] {
  return Object.keys(archivos).map((k) => k.replace("./respuestas/", "").replace(/\.json$/, ""));
}

/** Variantes con la misma URL que la respuesta normal (9.3: explicacion alterada y base de la Fase 4 caida). */
const VARIANTES_EXPLICITAS = ["--sin_configuracion", "--sin_sorteos", "--explicacion_alterada", "--sin_base"];

/** Respuestas normales por URL; las variantes y los errores se piden de forma explicita. */
function porUrl(): Map<string, Muestra> {
  const mapa = new Map<string, Muestra>();
  for (const nombre of nombresDeMuestras()) {
    const guardadoVariante = /--(?:modelos|modelo|carteras|cartera|resultados)--(?:vacio|alterado|incompatible)$/.test(nombre);
    if (nombre.startsWith("global--error--") || VARIANTES_EXPLICITAS.some((v) => nombre.endsWith(v)) || guardadoVariante) {
      continue;
    }
    const m = muestra(nombre);
    mapa.set(m.url, m);
    const partes = nombre.split("--");
    const variante = partes.length > (["metrica", "simulacion"].includes(partes[1] ?? "") ? 3 : 2);
    if (!variante) {  // sin consulta, la ruta sirve la respuesta normal (no la vacia)
      mapa.set(new URL(m.url, "http://x").pathname, m);
    }
  }
  return mapa;
}

export type Respuesta = Muestra | { estado: number; cuerpo?: unknown; texto?: string; tipo?: string; retry_after?: string };

export interface Llamada {
  url: string;
  init: RequestInit | undefined;
}

export const CONFIGURACION_SIN_CONSOLA = { estado: 200, cuerpo: { consola_local: null, api: "v1" } };

/**
 * Instala `fetch` falso. `extra` sustituye la respuesta de una URL exacta o de
 * una ruta (sin consulta); una funcion permite controlar el momento.
 */
export function instalarServidor(extra: Record<string, Respuesta | (() => Promise<Respuesta>)> = {}) {
  const base = porUrl();
  const llamadas: Llamada[] = [];
  const falso = vi.fn(async (entrada: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = typeof entrada === "string" ? entrada : entrada instanceof URL ? entrada.href : entrada.url;
    llamadas.push({ url, init });
    const ruta = new URL(url, "http://127.0.0.1:8020").pathname;
    const senal = init?.signal;
    const abortar = () => new DOMException("cancelada", "AbortError");
    if (senal?.aborted) {
      throw abortar();
    }
    const elegida = extra[url] ?? extra[ruta] ?? (ruta === "/pasarela/configuracion" ? CONFIGURACION_SIN_CONSOLA : undefined);
    const respuesta = await new Promise<Respuesta>((resolver, rechazar) => {
      senal?.addEventListener("abort", () => rechazar(abortar()), { once: true });
      if (typeof elegida === "function") {
        elegida().then(resolver, rechazar);
      } else {
        const m = elegida ?? base.get(url) ?? base.get(ruta);
        resolver(m ?? { estado: 404, cuerpo: { error: { codigo: "ruta_no_disponible", mensaje: `sin respuesta sintetica para ${url}`, solicitud: null } } });
      }
    });
    const cabeceras: Record<string, string> = {
      "content-type": "tipo" in respuesta && respuesta.tipo ? respuesta.tipo : "application/json",
      "x-request-id": "0123456789abcdef0123456789abcdef",
    };
    if (respuesta.retry_after) {
      cabeceras["retry-after"] = respuesta.retry_after;
    }
    const cuerpo = "texto" in respuesta && respuesta.texto !== undefined ? respuesta.texto : JSON.stringify(respuesta.cuerpo);
    return new Response(cuerpo, { status: respuesta.estado, headers: cabeceras });
  });
  vi.stubGlobal("fetch", falso);
  const deApi = () => llamadas.filter((l) => l.url.startsWith("/api/v1/")).map((l) => l.url);
  return { falso, llamadas, deApi };
}

/** Ubicacion actual y botones atras/adelante del historial del enrutador (solo pruebas). */
function Ubicacion() {
  const { pathname, search } = useLocation();
  const navegar = useNavigate();
  return (
    <div hidden>
      <output data-testid="ubicacion">{pathname + search}</output>
      <button type="button" data-testid="atras" onClick={() => navegar(-1)} />
      <button type="button" data-testid="adelante" onClick={() => navegar(1)} />
    </div>
  );
}

/** La aplicacion completa en StrictMode (doble montaje en desarrollo) sobre `rutas`. */
export function renderizar(...rutas: string[]) {
  return render(
    <StrictMode>
      <MemoryRouter initialEntries={rutas.length ? rutas : ["/"]} initialIndex={rutas.length ? rutas.length - 1 : 0}>
        <App />
        <Ubicacion />
      </MemoryRouter>
    </StrictMode>,
  );
}

/** Promesa controlable para ordenar respuestas en las pruebas. */
export function diferida<T>() {
  let resolver!: (valor: T) => void;
  const promesa = new Promise<T>((r) => {
    resolver = r;
  });
  return { promesa, resolver };
}
