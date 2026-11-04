"""Matriz de datos de la Fase 10 (DAT-01), revisada contra el codigo de E10.4.

Cada almacen se identifica por su ajuste `DIRECTORIO_*` (`app.core.config.Settings`). La lectura efectiva de la
API publica (endpoint -> proveedor -> lector -> almacen) esta en `backend/docs/fase10_generaciones.md` y la
comprueba `tests/unit/generaciones/test_inventario_lecturas.py` registrando cada apertura de archivo de los
19 endpoints sobre una generacion sintetica.

Clases:
- `publicable`: entra en la generacion (consulta) y en el respaldo;
- `interno`: no lo lee la API; solo en el respaldo de la fuente (informes de Producto 6);
- `operativo`: estado mutable de ejecucion (registros, progreso, cerrojos, configuracion de Fase 6); solo en el
  respaldo, y se OBSERVA durante la captura para detectar escritores;
- `transitorio`: temporales de publicacion y reservas huerfanas: nunca se copian;
- `secreto`: cuentas y sesiones de la consola (D12), `.env` y configuracion privada: nunca se leen ni se copian.
"""
from __future__ import annotations

from dataclasses import dataclass

PUBLICABLE, INTERNO, OPERATIVO = "publicable", "interno", "operativo"


@dataclass(frozen=True)
class Almacen:
    nombre: str                         # carpeta dentro de `archivos/`
    ajuste: str                         # atributo de Settings
    publicables: tuple[str, ...] | None  # subcarpetas publicables; None = todo el almacen
    operativas: tuple[str, ...] = ()    # subcarpetas de estado operativo
    clase: str = PUBLICABLE             # clase del almacen completo si no tiene subcarpetas publicables


ALMACENES = (
    # Producto 1/3: pronosticos experimentales (procedencia `operacion` de /resultados y /fiabilidad).
    Almacen("pronosticos", "directorio_pronosticos_experimentales", None),
    # Producto 4 y Fase 3: experimentos, pronosticos del laboratorio, modelos registrados y sus estimadores.
    Almacen("laboratorio", "directorio_laboratorio_modelos", ("modelos", "experimentos", "pronosticos"), ("operacion",)),
    # Producto 5: carteras y configuraciones (leidas); comparaciones y simulaciones se incluyen mientras la
    # medicion de lecturas no demuestre que no hacen falta (v2, 2.5).
    Almacen("carteras", "directorio_carteras_modelos", ("carteras", "configuraciones", "comparaciones", "simulaciones"),
            ("operacion",)),
    # Fase 4: explicaciones de las predicciones.
    Almacen("predicciones", "directorio_predicciones_modelos", ("explicaciones",), ("operacion",)),
    # Producto 6: informes guardados (rutas internas de la consola; la API no los lee).
    Almacen("resultados", "directorio_resultados_modelos", (), clase=INTERNO),
    # Estado operativo: Producto 3, Fase 6 y Fase 7 (resultado de Fase 7 en la tabla `simulaciones`).
    Almacen("operacion", "directorio_operacion", (), clase=OPERATIVO),
    Almacen("automatizacion", "directorio_automatizacion", (), clase=OPERATIVO),
    Almacen("simulaciones", "directorio_simulaciones", (), clase=OPERATIVO),
)
POR_NOMBRE = {a.nombre: a for a in ALMACENES}
PUBLICABLES = tuple(a for a in ALMACENES if a.clase == PUBLICABLE)
# Ajustes que la API privada lee de la generacion, y los que nunca deben apuntar a ella.
AJUSTES_DE_CONSULTA = tuple(a.ajuste for a in PUBLICABLES)
SECRETOS = ("consola_seguridad_directorio",)


def clase(almacen: str, relativa: str) -> str:
    """Clase de una ruta (relativa a la raiz del almacen) segun la matriz. Una subcarpeta no clasificada de un
    almacen publicable es `no_clasificado`: la captura se rechaza hasta actualizar la matriz (DAT-01)."""
    a = POR_NOMBRE[almacen]
    if a.clase != PUBLICABLE:
        return a.clase
    if a.publicables is None or relativa in ("", "."):
        return PUBLICABLE
    primera = relativa.split("/", 1)[0]
    if primera in a.publicables:
        return PUBLICABLE
    if primera in a.operativas:
        return OPERATIVO
    return "no_clasificado"
