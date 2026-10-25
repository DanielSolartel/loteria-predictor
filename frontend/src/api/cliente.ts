/**
 * Cliente de la pasarela local (mismo origen). Solo GET a `/api/v1` y a
 * `/pasarela/configuracion`; nunca envia credenciales: la clave de la API la
 * anade la pasarela en el servidor y no existe en el navegador.
 *
 * - Sin reintentos automaticos ni sondeo: cada llamada responde a un montaje,
 *   una navegacion o un reintento pedido por la persona.
 * - Peticiones identicas en curso se comparten (StrictMode monta dos veces):
 *   la cancelacion real se aplaza un ciclo y solo ocurre si nadie la espera.
 * - Solo `/api/v1/juegos` se guarda, en memoria y durante la vida de la
 *   pagina; nada va a almacenamiento persistente.
 */
import { type Decodificador, decodificar, EstructuraNoReconocida, type Json } from "./decodificar";
import { type ConfiguracionDeLaPasarela, decConfiguracion, decError, decJuegos, type Juego } from "./presentacion";

export class ErrorDeConsulta extends Error {
  readonly estadoHttp: number | null;
  readonly codigo: string;
  readonly solicitud: string | null;
  /** Segundos de `Retry-After` (429 y 503), si la respuesta los indica. */
  readonly reintentarEn: number | null;
  readonly detalles: Record<string, Json>[] | null;

  constructor(
    estadoHttp: number | null,
    codigo: string,
    mensaje: string,
    extra: { solicitud?: string | null; reintentarEn?: number | null; detalles?: Record<string, Json>[] | null } = {},
  ) {
    super(mensaje);
    this.name = "ErrorDeConsulta";
    this.estadoHttp = estadoHttp;
    this.codigo = codigo;
    this.solicitud = extra.solicitud ?? null;
    this.reintentarEn = extra.reintentarEn ?? null;
    this.detalles = extra.detalles ?? null;
  }
}

export function esCancelacion(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

/** Ruta de la API con segmentos codificados y consulta sin valores vacios. */
export function rutaApi(segmentos: readonly (string | number)[], consulta: Record<string, string | null> = {}): string {
  const ruta = `/api/v1/${segmentos.map((s) => encodeURIComponent(String(s))).join("/")}`;
  const pares = Object.entries(consulta).filter((p): p is [string, string] => p[1] !== null && p[1] !== "");
  return pares.length ? `${ruta}?${new URLSearchParams(pares).toString()}` : ruta;
}

interface EnCurso {
  promesa: Promise<unknown>;
  control: AbortController;
  usuarios: number;
  cancelacion: ReturnType<typeof setTimeout> | null;
}

const enCurso = new Map<string, EnCurso>();
let juegosEnMemoria: Juego[] | null = null;
let llamadas = 0;

/** Llamadas HTTP reales emitidas desde que cargo la pagina (pruebas y diagnostico). */
export function llamadasDeRed(): number {
  return llamadas;
}

/** Solo pruebas: vacia la memoria de `/juegos` y el contador. */
export function reiniciarCliente(): void {
  juegosEnMemoria = null;
  llamadas = 0;
  enCurso.clear();
}

function segundos(valor: string | null): number | null {
  return valor !== null && /^[0-9]{1,6}$/.test(valor) ? Number(valor) : null;
}

async function pedir(url: string, senal: AbortSignal): Promise<unknown> {
  llamadas += 1;
  let respuesta: Response;
  try {
    respuesta = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
      credentials: "omit",
      cache: "no-store",
      redirect: "error",
      referrerPolicy: "no-referrer",
      signal: senal,
    });
  } catch (error) {
    if (senal.aborted) {
      throw new DOMException("cancelada", "AbortError");
    }
    throw new ErrorDeConsulta(null, "red_no_disponible", "No se pudo contactar con la pasarela local.");
  }
  const solicitud = respuesta.headers.get("x-request-id");
  const reintentarEn = segundos(respuesta.headers.get("retry-after"));
  const tipo = respuesta.headers.get("content-type") ?? "";
  let cuerpo: unknown;
  try {
    if (!tipo.toLowerCase().startsWith("application/json")) {
      throw new TypeError("no es JSON");
    }
    cuerpo = await respuesta.json();
  } catch (error) {
    if (senal.aborted) {
      throw new DOMException("cancelada", "AbortError");
    }
    throw new ErrorDeConsulta(respuesta.status, "respuesta_no_valida", "La respuesta no tiene el formato esperado.", {
      solicitud,
    });
  }
  if (respuesta.ok) {
    return cuerpo;
  }
  try {
    const { error } = decodificar(decError, cuerpo);
    throw new ErrorDeConsulta(respuesta.status, error.codigo, error.mensaje, {
      solicitud: error.solicitud ?? solicitud,
      reintentarEn,
      detalles: error.detalles,
    });
  } catch (error) {
    if (error instanceof ErrorDeConsulta) {
      throw error;
    }
    throw new ErrorDeConsulta(respuesta.status, "respuesta_no_valida", "La respuesta de error no es reconocible.", {
      solicitud,
    });
  }
}

