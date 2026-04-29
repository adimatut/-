"""
╔══════════════════════════════════════════════════════════════╗
║      VPN BOT + PROXY BOT — объединённый (aiogram 3.x)        ║
║   • 3x-ui Multi-Panel VPN (Telegram Stars + Platega СБП)     ║
║   • Бесплатные прокси из 6 источников + проверка своих       ║
╚══════════════════════════════════════════════════════════════╝

Установка:
    pip install aiogram aiosqlite aiohttp aiohttp_socks
Запуск:
    python bot.py
"""

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple
from urllib.parse import quote

import aiohttp
import aiosqlite
from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Опциональная поддержка SOCKS5
try:
    from aiohttp_socks import ProxyConnector
    SOCKS_AVAILABLE = True
except ImportError:
    SOCKS_AVAILABLE = False

# ═══════════════════════════════════════════════════════════════
# КОНФИГ — измените под себя
# ═══════════════════════════════════════════════════════════════
BOT_TOKEN      = "8738691847:AAEorKb7j-Ux9vsHzc7Zo_PTaRn5xgbrhPg"
SUPER_ADMIN_ID = 8418189367
DB_PATH        = "vpn_bot.db"

# ── Platega.io ───────────────────────────────────────────────────
PLATEGA_MERCHANT_ID    = "68de2c50-1e97-4586-b404-ba9c930b708a"
PLATEGA_SECRET         = "ZvugOmcovbwYRNBevL8wg7rvtz3irFRV0C4AH7RzAFtZmgDmBbMEbVr7DFe69BP3L3U3BlSYpFllGxwanKi4NMRbfxpLtvD1QE1E"
PLATEGA_BASE_URL       = "https://app.platega.io"
PLATEGA_PAYMENT_METHOD = 2
PLATEGA_RETURN_URL     = "https://t.me/KageriBot"
PLATEGA_FAIL_URL       = "https://t.me/KageriBot"

SUBSCRIPTION_PLANS = {
    "1_month":  {"days": 30,  "price": 169,  "name": "1 месяц",   "stars": 150},
    "3_months": {"days": 90,  "price": 449,  "name": "3 месяца",  "stars": 400},
    "6_months": {"days": 180, "price": 789,  "name": "6 месяцев", "stars": 700},
    "1_year":   {"days": 365, "price": 1349, "name": "1 год",     "stars": 1200},
}

TRAFFIC_LIMITS = {
    "1_month":  50,
    "3_months": 150,
    "6_months": 300,
    "1_year":   0,
}

FREE_VPN_DAYS    = 3
FREE_VPN_TRAFFIC = 5

PRIVACY_POLICY_URL = "https://telegra.ph/Politika-konfidencialnosti-04-01-26"
TERMS_OF_USE_URL   = "https://telegra.ph/Polzovatelskoe-soglashenie-04-01-19"

RULES_TEXT = (
    "📜 <b>Правила использования сервиса</b>\n\n"
    "Перед оформлением подписки обязательно ознакомьтесь с правилами:\n\n"
    "1️⃣ Запрещены DDOS-атаки и нагрузка на сеть.\n"
    "2️⃣ Запрещён брутфорс (подбор паролей).\n"
    "3️⃣ Запрещён криптомайнинг через наш трафик.\n"
    "4️⃣ Запрещён спам (email, мессенджеры, комментарии).\n"
    "5️⃣ Запрещён фишинг и любые мошеннические действия.\n"
    "6️⃣ Запрещена перепродажа и расшаривание доступа.\n"
    "7️⃣ Запрещено сканирование портов чужих серверов.\n"
    "8️⃣ Запрещены действия, нарушающие закон РФ "
    "(наркотики, терроризм и т.п.).\n"
    "9️⃣ Запрещён анализ/взлом нашей сети или попытки деанона "
    "других пользователей.\n\n"
    "⚠️ <b>Нарушение правил</b> ведёт к мгновенной блокировке "
    "подписки <u>без возврата средств</u>.\n\n"
    f"📄 <a href=\"{PRIVACY_POLICY_URL}\">Политика конфиденциальности</a>\n"
    f"📄 <a href=\"{TERMS_OF_USE_URL}\">Пользовательское соглашение</a>\n\n"
    "Нажимая «✅ Принимаю», вы подтверждаете, что прочитали и "
    "соглашаетесь со всеми условиями выше."
)

IMG_DIR      = Path(__file__).parent / "images"
IMG_MENU     = IMG_DIR / "work.png"
IMG_SUBS     = IMG_DIR / "key.jpg"
IMG_PAYMENTS = IMG_DIR / "payments.jpg"

# ── Прокси-конфиг ───────────────────────────────────────────────
PROXY_CACHE_MINUTES     = 15
PROXY_CHECK_TIMEOUT     = 5
PROXY_CHECK_CONCURRENCY = 50
PROXY_MAX_TO_CHECK      = 400
PROXY_PER_PAGE          = 8
PROXY_TEST_URL          = "http://httpbin.org/ip"

EXCLUDED_COUNTRIES = {"RU", "BY", "CN", "SY"}

GEO_API_URL          = "http://ip-api.com/batch"
GEO_BATCH_SIZE       = 100
GEO_RATE_LIMIT_DELAY = 4.5

COUNTRY_FLAGS = {
    "US": "🇺🇸", "DE": "🇩🇪", "GB": "🇬🇧", "FR": "🇫🇷", "NL": "🇳🇱",
    "JP": "🇯🇵", "SG": "🇸🇬", "HK": "🇭🇰", "KR": "🇰🇷", "IN": "🇮🇳",
    "BR": "🇧🇷", "CA": "🇨🇦", "AU": "🇦🇺", "TR": "🇹🇷", "IT": "🇮🇹",
    "ES": "🇪🇸", "PL": "🇵🇱", "UA": "🇺🇦", "KZ": "🇰🇿", "AR": "🇦🇷",
    "MX": "🇲🇽", "ID": "🇮🇩", "TH": "🇹🇭", "VN": "🇻🇳", "PH": "🇵🇭",
    "MY": "🇲🇾", "PK": "🇵🇰", "BD": "🇧🇩", "EG": "🇪🇬", "ZA": "🇿🇦",
    "RO": "🇷🇴", "CZ": "🇨🇿", "SE": "🇸🇪", "FI": "🇫🇮", "NO": "🇳🇴",
    "DK": "🇩🇰", "CH": "🇨🇭", "AT": "🇦🇹", "BE": "🇧🇪", "PT": "🇵🇹",
    "IE": "🇮🇪", "GR": "🇬🇷", "HU": "🇭🇺", "BG": "🇧🇬", "HR": "🇭🇷",
    "RS": "🇷🇸", "LT": "🇱🇹", "LV": "🇱🇻", "EE": "🇪🇪", "MD": "🇲🇩",
    "GE": "🇬🇪", "AM": "🇦🇲", "AZ": "🇦🇿", "IL": "🇮🇱", "AE": "🇦🇪",
    "SA": "🇸🇦", "IR": "🇮🇷", "IQ": "🇮🇶", "CL": "🇨🇱", "CO": "🇨🇴",
    "PE": "🇵🇪", "VE": "🇻🇪", "EC": "🇪🇨", "TW": "🇹🇼", "MM": "🇲🇲",
    "LK": "🇱🇰", "NP": "🇳🇵", "NZ": "🇳🇿", "MA": "🇲🇦", "DZ": "🇩🇿",
    "TN": "🇹🇳", "NG": "🇳🇬", "KE": "🇰🇪", "ET": "🇪🇹", "GH": "🇬🇭",
}

