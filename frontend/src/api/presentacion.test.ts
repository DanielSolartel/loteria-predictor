/** Contrato de presentacion: toda respuesta sintetica de la API se decodifica sin perder estructura. */
import { describe, expect, it } from "vitest";
import { muestra, nombresDeMuestras } from "../pruebas/servidor";
import { type Decodificador, decodificar, EstructuraNoReconocida } from "./decodificar";
import { decCarterasGuardadas, decFichaCarteraGuardada, decFichaModeloGuardado, decModelosGuardados, decResultadosGuardados } from "./guardados";
import {
  decError,
  decEstado,
  decFiabilidad,
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
  fiabilidad: decFiabilidad,
  simulaciones: decSimulaciones,
  simulacion: decSimulacion,
  modelos: decModelosGuardados,
  modelo: decFichaModeloGuardado,
  carteras: decCarterasGuardadas,
  cartera: decFichaCarteraGuardada,
  resultados: decResultadosGuardados,
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

  it("9.3: rankings con la superbalota aparte, explicacion con importancias y cortes separados", () => {
    const p = decodificar(decPredicciones, muestra("BALOTO--predicciones").cuerpo).prediccion;
    expect(p?.rankings?.superbalota?.todos.length).toBe(16);
    expect(p?.rankings?.numeros.fuertes?.length).toBe(10);
    expect(p?.explicacion?.importancias.estado).toBe("disponible");
    expect(p?.explicacion?.importancias.valores?.length).toBeGreaterThan(0);
    expect(p?.explicacion?.metodo.entrenamiento?.corte_de_entrenamiento).toBe(2185);
    expect(p?.corte).toBe(2192);
    expect(p?.registrado?.numero).toBe(1);
    expect(p?.reproduccion?.exacta).toBe(true);
  });

  it("9.3: ColorLoto conserva los pares numero-color y separa numeros y colores", () => {
    const r = decodificar(decPredicciones, muestra("COLORLOTO--predicciones").cuerpo).prediccion?.rankings;
    const par = r?.pares?.fuertes?.[0]?.candidato;
    expect(Array.isArray(par) && typeof par[0] === "number" && typeof par[1] === "string").toBe(true);
    expect(r?.numeros.todos.every((f) => typeof f.candidato === "number")).toBe(true);
    expect(r?.colores?.todos.every((f) => typeof f.candidato === "string")).toBe(true);
    expect(r?.superbalota).toBeNull();
    expect(r?.pares?.todos[0]?.multiplicidad_esperada).not.toBeNull();
  });

  it("9.3: sin explicacion, alterada o con la base caida la API lo informa sin generarla", () => {
    const sin = decodificar(decPredicciones, muestra("BALOTO_REVANCHA--predicciones").cuerpo).prediccion;
    expect(sin?.explicacion).toBeNull();
    expect(sin?.explicacion_disponible).toBe(false);
    expect(sin?.rankings).not.toBeNull();
    const alterada = decodificar(decPredicciones, muestra("MILOTO--predicciones--explicacion_alterada").cuerpo).prediccion;
    expect(alterada?.explicacion).toBeNull();
    expect(alterada?.explicaciones_ilegibles).toEqual([{ clave: expect.stringMatching(/^[0-9a-f]{64}$/), motivo: "contenido_alterado" }]);
    const caida = decodificar(decFiabilidad, muestra("MILOTO--fiabilidad--sin_base").cuerpo);
    expect(caida.base).toEqual({ estado: "no_disponible", ultimo_sorteo: null, fecha: null, sorteos: null });
    expect(caida.lineas[0]?.evaluaciones[0]?.estado).toBe("sin_base");
  });

  it("9.3: la fiabilidad separa tipos, trae la semilla como texto y el corte pedido", () => {
    const f = decodificar(decFiabilidad, muestra("BALOTO--fiabilidad--corte-2192").cuerpo);
    expect(f.hasta).toBe(2192);
    expect(f.lineas.map((l) => l.evaluaciones.map((e) => e.tipo))).toEqual([
      ["seguimiento", "retrospectiva"],
      ["seguimiento", "retrospectiva"],
    ]);
    expect(f.receta.tipo).toBe("evaluacion_de_receta");
    const m = f.lineas[0]?.evaluaciones[0]?.componentes.numeros?.metricas?.diferencia_log_loss;
    expect(m?.semilla).toMatch(/^\d+$/);
    expect(m?.intervalo).toHaveLength(2);
    const todos = decodificar(decFiabilidad, muestra("BALOTO--fiabilidad").cuerpo);
    expect(todos.hasta).toBeNull();
    expect(todos.lineas[0]?.evaluaciones[0]?.muestra?.pendientes).toBe(1);
    expect(f.lineas[0]?.evaluaciones[0]?.muestra?.pendientes).toBe(0);
  });

  it("9.3: una fiabilidad con un intervalo mal formado se rechaza con la ruta del campo", () => {
    const cuerpo = muestra("BALOTO--fiabilidad").cuerpo as {
      lineas: { evaluaciones: { componentes: { numeros: { metricas: { diferencia_log_loss: { intervalo: number[] } } } } }[] }[];
    };
    const metrica = cuerpo.lineas[0]?.evaluaciones[0]?.componentes.numeros.metricas.diferencia_log_loss;
    if (metrica) {
      metrica.intervalo = [0, 1, 2];
    }
    expect(() => decodificar(decFiabilidad, cuerpo)).toThrow("respuesta.lineas[0].evaluaciones[0].componentes.numeros.metricas.diferencia_log_loss.intervalo");
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