/** Respuesta JSON de `url`; comparte la peticion con quien ya la espera. */
function compartida(url: string, senal: AbortSignal): Promise<unknown> {
  let entrada = enCurso.get(url);
  if (entrada === undefined) {
    const control = new AbortController();
    const nueva: EnCurso = { promesa: Promise.resolve(), control, usuarios: 0, cancelacion: null };
    nueva.promesa = pedir(url, control.signal).finally(() => {
      if (enCurso.get(url) === nueva) {
        enCurso.delete(url);
      }
    });
    nueva.promesa.catch(() => undefined);
    enCurso.set(url, nueva);
    entrada = nueva;
  }
  const actual = entrada;
  actual.usuarios += 1;
  if (actual.cancelacion !== null) {
    clearTimeout(actual.cancelacion);
    actual.cancelacion = null;
  }
  return new Promise((resolver, rechazar) => {
    let liberado = false;
    const liberar = () => {
      if (!liberado) {
        liberado = true;
        actual.usuarios -= 1;
      }
    };
    const soltar = () => {
      liberar();
      rechazar(new DOMException("cancelada", "AbortError"));
      if (actual.usuarios === 0 && actual.cancelacion === null) {
        actual.cancelacion = setTimeout(() => {
          actual.cancelacion = null;
          if (actual.usuarios === 0) {
            if (enCurso.get(url) === actual) {
              enCurso.delete(url);
            }
            actual.control.abort();
          }
        }, 0);
      }
    };
    if (senal.aborted) {
      soltar();
      return;
    }
    senal.addEventListener("abort", soltar, { once: true });
    actual.promesa.then(
      (valor) => {
        senal.removeEventListener("abort", soltar);
        liberar();
        resolver(valor);
      },
      (error: unknown) => {
        senal.removeEventListener("abort", soltar);
        liberar();
        rechazar(error);
      },
    );
  });
}

export async function consultar<T>(url: string, decodificador: Decodificador<T>, senal: AbortSignal): Promise<T> {
  const cuerpo = await compartida(url, senal);
  try {
    return decodificar(decodificador, cuerpo);
  } catch (error) {
    if (error instanceof EstructuraNoReconocida) {
      throw new ErrorDeConsulta(200, "estructura_no_reconocida", `Estructura no reconocida en ${error.ruta}.`);
    }
    throw error;
  }
}

/** Los cuatro juegos: unica respuesta guardada, en memoria. */
export async function obtenerJuegos(senal: AbortSignal): Promise<Juego[]> {
  if (juegosEnMemoria !== null) {
    return juegosEnMemoria;
  }
  const { juegos } = await consultar(rutaApi(["juegos"]), decJuegos, senal);
  juegosEnMemoria = juegos;
  return juegos;
}

export function obtenerConfiguracion(senal: AbortSignal): Promise<ConfiguracionDeLaPasarela> {
  return consultar("/pasarela/configuracion", decConfiguracion, senal);
}

/**
 * Enlace a la consola HTMX solo si es http:// en loopback con puerto y sin
 * credenciales, ruta, consulta ni fragmento. La pasarela ya lo valida; aqui se
 * repite para no confiar en un valor recibido.
 */
export function consolaLocal(valor: string | null): string | null {
  if (valor === null) {
    return null;
  }
  try {
    const url = new URL(valor);
    const local = ["127.0.0.1", "localhost", "[::1]"].includes(url.hostname);
    const limpia = !url.username && !url.password && !url.search && !url.hash && url.pathname === "/";
    return url.protocol === "http:" && local && url.port !== "" && limpia ? url.href : null;
  } catch {
    return null;
  }
}
