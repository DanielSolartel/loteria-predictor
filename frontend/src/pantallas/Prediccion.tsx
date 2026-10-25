/**
 * Prediccion guardada (GET /juegos/{codigo}/predicciones?cartera=...): seleccion
 * en el historial, modelo proyectado, clasificacion temporal, integridad,
 * combinaciones, observado y frente a la base. Todo es lo que informa la API;
 * esta consulta no informa la frescura del historico.
 */
import { Link, useParams } from "react-router-dom";
import { consultar, rutaApi } from "../api/cliente";
import { fechaHora } from "../api/formatos";
import {
  type BaseDelJuego,
  type Combinacion,
  decPredicciones,
  type FrenteALaBase,
  type Observado,
  type Prediccion as PrediccionDatos,
  type Predicciones,
} from "../api/presentacion";
import { ArbolDeDatos, AvisoExperimental, Huella, TablaDesplazable, VerResultado } from "../componentes/comunes";
import { Consulta } from "../componentes/Estados";
import { useFiltros } from "../componentes/Filtros";
import { PestanasDeJuego } from "../componentes/Marco";
import { useConsulta } from "../usos/consulta";

const NO_INFORMADO = <span className="text-muted">no informado</span>;
const legible = (texto: string) => texto.replaceAll("_", " ");
const siNo = (v: boolean | null) => (v === null ? NO_INFORMADO : v ? "sí" : "no");

/** Base del juego: estado de la base, corte y ultima fecha; sin equipararlo a «datos al dia». */
function VistaBase({ base, codigo }: { base: BaseDelJuego; codigo: string }) {
  const valor = (v: number | string | null | undefined) => (v === null || v === undefined ? NO_INFORMADO : v);
  return (
    <div className="card stat-card p-3 mb-3" data-base={base.estado}>
      <h2 className="h6">Base del juego</h2>
      <dl className="row small mb-2">
        <dt className="col-sm-4">Estado de la base</dt>
        <dd className="col-sm-8">{legible(base.estado)}</dd>
        <dt className="col-sm-4">Corte (último sorteo cargado)</dt>
        <dd className="col-sm-8">{valor(base.corte)}</dd>
        <dt className="col-sm-4">Sorteos</dt>
        <dd className="col-sm-8">{valor(base.sorteos)}</dd>
        <dt className="col-sm-4">Última fecha cargada</dt>
        <dd className="col-sm-8">{valor(base.ultima_fecha)}</dd>
        <dt className="col-sm-4">Siguiente objetivo</dt>
        <dd className="col-sm-8">{valor(base.objetivo)}</dd>
        <dt className="col-sm-4">Frescura del histórico</dt>
        <dd className="col-sm-8" data-frescura="no_informada">
          no informada por esta consulta
        </dd>
      </dl>
      <p className="small text-muted mb-0">
        «Base disponible» indica que la base respondió, no que los datos estén al día. La frescura la informa el{" "}
        <Link to={`/juegos/${encodeURIComponent(codigo)}`}>resumen del juego</Link>.
      </p>
    </div>
  );
}

