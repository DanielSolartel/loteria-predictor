import "bootstrap/dist/css/bootstrap.min.css";
import "./estilos/identidad.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";

const raiz = document.getElementById("raiz");
if (raiz === null) {
  throw new Error("falta el elemento #raiz");
}
if (import.meta.env.MODE === "escritorio") {
  void import("./escritorio/AppEscritorio").then(({ montarEscritorio }) => montarEscritorio(raiz));
} else {
  createRoot(raiz).render(
    <StrictMode>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </StrictMode>,
  );
}
