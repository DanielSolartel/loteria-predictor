/** Consultas de Fase 9.4: metadatos registrados y lecturas de Productos 5 y 6.
 * Los contratos se validan antes de mostrarlos y se vinculan al juego y la
 * identidad pedidos; ninguna ficha se completa con la configuración actual.
 */
import type { components } from "./esquema";
import {
  type Decodificador, booleano, diccionario, entero, EstructuraNoReconocida,
  esObjeto, lista, literal, nulable, numero, objeto, texto,
} from "./decodificar";

type E = components["schemas"];
export type ModeloGuardado = E["ModeloGuardado"];
export type ModelosGuardados = E["ModelosGuardados"];
export type FichaModeloGuardado = E["FichaModeloGuardado"];
export type CarteraGuardada = E["CarteraGuardada"];
export type CarterasGuardadas = E["CarterasGuardadas"];
export type FichaCarteraGuardada = E["FichaCarteraGuardada"];
export type ResultadosGuardados = E["ResultadosGuardados"];
export type ResumenResultadoGuardado = E["ResumenResultadoGuardado"];
export type ResultadoGuardado = E["ResultadoGuardado"];
export type EmisionGuardada = E["EmisionGuardada"];

const uso = literal("experimental_no_acreditado");
const referencia = objeto<E["ReferenciaRegistrada"]>({ clave: texto, numero: entero });
export const decModeloGuardado = objeto<ModeloGuardado>({
  clave: texto, juego: texto, estado: literal("disponible", "incompatible", "alterado"),
  motivo: nulable(texto), modelo: nulable(texto), nombre: nulable(texto), familia: nulable(texto),
  perfil: nulable(texto), version_receta: nulable(texto), numero: nulable(entero),
  corte: nulable(entero), sorteos: nulable(entero), entrenado_en: nulable(texto), linea: nulable(texto),
});
const pagina = {
  juego: texto, estado_de_uso: uso, pagina: entero, paginas: entero, por_pagina: entero, total: entero,
};
export const decModelosGuardados = objeto<ModelosGuardados>({
  ...pagina, elementos: lista(decModeloGuardado), modelo: nulable(texto), perfil: nulable(texto), nota: texto,
});
export const decFichaModeloGuardado = objeto<FichaModeloGuardado>({
  juego: texto, estado_de_uso: uso, modelo: decModeloGuardado,
  periodo: objeto<E["PeriodoGuardado"]>({ primer_sorteo: entero, ultimo_sorteo: entero, primera_fecha: texto, ultima_fecha: texto, sorteos: entero }),
  sha256_historico: texto, variables: lista(texto), semilla: entero, hilos: entero,
  objetivo_estadistico: texto, contrato_de_inferencia: texto, experimento: texto,
  evaluacion: objeto<E["EvaluacionGuardada"]>({
    estado: nulable(texto), veredicto: nulable(texto), corte: nulable(entero), objetivos: nulable(entero),
    muestra_pequena: nulable(booleano), log_loss: nulable(numero), log_loss_uniforme: nulable(numero), nota: texto,
  }), nota: texto,
});
export const decCarteraGuardada = objeto<CarteraGuardada>({
  clave: texto, juego: texto, estado: literal("disponible", "alterado"), motivo: nulable(texto), linea: nulable(texto),
  objetivo: nulable(entero), corte: nulable(entero), modelo: nulable(texto), nombre: nulable(texto),
  version_receta: nulable(texto), perfil: nulable(texto), version: nulable(entero), versiones: nulable(entero),
  cantidad: nulable(entero), generado_en: nulable(texto), registrado: nulable(referencia),
});
export const decCarterasGuardadas = objeto<CarterasGuardadas>({
  ...pagina, elementos: lista(decCarteraGuardada), lineas: lista(texto), linea: nulable(texto),
  desde: nulable(entero), hasta: nulable(entero), incidencias_sin_objetivo: entero, nota: texto,
});
const par = objeto<E["ParGuardado"]>({ numero: entero, color: texto });
const combinacion = objeto<E["CombinacionGuardada"]>({
  linea: entero, origen: texto, numeros: lista(entero), superbalota: nulable(entero), pares: lista(par),
});
export const decFichaCarteraGuardada = objeto<FichaCarteraGuardada>({
  juego: texto, estado_de_uso: uso, cartera: decCarteraGuardada, combinaciones: lista(combinacion),
  parametros: objeto<E["ParametrosCarteraGuardada"]>({
    cantidad: entero, semilla: entero, diversidad: texto, version: texto, algoritmo_rng: texto, presupuesto_de_intentos: entero,
  }), sha256_historico: texto, clasificacion_temporal: nulable(texto), nota_temporal: texto, nota: texto,
});
const perdida = objeto<E["PerdidaGuardada"]>({
  modelo: numero, uniforme: numero, diferencia: numero, objetivos: nulable(entero), veredicto: texto,
});
export const decResumenResultadoGuardado = objeto<ResumenResultadoGuardado>({
  objetivos: entero, incluidos: entero, pendientes: entero, excluidos: entero, sin_base: entero,
  excluidos_por_motivo: diccionario(entero), muestra_pequena: booleano,
  aciertos: nulable(objeto<E["AciertosGuardados"]>({
    suma: entero, promedio: numero, de: entero, objetivos: entero, distribucion: diccionario(entero),
  })), perdidas: nulable(diccionario(perdida)),
  superbalota: nulable(objeto<E["SuperbalotaAgregada"]>({ aciertos: entero, objetivos: entero, log_loss: perdida, brier: perdida })),
});
const resultado = objeto<ResultadoGuardado>({ numeros: lista(entero), superbalota: nulable(entero), pares: lista(par) });
const emision = objeto<EmisionGuardada>({
  juego: texto, procedencia: texto, linea: texto, clave_linea: texto, objetivo: entero, tipo: nulable(texto),
  identificador: nulable(texto), versiones: nulable(entero), integridad: texto, historico: nulable(texto),
  resultado_estado: nulable(texto), estado: literal("incluido", "pendiente", "excluido", "sin_base"),
  motivo: nulable(texto), fecha_sorteo: nulable(texto), resultado: nulable(resultado), aciertos: nulable(entero), de: nulable(entero),
  metricas: nulable(diccionario(numero)),
  superbalota: nulable(objeto<E["SuperbalotaResultadoGuardado"]>({
    acierto: booleano, log_loss: numero, log_loss_uniforme: numero, brier: numero, brier_uniforme: numero,
  })),
});
const decResultadosBase = objeto<ResultadosGuardados>({
  juego: texto, estado_de_uso: uso,
  filtros: objeto<E["FiltrosResultadosGuardados"]>({
    procedencia: nulable(texto), linea: nulable(texto), tipo: texto, desde: nulable(entero), hasta: nulable(entero), objetivo: nulable(entero),
  }),
  base: objeto<E["BaseResultadosGuardados"]>({ estado: texto, motivo: nulable(texto), ultimo_sorteo: nulable(entero), fecha: nulable(texto), sorteos: nulable(entero) }),
  procedencias: diccionario(objeto<E["ProcedenciaGuardada"]>({
    nombre: texto, elegida: booleano, estado: texto, lineas: entero, emisiones: entero, ilegibles: entero, error: nulable(texto),
  })),
  lineas: lista(objeto<E["LineaResultadoGuardado"]>({
    clave: texto, procedencia: texto, linea: texto, nombre: texto, modelo: nulable(texto), version: nulable(texto), perfil: nulable(texto), registrado: nulable(referencia),
  })), seleccion: lista(texto), resumenes: diccionario(decResumenResultadoGuardado),
  comparacion: objeto<E["ComparacionResultadosGuardados"]>({
    tipo: texto, lineas: lista(texto), totales_individuales: diccionario(entero), objetivos_comunes: lista(entero),
    fuera_de_la_muestra_comun: lista(objeto<E["ExclusionComparacionGuardada"]>({ objetivo: entero, linea: nulable(texto), motivo: texto })),
    por_linea: diccionario(decResumenResultadoGuardado), uniforme: nulable(diccionario(diccionario(numero))),
    clasificacion: lista(objeto<E["ClasificacionGuardada"]>({ linea: texto, log_loss: numero, uniforme: numero, diferencia: numero, veredicto: texto })),
    estado: texto, motivo: nulable(texto), signo: texto, muestra_pequena: nulable(booleano),
  }),
  historial: objeto<E["HistorialResultadosGuardados"]>({ filas: lista(emision), total: entero, pagina: entero, paginas: entero, por_pagina: entero }),
  sin_resultados_de_seguimiento: booleano, politica: texto, nota_seguimiento: texto, signo: texto,
  unidades: diccionario(texto), nota: texto,
});

