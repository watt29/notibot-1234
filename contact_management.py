# -*- coding: utf-8 -*-
"""
Contact Management System for LINE Bot
ระบบจัดการเบอร์โทรสำหรับ LINE Bot
"""

import os
import re
import pandas as pd
import io
from datetime import datetime
from supabase import create_client, Client

# Initialize Supabase client
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_SERVICE_KEY')
supabase_client: Client = create_client(supabase_url, supabase_key)

def validate_supabase_response(response, operation="database operation"):
    """Validate Supabase response and provide detailed error info"""
    if not response:
        raise Exception(f"No response from {operation}")
    
    if hasattr(response, 'error') and response.error:
        raise Exception(f"Supabase error in {operation}: {response.error}")
    
    if not hasattr(response, 'data'):
        raise Exception(f"Invalid response structure from {operation}")
    
    return True

def safe_supabase_query(query_func, operation_name="query"):
    """Execute Supabase query with proper error handling"""
    try:
        response = query_func()
        validate_supabase_response(response, operation_name)
        return {"success": True, "data": response.data}
    except Exception as e:
        error_msg = str(e)
        print(f"Error in {operation_name}: {e}")
        
        # Categorize errors for better user feedback
        if "connection" in error_msg.lower() or "timeout" in error_msg.lower():
            return {"success": False, "error": "ปัญหาการเชื่อมต่อฐานข้อมูล", "type": "connection"}
        elif "permission" in error_msg.lower() or "unauthorized" in error_msg.lower():
            return {"success": False, "error": "ไม่มีสิทธิ์เข้าถึงข้อมูล", "type": "permission"}
        elif "not found" in error_msg.lower():
            return {"success": False, "error": "ไม่พบข้อมูลที่ต้องการ", "type": "not_found"}
        else:
            return {"success": False, "error": f"เกิดข้อผิดพลาด: {error_msg[:100]}", "type": "general"}

def validate_phone_number(phone_number):
    """Validate Thai phone number format"""
    # Remove all spaces, dashes, and parentheses
    phone_clean = re.sub(r'[\s\-\(\)]', '', phone_number)
    
    # Check if it's a valid Thai phone number format
    # Thai mobile: 08X-XXXXXXX, 09X-XXXXXXX, 06X-XXXXXXX
    # Thai landline: 0XX-XXXXXX (not mobile 08X, 09X, 06X)
    patterns = [
        r'^0[689]\d{8}$',  # Mobile numbers
        r'^0[2-7][0-9]\d{6,7}$',  # Landline numbers
    ]
    
    for pattern in patterns:
        if re.match(pattern, phone_clean):
            # Format to standard Thai format: 0XX-XXX-XXXX
            if len(phone_clean) == 10:
                return f"{phone_clean[:3]}-{phone_clean[3:6]}-{phone_clean[6:]}"
            elif len(phone_clean) == 9:
                return f"{phone_clean[:2]}-{phone_clean[2:5]}-{phone_clean[5:]}"
    
    return None

def search_contacts_multi_keyword(keywords, user_id=None):
    """Search contacts with multiple keywords (partial match)"""
    try:
        # Split keywords by space
        keyword_list = keywords.strip().split()
        
        if not keyword_list:
            return []
            
        # Build query for multiple keywords
        # Each keyword should match either name or phone_number
        query = supabase_client.table('contacts').select('*')
        
        for keyword in keyword_list:
            query = query.or_(f"name.ilike.%{keyword}%,phone_number.ilike.%{keyword}%")
        
        # Execute query with limit for performance
        result = query.limit(50).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error searching contacts: {e}")
        return []

def search_contacts_by_category(category="all", limit=20, offset=0):
    """Search contacts by category for large datasets with pagination"""
    try:
        query = supabase_client.table('contacts').select('*')
        
        if category == "recent":
            # Get recently added contacts
            query = query.order('created_at', desc=True).limit(limit).offset(offset)
        elif category == "mobile":
            # Get mobile numbers (08x, 09x, 06x) with optimized query
            query = query.or_("phone_number.ilike.08%,phone_number.ilike.09%,phone_number.ilike.06%").order('name').limit(limit).offset(offset)
        elif category == "landline":
            # Get landline numbers (02x-07x) with optimized query
            query = query.or_("phone_number.ilike.02%,phone_number.ilike.03%,phone_number.ilike.04%,phone_number.ilike.05%,phone_number.ilike.07%").order('name').limit(limit).offset(offset)
        else:
            # Get all contacts with pagination and ordering
            query = query.order('name').limit(limit).offset(offset)
        
        result = query.execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error searching contacts by category: {e}")
        return []

