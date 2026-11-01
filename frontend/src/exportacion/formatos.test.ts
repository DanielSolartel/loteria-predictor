import { afterEach, describe, expect, it, vi } from "vitest";
import {
  descargarArchivo, exportarCsv, exportarJson, nombreArchivo,
  type SolicitudExportacion, textoCsvSeguro, validarExportacion,
} from "./formatos";

const fecha = new Date("2026-10-29T12:34:56.789Z");
const solicitud = (): SolicitudExportacion => ({
  juego: "COLORLOTO", recurso: "resultados", ruta: "/juegos/COLORLOTO/resultados",
  filtros: { tipo: "seguimiento", objetivo: 91, pagina: 2, por_pagina: 5, no_permitido: "no exportar" },
  pagina: { pagina: 2, por_pagina: 5, total: 8 }, alcance: "Sólo página cargada del historial; agregado indicado por separado.",
  datos: { juego: "COLORLOTO", pares: [{ numero: 2, color: "AZUL" }, { numero: 2, color: "ROJO" }],
    corte: 90, objetivo: 91, observado: false, aciertos: null, perdida: -0.012345678901234567, unidades: "fracción por balota", nombre: null },
  tablas: [{ id: "historial", titulo: "Historial de emisiones", columnas: ["numero", "color", "aciertos", "observado", "perdida"],
    filas: [[2, "AZUL", null, false, -0.012345678901234567], [2, "ROJO", 0, true, 0]] }],
  notas: ["Pendiente no significa cero aciertos."],
});

/** Parser de comprobación independiente: autómata CSV, no usa funciones de producción. */
function leerCsv(csv: string): string[][] {
  const texto = csv.startsWith("\ufeff") ? csv.slice(1) : csv;
  const filas: string[][] = [];
  let fila: string[] = [], celda = "", entrecomillada = false;
  for (let i = 0; i < texto.length; i++) {
    const c = texto[i];
    if (c === '"') {
      if (entrecomillada && texto[i + 1] === '"') { celda += '"'; i++; }
      else entrecomillada = !entrecomillada;
    } else if (c === "," && !entrecomillada) { fila.push(celda); celda = ""; }
    else if (c === "\r" && texto[i + 1] === "\n" && !entrecomillada) {
      fila.push(celda); filas.push(fila); fila = []; celda = ""; i++;
    } else celda += c;
  }
  expect(entrecomillada).toBe(false);
  expect(celda).toBe(""); expect(fila).toEqual([]);
  return filas;
}

afterEach(() => vi.restoreAllMocks());

