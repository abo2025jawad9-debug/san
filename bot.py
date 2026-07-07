import asyncio
import os
import random
import time
import sys
from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup

# ==========================================
# الإعدادات الأساسية
# ==========================================
TOTAL_REQUESTS = int(os.getenv('TOTAL_REQUESTS', '50'))
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '2'))
DELAY_MIN = int(os.getenv('DELAY_MIN', '8'))
DELAY_MAX = int(os.getenv('DELAY_MAX', '20'))

# الاسم الأساسي الذي سيتم تشكيله عشوائياً
BASE_NAME = "محمد لطف يحيى علي"

YEMEN_PREFIXES = ["77", "78", "73", "70", "71"]
GOVERNORATES = [str(i) for i in range(1, 23)]

ALL_TEAMS = {
    "1": "الأرجنتين", "2": "الأردن", "3": "أستراليا", "4": "أوزبكستان",
    "5": "ألمانيا", "6": "أوروغواي", "7": "إسكتلندا", "8": "إسبانيا",
    "9": "إنجلترا", "10": "إيران", "11": "الإكوادور", "12": "البرازيل",
    "13": "البرتغال", "14": "البوسنة والهرسك", "15": "التشيك", "16": "الجزائر",
    "17": "الرأس الأخضر", "18": "السعودية", "19": "السنغال", "20": "السويد",
    "21": "العراق", "22": "كوريا الجنوبية", "23": "الكونغو", "24": "المغرب",
    "25": "المكسيك", "26": "النمسا", "27": "النرويج", "28": "اليابان",
    "29": "الولايات المتحدة", "30": "باراغواي", "31": "بنما", "32": "بلجيكا",
    "33": "سويسرا", "34": "تركيا", "35": "تونس", "36": "جنوب إفريقيا",
    "37": "غانا", "38": "فرنسا", "39": "قطر", "40": "كرواتيا",
    "41": "كندا", "42": "كولومبيا", "43": "كوراساو", "44": "ساحل العاج",
    "45": "مصر", "46": "نيوزيلندا", "47": "هايتي", "48": "هولندا",
}

FORM_PAGE_URL = "https://quwatasad.com/worldcup2026"
TARGET_URL = "https://quwatasad.com/form-submit"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
]

def get_headers():
    ua = random.choice(USER_AGENTS)
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ar-YE,ar;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

# ==========================================
# مدير البروكسيات
# ==========================================
PROXY_SOURCES = [
    "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/http.txt",
    "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/main/http_all.txt",
    "https://raw.githubusercontent.com/komutan234/Proxy-List-Free/main/proxies/http.txt",
    "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt",
]

class ProxyManager:
    def __init__(self):
        self.proxies = []
        self.current_index = 0
        self.fail_counts = {}
        self.success_counts = {}
        self.current_proxy = None

    def fetch_proxies(self):
        all_proxies = set()
        print(f"[⌛] جلب البروكسيات من {len(PROXY_SOURCES)} مصادر...")

        for idx, source in enumerate(PROXY_SOURCES, 1):
            try:
                r = curl_requests.get(source, timeout=25, impersonate="chrome120")
                if r.status_code == 200:
                    for line in r.text.strip().split("\n"):
                        line = line.strip()
                        if line and ":" in line and not line.startswith("#"):
                            if line.startswith("http://"):
                                line = line[7:]
                            elif line.startswith("https://"):
                                line = line[8:]
                            parts = line.split(":")
                            if len(parts) == 2 and parts[1].isdigit():
                                all_proxies.add(line)
            except Exception as e:
                print(f"[✘] المصدر {idx}: فشل الجلب")

        self.proxies = list(all_proxies)
        random.shuffle(self.proxies)
        print(f"[✔] إجمالي البروكسيات الفريدة: {len(self.proxies)}")
        return len(self.proxies) > 0

    async def test_proxy(self, proxy_str):
        try:
            async with curl_requests.AsyncSession(impersonate="chrome120") as s:
                r = await s.get(
                    "https://httpbin.org/ip",
                    proxy=f"http://{proxy_str}",
                    timeout=10,
                )
                return r.status_code == 200
        except Exception:
            return False

    async def filter_working_proxies(self, max_test=30):
        if not self.proxies:
            print("[⚠] لا توجد بروكسيات!")
            return False

        test_list = self.proxies[:max_test]
        print(f"[⌛] اختبار {len(test_list)} بروكسي...")

        working = []
        for i, proxy in enumerate(test_list):
            if await self.test_proxy(proxy):
                working.append(proxy)
                print(f"[✔] {i+1}/{len(test_list)} يعمل: {proxy}")
            elif i % 5 == 0:
                print(f"[✘] {i+1}/{len(test_list)} فاشل...")

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
            if self.fail_counts.get(proxy, 0) < 3:
                self.current_proxy = proxy
                return proxy
            self.current_index = (self.current_index + 1) % len(self.proxies)
            attempts += 1

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
        if self.fail_counts[proxy] >= 3:
            print(f"[🔄] استبعاد: {proxy}")
            self.current_index = (self.current_index + 1) % len(self.proxies)
            return self.get_next_proxy()
        return proxy

