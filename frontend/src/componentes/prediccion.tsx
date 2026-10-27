/**
 * Fase 9.3: clasificacion de candidatos y explicacion guardada de una prediccion.
 * Presenta lo que envia la API (rankings ya ordenados con su referencia
 * uniforme, explicacion verificada por su almacen): no recalcula probabilidades,
 * posiciones, variables ni importancias. Las graficas de la consola HTMX se
 * sustituyen por sus tablas.
 */
import { especificacion, fechaHora } from "../api/formatos";
import type {
  Candidato,
  Explicacion,
  FilaDeRanking,
  Prediccion,
  Rankings,
  SeccionDeRanking,
} from "../api/presentacion";
import { ArbolDeDatos, Color, Huella, Numeros, ParColor, TablaDesplazable } from "./comunes";

const legible = (texto: string) => texto.replaceAll("_", " ");

export function VerCandidato({ c }: { c: Candidato }) {
  if (Array.isArray(c)) {
    return <ParColor numero={c[0]} color={c[1]} />;
  }
  return typeof c === "string" ? <Color color={c} /> : <Numeros numeros={[c]} />;
}

function clave(c: Candidato): string {
  return Array.isArray(c) ? `${c[0]}|${c[1]}` : String(c);
}

/** Tabla de un ranking: emitida, referencia uniforme, diferencia y razon (formatos de la consola). */
export function TablaDeRanking({
  titulo,
  filas,
  unidad,
  multiplicidad = false,
  id,
}: {
  titulo: string;
  filas: FilaDeRanking[];
  unidad: string;
  multiplicidad?: boolean;
  id: string;
}) {
  return (
    <div className="mb-3" data-ranking={id}>
      <h4 className="h6 mb-1">{titulo}</h4>
      <p className="small text-muted mb-1">
        {unidad}. Emitida: probabilidad del modelo; uniforme: referencia; diferencia: emitida − uniforme; razón: emitida /
        uniforme{multiplicidad ? "; en 6 balotas: multiplicidad esperada = 6 × emitida" : ""}.
      </p>
      <TablaDesplazable etiqueta={titulo}>
        <table className="table table-sm small mb-0">
          <thead>
            <tr>
              <th scope="col" className="text-end">
                Pos.
              </th>
              <th scope="col">Candidato</th>
              <th scope="col" className="text-end">
                Emitida
              </th>
              <th scope="col" className="text-end">
                Uniforme
              </th>
              <th scope="col" className="text-end">
                Diferencia
              </th>
              <th scope="col" className="text-end">
                Razón
              </th>
              {multiplicidad ? (
                <th scope="col" className="text-end">
                  En 6 balotas
                </th>
              ) : null}
            </tr>
          </thead>
          <tbody>
            {filas.map((f) => (
              <tr key={`${f.posicion}-${clave(f.candidato)}`}>
                <td className="text-end">{f.posicion}</td>
                <td>
                  <VerCandidato c={f.candidato} />
                </td>
                <td className="text-end">{especificacion(f.probabilidad, ".6f")}</td>
                <td className="text-end">{especificacion(f.uniforme, ".6f")}</td>
                <td className="text-end">{especificacion(f.diferencia, "+.6f")}</td>
                <td className="text-end">{f.razon === null ? "—" : especificacion(f.razon, ".3f")}</td>
                {multiplicidad ? <td className="text-end">{especificacion(f.multiplicidad_esperada, ".4f")}</td> : null}
              </tr>
            ))}
          </tbody>
        </table>
      </TablaDesplazable>
    </div>
  );
}

function Empates({ s }: { s: SeccionDeRanking }) {
  return s.nota_empates ? (
    <p className="small text-muted">
      <strong>{s.nota_empates}</strong>
    </p>
  ) : null;
}

