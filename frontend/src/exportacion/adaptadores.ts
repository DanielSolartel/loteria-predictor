/** Tablas de las proyecciones ya decodificadas. No consulta ni calcula estadísticas. */
import type { Json } from "../api/decodificar";
import type { Cabecera, Fiabilidad, Metrica, Panel, Predicciones, Resumen, Resultado, Simulacion, Simulaciones, Sorteo } from "../api/presentacion";
import type { CarteraGuardada, FichaCarteraGuardada, ModeloGuardado, ResultadosGuardados } from "../api/guardados";
import type { CeldaExportacion, TablaExportacion } from "./formatos";

const tabla = (id: string, titulo: string, columnas: string[], filas: (CeldaExportacion | undefined)[][]): TablaExportacion => ({ id, titulo, columnas, filas: filas.map((fila) => fila.map((v) => v === undefined ? "campo ausente" : v)) });
const nombreColor = (color: string) => color;
const camposDeIdentidad = (campos: Record<string, CeldaExportacion | undefined>): Record<string, CeldaExportacion> => {
  const identidad: Record<string, CeldaExportacion> = {};
  for (const [clave, valor] of Object.entries(campos)) if (valor !== undefined) identidad[clave] = valor;
  return identidad;
};

/** Identidad escalar recibida, compartida por JSON, CSV e impresión; no deriva una receta. */
export function identidadMuestra(m: Cabecera): Record<string, CeldaExportacion> {
  return { corte: m.corte.hasta_numero_sorteo, contexto: m.corte.descripcion,
    primer_sorteo: m.periodo?.primer_sorteo ?? null, ultimo_sorteo: m.periodo?.ultimo_sorteo ?? null,
    sorteos: m.total_sorteos, corte_observacion: m.ultimo_sorteo_disponible?.numero_sorteo ?? null,
    fecha_observacion: m.ultimo_sorteo_disponible?.fecha ?? null, fecha: m.consultado_el };
}

export function identidadPrediccion(d: Predicciones): Record<string, CeldaExportacion> {
  const p = d.prediccion;
  return { clave_cartera: p?.clave ?? null, corte_entrada: p?.corte ?? null, objetivo: p?.objetivo ?? null,
    linea: p?.linea ?? null, modelo: p?.modelo.id ?? null, version_receta: p?.modelo.version ?? null,
    perfil: p?.linea_de_modelo?.perfil ?? null, clave_registrada: p?.registrado?.clave ?? null,
    version_registrada: p?.registrado?.numero ?? null, estado: p?.integridad ?? null,
    tipo: p?.clasificacion_temporal?.tipo ?? null, fecha: p?.generado_en ?? null,
    corte_observacion: p?.observado?.ultimo_sorteo_actual ?? null,
    fecha_observacion: p?.observado?.fecha ?? null };
}

export function identidadFiabilidad(f: Fiabilidad): Record<string, CeldaExportacion> {
  const estimadores = [...new Set(f.lineas.map((l) => l.estimador))];
  return { contexto: "Fiabilidad general de la configuración actual; cada fila conserva su línea y corte del informe",
    hasta: f.hasta, estado: f.configuracion, clave_registrada: f.registrado?.clave ?? null,
    version_registrada: f.registrado?.numero ?? null, modelo: estimadores.length === 1 ? estimadores[0]! : null,
    corte_observacion: f.base.ultimo_sorteo, fecha_observacion: f.base.fecha, sorteos: f.base.sorteos };
}

export function identidadModelo(m: ModeloGuardado): Record<string, CeldaExportacion> {
  return camposDeIdentidad({ clave: m.clave, modelo: m.modelo, version_receta: m.version_receta,
    version_registrada: m.numero, perfil: m.perfil, corte_entrenamiento: m.corte,
    sorteos: m.sorteos, linea: m.linea, estado: m.estado, fecha: m.entrenado_en });
}

