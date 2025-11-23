# SPDX-License-Identifier: GPL-3.0-or-later

import http.server
import json
import queue
import socketserver
import threading

from .engine import execution_queue

PORT = 8081
server_thread = None
httpd = None


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


def start_server():
    global httpd, server_thread
    if httpd: return
    Handler = AgentRequestHandler
    socketserver.TCPServer.allow_reuse_address = True
    try:
        httpd = socketserver.TCPServer(("", PORT), Handler)  # type: ignore[arg-type]
        print(f"Serving on port {PORT}")
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()
    except OSError as e:
        print(f"Port {PORT} is already in use.")
        httpd = None


def stop_server():
    global httpd, server_thread
    if httpd:
        httpd.shutdown()
        httpd.server_close()
        httpd = None
        server_thread = None
