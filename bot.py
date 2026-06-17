"""
Crypto Trading Bot - Advanced Proxy System
Fetches 150+ proxies, tests all, picks the fastest
"""

import asyncio
import aiohttp
import aiohttp.client_exceptions
import json
import os
import time
import logging
import concurrent.futures
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any, Tuple
from collections import deque
import uuid
import requests
import socket
import ssl

# ==========================================
# ADVANCED PROXY MANAGER - 150+ PROXIES
# ==========================================

@dataclass
class ProxyResult:
    """نتيجة اختبار بروكسي"""
    url: str
    alive: bool = False
    response_time: float = float('inf')
    location: str = "Unknown"
    error: str = ""
    score: float = 0.0  # كلما زاد = أفضل

class AdvancedProxyManager:
    """
    مدير بروكسي متقدم:
    1. يجلب 150+ بروكسي من مصادر متعددة
    2. يختبر كل بروكسي (السرعة + الاتصال)
    3. يختار الأفضل تلقائياً
    4. يعيد الاختبار دورياً
    """

    PROXY_SOURCES = [
        # المصدر 1: ProxyScrape
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
        # المصدر 2: TheSpeedX
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        # المصدر 3: clarketm
        "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
        # المصدر 4: proxy-list.download
        "https://www.proxy-list.download/api/v1/get?type=http",
        # المصدر 5: free-proxy-list
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
        # المصدر 6: additional
        "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt",
        # المصدر 7: more proxies
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
        # المصدر 8: ssl proxies
        "https://www.sslproxies.org/",
    ]

    TEST_URLS = [
        "https://testnet.binance.vision/api/v3/ping",
        "https://api.binance.com/api/v3/ping",
        "https://api.coingecko.com/api/v3/ping",
    ]

    def __init__(self, max_proxies: int = 150):
        self.max_proxies = max_proxies
        self.proxy_list: List[str] = []
        self.working_proxies: List[ProxyResult] = []
        self.best_proxy: Optional[str] = None
        self.best_result: Optional[ProxyResult] = None
        self.last_refresh = 0
        self._lock = asyncio.Lock()

    def fetch_proxies_sync(self) -> List[str]:
        """جلب البروكسيات بشكل متزامن (للتشغيل في thread منفصل)"""
        all_proxies = []

        for source in self.PROXY_SOURCES:
            try:
                resp = requests.get(source, timeout=15, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                if resp.status_code == 200:
                    text = resp.text
                    # استخراج IP:Port من النص
                    import re
                    # نمط IP:Port
                    pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}:[0-9]{2,5}\b'
                    matches = re.findall(pattern, text)

                    for match in matches:
                        proxy_url = "http://%s" % match
                        if proxy_url not in all_proxies:
                            all_proxies.append(proxy_url)

                    logging.info("Source %s: fetched %d proxies" % (source[:50], len(matches)))
            except Exception as e:
                logging.warning("Failed source %s: %s" % (source[:50], str(e)))

        # إزالة التكرار والحد من العدد
        unique_proxies = list(dict.fromkeys(all_proxies))  # يحافظ على الترتيب
        limited = unique_proxies[:self.max_proxies]

        logging.info("Total unique proxies fetched: %d (limited to %d)" % (len(unique_proxies), len(limited)))
        return limited

    async def test_single_proxy(self, proxy_url: str, session: aiohttp.ClientSession) -> ProxyResult:
        """اختبار بروكسي واحد"""
        result = ProxyResult(url=proxy_url)
        start_time = time.time()

        try:
            # اختبار Binance Testnet
            test_url = "https://testnet.binance.vision/api/v3/time"
            timeout = aiohttp.ClientTimeout(total=8)

            async with session.get(
                test_url, 
                proxy=proxy_url,
                timeout=timeout,
                ssl=False  # بعض البروكسيات لا تدعم SSL الكامل
            ) as resp:
                elapsed = time.time() - start_time

                if resp.status == 200:
                    data = await resp.text()
                    if 'serverTime' in data or len(data) > 0:
                        result.alive = True
                        result.response_time = elapsed
                        # حساب الدرجة: كلما زادت = أفضل
                        # السرعة أهم عامل
                        result.score = 1000 / (elapsed + 0.1)
                        logging.debug("Proxy %s: %.2fs (score: %.1f)" % (proxy_url, elapsed, result.score))
                else:
                    result.error = "HTTP %d" % resp.status

        except asyncio.TimeoutError:
            result.error = "Timeout"
        except aiohttp.client_exceptions.ClientProxyConnectionError:
            result.error = "Proxy connection failed"
        except aiohttp.client_exceptions.ClientHttpProxyError:
            result.error = "Proxy HTTP error"
        except ssl.SSLError:
            result.error = "SSL error"
        except Exception as e:
            result.error = str(e)[:50]

        return result

    async def test_all_proxies(self, proxy_list: List[str]) -> List[ProxyResult]:
        """اختبار كل البروكسيات بشكل متوازي"""
        logging.info("Testing %d proxies..." % len(proxy_list))

        # إنشاء session واحد لكل الاختبارات
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=10, ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            # إنشاء جميع المهام
            tasks = [self.test_single_proxy(proxy, session) for proxy in proxy_list]

            # تنفيذ بشكل متوازي مع حد للعدد المتزامن
            semaphore = asyncio.Semaphore(50)  # 50 اختبار متزامن كحد أقصى

            async def bounded_test(task):
                async with semaphore:
                    return await task

            bounded_tasks = [bounded_test(t) for t in tasks]
            results = await asyncio.gather(*bounded_tasks, return_exceptions=True)

        # معالجة النتائج
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logging.debug("Proxy %s: Exception - %s" % (proxy_list[i], str(result)))
            elif isinstance(result, ProxyResult):
                valid_results.append(result)

        # تصفية العاملة وترتيبها
        working = [r for r in valid_results if r.alive]
        working.sort(key=lambda x: x.score, reverse=True)  # الأعلى درجة أولاً

        logging.info("Working proxies: %d/%d" % (len(working), len(proxy_list)))
        if working:
            logging.info("Best proxy: %s (%.2fs)" % (working[0].url, working[0].response_time))

        return working

    async def refresh_proxies(self) -> Optional[str]:
        """تحديث قائمة البروكسيات واختيار الأفضل"""
        async with self._lock:
            logging.info("=" * 60)
            logging.info("REFRESHING PROXY LIST")
            logging.info("=" * 60)

            # 1. جلب البروكسيات (في thread منفصل لأن requests متزامن)
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                proxy_list = await loop.run_in_executor(pool, self.fetch_proxies_sync)

            if not proxy_list:
                logging.error("No proxies fetched!")
                return None

            # 2. اختبار كل البروكسيات
            self.working_proxies = await self.test_all_proxies(proxy_list)

            # 3. اختيار الأفضل
            if self.working_proxies:
                self.best_result = self.working_proxies[0]
                self.best_proxy = self.best_result.url
                self.last_refresh = time.time()

                logging.info("=" * 60)
                logging.info("BEST PROXY: %s" % self.best_proxy)
                logging.info("Response time: %.2fs | Score: %.1f" % (self.best_result.response_time, self.best_result.score))
                logging.info("=" * 60)

                return self.best_proxy
            else:
                logging.error("No working proxies found!")
                self.best_proxy = None
                self.best_result = None
                return None

    def get_proxy_dict(self) -> Optional[Dict[str, str]]:
        """الحصول على قاموس البروكسي"""
        if self.best_proxy:
            return {
                "http": self.best_proxy,
                "https": self.best_proxy
            }
        return None

    async def get_next_proxy(self) -> Optional[str]:
        """الحصول على البروكسي التالي في القائمة (للتدوير)"""
        async with self._lock:
            if not self.working_proxies:
                return None

            # إزالة البروكسي الحالي من المقدمة وإعادة إضافته للنهاية
            if len(self.working_proxies) > 1:
                current = self.working_proxies.pop(0)
                self.working_proxies.append(current)
                self.best_proxy = self.working_proxies[0].url
                self.best_result = self.working_proxies[0]
                return self.best_proxy

            return self.best_proxy

    async def mark_proxy_failed(self, proxy_url: str):
        """وضع علامة فشل على بروكسي"""
        async with self._lock:
            self.working_proxies = [p for p in self.working_proxies if p.url != proxy_url]
            if self.working_proxies:
                self.best_proxy = self.working_proxies[0].url
                self.best_result = self.working_proxies[0]
            else:
                self.best_proxy = None
                self.best_result = None

            logging.warning("Proxy %s marked as failed. Remaining: %d" % (proxy_url, len(self.working_proxies)))