export function identidadCartera(c: CarteraGuardada): Record<string, CeldaExportacion> {
  return camposDeIdentidad({ clave_cartera: c.clave, corte_entrada: c.corte, objetivo: c.objetivo, linea: c.linea,
    modelo: c.modelo, version: c.version, version_receta: c.version_receta, perfil: c.perfil,
    clave_registrada: c.registrado?.clave ?? null, version_registrada: c.registrado?.numero ?? null,
    estado: c.estado, fecha: c.generado_en });
}

export function identidadSimulacion(s: Simulacion): Record<string, CeldaExportacion> {
  const escalar = (clave: string): CeldaExportacion => {
    const v = s.parametros[clave];
    return typeof v === "string" || typeof v === "number" || typeof v === "boolean" ? v : null;
  };
  return { id: s.id, clave: escalar("clave"), corte: escalar("corte"), semilla: escalar("semilla"),
    iteraciones: s.num_iteraciones, version: escalar("version_motor"), estado: s.integridad, fecha: s.ejecutado_en };
}

export function tablaSorteos(sorteos: readonly Sorteo[]): TablaExportacion[] {
  return [tabla("sorteos", "Sorteos cargados: una fila por balota y posición", ["Sorteo", "Fecha", "Día", "Posición de la balota", "Número", "Código del color", "Nombre del color", "Superbalota (aparte)"], sorteos.flatMap((s) =>
    s.pares.length ? s.pares.map((p, i) => [s.numero_sorteo, s.fecha, s.dia_semana, i + 1, p.numero, p.color_codigo, p.color_nombre, s.superbalota]) :
      s.numeros.map((n, i) => [s.numero_sorteo, s.fecha, s.dia_semana, i + 1, n, null, null, s.superbalota])))];
}

export function tablasResumen(r: Resumen): TablaExportacion[] {
  const e = r.estadisticas;
  if (!e) return [tabla("frecuencia_numeros", "Frecuencia de números", ["Valor", "Apariciones", "Frecuencia relativa (fracción o promedio por sorteo)"], [])];
  const ts: TablaExportacion[] = [];
  const frecuencia = (id: string, titulo: string, f: typeof e.frecuencia_numeros) => ts.push(tabla(id, titulo, ["Valor", "Apariciones", "Frecuencia relativa (fracción o promedio por sorteo)"], f.todas.map((v) => [v.valor, v.apariciones, v.frecuencia_relativa])));
  const atraso = (id: string, titulo: string, a: typeof e.atrasos_numeros) => {
    ts.push(tabla(id, titulo, ["Valor", "Sorteos sin salir", "Último sorteo observado"], a.mayores.map((v) => [v.valor, v.atraso, v.ultimo_sorteo])));
    ts.push(tabla(id + "_nunca", titulo + ": nunca observados", ["Valor nunca observado"], a.nunca_observados.map((v) => [v])));
  };
  frecuencia("frecuencia_numeros", "Frecuencia de números", e.frecuencia_numeros);
  atraso("atrasos_numeros", "Mayores atrasos de números", e.atrasos_numeros);
  for (const [id, titulo, f] of [["pares_impares", "Números pares por sorteo", e.pares_impares], ["altos_bajos", "Números altos/bajos por sorteo", e.altos_bajos]] as const) {
    ts.push(tabla(id, titulo, ["Valor", "Sorteos", "Frecuencia relativa (fracción)"], f.map((v) => [v.valor, v.sorteos, v.frecuencia_relativa])));
  }
  if (r.tipo === "colorloto" && r.estadisticas) {
    frecuencia("frecuencia_colores", "Frecuencia de colores", r.estadisticas.frecuencia_colores);
    frecuencia("frecuencia_pares", "Frecuencia de pares número-color", r.estadisticas.frecuencia_pares);
    atraso("atrasos_colores", "Mayores atrasos de colores", r.estadisticas.atrasos_colores);
    ts.push(tabla("maximo_repeticion_color", "Máximo de balotas de un color", ["Máximo", "Sorteos", "Frecuencia relativa (fracción)"], r.estadisticas.maximo_repeticion_color.map((v) => [v.valor, v.sorteos, v.frecuencia_relativa])));
  } else if (r.tipo === "numeros" && r.estadisticas) {
    const n = r.estadisticas;
    ts.push(tabla("decenas", "Decenas sobre números extraídos", ["Decena", "Sorteos", "Apariciones", "Porcentaje de números extraídos", "Denominador: sorteos", "Denominador: números por sorteo", "Denominador: números extraídos"], n.decenas_sobre_numeros_extraidos.filas.map((v) => [v.valor, v.sorteos, v.apariciones, v.porcentaje_de_numeros_extraidos, n.decenas_sobre_numeros_extraidos.denominador.sorteos, n.decenas_sobre_numeros_extraidos.denominador.numeros_por_sorteo, n.decenas_sobre_numeros_extraidos.denominador.numeros_extraidos])));
    if (n.superbalota) { frecuencia("superbalota_frecuencia", "Frecuencia de superbalota", n.superbalota.frecuencia); atraso("superbalota_atrasos", "Atrasos de superbalota", n.superbalota.atrasos); }
  }
  return ts;
}

