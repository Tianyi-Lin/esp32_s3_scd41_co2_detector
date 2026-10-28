"""Persist display-only appearance in a headless-generated FreeCAD assembly.

Reuse the project's native GUI appearance template. The document data and every
geometry payload are preserved byte-for-byte. Run with standard Python 3.
The template's material-list format is explicitly checked before modification.
"""
from pathlib import Path
import argparse
import math
import os
import struct
import tempfile
import xml.etree.ElementTree as ET
import zipfile


SHELLS = {"FrontBezel", "RemovableBottomCover", "RearShell"}
OPAQUE = {"ButtonPlungerPositive", "ButtonPlungerNegative",
          "ESP32BoardAssembly", "HeaderPinsKeepout", "CO2SensorPCB",
          "CO2SensorCan", "CO2SensorConnectors"}


def style_assembly(target, template, output):
    with zipfile.ZipFile(target) as source, zipfile.ZipFile(template) as style:
        assert "GuiDocument.xml" not in source.namelist(), (
            "This helper only styles headless output; preserve existing GUI edits."
        )
        document = ET.fromstring(source.read("Document.xml"))
        names = {o.get("name") for o in document.find("Objects") if o.get("name")}
        assert SHELLS | OPAQUE <= names
        gui = ET.fromstring(style.read("GuiDocument.xml"))
        providers = gui.find("ViewProviderData")
        material_transparency = {}
        for provider in list(providers):
            name = provider.get("name")
            if name not in names:
                providers.remove(provider)
                continue
            if name in SHELLS | OPAQUE:
                value = 50 if name in SHELLS else 0
                provider.find("./Properties/Property[@name='Transparency']/Integer").set("value", str(value))
                provider.find("./Properties/Property[@name='Visibility']/Bool").set("value", "true")
                material = provider.find("./Properties/Property[@name='ShapeAppearance']/MaterialList")
                assert material.get("version") == "3"
                material_transparency[material.get("file")] = value / 100
        providers.set("Count", str(len(providers)))

        # Native template hides the duplicate CO2 collision envelope, while
        # keeping its individual PCB, sensor and connector objects visible.
        for name in ["CO2SensorEnvelope", "DesignParameters"]:
            gui.find("./ViewProviderData/ViewProvider[@name='%s']/Properties/Property[@name='Visibility']/Bool" % name).set("value", "false")

        # Keep the template's viewing direction, but center the taller assembly
        # and give it an explicitly safe depth range (millimeters).
        axis = (0.47179145, 0.74463248, 0.47216013)
        length = math.sqrt(sum(v*v for v in axis))
        x, y, z = (v / length for v in axis)
        angle = 1.9817252
        c, s = math.cos(angle), math.sin(angle)
        direction = (y*s + x*z*(1-c), -x*s + y*z*(1-c), c + z*z*(1-c))
        center = (0, 0.75, 18.01523939289622)
        position = tuple(a + 100*b for a, b in zip(center, direction))
        gui.find("Camera").set("settings", (
            "OrthographicCamera {\n  viewportMapping ADJUST_CAMERA\n"
            "  position %s\n  orientation %s %s\n"
            "  nearDistance 1\n  farDistance 200\n  aspectRatio 1\n"
            "  focalDistance 100\n  height 95\n}\n"
        ) % (" ".join(map(str, position)), " ".join(map(str, axis)), angle))

        resources = {e.get("file") for e in gui.iter() if e.get("file")}
        assert not resources & set(source.namelist()), "Unexpected resource collision"
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as dest:
            for item in source.infolist():
                dest.writestr(item, source.read(item.filename))
            for name in sorted(resources):
                data = style.read(name)
                if name in material_transparency:
                    assert len(data) == 40 and struct.unpack_from("<I", data)[0] == 1
                    assert abs(struct.unpack_from("<f", data, 24)[0] - .6) < 1e-6
                    data = data[:24] + struct.pack("<f", material_transparency[name]) + data[28:]
                dest.writestr(name, data)
            dest.writestr("GuiDocument.xml", ET.tostring(gui, encoding="utf-8", xml_declaration=True))

    with zipfile.ZipFile(target) as original, zipfile.ZipFile(output) as result:
        assert all(original.read(n) == result.read(n) for n in original.namelist())
        gui = ET.fromstring(result.read("GuiDocument.xml"))
        for name in SHELLS | OPAQUE:
            provider = gui.find("./ViewProviderData/ViewProvider[@name='%s']" % name)
            expected = 50 if name in SHELLS else 0
            assert int(provider.find("./Properties/Property[@name='Transparency']/Integer").get("value")) == expected
            material = provider.find("./Properties/Property[@name='ShapeAppearance']/MaterialList").get("file")
            assert abs(struct.unpack_from("<f", result.read(material), 24)[0] - expected/100) < 1e-6


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    root = args.root.resolve()
    target = root / "盖板2.5mm_中壳加深_20261028/装配检查_盖板2.5mm_中间壳加深.FCStd"
    template = root / "ESP32-S3-LCD-1.47B_紧凑装配_五色半透明检查.FCStd"
    fd, temporary = tempfile.mkstemp(prefix="appearance-", suffix=".FCStd", dir=target.parent)
    os.close(fd)
    try:
        style_assembly(target, template, Path(temporary))
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print("Saved: three enclosure pieces 50% transparent; electronics opaque.")
    print("Original document and geometry payloads unchanged.")


if __name__ == "__main__":
    main()
