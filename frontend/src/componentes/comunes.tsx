/** Piezas de presentacion compartidas por las pantallas. */
import type { ReactNode } from "react";
import type { Json } from "../api/decodificar";
import type { ParNumeroColor, Resultado } from "../api/presentacion";

/** Region de tabla con desplazamiento propio, alcanzable con el teclado. */
export function TablaDesplazable({ etiqueta, children }: { etiqueta: string; children: ReactNode }) {
  return (
    <div className="tabla-desplazable" role="region" aria-label={etiqueta} tabIndex={0}>
      {children}
    </div>
  );
}

export function Cargando({ que }: { que: string }) {
  return (
    <p className="text-muted" role="status">
      Cargando {que}…
    </p>
  );
}

export function Numeros({ numeros, superbalota }: { numeros: readonly number[]; superbalota?: number | null }) {
  return (
    <span className="d-inline-flex flex-wrap align-items-center">
      {numeros.map((n, i) => (
        <span className="numero-bolita" key={`${i}-${n}`}>
          {n}
        </span>
      ))}
      {superbalota !== null && superbalota !== undefined ? (
        <>
          <span className="visually-hidden">superbalota</span>
          <span className="numero-bolita superbalota-bolita" title="superbalota">
            {superbalota}
          </span>
        </>
      ) : null}
    </span>
  );
}

const CLASES_DE_COLOR = new Set(["amarillo", "azul", "rojo", "verde", "blanco", "negro"]);

function Muestra({ color, nombre }: { color: string; nombre: string }) {
  const clase = color.toLowerCase();
  return (
    <span
      className={`color-swatch${CLASES_DE_COLOR.has(clase) ? ` color-${clase}` : ""}`}
      aria-hidden="true"
      title={nombre}
    />
  );
}

/** Un color de ColorLoto con su muestra y su nombre en texto (no solo el color). */
export function Color({ color }: { color: string }) {
  return (
    <span className="text-nowrap">
      <Muestra color={color} nombre={color} />
      {color}
    </span>
  );
}

export function ParColor({ numero, color, nombre }: { numero: number; color: string; nombre?: string }) {
  return (
    <span className="me-2 text-nowrap d-inline-block">
      <Muestra color={color} nombre={nombre ?? color} />
      {numero} <span className="small text-muted">{(nombre ?? color).toLowerCase()}</span>
    </span>
  );
}

export function Pares({ pares }: { pares: readonly ParNumeroColor[] }) {
  return (
    <span className="d-inline-flex flex-wrap">
      {pares.map(([n, c], i) => (
        <ParColor key={`${i}-${n}-${c}`} numero={n} color={c} />
      ))}
    </span>
  );
}

export function VerResultado({ resultado }: { resultado: Resultado }) {
  return "pares" in resultado ? (
    <Pares pares={resultado.pares} />
  ) : (
    <Numeros numeros={resultado.numeros} superbalota={resultado.superbalota} />
  );
}

/** Aviso experimental del backend; siempre visible donde hay predicciones o simulaciones. */
export function AvisoExperimental({ estadoDeUso, children }: { estadoDeUso: string; children?: ReactNode }) {
  return (
    <div className="alert alert-warning aviso-experimental small" role="note">
      <strong>Uso: {estadoDeUso.replaceAll("_", " ")}.</strong> {children}
    </div>
  );
}

export function textoJson(valor: Json): string {
  return typeof valor === "string" ? valor : JSON.stringify(valor);
}

/** Datos genericos (parametros, limites, contexto) como lista de definiciones anidada. */
export function ArbolDeDatos({ datos, profundidad = 0 }: { datos: Json; profundidad?: number }) {
  if (datos === null) {
    return <span className="text-muted">—</span>;
  }
  if (typeof datos !== "object") {
    return <span>{String(datos)}</span>;
  }
  if (Array.isArray(datos)) {
    if (datos.every((x) => x === null || typeof x !== "object")) {
      return <span>{datos.map((x) => (x === null ? "—" : String(x))).join(", ") || "(vacío)"}</span>;
    }
    return (
      <ol className="mb-0 ps-3">
        {datos.map((x, i) => (
          <li key={i}>
            <ArbolDeDatos datos={x} profundidad={profundidad + 1} />
          </li>
        ))}
      </ol>
    );
  }
  const entradas = Object.entries(datos);
  if (entradas.length === 0) {
    return <span className="text-muted">(vacío)</span>;
  }
  return (
    <dl className={`arbol mb-0${profundidad > 0 ? " small" : ""}`}>
      {entradas.map(([clave, valor]) => (
        <div key={clave}>
          <dt>
            <code>{clave}</code>
          </dt>
          <dd>
            <ArbolDeDatos datos={valor} profundidad={profundidad + 1} />
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function Huella({ valor }: { valor: string | null }) {
  return valor === null ? <span className="text-muted">—</span> : <span className="huella small">{valor}</span>;
}
