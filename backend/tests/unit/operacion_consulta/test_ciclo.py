from __future__ import annotations

import copy

import pytest

from despliegue.operacion_consulta.ciclo import Motor
from despliegue.operacion_consulta.modelo import Plan, Rechazo
from .conftest import Caida, Runtime, plan_de


def preparar(a, tmp):
    op = Runtime(a)
    m = Motor(a, lambda _: op, reloj=op.reloj)
    p, q = plan_de(tmp, 1), plan_de(tmp, 2)
    assert m.activar(p)["codigo"] == 0
    op.llamadas.clear()
    return m, op, p, q


def test_activa_par_independiente_y_conserva_datos(almacen, tmp_path):
    m, op, p, q = preparar(almacen, tmp_path)
    anteriores = copy.deepcopy(op.recursos)
    assert m.activar(q)["codigo"] == 0
    assert op.proxy == q.id and op.parejas == {q.id}
    assert op.recursos[p.id] == anteriores[p.id]
    assert [x[0] for x in op.llamadas] == ["preparar", "arrancar", "validar", "cerrar", "drenar", "detener",
                                         "publicar", "abrir", "sonda"]
    e = almacen.leer("estado.json")
    assert e["activa"] == q.id and e["anterior"] == p.id and e["pendiente"] is None
    assert e["contadores"]["activadas"] == 2


@pytest.mark.parametrize("fase", ["preparar", "arrancar", "validar", "cerrar", "drenar", "detener", "publicar", "abrir", "sonda"])
@pytest.mark.parametrize("momento", ["antes", "despues"])
def test_fallo_en_cada_efecto_revierte_sin_borrar(almacen, tmp_path, fase, momento):
    m, op, p, q = preparar(almacen, tmp_path)
    afectado = p if fase in ("cerrar", "drenar", "detener") else q
    op.fallo = (fase, afectado.id, momento)
    r = m.activar(q)
    assert r["codigo"] == 1 and r["resultado"] == "revertida"
    assert op.proxy == p.id and not op.cerrado and op.parejas == {p.id}
    assert almacen.leer("estado.json")["activa"] == p.id
    assert almacen.leer("estado.json")["pendiente"] is None
    assert p.id in op.recursos
    assert "SECRETO" not in str(r)
    if fase in ("preparar", "arrancar", "validar"):
        assert not any(n == "cerrar" and k == p.id for n, k in op.llamadas)


@pytest.mark.parametrize("fase", ["preparar", "arrancar", "validar", "cerrar", "drenar", "detener", "publicar", "abrir", "sonda"])
def test_caida_recupera_diario_anterior_al_efecto(almacen, tmp_path, fase):
    m, op, p, q = preparar(almacen, tmp_path)
    op.caida = (fase, (p if fase in ("cerrar", "drenar", "detener") else q).id)
    with pytest.raises(Caida):
        m.activar(q)
    assert almacen.leer("estado.json")["pendiente"]["fase"] == fase
    with pytest.raises(Rechazo, match="recuperacion_pendiente"):
        m.activar(q)
    # Motor nuevo, mismo estado persistido y procesos supervivientes.
    m2 = Motor(almacen, lambda _: op, reloj=op.reloj)
    assert m2.recuperar()["codigo"] == 0
    assert op.proxy == p.id and not op.cerrado and op.parejas == {p.id}
    assert almacen.leer("estado.json")["pendiente"] is None
    assert m2.recuperar()["resultado"] == "sin_transaccion"


def test_reversion_fallida_conserva_diario_y_reintento(almacen, tmp_path):
    m, op, p, q = preparar(almacen, tmp_path)
    def fallo(nombre, plan):
        if nombre == "sonda" and plan == q:
            op.fallo = ("arrancar", p.id, "antes")
            raise RuntimeError()
    op.antes = fallo
    assert m.activar(q)["codigo"] == 4
    e = almacen.leer("estado.json")
    assert e["pendiente"] is not None and e["acceso"] == "sin_verificar"
    op.antes = None
    assert m.recuperar()["codigo"] == 0
    assert op.proxy == p.id and not op.cerrado


