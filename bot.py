import asyncio
import os
import random
import aiohttp
from bs4 import BeautifulSoup
import time
import sys

# ==========================================
# 1. الإعدادات الأساسية
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
    "16": "المغرب",
    "45": "مصر",
}

FORM_PAGE_URL = "https://quwatasad.com/worldcup2026"
TARGET_URL = "https://quwatasad.com/form-submit"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": FORM_PAGE_URL,
    "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
}

# مصادر بروكسيات متعددة وموثوقة
PROXY_SOURCES = [
    "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/main/http_all.txt",
    "https://raw.githubusercontent.com/komutan234/Proxy-List-Free/main/proxies/http.txt",
    "https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/http.txt",
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

    async def fetch_proxies(self, session):
        all_proxies = set()
        print(f"[⌛] عدد المصادر: {len(PROXY_SOURCES)}")

        for idx, source in enumerate(PROXY_SOURCES, 1):
            try:
                print(f"[⌛] جلب المصدر {idx}/{len(PROXY_SOURCES)}: {source[:60]}...")
                async with session.get(source, timeout=25, ssl=False) as resp:
                    print(f"[ℹ] المصدر {idx} - كود الاستجابة: {resp.status}")
                    if resp.status == 200:
                        text = await resp.text()
                        lines = text.strip().split('\n')
                        source_proxies = set()
                        for line in lines:
                            line = line.strip()
                            if line and ':' in line and not line.startswith('#'):
                                # تنظيف البروكسي
                                if line.startswith('http://'):
                                    line = line[7:]
                                elif line.startswith('https://'):
                                    line = line[8:]
                                # التأكد من صحة التنسيق ip:port
                                parts = line.split(':')
                                if len(parts) == 2 and parts[1].isdigit():
                                    source_proxies.add(line)
                                    all_proxies.add(line)
                        print(f"[✔] المصدر {idx}: {len(source_proxies)} بروكسي صالح")
                    else:
                        print(f"[✘] المصدر {idx}: فشل (كود {resp.status})")
            except Exception as e:
                print(f"[✘] المصدر {idx}: خطأ - {str(e)[:80]}")

        self.proxies = list(all_proxies)
        random.shuffle(self.proxies)
        print(f"[✔] إجمالي البروكسيات الفريدة: {len(self.proxies)}")
        return len(self.proxies) > 0

    async def test_proxy(self, session, proxy_str):
        """اختبار البروكسي على الموقع المستهدف مباشرة"""
        proxy_url = f"http://{proxy_str}"
        try:
            async with session.get(
                FORM_PAGE_URL,
                proxy=proxy_url,
                headers=HEADERS,
                timeout=aiohttp.ClientTimeout(total=10),
                ssl=False
            ) as resp:
                if resp.status in [200, 301, 302]:
                    return True
        except Exception:
            pass
        return False

    async def filter_working_proxies(self, session, max_test=50):
        if not self.proxies:
            print("[⚠] لا توجد بروكسيات للاختبار!")
            return False

        test_list = self.proxies[:max_test]
        print(f"[⌛] اختبار {len(test_list)} بروكسي على الموقع المستهدف...")

        working = []
        for i, proxy in enumerate(test_list):
            if await self.test_proxy(session, proxy):
                working.append(proxy)
                print(f"[✔] بروكسي {i+1}/{len(test_list)} يعمل: {proxy}")
            else:
                print(f"[✘] بروكسي {i+1}/{len(test_list)} فاشل: {proxy}")

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
# 3. دوال المساعدة
# ==========================================
def load_names_from_file(filename="names.txt"):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            names = [line.strip() for line in f if line.strip()]
            if names:
                print(f"[✔] تم تحميل {len(names)} اسم")
                return names
    print(f"[⚠] ملف {filename} غير موجود! استخدام أسماء افتراضية.")
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
# 4. جلب بيانات النموذج
# ==========================================
async def fetch_live_form_data(session, proxy_manager):
    print("[⌛] جاري جلب التوكن...")

    # أولاً: محاولة بدون بروكسي (أسرع)
    print("[⌛] محاولة 1/1: جلب التوكن بدون بروكسي...")
    try:
        async with session.get(
            FORM_PAGE_URL, 
            headers=HEADERS, 
            timeout=aiohttp.ClientTimeout(total=15),
            ssl=False
        ) as response:
            print(f"[ℹ] بدون بروكسي - كود: {response.status}")
            if response.status == 200:
                html_content = await response.text()
                soup = BeautifulSoup(html_content, "html.parser")

                token_input = soup.find("input", {"name": "_token"})
                if token_input and token_input.get("value"):
                    live_fields = {
                        "_token": token_input.get("value"),
                        "date": "2026-07-06",
                        "section_id": "0",
                        "TopicID": "152",
                        "WebmasterSectionId": "",
                    }
                    print("[✔] جلب التوكن نجح بدون بروكسي!")
                    return live_fields
                else:
                    print("[⚠] التوكن غير موجود في الصفحة (بدون بروكسي)")
    except Exception as e:
        print(f"[✘] فشل بدون بروكسي: {str(e)[:80]}")

    # ثانياً: محاولة بالبروكسيات
    print("[⌛] محاولة بالبروكسيات...")
    for attempt in range(1, 6):
        proxy = proxy_manager.get_next_proxy()
        if not proxy:
            print("[✘] لا يوجد بروكسي متاح!")
            break

        proxy_url = f"http://{proxy}"
        try:
            print(f"[⌛] محاولة {attempt}/5 عبر: {proxy}")
            async with session.get(
                FORM_PAGE_URL, 
                headers=HEADERS, 
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=12),
                ssl=False
            ) as response:
                print(f"[ℹ] بروكسي {proxy} - كود: {response.status}")
                if response.status == 200:
                    html_content = await response.text()
                    soup = BeautifulSoup(html_content, "html.parser")

                    token_input = soup.find("input", {"name": "_token"})
                    if token_input and token_input.get("value"):
                        live_fields = {
                            "_token": token_input.get("value"),
                            "date": "2026-07-06",
                            "section_id": "0",
                            "TopicID": "152",
                            "WebmasterSectionId": "",
                        }
                        print(f"[✔] جلب التوكن نجح عبر: {proxy}")
                        proxy_manager.report_success(proxy)
                        return live_fields
                    else:
                        print(f"[⚠] التوكن غير موجود (بروكسي: {proxy})")
                        proxy_manager.report_failure(proxy)
                else:
                    print(f"[⚠] كود {response.status} من {proxy}")
                    proxy_manager.report_failure(proxy)
        except Exception as e:
            print(f"[✘] فشل البروكسي {proxy}: {str(e)[:80]}")
            proxy_manager.report_failure(proxy)

        await asyncio.sleep(1)

    print("[🛑] فشل جلب التوكن نهائياً!")
    return None

