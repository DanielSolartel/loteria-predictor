"""
Puerto: almacen del laboratorio de modelos (Producto 4).

Informes de experimento y pronosticos inmutables, identificados por su
clave determinista. Guardar dos veces la misma clave lanza
`FileExistsError` (nunca sobrescribe); el llamador devuelve lo ya guardado.
Los pronosticos se ordenan por linea de modelo y objetivo con una secuencia
sellada, nunca por fecha ni nombre.

Fase 3: MODELOS REGISTRADOS (manifiesto sellado + estimador serializado). La
version solo es visible cuando su manifiesto, publicado el ULTIMO, existe;
el estimador se publica antes y se identifica por su SHA-256. Un numero de
version reservado sin manifiesto (publicacion interrumpida o perdida frente
a otro proceso con la misma entrada) se informa, nunca se presenta como
modelo valido.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class GuardadoLaboratorio:
    identificador: str
    juego: str
    artefacto: dict
    linea: str | None = None
    reutilizado: bool = False
    version: int = 1
    versiones: int = 1

    @property
    def objetivo(self) -> int | None:
        return self.artefacto.get("pronostico", {}).get("objetivo")

    @property
    def secuencia(self) -> int:
        return int((self.artefacto.get("generacion") or {}).get("secuencia_en_la_linea") or 0)


@dataclass(frozen=True)
class IlegibleLaboratorio:
    identificador: str
    juego: str
    motivo: str
    linea: str | None = None
    objetivo: int | None = None


@dataclass(frozen=True)
class GuardadoModelo:
    identificador: str
    juego: str
    artefacto: dict
    reutilizado: bool = False

    @property
    def numero(self) -> int:
        return int(self.artefacto["publicacion"]["numero"])

    @property
    def modelo(self) -> str:
        return self.artefacto["identidad"]["modelo"]["id"]


@dataclass(frozen=True)
class IlegibleModelo:
    identificador: str
    juego: str
    motivo: str
    modelo: str | None = None
    numero: int | None = None


@dataclass(frozen=True)
class ReservaSinModelo:
    """Numero reservado sin un manifiesto valido con ese numero:
    `sin_publicar` (interrumpida o en curso) o `duplicada` (la misma entrada
    se publico con otro numero)."""
    juego: str
    modelo: str
    numero: int
    clave: str
    estado: str


class LaboratorioStore(ABC):
    @abstractmethod
    def guardar_experimento(self, artefacto: dict) -> GuardadoLaboratorio: ...

    @abstractmethod
    def obtener_experimento(self, clave: str) -> GuardadoLaboratorio | IlegibleLaboratorio | None: ...

    @abstractmethod
    def experimentos(self, juego: str) -> list: ...

    @abstractmethod
    def guardar_pronostico(self, artefacto: dict) -> GuardadoLaboratorio: ...

    @abstractmethod
    def obtener_pronostico(self, clave: str) -> GuardadoLaboratorio | IlegibleLaboratorio | None: ...

    @abstractmethod
    def lineas(self, juego: str) -> list[str]: ...

    @abstractmethod
    def pronosticos(self, juego: str, linea: str) -> list: ...

    # Fase 3: modelos registrados (no abstractos para no obligar a otros almacenes)

    def guardar_modelo(self, artefacto: dict, estimador: bytes) -> GuardadoModelo:
        raise NotImplementedError

    def obtener_modelo(self, clave: str) -> GuardadoModelo | IlegibleModelo | None:
        raise NotImplementedError

    def modelos(self, juego: str) -> list:
        raise NotImplementedError

    def leer_estimador(self, guardado: GuardadoModelo) -> bytes:
        raise NotImplementedError

    def reservas_sin_modelo(self, juego: str) -> list[ReservaSinModelo]:
        raise NotImplementedError

    def huerfanos(self) -> list[str]:
        raise NotImplementedError
