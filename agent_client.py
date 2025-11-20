import json
import time

import google.generativeai as genai
import requests

# ==========================================
# 設定 (ここを書き換えてください)
# ==========================================
GOOGLE_API_KEY = ""  # TODO
BLENDER_SERVER_URL = "http://127.0.0.1:8081"
MODEL_NAME = "gemini-3-pro-preview"  # "gemini-2.5-flash"
MAX_LOOP_COUNT = 5
# ==========================================

genai.configure(api_key=GOOGLE_API_KEY)


def run_blender_script(code: str):
    """
    Blender内でPythonコードを実行します。
    Args:
        code: 実行したいbpyを使用したPythonスクリプト。Markdownタグは不要。
    Returns:
        実行結果のステータスまたはエラーメッセージ。
    """
    # Markdownのコードブロック記号を削除する安全策
    clean_code = code.replace("```python", "").replace("```", "").strip()

    print(f"\n[Client] Sending code to Blender... ({len(clean_code)} chars)")
    try:
        response = requests.post(f"{BLENDER_SERVER_URL}/run", json={"code": clean_code})
        # サーバーは "accepted" を返すが、実際の実行は非同期。
        # 簡易的に少し待つ（本来はCallbackが理想だが今回はPollingしない）
        time.sleep(1.0)
        return json.dumps(response.json())
    except Exception as e:
        return f"Error sending code: {e}"


def get_viewport_screenshot():
    """
    現在のBlenderの3Dビューポートのスクリーンショットを取得します。
    視覚的な確認が必要な場合に使用します。
    Returns:
        画像のBase64文字列が含まれるJSON、またはエラーステータス。
    """
    print("\n[Client] Requesting screenshot...")
    try:
        response = requests.post(f"{BLENDER_SERVER_URL}/view", json={})
        return response.json()  # {status: success, image_base64: ...}
    except Exception as e:
        return {"status": "error", "message": str(e)}


tools = [run_blender_script, get_viewport_screenshot]

system_instruction = """
あなたはBlenderの熟練したPythonスクリプティングエキスパートです。
ユーザーの要望を実現するために、以下のサイクルで自律的に作業を行ってください。

【重要: コンテキストエラー対策】
BlenderのAPI (`bpy.ops`) は、実行コンテキストが適切でないと失敗します（例: "Poll failed"）。
もしコードの実行結果にエラーが含まれていたら、`bpy.ops` の代わりに `bpy.data` を直接操作して解決するか、
try-exceptブロックで囲んでエラーを回避してください。

【必須: 撮影セットアップ】
画像確認(`get_viewport_screenshot`)を行う際は、必ず以下を行ってください。
1. Camera: カメラを作成し、`bpy.context.scene.camera` にセットする。
2. Light: オブジェクトが見えるようにライトを配置する。

プロセス:
1. Plan: 実行計画を立てる。
2. Act: `run_blender_script` でコードを実行。返ってきた実行ログ(stdout/error)を確認する。
3. Observe: エラーがなければ `get_viewport_screenshot` で結果を確認。
4. Refine: 画像やエラーログを見て修正する。
"""


class BlenderAgent:
    def __init__(self):
        self.model = genai.GenerativeModel(
            model_name=MODEL_NAME,
            tools=tools,
            system_instruction=system_instruction
        )
        self.chat = self.model.start_chat(enable_automatic_function_calling=True)

    def send_message(self, message):
        print(f"\nUser: {message}")

        # ユーザー入力を送信
        # enable_automatic_function_calling=True なので、
        # モデルがツールを呼びたい場合、SDKが勝手に実行して結果をモデルに送り返し、
        # 最終的なテキスト回答が出るまでループしてくれる。

        # ただし、「画像」が返ってきた場合だけは特殊処理が必要。
        # SDKの自動ループは「テキスト(JSON)」の戻り値を想定しているため、
        # 画像をモデルに見せるために少しハックする。

        response = self.chat.send_message(message)

        # レスポンスの中に画像取得ツールの実行履歴があるか確認し、
        # もしあれば、取得した画像を明示的にユーザーとして見せるフローを追加しても良いが、
        # ここではシンプルにテキスト応答を表示する。
        # (※高度な画像フィードバックループは後述の「発展」で解説)

        print(f"\nAgent: {response.text}")
        return response


def main():
    agent = BlenderAgent()
    print("--- Gemini 3 Blender Agent Started ---")
    print("例: 'サイバーパンクな椅子を作って' 'シーンをクリアして' '終了'")

    while True:
        user_input = input("\n>> ")
        if user_input.lower() in ["exit", "quit", "終了"]:
            break

        try:
            # チャット履歴を手動制御して画像を送る必要があるため、
            # 標準の chat.send_message ではなく、少し泥臭い実装をここで紹介します。
            # 理由: 自動実行モードだと「画像データ」をテキストとして履歴に入れてしまいトークンが爆発するため。

            # 1. まず普通に投げる
            response = agent.chat.send_message(user_input)

            # 2. モデルが関数呼び出しをしたかチェック（SDKが裏でやってくれているが、結果を確認）
            # 実は enable_automatic_function_calling を使うと、画像の中身をモデルが見るのが難しい。
            # なので、今回は「モデルが get_viewport_screenshot を呼んだら、
            # 次のターンで画像を添付してあげる」というロジックを実装します。

            # モデルの思考の中に「画像を確認しました」的な発言が含まれているか、
            # あるいは function_calls の履歴を確認する。

            # (簡易実装のため、今回はテキスト応答のみを表示します。
            # 本当に画像を見せるには、automatic_function_callingをFalseにして手動ループを書く必要があります。
            # もしご希望なら「手動ループ完全版」を書きます)

            print(f"Gemini: {response.text}")

        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    model = genai.GenerativeModel(MODEL_NAME, tools=tools, system_instruction=system_instruction)
    chat = model.start_chat(enable_automatic_function_calling=False)

    print(f"--- Gemini 3 Blender Agent (Safety Limit: {MAX_LOOP_COUNT} turns) ---")

    while True:
        user_input = input("\nUser >> ")
        if user_input.lower() in ["exit", "quit"]:
            break

        try:
            current_loop = 0
            response = chat.send_message(user_input)

            while response.parts and any(part.function_call for part in response.parts):

                current_loop += 1
                if current_loop > MAX_LOOP_COUNT:
                    print(f"\n[System] Limit reached ({MAX_LOOP_COUNT} turns). Stopping execution to save tokens.")
                    response = chat.send_message(
                        "（システム通知: 試行回数が上限に達したため、ここで作業を打ち切ってください。）")
                    break

                print(f"  [Turn {current_loop}/{MAX_LOOP_COUNT}] Processing...")

                text_content = "".join([part.text for part in response.parts if part.text])
                if text_content:
                    print(f"Gemini (Thought): {text_content}")

                function_call_parts = [part for part in response.parts if part.function_call]

                for part in function_call_parts:
                    fc = part.function_call
                    fname = fc.name
                    fargs = fc.args

                    print(f"  [Thinking] Calling tool: {fname}...")

                    if fname == "run_blender_script":
                        result = run_blender_script(fargs["code"])
                        api_response = {"result": result}
                        response = chat.send_message(
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
                        res_json = get_viewport_screenshot()
                        if res_json.get("status") == "success":
                            pass  # TODO
                        else:
                            pass

            final_text = "".join([part.text for part in response.parts if part.text])
            print(f"Gemini: {final_text}")

        except Exception as e:
            print(f"Error: {e}")
            import traceback

            traceback.print_exc()
