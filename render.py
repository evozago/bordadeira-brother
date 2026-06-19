#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render.py — Ficha técnica + imagem (SVG) de um bordado, a partir do arquivo.

A "imagem" é desenhada a partir dos pontos do próprio arquivo (não é foto nem
câmera). Calcula: total de pontos, cores, trocas, tamanho e tempo estimado.

Requer pyembroidery (pip3 install pyembroidery).
"""
import os
import tempfile

SPM_PADRAO = 850  # pontos por minuto (velocidade típica da máquina)


def _thread_hex(pattern, idx):
    try:
        t = pattern.threadlist[idx % len(pattern.threadlist)]
        c = int(getattr(t, "color", 0)) & 0xFFFFFF
        return "#%06x" % c
    except Exception:
        palette = ["#222", "#c0392b", "#2980b9", "#27ae60", "#f39c12",
                   "#8e44ad", "#16a085", "#d35400"]
        return palette[idx % len(palette)]


def analyze(raw, filename, spm=SPM_PADRAO, max_px=420):
    """Retorna dict com ficha + svg. Lança RuntimeError se não der pra ler."""
    try:
        import pyembroidery
    except ImportError:
        raise RuntimeError("Instale pyembroidery: pip3 install pyembroidery")

    ext = os.path.splitext(filename)[1].lower() or ".pes"
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "f" + ext)
        with open(p, "wb") as f:
            f.write(raw)
        pattern = pyembroidery.read(p)
    if pattern is None or not pattern.stitches:
        raise RuntimeError("Arquivo de bordado não reconhecido.")

    st = pattern.stitches
    CMD = lambda c: c[2] & 0xFF
    COLOR_CHANGE = pyembroidery.COLOR_CHANGE
    NEEDLE_SET = getattr(pyembroidery, "NEEDLE_SET", -999)
    JUMP = pyembroidery.JUMP
    TRIM = pyembroidery.TRIM
    STOP = pyembroidery.STOP
    END = pyembroidery.END

    total = sum(1 for c in st if CMD(c) in (pyembroidery.STITCH, JUMP) or CMD(c) < 0x80)
    real_stitches = sum(1 for c in st if CMD(c) == pyembroidery.STITCH)
    color_changes = sum(1 for c in st if CMD(c) in (COLOR_CHANGE, NEEDLE_SET))
    trims = sum(1 for c in st if CMD(c) == TRIM)
    stops = sum(1 for c in st if CMD(c) == STOP)

    xs = [c[0] for c in st]
    ys = [c[1] for c in st]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    w10, h10 = (maxx - minx), (maxy - miny)
    w_mm, h_mm = w10 / 10.0, h10 / 10.0

    # ---- montar SVG (flip Y) ----
    pad = 20
    scale = (max_px - 2 * pad) / max(w10, h10, 1)
    W = int(w10 * scale + 2 * pad)
    H = int(h10 * scale + 2 * pad)

    def tx(x):
        return pad + (x - minx) * scale

    def ty(y):
        return pad + (maxy - y) * scale  # flip

    segs = []          # (color, [pts])
    cur = []
    color_idx = 0
    pen_color = _thread_hex(pattern, 0)
    prev = None
    for c in st:
        cmd = CMD(c)
        x, y = tx(c[0]), ty(c[1])
        if cmd in (COLOR_CHANGE, NEEDLE_SET):
            if len(cur) > 1:
                segs.append((pen_color, cur))
            cur = []
            color_idx += 1
            pen_color = _thread_hex(pattern, color_idx)
            prev = None
            continue
        if cmd in (JUMP, TRIM, STOP):
            if len(cur) > 1:
                segs.append((pen_color, cur))
            cur = []
            prev = (x, y)
            continue
        if cmd == END:
            break
        # ponto de costura
        if prev is None:
            cur = [(x, y)]
        else:
            if not cur:
                cur = [prev]
            cur.append((x, y))
        prev = (x, y)
    if len(cur) > 1:
        segs.append((pen_color, cur))

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
             f'<rect width="{W}" height="{H}" fill="#f7f7f9" rx="10"/>']
    for color, pts in segs:
        d = "M" + " L".join(f"{px:.1f},{py:.1f}" for px, py in pts)
        parts.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1" '
                     f'stroke-linecap="round" stroke-linejoin="round" opacity="0.9"/>')
    parts.append("</svg>")
    svg = "".join(parts)

    return {
        "ok": True,
        "stitches": real_stitches or len(st),
        "colors": len(pattern.threadlist) or (color_changes + 1),
        "color_changes": color_changes,
        "trims": trims,
        "stops": stops,
        "width_mm": round(w_mm, 1),
        "height_mm": round(h_mm, 1),
        "est_min": round((real_stitches or len(st)) / float(spm), 1),
        "svg": svg,
    }
