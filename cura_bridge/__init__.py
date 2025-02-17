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
    "version": (1, 0),
    "blender": (4, 2, 0),
    "location": "3D View > Sidebar > 3D Print",
    "description": "Export selected object to STL at a chosen scale and open it in Cura",
    "category": "3D Printing",
}

import bpy
import os
import subprocess
import tempfile

# -------------------------------------------------------------------
#   Addon Preferences to store the Cura executable path
# -------------------------------------------------------------------
class CuraBridgePreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    cura_path: bpy.props.StringProperty(
        name="Cura Executable Path",
        description="Path to the Cura executable",
        subtype='FILE_PATH',
        default="",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "cura_path")


# -------------------------------------------------------------------
#   Scene property for export scale percentage
# -------------------------------------------------------------------
def update_scale_percentage(self, context):
    pass  # Callback if needed

bpy.types.Scene.cura_export_scale = bpy.props.FloatProperty(
    name="Scale (%)",
    description="Scale factor for STL export, in percent",
    default=100.0,
    min=0.01,
    max=100000.0,
    update=update_scale_percentage
)


# -------------------------------------------------------------------
#   Operator to export STL and launch Cura
# -------------------------------------------------------------------
class OBJECT_OT_send_to_cura(bpy.types.Operator):
    bl_idname = "object.send_to_cura"
    bl_label = "Send to Cura"
    bl_description = "Export selected object as STL at a chosen scale and load it in Cura"

    def execute(self, context):
        obj = context.active_object
        if not obj:
            self.report({'ERROR'}, "No active object selected")
            return {'CANCELLED'}

        # Create a temporary STL file path.
        temp_dir = tempfile.gettempdir()
        stl_filepath = os.path.join(temp_dir, "temp_model.stl")

        # Convert percentage to a scale factor (e.g., 100% → 1.0).
        scale_val = context.scene.cura_export_scale / 100.0

        # Export selected objects using the new C++ STL exporter.
        # (See https://docs.blender.org/api/current/bpy.ops.wm.html#bpy.ops.wm.stl_export)
        try:
            bpy.ops.wm.stl_export(
                filepath=stl_filepath,
                check_existing=False,
                ascii_format=False,
                use_batch=False,
                export_selected_objects=True,
                global_scale=scale_val,
                use_scene_unit=False,
                forward_axis='Y',
                up_axis='Z',
                apply_modifiers=True,
                filter_glob="*.stl"
            )
        except Exception as e:
            self.report({'ERROR'}, f"STL export failed: {e}")
            return {'CANCELLED'}

        # Retrieve the Cura executable path from addon preferences.
        addon_prefs = context.preferences.addons[__name__].preferences
        cura_executable = addon_prefs.cura_path

        if not cura_executable or not os.path.exists(cura_executable):
            self.report({'ERROR'}, "Cura executable not found. Please set the path in the addon preferences.")
            return {'CANCELLED'}

        # Launch Cura with the exported STL.
        try:
            subprocess.Popen([cura_executable, stl_filepath])
        except Exception as e:
            self.report({'ERROR'}, "Failed to launch Cura: " + str(e))
            return {'CANCELLED'}

        self.report({'INFO'}, "Model sent to Cura")
        return {'FINISHED'}


# -------------------------------------------------------------------
#   Panel in the 3D View sidebar
# -------------------------------------------------------------------
class VIEW3D_PT_cura_bridge_panel(bpy.types.Panel):
    bl_label = "Cura Bridge"
    bl_idname = "VIEW3D_PT_cura_bridge_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = '3D Print'

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        row = layout.row(align=True)
        row.prop(scene, "cura_export_scale", text="Scale (%)")
        row.operator("object.send_to_cura", icon='EXPORT')


# -------------------------------------------------------------------
#   Registration
# -------------------------------------------------------------------
classes = (
    CuraBridgePreferences,
    OBJECT_OT_send_to_cura,
    VIEW3D_PT_cura_bridge_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    if hasattr(bpy.types.Scene, "cura_export_scale"):
        del bpy.types.Scene.cura_export_scale

if __name__ == "__main__":
    register()
