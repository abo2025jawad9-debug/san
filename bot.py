import asyncio
import os
import random
import cloudscraper
from bs4 import BeautifulSoup

# ==========================================
# 1. إعدادات الروابط والمصفوفات الأساسية
# ==========================================
YEMEN_PREFIXES = ["77", "78", "72", "73"]
GOVERNORATES = [str(i) for i in range(1, 23)]

ROUND_OF_16_TEAMS = {
    "1": "الأرجنتين",
    "12": "البرازيل",
    "38": "فرنسا",
    "9": "إنجلترا",
    "8": "إسبانيا",
    "25": "المكسيك",
    "13": "البرتغال",
    "27": "النرويج",
    "32": "بلجيكا",
    "33": "سويسرا",
    "40": "كرواتيا",
    "30": "باراغواي",
    "3": "استراليا",
    "41": "كندا"
}

FORM_PAGE_URL = "https://quwatasad.com/worldcup2026"
TARGET_URL = "https://quwatasad.com/form-submit"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": FORM_PAGE_URL,
    "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# ==========================================
# 2. إنشاء cloudscraper (يحاكي المتصفح ويتجاوز Cloudflare)
# ==========================================
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
)

# ==========================================
# 3. مصفوفات التمويه
# ==========================================
INVISIBLE_CHARS = [
    "\u064C", "\u064C"
]

ARABIC_DIACRITICS = [
    "\u064E", "\u064F", "\u0650", "\u064F", "\u064C", 
    "\u064D", "\u0651", "\u0651", "\u0640", "\u0653"
]

# ==========================================
# 4. دوال قراءة الملفات وهندسة النصوص
# ==========================================
def load_names_from_file(filename="names.txt"):
    """قراءة الأسماء من ملف txt، وإذا لم يوجد يستخدم قائمة افتراضية"""
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            names = [line.strip() for line in f if line.strip()]
            if names:
                print(f"[✔] تم تحميل {len(names)} اسم من ملف {filename} بنجاح.")
                return names
    print(f"[⚠] تنبيه: ملف {filename} غير موجود! سيتم استخدام أسماء افتراضية.")
    return [
        "محمد لطف يحيئ 772490746",
        "محمد لطف يحيى 772490746",
        "محمد لطف الزيلعي 772490746",
        "مجمد لطف الزيلعي 772490746",
    ]

def make_name_strictly_unique(name):
    hidden_prob = random.uniform(0.40, 0.80)
    diacritic_prob = random.uniform(0.20, 0.50)
    
    unique_name = ""
    
    if random.random() < 0.5:
        unique_name += "".join(random.choices(INVISIBLE_CHARS, k=random.randint(1, 2)))

    for char in name:
        unique_name += char
        if char != " ":
            if random.random() < hidden_prob:
                unique_name += random.choice(INVISIBLE_CHARS)
            if random.random() < diacritic_prob:
                unique_name += random.choice(ARABIC_DIACRITICS)
                if random.random() < 0.20:
                    unique_name += random.choice(ARABIC_DIACRITICS)

    trailing_spaces = " " * random.randint(0, 3)
    return f"{unique_name}{trailing_spaces}"

def generate_random_phone():
    prefix = random.choice(YEMEN_PREFIXES)
    suffix = "".join([str(random.randint(0, 9)) for _ in range(7)])
    return f"{prefix}{suffix}"

# ==========================================
# 5. جلب الحقول المخفية ديناميكياً
# ==========================================
async def fetch_live_form_data():
    print("[⌛] جاري الاتصال بالصفحة لجلب التوكن والحقول المخفية...")
    loop = asyncio.get_event_loop()
    try:
        def fetch():
            return scraper.get(FORM_PAGE_URL, headers=HEADERS, timeout=15)
        
        response = await asyncio.wait_for(
            loop.run_in_executor(None, fetch),
            timeout=20
        )
        
        if response.status_code != 200:
            print(f"[✘] فشل فتح الصفحة. كود الحالة: {response.status_code}")
            print("[⚠] سيتم استخدام البيانات الافتراضية للمتابعة...")
            return {
                "_token": "local_test_token",
                "date": "2026-07-03",
                "section_id": "0",
                "TopicID": "152",
                "WebmasterSectionId": ""
            }

        html_content = response.text
        soup = BeautifulSoup(html_content, "html.parser")

        token_input = soup.find("input", {"name": "_token"})
        topic_id_input = soup.find("input", {"name": "TopicID"})
        webmaster_id_input = soup.find("input", {"name": "WebmasterSectionId"})
        date_input = soup.find("input", {"name": "date"})
        section_id_input = soup.find("input", {"name": "section_id"})

        live_fields = {
            "_token": token_input.get("value", "mock_token_123") if token_input else "mock_token_123",
            "date": date_input.get("value", "2026-07-03") if date_input else "2026-07-03",
            "section_id": section_id_input.get("value", "0") if section_id_input else "0",
            "TopicID": topic_id_input.get("value", "152") if topic_id_input else "152",
            "WebmasterSectionId": webmaster_id_input.get("value", "") if webmaster_id_input else "",
        }

        print(f"[✔] تم جلب البيانات الأساسية بنجاح.")
        return live_fields
    except Exception as e:
        print(f"[✘] حدث خطأ أثناء جلب البيانات: {str(e)}")
        print("[⚠] سيتم استخدام البيانات الافتراضية للمتابعة...")
        return {
            "_token": "local_test_token",
            "date": "2026-07-03",
            "section_id": "0",
            "TopicID": "152",
            "WebmasterSectionId": ""
        }

