/**
 * Decodificadores de presentacion: validan en ejecucion las estructuras que la
 * interfaz muestra, en lugar de confiar en una conversion a `any`. Un valor que
 * no encaja produce `EstructuraNoReconocida` con la ruta del campo.
 */

export type Json = null | boolean | number | string | Json[] | { [clave: string]: Json };
export type Decodificador<T> = (valor: unknown, ruta: string) => T;

export class EstructuraNoReconocida extends Error {
  readonly ruta: string;

  constructor(ruta: string, esperado: string) {
    super(`${ruta}: se esperaba ${esperado}`);
    this.name = "EstructuraNoReconocida";
    this.ruta = ruta;
  }
}

function fallo(ruta: string, esperado: string): never {
  throw new EstructuraNoReconocida(ruta, esperado);
}

export function esObjeto(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === "object" && valor !== null && !Array.isArray(valor);
}

export const texto: Decodificador<string> = (v, r) => (typeof v === "string" ? v : fallo(r, "texto"));
export const numero: Decodificador<number> = (v, r) =>
  typeof v === "number" && Number.isFinite(v) ? v : fallo(r, "número");
export const entero: Decodificador<number> = (v, r) => (Number.isInteger(v) ? (v as number) : fallo(r, "entero"));
export const booleano: Decodificador<boolean> = (v, r) => (typeof v === "boolean" ? v : fallo(r, "booleano"));

export function literal<T extends string>(...valores: T[]): Decodificador<T> {
  return (v, r) => (typeof v === "string" && (valores as string[]).includes(v) ? (v as T) : fallo(r, valores.join("|")));
}

export function nulable<T>(d: Decodificador<T>): Decodificador<T | null> {
  return (v, r) => (v === null || v === undefined ? null : d(v, r));
}

export function lista<T>(d: Decodificador<T>): Decodificador<T[]> {
  return (v, r) => (Array.isArray(v) ? v.map((x, i) => d(x, `${r}[${i}]`)) : fallo(r, "lista"));
}

export function tupla<A, B>(a: Decodificador<A>, b: Decodificador<B>): Decodificador<[A, B]> {
  return (v, r) =>
    Array.isArray(v) && v.length === 2 ? [a(v[0], `${r}[0]`), b(v[1], `${r}[1]`)] : fallo(r, "par de valores");
}

export type Campos<T> = { [K in keyof T]-?: Decodificador<T[K]> };

/** Objeto con los campos indicados; los demas no se copian (quien los necesite usa `objetoJson`). */
export function objeto<T>(campos: Campos<T>): Decodificador<T> {
  return (v, r) => {
    if (!esObjeto(v)) {
      return fallo(r, "objeto");
    }
    const salida = {} as T;
    for (const clave of Object.keys(campos) as (keyof T & string)[]) {
      salida[clave] = campos[clave](v[clave], `${r}.${clave}`);
    }
    return salida;
  };
}

export function diccionario<T>(d: Decodificador<T>): Decodificador<Record<string, T>> {
  return (v, r) => {
    if (!esObjeto(v)) {
      return fallo(r, "objeto");
    }
    return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, d(x, `${r}.${k}`)]));
  };
}

export const json: Decodificador<Json> = (v, r) => {
  if (v === null || typeof v === "string" || typeof v === "boolean") {
    return v;
  }
  if (typeof v === "number") {
    return numero(v, r);
  }
  if (Array.isArray(v)) {
    return v.map((x, i) => json(x, `${r}[${i}]`));
  }
  if (esObjeto(v)) {
    return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, json(x, `${r}.${k}`)]));
  }
  return fallo(r, "JSON");
};

export const objetoJson: Decodificador<Record<string, Json>> = (v, r) => (esObjeto(v) ? diccionario(json)(v, r) : fallo(r, "objeto"));

/** Celda de una tabla de metrica: numero, texto o vacio. */
export const celda: Decodificador<number | string | null> = (v, r) =>
  v === null || typeof v === "string" ? v : numero(v, r);

/** Valor de una opcion o categoria que la API envia como texto o como numero. */
export const etiqueta: Decodificador<string> = (v, r) =>
  typeof v === "string" ? v : String(numero(v, r));

export function decodificar<T>(d: Decodificador<T>, valor: unknown): T {
  return d(valor, "respuesta");
}
