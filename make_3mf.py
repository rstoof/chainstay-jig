"""
Orca Slicer project for the Qidi Q2 with both fitted dies, laid on their flat backs.

Takes all settings from a Siraya Tech PPA-CF Q2 project (pass its .3mf), but labels the
filament PAHT-CF (Qidi's own type and filament id), because the Q2 / QIDI Box only know
PAHT-CF. The Siraya PPA-CF profile is QIDI PAHT-GF + bed 100 + the PPA-CF label, so every
temperature, speed and flow value stays the PPA-CF one.

Filament tweaks from the Siraya PPA-CF user manual: bed 90, fans off, retraction 1 mm.
Chamber heated to 60, and the QIDI Box heated to 65 while printing (BOX_TEMP_SET).
Process: Siraya's "ST PPA-CF 0.20mm Standard @Qidi Q2", made stronger for a press die
(more walls and top/bottom layers, denser gyroid infill), plus a brim against warping.

Run:  python make_3mf.py "~/Downloads/Siraya Tech PPA-CF Q2 0.4mm 20251112.3mf"
      -> out/print/chainstay_dies_PPA-CF_Q2.3mf  (open in Orca, check, slice, print)
"""
import json, sys, zipfile
from pathlib import Path
import numpy as np

ROOT = Path(__file__).parent
OUT = ROOT / "out" / "print" / "chainstay_dies_PPA-CF_Q2.3mf"

FIL_NAME = "Siraya Tech PPA-CF (as PAHT-CF) @Qidi Q2 0.4 nozzle"
PAHT_CF_ID = "OFKgmsqE"      # QIDI PAHT-CF filament id in the Orca Qidi profiles
PROCESS = {                  # on top of Siraya's ST PPA-CF process
    "wall_loops": "6",
    "top_shell_layers": "6",
    "bottom_shell_layers": "12",   # the flat back on the bed is the tension skin when the die bends

    "sparse_infill_density": "50%",
    "sparse_infill_pattern": "gyroid",
    "brim_type": "outer_only",
    "brim_width": "5",
    # the inner die's back has a channel at the BB end (clears the other stay): support its roof
    "enable_support": "1",
    "support_type": "tree(auto)",
    "support_on_build_plate_only": "1",
    "support_threshold_angle": "40",
}
# Siraya Fibreheart PPA-CF user manual: nozzle 300-320, bed 70-90 (PEI), cooling fans off,
# 30-120 mm/s, retraction 1-3 mm. The Siraya Q2 profile has bed 100, fan 20 %, retraction 0.8.
FILAMENT = {
    "hot_plate_temp": "90",
    "hot_plate_temp_initial_layer": "90",
    "fan_max_speed": "0",
    "fan_min_speed": "0",
    "overhang_fan_speed": "0",
    "filament_retraction_length": "1",
    "filament_cost": "60",
    # heated chamber: with 0 the Q2 start macro runs the exhaust fan at full speed
    "chamber_temperature": "60",
    "activate_chamber_temp_control": "1",
}
# QIDI Box: heat the box with the spool of tool 0 while printing (what QIDI Studio writes
# for "box temperature control"). The box firmware caps it at the lowest box limit of the
# loaded slots' filament types: PAHT-CF 65, PLA 0 - so take the PLA spools out of that box.
BOX_TEMP = 65
BOX_GCODE = f"DISABLE_BOX_HEATER\nBOX_TEMP_SET VT0={BOX_TEMP}\n"
# (file, rotation so the flat back faces down, plate centre)
PARTS = [
    ("die_inner_fitted", "+x90", (135.0, 80.0)),    # back is -Y
    ("die_outer_fitted", "-x90", (135.0, 185.0)),   # back is +Y
]


def read_stl(p):
    b = Path(p).read_bytes()
    n = int.from_bytes(b[80:84], "little")
    a = np.frombuffer(b[84:84 + n * 50], dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]))
    return a["v"].astype(float).reshape(-1, 3)


def place(v, rot, c):
    x, y, z = v[:, 0], v[:, 1], v[:, 2]
    v = np.c_[x, -z, y] if rot == "+x90" else np.c_[x, z, -y]
    lo, hi = v.min(0), v.max(0)
    return v - [(lo[0] + hi[0]) / 2 - c[0], (lo[1] + hi[1]) / 2 - c[1], lo[2]]


