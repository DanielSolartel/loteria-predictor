/** `formatear` del frontend frente a la tabla que produce el `formatear` de la consola HTMX. */
import { describe, expect, it } from "vitest";
// Texto sin transformar: el modulo JSON de Vite convertiria -0 en 0.
import texto from "../pruebas/formatos.json?raw";
import { abreviada, alineadoADerecha, ETIQUETAS_TIPO_P, fechaHora, formatear } from "./formatos";

const casos = JSON.parse(texto) as {
  etiquetas_tipo_p: Record<string, string>;
  casos: { valor: number | string | null; formato: string; esperado: string }[];
};

describe("formatear", () => {
  it("usa las mismas etiquetas de tipo de p-value que el backend", () => {
    expect(ETIQUETAS_TIPO_P).toEqual(casos.etiquetas_tipo_p);
  });

  it.each(casos.casos.map((c) => [c.formato, JSON.stringify(c.valor), c.esperado, c.valor] as const))(
    "%s(%s) = %s",
    (formato, _texto, esperado, valor) => {
      expect(formatear(valor, formato)).toBe(esperado);
    },
  );

  it("alinea a la derecha los numeros y no el texto", () => {
    expect(alineadoADerecha("dec2")).toBe(true);
    expect(alineadoADerecha("texto")).toBe(false);
    expect(alineadoADerecha("tipo_p")).toBe(false);
  });

  it("fechas y huellas", () => {
    expect(fechaHora("2026-10-07T01:00:03+00:00")).toBe("2026-10-07 01:00:03");
    expect(fechaHora(null)).toBe("—");
    expect(abreviada("a".repeat(64))).toBe(`${"a".repeat(12)}…`);
  });
});
