import os
import sys
import FreeCAD as App
import Part
import Import

# Postprocess the lower layer without scaling existing USB, vent, or boss details.
sys.path.insert(0, "/Users/bytedance/Documents/New project")
from raise_co2_layer import raise_lower_layer
from horizontal_supports import add_horizontal_supports, export_closed_button
from flush_screen_bezel import apply_flush_bezel
from flatten_bezel_underside import apply_planar_underside, export_planar_bezel
from space_side_vents import space_side_vents
from relieve_all_corner_columns import apply_all_corner_flats


OUT_DIR = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
STEP_PATH = os.path.join(OUT_DIR, "ESP32-S3-LCD-1.47B.stp")
SCD41_STEP_PATH = os.path.join(
    OUT_DIR, "Sensirion_CO2_Sensors_SEK-SCD41_STEP_file.STEP"
)
FCSTD_PATH = os.path.join(OUT_DIR, "ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd")
BASE_STL_PATH = os.path.join(OUT_DIR, "ESP32-S3-LCD-1.47B_紧凑双层外壳_后壳.stl")
LID_STL_PATH = os.path.join(OUT_DIR, "ESP32-S3-LCD-1.47B_紧凑双层外壳_前盖.stl")
BOTTOM_STL_PATH = os.path.join(
    OUT_DIR, "ESP32-S3-LCD-1.47B_紧凑双层外壳_可拆底盖.stl"
)
BUTTON_STL_PATH = os.path.join(
    OUT_DIR, "ESP32-S3-LCD-1.47B_紧凑双层外壳_按键顶杆_打印2件.stl"
)
PREVIEW_PATH = os.path.join(OUT_DIR, "ESP32-S3-LCD-1.47B_紧凑双层外壳_预览.png")
FRONT_PREVIEW_PATH = os.path.join(
    OUT_DIR, "ESP32-S3-LCD-1.47B_紧凑双层外壳_正面嵌入预览.png"
)


def doc_or_none(name):
    try:
        return App.getDocument(name)
    except NameError:
        return None


def rounded_prism(width, depth, height, radius, z=0.0, cx=0.0, cy=0.0):
    x0 = cx - width / 2.0
    y0 = cy - depth / 2.0
    result = Part.makeBox(width - 2 * radius, depth, height,
                          App.Vector(x0 + radius, y0, z))
    result = result.fuse(Part.makeBox(width, depth - 2 * radius, height,
                                      App.Vector(x0, y0 + radius, z)))
    for x in (x0 + radius, x0 + width - radius):
        for y in (y0 + radius, y0 + depth - radius):
            result = result.fuse(Part.makeCylinder(radius, height,
                                                    App.Vector(x, y, z)))
    return result.removeSplitter()


def horizontal_capsule_cut_x(length_x, width_y, height_z, x0, cy, cz):
    """Create an X-directed cut with a capsule profile in the YZ plane."""
    radius = height_z / 2.0
    straight = width_y - 2.0 * radius
    result = Part.makeBox(
        length_x,
        straight,
        height_z,
        App.Vector(x0, cy - straight / 2.0, cz - radius),
    )
    for y in (cy - straight / 2.0, cy + straight / 2.0):
        result = result.fuse(
            Part.makeCylinder(
                radius,
                length_x,
                App.Vector(x0, y, cz),
                App.Vector(1, 0, 0),
            )
        )
    return result.removeSplitter()


def rounded_wire(width, depth, radius, z=0.0, cx=0.0, cy=0.0):
    """Return a closed rounded-rectangle wire for lofted openings."""
    wafer = rounded_prism(width, depth, 0.01, radius, z, cx, cy)
    top_face = max(wafer.Faces, key=lambda face: face.CenterOfMass.z)
    return top_face.OuterWire


def relieve_pcb_columns(shell, board, centers, tower_radius, tap_radius,
                       clearance=0.30, minimum_wall=1.50, relief_bottom_z=None):
    """Use a single vertical 45-degree cut on each PCB-facing column side.

    The relief opens through the top of the shell, rather than forming a
    closed groove that would still obstruct the PCB edge during insertion.
    Measure clearance against the actual PCB, not a bounding rectangle.
    Reject a cut leaving too little wall even at the M2.5 nominal diameter.
    """
    candidates = [s for s in board.Solids
                  if s.BoundBox.XLength > 30 and s.BoundBox.YLength > 18
                  and abs(s.BoundBox.ZLength - 0.8) < 0.005]
    if len(candidates) != 1:
        raise RuntimeError("无法唯一识别 ESP32 PCB，停止螺丝柱避让")
    pcb = candidates[0]
    top = max((f for f in pcb.Faces if f.BoundBox.ZLength < 1e-5),
              key=lambda f: f.CenterOfMass.z)
    outline = Part.Face(top.OuterWire)
    z0 = pcb.BoundBox.ZMin - clearance if relief_bottom_z is None else relief_bottom_z
    if not shell.BoundBox.ZMin <= z0 < pcb.BoundBox.ZMin:
        raise RuntimeError("避让下沿必须位于主体范围内且低于 PCB")
    z1 = shell.BoundBox.ZMax + 0.1
    shell_z = shell.BoundBox.ZMin
    shell_height = shell.BoundBox.ZLength
    columns = [Part.makeCylinder(tower_radius, shell_height,
                                App.Vector(x, y, shell_z)) for x, y in centers]
    if any(x >= 0 for x, y in centers):
        raise RuntimeError("45度避让仅适用于当前左侧两根角柱")
    distances = []
    for x, y in centers:
        angle = 45.0 if y < 0 else -45.0
        aligned = outline.copy()
        aligned.translate(App.Vector(-x, -y, 0))
        aligned.rotate(App.Vector(), App.Vector(0, 0, 1), -angle)
        distances.append(aligned.BoundBox.XMin - clearance)
    # Share one offset so both cuts are exactly mirror-symmetric despite
    # micrometre-scale asymmetry in the imported PCB model.
    distance = min(distances)
    cutters = []
    for (x, y), column in zip(centers, columns):
        angle = 45.0 if y < 0 else -45.0
        halfspace = Part.makeBox(20, 40, z1 - z0,
                                 App.Vector(distance, -20, z0))
        halfspace.rotate(App.Vector(), App.Vector(0, 0, 1), angle)
        halfspace.translate(App.Vector(x, y, 0))
        cutters.append(halfspace.common(column))
    cutter = Part.makeCompound(cutters)
    walls = [Part.makeCylinder(tap_radius, shell_height,
                              App.Vector(x, y, shell_z)).distToShape(cutter)[0]
             for x, y in centers]
    nominal_walls = [Part.makeCylinder(1.25, shell_height,
                                      App.Vector(x, y, shell_z)).distToShape(cutter)[0]
                     for x, y in centers]
    if min(walls + nominal_walls) < minimum_wall - 1e-6:
        raise RuntimeError("PCB 避让将使通孔壁厚不足 %.2f mm" % minimum_wall)
    result = shell.cut(cutter).removeSplitter()
    if not result.isValid() or len(result.Solids) != 1:
        raise RuntimeError("PCB 避让后侧壁主体不是有效的单一实体")
    for column in columns:
        if result.common(column).distToShape(pcb)[0] < clearance - 1e-6:
            raise RuntimeError("螺丝柱与 PCB 的避让间隙不足")
    return result, cutter, pcb, {
        "clearance": clearance, "min_wall": min(walls), "bottom_z": z0,
        "min_nominal_thread_wall": min(nominal_walls), "plane_offset": distance,
        "removed_volume": shell.cut(result).Volume,
    }


