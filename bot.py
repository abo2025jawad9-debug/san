"""
Binance Trading Bot - Fixed Syntax Error
Arabic text quotes fixed
"""

import ccxt
import ccxt.pro as ccxt_pro
import asyncio
import aiohttp
import json
import os
import time
import logging
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from typing import List, Dict, Optional, Callable, Any
from collections import deque
import uuid

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
# TELEGRAM NOTIFIER - FIXED
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

    # ============ BUY NOTIFICATIONS ============

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

    # ============ SELL NOTIFICATIONS ============

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

    # ============ MONITORING ============

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

    async def notify_startup(self):
        msg = (
            "🚀 <b>Bot Started!</b>\n\n"
            "<b>Settings:</b>\n"
            "• Min Profit: $%.2f / %.1f%%\n"
            "• Profit Targets: %s\n"
            "• Cooldown: %d min\n"
            "• Check Interval: %d sec\n\n"
            "<b>Policy: NEVER sell at loss</b>\n"
            "<b>Notifications enabled for all operations</b>"
        ) % (
            self.config.min_profit_usdt, self.config.min_profit_pct,
            ", ".join("%.1f%%" % t for t in self.config.profit_targets),
            self.config.cooldown_seconds // 60,
            self.config.check_interval
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
# REAL-TIME PRICE ENGINE
# ==========================================

class PriceEngine:
    def __init__(self, exchange: ccxt_pro.Exchange, config: Config):
        self.exchange = exchange
        self.config = config
        self.price_cache = deque(maxlen=1000)
        self.last_price = 0.0
        self.last_update = 0
        self.ws_connected = False
        self._lock = asyncio.Lock()

    async def start_websocket(self):
        while True:
            try:
                ticker = await self.exchange.watch_ticker("BTC/USDT")
                async with self._lock:
                    self.last_price = ticker["last"]
                    self.last_update = time.time()
                    self.price_cache.append({
                        "price": ticker["last"],
                        "bid": ticker.get("bid", ticker["last"]),
                        "ask": ticker.get("ask", ticker["last"]),
                        "volume": ticker.get("quoteVolume", 0),
                        "timestamp": time.time()
                    })
                    self.ws_connected = True
            except Exception as e:
                self.ws_connected = False
                logging.error("WebSocket error: %s" % str(e))
                await asyncio.sleep(1)

    async def get_price(self) -> Dict:
        async with self._lock:
            if self.ws_connected and (time.time() - self.last_update) < 5:
                cache = self.price_cache[-1] if self.price_cache else None
                if cache:
                    return {
                        "last": cache["price"],
                        "bid": cache["bid"],
                        "ask": cache["ask"],
                        "source": "websocket",
                        "latency_ms": (time.time() - cache["timestamp"]) * 1000
                    }

        ticker = await self.exchange.fetch_ticker("BTC/USDT")
        return {
            "last": ticker["last"],
            "bid": ticker.get("bid", ticker["last"]),
            "ask": ticker.get("ask", ticker["last"]),
            "source": "rest",
            "latency_ms": 0
        }

    def get_stats(self) -> Dict:
        if len(self.price_cache) < 2:
            return {}
        return {
            "high_24h": max(c["price"] for c in self.price_cache),
            "low_24h": min(c["price"] for c in self.price_cache)
        }


# ==========================================
# MAIN TRADING BOT
# ==========================================

class TradingBot:
    def __init__(self):
        self.config = Config()
        self.positions = PositionManager(self.config)
        self.retry = RetryManager(self.config)
        self.notifier = TelegramNotifier(self.config)
        self.exchange = None
        self.price_engine = None
        self.running = False
        self.processed_signals = set()
        self.last_buy_time = 0
        self._tasks = []
        self._cycle_count = 0

    async def initialize(self):
        self.exchange = ccxt_pro.binance({
            "apiKey": self.config.api_key,
            "secret": self.config.secret,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
            "sandbox": True,
        })
        await self.exchange.load_markets()
        self.price_engine = PriceEngine(self.exchange, self.config)

        ws_task = asyncio.create_task(self.price_engine.start_websocket())
        self._tasks.append(ws_task)
        logging.info("Bot initialized")

    async def smart_execute(self, func: Callable, *args, **kwargs) -> Any:
        for attempt in range(self.config.max_retries):
            try:
                result = await func(*args, **kwargs)
                self.retry.record_success()
                return result
            except Exception as e:
                delay = self.retry.record_failure(str(e))
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
        amount = float(self.exchange.amount_to_precision("BTC/USDT", raw_amount))

        if amount < self.config.min_btc_amount:
            return None

        try:
            order = await self.smart_execute(
                self.exchange.create_market_buy_order, "BTC/USDT", amount
            )

            buy_fee = (current_price * amount) * self.config.fee_rate
            total_cost = (current_price * amount) + buy_fee

            pos = await self.positions.create_position(
                current_price, amount, buy_fee, total_cost, buy_reason
            )

            self.last_buy_time = time.time()
            await self.notifier.notify_buy_success(pos, order)

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
                order = await self.smart_execute(
                    self.exchange.create_market_sell_order, "BTC/USDT", pos.amount
                )

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
            await self.notifier.notify_startup()

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
        for task in self._tasks:
            task.cancel()
        if self.exchange:
            await self.exchange.close()


# ==========================================
# ENTRY POINT
# ==========================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler("bot_fixed.log"),
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

