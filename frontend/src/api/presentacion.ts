/**
 * Tipos de presentacion de /api/v1 y sus decodificadores.
 *
 * Las partes con contrato cerrado reutilizan los tipos generados del OpenAPI
 * versionado (`esquema.d.ts`). Las zonas genericas del contrato
 * (`{[key: string]: unknown}`: resumen, panel, metrica, prediccion,
 * simulacion) se describen aqui solo en lo que la interfaz muestra y se
 * validan en ejecucion; lo que no encaja es `EstructuraNoReconocida`. La
 * interfaz no calcula estadisticas, vigencia, integridad ni aciertos: los
 * presenta tal como llegan.
 */
import type { components } from "./esquema";
import {
  type Campos,
  type Decodificador,
  type Json,
  booleano,
  celda,
  diccionario,
  entero,
  esObjeto,
  etiqueta,
  EstructuraNoReconocida,
  json,
  lista,
  literal,
  nulable,
  numero,
  objeto,
  objetoJson,
  texto,
  tupla,
} from "./decodificar";

type Esquema = components["schemas"];

// ---------------------------------------------------------------------------
// Juegos y sorteos (contrato cerrado)
// ---------------------------------------------------------------------------

export type Juego = Esquema["Juego"];
export type JuegoDetalle = Omit<Esquema["JuegoDetalle"], "dimensiones"> & { dimensiones: Record<string, Json> };
export type Par = Esquema["Par"];
export type Sorteo = Esquema["Sorteo"];
export type PaginaDeSorteos = Esquema["PaginaDeSorteos"];
export type IndiceDeEstadisticas = Esquema["IndiceDeEstadisticas"];
export type Salud = Esquema["Salud"];
export type Ruta = Esquema["Ruta"];
export type EstadoDelServicio = Omit<Esquema["EstadoDelServicio"], "limites"> & { limites: Record<string, Json> };

const camposJuego: Campos<Juego> = {
  codigo: texto,
  nombre: texto,
  rango_min: entero,
  rango_max: entero,
  cantidad_numeros: entero,
  tiene_superbalota: booleano,
  superbalota_min: nulable(entero),
  superbalota_max: nulable(entero),
  tiene_color: booleano,
  permite_repeticion: booleano,
};

export const decJuego = objeto<Juego>(camposJuego);
export const decJuegos = objeto<Esquema["Juegos"]>({ juegos: lista(decJuego) });
export const decJuegoDetalle = objeto<JuegoDetalle>({
  ...camposJuego,
  espacio_muestral: entero,
  dimensiones: objetoJson,
});

const decPar = objeto<Par>({ numero: entero, color_codigo: texto, color_nombre: texto });
export const decSorteo = objeto<Sorteo>({
  numero_sorteo: entero,
  fecha: texto,
  dia_semana: texto,
  numeros: lista(entero),
  superbalota: nulable(entero),
  pares: lista(decPar),
});
export const decPaginaDeSorteos = objeto<PaginaDeSorteos>({
  juego: texto,
  pagina: entero,
  por_pagina: entero,
  total: entero,
  paginas: entero,
  sorteos: lista(decSorteo),
});

export const decIndice = objeto<IndiceDeEstadisticas>({
  juego: texto,
  resumen: texto,
  panel: texto,
  metricas: lista(
    objeto<Esquema["MetricaDisponible"]>({
      metrica: texto,
      titulo: texto,
      grupo: texto,
      origen: literal("fase5", "anterior"),
      parametro: nulable(literal("anio", "mes", "dia_semana", "ventana", "color")),
      paginada: booleano,
    }),
  ),
});

export const decSalud = objeto<Salud>({ estado: texto, api: texto });
const decRuta = objeto<Ruta>({
  metodo: texto,
  ruta: texto,
  solicitudes: entero,
  errores_4xx: entero,
  errores_5xx: entero,
  latencia_media_ms: numero,
  latencia_maxima_ms: numero,
});
export const decEstado = objeto<EstadoDelServicio>({
  api: texto,
  iniciado_en: texto,
  segundos_activo: numero,
  base: texto,
  solicitudes: entero,
  por_clase: (v, r) => {
    const o = objetoJson(v, r);
    return Object.fromEntries(Object.entries(o).map(([k, x]) => [k, entero(x, `${r}.${k}`)]));
  },
  rutas: lista(decRuta),
  limites: objetoJson,
  claves_configuradas: entero,
});

// ---------------------------------------------------------------------------
// Cabecera comun del resumen, el panel y las metricas (frescura incluida)
// ---------------------------------------------------------------------------

export type Intervalo = [number, number];
const intervalo: Decodificador<Intervalo> = tupla(entero, entero);

export type Reglas =
  | { tipo: "numeros"; rango: Intervalo; cantidad_numeros: number; superbalota: Intervalo | null }
  | { tipo: "colorloto"; rango: Intervalo; cantidad_balotas: number; colores: string[]; permite_repeticion: boolean };

const decReglas: Decodificador<Reglas> = (v, r) => {
  const tipo = esObjeto(v) ? v.tipo : undefined;
  if (tipo === "colorloto") {
    return {
      tipo,
      ...objeto({
        rango: intervalo,
        cantidad_balotas: entero,
        colores: lista(texto),
        permite_repeticion: booleano,
      })(v, r),
    };
  }
  if (tipo === "numeros") {
    return {
      tipo,
      ...objeto({ rango: intervalo, cantidad_numeros: entero, superbalota: nulable(intervalo) })(v, r),
    };
  }
  throw new EstructuraNoReconocida(`${r}.tipo`, "numeros|colorloto");
};