# ==========================================
# 6. تجهيز الحزمة وفحص الاستلام
# ==========================================
def prepare_payload(live_fields, names_list):
    raw_name = random.choice(names_list)
    unique_name = make_name_strictly_unique(raw_name)

    team_id = random.choice(list(ROUND_OF_16_TEAMS.keys()))
    team_name = ROUND_OF_16_TEAMS[team_id]

    payload = live_fields.copy()
    payload.update({
        "customField_18": team_id,
        "customField_19": unique_name,
        "customField_20": generate_random_phone(),
        "customField_24": random.choice(GOVERNORATES),
    })
    return payload, team_name

def check_submission_success(status, final_url, html_text):
    success_keywords = ["شكرا", "تم بنجاح", "success", "thank"]
    is_success_word = any(kw in html_text.lower() for kw in success_keywords)
    
    if status == 200 or is_success_word:
        return True, "تمت العملية بنجاح"
    else:
        return False, f"كود الحالة: {status}"

# ==========================================
# 7. إرسال الطلبات المتزامنة
# ==========================================
async def send_request(request_num, live_fields, names_list):
    payload, team_name = prepare_payload(live_fields, names_list)
    loop = asyncio.get_event_loop()
    try:
        def post_data():
            return scraper.post(TARGET_URL, data=payload, headers=HEADERS, timeout=15)
        
        response = await asyncio.wait_for(
            loop.run_in_executor(None, post_data),
            timeout=20
        )
        
        status = response.status_code
        final_url = str(response.url)
        html_text = response.text

        is_success, message = check_submission_success(status, final_url, html_text)

        if is_success:
            print(f"[🏆 نجاح] الطلب {request_num:02d} | المنتخب: {team_name} ({payload['customField_18']}) | الاسم: {repr(payload['customField_19'])}")
        else:
            print(f"[⚠ رفض] الطلب {request_num:02d} | المنتخب: {team_name} ({payload['customField_18']}) | {message}")
    except Exception as e:
        print(f"[✘ خطأ اتصال] الطلب {request_num:02d} فشل: {str(e)}")

# ==========================================
# 8. نقطة الانطلاق وإدارة التزامن
# ==========================================
async def main():
    print("==================================================")
    print("--- بدء تشغيل سكربت الاختبار: دالة الزخرفة العشوائية ---")
    print("==================================================")

    print("\n[📋] قائمة المنتخبات المتاحة في القاموس:")
    for tid, tname in ROUND_OF_16_TEAMS.items():
        print(f"    {tid}: {tname}")

    names_list = load_names_from_file("names.txt")

    live_fields = await fetch_live_form_data()

    if not live_fields:
        print("[🛑] توقف السكربت: فشل التهيئة.")
        return

    for round_num in range(1, 7):
        print(f"\n{'='*50}")
        print(f"--- بدء الدورة رقم {round_num} من 6 ---")
        print(f"{'='*50}")

        tasks = [
            send_request(i, live_fields, names_list)
            for i in range(1, 100)
        ]
        await asyncio.gather(*tasks)

        if round_num < 6:
            wait_time = random.randint(3, 8)
            print(f"\n[⏳] انتهت الدورة {round_num}. انتظار {wait_time} ثوانٍ قبل الدورة التالية...")
            await asyncio.sleep(wait_time)

    print("\n==================================================")
    print("--- تم الانتهاء من جميع الدورات (6/6) بنجاح ---")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(main())

