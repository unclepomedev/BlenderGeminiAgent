# SPDX-License-Identifier: GPL-3.0-or-later

import base64
import http.server
import io
import json
import os
import queue
import socketserver
import sys
import tempfile
import threading
import traceback

import bpy

PORT = 8081
execution_queue = queue.Queue()
server_thread = None
httpd = None


def get_view3d_context():
    for window in bpy.context.window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        with bpy.context.temp_override(window=window, area=area, region=region):
                            ctx = bpy.context.copy()
                            ctx['window'] = window
                            ctx['screen'] = screen
                            ctx['area'] = area
                            ctx['region'] = region
                            ctx['workspace'] = window.workspace
                            return ctx
    return None


class AgentRequestHandler(http.server.BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)

            res_q = queue.Queue()

            if self.path == '/run':
                code = data.get('code', '')
                execution_queue.put({"type": "code", "content": code, "response_queue": res_q})

                try:
                    result = res_q.get(timeout=30)
                    status_code = 200 if result['status'] == 'success' else 500
                    self._send_json(status_code, result)
                except queue.Empty:
                    self._send_json(504, {"status": "error", "message": "Code execution timed out"})

            elif self.path == '/view':
                execution_queue.put({"type": "view", "response_queue": res_q})

                try:
                    result = res_q.get(timeout=30)
                    self._send_json(200, result)
                except queue.Empty:
                    self._send_json(504, {"status": "error", "message": "Render timed out"})

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
            stdout_capture = io.StringIO()
            stderr_capture = io.StringIO()
            original_stdout = sys.stdout
            original_stderr = sys.stderr

            sys.stdout = stdout_capture
            sys.stderr = stderr_capture

            try:
                exec_globals = globals().copy()
                exec_globals['get_view3d_context'] = get_view3d_context

                exec(task['content'], exec_globals)

                output = stdout_capture.getvalue()
                task['response_queue'].put({"status": "success", "output": output})

                sys.__stdout__.write(output)
                print("Executed AI code successfully.")

            except Exception as e:
                error_msg = traceback.format_exc()
                task['response_queue'].put({"status": "error", "message": error_msg})
                print(f"Execution Error: {e}")

            finally:
                sys.stdout = original_stdout
                sys.stderr = original_stderr

        elif task['type'] == 'view':
            try:
                base_path = os.path.join(tempfile.gettempdir(), "agent_view")
                expected_path = base_path + ".png"

                if os.path.exists(expected_path):
                    os.remove(expected_path)

                if not bpy.context.scene.camera:
                    task['response_queue'].put(
                        {"status": "error", "message": "No camera found. Please create a camera."})
                    continue

                bpy.context.scene.render.image_settings.file_format = 'PNG'
                bpy.context.scene.render.filepath = base_path

                if hasattr(bpy.types, "RenderSettings") and 'BLENDER_EEVEE_NEXT' in \
                        bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items:
                    bpy.context.scene.render.engine = 'BLENDER_EEVEE_NEXT'
                else:
                    bpy.context.scene.render.engine = 'BLENDER_EEVEE'

                bpy.ops.render.render(write_still=True)

                if os.path.exists(expected_path):
                    with open(expected_path, "rb") as img_file:
                        b64_string = base64.b64encode(img_file.read()).decode('utf-8')
                    task['response_queue'].put({"status": "success", "image_base64": b64_string})
                else:
                    task['response_queue'].put({"status": "error", "message": "Render finished but file not found."})

            except Exception as e:
                task['response_queue'].put({"status": "error", "message": str(e)})

    return 0.1


def start_server_thread():
    global httpd, server_thread
    if httpd: return
    Handler = AgentRequestHandler
    socketserver.TCPServer.allow_reuse_address = True
    try:
        httpd = socketserver.TCPServer(("", PORT), Handler)
        print(f"Serving on port {PORT}")
        httpd.serve_forever()
    except OSError as e:
        print(f"Port {PORT} is already in use.")
        httpd = None


class OBJECT_OT_StartServer(bpy.types.Operator):
    bl_idname = "system.start_agent_server"
    bl_label = "Start Agent Server"

    def execute(self, context):
        global server_thread
        if server_thread and server_thread.is_alive(): return {'CANCELLED'}
        server_thread = threading.Thread(target=start_server_thread, daemon=True)
        server_thread.start()
        if not bpy.app.timers.is_registered(process_queue):
            bpy.app.timers.register(process_queue)
        self.report({'INFO'}, f"Server started on port {PORT}")
        return {'FINISHED'}


class OBJECT_OT_StopServer(bpy.types.Operator):
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
