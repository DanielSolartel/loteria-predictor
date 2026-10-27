/**
 * Fiabilidad observada de las predicciones (Fase 9.3; GET
 * /juegos/{codigo}/fiabilidad?hasta=...). Sin `hasta`, con todos los resultados
 * observados en la base consultada; con `hasta`, solo los objetivos hasta ese
 * sorteo. Seguimiento, retrospectiva y evaluacion de la receta van por separado.
 * Consulta general de la configuracion actual, no de una cartera identificada.
 * Presupuesto con memoria vacia: catalogo (1) + fiabilidad (3) = 4 fichas.
 */
import { Link, useParams } from "react-router-dom";
import { consultar, rutaApi } from "../api/cliente";
import { decFiabilidad, type Fiabilidad as FiabilidadDatos } from "../api/presentacion";
import { ArbolDeDatos, AvisoExperimental, Huella } from "../componentes/comunes";
import { Consulta } from "../componentes/Estados";
import { FiabilidadCompleta, LeyendaDeFiabilidad, VistaMetodoDeFiabilidad } from "../componentes/fiabilidad";
import { FormularioDeCorte, useFiltros } from "../componentes/Filtros";
import { PestanasDeJuego } from "../componentes/Marco";
import { useConsulta } from "../usos/consulta";

const legible = (texto: string) => texto.replaceAll("_", " ");

function Cabecera({ f, codigo }: { f: FiabilidadDatos; codigo: string }) {
  const b = f.base;
  return (
    <div className="card stat-card p-3 mb-3" data-base-fiabilidad={b.estado} data-hasta={f.hasta ?? "todos"}>
      <dl className="row small mb-0">
        <dt className="col-sm-4">Evidencia</dt>
        <dd className="col-sm-8">
          {f.hasta === null
            ? "Todos los resultados observados en la base consultada."
            : `Solo objetivos hasta el sorteo ${f.hasta}. Este filtro no acredita que los informes o emisiones existieran al generar una cartera.`}
        </dd>
        <dt className="col-sm-4">Base consultada</dt>
        <dd className="col-sm-8">
          {b.estado === "consultada"
            ? `respondió · último sorteo ${b.ultimo_sorteo ?? "—"} (${b.fecha ?? "—"}) · ${b.sorteos ?? "—"} sorteos`
            : b.estado === "no_disponible"
              ? "no disponible: no se sabe si las emisiones tienen resultado"
              : legible(b.estado)}
          <span className="d-block text-muted">
            Que la base responda no significa que los datos estén al día; un resultado ausente se muestra como pendiente y no se deduce que el
            sorteo no haya ocurrido.
          </span>
        </dd>
        <dt className="col-sm-4">Configuración de predicción</dt>
        <dd className="col-sm-8" data-configuracion={f.configuracion}>
          {legible(f.configuracion)}
        </dd>
        <dt className="col-sm-4">Versión registrada</dt>
        <dd className="col-sm-8">
          {f.registrado ? (
            <>
              versión {f.registrado.numero} ({legible(f.registrado.estado)}) · <Huella valor={f.registrado.clave} />
            </>
          ) : (
            "ninguna"
          )}
        </dd>
      </dl>
      <p className="small mb-0 mt-2">
        <Link to={`/juegos/${encodeURIComponent(codigo)}/prediccion`}>Predicción guardada</Link> (su fiabilidad requiere consulta
        explícita y correspondencia con la cartera seleccionada)
      </p>
    </div>
  );
}

export function Fiabilidad() {
  const { codigo = "" } = useParams();
  const [{ hasta }, cambiar] = useFiltros(["hasta"] as const);
  const url = rutaApi(["juegos", codigo, "fiabilidad"], { hasta });
  const [estado, reintentar] = useConsulta(url, (s) => consultar(url, decFiabilidad, s));
  return (
    <>
      <PestanasDeJuego codigo={codigo} />
      <h1 className="h3">Fiabilidad observada</h1>
      <p className="small text-muted">Consulta general de la configuración actual del juego; no acredita por sí sola la fiabilidad de una cartera histórica.</p>
      <FormularioDeCorte key={hasta ?? ""} valor={hasta} aplicar={(v) => cambiar({ hasta: v })} />
      <Consulta estado={estado} reintentar={reintentar} que="la fiabilidad observada">
        {(f) => (
          <>
            <AvisoExperimental estadoDeUso={f.estado_de_uso}>{f.aviso}</AvisoExperimental>
            <details className="small mb-3">
              <summary>Contexto informado por la API</summary>
              <ArbolDeDatos datos={f.contexto} />
            </details>
            <Cabecera f={f} codigo={codigo} />
            <LeyendaDeFiabilidad />
            <VistaMetodoDeFiabilidad m={f.metodo} />
            <FiabilidadCompleta f={f} />
          </>
        )}
      </Consulta>
    </>
  );
}
