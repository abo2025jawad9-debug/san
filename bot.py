import ccxt
from datetime import datetime, timezone

api_key = 'dmyc2X0llvZ1A1zGAy9wfkqJHqZC20Uv04iYwBmOrnBMLJlnH7SZOsPt4eYGYnoJ'.strip()
secret = 'uVax1wfQo0Ns1XIhGgsW4j2yjgB9VPlQWYzWvt1sAeg640WpGRCSqFMPvVyNtu6S'.strip()

ex = ccxt.binance({
    'apiKey': api_key, 'secret': secret, 'enableRateLimit': True,
    'options': {'defaultType': 'spot'},
    'urls': {'api': {'public': 'https://testnet.binance.vision/api/v3', 'private': 'https://testnet.binance.vision/api/v3'}}
})
ex.set_sandbox_mode(True)

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

def check_and_trade():
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

if __name__ == "__main__":
    check_and_trade()
