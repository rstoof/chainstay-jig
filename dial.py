"""
Dropout dial: reads the dropout spacing live while the spreader works, so you know when
to stop. A thread runs from an anchor on one dropout to a drum on the other; the drum
has a 100 mm circumference, so one turn of the needle = 100 mm and the bezel reads the
spacing straight off: 100 ... 199 mm. A second thread on the drum, wound the other way,
carries a hanging M8 nut that keeps the thread tight.

Both ends clamp in the axle slots with an M8 bolt (head on the inside, nut outside).
Set the bezel once: measure the inner-face spacing with a tape, turn the bezel until the
needle shows it.

Coordinates at dropout A: origin = axle bolt on A's inner face, +y toward dropout B,
+x rearward, +z up. The dial faces rearward, so you read it from behind the bike.

Run:  python dial.py   -> out/dial/*.stl, out/dial_assembly.png
"""
import math
from pathlib import Path
from build123d import *

FONT = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
R_STRING = 100 / (2 * math.pi)     # thread centre radius: 100 mm per turn
THREAD = 0.4
R_GROOVE = R_STRING - THREAD / 2
R_FLANGE = 18.0
BOLT_HOLE = 9.0
XD = 9.0             # dial plate behind the axle (clears the M8 head on the inside)
PLATE_T = 5.0
YD = 33.0            # drum axis, inward from A's inner face (and at axle height)
DISC_R = 33.0
PIN_D = 6.0
BZ_IN, BZ_OUT, BZ_T, BZ_RECESS = 19.0, 31.4, 2.2, 1.6   # bezel ring
NEEDLE_R = 30.8
GAP = 0.4            # bezel face to drum
F_T, G_W = 1.4, 2.2  # drum flange thickness, groove width
OUT = Path(__file__).parent / "out" / "dial"


def to_dial(shape):
    """Dial-local (X right, Y up, Z toward the viewer) -> bike frame at the drum axis."""
    return Location(Plane((XD + PLATE_T, YD, 0), x_dir=(0, 1, 0), z_dir=(1, 0, 0))) * shape


def body():
    # dial plate, built in dial-local coordinates (face at Z=0, plate behind it)
    plate = Pos(0, 0, -PLATE_T / 2) * Cylinder(DISC_R, PLATE_T)
    plate -= Pos(0, 0, -BZ_RECESS / 2) * (Cylinder(BZ_OUT + 0.25, BZ_RECESS) - Cylinder(BZ_IN - 0.25, BZ_RECESS))
    pin_l = BZ_T - BZ_RECESS + GAP + 3 * F_T + 2 * G_W + 4.0
    plate += Pos(0, 0, pin_l / 2) * Cylinder(PIN_D / 2, pin_l)
    plate += Pos(0, 0, 0.3) * Cylinder(PIN_D / 2 + 2.5, 0.6)          # thrust shoulder for the drum
    d = to_dial(plate)
    # tab in the xz plane against the dropout, holding the bolt
    tab = extrude(Plane.XZ * (Pos(0, 0) * Circle(12) + Pos((XD + PLATE_T) / 2 - 2, 0) * Rectangle(XD + PLATE_T + 4, 50)),
                  amount=-5.0)  # Plane.XZ normal is -y, so -5 grows toward +y
    tab -= Pos(0, 2.5, 0) * Rot(90, 0, 0) * Cylinder(BOLT_HOLE / 2, 10)
    tab = tab & Pos(0, 2.5, 0) * Box(200, 5, 200) & Pos(-50 + XD + PLATE_T - BZ_RECESS - 0.4, 0, 0) * Box(100, 50, 200)
    return d + tab


