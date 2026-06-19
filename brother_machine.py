#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
brother_machine.py — Biblioteca de comunicação com bordadeiras Brother
(linha Innov-is / WLAN, ex.: BP1530L) pela rede local.

Protocolo descoberto por engenharia reversa do "Design Database Transfer".
Veja PROTOCOL.md. Sem app, sem nuvem. Usa apenas a biblioteca padrão do Python 3.

Funções principais:
    info(ip)             -> dict com dados da máquina (/info)
    status(ip)           -> dict com espaço livre e lista de arquivos
    send(ip, bytes, nome)-> envia um .pes; retorna (ok: bool, http: int)
"""

import http.client
import json
import re
import ssl
import uuid

ENDPOINT = "/sewing/sewing.cgi"
APP_ID = "23"
USER_AGENT = "Design Database Transfer"
COMMON = {
    "Accept-Language": "1046",
    "User-Agent": USER_AGENT,
    "Cache-Control": "no-cache",
}


def _conn(ip, timeout=30):
    """Conexão HTTPS sem verificar certificado (a máquina usa cert auto-assinado)."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return http.client.HTTPSConnection(ip, 443, timeout=timeout, context=ctx)


def info(ip):
    """GET /info -> dados da máquina (modelo, série, firmware, limites)."""
    c = _conn(ip, 10)
    try:
        c.request("GET", "/info", headers={"User-Agent": USER_AGENT})
        r = c.getresponse()
        return json.loads(r.read().decode("utf-8", "replace"))
    finally:
        c.close()


def status(ip):
    """POST sewing.cgi (appstate=2) -> espaço e arquivos na memória."""
    body = f"req_sessionid=0&req_appid={APP_ID}&req_appver=1.2.0&req_appstate=2".encode()
    h = dict(COMMON)
    h["Content-Type"] = "application/x-www-form-urlencoded"
    c = _conn(ip, 10)
    try:
        c.request("POST", ENDPOINT, body=body, headers=h)
        xml = c.getresponse().read().decode("utf-8", "replace")
    finally:
        c.close()

    def g(tag):
        m = re.search(rf"<{tag}>(.*?)</{tag}>", xml, re.S)
        return m.group(1).strip() if m else None

    total = int(g("upload_size") or 0)
    free = int(g("upload_freesize") or 0)
    return {
        "error_code": g("error_code"),
        "total": total,
        "free": free,
        "used": total - free,
        "files": re.findall(r"<file_name>(.*?)</file_name>", xml),
        "upload_path": g("upload_path"),
    }


def send(ip, pes_bytes, filename):
    """POST sewing.cgi multipart (appstate=3) -> envia o .pes. (ok, http_status)."""
    boundary = "---------------------------" + uuid.uuid4().hex[:12]
    b = boundary.encode()
    CRLF = b"\r\n"
    p1 = f"req_sessionid=0&req_appid={APP_ID}&req_appver=100&req_appstate=3".encode()
    safe = filename.encode("ascii", "replace")
    body = b"".join([
        b"--", b, CRLF,
        b'Content-Disposition:form-data;name="req_parameter";filename="req_parameter"', CRLF,
        b"Content-Type:application/x-www-form-urlencoded", CRLF, CRLF, p1, CRLF,
        b"--", b, CRLF,
        b'Content-Disposition:form-data;name="myfile";filename="' + safe + b'"', CRLF,
        b"Content-Type:application/octet-stream", CRLF, CRLF, pes_bytes, CRLF,
        b"--", b, b"--", CRLF,
    ])
    h = dict(COMMON)
    h["Content-Type"] = "multipart/form-data;boundary=" + boundary
    h["Accept-Encoding"] = "gzip,deflate"
    h["Connection"] = "Keep-Alive"
    c = _conn(ip, 60)
    try:
        c.request("POST", ENDPOINT, body=body, headers=h)
        r = c.getresponse()
        r.read()
        return (r.status in (200, 204)), r.status
    finally:
        c.close()
