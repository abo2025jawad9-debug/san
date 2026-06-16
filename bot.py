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
DURATION_MINUTES = 360
CHECK_INTERVAL = 60
MIN_BTC_AMOUNT = 0.0001
STATE_FILE = 'state.json'
MIN_PROFIT_PERCENT = 0.003  # 0.3% ربح صافٍ

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
# 3. حفظ واسترجاع الحالة (مُحسّن)
# ==========================================
def load_state():
    default_state = {
        'positions': [],           # [{'buy_price', 'amount', 'actual_spent', 'buy_time', 'target_sell_price', 'is_first_buy', 'signal_time'}]
        'buy_count': 0,
        'total_usdt_spent': 0.0,
        'total_profit': 0.0,
        'total_loss': 0.0,
        'processed_signals': [],    # إشارات تم شراؤها
        'processed_dca': [],        # أوقات DCA تم شراؤها (لمنع التكرار في نفس النزول)
        'trades_history': [],
        'daily_low': None,
        'daily_high': None,
        'last_dca_price': None,    # آخر سعر DCA (لمنع الشراء المتكرر بنفس السعر)
        'session_start': None       # وقت بدء الجلسة
    }
    
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
            
            # ✅ إضافة أي مفاتيح مفقودة
            for key, value in default_state.items():
                if key not in state:
                    state[key] = value
            
            # ✅ التأكد من أن كل position تحتوي على كل الحقول
            for pos in state.get('positions', []):
                if 'signal_time' not in pos:
                    pos['signal_time'] = None
                if 'is_first_buy' not in pos:
                    pos['is_first_buy'] = False
                if 'actual_spent' not in pos:
                    pos['actual_spent'] = pos['buy_price'] * pos['amount'] * 1.001
            
            print(f"📂 تم تحميل الحالة: {len(state['positions'])} positions | {state['buy_count']} مشتريات")
            return state
            
        except Exception as e:
            print(f"❌ خطأ في قراءة state.json: {e} — إنشاء حالة جديدة")
    
    return default_state

def save_state(state):
    """حفظ الحالة فوراً وفي كل تغيير"""
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
        print(f"💾 حفظ: {len(state['positions'])} positions | ربح: {state['total_profit']:.6f}")
    except Exception as e:
        print(f"❌ فشل حفظ الحالة: {e}")

