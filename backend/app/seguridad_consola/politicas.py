"""Registro explícito de políticas de la consola local (Fase 10, E10.1).

Cada ruta de `app.main:app` (método y plantilla) tiene aquí una política. La dependencia global
`autorizar_consola` deniega cualquier ruta sin entrada, incluso a un administrador, y la prueba
`tests/unit/seguridad_consola/test_cobertura_politicas.py` falla si una ruta no tiene política, si una
política no tiene ruta o si una excepción de autenticación se usa fuera de su entrada concreta.

Roles: `lector` < `operador` < `administrador`.
- lector: consultas (incluidas las que guardan caché derivada de estadísticas y las exportaciones);
- operador: ejecuciones, generación y verificación;
- administrador: histórico (sorteos y colores), importaciones, configuración y control de automatización.

Las rutas cuyo efecto depende de un parámetro se resuelven por acción (`_accion`): un valor desconocido
no tiene rol y la solicitud se rechaza sin despachar nada.

Las entradas de rutas existentes se generaron desde el inventario efectivo de la base y se revisaron a mano;
las de escritura llevan su efecto y su justificación.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

TIPOS = ("acceso", "sesion", "rol")
_LEE = "Consulta sin efectos de negocio"
_CACHE = "Consulta que calcula y guarda caché derivada en `estadisticas` (idempotente; no cambia el histórico)"
_EXPORTA = "Descarga de datos ya guardados; no escribe"


@dataclass(frozen=True)
class Politica:
    tipo: str
    efecto: str
    justificacion: str
    rol: str | None = None
    fuente: str | None = None  # "ruta" o "formulario" en las políticas por acción
    parametro: str | None = None
    por_valor: Mapping[str, str] = field(default_factory=dict)

    @property
    def por_accion(self) -> bool:
        return self.parametro is not None

    def rol_requerido(self, parametros_ruta: Mapping[str, str], formulario: Mapping[str, str]) -> str | None:
        """Rol mínimo; None si la acción no está reconocida (no se despacha)."""
        if self.tipo != "rol":
            return None
        if not self.por_accion:
            return self.rol
        valores = parametros_ruta if self.fuente == "ruta" else formulario
        valor = valores.get(self.parametro)
        return self.por_valor.get(valor) if isinstance(valor, str) else None


def _rol(rol: str, efecto: str, justificacion: str) -> Politica:
    return Politica("rol", efecto, justificacion, rol=rol)


def _accion(fuente: str, parametro: str, por_valor: dict, efecto: str, justificacion: str) -> Politica:
    return Politica("rol", efecto, justificacion, fuente=fuente, parametro=parametro, por_valor=dict(por_valor))


#: Excepciones de autenticación: entradas concretas, sin prefijos.
EXCEPCIONES = {
    ("GET", "/acceso"): Politica("acceso", "autenticacion", "Formulario de acceso; emite la presesión y su CSRF"),
    ("POST", "/acceso"): Politica("acceso", "autenticacion",
                                  "Envío de credenciales: exige presesión, CSRF y límite de intentos; solo crea la sesión"),
    ("POST", "/salir"): Politica("sesion", "autenticacion", "Cierra la sesión propia; exige sesión y CSRF"),
}

#: Rutas de la consola existentes en la base (223), más las de autenticación de E10.1.
POLITICAS: dict[tuple[str, str], Politica] = {
    ('GET', '/'): _rol('lector', 'lectura', _LEE),
    ('GET', '/juegos'): _rol('lector', 'lectura', _LEE),
    ('GET', '/juegos/{codigo}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/sorteos'): _rol('lector', 'lectura', _LEE),
    ('GET', '/sorteos/tabla'): _rol('lector', 'lectura', _LEE),
    ('GET', '/sorteos/campos'): _rol('lector', 'lectura', _LEE),
    ('GET', '/sorteos/nuevo'): _rol('lector', 'lectura', _LEE),
    ('POST', '/sorteos'): _rol('administrador', 'escritura_negocio', 'Alta manual de sorteo (histórico)'),
    ('GET', '/sorteos/{sorteo_id}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/sorteos/{sorteo_id}/editar'): _rol('lector', 'lectura', _LEE),
    ('PUT', '/sorteos/{sorteo_id}'): _rol('administrador', 'escritura_negocio', 'Edición de sorteo (histórico)'),
    ('DELETE', '/sorteos/{sorteo_id}'): _rol('administrador', 'escritura_negocio', 'Borrado de sorteo (histórico)'),
    ('GET', '/colores'): _rol('lector', 'lectura', _LEE),
    ('POST', '/colores'): _rol('administrador', 'escritura_negocio', 'Alta de color de la paleta (histórico)'),
    ('DELETE', '/colores/{codigo}'): _rol('administrador', 'escritura_negocio', 'Retira un color de la paleta (histórico)'),
    ('GET', '/importacion'): _rol('lector', 'lectura', _LEE),
    ('GET', '/importacion/salud/{codigo_juego}'): _rol('lector', 'lectura', _LEE),
    ('POST', '/importacion/sincronizar/{codigo_juego}'): _rol('administrador', 'importacion', 'Consulta las fuentes oficiales e importa sorteos'),
    ('POST', '/importacion/reimportar-todo/{codigo_juego}'): _rol('administrador', 'importacion', 'Reimporta el histórico completo de un juego'),
    ('POST', '/importacion/reimportar-sorteo/{sorteo_id}'): _rol('administrador', 'importacion', 'Reimporta un sorteo desde la fuente'),
    ('POST', '/importacion/reprocesar-html/{codigo_juego}'): _rol('administrador', 'importacion', 'Reprocesa capturas HTML guardadas y actualiza el histórico'),
    ('GET', '/importacion/validar/{codigo_juego}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/importacion/calidad/{codigo_juego}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/importacion/logs'): _rol('lector', 'lectura', _LEE),
    ('GET', '/estadisticas'): _rol('lector', 'lectura', _LEE),
    ('GET', '/estadisticas/{juego_slug}/resumen'): _rol('lector', 'lectura', _LEE),
    ('GET', '/pronosticos'): _rol('lector', 'lectura', _LEE),
    ('GET', '/pronosticos/{juego_slug}'): _rol('lector', 'lectura', _LEE),
    ('POST', '/pronosticos/{juego_slug}/generar'): _rol('operador', 'ejecucion', 'Genera un pronóstico experimental (Producto 1)'),
    ('GET', '/pronosticos/{juego_slug}/verificar'): _rol('lector', 'lectura', _LEE),
    ('POST', '/pronosticos/{juego_slug}/verificar'): _rol('operador', 'verificacion', 'Verifica un pronóstico experimental (cálculo)'),
    ('GET', '/estadisticas/colorloto/frecuencia-numeros'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/frecuencia-colores'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/frecuencia-pares-numero-color'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/atrasos-numeros'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/atrasos-colores'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/atrasos-pares-numero-color'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/repeticiones-entre-sorteos'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/distribucion-pares-impares'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/distribucion-altos-bajos'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/maximo-repeticion-color'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/distribucion-pares-consecutivos'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/distribucion-racha-maxima'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/distribucion-trios-consecutivos'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/coocurrencia-pares'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/coocurrencia-trios'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/coocurrencia-pares-colores'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/coocurrencia-trios-colores'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/intervalos-historicos-colores'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/distribucion-sumas'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/intervalos-historicos-numeros'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/intervalos-historicos-pares-numero-color'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/frecuencia-colores-por-anio'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/frecuencia-colores-por-mes'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/frecuencia-colores-por-dia-semana'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/frecuencia-pares-numero-color-por-anio'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/frecuencia-pares-numero-color-por-mes'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/frecuencia-pares-numero-color-por-dia-semana'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/distribucion-conteo-color'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/comparacion-frecuencia-numeros-por-ventana'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/comparacion-frecuencia-colores-por-ventana'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/colorloto/comparacion-frecuencia-pares-numero-color-por-ventana'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/{juego_slug}/frecuencia-numeros'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/{juego_slug}/frecuencia-superbalota'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/{juego_slug}/frecuencia-observada-esperada'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/{juego_slug}/atrasos-numeros'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/{juego_slug}/distribucion-pares-impares'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/{juego_slug}/distribucion-altos-bajos'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/{juego_slug}/distribucion-pares-consecutivos'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/{juego_slug}/distribucion-trios-consecutivos'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/{juego_slug}/distribucion-racha-maxima'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/{juego_slug}/repeticiones-entre-sorteos'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/{juego_slug}/coocurrencia-pares'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/{juego_slug}/coocurrencia-trios'): _rol('lector', 'lectura_con_cache', _CACHE),
    ('GET', '/estadisticas/{juego_slug}/panel'): _rol('lector', 'lectura', _LEE),
    ('GET', '/estadisticas/{juego_slug}/frecuencia-numeros-por-anio'): _rol('lector', 'lectura', _LEE),
    ('GET', '/estadisticas/{juego_slug}/frecuencia-numeros-por-mes'): _rol('lector', 'lectura', _LEE),
    ('GET', '/estadisticas/{juego_slug}/frecuencia-numeros-por-dia-semana'): _rol('lector', 'lectura', _LEE),
    ('GET', '/estadisticas/{juego_slug}/frecuencia-superbalota-por-anio'): _rol('lector', 'lectura', _LEE),
    ('GET', '/estadisticas/{juego_slug}/frecuencia-superbalota-por-mes'): _rol('lector', 'lectura', _LEE),
    ('GET', '/estadisticas/{juego_slug}/frecuencia-superbalota-por-dia-semana'): _rol('lector', 'lectura', _LEE),
    ('GET', '/estadisticas/{juego_slug}/atrasos-superbalota'): _rol('lector', 'lectura', _LEE),
    ('GET', '/estadisticas/{juego_slug}/intervalos-historicos-numeros'): _rol('lector', 'lectura', _LEE),
    ('GET', '/estadisticas/{juego_slug}/intervalos-historicos-superbalota'): _rol('lector', 'lectura', _LEE),
    ('GET', '/estadisticas/{juego_slug}/distribucion-sumas'): _rol('lector', 'lectura', _LEE),
    ('GET', '/estadisticas/{juego_slug}/distribucion-decenas'): _rol('lector', 'lectura', _LEE),
    ('GET', '/estadisticas/{juego_slug}/repeticion-superbalota'): _rol('lector', 'lectura', _LEE),
    ('GET', '/estadisticas/{juego_slug}/comparacion-frecuencia-numeros-por-ventana'): _rol('lector', 'lectura', _LEE),
    ('GET', '/estadisticas/{juego_slug}/comparacion-frecuencia-superbalota-por-ventana'): _rol('lector', 'lectura', _LEE),
    ('GET', '/estadisticas/{juego_slug}/pruebas-uniformidad'): _rol('lector', 'lectura', _LEE),
    ('GET', '/estadisticas/{juego_slug}/independencia-pares'): _rol('lector', 'lectura', _LEE),
    ('GET', '/estadisticas/{juego_slug}/independencia-trios'): _rol('lector', 'lectura', _LEE),
    ('GET', '/estadisticas/{juego_slug}/correlaciones'): _rol('lector', 'lectura', _LEE),
    ('GET', '/operacion'): _rol('lector', 'lectura', _LEE),
    ('POST', '/operacion/ejecutar'): _accion('formulario', 'modo', {'local': 'operador', 'actualizar': 'administrador'}, 'ejecucion', 'local genera con el histórico local; actualizar consulta las fuentes e importa sorteos'),
    ('GET', '/operacion/ejecuciones/{identificador}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/operacion/ejecuciones/{identificador}/estado'): _rol('lector', 'lectura', _LEE),
    ('GET', '/rendimiento'): _rol('lector', 'lectura', _LEE),
    ('GET', '/automatizacion'): _rol('lector', 'lectura', _LEE),
    ('GET', '/automatizacion/ejecuciones/{identificador}'): _rol('lector', 'lectura', _LEE),
    ('POST', '/automatizacion/{accion}'): _accion('ruta', 'accion', {'comprobar': 'operador', 'pausar': 'administrador', 'reanudar': 'administrador', 'recuperar': 'administrador'}, 'control_automatizacion', 'Comprobar lanza un ciclo manual; pausar, reanudar y recuperar cambian el control de Fase 6'),
    ('GET', '/laboratorio'): _rol('lector', 'lectura', _LEE),
    ('GET', '/laboratorio/experimentos/{identificador}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/laboratorio/experimentos/{identificador}/estado'): _rol('lector', 'lectura', _LEE),
    ('POST', '/laboratorio/comparar'): _rol('operador', 'ejecucion', 'Lanza una comparación del laboratorio'),
    ('POST', '/laboratorio/experimentos/{clave}/generar'): _rol('operador', 'ejecucion', 'Genera un pronóstico del laboratorio'),
    ('POST', '/laboratorio/experimentos/{clave}/verificar'): _rol('operador', 'verificacion', 'Verifica un experimento (cálculo)'),
    ('GET', '/laboratorio/pronosticos/{clave}'): _rol('lector', 'lectura', _LEE),
    ('POST', '/laboratorio/pronosticos/{clave}/verificar'): _rol('operador', 'verificacion', 'Verifica un pronóstico (cálculo)'),
    ('POST', '/laboratorio/experimentos/{clave}/entrenar'): _rol('operador', 'ejecucion', 'Entrena y registra un modelo'),
    ('GET', '/laboratorio/modelos'): _rol('lector', 'lectura', _LEE),
    ('GET', '/laboratorio/modelo/{clave}'): _rol('lector', 'lectura', _LEE),
    ('POST', '/laboratorio/modelo/{clave}/verificar'): _rol('operador', 'verificacion', 'Verifica un modelo registrado (cálculo)'),
    ('POST', '/laboratorio/modelo/{clave}/generar'): _rol('operador', 'ejecucion', 'Genera un pronóstico con un modelo registrado'),
    ('GET', '/laboratorio/{slug}/seguimiento'): _rol('lector', 'lectura', _LEE),
    ('GET', '/laboratorio/{slug}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/carteras'): _rol('lector', 'lectura', _LEE),
    ('GET', '/carteras/ejecuciones/{identificador}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/carteras/ejecuciones/{identificador}/estado'): _rol('lector', 'lectura', _LEE),
    ('GET', '/carteras/comparaciones/{clave}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/carteras/comparaciones/{clave}/exportar.json'): _rol('lector', 'exportacion', _EXPORTA),
    ('GET', '/carteras/guardadas/{clave}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/carteras/guardadas/{clave}/exportar.csv'): _rol('lector', 'exportacion', _EXPORTA),
    ('GET', '/carteras/guardadas/{clave}/exportar.json'): _rol('lector', 'exportacion', _EXPORTA),
    ('GET', '/carteras/simulaciones/{clave}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/carteras/simulaciones/{clave}/exportar.csv'): _rol('lector', 'exportacion', _EXPORTA),
    ('GET', '/carteras/simulaciones/{clave}/exportar.json'): _rol('lector', 'exportacion', _EXPORTA),
    ('GET', '/carteras/{slug}/seguimiento'): _rol('lector', 'lectura', _LEE),
    ('GET', '/carteras/{slug}'): _rol('lector', 'lectura', _LEE),
    ('POST', '/carteras/comparar'): _rol('operador', 'ejecucion', 'Lanza una comparación de modelos en un proceso trabajador'),
    ('POST', '/carteras/generar'): _rol('operador', 'ejecucion', 'Genera una cartera (artefacto nuevo, inmutable)'),
    ('POST', '/carteras/configuradas'): _rol('operador', 'ejecucion', 'Genera carteras con la configuración vigente'),
    ('POST', '/carteras/guardadas/{clave}/simular'): _rol('operador', 'ejecucion', 'Simula una cartera guardada'),
    ('POST', '/carteras/{slug}/configurar'): _rol('administrador', 'configuracion', 'Cambia la configuración vigente de carteras'),
    ('POST', '/carteras/comparaciones/{clave}/verificar'): _rol('operador', 'verificacion', 'Verifica una comparación guardada (cálculo)'),
    ('POST', '/carteras/guardadas/{clave}/verificar'): _rol('operador', 'verificacion', 'Verifica una cartera guardada (cálculo)'),
    ('POST', '/carteras/simulaciones/{clave}/verificar'): _rol('operador', 'verificacion', 'Verifica una simulación guardada (cálculo)'),
    ('GET', '/resultados'): _rol('lector', 'lectura', _LEE),
    ('GET', '/resultados/informes/{clave}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/resultados/informes/{clave}/exportar.json'): _rol('lector', 'exportacion', _EXPORTA),
    ('GET', '/resultados/{slug}/exportar.csv'): _rol('lector', 'exportacion', _EXPORTA),
    ('GET', '/resultados/{slug}/exportar.json'): _rol('lector', 'exportacion', _EXPORTA),
    ('GET', '/resultados/{slug}/configuracion'): _rol('lector', 'lectura', _LEE),
    ('GET', '/resultados/{slug}'): _rol('lector', 'lectura', _LEE),
    ('POST', '/resultados/{slug}/informes'): _rol('operador', 'ejecucion', 'Guarda un informe inmutable de resultados'),
    ('POST', '/resultados/informes/{clave}/verificar'): _rol('operador', 'verificacion', 'Verifica un informe guardado (cálculo)'),
    ('POST', '/resultados/{slug}/configuracion'): _rol('administrador', 'configuracion', 'Usa una línea como configuración vigente de carteras'),
    ('GET', '/predicciones'): _rol('lector', 'lectura', _LEE),
    ('GET', '/predicciones/ejecuciones/{identificador}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/predicciones/ejecuciones/{identificador}/estado'): _rol('lector', 'lectura', _LEE),
    ('GET', '/predicciones/{slug}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/predicciones/{slug}/fiabilidad'): _rol('lector', 'lectura', _LEE),
    ('POST', '/predicciones/{slug}/generar'): _rol('operador', 'ejecucion', 'Genera cartera y explicación con la configuración vigente'),
    ('POST', '/predicciones/{slug}/explicar'): _rol('operador', 'ejecucion', 'Calcula y guarda la explicación de una cartera'),
    ('GET', '/simulaciones'): _rol('lector', 'lectura', _LEE),
    ('POST', '/simulaciones/simular'): _rol('operador', 'ejecucion', 'Lanza una simulación Monte Carlo'),
    ('GET', '/simulaciones/ejecuciones/{identificador}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/simulaciones/ejecuciones/{identificador}/estado'): _rol('lector', 'lectura', _LEE),
    ('GET', '/simulaciones/resultados/{identificador}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/simulaciones/resultados/{identificador}/exportar.json'): _rol('lector', 'exportacion', _EXPORTA),
    ('GET', '/simulaciones/resultados/{identificador}/exportar.csv'): _rol('lector', 'exportacion', _EXPORTA),
    ('POST', '/simulaciones/resultados/{identificador}/verificar'): _rol('operador', 'verificacion', 'Verifica una simulación guardada (cálculo)'),
    ('GET', '/api/juegos'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/juegos/{codigo}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/sorteos'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/sorteos/{sorteo_id}'): _rol('lector', 'lectura', _LEE),
    ('POST', '/api/sorteos'): _rol('administrador', 'escritura_negocio', 'Alta manual de sorteo (histórico)'),
    ('DELETE', '/api/sorteos/{sorteo_id}'): _rol('administrador', 'escritura_negocio', 'Borrado de sorteo (histórico)'),
    ('GET', '/api/colores'): _rol('lector', 'lectura', _LEE),
    ('POST', '/api/colores'): _rol('administrador', 'escritura_negocio', 'Alta de color de la paleta de ColorLoto (histórico)'),
    ('DELETE', '/api/colores/{codigo}'): _rol('administrador', 'escritura_negocio', 'Retira un color de la paleta (histórico)'),
    ('GET', '/api/estadisticas/{codigo}/resumen'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/pronosticos/{codigo}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/pronosticos/{codigo}/{identificador}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/resultados-observados/{codigo}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/operacion/panel'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/operacion/ejecuciones'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/operacion/ejecuciones/{identificador}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/rendimiento/{codigo}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/laboratorio/catalogo'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/laboratorio/ejecuciones'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/laboratorio/ejecuciones/{identificador}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/laboratorio/experimentos/{clave}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/laboratorio/pronosticos/{clave}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/laboratorio/modelos'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/laboratorio/modelos/{clave}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/laboratorio/{codigo}/experimentos'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/laboratorio/{codigo}/seguimiento'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/laboratorio/{codigo}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/carteras/catalogo'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/carteras/ejecuciones'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/carteras/ejecuciones/{identificador}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/carteras/comparaciones/{clave}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/carteras/guardadas/{clave}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/carteras/guardadas/{clave}/csv'): _rol('lector', 'exportacion', _EXPORTA),
    ('GET', '/api/carteras/simulaciones/{clave}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/carteras/simulaciones/{clave}/csv'): _rol('lector', 'exportacion', _EXPORTA),
    ('GET', '/api/carteras/{codigo}/comparaciones'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/carteras/{codigo}/lineas'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/carteras/{codigo}/configuracion'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/carteras/{codigo}/seguimiento'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/carteras/{codigo}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/resultados'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/resultados/informes/{clave}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/resultados/{codigo}/informes'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/resultados/{codigo}/configuracion'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/resultados/{codigo}/exportar.json'): _rol('lector', 'exportacion', _EXPORTA),
    ('GET', '/api/resultados/{codigo}/exportar.csv'): _rol('lector', 'exportacion', _EXPORTA),
    ('GET', '/api/resultados/{codigo}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/predicciones'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/predicciones/{codigo}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/predicciones/{codigo}/fiabilidad'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/estadisticas/{codigo}/panel'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/estadisticas/{codigo}/descriptivas/{metrica}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/simulaciones/catalogo'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/simulaciones/panel'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/simulaciones/ejecuciones'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/simulaciones/ejecuciones/{identificador}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/simulaciones'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/simulaciones/{identificador}'): _rol('lector', 'lectura', _LEE),
    ('GET', '/api/simulaciones/{identificador}/csv'): _rol('lector', 'exportacion', _EXPORTA),
    ('GET', '/api/simulaciones/{identificador}/json'): _rol('lector', 'exportacion', _EXPORTA),
    ('GET', '/api/simulaciones/{identificador}/verificacion'): _rol('lector', 'lectura', _LEE),
    **EXCEPCIONES,
}

#: Montaje estático admitido sin sesión (solo archivos de `app/static`, tras el límite local).
MONTAJES_ESTATICOS = ("/static",)


def politica(metodo: str, plantilla: str) -> Politica | None:
    return POLITICAS.get(("GET" if metodo == "HEAD" else metodo, plantilla))


def rutas_de(app) -> list[tuple[str, str, str]]:
    """(tipo, método, plantilla) de cada ruta efectiva de la aplicación, recorriendo los routers incluidos.
    Usa la API interna de FastAPI 0.16x (`_IncludedRouter.effective_route_contexts`); si cambia, la prueba
    de cobertura falla en lugar de dar una lista incompleta."""
    from fastapi.routing import _IncludedRouter
    from starlette.routing import Mount

    salida = []
    for r in app.routes:
        if isinstance(r, _IncludedRouter):
            for c in r.effective_route_contexts():
                tipo = type(c.original_route).__name__
                for m in sorted(getattr(c.original_route, "methods", None) or []):
                    salida.append((tipo, m, c.path))
        elif isinstance(r, Mount):
            salida.append(("Mount", "*", r.path))
        else:
            for m in sorted(getattr(r, "methods", None) or []):
                salida.append((type(r).__name__, m, r.path))
    return salida
