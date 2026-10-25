/**
 * Carga declarativa de una consulta. Cada cambio de `clave` cancela la
 * anterior y descarta su respuesta aunque llegue despues (no sobrescribe la
 * vigente). `reintentar` solo existe para el boton que pulsa la persona: no hay
 * reintentos automaticos.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { ErrorDeConsulta, esCancelacion } from "../api/cliente";

export type EstadoDeConsulta<T> =
  | { fase: "cargando" }
  | { fase: "lista"; datos: T }
  | { fase: "error"; error: ErrorDeConsulta };

function comoErrorDeConsulta(error: unknown): ErrorDeConsulta {
  return error instanceof ErrorDeConsulta
    ? error
    : new ErrorDeConsulta(null, "error_de_la_interfaz", "La interfaz no pudo procesar la respuesta.");
}

export function useConsulta<T>(
  clave: string | null,
  cargar: (senal: AbortSignal) => Promise<T>,
): [EstadoDeConsulta<T>, () => void] {
  const [intento, setIntento] = useState(0);
  const [guardado, setGuardado] = useState<{ marca: string; estado: EstadoDeConsulta<T> } | null>(null);
  const cargador = useRef(cargar);
  cargador.current = cargar;
  const marca = `${intento}|${clave ?? ""}`;

  useEffect(() => {
    if (clave === null) {
      return;
    }
    const control = new AbortController();
    let vigente = true;
    cargador.current(control.signal).then(
      (datos) => {
        if (vigente) {
          setGuardado({ marca, estado: { fase: "lista", datos } });
        }
      },
      (error: unknown) => {
        if (vigente && !esCancelacion(error)) {
          setGuardado({ marca, estado: { fase: "error", error: comoErrorDeConsulta(error) } });
        }
      },
    );
    return () => {
      vigente = false;
      control.abort();
    };
  }, [clave, marca]);

  const reintentar = useCallback(() => setIntento((n) => n + 1), []);
  const estado: EstadoDeConsulta<T> = guardado !== null && guardado.marca === marca ? guardado.estado : { fase: "cargando" };
  return [estado, reintentar];
}
