"""
Wrap a CLI-sliced G-code into a .gcode.3mf like Orca's "send to printer", so the Qidi
screen shows a preview. The Orca CLI cannot render thumbnails (no OpenGL), so the plate
images and the G-code thumbnail are rendered here with matplotlib.

Run:  python gcode3mf.py project.3mf plate_1.gcode out.gcode.3mf
"""
import hashlib, io, re, sys, zipfile, base64
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


def meshes_from_3mf(p):
    z = zipfile.ZipFile(p)
    tris = []
    for body in re.findall(r"<mesh>(.*?)</mesh>", z.read("3D/3dmodel.model").decode(), re.S):
        v = np.array(re.findall(r'<vertex x="([-\d.e]+)" y="([-\d.e]+)" z="([-\d.e]+)"', body), float)
        t = np.array(re.findall(r'<triangle v1="(\d+)" v2="(\d+)" v3="(\d+)"', body), int)
        tris.append(v[t])
    return np.concatenate(tris)


def render(tris, size, colour="#060606", elev=35, azim=-60):
    """Shaded isometric view on a transparent background, PNG bytes."""
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    light = np.array([-0.4, -0.6, 0.7]); light /= np.linalg.norm(light)
    shade = 0.35 + 0.65 * np.clip(n @ light, 0, 1)
    base = np.array(matplotlib.colors.to_rgb(colour))
    base = np.maximum(base, 0.6)         # black filament would vanish on the dark screen
    cols = np.clip(base[None] * shade[:, None], 0, 1)
    fig = plt.figure(figsize=(size / 100, size / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1], projection="3d")
    ax.add_collection3d(Poly3DCollection(tris, facecolors=cols, edgecolors="none"))
    lo, hi = tris.reshape(-1, 3).min(0), tris.reshape(-1, 3).max(0)
    c, r = (lo + hi) / 2, (hi - lo).max() / 2
    ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
    ax.set_box_aspect((1, 1, 1)); ax.view_init(elev, azim); ax.set_axis_off()
    fig.patch.set_alpha(0); ax.patch.set_alpha(0)
    buf = io.BytesIO(); fig.savefig(buf, format="png", transparent=True); plt.close(fig)
    return buf.getvalue()


def add_gcode_thumbnail(gcode, png, w, h):
    b64 = base64.b64encode(png).decode()
    lines = [f"; {b64[i:i + 78]}" for i in range(0, len(b64), 78)]
    block = ["; THUMBNAIL_BLOCK_START", "", ";", f"; thumbnail begin {w}x{h} {len(b64)}", *lines,
             "; thumbnail end", "; THUMBNAIL_BLOCK_END", ""]
    marker = "; HEADER_BLOCK_END\n"
    i = gcode.index(marker) + len(marker)
    return gcode[:i] + "\n" + "\n".join(block) + gcode[i:]


def main(project, gcode_path, out):
    tris = meshes_from_3mf(project)
    zin = zipfile.ZipFile(project)
    colour = re.search(r'"filament_colour": \[\s*"(#[0-9A-Fa-f]{6})', zin.read("Metadata/project_settings.config").decode())
    colour = colour.group(1) if colour else "#808080"
    gcode = Path(gcode_path).read_text()
    if "thumbnail begin" not in gcode:
        gcode = add_gcode_thumbnail(gcode, render(tris, 150, colour), 150, 150)
    gbytes = gcode.encode()
    big, small = render(tris, 512, colour), render(tris, 128, colour)

    ms = zin.read("Metadata/model_settings.config").decode()
    ms = ms.replace('  <metadata key="filament_maps"', '  <metadata key="gcode_file" value="Metadata/plate_1.gcode"/>\n'
                    '  <metadata key="thumbnail_file" value="Metadata/plate_1.png"/>\n  <metadata key="filament_maps"', 1)
    t = re.search(r"estimated printing time \(normal mode\) = (.*)", gcode)
    w = re.search(r"total filament used \[g\] = ([\d.]+)", gcode)
    secs = sum(int(n) * {"d": 86400, "h": 3600, "m": 60, "s": 1}[u] for n, u in re.findall(r"(\d+)([dhms])", t.group(1))) if t else 0
    slice_info = ('<?xml version="1.0" encoding="UTF-8"?>\n<config>\n  <header>\n'
                  '    <header_item key="X-BBL-Client-Type" value="slicer"/>\n    <header_item key="OrcaSlicer-Version" value="2.5.2"/>\n'
                  '  </header>\n  <plate>\n    <metadata key="index" value="1"/>\n    <metadata key="printer_model_id" value="Qidi-Q2"/>\n'
                  '    <metadata key="nozzle_diameters" value="0.4"/>\n'
                  f'    <metadata key="prediction" value="{secs}"/>\n    <metadata key="weight" value="{w.group(1) if w else 0}"/>\n'
                  '  </plate>\n</config>\n')

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for it in zin.infolist():
            if it.filename in ("_rels/.rels", "Metadata/model_settings.config"):
                continue
            z.writestr(it, zin.read(it.filename))
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                   ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
                   ' <Relationship Target="/Metadata/plate_1.png" Id="rel-2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/thumbnail"/>\n'
                   ' <Relationship Target="/Metadata/plate_1.png" Id="rel-4" Type="http://schemas.bambulab.com/package/2021/cover-thumbnail-middle"/>\n'
                   ' <Relationship Target="/Metadata/plate_1_small.png" Id="rel-5" Type="http://schemas.bambulab.com/package/2021/cover-thumbnail-small"/>\n</Relationships>')
        z.writestr("Metadata/_rels/model_settings.config.rels", '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                   ' <Relationship Target="/Metadata/plate_1.gcode" Id="rel-1" Type="http://schemas.bambulab.com/package/2021/gcode"/>\n</Relationships>')
        z.writestr("Metadata/model_settings.config", ms)
        z.writestr("Metadata/plate_1.gcode", gbytes)
        z.writestr("Metadata/plate_1.gcode.md5", hashlib.md5(gbytes).hexdigest().upper())
        z.writestr("Metadata/plate_1.png", big)
        z.writestr("Metadata/plate_no_light_1.png", big)
        z.writestr("Metadata/plate_1_small.png", small)
        z.writestr("Metadata/slice_info.config", slice_info)
    print("written", out)


if __name__ == "__main__":
    main(*sys.argv[1:4])
