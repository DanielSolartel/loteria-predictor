"""
Caso de uso: CalcularYPersistirEstadistica.

Primer pipeline estadístico funcional de extremo a extremo (Etapa T):

    ResultadosHistoricosRepository -> motor puro -> serialización -> EstadisticaRepository

Vive en la capa de aplicación, igual que `ObtenerResumenSistema`
-orquesta puertos, nunca infraestructura concreta. No importa
SQLAlchemy ni ningún módulo de `infrastructure/`.

Catálogo de recetas: deliberadamente mínimo (Etapa Q proponía un
catálogo completo para 22+ métricas, pero esta etapa registra
únicamente `frecuencia_numeros`, para validar el pipeline con la
métrica más simple antes de escalar). Cada receta es un par de
funciones (calcular, serializar) -agregar una métrica nueva en el
futuro significa agregar una entrada a `_CATALOGO`, sin tocar
`CalcularYPersistirEstadistica` en sí.

Decisión de diseño: el caso de uso recibe `rango_min`/`rango_max`
como parámetros explícitos de `parametros_metrica`, no resuelve
internamente "qué juego es Baloto". La resolución "código de juego ->
rango numérico" (vía `BalotoGame().number_range`, la fuente de verdad
real del dominio) es responsabilidad de quien invoca este caso de uso
-mismo criterio que otros casos de uso reciben `juego_id` ya resuelto
en vez de buscar el juego por su cuenta cuando no es estrictamente
necesario.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Callable, Sequence
from typing import NamedTuple
from uuid import UUID

from app.application.estadisticas.motor.atrasos import (
    AtrasoObservado,
    calcular_atrasos_colores,
    calcular_atrasos_numeros,
    calcular_atrasos_numeros_colorloto,
    calcular_atrasos_pares_numero_color,
)
from app.application.estadisticas.motor.corte_temporal import filtrar_por_corte_temporal
from app.application.estadisticas.motor.consecutivos import (
    calcular_distribucion_pares_consecutivos,
    calcular_distribucion_racha_maxima,
)
from app.application.estadisticas.motor.repeticiones import (
    calcular_repeticiones_entre_sorteos,
    calcular_repeticiones_entre_sorteos_colorloto,
)
from app.application.estadisticas.motor.distribuciones import (
    calcular_distribucion_altos_bajos,
    calcular_distribucion_altos_bajos_colorloto,
    calcular_distribucion_pares_impares,
    calcular_distribucion_pares_impares_colorloto,
)
from app.application.estadisticas.motor.frecuencia import (
    calcular_frecuencia_colores,
    calcular_frecuencia_numeros,
    calcular_frecuencia_numeros_colorloto,
    calcular_frecuencia_pares_numero_color,
    calcular_frecuencia_superbalota,
    construir_tabla_frecuencia,
)
from app.application.estadisticas.tipos import (
    FilaFrecuencia, FrecuenciaObservada, ResultadoColorLoto, ResultadoNumerico,
)
from app.application.exceptions import ResultadoHistoricoInconsistenteError, TipoEstadisticaNoSoportadoError
from app.application.interfaces.color_repository import ColorRepository
from app.application.interfaces.estadistica_repository import EstadisticaCalculada, EstadisticaRepository
from app.application.interfaces.resultados_historicos_repository import ResultadosHistoricosRepository
from app.domain.value_objects.color import Color


def _calcular_frecuencia_numeros(
    historico: Sequence[ResultadoNumerico], parametros: dict,
) -> list[FrecuenciaObservada]:
    return calcular_frecuencia_numeros(historico, parametros["rango_min"], parametros["rango_max"])


def _calcular_frecuencia_superbalota(
    historico: Sequence[ResultadoNumerico], parametros: dict,
) -> list[FrecuenciaObservada]:
    """Reutiliza calcular_frecuencia_superbalota directamente, sin
    reimplementar nada: pool independiente de los números
    principales.

    Validación defensiva agregada (Etapa AD): antes de invocar el
    motor, se rechaza el histórico completo si algún sorteo carece
    de superbalota o la tiene fuera de rango -confirmado por
    auditoría que el motor, por su cuenta, excluía `None`
    silenciosamente (reduciendo el denominador sin avisar) y dejaba
    un valor fuera de rango como `ValueError` sin capturar por
    ningún handler. `_validar_historico_superbalota_consistente` es
    un helper específico (no generaliza `_validar_historico_consistente`,
    que valida una responsabilidad distinta: `numeros`/`cantidad_numeros`)
    y garantiza siempre `ResultadoHistoricoInconsistenteError` (500
    controlado) en vez de una pérdida silenciosa o un 500 sin
    controlar."""
    rango_min = parametros["rango_min"]
    rango_max = parametros["rango_max"]
    _validar_historico_superbalota_consistente(historico, rango_min, rango_max)
    return calcular_frecuencia_superbalota(historico, rango_min, rango_max)


def _calcular_tabla_frecuencia_numeros(
    historico: Sequence[ResultadoNumerico], parametros: dict,
) -> list[FilaFrecuencia]:
    """Reutiliza calcular_frecuencia_numeros + construir_tabla_frecuencia
    tal cual -no reimplementa K/N ni la diferencia. `n` (tamaño del
    universo) se deriva del rango, `k` (cantidad_numeros) viene
    directamente del dominio a través de `parametros_metrica` (nunca
    hardcodeado aquí ni en ningún otro punto de esta capa)."""
    rango_min, rango_max = parametros["rango_min"], parametros["rango_max"]
    frecuencias = calcular_frecuencia_numeros(historico, rango_min, rango_max)
    n = rango_max - rango_min + 1
    return construir_tabla_frecuencia(frecuencias, k=parametros["cantidad_numeros"], n=n)


def _calcular_atrasos_numeros(
    historico: Sequence[ResultadoNumerico], parametros: dict,
) -> list[AtrasoObservado]:
    """Reutiliza calcular_atrasos_numeros SIN pasar hasta_numero_sorteo
    -decisión semántica deliberada (Etapa W), NO un descuido: el
    orquestador YA filtró `historico` por el corte (paso 2 de
    `ejecutar()`, igual que las demás recetas). Si aquí se pasara
    también el corte crudo como argumento aritmético, la función
    usaría ese número como referencia INCLUSO SI NUNCA existió un
    sorteo con ese numero_sorteo real (comprobado explícitamente con
    el dataset de la Etapa W: sorteos 100/102/105,
    hasta_numero_sorteo=104 -> con el corte crudo la distancia sería
    4, con el histórico ya filtrado y sin pasar el corte, la función
    deriva sola la referencia del máximo numero_sorteo REAL presente
    -102-, dando distancia=2, la semántica aprobada). Por eso NO se
    modificó `_Receta.calcular` ni se agregó `hasta_numero_sorteo` a
    `parametros_metrica`: el filtrado que el orquestador ya hace es
    exactamente lo que esta receta necesita, sin ningún cambio de
    contrato."""
    return calcular_atrasos_numeros(historico, parametros["rango_min"], parametros["rango_max"])


def _validar_historico_consistente(
    historico: Sequence[ResultadoNumerico], cantidad_numeros: int, *,
    rango_min: int | None = None, rango_max: int | None = None,
) -> None:
    """Helper defensivo compartido (Etapa Z), reutilizado por
    `distribucion_pares_impares` y `distribucion_altos_bajos` -evita
    duplicar la misma lógica de validación en cada receta que la
    necesite (Opción B de la auditoría previa: helper reutilizable,
    no una validación global en todas las recetas ni una modificación
    del motor).

    Valida en orden fijo, sobre TODO el histórico antes de tocar el
    motor:
      1) cantidad exacta -len(numeros) == cantidad_numeros;
      2) sin duplicados -len(set(numeros)) == len(numeros);
      3) dentro de rango -SOLO si ambos límites se proporcionan.

    Histórico vacío es válido (nada que validar). Un solo sorteo
    inválido rechaza el CÁLCULO COMPLETO -nunca se descartan filas
    individuales ni se calcula una distribución parcial; se reúnen
    los `numero_sorteo` afectados por el primer tipo de inconsistencia
    encontrado (si hay sorteos con cantidad incorrecta, esos son los
    reportados; solo si todos pasan ese primer chequeo se evalúan
    duplicados, y así sucesivamente).

    Proporcionar SOLO uno de `rango_min`/`rango_max` es un error de
    programación de quien llama (una receta mal escrita), no una
    condición de datos -se distingue explícitamente de una
    inconsistencia de histórico con un `ValueError` (nunca la
    excepción de dominio, que es para datos corruptos, no para bugs
    de invocación; y nunca la sentencia `assert`, que desaparecería
    con optimizaciones de Python -esta comprobación es un `if`
    explícito seguido de `raise`, siempre activo)."""
    if (rango_min is None) != (rango_max is None):
        raise ValueError(
            "_validar_historico_consistente: rango_min y rango_max deben proporcionarse juntos"
        )

    con_cantidad_incorrecta = [r.numero_sorteo for r in historico if len(r.numeros) != cantidad_numeros]
    if con_cantidad_incorrecta:
        raise ResultadoHistoricoInconsistenteError(sorted(set(con_cantidad_incorrecta)), cantidad_numeros)

    con_duplicados = [r.numero_sorteo for r in historico if len(set(r.numeros)) != len(r.numeros)]
    if con_duplicados:
        raise ResultadoHistoricoInconsistenteError.por_duplicados(sorted(set(con_duplicados)))

    if rango_min is not None and rango_max is not None:
        fuera_de_rango = [
            r.numero_sorteo for r in historico
            if any(not (rango_min <= n <= rango_max) for n in r.numeros)
        ]
        if fuera_de_rango:
            raise ResultadoHistoricoInconsistenteError.por_rango(
                sorted(set(fuera_de_rango)), rango_min, rango_max,
            )


def _validar_historico_superbalota_consistente(
    historico: Sequence[ResultadoNumerico], rango_min: int, rango_max: int,
) -> None:
    """Helper defensivo ESPECÍFICO de superbalota (Etapa AD) -no
    generaliza `_validar_historico_consistente` (que valida
    `numeros`/`cantidad_numeros`, una responsabilidad distinta: esa
    función nunca tocó `superbalota`, y mezclar ambas complicaría su
    firma y su identidad ya usada 5 veces sin necesidad real).

    Política de integridad (confirmada por auditoría previa,
    respaldada por evidencia de dominio -no una suposición): para
    un juego con superbalota, `superbalota is None` en un
    `ResultadoNumerico` del histórico NUNCA puede surgir de una
    operación legítima del sistema actual -confirmado con las 3
    rutas de escritura reales (`RegistrarSorteo`, `SincronizarSorteos`,
    `EditarSorteo`), todas exigen la superbalota vía
    `StandardNumberGame.validate_draw` antes de persistir cualquier
    dato. Por tanto, `None` aquí es SIEMPRE evidencia de corrupción
    histórica (nunca un estado de negocio válido) y se rechaza el
    CÁLCULO COMPLETO -exactamente el mismo criterio "todo o nada" ya
    usado por `_validar_historico_consistente` para números
    principales, nunca una exclusión silenciosa que reduzca el
    denominador sin que el usuario lo sepa.

    Orden determinista: ausencia se evalúa ANTES que rango -un sorteo
    sin superbalota no tiene ningún valor que comparar contra el
    rango, así que declarar "ausente" primero es la única
    clasificación con sentido; solo tras confirmar que todos los
    sorteos tienen un valor se evalúa si ese valor cae dentro del
    rango esperado.

    Histórico vacío es válido (nada que validar) -mismo criterio ya
    establecido. No usa sentencias `assert` para esta validación
    funcional (mismo criterio ya aplicado en el helper de números
    principales)."""
    sin_superbalota = [r.numero_sorteo for r in historico if r.superbalota is None]
    if sin_superbalota:
        raise ResultadoHistoricoInconsistenteError.por_superbalota_ausente(sorted(set(sin_superbalota)))

    fuera_de_rango = [
        r.numero_sorteo for r in historico
        if not (rango_min <= r.superbalota <= rango_max)
    ]
    if fuera_de_rango:
        raise ResultadoHistoricoInconsistenteError.por_rango_superbalota(
            sorted(set(fuera_de_rango)), rango_min, rango_max,
        )


def _validar_historico_colorloto_consistente(
    historico: Sequence[ResultadoColorLoto], catalogo_colores: list[Color],
    cantidad_numeros: int, rango_min: int, rango_max: int,
) -> None:
    """Helper defensivo ESPECÍFICO de ColorLoto (Etapa AE-1) -no
    generaliza `_validar_historico_consistente` (que opera sobre
    `ResultadoNumerico.numeros`, un tipo distinto de
    `ResultadoColorLoto.pares`). El motor `calcular_frecuencia_numeros_colorloto`
    NO valida cantidad de pares ni color -confirmado por auditoría
    que un sorteo con cantidad de pares incorrecta se contaría igual
    como "1 sorteo válido" en `total_sorteos`, sesgando el
    denominador sin ningún aviso (mismo riesgo ya resuelto para las
    4 métricas de números principales); tampoco valida rango de
    número (ValueError real, pero SÍ existe -confirmado por
    ejecución real en la auditoría de diseño previa) ni color en
    absoluto (la función ni siquiera recibe el color de cada par).

    Orden determinista, confirmado en la auditoría de diseño previa:
    1) cantidad -sin la cantidad correcta de pares, no tiene sentido
       evaluar rango/color de balotas que no deberían existir o
       faltan; 2) rango de número; 3) color -catálogo completo
       (`catalogo_colores`, cargado UNA sola vez por
       `ColorRepository.listar_todos`, nunca una consulta por
       sorteo) resuelto en memoria contra `Color.esta_vigente_en(fecha_del_sorteo)`,
       agrupando por código para evitar una búsqueda lineal repetida.

    NO rechaza números repetidos, colores repetidos, ni pares
    exactos repetidos -el dominio actual (`ColorLotoGame.validate_draw`)
    los permite explícitamente, y no existe una regla oficial
    verificada dentro de este proyecto que los prohíba (ver
    ColorLotoGame.sample_space_size, que documenta ese mismo supuesto
    sin verificar). Rechazar aquí algo que el propio dominio permite
    sería una inconsistencia interna del sistema, no una defensa de
    integridad real.

    Histórico vacío es válido (nada que validar) -mismo criterio ya
    establecido 3 veces. No usa sentencias `assert` para esta
    validación funcional."""
    con_cantidad_incorrecta = [r.numero_sorteo for r in historico if len(r.pares) != cantidad_numeros]
    if con_cantidad_incorrecta:
        raise ResultadoHistoricoInconsistenteError.por_cantidad_pares_colorloto(
            sorted(set(con_cantidad_incorrecta)), cantidad_numeros,
        )

    con_numero_fuera_de_rango = [
        r.numero_sorteo for r in historico
        if any(not (rango_min <= numero <= rango_max) for numero, _color in r.pares)
    ]
    if con_numero_fuera_de_rango:
        raise ResultadoHistoricoInconsistenteError.por_rango_numero_colorloto(
            sorted(set(con_numero_fuera_de_rango)), rango_min, rango_max,
        )

    colores_por_codigo: dict[str, list[Color]] = {}
    for color in catalogo_colores:
        colores_por_codigo.setdefault(color.codigo, []).append(color)

    def _color_valido_en(codigo: str, fecha) -> bool:
        candidatos = colores_por_codigo.get(codigo)
        if not candidatos:
            return False
        return any(c.esta_vigente_en(fecha) for c in candidatos)

    con_color_invalido = [
        r.numero_sorteo for r in historico
        if any(not _color_valido_en(codigo, r.fecha) for _numero, codigo in r.pares)
    ]
    if con_color_invalido:
        raise ResultadoHistoricoInconsistenteError.por_color_colorloto_invalido(sorted(set(con_color_invalido)))


def _calcular_distribucion_pares_impares(
    historico: Sequence[ResultadoNumerico], parametros: dict,
) -> list[FrecuenciaObservada]:
    """Reutiliza calcular_distribucion_pares_impares SIN modificar el
    motor. Validación defensiva (Etapa Y, generalizada en Etapa Z):
    usa el helper compartido `_validar_historico_consistente` SIN
    límites de rango -la paridad no depende del rango, así que validar
    rango aquí sería una comprobación sin efecto sobre esta métrica
    específica. Valida cantidad y duplicados (Etapa Z corrige una
    laguna real: la validación original de Etapa Y solo cubría
    cantidad, dejando pasar duplicados sin detectarlos -un duplicado
    que sea par infla artificialmente esa categoría, mismo tipo de
    sesgo silencioso ya documentado para el caso de cantidad
    excedida).

    `parametros_metrica` de esta receta sigue siendo EXACTAMENTE
    `{"cantidad_numeros": K}` -sin agregar rango_min/rango_max, para
    no alterar `parametros_hash` ni la identidad de caché ya validada
    en Windows (Etapa Y, 1053 passed)."""
    cantidad_numeros = parametros["cantidad_numeros"]
    _validar_historico_consistente(historico, cantidad_numeros)
    return calcular_distribucion_pares_impares(historico, cantidad_numeros)


def _calcular_distribucion_altos_bajos(
    historico: Sequence[ResultadoNumerico], parametros: dict,
) -> list[FrecuenciaObservada]:
    """Reutiliza calcular_distribucion_altos_bajos SIN modificar el
    motor. Validación defensiva completa (Etapa Z): cantidad,
    duplicados Y rango -a diferencia de pares/impares, esta métrica
    SÍ depende directamente del rango (a través del punto de corte),
    confirmado por la auditoría previa: un número fuera de rango se
    clasificaría silenciosamente como "superior" sin ningún aviso, ya
    que el motor no llama a `_validar_rango` internamente para esta
    función. No se pasa `hasta_numero_sorteo` al motor -mismo criterio
    ya establecido para atrasos_numeros/distribucion_pares_impares: el
    orquestador ya filtró `historico` por el corte antes de invocar
    esta receta."""
    rango_min = parametros["rango_min"]
    rango_max = parametros["rango_max"]
    cantidad_numeros = parametros["cantidad_numeros"]
    _validar_historico_consistente(historico, cantidad_numeros, rango_min=rango_min, rango_max=rango_max)
    return calcular_distribucion_altos_bajos(historico, rango_min, rango_max, cantidad_numeros)


def _calcular_distribucion_pares_consecutivos(
    historico: Sequence[ResultadoNumerico], parametros: dict,
) -> list[FrecuenciaObservada]:
    """Reutiliza calcular_distribucion_pares_consecutivos SIN
    modificar el motor. Validación defensiva completa (Etapa AA):
    cantidad, duplicados Y rango.

    A diferencia de `distribucion_pares_impares` (que no valida rango
    porque la paridad no depende de él) y en la misma situación que
    `distribucion_altos_bajos`: el motor de esta función SÍ llama a
    `_validar_rango` internamente (confirmado por lectura de
    `consecutivos.py`), pero ese `ValueError` interno del motor NO
    está capturado por ningún handler -no existe manejador global de
    `ValueError` (deliberadamente, tras la corrección de Etapa Y) ni
    uno específico para este caso. Si se dejara que el motor fuera el
    único punto de validación, un histórico con un número fuera de
    rango produciría un 500 SIN CONTROLAR (sin mensaje seguro,
    potencialmente con traceback expuesto según configuración de
    FastAPI) en vez de la respuesta controlada ya establecida como
    patrón. Por eso Application valida PRIMERO (cantidad, duplicados,
    rango) con el mismo helper compartido, garantizando que
    `ResultadoHistoricoInconsistenteError` (500 controlado) se
    dispare siempre antes de que el motor tenga oportunidad de
    lanzar su propio `ValueError` sin control -doble defensa
    deliberada, no redundancia accidental: la del motor sigue viva
    como última línea de seguridad si alguna vez se invocara la
    función directamente sin pasar por esta receta."""
    rango_min = parametros["rango_min"]
    rango_max = parametros["rango_max"]
    cantidad_numeros = parametros["cantidad_numeros"]
    _validar_historico_consistente(historico, cantidad_numeros, rango_min=rango_min, rango_max=rango_max)
    return calcular_distribucion_pares_consecutivos(historico, rango_min, rango_max, cantidad_numeros)


def _calcular_distribucion_racha_maxima(
    historico: Sequence[ResultadoNumerico], parametros: dict,
) -> list[FrecuenciaObservada]:
    """Reutiliza calcular_distribucion_racha_maxima SIN modificar el
    motor. Validación defensiva completa (Etapa AB): cantidad,
    duplicados Y rango -mismo criterio exacto de
    `distribucion_pares_consecutivos`/`distribucion_altos_bajos`: el
    motor llama a `_validar_rango` internamente, pero ese `ValueError`
    no está capturado por ningún handler; Application valida primero
    para garantizar siempre `ResultadoHistoricoInconsistenteError`
    (500 controlado) en vez de un 500 sin controlar.

    Riesgo adicional confirmado en la auditoría previa a esta etapa:
    un sorteo con `numeros=()` (caso límite accidental, nunca
    alcanzable con datos reales por `StandardNumberGame.validate_draw`)
    produciría racha=0 en el motor, que la propia función recorta
    silenciosamente (nunca aparece como categoría "0") -sin la
    validación de cantidad en `_validar_historico_consistente`, ese
    sorteo desaparecería del conteo sin ningún aviso. La validación
    de cantidad exacta ya cubre este caso: un sorteo sin números
    nunca pasa `len(numeros) == cantidad_numeros`, así que se
    rechaza aquí, antes de llegar al motor."""
    rango_min = parametros["rango_min"]
    rango_max = parametros["rango_max"]
    cantidad_numeros = parametros["cantidad_numeros"]
    _validar_historico_consistente(historico, cantidad_numeros, rango_min=rango_min, rango_max=rango_max)
    return calcular_distribucion_racha_maxima(historico, rango_min, rango_max, cantidad_numeros)


def _calcular_distribucion_repeticiones_entre_sorteos(
    historico: Sequence[ResultadoNumerico], parametros: dict,
) -> list[FrecuenciaObservada]:
    """Reutiliza calcular_repeticiones_entre_sorteos SIN modificar el
    motor. Validación defensiva completa (Etapa AC): cantidad,
    duplicados Y rango -mismo criterio exacto de las 3 recetas
    recientes: el motor valida rango internamente (`_validar_rango`),
    pero ese `ValueError` no está capturado por ningún handler;
    Application valida primero para garantizar siempre
    `ResultadoHistoricoInconsistenteError` (500 controlado).

    Riesgo confirmado en la auditoría previa a esta etapa: el motor
    NO valida cantidad ni duplicados internamente. Un sorteo con más
    números de los esperados podría producir una intersección mayor
    que K, que `tabular_conteo_por_sorteo` recorta silenciosamente
    (confirmado con ejecución real: `total_sorteos=1` pero suma de
    apariciones=0) -mismo riesgo ya resuelto en las 3 recetas
    anteriores. Duplicados dentro de un sorteo también inflan
    artificialmente la intersección (confirmado). La validación de
    cantidad/duplicados en `_validar_historico_consistente` cubre
    ambos casos antes de llegar al motor.

    `FrecuenciaObservada.total_sorteos` aquí NO es la cantidad de
    sorteos del histórico -es la cantidad de TRANSICIONES VÁLIDAS
    (numero_sorteo_actual == numero_sorteo_anterior + 1). El campo no
    se renombra (mismo contrato/dataclass que las demás recetas); la
    presentación correcta ("Transiciones analizadas") vive
    exclusivamente en el View Model, nunca aquí ni en el motor."""
    rango_min = parametros["rango_min"]
    rango_max = parametros["rango_max"]
    cantidad_numeros = parametros["cantidad_numeros"]
    _validar_historico_consistente(historico, cantidad_numeros, rango_min=rango_min, rango_max=rango_max)
    return calcular_repeticiones_entre_sorteos(historico, rango_min, rango_max, cantidad_numeros)


def _serializar_frecuencia_observada(filas: list[FrecuenciaObservada]) -> dict:
    """dataclasses.asdict conserva TODOS los campos (valor,
    apariciones, total_sorteos, frecuencia_relativa) sin necesitar
    que este módulo los liste a mano -suficiente para reconstruir el
    resultado completo más adelante. Reutilizada tal cual para
    frecuencia_superbalota y distribucion_pares_impares:
    FrecuenciaObservada es exactamente la misma forma en los tres
    casos, no hace falta un serializador nuevo."""
    return {"filas": [dataclasses.asdict(f) for f in filas]}


def _serializar_tabla_frecuencia(filas: list[FilaFrecuencia]) -> dict:
    """dataclasses.asdict es recursivo: serializa también los
    dataclasses anidados (frecuencia_observada, probabilidad_teorica)
    sin fusionarlos -cada uno queda como su propio sub-dict, exactamente
    la misma separación que el motor ya garantiza en FilaFrecuencia."""
    return {"filas": [dataclasses.asdict(f) for f in filas]}


def _serializar_atrasos(filas: list[AtrasoObservado]) -> dict:
    """dataclasses.asdict conserva `atraso`/`ultimo_sorteo_aparicion`
    tal cual, incluido None -json.dumps (usado más abajo por
    PostgreSQL vía JSONB) serializa None como `null`, nunca como 0 o
    -1. No se inventa ningún valor de reemplazo aquí."""
    return {"filas": [dataclasses.asdict(f) for f in filas]}


# Unión mínima y tipada del resultado que puede producir cualquier
# receta -evita Any indiscriminado; cada receta declara concretamente
# cuál de los tres produce mediante sus propias anotaciones arriba.
_ResultadoMotor = list[FrecuenciaObservada] | list[FilaFrecuencia] | list[AtrasoObservado]


class _HistoricoColorLoto(NamedTuple):
    """Envoltorio del histórico de ColorLoto -viaja junto al catálogo
    COMPLETO de colores del juego (activos e inactivos, cargado UNA
    sola vez por `ColorRepository.listar_todos`, nunca una consulta
    por sorteo). Existe para que la receta de ColorLoto pueda validar
    integridad de color en memoria sin necesitar una segunda
    inyección de dependencia dispersa por el orquestador -el mismo
    objeto que `obtener_historico` ya construyó trae todo lo
    necesario para validar y para calcular."""

    pares: Sequence[ResultadoColorLoto]
    catalogo_colores: list[Color]


def _obtener_historico_numerico(
    historico_repo: ResultadosHistoricosRepository, color_repository: ColorRepository | None,
    juego_id: UUID, hasta_numero_sorteo: int | None,
) -> Sequence[ResultadoNumerico]:
    """Estrategia por defecto -reproduce EXACTAMENTE el comportamiento
    ya usado por las 9 recetas numéricas existentes, sin ningún
    cambio funcional. Ignora deliberadamente `color_repository` (las
    recetas numéricas nunca lo necesitan). Re-filtra defensivamente
    por corte -mismo criterio "no confiar ciegamente en que el
    llamador ya cortó bien" ya aplicado en todo el motor, aunque el
    repositorio ya filtra en SQL."""
    historico = historico_repo.listar_resultados_numericos(juego_id, hasta_numero_sorteo)
    return filtrar_por_corte_temporal(historico, hasta_numero_sorteo)


def _obtener_historico_colorloto(
    historico_repo: ResultadosHistoricosRepository, color_repository: ColorRepository | None,
    juego_id: UUID, hasta_numero_sorteo: int | None,
) -> _HistoricoColorLoto:
    """Estrategia específica de ColorLoto -trae el histórico de pares
    número-color Y el catálogo completo de colores en exactamente 2
    consultas totales (nunca una por sorteo): `listar_resultados_colorloto`
    ya filtra el corte en SQL (mismo patrón que la versión numérica),
    y `ColorRepository.listar_todos` trae TODO el catálogo del juego
    de una vez, para que la receta resuelva vigencia histórica por
    sorteo en memoria vía `Color.esta_vigente_en`, sin ninguna
    consulta adicional. Re-filtra `pares` defensivamente por corte
    -el catálogo de colores nunca depende del corte, no se filtra.

    `ValueError` explícito (nunca `assert`, que desaparecería
    silenciosamente bajo `python -O`, dejando pasar un
    `AttributeError` opaco en su lugar) documenta con claridad la
    consecuencia de un `color_repository` faltante."""
    if color_repository is None:
        raise ValueError(
            "_obtener_historico_colorloto: color_repository es obligatorio para ColorLoto "
            "-verifica la composición de dependencias del caso de uso",
        )
    pares = historico_repo.listar_resultados_colorloto(juego_id, hasta_numero_sorteo)
    pares = filtrar_por_corte_temporal(pares, hasta_numero_sorteo)
    catalogo = color_repository.listar_todos(juego_id)
    return _HistoricoColorLoto(pares=pares, catalogo_colores=catalogo)


def _calcular_frecuencia_numeros_colorloto(
    historico: "_HistoricoColorLoto", parametros: dict,
) -> list[FrecuenciaObservada]:
    """Reutiliza calcular_frecuencia_numeros_colorloto directamente,
    sin reimplementar nada ni modificar el motor. `historico` aquí es
    el envoltorio `_HistoricoColorLoto` construido por
    `_obtener_historico_colorloto` -nunca una lista de
    `ResultadoColorLoto` directamente, porque la validación de
    integridad necesita también el catálogo completo de colores ya
    resuelto (una sola consulta, hecha en `obtener_historico`, nunca
    aquí).

    Validación defensiva completa (Etapa AE-1) antes de invocar el
    motor: cantidad de pares, rango de número, y color -confirmado
    por auditoría que el motor NO valida ninguna de las tres (una
    cantidad incorrecta se contaría igual como "1 sorteo válido" en
    `total_sorteos`, sesgando el denominador sin aviso; un color
    inventado se acepta sin ningún error porque la función ni
    siquiera lo mira). `_validar_historico_colorloto_consistente`
    garantiza siempre `ResultadoHistoricoInconsistenteError` (500
    controlado) en vez de una pérdida silenciosa o una salida
    matemáticamente incorrecta."""
    rango_min = parametros["rango_min"]
    rango_max = parametros["rango_max"]
    cantidad_numeros = parametros["cantidad_numeros"]
    _validar_historico_colorloto_consistente(
        historico.pares, historico.catalogo_colores, cantidad_numeros, rango_min, rango_max,
    )
    return calcular_frecuencia_numeros_colorloto(historico.pares, rango_min, rango_max)


POLITICA_UNIVERSO_COLORES_ACTUAL = "vigentes_ultimo_sorteo_mas_observados_v1"
"""Marcador ESTÁTICO de la política de universo temporal de colores
vigente (Etapa AE-4P) -no una huella dinámica del catálogo, nunca
cambia cuando se agrega o retira un color. Se incluye dentro de
`parametros_metrica` de las dos recetas que dependen del universo de
colores (`frecuencia_colores_colorloto`, `frecuencia_pares_colorloto`)
para forzar, mediante el propio mecanismo de `parametros_hash`
(`calcular_parametros_hash`, SHA-256 del diccionario completo de
parámetros), que cualquier fila persistida ANTES de este marcador
-calculada bajo la política anterior (catálogo completo sin
filtrar)- deje de coincidir con la identidad de caché actual: su
`parametros_hash` guardado corresponde a un diccionario de solo 3
claves, mientras que `buscar_vigente` ahora calcula el hash sobre un
diccionario de 4 claves -distinto por construcción, sin necesitar
ningún SQL manual ni migración. Las filas antiguas NO se borran: sólo
dejan de ser encontradas por `WHERE parametros_hash == hash_calculado`,
permaneciendo en la tabla como registros huérfanos e inofensivos
hasta que la próxima invalidación natural (por sorteo o por mutación
de paleta) las alcance.

