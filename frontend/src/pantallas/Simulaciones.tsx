/**
 * Simulaciones guardadas (GET /juegos/{codigo}/simulaciones?limite=) y su
 * detalle verificado (GET /simulaciones/{id}): parametros, integridad, huella y
 * contenido. Una simulacion alterada llega como 409 y no se muestra su contenido.
 */
import { Link, useParams, useLocation } from "react-router-dom";
import { consultar, rutaApi } from "../api/cliente";
import { fechaHora, formatear } from "../api/formatos";
import { decSimulacion, decSimulaciones, type EstadisticaSimulada, type ValorExacto } from "../api/presentacion";
import { ArbolDeDatos, AvisoExperimental, Huella, TablaDesplazable } from "../componentes/comunes";
import { Consulta } from "../componentes/Estados";
import { ExportarConsulta } from "../componentes/ExportarConsulta";
import { tablaSimulaciones, tablaSimulacion, identidadSimulacion } from "../exportacion/adaptadores";
import { useFiltros } from "../componentes/Filtros";
import { PestanasDeJuego } from "../componentes/Marco";
import { useConsulta } from "../usos/consulta";
import { useRutaDeListado, rutaDeRetorno } from "../usos/retorno";

const AVISO =
  "Comparación exploratoria con el mecanismo uniforme del juego: no es confirmatoria, no genera combinaciones ni recomendaciones.";

function Integridad({ valor, motivo }: { valor: string; motivo?: string | null }) {
  const correcta = valor === "verificada";
  return (
    <span className={`badge ${correcta ? "text-bg-success" : "text-bg-danger"}`} data-integridad={valor} title={motivo ?? undefined}>
      {correcta ? "verificada" : valor}
    </span>
  );
}

const LIMITES = ["10", "20", "50"];

