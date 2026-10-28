"""Compare cover rim choices against current electronics; read-only."""
import FreeCAD as App
import Part

PATH="/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)/ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd"
d=App.openDocument(PATH)
shell=d.RearShell.Shape
for rim in (1.0,1.1,1.2,1.25,1.5):
    radius=2.55+rim
    delta=5-radius
    x=17.5+.8*delta
    y=11.75+.6*delta
    towers=Part.makeCompound([Part.makeCylinder(radius,22.95,App.Vector(sx*x,sy*y,2.05))
                             for sx in (-1,1) for sy in (-1,1)])
    additions=towers.cut(shell)
    # Re-apply the existing narrow passages before checking the pin keep-out.
    slots=Part.makeCompound([Part.makeBox(22.92,2.6,7.936,App.Vector(-15.349,ry-1.3,10))
                            for ry in (-8.89,8.89)])
    additions=additions.cut(slots)
    results={name:additions.common(d.getObject(name).Shape).Volume
             for name in ("ESP32BoardAssembly","HeaderPinsKeepout","CO2SensorEnvelope",
                          "ButtonPlungerPositive","ButtonPlungerNegative")}
    print("OPTION",rim,"HOLE_XY",(x,y),"COLUMN_RADIUS",radius,
          "THROUGH_WALL",radius-1.15,"INTERFERENCES_MM3",results,flush=True)
App.closeDocument(d.Name)
