"""Read-only measurement of screw seating planes and ESP32 metal inserts."""
import FreeCAD as A
import Part

doc = A.openDocument("/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)/ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd")
mounts = [(-16.814, -6.64), (-16.814, 6.64), (15.186, -8.16), (15.186, 8.16)]


def bbox(s):
    b = s.optimalBoundingBox(False, False)
    return [round(getattr(b, a), 7) for a in ("XMin","XMax","YMin","YMax","ZMin","ZMax")]


for name in ("FrontBezel", "RemovableBottomCover", "RearShell", "CO2SensorPCB"):
    s = doc.getObject(name).Shape
    print("PART", name, bbox(s), flush=True)
    for i, f in enumerate(s.Faces, 1):
        if isinstance(f.Surface, Part.Cylinder) and abs(f.Surface.Axis.z) > .99:
            surf = f.Surface
            r, x, y = surf.Radius, surf.Center.x, surf.Center.y
            if any(abs(r-a) < .001 for a in (1.1, 1.15, 1.4, 1.45, 1.7, 2.5, 2.55)):
                print("CYLINDER", name, i, "axis", (x,y), "R", r, "z", (f.BoundBox.ZMin,f.BoundBox.ZMax), flush=True)
    planes = [(i+1,f.Area,f.CenterOfMass.z,tuple(f.normalAt(0,0))) for i,f in enumerate(s.Faces)
              if isinstance(f.Surface,Part.Plane) and f.BoundBox.ZLength<1e-6 and f.Area>2]
    print("HORIZONTAL", name, planes, flush=True)

board = doc.ESP32BoardAssembly.Shape
for n, s in enumerate(board.Solids, 1):
    b = s.BoundBox
    if b.XLength < 8 and b.YLength < 8 and any(b.XMin < x < b.XMax and b.YMin < y < b.YMax for x,y in mounts):
        print("ESP_MOUNT_SOLID", n, "bbox", bbox(s), "volume",s.Volume, flush=True)
        for j, f in enumerate(s.Faces,1):
            surf = f.Surface
            if isinstance(surf, Part.Cylinder):
                print("INSERT_CYL", n, j, "axis",tuple(surf.Axis), "center",tuple(surf.Center),
                      "R",surf.Radius,"bounds",bbox(f),flush=True)
            elif isinstance(surf,Part.Plane) and f.BoundBox.ZLength<1e-6:
                print("INSERT_PLANE",n,j,"z",f.CenterOfMass.z,"area",f.Area,"normal",tuple(f.normalAt(0,0)),flush=True)
for x,y in mounts:
    # Probe the insertion axis for solid material beyond the metal insert.
    line = Part.makeLine(A.Vector(x,y,17),A.Vector(x,y,30))
    common = board.common(line)
    print("AXIS_MATERIAL",x,y,[(e.BoundBox.ZMin,e.BoundBox.ZMax) for e in common.Edges],flush=True)
A.closeDocument(doc.Name)
