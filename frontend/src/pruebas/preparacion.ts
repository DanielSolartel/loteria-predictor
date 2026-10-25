/** Preparacion comun de Vitest: desmonta cada prueba, restaura `fetch` y vacia la memoria del cliente. */
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { reiniciarCliente } from "../api/cliente";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
  reiniciarCliente();
});
