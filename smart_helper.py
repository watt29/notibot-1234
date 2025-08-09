# -*- coding: utf-8 -*-
"""
Smart Helper for Contact Management
ระบบช่วยเหลือและแนะนำอัตโนมัติ
"""

import re
from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction

def detect_incomplete_command(text):
    """Detect incomplete commands and suggest completion"""
    text = text.lower().strip()
    
    suggestions = []
    
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

def suggest_phone_format(phone_text):
    """Suggest proper phone number format"""
    if not phone_text:
        return None
        
    # Remove all non-digits
    digits_only = re.sub(r'\D', '', phone_text)
    
    # Check if it looks like a phone number attempt
    if len(digits_only) >= 8:
        if len(digits_only) == 10 and digits_only.startswith('0'):
            # Format Thai phone number
            formatted = f"{digits_only[:3]}-{digits_only[3:6]}-{digits_only[6:]}"
            return {
                "original": phone_text,
                "formatted": formatted,
                "message": f"💡 แนะนำรูปแบบ: {formatted}"
            }
        elif len(digits_only) == 9 and digits_only.startswith('0'):
            # Landline format
            formatted = f"{digits_only[:2]}-{digits_only[2:5]}-{digits_only[5:]}"
            return {
                "original": phone_text,
                "formatted": formatted, 
                "message": f"💡 แนะนำรูปแบบ: {formatted}"
            }
    
    return None

def create_smart_suggestions(context, recent_contacts=None):
    """Create smart suggestions based on context"""
    suggestions = []
    
    if context == "add_contact":
        suggestions = [
            "เพิ่มเบอร์ สมชาย 081-234-5678",
            "เพิ่มเบอร์ นางสาวดาว 089-999-8888", 
            "เพิ่มเบอร์ คุณแม่ 02-123-4567"
        ]
    elif context == "search_contact":
        if recent_contacts:
            # Use recent contact names as suggestions
            suggestions = [f"หาเบอร์ {contact['name']}" for contact in recent_contacts[:3]]
        else:
            suggestions = ["หาเบอร์ สมชาย", "หาเบอร์ 081", "หาเบอร์ คุณ"]
    
    return suggestions

def create_suggestion_quick_reply(suggestions):
    """Create quick reply with suggestions"""
    items = []
    for i, suggestion in enumerate(suggestions[:10]):  # Limit to 10 items
        items.append(QuickReplyItem(
            action=MessageAction(label=f"💡 {suggestion[:20]}...", text=suggestion)
        ))
    
    # Add cancel option
    items.append(QuickReplyItem(
        action=MessageAction(label="❌ ยกเลิก", text="สวัสดี")
    ))
    
    return QuickReply(items=items)

def analyze_user_intent(text):
    """Analyze user intent from natural language"""
    text = text.lower().strip()
    
    # Contact-related keywords
    contact_keywords = ["เบอร์", "ชื่อ", "โทร", "ติดต่อ", "คน", "เพื่อน"]
    action_keywords = {
        "add": ["เพิ่ม", "บันทึก", "เก็บ", "ใส่", "เซฟ"],
        "search": ["หา", "ค้น", "ดู", "เช็ค", "ตรวจ"],
        "delete": ["ลบ", "ลบออก", "เอาออก", "ไม่เอา"],
        "list": ["ทั้งหมด", "รายการ", "ลิสต์", "แสดง"]
    }
    
    intent = {
        "action": None,
        "confidence": 0,
        "context": "contact" if any(keyword in text for keyword in contact_keywords) else "general"
    }
    
    # Check for action keywords
    for action, keywords in action_keywords.items():
        if any(keyword in text for keyword in keywords):
            intent["action"] = action
            intent["confidence"] = 0.8
            break
    
    return intent

def format_error_message(error_type, details=None):
    """Format user-friendly error messages"""
    messages = {
        "invalid_phone": "❌ เบอร์โทรไม่ถูกต้อง\n\n💡 เบอร์โทรไทยต้องมี 10 หลัก\n🔤 ตัวอย่าง: 081-234-5678",
        "missing_name": "❌ กรุณาใส่ชื่อด้วย\n\n💡 รูปแบบ: เพิ่มเบอร์ ชื่อ เบอร์โทร",
        "not_found": "❌ ไม่พบข้อมูลที่ค้นหา\n\n💡 ลองค้นหาด้วย:\n• ชื่อหรือนามสกุล\n• เลขเบอร์บางส่วน\n• คำที่จำได้",
        "duplicate": "⚠️ ข้อมูลนี้มีอยู่แล้ว\n\n💡 ลองค้นหาดูก่อนได้นะ",
        "no_permission": "🔒 คำสั่งนี้ใช้ได้เฉพาะ Admin\n\n💡 ใช้คำสั่งผู้ใช้ทั่วไปแทน:\n• เพิ่มเบอร์\n• หาเบอร์"
    }
    
    message = messages.get(error_type, "❌ เกิดข้อผิดพลาด")
    
    if details:
        message += f"\n\n📝 รายละเอียด: {details}"
    
    return message