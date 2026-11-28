"""
Chainstay spreader: a twin-screw jack that pushes the two chainstays apart just behind
bend 2 (100-140 mm from the lug end), to re-make the outward angle at the BB end that
sprang back, and bring the dropouts back out.

Two identical C-shaped jaws. Each cradles the inner half of a stay (lofted from the
gauge-measured SECTIONS) and hooks over its top and bottom with ears. The screws run
across ABOVE and BELOW the stays, where there is room: between the stays there is only
~38 mm. Uses the jig hardware: 2x M8x100 fully threaded + 2x M8 nut + 2x DIN 125 M8
washer (16 mm).

Jaw A, top ear: captive nut - the bolt goes in from outboard, its tip pushes jaw B.
Jaw A, bottom ear: socket - the bottom bolt comes from jaw B's side and its tip bears
on a steel washer in a slot (not on plastic). Jaw B = jaw A turned 180 deg about the
stay axis, so both jaws are the same part: print 2.

Run:  python spreader.py   -> out/spreader_jaw.stl, out/spreader_assembly.png
"""
import math
from pathlib import Path
from build123d import *
import jig

X0, X1 = 100.0, 140.0    # contact, from the lug end: behind bend 2 (82-100) and the dimple
LJ = X1 - X0             # jaw length along the stay
CLR = 0.4                # total clearance on the cradle (a layer of tape on the stay is fine)
BODY = 6.0               # PPA between the stay's inner face and the jaw's inner face
H_MAX = max(jig.sec(x)[1] for x in (X0, X1))
W_MID = jig.sec((X0 + X1) / 2)[0]
YC = -W_MID / 2          # stay centre (local y; the stay's inner face is at y = 0)
ZE0 = H_MAX / 2 + CLR / 2 + 0.4    # ears start above / below the stay
NUT_AF, NUT_T = 13.3, 6.9          # M8 nut pocket (13 AF, 6.5 thick)
NUT_R = NUT_AF / math.sqrt(3)      # hex corner radius
ZB = ZE0 + 2.5 + NUT_R             # screw axis height
HZ = ZB + NUT_R + 3.0              # half jaw height
EAR_OUT = YC - 7.0                 # ears reach 7 mm outboard of the stay centre
BOLT_D = 8.6
NUT_Y = (-10.4, -3.5)              # nut pocket, y range (over the stay)
SOCK_D, SOCK_L = 10.0, 10.0        # bolt-tip bore into the socket ear (room for jaw yaw)
WASH_D, WASH_T = 16.7, 2.4         # DIN 125 M8 washer slot (16 x 1.6)
OUT = Path(__file__).parent / "out"


def cradle():
    """Stay + CLR, lofted along x from the measured sections (a bit past both ends)."""
    secs = []
    for xl in (-1.0, 125.0 - X0, LJ + 1.0):   # 125 = a measured station
        w, h = jig.sec(X0 + xl)
        secs.append(Plane.YZ.offset(xl) * Pos(YC, 0) * Ellipse((w + CLR) / 2, (h + CLR) / 2))
    return loft(secs)


def box(x0, x1, y0, y1, z0, z1):
    return Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(x1 - x0, y1 - y0, z1 - z0)


def ybore(d, y0, y1, z):
    return Pos(LJ / 2, (y0 + y1) / 2, z) * Rot(90, 0, 0) * Cylinder(d / 2, y1 - y0)


def jaw():
    body = box(0, LJ, YC, BODY, -HZ, HZ)                   # not past the stay centre: slides on
    for s in (1, -1):
        z0, z1 = sorted((s * ZE0, s * HZ))
        body += box(0, LJ, EAR_OUT, BODY, z0, z1)
    body -= cradle()
    body = fillet(body.edges().filter_by(Axis.X).group_by(Axis.Y)[0], 2.0)  # outboard ear edges

    # top ear: captive nut + through bore
    body -= ybore(BOLT_D, EAR_OUT - 1, BODY + 1, ZB)
    nut = Pos(LJ / 2, sum(NUT_Y) / 2, ZB) * Rot(90, 0, 0) * Rot(0, 0, 30) * \
        extrude(RegularPolygon(NUT_R, 6), NUT_T / 2, both=True)
    body -= nut
    body -= box(LJ / 2 - NUT_AF / 2, LJ / 2 + NUT_AF / 2, *NUT_Y, ZB, HZ + 1)   # drop-in slot

    # bottom ear: socket for the other bolt's tip, washer slot open downwards
    body -= ybore(SOCK_D, BODY - SOCK_L, BODY + 1, -ZB)
    wy1 = BODY - SOCK_L
    body -= box(LJ / 2 - WASH_D / 2, LJ / 2 + WASH_D / 2, wy1 - WASH_T, wy1 + 0.01, -HZ - 1, -ZB + WASH_D / 2)
    body -= Pos(LJ / 2, wy1 - WASH_T / 2, -ZB) * Rot(90, 0, 0) * Cylinder(WASH_D / 2, WASH_T)

    # BB arrow + label on the inner face (which way round it goes)
    txt = Plane.XZ.offset(-BODY) * Pos(LJ / 2, 0) * Text("< BB", 6.0, align=(Align.CENTER, Align.CENTER))
    body -= extrude(txt, amount=-0.6)
    return body


def report(j):
    print(f"jaw {LJ:.0f} x {BODY - EAR_OUT:.1f} x {2 * HZ:.1f} mm, volume {j.volume / 1000:.1f} cm3, valid {j.is_valid}")
    print(f"screw axes at z = +-{ZB:.1f} (stay top at {H_MAX / 2:.1f}), ears from {ZE0:.1f}")
    for g in (32, 38, 45, 52):
        inside = g + (-EAR_OUT) + (-(BODY - SOCK_L))
        print(f"  stay gap {g} mm: jaw faces {g - 2 * BODY:.0f} mm apart, M8x100 has {100 - inside:.0f} mm of travel left")


