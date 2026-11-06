from __future__ import annotations

import sys
from pathlib import Path

# El operador vive fuera de app/ para conservar la huella de las generaciones E10.4.
RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ))

import pytest

from despliegue.operacion_consulta.estado import Almacen
from despliegue.operacion_consulta.modelo import Plan


def plan_de(raiz: Path, numero: int = 1) -> Plan:
    gid = f"{numero:032x}"
    return Plan.de({"formato": "operacion-consulta/1", "modo": "ensayo", "generacion": gid,
                    "manifiesto_sha256": "a" * 64, "huella_app": "b" * 64,
                    "imagen_api": "prueba/api@sha256:" + "c" * 64,
                    "imagen_pasarela": "prueba/pasarela@sha256:" + "d" * 64,
                    "imagen_proxy": "prueba/proxy@sha256:" + "e" * 64,
                    "host": "consulta.ensayo.invalid", "puerto": 18443,
                    "red_interna": f"172.28.{numero * 2}.0/24", "red_servicio": f"172.28.{numero * 2 + 1}.0/24",
                    "red_datos": "e105ensayodatos12345678", "ip_datos_api": f"172.29.0.{20 + numero}",
                    "directorio_generacion": str(raiz / "generaciones" / gid),
                    "clave_publica": str(raiz / "firma.pub"), "secretos": str(raiz / "secretos"),
                    "pki_proxy": str(raiz / "pki-proxy"), "pki_sonda": str(raiz / "pki-sonda")})


@pytest.fixture
def plan(tmp_path):
    return plan_de(tmp_path)


@pytest.fixture
def almacen(tmp_path):
    with Almacen(tmp_path / "control", crear=True) as a:
        yield a


class Caida(BaseException):
    """Simula morir entre un efecto y la escritura posterior del diario."""


class Reloj:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class Runtime:
    """Sustituto de procesos; no es evidencia de Docker, nginx, PostgreSQL o TLS."""
    def __init__(self, a, reloj=None):
        self.a, self.reloj = a, reloj or Reloj()
        self.llamadas, self.recursos, self.parejas = [], {}, set()
        self.proxy, self.cerrado, self.en_curso = None, True, 0
        self.fallo, self.caida, self.gastar = None, None, {}
        self.antes = None
        self.diario_en_emergencia = False

    def _paso(self, nombre, p, efecto):
        self.llamadas.append((nombre, p.id))
        diario = self.a.leer("estado.json")["pendiente"]
        assert diario is not None
        if not self.diario_en_emergencia:
            assert diario["fase"] == nombre or diario["fase"] == "revertir"
        if self.antes:
            self.antes(nombre, p)
        if self.fallo == (nombre, p.id, "antes"):
            self.fallo = None
            raise RuntimeError("fallo sintético; no divulgar SECRETO-SINTETICO")
        efecto()
        self.reloj.t += self.gastar.get(nombre, 0.001)
        if self.fallo == (nombre, p.id, "despues"):
            self.fallo = None
            raise RuntimeError("fallo sintético")
        if self.caida == (nombre, p.id):
            self.caida = None
            raise Caida()

    def preparar(self, p, plazo):
        self._paso("preparar", p, lambda: self.recursos.setdefault(p.id, ("base-" + p.generacion, "archivos-" + p.generacion)))

    def arrancar(self, p, plazo):
        self._paso("arrancar", p, lambda: self.parejas.add(p.id))

    def validar(self, p, plazo):
        self._paso("validar", p, lambda: self._exigir(p.id in self.parejas))

    @staticmethod
    def _exigir(valor):
        assert valor

    def mantenimiento(self, p, cerrar, plazo):
        def efecto():
            if self.proxy == p.id:
                self.cerrado = cerrar
            elif not cerrar:
                raise RuntimeError("proxy ausente")
        self._paso("cerrar" if cerrar else "abrir", p, efecto)

    def drenar(self, p, plazo):
        if self.proxy != p.id:
            return
        def efecto():
            assert self.cerrado
            assert self.en_curso == 0
        self._paso("drenar", p, efecto)

    def detener(self, p, plazo):
        def efecto():
            assert not (self.proxy == p.id and self.en_curso)
            self.parejas.discard(p.id)
            if self.proxy == p.id:
                self.proxy, self.cerrado = None, True
        self._paso("detener", p, efecto)

    def publicar(self, p, plazo):
        def efecto():
            assert p.id in self.parejas
            assert self.proxy in (None, p.id)
            self.proxy, self.cerrado = p.id, True
        self._paso("publicar", p, efecto)

    def sonda(self, p, plazo):
        self._paso("sonda", p, lambda: self._exigir(self.proxy == p.id and not self.cerrado))
