from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest,
    TextMessage, FlexMessage, FlexContainer, QuickReply, QuickReplyItem,
    MessageAction
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent
from datetime import datetime, date
import os
from supabase import create_client, Client
import re
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Supabase setup
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase_client: Client = create_client(supabase_url, supabase_key)

# Get LINE Channel Access Token and Channel Secret from environment variables
configuration = Configuration(access_token=os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))
admin_ids = os.getenv('ADMIN_IDS', '').split(',') if os.getenv('ADMIN_IDS') else []

# Initialize LINE Bot API
line_bot_api = MessagingApi(ApiClient(configuration))

def format_thai_date(date_str):
    """Convert date string to Thai format"""
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        thai_months = [
            '', 'มกราคม', 'กุมภาพันธ์', 'มีนาคม', 'เมษายน', 'พฤษภาคม', 'มิถุนายน',
            'กรกฎาคม', 'สิงหาคม', 'กันยายน', 'ตุลาคม', 'พฤศจิกายน', 'ธันวาคม'
        ]
        return f"{date_obj.day} {thai_months[date_obj.month]} {date_obj.year + 543}"
    except:
        return date_str

def create_event_flex_message(event_data):
    """Create Flex Message for a single event using Supabase data structure"""
    
    # Format the date for display
    formatted_date = format_thai_date(event_data.get('event_date', ''))
    
    flex_message_content = {
        "type": "bubble",
        "size": "mega",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "text",
                    "text": event_data.get('event_title', 'ไม่มีชื่อกิจกรรม'),
                    "wrap": True,
                    "weight": "bold",
                    "size": "lg",
                    "color": "#1DB446"
                },
                {
                    "type": "separator",
                    "margin": "md"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "sm",
                    "margin": "md",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "📅",
                                    "size": "sm",
                                    "flex": 0
                                },
                                {
                                    "type": "text",
                                    "text": f"วันที่: {formatted_date}",
                                    "size": "sm",
                                    "color": "#666666",
                                    "wrap": True,
                                    "margin": "sm"
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    }
    
    # Add description if available
    if event_data.get('event_description'):
        description_box = {
            "type": "box",
            "layout": "horizontal",
            "margin": "sm",
            "contents": [
                {
                    "type": "text",
                    "text": "📝",
                    "size": "sm",
                    "flex": 0
                },
                {
                    "type": "text",
                    "text": event_data.get('event_description'),
                    "size": "sm",
                    "color": "#444444",
                    "wrap": True,
                    "margin": "sm"
                }
            ]
        }
        flex_message_content["body"]["contents"][-1]["contents"].append(description_box)
    
    return flex_message_content

def get_single_flex_message(event_data):
    flex_message_content = create_event_flex_message(event_data)
    return FlexMessage(alt_text="กิจกรรมล่าสุด", contents=FlexContainer.from_dict(flex_message_content))

def create_events_carousel_message(events_list):
    bubbles = []
    for event_data in events_list:
        bubble_content = create_event_flex_message(event_data)
        bubbles.append(bubble_content)
    
    carousel_content = {
        "type": "carousel",
        "contents": bubbles
    }
    
    return FlexMessage(alt_text="กิจกรรมทั้งหมด", contents=FlexContainer.from_dict(carousel_content))

def create_main_quick_reply():
    """Create main menu quick reply buttons"""
    return QuickReply(items=[
        QuickReplyItem(action=MessageAction(label="📅 ดูกิจกรรมล่าสุด", text="ล่าสุด")),
        QuickReplyItem(action=MessageAction(label="📋 กิจกรรมวันนี้", text="/today")),
        QuickReplyItem(action=MessageAction(label="⏭️ กิจกรรมถัดไป", text="/next")),
        QuickReplyItem(action=MessageAction(label="🔔 สมัครแจ้งเตือน", text="/subscribe"))
    ])

def create_admin_quick_reply():
    """Create admin menu quick reply buttons"""
    return QuickReply(items=[
        QuickReplyItem(action=MessageAction(label="📝 เพิ่มกิจกรรม", text="เพิ่มกิจกรรม")),
        QuickReplyItem(action=MessageAction(label="📋 จัดการกิจกรรม", text="จัดการกิจกรรม")),
        QuickReplyItem(action=MessageAction(label="🏠 เมนูหลัก", text="สวัสดี")),
        QuickReplyItem(action=MessageAction(label="ℹ️ วิธีใช้", text="/admin"))
    ])

