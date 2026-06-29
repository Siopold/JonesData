#!/usr/bin/env python3
"""
Bookcloth Cutting Guide Generator
Generates an SVG file for cutting and scoring bookcloth to cover a hardback book.

Solid lines = CUT   |   Dashed lines = SCORE / FOLD
"""

import os
import re
import sys
from fractions import Fraction


# ── Input helpers ─────────────────────────────────────────────────────────────

def parse_measurement(s):
    """Accept plain decimals, simple fractions (3/8), or mixed numbers (5 3/8)."""
    s = s.strip()
    m = re.match(r'^(\d+)\s+(\d+)\s*/\s*(\d+)$', s)   # mixed: 5 3/8
    if m:
        return int(m.group(1)) + int(m.group(2)) / int(m.group(3))
    m = re.match(r'^(\d+(?:\.\d*)?)\s*/\s*(\d+(?:\.\d*)?)$', s)  # fraction: 3/8
    if m:
        return float(m.group(1)) / float(m.group(2))
    try:
        return float(s)
    except ValueError:
        return None


def ask(prompt, default=None):
    while True:
        suffix = f" (press Enter for {default})" if default is not None else ""
        raw = input(f"  {prompt}{suffix}: ").strip()
        if not raw and default is not None:
            raw = str(default)
        val = parse_measurement(raw)
        if val is not None and val > 0:
            return val
        print("    Enter a positive number. Fractions like 3/8 or mixed 5 3/8 are fine.")


def fmt_dim(inches, use_metric):
    if use_metric:
        return f"{inches * 25.4:.1f} mm"
    f = Fraction(inches).limit_denominator(64)
    whole = f.numerator // f.denominator
    rem   = Fraction(f.numerator % f.denominator, f.denominator)
    if rem == 0:
        return f'{whole}"'
    if whole == 0:
        return f'{rem.numerator}/{rem.denominator}"'
    return f'{whole} {rem.numerator}/{rem.denominator}"'


# ── SVG generation ────────────────────────────────────────────────────────────