export const decResultadosGuardados: Decodificador<ResultadosGuardados> = (valor, ruta) => {
  const d = decResultadosBase(valor, ruta);
  const lineas = new Map(d.lineas.map((l) => [l.clave, l]));
  if (lineas.size !== d.lineas.length || d.lineas.some((l) => l.clave !== `${l.procedencia}:${l.linea}`)) {
    throw new EstructuraNoReconocida(`${ruta}.lineas`, "identidades de línea únicas y completas");
  }
  if (d.seleccion.some((k) => !lineas.has(k) || !(k in d.resumenes)) ||
      Object.keys(d.resumenes).some((k) => !lineas.has(k)) ||
      d.comparacion.tipo !== d.filtros.tipo || d.comparacion.lineas.some((k) => !d.seleccion.includes(k))) {
    throw new EstructuraNoReconocida(`${ruta}.seleccion`, "líneas y resúmenes del contexto seleccionado");
  }
  for (const [i, e] of d.historial.filas.entries()) {
    const l = lineas.get(e.clave_linea);
    // Producto 6 muestra los artefactos antiguos sin clasificación en ambas
    // vistas, siempre excluidos (_cerrar/de_tipo); no son retrospectivas ni
    // seguimiento admitido. Preservar ese estado no acepta otro tipo temporal.
    const sinClasificacion = e.tipo === "sin_clasificacion";
    const tipoCorresponde = e.tipo === null || e.tipo === d.filtros.tipo || sinClasificacion;
    if (!l || !d.seleccion.includes(e.clave_linea) || e.linea !== l.linea || e.procedencia !== l.procedencia ||
        !tipoCorresponde || (sinClasificacion && (e.estado !== "excluido" || e.metricas !== null || e.superbalota !== null))) {
      throw new EstructuraNoReconocida(`${ruta}.historial.filas[${i}]`, "una emisión de la línea y el tipo seleccionados");
    }
  }
  return d;
};

