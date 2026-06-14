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
        'processed_signals': [],  # فقط الإشارات التي تم شراؤها بنجاح
        'total_profit': 0.0,
        'total_loss': 0.0,
        'trades_history': []
    }

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

# ==========================================
# 4. تنظيف الإشارات القديمة
# ==========================================
def clean_old_signals(state):
    """يمسح الإشارات التي مرّ تاريخها من processed_signals"""
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
# 6. جدول الإشارات
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
# 7. إيجاد أقرب موعد إشارة
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
# 8. البيع (مع التأكد من الربح + تقرير)
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
                state['total_profit'] += profit
                
                state['trades_history'].append({
                    'type': 'sell_profit',
                    'buy_price': entry_price,
                    'sell_price': current_price,
                    'amount': amount,
                    'profit': profit,
                    'time': time_str
                })
                
                msg = (f"🎉 <b>✅ بيع ناجح بربح!</b>\n\n"
                       f"💰 سعر الشراء: {entry_price:.2f} USDT\n"
                       f"💰 سعر البيع: {current_price:.2f} USDT\n"
                       f"📦 الكمية: {amount:.6f} BTC\n"
                       f"📊 <b>الربح: +{profit:.4f} USDT</b> 🟢\n"
                       f"💵 إجمالي الأرباح: {state['total_profit']:.4f} USDT\n"
                       f"🕒 {time_str}")
                send_telegram_message(msg)
                print(f"✅ بيع بربح: {profit:.4f} USDT")
                state['open_positions'].remove(pos)
                sold_any = True
            except Exception as e:
                print(f"❌ فشل بيع: {e}")
        else:
            loss = (entry_price - current_price) * amount
            print(f"⏳ Position: شراء {entry_price:.2f}$ | حالي {current_price:.2f}$ (خسارة محتملة: {loss:.4f} USDT)")
    return sold_any

# ==========================================
# 9. الشراء (المُصلح - لا يضيف إلى processed_signals إلا عند النجاح)
# ==========================================
# متغير مؤقت لمعرفة أي إشارات تم فحصها ورفضت (لا يُحفظ)
checked_signals_current_run = set()

def check_buy(ex, now, time_str, state):
    if state['buy_count'] >= MAX_BUYS:
        return False
    
    for signal in schedule:
        signal_time = datetime.strptime(signal["time"], '%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc)
        time_diff = abs((now - signal_time).total_seconds())
        
        # نافذة 5 دقائق
        if time_diff <= 300:
            # إذا تم شراؤها سابقاً، تخطى
            if signal["time"] in state['processed_signals']:
                continue
            
            try:
                ohlcv = ex.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=3)
                price_1h_ago = ohlcv[-2][4]
                ticker = ex.fetch_ticker('BTC/USDT')
                current_price = ticker['last']
                
                # إرسال تقرير فحص الإشارة مرة واحدة فقط لكل إشارة في هذه الدورة
                if signal["time"] not in checked_signals_current_run:
                    check_msg = (f"🔍 <b>فحص إشارة: {signal['time']}</b>\n"
                               f"⚠️ النوع: {signal['type']}\n"
                               f"📊 السعر قبل ساعة: {price_1h_ago:.2f} USDT\n"
                               f"💰 السعر الحالي: {current_price:.2f} USDT\n"
                               f"🕒 {time_str}")
                    send_telegram_message(check_msg)
                    checked_signals_current_run.add(signal["time"])
                
                # شرط الشراء: السعر قبل ساعة أعلى من الحالي (السعر نازل)
                if price_1h_ago > current_price:
                    amount = TRADE_USDT_PER_BUY / current_price
                    if amount < MIN_BTC_AMOUNT:
                        amount = MIN_BTC_AMOUNT
                    actual_usdt = amount * current_price
                    
                    if state['total_usdt_spent'] + actual_usdt > MAX_TOTAL_USDT:
                        msg = (f"⛔ <b>تم إلغاء الشراء</b>\n"
                              f"سيتجاوز الحد الإجمالي ({MAX_TOTAL_USDT} USDT)\n"
                              f"💵 المنفق: {state['total_usdt_spent']:.2f} USDT\n"
                              f"🕒 {time_str}")
                        send_telegram_message(msg)
                        return False  # لا نضيف إلى processed_signals - قد نحاول في الدورة القادمة
                    
                    ex.create_market_buy_order('BTC/USDT', amount)
                    state['buy_count'] += 1
                    state['total_usdt_spent'] += actual_usdt
                    state['open_positions'].append({
                        'price': current_price, 'amount': amount, 'signal_time': signal["time"]
                    })
                    
                    # ✅ نضيف إلى processed_signals فقط عند الشراء الناجح
                    state['processed_signals'].append(signal["time"])
                    
                    state['trades_history'].append({
                        'type': 'buy',
                        'price': current_price,
                        'amount': amount,
                        'usdt': actual_usdt,
                        'time': time_str
                    })
                    
                    msg = (f"🟢 <b>✅ شراء ناجح #{state['buy_count']}</b>\n\n"
                           f"⚠️ الإشارة: {signal['type']}\n"
                           f"💰 السعر الحالي: {current_price:.2f} USDT\n"
                           f"📊 السعر قبل ساعة: {price_1h_ago:.2f} USDT\n"
                           f"📦 الكمية: {amount:.6f} BTC\n"
                           f"💵 المبلغ: {actual_usdt:.2f} USDT\n"
                           f"📊 إجمالي منفق: {state['total_usdt_spent']:.2f}/{MAX_TOTAL_USDT} USDT\n"
                           f"🔢 المتبقي: {MAX_BUYS - state['buy_count']} عمليات\n"
                           f"🕒 {time_str}")
                    send_telegram_message(msg)
                    print(f"✅ شراء #{state['buy_count']} بسعر {current_price:.2f}$")
                    return True
                else:
                    # ❌ لا نضيف إلى processed_signals - سنعيد المحاولة في الـ Tick التالي
                    if signal["time"] not in checked_signals_current_run:
                        msg = (f"🚫 <b>شرط الشراء غير متحقق</b>\n"
                              f"السعر قبل ساعة ({price_1h_ago:.2f}) ليس أعلى من الحالي ({current_price:.2f})\n"
                              f"سيتم إعادة المحاولة في الفحص التالي...\n"
                              f"🕒 {time_str}")
                        send_telegram_message(msg)
                    print(f"🚫 شرط غير متحقق: {price_1h_ago:.2f} vs {current_price:.2f} - إعادة المحاولة لاحقاً")
                    return False
                    
            except Exception as e:
                msg = f"❌ <b>خطأ في معالجة إشارة {signal['time']}:</b>\n{e}\n🕒 {time_str}"
                send_telegram_message(msg)
                return False
    return False