export function tablaPanel(p: Panel): TablaExportacion[] {
  return [tabla("indicadores", "Indicadores del panel cargado", ["Grupo", "Métrica", "Título", "Estado", "Aplica", "Motivo", "Indicador", "Valor", "Unidad"], p.grupos.flatMap((g) => g.metricas.flatMap((m) =>
    m.indicadores.length ? m.indicadores.map((i) => [g.titulo, m.slug, m.titulo, m.estado, m.aplica, m.motivo, i.etiqueta, i.valor, i.unidad]) : [[g.titulo, m.slug, m.titulo, m.estado, m.aplica, m.motivo, null, null, null]])))];
}

/** Expansión estructural de celdas públicas: cada hoja escalar ocupa su columna.
 * No se serializan objetos opacos; listas/objetos vacíos quedan explícitos. */
function hojas(v: Json | undefined, prefijo: string, salida: Map<string, CeldaExportacion>): void {
  if (v === undefined) { salida.set(prefijo, "campo ausente"); return; }
  if (v === null || typeof v !== "object") { salida.set(prefijo, v); return; }
  if (Array.isArray(v)) {
    if (!v.length) salida.set(prefijo, "lista vacía");
    v.forEach((x, i) => hojas(x, `${prefijo} · elemento ${i + 1}`, salida));
  } else {
    const entradas = Object.entries(v);
    if (!entradas.length) salida.set(prefijo, "objeto vacío");
    entradas.forEach(([k, x]) => hojas(x, `${prefijo} · ${k}`, salida));
  }
}
export function tablasMetrica(m: Metrica): TablaExportacion[] {
  return m.tablas.map((t) => {
    const claves = [...t.columnas.map((c) => c.clave), ...Array.from(new Set(t.filas.flatMap((f) => Object.keys(f)))).filter((k) => !t.columnas.some((c) => c.clave === k)).sort()];
    const filas = t.filas.map((f) => {
      const mapa = new Map<string, CeldaExportacion>();
      claves.forEach((k) => {
        const c = t.columnas.find((v) => v.clave === k);
        hojas(f[k], c ? `${c.etiqueta}${c.unidad ? ` (${c.unidad})` : ""}` : k, mapa);
      });
      return mapa;
    });
    const columnas = Array.from(new Set(filas.flatMap((f) => [...f.keys()])));
    if (!columnas.length) columnas.push(...claves.map((k) => { const c = t.columnas.find((v) => v.clave === k); return c ? `${c.etiqueta}${c.unidad ? ` (${c.unidad})` : ""}` : k; }));
    return tabla(t.id, t.titulo + (t.paginacion ? " — página cargada" : ""), columnas, filas.map((f) => columnas.map((c) => f.has(c) ? f.get(c)! : "campo ausente")));
  });
}

