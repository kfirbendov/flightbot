#!/usr/bin/env python3
"""
Flight Price Monitor - Google Flights
=======================================
עוקב אחרי מחיר טיסה ישירה של אל על בגוגל פלייטס (או כל URL אחר של גוגל פלייטס
שתגדיר), ושולח התראת טלגרם כשהמחיר יורד מתחת לסף שקבעת.

איך זה עובד:
- פותח את ה-URL בדפדפן headless (Playwright)
- מחפש בעמוד מחירים בשקלים (₪)
- לוקח את המחיר הזול ביותר שנמצא
- אם המחיר <= הסף שקבעת -> שולח הודעת טלגרם
- שומר לוג CSV של כל בדיקה (זמן + מחיר) כדי שתוכל לראות מגמות

הרצה חוזרת (כל 15-20 דקות) נעשית באמצעות cron / Task Scheduler - ראה README.
"""

import os
import re
import csv
import json
import time
import random
import logging
import urllib.parse
from datetime import datetime, date, timedelta
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

# ---------------------------------------------------------------------------
# קונפיגורציה - נטענת ממשתני סביבה (ראה .env.example). אפשר גם לערוך כאן ישירות.
# ---------------------------------------------------------------------------

ORIGIN = os.environ.get("ORIGIN", "Tel Aviv")
DESTINATION = os.environ.get("DESTINATION", "Bangkok")
AIRLINE = os.environ.get("AIRLINE", "El Al")

# טווח תאריכים לבדיקה (כולל שני הקצוות)
START_DATE = os.environ.get("START_DATE", "2026-09-07")
END_DATE = os.environ.get("END_DATE", "2026-09-10")

# סף מחיר קבוע בשקלים - התראה נשלחת ברגע שהמחיר יורד מתחת לערך הזה,
# לא משנה מה היה המחיר לפני כן (12000, 5000, מה שלא יהיה)
PRICE_THRESHOLD_NIS = int(os.environ.get("PRICE_THRESHOLD_NIS", "2000"))

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# כמה זמן (בשניות) לחכות שהעמוד יטען לפני שקוראים את המחירים
PAGE_LOAD_WAIT_SECONDS = int(os.environ.get("PAGE_LOAD_WAIT_SECONDS", "8"))

# הפסקה קצרה בין בדיקת תאריך לתאריך (מפחית סיכוי לחסימה מגוגל)
DELAY_BETWEEN_DATES_SECONDS = float(os.environ.get("DELAY_BETWEEN_DATES_SECONDS", "4"))

DATA_DIR = Path(__file__).parent / "data"
LOG_CSV = DATA_DIR / "price_history.csv"
STATE_FILE = DATA_DIR / "last_alert_state.json"  # מונע ספאם של אותה התראה שוב ושוב, per-date

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("flight_monitor")


def generate_date_list(start_iso: str, end_iso: str) -> list[str]:
    start = date.fromisoformat(start_iso)
    end = date.fromisoformat(end_iso)
    days = []
    d = start
    while d <= end:
        days.append(d.isoformat())
        d += timedelta(days=1)
    return days


def build_flight_url(date_iso: str) -> str:
    """בונה URL של גוגל פלייטס דרך חיפוש בשפה טבעית (q=), כדי שנוכל לייצר
    בקלות URL לכל תאריך בטווח בלי לפענח את פורמט ה-protobuf הפנימי של גוגל."""
    d = date.fromisoformat(date_iso)
    readable_date = d.strftime("%B %-d, %Y") if os.name != "nt" else d.strftime("%B %d, %Y")
    query = (
        f"nonstop flights from {ORIGIN} to {DESTINATION} on {AIRLINE} "
        f"on {readable_date} one way"
    )
    params = {
        "hl": "iw",
        "gl": "IL",
        "curr": "ILS",
        "q": query,
    }
    return "https://www.google.com/travel/flights?" + urllib.parse.urlencode(params)


# ---------------------------------------------------------------------------
# ליבת הבדיקה
# ---------------------------------------------------------------------------

def ensure_locale_params(url: str) -> str:
    """מוודא שה-URL מבקש תצוגה בעברית/שקלים, כדי שהמחירים שנקרא יהיו ב-₪."""
    sep = "&" if "?" in url else "?"
    extra = []
    if "hl=" not in url:
        extra.append("hl=iw")
    if "gl=" not in url:
        extra.append("gl=IL")
    if "curr=" not in url:
        extra.append("curr=ILS")
    if not extra:
        return url
    return url + sep + "&".join(extra)


