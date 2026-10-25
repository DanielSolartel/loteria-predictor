/**
 * Estados de una consulta: cargando, error (por codigo estable) y contenido.
 * Los mensajes son los de la API o la pasarela; aqui solo se explica que
 * significan para quien consulta. No hay reintentos automaticos.
 */
import { type ReactNode, useCallback, useEffect, useState } from "react";
import type { ErrorDeConsulta } from "../api/cliente";
import type { EstadoDeConsulta } from "../usos/consulta";
import { Cargando } from "./comunes";

const EXPLICACIONES: Readonly<Record<string, string>> = {
  red_no_disponible: "La pasarela local no respondió. Comprueba que está en marcha en este equipo.",
  no_autenticado:
    "La pasarela no tiene una clave válida para la API. Se corrige en la configuración privada del servidor, no en el navegador.",
  cliente_no_local: "La pasarela solo atiende peticiones de este mismo equipo.",
  host_no_permitido: "La dirección usada no es una de las admitidas por la pasarela.",
  origen_no_permitido: "La petición procede de un origen no admitido por la pasarela.",
  ruta_no_disponible: "Esa consulta no existe en la API pública v1.",
  ruta_no_valida: "La dirección contiene caracteres o segmentos no admitidos.",
  no_encontrado: "El recurso pedido no existe en la API.",
  parametro_no_valido: "Algún filtro o parámetro no es válido.",
  alterado: "Integridad alterada: el recurso guardado no coincide con su huella y no se muestra.",
  no_disponible: "El recurso guardado no se puede leer ahora.",
  incompatible: "El recurso guardado no es compatible con esta versión.",
  sin_configuracion: "El juego no tiene configuración de predicción vigente.",
  limite_excedido: "Se alcanzó el límite de consultas por minuto de la API.",
  error_interno: "La API tuvo un error interno. El identificador de solicitud permite localizarlo en sus registros.",
  respuesta_no_valida: "La respuesta recibida no tiene el formato esperado.",
  respuesta_demasiado_grande: "La respuesta de la API supera el tamaño que admite la pasarela.",
  base_no_disponible: "La base de datos de la API no está disponible ahora.",
  no_configurada: "La API pública no tiene claves configuradas.",
  api_no_disponible: "La pasarela no pudo conectar con la API pública.",
  api_sin_respuesta: "La API pública no respondió a tiempo.",
  pasarela_no_configurada: "La pasarela no tiene configurada su clave privada para la API.",
  pasarela_ocupada: "La pasarela está atendiendo el máximo de consultas simultáneas.",
  estructura_no_reconocida: "La respuesta no tiene la estructura que esta interfaz sabe mostrar; no se muestra a medias.",
  error_de_la_interfaz: "La interfaz no pudo procesar la respuesta.",
};

function CuentaAtras({ segundos, alTerminar }: { segundos: number; alTerminar: () => void }) {
  const [restantes, setRestantes] = useState(segundos);
  useEffect(() => {
    if (restantes <= 0) {
      alTerminar();
      return;
    }
    const t = setTimeout(() => setRestantes((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [restantes, alTerminar]);
  return restantes > 0 ? <span aria-live="polite">Podrás reintentar en {restantes} s.</span> : null;
}

export function VistaDeError({ error, reintentar }: { error: ErrorDeConsulta; reintentar?: () => void }) {
  const espera = error.reintentarEn;
  const [habilitado, setHabilitado] = useState(espera === null || espera <= 0);
  const habilitar = useCallback(() => setHabilitado(true), []);
  const grave = error.codigo === "alterado" || error.estadoHttp === null || (error.estadoHttp ?? 0) >= 500;
  // Solo tiene sentido repetir lo transitorio (cuota, servidor, red); un 4xx daria lo mismo.
  const transitorio = error.estadoHttp === null || error.estadoHttp === 429 || error.estadoHttp >= 500;
  return (
    <div className={`alert text-break ${grave ? "alert-danger" : "alert-warning"}`} role="alert" data-codigo={error.codigo}>
      <h2 className="h6 mb-1">
        {error.estadoHttp !== null ? `Error ${error.estadoHttp}` : "Sin conexión"} · <code>{error.codigo}</code>
      </h2>
      <p className="mb-1">{error.message}</p>
      {EXPLICACIONES[error.codigo] ? <p className="small mb-1">{EXPLICACIONES[error.codigo]}</p> : null}
      {error.detalles && error.detalles.length > 0 ? (
        <ul className="small mb-1">
          {error.detalles.map((d, i) => (
            <li key={i}>
              {Array.isArray(d.ubicacion) ? d.ubicacion.join(" › ") : "parámetro"}:{" "}
              {typeof d.mensaje === "string" ? d.mensaje : JSON.stringify(d)}
            </li>
          ))}
        </ul>
      ) : null}
      {error.codigo === "limite_excedido" ? (
        <p className="small mb-1">
          Esperar no garantiza la cuota: otras pestañas o consultas con la misma clave también la consumen.
        </p>
      ) : null}
      {error.solicitud ? (
        <p className="small text-muted mb-1">
          Solicitud: <code>{error.solicitud}</code>
        </p>
      ) : null}
      {reintentar && transitorio ? (
        <p className="mb-0 small">
          {espera !== null && espera > 0 && !habilitado ? (
            <CuentaAtras segundos={espera} alTerminar={habilitar} />
          ) : null}{" "}
          <button type="button" className="btn btn-sm btn-outline-secondary" disabled={!habilitado} onClick={reintentar}>
            Reintentar
          </button>
        </p>
      ) : null}
    </div>
  );
}

/** Muestra el contenido de una consulta lista o su estado. */
export function Consulta<T>({
  estado,
  reintentar,
  que,
  children,
}: {
  estado: EstadoDeConsulta<T>;
  reintentar: () => void;
  que: string;
  children: (datos: T) => ReactNode;
}) {
  if (estado.fase === "cargando") {
    return <Cargando que={que} />;
  }
  if (estado.fase === "error") {
    return <VistaDeError error={estado.error} reintentar={reintentar} />;
  }
  return <>{children(estado.datos)}</>;
}