function elementos(r: Resultado): { numero: number; color: string | null; posicion: number }[] {
  return "pares" in r ? r.pares.map(([numero, color], i) => ({ numero, color, posicion: i + 1 })) : r.numeros.map((numero, i) => ({ numero, color: null, posicion: i + 1 }));
}
export function tablasPrediccion(d: Predicciones): TablaExportacion[] {
  const p = d.prediccion;
  const columnas = ["Clave de cartera", "Objetivo", "Corte de entrada", "Línea", "Posición", "Número", "Código de color", "Nombre de color", "Superbalota", "Papel", "Detalle", "Probabilidad del elemento", "Unidad", "Probabilidad de superbalota", "Aciertos observados de la línea"];
  const ts: TablaExportacion[] = [tabla("combinaciones", "Combinaciones guardadas: una fila por balota y posición", columnas, p ? p.combinaciones.flatMap((c) => elementos(c.resultado).map((e, i) => [p.clave, p.objetivo, p.corte, c.linea, e.posicion, e.numero, e.color, e.color === null ? null : nombreColor(e.color), "superbalota" in c.resultado ? c.resultado.superbalota : null, c.papel, c.detalle, c.probabilidades_de_sus_elementos?.[i] ?? null, c.unidad_de_los_elementos, c.probabilidad_de_su_superbalota, p.observado?.estado === "observado" ? p.observado.aciertos?.por_linea.find((x) => x.linea === c.linea)?.aciertos ?? null : null])) : [])];
  ts.push(tabla("historial_predicciones", "Historial cargado de predicciones", ["Clave", "Objetivo", "Corte", "Generado en (UTC)", "Clasificación temporal", "Línea", "Ilegible"], d.historial.map((h) => [h.clave, h.objetivo, h.corte, h.generado_en, h.tipo, h.linea, h.ilegible])));
  if (p?.rankings) {
    const rankings = p.rankings;
    for (const clave of ["numeros", "pares", "colores", "superbalota"] as const) {
      const r = rankings[clave]; if (!r) continue;
      ts.push(tabla(`ranking_${clave}`, `Candidatos: ${clave}`, ["Posición", "Candidato numérico", "Candidato textual / color", "Probabilidad", "Uniforme", "Diferencia", "Razón", "Multiplicidad esperada", "Unidad", "Denominador"], r.todos.map((f) => [f.posicion, typeof f.candidato === "number" ? f.candidato : Array.isArray(f.candidato) ? f.candidato[0] : null, typeof f.candidato === "string" ? f.candidato : Array.isArray(f.candidato) ? f.candidato[1] : null, f.probabilidad, f.uniforme, f.diferencia, f.razon, f.multiplicidad_esperada, r.unidad, r.denominador])));
    }
  }
  if (p?.explicacion?.importancias.valores) ts.push(tabla("importancias", "Importancias guardadas de variables", ["Variable", "Importancia", "Columnas", "Es identidad", "Mínimo", "Máximo", "Media absoluta", "Tipo", "Estado"], p.explicacion.importancias.valores.map((v) => [v.variable, v.valor, v.columnas, v.es_identidad, v.resumen?.minimo ?? null, v.resumen?.maximo ?? null, v.resumen?.media_absoluta ?? null, p.explicacion!.importancias.tipo, p.explicacion!.importancias.estado])));
  return ts;
}

