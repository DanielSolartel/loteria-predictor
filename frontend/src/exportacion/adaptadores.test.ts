/** Esperados de las proyecciones sintéticas, independientes del serializador CSV. */
import { describe, expect, it } from "vitest";
import { decSorteo } from "../api/presentacion";
import { decCarterasGuardadas, decFichaCarteraGuardada, decResultadosGuardados } from "../api/guardados";
import { muestra } from "../pruebas/servidor";
import { tablaCarteras, tablaSorteos, tablasCartera, tablasResultados } from "./adaptadores";

describe("tablas públicas sin pérdida de identidad, posición ni ausencia", () => {
  it("ColorLoto: el sorteo conserva seis pares ordenados y sus nombres textuales", () => {
    const d = decSorteo(muestra("COLORLOTO--sorteo").cuerpo, "$sorteo");
    const t = tablaSorteos([d])[0]!;
    expect(t.filas).toEqual([
      [45, "2024-12-16", "lunes", 1, 2, "BLANCO", "Blanco", null],
      [45, "2024-12-16", "lunes", 2, 5, "ROJO", "Rojo", null],
      [45, "2024-12-16", "lunes", 3, 4, "BLANCO", "Blanco", null],
      [45, "2024-12-16", "lunes", 4, 5, "AMARILLO", "Amarillo", null],
      [45, "2024-12-16", "lunes", 5, 2, "ROJO", "Rojo", null],
      [45, "2024-12-16", "lunes", 6, 1, "VERDE", "Verde", null],
    ]);
  });

  it("ColorLoto: la cartera conserva cada balota y no separa números de colores", () => {
    const d = decFichaCarteraGuardada(muestra("COLORLOTO--cartera").cuerpo, "$cartera");
    const t = tablasCartera(d).find((v) => v.id === "combinaciones")!;
    expect(t.filas.filter((f) => f[3] === 1).map((f) => f.slice(5))).toEqual([
      [1, 1, "AZUL", "AZUL", null], [2, 2, "AMARILLO", "AMARILLO", null],
      [3, 2, "ROJO", "ROJO", null], [4, 3, "VERDE", "VERDE", null],
      [5, 5, "AMARILLO", "AMARILLO", null], [6, 6, "NEGRO", "NEGRO", null],
    ]);
    expect(t.filas.every((f) => f[0] === d.cartera.clave && f[1] === d.cartera.objetivo && f[2] === d.cartera.corte)).toBe(true);
  });

  it("resultados pendientes no se convierten en cero y la pérdida conserva precisión", () => {
    const d = decResultadosGuardados(muestra("BALOTO--resultados").cuerpo, "$resultados");
    const observada = d.historial.filas.find((f) => f.metricas !== null)!;
    observada.metricas!.log_loss = 0.123456789012345;
    const pendiente = d.historial.filas.find((f) => f.estado === "pendiente")!;
    const t = tablasResultados(d).find((v) => v.id === "resultados_historial")!;
    const filaPendiente = t.filas.find((f) => f[0] === pendiente.objetivo && f[3] === pendiente.identificador)!;
    expect(filaPendiente[5]).toBe("pendiente");
    expect(filaPendiente.slice(11)).toEqual(Array(12).fill(null));
    const filasObservadas = t.filas.filter((f) => f[0] === observada.objetivo && f[3] === observada.identificador);
    expect(filasObservadas.length).toBeGreaterThan(0);
    expect(filasObservadas.every((f) => f[18] === 0.123456789012345)).toBe(true);
  });

  it("los metadatos alterados/null permanecen aislados junto a la cartera sana", () => {
    const d = decCarterasGuardadas(muestra("BALOTO--carteras").cuerpo, "$carteras");
    const sana = d.elementos[0]!;
    const alterada = { ...sana, clave: "a".repeat(64), estado: "alterado" as const, motivo: "Corte no acreditado", corte: null, nombre: null };
    const t = tablaCarteras([alterada, sana])[0]!;
    expect(t.filas[0]![2]).toBe("alterado");
    expect(t.filas[0]![3]).toBe("Corte no acreditado");
    expect(t.filas[0]![6]).toBeNull();
    expect(t.filas[0]![8]).toBeNull();
    expect(t.filas[1]![0]).toBe(sana.clave);
    expect(t.filas[1]![2]).toBe("disponible");
    expect(t.filas[1]![6]).toBe(sana.corte);
    expect(t.filas[1]![8]).toBe(sana.nombre);
  });
});
