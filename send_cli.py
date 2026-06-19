#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
send_cli.py — Envio por linha de comando (bom para automação / cron / scripts).

    python3 send_cli.py desenho.pes
    python3 send_cli.py desenho.pes --ip 192.168.1.120 --name PEDIDO123.pes
    python3 send_cli.py --info
"""
import argparse
import os
import sys
import brother_machine as bm


def main():
    ap = argparse.ArgumentParser(description="Envia .pes para a bordadeira Brother na rede.")
    ap.add_argument("pes", nargs="?", help="caminho do arquivo .pes")
    ap.add_argument("--ip", default="192.168.1.120")
    ap.add_argument("--name", default=None, help="nome do arquivo na máquina")
    ap.add_argument("--info", action="store_true", help="só mostra dados/estado e sai")
    a = ap.parse_args()

    try:
        nfo = bm.info(a.ip)
        st = bm.status(a.ip)
    except Exception as e:
        print(f"!! Sem conexão com a máquina ({a.ip}): {e}")
        sys.exit(1)

    print(f"Maquina: {nfo['name']} | serie {nfo['serial']} | fw {nfo['version']}")
    print(f"Espaco livre: {st['free']} de {st['total']} bytes | arquivos: {st['files']}")

    if a.info:
        return
    if not a.pes or not os.path.isfile(a.pes):
        print("!! Informe um .pes valido. Ex.: python3 send_cli.py desenho.pes")
        sys.exit(2)

    pes = open(a.pes, "rb").read()
    if pes[:4] != b"#PES":
        print("!! Aviso: arquivo nao comeca com '#PES'. Continuando mesmo assim...")
    if len(pes) > nfo["features"]["postsize"]:
        print(f"!! Arquivo grande demais ({len(pes)} > limite {nfo['features']['postsize']}).")
        sys.exit(3)

    name = a.name or os.path.basename(a.pes)
    print(f"Enviando '{name}' ({len(pes)} bytes)...")
    ok, http_status = bm.send(a.ip, pes, name)
    print(f"Resultado: HTTP {http_status} -> {'OK' if ok else 'FALHOU'}")
    if ok:
        print("Arquivos na maquina agora:", bm.status(a.ip)["files"])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
