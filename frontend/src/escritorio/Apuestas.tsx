import { useState, type FormEvent } from "react";
import { consultar, rutaApi } from "../api/cliente";
import { booleano, decodificar, entero, lista, nulable, objeto, texto } from "../api/decodificar";
import { fechaHora } from "../api/formatos";
import { decError, decResultado, type Combinacion, type Juego, type Prediccion } from "../api/presentacion";
import { TablaDesplazable, VerResultado } from "../componentes/comunes";
import { Consulta } from "../componentes/Estados";
import { useConsulta } from "../usos/consulta";

export type SeleccionDeApuesta = { juego: Juego; prediccion: Prediccion; linea: Combinacion; versionCartera: number | null };

const ruta = ["escritorio", "apuestas"];
const decGuardada = objeto({ id: texto });
const decParticipacion = objeto({
  juego: texto, sorteo: entero, resultado: nulable(decResultado), aciertos: nulable(entero),
  numeros_acertados: nulable(lista(entero)), superbalota: nulable(booleano),
});
const decApuesta = objeto({
  id: texto, registrada_en: texto, combinacion: decResultado, participaciones: lista(decParticipacion),
  origen: objeto({ cartera: texto, linea: entero, juego: texto, sorteo: entero, version_cartera: entero, modelo: texto }),
});
const decApuestas = objeto({ apuestas: lista(decApuesta), pagina: entero, paginas: entero });

export function FormularioApuesta({ seleccion, juegos, parejas, guardar, cancelar }: {
  seleccion: SeleccionDeApuesta; juegos: Juego[]; parejas: Record<string, string>;
  guardar: () => void; cancelar: () => void;
}) {
  const { juego, prediccion, linea, versionCartera } = seleccion;
  const [solicitud] = useState(() => crypto.randomUUID());
  const [guardando, fijarGuardando] = useState(false);
  const [error, fijarError] = useState<string | null>(null);
  const pareja = juegos.find((j) => j.codigo === parejas[juego.codigo]);
  const elegibles = pareja ? [juego, pareja] : [juego];

  async function confirmar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (guardando) return;
    const formulario = new FormData(evento.currentTarget);
    const destinos = formulario.getAll("juegos").map(String);
    if (destinos.length === 0) {
      fijarError("Elige al menos un juego en el que usaste esta combinación.");
      return;
    }
    fijarError(null);
    fijarGuardando(true);
    try {
      const respuesta = await fetch(rutaApi(ruta), {
        method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
        credentials: "same-origin", cache: "no-store", redirect: "error", referrerPolicy: "no-referrer",
        body: JSON.stringify({ solicitud, cartera: prediccion.clave, linea: linea.linea,
          sorteo: Number(formulario.get("sorteo")), juegos: destinos }),
      });
      const contenido: unknown = await respuesta.json();
      if (!respuesta.ok) {
        fijarError(decodificar(decError, contenido).error.mensaje);
        return;
      }
      decodificar(decGuardada, contenido);
      guardar();
    } catch {
      fijarError("No se pudo confirmar el guardado. Puedes volver a intentarlo desde este formulario.");
    } finally {
      fijarGuardando(false);
    }
  }

  return <form className="visor-panel" onSubmit={confirmar}>
    <h3>Registrar apuesta</h3>
    <p className="mb-2">{prediccion.modelo.nombre ?? prediccion.modelo.id} · {juego.nombre}
      {versionCartera !== null && ` · cartera v${versionCartera}`} · línea {linea.linea}</p>
    <VerResultado resultado={linea.resultado} />
    <fieldset disabled={guardando} className="mt-3">
      <legend className="fs-6 fw-semibold">Juegos en los que usaste la combinación</legend>
      <div className="d-flex flex-wrap gap-3 mb-3">{elegibles.map((j) => <label key={j.codigo} className="d-flex align-items-center gap-2">
        <input className="form-check-input m-0" type="checkbox" name="juegos" value={j.codigo} defaultChecked={j.codigo === juego.codigo} />
        {j.nombre}
      </label>)}</div>
      <div className="visor-filtros"><label>Sorteo<input className="form-control" name="sorteo" type="number"
        min="1" max="2147483647" step="1" defaultValue={prediccion.objetivo} required /></label></div>
    </fieldset>
    {error && <p className="alert alert-warning" role="alert">{error}</p>}
    <div className="d-flex gap-2 flex-wrap">
      <button className="btn btn-marca" type="submit" disabled={guardando}>{guardando ? "Guardando…" : "Guardar apuesta"}</button>
      <button className="btn btn-outline-secondary" type="button" disabled={guardando} onClick={cancelar}>Cancelar</button>
    </div>
  </form>;
}

export function MisApuestas({ juegos }: { juegos: Juego[] }) {
  const [pagina, cambiarPagina] = useState(1);
  const url = rutaApi(ruta, { pagina: String(pagina) });
  const [estado, reintentar] = useConsulta(url, (s) => consultar(url, decApuestas, s));
  const nombre = (codigo: string) => juegos.find((j) => j.codigo === codigo)?.nombre ?? codigo;

  return <Consulta estado={estado} reintentar={reintentar} que="tus apuestas">{(datos) => {
    if (datos.apuestas.length === 0) return <p>Aún no hay apuestas registradas. Elige una línea en Predicciones o Historial de aciertos.</p>;
    return <div className="d-grid gap-3">
      <div><button type="button" className="btn btn-outline-secondary" onClick={reintentar}>Recargar resultados</button></div>
      {datos.apuestas.map((a) => <article className="visor-panel" key={a.id}>
        <h3>{a.origen.modelo}</h3>
        <p className="text-body-secondary mb-2">Origen {nombre(a.origen.juego)} · objetivo {a.origen.sorteo} · cartera v{a.origen.version_cartera} · {a.origen.cartera.slice(0, 8)} · línea {a.origen.linea}</p>
        <VerResultado resultado={a.combinacion} />
        <p className="text-body-secondary small mt-2">Registrada el {fechaHora(a.registrada_en)}</p>
        <TablaDesplazable etiqueta="Resultados por juego de la apuesta"><table className="table mb-0 align-middle">
          <thead><tr><th scope="col">Juego</th><th scope="col">Sorteo</th><th scope="col">Resultado</th><th scope="col">Aciertos</th></tr></thead>
          <tbody>{a.participaciones.map((p) => <tr key={p.juego}>
            <th scope="row">{nombre(p.juego)}</th><td>{p.sorteo}</td>
            <td>{p.resultado ? <VerResultado resultado={p.resultado} /> : "—"}</td>
            <td>{p.aciertos === null ? "Pendiente" : <>
              {p.aciertos} / {"pares" in a.combinacion ? a.combinacion.pares.length : a.combinacion.numeros.length}
              {p.numeros_acertados?.length ? <span className="d-block small">{p.numeros_acertados.join(", ")}</span> : null}
              {p.superbalota !== null && <span className="d-block small">Superbalota {p.superbalota ? "acertada" : "sin acierto"}</span>}
            </>}</td>
          </tr>)}</tbody>
        </table></TablaDesplazable>
      </article>)}
      {datos.paginas > 1 && <div className="visor-paginacion" aria-label="Páginas de apuestas">
        <button className="btn btn-outline-secondary btn-sm" disabled={pagina === 1} onClick={() => cambiarPagina(pagina - 1)}>Anterior</button>
        <span>Página {pagina} de {datos.paginas}</span>
        <button className="btn btn-outline-secondary btn-sm" disabled={pagina >= datos.paginas} onClick={() => cambiarPagina(pagina + 1)}>Siguiente</button>
      </div>}
    </div>;
  }}</Consulta>;
}