# ==========================================
# CONFIGURATION
# ==========================================

@dataclass
class Config:
    api_key: str = os.getenv("BINANCE_API_KEY", "")
    secret: str = os.getenv("BINANCE_SECRET", "")
    telegram_token: str = os.getenv("TELEGRAM_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")

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

    # Proxy settings
    proxy_refresh_interval: int = 600  # تحديث البروكسي كل 10 دقائق
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
# INDEPENDENT POSITION
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

    def update_highest_price(self, current_price: float):
        if current_price > self.highest_price:
            self.highest_price = current_price
            return True
        return False

    def should_sell(self, current_price: float, min_profit_usdt: float, 
                     min_profit_pct: float, profit_targets: List[float]) -> tuple[bool, str]:
        net_profit = self.calculate_net_profit(current_price)
        profit_pct = self.calculate_profit_pct(current_price)

        if net_profit <= 0:
            return False, "Waiting for profit (currently: $%.4f)" % net_profit

        if net_profit < min_profit_usdt:
            return False, "Small profit ($%.4f < $%.2f)" % (net_profit, min_profit_usdt)

        if profit_pct < min_profit_pct:
            return False, "Small %% (%.2f%% < %.2f%%)" % (profit_pct, min_profit_pct)

        for target in sorted(profit_targets, reverse=True):
            if profit_pct >= target:
                return True, "Target %.1f%% (+$%.4f)" % (target, net_profit)

        return True, "Profit (+$%.4f, %.2f%%)" % (net_profit, profit_pct)

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
            "total_cost": self.total_cost,
            "gross_return": self.gross_return,
            "sell_fee": self.sell_fee,
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
        self._lock = asyncio.Lock()

    async def create_position(self, buy_price: float, amount: float, 
                             buy_fee: float, total_cost: float, reason: str) -> Position:
        pos = Position(buy_price, amount, buy_fee, total_cost, reason, self.config.fee_rate)
        async with self._lock:
            self.positions[pos.id] = pos
            self.open_positions.append(pos.id)
        return pos

    async def check_all_positions(self, current_price: float) -> List[tuple]:
        ready_to_sell = []
        async with self._lock:
            open_ids = self.open_positions.copy()

        for pos_id in open_ids:
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
                ready_to_sell.append((pos, reason))
        return ready_to_sell

    async def close_position(self, pos_id: str, sell_price: float, reason: str) -> Optional[Dict]:
        pos = self.positions.get(pos_id)
        if not pos or not pos.is_open:
            return None

        result = pos.execute_sell(sell_price)
        pos.sell_reason = reason

        async with self._lock:
            if pos_id in self.open_positions:
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
            "total_realized_profit": self.total_realized_profit,
            "total_positions": len(self.positions)
        }

    def get_open_positions_details(self, current_price: float) -> List[Dict]:
        details = []
        for pos_id in self.open_positions:
            pos = self.positions.get(pos_id)
            if pos:
                net_pnl = pos.calculate_net_profit(current_price)
                pct = pos.calculate_profit_pct(current_price)
                details.append({
                    "id": pos.id,
                    "buy_price": pos.buy_price,
                    "current_pnl": net_pnl,
                    "current_pct": pct,
                    "highest": pos.highest_price,
                    "age_hours": (datetime.now(timezone.utc) - pos.buy_time).total_seconds() / 3600
                })
        return details


