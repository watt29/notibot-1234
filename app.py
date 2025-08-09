# -*- coding: utf-8 -*-
# FORCE DEPLOY: 2025-08-09 - Deploy retry mechanism fix
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest,
    TextMessage, FlexMessage, FlexContainer, QuickReply, QuickReplyItem,
    MessageAction, PushMessageRequest
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent
from datetime import datetime, date, timedelta
import os
from supabase import create_client, Client
import re
import time
from dotenv import load_dotenv
import tempfile

# Load environment variables first
load_dotenv()

from contact_management import (
    validate_phone_number, search_contacts_multi_keyword, add_contact, 
    edit_contact, delete_contact, get_all_contacts, export_contacts_to_excel,
    create_contact_flex_message
)
# Contact management helper functions (inline to avoid circular imports)
def convert_thai_to_english_command(text):
    """Convert Thai natural language to English commands"""
    text = text.lower().strip()
    
    # เพิ่มเบอร์ commands
    add_patterns = ["เพิ่มเบอร์", "บันทึกเบอร์", "เพิ่มชื่อ", "บันทึกชื่อ", "เก็บเบอร์"]
    # ค้นหา commands  
    search_patterns = ["หาเบอร์", "ค้นหา", "หาชื่อ", "เบอร์ของ", "ชื่อ", "เบอร์", "หา"]
    
    # Check if it's an add command
    for pattern in add_patterns:
        if text.startswith(pattern):
            remaining = text.replace(pattern, "").strip()
            if remaining:
                return f"add_phone {remaining}"
            else:
                return "add_phone "
    
    # Check if it's a search command
    for pattern in search_patterns:
        if text.startswith(pattern):
            remaining = text.replace(pattern, "").strip()
            if remaining:
                return f"search_phone {remaining}"
            else:
                return "search_phone "
    
    return text

def detect_incomplete_command(text):
    """Detect incomplete commands and suggest completion"""
    text = text.lower().strip()
    
    # Check for incomplete add commands
    if text in ["add_phone", "เพิ่มเบอร์", "บันทึกเบอร์"]:
        return {
            "type": "incomplete_add",
            "message": "📝 กรุณาใส่ข้อมูลเพิ่มเติม\n\n💡 รูปแบบ: เพิ่มเบอร์ ชื่อ เบอร์โทร\n🔤 ตัวอย่าง: เพิ่มเบอร์ สมชาย 081-234-5678",
            "suggestions": ["เพิ่มเบอร์ สมชาย 081-234-5678", "เพิ่มเบอร์ นางสาวดาว 089-999-8888"]
        }
    
    # Check for incomplete search commands
    if text in ["search_phone", "หาเบอร์", "ค้นหา", "หา"]:
        return {
            "type": "incomplete_search", 
            "message": "🔍 กรุณาใส่คำค้นหา\n\n💡 สามารถค้นหาได้:\n• ชื่อ: หาเบอร์ สมชาย\n• เบอร์: หาเบอร์ 081\n• หลายคำ: หาเบอร์ สมชาย 081",
            "suggestions": ["หาเบอร์ สมชาย", "หาเบอร์ 081", "หาเบอร์ คุณ"]
        }
    
    return None

def create_contact_quick_reply():
    """Create quick reply for contact management"""
    return QuickReply(items=[
        QuickReplyItem(action=MessageAction(label="📞 เพิ่มเบอร์", text="เพิ่มเบอร์ ")),
        QuickReplyItem(action=MessageAction(label="🔍 หาเบอร์", text="หาเบอร์ ")),
        QuickReplyItem(action=MessageAction(label="📋 ดูทั้งหมด", text="เบอร์ทั้งหมด")),
        QuickReplyItem(action=MessageAction(label="🏠 เมนูหลัก", text="สวัสดี"))
    ])

def handle_add_contact_simple(data, event, user_id):
    """Handle add contact with simple interface"""
    parts = data.strip().split()
    
    if len(parts) < 2:
        error_msg = "❌ กรุณาใส่ข้อมูลครบ\n\n💡 รูปแบบ: เพิ่มเบอร์ ชื่อ เบอร์โทร\n🔤 ตัวอย่าง: เพิ่มเบอร์ สมชาย 081-234-5678"
        quick_reply = QuickReply(items=[
            QuickReplyItem(action=MessageAction(label="💡 เพิ่มเบอร์ สมชาย 081-234-5678", text="เพิ่มเบอร์ สมชาย 081-234-5678")),
            QuickReplyItem(action=MessageAction(label="💡 เพิ่มเบอร์ ดาว 089-999-8888", text="เพิ่มเบอร์ ดาว 089-999-8888"))
        ])
        
        safe_line_api_call(line_bot_api.reply_message,
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=error_msg, quick_reply=quick_reply)]
            )
        )
        return
    
    # รองรับชื่อหลายคำ - เบอร์โทรอยู่ท้ายสุด
    phone = parts[-1]  # เบอร์โทรคือคำสุดท้าย
    name = " ".join(parts[:-1])  # ชื่อคือทุกคำยกเว้นคำสุดท้าย
    
    result = add_contact(name, phone, user_id)
    
    if result["success"]:
        contact_data = result["data"]
        success_msg = f"✅ บันทึกเบอร์เรียบร้อย!\n\n📝 ชื่อ: {contact_data['name']}\n📞 เบอร์: {contact_data['phone_number']}\n\n💡 ลองค้นหาดู: หาเบอร์ {name}"
        quick_reply = create_contact_quick_reply()
    else:
        success_msg = f"❌ {result['error']}\n\n💡 ลองตรวจสอบเบอร์โทรให้ถูกต้อง"
        quick_reply = create_contact_quick_reply()
    
    safe_line_api_call(line_bot_api.reply_message,
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=success_msg, quick_reply=quick_reply)]
        )
    )

def handle_search_contact_simple(query, event):
    """Handle search with simple interface"""
    contacts = search_contacts_multi_keyword(query)
    
    if not contacts:
        error_msg = "❌ ไม่พบข้อมูลที่ตรงกับคำค้นหา\n\n💡 ลองใช้คำค้นหาอื่น เช่น บางส่วนของชื่อ หรือเลขเบอร์"
        quick_reply = create_contact_quick_reply()
        
        safe_line_api_call(line_bot_api.reply_message,
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=error_msg, quick_reply=quick_reply)]
            )
        )
        return
    
    if len(contacts) == 1:
        # Single result - show detailed
        contact = contacts[0]
        flex_content = create_contact_flex_message(contact, is_single=True)
        flex_message = FlexMessage(alt_text="ผลการค้นหา", contents=FlexContainer.from_dict(flex_content))
        
        success_msg = f"🎯 พบแล้ว! ({len(contacts)} คน)"
        quick_reply = create_contact_quick_reply()
        
        safe_line_api_call(line_bot_api.reply_message,
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[flex_message, TextMessage(text=success_msg, quick_reply=quick_reply)]
            )
        )
    else:
        # Multiple results - show carousel
        bubbles = [create_contact_flex_message(contact) for contact in contacts[:10]]
        carousel_content = {"type": "carousel", "contents": bubbles}
        flex_message = FlexMessage(alt_text="ผลการค้นหา", contents=FlexContainer.from_dict(carousel_content))
        
        success_msg = f"🎯 พบ {len(contacts)} คน{' (แสดง 10 คนแรก)' if len(contacts) > 10 else ''}"
        quick_reply = create_contact_quick_reply()
        
        safe_line_api_call(line_bot_api.reply_message,
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[flex_message, TextMessage(text=success_msg, quick_reply=quick_reply)]
            )
        )

app = Flask(__name__)

def safe_line_api_call(api_method, *args, max_retries=3, **kwargs):
    """Safely call LINE Bot API with retry logic for connection issues"""
    from urllib3.exceptions import ProtocolError
    
    for attempt in range(max_retries):
        try:
            return api_method(*args, **kwargs)
        except (ProtocolError, ConnectionResetError, ConnectionAbortedError) as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2  # 2, 4, 6 seconds
                app.logger.warning(f"LINE API connection error (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                app.logger.error(f"LINE API failed after {max_retries} attempts: {e}")
                raise e
        except Exception as e:
            # Log other unexpected errors but don't retry
            app.logger.error(f"Unexpected LINE API error: {e}")
            raise e

# Supabase setup
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_SERVICE_KEY')  # Use service role key for full permissions
supabase_client: Client = create_client(supabase_url, supabase_key)

# Simple in-memory storage for user states (in production, use Redis or database)
user_states = {}

# Get LINE Channel Access Token and Channel Secret from environment variables
configuration = Configuration(access_token=os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))
admin_ids = os.getenv('ADMIN_IDS', '').split(',') if os.getenv('ADMIN_IDS') else []

# Initialize LINE Bot API
line_bot_api = MessagingApi(ApiClient(configuration))

# ==================== CONTACT MANAGEMENT FUNCTIONS ====================
# Functions imported from contact_management.py

def is_admin_user(user_id):
    """Check if user is admin"""
    return user_id in admin_ids

# ==================== END CONTACT MANAGEMENT ====================

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

def create_event_flex_message(event_data, is_admin=False):
    """Create Flex Message for a single event using Supabase data structure"""
    
    # Format the date for display
    formatted_date = format_thai_date(event_data.get('event_date', ''))
    event_id = event_data.get('id', '')
    
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
                                    "text": "🆔",
                                    "size": "sm",
                                    "flex": 0
                                },
                                {
                                    "type": "text",
                                    "text": f"ID: {event_id}",
                                    "size": "sm",
                                    "color": "#999999",
                                    "margin": "sm"
                                }
                            ]
                        } if is_admin else None,
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
    
    # Filter out None items
    flex_message_content["body"]["contents"][-1]["contents"] = [
        item for item in flex_message_content["body"]["contents"][-1]["contents"] if item is not None
    ]
    
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
    
    # Add admin buttons if user is admin
    if is_admin:
        flex_message_content["footer"] = {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "secondary",
                    "height": "sm",
                    "action": {
                        "type": "message",
                        "label": "✏️ แก้ไข",
                        "text": f"แก้ไข {event_id}"
                    }
                },
                {
                    "type": "button",
                    "style": "secondary",
                    "height": "sm",
                    "color": "#ff6b6b",
                    "action": {
                        "type": "message",
                        "label": "🗑️ ลบ",
                        "text": f"ลบ {event_id}"
                    }
                }
            ]
        }
    
    return flex_message_content

def get_single_flex_message(event_data, is_admin=False):
    flex_message_content = create_event_flex_message(event_data, is_admin)
    return FlexMessage(alt_text="กิจกรรมล่าสุด", contents=FlexContainer.from_dict(flex_message_content))

def create_events_carousel_message(events_list, is_admin=False, page=1, total_events=None):
    # Limit to 10 events per carousel (LINE limit is 12)
    max_per_page = 10
    start_idx = (page - 1) * max_per_page
    end_idx = start_idx + max_per_page
    page_events = events_list[start_idx:end_idx]
    
    bubbles = []
    for event_data in page_events:
        bubble_content = create_event_flex_message(event_data, is_admin)
        bubbles.append(bubble_content)
    
    carousel_content = {
        "type": "carousel",
        "contents": bubbles
    }
    
    return FlexMessage(alt_text=f"กิจกรรมหน้า {page}", contents=FlexContainer.from_dict(carousel_content))