def bottom_vent_pattern(mounts, diameter=1.5, pitch=3.0, count=7,
                        head_radius=2.55, minimum_web=1.5):
    """Symmetric circular-hole grid, with protected screw-head pockets."""
    radius = diameter / 2.0
    limit_squared = (radius + head_radius + minimum_web)**2
    axis = [(i - (count - 1) / 2.0) * pitch for i in range(count)]
    return [(x, y) for x in axis for y in axis
            if all((x - mx)**2 + (y - my)**2 >= limit_squared
                   for mx, my in mounts)]


def make_side_button(side, outer_d, center_x, center_z):
    """Create an inside-loaded plunger with a single continuous inner collar.

    The collar combines the outward travel stop and switch contact surface.
    Only the thin stem passes through the shell, allowing installation from
    inside before the board and front cover are fitted.
    """
    outer_face = outer_d / 2.0
    switch_face = 11.36
    tip_gap = 0.30
    stem_d = 3.00
    outer_projection = 2.00
    collar_d = 5.80

    contact_inner = switch_face + tip_gap
    stop_outer = outer_face - 2.2 - 1.50 - 0.20
    stem_outer = outer_face + outer_projection
    axis = App.Vector(0, side, 0)

    # Continuous 3 mm stem: the exposed end is the finger button.  It enters
    # the 3.4 mm shell bore from the enclosure interior.
    stem_base = App.Vector(center_x, side * contact_inner, center_z)
    stem = Part.makeCylinder(
        stem_d / 2.0,
        stem_outer - contact_inner,
        stem_base,
        axis,
    )

    collar = Part.makeCylinder(
        collar_d / 2.0,
        stop_outer - contact_inner,
        App.Vector(center_x, side * contact_inner, center_z),
        axis,
    )
    return stem.fuse(collar).removeSplitter()


# Reuse the already-open STEP document where possible. This is more stable than
# importing a 15 MB STEP repeatedly on macOS.
source = doc_or_none("Unnamed")
source_object = source.getObject("ESP32_S3_LCD_1_47B_ASM") if source else None
if source_object is None or not hasattr(source_object, "Shape") or source_object.Shape.isNull():
    source = doc_or_none("ESP32_STEP_Source_Compact")
    if source is None:
        source = App.newDocument("ESP32_STEP_Source_Compact")
        Import.insert(STEP_PATH, source.Name)
    source_object = source.getObject("ESP32_S3_LCD_1_47B_ASM")
if source_object is None or not hasattr(source_object, "Shape") or source_object.Shape.isNull():
    # Some FreeCAD import configurations expand the STEP assembly into many
    # feature objects instead of creating the named top-level assembly.  Build
    # one compound so the same real geometry and coordinate system are used.
    source_parts = [
        obj for obj in source.Objects
        if hasattr(obj, "Shape") and not obj.Shape.isNull()
    ]
    if not source_parts:
        raise RuntimeError("无法读取 ESP32 STEP 总成")
    source_object = source.addObject("PartDesign::Feature", "ESP32_S3_LCD_1_47B_ASM")
    source_object.Label = "ESP32-S3-LCD-1.47B STEP 总成"
    source_object.Shape = Part.makeCompound([obj.Shape.copy() for obj in source_parts])


doc_name = "ESP32_Compact_Stacked_Enclosure"
old = doc_or_none(doc_name)
if old:
    App.closeDocument(old.Name)
doc = App.newDocument(doc_name, "ESP32-S3-LCD-1.47B 紧凑双层外壳")

# Compact portrait/stacked layout (mm). The board is rotated 90 degrees, so its
# 37.58 mm long edge follows the enclosure's 45.4 mm long edge.
outer_w = 45.4
outer_d = 33.9
base_h = 25.0
lid_t = 3.0
wall = 2.2
floor = 2.0
corner_r = 4.0
# Keep the existing internal cavity and deck; only the external corners change.
inner_corner_r = 3.0
fit_gap = 0.30
# SCD41 breakout reference: 25.4 x 22.86 mm PCB outline; the user specified
# a 20 x 18 mm mounting-hole center pattern (long x short edge), not inches.
# The sensor can is roughly
# 10.1 x 10.1 x 6.5 mm and the complete assembled board is about 7.7 mm high.
sensor_w = 25.4
sensor_d = 22.86
sensor_h = 7.7
sensor_standoff_h = 1.0
sensor_z = floor + sensor_standoff_h
sensor_mount_spacing_long = 20.0
sensor_mount_spacing_short = 18.0
sensor_mount_inset_x = (sensor_w - sensor_mount_spacing_long) / 2.0
sensor_mount_inset_y = (sensor_d - sensor_mount_spacing_short) / 2.0
sensor_mount_boss_radius = 2.5
sensor_mount_clearance_radius = 1.4
sensor_head_pocket_radius = 2.55
sensor_head_pocket_depth = 1.40
board_min_z = 16.7
pcb_length = 36.37
pcb_width = 20.32
header_pitch = 2.54
header_row_y = 17.78 / 2.0
header_pin_count = 9
header_pin_x0 = -14.049
header_row_center_x = -3.889
header_pin_diameter = 1.3
header_pin_bottom_z = 10.5
deck_z = 13.5
deck_t = 2.0
pcb_boss_radius = 1.7
pcb_mount_through_radius = 1.10

# Rear shell with open front. Z is the front/back stack direction.
outer = rounded_prism(outer_w, outer_d, base_h, corner_r)
inner = rounded_prism(outer_w - 2 * wall, outer_d - 2 * wall,
                      base_h - floor + 0.5, inner_corner_r, floor)
base_shape = outer.cut(inner)

# The rear/bottom face remains fully closed. Both short sides have grilles
# across the lower sensor layer.

# Side openings.  After the real STEP assembly is rotated 90 degrees, its
# USB-C receptacle is on the +X short end (not the -X end used previously).
# The larger cut includes clearance for the moulded shell of a USB-C plug.
usb_cut_w = 12.0
usb_cut_h = 6.2
usb_cut_z = 15.7
usb_cut = horizontal_capsule_cut_x(
    wall + 1.5,
    usb_cut_w,
    usb_cut_h,
    outer_w / 2.0 - wall - 0.5,
    0.0,
    usb_cut_z + usb_cut_h / 2.0,
)
# The CO2 sensor's Dupont leads remain inside the enclosure and pass through
# the two narrow deck slots, so the former large external wire opening below
# USB-C is intentionally omitted; a separate ventilation grille is cut below.
base_shape = base_shape.cut(usb_cut)

