/** Acciones locales, disponibles exclusivamente junto a una respuesta lista y reconocida. */
import { useId, useState } from "react";
import { useLocation } from "react-router-dom";
import { descargarArchivo, exportarCsv, exportarJson, filtrosPublicos, identidadPublica, type SolicitudExportacion, validarExportacion } from "../exportacion/formatos";

export type PropsExportarConsulta = Omit<SolicitudExportacion, "ruta">;

export function ExportarConsulta(props: PropsExportarConsulta) {
  const { pathname } = useLocation();
  const [elegida, elegir] = useState(props.tablas[0]?.id ?? "");
  const id = useId();
  const solicitud: SolicitudExportacion = { ...props, ruta: pathname };
  try { validarExportacion(solicitud); } catch { return null; }
  // Si el conjunto cambia sin desmontar, jamás se exporta una tabla de la vista anterior.
  const seleccionada = props.tablas.some((t) => t.id === elegida) ? elegida : props.tablas[0]?.id ?? "";
  const filtros = Object.entries(filtrosPublicos(solicitud));
  const identidad = Object.entries(identidadPublica(solicitud));
  return <section className="exportacion-consulta border rounded p-2 my-3" data-testid="exportacion" data-recurso={props.recurso} aria-label="Exportación de la consulta cargada">
    <div className="contexto-exportacion small">
      <p className="mb-1"><strong>{props.pagina ? "Exportar página actual" : "Exportar consulta cargada"}</strong> · {props.juego} · {props.alcance}</p>
      {props.pagina ? <p className="mb-1">Página {props.pagina.pagina}; tamaño {props.pagina.por_pagina}; total {props.pagina.total ?? "no informado"}. Sólo filas cargadas.</p> : null}
      {filtros.length ? <p className="mb-1">Filtros aplicados: {filtros.map(([k, v]) => `${k}: ${v === null || v === "" ? "sin filtro" : String(v)}`).join(" · ")}</p> : null}
      {identidad.length ? <p className="mb-1">Identidad acreditada: {identidad.map(([k, v]) => `${k}: ${v === null ? "no informado" : String(v)}`).join(" · ")}</p> : null}
      <p className="mb-1">Copia local experimental, sin nuevas consultas. No es un artefacto canónico ni acredita ventaja predictiva.</p>
      {(props.notas ?? []).map((n, i) => <p className="mb-1" key={i}>{n}</p>)}
    </div>
    <div className="acciones-exportacion d-flex flex-wrap align-items-center gap-2">
      <button type="button" className="btn btn-sm btn-outline-primary" onClick={() => descargarArchivo(exportarJson(solicitud))}>Exportar JSON</button>
      {props.tablas.length > 1 ? <div className="selector-tabla small"><label htmlFor={id}>Tabla CSV</label><select id={id} className="form-select form-select-sm" value={seleccionada} onChange={(e) => elegir(e.target.value)}>
        {props.tablas.map((t) => <option value={t.id} key={t.id}>{t.titulo}</option>)}
      </select></div> : props.tablas.length === 1 ? <span className="small">CSV: {props.tablas[0]?.titulo}</span> : null}
      {seleccionada ? <button type="button" className="btn btn-sm btn-outline-primary" onClick={() => descargarArchivo(exportarCsv(solicitud, seleccionada))}>Exportar CSV</button> : null}
      <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => window.print()}>Imprimir</button>
    </div>
  </section>;
}
