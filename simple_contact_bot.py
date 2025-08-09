# -*- coding: utf-8 -*-
"""
Simple Contact Bot - ใช้งานง่ายที่สุด
เพียงแค่พิมพ์ภาษาไทยธรรมดา
"""

from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest,
    TextMessage, FlexMessage, FlexContainer, QuickReply, QuickReplyItem,
    MessageAction
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
import os
from dotenv import load_dotenv
from contact_management import (
    add_contact, search_contacts_multi_keyword, create_contact_flex_message
)
from easy_commands import convert_thai_to_english_command, create_help_message, create_thai_contact_menu
from smart_helper import detect_incomplete_command, analyze_user_intent, format_error_message

load_dotenv()

app = Flask(__name__)

# Initialize LINE Bot
configuration = Configuration(access_token=os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))
line_bot_api = MessagingApi(ApiClient(configuration))

@app.route("/", methods=['GET'])
def home():
    return "Simple Contact Bot is ready! 🤖📞"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_simple_message(event):
    text = event.message.text.strip()
    user_id = event.source.user_id
    
    # Welcome messages
    if text.lower() in ["สวัสดี", "hello", "hi", "start"]:
        welcome_msg = """🤖 สวัสดีครับ! ยินดีต้อนรับสู่สมุดเบอร์โทร

📞 **ใช้งานง่ายมาก:**
• เพิ่มเบอร์ ชื่อ เบอร์โทร
• หาเบอร์ ชื่อหรือเบอร์

🎯 **ตัวอย่าง:**
• เพิ่มเบอร์ สมชาย 081-234-5678  
• หาเบอร์ สมชาย
• หาเบอร์ 081

กดปุ่มด้านล่างได้เลย! 👇"""
        
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=welcome_msg, quick_reply=create_thai_contact_menu())]
            )
        )
        return
    
    # Help command
    if text.lower() in ["วิธีใช้เบอร์", "ช่วย", "help"]:
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=create_help_message(), quick_reply=create_thai_contact_menu())]
            )
        )
        return
    
    # Convert Thai natural language to English commands
    converted_command = convert_thai_to_english_command(text)
    
    # Check for incomplete commands
    incomplete = detect_incomplete_command(converted_command)
    if incomplete:
        quick_reply = QuickReply(items=[
            QuickReplyItem(action=MessageAction(label=f"💡 {suggestion[:20]}", text=suggestion))
            for suggestion in incomplete["suggestions"]
        ])
        
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=incomplete["message"], quick_reply=quick_reply)]
            )
        )
        return
    
    # Handle add contact
    if converted_command.startswith("add_phone "):
        handle_add_simple(converted_command.replace("add_phone ", ""), event, user_id)
        return
    
    # Handle search contact  
    if converted_command.startswith("search_phone "):
        handle_search_simple(converted_command.replace("search_phone ", ""), event)
        return
    
    # Show all contacts (simple version)
    if text.lower() in ["เบอร์ทั้งหมด", "ทั้งหมด", "ดูทั้งหมด"]:
        handle_list_simple(event)
        return
    
    # Default response with suggestions
    intent = analyze_user_intent(text)
    
    if intent["context"] == "contact":
        suggestion_msg = """🤔 ไม่เข้าใจคำสั่งนี้

💡 **ลองใช้รูปแบบนี้:**
• เพิ่มเบอร์ ชื่อ เบอร์โทร
• หาเบอร์ คำค้นหา

🎯 **หรือกดปุ่มด้านล่าง**"""
        
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=suggestion_msg, quick_reply=create_thai_contact_menu())]
            )
        )
    else:
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="พิมพ์ 'สวัสดี' เพื่อเริ่มใช้งานสมุดเบอร์โทรนะ 📞")]
            )
        )