def bezel():
    ring = Pos(0, 0, BZ_T / 2) * (Cylinder(BZ_OUT, BZ_T) - Cylinder(BZ_IN, BZ_T))
    cuts = []
    for mm in range(100):
        a = math.radians(90 - 3.6 * mm)        # clockwise from the top, as seen from behind
        r0 = 26.4 if mm % 10 == 0 else 27.8 if mm % 5 == 0 else 29.0
        w = 0.9 if mm % 5 == 0 else 0.6
        r1 = BZ_OUT - 0.5
        cuts.append(Location(((r0 + r1) / 2 * math.cos(a), (r0 + r1) / 2 * math.sin(a), BZ_T),
                             (0, 0, math.degrees(a))) * Box(r1 - r0, w, 1.0))
        if mm % 10 == 0:
            t = Text(f"{100 + mm}", 3.6, font_path=FONT, align=(Align.CENTER, Align.CENTER))
            spin = math.degrees(a) - 90 + (180 if math.sin(a) < -0.01 else 0)   # bottom half reads upright too
            cuts.append(Location((23.0 * math.cos(a), 23.0 * math.sin(a), BZ_T - 0.5), (0, 0, spin)) * extrude(t, 1.0))
    return ring - cuts


def drum():
    """Back flange with the needle at Z=0 (faces the bezel), then two thread grooves."""
    z = 0.0
    parts = [Pos(0, 0, F_T / 2) * Cylinder(R_FLANGE, F_T)]
    needle = Pos(0, 0, F_T / 2) * extrude(Polygon((R_FLANGE - 3, -1.2), (NEEDLE_R - 2.5, -0.8), (NEEDLE_R, 0),
                                                    (NEEDLE_R - 2.5, 0.8), (R_FLANGE - 3, 1.2), align=None), F_T / 2, both=True)
    needle = Rot(0, 0, 90) * needle
    z = F_T
    for _ in range(2):
        parts.append(Pos(0, 0, z + G_W / 2) * Cylinder(R_GROOVE, G_W)); z += G_W
        parts.append(Pos(0, 0, z + F_T / 2) * Cylinder(R_FLANGE, F_T)); z += F_T
    d = Part() + parts + [needle]
    d -= Cylinder(PIN_D / 2 + 0.3, 3 * z)
    d -= Pos(0, 0, F_T / 2) * Cylinder(PIN_D / 2 + 2.8, F_T + 0.01)      # clears the shoulder
    # tie holes: axial hole + a notch from each groove into it
    for k, ang in enumerate((90, 270)):
        a = math.radians(ang)
        c = (13.0 * math.cos(a), 13.0 * math.sin(a))
        d -= Pos(*c, 0) * Cylinder(0.9, 3 * z)
        zg = F_T + G_W / 2 + k * (G_W + F_T)
        d -= Location(((13.0 + R_GROOVE) / 2 * math.cos(a), (13.0 + R_GROOVE) / 2 * math.sin(a), zg),
                      (0, 0, ang)) * Box(R_GROOVE - 13.0 + 1.0, 1.2, G_W)
    return d, z


def cap():
    c = Pos(0, 0, 1.5) * (Cylinder(PIN_D / 2 + 2.5, 3.0) - Pos(0, 0, 0.6) * Cylinder(PIN_D / 2 - 0.05, 3.0))
    return c


def anchor(x_eye, z_eye):
    """Clamps on dropout B (built at B's bolt, +y toward A here mirrored: plate at y in [-5, 0])."""
    prof = Pos(0, 0) * Circle(12) + Pos(x_eye, z_eye) * Circle(4.5)
    hull = make_hull(prof.edges())
    a = extrude(Plane.XZ * hull, amount=5.0)       # y from 0 to -5 (toward A it is mirrored later)
    a = Pos(0, 0, 0) * a
    a -= Rot(90, 0, 0) * Cylinder(BOLT_HOLE / 2, 20)
    a -= Pos(x_eye, 0, z_eye) * Rot(90, 0, 0) * Cylinder(0.9, 20)
    return a


