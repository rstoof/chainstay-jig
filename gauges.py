"""
Section gauges: thin split rings whose hole is the modelled stay + GCLR
at stations along the stay. Clip each one on at its distance from the lug end and
feel the fit: a gauge that is tight or loose tells where SECTIONS is wrong.

Split at the bottom, thin hinge at the top: open it like a clamshell to get it
around the stay. Tab label: distance from the lug end : modelled stay width x height (mm).
Print flat, PLA or PETG.
"""
import math
from pathlib import Path
from build123d import *
import jig

STATIONS = [0, 25, 50, 75, 100, 125, 150]
T = 2.4          # gauge thickness
WALLG = 2.0      # ring wall
SLIT = 1.0       # split at the bottom
HINGE = 0.7      # material left at the top hinge
TXT = 6.0      # label text height (Arial Black: strokes ~1.2 mm, two solid lines on a 0.4 nozzle)
GCLR = 0.1     # total clearance in the gauge hole (+0.2 felt loose-ish)
OUT = Path(__file__).parent / "out" / "gauges"


def ellipse(w, h):
    return Ellipse(w / 2, h / 2)


def gauge(x):
    sw, sh = jig.sec(x)
    w, h = sw + GCLR, sh + GCLR
    label = Text(f"{x:g}:{sw:.1f}x{sh:.1f}", TXT, font_path="/System/Library/Fonts/Supplemental/Arial Black.ttf",
                 align=(Align.MIN, Align.CENTER))
    tw = label.bounding_box().size.X
    tab_l = tw + 5
    x0 = w / 2 + WALLG - 1                                   # tab starts inside the ring wall
    with BuildSketch() as sk:
        Ellipse(w / 2 + WALLG, h / 2 + WALLG)
        with Locations((x0 + tab_l / 2, 0)):                 # label tab on the side
            RectangleRounded(tab_l, TXT + 4, 1.5)
        Ellipse(w / 2, h / 2, mode=Mode.SUBTRACT)
        with Locations((0, -(h / 2 + WALLG / 2))):           # split at the bottom
            Rectangle(SLIT, WALLG * 3, mode=Mode.SUBTRACT)
        with Locations((0, h / 2 + HINGE + 2)):              # hinge notch from the outside at the top
            Rectangle(1.2, 4, mode=Mode.SUBTRACT)
    part = extrude(sk.sketch, T)
    txt = extrude(Pos(x0 + 3, 0, T) * label, 0.6)
    return part + txt, w, h


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    allp, y = [], 0.0
    for x in STATIONS:
        g, w, h = gauge(x)
        print(f"station {x:5.0f}: stay {jig.sec(x)[0]:.1f} x {jig.sec(x)[1]:.1f}  hole {w:.1f} x {h:.1f}  valid {g.is_valid}")
        export_stl(g, str(OUT / f"gauge_{x:03d}.stl"))
        allp.append(Pos(0, y + h / 2 + WALLG, 0) * g)
        y += h + 2 * WALLG + 4
    export_stl(Compound(allp), str(OUT / "gauges_all.stl"))
    print("written", OUT)
