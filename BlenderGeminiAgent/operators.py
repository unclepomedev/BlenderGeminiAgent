# SPDX-License-Identifier: GPL-3.0-or-later

import bpy

from .engine import process_queue
from .server import start_server, stop_server, PORT


class OBJECT_OT_StartServer(bpy.types.Operator):
    bl_idname = "system.start_agent_server"
    bl_label = "Start Agent Server"

    def execute(self, _):
        start_server()
        if not bpy.app.timers.is_registered(process_queue):
            bpy.app.timers.register(process_queue)
        self.report({'INFO'}, f"Server started on port {PORT}")
        return {'FINISHED'}


class OBJECT_OT_StopServer(bpy.types.Operator):
    bl_idname = "system.stop_agent_server"
    bl_label = "Stop Agent Server"

    def execute(self, _):
        stop_server()
        if bpy.app.timers.is_registered(process_queue):
            bpy.app.timers.unregister(process_queue)
        self.report({'INFO'}, "Server stopped")
        return {'FINISHED'}


classes = (
    OBJECT_OT_StartServer,
    OBJECT_OT_StopServer,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
