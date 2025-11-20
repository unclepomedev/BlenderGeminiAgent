import requests
import base64

URL = "http://localhost:8081"

print("Sending code execution request...")
create_cube_code = """
import bpy
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 2))
bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(3, 0, 2))
"""

res = requests.post(f"{URL}/run", json={"code": create_cube_code})
print("Run response:", res.json())

print("Requesting viewport screenshot...")
res_img = requests.post(f"{URL}/view", json={})
data = res_img.json()

if data.get("status") == "success":
    print("Image received!")
    img_data = base64.b64decode(data["image_base64"])
    with open("result_from_blender.png", "wb") as f:
        f.write(img_data)
    print("Saved as result_from_blender.png")
else:
    print("Image error:", data)
