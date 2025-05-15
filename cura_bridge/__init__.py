# ***** BEGIN GPL LICENSE BLOCK *****
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ***** END GPL LICENCE BLOCK *****

bl_info = {
    "name": "Cura Bridge",
    "author": "Synopsik",
    "version": (1, 1, 0),
    "blender": (4, 2, 0),
    "location": "View3D ▸ Sidebar ▸ Cura",
    "description": "Export selected mesh(es) to STL and open in UltiMaker Cura",
    "category": "3D View",
}

# -----------------------------------------------------------------------------#
#  Preferences                                                                 #
# -----------------------------------------------------------------------------#
import bpy, os, platform, subprocess, shutil, time
from datetime import datetime

class CuraBridgePreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    cura_path: bpy.props.StringProperty(
        name        = "Cura Executable",
        subtype     = 'FILE_PATH',
        description = "Optional path to Cura executable / AppImage / .exe. "
                      "Leave blank for auto-detect.",
        default     = ""
    )
    tab_name: bpy.props.StringProperty(
        name        = "Sidebar Tab Name",
        description = "Name of the Sidebar tab that hosts Cura Bridge panel.",
        default     = "3D Print"
    )

    def draw(self, _):
        l = self.layout
        l.prop(self, "tab_name")
        l.prop(self, "cura_path")

# -----------------------------------------------------------------------------#
#  Scene-level export settings                                                 #
# -----------------------------------------------------------------------------#
class CuraExportProps(bpy.types.PropertyGroup):
    scale: bpy.props.FloatProperty(
        name        = "Scale",
        description = "Global scale factor (1 = unchanged). "
                      "If you model in metres, set 1000 to convert to mm.",
        default     = 1.0, min = 0.001
    )
    ascii_format: bpy.props.BoolProperty(
        name        = "ASCII STL",
        description = "Export ASCII (larger) instead of binary (smaller).",
        default     = False
    )
    apply_modifiers: bpy.props.BoolProperty(
        name        = "Apply Modifiers",
        description = "Apply all object modifiers before export (Boolean, Mirror, etc.).",
        default     = True
    )
    use_scene_unit: bpy.props.BoolProperty(
        name        = "Use Scene Units",
        description = "Apply scene unit scaling (cm / mm).",
        default     = True
    )
    axis_forward: bpy.props.EnumProperty(
        name        = "Forward Axis",
        description = "Forward axis in exported coordinates.",
        items = [('X','+X',''), ('Y','+Y',''), ('Z','+Z',''),
                 ('NEGATIVE_X','-X',''), ('NEGATIVE_Y','-Y',''), ('NEGATIVE_Z','-Z','')],
        default = 'Y'
    )
    axis_up: bpy.props.EnumProperty(
        name        = "Up Axis",
        description = "Up axis in exported coordinates.",
        items = [('X','+X',''), ('Y','+Y',''), ('Z','+Z',''),
                 ('NEGATIVE_X','-X',''), ('NEGATIVE_Y','-Y',''), ('NEGATIVE_Z','-Z','')],
        default = 'Z'
    )

# -----------------------------------------------------------------------------#
#  Export directory utilities                                                  #
# -----------------------------------------------------------------------------#
HOME        = os.path.expanduser("~")
EXPORT_DIR  = os.path.join(HOME, "Downloads", "CuraBridge")

def _wipe_export_dir() -> None:
    # Remove every file + the folder (ignore errors)
    if os.path.isdir(EXPORT_DIR):
        for f in os.listdir(EXPORT_DIR):
            try:
                os.remove(os.path.join(EXPORT_DIR, f))
            except OSError:
                pass
        try:
            os.rmdir(EXPORT_DIR)
        except OSError:
            pass

def _ensure_export_dir() -> None:
    os.makedirs(EXPORT_DIR, exist_ok=True)

def _make_stl_path(obj) -> str:
    _ensure_export_dir()
    if bpy.data.filepath:
        base = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
        return os.path.join(EXPORT_DIR, f"{base}.stl")
    safe = bpy.path.clean_name(obj.name)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(EXPORT_DIR, f"{safe}_{ts}.stl")