def handle_add_simple(data, event, user_id):
    """Handle add contact with simple interface"""
    parts = data.strip().split()
    
    if len(parts) < 2:
        error_msg = format_error_message("missing_name")
        quick_reply = QuickReply(items=[
            QuickReplyItem(action=MessageAction(label="💡 เพิ่มเบอร์ สมชาย 081-234-5678", text="เพิ่มเบอร์ สมชาย 081-234-5678")),
            QuickReplyItem(action=MessageAction(label="💡 เพิ่มเบอร์ ดาว 089-999-8888", text="เพิ่มเบอร์ ดาว 089-999-8888"))
        ])
        
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=error_msg, quick_reply=quick_reply)]
            )
        )
        return
    
    name = parts[0]
    phone = parts[1]
    
    result = add_contact(name, phone, user_id)
    
    if result["success"]:
        contact_data = result["data"]
        success_msg = f"✅ บันทึกเบอร์เรียบร้อย!\n\n📝 ชื่อ: {contact_data['name']}\n📞 เบอร์: {contact_data['phone_number']}\n\n💡 ลองค้นหาดู: หาเบอร์ {name}"
        
        quick_reply = QuickReply(items=[
            QuickReplyItem(action=MessageAction(label="🔍 ค้นหาคนนี้", text=f"หาเบอร์ {name}")),
            QuickReplyItem(action=MessageAction(label="📝 เพิ่มคนใหม่", text="เพิ่มเบอร์ ")),
            QuickReplyItem(action=MessageAction(label="📋 ดูทั้งหมด", text="เบอร์ทั้งหมด"))
        ])
    else:
        success_msg = format_error_message("invalid_phone" if "เบอร์โทร" in result["error"] else "duplicate")
        quick_reply = create_thai_contact_menu()
    
    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=success_msg, quick_reply=quick_reply)]
        )
    )

def handle_search_simple(query, event):
    """Handle search with simple interface"""
    contacts = search_contacts_multi_keyword(query)
    
    if not contacts:
        error_msg = format_error_message("not_found")
        quick_reply = QuickReply(items=[
            QuickReplyItem(action=MessageAction(label="🔍 ลองคำอื่น", text="หาเบอร์ ")),
            QuickReplyItem(action=MessageAction(label="📋 ดูทั้งหมด", text="เบอร์ทั้งหมด")),
            QuickReplyItem(action=MessageAction(label="📝 เพิ่มใหม่", text="เพิ่มเบอร์ "))
        ])
        
        line_bot_api.reply_message(
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
        
        success_msg = f"🎯 พบแล้ว! ({len(contacts)} คน)\n\n💡 ต้องการค้นหาต่อไหม?"
        quick_reply = QuickReply(items=[
            QuickReplyItem(action=MessageAction(label="🔍 ค้นหาใหม่", text="หาเบอร์ ")),
            QuickReplyItem(action=MessageAction(label="📝 เพิ่มคนใหม่", text="เพิ่มเบอร์ ")),
            QuickReplyItem(action=MessageAction(label="📋 ดูทั้งหมด", text="เบอร์ทั้งหมด"))
        ])
        
        line_bot_api.reply_message(
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
        
        success_msg = f"🎯 พบ {len(contacts)} คน{' (แสดง 10 คนแรก)' if len(contacts) > 10 else ''}\n\n💡 ต้องการค้นหาเพิ่มไหม?"
        quick_reply = QuickReply(items=[
            QuickReplyItem(action=MessageAction(label="🔍 ค้นหาใหม่", text="หาเบอร์ ")),
            QuickReplyItem(action=MessageAction(label="📝 เพิ่มคนใหม่", text="เพิ่มเบอร์ ")),
            QuickReplyItem(action=MessageAction(label="📋 ดูทั้งหมด", text="เบอร์ทั้งหมด"))
        ])
        
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[flex_message, TextMessage(text=success_msg, quick_reply=quick_reply)]
            )
        )

def handle_list_simple(event):
    """Handle list all contacts with simple interface"""
    from contact_management import get_all_contacts
    
    contacts = get_all_contacts()
    
    if not contacts:
        msg = "📭 ยังไม่มีเบอร์โทรในสมุด\n\n💡 เริ่มเพิ่มเบอร์แรกกันเลย!"
        quick_reply = QuickReply(items=[
            QuickReplyItem(action=MessageAction(label="📝 เพิ่มเบอร์แรก", text="เพิ่มเบอร์ "))
        ])
    else:
        # Show summary
        msg = f"📋 สมุดเบอร์โทร ({len(contacts)} คน)\n\n"
        for i, contact in enumerate(contacts[:20], 1):
            msg += f"{i}. {contact['name']} - {contact['phone_number']}\n"
        
        if len(contacts) > 20:
            msg += f"\n... และอีก {len(contacts) - 20} คน"
        
        msg += "\n\n💡 ลองค้นหาคนที่ต้องการดู"
        
        quick_reply = QuickReply(items=[
            QuickReplyItem(action=MessageAction(label="🔍 ค้นหา", text="หาเบอร์ ")),
            QuickReplyItem(action=MessageAction(label="📝 เพิ่มใหม่", text="เพิ่มเบอร์ "))
        ])
    
    line_bot_api.reply_message(
        ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=msg, quick_reply=quick_reply)]
        )
    )

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)