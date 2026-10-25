/**
 * Formato de presentacion de las celdas e indicadores de las metricas: el mismo
 * criterio que `formatear` de la consola HTMX
 * (backend/app/api/web/routers/estadisticas_descriptivas.py). Las etiquetas del
 * tipo de p-value son las de `ETIQUETAS_TIPO_P_VALUE`
 * (backend/app/application/estadisticas/descriptivas.py); una prueba de Python
 * las compara. Solo presenta: no calcula estadisticas.
 */

export const ETIQUETAS_TIPO_P: Readonly<Record<string, string>> = {
  asintotico: "asintótico (chi-cuadrado límite)",
  permutacion_exacta: "permutación exacta",
  permutacion_monte_carlo: "permutación Monte Carlo",
};

export const FORMATOS = ["entero", "texto", "dec1", "dec2", "dec3", "pct", "pp", "p", "tipo_p"] as const;

/**
 * Como `format(x, ".{f}f")` de Python: `toFixed` redondea los empates exactos
 * hacia arriba y Python al par; y Python conserva el signo de -0. Un empate
 * exacto tiene a lo sumo f+1 decimales en binario, asi que 25 cifras mas bastan
 * para distinguirlo de un valor apenas mayor.
 */
function fijo(x: number, f: number): string {
  const negativo = x < 0 || Object.is(x, -0);
  const a = Math.abs(x);
  let cifras = a.toFixed(f);
  const largo = a.toFixed(f + 25);
  if (/^50{24}$/.test(largo.slice(-25))) {
    const truncado = largo.slice(0, -25).replace(/\.$/, "");
    const ultima = Number(truncado.replace(".", "").slice(-1));
    if (ultima % 2 === 0) {
      cifras = truncado;
    }
  }
  return (negativo ? "-" : "") + cifras;
}

/**
 * `formatear` de la consola HTMX. Diferencia conocida: con formato `texto`, un
 * numero se muestra con `String` (JSON no distingue 100 de 100.0 ni conserva la
 * notacion exponencial de Python); las tablas de la API usan texto en esas columnas.
 */
export function formatear(valor: number | string | null | undefined, formato: string): string {
  if (valor === null || valor === undefined) {
    return "—";
  }
  if (formato === "tipo_p") {
    return ETIQUETAS_TIPO_P[String(valor)] ?? String(valor);
  }
  if (formato === "texto" || typeof valor === "string") {
    return String(valor);
  }
  switch (formato) {
    case "entero": {
      const entero = Math.trunc(valor);
      return Math.abs(entero) >= 1e21 ? BigInt(entero).toString() : String(entero === 0 ? 0 : entero);
    }
    case "pct":
      return fijo(valor, 1);
    case "pp":
      return (valor < 0 || Object.is(valor, -0) ? "-" : "+") + fijo(Math.abs(valor), 1);
    case "p":
      return valor < 0.0001 ? "< 0.0001" : fijo(valor, 4);
    case "dec1":
      return fijo(valor, 1);
    case "dec3":
      return fijo(valor, 3);
    default:
      return fijo(valor, 2);
  }
}

export function alineadoADerecha(formato: string): boolean {
  return formato !== "texto" && formato !== "tipo_p";
}

export function fechaHora(iso: string | null | undefined): string {
  if (!iso) {
    return "—";
  }
  return iso.slice(0, 19).replace("T", " ");
}

export function abreviada(huella: string, largo = 12): string {
  return huella.length > largo ? `${huella.slice(0, largo)}…` : huella;
}