# -----------------------------------------------------------------------------#
#  Operator – export & launch Cura                                             #
# -----------------------------------------------------------------------------#
class CURA_OT_send(bpy.types.Operator):
    bl_idname      = "cura.send"
    bl_label       = "Send to Cura"
    bl_description = ("Export selected mesh(es) as STL to ~/Downloads/CuraBridge "
                      "and open in Cura.  Export folder is cleaned on Blender "
                      "start / exit.")

    @staticmethod
    def _launch(cmd:list) -> bool:
        print("[CuraBridge]", " ".join(cmd))
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(1)
            if p.poll() is not None:  # If exited early, return as False
                out, err = p.communicate()
                print(out.decode()); print(err.decode())
                return False
            return True
        except Exception as e:
            print("[CuraBridge] launch error:", e)
            return False

    def execute(self, ctx):
        _wipe_export_dir()  # clean on export

        if not any(o.type == 'MESH' for o in ctx.selected_objects):
            self.report({'ERROR'}, "Select a mesh object to export.")
            return {'CANCELLED'}

        props   = ctx.scene.cura_export
        stlpath = _make_stl_path(ctx.active_object)
        print(f"[CuraBridge] Export -> {stlpath}")

        try:
            bpy.ops.wm.stl_export(
                filepath                = stlpath,
                ascii_format            = props.ascii_format,
                export_selected_objects = True,
                use_batch               = False,
                global_scale            = props.scale,
                apply_modifiers         = props.apply_modifiers,
                use_scene_unit          = props.use_scene_unit,
                forward_axis            = props.axis_forward,
                up_axis                 = props.axis_up,
                check_existing          = False)
        except Exception as e:
            self.report({'ERROR'}, f"STL export failed: {e}")
            return {'CANCELLED'}

        prefs = ctx.preferences.addons[__name__].preferences
        launched = False

        if prefs.cura_path and os.path.isfile(prefs.cura_path):
            launched = self._launch([prefs.cura_path, stlpath])

        if not launched and os.environ.get("FLATPAK_ID") and shutil.which("flatpak-spawn"):
            launched = self._launch(["flatpak-spawn", "--host", f"--directory={HOME}",
                                     "flatpak", "run", "com.ultimaker.cura", stlpath])

        if not launched and platform.system() == "Linux":
            if shutil.which("cura"):
                launched = self._launch(["cura", stlpath])
            elif shutil.which("flatpak"):
                launched = self._launch(["flatpak", "run", "com.ultimaker.cura", stlpath])

        if not launched and platform.system() == "Windows":
            try: os.startfile(stlpath); launched = True
            except OSError: pass

        if not launched and platform.system() == "Darwin":
            launched = self._launch(["open", "-a", "Ultimaker Cura", stlpath])

        if not launched:
            self.report({'ERROR'}, "Could not launch Cura – see console.")
            return {'CANCELLED'}

        self.report({'INFO'}, "Cura launched; STL sent.")
        return {'FINISHED'}

# -----------------------------------------------------------------------------#
#  Panel – UI                                                                  #
# -----------------------------------------------------------------------------#
class CURA_PT_panel(bpy.types.Panel):
    bl_idname      = "CURA_PT_panel"
    bl_label       = "Cura Bridge"
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category    = 'Cura'

    def draw(self, ctx):
        prefs = ctx.preferences.addons[__name__].preferences
        if self.bl_category != prefs.tab_name:
            self.bl_category = prefs.tab_name

        layout = self.layout
        p = ctx.scene.cura_export
        for prop in ("scale", "ascii_format", "apply_modifiers",
                     "use_scene_unit", "axis_forward", "axis_up"):
            layout.prop(p, prop)
        layout.operator(CURA_OT_send.bl_idname, icon='EXPORT')

# -----------------------------------------------------------------------------#
#  Register / Unregister                                                       #
# -----------------------------------------------------------------------------#
classes = (CuraBridgePreferences, CuraExportProps,
           CURA_OT_send, CURA_PT_panel)

def register():
    _wipe_export_dir() # clean on start
    _ensure_export_dir()
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.cura_export = bpy.props.PointerProperty(type=CuraExportProps)
    prefs = bpy.context.preferences.addons.get(__name__)
    if prefs:
        CURA_PT_panel.bl_category = prefs.preferences.tab_name
    print("[CuraBridge] registered v1.5.0 – export dir cleaned.")

def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
    del bpy.types.Scene.cura_export
    _wipe_export_dir()
    print("[CuraBridge] unregistered – export dir cleaned.")

if __name__ == "__main__":
    register()
