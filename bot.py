import ccxt
import requests
import time
import json
import os
from datetime import datetime, timezone

# ==========================================
# 1. إعداد مفاتيح API
# ==========================================
api_key = 'dmyc2X0llvZ1A1zGAy9wfkqJHqZC20Uv04iYwBmOrnBMLJlnH7SZOsPt4eYGYnoJ'.strip()
secret = 'uVax1wfQo0Ns1XIhGgsW4j2yjgB9VPlQWYzWvt1sAeg640WpGRCSqFMPvVyNtu6S'.strip()

TELEGRAM_TOKEN = '8777604170:AAGVQWj7KtRZWKjZQ0BuyIZCHJ3FCmFgQP4'
TELEGRAM_CHAT_ID = '6390985342'

# ==========================================
# إعدادات التداول
# ==========================================
MAX_BUYS = 7
MAX_TOTAL_USDT = 50
TRADE_USDT_PER_BUY = MAX_TOTAL_USDT // MAX_BUYS
DURATION_MINUTES = 180
CHECK_INTERVAL = 60
MIN_BTC_AMOUNT = 0.0001
STATE_FILE = 'state.json'

# ==========================================
# 2. دالة تليجرام
# ==========================================
def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ Telegram: {e}")

# ==========================================
# 3. حفظ واسترجاع الحالة
# ==========================================
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {
        'open_positions': [],
        'buy_count': 0,
        'total_usdt_spent': 0.0,
        'processed_signals': []
    }

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)
    print(f"💾 تم حفظ الحالة: {state['buy_count']} شراء | {len(state['open_positions'])} مفتوحة")

# ==========================================
# 4. بروكسيات
# ==========================================
def get_auto_proxy_exchange():
    print("🌐 جاري سحب البروكسيات...")
    try:
        url = "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt"
        response = requests.get(url, timeout=10)
        proxies_list = response.text.split('\n')[:150]
        for p in proxies_list:
            if not p.strip(): continue
            proxy_url = f"http://{p.strip()}"
            try:
                ex = ccxt.binance({
                    'apiKey': api_key, 'secret': secret,
                    'enableRateLimit': True,
                    'proxies': {'http': proxy_url, 'https': proxy_url},
                    'options': {'defaultType': 'spot'}
                })
                ex.set_sandbox_mode(True)
                ex.load_markets()
                return ex, proxy_url
            except:
                continue
    except Exception as e:
        print(f"❌ خطأ بروكسيات: {e}")
    return None, None

# ==========================================
# 5. جدول الإشارات
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
# 6. البيع (مع التأكد من الربح)
# ==========================================
def check_sell(ex, current_price, time_str, state):
    sold_any = False
    for pos in state['open_positions'][:]:
        entry_price = pos['price']
        amount = pos['amount']
        if current_price > entry_price:
            try:
                ex.create_market_sell_order('BTC/USDT', amount)
                profit = (current_price - entry_price) * amount
                msg = (f"✅ <b>بيع بربح!</b>\n"
                       f"💰 شراء: {entry_price:.2f}$ | بيع: {current_price:.2f}$\n"
                       f"📦 {amount:.6f} BTC | ربح: {profit:.4f} USDT\n🕒 {time_str}")
                send_telegram_message(msg)
                print(f"✅ بيع بربح: {profit:.4f} USDT")
                state['open_positions'].remove(pos)
                sold_any = True
            except Exception as e:
                print(f"❌ فشل بيع: {e}")
        else:
            print(f"⏳ Position: شراء {entry_price:.2f}$ | حالي {current_price:.2f}$ (لا ربح)")
    return sold_any

# ==========================================
# 7. الشراء (السعر قبل ساعة أعلى من الحالي)
# ==========================================
def check_buy(ex, now, time_str, state):
    if state['buy_count'] >= MAX_BUYS:
        return False
    for signal in schedule:
        signal_time = datetime.strptime(signal["time"], '%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc)
        time_diff = abs((now - signal_time).total_seconds())
        if time_diff <= 300:
            if signal["time"] in state['processed_signals']:
                continue
            try:
                ohlcv = ex.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=3)
                price_1h_ago = ohlcv[-2][4]
                ticker = ex.fetch_ticker('BTC/USDT')
                current_price = ticker['last']
                print(f"📊 {signal['time']} | قبل ساعة: {price_1h_ago:.2f}$ | حالي: {current_price:.2f}$")
                
                if price_1h_ago > current_price:
                    amount = TRADE_USDT_PER_BUY / current_price
                    if amount < MIN_BTC_AMOUNT:
                        amount = MIN_BTC_AMOUNT
                    actual_usdt = amount * current_price
                    
                    if state['total_usdt_spent'] + actual_usdt > MAX_TOTAL_USDT:
                        state['processed_signals'].append(signal["time"])
                        return False
                    
                    ex.create_market_buy_order('BTC/USDT', amount)
                    state['buy_count'] += 1
                    state['total_usdt_spent'] += actual_usdt
                    state['open_positions'].append({
                        'price': current_price, 'amount': amount, 'signal_time': signal["time"]
                    })
                    state['processed_signals'].append(signal["time"])
                    
                    msg = (f"🟢 <b>شراء #{state['buy_count']}</b>\n"
                           f"⚠️ {signal['type']} | 💰 {current_price:.2f} USDT\n"
                           f"📦 {amount:.6f} BTC | 💵 {actual_usdt:.2f} USDT\n"
                           f"📊 إجمالي: {state['total_usdt_spent']:.2f}/{MAX_TOTAL_USDT} USDT\n"
                           f"🔢 متبقي: {MAX_BUYS - state['buy_count']} | 🕒 {time_str}")
                    send_telegram_message(msg)
                    print(f"✅ شراء #{state['buy_count']} بسعر {current_price:.2f}$")
                    return True
                else:
                    print(f"🚫 شرط غير متحقق")
                    state['processed_signals'].append(signal["time"])
                    return False
            except Exception as e:
                print(f"❌ خطأ شراء: {e}")
                return False
    return False