# ==========================================
# TELEGRAM NOTIFIER
# ==========================================

class TelegramNotifier:
    def __init__(self, config: Config):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self._sender_task: Optional[asyncio.Task] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        self._sender_task = asyncio.create_task(self._queue_sender())
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

    async def _queue_sender(self):
        while True:
            try:
                message = await self.message_queue.get()
                await self._send_raw(message)
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error("Queue sender error: %s" % str(e))

    async def _send_raw(self, message: str):
        if not self.config.telegram_token or not self.config.telegram_chat_id:
            return
        try:
            url = "https://api.telegram.org/bot%s/sendMessage" % self.config.telegram_token
            payload = {
                "chat_id": self.config.telegram_chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            async with self.session.post(url, json=payload, timeout=10) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logging.warning("Telegram API error %d: %s" % (resp.status, text))
        except Exception as e:
            logging.warning("Telegram send failed: %s" % str(e))

    async def send(self, message: str):
        await self.message_queue.put(message)

    async def notify_buy_success(self, pos: Position, order_info: Dict = None):
        msg = (
            "🟢 <b>Buy Successful!</b>\n\n"
            "<b>ID:</b> <code>#%s</code>\n"
            "<b>Buy Price:</b> <code>%.2f</code> USDT\n"
            "<b>Amount:</b> <code>%.6f</code> BTC\n"
            "<b>Total Cost:</b> <code>%.4f</code> USDT\n\n"
            "<b>Reason:</b> %s\n"
            "<b>Time:</b> %s\n\n"
            "<b>Policy:</b> Sell ONLY at profit"
        ) % (
            pos.id, pos.buy_price, pos.amount, pos.total_cost,
            pos.reason, pos.buy_time.strftime("%Y-%m-%d %H:%M:%S")
        )
        await self.send(msg)

    async def notify_buy_failed(self, error: str, attempted_price: float = 0, attempted_amount: float = 0):
        msg = (
            "🔴 <b>Buy Failed!</b>\n\n"
            "<b>Error:</b> <code>%s</code>\n"
            "<b>Target Price:</b> <code>%.2f</code> USDT\n"
            "<b>Target Amount:</b> <code>%.6f</code> BTC\n\n"
            "<b>Time:</b> %s\n\n"
            "Retrying automatically..."
        ) % (
            error, attempted_price, attempted_amount,
            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        )
        await self.send(msg)

    async def notify_sell_success(self, pos: Position, result: Dict, reason: str, 
                                   total_portfolio_profit: float):
        if pos.profit_pct >= 5:
            emoji = "🚀🚀🚀"
        elif pos.profit_pct >= 3:
            emoji = "🚀🚀"
        elif pos.profit_pct >= 1:
            emoji = "🚀"
        else:
            emoji = "✅"

        bar_length = min(int(pos.profit_pct), 20)
        profit_bar = "█" * bar_length + "░" * (20 - bar_length)

        msg = (
            "%s <b>Sell Successful! #%s</b>\n\n"
            "<b>Buy Price:</b> <code>%.2f</code> USDT\n"
            "<b>Sell Price:</b> <code>%.2f</code> USDT\n"
            "<b>Amount:</b> <code>%.6f</code> BTC\n\n"
            "<b>Profit Details:</b>\n"
            "├ <b>Gross:</b> <code>%.4f</code> USDT\n"
            "├ <b>Sell Fee:</b> <code>%.4f</code> USDT\n"
            "├ <b>Buy Cost:</b> <code>%.4f</code> USDT\n"
            "└ <b>Net Profit:</b> <code>+$%.4f</code> USDT\n\n"
            "<b>Profit: %.2f%%</b>\n"
            "%s\n\n"
            "<b>Reason:</b> %s\n"
            "<b>Hold Time:</b> %.1f hours\n"
            "<b>Time:</b> %s\n\n"
            "<b>Total Portfolio Profit:</b> <code>$%.4f</code> USDT"
        ) % (
            emoji, pos.id,
            pos.buy_price, pos.sell_price, pos.amount,
            pos.gross_return, pos.sell_fee, pos.total_cost, pos.net_profit,
            pos.profit_pct, profit_bar,
            reason, result["hold_hours"],
            pos.sell_time.strftime("%Y-%m-%d %H:%M:%S"),
            total_portfolio_profit
        )
        await self.send(msg)

    async def notify_sell_failed(self, pos_id: str, error: str, current_price: float):
        msg = (
            "🔴 <b>Sell Failed! #%s</b>\n\n"
            "<b>Error:</b> <code>%s</code>\n"
            "<b>Current Price:</b> <code>%.2f</code> USDT\n\n"
            "<b>Time:</b> %s\n\n"
            "Retrying automatically..."
        ) % (
            pos_id, error, current_price,
            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        )
        await self.send(msg)

    async def notify_price_update(self, current_price: float, open_positions: List[Dict], 
                                   total_realized: float):
        if not open_positions:
            return

        lines = ["📊 <b>Portfolio Update - Price: $%.2f</b>\n" % current_price]

        total_unrealized = 0.0
        for pos in open_positions:
            pnl = pos["current_pnl"]
            total_unrealized += pnl
            emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
            lines.append(
                "#%s: Buy@%.2f | Now: %s $%.4f (%.2f%%) | High: %.2f | %.1fh" % (
                    pos["id"], pos["buy_price"], emoji, pnl,
                    pos["current_pct"], pos["highest"], pos["age_hours"]
                )
            )

        lines.append("\n<b>Unrealized:</b> <code>$%.4f</code>" % total_unrealized)
        lines.append("<b>Realized:</b> <code>$%.4f</code>" % total_realized)

        await self.send("\n".join(lines))

    async def notify_startup(self, proxy_info: str = ""):
        msg = (
            "🚀 <b>Bot Started!</b>\n\n"
            "<b>Settings:</b>\n"
            "• Min Profit: $%.2f / %.1f%%\n"
            "• Profit Targets: %s\n"
            "• Cooldown: %d min\n"
            "• Check Interval: %d sec\n\n"
            "%s"
            "<b>Policy: NEVER sell at loss</b>\n"
            "<b>Notifications enabled for all operations</b>"
        ) % (
            self.config.min_profit_usdt, self.config.min_profit_pct,
            ", ".join("%.1f%%" % t for t in self.config.profit_targets),
            self.config.cooldown_seconds // 60,
            self.config.check_interval,
            ("<b>Proxy:</b> %s\n\n" % proxy_info) if proxy_info else ""
        )
        await self.send(msg)

    async def notify_proxy_refresh(self, proxy_count: int, working_count: int, best_proxy: str, response_time: float):
        msg = (
            "🔄 <b>Proxy Refresh Complete</b>\n\n"
            "<b>Total fetched:</b> %d\n"
            "<b>Working:</b> %d\n"
            "<b>Best proxy:</b> <code>%s</code>\n"
            "<b>Response time:</b> <code>%.2fs</code>\n\n"
            "<b>Time:</b> %s"
        ) % (
            proxy_count, working_count, best_proxy, response_time,
            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        )
        await self.send(msg)

    async def notify_error(self, error: str, context: str = ""):
        msg = (
            "🚨 <b>Bot Error!</b>\n\n"
            "<b>Context:</b> %s\n"
            "<b>Error:</b> <code>%s</code>\n\n"
            "<b>Time:</b> %s\n\n"
            "Retrying..."
        ) % (
            context or "Unknown", error,
            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        )
        await self.send(msg)

    async def notify_daily_summary(self, stats: Dict):
        msg = (
            "📋 <b>Daily Summary</b>\n\n"
            "<b>Stats:</b>\n"
            "• Closed: %d\n"
            "• Open: %d\n"
            "• Total Profit: <code>$%.4f</code> USDT\n\n"
            "<b>%s</b>"
        ) % (
            stats["closed_count"], stats["open_count"],
            stats["total_realized_profit"],
            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        )
        await self.send(msg)


# ==========================================
# SMART RETRY SYSTEM
# ==========================================

class RetryManager:
    def __init__(self, config: Config):
        self.config = config
        self.failure_count = 0
        self.circuit_open = False
        self.circuit_reset_time = 0

    def get_delay(self) -> float:
        if self.circuit_open:
            if time.time() - self.circuit_reset_time > 60:
                self.circuit_open = False
                self.failure_count = 0
                return 1.0
            return self.config.max_retry_delay

        delay = min(self.config.base_retry_delay * (2 ** self.failure_count), 
                    self.config.max_retry_delay)
        return delay

    def record_success(self):
        if self.failure_count > 0:
            logging.info("Connection restored after %d failures" % self.failure_count)
        self.failure_count = 0

    def record_failure(self, error: str) -> float:
        self.failure_count += 1
        if self.failure_count >= self.config.max_retries:
            self.circuit_open = True
            self.circuit_reset_time = time.time()
            logging.error("Circuit breaker after %d failures" % self.failure_count)
        else:
            delay = self.get_delay()
            logging.warning("Failure #%d: %s. Retry in %.1fs..." % (self.failure_count, error, delay))
            return delay
        return self.config.max_retry_delay


# ==========================================
# PRICE ENGINE WITH PROXY
# ==========================================

class PriceEngine:
    def __init__(self, proxy_manager: AdvancedProxyManager):
        self.proxy_manager = proxy_manager
        self.price_cache = deque(maxlen=1000)
        self.last_price = 0.0
        self.last_update = 0
        self._lock = asyncio.Lock()

    async def get_price(self) -> Dict:
        """جلب السعر مع دعم البروكسي"""
        proxy_dict = self.proxy_manager.get_proxy_dict()

        try:
            # محاولة مع البروكسي
            if proxy_dict:
                connector = aiohttp.TCPConnector(ssl=False)
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.get(
                        "https://testnet.binance.vision/api/v3/ticker/price?symbol=BTCUSDT",
                        proxy=proxy_dict.get("http"),
                        timeout=aiohttp.ClientTimeout(total=10),
                        ssl=False
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            price = float(data.get("price", 0))
                            async with self._lock:
                                self.last_price = price
                                self.last_update = time.time()
                                self.price_cache.append({"price": price, "timestamp": time.time()})
                            return {"last": price, "source": "binance_proxy"}
        except Exception as e:
            logging.warning("Proxy price fetch failed: %s" % str(e))

        # Fallback: CoinGecko بدون بروكسي
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        price = data.get("bitcoin", {}).get("usd", 0)
                        async with self._lock:
                            self.last_price = price
                            self.last_update = time.time()
                            self.price_cache.append({"price": price, "timestamp": time.time()})
                        return {"last": price, "source": "coingecko_fallback"}
        except Exception as e:
            logging.error("All price sources failed: %s" % str(e))
            raise

    def get_stats(self) -> Dict:
        if len(self.price_cache) < 2:
            return {}
        prices = [c["price"] for c in self.price_cache]
        return {
            "high_24h": max(prices),
            "low_24h": min(prices)
        }


# ==========================================
# MAIN TRADING BOT
# ==========================================

class TradingBot:
    def __init__(self):
        self.config = Config()
        self.proxy_manager = AdvancedProxyManager(max_proxies=self.config.proxy_max_count)
        self.price_engine = PriceEngine(self.proxy_manager)
        self.positions = PositionManager(self.config)
        self.retry = RetryManager(self.config)
        self.notifier = TelegramNotifier(self.config)
        self.running = False
        self.processed_signals = set()
        self.last_buy_time = 0
        self._cycle_count = 0
        self._proxy_refresh_count = 0

    async def initialize(self):
        """تهيئة البوت مع البروكسي"""
        logging.info("=" * 60)
        logging.info("INITIALIZING BOT WITH ADVANCED PROXY SYSTEM")
        logging.info("=" * 60)

        # جلب واختبار البروكسيات
        best_proxy = await self.proxy_manager.refresh_proxies()

        if best_proxy:
            logging.info("Bot initialized with proxy: %s" % best_proxy)
        else:
            logging.warning("No working proxy found, will use fallback sources")

    async def refresh_proxy_if_needed(self):
        """تحديث البروكسي إذا لزم الأمر"""
        if time.time() - self.proxy_manager.last_refresh > self.config.proxy_refresh_interval:
            logging.info("Refreshing proxy list...")
            await self.proxy_manager.refresh_proxies()

            if self.proxy_manager.best_result:
                await self.notifier.notify_proxy_refresh(
                    len(self.proxy_manager.proxy_list),
                    len(self.proxy_manager.working_proxies),
                    self.proxy_manager.best_proxy,
                    self.proxy_manager.best_result.response_time
                )

    async def smart_execute(self, func: Callable, *args, **kwargs) -> Any:
        for attempt in range(self.config.max_retries):
            try:
                result = await func(*args, **kwargs)
                self.retry.record_success()
                return result
            except Exception as e:
                error_str = str(e)

                # إذا كان الخطأ بسبب البروكسي
                if "proxy" in error_str.lower() or "connection" in error_str.lower() or "451" in error_str:
                    logging.warning("Proxy/Connection error detected, switching proxy...")
                    await self.proxy_manager.mark_proxy_failed(self.proxy_manager.best_proxy)

                    # محاولة مع بروكسي آخر
                    next_proxy = await self.proxy_manager.get_next_proxy()
                    if next_proxy:
                        logging.info("Switched to next proxy: %s" % next_proxy)
                    else:
                        # إعادة جلب البروكسيات
                        await self.proxy_manager.refresh_proxies()

                delay = self.retry.record_failure(error_str)
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(delay)
                else:
                    raise
        return None

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
            price_data = await self.smart_execute(self.price_engine.get_price)
            current_price = price_data["last"]
        except Exception as e:
            logging.error("Price fetch failed: %s" % str(e))
            return None

        stats = self.price_engine.get_stats()
        low_24h = stats.get("low_24h", current_price)
        if current_price > low_24h * 1.001:
            return None

        raw_amount = self.config.trade_usdt_per_buy / current_price
        amount = max(raw_amount, self.config.min_btc_amount)

        # تنفيذ الشراء (محاكاة لأننا نستخدم بيانات فقط)
        try:
            buy_fee = (current_price * amount) * self.config.fee_rate
            total_cost = (current_price * amount) + buy_fee

            pos = await self.positions.create_position(
                current_price, amount, buy_fee, total_cost, buy_reason
            )

            self.last_buy_time = time.time()
            await self.notifier.notify_buy_success(pos)

            logging.info("BUY #%s: %.6f BTC @ %.2f" % (pos.id, amount, current_price))
            return pos

        except Exception as e:
            logging.error("Buy failed: %s" % str(e))
            await self.notifier.notify_buy_failed(str(e), current_price, amount)
            return None

    async def check_sell(self) -> List[Dict]:
        sold_results = []

        try:
            price_data = await self.smart_execute(self.price_engine.get_price)
            current_price = price_data["last"]
        except Exception as e:
            logging.error("Price fetch for sell failed: %s" % str(e))
            return sold_results

        ready_to_sell = await self.positions.check_all_positions(current_price)

        for pos, reason in ready_to_sell:
            try:
                result = await self.positions.close_position(pos.id, current_price, reason)

                if result:
                    await self.notifier.notify_sell_success(
                        pos, result, reason, self.positions.total_realized_profit
                    )

                    logging.info("SELL #%s: +$%.4f (%.2f%%)" % (pos.id, pos.net_profit, pos.profit_pct))
                    sold_results.append(result)

            except Exception as e:
                logging.error("Sell failed for #%s: %s" % (pos.id, str(e)))
                await self.notifier.notify_sell_failed(pos.id, str(e), current_price)

        return sold_results

    async def send_periodic_update(self):
        try:
            price_data = await self.price_engine.get_price()
            current_price = price_data["last"]
            open_details = self.positions.get_open_positions_details(current_price)

            if open_details:
                await self.notifier.notify_price_update(
                    current_price, open_details, self.positions.total_realized_profit
                )
        except Exception as e:
            logging.warning("Periodic update failed: %s" % str(e))

    async def run_cycle(self):
        now = datetime.now(timezone.utc)

        # تحديث البروكسي كل 10 دقائق
        await self.refresh_proxy_if_needed()

        await self.check_sell()
        await self.check_buy(now)

        self._cycle_count += 1
        if self._cycle_count % 30 == 0:
            await self.send_periodic_update()

        if now.hour == 0 and now.minute == 0 and now.second < 5:
            await self.notifier.notify_daily_summary(self.positions.get_stats())

    async def run(self):
        self.running = True

        async with self.notifier:
            await self.initialize()

            proxy_info = self.proxy_manager.best_proxy or "Direct/Fallback"
            await self.notifier.notify_startup(proxy_info)

            while self.running:
                start = time.time()
                try:
                    await self.run_cycle()
                    self.retry.record_success()
                except Exception as e:
                    delay = self.retry.record_failure(str(e))
                    await self.notifier.notify_error(str(e), "Main cycle")
                    await asyncio.sleep(delay)
                    continue

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
            logging.FileHandler("bot_proxy_advanced.log"),
            logging.StreamHandler()
        ]
    )

    bot = TradingBot()

    import signal
    def handle_signal(sig, frame):
        asyncio.create_task(bot.stop())

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logging.info("Stopped by user")
    except Exception as e:
        logging.critical("Fatal: %s" % str(e))
        raise
