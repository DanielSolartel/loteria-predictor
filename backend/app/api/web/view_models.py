"""
View Models del adaptador web.

Ninguna plantilla Jinja2 recibe una entidad de dominio directamente.
Recibe el resultado de estas funciones: dicts/dataclasses simples,
con formato ya pensado para mostrarse (fechas legibles, listas ya
armadas, flags de UI). Esto mantiene al dominio ignorante de que
existe una interfaz HTML, y evita lógica de presentación dispersa
dentro de los templates.
"""
from __future__ import annotations

from app.application.use_cases.consultar_juegos import JuegoConReglas
from app.domain.entities.juego import Juego
from app.domain.entities.sorteo import Sorteo
from app.domain.value_objects.color import Color

MESES_ES = [
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _fecha_legible(fecha) -> str:
    return f"{fecha.day} de {MESES_ES[fecha.month]} de {fecha.year}"


def juego_a_vm(juego: Juego) -> dict:
    return {
        "id": str(juego.id),
        "codigo": juego.codigo,
        "nombre": juego.nombre,
        "rango": f"{juego.rango_min}–{juego.rango_max}",
        "cantidad_numeros": juego.cantidad_numeros,
        "tiene_superbalota": juego.tiene_superbalota,
        "superbalota_rango": (
            f"{juego.superbalota_min}–{juego.superbalota_max}" if juego.tiene_superbalota else None
        ),
        "tiene_color": juego.tiene_color,
        "permite_repeticion": juego.permite_repeticion,
        "activo": juego.activo,
    }


def juego_con_reglas_a_vm(datos: JuegoConReglas) -> dict:
    vm = juego_a_vm(datos.juego)
    vm["espacio_muestral"] = f"{datos.espacio_muestral:,}".replace(",", ".")
    vm["dimensiones"] = datos.dimensiones
    return vm


def sorteo_a_vm(sorteo: Sorteo) -> dict:
    numeros = list(sorteo.resultado.numeros)
    pares = [
        {"numero": p.numero, "color_codigo": p.color.codigo, "color_nombre": p.color.nombre}
        for p in sorteo.resultado.pares
    ]
    return {
        "id": str(sorteo.id),
        "juego_id": str(sorteo.juego_id),
        "numero_sorteo": sorteo.numero_sorteo,
        "fecha": sorteo.fecha.isoformat(),
        "fecha_legible": _fecha_legible(sorteo.fecha),
        "dia_semana": sorteo.dia_semana.capitalize(),
        "numeros": numeros,
        "superbalota": sorteo.resultado.superbalota,
        "pares": pares,
        "fuente": sorteo.fuente or "—",
    }


def color_a_vm(color: Color) -> dict:
    return {
        "codigo": color.codigo,
        "nombre": color.nombre,
        "activo": color.activo,
        "vigente_desde": color.vigente_desde.isoformat() if color.vigente_desde else None,
        "vigente_hasta": color.vigente_hasta.isoformat() if color.vigente_hasta else None,
        "css_class": f"color-swatch color-{color.codigo.lower()}",
    }


def _frecuencia_a_vm_base(estadistica, rango_min: int, rango_max: int) -> dict:
    """Helper compartido entre `frecuencia_numeros_a_vm` y
    `frecuencia_superbalota_a_vm`: ambas transforman una
    `EstadisticaCalculada` cuyo `resultado["filas"]` es una lista de
    `FrecuenciaObservada` serializada, con exactamente la misma
    forma -la única diferencia entre ambas visualizaciones es de qué
    pool proviene el resultado (números vs. superbalota), algo que ya
    quedó resuelto en la capa de orquestación (Etapa T/V). Ordena
    NUMÉRICAMENTE por el valor (no por frecuencia), nunca recalcula
    ninguna frecuencia, y no muta `estadistica.resultado["filas"]`
    (crea una lista nueva vía `sorted`)."""
    filas_ordenadas = sorted(estadistica.resultado["filas"], key=lambda f: int(f["valor"]))

    return {
        "rango_min": rango_min,
        "rango_max": rango_max,
        "hasta_numero_sorteo": estadistica.hasta_numero_sorteo,
        "total_sorteos": filas_ordenadas[0]["total_sorteos"] if filas_ordenadas else 0,
        "calculado_en": estadistica.calculado_en.isoformat() if estadistica.calculado_en else None,
        "filas": filas_ordenadas,
        "chart_labels": [f["valor"] for f in filas_ordenadas],
        "chart_valores": [f["apariciones"] for f in filas_ordenadas],
    }


def frecuencia_numeros_a_vm(estadistica, rango_min: int, rango_max: int, juego: Juego) -> dict:
    """Transforma una `EstadisticaCalculada` de tipo "frecuencia_numeros"
    (Etapa T) en un view model listo para la plantilla. Ver
    `_frecuencia_a_vm_base` para el detalle del ordenamiento/formato.
    `juego` es la entidad REAL resuelta por el router -nunca se
    hardcodea código ni nombre aquí (corrección de la generalización
    a Baloto Revancha/MiLoto: antes decía "BALOTO" sin importar qué
    juego se hubiera calculado)."""
    return {
        "juego_codigo": juego.codigo, "juego_nombre": juego.nombre,
        **_frecuencia_a_vm_base(estadistica, rango_min, rango_max),
    }


def frecuencia_superbalota_a_vm(estadistica, rango_min: int, rango_max: int, juego: Juego) -> dict:
    """Transforma una `EstadisticaCalculada` de tipo
    "frecuencia_superbalota" (Etapa V) en un view model listo para la
    plantilla -mismo formato exacto que `frecuencia_numeros_a_vm`,
    reutilizando el helper compartido. `rango_min`/`rango_max` deben
    provenir de `juego_dominio.superballot_range` (nunca hardcodeados
    1-16 aquí). `juego` real, nunca "BALOTO" fijo."""
    return {
        "juego_codigo": juego.codigo, "juego_nombre": juego.nombre,
        **_frecuencia_a_vm_base(estadistica, rango_min, rango_max),
    }


def tabla_frecuencia_numeros_a_vm(
    estadistica, rango_min: int, rango_max: int, cantidad_numeros: int, juego: Juego,
) -> dict:
    """Transforma una `EstadisticaCalculada` de tipo
    "tabla_frecuencia_numeros" (comparación observado vs. esperado)
    en un view model listo para la plantilla. NO reutiliza
    `_frecuencia_a_vm_base`: la forma de cada fila es distinta
    (`FilaFrecuencia` anidada, no `FrecuenciaObservada` plana) -forzar
    el mismo helper habría mezclado dos contratos distintos.

    Mantiene observado y teórico SEPARADOS en todo momento -nunca los
    fusiona en un solo campo ambiguo, ni aquí ni en el template:
    `chart_observada` viene de `frecuencia_observada.frecuencia_relativa`,
    `chart_teorica` viene de `probabilidad_teorica.probabilidad`, ambas
    como PROPORCIONES en [0,1] (misma unidad, comparables
    directamente) -el formato a porcentaje es responsabilidad de
    Chart.js/Jinja al presentar, nunca de este view model. `diferencia`
    conserva su signo tal cual la calculó el motor
    (observada - teórica), sin ninguna clasificación de "bueno/malo".
    `juego` es la entidad real resuelta por el router -nunca "BALOTO"
    fijo (corrección de la generalización)."""
    filas_ordenadas = sorted(estadistica.resultado["filas"], key=lambda f: int(f["valor"]))

    total_sorteos = filas_ordenadas[0]["frecuencia_observada"]["total_sorteos"] if filas_ordenadas else 0
    n = rango_max - rango_min + 1
    metodo_teorico = (
        filas_ordenadas[0]["probabilidad_teorica"]["metodo"] if filas_ordenadas
        else f"K/N = {cantidad_numeros}/{n}"
    )

    return {
        "juego_codigo": juego.codigo,
        "juego_nombre": juego.nombre,
        "rango_min": rango_min,
        "rango_max": rango_max,
        "cantidad_numeros": cantidad_numeros,
        "metodo_teorico": metodo_teorico,
        "hasta_numero_sorteo": estadistica.hasta_numero_sorteo,
        "total_sorteos": total_sorteos,
        "calculado_en": estadistica.calculado_en.isoformat() if estadistica.calculado_en else None,
        "filas": filas_ordenadas,
        "chart_labels": [f["valor"] for f in filas_ordenadas],
        "chart_observada": [f["frecuencia_observada"]["frecuencia_relativa"] for f in filas_ordenadas],
        "chart_teorica": [f["probabilidad_teorica"]["probabilidad"] for f in filas_ordenadas],
    }


# =====================================================================
# Navegación de dos niveles (juego + métrica) para las tres páginas
# estadísticas -construida enteramente aquí (nunca en el template ni
# en JavaScript). Alcance deliberadamente cerrado a 3 juegos (nunca
# ColorLoto, decisión de producto explícita para esta etapa).
# =====================================================================

_SLUG_A_CODIGO: dict[str, str] = {
    "baloto": "BALOTO",
    "baloto-revancha": "BALOTO_REVANCHA",
    "miloto": "MILOTO",
}
_NOMBRE_VISIBLE_POR_SLUG: dict[str, str] = {
    "baloto": "Baloto",
    "baloto-revancha": "Baloto Revancha",
    "miloto": "MiLoto",
}
_ETIQUETA_METRICA: dict[str, str] = {
    "frecuencia-numeros": "Números principales",
    "frecuencia-superbalota": "Superbalota",
    "frecuencia-observada-esperada": "Observada vs. esperada",
    "atrasos-numeros": "Distancia desde la última aparición",
    "distribucion-pares-impares": "Pares e impares",
    "distribucion-altos-bajos": "Distribución inferior/superior",
    "distribucion-pares-consecutivos": "Distribución de pares consecutivos",
    "distribucion-racha-maxima": "Racha máxima de números consecutivos",
    "repeticiones-entre-sorteos": "Repeticiones entre sorteos consecutivos",
}


def _etiqueta_composicion(cantidad_pares: int, cantidad_numeros: int) -> str:
    """Singular/plural correcto para pares e impares por separado -
    "1 par / 4 impares", "0 pares / 5 impares", nunca una etiqueta
    ambigua como solo el número."""
    cantidad_impares = cantidad_numeros - cantidad_pares
    texto_pares = "1 par" if cantidad_pares == 1 else f"{cantidad_pares} pares"
    texto_impares = "1 impar" if cantidad_impares == 1 else f"{cantidad_impares} impares"
    return f"{texto_pares} / {texto_impares}"


def distribucion_pares_impares_a_vm(estadistica, cantidad_numeros: int, juego: Juego) -> dict:
    """Transforma una `EstadisticaCalculada` de tipo
    "distribucion_pares_impares" (Etapa Y) en un view model listo
    para la plantilla. Nunca recalcula la métrica.

    "Composición histórica más frecuente" (Etapa Y, transformación de
    PRESENTACIÓN, no un cálculo estadístico nuevo): si no hay datos
    (`total_sorteos == 0`), None -el template debe mostrar "N/D", sin
    asumir que las categorías con 0 apariciones están "empatadas" en
    ese caso. Con datos, se incluyen TODAS las categorías con el
    máximo de apariciones -nunca se elige una arbitrariamente en caso
    de empate."""
    filas_ordenadas = sorted(estadistica.resultado["filas"], key=lambda f: int(f["valor"]))

    total_sorteos = filas_ordenadas[0]["total_sorteos"] if filas_ordenadas else 0

    filas_presentacion = []
    for f in filas_ordenadas:
        cantidad_pares = int(f["valor"])
        filas_presentacion.append({
            "cantidad_pares": cantidad_pares,
            "cantidad_impares": cantidad_numeros - cantidad_pares,
            "etiqueta": _etiqueta_composicion(cantidad_pares, cantidad_numeros),
            "apariciones": f["apariciones"],
            "frecuencia_relativa": f["frecuencia_relativa"],
        })

    composicion_mas_frecuente = None
    if total_sorteos > 0 and filas_presentacion:
        maximo = max(f["apariciones"] for f in filas_presentacion)
        if maximo > 0:
            composicion_mas_frecuente = [
                f["etiqueta"] for f in filas_presentacion if f["apariciones"] == maximo
            ]

    return {
        "juego_codigo": juego.codigo,
        "juego_nombre": juego.nombre,
        "cantidad_numeros": cantidad_numeros,
        "hasta_numero_sorteo": estadistica.hasta_numero_sorteo,
        "total_sorteos": total_sorteos,
        "calculado_en": estadistica.calculado_en.isoformat() if estadistica.calculado_en else None,
        "filas": filas_presentacion,
        "composicion_mas_frecuente": composicion_mas_frecuente,
        "chart_labels": [f["etiqueta"] for f in filas_presentacion],
        "chart_porcentajes": [f["frecuencia_relativa"] * 100 for f in filas_presentacion],
        "chart_apariciones": [f["apariciones"] for f in filas_presentacion],
    }


def _punto_de_corte_altos_bajos_vm(rango_min: int, rango_max: int) -> int:
    """Réplica exacta de `_punto_de_corte_altos_bajos` del motor
    (`app/application/estadisticas/motor/distribuciones.py`) -no se
    importa la función privada del motor a través del límite de
    módulo (misma convención ya seguida en el resto del proyecto para
    símbolos con guion bajo); esta es una fórmula trivial de una
    línea, verificada exhaustivamente contra la función real del
    motor en la auditoría previa a esta etapa. Cambiar la fórmula del
    motor sin actualizar esta réplica sería detectado de inmediato
    por los tests de esta etapa, que comparan ambas contra los mismos
    casos."""
    mitad = (rango_max - rango_min + 1) // 2
    return rango_min + mitad - 1


def _etiqueta_inferior_superior(cantidad_inferiores: int, cantidad_numeros: int) -> str:
    """Singular/plural correcto para inferiores/superiores por
    separado -mismo patrón exacto ya usado en
    `_etiqueta_composicion` para pares/impares."""
    cantidad_superiores = cantidad_numeros - cantidad_inferiores
    texto_inf = "1 inferior" if cantidad_inferiores == 1 else f"{cantidad_inferiores} inferiores"
    texto_sup = "1 superior" if cantidad_superiores == 1 else f"{cantidad_superiores} superiores"
    return f"{texto_inf} / {texto_sup}"


def _etiqueta_pares_consecutivos(cantidad: int) -> str:
    """Singular/plural correcto: '0 pares consecutivos', '1 par
    consecutivo', '2 pares consecutivos'... Nunca una etiqueta
    ambigua como solo el número, y nunca confundida con frecuencia
    individual de un número (de ahí el nombre completo, no
    "consecutivos" a secas)."""
    return "1 par consecutivo" if cantidad == 1 else f"{cantidad} pares consecutivos"


def _etiqueta_racha_maxima(longitud: int) -> str:
    """Singular/plural correcto: 'Racha de 1 número', 'Racha de 2
    números'... Nunca se reutiliza literalmente la etiqueta de pares
    consecutivos -representan semánticas distintas (enlaces
    adyacentes vs. longitud del bloque más largo)."""
    return "Racha de 1 número" if longitud == 1 else f"Racha de {longitud} números"


def _etiqueta_trios_consecutivos(cantidad: int) -> str:
    """Singular/plural correcto: 'Sin tríos consecutivos', '1 trío
    consecutivo', '2 tríos consecutivos'... Nunca una etiqueta
    ambigua como solo el número, y nunca confundida con "cantidad de
    números consecutivos" (longitud de racha) ni con la etiqueta de
    pares consecutivos -representan semánticas distintas: un trío
    exige tres números adyacentes, no dos."""
    if cantidad == 0:
        return "Sin tríos consecutivos"
    return "1 trío consecutivo" if cantidad == 1 else f"{cantidad} tríos consecutivos"


def _etiqueta_repeticiones(cantidad: int) -> str:
    """Singular/plural correcto: '0 números repetidos', '1 número
    repetido', 'N números repetidos'."""
    return "1 número repetido" if cantidad == 1 else f"{cantidad} números repetidos"


def distribucion_repeticiones_entre_sorteos_a_vm(
    estadistica, rango_min: int, rango_max: int, cantidad_numeros: int, juego: Juego,
) -> dict:
    """Transforma una `EstadisticaCalculada` de tipo
    "distribucion_repeticiones_entre_sorteos" (Etapa AC) en un view
    model listo para la plantilla. Nunca recalcula la métrica, nunca
    consulta repositorios, nunca llama al motor.

    Renombra `total_sorteos` (nombre del campo persistido, sin
    cambiar el contrato/dataclass) a `total_transiciones` -SOLO en
    presentación- porque para esta métrica ese campo NO representa
    la cantidad de sorteos del histórico, sino la cantidad de
    transiciones válidas (numero_sorteo_actual ==
    numero_sorteo_anterior + 1). Ver docstring de la receta y del
    motor para la justificación completa.

    "Repetición más frecuente" sigue el mismo criterio ya validado
    cuatro veces: excluye sin transiciones, incluye TODAS las
    categorías empatadas en el máximo, nunca elige una arbitraria."""
    filas_ordenadas = sorted(estadistica.resultado["filas"], key=lambda f: int(f["valor"]))

    total_transiciones = filas_ordenadas[0]["total_sorteos"] if filas_ordenadas else 0

    filas_presentacion = []
    for f in filas_ordenadas:
        cantidad_repetidos = int(f["valor"])
        filas_presentacion.append({
            "cantidad_repetidos": cantidad_repetidos,
            "etiqueta": _etiqueta_repeticiones(cantidad_repetidos),
            "transiciones": f["apariciones"],
            "frecuencia_relativa": f["frecuencia_relativa"],
        })

    repeticion_mas_frecuente = None
    if total_transiciones > 0 and filas_presentacion:
        maximo = max(f["transiciones"] for f in filas_presentacion)
        if maximo > 0:
            repeticion_mas_frecuente = [
                f["etiqueta"] for f in filas_presentacion if f["transiciones"] == maximo
            ]

    return {
        "juego_codigo": juego.codigo,
        "juego_nombre": juego.nombre,
        "rango_min": rango_min,
        "rango_max": rango_max,
        "cantidad_numeros": cantidad_numeros,
        "hasta_numero_sorteo": estadistica.hasta_numero_sorteo,
        "total_transiciones": total_transiciones,
        "calculado_en": estadistica.calculado_en.isoformat() if estadistica.calculado_en else None,
        "filas": filas_presentacion,
        "repeticion_mas_frecuente": repeticion_mas_frecuente,
        "chart_labels": [f["etiqueta"] for f in filas_presentacion],
        "chart_porcentajes": [f["frecuencia_relativa"] * 100 for f in filas_presentacion],
        "chart_transiciones": [f["transiciones"] for f in filas_presentacion],
    }


def _etiqueta_numero_colorloto(cantidad_repetidos_o_valor: int) -> str:
    return str(cantidad_repetidos_o_valor)


def frecuencia_numeros_colorloto_a_vm(estadistica, rango_min: int, rango_max: int, juego: Juego) -> dict:
    """Transforma una `EstadisticaCalculada` de tipo
    "frecuencia_numeros_colorloto" (Etapa AE-1) en un view model listo
    para la plantilla. Nunca recalcula la métrica, nunca consulta
    repositorios, nunca llama al motor -transformación pura sobre el
    resultado ya serializado.

    `total_sorteos` se presenta como "Sorteos analizados"; la razón
    `apariciones / total_sorteos` (ya calculada por el motor como
    `frecuencia_relativa`, aquí solo renombrada para la interfaz) se
    presenta como "Apariciones promedio por sorteo" -NUNCA
    "porcentaje" ni con símbolo `%`: en ColorLoto un número puede
    repetirse dentro de un mismo sorteo (contrato del dominio
    confirmado, no un supuesto), así que esta magnitud puede legítimamente
    superar 1.0 -no es una probabilidad ni una frecuencia acotada a
    [0,1].

    "Número(s) con mayor promedio" sigue el mismo criterio ya usado
    4 veces: excluye sin sorteos, incluye TODAS las categorías
    empatadas en el máximo, nunca elige una arbitraria."""
    filas_ordenadas = sorted(estadistica.resultado["filas"], key=lambda f: int(f["valor"]))

    total_sorteos = filas_ordenadas[0]["total_sorteos"] if filas_ordenadas else 0

    filas_presentacion = []
    for f in filas_ordenadas:
        filas_presentacion.append({
            "numero": int(f["valor"]),
            "apariciones": f["apariciones"],
            "apariciones_promedio": f["frecuencia_relativa"],
            "apariciones_promedio_texto": f"{f['frecuencia_relativa']:.2f}",
        })

    numero_mayor_promedio = None
    if total_sorteos > 0 and filas_presentacion:
        maximo = max(f["apariciones_promedio"] for f in filas_presentacion)
        if maximo > 0:
            numero_mayor_promedio = [
                str(f["numero"]) for f in filas_presentacion if f["apariciones_promedio"] == maximo
            ]

    return {
        "juego_codigo": juego.codigo,
        "juego_nombre": juego.nombre,
        "rango_min": rango_min,
        "rango_max": rango_max,
        "hasta_numero_sorteo": estadistica.hasta_numero_sorteo,
        "total_sorteos": total_sorteos,
        "calculado_en": estadistica.calculado_en.isoformat() if estadistica.calculado_en else None,
        "filas": filas_presentacion,
        "numero_mayor_promedio": numero_mayor_promedio,
        "chart_labels": [str(f["numero"]) for f in filas_presentacion],
        "chart_promedios": [f["apariciones_promedio"] for f in filas_presentacion],
        "chart_apariciones": [f["apariciones"] for f in filas_presentacion],
    }


# Mapeo CERRADO y seguro de código de color -> valor hexadecimal para
# las barras de la gráfica. `Color` (value object) no tiene ningún
# campo de color visual -este mapeo vive aquí, en la capa de
# presentación, nunca en el dominio. Fallback gris neutro para
# cualquier código no reconocido (paleta ampliada en el futuro, o dato
# corrupto que ya pasó la validación de integridad por algún motivo
# excepcional) -nunca falla ni deja una barra sin color.
_COLOR_HEX_SEGURO = {
    "ROJO": "#DC2626",
    "AZUL": "#2563EB",
    "VERDE": "#16A34A",
    "NEGRO": "#1F2937",
    "BLANCO": "#E5E7EB",
    "AMARILLO": "#EAB308",
}
_COLOR_HEX_FALLBACK = "#9CA3AF"


def _color_hex_seguro(codigo: str) -> str:
    return _COLOR_HEX_SEGURO.get(codigo, _COLOR_HEX_FALLBACK)


def frecuencia_colores_colorloto_a_vm(estadistica, juego: Juego) -> dict:
    """Transforma una `EstadisticaCalculada` de tipo
    "frecuencia_colores_colorloto" (Etapa AE-2) en un view model listo
    para la plantilla. Nunca recalcula la métrica, nunca consulta
    repositorios, nunca llama al motor -transformación pura sobre el
    resultado ya serializado. Mismo criterio semántico que
    `frecuencia_numeros_colorloto_a_vm`: "Apariciones promedio por
    sorteo" (nunca "porcentaje"), puede legítimamente superar 1.0
    porque un color puede repetirse dentro de un mismo sorteo.

    Orden determinista: se conserva tal cual llega en `resultado`
    -ya ordenado alfabéticamente por código por el propio motor
    (`sorted(colores_a_reportar)`), nunca reordenado aquí.

    Código y nombre legible: el catálogo real solo garantiza
    `codigo` de forma fiable en la salida del motor (`FrecuenciaObservada.valor`)
    -el "nombre legible" se deriva de ese mismo código con un
    `.title()` simple y seguro (mismo criterio ya usado en varios
    fixtures del proyecto: "ROJO" -> "Rojo"), sin depender de una
    consulta adicional al catálogo completo (que ya no está disponible
    en esta capa, solo el resultado ya serializado)."""
    filas_ordenadas = estadistica.resultado["filas"]

    total_sorteos = filas_ordenadas[0]["total_sorteos"] if filas_ordenadas else 0

    filas_presentacion = []
    for f in filas_ordenadas:
        codigo = f["valor"]
        filas_presentacion.append({
            "codigo": codigo,
            "nombre": codigo.title(),
            "color_hex": _color_hex_seguro(codigo),
            "apariciones": f["apariciones"],
            "apariciones_promedio": f["frecuencia_relativa"],
            "apariciones_promedio_texto": f"{f['frecuencia_relativa']:.2f}",
        })

    color_mayor_promedio = None
    if total_sorteos > 0 and filas_presentacion:
        maximo = max(f["apariciones_promedio"] for f in filas_presentacion)
        if maximo > 0:
            color_mayor_promedio = [
                f["nombre"] for f in filas_presentacion if f["apariciones_promedio"] == maximo
            ]

    return {
        "juego_codigo": juego.codigo,
        "juego_nombre": juego.nombre,
        "hasta_numero_sorteo": estadistica.hasta_numero_sorteo,
        "total_sorteos": total_sorteos,
        "calculado_en": estadistica.calculado_en.isoformat() if estadistica.calculado_en else None,
        "filas": filas_presentacion,
        "color_mayor_promedio": color_mayor_promedio,
        "chart_labels": [f["nombre"] for f in filas_presentacion],
        "chart_promedios": [f["apariciones_promedio"] for f in filas_presentacion],
        "chart_apariciones": [f["apariciones"] for f in filas_presentacion],
        "chart_colores": [f["color_hex"] for f in filas_presentacion],
    }


def _deserializar_par_numero_color(valor: str) -> tuple[int, str]:
    """Deserializa el contrato ya existente del motor
    (`f"{numero}-{color_codigo}"`, Paso 13) de forma INEQUÍVOCA.
    `maxsplit=1` sobre el PRIMER guión es correcto siempre: el número
    es un entero positivo (rango 1..7) sin guión propio, así que
    precede siempre al primer guión de la cadena completa -incluso si
    un futuro código de color contuviera guiones, el resto de la
    cadena (después del primer corte) se conserva íntegro como
    segundo elemento. Único punto de parseo -reutilizado por toda
    esta capa, nunca reimplementado en el template."""
    numero_str, color_codigo = valor.split("-", maxsplit=1)
    return int(numero_str), color_codigo


def frecuencia_pares_colorloto_a_vm(estadistica, rango_min: int, rango_max: int, juego: Juego) -> dict:
    """Transforma una `EstadisticaCalculada` de tipo
    "frecuencia_pares_colorloto" (Etapa AE-3) en un view model listo
    para la plantilla. Nunca recalcula la métrica, nunca consulta
    repositorios, nunca llama al motor -transformación pura sobre el
    resultado ya serializado. Mismo criterio semántico que las dos
    métricas anteriores de ColorLoto: "Apariciones promedio por
    sorteo" (nunca "porcentaje"), puede legítimamente superar 1.0
    porque el mismo par exacto puede repetirse dentro de un sorteo.

    Orden determinista: se conserva tal cual llega en `resultado`
    -ya ordenado por (número, código) ascendente por el propio motor
    (`sorted(universo)`), nunca reordenado aquí.

    Datasets AGRUPADOS por color para la gráfica de barras agrupadas
    (eje X = números 1..K, un dataset por color) -evita una fila
    ilegible de 42 etiquetas: se construyen dinámicamente a partir de
    los colores REALES presentes en el resultado (nunca 6 códigos
    fijados a mano), preservando el sistema funcionando aunque el
    catálogo tenga una cantidad distinta de colores."""
    filas_crudas = estadistica.resultado["filas"]
    total_sorteos = filas_crudas[0]["total_sorteos"] if filas_crudas else 0

    filas_presentacion = []
    for f in filas_crudas:
        numero, codigo = _deserializar_par_numero_color(f["valor"])
        filas_presentacion.append({
            "numero": numero,
            "codigo": codigo,
            "nombre": codigo.title(),
            "color_hex": _color_hex_seguro(codigo),
            "apariciones": f["apariciones"],
            "apariciones_promedio": f["frecuencia_relativa"],
            "apariciones_promedio_texto": f"{f['frecuencia_relativa']:.2f}",
        })

    par_mayor_promedio = None
    if total_sorteos > 0 and filas_presentacion:
        maximo = max(f["apariciones_promedio"] for f in filas_presentacion)
        if maximo > 0:
            par_mayor_promedio = [
                f"{f['numero']} - {f['nombre']}" for f in filas_presentacion if f["apariciones_promedio"] == maximo
            ]

    # Colores reales presentes en el resultado, en orden de primera
    # aparición estable (no un conjunto sin orden) -nunca una lista
    # fija de 6 códigos hardcodeados.
    colores_presentes: list[str] = []
    vistos: set[str] = set()
    for f in filas_presentacion:
        if f["codigo"] not in vistos:
            vistos.add(f["codigo"])
            colores_presentes.append(f["codigo"])

    numeros_presentes = sorted({f["numero"] for f in filas_presentacion})

    datasets = []
    for codigo_color in colores_presentes:
        filas_de_este_color = {f["numero"]: f for f in filas_presentacion if f["codigo"] == codigo_color}
        datasets.append({
            "label": codigo_color.title(),
            "color_hex": _color_hex_seguro(codigo_color),
            # Acceso seguro con .get(): en el contrato normal del
            # motor todo color en colores_a_reportar tiene una fila
            # para CADA número (producto cartesiano completo), pero
            # el propio motor documenta que un par observado con un
            # color fuera de `colores_vigentes` puede aportar
            # entradas parciales sin garantía de cobertura completa
            # -nunca asumir indexación directa aquí.
            "data": [
                filas_de_este_color[n]["apariciones_promedio"] if n in filas_de_este_color else 0.0
                for n in numeros_presentes
            ],
        })

    return {
        "juego_codigo": juego.codigo,
        "juego_nombre": juego.nombre,
        "rango_min": rango_min,
        "rango_max": rango_max,
        "hasta_numero_sorteo": estadistica.hasta_numero_sorteo,
        "total_sorteos": total_sorteos,
        "calculado_en": estadistica.calculado_en.isoformat() if estadistica.calculado_en else None,
        "filas": filas_presentacion,
        "par_mayor_promedio": par_mayor_promedio,
        "chart_labels": [str(n) for n in numeros_presentes],
        "chart_datasets": datasets,
    }


def atrasos_numeros_colorloto_a_vm(estadistica, rango_min: int, rango_max: int, juego: Juego) -> dict:
    """Transforma una `EstadisticaCalculada` de tipo
    "atrasos_numeros_colorloto" (Etapa AE-4) en un view model listo
    para la plantilla. Nunca recalcula la métrica, nunca consulta
    repositorios, nunca llama al motor -transformación pura sobre el
    resultado ya serializado.

    Campo real del contrato serializado: `AtrasoObservado.valor`
    (string, mismo patrón que `FrecuenciaObservada.valor`) -nunca
    `numero` directamente; se deserializa aquí a entero, igual que en
    las tres recetas anteriores de ColorLoto. `atraso` y
    `ultimo_sorteo_aparicion` pueden ser `None` (nunca apareció) -se
    presentan como "N/D", nunca como `0` (0 tiene un significado real
    distinto: apareció en el sorteo de referencia más reciente).

    "Número(s) con mayor atraso": excluye explícitamente los números
    sin ninguna aparición (`atraso is None`) del cálculo del máximo
    -un valor sin aparición NO es "el más atrasado" de forma
    arbitraria, es simplemente un dato no calculable con el contrato
    actual. Si TODOS los números carecen de atraso (histórico vacío),
    la tarjeta es N/D. Empates preservados completos, mismo criterio
    ya usado 4 veces en las métricas anteriores."""
    filas_ordenadas = sorted(estadistica.resultado["filas"], key=lambda f: int(f["valor"]))

    total_sorteos = filas_ordenadas[0]["total_sorteos"] if filas_ordenadas else 0

    filas_presentacion = []
    for f in filas_ordenadas:
        filas_presentacion.append({
            "numero": int(f["valor"]),
            "atraso": f["atraso"],
            "ultimo_sorteo_aparicion": f["ultimo_sorteo_aparicion"],
        })

    numero_mayor_atraso = None
    filas_con_atraso = [f for f in filas_presentacion if f["atraso"] is not None]
    if filas_con_atraso:
        maximo = max(f["atraso"] for f in filas_con_atraso)
        numero_mayor_atraso = [str(f["numero"]) for f in filas_con_atraso if f["atraso"] == maximo]

    return {
        "juego_codigo": juego.codigo,
        "juego_nombre": juego.nombre,
        "rango_min": rango_min,
        "rango_max": rango_max,
        "hasta_numero_sorteo": estadistica.hasta_numero_sorteo,
        "total_sorteos": total_sorteos,
        "calculado_en": estadistica.calculado_en.isoformat() if estadistica.calculado_en else None,
        "filas": filas_presentacion,
        "numero_mayor_atraso": numero_mayor_atraso,
        "chart_labels": [str(f["numero"]) for f in filas_presentacion],
        # None (nunca apareció) se serializa como `null` -Chart.js
        # muestra un hueco real en esa barra, nunca la confunde con
        # un atraso=0 verdadero (mismo riesgo de interpretación que
        # la tarjeta de "mayor atraso" ya evita explícitamente).
        "chart_atrasos": [f["atraso"] for f in filas_presentacion],
    }


def atrasos_colores_colorloto_a_vm(estadistica, juego: Juego) -> dict:
    """Transforma una `EstadisticaCalculada` de tipo
    "atrasos_colores_colorloto" (Etapa AE-5) en un view model listo
    para la plantilla. Nunca recalcula la métrica, nunca consulta
    repositorios, nunca llama al motor -transformación pura sobre el
    resultado ya serializado.

    Combina los dos patrones ya validados: deserialización/estilo de
    color de `frecuencia_colores_colorloto_a_vm` (Etapa AE-2 -`valor`
    es el CÓDIGO del color, `.title()` para nombre legible,
    `_color_hex_seguro` para el color visual, orden ya alfabético del
    motor, nunca reordenado aquí) y distinción estricta `0`/`N/D` de
    `atrasos_numeros_colorloto_a_vm` (Etapa AE-4 -`atraso`/
    `ultimo_sorteo_aparicion` pueden ser `None`, nunca convertido a
    `0`; el `None` se serializa como `null` para el gráfico, Chart.js
    muestra un hueco real en esa barra, nunca confundido con un
    atraso=0 verdadero).

    "Color(es) con mayor atraso": excluye explícitamente los colores
    sin ninguna aparición (`atraso is None`) del cálculo del máximo
    -un color sin aparición NO es "el más atrasado" de forma
    arbitraria. Si TODOS los colores carecen de atraso (histórico
    vacío), la tarjeta es N/D. Empates preservados completos, mismo
    criterio ya usado en las cuatro métricas anteriores."""
    filas_ordenadas = estadistica.resultado["filas"]

    total_sorteos = filas_ordenadas[0]["total_sorteos"] if filas_ordenadas else 0

    filas_presentacion = []
    for f in filas_ordenadas:
        codigo = f["valor"]
        filas_presentacion.append({
            "codigo": codigo,
            "nombre": codigo.title(),
            "color_hex": _color_hex_seguro(codigo),
            "atraso": f["atraso"],
            "ultimo_sorteo_aparicion": f["ultimo_sorteo_aparicion"],
        })

    color_mayor_atraso = None
    filas_con_atraso = [f for f in filas_presentacion if f["atraso"] is not None]
    if filas_con_atraso:
        maximo = max(f["atraso"] for f in filas_con_atraso)
        color_mayor_atraso = [f["nombre"] for f in filas_con_atraso if f["atraso"] == maximo]

    return {
        "juego_codigo": juego.codigo,
        "juego_nombre": juego.nombre,
        "hasta_numero_sorteo": estadistica.hasta_numero_sorteo,
        "total_sorteos": total_sorteos,
        "calculado_en": estadistica.calculado_en.isoformat() if estadistica.calculado_en else None,
        "filas": filas_presentacion,
        "color_mayor_atraso": color_mayor_atraso,
        "chart_labels": [f["nombre"] for f in filas_presentacion],
        # None (nunca observado) se serializa como `null` -Chart.js
        # muestra un hueco real en esa barra, nunca lo confunde con
        # un atraso=0 verdadero.
        "chart_atrasos": [f["atraso"] for f in filas_presentacion],
        "chart_colores": [f["color_hex"] for f in filas_presentacion],
    }


def atrasos_pares_colorloto_a_vm(estadistica, rango_min: int, rango_max: int, juego: Juego) -> dict:
    """Transforma una `EstadisticaCalculada` de tipo
    "atrasos_pares_colorloto" (Etapa AE-6) en un view model listo
    para la plantilla. Nunca recalcula la métrica, nunca consulta
    repositorios, nunca llama al motor -transformación pura sobre
    el resultado ya serializado.

    Combina los dos patrones ya validados: deserialización/
    agrupación de `frecuencia_pares_colorloto_a_vm` (Etapa AE-3
    -reutiliza `_deserializar_par_numero_color` como único punto
    de parseo, agrupa por número en el eje X y por color en
    datasets, colores REALES presentes en orden de primera
    aparición estable, nunca 6 códigos fijados a mano) y
    distinción estricta `0`/`N-D` de
    `atrasos_colores_colorloto_a_vm`/`atrasos_numeros_colorloto_a_vm`
    (Etapas AE-4/AE-5 -`atraso`/`ultimo_sorteo_aparicion` pueden
    ser `None`, nunca convertido a `0`).

    Diferencia CRÍTICA frente al fallback de
    `frecuencia_pares_colorloto_a_vm`: esa función usa `0.0` para
    una combinación sin fila (frecuencia cero es un valor real
    válido); aquí el fallback para una combinación sin fila es
    `None`, nunca `0` -un atraso de `0` es un valor real distinto
    (paró en el sorteo de referencia) que jamás debe confundirse
    con "sin datos". El `None` se serializa como `null` en el
    dataset de Chart.js -la librería ya muestra un hueco real en
    esa barra, nunca la dibuja como una barra de altura cero.

    "Par(es) con mayor atraso": excluye explícitamente los pares
    sin ninguna aparición (`atraso is None`) del cálculo del
    máximo -un par sin aparición NO es "el más atrasado" de forma
    arbitraria. Si TODOS los pares carecen de atraso (histórico
    vacío), la tarjeta es N/D. Empates preservados completos,
    mismo criterio ya usado en las cinco métricas anteriores.

    Orden determinista: se conserva tal cual llega en `resultado`
    -confirmado por auditoría que coincide exactamente con el
    orden numérico de `frecuencia_pares_colorloto_a_vm` para el
    dominio real 1..7, nunca reordenado aquí."""
    filas_crudas = estadistica.resultado["filas"]
    total_sorteos = filas_crudas[0]["total_sorteos"] if filas_crudas else 0

    filas_presentacion = []
    for f in filas_crudas:
        numero, codigo = _deserializar_par_numero_color(f["valor"])
        filas_presentacion.append({
            "numero": numero,
            "codigo": codigo,
            "nombre": codigo.title(),
            "color_hex": _color_hex_seguro(codigo),
            "atraso": f["atraso"],
            "ultimo_sorteo_aparicion": f["ultimo_sorteo_aparicion"],
        })

    par_mayor_atraso = None
    filas_con_atraso = [f for f in filas_presentacion if f["atraso"] is not None]
    if filas_con_atraso:
        maximo = max(f["atraso"] for f in filas_con_atraso)
        par_mayor_atraso = [
            f"{f['numero']} - {f['nombre']}" for f in filas_con_atraso if f["atraso"] == maximo
        ]

    # Colores reales presentes en el resultado, en orden de primera
    # aparición estable (no un conjunto sin orden) -nunca una lista
    # fija de 6 códigos hardcodeados.
    colores_presentes: list[str] = []
    vistos: set[str] = set()
    for f in filas_presentacion:
        if f["codigo"] not in vistos:
            vistos.add(f["codigo"])
            colores_presentes.append(f["codigo"])

    numeros_presentes = sorted({f["numero"] for f in filas_presentacion})

    datasets = []
    for codigo_color in colores_presentes:
        filas_de_este_color = {f["numero"]: f for f in filas_presentacion if f["codigo"] == codigo_color}
        datasets.append({
            "label": codigo_color.title(),
            "color_hex": _color_hex_seguro(codigo_color),
            # None (nunca observado) se serializa como `null`
            # -nunca 0.0 como en frecuencia, ya que aquí 0 es un
            # atraso real distinto de "sin datos". Chart.js
            # muestra un hueco real en esa barra.
            "data": [
                filas_de_este_color[n]["atraso"] if n in filas_de_este_color else None
                for n in numeros_presentes
            ],
        })

    return {
        "juego_codigo": juego.codigo,
        "juego_nombre": juego.nombre,
        "rango_min": rango_min,
        "rango_max": rango_max,
        "hasta_numero_sorteo": estadistica.hasta_numero_sorteo,
        "total_sorteos": total_sorteos,
        "calculado_en": estadistica.calculado_en.isoformat() if estadistica.calculado_en else None,
        "filas": filas_presentacion,
        "par_mayor_atraso": par_mayor_atraso,
        "chart_labels": [str(n) for n in numeros_presentes],
        "chart_datasets": datasets,
    }


def repeticiones_entre_sorteos_colorloto_a_vm(
    estadistica, rango_min: int, rango_max: int, cantidad_numeros: int, juego: Juego,
) -> dict:
    """Transforma una `EstadisticaCalculada` de tipo
    "repeticiones_entre_sorteos_colorloto" (Etapa AE-7) en un
    view model listo para la plantilla. Nunca recalcula la
    métrica, nunca consulta repositorios, nunca llama al motor.

    Mismo patrón exacto ya validado por
    `distribucion_repeticiones_entre_sorteos_a_vm` (Etapa AC, la
    versión numérica): reutiliza `_etiqueta_repeticiones` sin
    duplicarla, y renombra `total_sorteos` (nombre del campo
    persistido, sin cambiar el contrato/dataclass ni el
    serializador) a `total_transiciones` -SOLO en presentación-
    porque ese campo NO representa la cantidad de sorteos del
    histórico, sino la cantidad de transiciones válidas
    (numero_sorteo_actual == numero_sorteo_anterior + 1). A
    diferencia del resto de VMs de ColorLoto, esta función nunca
    lee ni deriva ningún color: la métrica ignora el color por
    completo.

    "Repetición más frecuente": mismo criterio ya validado
    cinco veces -excluye el caso sin transiciones, incluye TODAS
    las categorías empatadas en el máximo, nunca elige una
    arbitraria."""
    filas_ordenadas = sorted(estadistica.resultado["filas"], key=lambda f: int(f["valor"]))

    total_transiciones = filas_ordenadas[0]["total_sorteos"] if filas_ordenadas else 0

    filas_presentacion = []
    for f in filas_ordenadas:
        cantidad_repetidos = int(f["valor"])
        filas_presentacion.append({
            "cantidad_repetidos": cantidad_repetidos,
            "etiqueta": _etiqueta_repeticiones(cantidad_repetidos),
            "transiciones": f["apariciones"],
            "frecuencia_relativa": f["frecuencia_relativa"],
        })

    repeticion_mas_frecuente = None
    if total_transiciones > 0 and filas_presentacion:
        maximo = max(f["transiciones"] for f in filas_presentacion)
        if maximo > 0:
            repeticion_mas_frecuente = [
                f["etiqueta"] for f in filas_presentacion if f["transiciones"] == maximo
            ]

    return {
        "juego_codigo": juego.codigo,
        "juego_nombre": juego.nombre,
        "rango_min": rango_min,
        "rango_max": rango_max,
        "cantidad_numeros": cantidad_numeros,
        "hasta_numero_sorteo": estadistica.hasta_numero_sorteo,
        "total_transiciones": total_transiciones,
        "calculado_en": estadistica.calculado_en.isoformat() if estadistica.calculado_en else None,
        "filas": filas_presentacion,
        "repeticion_mas_frecuente": repeticion_mas_frecuente,
        "chart_labels": [f["etiqueta"] for f in filas_presentacion],
        "chart_porcentajes": [f["frecuencia_relativa"] * 100 for f in filas_presentacion],
        "chart_transiciones": [f["transiciones"] for f in filas_presentacion],
    }


def distribucion_pares_impares_colorloto_a_vm(estadistica, cantidad_numeros: int, juego: Juego) -> dict:
    """Transforma una `EstadisticaCalculada` de tipo
    "distribucion_pares_impares_colorloto" (Etapa AE-8) en un
    view model listo para la plantilla. Nunca recalcula la
    métrica, nunca consulta repositorios, nunca llama al motor.

    Mismo patrón exacto ya validado por
    `distribucion_pares_impares_a_vm` (Etapa Y, la versión
    numérica): reutiliza `_etiqueta_composicion` sin duplicarla
    -la identidad `cantidad_impares = cantidad_numeros -
    cantidad_pares` sigue siendo matemáticamente correcta con
    repetición, ya que cada una de las 6 posiciones (balotas)
    contribuye independientemente a par o impar, sin importar si
    el número se repite. A diferencia del resto de VMs de
    ColorLoto, esta función nunca lee ni deriva ningún color: la
    métrica ignora el color por completo.

    "Composición más frecuente": mismo criterio ya validado -si
    no hay datos (`total_sorteos == 0`), `None` (el template debe
    mostrar "N/D", sin asumir empate entre categorías en cero);
    con datos, incluye TODAS las categorías empatadas en el
    máximo, nunca elige una arbitraria."""
    filas_ordenadas = sorted(estadistica.resultado["filas"], key=lambda f: int(f["valor"]))

    total_sorteos = filas_ordenadas[0]["total_sorteos"] if filas_ordenadas else 0

    filas_presentacion = []
    for f in filas_ordenadas:
        cantidad_pares = int(f["valor"])
        filas_presentacion.append({
            "cantidad_pares": cantidad_pares,
            "cantidad_impares": cantidad_numeros - cantidad_pares,
            "etiqueta": _etiqueta_composicion(cantidad_pares, cantidad_numeros),
            "apariciones": f["apariciones"],
            "frecuencia_relativa": f["frecuencia_relativa"],
        })

    composicion_mas_frecuente = None
    if total_sorteos > 0 and filas_presentacion:
        maximo = max(f["apariciones"] for f in filas_presentacion)
        if maximo > 0:
            composicion_mas_frecuente = [
                f["etiqueta"] for f in filas_presentacion if f["apariciones"] == maximo
            ]

    return {
        "juego_codigo": juego.codigo,
        "juego_nombre": juego.nombre,
        "cantidad_numeros": cantidad_numeros,
        "hasta_numero_sorteo": estadistica.hasta_numero_sorteo,
        "total_sorteos": total_sorteos,
        "calculado_en": estadistica.calculado_en.isoformat() if estadistica.calculado_en else None,
        "filas": filas_presentacion,
        "composicion_mas_frecuente": composicion_mas_frecuente,
        "chart_labels": [f["etiqueta"] for f in filas_presentacion],
        "chart_porcentajes": [f["frecuencia_relativa"] * 100 for f in filas_presentacion],
        "chart_apariciones": [f["apariciones"] for f in filas_presentacion],
    }


def _etiqueta_altos_bajos_colorloto(cantidad_bajos: int, cantidad_numeros: int) -> str:
    """Singular/plural correcto para bajos/altos por separado
    -mismo patrón exacto ya usado en `_etiqueta_composicion`
    (pares/impares) y `_etiqueta_inferior_superior` (numérico),
    pero con la terminología "bajos"/"altos" exacta exigida por
    el contrato de esta etapa -deliberadamente distinta del
    helper numérico `_etiqueta_inferior_superior`, que usa
    "inferior"/"superior", para que la etiqueta coincida con el
    propio nombre de la métrica (`distribucion_altos_bajos`)."""
    cantidad_altos = cantidad_numeros - cantidad_bajos
    texto_bajos = "1 bajo" if cantidad_bajos == 1 else f"{cantidad_bajos} bajos"
    texto_altos = "1 alto" if cantidad_altos == 1 else f"{cantidad_altos} altos"
    return f"{texto_bajos} / {texto_altos}"


def distribucion_altos_bajos_colorloto_a_vm(
    estadistica, rango_min: int, rango_max: int, cantidad_numeros: int, juego: Juego,
) -> dict:
    """Transforma una `EstadisticaCalculada` de tipo
    "distribucion_altos_bajos_colorloto" (Etapa AE-9) en un view
    model listo para la plantilla. Nunca recalcula la métrica,
    nunca consulta repositorios, nunca llama al motor.

    Reutiliza `_punto_de_corte_altos_bajos_vm` sin duplicarla
    -esa función YA es genérica (no específica de ningún juego,
    solo depende de `rango_min`/`rango_max`) y YA está verificada
    exhaustivamente contra la fórmula real del motor. Para el
    rango real 1..7 el corte es 3: bajos={1,2,3}, altos={4,5,6,7}.

    `valor` en el resultado ya serializado es la cantidad de
    NÚMEROS BAJOS del sorteo (confirmado por auditoría citando
    el bloque exacto del motor: `sum(1 for n, _ in r.pares if n
    <= corte)`) -este VM la expone como `cantidad_bajos` y
    deriva `cantidad_altos = cantidad_numeros - cantidad_bajos`,
    con una etiqueta compuesta explícita (`_etiqueta_altos_bajos_colorloto`)
    para que ninguna vista quede con una categoría ambigua
    "0".."6" sin contexto. A diferencia del resto de VMs de
    ColorLoto, esta función nunca lee ni deriva ningún color: la
    métrica ignora el color por completo.

    "Composición más frecuente": mismo criterio ya validado -si
    no hay datos (`total_sorteos == 0`), `None` (el template debe
    mostrar "N/D"); con datos, incluye TODAS las categorías
    empatadas en el máximo, nunca elige una arbitraria."""
    punto_de_corte = _punto_de_corte_altos_bajos_vm(rango_min, rango_max)

    filas_ordenadas = sorted(estadistica.resultado["filas"], key=lambda f: int(f["valor"]))

    total_sorteos = filas_ordenadas[0]["total_sorteos"] if filas_ordenadas else 0

    filas_presentacion = []
    for f in filas_ordenadas:
        cantidad_bajos = int(f["valor"])
        filas_presentacion.append({
            "cantidad_bajos": cantidad_bajos,
            "cantidad_altos": cantidad_numeros - cantidad_bajos,
            "etiqueta": _etiqueta_altos_bajos_colorloto(cantidad_bajos, cantidad_numeros),
            "apariciones": f["apariciones"],
            "total_sorteos": f["total_sorteos"],
            "frecuencia_relativa": f["frecuencia_relativa"],
        })

    composicion_mas_frecuente = None
    if total_sorteos > 0 and filas_presentacion:
        maximo = max(f["apariciones"] for f in filas_presentacion)
        if maximo > 0:
            composicion_mas_frecuente = [
                f["etiqueta"] for f in filas_presentacion if f["apariciones"] == maximo
            ]

    return {
        "juego_codigo": juego.codigo,
        "juego_nombre": juego.nombre,
        "rango_min": rango_min,
        "rango_max": rango_max,
        "cantidad_numeros": cantidad_numeros,
        "punto_de_corte": punto_de_corte,
        "franja_bajos_texto": f"{rango_min}-{punto_de_corte}",
        "franja_altos_texto": f"{punto_de_corte + 1}-{rango_max}",
        "hasta_numero_sorteo": estadistica.hasta_numero_sorteo,
        "total_sorteos": total_sorteos,
        "calculado_en": estadistica.calculado_en.isoformat() if estadistica.calculado_en else None,
        "filas": filas_presentacion,
        "composicion_mas_frecuente": composicion_mas_frecuente,
        "chart_labels": [f["etiqueta"] for f in filas_presentacion],
        "chart_porcentajes": [f["frecuencia_relativa"] * 100 for f in filas_presentacion],
        "chart_apariciones": [f["apariciones"] for f in filas_presentacion],
    }


def _etiqueta_maximo_repeticion_color(cantidad_balotas_del_color: int) -> str:
    """Singular/plural correcto -mismo patrón exacto ya usado
    por `_etiqueta_composicion`/`_etiqueta_altos_bajos_colorloto`.
    Nunca menciona un código de color específico: el motor no
    reporta CUÁL color alcanzó el máximo, solo CUÁNTAS balotas
    lo alcanzaron -los empates entre colores no forman parte
    del resultado."""
    if cantidad_balotas_del_color == 1:
        return "1 balota del mismo color"
    return f"{cantidad_balotas_del_color} balotas del mismo color"


def maximo_repeticion_color_por_sorteo_colorloto_a_vm(estadistica, cantidad_numeros: int, juego: Juego) -> dict:
    """Transforma una `EstadisticaCalculada` de tipo
    "maximo_repeticion_color_por_sorteo_colorloto" (Etapa AE-10,
    PROVISIONAL) en un view model listo para la plantilla. Nunca
    recalcula la métrica, nunca consulta repositorios, nunca
    llama al motor -mismo patrón exacto ya validado por AE-8/AE-9.

    Categorías 1..6 (nunca 0, confirmado por el propio motor):
    `valor` es la mayor cantidad de balotas que compartieron un
    mismo color dentro del sorteo. A diferencia del resto de VMs
    de ColorLoto, esta función lee el resultado de una métrica
    que SÍ depende del color internamente (Counter en el motor),
    pero el propio VM nunca deriva ni expone ningún código,
    nombre o valor hexadecimal de color -el resultado serializado
    ya es puramente numérico (multiplicidad máxima), sin ninguna
    identidad de color que traducir.

    "Composición más frecuente": mismo criterio ya validado -si
    no hay datos (`total_sorteos == 0`), `None` (el template debe
    mostrar "N/D"); con datos, incluye TODAS las categorías
    empatadas en el máximo, nunca elige una arbitraria."""
    filas_ordenadas = sorted(estadistica.resultado["filas"], key=lambda f: int(f["valor"]))

    total_sorteos = filas_ordenadas[0]["total_sorteos"] if filas_ordenadas else 0

    filas_presentacion = []
    for f in filas_ordenadas:
        maximo_repetido = int(f["valor"])
        filas_presentacion.append({
            "maximo_repetido": maximo_repetido,
            "etiqueta": _etiqueta_maximo_repeticion_color(maximo_repetido),
            "etiqueta_corta": f"{maximo_repetido} balota" if maximo_repetido == 1 else f"{maximo_repetido} balotas",
            "apariciones": f["apariciones"],
            "total_sorteos": f["total_sorteos"],
            "frecuencia_relativa": f["frecuencia_relativa"],
        })

    composicion_mas_frecuente = None
    if total_sorteos > 0 and filas_presentacion:
        maximo_apariciones = max(f["apariciones"] for f in filas_presentacion)
        if maximo_apariciones > 0:
            composicion_mas_frecuente = [
                f["etiqueta"] for f in filas_presentacion if f["apariciones"] == maximo_apariciones
            ]

    return {
        "juego_codigo": juego.codigo,
        "juego_nombre": juego.nombre,
        "cantidad_numeros": cantidad_numeros,
        "hasta_numero_sorteo": estadistica.hasta_numero_sorteo,
        "total_sorteos": total_sorteos,
        "calculado_en": estadistica.calculado_en.isoformat() if estadistica.calculado_en else None,
        "filas": filas_presentacion,
        "composicion_mas_frecuente": composicion_mas_frecuente,
        "chart_labels": [f["etiqueta_corta"] for f in filas_presentacion],
        "chart_porcentajes": [f["frecuencia_relativa"] * 100 for f in filas_presentacion],
        "chart_apariciones": [f["apariciones"] for f in filas_presentacion],
    }


def distribucion_pares_consecutivos_colorloto_a_vm(estadistica, cantidad_numeros: int, juego: Juego) -> dict:
    """Transforma una `EstadisticaCalculada` de tipo
    "distribucion_pares_consecutivos_colorloto" (Etapa AE-11,
    PROVISIONAL) en un view model listo para la plantilla. Nunca
    recalcula la métrica, nunca consulta repositorios, nunca llama
    al motor -mismo patrón exacto ya validado por AE-8/AE-9/AE-10.

    Categorías 0..5 (nunca 0..6 -un par consecutivo requiere DOS
    números distintos, así que con 6 balotas el máximo teórico de
    pares es 5, confirmado por el propio motor y verificado con
    caracterización real en la auditoría y su adenda correctiva).
    Reutiliza el helper `_etiqueta_pares_consecutivos` ya existente
    (Etapa AA, sin duplicar su lógica de singular/plural) -mismo
    criterio textual ya usado por la versión numérica de esta misma
    métrica (`distribucion_pares_consecutivos_a_vm`).

    "Composición más frecuente" sigue el mismo criterio ya validado
    cuatro veces (AE-7/AE-8/AE-9/AE-10): excluye sin datos, incluye
    TODAS las categorías empatadas en el máximo, nunca elige una
    arbitraria. `apariciones=0` se presenta como cero real, nunca
    como `None` ni "N/D" -el template decide su propia presentación
    a partir de este valor entero real.

    No expone ni deriva ningún código, nombre o valor hexadecimal de
    color -el resultado serializado ya es puramente numérico
    (cantidad de pares consecutivos), sin ninguna identidad de color
    que traducir; el motor que produce este resultado ignora el
    color por completo."""
    filas_ordenadas = sorted(estadistica.resultado["filas"], key=lambda f: int(f["valor"]))

    total_sorteos = filas_ordenadas[0]["total_sorteos"] if filas_ordenadas else 0

    filas_presentacion = []
    for f in filas_ordenadas:
        cantidad_pares = int(f["valor"])
        filas_presentacion.append({
            "cantidad_pares_consecutivos": cantidad_pares,
            "etiqueta": _etiqueta_pares_consecutivos(cantidad_pares),
            "apariciones": f["apariciones"],
            "frecuencia_relativa": f["frecuencia_relativa"],
        })

    composicion_mas_frecuente = None
    if total_sorteos > 0 and filas_presentacion:
        maximo = max(f["apariciones"] for f in filas_presentacion)
        if maximo > 0:
            composicion_mas_frecuente = [
                f["etiqueta"] for f in filas_presentacion if f["apariciones"] == maximo
            ]

    return {
        "juego_codigo": juego.codigo,
        "juego_nombre": juego.nombre,
        "cantidad_numeros": cantidad_numeros,
        "hasta_numero_sorteo": estadistica.hasta_numero_sorteo,
        "total_sorteos": total_sorteos,
        "calculado_en": estadistica.calculado_en.isoformat() if estadistica.calculado_en else None,
        "filas": filas_presentacion,
        "composicion_mas_frecuente": composicion_mas_frecuente,
        "chart_labels": [f["etiqueta"] for f in filas_presentacion],
        "chart_porcentajes": [f["frecuencia_relativa"] * 100 for f in filas_presentacion],
        "chart_apariciones": [f["apariciones"] for f in filas_presentacion],
    }


def distribucion_racha_maxima_colorloto_a_vm(estadistica, cantidad_numeros: int, juego: Juego) -> dict:
    """Transforma una `EstadisticaCalculada` de tipo
    "distribucion_racha_maxima_colorloto" (Etapa AE-12, PROVISIONAL)
    en un view model listo para la plantilla. Nunca recalcula la
    métrica, nunca consulta repositorios, nunca llama al motor
    -mismo patrón exacto ya validado por AE-8/AE-9/AE-10/AE-11.

    Categorías 1..6 (nunca 0 -un sorteo con al menos un número
    siempre tiene una racha de longitud mínima 1, confirmado por el
    propio motor, que ya filtra la categoría "0" antes de devolver el
    resultado). Reutiliza el helper `_etiqueta_racha_maxima` ya
    existente (Etapa AB, numérica) sin duplicar su lógica de
    singular/plural -mismo criterio textual ya usado por la versión
    numérica de esta misma métrica (`distribucion_racha_maxima_a_vm`),
    de la que este VM toma prestados los nombres de clave
    (`longitud_racha`, `racha_mas_frecuente`) para máxima coherencia
    entre ambas versiones de la misma métrica.

    "Racha más frecuente" sigue el mismo criterio ya validado cinco
    veces (AE-7/AE-8/AE-9/AE-10/AE-11): excluye sin datos, incluye
    TODAS las categorías empatadas en el máximo, nunca elige una
    arbitraria. `apariciones=0` se presenta como cero real, nunca
    como `None` ni "N/D" -el template decide su propia presentación
    a partir de este valor entero real.

    No expone ni deriva ningún código, nombre o valor hexadecimal de
    color -el resultado serializado ya es puramente numérico
    (longitud de racha), sin ninguna identidad de color que
    traducir; el motor que produce este resultado ignora el color
    por completo."""
    filas_ordenadas = sorted(estadistica.resultado["filas"], key=lambda f: int(f["valor"]))

    total_sorteos = filas_ordenadas[0]["total_sorteos"] if filas_ordenadas else 0

    filas_presentacion = []
    for f in filas_ordenadas:
        longitud = int(f["valor"])
        filas_presentacion.append({
            "longitud_racha": longitud,
            "etiqueta": _etiqueta_racha_maxima(longitud),
            "apariciones": f["apariciones"],
            "frecuencia_relativa": f["frecuencia_relativa"],
        })

    racha_mas_frecuente = None
    if total_sorteos > 0 and filas_presentacion:
        maximo = max(f["apariciones"] for f in filas_presentacion)
        if maximo > 0:
            racha_mas_frecuente = [
                f["etiqueta"] for f in filas_presentacion if f["apariciones"] == maximo
            ]

    return {
        "juego_codigo": juego.codigo,
        "juego_nombre": juego.nombre,
        "cantidad_numeros": cantidad_numeros,
        "hasta_numero_sorteo": estadistica.hasta_numero_sorteo,
        "total_sorteos": total_sorteos,
        "calculado_en": estadistica.calculado_en.isoformat() if estadistica.calculado_en else None,
        "filas": filas_presentacion,
        "racha_mas_frecuente": racha_mas_frecuente,
        "chart_labels": [f["etiqueta"] for f in filas_presentacion],
        "chart_porcentajes": [f["frecuencia_relativa"] * 100 for f in filas_presentacion],
        "chart_apariciones": [f["apariciones"] for f in filas_presentacion],
    }


def distribucion_trios_consecutivos_colorloto_a_vm(estadistica, cantidad_numeros: int, juego: Juego) -> dict:
    """Transforma una `EstadisticaCalculada` de tipo
    "distribucion_trios_consecutivos_colorloto" (Etapa AE-13,
    PROVISIONAL) en un view model listo para la plantilla. Nunca
    recalcula la métrica, nunca consulta repositorios, nunca llama
    al motor -mismo patrón exacto ya validado por AE-8/AE-9/AE-10/AE-11/AE-12.

    Categorías 0..4 (a diferencia de AE-12, esta métrica SÍ incluye
    la categoría 0: un sorteo sin ningún trío consecutivo es un valor
    real y posible -mismo criterio ya usado por
    `distribucion_pares_consecutivos_colorloto_a_vm`, Etapa AE-11-,
    nunca 0..6: un trío consecutivo requiere TRES números distintos,
    así que con 6 balotas el máximo teórico es 4, confirmado por el
    propio motor y verificado con caracterización real en la
    auditoría de AE-13). Reutiliza el helper `_etiqueta_trios_consecutivos`
    agregado en esta misma etapa (no existía precedente, ni siquiera
    numérico, confirmado por la auditoría) sin duplicar lógica de
    singular/plural en ningún otro punto del View Model. Clave
    `cantidad_trios_consecutivos` (nunca `longitud_racha` ni
    `cantidad_pares_consecutivos`) para no confundir "cantidad de
    tríos" con "longitud de la racha máxima" ni con "cantidad de
    pares consecutivos" -tres semánticas distintas ya presentes en
    ColorLoto (AE-11, AE-12, AE-13).

    "Composición más frecuente" sigue el mismo criterio ya validado
    seis veces (AE-7/AE-8/AE-9/AE-10/AE-11/AE-12): excluye sin datos,
    incluye TODAS las categorías empatadas en el máximo, nunca elige
    una arbitraria. `apariciones=0` se presenta como cero real, nunca
    como `None` ni "N/D" -el template decide su propia presentación
    a partir de este valor entero real.

    No expone ni deriva ningún código, nombre o valor hexadecimal de
    color -el resultado serializado ya es puramente numérico
    (cantidad de tríos consecutivos), sin ninguna identidad de color
    que traducir; el motor que produce este resultado ignora el
    color por completo."""
    filas_ordenadas = sorted(estadistica.resultado["filas"], key=lambda f: int(f["valor"]))

    total_sorteos = filas_ordenadas[0]["total_sorteos"] if filas_ordenadas else 0

    filas_presentacion = []
    for f in filas_ordenadas:
        cantidad_trios = int(f["valor"])
        filas_presentacion.append({
            "cantidad_trios_consecutivos": cantidad_trios,
            "etiqueta": _etiqueta_trios_consecutivos(cantidad_trios),
            "apariciones": f["apariciones"],
            "frecuencia_relativa": f["frecuencia_relativa"],
        })

    composicion_mas_frecuente = None
    if total_sorteos > 0 and filas_presentacion:
        maximo = max(f["apariciones"] for f in filas_presentacion)
        if maximo > 0:
            composicion_mas_frecuente = [
                f["etiqueta"] for f in filas_presentacion if f["apariciones"] == maximo
            ]

    return {
        "juego_codigo": juego.codigo,
        "juego_nombre": juego.nombre,
        "cantidad_numeros": cantidad_numeros,
        "hasta_numero_sorteo": estadistica.hasta_numero_sorteo,
        "total_sorteos": total_sorteos,
        "calculado_en": estadistica.calculado_en.isoformat() if estadistica.calculado_en else None,
        "filas": filas_presentacion,
        "composicion_mas_frecuente": composicion_mas_frecuente,
        "chart_labels": [f["etiqueta"] for f in filas_presentacion],
        "chart_porcentajes": [f["frecuencia_relativa"] * 100 for f in filas_presentacion],
        "chart_apariciones": [f["apariciones"] for f in filas_presentacion],
    }


def coocurrencia_pares_colorloto_a_vm(estadistica, juego: Juego) -> dict:
    """Transforma una `EstadisticaCalculada` de tipo
    "coocurrencia_pares_colorloto" (Etapa AE-14, PROVISIONAL) en un
    view model listo para la plantilla. Nunca recalcula la métrica,
    nunca consulta repositorios, nunca llama al motor -mismo patrón
    ya validado por las trece VM anteriores de ColorLoto.

    A DIFERENCIA de las trece VM anteriores, esta NO tabula
    categorías por sorteo -consume directamente las filas de
    `MetricaAsociacion` ya serializadas por `_serializar_metrica_asociacion`
    (elementos como enteros reales, nunca strings), preservando el
    orden real devuelto por el motor (ordenado por soporte
    descendente; sin ningún criterio de desempate adicional -no se
    inventa ninguno aquí, ni se reordena alfabética o numéricamente,
    porque no existe todavía ninguna convención de producción para
    ese caso). NUNCA selecciona un único "par más frecuente": si hay
    empate en el soporte máximo, TODAS las filas empatadas quedan
    visibles en la tabla completa -no hay resumen que elija una
    arbitraria, mismo espíritu que "composición más frecuente" en
    las VM anteriores, pero aquí ni siquiera se resume: se muestran
    todas las filas siempre.

    `frecuencia_esperada`/`lift` se preservan literalmente como
    `None` cuando el serializado los trae así (siempre el caso para
    ColorLoto, ver `motor/coocurrencia.py`) -nunca se sustituyen por
    0, que sería un dato matemáticamente distinto (0 significaría
    "nunca coocurre pese a ser matemáticamente posible", no "no
    calculado por ambigüedad del modelo"). El resumen superior se
    limita a total de sorteos y cantidad de pares observados -sin
    ninguna recomendación de números ni cálculo estadístico nuevo,
    conforme al contrato exacto autorizado para AE-14.

    No expone ningún código, nombre ni valor hexadecimal de color -el
    resultado serializado ya es puramente numérico (dos enteros por
    par), sin ninguna identidad de color que traducir; el motor que
    produce este resultado ignora el color por completo."""
    filas_serializadas = estadistica.resultado["filas"]

    total_sorteos = filas_serializadas[0]["total_sorteos"] if filas_serializadas else 0

    filas_presentacion = []
    for f in filas_serializadas:
        numero_a, numero_b = f["elementos"]
        filas_presentacion.append({
            "numero_a": numero_a,
            "numero_b": numero_b,
            "soporte": f["soporte"],
            "frecuencia_relativa": f["frecuencia_relativa"],
            "porcentaje": f["frecuencia_relativa"] * 100,
            "frecuencia_esperada": f["frecuencia_esperada"],
            "lift": f["lift"],
        })

    return {
        "juego_codigo": juego.codigo,
        "juego_nombre": juego.nombre,
        "hasta_numero_sorteo": estadistica.hasta_numero_sorteo,
        "total_sorteos": total_sorteos,
        "calculado_en": estadistica.calculado_en.isoformat() if estadistica.calculado_en else None,
        "filas": filas_presentacion,
        "cantidad_pares_observados": len(filas_presentacion),
    }


def coocurrencia_trios_colorloto_a_vm(estadistica, juego: Juego) -> dict:
    """Transforma una `EstadisticaCalculada` de tipo
    "coocurrencia_trios_colorloto" (Etapa AE-15, PROVISIONAL) en un
    view model listo para la plantilla. Nunca recalcula la métrica,
    nunca consulta repositorios, nunca llama al motor -mismo patrón
    exacto ya validado por `coocurrencia_pares_colorloto_a_vm`
    (AE-14), solo con tres elementos por fila en vez de dos.

    Igual que la VM de pares: consume directamente las filas de
    `MetricaAsociacion` ya serializadas por `_serializar_metrica_asociacion`
    (elementos como enteros reales, nunca strings), preservando el
    orden real devuelto por el motor (soporte descendente, sin
    ningún criterio de desempate adicional) y sin nunca elegir un
    único "trío más frecuente" -todas las filas empatadas quedan
    visibles siempre. Para ColorLoto (7 números posibles), el máximo
    teórico es C(7,3)=35 tríos -se muestran todas las filas
    observadas, sin top-N, paginación ni truncamiento.

    `frecuencia_esperada`/`lift` se preservan literalmente como
    `None` cuando el serializado los trae así (siempre el caso para
    ColorLoto) -nunca se sustituyen por 0. El resumen superior se
    limita a total de sorteos y cantidad de tríos observados, sin
    ninguna recomendación de números ni cálculo estadístico nuevo."""
    filas_serializadas = estadistica.resultado["filas"]

    total_sorteos = filas_serializadas[0]["total_sorteos"] if filas_serializadas else 0

    filas_presentacion = []
    for f in filas_serializadas:
        numero_1, numero_2, numero_3 = f["elementos"]
        filas_presentacion.append({
            "numero_1": numero_1,
            "numero_2": numero_2,
            "numero_3": numero_3,
            "soporte": f["soporte"],
            "frecuencia_relativa": f["frecuencia_relativa"],
            "porcentaje": f["frecuencia_relativa"] * 100,
            "frecuencia_esperada": f["frecuencia_esperada"],
            "lift": f["lift"],
        })

    return {
        "juego_codigo": juego.codigo,
        "juego_nombre": juego.nombre,
        "hasta_numero_sorteo": estadistica.hasta_numero_sorteo,
        "total_sorteos": total_sorteos,
        "calculado_en": estadistica.calculado_en.isoformat() if estadistica.calculado_en else None,
        "filas": filas_presentacion,
        "cantidad_trios_observados": len(filas_presentacion),
    }


def coocurrencia_pares_colores_colorloto_a_vm(estadistica, juego: Juego) -> dict:
    """Transforma una `EstadisticaCalculada` de tipo
    "coocurrencia_pares_colores_colorloto" (Etapa AE-16, PROVISIONAL)
    en un view model listo para la plantilla. Nunca recalcula la
    métrica, nunca consulta repositorios, nunca llama al motor
    -mismo patrón exacto ya validado por `coocurrencia_pares_colorloto_a_vm`
    (AE-14) y `coocurrencia_trios_colorloto_a_vm` (AE-15).

    A DIFERENCIA de esas dos VM, aquí `f["elementos"]` contiene dos
    CÓDIGOS DE COLOR (strings reales, p. ej. "AMARILLO"/"AZUL"), no
    números -provienen de `_serializar_metrica_asociacion_texto`
    (Etapa AE-16), nunca de `_serializar_metrica_asociacion`. Esta
    VM nunca aplica `int(...)` sobre esos valores -serían códigos
    inválidos como enteros, mismo motivo exacto que forzó la
    creación del serializador textual nuevo en esta etapa. Los
    colores se conservan literalmente tal como llegan serializados,
    incluidos códigos históricamente retirados si el histórico los
    contiene -esta VM no filtra ni valida vigencia, esa
    responsabilidad ya quedó resuelta antes de llegar aquí (capa de
    validación defensiva del histórico, no esta capa de
    presentación).

    Igual que las dos VM de coocurrencia anteriores: preserva el
    orden real devuelto por el motor (soporte descendente, sin
    ningún criterio de desempate adicional) y nunca elige un único
    "par de colores más frecuente" -todas las filas empatadas
    quedan visibles siempre. `frecuencia_esperada`/`lift` se
    preservan literalmente como `None` cuando el serializado los
    trae así (siempre el caso para ColorLoto) -nunca se sustituyen
    por 0. El resumen superior se limita a total de sorteos y
    cantidad de pares de colores observados, sin ninguna
    recomendación ni cálculo estadístico nuevo. No expone ningún
    número de balota -el motor que produce este resultado ignora
    los números por completo."""
    filas_serializadas = estadistica.resultado["filas"]

    total_sorteos = filas_serializadas[0]["total_sorteos"] if filas_serializadas else 0

    filas_presentacion = []
    for f in filas_serializadas:
        color_1, color_2 = f["elementos"]
        filas_presentacion.append({
            "color_1": color_1,
            "color_2": color_2,
            "soporte": f["soporte"],
            "frecuencia_relativa": f["frecuencia_relativa"],
            "porcentaje": f["frecuencia_relativa"] * 100,
            "frecuencia_esperada": f["frecuencia_esperada"],
            "lift": f["lift"],
        })

    return {
        "juego_codigo": juego.codigo,
        "juego_nombre": juego.nombre,
        "hasta_numero_sorteo": estadistica.hasta_numero_sorteo,
        "total_sorteos": total_sorteos,
        "calculado_en": estadistica.calculado_en.isoformat() if estadistica.calculado_en else None,
        "filas": filas_presentacion,
        "cantidad_pares_observados": len(filas_presentacion),
    }


def coocurrencia_trios_colores_colorloto_a_vm(estadistica, juego: Juego) -> dict:
    """Transforma una `EstadisticaCalculada` de tipo
    "coocurrencia_trios_colores_colorloto" (Etapa AE-17, PROVISIONAL)
    en un view model listo para la plantilla. Nunca recalcula la
    métrica, nunca consulta repositorios, nunca llama al motor
    -mismo patrón exacto ya validado por
    `coocurrencia_pares_colores_colorloto_a_vm` (AE-16), esta vez
    con TRES códigos de color en vez de dos.

    `f["elementos"]` contiene exactamente tres strings reales
    (p. ej. "AMARILLO"/"AZUL"/"ROJO"), producidos por
    `_serializar_metrica_asociacion_texto` (Etapa AE-16, reutilizado
    sin cambios) -nunca por `_serializar_metrica_asociacion`. Esta
    VM nunca aplica `int(...)` sobre esos valores, y nunca concatena
    los tres colores en un único campo -se exponen como
    `color_1`/`color_2`/`color_3` separados, mismo patrón que
    `numero_1`/`numero_2`/`numero_3` de AE-15. El desempaquetado
    `color_1, color_2, color_3 = f["elementos"]` es seguro porque el
    motor y el serializador siempre producen tuplas de exactamente
    tres elementos para esta receta -nunca dos, nunca cuatro-,
    confirmado por la auditoría previa mediante ejecución real.

    Los colores se conservan literalmente tal como llegan
    serializados, incluidos códigos históricamente retirados si el
    histórico los contiene -esta VM no filtra ni valida vigencia,
    esa responsabilidad ya quedó resuelta antes de llegar aquí.

    Igual que las tres VM de coocurrencia anteriores: preserva el
    orden real devuelto por el motor (soporte descendente) y nunca
    elige un único "trío de colores más frecuente" -todas las filas
    empatadas quedan visibles siempre. `frecuencia_esperada`/`lift`
    se preservan literalmente como `None` cuando el serializado los
    trae así (siempre el caso para ColorLoto) -nunca se sustituyen
    por 0. El resumen superior se limita a total de sorteos y
    cantidad de tríos de colores observados, sin ninguna
    recomendación ni cálculo estadístico nuevo. No expone ningún
    número de balota -el motor que produce este resultado ignora
    los números por completo."""
    filas_serializadas = estadistica.resultado["filas"]

    total_sorteos = filas_serializadas[0]["total_sorteos"] if filas_serializadas else 0

    filas_presentacion = []
    for f in filas_serializadas:
        color_1, color_2, color_3 = f["elementos"]
        filas_presentacion.append({
            "color_1": color_1,
            "color_2": color_2,
            "color_3": color_3,
            "soporte": f["soporte"],
            "frecuencia_relativa": f["frecuencia_relativa"],
            "porcentaje": f["frecuencia_relativa"] * 100,
            "frecuencia_esperada": f["frecuencia_esperada"],
            "lift": f["lift"],
        })

    return {
        "juego_codigo": juego.codigo,
        "juego_nombre": juego.nombre,
        "hasta_numero_sorteo": estadistica.hasta_numero_sorteo,
        "total_sorteos": total_sorteos,
        "calculado_en": estadistica.calculado_en.isoformat() if estadistica.calculado_en else None,
        "filas": filas_presentacion,
        "cantidad_trios_observados": len(filas_presentacion),
    }


def distribucion_racha_maxima_a_vm(
    estadistica, rango_min: int, rango_max: int, cantidad_numeros: int, juego: Juego,
) -> dict:
    """Transforma una `EstadisticaCalculada` de tipo
    "distribucion_racha_maxima" (Etapa AB) en un view model listo
    para la plantilla. Nunca recalcula la métrica, nunca consulta
    repositorios, nunca llama al motor.

    Categorías 1..K (nunca 0 -un sorteo válido siempre tiene al
    menos una racha de longitud 1, confirmado por el propio motor).
    "Racha máxima más frecuente" sigue el mismo criterio ya validado
    tres veces: excluye sin datos, incluye TODAS las categorías
    empatadas en el máximo, nunca elige una arbitraria."""
    filas_ordenadas = sorted(estadistica.resultado["filas"], key=lambda f: int(f["valor"]))

    total_sorteos = filas_ordenadas[0]["total_sorteos"] if filas_ordenadas else 0

    filas_presentacion = []
    for f in filas_ordenadas:
        longitud = int(f["valor"])
        filas_presentacion.append({
            "longitud_racha": longitud,
            "etiqueta": _etiqueta_racha_maxima(longitud),
            "apariciones": f["apariciones"],
            "frecuencia_relativa": f["frecuencia_relativa"],
        })

    racha_mas_frecuente = None
    if total_sorteos > 0 and filas_presentacion:
        maximo = max(f["apariciones"] for f in filas_presentacion)
        if maximo > 0:
            racha_mas_frecuente = [
                f["etiqueta"] for f in filas_presentacion if f["apariciones"] == maximo
            ]

    return {
        "juego_codigo": juego.codigo,
        "juego_nombre": juego.nombre,
        "rango_min": rango_min,
        "rango_max": rango_max,
        "cantidad_numeros": cantidad_numeros,
        "hasta_numero_sorteo": estadistica.hasta_numero_sorteo,
        "total_sorteos": total_sorteos,
        "calculado_en": estadistica.calculado_en.isoformat() if estadistica.calculado_en else None,
        "filas": filas_presentacion,
        "racha_mas_frecuente": racha_mas_frecuente,
        "chart_labels": [f["etiqueta"] for f in filas_presentacion],
        "chart_porcentajes": [f["frecuencia_relativa"] * 100 for f in filas_presentacion],
        "chart_apariciones": [f["apariciones"] for f in filas_presentacion],
    }


def distribucion_pares_consecutivos_a_vm(
    estadistica, rango_min: int, rango_max: int, cantidad_numeros: int, juego: Juego,
) -> dict:
    """Transforma una `EstadisticaCalculada` de tipo
    "distribucion_pares_consecutivos" (Etapa AA) en un view model
    listo para la plantilla. Nunca recalcula la métrica, nunca
    consulta repositorios.

    Categorías 0..K-1 (nunca 0..K -un par consecutivo requiere DOS
    números, así que con K números el máximo teórico de pares es
    K-1, confirmado por el propio motor y verificado con datasets
    reales durante la auditoría de esta etapa). "Composición más
    frecuente" sigue el mismo criterio ya validado dos veces: excluye
    sin datos, incluye TODAS las categorías empatadas en el máximo,
    nunca elige una arbitraria."""
    filas_ordenadas = sorted(estadistica.resultado["filas"], key=lambda f: int(f["valor"]))

    total_sorteos = filas_ordenadas[0]["total_sorteos"] if filas_ordenadas else 0

    filas_presentacion = []
    for f in filas_ordenadas:
        cantidad_pares = int(f["valor"])
        filas_presentacion.append({
            "cantidad_pares_consecutivos": cantidad_pares,
            "etiqueta": _etiqueta_pares_consecutivos(cantidad_pares),
            "apariciones": f["apariciones"],
            "frecuencia_relativa": f["frecuencia_relativa"],
        })

    composicion_mas_frecuente = None
    if total_sorteos > 0 and filas_presentacion:
        maximo = max(f["apariciones"] for f in filas_presentacion)
        if maximo > 0:
            composicion_mas_frecuente = [
                f["etiqueta"] for f in filas_presentacion if f["apariciones"] == maximo
            ]

    return {
        "juego_codigo": juego.codigo,
        "juego_nombre": juego.nombre,
        "rango_min": rango_min,
        "rango_max": rango_max,
        "cantidad_numeros": cantidad_numeros,
        "hasta_numero_sorteo": estadistica.hasta_numero_sorteo,
        "total_sorteos": total_sorteos,
        "calculado_en": estadistica.calculado_en.isoformat() if estadistica.calculado_en else None,
        "filas": filas_presentacion,
        "composicion_mas_frecuente": composicion_mas_frecuente,
        "chart_labels": [f["etiqueta"] for f in filas_presentacion],
        "chart_porcentajes": [f["frecuencia_relativa"] * 100 for f in filas_presentacion],
        "chart_apariciones": [f["apariciones"] for f in filas_presentacion],
    }


def distribucion_altos_bajos_a_vm(
    estadistica, rango_min: int, rango_max: int, cantidad_numeros: int, juego: Juego,
) -> dict:
    """Transforma una `EstadisticaCalculada` de tipo
    "distribucion_altos_bajos" (Etapa Z) en un view model listo para
    la plantilla. Nunca recalcula la métrica, nunca consulta
    repositorios.

    Expone el punto de corte y el tamaño real de cada franja
    (asimétricas: 21/22 para Baloto/Revancha, 19/20 para MiLoto) para
    que la plantilla pueda explicar la asimetría junto a la
    definición de los grupos, sin necesitar que el template conozca
    ningún detalle de cálculo por su cuenta.

    "Composición más frecuente" sigue el mismo criterio ya validado
    para pares/impares: excluye None/sin datos, incluye TODAS las
    categorías empatadas en el máximo, nunca elige una arbitraria."""
    punto_de_corte = _punto_de_corte_altos_bajos_vm(rango_min, rango_max)
    tamano_inferior = punto_de_corte - rango_min + 1
    tamano_superior = rango_max - punto_de_corte

    filas_ordenadas = sorted(estadistica.resultado["filas"], key=lambda f: int(f["valor"]))

    total_sorteos = filas_ordenadas[0]["total_sorteos"] if filas_ordenadas else 0

    filas_presentacion = []
    for f in filas_ordenadas:
        cantidad_inferiores = int(f["valor"])
        filas_presentacion.append({
            "cantidad_inferiores": cantidad_inferiores,
            "cantidad_superiores": cantidad_numeros - cantidad_inferiores,
            "etiqueta": _etiqueta_inferior_superior(cantidad_inferiores, cantidad_numeros),
            "apariciones": f["apariciones"],
            "frecuencia_relativa": f["frecuencia_relativa"],
        })

    composicion_mas_frecuente = None
    if total_sorteos > 0 and filas_presentacion:
        maximo = max(f["apariciones"] for f in filas_presentacion)
        if maximo > 0:
            composicion_mas_frecuente = [
                f["etiqueta"] for f in filas_presentacion if f["apariciones"] == maximo
            ]

    return {
        "juego_codigo": juego.codigo,
        "juego_nombre": juego.nombre,
        "rango_min": rango_min,
        "rango_max": rango_max,
        "cantidad_numeros": cantidad_numeros,
        "punto_de_corte": punto_de_corte,
        "franja_inferior_texto": f"{rango_min}–{punto_de_corte}",
        "franja_superior_texto": f"{punto_de_corte + 1}–{rango_max}",
        "tamano_inferior": tamano_inferior,
        "tamano_superior": tamano_superior,
        "hasta_numero_sorteo": estadistica.hasta_numero_sorteo,
        "total_sorteos": total_sorteos,
        "calculado_en": estadistica.calculado_en.isoformat() if estadistica.calculado_en else None,
        "filas": filas_presentacion,
        "composicion_mas_frecuente": composicion_mas_frecuente,
        "chart_labels": [f["etiqueta"] for f in filas_presentacion],
        "chart_porcentajes": [f["frecuencia_relativa"] * 100 for f in filas_presentacion],
        "chart_apariciones": [f["apariciones"] for f in filas_presentacion],
    }


def atrasos_numeros_a_vm(estadistica, rango_min: int, rango_max: int, juego: Juego) -> dict:
    """Transforma una `EstadisticaCalculada` de tipo "atrasos_numeros"
    (Etapa W) en un view model listo para la plantilla. Nunca
    recalcula la métrica -solo formatea lo que el orquestador ya
    calculó y persistió. `None` (nunca observado) se conserva tal
    cual en `filas`/`chart_valores` -el template decide cómo
    mostrarlo ("Nunca"/"N/D"), este View Model nunca lo convierte en
    0 ni en ningún otro valor numérico de reemplazo.

    "Mayor distancia observada" se calcula aquí (no en el template,
    para no repetir lógica de max()/filtrado de None en Jinja)
    EXCLUYENDO explícitamente los None -si todas las filas son None
    (juego sin sorteos o rango sin ninguna aparición), el campo queda
    en None y el template debe mostrar una etiqueta neutral, nunca
    "0"."""
    filas_ordenadas = sorted(estadistica.resultado["filas"], key=lambda f: int(f["valor"]))

    total_sorteos = filas_ordenadas[0]["total_sorteos"] if filas_ordenadas else 0

    distancias_observadas = [f["atraso"] for f in filas_ordenadas if f["atraso"] is not None]
    mayor_distancia = max(distancias_observadas) if distancias_observadas else None
    numeros_con_mayor_distancia = (
        [f["valor"] for f in filas_ordenadas if f["atraso"] == mayor_distancia]
        if mayor_distancia is not None else []
    )

    return {
        "juego_codigo": juego.codigo,
        "juego_nombre": juego.nombre,
        "rango_min": rango_min,
        "rango_max": rango_max,
        "hasta_numero_sorteo": estadistica.hasta_numero_sorteo,
        "total_sorteos": total_sorteos,
        "calculado_en": estadistica.calculado_en.isoformat() if estadistica.calculado_en else None,
        "filas": filas_ordenadas,
        "mayor_distancia": mayor_distancia,
        "numeros_con_mayor_distancia": numeros_con_mayor_distancia,
        "chart_labels": [f["valor"] for f in filas_ordenadas],
        "chart_valores": [f["atraso"] for f in filas_ordenadas],  # None se preserva; nunca 0 de relleno
    }


def construir_navegacion_estadisticas(
    juego_slug_actual: str, metrica_actual: str, tiene_superbalota_por_slug: dict[str, bool],
    nombres_reales: dict[str, str] | None = None, hasta_numero_sorteo: int | None = None,
) -> dict:
    """Navegación de dos niveles. `tiene_superbalota_por_slug` debe
    venir de la capacidad REAL de cada `LotteryGame`
    (`.has_superballot`, un atributo de clase del dominio), nunca
    inferida del slug -evita hardcodear qué juegos tienen superbalota
    fuera de `domain/games/`. `nombres_reales` (código -> nombre de
    `Juego.nombre`, la fuente de verdad persistida) es opcional: si no
    se provee (p. ej. sin conexión a BD), se usa una etiqueta estática
    de respaldo -nunca se rompe el render por falta de ese dato.

    Desde una métrica incompatible con otro juego (superbalota hacia
    MiLoto), el enlace de ESE juego en la navegación redirige a
    "frecuencia-numeros" en vez de reproducir una ruta que fallaría.

    Corte temporal (Etapa X) -decisión semántica deliberada, no un
    descuido: la numeración de sorteos de Baloto/Revancha (2081-2695
    en la base real) NO es comparable con la de MiLoto (532-589) -son
    juegos independientes con series temporales propias. Por eso:
      - `juegos_nav` NUNCA incluye el corte -cambiar de juego SIEMPRE
        vuelve al histórico completo del juego destino, sin
        excepción.
      - `metricas_nav` SÍ incluye `?hasta_numero_sorteo=N` cuando hay
        un corte activo -cambiar de métrica dentro del MISMO juego
        conserva el corte, porque la numeración sigue siendo la
        misma serie."""
    nombres_reales = nombres_reales or {}

    juegos_nav = []
    for slug, codigo in _SLUG_A_CODIGO.items():
        metrica_destino = metrica_actual
        if metrica_actual == "frecuencia-superbalota" and not tiene_superbalota_por_slug.get(slug, False):
            metrica_destino = "frecuencia-numeros"
        juegos_nav.append({
            "slug": slug,
            "nombre": nombres_reales.get(codigo) or _NOMBRE_VISIBLE_POR_SLUG[slug],
            "activo": slug == juego_slug_actual,
            "url": f"/estadisticas/{slug}/{metrica_destino}",  # NUNCA lleva corte -numeraciones no comparables entre juegos
        })

    def _url_metrica(metrica_id: str) -> str:
        base = f"/estadisticas/{juego_slug_actual}/{metrica_id}"
        if hasta_numero_sorteo is not None:
            return f"{base}?hasta_numero_sorteo={hasta_numero_sorteo}"
        return base

    metricas_nav = [{
        "id": "frecuencia-numeros", "etiqueta": _ETIQUETA_METRICA["frecuencia-numeros"],
        "url": _url_metrica("frecuencia-numeros"),
        "activo": metrica_actual == "frecuencia-numeros",
    }]
    if tiene_superbalota_por_slug.get(juego_slug_actual, False):
        metricas_nav.append({
            "id": "frecuencia-superbalota", "etiqueta": _ETIQUETA_METRICA["frecuencia-superbalota"],
            "url": _url_metrica("frecuencia-superbalota"),
            "activo": metrica_actual == "frecuencia-superbalota",
        })
    metricas_nav.append({
        "id": "frecuencia-observada-esperada", "etiqueta": _ETIQUETA_METRICA["frecuencia-observada-esperada"],
        "url": _url_metrica("frecuencia-observada-esperada"),
        "activo": metrica_actual == "frecuencia-observada-esperada",
    })
    metricas_nav.append({
        "id": "atrasos-numeros", "etiqueta": _ETIQUETA_METRICA["atrasos-numeros"],
        "url": _url_metrica("atrasos-numeros"),
        "activo": metrica_actual == "atrasos-numeros",
    })
    metricas_nav.append({
        "id": "distribucion-pares-impares", "etiqueta": _ETIQUETA_METRICA["distribucion-pares-impares"],
        "url": _url_metrica("distribucion-pares-impares"),
        "activo": metrica_actual == "distribucion-pares-impares",
    })
    metricas_nav.append({
        "id": "distribucion-altos-bajos", "etiqueta": _ETIQUETA_METRICA["distribucion-altos-bajos"],
        "url": _url_metrica("distribucion-altos-bajos"),
        "activo": metrica_actual == "distribucion-altos-bajos",
    })
    metricas_nav.append({
        "id": "distribucion-pares-consecutivos", "etiqueta": _ETIQUETA_METRICA["distribucion-pares-consecutivos"],
        "url": _url_metrica("distribucion-pares-consecutivos"),
        "activo": metrica_actual == "distribucion-pares-consecutivos",
    })
    metricas_nav.append({
        "id": "distribucion-racha-maxima", "etiqueta": _ETIQUETA_METRICA["distribucion-racha-maxima"],
        "url": _url_metrica("distribucion-racha-maxima"),
        "activo": metrica_actual == "distribucion-racha-maxima",
    })
    metricas_nav.append({
        "id": "repeticiones-entre-sorteos", "etiqueta": _ETIQUETA_METRICA["repeticiones-entre-sorteos"],
        "url": _url_metrica("repeticiones-entre-sorteos"),
        "activo": metrica_actual == "repeticiones-entre-sorteos",
    })

    return {
        "juegos_nav": juegos_nav,
        "metricas_nav": metricas_nav,
        "hasta_numero_sorteo": hasta_numero_sorteo,
        # Histórico completo de la MISMA métrica/juego actual -nunca
        # lleva query parameter, ni siquiera "?hasta_numero_sorteo="
        # vacío (cero no es sinónimo de histórico completo).
        "url_historico_completo": f"/estadisticas/{juego_slug_actual}/{metrica_actual}",
    }
