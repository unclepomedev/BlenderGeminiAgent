import base64
import io

import google.generativeai as genai
import streamlit as st
from PIL import Image

from client.blender_client import BlenderClient
from client.logger import log_blender_interaction


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


class GeminiAgent:
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.blender_client = BlenderClient(server_url)

    def run_blender_script(self, code: str):
        """
        Sends Python code to the Blender server for execution.
        """
        clean_code = code.replace("```python", "").replace("```", "").strip()
        return self.blender_client.execute_script(clean_code)

    def get_viewport_screenshot(self):
        """
        Requests a rendered screenshot from the Blender server.
        """
        return self.blender_client.get_screenshot()

    def handle_run_blender_script(self, fname: str, fargs: dict, *, chat_session):
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

        result = self.run_blender_script(code_to_run)
        log_blender_interaction(code_to_run, result)
        api_response = {"result": result}

        if result.get("status") == "error":
            st.error(f"Execution Error: {result.get('message')}")
        elif result.get("output"):
            st.success("Code Executed Successfully")

        part = _make_function_response_part(fname, api_response)
        return chat_session.send_message([part])

    def handle_get_viewport_screenshot(self, fname: str, *, chat_session, turn_count: int):
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
        result = self.get_viewport_screenshot()

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

    def process_one_turn(self, response, *, chat_session, turn_count: int):
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
                next_response = self.handle_run_blender_script(fname, fargs, chat_session=chat_session)
            elif fname == "get_viewport_screenshot":
                next_response = self.handle_get_viewport_screenshot(
                    fname, chat_session=chat_session, turn_count=turn_count
                )
            else:
                st.warning(f"Unknown tool: {fname}")
                # For unknown tools, return an error via function_response
                error_part = _make_function_response_part(fname, {"error": "Unknown tool"})
                next_response = chat_session.send_message(genai.protos.Content(parts=[error_part]))

        return next_response
