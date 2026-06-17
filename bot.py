"""
Trading Bot - Telegram Debug Version
With clear diagnostics and forced notifications
"""

import asyncio
import aiohttp
import json
import os
import time
import logging
import sys
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import List, Dict, Optional, Callable, Any
from collections import deque
import uuid
import requests
import re

# ==========================================
# CONFIGURATION
# ==========================================

@dataclass
class Config:
    api_key: str = 'dmyc2X0llvZ1A1zGAy9wfkqJHqZC20Uv04iYwBmOrnBMLJlnH7SZOsPt4eYGYnoJ'
    secret: str = 'uVax1wfQo0Ns1XIhGgsW4j2yjgB9VPlQWYzWvt1sAeg640WpGRCSqFMPvVyNtu6S'
    telegram_token: str = '8777604170:AAGVQWj7KtRZWKjZQ0BuyIZCHJ3FCmFgQP4'
    telegram_chat_id: str = '6390985342'

    max_buys: int = 7
    max_total_usdt: float = 75.0
    trade_usdt_per_buy: float = 10.0
    min_btc_amount: float = 0.0001
    fee_rate: float = 0.001

    min_profit_usdt: float = 0.5
    min_profit_pct: float = 0.5
    profit_targets: List[float] = None

    cooldown_seconds: int = 300

    max_retries: int = 5
    base_retry_delay: float = 1.0
    max_retry_delay: float = 60.0
    check_interval: int = 3

    proxy_refresh_interval: int = 600
    proxy_max_count: int = 150

    schedule: List[Dict] = None

    def __post_init__(self):
        if self.profit_targets is None:
            self.profit_targets = [1.5, 3.0, 5.0, 8.0]

        if self.schedule is None:
            self.schedule = [
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
# TELEGRAM NOTIFIER - ENHANCED WITH DEBUG
# ==========================================

class TelegramNotifier:
    """نظام إشعارات تليجرام مع تشخيصات كاملة"""

    def __init__(self, config: Config):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self._sender_task: Optional[asyncio.Task] = None
        self._connected: bool = False
        self._messages_sent: int = 0
        self._messages_failed: int = 0

    async def __aenter__(self):
        """تهيئة الجلسة مع تشخيص"""
        logging.info("=" * 60)
        logging.info("تهيئة نظام إشعارات تليجرام")
        logging.info("=" * 60)

        # فحص الإعدادات
        if not self.config.telegram_token:
            logging.error("❌ TELEGRAM_TOKEN فارغ!")
            logging.error("   يرجى تعيين TELEGRAM_TOKEN في أسرار GitHub")
            self._connected = False
            return self

        if not self.config.telegram_chat_id:
            logging.error("❌ TELEGRAM_CHAT_ID فارغ!")
            logging.error("   يرجى تعيين TELEGRAM_CHAT_ID في أسرار GitHub")
            self._connected = False
            return self

        logging.info("✅ TELEGRAM_TOKEN: %s...%s (الطول: %d)" % (
            self.config.telegram_token[:8],
            self.config.telegram_token[-4:],
            len(self.config.telegram_token)
        ))
        logging.info("✅ TELEGRAM_CHAT_ID: %s" % self.config.telegram_chat_id)

        try:
            self.session = aiohttp.ClientSession()

            # اختبار الاتصال فوراً
            test_result = await self._test_connection()
            if test_result:
                logging.info("✅ اختبار الاتصال بتليجرام ناجح")
                self._connected = True
            else:
                logging.error("❌ اختبار الاتصال بتليجرام فاشل")
                self._connected = False

            # تشغيل مرسل الخلفية
            self._sender_task = asyncio.create_task(self._queue_sender())

        except Exception as e:
            logging.error("❌ فشل في تهيئة تليجرام: %s" % str(e))
            self._connected = False

        return self

    async def __aexit__(self, *args):
        if self._sender_task:
            self._sender_task.cancel()
            try:
                await self._sender_task
            except asyncio.CancelledError:
                pass
        if self.session:
            await self.session.close()

    async def _test_connection(self) -> bool:
        """اختبار الاتصال بـ Telegram API"""
        try:
            url = "https://api.telegram.org/bot%s/getMe" % self.config.telegram_token
            async with self.session.get(url, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("ok"):
                        bot_info = data.get("result", {})
                        logging.info("✅ Bot connected: @%s (ID: %s)" % (
                            bot_info.get("username", "unknown"),
                            bot_info.get("id", "unknown")
                        ))
                        return True
                    else:
                        logging.error("❌ خطأ في API تليجرام: %s" % data.get("description", "Unknown"))
                        return False
                else:
                    logging.error("❌ HTTP %d: %s" % (resp.status, await resp.text()))
                    return False
        except Exception as e:
            logging.error("❌ Connection test failed: %s" % str(e))
            return False

    async def _queue_sender(self):
        """مرسل الإشعارات في الخلفية"""
        logging.info("📡 بدأ مرسل الطابور")

        while True:
            try:
                message = await self.message_queue.get()

                if not self._connected:
                    logging.warning("⚠️ تليجرام غير متصل، تم حذف الرسالة")
                    self._messages_failed += 1
                    continue

                success = await self._send_raw(message)
                if success:
                    self._messages_sent += 1
                else:
                    self._messages_failed += 1

                await asyncio.sleep(0.1)  # Rate limit protection

            except asyncio.CancelledError:
                logging.info("📡 توقف مرسل الطابور")
                break
            except Exception as e:
                logging.error("خطأ في مرسل الطابور: %s" % str(e))
                self._messages_failed += 1

    async def _send_raw(self, message: str) -> bool:
        """إرسال رسالة خام - مع تسجيل كامل"""
        if not self.session:
            logging.error("❌ لا توجد جلسة متاحة")
            return False

        try:
            url = "https://api.telegram.org/bot%s/sendMessage" % self.config.telegram_token
            payload = {
                "chat_id": self.config.telegram_chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }

            logging.debug("إرسال رسالة إلى %s..." % self.config.telegram_chat_id)

            async with self.session.post(url, json=payload, timeout=15) as resp:
                response_text = await resp.text()

                if resp.status == 200:
                    data = json.loads(response_text)
                    if data.get("ok"):
                        logging.info("✅ تم إرسال الرسالة بنجاح (الإجمالي: %d)" % self._messages_sent)
                        return True
                    else:
                        logging.error("❌ خطأ في API تليجرام: %s" % data.get("description", "Unknown"))
                        return False
                else:
                    logging.error("❌ HTTP %d: %s" % (resp.status, response_text[:200]))
                    return False

        except asyncio.TimeoutError:
            logging.error("❌ انتهت مهلة إرسال تليجرام")
            return False
        except Exception as e:
            logging.error("❌ فشل إرسال تليجرام: %s" % str(e))
            return False

    async def send(self, message: str):
        """إضافة رسالة إلى الطابور"""
        if not self._connected:
            logging.warning("⚠️ لا يمكن الإرسال - تليجرام غير متصل")
            return

        await self.message_queue.put(message)
        logging.debug("📨 تم وضع الرسالة في الطابور (حجم الطابور: %d)" % self.message_queue.qsize())

    async def force_send(self, message: str) -> bool:
        """إرسال فوري بدون طابور (للتشخيص)"""
        if not self.session:
            logging.error("❌ No session")
            return False
        return await self._send_raw(message)

    # ============ NOTIFICATIONS ============

    async def notify_startup(self, proxy_info: str = "", mode: str = "LIVE"):
        """إشعار بدء التشغيل - مهم جداً"""
        if not self._connected:
            logging.error("❌ لا يمكن إرسال إشعار بدء التشغيل - غير متصل")
            return

        msg = (
            "🚀 <b>Bot Started! (%s MODE)</b>\n\n"
            "<b>Settings:</b>\n"
            "• Min Profit: $%.2f / %.1f%%\n"
            "• Profit Targets: %s\n"
            "• Cooldown: %d min\n"
            "• Check Interval: %d sec\n"
            "• Proxy: %s\n\n"
            "<b>Policy: NEVER sell at loss</b>\n"
            "<b>الوقت:</b> %s"
        ) % (
            mode,
            self.config.min_profit_usdt, self.config.min_profit_pct,
            ", ".join("%.1f%%" % t for t in self.config.profit_targets),
            self.config.cooldown_seconds // 60,
            self.config.check_interval,
            proxy_info or "None",
            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        )

        # إرسال فوري بدون طابور للتأكد
        success = await self.force_send(msg)
        if success:
            logging.info("✅ تم إرسال إشعار بدء التشغيل")
        else:
            logging.error("❌ فشل في إرسال إشعار بدء التشغيل")

    async def notify_buy_success(self, pos_id: str, buy_price: float, amount: float, 
                                  total_cost: float, reason: str):
        if not self._connected:
            return

        msg = (
            "🟢 <b>Buy Successful! #%s</b>\n\n"
            "<b>Price:</b> <code>%.2f</code> USDT\n"
            "<b>Amount:</b> <code>%.6f</code> BTC\n"
            "<b>Total Cost:</b> <code>%.4f</code> USDT\n"
            "<b>Reason:</b> %s\n"
            "<b>الوقت:</b> %s"
        ) % (
            pos_id, buy_price, amount, total_cost, reason,
            datetime.now(timezone.utc).strftime("%H:%M:%S")
        )
        await self.send(msg)

    async def notify_sell_success(self, pos_id: str, buy_price: float, sell_price: float,
                                   amount: float, net_profit: float, profit_pct: float,
                                   reason: str, total_portfolio_profit: float):
        if not self._connected:
            return

        emoji = "🚀🚀🚀" if profit_pct >= 5 else "🚀🚀" if profit_pct >= 3 else "🚀" if profit_pct >= 1 else "✅"

        msg = (
            "%s <b>Sell Successful! #%s</b>\n\n"
            "<b>Buy:</b> <code>%.2f</code> | <b>Sell:</b> <code>%.2f</code>\n"
            "<b>Amount:</b> <code>%.6f</code> BTC\n\n"
            "<b>Net Profit: +$%.4f (%.2f%%)</b>\n"
            "<b>Reason:</b> %s\n"
            "<b>Portfolio Total:</b> <code>$%.4f</code>\n"
            "<b>الوقت:</b> %s"
        ) % (
            emoji, pos_id, buy_price, sell_price, amount,
            net_profit, profit_pct, reason, total_portfolio_profit,
            datetime.now(timezone.utc).strftime("%H:%M:%S")
        )
        await self.send(msg)

    async def notify_error(self, error: str, context: str = ""):
        if not self._connected:
            logging.error("Telegram error (%s): %s" % (context, error))
            return

        msg = (
            "🚨 <b>Error!</b>\n\n"
            "<b>Context:</b> %s\n"
            "<b>Error:</b> <code>%s</code>\n"
            "<b>الوقت:</b> %s"
        ) % (
            context or "Unknown", error,
            datetime.now(timezone.utc).strftime("%H:%M:%S")
        )
        await self.send(msg)

    async def notify_proxy_refresh(self, total: int, working: int, best: str, response_time: float):
        if not self._connected:
            return

        msg = (
            "🔄 <b>Proxy Refresh</b>\n\n"
            "<b>Total:</b> %d | <b>Working:</b> %d\n"
            "<b>Best:</b> <code>%s</code>\n"
            "<b>Speed:</b> <code>%.2fs</code>\n"
            "<b>الوقت:</b> %s"
        ) % (
            total, working, best, response_time,
            datetime.now(timezone.utc).strftime("%H:%M:%S")
        )
        await self.send(msg)

    async def notify_test(self):
        """إشعار اختبار - يُرسل فوراً"""
        msg = (
            "✅ <b>Test Message</b>\n\n"
            "<b>Bot is running!</b>\n"
            "<b>Time:</b> %s\n\n"
            "إذا رأيت هذه الرسالة، فإن تليجرام يعمل بشكل صحيح."
        ) % datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        return await self.force_send(msg)

    def get_stats(self) -> Dict:
        return {
            "connected": self._connected,
            "sent": self._messages_sent,
            "failed": self._messages_failed,
            "queue_size": self.message_queue.qsize()
        }


# ==========================================
# PROXY MANAGER (Simplified)
# ==========================================

class ProxyManager:
    def __init__(self, max_proxies: int = 150):
        self.max_proxies = max_proxies
        self.working_proxies: List[Dict] = []
        self.best_proxy: Optional[str] = None
        self.last_refresh = 0

    def fetch_proxies_sync(self) -> List[str]:
        sources = [
            "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
        ]

        all_proxies = []
        for source in sources:
            try:
                resp = requests.get(source, timeout=15, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                if resp.status_code == 200:
                    pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}:[0-9]{2,5}\b'
                    matches = re.findall(pattern, resp.text)
                    for match in matches:
                        proxy = "http://%s" % match
                        if proxy not in all_proxies:
                            all_proxies.append(proxy)
            except Exception as e:
                logging.warning("Source failed: %s" % str(e))

        return list(dict.fromkeys(all_proxies))[:self.max_proxies]

    async def test_proxy(self, proxy: str) -> tuple[bool, float]:
        try:
            start = time.time()
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://testnet.binance.vision/api/v3/time",
                    proxy=proxy,
                    timeout=aiohttp.ClientTimeout(total=8),
                    ssl=False
                ) as resp:
                    elapsed = time.time() - start
                    if resp.status == 200:
                        return True, elapsed
        except:
            pass
        return False, float('inf')

    async def refresh_proxies(self) -> Optional[str]:
        logging.info("جلب البروكسيات...")
        proxy_list = self.fetch_proxies_sync()
        logging.info("تم جلب %d بروكسي" % len(proxy_list))

        if not proxy_list:
            return None

        # Test in batches
        working = []
        for i in range(0, len(proxy_list), 50):
            batch = proxy_list[i:i+50]
            tasks = [self.test_proxy(p) for p in batch]
            results = await asyncio.gather(*tasks)

            for proxy, (alive, response_time) in zip(batch, results):
                if alive:
                    working.append({"url": proxy, "time": response_time})

            logging.info("تم اختبار %d/%d، يعمل حتى الآن: %d" % (
                min(i+50, len(proxy_list)), len(proxy_list), len(working)
            ))

        if working:
            working.sort(key=lambda x: x["time"])
            self.working_proxies = working
            self.best_proxy = working[0]["url"]
            self.last_refresh = time.time()
            logging.info("أفضل بروكسي: %s (%.2fث)" % (self.best_proxy, working[0]["time"]))
            return self.best_proxy

        return None

    def get_proxy_dict(self) -> Optional[Dict]:
        if self.best_proxy:
            return {"http": self.best_proxy, "https": self.best_proxy}
        return None


# ==========================================
# POSITION
# ==========================================

class Position:
    def __init__(self, buy_price: float, amount: float, buy_fee: float, 
                 total_cost: float, reason: str, fee_rate: float):
        self.id = str(uuid.uuid4())[:8]
        self.buy_price = buy_price
        self.amount = amount
        self.buy_fee = buy_fee
        self.total_cost = total_cost
        self.reason = reason
        self.fee_rate = fee_rate
        self.buy_time = datetime.now(timezone.utc)

        self.status = "open"
        self.sell_price = 0.0
        self.sell_fee = 0.0
        self.gross_return = 0.0
        self.net_profit = 0.0
        self.profit_pct = 0.0
        self.sell_time = None
        self.sell_reason = ""
        self.highest_price = buy_price

    @property
    def is_open(self) -> bool:
        return self.status == "open"

    def calculate_net_profit(self, current_price: float) -> float:
        gross_sell = current_price * self.amount
        sell_fee = gross_sell * self.fee_rate
        net_return = gross_sell - sell_fee
        return net_return - self.total_cost

    def calculate_profit_pct(self, current_price: float) -> float:
        net_profit = self.calculate_net_profit(current_price)
        return (net_profit / self.total_cost) * 100 if self.total_cost > 0 else 0

    def should_sell(self, current_price: float, min_profit_usdt: float, 
                     min_profit_pct: float, profit_targets: List[float]) -> tuple[bool, str]:
        net_profit = self.calculate_net_profit(current_price)
        profit_pct = self.calculate_profit_pct(current_price)

        if net_profit <= 0:
            return False, "في انتظار الربح ($%.4f)" % net_profit

        if net_profit < min_profit_usdt:
            return False, "ربح صغير ($%.4f)" % net_profit

        if profit_pct < min_profit_pct:
            return False, "نسبة صغيرة (%.2f%%)" % profit_pct

        for target in sorted(profit_targets, reverse=True):
            if profit_pct >= target:
                return True, "هدف %.1f%% (+$%.4f)" % (target, net_profit)

        return True, "ربح (+$%.4f, %.2f%%)" % (net_profit, profit_pct)

    def execute_sell(self, sell_price: float) -> Dict:
        self.sell_price = sell_price
        self.gross_return = sell_price * self.amount
        self.sell_fee = self.gross_return * self.fee_rate
        self.net_profit = self.gross_return - self.sell_fee - self.total_cost
        self.profit_pct = (self.net_profit / self.total_cost) * 100
        self.status = "closed"
        self.sell_time = datetime.now(timezone.utc)

        return {
            "id": self.id,
            "buy_price": self.buy_price,
            "sell_price": sell_price,
            "amount": self.amount,
            "net_profit": self.net_profit,
            "profit_pct": self.profit_pct,
            "hold_hours": (self.sell_time - self.buy_time).total_seconds() / 3600
        }


# ==========================================
# POSITION MANAGER
# ==========================================

class PositionManager:
    def __init__(self, config: Config):
        self.config = config
        self.positions: Dict[str, Position] = {}
        self.open_positions: List[str] = []
        self.closed_positions: List[str] = []
        self.total_realized_profit: float = 0.0

    async def create_position(self, buy_price: float, amount: float, 
                             buy_fee: float, total_cost: float, reason: str) -> Position:
        pos = Position(buy_price, amount, buy_fee, total_cost, reason, self.config.fee_rate)
        self.positions[pos.id] = pos
        self.open_positions.append(pos.id)
        return pos

    async def check_all_positions(self, current_price: float) -> List[tuple]:
        ready = []
        for pos_id in self.open_positions[:]:
            pos = self.positions.get(pos_id)
            if not pos or not pos.is_open:
                continue
            pos.update_highest_price(current_price)
            should_sell, reason = pos.should_sell(
                current_price,
                self.config.min_profit_usdt,
                self.config.min_profit_pct,
                self.config.profit_targets
            )
            if should_sell:
                ready.append((pos, reason))
        return ready

    async def close_position(self, pos_id: str, sell_price: float, reason: str) -> Optional[Dict]:
        pos = self.positions.get(pos_id)
        if not pos or not pos.is_open:
            return None

        result = pos.execute_sell(sell_price)
        pos.sell_reason = reason
        self.open_positions.remove(pos_id)
        self.closed_positions.append(pos_id)
        self.total_realized_profit += pos.net_profit
        return result

    def get_open_count(self) -> int:
        return len(self.open_positions)

    def get_stats(self) -> Dict:
        return {
            "open_count": len(self.open_positions),
            "closed_count": len(self.closed_positions),
            "total_realized_profit": self.total_realized_profit
        }


# ==========================================
# PRICE ENGINE
# ==========================================

class PriceEngine:
    def __init__(self, proxy_manager: ProxyManager):
        self.proxy_manager = proxy_manager
        self.last_price = 0.0

    async def get_price(self) -> Dict:
        proxy_dict = self.proxy_manager.get_proxy_dict()

        # Try with proxy
        if proxy_dict:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "https://testnet.binance.vision/api/v3/ticker/price?symbol=BTCUSDT",
                        proxy=proxy_dict.get("http"),
                        timeout=aiohttp.ClientTimeout(total=10),
                        ssl=False
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            self.last_price = float(data.get("price", 0))
                            return {"last": self.last_price, "source": "binance_proxy"}
            except Exception as e:
                logging.warning("فشل جلب البروكسي: %s" % str(e))

        # Fallback: CoinGecko
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.last_price = data.get("bitcoin", {}).get("usd", 0)
                        return {"last": self.last_price, "source": "coingecko"}
        except Exception as e:
            logging.error("فشلت جميع مصادر السعر: %s" % str(e))
            raise


# ==========================================
# MAIN BOT
# ==========================================

class TradingBot:
    def __init__(self):
        self.config = Config()
        self.proxy_manager = ProxyManager(max_proxies=self.config.proxy_max_count)
        self.price_engine = PriceEngine(self.proxy_manager)
        self.positions = PositionManager(self.config)
        self.notifier = TelegramNotifier(self.config)
        self.running = False
        self.processed_signals = set()
        self.last_buy_time = 0
        self._cycle_count = 0
        self.start_time = 0
        self.max_runtime_hours = 6  # [TIME] عدد الساعات حتى التوقف التلقائي

    async def initialize(self):
        logging.info("=" * 60)
        logging.info("تهيئة البوت")
        logging.info("=" * 60)

        # Refresh proxies
        best_proxy = await self.proxy_manager.refresh_proxies()
        if best_proxy:
            logging.info("استخدام البروكسي: %s" % best_proxy)
        else:
            logging.warning("لا يوجد بروكسي، استخدام CoinGecko كبديل")

    async def check_buy(self, now: datetime) -> Optional[Position]:
        if self.positions.get_open_count() >= self.config.max_buys:
            return None

        if time.time() - self.last_buy_time < self.config.cooldown_seconds:
            return None

        time_str = now.strftime("%Y-%m-%d %H:%M")
        buy_reason = None

        for signal in self.config.schedule:
            if signal["time"] == time_str and signal["time"] not in self.processed_signals:
                if signal["type"] in ["نزول", "صعود ونزول"]:
                    buy_reason = "Signal: %s" % signal["type"]
                    self.processed_signals.add(signal["time"])
                    break

        if not buy_reason:
            return None

        try:
            price_data = await self.price_engine.get_price()
            current_price = price_data["last"]
        except Exception as e:
            logging.error("فشل في جلب السعر: %s" % str(e))
            return None

        raw_amount = self.config.trade_usdt_per_buy / current_price
        amount = max(raw_amount, self.config.min_btc_amount)

        buy_fee = (current_price * amount) * self.config.fee_rate
        total_cost = (current_price * amount) + buy_fee

        pos = await self.positions.create_position(
            current_price, amount, buy_fee, total_cost, buy_reason
        )

        self.last_buy_time = time.time()

        # Notify
        await self.notifier.notify_buy_success(
            pos.id, current_price, amount, total_cost, buy_reason
        )

        logging.info("شراء #%s: %.6f BTC @ %.2f" % (pos.id, amount, current_price))
        return pos

    async def check_sell(self):
        try:
            price_data = await self.price_engine.get_price()
            current_price = price_data["last"]
        except Exception as e:
            logging.error("فشل في جلب السعر: %s" % str(e))
            return

        ready = await self.positions.check_all_positions(current_price)

        for pos, reason in ready:
            try:
                result = await self.positions.close_position(pos.id, current_price, reason)
                if result:
                    await self.notifier.notify_sell_success(
                        pos.id, pos.buy_price, current_price, pos.amount,
                        pos.net_profit, pos.profit_pct, reason,
                        self.positions.total_realized_profit
                    )
                    logging.info("بيع #%s: +$%.4f (%.2f%%)" % (pos.id, pos.net_profit, pos.profit_pct))
            except Exception as e:
                logging.error("فشل البيع: %s" % str(e))

    async def run_cycle(self):
        # [TIME] فحص وقت التشغيل - إيقاف تلقائي بعد 6 ساعات
        elapsed_hours = (time.time() - self.start_time) / 3600
        if elapsed_hours >= self.max_runtime_hours:
            logging.info("[TIME] تم الوصول إلى الحد الأقصى للوقت (%.1f ساعة). إيقاف البوت..." % self.max_runtime_hours)
            await self.notifier.send("[STOP] <b>انتهى وقت التشغيل</b>\n\nتم تشغيل البوت لمدة %.1f ساعة.\nجاري الإيقاف الآن..." % elapsed_hours)
            self.running = False
            return

        now = datetime.now(timezone.utc)
        await self.check_sell()
        await self.check_buy(now)
        self._cycle_count += 1

    async def run(self):
        self.running = True
        self.start_time = time.time()  # [TIME] تسجيل وقت البدء
        stop_time = self.start_time + (self.max_runtime_hours * 3600)

        async with self.notifier:
            await self.initialize()

            # Send startup notification
            proxy_info = self.proxy_manager.best_proxy or "CoinGecko Fallback"
            await self.notifier.notify_startup(proxy_info, "LIVE")

            # [TIME] إشعار بوقت التوقف التلقائي
            stop_at = datetime.fromtimestamp(stop_time, timezone.utc).strftime("%H:%M:%S")
            await self.notifier.send("[TIME] <b>وقت التوقف التلقائي:</b> <code>%s</code> UTC (بعد %d ساعة)" % (stop_at, self.max_runtime_hours))

            # Send test message
            test_success = await self.notifier.notify_test()
            if test_success:
                logging.info("✅ تم إرسال رسالة الاختبار بنجاح")
            else:
                logging.error("❌ فشلت رسالة الاختبار")

            # Log Telegram stats
            stats = self.notifier.get_stats()
            logging.info("إحصائيات تليجرام: %s" % json.dumps(stats))

            while self.running:
                start = time.time()
                try:
                    await self.run_cycle()
                except Exception as e:
                    logging.error("خطأ في الدورة: %s" % str(e))
                    await self.notifier.notify_error(str(e), "Main cycle")

                elapsed = time.time() - start
                sleep_time = max(0, self.config.check_interval - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

    async def stop(self):
        self.running = False


# ==========================================
# ENTRY POINT
# ==========================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler("bot_debug.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Log environment variables (masked)
    token = os.getenv("TELEGRAM_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    logging.info("=" * 60)
    logging.info("فحص البيئة")
    logging.info("=" * 60)
    logging.info("TELEGRAM_TOKEN: %s (الطول: %d)" % ("SET" if token else "EMPTY", len(token)))
    logging.info("TELEGRAM_CHAT_ID: %s (الطول: %d)" % ("SET" if chat_id else "EMPTY", len(chat_id)))
    logging.info("=" * 60)

    bot = TradingBot()

    import signal
    def handle_signal(sig, frame):
        asyncio.create_task(bot.stop())

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logging.info("توقف بواسطة المستخدم")
    except Exception as e:
        logging.critical("خطأ فادح: %s" % str(e))
        raise