describe("JSON de la proyección cargada", () => {
  it("conserva pares, precisión, null, falso y contexto; no copia parámetros ajenos", () => {
    const s = solicitud(); const a = exportarJson(s, fecha); const leido = JSON.parse(a.contenido);
    expect(a.mime).toBe("application/json;charset=utf-8");
    expect(leido).toEqual({
      esquema: "loteria-predictor/consulta-publica/1", exportado_en: "2026-10-29T12:34:56.789Z",
      juego: "COLORLOTO", recurso: "resultados", ruta_spa: "/juegos/COLORLOTO/resultados?tipo=seguimiento&objetivo=91&pagina=2&por_pagina=5",
      filtros: { tipo: "seguimiento", objetivo: 91, pagina: 2, por_pagina: 5 }, alcance: s.alcance,
      paginacion: { pagina: 2, por_pagina: 5, total: 8 }, identidad: {}, estado_de_uso: "experimental_no_acreditado", autoriza_evaluacion: false,
      advertencias: ["experimental_no_acreditado", "AE-39 NO-GO; AUTORIZA_EVALUACION = False",
        "Copia local de la consulta cargada: no es un artefacto canónico, prueba de autenticidad, sello temporal ni ventaja predictiva.",
        "Pendiente no significa cero aciertos."], datos: s.datos,
    });
    expect(leido.datos.pares).toEqual([{ numero: 2, color: "AZUL" }, { numero: 2, color: "ROJO" }]);
    expect(leido.datos.perdida).toBe(-0.012345678901234567);
    expect(a.contenido).not.toContain("no_permitido"); expect(a.contenido).not.toContain("no exportar");
  });

  it("distingue ausencias de cero/falso y conserva una cadena peligrosa original", () => {
    const s = solicitud(); s.datos = { nombre: null, ausente: undefined, cero: 0, falso: false, texto: ' \t="Árbol, ñ"\n+SUM(1,2)' };
    expect(JSON.parse(exportarJson(s, fecha).contenido).datos).toEqual({ nombre: null, cero: 0, falso: false, texto: ' \t="Árbol, ñ"\n+SUM(1,2)' });
  });

  it("acepta vacíos explícitos sin inventar observaciones", () => {
    const s = solicitud(); s.datos = { elementos: [], total: 0 }; s.tablas = [{ id: "historial", titulo: "Historial", columnas: ["objetivo"], filas: [] }];
    expect(JSON.parse(exportarJson(s, fecha).contenido).datos).toEqual({ elementos: [], total: 0 });
  });

  it("identifica canónicamente la barra final admitida por la ruta SPA", () => {
    const s = solicitud(); s.ruta += "/";
    expect(JSON.parse(exportarJson(s, fecha).contenido).ruta_spa).toBe("/juegos/COLORLOTO/resultados?tipo=seguimiento&objetivo=91&pagina=2&por_pagina=5");
  });

  it.each([NaN, Infinity, -Infinity, () => 1, new Date()])("rechaza estructuras no JSON reconocidas %s", (v) => {
    const s = solicitud(); s.datos = { v }; expect(() => exportarJson(s, fecha)).toThrow();
  });

  it("rechaza ciclos y tablas desalineadas sin fabricar un archivo", () => {
    const s = solicitud(); const ciclo: Record<string, unknown> = {}; ciclo.a = ciclo; s.datos = ciclo;
    expect(() => validarExportacion(s)).toThrow();
    s.datos = {}; s.tablas = [{ id: "x", titulo: "X", columnas: ["a", "b"], filas: [[1]] }];
    expect(() => exportarCsv(s, "x", fecha)).toThrow();
  });

  it.each(["https://example.invalid/juegos/COLORLOTO/resultados", "/juegos/BALOTO/resultados", "/juegos/COLORLOTO/resultados?api_key=secreto", "/juegos/COLORLOTO/../resultados"])("no exporta otra ruta/origen %s", (ruta) => {
    const s = solicitud(); s.ruta = ruta; expect(() => exportarJson(s, fecha)).toThrow();
  });
});

