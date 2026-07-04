import asyncio
import os
import random
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from curl_cffi import requests

# ==========================================
# 1. الإعدادات
# ==========================================
FORM_PAGE_URL = "https://quwatasad.com/worldcup2026"
TARGET_URL = "https://quwatasad.com/form-submit"

YEMEN_PREFIXES = ["77", "78", "73", "71", "70"]
GOVERNORATES = [str(i) for i in range(1, 23)]

TEAMS = {
    "1": "الأرجنتين", "2": "الأردن", "3": "أستراليا", "4": "أوزبكستان",
    "5": "ألمانيا", "6": "أوروغواي", "7": "إسكتلندا", "8": "إسبانيا",
    "9": "إنجلترا", "10": "إيران", "11": "الإكوادور", "12": "البرازيل",
    "13": "البرتغال", "14": "البوسنة والهرسك", "15": "التشيك", "16": "الجزائر",
    "17": "الرأس الأخضر(كاب فيردي)", "18": "السعودية", "19": "السنغال", "20": "السويد",
    "21": "العراق", "22": "كوريا الجنوبية", "23": "الكونغو", "24": "المغرب",
    "25": "المكسيك", "26": "النمسا", "27": "النرويج", "28": "اليابان",
    "29": "الولايات المتحدة الأمريكية", "30": "باراغواي", "31": "بنما", "32": "بلجيكا",
    "33": "سويسرا", "34": "تركيا", "35": "تونس", "36": "جنوب إفريقيا",
    "37": "غانا", "38": "فرنسا", "39": "قطر", "40": "كرواتيا",
    "41": "كندا", "42": "كولومبيا", "43": "كوراساو", "44": "ساحل العاج (كوت ديفوار)",
    "45": "مصر", "46": "نيوزيلندا", "47": "هايتي", "48": "هولندا",
}

INVISIBLE_CHARS = ["\u200C", "\u200D", "\u2060", "\uFEFF", "\u180E"]
ARABIC_DIACRITICS = [
    "\u064E", "\u064F", "\u0650", "\u064B", "\u064C",
    "\u064D", "\u0651", "\u0652", "\u0653", "\u0670"
]

ARAB_COUNTRY_CODES = [
    "sa", "eg", "ae", "jo", "kw", "qa", "om", "bh", "iq", "lb",
    "ma", "tn", "dz", "ly", "sd", "so", "dj", "km", "mr", "ps", "ye"
]

ARAB_COUNTRY_NAMES = {
    "sa": "السعودية", "eg": "مصر", "ae": "الإمارات", "jo": "الأردن",
    "kw": "الكويت", "qa": "قطر", "om": "عمان", "bh": "البحرين",
    "iq": "العراق", "lb": "لبنان", "ma": "المغرب", "tn": "تونس",
    "dz": "الجزائر", "ly": "ليبيا", "sd": "السودان", "so": "الصومال",
    "dj": "جيبوتي", "km": "جزر القمر", "mr": "موريتانيا", "ps": "فلسطين", "ye": "اليمن"
}

# ✅ متنوعات للتمويه
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

IMPERSONATE_VARIANTS = ["chrome120", "chrome119", "chrome118", "safari17_2_1", "safari17_0"]

# ==========================================
# 2. جلب بروكسيات عربية
# ==========================================
def fetch_arab_proxies(max_per_source=80):
    proxies = []

    try:
        countries = ",".join(ARAB_COUNTRY_CODES)
        url = f"https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text&country={countries}"
        print(f"[🌐] ProxyScrape...")
        resp = requests.get(url, impersonate="chrome120", timeout=15)
        if resp.status_code == 200 and resp.text.strip():
            lines = [line.strip() for line in resp.text.strip().split("\n") if line.strip()]
            for line in lines:
                if line.startswith("http://") or line.startswith("https://"):
                    proxies.append(line)
                elif ":" in line and not line.startswith("http"):
                    proxies.append(f"http://{line}")
            print(f"   ✔ {len(lines)} بروكسي")
    except Exception as e:
        print(f"   ✘ ProxyScrape: {e}")

    try:
        print(f"[🌐] free-proxy-list...")
        url = "https://free-proxy-list.net/"
        resp = requests.get(url, impersonate="chrome120", timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            table = soup.find("table", {"class": "table-striped"})
            if table:
                rows = table.find("tbody").find_all("tr") if table.find("tbody") else []
                count = 0
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) >= 8:
                        ip = cols[0].text.strip()
                        port = cols[1].text.strip()
                        country_code = cols[2].text.strip().lower()
                        if country_code in ARAB_COUNTRY_CODES:
                            proxies.append(f"http://{ip}:{port}")
                            count += 1
                print(f"   ✔ {count} بروكسي عربي")
    except Exception as e:
        print(f"   ✘ free-proxy-list: {e}")

    try:
        print(f"[🌐] proxy-list.download...")
        url = "https://www.proxy-list.download/api/v1/get?type=http"
        resp = requests.get(url, impersonate="chrome120", timeout=15)
        if resp.status_code == 200:
            lines = [line.strip() for line in resp.text.strip().split("\n") if line.strip()]
            for line in lines[:max_per_source]:
                if ":" in line and not line.startswith("http"):
                    proxies.append(f"http://{line}")
            print(f"   ✔ {len(lines[:max_per_source])} بروكسي")
    except Exception as e:
        print(f"   ✘ proxy-list: {e}")

    proxies = list(dict.fromkeys(proxies))
    random.shuffle(proxies)
    print(f"\n[📊] إجمالي فريد: {len(proxies)}")
    return proxies

