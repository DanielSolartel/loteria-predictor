"""FIXTURES SINTETICAS de Producto 6, solo para pruebas: los almacenes de
Productos 1-3 (operacion diaria), 4 (laboratorio) y 5 (carteras) sobre los
MISMOS repositorios en memoria (sin PostgreSQL ni Internet), y el centro de
resultados que los lee. Ningun dato es real."""
from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path

from app.application.ml import laboratorio_evaluacion as le
from app.application.use_cases.resultados import CentroDeResultados
from app.infrastructure.storage.resultados_file_store import ResultadosFileStore
from tests.unit import fixtures_producto1 as fx
from tests.unit import fixtures_producto3 as f3
from tests.unit import fixtures_producto4 as f4
from tests.unit import fixtures_producto5 as f5

LOCAL = f4.LOCAL
MODELO_LABORATORIO = {"BALOTO": "logistica_regularizada", "BALOTO_REVANCHA": "logistica_regularizada",
                      "MILOTO": "logistica_regularizada", "COLORLOTO": "poisson_regularizado"}
MODELO_CARTERA = {"BALOTO": "logistica_regularizada", "BALOTO_REVANCHA": "logistica_regularizada",
                  "MILOTO": "logistica_regularizada", "COLORLOTO": "uniforme_paleta"}


@dataclasses.dataclass
class Entorno:
    e3: f3.Entorno
    e4: f4.Entorno
    e5: f5.Entorno
    directorio: Path

    @property
    def informes(self) -> ResultadosFileStore:
        return ResultadosFileStore(self.directorio / "resultados")

    def centro(self, reloj=None) -> CentroDeResultados:
        return CentroDeResultados(self.e3.almacen, self.e4.almacen, self.e5.almacen, self.informes, self.e4.abrir,
                                  carteras_servicio=self.e5.carteras, reloj=reloj or f4.Reloj())

    def poblar(self, juegos=("MILOTO", "COLORLOTO"), *, operacion=True, laboratorio=True, carteras=(5, 3)):
        """Emite artefactos REALES de las tres procedencias para el objetivo
        siguiente al ultimo sorteo cargado (entrenamientos reducidos)."""
        if operacion:
            self.e3.operacion().ejecutar_ahora(list(juegos), "local", "prueba")
        if laboratorio:
            lab = self.e4.laboratorio()
            for j in juegos:
                r = lab.comparar_ahora([j], le.Protocolo(bloques=1, perfil="reducido"))["juegos"][j]
                lab.generar(r["experimento"], MODELO_LABORATORIO[j])
        if carteras:
            servicio = self.e5.carteras()
            for j in juegos:
                for n in carteras:
                    servicio.ahora("cartera", [j], {"modelo": MODELO_CARTERA[j], "perfil": "reducido", "cantidad": n,
                                                    "semilla": 42, "diversidad": "libre"})

    def llega_el_resultado(self, juego: str, semilla: int = 99) -> list:
        """Carga el sorteo del objetivo pendiente (el siguiente al ultimo)."""
        nuevos = self.e4.siguiente(juego, semilla=semilla)
        self.e4.anadir(juego, nuevos)
        return nuevos


def entorno(tmp_path: Path) -> Entorno:
    e3 = f3.entorno(tmp_path / "p3")
    e4 = f4.Entorno(e3.juegos, e3.resultados, e3.historicos, tmp_path / "laboratorio")
    e5 = f5.Entorno(e3.juegos, e3.resultados, e3.historicos, tmp_path / "carteras")
    return Entorno(e3, e4, e5, tmp_path)


def cliente(e: Entorno, *, client=LOCAL, conectada: bool = True, centro: CentroDeResultados | None = None):
    """TestClient de la aplicacion real con el centro de resultados sintetico."""
    from tests import consola_sesion

    from app.api import dependencies as dep
    from app.infrastructure.db.session import get_db
    from app.main import app

    servicio = centro or e.centro()
    app.dependency_overrides = {get_db: lambda: fx._SesionFalsa(conectada), dep.get_resultados: lambda: servicio}
    return consola_sesion.cliente_de_consola(app, client=client)  # E10.1: sesión legítima explícita


limpiar = f4.limpiar


def token(c) -> str:
    return c.get("/resultados/miloto").text.split('name="token_local" value="', 1)[1].split('"', 1)[0]


def foto(directorio: Path) -> dict[str, str]:
    """Huella de cada archivo bajo `directorio` (para comprobar que nada se escribe)."""
    if not directorio.exists():
        return {}
    return {str(p.relative_to(directorio)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directorio.rglob("*")) if p.is_file()}
