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
    "27": "النرويج",
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

# مصادر البروكسيات المجانية
PROXY_SOURCES = [
    "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text",
    "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt",
    "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/https/data.txt",
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
        self.lock = asyncio.Lock()
    
    async def fetch_proxies(self, session):
        all_proxies = set()
        for source in PROXY_SOURCES:
            try:
                async with session.get(source, timeout=20) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        for line in text.strip().split('\n'):
                            line = line.strip()
                            if line and ':' in line:
                                if line.startswith('http://'):
                                    line = line[7:]
                                elif line.startswith('https://'):
                                    line = line[8:]
                                all_proxies.add(line)
                        print(f"[✔] جلبت {len(all_proxies)} بروكسي من {source[:50]}...")
            except Exception as e:
                print(f"[⚠] فشل جلب {source[:50]}: {e}")
        
        self.proxies = list(all_proxies)
        random.shuffle(self.proxies)
        print(f"[✔] إجمالي البروكسيات المجلبة: {len(self.proxies)}")
        return len(self.proxies) > 0
    
    async def test_proxy(self, session, proxy_str):
        proxy_url = f"http://{proxy_str}"
        try:
            async with session.get(
                "https://httpbin.org/ip",
                proxy=proxy_url,
                timeout=aiohttp.ClientTimeout(total=10),
                ssl=False
            ) as resp:
                if resp.status == 200:
                    return True
        except:
            pass
        return False
    
    async def filter_working_proxies(self, session, max_test=30):
        if not self.proxies:
            return False
        
        test_list = self.proxies[:max_test]
        tasks = [self.test_proxy(session, p) for p in test_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        working = []
        for proxy, is_working in zip(test_list, results):
            if is_working is True:
                working.append(proxy)
        
        self.proxies = working
        self.fail_counts = {p: 0 for p in working}
        self.success_counts = {p: 0 for p in working}
        
        print(f"[✔] البروكسيات العاملة بعد الاختبار: {len(working)}")
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
    proxy = proxy_manager.get_next_proxy()
    proxy_url = f"http://{proxy}" if proxy else None
    
    try:
        async with session.get(
            FORM_PAGE_URL, 
            headers=HEADERS, 
            proxy=proxy_url,
            timeout=15,
            ssl=False
        ) as response:
            if response.status != 200:
                print(f"[✘] فشل جلب الصفحة: {response.status}")
                return None

            html_content = await response.text()
            soup = BeautifulSoup(html_content, "html.parser")

            token_input = soup.find("input", {"name": "_token"})
            topic_id_input = soup.find("input", {"name": "TopicID"})
            webmaster_id_input = soup.find("input", {"name": "WebmasterSectionId"})
            date_input = soup.find("input", {"name": "date"})
            section_id_input = soup.find("input", {"name": "section_id"})

            live_fields = {
                "_token": token_input.get("value", "mock_token") if token_input else "mock_token",
                "date": date_input.get("value", "2026-07-06") if date_input else "2026-07-06",
                "section_id": section_id_input.get("value", "0") if section_id_input else "0",
                "TopicID": topic_id_input.get("value", "152") if topic_id_input else "152",
                "WebmasterSectionId": webmaster_id_input.get("value", "") if webmaster_id_input else "",
            }

            print(f"[✔] جلب التوكن نجح عبر: {proxy}")
            proxy_manager.report_success(proxy)
            return live_fields
    except Exception as e:
        print(f"[✘] خطأ: {str(e)[:80]}")
        if proxy:
            proxy_manager.report_failure(proxy)
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
# 6. إرسال الطلب مع إعادة المحاولة
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
        await proxy_manager.fetch_proxies(session)
        
        print("\n[⌛] جاري اختبار البروكسيات...")
        await proxy_manager.filter_working_proxies(session, max_test=30)
        
        if not proxy_manager.proxies:
            print("[🛑] لا توجد بروكسيات عاملة! إيقاف.")
            return
        
        # جلب التوكن
        live_fields = await fetch_live_form_data(session, proxy_manager)
        if not live_fields:
            print("[🛑] فشل جلب التوكن! إيقاف.")
            return

        # تشغيل الدورات
        TOTAL_ROUNDS = 6
        REQUESTS_PER_ROUND = 20  # تقليل العدد لتناسب GitHub Actions
        
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

