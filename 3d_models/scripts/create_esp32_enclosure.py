import FreeCAD as App
import Part


OUT_DIR = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
FCSTD_PATH = OUT_DIR + "/ESP32-S3-LCD-1.47B_外壳.FCStd"
BASE_STL_PATH = OUT_DIR + "/ESP32-S3-LCD-1.47B_外壳_底壳.stl"
LID_STL_PATH = OUT_DIR + "/ESP32-S3-LCD-1.47B_外壳_上盖.stl"


def rounded_prism(width, depth, height, radius, z=0.0):
    """Rounded rectangle prism centered on X/Y."""
    x0 = -width / 2.0
    y0 = -depth / 2.0
    shape = Part.makeBox(width - 2 * radius, depth, height,
                         App.Vector(x0 + radius, y0, z))
    shape = shape.fuse(Part.makeBox(width, depth - 2 * radius, height,
                                    App.Vector(x0, y0 + radius, z)))
    for x in (x0 + radius, x0 + width - radius):
        for y in (y0 + radius, y0 + depth - radius):
            shape = shape.fuse(Part.makeCylinder(radius, height,
                                                  App.Vector(x, y, z)))
    return shape.removeSplitter()


doc_name = "ESP32_S3_LCD_Enclosure"
try:
    old = App.getDocument(doc_name)
except NameError:
    old = None
if old:
    App.closeDocument(doc_name)
doc = App.newDocument(doc_name, "ESP32-S3-LCD-1.47B 外壳")

# Main design dimensions (mm)
outer_w = 67.0
outer_d = 48.0
base_h = 21.5
wall = 2.0
floor = 2.5
corner_r = 5.0
lid_t = 3.0
fit_gap = 0.35

# Bottom enclosure with open top
outer = rounded_prism(outer_w, outer_d, base_h, corner_r, 0)
inner = rounded_prism(outer_w - 2 * wall, outer_d - 2 * wall,
                      base_h - floor + 1.0, corner_r - wall, floor)
base_shape = outer.cut(inner)

# USB-C opening on the front wall, aligned with the ESP32 bay
usb_opening = Part.makeBox(14.0, 5.0, 8.5,
                           App.Vector(-25.0, -outer_d / 2.0 - 0.5, 3.8))
base_shape = base_shape.cut(usb_opening)

# Tall Dupont-wire exit: 12 mm vertical clearance on the right wall
dupont_opening = Part.makeBox(5.0, 20.0, 12.0,
                              App.Vector(outer_w / 2.0 - 2.5, -10.0, 7.0))
base_shape = base_shape.cut(dupont_opening)

# PCB and sensor mounting bosses
bosses = []
pcb_boss_xy = [(-26.5, -15.0), (-9.5, -15.0),
               (-26.5, 15.0), (-9.5, 15.0)]
sensor_boss_xy = [(6.0, -8.5), (26.0, -8.5),
                  (6.0, 8.5), (26.0, 8.5)]
for x, y in pcb_boss_xy:
    bosses.append((Part.makeCylinder(2.8, 4.0, App.Vector(x, y, floor)), x, y, 2.1))
for x, y in sensor_boss_xy:
    bosses.append((Part.makeCylinder(2.5, 3.5, App.Vector(x, y, floor)), x, y, 1.8))

# Four corner screw towers
corner_towers = [(-28.0, -18.5), (28.0, -18.5),
                 (-28.0, 18.5), (28.0, 18.5)]
for x, y in corner_towers:
    bosses.append((Part.makeCylinder(3.4, base_h - floor,
                                      App.Vector(x, y, floor)), x, y, 2.4))

for boss, x, y, hole_d in bosses:
    base_shape = base_shape.fuse(boss)
    hole = Part.makeCylinder(hole_d / 2.0, base_h + 2.0,
                             App.Vector(x, y, 1.5))
    base_shape = base_shape.cut(hole)
base_shape = base_shape.removeSplitter()

base_obj = doc.addObject("PartDesign::Feature", "BottomCase")
base_obj.Label = "底壳（USB 与杜邦线开口）"
base_obj.Shape = base_shape
base_obj.addProperty("App::PropertyLength", "DupontVerticalClearance", "Clearances")
base_obj.DupontVerticalClearance = 12.0
base_obj.addProperty("App::PropertyString", "Note", "Clearances")
base_obj.Note = "Right-wall slot reserves 12 mm vertical clearance for Dupont wires."
base_obj.ViewObject.ShapeColor = (0.22, 0.48, 0.82)

# Lid plate
lid_shape = rounded_prism(outer_w, outer_d, lid_t, corner_r, base_h)

# Display window above the ESP32 module (left bay)
screen_window = Part.makeBox(20.5, 35.5, lid_t + 2.0,
                             App.Vector(-28.25, -17.75, base_h - 1.0))
lid_shape = lid_shape.cut(screen_window)

