# -*- coding: utf-8 -*-
import os
import sys
from os.path import join, dirname
from dotenv import load_dotenv
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest,
    TextMessage, FlexMessage, FlexContainer, QuickReply, QuickReplyButton,
    MessageAction, PostbackAction, PushMessageRequest
)
from linebot.v3.webhooks import (
    MessageEvent, TextMessageContent, FollowEvent, UnfollowEvent, PostbackEvent
)
from supabase import create_client, Client
from datetime import datetime, date, timedelta
import re

# --- Environment and API Setup ---
dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

app = Flask(__name__)

# --- Environment Variable Validation ---
def get_env(var_name):
    value = os.environ.get(var_name)
    if not value:
        print(f'Error: Specify {var_name} as environment variable.')
        sys.exit(1)
    return value

channel_secret = get_env('LINE_CHANNEL_SECRET')
channel_access_token = get_env('LINE_CHANNEL_ACCESS_TOKEN')
admin_user_id = get_env('ADMIN_USER_ID')
supabase_url = get_env('SUPABASE_URL')
supabase_key = get_env('SUPABASE_KEY')

# --- API Clients Initialization ---
handler = WebhookHandler(channel_secret)
configuration = Configuration(access_token=channel_access_token)
supabase: Client = create_client(supabase_url, supabase_key)

# --- UI Component Creation ---

def create_quick_reply_buttons(is_admin=False):
    if is_admin:
        items = [
            QuickReplyButton(action=MessageAction(label="เพิ่มกิจกรรม", text="/add")),
            QuickReplyButton(action=MessageAction(label="ล่าสุด", text="ล่าสุด")),
            QuickReplyButton(action=MessageAction(label="ดูสถิติ", text="/stats subscribers")),
        ]
    else:
        items = [
            QuickReplyButton(action=MessageAction(label="เหตุการณ์ล่าสุด", text="ล่าสุด")),
            QuickReplyButton(action=MessageAction(label="กิจกรรมวันนี้", text="วันนี้")),
            QuickReplyButton(action=MessageAction(label="ช่วยเหลือ", text="/help")),
        ]
    return QuickReply(items=items)

def create_event_flex_message(event, is_admin=False):
    footer_components = []
    if is_admin:
        footer_components.append({
            "type": "button",
            "style": "primary",
            "color": "#FF5555",
            "height": "sm",
            "action": {
                "type": "postback",
                "label": "ลบกิจกรรมนี้",
                "data": f"delete_event_{event['id']}",
                "displayText": f"ขอลบกิจกรรม ID: {event['id']}"
            }
        })

    return {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "Event", "weight": "bold", "color": "#1DB446", "size": "sm"},
                {"type": "text", "text": event['event_title'], "weight": "bold", "size": "xl", "margin": "md", "wrap": True}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "รายละเอียด", "weight": "bold", "size": "md"},
                {"type": "text", "text": event['event_description'] or "ไม่มีรายละเอียด", "wrap": True, "size": "sm", "margin": "md"},
                {"type": "separator", "margin": "xxl"},
                {"type": "box", "layout": "vertical", "margin": "xxl", "spacing": "sm", "contents": [
                    {"type": "box", "layout": "horizontal", "contents": [
                        {"type": "text", "text": "วันที่", "size": "sm", "color": "#555555", "flex": 0},
                        {"type": "text", "text": datetime.strptime(event['event_date'], '%Y-%m-%d').strftime('%d %b %Y'), "size": "sm", "color": "#111111", "align": "end"}
                    ]}
                ]}
            ]
        },
        "footer": {"type": "box", "layout": "vertical", "spacing": "sm", "contents": footer_components, "flex": 0} if footer_components else None
    }

# --- Database Functions ---

def add_subscriber(user_id):
    try:
        supabase.table('subscribers').insert({"user_id": user_id, "subscribed_at": datetime.now().isoformat()}).execute()
        app.logger.info(f"New subscriber added: {user_id}")
    except Exception as e:
        app.logger.error(f"Error adding subscriber {user_id}: {e}")

def remove_subscriber(user_id):
    try:
        supabase.table('subscribers').delete().eq('user_id', user_id).execute()
        app.logger.info(f"Subscriber removed: {user_id}")
    except Exception as e:
        app.logger.error(f"Error removing subscriber {user_id}: {e}")

def get_events(event_date):
    try:
        response = supabase.table('events').select('*').eq('event_date', event_date.isoformat()).order('created_at', desc=True).execute()
        return response.data
    except Exception as e:
        app.logger.error(f"Error fetching events for {event_date}: {e}")
        return []

def get_latest_events(limit=5):
    try:
        today = date.today().isoformat()
        response = supabase.table('events').select('*').gte('event_date', today).order('event_date').limit(limit).execute()
        return response.data
    except Exception as e:
        app.logger.error(f"Error fetching latest events: {e}")
        return []

# --- Webhook and Event Handlers ---

