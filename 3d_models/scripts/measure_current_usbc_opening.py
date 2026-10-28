"""Read-only measurements from actual outer-face opening wires."""
import FreeCAD as App
import Part

ROOT = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)/"
for filename in ("ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd",
                 "ESP32-S3-LCD-1.47B_紧凑装配_五色半透明检查.FCStd"):
    doc = App.openDocument(ROOT + filename)
    shell = doc.RearShell.Shape
    print("FILE", filename, flush=True)
    print("USB_PARAMETERS", doc.DesignParameters.USBCutWidth.Value,
          doc.DesignParameters.USBCutHeight.Value, flush=True)
    matches = []
    for face in shell.Faces:
        if (isinstance(face.Surface, Part.Plane)
                and face.BoundBox.XLength < 1e-6
                and abs(face.BoundBox.XMin - shell.BoundBox.XMax) < 1e-6):
            for wire in face.Wires:
                bb = wire.BoundBox
                if 10 < bb.YLength < 15 and 4 < bb.ZLength < 8:
                    matches.append(wire)
                    print("ACTUAL_USB_OUTER_OPENING_YZ", bb.YMin, bb.YMax,
                          bb.ZMin, bb.ZMax, "TOTAL", bb.YLength, bb.ZLength,
                          flush=True)
                    for edge in wire.Edges:
                        print("BOUNDARY_EDGE", type(edge.Curve).__name__,
                              "LENGTH", edge.Length, "RADIUS",
                              getattr(edge.Curve, "Radius", None), flush=True)
    assert len(matches) == 1, len(matches)
    App.closeDocument(doc.Name)