/** Fuertes, debiles y universo completo de una seccion; el universo va plegado. */
function Seccion({
  s,
  nombre,
  id,
  multiplicidad = false,
  universo,
}: {
  s: SeccionDeRanking;
  nombre: string;
  id: string;
  multiplicidad?: boolean;
  universo: string;
}) {
  const unidad = `${s.unidad}; ${s.denominador}`;
  return (
    <>
      {s.fuertes && s.debiles ? (
        <div className="row g-3">
          <div className="col-lg-6">
            <TablaDeRanking titulo={`${nombre} más probables (${s.por_extremo ?? s.fuertes.length} de ${universo})`} filas={s.fuertes} unidad={unidad} multiplicidad={multiplicidad} id={`${id}-fuertes`} />
          </div>
          <div className="col-lg-6">
            <TablaDeRanking titulo={`${nombre} menos probables (${s.por_extremo ?? s.debiles.length} de ${universo})`} filas={s.debiles} unidad={unidad} multiplicidad={multiplicidad} id={`${id}-debiles`} />
          </div>
        </div>
      ) : null}
      <details className="small mb-2">
        <summary>
          {nombre}: universo completo ({s.universo}), de mayor a menor probabilidad emitida
        </summary>
        <TablaDeRanking titulo={`${nombre}: universo completo`} filas={s.todos} unidad={unidad} multiplicidad={multiplicidad} id={`${id}-todos`} />
      </details>
      {s.suma !== null || s.nota ? (
        <p className="small text-muted mb-1">
          {s.nota ? `${s.nota} ` : ""}
          {s.suma !== null ? `Suma de las probabilidades: ${especificacion(s.suma, ".6f")}.` : ""}
        </p>
      ) : null}
      <Empates s={s} />
    </>
  );
}

/** Clasificacion de candidatos: numeros (y superbalota aparte) o pares numero-color de ColorLoto. */
export function Clasificacion({ rankings: r }: { rankings: Rankings }) {
  return (
    <section className="card stat-card p-3 mb-3" aria-labelledby="titulo-clasificacion" data-clasificacion={r.pares ? "pares" : "numeros"}>
      <h3 className="h5 mb-1" id="titulo-clasificacion">
        Clasificación de candidatos (fuertes y débiles)
      </h3>
      <p className="small text-muted mb-2">
        {r.aviso} Objetivo {r.objetivo}, con datos hasta el sorteo {r.corte}. La clasificación es la que envía la API; la
        interfaz no la recalcula.
      </p>
      {r.pares ? (
        <>
          <Seccion s={r.pares} nombre="Pares" id="pares" multiplicidad universo={r.pares.denominador} />
          <div className="row g-3">
            <div className="col-lg-6">
              <TablaDeRanking titulo={`Números por separado (${r.numeros.denominador})`} filas={r.numeros.todos} unidad={r.numeros.unidad} multiplicidad id="numeros-colorloto" />
              <Empates s={r.numeros} />
            </div>
            {r.colores ? (
              <div className="col-lg-6">
                <TablaDeRanking titulo={`Colores por separado (${r.colores.denominador})`} filas={r.colores.todos} unidad={r.colores.unidad} multiplicidad id="colores-colorloto" />
                <Empates s={r.colores} />
              </div>
            ) : null}
          </div>
        </>
      ) : (
        <Seccion s={r.numeros} nombre="Números" id="numeros" universo={String(r.numeros.universo)} />
      )}
      {r.superbalota ? (
        <div className="border-top pt-2 mt-2" data-superbalota="aparte">
          <h4 className="h6">Superbalota (sección separada)</h4>
          <TablaDeRanking
            titulo={`Superbalota (${r.superbalota.denominador})`}
            filas={r.superbalota.todos}
            unidad={`${r.superbalota.unidad}${r.superbalota.nota ? `. ${r.superbalota.nota}` : ""}`}
            id="superbalota"
          />
          <p className="small text-muted">
            Más probables: {(r.superbalota.fuertes ?? []).map((f) => String(f.candidato)).join(", ") || "—"} · menos probables:{" "}
            {(r.superbalota.debiles ?? []).map((f) => String(f.candidato)).join(", ") || "—"}.
            {r.superbalota.estrategia ? ` Estrategia: ${legible(r.superbalota.estrategia)}.` : ""}
          </p>
          <Empates s={r.superbalota} />
        </div>
      ) : null}
    </section>
  );
}

