import os
from supabase import create_client, Client
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    PushMessageRequest,
    TextMessage
)
from datetime import date, timedelta

# --- Load Environment Variables ---
def get_env(var_name):
    value = os.environ.get(var_name)
    if not value:
        raise ValueError(f"{var_name} not set in environment variables.")
    return value

SUPABASE_URL = get_env('SUPABASE_URL')
SUPABASE_KEY = get_env('SUPABASE_KEY')
LINE_CHANNEL_ACCESS_TOKEN = get_env('LINE_CHANNEL_ACCESS_TOKEN')

# --- Initialize Supabase & LINE Bot API ---
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)

# --- Main Logic ---
def send_reminder_notifications():
    """Fetches events happening tomorrow and notifies all subscribers."""
    tomorrow = date.today() + timedelta(days=1)
    
    try:
        # 1. Fetch events for tomorrow
        events_res = supabase.table('events').select('event_title', 'event_description').eq('event_date', str(tomorrow)).execute()
        if not events_res.data:
            print(f"No events found for {tomorrow}. Exiting.")
            return

        # 2. Fetch all subscribers
        subscribers_res = supabase.table('subscribers').select('user_id').execute()
        if not subscribers_res.data:
            print("No subscribers to notify. Exiting.")
            return

        subscriber_ids = [sub['user_id'] for sub in subscribers_res.data]

        # 3. Construct the message
        message_body = f"🔔 แจ้งเตือนเหตุการณ์วันพรุ่งนี้ ({tomorrow.strftime('%d/%m/%Y')})\n"
        for event in events_res.data:
            message_body += f"\n🔹 {event['event_title']}\n   - {event['event_description']}"
        
        message = TextMessage(text=message_body)

        # 4. Send push message to all subscribers
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.push_message(PushMessageRequest(
                to=subscriber_ids, # Send to all subscribers at once
                messages=[message]
            ))
        print(f"Successfully sent reminders for {tomorrow} to {len(subscriber_ids)} subscribers.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    print("Running scheduled job: Sending event reminders...")
    send_reminder_notifications()
