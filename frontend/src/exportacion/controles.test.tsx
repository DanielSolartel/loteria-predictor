import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { ExportarConsulta, type PropsExportarConsulta } from "../componentes/ExportarConsulta";

afterEach(() => vi.restoreAllMocks());
const props = (): PropsExportarConsulta => ({ juego: "BALOTO", recurso: "sorteos", alcance: "Página cargada", filtros: { pagina: 2, secreto: "no publicar" },
  pagina: { pagina: 2, por_pagina: 20, total: 21 }, datos: { elementos: [], total: 21 },
  tablas: [{ id: "sorteos", titulo: "Sorteos", columnas: ["numero"], filas: [] }] });

it("sólo acciones explícitas; imprimir/exportar no usan fetch ni consultan fiabilidad", () => {
  vi.useFakeTimers();
  const fetch = vi.fn(); const imprimir = vi.fn(); vi.stubGlobal("fetch", fetch); vi.stubGlobal("print", imprimir);
  vi.stubGlobal("URL", { createObjectURL: vi.fn(() => "blob:local"), revokeObjectURL: vi.fn() });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
  render(<MemoryRouter initialEntries={["/juegos/BALOTO/sorteos?pagina=2&secreto=no-publicar"]}><ExportarConsulta {...props()} /></MemoryRouter>);
  expect(imprimir).not.toHaveBeenCalled(); expect(fetch).not.toHaveBeenCalled();
  expect(screen.getByText(/Exportar página actual/)).toBeTruthy();
  expect(screen.queryByText(/no publicar/)).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Exportar JSON" }));
  fireEvent.click(screen.getByRole("button", { name: "Exportar CSV" }));
  fireEvent.click(screen.getByRole("button", { name: "Imprimir" }));
  expect(imprimir).toHaveBeenCalledTimes(1); expect(fetch).not.toHaveBeenCalled();
  vi.runAllTimers();
});

it("la estructura no reconocida no habilita ninguna acción", () => {
  render(<MemoryRouter initialEntries={["/juegos/BALOTO/sorteos"]}><ExportarConsulta {...props()} datos={{ invalido: NaN }} /></MemoryRouter>);
  expect(screen.queryByRole("button", { name: "Exportar JSON" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Imprimir" })).toBeNull();
});

it("selección de tabla explícita y cambio de colección no conserva una identidad ajena", () => {
  const s = props();
  const visto = render(<MemoryRouter initialEntries={["/juegos/BALOTO/sorteos"]}><ExportarConsulta {...s} tablas={[...s.tablas, { id: "segunda", titulo: "Otra tabla cargada", columnas: ["id"], filas: [[2]] }]} /></MemoryRouter>);
  const selector = screen.getByRole("combobox", { name: "Tabla CSV" });
  expect((selector as HTMLSelectElement).labels?.[0]?.textContent).toBe("Tabla CSV");
  fireEvent.change(selector, { target: { value: "segunda" } }); expect((selector as HTMLSelectElement).value).toBe("segunda");
  visto.rerender(<MemoryRouter initialEntries={["/juegos/BALOTO/sorteos"]}><ExportarConsulta {...s} tablas={[{ id: "tercera", titulo: "Nueva tabla", columnas: ["id"], filas: [[3]] }]} /></MemoryRouter>);
  expect(screen.queryByRole("combobox", { name: "Tabla CSV" })).toBeNull();
  expect(screen.getByText("CSV: Nueva tabla")).toBeTruthy();
});
