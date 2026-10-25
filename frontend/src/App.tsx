/** Rutas de la SPA (9.1): solo consultas de /api/v1. */
import { Link, Route, Routes } from "react-router-dom";
import { Marco } from "./componentes/Marco";
import { Estadisticas, Metrica } from "./pantallas/Estadisticas";
import { Ficha } from "./pantallas/Ficha";
import { Inicio } from "./pantallas/Inicio";
import { Prediccion } from "./pantallas/Prediccion";
import { Servicio } from "./pantallas/Servicio";
import { DetalleSimulacion, Simulaciones } from "./pantallas/Simulaciones";
import { DetalleSorteo, Sorteos } from "./pantallas/Sorteos";

function NoEncontrado() {
  return (
    <>
      <h1 className="h3">Página no encontrada</h1>
      <p>
        Esta dirección no corresponde a ninguna pantalla de la consulta. <Link to="/">Volver al inicio</Link>.
      </p>
    </>
  );
}

export function App() {
  return (
    <Marco>
      <Routes>
        <Route path="/" element={<Inicio />} />
        <Route path="/juegos/:codigo" element={<Ficha />} />
        <Route path="/juegos/:codigo/sorteos" element={<Sorteos />} />
        <Route path="/juegos/:codigo/sorteos/:numero" element={<DetalleSorteo />} />
        <Route path="/juegos/:codigo/estadisticas" element={<Estadisticas />} />
        <Route path="/juegos/:codigo/estadisticas/:metrica" element={<Metrica />} />
        <Route path="/juegos/:codigo/prediccion" element={<Prediccion />} />
        <Route path="/juegos/:codigo/simulaciones" element={<Simulaciones />} />
        <Route path="/simulaciones/:identificador" element={<DetalleSimulacion />} />
        <Route path="/servicio" element={<Servicio />} />
        <Route path="*" element={<NoEncontrado />} />
      </Routes>
    </Marco>
  );
}
