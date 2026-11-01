/** Descargas locales de una proyección pública ya cargada; no conoce el cliente HTTP. */
export type CeldaExportacion = string | number | boolean | null;
export type TablaExportacion = {
  id: string;
  titulo: string;
  columnas: readonly string[];
  filas: readonly (readonly CeldaExportacion[])[];
};
export type RecursoExportacion = "resumen" | "sorteos" | "sorteo" | "estadisticas" | "metrica" |
  "prediccion" | "fiabilidad" | "modelos" | "modelo" | "carteras" | "cartera" |
  "resultados" | "simulaciones" | "simulacion";
export type PaginacionExportacion = { pagina: number; por_pagina: number; total: number | null };
export type SolicitudExportacion = {
  juego: string;
  recurso: RecursoExportacion;
  ruta: string;
  datos: unknown;
  tablas: readonly TablaExportacion[];
  alcance: string;
  filtros?: Readonly<Record<string, CeldaExportacion>>;
  identidad?: Readonly<Record<string, CeldaExportacion>>;
  pagina?: PaginacionExportacion;
  notas?: readonly string[];
};
export type ArchivoExportacion = { contenido: string; mime: string; nombre: string };

export const ESQUEMA_EXPORTACION = "loteria-predictor/consulta-publica/1";
export const ESQUEMA_CSV = "loteria-predictor/tabla-publica/1";
const JUEGOS = new Set(["BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO"]);
const CAMPOS_IDENTIDAD = ["clave", "clave_cartera", "corte", "objetivo", "linea", "modelo", "version", "version_receta", "version_registrada", "clave_registrada", "perfil", "corte_entrenamiento", "corte_entrada", "corte_informe", "corte_observacion", "numero_sorteo", "fecha", "primer_sorteo", "ultimo_sorteo", "sorteos", "hasta", "metrica", "id", "semilla", "iteraciones", "estado", "contexto", "tipo", "fecha_observacion"] as const;
const FILTROS: Record<RecursoExportacion, readonly string[]> = {
  resumen: ["hasta_numero_sorteo"],
  sorteos: ["desde", "hasta", "numero_desde", "numero_hasta", "orden", "por_pagina", "pagina"],
  sorteo: [],
  estadisticas: ["hasta_numero_sorteo"],
  metrica: ["hasta_numero_sorteo", "anio", "mes", "dia_semana", "ventana", "color", "pagina"],
  prediccion: ["cartera"],
  fiabilidad: ["hasta"],
  modelos: ["modelo", "perfil", "pagina", "por_pagina"],
  modelo: [],
  carteras: ["linea", "desde", "hasta", "pagina", "por_pagina"],
  cartera: [],
  resultados: ["procedencia", "linea", "tipo", "desde", "hasta", "objetivo", "pagina", "por_pagina"],
  simulaciones: ["limite"],
  simulacion: [],
};
const AVISOS = [
  "experimental_no_acreditado",
  "AE-39 NO-GO; AUTORIZA_EVALUACION = False",
  "Copia local de la consulta cargada: no es un artefacto canónico, prueba de autenticidad, sello temporal ni ventaja predictiva.",
] as const;

function exigir(condicion: boolean): asserts condicion {
  if (!condicion) throw new Error("La consulta no tiene una estructura exportable reconocida.");
}

/** Se valida el árbol JSON público, sin transformar tipos ni inventar valores ausentes. */
function comprobarJson(valor: unknown, vistos = new Set<object>(), profundidad = 0): void {
  exigir(profundidad < 64);
  if (valor === null || typeof valor === "string" || typeof valor === "boolean") return;
  if (typeof valor === "number") { exigir(Number.isFinite(valor)); return; }
  exigir(typeof valor === "object" && valor !== null);
  exigir(!vistos.has(valor));
  exigir(Array.isArray(valor) || Object.getPrototypeOf(valor) === Object.prototype || Object.getPrototypeOf(valor) === null);
  vistos.add(valor);
  if (Array.isArray(valor)) {
    for (const elemento of valor) comprobarJson(elemento, vistos, profundidad + 1);
  } else {
    for (const elemento of Object.values(valor)) {
      // Una propiedad opcional no presente mantiene la ausencia en JSON.
      if (elemento !== undefined) comprobarJson(elemento, vistos, profundidad + 1);
    }
  }
  vistos.delete(valor);
}

/** React Router admite una barra final; el archivo identifica la misma ruta canónica. */
function rutaCanonica(ruta: string): string {
  return ruta.endsWith("/") ? ruta.slice(0, -1) : ruta;
}