def build(D=102.0):
    b = body()
    bz = to_dial(Pos(0, 0, -BZ_RECESS) * bezel())
    dr, dl = drum()
    z0 = BZ_T - BZ_RECESS + GAP
    drum_w = to_dial(Pos(0, 0, z0) * Rot(0, 0, -3.6 * (D - 100)) * dr)
    pin_l = BZ_T - BZ_RECESS + GAP + 3 * F_T + 2 * G_W + 4.0
    cp = to_dial(Pos(0, 0, pin_l - 2.4) * cap())
    x_g1 = XD + PLATE_T + z0 + F_T + G_W / 2          # first groove: thread to dropout B
    x_g2 = x_g1 + G_W + F_T                            # second groove: counterweight
    anc = Pos(0, D, 0) * anchor(x_g1, R_STRING)          # plate y in [D-5, D]
    return dict(body=b, bezel=bz, drum=drum_w, cap=cp, anchor=anc), (x_g1, x_g2)


def hardware(D, xg):
    x_g1, x_g2 = xg
    hw = []
    for y0, s in ((0.0, 1), (D, -1)):
        hw.append(Pos(0, y0 + s * (5 + 2.65), 0) * Rot(90, 0, 0) * Cylinder(6.5, 5.3))      # head inside
        hw.append(Pos(0, y0 - s * 45, 0) * Rot(90, 0, 0) * Cylinder(4, 100))
    thread1 = Pos(x_g1, 0, R_STRING) * Rot(90, 0, 0) * Pos(0, 0, -(YD + D - 5) / 2) * Cylinder(THREAD / 2, D - 5 - YD)
    thread2 = Pos(x_g2, YD - R_STRING, -45) * Cylinder(THREAD / 2, 90)
    nut = Pos(x_g2, YD - R_STRING, -95) * (extrude(RegularPolygon(13 / math.sqrt(3), 6), 3.25, both=True) - Cylinder(4, 8))
    dropouts = [Pos(25, y, 0) * Box(80, 5, 40) for y in (-2.5, D + 2.5)]
    return hw + [thread1, thread2, nut], dropouts


def picture(parts, path, elev=18, azim=25):
    import numpy as np, matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    fig = plt.figure(figsize=(9, 7), dpi=110)
    ax = fig.add_axes([0, 0, 1, 1], projection="3d")
    light = np.array([0.6, -0.3, 0.75]); light /= np.linalg.norm(light)
    allv = []
    for shape, col in parts:
        v, f = shape.tessellate(0.05)
        v = np.array([(p.X, p.Y, p.Z) for p in v]); t = v[np.array(f)]
        n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]); n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        sh = 0.35 + 0.65 * np.clip(np.abs(n @ light), 0, 1)
        c = np.array(matplotlib.colors.to_rgb(col))
        ax.add_collection3d(Poly3DCollection(t, facecolors=np.clip(c[None] * sh[:, None], 0, 1), edgecolors="none"))
        allv.append(v)
    v = np.concatenate(allv); lo, hi = v.min(0), v.max(0); c, r = (lo + hi) / 2, (hi - lo).max() / 2 * 0.62
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
    ax.set_box_aspect((1, 1, 1)); ax.view_init(elev, azim); ax.set_axis_off()
    fig.savefig(path); plt.close(fig)


def print_parts():
    """Each part flat on the bed (z up), as separate solids."""
    b = body()
    b = Rot(90, 0, 0) * b                      # tab face (y=0) -> bed... checked below
    out = {}
    bb = b.bounding_box()
    out["dial_body"] = Pos(-bb.center().X, -bb.center().Y, -bb.min.Z) * b
    out["dial_bezel"] = bezel()
    dr, _ = drum()
    out["dial_drum"] = dr
    out["dial_cap"] = cap()
    an = Rot(-90, 0, 0) * anchor(XD + PLATE_T + BZ_T - BZ_RECESS + GAP + F_T + G_W / 2, R_STRING)
    abb = an.bounding_box()
    out["dial_anchor"] = Pos(0, 0, -abb.min.Z) * an
    return out