/** Frescura del historico tal como la informa el backend (resumen, panel y metricas). */
export interface Frescura {
  estado: string;
  dias_desde_el_ultimo_sorteo: number | null;
  mensaje: string;
}

export const decFrescura = objeto<Frescura>({
  estado: texto,
  dias_desde_el_ultimo_sorteo: nulable(entero),
  mensaje: texto,
});

export interface Cabecera {
  codigo_juego: string;
  nombre: string;
  reglas: Reglas;
  total_sorteos: number;
  total_sorteos_sin_corte: number;
  corte: { hasta_numero_sorteo: number | null; descripcion: string };
  periodo: { primer_sorteo: number; primera_fecha: string; ultimo_sorteo: number; ultima_fecha: string } | null;
  ultimo_sorteo_disponible: { numero_sorteo: number; fecha: string } | null;
  frescura: Frescura;
  huecos: { cantidad: number; primeros: number[]; cobertura: number | null };
  consultado_el: string;
}

export const decCabecera = objeto<Cabecera>({
  codigo_juego: texto,
  nombre: texto,
  reglas: decReglas,
  total_sorteos: entero,
  total_sorteos_sin_corte: entero,
  corte: objeto({ hasta_numero_sorteo: nulable(entero), descripcion: texto }),
  periodo: nulable(
    objeto({ primer_sorteo: entero, primera_fecha: texto, ultimo_sorteo: entero, ultima_fecha: texto }),
  ),
  ultimo_sorteo_disponible: nulable(objeto({ numero_sorteo: entero, fecha: texto })),
  frescura: decFrescura,
  huecos: objeto({ cantidad: entero, primeros: lista(entero), cobertura: nulable(numero) }),
  consultado_el: texto,
});

// ---------------------------------------------------------------------------
// Resumen (Producto 1)
// ---------------------------------------------------------------------------

export interface FilaFrecuencia {
  valor: string;
  apariciones: number;
  frecuencia_relativa: number;
}
export interface Frecuencias {
  todas: FilaFrecuencia[];
  mas_frecuentes: FilaFrecuencia[];
  menos_frecuentes: FilaFrecuencia[];
}
export interface FilaAtraso {
  valor: string;
  atraso: number;
  ultimo_sorteo: number | null;
}
export interface Atrasos {
  mayores: FilaAtraso[];
  nunca_observados: string[];
}
export interface FilaDistribucion {
  valor: string;
  sorteos: number;
  frecuencia_relativa: number;
}
export interface Decenas {
  filas: (FilaDistribucion & { apariciones: number; porcentaje_de_numeros_extraidos: number | null })[];
  denominador: { sorteos: number; numeros_por_sorteo: number; numeros_extraidos: number };
}
export interface EstadisticasNumeros {
  frecuencia_numeros: Frecuencias;
  atrasos_numeros: Atrasos;
  pares_impares: FilaDistribucion[];
  altos_bajos: FilaDistribucion[];
  decenas_sobre_numeros_extraidos: Decenas;
  superbalota: { frecuencia: Frecuencias; atrasos: Atrasos } | null;
}
export interface EstadisticasColorloto {
  frecuencia_colores: Frecuencias;
  frecuencia_numeros: Frecuencias;
  frecuencia_pares: Frecuencias;
  atrasos_colores: Atrasos;
  atrasos_numeros: Atrasos;
  pares_impares: FilaDistribucion[];
  altos_bajos: FilaDistribucion[];
  maximo_repeticion_color: FilaDistribucion[];
  colores_fuera_de_la_paleta_vigente: string[];
}

export type ResultadoNumeros = { numeros: number[]; superbalota: number | null };
export type ParNumeroColor = [number, string];
export type ResultadoColorloto = { pares: ParNumeroColor[] };
export type Resultado = ResultadoNumeros | ResultadoColorloto;

const parNumeroColor: Decodificador<ParNumeroColor> = tupla(entero, texto);
const decResultadoNumeros = objeto<ResultadoNumeros>({ numeros: lista(entero), superbalota: nulable(entero) });
const decResultadoColorloto = objeto<ResultadoColorloto>({ pares: lista(parNumeroColor) });
/** Resultado de un sorteo: pares numero-color (ColorLoto) o numeros con superbalota opcional. */
export const decResultado: Decodificador<Resultado> = (v, r) =>
  esObjeto(v) && "pares" in v ? decResultadoColorloto(v, r) : decResultadoNumeros(v, r);

const filaFrecuencia = objeto<FilaFrecuencia>({ valor: etiqueta, apariciones: entero, frecuencia_relativa: numero });
const frecuencias = objeto<Frecuencias>({
  todas: lista(filaFrecuencia),
  mas_frecuentes: lista(filaFrecuencia),
  menos_frecuentes: lista(filaFrecuencia),
});
const atrasos = objeto<Atrasos>({
  mayores: lista(objeto<FilaAtraso>({ valor: etiqueta, atraso: entero, ultimo_sorteo: nulable(entero) })),
  nunca_observados: lista(etiqueta),
});
const filaDistribucion = objeto<FilaDistribucion>({ valor: etiqueta, sorteos: entero, frecuencia_relativa: numero });
const distribucion = lista(filaDistribucion);

