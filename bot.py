import asyncio
import os
import random
from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup
import time
import sys

# ==========================================
# 1. الإعدادات
# ==========================================
YEMEN_PREFIXES = ["77", "78", "72", "73", "70", "71"]
GOVERNORATES = [str(i) for i in range(1, 23)]

# قائمة الفرق كما هي (12 فريقاً) - يمكن توسيعها
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
    "16": "المغرب",
    "45": "مصر",
}

FORM_PAGE_URL = "https://quwatasad.com/worldcup2026"
TARGET_URL = "https://quwatasad.com/form-submit"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": FORM_PAGE_URL,
    "Origin": "https://quwatasad.com",
    "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
}

PROXY_SOURCES = [
    "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/main/http_all.txt",
    "https://raw.githubusercontent.com/komutan234/Proxy-List-Free/main/proxies/http.txt",
    "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt",
]

INVISIBLE_CHARS = ["\u064C", "\u064C"]
ARABIC_DIACRITICS = [
    "\u064E", "\u064F", "\u0650", "\u064F", "\u064C",
    "\u064D", "\u0651", "\u0651", "\u0640", "\u0653"
]

# ==========================================
# 2. مدير البروكسيات
# ==========================================
class ProxyManager:
    def __init__(self):
        self.proxies = []
        self.current_index = 0
        self.fail_counts = {}
        self.success_counts = {}
        self.current_proxy = None

    def fetch_proxies(self):
        """جلب البروكسيات باستخدام curl_cffi (sync)"""
        all_proxies = set()
        print(f"[⌛] عدد المصادر: {len(PROXY_SOURCES)}")

        for idx, source in enumerate(PROXY_SOURCES, 1):
            try:
                r = curl_requests.get(source, headers=HEADERS, timeout=25)
                print(f"[ℹ] المصدر {idx} - كود: {r.status_code}")
                if r.status_code == 200:
                    source_proxies = set()
                    for line in r.text.strip().split("\n"):
                        line = line.strip()
                        if line and ":" in line and not line.startswith("#"):
                            if line.startswith("http://"):
                                line = line[7:]
                            elif line.startswith("https://"):
                                line = line[8:]
                            parts = line.split(":")
                            if len(parts) == 2 and parts[1].isdigit():
                                source_proxies.add(line)
                                all_proxies.add(line)
                    print(f"[✔] المصدر {idx}: {len(source_proxies)} بروكسي صالح")
                else:
                    print(f"[✘] المصدر {idx}: فشل (كود {r.status_code})")
            except Exception as e:
                print(f"[✘] المصدر {idx}: خطأ - {str(e)[:80]}")

        self.proxies = list(all_proxies)
        random.shuffle(self.proxies)
        print(f"[✔] إجمالي البروكسيات الفريدة: {len(self.proxies)}")
        return len(self.proxies) > 0

    async def test_proxy(self, proxy_str):
        """اختبار البروكسي على الموقع المستهدف"""
        try:
            async with curl_requests.AsyncSession(impersonate="chrome124") as s:
                r = await s.get(
                    FORM_PAGE_URL,
                    proxy=f"http://{proxy_str}",
                    headers=HEADERS,
                    timeout=10,
                )
                return r.status_code == 200
        except Exception:
            pass
        return False

    async def filter_working_proxies(self, max_test=30):
        if not self.proxies:
            print("[⚠] لا توجد بروكسيات للاختبار!")
            return False

        test_list = self.proxies[:max_test]
        print(f"[⌛] اختبار {len(test_list)} بروكسي على الموقع المستهدف...")

        working = []
        for i, proxy in enumerate(test_list):
            if await self.test_proxy(proxy):
                working.append(proxy)
                print(f"[✔] {i+1}/{len(test_list)} يعمل: {proxy}")
            else:
                print(f"[✘] {i+1}/{len(test_list)} فاشل: {proxy}")

        self.proxies = working
        self.fail_counts = {p: 0 for p in working}
        self.success_counts = {p: 0 for p in working}
        print(f"[✔] البروكسيات العاملة: {len(working)}")
        return len(working) > 0

    def get_next_proxy(self):
        if not self.proxies:
            return None
        attempts = 0
        while attempts < len(self.proxies):
            proxy = self.proxies[self.current_index]
            if self.fail_counts.get(proxy, 0) < 2:
                self.current_proxy = proxy
                return proxy
            self.current_index = (self.current_index + 1) % len(self.proxies)
            attempts += 1
        # إعادة تعيين
        print("[⚠] جميع البروكسيات فاشلة! إعادة التعيين...")
        for p in self.proxies:
            self.fail_counts[p] = 0
        self.current_index = 0
        self.current_proxy = self.proxies[0]
        return self.current_proxy

    def report_success(self, proxy):
        self.success_counts[proxy] = self.success_counts.get(proxy, 0) + 1
        self.fail_counts[proxy] = 0

    def report_failure(self, proxy):
        self.fail_counts[proxy] = self.fail_counts.get(proxy, 0) + 1
        print(f"[⚠] فشل {proxy} ({self.fail_counts[proxy]}/2)")
        if self.fail_counts[proxy] >= 2:
            print(f"[🔄] تبديل البروكسي: {proxy} فشل مرتين")
            self.current_index = (self.current_index + 1) % len(self.proxies)
            return self.get_next_proxy()
        return proxy

