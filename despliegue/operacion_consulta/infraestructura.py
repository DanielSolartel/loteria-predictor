"""Compose de ensayo sin construcción, publicación, contraseñas ni volúmenes de datos.

PostgreSQL y la generación importada se proporcionan por separado. Este módulo
solo produce archivos: no ejecuta Docker ni cambia la infraestructura existente.
"""
from __future__ import annotations

from .modelo import Plan

PREFIJO = "es.loteria.e105"


def etiquetas(p: Plan, propietario: str) -> dict:
    return {PREFIJO + ".propietario": propietario, PREFIJO + ".plan": p.id,
            PREFIJO + ".generacion": p.generacion, PREFIJO + ".modo": "ensayo"}


def montajes(p: Plan, carpeta: str, servicio: str) -> dict[str, str]:
    return {
        "api": {"/srv/generacion/" + p.generacion: p.directorio_generacion,
                "/run/publica/firma.pub": p.clave_publica,
                "/run/secretos/api_database_url": p.secretos + "/api_database_url",
                "/run/secretos/api_claves": p.secretos + "/api_claves"},
        "pasarela": {"/run/secretos/pasarela_ingreso": p.secretos + "/pasarela_ingreso",
                     "/run/secretos/pasarela_clave_api": p.secretos + "/pasarela_clave_api"},
        "proxy": {"/etc/nginx/ensayo": carpeta, "/etc/nginx/tls": p.pki_proxy,
                  "/etc/nginx/secretos/ingreso.conf": p.secretos + "/proxy_ingreso.conf"},
    }[servicio]


def componer(p: Plan, propietario: str, carpeta: str) -> dict:
    proyecto = p.proyecto(propietario)
    labs = etiquetas(p, propietario)

    def servicio(nombre, imagen, usuario, memoria, cpu, entorno, redes):
        return {"image": imagen, "pull_policy": "never", "user": usuario, "labels": labs,
                "read_only": True, "cap_drop": ["ALL"], "security_opt": ["no-new-privileges:true"],
                "pids_limit": 128, "tmpfs": ["/tmp:size=16m,mode=1777"], "restart": "no",
                "mem_limit": memoria, "cpus": cpu, "environment": entorno, "networks": redes,
                "volumes": [{"type": "bind", "source": origen.replace("$", "$$"), "target": destino,
                             "read_only": True, "bind": {"create_host_path": False}}
                            for destino, origen in montajes(p, carpeta, nombre).items()]}

    entorno_api = {
        "DATABASE_URL_ARCHIVO": "/run/secretos/api_database_url",
        "API_PUBLICA_CLAVES_ARCHIVO": "/run/secretos/api_claves",
        "GENERACION_DIRECTORIO": "/srv/generacion/" + p.generacion,
        "GENERACION_CLAVE_PUBLICA": "/run/publica/firma.pub",
        "API_PUBLICA_HOSTS": p.ip("red_servicio", 20) + ":8010,127.0.0.1:8010",
        "API_PUBLICA_CLIENTES": p.ip("red_servicio", 10) + ",127.0.0.1",
        "API_PUBLICA_DOCUMENTACION": "false", "API_PUBLICA_FICHAS_POR_MINUTO": "1200",
        "API_PUBLICA_FICHAS_POR_MINUTO_IP": "2400", "API_PUBLICA_CONCURRENCIA_COSTOSAS": "2",
        "API_PUBLICA_ESPERA_COSTOSAS": "0.5", "BASE_TIEMPO_MAXIMO_CONSULTA_MS": "1500",
        "BASE_TIEMPO_MAXIMO_INACTIVA_MS": "5000", "BASE_POOL_TAMANO": "4",
        "BASE_POOL_DESBORDE": "2", "BASE_POOL_ESPERA_S": "2"}
    for nombre in ("RESULTADOS_MODELOS", "SIMULACIONES", "OPERACION", "AUTOMATIZACION"):
        entorno_api["DIRECTORIO_" + nombre] = "/srv/sin-publicar/" + nombre.lower()
    api = servicio("api", p.imagen_api, "10001:10001", "768m", 1.0, entorno_api,
                   {"servicio": {"ipv4_address": p.ip("red_servicio", 20)},
                    "datos": {"ipv4_address": p.ip_datos_api}})
    api.update(entrypoint=["uvicorn"], command=["app.api.publica.privada:app", "--host", "0.0.0.0", "--port", "8010",
                                               "--workers", "1", "--no-access-log", "--no-proxy-headers"])
    direccion = p.host + ":" + str(p.puerto)
    pasarela = servicio("pasarela", p.imagen_pasarela, "10001:10001", "256m", 0.5, {
        "PASARELA_PERFIL": "privado", "PASARELA_PROXIES_FIABLES": p.ip("red_interna", 10),
        "PASARELA_SECRETO_PROXY_ARCHIVO": "/run/secretos/pasarela_ingreso",
        "PASARELA_CLAVE_API_ARCHIVO": "/run/secretos/pasarela_clave_api",
        "PASARELA_API_URL": "http://" + p.ip("red_servicio", 20) + ":8010",
        "PASARELA_HOSTS": direccion, "PASARELA_ORIGENES": "https://" + direccion,
        "PASARELA_FICHAS_PERSONA_POR_MINUTO": "30", "PASARELA_FICHAS_AGREGADAS_POR_MINUTO": "50",
        "PASARELA_MAX_PERSONAS": "16"}, {"interna": {"ipv4_address": p.ip("red_interna", 20)},
                                         "servicio": {"ipv4_address": p.ip("red_servicio", 10)}})
    pasarela.update(entrypoint=["uvicorn"], command=["app.pasarela.aplicacion:app", "--host", "0.0.0.0", "--port", "8020",
                                                    "--workers", "1", "--no-access-log", "--no-proxy-headers"])
    proxy = servicio("proxy", p.imagen_proxy, "101:101", "128m", 0.5, {},
                     {"frontal": {}, "interna": {"ipv4_address": p.ip("red_interna", 10)}})
    proxy.update(entrypoint=["nginx", "-c", "/etc/nginx/ensayo/nginx.conf", "-g", "daemon off;"],
                 command=[],
                 ports=[{"target": 18443, "published": str(p.puerto), "host_ip": "127.0.0.1", "protocol": "tcp"}],
                 tmpfs=["/tmp:size=16m,mode=1777", "/var/cache/nginx:size=16m,uid=101,gid=101"])
    return {"name": proyecto, "services": {"api": api, "pasarela": pasarela, "proxy": proxy}, "networks": {
        "frontal": {"labels": labs},
        "interna": {"internal": True, "labels": labs, "ipam": {"config": [{"subnet": p.red_interna}]}},
        "servicio": {"internal": True, "labels": labs, "ipam": {"config": [{"subnet": p.red_servicio}]}},
        "datos": {"external": True, "name": p.red_datos}}}


