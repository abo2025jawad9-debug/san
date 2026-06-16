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

# نسبة الربح الصافي المطلوبة (بعد الرسوم)
MIN_PROFIT_PERCENT = 0.003  # 0.3% ربح صافي

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
# 3. جلب الرسوم الفعلية من Binance
# ==========================================
def get_trading_fees(ex):
    """
    جلب الرسوم الفعلية للـ symbol من Binance API
    تعيد: (maker_fee, taker_fee, bnb_discount_active)
    """
    try:
        # جلب رسوم الـ trading fee للـ symbol
        fees = ex.fetchTradingFee('BTC/USDT')
        maker_fee = fees.get('maker', 0.001)  # افتراضي 0.1%
        taker_fee = fees.get('taker', 0.001)  # افتراضي 0.1%

        # التحقق من خصم BNB
        bal = ex.fetch_balance()
        bnb_discount = bal.get('info', {}).get('canTrade', False)

        # إذا كان خصم BNB مفعل، نطبق الخصم
        if bnb_discount:
            # خصم BNB = 25% على الرسوم
            maker_fee = maker_fee * 0.75
            taker_fee = taker_fee * 0.75

        return maker_fee, taker_fee, bnb_discount
    except Exception as e:
        print(f"⚠️ فشل جلب الرسوم من API، استخدام القيم الافتراضية: {e}")
        return 0.001, 0.001, False  # افتراضي 0.1%

def calculate_sell_multiplier(buy_taker_fee, sell_taker_fee):
    """
    حساب مضاعف سعر البيع المطلوب
    الرسوم الإجمالية = رسوم الشراء + رسوم البيع
    سعر البيع = سعر الشراء × (1 + رسوم الشراء + رسوم البيع + ربح صافي)
    """
    total_fees = buy_taker_fee + sell_taker_fee
    multiplier = 1 + total_fees + MIN_PROFIT_PERCENT
    return multiplier, total_fees

# ==========================================
# 4. حفظ واسترجاع الحالة
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
        'trades_history': [],
        'daily_low_price': None,
        'daily_low_time': None,
        'bought_at_daily_low': False,
        'last_fees_update': None,
        'cached_maker_fee': 0.001,
        'cached_taker_fee': 0.001,
        'bnb_discount_active': False
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
# 5. تنظيف الإشارات القديمة
# ==========================================
def clean_old_signals(state):
    now = datetime.now(timezone.utc)
    kept = []
    for sig_time_str in state['processed_signals']:
        try:
            sig_time = datetime.strptime(sig_time_str, '%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc)
            if sig_time.date() == now.date():
                kept.append(sig_time_str)
        except:
            pass
    state['processed_signals'] = kept
    return state

# ==========================================
# 6. بروكسيات
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
# 7. جلب الرصيد
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
# 8. جلب أدنى سعر لليوم
# ==========================================
def get_daily_low(ex):
    """جلب أدنى سعر لـ BTC/USDT في آخر 24 ساعة"""
    try:
        ohlcv = ex.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=24)
        if not ohlcv or len(ohlcv) == 0:
            return None, None

        daily_low = min([candle[3] for candle in ohlcv])
        daily_low_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')

        return daily_low, daily_low_time
    except Exception as e:
        print(f"❌ فشل جلب أدنى سعر يومي: {e}")
        return None, None

