# Cura Bridge

 An addon for Blender that allows you to select any model(s) and press a single button to load directly into Cura.

> [!Note]
> First time starting Cura may take some time
> 
> Tested for Blender version 4.2 - 4.4

---

How to install:

1. Install .zip file to PC from Releases

2. Open Blender -> goto Edit -> Preferences -> Top right Install from Disk

3. Choose downloaded cura-bridge-v#.zip

---

### Update V1.1 5/14/25

Now with cross-compatibility, including Flatpak support.

If using Flatpak, you will need to also install:

`flatpak-spawn`

and upgrade permissions for Blender

`flatpak override --user --talk-name=org.freedesktop.Flatpak org.blender.Blender`

---

### Update V1.1.1 5/15/25

Added a field for custom export path. Defaults to the Downloads folder.

> [!Note]
> Flatpak users need to provide additional permissions for custom folders outside Cura's environment. 
> 
> ex. `flatpak override --user --filesystem=/tmp com.ultimaker.cura`