# ==========================================
# 3. اختبار البروكسي الواحد
# ==========================================
def test_single_proxy(proxy_url):
    proxies = {"http": proxy_url, "https": proxy_url}
    try:
        start = time.time()
        resp = requests.get(
            FORM_PAGE_URL,
            proxies=proxies,
            timeout=10,
            impersonate="chrome120",
            allow_redirects=True
        )
        latency = time.time() - start
        if resp.status_code == 200 and len(resp.text) > 1000:
            return (proxy_url, latency, True)
    except Exception:
        pass
    return (proxy_url, 999, False)

def test_proxies(proxy_list, max_workers=50, min_working=15):
    if not proxy_list:
        return []
    working = []
    print(f"\n[🔬] اختبار {len(proxy_list)} بروكسي...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(test_single_proxy, p): p for p in proxy_list}
        for future in as_completed(futures):
            proxy, latency, is_working = future.result()
            if is_working:
                working.append((proxy, latency))
                print(f"   ✔ #{len(working)}: {proxy[:40]} | {latency:.1f}s")
                if len(working) >= min_working:
                    # نجمع أكثر قليلاً ثم نتوقف
                    if len(working) >= min_working + 5:
                        for f in futures:
                            f.cancel()
                        break

    working.sort(key=lambda x: x[1])
    print(f"\n[✅] عاملة: {len(working)}")
    return [p[0] for p in working]

# ==========================================
# 4. المساعدات
# ==========================================
def load_names_from_file(filename="names.txt"):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            names = [line.strip() for line in f if line.strip()]
            if names:
                print(f"[✔] {len(names)} اسم")
                return names
    print(f"[⚠] ملف {filename} غير موجود! استخدام افتراضي.")
    return [
        "محمد لطف يحيى الزيلعي", "أحمد صالح سعيد علي",
        "خالد صالح محمود سالم", "عبدالله صالح فؤاد عمر",
        "علي محمد أحمد القاضي", "فهد عبدالرحمن سالم باسليم",
        "سعيد علي محسن الجابري", "ناصر صالح عبدالله الهتاري",
    ]

def make_name_unique(name):
    hidden_prob = random.uniform(0.10, 0.25)
    diacritic_prob = random.uniform(0.05, 0.15)
    unique_name = ""
    for i, char in enumerate(name):
        unique_name += char
        if char != " ":
            if random.random() < hidden_prob:
                unique_name += random.choice(INVISIBLE_CHARS)
            if random.random() < diacritic_prob and i % 3 == 0:
                unique_name += random.choice(ARABIC_DIACRITICS)
    return unique_name.strip()

def generate_phone():
    prefix = random.choice(YEMEN_PREFIXES)
    suffix = ''.join(str(random.randint(0, 9)) for _ in range(7))
    return f"{prefix}{suffix}"

def get_random_headers():
    ua = random.choice(USER_AGENTS)
    langs = [
        "ar,en-US;q=0.9,en;q=0.8",
        "ar-YE,ar;q=0.9,en-US;q=0.8,en;q=0.7",
        "ar-SA,ar;q=0.9,en;q=0.8",
    ]
    return {
        "User-Agent": ua,
        "Referer": FORM_PAGE_URL,
        "Accept-Language": random.choice(langs),
        "Origin": "https://quwatasad.com",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
    }

# ==========================================
# 5. إرسال طلب واحد = بروكسي واحد
# ==========================================
async def send_one_request(request_num, names_list, proxy_url, semaphore):
    async with semaphore:
        if not proxy_url:
            return False

        impersonate = random.choice(IMPERSONATE_VARIANTS)
        session = requests.Session(impersonate=impersonate)
        headers = get_random_headers()
        proxies = {"http": proxy_url, "https": proxy_url}

        try:
            # GET - جلب التوكن
            def do_get():
                return session.get(FORM_PAGE_URL, headers=headers, proxies=proxies, timeout=15, allow_redirects=True)

            resp_get = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, do_get),
                timeout=20
            )

            if resp_get.status_code != 200 or len(resp_get.text) < 1000:
                session.close()
                return False

            soup = BeautifulSoup(resp_get.text, "html.parser")
            token = (soup.find("input", {"name": "_token"}) or {}).get("value", "")
            if not token:
                session.close()
                return False

            # تحضير البيانات
            raw_name = random.choice(names_list)
            unique_name = make_name_unique(raw_name)
            team_id = random.choice(list(TEAMS.keys()))
            team_name = TEAMS[team_id]

            payload = {
                "_token": token,
                "date": (soup.find("input", {"name": "date"}) or {}).get("value", "2026-07-05"),
                "section_id": (soup.find("input", {"name": "section_id"}) or {}).get("value", "0"),
                "TopicID": (soup.find("input", {"name": "TopicID"}) or {}).get("value", "152"),
                "WebmasterSectionId": (soup.find("input", {"name": "WebmasterSectionId"}) or {}).get("value", ""),
                "customField_18": team_id,
                "customField_19": unique_name,
                "customField_20": generate_phone(),
                "customField_24": random.choice(GOVERNORATES),
            }

            # POST - إرسال النموذج
            post_headers = headers.copy()
            post_headers["Content-Type"] = "application/x-www-form-urlencoded"

            def do_post():
                return session.post(TARGET_URL, data=payload, headers=post_headers, proxies=proxies, timeout=15, allow_redirects=True)

            resp_post = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, do_post),
                timeout=20
            )

            # فحص النجاح
            text_lower = resp_post.text.lower()
            keywords = ["شكرا", "تم بنجاح", "success", "thank", "تم الإرسال", "تم التسجيل", "تم الاشتراك", "redirect"]
            is_success = resp_post.status_code == 200 and any(kw in text_lower for kw in keywords)

            if is_success:
                print(f"[🏆 نجاح] الطلب {request_num:02d} | {team_name} | {proxy_url[:35]}...")
            else:
                if request_num <= 3:
                    print(f"[DEBUG] طلب {request_num}: status={resp_post.status_code}, url={resp_post.url}, text={resp_post.text[:150]}")

            session.close()
            return is_success

        except Exception as e:
            session.close()
            return False