/** Defensa de atribución: las respuestas de otro juego o ficha no se presentan. */
export function delContexto<T extends { juego: string }>(
  decoder: Decodificador<T>, juego: string, identidad?: { clave: string; leer: (v: T) => { clave: string; juego: string } },
): Decodificador<T> {
  return (valor, ruta) => {
    const datos = decoder(valor, ruta);
    if (datos.juego !== juego) throw new EstructuraNoReconocida(`${ruta}.juego`, juego);
    if ("elementos" in datos && Array.isArray(datos.elementos)) {
      for (const [i, elemento] of datos.elementos.entries()) {
        if (!esObjeto(elemento) || elemento.juego !== juego) {
          throw new EstructuraNoReconocida(`${ruta}.elementos[${i}].juego`, juego);
        }
      }
    }
    if ("historial" in datos && esObjeto(datos.historial) && Array.isArray(datos.historial.filas)) {
      for (const [i, fila] of datos.historial.filas.entries()) {
        if (!esObjeto(fila) || fila.juego !== juego) {
          throw new EstructuraNoReconocida(`${ruta}.historial.filas[${i}].juego`, juego);
        }
      }
    }
    if (identidad) {
      const ficha = identidad.leer(datos);
      if (ficha.juego !== juego || ficha.clave !== identidad.clave) {
        throw new EstructuraNoReconocida(`${ruta}.identidad`, "la ficha del juego e identificador solicitados");
      }
    }
    return datos;
  };
}
