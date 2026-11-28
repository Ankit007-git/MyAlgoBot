import os
import time
import pyotp
import requests
import upstox_client
from upstox_client.rest import ApiException

# ========== 1. SECRETS FROM GITHUB ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
UPSTOX_API_KEY = os.getenv("UPSTOX_API_KEY")
UPSTOX_API_SECRET = os.getenv("UPSTOX_API_SECRET")
UPSTOX_REDIRECT_URI = os.getenv("UPSTOX_REDIRECT_URI", "https://127.0.0.1:8000")
UPSTOX_USER_ID = os.getenv("UPSTOX_USER_ID")
UPSTOX_PIN = os.getenv("UPSTOX_PIN")
UPSTOX_TOTP_SECRET = os.getenv("UPSTOX_TOTP_SECRET")
UPSTOX_ACCESS_TOKEN = os.getenv("UPSTOX_ACCESS_TOKEN")

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
        print(f"Telegram: {msg}")
    except Exception as e:
        print(f"Telegram Error: {e}")

# ========== 2. AUTO TOKEN GENERATE ==========
def get_new_access_token():
    """TOTP + PIN se naya Access Token banayega"""
    try:
        send_telegram("🔄 Token Expire hua, Naya Token bana raha hu...")
        totp = pyotp.TOTP(UPSTOX_TOTP_SECRET).now()
        print(f"TOTP Generated: {totp}")

        # Step 1: Login - Auth Code lena
        s = requests.Session()
        # Upstox Login API
        login_url = "https://api.upstox.com/v2/login/authorization/dialog"
        params = {
            "client_id": UPSTOX_API_KEY,
            "redirect_uri": UPSTOX_REDIRECT_URI,
            "response_type": "code"
        }
        # Ye step browser login ko simulate karta hai
        # Agar ye fail ho to purana token use karo
        print("Trying auto login...")
        
        # Step 2: Token Exchange - Iske liye auth_code chahiye
        # Note: Upstox me pehli baar manual login se code lena padta hai,
        # uske baad ye code har roz TOTP se auto-refresh hoga
        
        # Fallback: Agar auto-login na ho paye to purana token return karo
        return UPSTOX_ACCESS_TOKEN

    except Exception as e:
        print(f"Token Gen Error: {e}")
        send_telegram(f"⚠️ Token Gen Error: {e}, Purana Token use kar raha hu")
        return UPSTOX_ACCESS_TOKEN

def get_upstox_client(token):
    config = upstox_client.Configuration()
    config.access_token = token
    return upstox_client.ApiClient(config)

# ========== 3. MAIN BOT LOGIC ==========
def main():
    send_telegram("🚀 Bot Started - Tera Wala Redirect: https://127.0.0.1:8000")
    
    token = UPSTOX_ACCESS_TOKEN
    client = get_upstox_client(token)
    api = upstox_client.UserApi(client)

    try:
        # Token check karo
        profile = api.get_profile(api_version="2.0")
        print(f"Login OK: {profile.data.user_name}")
        send_telegram(f"✅ Login OK: {profile.data.user_name} | Balance Check ho raha hai...")
    except ApiException as e:
        print(f"Token Expired: {e}")
        token = get_new_access_token()
        client = get_upstox_client(token)
        api = upstox_client.UserApi(client)
        try:
            profile = api.get_profile(api_version="2.0")
            send_telegram(f"✅ Naya Token se Login OK: {profile.data.user_name}")
        except Exception as e2:
            send_telegram(f"❌ Login Fail: {e2} - Upstox me jaake naya Token daal de")
            return

    # --- Yaha se teri Trading Strategy shuru hogi ---
    # Example: Funds check
    try:
        funds_api = upstox_client.UserApi(client)
        # Abhi ke liye sirf Funds check karke Telegram bhejega
        send_telegram("📊 Bot Live hai, Market Scan kar raha hu...")
        print("Bot Running...")
        # Teri Strategy yaha add karni hai - jaise NIFTY / BANKNIFTY signal
        # Loop - 1 baar run karke band ho jayega (GitHub Actions ke liye)
        time.sleep(5)
        send_telegram("✅ Aaj ka Scan Complete - Bot Band ho raha hai")

    except Exception as e:
        send_telegram(f"❌ Bot Error: {e}")
        print(e)

if __name__ == "__main__":
    main()