# ==========================================
# توليد زخرفة فريدة (بالحركات فقط)
# ==========================================
def apply_random_tashkeel(name):
    """إضافة حركات (تخيلية/عشوائية) للاسم لجعله فريداً برمجياً دون تغيير الحروف"""
    # قائمة الحركات: تنوين فتح، تنوين ضم، تنوين كسر، فتحة، ضمة، كسرة، شدة، سكون
    tashkeel = ['\u064B', '\u064C', '\u064D', '\u064E', '\u064F', '\u0650', '\u0651', '\u0652']
    decorated_name = ""
    for char in name:
        decorated_name += char
        # تجاهل المسافات، وإضافة حركة عشوائية باحتمال 60% لكل حرف
        if char != " " and random.random() > 0.4:
            decorated_name += random.choice(tashkeel)
    return decorated_name

def prepare_payload():
    """تجهيز البيانات"""
    unique_name = apply_random_tashkeel(BASE_NAME)
    team_id = random.choice(list(ALL_TEAMS.keys()))

    payload = {
        "customField_18": team_id,
        "customField_19": unique_name,
        "customField_20": generate_phone(),
        "customField_24": random.choice(GOVERNORATES),
    }
    return payload, ALL_TEAMS[team_id], unique_name

def generate_phone():
    """توليد رقم هاتف يمني صحيح"""
    prefix = random.choice(YEMEN_PREFIXES)
    suffix = "".join([str(random.randint(0, 9)) for _ in range(7)])
    return f"{prefix}{suffix}"

def check_success(response):
    """التحقق من نجاح الإرسال"""
    if response.status_code in [301, 302, 303, 307, 308]:
        return True, f"redirect_{response.status_code}"

    try:
        json_data = response.json()
        if any(k in str(json_data).lower() for k in ["success", "true", "ok", "شكرا", "تم"]):
            return True, "json_success"
    except:
        pass

    html = response.text.lower()
    success_kw = ["شكرا", "تم بنجاح", "success", "thank", "شكراً", "تم الإرسال", "تمت المشاركة", "نجاح", "تم التسجيل"]
    fail_kw = ["خطأ", "error", "فشل", "invalid", "مطلوب", "required", "csrf", "token", "مكرر", "duplicate"]

    has_success = any(k in html for k in success_kw)
    has_fail = any(k in html for k in fail_kw)

    if has_success and not has_fail:
        return True, "html_success"
    if has_fail:
        return False, "html_fail"

    if response.status_code == 200:
        return True, "status_200"

    return False, f"status_{response.status_code}"