# ==========================================
# 4. تنظيف الإشارات القديمة
# ==========================================
def clean_old_signals(state):
    now = datetime.now(timezone.utc)
    
    # تنظيف الإشارات الزمنية
    kept_signals = []
    for sig_time_str in state['processed_signals']:
        try:
            sig_time = datetime.strptime(sig_time_str, '%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc)
            if sig_time > now - timezone.timedelta(days=1):  # احتفظ بـ 24 ساعة
                kept_signals.append(sig_time_str)
        except:
            pass
    state['processed_signals'] = kept_signals
    
    # تنظيف DCA القديم (أكثر من 24 ساعة)
    kept_dca = []
    for dca_time in state.get('processed_dca', []):
        try:
            dca_dt = datetime.strptime(dca_time, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
            if dca_dt > now - timezone.timedelta(days=1):
                kept_dca.append(dca_time)
        except:
            pass
    state['processed_dca'] = kept_dca
    
    return state

# ==========================================
# 5. الاتصال بـ Binance
# ==========================================
def get_exchange():
    print("🌐 الاتصال بـ Binance...")
    try:
        ex = ccxt.binance({
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        ex.set_sandbox_mode(True)
        ex.load_markets()
        print("✅ تم الاتصال")
        return ex
    except Exception as e:
        print(f"❌ فشل: {e}")
        return None

# ==========================================
# 6. جلب السعر مع retry
# ==========================================
def fetch_price_with_retry(ex, symbol='BTC/USDT', max_retries=3):
    for attempt in range(max_retries):
        try:
            ticker = ex.fetch_ticker(symbol)
            return ticker['last']
        except Exception as e:
            print(f"⚠️ محاولة {attempt+1}/{max_retries}: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
    return None

# ==========================================
# 7. جلب أعلى/أقل سعر في 24 ساعة
# ==========================================
def get_daily_range(ex, symbol='BTC/USDT'):
    try:
        ticker = ex.fetch_ticker(symbol)
        return {
            'high': ticker['high'],
            'low': ticker['low'],
            'last': ticker['last']
        }
    except Exception as e:
        print(f"❌ فشل جلب النطاق اليومي: {e}")
        return None

# ==========================================
# 8. جلب السعر قبل ساعة
# ==========================================
def get_price_1h_ago(ex, symbol='BTC/USDT'):
    try:
        ohlcv = ex.fetch_ohlcv(symbol, timeframe='1h', limit=3)
        return ohlcv[-2][4]
    except Exception as e:
        print(f"❌ فشل جلب سعر الساعة الماضية: {e}")
        return None

# ==========================================
# 9. جلب الرصيد
# ==========================================
def get_balance(ex):
    try:
        bal = ex.fetch_balance()
        return bal['USDT']['free'], bal['BTC']['free']
    except Exception as e:
        print(f"❌ فشل جلب الرصيد: {e}")
        return None, None

# ==========================================
# 10. جدول الإشارات (للعملية الأولى فقط)
# ==========================================
schedule = [
    {"time": "2026-06-16 22:15", "type": "نزول"},
    {"time": "2026-06-16 23:15", "type": "نزول"},
    {"time": "2026-06-16 21:29", "type": "نزول"},
    {"time": "2026-06-15 23:15", "type": "صعود ونزول"},
    {"time": "2026-06-15 21:15", "type": "نزول"},
    {"time": "2026-06-14 22:15", "type": "صعود"},
    {"time": "2026-06-14 21:15", "type": "نزول"},
    {"time": "2026-06-14 20:15", "type": "نزول"},
    {"time": "2026-06-14 00:15", "type": "نزول"},
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
# 11. إيجاد أقرب إشارة
# ==========================================
def get_next_signal():
    now = datetime.now(timezone.utc)
    future_signals = []
    for signal in schedule:
        signal_time = datetime.strptime(signal["time"], '%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc)
        if signal_time > now:
            future_signals.append((signal_time, signal["type"]))
    
    if not future_signals:
        return None, None, None
    
    future_signals.sort(key=lambda x: x[0])
    next_time, next_type = future_signals[0]
    time_diff = next_time - now
    hours = time_diff.seconds // 3600
    minutes = (time_diff.seconds % 3600) // 60
    time_str = f"{hours} ساعة و {minutes} دقيقة" if hours > 0 else f"{minutes} دقيقة"
    
    return next_time.strftime('%Y-%m-%d %H:%M'), next_type, time_str

# ==========================================
# 12. حساب متوسط سعر الشراء
# ==========================================
def get_avg_buy_price(positions):
    if not positions:
        return 0
    total_cost = sum(p['actual_spent'] for p in positions)
    total_amount = sum(p['amount'] for p in positions)
    return total_cost / total_amount if total_amount > 0 else 0

# ==========================================
# 13. البيع الذكي — يبيع الـ position التي تحقق ربحها
# ==========================================
def check_sell(ex, current_price, time_str, state):
    sold_any = False
    
    for pos in state['positions'][:]:
        target_sell = pos['target_sell_price']
        
        print(f"📊 فحص position #{state['positions'].index(pos)+1}: "
              f"شراء {pos['buy_price']:.2f}$ | هدف: {target_sell:.2f}$ | حالي: {current_price:.2f}$")
        
        if current_price >= target_sell:
            usdt_before, btc_before = get_balance(ex)
            
            try:
                order = ex.create_market_sell_order('BTC/USDT', pos['amount'])
                time.sleep(3)
                
                usdt_after, btc_after = get_balance(ex)
                
                if usdt_before is not None and usdt_after is not None:
                    actual_pnl = usdt_after - usdt_before
                else:
                    actual_pnl = (current_price - pos['buy_price']) * pos['amount'] * 0.998
                
                if actual_pnl > 0:
                    state['total_profit'] += actual_pnl
                    
                    # ✅ حفظ قبل الحذف
                    sold_position = pos.copy()
                    state['positions'].remove(pos)
                    
                    state['trades_history'].append({
                        'type': 'sell_profit',
                        'buy_price': sold_position['buy_price'],
                        'sell_price': current_price,
                        'amount': sold_position['amount'],
                        'actual_pnl': actual_pnl,
                        'time': time_str
                    })
                    
                    # ✅ حفظ فوري بعد البيع
                    save_state(state)
                    
                    usdt_bef_str = f"{usdt_before:.6f}" if usdt_before is not None else "غير معروف"
                    usdt_aft_str = f"{usdt_after:.6f}" if usdt_after is not None else "غير معروف"
                    
                    msg = (f"🎉 <b>✅ بيع ناجح!</b>\n\n"
                           f"📋 <b>تفاصيل الـ position:</b>\n"
                           f"💰 سعر الشراء: {sold_position['buy_price']:.2f} USDT\n"
                           f"💰 سعر البيع: {current_price:.2f} USDT\n"
                           f"📦 الكمية: {sold_position['amount']:.6f} BTC\n"
                           f"🎯 الهدف: {sold_position['target_sell_price']:.2f} USDT\n"
                           f"🕒 وقت الشراء: {sold_position['buy_time']}\n\n"
                           f"📊 <b>الربح الفعلي: 🟢 +{actual_pnl:.6f} USDT</b>\n\n"
                           f"💵 رصيد قبل: {usdt_bef_str}\n"
                           f"💵 رصيد بعد: {usdt_aft_str}\n"
                           f"📈 الفرق: +{actual_pnl:.6f} USDT\n\n"
                           f"💰 إجمالي أرباح: {state['total_profit']:.6f} USDT\n"
                           f"📦 Positions متبقية: {len(state['positions'])}\n"
                           f"🕒 {time_str}")
                    send_telegram_message(msg)
                    print(f"✅ بيع position بربح: +{actual_pnl:.6f}")
                    sold_any = True
                else:
                    print(f"⏳ لم يُباع: ربح فعلي سالب {actual_pnl:.6f}")
                    
            except Exception as e:
                print(f"❌ فشل بيع: {e}")
        else:
            needed = ((target_sell - current_price) / current_price) * 100
            print(f"⏳ لم يصل للهدف: يحتاج +{needed:.2f}%")
    
    return sold_any

# ==========================================
# 14. الشراء — شروط متعددة
# ==========================================
checked_signals_current_run = set()

def check_buy(ex, now, time_str, state):
    if state['buy_count'] >= MAX_BUYS:
        return False
    
    current_price = fetch_price_with_retry(ex)
    if current_price is None:
        return False
    
    price_1h_ago = get_price_1h_ago(ex)
    daily_range = get_daily_range(ex)
    
    if daily_range:
        state['daily_high'] = daily_range['high']
        state['daily_low'] = daily_range['low']
    
    # ==========================================
    # الشرط 1: العملية الأولى (من الجدول الزمني)
    # ==========================================
    for signal in schedule:
        signal_time = datetime.strptime(signal["time"], '%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc)
        time_diff = abs((now - signal_time).total_seconds())
        
        if time_diff <= 300:
            if signal["time"] in state['processed_signals']:
                continue
            
            if price_1h_ago and price_1h_ago > current_price:
                result = execute_buy(ex, current_price, time_str, state, is_first_buy=True, signal=signal)
                if result:
                    save_state(state)  # ✅ حفظ فوري
                return result
            else:
                if signal["time"] not in checked_signals_current_run:
                    msg = (f"🔍 <b>فحص إشارة أولية: {signal['time']}</b>\n"
                           f"⚠️ النوع: {signal['type']}\n"
                           f"📊 السعر قبل ساعة: {price_1h_ago:.2f if price_1h_ago else 'غير معروف'}\n"
                           f"💰 السعر الحالي: {current_price:.2f}\n"
                           f"🚫 <b>لم يتحقق شرط النزول</b>\n"
                           f"🕒 {time_str