# BOOT and RST side-button access.  The centers are measured from the two
# SWITCH-TS24CA bodies in the real STEP assembly after the same 90-degree
# rotation and centering transform used below.  The switches face opposite
# long sides, so each wall receives its own opening rather than putting both
# holes beside the USB-C connector.
button_center_x = 10.55
button_center_z = 19.25
button_stem_d = 3.0
button_bore_d = 3.4
button_guide_od = 6.2
button_guide_len = 1.5
button_plunger_travel = 0.8
button_outer_projection = 2.0
button_switch_gap = 0.3
button_stop_flange_d = 5.8
button_stop_flange_t = (
    outer_d / 2.0 - wall - button_guide_len - 0.20
    - (11.36 + button_switch_gap)
)
button_contact_pad_d = button_stop_flange_d
button_contact_pad_t = button_stop_flange_t
for side in (-1.0, 1.0):
    inward_axis = App.Vector(0, -side, 0)
    outer_face_y = side * outer_d / 2.0
    inner_face_y = side * (outer_d / 2.0 - wall)

    # A short annular boss on the inside face guides the cylindrical stem.
    # The one-piece plunger is loaded from the enclosure interior: its thin
    # exposed stem passes out through this bore while the single collar stays
    # inside the shell.
    guide = Part.makeCylinder(
        button_guide_od / 2.0,
        button_guide_len,
        App.Vector(button_center_x, inner_face_y, button_center_z),
        inward_axis,
    )
    base_shape = base_shape.fuse(guide)

    # Round sliding bore through the wall and the full guide boss.  0.20 mm
    # radial clearance accommodates an FDM printed 3.0 mm stem.
    bore = Part.makeCylinder(
        button_bore_d / 2.0,
        wall + button_guide_len + 1.0,
        App.Vector(button_center_x, outer_face_y + side * 0.5,
                   button_center_z),
        inward_axis,
    )
    base_shape = base_shape.cut(bore)


# Matching convection grilles across the CO2 sensor layer on both short sides.
# The +X grille is below USB-C, with 3 mm of material between their openings.
vent_slot_w = 14.0
vent_slot_h = 0.9
vent_slot_z = 5.0
vent_slot_pitch = 1.7
vent_slot_count = 5
vent_slot_end_radius = vent_slot_h / 2.0
for vent_x in (-outer_w / 2.0 - 0.5, outer_w / 2.0 - wall - 0.5):
    for index in range(vent_slot_count):
        vent = horizontal_capsule_cut_x(
            wall + 1.0,
            vent_slot_w,
            vent_slot_h,
            vent_x,
            0.0,
            vent_slot_z + index * vent_slot_pitch + vent_slot_h / 2.0,
        )
        base_shape = base_shape.cut(vent)

# The rear face is a separate removable bottom cover.  Its four M2.5 sensor
# bosses let the CO2 module be assembled on the bench first, then wired to the
# ESP32 and closed into the enclosure as one serviceable subassembly.
bottom_plate_shape = rounded_prism(outer_w, outer_d, floor, corner_r)

# Four 1 mm sensor mounting bosses on the removable bottom cover.  The 2.8 mm
# M2.5 clearance holes pass completely through the cover and bosses so bolts
# can be inserted from below.  The module's flat PCB back faces the bosses and
# its component side faces upward into the enclosure.
sensor_rotation_deg = 90.0
sensor_mount_x_local = sensor_w / 2.0 - sensor_mount_inset_x
sensor_mount_y_local = sensor_d / 2.0 - sensor_mount_inset_y
sensor_mounts_local = [
    (-sensor_mount_x_local, -sensor_mount_y_local),
    (-sensor_mount_x_local, sensor_mount_y_local),
    (sensor_mount_x_local, -sensor_mount_y_local),
    (sensor_mount_x_local, sensor_mount_y_local),
]
# The bottom module is viewed from above.  Positive Z rotation is a 90-degree
# left/counter-clockwise turn.  Rotate the real screw pattern as well as the
# display model so the bottom-cover holes and bosses remain aligned.
sensor_mounts = [(-y, x) for x, y in sensor_mounts_local]
sensor_mount_x = max(abs(x) for x, _ in sensor_mounts)
sensor_mount_y = max(abs(y) for _, y in sensor_mounts)
sensor_boss_h = sensor_z - floor
for x, y in sensor_mounts:
    boss = Part.makeCylinder(
        sensor_mount_boss_radius, sensor_boss_h, App.Vector(x, y, floor)
    )
    through_hole = Part.makeCylinder(
        sensor_mount_clearance_radius,
        floor + sensor_boss_h + 0.4,
        App.Vector(x, y, -0.2),
    )
    bottom_plate_shape = bottom_plate_shape.fuse(boss).cut(through_hole)
    # Flat-bottom counterbore from the exterior underside. Match the existing
    # four cover-screw pockets; retain 1.6 mm up to the sensor support plane.
    bottom_plate_shape = bottom_plate_shape.cut(Part.makeCylinder(
        sensor_head_pocket_radius, sensor_head_pocket_depth + 0.05,
        App.Vector(x, y, -0.05),
    ))

# ESP32 hole pattern follows the real STEP standoffs after 90° rotation.  The
# actual mounting bosses are added after the 2 mm inter-layer deck, so they are
# structurally rooted in that deck rather than extending all the way from the
# rear floor.
pcb_mounts = [(-16.814, -6.640), (-16.814, 6.640),
              (15.186, -8.160), (15.186, 8.160)]

# A 2 mm inter-layer mounting deck fixes the front PCB above the CO2 module.
# Join its entire perimeter to all four walls. The small boolean overlap lies
# inside the existing wall and does not change the enclosure's outer size.
# Each complete Dupont/header row is opened as one narrow continuous slot, as
# requested, so all soldered pins and fillets share a single passage.
deck_wall_overlap = 0.20
deck_shape = rounded_prism(
    outer_w - 2 * wall + 2 * deck_wall_overlap,
    outer_d - 2 * wall + 2 * deck_wall_overlap,
    deck_t,
    inner_corner_r + deck_wall_overlap,
    deck_z,
)
header_slot_end_axis_distance = 1.3
header_slot_length = (header_pin_count - 1) * header_pitch + 2 * header_slot_end_axis_distance
header_slot_width = 2.6
for y in (-header_row_y, header_row_y):
    row_slot = Part.makeBox(
        header_slot_length,
        header_slot_width,
        deck_t + 1.0,
        App.Vector(
            header_row_center_x - header_slot_length / 2.0,
            y - header_slot_width / 2.0,
            deck_z - 0.5,
        ),
    )
    deck_shape = deck_shape.cut(row_slot)

# Central airflow/service opening between the two pin rows.  Extend it far
# enough in Y to overlap both header slots by 0.15 mm per side, turning the
# former three separate cuts into one continuous opening.  The positive
# overlap also avoids fragile coincident/tangent faces in the boolean result.
# Keep all four central-opening corners square, including the transitions
# next to the header rows; no R2 corner material remains in the passage.
central_opening_length = 26.0
# Preserve the existing 15.48 mm central opening when narrowing the slots.
slot_to_center_overlap = 0.15
central_opening_width = 2.0 * (
    header_row_y - header_slot_width / 2.0 + slot_to_center_overlap
)
deck_shape = deck_shape.cut(
    Part.makeBox(
        central_opening_length,
        central_opening_width,
        deck_t + 1.0,
        App.Vector(
            -central_opening_length / 2.0,
            -central_opening_width / 2.0,
            deck_z - 0.5,
        ),
    )
)
base_shape = base_shape.fuse(deck_shape)

