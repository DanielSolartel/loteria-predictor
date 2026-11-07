"""Trabajo sintetico dentro de la imagen de dependencias ya instalada.

Sin Docker socket ni acceso a la base operativa. Su unico montaje escribible es
el directorio nuevo de este ensayo; la copia de fuentes se monta de solo lectura.
"""
from __future__ import annotations

import hashlib
import importlib.util
import ipaddress
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def crear_pki(raiz: Path) -> None:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    raiz.mkdir(mode=0o700)
    ahora = datetime.now(timezone.utc)
    clave_ca = ec.generate_private_key(ec.SECP256R1())
    nombre_ca = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "E107 ENSAYO LOCAL")])

    def base(sujeto, publica):
        return (x509.CertificateBuilder().subject_name(sujeto).issuer_name(nombre_ca)
                .public_key(publica).serial_number(x509.random_serial_number())
                .not_valid_before(ahora - timedelta(minutes=2))
                .not_valid_after(ahora + timedelta(days=2))
                .add_extension(x509.SubjectKeyIdentifier.from_public_key(publica), critical=False)
                .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(clave_ca.public_key()), critical=False))

    ca = (base(nombre_ca, clave_ca.public_key())
          .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
          .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
              key_encipherment=False, data_encipherment=False, key_agreement=False,
              key_cert_sign=True, crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
          .sign(clave_ca, hashes.SHA256()))
    pem = serialization.Encoding.PEM
    (raiz / "ca.crt").write_bytes(ca.public_bytes(pem))
    for nombre, cn, uso in (("servidor", "localhost", ExtendedKeyUsageOID.SERVER_AUTH),
                             ("cliente", "invitado-e107", ExtendedKeyUsageOID.CLIENT_AUTH)):
        clave = ec.generate_private_key(ec.SECP256R1())
        sujeto = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
        cert = (base(sujeto, clave.public_key())
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                    key_encipherment=False, data_encipherment=False, key_agreement=False,
                    key_cert_sign=False, crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
                .add_extension(x509.ExtendedKeyUsage([uso]), critical=False))
        if nombre == "servidor":
            cert = cert.add_extension(x509.SubjectAlternativeName([
                x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
        (raiz / (nombre + ".crt")).write_bytes(cert.sign(clave_ca, hashes.SHA256()).public_bytes(pem))
        ruta = raiz / (nombre + ".key")
        fd = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(clave.private_bytes(pem, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    crl = (x509.CertificateRevocationListBuilder().issuer_name(nombre_ca).last_update(ahora)
           .next_update(ahora + timedelta(days=1)).sign(clave_ca, hashes.SHA256()))
    (raiz / "crl.pem").write_bytes(crl.public_bytes(pem))
    # La clave CA permanece solo en memoria y no se instala en Windows/Ubuntu.


def _modulo(ruta: Path):
    spec = importlib.util.spec_from_file_location("demo_generaciones_e107", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class PasoNoSuperado(RuntimeError):
    def __init__(self, paso: str):
        self.paso = paso if re.fullmatch(r"D[0-9]{2}[a-z]?|R[0-9]{2}|N-respaldo-(?:alterado|truncado)", paso) else "sin_identificador"
        super().__init__("verificacion_sintetica_no_superada")


def ejecutar(modo: str, raiz: Path, fuente: Path, *, control: dict | None = None) -> dict:
    control = control if control is not None else {"fase": "inicio", "pasos": []}
    if modo not in {"comprobar", "migrar", "generar", "verificar"}:
        raise ValueError("modo_de_preparacion")
    control["fase"] = modo
    sys.path.insert(0, str(fuente / "backend"))
    sys.path.insert(0, str(fuente))
    if modo == "comprobar":
        import cryptography, fastapi, h11, psycopg, sqlalchemy, uvicorn  # noqa: F401
        from app.infrastructure.generaciones.codigo import huella_app
        return {"codigo": 0, "huella_app": huella_app(fuente / "backend/app")[0]}
    if modo == "verificar":
        from app.infrastructure.generaciones.importacion import verificar_publicada
        d = json.loads((raiz / "preparacion.json").read_text())
        v = verificar_publicada(Path(d["directorio_generacion"]), Path(d["clave_publica"]))
        return {"codigo": 0, "sha256_manifiesto": v["sha256_manifiesto"],
                "manifiesto": {"id": v["manifiesto"]["id"], "codigo": v["manifiesto"]["codigo"]}}
    urls = json.loads((raiz / "urls.json").read_text())
    limpio = {k: v for k, v in os.environ.items() if not k.startswith((
        "DATABASE_URL", "DIRECTORIO_", "API_PUBLICA_", "GENERACION_"))}
    limpio["PYTHONDONTWRITEBYTECODE"] = "1"
    if modo == "migrar":
        control["fase"] = "migrar"
        limpio["DATABASE_URL"] = urls["propietario"]
        r = subprocess.run([sys.executable, "-B", "-m", "alembic", "upgrade", "head"],
            cwd=fuente / "backend", env=limpio, capture_output=True, timeout=120)
        if r.returncode:
            raise ValueError("migracion_sintetica_rechazada")
        return {"codigo": 0}
    if modo != "generar":
        raise ValueError("modo_de_preparacion")
    os.environ.clear()
    os.environ.update(limpio)
    os.chdir(fuente / "backend")
    modulo = _modulo(fuente / "despliegue/generaciones/demostracion_e104.py")
    salida = raiz / "generaciones"
    salida.mkdir(mode=0o700)
    class DemoLocal(modulo.Demo):
        def anotar(self, ident, descripcion, ok, **detalle):
            control["pasos"].append({"id": ident, "ok": bool(ok)})
            correcto = super().anotar(ident, descripcion, ok, **detalle)
            if not correcto:
                raise PasoNoSuperado(ident)
            return correcto

    demo = DemoLocal(salida, urls, sys.executable)
    control["fase"] = "fuente"
    demo.preparar()
    control["fase"] = "captura_importacion"
    demo.g1()
    control["fase"] = "api_ligada"
    demo.api_ligada()
    control["fase"] = "respaldo_restauracion"
    demo.respaldo()
    if not demo.filas or not all(f["ok"] for f in demo.filas):
        raise ValueError("recorrido_sintetico_rechazado")
    from app.infrastructure.generaciones.respaldo import comprobar_restauracion
    restauracion = comprobar_restauracion(salida / "restauracion")
    carpeta = demo.raiz / "generaciones" / demo.g1_id
    m = json.loads((carpeta / "manifiesto.json").read_text())
    datos = {"codigo": 0, "generacion": demo.g1_id,
             "directorio_generacion": str(carpeta),
             "clave_publica": str(demo.secretos / "firma.pub"),
             "manifiesto_sha256": hashlib.sha256((carpeta / "manifiesto.json").read_bytes()).hexdigest(),
             "huella_app": m["codigo"]["huella_app"],
             "restauracion": {"estado": restauracion["estado"], "base_nueva": True},
             "comprobaciones": [{"id": f["id"], "ok": f["ok"]} for f in demo.filas]}
    control["fase"] = "pki"
    crear_pki(raiz / "pki")
    (raiz / "preparacion.json").write_text(json.dumps(datos))
    control["fase"] = "completada"
    return datos


if __name__ == "__main__":
    control = {"fase": "inicio", "pasos": []}
    try:
        resultado = ejecutar(sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), control=control)
    except BaseException as error:
        resultado = {"codigo": 1, "resultado": "preparacion_sintetica_rechazada",
                     "tipo_error": type(error).__name__, "comprobaciones": control["pasos"]}
        if isinstance(error, PasoNoSuperado):
            resultado["paso_fallido"] = error.paso
    resultado["fase_preparacion"] = control["fase"]
    print("E107_PREPARACION:" + json.dumps(resultado, ensure_ascii=True), flush=True)
    raise SystemExit(resultado["codigo"])
