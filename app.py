import base64
import io

import google.generativeai as genai
import requests
import streamlit as st
from PIL import Image

st.set_page_config(page_title="Blender Gemini Agent", layout="wide")
st.sidebar.title("⚙️ Configuration")
api_key = st.sidebar.text_input("Google API Key", type="password")
server_url = st.sidebar.text_input("Blender Server URL", value="http://127.0.0.1:8081")
model_name = st.sidebar.selectbox("Model Name", ["gemini-2.5-flash", "gemini-3-pro-preview", ])
max_turns = st.sidebar.slider("Max Retry Turns", min_value=1, max_value=10, value=5)


def run_blender_script(code: str):
    """
    Sends Python code to the Blender server for execution.
    """
    clean_code = code.replace("```python", "").replace("```", "").strip()

    try:
        response = requests.post(f"{server_url}/run", json={"code": clean_code})
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


def get_viewport_screenshot():
    """
    Requests a rendered screenshot from the Blender server.
    """
    try:
        response = requests.post(f"{server_url}/view", json={})
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


SYSTEM_INSTRUCTION = """
You are an expert Blender Python scripter agent.
Your goal is to autonomously modify the Blender scene to meet the user's requirements.

### CRITICAL RULES:
1. **Context Safety**: Blender operators (`bpy.ops`) often fail if the context is incorrect. If you encounter a "Poll failed" error, act autonomously:
   - Use `bpy.data` manipulations instead of operators where possible.
   - Or rely on the `get_view3d_context()` helper which is available in the environment.
2. **Visualization**: When `get_viewport_screenshot` is called, YOU MUST ENSURE:
   - A **Camera** exists and is active (`bpy.context.scene.camera`).
   - **Lights** are placed so objects are visible (otherwise the image will be black).
3. **Iterative Correction**: If the screenshot does not match the user's request (e.g., wrong color, empty scene), modify the code and retry.

### PROCESS:
1. **Plan**: Decide what to do.
2. **Act**: Execute code via `run_blender_script`. Check the stdout/stderr logs returned.
3. **Observe**: Capture an image via `get_viewport_screenshot`.
4. **Refine**: Iterate until satisfied.
"""

tools = [run_blender_script, get_viewport_screenshot]

if "messages" not in st.session_state:
    st.session_state.messages = []  # Store chat history
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None

st.title("🤖 Blender Gemini Agent")
st.caption("Autonomous 3D Modeling Agent powered by Gemini 3")

if api_key:
    try:
        genai.configure(api_key=api_key)
        if st.session_state.chat_session is None:
            model = genai.GenerativeModel(
                model_name=model_name,
                tools=tools,
                system_instruction=SYSTEM_INSTRUCTION
            )
            st.session_state.chat_session = model.start_chat(enable_automatic_function_calling=False)
            st.success("System Ready: Model initialized.")
    except Exception as e:
        st.error(f"Failed to initialize model: {e}")
else:
    st.warning("Please enter your Google API Key in the sidebar to start.")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg.get("content"):
            st.markdown(msg["content"])
        if msg.get("images"):
            for img in msg["images"]:
                st.image(img, caption="Viewport Capture", use_column_width=True)
        if msg.get("logs"):
            with st.expander("See Execution Logs"):
                st.code(msg["logs"], language="text")

if prompt := st.chat_input("Ex: 'Clear the scene and create a red chair'"):
    if not st.session_state.chat_session:
        st.error("Model is not initialized.")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        current_response_text = ""
        turn_count = 0

        with st.status("Agent is working...", expanded=True) as status:
            try:
                response = st.session_state.chat_session.send_message(prompt)

                while response.parts and any(part.function_call for part in response.parts):
                    turn_count += 1
                    if turn_count > max_turns:
                        st.error(f"Max turns ({max_turns}) reached. Stopping loop.")
                        break

                    thought_text = "".join([part.text for part in response.parts if part.text])
                    if thought_text:
                        st.markdown(f"**Thought:** {thought_text}")
                        current_response_text += f"\n\n**Thought:** {thought_text}"

                    function_call_parts = [part for part in response.parts if part.function_call]

                    for part in function_call_parts:
                        fc = part.function_call
                        fname = fc.name
                        fargs = fc.args

                        st.write(f"🔧 **Calling Tool:** `{fname}`")

                        api_response = {}

                        if fname == "run_blender_script":
                            code_to_run = fargs["code"]
                            with st.expander(f"View Python Code ({len(code_to_run)} chars)"):
                                st.code(code_to_run, language="python")

                            result = run_blender_script(code_to_run)
                            api_response = {"result": result}

                            if result.get("status") == "error":
                                st.error(f"Execution Error: {result.get('message')}")
                            elif result.get("output"):
                                st.success("Code Executed Successfully")

                            response = st.session_state.chat_session.send_message(
                                genai.protos.Content(
                                    parts=[genai.protos.Part(
                                        function_response=genai.protos.FunctionResponse(
                                            name=fname,
                                            response=api_response
                                        )
                                    )]
                                )
                            )

                        elif fname == "get_viewport_screenshot":
                            result = get_viewport_screenshot()

                            if result.get("status") == "success":
                                img_data = base64.b64decode(result["image_base64"])
                                image = Image.open(io.BytesIO(img_data))

                                st.image(image, caption=f"Observation (Turn {turn_count})", width=400)

                                if "temp_images" not in st.session_state:
                                    st.session_state.temp_images = []
                                st.session_state.temp_images.append(image)

                                function_response_part = genai.protos.Part(
                                    function_response=genai.protos.FunctionResponse(
                                        name=fname,
                                        response={"result": "Image captured successfully. See attached."}
                                    )
                                )
                                response = st.session_state.chat_session.send_message([
                                    function_response_part,
                                    "Here is the current viewport render:",
                                    image
                                ])
                            else:
                                st.error(f"Vision Error: {result.get('message')}")
                                error_part = genai.protos.Part(
                                    function_response=genai.protos.FunctionResponse(
                                        name=fname,
                                        response={"error": result.get('message')}
                                    )
                                )
                                response = st.session_state.chat_session.send_message(
                                    genai.protos.Content(parts=[error_part])
                                )

                status.update(label="Task Completed!", state="complete", expanded=False)

            except Exception as e:
                st.error(f"An error occurred: {e}")
                status.update(label="Error", state="error")

        final_text = "".join([part.text for part in response.parts if part.text])
        st.markdown(final_text)

        msg_data = {"role": "assistant", "content": final_text}

        if "temp_images" in st.session_state and st.session_state.temp_images:
            msg_data["images"] = st.session_state.temp_images
            del st.session_state.temp_images

        st.session_state.messages.append(msg_data)