# Four short M2 screw pedestals rise from the top of the structural deck and
# contact the actual underside of the four SMTSO-M2 inserts in the STEP model.
# A 2.2 mm clearance hole runs through the complete pedestal and the full
# 2 mm deck thickness so an M2 screw can be inserted from the rear layer and
# tightened directly into each threaded insert on the ESP32 board.
# Their measured contact plane is Z=17.436 mm; using the assembly bounding-box
# minimum here previously left an incorrect 0.736 mm air gap.
deck_top_z = deck_z + deck_t
pcb_mount_contact_z = 17.436
pcb_boss_h = pcb_mount_contact_z - deck_top_z
for x, y in pcb_mounts:
    boss = Part.makeCylinder(
        pcb_boss_radius, pcb_boss_h, App.Vector(x, y, deck_top_z)
    )
    through_hole = Part.makeCylinder(
        pcb_mount_through_radius,
        deck_t + pcb_boss_h + 0.6,
        App.Vector(x, y, deck_z - 0.3),
    )
    base_shape = base_shape.fuse(boss).cut(through_hole)

# Four shared side-body screw columns tucked into the rounded corners.  The
# top and bottom covers are both clamped with M2.5 screws.  A continuous
# 2.3 mm tapping hole runs through each column for easier cleaning, tapping,
# inspection and repair; screw length must stay below half the shell depth.
# Retain the shared axes and 7.1 mm columns after reducing external R5 to R4.
# The 5.1 mm counterbores now have a 1.29 mm minimum exterior rim. Internal
# columns are unchanged: radial bore walls are 2.4 mm inward, ~2.795 outward.
cover_head_outer_rim = 1.29
cover_screw_x = 18.86
cover_screw_y = 12.82
cover_screws = [(-cover_screw_x, -cover_screw_y),
                (-cover_screw_x, cover_screw_y),
                (cover_screw_x, -cover_screw_y),
                (cover_screw_x, cover_screw_y)]
cover_tap_radius = 1.15
cover_clearance_radius = 1.45
cover_head_radius = 2.55
cover_head_depth = 1.35
cover_tower_radius = 3.55
cover_corner_dx = cover_screw_x - (outer_w / 2.0 - corner_r)
cover_corner_dy = cover_screw_y - (outer_d / 2.0 - corner_r)
cover_radial_projection = 0.8 * cover_corner_dx + 0.6 * cover_corner_dy
cover_outer_radial_wall = (
    -cover_radial_projection
    + (cover_radial_projection**2 + corner_r**2
       - cover_corner_dx**2 - cover_corner_dy**2)**0.5
    - cover_tap_radius
)
for x, y in cover_screws:
    tower = Part.makeCylinder(
        cover_tower_radius, base_h - floor, App.Vector(x, y, floor)
    )
    through_tap = Part.makeCylinder(
        cover_tap_radius, base_h - floor + 0.4,
        App.Vector(x, y, floor - 0.2)
    )
    base_shape = base_shape.fuse(tower).cut(through_tap)

# Re-cut both continuous row passages after the bosses/towers have been added.
# This guarantees the full narrow slots remain open where they pass close to a
# PCB mounting pedestal. The top follows the measured pedestal contact plane:
# the previous cut stopped at Z=17.2, leaving a 0.236 mm cap over the slots.
header_slot_cut_z = min(header_pin_bottom_z, deck_z) - 0.5
header_slot_cut_top_z = max(board_min_z, pcb_mount_contact_z) + 0.5
for y in (-header_row_y, header_row_y):
    through_slot = Part.makeBox(
        header_slot_length,
        header_slot_width,
        header_slot_cut_top_z - header_slot_cut_z,
        App.Vector(
            header_row_center_x - header_slot_length / 2.0,
            y - header_slot_width / 2.0,
            header_slot_cut_z,
        ),
    )
    base_shape = base_shape.cut(through_slot)

# Remove the former integral rear floor from the main shell.  The side body now
# starts at Z=2 mm and can be lifted away after releasing the four cover
# screws, giving unobstructed access to the sensor and wiring.
bottom_separation_cut = rounded_prism(
    outer_w + 1.0, outer_d + 1.0, floor + 0.1, corner_r + 0.5, -0.05
)
base_shape = base_shape.cut(bottom_separation_cut)

# Bottom-cover M2.5 clearance and recessed head pockets.  These four holes sit
# at the outer corners and align only with the side-body columns; they are not
# the ESP32 or CO2 mounting pattern.
for x, y in cover_screws:
    bottom_plate_shape = bottom_plate_shape.cut(Part.makeCylinder(
        cover_clearance_radius, floor + 0.5,
        App.Vector(x, y, -0.1)
    ))
    bottom_plate_shape = bottom_plate_shape.cut(Part.makeCylinder(
        cover_head_radius, cover_head_depth + 0.1,
        App.Vector(x, y, -0.05)
    ))

bottom_vent_diameter = 1.5
bottom_vent_pitch = 3.0
bottom_vent_centers = bottom_vent_pattern(sensor_mounts)
bottom_vent_min_pocket_web = min(
    ((x - mx)**2 + (y - my)**2)**0.5
    - bottom_vent_diameter / 2.0 - sensor_head_pocket_radius
    for x, y in bottom_vent_centers for mx, my in sensor_mounts
)
for x, y in bottom_vent_centers:
    bottom_plate_shape = bottom_plate_shape.cut(Part.makeCylinder(
        bottom_vent_diameter / 2.0, floor + 0.2, App.Vector(x, y, -0.1)))

base_shape = base_shape.removeSplitter()
bottom_plate_shape = bottom_plate_shape.removeSplitter()

base_obj = doc.addObject("PartDesign::Feature", "RearShell")
base_obj.Label = "侧壁＋中间层（上下盖 M2.5 攻丝柱）"
base_obj.Shape = base_shape
base_obj.addProperty("App::PropertyString", "MaterialName", "Material")
base_obj.MaterialName = "PC (Semi-Transparent Polycarbonate)"
if App.GuiUp:
    base_obj.ViewObject.ShapeColor = (0.72, 0.84, 0.90)
    base_obj.ViewObject.LineColor = (0.20, 0.32, 0.40)
    base_obj.ViewObject.Transparency = 55

bottom_obj = doc.addObject("PartDesign::Feature", "RemovableBottomCover")
bottom_obj.Label = "可拆下盖（M2.5 螺丝固定到侧壁）"
bottom_obj.Shape = bottom_plate_shape
bottom_obj.addProperty("App::PropertyString", "MaterialName", "Material")
bottom_obj.MaterialName = "PC (Semi-Transparent Polycarbonate)"
if App.GuiUp:
    bottom_obj.ViewObject.ShapeColor = (0.66, 0.79, 0.86)
    bottom_obj.ViewObject.LineColor = (0.18, 0.29, 0.36)
    bottom_obj.ViewObject.Transparency = 45

# Front lid.  The display opening follows the user's section sketch: a shallow
# lower pocket leaves 1 mm air above the screen, a short vertical inner wall
# masks the glass border, and a chamfer rises to the cover's outer surface.
# Both chamfer transitions are filleted so there are no sharp dust-catching
# corners at the top surface or at the lower vertical wall.
lid_shape = rounded_prism(outer_w, outer_d, lid_t, corner_r, base_h)
# The STEP screen assembly is not centred on the complete PCB assembly.  Its
# active area is 32.35 x 17.39 mm and, after the 90 degree board rotation and
# enclosure centring above, its centre is X=-1.5675 mm.  Cutting the old
# 34.8 x 18.9 mm window at X=0 exposed the cyan glass border at one short end
# and slightly clipped the active area at the other.  Keep only 0.25 mm of
# clearance per side around the true active area so the lid masks the glass
# border evenly.
window_w = 32.85
window_d = 17.89
window_r = 2.50
window_cx = -1.5675
funnel_top_w = 36.45
funnel_top_d = 21.15
funnel_top_r = 4.05
funnel_top_cx = -0.85
screen_top_z = base_h
screen_lid_gap = 1.0
inner_wall_h = 0.70
lip_bottom_z = screen_top_z + screen_lid_gap
funnel_bottom_z = lip_bottom_z + inner_wall_h
funnel_top_z = base_h + lid_t + 0.20
display_cut_overlap = 0.50

