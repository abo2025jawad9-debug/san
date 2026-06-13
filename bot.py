import ccxt
import requests
import time
from datetime import datetime, timezone

# ==========================================
# 1. إعداد مفاتيح API (بينانس و تليجرام)
# ==========================================
api_key = 'dmyc2X0llvZ1A1zGAy9wfkqJHqZC20Uv04iYwBmOrnBMLJlnH7SZOsPt4eYGYnoJ'.strip()
secret = 'uVax1wfQo0Ns1XIhGgsW4j2yjgB9VPlQWYzWvt1sAeg640WpGRCSqFMPvVyNtu6S'.strip()

# ---- معلومات تليجرام الخاصة بك ----
TELEGRAM_TOKEN = '8777604170:AAGVQWj7KtRZWKjZQ0BuyIZCHJ3FCmFgQP4'
TELEGRAM_CHAT_ID = '6390985342'
# --------------------------------

def send_telegram_message(message):
    """دالة لإرسال الرسائل إلى تليجرام"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ فشل إرسال رسالة تليجرام: {e}")

# ==========================================
# 2. دالة الجلب التلقائي للبروكسيات
# ==========================================
def get_auto_proxy_exchange():
    print("🌐 جاري سحب أحدث البروكسيات...")
    try:
        url = "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"
        response = requests.get(url, timeout=10)
        proxies_list = response.text.split('\n')[:150] 

        for p in proxies_list:
            if not p.strip(): continue
            proxy_url = f"http://{p.strip()}"
            
            try:
                ex = ccxt.binance({
                    'apiKey': api_key, 
                    'secret': secret, 
                    'enableRateLimit': True,
                    'proxies': {'http': proxy_url, 'https': proxy_url},
                    'options': {'defaultType': 'spot', 'warnOnFetchOpenOrdersWithoutSymbol': False}
                })
                ex.set_sandbox_mode(True)
                # الفحص القوي للبروكسي
                ex.load_markets()
                return ex, proxy_url
                
            except:
                continue
                
    except Exception as e:
        print(f"❌ خطأ في سحب البروكسيات: {e}")
        
    return None, None

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
# 4. دالة التداول الرئيسية وبناء التقرير
# ==========================================
def check_and_trade(ex, proxy_url):
    now_utc = datetime.now(timezone.utc)
    time_str = now_utc.strftime('%Y-%m-%d %H:%M')
    
    # بداية بناء رسالة التليجرام
    telegram_msg = f"🤖 <b>تقرير البوت:</b>\n"
    telegram_msg += f"🕒 الوقت: {time_str} UTC\n"
    telegram_msg += f"✅ تم تخطي الحظر وتوصيل السيرفر\n"
    
    try:
        ticker = ex.fetch_ticker('BTC/USDT')
        current_price = ticker['last']
        telegram_msg += f"💰 سعر البتكوين الحالي: {current_price}$\n"
        
        signal_found = False
        for signal in schedule:
            signal_time = datetime.strptime(signal["time"], '%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc)
            time_diff = abs((now_utc - signal_time).total_seconds())
            
            if time_diff <= 300: # 5 دقائق
                signal_found = True
                telegram_msg += f"⚠️ <b>تم العثور على إشارة:</b> {signal['type']} (موعد: {signal['time']})\n"
                
                ohlcv = ex.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=2)
                price_1h_ago = ohlcv[0][4]
                telegram_msg += f"السعر قبل ساعة: {price_1h_ago}$\n"
                
                if "نزول" in signal["type"] and current_price < price_1h_ago:
                    ex.create_market_buy_order('BTC/USDT', 0.001)
                    telegram_msg += "✅ <b>القرار:</b> تم تنفيذ صفقة شراء بنجاح (نزول مؤكد)!\n"
                elif "صعود" in signal["type"] and current_price <= price_1h_ago:
                    ex.create_market_buy_order('BTC/USDT', 0.001)
                    telegram_msg += "✅ <b>القرار:</b> تم تنفيذ صفقة شراء بنجاح (صعود مؤكد)!\n"
                else:
                    telegram_msg += "🚫 <b>القرار:</b> تم إلغاء الصفقة مؤقتاً، الشروط الفنية لم تتحقق للحماية.\n"
                break
                
        if not signal_found:
            telegram_msg += "💤 لا توجد صفقات مجدولة تتطابق مع هذا الوقت.\n"

        # إرسال التقرير النهائي إلى تليجرام
        send_telegram_message(telegram_msg)
        print("✅ تم إرسال التقرير إلى تليجرام بنجاح.")

    except Exception as e:
        error_msg = f"🚨 <b>حدث خطأ أثناء فحص السوق:</b>\n{e}"
        send_telegram_message(error_msg)
        print(f"❌ حدث خطأ: {e}")

# ==========================================
# 5. التشغيل الرئيسي - LOOP لمدة 30 دقيقة
# ==========================================
if __name__ == "__main__":
    DURATION_MINUTES = 30      # مدة التشغيل الكلية
    INTERVAL_MINUTES = 10      # الفاصل بين كل دورة
    
    start_time = time.time()
    duration_seconds = DURATION_MINUTES * 60
    interval_seconds = INTERVAL_MINUTES * 60
    
    print(f"🚀 بدء التشغيل لمدة {DURATION_MINUTES} دقيقة")
    print(f"⏱️  كل {INTERVAL_MINUTES} دقائق ستُعاد العمليات")
    print(f"🕒 الوقت الآن: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")
    
    # إرسال إشعار بدء التشغيل
    send_telegram_message(
        f"🚀 <b>بدأت دورة البوت</b>\n"
        f"⏱️ المدة: {DURATION_MINUTES} دقيقة\n"
        f"🔄 تكرار كل: {INTERVAL_MINUTES} دقائق\n"
        f"🕒 الوقت: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}"
    )
    
    cycle_number = 1
    
    while time.time() - start_time < duration_seconds:
        print(f"\n{'='*60}")
        print(f"🔄 الدورة رقم {cycle_number} - {datetime.now(timezone.utc).strftime('%H:%M:%S')}")
        print(f"{'='*60}")
        
        exchange, valid_proxy = get_auto_proxy_exchange()
        if exchange is not None:
            check_and_trade(exchange, valid_proxy)
        else:
            send_telegram_message("🚨 <b>تحذير:</b> البوت لم يتمكن من العثور على أي بروكسي يعمل في هذه الدورة.")
            print("❌ فشل الاتصال بجميع البروكسيات.")
        
        # حساب الوقت المتبقي حتى الدورة القادمة
        elapsed = time.time() - start_time
        next_cycle_time = ((elapsed // interval_seconds) + 1) * interval_seconds
        wait_seconds = next_cycle_time - elapsed
        
        # إذا كان الوقت المتبقي أقل من الفاصل، ننتظر حتى النهاية
        if wait_seconds > 0 and elapsed + wait_seconds <= duration_seconds:
            print(f"💤 انتظار {wait_seconds/60:.0f} دقيقة حتى الدورة التالية...")
            time.sleep(wait_seconds)
            cycle_number += 1
        else:
            break
    
    # نهاية التشغيل
    end_msg = (
        f"✅ <b>انتهت دورة البوت</b>\n"
        f"⏱️ تم تشغيل {cycle_number} دورة/دورات خلال {DURATION_MINUTES} دقيقة\n"
        f"🕒 الوقت: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}\n"
        f"💤 سيتم إعادة التشغيل تلقائياً في الجدولة القادمة."
    )
    send_telegram_message(end_msg)
    print(f"\n✅ انتهت مدة التشغيل ({DURATION_MINUTES} دقيقة).")
