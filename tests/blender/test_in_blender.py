import sys
import traceback
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

import BlenderGeminiAgent  # noqa: E402


def main() -> None:
    try:
        BlenderGeminiAgent.register()

        result = bpy.ops.myaddon.hello()
        print(f"bpy.ops.myaddon.hello() -> {result}")

        assert "FINISHED" in result
        print("Blender integration test: OK")
    except Exception:
        traceback.print_exc()
        sys.exit(1)
    finally:
        BlenderGeminiAgent.unregister()


if __name__ == "__main__":
    main()
