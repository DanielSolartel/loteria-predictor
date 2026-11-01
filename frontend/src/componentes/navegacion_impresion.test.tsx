/** Regresiones de navegación e impresión local; DOM simulado, sin Programador ni navegador nativo. */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Link, useNavigate } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import juegos from "../pruebas/respuestas/global--juegos.json";
import { FormularioDeCorte } from "./Filtros";
import { Marco, PestanasDeJuego } from "./Marco";

function servidor() {
  const consultar = vi.fn(async (url: string | URL | Request) => new Response(JSON.stringify(
    String(url) === "/api/v1/juegos" ? juegos.cuerpo : { consola_local: null, api: "v1" },
  ), { status: 200, headers: { "content-type": "application/json" } }));
  vi.stubGlobal("fetch", consultar);
  return consultar;
}

function Destinos() {
  const navegar = useNavigate();
  return <>
    <h1>Consulta sintética</h1>
    <Link to="?pagina=2">Página dos</Link>
    <Link to="/juegos/MILOTO">Otro juego</Link>
    <button type="button" onClick={() => navegar(-1)}>Atrás</button>
  </>;
}

describe("revisión final de navegación e impresión local", () => {
  it("lleva el foco al contenido tras cambiar filtros, volver por historial y cambiar de ruta", async () => {
    servidor();
    render(<MemoryRouter initialEntries={["/juegos/BALOTO/sorteos?pagina=1"]}>
      <Marco><Destinos /></Marco>
    </MemoryRouter>);
    const main = screen.getByRole("main");
    const pagina = screen.getByRole("link", { name: "Página dos" });
    pagina.focus();
    fireEvent.click(pagina);
    await waitFor(() => expect(document.activeElement).toBe(main));
    const atras = screen.getByRole("button", { name: "Atrás" });
    atras.focus();
    fireEvent.click(atras);
    await waitFor(() => expect(document.activeElement).toBe(main));
    const otro = screen.getByRole("link", { name: "Otro juego" });
    otro.focus();
    fireEvent.click(otro);
    await waitFor(() => expect(document.activeElement).toBe(main));
    expect(screen.getByRole("link", { name: "Saltar al contenido" }).getAttribute("href")).toBe("#contenido");
  });

  it("sincroniza el corte editable con el valor efectivo al regresar o quitar filtros", () => {
    const aplicar = vi.fn();
    const vista = render(<FormularioDeCorte valor="12" aplicar={aplicar} />);
    const campo = screen.getByRole("spinbutton", { name: "Corte (hasta el sorteo)" }) as HTMLInputElement;
    fireEvent.change(campo, { target: { value: "42" } });
    expect(campo.value).toBe("42");
    vista.rerender(<FormularioDeCorte valor="24" aplicar={aplicar} />);
    expect(campo.value).toBe("24");
    fireEvent.click(screen.getByRole("button", { name: "Aplicar" }));
    expect(aplicar.mock.calls).toEqual([["24"]]);
    vista.rerender(<FormularioDeCorte valor={null} aplicar={aplicar} />);
    expect(campo.value).toBe("");
    expect(screen.getByText("Corte de la muestra: histórico completo.")).toBeTruthy();
  });

  it("abre sólo detalles ya cargados para imprimir y restaura estados tras cancelar sin solicitudes", async () => {
    const consultar = servidor();
    const ajeno = document.createElement("details");
    document.body.append(ajeno);
    const vista = render(<MemoryRouter><Marco>
      <details data-testid="cerrado"><summary>Contexto guardado</summary><p>Última fila sintética</p></details>
      <details data-testid="abierto" open><summary>Advertencias</summary><p>Experimental</p></details>
    </Marco></MemoryRouter>);
    await screen.findByRole("link", { name: "Baloto" });
    const cerrado = screen.getByTestId("cerrado") as HTMLDetailsElement;
    const abierto = screen.getByTestId("abierto") as HTMLDetailsElement;
    const llamadas = consultar.mock.calls.length;
    fireEvent(window, new Event("beforeprint"));
    expect([cerrado.open, abierto.open, ajeno.open]).toEqual([true, true, false]);
    // Una segunda notificación no convierte el estado expandido en el original.
    fireEvent(window, new Event("beforeprint"));
    fireEvent(window, new Event("afterprint"));
    expect([cerrado.open, abierto.open]).toEqual([false, true]);
    cerrado.open = true;
    fireEvent(window, new Event("beforeprint"));
    fireEvent(window, new Event("afterprint"));
    expect(cerrado.open).toBe(true);
    expect(consultar.mock.calls.length).toBe(llamadas);
    vista.unmount();
    fireEvent(window, new Event("beforeprint"));
    expect(ajeno.open).toBe(false);
    ajeno.remove();
  });

  it("conserva el nombre del juego fuera de la navegación que se oculta en impresión", async () => {
    servidor();
    render(<MemoryRouter initialEntries={["/juegos/COLORLOTO"]}><Marco>
      <PestanasDeJuego codigo="COLORLOTO" />
    </Marco></MemoryRouter>);
    const nav = await screen.findByRole("navigation", { name: "Secciones de ColorLoto" });
    const encabezado = nav.parentElement;
    expect(encabezado?.classList.contains("encabezado-juego")).toBe(true);
    expect(encabezado?.querySelector("p")?.textContent).toBe("ColorLoto");
    expect(nav.querySelector("p")).toBeNull();
    expect(screen.getByRole("link", { name: "Ficha y resumen" }).getAttribute("aria-current")).toBe("page");
  });
});