NUNCA se agrega a `frecuencia_numeros_colorloto` ni
`atrasos_numeros_colorloto` -ninguna de las dos depende del universo
de colores (ignoran el color por completo), así que agregar el
marcador ahí sería ruido sin ningún propósito real, y además
invalidaría innecesariamente cachés que la corrección de AE-4P nunca
tocó.

Nunca reemplaza la invalidación explícita de paleta ya implementada
en `GestionarPaletaColores` -ambos mecanismos son complementarios: el
marcador resuelve el despliegue inicial (filas ya persistidas antes
de este cambio de versión), la invalidación explícita resuelve
mutaciones futuras de la paleta después del despliegue."""


def _codigos_colores_vigentes_en_referencia(historico: "_HistoricoColorLoto") -> list[str]:
    """Universo temporal de colores para las métricas de ColorLoto que
    dependen del catálogo (Etapa AE-4P) -devuelve los códigos de color
    VIGENTES en la fecha del sorteo real con mayor `numero_sorteo`
    dentro de `historico.pares` (ya filtrado por corte por el
    orquestador; nunca se deriva la fecha desde `hasta_numero_sorteo`
    directamente -si el corte solicitado supera el último sorteo real,
    la referencia sigue siendo la fecha de ese último sorteo real, no
    una fecha inexistente).

    Política de producto aprobada (Etapa AE-4P): universo inicial =
    vigentes en esa fecha; los colores realmente OBSERVADOS que no
    estén en este universo inicial (p.ej. un color ya retirado antes
    de la referencia, pero presente en el histórico filtrado) se
    preservan igualmente -nunca aquí: cada motor ya realiza esa unión
    internamente (`set(colores_vigentes) | set(observados)`,
    confirmado por auditoría del código real de `atrasos.py` y
    `frecuencia.py`), así que este helper NUNCA necesita agregar los
    observados por su cuenta ni duplicar esa regla.

    Histórico vacío -> `[]`, determinista: no existe ningún sorteo
    real del cual derivar una fecha de referencia -sin fecha, no hay
    universo inicial que resolver (el resultado final de la métrica
    también queda vacío, ya que tampoco hay observados que agregar).

    Nunca consulta repositorios -recibe `historico` ya construido por
    `_obtener_historico_colorloto`, con el catálogo COMPLETO ya
    cargado en una sola consulta compartida; nunca N+1, nunca una
    llamada adicional a `listar_vigentes`. No muta `historico` ni su
    catálogo. Nunca usa `assert` (esta es una regla de negocio, no una
    invariante interna que deba desaparecer bajo `python -O`).

    Reutilizado por AE-2 y AE-3; queda listo para una futura AE-5."""
    if not historico.pares:
        return []
    sorteo_referencia = max(historico.pares, key=lambda r: r.numero_sorteo)
    fecha_referencia = sorteo_referencia.fecha
    return sorted(c.codigo for c in historico.catalogo_colores if c.esta_vigente_en(fecha_referencia))


def _calcular_frecuencia_colores_colorloto(
    historico: "_HistoricoColorLoto", parametros: dict,
) -> list[FrecuenciaObservada]:
    """Reutiliza calcular_frecuencia_colores directamente, sin
    reimplementar nada ni modificar el motor (Etapa AE-2). Mismo
    envoltorio `_HistoricoColorLoto` y misma validación defensiva que
    `frecuencia_numeros_colorloto` -la integridad histórica (cantidad
    de pares, rango de número, color) es independiente de CUÁL
    métrica se calcule después sobre el mismo histórico validado, así
    que no se duplica ninguna regla.

    `colores_vigentes` para el motor se deriva de los colores VIGENTES
    en la fecha del último sorteo real del histórico ya filtrado
    (Etapa AE-4P, `_codigos_colores_vigentes_en_referencia`) -nunca el
    catálogo completo sin filtrar (corregido: un color futuro nunca
    observado, con `vigente_desde` posterior a esa fecha, ya NO
    aparece en cortes anteriores a su vigencia). Un color realmente
    observado que ya no esté vigente en la referencia (retirado) se
    preserva igual, gracias a la unión que el propio motor ya realiza
    internamente -nunca se pierde un dato observado."""
    rango_min = parametros["rango_min"]
    rango_max = parametros["rango_max"]
    cantidad_numeros = parametros["cantidad_numeros"]
    _validar_historico_colorloto_consistente(
        historico.pares, historico.catalogo_colores, cantidad_numeros, rango_min, rango_max,
    )
    colores_vigentes = _codigos_colores_vigentes_en_referencia(historico)
    return calcular_frecuencia_colores(historico.pares, colores_vigentes)


def _calcular_frecuencia_pares_colorloto(
    historico: "_HistoricoColorLoto", parametros: dict,
) -> list[FrecuenciaObservada]:
    """Reutiliza calcular_frecuencia_pares_numero_color directamente,
    sin reimplementar nada ni modificar el motor (Etapa AE-3). Mismo
    envoltorio `_HistoricoColorLoto` y misma validación defensiva
    compartida con AE-1/AE-2 -no se duplica ninguna regla.

    `FrecuenciaObservada.valor` codifica cada par como
    `f"{numero}-{color_codigo}"` (contrato ya existente del motor,
    Paso 13 -no una codificación nueva inventada aquí). Es
    deserializable de forma INEQUÍVOCA con `valor.split("-", maxsplit=1)`:
    el número siempre precede al primer guión de la cadena y nunca
    contiene un guión propio (es un entero positivo formateado con
    `f'{numero}'`), así que el primer guión SIEMPRE delimita
    correctamente número de color, incluso si un código de color
    futuro llegara a contener guiones -`maxsplit=1` nunca corta
    dentro del resto de la cadena. Esta capa de Application NO
    reimplementa el parseo -expone el contrato para que el VM lo use
    consistentemente en un único lugar (ver `frecuencia_pares_colorloto_a_vm`)."""
    rango_min = parametros["rango_min"]
    rango_max = parametros["rango_max"]
    cantidad_numeros = parametros["cantidad_numeros"]
    _validar_historico_colorloto_consistente(
        historico.pares, historico.catalogo_colores, cantidad_numeros, rango_min, rango_max,
    )
    colores_vigentes = _codigos_colores_vigentes_en_referencia(historico)
    return calcular_frecuencia_pares_numero_color(historico.pares, rango_min, rango_max, colores_vigentes)


def _calcular_atrasos_numeros_colorloto(
    historico: "_HistoricoColorLoto", parametros: dict,
) -> list[AtrasoObservado]:
    """Reutiliza calcular_atrasos_numeros_colorloto directamente, sin
    reimplementar nada ni modificar el motor (Etapa AE-4). Mismo
    envoltorio `_HistoricoColorLoto` y misma validación defensiva
    compartida con AE-1/AE-2/AE-3 -no se duplica ninguna regla.

    NUNCA se pasa `hasta_numero_sorteo` al motor -mismo precedente
    exacto ya establecido por `_calcular_atrasos_numeros` (la receta
    numérica ya conectada desde la Etapa W): el orquestador YA filtró
    `historico.pares` por el corte antes de llegar aquí, y el motor,
    al recibir `hasta_numero_sorteo=None` (su propio default), deriva
    la referencia correcta como el máximo `numero_sorteo` del propio
    histórico ya filtrado (`_filtrar_por_corte` interno del módulo
    `atrasos.py`) -pasar el corte crudo aquí produciría una referencia
    incorrecta si ese número de sorteo exacto no existe en el
    histórico real, exactamente el mismo riesgo ya documentado y
    evitado en la Etapa W.

    `AtrasoObservado.valor` es un string (mismo patrón que
    `FrecuenciaObservada.valor`, nunca `numero` directamente) -el VM
    deserializa a entero, igual que en las tres recetas anteriores de
    ColorLoto."""
    rango_min = parametros["rango_min"]
    rango_max = parametros["rango_max"]
    cantidad_numeros = parametros["cantidad_numeros"]
    _validar_historico_colorloto_consistente(
        historico.pares, historico.catalogo_colores, cantidad_numeros, rango_min, rango_max,
    )
    return calcular_atrasos_numeros_colorloto(historico.pares, rango_min, rango_max)


def _calcular_atrasos_colores_colorloto(
    historico: "_HistoricoColorLoto", parametros: dict,
) -> list[AtrasoObservado]:
    """Reutiliza calcular_atrasos_colores directamente, sin
    reimplementar nada ni modificar el motor (Etapa AE-5). Mismo
    envoltorio `_HistoricoColorLoto` y misma validación defensiva
    compartida con AE-1/AE-2/AE-3/AE-4 -no se duplica ninguna regla.

    `colores_vigentes` para el motor se deriva del mismo helper ya
    validado por AE-4P (`_codigos_colores_vigentes_en_referencia`):
    colores VIGENTES en la fecha del último sorteo real del histórico
    ya filtrado, más cualquier color realmente OBSERVADO que ya no
    esté vigente en esa referencia (retirado) -unión que el propio
    motor ya realiza internamente, nunca duplicada aquí. Mismo
    contrato exacto ya reutilizado por `frecuencia_colores_colorloto`
    y `frecuencia_pares_colorloto` -AE-5 no crea ninguna política
    paralela.

    NUNCA se pasa `hasta_numero_sorteo` al motor -mismo precedente
    exacto ya establecido por `_calcular_atrasos_numeros_colorloto`
    (Etapa AE-4): el orquestador YA filtró `historico.pares` por el
    corte antes de llegar aquí, y el motor, al recibir
    `hasta_numero_sorteo=None` (su propio default), deriva la
    referencia correcta como el máximo `numero_sorteo` del propio
    histórico ya filtrado -pasar el corte crudo aquí sería doble
    aplicación, mismo riesgo ya evitado en AE-4.

    `AtrasoObservado.valor` es el CÓDIGO del color (string, ej.
    "ROJO") -mismo patrón que `FrecuenciaObservada.valor` en
    `frecuencia_colores_colorloto`; el VM deserializa/estiliza igual
    que esa receta, nunca aquí (esta función no conoce presentación)."""
    rango_min = parametros["rango_min"]
    rango_max = parametros["rango_max"]
    cantidad_numeros = parametros["cantidad_numeros"]
    _validar_historico_colorloto_consistente(
        historico.pares, historico.catalogo_colores, cantidad_numeros, rango_min, rango_max,
    )
    colores_vigentes = _codigos_colores_vigentes_en_referencia(historico)
    return calcular_atrasos_colores(historico.pares, colores_vigentes)


def _calcular_atrasos_pares_colorloto(
    historico: "_HistoricoColorLoto", parametros: dict,
) -> list[AtrasoObservado]:
    """Reutiliza calcular_atrasos_pares_numero_color directamente,
    sin reimplementar nada ni modificar el motor (Etapa AE-6). Mismo
    envoltorio `_HistoricoColorLoto` y misma validación defensiva
    compartida con AE-1/AE-2/AE-3/AE-4/AE-5 -no se duplica ninguna
    regla.

    Firma real del motor confirmada por auditoría (distinta de
    `calcular_atrasos_colores`, que solo recibe 2 argumentos):
    `calcular_atrasos_pares_numero_color(resultados, rango_min,
    rango_max, colores_vigentes, hasta_numero_sorteo=None)` -mismo
    patrón de `rango_min`/`rango_max` ya usado por
    `_calcular_atrasos_numeros_colorloto` (AE-4), combinado con el
    mismo `colores_vigentes` derivado por el helper temporal ya
    usado por `_calcular_atrasos_colores_colorloto` (AE-5) -AE-6 no
    introduce ningún patrón nuevo, combina los dos ya validados.

    `colores_vigentes` se deriva del mismo helper ya validado por
    AE-4P (`_codigos_colores_vigentes_en_referencia`): colores
    VIGENTES en la fecha del último sorteo real del histórico ya
    filtrado, más cualquier color realmente OBSERVADO que ya no
    esté vigente en esa referencia (retirado) -unión que el propio
    motor ya realiza internamente (`colores_a_reportar =
    set(colores_vigentes) | {c for _, c in todos_los_pares}`,
    confirmado por lectura directa del motor), nunca duplicada
    aquí. Mismo contrato exacto ya reutilizado por
    `frecuencia_pares_colorloto`/`atrasos_colores_colorloto` -AE-6
    no crea ninguna política paralela.

    NUNCA se pasa `hasta_numero_sorteo` al motor -mismo precedente
    exacto ya establecido por AE-4/AE-5: el orquestador YA filtró
    `historico.pares` por el corte antes de llegar aquí, y el
    motor, al recibir `hasta_numero_sorteo=None` (su propio
    default), deriva la referencia correcta como el máximo
    `numero_sorteo` del propio histórico ya filtrado -pasar el
    corte crudo aquí sería doble aplicación, mismo riesgo ya
    evitado en AE-4/AE-5. Exactamente 4 argumentos posicionales
    efectivos al motor -confirmado con espionaje en los tests.

    `AtrasoObservado.valor` codifica cada par como
    `f"{numero}-{color}"` (contrato ya existente del motor,
    idéntico al usado por `frecuencia_pares_colorloto`) -el VM
    deserializa/estiliza igual que esa receta, nunca aquí (esta
    función no conoce presentación).

    Orden determinista del universo de 42 pares: confirmado por
    auditoría que coincide exactamente con el orden numérico de
    `frecuencia_pares_colorloto` para el dominio real 1..7 (un solo
    dígito) -una fragilidad latente del motor compartido para
    rangos hipotéticos de dos dígitos queda explícitamente fuera
    de alcance de esta etapa, como deuda técnica no bloqueante,
    sin modificar el motor puro."""
    rango_min = parametros["rango_min"]
    rango_max = parametros["rango_max"]
    cantidad_numeros = parametros["cantidad_numeros"]
    _validar_historico_colorloto_consistente(
        historico.pares, historico.catalogo_colores, cantidad_numeros, rango_min, rango_max,
    )
    colores_vigentes = _codigos_colores_vigentes_en_referencia(historico)
    return calcular_atrasos_pares_numero_color(historico.pares, rango_min, rango_max, colores_vigentes)


def _calcular_repeticiones_entre_sorteos_colorloto(
    historico: "_HistoricoColorLoto", parametros: dict,
) -> list[FrecuenciaObservada]:
    """Reutiliza calcular_repeticiones_entre_sorteos_colorloto
    directamente, sin reimplementar nada ni modificar el motor
    (Etapa AE-7). Mismo envoltorio `_HistoricoColorLoto` y misma
    validación defensiva compartida con AE-1 a AE-6 -no se
    duplica ninguna regla.

    Firma real del motor: `calcular_repeticiones_entre_sorteos_colorloto
    (resultados, rango_min, rango_max, cantidad_balotas,
    hasta_numero_sorteo=None)` -exactamente 4 argumentos
    posicionales efectivos, NUNCA `hasta_numero_sorteo`: el
    orquestador YA filtró `historico.pares` por el corte antes de
    llegar aquí, mismo precedente exacto ya establecido por las
    seis recetas anteriores de ColorLoto.

    El motor ignora el color por completo (`for n, _ in r.pares`
    en ambos puntos donde itera sobre los pares, confirmado por
    lectura directa) -por eso esta receta nunca deriva
    `colores_vigentes` ni pasa ningún parámetro relacionado con
    la paleta al motor: un cambio de paleta no puede alterar el
    resultado matemático de esta métrica.

    Usa intersección de MULTICONJUNTOS (no de conjuntos): un
    número que aparece dos veces en ambos sorteos de una
    transición aporta 2 al conteo de repetidos, no 1 -confirmado
    por el propio docstring del módulo y por ejecución real en
    la auditoría previa a esta implementación.

    Una transición solo es válida cuando `numero_sorteo_actual ==
    numero_sorteo_anterior + 1`; un hueco en la numeración nunca
    fabrica una transición. `FrecuenciaObservada.total_sorteos`
    en el resultado de ESTA función **no** es la cantidad de
    sorteos del histórico, sino la cantidad de TRANSICIONES
    VÁLIDAS -mismo criterio y mismo nombre de campo ya usado por
    `distribucion_repeticiones_entre_sorteos` (Etapa AC, la
    versión numérica ya validada); el renombrado a
    "Transiciones analizadas" vive exclusivamente en el View
    Model, nunca aquí ni en el motor."""
    rango_min = parametros["rango_min"]
    rango_max = parametros["rango_max"]
    cantidad_numeros = parametros["cantidad_numeros"]
    _validar_historico_colorloto_consistente(
        historico.pares, historico.catalogo_colores, cantidad_numeros, rango_min, rango_max,
    )
    return calcular_repeticiones_entre_sorteos_colorloto(historico.pares, rango_min, rango_max, cantidad_numeros)


_RANGO_REAL_COLORLOTO = (1, 7)
"""Rango numérico REAL y FIJO de ColorLoto (1..7), confirmado por
el reglamento oficial documentado en `domain/games/colorloto.py`.
A diferencia de las 9 recetas numéricas (que sirven a TRES juegos
con rangos DISTINTOS -Baloto 1-43, MiLoto 1-39- y por eso deben
leer `rango_min`/`rango_max` dinámicamente de cada `Juego`),
ColorLoto es un único juego con un único rango que nunca varía
-usarlo como constante aquí, en vez de pasarlo a través de
`parametros_metrica`, es lo que permite que la identidad de
caché de esta receta sea exactamente `{"cantidad_numeros": 6}`,
sin `rango_min`/`rango_max` -el resultado de paridad NUNCA
depende de esos límites, solo la VALIDACIÓN previa de integridad
los necesita."""


def _calcular_distribucion_pares_impares_colorloto(
    historico: "_HistoricoColorLoto", parametros: dict,
) -> list[FrecuenciaObservada]:
    """Reutiliza calcular_distribucion_pares_impares_colorloto
    directamente, sin reimplementar nada ni modificar el motor
    (Etapa AE-8). Mismo envoltorio `_HistoricoColorLoto` y misma
    validación defensiva compartida con AE-1 a AE-7 -no se
    duplica ninguna regla.

    Firma real del motor: `calcular_distribucion_pares_impares_colorloto
    (resultados, cantidad_balotas, hasta_numero_sorteo=None)`
    -exactamente 2 argumentos posicionales efectivos, NUNCA
    `hasta_numero_sorteo`: el orquestador YA filtró
    `historico.pares` por el corte antes de llegar aquí, mismo
    precedente exacto ya establecido por las siete recetas
    anteriores de ColorLoto.

    El motor ignora el color por completo (`for n, _ in r.pares`,
    confirmado por lectura directa) -por eso esta receta nunca
    deriva `colores_vigentes` ni pasa ningún parámetro
    relacionado con la paleta: un cambio de paleta no puede
    alterar el resultado matemático de esta métrica. Mismo
    criterio ya aplicado por `_calcular_repeticiones_entre_sorteos_colorloto`
    (Etapa AE-7).

    La validación de integridad previa sí necesita rango (para
    confirmar que cada número del histórico está dentro de
    1..7) -usa `_RANGO_REAL_COLORLOTO`, la constante del rango
    real y fijo del juego, en vez de leerlo de `parametros`: así
    la identidad de caché persistida queda exactamente
    `{"cantidad_numeros": 6}`, sin `rango_min`/`rango_max` -el
    resultado de paridad nunca depende de esos límites, solo la
    validación de integridad los necesita.

    Multiplicidad: un número par repetido dentro del mismo
    sorteo ocupa otra posición y vuelve a contar (confirmado por
    lectura y ejecución real del motor en la auditoría previa a
    esta implementación) -cada una de las 6 balotas contribuye
    independientemente a par o impar, así que
    `cantidad_pares + cantidad_impares = cantidad_numeros` se
    cumple siempre, con o sin repetición de número.

    Reutiliza `_serializar_frecuencia_observada` sin cambios
    -mismo tipo `FrecuenciaObservada` ya usado por AE-7 y por
    `distribucion_pares_impares` (la versión numérica ya
    validada, Etapa Y)."""
    cantidad_numeros = parametros["cantidad_numeros"]
    rango_min, rango_max = _RANGO_REAL_COLORLOTO
    _validar_historico_colorloto_consistente(
        historico.pares, historico.catalogo_colores, cantidad_numeros, rango_min, rango_max,
    )
    return calcular_distribucion_pares_impares_colorloto(historico.pares, cantidad_numeros)


def _calcular_distribucion_altos_bajos_colorloto(
    historico: "_HistoricoColorLoto", parametros: dict,
) -> list[FrecuenciaObservada]:
    """Reutiliza calcular_distribucion_altos_bajos_colorloto
    directamente, sin reimplementar nada ni modificar el motor
    (Etapa AE-9). Mismo envoltorio `_HistoricoColorLoto` y misma
    validación defensiva compartida con AE-1 a AE-8 -no se
    duplica ninguna regla.

    Firma real del motor: `calcular_distribucion_altos_bajos_colorloto
    (resultados, rango_min, rango_max, cantidad_balotas,
    hasta_numero_sorteo=None)` -exactamente 4 argumentos
    posicionales efectivos, NUNCA `hasta_numero_sorteo`: el
    orquestador YA filtró `historico.pares` por el corte antes de
    llegar aquí, mismo precedente exacto ya establecido por las
    ocho recetas anteriores de ColorLoto.

    A DIFERENCIA de `_calcular_distribucion_pares_impares_colorloto`
    (Etapa AE-8), aquí `rango_min`/`rango_max` SÍ forman parte de
    `parametros` -confirmado por auditoría que el resultado de
    esta métrica SÍ depende materialmente del rango: el motor
    calcula `corte = _punto_de_corte_altos_bajos(rango_min,
    rango_max)` y clasifica cada número como "bajo" (`n <=
    corte`) o "alto" según ese umbral -dos ejecuciones con rangos
    distintos producirían resultados distintos con el mismo
    histórico. AE-8 fue la EXCEPCIÓN (su motor de paridad nunca
    recibe rango), no la regla general: el patrón correcto,
    confirmado contra las identidades reales de AE-4/AE-6/AE-7,
    es incluir el rango en `parametros` siempre que el motor lo
    reciba como argumento -mismo criterio aquí.

    El motor ignora el color por completo (`for n, _ in r.pares`,
    confirmado por lectura directa) -por eso esta receta nunca
    deriva `colores_vigentes` ni incluye el marcador de política
    en `parametros`: un cambio de paleta no puede alterar el
    resultado matemático de esta métrica.

    `valor` en cada fila serializada es la cantidad de NÚMEROS
    BAJOS del sorteo (`n <= corte`, confirmado citando el bloque
    exacto del motor en la auditoría) -para el rango real 1..7 el
    corte es 3: bajos={1,2,3}, altos={4,5,6,7}. Multiplicidad
    preservada: una aparición repetida vuelve a contar. La
    traducción a "cantidad_altos"/etiquetas compuestas vive
    exclusivamente en el View Model, nunca aquí ni en el motor.

    Reutiliza `_serializar_frecuencia_observada` sin cambios
    -mismo tipo `FrecuenciaObservada` ya usado por AE-7/AE-8 y
    por `distribucion_altos_bajos` (la versión numérica ya
    validada, Etapa Z)."""
    rango_min = parametros["rango_min"]
    rango_max = parametros["rango_max"]
    cantidad_numeros = parametros["cantidad_numeros"]
    _validar_historico_colorloto_consistente(
        historico.pares, historico.catalogo_colores, cantidad_numeros, rango_min, rango_max,
    )
    return calcular_distribucion_altos_bajos_colorloto(historico.pares, rango_min, rango_max, cantidad_numeros)


class _Receta(NamedTuple):
    calcular: Callable[[Sequence[ResultadoNumerico], dict], _ResultadoMotor]
    serializar: Callable[[_ResultadoMotor], dict]
    obtener_historico: Callable[
        [ResultadosHistoricosRepository, "ColorRepository | None", UUID, "int | None"], object,
    ] = _obtener_historico_numerico


_CATALOGO: dict[str, _Receta] = {
    "frecuencia_numeros": _Receta(calcular=_calcular_frecuencia_numeros, serializar=_serializar_frecuencia_observada),
    "frecuencia_superbalota": _Receta(
        calcular=_calcular_frecuencia_superbalota, serializar=_serializar_frecuencia_observada,
    ),
    "tabla_frecuencia_numeros": _Receta(
        calcular=_calcular_tabla_frecuencia_numeros, serializar=_serializar_tabla_frecuencia,
    ),
    "atrasos_numeros": _Receta(calcular=_calcular_atrasos_numeros, serializar=_serializar_atrasos),
    "distribucion_pares_impares": _Receta(
        calcular=_calcular_distribucion_pares_impares, serializar=_serializar_frecuencia_observada,
    ),
    "distribucion_altos_bajos": _Receta(
        calcular=_calcular_distribucion_altos_bajos, serializar=_serializar_frecuencia_observada,
    ),
    "distribucion_pares_consecutivos": _Receta(
        calcular=_calcular_distribucion_pares_consecutivos, serializar=_serializar_frecuencia_observada,
    ),
    "distribucion_racha_maxima": _Receta(
        calcular=_calcular_distribucion_racha_maxima, serializar=_serializar_frecuencia_observada,
    ),
    "distribucion_repeticiones_entre_sorteos": _Receta(
        calcular=_calcular_distribucion_repeticiones_entre_sorteos, serializar=_serializar_frecuencia_observada,
    ),
    "frecuencia_numeros_colorloto": _Receta(
        calcular=_calcular_frecuencia_numeros_colorloto, serializar=_serializar_frecuencia_observada,
        obtener_historico=_obtener_historico_colorloto,
    ),
    "frecuencia_colores_colorloto": _Receta(
        calcular=_calcular_frecuencia_colores_colorloto, serializar=_serializar_frecuencia_observada,
        obtener_historico=_obtener_historico_colorloto,
    ),
    "frecuencia_pares_colorloto": _Receta(
        calcular=_calcular_frecuencia_pares_colorloto, serializar=_serializar_frecuencia_observada,
        obtener_historico=_obtener_historico_colorloto,
    ),
    "atrasos_numeros_colorloto": _Receta(
        calcular=_calcular_atrasos_numeros_colorloto, serializar=_serializar_atrasos,
        obtener_historico=_obtener_historico_colorloto,
    ),
    "atrasos_colores_colorloto": _Receta(
        calcular=_calcular_atrasos_colores_colorloto, serializar=_serializar_atrasos,
        obtener_historico=_obtener_historico_colorloto,
    ),
    "atrasos_pares_colorloto": _Receta(
        calcular=_calcular_atrasos_pares_colorloto, serializar=_serializar_atrasos,
        obtener_historico=_obtener_historico_colorloto,
    ),
    "repeticiones_entre_sorteos_colorloto": _Receta(
        calcular=_calcular_repeticiones_entre_sorteos_colorloto, serializar=_serializar_frecuencia_observada,
        obtener_historico=_obtener_historico_colorloto,
    ),
    "distribucion_pares_impares_colorloto": _Receta(
        calcular=_calcular_distribucion_pares_impares_colorloto, serializar=_serializar_frecuencia_observada,
        obtener_historico=_obtener_historico_colorloto,
    ),
    "distribucion_altos_bajos_colorloto": _Receta(
        calcular=_calcular_distribucion_altos_bajos_colorloto, serializar=_serializar_frecuencia_observada,
        obtener_historico=_obtener_historico_colorloto,
    ),
}


class CalcularYPersistirEstadistica:
    def __init__(
        self, historico_repository: ResultadosHistoricosRepository, estadistica_repository: EstadisticaRepository,
        color_repository: ColorRepository | None = None,
    ):
        self._historico = historico_repository
        self._estadisticas = estadistica_repository
        self._color_repository = color_repository

    def ejecutar(
        self, juego_id: UUID, tipo_estadistica: str, hasta_numero_sorteo: int | None = None,
        parametros_metrica: dict | None = None,
    ) -> EstadisticaCalculada:
        parametros_metrica = parametros_metrica or {}

        receta = _CATALOGO.get(tipo_estadistica)
        if receta is None:
            raise TipoEstadisticaNoSoportadoError(tipo_estadistica)

        # 1. cache: si existe una estadística vigente, se devuelve
        # directamente -NUNCA se consulta el histórico ni se ejecuta
        # el motor en ese caso.
        vigente = self._estadisticas.buscar_vigente(juego_id, tipo_estadistica, hasta_numero_sorteo, parametros_metrica)
        if vigente is not None:
            return vigente

        # 2. cache miss: obtener histórico -cada estrategia
        # (`receta.obtener_historico`) ya filtra por corte
        # defensivamente hacia dentro (mismo criterio "no confiar
        # ciegamente en que el llamador ya cortó bien" ya aplicado en
        # todo el motor), porque la forma exacta del resultado difiere
        # entre la fuente numérica (lista simple) y la de ColorLoto
        # (envoltorio con catálogo de colores) -el orquestador nunca
        # bifurca por `tipo_estadistica` para elegir el repositorio ni
        # para decidir cómo filtrar, solo despacha vía el propio
        # catálogo (patrón Strategy).
        historico = receta.obtener_historico(self._historico, self._color_repository, juego_id, hasta_numero_sorteo)

        # 3. calcular (motor puro, sin infraestructura)
        resultado_motor = receta.calcular(historico, parametros_metrica)

        # 4. serializar (frontera entre el motor y la persistencia
        # genérica -el repositorio nunca conoce FrecuenciaObservada)
        resultado_serializado = receta.serializar(resultado_motor)

        # 5. persistir
        entrada = EstadisticaCalculada(
            id=None, juego_id=juego_id, tipo_estadistica=tipo_estadistica,
            hasta_numero_sorteo=hasta_numero_sorteo, parametros=parametros_metrica,
            parametros_hash="",
            resultado=resultado_serializado, calculado_en=None, valido_hasta=None,
        )
        return self._estadisticas.guardar(entrada)
