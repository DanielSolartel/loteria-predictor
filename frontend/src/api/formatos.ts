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

/** `color` (Fase 9.2): codigo de un color de ColorLoto; se muestra con su muestra y su codigo en texto. */
export const FORMATOS = ["entero", "texto", "dec1", "dec2", "dec3", "pct", "pp", "p", "tipo_p", "color"] as const;

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

/**
 * Las especificaciones de `format` de Python que usa la consola HTMX en las
 * predicciones (`.6f`, `+.6f`, `.3f`, `.4f`, `.5f`, `.1f` y `.4g`). Solo presenta.
 */
export function especificacion(valor: number | null | undefined, spec: string): string {
  if (valor === null || valor === undefined) {
    return "—";
  }
  const fija = /^(\+?)\.(\d)f$/.exec(spec);
  if (fija) {
    const cifras = fijo(valor, Number(fija[2]));
    return fija[1] && !cifras.startsWith("-") ? `+${cifras}` : cifras;
  }
  const general = /^\.(\d)g$/.exec(spec);
  if (!general) {
    throw new Error(`especificación no admitida: ${spec}`);
  }
  // `%g` de Python: notación científica si el exponente es < -4 o >= la precisión; sin ceros finales.
  const p = Math.max(1, Number(general[1]));
  if (valor === 0) {
    return Object.is(valor, -0) ? "-0" : "0";
  }
  const [mantisa, e] = partesExponenciales(valor, p - 1);
  const sinCeros = (s: string) => (s.includes(".") ? s.replace(/0+$/, "").replace(/\.$/, "") : s);
  if (e < -4 || e >= p) {
    return `${sinCeros(mantisa)}e${e < 0 ? "-" : "+"}${String(Math.abs(e)).padStart(2, "0")}`;
  }
  return sinCeros(fijo(valor, p - 1 - e));
}

/**
 * `formatear_cifra` de la fiabilidad (backend/app/application/ml/predicciones_fiabilidad.py):
 * cinco decimales y, si el valor no es nulo y su magnitud es menor que 0.00005,
 * notación científica con cinco cifras significativas. Nunca redondea un no-cero a 0.
 */
export function formatearCifra(valor: number | null | undefined): string {
  if (valor === null || valor === undefined) {
    return "—";
  }
  if (valor !== 0 && Math.abs(valor) < 0.00005) {
    return especificacionCientifica(valor);
  }
  return fijo(valor === 0 ? 0 : valor, 5);
}

/** Mantisa y exponente de `toExponential(decimales)`. */
function partesExponenciales(valor: number, decimales: number): [string, number] {
  const texto = valor.toExponential(decimales);
  const posicion = texto.indexOf("e");
  return [texto.slice(0, posicion), Number(texto.slice(posicion + 1))];
}

/** Como `format(x, ".4e")` de Python (exponente con al menos dos cifras). */
function especificacionCientifica(valor: number): string {
  const [mantisa, e] = partesExponenciales(valor, 4);
  return `${mantisa}e${e < 0 ? "-" : "+"}${String(Math.abs(e)).padStart(2, "0")}`;
}

/** Etiquetas de la consola HTMX (backend/app/api/web/routers/predicciones.py); una prueba las compara. */
export const ESTADOS_FIABILIDAD: Readonly<Record<string, string>> = {
  estimable: "estimable",
  muestra_insuficiente: "muestra insuficiente",
  sin_resultados: "sin resultados todavía",
  sin_base: "base no disponible",
  excluidas: "emisiones excluidas",
  sin_datos: "sin datos",
  no_disponible: "no disponible",
  fallo_de_calculo: "fallo de cálculo",
};
export const COMPONENTES_FIABILIDAD: Readonly<Record<string, string>> = {
  numeros: "Números principales",
  pares: "Pares número-color",
  superbalota: "Superbalota (aparte)",
};
export const TIPOS_FIABILIDAD: Readonly<Record<string, string>> = {
  seguimiento: "Seguimiento",
  retrospectiva: "Retrospectiva",
  evaluacion_de_receta: "Evaluación de la receta (informe del laboratorio)",
};

export function alineadoADerecha(formato: string): boolean {
  return formato !== "texto" && formato !== "tipo_p" && formato !== "color";
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
