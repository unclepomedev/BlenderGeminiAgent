import base64
import io
import streamlit as st
import google.generativeai as genai
from PIL import Image

from client.config import SYSTEM_INSTRUCTION, DEFAULT_SERVER_URL
from client.logger import log_blender_interaction, log_user_prompt, ensure_log_dir
from client.blender_client import BlenderClient

ensure_log_dir()

st.set_page_config(page_title="Blender Gemini Agent", layout="wide")
st.sidebar.title("⚙️ Configuration")
api_key = st.sidebar.text_input("Google API Key", type="password")
server_url = st.sidebar.text_input("Blender Server URL", value=DEFAULT_SERVER_URL)
model_name = st.sidebar.selectbox("Model Name", ["gemini-2.5-flash", "gemini-3-pro-preview", ])
max_turns = st.sidebar.slider("Max Retry Turns", min_value=1, max_value=10, value=5)


def run_blender_script(code: str):
    """
    Sends Python code to the Blender server for execution.
    """
    clean_code = code.replace("```python", "").replace("```", "").strip()

    # Create client using the current server_url from sidebar
    client = BlenderClient(server_url)
    return client.execute_script(clean_code)


def get_viewport_screenshot():
    """
    Requests a rendered screenshot from the Blender server.
    """
    # Create client using the current server_url from sidebar
    client = BlenderClient(server_url)
    return client.get_screenshot()


tools = [run_blender_script, get_viewport_screenshot]

if "messages" not in st.session_state:
    st.session_state.messages = []  # Store chat history
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None


def _make_function_response_part(name: str, response_dict: dict):
    """Create a function_response part for Gemini.

    Args:
        name: Tool/function name to attach to the response.
        response_dict: JSON-serializable dictionary payload to return to the model.

    Returns:
        A dict content part for a function_response.
    """
    return {
        "function_response": {
            "name": name,
            "response": response_dict,
        }
    }


def handle_run_blender_script(fname: str, fargs: dict, *, chat_session):
    """Handle the `run_blender_script` tool invocation.

    This shows the generated Python code, sends it to the Blender server, reflects
    the execution result in the UI, and sends a function_response back to the model.

    Args:
        fname: Tool name as requested by the model.
        fargs: Tool arguments; expects a key "code" containing Python source.
        chat_session: Active GenerativeModel chat session used to send responses.

    Returns:
        The next model response returned by ``chat_session.send_message(...)``.
    """
    code_to_run = fargs["code"]
    with st.expander(f"View Python Code ({len(code_to_run)} chars)"):
        st.code(code_to_run, language="python")

    result = run_blender_script(code_to_run)

    log_blender_interaction(code_to_run, result)

    api_response = {"result": result}

    if result.get("status") == "error":
        st.error(f"Execution Error: {result.get('message')}")
    elif result.get("output"):
        st.success("Code Executed Successfully")

    part = _make_function_response_part(fname, api_response)
    return chat_session.send_message([part])


def handle_get_viewport_screenshot(fname: str, *, chat_session, turn_count: int):
    """Handle the `get_viewport_screenshot` tool invocation.

    This requests a viewport render from the Blender server, displays the image in
    the UI and stores it temporarily, then sends a function_response plus the
    captured image back to the model.

    Args:
        fname: Tool name as requested by the model.
        chat_session: Active GenerativeModel chat session used to send responses.
        turn_count: Current turn index used for UI captions.

    Returns:
        The next model response returned by ``chat_session.send_message(...)``.
    """
    result = get_viewport_screenshot()

    if result.get("status") == "success":
        img_data = base64.b64decode(result["image_base64"])
        image = Image.open(io.BytesIO(img_data))

        st.image(image, caption=f"Observation (Turn {turn_count})", width=400)

        if "temp_images" not in st.session_state:
            st.session_state.temp_images = []
        st.session_state.temp_images.append(image)

        function_response_part = _make_function_response_part(
            fname, {"result": "Image captured successfully. See attached."}
        )
        return chat_session.send_message([
            function_response_part,
            "Here is the current viewport render:",
            image,
        ])

    # Error path
    st.error(f"Vision Error: {result.get('message')}")
    error_part = _make_function_response_part(fname, {"error": result.get("message")})
    return chat_session.send_message([error_part])


def process_one_turn(response, *, chat_session, turn_count: int):
    """Process one turn of function_call handling and return the next response.

    Extracts any Thought text, dispatches each function_call to the appropriate
    handler, and returns the model's subsequent response.

    Args:
        response: The current model response that may include function calls.
        chat_session: Active GenerativeModel chat session used to send responses.
        turn_count: Current turn index (1-based) for UI labeling.

    Returns:
        The next model response produced after handling all function calls.
    """
    # Extract and render Thought text
    thought_text = "".join([part.text for part in response.parts if getattr(part, "text", None)])
    if thought_text:
        st.markdown(f"**Thought:** {thought_text}")

    # Extract function_call parts
    function_call_parts = [part for part in response.parts if getattr(part, "function_call", None)]

    next_response = response

    for part in function_call_parts:
        fc = part.function_call
        fname = fc.name
        fargs = fc.args

        st.write(f"🔧 **Calling Tool:** `{fname}`")

        if fname == "run_blender_script":
            next_response = handle_run_blender_script(fname, fargs, chat_session=chat_session)
        elif fname == "get_viewport_screenshot":
            next_response = handle_get_viewport_screenshot(
                fname, chat_session=chat_session, turn_count=turn_count
            )
        else:
            st.warning(f"Unknown tool: {fname}")
            # For unknown tools, return an error via function_response
            error_part = _make_function_response_part(fname, {"error": "Unknown tool"})
            next_response = chat_session.send_message(genai.protos.Content(parts=[error_part]))

    return next_response


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
                st.image(img, caption="Viewport Capture", width="stretch")
        if msg.get("logs"):
            with st.expander("See Execution Logs"):
                st.code(msg["logs"], language="text")

if prompt := st.chat_input("Ex: 'Clear the scene and create a red chair'"):
    if not st.session_state.chat_session:
        st.error("Model is not initialized.")
        st.stop()

    log_user_prompt(prompt)

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        current_response_text = ""
        turn_count = 0
        response = None

        with st.status("Agent is working...", expanded=True) as status:
            try:
                response = st.session_state.chat_session.send_message(prompt)

                while response.parts and any(part.function_call for part in response.parts):
                    turn_count += 1
                    if turn_count > max_turns:
                        st.error(f"Max turns ({max_turns}) reached. Stopping loop.")
                        break

                    response = process_one_turn(
                        response,
                        chat_session=st.session_state.chat_session,
                        turn_count=turn_count,
                    )

                status.update(label="Task Completed!", state="complete", expanded=False)

            except Exception as e:
                st.error(f"An error occurred: {e}")
                status.update(label="Error", state="error")

        if response:
            final_text = "".join([part.text for part in response.parts if part.text])
            st.markdown(final_text)

            msg_data = {"role": "assistant", "content": final_text}

            if "temp_images" in st.session_state and st.session_state.temp_images:
                msg_data["images"] = st.session_state.temp_images
                del st.session_state.temp_images

            st.session_state.messages.append(msg_data)
