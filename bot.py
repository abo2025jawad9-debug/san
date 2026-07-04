import asyncio
import os
import random
import time
#import requests
from curl_cffi import requests
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup

# ==========================================
# 1. الإعدادات
# ==========================================
FORM_PAGE_URL = "https://quwatasad.com/worldcup2026"
TARGET_URL = "https://quwatasad.com/form-submit"

YEMEN_PREFIXES = ["77", "78", "73", "71", "70"]
GOVERNORATES = [str(i) for i in (1, 23)]

ROUND_OF_16_TEAMS = {
    "1": "الأرجنتين", "12": "البرازيل", "38": "rangeفرنسا", "9": "إنجلترا",
    "8": "إسبانيا", "25": "المكسيك", "13": "البرتغال", "27": "النرويج",
    "32": "بلجيكا", "33": "سويسرا", "40": "كرواتيا", "30": "باراغواي",
    "3": "استراليا", "41": "كندا"
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
]

INVISIBLE_CHARS = ["\u064C", "\u064C"]
ARABIC_DIACRITICS = [
    "\u064E", "\u064F", "\u0650", "\u064F", "\u064C",
    "\u064D", "\u0651", "\u0651", "\u0640", "\u0653"
]

# أكواد الدول العربية (ISO 3166-1 alpha-2)
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

# ==========================================
# 2. جلب بروكسيات عربية
# ==========================================
def fetch_arab_proxies(max_per_source=50):
    """جلب بروكسيات من جميع الدول العربية"""
    proxies = []
    headers = {"User-Agent": random.choice(USER_AGENTS)}

    # المصدر 1: ProxyScrape API (جميع الدول العربية مرة واحدة)
    try:
        countries = ",".join(ARAB_COUNTRY_CODES)
        url = f"https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text&country={countries}"
        print(f"[🌐] جلب بروكسيات عربية من ProxyScrape...")
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200 and resp.text.strip():
            lines = [line.strip() for line in resp.text.strip().split("\n") if line.strip()]
            for line in lines:
                if line.startswith("http://") or line.startswith("https://"):
                    proxies.append(line)
                elif ":" in line and not line.startswith("http"):
                    proxies.append(f"http://{line}")
            print(f"   ✔ تم جلب {len(lines)} بروكسي عربي")
        else:
            print("   ✘ لا يوجد بروكسيات عربية في ProxyScrape")
    except Exception as e:
        print(f"   ✘ خطأ ProxyScrape: {e}")

    # المصدر 2: free-proxy-list.net (فلترة يدوية للدول العربية)
    try:
        print(f"[🌐] جلب بروكسيات عربية من free-proxy-list.net...")
        url = "https://free-proxy-list.net/"
        resp = requests.get(url, headers=headers, timeout=15)
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
                print(f"   ✔ تم جلب {count} بروكسي عربي")
    except Exception as e:
        print(f"   ✘ خطأ free-proxy-list: {e}")

    # المصدر 3: proxy-list.download (HTTP)
    try:
        print(f"[🌐] جلب بروكسيات عربية من proxy-list.download...")
        url = "https://www.proxy-list.download/api/v1/get?type=http"
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            lines = [line.strip() for line in resp.text.strip().split("\n") if line.strip()]
            # هذا المصدر لا يعطي دول، نضيف الكل ونختبر لاحقاً
            # لكنه عادةً يعطي بروكسيات مختلطة، نجرب
            for line in lines[:max_per_source]:
                if ":" in line and not line.startswith("http"):
                    proxies.append(f"http://{line}")
            print(f"   ✔ تم جلب {len(lines[:max_per_source])} بروكسي (سنختبرها)")
    except Exception as e:
        print(f"   ✘ خطأ proxy-list: {e}")

    # إزالة التكرارات
    proxies = list(dict.fromkeys(proxies))
    random.shuffle(proxies)
    print(f"\n[📊] إجمالي بروكسيات عربية فريدة: {len(proxies)}")
    return proxies[:150]

# ==========================================
# 3. اختبار البروكسيات العربية
# ==========================================
def test_single_proxy(proxy_url):
    """اختبار بروكسي عربي"""
    proxies = {"http": proxy_url, "https": proxy_url}
    headers = {"User-Agent": random.choice(USER_AGENTS)}

    try:
        start = time.time()
        resp = requests.get(
            FORM_PAGE_URL,
            headers=headers,
            proxies=proxies,
            timeout=5,
            allow_redirects=True
        )
        latency = time.time() - start

        if resp.status_code == 200 and len(resp.text) > 1000:
            return (proxy_url, latency, True)
    except Exception:
        pass

    return (proxy_url, 999, False)

