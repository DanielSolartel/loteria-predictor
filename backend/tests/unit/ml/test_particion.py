"""Tests de `application/ml/particion.py` -Etapa AE-36."""
from __future__ import annotations

from datetime import date, timedelta
import random

import pytest

from app.application.estadisticas.tipos import ResultadoNumerico
from app.application.ml.dataset import construir_dataset_binario
from app.application.ml.particion import construir_particion_walk_forward


def _historico_sintetico(n_sorteos: int, semilla: int = 7) -> list[ResultadoNumerico]:
    rng = random.Random(semilla)
    base = date(2020, 1, 1)
    return [
        ResultadoNumerico(
            numero_sorteo=n, fecha=base + timedelta(days=n), dia_semana="lunes",
            numeros=tuple(sorted(rng.sample(range(1, 44), 5))), superbalota=rng.randint(1, 16),
        )
        for n in range(1, n_sorteos + 1)
    ]


class TestParticionWalkForward:
    def test_test_final_nunca_aparece_en_entrenamiento_ni_validacion(self):
        hist = _historico_sintetico(200)
        ds = construir_dataset_binario(hist, 1, 43, 5, "BALOTO")
        part = construir_particion_walk_forward(ds)
        sorteos_test = {f.sorteo_objetivo for f in part.filas_test_final}
        for bloque in part.filas_entrenamiento_por_bloque:
            assert not any(f.sorteo_objetivo in sorteos_test for f in bloque)
        for bloque in part.filas_validacion_por_bloque:
            assert not any(f.sorteo_objetivo in sorteos_test for f in bloque)

    def test_bloques_de_entrenamiento_son_expansivos(self):
        hist = _historico_sintetico(200)
        ds = construir_dataset_binario(hist, 1, 43, 5, "BALOTO")
        part = construir_particion_walk_forward(ds)
        tamanos = [len(b) for b in part.filas_entrenamiento_por_bloque]
        assert all(tamanos[i] <= tamanos[i + 1] for i in range(len(tamanos) - 1))

    def test_sin_interseccion_entre_entrenamiento_y_validacion_del_mismo_bloque(self):
        hist = _historico_sintetico(200)
        ds = construir_dataset_binario(hist, 1, 43, 5, "BALOTO")
        part = construir_particion_walk_forward(ds)
        for bloque_train, bloque_val in zip(part.filas_entrenamiento_por_bloque, part.filas_validacion_por_bloque):
            sorteos_train = {f.sorteo_objetivo for f in bloque_train}
            sorteos_val = {f.sorteo_objetivo for f in bloque_val}
            assert not (sorteos_train & sorteos_val)

    def test_grupos_de_sorteo_nunca_se_dividen(self):
        hist = _historico_sintetico(200)
        ds = construir_dataset_binario(hist, 1, 43, 5, "BALOTO")
        part = construir_particion_walk_forward(ds)
        todos_los_bloques = list(part.filas_entrenamiento_por_bloque) + list(part.filas_validacion_por_bloque) + [part.filas_test_final]
        for bloque in todos_los_bloques:
            conteo: dict[int, int] = {}
            for f in bloque:
                conteo[f.sorteo_objetivo] = conteo.get(f.sorteo_objetivo, 0) + 1
            assert all(v == 43 for v in conteo.values())

    def test_fronteras_registradas_con_numeros_de_sorteo_reales(self):
        hist = _historico_sintetico(200)
        ds = construir_dataset_binario(hist, 1, 43, 5, "BALOTO")
        part = construir_particion_walk_forward(ds)
        assert part.limites.test_inicio in ds.sorteos_objetivo
        assert part.limites.test_fin == ds.sorteos_objetivo[-1]
        assert part.limites.primer_sorteo_elegible == ds.sorteos_objetivo[0]

    def test_dataset_sin_sorteos_elegibles_falla_explicitamente(self):
        ds_vacio = construir_dataset_binario([], 1, 43, 5, "BALOTO")
        with pytest.raises(ValueError):
            construir_particion_walk_forward(ds_vacio)

    def test_test_final_no_vacio(self):
        hist = _historico_sintetico(200)
        ds = construir_dataset_binario(hist, 1, 43, 5, "BALOTO")
        part = construir_particion_walk_forward(ds)
        assert len(part.filas_test_final) > 0
