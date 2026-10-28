import FreeCAD as App
import Part
import Mesh


# ESP32-S3-LCD-1.47B enclosure concept
# Units are millimetres. Re-run this script after changing the values below.
WALL = 2.0
CLEARANCE = 1.0
BOTTOM_THICKNESS = 2.0
LID_THICKNESS = 2.0
DUPONT_CLEARANCE_HEIGHT = 16.0

SENSOR_LENGTH = 25.4
SENSOR_WIDTH = 23.0
SENSOR_HEIGHT = 7.0

# Measured from the currently loaded STEP assembly.
BOARD_X_MIN = -11.36
BOARD_X_MAX = 11.36
BOARD_Y_MIN = -20.36
BOARD_Y_MAX = 17.22
BOARD_Z_MIN = -6.85
BOARD_Z_MAX = 1.45


source_doc = App.ActiveDocument
source_shape = None
if source_doc:
    for candidate_name in (
        "ESP32_S3_LCD_1_47B_ASM",
        "ESP32-S3-LCD-1_47B_ASM",
    ):
        candidate = source_doc.getObject(candidate_name)
        if candidate and hasattr(candidate, "Shape") and not candidate.Shape.isNull():
            source_shape = candidate.Shape.copy()
            break

try:
    old_doc = App.getDocument("ESP32_Enclosure")
except NameError:
    old_doc = None
if old_doc:
    App.closeDocument(old_doc.Name)

doc = App.newDocument("ESP32_Enclosure", "ESP32 Enclosure")
group = doc.addObject("App::DocumentObjectGroup", "Enclosure_Design")
group.Label = "外壳设计（可编辑）"

params = doc.addObject("App::FeaturePython", "Enclosure_Parameters")
params.Label = "外壳参数"
for prop_name, label, value in (
    ("WallThickness", "壁厚", WALL),
    ("AssemblyClearance", "装配间隙", CLEARANCE),
    ("SensorLength", "传感器长度", SENSOR_LENGTH),
    ("SensorWidth", "传感器宽度", SENSOR_WIDTH),
    ("SensorHeight", "传感器高度", SENSOR_HEIGHT),
    ("DupontClearanceHeight", "杜邦线预留高度", DUPONT_CLEARANCE_HEIGHT),
):
    params.addProperty("App::PropertyLength", prop_name, "尺寸参数", label)
    setattr(params, prop_name, value)
params.addProperty("App::PropertyString", "DesignNote", "说明", "设计说明")
params.DesignNote = "传感器位于主板右侧；杜邦线区域向上预留16mm，并由凸起护罩覆盖。"
group.addObject(params)

if source_shape:
    board_ref = doc.addObject("Part::Feature", "Board_Reference")
    board_ref.Label = "当前板卡参照"
    board_ref.Shape = source_shape
    board_ref.ViewObject.ShapeColor = (0.70, 0.72, 0.75)
    board_ref.ViewObject.Transparency = 68
    group.addObject(board_ref)

# Main-board chamber and side-by-side sensor chamber.
board_inner_x0 = BOARD_X_MIN - 2.0
board_inner_x1 = BOARD_X_MAX + 2.0
inner_y0 = BOARD_Y_MIN - 2.0
inner_y1 = BOARD_Y_MAX + 2.0
divider_x0 = board_inner_x1

sensor_x0 = divider_x0 + WALL + CLEARANCE
sensor_y0 = (inner_y0 + inner_y1 - SENSOR_WIDTH) / 2.0
sensor_x1 = sensor_x0 + SENSOR_LENGTH

inner_x0 = board_inner_x0
inner_x1 = sensor_x1 + CLEARANCE
outer_x0 = inner_x0 - WALL
outer_y0 = inner_y0 - WALL
outer_w = (inner_x1 - inner_x0) + 2.0 * WALL
outer_d = (inner_y1 - inner_y0) + 2.0 * WALL

outer_z0 = BOARD_Z_MIN - 1.5 - BOTTOM_THICKNESS
inner_z0 = outer_z0 + BOTTOM_THICKNESS
lid_z0 = BOARD_Z_MAX + 1.55
bottom_h = lid_z0 - outer_z0

outer_box = Part.makeBox(outer_w, outer_d, bottom_h, App.Vector(outer_x0, outer_y0, outer_z0))
inner_box = Part.makeBox(
    outer_w - 2.0 * WALL,
    outer_d - 2.0 * WALL,
    bottom_h - BOTTOM_THICKNESS + 0.1,
    App.Vector(outer_x0 + WALL, outer_y0 + WALL, inner_z0),
)
bottom_shape = outer_box.cut(inner_box)

# Low divider and a shallow locating frame for the sensor module.
divider = Part.makeBox(
    WALL,
    inner_y1 - inner_y0,
    3.0,
    App.Vector(divider_x0, inner_y0, inner_z0),
)
sensor_frame_outer = Part.makeBox(
    SENSOR_LENGTH + 2.0 * CLEARANCE,
    SENSOR_WIDTH + 2.0 * CLEARANCE,
    1.5,
    App.Vector(sensor_x0 - CLEARANCE, sensor_y0 - CLEARANCE, inner_z0),
)
sensor_frame_inner = Part.makeBox(
    SENSOR_LENGTH,
    SENSOR_WIDTH,
    1.6,
    App.Vector(sensor_x0, sensor_y0, inner_z0),
)
bottom_shape = bottom_shape.fuse(divider).fuse(sensor_frame_outer.cut(sensor_frame_inner))

