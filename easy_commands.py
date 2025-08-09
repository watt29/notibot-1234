# -*- coding: utf-8 -*-
"""
Easy Thai Commands for Contact Management
คำสั่งภาษาไทยที่เข้าใจง่าย
"""

def convert_thai_to_english_command(text):
    """Convert Thai natural language to English commands"""
    text = text.lower().strip()
    
    # เพิ่มเบอร์ commands
    add_patterns = [
        "เพิ่มเบอร์",
        "บันทึกเบอร์", 
        "เพิ่มชื่อ",
        "บันทึกชื่อ",
        "เพิ่มคนใหม่",
        "เก็บเบอร์"
    ]
    
    # ค้นหา commands  
    search_patterns = [
        "หาเบอร์",
        "ค้นหา",
        "หาชื่อ",
        "เบอร์ของ",
        "ชื่อ",
        "เบอร์",
        "หา"
    ]
    
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
    
    # Return original text if no pattern matches
    return text

def create_help_message():
    """Create help message in Thai"""
    return """📞 วิธีใช้งานสมุดเบอร์โทร

🎯 **วิธีง่ายๆ ที่เข้าใจได้:**

📝 **เพิ่มเบอร์:**
• เพิ่มเบอร์ สมชาย 081-234-5678
• บันทึกเบอร์ นางสาวดาว 089-999-8888
• เก็บเบอร์ คุณแม่ 02-123-4567

🔍 **หาเบอร์:**
• หาเบอร์ สมชาย
• ค้นหา 081
• เบอร์ของ ดาว
• หา สมชาย 081

💡 **เทคนิค:**
• พิมพ์แค่บางส่วนก็ได้
• ค้นหาได้หลายคำพร้อมกัน
• ไม่ต้องสนใจตัวพิมพ์เล็ก-ใหญ่

🎮 **กดปุ่มด่วน:**
ใช้ปุ่มด้านล่างได้เลย!"""

def create_thai_contact_menu():
    """Create Thai language contact menu"""
    from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction
    
    return QuickReply(items=[
        QuickReplyItem(action=MessageAction(label="📝 เพิ่มเบอร์", text="เพิ่มเบอร์ ")),
        QuickReplyItem(action=MessageAction(label="🔍 หาเบอร์", text="หาเบอร์ ")),
        QuickReplyItem(action=MessageAction(label="📖 วิธีใช้", text="วิธีใช้เบอร์")),
        QuickReplyItem(action=MessageAction(label="📞 เบอร์ทั้งหมด", text="เบอร์ทั้งหมด")),
        QuickReplyItem(action=MessageAction(label="🏠 กลับหน้าแรก", text="สวัสดี"))
    ])