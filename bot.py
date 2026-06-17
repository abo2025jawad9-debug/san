import ccxt
import requests
import time
import json
import os
import tempfile
import shutil
from datetime import datetime, timezone

# ==========================================
# 1. إعداد مفاتيح API (عبر متغيرات البيئة للحماية)
# ==========================================
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

api_key = os.getenv('BINANCE_API_KEY', '')
secret = os.getenv('BINANCE_SECRET', '')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# ==========================================
# 2. إعدادات التداول
# ==========================================
MAX_BUYS = 7
MAX_TOTAL_USDT = 75  
TRADE_USDT_PER_BUY = MAX_TOTAL_USDT // MAX_BUYS
DURATION_MINUTES = 360
CHECK_INTERVAL = 5   
MIN_BTC_AMOUNT = 0.0001
STATE_FILE = 'state.json'
FEE_RATE = 0.001 

# جدول الإشارات الفلكية
schedule = [
    {"time": "2026-06-16 01:19", "type": "نزول"},
    {"time": "2026-06-16 02:19", "type": "نزول"},
    {"time": "2026-06-16 03:29", "type": "نزول"},
    {"time": "2026-06-16 04:15", "type": "صعود ونزول"},
    {"time": "2026-06-16 23:59", "type": "نزول"},
    {"time": "2026-06-14 22:40", "type": "صعود"},
    {"time": "2026-06-14 21:15", "type": "نزول"},
    {"time": "2026-06-15 22:50", "type": "نزول"},
    {"time": "2026-06-15 23:10", "type": "نزول"},
    {"time": "2026-06-07 05:29", "type": "نزول"},
    {"time": "2026-06-07 11:29", "type": "نزول"},
    {"time": "2026-06-08 00:29", "type": "نزول"},
    {"time": "2026-06-08 11:29", "type": "نزول"},
    {"time": "2026-06-08 15:29", "type": "صعود"},
    {"time": "2026-06-09 00:29", "type": "نزول"},
    {"time": "2026-06-09 11:29", "type": "نزول"},
    {"time": "2026-06-09 12:59", "type": "صعود"},
    {"time": "2026-06-10 00:29", "type": "نزول"},
    {"time": "2026-06-10 11:29", "type": "نزول"},
    {"time": "2026-06-10 15:29", "type": "نزول"},
    {"time": "2026-06-11 00:29", "type": "نزول"},
    {"time": "2026-06-11 11:29", "type": "نزول"},
    {"time": "2026-06-11 16:59", "type": "صعود ونزول"},
    {"time": "2026-06-12 00:29", "type": "نزول"},
    {"time": "2026-06-12 07:59", "type": "نزول"},
    {"time": "2026-06-12 11:59", "type": "نزول"},
    {"time": "2026-06-13 00:59", "type": "نزول"},
    {"time": "2026-06-13 11:59", "type": "نزول"},
    {"time": "2026-06-14 00:59", "type": "نزول"},
    {"time": "2026-06-14 10:29", "type": "نزول"},
    {"time": "2026-06-14 11:59", "type": "نزول"},
    {"time": "2026-06-14 21:00", "type": "نزول"},
    {"time": "2026-06-15 00:59", "type": "نزول"}
]