describe("CSV de tabla explícita", () => {
  it("repite identidad acreditada en CSV y JSON sin convertirla en parámetros de consulta", () => {
    const s = solicitud();
    s.identidad = { corte_entrada: 90, objetivo: 91, modelo: "modelo_publico", version_registrada: 2, clave_registrada: "a".repeat(64), contexto: "cartera histórica", no_permitido: "privado" };
    const j = JSON.parse(exportarJson(s, fecha).contenido);
    expect(j.identidad).toEqual({ objetivo: 91, modelo: "modelo_publico", version_registrada: 2, clave_registrada: "a".repeat(64), corte_entrada: 90, contexto: "cartera histórica" });
    expect(j.ruta_spa).not.toContain("modelo_publico");
    const csv = exportarCsv(s, "historial", fecha).contenido;
    const filas = leerCsv(csv);
    for (const fila of filas.slice(1)) {
      expect(fila[filas[0]!.indexOf("identidad_corte_entrada")]).toBe("90");
      expect(fila[filas[0]!.indexOf("identidad_version_registrada")]).toBe("2");
      expect(fila[filas[0]!.indexOf("identidad_clave_registrada")]).toBe("a".repeat(64));
    }
    expect(csv).not.toContain("privado");
  });
  it("relee pares ligados, unidades, números, null y booleanos con tipos explícitos", () => {
    const s = solicitud(); const archivo = exportarCsv(s, "historial", fecha);
    const filas = leerCsv(archivo.contenido); const cabeceras = filas[0]!;
    const mapa = (fila: string[]) => Object.fromEntries(cabeceras.map((c, i) => [c, fila[i]]));
    expect(archivo.contenido.charCodeAt(0)).toBe(0xfeff);
    expect(archivo.mime).toBe("text/csv;charset=utf-8");
    expect(filas).toHaveLength(4);
    expect(cabeceras).toContain("dato_numero"); expect(cabeceras).toContain("dato_color_tipo");
    expect(new Set(cabeceras).size).toBe(cabeceras.length);
    expect(mapa(filas[1]!)).toMatchObject({ tipo_fila: "contexto", esquema: "loteria-predictor/tabla-publica/1", filas_cargadas: "2", juego: "COLORLOTO", pagina: "2", total: "8" });
    expect(mapa(filas[2]!)).toMatchObject({ tipo_fila: "dato", dato_numero: "2", dato_numero_tipo: "numero", dato_color: "AZUL", dato_color_tipo: "texto", dato_aciertos: "null", dato_aciertos_tipo: "null", dato_observado: "false", dato_observado_tipo: "booleano", dato_perdida: "-0.012345678901234567", dato_perdida_tipo: "numero" });
    expect(mapa(filas[3]!)).toMatchObject({ dato_numero: "2", dato_color: "ROJO", dato_aciertos: "0", dato_aciertos_tipo: "numero", dato_observado: "true", dato_perdida: "0" });
    expect(archivo.contenido).toContain("Sólo página cargada");
  });

  it("vacío válido tiene contexto/cabecera y cero registros dato", () => {
    const s = solicitud(); s.tablas = [{ id: "vacia", titulo: "Sin filas cargadas", columnas: ["objetivo", "observado"], filas: [] }];
    const filas = leerCsv(exportarCsv(s, "vacia", fecha).contenido);
    expect(filas).toHaveLength(2); expect(filas[1]![0]).toBe("contexto");
    expect(filas[1]![filas[0]!.indexOf("filas_cargadas")]).toBe("0");
  });

  it("distingue null, marcador textual null, texto vacío, cero y falso", () => {
    const s = solicitud(); s.tablas = [{ id: "tipos", titulo: "Tipos", columnas: ["valor"], filas: [[null], ["null"], [""], [0], [false], ["\\N"]] }];
    const filas = leerCsv(exportarCsv(s, "tipos", fecha).contenido);
    const j = filas[0]!.indexOf("dato_valor");
    expect(filas.slice(2).map((f) => f.slice(j))).toEqual([["null", "null"], ["null", "texto"], ["", "texto"], ["0", "numero"], ["false", "booleano"], ["\\N", "texto"]]);
  });

  it.each(["=2+2", "+SUM(1,2)", "-2+3", "@A1", "  =2", "\t+2", "\r\n@A1", '"=1"', "'=3", "\ufeff=1", "a\n=9", "\0=4"])("neutraliza texto peligroso completo sin confiar sólo en las comillas %j", (valor) => {
    const s = solicitud(); s.tablas = [{ id: "texto", titulo: "=Título de tabla", columnas: ["=Etiqueta"], filas: [[valor]] }];
    const filas = leerCsv(exportarCsv(s, "texto", fecha).contenido);
    expect(filas[0]).toContain("dato_=Etiqueta");
    expect(filas[1]![filas[0]!.indexOf("tabla")]).toBe("'=Título de tabla");
    const i = filas[0]!.indexOf("dato_=Etiqueta");
    expect(filas[2]![i]).toBe("'" + valor); expect(filas[2]![i+1]).toBe("texto");
  });

  it("escapa separadores/comillas/saltos y mantiene español y números negativos tipados", () => {
    const s = solicitud(); s.tablas = [{ id: "unicode", titulo: "Prueba", columnas: ["texto", "numero", "texto_negativo"], filas: [['Árbol, "niño"\nsegunda línea', -2.5, "-2.5"]] }];
    const filas = leerCsv(exportarCsv(s, "unicode", fecha).contenido); const i = filas[0]!.indexOf("dato_texto");
    expect(filas[2]!.slice(i)).toEqual(['\'Árbol, "niño"\nsegunda línea', "texto", "-2.5", "numero", "'-2.5", "texto"]);
    expect(textoCsvSeguro("niño, áéíóú")).toBe("niño, áéíóú");
  });

  it("selecciona sólo una tabla disponible y rechaza identidades desconocidas", () => {
    const s = solicitud(); s.tablas = [...s.tablas, { id: "agregado", titulo: "Agregado", columnas: ["objetivos"], filas: [[7]] }];
    const f = leerCsv(exportarCsv(s, "agregado", fecha).contenido);
    expect(f[0]).toContain("dato_objetivos"); expect(f[0]).not.toContain("dato_color");
    expect(() => exportarCsv(s, "ajena", fecha)).toThrow();
  });
});

