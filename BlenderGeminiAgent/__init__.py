# SPDX-License-Identifier: GPL-3.0-or-later

import base64
import http.server
import json
import os
import queue
import socketserver
import tempfile
import threading

import bpy

PORT = 8081
execution_queue = queue.Queue()
server_thread = None
httpd = None


class AgentRequestHandler(http.server.BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)

            if self.path == '/run':
                code = data.get('code', '')
                execution_queue.put({"type": "code", "content": code})

                response = {"status": "accepted", "message": "Code queued for execution"}
                self._send_json(200, response)

            elif self.path == '/view':
                res_q = queue.Queue()
                execution_queue.put({"type": "view", "response_queue": res_q})

                try:
                    result = res_q.get(timeout=5)
                    self._send_json(200, result)
                except queue.Empty:
                    self._send_json(504, {"status": "error", "message": "Timeout waiting for Blender"})

            else:
                self._send_json(404, {"status": "error", "message": "Not found"})

        except Exception as e:
            print(f"Server Error: {e}")
            self._send_json(500, {"status": "error", "message": str(e)})

    def _send_json(self, code, data):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())


def process_queue():
    while not execution_queue.empty():
        task = execution_queue.get()

        if task['type'] == 'code':
            try:
                exec(task['content'], globals())
                print("Executed AI code.")
            except Exception as e:
                print(f"Execution Error: {e}")

        elif task['type'] == 'view':
            try:
                tmp_path = os.path.join(tempfile.gettempdir(), "agent_view.png")

                if bpy.context.scene:
                    bpy.context.scene.render.filepath = tmp_path
                    bpy.ops.render.opengl(write_still=True, view_context=True)

                if os.path.exists(tmp_path):
                    with open(tmp_path, "rb") as img_file:
                        b64_string = base64.b64encode(img_file.read()).decode('utf-8')

                    task['response_queue'].put({"status": "success", "image_base64": b64_string})
                else:
                    task['response_queue'].put({"status": "error", "message": "Image capture failed"})

            except Exception as e:
                task['response_queue'].put({"status": "error", "message": str(e)})

    return 0.1


def start_server_thread():
    global httpd, server_thread
    if httpd:
        return

    Handler = AgentRequestHandler
    socketserver.TCPServer.allow_reuse_address = True
    try:
        httpd = socketserver.TCPServer(("", PORT), Handler)
        print(f"Serving on port {PORT}")
        httpd.serve_forever()
    except OSError as e:
        print(f"Port {PORT} is already in use. Server not started.")
        httpd = None


class OBJECT_OT_StartServer(bpy.types.Operator):
    """Start the AI Agent Server"""
    bl_idname = "system.start_agent_server"
    bl_label = "Start Agent Server"

    def execute(self, context):
        global server_thread
        if server_thread and server_thread.is_alive():
            self.report({'WARNING'}, "Server is already running")
            return {'CANCELLED'}

        server_thread = threading.Thread(target=start_server_thread, daemon=True)
        server_thread.start()

        if not bpy.app.timers.is_registered(process_queue):
            bpy.app.timers.register(process_queue)

        self.report({'INFO'}, f"Server started on port {PORT}")
        return {'FINISHED'}


class OBJECT_OT_StopServer(bpy.types.Operator):
    """Stop the AI Agent Server"""
    bl_idname = "system.stop_agent_server"
    bl_label = "Stop Agent Server"

    def execute(self, context):
        global httpd
        if httpd:
            httpd.shutdown()
            httpd.server_close()
            httpd = None
            if bpy.app.timers.is_registered(process_queue):
                bpy.app.timers.unregister(process_queue)
            self.report({'INFO'}, "Server stopped")
        else:
            self.report({'WARNING'}, "Server is not running")
        return {'FINISHED'}


def register():
    bpy.utils.register_class(OBJECT_OT_StartServer)
    bpy.utils.register_class(OBJECT_OT_StopServer)


def unregister():
    bpy.utils.unregister_class(OBJECT_OT_StartServer)
    bpy.utils.unregister_class(OBJECT_OT_StopServer)

    global httpd
    if httpd:
        httpd.shutdown()
        httpd.server_close()