def get_contacts_stats():
    """Get statistics about contacts for large datasets"""
    try:
        # Get total count
        total_result = supabase_client.table('contacts').select('*', count='exact').execute()
        total_count = total_result.count
        
        # Get mobile count
        mobile_result = supabase_client.table('contacts').select('*', count='exact').or_("phone_number.ilike.08%,phone_number.ilike.09%,phone_number.ilike.06%").execute()
        mobile_count = mobile_result.count
        
        # Get recent count (last 30 days)
        from datetime import datetime, timedelta
        thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
        recent_result = supabase_client.table('contacts').select('*', count='exact').gte('created_at', thirty_days_ago).execute()
        recent_count = recent_result.count
        
        return {
            "total": total_count,
            "mobile": mobile_count,
            "landline": total_count - mobile_count,
            "recent": recent_count
        }
    except Exception as e:
        print(f"Error getting contacts stats: {e}")
        return {"total": 0, "mobile": 0, "landline": 0, "recent": 0}

def bulk_search_contacts(search_terms, limit=50):
    """Bulk search contacts for multiple keywords with performance optimization"""
    try:
        if not search_terms or not search_terms.strip():
            return []
        
        # Split search terms and clean them
        terms = [term.strip() for term in search_terms.split() if term.strip()]
        if not terms:
            return []
        
        # Use Full Text Search for better performance on large datasets
        query = supabase_client.table('contacts').select('*')
        
        # Build OR conditions for each term against name and phone
        or_conditions = []
        for term in terms:
            or_conditions.append(f"name.ilike.%{term}%")
            or_conditions.append(f"phone_number.ilike.%{term}%")
        
        # Execute optimized query with ordering
        query = query.or_(",".join(or_conditions)).order('name').limit(limit)
        result = query.execute()
        
        return result.data if result.data else []
    except Exception as e:
        print(f"Error in bulk search: {e}")
        return []

def add_contact(name, phone_number, user_id):
    """Add new contact to database"""
    try:
        # Validate phone number
        formatted_phone = validate_phone_number(phone_number)
        if not formatted_phone:
            return {"success": False, "error": "เบอร์โทรไม่ถูกต้อง กรุณาใส่เบอร์โทรที่ถูกต้อง (10 หลัก)"}
        
        # Check if contact already exists (same name and phone)
        existing = supabase_client.table('contacts').select('*').eq('name', name).eq('phone_number', formatted_phone).execute()
        if existing.data:
            return {"success": False, "error": "ข้อมูลนี้มีอยู่แล้วในระบบ"}
        
        # Insert new contact
        result = supabase_client.table('contacts').insert({
            'name': name,
            'phone_number': formatted_phone,
            'created_by': user_id,
            'updated_at': datetime.now().isoformat()
        }).execute()
        
        if result.data:
            return {"success": True, "data": result.data[0]}
        else:
            return {"success": False, "error": "ไม่สามารถเพิ่มข้อมูลได้"}
    except Exception as e:
        error_msg = str(e)
        print(f"Error adding contact: {e}")
        
        # Provide more specific error messages
        if "duplicate" in error_msg.lower() or "unique" in error_msg.lower():
            return {"success": False, "error": "ข้อมูลนี้มีอยู่แล้วในระบบ กรุณาตรวจสอบชื่อและเบอร์โทร"}
        elif "connection" in error_msg.lower() or "network" in error_msg.lower():
            return {"success": False, "error": "ปัญหาการเชื่อมต่อฐานข้อมูล กรุณาลองใหม่ในอีกสักครู่"}
        elif "invalid" in error_msg.lower():
            return {"success": False, "error": "รูปแบบข้อมูลไม่ถูกต้อง กรุณาตรวจสอบชื่อและเบอร์โทร"}
        else:
            return {"success": False, "error": f"เกิดข้อผิดพลาดในระบบ: {error_msg[:50]}"}

def edit_contact(contact_id, name, phone_number, user_id):
    """Edit existing contact (admin only)"""
    try:
        # Validate phone number
        formatted_phone = validate_phone_number(phone_number)
        if not formatted_phone:
            return {"success": False, "error": "เบอร์โทรไม่ถูกต้อง กรุณาใส่เบอร์โทรที่ถูกต้อง (10 หลัก)"}
        
        # Update contact
        result = supabase_client.table('contacts').update({
            'name': name,
            'phone_number': formatted_phone,
            'updated_at': datetime.now().isoformat()
        }).eq('id', contact_id).execute()
        
        if result.data:
            return {"success": True, "data": result.data[0]}
        else:
            return {"success": False, "error": "ไม่พบข้อมูลที่ต้องการแก้ไข"}
    except Exception as e:
        print(f"Error editing contact: {e}")
        return {"success": False, "error": "เกิดข้อผิดพลาดในระบบ"}

def delete_contact(contact_id, user_id):
    """Delete contact (admin only)"""
    try:
        result = supabase_client.table('contacts').delete().eq('id', contact_id).execute()
        if result.data:
            return {"success": True, "data": result.data[0]}
        else:
            return {"success": False, "error": "ไม่พบข้อมูลที่ต้องการลบ"}
    except Exception as e:
        print(f"Error deleting contact: {e}")
        return {"success": False, "error": "เกิดข้อผิดพลาดในระบบ"}