def test_plazo_superado_no_se_convierte_en_exito(almacen, tmp_path):
    m, op, p, q = preparar(almacen, tmp_path)
    op.gastar["drenar"] = 121
    r = m.activar(q)
    assert r["codigo"] == 1 and r["presupuesto_excedido"]
    assert op.proxy == p.id


def test_idempotencia_no_promete_salud(almacen, tmp_path):
    m, op, p, _ = preparar(almacen, tmp_path)
    assert m.activar(p) == {"codigo": 0, "resultado": "ya_registrada", "salud_comprobada": False}
    assert not op.llamadas


def test_reversion_explicita_es_otra_transaccion(almacen, tmp_path):
    m, op, p, q = preparar(almacen, tmp_path)
    assert m.activar(q)["codigo"] == 0
    assert m.revertir()["codigo"] == 0
    assert op.proxy == p.id
    assert almacen.leer("estado.json")["anterior"] == q.id


def test_cambio_de_activa_no_revierte_una_lectura_vieja(almacen, tmp_path):
    m, op, p, q = preparar(almacen, tmp_path)
    assert m.activar(q)["codigo"] == 0
    op.llamadas.clear()
    with pytest.raises(Rechazo, match="activa_cambio"):
        m.activar(p, activa_esperada=p.id)
    assert not op.llamadas


@pytest.mark.parametrize("campo,valor", [("puerto", 18444), ("host", "otro.ensayo.invalid"),
                                         ("red_interna", "172.28.2.0/24"), ("ip_datos_api", "172.29.0.21")])
def test_candidato_incompatible_se_rechaza_antes_de_efectos(almacen, tmp_path, campo, valor):
    m, op, p, q = preparar(almacen, tmp_path)
    d = q.objeto()
    d[campo] = valor
    with pytest.raises(Rechazo):
        m.activar(Plan.de(d))
    assert not op.llamadas


def test_fallo_primera_activacion_queda_cerrado(almacen, plan):
    op = Runtime(almacen)
    op.fallo = ("sonda", plan.id, "antes")
    assert Motor(almacen, lambda _: op, reloj=op.reloj).activar(plan)["codigo"] == 1
    e = almacen.leer("estado.json")
    assert e["activa"] is None and e["acceso"] == "cerrado" and op.proxy is None


def test_fallo_al_persistir_commit_no_pierde_transaccion(almacen, tmp_path, monkeypatch):
    m, op, p, q = preparar(almacen, tmp_path)
    original = almacen.escribir
    fallar = True
    def escribir(nombre, valor):
        nonlocal fallar
        if nombre == "estado.json" and valor["activa"] == q.id and fallar:
            fallar = False
            raise OSError("disco lleno sintético")
        return original(nombre, valor)
    monkeypatch.setattr(almacen, "escribir", escribir)
    assert m.activar(q)["codigo"] == 1
    assert op.proxy == p.id and not op.cerrado
    assert almacen.leer("estado.json")["activa"] == p.id


def test_disco_lleno_no_impide_reversion_fisica(almacen, tmp_path, monkeypatch):
    m, op, p, q = preparar(almacen, tmp_path)
    original = almacen.escribir
    lleno = False
    def antes(nombre, plan):
        nonlocal lleno
        if nombre == "drenar":
            lleno = True
            op.diario_en_emergencia = True
    def escribir(nombre, valor):
        if lleno:
            raise OSError("sin espacio")
        original(nombre, valor)
    op.antes = antes
    monkeypatch.setattr(almacen, "escribir", escribir)
    assert m.activar(q)["codigo"] == 4  # no puede certificar el cierre del diario
    assert op.proxy == p.id and not op.cerrado
    assert almacen.leer("estado.json")["pendiente"] is not None