bottom = doc.addObject("Part::Feature", "Enclosure_Bottom")
bottom.Label = "底壳"
bottom.Shape = bottom_shape
bottom.ViewObject.ShapeColor = (0.18, 0.42, 0.72)
group.addObject(bottom)

# Flat top cover with LCD opening and ventilation slots over the sensor.
lid_plate = Part.makeBox(outer_w, outer_d, LID_THICKNESS, App.Vector(outer_x0, outer_y0, lid_z0))

screen_opening = Part.makeBox(
    18.6,
    35.8,
    LID_THICKNESS + 1.0,
    App.Vector(-9.3, -19.2, lid_z0 - 0.5),
)
lid_shape = lid_plate.cut(screen_opening)

# Open the lid below the raised Dupont-wire hood.
dupont_x0 = 7.8
dupont_y0 = -6.5
dupont_w = 6.5
dupont_d = 14.0
dupont_opening = Part.makeBox(
    dupont_w,
    dupont_d,
    LID_THICKNESS + 1.0,
    App.Vector(dupont_x0, dupont_y0, lid_z0 - 0.5),
)
lid_shape = lid_shape.cut(dupont_opening)

# Five simple ventilation slots above the sensor compartment.
for slot_index in range(5):
    slot = Part.makeBox(
        17.0,
        1.4,
        LID_THICKNESS + 1.0,
        App.Vector(sensor_x0 + 4.2, sensor_y0 + 3.0 + slot_index * 3.5, lid_z0 - 0.5),
    )
    lid_shape = lid_shape.cut(slot)

# Downward locating lip with 0.3 mm assembly clearance.
lip_clearance = 0.3
lip_wall = 1.2
lip_outer = Part.makeBox(
    outer_w - 2.0 * (WALL + lip_clearance),
    outer_d - 2.0 * (WALL + lip_clearance),
    2.5,
    App.Vector(outer_x0 + WALL + lip_clearance, outer_y0 + WALL + lip_clearance, lid_z0 - 2.5),
)
lip_inner = Part.makeBox(
    outer_w - 2.0 * (WALL + lip_clearance + lip_wall),
    outer_d - 2.0 * (WALL + lip_clearance + lip_wall),
    2.6,
    App.Vector(
        outer_x0 + WALL + lip_clearance + lip_wall,
        outer_y0 + WALL + lip_clearance + lip_wall,
        lid_z0 - 2.55,
    ),
)
lid_shape = lid_shape.fuse(lip_outer.cut(lip_inner))

# Raised hollow hood: 16 mm clear vertical volume for Dupont plugs and wire bend.
hood_wall = 2.0
hood_outer_x0 = dupont_x0 - hood_wall
hood_outer_y0 = dupont_y0 - hood_wall
hood_outer_w = dupont_w + 2.0 * hood_wall
hood_outer_d = dupont_d + 2.0 * hood_wall
hood_outer_h = DUPONT_CLEARANCE_HEIGHT + hood_wall
hood_outer = Part.makeBox(
    hood_outer_w,
    hood_outer_d,
    hood_outer_h,
    App.Vector(hood_outer_x0, hood_outer_y0, lid_z0),
)
hood_inner = Part.makeBox(
    dupont_w,
    dupont_d,
    DUPONT_CLEARANCE_HEIGHT,
    App.Vector(dupont_x0, dupont_y0, lid_z0),
)
hood = hood_outer.cut(hood_inner)
lid_shape = lid_shape.fuse(hood)

lid = doc.addObject("Part::Feature", "Enclosure_Top")
lid.Label = "上盖（含杜邦线增高罩）"
lid.Shape = lid_shape
lid.ViewObject.ShapeColor = (0.82, 0.82, 0.86)
lid.ViewObject.Transparency = 15
group.addObject(lid)

sensor = doc.addObject("Part::Feature", "Sensor_Placeholder")
sensor.Label = "传感器占位 25.4×23×7 mm"
sensor.Shape = Part.makeBox(
    SENSOR_LENGTH,
    SENSOR_WIDTH,
    SENSOR_HEIGHT,
    App.Vector(sensor_x0, sensor_y0, inner_z0),
)
sensor.ViewObject.ShapeColor = (0.30, 0.75, 0.32)
sensor.ViewObject.Transparency = 62
group.addObject(sensor)

dupont_guide = doc.addObject("Part::Feature", "Dupont_Clearance_Guide")
dupont_guide.Label = "杜邦线净空 16 mm"
dupont_guide.Shape = Part.makeBox(
    dupont_w,
    dupont_d,
    DUPONT_CLEARANCE_HEIGHT,
    App.Vector(dupont_x0, dupont_y0, lid_z0),
)
dupont_guide.ViewObject.ShapeColor = (1.0, 0.70, 0.10)
dupont_guide.ViewObject.Transparency = 78
group.addObject(dupont_guide)

doc.recompute()

output_dir = "/Users/bytedance/Documents/New project"
doc.saveAs(output_dir + "/ESP32_S3_LCD_sensor_enclosure.FCStd")
Mesh.export([bottom], output_dir + "/ESP32_S3_LCD_enclosure_bottom.stl")
Mesh.export([lid], output_dir + "/ESP32_S3_LCD_enclosure_top.stl")

Gui.activeDocument().activeView().viewAxonometric()
Gui.activeDocument().activeView().fitAll()
print("ENCLOSURE_CREATED", outer_w, outer_d, bottom_h + LID_THICKNESS)