def create_pagination_quick_reply(page, total_pages, command_prefix="ล่าสุด"):
    """Create pagination quick reply buttons"""
    items = []
    
    if page > 1:
        items.append(QuickReplyItem(action=MessageAction(label="◀️ ก่อนหน้า", text=f"{command_prefix} {page-1}")))
    
    items.append(QuickReplyItem(action=MessageAction(label=f"📄 {page}/{total_pages}", text=f"{command_prefix} 1")))
    
    if page < total_pages:
        items.append(QuickReplyItem(action=MessageAction(label="▶️ ถัดไป", text=f"{command_prefix} {page+1}")))
    
    items.append(QuickReplyItem(action=MessageAction(label="🏠 เมนูหลัก", text="สวัสดี")))
    
    return QuickReply(items=items)

def create_main_quick_reply():
    """Create main menu quick reply buttons - รวมทั้งระบบเดิมและใหม่"""
    return QuickReply(items=[
        QuickReplyItem(action=MessageAction(label="📅 กิจกรรมล่าสุด", text="ล่าสุด")),
        QuickReplyItem(action=MessageAction(label="📋 กิจกรรมวันนี้", text="/today")),
        QuickReplyItem(action=MessageAction(label="📞 เพิ่มเบอร์", text="เพิ่มเบอร์ ")),
        QuickReplyItem(action=MessageAction(label="🔍 หาเบอร์", text="หาเบอร์ ")),
        QuickReplyItem(action=MessageAction(label="📱 เบอร์ทั้งหมด", text="เบอร์ทั้งหมด")),
        QuickReplyItem(action=MessageAction(label="🔍 ค้นหากิจกรรม", text="/search")),
        QuickReplyItem(action=MessageAction(label="🗓️ เดือนนี้", text="/month")),
        QuickReplyItem(action=MessageAction(label="🔔 สมัครแจ้งเตือน", text="/subscribe"))
    ])

def create_admin_quick_reply():
    """Create admin menu quick reply buttons - รวมทั้งระบบเดิมและใหม่"""
    return QuickReply(items=[
        QuickReplyItem(action=MessageAction(label="📝 เพิ่มกิจกรรม", text="เพิ่มกิจกรรม")),
        QuickReplyItem(action=MessageAction(label="📋 จัดการกิจกรรม", text="จัดการกิจกรรม")),
        QuickReplyItem(action=MessageAction(label="📞 จัดการเบอร์", text="/contacts")),
        QuickReplyItem(action=MessageAction(label="📊 เบอร์ทั้งหมด", text="/list")),
        QuickReplyItem(action=MessageAction(label="📁 Export Excel", text="/export")),
        QuickReplyItem(action=MessageAction(label="📢 ส่งแจ้งเตือน", text="ส่งแจ้งเตือน")),
        QuickReplyItem(action=MessageAction(label="🏠 เมนูหลัก", text="สวัสดี")),
        QuickReplyItem(action=MessageAction(label="ℹ️ วิธีใช้", text="/admin"))
    ])

def create_delete_confirm_quick_reply(event_id):
    """Create delete confirmation quick reply buttons"""
    return QuickReply(items=[
        QuickReplyItem(action=MessageAction(label="✅ ยืนยันลบ", text=f"ยืนยันลบ {event_id}")),
        QuickReplyItem(action=MessageAction(label="❌ ยกเลิก", text="สวัสดี")),
        QuickReplyItem(action=MessageAction(label="🏠 เมนูหลัก", text="สวัสดี"))
    ])

def create_date_quick_reply():
    """Create quick date selection buttons"""
    today = date.today()
    dates = []
    for i in range(11):  # Next 11 days (maximum for Quick Reply limit)
        future_date = today + timedelta(days=i)
        label = "วันนี้" if i == 0 else f"{future_date.day}/{future_date.month}"
        dates.append(QuickReplyItem(action=MessageAction(label=label, text=str(future_date))))
    
    dates.append(QuickReplyItem(action=MessageAction(label="📅 วันอื่น", text="วันอื่น")))
    dates.append(QuickReplyItem(action=MessageAction(label="❌ ยกเลิก", text="สวัสดี")))
    
    return QuickReply(items=dates)

def create_cancel_quick_reply():
    """Create cancel operation quick reply"""
    return QuickReply(items=[
        QuickReplyItem(action=MessageAction(label="❌ ยกเลิก", text="สวัสดี")),
        QuickReplyItem(action=MessageAction(label="🏠 เมนูหลัก", text="สวัสดี"))
    ])

def send_automatic_notifications():
    """Send automatic notifications for events happening today or tomorrow"""
    try:
        today = date.today()
        tomorrow = today + timedelta(days=1)
        
        # Get events for today and tomorrow
        events_today = supabase_client.table('events').select('*').eq('event_date', str(today)).execute()
        events_tomorrow = supabase_client.table('events').select('*').eq('event_date', str(tomorrow)).execute()
        
        # Get all subscribers
        subscribers_response = supabase_client.table('subscribers').select('user_id').execute()
        if not subscribers_response.data:
            return {"status": "no_subscribers", "message": "No subscribers found"}
        
        notifications_sent = 0
        
        # Send notifications for today's events
        if events_today.data:
            for event in events_today.data:
                formatted_date = format_thai_date(event.get('event_date', ''))
                message = f"""🔔 เตือนกิจกรรมวันนี้!

📝 **{event.get('event_title', '')}**
📋 {event.get('event_description', '')}
📅 **วันที่:** {formatted_date} (วันนี้)

⏰ อย่าลืมเข้าร่วมนะครับ!

📲 แจ้งเตือนอัตโนมัติ"""
                
                for subscriber in subscribers_response.data:
                    try:
                        safe_line_api_call(line_bot_api.push_message,
                            PushMessageRequest(
                                to=subscriber['user_id'],
                                messages=[TextMessage(text=message)]
                            )
                        )
                        notifications_sent += 1
                    except Exception as e:
                        app.logger.error(f"Failed to send today notification to {subscriber['user_id']}: {e}")
        
        # Send notifications for tomorrow's events
        if events_tomorrow.data:
            for event in events_tomorrow.data:
                formatted_date = format_thai_date(event.get('event_date', ''))
                message = f"""🔔 เตือนกิจกรรมพรุ่งนี้!

📝 **{event.get('event_title', '')}**
📋 {event.get('event_description', '')}
📅 **วันที่:** {formatted_date} (พรุ่งนี้)

⏰ เตรียมตัวไว้นะครับ!

📲 แจ้งเตือนอัตโนมัติ"""
                
                for subscriber in subscribers_response.data:
                    try:
                        safe_line_api_call(line_bot_api.push_message,
                            PushMessageRequest(
                                to=subscriber['user_id'],
                                messages=[TextMessage(text=message)]
                            )
                        )
                        notifications_sent += 1
                    except Exception as e:
                        app.logger.error(f"Failed to send tomorrow notification to {subscriber['user_id']}: {e}")
        
        return {
            "status": "success", 
            "notifications_sent": notifications_sent,
            "events_today": len(events_today.data) if events_today.data else 0,
            "events_tomorrow": len(events_tomorrow.data) if events_tomorrow.data else 0,
            "subscribers": len(subscribers_response.data)
        }
        
    except Exception as e:
        app.logger.error(f"Error in automatic notifications: {e}")
        return {"status": "error", "message": str(e)}

@app.route("/")
def health_check():
    """Health check endpoint for monitoring services"""
    return {"status": "ok", "service": "LINE Bot Event Notification System", "version": "v3.4-undefined-fix"}, 200

@app.route("/send-notifications", methods=['GET', 'POST'])
def trigger_notifications():
    """Endpoint to trigger automatic notifications - can be called by scheduler"""
    result = send_automatic_notifications()
    return result, 200

