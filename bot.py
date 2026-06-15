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
DURATION_MINUTES =360
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
    default_state = {
        'open_positions': [],
        'buy_count': 0,
        'total_usdt_spent': 0.0,
        'total_fees_paid': 0.0,
        'processed_signals': [],
        'total_profit': 0.0,
        'total_loss': 0.0,
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
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

# ==========================================
# 4. تنظيف الإشارات القديمة
# ==========================================
def clean_old_signals(state):
    now = datetime.now(timezone.utc)
    kept = []
    for sig_time_str in state['processed_signals']:
        try:
            sig_time = datetime.strptime(sig_time_str, '%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc)
            if sig_time > now:
                kept.append(sig_time_str)
        except:
            pass
    state['processed_signals'] = kept
    return state

# ==========================================
# 5. بروكسيات
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
# 6. جلب الرصيد
# ==========================================
def get_balance(ex):
    try:
        bal = ex.fetch_balance()
        usdt = bal['USDT']['free']
        btc = bal['BTC']['free']
        return usdt, btc
    except Exception as e:
        print(f"❌ فشل جلب الرصيد: {e}")
        return None, None

# ==========================================
# 7. جدول الإشارات
# ==========================================
schedule = [
    {"time": "2026-06-13 11:59", "type": "نزول"},
    {"time": "2026-06-02 05:29", "type": "نزول"},
    {"time": "2026-06-15 22:29", "type": "نزول"},
    {"time": "2026-06-15 23:15", "type": "صعود ونزول"},
    {"time": "2026-06-15 21:15", "type": "نزول"},
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
# 8. إيجاد أقرب موعد إشارة
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
# 9. البيع — فقط إذا كان الربح الفعلي إيجابي
# ==========================================
def check_sell(ex, current_price, time_str, state):
    sold_any = False
    for pos in state['open_positions'][:]:
        entry_price = pos['price']
        amount = pos['amount']
        
        usdt_before, btc_before = get_balance(ex)
        print(f"💰 الرصيد قبل البيع: USDT={usdt_before}, BTC={btc_before}" if usdt_before else "❌ فشل جلب الرصيد")
        
        min_sell_price = entry_price * 1.003
        
        if current_price >= min_sell_price:
            try:
                order = ex.create_market_sell_order('BTC/USDT', amount)
                time.sleep(3)
                
                usdt_after, btc_after = get_balance(ex)
                print(f"💰 الرصيد بعد البيع: USDT={usdt_after}, BTC={btc_after}" if usdt_after else "❌ فشل جلب الرصيد")
                
                if usdt_before is not None and usdt_after is not None:
                    actual_pnl = usdt_after - usdt_before
                else:
                    actual_pnl = (current_price - entry_price) * amount * 0.998
                
                if actual_pnl > 0:
                    state['total_profit'] += actual_pnl
                    
                    state['trades_history'].append({
                        'type': 'sell_profit',
                        'buy_price': entry_price,
                        'sell_price': current_price,
                        'amount': amount,
                        'actual_pnl': actual_pnl,
                        'usdt_before': usdt_before,
                        'usdt_after': usdt_after,
                        'time': time_str
                    })
                    
                    usdt_bef_str = f"{usdt_before:.6f}" if usdt_before is not None else "غير معروف"
                    usdt_aft_str = f"{usdt_after:.6f}" if usdt_after is not None else "غير معروف"
                    
                    msg = (f"🎉 <b>✅ بيع ناجح بربح صافٍ!</b>\n\n"
                           f"💰 سعر الشراء: {entry_price:.2f} USDT\n"
                           f"💰 سعر البيع: {current_price:.2f} USDT\n"
                           f"📦 الكمية المباعة: {amount:.6f} BTC\n\n"
                           f"📊 <b>الربح الفعلي: 🟢 +{actual_pnl:.6f} USDT</b>\n\n"
                           f"💵 رصيد USDT قبل: {usdt_bef_str}\n"
                           f"💵 رصيد USDT بعد: {usdt_aft_str}\n"
                           f"📈 الفرق: +{actual_pnl:.6f} USDT\n\n"
                           f"💰 إجمالي أرباح: {state['total_profit']:.6f} USDT\n"
                           f"🕒 {time_str}")
                    send_telegram_message(msg)
                    print(f"✅ بيع بربح: +{actual_pnl:.6f} USDT")
                    state['open_positions'].remove(pos)
                    sold_any = True
                else:
                    usdt_bef_str = f"{usdt_before:.6f}" if usdt_before is not None else "غير معروف"
                    usdt_aft_str = f"{usdt_after:.6f}" if usdt_after is not None else "غير معروف"
                    
                    msg = (f"⏳ <b>لم يُباع — الربح الفعلي سالب</b>\n\n"
                           f"💰 سعر الشراء: {entry_price:.2f} USDT\n"
                           f"💰 سعر البيع الحالي: {current_price:.2f} USDT\n"
                           f"📦 الكمية: {amount:.6f} BTC\n"
                           f"📉 <b>الربح الفعلي المحتمل: 🔴 {actual_pnl:.6f} USDT</b>\n"
                           f"💵 رصيد USDT قبل: {usdt_bef_str}\n"
                           f"💵 رصيد USDT بعد: {usdt_aft_str}\n\n"
                           f"⏳ <b>سيتم الانتظار حتى يرتفع السعر أكثر...</b>\n"
                           f"🎯 السعر المطلوب: {min_sell_price:.2f} USDT\n"
                           f"🕒 {time_str}")
                    send_telegram_message(msg)
                    print(f"⏳ لم يُباع: ربح فعلي سالب {actual_pnl:.6f} — في الانتظار")
                    
            except Exception as e:
                print(f"❌ فشل بيع: {e}")
                send_telegram_message(f"❌ <b>فشل البيع:</b>\n{e}\n🕒 {time_str}")
        else:
            needed_rise = ((min_sell_price - current_price) / current_price) * 100
            print(f"⏳ لم يُباع: السعر {current_price:.2f} < الحد {min_sell_price:.2f} (يحتاج ارتفاع {needed_rise:.2f}%)")
    return sold_any

# ==========================================
# 10. الشراء
# ==========================================
checked_signals_current_run = set()

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
                
                if signal["time"] not in checked_signals_current_run:
                    check_msg = (f"🔍 <b>فحص إشارة: {signal['time']}</b>\n"
                               f"⚠️ النوع: {signal['type']}\n"
                               f"📊 السعر قبل ساعة: {price_1h_ago:.2f} USDT\n"
                               f"💰 السعر الحالي: {current_price:.2f} USDT\n"
                               f"🕒 {time_str}")
                    send_telegram_message(check_msg)
                    checked_signals_current_run.add(signal["time"])
                
                if price_1h_ago > current_price:
                    usdt_before, btc_before = get_balance(ex)
                    print(f"💰 الرصيد قبل الشراء: USDT={usdt_before}, BTC={btc_before}" if usdt_before else "❌ فشل جلب الرصيد")
                    
                    amount = TRADE_USDT_PER_BUY / current_price
                    if amount < MIN_BTC_AMOUNT:
                        amount = MIN_BTC_AMOUNT
                    
                    estimated_cost = amount * current_price * 1.001
                    
                    if state['total_usdt_spent'] + estimated_cost > MAX_TOTAL_USDT:
                        msg = (f"⛔ <b>تم إلغاء الشراء</b>\n"
                               f"سيتجاوز الحد الإجمالي ({MAX_TOTAL_USDT} USDT)\n"
                               f"💵 المنفق: {state['total_usdt_spent']:.2f} USDT\n"
                               f"🕒 {time_str}")
                        send_telegram_message(msg)
                        return False
                    
                    order = ex.create_market_buy_order('BTC/USDT', amount)
                    time.sleep(3)
                    
                    usdt_after, btc_after = get_balance(ex)
                    print(f"💰 الرصيد بعد الشراء: USDT={usdt_after}, BTC={btc_after}" if usdt_after else "❌ فشل جلب الرصيد")
                    
                    if usdt_before is not None and usdt_after is not None:
                        actual_spent = usdt_before - usdt_after
                        actual_btc_gained = btc_after - btc_before if btc_before else amount * 0.999
                    else:
                        actual_spent = amount * current_price * 1.001
                        actual_btc_gained = amount * 0.999
                    
                    state['buy_count'] += 1
                    state['total_usdt_spent'] += actual_spent
                    state['open_positions'].append({
                        'price': current_price,
                        'amount': actual_btc_gained,
                        'signal_time': signal["time"],
                        'actual_spent': actual_spent,
                        'usdt_before_buy': usdt_before,
                        'usdt_after_buy': usdt_after
                    })
                    state['processed_signals'].append(signal["time"])
                    
                    state['trades_history'].append({
                        'type': 'buy',
                        'price': current_price,
                        'amount': actual_btc_gained,
                        'actual_spent': actual_spent,
                        'usdt_before': usdt_before,
                        'usdt_after': usdt_after,
                        'time': time_str
                    })
                    
                    min_sell = current_price * 1.003
                    usdt_bef_str = f"{usdt_before:.6f}" if usdt_before is not None else "غير معروف"
                    usdt_aft_str = f"{usdt_after:.6f}" if usdt_after is not None else "غير معروف"
                    
                    msg = (f"🟢 <b>✅ شراء ناجح #{state['buy_count']}</b>\n\n"
                           f"⚠️ الإشارة: {signal['type']}\n"
                           f"💰 السعر: {current_price:.2f} USDT\n"
                           f"📦 الكمية: {actual_btc_gained:.6f} BTC\n"
                           f"💵 المبلغ المدفوع: {actual_spent:.6f} USDT\n\n"
                           f"💵 رصيد USDT قبل: {usdt_bef_str}\n"
                           f"💵 رصيد USDT بعد: {usdt_aft_str}\n\n"
                           f"🎯 <b>سعر البيع المطلوب للربح: {min_sell:.2f} USDT</b>\n"
                           f"📊 إجمالي منفق: {state['total_usdt_spent']:.2f}/{MAX_TOTAL_USDT} USDT\n"
                           f"🔢 المتبقي: {MAX_BUYS - state['buy_count']} عمليات\n"
                           f"🕒 {time_str}")
                    send_telegram_message(msg)
                    print(f"✅ شراء #{state['buy_count']} | مبلغ: {actual_spent:.6f} | بيع عند: {min_sell:.2f}")
                    return True
                else:
                    if signal["time"] not in checked_signals_current_run:
                        msg = (f"🚫 <b>تم رفض الشراء</b>\n"
                               f"السعر قبل ساعة ({price_1h_ago:.2f}) ليس أعلى من الحالي ({current_price:.2f})\n"
                               f"سيتم إعادة المحاولة...\n🕒 {time_str}")
                        send_telegram_message(msg)
                    print(f"🚫 شرط غير متحقق: {price_1h_ago:.2f} vs {current_price:.2f}")
                    return False
                    
            except Exception as e:
                msg = f"❌ <b>خطأ في معالجة إشارة {signal['time']}:</b>\n{e}\n🕒 {time_str}"
                send_telegram_message(msg)
                return False
    return False

# ==========================================
# 11. التقرير الدوري (كل 10 دقائق)
# ==========================================
def send_status_report(tick_num, time_str, elapsed_min, current_price, state, next_signal_info):
    next_time, next_type, next_diff = next_signal_info
    
    usdt_bal, btc_bal = get_balance(exchange)
    
    open_value = 0
    unrealized_pnl = 0
    
    for pos in state['open_positions']:
        val = pos['amount'] * current_price
        open_value += val
        gross = (current_price - pos['price']) * pos['amount']
        unrealized_pnl += gross
    
    pnl_emoji = "🟢" if unrealized_pnl >= 0 else "🔴"
    pnl_text = f"+{unrealized_pnl:.4f}" if unrealized_pnl >= 0 else f"{unrealized_pnl:.4f}"
    
    usdt_bal_str = f"{usdt_bal:.6f}" if usdt_bal is not None else "غير معروف"
    btc_bal_str = f"{btc_bal:.6f}" if btc_bal is not None else "غير معروف"
    
    msg = (f"📊 <b>تقرير الدورة #{tick_num}</b>\n\n"
           f"🕒 الوقت: {time_str} | مضى: {elapsed_min:.0f} دقيقة\n"
           f"💰 سعر BTC: {current_price:.2f} USDT\n\n"
           f"💵 <b>الرصيد الفعلي:</b>\n"
           f"   USDT: {usdt_bal_str}\n"
           f"   BTC: {btc_bal_str}\n\n"
           f"📈 <b>الحالة:</b>\n"
           f"🔢 عمليات شراء: {state['buy_count']}/{MAX_BUYS}\n"
           f"📦 Positions مفتوحة: {len(state['open_positions'])}\n"
           f"💵 قيمة المفتوحة: {open_value:.2f} USDT\n"
           f"📊 ربح/خسارة غير محقق: {pnl_emoji} {pnl_text} USDT\n"
           f"💰 إجمالي أرباح محققة: {state['total_profit']:.6f} USDT\n"
           f"📉 إجمالي خسائر: {state['total_loss']:.6f} USDT\n"
           f"💵 إجمالي منفق: {state['total_usdt_spent']:.2f}/{MAX_TOTAL_USDT} USDT\n\n")
    
    if next_time:
        msg += (f"⏰ <b>أقرب إشارة قادمة:</b>\n"
                f"📅 {next_time}\n"
                f"⚠️ النوع: {next_type}\n"
                f"⏳ بعد: {next_diff}\n\n")
    else:
        msg += "⏰ لا توجد إشارات مستقبلية.\n\n"
    
    if state['open_positions']:
        msg += "📋 <b>Positions المفتوحة (في الانتظار):</b>\n"
        for i, pos in enumerate(state['open_positions'], 1):
            min_sell = pos['price'] * 1.003
            needed = ((min_sell - current_price) / current_price) * 100
            msg += (f"  #{i}: شراء {pos['price']:.2f}$ | حالي {current_price:.2f}$\n"
                   f"      🎯 بيع عند: {min_sell:.2f}$ (يحتاج +{needed:.2f}%)\n")
    
    send_telegram_message(msg)

# ==========================================
# 12. التشغيل الرئيسي (3 ساعات)
# ==========================================
if __name__ == "__main__":
    global exchange
    exchange, valid_proxy = get_auto_proxy_exchange()
    if exchange is None:
        send_telegram_message("🚨 <b>فشل الاتصال بجميع البروكسيات.</b> تم إيقاف البوت.")
        exit(1)
    
    state = load_state()
    state = clean_old_signals(state)
    
    start_time = time.time()
    duration = DURATION_MINUTES * 60
    
    opening_usdt, opening_btc = get_balance(exchange)
    
    next_time, next_type, next_diff = get_next_signal()
    
    op_usdt_str = f"{opening_usdt:.6f}" if opening_usdt is not None else "غير معروف"
    op_btc_str = f"{opening_btc:.6f}" if opening_btc is not None else "غير معروف"
    
    send_telegram_message(
        f"🚀 <b>بدأت دورة البوت (3 ساعات)</b>\n\n"
        f"💵 رصيد USDT: {op_usdt_str}\n"
        f"📦 رصيد BTC: {op_btc_str}\n"
        f"📊 Positions سابقة: {len(state['open_positions'])}\n"
        f"💵 منفق سابق: {state['total_usdt_spent']:.2f} USDT\n"
        f"💰 أرباح سابقة: {state['total_profit']:.6f} USDT\n"
        f"⏰ أقرب إشارة: {next_time or 'لا يوجد'} ({next_type or ''})\n"
        f"🕒 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )
    
    print(f"🚀 بدء 3 ساعات | Positions: {len(state['open_positions'])}")
    
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
            
            if state['open_positions']:
                check_sell(exchange, current_price, time_str, state)
                save_state(state)
            
            if state['buy_count'] < MAX_BUYS:
                if check_buy(exchange, now, time_str, state):
                    save_state(state)
            
            if cycle % 10 == 0:
                next_signal_info = get_next_signal()
                send_status_report(cycle, time_str, elapsed, current_price, state, next_signal_info)
                print(f"📨 تقرير دوري #{cycle//10}")
            
            print(f"📊 {state['buy_count']} شراء | {len(state['open_positions'])} مفتوحة | "
                  f"ربح: {state['total_profit']:.6f}")
            
        except Exception as e:
            print(f"❌ خطأ Tick: {e}")
            if cycle % 10 == 0:
                send_telegram_message(f"⚠️ <b>خطأ في Tick #{cycle}:</b>\n{e}\n🕒 {time_str}")
        
        remaining = duration - (time.time() - start_time)
        if remaining > 0:
            sleep_time = min(CHECK_INTERVAL, remaining)
            print(f"💤 {sleep_time:.0f} ثانية...")
            time.sleep(sleep_time)
    
    # ==========================================
    # نهاية الدورة
    # ==========================================
    print(f"\n{'='*50}\n⏰ انتهت الـ 3 ساعات!\n{'='*50}")
    
    closing_usdt, closing_btc = get_balance(exchange)
    
    remaining_positions = len(state['open_positions'])
    
    if remaining_positions > 0:
        msg = (f"⏰ <b>انتهت الدورة — Positions متبقية</b>\n\n"
               f"📦 عدد الـ Positions المفتوحة: {remaining_positions}\n"
               f"⏳ <b>لم تُباع لأن السعر لم يصل للربح المطلوب</b>\n"
               f"💤 سيتم الاحتفاظ بها للدورة القادمة\n\n")
        
        for pos in state['open_positions']:
            min_sell = pos['price'] * 1.003
            msg += f"💰 شراء بـ {pos['price']:.2f}$ | بيع عند {min_sell:.2f}$\n"
        
        msg += f"\n🕒 {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}"
        send_telegram_message(msg)
    
    save_state(state)
    
    cl_usdt_str = f"{closing_usdt:.6f}" if closing_usdt is not None else "غير معروف"
    cl_btc_str = f"{closing_btc:.6f}" if closing_btc is not None else "غير معروف"
    
    final_msg = (
        f"✅ <b>انتهت الدورة (3 ساعات)</b>\n\n"
        f"💵 رصيد USDT الافتتاحي: {op_usdt_str}\n"
        f"💵 رصيد USDT الختامي: {cl_usdt_str}\n"
        f"📦 رصيد BTC الختامي: {cl_btc_str}\n"
        f"📦 Positions مفتوحة: {remaining_positions}\n\n"
        f"📊 <b>ملخص الأداء:</b>\n"
        f"🔢 عمليات شراء: {state['buy_count']}\n"
        f"💰 عمليات بيع ناجحة: {len([t for t in state['trades_history'] if t['type'] == 'sell_profit'])}\n"
        f"💰 إجمالي أرباح محققة: {state['total_profit']:.6f} USDT\n"
        f"💵 إجمالي منفق: {state['total_usdt_spent']:.2f} USDT\n\n"
        f"🕒 {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}\n"
        f"💤 إعادة التشغيل بعد ساعة."
    )
    send_telegram_message(final_msg)
    print(f"✅ انتهى | ربح: {state['total_profit']:.6f} | Positions متبقية: {remaining_positions}")