function rutaValida(s: SolicitudExportacion): boolean {
  const ruta = rutaCanonica(s.ruta);
  const base = `/juegos/${s.juego}`;
  switch (s.recurso) {
    case "resumen": return ruta === base;
    case "sorteos": return ruta === `${base}/sorteos`;
    case "sorteo": return new RegExp(`^${base}/sorteos/[1-9][0-9]*$`).test(ruta);
    case "estadisticas": return ruta === `${base}/estadisticas`;
    case "metrica": return new RegExp(`^${base}/estadisticas/[a-z0-9]+(?:-[a-z0-9]+)*$`).test(ruta);
    case "prediccion": case "fiabilidad": case "modelos": case "carteras": case "resultados": case "simulaciones":
      return ruta === `${base}/${s.recurso}`;
    case "modelo": return new RegExp(`^${base}/modelos/[a-f0-9]{64}$`).test(ruta);
    case "cartera": return new RegExp(`^${base}/carteras/[a-f0-9]{64}$`).test(ruta);
    case "simulacion": return /^\/simulaciones\/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(ruta);
  }
}

export function filtrosPublicos(s: SolicitudExportacion): Record<string, CeldaExportacion> {
  const filtrados: Record<string, CeldaExportacion> = {};
  for (const k of FILTROS[s.recurso]) {
    const v = s.filtros?.[k];
    if (v !== undefined) {
      exigir(v === null || typeof v === "boolean" || typeof v === "number" && Number.isFinite(v) || typeof v === "string" && v.length <= 500);
      filtrados[k] = v;
    }
  }
  return filtrados;
}

/** Identidad acreditada de la proyección; nunca se incorpora a la URL como filtro. */
export function identidadPublica(s: SolicitudExportacion): Record<string, CeldaExportacion> {
  const resultado: Record<string, CeldaExportacion> = {};
  for (const clave of CAMPOS_IDENTIDAD) {
    const valor = s.identidad?.[clave];
    if (valor !== undefined) {
      exigir(valor === null || typeof valor === "boolean" || typeof valor === "number" && Number.isFinite(valor) || typeof valor === "string" && valor.length <= 2000);
      resultado[clave] = valor;
    }
  }
  return resultado;
}

export function validarExportacion(s: SolicitudExportacion): void {
  exigir(JUEGOS.has(s.juego));
  exigir(Object.hasOwn(FILTROS, s.recurso) && rutaValida(s));
  exigir(typeof s.alcance === "string" && s.alcance.length > 0 && s.alcance.length <= 2000);
  comprobarJson(s.datos);
  filtrosPublicos(s);
  identidadPublica(s);
  if (s.pagina !== undefined) {
    exigir(Number.isSafeInteger(s.pagina.pagina) && s.pagina.pagina > 0);
    exigir(Number.isSafeInteger(s.pagina.por_pagina) && s.pagina.por_pagina > 0);
    exigir(s.pagina.total === null || Number.isSafeInteger(s.pagina.total) && s.pagina.total >= 0);
  }
  exigir(s.tablas.every((t) => typeof t.id === "string" && t.id.length > 0 && typeof t.titulo === "string" && t.columnas.length > 0 &&
    t.columnas.every((c) => typeof c === "string" && c.length > 0) &&
    t.filas.every((f) => f.length === t.columnas.length && f.every((v) => v === null || typeof v === "string" || typeof v === "boolean" || typeof v === "number" && Number.isFinite(v)))));
  exigir(new Set(s.tablas.map((t) => t.id)).size === s.tablas.length);
  exigir((s.notas ?? []).every((n) => typeof n === "string"));
}

function contexto(s: SolicitudExportacion, fecha: Date) {
  validarExportacion(s);
  exigir(Number.isFinite(fecha.getTime()));
  const filtros = filtrosPublicos(s);
  const query = new URLSearchParams();
  for (const [k, v] of Object.entries(filtros)) if (v !== null && v !== "") query.set(k, String(v));
  return {
    exportado_en: fecha.toISOString(), juego: s.juego, recurso: s.recurso,
    ruta_spa: rutaCanonica(s.ruta) + (query.size ? `?${query.toString()}` : ""), filtros,
    alcance: s.alcance, paginacion: s.pagina ? { pagina: s.pagina.pagina, por_pagina: s.pagina.por_pagina, total: s.pagina.total } : null, identidad: identidadPublica(s),
    estado_de_uso: "experimental_no_acreditado", autoriza_evaluacion: false,
    advertencias: [...AVISOS, ...(s.notas ?? [])],
  };
}

