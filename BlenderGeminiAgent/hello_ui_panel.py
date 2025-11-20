# SPDX-License-Identifier: GPL-3.0-or-later

import bpy


class HelloPanel(bpy.types.Panel):
    bl_label = "Hello World"
    bl_idname = "myaddon.hello_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "hello"

    def draw(self, context):
        layout = self.layout
        layout.operator("myaddon.hello", icon="INFO")


def register():
    bpy.utils.register_class(HelloPanel)


def unregister():
    bpy.utils.unregister_class(HelloPanel)
