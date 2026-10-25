/** Contrato de presentacion: toda respuesta sintetica de la API se decodifica sin perder estructura. */
import { describe, expect, it } from "vitest";
import { muestra, nombresDeMuestras } from "../pruebas/servidor";
import { type Decodificador, decodificar, EstructuraNoReconocida } from "./decodificar";
import {
  decError,
  decEstado,
  decIndice,
  decJuegoDetalle,
  decJuegos,
  decPaginaDeSorteos,
  decPanel,
  decPredicciones,
  decRespuestaDeMetrica,
  decResumen,
  decSalud,
  decSimulacion,
  decSimulaciones,
  decSorteo,
} from "./presentacion";

const POR_TIPO: Record<string, Decodificador<unknown>> = {
  juegos: decJuegos,
  salud: decSalud,
  estado: decEstado,
  juego: decJuegoDetalle,
  indice: decIndice,
  resumen: decResumen,
  panel: decPanel,
  metrica: decRespuestaDeMetrica,
  sorteos: decPaginaDeSorteos,
  sorteo: decSorteo,
  predicciones: decPredicciones,
  simulaciones: decSimulaciones,
  simulacion: decSimulacion,
};

describe("respuestas sinteticas de la API", () => {
  const nombres = nombresDeMuestras();

  it("hay respuestas de los cuatro juegos y de todos los errores contractuales", () => {
    for (const juego of ["BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO"]) {
      expect(nombres.some((n) => n.startsWith(`${juego}--`))).toBe(true);
    }
    for (const estado of [401, 404, 422, 429, 500, 503]) {
      expect(nombres).toContain(`global--error--${estado}`);
    }
    expect(nombres).toContain("COLORLOTO--simulacion--alterada");
  });

  it.each(nombres)("%s se decodifica con su tipo", (nombre) => {
    const m = muestra(nombre);
    if (m.estado !== 200) {
      const { error } = decodificar(decError, m.cuerpo);
      expect(error.codigo).toMatch(/^[a-z_]+$/);
      expect(error.mensaje.length).toBeGreaterThan(0);
      return;
    }
    const tipo = nombre.split("--")[1] ?? "";
    const decodificador = POR_TIPO[tipo];
    expect(decodificador, `sin decodificador para ${tipo}`).toBeDefined();
    expect(() => decodificar(decodificador as Decodificador<unknown>, m.cuerpo)).not.toThrow();
  });

  it("los pares numero-color y la superbalota se conservan", () => {
    const sorteo = decodificar(decSorteo, muestra("COLORLOTO--sorteo").cuerpo);
    expect(sorteo.pares).toHaveLength(6);
    expect(sorteo.pares[0]).toMatchObject({ color_codigo: expect.any(String), color_nombre: expect.any(String) });
    const baloto = decodificar(decSorteo, muestra("BALOTO--sorteo").cuerpo);
    expect(baloto.superbalota).not.toBeNull();
    const prediccion = decodificar(decPredicciones, muestra("COLORLOTO--predicciones").cuerpo).prediccion;
    expect(prediccion?.combinaciones[0]?.resultado).toHaveProperty("pares");
  });

  it("las filas de metrica conservan las claves no declaradas en columnas", () => {
    const { metrica } = decodificar(decRespuestaDeMetrica, muestra("BALOTO--metrica--correlaciones").cuerpo);
    const tabla = metrica.tablas[0];
    const declaradas = new Set(tabla?.columnas.map((c) => c.clave));
    const extra = Object.keys(tabla?.filas[0] ?? {}).filter((k) => !declaradas.has(k));
    expect(extra).toEqual(expect.arrayContaining(["contraste", "motivo", "motivo_p_value", "n", "permutaciones"]));
  });

  it("el resumen sin sorteos hasta el corte trae estadisticas nulas y frescura", () => {
    const r = decodificar(decResumen, muestra("BALOTO--resumen--sin_sorteos").cuerpo);
    expect(r.estadisticas).toBeNull();
    expect(r.periodo).toBeNull();
    expect(r.frescura.estado).toBe("desactualizado");
  });

  it("una estructura distinta se rechaza con la ruta del campo", () => {
    const cuerpo = muestra("BALOTO--resumen").cuerpo as Record<string, unknown>;
    (cuerpo.frescura as Record<string, unknown>).dias_desde_el_ultimo_sorteo = "muchos";
    expect(() => decodificar(decResumen, cuerpo)).toThrow(EstructuraNoReconocida);
    expect(() => decodificar(decResumen, cuerpo)).toThrow("respuesta.frescura.dias_desde_el_ultimo_sorteo");
    const sinTipo = muestra("BALOTO--resumen").cuerpo as Record<string, unknown>;
    (sinTipo.reglas as Record<string, unknown>).tipo = "quiniela";
    expect(() => decodificar(decResumen, sinTipo)).toThrow("respuesta.reglas.tipo");
  });
});
