import FreeCAD as App
import Part
import Mesh


# Lightweight, reload-safe enclosure model. Units: mm.
WALL = 2.0
CLEARANCE = 1.0
BOTTOM_THICKNESS = 2.0
LID_THICKNESS = 2.0
DUPONT_CLEARANCE_HEIGHT = 16.0

SENSOR_LENGTH = 25.4
SENSOR_WIDTH = 23.0
SENSOR_HEIGHT = 7.0

# Simplified envelope measured from the ESP32-S3-LCD-1.47B STEP assembly.
BOARD_X_MIN = -11.36
BOARD_X_MAX = 11.36
BOARD_Y_MIN = -20.36
BOARD_Y_MAX = 17.22
BOARD_Z_MIN = -6.85
BOARD_Z_MAX = 1.45

doc = App.newDocument("ESP32_Enclosure_Lite", "ESP32 Enclosure Lite")
group = doc.addObject("App::DocumentObjectGroup", "Enclosure_Design")
group.Label = "外壳设计（轻量稳定版）"


def set_view(obj, color, transparency=0):
    if getattr(obj, "ViewObject", None):
        obj.ViewObject.ShapeColor = color
        obj.ViewObject.Transparency = transparency

params = doc.addObject("App::FeaturePython", "Enclosure_Parameters")
params.Label = "外壳参数"
for name, label, value in (
    ("WallThickness", "壁厚", WALL),
    ("AssemblyClearance", "装配间隙", CLEARANCE),
    ("SensorLength", "传感器长度", SENSOR_LENGTH),
    ("SensorWidth", "传感器宽度", SENSOR_WIDTH),
    ("SensorHeight", "传感器高度", SENSOR_HEIGHT),
    ("DupontClearanceHeight", "杜邦线预留高度", DUPONT_CLEARANCE_HEIGHT),
):
    params.addProperty("App::PropertyLength", name, "尺寸参数", label)
    setattr(params, name, value)
params.addProperty("App::PropertyString", "DesignNote", "说明", "设计说明")
params.DesignNote = "不嵌入原始STEP；灰色板卡为简化包络，传感器在右侧，杜邦线净高16mm。"
group.addObject(params)

# A simple envelope replaces the large imported STEP to avoid reload crashes.
board_ref = doc.addObject("Part::Feature", "Board_Envelope")
board_ref.Label = "板卡简化包络"
board_ref.Shape = Part.makeBox(
    BOARD_X_MAX - BOARD_X_MIN,
    BOARD_Y_MAX - BOARD_Y_MIN,
    BOARD_Z_MAX - BOARD_Z_MIN,
    App.Vector(BOARD_X_MIN, BOARD_Y_MIN, BOARD_Z_MIN),
)
set_view(board_ref, (0.65, 0.68, 0.72), 72)
group.addObject(board_ref)

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

divider = Part.makeBox(WALL, inner_y1 - inner_y0, 3.0, App.Vector(divider_x0, inner_y0, inner_z0))
frame_outer = Part.makeBox(
    SENSOR_LENGTH + 2.0 * CLEARANCE,
    SENSOR_WIDTH + 2.0 * CLEARANCE,
    1.5,
    App.Vector(sensor_x0 - CLEARANCE, sensor_y0 - CLEARANCE, inner_z0),
)
frame_inner = Part.makeBox(
    SENSOR_LENGTH,
    SENSOR_WIDTH,
    1.6,
    App.Vector(sensor_x0, sensor_y0, inner_z0),
)
bottom_shape = bottom_shape.fuse(divider).fuse(frame_outer.cut(frame_inner))

bottom = doc.addObject("Part::Feature", "Enclosure_Bottom")
bottom.Label = "底壳"
bottom.Shape = bottom_shape
set_view(bottom, (0.18, 0.42, 0.72))
group.addObject(bottom)

lid_shape = Part.makeBox(outer_w, outer_d, LID_THICKNESS, App.Vector(outer_x0, outer_y0, lid_z0))
screen_opening = Part.makeBox(18.6, 35.8, 3.0, App.Vector(-9.3, -19.2, lid_z0 - 0.5))
lid_shape = lid_shape.cut(screen_opening)

dupont_x0 = 7.8
dupont_y0 = -6.5
dupont_w = 6.5
dupont_d = 14.0
dupont_opening = Part.makeBox(dupont_w, dupont_d, 3.0, App.Vector(dupont_x0, dupont_y0, lid_z0 - 0.5))
lid_shape = lid_shape.cut(dupont_opening)

for i in range(5):
    slot = Part.makeBox(17.0, 1.4, 3.0, App.Vector(sensor_x0 + 4.2, sensor_y0 + 3.0 + i * 3.5, lid_z0 - 0.5))
    lid_shape = lid_shape.cut(slot)

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

hood_wall = 2.0
hood_outer = Part.makeBox(
    dupont_w + 2.0 * hood_wall,
    dupont_d + 2.0 * hood_wall,
    DUPONT_CLEARANCE_HEIGHT + hood_wall,
    App.Vector(dupont_x0 - hood_wall, dupont_y0 - hood_wall, lid_z0),
)
hood_inner = Part.makeBox(
    dupont_w,
    dupont_d,
    DUPONT_CLEARANCE_HEIGHT,
    App.Vector(dupont_x0, dupont_y0, lid_z0),
)
lid_shape = lid_shape.fuse(hood_outer.cut(hood_inner))

lid = doc.addObject("Part::Feature", "Enclosure_Top")
lid.Label = "上盖（含杜邦线增高罩）"
lid.Shape = lid_shape
set_view(lid, (0.82, 0.82, 0.86), 15)
group.addObject(lid)

sensor = doc.addObject("Part::Feature", "Sensor_Placeholder")
sensor.Label = "传感器占位 25.4×23×7 mm"
sensor.Shape = Part.makeBox(SENSOR_LENGTH, SENSOR_WIDTH, SENSOR_HEIGHT, App.Vector(sensor_x0, sensor_y0, inner_z0))
set_view(sensor, (0.30, 0.75, 0.32), 62)
group.addObject(sensor)

dupont = doc.addObject("Part::Feature", "Dupont_Clearance_Guide")
dupont.Label = "杜邦线净空 16 mm"
dupont.Shape = Part.makeBox(dupont_w, dupont_d, DUPONT_CLEARANCE_HEIGHT, App.Vector(dupont_x0, dupont_y0, lid_z0))
set_view(dupont, (1.0, 0.70, 0.10), 78)
group.addObject(dupont)

doc.recompute()
out = "/Users/bytedance/Documents/New project"
doc.saveAs(out + "/ESP32_S3_LCD_sensor_enclosure_LITE.FCStd")
Mesh.export([bottom], out + "/ESP32_S3_LCD_enclosure_bottom_LITE.stl")
Mesh.export([lid], out + "/ESP32_S3_LCD_enclosure_top_LITE.stl")

if "Gui" in globals():
    Gui.activeDocument().activeView().viewAxonometric()
    Gui.activeDocument().activeView().fitAll()

print("LITE_CREATED", outer_w, outer_d, bottom_h + LID_THICKNESS)