function Historial({ datos, seleccionada, codigo }: { datos: Predicciones; seleccionada: string | null; codigo: string }) {
  if (datos.historial.length === 0) {
    return <p className="small text-muted">Sin predicciones guardadas en el historial.</p>;
  }
  return (
    <>
      <p className="small text-muted mb-1">
        Se muestran {datos.historial.length} de {datos.historial_total} predicciones guardadas.
      </p>
      <TablaDesplazable etiqueta="Historial de predicciones guardadas">
        <table className="table table-sm">
          <thead>
            <tr>
              <th scope="col" className="text-end">
                Objetivo
              </th>
              <th scope="col" className="text-end">
                Corte
              </th>
              <th scope="col">Generada (UTC)</th>
              <th scope="col">Clasificación temporal</th>
              <th scope="col">Línea</th>
              <th scope="col">Ver</th>
            </tr>
          </thead>
          <tbody>
            {datos.historial.map((h) => (
              <tr key={h.clave} className={h.clave === seleccionada ? "table-active" : undefined}>
                <td className="text-end">{h.objetivo ?? "—"}</td>
                <td className="text-end">{h.corte ?? "—"}</td>
                {h.ilegible ? (
                  <td colSpan={3} className="text-danger">
                    ilegible: {h.ilegible}
                  </td>
                ) : (
                  <>
                    <td className="text-nowrap">{fechaHora(h.generado_en)}</td>
                    <td>{h.tipo ? legible(h.tipo) : "sin clasificación"}</td>
                    <td>
                      <code>{h.linea ?? "—"}</code>
                    </td>
                  </>
                )}
                <td>
                  {h.clave === seleccionada ? (
                    <span aria-current="true">seleccionada</span>
                  ) : h.ilegible ? (
                    "—"
                  ) : (
                    <Link to={`/juegos/${encodeURIComponent(codigo)}/prediccion?cartera=${h.clave}`} aria-label={`Ver la predicción del objetivo ${h.objetivo ?? ""}`}>
                      ver
                    </Link>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </TablaDesplazable>
    </>
  );
}

function Combinaciones({ combinaciones, observado }: { combinaciones: Combinacion[]; observado: Observado | null }) {
  const aciertos = observado?.estado === "observado" ? (observado.aciertos?.por_linea ?? []) : null;
  return (
    <TablaDesplazable etiqueta="Combinaciones de la predicción">
      <table className="table table-sm">
        <thead>
          <tr>
            <th scope="col" className="text-end">
              Línea
            </th>
            <th scope="col">Combinación</th>
            <th scope="col">Papel y detalle</th>
            {aciertos ? (
              <th scope="col" className="text-end">
                Aciertos observados
              </th>
            ) : null}
          </tr>
        </thead>
        <tbody>
          {combinaciones.map((c) => {
            const a = aciertos?.find((x) => x.linea === c.linea);
            return (
              <tr key={c.linea}>
                <td className="text-end">{c.linea}</td>
                <td>
                  <VerResultado resultado={c.resultado} />
                </td>
                <td className="small">
                  {c.papel ? <strong>{c.papel}</strong> : null}
                  {c.detalle ? `: ${c.detalle}` : null}
                  {c.probabilidades_de_sus_elementos ? (
                    <div className="text-muted">
                      {c.unidad_de_los_elementos ?? "probabilidades"}:{" "}
                      {c.probabilidades_de_sus_elementos.map((x) => Number(x.toFixed(4))).join(", ")}
                      {c.probabilidad_de_su_superbalota !== null
                        ? ` · superbalota (aparte): ${Number(c.probabilidad_de_su_superbalota.toFixed(4))}`
                        : ""}
                    </div>
                  ) : null}
                </td>
                {aciertos ? (
                  <td className="text-end">
                    {a ? a.aciertos : "—"}
                    {a && a.superbalota !== null ? ` · sb ${a.superbalota ? "sí" : "no"}` : ""}
                  </td>
                ) : null}
              </tr>
            );
          })}
        </tbody>
      </table>
    </TablaDesplazable>
  );
}

function VistaObservado({ o }: { o: Observado | null }) {
  if (o === null) {
    return NO_INFORMADO;
  }
  if (o.estado === "observado") {
    return (
      <span data-observado="observado">
        observado el {o.fecha ?? "—"}: {o.resultado ? <VerResultado resultado={o.resultado} /> : null}
        {o.aciertos ? (
          <span className="d-block">
            Máximo de la cartera: {o.aciertos.maximo ?? "—"} ({o.aciertos.definicion})
          </span>
        ) : null}
      </span>
    );
  }
  return (
    <span data-observado={o.estado}>
      {legible(o.estado)}
      {o.motivo ? `: ${o.motivo}` : ""}
    </span>
  );
}

function VistaFrenteALaBase({ f }: { f: FrenteALaBase | null }) {
  if (f === null) {
    return NO_INFORMADO;
  }
  if (f.estado !== "disponible") {
    return <span className="text-danger">{legible(f.estado)}</span>;
  }
  return (
    <span data-frente={f.base_avanzo ? "base_avanzo" : "sin_cambios"}>
      histórico hasta el corte: {f.historico_hasta_el_corte ? legible(f.historico_hasta_el_corte) : "no informado"} · último
      sorteo actual {f.ultimo_sorteo_actual ?? "—"}
      {f.base_avanzo ? (
        <span className="text-warning-emphasis"> · la base avanzó {f.nuevos_desde_el_corte ?? "?"} sorteo(s) desde el corte</span>
      ) : null}
    </span>
  );
}

function VistaPrediccion({ p }: { p: PrediccionDatos }) {
  const t = p.clasificacion_temporal;
  return (
    <div className="card stat-card p-3 mb-3" data-prediccion={p.clave}>
      <h2 className="h5 mb-2">
        Objetivo {p.objetivo} · {p.combinaciones.length} combinaciones
      </h2>
      <Combinaciones combinaciones={p.combinaciones} observado={p.observado} />
      <dl className="row small mt-3 mb-0">
        <dt className="col-sm-3">Integridad</dt>
        <dd className="col-sm-9" data-integridad={p.integridad}>
          {p.integridad} (verificada por la API al leerla)
        </dd>
        <dt className="col-sm-3">Modelo</dt>
        <dd className="col-sm-9">
          {p.modelo.nombre ?? "—"} · <code>{p.modelo.id ?? "—"}</code> v{p.modelo.version ?? "—"} · familia{" "}
          {p.modelo.familia ?? "—"} · tipo {p.modelo.tipo ?? "—"}
        </dd>
        <dt className="col-sm-3">Clasificación temporal</dt>
        <dd className="col-sm-9">
          {t ? (
            <>
              <strong>{legible(t.tipo)}</strong>. {t.descripcion}
              <span className="d-block text-muted">
                Objetivo en la base: {siNo(t.objetivo_en_la_base)} · último sorteo disponible al generar:{" "}
                {t.ultimo_sorteo_disponible ?? "—"} ({t.ultima_fecha_disponible ?? "—"})
              </span>
            </>
          ) : (
            "sin clasificación"
          )}
        </dd>
        <dt className="col-sm-3">Resultado del objetivo</dt>
        <dd className="col-sm-9">
          <VistaObservado o={p.observado} />
        </dd>
        <dt className="col-sm-3">Frente a la base actual</dt>
        <dd className="col-sm-9">
          <VistaFrenteALaBase f={p.frente_a_la_base} />
        </dd>
        <dt className="col-sm-3">Corte y generación</dt>
        <dd className="col-sm-9">
          corte {p.corte ?? "—"} · generada {fechaHora(p.generado_en)} UTC · línea <code>{p.linea}</code>
        </dd>
        <dt className="col-sm-3">Clave</dt>
        <dd className="col-sm-9">
          <Huella valor={p.clave} />
        </dd>
        <dt className="col-sm-3">Huella del histórico</dt>
        <dd className="col-sm-9">
          <Huella valor={p.sha256_historico} />
        </dd>
        <dt className="col-sm-3">Explicación</dt>
        <dd className="col-sm-9">
          {p.explicacion_disponible ? "guardada" : "no guardada"}; su presentación, la clasificación de candidatos y la fiabilidad quedan
          pendientes en esta entrega.
        </dd>
      </dl>
    </div>
  );
}

export function Prediccion() {
  const { codigo = "" } = useParams();
  const [{ cartera }] = useFiltros(["cartera"] as const);
  const url = rutaApi(["juegos", codigo, "predicciones"], { cartera });
  const [estado, reintentar] = useConsulta(url, (s) => consultar(url, decPredicciones, s));
  return (
    <>
      <PestanasDeJuego codigo={codigo} />
      <h1 className="h3">Predicción guardada</h1>
      <Consulta estado={estado} reintentar={reintentar} que="la predicción guardada">
        {(d) => (
          <>
            <AvisoExperimental estadoDeUso={d.estado_de_uso}>{d.aviso}</AvisoExperimental>
            <details className="small mb-3">
              <summary>Contexto informado por la API</summary>
              <ArbolDeDatos datos={d.contexto} />
            </details>
            <p className="small">
              Configuración de predicción: <strong data-configuracion={d.configuracion}>{legible(d.configuracion)}</strong>
            </p>
            <VistaBase base={d.base} codigo={codigo} />
            {d.prediccion ? (
              <VistaPrediccion p={d.prediccion} />
            ) : (
              <div className="alert alert-info" data-estado="sin-prediccion">
                No hay predicción guardada para mostrar
                {d.configuracion === "sin_configuracion" ? ": el juego no tiene configuración de predicción vigente." : "."}
              </div>
            )}
            <h2 className="h5">Historial</h2>
            <Historial datos={d} seleccionada={d.prediccion?.clave ?? null} codigo={codigo} />
          </>
        )}
      </Consulta>
    </>
  );
}
