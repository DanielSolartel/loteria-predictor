/**
 * Fase 9.3: fiabilidad observada (contrato de la Fase 4). Seguimiento,
 * retrospectiva y evaluacion de la receta se presentan por separado, con su
 * muestra, exclusiones, perdidas frente a la uniforme e incertidumbre, tal como
 * las informa la API. No hay puntuacion de confianza ni probabilidad de premio:
 * la interfaz no combina ni recalcula cifras.
 */
import { Fragment } from "react";
import { COMPONENTES_FIABILIDAD, ESTADOS_FIABILIDAD, especificacion, formatearCifra, TIPOS_FIABILIDAD } from "../api/formatos";
import type {
  ComponenteDeFiabilidad,
  EvaluacionDeFiabilidad,
  ExtremoObservado,
  Fiabilidad,
  MetricaDeFiabilidad,
  MetodoDeFiabilidad,
  MuestraDeFiabilidad,
} from "../api/presentacion";
import { Huella, TablaDesplazable } from "./comunes";

const legible = (texto: string) => texto.replaceAll("_", " ");
const ORDEN_COMPONENTES = ["numeros", "pares", "superbalota"];

export function etiquetaDeEstado(estado: string): string {
  return ESTADOS_FIABILIDAD[estado] ?? legible(estado);
}

function componentesOrdenados(ev: EvaluacionDeFiabilidad): [string, ComponenteDeFiabilidad][] {
  return Object.entries(ev.componentes).sort(
    ([a], [b]) => (ORDEN_COMPONENTES.indexOf(a) + 1 || 99) - (ORDEN_COMPONENTES.indexOf(b) + 1 || 99),
  );
}

/** Lectura de Δ Log Loss y del estado «estimable»; siempre visible junto a las cifras. */
export function LeyendaDeFiabilidad() {
  return (
    <p className="small text-muted mb-2" data-leyenda="delta">
      Δ = modelo − uniforme por sorteo. <strong>Positivo: mayor pérdida que la uniforme; negativo: menor pérdida en esa
      muestra.</strong> «Estimable» solo indica que hay sorteos suficientes para calcular un intervalo: no acredita ventaja
      predictiva. No es una puntuación de confianza ni una probabilidad de premio.
    </p>
  );
}

export function VistaEstado({ estado, motivo }: { estado: string; motivo: string | null }) {
  return (
    <span data-estado-fiabilidad={estado}>
      {etiquetaDeEstado(estado)}
      {motivo ? `: ${motivo}` : ""}
    </span>
  );
}

function MediaEIntervalo({ m }: { m: MetricaDeFiabilidad | undefined }) {
  if (!m || m.media === null) {
    return <>—</>;
  }
  return (
    <span className="text-nowrap">
      {formatearCifra(m.media)}
      {m.intervalo ? ` [${formatearCifra(m.intervalo[0])}, ${formatearCifra(m.intervalo[1])}]` : " (sin intervalo)"}
    </span>
  );
}

/** Δ Log Loss de un componente en una celda compacta (resumen al corte). */
function DeltaDeComponente({ ev, componente }: { ev: EvaluacionDeFiabilidad; componente: string }) {
  const c = ev.componentes[componente];
  if (!c) {
    return <>—</>;
  }
  if (!c.metricas) {
    return <VistaEstado estado={c.estado ?? "no_disponible"} motivo={c.motivo} />;
  }
  return <MediaEIntervalo m={c.metricas.diferencia_log_loss} />;
}

function FilaDeResumen({ ev, linea, estimador }: { ev: EvaluacionDeFiabilidad; linea: string; estimador: string }) {
  const principal = "pares" in ev.componentes ? "pares" : "numeros";
  const m = ev.muestra;
  return (
    <tr data-evaluacion={ev.tipo} data-estado={ev.estado}>
      <td>
        {linea}
        <span className="d-block text-muted">{estimador}</span>
      </td>
      <td>{TIPOS_FIABILIDAD[ev.tipo] ?? legible(ev.tipo)}</td>
      <td>
        <VistaEstado estado={ev.estado} motivo={ev.motivo} />
      </td>
      <td className="text-end">{m?.sorteos ?? 0}</td>
      <td className="text-end">{m?.pendientes ?? "—"}</td>
      <td>
        {!m || m.exclusiones.length === 0
          ? "ninguna"
          : m.exclusiones.map((x) => (
              <span className="d-block" key={`${x.estado}-${x.motivo}`}>
                {x.emisiones} {legible(x.motivo)}
              </span>
            ))}
      </td>
      <td>
        <DeltaDeComponente ev={ev} componente={principal} />
      </td>
      <td>
        <DeltaDeComponente ev={ev} componente="superbalota" />
      </td>
    </tr>
  );
}