const decEstadisticasNumeros = objeto<EstadisticasNumeros>({
  frecuencia_numeros: frecuencias,
  atrasos_numeros: atrasos,
  pares_impares: distribucion,
  altos_bajos: distribucion,
  decenas_sobre_numeros_extraidos: objeto<Decenas>({
    filas: lista((v, r) => ({
      ...filaDistribucion(v, r),
      ...objeto({ apariciones: entero, porcentaje_de_numeros_extraidos: nulable(numero) })(v, r),
    })),
    denominador: objeto({ sorteos: entero, numeros_por_sorteo: entero, numeros_extraidos: entero }),
  }),
  superbalota: nulable(objeto({ frecuencia: frecuencias, atrasos })),
});
const decEstadisticasColorloto = objeto<EstadisticasColorloto>({
  frecuencia_colores: frecuencias,
  frecuencia_numeros: frecuencias,
  frecuencia_pares: frecuencias,
  atrasos_colores: atrasos,
  atrasos_numeros: atrasos,
  pares_impares: distribucion,
  altos_bajos: distribucion,
  maximo_repeticion_color: distribucion,
  colores_fuera_de_la_paleta_vigente: lista(texto),
});

export type Resumen = Cabecera &
  (
    | { tipo: "numeros"; ultimo_resultado: ResultadoNumeros | null; estadisticas: EstadisticasNumeros | null }
    | { tipo: "colorloto"; ultimo_resultado: ResultadoColorloto | null; estadisticas: EstadisticasColorloto | null }
  );

export const decResumen: Decodificador<Resumen> = (v, r) => {
  const cabecera = decCabecera(v, r);
  const o = v as Record<string, unknown>;
  if (cabecera.reglas.tipo === "colorloto") {
    return {
      ...cabecera,
      tipo: "colorloto",
      ultimo_resultado: nulable(decResultadoColorloto)(o.ultimo_resultado, `${r}.ultimo_resultado`),
      estadisticas: nulable(decEstadisticasColorloto)(o.estadisticas, `${r}.estadisticas`),
    };
  }
  return {
    ...cabecera,
    tipo: "numeros",
    ultimo_resultado: nulable(decResultadoNumeros)(o.ultimo_resultado, `${r}.ultimo_resultado`),
    estadisticas: nulable(decEstadisticasNumeros)(o.estadisticas, `${r}.estadisticas`),
  };
};

// ---------------------------------------------------------------------------
// Panel y metricas (Fase 5)
// ---------------------------------------------------------------------------

export interface Indicador {
  etiqueta: string;
  valor: number | string | null;
  unidad: string;
  formato: string;
}
export const decIndicador = objeto<Indicador>({ etiqueta: texto, valor: celda, unidad: texto, formato: texto });

export interface MetricaDelPanel {
  slug: string;
  titulo: string;
  aplica: boolean;
  nueva: boolean;
  motivo: string | null;
  estado: string;
  indicadores: Indicador[];
}
export interface GrupoDelPanel {
  clave: string;
  titulo: string;
  metricas: MetricaDelPanel[];
}
export interface JuegoDeLaMuestra {
  codigo: string;
  nombre: string;
}
export interface Panel {
  juego: JuegoDeLaMuestra;
  muestra: Cabecera;
  grupos: GrupoDelPanel[];
}

const decJuegoDeLaMuestra = objeto<JuegoDeLaMuestra>({ codigo: texto, nombre: texto });

export const decPanel = objeto<Panel>({
  juego: decJuegoDeLaMuestra,
  muestra: decCabecera,
  grupos: lista(
    objeto<GrupoDelPanel>({
      clave: texto,
      titulo: texto,
      metricas: lista(
        objeto<MetricaDelPanel>({
          slug: texto,
          titulo: texto,
          aplica: booleano,
          nueva: booleano,
          motivo: nulable(texto),
          estado: texto,
          indicadores: lista(decIndicador),
        }),
      ),
    }),
  ),
});

export interface Columna {
  clave: string;
  etiqueta: string;
  formato: string;
  unidad: string;
}
export type Paginacion = Esquema["Paginacion"];
export interface TablaDeMetrica {
  id: string;
  titulo: string;
  columnas: Columna[];
  /** Filas completas: las claves fuera de `columnas` se muestran como datos adicionales. */
  filas: Record<string, Json>[];
  nota: string | null;
  /** Solo en las tablas paginadas por la API (las demas llegan completas). */
  paginacion: Paginacion | null;
}
export interface Grafica {
  titulo: string;
  /** `id` de la tabla con los mismos valores. */
  tabla: string | null;
  unidad: string | null;
  referencia: number | null;
  etiqueta_referencia: string | null;
}
export interface OpcionDelSelector {
  valor: string;
  etiqueta: string;
  sorteos: number | null;
}
export interface Selector {
  parametro: string;
  valor: string | null;
  etiqueta: string | null;
  opciones: OpcionDelSelector[];
}
export interface Metrica {
  slug: string;
  titulo: string;
  grupo: string;
  /** fase5: pagina del catalogo de la Fase 5; anterior: receta de la consola (Fase 9.2). */
  origen: "fase5" | "anterior";
  parametro: string | null;
  estado: string;
  motivo: string | null;
  indicadores: Indicador[];
  tablas: TablaDeMetrica[];
  grafica: Grafica | null;
  notas: string[];
  selector: Selector | null;
}
export interface RespuestaDeMetrica {
  juego: JuegoDeLaMuestra;
  muestra: Cabecera;
  metrica: Metrica;
}

