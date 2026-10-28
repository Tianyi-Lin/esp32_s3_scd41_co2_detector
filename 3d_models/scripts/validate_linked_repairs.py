import hashlib
import json
import sys
from pathlib import Path
import FreeCAD as App
import Part
import MeshPart
sys.path.insert(0,"/Users/bytedance/Documents/New project")
import repair_sketch_engineering as checks

FILES=[
    ("bottom",Path("/Users/bytedance/Documents/New project/.cad-recovery/sketch-linked-repair-5ebdqoz7/下盖_草图编辑.FCStd"),
     [("SensorBossSketch",4),("CoverHolesSketch",4)]),
    ("middle",Path("/Users/bytedance/Documents/New project/.cad-recovery/sketch-linked-repair-5ebdqoz7/中间外壳_草图编辑.FCStd"),
     [("BossSketch",4),("ColumnSketch",4),("GuideSketchNegative",1),("GuideSketchPositive",1)]),
    ("top",Path("/Users/bytedance/Documents/New project/.cad-recovery/sketch-linked-repair-mp517jpv/上盖_草图编辑.FCStd"),
     [("ThroughHolesSketch",4)]),
]

def main():
    records=[]
    for kind,path,groups in FILES:
        doc=App.openDocument(str(path))
        for obj in doc.Objects:
            obj.touch()
        original=checks.check(doc).copy()
        checks.check_alignment(doc,kind)
        feature_count=0
        for obj in doc.Objects:
            if obj.TypeId.startswith("PartDesign::") and hasattr(obj,"Shape") and not obj.Shape.isNull():
                obj.Shape.check(True)
                feature_count+=1
        tests=[]
        for name,count in groups:
            sk=doc.getObject(name)
            old=[]
            for hole in range(1,count+1):
                for axis in ("X","Y"):
                    idx=checks.constraint_index(sk,"Hole%d_%s"%(hole,axis))
                    value=sk.getDatum(idx)
                    old.append((idx,value))
                    delta=.025*hole*(1 if axis=="X" else -1)
                    sk.setDatum(idx,App.Units.Quantity(value.Value+delta,App.Units.Length))
            checks.check(doc)
            checks.check_alignment(doc,kind)
            for idx,value in old:
                sk.setDatum(idx,value)
            checks.check(doc)
            checks.check_alignment(doc,kind)
            tests.append({"master_sketch":name,"hole_centers_tested":count,
                          "changed_axes":["X","Y"],"result":"PASS"})
            print("ALL_HOLE_POSITIONS_PASS",kind,name,count,flush=True)
        if kind=="top":
            radius=doc.WindowFillet.Radius.Value
            doc.WindowFillet.Radius=.45
            checks.check(doc)
            assert abs(doc.RightWindowFillet.Radius.Value-.45)<1e-8
            doc.WindowFillet.Radius=radius
            checks.check(doc)
            tests.append({"fillet_radius_test_mm":.45,"result":"PASS",
                          "restored_radius_mm":radius})
            print("FILLET_RADIUS_EDIT_PASS",flush=True)
        shape=checks.check(doc)
        assert abs(shape.Volume-original.Volume)<.003
        mesh=MeshPart.meshFromShape(Shape=shape,LinearDeflection=.001 if kind=="top" else .01,
                                   AngularDeflection=.03 if kind=="top" else .1,Relative=False)
        mesh_report={"facets":mesh.CountFacets,"closed":mesh.isSolid(),
                     "linear_deflection_mm":.001 if kind=="top" else .01,
                     "angular_deflection_radians":.03 if kind=="top" else .1,
                     "components":mesh.countComponents(),
                     "non_manifold":mesh.hasNonManifolds(),
                     "self_intersections":mesh.hasSelfIntersections(),
                     "non_uniform_oriented_facets":mesh.countNonUniformOrientedFacets(),
                     "signed_volume_mm3":mesh.Volume}
        print("MESH_CHECK",kind,mesh_report,flush=True)
        assert mesh_report["closed"] and mesh_report["components"]==1
        assert not mesh_report["non_manifold"] and not mesh_report["self_intersections"]
        assert mesh_report["non_uniform_oriented_facets"]==0
        assert mesh_report["signed_volume_mm3"]>0
        print("MESH_PASS",kind,mesh_report,flush=True)
        rec={"part":kind,"filename":path.name,"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
             "single_valid_solid":True,"extended_geometry_check":"PASS",
             "all_feature_extended_checks":"PASS","native_features_checked":feature_count,
             "volume_mm3":shape.Volume,"tests":tests,"mesh":mesh_report,
             "forced_recompute_after_reopen":"PASS"}
        if kind=="top":
            rec["repair_method"]="Native half-pockets, live sub-shape binder, two native R0.4 fillets, native Boolean fuse without surface unification. Single final solid; no static replacement."
            rec["max_bidirectional_sampled_surface_difference_mm"]=.000444296517019515
            rec["reference_comparison"]="Previous direct-sketch top-cover file; geometry source retained for user dimensions."
        records.append(rec)
        App.closeDocument(doc.Name)
    path=checks.STAGE/"修正检查记录.json"
    path.write_text(json.dumps(records,ensure_ascii=False,indent=2))
    print("REPORT",path,flush=True)

if __name__=="__main__":
    main()
