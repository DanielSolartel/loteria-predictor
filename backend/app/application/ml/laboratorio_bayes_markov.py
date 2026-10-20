"""Estimadores congelables de Bayes jerárquico y Markov (CPU, sin sklearn).

Estas predictivas crudas preceden al ajuste de cardinalidad o normalización
comunes del laboratorio. Esas transformaciones no son actualizaciones de la
posterior. Ver ``docs/ml_cinco_familias.md`` para supuestos y límites.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.special import betaln, gammaln, logsumexp, roots_legendre

VERSION = "bayes-markov-1"
_IDS = {"bayes_jerarquico_binario", "bayes_jerarquico_pares", "markov_apariciones", "markov_pares"}


class InferenciaNoConvergente(ValueError):
    """La cuadratura agotó su presupuesto sin el refinamiento exigido."""


def _datos(X, y=None):
    X = np.asarray(X, dtype=float)
    if X.ndim != 2 or X.shape[1] < 6 or not np.all(np.isfinite(X)):
        raise ValueError("se requieren variables finitas con identidad y estado anterior")
    if y is None:
        return X
    y = np.asarray(y, dtype=float)
    if y.shape != (len(X),) or not len(y) or not np.all(np.isfinite(y)) or np.any(y != np.floor(y)):
        raise ValueError("etiquetas enteras finitas no vacías, una por fila")
    return X, y


def _congelar(v):
    v = np.asarray(v, dtype=float)
    v.setflags(write=False)
    return v


def _array(d, clave, forma, *, minimo=0):
    a = np.asarray(d[clave], dtype=float)
    if a.shape != forma or not np.all(np.isfinite(a)) or np.any(a < minimo):
        raise ValueError(f"{clave}: dimensión o contenido inválido")
    return _congelar(a)


def _identidades(d):
    ids = np.asarray(d["identidades"], dtype=float)
    if ids.ndim != 1 or len(ids) == 0 or not np.all(np.isfinite(ids)) or len(set(ids)) != len(ids):
        raise ValueError("identidades inválidas o repetidas")
    return _congelar(ids)


class _Descripcion:
    def componentes_de_inferencia(self):
        return [{"paso": "estimador", "clase": type(self).__name__, "detalle": self.descripcion}]

    def valores_globales(self, nombres):
        return {"motivo": "El estimador conserva " + self.descripcion +
                "; no define coeficientes ni importancias globales comparables de las variables.",
                "estimador": type(self).__name__}


class BayesJerarquicoBinario(_Descripcion):
    """Posterior Beta-Beta-Bernoulli integrada en una dimensión (μ)."""

    descripcion = "momentos de la posterior jerárquica Beta-Beta-Bernoulli congelada"
    classes_ = np.asarray([0, 1])

    def __init__(self, universo=43, kappa=20.0, tolerancia=1e-9, max_nodos=512):
        self.universo = int(universo)
        self.kappa = float(kappa)
        self.tolerancia = float(tolerancia)
        self.max_nodos = int(max_nodos)
        if not self.universo > 5 or not math.isfinite(self.kappa) or not self.kappa > 0 or not 0 < self.tolerancia < 1 or self.max_nodos not in (32, 64, 128, 256, 512):
            raise ValueError("hiperparámetros de cuadratura/prior inválidos")

    def fit(self, X, y):
        X, y = _datos(X, y)
        if np.any((y != 0) & (y != 1)):
            raise ValueError("Bayes numérico requiere apariciones 0/1")
        self.identidades = _congelar(np.unique(X[:, 0]))
        s = np.asarray([y[X[:, 0] == c].sum() for c in self.identidades])
        n = np.asarray([np.count_nonzero(X[:, 0] == c) for c in self.identidades])
        self.exitos, self.ensayos = _congelar(s), _congelar(n)
        anterior = None
        error = math.inf
        for nodos in (32, 64, 128, 256, 512):
            if nodos > self.max_nodos:
                break
            z, w = roots_legendre(nodos)
            mu, w = (z + 1) / 2, w / 2
            a, b = self.kappa * mu[:, None], self.kappa * (1 - mu[:, None])
            lp = 4 * np.log(mu) + (self.universo - 6) * np.log1p(-mu)
            lp += (betaln(a + s, b + n - s) - betaln(a, b)).sum(axis=1)
            lw = lp + np.log(w)
            masa = np.exp(lw - logsumexp(lw))
            media = (a + s) / (n + self.kappa)
            segundo = (a + s) * (a + s + 1) / ((n + self.kappa) * (n + self.kappa + 1))
            momentos = np.r_[masa @ mu, masa @ (mu * mu), masa @ media, masa @ segundo]
            if anterior is not None:
                error = float(np.max(np.abs(momentos - anterior)))
                if error <= self.tolerancia:
                    break
            anterior = momentos
        else:
            pass
        if anterior is None or not math.isfinite(error) or error > self.tolerancia:
            raise InferenciaNoConvergente(f"cuadratura sin refinamiento: nodos={nodos}, error={error!r}")
        m = len(self.identidades)
        self.media_mu, self.segundo_mu = map(float, momentos[:2])
        self.medias = _congelar(momentos[2:2 + m])
        self.segundos = _congelar(momentos[2 + m:])
        self.diagnostico = {"metodo": "Gauss-Legendre en logaritmos", "inferencia": "cuadratura determinista aproximada",
                            "nodos": nodos, "error_refinamiento": error, "tolerancia": self.tolerancia,
                            "convergio": True, "max_nodos": self.max_nodos}
        self._indice = {c: i for i, c in enumerate(self.identidades)}
        return self

    def predict_proba(self, X):
        X = _datos(X)
        p = np.asarray([self.medias[self._indice[c]] if c in self._indice else self.media_mu for c in X[:, 0]])
        return np.column_stack([1 - p, p])

    def to_dict(self):
        return {"version": VERSION, "clase": type(self).__name__, "universo": self.universo,
                "kappa": self.kappa, "tolerancia": self.tolerancia, "max_nodos": self.max_nodos,
                "identidades": self.identidades.tolist(), "exitos": self.exitos.tolist(),
                "ensayos": self.ensayos.tolist(), "medias": self.medias.tolist(), "segundos": self.segundos.tolist(),
                "media_mu": self.media_mu, "segundo_mu": self.segundo_mu, "diagnostico": self.diagnostico}

    @classmethod
    def from_dict(cls, d):
        o = cls(d["universo"], d["kappa"], d["tolerancia"], d["max_nodos"])
        o.identidades = _identidades(d)
        m = len(o.identidades)
        for k in ("exitos", "ensayos", "medias", "segundos"):
            setattr(o, k, _array(d, k, (m,)))
        o.media_mu, o.segundo_mu = float(d["media_mu"]), float(d["segundo_mu"])
        if np.any(o.exitos > o.ensayos) or np.any(o.medias >= 1) or np.any(o.medias <= 0) or np.any(o.segundos > o.medias + 1e-12) or np.any(o.segundos < o.medias ** 2 - 1e-12):
            raise ValueError("momentos o cuentas posteriores incoherentes")
        if not 0 < o.media_mu < 1 or not o.media_mu ** 2 <= o.segundo_mu <= o.media_mu:
            raise ValueError("momentos de μ inválidos")
        o.diagnostico = dict(d["diagnostico"])
        if o.diagnostico.get("convergio") is not True or o.diagnostico.get("error_refinamiento", math.inf) > o.tolerancia:
            raise ValueError("posterior sin diagnóstico de convergencia")
        o._indice = {c: i for i, c in enumerate(o.identidades)}
        return o


class BayesJerarquicoPares(_Descripcion):
    """Dos niveles Dirichlet conjugados: color y número condicionado a color."""

    descripcion = "posteriores Dirichlet de colores y números por color congeladas, con reserva OTROS"

    def __init__(self, candidatos=None):
        self.candidatos_de_ajuste = candidatos

    def fit(self, X, y):
        X, y = _datos(X, y)
        if np.any(y < 0) or np.any(y > 6) or self.candidatos_de_ajuste is None or len(self.candidatos_de_ajuste) != len(X):
            raise ValueError("ColorLoto necesita conteos 0..6 e identidad de cada par")
        pares = [(int(n), str(c)) for n, c in self.candidatos_de_ajuste]
        if any(not 1 <= n <= 7 or not c for n, c in pares):
            raise ValueError("par de ColorLoto inválido")
        self.colores = tuple(sorted({c for _, c in pares}))
        ix = {c: i for i, c in enumerate(self.colores)}
        cuentas = np.zeros((len(self.colores) + 1, 7))
        ident = {}
        for identidad, par, cuenta in zip(X[:, 0], pares, y):
            n, c = par
            if identidad in ident and ident[identidad] != (n, c):
                raise ValueError("colisión de identidades de pares")
            ident[identidad] = (n, c)
            cuentas[ix[c], n - 1] += cuenta
        self.identidades = _congelar(sorted(ident))
        self.pares = tuple(ident[c] for c in self.identidades)
        self.cuentas = _congelar(cuentas)
        self.alfa_color = _congelar(1 + cuentas.sum(axis=1))
        self.beta_numero = _congelar(1 + cuentas)
        self.diagnostico = {"metodo": "conjugación Dirichlet en dos niveles", "inferencia": "exacta",
                            "convergio": True, "reserva_otros": True}
        self._preparar()
        self.candidatos_de_ajuste = None
        return self

    def _preparar(self):
        self._color = {c: i for i, c in enumerate(self.colores)}
        self._indice = {c: i for i, c in enumerate(self.identidades)}
        self._medias_color = _congelar(self.alfa_color / self.alfa_color.sum())
        self._medias_numero = _congelar(self.beta_numero / self.beta_numero.sum(axis=1, keepdims=True))

    def predict(self, X):
        X = _datos(X)
        desconocidos = {c for c in X[:, 0] if c not in self._indice}
        reserva = self._medias_color[-1] / max(1, len(desconocidos))
        salida = []
        for identidad in X[:, 0]:
            if identidad not in self._indice:
                salida.append(6 * reserva)
            else:
                n, color = self.pares[self._indice[identidad]]
                c = self._color[color]
                salida.append(6 * self._medias_color[c] * self._medias_numero[c, n - 1])
        return np.asarray(salida)

    def predict_para_objetivos(self, X, posiciones):
        X = _datos(X)
        posiciones = np.asarray(posiciones)
        if posiciones.shape != (len(X),):
            raise ValueError("una posición por fila")
        p = np.empty(len(X))
        for objetivo in np.unique(posiciones):
            mascara = posiciones == objetivo
            p[mascara] = self.predict(X[mascara])
        return p

    def log_predictiva_conjunta(self, pares):
        """Log probabilidad del multiconjunto integrado, no la de Carteras.

        Se integra q y cada r; incluye el coeficiente multinomial. El
        contraste usa colores conocidos. Un único color nuevo se representa
        mediante OTROS; distinguir varios colores nuevos no está identificado.
        """
        pares = tuple(pares)
        cuentas = np.zeros_like(self.beta_numero)
        nuevos = {c for _, c in pares if c not in self._color}
        if len(nuevos) > 1:
            raise ValueError("la predictiva conjunta distingue como máximo un color OTROS")
        for n, c in pares:
            if not 1 <= int(n) <= 7:
                raise ValueError("número fuera de 1..7")
            cuentas[self._color.get(c, len(self.colores)), int(n) - 1] += 1
        n_color = cuentas.sum(axis=1)
        def log_beta(v):
            return gammaln(v).sum() - gammaln(v.sum())
        valor = gammaln(cuentas.sum() + 1) - gammaln(cuentas + 1).sum()
        valor += log_beta(self.alfa_color + n_color) - log_beta(self.alfa_color)
        valor += sum(log_beta(b + n) - log_beta(b) for b, n in zip(self.beta_numero, cuentas))
        return float(valor)

    def to_dict(self):
        return {"version": VERSION, "clase": type(self).__name__, "colores": list(self.colores),
                "identidades": self.identidades.tolist(), "pares": [list(p) for p in self.pares],
                "cuentas": self.cuentas.tolist(), "alfa_color": self.alfa_color.tolist(),
                "beta_numero": self.beta_numero.tolist(), "diagnostico": self.diagnostico}

    @classmethod
    def from_dict(cls, d):
        o = cls()
        o.colores = tuple(d["colores"])
        if not o.colores or any(not isinstance(c, str) or not c for c in o.colores) or tuple(sorted(set(o.colores))) != o.colores:
            raise ValueError("paleta posterior inválida")
        o.identidades = _identidades(d)
        o.pares = tuple((int(n), str(c)) for n, c in d["pares"])
        if len(o.pares) != len(o.identidades) or len(set(o.pares)) != len(o.pares) or any(not 1 <= n <= 7 or c not in o.colores for n, c in o.pares):
            raise ValueError("identidad de pares inválida")
        forma = (len(o.colores) + 1, 7)
        o.cuentas = _array(d, "cuentas", forma)
        o.alfa_color = _array(d, "alfa_color", (len(o.colores) + 1,), minimo=1)
        o.beta_numero = _array(d, "beta_numero", forma, minimo=1)
        if not np.array_equal(o.beta_numero, 1 + o.cuentas) or not np.array_equal(o.alfa_color, 1 + o.cuentas.sum(axis=1)) or np.any(o.cuentas[-1] != 0):
            raise ValueError("posterior Dirichlet incoherente con las cuentas")
        o.diagnostico = dict(d["diagnostico"])
        if o.diagnostico.get("convergio") is not True or o.diagnostico.get("inferencia") != "exacta":
            raise ValueError("diagnóstico conjugado inválido")
        o._preparar()
        return o


class MarkovApariciones(_Descripcion):
    """Una matriz dirigida por candidato, posterior Dirichlet por fila."""

    descripcion = "cuentas de transiciones dirigidas y medias posteriores Dirichlet congeladas"
    classes_ = np.asarray([0, 1])

    def __init__(self, universo=43, fuerza=10.0):
        self.universo, self.fuerza = int(universo), float(fuerza)
        self.estados = 2
        self.p = 5 / self.universo
        if self.universo <= 5 or not math.isfinite(self.fuerza) or self.fuerza <= 0:
            raise ValueError("prior Markov inválido")

    def fit(self, X, y):
        X, y = _datos(X, y)
        previo = X[:, 5]
        if np.any(y < 0) or np.any(y >= self.estados) or np.any(previo != np.floor(previo)) or np.any(previo < 0) or np.any(previo >= self.estados):
            raise ValueError("estado Markov de ajuste fuera del espacio declarado")
        self.identidades = _congelar(np.unique(X[:, 0]))
        self._indice = {c: i for i, c in enumerate(self.identidades)}
        cuentas = np.zeros((len(self.identidades), self.estados, self.estados))
        for c, a, b in zip(X[:, 0], previo.astype(int), y.astype(int)):
            cuentas[self._indice[c], a, b] += 1
        self.cuentas = _congelar(cuentas)
        self.prior = _congelar([math.comb(self.estados - 1, k) * self.p ** k * (1 - self.p) ** (self.estados - 1 - k)
                               for k in range(self.estados)])
        total = cuentas + self.fuerza * self.prior
        self.transiciones = _congelar(total / total.sum(axis=2, keepdims=True))
        self.diagnostico = {"metodo": "media posterior Dirichlet por fila de transición", "orden": 1,
                            "orientacion": "estado_anterior_X5 -> objetivo_y", "convergio": True}
        return self

    def _medias(self, X):
        X = _datos(X)
        valores = np.arange(self.estados)
        previo = float(self.prior @ valores)
        salida = []
        for identidad, a in zip(X[:, 0], X[:, 5]):
            if identidad not in self._indice or a != math.floor(a) or not 0 <= a < self.estados:
                salida.append(previo)
            else:
                salida.append(float(self.transiciones[self._indice[identidad], int(a)] @ valores))
        return np.asarray(salida)

    def predict_proba(self, X):
        p = self._medias(X)
        return np.column_stack([1 - p, p])

    def to_dict(self):
        return {"version": VERSION, "clase": type(self).__name__, "universo": self.universo, "fuerza": self.fuerza,
                "estados": self.estados, "p": self.p, "identidades": self.identidades.tolist(),
                "cuentas": self.cuentas.tolist(), "prior": self.prior.tolist(),
                "transiciones": self.transiciones.tolist(), "diagnostico": self.diagnostico}

    @classmethod
    def from_dict(cls, d):
        o = cls(d["universo"], d["fuerza"])
        if d["estados"] != o.estados or d["p"] != o.p:
            raise ValueError("espacio o centro del prior Markov incompatible")
        o.identidades = _identidades(d)
        forma = (len(o.identidades), o.estados, o.estados)
        o.cuentas = _array(d, "cuentas", forma)
        o.prior = _array(d, "prior", (o.estados,))
        esperado = np.asarray([math.comb(o.estados - 1, k) * o.p ** k * (1 - o.p) ** (o.estados - 1 - k)
                               for k in range(o.estados)])
        o.transiciones = _array(d, "transiciones", forma)
        total = o.cuentas + o.fuerza * esperado
        if not np.array_equal(o.prior, esperado) or not np.allclose(o.transiciones, total / total.sum(axis=2, keepdims=True), rtol=0, atol=1e-14):
            raise ValueError("transiciones incompatibles con prior y cuentas")
        o._indice = {c: i for i, c in enumerate(o.identidades)}
        o.diagnostico = dict(d["diagnostico"])
        if o.diagnostico.get("orden") != 1 or o.diagnostico.get("convergio") is not True:
            raise ValueError("diagnóstico Markov inválido")
        return o


class MarkovPares(MarkovApariciones):
    """Estados 0..6 y prior Binomial(6,1/K), con multiplicidad."""

    def __init__(self, universo=7, fuerza=10.0):
        self.universo, self.fuerza = int(universo), float(fuerza)
        self.estados = 7
        if self.universo < 7 or not math.isfinite(self.fuerza) or self.fuerza <= 0:
            raise ValueError("prior Markov de pares inválido")
        self.p = 1 / self.universo

    def predict(self, X):
        return self._medias(X)

    def predict_para_objetivos(self, X, posiciones):
        if np.asarray(posiciones).shape != (len(X),):
            raise ValueError("una posición por fila")
        return self.predict(X)


def ajustar_bayes_markov(candidato_id, X, y, *, reglas, candidatos=None, parametros=None):
    """Construye y ajusta únicamente con el bloque causal recibido del core."""
    parametros = parametros or {}
    if candidato_id not in _IDS:
        raise ValueError("familia Bayes/Markov desconocida")
    if candidato_id == "bayes_jerarquico_binario":
        modelo = BayesJerarquicoBinario(len(reglas.candidatos), parametros.get("kappa", 20),
                                       parametros.get("tolerancia", 1e-9), parametros.get("max_nodos", 512))
    elif candidato_id == "bayes_jerarquico_pares":
        modelo = BayesJerarquicoPares(candidatos)
    elif candidato_id == "markov_apariciones":
        modelo = MarkovApariciones(len(reglas.candidatos), parametros.get("fuerza", 10))
    else:
        modelo = MarkovPares(len(set(map(float, np.asarray(X)[:, 0]))), parametros.get("fuerza", 10))
    return modelo.fit(X, y)


def deserializar_bayes_markov(d):
    """Carga sólo estas cuatro estructuras explícitas; nunca llama a fit."""
    clases = {c.__name__: c for c in (BayesJerarquicoBinario, BayesJerarquicoPares, MarkovApariciones, MarkovPares)}
    if not isinstance(d, dict) or d.get("version") != VERSION or d.get("clase") not in clases:
        raise ValueError("versión o clase Bayes/Markov incompatible")
    try:
        return clases[d["clase"]].from_dict(d)
    except (KeyError, TypeError, OverflowError) as error:
        raise ValueError("estructura Bayes/Markov incompleta o inválida") from error


def validar_receta(d, receta, identidad):
    """Contrasta estado congelado, receta y reglas sin ajustar ni integrar.

    El registro comprueba antes el manifiesto y la identidad exterior. Aquí
    se comprueban el soporte y los hiperparámetros que los formatos explícitos
    sí conservan. Los momentos se contrastan algebraicamente; no se vuelve a
    ejecutar cuadratura ni se estima ninguna transición al cargar.
    """
    from app.application.ml import laboratorio_variables as lv

    try:
        identificador, p = receta["id"], receta["parametros"]
        reglas = lv.REGLAS[identidad["juego"]]
        paleta = identidad["paleta_del_corte"]
        if reglas.colores and (not paleta or paleta != sorted(set(paleta)) or
                               any(not isinstance(c, str) or not c for c in paleta)):
            raise ValueError("paleta incompatible con reglas del juego")
        pares = sorted((lv.codigo_de_par(n, c), (n, c)) for c in paleta for n in reglas.candidatos) if reglas.colores else []
        soporte = [i for i, _ in pares] if reglas.colores else list(reglas.candidatos)
        ids = _identidades(d)
        if ids.tolist() != soporte:
            raise ValueError("soporte incompatible con reglas y paleta del corte")
        objetivos = identidad["periodo"]["sorteos"] - lv.CALENTAMIENTO
        diagnostico = d["diagnostico"]
        if identificador == "bayes_jerarquico_binario":
            for clave, esperado in (("universo", len(soporte)), ("kappa", p["kappa"]),
                                     ("tolerancia", p["tolerancia"]), ("max_nodos", p["max_nodos"])):
                if d[clave] != esperado:
                    raise ValueError("hiperparámetros Bayes distintos de receta o reglas")
            s = _array(d, "exitos", (len(ids),))
            n = _array(d, "ensayos", (len(ids),))
            if np.any(n != objetivos) or np.any(s != np.floor(s)) or np.any(s > n) or s.sum() != reglas.cantidad * objetivos:
                raise ValueError("cuentas Bayes incompatibles con reglas y periodo")
            k, mu, mu2 = d["kappa"], d["media_mu"], d["segundo_mu"]
            media = (s + k * mu) / (n + k)
            segundo = (s * (s + 1) + k * (2*s + 1) * mu + k*k * mu2) / ((n+k)*(n+k+1))
            if not np.allclose(_array(d, "medias", (len(ids),)), media, rtol=0, atol=1e-12) or \
                    not np.allclose(_array(d, "segundos", (len(ids),)), segundo, rtol=0, atol=1e-12):
                raise ValueError("momentos incompatibles con parámetros y cuentas de la receta")
            error = diagnostico["error_refinamiento"]
            if diagnostico["metodo"] != "Gauss-Legendre en logaritmos" or \
                    diagnostico["inferencia"] != "cuadratura determinista aproximada" or \
                    diagnostico["max_nodos"] != p["max_nodos"] or diagnostico["tolerancia"] != p["tolerancia"] or \
                    diagnostico["nodos"] not in (64, 128, 256, 512) or diagnostico["nodos"] > p["max_nodos"] or \
                    not math.isfinite(error) or not 0 <= error <= p["tolerancia"]:
                raise ValueError("diagnóstico incompatible con presupuesto de la receta Bayes")
        elif identificador == "bayes_jerarquico_pares":
            if p != {"prior_colores": 1.0, "prior_numeros": 1.0, "reserva_otros": True} or \
                    d["colores"] != paleta or d["pares"] != [list(par) for _, par in pares]:
                raise ValueError("soporte o prior de pares incompatible con receta y reglas")
            cuentas = _array(d, "cuentas", (len(paleta) + 1, len(reglas.candidatos)))
            if np.any(cuentas != np.floor(cuentas)) or cuentas.sum() != reglas.cantidad * objetivos:
                raise ValueError("cuentas Dirichlet incompatibles con reglas y periodo")
            # El lector de la estructura contrasta además alfa=1+suma(cuentas),
            # beta=1+cuentas y reserva OTROS vacía, sin inferencia nueva.
        elif identificador in ("markov_apariciones", "markov_pares"):
            estados = reglas.cantidad + 1 if reglas.colores else 2
            universo = len(soporte)
            centro = (1 if reglas.colores else reglas.cantidad) / universo
            if p["orden"] != 1 or d["universo"] != universo or d["fuerza"] != p["fuerza"] or \
                    d["estados"] != estados or d["p"] != centro:
                raise ValueError("hiperparámetros Markov distintos de receta o reglas")
            cuentas = _array(d, "cuentas", (len(ids), estados, estados))
            if np.any(cuentas != np.floor(cuentas)) or np.any(cuentas.sum(axis=(1, 2)) != objetivos):
                raise ValueError("cuentas Markov incompatibles con reglas y periodo")
            if diagnostico["orden"] != p["orden"] or diagnostico["orientacion"] != "estado_anterior_X5 -> objetivo_y":
                raise ValueError("orientación u orden Markov distintos de la receta")
        else:
            raise ValueError("receta Bayes/Markov desconocida")
        if diagnostico.get("convergio") is not True:
            raise ValueError("diagnóstico sin convergencia de la receta")
    except (KeyError, TypeError, IndexError, OverflowError) as error:
        raise ValueError("estado incompatible con receta o reglas Bayes/Markov") from error
