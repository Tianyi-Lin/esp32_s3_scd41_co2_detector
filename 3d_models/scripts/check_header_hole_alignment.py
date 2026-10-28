"""Read-only audit of the real ESP32 STEP pin holes, reference pins and slots."""
import os
import math
import FreeCAD as App
import Part

DIRECTORY = "/Users/bytedance/Downloads/ESP32-S3-LCD-1.47B_20260204 (1)"
for filename in ("ESP32-S3-LCD-1.47B_紧凑双层外壳.FCStd",
                 "ESP32-S3-LCD-1.47B_装配检查_爆炸图.FCStd"):
    doc=App.openDocument(os.path.join(DIRECTORY,filename))
    p=doc.DesignParameters
    axes=sorted({(round(f.Surface.Center.x,9),round(f.Surface.Center.y,9))
        for f in doc.ESP32BoardAssembly.Shape.Faces
        if isinstance(f.Surface,Part.Cylinder)
        and abs(abs(f.Surface.Axis.z)-1)<1e-8
        and abs(f.Surface.Radius-.5)<1e-5
        and abs(abs(f.Surface.Center.y)-8.89)<.01
        and abs(f.BoundBox.ZLength-.8)<1e-5})
    assert len(axes)==18,axes
    rows=[sorted((x,y) for x,y in axes if y*sign>0) for sign in (-1,1)]
    pitches=[row[i+1][0]-row[i][0] for row in rows for i in range(8)]
    assert max(abs(v-2.54) for v in pitches)<1e-7
    assert all(len(row)==9 for row in rows)
    pins=sorted((s.BoundBox.Center.x,s.BoundBox.Center.y)
                 for s in doc.HeaderPinsKeepout.Shape.Solids)
    assert len(pins)==18
    matched=[min(pins,key=lambda q:math.hypot(q[0]-x,q[1]-y)) for x,y in axes]
    assert len(set(matched))==18
    errors=[math.hypot(x-q[0],y-q[1]) for (x,y),q in zip(axes,matched)]
    assert max(errors)<.0001
    shell=doc.RearShell.Shape
    first_x=min(x for x,y in pins)
    last_x=max(x for x,y in pins)
    slot_xmin=first_x-p.HeaderSlotEndAxisDistance.Value
    slot_xmax=last_x+p.HeaderSlotEndAxisDistance.Value
    end_gaps=[]
    for row in rows:
        row_y=sum(y for x,y in row)/9
        slot_y=p.HeaderRowSpacing.Value/2*(1 if row_y>0 else -1)
        end_gaps.append((row[0][0]-slot_xmin,slot_xmax-row[-1][0]))
        tool=Part.makeBox(p.HeaderSlotLength.Value,p.HeaderSlotWidth.Value,
             p.HeaderSlotCutTopZ.Value-p.HeaderSlotCutBottomZ.Value,
             App.Vector(slot_xmin,slot_y-p.HeaderSlotWidth.Value/2,p.HeaderSlotCutBottomZ.Value))
        assert shell.common(tool).Volume<1e-7
        # Material probes confirm these are the actual slot boundaries, not
        # merely stale dimensions stored in the parameter object.
        probes=[Part.makeBox(.01,1,.5,App.Vector(x,slot_y-.5,14))
                for x in (slot_xmin-.01,slot_xmax)]
        probes += [Part.makeBox(.5,.01,.5,App.Vector(-14.5,y,14))
                   for y in (slot_y-p.HeaderSlotWidth.Value/2-.01,
                             slot_y+p.HeaderSlotWidth.Value/2)]
        assert all(probe.cut(shell).Volume<1e-7 for probe in probes)
        assert abs(row_y-slot_y)<.0001
    projected_tools=Part.makeCompound([Part.makeCylinder(.65,
         p.HeaderSlotCutTopZ.Value-p.HeaderSlotCutBottomZ.Value,
         App.Vector(x,y,p.HeaderSlotCutBottomZ.Value)) for x,y in axes])
    assert shell.common(projected_tools).Volume<1e-7
    print("AUDITED",filename,flush=True)
    print("PINS_PER_ROW",[len(row) for row in rows],"ACTUAL_PITCH_RANGE",(min(pitches),max(pitches)),
          "ACTUAL_ROW_SPACING",rows[1][0][1]-rows[0][0][1],flush=True)
    print("MAX_XY_AXIS_ERROR_MM",max(errors),"ACTUAL_END_AXIS_GAPS_MM",end_gaps,
          "SLOT_WIDTH",p.HeaderSlotWidth.Value,"SLOT_LENGTH",p.HeaderSlotLength.Value,
          "PIN_AXIS_PROJECTED_CLEARANCE_INTERFERENCE",shell.common(projected_tools).Volume,flush=True)
    print("BOARD_HOLE_ROWS",rows,flush=True)
    print("EXPLODED_Z_SEPARATION_ONLY",doc.ESP32BoardAssembly.Placement.Base.z,
          doc.HeaderPinsKeepout.Placement.Base.z,flush=True)
    App.closeDocument(doc.Name)