# ==========================================
# 6. التشغيل الرئيسي - كل بروكسي = طلب واحد
# ==========================================
async def main():
    print("=" * 60)
    print("--- قوة أسد v3: كل بروكسي = طلب واحد ---")
    print("=" * 60)

    names_list = load_names_from_file("names.txt")
    total_success = 0
    total_attempts = 0

    for round_num in range(1, 7):
        print(f"\n{'='*50}")
        print(f"--- الدورة {round_num} من 6 ---")
        print(f"{'='*50}")

        # جلب + اختبار بروكسيات جديدة
        print("[🌐] جلب بروكسيات...")
        raw_proxies = fetch_arab_proxies(max_per_source=80)

        if not raw_proxies:
            print("[✘] لا يوجد بروكسيات!")
            continue

        working_proxies = test_proxies(raw_proxies, max_workers=50, min_working=15)

        if not working_proxies:
            print("[✘] لا يوجد بروكسي عامل!")
            continue

        print(f"\n[⏱️] إرسال {len(working_proxies)} طلب (واحد لكل بروكسي)...")

        # ✅ كل بروكسي = طلب واحد فقط
        semaphore = asyncio.Semaphore(5)  # 5 متوازية كحد أقصى
        tasks = []
        for i, proxy in enumerate(working_proxies, 1):
            tasks.append(send_one_request(i, names_list, proxy, semaphore))
            # ✅ delay عشوائي بين إنشاء المهام
            await asyncio.sleep(random.uniform(0.5, 1.5))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        round_success = sum(1 for r in results if r is True)
        round_total = len(working_proxies)
        total_success += round_success
        total_attempts += round_total

        print(f"\n[📊] الدورة {round_num}: {round_success}/{round_total} | الإجمالي: {total_success}/{total_attempts}")

        if round_num < 6:
            wait_time = random.randint(20, 40)
            print(f"\n[⏳] انتظار {wait_time} ثانية...")
            await asyncio.sleep(wait_time)

    print("\n" + "=" * 60)
    print(f"--- النهائي: {total_success}/{total_attempts} ---")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())