/** Solo segmentos saneados propios; nunca nombres, rutas o títulos del servidor. */
export function nombreArchivo(juego: string, recurso: string, extension: "json" | "csv", fecha: Date, tabla?: string): string {
  const segmento = (v: string) => v.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40) || "consulta";
  const instante = fecha.toISOString().replace(/[-:.]/g, "");
  return `lp-${segmento(juego)}-${segmento(recurso)}${tabla ? `-${segmento(tabla)}` : ""}-${instante}.${extension}`;
}

export function exportarJson(s: SolicitudExportacion, fecha = new Date()): ArchivoExportacion {
  const c = contexto(s, fecha);
  return { contenido: JSON.stringify({ esquema: ESQUEMA_EXPORTACION, ...c, datos: s.datos }, null, 2) + "\n",
    mime: "application/json;charset=utf-8", nombre: nombreArchivo(s.juego, s.recurso, "json", fecha) };
}

/** Protección de texto, adicional al escape CSV. Los números negativos siguen numéricos. */
export function textoCsvSeguro(texto: string): string {
  return /^[\s"'=+\-@]|[\u0000-\u001f\u007f]/u.test(texto) ? "'" + texto : texto;
}

const tipoCelda = (v: CeldaExportacion) => v === null ? "null" : typeof v === "number" ? "numero" : typeof v === "boolean" ? "booleano" : "texto";
const celdaCsv = (v: CeldaExportacion) => `"${(v === null ? "null" : typeof v === "string" ? textoCsvSeguro(v) : String(v)).replace(/"/g, '""')}"`;

/** CSV tabla pública/1: cabecera, registro de contexto y cero o más registros de datos. */
export function exportarCsv(s: SolicitudExportacion, tablaId: string, fecha = new Date()): ArchivoExportacion {
  const c = contexto(s, fecha);
  const tabla = s.tablas.find((t) => t.id === tablaId);
  exigir(tabla !== undefined);
  const filtros = Object.entries(c.filtros);
  const identidad = Object.entries(c.identidad);
  const nombres = ["tipo_fila", "esquema", "exportado_en", "juego", "recurso", "ruta_spa", "alcance", "tabla", "filas_cargadas",
    "pagina", "por_pagina", "total", "estado_de_uso", "autoriza_evaluacion", "advertencias", ...filtros.map(([k]) => `filtro_${k}`),
    ...identidad.flatMap(([k]) => [`identidad_${k}`, `identidad_${k}_tipo`]),
    ...tabla.columnas.flatMap((k) => [`dato_${k}`, `dato_${k}_tipo`])];
  exigir(new Set(nombres).size === nombres.length);
  const meta: CeldaExportacion[] = [ESQUEMA_CSV, c.exportado_en, c.juego, c.recurso, c.ruta_spa, c.alcance, tabla.titulo, tabla.filas.length,
    c.paginacion?.pagina ?? null, c.paginacion?.por_pagina ?? null, c.paginacion?.total ?? null,
    c.estado_de_uso, c.autoriza_evaluacion, c.advertencias.join(" · "), ...filtros.map(([, v]) => v),
    ...identidad.flatMap(([, v]) => [v, tipoCelda(v)])];
  const contextoCsv: CeldaExportacion[] = ["contexto", ...meta, ...tabla.columnas.flatMap(() => ["", ""] as const)];
  const filas = [nombres, contextoCsv, ...tabla.filas.map((f) => ["dato", ...meta, ...f.flatMap((v) => [v, tipoCelda(v)])])];
  return { contenido: "\ufeff" + filas.map((f) => f.map(celdaCsv).join(",")).join("\r\n") + "\r\n",
    mime: "text/csv;charset=utf-8", nombre: nombreArchivo(s.juego, s.recurso, "csv", fecha, tabla.id) };
}

/** El clic inicia la descarga antes de liberar su URL, con una concesión por archivo. */
export function descargarArchivo(archivo: ArchivoExportacion): void {
  const liberar = URL.revokeObjectURL.bind(URL);
  const url = URL.createObjectURL(new Blob([archivo.contenido], { type: archivo.mime }));
  const enlace = document.createElement("a");
  enlace.href = url; enlace.download = archivo.nombre;
  enlace.hidden = true; document.body.append(enlace);
  try {
    enlace.click();
  } catch (error) {
    liberar(url);
    throw error;
  } finally {
    enlace.remove();
  }
  // La revocación en el mismo turno puede cancelar la descarga en navegadores reales.
  setTimeout(() => liberar(url), 1000);
}
