/**
 * Salud y estado del proceso de la API publica (GET /salud y /estado). No es el
 * estado de la operacion automatica: esa vive en la consola local y no tiene
 * consulta en la API v1.
 */
import { consultar, rutaApi } from "../api/cliente";
import { fechaHora } from "../api/formatos";
import { decEstado, decSalud } from "../api/presentacion";
import { ArbolDeDatos, TablaDesplazable } from "../componentes/comunes";
import { Consulta } from "../componentes/Estados";
import { useConsulta } from "../usos/consulta";

const URL_SALUD = rutaApi(["salud"]);
const URL_ESTADO = rutaApi(["estado"]);

export function Servicio() {
  const [salud, reintentarSalud] = useConsulta(URL_SALUD, (s) => consultar(URL_SALUD, decSalud, s));
  const [estado, reintentarEstado] = useConsulta(URL_ESTADO, (s) => consultar(URL_ESTADO, decEstado, s));
  return (
    <>
      <h1 className="h3">Servicio de la API</h1>
      <div className="alert alert-info small" role="note">
        Esta página describe el <strong>proceso de la API pública</strong> (salud, solicitudes, latencia, límites y
        disponibilidad de su base). <strong>No</strong> informa de la operación automática, sus tareas programadas ni sus
        ejecuciones: no tienen consulta en la API v1.
      </div>
      <h2 className="h5">Salud del proceso</h2>
      <Consulta estado={salud} reintentar={reintentarSalud} que="la salud">
        {(s) => (
          <p data-salud={s.estado}>
            <span className={`badge ${s.estado === "ok" ? "text-bg-success" : "text-bg-warning"}`}>{s.estado}</span> · API{" "}
            {s.api}
          </p>
        )}
      </Consulta>
      <h2 className="h5">Estado del proceso</h2>
      <Consulta estado={estado} reintentar={reintentarEstado} que="el estado">
        {(e) => (
          <>
            <dl className="row small">
              <dt className="col-sm-3">Iniciado</dt>
              <dd className="col-sm-9">
                {fechaHora(e.iniciado_en)} UTC · {Math.floor(e.segundos_activo)} s activo
              </dd>
              <dt className="col-sm-3">Base de la API</dt>
              <dd className="col-sm-9" data-base={e.base}>
                {e.base.replaceAll("_", " ")} (disponibilidad, no frescura de los datos)
              </dd>
              <dt className="col-sm-3">Solicitudes</dt>
              <dd className="col-sm-9">
                {e.solicitudes} ·{" "}
                {Object.entries(e.por_clase)
                  .map(([k, v]) => `${k}: ${v}`)
                  .join(" · ") || "—"}
              </dd>
              <dt className="col-sm-3">Claves configuradas</dt>
              <dd className="col-sm-9">{e.claves_configuradas}</dd>
            </dl>
            <details className="mb-3" open>
              <summary>Límites de uso</summary>
              <ArbolDeDatos datos={e.limites} />
            </details>
            <TablaDesplazable etiqueta="Solicitudes por ruta">
              <table className="table table-sm">
                <thead>
                  <tr>
                    <th scope="col">Método</th>
                    <th scope="col">Ruta</th>
                    <th scope="col" className="text-end">
                      Solicitudes
                    </th>
                    <th scope="col" className="text-end">
                      4xx
                    </th>
                    <th scope="col" className="text-end">
                      5xx
                    </th>
                    <th scope="col" className="text-end">
                      Latencia media (ms)
                    </th>
                    <th scope="col" className="text-end">
                      Latencia máxima (ms)
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {e.rutas.map((r) => (
                    <tr key={`${r.metodo} ${r.ruta}`}>
                      <td>{r.metodo}</td>
                      <td>
                        <code>{r.ruta}</code>
                      </td>
                      <td className="text-end">{r.solicitudes}</td>
                      <td className="text-end">{r.errores_4xx}</td>
                      <td className="text-end">{r.errores_5xx}</td>
                      <td className="text-end">{r.latencia_media_ms.toFixed(1)}</td>
                      <td className="text-end">{r.latencia_maxima_ms.toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TablaDesplazable>
          </>
        )}
      </Consulta>
    </>
  );
}
