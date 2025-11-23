# SPDX-License-Identifier: GPL-3.0-or-later

import base64
import io
import os
import queue
import sys
import tempfile
import traceback

import bpy

execution_queue = queue.Queue()


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