def export_viewer(D=102.0):
    """STLs for the viewer's Dial mode (drum at D; the page turns it and moves dropout B)."""
    d = OUT.parent / "dial_view"; d.mkdir(exist_ok=True)
    parts, xg = build(D)
    hw, drops = hardware(D, xg)
    bolt_a, bolt_b = Compound(hw[0:2]), Compound(hw[2:4])
    for name, shp in (("body", parts["body"]), ("bezel", parts["bezel"]), ("drum", parts["drum"]), ("cap", parts["cap"]),
                      ("anchor", parts["anchor"]), ("bolt_a", bolt_a), ("bolt_b", bolt_b), ("thread1", hw[4]),
                      ("thread2", hw[5]), ("nut", hw[6]), ("drop_a", drops[0]), ("drop_b", drops[1])):
        export_stl(shp, str(d / f"{name}.stl"), tolerance=0.04, angular_tolerance=0.15)


def plate_all():
    """One print: 2 spreader jaws, the locator and the dial parts, all flat / standing as designed."""
    import spreader
    j = spreader.jaw()
    jaws = spreader.print_layout(j)
    loc = Rot(90, 0, 0) * spreader.locator()          # lies on its side
    pp = print_parts()
    items = [(jaws, (-80, 70)), (loc, (20, -80)), (pp["dial_body"], (10, 70)), (pp["dial_bezel"], (85, 60)),
             (pp["dial_drum"], (85, -5)), (pp["dial_anchor"], (-80, -5)), (pp["dial_cap"], (30, -5))]
    placed = []
    for shp, (cx, cy) in items:
        bb = shp.bounding_box()
        placed.append(Pos(cx - bb.center().X, cy - bb.center().Y, -bb.min.Z) * shp)
    for i in range(len(placed)):
        for k in range(i + 1, len(placed)):
            bi, bk = placed[i].bounding_box(), placed[k].bounding_box()
            sep = max(bk.min.X - bi.max.X, bi.min.X - bk.max.X, bk.min.Y - bi.max.Y, bi.min.Y - bk.max.Y)
            assert sep > 8, (i, k, sep)
    c = Compound(placed)
    bb = c.bounding_box()
    print(f"plate: {bb.size.X:.0f} x {bb.size.Y:.0f} x {bb.size.Z:.0f} mm")
    export_stl(c, str(OUT.parent / "spreader_set.stl"), tolerance=0.02, angular_tolerance=0.1)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    parts, xg = build(102.0)
    for k, v in parts.items():
        print(f"{k}: valid {v.is_valid}, volume {v.volume / 1000:.2f} cm3")
    # drum turns freely: no overlap with body / bezel / cap
    for a_, b_ in (("drum", "body"), ("drum", "bezel"), ("drum", "cap"), ("bezel", "body")):
        print(f"  {a_} x {b_}: overlap {(parts[a_] & parts[b_]).volume:.3f} mm3")
    hw, drops = hardware(102.0, xg)
    print(f"thread grooves at x = {xg[0]:.1f} / {xg[1]:.1f}; anchor eye at z = {R_STRING:.2f}")
    for k, v in parts.items():
        export_stl(v, str(OUT / f"{k}.stl"), tolerance=0.02, angular_tolerance=0.1)
    picture([(parts["body"], "#3a3a3a"), (parts["bezel"], "#d8d2c4"), (parts["drum"], "#c0392b"),
             (parts["cap"], "#3a3a3a"), (parts["anchor"], "#3a3a3a")] + [(h, "#d9b44a") for h in hw] +
            [(d, "#2f7a57") for d in drops], OUT.parent / "dial_assembly.png")
    for k, v in print_parts().items():
        bb = v.bounding_box()
        print(f"print {k}: {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f}, min z {bb.min.Z:.2f}")
        export_stl(v, str(OUT / f"print_{k}.stl"), tolerance=0.02, angular_tolerance=0.1)
    export_viewer()
    plate_all()
