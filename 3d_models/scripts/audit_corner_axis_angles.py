import math
import FreeCAD as App
import Part
d=App.openDocument('/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)/ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd')
board=d.ESP32BoardAssembly.Shape
for angle in (36.869897645844,45,50,55,60):
    t=math.radians(angle)
    x=17.5+1.45*math.cos(t)
    y=11.75+1.45*math.sin(t)
    for sx in (-1,1):
        col=Part.makeCylinder(3.55,22.95,App.Vector(sx*x,y,2.05))
        overlap=col.common(board)
        print('ANGLE',angle,'XY',x,y,'SIDE',sx,'OVERLAP',overlap.Volume,
              'CLEARANCE',col.distToShape(board)[0],
              'OVERLAP_BOUNDS',str(overlap.BoundBox),flush=True)