def generate_svg(H, W, S, G, T, use_metric=False):
    """
    H  board height (inches)
    W  board width  (inches)
    S  spine depth  (inches)
    G  gutter width (inches)
    T  board thickness (inches)
    """
    TO = 0.5   # turnover: 1/2" on the three outer sides of each board

    # Validate geometry
    if T >= TO:
        sys.exit(f"\nError: board thickness ({T:.4f}\") must be less than the "
                 f"turnover ({TO}\"). Use thinner boards or increase turnover.")

    cloth_w = TO + W + G + S + G + W + TO
    cloth_h = TO + H + TO

    PPI    = 72.0          # SVG user units per inch (print points)
    margin = 0.75 * PPI    # canvas border

    svg_w  = cloth_w * PPI + 2 * margin
    svg_h  = cloth_h * PPI + 2 * margin

    ox, oy = margin, margin   # cloth-piece origin in SVG space

    def sx(cx): return ox + cx * PPI   # cloth-coord → SVG x
    def sy(cy): return oy + cy * PPI   # cloth-coord → SVG y
    def pu(v):  return v * PPI         # inches → SVG units

    def P(cx, cy): return f"{sx(cx):.3f},{sy(cy):.3f}"

    # ── Named cloth coordinates ────────────────────────────────────────
    t = TO

    lb_x1, lb_x2 = t,       t + W               # left board l/r
    rb_x1, rb_x2 = t+W+2*G+S, t+2*W+2*G+S      # right board l/r
    sp_x1, sp_x2 = t+W+G,   t+W+G+S             # spine l/r
    lg_x1, lg_x2 = t+W,     t+W+G               # left gutter l/r
    rg_x1, rg_x2 = t+W+G+S, t+W+2*G+S          # right gutter l/r
    bd_y1, bd_y2 = t,       t + H               # board top/bottom

    # Outer score lines: T inward from cloth edge (board-thickness away from board edge)
    os_left   = t - T           # left outer score  x
    os_top    = t - T           # top outer score   y
    os_bottom = t + H + T       # bottom outer score y
    os_right  = rb_x2 + T      # right outer score x   (= cloth_w - t + T)

    # Miter diagonal passes through outer-score corner; leg length on each edge:
    miter_d = 2 * (t - T)      # = 2*(0.5 - T)

    # ── Cut path ──────────────────────────────────────────────────────
    # Outer boundary: rectangle with 4 fore-edge miter cuts (clockwise).
    # Spine tab taper cuts are separate open paths within the cloth.
    cut = (
        # Outer rectangle + miter cuts (clockwise)
        f"M {P(0, miter_d)}"
        f" L {P(miter_d, 0)}"
        f" L {P(cloth_w - miter_d, 0)}"
        f" L {P(cloth_w, miter_d)}"
        f" L {P(cloth_w, cloth_h - miter_d)}"
        f" L {P(cloth_w - miter_d, cloth_h)}"
        f" L {P(miter_d, cloth_h)}"
        f" L {P(0, cloth_h - miter_d)}"
        f" Z"
    )

    # ── Score path (all dashed segments joined into one <path>) ────────
    def seg(*pts):
        coords = [f"M {P(pts[0][0], pts[0][1])}"]
        for p in pts[1:]:
            coords.append(f"L {P(p[0], p[1])}")
        return " ".join(coords)

    scores = []

    # Inner board rectangles
    scores.append(f"M {P(lb_x1,bd_y1)} L {P(lb_x2,bd_y1)} L {P(lb_x2,bd_y2)} L {P(lb_x1,bd_y2)} Z")
    scores.append(f"M {P(rb_x1,bd_y1)} L {P(rb_x2,bd_y1)} L {P(rb_x2,bd_y2)} L {P(rb_x1,bd_y2)} Z")

    # Outer score lines — verticals (left and right outer edges only)
    scores.append(seg((os_left,  os_top), (os_left,  os_bottom)))
    scores.append(seg((os_right, os_top), (os_right, os_bottom)))

    # Outer score lines — full-width horizontals spanning corner to corner
    scores.append(seg((os_left, os_top),    (os_right, os_top)))
    scores.append(seg((os_left, os_bottom), (os_right, os_bottom)))

    # Spine-tab inner fold lines (where the tab folds over the spine edge)
    scores.append(seg((lg_x2, t),          (rg_x1, t)))              # top
    scores.append(seg((lg_x2, cloth_h - t),(rg_x1, cloth_h - t)))   # bottom

    # Gutter / hinge verticals (guides for the flex zone between boards and spine)
    for vx in (lg_x1, lg_x2, rg_x1, rg_x2):
        scores.append(seg((vx, bd_y1), (vx, bd_y2)))

    score = " ".join(scores)

    # ── Labels ────────────────────────────────────────────────────────
    def dim(v):  return fmt_dim(v, use_metric)

    lb_cx  = sx((lb_x1 + lb_x2) / 2)
    rb_cx  = sx((rb_x1 + rb_x2) / 2)
    sp_cx  = sx((sp_x1 + sp_x2) / 2)
    bd_mcy = sy((bd_y1 + bd_y2) / 2)

    cloth_label = (f"Cloth: {cloth_w:.3f}\" × {cloth_h:.3f}\""
                   f"  ({cloth_w*25.4:.1f} mm × {cloth_h*25.4:.1f} mm)")

    # Legend position: right of cloth if room, else below
    leg_x = ox + cloth_w * PPI + 15
    leg_y = oy + 10
    if leg_x + 110 > svg_w:
        leg_x = ox
        leg_y  = oy + cloth_h * PPI + 30

    # ── Assemble SVG ──────────────────────────────────────────────────
    L = []
    def emit(*s): L.extend(s)

    emit(
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg"',
        f'     width="{svg_w:.2f}pt" height="{svg_h:.2f}pt"',
        f'     viewBox="0 0 {svg_w:.2f} {svg_h:.2f}">',
        '<title>Bookcloth Cutting Guide</title>',
        '<style>',
        '  .cut   { fill:none; stroke:#000; stroke-width:1.5; stroke-linecap:round; }',
        '  .score { fill:none; stroke:#000; stroke-width:0.75;',
        '           stroke-dasharray:6,4; stroke-linecap:round; }',
        '  .lbl   { font-family:Helvetica,Arial,sans-serif; font-size:7pt; fill:#333; }',
        '  .lbl-b { font-family:Helvetica,Arial,sans-serif; font-size:7pt; fill:#111;',
        '           font-weight:bold; }',
        '  .note  { font-family:Helvetica,Arial,sans-serif; font-size:6pt; fill:#888; }',
        '</style>',
        f'<rect x="0" y="0" width="{svg_w:.2f}" height="{svg_h:.2f}" fill="#fff"/>',
        '',
        '<!-- CUT LINES -->',
        f'<path d="{cut}" class="cut"/>',
        '',
        '<!-- SCORE / FOLD LINES -->',
        f'<path d="{score}" class="score"/>',
        '',
        '<!-- Labels -->',
    )

    # Board / spine labels
    for cx, name, w_val, h_val in [
        (lb_cx, "LEFT BOARD",  W, H),
        (rb_cx, "RIGHT BOARD", W, H),
    ]:
        emit(
            f'<text x="{cx:.1f}" y="{bd_mcy - 10:.1f}" class="lbl" text-anchor="middle">{name}</text>',
            f'<text x="{cx:.1f}" y="{bd_mcy + 4:.1f}"  class="lbl" text-anchor="middle">{dim(w_val)} × {dim(h_val)}</text>',
        )
    emit(
        f'<text x="{sp_cx:.1f}" y="{bd_mcy - 10:.1f}" class="lbl" text-anchor="middle">SPINE</text>',
        f'<text x="{sp_cx:.1f}" y="{bd_mcy + 4:.1f}"  class="lbl" text-anchor="middle">{dim(S)}</text>',
    )

    # Cloth-size label below piece
    cly = oy + cloth_h * PPI + 14
    emit(f'<text x="{ox + cloth_w*PPI/2:.1f}" y="{cly:.1f}" class="note" text-anchor="middle">{cloth_label}</text>')

    # Legend
    emit(
        f'<text x="{leg_x:.1f}" y="{leg_y:.1f}" class="lbl-b">LEGEND</text>',
        f'<line x1="{leg_x:.1f}" y1="{leg_y+12:.1f}" x2="{leg_x+24:.1f}" y2="{leg_y+12:.1f}" class="cut"/>',
        f'<text x="{leg_x+28:.1f}" y="{leg_y+16:.1f}" class="lbl">Cut</text>',
        f'<line x1="{leg_x:.1f}" y1="{leg_y+27:.1f}" x2="{leg_x+24:.1f}" y2="{leg_y+27:.1f}" class="score"/>',
        f'<text x="{leg_x+28:.1f}" y="{leg_y+31:.1f}" class="lbl">Score / fold</text>',
    )

    # Print note
    emit(
        f'<text x="{svg_w/2:.1f}" y="{svg_h - 4:.1f}" class="note" text-anchor="middle">'
        f'Print at 100 % Actual Size (no scaling). 72 pt = 1 inch.</text>',
    )

    emit('</svg>')
    return "\n".join(L)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print()
    print("┌──────────────────────────────────────────────────────────┐")
    print("│            BOOKCLOTH CUTTING GUIDE GENERATOR            │")
    print("├──────────────────────────────────────────────────────────┤")
    print("│  Default units: INCHES                                   │")
    print("│  Fractions OK: e.g.  3/8   11/16   5 3/4               │")
    print("│  Type 'y' at the next prompt to switch to millimetres.  │")
    print("└──────────────────────────────────────────────────────────┘")
    print()

    use_metric = input("Use metric units (mm) instead of inches? Press Enter for inches, or type y for mm: ").strip().lower() in ("y", "yes")
    unit = "mm" if use_metric else "in"

    # Default gutter ≈ 3/8"  |  default thickness ≈ 3/16"
    if use_metric:
        def_gut, def_thk = 9.5, 3.2
    else:
        def_gut, def_thk = "3/8", "1/8"

    print(f"\n  Measurements in {unit}:\n")
    H = ask(f"Board height ({unit})")
    W = ask(f"Board width ({unit})")
    S = ask(f"Spine depth / book-block depth ({unit})")
    G = ask(f"Gutter width ({unit})", default=def_gut)
    T = ask(f"Board thickness ({unit})", default=def_thk)

    if use_metric:
        H /= 25.4; W /= 25.4; S /= 25.4; G /= 25.4; T /= 25.4

    TO = 0.5
    cloth_w = TO + W + G + S + G + W + TO
    cloth_h = TO + H + TO

    print()
    print(f"  Cloth piece: {cloth_w:.3f}\" wide  ×  {cloth_h:.3f}\" tall")
    print(f"               ({cloth_w*25.4:.1f} mm  ×  {cloth_h*25.4:.1f} mm)")
    print()

    out = input("  Output filename (press Enter for bookcloth_guide.svg): ").strip() or "bookcloth_guide.svg"
    if not out.lower().endswith(".svg"):
        out += ".svg"

    svg = generate_svg(H, W, S, G, T, use_metric=use_metric)

    with open(out, "w", encoding="utf-8") as f:
        f.write(svg)

    print()
    print(f"  Saved: {os.path.abspath(out)}")
    print()
    print("  Open in Adobe Illustrator.")
    print("  File → Document Setup can be used to verify units.")
    print("  Print at Actual Size (100 %) — do NOT scale to fit page.")
    print()
    print("  ── Solid lines  =  CUT")
    print("  ── Dashed lines =  SCORE / FOLD")
    print()


if __name__ == "__main__":
    main()
