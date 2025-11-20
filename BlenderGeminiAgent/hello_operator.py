# SPDX-License-Identifier: GPL-3.0-or-later

import bpy


class HelloOperator(bpy.types.Operator):
    bl_idname = "myaddon.hello"
    bl_label = "Say Hello"
    bl_description = "hello world message"

    def execute(self, context):
        self.report({"INFO"}, "hello from BlenderGeminiAgent")
        return {"FINISHED"}


def register():
    bpy.utils.register_class(HelloOperator)


def unregister():
    bpy.utils.unregister_class(HelloOperator)