# Small vertical aperture below the chamfer.  Extend it 0.50 mm into the
# chamfer cutter instead of ending both cuts on the same plane.  Coincident
# Boolean faces left a roughly 0.01 mm PC membrane across the display in OCC,
# which appeared as a cyan sheet over the screen in FreeCAD.
vertical_window = rounded_prism(
    window_w, window_d,
    funnel_bottom_z - (base_h - 0.30) + display_cut_overlap,
    window_r, base_h - 0.30, window_cx, 0.0,
)
lid_shape = lid_shape.cut(vertical_window)

funnel = Part.makeLoft([
    rounded_wire(window_w, window_d, window_r,
                 funnel_bottom_z, window_cx, 0.0),
    rounded_wire(funnel_top_w, funnel_top_d, funnel_top_r,
                 funnel_top_z, funnel_top_cx, 0.0),
], True, False)
lid_shape = lid_shape.cut(funnel)

# Underside relief clears the full rounded display lens and stops exactly
# 1.0 mm above its top face.  It is downward-facing and therefore does not form
# an exposed dust shelf in the display opening.
recess_w = 37.1
recess_d = 21.6
recess_r = 4.1
recess_cx = -0.60
recess = rounded_prism(recess_w, recess_d,
                       lip_bottom_z - (base_h - 0.30), recess_r,
                       base_h - 0.30, recess_cx, 0.0)
lid_shape = lid_shape.cut(recess)

# Round both edges marked in the user's section sketch.  Select only edges
# around the display opening at the lower chamfer junction and the top face;
# enclosure perimeter and screw-hole edges are intentionally excluded.
bezel_edge_fillet_r = 0.40
bezel_transition_edges = []
for edge in lid_shape.Edges:
    ebb = edge.BoundBox
    edge_cx = (ebb.XMin + ebb.XMax) / 2.0
    edge_cy = (ebb.YMin + ebb.YMax) / 2.0
    is_transition_z = (
        (ebb.ZLength < 0.04 and abs(ebb.ZMin - funnel_bottom_z) < 0.04)
        or (ebb.ZLength < 0.04 and abs(ebb.ZMin - (base_h + lid_t)) < 0.04)
    )
    is_near_window = (
        abs(edge_cx - window_cx) < funnel_top_w / 2.0 + 0.6
        and abs(edge_cy) < funnel_top_d / 2.0 + 0.6
    )
    if is_transition_z and is_near_window:
        bezel_transition_edges.append(edge)
if bezel_transition_edges:
    lid_shape = lid_shape.makeFillet(
        bezel_edge_fillet_r, bezel_transition_edges
    )

# Both cover locating rims were removed at the user's request.  The four M2.5
# screws and the shared side-body columns provide the cover alignment.
for x, y in cover_screws:
    lid_shape = lid_shape.cut(Part.makeCylinder(
        cover_clearance_radius, lid_t + 2.0,
        App.Vector(x, y, base_h - 1.0)))
    lid_shape = lid_shape.cut(Part.makeCylinder(
        cover_head_radius, cover_head_depth + 0.1,
        App.Vector(x, y, base_h + lid_t - cover_head_depth)))
lid_shape = lid_shape.removeSplitter()

lid_obj = doc.addObject("PartDesign::Feature", "FrontBezel")
lid_obj.Label = "前盖（下沉斜面防尘显示窗）"
lid_obj.Shape = lid_shape
lid_obj.addProperty("App::PropertyString", "MaterialName", "Material")
lid_obj.MaterialName = "PC (Semi-Transparent Polycarbonate)"
if App.GuiUp:
    lid_obj.ViewObject.ShapeColor = (0.72, 0.84, 0.90)
    lid_obj.ViewObject.LineColor = (0.20, 0.32, 0.40)
    lid_obj.ViewObject.Transparency = 45

# Real ESP32 assembly: rotate 90° around Z, then center it over the rear sensor.
board_shape = source_object.Shape.copy()
board_shape.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 90.0)
bb = board_shape.BoundBox
board_shape.translate(App.Vector(
    -(bb.XMin + bb.XMax) / 2.0,
    -(bb.YMin + bb.YMax) / 2.0,
    board_min_z - bb.ZMin,
))
board = doc.addObject("PartDesign::Feature", "ESP32BoardAssembly")
board.Label = "ESP32 总成（旋转 90°，前层）"
board.Shape = board_shape
if App.GuiUp:
    board.ViewObject.ShapeColor = (0.14, 0.46, 0.22)

# The left cover columns formerly overlapped the actual PCB edge.  Preserve
# their updated axes and cut each PCB-facing side with one 45-degree plane,
# leaving at least 1.5 mm even around the nominal 2.5 mm thread envelope.
base_shape, pcb_relief_tool, pcb_solid, pcb_relief = relieve_pcb_columns(
    base_shape, board.Shape,
    [(-cover_screw_x, -cover_screw_y), (-cover_screw_x, cover_screw_y)],
    cover_tower_radius, cover_tap_radius,
    relief_bottom_z=deck_top_z,
)
base_obj.Shape = base_shape

# Actual soldered header-pin keep-out: 9 pins per side at 2.54 mm pitch.
# The cylinders are references, not printable geometry.
pin_shapes = []
for row_y in (-header_row_y, header_row_y):
    for index in range(header_pin_count):
        pin_x = header_pin_x0 + index * header_pitch
        pin_shapes.append(Part.makeCylinder(
            header_pin_diameter / 2.0,
            board_min_z - header_pin_bottom_z,
            App.Vector(pin_x, row_y, header_pin_bottom_z),
        ))
header_pins = doc.addObject("PartDesign::Feature", "HeaderPinsKeepout")
header_pins.Label = "焊接排针穿透预留（2×9，间距 2.54）"
header_pins.Shape = Part.makeCompound(pin_shapes)
if App.GuiUp:
    header_pins.ViewObject.ShapeColor = (0.96, 0.74, 0.12)

# SCD41 breakout reference in the rear layer.  Model the user's actual module
# as a four-hole black PCB, a central green carrier/metal sensor can and two
# white STEMMA QT connectors.  The flat rear PCB rests on the 1 mm bosses and
# all components face upward toward the inter-layer deck.
sensor_pcb_t = 1.2
sensor_pcb_shape = rounded_prism(
    sensor_w, sensor_d, sensor_pcb_t, 2.2, sensor_z
)
for x, y in sensor_mounts_local:
    sensor_hole = Part.makeCylinder(
        sensor_mount_clearance_radius,
        sensor_pcb_t + 1.0,
        App.Vector(x, y, sensor_z - 0.5),
    )
    sensor_pcb_shape = sensor_pcb_shape.cut(sensor_hole)
sensor_pcb_shape = sensor_pcb_shape.removeSplitter()
sensor_pcb_shape.rotate(
    App.Vector(0, 0, 0), App.Vector(0, 0, 1), sensor_rotation_deg
)

