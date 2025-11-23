import google.generativeai as genai
import streamlit as st

from client.agent import GeminiAgent
from client.config import SYSTEM_INSTRUCTION, DEFAULT_SERVER_URL
from client.logger import log_user_prompt, ensure_log_dir

ensure_log_dir()

st.set_page_config(page_title="Blender Gemini Agent", layout="wide")
st.sidebar.title("⚙️ Configuration")
api_key = st.sidebar.text_input("Google API Key", type="password")
server_url = st.sidebar.text_input("Blender Server URL", value=DEFAULT_SERVER_URL)
model_name = st.sidebar.selectbox("Model Name", ["gemini-2.5-flash", "gemini-3-pro-preview", ])
max_turns = st.sidebar.slider("Max Retry Turns", min_value=1, max_value=10, value=5)

agent = GeminiAgent(server_url)
tools = [agent.run_blender_script, agent.get_viewport_screenshot]

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

                    response = agent.process_one_turn(
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