def get_all_contacts():
    """Get all contacts (admin only)"""
    try:
        result = supabase_client.table('contacts').select('*').order('created_at', desc=True).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"Error getting contacts: {e}")
        return []

def export_contacts_to_excel():
    """Export all contacts to Excel file (admin only)"""
    try:
        contacts = get_all_contacts()
        if not contacts:
            return {"success": False, "error": "ไม่มีข้อมูลที่จะส่งออก"}
        
        # Validate contacts data structure
        if not isinstance(contacts, list):
            return {"success": False, "error": "ข้อมูลเบอร์โทรไม่ถูกต้อง"}
        
        # Create DataFrame with error handling
        try:
            df = pd.DataFrame(contacts)
            if df.empty:
                return {"success": False, "error": "ไม่มีข้อมูลที่สามารถส่งออกได้"}
            
            # Validate required columns exist
            required_cols = ['id', 'name', 'phone_number', 'created_at', 'created_by']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                print(f"Missing columns: {missing_cols}")
                # Use available columns only
                available_cols = [col for col in required_cols if col in df.columns]
                df = df[available_cols]
            else:
                df = df[required_cols]
            
            df.columns = ['ID', 'ชื่อ', 'เบอร์โทร', 'วันที่สร้าง', 'ผู้สร้าง'][:len(df.columns)]
            
        except Exception as df_error:
            print(f"Error creating DataFrame: {df_error}")
            return {"success": False, "error": "ไม่สามารถประมวลผลข้อมูลได้"}
        
        # Create Excel file in memory with proper error handling
        output = io.BytesIO()
        try:
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Contacts', index=False)
        except Exception as excel_error:
            print(f"Error creating Excel file: {excel_error}")
            return {"success": False, "error": "ไม่สามารถสร้างไฟล์ Excel ได้"}
        
        try:
            output.seek(0)
            file_data = output.getvalue()
            
            if not file_data:
                return {"success": False, "error": "ไฟล์ Excel ว่างเปล่า"}
                
        except Exception as read_error:
            print(f"Error reading Excel data: {read_error}")
            return {"success": False, "error": "ไม่สามารถอ่านไฟล์ Excel ได้"}
        
        return {
            "success": True, 
            "file": file_data, 
            "filename": f"contacts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            "count": len(contacts)
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"Error exporting contacts: {e}")
        
        if "memory" in error_msg.lower():
            return {"success": False, "error": "หน่วยความจำไม่เพียงพอ ข้อมูลเยอะเกินไป"}
        elif "permission" in error_msg.lower():
            return {"success": False, "error": "ไม่มีสิทธิ์เข้าถึงไฟล์"}
        else:
            return {"success": False, "error": f"เกิดข้อผิดพลาดในการส่งออกข้อมูล: {error_msg[:50]}"}

def create_contact_flex_message(contact_data, is_single=False):
    """Create Flex Message for contact display"""
    contact_id = contact_data.get('id', '')
    name = contact_data.get('name', 'ไม่ระบุชื่อ')
    phone = contact_data.get('phone_number', 'ไม่ระบุเบอร์')
    created_at = contact_data.get('created_at', '')
    
    # Format date
    try:
        if created_at:
            date_obj = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            formatted_date = date_obj.strftime('%d/%m/%Y %H:%M')
        else:
            formatted_date = 'ไม่ระบุ'
    except:
        formatted_date = 'ไม่ระบุ'
    
    flex_content = {
        "type": "bubble",
        "size": "micro" if not is_single else "kilo",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "text",
                    "text": name,
                    "wrap": True,
                    "weight": "bold",
                    "size": "md",
                    "color": "#1DB446"
                },
                {
                    "type": "separator",
                    "margin": "sm"
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "sm",
                    "margin": "sm",
                    "contents": [
                        {
                            "type": "text",
                            "text": "📞",
                            "size": "sm",
                            "flex": 0
                        },
                        {
                            "type": "text",
                            "text": phone,
                            "size": "sm",
                            "color": "#333333",
                            "flex": 1
                        }
                    ]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "sm",
                    "margin": "xs",
                    "contents": [
                        {
                            "type": "text",
                            "text": "🆔",
                            "size": "xs",
                            "flex": 0
                        },
                        {
                            "type": "text",
                            "text": f"ID: {contact_id}",
                            "size": "xs",
                            "color": "#999999",
                            "flex": 1
                        }
                    ]
                } if is_single else None,
                {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "sm",
                    "margin": "xs",
                    "contents": [
                        {
                            "type": "text",
                            "text": "⏰",
                            "size": "xs",
                            "flex": 0
                        },
                        {
                            "type": "text",
                            "text": formatted_date,
                            "size": "xs",
                            "color": "#999999",
                            "flex": 1
                        }
                    ]
                } if is_single else None
            ]
        }
    }
    
    # Remove None items
    flex_content["body"]["contents"] = [item for item in flex_content["body"]["contents"] if item is not None]
    
    return flex_content