const decColumna = objeto<Columna>({ clave: texto, etiqueta: texto, formato: texto, unidad: texto });
const decPaginacion = objeto<Paginacion>({ pagina: entero, por_pagina: entero, total_filas: entero, total_paginas: entero });
export const decMetrica = objeto<Metrica>({
  slug: texto,
  titulo: texto,
  grupo: texto,
  origen: literal("fase5", "anterior"),
  parametro: nulable(texto),
  estado: texto,
  motivo: nulable(texto),
  indicadores: lista(decIndicador),
  tablas: lista(
    objeto<TablaDeMetrica>({
      id: texto,
      titulo: texto,
      columnas: lista(decColumna),
      filas: lista(objetoJson),
      nota: nulable(texto),
      paginacion: nulable(decPaginacion),
    }),
  ),
  grafica: nulable(
    objeto<Grafica>({
      titulo: texto,
      tabla: nulable(texto),
      unidad: nulable(texto),
      referencia: nulable(numero),
      etiqueta_referencia: nulable(texto),
    }),
  ),
  notas: lista(texto),
  selector: nulable(
    objeto<Selector>({
      parametro: texto,
      valor: nulable(etiqueta),
      etiqueta: nulable(etiqueta),
      opciones: lista(objeto<OpcionDelSelector>({ valor: etiqueta, etiqueta: etiqueta, sorteos: nulable(entero) })),
    }),
  ),
});
export const decRespuestaDeMetrica = objeto<RespuestaDeMetrica>({
  juego: decJuegoDeLaMuestra,
  muestra: decCabecera,
  metrica: decMetrica,
});

// ---------------------------------------------------------------------------
// Predicciones guardadas (Fase 4)
// ---------------------------------------------------------------------------

export type BaseDelJuego = Esquema["BaseDelJuego"];
export type PrediccionGuardada = Esquema["PrediccionGuardada"];
export type ModeloDeLaPrediccion = Esquema["ModeloDeLaPrediccion"];

export interface ClasificacionTemporal {
  tipo: string;
  descripcion: string;
  objetivo: number | null;
  objetivo_en_la_base: boolean | null;
  ultimo_sorteo_disponible: number | null;
  ultima_fecha_disponible: string | null;
  resultado_observado: Resultado | null;
}
export interface Combinacion {
  linea: number;
  resultado: Resultado;
  papel: string | null;
  detalle: string | null;
  probabilidades_de_sus_elementos: number[] | null;
  unidad_de_los_elementos: string | null;
  probabilidad_de_su_superbalota: number | null;
}
export interface AciertoDeLinea {
  linea: number;
  aciertos: number;
  superbalota: boolean | null;
}
export interface Observado {
  estado: string;
  motivo: string | null;
  historico_hasta_el_corte: string | null;
  ultimo_sorteo_actual: number | null;
  fecha: string | null;
  resultado: Resultado | null;
  aciertos: { por_linea: AciertoDeLinea[]; maximo: number | null; definicion: string } | null;
}
export interface FrenteALaBase {
  estado: string;
  historico_hasta_el_corte: string | null;
  ultimo_sorteo_actual: number | null;
  base_avanzo: boolean | null;
  nuevos_desde_el_corte: number | null;
}
// Clasificacion de candidatos y explicacion guardada (Fase 9.3). La API ya
// envia los rankings ordenados con su referencia uniforme: aqui no se recalculan.

export type Candidato = number | string | ParNumeroColor;
export interface FilaDeRanking {
  posicion: number;
  candidato: Candidato;
  probabilidad: number;
  uniforme: number;
  diferencia: number;
  razon: number | null;
  multiplicidad_esperada: number | null;
}
export interface SeccionDeRanking {
  todos: FilaDeRanking[];
  fuertes: FilaDeRanking[] | null;
  debiles: FilaDeRanking[] | null;
  universo: number;
  por_extremo: number | null;
  empate_en_el_limite: Record<string, boolean> | null;
  nota_empates: string | null;
  suma: number | null;
  unidad: string;
  denominador: string;
  nota: string | null;
  estrategia: string | null;
}
export interface Rankings {
  aviso: string;
  objetivo: number;
  corte: number;
  numeros: SeccionDeRanking;
  superbalota: SeccionDeRanking | null;
  pares: SeccionDeRanking | null;
  colores: SeccionDeRanking | null;
}
export type LineaDeModelo = Esquema["LineaDeModelo"];
export type VersionRegistradaDeLaCartera = Esquema["VersionRegistradaDeLaCartera"];
export interface MetodoDeLaExplicacion {
  modelo: string;
  nombre: string;
  version_de_la_receta: string;
  perfil: string;
  salida: string;
  objetivo: number;
  corte: number;
  familia: string;
  tipo: string | null;
  variables: { version: string; nombres: string[]; descripcion: string | null } | null;
  transformacion: { tipo: string; detalle: string | null; delta: number | null; epsilon: number | null; tolerancia: number | null } | null;
  parametros: Record<string, Json> | null;
  pesos: { componente: string; peso: number }[] | null;
  entrenamiento: {
    estimador: string;
    corte_de_entrenamiento: number | null;
    periodo: Record<string, Json> | null;
    parametros_ajustados: Record<string, Json> | null;
    detalle: Json;
  } | null;
  registrado: { clave: string; numero: number; corte_de_entrenamiento: number | null; sha256_estimador: string | null } | null;
}
export interface VariablesDeCandidatos {
  version: string;
  nombres: string[];
  por_candidato: Record<string, number[]>;
  usadas_por_el_modelo: boolean;
  calculado_hasta_sorteo: number;
  nota: string | null;
}
export interface ImportanciaDeVariable {
  variable: string;
  valor: number | null;
  columnas: number;
  es_identidad: boolean;
  resumen: { minimo: number; maximo: number; media_absoluta: number } | null;
}
export interface Importancias {
  estado: "disponible" | "no_disponible";
  motivo: string | null;
  tipo: string | null;
  descripcion: string | null;
  estimador: string | null;
  calibrado: boolean | null;
  valores: ImportanciaDeVariable[] | null;
  aviso: string | null;
}
export interface Explicacion {
  clave: string;
  esquema: string;
  version: string;
  cartera: Esquema["CarteraDeLaExplicacion"];
  metodo: MetodoDeLaExplicacion;
  variables: VariablesDeCandidatos | null;
  importancias: Importancias;
  avisos: string[];
  generacion: { generado_en: string | null; origen: string | null; nota: string | null } | null;
}
export interface Reproduccion {
  exacta: boolean;
  distintos: string[];
  motivo: string | null;
  nota: string | null;
}