# ==========================================
# 10. التقرير الدوري (كل 10 دقائق)
# ==========================================
def send_status_report(tick_num, time_str, elapsed_min, current_price, state, next_signal_info):
    next_time, next_type, next_diff = next_signal_info
    
    open_value = 0
    unrealized_pnl = 0
    for pos in state['open_positions']:
        open_value += pos['amount'] * current_price
        unrealized_pnl += (current_price - pos['price']) * pos['amount']
    
    pnl_emoji = "🟢" if unrealized_pnl >= 0 else "🔴"
    pnl_text = f"+{unrealized_pnl:.4f}" if unrealized_pnl >= 0 else f"{unrealized_pnl:.4f}"
    
    msg = (f"📊 <b>تقرير الدورة #{tick_num}</b>\n\n"
           f"🕒 الوقت: {time_str} | مضى: {elapsed_min:.0f} دقيقة\n"
           f"💰 سعر BTC: {current_price:.2f} USDT\n\n"
           f"📈 <b>الحالة:</b>\n"
           f"🔢 عمليات شراء: {state['buy_count']}/{MAX_BUYS}\n"
           f"📦 Positions مفتوحة: {len(state['open_positions'])}\n"
           f"💵 قيمة المفتوحة: {open_value:.2f} USDT\n"
           f"📊 ربح/خسارة غير محقق: {pnl_emoji} {pnl_text} USDT\n"
           f"💰 إجمالي أرباح محققة: {state['total_profit']:.4f} USDT\n"
           f"📉 إجمالي خسائر: {state['total_loss']:.4f} USDT\n"
           f"💵 إجمالي منفق: {state['total_usdt_spent']:.2f}/{MAX_TOTAL_USDT} USDT\n\n")
    
    if next_time:
        msg += (f"⏰ <b>أقرب إشارة قادمة:</b>\n"
               f"📅 {next_time}\n"
               f"⚠️ النوع: {next_type}\n"
               f"⏳ بعد: {next_diff}\n\n")
    else:
        msg += "⏰ لا توجد إشارات مستقبلية في الجدول.\n\n"
    
    if state['open_positions']:
        msg += "📋 <b>Positions المفتوحة:</b>\n"
        for i, pos in enumerate(state['open_positions'], 1):
            current_val = pos['amount'] * current_price
            pnl = (current_price - pos['price']) * pos['amount']
            pnl_em = "🟢" if pnl >= 0 else "🔴"
            msg += (f"  #{i}: شراء {pos['price']:.2f}$ | حالي {current_price:.2f}$ | "
                   f"{pnl_em} {pnl:.4f} USDT\n")
    
    send_telegram_message(msg)

