"""
Tests de `application/interfaces/estadistica_repository.py`.

IMPORTANTE - transparencia sobre el alcance real de esta verificación:
este sandbox NO tiene un servidor PostgreSQL disponible (confirmado:
sin binario `postgres`, sin `psycopg` instalado) ni el proyecto tiene,
en ninguna etapa anterior, un patrón de tests de integración contra
una base de datos real -todos los repositorios SQLAlchemy existentes
(`SorteoRepositorySQLAlchemy`, etc.) carecen de tests de integración
directos; se validan indirectamente a través de los casos de uso con
repositorios FALSOS que implementan el mismo puerto (ver
`test_persistencia_incremental.py::_SorteoRepositoryTransaccional`).

Este archivo sigue exactamente ese mismo precedente, con dos partes
CLARAMENTE separadas:

  1. `calcular_parametros_hash` -función pura, sin ninguna
     infraestructura- se prueba de verdad, ejecutada realmente.
  2. El CONTRATO de `EstadisticaRepository` (unicidad, vigencia,
     invalidación) se prueba contra un FAKE en memoria
     (`_EstadisticaRepositoryEnMemoria`) que replica fielmente la
     semántica esperada, incluyendo la estrategia de dos índices
     únicos parciales para el caso NULL (ya verificada
     independientemente con sqlite3 antes de implementar la
     migración real). Esto verifica que el PUERTO está bien diseñado
     y que su semántica es implementable correctamente -NO verifica
     que `EstadisticaRepositorySQLAlchemy` funcione contra un
     PostgreSQL real, porque no hay ninguno disponible en este
     entorno para probarlo. Se señala esta limitación explícitamente
     en el informe final, sin ocultarla.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from app.application.interfaces.estadistica_repository import (
    EstadisticaCalculada,
    EstadisticaRepository,
    calcular_parametros_hash,
)


# =====================================================================
# 1. calcular_parametros_hash -función pura, tests reales
# =====================================================================

class TestCalcularParametrosHash:
    def test_mismos_parametros_mismo_hash(self):
        h1 = calcular_parametros_hash({"rango_min": 1, "rango_max": 43})
        h2 = calcular_parametros_hash({"rango_min": 1, "rango_max": 43})
        assert h1 == h2

    def test_orden_de_claves_no_afecta_el_hash(self):
        h1 = calcular_parametros_hash({"a": 1, "b": 2})
        h2 = calcular_parametros_hash({"b": 2, "a": 1})
        assert h1 == h2

    def test_contenido_diferente_da_hash_diferente(self):
        h1 = calcular_parametros_hash({"rango_max": 43})
        h2 = calcular_parametros_hash({"rango_max": 39})
        assert h1 != h2

    def test_estructuras_anidadas_con_orden_de_claves_distinto(self):
        h1 = calcular_parametros_hash({"rango": [1, 43], "colores": {"z": True, "a": None}})
        h2 = calcular_parametros_hash({"colores": {"a": None, "z": True}, "rango": [1, 43]})
        assert h1 == h2

    def test_listas_importan_el_orden(self):
        h1 = calcular_parametros_hash({"valores": [1, 2, 3]})
        h2 = calcular_parametros_hash({"valores": [3, 2, 1]})
        assert h1 != h2

    def test_booleanos_y_none(self):
        h1 = calcular_parametros_hash({"activo": True, "opcional": None})
        h2 = calcular_parametros_hash({"activo": False, "opcional": None})
        assert h1 != h2

    def test_diccionario_vacio(self):
        h = calcular_parametros_hash({})
        assert len(h) == 64
        assert h == calcular_parametros_hash({})

    def test_es_hexadecimal_de_64_caracteres_sha256(self):
        h = calcular_parametros_hash({"x": 1})
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_no_muta_el_diccionario_original(self):
        original = {"z": 1, "a": 2, "anidado": {"y": 1, "x": 2}}
        copia = {"z": 1, "a": 2, "anidado": {"y": 1, "x": 2}}
        calcular_parametros_hash(original)
        assert original == copia

    def test_verificado_independientemente_contra_hashlib_json_puro(self):
        import hashlib
        import json

        parametros = {"rango_min": 1, "rango_max": 43, "colores_vigentes": ["ROJO", "AZUL"]}
        manual = hashlib.sha256(
            json.dumps(parametros, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        assert calcular_parametros_hash(parametros) == manual

    def test_no_incluye_hasta_numero_sorteo_es_responsabilidad_del_llamador(self):
        con_corte_en_parametros = calcular_parametros_hash({"rango_max": 43, "hasta_numero_sorteo": 800})
        sin_esa_clave = calcular_parametros_hash({"rango_max": 43})
        assert con_corte_en_parametros != sin_esa_clave


# =====================================================================
# 2. Contrato de EstadisticaRepository -verificado contra un FAKE en
#    memoria, no contra PostgreSQL real (ver docstring del módulo).
# =====================================================================

class _EstadisticaRepositoryEnMemoria(EstadisticaRepository):
    def __init__(self):
        self._filas: list[EstadisticaCalculada] = []

    def guardar(self, entrada: EstadisticaCalculada) -> EstadisticaCalculada:
        """UPSERT por identidad -reemplaza (mismo id) si ya existe una
        fila con la misma (juego_id, tipo_estadistica,
        hasta_numero_sorteo, parametros_hash), IGNORANDO valido_hasta
        (una fila invalidada sigue siendo la misma identidad
        reutilizable). Inserta si no existe."""
        hash_calculado = calcular_parametros_hash(entrada.parametros)
        for i, fila in enumerate(self._filas):
            if (
                fila.juego_id == entrada.juego_id
                and fila.tipo_estadistica == entrada.tipo_estadistica
                and fila.hasta_numero_sorteo == entrada.hasta_numero_sorteo
                and fila.parametros_hash == hash_calculado
            ):
                reemplazada = EstadisticaCalculada(
                    id=fila.id, juego_id=entrada.juego_id, tipo_estadistica=entrada.tipo_estadistica,
                    hasta_numero_sorteo=entrada.hasta_numero_sorteo, parametros=entrada.parametros,
                    parametros_hash=hash_calculado, resultado=entrada.resultado,
                    calculado_en=datetime.now(timezone.utc), valido_hasta=entrada.valido_hasta,
                )
                self._filas[i] = reemplazada
                return reemplazada

        guardada = EstadisticaCalculada(
            id=uuid4(), juego_id=entrada.juego_id, tipo_estadistica=entrada.tipo_estadistica,
            hasta_numero_sorteo=entrada.hasta_numero_sorteo, parametros=entrada.parametros,
            parametros_hash=hash_calculado, resultado=entrada.resultado,
            calculado_en=datetime.now(timezone.utc), valido_hasta=entrada.valido_hasta,
        )
        self._filas.append(guardada)
        return guardada

    def buscar_vigente(
        self, juego_id: UUID, tipo_estadistica: str, hasta_numero_sorteo: int | None, parametros: dict,
    ) -> EstadisticaCalculada | None:
        hash_calculado = calcular_parametros_hash(parametros)
        ahora = datetime.now(timezone.utc)
        for fila in self._filas:
            if (
                fila.juego_id == juego_id
                and fila.tipo_estadistica == tipo_estadistica
                and fila.hasta_numero_sorteo == hasta_numero_sorteo
                and fila.parametros_hash == hash_calculado
                and (fila.valido_hasta is None or fila.valido_hasta > ahora)
            ):
                return fila
        return None

    def invalidar_por_juego(self, juego_id: UUID, desde_numero_sorteo: int | None = None) -> int:
        ahora = datetime.now(timezone.utc)
        afectadas = 0
        nuevas_filas = []
        for fila in self._filas:
            corte_afectado = fila.hasta_numero_sorteo is None or (
                desde_numero_sorteo is not None and fila.hasta_numero_sorteo >= desde_numero_sorteo
            )
            if (
                fila.juego_id == juego_id
                and corte_afectado
                and (fila.valido_hasta is None or fila.valido_hasta > ahora)
            ):
                fila = EstadisticaCalculada(
                    id=fila.id, juego_id=fila.juego_id, tipo_estadistica=fila.tipo_estadistica,
                    hasta_numero_sorteo=fila.hasta_numero_sorteo, parametros=fila.parametros,
                    parametros_hash=fila.parametros_hash, resultado=fila.resultado,
                    calculado_en=fila.calculado_en, valido_hasta=ahora,
                )
                afectadas += 1
            nuevas_filas.append(fila)
        self._filas = nuevas_filas
        return afectadas

    def listar_por_juego_y_tipo(self, juego_id: UUID, tipo_estadistica: str) -> list[EstadisticaCalculada]:
        filas = [f for f in self._filas if f.juego_id == juego_id and f.tipo_estadistica == tipo_estadistica]
        return sorted(filas, key=lambda f: f.calculado_en, reverse=True)


def _entrada(
    juego_id: UUID, tipo: str = "frecuencia_numeros", hasta_numero_sorteo: int | None = None,
    parametros: dict | None = None, resultado: dict | None = None, valido_hasta: datetime | None = None,
) -> EstadisticaCalculada:
    return EstadisticaCalculada(
        id=None, juego_id=juego_id, tipo_estadistica=tipo, hasta_numero_sorteo=hasta_numero_sorteo,
        parametros=parametros if parametros is not None else {"rango_min": 1, "rango_max": 43},
        parametros_hash="", resultado=resultado if resultado is not None else {"1": 10, "2": 8},
        calculado_en=None, valido_hasta=valido_hasta,
    )


class TestGuardarYRecuperar:
    def test_guarda_y_recupera_todos_los_campos(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        entrada = _entrada(juego_id, resultado={"1": 5, "2": 3})
        guardada = repo.guardar(entrada)

        recuperada = repo.buscar_vigente(juego_id, "frecuencia_numeros", None, entrada.parametros)
        assert recuperada is not None
        assert recuperada.juego_id == juego_id
        assert recuperada.tipo_estadistica == "frecuencia_numeros"
        assert recuperada.resultado == {"1": 5, "2": 3}
        assert recuperada.hasta_numero_sorteo is None
        assert recuperada.parametros_hash == guardada.parametros_hash
        assert len(recuperada.parametros_hash) == 64

    def test_conserva_hasta_numero_sorteo(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=800))
        recuperada = repo.buscar_vigente(juego_id, "frecuencia_numeros", 800, {"rango_min": 1, "rango_max": 43})
        assert recuperada is not None
        assert recuperada.hasta_numero_sorteo == 800

    def test_conserva_valido_hasta(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        futuro = datetime.now(timezone.utc) + timedelta(days=1)
        repo.guardar(_entrada(juego_id, valido_hasta=futuro))
        recuperada = repo.buscar_vigente(juego_id, "frecuencia_numeros", None, {"rango_min": 1, "rango_max": 43})
        assert recuperada.valido_hasta == futuro


class TestBuscarVigente:
    def test_encuentra_una_estadistica_vigente(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id))
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros", None, {"rango_min": 1, "rango_max": 43}) is not None

    def test_no_devuelve_una_estadistica_vencida(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        pasado = datetime.now(timezone.utc) - timedelta(days=1)
        repo.guardar(_entrada(juego_id, valido_hasta=pasado))
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros", None, {"rango_min": 1, "rango_max": 43}) is None

    def test_diferencia_parametros(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, parametros={"rango_min": 1, "rango_max": 43}))
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros", None, {"rango_min": 1, "rango_max": 39}) is None

    def test_diferencia_hasta_numero_sorteo(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=800))
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros", 900, {"rango_min": 1, "rango_max": 43}) is None
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros", 800, {"rango_min": 1, "rango_max": 43}) is not None

    def test_diferencia_tipo_estadistica(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="frecuencia_numeros"))
        assert repo.buscar_vigente(juego_id, "atrasos_numeros", None, {"rango_min": 1, "rango_max": 43}) is None

    def test_diferencia_juego_id(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_a, juego_b = uuid4(), uuid4()
        repo.guardar(_entrada(juego_a))
        assert repo.buscar_vigente(juego_b, "frecuencia_numeros", None, {"rango_min": 1, "rango_max": 43}) is None

    def test_funciona_con_hasta_numero_sorteo_none(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=None))
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros", None, {"rango_min": 1, "rango_max": 43}) is not None

    def test_no_devuelve_registros_de_otro_juego_con_todo_lo_demas_igual(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_a, juego_b = uuid4(), uuid4()
        repo.guardar(_entrada(juego_a, parametros={"x": 1}))
        repo.guardar(_entrada(juego_b, parametros={"x": 1}))
        resultado_a = repo.buscar_vigente(juego_a, "frecuencia_numeros", None, {"x": 1})
        resultado_b = repo.buscar_vigente(juego_b, "frecuencia_numeros", None, {"x": 1})
        assert resultado_a.juego_id == juego_a
        assert resultado_b.juego_id == juego_b

    def test_no_devuelve_registros_con_parametros_diferentes(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, parametros={"rango_max": 43}))
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros", None, {"rango_max": 39}) is None


class TestInvalidarPorJuego:
    def test_invalida_solo_el_juego_solicitado(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_a, juego_b = uuid4(), uuid4()
        repo.guardar(_entrada(juego_a))
        repo.guardar(_entrada(juego_b))
        repo.invalidar_por_juego(juego_a)
        assert repo.buscar_vigente(juego_a, "frecuencia_numeros", None, {"rango_min": 1, "rango_max": 43}) is None
        assert repo.buscar_vigente(juego_b, "frecuencia_numeros", None, {"rango_min": 1, "rango_max": 43}) is not None

    def test_invalida_solo_historico_completo_no_estadisticas_con_corte(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=None))
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=800, parametros={"otro": True}))
        repo.invalidar_por_juego(juego_id)
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros", None, {"rango_min": 1, "rango_max": 43}) is None
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros", 800, {"otro": True}) is not None

    def test_devuelve_la_cantidad_de_filas_afectadas(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="frecuencia_numeros"))
        repo.guardar(_entrada(juego_id, tipo="atrasos_numeros"))
        afectadas = repo.invalidar_por_juego(juego_id)
        assert afectadas == 2

    def test_no_vuelve_a_contar_filas_ya_invalidas(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id))
        primera = repo.invalidar_por_juego(juego_id)
        segunda = repo.invalidar_por_juego(juego_id)
        assert primera == 1
        assert segunda == 0


class TestUnicidad:
    def test_mismo_juego_tipo_parametros_corte_hace_upsert_no_duplica(self):
        """Corrección del bug de UniqueViolation: guardar() sobre la
        misma identidad ya NO lanza -reemplaza la fila existente
        (mismo id), y el total de filas para esa identidad permanece
        en una sola."""
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, parametros={"x": 1}, resultado={"v": "vieja"}))
        segunda = repo.guardar(_entrada(juego_id, parametros={"x": 1}, resultado={"v": "nueva"}))

        assert segunda.id == primera.id  # misma fila logica, no una nueva
        assert segunda.resultado == {"v": "nueva"}
        filas_de_esa_identidad = [
            f for f in repo._filas
            if f.juego_id == juego_id and f.tipo_estadistica == "frecuencia_numeros"
            and f.hasta_numero_sorteo is None and f.parametros_hash == calcular_parametros_hash({"x": 1})
        ]
        assert len(filas_de_esa_identidad) == 1

    def test_tipo_diferente_coexiste(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="frecuencia_numeros", parametros={"x": 1}))
        repo.guardar(_entrada(juego_id, tipo="atrasos_numeros", parametros={"x": 1}))

    def test_parametros_diferentes_coexisten(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, parametros={"x": 1}))
        repo.guardar(_entrada(juego_id, parametros={"x": 2}))

    def test_juego_diferente_coexiste(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_a, juego_b = uuid4(), uuid4()
        repo.guardar(_entrada(juego_a, parametros={"x": 1}))
        repo.guardar(_entrada(juego_b, parametros={"x": 1}))

    def test_corte_diferente_coexiste(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=100, parametros={"x": 1}))
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=200, parametros={"x": 1}))

    def test_dos_guardados_con_hasta_numero_sorteo_none_y_mismo_resto_hacen_upsert(self):
        """Mismo caso central que antes, pero con la semántica
        corregida: el segundo guardar() reemplaza, no falla."""
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, hasta_numero_sorteo=None, parametros={"x": 1}))
        segunda = repo.guardar(_entrada(juego_id, hasta_numero_sorteo=None, parametros={"x": 1}))
        assert segunda.id == primera.id


class TestListarPorJuegoYTipo:
    def test_devuelve_todas_las_estadisticas_del_juego_y_tipo(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="frecuencia_numeros", parametros={"x": 1}))
        repo.guardar(_entrada(juego_id, tipo="frecuencia_numeros", parametros={"x": 2}))
        repo.guardar(_entrada(juego_id, tipo="atrasos_numeros", parametros={"x": 1}))
        filas = repo.listar_por_juego_y_tipo(juego_id, "frecuencia_numeros")
        assert len(filas) == 2
        assert all(f.tipo_estadistica == "frecuencia_numeros" for f in filas)

    def test_orden_descendente_por_calculado_en(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, parametros={"x": 1}))
        repo.guardar(_entrada(juego_id, parametros={"x": 2}))
        filas = repo.listar_por_juego_y_tipo(juego_id, "frecuencia_numeros")
        assert filas[0].calculado_en >= filas[1].calculado_en

    def test_no_incluye_otro_juego(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_a, juego_b = uuid4(), uuid4()
        repo.guardar(_entrada(juego_a))
        repo.guardar(_entrada(juego_b))
        filas = repo.listar_por_juego_y_tipo(juego_a, "frecuencia_numeros")
        assert len(filas) == 1
        assert filas[0].juego_id == juego_a

    def test_lista_vacia_si_no_hay_nada(self):
        repo = _EstadisticaRepositoryEnMemoria()
        assert repo.listar_por_juego_y_tipo(uuid4(), "frecuencia_numeros") == []


class TestNoMutacion:
    def test_guardar_no_muta_el_dict_de_parametros_original(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        parametros = {"rango_min": 1, "rango_max": 43}
        copia = dict(parametros)
        repo.guardar(_entrada(juego_id, parametros=parametros))
        assert parametros == copia

    def test_buscar_vigente_no_muta_el_dict_de_parametros(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        parametros = {"rango_min": 1, "rango_max": 43}
        repo.guardar(_entrada(juego_id, parametros=dict(parametros)))
        copia = dict(parametros)
        repo.buscar_vigente(juego_id, "frecuencia_numeros", None, parametros)
        assert parametros == copia


class TestInvalidarPorJuegoSemanticaDeCorte:
    """Corrección del bug reportado: desde_numero_sorteo ahora sí se
    respeta -histórico completo y cortes >= N se invalidan, cortes
    < N se conservan (nunca llegaron al sorteo mutado)."""

    def test_hasta_numero_sorteo_null_se_invalida(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=None, parametros={"x": 1}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=100)
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros", None, {"x": 1}) is None

    def test_corte_igual_a_n_se_invalida(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=100, parametros={"x": 1}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=100)
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros", 100, {"x": 1}) is None

    def test_corte_mayor_a_n_se_invalida(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=200, parametros={"x": 1}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=100)
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros", 200, {"x": 1}) is None

    def test_corte_menor_a_n_permanece_vigente(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=50, parametros={"x": 1}))
        afectadas = repo.invalidar_por_juego(juego_id, desde_numero_sorteo=100)
        assert afectadas == 0
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros", 50, {"x": 1}) is not None

    def test_otro_juego_no_cambia(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_a, juego_b = uuid4(), uuid4()
        repo.guardar(_entrada(juego_a, hasta_numero_sorteo=None, parametros={"x": 1}))
        repo.guardar(_entrada(juego_b, hasta_numero_sorteo=None, parametros={"x": 1}))
        repo.invalidar_por_juego(juego_a, desde_numero_sorteo=100)
        assert repo.buscar_vigente(juego_a, "frecuencia_numeros", None, {"x": 1}) is None
        assert repo.buscar_vigente(juego_b, "frecuencia_numeros", None, {"x": 1}) is not None

    def test_sin_desde_numero_sorteo_conserva_semantica_documentada(self):
        """Sin desde_numero_sorteo, solo se invalida el histórico
        completo -mismo comportamiento documentado en el puerto."""
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=None, parametros={"x": 1}))
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=100, parametros={"y": 1}))
        afectadas = repo.invalidar_por_juego(juego_id)
        assert afectadas == 1  # solo el historico completo
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros", None, {"x": 1}) is None
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros", 100, {"y": 1}) is not None

    def test_invalida_todos_los_tipos_estadisticos_del_juego(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="frecuencia_numeros", hasta_numero_sorteo=None, parametros={"x": 1}))
        repo.guardar(_entrada(juego_id, tipo="frecuencia_superbalota", hasta_numero_sorteo=None, parametros={"x": 1}))
        repo.guardar(_entrada(juego_id, tipo="tabla_frecuencia_numeros", hasta_numero_sorteo=None, parametros={"x": 1}))
        afectadas = repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        assert afectadas == 3

    def test_buscar_vigente_no_devuelve_filas_invalidadas(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=200, parametros={"x": 1}))
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros", 200, {"x": 1}) is not None
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=100)
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros", 200, {"x": 1}) is None


class TestUpsertTrasInvalidacion:
    """Corrección del defecto real reportado en Windows: recalcular
    una identidad estadística invalidada debe REEMPLAZAR la fila
    existente, no intentar crear una segunda (lo que producía
    UniqueViolation contra los índices únicos parciales).

    Verificación previa e independiente (antes de escribir estos
    tests, sin usar pytest): confirmé con un script separado, contra
    el código real de `FakeEstadisticaRepository.guardar()`, que tras
    invalidar y volver a guardar la MISMA identidad: (a) el id no
    cambia, (b) el resultado es el nuevo, (c) calculado_en avanza,
    (d) queda vigente de nuevo, (e) el total de filas de esa
    identidad permanece en 1 -tanto sin corte como con corte."""

    def test_guardar_identidad_sin_corte_inexistente_inserta(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        guardada = repo.guardar(_entrada(juego_id, hasta_numero_sorteo=None, resultado={"v": 1}))
        assert guardada.id is not None
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros", None, {"rango_min": 1, "rango_max": 43}) is not None

    def test_recalcular_identidad_sin_corte_invalidada_no_duplica(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=None, resultado={"v": "vieja"}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=None, resultado={"v": "nueva"}))  # NO debe lanzar
        total = sum(
            1 for f in repo._filas
            if f.juego_id == juego_id and f.hasta_numero_sorteo is None and f.tipo_estadistica == "frecuencia_numeros"
        )
        assert total == 1

    def test_misma_fila_logica_queda_con_resultado_nuevo_sin_corte(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, hasta_numero_sorteo=None, resultado={"v": "vieja"}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        segunda = repo.guardar(_entrada(juego_id, hasta_numero_sorteo=None, resultado={"v": "nueva"}))
        assert segunda.id == primera.id
        assert segunda.resultado == {"v": "nueva"}

    def test_queda_vigente_despues_del_recalculo_sin_corte(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=None, resultado={"v": 1}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros", None, {"rango_min": 1, "rango_max": 43}) is None
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=None, resultado={"v": 2}))
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros", None, {"rango_min": 1, "rango_max": 43}) is not None

    def test_calculado_en_refleja_el_recalculo(self):
        import time

        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, hasta_numero_sorteo=None, resultado={"v": 1}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        time.sleep(0.01)
        segunda = repo.guardar(_entrada(juego_id, hasta_numero_sorteo=None, resultado={"v": 2}))
        assert segunda.calculado_en > primera.calculado_en

    def test_guardar_identidad_con_corte_inexistente_inserta(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        guardada = repo.guardar(_entrada(juego_id, hasta_numero_sorteo=100, resultado={"v": 1}))
        assert guardada.id is not None
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros", 100, {"rango_min": 1, "rango_max": 43}) is not None

    def test_recalcular_identidad_con_corte_invalidada_no_duplica(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=100, resultado={"v": "vieja"}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=100)
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=100, resultado={"v": "nueva"}))  # NO debe lanzar
        total = sum(1 for f in repo._filas if f.juego_id == juego_id and f.hasta_numero_sorteo == 100)
        assert total == 1

    def test_conserva_exactamente_el_mismo_corte(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=100, resultado={"v": "vieja"}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=100)
        segunda = repo.guardar(_entrada(juego_id, hasta_numero_sorteo=100, resultado={"v": "nueva"}))
        assert segunda.hasta_numero_sorteo == 100

    def test_no_reemplaza_identidad_con_otro_parametros_hash(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, hasta_numero_sorteo=None, parametros={"rango_max": 43}, resultado={"v": 1}))
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=None, parametros={"rango_max": 39}, resultado={"v": 2}))
        # la primera identidad (rango_max=43) sigue intacta, sin tocar
        recuperada = repo.buscar_vigente(juego_id, "frecuencia_numeros", None, {"rango_max": 43})
        assert recuperada is not None
        assert recuperada.id == primera.id
        assert recuperada.resultado == {"v": 1}

    def test_no_reemplaza_otro_tipo_estadistica(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, tipo="frecuencia_numeros", hasta_numero_sorteo=None, resultado={"v": 1}))
        repo.guardar(_entrada(juego_id, tipo="frecuencia_superbalota", hasta_numero_sorteo=None, resultado={"v": 2}))
        recuperada = repo.buscar_vigente(juego_id, "frecuencia_numeros", None, {"rango_min": 1, "rango_max": 43})
        assert recuperada.id == primera.id
        assert recuperada.resultado == {"v": 1}

    def test_no_reemplaza_estadisticas_de_otro_juego(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_a, juego_b = uuid4(), uuid4()
        primera = repo.guardar(_entrada(juego_a, hasta_numero_sorteo=None, resultado={"v": 1}))
        repo.guardar(_entrada(juego_b, hasta_numero_sorteo=None, resultado={"v": 2}))
        recuperada = repo.buscar_vigente(juego_a, "frecuencia_numeros", None, {"rango_min": 1, "rango_max": 43})
        assert recuperada.id == primera.id
        assert recuperada.resultado == {"v": 1}

    def test_total_de_filas_para_la_misma_identidad_permanece_en_uno(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        for i in range(5):
            repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
            repo.guardar(_entrada(juego_id, hasta_numero_sorteo=None, resultado={"v": i}))
        total = sum(1 for f in repo._filas if f.juego_id == juego_id and f.hasta_numero_sorteo is None)
        assert total == 1

    def test_buscar_vigente_devuelve_el_resultado_recien_recalculado(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=None, resultado={"v": "vieja"}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=None, resultado={"v": "nueva"}))
        recuperada = repo.buscar_vigente(juego_id, "frecuencia_numeros", None, {"rango_min": 1, "rango_max": 43})
        assert recuperada.resultado == {"v": "nueva"}


class TestUpsertConAtrasosNumerosEtapaW:
    """El upsert (ya corregido) es genérico por identidad -no
    requiere ningún cambio para cubrir la receta nueva. Demostrado
    explícitamente con tipo_estadistica="atrasos_numeros"."""

    def test_recalcular_atrasos_numeros_invalidado_no_duplica(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, tipo="atrasos_numeros", hasta_numero_sorteo=None, resultado={"filas": [{"valor": "1", "atraso": 5}]}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        segunda = repo.guardar(_entrada(juego_id, tipo="atrasos_numeros", hasta_numero_sorteo=None, resultado={"filas": [{"valor": "1", "atraso": 0}]}))
        assert segunda.id == primera.id
        total = sum(1 for f in repo._filas if f.juego_id == juego_id and f.tipo_estadistica == "atrasos_numeros")
        assert total == 1

    def test_buscar_vigente_atrasos_numeros_devuelve_el_recalculo(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="atrasos_numeros", hasta_numero_sorteo=None, resultado={"v": "vieja"}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        repo.guardar(_entrada(juego_id, tipo="atrasos_numeros", hasta_numero_sorteo=None, resultado={"v": "nueva"}))
        recuperada = repo.buscar_vigente(juego_id, "atrasos_numeros", None, {"rango_min": 1, "rango_max": 43})
        assert recuperada.resultado == {"v": "nueva"}


class TestUpsertConDistribucionParesImparesEtapaY:
    """El upsert (ya corregido) es genérico por identidad -no
    requiere ningún cambio para cubrir la receta nueva."""

    def test_recalcular_distribucion_pares_impares_invalidado_no_duplica(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, tipo="distribucion_pares_impares", hasta_numero_sorteo=None, resultado={"filas": [{"valor": "2", "apariciones": 5}]}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        segunda = repo.guardar(_entrada(juego_id, tipo="distribucion_pares_impares", hasta_numero_sorteo=None, resultado={"filas": [{"valor": "2", "apariciones": 3}]}))
        assert segunda.id == primera.id
        total = sum(1 for f in repo._filas if f.juego_id == juego_id and f.tipo_estadistica == "distribucion_pares_impares")
        assert total == 1

    def test_buscar_vigente_distribucion_pares_impares_devuelve_el_recalculo(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="distribucion_pares_impares", hasta_numero_sorteo=None, resultado={"v": "vieja"}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        repo.guardar(_entrada(juego_id, tipo="distribucion_pares_impares", hasta_numero_sorteo=None, resultado={"v": "nueva"}))
        recuperada = repo.buscar_vigente(juego_id, "distribucion_pares_impares", None, {"rango_min": 1, "rango_max": 43})
        assert recuperada.resultado == {"v": "nueva"}


class TestUpsertConDistribucionAltosBajosEtapaZ:
    """El upsert (ya corregido en etapas anteriores) es genérico por
    identidad -no requiere ningún cambio para cubrir la receta nueva.
    Demostrado explícitamente con tipo_estadistica="distribucion_altos_bajos",
    incluidos aislamiento por corte y rollback (verificado en
    test_persistencia_incremental.py, sin cambios necesarios ahí).

    IMPORTANTE (corrección post Etapa Z): estos tests usan los TRES
    parámetros completos -{"rango_min", "rango_max", "cantidad_numeros"}-
    exactamente como los construye la receta real de producción
    (`app/api/web/routers/estadisticas.py::distribucion_altos_bajos`,
    `parametros_metrica={"rango_min": rango_min, "rango_max": rango_max,
    "cantidad_numeros": cantidad_numeros}`). Una corrección anterior
    de estos mismos tests había usado parámetros incompletos (solo
    rango_min/rango_max, sin cantidad_numeros) y ajustado la búsqueda
    para que coincidiera con esa entrada incompleta -eso hacía pasar
    el test sin representar el contrato real. Aquí se corrige en la
    dirección correcta: los tests representan el contrato real, no al
    revés."""

    # Los tres parámetros exactos que la receta de producción
    # construye para Baloto/Baloto Revancha (1-43, K=5).
    _PARAMS_BALOTO = {"rango_min": 1, "rango_max": 43, "cantidad_numeros": 5}
    # Los mismos tres para MiLoto (1-39, K=5) -mismo K, rango distinto.
    _PARAMS_MILOTO = {"rango_min": 1, "rango_max": 39, "cantidad_numeros": 5}

    def test_receta_real_genera_exactamente_las_tres_claves(self):
        """Verificado contra el código real del router, no supuesto:
        la receta de producción arma parametros_metrica con
        exactamente estas tres claves, ni una más ni una menos."""
        codigo_fuente = Path("app/api/web/routers/estadisticas.py").read_text(encoding="utf-8")
        indice = codigo_fuente.index('tipo_estadistica="distribucion_altos_bajos"')
        bloque = codigo_fuente[indice:indice + 300]
        assert '"rango_min": rango_min, "rango_max": rango_max, "cantidad_numeros": cantidad_numeros' in bloque

    def test_recalcular_altos_bajos_invalidado_no_duplica(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(
            juego_id, tipo="distribucion_altos_bajos", hasta_numero_sorteo=None,
            parametros=self._PARAMS_BALOTO, resultado={"filas": [{"valor": "3", "apariciones": 5}]},
        ))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        segunda = repo.guardar(_entrada(
            juego_id, tipo="distribucion_altos_bajos", hasta_numero_sorteo=None,
            parametros=self._PARAMS_BALOTO, resultado={"filas": [{"valor": "3", "apariciones": 3}]},
        ))
        assert segunda.id == primera.id
        total = sum(1 for f in repo._filas if f.juego_id == juego_id and f.tipo_estadistica == "distribucion_altos_bajos")
        assert total == 1

    def test_guardar_y_buscar_con_los_tres_parametros_recupera_la_misma_fila(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(
            juego_id, tipo="distribucion_altos_bajos", hasta_numero_sorteo=None,
            parametros=self._PARAMS_BALOTO, resultado={"v": "correcta"},
        ))
        recuperada = repo.buscar_vigente(juego_id, "distribucion_altos_bajos", None, self._PARAMS_BALOTO)
        assert recuperada is not None
        assert recuperada.resultado == {"v": "correcta"}

    def test_buscar_vigente_altos_bajos_devuelve_el_recalculo(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(
            juego_id, tipo="distribucion_altos_bajos", hasta_numero_sorteo=None,
            parametros=self._PARAMS_BALOTO, resultado={"v": "vieja"},
        ))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        repo.guardar(_entrada(
            juego_id, tipo="distribucion_altos_bajos", hasta_numero_sorteo=None,
            parametros=self._PARAMS_BALOTO, resultado={"v": "nueva"},
        ))
        recuperada = repo.buscar_vigente(juego_id, "distribucion_altos_bajos", None, self._PARAMS_BALOTO)
        assert recuperada.resultado == {"v": "nueva"}

    def test_cambiar_solo_cantidad_numeros_produce_hash_distinto(self):
        """cantidad_numeros=5 vs cantidad_numeros=6 (mismo rango) ->
        identidades de caché distintas -una búsqueda con 5 nunca debe
        devolver la fila guardada con 6."""
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        params_k5 = {"rango_min": 1, "rango_max": 43, "cantidad_numeros": 5}
        params_k6 = {"rango_min": 1, "rango_max": 43, "cantidad_numeros": 6}
        repo.guardar(_entrada(
            juego_id, tipo="distribucion_altos_bajos", hasta_numero_sorteo=None,
            parametros=params_k5, resultado={"v": "k5"},
        ))
        repo.guardar(_entrada(
            juego_id, tipo="distribucion_altos_bajos", hasta_numero_sorteo=None,
            parametros=params_k6, resultado={"v": "k6"},
        ))
        recuperada_k5 = repo.buscar_vigente(juego_id, "distribucion_altos_bajos", None, params_k5)
        recuperada_k6 = repo.buscar_vigente(juego_id, "distribucion_altos_bajos", None, params_k6)
        assert recuperada_k5.resultado == {"v": "k5"}
        assert recuperada_k6.resultado == {"v": "k6"}
        # Confirmar explícitamente que son DOS filas distintas, no una sola sobrescrita
        total = sum(1 for f in repo._filas if f.juego_id == juego_id and f.tipo_estadistica == "distribucion_altos_bajos")
        assert total == 2

    def test_busqueda_con_cantidad_5_no_devuelve_fila_guardada_con_cantidad_6(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        params_k6 = {"rango_min": 1, "rango_max": 43, "cantidad_numeros": 6}
        repo.guardar(_entrada(
            juego_id, tipo="distribucion_altos_bajos", hasta_numero_sorteo=None,
            parametros=params_k6, resultado={"v": "k6"},
        ))
        # Buscando con K=5 (identidad distinta) -no debe encontrar la fila de K=6
        recuperada = repo.buscar_vigente(juego_id, "distribucion_altos_bajos", None, self._PARAMS_BALOTO)
        assert recuperada is None

    def test_identidad_no_omite_cantidad_numeros_en_estos_tests(self):
        """Confirma explícitamente, por inspección de la constante de
        clase usada en TODOS los tests de esta clase, que
        cantidad_numeros nunca falta -a diferencia de una corrección
        anterior de estos mismos tests."""
        assert "cantidad_numeros" in self._PARAMS_BALOTO
        assert "cantidad_numeros" in self._PARAMS_MILOTO
        assert set(self._PARAMS_BALOTO.keys()) == {"rango_min", "rango_max", "cantidad_numeros"}

    def test_hasta_numero_sorteo_sigue_fuera_de_parametros_metrica(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        entrada = _entrada(
            juego_id, tipo="distribucion_altos_bajos", hasta_numero_sorteo=2694,
            parametros=self._PARAMS_BALOTO, resultado={"v": "con_corte"},
        )
        guardada = repo.guardar(entrada)
        assert "hasta_numero_sorteo" not in guardada.parametros
        assert guardada.hasta_numero_sorteo == 2694  # columna separada, no dentro de parametros

    def test_altos_bajos_historico_y_corte_son_identidades_distintas(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(
            juego_id, tipo="distribucion_altos_bajos", hasta_numero_sorteo=None,
            parametros=self._PARAMS_BALOTO, resultado={"v": "completo"},
        ))
        repo.guardar(_entrada(
            juego_id, tipo="distribucion_altos_bajos", hasta_numero_sorteo=2694,
            parametros=self._PARAMS_BALOTO, resultado={"v": "con_corte"},
        ))
        completo = repo.buscar_vigente(juego_id, "distribucion_altos_bajos", None, self._PARAMS_BALOTO)
        con_corte = repo.buscar_vigente(juego_id, "distribucion_altos_bajos", 2694, self._PARAMS_BALOTO)
        assert completo.resultado == {"v": "completo"}
        assert con_corte.resultado == {"v": "con_corte"}

    def test_altos_bajos_aislado_de_pares_impares_pese_a_compartir_juego(self):
        """Confirma que ambas recetas conviven en la misma tabla sin
        interferirse -distintos tipo_estadistica, misma identidad de
        juego. pares_impares usa SOLO cantidad_numeros (su contrato
        real, sin rango); altos_bajos usa los tres parámetros
        completos -contratos genuinamente distintos entre sí."""
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        params_pares = {"cantidad_numeros": 5}
        repo.guardar(_entrada(
            juego_id, tipo="distribucion_pares_impares", hasta_numero_sorteo=None,
            parametros=params_pares, resultado={"v": "pares"},
        ))
        repo.guardar(_entrada(
            juego_id, tipo="distribucion_altos_bajos", hasta_numero_sorteo=None,
            parametros=self._PARAMS_BALOTO, resultado={"v": "altos_bajos"},
        ))
        pares = repo.buscar_vigente(juego_id, "distribucion_pares_impares", None, params_pares)
        altos_bajos = repo.buscar_vigente(juego_id, "distribucion_altos_bajos", None, self._PARAMS_BALOTO)
        assert pares.resultado == {"v": "pares"}
        assert altos_bajos.resultado == {"v": "altos_bajos"}


class TestUpsertConDistribucionParesConsecutivosEtapaAA:
    """Mismo patrón exacto ya usado para distribucion_altos_bajos en
    Etapa Z -parámetros completos, coherentes con la receta real de
    producción."""

    _PARAMS_BALOTO = {"rango_min": 1, "rango_max": 43, "cantidad_numeros": 5}

    def test_identidad_por_juego(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_a, juego_b = uuid4(), uuid4()
        repo.guardar(_entrada(juego_a, tipo="distribucion_pares_consecutivos", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "juego_a"}))
        repo.guardar(_entrada(juego_b, tipo="distribucion_pares_consecutivos", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "juego_b"}))
        a = repo.buscar_vigente(juego_a, "distribucion_pares_consecutivos", None, self._PARAMS_BALOTO)
        b = repo.buscar_vigente(juego_b, "distribucion_pares_consecutivos", None, self._PARAMS_BALOTO)
        assert a.resultado == {"v": "juego_a"}
        assert b.resultado == {"v": "juego_b"}

    def test_identidad_por_tipo(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="distribucion_altos_bajos", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "altos_bajos"}))
        repo.guardar(_entrada(juego_id, tipo="distribucion_pares_consecutivos", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "pares_consecutivos"}))
        ab = repo.buscar_vigente(juego_id, "distribucion_altos_bajos", None, self._PARAMS_BALOTO)
        pc = repo.buscar_vigente(juego_id, "distribucion_pares_consecutivos", None, self._PARAMS_BALOTO)
        assert ab.resultado == {"v": "altos_bajos"}
        assert pc.resultado == {"v": "pares_consecutivos"}

    def test_recalcular_invalidado_no_duplica_upsert(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, tipo="distribucion_pares_consecutivos", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "vieja"}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        segunda = repo.guardar(_entrada(juego_id, tipo="distribucion_pares_consecutivos", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "nueva"}))
        assert segunda.id == primera.id
        total = sum(1 for f in repo._filas if f.juego_id == juego_id and f.tipo_estadistica == "distribucion_pares_consecutivos")
        assert total == 1

    def test_convivencia_sin_interferencia_con_pares_impares_y_altos_bajos(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        params_pares_impares = {"cantidad_numeros": 5}
        repo.guardar(_entrada(juego_id, tipo="distribucion_pares_impares", hasta_numero_sorteo=None, parametros=params_pares_impares, resultado={"v": "pares"}))
        repo.guardar(_entrada(juego_id, tipo="distribucion_altos_bajos", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "altos_bajos"}))
        repo.guardar(_entrada(juego_id, tipo="distribucion_pares_consecutivos", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "consecutivos"}))
        pares = repo.buscar_vigente(juego_id, "distribucion_pares_impares", None, params_pares_impares)
        altos_bajos = repo.buscar_vigente(juego_id, "distribucion_altos_bajos", None, self._PARAMS_BALOTO)
        consecutivos = repo.buscar_vigente(juego_id, "distribucion_pares_consecutivos", None, self._PARAMS_BALOTO)
        assert pares.resultado == {"v": "pares"}
        assert altos_bajos.resultado == {"v": "altos_bajos"}
        assert consecutivos.resultado == {"v": "consecutivos"}


class TestUpsertConDistribucionRachaMaximaEtapaAB:
    """Mismo patrón exacto ya usado para las 3 recetas anteriores -
    parámetros completos, coherentes con la receta real de producción."""

    _PARAMS_BALOTO = {"rango_min": 1, "rango_max": 43, "cantidad_numeros": 5}

    def test_identidad_por_juego(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_a, juego_b = uuid4(), uuid4()
        repo.guardar(_entrada(juego_a, tipo="distribucion_racha_maxima", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "juego_a"}))
        repo.guardar(_entrada(juego_b, tipo="distribucion_racha_maxima", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "juego_b"}))
        a = repo.buscar_vigente(juego_a, "distribucion_racha_maxima", None, self._PARAMS_BALOTO)
        b = repo.buscar_vigente(juego_b, "distribucion_racha_maxima", None, self._PARAMS_BALOTO)
        assert a.resultado == {"v": "juego_a"}
        assert b.resultado == {"v": "juego_b"}

    def test_identidad_por_tipo(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="distribucion_pares_consecutivos", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "pares"}))
        repo.guardar(_entrada(juego_id, tipo="distribucion_racha_maxima", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "racha"}))
        pares = repo.buscar_vigente(juego_id, "distribucion_pares_consecutivos", None, self._PARAMS_BALOTO)
        racha = repo.buscar_vigente(juego_id, "distribucion_racha_maxima", None, self._PARAMS_BALOTO)
        assert pares.resultado == {"v": "pares"}
        assert racha.resultado == {"v": "racha"}

    def test_recalcular_invalidado_no_duplica_upsert(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, tipo="distribucion_racha_maxima", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "vieja"}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        segunda = repo.guardar(_entrada(juego_id, tipo="distribucion_racha_maxima", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "nueva"}))
        assert segunda.id == primera.id
        total = sum(1 for f in repo._filas if f.juego_id == juego_id and f.tipo_estadistica == "distribucion_racha_maxima")
        assert total == 1

    def test_convivencia_sin_interferencia_con_metricas_anteriores(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        params_pares_impares = {"cantidad_numeros": 5}
        repo.guardar(_entrada(juego_id, tipo="distribucion_pares_impares", hasta_numero_sorteo=None, parametros=params_pares_impares, resultado={"v": "pares_impares"}))
        repo.guardar(_entrada(juego_id, tipo="distribucion_altos_bajos", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "altos_bajos"}))
        repo.guardar(_entrada(juego_id, tipo="distribucion_pares_consecutivos", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "consecutivos"}))
        repo.guardar(_entrada(juego_id, tipo="distribucion_racha_maxima", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "racha_maxima"}))
        assert repo.buscar_vigente(juego_id, "distribucion_pares_impares", None, params_pares_impares).resultado == {"v": "pares_impares"}
        assert repo.buscar_vigente(juego_id, "distribucion_altos_bajos", None, self._PARAMS_BALOTO).resultado == {"v": "altos_bajos"}
        assert repo.buscar_vigente(juego_id, "distribucion_pares_consecutivos", None, self._PARAMS_BALOTO).resultado == {"v": "consecutivos"}
        assert repo.buscar_vigente(juego_id, "distribucion_racha_maxima", None, self._PARAMS_BALOTO).resultado == {"v": "racha_maxima"}


class TestUpsertConDistribucionRepeticionesEntreSorteosEtapaAC:
    """Mismo patrón exacto ya usado para las 4 recetas anteriores."""

    _PARAMS_BALOTO = {"rango_min": 1, "rango_max": 43, "cantidad_numeros": 5}

    def test_identidad_por_juego(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_a, juego_b = uuid4(), uuid4()
        repo.guardar(_entrada(juego_a, tipo="distribucion_repeticiones_entre_sorteos", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "juego_a"}))
        repo.guardar(_entrada(juego_b, tipo="distribucion_repeticiones_entre_sorteos", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "juego_b"}))
        a = repo.buscar_vigente(juego_a, "distribucion_repeticiones_entre_sorteos", None, self._PARAMS_BALOTO)
        b = repo.buscar_vigente(juego_b, "distribucion_repeticiones_entre_sorteos", None, self._PARAMS_BALOTO)
        assert a.resultado == {"v": "juego_a"}
        assert b.resultado == {"v": "juego_b"}

    def test_identidad_por_tipo(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="distribucion_racha_maxima", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "racha"}))
        repo.guardar(_entrada(juego_id, tipo="distribucion_repeticiones_entre_sorteos", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "repeticiones"}))
        racha = repo.buscar_vigente(juego_id, "distribucion_racha_maxima", None, self._PARAMS_BALOTO)
        rep = repo.buscar_vigente(juego_id, "distribucion_repeticiones_entre_sorteos", None, self._PARAMS_BALOTO)
        assert racha.resultado == {"v": "racha"}
        assert rep.resultado == {"v": "repeticiones"}

    def test_recalcular_invalidado_no_duplica_upsert(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, tipo="distribucion_repeticiones_entre_sorteos", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "vieja"}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        segunda = repo.guardar(_entrada(juego_id, tipo="distribucion_repeticiones_entre_sorteos", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "nueva"}))
        assert segunda.id == primera.id
        total = sum(1 for f in repo._filas if f.juego_id == juego_id and f.tipo_estadistica == "distribucion_repeticiones_entre_sorteos")
        assert total == 1

    def test_convivencia_sin_interferencia_con_las_metricas_anteriores(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        params_pares_impares = {"cantidad_numeros": 5}
        repo.guardar(_entrada(juego_id, tipo="distribucion_pares_impares", hasta_numero_sorteo=None, parametros=params_pares_impares, resultado={"v": "pares"}))
        repo.guardar(_entrada(juego_id, tipo="distribucion_altos_bajos", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "altos_bajos"}))
        repo.guardar(_entrada(juego_id, tipo="distribucion_pares_consecutivos", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "consecutivos"}))
        repo.guardar(_entrada(juego_id, tipo="distribucion_racha_maxima", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "racha"}))
        repo.guardar(_entrada(juego_id, tipo="distribucion_repeticiones_entre_sorteos", hasta_numero_sorteo=None, parametros=self._PARAMS_BALOTO, resultado={"v": "repeticiones"}))
        assert repo.buscar_vigente(juego_id, "distribucion_pares_impares", None, params_pares_impares).resultado == {"v": "pares"}
        assert repo.buscar_vigente(juego_id, "distribucion_altos_bajos", None, self._PARAMS_BALOTO).resultado == {"v": "altos_bajos"}
        assert repo.buscar_vigente(juego_id, "distribucion_pares_consecutivos", None, self._PARAMS_BALOTO).resultado == {"v": "consecutivos"}
        assert repo.buscar_vigente(juego_id, "distribucion_racha_maxima", None, self._PARAMS_BALOTO).resultado == {"v": "racha"}
        assert repo.buscar_vigente(juego_id, "distribucion_repeticiones_entre_sorteos", None, self._PARAMS_BALOTO).resultado == {"v": "repeticiones"}


class TestUpsertConFrecuenciaNumerosColorLotoEtapaAE1:
    """Mismo patrón exacto ya usado para las 5 recetas anteriores."""

    _PARAMS_COLORLOTO = {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}

    def test_identidad_por_juego(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_a, juego_b = uuid4(), uuid4()
        repo.guardar(_entrada(juego_a, tipo="frecuencia_numeros_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "juego_a"}))
        repo.guardar(_entrada(juego_b, tipo="frecuencia_numeros_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "juego_b"}))
        a = repo.buscar_vigente(juego_a, "frecuencia_numeros_colorloto", None, self._PARAMS_COLORLOTO)
        b = repo.buscar_vigente(juego_b, "frecuencia_numeros_colorloto", None, self._PARAMS_COLORLOTO)
        assert a.resultado == {"v": "juego_a"}
        assert b.resultado == {"v": "juego_b"}

    def test_identidad_por_tipo(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="frecuencia_numeros", hasta_numero_sorteo=None, parametros={"rango_min": 1, "rango_max": 43}, resultado={"v": "numeros"}))
        repo.guardar(_entrada(juego_id, tipo="frecuencia_numeros_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "colorloto"}))
        numeros = repo.buscar_vigente(juego_id, "frecuencia_numeros", None, {"rango_min": 1, "rango_max": 43})
        colorloto = repo.buscar_vigente(juego_id, "frecuencia_numeros_colorloto", None, self._PARAMS_COLORLOTO)
        assert numeros.resultado == {"v": "numeros"}
        assert colorloto.resultado == {"v": "colorloto"}

    def test_historico_completo_y_corte_son_cachés_distintas(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="frecuencia_numeros_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "completo"}))
        repo.guardar(_entrada(juego_id, tipo="frecuencia_numeros_colorloto", hasta_numero_sorteo=100, parametros=self._PARAMS_COLORLOTO, resultado={"v": "corte"}))
        completo = repo.buscar_vigente(juego_id, "frecuencia_numeros_colorloto", None, self._PARAMS_COLORLOTO)
        corte = repo.buscar_vigente(juego_id, "frecuencia_numeros_colorloto", 100, self._PARAMS_COLORLOTO)
        assert completo.resultado == {"v": "completo"}
        assert corte.resultado == {"v": "corte"}

    def test_cambio_solo_de_cantidad_numeros_no_produce_cache_hit(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="frecuencia_numeros_colorloto", hasta_numero_sorteo=None, parametros={"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}, resultado={"v": "k6"}))
        vigente_k5 = repo.buscar_vigente(juego_id, "frecuencia_numeros_colorloto", None, {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 5})
        assert vigente_k5 is None

    def test_recalcular_invalidado_no_duplica_upsert(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, tipo="frecuencia_numeros_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "vieja"}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        segunda = repo.guardar(_entrada(juego_id, tipo="frecuencia_numeros_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "nueva"}))
        assert segunda.id == primera.id
        total = sum(1 for f in repo._filas if f.juego_id == juego_id and f.tipo_estadistica == "frecuencia_numeros_colorloto")
        assert total == 1

    def test_convivencia_sin_interferencia_con_las_nueve_metricas_anteriores(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="distribucion_pares_impares", hasta_numero_sorteo=None, parametros={"cantidad_numeros": 5}, resultado={"v": "pares"}))
        repo.guardar(_entrada(juego_id, tipo="distribucion_racha_maxima", hasta_numero_sorteo=None, parametros={"rango_min": 1, "rango_max": 43, "cantidad_numeros": 5}, resultado={"v": "racha"}))
        repo.guardar(_entrada(juego_id, tipo="distribucion_repeticiones_entre_sorteos", hasta_numero_sorteo=None, parametros={"rango_min": 1, "rango_max": 43, "cantidad_numeros": 5}, resultado={"v": "repeticiones"}))
        repo.guardar(_entrada(juego_id, tipo="frecuencia_numeros_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "colorloto"}))
        assert repo.buscar_vigente(juego_id, "distribucion_pares_impares", None, {"cantidad_numeros": 5}).resultado == {"v": "pares"}
        assert repo.buscar_vigente(juego_id, "distribucion_racha_maxima", None, {"rango_min": 1, "rango_max": 43, "cantidad_numeros": 5}).resultado == {"v": "racha"}
        assert repo.buscar_vigente(juego_id, "distribucion_repeticiones_entre_sorteos", None, {"rango_min": 1, "rango_max": 43, "cantidad_numeros": 5}).resultado == {"v": "repeticiones"}
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros_colorloto", None, self._PARAMS_COLORLOTO).resultado == {"v": "colorloto"}


class TestUpsertConFrecuenciaColoresColorLotoEtapaAE2:
    """Mismo patrón exacto ya usado para las 6 recetas anteriores."""

    _PARAMS_COLORLOTO = {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}

    def test_identidad_por_juego(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_a, juego_b = uuid4(), uuid4()
        repo.guardar(_entrada(juego_a, tipo="frecuencia_colores_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "juego_a"}))
        repo.guardar(_entrada(juego_b, tipo="frecuencia_colores_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "juego_b"}))
        a = repo.buscar_vigente(juego_a, "frecuencia_colores_colorloto", None, self._PARAMS_COLORLOTO)
        b = repo.buscar_vigente(juego_b, "frecuencia_colores_colorloto", None, self._PARAMS_COLORLOTO)
        assert a.resultado == {"v": "juego_a"}
        assert b.resultado == {"v": "juego_b"}

    def test_identidad_por_tipo_distinta_de_frecuencia_numeros_colorloto(self):
        """Aislamiento crítico: mismos parametros_metrica exactos,
        distinto tipo_estadistica -deben ser cachés completamente
        separadas, nunca colisionar entre sí."""
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="frecuencia_numeros_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "numeros"}))
        repo.guardar(_entrada(juego_id, tipo="frecuencia_colores_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "colores"}))
        numeros = repo.buscar_vigente(juego_id, "frecuencia_numeros_colorloto", None, self._PARAMS_COLORLOTO)
        colores = repo.buscar_vigente(juego_id, "frecuencia_colores_colorloto", None, self._PARAMS_COLORLOTO)
        assert numeros.resultado == {"v": "numeros"}
        assert colores.resultado == {"v": "colores"}

    def test_historico_completo_y_corte_son_cachés_distintas(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="frecuencia_colores_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "completo"}))
        repo.guardar(_entrada(juego_id, tipo="frecuencia_colores_colorloto", hasta_numero_sorteo=100, parametros=self._PARAMS_COLORLOTO, resultado={"v": "corte"}))
        completo = repo.buscar_vigente(juego_id, "frecuencia_colores_colorloto", None, self._PARAMS_COLORLOTO)
        corte = repo.buscar_vigente(juego_id, "frecuencia_colores_colorloto", 100, self._PARAMS_COLORLOTO)
        assert completo.resultado == {"v": "completo"}
        assert corte.resultado == {"v": "corte"}

    def test_recalcular_invalidado_no_duplica_upsert(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, tipo="frecuencia_colores_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "vieja"}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        segunda = repo.guardar(_entrada(juego_id, tipo="frecuencia_colores_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "nueva"}))
        assert segunda.id == primera.id
        total = sum(1 for f in repo._filas if f.juego_id == juego_id and f.tipo_estadistica == "frecuencia_colores_colorloto")
        assert total == 1

    def test_convivencia_sin_interferencia_con_las_diez_metricas_anteriores(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="distribucion_racha_maxima", hasta_numero_sorteo=None, parametros={"rango_min": 1, "rango_max": 43, "cantidad_numeros": 5}, resultado={"v": "racha"}))
        repo.guardar(_entrada(juego_id, tipo="frecuencia_numeros_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "numeros"}))
        repo.guardar(_entrada(juego_id, tipo="frecuencia_colores_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "colores"}))
        assert repo.buscar_vigente(juego_id, "distribucion_racha_maxima", None, {"rango_min": 1, "rango_max": 43, "cantidad_numeros": 5}).resultado == {"v": "racha"}
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros_colorloto", None, self._PARAMS_COLORLOTO).resultado == {"v": "numeros"}
        assert repo.buscar_vigente(juego_id, "frecuencia_colores_colorloto", None, self._PARAMS_COLORLOTO).resultado == {"v": "colores"}


class TestUpsertConFrecuenciaParesColorLotoEtapaAE3:
    """Mismo patrón exacto ya usado para las 7 recetas anteriores."""

    _PARAMS_COLORLOTO = {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}

    def test_identidad_por_juego(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_a, juego_b = uuid4(), uuid4()
        repo.guardar(_entrada(juego_a, tipo="frecuencia_pares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "juego_a"}))
        repo.guardar(_entrada(juego_b, tipo="frecuencia_pares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "juego_b"}))
        a = repo.buscar_vigente(juego_a, "frecuencia_pares_colorloto", None, self._PARAMS_COLORLOTO)
        b = repo.buscar_vigente(juego_b, "frecuencia_pares_colorloto", None, self._PARAMS_COLORLOTO)
        assert a.resultado == {"v": "juego_a"}
        assert b.resultado == {"v": "juego_b"}

    def test_identidad_por_tipo_distinta_de_las_otras_dos_recetas_colorloto(self):
        """Aislamiento crítico: mismos parametros_metrica exactos en
        las TRES recetas de ColorLoto, distinto tipo_estadistica ->
        deben ser cachés completamente separadas."""
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="frecuencia_numeros_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "numeros"}))
        repo.guardar(_entrada(juego_id, tipo="frecuencia_colores_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "colores"}))
        repo.guardar(_entrada(juego_id, tipo="frecuencia_pares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "pares"}))
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros_colorloto", None, self._PARAMS_COLORLOTO).resultado == {"v": "numeros"}
        assert repo.buscar_vigente(juego_id, "frecuencia_colores_colorloto", None, self._PARAMS_COLORLOTO).resultado == {"v": "colores"}
        assert repo.buscar_vigente(juego_id, "frecuencia_pares_colorloto", None, self._PARAMS_COLORLOTO).resultado == {"v": "pares"}

    def test_historico_completo_y_corte_son_cachés_distintas(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="frecuencia_pares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "completo"}))
        repo.guardar(_entrada(juego_id, tipo="frecuencia_pares_colorloto", hasta_numero_sorteo=100, parametros=self._PARAMS_COLORLOTO, resultado={"v": "corte"}))
        completo = repo.buscar_vigente(juego_id, "frecuencia_pares_colorloto", None, self._PARAMS_COLORLOTO)
        corte = repo.buscar_vigente(juego_id, "frecuencia_pares_colorloto", 100, self._PARAMS_COLORLOTO)
        assert completo.resultado == {"v": "completo"}
        assert corte.resultado == {"v": "corte"}

    def test_recalcular_invalidado_no_duplica_upsert(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, tipo="frecuencia_pares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "vieja"}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        segunda = repo.guardar(_entrada(juego_id, tipo="frecuencia_pares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "nueva"}))
        assert segunda.id == primera.id
        total = sum(1 for f in repo._filas if f.juego_id == juego_id and f.tipo_estadistica == "frecuencia_pares_colorloto")
        assert total == 1

    def test_convivencia_sin_interferencia_con_las_once_metricas_anteriores(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="distribucion_racha_maxima", hasta_numero_sorteo=None, parametros={"rango_min": 1, "rango_max": 43, "cantidad_numeros": 5}, resultado={"v": "racha"}))
        repo.guardar(_entrada(juego_id, tipo="frecuencia_numeros_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "numeros"}))
        repo.guardar(_entrada(juego_id, tipo="frecuencia_colores_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "colores"}))
        repo.guardar(_entrada(juego_id, tipo="frecuencia_pares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "pares"}))
        assert repo.buscar_vigente(juego_id, "distribucion_racha_maxima", None, {"rango_min": 1, "rango_max": 43, "cantidad_numeros": 5}).resultado == {"v": "racha"}
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros_colorloto", None, self._PARAMS_COLORLOTO).resultado == {"v": "numeros"}
        assert repo.buscar_vigente(juego_id, "frecuencia_colores_colorloto", None, self._PARAMS_COLORLOTO).resultado == {"v": "colores"}
        assert repo.buscar_vigente(juego_id, "frecuencia_pares_colorloto", None, self._PARAMS_COLORLOTO).resultado == {"v": "pares"}


class TestUpsertConAtrasosNumerosColorLotoEtapaAE4:
    """Mismo patrón exacto ya usado para las 8 recetas anteriores."""

    _PARAMS_COLORLOTO = {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}

    def test_identidad_por_juego(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_a, juego_b = uuid4(), uuid4()
        repo.guardar(_entrada(juego_a, tipo="atrasos_numeros_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "juego_a"}))
        repo.guardar(_entrada(juego_b, tipo="atrasos_numeros_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "juego_b"}))
        a = repo.buscar_vigente(juego_a, "atrasos_numeros_colorloto", None, self._PARAMS_COLORLOTO)
        b = repo.buscar_vigente(juego_b, "atrasos_numeros_colorloto", None, self._PARAMS_COLORLOTO)
        assert a.resultado == {"v": "juego_a"}
        assert b.resultado == {"v": "juego_b"}

    def test_identidad_por_tipo_distinta_de_las_otras_tres_recetas_colorloto(self):
        """Aislamiento crítico: mismos parametros_metrica exactos en
        las CUATRO recetas de ColorLoto, distinto tipo_estadistica ->
        deben ser cachés completamente separadas."""
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="frecuencia_numeros_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "numeros"}))
        repo.guardar(_entrada(juego_id, tipo="frecuencia_colores_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "colores"}))
        repo.guardar(_entrada(juego_id, tipo="frecuencia_pares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "pares"}))
        repo.guardar(_entrada(juego_id, tipo="atrasos_numeros_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "atrasos"}))
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros_colorloto", None, self._PARAMS_COLORLOTO).resultado == {"v": "numeros"}
        assert repo.buscar_vigente(juego_id, "frecuencia_colores_colorloto", None, self._PARAMS_COLORLOTO).resultado == {"v": "colores"}
        assert repo.buscar_vigente(juego_id, "frecuencia_pares_colorloto", None, self._PARAMS_COLORLOTO).resultado == {"v": "pares"}
        assert repo.buscar_vigente(juego_id, "atrasos_numeros_colorloto", None, self._PARAMS_COLORLOTO).resultado == {"v": "atrasos"}

    def test_historico_completo_y_corte_son_cachés_distintas(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="atrasos_numeros_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "completo"}))
        repo.guardar(_entrada(juego_id, tipo="atrasos_numeros_colorloto", hasta_numero_sorteo=100, parametros=self._PARAMS_COLORLOTO, resultado={"v": "corte"}))
        completo = repo.buscar_vigente(juego_id, "atrasos_numeros_colorloto", None, self._PARAMS_COLORLOTO)
        corte = repo.buscar_vigente(juego_id, "atrasos_numeros_colorloto", 100, self._PARAMS_COLORLOTO)
        assert completo.resultado == {"v": "completo"}
        assert corte.resultado == {"v": "corte"}

    def test_recalcular_invalidado_no_duplica_upsert(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, tipo="atrasos_numeros_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "vieja"}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=1)
        segunda = repo.guardar(_entrada(juego_id, tipo="atrasos_numeros_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "nueva"}))
        assert segunda.id == primera.id
        total = sum(1 for f in repo._filas if f.juego_id == juego_id and f.tipo_estadistica == "atrasos_numeros_colorloto")
        assert total == 1

    def test_convivencia_sin_interferencia_con_las_doce_metricas_anteriores(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="atrasos_numeros", hasta_numero_sorteo=None, parametros={"rango_min": 1, "rango_max": 43}, resultado={"v": "atrasos_numericos"}))
        repo.guardar(_entrada(juego_id, tipo="frecuencia_pares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "pares"}))
        repo.guardar(_entrada(juego_id, tipo="atrasos_numeros_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_COLORLOTO, resultado={"v": "atrasos_colorloto"}))
        assert repo.buscar_vigente(juego_id, "atrasos_numeros", None, {"rango_min": 1, "rango_max": 43}).resultado == {"v": "atrasos_numericos"}
        assert repo.buscar_vigente(juego_id, "frecuencia_pares_colorloto", None, self._PARAMS_COLORLOTO).resultado == {"v": "pares"}
        assert repo.buscar_vigente(juego_id, "atrasos_numeros_colorloto", None, self._PARAMS_COLORLOTO).resultado == {"v": "atrasos_colorloto"}


class TestInvalidarPorJuegoDesdeNumeroSorteoCeroUsadoPorPaleta:
    """`GestionarPaletaColores` usa exactamente
    invalidar_por_juego(juego_id, desde_numero_sorteo=0) tras cada
    mutación exitosa -este bloque confirma que `0` cubre TODO corte
    real (histórico completo + cualquier corte positivo), sin dejar
    accidentalmente vigente ninguno. Complementa (sin duplicar) la
    cobertura ya existente de TestInvalidarPorJuegoSemanticaDeCorte,
    que usa desde_numero_sorteo=100 como caso de sorteo."""

    def test_hasta_numero_sorteo_null_se_invalida_con_cero(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=None, parametros={"x": 1}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=0)
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros", None, {"x": 1}) is None

    def test_corte_uno_se_invalida_con_cero(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=1, parametros={"x": 1}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=0)
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros", 1, {"x": 1}) is None

    def test_corte_cien_se_invalida_con_cero(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=100, parametros={"x": 1}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=0)
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros", 100, {"x": 1}) is None

    def test_cualquier_corte_positivo_se_invalida_con_cero(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=99999, parametros={"x": 1}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=0)
        assert repo.buscar_vigente(juego_id, "frecuencia_numeros", 99999, {"x": 1}) is None

    def test_todas_las_metricas_del_mismo_juego_se_invalidan_no_solo_una(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="frecuencia_numeros_colorloto", hasta_numero_sorteo=None, parametros={"x": 1}))
        repo.guardar(_entrada(juego_id, tipo="frecuencia_colores_colorloto", hasta_numero_sorteo=None, parametros={"x": 1}))
        repo.guardar(_entrada(juego_id, tipo="frecuencia_pares_colorloto", hasta_numero_sorteo=None, parametros={"x": 1}))
        repo.guardar(_entrada(juego_id, tipo="atrasos_numeros_colorloto", hasta_numero_sorteo=None, parametros={"x": 1}))
        afectadas = repo.invalidar_por_juego(juego_id, desde_numero_sorteo=0)
        assert afectadas == 4
        for tipo in ("frecuencia_numeros_colorloto", "frecuencia_colores_colorloto", "frecuencia_pares_colorloto", "atrasos_numeros_colorloto"):
            assert repo.buscar_vigente(juego_id, tipo, None, {"x": 1}) is None

    def test_otro_juego_permanece_vigente_con_cero(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_a, juego_b = uuid4(), uuid4()
        repo.guardar(_entrada(juego_b, hasta_numero_sorteo=None, parametros={"x": 1}))
        repo.invalidar_por_juego(juego_a, desde_numero_sorteo=0)
        assert repo.buscar_vigente(juego_b, "frecuencia_numeros", None, {"x": 1}) is not None

    def test_cero_no_deja_vigente_el_historico_completo_por_error(self):
        """Confirma explícitamente que `0` no es interpretado como
        'falsy' de forma que se comporte igual que `None` (que solo
        invalida el histórico completo) -0 SÍ debe activar la rama
        `desde_numero_sorteo is not None`."""
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=None, parametros={"x": 1}))
        repo.guardar(_entrada(juego_id, hasta_numero_sorteo=1, parametros={"y": 2}))
        afectadas = repo.invalidar_por_juego(juego_id, desde_numero_sorteo=0)
        assert afectadas == 2


class TestUpsertConAtrasosColoresColorLotoEtapaAE5:
    """Mismo patrón exacto ya usado para las 9 recetas anteriores.
    Identidad con las CUATRO claves, incluido el marcador de política
    (mismo patrón ya validado por AE-2/AE-3 en AE-4P)."""

    _PARAMS_CON_MARCADOR = {
        "rango_min": 1, "rango_max": 7, "cantidad_numeros": 6,
        "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1",
    }
    _PARAMS_SIN_MARCADOR = {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}

    def test_parametros_exactos_con_las_cuatro_claves_y_marcador(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        entrada = repo.guardar(_entrada(juego_id, tipo="atrasos_colores_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_CON_MARCADOR, resultado={"v": "nueva"}))
        assert entrada.parametros == self._PARAMS_CON_MARCADOR
        assert set(entrada.parametros.keys()) == {"rango_min", "rango_max", "cantidad_numeros", "politica_universo_colores"}

    def test_identidad_por_juego(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_a, juego_b = uuid4(), uuid4()
        repo.guardar(_entrada(juego_a, tipo="atrasos_colores_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_CON_MARCADOR, resultado={"v": "juego_a"}))
        repo.guardar(_entrada(juego_b, tipo="atrasos_colores_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_CON_MARCADOR, resultado={"v": "juego_b"}))
        a = repo.buscar_vigente(juego_a, "atrasos_colores_colorloto", None, self._PARAMS_CON_MARCADOR)
        b = repo.buscar_vigente(juego_b, "atrasos_colores_colorloto", None, self._PARAMS_CON_MARCADOR)
        assert a.resultado == {"v": "juego_a"}
        assert b.resultado == {"v": "juego_b"}

    def test_identidad_por_tipo_distinta_de_las_otras_recetas_colorloto(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="atrasos_numeros_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_SIN_MARCADOR, resultado={"v": "numeros"}))
        repo.guardar(_entrada(juego_id, tipo="frecuencia_colores_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_CON_MARCADOR, resultado={"v": "frec_colores"}))
        repo.guardar(_entrada(juego_id, tipo="atrasos_colores_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_CON_MARCADOR, resultado={"v": "atrasos_colores"}))
        assert repo.buscar_vigente(juego_id, "atrasos_numeros_colorloto", None, self._PARAMS_SIN_MARCADOR).resultado == {"v": "numeros"}
        assert repo.buscar_vigente(juego_id, "frecuencia_colores_colorloto", None, self._PARAMS_CON_MARCADOR).resultado == {"v": "frec_colores"}
        assert repo.buscar_vigente(juego_id, "atrasos_colores_colorloto", None, self._PARAMS_CON_MARCADOR).resultado == {"v": "atrasos_colores"}

    def test_caché_antigua_sin_marcador_no_es_seleccionada(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="atrasos_colores_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_SIN_MARCADOR, resultado={"v": "sin_marcador_hipotetico"}))
        vigente = repo.buscar_vigente(juego_id, "atrasos_colores_colorloto", None, self._PARAMS_CON_MARCADOR)
        assert vigente is None

    def test_hit_de_cache_nueva_con_marcador(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, tipo="atrasos_colores_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_CON_MARCADOR, resultado={"v": "cacheado"}))
        vigente = repo.buscar_vigente(juego_id, "atrasos_colores_colorloto", None, self._PARAMS_CON_MARCADOR)
        assert vigente is not None
        assert vigente.id == primera.id

    def test_historico_completo_y_corte_son_cachés_distintas(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="atrasos_colores_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_CON_MARCADOR, resultado={"v": "completo"}))
        repo.guardar(_entrada(juego_id, tipo="atrasos_colores_colorloto", hasta_numero_sorteo=100, parametros=self._PARAMS_CON_MARCADOR, resultado={"v": "corte"}))
        completo = repo.buscar_vigente(juego_id, "atrasos_colores_colorloto", None, self._PARAMS_CON_MARCADOR)
        corte = repo.buscar_vigente(juego_id, "atrasos_colores_colorloto", 100, self._PARAMS_CON_MARCADOR)
        assert completo.resultado == {"v": "completo"}
        assert corte.resultado == {"v": "corte"}

    def test_recalcular_invalidado_no_duplica_upsert(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, tipo="atrasos_colores_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_CON_MARCADOR, resultado={"v": "vieja"}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=0)
        segunda = repo.guardar(_entrada(juego_id, tipo="atrasos_colores_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_CON_MARCADOR, resultado={"v": "nueva"}))
        assert segunda.id == primera.id
        total = sum(1 for f in repo._filas if f.juego_id == juego_id and f.tipo_estadistica == "atrasos_colores_colorloto")
        assert total == 1

    def test_ninguna_estadistica_de_otro_juego_es_invalidada(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_a, juego_b = uuid4(), uuid4()
        repo.guardar(_entrada(juego_b, tipo="atrasos_colores_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_CON_MARCADOR, resultado={"v": "juego_b"}))
        repo.invalidar_por_juego(juego_a, desde_numero_sorteo=0)
        vigente_b = repo.buscar_vigente(juego_b, "atrasos_colores_colorloto", None, self._PARAMS_CON_MARCADOR)
        assert vigente_b is not None
        assert vigente_b.resultado == {"v": "juego_b"}

    def test_convivencia_sin_interferencia_con_las_trece_metricas_anteriores(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="atrasos_numeros_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_SIN_MARCADOR, resultado={"v": "atrasos_numeros"}))
        repo.guardar(_entrada(juego_id, tipo="frecuencia_pares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_CON_MARCADOR, resultado={"v": "pares"}))
        repo.guardar(_entrada(juego_id, tipo="atrasos_colores_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_CON_MARCADOR, resultado={"v": "atrasos_colores"}))
        assert repo.buscar_vigente(juego_id, "atrasos_numeros_colorloto", None, self._PARAMS_SIN_MARCADOR).resultado == {"v": "atrasos_numeros"}
        assert repo.buscar_vigente(juego_id, "frecuencia_pares_colorloto", None, self._PARAMS_CON_MARCADOR).resultado == {"v": "pares"}
        assert repo.buscar_vigente(juego_id, "atrasos_colores_colorloto", None, self._PARAMS_CON_MARCADOR).resultado == {"v": "atrasos_colores"}


class TestUpsertConAtrasosParesColorlotoEtapaAE6:
    """Mismo patrón exacto ya usado para las 14 recetas anteriores.
    Identidad con las CUATRO claves, incluido el marcador de
    política (mismo patrón ya validado por AE-2/AE-3/AE-5)."""

    _PARAMS_CON_MARCADOR = {
        "rango_min": 1, "rango_max": 7, "cantidad_numeros": 6,
        "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1",
    }

    def test_parametros_exactos_con_las_cuatro_claves_y_marcador(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        entrada = repo.guardar(_entrada(juego_id, tipo="atrasos_pares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_CON_MARCADOR, resultado={"v": "nueva"}))
        assert entrada.parametros == self._PARAMS_CON_MARCADOR
        assert set(entrada.parametros.keys()) == {"rango_min", "rango_max", "cantidad_numeros", "politica_universo_colores"}

    def test_ausencia_de_corte_y_lista_de_colores_en_parametros(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        entrada = repo.guardar(_entrada(juego_id, tipo="atrasos_pares_colorloto", hasta_numero_sorteo=100, parametros=self._PARAMS_CON_MARCADOR, resultado={"v": "x"}))
        assert "hasta_numero_sorteo" not in entrada.parametros
        assert not any("color" in k and k != "politica_universo_colores" for k in entrada.parametros.keys())

    def test_identidad_por_juego(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_a, juego_b = uuid4(), uuid4()
        repo.guardar(_entrada(juego_a, tipo="atrasos_pares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_CON_MARCADOR, resultado={"v": "juego_a"}))
        repo.guardar(_entrada(juego_b, tipo="atrasos_pares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_CON_MARCADOR, resultado={"v": "juego_b"}))
        a = repo.buscar_vigente(juego_a, "atrasos_pares_colorloto", None, self._PARAMS_CON_MARCADOR)
        b = repo.buscar_vigente(juego_b, "atrasos_pares_colorloto", None, self._PARAMS_CON_MARCADOR)
        assert a.resultado == {"v": "juego_a"}
        assert b.resultado == {"v": "juego_b"}

    def test_caché_antigua_sin_marcador_no_es_seleccionada(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        params_sin_marcador = {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}
        repo.guardar(_entrada(juego_id, tipo="atrasos_pares_colorloto", hasta_numero_sorteo=None, parametros=params_sin_marcador, resultado={"v": "sin_marcador_hipotetico"}))
        vigente = repo.buscar_vigente(juego_id, "atrasos_pares_colorloto", None, self._PARAMS_CON_MARCADOR)
        assert vigente is None

    def test_hit_de_cache_nueva_con_marcador(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, tipo="atrasos_pares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_CON_MARCADOR, resultado={"v": "cacheado"}))
        vigente = repo.buscar_vigente(juego_id, "atrasos_pares_colorloto", None, self._PARAMS_CON_MARCADOR)
        assert vigente is not None
        assert vigente.id == primera.id

    def test_historico_completo_y_corte_son_caches_distintas(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="atrasos_pares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_CON_MARCADOR, resultado={"v": "completo"}))
        repo.guardar(_entrada(juego_id, tipo="atrasos_pares_colorloto", hasta_numero_sorteo=100, parametros=self._PARAMS_CON_MARCADOR, resultado={"v": "corte"}))
        completo = repo.buscar_vigente(juego_id, "atrasos_pares_colorloto", None, self._PARAMS_CON_MARCADOR)
        corte = repo.buscar_vigente(juego_id, "atrasos_pares_colorloto", 100, self._PARAMS_CON_MARCADOR)
        assert completo.resultado == {"v": "completo"}
        assert corte.resultado == {"v": "corte"}

    def test_recalcular_invalidado_no_duplica_upsert(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, tipo="atrasos_pares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_CON_MARCADOR, resultado={"v": "vieja"}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=0)
        segunda = repo.guardar(_entrada(juego_id, tipo="atrasos_pares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_CON_MARCADOR, resultado={"v": "nueva"}))
        assert segunda.id == primera.id
        total = sum(1 for f in repo._filas if f.juego_id == juego_id and f.tipo_estadistica == "atrasos_pares_colorloto")
        assert total == 1

    def test_ninguna_estadistica_de_otro_juego_es_invalidada(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_a, juego_b = uuid4(), uuid4()
        repo.guardar(_entrada(juego_b, tipo="atrasos_pares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_CON_MARCADOR, resultado={"v": "juego_b"}))
        repo.invalidar_por_juego(juego_a, desde_numero_sorteo=0)
        vigente_b = repo.buscar_vigente(juego_b, "atrasos_pares_colorloto", None, self._PARAMS_CON_MARCADOR)
        assert vigente_b is not None
        assert vigente_b.resultado == {"v": "juego_b"}

    def test_convivencia_sin_interferencia_con_las_catorce_metricas_anteriores(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        params_sin_marcador = {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}
        repo.guardar(_entrada(juego_id, tipo="atrasos_numeros_colorloto", hasta_numero_sorteo=None, parametros=params_sin_marcador, resultado={"v": "atrasos_numeros"}))
        repo.guardar(_entrada(juego_id, tipo="atrasos_colores_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_CON_MARCADOR, resultado={"v": "atrasos_colores"}))
        repo.guardar(_entrada(juego_id, tipo="atrasos_pares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_CON_MARCADOR, resultado={"v": "atrasos_pares"}))
        assert repo.buscar_vigente(juego_id, "atrasos_numeros_colorloto", None, params_sin_marcador).resultado == {"v": "atrasos_numeros"}
        assert repo.buscar_vigente(juego_id, "atrasos_colores_colorloto", None, self._PARAMS_CON_MARCADOR).resultado == {"v": "atrasos_colores"}
        assert repo.buscar_vigente(juego_id, "atrasos_pares_colorloto", None, self._PARAMS_CON_MARCADOR).resultado == {"v": "atrasos_pares"}

    def test_invalidacion_existente_aplicable_sin_cambios(self):
        """Confirma que invalidar_por_juego (mecanismo agnóstico ya
        existente, sin ningún cambio de código) cubre la nueva
        receta automáticamente."""
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="atrasos_pares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS_CON_MARCADOR, resultado={"v": "x"}))
        afectadas = repo.invalidar_por_juego(juego_id, desde_numero_sorteo=0)
        assert afectadas == 1
        assert repo.buscar_vigente(juego_id, "atrasos_pares_colorloto", None, self._PARAMS_CON_MARCADOR) is None


class TestUpsertConRepeticionesEntreSorteosColorlotoEtapaAE7:
    """Mismo patrón exacto ya usado para las 15 recetas anteriores.
    Identidad con SOLO TRES claves -sin el marcador de política,
    confirmado que esta métrica ignora el color por completo."""

    _PARAMS = {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}

    def test_parametros_exactos_con_las_tres_claves_sin_marcador(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        entrada = repo.guardar(_entrada(juego_id, tipo="repeticiones_entre_sorteos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "nueva"}))
        assert entrada.parametros == self._PARAMS
        assert set(entrada.parametros.keys()) == {"rango_min", "rango_max", "cantidad_numeros"}
        assert "politica_universo_colores" not in entrada.parametros

    def test_ausencia_de_corte_en_parametros(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        entrada = repo.guardar(_entrada(juego_id, tipo="repeticiones_entre_sorteos_colorloto", hasta_numero_sorteo=100, parametros=self._PARAMS, resultado={"v": "x"}))
        assert "hasta_numero_sorteo" not in entrada.parametros

    def test_identidad_por_juego(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_a, juego_b = uuid4(), uuid4()
        repo.guardar(_entrada(juego_a, tipo="repeticiones_entre_sorteos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "juego_a"}))
        repo.guardar(_entrada(juego_b, tipo="repeticiones_entre_sorteos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "juego_b"}))
        a = repo.buscar_vigente(juego_a, "repeticiones_entre_sorteos_colorloto", None, self._PARAMS)
        b = repo.buscar_vigente(juego_b, "repeticiones_entre_sorteos_colorloto", None, self._PARAMS)
        assert a.resultado == {"v": "juego_a"}
        assert b.resultado == {"v": "juego_b"}

    def test_hit_de_cache(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, tipo="repeticiones_entre_sorteos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "cacheado"}))
        vigente = repo.buscar_vigente(juego_id, "repeticiones_entre_sorteos_colorloto", None, self._PARAMS)
        assert vigente is not None
        assert vigente.id == primera.id

    def test_miss_de_cache_con_parametros_distintos(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="repeticiones_entre_sorteos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "x"}))
        otros_params = {"rango_min": 1, "rango_max": 9, "cantidad_numeros": 6}
        vigente = repo.buscar_vigente(juego_id, "repeticiones_entre_sorteos_colorloto", None, otros_params)
        assert vigente is None

    def test_historico_completo_y_corte_son_caches_distintas(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="repeticiones_entre_sorteos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "completo"}))
        repo.guardar(_entrada(juego_id, tipo="repeticiones_entre_sorteos_colorloto", hasta_numero_sorteo=100, parametros=self._PARAMS, resultado={"v": "corte"}))
        completo = repo.buscar_vigente(juego_id, "repeticiones_entre_sorteos_colorloto", None, self._PARAMS)
        corte = repo.buscar_vigente(juego_id, "repeticiones_entre_sorteos_colorloto", 100, self._PARAMS)
        assert completo.resultado == {"v": "completo"}
        assert corte.resultado == {"v": "corte"}

    def test_recalcular_invalidado_no_duplica_upsert(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, tipo="repeticiones_entre_sorteos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "vieja"}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=0)
        segunda = repo.guardar(_entrada(juego_id, tipo="repeticiones_entre_sorteos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "nueva"}))
        assert segunda.id == primera.id
        total = sum(1 for f in repo._filas if f.juego_id == juego_id and f.tipo_estadistica == "repeticiones_entre_sorteos_colorloto")
        assert total == 1

    def test_invalidacion_por_sorteo_existente_aplicable_sin_cambios(self):
        """Confirma que invalidar_por_juego (mecanismo agnóstico ya
        existente, sin ningún cambio de código) cubre la nueva
        receta automáticamente."""
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="repeticiones_entre_sorteos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "x"}))
        afectadas = repo.invalidar_por_juego(juego_id, desde_numero_sorteo=0)
        assert afectadas == 1
        assert repo.buscar_vigente(juego_id, "repeticiones_entre_sorteos_colorloto", None, self._PARAMS) is None

    def test_invalidacion_conservadora_por_paleta_sin_modificar_su_codigo(self):
        """La invalidación genérica por cambios de paleta
        (`GestionarPaletaColores` -> `invalidar_por_juego`, agnóstica
        de tipo_estadistica) invalida esta caché igual que las
        demás, aunque la métrica no dependa del color -comportamiento
        conservador aceptado, mismo mecanismo YA existente, SIN
        ningún cambio de código requerido ni realizado."""
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="repeticiones_entre_sorteos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "x"}))
        # Mismo invalidar_por_juego usado por GestionarPaletaColores -
        # sin discriminar tipo_estadistica, tal como ya sucede para
        # las 6 recetas de ColorLoto que SI dependen de color.
        afectadas = repo.invalidar_por_juego(juego_id, desde_numero_sorteo=0)
        assert afectadas == 1

    def test_convivencia_sin_interferencia_con_las_quince_metricas_anteriores(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        params_con_marcador = {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6, "politica_universo_colores": "vigentes_ultimo_sorteo_mas_observados_v1"}
        repo.guardar(_entrada(juego_id, tipo="atrasos_pares_colorloto", hasta_numero_sorteo=None, parametros=params_con_marcador, resultado={"v": "atrasos_pares"}))
        repo.guardar(_entrada(juego_id, tipo="repeticiones_entre_sorteos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "repeticiones"}))
        assert repo.buscar_vigente(juego_id, "atrasos_pares_colorloto", None, params_con_marcador).resultado == {"v": "atrasos_pares"}
        assert repo.buscar_vigente(juego_id, "repeticiones_entre_sorteos_colorloto", None, self._PARAMS).resultado == {"v": "repeticiones"}


class TestUpsertConDistribucionParesImparesColorlotoEtapaAE8:
    """Mismo patrón exacto ya usado para las 16 recetas anteriores.
    Identidad con SOLO UNA clave -sin rango, sin marcador de
    política, confirmado que esta métrica ignora el color y no
    depende de los límites del rango."""

    _PARAMS = {"cantidad_numeros": 6}

    def test_parametros_exactos_con_una_sola_clave(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        entrada = repo.guardar(_entrada(juego_id, tipo="distribucion_pares_impares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "nueva"}))
        assert entrada.parametros == self._PARAMS
        assert set(entrada.parametros.keys()) == {"cantidad_numeros"}
        assert "rango_min" not in entrada.parametros
        assert "rango_max" not in entrada.parametros
        assert "politica_universo_colores" not in entrada.parametros

    def test_ausencia_de_corte_en_parametros(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        entrada = repo.guardar(_entrada(juego_id, tipo="distribucion_pares_impares_colorloto", hasta_numero_sorteo=100, parametros=self._PARAMS, resultado={"v": "x"}))
        assert "hasta_numero_sorteo" not in entrada.parametros

    def test_identidad_por_juego(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_a, juego_b = uuid4(), uuid4()
        repo.guardar(_entrada(juego_a, tipo="distribucion_pares_impares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "juego_a"}))
        repo.guardar(_entrada(juego_b, tipo="distribucion_pares_impares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "juego_b"}))
        a = repo.buscar_vigente(juego_a, "distribucion_pares_impares_colorloto", None, self._PARAMS)
        b = repo.buscar_vigente(juego_b, "distribucion_pares_impares_colorloto", None, self._PARAMS)
        assert a.resultado == {"v": "juego_a"}
        assert b.resultado == {"v": "juego_b"}

    def test_hit_de_cache(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, tipo="distribucion_pares_impares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "cacheado"}))
        vigente = repo.buscar_vigente(juego_id, "distribucion_pares_impares_colorloto", None, self._PARAMS)
        assert vigente is not None
        assert vigente.id == primera.id

    def test_historico_completo_y_corte_son_caches_distintas(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="distribucion_pares_impares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "completo"}))
        repo.guardar(_entrada(juego_id, tipo="distribucion_pares_impares_colorloto", hasta_numero_sorteo=100, parametros=self._PARAMS, resultado={"v": "corte"}))
        completo = repo.buscar_vigente(juego_id, "distribucion_pares_impares_colorloto", None, self._PARAMS)
        corte = repo.buscar_vigente(juego_id, "distribucion_pares_impares_colorloto", 100, self._PARAMS)
        assert completo.resultado == {"v": "completo"}
        assert corte.resultado == {"v": "corte"}

    def test_recalcular_invalidado_no_duplica_upsert(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, tipo="distribucion_pares_impares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "vieja"}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=0)
        segunda = repo.guardar(_entrada(juego_id, tipo="distribucion_pares_impares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "nueva"}))
        assert segunda.id == primera.id
        total = sum(1 for f in repo._filas if f.juego_id == juego_id and f.tipo_estadistica == "distribucion_pares_impares_colorloto")
        assert total == 1

    def test_invalidacion_existente_aplicable_sin_cambios(self):
        """Confirma que invalidar_por_juego (mecanismo agnóstico ya
        existente, sin ningún cambio de código) cubre la nueva
        receta automáticamente."""
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="distribucion_pares_impares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "x"}))
        afectadas = repo.invalidar_por_juego(juego_id, desde_numero_sorteo=0)
        assert afectadas == 1
        assert repo.buscar_vigente(juego_id, "distribucion_pares_impares_colorloto", None, self._PARAMS) is None

    def test_invalidacion_conservadora_por_paleta_sin_modificar_su_codigo(self):
        """La invalidación genérica por cambios de paleta continúa
        funcionando de manera genérica, sin ningún cambio de código,
        aunque la métrica no dependa del color."""
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="distribucion_pares_impares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "x"}))
        afectadas = repo.invalidar_por_juego(juego_id, desde_numero_sorteo=0)
        assert afectadas == 1

    def test_no_colisiona_con_cache_de_otras_metricas(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        params_repeticiones = {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}
        repo.guardar(_entrada(juego_id, tipo="repeticiones_entre_sorteos_colorloto", hasta_numero_sorteo=None, parametros=params_repeticiones, resultado={"v": "repeticiones"}))
        repo.guardar(_entrada(juego_id, tipo="distribucion_pares_impares_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "pares_impares"}))
        assert repo.buscar_vigente(juego_id, "repeticiones_entre_sorteos_colorloto", None, params_repeticiones).resultado == {"v": "repeticiones"}
        assert repo.buscar_vigente(juego_id, "distribucion_pares_impares_colorloto", None, self._PARAMS).resultado == {"v": "pares_impares"}


class TestUpsertConDistribucionAltosBajosColorlotoEtapaAE9:
    """Mismo patrón exacto ya usado para las 17 recetas anteriores.
    Identidad con TRES claves -a diferencia de AE-8, aquí
    `rango_min`/`rango_max` SÍ forman parte de la identidad,
    confirmado por la auditoría y su adenda correctiva que el
    umbral bajos/altos depende materialmente del rango."""

    _PARAMS = {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}

    def test_parametros_exactos_con_tres_claves(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        entrada = repo.guardar(_entrada(juego_id, tipo="distribucion_altos_bajos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "nueva"}))
        assert entrada.parametros == self._PARAMS
        assert set(entrada.parametros.keys()) == {"rango_min", "rango_max", "cantidad_numeros"}
        assert "politica_universo_colores" not in entrada.parametros

    def test_ausencia_de_corte_en_parametros(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        entrada = repo.guardar(_entrada(juego_id, tipo="distribucion_altos_bajos_colorloto", hasta_numero_sorteo=100, parametros=self._PARAMS, resultado={"v": "x"}))
        assert "hasta_numero_sorteo" not in entrada.parametros

    def test_identidad_por_juego(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_a, juego_b = uuid4(), uuid4()
        repo.guardar(_entrada(juego_a, tipo="distribucion_altos_bajos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "juego_a"}))
        repo.guardar(_entrada(juego_b, tipo="distribucion_altos_bajos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "juego_b"}))
        a = repo.buscar_vigente(juego_a, "distribucion_altos_bajos_colorloto", None, self._PARAMS)
        b = repo.buscar_vigente(juego_b, "distribucion_altos_bajos_colorloto", None, self._PARAMS)
        assert a.resultado == {"v": "juego_a"}
        assert b.resultado == {"v": "juego_b"}

    def test_hit_de_cache_con_las_tres_claves_identicas(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, tipo="distribucion_altos_bajos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "cacheado"}))
        vigente = repo.buscar_vigente(juego_id, "distribucion_altos_bajos_colorloto", None, dict(self._PARAMS))
        assert vigente is not None
        assert vigente.id == primera.id

    def test_miss_de_cache_si_cambia_rango_min(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="distribucion_altos_bajos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "x"}))
        otros_params = {"rango_min": 2, "rango_max": 7, "cantidad_numeros": 6}
        vigente = repo.buscar_vigente(juego_id, "distribucion_altos_bajos_colorloto", None, otros_params)
        assert vigente is None

    def test_miss_de_cache_si_cambia_rango_max(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="distribucion_altos_bajos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "x"}))
        otros_params = {"rango_min": 1, "rango_max": 9, "cantidad_numeros": 6}
        vigente = repo.buscar_vigente(juego_id, "distribucion_altos_bajos_colorloto", None, otros_params)
        assert vigente is None

    def test_miss_de_cache_si_cambia_cantidad_numeros(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="distribucion_altos_bajos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "x"}))
        otros_params = {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 5}
        vigente = repo.buscar_vigente(juego_id, "distribucion_altos_bajos_colorloto", None, otros_params)
        assert vigente is None

    def test_historico_completo_y_corte_son_caches_distintas(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="distribucion_altos_bajos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "completo"}))
        repo.guardar(_entrada(juego_id, tipo="distribucion_altos_bajos_colorloto", hasta_numero_sorteo=100, parametros=self._PARAMS, resultado={"v": "corte"}))
        completo = repo.buscar_vigente(juego_id, "distribucion_altos_bajos_colorloto", None, self._PARAMS)
        corte = repo.buscar_vigente(juego_id, "distribucion_altos_bajos_colorloto", 100, self._PARAMS)
        assert completo.resultado == {"v": "completo"}
        assert corte.resultado == {"v": "corte"}

    def test_recalcular_invalidado_no_duplica_upsert(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, tipo="distribucion_altos_bajos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "vieja"}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=0)
        segunda = repo.guardar(_entrada(juego_id, tipo="distribucion_altos_bajos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "nueva"}))
        assert segunda.id == primera.id
        total = sum(1 for f in repo._filas if f.juego_id == juego_id and f.tipo_estadistica == "distribucion_altos_bajos_colorloto")
        assert total == 1

    def test_invalidacion_existente_aplicable_sin_cambios(self):
        """Confirma que invalidar_por_juego (mecanismo agnóstico ya
        existente, sin ningún cambio de código) cubre la nueva
        receta automáticamente."""
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="distribucion_altos_bajos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "x"}))
        afectadas = repo.invalidar_por_juego(juego_id, desde_numero_sorteo=0)
        assert afectadas == 1
        assert repo.buscar_vigente(juego_id, "distribucion_altos_bajos_colorloto", None, self._PARAMS) is None

    def test_no_colisiona_con_cache_de_otras_metricas(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        params_pares_impares = {"cantidad_numeros": 6}
        repo.guardar(_entrada(juego_id, tipo="distribucion_pares_impares_colorloto", hasta_numero_sorteo=None, parametros=params_pares_impares, resultado={"v": "pares_impares"}))
        repo.guardar(_entrada(juego_id, tipo="distribucion_altos_bajos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "altos_bajos"}))
        assert repo.buscar_vigente(juego_id, "distribucion_pares_impares_colorloto", None, params_pares_impares).resultado == {"v": "pares_impares"}
        assert repo.buscar_vigente(juego_id, "distribucion_altos_bajos_colorloto", None, self._PARAMS).resultado == {"v": "altos_bajos"}


class TestUpsertConMaximoRepeticionColorPorSorteoColorlotoEtapaAE10:
    """Mismo patrón exacto ya usado para las 18 recetas anteriores.
    Identidad con SOLO UNA clave -decisión M1, confirmada con
    evidencia directa en la auditoría y su adenda correctiva: el
    motor lee y compara colores observados, pero nunca construye
    categorías desde el catálogo, así que la política de universo
    de colores no forma parte de la identidad."""

    _PARAMS = {"cantidad_numeros": 6}

    def test_parametros_exactos_con_una_sola_clave(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        entrada = repo.guardar(_entrada(juego_id, tipo="maximo_repeticion_color_por_sorteo_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "nueva"}))
        assert entrada.parametros == self._PARAMS
        assert set(entrada.parametros.keys()) == {"cantidad_numeros"}
        assert "rango_min" not in entrada.parametros
        assert "rango_max" not in entrada.parametros
        assert "politica_universo_colores" not in entrada.parametros

    def test_ausencia_de_corte_en_parametros(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        entrada = repo.guardar(_entrada(juego_id, tipo="maximo_repeticion_color_por_sorteo_colorloto", hasta_numero_sorteo=100, parametros=self._PARAMS, resultado={"v": "x"}))
        assert "hasta_numero_sorteo" not in entrada.parametros

    def test_identidad_por_juego(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_a, juego_b = uuid4(), uuid4()
        repo.guardar(_entrada(juego_a, tipo="maximo_repeticion_color_por_sorteo_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "juego_a"}))
        repo.guardar(_entrada(juego_b, tipo="maximo_repeticion_color_por_sorteo_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "juego_b"}))
        a = repo.buscar_vigente(juego_a, "maximo_repeticion_color_por_sorteo_colorloto", None, self._PARAMS)
        b = repo.buscar_vigente(juego_b, "maximo_repeticion_color_por_sorteo_colorloto", None, self._PARAMS)
        assert a.resultado == {"v": "juego_a"}
        assert b.resultado == {"v": "juego_b"}

    def test_hit_de_cache_con_identidad_identica(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, tipo="maximo_repeticion_color_por_sorteo_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "cacheado"}))
        vigente = repo.buscar_vigente(juego_id, "maximo_repeticion_color_por_sorteo_colorloto", None, dict(self._PARAMS))
        assert vigente is not None
        assert vigente.id == primera.id

    def test_miss_de_cache_si_cambia_cantidad_numeros(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="maximo_repeticion_color_por_sorteo_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "x"}))
        otros_params = {"cantidad_numeros": 5}
        vigente = repo.buscar_vigente(juego_id, "maximo_repeticion_color_por_sorteo_colorloto", None, otros_params)
        assert vigente is None

    def test_historico_completo_y_corte_son_caches_distintas(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="maximo_repeticion_color_por_sorteo_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "completo"}))
        repo.guardar(_entrada(juego_id, tipo="maximo_repeticion_color_por_sorteo_colorloto", hasta_numero_sorteo=100, parametros=self._PARAMS, resultado={"v": "corte"}))
        completo = repo.buscar_vigente(juego_id, "maximo_repeticion_color_por_sorteo_colorloto", None, self._PARAMS)
        corte = repo.buscar_vigente(juego_id, "maximo_repeticion_color_por_sorteo_colorloto", 100, self._PARAMS)
        assert completo.resultado == {"v": "completo"}
        assert corte.resultado == {"v": "corte"}

    def test_recalcular_invalidado_no_duplica_upsert(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, tipo="maximo_repeticion_color_por_sorteo_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "vieja"}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=0)
        segunda = repo.guardar(_entrada(juego_id, tipo="maximo_repeticion_color_por_sorteo_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "nueva"}))
        assert segunda.id == primera.id
        total = sum(1 for f in repo._filas if f.juego_id == juego_id and f.tipo_estadistica == "maximo_repeticion_color_por_sorteo_colorloto")
        assert total == 1

    def test_invalidacion_por_sorteo_existente_aplicable_sin_cambios(self):
        """Confirma que invalidar_por_juego (mecanismo agnóstico ya
        existente, sin ningún cambio de código) cubre la nueva
        receta automáticamente -mismo mecanismo usado por
        RegistrarSorteo/EditarSorteo/EliminarSorteo, ninguno de
        los cuales fue modificado."""
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="maximo_repeticion_color_por_sorteo_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "x"}))
        afectadas = repo.invalidar_por_juego(juego_id, desde_numero_sorteo=0)
        assert afectadas == 1
        assert repo.buscar_vigente(juego_id, "maximo_repeticion_color_por_sorteo_colorloto", None, self._PARAMS) is None

    def test_invalidacion_conservadora_por_paleta_cubre_ae10_sin_cambios(self):
        """GestionarPaletaColores llama exactamente al mismo
        invalidar_por_juego(juego_id, desde_numero_sorteo=0),
        agnóstico de tipo_estadistica -cubre esta receta
        automáticamente sin ningún cambio de código, aunque
        matemáticamente no sea necesario para colores no
        observados (decisión M1). No se duplica la cobertura ya
        existente de GestionarPaletaColores mismo -solo se
        confirma aquí que el mecanismo agnóstico alcanza también
        a esta receta específica."""
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="maximo_repeticion_color_por_sorteo_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "x"}))
        afectadas = repo.invalidar_por_juego(juego_id, desde_numero_sorteo=0)
        assert afectadas == 1

    def test_no_colisiona_con_cache_de_otras_metricas(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        params_altos_bajos = {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}
        repo.guardar(_entrada(juego_id, tipo="distribucion_altos_bajos_colorloto", hasta_numero_sorteo=None, parametros=params_altos_bajos, resultado={"v": "altos_bajos"}))
        repo.guardar(_entrada(juego_id, tipo="maximo_repeticion_color_por_sorteo_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "max_color"}))
        assert repo.buscar_vigente(juego_id, "distribucion_altos_bajos_colorloto", None, params_altos_bajos).resultado == {"v": "altos_bajos"}
        assert repo.buscar_vigente(juego_id, "maximo_repeticion_color_por_sorteo_colorloto", None, self._PARAMS).resultado == {"v": "max_color"}


class TestUpsertConDistribucionParesConsecutivosColorlotoEtapaAE11:
    """Mismo patrón exacto ya usado para las 19 recetas anteriores
    (Etapa AE-11, PROVISIONAL). Identidad con SOLO UNA clave -decisión
    M1, confirmada con evidencia directa (caracterización real) en la
    auditoría y su adenda correctiva: el motor exige `rango_min`/
    `rango_max` como argumentos posicionales, pero únicamente para su
    validación interna -el conteo de pares consecutivos, las
    categorías y el denominador nunca dependen de esos límites, así
    que la identidad de caché persistida es idéntica a la de AE-8/AE-10
    (`{"cantidad_numeros": 6}`), sin rango y sin política de universo
    de colores (el motor ignora el color por completo)."""

    _PARAMS = {"cantidad_numeros": 6}

    def test_parametros_exactos_con_una_sola_clave(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        entrada = repo.guardar(_entrada(juego_id, tipo="distribucion_pares_consecutivos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "nueva"}))
        assert entrada.parametros == self._PARAMS
        assert set(entrada.parametros.keys()) == {"cantidad_numeros"}
        assert "rango_min" not in entrada.parametros
        assert "rango_max" not in entrada.parametros
        assert "politica_universo_colores" not in entrada.parametros

    def test_ausencia_de_corte_en_parametros(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        entrada = repo.guardar(_entrada(juego_id, tipo="distribucion_pares_consecutivos_colorloto", hasta_numero_sorteo=100, parametros=self._PARAMS, resultado={"v": "x"}))
        assert "hasta_numero_sorteo" not in entrada.parametros

    def test_identidad_por_juego(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_a, juego_b = uuid4(), uuid4()
        repo.guardar(_entrada(juego_a, tipo="distribucion_pares_consecutivos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "juego_a"}))
        repo.guardar(_entrada(juego_b, tipo="distribucion_pares_consecutivos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "juego_b"}))
        a = repo.buscar_vigente(juego_a, "distribucion_pares_consecutivos_colorloto", None, self._PARAMS)
        b = repo.buscar_vigente(juego_b, "distribucion_pares_consecutivos_colorloto", None, self._PARAMS)
        assert a.resultado == {"v": "juego_a"}
        assert b.resultado == {"v": "juego_b"}

    def test_hit_de_cache_con_identidad_identica(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, tipo="distribucion_pares_consecutivos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "cacheado"}))
        vigente = repo.buscar_vigente(juego_id, "distribucion_pares_consecutivos_colorloto", None, dict(self._PARAMS))
        assert vigente is not None
        assert vigente.id == primera.id

    def test_miss_de_cache_si_cambia_cantidad_numeros(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="distribucion_pares_consecutivos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "x"}))
        otros_params = {"cantidad_numeros": 5}
        vigente = repo.buscar_vigente(juego_id, "distribucion_pares_consecutivos_colorloto", None, otros_params)
        assert vigente is None

    def test_historico_completo_y_corte_son_caches_distintas(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="distribucion_pares_consecutivos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "completo"}))
        repo.guardar(_entrada(juego_id, tipo="distribucion_pares_consecutivos_colorloto", hasta_numero_sorteo=100, parametros=self._PARAMS, resultado={"v": "corte"}))
        completo = repo.buscar_vigente(juego_id, "distribucion_pares_consecutivos_colorloto", None, self._PARAMS)
        corte = repo.buscar_vigente(juego_id, "distribucion_pares_consecutivos_colorloto", 100, self._PARAMS)
        assert completo.resultado == {"v": "completo"}
        assert corte.resultado == {"v": "corte"}

    def test_recalcular_invalidado_no_duplica_upsert(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        primera = repo.guardar(_entrada(juego_id, tipo="distribucion_pares_consecutivos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "vieja"}))
        repo.invalidar_por_juego(juego_id, desde_numero_sorteo=0)
        segunda = repo.guardar(_entrada(juego_id, tipo="distribucion_pares_consecutivos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "nueva"}))
        assert segunda.id == primera.id
        total = sum(1 for f in repo._filas if f.juego_id == juego_id and f.tipo_estadistica == "distribucion_pares_consecutivos_colorloto")
        assert total == 1

    def test_invalidacion_por_sorteo_existente_aplicable_sin_cambios(self):
        """Confirma que invalidar_por_juego (mecanismo agnóstico ya
        existente, sin ningún cambio de código) cubre la nueva
        receta automáticamente -mismo mecanismo usado por
        RegistrarSorteo/EditarSorteo/EliminarSorteo, ninguno de
        los cuales fue modificado."""
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="distribucion_pares_consecutivos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "x"}))
        afectadas = repo.invalidar_por_juego(juego_id, desde_numero_sorteo=0)
        assert afectadas == 1
        assert repo.buscar_vigente(juego_id, "distribucion_pares_consecutivos_colorloto", None, self._PARAMS) is None

    def test_invalidacion_conservadora_por_paleta_cubre_ae11_sin_cambios(self):
        """GestionarPaletaColores llama exactamente al mismo
        invalidar_por_juego(juego_id, desde_numero_sorteo=0),
        agnóstico de tipo_estadistica -cubre esta receta
        automáticamente sin ningún cambio de código, aunque
        matemáticamente no sea necesario (el motor ignora el color
        por completo, decisión M1). No se duplica la cobertura ya
        existente de GestionarPaletaColores mismo -solo se
        confirma aquí que el mecanismo agnóstico alcanza también
        a esta receta específica."""
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        repo.guardar(_entrada(juego_id, tipo="distribucion_pares_consecutivos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "x"}))
        afectadas = repo.invalidar_por_juego(juego_id, desde_numero_sorteo=0)
        assert afectadas == 1

    def test_no_colisiona_con_cache_de_otras_metricas(self):
        repo = _EstadisticaRepositoryEnMemoria()
        juego_id = uuid4()
        params_altos_bajos = {"rango_min": 1, "rango_max": 7, "cantidad_numeros": 6}
        repo.guardar(_entrada(juego_id, tipo="distribucion_altos_bajos_colorloto", hasta_numero_sorteo=None, parametros=params_altos_bajos, resultado={"v": "altos_bajos"}))
        repo.guardar(_entrada(juego_id, tipo="distribucion_pares_consecutivos_colorloto", hasta_numero_sorteo=None, parametros=self._PARAMS, resultado={"v": "pares_consecutivos"}))
        assert repo.buscar_vigente(juego_id, "distribucion_altos_bajos_colorloto", None, params_altos_bajos).resultado == {"v": "altos_bajos"}
        assert repo.buscar_vigente(juego_id, "distribucion_pares_consecutivos_colorloto", None, self._PARAMS).resultado == {"v": "pares_consecutivos"}
