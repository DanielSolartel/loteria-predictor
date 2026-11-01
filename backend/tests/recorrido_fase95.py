"""9.5: API/pasarela/SPA reales, descargas locales y PDF con datos SINTÉTICOS.

No consulta PostgreSQL, servicios operativos ni configura el navegador global.
El ejecutable externo (--navegador) sólo se emplea en este ensayo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import zlib
import xml.etree.ElementTree as ET
from contextlib import ExitStack
from pathlib import Path

from tests import recorrido_fase9 as r9
from tests.unit.fixtures_fase4 import arbol

BACKEND, FRONTEND = r9.BACKEND, r9.FRONTEND
ESCENARIOS = ("normal", "vacio", "alterado", "incompatible", "cuota", "api_caida")


def _texto_pdf_portable(contenido: bytes) -> str:
    """Lee los mapas ToUnicode y operadores de texto de los PDF de Chromium.

    Comprobador acotado de estos PDF de ensayo, no lector general PDF. No usa
    software externo ni interpreta JavaScript. Un formato sin mapa se rechaza.
    """
    objetos = {int(n): cuerpo for n, cuerpo in re.findall(rb"(\d+) 0 obj\s*(.*?)\s*endobj", contenido, re.S)}

    def flujo(cuerpo):
        m = re.search(rb"stream\r?\n(.*?)\r?\nendstream", cuerpo, re.S)
        if not m:
            return b""
        b = m[1]
        return zlib.decompress(b) if b"/FlateDecode" in cuerpo[:m.start()] else b

    mapas = {}
    for numero, cuerpo in objetos.items():
        ref = re.search(rb"/ToUnicode\s+(\d+) 0 R", cuerpo)
        if not ref:
            continue
        cmap = flujo(objetos[int(ref[1])])
        mapa = {}
        for grupo in re.findall(rb"beginbfchar(.*?)endbfchar", cmap, re.S):
            for a, b in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", grupo):
                mapa[a.decode().upper()] = bytes.fromhex(b.decode()).decode("utf-16-be")
        for grupo in re.findall(rb"beginbfrange(.*?)endbfrange", cmap, re.S):
            for a, b, c in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", grupo):
                inicio, fin, destino = int(a, 16), int(b, 16), int(c, 16)
                for i in range(inicio, fin+1):
                    mapa[f"{i:0{len(a)}X}"] = (destino+i-inicio).to_bytes(max(2, len(c)//2), "big").decode("utf-16-be")
            for a, b, lista in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*\[(.*?)\]", grupo, re.S):
                for i, c in enumerate(re.findall(rb"<([0-9A-Fa-f]+)>", lista)):
                    mapa[f"{int(a,16)+i:0{len(a)}X}"] = bytes.fromhex(c.decode()).decode("utf-16-be")
        if mapa:
            mapas[numero] = mapa
    recursos = {}
    for cuerpo in objetos.values():
        for nombre, numero in re.findall(rb"/(F\d+)\s+(\d+) 0 R", cuerpo):
            if int(numero) in mapas:
                recursos[nombre] = mapas[int(numero)]
    textos = []
    for cuerpo in objetos.values():
        stream = flujo(cuerpo)
        if b"BT" not in stream:
            continue
        fuente = None
        tokens = re.finditer(rb"/(F\d+)\s+[-.\d]+\s+Tf|<([0-9A-Fa-f]+)>\s*Tj|\[(.*?)\]\s*TJ", stream, re.S)
        for m in tokens:
            if m[1]:
                fuente = recursos.get(m[1])
                continue
            for hexadec in ([m[2]] if m[2] else re.findall(rb"<([0-9A-Fa-f]+)>", m[3] or b"")):
                if fuente is None:
                    continue
                h = hexadec.decode().upper()
                anchura = max(map(len, fuente))
                textos.append("".join(fuente.get(h[i:i+anchura], "�") for i in range(0, len(h), anchura)))
    if not textos:
        raise ValueError("PDF sin texto ToUnicode reconocido por el comprobador acotado")
    return " ".join(textos)


def _verificar_pdfs(salida: Path, *, exigir_matriz: bool = False) -> list[dict]:
    matriz = salida / "navegador" / "matriz-pdf.json"
    if not matriz.exists():
        if exigir_matriz:
            raise ValueError("Falta la matriz de doce PDF del escenario normal")
        return []
    filas = json.loads(matriz.read_text(encoding="utf-8"))
    formatos = {"carta-vertical": (612.0, 792.0), "carta-horizontal": (792.0, 612.0),
                "a4-vertical": (595.2756, 841.8898)}
    esperadas = {(j, f) for j in ("BALOTO", "BALOTO_REVANCHA", "MILOTO", "COLORLOTO") for f in formatos}
    parejas = [(f["juego"], f["formato"]) for f in filas]
    if len(set(parejas)) != len(parejas) or any(p not in esperadas for p in parejas):
        raise ValueError("La matriz PDF tiene identidades duplicadas o desconocidas")
    if exigir_matriz and (len(filas) != 12 or set(parejas) != esperadas):
        raise ValueError("La matriz normal debe contener cuatro juegos por tres formatos: doce PDF")
    resultados = []
    # Los mapas ToUnicode pueden conservar ligaduras tipográficas (ﬁ); son la
    # misma secuencia textual que fi. No se eliminan palabras ni se redondean datos.
    compacto = lambda s: re.sub(r"\s+", "", unicodedata.normalize("NFKC", s))
    for fila in filas:
        if fila["archivo"] != "pdf/" + fila["juego"] + "-" + fila["formato"] + ".pdf":
            raise ValueError("Ruta PDF no reconocida en la matriz sintética")
        textos = fila.get("textos_obligatorios")
        if not isinstance(textos, list) or not textos or any(not isinstance(t, str) or not t.strip() for t in textos):
            raise ValueError("Cada PDF requiere contenido textual esperado explícito y no vacío")
        ruta = salida / "navegador" / fila["archivo"]
        b = ruta.read_bytes()
        paginas = len(re.findall(rb"/Type\s*/Page\b", b))
        cajas = [list(map(float, valores.split())) for valores in re.findall(rb"/MediaBox\s*\[([^]]+)\]", b)]
        dimensiones = [(c[2] - c[0], c[3] - c[1]) for c in cajas if len(c) == 4]
        ancho_esperado, alto_esperado = formatos[fila["formato"]]
        # Chromium redondea A4 desde píxeles CSS: se admite como máximo 1,1 pt
        # frente al papel nominal, conservando dimensiones y orientación reales.
        dimensiones_validas = len(dimensiones) == paginas and paginas > 0 and all(
            abs(ancho - ancho_esperado) <= 1.1 and abs(alto - alto_esperado) <= 1.1
            for ancho, alto in dimensiones)
        texto = _texto_pdf_portable(b)
        # En Linux se contrasta además con Poppler, si ya está instalado; no se
        # instala nada y el comprobador portable sigue siendo reproducible.
        poppler = shutil.which("pdftotext")
        contraste = None
        posicion = None
        if poppler:
            # El orden del contenido conserva una celda completa; -layout
            # intercala las líneas de columnas vecinas cuando la tabla refluye.
            p = subprocess.run([poppler, "-raw", str(ruta), "-"], capture_output=True, check=False)
            if p.returncode != 0:
                raise RuntimeError("pdftotext no pudo leer el PDF sintético")
            contraste = p.stdout.decode("utf-8", "strict")
            bbox = subprocess.run([poppler, "-bbox", str(ruta), "-"], capture_output=True, check=False)
            if bbox.returncode != 0:
                raise RuntimeError("pdftotext no pudo comprobar posiciones del PDF sintético")
            dom = ET.fromstring(bbox.stdout)
            hojas = [e for e in dom.iter() if e.tag.rsplit("}", 1)[-1] == "page"]
            fuera, palabras, solapamientos_superbalota = [], 0, []
            solapes_linea, color_pegado = [], []
            for numero, hoja in enumerate(hojas, 1):
                ancho, alto = float(hoja.attrib["width"]), float(hoja.attrib["height"])
                palabras_hoja = [p for p in hoja.iter() if p.tag.rsplit("}", 1)[-1] == "word"]
                # F95-PDF-01: dos palabras de una misma línea no pueden ocupar el mismo espacio (texto de una
                # celda que invade la vecina), y el nombre de un color no puede quedar pegado a una cifra
                # (Poppler une en una palabra las cajas sin separación).
                cajas = [(p.text or "", *(float(p.attrib[k]) for k in ("xMin", "xMax", "yMin", "yMax"))) for p in palabras_hoja]
                for i, (ta, x0a, x1a, y0a, y1a) in enumerate(cajas):
                    if re.match(r"(?i)(amarillo|azul|blanco|negro|rojo|verde)[0-9+\-.]", ta):
                        color_pegado.append({"pagina": numero, "texto_sintetico": ta})
                    for tb, x0b, x1b, y0b, y1b in cajas[i + 1:]:
                        solape_y = min(y1a, y1b) - max(y0a, y0b)
                        solape_x = min(x1a, x1b) - max(x0a, x0b)
                        if solape_y > 0.5 * min(y1a - y0a, y1b - y0b) and solape_x > 0.5:
                            solapes_linea.append({"pagina": numero, "textos_sinteticos": [ta, tb], "solape_pt": round(solape_x, 3)})
                for etiqueta in palabras_hoja:
                    if (etiqueta.text or "").strip().lower() != "superbalota":
                        continue
                    for valor in palabras_hoja:
                        if not re.fullmatch(r"\d+", valor.text or ""):
                            continue
                        caja_etiqueta, caja_numero = etiqueta.attrib, valor.attrib
                        area = max(0.0, min(float(caja_etiqueta["xMax"]), float(caja_numero["xMax"])) - max(float(caja_etiqueta["xMin"]), float(caja_numero["xMin"]))) * max(
                            0.0, min(float(caja_etiqueta["yMax"]), float(caja_numero["yMax"])) - max(float(caja_etiqueta["yMin"]), float(caja_numero["yMin"])))
                        if area > 0.01:
                            solapamientos_superbalota.append({"pagina": numero, "numero_sintetico": valor.text, "area_pt2": area})
                for palabra in hoja.iter():
                    if palabra.tag.rsplit("}", 1)[-1] != "word":
                        continue
                    palabras += 1
                    caja = {k: float(palabra.attrib[k]) for k in ("xMin", "xMax", "yMin", "yMax")}
                    if (caja["xMin"] < -1 or caja["yMin"] < -1 or
                            caja["xMax"] > ancho+1 or caja["yMax"] > alto+1):
                        fuera.append({"pagina": numero, "texto_sintetico": palabra.text, **caja})
            posicion = {"paginas": len(hojas), "palabras": palabras,
                        "palabras_fuera_de_la_pagina": len(fuera), "ejemplos": fuera[:20],
                        "solapamientos_texto_superbalota_numeros": len(solapamientos_superbalota),
                        "ejemplos_solapamientos_superbalota": solapamientos_superbalota[:20],
                        "solapamientos_texto_misma_linea": len(solapes_linea), "ejemplos_solapamientos_misma_linea": solapes_linea[:20],
                        "colores_pegados_a_cifras": len(color_pegado), "ejemplos_colores_pegados": color_pegado[:20]}
        faltan = [s for s in fila["textos_obligatorios"] if compacto(s) not in compacto(texto)]
        faltan_poppler = [s for s in fila["textos_obligatorios"] if contraste is not None and compacto(s) not in compacto(contraste)]
        destino = ruta.with_suffix(".texto.txt")
        destino.write_text(texto + "\n", encoding="utf-8")
        resultados.append({**fila, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest(),
                           "paginas": paginas, "textos_ausentes": faltan,
                           "dimensiones_pt": dimensiones,
                           "papel_nominal_pt": [ancho_esperado, alto_esperado],
                           "tolerancia_dimension_pt": 1.1,
                           "dimensiones_y_orientacion_correctas": dimensiones_validas,
                           "contraste_poppler": poppler is not None,
                           "modo_poppler": "raw" if poppler else None,
                           "normalizacion_textual": "Unicode NFKC y espacios; contenido completo sin redondeo",
                           "posicion_palabras_poppler": posicion,
                           "textos_ausentes_poppler": faltan_poppler,
                           "ok": dimensiones_validas and not faltan and not faltan_poppler and
                           (posicion is None or posicion["paginas"] == paginas and
                            posicion["palabras"] > 0 and posicion["palabras_fuera_de_la_pagina"] == 0 and
                            posicion["solapamientos_texto_superbalota_numeros"] == 0 and
                            posicion["solapamientos_texto_misma_linea"] == 0 and posicion["colores_pegados_a_cifras"] == 0),
                           "revision_visual": "pendiente; extracción de texto no equivale a inspección visual"})
    return resultados


def resumen_impresion(salida: Path) -> dict:
    """F95-NAT-01: cuenta las comprobaciones de impresión por grupo, estado y resultado."""
    archivo = salida / "navegador" / "resultados.json"
    if not archivo.exists():
        return {"error": "Falta resultados.json del navegador", "grupos": {}}
    filas = json.loads(archivo.read_text(encoding="utf-8")).get("comprobaciones", [])
    grupos: dict[str, dict[str, int]] = {}
    for fila in filas:
        nombre = fila.get("nombre", "")
        for prefijo in ("imprimir-clic-real-", "imprimir-pdf-restaura-", "imprimir-control-negativo-",
                        "descargar-imprimir-sin-red-", "imprimir-sin-red-"):
            if nombre.startswith(prefijo):
                clave = f"{fila.get('estado')}:{fila.get('resultado', '-')}"
                grupo = grupos.setdefault(prefijo.rstrip("-"), {})
                grupo[clave] = grupo.get(clave, 0) + 1
    return {"error": None, "grupos": grupos}


def ejecutar(escenario: str, salida: Path, *, anchos: str, node: str, navegador: str | None = None, solo_pdf: bool = False,
             solo_impresion: bool = False) -> int:
    if solo_pdf and escenario != "normal":
        raise ValueError("--solo-pdf requiere el escenario normal")
    if solo_impresion and (escenario != "normal" or solo_pdf):
        raise ValueError("--solo-impresion requiere el escenario normal y excluye --solo-pdf")
    salida.mkdir(parents=True, exist_ok=False)
    registros = salida / "registros"
    registros.mkdir()
    dist = FRONTEND / "dist"
    if not (dist / "index.html").is_file():
        raise SystemExit("Falta frontend/dist; compilar antes de este ensayo")
    compilado_antes = arbol(dist)
    inicio = time.monotonic()
    clave = "f95canario-" + secrets.token_hex(24)
    huella = hashlib.sha256(clave.encode("ascii")).hexdigest()
    p_api, p_pasarela = r9.puerto_libre(), r9.puerto_libre()
    resultado = {"escenario": escenario, "alcance": "solo_pdf" if solo_pdf else "solo_impresion" if solo_impresion else "completo", "plataforma": sys.platform,
                 "python": sys.version.split()[0], "sustitutos": {
                     "api": "crear_app real; SQLite y artefactos sintéticos reales, no PostgreSQL",
                     "pasarela": "app.pasarela.aplicacion:app real", "spa": "frontend/dist compilado",
                     "intercepcion_http": False},
                 "fichas_por_minuto": 6 if escenario == "cuota" else 100000,
                 "spa_compilada": {"archivos": compilado_antes}}
    with ExitStack() as pila:
        raiz = Path(pila.enter_context(tempfile.TemporaryDirectory(prefix="f95 ensayo ")))
        datos = raiz / "api"
        entorno_api = r9.entorno_minimo(
            F95_RAIZ=str(datos), F95_ESTADO="normal" if escenario in ("cuota", "api_caida") else escenario,
            API_PUBLICA_CLAVES=f"f95:sha256:{huella}",
            F9_FICHAS_POR_MINUTO=str(resultado["fichas_por_minuto"]), F9_FICHAS_POR_MINUTO_IP="100000",
            DATABASE_URL="sqlite:///" + (raiz / "sin-uso.sqlite").as_posix(),
            **{f"DIRECTORIO_{n}": str(raiz / "inutilizado" / n.lower()) for n in (
                "PRONOSTICOS_EXPERIMENTALES", "OPERACION", "LABORATORIO_MODELOS", "CARTERAS_MODELOS",
                "RESULTADOS_MODELOS", "PREDICCIONES_MODELOS", "AUTOMATIZACION", "SIMULACIONES")})
        pila.enter_context(r9.uvicorn("api", "tests.fase95_api_sintetica:app", p_api, entorno_api, registros))
        antes = arbol(datos)
        destino = r9.puerto_libre() if escenario == "api_caida" else p_api
        entorno_pasarela = r9.entorno_minimo(
            PASARELA_API_URL=f"http://127.0.0.1:{destino}", PASARELA_CLAVE_API=clave,
            PASARELA_HOSTS=f"127.0.0.1:{p_pasarela},localhost:{p_pasarela}",
            PASARELA_ORIGENES=f"http://127.0.0.1:{p_pasarela},http://localhost:{p_pasarela}",
            PASARELA_DIST=str(dist), PASARELA_CONSOLA_LOCAL="http://127.0.0.1:8000/")
        pila.enter_context(r9.uvicorn("pasarela", "app.pasarela.aplicacion:app", p_pasarela, entorno_pasarela, registros))
        cuerpos = raiz / "respuestas"
        cuerpos.mkdir()
        argumentos = [node, str(FRONTEND / "e2e" / "exportacion.mjs"), "--base", f"http://127.0.0.1:{p_pasarela}",
                      "--escenario", escenario, "--salida", str(salida / "navegador"), "--anchos", anchos,
                      "--cuerpos", str(cuerpos)]
        if solo_pdf:
            argumentos += ["--solo-pdf", "true"]
        if solo_impresion:
            argumentos += ["--solo-impresion", "true"]
        if navegador:
            argumentos += ["--navegador", navegador]
        with (registros / "navegador.stdout.log").open("wb") as out, (registros / "navegador.stderr.log").open("wb") as err:
            codigo = subprocess.run(argumentos, cwd=FRONTEND, env=r9.entorno_minimo(), stdout=out,
                                    stderr=err, timeout=1800).returncode
        resultado["ejecucion_navegador"] = {"argv": argumentos, "cwd": str(FRONTEND), "codigo": codigo}
        despues = arbol(datos)
        resultado["almacenes"] = {"archivos_antes": len(antes), "archivos_despues": len(despues),
                                  "intactos": antes == despues, "antes": antes, "despues": despues}
        resultado["respuestas_al_navegador_inspeccionadas"] = sum(1 for _ in cuerpos.iterdir())
        resultado["canario"] = {"respuestas_al_navegador": r9.buscar_canario(cuerpos, {"clave": clave, "huella": huella})}
        resultado["almacenes_ajenos_creados"] = (raiz / "inutilizado").exists()
    canarios = {"clave": clave, "huella": huella}
    resultado["canario"].update({"registros": r9.buscar_canario(registros, canarios),
                                 "navegador": r9.buscar_canario(salida / "navegador", canarios),
                                 "dist": r9.buscar_canario(dist, canarios)})
    resultado["canario_encontrado"] = any(v for grupo in resultado["canario"].values() for v in grupo.values())
    try:
        resultado["pdfs"] = _verificar_pdfs(salida, exigir_matriz=escenario == "normal" and not solo_impresion)
        resultado["error_matriz_pdf"] = None
    except (ValueError, KeyError, FileNotFoundError) as error:
        resultado["pdfs"] = []
        resultado["error_matriz_pdf"] = str(error)
    resultado["spa_compilada"]["intacta_durante_recorrido"] = arbol(dist) == compilado_antes
    resultado["impresion"] = resumen_impresion(salida)
    grupos = resultado["impresion"]["grupos"]
    # El modo focal no puede quedar en verde sin criterios evaluados: exige clic real y page.pdf aprobados.
    resultado["impresion"]["focal_con_criterios"] = (not solo_impresion) or (
        any(k.startswith("aprobada:") for k in grupos.get("imprimir-pdf-restaura", {}))
        and sum(grupos.get("imprimir-clic-real", {}).values()) > 0
        and sum(grupos.get("imprimir-sin-red", {}).values()) > 0)
    resultado["duracion_segundos"] = round(time.monotonic()-inicio, 3)
    resultado["ok"] = (codigo == 0 and not resultado["canario_encontrado"] and antes == despues
                       and not resultado["almacenes_ajenos_creados"]
                       and resultado["spa_compilada"]["intacta_durante_recorrido"]
                       and not resultado["error_matriz_pdf"]
                       and not resultado["impresion"]["error"] and resultado["impresion"]["focal_con_criterios"]
                       and all(p["ok"] for p in resultado["pdfs"]))
    (salida / "recorrido.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if resultado["ok"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--salida", type=Path, required=True, help="Carpeta nueva, puede contener espacios")
    parser.add_argument("--escenario", choices=ESCENARIOS, default="normal")
    parser.add_argument("--anchos", default="360,390,1280")
    parser.add_argument("--node", default=shutil.which("node") or "node")
    parser.add_argument("--navegador", help="Ejecutable externo Chromium/Brave ya instalado; sólo este ensayo")
    parser.add_argument("--solo-pdf", action="store_true", help="Revisar únicamente los doce PDF; no sustituye el recorrido completo")
    parser.add_argument("--solo-impresion", action="store_true",
                        help="F95-NAT-01: sólo criterios de impresión (clic real, page.pdf, cero red/fichas), sin descargas; no sustituye el recorrido completo")
    args = parser.parse_args(argv)
    return ejecutar(args.escenario, args.salida.resolve(), anchos=args.anchos, node=args.node, navegador=args.navegador, solo_pdf=args.solo_pdf,
                    solo_impresion=args.solo_impresion)


if __name__ == "__main__":
    raise SystemExit(main())