/** Tabla compacta de la fiabilidad: una fila por linea y tipo, y la receta aparte. */
export function ResumenDeFiabilidad({ f }: { f: Fiabilidad }) {
  return (
    <TablaDesplazable etiqueta={f.hasta === null ? "Fiabilidad con todos los resultados" : `Fiabilidad hasta el sorteo ${f.hasta}`}>
      <table className="table table-sm small mb-0">
        <thead>
          <tr>
            <th scope="col">Línea</th>
            <th scope="col">Tipo</th>
            <th scope="col">Estado</th>
            <th scope="col" className="text-end">
              Sorteos incluidos
            </th>
            <th scope="col" className="text-end">
              Pendientes
            </th>
            <th scope="col">Exclusiones</th>
            <th scope="col">Δ Log Loss (media [intervalo 95 %])</th>
            <th scope="col">Δ Log Loss superbalota (aparte)</th>
          </tr>
        </thead>
        <tbody>
          {f.lineas.map((l) =>
            l.evaluaciones.map((ev) => <FilaDeResumen key={`${l.linea}-${ev.tipo}`} ev={ev} linea={l.nombre} estimador={l.estimador} />),
          )}
          <FilaDeResumen ev={f.receta} linea="Receta en su informe" estimador={f.receta.origen ?? ""} />
        </tbody>
      </table>
    </TablaDesplazable>
  );
}

function VistaMuestra({ m }: { m: MuestraDeFiabilidad | null }) {
  if (!m) {
    return <p className="small text-muted mb-1">Muestra no informada.</p>;
  }
  return (
    <dl className="row small mb-1">
      <dt className="col-sm-4">Sorteos incluidos</dt>
      <dd className="col-sm-8">
        {m.sorteos ?? 0}
        {m.periodo ? ` (objetivos ${m.periodo[0]}–${m.periodo[1]})` : ""}
      </dd>
      <dt className="col-sm-4">Evidencia</dt>
      <dd className="col-sm-8">{m.hasta === null ? "todos los resultados observados" : `solo objetivos hasta el sorteo ${m.hasta}`}</dd>
      {m.emisiones !== null ? (
        <>
          <dt className="col-sm-4">Emisiones de la línea y tipo</dt>
          <dd className="col-sm-8">{m.emisiones}</dd>
        </>
      ) : null}
      {m.pendientes !== null ? (
        <>
          <dt className="col-sm-4">Pendientes</dt>
          <dd className="col-sm-8">{m.pendientes} sin resultado observado en la base consultada (no se deduce si el sorteo ya ocurrió)</dd>
        </>
      ) : null}
      {m.sin_base !== null ? (
        <>
          <dt className="col-sm-4">Sin base</dt>
          <dd className="col-sm-8">{m.sin_base} (la base no respondió: no se sabe si tienen resultado)</dd>
        </>
      ) : null}
      {m.estado_del_candidato !== null ? (
        <>
          <dt className="col-sm-4">Estado en el informe</dt>
          <dd className="col-sm-8">{legible(m.estado_del_candidato)}</dd>
        </>
      ) : null}
      {m.excluidos_de_la_muestra_comun !== null ? (
        <>
          <dt className="col-sm-4">Excluidos de la muestra común</dt>
          <dd className="col-sm-8">{m.excluidos_de_la_muestra_comun}</dd>
        </>
      ) : null}
      <dt className="col-sm-4">Exclusiones</dt>
      <dd className="col-sm-8" data-exclusiones={m.exclusiones.length}>
        {m.exclusiones.length === 0
          ? "ninguna"
          : m.exclusiones.map((x) => (
              <span className="d-block" key={`${x.estado}-${x.motivo}`}>
                {x.emisiones} {legible(x.estado)}: {legible(x.motivo)}
              </span>
            ))}
      </dd>
    </dl>
  );
}