function CortesYEntrenamiento({ p, e }: { p: Prediccion; e: Explicacion | null }) {
  const entrenamiento = e?.metodo.entrenamiento ?? null;
  const registrado = e?.metodo.registrado ?? null;
  const corteEntrenamiento = entrenamiento?.corte_de_entrenamiento ?? registrado?.corte_de_entrenamiento ?? null;
  return (
    <TablaDesplazable etiqueta="Cortes de entrada y de entrenamiento">
      <table className="table table-sm small mb-2" data-cortes="separados">
        <thead>
          <tr>
            <th scope="col">Corte</th>
            <th scope="col" className="text-end">
              Sorteo
            </th>
            <th scope="col">Qué significa</th>
          </tr>
        </thead>
        <tbody>
          <tr data-corte="entrada">
            <td>Entrada de la predicción</td>
            <td className="text-end">{p.corte ?? "—"}</td>
            <td>Último sorteo del histórico con el que se emitió la cartera (objetivo {p.objetivo}).</td>
          </tr>
          <tr data-corte="vector-fuente">
            <td>Vector fuente y variables</td>
            <td className="text-end">{e ? e.metodo.corte : "—"}</td>
            <td>{e ? "Probabilidades y variables calculadas solo con los sorteos hasta este corte." : "Sin explicación guardada: no informado."}</td>
          </tr>
          <tr data-corte="entrenamiento">
            <td>Entrenamiento del estimador</td>
            <td className="text-end">{corteEntrenamiento ?? "—"}</td>
            <td>
              {corteEntrenamiento !== null
                ? "Versión registrada congelada: se ajustó con este corte y se recargó sin reentrenar."
                : entrenamiento
                  ? `No hay un corte de entrenamiento aparte: ${entrenamiento.estimador}.`
                  : "No informado (sin explicación guardada)."}
            </td>
          </tr>
        </tbody>
      </table>
    </TablaDesplazable>
  );
}

function Metodo({ p, e }: { p: Prediccion; e: Explicacion }) {
  const m = e.metodo;
  const periodo = m.entrenamiento?.periodo ?? null;
  return (
    <dl className="row small mb-2" data-metodo={m.modelo}>
      <dt className="col-sm-3">Familia y receta</dt>
      <dd className="col-sm-9">
        {m.nombre} · <code>{m.modelo}</code> · familia {m.familia}
        {m.tipo ? ` · tipo ${m.tipo}` : ""} · receta v{m.version_de_la_receta} · perfil {m.perfil} · salida {legible(m.salida)}
      </dd>
      <dt className="col-sm-3">Versión registrada</dt>
      <dd className="col-sm-9" data-registrado={m.registrado ? m.registrado.numero : "ninguna"}>
        {m.registrado ? (
          <>
            versión {m.registrado.numero} · clave <Huella valor={m.registrado.clave} /> · estimador <Huella valor={m.registrado.sha256_estimador} />
          </>
        ) : p.registrado ? (
          <>
            versión {p.registrado.numero} · clave <Huella valor={p.registrado.clave} />
          </>
        ) : (
          "ninguna: la cartera no usa una versión registrada"
        )}
      </dd>
      <dt className="col-sm-3">Variables del método</dt>
      <dd className="col-sm-9">
        {m.variables ? `${m.variables.version}: ${m.variables.nombres.join(", ")}` : "no informadas"}
        {m.variables?.descripcion ? <span className="d-block text-muted">{m.variables.descripcion}</span> : null}
      </dd>
      <dt className="col-sm-3">Transformación de salida</dt>
      <dd className="col-sm-9">
        {m.transformacion ? `${legible(m.transformacion.tipo)}${m.transformacion.detalle ? `: ${m.transformacion.detalle}` : ""}` : "no informada"}
      </dd>
      <dt className="col-sm-3">Entrenamiento</dt>
      <dd className="col-sm-9">
        {m.entrenamiento ? m.entrenamiento.estimador : "no informado"}
        {periodo ? (
          <div className="text-muted">
            Periodo de entrenamiento: <ArbolDeDatos datos={periodo} profundidad={1} />
          </div>
        ) : null}
      </dd>
      {m.pesos ? (
        <>
          <dt className="col-sm-3">Pesos de la mezcla</dt>
          <dd className="col-sm-9">{m.pesos.map((w) => `${w.componente} ${especificacion(w.peso, ".1f")}`).join(" · ")}</dd>
        </>
      ) : null}
      {m.parametros || m.entrenamiento?.parametros_ajustados ? (
        <>
          <dt className="col-sm-3">Parámetros</dt>
          <dd className="col-sm-9">
            <details>
              <summary>Parámetros de la receta{m.entrenamiento?.parametros_ajustados ? " y ajustados" : ""}</summary>
              {m.parametros ? <ArbolDeDatos datos={m.parametros} profundidad={1} /> : null}
              {m.entrenamiento?.parametros_ajustados ? <ArbolDeDatos datos={m.entrenamiento.parametros_ajustados} profundidad={1} /> : null}
            </details>
          </dd>
        </>
      ) : null}
    </dl>
  );
}