# The supplied SEK STEP combines an evaluation PCB, its connector and SCD41
# into one solid. The evaluation PCB's top is Z=0. Removing only its board
# thickness separates the two components; retain the 10.1 mm SCD41 package.
scd41_source = Part.read(SCD41_STEP_PATH)
scd41_above_board = scd41_source.common(
    Part.makeBox(40, 40, 10, App.Vector(-5, -5, 0))
)
scd41_candidates = [
    solid for solid in scd41_above_board.Solids
    if abs(solid.BoundBox.XLength - 10.1) < 0.01
    and abs(solid.BoundBox.YLength - 10.1) < 0.01
    and abs(solid.BoundBox.ZLength - 6.28) < 0.01
]
if len(scd41_candidates) != 1:
    raise RuntimeError("无法从 SEK STEP 唯一识别 SCD41 本体")
scd41_package = scd41_candidates[0]
scd41_box = scd41_package.BoundBox
sensor_can_shape = scd41_package.transformed(App.Placement(
    App.Vector(
        -(scd41_box.XMin + scd41_box.XMax) / 2.0,
        -(scd41_box.YMin + scd41_box.YMax) / 2.0,
        sensor_z + sensor_pcb_t - scd41_box.ZMin,
    ), App.Rotation(),
).toMatrix(), copy=True)
sensor_h = sensor_pcb_t + scd41_box.ZLength
sensor_can_shape.rotate(
    App.Vector(0, 0, 0), App.Vector(0, 0, 1), sensor_rotation_deg
)

connector_w = 7.2
connector_d = 3.7
connector_h = 2.5
connector_y = sensor_d / 2.0 - connector_d / 2.0
sensor_connector_shape = Part.makeCompound([
    Part.makeBox(
        connector_w, connector_d, connector_h,
        App.Vector(-connector_w / 2.0, connector_y - connector_d / 2.0,
                   sensor_z + sensor_pcb_t),
    ),
    Part.makeBox(
        connector_w, connector_d, connector_h,
        App.Vector(-connector_w / 2.0, -connector_y - connector_d / 2.0,
                   sensor_z + sensor_pcb_t),
    ),
])
sensor_connector_shape.rotate(
    App.Vector(0, 0, 0), App.Vector(0, 0, 1), sensor_rotation_deg
)

# Hidden aggregate is retained for reliable collision checks.  The three
# coloured component objects below are what the user sees in the assembly.
sensor_shape = Part.makeCompound([
    sensor_pcb_shape, sensor_can_shape, sensor_connector_shape
])
sensor = doc.addObject("PartDesign::Feature", "CO2SensorEnvelope")
sensor.Label = "SCD41 总成碰撞参考（含真实 STEP 本体）"
sensor.Shape = sensor_shape

sensor_pcb_obj = doc.addObject("PartDesign::Feature", "CO2SensorPCB")
sensor_pcb_obj.Label = "SCD41 黑色 PCB（背面朝下）"
sensor_pcb_obj.Shape = sensor_pcb_shape
sensor_can_obj = doc.addObject("PartDesign::Feature", "CO2SensorCan")
sensor_can_obj.Label = "SCD41 传感器本体（真实 STEP，朝上）"
sensor_can_obj.Shape = sensor_can_shape
sensor_can_obj.addProperty("App::PropertyFile", "SourceSTEP", "Source")
sensor_can_obj.SourceSTEP = SCD41_STEP_PATH
sensor_connector_obj = doc.addObject("PartDesign::Feature", "CO2SensorConnectors")
sensor_connector_obj.Label = "SCD41 上下 STEMMA QT 插座"
sensor_connector_obj.Shape = sensor_connector_shape
if App.GuiUp:
    sensor.ViewObject.Visibility = False
    sensor_pcb_obj.ViewObject.ShapeColor = (0.05, 0.07, 0.06)
    sensor_pcb_obj.ViewObject.LineColor = (0.35, 0.42, 0.38)
    sensor_can_obj.ViewObject.ShapeColor = (0.72, 0.74, 0.72)
    sensor_can_obj.ViewObject.LineColor = (0.28, 0.30, 0.28)
    sensor_connector_obj.ViewObject.ShapeColor = (0.92, 0.92, 0.88)
    sensor_connector_obj.ViewObject.LineColor = (0.45, 0.45, 0.42)

# Two one-piece round sliding plungers make the recessed BOOT/RST tact switches
# operable from outside.  They are inserted from inside before the front cover
# is fitted. Only the 3 mm stem passes through the wall. The continuous inner
# collar limits outward travel and presses the switch with its inner face.
button_positive = doc.addObject("PartDesign::Feature", "ButtonPlungerPositive")
button_positive.Label = "内装式单圆台推杆（BOOT/RST，打印件 1）"
button_positive.Shape = make_side_button(
    1.0, outer_d, button_center_x, button_center_z
)
button_positive.addProperty("App::PropertyString", "MaterialName", "Material")
button_positive.MaterialName = "PLA or PETG"

button_negative = doc.addObject("PartDesign::Feature", "ButtonPlungerNegative")
button_negative.Label = "内装式单圆台推杆（BOOT/RST，翻转件 2）"
button_negative.Shape = make_side_button(
    -1.0, outer_d, button_center_x, button_center_z
)
button_negative.addProperty("App::PropertyString", "MaterialName", "Material")
button_negative.MaterialName = "PLA or PETG"
if App.GuiUp:
    for button_obj in (button_positive, button_negative):
        button_obj.ViewObject.ShapeColor = (0.96, 0.62, 0.12)
        button_obj.ViewObject.LineColor = (0.35, 0.20, 0.04)

