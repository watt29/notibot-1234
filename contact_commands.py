# -*- coding: utf-8 -*-
"""
Contact Commands for LINE Bot
คำสั่งเบอร์โทรสำหรับ LINE Bot
"""

from linebot.v3.messaging import (
    ReplyMessageRequest, TextMessage, FlexMessage, FlexContainer,
    QuickReply, QuickReplyItem, MessageAction
)
from contact_management import (
    add_contact, search_contacts_multi_keyword, edit_contact, 
    delete_contact, get_all_contacts, export_contacts_to_excel,
    create_contact_flex_message
)
from datetime import datetime

def create_contact_quick_reply():
    """Create quick reply for contact management"""
    return QuickReply(items=[
        QuickReplyItem(action=MessageAction(label="📞 เพิ่มเบอร์", text="add_phone ")),
        QuickReplyItem(action=MessageAction(label="🔍 หาเบอร์", text="search_phone ")),
        QuickReplyItem(action=MessageAction(label="📋 ดูทั้งหมด", text="/list")),
        QuickReplyItem(action=MessageAction(label="📖 วิธีใช้", text="/contacts")),
        QuickReplyItem(action=MessageAction(label="🏠 เมนูหลัก", text="สวัสดี"))
    ])

def create_contact_admin_quick_reply():
    """Create admin quick reply for contact management"""
    return QuickReply(items=[
        QuickReplyItem(action=MessageAction(label="➕ เพิ่ม", text="/add ")),
        QuickReplyItem(action=MessageAction(label="✏️ แก้ไข", text="/edit ")),
        QuickReplyItem(action=MessageAction(label="🗑️ ลบ", text="/delete ")),
        QuickReplyItem(action=MessageAction(label="📊 ทั้งหมด", text="/list")),
        QuickReplyItem(action=MessageAction(label="🔍 ค้นหา", text="/search ")),
        QuickReplyItem(action=MessageAction(label="📁 Excel", text="/export")),
        QuickReplyItem(action=MessageAction(label="🏠 หลัก", text="/admin"))
    ])

def handle_add_contact_user(text, event, line_bot_api, create_main_quick_reply):
    """Handle regular user add contact command"""
    try:
        # Parse: เพิ่มเบอร์ ชื่อ เบอร์โทร
        parts = text.replace("เพิ่มเบอร์ ", "").split()
        if len(parts) < 2:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="❌ รูปแบบไม่ถูกต้อง\n\n📝 รูปแบบ: เพิ่มเบอร์ ชื่อ เบอร์โทร\n💡 ตัวอย่าง: เพิ่มเบอร์ สมชาย 081-234-5678")]
                )
            )
            return
        
        name = parts[0]
        phone_number = parts[1]
        
        result = add_contact(name, phone_number, event.source.user_id)
        
        if result["success"]:
            contact_data = result["data"]
            success_text = f"✅ เพิ่มข้อมูลสำเร็จ!\n\n📝 ชื่อ: {contact_data['name']}\n📞 เบอร์: {contact_data['phone_number']}\n🆔 ID: {contact_data['id']}"
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=success_text, quick_reply=create_main_quick_reply())]
                )
            )
        else:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"❌ {result['error']}", quick_reply=create_main_quick_reply())]
                )
            )
    except Exception as e:
        print(f"Error in add contact: {e}")
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="❌ เกิดข้อผิดพลาดในระบบ", quick_reply=create_main_quick_reply())]
            )
        )

def handle_search_contact_user(text, event, line_bot_api, create_main_quick_reply):
    """Handle regular user search contact command"""
    try:
        keywords = text.replace("หาเบอร์ ", "").strip()
        if not keywords:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="❌ กรุณาใส่คำค้นหา\n\n💡 ตัวอย่าง: หาเบอร์ สมชาย\n💡 หรือ: หาเบอร์ สมชาย 081")]
                )
            )
            return
        
        contacts = search_contacts_multi_keyword(keywords)
        
        if contacts:
            if len(contacts) == 1:
                # Single contact - show detailed info
                flex_content = create_contact_flex_message(contacts[0], is_single=True)
                flex_message = FlexMessage(alt_text="ผลการค้นหา", contents=FlexContainer.from_dict(flex_content))
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[flex_message, TextMessage(text="💡 ใช้: หาเบอร์ [คำค้นหา] เพื่อค้นหาอีกครั้ง", quick_reply=create_main_quick_reply())]
                    )
                )
            else:
                # Multiple contacts - show carousel
                bubbles = []
                for contact in contacts[:10]:  # Limit to 10 contacts
                    bubbles.append(create_contact_flex_message(contact))
                
                carousel_content = {
                    "type": "carousel",
                    "contents": bubbles
                }
                
                flex_message = FlexMessage(alt_text="ผลการค้นหา", contents=FlexContainer.from_dict(carousel_content))
                result_text = f"🔍 พบ {len(contacts)} รายการ{' (แสดง 10 รายการแรก)' if len(contacts) > 10 else ''}"
                
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[flex_message, TextMessage(text=result_text, quick_reply=create_main_quick_reply())]
                    )
                )
        else:
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="❌ ไม่พบข้อมูลที่ตรงกับคำค้นหา\n\n💡 ลองใช้คำค้นหาอื่น เช่น บางส่วนของชื่อ หรือเลขเบอร์", quick_reply=create_main_quick_reply())]
                )
            )
    except Exception as e:
        print(f"Error in search contact: {e}")
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="❌ เกิดข้อผิดพลาดในการค้นหา", quick_reply=create_main_quick_reply())]
            )
        )

