import asyncio
import os
import random
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
# === التعديل الجوهري: استخدام curl_cffi بدلاً من requests العادية ===
from curl_cffi import requests 

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

INVISIBLE_CHARS = ["\u064C", "\u064C"]
ARABIC_DIACRITICS = [
    "\u064E", "\u064F", "\u0650", "\u064F", "\u064C",
    "\u064D", "\u0651", "\u0651", "\u0640", "\u0653"
]

# أكواد الدول العربية
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
    proxies = []
    
    # استخدام impersonate لخداع أنظمة حماية مواقع البروكسي أيضاً
    try:
        countries = ",".join(ARAB_COUNTRY_CODES)
        url = f"https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text&country={countries}"
        print(f"[🌐] جلب بروكسيات عربية من ProxyScrape...")
        resp = requests.get(url, impersonate="chrome120", timeout=15)
        if resp.status_code == 200 and resp.text.strip():
            lines = [line.strip() for line in resp.text.strip().split("\n") if line.strip()]
            for line in lines:
                if line.startswith("http://") or line.startswith("https://"):
                    proxies.append(line)
                elif ":" in line and not line.startswith("http"):
                    proxies.append(f"http://{line}")
            print(f"   ✔ تم جلب {len(lines)} بروكسي عربي")
    except Exception as e:
        print(f"   ✘ خطأ ProxyScrape: {e}")

    try:
        print(f"[🌐] جلب بروكسيات عربية من free-proxy-list.net...")
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
                print(f"   ✔ تم جلب {count} بروكسي عربي")
    except Exception as e:
        print(f"   ✘ خطأ free-proxy-list: {e}")

    try:
        print(f"[🌐] جلب بروكسيات عربية من proxy-list.download...")
        url = "https://www.proxy-list.download/api/v1/get?type=http"
        resp = requests.get(url, impersonate="chrome120", timeout=15)
        if resp.status_code == 200:
            lines = [line.strip() for line in resp.text.strip().split("\n") if line.strip()]
            for line in lines[:max_per_source]:
                if ":" in line and not line.startswith("http"):
                    proxies.append(f"http://{line}")
            print(f"   ✔ تم جلب {len(lines[:max_per_source])} بروكسي (سنختبرها)")
    except Exception as e:
        print(f"   ✘ خطأ proxy-list: {e}")

    proxies = list(dict.fromkeys(proxies))
    random.shuffle(proxies)
    print(f"\n[📊] إجمالي بروكسيات عربية فريدة: {len(proxies)}")
    return proxies[:150]

# ==========================================
# 3. اختبار البروكسيات العربية
# ==========================================
def test_single_proxy(proxy_url):
    proxies = {"http": proxy_url, "https": proxy_url}
    try:
        start = time.time()
        resp = requests.get(
            FORM_PAGE_URL,
            proxies=proxies,
            timeout=10,
            impersonate="chrome120", # محاكاة المتصفح أثناء الفحص
            allow_redirects=True
        )
        latency = time.time() - start
        if resp.status_code == 200 and len(resp.text) > 1000:
            return (proxy_url, latency, True)
    except Exception:
        pass
    return (proxy_url, 999, False)

def test_arab_proxies(proxy_list, max_workers=40, min_working=3):
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
                if len(working) >= min_working:
                    for f in futures:
                        f.cancel()
                    break

    working.sort(key=lambda x: x[1])
    print(f"\n[✅] بروكسيات عربية عاملة: {len(working)}")
    return [p[0] for p in working]

# ==========================================
# 4. المساعدات وتجهيز البيانات
# ==========================================
def load_names_from_file(filename="names.txt"):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            # فلترة الأسطر الفارغة بدقة
            names = [line.strip() for line in f if line.strip()]
            if names:
                print(f"[✔] تم تحميل {len(names)} اسم")
                return names
    print(f"[⚠] ملف {filename} غير موجود أو فارغ! استخدام الأسماء الافتراضية.")
    return [
        "محمد لطف يحيى الزيلعي",
        "أحمد سعيد علي",
        "خالد محمود سالم",
        "عبدالله فؤاد عمر",
    ]

