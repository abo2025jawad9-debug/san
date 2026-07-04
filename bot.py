import asyncio
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from curl_cffi import requests

# ==========================================
# 1. الإعدادات
# ==========================================
FORM_PAGE_URL = "https://quwatasad.com/worldcup2026"
TARGET_URL = "https://quwatasad.com/form-submit"

# ✅ تاكد: فقط 77 أو 73 أو 71 — بدون 78 أو 70
YEMEN_PREFIXES = ["77", "73", "71"]

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

# ✅ أحرف خفية متعددة (Zero Width, Joiners, Non-Joiners, etc.)
INVISIBLE_CHARS = [
    "\u200C", "\u200D", "\u2060", "\uFEFF", "\u180E",
    "\u200B", "\u200E", "\u200F", "\u202A", "\u202B",
    "\u202C", "\u202D", "\u202E", "\u2061", "\u2062",
    "\u2063", "\u2064", "\u206A", "\u206B", "\u206C",
    "\u206D", "\u206E", "\u206F", "\u00AD",
]

# ✅ تشكيلات عربية متنوعة
ARABIC_DIACRITICS = [
    "\u064E", "\u064F", "\u0650", "\u064B", "\u064C",
    "\u064D", "\u0651", "\u0652", "\u0653", "\u0670",
    "\u0654", "\u0655", "\u0640",
]

# ✅ حروف عربية مشابهة (تبدو متشابهة لكنها مختلفة يونيكود)
ARABIC_LOOKALIKES = {
    "ا": ["\u0627", "\u0622", "\u0623", "\u0625", "\u0671"],
    "أ": ["\u0623", "\u0625", "\u0671"],
    "آ": ["\u0622"],
    "إ": ["\u0625"],
    "ي": ["\u064A", "\u0649", "\u06CC", "\u06D0"],
    "ى": ["\u0649", "\u064A"],
    "ه": ["\u0647", "\u06D5"],
    "ة": ["\u0629", "\u0647"],
    "ك": ["\u0643", "\u06A9"],
    "و": ["\u0648", "\u06C4"],
    "د": ["\u062F", "\u0688"],
    "ر": ["\u0631", "\u0691"],
    "س": ["\u0633", "\u0698"],
    "ز": ["\u0632", "\u0698"],
    "ط": ["\u0637", "\u0638"],
    "ظ": ["\u0638", "\u0637"],
    "ع": ["\u0639", "\u063A"],
    "غ": ["\u063A", "\u0639"],
    "ف": ["\u0641", "\u06A4"],
    "ق": ["\u0642", "\u06A8"],
    "ب": ["\u0628", "\u067E"],
    "ت": ["\u062A", "\u062B"],
    "ث": ["\u062B", "\u062A"],
    "ج": ["\u062C", "\u0686"],
    "ح": ["\u062D", "\u062E"],
    "خ": ["\u062E", "\u062D"],
    "ص": ["\u0635", "\u0636"],
    "ض": ["\u0636", "\u0635"],
    "م": ["\u0645", "\u0645"],
    "ن": ["\u0646", "\u06BA"],
    "ل": ["\u0644", "\u06B5"],
}

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

# ✅ تاكد: زخرفة الاسم بشكل عشوائي وفريد
def make_name_unique(name):
    """
    زخرفة الاسم بشكل عشوائي بحيث يكون فريداً في كل مرة.
    تستخدم:
    1. أحرف خفية (Zero Width Characters)
    2. تشكيلات عربية متنوعة
    3. حروف عربية مشابهة (تبدو متشابهة لكنها مختلفة يونيكود)
    4. ترتيب عشوائي للتشكيلات
    """
    result = ""

    for i, char in enumerate(name):
        # ✅ 1. استبدال الحرف بمكافئ مشابه أحياناً (30% احتمال)
        if char in ARABIC_LOOKALIKES and random.random() < 0.30:
            char = random.choice(ARABIC_LOOKALIKES[char])

        result += char

        if char == " ":
            continue

        # ✅ 2. إضافة أحرف خفية (40-70% احتمال لكل حرف)
        if random.random() < random.uniform(0.40, 0.70):
            # إضافة 1-3 أحرف خفية
            for _ in range(random.randint(1, 3)):
                result += random.choice(INVISIBLE_CHARS)

        # ✅ 3. إضافة تشكيلات عربية (30-50% احتمال)
        if random.random() < random.uniform(0.30, 0.50):
            # إضافة 1-2 تشكيلات
            for _ in range(random.randint(1, 2)):
                result += random.choice(ARABIC_DIACRITICS)

    # ✅ 4. إضافة أحرف خفية في البداية والنهاية أحياناً
    if random.random() < 0.5:
        result = random.choice(INVISIBLE_CHARS) + result
    if random.random() < 0.5:
        result = result + random.choice(INVISIBLE_CHARS)

    return result.strip()

# ✅ تاكد: رقم هاتف عشوائي يبدأ بـ 77 أو 73 أو 71 فقط
def generate_phone():
    """
    إنشاء رقم هاتف يمني عشوائي يبدأ بـ 77 أو 73 أو 71 فقط.
    7 أرقام بعد البادئة.
    """
    prefix = random.choice(YEMEN_PREFIXES)  # فقط 77 أو 73 أو 71
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

            # ✅ تاكد: تحضير بيانات فريدة
            raw_name = random.choice(names_list)
            unique_name = make_name_unique(raw_name)
            team_id = random.choice(list(TEAMS.keys()))
            team_name = TEAMS[team_id]
            phone = generate_phone()  # ✅ تاكد: 77 أو 73 أو 71

            payload = {
                "_token": token,
                "date": (soup.find("input", {"name": "date"}) or {}).get("value", "2026-07-05"),
                "section_id": (soup.find("input", {"name": "section_id"}) or {}).get("value", "0"),
                "TopicID": (soup.find("input", {"name": "TopicID"}) or {}).get("value", "152"),
                "WebmasterSectionId": (soup.find("input", {"name": "WebmasterSectionId"}) or {}).get("value", ""),
                "customField_18": team_id,
                "customField_19": unique_name,  # ✅ تاكد: اسم مزخرف وفريد
                "customField_20": phone,        # ✅ تاكد: رقم يبدأ بـ 77/73/71
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
    print("--- قوة أسد v4: كل بروكسي = طلب واحد ---")
    print("=" * 60)
    print("[✅] رقم الهاتف: يبدأ بـ 77 أو 73 أو 71 فقط")
    print("[✅] الاسم: مزخرف بأحرف خفية + تشكيلات + حروف مشابهة")
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
        semaphore = asyncio.Semaphore(5)
        tasks = []
        for i, proxy in enumerate(working_proxies, 1):
            tasks.append(send_one_request(i, names_list, proxy, semaphore))
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