function VistaImportancias({ e }: { e: Explicacion }) {
  const imp = e.importancias;
  if (imp.estado !== "disponible" || !imp.valores) {
    return (
      <p className="small mb-2" data-importancias="no_disponible">
        <strong>Importancias no disponibles:</strong> {imp.motivo ?? "no informado"}
      </p>
    );
  }
  const coeficiente = imp.tipo === "coeficiente";
  return (
    <div data-importancias="disponible">
      <p className="small text-muted mb-1">
        {imp.descripcion} Estimador {imp.estimador ?? "—"}
        {imp.calibrado ? " (bajo una calibración sigmoide)" : ""}. {imp.aviso}
      </p>
      <TablaDesplazable etiqueta="Importancias o coeficientes globales del estimador">
        <table className="table table-sm small mb-2">
          <thead>
            <tr>
              <th scope="col">Variable</th>
              <th scope="col" className="text-end">
                {coeficiente ? "Coeficiente" : "Importancia"}
              </th>
              <th scope="col" className="text-end">
                Columnas
              </th>
            </tr>
          </thead>
          <tbody>
            {imp.valores.map((v) => (
              <tr key={v.variable}>
                <td>
                  {legible(v.variable)}
                  {v.es_identidad ? " (identidad del candidato)" : ""}
                </td>
                <td className="text-end">
                  {v.valor !== null
                    ? especificacion(v.valor, ".6f")
                    : v.resumen
                      ? `mín ${especificacion(v.resumen.minimo, ".4f")} · máx ${especificacion(v.resumen.maximo, ".4f")} · media |·| ${especificacion(v.resumen.media_absoluta, ".4f")}`
                      : "—"}
                </td>
                <td className="text-end">{v.columnas}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </TablaDesplazable>
    </div>
  );
}

/** Valores de las variables de los candidatos extremos (como la consola): contexto, no atribucion. */
function VariablesDeExtremos({ e, r }: { e: Explicacion; r: Rankings }) {
  const va = e.variables;
  const principal = r.pares ?? r.numeros;
  if (!va || !principal.fuertes || !principal.debiles) {
    return <p className="small text-muted">Variables de los candidatos no informadas por la explicación.</p>;
  }
  const grupos: [string, FilaDeRanking[]][] = [
    ["fuerte", principal.fuertes],
    ["débil", principal.debiles],
  ];
  return (
    <>
      <p className="small text-muted mb-1">
        Valor emitido, referencia y variables calculadas solo con los sorteos hasta el corte ({va.calculado_hasta_sorteo}).{" "}
        {va.nota} {va.usadas_por_el_modelo ? "" : "No son entradas de este método. "}No es una atribución por candidato: las
        importancias son globales.
      </p>
      <TablaDesplazable etiqueta="Variables de los candidatos fuertes y débiles">
        <table className="table table-sm small mb-0" data-variables={va.usadas_por_el_modelo ? "usadas" : "contexto"}>
          <thead>
            <tr>
              <th scope="col">Extremo</th>
              <th scope="col">Candidato</th>
              <th scope="col" className="text-end">
                Emitida
              </th>
              <th scope="col" className="text-end">
                Uniforme
              </th>
              {va.nombres.map((n) => (
                <th scope="col" className="text-end" key={n}>
                  {legible(n)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {grupos.flatMap(([grupo, filas]) =>
              filas.map((f) => (
                <tr key={`${grupo}-${f.posicion}`}>
                  <td>
                    {grupo} {f.posicion}
                  </td>
                  <td>
                    <VerCandidato c={f.candidato} />
                  </td>
                  <td className="text-end">{especificacion(f.probabilidad, ".5f")}</td>
                  <td className="text-end">{especificacion(f.uniforme, ".5f")}</td>
                  {(va.por_candidato[clave(f.candidato)] ?? []).map((x, i) => (
                    <td className="text-end" key={i}>
                      {especificacion(x, ".4g")}
                    </td>
                  ))}
                </tr>
              )),
            )}
          </tbody>
        </table>
      </TablaDesplazable>
    </>
  );
}

/** Explicacion guardada de la prediccion, o su ausencia; la API nunca la genera al consultar. */
export function VistaExplicacion({ p }: { p: Prediccion }) {
  const e = p.explicacion;
  return (
    <section className="card stat-card p-3 mb-3" aria-labelledby="titulo-explicacion" data-explicacion={e ? "guardada" : "ausente"}>
      <h3 className="h5 mb-1" id="titulo-explicacion">
        Explicación
      </h3>
      {p.explicaciones_ilegibles.length > 0 ? (
        <div className="alert alert-danger small py-2" role="alert" data-explicacion-ilegible={p.explicaciones_ilegibles.length}>
          {p.explicaciones_ilegibles.length === 1 ? "Una explicación guardada no se muestra" : `${p.explicaciones_ilegibles.length} explicaciones guardadas no se muestran`}{" "}
          porque su almacén no la verifica:{" "}
          {p.explicaciones_ilegibles.map((x) => (
            <span key={x.clave} className="d-block">
              <Huella valor={x.clave} /> · {legible(x.motivo)}
            </span>
          ))}
        </div>
      ) : null}
      {e ? (
        <>
          <p className="small text-muted mb-2">
            Explicación <Huella valor={e.clave} /> (versión {e.version}), guardada {fechaHora(e.generacion?.generado_en)} UTC
            {e.generacion?.nota ? ` (${e.generacion.nota})` : ""}.{" "}
            {p.reproduccion
              ? p.reproduccion.exacta
                ? "La API recalculó rankings y variables desde la cartera y coinciden con los guardados."
                : `La API no reproduce la explicación: ${p.reproduccion.motivo ?? `difieren ${p.reproduccion.distintos.join(", ")}`}.`
              : ""}
          </p>
          <Metodo p={p} e={e} />
        </>
      ) : (
        <p className="small mb-2" data-explicacion-ausente="">
          Esta predicción no tiene una explicación guardada vigente. La API no la genera al consultar; se genera desde la consola
          local. La clasificación de candidatos sigue siendo la del vector fuente de la cartera.
        </p>
      )}
      <h4 className="h6">Cortes</h4>
      <CortesYEntrenamiento p={p} e={e} />
      {e ? (
        <>
          <h4 className="h6">Importancias o coeficientes globales del estimador</h4>
          <VistaImportancias e={e} />
          {p.rankings ? (
            <>
              <h4 className="h6">Variables de los candidatos extremos</h4>
              <VariablesDeExtremos e={e} r={p.rankings} />
            </>
          ) : null}
          <ul className="small text-muted mt-2 mb-0">
            {e.avisos.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}