describe("nombres y descarga", () => {
  it("libera mediante la API que creó la URL aunque su referencia global cambie después del clic", () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const original = vi.fn(), posterior = vi.fn();
    vi.stubGlobal("URL", { createObjectURL: () => "blob:propia", revokeObjectURL: original });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    descargarArchivo(exportarJson(solicitud(), fecha));
    URL.revokeObjectURL = posterior;
    expect(original).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1000);
    expect(original).toHaveBeenCalledExactlyOnceWith("blob:propia");
    expect(posterior).not.toHaveBeenCalled();
  });
  it("acota nombres, sin separadores ni controles ni títulos sin validar", () => {
    const nombre = nombreArchivo("../../C:\\ruta-ficticia\\segmento\n", '"=métrica/'.repeat(30), "csv", fecha, "../../../tabla\r\n");
    expect(nombre).toMatch(/^lp-[a-z0-9_-]+-20261029T123456789Z\.csv$/);
    expect(nombre.length).toBeLessThan(180); expect(nombre).not.toMatch(/[\\/\x00-\x1f]/);
    expect(nombre).not.toContain("..");
  });

  it("crea Blob con resultado real, inicia cada clic antes de revocar, y libera cada URL sucesiva", async () => {
    // FileReader de jsdom completa por setImmediate; sólo controlamos el plazo
    // de revocación setTimeout para no detener esa lectura independiente.
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const blobs: Blob[] = []; const orden: string[] = [];
    const crear = vi.fn((blob: Blob) => { blobs.push(blob); return `blob:local-${blobs.length}`; });
    const revocar = vi.fn((url: string) => { orden.push(`revocar:${url}`); });
    vi.stubGlobal("URL", { createObjectURL: crear, revokeObjectURL: revocar });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      expect(this.isConnected).toBe(true); expect(this.download).toMatch(/\.json$/); orden.push(`clic:${this.href}`);
    });
    const a = exportarJson(solicitud(), fecha);
    descargarArchivo(a); descargarArchivo(a);
    expect(orden).toEqual(["clic:blob:local-1", "clic:blob:local-2"]);
    expect(document.querySelectorAll("a[download]")).toHaveLength(0);
    expect(blobs[0]!.type).toBe("application/json;charset=utf-8");
    const leido = await new Promise<string>((resolver, rechazar) => { const lector = new FileReader(); lector.onload = () => resolver(String(lector.result)); lector.onerror = rechazar; lector.readAsText(blobs[0]!); });
    expect(JSON.parse(leido).datos.pares).toEqual([{ numero: 2, color: "AZUL" }, { numero: 2, color: "ROJO" }]);
    vi.advanceTimersByTime(999); expect(revocar).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1); expect(orden).toEqual(["clic:blob:local-1", "clic:blob:local-2", "revocar:blob:local-1", "revocar:blob:local-2"]);
  });

  it("libera la URL si no puede iniciarse el clic, sin ocultar el fallo", () => {
    const revocar = vi.fn(); vi.stubGlobal("URL", { createObjectURL: () => "blob:fallida", revokeObjectURL: revocar });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => { throw new Error("fallo deliberado"); });
    expect(() => descargarArchivo(exportarJson(solicitud(), fecha))).toThrow("fallo deliberado");
    expect(revocar).toHaveBeenCalledWith("blob:fallida"); expect(document.querySelectorAll("a[download]")).toHaveLength(0);
  });
});