# ==========================================
# إرسال الطلب
# ==========================================
async def send_request(request_num, proxy_manager):
    payload, team_name, unique_name = prepare_payload()
    proxy = proxy_manager.get_next_proxy()

    if not proxy:
        print(f"[✘] #{request_num:02d} | لا يوجد بروكسي!")
        return False

    max_retries = 2
    attempt = 0
    current_proxy = proxy

    while attempt <= max_retries:
        try:
            async with curl_requests.AsyncSession(impersonate="chrome120") as s:
                headers = get_headers()

                try:
                    page_resp = await s.get(
                        FORM_PAGE_URL,
                        proxy=f"http://{current_proxy}",
                        headers=headers,
                        timeout=15,
                    )
                    soup = BeautifulSoup(page_resp.text, 'html.parser')
                    hidden_inputs = soup.find_all('input', type='hidden')
                    for inp in hidden_inputs:
                        if inp.get('name') and inp.get('value'):
                            payload[inp['name']] = inp['value']
                except Exception as e:
                    pass # يتم التجاهل للاستمرار في الإرسال

                await asyncio.sleep(random.uniform(0.5, 2))

                headers["Referer"] = FORM_PAGE_URL
                headers["Origin"] = "https://quwatasad.com"

                r = await s.post(
                    TARGET_URL,
                    data=payload,
                    headers=headers,
                    proxy=f"http://{current_proxy}",
                    timeout=20,
                )

                success, reason = check_success(r)

                if success:
                    proxy_manager.report_success(current_proxy)
                    print(f"[🏆] #{request_num:02d} | {current_proxy} | {team_name} | الاسم: {unique_name} | نجاح ({reason})")
                    return True
                else:
                    print(f"[⚠] #{request_num:02d} | {current_proxy} | {team_name} | الاسم: {unique_name} | فشل: {reason}")
                    new_proxy = proxy_manager.report_failure(current_proxy)
                    if new_proxy != current_proxy:
                        current_proxy = new_proxy
                        attempt += 1
                        await asyncio.sleep(random.uniform(1, 3))
                        continue
                    return False

        except Exception as e:
            print(f"[✘] #{request_num:02d} | {current_proxy} | خطأ في الاتصال")
            new_proxy = proxy_manager.report_failure(current_proxy)
            if new_proxy != current_proxy:
                current_proxy = new_proxy
                attempt += 1
                await asyncio.sleep(random.uniform(1, 3))
                continue
            return False

    return False

# ==========================================
# الدالة الرئيسية
# ==========================================
async def main():
    print("=" * 60)
    print("--- Vote Bot Script ---")
    print(f"--- الاسم الأصلي: {BASE_NAME} ---")
    print(f"--- الطلبات: {TOTAL_REQUESTS} | الدفعة: {BATCH_SIZE} ---")
    print("=" * 60)

    proxy_manager = ProxyManager()

    print("\n[⌛] جاري جلب البروكسيات...")
    proxy_manager.fetch_proxies()

    print("\n[⌛] جاري اختبار البروكسيات...")
    await proxy_manager.filter_working_proxies(max_test=30)

    if not proxy_manager.proxies:
        print("[⚠] لا توجد بروكسيات عاملة! إيقاف...")
        return

    completed = 0
    successful = 0

    while completed < TOTAL_REQUESTS:
        batch = min(BATCH_SIZE, TOTAL_REQUESTS - completed)
        print(f"\n{'='*50}")
        print(f"--- الدفعة {(completed//BATCH_SIZE)+1} | {completed+1}-{completed+batch}/{TOTAL_REQUESTS} ---")
        print(f"{'='*50}")

        tasks = [
            send_request(completed + i + 1, proxy_manager)
            for i in range(batch)
        ]
        results = await asyncio.gather(*tasks)

        batch_success = sum(1 for r in results if r)
        successful += batch_success
        completed += batch

        print(f"\n[📊] الدفعة: {batch_success}/{batch} | إجمالي: {successful}/{completed}")

        if completed < TOTAL_REQUESTS:
            wait_time = random.randint(DELAY_MIN, DELAY_MAX)
            print(f"[⏳] انتظار {wait_time} ثانية...")
            await asyncio.sleep(wait_time)

    print("\n" + "=" * 60)
    print(f"--- انتهى | النجاح: {successful}/{TOTAL_REQUESTS} ---")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