# ==========================================
# 3. المساعدات
# ==========================================
def load_names_from_file(filename="names.txt"):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            names = [line.strip() for line in f if line.strip()]
            if names:
                print(f"[✔] تم تحميل {len(names)} اسم")
                return names
    print("[⚠] ملف names.txt غير موجود! استخدام أسماء افتراضية.")
    return [
        "محمد أحمد عبدالله علي",
        "أحمد محمد سعيد محسن",
        "عبدالله علي محمد أحمد",
        "خالد سعيد عبدالرحمن علي",
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
    return f"{unique_name}{' ' * random.randint(0, 3)}"

def generate_random_phone():
    prefix = random.choice(YEMEN_PREFIXES)
    suffix = "".join([str(random.randint(0, 9)) for _ in range(7)])
    return f"{prefix}{suffix}"

# ==========================================
# 4. تجهيز الحمولة (بدون توكن - لا يوجد CSRF)
# ==========================================
def prepare_payload(names_list):
    raw_name = random.choice(names_list)
    unique_name = make_name_strictly_unique(raw_name)
    team_id = random.choice(list(ROUND_OF_16_TEAMS.keys()))
    team_name = ROUND_OF_16_TEAMS[team_id]

    # الحقول المطلوبة فقط - 4 حقول
    payload = {
        "customField_18": team_id,           # بطل كأس العالم
        "customField_19": unique_name,       # الاسم الرباعي
        "customField_20": generate_random_phone(),  # رقم الجوال
        "customField_24": random.choice(GOVERNORATES),  # المحافظة
    }
    return payload, team_name

def check_success(status, html):
    """التحقق من نجاح الإرسال"""
    if status != 200:
        return False

    # كلمات مفتاحية للنجاح
    success_keywords = ["شكرا", "تم بنجاح", "success", "thank", "شكراً", 
                        "تم الإرسال", "تمت المشاركة", "نجاح"]

    # كلمات مفتاحية للفشل
    fail_keywords = ["خطأ", "error", "فشل", "invalid", "مطلوب", "required"]

    html_lower = html.lower()

    has_success = any(k in html_lower for k in success_keywords)
    has_fail = any(k in html_lower for k in fail_keywords)

    return has_success or not has_fail

# ==========================================
# 5. إرسال الطلب
# ==========================================
async def send_request(request_num, names_list, proxy_manager):
    payload, team_name = prepare_payload(names_list)
    proxy = proxy_manager.get_next_proxy()
    if not proxy:
        print(f"[✘] لا يوجد بروكسي!")
        return False

    max_retries = 2
    attempt = 0
    current_proxy = proxy

    while attempt < max_retries:
        try:
            async with curl_requests.AsyncSession(impersonate="chrome124") as s:
                # إرسال كـ multipart/form-data (مطابق للنموذج الأصلي)
                r = await s.post(
                    TARGET_URL, 
                    data=payload,  # curl_cffi يتعامل مع الترميز تلقائياً
                    headers=HEADERS,
                    proxy=f"http://{current_proxy}", 
                    timeout=15
                )

                if check_success(r.status_code, r.text):
                    proxy_manager.report_success(current_proxy)
                    print(f"[🏆] #{request_num:02d} | {current_proxy} | {team_name} | نجاح (كود: {r.status_code})")
                    return True
                else:
                    print(f"[⚠] #{request_num:02d} | {current_proxy} | كود: {r.status_code} | رد غير متوقع")
                    new_proxy = proxy_manager.report_failure(current_proxy)
                    if new_proxy != current_proxy:
                        current_proxy = new_proxy
                        attempt += 1
                        print(f"[🔄] إعادة المحاولة {attempt}/{max_retries}")
                        continue
                    return False
        except Exception as e:
            print(f"[✘] #{request_num:02d} | {current_proxy} | {str(e)[:80]}")
            new_proxy = proxy_manager.report_failure(current_proxy)
            if new_proxy != current_proxy:
                current_proxy = new_proxy
                attempt += 1
                continue
            return False

    return False

# ==========================================
# 6. الدالة الرئيسية
# ==========================================
async def main():
    print("=" * 60)
    print("--- Vote Bot - Fixed Edition (No CSRF) ---")
    print("=" * 60)

    names_list = load_names_from_file("names.txt")
    proxy_manager = ProxyManager()

    # جلب البروكسيات (sync)
    print("\n[⌛] جاري جلب البروكسيات...")
    proxy_manager.fetch_proxies()

    # اختبار البروكسيات (async)
    print("\n[⌛] جاري اختبار البروكسيات...")
    await proxy_manager.filter_working_proxies(max_test=30)

    if not proxy_manager.proxies:
        print("[⚠] لا توجد بروكسيات عاملة! سأحاول بدون بروكسي...")

    # الدورات
    TOTAL_ROUNDS = 60000
    REQUESTS_PER_ROUND = 20

    for round_num in range(1, TOTAL_ROUNDS + 1):
        print(f"\n{'='*50}")
        print(f"--- الدورة {round_num}/{TOTAL_ROUNDS} ---")
        print(f"{'='*50}")

        tasks = [
            send_request(i, names_list, proxy_manager)
            for i in range(1, REQUESTS_PER_ROUND + 1)
        ]
        results = await asyncio.gather(*tasks)

        success_count = sum(1 for r in results if r)
        print(f"\n[📊] الدورة {round_num}: {success_count}/{REQUESTS_PER_ROUND} نجاح")

        if round_num < TOTAL_ROUNDS:
            wait_time = random.randint(5, 10)
            print(f"[⏳] انتظار {wait_time} ثوانٍ...")
            await asyncio.sleep(wait_time)

    print("\n" + "=" * 60)
    print("--- تم الانتهاء ---")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())