def test_arab_proxies(proxy_list, max_workers=40, min_working=3):
    """اختبار البروكسيات العربية - يتوقف عند أول 3 ناجحين"""
    if not proxy_list:
        return []

    working = []
    print(f"\n[🔬] اختبار {len(proxy_list)} بروكسي عربي...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(test_single_proxy, p): p for p in proxy_list}

        for future in as_completed(futures):
            proxy, latency, is_working = future.result()
            if is_working:
                working.append((proxy, latency))
                print(f"   ✔ عامل #{len(working)}: {proxy[:45]} | {latency:.2f}s")

                # نتوقف عند الوصول للحد الأدنى
                if len(working) >= min_working:
                    for f in futures:
                        f.cancel()
                    break

    working.sort(key=lambda x: x[1])
    print(f"\n[✅] بروكسيات عربية عاملة: {len(working)}")
    return [p[0] for p in working]

# ==========================================
# 4. المساعدات
# ==========================================
def load_names_from_file(filename="names.txt"):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            names = [line.strip() for line in f if line.strip()]
            if names:
                print(f"[✔] تم تحميل {len(names)} اسم")
                return names
    print(f"[⚠] ملف {filename} غير موجود! استخدام افتراضية.")
    return [
        "محمد لطف يحيى 772490746",
        "أحمد سعيد علي 771234567",
        "خالد محمود سالم 773456789",
        "عبدالله فؤاد عمر 774567890",
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
    return f"{random.choice(YEMEN_PREFIXES)}{''.join([str(random.randint(0,9)) for _ in range(7)])}"

# ==========================================
# 5. جلب التوكن + إرسال الطلب
# ==========================================
def fetch_form_data(session, proxies, headers):
    try:
        resp = session.get(FORM_PAGE_URL, headers=headers, proxies=proxies, timeout=10)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
        return {
            "_token": (soup.find("input", {"name": "_token"}) or {}).get("value", ""),
            "date": (soup.find("input", {"name": "date"}) or {}).get("value", ""),
            "section_id": (soup.find("input", {"name": "section_id"}) or {}).get("value", ""),
            "TopicID": (soup.find("input", {"name": "TopicID"}) or {}).get("value", ""),
            "WebmasterSectionId": (soup.find("input", {"name": "WebmasterSectionId"}) or {}).get("value", ""),
        }
    except Exception:
        return None

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

def check_success(status, html_text):
    if status != 200:
        return False
    keywords = ["شكرا", "تم بنجاح", "success", "thank", "تم الإرسال", "تم التسجيل"]
    return any(kw in html_text.lower() for kw in keywords)

# ==========================================
# 6. إرسال طلب مع بروكسي عربي
# ==========================================
async def send_single_request(request_num, names_list, working_proxies, semaphore):
    async with semaphore:
        if not working_proxies:
            print(f"[✘] الطلب {request_num:02d} فشل: لا يوجد بروكسي عربي عامل")
            return False

        # نختار 3 بروكسيات عشوائية للتجربة
        candidates = random.sample(working_proxies, min(3, len(working_proxies)))

        for proxy_url in candidates:
            session = requests.Session()
            headers = {
                "User-Agent": random.choice(USER_AGENTS),
                "Referer": FORM_PAGE_URL,
                "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Origin": "https://quwatasad.com",
            }
            proxies = {"http": proxy_url, "https": proxy_url}

            try:
                # GET
                def do_get():
                    return fetch_form_data(session, proxies, headers)

                live_fields = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, do_get),
                    timeout=15
                )

                if not live_fields:
                    continue

                payload, team_name = prepare_payload(live_fields, names_list)

                # POST
                def do_post():
                    return session.post(TARGET_URL, data=payload, headers=headers, proxies=proxies, timeout=10, allow_redirects=True)

                resp = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, do_post),
                    timeout=15
                )

                if check_success(resp.status_code, resp.text):
                    print(f"[🏆 نجاح] الطلب {request_num:02d} | {team_name} | {proxy_url[:35]}...")
                    session.close()
                    return True
                else:
                    session.close()
                    return False

            except Exception:
                session.close()
                continue

        print(f"[✘] الطلب {request_num:02d} فشل بعد {len(candidates)} محاولات")
        return False

# ==========================================
# 7. التشغيل الرئيسي
# ==========================================
async def main():
    print("=" * 60)
    print("--- سكربت قوة أسد - بروكسيات عربية ---")
    print("=" * 60)
    print(f"[🌍] الدول المستهدفة: {', '.join(ARAB_COUNTRY_NAMES.values())}")

    names_list = load_names_from_file("names.txt")

    for round_num in range(1, 7):
        print(f"\n{'='*50}")
        print(f"--- الدورة {round_num} من 6 ---")
        print(f"{'='*50}")

        # جلب بروكسيات عربية
        print("[🌐] جلب بروكسيات عربية...")
        raw_proxies = fetch_arab_proxies(max_per_source=50)

        if not raw_proxies:
            print("[✘] لا يوجد بروكسيات عربية متاحة!")
            print("[💡] الحلول: 1) بروكسي مدفوع 2) تشغيل محلي")
            return

        # اختبار البروكسيات العربية
        working_proxies = test_arab_proxies(raw_proxies, max_workers=40, min_working=3)

        if not working_proxies:
            print("[✘] لا يوجد بروكسي عربي عامل!")
            return

        # تشغيل الطلبات
        print("\n[⏱️] بدء إرسال الطلبات...")
        semaphore = asyncio.Semaphore(5)
        tasks = [send_single_request(i, names_list, working_proxies, semaphore) for i in range(1, 100)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        success = sum(1 for r in results if r is True)
        print(f"\n[📊] الدورة {round_num}: نجاح={success}/99")

        if round_num < 6:
            wait_time = random.randint(5, 15)
            print(f"\n[⏳] انتظار {wait_time} ثوانٍ...")
            await asyncio.sleep(wait_time)

    print("\n" + "=" * 60)
    print("--- تم الانتهاء ---")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())

