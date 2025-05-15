bl_info = {
    "name": "Cura Bridge",
    "author": "Synopsik",
    "version": (1, 1, 1),
    "blender": (4, 2, 0),
    "location": "View3D ▸ Sidebar ▸ Cura",
    "description": "Export selected mesh(es) to STL and open in UltiMaker Cura",
    "category": "3D View",
}

import bpy, os, platform, subprocess, shutil, time
from datetime import datetime

# -----------------------------------------------------------------------------#
#  Preferences                                                                 #
# -----------------------------------------------------------------------------#
class CuraBridgePreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    def _update_tab(self, ctx):
        bpy.utils.unregister_class(CURA_PT_panel)
        CURA_PT_panel.bl_category = self.tab_name
        bpy.utils.register_class(CURA_PT_panel)



    cura_path: bpy.props.StringProperty(
        name="Cura Executable",
        subtype='FILE_PATH',
        description="Locations:\n\n"
                    "Windows: C:\\Program Files\\UltiMaker Cura\\UltiMaker-Cura.exe\n"
                    "Linux: /usr/bin/cura or ~/.local/bin/cura\n"
                    "Flatpak: Leave blank\n"
                    "macOS: /Applications/UltiMaker Cura.app/Contents/MacOS/UltiMaker Cura",
        default=""
    )
    tab_name: bpy.props.StringProperty(
        name        = "N-Panel Tab Name",
        description = "Name of the N-Panel tab that hosts Cura Bridge",
        default     = "Cura",
        update      = _update_tab
    )
    export_dir: bpy.props.StringProperty(
        name        = "Export Directory",
        subtype     = 'DIR_PATH',
        description = "Directory where STLs are exported to",
        default     = ""
    )

    def draw(self, _):
        l = self.layout
        l.prop(self, "tab_name")
        l.prop(self, "cura_path")
        l.prop(self, "export_dir")

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
HOME                = os.path.expanduser("~")
DEFAULT_EXPORT_DIR  = os.path.join(HOME, "Downloads", "CuraBridge")

def _chosen_dir() -> str:
    prefs = bpy.context.preferences.addons[__name__].preferences
    if prefs.export_dir.strip():
        return os.path.abspath(os.path.expanduser(prefs.export_dir.strip()))
    return DEFAULT_EXPORT_DIR

def _wipe_export_dir(path: str) -> None:
    # Remove every file + the folder (ignore errors)
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)

def _ensure_export_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def _make_stl_path(obj) -> str:
    directory = _chosen_dir()
    _ensure_export_dir(directory)
    if bpy.data.filepath:
        base = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
        return os.path.join(directory, f"{base}.stl")
    safe = bpy.path.clean_name(obj.name)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(directory, f"{safe}_{ts}.stl")

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

        _wipe_export_dir(_chosen_dir())  # clean on export

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

def _apply_tab():
    try:
        prefs = bpy.context.preferences.addons[__name__].preferences
        bpy.utils.unregister_class(CURA_PT_panel)
        CURA_PT_panel.bl_category = prefs.tab_name
        print("[CuraBridge] _apply_tab(): applied", prefs.tab_name)
    except Exception as e:
        print("[CuraBridge] _apply_tab() error:", e)

    try:
        bpy.utils.register_class(CURA_PT_panel)
    except RuntimeError as e:
        print("[CuraBridge] _apply_tab(): register failed:", e)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.cura_export = bpy.props.PointerProperty(type=CuraExportProps)
    print("[CuraBridge] register(): calling _apply_tab()")
    _apply_tab()
    try:
        bpy.app.handlers.load_post.append(_apply_tab)
        print("[CuraBridge] register(): appended load_post handler")
    except Exception as e:
        print("[CuraBridge] register(): failed to append handler:", e)

    _wipe_export_dir(_chosen_dir()) # clean on start
    _ensure_export_dir(_chosen_dir())
    print("[CuraBridge] registered – export dir cleaned.")

def unregister():
    try:
        bpy.app.handlers.load_post.remove(_apply_tab)
        print("[CuraBridge] unregister(): removed load_post handler")
    except Exception as e:
        print("[CuraBridge] unregister(): failed to remove handler:", e)
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
    del bpy.types.Scene.cura_export

    _wipe_export_dir(_chosen_dir())
    print("[CuraBridge] unregistered – export dir cleaned.")

if __name__ == "__main__":
    register()