import Mesh

base = "/Users/bytedance/Documents/New project"
assembly = Mesh.Mesh(base + "/ESP32_S3_LCD_enclosure_bottom_LITE.stl")
top = Mesh.Mesh(base + "/ESP32_S3_LCD_enclosure_top_LITE.stl")
assembly.addMesh(top)
assembly.write(base + "/ESP32_S3_LCD_enclosure_preview.stl")
print("STL_PREVIEW_OK", assembly.CountFacets)