@app.route("/force-restart", methods=['POST'])
def force_restart():
    """Emergency endpoint to force application restart - helps with deployment issues"""
    import os
    import sys
    
    app.logger.info("Force restart requested - triggering application restart")
    
    # In production, this will cause the container to restart
    os.execv(sys.executable, ['python'] + sys.argv)
    
    return {"status": "restarting", "message": "Application restart initiated"}, 200

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
    safe_line_api_call(line_bot_api.reply_message,
        ReplyMessageRequest(reply_token=event.reply_token, messages=[welcome_message])
    )

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    text = event.message.text
    if text == "สวัสดี":
        message = TextMessage(
            text="สวัสดีครับ! ยินดีต้อนรับ 🎉\n\n📅 **ระบบแจ้งเตือนกิจกรรม**\n• ดูกิจกรรมต่างๆ\n• ค้นหากิจกรรม\n\n📞 **สมุดเบอร์โทร**\n• เพิ่มเบอร์ ชื่อ เบอร์\n• หาเบอร์ ชื่อ\n• เบอร์ทั้งหมด\n\nเลือกได้จากเมนูด้านล่าง 👇",
            quick_reply=create_main_quick_reply()
        )
        safe_line_api_call(line_bot_api.reply_message,
            ReplyMessageRequest(reply_token=event.reply_token, messages=[message])
        )
    elif text.startswith("ล่าสุด"):
        try:
            # Parse page number if provided
            parts = text.split()
            page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
            
            response = supabase_client.table('events').select('*').order('event_date', desc=False).execute()
            events = response.data

            if events:
                is_admin = event.source.user_id in admin_ids
                total_events = len(events)
                max_per_page = 10
                total_pages = (total_events + max_per_page - 1) // max_per_page  # Ceiling division
                
                if total_pages > 1:
                    flex_message = create_events_carousel_message(events, is_admin, page)
                    pagination_reply = create_pagination_quick_reply(page, total_pages, "ล่าสุด")
                    status_text = f"📄 หน้า {page}/{total_pages} (ทั้งหมด {total_events} กิจกรรม)"
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[flex_message, TextMessage(text=status_text, quick_reply=pagination_reply)]
                        )
                    )
                else:
                    flex_message = create_events_carousel_message(events, is_admin)
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[flex_message, TextMessage(text="เลือกดูกิจกรรมอื่นๆ ได้เลยครับ", quick_reply=create_main_quick_reply())]
                        )
                    )
            else:
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="ยังไม่มีกิจกรรมที่บันทึกไว้ค่ะ", quick_reply=create_main_quick_reply())]
                    )
                )
        except Exception as e:
            app.logger.error(f"Error fetching events from Supabase: {e}")
            safe_line_api_call(line_bot_api.reply_message,
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
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="คุณได้สมัครรับการแจ้งเตือนอยู่แล้วค่ะ", quick_reply=create_main_quick_reply())]
                    )
                )
            else:
                # Add user to subscribers table
                supabase_client.table('subscribers').insert({'user_id': user_id}).execute()
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="✅ คุณได้สมัครรับการแจ้งเตือนกิจกรรมเรียบร้อยแล้วค่ะ", quick_reply=create_main_quick_reply())]
                    )
                )
        except Exception as e:
            app.logger.error(f"Error subscribing user: {e}")
            safe_line_api_call(line_bot_api.reply_message,
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="เกิดข้อผิดพลาดในการสมัครรับการแจ้งเตือนค่ะ กรุณาลองใหม่อีกครั้ง", quick_reply=create_main_quick_reply())]
                )
            )
    elif text.startswith("/add "):
        user_id = event.source.user_id
        if user_id not in admin_ids:
            safe_line_api_call(line_bot_api.reply_message,
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
            
            safe_line_api_call(line_bot_api.reply_message,
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
            safe_line_api_call(line_bot_api.reply_message,
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
                safe_line_api_call(line_bot_api.reply_message,
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
            safe_line_api_call(line_bot_api.reply_message,
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
                is_admin = event.source.user_id in admin_ids
                if len(events) == 1:
                    flex_message = get_single_flex_message(events[0], is_admin)
                else:
                    flex_message = create_events_carousel_message(events, is_admin)
                
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[flex_message, TextMessage(text="เลือกดูกิจกรรมอื่นๆ ได้เลยครับ", quick_reply=create_main_quick_reply())]
                    )
                )
            else:
                safe_line_api_call(line_bot_api.reply_message,
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
            safe_line_api_call(line_bot_api.reply_message,
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
                is_admin = event.source.user_id in admin_ids
                if len(events) == 1:
                    flex_message = get_single_flex_message(events[0], is_admin)
                else:
                    flex_message = create_events_carousel_message(events, is_admin)
                
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[flex_message, TextMessage(text="เลือกดูกิจกรรมอื่นๆ ได้เลยครับ", quick_reply=create_main_quick_reply())]
                    )
                )
            else:
                safe_line_api_call(line_bot_api.reply_message,
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
            safe_line_api_call(line_bot_api.reply_message,
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(
                        text="เกิดข้อผิดพลาดในการดึงข้อมูลกิจกรรมถัดไปค่ะ กรุณาลองใหม่อีกครั้ง",
                        quick_reply=create_main_quick_reply()
                    )]
                )
            )
    elif text == "/month":
        try:
            today = date.today()
            start_of_month = today.replace(day=1)
            # Get last day of month
            if today.month == 12:
                end_of_month = date(today.year + 1, 1, 1) - timedelta(days=1)
            else:
                end_of_month = date(today.year, today.month + 1, 1) - timedelta(days=1)
            
            response = supabase_client.table('events').select('*').gte('event_date', str(start_of_month)).lte('event_date', str(end_of_month)).order('event_date', desc=False).execute()
            events = response.data

            if events:
                is_admin = event.source.user_id in admin_ids
                total_events = len(events)
                
                if len(events) == 1:
                    flex_message = get_single_flex_message(events[0], is_admin)
                elif total_events > 10:
                    flex_message = create_events_carousel_message(events, is_admin, 1)
                    total_pages = (total_events + 9) // 10
                    pagination_reply = create_pagination_quick_reply(1, total_pages, "/month")
                    status_text = f"🗓️ เดือน {today.month}/{today.year} - หน้า 1/{total_pages} (ทั้งหมด {total_events} กิจกรรม)"
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[flex_message, TextMessage(text=status_text, quick_reply=pagination_reply)]
                        )
                    )
                    return
                else:
                    flex_message = create_events_carousel_message(events, is_admin)
                
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[flex_message, TextMessage(text=f"🗓️ กิจกรรมเดือน {today.month}/{today.year} ทั้งหมด {total_events} รายการ", quick_reply=create_main_quick_reply())]
                    )
                )
            else:
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(
                            text=f"🗓️ ไม่มีกิจกรรมในเดือน {today.month}/{today.year}",
                            quick_reply=create_main_quick_reply()
                        )]
                    )
                )
        except Exception as e:
            app.logger.error(f"Error fetching monthly events: {e}")
            safe_line_api_call(line_bot_api.reply_message,
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(
                        text="เกิดข้อผิดพลาดในการดึงข้อมูลกิจกรรมประจำเดือนค่ะ กรุณาลองใหม่อีกครั้ง",
                        quick_reply=create_main_quick_reply()
                    )]
                )
            )
    elif text == "/search":
        # Start guided search flow
        user_states[event.source.user_id] = {"step": "search_menu"}
        
        # Create search menu buttons
        search_menu = QuickReply(items=[
            QuickReplyItem(action=MessageAction(label="📝 ค้นหาชื่อ/รายละเอียด", text="ค้นหาข้อความ")),
            QuickReplyItem(action=MessageAction(label="📅 ค้นหาวันที่", text="ค้นหาวันที่")),
            QuickReplyItem(action=MessageAction(label="🔍 ค้นหาทั้งหมด", text="ค้นหาทั้งหมด")),
            QuickReplyItem(action=MessageAction(label="❌ ยกเลิก", text="สวัสดี"))
        ])
        
        search_help = """🔍 เลือกประเภทการค้นหา

🔸 **ค้นหาชื่อ/รายละเอียด** - ค้นหาจากคำในชื่อหรือรายละเอียดกิจกรรม
🔸 **ค้นหาวันที่** - ค้นหากิจกรรมในวันที่เฉพาะ  
🔸 **ค้นหาทั้งหมด** - พิมพ์คำค้นเองได้ทุกรูปแบบ

เลือกปุ่มด้านล่างเพื่อเริ่มค้นหา"""
        
        safe_line_api_call(line_bot_api.reply_message,
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=search_help, quick_reply=search_menu)]
            )
        )
    elif text.startswith("/search "):
        search_term = text[len("/search "):].strip()
        
        try:
            # Check if search term is a date
            if re.match(r'\d{4}-\d{2}-\d{2}', search_term):
                response = supabase_client.table('events').select('*').eq('event_date', search_term).execute()
            else:
                # Search in title and description
                response = supabase_client.table('events').select('*').or_(f"event_title.ilike.%{search_term}%,event_description.ilike.%{search_term}%").order('event_date', desc=False).execute()
            
            events = response.data
            
            if events:
                is_admin = event.source.user_id in admin_ids
                total_events = len(events)
                
                if len(events) == 1:
                    flex_message = get_single_flex_message(events[0], is_admin)
                elif total_events > 10:
                    flex_message = create_events_carousel_message(events, is_admin, 1)
                    total_pages = (total_events + 9) // 10
                    pagination_reply = create_pagination_quick_reply(1, total_pages, f"/search {search_term}")
                    status_text = f"🔍 ค้นหา '{search_term}' - หน้า 1/{total_pages} (พบ {total_events} รายการ)"
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[flex_message, TextMessage(text=status_text, quick_reply=pagination_reply)]
                        )
                    )
                    return
                else:
                    flex_message = create_events_carousel_message(events, is_admin)
                
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[flex_message, TextMessage(text=f"🔍 ค้นหา '{search_term}' พบ {total_events} รายการ", quick_reply=create_main_quick_reply())]
                    )
                )
            else:
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(
                            text=f"🔍 ไม่พบกิจกรรมที่ตรงกับ '{search_term}'",
                            quick_reply=create_main_quick_reply()
                        )]
                    )
                )
        except Exception as e:
            app.logger.error(f"Error searching events: {e}")
            safe_line_api_call(line_bot_api.reply_message,
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(
                        text="เกิดข้อผิดพลาดในการค้นหาค่ะ กรุณาลองใหม่อีกครั้ง",
                        quick_reply=create_main_quick_reply()
                    )]
                )
            )
    elif text == "/admin" and event.source.user_id in admin_ids:
        admin_help_text = """🔧 เมนู Admin - ระบบครบครัน!

📅 **จัดการกิจกรรม:**
• เพิ่มกิจกรรม = กดปุ่ม "เพิ่มกิจกรรม"  
• จัดการกิจกรรม = กดปุ่ม "จัดการกิจกรรม"
• ส่งแจ้งเตือน = กดปุ่ม "ส่งแจ้งเตือน"

📞 **จัดการเบอร์โทร:**
• /contacts - ดูคำสั่งเบอร์ทั้งหมด
• /add ชื่อ เบอร์ - เพิ่มเบอร์ใหม่
• /list - ดูเบอร์ทั้งหมด
• /export - ส่งออกไฟล์ Excel

💡 **คำสั่งเดิม:**
• /add ชื่อ | รายละเอียด | 2025-01-20 (กิจกรรม)
• /edit, /delete, /notify"""
        
        safe_line_api_call(line_bot_api.reply_message,
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=admin_help_text, quick_reply=create_admin_quick_reply())]
            )
        )
    elif text == "เพิ่มกิจกรรม" and event.source.user_id in admin_ids:
        # Start guided event creation
        user_states[event.source.user_id] = {"step": "waiting_title", "event_data": {}}
        
        guide_text = """📝 เพิ่มกิจกรรมใหม่ - ขั้นตอน 1/3

🔸 **ส่งชื่อกิจกรรม**

ตัวอย่าง:
• บัตรข้าราชการตำรวจ  
• การประชุมทีมงาน
• งานวันกำนันผู้ใหญ่บ้าน

💬 แค่พิมพ์ชื่อกิจกรรมแล้วส่งมา"""
        
        safe_line_api_call(line_bot_api.reply_message,
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=guide_text, quick_reply=create_cancel_quick_reply())]
            )
        )
    elif text == "จัดการกิจกรรม" and event.source.user_id in admin_ids:
        try:
            # Log for debugging
            app.logger.info(f"Admin {event.source.user_id} requested event management")
            
            response = supabase_client.table('events').select('*').order('event_date', desc=False).execute()
            events = response.data
            
            app.logger.info(f"Found {len(events) if events else 0} events")
            
            if events and len(events) > 0:
                # Create Flex Messages for better management
                events_for_management = events[:10]  # แสดงแค่ 10 รายการแรก
                
                if len(events_for_management) == 1:
                    # Single event - show as single Flex Message with management buttons
                    flex_message = get_single_flex_message(events_for_management[0], is_admin=True)
                    status_text = f"📋 กิจกรรมที่ต้องการจัดการ (1 รายการ)\n\nใช้ปุ่ม ✏️ แก้ไข หรือ 🗑️ ลบ ในการ์ดด้านบน"
                else:
                    # Multiple events - show as carousel
                    flex_message = create_events_carousel_message(events_for_management, is_admin=True)
                    status_text = f"📋 กิจกรรมที่ต้องการจัดการ ({len(events_for_management)} รายการ)\n\nใช้ปุ่ม ✏️ แก้ไข หรือ 🗑️ ลบ ในการ์ดแต่ละอัน"
                
                if len(events) > 10:
                    status_text += f"\n\n📄 แสดง 10 จาก {len(events)} กิจกรรม\nใช้คำสั่ง /list เพื่อดูทั้งหมด"
                
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[
                            flex_message,
                            TextMessage(text=status_text, quick_reply=create_admin_quick_reply())
                        ]
                    )
                )
            else:
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="ยังไม่มีกิจกรรมในระบบครับ\n\nกดปุ่ม '📝 เพิ่มกิจกรรม' เพื่อเริ่มต้น", quick_reply=create_admin_quick_reply())]
                    )
                )
        except Exception as e:
            app.logger.error(f"Error listing events for management: {e}")
            safe_line_api_call(line_bot_api.reply_message,
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"เกิดข้อผิดพลาดในการดึงรายการกิจกรรมครับ\n\nError: {str(e)[:100]}", quick_reply=create_admin_quick_reply())]
                )
            )
    # เพิ่มการจัดการสำหรับ Non-Admin users ที่กดปุ่ม "จัดการกิจกรรม"
    elif text == "จัดการกิจกรรม":
        safe_line_api_call(line_bot_api.reply_message,
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="❌ คุณไม่มีสิทธิ์ในการจัดการกิจกรรม\n\nเฉพาะ Admin เท่านั้นที่สามารถใช้ฟีเจอร์นี้ได้", quick_reply=create_main_quick_reply())]
            )
        )
    elif text == "ส่งแจ้งเตือน" and event.source.user_id in admin_ids:
        # Start guided notification sending
        try:
            # Get subscriber count
            subscribers_response = supabase_client.table('subscribers').select('user_id').execute()
            subscriber_count = len(subscribers_response.data) if subscribers_response.data else 0
            
            # Get upcoming events for quick notification options
            today = date.today()
            upcoming_response = supabase_client.table('events').select('*').gte('event_date', str(today)).order('event_date', desc=False).limit(5).execute()
            upcoming_events = upcoming_response.data if upcoming_response.data else []
            
            user_states[event.source.user_id] = {"step": "notify_menu"}
            
            # Create notification menu
            notify_menu = QuickReply(items=[
                QuickReplyItem(action=MessageAction(label="📝 ข้อความกำหนดเอง", text="ข้อความกำหนดเอง")),
                QuickReplyItem(action=MessageAction(label="📅 แจ้งกิจกรรมถัดไป", text="แจ้งกิจกรรมถัดไป")),
                QuickReplyItem(action=MessageAction(label="🤖 ทดสอบแจ้งเตือนอัตโนมัติ", text="ทดสอบแจ้งเตือนอัตโนมัติ")),
                QuickReplyItem(action=MessageAction(label="📊 ดูสถิติผู้สมัคร", text="ดูสถิติผู้สมัคร")),
                QuickReplyItem(action=MessageAction(label="❌ ยกเลิก", text="สวัสดี"))
            ])
            
            guide_text = f"""📢 ส่งแจ้งเตือนให้ผู้สมัคร

👥 **จำนวนผู้สมัครปัจจุบัน:** {subscriber_count} คน
📅 **กิจกรรมถัดไป:** {len(upcoming_events)} รายการ

🔸 **เลือกประเภทการแจ้งเตือน:**

• **ข้อความกำหนดเอง** - พิมพ์ข้อความเอง
• **แจ้งกิจกรรมถัดไป** - แจ้งกิจกรรมที่กำลังจะมาถึง
• **🤖 ทดสอบแจ้งเตือนอัตโนมัติ** - ทดสอบระบบแจ้งเตือนวันนี้/พรุ่งนี้
• **ดูสถิติผู้สมัคร** - ดูข้อมูลผู้สมัครรับแจ้งเตือน

เลือกปุ่มด้านล่างเพื่อเริ่มส่งแจ้งเตือน"""
            
            safe_line_api_call(line_bot_api.reply_message,
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=guide_text, quick_reply=notify_menu)]
                )
            )
        except Exception as e:
            app.logger.error(f"Error preparing notification menu: {e}")
            safe_line_api_call(line_bot_api.reply_message,
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="เกิดข้อผิดพลาดในการเตรียมเมนูแจ้งเตือน", quick_reply=create_admin_quick_reply())]
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
                
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=event_list)]
                    )
                )
            else:
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="ยังไม่มีกิจกรรมในระบบครับ")]
                    )
                )
        except Exception as e:
            app.logger.error(f"Error listing events: {e}")
            safe_line_api_call(line_bot_api.reply_message,
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="เกิดข้อผิดพลาดในการดึงรายการกิจกรรมครับ")]
                )
            )
    elif text.startswith("/edit ") and event.source.user_id in admin_ids:
        # Expected format: /edit [ID] | [title] | [description] | [date]
        parts = text[len("/edit "):].split(' | ', 3)
        if len(parts) != 4:
            safe_line_api_call(line_bot_api.reply_message,
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
                safe_line_api_call(line_bot_api.reply_message,
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
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=f"✅ แก้ไขกิจกรรม ID: {event_id} เรียบร้อยแล้วครับ")]
                    )
                )
            else:
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=f"❌ ไม่พบกิจกรรม ID: {event_id} หรือไม่สามารถแก้ไขได้")]
                    )
                )
        except ValueError:
            safe_line_api_call(line_bot_api.reply_message,
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="ID ต้องเป็นตัวเลขเท่านั้นครับ")]
                )
            )
        except Exception as e:
            app.logger.error(f"Error editing event: {e}")
            safe_line_api_call(line_bot_api.reply_message,
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
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=f"🗑️ ลบกิจกรรมเรียบร้อยแล้วครับ\n\n📝 {event_data.get('event_title', '')}\n🆔 ID: {event_id}")]
                        )
                    )
                else:
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=f"❌ ไม่สามารถลบกิจกรรม ID: {event_id} ได้")]
                        )
                    )
            else:
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=f"❌ ไม่พบกิจกรรม ID: {event_id}")]
                    )
                )
        except ValueError:
            safe_line_api_call(line_bot_api.reply_message,
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="ID ต้องเป็นตัวเลขเท่านั้นครับ")]
                )
            )
        except Exception as e:
            app.logger.error(f"Error deleting event: {e}")
            safe_line_api_call(line_bot_api.reply_message,
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="เกิดข้อผิดพลาดในการลบกิจกรรมครับ")]
                )
            )
    elif text.startswith("แก้ไข ") and event.source.user_id in admin_ids:
        # Handle "แก้ไข ID" from Flex Message button
        try:
            event_id = int(text[len("แก้ไข "):].strip())
            
            # Get current event data
            response = supabase_client.table('events').select('*').eq('id', event_id).execute()
            if response.data and len(response.data) > 0:
                event_data = response.data[0]
                current_date = event_data.get('event_date', '2025-01-01')
                
                # Start guided edit flow - show selection menu
                user_states[event.source.user_id] = {
                    "step": "edit_menu", 
                    "event_id": event_id,
                    "current_data": event_data
                }
                
                # Create selection buttons for what to edit
                edit_menu = QuickReply(items=[
                    QuickReplyItem(action=MessageAction(label="📝 แก้ชื่อ", text="แก้ชื่อ")),
                    QuickReplyItem(action=MessageAction(label="📋 แก้รายละเอียด", text="แก้รายละเอียด")),
                    QuickReplyItem(action=MessageAction(label="📅 แก้วันที่", text="แก้วันที่")),
                    QuickReplyItem(action=MessageAction(label="🔄 แก้ทั้งหมด", text="แก้ทั้งหมด")),
                    QuickReplyItem(action=MessageAction(label="❌ ยกเลิก", text="สวัสดี"))
                ])
                
                guide_text = f"""✏️ แก้ไขกิจกรรม ID: {event_id}

📝 **ชื่อ:** {event_data.get('event_title', '')}
📋 **รายละเอียด:** {event_data.get('event_description', '')}  
📅 **วันที่:** {format_thai_date(event_data.get('event_date', ''))}

🔸 **เลือกส่วนที่ต้องการแก้ไข:**"""
                
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=guide_text, quick_reply=edit_menu)]
                    )
                )
            else:
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=f"❌ ไม่พบกิจกรรม ID: {event_id}", quick_reply=create_admin_quick_reply())]
                    )
                )
        except ValueError:
            safe_line_api_call(line_bot_api.reply_message,
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="ID ต้องเป็นตัวเลขเท่านั้นครับ", quick_reply=create_admin_quick_reply())]
                )
            )
        except Exception as e:
            app.logger.error(f"Error handling edit request: {e}")
            safe_line_api_call(line_bot_api.reply_message,
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="เกิดข้อผิดพลาดครับ", quick_reply=create_admin_quick_reply())]
                )
            )
    elif text.startswith("ลบ ") and event.source.user_id in admin_ids:
        # Handle "ลบ ID" from Flex Message button
        try:
            event_id = int(text[len("ลบ "):].strip())
            
            # Get event details for confirmation
            response = supabase_client.table('events').select('*').eq('id', event_id).execute()
            if response.data and len(response.data) > 0:
                event_data = response.data[0]
                
                confirm_text = f"""🗑️ ยืนยันการลบกิจกรรม?

🆔 ID: {event_id}
📝 {event_data.get('event_title', '')}
📋 {event_data.get('event_description', '')}
📅 {format_thai_date(event_data.get('event_date', ''))}

⚠️ การลบไม่สามารถย้อนกลับได้!

กดปุ่ม "✅ ยืนยันลบ" เพื่อลบ หรือ "❌ ยกเลิก" """
                
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=confirm_text, quick_reply=create_delete_confirm_quick_reply(event_id))]
                    )
                )
            else:
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=f"❌ ไม่พบกิจกรรม ID: {event_id}", quick_reply=create_admin_quick_reply())]
                    )
                )
        except ValueError:
            safe_line_api_call(line_bot_api.reply_message,
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="ID ต้องเป็นตัวเลขเท่านั้นครับ", quick_reply=create_admin_quick_reply())]
                )
            )
        except Exception as e:
            app.logger.error(f"Error handling delete request: {e}")
            safe_line_api_call(line_bot_api.reply_message,
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="เกิดข้อผิดพลาดครับ", quick_reply=create_admin_quick_reply())]
                )
            )
    elif text.startswith("ยืนยันลบ ") and event.source.user_id in admin_ids:
        # Handle "ยืนยันลบ ID" from quick reply button - actually delete the event
        try:
            event_id = int(text[len("ยืนยันลบ "):].strip())
            
            # Get event details before deleting
            get_response = supabase_client.table('events').select('*').eq('id', event_id).execute()
            
            if get_response.data and len(get_response.data) > 0:
                event_data = get_response.data[0]
                
                # Delete event from database
                delete_response = supabase_client.table('events').delete().eq('id', event_id).execute()
                
                if delete_response.data:
                    success_text = f"🗑️ ลบกิจกรรมเรียบร้อยแล้วครับ!\n\n📝 {event_data.get('event_title', '')}\n🆔 ID: {event_id}\n\n✅ การลบสำเร็จ"
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=success_text, quick_reply=create_admin_quick_reply())]
                        )
                    )
                else:
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=f"❌ ไม่สามารถลบกิจกรรม ID: {event_id} ได้", quick_reply=create_admin_quick_reply())]
                        )
                    )
            else:
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=f"❌ ไม่พบกิจกรรม ID: {event_id}", quick_reply=create_admin_quick_reply())]
                    )
                )
        except ValueError:
            safe_line_api_call(line_bot_api.reply_message,
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="ID ต้องเป็นตัวเลขเท่านั้นครับ", quick_reply=create_admin_quick_reply())]
                )
            )
        except Exception as e:
            app.logger.error(f"Error confirming delete: {e}")
            safe_line_api_call(line_bot_api.reply_message,
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="เกิดข้อผิดพลาดในการลบกิจกรรมครับ", quick_reply=create_admin_quick_reply())]
                )
            )
    else:
        user_id = event.source.user_id
        
        # Handle guided conversation flow for all users (admin and search)
        if user_id in user_states:
            state = user_states[user_id]
            
            # Search flow handlers (for all users)
            if state["step"] == "search_menu":
                selected_option = text.strip()
                
                if selected_option == "ค้นหาข้อความ":
                    state["step"] = "search_text_input"
                    state["search_type"] = "text"
                    
                    guide_text = """📝 ค้นหาจากชื่อ/รายละเอียด

🔸 **พิมพ์คำที่ต้องการค้นหา:**

ตัวอย่าง:
• บัตร
• ประชุม  
• แม่
• วันเกิด

💬 พิมพ์คำค้นแล้วส่งมา"""
                    
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=guide_text, quick_reply=create_cancel_quick_reply())]
                        )
                    )
                    return
                
                elif selected_option == "ค้นหาวันที่":
                    state["step"] = "search_date_input"
                    state["search_type"] = "date"
                    
                    guide_text = """📅 ค้นหาตามวันที่

🔸 **เลือกวันที่ที่ต้องการค้นหา:**

กดปุ่มด้านล่างเพื่อเลือกวันที่ หรือกด "📅 วันอื่น" แล้วพิมพ์ YYYY-MM-DD"""
                    
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=guide_text, quick_reply=create_date_quick_reply())]
                        )
                    )
                    return
                
                elif selected_option == "ค้นหาทั้งหมด":
                    state["step"] = "search_free_input"
                    state["search_type"] = "free"
                    
                    guide_text = """🔍 ค้นหาแบบอิสระ

💬 **พิมพ์คำค้นในรูปแบบใดก็ได้:**

📝 ค้นหาคำ: บัตร, ประชุม, แม่
📅 ค้นหาวันที่: วันนี้, พรุ่งนี้, เมื่อวาน
📅 หรือ: 2025-08-15, 2025-12-25
🔤 ค้นหาผสม: อะไรก็ได้

ระบบจะค้นหาในทุกส่วน (ชื่อ, รายละเอียด, วันที่)"""
                    
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=guide_text, quick_reply=create_cancel_quick_reply())]
                        )
                    )
                    return
                
                return
            
            elif state["step"] == "search_text_input":
                search_term = text.strip()
                del user_states[user_id]  # Clear state
                
                try:
                    # Search in title and description
                    response = supabase_client.table('events').select('*').or_(f"event_title.ilike.%{search_term}%,event_description.ilike.%{search_term}%").order('event_date', desc=False).execute()
                    events = response.data
                    
                    if events:
                        is_admin = user_id in admin_ids
                        total_events = len(events)
                        
                        if len(events) == 1:
                            flex_message = get_single_flex_message(events[0], is_admin)
                        elif total_events > 10:
                            flex_message = create_events_carousel_message(events, is_admin, 1)
                            total_pages = (total_events + 9) // 10
                            pagination_reply = create_pagination_quick_reply(1, total_pages, f"/search {search_term}")
                            status_text = f"🔍 ค้นหา '{search_term}' - หน้า 1/{total_pages} (พบ {total_events} รายการ)"
                            safe_line_api_call(line_bot_api.reply_message,
                                ReplyMessageRequest(
                                    reply_token=event.reply_token,
                                    messages=[flex_message, TextMessage(text=status_text, quick_reply=pagination_reply)]
                                )
                            )
                            return
                        else:
                            flex_message = create_events_carousel_message(events, is_admin)
                        
                        safe_line_api_call(line_bot_api.reply_message,
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[flex_message, TextMessage(text=f"🔍 ค้นหา '{search_term}' พบ {total_events} รายการ", quick_reply=create_main_quick_reply())]
                            )
                        )
                    else:
                        safe_line_api_call(line_bot_api.reply_message,
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(
                                    text=f"🔍 ไม่พบกิจกรรมที่ตรงกับ '{search_term}'",
                                    quick_reply=create_main_quick_reply()
                                )]
                            )
                        )
                except Exception as e:
                    app.logger.error(f"Error in guided text search: {e}")
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(
                                text="เกิดข้อผิดพลาดในการค้นหา กรุณาลองใหม่อีกครั้ง",
                                quick_reply=create_main_quick_reply()
                            )]
                        )
                    )
                return
            
            elif state["step"] == "search_date_input":
                selected_date = text.strip()
                
                # Handle "วันอื่น" case
                if selected_date == "วันอื่น":
                    guide_text = """📅 ระบุวันที่ค้นหา

พิมพ์วันที่ในรูปแบบ: **YYYY-MM-DD**

ตัวอย่าง:
• 2025-08-15
• 2025-09-01
• 2025-12-25

💬 พิมพ์วันที่แล้วส่งมา"""
                    
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=guide_text, quick_reply=create_cancel_quick_reply())]
                        )
                    )
                    return
                
                del user_states[user_id]  # Clear state
                
                # Handle Thai date keywords first
                actual_date = None
                if selected_date.lower() in ["วันนี้", "today"]:
                    actual_date = str(date.today())
                elif selected_date.lower() in ["พรุ่งนี้", "tomorrow"]:
                    actual_date = str(date.today() + timedelta(days=1))
                elif selected_date.lower() in ["เมื่อวาน", "yesterday"]:
                    actual_date = str(date.today() - timedelta(days=1))
                else:
                    # Validate date format
                    try:
                        parsed_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
                        actual_date = str(parsed_date)
                    except ValueError:
                        safe_line_api_call(line_bot_api.reply_message,
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text="❌ รูปแบบวันที่ไม่ถูกต้อง\n\nใช้ได้:\n• วันนี้, พรุ่งนี้, เมื่อวาน\n• หรือ YYYY-MM-DD (เช่น 2025-08-15)", quick_reply=create_main_quick_reply())]
                            )
                        )
                        return
                
                try:
                    response = supabase_client.table('events').select('*').eq('event_date', actual_date).execute()
                    events = response.data
                    
                    if events:
                        is_admin = user_id in admin_ids
                        total_events = len(events)
                        
                        if len(events) == 1:
                            flex_message = get_single_flex_message(events[0], is_admin)
                        else:
                            flex_message = create_events_carousel_message(events, is_admin)
                        
                        # Create friendly date display
                        if selected_date.lower() in ["วันนี้", "today"]:
                            date_display = f"วันนี้ ({format_thai_date(actual_date)})"
                        elif selected_date.lower() in ["พรุ่งนี้", "tomorrow"]:
                            date_display = f"พรุ่งนี้ ({format_thai_date(actual_date)})"
                        elif selected_date.lower() in ["เมื่อวาน", "yesterday"]:
                            date_display = f"เมื่อวาน ({format_thai_date(actual_date)})"
                        else:
                            date_display = format_thai_date(actual_date)
                        
                        safe_line_api_call(line_bot_api.reply_message,
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[flex_message, TextMessage(text=f"📅 {date_display} พบ {total_events} รายการ", quick_reply=create_main_quick_reply())]
                            )
                        )
                    else:
                        # Create friendly date display for no results
                        if selected_date.lower() in ["วันนี้", "today"]:
                            date_display = f"วันนี้ ({format_thai_date(actual_date)})"
                        elif selected_date.lower() in ["พรุ่งนี้", "tomorrow"]:
                            date_display = f"พรุ่งนี้ ({format_thai_date(actual_date)})"
                        elif selected_date.lower() in ["เมื่อวาน", "yesterday"]:
                            date_display = f"เมื่อวาน ({format_thai_date(actual_date)})"
                        else:
                            date_display = format_thai_date(actual_date)
                            
                        safe_line_api_call(line_bot_api.reply_message,
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(
                                    text=f"📅 ไม่พบกิจกรรมใน{date_display}",
                                    quick_reply=create_main_quick_reply()
                                )]
                            )
                        )
                except Exception as e:
                    app.logger.error(f"Error in guided date search: {e}")
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(
                                text="เกิดข้อผิดพลาดในการค้นหา กรุณาลองใหม่อีกครั้ง",
                                quick_reply=create_main_quick_reply()
                            )]
                        )
                    )
                return
            
            elif state["step"] == "search_free_input":
                search_term = text.strip()
                del user_states[user_id]  # Clear state
                
                try:
                    # Handle Thai date keywords first
                    actual_search_term = search_term
                    if search_term.lower() in ["วันนี้", "today"]:
                        actual_search_term = str(date.today())
                    elif search_term.lower() in ["พรุ่งนี้", "tomorrow"]:
                        actual_search_term = str(date.today() + timedelta(days=1))
                    elif search_term.lower() in ["เมื่อวาน", "yesterday"]:
                        actual_search_term = str(date.today() - timedelta(days=1))
                    
                    # Check if search term is a date (original or converted)
                    if re.match(r'\d{4}-\d{2}-\d{2}', actual_search_term):
                        response = supabase_client.table('events').select('*').eq('event_date', actual_search_term).execute()
                    else:
                        # Search in title and description
                        response = supabase_client.table('events').select('*').or_(f"event_title.ilike.%{actual_search_term}%,event_description.ilike.%{actual_search_term}%").order('event_date', desc=False).execute()
                    
                    events = response.data
                    
                    if events:
                        is_admin = user_id in admin_ids
                        total_events = len(events)
                        
                        if len(events) == 1:
                            flex_message = get_single_flex_message(events[0], is_admin)
                        elif total_events > 10:
                            flex_message = create_events_carousel_message(events, is_admin, 1)
                            total_pages = (total_events + 9) // 10
                            pagination_reply = create_pagination_quick_reply(1, total_pages, f"/search {search_term}")
                            status_text = f"🔍 ค้นหา '{search_term}' - หน้า 1/{total_pages} (พบ {total_events} รายการ)"
                            safe_line_api_call(line_bot_api.reply_message,
                                ReplyMessageRequest(
                                    reply_token=event.reply_token,
                                    messages=[flex_message, TextMessage(text=status_text, quick_reply=pagination_reply)]
                                )
                            )
                            return
                        else:
                            flex_message = create_events_carousel_message(events, is_admin)
                        
                        safe_line_api_call(line_bot_api.reply_message,
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[flex_message, TextMessage(text=f"🔍 ค้นหา '{search_term}' พบ {total_events} รายการ", quick_reply=create_main_quick_reply())]
                            )
                        )
                    else:
                        safe_line_api_call(line_bot_api.reply_message,
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(
                                    text=f"🔍 ไม่พบกิจกรรมที่ตรงกับ '{search_term}'",
                                    quick_reply=create_main_quick_reply()
                                )]
                            )
                        )
                except Exception as e:
                    app.logger.error(f"Error in guided free search: {e}")
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(
                                text="เกิดข้อผิดพลาดในการค้นหา กรุณาลองใหม่อีกครั้ง",
                                quick_reply=create_main_quick_reply()
                            )]
                        )
                    )
                return
            
            # Notification flow handlers (admin only)
            elif user_id in admin_ids and state["step"] == "notify_menu":
                selected_option = text.strip()
                
                if selected_option == "ข้อความกำหนดเอง":
                    state["step"] = "notify_custom_input"
                    
                    guide_text = """📝 ข้อความกำหนดเอง

🔸 **พิมพ์ข้อความที่ต้องการส่ง:**

ตัวอย่าง:
• 🔔 อย่าลืมกิจกรรมวันพรุ่งนี้นะครับ!
• ⚠️ เลื่องกิจกรรมประชุม เนื่องจากฝนตก
• 🎉 ขอเชิญร่วมกิจกรรมวันแม่ วันอาทิตย์นี้

💬 พิมพ์ข้อความแล้วส่งมา (จะส่งให้ผู้สมัครทุกคน)"""
                    
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=guide_text, quick_reply=create_cancel_quick_reply())]
                        )
                    )
                    return
                
                elif selected_option == "แจ้งกิจกรรมถัดไป":
                    # Get next upcoming event
                    try:
                        today = date.today()
                        response = supabase_client.table('events').select('*').gte('event_date', str(today)).order('event_date', desc=False).limit(1).execute()
                        
                        if response.data and len(response.data) > 0:
                            event_data = response.data[0]
                            formatted_date = format_thai_date(event_data.get('event_date', ''))
                            
                            notification_message = f"""🔔 แจ้งเตือนกิจกرรม

📝 **{event_data.get('event_title', '')}**
📋 {event_data.get('event_description', '')}
📅 **วันที่:** {formatted_date}

📲 ส่งจาก: ระบบแจ้งเตือนกิจกรรม"""
                            
                            # Send to all subscribers
                            subscribers_response = supabase_client.table('subscribers').select('user_id').execute()
                            if subscribers_response.data:
                                sent_count = 0
                                failed_count = 0
                                
                                for subscriber in subscribers_response.data:
                                    try:
                                        safe_line_api_call(line_bot_api.push_message,
                                            PushMessageRequest(
                                                to=subscriber['user_id'],
                                                messages=[TextMessage(text=notification_message)]
                                            )
                                        )
                                        sent_count += 1
                                    except Exception as e:
                                        app.logger.error(f"Failed to send notification to {subscriber['user_id']}: {e}")
                                        failed_count += 1
                                
                                success_message = f"""📢 ส่งแจ้งเตือนสำเร็จ!

📝 **กิจกรรม:** {event_data.get('event_title', '')}
✅ **ส่งสำเร็จ:** {sent_count} คน
❌ **ส่งไม่สำเร็จ:** {failed_count} คน

📊 **รวม:** {sent_count + failed_count} คน"""
                                
                                safe_line_api_call(line_bot_api.reply_message,
                                    ReplyMessageRequest(
                                        reply_token=event.reply_token,
                                        messages=[TextMessage(text=success_message, quick_reply=create_admin_quick_reply())]
                                    )
                                )
                            else:
                                safe_line_api_call(line_bot_api.reply_message,
                                    ReplyMessageRequest(
                                        reply_token=event.reply_token,
                                        messages=[TextMessage(text="❌ ไม่มีผู้สมัครรับแจ้งเตือน", quick_reply=create_admin_quick_reply())]
                                    )
                                )
                        else:
                            safe_line_api_call(line_bot_api.reply_message,
                                ReplyMessageRequest(
                                    reply_token=event.reply_token,
                                    messages=[TextMessage(text="❌ ไม่มีกิจกรรมถัดไปที่จะแจ้งเตือน", quick_reply=create_admin_quick_reply())]
                                )
                            )
                        
                        del user_states[user_id]
                        return
                        
                    except Exception as e:
                        app.logger.error(f"Error sending event notification: {e}")
                        safe_line_api_call(line_bot_api.reply_message,
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text="❌ เกิดข้อผิดพลาดในการส่งแจ้งเตือน", quick_reply=create_admin_quick_reply())]
                            )
                        )
                        del user_states[user_id]
                        return
                
                elif selected_option == "ทดสอบแจ้งเตือนอัตโนมัติ":
                    # Test automatic notification system
                    del user_states[user_id]
                    
                    try:
                        result = send_automatic_notifications()
                        
                        if result["status"] == "success":
                            success_message = f"""🤖 ทดสอบแจ้งเตือนอัตโนมัติสำเร็จ!

📊 **ผลการส่ง:**
✅ ส่งแจ้งเตือนได้: {result['notifications_sent']} ข้อความ
📅 กิจกรรมวันนี้: {result['events_today']} รายการ
📅 กิจกรรมพรุ่งนี้: {result['events_tomorrow']} รายการ  
👥 ผู้สมัครทั้งหมด: {result['subscribers']} คน

💡 **หมายเหตุ:** ระบบจะแจ้งเตือนอัตโนมัติเมื่อ:
• มีกิจกรรมในวันนี้ (เตือนเวลา 06:00 น.)
• มีกิจกรรมพรุ่งนี้ (เตือนเวลา 18:00 น.)

🔗 **URL สำหรับ Scheduler:**
https://notibot-1234.onrender.com/send-notifications"""
                            
                        elif result["status"] == "no_subscribers":
                            success_message = """🤖 ทดสอบแจ้งเตือนอัตโนมัติ

❌ **ไม่มีผู้สมัครรับแจ้งเตือน**

💡 ผู้ใช้สามารถสมัครได้โดยกดปุ่ม "🔔 สมัครแจ้งเตือน" ในเมนูหลัก"""
                            
                        else:
                            success_message = f"""🤖 ทดสอบแจ้งเตือนอัตโนมัติ

❌ **เกิดข้อผิดพลาด:** {result.get('message', 'Unknown error')}

กรุณาตรวจสอบ logs สำหรับรายละเอียดเพิ่มเติม"""
                        
                        safe_line_api_call(line_bot_api.reply_message,
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=success_message, quick_reply=create_admin_quick_reply())]
                            )
                        )
                        return
                        
                    except Exception as e:
                        app.logger.error(f"Error testing automatic notifications: {e}")
                        safe_line_api_call(line_bot_api.reply_message,
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text="❌ เกิดข้อผิดพลาดในการทดสอบระบบแจ้งเตือนอัตโนมัติ", quick_reply=create_admin_quick_reply())]
                            )
                        )
                        return
                
                elif selected_option == "ดูสถิติผู้สมัคร":
                    try:
                        # Get subscriber statistics
                        subscribers_response = supabase_client.table('subscribers').select('user_id').execute()
                        subscriber_count = len(subscribers_response.data) if subscribers_response.data else 0
                        
                        # Get total events
                        events_response = supabase_client.table('events').select('id').execute()
                        total_events = len(events_response.data) if events_response.data else 0
                        
                        # Get upcoming events
                        today = date.today()
                        upcoming_response = supabase_client.table('events').select('id').gte('event_date', str(today)).execute()
                        upcoming_events = len(upcoming_response.data) if upcoming_response.data else 0
                        
                        stats_text = f"""📊 สถิติระบบแจ้งเตือน

👥 **ผู้สมัครรับแจ้งเตือน:** {subscriber_count} คน
📋 **กิจกรรมทั้งหมด:** {total_events} รายการ
📅 **กิจกรรมถัดไป:** {upcoming_events} รายการ

💡 **การใช้งาน:**
• ผู้ใช้สามารถกดปุ่ม "🔔 สมัครแจ้งเตือน" เพื่อสมัคร
• Admin สามารถส่งแจ้งเตือนผ่านเมนูนี้
• ระบบจะส่งข้อความไปหาผู้สมัครทุกคน"""
                        
                        safe_line_api_call(line_bot_api.reply_message,
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=stats_text, quick_reply=create_admin_quick_reply())]
                            )
                        )
                        
                        del user_states[user_id]
                        return
                        
                    except Exception as e:
                        app.logger.error(f"Error getting subscriber stats: {e}")
                        safe_line_api_call(line_bot_api.reply_message,
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text="❌ เกิดข้อผิดพลาดในการดึงสถิติ", quick_reply=create_admin_quick_reply())]
                            )
                        )
                        del user_states[user_id]
                        return
                
                return
            
            elif user_id in admin_ids and state["step"] == "notify_custom_input":
                custom_message = text.strip()
                del user_states[user_id]
                
                try:
                    # Send custom message to all subscribers
                    subscribers_response = supabase_client.table('subscribers').select('user_id').execute()
                    
                    if subscribers_response.data:
                        sent_count = 0
                        failed_count = 0
                        
                        notification_text = f"""📢 {custom_message}

📲 ส่งจาก: ระบบแจ้งเตือนกิจกรรม"""
                        
                        for subscriber in subscribers_response.data:
                            try:
                                safe_line_api_call(line_bot_api.push_message,
                                    PushMessageRequest(
                                        to=subscriber['user_id'],
                                        messages=[TextMessage(text=notification_text)]
                                    )
                                )
                                sent_count += 1
                            except Exception as e:
                                app.logger.error(f"Failed to send custom notification to {subscriber['user_id']}: {e}")
                                failed_count += 1
                        
                        success_message = f"""📢 ส่งข้อความกำหนดเองสำเร็จ!

💬 **ข้อความ:** {custom_message}
✅ **ส่งสำเร็จ:** {sent_count} คน
❌ **ส่งไม่สำเร็จ:** {failed_count} คน

📊 **รวม:** {sent_count + failed_count} คน"""
                        
                        safe_line_api_call(line_bot_api.reply_message,
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=success_message, quick_reply=create_admin_quick_reply())]
                            )
                        )
                    else:
                        safe_line_api_call(line_bot_api.reply_message,
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text="❌ ไม่มีผู้สมัครรับแจ้งเตือน", quick_reply=create_admin_quick_reply())]
                            )
                        )
                    
                    return
                    
                except Exception as e:
                    app.logger.error(f"Error sending custom notification: {e}")
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="❌ เกิดข้อผิดพลาดในการส่งข้อความ", quick_reply=create_admin_quick_reply())]
                        )
                    )
                    return
            
            # Admin-only flows
            elif user_id in admin_ids and state["step"] == "waiting_title":
                # Save title and ask for description
                state["event_data"]["title"] = text.strip()
                state["step"] = "waiting_description"
                
                guide_text = f"""📝 เพิ่มกิจกรรม - ขั้นตอน 2/3

✅ ชื่อ: {text.strip()}

🔸 **ส่งรายละเอียดกิจกรรม**

ตัวอย่าง:
• ผกก. อยู่ในกระเป๋าปืน
• หารือแผนงาน Q1 
• เวลา 08.30 น. มอบ มหาราช 2 มหาราช 5

💬 แค่พิมพ์รายละเอียดแล้วส่งมา"""
                
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=guide_text, quick_reply=create_cancel_quick_reply())]
                    )
                )
                return
                
            elif state["step"] == "waiting_description":
                # Save description and ask for date
                state["event_data"]["description"] = text.strip()
                state["step"] = "waiting_date"
                
                guide_text = f"""📝 เพิ่มกิจกรรม - ขั้นตอน 3/3

✅ ชื่อ: {state["event_data"]["title"]}
✅ รายละเอียด: {text.strip()}

🔸 **เลือกวันที่กิจกรรม**

กดปุ่มด้านล่างเพื่อเลือกวันที่ หรือกด "📅 วันอื่น" แล้วพิมพ์ YYYY-MM-DD"""
                
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=guide_text, quick_reply=create_date_quick_reply())]
                    )
                )
                return
                
            elif state["step"] == "waiting_date":
                selected_date = text.strip()
                
                # Handle "วันอื่น" case
                if selected_date == "วันอื่น":
                    guide_text = """📅 ระบุวันที่

พิมพ์วันที่ในรูปแบบ: **YYYY-MM-DD**

ตัวอย่าง:
• 2025-08-15
• 2025-09-01
• 2025-12-25

💬 พิมพ์วันที่แล้วส่งมา"""
                    
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=guide_text, quick_reply=create_cancel_quick_reply())]
                        )
                    )
                    return
                
                # Validate date format
                try:
                    event_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
                except ValueError:
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="❌ รูปแบบวันที่ไม่ถูกต้อง กรุณาใช้ YYYY-MM-DD", quick_reply=create_cancel_quick_reply())]
                        )
                    )
                    return
                
                # Create event
                try:
                    response = supabase_client.table('events').insert({
                        'event_title': state["event_data"]["title"],
                        'event_description': state["event_data"]["description"],
                        'event_date': str(event_date),
                        'created_by': user_id
                    }).execute()
                    
                    if response.data and len(response.data) > 0:
                        event_id = response.data[0]['id']
                        success_text = f"""🎉 เพิ่มกิจกรรมสำเร็จ!

🆔 ID: {event_id}
📝 {state["event_data"]["title"]}
📋 {state["event_data"]["description"]}
📅 {format_thai_date(str(event_date))}

✅ บันทึกลงฐานข้อมูลแล้ว"""
                        
                        safe_line_api_call(line_bot_api.reply_message,
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=success_text, quick_reply=create_admin_quick_reply())]
                            )
                        )
                    else:
                        safe_line_api_call(line_bot_api.reply_message,
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text="❌ เกิดข้อผิดพลาดในการบันทึก", quick_reply=create_admin_quick_reply())]
                            )
                        )
                    
                    # Clear user state
                    del user_states[user_id]
                    return
                    
                except Exception as e:
                    app.logger.error(f"Error creating event via guided flow: {e}")
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="❌ เกิดข้อผิดพลาดในการบันทึกกิจกรรม", quick_reply=create_admin_quick_reply())]
                        )
                    )
                    del user_states[user_id]
                    return
            
            # Edit menu handler
            elif state["step"] == "edit_menu":
                selected_option = text.strip()
                
                if selected_option == "แก้ชื่อ":
                    state["step"] = "edit_title_only"
                    state["edit_mode"] = "title_only"
                    
                    guide_text = f"""📝 แก้ไขชื่อกิจกรรม

**ปัจจุบัน:** {state["current_data"].get('event_title', '')}

🔸 **ส่งชื่อใหม่:**

💬 พิมพ์ชื่อใหม่แล้วส่งมา"""
                    
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=guide_text, quick_reply=create_cancel_quick_reply())]
                        )
                    )
                    return
                
                elif selected_option == "แก้รายละเอียด":
                    state["step"] = "edit_description_only"
                    state["edit_mode"] = "description_only"
                    
                    guide_text = f"""📋 แก้ไขรายละเอียดกิจกรรม

**ปัจจุบัน:** {state["current_data"].get('event_description', '')}

🔸 **ส่งรายละเอียดใหม่:**

💬 พิมพ์รายละเอียดใหม่แล้วส่งมา"""
                    
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=guide_text, quick_reply=create_cancel_quick_reply())]
                        )
                    )
                    return
                
                elif selected_option == "แก้วันที่":
                    state["step"] = "edit_date_only"
                    state["edit_mode"] = "date_only"
                    
                    current_date_str = state["current_data"].get('event_date', '')
                    
                    guide_text = f"""📅 แก้ไขวันที่กิจกรรม

**ปัจจุบัน:** {format_thai_date(current_date_str)}

🔸 **เลือกวันที่ใหม่:**

กดปุ่มด้านล่างเพื่อเลือกวันที่ใหม่"""
                    
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=guide_text, quick_reply=create_date_quick_reply())]
                        )
                    )
                    return
                
                elif selected_option == "แก้ทั้งหมด":
                    state["step"] = "edit_waiting_title"
                    state["edit_mode"] = "full_edit"
                    
                    guide_text = f"""✏️ แก้ไขกิจกรรม - ขั้นตอน 1/3

📝 **ปัจจุบัน:** {state["current_data"].get('event_title', '')}

🔸 **ส่งชื่อใหม่** หรือส่ง "เหมือนเดิม" เพื่อข้าม

💬 แค่พิมพ์ชื่อใหม่แล้วส่งมา"""
                    
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=guide_text, quick_reply=create_cancel_quick_reply())]
                        )
                    )
                    return
                
                return
            
            # Single field edit handlers
            elif state["step"] == "edit_title_only":
                new_title = text.strip()
                
                try:
                    response = supabase_client.table('events').update({
                        'event_title': new_title
                    }).eq('id', state["event_id"]).execute()
                    
                    if response.data and len(response.data) > 0:
                        success_text = f"""🎉 แก้ไขชื่อสำเร็จ!

🆔 ID: {state["event_id"]}
📝 **ชื่อใหม่:** {new_title}
📋 รายละเอียด: {state["current_data"].get('event_description', '')}
📅 วันที่: {format_thai_date(state["current_data"].get('event_date', ''))}

✅ อัปเดตในฐานข้อมูลแล้ว"""
                        
                        safe_line_api_call(line_bot_api.reply_message,
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=success_text, quick_reply=create_admin_quick_reply())]
                            )
                        )
                    else:
                        safe_line_api_call(line_bot_api.reply_message,
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text="❌ ไม่สามารถแก้ไขได้", quick_reply=create_admin_quick_reply())]
                            )
                        )
                    
                    del user_states[user_id]
                    return
                
                except Exception as e:
                    app.logger.error(f"Error editing title only: {e}")
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="❌ เกิดข้อผิดพลาดในการแก้ไขชื่อ", quick_reply=create_admin_quick_reply())]
                        )
                    )
                    del user_states[user_id]
                    return
            
            elif state["step"] == "edit_description_only":
                new_description = text.strip()
                
                try:
                    response = supabase_client.table('events').update({
                        'event_description': new_description
                    }).eq('id', state["event_id"]).execute()
                    
                    if response.data and len(response.data) > 0:
                        success_text = f"""🎉 แก้ไขรายละเอียดสำเร็จ!

🆔 ID: {state["event_id"]}
📝 ชื่อ: {state["current_data"].get('event_title', '')}
📋 **รายละเอียดใหม่:** {new_description}
📅 วันที่: {format_thai_date(state["current_data"].get('event_date', ''))}

✅ อัปเดตในฐานข้อมูลแล้ว"""
                        
                        safe_line_api_call(line_bot_api.reply_message,
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=success_text, quick_reply=create_admin_quick_reply())]
                            )
                        )
                    else:
                        safe_line_api_call(line_bot_api.reply_message,
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text="❌ ไม่สามารถแก้ไขได้", quick_reply=create_admin_quick_reply())]
                            )
                        )
                    
                    del user_states[user_id]
                    return
                
                except Exception as e:
                    app.logger.error(f"Error editing description only: {e}")
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="❌ เกิดข้อผิดพลาดในการแก้ไขรายละเอียด", quick_reply=create_admin_quick_reply())]
                        )
                    )
                    del user_states[user_id]
                    return
            
            elif state["step"] == "edit_date_only":
                selected_date = text.strip()
                
                # Handle "วันอื่น" case
                if selected_date == "วันอื่น":
                    guide_text = """📅 ระบุวันที่ใหม่

พิมพ์วันที่ในรูปแบบ: **YYYY-MM-DD**

ตัวอย่าง:
• 2025-08-15
• 2025-09-01
• 2025-12-25

💬 พิมพ์วันที่แล้วส่งมา"""
                    
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=guide_text, quick_reply=create_cancel_quick_reply())]
                        )
                    )
                    return
                
                # Validate date format
                try:
                    event_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
                    event_date_str = str(event_date)
                except ValueError:
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="❌ รูปแบบวันที่ไม่ถูกต้อง กรุณาใช้ YYYY-MM-DD", quick_reply=create_cancel_quick_reply())]
                        )
                    )
                    return
                
                try:
                    response = supabase_client.table('events').update({
                        'event_date': event_date_str
                    }).eq('id', state["event_id"]).execute()
                    
                    if response.data and len(response.data) > 0:
                        success_text = f"""🎉 แก้ไขวันที่สำเร็จ!

🆔 ID: {state["event_id"]}
📝 ชื่อ: {state["current_data"].get('event_title', '')}
📋 รายละเอียด: {state["current_data"].get('event_description', '')}
📅 **วันที่ใหม่:** {format_thai_date(event_date_str)}

✅ อัปเดตในฐานข้อมูลแล้ว"""
                        
                        safe_line_api_call(line_bot_api.reply_message,
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=success_text, quick_reply=create_admin_quick_reply())]
                            )
                        )
                    else:
                        safe_line_api_call(line_bot_api.reply_message,
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text="❌ ไม่สามารถแก้ไขได้", quick_reply=create_admin_quick_reply())]
                            )
                        )
                    
                    del user_states[user_id]
                    return
                
                except Exception as e:
                    app.logger.error(f"Error editing date only: {e}")
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="❌ เกิดข้อผิดพลาดในการแก้ไขวันที่", quick_reply=create_admin_quick_reply())]
                        )
                    )
                    del user_states[user_id]
                    return

            # Full edit flow handlers (original 3-step process)
            elif state["step"] == "edit_waiting_title":
                new_title = text.strip() if text.strip() != "เหมือนเดิม" else state["current_data"]["event_title"]
                state["event_data"]["title"] = new_title
                state["step"] = "edit_waiting_description"
                
                guide_text = f"""✏️ แก้ไขกิจกรรม - ขั้นตอน 2/3

✅ ชื่อ: {new_title}

📋 **ปัจจุบัน:** {state["current_data"].get('event_description', '')}

🔸 **ส่งรายละเอียดใหม่** หรือส่ง "เหมือนเดิม" เพื่อข้าม

💬 แค่พิมพ์รายละเอียดใหม่แล้วส่งมา"""
                
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=guide_text, quick_reply=create_cancel_quick_reply())]
                    )
                )
                return
                
            elif state["step"] == "edit_waiting_description":
                new_description = text.strip() if text.strip() != "เหมือนเดิม" else state["current_data"]["event_description"]
                state["event_data"]["description"] = new_description
                state["step"] = "edit_waiting_date"
                
                # Add current date as first option
                current_date_str = state["current_data"].get('event_date', '')
                same_date_button = QuickReplyItem(action=MessageAction(label="📅 วันเดิม", text="เหมือนเดิม"))
                
                date_buttons = create_date_quick_reply()
                date_buttons.items.insert(0, same_date_button)
                
                guide_text = f"""✏️ แก้ไขกิจกรรม - ขั้นตอน 3/3

✅ ชื่อ: {state["event_data"]["title"]}
✅ รายละเอียด: {new_description}

📅 **ปัจจุบัน:** {format_thai_date(current_date_str)}

🔸 **เลือกวันที่ใหม่** หรือกด "📅 วันเดิม" เพื่อใช้วันเดิม

กดปุ่มด้านล่างเพื่อเลือกวันที่"""
                
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=guide_text, quick_reply=date_buttons)]
                    )
                )
                return
                
            elif state["step"] == "edit_waiting_date":
                selected_date = text.strip()
                
                if selected_date == "เหมือนเดิม":
                    event_date_str = state["current_data"]["event_date"]
                elif selected_date == "วันอื่น":
                    guide_text = """📅 ระบุวันที่ใหม่

พิมพ์วันที่ในรูปแบบ: **YYYY-MM-DD**

ตัวอย่าง:
• 2025-08-15
• 2025-09-01
• 2025-12-25

💬 พิมพ์วันที่แล้วส่งมา"""
                    
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=guide_text, quick_reply=create_cancel_quick_reply())]
                        )
                    )
                    return
                else:
                    # Validate date format
                    try:
                        event_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
                        event_date_str = str(event_date)
                    except ValueError:
                        safe_line_api_call(line_bot_api.reply_message,
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text="❌ รูปแบบวันที่ไม่ถูกต้อง กรุณาใช้ YYYY-MM-DD", quick_reply=create_cancel_quick_reply())]
                            )
                        )
                        return
                
                # Update event
                try:
                    response = supabase_client.table('events').update({
                        'event_title': state["event_data"]["title"],
                        'event_description': state["event_data"]["description"],
                        'event_date': event_date_str
                    }).eq('id', state["event_id"]).execute()
                    
                    if response.data and len(response.data) > 0:
                        success_text = f"""🎉 แก้ไขกิจกรรมสำเร็จ!

🆔 ID: {state["event_id"]}
📝 {state["event_data"]["title"]}
📋 {state["event_data"]["description"]}
📅 {format_thai_date(event_date_str)}

✅ อัปเดตในฐานข้อมูลแล้ว"""
                        
                        safe_line_api_call(line_bot_api.reply_message,
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text=success_text, quick_reply=create_admin_quick_reply())]
                            )
                        )
                    else:
                        safe_line_api_call(line_bot_api.reply_message,
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text="❌ ไม่สามารถแก้ไขกิจกรรมได้", quick_reply=create_admin_quick_reply())]
                            )
                        )
                    
                    del user_states[user_id]
                    return
                    
                except Exception as e:
                    app.logger.error(f"Error editing event via guided flow: {e}")
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="❌ เกิดข้อผิดพลาดในการแก้ไขกิจกรรม", quick_reply=create_admin_quick_reply())]
                        )
                    )
                    del user_states[user_id]
                    return
        
        # Handle cancel during guided flow (for all users)
        if user_id in user_states and text in ["สวัสดี", "ยกเลิก"]:
            current_step = user_states[user_id].get("step", "")
            del user_states[user_id]
            
            # Different cancel messages based on user type and action
            if user_id in admin_ids and current_step.startswith(("waiting_", "edit_")):
                cancel_msg = "❌ ยกเลิกการดำเนินการแล้ว"
                quick_reply = create_admin_quick_reply()
            else:
                cancel_msg = "❌ ยกเลิกการค้นหาแล้ว"
                quick_reply = create_main_quick_reply()
            
            safe_line_api_call(line_bot_api.reply_message,
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=cancel_msg, quick_reply=quick_reply)]
                )
            )
            return
        
        # Handle /notify command for quick notifications
        if text.startswith("/notify ") and user_id in admin_ids:
            custom_message = text[len("/notify "):].strip()
            
            try:
                # Send message to all subscribers
                subscribers_response = supabase_client.table('subscribers').select('user_id').execute()
                
                if subscribers_response.data:
                    sent_count = 0
                    failed_count = 0
                    
                    notification_text = f"""📢 {custom_message}

📲 ส่งจาก: ระบบแจ้งเตือนกิจกรรม"""
                    
                    for subscriber in subscribers_response.data:
                        try:
                            safe_line_api_call(line_bot_api.push_message,
                                PushMessageRequest(
                                    to=subscriber['user_id'],
                                    messages=[TextMessage(text=notification_text)]
                                )
                            )
                            sent_count += 1
                        except Exception as e:
                            app.logger.error(f"Failed to send notification via command to {subscriber['user_id']}: {e}")
                            failed_count += 1
                    
                    success_message = f"""📢 ส่งข้อความสำเร็จ!

💬 **ข้อความ:** {custom_message}
✅ **ส่งสำเร็จ:** {sent_count} คน
❌ **ส่งไม่สำเร็จ:** {failed_count} คน

📊 **รวม:** {sent_count + failed_count} คน"""
                    
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=success_message, quick_reply=create_admin_quick_reply())]
                        )
                    )
                else:
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="❌ ไม่มีผู้สมัครรับแจ้งเตือน", quick_reply=create_admin_quick_reply())]
                        )
                    )
            except Exception as e:
                app.logger.error(f"Error sending notification via command: {e}")
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="❌ เกิดข้อผิดพลาดในการส่งข้อความ", quick_reply=create_admin_quick_reply())]
                    )
                )
            return
        
        # ตรวจสอบว่าเป็น Admin และส่งข้อความแบบ "ชื่อ | รายละเอียด | วันที่" หรือไม่
        elif user_id in admin_ids and ' | ' in text and len(text.split(' | ')) == 3:
            parts = text.split(' | ')
            event_title = parts[0].strip()
            event_description = parts[1].strip()
            event_date_str = parts[2].strip()
            
            try:
                event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
            except ValueError:
                safe_line_api_call(line_bot_api.reply_message,
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
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text=success_text, quick_reply=create_admin_quick_reply())]
                        )
                    )
                else:
                    safe_line_api_call(line_bot_api.reply_message,
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="เกิดข้อผิดพลาดในการบันทึกกิจกรรมครับ", quick_reply=create_admin_quick_reply())]
                        )
                    )
            except Exception as e:
                app.logger.error(f"Error adding event via simple format: {e}")
                safe_line_api_call(line_bot_api.reply_message,
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="เกิดข้อผิดพลาดในการบันทึกกิจกรรมครับ", quick_reply=create_admin_quick_reply())]
                    )
                )
    
    # ==================== CONTACT MANAGEMENT COMMANDS ====================
    
    # Handle show all contacts in Thai FIRST (before conversion)
    if text.lower() in ["เบอร์ทั้งหมด", "ทั้งหมด", "ดูทั้งหมด", "รายการทั้งหมด"]:
        contacts = get_all_contacts()
        if not contacts:
            msg = "📭 ยังไม่มีเบอร์โทรในสมุด\n\n💡 เริ่มเพิ่มเบอร์แรกกันเลย!"
            quick_reply = create_contact_quick_reply()
        else:
            msg = f"📋 สมุดเบอร์โทร ({len(contacts)} คน)\n\n"
            for i, contact in enumerate(contacts[:20], 1):
                msg += f"{i}. {contact['name']} - {contact['phone_number']}\n"
            if len(contacts) > 20:
                msg += f"\n... และอีก {len(contacts) - 20} คน"
            msg += "\n\n💡 ลองค้นหาคนที่ต้องการดู"
            quick_reply = create_contact_quick_reply()
        
        safe_line_api_call(line_bot_api.reply_message,
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=msg, quick_reply=quick_reply)]
            )
        )
        return
    
    # Check for Thai natural language conversion
    converted_command = convert_thai_to_english_command(text)
    
    # Check for incomplete commands and provide help
    incomplete = detect_incomplete_command(converted_command)
    if incomplete:
        from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
        quick_reply = QuickReply(items=[
            QuickReplyItem(action=MessageAction(label=f"💡 {suggestion[:20]}", text=suggestion))
            for suggestion in incomplete["suggestions"][:10]
        ])
        safe_line_api_call(line_bot_api.reply_message,
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=incomplete["message"], quick_reply=quick_reply)]
            )
        )
        return
    
    # Handle English commands (old format)
    elif text.startswith("add_phone "):
        data = text.replace("add_phone ", "")
        user_id = event.source.user_id
        handle_add_contact_simple(data, event, user_id)
    
    elif text.startswith("search_phone "):
        query = text.replace("search_phone ", "")
        handle_search_contact_simple(query, event)
    
    # Handle Thai commands (new format)
    elif converted_command.startswith("add_phone "):
        data = converted_command.replace("add_phone ", "")
        user_id = event.source.user_id
        handle_add_contact_simple(data, event, user_id)
    
    elif converted_command.startswith("search_phone "):
        query = converted_command.replace("search_phone ", "")
        handle_search_contact_simple(query, event)
    
    # Handle help command in Thai
    elif text.lower() in ["วิธีใช้เบอร์", "ช่วยเหลือเบอร์", "help เบอร์"]:
        help_text = """📞 วิธีใช้งานสมุดเบอร์โทร

🎯 **วิธีง่ายๆ ที่เข้าใจได้:**

📝 **เพิ่มเบอร์:**
• เพิ่มเบอร์ สมชาย 081-234-5678
• บันทึกเบอร์ นางสาวดาว 089-999-8888
• add_phone คุณแม่ 02-123-4567

🔍 **หาเบอร์:**
• หาเบอร์ สมชาย
• ค้นหา 081
• search_phone ดาว

💡 **เทคนิค:**
• พิมพ์แค่บางส่วนก็ได้
• ค้นหาได้หลายคำพร้อมกัน
• ใช้ได้ทั้งภาษาไทยและอังกฤษ

🎮 **กดปุ่มด่วน:**
ใช้ปุ่มด้านล่างได้เลย!"""
        
        safe_line_api_call(line_bot_api.reply_message,
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=help_text, quick_reply=create_contact_quick_reply())]
            )
        )
    
    # Handle admin contact commands (disabled - function not implemented)
    # elif handle_admin_commands(text, event, line_bot_api, admin_ids, create_admin_quick_reply):
    #     pass  # Command was handled by handle_admin_commands
    
    # ==================== END CONTACT MANAGEMENT ====================
    
    else:
        safe_line_api_call(line_bot_api.reply_message,
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=f"คุณพูดว่า: {text}\n\nลองใช้เมนูด้านล่างเพื่อดูกิจกรรมครับ\n\n📞 **คำสั่งเบอร์โทรใหม่:**\n• เพิ่มเบอร์ ชื่อ เบอร์ - เพิ่มเบอร์\n• หาเบอร์ คำค้นหา - หาเบอร์\n• เบอร์ทั้งหมด - ดูทั้งหมด\n• วิธีใช้เบอร์ - วิธีใช้งาน\n\n💡 **คำสั่งเดิม:**\n• add_phone, search_phone ยังใช้ได้", quick_reply=create_main_quick_reply())]
            )
        )

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