function VistaExtremo({ nombre, x }: { nombre: string; x: ExtremoObservado | null }) {
  if (!x) {
    return null;
  }
  return (
    <span className="d-block">
      {nombre} ({x.candidatos_por_sorteo} por sorteo): observados {especificacion(x.observado, ".4g")} · esperados por el modelo{" "}
      {formatearCifra(x.esperado)} · razón {x.razon_observado_esperado === null ? "—" : formatearCifra(x.razon_observado_esperado)}
    </span>
  );
}

function VistaComponente({ nombre, c, tipo }: { nombre: string; c: ComponenteDeFiabilidad; tipo: string }) {
  const titulo = COMPONENTES_FIABILIDAD[nombre] ?? legible(nombre);
  if (!c.metricas) {
    return (
      <p className="small mb-2" data-componente={nombre} data-estado={c.estado ?? "no_disponible"}>
        <strong>{titulo}:</strong> <VistaEstado estado={c.estado ?? "no_disponible"} motivo={c.motivo} />
      </p>
    );
  }
  const metricas = Object.entries(c.metricas);
  return (
    <div className="mb-2" data-componente={nombre}>
      <h5 className="h6 mb-1">
        {titulo} · {c.sorteos ?? 0} sorteos
      </h5>
      <TablaDesplazable etiqueta={`${titulo}: cifras por sorteo de ${TIPOS_FIABILIDAD[tipo] ?? tipo}`}>
        <table className="table table-sm small mb-1">
          <thead>
            <tr>
              <th scope="col">Cifra por sorteo</th>
              <th scope="col">Estado</th>
              <th scope="col" className="text-end">
                n
              </th>
              <th scope="col" className="text-end">
                Media
              </th>
              <th scope="col">Intervalo 95 %</th>
              <th scope="col">Lectura</th>
            </tr>
          </thead>
          <tbody>
            {metricas.map(([clave, m]) => (
              <tr key={clave} data-metrica={clave} data-estado={m.estado}>
                <td>{m.etiqueta ?? legible(clave)}</td>
                <td>
                  <VistaEstado estado={m.estado} motivo={m.estado === "estimable" ? null : m.motivo} />
                </td>
                <td className="text-end">{m.n ?? "—"}</td>
                <td className="text-end">{formatearCifra(m.media)}</td>
                <td className="text-nowrap">
                  {m.intervalo ? `[${formatearCifra(m.intervalo[0])}, ${formatearCifra(m.intervalo[1])}]` : "sin intervalo"}
                </td>
                <td>{m.lectura ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </TablaDesplazable>
      {c.extremos && (c.extremos.fuertes || c.extremos.debiles) ? (
        <p className="small mb-1">
          <VistaExtremo nombre="Más probables" x={c.extremos.fuertes} />
          <VistaExtremo nombre="Menos probables" x={c.extremos.debiles} />
        </p>
      ) : null}
      <details className="small">
        <summary>Remuestreo (bootstrap de bloques)</summary>
        <ul className="mb-1">
          {metricas.map(([clave, m]) => (
            <li key={clave}>
              {m.etiqueta ?? legible(clave)}:{" "}
              {m.bloque !== null
                ? `bloque ${m.bloque} · ${m.remuestreos ?? "—"} remuestras · nivel ${m.nivel ?? "—"} · semilla ${m.semilla ?? "—"} · error estándar bootstrap ${formatearCifra(m.error_estandar_bootstrap)}`
                : "sin remuestreo"}
            </li>
          ))}
        </ul>
        {c.identidad_remuestreo ? <p className="mb-0 text-muted">{c.identidad_remuestreo.motivo ?? ""}</p> : null}
      </details>
    </div>
  );
}

/** Una evaluacion (seguimiento, retrospectiva o receta) con su muestra y sus componentes. */
export function EvaluacionCompleta({ ev, titulo }: { ev: EvaluacionDeFiabilidad; titulo: string }) {
  return (
    <section className="border rounded p-2 mb-3" data-evaluacion={ev.tipo} data-estado={ev.estado} aria-label={titulo}>
      <h4 className="h6 mb-1">
        {titulo}: <VistaEstado estado={ev.estado} motivo={ev.motivo} />
      </h4>
      {ev.descripcion ? <p className="small text-muted mb-1">{ev.descripcion}</p> : null}
      {ev.tipo === "evaluacion_de_receta" ? (
        <p className="small mb-1">
          {ev.origen ? `Origen: ${ev.origen}. ` : ""}
          {ev.informe ? (
            <>
              Informe <Huella valor={ev.informe} />
              {ev.corte_del_informe !== null ? ` (corte ${ev.corte_del_informe})` : ""}.
            </>
          ) : null}
        </p>
      ) : null}
      <VistaMuestra m={ev.muestra} />
      {componentesOrdenados(ev).map(([nombre, c]) => (
        <VistaComponente key={nombre} nombre={nombre} c={c} tipo={ev.tipo} />
      ))}
    </section>
  );
}

export function VistaMetodoDeFiabilidad({ m }: { m: MetodoDeFiabilidad }) {
  return (
    <details className="small mb-3" data-metodo-fiabilidad={m.version}>
      <summary>Método ({m.version}), supuestos y limitaciones</summary>
      <dl className="row mb-1 mt-2">
        <dt className="col-sm-3">Unidad</dt>
        <dd className="col-sm-9">{m.unidad}</dd>
        <dt className="col-sm-3">Estimación</dt>
        <dd className="col-sm-9">{m.estimacion}</dd>
        <dt className="col-sm-3">Incertidumbre</dt>
        <dd className="col-sm-9">{m.incertidumbre}</dd>
        <dt className="col-sm-3">Mínimo para el intervalo</dt>
        <dd className="col-sm-9">{m.minimo_para_intervalo} sorteos</dd>
        <dt className="col-sm-3">Extremos por sorteo</dt>
        <dd className="col-sm-9">
          {Object.entries(m.extremos)
            .map(([k, v]) => `${COMPONENTES_FIABILIDAD[k] ?? legible(k)}: ${v}`)
            .join(" · ")}
        </dd>
        <dt className="col-sm-3">Supuestos</dt>
        <dd className="col-sm-9">{m.supuestos}</dd>
        <dt className="col-sm-3">Presentación</dt>
        <dd className="col-sm-9">
          {m.presentacion.criterio} {m.presentacion.formato}
        </dd>
      </dl>
      <p className="mb-1">Limitaciones:</p>
      <ul>
        {m.limitaciones.map((x) => (
          <li key={x}>{x}</li>
        ))}
      </ul>
      <p className="mb-1">Fuentes:</p>
      <ul className="mb-0">
        {m.fuentes.map((x) => (
          <li key={x.cita}>
            {x.cita}
            {x.doi ? ` DOI ${x.doi}.` : ""} <span className="text-muted">Uso: {x.uso}.</span>
          </li>
        ))}
      </ul>
    </details>
  );
}

/** Lineas de la configuracion con sus dos tipos por separado, y la receta aparte. */
export function FiabilidadCompleta({ f }: { f: Fiabilidad }) {
  return (
    <>
      {f.lineas.length === 0 ? (
        <p className="small text-muted">Sin líneas que evaluar: el juego no tiene configuración de predicción vigente.</p>
      ) : null}
      {f.lineas.map((l) => (
        <section className="card stat-card p-3 mb-3" key={l.linea} data-linea={l.linea} aria-label={l.nombre}>
          <h3 className="h5 mb-1">{l.nombre}</h3>
          <p className="small text-muted mb-2">
            <code>{l.linea}</code> · {l.papel} · {l.estimador}
          </p>
          {l.evaluaciones.map((ev) => (
            <Fragment key={ev.tipo}>
              <EvaluacionCompleta ev={ev} titulo={TIPOS_FIABILIDAD[ev.tipo] ?? legible(ev.tipo)} />
            </Fragment>
          ))}
        </section>
      ))}
      <section className="card stat-card p-3 mb-3" data-receta={f.receta.estado} aria-label="Evaluación de la receta">
        <h3 className="h5 mb-1">{TIPOS_FIABILIDAD.evaluacion_de_receta}</h3>
        <EvaluacionCompleta ev={f.receta} titulo="Receta en su informe" />
      </section>
    </>
  );
}