def fetch_prices_from_page(url: str) -> list[int]:
    """פותח את הדף, ומחזיר רשימת כל המחירים בשקלים שנמצאו בטקסט העמוד."""
    url = ensure_locale_params(url)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            locale="he-IL",
            timezone_id="Asia/Jerusalem",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 900},
        )
        page = context.new_page()
        log.info("Loading page...")
        page.goto(url, timeout=45000)

        # מחכים שהתוצאות ייטענו (גוגל פלייטס טוען אסינכרונית)
        page.wait_for_timeout(PAGE_LOAD_WAIT_SECONDS * 1000)

        # ניסיון להמתין ספציפית לטקסט עם סימן שקל, לא חובה שיצליח
        try:
            page.wait_for_selector("text=/₪/", timeout=10000)
        except Exception:
            log.warning("Didn't detect ₪ text within timeout, continuing anyway")

        body_text = page.inner_text("body")
        browser.close()

    # תבניות אפשריות: "₪1,234" / "₪ 1,234" / "1,234 ₪"
    matches = re.findall(r"₪\s?([\d,]{3,7})|([\d,]{3,7})\s?₪", body_text)
    prices = []
    for a, b in matches:
        raw = a or b
        try:
            prices.append(int(raw.replace(",", "")))
        except ValueError:
            continue

    # מסננים מחירים לא סבירים (חוסם רעש כמו מספרי טלפון/שנים שנתפסו בטעות)
    prices = [p for p in prices if 300 <= p <= 100000]
    return prices


def send_telegram_alert(message: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.error("Telegram not configured - set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
        return False
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            api_url,
            data={"chat_id": TELEGRAM_CHAT_ID, "text": message, "disable_web_page_preview": False},
            timeout=15,
        )
        resp.raise_for_status()
        return True
    except Exception as e:
        log.error(f"Failed to send Telegram message: {e}")
        return False


def log_price(check_date: str, price: int) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    is_new = not LOG_CSV.exists()
    with open(LOG_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["timestamp", "flight_date", "price_nis"])
        writer.writerow([datetime.now().isoformat(timespec="seconds"), check_date, price])


def load_alert_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (ValueError, json.JSONDecodeError):
            return {}
    return {}


def save_alert_state(state: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state))


def check_date(flight_date: str, alert_state: dict) -> None:
    url = build_flight_url(flight_date)
    log.info(f"Checking {flight_date} ...")
    try:
        prices = fetch_prices_from_page(url)
    except Exception as e:
        log.error(f"[{flight_date}] Failed to fetch page: {e}")
        return

    if not prices:
        log.warning(f"[{flight_date}] No prices found — Google may have changed its layout, "
                     f"or the page didn't finish loading. Try increasing PAGE_LOAD_WAIT_SECONDS.")
        return

    cheapest = min(prices)
    log.info(f"[{flight_date}] Cheapest price found: ₪{cheapest}")
    log_price(flight_date, cheapest)

    already_alerted = alert_state.get(flight_date, False)

    if cheapest < PRICE_THRESHOLD_NIS:
        if not already_alerted:
            msg = (
                f"✈️ מחיר טיסה מתחת ל-₪{PRICE_THRESHOLD_NIS:,}!\n"
                f"{ORIGIN} → {DESTINATION} ({AIRLINE}, ישירה)\n"
                f"תאריך: {flight_date}\n"
                f"מחיר נוכחי: ₪{cheapest:,}\n\n"
                f"{url}"
            )
            if send_telegram_alert(msg):
                log.info(f"[{flight_date}] Alert sent!")
                alert_state[flight_date] = True
            else:
                log.error(f"[{flight_date}] Alert NOT sent (see error above)")
        else:
            log.info(f"[{flight_date}] Still below threshold - already alerted, skipping duplicate")
    else:
        # המחיר חזר מעל הסף - מאפסים כדי שהתראה הבאה על התאריך הזה תישלח מחדש
        if already_alerted:
            alert_state[flight_date] = False


def run_once() -> None:
    dates = generate_date_list(START_DATE, END_DATE)
    log.info(f"Checking {len(dates)} date(s) between {START_DATE} and {END_DATE} "
             f"(threshold = ₪{PRICE_THRESHOLD_NIS})...")

    alert_state = load_alert_state()

    for i, d in enumerate(dates):
        check_date(d, alert_state)
        if i < len(dates) - 1:
            time.sleep(DELAY_BETWEEN_DATES_SECONDS + random.uniform(0, 2))

    save_alert_state(alert_state)


if __name__ == "__main__":
    run_once()
