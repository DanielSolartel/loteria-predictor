/**
 * Estadisticas: indice de metricas (GET .../estadisticas) y panel (GET .../panel).
 * Solo las metricas que el indice declara tienen pagina (las de la Fase 5 y,
 * desde la 9.2, las anteriores); si alguna no figurase, muestra sus indicadores
 * del panel y queda pendiente. Las que no aplican, su motivo.
 */
import { type FormEvent, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { consultar, rutaApi } from "../api/cliente";
import { formatear } from "../api/formatos";
import { decIndice, decPanel, decRespuestaDeMetrica, type Metrica as MetricaDatos, type Selector } from "../api/presentacion";
import { Consulta } from "../componentes/Estados";
import { ExportarConsulta } from "../componentes/ExportarConsulta";
import { tablaPanel, tablasMetrica, identidadMuestra } from "../exportacion/adaptadores";
import { Indicadores, NotaDeGrafica, TablaMetrica, VistaMuestra } from "../componentes/estadisticas";
import { FormularioDeCorte, useFiltros } from "../componentes/Filtros";
import { PestanasDeJuego } from "../componentes/Marco";
import { useConsulta } from "../usos/consulta";

function conCorte(ruta: string, corte: string | null): string {
  return corte ? `${ruta}?hasta_numero_sorteo=${encodeURIComponent(corte)}` : ruta;
}

export function Estadisticas() {
  const { codigo = "" } = useParams();
  const [{ hasta_numero_sorteo: corte }, cambiar] = useFiltros(["hasta_numero_sorteo"] as const);
  const urlIndice = rutaApi(["juegos", codigo, "estadisticas"]);
  const urlPanel = rutaApi(["juegos", codigo, "estadisticas", "panel"], { hasta_numero_sorteo: corte });
  const [indice, reintentarIndice] = useConsulta(urlIndice, (s) => consultar(urlIndice, decIndice, s));
  const [panel, reintentarPanel] = useConsulta(urlPanel, (s) => consultar(urlPanel, decPanel, s));
  const base = `/juegos/${encodeURIComponent(codigo)}/estadisticas`;
  return (
    <>
      <PestanasDeJuego codigo={codigo} />
      <h1 className="h3">Estadísticas descriptivas</h1>
      <p className="small text-muted">
        Describen sorteos ya ocurridos: no son probabilidades del próximo sorteo ni recomendaciones.
      </p>
      <FormularioDeCorte key={corte ?? ""} valor={corte} aplicar={(v) => cambiar({ hasta_numero_sorteo: v })} />
      <Consulta estado={indice} reintentar={reintentarIndice} que="el índice de métricas">
        {(i) => {
          const conPagina = new Set(i.metricas.map((m) => m.metrica));
          return (
            <Consulta estado={panel} reintentar={reintentarPanel} que="el panel">
              {(p) => (
                <>
                  <ExportarConsulta juego={codigo} recurso="estadisticas" identidad={identidadMuestra(p.muestra)} datos={{ indice: i, panel: p }} tablas={tablaPanel(p)} alcance="Indicadores del panel cargado; no descarga páginas de métricas" filtros={{ hasta_numero_sorteo: p.muestra.corte.hasta_numero_sorteo }} />
                  <VistaMuestra muestra={p.muestra} />
                  <p className="small" data-metricas-con-pagina={i.metricas.length}>
                    {i.metricas.length} métricas con página propia según el índice de la API (
                    {i.metricas.filter((m) => m.origen === "fase5").length} de la Fase 5 y{" "}
                    {i.metricas.filter((m) => m.origen === "anterior").length} anteriores).
                  </p>
                  {p.grupos.map((g) => (
                    <section className="mb-4" key={g.clave} aria-labelledby={`grupo-${g.clave}`}>
                      <h2 className="h5" id={`grupo-${g.clave}`}>
                        {g.titulo}
                      </h2>
                      <div className="row g-3">
                        {g.metricas.map((m) => (
                          <div className="col-12 col-md-6 col-xl-4" key={m.slug}>
                            <div className="card stat-card p-3 h-100" data-metrica={m.slug} data-estado={m.estado}>
                              <h3 className="h6 mb-1">
                                {conPagina.has(m.slug) ? (
                                  <Link to={conCorte(`${base}/${m.slug}`, corte)}>{m.titulo}</Link>
                                ) : (
                                  m.titulo
                                )}
                              </h3>
                              {m.estado === "no_aplica" || !m.aplica ? (
                                <p className="small text-muted mb-0">No aplica: {m.motivo ?? "sin motivo informado"}</p>
                              ) : (
                                <>
                                  {m.estado !== "ok" ? (
                                    <p className="small text-warning-emphasis mb-1">
                                      Estado {m.estado}
                                      {m.motivo ? `: ${m.motivo}` : ""}
                                    </p>
                                  ) : null}
                                  <ul className="list-unstyled small mb-1">
                                    {m.indicadores.map((x) => (
                                      <li key={x.etiqueta}>
                                        <span className="text-muted">{x.etiqueta}:</span> {formatear(x.valor, x.formato)}
                                        {x.unidad ? ` ${x.unidad}` : ""}
                                      </li>
                                    ))}
                                  </ul>
                                  {!conPagina.has(m.slug) ? (
                                    <p className="small text-muted mb-0">Página de detalle pendiente (no está en el índice v1).</p>
                                  ) : null}
                                </>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </section>
                  ))}
                </>
              )}
            </Consulta>
          );
        }}
      </Consulta>
    </>
  );
}

const PARAMETROS = ["hasta_numero_sorteo", "anio", "mes", "dia_semana", "ventana", "color", "pagina"] as const;
type Parametro = (typeof PARAMETROS)[number];
const esParametro = (n: string): n is Parametro => (PARAMETROS as readonly string[]).includes(n);

function FormularioDeMetrica({
  selector,
  corte,
  aplicar,
}: {
  selector: Selector | null;
  corte: string | null;
  aplicar: (corte: string | null, parametro: string | null) => void;
}) {
  const [texto, setTexto] = useState(corte ?? "");
  const [valor, setValor] = useState(selector?.valor ?? "");
  const enviar = (e: FormEvent) => {
    e.preventDefault();
    aplicar(texto.trim() || null, valor || null);
  };
  return (
    <form className="row g-2 align-items-end mb-3" onSubmit={enviar} aria-label="Parámetros de la métrica">
      {selector ? (
        <div className="col-auto">
          <label className="form-label small mb-0" htmlFor="selector">
            {selector.parametro.replace("_", " ")}
          </label>
          <select id="selector" className="form-select form-select-sm" value={valor} onChange={(e) => setValor(e.target.value)}>
            {selector.opciones.map((o) => (
              <option key={o.valor} value={o.valor}>
                {o.etiqueta}
                {o.sorteos !== null ? ` (${o.sorteos} sorteos)` : ""}
              </option>
            ))}
          </select>
        </div>
      ) : null}
      <div className="col-auto">
        <label className="form-label small mb-0" htmlFor="corte-metrica">
          Corte (hasta el sorteo)
        </label>
        <input
          id="corte-metrica"
          className="form-control form-control-sm"
          type="number"
          min={1}
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
        />
      </div>
      <div className="col-auto">
        <button className="btn btn-sm btn-marca" type="submit">
          Aplicar
        </button>
      </div>
    </form>
  );
}

function VistaMetrica({ m, enlace }: { m: MetricaDatos; enlace: (pagina: number) => string }) {
  const tablaDeGrafica = m.grafica ? m.tablas.find((t) => t.id === m.grafica?.tabla) : undefined;
  return (
    <>
      {m.estado !== "ok" ? (
        <div className={`alert ${m.estado === "sin_datos" ? "alert-info" : "alert-warning"}`} data-estado={m.estado}>
          {m.estado === "no_aplica" ? "No aplica: " : m.estado === "sin_datos" ? "Sin datos: " : `Estado ${m.estado}: `}
          {m.motivo ?? "sin motivo informado"}
        </div>
      ) : null}
      <Indicadores indicadores={m.indicadores} />
      {m.grafica ? <NotaDeGrafica grafica={m.grafica} tabla={tablaDeGrafica?.titulo} /> : null}
      {m.tablas.map((t) => (
        <TablaMetrica tabla={t} key={t.id} enlace={enlace} />
      ))}
      {m.notas.length > 0 ? (
        <div className="alert alert-secondary small">
          <ul className="mb-0">
            {m.notas.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </>
  );
}

export function Metrica() {
  const { codigo = "", metrica = "" } = useParams();
  const { pathname, search } = useLocation();
  const [valores, cambiar] = useFiltros(PARAMETROS);
  const enlace = (pagina: number) => {
    const consulta = new URLSearchParams(search);
    consulta.set("pagina", String(pagina));
    return `${pathname}?${consulta.toString()}`;
  };
  const url = rutaApi(["juegos", codigo, "estadisticas", metrica], valores);
  const [estado, reintentar] = useConsulta(url, (s) => consultar(url, decRespuestaDeMetrica, s));
  return (
    <>
      <PestanasDeJuego codigo={codigo} />
      {estado.fase !== "lista" ? <h1 className="h3">Métrica {metrica}</h1> : null}
      <Consulta estado={estado} reintentar={reintentar} que="la métrica">
        {({ metrica: m, muestra }) => (
          <>
            <h1 className="h3">{m.titulo}</h1>
            <p className="small text-muted">
              Grupo {m.grupo}
              {m.origen === "anterior" ? " · página anterior (misma receta que la consola local)" : ""} · estadística descriptiva de sorteos ya ocurridos: no es una probabilidad del próximo sorteo ni una
              recomendación.
            </p>
            <FormularioDeMetrica
              key={url}
              selector={m.selector}
              corte={valores.hasta_numero_sorteo}
              aplicar={(corte, valor) =>
                cambiar({
                  hasta_numero_sorteo: corte,
                  pagina: null,  // otro corte u otro filtro: la tabla vuelve a su primera pagina
                  ...(m.selector && esParametro(m.selector.parametro) ? { [m.selector.parametro]: valor } : {}),
                })
              }
            />
            <ExportarConsulta juego={codigo} recurso="metrica" identidad={{ ...identidadMuestra(muestra), metrica: m.slug }} datos={{ muestra, metrica: m }} tablas={tablasMetrica(m)} alcance={m.tablas.some((t) => t.paginacion) ? "Tablas cargadas: sólo la página actual de las tablas paginadas" : "Tablas y dimensiones cargadas de esta métrica"} filtros={{ ...valores, hasta_numero_sorteo: muestra.corte.hasta_numero_sorteo, ...(m.selector ? { [m.selector.parametro]: m.selector.valor } : {}) }} pagina={(() => { const p = m.tablas.find((t) => t.paginacion)?.paginacion; return p ? { pagina: p.pagina, por_pagina: p.por_pagina, total: p.total_filas } : undefined; })()} />
            <VistaMuestra muestra={muestra} />
            <VistaMetrica m={m} enlace={enlace} />
          </>
        )}
      </Consulta>
      <p className="small mt-3">
        <Link to={conCorte(`/juegos/${encodeURIComponent(codigo)}/estadisticas`, valores.hasta_numero_sorteo)}>
          Volver al panel
        </Link>
      </p>
    </>
  );
}
