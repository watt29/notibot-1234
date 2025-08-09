# -*- coding: utf-8 -*-
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
from dotenv import load_dotenv
import tempfile
from contact_management import (
    validate_phone_number, search_contacts_multi_keyword, add_contact, 
    edit_contact, delete_contact, get_all_contacts, export_contacts_to_excel,
    create_contact_flex_message
)
from contact_commands import (
    handle_add_contact_user, handle_search_contact_user, handle_admin_commands
)

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

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

# Test webhook endpoint
@app.route("/", methods=['GET'])
def home():
    return "LINE Bot is running! 🤖"

# Contact management integration
@handler.add(MessageEvent, message=TextMessageContent)
def handle_contact_commands(event):
    text = event.message.text
    
    # Handle regular user contact commands
    if text.startswith("add_phone "):
        text = text.replace("add_phone ", "เพิ่มเบอร์ ")
        handle_add_contact_user(text, event, line_bot_api, None)  # We'll need to import create_main_quick_reply
    elif text.startswith("search_phone "):
        text = text.replace("search_phone ", "หาเบอร์ ")
        handle_search_contact_user(text, event, line_bot_api, None)  # We'll need to import create_main_quick_reply
    elif handle_admin_commands(text, event, line_bot_api, admin_ids, None):  # We'll need to import create_admin_quick_reply
        pass
    else:
        # Default response for unknown commands
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=f"Contact Management Commands:\n• add_phone [name] [phone] - Add contact\n• search_phone [keyword] - Search contact\n• /contacts - Admin help")]
            )
        )

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)