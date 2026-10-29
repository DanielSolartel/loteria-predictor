/** Lecturas de Fase 9.4: cada pantalla hace una consulta, sin precarga de fichas. */
import { type FormEvent, type ReactNode, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { consultar, rutaApi } from "../api/cliente";
import { EstructuraNoReconocida, type Decodificador } from "../api/decodificar";
import { fechaHora, formatear } from "../api/formatos";
import {
  type CarteraGuardada, type EmisionGuardada, type ModeloGuardado,
  type ResultadoGuardado, type ResumenResultadoGuardado,
  decCarterasGuardadas, decFichaCarteraGuardada, decFichaModeloGuardado,
  decModelosGuardados, decResultadosGuardados, delContexto,
} from "../api/guardados";
import { ArbolDeDatos, AvisoExperimental, Huella, Numeros, ParColor, TablaDesplazable } from "../componentes/comunes";
import { Consulta } from "../componentes/Estados";
import { useFiltros } from "../componentes/Filtros";
import { PestanasDeJuego } from "../componentes/Marco";
import { useConsulta } from "../usos/consulta";
import { Paginacion } from "./Sorteos";
import "./guardados.css";

const NOTA = "Consulta de artefactos guardados. No entrena, genera, simula, repara ni modifica la operación automática.";
const FILTROS_MODELOS = ["modelo", "perfil", "pagina", "por_pagina"] as const;
const FILTROS_CARTERAS = ["linea", "desde", "hasta", "pagina", "por_pagina"] as const;
const FILTROS_RESULTADOS = ["procedencia", "linea", "tipo", "desde", "hasta", "objetivo", "pagina", "por_pagina"] as const;
const claveConsultable = (clave: string) => /^[a-f0-9]{64}$/.test(clave);
type Campo = { nombre: string; etiqueta: string; tipo?: "number"; opciones?: { valor: string; titulo: string }[] };

/** El borrador se reinicia al navegar por URL (incluidos atrás y adelante). */
function Formulario({ valores, campos, aplicar, nombre }: {
  valores: Record<string, string | null>; campos: Campo[];
  aplicar: (v: Record<string, string | null>) => void; nombre: string;
}) {
  const [borrador, setBorrador] = useState(valores);
  const enviar = (e: FormEvent) => {
    e.preventDefault();
    aplicar({ ...borrador, pagina: null });
  };
  return <form className="row g-2 align-items-end mb-3" onSubmit={enviar} aria-label={nombre}>
    {campos.map((c) => <div className="col-12 col-sm-6 col-lg-3" key={c.nombre}>
      <label className="form-label small mb-0" htmlFor={`guardados-${c.nombre}`}>{c.etiqueta}</label>
      {c.opciones ? <select id={`guardados-${c.nombre}`} className="form-select form-select-sm"
        value={borrador[c.nombre] ?? ""} onChange={(e) => setBorrador((b) => ({ ...b, [c.nombre]: e.target.value }))}>
        {c.opciones.map((o) => <option value={o.valor} key={o.valor}>{o.titulo}</option>)}
      </select> : <input id={`guardados-${c.nombre}`} className="form-control form-control-sm"
        type={c.tipo ?? "text"} min={c.tipo === "number" ? 1 : undefined}
        maxLength={c.tipo ? undefined : 160} value={borrador[c.nombre] ?? ""}
        onChange={(e) => setBorrador((b) => ({ ...b, [c.nombre]: e.target.value }))} />}
    </div>)}
    <div className="col-12 d-flex gap-2">
      <button className="btn btn-sm btn-marca" type="submit">Aplicar filtros</button>
      <button className="btn btn-sm btn-outline-secondary" type="button" onClick={() => aplicar(Object.fromEntries(Object.keys(valores).map((k) => [k, null])))}>Quitar filtros</button>
    </div>
  </form>;
}

const POR_PAGINA: Campo = { nombre: "por_pagina", etiqueta: "Por página", opciones: [
  { valor: "", titulo: "20 (predeterminado)" }, ...[5, 10, 50].map((n) => ({ valor: String(n), titulo: String(n) })),
] };
function usePagina() {
  const [parametros] = useSearchParams();
  return (p: number) => {
    const q = new URLSearchParams(parametros); q.set("pagina", String(p)); return `?${q}`;
  };
}
function Estado({ valor, motivo }: { valor: string; motivo?: string | null }) {
  return <><span className={`badge ${valor === "disponible" ? "text-bg-success" : "text-bg-warning"}`} data-integridad={valor}>{valor}</span>
    {motivo ? <div className="small text-break">{motivo}</div> : null}</>;
}
function Vacio({ children }: { children: ReactNode }) {
  return <div className="alert alert-info" data-estado="vacio">{children}</div>;
}
function Cabecera({ codigo, titulo }: { codigo: string; titulo: string }) {
  return <><PestanasDeJuego codigo={codigo} /><h1 className="h3">{titulo}</h1></>;
}
function Combinacion({ resultado }: { resultado: ResultadoGuardado }) {
  return resultado.pares?.length ? <span className="d-inline-flex flex-wrap">{resultado.pares.map((p, i) =>
    <ParColor numero={p.numero} color={p.color} key={i} />)}</span> :
    <Numeros numeros={resultado.numeros ?? []} superbalota={resultado.superbalota} />;
}
function metadatos(c: ModeloGuardado | CarteraGuardada) {
  return <>{c.nombre ?? c.modelo ?? "No acreditado"}<div className="small text-break"><code>{c.modelo ?? "—"}</code> · receta {c.version_receta ?? "—"} · perfil {c.perfil ?? "—"}</div></>;
}
/** Verifica los filtros devueltos antes de atribuir el listado a la URL. */
function filtrosCoincidentes<T>(dec: Decodificador<T>, esperados: Record<string, string | null>, leer: (v: T) => Record<string, unknown>, numericos: string[] = []): Decodificador<T> {
  return (valor, ruta) => {
    const datos = dec(valor, ruta); const recibidos = leer(datos);
    for (const [k, texto] of Object.entries(esperados)) {
      const esperado = texto === null || texto === "" ? null : numericos.includes(k) ? Number(texto) : texto;
      if (recibidos[k] !== esperado) throw new EstructuraNoReconocida(`${ruta}.filtros.${k}`, "los filtros solicitados");
    }
    return datos;
  };
}

export function ModelosGuardados() {
  const { codigo = "" } = useParams();
  const [f, cambiar] = useFiltros(FILTROS_MODELOS); const [q] = useSearchParams(); const enlace = usePagina();
  const url = rutaApi(["juegos", codigo, "modelos-guardados"], f);
  const dec = filtrosCoincidentes(delContexto(decModelosGuardados, codigo), { modelo: f.modelo, perfil: f.perfil }, (d) => ({ modelo: d.modelo, perfil: d.perfil }));
  const [estado, reintentar] = useConsulta(url, (s) => consultar(url, dec, s));
  return <section data-consulta="modelos"><Cabecera codigo={codigo} titulo="Modelos registrados" />
    <p>Versiones que existen en el registro, distintas del catálogo de candidatos del laboratorio. Consultar sus metadatos no carga ni ejecuta el estimador.</p>
    <Formulario key={q.toString()} valores={f} aplicar={cambiar} nombre="Filtros de modelos" campos={[
      { nombre: "modelo", etiqueta: "Identificador de modelo" }, { nombre: "perfil", etiqueta: "Perfil" }, POR_PAGINA,
    ]} />
    <Consulta estado={estado} reintentar={reintentar} que="los modelos registrados">{(d) => <>
      <AvisoExperimental estadoDeUso={d.estado_de_uso}>{NOTA}</AvisoExperimental><p className="small">{d.nota}</p>
      {!d.elementos.length ? <Vacio>No hay versiones registradas que cumplan estos filtros.</Vacio> : <>
        <p className="small" aria-live="polite">{d.total} versiones · página {d.pagina} de {d.paginas}</p>
        <TablaDesplazable etiqueta="Versiones de modelos registrados"><table className="table table-sm"><thead><tr>
          <th scope="col">Modelo y receta</th><th scope="col">Familia</th><th scope="col">Versión registrada</th><th scope="col">Entrenamiento</th><th scope="col">Estado</th><th scope="col">Ficha</th>
        </tr></thead><tbody>{d.elementos.map((m, i) => <tr key={m.clave || `ilegible-${i}`} data-clave={m.clave} data-integridad={m.estado}>
          <td>{metadatos(m)}</td><td>{m.familia ?? "—"}</td><td>{m.numero ?? "—"}<div><Huella valor={m.clave} /></div></td>
          <td>corte {m.corte ?? "—"} · {m.sorteos ?? "—"} sorteos<div className="small">{fechaHora(m.entrenado_en)}</div></td>
          <td><Estado valor={m.estado} motivo={m.motivo} /></td><td>{claveConsultable(m.clave) ? <Link to={`/juegos/${codigo}/modelos/${m.clave}`}>{m.numero === null ? "Ver estado del modelo" : `Ver modelo v${m.numero}`}</Link> : "Ficha no disponible: identidad no acreditada"}</td>
        </tr>)}</tbody></table></TablaDesplazable><Paginacion pagina={d.pagina} paginas={d.paginas} enlace={enlace} />
      </>}
    </>}</Consulta>
  </section>;
}

export function DetalleModeloGuardado() {
  const { codigo = "", identificador = "" } = useParams();
  const url = rutaApi(["juegos", codigo, "modelos-guardados", identificador]);
  const dec = delContexto(decFichaModeloGuardado, codigo, { clave: identificador, leer: (d) => d.modelo });
  const [estado, reintentar] = useConsulta(url, (s) => consultar(url, dec, s));
  return <section><Cabecera codigo={codigo} titulo="Modelo registrado" />
    <Consulta estado={estado} reintentar={reintentar} que="el modelo registrado">{(d) => <div data-modelo={d.modelo.clave}>
      <AvisoExperimental estadoDeUso={d.estado_de_uso}>{NOTA}</AvisoExperimental>
      <div className="card stat-card p-3 mb-3"><h2 className="h5">{d.modelo.nombre ?? d.modelo.modelo} · versión registrada {d.modelo.numero ?? "—"}</h2>
        <Estado valor={d.modelo.estado} motivo={d.modelo.motivo} /><dl className="row small mt-2 mb-0">
          <dt className="col-sm-4">Identidad registrada</dt><dd className="col-sm-8"><Huella valor={d.modelo.clave} /></dd>
          <dt className="col-sm-4">Familia, receta y perfil</dt><dd className="col-sm-8">{d.modelo.familia ?? "—"} · {d.modelo.modelo} v{d.modelo.version_receta} · {d.modelo.perfil}</dd>
          <dt className="col-sm-4">Línea histórica</dt><dd className="col-sm-8"><Huella valor={d.modelo.linea ?? null} /></dd>
          <dt className="col-sm-4">Corte de entrenamiento</dt><dd className="col-sm-8" data-corte="entrenamiento">{d.modelo.corte ?? "—"}; {d.periodo.sorteos} sorteos, {d.periodo.primer_sorteo}–{d.periodo.ultimo_sorteo} ({d.periodo.primera_fecha} a {d.periodo.ultima_fecha})</dd>
          <dt className="col-sm-4">Entrenado</dt><dd className="col-sm-8">{fechaHora(d.modelo.entrenado_en)}</dd>
          <dt className="col-sm-4">Huella del histórico de entrenamiento</dt><dd className="col-sm-8"><Huella valor={d.sha256_historico} /></dd>
          <dt className="col-sm-4">Semilla e hilos declarados</dt><dd className="col-sm-8">{d.semilla} · {d.hilos}</dd>
          <dt className="col-sm-4">Objetivo estadístico</dt><dd className="col-sm-8">{d.objetivo_estadistico}</dd>
        </dl></div>
      <h2 className="h5">Evaluación de la receta guardada en esta versión</h2>
      <p className="small">{d.evaluacion.nota}</p><dl className="row small">
        <dt className="col-sm-4">Estado y corte de evaluación</dt><dd className="col-sm-8">{d.evaluacion.estado ?? "—"}; corte {d.evaluacion.corte ?? "—"}; {d.evaluacion.objetivos ?? "—"} objetivos</dd>
        <dt className="col-sm-4">Log Loss de receta / uniforme</dt><dd className="col-sm-8">{formatear(d.evaluacion.log_loss, "dec3")} / {formatear(d.evaluacion.log_loss_uniforme, "dec3")}</dd>
        <dt className="col-sm-4">Veredicto registrado</dt><dd className="col-sm-8 text-break">{d.evaluacion.veredicto ?? "—"}{d.evaluacion.muestra_pequena ? " · muestra pequeña" : ""}</dd>
        <dt className="col-sm-4">Informe de procedencia</dt><dd className="col-sm-8"><Huella valor={d.experimento} /></dd>
      </dl>
      <details className="mb-3"><summary>Variables y contrato de inferencia guardados</summary><p>{d.variables.join(", ")}</p><p>{d.contrato_de_inferencia}</p></details>
      <p className="small">{d.nota}</p>
    </div>}</Consulta><p><Link to={`/juegos/${codigo}/modelos`}>Volver a los modelos registrados</Link></p>
  </section>;
}

export function CarterasGuardadas() {
  const { codigo = "" } = useParams(); const [f, cambiar] = useFiltros(FILTROS_CARTERAS);
  const [q] = useSearchParams(); const enlace = usePagina();
  const url = rutaApi(["juegos", codigo, "carteras-guardadas"], f);
  const dec = filtrosCoincidentes(delContexto(decCarterasGuardadas, codigo), { linea: f.linea, desde: f.desde, hasta: f.hasta }, (d) => ({ linea: d.linea, desde: d.desde, hasta: d.hasta }), ["desde", "hasta"]);
  const [estado, reintentar] = useConsulta(url, (s) => consultar(url, dec, s));
  return <section data-consulta="carteras"><Cabecera codigo={codigo} titulo="Carteras guardadas" />
    <p>Carteras de combinaciones de Producto 5; esta consulta es distinta de la pantalla de predicción guardada.</p>
    <Formulario key={q.toString()} valores={f} aplicar={cambiar} nombre="Filtros de carteras" campos={[
      { nombre: "linea", etiqueta: "Línea de cartera" }, { nombre: "desde", etiqueta: "Objetivo desde", tipo: "number" }, { nombre: "hasta", etiqueta: "Objetivo hasta", tipo: "number" }, POR_PAGINA,
    ]} />
    <Consulta estado={estado} reintentar={reintentar} que="las carteras guardadas">{(d) => <>
      <AvisoExperimental estadoDeUso={d.estado_de_uso}>{NOTA}</AvisoExperimental><p className="small">{d.nota}</p>
      {d.incidencias_sin_objetivo > 0 ? <p className="alert alert-warning small">{d.incidencias_sin_objetivo} artefactos ilegibles sin objetivo acreditado; no se les atribuye un objetivo.</p> : null}
      {!d.elementos.length ? <Vacio>No hay carteras guardadas que cumplan estos filtros.</Vacio> : <>
        <p className="small" aria-live="polite">{d.total} carteras · página {d.pagina} de {d.paginas}</p>
        <TablaDesplazable etiqueta="Carteras de Producto 5"><table className="table table-sm"><thead><tr>
          <th scope="col">Objetivo / corte de entrada</th><th scope="col">Modelo y receta</th><th scope="col">Línea y versión de cartera</th><th scope="col">Combinaciones</th><th scope="col">Estado</th><th scope="col">Ficha</th>
        </tr></thead><tbody>{d.elementos.map((c, i) => <tr key={c.clave || `ilegible-${i}`} data-clave={c.clave} data-integridad={c.estado}>
          <td>{c.objetivo ?? "—"} / {c.corte ?? "—"}</td><td>{metadatos(c)}{c.registrado ? <div className="small">modelo registrado v{c.registrado.numero}</div> : null}</td>
          <td><Huella valor={c.linea ?? null} /><div className="small">versión {c.version ?? "—"} de {c.versiones ?? "—"}</div></td>
          <td>{c.cantidad ?? "—"}</td><td><Estado valor={c.estado} motivo={c.motivo} /></td>
          <td>{claveConsultable(c.clave) ? <Link to={`/juegos/${codigo}/carteras/${c.clave}`}>{c.objetivo === null ? "Ver estado de la cartera" : `Ver cartera del objetivo ${c.objetivo}`}</Link> : "Ficha no disponible: identidad no acreditada"}</td>
        </tr>)}</tbody></table></TablaDesplazable><Paginacion pagina={d.pagina} paginas={d.paginas} enlace={enlace} />
      </>}
    </>}</Consulta>
  </section>;
}

export function DetalleCarteraGuardada() {
  const { codigo = "", identificador = "" } = useParams();
  const url = rutaApi(["juegos", codigo, "carteras-guardadas", identificador]);
  const dec = delContexto(decFichaCarteraGuardada, codigo, { clave: identificador, leer: (d) => d.cartera });
  const [estado, reintentar] = useConsulta(url, (s) => consultar(url, dec, s));
  return <section><Cabecera codigo={codigo} titulo="Cartera guardada" />
    <Consulta estado={estado} reintentar={reintentar} que="la cartera guardada">{(d) => <div data-cartera={d.cartera.clave}>
      <AvisoExperimental estadoDeUso={d.estado_de_uso}>{NOTA}</AvisoExperimental>
      <div className="card stat-card p-3 mb-3"><h2 className="h5">{d.cartera.nombre ?? d.cartera.modelo} · objetivo {d.cartera.objetivo ?? "—"}</h2>
        <dl className="row small mb-0">
          <dt className="col-sm-4">Identidad de la cartera</dt><dd className="col-sm-8"><Huella valor={d.cartera.clave} /></dd>
          <dt className="col-sm-4">Modelo, receta y perfil</dt><dd className="col-sm-8">{metadatos(d.cartera)}</dd>
          <dt className="col-sm-4">Línea / versión de cartera</dt><dd className="col-sm-8"><Huella valor={d.cartera.linea ?? null} /> · {d.cartera.version ?? "—"} de {d.cartera.versiones ?? "—"}</dd>
          <dt className="col-sm-4">Corte de entrada</dt><dd className="col-sm-8" data-corte="entrada">{d.cartera.corte ?? "—"}</dd>
          <dt className="col-sm-4">Objetivo</dt><dd className="col-sm-8" data-corte="objetivo">{d.cartera.objetivo ?? "—"}</dd>
          <dt className="col-sm-4">Generada</dt><dd className="col-sm-8">{fechaHora(d.cartera.generado_en)}</dd>
          <dt className="col-sm-4">Clasificación temporal</dt><dd className="col-sm-8">{d.clasificacion_temporal ?? "No acreditada"}</dd>
          <dt className="col-sm-4">Huella del histórico de entrada</dt><dd className="col-sm-8"><Huella valor={d.sha256_historico} /></dd>
          {d.cartera.registrado ? <><dt className="col-sm-4">Modelo registrado de esta cartera</dt><dd className="col-sm-8"><Link to={`/juegos/${codigo}/modelos/${d.cartera.registrado.clave}`}>Ver modelo v{d.cartera.registrado.numero}</Link></dd></> : null}
        </dl></div>
      <p className="small">{d.nota_temporal}</p>
      <TablaDesplazable etiqueta="Combinaciones de la cartera"><table className="table table-sm"><thead><tr><th scope="col">Línea</th><th scope="col">Combinación</th><th scope="col">Método</th></tr></thead>
        <tbody>{d.combinaciones.map((c) => <tr key={c.linea}><td>{c.linea}</td><td><Combinacion resultado={c} /></td><td>{c.origen.replaceAll("_", " ")}</td></tr>)}</tbody>
      </table></TablaDesplazable>
      {codigo === "COLORLOTO" ? <p className="small">Cada combinación contiene pares número-color; pueden repetirse números y pares. El color también se indica por su nombre.</p> : null}
      <h2 className="h5 mt-3">Parámetros de reproducción guardados</h2><ArbolDeDatos datos={d.parametros} />
      <p className="small mt-2">Se muestran los parámetros conservados; abrir esta ficha no ejecuta una reproducción ni una nueva inferencia. {d.nota}</p>
    </div>}</Consulta><p><Link to={`/juegos/${codigo}/carteras`}>Volver a las carteras guardadas</Link></p>
  </section>;
}

const ESTADOS: Record<EmisionGuardada["estado"], string> = { incluido: "Incluido", pendiente: "Pendiente de resultado", excluido: "Excluido", sin_base: "Sin base para comprobar" };
function Resumen({ d }: { d: ResumenResultadoGuardado }) {
  return <><p className="mb-1">{d.incluidos} incluidos · {d.pendientes} pendientes · {d.excluidos} excluidos · {d.sin_base} sin base</p>
    {d.muestra_pequena ? <p className="small mb-1">Muestra pequeña.</p> : null}
    {d.aciertos ? <p className="small mb-1">Aciertos observados: {formatear(d.aciertos.promedio, "dec3")} de {d.aciertos.de} en {d.aciertos.objetivos} objetivos.</p> : <p className="small mb-1">Sin aciertos agregados disponibles.</p>}
    {d.perdidas ? <TablaDesplazable etiqueta="Pérdidas frente a la uniforme"><table className="table table-sm small"><thead><tr><th scope="col">Métrica</th><th scope="col">Modelo</th><th scope="col">Uniforme</th><th scope="col">Diferencia</th><th scope="col">Veredicto</th></tr></thead><tbody>
      {Object.entries(d.perdidas).map(([n, p]) => <tr key={n}><th scope="row">{n}</th><td>{formatear(p.modelo, "dec3")}</td><td>{formatear(p.uniforme, "dec3")}</td><td>{formatear(p.diferencia, "dec3")}</td><td>{p.veredicto}</td></tr>)}
    </tbody></table></TablaDesplazable> : null}
    {Object.keys(d.excluidos_por_motivo).length ? <details className="small mt-1"><summary>Exclusiones por motivo</summary><ArbolDeDatos datos={d.excluidos_por_motivo} /></details> : null}
    {d.superbalota ? <p className="small mt-1">Superbalota aparte: {d.superbalota.aciertos} aciertos en {d.superbalota.objetivos} objetivos.</p> : null}
  </>;
}

export function ResultadosGuardados() {
  const { codigo = "" } = useParams(); const [f, cambiar] = useFiltros(FILTROS_RESULTADOS);
  const [q] = useSearchParams(); const enlace = usePagina();
  const url = rutaApi(["juegos", codigo, "resultados"], f);
  const dec = filtrosCoincidentes(delContexto(decResultadosGuardados, codigo), {
    procedencia: f.procedencia, linea: f.linea, tipo: f.tipo ?? "seguimiento", desde: f.desde, hasta: f.hasta, objetivo: f.objetivo,
  }, (d) => d.filtros, ["desde", "hasta", "objetivo"]);
  const [estado, reintentar] = useConsulta(url, (s) => consultar(url, dec, s));
  return <section className="resultados-guardados" data-consulta="resultados"><Cabecera codigo={codigo} titulo="Resultados observados" />
    <p>Emisiones congeladas y resultados observados de Producto 6. Seguimiento y retrospectiva se consultan por separado.</p>
    <Formulario key={q.toString()} valores={f} aplicar={cambiar} nombre="Filtros de resultados" campos={[
      { nombre: "procedencia", etiqueta: "Procedencia", opciones: [
        { valor: "", titulo: "Todas" }, { valor: "operacion", titulo: "Operación diaria" },
        { valor: "laboratorio", titulo: "Laboratorio" }, { valor: "carteras", titulo: "Carteras" },
      ] }, { nombre: "linea", etiqueta: "Identidad completa de línea" },
      { nombre: "tipo", etiqueta: "Tipo temporal", opciones: [{ valor: "", titulo: "Seguimiento (predeterminado)" }, { valor: "seguimiento", titulo: "Seguimiento" }, { valor: "retrospectiva", titulo: "Retrospectiva" }] },
      { nombre: "desde", etiqueta: "Objetivo desde", tipo: "number" }, { nombre: "hasta", etiqueta: "Objetivo hasta", tipo: "number" },
      { nombre: "objetivo", etiqueta: "Objetivo exacto (prioritario)", tipo: "number" }, POR_PAGINA,
    ]} />
    <p className="small">Los filtros se aplican a objetivos; no prueban cuándo estaba disponible una emisión. El objetivo exacto tiene prioridad sobre el intervalo. Sin línea explícita, el lector elige una por procedencia y muestra la selección.</p>
    <Consulta estado={estado} reintentar={reintentar} que="los resultados observados">{(d) => <>
      <AvisoExperimental estadoDeUso={d.estado_de_uso}>{NOTA}</AvisoExperimental>
      <p className="small">{d.politica} {d.nota_seguimiento}</p>
      <details className="small mb-3"><summary>Unidades y denominadores de las métricas</summary><ArbolDeDatos datos={d.unidades} /></details>
      <p className={`alert ${d.base.estado === "consultada" ? "alert-info" : "alert-warning"} small`} data-base={d.base.estado}>
        {d.base.estado === "consultada" ? <>Último resultado cargado: {d.base.ultimo_sorteo ?? "ninguno"} {d.base.fecha ?? ""}; {d.base.sorteos ?? "—"} sorteos.</> : "La base no está disponible. Las emisiones no se consideran cero aciertos ni pendientes confirmados."}
      </p>
      {d.sin_resultados_de_seguimiento ? <p className="alert alert-info small">No hay resultados incluidos de seguimiento para estos filtros; no se cambia automáticamente a retrospectiva.</p> : null}
      <h2 className="h5">Procedencias y selección</h2>
      <TablaDesplazable etiqueta="Procedencias de resultados"><table className="table table-sm small"><thead><tr><th scope="col">Procedencia</th><th scope="col">Estado</th><th scope="col">Líneas</th><th scope="col">Emisiones</th><th scope="col">Ilegibles</th></tr></thead><tbody>
        {Object.entries(d.procedencias).map(([k, p]) => <tr key={k}><th scope="row">{p.nombre}</th><td>{p.estado}{p.error ? ` · ${p.error}` : ""}</td><td>{p.lineas}</td><td>{p.emisiones}</td><td>{p.ilegibles}</td></tr>)}
      </tbody></table></TablaDesplazable>
      {d.seleccion.length ? <div className="my-3">{d.seleccion.map((clave) => {
        const l = d.lineas.find((x) => x.clave === clave); const r = d.resumenes[clave];
        return <article className="card stat-card p-3 mb-2" key={clave} data-linea={clave}><h3 className="h6">{l?.nombre ?? clave}</h3><p className="small text-break"><code>{clave}</code>{l?.perfil ? ` · perfil ${l.perfil}` : ""}</p>
          {l?.registrado ? <p className="small">Versión registrada {l.registrado.numero} · <Huella valor={l.registrado.clave} /></p> : null}
          {r ? <Resumen d={r} /> : <p>Resumen no disponible para esta línea.</p>}
        </article>;
      })}</div> : <Vacio>No hay líneas seleccionables para estas procedencias.</Vacio>}
      <h2 className="h5">Comparación sobre la muestra común</h2>
      <p className="small">{d.comparacion.estado}{d.comparacion.motivo ? `: ${d.comparacion.motivo}` : ""}. {d.comparacion.objetivos_comunes.length} objetivos comunes. {d.signo}</p>
      {d.comparacion.clasificacion.length ? <TablaDesplazable etiqueta="Comparación de líneas"><table className="table table-sm small"><thead><tr><th scope="col">Línea</th><th scope="col">Log Loss</th><th scope="col">Uniforme</th><th scope="col">Diferencia</th><th scope="col">Veredicto</th></tr></thead><tbody>
        {d.comparacion.clasificacion.map((c) => <tr key={c.linea}><th scope="row"><Huella valor={c.linea} /></th><td>{formatear(c.log_loss, "dec3")}</td><td>{formatear(c.uniforme, "dec3")}</td><td>{formatear(c.diferencia, "dec3")}</td><td>{c.veredicto}</td></tr>)}
      </tbody></table></TablaDesplazable> : null}
      {d.comparacion.fuera_de_la_muestra_comun.length ? <details className="small my-2"><summary>Fuera de la muestra común</summary><ArbolDeDatos datos={d.comparacion.fuera_de_la_muestra_comun} /></details> : null}
      <h2 className="h5 mt-3">Emisiones y resultados</h2>
      <p className="small" aria-live="polite">{d.historial.total} emisiones · página {d.historial.pagina} de {d.historial.paginas}. Los pendientes conservan aciertos y pérdidas no disponibles; no se sustituyen por ceros.</p>
      {!d.historial.filas.length ? <Vacio>No hay emisiones para estos filtros.</Vacio> : <TablaDesplazable etiqueta="Emisiones y resultados"><table className="table table-sm small"><thead><tr>
        <th scope="col">Objetivo y línea</th><th scope="col">Tipo temporal</th><th scope="col">Estado</th><th scope="col">Integridad / histórico</th><th scope="col">Resultado observado</th><th scope="col">Aciertos</th><th scope="col">Log Loss / uniforme</th><th scope="col">Superbalota</th>
      </tr></thead><tbody>{d.historial.filas.map((e) => <tr key={`${e.procedencia}-${e.clave_linea}-${e.objetivo}`} data-estado={e.estado} data-tipo={e.tipo}>
        <th scope="row">{e.objetivo}<div><Huella valor={e.clave_linea} /></div><div className="small">{e.procedencia}</div></th>
        <td>{e.tipo ?? "No acreditado"}</td><td>{ESTADOS[e.estado]}{e.motivo ? <div className="small">{e.motivo}</div> : null}</td>
        <td>{e.integridad} / {e.historico ?? "—"}</td><td data-resultado={e.resultado_estado ?? "ausente"}>{e.resultado ? <Combinacion resultado={e.resultado} /> : "—"}<div>{e.fecha_sorteo ?? "—"}</div></td>
        <td data-aciertos={e.aciertos ?? "ausente"}>{e.aciertos === null ? "—" : `${e.aciertos} de ${e.de ?? "—"}${codigo === "COLORLOTO" ? " pares" : ""}`}</td>
        <td>{formatear(e.metricas?.log_loss ?? null, "dec3")} / {formatear(e.metricas?.log_loss_uniforme ?? null, "dec3")}</td>
        <td>{e.superbalota ? `${e.superbalota.acierto ? "Acierto" : "Sin acierto"} · ${formatear(e.superbalota.log_loss, "dec3")}` : "—"}</td>
      </tr>)}</tbody></table></TablaDesplazable>}
      <Paginacion pagina={d.historial.pagina} paginas={d.historial.paginas} enlace={enlace} /><p className="small mt-2">{d.nota}</p>
    </>}</Consulta>
  </section>;
}
