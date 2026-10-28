import os
import FreeCAD as App


source_path = (
    "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)/"
    "ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd"
)
output_path = (
    "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)/"
    "ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd"
)

doc = App.openDocument(source_path)


def move_z(object_name, distance):
    obj = doc.getObject(object_name)
    if obj is None:
        raise RuntimeError("Missing object: " + object_name)
    placement = obj.Placement
    placement.Base.z += distance
    obj.Placement = placement


top_offset = 30.0
esp32_offset = 15.0
co2_offset = -18.0
bottom_offset = -32.0

# Separate every assembly layer so the electronics are visible instead of
# travelling with (or remaining hidden inside) an enclosure half.
move_z("FrontBezel", top_offset)
move_z("ESP32BoardAssembly", esp32_offset)

move_z("RemovableBottomCover", bottom_offset)
for object_name in (
    "CO2SensorEnvelope",
    "CO2SensorPCB",
    "CO2SensorCan",
    "CO2SensorConnectors",
):
    move_z(object_name, co2_offset)

info = doc.addObject("App::FeaturePython", "ExplodedViewParameters")
info.Label = "爆炸检查偏移（毫米）"
info.addProperty("App::PropertyLength", "FrontCoverOffsetZ", "ExplodedView")
info.FrontCoverOffsetZ = top_offset
info.addProperty("App::PropertyLength", "ESP32OffsetZ", "ExplodedView")
info.ESP32OffsetZ = esp32_offset
info.addProperty("App::PropertyLength", "CO2SensorOffsetZ", "ExplodedView")
info.CO2SensorOffsetZ = co2_offset
info.addProperty("App::PropertyLength", "BottomCoverOffsetZ", "ExplodedView")
info.BottomCoverOffsetZ = bottom_offset
info.addProperty("App::PropertyString", "Instructions", "ExplodedView")
info.Instructions = (
    "完整爆炸图：上盖上移 30 mm；ESP32 上移 15 mm；"
    "CO2 模块下移 18 mm；底盖下移 32 mm。"
    "选中零件后可通过 Placement 或右键‘变换’继续拖动。"
)

doc.recompute()
doc.saveAs(output_path)
print("EXPLODED_CREATED", output_path)