# ==========================================
# 9. جدول الإشارات
# ==========================================
schedule = [
    {"time": "2026-06-16 21:19", "type": "نزول"},
    {"time": "2026-06-16 22:19", "type": "نزول"},
    {"time": "2026-06-16 23:29", "type": "نزول"},
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
# 10. إيجاد أقرب موعد إشارة
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
# 11. البيع الذكي — يبيع فقط الـ position المربحة
# ==========================================
def check_sell(ex, current_price, time_str, state):
    """
    يفحص كل position على حدة ويبيع فقط التي أصبحت مربحة
    عند البيع: ينقص buy_count ويسمح بشراء جديد
    """
    sold_any = False
    positions_to_remove = []

    # جلب الرسوم الحالية
    maker_fee, taker_fee, bnb_discount = get_trading_fees(ex)
    sell_multiplier, total_fees = calculate_sell_multiplier(taker_fee, taker_fee)

    for idx, pos in enumerate(state['open_positions']):
        entry_price = pos['price']
        amount = pos['amount']
        position_id = pos.get('id', idx + 1)

        # استخدام الرسوم المحفوظة مع الـ position أو الرسوم الحالية
        pos_buy_fee = pos.get('buy_fee', taker_fee)
        pos_sell_fee = pos.get('sell_fee', taker_fee)
        pos_multiplier = pos.get('sell_multiplier', sell_multiplier)

        min_sell_price = entry_price * pos_multiplier

        if current_price >= min_sell_price:
            try:
                usdt_before, btc_before = get_balance(ex)
                print(f"💰 الرصيد قبل البيع pos#{position_id}: USDT={usdt_before}, BTC={btc_before}" if usdt_before else "❌ فشل جلب الرصيد")

                order = ex.create_market_sell_order('BTC/USDT', amount)
                time.sleep(3)

                usdt_after, btc_after = get_balance(ex)
                print(f"💰 الرصيد بعد البيع pos#{position_id}: USDT={usdt_after}, BTC={btc_after}" if usdt_after else "❌ فشل جلب الرصيد")

                if usdt_before is not None and usdt_after is not None:
                    actual_pnl = usdt_after - usdt_before
                else:
                    actual_pnl = (current_price - entry_price) * amount * (1 - pos_sell_fee)

                # التأكد أن الربح صافي (يغطي الرسوم الفعلية)
                min_profit_usdt = entry_price * amount * MIN_PROFIT_PERCENT
                total_fees_usdt = entry_price * amount * (pos_buy_fee + pos_sell_fee)
                required_pnl = min_profit_usdt + total_fees_usdt

                if actual_pnl >= required_pnl:
                    state['total_profit'] += actual_pnl
                    state['total_fees_paid'] += total_fees_usdt
                    state['buy_count'] -= 1  # ⭐ تحرير فرصة شراء

                    state['trades_history'].append({
                        'type': 'sell_profit',
                        'position_id': position_id,
                        'buy_price': entry_price,
                        'sell_price': current_price,
                        'amount': amount,
                        'actual_pnl': actual_pnl,
                        'total_fees': total_fees_usdt,
                        'buy_fee': pos_buy_fee,
                        'sell_fee': pos_sell_fee,
                        'usdt_before': usdt_before,
                        'usdt_after': usdt_after,
                        'time': time_str
                    })

                    usdt_bef_str = f"{usdt_before:.6f}" if usdt_before is not None else "غير معروف"
                    usdt_aft_str = f"{usdt_after:.6f}" if usdt_after is not None else "غير معروف"

                    msg = (f"🎉 <b>✅ بيع ناجح بربح صافٍ!</b>\n\n"
                           f"📦 <b>الـ Position:</b> #{position_id}\n"
                           f"💰 سعر الشراء: {entry_price:.2f} USDT\n"
                           f"💰 سعر البيع: {current_price:.2f} USDT\n"
                           f"📦 الكمية المباعة: {amount:.6f} BTC\n"
                           f"🎯 سعر البيع المطلوب: {min_sell_price:.2f} USDT\n\n"
                           f"📊 <b>تفاصيل الرسوم:</b>\n"
                           f"   رسوم الشراء: {pos_buy_fee*100:.4f}%\n"
                           f"   رسوم البيع: {pos_sell_fee*100:.4f}%\n"
                           f"   إجمالي الرسوم: {total_fees_usdt:.6f} USDT\n\n"
                           f"📊 <b>الربح الفعلي: 🟢 +{actual_pnl:.6f} USDT</b>\n"
                           f"📊 الربح الصافي المطلوب: {min_profit_usdt:.6f} USDT\n\n"
                           f"💵 رصيد USDT قبل: {usdt_bef_str}\n"
                           f"💵 رصيد USDT بعد: {usdt_aft_str}\n"
                           f"📈 الفرق: +{actual_pnl:.6f} USDT\n\n"
                           f"🔢 فرص الشراء المتبقية: {MAX_BUYS - state['buy_count']}/{MAX_BUYS}\n"
                           f"💰 إجمالي أرباح: {state['total_profit']:.6f} USDT\n"
                           f"📊 إجمالي رسوم مدفوعة: {state['total_fees_paid']:.6f} USDT\n"
                           f"🕒 {time_str}")
                    send_telegram_message(msg)
                    print(f"✅ بيع pos#{position_id} بربح: +{actual_pnl:.6f} USDT | فرص متبقية: {MAX_BUYS - state['buy_count']}")
                    positions_to_remove.append(pos)
                    sold_any = True
                else:
                    usdt_bef_str = f"{usdt_before:.6f}" if usdt_before is not None else "غير معروف"
                    usdt_aft_str = f"{usdt_after:.6f}" if usdt_after is not None else "غير معروف"

                    msg = (f"⏳ <b>لم يُباع pos#{position_id} — الربح لا يغطي الرسوم</b>\n\n"
                           f"💰 سعر الشراء: {entry_price:.2f} USDT\n"
                           f"💰 سعر البيع الحالي: {current_price:.2f} USDT\n"
                           f"📦 الكمية: {amount:.6f} BTC\n"
                           f"📉 <b>الربح الفعلي: 🔴 {actual_pnl:.6f} USDT</b>\n"
                           f"📊 الربح المطلوب: {required_pnl:.6f} USDT\n"
                           f"   (رسوم: {total_fees_usdt:.6f} + ربح صافي: {min_profit_usdt:.6f})\n"
                           f"💵 رصيد USDT قبل: {usdt_bef_str}\n"
                           f"💵 رصيد USDT بعد: {usdt_aft_str}\n\n"
                           f"⏳ <b>سيتم الانتظار حتى يرتفع السعر أكثر...</b>\n"
                           f"🎯 السعر المطلوب: {min_sell_price:.2f} USDT\n"
                           f"🕒 {time_str}")
                    send_telegram_message(msg)
                    print(f"⏳ لم يُباع pos#{position_id}: ربح {actual_pnl:.6f} < {required_pnl:.6f}")

            except Exception as e:
                print(f"❌ فشل بيع pos#{position_id}: {e}")
                send_telegram_message(f"❌ <b>فشل البيع pos#{position_id}:</b>\n{e}\n🕒 {time_str}")
        else:
            needed_rise = ((min_sell_price - current_price) / current_price) * 100
            print(f"⏳ pos#{position_id}: السعر {current_price:.2f} < الحد {min_sell_price:.2f} (يحتاج +{needed_rise:.2f}%)")

    for pos in positions_to_remove:
        state['open_positions'].remove(pos)

    return sold_any

# ==========================================
# 12. الشراء الأولي (من الجدول الزمني)
# ==========================================
checked_signals_current_run = set()

def check_buy_signal(ex, now, time_str, state):
    """الشراء الأولي بناءً على الجدول الزمني"""
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
                    return execute_buy(ex, current_price, signal["type"], signal["time"], time_str, state, buy_reason="إشارة جدول")
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
# 13. الشراء على أدنى سعر يومي
# ==========================================
def check_buy_daily_low(ex, current_price, time_str, state):
    """
    إذا وصل السعر لأدنى سعر في 24 ساعة → يشتري
    """
    if state['buy_count'] >= MAX_BUYS:
        return False

    daily_low, daily_low_time = get_daily_low(ex)
    if daily_low is None:
        return False

    state['daily_low_price'] = daily_low
    state['daily_low_time'] = daily_low_time

    price_diff_percent = abs(current_price - daily_low) / daily_low

    if price_diff_percent <= 0.005:
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        if state.get('bought_at_daily_low') == today:
            print(f"⏳ تم الشراء على أدنى سعر اليوم بالفعل")
            return False

        print(f"🎯 السعر الحالي {current_price:.2f} قريب من أدنى سعر يومي {daily_low:.2f}")

        result = execute_buy(ex, current_price, "نزول يومي قوي", f"daily_low_{today}", time_str, state, buy_reason="أدنى سعر يومي")
        if result:
            state['bought_at_daily_low'] = today
            return True

    return False

# ==========================================
# 14. تنفيذ الشراء
# ==========================================
def execute_buy(ex, current_price, signal_type, signal_time_str, time_str, state, buy_reason=""):
    """تنفيذ عملية شراء واحدة وإنشاء position جديدة مع تسجيل الرسوم الفعلية"""
    try:
        # جلب الرسوم الفعلية
        maker_fee, taker_fee, bnb_discount = get_trading_fees(ex)
        sell_multiplier, total_fees = calculate_sell_multiplier(taker_fee, taker_fee)

        usdt_before, btc_before = get_balance(ex)
        print(f"💰 الرصيد قبل الشراء: USDT={usdt_before}, BTC={btc_before}" if usdt_before else "❌ فشل جلب الرصيد")

        amount = TRADE_USDT_PER_BUY / current_price
        if amount < MIN_BTC_AMOUNT:
            amount = MIN_BTC_AMOUNT

        # التكلفة التقديرية مع الرسوم الفعلية
        estimated_cost = amount * current_price * (1 + taker_fee)

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
            actual_btc_gained = btc_after - btc_before if btc_before else amount * (1 - taker_fee)
            # حساب الرسوم الفعلية من الفرق
            estimated_without_fees = amount * current_price
            actual_fee = actual_spent - estimated_without_fees
            if actual_fee < 0:
                actual_fee = estimated_without_fees * taker_fee
        else:
            actual_spent = amount * current_price * (1 + taker_fee)
            actual_btc_gained = amount * (1 - taker_fee)
            actual_fee = amount * current_price * taker_fee

        state['buy_count'] += 1
        state['total_usdt_spent'] += actual_spent
        state['total_fees_paid'] += actual_fee

        # حفظ الرسوم في الـ state
        state['cached_maker_fee'] = maker_fee
        state['cached_taker_fee'] = taker_fee
        state['bnb_discount_active'] = bnb_discount
        state['last_fees_update'] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

        position_id = state['buy_count']
        min_sell = current_price * sell_multiplier

        new_position = {
            'id': position_id,
            'price': current_price,
            'amount': actual_btc_gained,
            'signal_time': signal_time_str,
            'actual_spent': actual_spent,
            'usdt_before_buy': usdt_before,
            'usdt_after_buy': usdt_after,
            'buy_reason': buy_reason,
            'min_sell_price': min_sell,
            'sell_multiplier': sell_multiplier,
            'buy_fee': taker_fee,
            'sell_fee': taker_fee,
            'total_fees': actual_fee,
            'created_at': time_str
        }

        state['open_positions'].append(new_position)

        if "daily_low" not in signal_time_str:
            state['processed_signals'].append(signal_time_str)

        state['trades_history'].append({
            'type': 'buy',
            'position_id': position_id,
            'price': current_price,
            'amount': actual_btc_gained,
            'actual_spent': actual_spent,
            'buy_fee': taker_fee,
            'sell_fee': taker_fee,
            'total_fees': actual_fee,
            'usdt_before': usdt_before,
            'usdt_after': usdt_after,
            'buy_reason': buy_reason,
            'time': time_str
        })

        usdt_bef_str = f"{usdt_before:.6f}" if usdt_before is not None else "غير معروف"
        usdt_aft_str = f"{usdt_after:.6f}" if usdt_after is not None else "غير معروف"
        bnb_status = "✅ مفعل" if bnb_discount else "❌ غير مفعل"

        msg = (f"🟢 <b>✅ شراء ناجح #{position_id}</b>\n\n"
               f"📋 <b>السبب:</b> {buy_reason}\n"
               f"⚠️ الإشارة: {signal_type}\n"
               f"💰 السعر: {current_price:.2f} USDT\n"
               f"📦 الكمية: {actual_btc_gained:.6f} BTC\n"
               f"💵 المبلغ المدفوع: {actual_spent:.6f} USDT\n"
               f"📊 الرسوم: {actual_fee:.6f} USDT ({taker_fee*100:.4f}%)\n\n"
               f"📊 <b>تفاصيل الرسوم:</b>\n"
               f"   Maker: {maker_fee*100:.4f}%\n"
               f"   Taker: {taker_fee*100:.4f}%\n"
               f"   خصم BNB: {bnb_status}\n\n"
               f"💵 رصيد USDT قبل: {usdt_bef_str}\n"
               f"💵 رصيد USDT بعد: {usdt_aft_str}\n\n"
               f"🎯 <b>سعر البيع المطلوب للربح الصافي: {min_sell:.2f} USDT</b>\n"
               f"📊 إجمالي منفق: {state['total_usdt_spent']:.2f}/{MAX_TOTAL_USDT} USDT\n"
               f"🔢 فرص الشراء المتبقية: {MAX_BUYS - state['buy_count']}/{MAX_BUYS}\n"
               f"📦 Positions مفتوحة: {len(state['open_positions'])}\n"
               f"🕒 {time_str}")
        send_telegram_message(msg)
        print(f"✅ شراء #{position_id} | سبب: {buy_reason} | مبلغ: {actual_spent:.6f} | رسوم: {actual_fee:.6f} | بيع عند: {min_sell:.2f}")
        return True

    except Exception as e:
        msg = f"❌ <b>خطأ في الشراء ({buy_reason}):</b>\n{e}\n🕒 {time_str}"
        send_telegram_message(msg)
        return False

# ==========================================
# 15. التقرير الدوري
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

    daily_low_str = f"{state.get('daily_low_price', 'غير معروف'):.2f}" if state.get('daily_low_price') else "غير معروف"

    # معلومات الرسوم
    maker_fee = state.get('cached_maker_fee', 0.001)
    taker_fee = state.get('cached_taker_fee', 0.001)
    bnb_status = "✅" if state.get('bnb_discount_active') else "❌"

    msg = (f"📊 <b>تقرير الدورة #{tick_num}</b>\n\n"
           f"🕒 الوقت: {time_str} | مضى: {elapsed_min:.0f} دقيقة\n"
           f"💰 سعر BTC: {current_price:.2f} USDT\n"
           f"📉 أدنى سعر يومي: {daily_low_str} USDT\n\n"
           f"📊 <b>الرسوم الحالية:</b>\n"
           f"   Maker: {maker_fee*100:.4f}% | Taker: {taker_fee*100:.4f}%\n"
           f"   خصم BNB: {bnb_status}\n\n"
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
           f"📊 إجمالي رسوم مدفوعة: {state['total_fees_paid']:.6f} USDT\n"
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
        for pos in state['open_positions']:
            min_sell = pos['min_sell_price']
            needed = ((min_sell - current_price) / current_price) * 100 if current_price < min_sell else 0
            status = "✅ مربح" if current_price >= min_sell else f"يحتاج +{needed:.2f}%"
            msg += (f"  #{pos['id']}: شراء {pos['price']:.2f}$ | حالي {current_price:.2f}$\n"
                   f"      🎯 بيع عند: {min_sell:.2f}$ | الحالة: {status}\n"
                   f"      📦 كمية: {pos['amount']:.6f} BTC | رسوم: {pos.get('buy_fee', 0)*100:.4f}%\n"
                   f"      📋 سبب: {pos.get('buy_reason', 'غير معروف')}\n")

    send_telegram_message(msg)

# ==========================================
# 16. التشغيل الرئيسي
# ==========================================
if __name__ == "__main__":
    global exchange
    exchange, valid_proxy = get_auto_proxy_exchange()
    if exchange is None:
        send_telegram_message("🚨 <b>فشل الاتصال بجميع البروكسيات.</b> تم إيقاف البوت.")
        exit(1)

    state = load_state()
    state = clean_old_signals(state)

    # جلب الرسوم عند البداية
    maker_fee, taker_fee, bnb_discount = get_trading_fees(exchange)
    state['cached_maker_fee'] = maker_fee
    state['cached_taker_fee'] = taker_fee
    state['bnb_discount_active'] = bnb_discount
    state['last_fees_update'] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    if state.get('bought_at_daily_low') != today:
        state['bought_at_daily_low'] = False

    start_time = time.time()
    duration = DURATION_MINUTES * 60

    opening_usdt, opening_btc = get_balance(exchange)

    next_time, next_type, next_diff = get_next_signal()

    op_usdt_str = f"{opening_usdt:.6f}" if opening_usdt is not None else "غير معروف"
    op_btc_str = f"{opening_btc:.6f}" if opening_btc is not None else "غير معروف"

    positions_info = ""
    if state['open_positions']:
        positions_info = "\n\n📦 <b>Positions مفتوحة سابقة:</b>\n"
        for pos in state['open_positions']:
            positions_info += f"  #{pos['id']}: شراء بـ {pos['price']:.2f}$ | بيع عند {pos['min_sell_price']:.2f}$ | رسوم: {pos.get('buy_fee', 0)*100:.4f}%\n"

    send_telegram_message(
        f"🚀 <b>بدأت دورة البوت (6 ساعات)</b>\n\n"
        f"💵 رصيد USDT: {op_usdt_str}\n"
        f"📦 رصيد BTC: {op_btc_str}\n"
        f"📊 Positions سابقة: {len(state['open_positions'])}\n"
        f"💵 منفق سابق: {state['total_usdt_spent']:.2f} USDT\n"
        f"💰 أرباح سابقة: {state['total_profit']:.6f} USDT\n"
        f"🔢 فرص شراء متاحة: {MAX_BUYS - state['buy_count']}/{MAX_BUYS}\n"
        f"⏰ أقرب إشارة: {next_time or 'لا يوجد'} ({next_type or ''})\n"
        f"\n📊 <b>الرسوم الحالية:</b>\n"
        f"   Maker: {maker_fee*100:.4f}%\n"
        f"   Taker: {taker_fee*100:.4f}%\n"
        f"   خصم BNB: {'✅ مفعل' if bnb_discount else '❌ غير مفعل'}\n"
        f"🕒 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
        f"{positions_info}"
    )

    print(f"🚀 بدء 6 ساعات | Positions: {len(state['open_positions'])} | فرص متبقية: {MAX_BUYS - state['buy_count']} | رسوم: {taker_fee*100:.4f}%")

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

            # 1. فحص البيع أولاً
            if state['open_positions']:
                check_sell(exchange, current_price, time_str, state)
                save_state(state)

            # 2. فحص الشراء من الجدول
            if state['buy_count'] < MAX_BUYS:
                if check_buy_signal(exchange, now, time_str, state):
                    save_state(state)

            # 3. فحص الشراء على أدنى سعر يومي
            if state['buy_count'] < MAX_BUYS:
                if check_buy_daily_low(exchange, current_price, time_str, state):
                    save_state(state)

            # 4. التقرير الدوري
            if cycle % 10 == 0:
                next_signal_info = get_next_signal()
                send_status_report(cycle, time_str, elapsed, current_price, state, next_signal_info)
                print(f"📨 تقرير دوري #{cycle//10}")

            print(f"📊 {state['buy_count']} شراء | {len(state['open_positions'])} مفتوحة | "
                  f"ربح: {state['total_profit']:.6f} | رسوم: {state['total_fees_paid']:.6f} | فرص متبقية: {MAX_BUYS - state['buy_count']}")

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
    print(f"\n{'='*50}\n⏰ انتهت الـ 6 ساعات!\n{'='*50}")

    closing_usdt, closing_btc = get_balance(exchange)

    remaining_positions = len(state['open_positions'])

    if remaining_positions > 0:
        msg = (f"⏰ <b>انتهت الدورة — Positions متبقية</b>\n\n"
               f"📦 عدد الـ Positions المفتوحة: {remaining_positions}\n"
               f"⏳ <b>لم تُباع لأن السعر لم يصل للربح المطلوب</b>\n"
               f"💤 سيتم الاحتفاظ بها للدورة القادمة\n\n")

        for pos in state['open_positions']:
            msg += f"💰 pos#{pos['id']}: شراء بـ {pos['price']:.2f}$ | بيع عند {pos['min_sell_price']:.2f}$ | كمية: {pos['amount']:.6f} BTC | رسوم: {pos.get('buy_fee', 0)*100:.4f}%\n"

        msg += f"\n🕒 {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}"
        send_telegram_message(msg)

    save_state(state)

    cl_usdt_str = f"{closing_usdt:.6f}" if closing_usdt is not None else "غير معروف"
    cl_btc_str = f"{closing_btc:.6f}" if closing_btc is not None else "غير معروف"

    final_msg = (
        f"✅ <b>انتهت الدورة (6 ساعات)</b>\n\n"
        f"💵 رصيد USDT الافتتاحي: {op_usdt_str}\n"
        f"💵 رصيد USDT الختامي: {cl_usdt_str}\n"
        f"📦 رصيد BTC الختامي: {cl_btc_str}\n"
        f"📦 Positions مفتوحة: {remaining_positions}\n"
        f"🔢 فرص شراء متاحة: {MAX_BUYS - state['buy_count']}/{MAX_BUYS}\n\n"
        f"📊 <b>ملخص الأداء:</b>\n"
        f"🔢 عمليات شراء: {state['buy_count']}\n"
        f"💰 عمليات بيع ناجحة: {len([t for t in state['trades_history'] if t['type'] == 'sell_profit'])}\n"
        f"💰 إجمالي أرباح محققة: {state['total_profit']:.6f} USDT\n"
        f"📊 إجمالي رسوم مدفوعة: {state['total_fees_paid']:.6f} USDT\n"
        f"💵 إجمالي منفق: {state['total_usdt_spent']:.2f} USDT\n\n"
        f"🕒 {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}\n"
        f"💤 إعادة التشغيل بعد ساعة."
    )
    send_telegram_message(final_msg)
    print(f"✅ انتهى | ربح: {state['total_profit']:.6f} | رسوم: {state['total_fees_paid']:.6f} | Positions متبقية: {remaining_positions} | فرص متبقية: {MAX_BUYS - state['buy_count']}")
