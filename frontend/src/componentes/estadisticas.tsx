/** Presentacion de la cabecera de muestra, la frescura, los indicadores y las tablas de metrica. */
import type { ReactNode } from "react";
import type { Json } from "../api/decodificar";
import { alineadoADerecha, formatear } from "../api/formatos";
import type { Cabecera, Frescura, Grafica, Indicador, TablaDeMetrica } from "../api/presentacion";
import { TablaDesplazable, textoJson } from "./comunes";

const ESTADOS_DE_FRESCURA: Readonly<Record<string, { etiqueta: string; clase: string }>> = {
  al_dia: { etiqueta: "Al día", clase: "text-bg-success" },
  desactualizado: { etiqueta: "Atrasado", clase: "text-bg-warning" },
  sin_datos: { etiqueta: "Sin datos", clase: "text-bg-secondary" },
};

/** Frescura informada por el backend: estado, dias y mensaje, sin recalcular nada. */
export function VistaFrescura({ frescura }: { frescura: Frescura }) {
  const conocido = ESTADOS_DE_FRESCURA[frescura.estado];
  const dias = frescura.dias_desde_el_ultimo_sorteo;
  return (
    <div
      className={`alert ${frescura.estado === "al_dia" ? "alert-light" : "alert-warning"} py-2 small mb-3`}
      data-frescura={frescura.estado}
    >
      <span className={`badge ${conocido?.clase ?? "text-bg-light"} me-2`}>
        {conocido ? conocido.etiqueta : `Estado ${frescura.estado}`}
        {frescura.estado === "desactualizado" && dias !== null ? `: ${dias} días` : ""}
      </span>
      {frescura.mensaje}
    </div>
  );
}

export function Tarjeta({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <div className="card stat-card p-3 h-100">
      <div className="text-muted small">{titulo}</div>
      {children}
    </div>
  );
}

/** Muestra analizada (resumen, panel y metricas): sorteos, periodo, corte y frescura. */
export function VistaMuestra({ muestra }: { muestra: Cabecera }) {
  const { periodo, ultimo_sorteo_disponible: ultimo, huecos } = muestra;
  return (
    <>
      <div className="row g-3 mb-3">
        <div className="col-6 col-md-3">
          <Tarjeta titulo="Sorteos analizados">
            <div className="fw-bold fs-5">{muestra.total_sorteos}</div>
            <div className="small text-muted">de {muestra.total_sorteos_sin_corte} cargados</div>
          </Tarjeta>
        </div>
        <div className="col-6 col-md-3">
          <Tarjeta titulo="Período">
            {periodo ? (
              <>
                <div className="fw-bold">
                  {periodo.primera_fecha} → {periodo.ultima_fecha}
                </div>
                <div className="small text-muted">
                  sorteos {periodo.primer_sorteo}–{periodo.ultimo_sorteo}
                </div>
              </>
            ) : (
              <div className="fw-bold">—</div>
            )}
          </Tarjeta>
        </div>
        <div className="col-6 col-md-3">
          <Tarjeta titulo="Corte aplicado">
            <div className="fw-bold">{muestra.corte.descripcion}</div>
          </Tarjeta>
        </div>
        <div className="col-6 col-md-3">
          <Tarjeta titulo="Último sorteo cargado">
            <div className="fw-bold">{ultimo ? `#${ultimo.numero_sorteo} · ${ultimo.fecha}` : "—"}</div>
            <div className="small text-muted">consultado el {muestra.consultado_el}</div>
          </Tarjeta>
        </div>
      </div>
      <VistaFrescura frescura={muestra.frescura} />
      {huecos.cantidad > 0 ? (
        <p className="small text-warning-emphasis">
          Hay {huecos.cantidad} número(s) de sorteo sin cargar en el período (p. ej. {huecos.primeros.slice(0, 5).join(", ")}).
        </p>
      ) : null}
    </>
  );
}

