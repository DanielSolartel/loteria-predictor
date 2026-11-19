import { diccionario, entero, lista, literal, nulable, objeto, texto } from "../api/decodificar";
import { decResumenResultadoGuardado } from "../api/guardados";

const decSincronizacion = objeto({ estado: texto, iniciado_en: texto, finalizado_en: nulable(texto), sorteos_nuevos: entero });
const decEstadoJuego = objeto({
  juego: texto, ultimo_sorteo: nulable(entero), total_sorteos: entero, estado_fase6: texto,
  ultima_comprobacion: nulable(texto), sincronizacion: nulable(decSincronizacion),
});
const decFuente = literal("sinteticos", "fase6");
export type Fuente = ReturnType<typeof decFuente>;
export const decOrigen = objeto({ datos: decFuente, apuestas: nulable(objeto({ parejas: diccionario(texto) })) });
export const decEstadoReferencia = objeto({ datos: decFuente, fecha_referencia: nulable(texto), juegos: lista(decEstadoJuego) });

export const decComparacion = objeto({
  juego: texto,
  comparacion: objeto({
    tipo: texto, lineas: lista(texto), estado: texto, objetivos_comunes: lista(entero), motivo: nulable(texto),
    por_linea: diccionario(decResumenResultadoGuardado),
  }),
  resumenes: diccionario(decResumenResultadoGuardado),
});
