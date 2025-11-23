import datetime
import os

from .config import LOG_DIR


def ensure_log_dir():
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)


def log_blender_interaction(code: str, result: dict):
    """Logs the code and the result to a file."""
    now = datetime.datetime.now()
    date_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M:%S')
    log_file = os.path.join(LOG_DIR, f"log_{date_str}.txt")

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{time_str}] Interaction\n")
            f.write("-" * 20 + " REQUEST (PYTHON) " + "-" * 20 + "\n")
            f.write(code + "\n")
            f.write("-" * 20 + " RESPONSE " + "-" * 20 + "\n")

            status = result.get("status", "unknown")
            f.write(f"Status: {status}\n")

            if status == "error":
                f.write(f"Message: {result.get('message', '')}\n")
            else:
                # Output might be large, maybe truncate if needed, but for now full log is safer for debugging
                f.write(f"Output: {result.get('output', '')}\n")

            f.write("=" * 50 + "\n\n")
    except Exception as e:
        print(f"Failed to write log: {e}")


def log_user_prompt(prompt: str):
    """Logs the user prompt to a file."""
    now = datetime.datetime.now()
    date_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M:%S')
    log_file = os.path.join(LOG_DIR, f"log_{date_str}.txt")

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{time_str}] USER PROMPT\n")
            f.write("-" * 20 + " PROMPT " + "-" * 20 + "\n")
            f.write(prompt + "\n")
            f.write("=" * 50 + "\n\n")
    except Exception as e:
        print(f"Failed to write log: {e}")