export interface Prediccion {
  clave: string;
  integridad: string;
  linea: string;
  objetivo: number;
  corte: number | null;
  sha256_historico: string | null;
  generado_en: string | null;
  clasificacion_temporal: ClasificacionTemporal | null;
  modelo: ModeloDeLaPrediccion;
  combinaciones: Combinacion[];
  rankings: Rankings | null;
  observado: Observado | null;
  frente_a_la_base: FrenteALaBase | null;
  explicacion_disponible: boolean;
  linea_de_modelo: LineaDeModelo | null;
  registrado: VersionRegistradaDeLaCartera | null;
  explicacion: Explicacion | null;
  explicaciones_ilegibles: Esquema["ExplicacionIlegible"][];
  reproduccion: Reproduccion | null;
}
export interface Predicciones {
  juego: string;
  nombre: string;
  estado_de_uso: string;
  aviso: string;
  contexto: Record<string, Json>;
  configuracion: string;
  base: BaseDelJuego;
  prediccion: Prediccion | null;
  historial: PrediccionGuardada[];
  historial_total: number;
}

const decCombinacion: Decodificador<Combinacion> = (v, r) => ({
  linea: entero(esObjeto(v) ? v.linea : undefined, `${r}.linea`),
  resultado: decResultado(v, r),
  ...objeto({
    papel: nulable(texto),
    detalle: nulable(texto),
    probabilidades_de_sus_elementos: nulable(lista(numero)),
    unidad_de_los_elementos: nulable(texto),
    probabilidad_de_su_superbalota: nulable(numero),
  })(v, r),
});

const candidato: Decodificador<Candidato> = (v, r) =>
  typeof v === "string" ? v : Array.isArray(v) ? parNumeroColor(v, r) : entero(v, r);
const decFilaDeRanking = objeto<FilaDeRanking>({
  posicion: entero,
  candidato,
  probabilidad: numero,
  uniforme: numero,
  diferencia: numero,
  razon: nulable(numero),
  multiplicidad_esperada: nulable(numero),
});
const decSeccionDeRanking = objeto<SeccionDeRanking>({
  todos: lista(decFilaDeRanking),
  fuertes: nulable(lista(decFilaDeRanking)),
  debiles: nulable(lista(decFilaDeRanking)),
  universo: entero,
  por_extremo: nulable(entero),
  empate_en_el_limite: nulable(diccionario(booleano)),
  nota_empates: nulable(texto),
  suma: nulable(numero),
  unidad: texto,
  denominador: texto,
  nota: nulable(texto),
  estrategia: nulable(texto),
});
export const decRankings = objeto<Rankings>({
  aviso: texto,
  objetivo: entero,
  corte: entero,
  numeros: decSeccionDeRanking,
  superbalota: nulable(decSeccionDeRanking),
  pares: nulable(decSeccionDeRanking),
  colores: nulable(decSeccionDeRanking),
});
const decExplicacion = objeto<Explicacion>({
  clave: texto,
  esquema: texto,
  version: texto,
  cartera: objeto<Esquema["CarteraDeLaExplicacion"]>({
    clave: texto,
    linea: texto,
    objetivo: entero,
    corte: entero,
    sha256_historico: nulable(texto),
    sha256_fuente: texto,
  }),
  metodo: objeto<MetodoDeLaExplicacion>({
    modelo: texto,
    nombre: texto,
    version_de_la_receta: texto,
    perfil: texto,
    salida: texto,
    objetivo: entero,
    corte: entero,
    familia: texto,
    tipo: nulable(texto),
    variables: nulable(objeto({ version: texto, nombres: lista(texto), descripcion: nulable(texto) })),
    transformacion: nulable(
      objeto({ tipo: texto, detalle: nulable(texto), delta: nulable(numero), epsilon: nulable(numero), tolerancia: nulable(numero) }),
    ),
    parametros: nulable(objetoJson),
    pesos: nulable(lista(objeto({ componente: texto, peso: numero }))),
    entrenamiento: nulable(
      objeto({
        estimador: texto,
        corte_de_entrenamiento: nulable(entero),
        periodo: nulable(objetoJson),
        parametros_ajustados: nulable(objetoJson),
        detalle: (v, r) => (v === undefined ? null : json(v, r)),
      }),
    ),
    registrado: nulable(
      objeto({ clave: texto, numero: entero, corte_de_entrenamiento: nulable(entero), sha256_estimador: nulable(texto) }),
    ),
  }),
  variables: nulable(
    objeto<VariablesDeCandidatos>({
      version: texto,
      nombres: lista(texto),
      por_candidato: diccionario(lista(numero)),
      usadas_por_el_modelo: booleano,
      calculado_hasta_sorteo: entero,
      nota: nulable(texto),
    }),
  ),
  importancias: objeto<Importancias>({
    estado: literal("disponible", "no_disponible"),
    motivo: nulable(texto),
    tipo: nulable(texto),
    descripcion: nulable(texto),
    estimador: nulable(texto),
    calibrado: nulable(booleano),
    valores: nulable(
      lista(
        objeto<ImportanciaDeVariable>({
          variable: texto,
          valor: nulable(numero),
          columnas: entero,
          es_identidad: booleano,
          resumen: nulable(objeto({ minimo: numero, maximo: numero, media_absoluta: numero })),
        }),
      ),
    ),
    aviso: nulable(texto),
  }),
  avisos: lista(texto),
  generacion: nulable(objeto({ generado_en: nulable(texto), origen: nulable(texto), nota: nulable(texto) })),
});

