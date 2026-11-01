import os
from datetime import date, datetime, timedelta, timezone

import redis
from flask import Flask, abort, jsonify, render_template, request

from surahs import SURAHS, TOTAL_AYAHS

app = Flask(__name__)

r = redis.Redis(
    host=os.environ.get("REDIS_HOST", "redis"),
    port=int(os.environ.get("REDIS_PORT", 6379)),
    password=os.environ.get("REDIS_PASSWORD") or None,
    decode_responses=True,
)

INTERVALS = [1, 3, 7, 14, 30, 60]  # days between revisions


def now_ts():
    return datetime.now(timezone.utc).timestamp()


def check_surah(n):
    if not 1 <= n <= len(SURAHS):
        abort(404)


def get_surah(n):
    name, total = SURAHS[n - 1]
    data = r.hgetall(f"surah:{n}")
    ayahs = int(data.get("ayahs", 0))
    stage = int(data.get("stage", 0))
    due = r.zscore("revision:due", n)

    if ayahs == 0:
        status = "not_started"
    elif ayahs < total:
        status = "learning"
    elif due is not None and due <= now_ts():
        status = "needs_revision"
    else:
        status = "memorised"

    return {
        "number": n,
        "name": name,
        "total": total,
        "ayahs": ayahs,
        "stage": stage,
        "status": status,
        "last_revised": data.get("last_revised"),
        "due": due,
    }


def touch_streak():
    today = date.today()
    last = r.get("streak:last_active")
    if last == today.isoformat():
        return
    if last == (today - timedelta(days=1)).isoformat():
        r.incr("streak:count")
    else:
        r.set("streak:count", 1)
    r.set("streak:last_active", today.isoformat())


def current_streak():
    today = date.today()
    last = r.get("streak:last_active")
    if last in (today.isoformat(), (today - timedelta(days=1)).isoformat()):
        return int(r.get("streak:count") or 0)
    return 0


@app.get("/")
def dashboard():
    return render_template("index.html")


@app.get("/health")
def health():
    r.ping()
    return jsonify(status="ok")


@app.get("/api/surahs")
def list_surahs():
    return jsonify([get_surah(n) for n in range(1, len(SURAHS) + 1)])


@app.get("/api/summary")
def summary():
    surahs = [get_surah(n) for n in range(1, len(SURAHS) + 1)]
    memorised = sum(s["ayahs"] for s in surahs)
    counts = {}
    for s in surahs:
        counts[s["status"]] = counts.get(s["status"], 0) + 1
    return jsonify(
        memorised_ayahs=memorised,
        total_ayahs=TOTAL_AYAHS,
        percent=round(memorised / TOTAL_AYAHS * 100, 1),
        streak=current_streak(),
        due_count=counts.get("needs_revision", 0),
        counts=counts,
    )


@app.get("/api/due")
def due_today():
    members = r.zrangebyscore("revision:due", 0, now_ts())
    return jsonify([get_surah(int(n)) for n in members])


@app.post("/api/surah/<int:n>/progress")
def set_progress(n):
    check_surah(n)
    total = SURAHS[n - 1][1]
    body = request.get_json(silent=True) or {}
    try:
        ayahs = int(body.get("ayahs"))
    except (TypeError, ValueError):
        return jsonify(error="ayahs must be a number"), 400
    ayahs = max(0, min(ayahs, total))

    r.hset(f"surah:{n}", mapping={"ayahs": ayahs})
    if ayahs == total:
        # Fully memorised: schedule the first revision (once)
        if r.zscore("revision:due", n) is None:
            r.hset(f"surah:{n}", mapping={"stage": 0})
            r.zadd("revision:due", {n: now_ts() + INTERVALS[0] * 86400})
    else:
        r.zrem("revision:due", n)

    touch_streak()
    return jsonify(get_surah(n))


@app.post("/api/surah/<int:n>/revise")
def revise(n):
    check_surah(n)
    s = get_surah(n)
    if s["ayahs"] < s["total"]:
        return jsonify(error="finish memorising this surah first"), 400

    stage = min(s["stage"] + 1, len(INTERVALS) - 1)
    r.hset(f"surah:{n}", mapping={"stage": stage, "last_revised": date.today().isoformat()})
    r.zadd("revision:due", {n: now_ts() + INTERVALS[stage] * 86400})

    touch_streak()
    return jsonify(get_surah(n))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
