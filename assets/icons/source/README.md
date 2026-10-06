<!-- SPDX-License-Identifier: AGPL-3.0-only -->
# Icon source files / Ikon-forrásfájlok

One file per icon, named exactly as the id in [docs/icons.md](../../../docs/icons.md):
`<id>.png` (1024×1024, transparent background; convert SVG to PNG first), plus `<id>_small.png`
for the icons marked **small**. The files here now are simple placeholder sketches;
replacing a file with the final artwork is enough. Then run:

```sh
python3 tools/build_device_assets.py   # renders assets/device/*.png
python3 tools/gen_esphome_images.py    # only when assets/device_assets.json changed
```

Artwork in this public repository must be your own or freely redistributable.

Ikononként egy fájl, pontosan a [docs/icons.md](../../../docs/icons.md) szerinti néven. A mostani
fájlok egyszerű helyettesítő vázlatok; a végleges rajzzal elég lecserélni őket (a GitHub
weboldalán: *Add file → Upload files*), utána a fenti szkript elkészíti a knob méreteit.
