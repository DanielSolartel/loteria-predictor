/** Marco comun: barra superior, salto al contenido, pestañas de juego y pie con el aviso. */
import { type ReactNode, useEffect, useRef } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { consolaLocal, obtenerConfiguracion, obtenerJuegos } from "../api/cliente";
import { useConsulta } from "../usos/consulta";

export function Marco({ children }: { children: ReactNode }) {
  const [juegos] = useConsulta("juegos", obtenerJuegos);
  const [configuracion] = useConsulta("configuracion", obtenerConfiguracion);
  const consola = configuracion.fase === "lista" ? consolaLocal(configuracion.datos.consola_local) : null;
  const { pathname } = useLocation();
  const principal = useRef<HTMLElement>(null);
  const primera = useRef(true);

  useEffect(() => {
    if (primera.current) {
      primera.current = false;
      return;
    }
    principal.current?.focus();
  }, [pathname]);

  return (
    <>
      <a className="salto" href="#contenido">
        Saltar al contenido
      </a>
      <header>
        <nav className="navbar navbar-expand navbar-dark topbar" aria-label="Principal">
          <div className="container-fluid flex-wrap">
            <Link className="navbar-brand" to="/">
              Lotería Predictor <span className="small text-white-50">· consulta</span>
            </Link>
            <ul className="navbar-nav flex-wrap">
              <li className="nav-item">
                <NavLink className="nav-link" to="/" end>
                  Inicio
                </NavLink>
              </li>
              {juegos.fase === "lista"
                ? juegos.datos.map((j) => (
                    <li className="nav-item" key={j.codigo}>
                      <NavLink className="nav-link" to={`/juegos/${j.codigo}`}>
                        {j.nombre}
                      </NavLink>
                    </li>
                  ))
                : null}
              <li className="nav-item">
                <NavLink className="nav-link" to="/servicio">
                  Servicio
                </NavLink>
              </li>
              {consola ? (
                <li className="nav-item">
                  <a className="nav-link" href={consola} rel="noreferrer">
                    Consola local
                  </a>
                </li>
              ) : null}
            </ul>
          </div>
        </nav>
      </header>
      <main id="contenido" className="container-fluid contenido py-3" tabIndex={-1} ref={principal}>
        {children}
      </main>
      <footer className="container-fluid contenido pb-4 small text-muted">
        <p className="mb-1">
          Consulta de solo lectura de la API pública v1 a través de la pasarela local. Las estadísticas describen
          sorteos ya ocurridos; no son probabilidades del próximo sorteo ni recomendaciones de apuesta.
        </p>
        <p className="mb-0">
          Predicciones y simulaciones: uso experimental no acreditado; no acreditan ventaja frente al azar.
        </p>
      </footer>
    </>
  );
}

const SECCIONES = [
  { ruta: "", titulo: "Ficha y resumen" },
  { ruta: "/sorteos", titulo: "Sorteos" },
  { ruta: "/estadisticas", titulo: "Estadísticas" },
  { ruta: "/prediccion", titulo: "Predicción guardada" },
  { ruta: "/fiabilidad", titulo: "Fiabilidad" },
  { ruta: "/modelos", titulo: "Modelos registrados" },
  { ruta: "/carteras", titulo: "Carteras guardadas" },
  { ruta: "/resultados", titulo: "Resultados observados" },
  { ruta: "/simulaciones", titulo: "Simulaciones" },
] as const;

/** Pestañas de un juego; el nombre sale de `/juegos` (en memoria) o, mientras tanto, del codigo. */
export function PestanasDeJuego({ codigo }: { codigo: string }) {
  const [juegos] = useConsulta("juegos", obtenerJuegos);
  const nombre = juegos.fase === "lista" ? (juegos.datos.find((j) => j.codigo === codigo)?.nombre ?? codigo) : codigo;
  const base = `/juegos/${encodeURIComponent(codigo)}`;
  return (
    <nav aria-label={`Secciones de ${nombre}`} className="mb-3">
      <p className="h4 mb-2">{nombre}</p>
      <ul className="nav nav-pills pestanas flex-wrap">
        {SECCIONES.map((s) => (
          <li className="nav-item" key={s.ruta}>
            <NavLink className="nav-link py-1" to={`${base}${s.ruta}`} end={s.ruta === "" || s.ruta === "/prediccion"}>
              {s.titulo}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