@app.route("/")
def health_check():
    return "OK"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(FollowEvent)
def handle_follow(event):
    user_id = event.source.user_id
    add_subscriber(user_id)
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        welcome_text = "ยินดีต้อนรับครับ! พิมพ์ 'ล่าสุด' เพื่อดูเหตุการณ์ หรือใช้เมนูด้านล่างได้เลย"
        line_bot_api.reply_message(ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=welcome_text, quick_reply=create_quick_reply_buttons(is_admin=False))]
        ))

@handler.add(UnfollowEvent)
def handle_unfollow(event):
    remove_subscriber(event.source.user_id)

@handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data
    user_id = event.source.user_id
    
    if user_id == admin_user_id and data.startswith('delete_event_'):
        event_id = data.split('_')[-1]
        try:
            supabase.table('events').delete().eq('id', int(event_id)).execute()
            reply_text = f"ลบกิจกรรม ID: {event_id} เรียบร้อยแล้ว"
        except Exception as e:
            reply_text = f"เกิดข้อผิดพลาดในการลบ: {e}"
            app.logger.error(reply_text)
        
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            ))

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    text = event.message.text.strip()
    user_id = event.source.user_id
    is_admin = user_id == admin_user_id
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        
        # --- Admin Commands ---
        if is_admin:
            if text.lower().startswith('/add '):
                parts = text[5:].split(';')
                if len(parts) != 3:
                    reply_text = "รูปแบบคำสั่งผิดพลาด\nตัวอย่าง: /add หัวข้อ;รายละเอียด;YYYY-MM-DD"
                    line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply_text)]))
                    return

                title, desc, event_date_str = [p.strip() for p in parts]
                try:
                    event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
                    new_event = {
                        'event_title': title,
                        'event_description': desc,
                        'event_date': event_date.isoformat(),
                        'created_by': user_id
                    }
                    insert_res = supabase.table('events').insert(new_event).execute()
                    
                    # Broadcast to subscribers
                    subscribers_res = supabase.table('subscribers').select('user_id').execute()
                    subscriber_ids = [sub['user_id'] for sub in subscribers_res.data]
                    if subscriber_ids:
                        broadcast_message = f"📢 มีกิจกรรมใหม่: {title}\nวันที่: {event_date.strftime('%d %b %Y')}\nรายละเอียด: {desc}"
                        line_bot_api.push_message(PushMessageRequest(to=subscriber_ids, messages=[TextMessage(text=broadcast_message)]))

                    reply_text = f"เพิ่มกิจกรรม '{title}' เรียบร้อยแล้ว และแจ้งเตือนผู้ติดตาม {len(subscriber_ids)} คน"
                except ValueError:
                    reply_text = "รูปแบบวันที่ไม่ถูกต้อง กรุณใช้ YYYY-MM-DD"
                except Exception as e:
                    reply_text = f"เกิดข้อผิดพลาด: {e}"
                    app.logger.error(reply_text)
                
                line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply_text)]))
                return

            if text.lower() == '/stats subscribers':
                count = supabase.table('subscribers').select('user_id', count='exact').execute().count
                line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=f"จำนวนผู้ติดตามทั้งหมด: {count} คน")]))
                return

        # --- User Commands ---
        reply_message = None
        events = []
        if text == 'ล่าสุด':
            events = get_latest_events()
            if not events:
                reply_message = TextMessage(text="ยังไม่มีกิจกรรมเร็วๆ นี้ครับ", quick_reply=create_quick_reply_buttons(is_admin))
        elif text == 'วันนี้':
            events = get_events(date.today())
            if not events:
                reply_message = TextMessage(text="วันนี้ไม่มีกิจกรรมครับ", quick_reply=create_quick_reply_buttons(is_admin))
        elif text.lower() == '/help':
            reply_message = TextMessage(text="คุณสามารถใช้คำสั่ง 'ล่าสุด' หรือ 'วันนี้' เพื่อดูกิจกรรมได้ครับ", quick_reply=create_quick_reply_buttons(is_admin))
        else: # Search by keyword
            try:
                response = supabase.table('events').select('*').text_search('event_title', f"'{text}'").execute()
                events = response.data
                if not events:
                    reply_message = TextMessage(text=f"ไม่พบกิจกรรมที่เกี่ยวกับ '{text}'", quick_reply=create_quick_reply_buttons(is_admin))
            except Exception as e:
                app.logger.error(f"Error during text search: {e}")
                reply_message = TextMessage(text="ขออภัย เกิดข้อผิดพลาดในการค้นหา", quick_reply=create_quick_reply_buttons(is_admin))

        if events:
            messages = [FlexMessage(alt_text="รายการกิจกรรม", contents={"type": "carousel", "contents": [create_event_flex_message(e, is_admin) for e in events]})]
            line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=messages))
        elif reply_message:
            line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[reply_message]))
        # If no command matches and it's not a search, we don't reply to avoid spam.

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