def assembly(j, gap):
    a = Pos(0, -gap / 2, 0) * j
    b = Pos(0, gap / 2, 0) * Rot(180, 0, 0) * j
    stays = []
    for s in (-1, 1):
        secs = [Plane.YZ.offset(xl) * Pos(s * (gap / 2 + jig.sec(X0 + xl)[0] / 2), 0) *
                Ellipse(jig.sec(X0 + xl)[0] / 2, jig.sec(X0 + xl)[1] / 2) for xl in (-35.0, 0.0, 25.0, 50.0, 75.0)]
        stays.append(loft(secs))
    inside = gap - EAR_OUT - (BODY - SOCK_L)
    bolts = []
    for s in (1, -1):   # top bolt from A's side (-y), bottom bolt from B's side (+y)
        y_tip = s * (gap / 2 - (BODY - SOCK_L) + 0.8)
        y_head = y_tip - s * 100
        bolts.append(Pos(LJ / 2, (y_tip + y_head) / 2, s * ZB) * Rot(90, 0, 0) * Cylinder(4, 100))
        bolts.append(Pos(LJ / 2, y_head - s * 2.65, s * ZB) * Rot(90, 0, 0) * Rot(0, 0, 30) *
                     extrude(RegularPolygon(13 / math.sqrt(3), 6), 2.65, both=True))
    return a, b, stays, bolts


def picture(parts, path):
    import numpy as np, matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    fig = plt.figure(figsize=(9, 7), dpi=110)
    ax = fig.add_axes([0, 0, 1, 1], projection="3d")
    light = np.array([-0.3, -0.5, 0.8]); light /= np.linalg.norm(light)
    allv = []
    for shape, col in parts:
        v, f = shape.tessellate(0.1)
        v = np.array([(p.X, p.Y, p.Z) for p in v]); t = v[np.array(f)]
        n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]); n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        sh = 0.35 + 0.65 * np.clip(np.abs(n @ light), 0, 1)
        c = np.array(matplotlib.colors.to_rgb(col))
        ax.add_collection3d(Poly3DCollection(t, facecolors=np.clip(c[None] * sh[:, None], 0, 1), edgecolors="none"))
        allv.append(v)
    v = np.concatenate(allv); lo, hi = v.min(0), v.max(0); c, r = (lo + hi) / 2, (hi - lo).max() / 2 * 0.72
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
    ax.set_box_aspect((1, 1, 1)); ax.view_init(24, -58); ax.set_axis_off()
    fig.savefig(path); plt.close(fig)


def print_layout(j):
    """Two jaws standing on their BB end (stay axis vertical: cradle walls need no support)."""
    jaws = []
    for k in (-1, 1):
        r = Rot(0, -90, 0) * j                       # +x (along the stay) -> +z
        bb = r.bounding_box()
        jaws.append(Pos(-bb.center().X, -bb.center().Y + k * 18, -bb.min.Z) * r)
    return Compound(jaws)


def export_viewer(j, gap=38.0):
    """STLs for the 'Spreader' mode of viewer/index.html (make_viewer.py embeds them)."""
    d = OUT / "spreader"; d.mkdir(exist_ok=True)
    a, b, stays, bolts = assembly(j, gap)
    my = sum(NUT_Y) / 2
    hexnut = lambda: Rot(90, 0, 0) * Rot(0, 0, 30) * (extrude(RegularPolygon(13 / math.sqrt(3), 6), 3.25, both=True)
                                                      - Cylinder(4, 8))
    nuts = [Pos(LJ / 2, -gap / 2 + my, ZB) * hexnut(), Pos(LJ / 2, gap / 2 - my, -ZB) * hexnut()]
    wy = BODY - SOCK_L - 0.8 - 0.8          # washer centre (local), outboard of the bolt tip
    washer = lambda: Rot(90, 0, 0) * (Cylinder(8, 1.6) - Cylinder(4.2, 1.6))
    washers = [Pos(LJ / 2, -gap / 2 + wy, -ZB) * washer(), Pos(LJ / 2, gap / 2 - wy, ZB) * washer()]
    # bolts[0:2] = top bolt + head (pushes jaw B), bolts[2:4] = bottom bolt + head (pushes jaw A)
    for name, shp in (("jaw_a", a), ("jaw_b", b), ("stay_a", stays[0]), ("stay_b", stays[1]),
                      ("bolt_top", Compound(bolts[0:2])), ("bolt_bot", Compound(bolts[2:4])),
                      ("nut_top", nuts[0]), ("nut_bot", nuts[1]), ("washer_a", washers[0]), ("washer_b", washers[1])):
        export_stl(shp, str(d / f"{name}.stl"), tolerance=0.05, angular_tolerance=0.2)


if __name__ == "__main__":
    j = jaw()
    report(j)
    export_stl(j, str(OUT / "spreader_jaw.stl"), tolerance=0.02, angular_tolerance=0.1)
    a, b, stays, bolts = assembly(j, 38.0)
    for o in (a, b):
        for s in stays + bolts:
            ov = (o & s).volume
            if ov > 1e-3:
                print(f"  overlap {ov:.2f} mm3")
    picture([(a, "#3a3a3a"), (b, "#3a3a3a")] + [(s, "#b0b6c0") for s in stays] + [(s, "#d9b44a") for s in bolts],
            OUT / "spreader_assembly.png")
    export_viewer(j)
    export_stl(print_layout(j), str(OUT / "spreader_jaws_x2.stl"), tolerance=0.02, angular_tolerance=0.1)
    print("written", OUT / "spreader_jaw.stl", OUT / "spreader_jaws_x2.stl")

