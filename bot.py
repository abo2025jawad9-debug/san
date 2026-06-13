import ccxt
import requests
from datetime import datetime, timezone

# ==========================================
# 1. إعداد مفاتيح API
# ==========================================
api_key = 'dmyc2X0llvZ1A1zGAy9wfkqJHqZC20Uv04iYwBmOrnBMLJlnH7SZOsPt4eYGYnoJ'.strip()
secret = 'uVax1wfQo0Ns1XIhGgsW4j2yjgB9VPlQWYzWvt1sAeg640WpGRCSqFMPvVyNtu6S'.strip()

# ==========================================
# 2. دالة الجلب التلقائي للبروكسيات من الإنترنت
# ==========================================
def get_auto_proxy_exchange():
    print("🌐 جاري سحب أحدث البروكسيات المجانية من الإنترنت تلقائياً...")
    try:
        # سحب قائمة بروكسيات محدثة لحظياً من مستودعات موثوقة
        url = "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"
        response = requests.get(url, timeout=10)
        
        # نأخذ أول 100 بروكسي للتجربة
        proxies_list = response.text.split('\n')[:100] 
        print(f"✅ تم جلب {len(proxies_list)} بروكسي بنجاح! جاري فحصها لتخطي الحظر...")

        for p in proxies_list:
            if not p.strip(): continue
            proxy_url = f"http://{p.strip()}"
            
            try:
                ex = ccxt.binance({
                    'apiKey': api_key, 
                    'secret': secret, 
                    'enableRateLimit': True,
                    'proxies': {
                        'http': proxy_url,
                        'https': proxy_url,
                    },
                    'options': {'defaultType': 'spot'},
                    'urls': {'api': {'public': 'https://testnet.binance.vision/api/v3', 'private': 'https://testnet.binance.vision/api/v3'}}
                })
                ex.set_sandbox_mode(True)
                
                # إرسال طلب سريع لبينانس للتأكد أن البروكسي غير محظور ويعمل
                ex.fetch_time()
                print(f"🎉 عظيم! تم العثور على بروكسي يعمل وتخطي الحظر بنجاح: {proxy_url}")
                return ex  # إرجاع المنصة الجاهزة للعمل
                
            except:
                # إذا كان البروكسي محظوراً أو ميتاً، نتجاهله بصمت ونجرب الذي بعده
                continue
                
    except Exception as e:
        print(f"❌ خطأ في نظام سحب البروكسيات: {e}")
        
    print("🚨 فشلت كل المحاولات. يبدو أن جميع البروكسيات مسدودة حالياً.")
    return None

# ==========================================
# 3. جدول المواعيد والإشارات
# ==========================================
schedule = [
    {"time": "2026-06-13 11:59", "type": "نزول"},
    {"time": "2026-06-14 00:59", "type": "نزول"},
    {"time": "2026-06-14 10:29", "type": "نزول"},
    {"time": "2026-06-14 11:59", "type": "نزول"},
    {"time": "2026-06-14 21:00", "type": "نزول"},
    {"time": "2026-06-15 00:00", "type": "نزول"},
    {"time": "2026-06-15 00:59", "type": "نزول"},
    {"time": "2026-06-15 16:59", "type": "صعود ونزول"},
    {"time": "2026-06-15 22:59", "type": "صعود"},
    {"time": "2026-06-16 00:59", "type": "صعود"},
    {"time": "2026-06-16 16:29", "type": "نزول"},
    {"time": "2026-06-17 16:59", "type": "صعود"},
    {"time": "2026-06-18 12:59", "type": "صعود"},
    {"time": "2026-06-19 19:59", "type": "نزول"},
    {"time": "2026-06-22 02:59", "type": "صعود"},
    {"time": "2026-06-23 07:59", "type": "نزول"},
    {"time": "2026-06-24 13:29", "type": "نزول"},
    {"time": "2026-06-24 21:59", "type": "صعود"}
]

# ==========================================
# 4. دالة التداول الرئيسية
# ==========================================
def check_and_trade(ex):
    try:
        now_utc = datetime.now(timezone.utc)
        print(f"وقت الفحص الحالي (UTC): {now_utc.strftime('%Y-%m-%d %H:%M')}")
        
        ticker = ex.fetch_ticker('BTC/USDT')
        current_price = ticker['last']
        
        for signal in schedule:
            signal_time = datetime.strptime(signal["time"], '%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc)
            time_diff = abs((now_utc - signal_time).total_seconds())
            
            if time_diff <= 300: # 5 دقائق
                print(f"تم العثور على إشارة متطابقة: {signal['type']} في الموعد {signal['time']}")
                ohlcv = ex.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=2)
                price_1h_ago = ohlcv[0][4]
                print(f"السعر الحالي: {current_price} | السعر قبل ساعة: {price_1h_ago}")
                
                if "نزول" in signal["type"] and current_price < price_1h_ago:
                    print("تأكيد النزول المستهدف. شراء...")
                    ex.create_market_buy_order('BTC/USDT', 0.001)
                elif "صعود" in signal["type"] and current_price <= price_1h_ago:
                    print("تأكيد نقطة انطلاق الصعود. شراء...")
                    ex.create_market_buy_order('BTC/USDT', 0.001)
                else:
                    print("الشروط الفنية لم تتحقق، تم إلغاء الصفقة مؤقتاً لحمايتك.")
                return

        print("لا توجد إشارات مجدولة في هذا الوقت الحالي.")

    except Exception as e:
        print(f"❌ حدث خطأ أثناء تنفيذ التداول: {e}")

# ==========================================
# 5. التشغيل
# ==========================================
if __name__ == "__main__":
    # تشغيل نظام جلب البروكسي التلقائي أولاً
    exchange = get_auto_proxy_exchange()
    
    # إذا وجدنا بروكسي يعمل، نقوم بتشغيل التداول
    if exchange is not None:
        check_and_trade(exchange)