params = doc.addObject("App::FeaturePython", "DesignParameters")
params.Label = "紧凑双层设计参数（毫米）"
for name, value in (
    ("OuterLength", outer_w), ("OuterWidth", outer_d),
    ("OuterCornerRadius", corner_r), ("InnerCornerRadius", inner_corner_r),
    ("RearShellDepth", base_h), ("FrontBezelThickness", lid_t),
    ("WallThickness", wall), ("ScreenWindowLength", window_w),
    ("ScreenWindowWidth", window_d), ("ScreenCornerRadius", window_r),
    ("ScreenWindowCenterX", window_cx),
    ("ScreenToLidGap", screen_lid_gap),
    ("BezelInnerWallHeight", inner_wall_h),
    ("BezelTransitionFilletRadius", bezel_edge_fillet_r),
    ("DisplayBooleanCutOverlap", display_cut_overlap),
    ("CO2Length", sensor_w), ("CO2Width", sensor_d),
    ("CO2Height", sensor_h), ("BoardLayerStart", board_min_z),
    ("CO2MountSpacingX", 2 * sensor_mount_x),
    ("CO2MountSpacingY", 2 * sensor_mount_y),
    ("CO2MountSpacingLongEdge", sensor_mount_spacing_long),
    ("CO2MountSpacingShortEdge", sensor_mount_spacing_short),
    ("CO2MountClearanceDiameter", 2 * sensor_mount_clearance_radius),
    ("CO2BottomStandoffHeight", sensor_standoff_h),
    ("CO2BottomThroughHoleDiameter", 2 * sensor_mount_clearance_radius),
    ("CO2BottomHeadPocketDiameter", 2 * sensor_head_pocket_radius),
    ("CO2BottomHeadPocketDepth", sensor_head_pocket_depth),
    ("PCBLength", pcb_length), ("PCBWidth", pcb_width),
    ("HeaderPitch", header_pitch), ("HeaderRowSpacing", 2 * header_row_y),
    ("InterLayerDeckThickness", deck_t),
    ("InterLayerDeckPerimeterGap", 0.0),
    ("InterLayerDeckWallOverlap", deck_wall_overlap),
    ("BottomCoverThickness", floor),
    ("CoverScrewNominalDiameter", 2.5),
    ("SideBodyTapHoleDiameter", 2 * cover_tap_radius),
    ("SideBodyColumnDiameter", 2 * cover_tower_radius),
    ("SideBodyColumnCenterX", cover_screw_x),
    ("SideBodyColumnCenterY", cover_screw_y),
    ("CoverScrewCenterX", cover_screw_x),
    ("CoverScrewCenterY", cover_screw_y),
    ("CoverScrewRadialOutwardShift", ((18.86-18.1)**2+(12.82-12.2)**2)**0.5),
    ("CoverScrewDiagonalShiftFromPrevious", 2**0.5 * 0.2),
    ("OuterExpansionPerSide", 0.2),
    ("CoverScrewRadialInnerWallThickness", cover_tower_radius - cover_tap_radius),
    ("CoverScrewRadialOuterWallThickness", cover_outer_radial_wall),
    ("PCBColumnReliefClearance", pcb_relief["clearance"]),
    ("PCBColumnReliefMinWall", pcb_relief["min_wall"]),
    ("PCBColumnReliefBottomZ", pcb_relief["bottom_z"]),
    ("PCBColumnReliefNominalThreadMinWall", pcb_relief["min_nominal_thread_wall"]),
    ("PCBColumnReliefPlaneOffset", pcb_relief["plane_offset"]),
    ("CoverHeadPocketOuterRim", cover_head_outer_rim),
    ("CoverClearanceDiameter", 2 * cover_clearance_radius),
    ("CoverHeadPocketDiameter", 2 * cover_head_radius),
    ("PCBBossDiameter", 2 * pcb_boss_radius),
    ("PCBBossRadius", pcb_boss_radius),
    ("PCBMountThroughHoleDiameter", 2 * pcb_mount_through_radius),
    ("PCBMountContactHeight", pcb_mount_contact_z),
    ("HeaderSlotLength", header_slot_length),
    ("HeaderSlotWidth", header_slot_width),
    ("HeaderSlotEndAxisDistance", header_slot_end_axis_distance),
    ("HeaderSlotCutBottomZ", header_slot_cut_z),
    ("HeaderSlotCutTopZ", header_slot_cut_top_z),
    ("CentralOpeningLength", central_opening_length),
    ("CentralOpeningWidth", central_opening_width),
    ("CentralOpeningCornerRadius", 0.0),
    ("SlotToCenterOverlap", slot_to_center_overlap),
    ("USBCutWidth", usb_cut_w), ("USBCutHeight", usb_cut_h),
    ("ButtonStemDiameter", button_stem_d),
    ("ButtonGuideBoreDiameter", button_bore_d),
    ("ButtonGuideBossDiameter", button_guide_od),
    ("ButtonGuideBossLength", button_guide_len),
    ("ButtonCenterX", button_center_x),
    ("ButtonCenterZ", button_center_z),
    ("ButtonPlungerTravel", button_plunger_travel),
    ("ButtonSwitchGap", button_switch_gap),
    ("ButtonOuterProjection", button_outer_projection),
    ("ButtonStopFlangeDiameter", button_stop_flange_d),
    ("ButtonStopFlangeThickness", button_stop_flange_t),
    ("ButtonContactPadDiameter", button_contact_pad_d),
    ("ButtonContactPadThickness", button_contact_pad_t),
    ("ButtonCollarDiameter", button_stop_flange_d),
    ("ButtonCollarThickness", button_stop_flange_t),
    ("DisplayToLidClearance", base_h - board.Shape.BoundBox.ZMax),
    ("ConvectionSlotWidth", vent_slot_w),
    ("ConvectionSlotHeight", vent_slot_h),
    ("ConvectionSlotPitch", vent_slot_pitch),
    ("ConvectionSlotEndRadius", vent_slot_end_radius),
    ("BottomVentDiameter", bottom_vent_diameter),
    ("BottomVentPitch", bottom_vent_pitch),
    ("BottomVentFootprintLength", 19.5),
    ("BottomVentFootprintWidth", 19.5),
    ("BottomVentMinimumPocketWeb", bottom_vent_min_pocket_web),
    ("USBCVentSlotStartZ", vent_slot_z),
    ("USBCVentToConnectorGap", usb_cut_z - (
        vent_slot_z + (vent_slot_count - 1) * vent_slot_pitch + vent_slot_h)),
):
    params.addProperty("App::PropertyLength", name, "Dimensions")
    setattr(params, name, value)
params.addProperty("App::PropertyInteger", "USBCVentSlotCount", "Dimensions")
params.USBCVentSlotCount = vent_slot_count
params.addProperty("App::PropertyInteger", "BottomVentCount", "Dimensions")
params.BottomVentCount = len(bottom_vent_centers)
params.addProperty("App::PropertyAngle", "PCBColumnReliefAngle", "Dimensions")
params.PCBColumnReliefAngle = 45.0
params.addProperty("App::PropertyInteger", "ButtonInnerRingCount", "Dimensions")
params.ButtonInnerRingCount = 1
params.addProperty("App::PropertyString", "Layout", "Documentation")
params.Layout = (
    "Z 方向双层：CO2 背面朝下放在底盖四个 1 mm 凸台上，元件面朝上；"
    "底盖四个 2.8 mm 通孔供 M2.5 螺栓固定 CO2。"
    "CO2 安装孔中心距为长边 20 mm、短边 18 mm；旋转后底板 X 向 18 mm、Y 向 20 mm。"
    "前层通过 2 mm 中间层板上的四个 M2 柱台接触 STEP 实测安装面；"
    "中层板四周无间隙，与四面侧壁连续融合为一体。"
    "四个 2.2 mm 通孔贯穿柱台和中层板，M2 螺丝从背面穿入并固定 ESP32。"
    "上盖和下盖各用四颗 M2.5 螺丝固定到侧壁主体；"
    "盖板设 2.9 mm 通孔和沉头窝，侧壁四角柱设上下贯通的 2.3 mm 攻丝孔；"
    "外形45.4×33.9mm，四边各扩0.2mm，内腔和电子件位置不变；"
    "四角孔中心 X=±18.86、Y=±12.82；螺丝柱直径7.1mm，未避让区域径向内壁2.4mm、外壁约2.795mm；"
    "三件外轮廓均为R4，内腔保持不变，上下盖5.1mm沉孔到外缘最薄1.29mm，三件孔位一致。"
    "左侧两根角柱各用一个45度竖直平面截切，下沿到中层板顶面Z15.5，板边间隙至少0.3mm，向上贯通；"
    "避让处Ø2.3孔最薄壁厚约1.632mm，按M2.5公称外径仍约1.532mm。"
    "便于安装传感器、接杜邦线和后期维修。"
    "两端短边均设置五条14×0.9mm横向透气槽，两端R0.45半圆，+X端位于USB-C下方；"
    "底盖中央37个Ø1.5mm通气圆孔，3mm间距，覆盖19.5×19.5mm，避开四个传感器沉孔；"
    "原外部杜邦线出口保持封闭。"
    "两条长边按 STEP 实际位置分别设置 BOOT 与 RST 按键孔。"
    "孔内安装两个 3.0 mm 圆柱滑动按键，内侧导向台防止摆动；"
    "外部为 3 mm 圆柱按压端，内部为直径 5.8 mm、厚 1.39 mm 的一体圆台；"
    "从壳内装入，圆台兼作防脱限位和按键接触面，预留 0.8 mm 行程。"
    "显示屏与前盖近乎贴合。"
)

