import os
import time
from flask import Flask, request, render_template, redirect, send_from_directory
from linebot import LineBotApi, WebhookHandler
from linebot.models import *
from linebot.exceptions import InvalidSignatureError

app = Flask(__name__)

# 認証情報
line_bot_api = LineBotApi('00KCkQLhlaDFzo5+UTu+/C4A49iLmHu7bbpsfW8iamonjEJ1s88/wdm7Yrou+FazbxY7719UNGh96EUMa8QbsG Bf9K5rDWhJpq8XTxakXRuTM6HiJDSmERbIWfyfRMfscXJPcRyTL6YyGNZxqkYSAQdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('6c12aedc292307f95ccd67e959973761')

# 状態管理
user_states = {}
pending_users = {}

# 問題データ
questions = [
    {"q": "第1問: ◯◯。その答えを写真で送ってね！", "a": ["answer1"], "hint": "○○に注目してみよう", "explain": "これは○○でした。"},
    {"q": "第2問: △△。その答えを写真で送ってね！", "a": ["answer2"], "hint": "△△が鍵かも", "explain": "これは△△でした。"},
    {"q": "第3問: □□。その答えを写真で送ってね！", "a": ["answer3"], "hint": "□□をよく見て", "explain": "これは□□でした。"},
    {"q": "第4問: ◇◇。その答えを写真で送ってね！", "a": ["answer4"], "hint": "◇◇の色に注目", "explain": "これは◇◇でした。"},
    {"q": "第5問: 最後の謎、○○または△△。その答えを写真で送ってね！", "a": ["final1", "final2"], "hint": "最後は分岐があるよ", "explain": "実は答えは2つありました。"}
]

# 画像保存先
IMAGE_DIR = 'static/images'
os.makedirs(IMAGE_DIR, exist_ok=True)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    if user_id not in user_states:
        user_states[user_id] = {"name": None, "stage": 0}
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="こんにちは！あなたの名前を教えてください。"))
        return

    state = user_states[user_id]

    if state["name"] is None:
        state["name"] = text
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{text}さん、登録完了！{questions[0]['q']}"))
        return

    if text == "ヒント":
        hint = questions[state['stage']]['hint']
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=hint))
        return

    if text == "リタイア":
        explain = questions[state['stage']]['explain']
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"{explain}\n{advance(user_id)}"))
        return

    if text == "1=∞":
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="そんなわけないだろ亀ども"))
        return

    if text.endswith("？") or text.endswith("?"):
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="Good question!"))
        return

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    user_id = event.source.user_id
    message_id = event.message.id
    timestamp = int(time.time())
    filename = f"{user_id}_{timestamp}.jpg"
    filepath = os.path.join(IMAGE_DIR, filename)

    # 画像取得して保存
    message_content = line_bot_api.get_message_content(message_id)
    with open(filepath, 'wb') as f:
        for chunk in message_content.iter_content():
            f.write(chunk)

    # 表示用に保存
    pending_users[user_id] = {
        "name": user_states[user_id]["name"],
        "stage": user_states[user_id]["stage"] + 1,
        "img": filename
    }

    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="画像を受け取りました!判定をお待ちください。"))

@handler.add(MessageEvent, message=StickerMessage)
def handle_sticker(event):
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text="何の意味があるの？"))

@app.route("/form")
def form():
    return render_template("judge.html", users=pending_users)

@app.route("/judge", methods=["POST"])
def judge():
    user_id = request.form["user_id"]
    result = request.form["result"]
    if user_id in user_states:
        if result == "correct":
            msg = "大正解！次の問題に進むよ"
            advance(user_id)
        else:
            msg = "残念不正解。もう一度よく考えてみよう。「ヒント」と送れば何かあるかも"
        line_bot_api.push_message(user_id, TextSendMessage(text=msg))
        del pending_users[user_id]
    return redirect("/form")

def advance(user_id):
    state = user_states[user_id]
    state['stage'] += 1
    if state['stage'] >= len(questions):
        line_bot_api.push_message(user_id, TextSendMessage(text=f"全問クリア！おめでとう！"))
        return "終了"
    else:
        next_q = questions[state['stage']]['q']
        line_bot_api.push_message(user_id, TextSendMessage(text=next_q))
        return next_q

if __name__ == "__main__":
    app.run(debug=True)