def make_name_strictly_unique(name):
    hidden_prob = random.uniform(0.40, 0.80)
    diacritic_prob = random.uniform(0.20, 0.50)
    unique_name = ""
    for char in name:
        unique_name += char
        if char != " ":
            if random.random() < hidden_prob:
                unique_name += random.choice(INVISIBLE_CHARS)
            if random.random() < diacritic_prob:
                unique_name += random.choice(ARABIC_DIACRITICS)
    # تنظيف الفراغات النهائية لتجنب أخطاء Laravel
    return unique_name.strip()

def generate_random_phone():
    return f"{random.choice(YEMEN_PREFIXES)}{''.join([str(random.randint(0,9)) for _ in range(7)])}"

# ==========================================
# 5. جلب التوكن + إرسال الطلب
# ==========================================
def fetch_form_data(session, proxies, headers):
    try:
        resp = session.get(FORM_PAGE_URL, headers=headers, proxies=proxies, timeout=15)
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
        "customField_19": unique_name, # الاسم المنظف
        "customField_20": generate_random_phone(),
        "customField_24": random.choice(GOVERNORATES),
    })
    return payload, team_name

def check_success(status, html_text):
    if status != 200:
        return False
    keywords = ["شكرا", "تم بنجاح", "success", "thank", "تم الإرسال", "تم التسجيل", "تم الاشتراك"]
    return any(kw in html_text.lower() for kw in keywords)

# ==========================================
# 6. إرسال طلب مع بروكسي عربي
# ==========================================
async def send_single_request(request_num, names_list, working_proxies, semaphore):
    async with semaphore:
        if not working_proxies:
            return False

        candidates = random.sample(working_proxies, min(3, len(working_proxies)))

        for proxy_url in candidates:
            # === استخدام المتصفح الوهمي هنا (السر في تجاوز Cloudflare) ===
            session = requests.Session(impersonate="chrome120")
            
            headers = {
                "Referer": FORM_PAGE_URL,
                "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
                "Origin": "https://quwatasad.com",
            }
            proxies = {"http": proxy_url, "https": proxy_url}

            try:
                def do_get():
                    return fetch_form_data(session, proxies, headers)

                live_fields = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, do_get),
                    timeout=20
                )

                if not live_fields or not live_fields.get('_token'):
                    session.close()
                    continue

                payload, team_name = prepare_payload(live_fields, names_list)

                def do_post():
                    return session.post(TARGET_URL, data=payload, headers=headers, proxies=proxies, timeout=15, allow_redirects=True)

                resp = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, do_post),
                    timeout=20
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

        print(f"[✘] الطلب {request_num:02d} فشل (ربما البروكسي ضعيف أو تم الحظر)")
        return False

# ==========================================
# 7. التشغيل الرئيسي
# ==========================================
async def main():
    print("=" * 60)
    print("--- سكربت قوة أسد (النسخة الاحترافية - تجاوز Cloudflare) ---")
    print("=" * 60)
    print(f"[🌍] الدول المستهدفة: {', '.join(ARAB_COUNTRY_NAMES.values())}")

    names_list = load_names_from_file("names.txt")

    for round_num in range(1, 7):
        print(f"\n{'='*50}")
        print(f"--- الدورة {round_num} من 6 ---")
        print(f"{'='*50}")

        print("[🌐] جلب بروكسيات عربية...")
        raw_proxies = fetch_arab_proxies(max_per_source=50)

        if not raw_proxies:
            print("[✘] لا يوجد بروكسيات عربية متاحة!")
            return

        working_proxies = test_arab_proxies(raw_proxies, max_workers=40, min_working=3)

        if not working_proxies:
            print("[✘] لا يوجد بروكسي عربي عامل حالياً!")
            return

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