def mesh_xml(i, v):
    uv, inv = np.unique(v.round(5), axis=0, return_inverse=True)
    tri = inv.reshape(-1, 3)
    vs = "\n".join(f'<vertex x="{a:.5f}" y="{b:.5f}" z="{c:.5f}"/>' for a, b, c in uv)
    ts = "\n".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in tri)
    return f'<object id="{i}" type="model"><mesh><vertices>\n{vs}\n</vertices><triangles>\n{ts}\n</triangles></mesh></object>'


def main(template):
    zin = zipfile.ZipFile(Path(template).expanduser())
    cfg = json.loads(zin.read("Metadata/project_settings.config"))
    assert cfg["filament_type"] == ["PPA-CF"] and "Q2" in cfg["printer_settings_id"], "not the Siraya PPA-CF Q2 project"
    cfg["filament_type"] = ["PAHT-CF"]
    cfg["filament_ids"] = [PAHT_CF_ID]
    cfg["filament_settings_id"] = [FIL_NAME]
    cfg.update(PROCESS)
    cfg.update({k: [v] for k, v in FILAMENT.items()})
    if "BOX_TEMP_SET" not in cfg["machine_start_gcode"]:
        cfg["machine_start_gcode"] = BOX_GCODE + cfg["machine_start_gcode"]
    d = cfg["different_settings_to_system"]
    d[0] = ";".join(sorted(set(filter(None, d[0].split(";"))) | set(PROCESS)))
    d[2] = ";".join(sorted(set(filter(None, d[2].split(";"))) | {"machine_start_gcode"}))
    d[1] = ";".join(sorted(set(filter(None, d[1].split(";"))) | {"filament_type"} | set(FILAMENT)))
    cfg["different_settings_to_system"] = d

    fil = json.loads(zin.read("Metadata/filament_settings_9.config"))
    assert fil["name"] == "Siraya Tech PPA-CF @Qidi Q2 0.4 nozzle"
    fil.update(filament_type=["PAHT-CF"], filament_settings_id=[FIL_NAME], name=FIL_NAME, filament_ids=[PAHT_CF_ID])
    fil.update({k: [v] for k, v in FILAMENT.items()})
    proc = json.loads(zin.read("Metadata/process_settings_6.config"))
    assert proc["name"] == "ST PPA-CF 0.20mm Standard @Qidi Q2"
    proc.update(PROCESS)

    objs, ms = [], ['<?xml version="1.0" encoding="UTF-8"?>', "<config>"]
    for i, (name, rot, c) in enumerate(PARTS, 1):
        v = place(read_stl(ROOT / "out" / f"{name}.stl"), rot, c)
        print(f"{name}: {np.ptp(v[:, 0]):.1f} x {np.ptp(v[:, 1]):.1f} x {np.ptp(v[:, 2]):.1f} mm")
        objs.append(mesh_xml(i, v))
        ms += [f' <object id="{i}">', f'  <metadata key="name" value="{name}"/>', '  <metadata key="extruder" value="1"/>',
               '  <part id="1" subtype="normal_part">', f'   <metadata key="name" value="{name}"/>',
               '   <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>', '  </part>', ' </object>']
    ms += [" <plate>", '  <metadata key="plater_id" value="1"/>', '  <metadata key="locked" value="false"/>',
           '  <metadata key="filament_map_mode" value="Auto For Flush"/>', '  <metadata key="filament_maps" value="1"/>']
    for i in range(1, len(PARTS) + 1):
        ms += ["  <model_instance>", f'   <metadata key="object_id" value="{i}"/>', '   <metadata key="instance_id" value="0"/>',
               f'   <metadata key="identify_id" value="{100 + i}"/>', "  </model_instance>"]
    ms += [" </plate>", "</config>"]

    model = ('<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
             'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021">\n'
             ' <metadata name="Application">OrcaSlicer-2.5.2</metadata>\n'
             ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
             ' <metadata name="Title">Chainstay jig dies</metadata>\n <resources>\n' + "\n".join(objs) +
             '\n </resources>\n <build>\n' + "\n".join(f'  <item objectid="{i}" printable="1"/>' for i in range(1, len(PARTS) + 1)) +
             "\n </build>\n</model>\n")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", zin.read("[Content_Types].xml"))
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
                   ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n</Relationships>')
        z.writestr("3D/3dmodel.model", model)
        z.writestr("Metadata/model_settings.config", "\n".join(ms))
        z.writestr("Metadata/project_settings.config", json.dumps(cfg, indent=4))
        z.writestr("Metadata/filament_settings_1.config", json.dumps(fil, indent=4))
        z.writestr("Metadata/process_settings_1.config", json.dumps(proc, indent=4))
    print("written", OUT)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "~/Downloads/Siraya Tech PPA-CF Q2 0.4mm 20251112.3mf")