def handle_admin_commands(text, event, line_bot_api, admin_ids, create_admin_quick_reply):
    """Handle all admin contact commands"""
    if text == "/contacts" and event.source.user_id in admin_ids:
        help_text = """📞 คำสั่งจัดการเบอร์โทร (Admin)

👥 ผู้ใช้ทั่วไป:
• เพิ่มเบอร์ [ชื่อ] [เบอร์] - เพิ่มข้อมูล
• หาเบอร์ [คำค้นหา] - ค้นหาข้อมูล

🔧 Admin เท่านั้น:
• /add [ชื่อ] [เบอร์] - เพิ่มข้อมูล
• /edit [ID] [ชื่อใหม่] [เบอร์ใหม่] - แก้ไข
• /delete [ID] - ลบข้อมูล
• /list - ดูข้อมูลทั้งหมด
• /export - ส่งออกไฟล์ Excel
• /search [คำค้นหา] - ค้นหาแบบ admin

💡 ตัวอย่าง:
• เพิ่มเบอร์ สมชาย 081-234-5678
• หาเบอร์ สมชาย 081
• /edit 123 สมชาย 089-999-9999"""

        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=help_text, quick_reply=create_admin_quick_reply())]
            )
        )
        return True
    
    elif text.startswith("/add ") and event.source.user_id in admin_ids:
        try:
            parts = text.replace("/add ", "").split()
            if len(parts) < 2:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="❌ รูปแบบไม่ถูกต้อง\n\n📝 รูปแบบ: /add ชื่อ เบอร์โทร", quick_reply=create_admin_quick_reply())]
                    )
                )
                return True
            
            name = parts[0]
            phone_number = parts[1]
            
            result = add_contact(name, phone_number, event.source.user_id)
            
            if result["success"]:
                contact_data = result["data"]
                success_text = f"✅ เพิ่มข้อมูลสำเร็จ! (Admin)\n\n📝 ชื่อ: {contact_data['name']}\n📞 เบอร์: {contact_data['phone_number']}\n🆔 ID: {contact_data['id']}"
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
                        messages=[TextMessage(text=f"❌ {result['error']}", quick_reply=create_admin_quick_reply())]
                    )
                )
        except Exception as e:
            print(f"Error in admin add contact: {e}")
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="❌ เกิดข้อผิดพลาดในระบบ", quick_reply=create_admin_quick_reply())]
                )
            )
        return True
    
    elif text.startswith("/edit ") and event.source.user_id in admin_ids:
        try:
            parts = text.replace("/edit ", "").split()
            if len(parts) < 3:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="❌ รูปแบบไม่ถูกต้อง\n\n📝 รูปแบบ: /edit ID ชื่อใหม่ เบอร์ใหม่", quick_reply=create_admin_quick_reply())]
                    )
                )
                return True
            
            contact_id = parts[0]
            name = parts[1]
            phone_number = parts[2]
            
            result = edit_contact(contact_id, name, phone_number, event.source.user_id)
            
            if result["success"]:
                contact_data = result["data"]
                success_text = f"✅ แก้ไขข้อมูลสำเร็จ!\n\n📝 ชื่อ: {contact_data['name']}\n📞 เบอร์: {contact_data['phone_number']}\n🆔 ID: {contact_data['id']}"
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
                        messages=[TextMessage(text=f"❌ {result['error']}", quick_reply=create_admin_quick_reply())]
                    )
                )
        except Exception as e:
            print(f"Error in edit contact: {e}")
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="❌ เกิดข้อผิดพลาดในระบบ", quick_reply=create_admin_quick_reply())]
                )
            )
        return True
    
    elif text.startswith("/delete ") and event.source.user_id in admin_ids:
        try:
            contact_id = text.replace("/delete ", "").strip()
            
            if not contact_id:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="❌ รูปแบบไม่ถูกต้อง\n\n📝 รูปแบบ: /delete ID", quick_reply=create_admin_quick_reply())]
                    )
                )
                return True
            
            result = delete_contact(contact_id, event.source.user_id)
            
            if result["success"]:
                deleted_data = result["data"]
                success_text = f"✅ ลบข้อมูลสำเร็จ!\n\n📝 ชื่อ: {deleted_data['name']}\n📞 เบอร์: {deleted_data['phone_number']}\n🆔 ID: {deleted_data['id']}"
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
                        messages=[TextMessage(text=f"❌ {result['error']}", quick_reply=create_admin_quick_reply())]
                    )
                )
        except Exception as e:
            print(f"Error in delete contact: {e}")
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="❌ เกิดข้อผิดพลาดในระบบ", quick_reply=create_admin_quick_reply())]
                )
            )
        return True
    
    elif text == "/list" and event.source.user_id in admin_ids:
        try:
            contacts = get_all_contacts()
            
            if contacts:
                # Show summary first
                summary_text = f"📊 ข้อมูลทั้งหมด: {len(contacts)} รายการ\n\n"
                for i, contact in enumerate(contacts[:20], 1):  # Show first 20
                    summary_text += f"{i}. {contact['name']} - {contact['phone_number']} (ID: {contact['id']})\n"
                
                if len(contacts) > 20:
                    summary_text += f"\n... และอีก {len(contacts) - 20} รายการ\n\n💡 ใช้ /export เพื่อดาวน์โหลดไฟล์ Excel"
                else:
                    summary_text += "\n💡 ใช้ /export เพื่อดาวน์โหลดไฟล์ Excel"
                
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=summary_text, quick_reply=create_admin_quick_reply())]
                    )
                )
            else:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="❌ ยังไม่มีข้อมูลในระบบ", quick_reply=create_admin_quick_reply())]
                    )
                )
        except Exception as e:
            print(f"Error in list contacts: {e}")
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="❌ เกิดข้อผิดพลาดในระบบ", quick_reply=create_admin_quick_reply())]
                )
            )
        return True
    
    elif text == "/export" and event.source.user_id in admin_ids:
        try:
            result = export_contacts_to_excel()
            
            if result["success"]:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=f"✅ ส่งออกข้อมูลสำเร็จ!\n\n📁 ไฟล์: {result['filename']}\n\n⚠️ หมายเหตุ: LINE Bot ไม่สามารถส่งไฟล์โดยตรง กรุณาติดต่อผู้ดูแลระบบเพื่อรับไฟล์", quick_reply=create_admin_quick_reply())]
                    )
                )
            else:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=f"❌ {result['error']}", quick_reply=create_admin_quick_reply())]
                    )
                )
        except Exception as e:
            print(f"Error in export contacts: {e}")
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="❌ เกิดข้อผิดพลาดในการส่งออก", quick_reply=create_admin_quick_reply())]
                )
            )
        return True
    
    elif text.startswith("/search ") and event.source.user_id in admin_ids:
        try:
            keywords = text.replace("/search ", "").strip()
            if not keywords:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="❌ กรุณาใส่คำค้นหา\n\n💡 ตัวอย่าง: /search สมชาย 081", quick_reply=create_admin_quick_reply())]
                    )
                )
                return True
            
            contacts = search_contacts_multi_keyword(keywords)
            
            if contacts:
                # Show detailed list for admin
                result_text = f"🔍 พบ {len(contacts)} รายการ\n\n"
                for i, contact in enumerate(contacts[:15], 1):  # Show first 15
                    created_date = ""
                    try:
                        if contact.get('created_at'):
                            date_obj = datetime.fromisoformat(contact['created_at'].replace('Z', '+00:00'))
                            created_date = date_obj.strftime('%d/%m/%Y')
                    except:
                        created_date = "ไม่ระบุ"
                    
                    result_text += f"{i}. {contact['name']} - {contact['phone_number']}\n   ID: {contact['id']} | วันที่: {created_date}\n\n"
                
                if len(contacts) > 15:
                    result_text += f"... และอีก {len(contacts) - 15} รายการ"
                
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=result_text, quick_reply=create_admin_quick_reply())]
                    )
                )
            else:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="❌ ไม่พบข้อมูลที่ตรงกับคำค้นหา", quick_reply=create_admin_quick_reply())]
                    )
                )
        except Exception as e:
            print(f"Error in admin search: {e}")
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="❌ เกิดข้อผิดพลาดในการค้นหา", quick_reply=create_admin_quick_reply())]
                )
            )
        return True
    
    return False