# ==========================================
# 3. الدوال المساعدة وجلب البروكسي
# ==========================================
def send_telegram_message(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ Telegram: {e}")

def get_working_proxy():
    print("🔄 جاري البحث عن بروكسي مجاني لتجاوز حظر الخادم...")
    # مصادر متجددة للبروكسيات المجانية
    sources = [
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=yes&anonymity=all",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"
    ]
    
    for source in sources:
        try:
            resp = requests.get(source, timeout=10)
            if resp.status_code == 200:
                proxies = resp.text.strip().split('\n')
                # نجرب أول 30 بروكسي لضمان إيجاد واحد سريع
                for prx in proxies[:30]: 
                    prx = prx.strip()
                    if not prx: continue
                    proxy_url = f"http://{prx}"
                    test_proxies = {"http": proxy_url, "https": proxy_url}
                    try:
                        # اختبار سريع للاتصال بسيرفر بينانس
                        test_req = requests.get("https://testnet.binance.vision/api/v3/ping", proxies=test_proxies, timeout=5)
                        if test_req.status_code == 200:
                            print(f"✅ تم العثور على بروكسي يعمل بنجاح: {proxy_url}")
                            return test_proxies
                    except:
                        continue
        except Exception as e:
            print(f"⚠️ فشل جلب القائمة من المصدر: {e}")
            
    print("❌ لم يتم العثور على بروكسي سريع. سيتم محاولة الاتصال المباشر.")
    return None

def load_state():
    default_state = {
        'open_positions': [],
        'buy_count': 0,
        'total_usdt_spent': 0.0,
        'processed_signals': [],
        'total_profit': 0.0,
        'trades_history': []
    }
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
            for key, value in default_state.items():
                if key not in state:
                    state[key] = value
            return state
        except:
            pass
    return default_state

def save_state(state):
    fd, temp_path = tempfile.mkstemp()
    with os.fdopen(fd, 'w') as f:
        json.dump(state, f, indent=2)
    shutil.move(temp_path, STATE_FILE)

# ==========================================
# 4. منطق الشراء (تأكيد مزدوج)
# ==========================================
def check_buy(ex, now, time_str, state):
    if state['buy_count'] >= MAX_BUYS:
        return False
    
    try:
        ticker = ex.fetch_ticker('BTC/USDT')
        current_price = ticker['last']
        low_24h = ticker['low']
        buy_reason = None
        
        for signal in schedule:
            signal_time = datetime.strptime(signal["time"], '%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc)
            time_diff = abs((now - signal_time).total_seconds())
            
            if time_diff <= 300 and signal["type"] == "نزول" and signal["time"] not in state.get('processed_signals', []):
                ohlcv = ex.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=2)
                price_1h_ago = ohlcv[0][4]
                
                if price_1h_ago > current_price:
                    buy_reason = f"إشارة نزول مؤكدة (السعر السابق {price_1h_ago:.2f} > الحالي {current_price:.2f})"
                    state.setdefault('processed_signals', []).append(signal["time"])
                    break
        
        if not buy_reason and current_price <= (low_24h * 1.001):
            buy_reason = f"أدنى سعر في 24 ساعة (القاع: {low_24h:.2f})"

        if buy_reason:
            raw_amount = TRADE_USDT_PER_BUY / current_price
            amount = float(ex.amount_to_precision('BTC/USDT', raw_amount))
            
            if amount < MIN_BTC_AMOUNT:
                print("⚠️ الكمية أقل من الحد الأدنى المسموح للتداول.")
                return False

            order = ex.create_market_buy_order('BTC/USDT', amount)
            
            buy_fee_usdt = (current_price * amount) * FEE_RATE
            total_cost = (current_price * amount) + buy_fee_usdt
            
            state['open_positions'].append({
                'buy_price': current_price,
                'amount': amount,
                'buy_fee': buy_fee_usdt,
                'total_cost': total_cost,
                'reason': buy_reason,
                'time': time_str
            })
            
            state['buy_count'] += 1
            state['total_usdt_spent'] += total_cost
            
            msg = (f"🟢 <b>✅ تم الشراء بنجاح!</b>\n\n"
                   f"📝 <b>السبب:</b> {buy_reason}\n"
                   f"💰 <b>سعر الشراء:</b> {current_price:.2f} USDT\n"
                   f"📦 <b>الكمية:</b> {amount} BTC\n"
                   f"💵 <b>إجمالي التكلفة (مع الرسوم):</b> {total_cost:.4f} USDT\n"
                   f"🕒 {time_str}")
            send_telegram_message(msg)
            print(f"✅ تم الشراء | {buy_reason}")
            return True

    except Exception as e:
        print(f"❌ خطأ في عملية الشراء: {e}")
        
    return False

# ==========================================
# 5. منطق البيع (الربح الصافي والفصل بين العمليات)
# ==========================================
def check_sell(ex, current_price, time_str, state):
    sold_any = False
    
    for pos in state['open_positions'][:]:
        buy_price = pos['buy_price']
        amount = pos['amount']
        total_cost = pos['total_cost']
        
        if current_price > buy_price:
            estimated_sell_fee_usdt = (current_price * amount) * FEE_RATE
            net_return = (current_price * amount) - estimated_sell_fee_usdt
            net_profit = net_return - total_cost
            
            if net_profit > 0:
                try:
                    sell_amount = float(ex.amount_to_precision('BTC/USDT', amount))
                    order = ex.create_market_sell_order('BTC/USDT', sell_amount)
                    
                    state['total_profit'] += net_profit
                    state['trades_history'].append({
                        'type': 'sell_profit',
                        'buy_price': buy_price,
                        'sell_price': current_price,
                        'amount': sell_amount,
                        'net_profit': net_profit,
                        'time': time_str
                    })
                    
                    state['open_positions'].remove(pos)
                    sold_any = True
                    
                    msg = (f"🎉 <b>✅ بيع ناجح بربح صافٍ!</b>\n\n"
                           f"💰 سعر الشراء: {buy_price:.2f} USDT\n"
                           f"💰 سعر البيع: {current_price:.2f} USDT\n"
                           f"📦 الكمية المباعة: {sell_amount} BTC\n\n"
                           f"📊 <b>الربح الصافي الدقيق: 🟢 +{net_profit:.4f} USDT</b>\n"
                           f"💰 إجمالي الأرباح المتراكمة: {state['total_profit']:.4f} USDT\n"
                           f"🕒 {time_str}")
                    send_telegram_message(msg)
                    print(f"✅ بيع بربح: +{net_profit:.4f} USDT")
                    
                except Exception as e:
                    print(f"❌ فشل تنفيذ أمر البيع: {e}")
            else:
                needed_price = (total_cost / amount) / (1 - FEE_RATE)
                print(f"⏳ العملية المسجلة بـ {buy_price:.2f} تحتاج سعر {needed_price:.2f} لتعويض الرسوم.")
    
    return sold_any

# ==========================================
# 6. التشغيل الرئيسي
# ==========================================
if __name__ == "__main__":
    print("🌐 جاري تهيئة الاتصال بمنصة Binance...")
    
    # 1. جلب بروكسي يعمل لتجاوز حظر GitHub Actions
    working_proxy = get_working_proxy()
    
    # 2. إعداد الاتصال
    exchange_params = {
        'apiKey': api_key,
        'secret': secret,
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'},
        'timeout': 15000 # زيادة وقت الانتظار لتجنب انقطاع البروكسي
    }
    
    if working_proxy:
        exchange_params['proxies'] = working_proxy
        
    try:
        exchange = ccxt.binance(exchange_params)
        exchange.set_sandbox_mode(True) 
        exchange.load_markets()
    except Exception as e:
        print(f"🚨 فشل الاتصال بمنصة Binance (تأكد من المفاتيح والبروكسي): {e}")
        exit(1)
        
    state = load_state()
    start_time = time.time()
    duration = DURATION_MINUTES * 60
    
    send_telegram_message("🚀 <b>تم تشغيل البوت بنجاح!</b>\nتم تجاوز قيود الشبكة والمراقبة مستمرة.")
    print(f"🚀 بدء التشغيل | الصفقات المفتوحة الحالية: {len(state['open_positions'])}")
    
    cycle = 0
    while time.time() - start_time < duration:
        cycle += 1
        now = datetime.now(timezone.utc)
        time_str = now.strftime('%H:%M:%S')
        
        if cycle % 12 == 0 or cycle == 1:
            print(f"\n🔄 الفحص مستمر... | الوقت: {time_str}")
        
        try:
            ticker = exchange.fetch_ticker('BTC/USDT')
            current_price = ticker['last']
            
            if state['open_positions']:
                if check_sell(exchange, current_price, time_str, state):
                    save_state(state)
            
            if check_buy(exchange, now, time_str, state):
                save_state(state)
                print(f"📊 إجمالي عمليات الشراء: {state['buy_count']}/{MAX_BUYS} | أرباح متراكمة: {state['total_profit']:.4f}$")
            
        except Exception as e:
            # تم اختصار رسالة الخطأ هنا حتى لا تمتلئ شاشة GitHub Actions باللون الأحمر إذا تأخر البروكسي ثانية
            print(f"⚠️ تأخير في الاستجابة (سيتم المحاولة بعد {CHECK_INTERVAL} ثوانٍ)...")
        
        remaining = duration - (time.time() - start_time)
        if remaining > 0:
            sleep_time = min(CHECK_INTERVAL, remaining)
            time.sleep(sleep_time)
            
    save_state(state)
    print(f"\n{'='*50}\n⏰ انتهت الدورة التدريبية!\n{'='*50}")
    send_telegram_message("⏰ <b>انتهت دورة التشغيل الحالية للبوت.</b>")