print_group = doc.addObject("App::DocumentObjectGroup", "PrintableParts")
print_group.Label = "可打印零件"
print_group.addObject(base_obj)
print_group.addObject(bottom_obj)
print_group.addObject(lid_obj)
assembly_group = doc.addObject("App::DocumentObjectGroup", "Assembly")
assembly_group.Label = "双层装配件"
assembly_group.addObject(sensor)
assembly_group.addObject(sensor_pcb_obj)
assembly_group.addObject(sensor_can_obj)
assembly_group.addObject(sensor_connector_obj)
assembly_group.addObject(board)
assembly_group.addObject(header_pins)
assembly_group.addObject(button_positive)
assembly_group.addObject(button_negative)

doc.recompute()

# Collision checks for the two stacked electronic modules and shell.
raise_lower_layer(doc, target=20.0, reference="co2_pcb_top")
add_horizontal_supports(doc)
# Keep the old slots below the extension split until the lower layer is raised,
# then redistribute them into the added height with 1.7 mm solid ribs.
space_side_vents(doc)
# Mirror the original two upper PCB-facing flats to all four corners and
# both cavities, while leaving the connecting middle deck intact.
apply_all_corner_flats(doc)
# Final cover revision removes the temporary stepped display relief above.
apply_flush_bezel(doc)
# Remove the sub-micron glass-datum lip so the entire underside is one plane.
apply_planar_underside(doc)
sensor_board_overlap = sensor.Shape.common(board.Shape).Volume
sensor_shell_overlap = sensor.Shape.common(base_obj.Shape).Volume
sensor_bottom_overlap = sensor.Shape.common(bottom_obj.Shape).Volume
bottom_shell_overlap = bottom_obj.Shape.common(base_obj.Shape).Volume
board_shell_overlap = board.Shape.common(base_obj.Shape).Volume
if board_shell_overlap > 1e-6:
    raise RuntimeError("ESP32 与侧壁主体发生干涉: %.9f mm^3" % board_shell_overlap)
sensor_pin_overlap = sensor.Shape.common(header_pins.Shape).Volume
pin_shell_overlap = header_pins.Shape.common(base_obj.Shape).Volume
button_positive_shell_overlap = button_positive.Shape.common(base_obj.Shape).Volume
button_negative_shell_overlap = button_negative.Shape.common(base_obj.Shape).Volume
button_positive_board_overlap = button_positive.Shape.common(board.Shape).Volume
button_negative_board_overlap = button_negative.Shape.common(board.Shape).Volume
if sensor_board_overlap > 0.01:
    raise RuntimeError("CO2 与 ESP32 层发生碰撞")
if sensor_shell_overlap > 0.01:
    raise RuntimeError("CO2 与后壳发生碰撞")
if sensor_bottom_overlap > 0.01:
    raise RuntimeError("CO2 与可拆底盖发生碰撞")
if bottom_shell_overlap > 0.01:
    raise RuntimeError(
        "可拆底盖与侧壁主体发生干涉: %.6f mm^3" % bottom_shell_overlap
    )
if sensor_pin_overlap > 0.01:
    raise RuntimeError("焊接排针与 CO2 模块发生碰撞")
if pin_shell_overlap > 0.01:
    raise RuntimeError("排针穿透孔被层板或后壳遮挡")
if button_positive_shell_overlap > 0.01 or button_negative_shell_overlap > 0.01:
    raise RuntimeError("按键顶杆与外壳干涉")
if button_positive_board_overlap > 0.01 or button_negative_board_overlap > 0.01:
    raise RuntimeError("按键顶杆在静止位置压住 ESP32")

doc.saveAs(FCSTD_PATH)
Part.export([base_obj], BASE_STL_PATH)
Part.export([bottom_obj], BOTTOM_STL_PATH)
export_planar_bezel(lid_obj, LID_STL_PATH)
export_closed_button(button_positive, BUTTON_STL_PATH)

# Inspection views are generated only in the desktop GUI.  Keeping this guard
# lets the same source regenerate the FCStd/STLs reliably with freecadcmd.
if App.GuiUp:
    lid_obj.ViewObject.Visibility = False
    base_obj.ViewObject.Transparency = 55
    doc.save()
    Gui.activeDocument().activeView().viewAxonometric()
    Gui.activeDocument().activeView().fitAll()
    Gui.activeDocument().activeView().setNavigationType("Gui::SolidWorksNavigationStyle")
    Gui.activeDocument().activeView().saveImage(PREVIEW_PATH, 1600, 1100, "White")

    # Finished front view: the rounded opening exposes the display while the
    # wider inner recess captures its rounded lens below the thin bezel lip.
    lid_obj.ViewObject.Visibility = True
    base_obj.ViewObject.Transparency = 55
    lid_obj.ViewObject.Transparency = 45
    sensor.ViewObject.Visibility = False
    sensor_pcb_obj.ViewObject.Visibility = False
    sensor_can_obj.ViewObject.Visibility = False
    sensor_connector_obj.ViewObject.Visibility = False
    Gui.activeDocument().activeView().viewTop()
    Gui.activeDocument().activeView().fitAll()
    Gui.activeDocument().activeView().saveImage(
        FRONT_PREVIEW_PATH, 1600, 1100, "White"
    )

    # Leave the editable FCStd in an assembly-inspection state.  The PC shell
    # and bezel remain semi-transparent, while internal modules stay visible.
    sensor.ViewObject.Visibility = False
    sensor_pcb_obj.ViewObject.Visibility = True
    sensor_can_obj.ViewObject.Visibility = True
    sensor_connector_obj.ViewObject.Visibility = True
    Gui.activeDocument().activeView().viewAxonometric()
    Gui.activeDocument().activeView().fitAll()
doc.save()
print("COMPACT_STACKED_CREATED", FCSTD_PATH)
print("BOARD_BBOX", board.Shape.BoundBox.XLength, board.Shape.BoundBox.YLength,
      board.Shape.BoundBox.ZMin, board.Shape.BoundBox.ZMax)
print("PCB_BOSS_CONTACT_GAP", pcb_mount_contact_z - (deck_top_z + pcb_boss_h))
print("CO2_STANDOFF_HEIGHT", sensor_z - floor)
print("OVERLAPS", sensor_board_overlap, sensor_shell_overlap, board_shell_overlap)
print("BOTTOM_OVERLAPS", sensor_bottom_overlap, bottom_shell_overlap)
print("PIN_OVERLAPS", sensor_pin_overlap, pin_shell_overlap)
print("BUTTON_OVERLAPS", button_positive_shell_overlap,
      button_negative_shell_overlap, button_positive_board_overlap,
      button_negative_board_overlap)
print("BUTTON_STL", BUTTON_STL_PATH)
print("BOTTOM_STL", BOTTOM_STL_PATH)