export function tablasFiabilidad(f: Fiabilidad): TablaExportacion[] {
  const metricas: CeldaExportacion[][] = [], muestras: CeldaExportacion[][] = [];
  for (const l of [...f.lineas, { linea: "receta_actual", nombre: "Receta de la configuración actual", papel: "receta", estimador: "", evaluaciones: [f.receta] }]) {
    for (const e of l.evaluaciones) {
      muestras.push([l.linea, l.nombre, l.estimador || null, e.tipo, e.estado, e.motivo, e.corte_del_informe, e.muestra?.sorteos ?? null, e.muestra?.emisiones ?? null, e.muestra?.pendientes ?? null, e.muestra?.sin_base ?? null, e.muestra?.hasta ?? null]);
      for (const [componente, c] of Object.entries(e.componentes)) for (const [metrica, v] of Object.entries(c.metricas ?? {})) metricas.push([l.linea, l.nombre, l.estimador || null, e.tipo, e.estado, e.corte_del_informe, componente, c.estado, metrica, v.estado, v.n, v.media, v.intervalo?.[0] ?? null, v.intervalo?.[1] ?? null, v.nivel, v.motivo, v.etiqueta, v.semilla, v.error_estandar_bootstrap, f.metodo.unidad]);
    }
  }
  return [tabla("fiabilidad_metricas", "Fiabilidad: métricas observadas e intervalos", ["Línea", "Nombre", "Estimador informado", "Tipo de evaluación", "Estado de evaluación", "Corte del informe", "Componente", "Estado del componente", "Métrica", "Estado de métrica", "N", "Media", "Intervalo inferior", "Intervalo superior", "Nivel", "Motivo", "Etiqueta", "Semilla (texto exacto)", "Error estándar bootstrap", "Unidad de observación"], metricas), tabla("fiabilidad_muestras", "Fiabilidad: muestras y estados", ["Línea", "Nombre", "Estimador informado", "Tipo", "Estado", "Motivo", "Corte del informe", "Sorteos", "Emisiones", "Pendientes", "Sin base", "Objetivos hasta"], muestras)];
}