PROXY_SOURCES = [
    {"name": "ProxyScrape HTTP",  "url": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&country=all",    "type": "http"},
    {"name": "ProxyScrape SOCKS5","url": "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5&timeout=5000&country=all",  "type": "socks5"},
    {"name": "TheSpeedX HTTP",    "url": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",                      "type": "http"},
    {"name": "TheSpeedX SOCKS5",  "url": "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",                    "type": "socks5"},
    {"name": "MonoSans HTTP",     "url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",                 "type": "http"},
    {"name": "MonoSans SOCKS5",   "url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",               "type": "socks5"},
]

PROXY_RE = re.compile(r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{1,5})$")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger(__name__)

if not SOCKS_AVAILABLE:
    log.warning("⚠️ aiohttp_socks не установлен — SOCKS5 проверяться не будут.")


# ═══════════════════════════════════════════════════════════════
# БАЗА ДАННЫХ
# ═══════════════════════════════════════════════════════════════
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY,
                tg_id         INTEGER UNIQUE NOT NULL,
                username      TEXT,
                full_name     TEXT,
                is_admin      INTEGER DEFAULT 0,
                is_banned     INTEGER DEFAULT 0,
                balance       REAL    DEFAULT 0,
                referral_id   INTEGER,
                free_used     INTEGER DEFAULT 0,
                rules_accepted INTEGER DEFAULT 0,
                registered_at TEXT    DEFAULT (datetime('now')),
                last_active   TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS panels (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT NOT NULL,
                url             TEXT NOT NULL,
                username        TEXT NOT NULL,
                password        TEXT NOT NULL,
                inbound_id      INTEGER DEFAULT 1,
                sub_url         TEXT NOT NULL,
                location        TEXT    DEFAULT 'Unknown',
                flag            TEXT    DEFAULT '🌍',
                is_active       INTEGER DEFAULT 1,
                max_clients     INTEGER DEFAULT 100,
                current_clients INTEGER DEFAULT 0,
                added_by        INTEGER,
                added_at        TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL,
                panel_id     INTEGER NOT NULL,
                plan_key     TEXT    NOT NULL,
                client_uuid  TEXT    NOT NULL,
                client_email TEXT    NOT NULL,
                traffic_gb   INTEGER DEFAULT 50,
                expires_at   TEXT    NOT NULL,
                is_active    INTEGER DEFAULT 1,
                config_link  TEXT,
                created_at   TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS payments (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                amount          REAL    NOT NULL,
                currency        TEXT    DEFAULT 'RUB',
                payment_method  TEXT,
                payment_id      TEXT,
                status          TEXT    DEFAULT 'pending',
                plan_key        TEXT,
                panel_id        INTEGER,
                subscription_id INTEGER,
                created_at      TEXT    DEFAULT (datetime('now')),
                completed_at    TEXT
            );

            CREATE TABLE IF NOT EXISTS promo_codes (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                code             TEXT UNIQUE NOT NULL,
                discount_percent INTEGER DEFAULT 0,
                free_days        INTEGER DEFAULT 0,
                sub_days         INTEGER DEFAULT 0,
                promo_panel_id   INTEGER DEFAULT NULL,
                max_uses         INTEGER DEFAULT 1,
                uses             INTEGER DEFAULT 0,
                is_active        INTEGER DEFAULT 1,
                created_by       INTEGER,
                created_at       TEXT    DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS free_proxies (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ip           TEXT    NOT NULL,
                port         INTEGER NOT NULL,
                proxy_type   TEXT    NOT NULL,
                country_code TEXT    DEFAULT '',
                country_name TEXT    DEFAULT '',
                latency_ms   INTEGER DEFAULT 0,
                checked_at   TEXT    DEFAULT (datetime('now')),
                UNIQUE(ip, port, proxy_type)
            );
            CREATE INDEX IF NOT EXISTS idx_proxy_checked ON free_proxies(checked_at);
            CREATE INDEX IF NOT EXISTS idx_proxy_country ON free_proxies(country_code);
        """)
        await db.commit()

    # Авто-миграции
    async with aiosqlite.connect(DB_PATH) as db:
        for col, ddl in [
            ("free_used",          "ALTER TABLE users         ADD COLUMN free_used          INTEGER DEFAULT 0"),
            ("rules_accepted",     "ALTER TABLE users         ADD COLUMN rules_accepted     INTEGER DEFAULT 0"),
            ("sub_url",            "ALTER TABLE panels        ADD COLUMN sub_url            TEXT"),
            ("sub_days",           "ALTER TABLE promo_codes   ADD COLUMN sub_days           INTEGER DEFAULT 0"),
            ("promo_panel_id",     "ALTER TABLE promo_codes   ADD COLUMN promo_panel_id     INTEGER DEFAULT NULL"),
            ("last_region_change", "ALTER TABLE subscriptions ADD COLUMN last_region_change TEXT"),
        ]:
            try:
                await db.execute(ddl)
                await db.commit()
                log.info(f"✅ Колонка {col} добавлена")
            except Exception:
                pass

    log.info("✅ DB ready")


# ── Хелперы ──────────────────────────────────────────────────────
async def db_fetchone(sql, params=()):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(sql, params) as cur:
            return await cur.fetchone()


async def db_fetchall(sql, params=()):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(sql, params) as cur:
            return await cur.fetchall()


async def db_execute(sql, params=()):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(sql, params)
        await db.commit()
        return cur.lastrowid


async def db_update(table, row_id, id_col="id", **kwargs):
    if not kwargs:
        return
    fields = ", ".join(f"{k}=?" for k in kwargs)
    vals   = list(kwargs.values()) + [row_id]
    await db_execute(f"UPDATE {table} SET {fields} WHERE {id_col}=?", vals)


# ── Пользователи ─────────────────────────────────────────────────
async def get_user(tg_id):
    return await db_fetchone("SELECT * FROM users WHERE tg_id=?", (tg_id,))


async def create_user(tg_id, username, full_name, referral_id=None):
    await db_execute(
        "INSERT OR IGNORE INTO users (tg_id,username,full_name,referral_id) VALUES(?,?,?,?)",
        (tg_id, username, full_name, referral_id),
    )


async def get_all_users():
    return await db_fetchall("SELECT * FROM users ORDER BY registered_at DESC")


async def get_all_admins():
    rows = await db_fetchall("SELECT tg_id FROM users WHERE is_admin=1")
    admin_ids = [r["tg_id"] for r in rows]
    if SUPER_ADMIN_ID not in admin_ids:
        admin_ids.append(SUPER_ADMIN_ID)
    return admin_ids


async def get_stats():
    s = {}
    for key, sql in [
        ("total_users",   "SELECT COUNT(*) FROM users"),
        ("banned_users",  "SELECT COUNT(*) FROM users WHERE is_banned=1"),
        ("active_subs",   "SELECT COUNT(*) FROM subscriptions WHERE is_active=1"),
        ("active_panels", "SELECT COUNT(*) FROM panels WHERE is_active=1"),
        ("new_today",     "SELECT COUNT(*) FROM users WHERE registered_at > datetime('now','-1 day')"),
    ]:
        row = await db_fetchone(sql)
        s[key] = row[0] if row else 0
    row = await db_fetchone("SELECT SUM(amount) FROM payments WHERE status='completed'")
    s["total_revenue"] = (row[0] or 0) if row else 0
    return s


# ── Панели ───────────────────────────────────────────────────────
async def add_panel(name, url, username, password, inbound_id,
                    sub_url, location, flag, added_by):
    return await db_execute(
        "INSERT INTO panels(name,url,username,password,inbound_id,"
        "sub_url,location,flag,added_by) VALUES(?,?,?,?,?,?,?,?,?)",
        (name, url, username, password, inbound_id, sub_url, location, flag, added_by),
    )


async def get_panel(pid):
    return await db_fetchone("SELECT * FROM panels WHERE id=?", (pid,))


async def get_all_panels(active_only=True):
    sql = "SELECT * FROM panels" + (" WHERE is_active=1" if active_only else "")
    return await db_fetchall(sql)


async def delete_panel(pid):
    await db_execute("DELETE FROM panels WHERE id=?", (pid,))


# ── Подписки ─────────────────────────────────────────────────────
async def create_subscription(user_id, panel_id, plan_key, client_uuid,
                              client_email, traffic_gb, expires_at, config_link):
    sid = await db_execute(
        "INSERT INTO subscriptions"
        "(user_id,panel_id,plan_key,client_uuid,client_email,"
        "traffic_gb,expires_at,config_link) VALUES(?,?,?,?,?,?,?,?)",
        (user_id, panel_id, plan_key, client_uuid, client_email,
         traffic_gb, expires_at, config_link),
    )
    await db_execute(
        "UPDATE panels SET current_clients=current_clients+1 WHERE id=?", (panel_id,)
    )
    return sid


async def get_subscription(sid):
    return await db_fetchone("SELECT * FROM subscriptions WHERE id=?", (sid,))


async def get_active_subscriptions(user_id):
    return await db_fetchall(
        """SELECT s.*, p.name AS panel_name, p.flag, p.location, p.url
           FROM subscriptions s JOIN panels p ON s.panel_id=p.id
           WHERE s.user_id=? AND s.is_active=1 AND s.expires_at > datetime('now')
           ORDER BY s.expires_at DESC""",
        (user_id,),
    )


# ── Платежи ──────────────────────────────────────────────────────
async def create_payment(user_id, amount, currency, method, plan_key, panel_id):
    return await db_execute(
        "INSERT INTO payments(user_id,amount,currency,payment_method,plan_key,panel_id)"
        " VALUES(?,?,?,?,?,?)",
        (user_id, amount, currency, method, plan_key, panel_id),
    )


# ── Промокоды ────────────────────────────────────────────────────
async def get_promo(code):
    return await db_fetchone(
        "SELECT * FROM promo_codes WHERE code=? AND is_active=1 AND uses<max_uses",
        (code.upper(),),
    )


async def create_promo(code, discount, free_days, max_uses, created_by, sub_days=0, promo_panel_id=None):
    await db_execute(
        "INSERT INTO promo_codes(code,discount_percent,free_days,sub_days,promo_panel_id,max_uses,created_by)"
        " VALUES(?,?,?,?,?,?,?)",
        (code.upper(), discount, free_days, sub_days, promo_panel_id, max_uses, created_by),
    )


# ═══════════════════════════════════════════════════════════════
# 3x-ui API КЛИЕНТ
# ═══════════════════════════════════════════════════════════════
class XUIClient:
    def __init__(self, url: str, username: str, password: str):
        self.base  = url.rstrip("/")
        self.user  = username
        self.pwd   = password
        self._sess = None
        self._cook = None

    async def _session(self):
        if not self._sess or self._sess.closed:
            self._sess = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=False)
            )
        return self._sess

    async def login(self) -> bool:
        try:
            s = await self._session()
            async with s.post(
                f"{self.base}/login",
                json={"username": self.user, "password": self.pwd},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    if data.get("success"):
                        self._cook = r.cookies
                        return True
            return False
        except Exception as e:
            log.error(f"XUI login error {self.base}: {e}")
            return False

    async def _req(self, method, endpoint, **kw):
        if not self._cook:
            if not await self.login():
                return None
        s = await self._session()
        try:
            async with s.request(
                method, f"{self.base}{endpoint}",
                cookies=self._cook,
                timeout=aiohttp.ClientTimeout(total=20),
                ssl=False, **kw,
            ) as r:
                raw = await r.text()
                if r.status == 401:
                    self._cook = None
                    if await self.login():
                        return await self._req(method, endpoint, **kw)
                    return None
                if r.status == 200:
                    try:
                        return json.loads(raw)
                    except Exception:
                        return None
        except Exception as e:
            log.error(f"XUI req {endpoint}: {e}")
        return None

    async def get_inbound(self, iid: int):
        d = await self._req("GET", f"/panel/api/inbounds/get/{iid}")
        return d.get("obj") if d and d.get("success") else None

    async def add_client(self, inbound_id, email, traffic_gb=50, expire_days=30, limit_ip=3):
        inbound = await self.get_inbound(inbound_id)
        flow = ""
        if inbound:
            protocol   = inbound.get("protocol", "")
            stream_raw = inbound.get("streamSettings", "{}")
            stream     = json.loads(stream_raw) if isinstance(stream_raw, str) else stream_raw
            security   = stream.get("security", "none")
            if protocol == "vless" and security in ("reality", "tls", "xtls"):
                flow = "xtls-rprx-vision"
        cid = str(uuid.uuid4())
        exp = int((datetime.now() + timedelta(days=expire_days)).timestamp() * 1000)
        tb  = traffic_gb * 1024 ** 3 if traffic_gb > 0 else 0
        payload = {
            "id": inbound_id,
            "settings": json.dumps({"clients": [{
                "id": cid, "email": email, "enable": True,
                "expiryTime": exp, "totalGB": tb,
                "limitIp": limit_ip, "flow": flow,
                "subId": email, "tgId": "", "reset": 0,
            }]}),
        }
        d = await self._req("POST", "/panel/api/inbounds/addClient", json=payload)
        if d and d.get("success"):
            return {"uuid": cid, "email": email}
        return None

    async def delete_client(self, inbound_id, client_uuid) -> bool:
        d = await self._req("POST", f"/panel/api/inbounds/{inbound_id}/delClient/{client_uuid}")
        return bool(d and d.get("success"))

    async def update_client(self, inbound_id, client_uuid, **kw) -> bool:
        inbound = await self.get_inbound(inbound_id)
        if not inbound:
            return False
        settings = json.loads(inbound.get("settings", "{}"))
        clients  = settings.get("clients", [])
        for c in clients:
            if c.get("id") == client_uuid:
                c.update(kw)
                payload = {
                    "id": inbound_id,
                    "settings": json.dumps({"clients": [c]}),
                }
                d = await self._req(
                    "POST", f"/panel/api/inbounds/updateClient/{client_uuid}", json=payload
                )
                return bool(d and d.get("success"))
        return False

    async def get_client_stats(self, email):
        d = await self._req("GET", f"/panel/api/inbounds/getClientTraffics/{email}")
        return d.get("obj") if d and d.get("success") else None

    def sub_link(self, sub_url, email: str) -> str:
        base = (sub_url or self.base).strip().rstrip("/")
        if base.startswith("http://"):
            base = "https://" + base[len("http://"):]
        elif not base.startswith("https://"):
            base = "https://" + base.lstrip("/")
        return f"{base}/{email}"

    async def test(self) -> bool:
        return await self.login()

    async def close(self):
        if self._sess and not self._sess.closed:
            await self._sess.close()


_xui_cache: dict[int, XUIClient] = {}


def xui(panel) -> XUIClient:
    pid = panel["id"]
    if pid not in _xui_cache:
        _xui_cache[pid] = XUIClient(panel["url"], panel["username"], panel["password"])
    return _xui_cache[pid]


def drop_xui(pid: int):
    _xui_cache.pop(pid, None)


# ═══════════════════════════════════════════════════════════════
# PLATEGA API КЛИЕНТ
# ═══════════════════════════════════════════════════════════════
class PlategaClient:
    def __init__(self, merchant_id: str, secret: str, base_url: str = PLATEGA_BASE_URL):
        self.merchant_id = merchant_id
        self.secret      = secret
        self.base        = base_url.rstrip("/")
        self._sess: Optional[aiohttp.ClientSession] = None

    async def _session(self) -> aiohttp.ClientSession:
        if not self._sess or self._sess.closed:
            self._sess = aiohttp.ClientSession(
                headers={
                    "X-MerchantId": self.merchant_id,
                    "X-Secret":     self.secret,
                    "Content-Type": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=25),
            )
        return self._sess

    async def create_transaction(self, amount, description, payload,
                                  return_url=PLATEGA_RETURN_URL,
                                  failed_url=PLATEGA_FAIL_URL,
                                  payment_method=PLATEGA_PAYMENT_METHOD,
                                  currency="RUB") -> Optional[dict]:
        body = {
            "paymentMethod":  payment_method,
            "paymentDetails": {"amount": amount, "currency": currency},
            "description":    description,
            "return":         return_url,
            "failedUrl":      failed_url,
            "payload":        payload,
        }
        try:
            s = await self._session()
            async with s.post(f"{self.base}/transaction/process", json=body) as r:
                raw = await r.text()
                if r.status in (200, 201):
                    try:
                        return json.loads(raw)
                    except Exception:
                        return None
                return None
        except Exception as e:
            log.error(f"Platega create exception: {e}")
            return None

    async def get_status(self, transaction_id: str) -> Optional[dict]:
        try:
            s = await self._session()
            async with s.get(f"{self.base}/transaction/{transaction_id}") as r:
                raw = await r.text()
                if r.status == 200:
                    try:
                        return json.loads(raw)
                    except Exception:
                        return None
                return None
        except Exception as e:
            log.error(f"Platega status exception: {e}")
            return None

    async def close(self):
        if self._sess and not self._sess.closed:
            await self._sess.close()


platega = PlategaClient(PLATEGA_MERCHANT_ID, PLATEGA_SECRET, PLATEGA_BASE_URL)

PLATEGA_STATUS_OK     = {"CONFIRMED"}
PLATEGA_STATUS_FAILED = {"CANCELED", "CANCELLED", "EXPIRED", "FAILED", "DECLINED"}


# ═══════════════════════════════════════════════════════════════
# СЕРВИС ПОДПИСОК
# ═══════════════════════════════════════════════════════════════
async def make_subscription(user_id, panel_id, plan_key, traffic_override=None, days_override=None):
    panel = await get_panel(panel_id)
    plan  = SUBSCRIPTION_PLANS.get(plan_key)
    if not panel:
        return None

    traffic = traffic_override if traffic_override is not None else TRAFFIC_LIMITS.get(plan_key, 50)
    days    = days_override    if days_override    is not None else (plan["days"] if plan else 30)

    client = xui(panel)
    email  = f"u{user_id}_{uuid.uuid4().hex[:6]}"

    result = await client.add_client(panel["inbound_id"], email, traffic, days)
    if not result:
        return None

    expires    = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    config_url = client.sub_link(panel["sub_url"], email)

    sid = await create_subscription(
        user_id, panel_id, plan_key,
        result["uuid"], email, traffic, expires, config_url,
    )
    return {
        "sub_id":      sid,
        "uuid":        result["uuid"],
        "email":       email,
        "config_link": config_url,
        "expires_at":  expires,
        "panel_name":  panel["name"],
        "flag":        panel["flag"],
    }


async def extend_sub(sid, extra_days) -> bool:
    sub   = await get_subscription(sid)
    panel = await get_panel(sub["panel_id"]) if sub else None
    if not sub or not panel:
        return False
    cur = datetime.strptime(sub["expires_at"], "%Y-%m-%d %H:%M:%S")
    new = (cur if cur > datetime.now() else datetime.now()) + timedelta(days=extra_days)
    ok  = await xui(panel).update_client(
        panel["inbound_id"], sub["client_uuid"],
        expiryTime=int(new.timestamp() * 1000),
    )
    if ok:
        await db_update("subscriptions", sid,
                        expires_at=new.strftime("%Y-%m-%d %H:%M:%S"), is_active=1)
    return ok


REGION_CHANGE_COOLDOWN_HOURS = 24


def region_change_cooldown_left(sub) -> timedelta:
    last = sub["last_region_change"] if "last_region_change" in sub.keys() else None
    if not last:
        return timedelta(0)
    try:
        last_dt = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return timedelta(0)
    elapsed  = datetime.now() - last_dt
    cooldown = timedelta(hours=REGION_CHANGE_COOLDOWN_HOURS)
    return cooldown - elapsed if elapsed < cooldown else timedelta(0)


async def migrate_subscription(sid: int, new_panel_id: int) -> dict | None:
    sub = await get_subscription(sid)
    if not sub:
        return None
    expires_at = datetime.strptime(sub["expires_at"], "%Y-%m-%d %H:%M:%S")
    if expires_at <= datetime.now():
        return None
    old_panel = await get_panel(sub["panel_id"])
    new_panel = await get_panel(new_panel_id)
    if not new_panel or not new_panel["is_active"] or new_panel["id"] == sub["panel_id"]:
        return None

    new_client = xui(new_panel)
    new_email  = f"u{sub['user_id']}_{uuid.uuid4().hex[:6]}"
    new_uuid   = str(uuid.uuid4())
    expiry_ms  = int(expires_at.timestamp() * 1000)
    traffic_b  = sub["traffic_gb"] * 1024 ** 3 if sub["traffic_gb"] > 0 else 0

    inbound = await new_client.get_inbound(new_panel["inbound_id"])
    flow = ""
    if inbound:
        protocol   = inbound.get("protocol", "")
        stream_raw = inbound.get("streamSettings", "{}")
        stream     = json.loads(stream_raw) if isinstance(stream_raw, str) else stream_raw
        security   = stream.get("security", "none")
        if protocol == "vless" and security in ("reality", "tls", "xtls"):
            flow = "xtls-rprx-vision"

    payload = {
        "id": new_panel["inbound_id"],
        "settings": json.dumps({"clients": [{
            "id": new_uuid, "email": new_email, "enable": True,
            "expiryTime": expiry_ms, "totalGB": traffic_b,
            "limitIp": 3, "flow": flow,
            "subId": new_email, "tgId": "", "reset": 0,
        }]}),
    }
    resp = await new_client._req("POST", "/panel/api/inbounds/addClient", json=payload)
    if not (resp and resp.get("success")):
        return None

    new_config = new_client.sub_link(new_panel["sub_url"], new_email)

    if old_panel:
        try:
            await xui(old_panel).delete_client(old_panel["inbound_id"], sub["client_uuid"])
        except Exception:
            pass
        await db_execute(
            "UPDATE panels SET current_clients=MAX(0,current_clients-1) WHERE id=?",
            (sub["panel_id"],),
        )

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await db_update(
        "subscriptions", sid,
        panel_id=new_panel_id, client_uuid=new_uuid, client_email=new_email,
        config_link=new_config, last_region_change=now_str,
    )
    await db_execute(
        "UPDATE panels SET current_clients=current_clients+1 WHERE id=?", (new_panel_id,)
    )
    return {
        "sub_id":      sid,
        "uuid":        new_uuid,
        "email":       new_email,
        "config_link": new_config,
        "expires_at":  sub["expires_at"],
        "panel_name":  new_panel["name"],
        "flag":        new_panel["flag"],
    }


async def activate_after_platega(bot: Bot, pay_id: int) -> bool:
    pay = await db_fetchone("SELECT * FROM payments WHERE id=?", (pay_id,))
    if not pay:
        return False
    if pay["status"] == "completed":
        return True

    user_id  = pay["user_id"]
    panel_id = pay["panel_id"]
    plan_key = pay["plan_key"]

    result = await make_subscription(user_id, panel_id, plan_key)
    if not result:
        try:
            await bot.send_message(user_id,
                "❌ <b>Оплата получена, но создать подписку не удалось</b>\n\n"
                "Напишите в 💬 поддержку — активируем вручную.",
                reply_markup=kb_home_vpn())
        except Exception:
            pass
        return False

    await db_update("payments", pay_id,
                    status="completed", subscription_id=result["sub_id"],
                    completed_at=str(datetime.now()))
    try:
        await bot.send_message(user_id,
            f"✅ <b>Подписка успешно активирована!</b>\n\n"
            f"📡 Сервер: {result['flag']} {result['panel_name']}\n"
            f"📅 Действует до: <b>{result['expires_at'][:10]}</b>\n\n"
            f"🔗 <b>Ваша ссылка для подключения:</b>\n"
            f"<code>{result['config_link']}</code>\n\n"
            "📱 Hiddify / v2rayNG / Streisand → добавить подписку → обновить\n\n"
            "Спасибо, что выбрали KageriVPN! 💙",
            reply_markup=kb_home_vpn())
    except Exception:
        pass
    return True


# ═══════════════════════════════════════════════════════════════
# КЛАВИАТУРЫ
# ═══════════════════════════════════════════════════════════════
def kb_main(is_admin_user=False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🛡 Мои подписки",     callback_data="menu:my_subs")
    b.button(text="🛒 Купить VPN",       callback_data="menu:buy")
    b.button(text="🆓 Пробный VPN",      callback_data="menu:free")
    b.button(text="🎁 Промокод",         callback_data="menu:promo")
    b.button(text="💰 Баланс",           callback_data="menu:balance")
    b.button(text="👥 Рефералка",        callback_data="menu:ref")
    b.button(text="📜 Правила",          callback_data="menu:rules")
    b.button(text="💬 Поддержка",        callback_data="menu:support")
    if is_admin_user:
        b.button(text="⚙️ Админ панель", callback_data="menu:admin")
    b.button(text="🌐 Бесплатные прокси", callback_data="menu:proxy")
    b.adjust(2, 2, 2, 2, 1, 1)
    return b.as_markup()


def kb_home_vpn() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🏠 Главное меню", callback_data="menu:home")
    return b.as_markup()


# Алиас для совместимости внутри кода
kb_home = kb_home_vpn


def kb_plans(panel_id) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for k, p in SUBSCRIPTION_PLANS.items():
        b.button(
            text=f"📅 {p['name']} — ⭐ {p['stars']} / {p['price']}₽",
            callback_data=f"buy:{panel_id}:{k}",
        )
    b.button(text="◀️ Назад к серверам", callback_data="back_panels")
    b.button(text="🏠 Главное меню",     callback_data="menu:home")
    b.adjust(1)
    return b.as_markup()


def kb_panels(panels) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for p in panels:
        load = int(p["current_clients"] / max(p["max_clients"], 1) * 100)
        dot  = "🟢" if load < 60 else ("🟡" if load < 85 else "🔴")
        b.button(
            text=f"{p['flag']} {p['name']} ({p['location']}) {dot}",
            callback_data=f"panel:{p['id']}",
        )
    b.button(text="🏠 Главное меню", callback_data="menu:home")
    b.adjust(1)
    return b.as_markup()


def kb_pay(panel_id, plan_key) -> InlineKeyboardMarkup:
    p = SUBSCRIPTION_PLANS[plan_key]
    b = InlineKeyboardBuilder()
    b.button(text=f"⭐ Telegram Stars ({p['stars']} ⭐)", callback_data=f"pay:stars:{panel_id}:{plan_key}")
    b.button(text=f"💳 СБП / Карта ({p['price']}₽)",    callback_data=f"pay:platega:{panel_id}:{plan_key}")
    b.button(text="◀️ Назад к тарифам", callback_data=f"panel:{panel_id}")
    b.button(text="🏠 Главное меню",    callback_data="menu:home")
    b.adjust(1)
    return b.as_markup()


def kb_platega_payment(pay_id: int, redirect_url: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💳 Перейти к оплате",     url=redirect_url)
    b.button(text="🔄 Я оплатил — проверить", callback_data=f"platega:check:{pay_id}")
    b.button(text="❌ Отменить",              callback_data=f"platega:cancel:{pay_id}")
    b.adjust(1)
    return b.as_markup()


def kb_legal(panel_id, plan_key) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📄 Политика конфиденциальности", url=PRIVACY_POLICY_URL)
    b.button(text="📄 Пользовательское соглашение", url=TERMS_OF_USE_URL)
    b.button(text="✅ Принимаю и оплачиваю", callback_data=f"legal:accept:{panel_id}:{plan_key}")
    b.button(text="❌ Отказаться", callback_data="menu:home")
    b.adjust(1)
    return b.as_markup()


def kb_legal_free(panel_id) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📄 Политика конфиденциальности", url=PRIVACY_POLICY_URL)
    b.button(text="📄 Пользовательское соглашение", url=TERMS_OF_USE_URL)
    b.button(text="✅ Принимаю и активирую", callback_data=f"legal:free:{panel_id}")
    b.button(text="❌ Отказаться", callback_data="menu:home")
    b.adjust(1)
    return b.as_markup()


def kb_sub(sid) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📊 Трафик",        callback_data=f"sub:traffic:{sid}")
    b.button(text="🔗 Конфиг",        callback_data=f"sub:config:{sid}")
    b.button(text="🌍 Сменить регион", callback_data=f"sub:region:{sid}")
    b.button(text="♻️ Продлить",      callback_data=f"sub:renew:{sid}")
    b.button(text="◀️ К подпискам",   callback_data="my_subs")
    b.button(text="🏠 Главное меню",  callback_data="menu:home")
    b.adjust(2, 1, 1, 1, 1)
    return b.as_markup()


def kb_subs_list(subs) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for s in subs:
        b.button(
            text=f"{s['flag']} {s['panel_name']} · до {s['expires_at'][:10]}",
            callback_data=f"sub:view:{s['id']}",
        )
    b.button(text="🛒 Купить ещё",   callback_data="buy_vpn")
    b.button(text="🏠 Главное меню", callback_data="menu:home")
    b.adjust(1)
    return b.as_markup()


def kb_free_panels(panels) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for p in panels:
        b.button(
            text=f"{p['flag']} {p['name']} ({p['location']})",
            callback_data=f"free:panel:{p['id']}",
        )
    b.button(text="🏠 Главное меню", callback_data="menu:home")
    b.adjust(1)
    return b.as_markup()


def kb_admin_main(is_super=False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📊 Статистика",   callback_data="adm:stats")
    b.button(text="📡 Панели",       callback_data="adm:panels")
    b.button(text="👥 Пользователи", callback_data="adm:users")
    b.button(text="📢 Рассылка",     callback_data="adm:broadcast")
    if is_super:
        b.button(text="🎁 Промокоды",          callback_data="adm:promos")
        b.button(text="🔑 Генератор ключей",   callback_data="adm:keygen")
        b.button(text="👮 Управление админами", callback_data="adm:admins")
    b.button(text="🏠 Главное меню", callback_data="menu:home")
    b.adjust(2)
    return b.as_markup()


def kb_admin_panels(panels) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for p in panels:
        ico = "✅" if p["is_active"] else "❌"
        b.button(text=f"{ico} {p['flag']} {p['name']}", callback_data=f"adm:panel:{p['id']}")
    b.button(text="➕ Добавить панель", callback_data="adm:panel:add")
    b.button(text="◀️ Назад в админку", callback_data="adm:back")
    b.adjust(1)
    return b.as_markup()


def kb_panel_detail(pid, active) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔴 Отключить" if active else "🟢 Включить", callback_data=f"adm:ptoggle:{pid}")
    b.button(text="🔍 Проверить", callback_data=f"adm:ptest:{pid}")
    b.button(text="🗑 Удалить",   callback_data=f"adm:pdel:{pid}")
    b.button(text="◀️ К списку панелей", callback_data="adm:panels")
    b.adjust(2, 1, 1)
    return b.as_markup()


def kb_keygen_panels(panels) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for p in panels:
        b.button(text=f"{p['flag']} {p['name']} ({p['location']})", callback_data=f"keygen:panel:{p['id']}")
    b.button(text="◀️ Назад в админку", callback_data="adm:back")
    b.adjust(1)
    return b.as_markup()


def kb_keygen_plans(panel_id) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for k, p in SUBSCRIPTION_PLANS.items():
        b.button(text=f"📅 {p['name']} ({p['days']} дн.)", callback_data=f"keygen:plan:{panel_id}:{k}")
    b.button(text="♾ Бессрочный (9999 дн.)", callback_data=f"keygen:plan:{panel_id}:forever")
    b.button(text="◀️ Назад", callback_data="adm:keygen")
    b.adjust(1)
    return b.as_markup()


def kb_user_manage(tg_id, banned, admin) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Разбанить" if banned else "🚫 Забанить", callback_data=f"adm:uban:{tg_id}")
    b.button(text="👤 Снять права" if admin else "⚙️ Сделать админом", callback_data=f"adm:uadmin:{tg_id}")
    b.button(text="◀️ К админ-панели", callback_data="adm:back")
    b.adjust(2, 1)
    return b.as_markup()


def kb_back(cb="menu:home") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="◀️ Назад", callback_data=cb)
    return b.as_markup()


def kb_confirm(yes, no="menu:home") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Да",  callback_data=yes)
    b.button(text="❌ Нет", callback_data=no)
    return b.as_markup()


# ── Прокси-клавиатуры ───────────────────────────────────────────
def kb_proxy_list(proxies_on_page: List[Dict], page: int,
                  total_pages: int, page_offset: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    rows: List[int] = []
    for i, p in enumerate(proxies_on_page, start=page_offset + 1):
        link = _make_tg_proxy_link(p)
        if link:
            flag = _country_flag(p["country_code"])
            b.button(text=f"📲 {i}. {flag} {p['ip']}:{p['port']} → TG", url=link)
            rows.append(1)
    if total_pages > 1:
        nav_count = 1
        if page > 0:
            b.button(text="◀️", callback_data=f"proxy:page:{page - 1}")
            nav_count += 1
        b.button(text=f"{page + 1}/{total_pages}", callback_data="proxy:noop")
        if page < total_pages - 1:
            b.button(text="▶️", callback_data=f"proxy:page:{page + 1}")
            nav_count += 1
        rows.append(nav_count)
    b.button(text="🔄 Обновить", callback_data="proxy:refresh")
    b.button(text="🔍 Свой прокси", callback_data="menu:check")
    b.button(text="🏠 Главное меню", callback_data="menu:home")
    rows.append(3)
    b.adjust(*rows)
    return b.as_markup()


def kb_cancel_check() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="❌ Отмена", callback_data="check:cancel")
    return b.as_markup()


# ═══════════════════════════════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ПРОКСИ
# ═══════════════════════════════════════════════════════════════
def _country_flag(code: str) -> str:
    if not code:
        return "🏳️"
    if code in COUNTRY_FLAGS:
        return COUNTRY_FLAGS[code]
    if len(code) == 2 and code.isalpha():
        return "".join(chr(0x1F1E6 + ord(c.upper()) - ord("A")) for c in code)
    return "🏳️"


def _make_tg_proxy_link(proxy: Dict) -> Optional[str]:
    if proxy["type"] != "socks5":
        return None
    return f"https://t.me/socks?server={quote(proxy['ip'])}&port={proxy['port']}"


async def _get_cache_age_minutes() -> Optional[float]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT MAX(checked_at) AS last FROM free_proxies") as cur:
            row = await cur.fetchone()
            if not row or not row["last"]:
                return None
            try:
                last = datetime.fromisoformat(row["last"])
            except ValueError:
                last = datetime.strptime(row["last"], "%Y-%m-%d %H:%M:%S")
            return (datetime.utcnow() - last).total_seconds() / 60


async def _save_proxies(proxies: List[Dict]):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM free_proxies")
        await db.executemany(
            "INSERT OR IGNORE INTO free_proxies "
            "(ip, port, proxy_type, country_code, country_name, latency_ms) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(p["ip"], p["port"], p["type"], p.get("country_code", ""),
              p.get("country_name", ""), p["latency_ms"]) for p in proxies],
        )
        await db.commit()


async def _load_proxies() -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT ip, port, proxy_type, country_code, country_name, latency_ms "
            "FROM free_proxies ORDER BY latency_ms ASC"
        ) as cur:
            rows = await cur.fetchall()
            return [{"ip": r["ip"], "port": r["port"], "type": r["proxy_type"],
                     "country_code": r["country_code"] or "", "country_name": r["country_name"] or "",
                     "latency_ms": r["latency_ms"]} for r in rows]


async def _fetch_source(session: aiohttp.ClientSession, src: Dict) -> List[Dict]:
    try:
        async with session.get(src["url"], timeout=15) as resp:
            if resp.status != 200:
                return []
            text = await resp.text()
    except Exception:
        return []
    proxies = []
    for line in text.splitlines():
        line = line.strip()
        m = PROXY_RE.match(line)
        if not m:
            continue
        ip, port = m.group(1), int(m.group(2))
        if not (0 < port <= 65535):
            continue
        proxies.append({"ip": ip, "port": port, "type": src["type"]})
    return proxies


async def _fetch_all_sources() -> List[Dict]:
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(*[_fetch_source(session, src) for src in PROXY_SOURCES], return_exceptions=True)
    all_proxies, seen, unique = [], set(), []
    for res in results:
        if isinstance(res, list):
            all_proxies.extend(res)
    for p in all_proxies:
        key = (p["ip"], p["port"], p["type"])
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


async def _geolocate_batch(session: aiohttp.ClientSession, ips: List[str]) -> Dict[str, Dict]:
    if not ips:
        return {}
    payload = [{"query": ip, "fields": "query,countryCode,country,status"} for ip in ips]
    result: Dict[str, Dict] = {}
    try:
        async with session.post(GEO_API_URL, json=payload, timeout=15) as resp:
            if resp.status != 200:
                return result
            data = await resp.json()
            for item in data:
                if item.get("status") != "success":
                    continue
                ip = item.get("query")
                if not ip:
                    continue
                result[ip] = {
                    "country_code": item.get("countryCode", "") or "",
                    "country_name": item.get("country", "") or "",
                }
    except Exception:
        pass
    return result


async def _geolocate_and_filter(proxies: List[Dict]) -> List[Dict]:
    if not proxies:
        return []
    unique_ips = list({p["ip"] for p in proxies})
    geo_data: Dict[str, Dict] = {}
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(unique_ips), GEO_BATCH_SIZE):
            batch = unique_ips[i: i + GEO_BATCH_SIZE]
            geo_data.update(await _geolocate_batch(session, batch))
            if i + GEO_BATCH_SIZE < len(unique_ips):
                await asyncio.sleep(GEO_RATE_LIMIT_DELAY)
    filtered = []
    for p in proxies:
        geo = geo_data.get(p["ip"], {})
        cc = geo.get("country_code", "")
        if cc in EXCLUDED_COUNTRIES:
            continue
        p["country_code"] = cc
        p["country_name"] = geo.get("country_name", "")
        filtered.append(p)
    return filtered


async def _check_one_proxy(proxy: Dict, semaphore: asyncio.Semaphore) -> Optional[Dict]:
    async with semaphore:
        ptype   = proxy["type"]
        timeout = aiohttp.ClientTimeout(total=PROXY_CHECK_TIMEOUT)
        loop    = asyncio.get_event_loop()
        try:
            start = loop.time()
            if ptype in ("http", "https"):
                proxy_url = f"http://{proxy['ip']}:{proxy['port']}"
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(PROXY_TEST_URL, proxy=proxy_url) as resp:
                        if resp.status != 200:
                            return None
                        await resp.read()
            elif ptype == "socks5":
                if not SOCKS_AVAILABLE:
                    return None
                connector = ProxyConnector.from_url(f"socks5://{proxy['ip']}:{proxy['port']}")
                async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                    async with session.get(PROXY_TEST_URL) as resp:
                        if resp.status != 200:
                            return None
                        await resp.read()
            else:
                return None
            return {**proxy, "latency_ms": int((loop.time() - start) * 1000)}
        except Exception:
            return None


async def _check_proxies(proxies: List[Dict]) -> List[Dict]:
    sample    = proxies[:PROXY_MAX_TO_CHECK]
    semaphore = asyncio.Semaphore(PROXY_CHECK_CONCURRENCY)
    results   = await asyncio.gather(*[_check_one_proxy(p, semaphore) for p in sample], return_exceptions=True)
    return [r for r in results if isinstance(r, dict)]


_refresh_lock = asyncio.Lock()


async def get_free_proxies(force_refresh: bool = False) -> List[Dict]:
    if not force_refresh:
        age = await _get_cache_age_minutes()
        if age is not None and age < PROXY_CACHE_MINUTES:
            return await _load_proxies()
    async with _refresh_lock:
        if not force_refresh:
            age = await _get_cache_age_minutes()
            if age is not None and age < PROXY_CACHE_MINUTES:
                return await _load_proxies()
        raw = await _fetch_all_sources()
        if not raw:
            return await _load_proxies()
        alive = await _check_proxies(raw)
        if not alive:
            return await _load_proxies()
        filtered = await _geolocate_and_filter(alive)
        filtered.sort(key=lambda p: p["latency_ms"])
        await _save_proxies(filtered)
        return filtered


USER_PROXY_RE = re.compile(
    r"^(?:(?P<scheme>https?|socks5|socks4)://)?"
    r"(?P<ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    r"[:\s]+"
    r"(?P<port>\d{1,5})$"
)


def parse_user_proxy(text: str) -> Optional[Dict]:
    text = text.strip().lower()
    m = USER_PROXY_RE.match(text)
    if not m:
        return None
    ip, port = m.group("ip"), int(m.group("port"))
    if not (0 < port <= 65535):
        return None
    scheme = m.group("scheme") or "http"
    if scheme == "socks4":
        scheme = "socks5"
    if scheme == "https":
        scheme = "http"
    return {"ip": ip, "port": port, "type": scheme}


async def check_user_proxy(proxy: Dict) -> Optional[Dict]:
    semaphore = asyncio.Semaphore(1)
    types_to_try = [proxy["type"]]
    if proxy["type"] == "http":
        types_to_try.append("socks5")
    alive = None
    for ptype in types_to_try:
        result = await _check_one_proxy({**proxy, "type": ptype}, semaphore)
        if result:
            alive = result
            break
    if not alive:
        return None
    async with aiohttp.ClientSession() as session:
        geo = await _geolocate_batch(session, [alive["ip"]])
    info = geo.get(alive["ip"], {})
    alive["country_code"] = info.get("country_code", "")
    alive["country_name"] = info.get("country_name", "")
    return alive


def _format_proxy_page(proxies: List[Dict], page: int,
                       per_page: int = PROXY_PER_PAGE) -> Tuple[str, int, List[Dict], int]:
    if not proxies:
        return ("😔 Не удалось получить рабочие прокси.\n\nНажмите «🔄 Обновить».", 1, [], 0)
    total_pages = max(1, (len(proxies) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    chunk = proxies[start: start + per_page]
    socks_count = sum(1 for p in proxies if p["type"] == "socks5")
    http_count = len(proxies) - socks_count

    # Убеждаемся, что текст не пустой
    lines = [
        "🌐 <b>Бесплатные прокси</b>\n",
        f"Всего: <b>{len(proxies)}</b> (SOCKS5: {socks_count}, HTTP: {http_count}) · "
        f"страница <b>{page + 1}</b>/<b>{total_pages}</b>\n",
    ]
    for i, p in enumerate(chunk, start=start + 1):
        flag = _country_flag(p["country_code"])
        country = p["country_code"] or "??"
        lines.append(
            f"<b>{i}.</b> {flag} <code>{p['ip']}:{p['port']}</code>\n"
            f"    └ {p['type'].upper()} · {country} · {p['latency_ms']} мс"
        )
    lines.append(
        "\n📲 Кнопки ниже — подключение SOCKS5 в Telegram одним нажатием.\n"
        "⚠️ <b>Важно:</b> бесплатные прокси не шифруют трафик. Не вводите через них пароли.\n"
        "🔒 Для надёжной защиты — оформите <b>KageriVPN</b>."
    )
    result_text = "\n".join(lines)
    # Убеждаемся, что текст не пустой
    if not result_text or result_text.isspace():
        result_text = "🌐 <b>Бесплатные прокси</b>\n\nНет доступных прокси."
    return result_text, total_pages, chunk, start

# ═══════════════════════════════════════════════════════════════
# ОТПРАВКА СООБЩЕНИЙ С КАРТИНКАМИ
# ═══════════════════════════════════════════════════════════════
async def send_with_photo(target, photo_path, text: str, reply_markup=None, edit: bool = False):
    msg = target.message if isinstance(target, CallbackQuery) else target
    photo_path = Path(photo_path)
    if edit and isinstance(target, CallbackQuery):
        try:
            await msg.delete()
        except Exception:
            pass
    if not photo_path.exists():
        return await msg.answer(text, reply_markup=reply_markup)
    photo = FSInputFile(str(photo_path))
    if len(text) <= 1024:
        return await msg.answer_photo(photo, caption=text, reply_markup=reply_markup)
    await msg.answer_photo(photo)
    return await msg.answer(text, reply_markup=reply_markup)


async def safe_edit_or_answer(call: CallbackQuery, text: str, reply_markup=None,
                               photo: Path | None = None, disable_web_page_preview: bool = True):
    msg = call.message
    if msg.photo or (msg.caption and len(msg.caption) > 0):
        try:
            await msg.delete()
        except Exception:
            pass
        if photo and photo.exists():
            return await send_with_photo(call, photo, text, reply_markup)
        return await msg.answer(text, reply_markup=reply_markup,
                                disable_web_page_preview=disable_web_page_preview)
    try:
        return await msg.edit_text(text, reply_markup=reply_markup,
                                   disable_web_page_preview=disable_web_page_preview)
    except Exception:
        if photo and photo.exists():
            return await send_with_photo(call, photo, text, reply_markup)
        return await msg.answer(text, reply_markup=reply_markup,
                                disable_web_page_preview=disable_web_page_preview)


# ═══════════════════════════════════════════════════════════════
# MIDDLEWARE
# ═══════════════════════════════════════════════════════════════
class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        u = event.from_user
        if not u:
            return await handler(event, data)
        db_user = await get_user(u.id)
        if not db_user:
            ref = None
            if isinstance(event, Message) and event.text and event.text.startswith("/start "):
                arg = event.text.split()[1]
                if arg.startswith("ref_"):
                    try:
                        ref = int(arg[4:])
                    except ValueError:
                        pass
            await create_user(u.id, u.username, u.full_name, ref)
            db_user = await get_user(u.id)
        if db_user and db_user["is_banned"]:
            if isinstance(event, Message):
                await event.answer("🚫 Вы заблокированы.")
            else:
                await event.answer("🚫 Заблокировано.", show_alert=True)
            return
        data["db_user"] = db_user
        return await handler(event, data)


# ═══════════════════════════════════════════════════════════════
# ХЕНДЛЕРЫ
# ═══════════════════════════════════════════════════════════════
router = Router()


def is_admin(event, db_user=None) -> bool:
    uid = event.from_user.id
    return uid == SUPER_ADMIN_ID or bool(db_user and db_user["is_admin"])


# ── FSM States ───────────────────────────────────────────────────
class S(StatesGroup):
    p_name = State(); p_url = State(); p_user = State(); p_pass = State()
    p_inb  = State(); p_sub = State(); p_loc  = State(); p_flag = State()
    u_id   = State()
    bcast  = State()
    pr_code = State(); pr_disc = State(); pr_days = State(); pr_uses = State()
    pr_type = State(); pr_subdays = State(); pr_panel = State()
    promo  = State()
    kg_count = State()
    support_msg   = State()
    support_reply = State()
    add_admin_id  = State()
    # Прокси
    check_proxy = State()


# ── Тексты ───────────────────────────────────────────────────────
WELCOME_TEXT = (
    "👋 Привет, <b>{name}</b>!\n\n"
    "🛡 <b>KageriVPN</b> — быстрый и стабильный VPN, который просто работает.\n\n"
    "⚡ <b>Что мы предлагаем:</b>\n"
    "• 🌍 Серверы в нескольких странах\n"
    "• 🚀 Высокая скорость и низкий пинг\n"
    "• 🔒 VLESS + Reality протоколы\n"
    "• 📱 iOS, Android, Windows, macOS, Linux\n"
    "• 🆓 Пробный период без оплаты\n"
    "• 🌐 Бесплатные прокси внутри бота\n\n"
    "👇 <b>Выберите действие:</b>"
)

NO_SUBS_TEXT = (
    "🛡 <b>У вас пока нет активных подписок</b>\n\n"
    "🛒 Нажмите <b>Купить VPN</b> — выберите сервер и тариф\n"
    f"🆓 Или попробуйте <b>Пробный VPN</b> бесплатно ({FREE_VPN_DAYS} дн., {FREE_VPN_TRAFFIC} GB)"
)

BUY_INTRO_TEXT = (
    "🌍 <b>Выберите сервер</b>\n\n"
    "🟢 Свободно  🟡 Средне  🔴 Загружено\n\n"
    "👇 Нажмите на нужный сервер:"
)

FREE_VPN_INTRO = (
    f"🆓 <b>Бесплатный пробный VPN</b>\n\n"
    f"⏱ Срок: <b>{FREE_VPN_DAYS} дня</b>\n"
    f"📦 Трафик: <b>{FREE_VPN_TRAFFIC} GB</b>\n"
    "🌍 Любой сервер на выбор\n\n"
    "⚠️ Активировать можно только <u>один раз</u>\n\n"
    "👇 <b>Выберите сервер:</b>"
)

ADMIN_INTRO = (
    "⚙️ <b>Панель администратора</b>\n\n"
    "📊 Статистика · 📡 Панели · 👥 Пользователи · 📢 Рассылка\n"
)
SUPER_ADMIN_EXTRA = "🎁 Промокоды · 🔑 Генератор ключей · 👮 Управление админами"


# ── /start, /help, /menu ─────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(msg: Message, db_user=None):
    try:
        sent = await msg.answer("⏳", reply_markup=ReplyKeyboardRemove())
        await sent.delete()
    except Exception:
        pass
    await send_with_photo(msg, IMG_MENU, WELCOME_TEXT.format(name=msg.from_user.full_name),
                          reply_markup=kb_main(is_admin(msg, db_user)))


@router.message(Command("help"))
async def cmd_help(msg: Message, db_user=None):
    await msg.answer(
        "ℹ️ <b>Помощь</b>\n\n/start /menu — Главное меню\n/subs — Мои подписки\n"
        "/buy — Купить VPN\n/proxy — Бесплатные прокси\n/admin — Панель администратора",
        reply_markup=kb_home())


@router.message(Command("menu"))
async def cmd_menu(msg: Message, db_user=None):
    await send_with_photo(msg, IMG_MENU, WELCOME_TEXT.format(name=msg.from_user.full_name),
                          reply_markup=kb_main(is_admin(msg, db_user)))


@router.message(Command("proxy"))
async def cmd_proxy(msg: Message):
    loading_msg = await msg.answer("⏳ <b>Загружаю список прокси…</b>\n\nЕсли кэш устарел — займёт ~1 мин.")

    proxies = await get_free_proxies()
    text, total, chunk, offset = _format_proxy_page(proxies, page=0)

    await loading_msg.delete()
    await msg.answer(text, reply_markup=kb_proxy_list(chunk, 0, total, offset))

    
# ── Главное меню ─────────────────────────────────────────────────
@router.callback_query(F.data == "menu:home")
async def cb_main_menu(call: CallbackQuery, state: FSMContext, db_user=None):
    await state.clear()
    await send_with_photo(call, IMG_MENU, WELCOME_TEXT.format(name=call.from_user.full_name),
                          reply_markup=kb_main(is_admin(call, db_user)), edit=True)
    await call.answer()


@router.callback_query(F.data == "menu:rules")
async def cb_menu_rules(call: CallbackQuery):
    await safe_edit_or_answer(call, RULES_TEXT, reply_markup=kb_home(), disable_web_page_preview=True)
    await call.answer()


# ── Баланс / рефералка / поддержка ───────────────────────────────
@router.callback_query(F.data == "menu:balance")
async def show_balance(call: CallbackQuery, db_user=None):
    if not db_user:
        return await call.answer("❌ Ошибка", show_alert=True)
    await safe_edit_or_answer(call,
        f"💰 <b>Ваш баланс</b>\n\n💵 На счету: <b>{db_user['balance']:.2f}₽</b>\n\n"
        "Оплата подписок — через ⭐ Telegram Stars или 💳 СБП.",
        reply_markup=kb_home())
    await call.answer()


@router.callback_query(F.data == "menu:support")
async def show_support(call: CallbackQuery, state: FSMContext):
    await state.set_state(S.support_msg)
    await safe_edit_or_answer(call,
        "💬 <b>Служба поддержки</b>\n\n✏️ Опишите проблему:",
        reply_markup=kb_back("menu:home"))
    await call.answer()


@router.message(S.support_msg)
async def support_send(msg: Message, state: FSMContext):
    await state.clear()
    user = msg.from_user
    admin_ids = await get_all_admins()
    info = (f"📩 <b>Обращение в поддержку</b>\n\n"
            f"👤 {user.full_name} | @{user.username or 'нет'} | <code>{user.id}</code>\n\n"
            f"💬 {msg.text}")
    for aid in admin_ids:
        try:
            await msg.bot.send_message(aid, info, reply_markup=_kb_support_reply(user.id))
        except Exception:
            pass
    await msg.answer("✅ Сообщение отправлено! Ответим в течение 24 ч.", reply_markup=kb_home())


def _kb_support_reply(user_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="↩️ Ответить", callback_data=f"support:reply:{user_id}")
    return b.as_markup()


@router.callback_query(F.data.startswith("support:reply:"))
async def support_reply_start(call: CallbackQuery, state: FSMContext, db_user=None):
    if not is_admin(call, db_user):
        return await call.answer("⛔", show_alert=True)
    target_id = int(call.data.split(":")[-1])
    await state.update_data(support_target=target_id)
    await state.set_state(S.support_reply)
    await call.message.answer(f"✏️ Ответ пользователю <code>{target_id}</code>:",
                               reply_markup=kb_back("menu:home"))
    await call.answer()


@router.message(S.support_reply)
async def support_reply_send(msg: Message, state: FSMContext, db_user=None):
    if not is_admin(msg, db_user):
        return
    data = await state.get_data()
    await state.clear()
    target_id = data.get("support_target")
    if not target_id:
        return await msg.answer("❌ Ошибка.")
    try:
        await msg.bot.send_message(target_id, f"📬 <b>Ответ поддержки</b>\n\n{msg.text}")
        await msg.answer("✅ Ответ отправлен.")
    except Exception:
        await msg.answer("❌ Не удалось отправить.")


@router.callback_query(F.data == "menu:ref")
async def show_ref(call: CallbackQuery):
    me   = await call.bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{call.from_user.id}"
    cnt  = await db_fetchone("SELECT COUNT(*) FROM users WHERE referral_id=?", (call.from_user.id,))
    invited = cnt[0] if cnt else 0
    await safe_edit_or_answer(call,
        f"👥 <b>Реферальная программа</b>\n\n"
        f"🎁 50₽ за каждого приглашённого (после первой покупки)\n"
        f"👤 Приглашено: <b>{invited}</b>\n\n"
        f"🔗 Ваша ссылка:\n<code>{link}</code>",
        reply_markup=kb_home())
    await call.answer()


# ── Подписки ─────────────────────────────────────────────────────
@router.message(Command("subs"))
async def my_subs(msg: Message):
    subs = await get_active_subscriptions(msg.from_user.id)
    if not subs:
        return await send_with_photo(msg, IMG_SUBS, NO_SUBS_TEXT, reply_markup=kb_home())
    await send_with_photo(msg, IMG_SUBS,
        f"🛡 <b>Ваши подписки</b> ({len(subs)} активных)\n\nНажмите для деталей:",
        reply_markup=kb_subs_list(subs))


@router.callback_query(F.data == "menu:my_subs")
@router.callback_query(F.data == "my_subs")
async def my_subs_cb(call: CallbackQuery):
    subs = await get_active_subscriptions(call.from_user.id)
    if not subs:
        await send_with_photo(call, IMG_SUBS, NO_SUBS_TEXT, reply_markup=kb_home(), edit=True)
    else:
        await send_with_photo(call, IMG_SUBS,
            f"🛡 <b>Ваши подписки</b> ({len(subs)} активных)\n\nНажмите для деталей:",
            reply_markup=kb_subs_list(subs), edit=True)
    await call.answer()


@router.callback_query(F.data.startswith("sub:view:"))
async def sub_view(call: CallbackQuery):
    sid = int(call.data.split(":")[-1])
    sub = await get_subscription(sid)
    if not sub or sub["user_id"] != call.from_user.id:
        return await call.answer("❌ Не найдено", show_alert=True)
    exp   = datetime.strptime(sub["expires_at"], "%Y-%m-%d %H:%M:%S")
    left  = (exp - datetime.now()).days
    panel = await get_panel(sub["panel_id"])
    traf  = f"{sub['traffic_gb']} GB" if sub["traffic_gb"] > 0 else "♾ Безлимит"
    await safe_edit_or_answer(call,
        f"🛡 <b>Подписка #{sid}</b>\n\n"
        f"📡 {panel['flag'] if panel else '🌍'} {panel['name'] if panel else 'N/A'}\n"
        f"📦 {sub['plan_key'].replace('_',' ').title()}\n"
        f"📊 Трафик: {traf}\n"
        f"📅 До: {sub['expires_at'][:10]}\n"
        f"⏳ Осталось: {left} дн.\n"
        f"🔹 {'✅ Активна' if left > 0 else '⛔ Истекла'}",
        reply_markup=kb_sub(sid))
    await call.answer()


@router.callback_query(F.data.startswith("sub:config:"))
async def sub_config(call: CallbackQuery):
    sid = int(call.data.split(":")[-1])
    sub = await get_subscription(sid)
    if not sub or sub["user_id"] != call.from_user.id:
        return await call.answer("❌ Не найдено", show_alert=True)
    if not sub["config_link"]:
        return await call.answer("⚠️ Конфиг недоступен.", show_alert=True)
    await call.message.answer(
        f"🔗 <b>Ссылка на подписку</b>\n\n<code>{sub['config_link']}</code>\n\n"
        "1. Скопируйте ссылку\n2. Откройте Hiddify / v2rayNG / Streisand\n"
        "3. Добавьте подписку → Обновите список")
    await call.answer()


@router.callback_query(F.data.startswith("sub:traffic:"))
async def sub_traffic(call: CallbackQuery):
    sid   = int(call.data.split(":")[-1])
    sub   = await get_subscription(sid)
    panel = await get_panel(sub["panel_id"]) if sub else None
    if not sub or sub["user_id"] != call.from_user.id or not panel:
        return await call.answer("❌ Не найдено", show_alert=True)
    await call.answer("📊 Загружаю…")
    stats = await xui(panel).get_client_stats(sub["client_email"])
    if not stats:
        return await call.message.answer("⚠️ Нет данных о трафике.")
    up, down = stats.get("up", 0) / 1024**3, stats.get("down", 0) / 1024**3
    tot, lim = up + down, sub["traffic_gb"]
    await call.message.answer(
        f"📊 <b>Трафик</b>\n⬆️ {up:.2f} GB  ⬇️ {down:.2f} GB  📦 {tot:.2f} GB\n"
        f"Лимит: {f'{lim} GB' if lim else '♾'}  Осталось: {f'{max(0, lim - tot):.2f} GB' if lim else '♾'}")


@router.callback_query(F.data.startswith("sub:renew:"))
async def sub_renew(call: CallbackQuery):
    sid   = int(call.data.split(":")[-1])
    sub   = await get_subscription(sid)
    panel = await get_panel(sub["panel_id"]) if sub else None
    if not sub or sub["user_id"] != call.from_user.id or not panel:
        return await call.answer("❌ Не найдено", show_alert=True)
    await safe_edit_or_answer(call,
        f"♻️ <b>Продление</b>\nСервер: {panel['flag']} {panel['name']}\n\nВыберите тариф:",
        reply_markup=kb_plans(panel["id"]))
    await call.answer()


# ── Смена региона ────────────────────────────────────────────────
def _format_cooldown(td: timedelta) -> str:
    total = int(td.total_seconds())
    h, rem = divmod(total, 3600)
    m, _   = divmod(rem, 60)
    return f"{h} ч. {m} мин." if h > 0 else f"{m} мин."


@router.callback_query(F.data.startswith("sub:region:"))
async def sub_region_list(call: CallbackQuery):
    sid = int(call.data.split(":")[-1])
    sub = await get_subscription(sid)
    if not sub or sub["user_id"] != call.from_user.id:
        return await call.answer("❌ Не найдено", show_alert=True)
    exp = datetime.strptime(sub["expires_at"], "%Y-%m-%d %H:%M:%S")
    if exp <= datetime.now():
        return await call.answer("⛔ Подписка истекла.", show_alert=True)
    left = region_change_cooldown_left(sub)
    if left > timedelta(0):
        return await call.answer(
            f"⏳ Можно менять раз в {REGION_CHANGE_COOLDOWN_HOURS} ч. "
            f"Через {_format_cooldown(left)}.", show_alert=True)
    panels = await get_all_panels(active_only=True)
    others = [p for p in panels if p["id"] != sub["panel_id"]]
    if not others:
        return await call.answer("😔 Других серверов нет.", show_alert=True)
    cur_panel = await get_panel(sub["panel_id"])
    b = InlineKeyboardBuilder()
    for p in others:
        b.button(text=f"{p['flag']} {p['name']} ({p['location']})",
                 callback_data=f"sub:region_pick:{sid}:{p['id']}")
    b.button(text="◀️ Отмена", callback_data=f"sub:view:{sid}")
    b.adjust(1)
    await safe_edit_or_answer(call,
        f"🌍 <b>Смена региона</b>\n\n"
        f"Текущий: {cur_panel['flag'] if cur_panel else ''} {cur_panel['name'] if cur_panel else 'N/A'}\n"
        f"⏳ Осталось: {(exp - datetime.now()).days} дн.\n\n"
        f"ℹ️ Срок не продлевается. Менять раз в {REGION_CHANGE_COOLDOWN_HOURS} ч.\n\n"
        "👇 Выберите новый сервер:", reply_markup=b.as_markup())
    await call.answer()


@router.callback_query(F.data.startswith("sub:region_pick:"))
async def sub_region_confirm(call: CallbackQuery):
    parts = call.data.split(":")
    sid, new_pid = int(parts[2]), int(parts[3])
    sub = await get_subscription(sid)
    if not sub or sub["user_id"] != call.from_user.id:
        return await call.answer("❌ Не найдено", show_alert=True)
    new_panel = await get_panel(new_pid)
    if not new_panel or not new_panel["is_active"]:
        return await call.answer("❌ Сервер недоступен", show_alert=True)
    exp = datetime.strptime(sub["expires_at"], "%Y-%m-%d %H:%M:%S")
    b = InlineKeyboardBuilder()
    b.button(text="✅ Подтвердить", callback_data=f"sub:region_go:{sid}:{new_pid}")
    b.button(text="◀️ Назад", callback_data=f"sub:region:{sid}")
    b.adjust(1)
    await safe_edit_or_answer(call,
        f"🌍 <b>Подтверждение</b>\n\n"
        f"Новый сервер: {new_panel['flag']} {new_panel['name']}\n"
        f"Осталось: {(exp - datetime.now()).days} дн.\n\nПродолжить?",
        reply_markup=b.as_markup())
    await call.answer()


@router.callback_query(F.data.startswith("sub:region_go:"))
async def sub_region_execute(call: CallbackQuery):
    parts = call.data.split(":")
    sid, new_pid = int(parts[2]), int(parts[3])
    sub = await get_subscription(sid)
    if not sub or sub["user_id"] != call.from_user.id:
        return await call.answer("❌ Не найдено", show_alert=True)
    exp = datetime.strptime(sub["expires_at"], "%Y-%m-%d %H:%M:%S")
    if exp <= datetime.now():
        return await call.answer("⛔ Подписка истекла.", show_alert=True)
    left = region_change_cooldown_left(sub)
    if left > timedelta(0):
        return await call.answer(f"⏳ Подождите {_format_cooldown(left)}.", show_alert=True)
    await call.answer("🌍 Переношу…")
    result = await migrate_subscription(sid, new_pid)
    if not result:
        return await safe_edit_or_answer(call,
            "❌ <b>Не удалось сменить регион</b>\n\nПопробуйте другой сервер.",
            reply_markup=kb_sub(sid))
    days_left = (datetime.strptime(result["expires_at"], "%Y-%m-%d %H:%M:%S") - datetime.now()).days
    await safe_edit_or_answer(call,
        f"✅ <b>Регион изменён</b>\n\n"
        f"📡 {result['flag']} {result['panel_name']}\n"
        f"📅 До: {result['expires_at'][:10]}  ⏳ {days_left} дн.\n\n"
        f"🔗 Новая ссылка:\n<code>{result['config_link']}</code>\n\n"
        "Обновите подписку в Hiddify / v2rayNG / Streisand.",
        reply_markup=kb_sub(sid))


# ── Покупка ──────────────────────────────────────────────────────
@router.message(Command("buy"))
async def buy_cmd(msg: Message):
    panels = await get_all_panels(active_only=True)
    if not panels:
        return await msg.answer("😔 Серверы временно недоступны.", reply_markup=kb_home())
    await msg.answer(BUY_INTRO_TEXT, reply_markup=kb_panels(panels))


@router.callback_query(F.data == "menu:buy")
@router.callback_query(F.data == "buy_vpn")
async def show_panels_handler(call: CallbackQuery):
    panels = await get_all_panels(active_only=True)
    if not panels:
        await safe_edit_or_answer(call, "😔 Серверы временно недоступны.", reply_markup=kb_home())
        return await call.answer()
    await safe_edit_or_answer(call, BUY_INTRO_TEXT, reply_markup=kb_panels(panels))
    await call.answer()


@router.callback_query(F.data.startswith("panel:"))
async def select_panel(call: CallbackQuery):
    pid   = int(call.data.split(":")[1])
    panel = await get_panel(pid)
    if not panel or not panel["is_active"]:
        return await call.answer("❌ Сервер недоступен", show_alert=True)
    load = int(panel["current_clients"] / max(panel["max_clients"], 1) * 100)
    dot  = "🟢" if load < 60 else ("🟡" if load < 85 else "🔴")
    await safe_edit_or_answer(call,
        f"📡 <b>{panel['flag']} {panel['name']}</b>\n"
        f"🌍 {panel['location']}  {dot} {load}%\n\n"
        "📅 <b>Выберите тариф:</b>",
        reply_markup=kb_plans(pid))
    await call.answer()


@router.callback_query(F.data == "back_panels")
async def back_panels(call: CallbackQuery):
    panels = await get_all_panels(active_only=True)
    await safe_edit_or_answer(call, BUY_INTRO_TEXT, reply_markup=kb_panels(panels))
    await call.answer()


@router.callback_query(F.data.startswith("buy:"))
async def select_pay_method(call: CallbackQuery):
    _, pid_s, plan_key = call.data.split(":")
    pid, plan, panel = int(pid_s), SUBSCRIPTION_PLANS.get(plan_key), await get_panel(int(pid_s))
    if not plan or not panel:
        return await call.answer("❌ Ошибка", show_alert=True)
    traf      = TRAFFIC_LIMITS.get(plan_key, 50)
    traf_text = f"{traf} GB" if traf > 0 else "♾ Безлимит"
    await safe_edit_or_answer(call,
        f"📋 <b>Подтверждение заказа</b>\n\n"
        f"📡 {panel['flag']} {panel['name']}\n"
        f"📅 {plan['name']} ({plan['days']} дн.)\n"
        f"📦 {traf_text}\n"
        f"💰 ⭐ {plan['stars']} Stars или {plan['price']}₽\n\n" + RULES_TEXT,
        reply_markup=kb_legal(pid, plan_key), disable_web_page_preview=True)
    await call.answer()


@router.callback_query(F.data.startswith("legal:accept:"))
async def legal_accept_buy(call: CallbackQuery):
    parts    = call.data.split(":")
    pid, plan_key = int(parts[2]), parts[3]
    plan, panel = SUBSCRIPTION_PLANS.get(plan_key), await get_panel(pid)
    if not plan or not panel:
        return await call.answer("❌ Ошибка", show_alert=True)
    await db_update("users", call.from_user.id, id_col="tg_id", rules_accepted=1)
    await send_with_photo(call, IMG_PAYMENTS,
        f"💳 <b>Оплата</b>\n\n📡 {panel['flag']} {panel['name']}\n"
        f"📅 {plan['name']}\n\n"
        f"⭐ Telegram Stars — {plan['stars']} ⭐  (мгновенно)\n"
        f"💳 СБП / карта — {plan['price']}₽  (после нажмите «Я оплатил»)\n\n"
        "👇 Выберите способ оплаты:",
        reply_markup=kb_pay(pid, plan_key), edit=True)
    await call.answer()


# ── Telegram Stars ───────────────────────────────────────────────
@router.callback_query(F.data.startswith("pay:stars:"))
async def pay_stars(call: CallbackQuery):
    parts    = call.data.split(":")
    pid, plan_key = int(parts[2]), parts[3]
    plan = SUBSCRIPTION_PLANS[plan_key]
    await call.message.answer_invoice(
        title=f"VPN — {plan['name']}",
        description=f"Подписка KageriVPN на {plan['name']}.",
        payload=f"stars:{pid}:{plan_key}:{call.from_user.id}",
        currency="XTR",
        prices=[LabeledPrice(label=plan["name"], amount=plan["stars"])],
    )
    await call.answer()


@router.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)


@router.message(F.successful_payment)
async def on_payment_ok(msg: Message, db_user=None):
    payload = msg.successful_payment.invoice_payload
    parts   = payload.split(":")
    if parts[0] != "stars":
        return
    pid, plan_key, uid = int(parts[1]), parts[2], int(parts[3])
    await msg.answer("⏳ Создаю подписку…")
    result = await make_subscription(uid, pid, plan_key)
    if not result:
        return await msg.answer(
            "❌ <b>Ошибка создания подписки</b>\nНапишите в поддержку.", reply_markup=kb_home())
    plan   = SUBSCRIPTION_PLANS[plan_key]
    pay_id = await create_payment(uid, plan["stars"], "XTR", "stars", plan_key, pid)
    await db_update("payments", pay_id, status="completed",
                    subscription_id=result["sub_id"], completed_at=str(datetime.now()))
    await msg.answer(
        f"✅ <b>Подписка активирована!</b>\n\n"
        f"📡 {result['flag']} {result['panel_name']}\n"
        f"📅 До: {result['expires_at'][:10]}\n\n"
        f"🔗 Ссылка:\n<code>{result['config_link']}</code>\n\n"
        "Hiddify / v2rayNG / Streisand → добавить подписку → обновить\n\n"
        "Спасибо! 💙", reply_markup=kb_home())


# ── Platega (СБП / карта) ────────────────────────────────────────
@router.callback_query(F.data.startswith("pay:platega:"))
async def pay_platega(call: CallbackQuery, db_user=None):
    parts    = call.data.split(":")
    pid, plan_key = int(parts[2]), parts[3]
    plan, panel = SUBSCRIPTION_PLANS.get(plan_key), await get_panel(pid)
    if not plan or not panel:
        return await call.answer("❌ Ошибка", show_alert=True)
    await call.answer("⏳ Создаю платёж…")
    pay_id = await create_payment(call.from_user.id, plan["price"], "RUB", "platega", plan_key, pid)
    tx = await platega.create_transaction(amount=plan["price"],
                                           description=f"VPN — {plan['name']}", payload=str(pay_id))
    tx_id        = tx.get("transactionId") if tx else None
    redirect_url = tx.get("redirect") if tx else None
    if not tx_id or not redirect_url:
        await db_update("payments", pay_id, status="failed")
        return await safe_edit_or_answer(call,
            "❌ Платёжная система недоступна. Попробуйте Stars.", reply_markup=kb_home())
    await db_update("payments", pay_id, payment_id=tx_id)
    await safe_edit_or_answer(call,
        f"💳 <b>Оплата через СБП</b>\n\n📡 {panel['flag']} {panel['name']}\n"
        f"📅 {plan['name']}  💰 {plan['price']}₽\n\n"
        "1️⃣ Нажмите «Перейти к оплате»\n"
        "2️⃣ Оплатите\n3️⃣ Нажмите «Я оплатил»",
        reply_markup=kb_platega_payment(pay_id, redirect_url))


@router.callback_query(F.data.startswith("platega:check:"))
async def platega_check(call: CallbackQuery):
    pay_id = int(call.data.split(":")[-1])
    pay    = await db_fetchone("SELECT * FROM payments WHERE id=?", (pay_id,))
    if not pay:
        return await call.answer("❌ Платёж не найден", show_alert=True)
    if pay["user_id"] != call.from_user.id:
        return await call.answer("⛔ Не ваш платёж", show_alert=True)
    if pay["status"] == "completed":
        return await call.answer("✅ Уже подтверждён.", show_alert=True)
    if pay["status"] == "failed":
        return await call.answer("❌ Платёж отменён. Создайте новый.", show_alert=True)
    tx_id = pay["payment_id"]
    if not tx_id:
        return await call.answer("⚠️ Обратитесь в поддержку.", show_alert=True)
    await call.answer("🔍 Проверяю…")
    info   = await platega.get_status(tx_id)
    if not info:
        return await call.message.answer("⚠️ Попробуйте через минуту.")
    status = str(info.get("status", "")).upper()
    if status in PLATEGA_STATUS_OK:
        await activate_after_platega(call.bot, pay_id)
        try:
            await safe_edit_or_answer(call, "✅ Оплата подтверждена!", reply_markup=kb_home())
        except Exception:
            pass
        return
    if status in PLATEGA_STATUS_FAILED:
        await db_update("payments", pay_id, status="failed")
        return await safe_edit_or_answer(call,
            f"❌ Платёж не прошёл ({status}). Деньги не списаны.", reply_markup=kb_home())
    await call.message.answer("⏳ Ещё в обработке. Подождите минуту и проверьте снова.")


@router.callback_query(F.data.startswith("platega:cancel:"))
async def platega_cancel(call: CallbackQuery):
    pay_id = int(call.data.split(":")[-1])
    pay    = await db_fetchone("SELECT * FROM payments WHERE id=?", (pay_id,))
    if not pay or pay["user_id"] != call.from_user.id:
        return await call.answer("❌ Не найдено", show_alert=True)
    if pay["status"] == "completed":
        return await call.answer("✅ Уже подтверждён, отменить нельзя.", show_alert=True)
    await db_update("payments", pay_id, status="failed")
    await safe_edit_or_answer(call, "❌ Платёж отменён.", reply_markup=kb_home())
    await call.answer()


# ── Бесплатный VPN ───────────────────────────────────────────────
@router.callback_query(F.data == "menu:free")
async def free_vpn_entry(call: CallbackQuery, db_user=None):
    if not db_user:
        return await call.answer("❌ Ошибка", show_alert=True)
    if db_user["free_used"]:
        return await safe_edit_or_answer(call,
            "😔 Пробная подписка уже использована.\n\nТарифы от 150 ⭐ или 169₽:",
            reply_markup=InlineKeyboardBuilder()
                .button(text="🛒 Купить VPN", callback_data="menu:buy")
                .button(text="🏠 Главное меню", callback_data="menu:home")
                .adjust(1).as_markup())
    panels = await get_all_panels(active_only=True)
    if not panels:
        return await safe_edit_or_answer(call, "😔 Серверы недоступны.", reply_markup=kb_home())
    await safe_edit_or_answer(call, FREE_VPN_INTRO, reply_markup=kb_free_panels(panels))
    await call.answer()


@router.callback_query(F.data.startswith("free:panel:"))
async def free_vpn_choose(call: CallbackQuery, db_user=None):
    if not db_user or db_user["free_used"]:
        return await call.answer("❌ Уже использована!", show_alert=True)
    pid   = int(call.data.split(":")[-1])
    panel = await get_panel(pid)
    if not panel or not panel["is_active"]:
        return await call.answer("❌ Сервер недоступен", show_alert=True)
    await safe_edit_or_answer(call,
        f"📋 {panel['flag']} {panel['name']} · {FREE_VPN_DAYS} дн. · {FREE_VPN_TRAFFIC} GB\n\n" + RULES_TEXT,
        reply_markup=kb_legal_free(pid), disable_web_page_preview=True)
    await call.answer()


@router.callback_query(F.data.startswith("legal:free:"))
async def free_vpn_activate(call: CallbackQuery, db_user=None):
    if not db_user or db_user["free_used"]:
        return await call.answer("❌ Уже использована!", show_alert=True)
    pid   = int(call.data.split(":")[-1])
    panel = await get_panel(pid)
    if not panel or not panel["is_active"]:
        return await call.answer("❌ Сервер недоступен", show_alert=True)
    await safe_edit_or_answer(call, "⏳ Активирую…")
    client = xui(panel)
    email  = f"free_{call.from_user.id}_{uuid.uuid4().hex[:6]}"
    result = await client.add_client(panel["inbound_id"], email,
                                      traffic_gb=FREE_VPN_TRAFFIC, expire_days=FREE_VPN_DAYS)
    if not result:
        return await safe_edit_or_answer(call, "❌ Ошибка сервера. Попробуйте позже.", reply_markup=kb_home())
    expires    = (datetime.now() + timedelta(days=FREE_VPN_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    config_url = client.sub_link(panel["sub_url"], email)
    await create_subscription(call.from_user.id, pid, "free", result["uuid"], email,
                               FREE_VPN_TRAFFIC, expires, config_url)
    await db_update("users", call.from_user.id, id_col="tg_id", free_used=1, rules_accepted=1)
    await safe_edit_or_answer(call,
        f"✅ <b>Пробная подписка активирована!</b>\n\n"
        f"📡 {panel['flag']} {panel['name']}\n"
        f"📅 До: {expires[:10]}\n\n"
        f"🔗 Ссылка:\n<code>{config_url}</code>\n\n"
        "Hiddify / v2rayNG / Streisand → добавить подписку 🛒",
        reply_markup=kb_home())
    await call.answer()


# ── Промокод ─────────────────────────────────────────────────────
@router.callback_query(F.data == "menu:promo")
async def promo_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(S.promo)
    await safe_edit_or_answer(call,
        "🎁 <b>Активация промокода</b>\n\n✏️ Введите промокод:",
        reply_markup=kb_back("menu:home"))
    await call.answer()


@router.message(S.promo)
async def promo_activate(msg: Message, state: FSMContext, db_user=None):
    await state.clear()
    promo_row = await get_promo(msg.text.strip())
    if not promo_row:
        return await msg.answer("❌ Промокод не найден или использован.", reply_markup=kb_home())
    await db_execute("UPDATE promo_codes SET uses=uses+1 WHERE code=?", (promo_row["code"],))
    lines = []
    if promo_row["discount_percent"]:
        lines.append(f"💸 Скидка {promo_row['discount_percent']}%")
    if promo_row["free_days"]:
        lines.append(f"📅 +{promo_row['free_days']} дней к подписке")
        subs = await get_active_subscriptions(msg.from_user.id)
        if subs:
            await extend_sub(subs[0]["id"], promo_row["free_days"])
        else:
            lines[-1] += " (применится при наличии подписки)"
    if promo_row["sub_days"]:
        panel_id = promo_row["promo_panel_id"]
        panel    = await get_panel(panel_id) if panel_id else None
        if not panel:
            panels = await get_all_panels(active_only=True)
            panel  = panels[0] if panels else None
        if not panel:
            lines.append("❌ Нет доступных серверов.")
        else:
            await msg.answer("⏳ Создаю подписку…")
            result = await make_subscription(msg.from_user.id, panel["id"], "promo",
                                              days_override=promo_row["sub_days"])
            if result:
                lines.append(
                    f"🎁 Подписка {promo_row['sub_days']} дн. активирована!\n"
                    f"📡 {result['flag']} {result['panel_name']}\n"
                    f"🔗 <code>{result['config_link']}</code>")
            else:
                lines.append("❌ Ошибка создания подписки. Обратитесь в поддержку.")
    await msg.answer("✅ <b>Промокод активирован!</b>\n\n" + "\n".join(lines or ["✨"]),
                     reply_markup=kb_home())


# ═══════════════════════════════════════════════════════════════
# ПРОКСИ — ХЕНДЛЕРЫ
# ═══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "menu:proxy")
async def cb_proxy_menu(call: CallbackQuery):
    await call.answer("⏳ Загружаю…")

    # Отправляем новое сообщение вместо редактирования
    loading_msg = await call.message.answer(
        "⏳ <b>Загружаю список прокси…</b>\n\nЕсли кэш устарел — займёт ~1 мин."
    )

    proxies = await get_free_proxies()
    text, total, chunk, offset = _format_proxy_page(proxies, page=0)

    # Удаляем сообщение о загрузке
    await loading_msg.delete()
    # Отправляем результат новым сообщением
    await call.message.answer(text, reply_markup=kb_proxy_list(chunk, 0, total, offset))


@router.callback_query(F.data.startswith("proxy:page:"))
async def cb_proxy_page(call: CallbackQuery):
    try:
        page = int(call.data.split(":")[2])
    except (ValueError, IndexError):
        page = 0
    proxies = await _load_proxies()
    text, total, chunk, offset = _format_proxy_page(proxies, page=page)
    try:
        await call.message.edit_text(text, reply_markup=kb_proxy_list(chunk, page, total, offset))
    except Exception:
        pass
    await call.answer()


@router.callback_query(F.data == "proxy:refresh")
async def cb_proxy_refresh(call: CallbackQuery):
    await call.answer("🔄 Обновляю (~1 мин.)…")
    try:
        await call.message.edit_text("🔄 <b>Обновляю список прокси…</b>\n\nЭто займёт ~1 минуту.")
    except Exception:
        pass
    proxies = await get_free_proxies(force_refresh=True)
    text, total, chunk, offset = _format_proxy_page(proxies, page=0)
    await call.message.edit_text(text, reply_markup=kb_proxy_list(chunk, 0, total, offset))


@router.callback_query(F.data == "proxy:noop")
async def cb_proxy_noop(call: CallbackQuery):
    await call.answer()


@router.callback_query(F.data == "menu:check")
async def cb_check_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(S.check_proxy)
    await call.message.edit_text(
        "🔍 <b>Проверка своего прокси</b>\n\n"
        "Форматы:\n• <code>1.2.3.4:8080</code>\n• <code>socks5://1.2.3.4:1080</code>\n\n"
        "✏️ Введите прокси:",
        reply_markup=kb_cancel_check())
    await call.answer()


@router.callback_query(F.data == "check:cancel")
async def cb_check_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await call.message.edit_text(
            WELCOME_TEXT.format(name=call.from_user.full_name), reply_markup=kb_main())
    except Exception:
        await call.message.answer(
            WELCOME_TEXT.format(name=call.from_user.full_name), reply_markup=kb_main())
    await call.answer("Отменено")


@router.message(S.check_proxy)
async def msg_check_proxy(msg: Message, state: FSMContext):
    parsed = parse_user_proxy(msg.text or "")
    if not parsed:
        return await msg.answer(
            "❌ Не удалось распознать. Пример: <code>1.2.3.4:8080</code>",
            reply_markup=kb_cancel_check())
    sent = await msg.answer(f"⏳ Проверяю <code>{parsed['ip']}:{parsed['port']}</code>…")
    await state.clear()
    result = await check_user_proxy(parsed)
    if not result:
        return await sent.edit_text(
            f"❌ <b>Прокси не работает</b>\n\n<code>{parsed['ip']}:{parsed['port']}</code>",
            reply_markup=kb_home_vpn())
    flag    = _country_flag(result["country_code"])
    country = result["country_name"] or result["country_code"] or "неизвестно"
    text    = (f"✅ <b>Прокси рабочий!</b>\n\n"
               f"📍 <code>{result['ip']}:{result['port']}</code>\n"
               f"🔌 {result['type'].upper()}\n"
               f"{flag} {country}\n"
               f"⚡ {result['latency_ms']} мс")
    builder = InlineKeyboardBuilder()
    tg_link = _make_tg_proxy_link(result)
    if tg_link:
        builder.button(text="📲 Подключить в Telegram", url=tg_link)
    builder.button(text="🔍 Проверить ещё", callback_data="menu:check")
    builder.button(text="🏠 Главное меню",  callback_data="menu:home")
    builder.adjust(1)
    await sent.edit_text(text, reply_markup=builder.as_markup())


# ═══════════════════════════════════════════════════════════════
# ГЕНЕРАТОР КЛЮЧЕЙ (суперадмин)
# ═══════════════════════════════════════════════════════════════
@router.callback_query(F.data == "adm:keygen")
async def adm_keygen_entry(call: CallbackQuery):
    if call.from_user.id != SUPER_ADMIN_ID:
        return await call.answer("⛔ Только суперадмин", show_alert=True)
    panels = await get_all_panels(active_only=True)
    if not panels:
        return await call.answer("❌ Нет активных панелей", show_alert=True)
    await safe_edit_or_answer(call, "🔑 <b>Генератор ключей</b>\n\nВыберите панель:",
                               reply_markup=kb_keygen_panels(panels))
    await call.answer()


@router.callback_query(F.data.startswith("keygen:panel:"))
async def adm_keygen_panel(call: CallbackQuery):
    if call.from_user.id != SUPER_ADMIN_ID:
        return await call.answer("⛔", show_alert=True)
    pid   = int(call.data.split(":")[-1])
    panel = await get_panel(pid)
    if not panel:
        return await call.answer("❌ Не найдено", show_alert=True)
    await safe_edit_or_answer(call,
        f"🔑 {panel['flag']} {panel['name']}\n\nСрок действия:",
        reply_markup=kb_keygen_plans(pid))
    await call.answer()


@router.callback_query(F.data.startswith("keygen:plan:"))
async def adm_keygen_count(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != SUPER_ADMIN_ID:
        return await call.answer("⛔", show_alert=True)
    parts    = call.data.split(":")
    pid, plan_key = int(parts[2]), parts[3]
    await state.update_data(kg_pid=pid, kg_plan=plan_key)
    await state.set_state(S.kg_count)
    await safe_edit_or_answer(call, "🔑 Сколько ключей? (1–50):", reply_markup=kb_back("adm:keygen"))
    await call.answer()


@router.message(S.kg_count)
async def adm_keygen_generate(msg: Message, state: FSMContext):
    if msg.from_user.id != SUPER_ADMIN_ID:
        return
    try:
        count = max(1, min(50, int(msg.text.strip())))
    except ValueError:
        return await msg.answer("❌ Введите число от 1 до 50!")
    data     = await state.get_data()
    await state.clear()
    pid, plan_key = data["kg_pid"], data["kg_plan"]
    panel    = await get_panel(pid)
    if not panel:
        return await msg.answer("❌ Панель не найдена.")
    if plan_key == "forever":
        days, traffic, plan_name = 9999, 0, "Бессрочный"
    else:
        plan  = SUBSCRIPTION_PLANS[plan_key]
        days, traffic, plan_name = plan["days"], TRAFFIC_LIMITS.get(plan_key, 50), plan["name"]
    progress = await msg.answer(f"⏳ Генерирую {count} ключей…")
    client   = xui(panel)
    keys, failed = [], 0
    for _ in range(count):
        email  = f"key_{uuid.uuid4().hex[:10]}"
        result = await client.add_client(panel["inbound_id"], email,
                                          traffic_gb=traffic, expire_days=days)
        if result:
            config_url = client.sub_link(panel["sub_url"], email)
            keys.append(config_url)
            expires = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            await create_subscription(msg.from_user.id, pid, plan_key,
                                       result["uuid"], email, traffic, expires, config_url)
        else:
            failed += 1
    await progress.delete()
    if not keys:
        return await msg.answer("❌ Не удалось создать ни одного ключа.")
    header = (f"🔑 <b>{len(keys)} ключей</b> · {panel['flag']} {panel['name']} · {plan_name}\n"
              + (f"❌ Ошибок: {failed}\n" if failed else "") + "\n")
    chunk = header
    for i, k in enumerate(keys, 1):
        line = f"<b>#{i}</b> <code>{k}</code>\n\n"
        if len(chunk) + len(line) > 4000:
            await msg.answer(chunk)
            chunk = ""
        chunk += line
    if chunk:
        await msg.answer(chunk, reply_markup=kb_back("adm:keygen"))


# ═══════════════════════════════════════════════════════════════
# АДМИН ПАНЕЛЬ
# ═══════════════════════════════════════════════════════════════
@router.message(Command("admin"))
async def admin_entry(msg: Message, db_user=None):
    if not is_admin(msg, db_user):
        return
    is_super = msg.from_user.id == SUPER_ADMIN_ID
    await msg.answer(ADMIN_INTRO + (SUPER_ADMIN_EXTRA if is_super else ""),
                     reply_markup=kb_admin_main(is_super))


@router.callback_query(F.data == "menu:admin")
async def admin_entry_cb(call: CallbackQuery, db_user=None):
    if not is_admin(call, db_user):
        return await call.answer("⛔", show_alert=True)
    is_super = call.from_user.id == SUPER_ADMIN_ID
    await safe_edit_or_answer(call, ADMIN_INTRO + (SUPER_ADMIN_EXTRA if is_super else ""),
                               reply_markup=kb_admin_main(is_super))
    await call.answer()


@router.callback_query(F.data == "adm:back")
async def adm_back(call: CallbackQuery, db_user=None):
    if not is_admin(call, db_user):
        return await call.answer("⛔", show_alert=True)
    is_super = call.from_user.id == SUPER_ADMIN_ID
    await safe_edit_or_answer(call, ADMIN_INTRO + (SUPER_ADMIN_EXTRA if is_super else ""),
                               reply_markup=kb_admin_main(is_super))
    await call.answer()


@router.callback_query(F.data == "adm:stats")
async def adm_stats(call: CallbackQuery, db_user=None):
    if not is_admin(call, db_user):
        return await call.answer("⛔", show_alert=True)
    s = await get_stats()
    await safe_edit_or_answer(call,
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Всего: {s['total_users']}  Новых/сут: {s['new_today']}  Бан: {s['banned_users']}\n"
        f"🛡 Подписок: {s['active_subs']}  Панелей: {s['active_panels']}\n"
        f"💰 Доход: {s['total_revenue']:.2f}",
        reply_markup=kb_back("adm:back"))
    await call.answer()


@router.callback_query(F.data == "adm:panels")
async def adm_panels(call: CallbackQuery, db_user=None):
    if not is_admin(call, db_user):
        return await call.answer("⛔", show_alert=True)
    panels = await get_all_panels(active_only=False)
    await safe_edit_or_answer(call,
        f"📡 <b>Панели</b> ({len(panels)} шт.)" if panels else "📡 Нет панелей.",
        reply_markup=kb_admin_panels(panels))
    await call.answer()


@router.callback_query(F.data.regexp(r"^adm:panel:\d+$"))
async def adm_panel_detail(call: CallbackQuery, db_user=None):
    if not is_admin(call, db_user):
        return await call.answer("⛔", show_alert=True)
    pid   = int(call.data.split(":")[-1])
    panel = await get_panel(pid)
    if not panel:
        return await call.answer("Не найдено", show_alert=True)
    load = int(panel["current_clients"] / max(panel["max_clients"], 1) * 100)
    await safe_edit_or_answer(call,
        f"📡 <b>{panel['flag']} {panel['name']}</b>\n"
        f"🌍 {panel['location']}\n🔗 <code>{panel['url']}</code>\n"
        f"🔗 sub: <code>{panel['sub_url']}</code>\n"
        f"👤 {panel['username']}  Inbound: {panel['inbound_id']}\n"
        f"👥 {panel['current_clients']}/{panel['max_clients']} ({load}%)\n"
        f"{'✅ Активна' if panel['is_active'] else '❌ Выкл.'}",
        reply_markup=kb_panel_detail(pid, bool(panel["is_active"])))
    await call.answer()


@router.callback_query(F.data.startswith("adm:ptoggle:"))
async def adm_panel_toggle(call: CallbackQuery, db_user=None):
    if not is_admin(call, db_user):
        return await call.answer("⛔", show_alert=True)
    pid   = int(call.data.split(":")[-1])
    panel = await get_panel(pid)
    new   = 0 if panel["is_active"] else 1
    await db_update("panels", pid, is_active=new)
    await call.answer("✅ Включена" if new else "❌ Выключена", show_alert=True)
    panels = await get_all_panels(active_only=False)
    await safe_edit_or_answer(call, f"📡 <b>Панели</b> ({len(panels)} шт.)",
                               reply_markup=kb_admin_panels(panels))


@router.callback_query(F.data.startswith("adm:ptest:"))
async def adm_panel_test(call: CallbackQuery, db_user=None):
    if not is_admin(call, db_user):
        return await call.answer("⛔", show_alert=True)
    pid   = int(call.data.split(":")[-1])
    panel = await get_panel(pid)
    await call.answer("🔍 Проверяю…")
    ok = await xui(panel).test()
    await call.message.answer(
        f"{'✅' if ok else '❌'} {panel['name']} {'доступна' if ok else 'недоступна'}!")


@router.callback_query(F.data.startswith("adm:pdel:"))
async def adm_panel_del_confirm(call: CallbackQuery, db_user=None):
    if not is_admin(call, db_user):
        return await call.answer("⛔", show_alert=True)
    pid = int(call.data.split(":")[-1])
    await safe_edit_or_answer(call, "⚠️ Удалить панель?",
                               reply_markup=kb_confirm(f"adm:pdel_ok:{pid}", "adm:panels"))
    await call.answer()


@router.callback_query(F.data.startswith("adm:pdel_ok:"))
async def adm_panel_del(call: CallbackQuery, db_user=None):
    if not is_admin(call, db_user):
        return await call.answer("⛔", show_alert=True)
    pid = int(call.data.split(":")[-1])
    drop_xui(pid)
    await delete_panel(pid)
    await call.answer("🗑 Удалено", show_alert=True)
    panels = await get_all_panels(active_only=False)
    await safe_edit_or_answer(call,
        f"📡 <b>Панели</b> ({len(panels)} шт.)" if panels else "📡 Нет панелей.",
        reply_markup=kb_admin_panels(panels))


# ── Добавление панели — FSM ───────────────────────────────────────
@router.callback_query(F.data == "adm:panel:add")
async def adm_panel_add_start(call: CallbackQuery, state: FSMContext, db_user=None):
    if not is_admin(call, db_user):
        return await call.answer("⛔", show_alert=True)
    await state.set_state(S.p_name)
    await safe_edit_or_answer(call, "➕ <b>Шаг 1/8</b> — Название (напр.: Германия #1):",
                               reply_markup=kb_back("adm:panels"))
    await call.answer()


@router.message(S.p_name)
async def adm_p_url(msg: Message, state: FSMContext, db_user=None):
    if not is_admin(msg, db_user): return
    await state.update_data(name=msg.text.strip())
    await state.set_state(S.p_url)
    await msg.answer("<b>Шаг 2/8</b> — URL панели:\n<code>https://IP:PORT/путь</code>")


@router.message(S.p_url)
async def adm_p_user(msg: Message, state: FSMContext, db_user=None):
    if not is_admin(msg, db_user): return
    await state.update_data(url=msg.text.strip().rstrip("/"))
    await state.set_state(S.p_user)
    await msg.answer("<b>Шаг 3/8</b> — Логин:")


@router.message(S.p_user)
async def adm_p_pass(msg: Message, state: FSMContext, db_user=None):
    if not is_admin(msg, db_user): return
    await state.update_data(username=msg.text.strip())
    await state.set_state(S.p_pass)
    await msg.answer("<b>Шаг 4/8</b> — Пароль:")


@router.message(S.p_pass)
async def adm_p_inb(msg: Message, state: FSMContext, db_user=None):
    if not is_admin(msg, db_user): return
    await state.update_data(password=msg.text.strip())
    await state.set_state(S.p_inb)
    await msg.answer("<b>Шаг 5/8</b> — ID Inbound (обычно 1):")


@router.message(S.p_inb)
async def adm_p_sub(msg: Message, state: FSMContext, db_user=None):
    if not is_admin(msg, db_user): return
    try:
        inb = int(msg.text.strip())
    except ValueError:
        return await msg.answer("❌ Введите число!")
    await state.update_data(inbound_id=inb)
    await state.set_state(S.p_sub)
    await msg.answer("<b>Шаг 6/8</b> — URL подписки:\n"
                     "3x-ui → Settings → Subscription\n"
                     "Пример: <code>https://IP:PORT/путь_подписки</code>")


@router.message(S.p_sub)
async def adm_p_loc(msg: Message, state: FSMContext, db_user=None):
    if not is_admin(msg, db_user): return
    raw = msg.text.strip().rstrip("/")
    if raw.startswith("http://"):
        raw = "https://" + raw[len("http://"):]
    elif not raw.startswith("https://"):
        raw = "https://" + raw.lstrip("/")
    await state.update_data(sub_url=raw)
    await state.set_state(S.p_loc)
    await msg.answer("<b>Шаг 7/8</b> — Локация (напр.: Germany):")


@router.message(S.p_loc)
async def adm_p_flag(msg: Message, state: FSMContext, db_user=None):
    if not is_admin(msg, db_user): return
    await state.update_data(location=msg.text.strip())
    await state.set_state(S.p_flag)
    await msg.answer("<b>Шаг 8/8</b> — Флаг эмодзи (🇩🇪 🇳🇱 🇺🇸 …):")


@router.message(S.p_flag)
async def adm_p_finish(msg: Message, state: FSMContext, db_user=None):
    if not is_admin(msg, db_user): return
    data = await state.get_data()
    await state.clear()
    flag = msg.text.strip()
    await msg.answer("🔍 Проверяю соединение…")
    tmp = XUIClient(data["url"], data["username"], data["password"])
    ok  = await tmp.test()
    await tmp.close()
    pid = await add_panel(
        name=data["name"], url=data["url"], username=data["username"],
        password=data["password"], inbound_id=data["inbound_id"],
        sub_url=data["sub_url"], location=data["location"],
        flag=flag, added_by=msg.from_user.id)
    await msg.answer(
        f"{'✅' if ok else '⚠️'} <b>Панель добавлена!</b>\n\n"
        f"🆔 {pid}  📡 {data['name']}  {flag} {data['location']}\n"
        f"🔌 {'✅ OK' if ok else '❌ Ошибка подключения'}",
        reply_markup=kb_back("adm:panels"))


# ── Управление пользователями ─────────────────────────────────────
@router.callback_query(F.data == "adm:users")
async def adm_users(call: CallbackQuery, state: FSMContext, db_user=None):
    if not is_admin(call, db_user):
        return await call.answer("⛔", show_alert=True)
    await state.set_state(S.u_id)
    await safe_edit_or_answer(call, "👥 Введите Telegram ID:", reply_markup=kb_back("adm:back"))
    await call.answer()


@router.message(S.u_id)
async def adm_show_user(msg: Message, state: FSMContext, db_user=None):
    if not is_admin(msg, db_user): return
    await state.clear()
    try:
        tid = int(msg.text.strip())
    except ValueError:
        return await msg.answer("❌ Введите число!")
    target = await get_user(tid)
    if not target:
        return await msg.answer("❌ Пользователь не найден.")
    subs = await get_active_subscriptions(tid)
    await msg.answer(
        f"👤 <b>Пользователь</b>\n\n"
        f"🆔 <code>{target['tg_id']}</code>\n👤 {target['full_name']}\n"
        f"💰 {target['balance']:.2f}₽  🛡 {len(subs)} подписок\n"
        f"⚙️ {'Админ' if target['is_admin'] else '—'}  "
        f"🚫 {'Забанен' if target['is_banned'] else '—'}",
        reply_markup=kb_user_manage(tid, bool(target["is_banned"]), bool(target["is_admin"])))


@router.callback_query(F.data.startswith("adm:uban:"))
async def adm_ban(call: CallbackQuery, db_user=None):
    if not is_admin(call, db_user):
        return await call.answer("⛔", show_alert=True)
    tid    = int(call.data.split(":")[-1])
    target = await get_user(tid)
    new    = 0 if target["is_banned"] else 1
    await db_update("users", tid, id_col="tg_id", is_banned=new)
    await call.answer("✅ Разблокирован" if not new else "🚫 Заблокирован", show_alert=True)


@router.callback_query(F.data.startswith("adm:uadmin:"))
async def adm_toggle_admin(call: CallbackQuery):
    if call.from_user.id != SUPER_ADMIN_ID:
        return await call.answer("⛔ Только суперадмин", show_alert=True)
    tid    = int(call.data.split(":")[-1])
    target = await get_user(tid)
    new    = 0 if target["is_admin"] else 1
    await db_update("users", tid, id_col="tg_id", is_admin=new)
    await call.answer("⚙️ Права выданы" if new else "👤 Права сняты", show_alert=True)


# ── Рассылка ─────────────────────────────────────────────────────
@router.callback_query(F.data == "adm:broadcast")
async def adm_broadcast_start(call: CallbackQuery, state: FSMContext, db_user=None):
    if not is_admin(call, db_user):
        return await call.answer("⛔", show_alert=True)
    await state.set_state(S.bcast)
    await safe_edit_or_answer(call, "📢 Введите текст рассылки:", reply_markup=kb_back("adm:back"))
    await call.answer()


@router.message(S.bcast)
async def adm_do_broadcast(msg: Message, state: FSMContext, db_user=None):
    if not is_admin(msg, db_user): return
    await state.clear()
    users        = await get_all_users()
    sent, failed = 0, 0
    prog         = await msg.answer(f"📢 0/{len(users)}…")
    for i, u in enumerate(users):
        try:
            await msg.bot.send_message(u["tg_id"], msg.text)
            sent += 1
        except Exception:
            failed += 1
        if i % 25 == 0:
            try:
                await prog.edit_text(f"📢 {i}/{len(users)}…")
            except Exception:
                pass
    await prog.edit_text(f"📢 <b>Рассылка завершена!</b>\n✅ {sent}  ❌ {failed}")


# ── Промокоды (создание) ─────────────────────────────────────────
@router.callback_query(F.data == "adm:promos")
async def adm_promos(call: CallbackQuery, state: FSMContext, db_user=None):
    if call.from_user.id != SUPER_ADMIN_ID:
        return await call.answer("⛔ Только суперадмин", show_alert=True)
    await state.set_state(S.pr_code)
    await safe_edit_or_answer(call, "🎁 <b>Создать промокод</b>\n\nВведите код:",
                               reply_markup=kb_back("adm:back"))
    await call.answer()


@router.message(S.pr_code)
async def adm_pr_disc(msg: Message, state: FSMContext, db_user=None):
    if not is_admin(msg, db_user): return
    await state.update_data(code=msg.text.strip().upper())
    await state.set_state(S.pr_disc)
    await msg.answer("Скидка в % (0 — нет):")


@router.message(S.pr_disc)
async def adm_pr_days(msg: Message, state: FSMContext, db_user=None):
    if not is_admin(msg, db_user): return
    try:
        disc = int(msg.text.strip())
    except ValueError:
        return await msg.answer("❌ Число!")
    await state.update_data(discount=disc)
    await state.set_state(S.pr_days)
    await msg.answer("Дней продления существующей подписки (0 — нет):")


@router.message(S.pr_days)
async def adm_pr_subdays(msg: Message, state: FSMContext, db_user=None):
    if not is_admin(msg, db_user): return
    try:
        days = int(msg.text.strip())
    except ValueError:
        return await msg.answer("❌ Число!")
    await state.update_data(free_days=days)
    await state.set_state(S.pr_subdays)
    await msg.answer("Дней для новой подписки по промокоду (0 — не выдавать):")


@router.message(S.pr_subdays)
async def adm_pr_panel(msg: Message, state: FSMContext, db_user=None):
    if not is_admin(msg, db_user): return
    try:
        sub_days = int(msg.text.strip())
    except ValueError:
        return await msg.answer("❌ Число!")
    await state.update_data(sub_days=sub_days)
    if sub_days > 0:
        panels = await get_all_panels(active_only=True)
        if not panels:
            await state.update_data(promo_panel_id=None)
            await state.set_state(S.pr_uses)
            return await msg.answer("⚠️ Нет панелей — первая доступная.\n\nМакс. использований:")
        b = InlineKeyboardBuilder()
        for p in panels:
            b.button(text=f"{p['flag']} {p['name']}", callback_data=f"adm:promo_panel:{p['id']}")
        b.button(text="🎲 Любая", callback_data="adm:promo_panel:0")
        b.adjust(1)
        await state.set_state(S.pr_panel)
        await msg.answer("📡 <b>Сервер для подписки:</b>", reply_markup=b.as_markup())
    else:
        await state.update_data(promo_panel_id=None)
        await state.set_state(S.pr_uses)
        await msg.answer("Макс. использований:")


@router.callback_query(F.data.startswith("adm:promo_panel:"), S.pr_panel)
async def adm_pr_panel_chosen(call: CallbackQuery, state: FSMContext, db_user=None):
    if not is_admin(call, db_user):
        return await call.answer("⛔", show_alert=True)
    pid_str        = call.data.split(":")[-1]
    promo_panel_id = int(pid_str) if pid_str != "0" else None
    await state.update_data(promo_panel_id=promo_panel_id)
    await state.set_state(S.pr_uses)
    await safe_edit_or_answer(call, "✅ Сервер выбран.\n\nМакс. использований:")
    await call.answer()


@router.message(S.pr_uses)
async def adm_pr_finish(msg: Message, state: FSMContext, db_user=None):
    if not is_admin(msg, db_user): return
    try:
        uses = int(msg.text.strip())
    except ValueError:
        return await msg.answer("❌ Число!")
    data = await state.get_data()
    await state.clear()
    sub_days, promo_panel_id = data.get("sub_days", 0), data.get("promo_panel_id", None)
    await create_promo(data["code"], data["discount"], data["free_days"], uses,
                       msg.from_user.id, sub_days=sub_days, promo_panel_id=promo_panel_id)
    await msg.answer(
        f"✅ Промокод <code>{data['code']}</code> создан!\n"
        f"Скидка: {data['discount']}%  Дней: {data['free_days']}  "
        f"Подписка: {sub_days} дн.  Лимит: {uses}")


# ── Управление администраторами ───────────────────────────────────
@router.callback_query(F.data == "adm:admins")
async def adm_admins(call: CallbackQuery, db_user=None):
    if call.from_user.id != SUPER_ADMIN_ID:
        return await call.answer("⛔", show_alert=True)
    admins = await db_fetchall("SELECT tg_id, full_name, username FROM users WHERE is_admin=1")
    lines  = ["👮 <b>Администраторы:</b>\n"]
    for a in admins:
        lines.append(f"• {a['full_name'] or 'N/A'} (@{a['username'] or 'нет'}) — <code>{a['tg_id']}</code>")
    if not admins:
        lines.append("Нет обычных администраторов.")
    b = InlineKeyboardBuilder()
    b.button(text="➕ Добавить", callback_data="adm:admin:add")
    b.button(text="➖ Снять",    callback_data="adm:admin:remove")
    b.button(text="◀️ Назад",   callback_data="adm:back")
    b.adjust(2)
    await safe_edit_or_answer(call, "\n".join(lines), reply_markup=b.as_markup())
    await call.answer()


@router.callback_query(F.data == "adm:admin:add")
async def adm_admin_add_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != SUPER_ADMIN_ID:
        return await call.answer("⛔", show_alert=True)
    await state.set_state(S.add_admin_id)
    await state.update_data(admin_action="add")
    await safe_edit_or_answer(call, "➕ Введите Telegram ID:", reply_markup=kb_back("adm:admins"))
    await call.answer()


@router.callback_query(F.data == "adm:admin:remove")
async def adm_admin_remove_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != SUPER_ADMIN_ID:
        return await call.answer("⛔", show_alert=True)
    await state.set_state(S.add_admin_id)
    await state.update_data(admin_action="remove")
    await safe_edit_or_answer(call, "➖ Введите Telegram ID:", reply_markup=kb_back("adm:admins"))
    await call.answer()


@router.message(S.add_admin_id)
async def adm_admin_apply(msg: Message, state: FSMContext):
    if msg.from_user.id != SUPER_ADMIN_ID: return
    data = await state.get_data()
    await state.clear()
    action = data.get("admin_action", "add")
    try:
        tid = int(msg.text.strip())
    except ValueError:
        return await msg.answer("❌ Числовой ID!")
    if tid == SUPER_ADMIN_ID:
        return await msg.answer("❌ Нельзя изменить суперадмина.")
    target = await get_user(tid)
    if not target:
        return await msg.answer("❌ Пользователь не найден.")
    new_val = 1 if action == "add" else 0
    await db_update("users", tid, id_col="tg_id", is_admin=new_val)
    if action == "add":
        await msg.answer(f"✅ {target['full_name']} назначен администратором.")
        try:
            await msg.bot.send_message(tid, "🎉 Вам выданы права <b>администратора</b>!")
        except Exception:
            pass
    else:
        await msg.answer(f"✅ Права сняты с {target['full_name']}.")


# ── Fallback ─────────────────────────────────────────────────────
@router.callback_query(F.data == "cancel")
async def on_cancel(call: CallbackQuery, state: FSMContext, db_user=None):
    await state.clear()
    await send_with_photo(call, IMG_MENU, WELCOME_TEXT.format(name=call.from_user.full_name),
                          reply_markup=kb_main(is_admin(call, db_user)), edit=True)
    await call.answer()


@router.callback_query()
async def cb_fallback(call: CallbackQuery, state: FSMContext, db_user=None):
    await state.clear()
    try:
        await call.answer("⚠️ Кнопка устарела", show_alert=False)
    except Exception:
        pass
    await send_with_photo(call, IMG_MENU, WELCOME_TEXT.format(name=call.from_user.full_name),
                          reply_markup=kb_main(is_admin(call, db_user)), edit=True)


# ═══════════════════════════════════════════════════════════════
# ТОЧКА ВХОДА
# ═══════════════════════════════════════════════════════════════
async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp  = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    dp.include_router(router)

    await init_db()

    log.info("🤖 Bot starting…")
    log.info("   SOCKS5: %s", "✅" if SOCKS_AVAILABLE else "❌ (install aiohttp_socks)")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        try:
            await platega.close()
        except Exception:
            pass
        for c in list(_xui_cache.values()):
            try:
                await c.close()
            except Exception:
                pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("👋 Bot stopped")