export const decPredicciones = objeto<Predicciones>({
  juego: texto,
  nombre: texto,
  estado_de_uso: texto,
  aviso: texto,
  contexto: objetoJson,
  configuracion: texto,
  base: objeto<BaseDelJuego>({
    estado: texto,
    corte: nulable(entero),
    sorteos: nulable(entero),
    ultima_fecha: nulable(texto),
    objetivo: nulable(entero),
  }),
  prediccion: nulable(
    objeto<Prediccion>({
      clave: texto,
      integridad: texto,
      linea: texto,
      objetivo: entero,
      corte: nulable(entero),
      sha256_historico: nulable(texto),
      generado_en: nulable(texto),
      clasificacion_temporal: nulable(
        objeto<ClasificacionTemporal>({
          tipo: texto,
          descripcion: texto,
          objetivo: nulable(entero),
          objetivo_en_la_base: nulable(booleano),
          ultimo_sorteo_disponible: nulable(entero),
          ultima_fecha_disponible: nulable(texto),
          resultado_observado: nulable(decResultado),
        }),
      ),
      modelo: objeto<ModeloDeLaPrediccion>({
        id: nulable(texto),
        nombre: nulable(texto),
        familia: nulable(texto),
        tipo: nulable(texto),
        version: nulable(texto),
      }),
      combinaciones: lista(decCombinacion),
      rankings: nulable(decRankings),
      observado: nulable(
        objeto<Observado>({
          estado: texto,
          motivo: nulable(texto),
          historico_hasta_el_corte: nulable(texto),
          ultimo_sorteo_actual: nulable(entero),
          fecha: nulable(texto),
          resultado: nulable(decResultado),
          aciertos: nulable(
            objeto({
              por_linea: lista(
                objeto<AciertoDeLinea>({ linea: entero, aciertos: entero, superbalota: nulable(booleano) }),
              ),
              maximo: nulable(entero),
              definicion: texto,
            }),
          ),
        }),
      ),
      frente_a_la_base: nulable(
        objeto<FrenteALaBase>({
          estado: texto,
          historico_hasta_el_corte: nulable(texto),
          ultimo_sorteo_actual: nulable(entero),
          base_avanzo: nulable(booleano),
          nuevos_desde_el_corte: nulable(entero),
        }),
      ),
      explicacion_disponible: booleano,
      linea_de_modelo: nulable(objeto<LineaDeModelo>({ id: texto, modelo: texto, version: texto, perfil: texto, nombre: texto })),
      registrado: nulable(objeto<VersionRegistradaDeLaCartera>({ clave: texto, numero: entero })),
      explicacion: nulable(decExplicacion),
      explicaciones_ilegibles: lista(objeto<Esquema["ExplicacionIlegible"]>({ clave: texto, motivo: texto })),
      reproduccion: nulable(
        objeto<Reproduccion>({ exacta: booleano, distintos: lista(texto), motivo: nulable(texto), nota: nulable(texto) }),
      ),
    }),
  ),
  historial: lista(
    objeto<PrediccionGuardada>({
      clave: texto,
      linea: nulable(texto),
      objetivo: nulable(entero),
      corte: nulable(entero),
      generado_en: nulable(texto),
      tipo: nulable(texto),
      ilegible: nulable(texto),
    }),
  ),
  historial_total: entero,
});

// ---------------------------------------------------------------------------
// Fiabilidad observada (Fase 4, consultada en la 9.3): rendimiento observado e
// incertidumbre por separado; no hay puntuacion de confianza que mostrar.
// ---------------------------------------------------------------------------