# ==========================================
# 5. تجهيز الحمولة
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

def check_submission_success(status, html_text):
    success_keywords = ["شكرا", "تم بنجاح", "success", "thank", "شكراً"]
    is_success = any(kw in html_text.lower() for kw in success_keywords)
    return (status == 200 or is_success), "نجاح" if (status == 200 or is_success) else f"كود: {status}"

# ==========================================
# 6. إرسال الطلب
# ==========================================
async def send_request(session, request_num, live_fields, names_list, proxy_manager):
    payload, team_name = prepare_payload(live_fields, names_list)

    proxy = proxy_manager.get_next_proxy()
    if not proxy:
        print(f"[✘] لا يوجد بروكسي!")
        return False

    proxy_url = f"http://{proxy}"
    max_retries = 2
    attempt = 0

    while attempt < max_retries:
        try:
            async with session.post(
                TARGET_URL, 
                data=payload, 
                headers=HEADERS, 
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=15),
                ssl=False
            ) as response:
                status = response.status
                html_text = await response.text()
                is_success, message = check_submission_success(status, html_text)

                if is_success:
                    proxy_manager.report_success(proxy)
                    print(f"[🏆] #{request_num:02d} | {proxy} | {team_name} | نجاح")
                    return True
                else:
                    print(f"[⚠] #{request_num:02d} | {proxy} | {message}")
                    new_proxy = proxy_manager.report_failure(proxy)
                    if new_proxy != proxy:
                        proxy = new_proxy
                        proxy_url = f"http://{proxy}"
                        attempt += 1
                        print(f"[🔄] إعادة المحاولة {attempt}/{max_retries} بـ {proxy}")
                        continue
                    return False

        except Exception as e:
            print(f"[✘] #{request_num:02d} | {proxy} | {str(e)[:60]}")
            new_proxy = proxy_manager.report_failure(proxy)
            if new_proxy != proxy:
                proxy = new_proxy
                proxy_url = f"http://{proxy}"
                attempt += 1
                print(f"[🔄] إعادة المحاولة {attempt}/{max_retries} بـ {proxy}")
                continue
            return False

    print(f"[✘] #{request_num:02d} فشل بعد {max_retries} محاولات")
    return False

# ==========================================
# 7. الدالة الرئيسية
# ==========================================
async def main():
    print("=" * 60)
    print("--- سكربت التصويت - GitHub Actions Edition ---")
    print("=" * 60)

    names_list = load_names_from_file("names.txt")
    proxy_manager = ProxyManager()

    connector = aiohttp.TCPConnector(limit=50, limit_per_host=30, ssl=False)
    timeout = aiohttp.ClientTimeout(total=300)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:

        # جلب البروكسيات
        print("\n[⌛] جاري جلب البروكسيات...")
        has_proxies = await proxy_manager.fetch_proxies(session)

        if has_proxies:
            print("\n[⌛] جاري اختبار البروكسيات...")
            await proxy_manager.filter_working_proxies(session, max_test=50)

        if not proxy_manager.proxies:
            print("[⚠] لا توجد بروكسيات عاملة! سأحاول بدون بروكسي...")

        # جلب التوكن
        live_fields = await fetch_live_form_data(session, proxy_manager)
        if not live_fields:
            print("[🛑] توقف السكربت: فشل جلب التوكن.")
            return

        # تشغيل الدورات
        TOTAL_ROUNDS = 6
        REQUESTS_PER_ROUND = 20

        for round_num in range(1, TOTAL_ROUNDS + 1):
            print(f"\n{'='*50}")
            print(f"--- الدورة {round_num}/{TOTAL_ROUNDS} ---")
            print(f"{'='*50}")

            tasks = [
                send_request(session, i, live_fields, names_list, proxy_manager)
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