export function Simulaciones() {
  const { codigo = "" } = useParams();
  const retorno = useRutaDeListado(`/juegos/${encodeURIComponent(codigo)}/simulaciones`, ["limite"]);
  const [{ limite }, cambiar] = useFiltros(["limite"] as const);
  const url = rutaApi(["juegos", codigo, "simulaciones"], { limite });
  const [estado, reintentar] = useConsulta(url, (s) => consultar(url, decSimulaciones, s));
  return (
    <>
      <PestanasDeJuego codigo={codigo} />
      <h1 className="h3">Simulaciones guardadas</h1>
      <div className="mb-3">
        <label className="form-label small mb-0 me-2" htmlFor="limite">
          Mostrar
        </label>
        <select id="limite" className="form-select form-select-sm d-inline-block w-auto" value={limite ?? "20"} onChange={(e) => cambiar({ limite: e.target.value })}>
          {LIMITES.map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>
      </div>
      <Consulta estado={estado} reintentar={reintentar} que="las simulaciones">
        {(d) => (
          <>
            <ExportarConsulta juego={codigo} recurso="simulaciones" identidad={{ contexto: "Lista cargada; cada simulación acredita su identidad, corte y estado" }} datos={d} tablas={tablaSimulaciones(d)} alcance="Sólo la lista de simulaciones cargada hasta el límite indicado" filtros={{ limite: d.limite }} />
            <AvisoExperimental estadoDeUso={d.estado_de_uso}>{AVISO}</AvisoExperimental>
            {d.simulaciones.length === 0 ? (
              <div className="alert alert-info" data-estado="vacio">
                No hay simulaciones guardadas para este juego.
              </div>
            ) : (
              <TablaDesplazable etiqueta="Simulaciones guardadas">
                <table className="table table-sm">
                  <thead>
                    <tr>
                      <th scope="col">Ejecutada</th>
                      <th scope="col" className="text-end">
                        Corte
                      </th>
                      <th scope="col" className="text-end">
                        Iteraciones
                      </th>
                      <th scope="col" className="text-end">
                        Semilla
                      </th>
                      <th scope="col">Integridad</th>
                      <th scope="col">Umbral exploratorio</th>
                      <th scope="col">Detalle</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.simulaciones.map((s) => (
                      <tr key={s.id}>
                        <td className="text-nowrap">{fechaHora(s.ejecutado_en)}</td>
                        <td className="text-end">{s.corte ?? "—"}</td>
                        <td className="text-end">{s.iteraciones ?? "—"}</td>
                        <td className="text-end">{s.semilla ?? "—"}</td>
                        <td>
                          <Integridad valor={s.integridad} motivo={s.motivo} />
                          {s.motivo ? <div className="small text-danger">{s.motivo}</div> : null}
                        </td>
                        <td>
                          {s.alguna_supera_umbral_exploratorio === null
                            ? "—"
                            : s.alguna_supera_umbral_exploratorio
                              ? "alguna lo supera (a revisar)"
                              : "ninguna lo supera"}
                        </td>
                        <td>
                          <Link state={{ retornoListado: retorno }} to={`/simulaciones/${encodeURIComponent(s.id)}`}>ver</Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TablaDesplazable>
            )}
          </>
        )}
      </Consulta>
    </>
  );
}

function ValorConExacto({ v, formato }: { v: ValorExacto | null; formato: string }) {
  if (v === null) {
    return <>—</>;
  }
  return (
    <>
      {formatear(v.valor, formato)}
      {v.exacto ? <div className="small text-muted">{v.exacto}</div> : null}
    </>
  );
}

function TablaDeEstadisticas({ estadisticas }: { estadisticas: EstadisticaSimulada[] }) {
  return (
    <TablaDesplazable etiqueta="Estadísticas comparadas">
      <table className="table table-sm">
        <thead>
          <tr>
            <th scope="col">Estadística</th>
            <th scope="col" className="text-end">
              Observado
            </th>
            <th scope="col" className="text-end">
              Referencia analítica
            </th>
            <th scope="col" className="text-end">
              Percentil observado
            </th>
            <th scope="col" className="text-end">
              p-value empírico
            </th>
            <th scope="col" className="text-end">
              p-value ajustado (Bonferroni)
            </th>
            <th scope="col">Umbral exploratorio</th>
          </tr>
        </thead>
        <tbody>
          {estadisticas.map((e) => (
            <tr key={e.nombre}>
              <td>
                <code>{e.nombre}</code>
                <div className="small text-muted">{e.descripcion}</div>
              </td>
              <td className="text-end">
                <ValorConExacto v={e.observado} formato="dec3" />
              </td>
              <td className="text-end">
                <ValorConExacto v={e.referencia_analitica} formato="dec3" />
              </td>
              <td className="text-end">
                <ValorConExacto v={e.percentil_observado} formato="dec3" />
              </td>
              <td className="text-end">
                <ValorConExacto v={e.p_valor_empirico} formato="p" />
              </td>
              <td className="text-end">
                <ValorConExacto v={e.p_valor_ajustado_bonferroni} formato="p" />
              </td>
              <td>{e.supera_umbral_exploratorio === null ? "—" : e.supera_umbral_exploratorio ? "lo supera" : "no lo supera"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </TablaDesplazable>
  );
}

export function DetalleSimulacion() {
  const { identificador = "" } = useParams();
  const { state: origen } = useLocation();
  const url = rutaApi(["simulaciones", identificador]);
  const [estado, reintentar] = useConsulta(url, (s) => consultar(url, decSimulacion, s));
  return (
    <>
      <h1 className="h3">Simulación guardada</h1>
      <Consulta estado={estado} reintentar={reintentar} que="la simulación">
        {(s) => (
          <>
            <PestanasDeJuego codigo={s.juego} />
            <ExportarConsulta juego={s.juego} recurso="simulacion" identidad={identidadSimulacion(s)} datos={s} tablas={tablaSimulacion(s)} alcance="Estadísticas y parámetros de esta simulación guardada; no es una nueva simulación" />
            <AvisoExperimental estadoDeUso={s.estado_de_uso}>{s.contenido.nota}</AvisoExperimental>
            <div className="card stat-card p-3 mb-3">
              <dl className="row small mb-0">
                <dt className="col-sm-3">Integridad</dt>
                <dd className="col-sm-9">
                  <Integridad valor={s.integridad} /> (la API la comprueba con la huella del contenido al leerla)
                </dd>
                <dt className="col-sm-3">Huella del contenido</dt>
                <dd className="col-sm-9">
                  <Huella valor={s.contenido_sha256} />
                </dd>
                <dt className="col-sm-3">Juego e iteraciones</dt>
                <dd className="col-sm-9">
                  {s.juego} · {s.num_iteraciones} iteraciones
                </dd>
                <dt className="col-sm-3">Ejecutada</dt>
                <dd className="col-sm-9">
                  {fechaHora(s.ejecutado_en)} · {s.duracion_ms ?? "—"} ms
                </dd>
                <dt className="col-sm-3">Identificador</dt>
                <dd className="col-sm-9">
                  <Huella valor={s.id} />
                </dd>
              </dl>
            </div>
            <h2 className="h5">Estadísticas comparadas</h2>
            <TablaDeEstadisticas estadisticas={s.contenido.estadisticas} />
            <p className="small mt-2">
              Alguna supera el umbral exploratorio:{" "}
              {s.contenido.alguna_supera_umbral_exploratorio === null ? "—" : s.contenido.alguna_supera_umbral_exploratorio ? "sí" : "no"}.
            </p>
            <details className="mb-3">
              <summary>Familia de comparaciones</summary>
              <ArbolDeDatos datos={s.contenido.familia} />
            </details>
            <details className="mb-3">
              <summary>Parámetros (identidad completa)</summary>
              <ArbolDeDatos datos={s.parametros} />
            </details>
            <details className="mb-3">
              <summary>Contenido completo</summary>
              <ArbolDeDatos datos={s.contenido.completo} />
            </details>
            <p className="small">
              <Link to={rutaDeRetorno(origen, `/juegos/${encodeURIComponent(s.juego)}/simulaciones`, ["limite"])}>Volver a las simulaciones</Link>
            </p>
          </>
        )}
      </Consulta>
    </>
  );
}