@app.route("/")
def health_check():
    """Health check endpoint for monitoring services"""
    return {"status": "ok", "service": "LINE Bot Event Notification System"}, 200

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
    """Handle when user follows the bot"""
    welcome_message = TextMessage(
        text="🎉 ยินดีต้อนรับครับ!\n\nขอบคุณที่ติดตามระบบแจ้งเตือนกิจกรรมของเรา\n\nคุณสามารถใช้เมนูด้านล่างเพื่อดูกิจกรรมต่างๆ หรือสมัครรับการแจ้งเตือนได้เลยครับ",
        quick_reply=create_main_quick_reply()
    )
    line_bot_api.reply_message(
        ReplyMessageRequest(reply_token=event.reply_token, messages=[welcome_message])
    )

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    text = event.message.text
    if text == "สวัสดี":
        message = TextMessage(
            text="สวัสดีครับ! ยินดีต้อนรับสู่ระบบแจ้งเตือนกิจกรรม 🎉\n\nคุณสามารถใช้เมนูด้านล่างเพื่อดูกิจกรรมต่างๆ ได้เลยครับ",
            quick_reply=create_main_quick_reply()
        )
        line_bot_api.reply_message(
            ReplyMessageRequest(reply_token=event.reply_token, messages=[message])
        )
    elif text == "ล่าสุด":
        try:
            response = supabase_client.table('events').select('*').order('event_date', desc=False).execute()
            events = response.data

            if events:
                flex_message = create_events_carousel_message(events)
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[flex_message, TextMessage(text="เลือกดูกิจกรรมอื่นๆ ได้เลยครับ", quick_reply=create_main_quick_reply())]
                    )
                )
            else:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="ยังไม่มีกิจกรรมที่บันทึกไว้ค่ะ", quick_reply=create_main_quick_reply())]
                    )
                )
        except Exception as e:
            app.logger.error(f"Error fetching events from Supabase: {e}")
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="เกิดข้อผิดพลาดในการดึงข้อมูลกิจกรรมค่ะ กรุณาลองใหม่อีกครั้ง", quick_reply=create_main_quick_reply())]
                )
            )
    elif text == "/subscribe":
        user_id = event.source.user_id
        try:
            # Check if user is already subscribed
            response = supabase_client.table('subscribers').select('user_id').eq('user_id', user_id).execute()
            if response.data:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="คุณได้สมัครรับการแจ้งเตือนอยู่แล้วค่ะ", quick_reply=create_main_quick_reply())]
                    )
                )
            else:
                # Add user to subscribers table
                supabase_client.table('subscribers').insert({'user_id': user_id}).execute()
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="✅ คุณได้สมัครรับการแจ้งเตือนกิจกรรมเรียบร้อยแล้วค่ะ", quick_reply=create_main_quick_reply())]
                    )
                )
        except Exception as e:
            app.logger.error(f"Error subscribing user: {e}")
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="เกิดข้อผิดพลาดในการสมัครรับการแจ้งเตือนค่ะ กรุณาลองใหม่อีกครั้ง", quick_reply=create_main_quick_reply())]
                )
            )
    elif text.startswith("/add "):
        user_id = event.source.user_id
        if user_id not in admin_ids:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="คุณไม่มีสิทธิ์ในการเพิ่มกิจกรรมค่ะ")]
                )
            )
            return

        # รองรับหลายรูปแบบ: /add title | desc | date หรือ /add title desc date
        content = text[len("/add "):].strip()
        
        # ลองแยกด้วย | ก่อน
        if ' | ' in content:
            parts = content.split(' | ', 2)
        else:
            # แยกด้วยช่องว่าง โดยเอาส่วนท้ายเป็นวันที่
            words = content.split()
            if len(words) >= 3:
                # หาวันที่ในรูปแบบ YYYY-MM-DD
                date_pattern = r'\d{4}-\d{2}-\d{2}'
                date_matches = []
                for i, word in enumerate(words):
                    if re.match(date_pattern, word):
                        date_matches.append((i, word))
                
                if date_matches:
                    # ใช้วันที่แรกที่พบ
                    date_index, date_str = date_matches[0]
                    title_desc_words = words[:date_index] + words[date_index+1:]
                    
                    # แบ่งครึ่งสำหรับ title และ description
                    mid = len(title_desc_words) // 2
                    if mid == 0:
                        parts = [' '.join(title_desc_words), 'ไม่มีรายละเอียด', date_str]
                    else:
                        parts = [
                            ' '.join(title_desc_words[:mid]),
                            ' '.join(title_desc_words[mid:]),
                            date_str
                        ]
                else:
                    # ไม่พบวันที่ ใช้คำสุดท้ายเป็นวันที่
                    if len(words) >= 3:
                        parts = [
                            ' '.join(words[:-2]),
                            words[-2],
                            words[-1]
                        ]
                    else:
                        parts = words
            else:
                parts = words

        if len(parts) < 3:
            help_text = """📝 วิธีเพิ่มกิจกรรม:

แบบง่าย:
/add บัตรตำรวจ ผกก.อยู่ที่กระเป๋าปืน 2025-08-08

แบบละเอียด:  
/add บัตรตำรวจ | ผกก.อยู่ที่กระเป๋าปืน | 2025-08-08

หรือกด "เพิ่มกิจกรรม" แล้วพิมพ์:
บัตรตำรวจ | ผกก.อยู่ที่กระเป๋าปืน | 2025-08-08"""
            
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=help_text, quick_reply=create_admin_quick_reply())]
                )
            )
            return

        event_title = parts[0].strip()
        event_description = parts[1].strip() if len(parts) > 1 else 'ไม่มีรายละเอียด'
        event_date_str = parts[2].strip() if len(parts) > 2 else parts[-1].strip()

        try:
            event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
        except ValueError:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="รูปแบบวันที่ไม่ถูกต้องค่ะ กรุณาใช้ YYYY-MM-DD", quick_reply=create_admin_quick_reply())]
                )
            )
            return

        try:
            # Log parsing results for debugging
            app.logger.info(f"Parsed event - Title: '{event_title}', Desc: '{event_description}', Date: '{event_date}'")
            
            response = supabase_client.table('events').insert({
                'event_title': event_title,
                'event_description': event_description,
                'event_date': str(event_date),
                'created_by': user_id
            }).execute()
            
            app.logger.info(f"Supabase response: {response}")
            
            if response.data and len(response.data) > 0:
                event_id = response.data[0]['id']
                success_text = f"✅ เพิ่มกิจกรรมสำเร็จ!\n\n📝 {event_title}\n📋 {event_description}\n📅 {format_thai_date(str(event_date))}\n🆔 ID: {event_id}"
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=success_text, quick_reply=create_admin_quick_reply())]
                    )
                )
            else:
                app.logger.error(f"Supabase returned no data: {response}")
                raise Exception("No data returned from Supabase insert.")

        except Exception as e:
            app.logger.error(f"Error adding event to Supabase: {e}")
            app.logger.error(f"Event data - Title: '{event_title}', Desc: '{event_description}', Date: '{event_date}'")
            
            # Return more specific error message
            error_msg = f"เกิดข้อผิดพลาด: {str(e)[:100]}\nTitle: {event_title}\nDescription: {event_description}\nDate: {event_date}"
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=error_msg, quick_reply=create_admin_quick_reply())]
                )
            )
    elif text == "/today":
        try:
            today = date.today()
            response = supabase_client.table('events').select('*').eq('event_date', str(today)).execute()
            events = response.data

            if events:
                if len(events) == 1:
                    flex_message = get_single_flex_message(events[0])
                else:
                    flex_message = create_events_carousel_message(events)
                
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[flex_message, TextMessage(text="เลือกดูกิจกรรมอื่นๆ ได้เลยครับ", quick_reply=create_main_quick_reply())]
                    )
                )
            else:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(
                            text="วันนี้ยังไม่มีกิจกรรมที่กำหนดไว้ค่ะ",
                            quick_reply=create_main_quick_reply()
                        )]
                    )
                )
        except Exception as e:
            app.logger.error(f"Error fetching today's events: {e}")
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(
                        text="เกิดข้อผิดพลาดในการดึงข้อมูลกิจกรรมวันนี้ค่ะ กรุณาลองใหม่อีกครั้ง",
                        quick_reply=create_main_quick_reply()
                    )]
                )
            )
    elif text == "/next":
        try:
            today = date.today()
            response = supabase_client.table('events').select('*').gte('event_date', str(today)).order('event_date', desc=False).limit(5).execute()
            events = response.data

            if events:
                if len(events) == 1:
                    flex_message = get_single_flex_message(events[0])
                else:
                    flex_message = create_events_carousel_message(events)
                
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[flex_message, TextMessage(text="เลือกดูกิจกรรมอื่นๆ ได้เลยครับ", quick_reply=create_main_quick_reply())]
                    )
                )
            else:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(
                            text="ยังไม่มีกิจกรรมที่กำหนดไว้ในอนาคตค่ะ",
                            quick_reply=create_main_quick_reply()
                        )]
                    )
                )
        except Exception as e:
            app.logger.error(f"Error fetching upcoming events: {e}")
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(
                        text="เกิดข้อผิดพลาดในการดึงข้อมูลกิจกรรมถัดไปค่ะ กรุณาลองใหม่อีกครั้ง",
                        quick_reply=create_main_quick_reply()
                    )]
                )
            )
    elif text == "/admin" and event.source.user_id in admin_ids:
        admin_help_text = """🔧 เมนู Admin - ใช้ปุ่มด้านล่างได้เลย!

📝 เพิ่มกิจกรรม = กดปุ่ม "เพิ่มกิจกรรม"
📋 จัดการกิจกรรม = กดปุ่ม "จัดการกิจกรรม"

📖 คำสั่งแบบเดิม:
• /add ชื่อ | รายละเอียด | 2025-01-20
• /edit ID | ชื่อใหม่ | รายละเอียด | วันที่
• /delete ID"""
        
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=admin_help_text, quick_reply=create_admin_quick_reply())]
            )
        )
    elif text == "เพิ่มกิจกรรม" and event.source.user_id in admin_ids:
        guide_text = """📝 เพิ่มกิจกรรมใหม่ (ใช้ง่าย!)

🔸 แบบง่าย (แนะนำ):
/add บัตรตำรวจ ผกก.อยู่ที่กระเป๋าปืน 2025-08-08

🔸 แบบละเอียด:
/add การประชุมทีม | หารือแผนงาน Q1 | 2025-01-20

🔸 แบบไม่ใช้คำสั่ง:
การประชุมทีม | หารือแผนงาน Q1 | 2025-01-20

💡 เคล็ดลับ: ใส่วันที่ท้ายสุดรูปแบบ YYYY-MM-DD"""
        
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=guide_text, quick_reply=create_admin_quick_reply())]
            )
        )
    elif text == "จัดการกิจกรรม" and event.source.user_id in admin_ids:
        try:
            response = supabase_client.table('events').select('*').order('event_date', desc=False).execute()
            events = response.data
            
            if events:
                event_list = "📋 เลือกกิจกรรมที่ต้องการจัดการ:\n\n"
                for event in events[:8]:  # แสดงแค่ 8 รายการแรก
                    formatted_date = format_thai_date(event.get('event_date', ''))
                    event_list += f"🆔 {event['id']} - {event.get('event_title', 'ไม่มีชื่อ')}\n"
                    event_list += f"📅 {formatted_date}\n"
                    event_list += f"▫️ แก้ไข: /edit {event['id']} | ชื่อใหม่ | รายละเอียด | วันที่\n"
                    event_list += f"▫️ ลบ: /delete {event['id']}\n"
                    event_list += "─" * 25 + "\n\n"
                
                if len(events) > 8:
                    event_list += f"และอีก {len(events) - 8} กิจกรรม...\nใช้ /list เพื่อดูทั้งหมด"
                
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=event_list, quick_reply=create_admin_quick_reply())]
                    )
                )
            else:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="ยังไม่มีกิจกรรมในระบบครับ\nกดปุ่ม 'เพิ่มกิจกรรม' เพื่อเริ่มต้น", quick_reply=create_admin_quick_reply())]
                    )
                )
        except Exception as e:
            app.logger.error(f"Error listing events for management: {e}")
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="เกิดข้อผิดพลาดในการดึงรายการกิจกรรมครับ", quick_reply=create_admin_quick_reply())]
                )
            )
    elif text == "/list" and event.source.user_id in admin_ids:
        try:
            response = supabase_client.table('events').select('*').order('event_date', desc=False).execute()
            events = response.data
            
            if events:
                event_list = "📋 รายการกิจกรรมทั้งหมด:\n\n"
                for event in events:
                    formatted_date = format_thai_date(event.get('event_date', ''))
                    event_list += f"🆔 ID: {event['id']}\n"
                    event_list += f"📅 {event.get('event_title', 'ไม่มีชื่อ')}\n"
                    event_list += f"📝 {event.get('event_description', 'ไม่มีรายละเอียด')}\n"
                    event_list += f"🗓️ {formatted_date}\n"
                    event_list += "─" * 30 + "\n\n"
                
                # Split long messages if needed
                if len(event_list) > 2000:
                    event_list = event_list[:1900] + "...\n\nใช้ /admin เพื่อดูคำสั่งจัดการ"
                
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=event_list)]
                    )
                )
            else:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="ยังไม่มีกิจกรรมในระบบครับ")]
                    )
                )
        except Exception as e:
            app.logger.error(f"Error listing events: {e}")
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="เกิดข้อผิดพลาดในการดึงรายการกิจกรรมครับ")]
                )
            )
    elif text.startswith("/edit ") and event.source.user_id in admin_ids:
        # Expected format: /edit [ID] | [title] | [description] | [date]
        parts = text[len("/edit "):].split(' | ', 3)
        if len(parts) != 4:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="รูปแบบคำสั่งไม่ถูกต้องครับ\nใช้: /edit [ID] | ชื่อใหม่ | รายละเอียดใหม่ | YYYY-MM-DD")]
                )
            )
            return
        
        try:
            event_id = int(parts[0].strip())
            new_title = parts[1].strip()
            new_description = parts[2].strip()
            new_date_str = parts[3].strip()
            
            # Validate date format
            try:
                new_date = datetime.strptime(new_date_str, '%Y-%m-%d').date()
            except ValueError:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="รูปแบบวันที่ไม่ถูกต้องครับ กรุณาใช้ YYYY-MM-DD")]
                    )
                )
                return
            
            # Update event in database
            response = supabase_client.table('events').update({
                'event_title': new_title,
                'event_description': new_description,
                'event_date': str(new_date)
            }).eq('id', event_id).execute()
            
            if response.data and len(response.data) > 0:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=f"✅ แก้ไขกิจกรรม ID: {event_id} เรียบร้อยแล้วครับ")]
                    )
                )
            else:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=f"❌ ไม่พบกิจกรรม ID: {event_id} หรือไม่สามารถแก้ไขได้")]
                    )
                )
        except ValueError:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="ID ต้องเป็นตัวเลขเท่านั้นครับ")]
                )
            )
        except Exception as e:
            app.logger.error(f"Error editing event: {e}")
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="เกิดข้อผิดพลาดในการแก้ไขกิจกรรมครับ")]
                )
            )
    elif text.startswith("/delete ") and event.source.user_id in admin_ids:
        # Expected format: /delete [ID]
        try:
            event_id_str = text[len("/delete "):].strip()
            event_id = int(event_id_str)
            
            # First get event details for confirmation
            get_response = supabase_client.table('events').select('*').eq('id', event_id).execute()
            
            if get_response.data and len(get_response.data) > 0:
                event_data = get_response.data[0]
                
                # Delete event from database
                delete_response = supabase_client.table('events').delete().eq('id', event_id).execute()
                
                if delete_response.data:
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=f"🗑️ ลบกิจกรรมเรียบร้อยแล้วครับ\n\n📝 {event_data.get('event_title', '')}\n🆔 ID: {event_id}")]
                        )
                    )
                else:
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=f"❌ ไม่สามารถลบกิจกรรม ID: {event_id} ได้")]
                        )
                    )
            else:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=f"❌ ไม่พบกิจกรรม ID: {event_id}")]
                    )
                )
        except ValueError:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="ID ต้องเป็นตัวเลขเท่านั้นครับ")]
                )
            )
        except Exception as e:
            app.logger.error(f"Error deleting event: {e}")
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="เกิดข้อผิดพลาดในการลบกิจกรรมครับ")]
                )
            )
    else:
        # ตรวจสอบว่าเป็น Admin และส่งข้อความแบบ "ชื่อ | รายละเอียด | วันที่" หรือไม่
        if event.source.user_id in admin_ids and ' | ' in text and len(text.split(' | ')) == 3:
            parts = text.split(' | ')
            event_title = parts[0].strip()
            event_description = parts[1].strip()
            event_date_str = parts[2].strip()
            
            try:
                event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
            except ValueError:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="รูปแบบวันที่ไม่ถูกต้องครับ กรุณาใช้ YYYY-MM-DD", quick_reply=create_admin_quick_reply())]
                    )
                )
                return
            
            try:
                response = supabase_client.table('events').insert({
                    'event_title': event_title,
                    'event_description': event_description,
                    'event_date': str(event_date),
                    'created_by': event.source.user_id
                }).execute()
                
                if response.data and len(response.data) > 0:
                    event_id = response.data[0]['id']
                    success_text = f"✅ เพิ่มกิจกรรมสำเร็จ!\n\n📝 {event_title}\n📋 {event_description}\n📅 {format_thai_date(str(event_date))}\n🆔 ID: {event_id}"
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=success_text, quick_reply=create_admin_quick_reply())]
                        )
                    )
                else:
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="เกิดข้อผิดพลาดในการบันทึกกิจกรรมครับ", quick_reply=create_admin_quick_reply())]
                        )
                    )
            except Exception as e:
                app.logger.error(f"Error adding event via simple format: {e}")
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="เกิดข้อผิดพลาดในการบันทึกกิจกรรมครับ", quick_reply=create_admin_quick_reply())]
                    )
                )
        else:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"คุณพูดว่า: {text}\n\nลองใช้เมนูด้านล่างเพื่อดูกิจกรรมครับ", quick_reply=create_main_quick_reply())]
                )
            )

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