def nginx(p: Plan) -> str:
    # Todos los valores interpolados proceden de campos cerrados de Plan.
    return """worker_processes 1;
worker_shutdown_timeout %ds;
pid /tmp/nginx.pid;
error_log /dev/stderr warn;
events { worker_connections 256; }
http {
    server_tokens off;
    client_body_temp_path /tmp/cuerpo;
    proxy_temp_path /tmp/proxy;
    fastcgi_temp_path /tmp/fastcgi;
    uwsgi_temp_path /tmp/uwsgi;
    scgi_temp_path /tmp/scgi;
    client_max_body_size 1k;
    client_header_timeout 5s;
    client_body_timeout 5s;
    send_timeout 20s;
    keepalive_timeout 5s;
    log_format consulta '$time_iso8601 $request_method $uri $status';
    access_log /dev/stdout consulta;
    map $ssl_client_s_dn $identidad {
        "~^CN=(?<cn>[a-z0-9][a-z0-9-]{1,62})$" $cn;
        default "";
    }
    map $http_host $host_admitido { "%s:%d" 1; default 0; }
    limit_req_zone $ssl_client_serial zone=por_certificado:1m rate=20r/s;
    limit_req_status 429;
    server {
        listen 18443 ssl;
        server_name %s;
        ssl_certificate /etc/nginx/tls/servidor.crt;
        ssl_certificate_key /etc/nginx/tls/servidor.key;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_client_certificate /etc/nginx/tls/ca-consulta.crt;
        ssl_verify_client on;
        ssl_verify_depth 1;
        ssl_crl /etc/nginx/tls/crl.pem;
        if ($host_admitido = 0) { return 421; }
        if ($identidad = "") { return 403; }
        include /etc/nginx/ensayo/mantenimiento.conf;
        location / {
            limit_req zone=por_certificado burst=40 nodelay;
            proxy_pass http://%s:8020;
            proxy_http_version 1.1;
            proxy_set_header Host $http_host;
            proxy_set_header Connection "";
            proxy_set_header X-Consulta-Identidad $identidad;
            include /etc/nginx/secretos/ingreso.conf;
            proxy_set_header X-Forwarded-For "";
            proxy_set_header Forwarded "";
            proxy_set_header X-Real-IP "";
            proxy_set_header X-Forwarded-Host "";
            proxy_set_header X-Forwarded-Proto "";
            proxy_read_timeout 20s;
            proxy_connect_timeout 3s;
        }
    }
}
""" % (p.drenaje_s, p.host, p.puerto, p.host, p.ip("red_interna", 20))


MANTENIMIENTO = 'add_header Retry-After "30" always;\nreturn 503;\n'
