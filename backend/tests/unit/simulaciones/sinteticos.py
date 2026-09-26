"""Historicos sinteticos deterministas para las pruebas de AE-49.

Se construyen con una formula aritmetica -nunca con azar ni con datos
reales- para que las pruebas de referencia de bytes sean
reproducibles. Cinco numeros distintos de 1..43: `(i*a + j*b) % 43`
con `b` coprimo con 43 da cinco residuos distintos para j = 0..4."""
from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from app.application.estadisticas.tipos import ResultadoNumerico
from app.domain.entities.juego import Juego

ID_BALOTO = UUID("00000000-0000-0000-0000-00000000b001")
ID_REVANCHA = UUID("00000000-0000-0000-0000-00000000b002")
ID_MILOTO = UUID("00000000-0000-0000-0000-00000000c003")


def historico(desde: int = 2081, hasta: int = 2705, a: int = 7, b: int = 9, c: int = 5) -> list[ResultadoNumerico]:
    salida = []
    for i, numero_sorteo in enumerate(range(desde, hasta + 1)):
        numeros = tuple(sorted(((i * a + j * b) % 43) + 1 for j in range(5)))
        salida.append(ResultadoNumerico(
            numero_sorteo=numero_sorteo,
            fecha=date(2020, 1, 1) + timedelta(days=i),
            dia_semana="lunes",
            numeros=numeros,
            superbalota=(i * c) % 16 + 1,
        ))
    return salida


def historico_baloto() -> list[ResultadoNumerico]:
    return historico(a=7, b=9, c=5)


def historico_revancha() -> list[ResultadoNumerico]:
    return historico(a=11, b=13, c=3)


def juego(codigo: str, juego_id: UUID, **cambios) -> Juego:
    datos = dict(
        id=juego_id, codigo=codigo, nombre=codigo.title(), rango_min=1, rango_max=43, cantidad_numeros=5,
        tiene_superbalota=True, superbalota_min=1, superbalota_max=16, tiene_color=False,
        permite_repeticion=False,
    )
    datos.update(cambios)
    return Juego(**datos)


class JuegoRepositoryFake:
    def __init__(self, juegos: dict[str, Juego] | None = None):
        self.juegos = juegos if juegos is not None else {
            "BALOTO": juego("BALOTO", ID_BALOTO),
            "BALOTO_REVANCHA": juego("BALOTO_REVANCHA", ID_REVANCHA),
        }
        self.consultas: list[str] = []

    def obtener_por_codigo(self, codigo: str):
        self.consultas.append(codigo)
        return self.juegos.get(codigo)


class ResultadosRepositoryFake:
    """Falla si se pide cualquier corte distinto de 2705: AE-49 nunca
    lee 2706 en adelante."""

    def __init__(self, historicos: dict[UUID, list[ResultadoNumerico]] | None = None, fallar_en: UUID | None = None):
        self.historicos = historicos if historicos is not None else {
            ID_BALOTO: historico_baloto(),
            ID_REVANCHA: historico_revancha(),
        }
        self.fallar_en = fallar_en
        self.consultas: list[tuple[UUID, int | None]] = []

    def listar_resultados_numericos(self, juego_id: UUID, hasta_numero_sorteo: int | None = None):
        assert hasta_numero_sorteo == 2705, f"corte no permitido en AE-49: {hasta_numero_sorteo}"
        self.consultas.append((juego_id, hasta_numero_sorteo))
        if juego_id == self.fallar_en:
            raise RuntimeError("fallo sintetico del repositorio")
        return list(self.historicos.get(juego_id, []))

    def listar_resultados_colorloto(self, juego_id: UUID, hasta_numero_sorteo: int | None = None):
        raise AssertionError("AE-49 nunca consulta ColorLoto")
