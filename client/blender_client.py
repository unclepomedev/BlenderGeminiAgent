import requests


class BlenderClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')

    def execute_script(self, code: str) -> dict:
        """
        Sends Python code to the Blender server for execution.
        """
        try:
            response = requests.post(f"{self.base_url}/run", json={"code": code})
            if response.status_code == 200:
                return response.json()  # Expecting {"status": "success", "output": ...}
            elif response.status_code == 504:
                return {"status": "error", "message": "Timeout: Blender took too long to execute."}
            else:
                return {"status": "error", "message": f"HTTP {response.status_code}: {response.text}"}
        except requests.exceptions.ConnectionError:
            return {"status": "error", "message": "Connection refused. Is the Blender server running?"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_screenshot(self) -> dict:
        """
        Requests a rendered screenshot from the Blender server.
        """
        try:
            response = requests.post(f"{self.base_url}/view", json={})
            if response.status_code == 200:
                return response.json()  # Expecting {"status": "success", "image_base64": ...}
            elif response.status_code == 504:
                return {"status": "error", "message": "Timeout: Rendering took too long."}
            else:
                return {"status": "error", "message": f"HTTP {response.status_code}: {response.text}"}
        except requests.exceptions.ConnectionError:
            return {"status": "error", "message": "Connection refused. Is the Blender server running?"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
