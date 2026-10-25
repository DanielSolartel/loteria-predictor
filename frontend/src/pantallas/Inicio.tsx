/** Inicio: los cuatro juegos con sus reglas (GET /api/v1/juegos, en memoria). */
import { Link } from "react-router-dom";
import { obtenerJuegos } from "../api/cliente";
import type { Juego } from "../api/presentacion";
import { Consulta } from "../componentes/Estados";
import { useConsulta } from "../usos/consulta";

export function reglasDe(j: Juego): string {
  const repeticion = j.permite_repeticion ? "con repetición" : "sin repetición";
  const color = j.tiene_color ? " con color" : "";
  const superbalota =
    j.tiene_superbalota && j.superbalota_min !== null && j.superbalota_max !== null
      ? ` + superbalota de ${j.superbalota_min} a ${j.superbalota_max}`
      : ", sin superbalota";
  return `${j.cantidad_numeros} números${color} de ${j.rango_min} a ${j.rango_max}, ${repeticion}${superbalota}.`;
}

export function Inicio() {
  const [estado, reintentar] = useConsulta("juegos", obtenerJuegos);
  return (
    <>
      <h1 className="h3">Juegos</h1>
      <p className="text-muted small">
        Consulta de sorteos, estadísticas descriptivas, predicciones y simulaciones guardadas. Solo lectura.
      </p>
      <Consulta estado={estado} reintentar={reintentar} que="los juegos">
        {(juegos) => (
          <div className="row g-3">
            {juegos.map((j) => (
              <div className="col-12 col-md-6" key={j.codigo}>
                <div className="card stat-card p-3 h-100">
                  <h2 className="h5 mb-1">
                    <Link to={`/juegos/${j.codigo}`}>{j.nombre}</Link>
                  </h2>
                  <p className="small text-muted mb-2">
                    Código <code>{j.codigo}</code>
                  </p>
                  <p className="mb-2">{reglasDe(j)}</p>
                  <ul className="list-inline small mb-0">
                    <li className="list-inline-item">
                      <Link to={`/juegos/${j.codigo}/sorteos`}>Sorteos</Link>
                    </li>
                    <li className="list-inline-item">
                      <Link to={`/juegos/${j.codigo}/estadisticas`}>Estadísticas</Link>
                    </li>
                    <li className="list-inline-item">
                      <Link to={`/juegos/${j.codigo}/prediccion`}>Predicción guardada</Link>
                    </li>
                    <li className="list-inline-item">
                      <Link to={`/juegos/${j.codigo}/simulaciones`}>Simulaciones</Link>
                    </li>
                  </ul>
                </div>
              </div>
            ))}
          </div>
        )}
      </Consulta>
    </>
  );
}
