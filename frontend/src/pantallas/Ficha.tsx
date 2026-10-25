/** Ficha de un juego (GET /juegos/{codigo}) y su resumen con frescura (GET .../estadisticas/resumen). */
import { Link, useParams } from "react-router-dom";
import { consultar, rutaApi } from "../api/cliente";
import { formatear } from "../api/formatos";
import {
  type Atrasos,
  decJuegoDetalle,
  decResumen,
  type FilaDistribucion,
  type Frecuencias,
  type Resumen,
} from "../api/presentacion";
import { ArbolDeDatos, Color, Numeros, Pares, TablaDesplazable } from "../componentes/comunes";
import { Consulta } from "../componentes/Estados";
import { Tarjeta, VistaMuestra } from "../componentes/estadisticas";
import { FormularioDeCorte, useFiltros } from "../componentes/Filtros";
import { PestanasDeJuego } from "../componentes/Marco";
import { useConsulta } from "../usos/consulta";
import { reglasDe } from "./Inicio";

/** Fraccion de sorteos mostrada en %, como la consola HTMX (`100 * frecuencia_relativa`, un decimal). */
const porcentaje = (fraccion: number) => formatear(100 * fraccion, "pct");

function TablaFrecuencias({ titulo, filas, colores, unidad }: { titulo: string; filas: Frecuencias["todas"]; colores?: boolean; unidad: string }) {
  return (
    <TablaDesplazable etiqueta={titulo}>
      <table className="table table-sm">
        <thead>
          <tr>
            <th scope="col">Valor</th>
            <th scope="col" className="text-end">
              Apariciones
            </th>
            <th scope="col" className="text-end">
              {unidad}
            </th>
          </tr>
        </thead>
        <tbody>
          {filas.map((f) => (
            <tr key={f.valor}>
              <td>{colores ? <Color color={f.valor} /> : f.valor}</td>
              <td className="text-end">{f.apariciones}</td>
              <td className="text-end">{formatear(f.frecuencia_relativa, "dec3")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </TablaDesplazable>
  );
}

function TablaDistribucion({ titulo, etiqueta, filas }: { titulo: string; etiqueta: string; filas: FilaDistribucion[] }) {
  return (
    <div className="card stat-card p-3 h-100">
      <h3 className="h6">{titulo}</h3>
      <TablaDesplazable etiqueta={titulo}>
        <table className="table table-sm">
          <thead>
            <tr>
              <th scope="col">{etiqueta}</th>
              <th scope="col" className="text-end">
                Sorteos
              </th>
              <th scope="col" className="text-end">
                % de sorteos
              </th>
            </tr>
          </thead>
          <tbody>
            {filas.map((d) => (
              <tr key={d.valor}>
                <td>{d.valor}</td>
                <td className="text-end">{d.sorteos}</td>
                <td className="text-end">{porcentaje(d.frecuencia_relativa)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </TablaDesplazable>
    </div>
  );
}

function TablaAtrasos({ titulo, atrasos, colores }: { titulo: string; atrasos: Atrasos; colores?: boolean }) {
  return (
    <div className="card stat-card p-3 h-100">
      <h3 className="h6">{titulo}</h3>
      <TablaDesplazable etiqueta={titulo}>
        <table className="table table-sm">
          <thead>
            <tr>
              <th scope="col">Valor</th>
              <th scope="col" className="text-end">
                Sorteos sin salir
              </th>
            </tr>
          </thead>
          <tbody>
            {atrasos.mayores.map((a) => (
              <tr key={a.valor}>
                <td>{colores ? <Color color={a.valor} /> : a.valor}</td>
                <td className="text-end">{a.atraso}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </TablaDesplazable>
      {atrasos.nunca_observados.length > 0 ? (
        <p className="small text-muted mb-0">Nunca observados: {atrasos.nunca_observados.join(", ")}</p>
      ) : null}
    </div>
  );
}

function Lista({ filas }: { filas: Frecuencias["mas_frecuentes"] }) {
  return <>{filas.map((f) => `${f.valor} (${f.apariciones})`).join(", ") || "—"}</>;
}

function EstadisticasDelResumen({ r }: { r: Resumen }) {
  if (r.tipo === "colorloto") {
    const e = r.estadisticas;
    if (e === null) {
      return null;
    }
    return (
      <div className="row g-3">
        <div className="col-md-6">
          <div className="card stat-card p-3 h-100">
            <h3 className="h6">Frecuencia de colores</h3>
            <p className="small text-muted">
              Promedio de apariciones por sorteo (6 balotas con repetición): puede superar 1 y no es una probabilidad.
            </p>
            <TablaFrecuencias titulo="Frecuencia de colores" filas={e.frecuencia_colores.todas} colores unidad="promedio por sorteo" />
            {e.colores_fuera_de_la_paleta_vigente.length > 0 ? (
              <p className="small text-warning-emphasis mb-0">
                Colores observados fuera de la paleta vigente: {e.colores_fuera_de_la_paleta_vigente.join(", ")}
              </p>
            ) : null}
          </div>
        </div>
        <div className="col-md-6">
          <div className="card stat-card p-3 h-100">
            <h3 className="h6">Frecuencia de números</h3>
            <p className="small text-muted">Promedio de apariciones por sorteo: puede superar 1 y no es una probabilidad.</p>
            <TablaFrecuencias titulo="Frecuencia de números" filas={e.frecuencia_numeros.todas} unidad="promedio por sorteo" />
          </div>
        </div>
        <div className="col-md-6">
          <TablaAtrasos titulo="Atraso de colores" atrasos={e.atrasos_colores} colores />
        </div>
        <div className="col-md-6">
          <div className="card stat-card p-3 h-100">
            <h3 className="h6">Pares número-color más y menos frecuentes</h3>
            <p className="small mb-1">
              Más: <Lista filas={e.frecuencia_pares.mas_frecuentes} />
            </p>
            <p className="small mb-0">
              Menos: <Lista filas={e.frecuencia_pares.menos_frecuentes} />
            </p>
          </div>
        </div>
        <div className="col-md-6">
          <TablaDistribucion titulo="Máximo de balotas del mismo color por sorteo" etiqueta="Máximo" filas={e.maximo_repeticion_color} />
        </div>
        <div className="col-md-6">
          <TablaDistribucion titulo="Números pares por sorteo" etiqueta="Pares" filas={e.pares_impares} />
        </div>
      </div>
    );
  }
  const e = r.estadisticas;
  if (e === null) {
    return null;
  }
  const dec = e.decenas_sobre_numeros_extraidos;
  return (
    <div className="row g-3">
      <div className="col-md-8">
        <div className="card stat-card p-3 h-100">
          <h3 className="h6">
            Frecuencia de números ({r.reglas.rango[0]}–{r.reglas.rango[1]})
          </h3>
          <TablaFrecuencias titulo="Frecuencia de números" filas={e.frecuencia_numeros.todas} unidad="fracción de sorteos" />
        </div>
      </div>
      <div className="col-md-4">
        <TablaAtrasos titulo="Mayores atrasos" atrasos={e.atrasos_numeros} />
      </div>
      <div className="col-md-4">
        <div className="card stat-card p-3 h-100">
          <h3 className="h6">Más y menos frecuentes</h3>
          <p className="small mb-1">
            Más: <Lista filas={e.frecuencia_numeros.mas_frecuentes} />
          </p>
          <p className="small mb-0">
            Menos: <Lista filas={e.frecuencia_numeros.menos_frecuentes} />
          </p>
        </div>
      </div>
      <div className="col-md-4">
        <div className="card stat-card p-3 h-100">
          <h3 className="h6">Superbalota</h3>
          {e.superbalota ? (
            <>
              <p className="small mb-1">
                Más frecuentes: <Lista filas={e.superbalota.frecuencia.mas_frecuentes} />
              </p>
              <p className="small mb-0">
                Mayor atraso: {e.superbalota.atrasos.mayores.map((a) => `${a.valor} (${a.atraso})`).join(", ") || "—"}
              </p>
            </>
          ) : (
            <p className="small text-muted mb-0">{r.nombre} no tiene superbalota.</p>
          )}
        </div>
      </div>
      <div className="col-md-4">
        <div className="card stat-card p-3 h-100">
          <h3 className="h6">Números por decena</h3>
          <p className="small text-muted">
            Porcentaje de todos los números extraídos: {dec.denominador.sorteos} sorteos × {dec.denominador.numeros_por_sorteo}{" "}
            números = {dec.denominador.numeros_extraidos} números extraídos.
          </p>
          <TablaDesplazable etiqueta="Números por decena">
            <table className="table table-sm">
              <thead>
                <tr>
                  <th scope="col">Franja</th>
                  <th scope="col" className="text-end">
                    Apariciones
                  </th>
                  <th scope="col" className="text-end">
                    % de los números extraídos
                  </th>
                </tr>
              </thead>
              <tbody>
                {dec.filas.map((d) => (
                  <tr key={d.valor}>
                    <td>{d.valor}</td>
                    <td className="text-end">{d.apariciones}</td>
                    <td className="text-end">
                      {formatear(d.porcentaje_de_numeros_extraidos, "pct")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TablaDesplazable>
        </div>
      </div>
      <div className="col-md-4">
        <TablaDistribucion titulo="Números pares por sorteo" etiqueta="Pares" filas={e.pares_impares} />
      </div>
      <div className="col-md-4">
        <TablaDistribucion titulo="Números bajos por sorteo" etiqueta="Bajos" filas={e.altos_bajos} />
      </div>
    </div>
  );
}

function VistaResumen({ r, corte }: { r: Resumen; corte: string | null }) {
  return (
    <>
      <VistaMuestra muestra={r} />
      {r.estadisticas === null ? (
        <div className="alert alert-info" data-estado="sin-sorteos">
          No hay sorteos {corte !== null ? "hasta el corte indicado" : "cargados para este juego"}.
        </div>
      ) : (
        <>
          <p className="mb-3">
            <span className="small text-muted me-1">Último resultado analizado:</span>
            {r.tipo === "colorloto"
              ? r.ultimo_resultado && <Pares pares={r.ultimo_resultado.pares} />
              : r.ultimo_resultado && <Numeros numeros={r.ultimo_resultado.numeros} superbalota={r.ultimo_resultado.superbalota} />}
          </p>
          <EstadisticasDelResumen r={r} />
        </>
      )}
    </>
  );
}

export function Ficha() {
  const { codigo = "" } = useParams();
  const [{ hasta_numero_sorteo: corte }, cambiar] = useFiltros(["hasta_numero_sorteo"] as const);
  const urlJuego = rutaApi(["juegos", codigo]);
  const urlResumen = rutaApi(["juegos", codigo, "estadisticas", "resumen"], { hasta_numero_sorteo: corte });
  const [juego, reintentarJuego] = useConsulta(urlJuego, (s) => consultar(urlJuego, decJuegoDetalle, s));
  const [resumen, reintentarResumen] = useConsulta(urlResumen, (s) => consultar(urlResumen, decResumen, s));
  return (
    <>
      <PestanasDeJuego codigo={codigo} />
      <h1 className="h3">Ficha y resumen</h1>
      <Consulta estado={juego} reintentar={reintentarJuego} que="la ficha del juego">
        {(j) => (
          <div className="row g-3 mb-3">
            <div className="col-md-6">
              <Tarjeta titulo="Reglas">
                <div>{reglasDe(j)}</div>
              </Tarjeta>
            </div>
            <div className="col-md-6">
              <Tarjeta titulo="Espacio muestral">
                <div className="fw-bold">{j.espacio_muestral.toLocaleString("es-CO")} combinaciones</div>
                <details className="small mt-1">
                  <summary>Dimensiones informadas por la API</summary>
                  <ArbolDeDatos datos={j.dimensiones} />
                </details>
              </Tarjeta>
            </div>
          </div>
        )}
      </Consulta>
      <h2 className="h4">Resumen</h2>
      <FormularioDeCorte key={corte ?? ""} valor={corte} aplicar={(v) => cambiar({ hasta_numero_sorteo: v })} />
      <Consulta estado={resumen} reintentar={reintentarResumen} que="el resumen">
        {(r) => <VistaResumen r={r} corte={corte} />}
      </Consulta>
      <p className="small mt-3">
        <Link to={`/juegos/${encodeURIComponent(codigo)}/estadisticas${corte ? `?hasta_numero_sorteo=${encodeURIComponent(corte)}` : ""}`}>
          Panel completo de estadísticas
        </Link>
      </p>
    </>
  );
}
