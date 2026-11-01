/** Origen de una ficha: sólo la ruta del listado del mismo juego y sus filtros permitidos. */
import { useLocation } from "react-router-dom";

function conFiltros(ruta: string, search: string, permitidos: readonly string[]): string {
  const entrada = new URLSearchParams(search);
  const salida = new URLSearchParams();
  for (const k of permitidos) {
    const v = entrada.get(k);
    if (v !== null && v !== "") salida.set(k, v);
  }
  return ruta + (salida.size ? `?${salida.toString()}` : "");
}
export function useRutaDeListado(ruta: string, permitidos: readonly string[]): string {
  const { pathname, search } = useLocation();
  return conFiltros(ruta, pathname === ruta ? search : "", permitidos);
}
export function rutaDeRetorno(estado: unknown, ruta: string, permitidos: readonly string[]): string {
  if (typeof estado !== "object" || estado === null || !("retornoListado" in estado) || typeof estado.retornoListado !== "string") return ruta;
  const valor = estado.retornoListado;
  if (!valor.startsWith("/") || valor.startsWith("//") || valor.includes("\\")) return ruta;
  try {
    const url = new URL(valor, "http://127.0.0.1");
    if (url.origin !== "http://127.0.0.1" || url.pathname !== ruta || url.hash) return ruta;
    return conFiltros(ruta, url.search, permitidos);
  } catch { return ruta; }
}
export function useRutaDeRetorno(ruta: string, permitidos: readonly string[]): string {
  return rutaDeRetorno(useLocation().state, ruta, permitidos);
}
