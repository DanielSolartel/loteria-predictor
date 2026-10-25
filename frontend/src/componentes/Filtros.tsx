/**
 * Filtros en la URL. La consulta del navegador es la unica fuente: recargar,
 * entrar por enlace directo o usar atras/adelante reproduce la misma vista.
 * Solo se reenvian a la API los nombres que admite cada ruta; la validacion
 * semantica es de la API (422).
 */
import { type FormEvent, useState } from "react";
import { useSearchParams } from "react-router-dom";

/** Valores presentes en la URL para los nombres indicados (los demas se ignoran). */
export function useFiltros<N extends string>(nombres: readonly N[]): [Record<N, string | null>, (nuevos: Partial<Record<N, string | null>>) => void] {
  const [parametros, setParametros] = useSearchParams();
  const valores = Object.fromEntries(nombres.map((n) => [n, parametros.get(n)])) as Record<N, string | null>;
  const cambiar = (nuevos: Partial<Record<N, string | null>>) => {
    const siguiente = new URLSearchParams();
    for (const n of nombres) {
      const v = n in nuevos ? nuevos[n] : valores[n];
      if (v !== null && v !== undefined && v !== "") {
        siguiente.set(n, v);
      }
    }
    setParametros(siguiente);
  };
  return [valores, cambiar];
}

/** Corte opcional `hasta_numero_sorteo` del resumen, el panel y las metricas. */
export function FormularioDeCorte({ valor, aplicar }: { valor: string | null; aplicar: (v: string | null) => void }) {
  const [texto, setTexto] = useState(valor ?? "");
  const enviar = (e: FormEvent) => {
    e.preventDefault();
    aplicar(texto.trim() === "" ? null : texto.trim());
  };
  return (
    <form className="row g-2 align-items-end mb-3" onSubmit={enviar} aria-label="Corte de la muestra">
      <div className="col-auto">
        <label className="form-label small mb-0" htmlFor="corte">
          Corte (hasta el sorteo)
        </label>
        <input
          className="form-control form-control-sm"
          id="corte"
          type="number"
          min={1}
          inputMode="numeric"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
        />
      </div>
      <div className="col-auto">
        <button className="btn btn-sm btn-marca me-2" type="submit">
          Aplicar
        </button>
        {valor !== null ? (
          <button className="btn btn-sm btn-outline-secondary" type="button" onClick={() => aplicar(null)}>
            Quitar corte
          </button>
        ) : null}
      </div>
    </form>
  );
}