# Vent slots above the sensor bay
for y in (-8.0, -4.0, 0.0, 4.0, 8.0):
    vent = Part.makeBox(18.0, 1.8, lid_t + 2.0,
                        App.Vector(7.0, y - 0.9, base_h - 1.0))
    lid_shape = lid_shape.cut(vent)

# Locating rim under the lid
rim_outer = rounded_prism(outer_w - 2 * wall - 2 * fit_gap,
                          outer_d - 2 * wall - 2 * fit_gap,
                          2.0, corner_r - wall - fit_gap, base_h - 2.0)
rim_inner = rounded_prism(outer_w - 4 * wall - 2 * fit_gap,
                          outer_d - 4 * wall - 2 * fit_gap,
                          2.5, max(corner_r - 2 * wall - fit_gap, 0.8),
                          base_h - 2.25)
lid_shape = lid_shape.fuse(rim_outer.cut(rim_inner))

# Lid screw clearance holes
for x, y in corner_towers:
    hole = Part.makeCylinder(1.35, lid_t + 3.0,
                             App.Vector(x, y, base_h - 2.5))
    lid_shape = lid_shape.cut(hole)
lid_shape = lid_shape.removeSplitter()

lid_obj = doc.addObject("PartDesign::Feature", "TopLid")
lid_obj.Label = "上盖（屏幕窗口与传感器散热孔）"
lid_obj.Shape = lid_shape
lid_obj.ViewObject.ShapeColor = (0.82, 0.84, 0.88)
lid_obj.ViewObject.Transparency = 25

# Reference keep-out volumes (not printable solids)
pcb_ref = doc.addObject("PartDesign::Feature", "PCBKeepout")
pcb_ref.Label = "ESP32 模块参考体 22.72×37.58×8.30"
pcb_ref.Shape = Part.makeBox(22.72, 37.58, 8.30,
                             App.Vector(-29.36, -18.79, 5.0))
pcb_ref.ViewObject.ShapeColor = (0.12, 0.65, 0.20)
pcb_ref.ViewObject.Transparency = 72

sensor_ref = doc.addObject("PartDesign::Feature", "SensorKeepout")
sensor_ref.Label = "传感器预留体 25.4×23×7"
sensor_ref.Shape = Part.makeBox(25.4, 23.0, 7.0,
                                App.Vector(3.3, -11.5, 5.0))
sensor_ref.ViewObject.ShapeColor = (0.94, 0.52, 0.12)
sensor_ref.ViewObject.Transparency = 68

wire_ref = doc.addObject("PartDesign::Feature", "DupontWireKeepout")
wire_ref.Label = "杜邦线高度预留 12 mm"
wire_ref.Shape = Part.makeBox(9.0, 18.0, 12.0,
                              App.Vector(24.5, -9.0, 7.0))
wire_ref.ViewObject.ShapeColor = (0.88, 0.20, 0.20)
wire_ref.ViewObject.Transparency = 82

# Editable design notes and dimensions
params = doc.addObject("App::FeaturePython", "DesignParameters")
params.Label = "设计参数（毫米）"
for name, value in (
    ("OuterWidth", outer_w),
    ("OuterDepth", outer_d),
    ("BaseHeight", base_h),
    ("WallThickness", wall),
    ("FloorThickness", floor),
    ("LidThickness", lid_t),
    ("DupontClearanceHeight", 12.0),
    ("SensorLength", 25.4),
    ("SensorWidth", 23.0),
    ("SensorHeight", 7.0),
):
    params.addProperty("App::PropertyLength", name, "Dimensions")
    setattr(params, name, value)
params.addProperty("App::PropertyString", "LayoutNote", "Documentation")
params.LayoutNote = "Left bay: ESP32 display module. Right bay: 25.4×23×7 mm sensor."

print_group = doc.addObject("App::DocumentObjectGroup", "PrintableParts")
print_group.Label = "可打印零件"
print_group.addObject(base_obj)
print_group.addObject(lid_obj)

reference_group = doc.addObject("App::DocumentObjectGroup", "ReferenceVolumes")
reference_group.Label = "安装参考体（不打印）"
reference_group.addObject(pcb_ref)
reference_group.addObject(sensor_ref)
reference_group.addObject(wire_ref)

doc.recompute()
doc.recompute()
doc.saveAs(FCSTD_PATH)
Part.export([base_obj], BASE_STL_PATH)
Part.export([lid_obj], LID_STL_PATH)

# Present an inspection-friendly view: base and keep-outs visible, lid hidden.
lid_obj.ViewObject.Visibility = False
pcb_ref.ViewObject.Visibility = True
sensor_ref.ViewObject.Visibility = True
wire_ref.ViewObject.Visibility = True
doc.save()
Gui.activeDocument().activeView().viewAxonometric()
Gui.activeDocument().activeView().fitAll()
Gui.activeDocument().activeView().setNavigationType("Gui::SolidWorksNavigationStyle")
print("ENCLOSURE_CREATED", FCSTD_PATH)