export function Indicadores({ indicadores }: { indicadores: readonly Indicador[] }) {
  if (indicadores.length === 0) {
    return null;
  }
  return (
    <div className="row g-3 mb-3">
      {indicadores.map((i) => (
        <div className="col-6 col-md-3" key={i.etiqueta}>
          <Tarjeta titulo={i.etiqueta}>
            <div className="fw-bold text-break">{formatear(i.valor, i.formato)}</div>
            {i.unidad ? <div className="small text-muted">{i.unidad}</div> : null}
          </Tarjeta>
        </div>
      ))}
    </div>
  );
}

function valorDeCelda(valor: Json | undefined, formato: string): string {
  if (valor === undefined || valor === null) {
    return "—";
  }
  if (typeof valor === "number" || typeof valor === "string") {
    return formatear(valor, formato);
  }
  return textoJson(valor);
}

/**
 * Tabla generica de una metrica: las columnas declaradas con su formato y
 * unidad y, si alguna fila trae claves no declaradas, una columna final con
 * esos datos adicionales para no perder contenido.
 */
export function TablaMetrica({ tabla }: { tabla: TablaDeMetrica }) {
  const declaradas = new Set(tabla.columnas.map((c) => c.clave));
  const adicionales = (fila: Record<string, Json>) => Object.entries(fila).filter(([k]) => !declaradas.has(k));
  const hayAdicionales = tabla.filas.some((f) => adicionales(f).length > 0);
  return (
    <div className="card stat-card p-3 mb-3">
      <h3 className="h6">{tabla.titulo}</h3>
      {tabla.filas.length === 0 ? (
        <p className="small text-muted mb-0">Sin filas para esta muestra.</p>
      ) : (
        <TablaDesplazable etiqueta={`Tabla: ${tabla.titulo}`}>
          <table className="table table-sm" id={`tabla-${tabla.id}`} data-tabla={tabla.id}>
            <thead>
              <tr>
                {tabla.columnas.map((c) => (
                  <th scope="col" key={c.clave} className={alineadoADerecha(c.formato) ? "text-end" : undefined}>
                    {c.etiqueta}
                    {c.unidad && c.formato !== "texto" ? (
                      <div className="fw-normal small text-muted">{c.unidad}</div>
                    ) : null}
                  </th>
                ))}
                {hayAdicionales ? <th scope="col">Datos adicionales</th> : null}
              </tr>
            </thead>
            <tbody>
              {tabla.filas.map((fila, i) => (
                <tr key={i}>
                  {tabla.columnas.map((c) => (
                    <td key={c.clave} className={alineadoADerecha(c.formato) ? "text-end" : undefined}>
                      {valorDeCelda(fila[c.clave], c.formato)}
                    </td>
                  ))}
                  {hayAdicionales ? (
                    <td>
                      <dl className="datos-adicionales mb-0">
                        {adicionales(fila).map(([k, v]) => (
                          <div key={k}>
                            <dt className="d-inline">
                              <code>{k}</code>:
                            </dt>{" "}
                            <dd className="d-inline mb-0">{v === null ? "—" : textoJson(v)}</dd>
                          </div>
                        ))}
                      </dl>
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </TablaDesplazable>
      )}
      {tabla.nota ? <p className="small text-muted mb-0 mt-1">{tabla.nota}</p> : null}
    </div>
  );
}

/** La grafica de la consola HTMX no se reproduce en 9.1: se indica su tabla y su referencia. */
export function NotaDeGrafica({ grafica, tabla }: { grafica: Grafica; tabla: string | undefined }) {
  return (
    <p className="small text-muted">
      Gráfica «{grafica.titulo}»{grafica.unidad ? ` (${grafica.unidad})` : ""}: sus valores están en la tabla
      {tabla ? ` «${tabla}»` : ""}
      {grafica.referencia !== null
        ? `; referencia ${formatear(grafica.referencia, "dec2")}${grafica.etiqueta_referencia ? ` (${grafica.etiqueta_referencia})` : ""}`
        : ""}
      . La representación gráfica queda pendiente.
    </p>
  );
}
