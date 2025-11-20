# SPDX-License-Identifier: GPL-3.0-or-later

import bpy


# see also: https://docs.blender.org/api/current/bpy.types.AddonPreferences.html
class HwAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__  # "BlenderGeminiAgent"

    sample_text: bpy.props.StringProperty(
        name="Sample Text",
        default="Hello",
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "sample_text")


def register():
    bpy.utils.register_class(HwAddonPreferences)


def unregister():
    bpy.utils.unregister_class(HwAddonPreferences)