export type IntervaloDeFiabilidad = [number, number];
export interface MetricaDeFiabilidad {
  estado: string;
  n: number | null;
  media: number | null;
  intervalo: IntervaloDeFiabilidad | null;
  motivo: string | null;
  etiqueta: string | null;
  lectura: string | null;
  bloque: number | null;
  remuestreos: number | null;
  nivel: number | null;
  /** Texto decimal: la semilla puede superar la precision entera de JavaScript. */
  semilla: string | null;
  error_estandar_bootstrap: number | null;
}
export interface ExtremoObservado {
  candidatos_por_sorteo: number;
  observado: number;
  esperado: number;
  razon_observado_esperado: number | null;
}
export interface ComponenteDeFiabilidad {
  estado: string | null;
  motivo: string | null;
  sorteos: number | null;
  metricas: Record<string, MetricaDeFiabilidad> | null;
  extremos: { fuertes: ExtremoObservado | null; debiles: ExtremoObservado | null } | null;
  identidad_remuestreo: Record<string, string> | null;
}
export interface MuestraDeFiabilidad {
  sorteos: number | null;
  periodo: Intervalo | null;
  hasta: number | null;
  emisiones: number | null;
  pendientes: number | null;
  sin_base: number | null;
  exclusiones: Esquema["ExclusionDeFiabilidad"][];
  estado_del_candidato: string | null;
  excluidos_de_la_muestra_comun: number | null;
}
export interface EvaluacionDeFiabilidad {
  tipo: "seguimiento" | "retrospectiva" | "evaluacion_de_receta";
  descripcion: string | null;
  estado: string;
  motivo: string | null;
  muestra: MuestraDeFiabilidad | null;
  componentes: Record<string, ComponenteDeFiabilidad>;
  origen: string | null;
  informe: string | null;
  corte_del_informe: number | null;
  clasificacion_componentes: Record<string, string> | null;
}
export interface LineaDeFiabilidad {
  linea: string;
  papel: string;
  nombre: string;
  estimador: string;
  evaluaciones: EvaluacionDeFiabilidad[];
}
export interface MetodoDeFiabilidad {
  version: string;
  unidad: string;
  estimacion: string;
  incertidumbre: string;
  minimo_para_intervalo: number;
  supuestos: string;
  limitaciones: string[];
  extremos: Record<string, number>;
  presentacion: Esquema["PresentacionDelMetodo"];
  fuentes: Esquema["FuenteDelMetodo"][];
}
export interface Fiabilidad {
  juego: string;
  nombre: string;
  estado_de_uso: string;
  aviso: string;
  contexto: Record<string, Json>;
  configuracion: string;
  registrado: Esquema["VersionRegistradaDeLaConfiguracion"] | null;
  base: { estado: string; ultimo_sorteo: number | null; fecha: string | null; sorteos: number | null };
  hasta: number | null;
  metodo: MetodoDeFiabilidad;
  lineas: LineaDeFiabilidad[];
  receta: EvaluacionDeFiabilidad;
}

const intervaloReal: Decodificador<IntervaloDeFiabilidad> = tupla(numero, numero);
const decExtremo = objeto<ExtremoObservado>({
  candidatos_por_sorteo: entero,
  observado: numero,
  esperado: numero,
  razon_observado_esperado: nulable(numero),
});
const decMetricaDeFiabilidad = objeto<MetricaDeFiabilidad>({
  estado: texto,
  n: nulable(entero),
  media: nulable(numero),
  intervalo: nulable(intervaloReal),
  motivo: nulable(texto),
  etiqueta: nulable(texto),
  lectura: nulable(texto),
  bloque: nulable(entero),
  remuestreos: nulable(entero),
  nivel: nulable(numero),
  semilla: nulable(texto),
  error_estandar_bootstrap: nulable(numero),
});
const decEvaluacionDeFiabilidad = objeto<EvaluacionDeFiabilidad>({
  tipo: literal("seguimiento", "retrospectiva", "evaluacion_de_receta"),
  descripcion: nulable(texto),
  estado: texto,
  motivo: nulable(texto),
  muestra: nulable(
    objeto<MuestraDeFiabilidad>({
      sorteos: nulable(entero),
      periodo: nulable(intervalo),
      hasta: nulable(entero),
      emisiones: nulable(entero),
      pendientes: nulable(entero),
      sin_base: nulable(entero),
      exclusiones: lista(objeto<Esquema["ExclusionDeFiabilidad"]>({ estado: texto, motivo: texto, emisiones: entero })),
      estado_del_candidato: nulable(texto),
      excluidos_de_la_muestra_comun: nulable(entero),
    }),
  ),
  componentes: diccionario(
    objeto<ComponenteDeFiabilidad>({
      estado: nulable(texto),
      motivo: nulable(texto),
      sorteos: nulable(entero),
      metricas: nulable(diccionario(decMetricaDeFiabilidad)),
      extremos: nulable(objeto({ fuertes: nulable(decExtremo), debiles: nulable(decExtremo) })),
      identidad_remuestreo: nulable(diccionario(texto)),
    }),
  ),
  origen: nulable(texto),
  informe: nulable(texto),
  corte_del_informe: nulable(entero),
  clasificacion_componentes: nulable(diccionario(texto)),
});
export const decFiabilidad = objeto<Fiabilidad>({
  juego: texto,
  nombre: texto,
  estado_de_uso: texto,
  aviso: texto,
  contexto: objetoJson,
  configuracion: texto,
  registrado: nulable(objeto<Esquema["VersionRegistradaDeLaConfiguracion"]>({ clave: texto, numero: entero, estado: texto })),
  base: objeto({ estado: texto, ultimo_sorteo: nulable(entero), fecha: nulable(texto), sorteos: nulable(entero) }),
  hasta: nulable(entero),
  metodo: objeto<MetodoDeFiabilidad>({
    version: texto,
    unidad: texto,
    estimacion: texto,
    incertidumbre: texto,
    minimo_para_intervalo: entero,
    supuestos: texto,
    limitaciones: lista(texto),
    extremos: diccionario(entero),
    presentacion: objeto<Esquema["PresentacionDelMetodo"]>({
      umbral_absoluto_proximo_a_cero: numero,
      criterio: texto,
      formato: texto,
    }),
    fuentes: lista(objeto<Esquema["FuenteDelMetodo"]>({ cita: texto, doi: nulable(texto), uso: texto })),
  }),
  lineas: lista(
    objeto<LineaDeFiabilidad>({
      linea: texto,
      papel: texto,
      nombre: texto,
      estimador: texto,
      evaluaciones: lista(decEvaluacionDeFiabilidad),
    }),
  ),
  receta: decEvaluacionDeFiabilidad,
});