# ==========================================
# 8. التشغيل الرئيسي (3 ساعات)
# ==========================================
if __name__ == "__main__":
    exchange, valid_proxy = get_auto_proxy_exchange()
    if exchange is None:
        send_telegram_message("🚨 فشل الاتصال بجميع البروكسيات.")
        exit(1)
    
    state = load_state()
    start_time = time.time()
    duration = DURATION_MINUTES * 60
    
    send_telegram_message(
        f"🚀 <b>بدأت الدورة (3 ساعات)</b>\n"
        f"📊 Positions سابقة: {len(state['open_positions'])}\n"
        f"💵 منفق سابق: {state['total_usdt_spent']:.2f} USDT\n"
        f"🕒 {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}"
    )
    
    print(f"🚀 بدء 3 ساعات | Positions سابقة: {len(state['open_positions'])}")
    
    cycle = 0
    while time.time() - start_time < duration:
        cycle += 1
        now = datetime.now(timezone.utc)
        time_str = now.strftime('%H:%M:%S')
        elapsed = (time.time() - start_time) / 60
        
        print(f"\n{'='*50}")
        print(f"🔄 Tick #{cycle} | {time_str} | مضى: {elapsed:.0f} دقيقة")
        
        try:
            ticker = exchange.fetch_ticker('BTC/USDT')
            current_price = ticker['last']
            print(f"💰 BTC: {current_price:.2f} USDT")
            
            # 1. بيع أولاً
            if state['open_positions']:
                check_sell(exchange, current_price, time_str, state)
                save_state(state)
            
            # 2. شراء
            if state['buy_count'] < MAX_BUYS:
                if check_buy(exchange, now, time_str, state):
                    save_state(state)
            else:
                print(f"⛔ وصلنا للحد ({MAX_BUYS})")
            
            print(f"📊 {state['buy_count']} شراء | {len(state['open_positions'])} مفتوحة | {state['total_usdt_spent']:.2f} USDT")
            
        except Exception as e:
            print(f"❌ خطأ Tick: {e}")
            send_telegram_message(f"⚠️ خطأ Tick #{cycle}: {e}")
        
        # انتظار
        remaining = duration - (time.time() - start_time)
        if remaining > 0:
            sleep_time = min(CHECK_INTERVAL, remaining)
            print(f"💤 {sleep_time:.0f} ثانية متبقية...")
            time.sleep(sleep_time)
    
    # ==========================================
    # نهاية الدورة: بيع ما أمكن + حفظ الحالة
    # ==========================================
    print(f"\n{'='*50}\n⏰ انتهت الـ 3 ساعات!\n{'='*50}")
    
    if state['open_positions']:
        try:
            ticker = exchange.fetch_ticker('BTC/USDT')
            current_price = ticker['last']
            for pos in state['open_positions'][:]:
                if current_price > pos['price']:
                    exchange.create_market_sell_order('BTC/USDT', pos['amount'])
                    profit = (current_price - pos['price']) * pos['amount']
                    send_telegram_message(f"⏰ <b>بيع نهائي</b> | ربح: {profit:.4f} USDT")
                    state['open_positions'].remove(pos)
                else:
                    send_telegram_message(
                        f"⚠️ <b>Position باقٍ</b>\n"
                        f"شراء: {pos['price']:.2f}$ | حالي: {current_price:.2f}$\n"
                        f"سيتم متابعته في الدورة القادمة."
                    )
        except Exception as e:
            print(f"❌ خطأ بيع نهائي: {e}")
    
    save_state(state)
    
    final_msg = (
        f"✅ <b>انتهت الدورة</b>\n"
        f"🔢 شراء: {state['buy_count']} | 📊 مفتوحة: {len(state['open_positions'])}\n"
        f"💵 منفق: {state['total_usdt_spent']:.2f} USDT\n"
        f"🕒 {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}\n"
        f"💤 إعادة التشغيل بعد ساعة."
    )
    send_telegram_message(final_msg)
    print(f"✅ انتهى | {state['buy_count']} شراء | {len(state['open_positions'])} مفتوحة")
