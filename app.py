from flask import Flask, request, abort, render_template, redirect, url_for
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, ImageMessage, TextSendMessage, ImageSendMessage

import os
import uuid

app = Flask(__name__)

# ==============================
# 直書き設定（必ず自分のを入れてください）
# ==============================
LINE_CHANNEL_ACCESS_TOKEN = "00KCkQLhlaDFzo5+UTu+/C4A49iLmHu7bbpsfW8iamonjEJ1s88/wdm7Yrou+FazbxY7719UNGh96EUMa8QbsG Bf9K5rDWhJpq8XTxakXRuTM6HiJDSmERbIWfyfRMfscXJPcRyTL6YyGNZxqkYSAQdB04t89/1O/w1cDnyilFU="
LINE_CHANNEL_SECRET = "6c12aedc292307f95ccd67e959973761"

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ==============================
# 状態管理用（簡易版：メモリ内）
# ==============================
user_states = {}  # {user_id: {"stage": int, "pending_image": str, "history": []}}

# 謎データ（問題画像ID, ヒントキーワード, ヒント文）
QUESTIONS = {
    1: {"story": "ストーリー1", "image_id": "1GhjyvsaWP23x_wdz7n-nSqq5cziFcf1U", "hint_key": "hint1", "hint_text": "ヒント1"},
    2: {"story": "ストーリー2", "image_id": "1GhjyvsaWP23x_wdz7n-nSqq5cziFcf1U", "hint_key": "hint2", "hint_text": "ヒント2"},
    3: {"story": "ストーリー3", "image_id": "1GhjyvsaWP23x_wdz7n-nSqq5cziFcf1U", "hint_key": "hint3", "hint_text": "ヒント3"},
    4: {"story": "ストーリー4", "image_id": "1GhjyvsaWP23x_wdz7n-nSqq5cziFcf1U", "hint_key": "hint4", "hint_text": "ヒント4"},
    5: {"story": "ストーリー5", "image_id": "1GhjyvsaWP23x_wdz7n-nSqq5cziFcf1U", "hint_key": "hint5", "hint_text": "ヒント5"},
    6: {"story": "終章", "image_id": "1GhjyvsaWP23x_wdz7n-nSqq5cziFcf1U", "hint_key": "hint6", "hint_text": "ヒント6"},
}

# ==============================
# LINE webhook
# ==============================
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# ==============================
# メッセージ受信処理
# ==============================
@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    # 初期化: 「start」でゲーム開始
    if text.lower() == "start":
        user_states[user_id] = {"stage": 1, "pending_image": None, "history": []}
        send_question(user_id, 1)
        return

    # 進行中ならヒントチェック
    if user_id in user_states:
        stage = user_states[user_id]["stage"]
        q = QUESTIONS.get(stage)
        if q and text == q["hint_key"]:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=q["hint_text"])
            )
            return

    # それ以外は無視
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="「start」と送ってゲームを始めてね！")
    )

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    user_id = event.source.user_id
    if user_id not in user_states:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="まず「start」と送ってね！")
        )
        return

    stage = user_states[user_id]["stage"]

    # 画像保存
    message_content = line_bot_api.get_message_content(event.message.id)
    filename = f"static/{str(uuid.uuid4())}.jpg"
    with open(filename, "wb") as f:
        for chunk in message_content.iter_content():
            f.write(chunk)

    # 履歴に保存
    user_states[user_id]["pending_image"] = filename
    user_states[user_id]["history"].append({"stage": stage, "image": filename})

    # 主催者判定待ち
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="判定中です。しばらくお待ちください。")
    )

# ==============================
# 主催者用判定フォーム
# ==============================
@app.route("/judge")
def judge():
    return render_template("judge.html", users=user_states, questions=QUESTIONS)

@app.route("/judge/<user_id>/<result>")
def judge_user(user_id, result):
    if user_id not in user_states:
        return redirect(url_for("judge"))

    stage = user_states[user_id]["stage"]

    # 問題5は3パターン
    if stage == 5:
        if result == "correct1":
            msgs = [TextSendMessage(text="大正解！"), TextSendMessage(text="goodなエンディング")]
        elif result == "correct2":
            msgs = [TextSendMessage(text="正解！"), TextSendMessage(text="badなエンディング")]
        else:
            msgs = [TextSendMessage(text="残念。もう一度考えてみよう\nヒントが欲しければキーワードを送ってみて！")]
        line_bot_api.push_message(user_id, msgs)
        if result.startswith("correct"):
            user_states[user_id]["stage"] += 1

    # 問題6は通常2パターン
    elif stage == 6:
        if result == "correct":
            msgs = [TextSendMessage(text="大正解！"), TextSendMessage(text="クリア特典があるよ。探偵事務所にお越しください。")]
        else:
            msgs = [TextSendMessage(text="残念。もう一度考えてみよう\nヒントが欲しければキーワードを送ってみて！")]
        line_bot_api.push_message(user_id, msgs)
        if result == "correct":
            user_states[user_id]["stage"] += 1

    else:
        # 通常問題
        if result == "correct":
            msgs = [TextSendMessage(text="大正解！")]
            line_bot_api.push_message(user_id, msgs)
            user_states[user_id]["stage"] += 1
            send_question(user_id, user_states[user_id]["stage"])
        else:
            msgs = [TextSendMessage(text="残念。もう一度考えてみよう\nヒントが欲しければキーワードを送ってみて！")]
            line_bot_api.push_message(user_id, msgs)

    return redirect(url_for("judge"))

# ==============================
# 出題関数
# ==============================
def send_question(user_id, stage):
    if stage not in QUESTIONS:
        line_bot_api.push_message(user_id, TextSendMessage(text="すべての問題が終了しました！"))
        return
    q = QUESTIONS[stage]
    msgs = [
        TextSendMessage(text=q["story"]),
        ImageSendMessage(original_content_url=f"https://your-domain/static/{q['image_id']}.jpg",
                         preview_image_url=f"https://your-domain/static/{q['image_id']}.jpg"),
        TextSendMessage(text="答えとなる写真を送ってね！")
    ]
    line_bot_api.push_message(user_id, msgs)

# ==============================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
