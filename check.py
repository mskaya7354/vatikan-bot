#!/usr/bin/env python3
"""
Vatikan Muzeleri bilet botu - GitHub Actions surumu (8 Ekim 2026)
Dakikada bir kontrol eder; "Biglietti d'ingresso" acilinca ntfy ile iPhone'a bildirim yollar.
Ek kutuphane gerekmez (sadece Python standart kutuphanesi).
"""
import json, os, random, time, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

# ================= AYARLAR =================
VISIT_DATE = "08/10/2026"
STOP_AT = datetime(2026, 10, 8, 18, 0, tzinfo=timezone(timedelta(hours=2)))  # Roma saatiyle son giris
TARGETS = ["Musei Vaticani - Biglietti d'ingresso"]
# Rehberli tur da istersen alttaki satirin basindaki # isaretini kaldir:
# TARGETS.append("Musei Vaticani - Visite Guidate Singoli Musei")
TEST_TARGET = "Palazzo Papale - Biglietti d'ingresso"  # su an musait olan bilet, test icin
INTERVAL = 60  # saniye
# ===========================================

URL = ("https://tickets.museivaticani.va/api/search/result"
       f"?lang=it&visitorNum=1&visitDate={VISIT_DATE}&area=1&who=1&page=0")
BOOKING_URL = "https://tickets.museivaticani.va/home/visit/1/1791406800000/1/1"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "").strip()
RUN_MINUTES = int(os.environ.get("RUN_MINUTES", "340"))
TEST = os.environ.get("TEST", "false").lower() == "true"
IST = timezone(timedelta(hours=3))


def log(m):
    print(f"[{datetime.now(IST):%d.%m %H:%M:%S}] {m}", flush=True)


def notify(title, msg, priority="urgent"):
    log(f"BILDIRIM: {title} - {msg}")
    if not NTFY_TOPIC:
        log("NTFY_TOPIC secret'i tanimli degil, bildirim gonderilemedi!")
        return
    req = urllib.request.Request(
        f"https://ntfy.sh/{NTFY_TOPIC}", data=msg.encode("utf-8"), method="POST",
        headers={"Title": title, "Priority": priority, "Tags": "ticket", "Click": BOOKING_URL})
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception as e:
        log(f"ntfy hatasi: {e}")


def fetch():
    """{bilet adi: durum} doner, or. {"Musei Vaticani - Biglietti d'ingresso": "SOLD_OUT"}"""
    req = urllib.request.Request(URL, headers={
        "User-Agent": UA, "Accept": "application/json, text/plain, */*", "Referer": BOOKING_URL})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read().decode("utf-8", "replace")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise RuntimeError(f"Site JSON yerine baska bir sey dondu: {raw[:200]!r}")
    return {(v.get("name") or "").strip(): v.get("availability", "?") for v in data.get("visits", [])}


def main():
    targets = [TEST_TARGET] if TEST else TARGETS
    end = time.time() + RUN_MINUTES * 60
    last, errors, warned, wait = {}, 0, False, INTERVAL
    log(f"Basladi. Tarih: {VISIT_DATE}, mod: {'TEST' if TEST else 'takip'}, sure: {RUN_MINUTES} dk")

    while True:
        if datetime.now(timezone.utc) > STOP_AT:
            log("8 Ekim gecti, bot duruyor. GitHub'da workflow'u kapatabilirsin.")
            return
        try:
            status = fetch()
            errors, wait = 0, INTERVAL
            for t in targets:
                av = status.get(t)
                if av is None:
                    log(f"Uyari: '{t}' yanitta yok ({len(status)} kayit geldi)")
                    if TEST:
                        notify("TEST HATA", f"Yanit geldi ama '{t}' bulunamadi.", "high")
                    continue
                log(f"{t}: {av}")
                if av == "AVAILABLE" and last.get(t) != "AVAILABLE":
                    notify("TEST basarili" if TEST else "Vatikan bileti ACILDI",
                           f"{VISIT_DATE} - {t} musait! Hemen al.")
                last[t] = av
        except urllib.error.HTTPError as e:
            errors += 1
            log(f"HTTP {e.code}")
            if e.code in (401, 403, 429):
                wait = min(wait * 2, 1800)
            if TEST:
                notify("TEST HATA", f"Site HTTP {e.code} dondu (bulut IP'si engellenmis olabilir).", "high")
        except Exception as e:
            errors += 1
            log(f"Hata: {e}")
            if TEST:
                notify("TEST HATA", f"Siteye ulasilamadi: {e}"[:300], "high")
        if errors >= 5 and not warned:
            notify("Vatikan bot SORUN",
                   "Bot 5 kez ust uste siteye ulasamadi. GitHub Actions loguna bak.", "high")
            warned = True
        if TEST or time.time() + wait > end:
            log("Bu kosu bitti; zamanlayici yenisini baslatacak.")
            return
        time.sleep(wait + random.randint(0, 15))


if __name__ == "__main__":
    main()
