import os

import FreeCAD as App
import Part


OUT_DIR = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
SOURCE_PATH = os.path.join(OUT_DIR, "ESP32-S3-LCD-1.47B_外壳_装配预览.FCStd")
OUTPUT_PATH = os.path.join(OUT_DIR, "ESP32-S3-LCD-1.47B_外壳_CO2背装预览.FCStd")

doc = App.openDocument(SOURCE_PATH)
board = doc.getObject("ESP32BoardAssembly")
sensor = doc.getObject("SensorKeepout")
bottom = doc.getObject("BottomCase")

# Stack the 25.4 x 23 x 7 mm CO2 module beneath the ESP32, toward the back
# shell.  The module sits 0.5 mm above the 2.5 mm floor.
sensor.Shape = Part.makeBox(
    25.4,
    23.0,
    7.0,
    App.Vector(-30.7, -11.5, 3.0),
)
sensor.Label = "CO₂ 传感器背装预留体 25.4×23×7"

# Raise the real ESP32 assembly so its lowest point is at Z=11 mm,
# leaving 1 mm between it and the top of the CO2 module.
bb = board.Shape.BoundBox
board.Placement.Base.z += 11.0 - bb.ZMin
board.PlacementNote = (
    "CO2 module mounted behind ESP32: sensor Z=3–10 mm, "
    "1 mm gap, ESP32 minimum Z=11 mm."
)

params = doc.getObject("DesignParameters")
if params:
    params.LayoutNote = (
        "Stacked layout: 25.4×23×7 mm CO2 sensor behind the ESP32. "
        "Sensor Z=3–10 mm; ESP32 Z=11–19.3 mm."
    )

# Add readable stack dimensions to the sensor reference object.
for name, value in (
    ("FloorGap", 0.5),
    ("BoardGap", 1.0),
):
    if name not in sensor.PropertiesList:
        sensor.addProperty("App::PropertyLength", name, "StackClearances")
    setattr(sensor, name, value)

doc.recompute()

# Verify the simplified sensor envelope does not cut the printable shell.
shell_overlap = sensor.Shape.common(bottom.Shape).Volume
board_sensor_overlap = board.Shape.common(sensor.Shape).Volume
if shell_overlap > 0.01:
    raise RuntimeError(f"CO2 sensor intersects bottom shell: {shell_overlap:.3f} mm3")
if board_sensor_overlap > 0.01:
    raise RuntimeError(f"CO2 sensor intersects ESP32 assembly: {board_sensor_overlap:.3f} mm3")

doc.saveAs(OUTPUT_PATH)
print("CO2_BACK_ASSEMBLY_CREATED", OUTPUT_PATH)
print(
    "STACK_Z",
    round(sensor.Shape.BoundBox.ZMin, 2),
    round(sensor.Shape.BoundBox.ZMax, 2),
    round(board.Shape.BoundBox.ZMin, 2),
    round(board.Shape.BoundBox.ZMax, 2),
)
print("OVERLAP_VOLUMES", round(shell_overlap, 6), round(board_sensor_overlap, 6))