// Los tipos de presentacion (sin campos opcionales) encajan en el contrato generado.
type Encaja<A extends B, B> = A;
export type ComprobacionesDelContrato = [
  Encaja<Rankings, Esquema["Rankings"]>,
  Encaja<Explicacion, Esquema["Explicacion"]>,
  Encaja<Reproduccion, Esquema["Reproduccion"]>,
  Encaja<Fiabilidad, Esquema["Fiabilidad"]>,
];

// ---------------------------------------------------------------------------
// Simulaciones guardadas (Fase 7)
// ---------------------------------------------------------------------------

export type SimulacionResumen = Esquema["SimulacionResumen"];
export type Simulaciones = Esquema["Simulaciones"];

export interface ValorExacto {
  valor: number | null;
  exacto: string | null;
}
export interface EstadisticaSimulada {
  nombre: string;
  descripcion: string;
  observado: ValorExacto | null;
  referencia_analitica: ValorExacto | null;
  percentil_observado: ValorExacto | null;
  p_valor_empirico: ValorExacto | null;
  p_valor_ajustado_bonferroni: ValorExacto | null;
  supera_umbral_exploratorio: boolean | null;
}
export interface ContenidoDeSimulacion {
  juego: string;
  iteraciones: number;
  estadisticas: EstadisticaSimulada[];
  familia: Record<string, Json>;
  alguna_supera_umbral_exploratorio: boolean | null;
  nota: string;
  /** Contenido completo tal como llega, para mostrarlo sin perder campos. */
  completo: Record<string, Json>;
}
export interface Simulacion {
  id: string;
  juego: string;
  num_iteraciones: number;
  ejecutado_en: string | null;
  duracion_ms: number | null;
  integridad: string;
  estado_de_uso: string;
  parametros: Record<string, Json>;
  contenido: ContenidoDeSimulacion;
  contenido_sha256: string;
}

export const decSimulaciones = objeto<Simulaciones>({
  juego: texto,
  limite: entero,
  estado_de_uso: texto,
  simulaciones: lista(
    objeto<SimulacionResumen>({
      id: texto,
      juego: nulable(texto),
      clave: nulable(texto),
      corte: nulable(entero),
      iteraciones: nulable(entero),
      semilla: nulable(entero),
      ejecutado_en: nulable(texto),
      duracion_ms: nulable(entero),
      integridad: texto,
      motivo: nulable(texto),
      alguna_supera_umbral_exploratorio: nulable(booleano),
    }),
  ),
});

/** `{valor, exacto}` o `{valor, exacta}`: la referencia analitica usa el femenino. */
const valorExacto: Decodificador<ValorExacto> = (v, r) => {
  if (!esObjeto(v)) {
    throw new EstructuraNoReconocida(r, "objeto");
  }
  return {
    valor: nulable(numero)(v.valor, `${r}.valor`),
    exacto: nulable(texto)(v.exacto ?? v.exacta, `${r}.exacto`),
  };
};

const decContenido: Decodificador<ContenidoDeSimulacion> = (v, r) => ({
  ...objeto({
    juego: texto,
    iteraciones: entero,
    estadisticas: lista(
      objeto<EstadisticaSimulada>({
        nombre: texto,
        descripcion: texto,
        observado: nulable(valorExacto),
        referencia_analitica: nulable(valorExacto),
        percentil_observado: nulable(valorExacto),
        p_valor_empirico: nulable(valorExacto),
        p_valor_ajustado_bonferroni: nulable(valorExacto),
        supera_umbral_exploratorio: nulable(booleano),
      }),
    ),
    familia: objetoJson,
    alguna_supera_umbral_exploratorio: nulable(booleano),
    nota: texto,
  })(v, r),
  completo: objetoJson(v, r),
});

export const decSimulacion = objeto<Simulacion>({
  id: texto,
  juego: texto,
  num_iteraciones: entero,
  ejecutado_en: nulable(texto),
  duracion_ms: nulable(entero),
  integridad: texto,
  estado_de_uso: texto,
  parametros: objetoJson,
  contenido: decContenido,
  contenido_sha256: texto,
});

// ---------------------------------------------------------------------------
// Errores y configuracion publica de la pasarela
// ---------------------------------------------------------------------------

export interface DetalleDeError {
  codigo: string;
  mensaje: string;
  solicitud: string | null;
  detalles: Record<string, Json>[] | null;
}
export const decError = objeto<{ error: DetalleDeError }>({
  error: objeto<DetalleDeError>({
    codigo: texto,
    mensaje: texto,
    solicitud: nulable(texto),
    detalles: nulable(lista(objetoJson)),
  }),
});

export interface ConfiguracionDeLaPasarela {
  consola_local: string | null;
  api: string;
}
export const decConfiguracion = objeto<ConfiguracionDeLaPasarela>({ consola_local: nulable(texto), api: texto });
