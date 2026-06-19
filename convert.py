#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convert.py — Conversão de formatos de bordado para PES.

Aceita DST, EXP, JEF, VP3, XXX, etc. e converte para PES (o formato da Brother)
usando a biblioteca pyembroidery (opcional). Se o arquivo já for PES, devolve
como está, sem reprocessar.

    pip3 install pyembroidery   # necessário só para converter formatos != PES
"""
import os
import tempfile


def pes_name(filename):
    """Garante extensão .pes no nome (mantém o nome base)."""
    base = os.path.splitext(os.path.basename(filename))[0]
    return base + ".pes"


def to_pes(raw, filename):
    """
    Retorna (bytes_pes, nome_final.pes).
    Se já for PES, devolve sem alterar. Senão, converte via pyembroidery.
    Lança RuntimeError se não der para converter.
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pes" or raw[:4] == b"#PES":
        return raw, pes_name(filename)

    try:
        import pyembroidery
    except ImportError:
        raise RuntimeError(
            "Conversao indisponivel. Instale: pip3 install pyembroidery"
        )

    with tempfile.TemporaryDirectory() as d:
        inp = os.path.join(d, "entrada" + (ext or ".dst"))
        outp = os.path.join(d, "saida.pes")
        with open(inp, "wb") as f:
            f.write(raw)
        pattern = pyembroidery.read(inp)
        if pattern is None:
            raise RuntimeError(f"Formato nao reconhecido: {ext or '(sem extensao)'}")
        pyembroidery.write_pes(pattern, outp)
        with open(outp, "rb") as f:
            return f.read(), pes_name(filename)


def is_supported(filename):
    ext = os.path.splitext(filename)[1].lower()
    return ext in {".pes", ".dst", ".exp", ".jef", ".vp3", ".xxx", ".pec", ".phc", ".u01"}