# ==========================================
# 11. التشغيل الرئيسي (3 ساعات)
# ==========================================
if __name__ == "__main__":
    exchange, valid_proxy = get_auto_proxy_exchange()
    if exchange is None:
        send_telegram_message("🚨 <b>فشل الاتصال بجميع البروكسيات.</b> تم إيقاف البوت.")
        exit(1)
    
    state = load_state()
    
    # ✅ تنظيف الإشارات القديمة (التي مرّ تاريخها) من processed_signals
    state = clean_old_signals(state)
    
    start_time = time.time()
    duration = DURATION_MINUTES * 60
    
    # إشعار البدء
    next_time, next_type, next_diff = get_next_signal()
    send_telegram_message(
        f"🚀 <b>بدأت دورة البوت (3 ساعات)</b>\n\n"
        f"📊 Positions سابقة: {len(state['open_positions'])}\n"
        f"💵 منفق سابق: {state['total_usdt_spent']:.2f} USDT\n"
        f"💰 أرباح سابقة: {state['total_profit']:.4f} USDT\n"
        f"⏰ أقرب إشارة: {next_time or 'لا يوجد'} ({next_type or ''})\n"
        f"🕒 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )
    
    print(f"🚀 بدء 3 ساعات | Positions: {len(state['open_positions'])} | processed: {state['processed_signals']}")
    
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
            
            # 3. التقرير الدوري كل 10 دقائق
            if cycle % 10 == 0:
                next_signal_info = get_next_signal()
                send_status_report(cycle, time_str, elapsed, current_price, state, next_signal_info)
                print(f"📨 تم إرسال التقرير الدوري #{cycle//10}")
            
            print(f"📊 {state['buy_count']} شراء | {len(state['open_positions'])} مفتوحة | "
                  f"ربح: {state['total_profit']:.4f} | منفق: {state['total_usdt_spent']:.2f}")
            
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
    
    if state['open_positions']:
        try:
            ticker = exchange.fetch_ticker('BTC/USDT')
            current_price = ticker['last']
            for pos in state['open_positions'][:]:
                if current_price > pos['price']:
                    exchange.create_market_sell_order('BTC/USDT', pos['amount'])
                    profit = (current_price - pos['price']) * pos['amount']
                    state['total_profit'] += profit
                    state['trades_history'].append({
                        'type': 'sell_final', 'buy_price': pos['price'],
                        'sell_price': current_price, 'amount': pos['amount'],
                        'profit': profit, 'time': time_str
                    })
                    send_telegram_message(f"⏰ <b>بيع نهائي</b> | ربح: {profit:.4f} USDT")
                    state['open_positions'].remove(pos)
                else:
                    loss = (pos['price'] - current_price) * pos['amount']
                    send_telegram_message(
                        f"⚠️ <b>Position باقٍ مفتوح</b>\n"
                        f"شراء: {pos['price']:.2f}$ | حالي: {current_price:.2f}$\n"
                        f"خسارة محتملة: {loss:.4f} USDT\n"
                        f"سيتم متابعته في الدورة القادمة."
                    )
        except Exception as e:
            print(f"❌ خطأ بيع نهائي: {e}")
    
    save_state(state)
    
    total_trades = len([t for t in state['trades_history'] if t['type'] in ('sell_profit', 'sell_final')])
    net_pnl = state['total_profit'] - state['total_loss']
    net_emoji = "🟢" if net_pnl >= 0 else "🔴"
    
    final_msg = (
        f"✅ <b>انتهت الدورة (3 ساعات)</b>\n\n"
        f"📊 <b>ملخص الأداء:</b>\n"
        f"🔢 عمليات شراء: {state['buy_count']}\n"
        f"💰 عمليات بيع ناجحة: {total_trades}\n"
        f"📦 Positions مفتوحة: {len(state['open_positions'])}\n"
        f"💵 إجمالي منفق: {state['total_usdt_spent']:.2f} USDT\n"
        f"📊 إجمالي أرباح: {state['total_profit']:.4f} USDT\n"
        f"📉 إجمالي خسائر: {state['total_loss']:.4f} USDT\n"
        f"{net_emoji} <b>صافي الربح/الخسارة: {net_pnl:.4f} USDT</b>\n\n"
        f"🕒 {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}\n"
        f"💤 إعادة التشغيل بعد ساعة."
    )
    send_telegram_message(final_msg)
    print(f"✅ انتهى | ربح: {state['total_profit']:.4f} | خسارة: {state['total_loss']:.4f} | صافي: {net_pnl:.4f}")