export function tablaModelos(ms: readonly ModeloGuardado[]): TablaExportacion[] {
  return [tabla("modelos", "Metadatos públicos de modelos registrados", ["Clave", "Juego", "Estado", "Motivo", "Modelo", "Nombre", "Familia", "Perfil", "Versión de receta", "Versión registrada", "Corte de entrenamiento", "Sorteos", "Entrenado en", "Línea"], ms.map((m) => [m.clave, m.juego, m.estado, m.motivo, m.modelo, m.nombre, m.familia, m.perfil, m.version_receta, m.numero, m.corte, m.sorteos, m.entrenado_en, m.linea]))];
}
export function tablaCarteras(cs: readonly CarteraGuardada[]): TablaExportacion[] {
  return [tabla("carteras", "Metadatos públicos de carteras guardadas", ["Clave", "Juego", "Estado", "Motivo", "Línea", "Objetivo", "Corte de entrada", "Modelo", "Nombre", "Versión de receta", "Perfil", "Versión de cartera", "Versiones", "Cantidad", "Generado en", "Clave de modelo registrado", "Versión registrada"], cs.map((c) => [c.clave, c.juego, c.estado, c.motivo, c.linea, c.objetivo, c.corte, c.modelo, c.nombre, c.version_receta, c.perfil, c.version, c.versiones, c.cantidad, c.generado_en, c.registrado?.clave ?? null, c.registrado?.numero ?? null]))];
}
export function tablasCartera(d: FichaCarteraGuardada): TablaExportacion[] {
  return [...tablaCarteras([d.cartera]), tabla("combinaciones", "Combinaciones de cartera: una fila por balota y posición", ["Clave de cartera", "Objetivo", "Corte de entrada", "Línea", "Origen", "Posición", "Número", "Código de color", "Nombre de color", "Superbalota"], d.combinaciones.flatMap((c) => {
    const filas = c.pares.length ? c.pares.map((p, i) => [i + 1, p.numero, p.color, nombreColor(p.color)]) : c.numeros.map((n, i) => [i + 1, n, null, null]);
    return filas.map((v) => [d.cartera.clave, d.cartera.objetivo, d.cartera.corte, c.linea, c.origen, ...v, c.superbalota]);
  }))];
}
export function tablasResultados(d: ResultadosGuardados): TablaExportacion[] {
  const filas: CeldaExportacion[][] = d.historial.filas.flatMap((e) => {
    const posiciones = e.resultado?.pares?.length ? e.resultado.pares.map((p, i) => [i + 1, p.numero, p.color, nombreColor(p.color)]) : e.resultado?.numeros?.length ? e.resultado.numeros.map((n, i) => [i + 1, n, null, null]) : [[null, null, null, null]];
    return posiciones.map((p) => [e.objetivo, e.procedencia, e.clave_linea, e.identificador, e.tipo, e.estado, e.motivo, e.integridad, e.historico, e.resultado_estado, e.fecha_sorteo, ...p, e.resultado?.superbalota ?? null, e.aciertos, e.de, e.metricas?.log_loss ?? null, e.metricas?.log_loss_uniforme ?? null, e.metricas?.brier ?? null, e.metricas?.brier_uniforme ?? null, e.superbalota?.acierto ?? null]);
  });
  const agregados: CeldaExportacion[][] = Object.entries(d.resumenes).flatMap(([linea, r]) => {
    const perdidas = Object.entries(r.perdidas ?? {});
    return (perdidas.length ? perdidas : [[null, null]] as const).map(([metrica, p]) => [linea, r.objetivos, r.incluidos, r.pendientes, r.excluidos, r.sin_base, r.aciertos?.promedio ?? null, r.aciertos?.de ?? null, metrica, p?.modelo ?? null, p?.uniforme ?? null, p?.diferencia ?? null, p?.objetivos ?? null, p?.veredicto ?? null]);
  });
  return [tabla("resultados_historial", "Historial cargado: una fila por balota; sin resultado una fila explícita", ["Objetivo", "Procedencia", "Línea", "Identificador", "Tipo temporal", "Estado", "Motivo", "Integridad", "Histórico", "Estado del resultado", "Fecha observada", "Posición", "Número", "Código de color", "Nombre de color", "Superbalota observada", "Aciertos", "De", "Log Loss", "Log Loss uniforme", "Brier", "Brier uniforme", "Acierto de superbalota"], filas), tabla("resultados_agregados", "Agregados sobre todos los objetivos del filtro (no sólo la página)", ["Línea", "Objetivos", "Incluidos", "Pendientes", "Excluidos", "Sin base", "Promedio de aciertos", "De", "Métrica", "Modelo", "Uniforme", "Diferencia", "Objetivos de la métrica", "Veredicto"], agregados), tabla("resultados_comparacion", "Comparación en la muestra común", ["Línea", "Log Loss", "Uniforme", "Diferencia", "Veredicto"], d.comparacion.clasificacion.map((v) => [v.linea, v.log_loss, v.uniforme, v.diferencia, v.veredicto]))];
}
export function tablaSimulaciones(d: Simulaciones): TablaExportacion[] {
  return [tabla("simulaciones", "Simulaciones de la lista cargada", ["Identificador", "Juego", "Clave", "Corte", "Iteraciones", "Semilla", "Ejecutado en", "Integridad", "Motivo", "Alguna supera el umbral exploratorio"], d.simulaciones.map((s) => [s.id, s.juego, s.clave, s.corte, s.iteraciones, s.semilla, s.ejecutado_en, s.integridad, s.motivo, s.alguna_supera_umbral_exploratorio]))];
}
export function tablaSimulacion(s: Simulacion): TablaExportacion[] {
  return [tabla("estadisticas_simuladas", "Estadísticas comparadas de la simulación", ["Estadística", "Descripción", "Observado", "Observado exacto", "Referencia analítica", "Referencia exacta", "Percentil observado", "Percentil exacto", "p-value empírico", "p-value exacto", "p-value Bonferroni", "p-value Bonferroni exacto", "Supera umbral exploratorio"], s.contenido.estadisticas.map((e) => [e.nombre, e.descripcion, e.observado?.valor ?? null, e.observado?.exacto ?? null, e.referencia_analitica?.valor ?? null, e.referencia_analitica?.exacto ?? null, e.percentil_observado?.valor ?? null, e.percentil_observado?.exacto ?? null, e.p_valor_empirico?.valor ?? null, e.p_valor_empirico?.exacto ?? null, e.p_valor_ajustado_bonferroni?.valor ?? null, e.p_valor_ajustado_bonferroni?.exacto ?? null, e.supera_umbral_exploratorio]))];
}
