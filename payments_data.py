"""
Mock payments data for the SimpleBit merchant app shell (static/app.html).

There is no real SimpleBit backend to read from (see tools.py's show_*_button
docstrings -- same situation), so this module seeds a realistic, internally
consistent set of payment records in memory and answers the same questions a
real payments API would: list/filter/search, fetch one payment's full detail
and timeline, and the Home screen's aggregate stats.

All dates are relative to "now" (computed fresh each time _build_payments()
runs, not hardcoded), so "Collected today" / "Latest" / the 7-day chart stay
meaningful no matter when the server is started -- a hardcoded date would go
stale the day after it was written.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

STATUSES = ["pending", "paid", "failed", "expired", "refunded"]

STATUS_LABEL = {
    "pending": "Pending",
    "paid": "Paid",
    "failed": "Failed",
    "expired": "Expired",
    "refunded": "Refunded",
}

# Matches the design mockups' pill colors (Design update - HTML/02, /04).
STATUS_COLOR = {
    "pending": "#D97706",
    "paid": "#16A34A",
    "failed": "#DC2626",
    "expired": "#9CA3AF",
    "refunded": "#6B7280",
}

MERCHANT_NAME = "Webcreaters"
MERCHANT_USER = "Parveen"


def _dt(days_ago: float, hour: int, minute: int) -> datetime:
    """A timestamp roughly `days_ago` days before today, at a fixed
    hour:minute -- fixed on the STORY (e.g. "created the day it was sent"),
    relative on the CALENDAR (so it stays "recent" instead of drifting into
    the past). Pinning the hour can otherwise land AFTER the actual current
    time on a small days_ago (e.g. "0.02 days ago" at a hardcoded 13:43 when
    it's actually 9am) -- step back one more day whenever that happens, so
    nothing is ever timestamped in the future relative to datetime.now()."""
    now = datetime.now()
    candidate = (now - timedelta(days=days_ago)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate > now:
        candidate -= timedelta(days=1)
    return candidate


def _enforce_chronological(timeline: List[Dict]) -> None:
    """Each step in `timeline` is built independently via `_dt(days_ago, hour,
    minute)`, so two nearby steps with different hand-picked hours can land
    out of order once `_dt`'s future-timestamp clamp (see its docstring)
    steps one of them back a full day -- e.g. "Opened" at a fixed 12:00 can
    end up before "Sent" at a fixed 18:02 the day before. Mutates in place:
    nudges any step earlier than its predecessor forward by a minute, and
    clamps a final overrun back to now."""
    now = datetime.now()
    for i in range(1, len(timeline)):
        if timeline[i]["time"] < timeline[i - 1]["time"]:
            timeline[i]["time"] = timeline[i - 1]["time"] + timedelta(minutes=1)
    if timeline and timeline[-1]["time"] > now:
        timeline[-1]["time"] = now


def _build_payments() -> List[Dict]:
    """20 payments spanning every status, built fresh against "now" so the
    Home screen's "today" math and the "Latest" list stay live. Amounts,
    names and the failed/settling timelines are carried over verbatim from
    the design mockups (Design update - HTML/02, /03, /04) for continuity;
    the rest fill out a believable spread around them."""
    payments: List[Dict] = []

    def add(id_, customer, amount, status, method, method_detail, description, timeline, fees=None):
        _enforce_chronological(timeline)
        net_payout = None
        if status in ("paid", "refunded") and fees is not None:
            net_payout = round(amount - fees, 2)
        payments.append({
            "id": id_,
            "customer": customer,
            "amount": amount,
            "status": status,
            "method": method,
            "method_detail": method_detail,
            "description": description,
            "invoice_ref": f"INV-{1789000000000 + int(id_.split('-')[1]) * 137951}-{id_.split('-')[1]}",
            "fees": fees,
            "net_payout": net_payout,
            "created_at": timeline[0]["time"],
            "timeline": timeline,
        })

    # -- Failed: Sarah K., car rental deposit (mockups/03, left card) --
    add("PAY-0001", "Sarah K.", 3200.00, "failed", "Card", "Card ····4417", "Car rental deposit", [
        {"event": "Created", "detail": "By Parveen", "time": _dt(0.02, 13, 12), "action": None},
        {"event": "Sent", "detail": "WhatsApp template", "time": _dt(0.02, 13, 12), "action": None},
        {"event": "Opened", "detail": "First viewed · viewed twice", "time": _dt(0.02, 13, 40), "action": None},
        {"event": "Payment attempt failed", "detail": "Card ending 4417 · customer left at the bank's 3-D Secure step",
         "time": _dt(0.02, 13, 43), "action": "Send resume link", "failed": True},
    ])

    # -- Settling: Ahmed M., yacht booking (mockups/03, right card) --
    add("PAY-0002", "Ahmed M.", 3200.00, "paid", "Apple Pay", "Apple Pay", "Yacht booking", [
        {"event": "Created", "detail": "By Arfath", "time": _dt(1.2, 11, 2), "action": None},
        {"event": "Sent", "detail": "Email", "time": _dt(1.2, 11, 2), "action": None},
        {"event": "Opened", "detail": "Viewed", "time": _dt(1.2, 13, 58), "action": None},
        {"event": "Payment attempt", "detail": "Apple Pay · approved", "time": _dt(1.2, 14, 4), "action": None},
        {"event": "Paid", "detail": "Fees AED 98.49 · net AED 3,101.51", "time": _dt(1.2, 14, 4), "action": None},
        {"event": "Settling", "detail": "In payout PO-2291", "time": _dt(1.2, 14, 4),
         "action": "Get it today · fee AED 21"},
    ], fees=98.49)

    # -- Pending link, opened not paid (mockups/02, row 1 & Home "Sarah K." latest) --
    add("PAY-0003", "modebebrian@gmail.com", 500.00, "pending", "Link", "Card link", "Design consultation", [
        {"event": "Created", "detail": "By Parveen", "time": _dt(0.9, 18, 2), "action": None},
        {"event": "Sent", "detail": "Email", "time": _dt(0.9, 18, 2), "action": None},
        {"event": "Opened", "detail": "First viewed · not paid", "time": _dt(0.05, 12, 0),
         "action": "Send reminder"},
    ])

    # -- Pending, sent not opened (mockups/02, row 3) --
    add("PAY-0004", "prekshap277@gmail.com", 5000.00, "pending", "Link", "Link", "Logo + brand kit", [
        {"event": "Created", "detail": "By Parveen", "time": _dt(0.08, 14, 10), "action": None},
        {"event": "Sent", "detail": "Email", "time": _dt(0.08, 14, 10), "action": "Send reminder"},
    ])

    # -- Pending, large invoice reminded 2 days ago (mockups/02, row 4) --
    add("PAY-0005", "modebebrian@gmail.com", 399754.00, "pending", "Invoice", "Invoice", "Q3 retainer", [
        {"event": "Created", "detail": "By Parveen", "time": _dt(6, 9, 0), "action": None},
        {"event": "Sent", "detail": "Invoice email", "time": _dt(6, 9, 0), "action": None},
        {"event": "Reminded", "detail": "Follow-up sent", "time": _dt(2, 9, 0), "action": "Send reminder"},
    ])

    # -- Latest paid today, Home screen (Ahmed M. / Fatima A. entries) --
    add("PAY-0006", "Ahmed M.", 3200.00, "paid", "Apple Pay", "Apple Pay", "Website deposit", [
        {"event": "Created", "detail": "By Parveen", "time": _dt(0.001, 9, 0), "action": None},
        {"event": "Sent", "detail": "WhatsApp template", "time": _dt(0.001, 9, 0), "action": None},
        {"event": "Paid", "detail": "Fees AED 96.00 · net AED 3,104.00", "time": _dt(0.001, 9, 2), "action": None},
        {"event": "Settling", "detail": "Expected in the next payout", "time": _dt(0.001, 9, 2), "action": None},
    ], fees=96.00)
    add("PAY-0007", "Fatima A.", 2400.00, "paid", "Card", "Card ····2210", "Consulting session", [
        {"event": "Created", "detail": "By Parveen", "time": _dt(0.02, 8, 44), "action": None},
        {"event": "Sent", "detail": "Payment link", "time": _dt(0.02, 8, 44), "action": None},
        {"event": "Paid", "detail": "Fees AED 72.00 · net AED 2,328.00", "time": _dt(0.02, 8, 46), "action": None},
        {"event": "Settling", "detail": "Expected in the next payout", "time": _dt(0.02, 8, 46), "action": None},
    ], fees=72.00)

    # -- Rest of the spread: more paid (to reach 10), failed (to reach 2),
    # expired (3) and a refund (1), across the last ~2 weeks.
    paid_extra = [
        ("PAY-0008", "Khalid M.", 1850.00, "Card", "Card ····9903", "Photography package", 1.3),
        ("PAY-0009", "Noor H.", 4100.00, "Tabby", "Tabby", "Furniture order", 2.5),
        ("PAY-0010", "Youssef R.", 3000.00, "Link", "Link", "Logo project", 3.4),
        ("PAY-0011", "Lina S.", 950.00, "Apple Pay", "Apple Pay", "Tailoring", 4.1),
        ("PAY-0012", "Mira Studio", 7200.00, "Invoice", "Invoice", "Interior styling", 5.6),
        ("PAY-0013", "Omar F.", 8000.00, "Card", "Card ····5521", "Website build", 8.2),
        ("PAY-0014", "Aisha K.", 620.00, "Card", "Card ····1187", "Skincare bundle", 9.7),
        ("PAY-0015", "Rami D.", 2750.00, "Tamara", "Tamara", "Furniture order", 12.4),
    ]
    for id_, customer, amount, method, method_detail, description, days_ago in paid_extra:
        fees = round(amount * 0.0305 + 1, 2)
        timeline = [
            {"event": "Created", "detail": "By Parveen", "time": _dt(days_ago, 10, 0), "action": None},
            {"event": "Sent", "detail": f"{method_detail} checkout", "time": _dt(days_ago, 10, 0), "action": None},
            {"event": "Paid", "detail": f"Fees AED {fees:.2f} · net AED {amount - fees:,.2f}",
             "time": _dt(days_ago, 10, 5), "action": None},
        ]
        # Payout settles 3 days after payment -- only far-enough-in-the-past
        # payments have actually reached that point yet; a payment paid more
        # recently than 3 days ago is still settling (see PAY-0002/6/7).
        if days_ago > 3.3:
            timeline.append({"event": "Paid out", "detail": "To Mashreq ····6789",
                              "time": _dt(days_ago - 3, 9, 0), "action": None})
        else:
            timeline.append({"event": "Settling", "detail": "Expected in the next payout",
                              "time": _dt(days_ago, 10, 5), "action": "Get it today · fee AED 21"})
        add(id_, customer, amount, "paid", method, method_detail, description, timeline, fees=fees)

    add("PAY-0016", "Grace T.", 1200.00, "failed", "Card", "Card ····3390", "Event styling", [
        {"event": "Created", "detail": "By Parveen", "time": _dt(3.4, 15, 20), "action": None},
        {"event": "Sent", "detail": "Payment link", "time": _dt(3.4, 15, 20), "action": None},
        {"event": "Payment attempt failed", "detail": "Card declined by issuing bank",
         "time": _dt(3.4, 15, 32), "action": "Send resume link", "failed": True},
    ])

    for id_, customer, amount, method, method_detail, description, days_ago in [
        ("PAY-0017", "Hana W.", 640.00, "Link", "Link", "Candle order", 15.0),
        ("PAY-0018", "Karim B.", 2100.00, "Link", "Link", "Drone footage", 18.0),
        ("PAY-0019", "Dana P.", 375.00, "Link", "Link", "Prints order", 21.0),
    ]:
        add(id_, customer, amount, "expired", method, method_detail, description, [
            {"event": "Created", "detail": "By Parveen", "time": _dt(days_ago, 11, 0), "action": None},
            {"event": "Sent", "detail": "Payment link", "time": _dt(days_ago, 11, 0), "action": None},
            {"event": "Expired", "detail": "Never opened · link expired after 7 days",
             "time": _dt(days_ago - 7, 11, 0), "action": None},
        ])

    add("PAY-0020", "Zayd A.", 1400.00, "refunded", "Card", "Card ····7734", "Cancelled order", [
        {"event": "Created", "detail": "By Parveen", "time": _dt(10.0, 10, 0), "action": None},
        {"event": "Sent", "detail": "Payment link", "time": _dt(10.0, 10, 0), "action": None},
        {"event": "Paid", "detail": "Fees AED 43.70 · net AED 1,356.30", "time": _dt(10.0, 10, 4), "action": None},
        {"event": "Refunded", "detail": "Full refund · order cancelled by customer",
         "time": _dt(8.0, 16, 0), "action": None},
    ], fees=43.70)

    return payments


def _status_dot_color(status: str) -> str:
    return STATUS_COLOR.get(status, "#9CA3AF")


def list_payments(status: Optional[str] = None, q: Optional[str] = None) -> Dict:
    """Every payment (optionally filtered by status and/or a customer/description
    search), plus the per-status counts a filter-chip row needs -- counts are
    always computed against the UNFILTERED set so chip counts don't shift
    around as you filter, matching the mockups (Design update - HTML/02)."""
    payments = _build_payments()
    counts = {"all": len(payments)}
    for s in STATUSES:
        counts[s] = sum(1 for p in payments if p["status"] == s)

    filtered = payments
    if status and status != "all":
        filtered = [p for p in filtered if p["status"] == status]
    if q:
        q_lower = q.strip().lower()
        filtered = [
            p for p in filtered
            if q_lower in p["customer"].lower() or q_lower in p["description"].lower()
        ]

    filtered = sorted(filtered, key=lambda p: p["created_at"], reverse=True)
    total_amount = round(sum(p["amount"] for p in filtered), 2)

    return {
        "payments": [_public_summary(p) for p in filtered],
        "counts": counts,
        "total_amount": total_amount,
    }


def get_payment(payment_id: str) -> Optional[Dict]:
    for p in _build_payments():
        if p["id"] == payment_id:
            return _public_detail(p)
    return None


def _public_summary(p: Dict) -> Dict:
    last_event = p["timeline"][-1]
    return {
        "id": p["id"],
        "customer": p["customer"],
        "amount": p["amount"],
        "status": p["status"],
        "status_label": STATUS_LABEL[p["status"]],
        "status_color": _status_dot_color(p["status"]),
        "method": p["method"],
        "detail": f"{p['method_detail']} · {_relative(last_event['time'])}",
    }


def _public_detail(p: Dict) -> Dict:
    return {
        "id": p["id"],
        "customer": p["customer"],
        "amount": p["amount"],
        "status": p["status"],
        "status_label": STATUS_LABEL[p["status"]],
        "status_color": _status_dot_color(p["status"]),
        "method": p["method"],
        "description": p["description"],
        "invoice_ref": p["invoice_ref"],
        "fees": p["fees"],
        "net_payout": p["net_payout"],
        "timeline": [
            {
                "event": t["event"],
                "detail": t["detail"],
                "time_label": t["time"].strftime("%a %d %b, %I:%M %p").replace(" 0", " "),
                "action": t.get("action"),
                "failed": t.get("failed", False),
            }
            for t in p["timeline"]
        ],
    }


def _relative(dt: datetime) -> str:
    delta = datetime.now() - dt
    seconds = delta.total_seconds()
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)} min ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)} h ago"
    days = int(seconds // 86400)
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days} days ago"
    return dt.strftime("%d %b")


def home_summary() -> Dict:
    """Aggregate stats for the Home screen: today's collections vs. the same
    time last week, a 7-day bar-chart series, what needs chasing, the next
    payout, and the latest few transactions."""
    payments = _build_payments()
    now = datetime.now()

    def paid_on(p, days_ago_max, days_ago_min=0):
        if p["status"] not in ("paid", "refunded"):
            return False
        paid_event = next((t for t in p["timeline"] if t["event"] == "Paid"), None)
        if not paid_event:
            return False
        age_days = (now - paid_event["time"]).total_seconds() / 86400
        return days_ago_min <= age_days < days_ago_max

    collected_today = round(sum(p["amount"] for p in payments if paid_on(p, 1)), 2)
    collected_last_week_same_day = round(sum(p["amount"] for p in payments if paid_on(p, 8, 7)), 2)

    last_7_days = []
    for i in range(6, -1, -1):
        day_total = sum(p["amount"] for p in payments if paid_on(p, i + 1, i))
        last_7_days.append(round(day_total, 2))
    max_day = max(last_7_days) or 1

    chasing = [
        p for p in payments
        if p["status"] == "pending"
        and (now - p["created_at"]).total_seconds() / 86400 >= 1
    ]
    chasing_total = round(sum(p["amount"] for p in chasing), 2)
    chasing_oldest_days = (
        max(int((now - p["created_at"]).total_seconds() // 86400) for p in chasing) if chasing else 0
    )

    settling = [
        p for p in payments
        if p["status"] == "paid" and p["timeline"][-1]["event"] == "Settling"
    ]
    next_payout = None
    if settling:
        soonest = min(settling, key=lambda p: p["timeline"][-1]["time"])
        payout_amount = round(sum(p["amount"] for p in settling), 2)
        payout_date = (now + timedelta(days=3)).strftime("%a %d %b")
        next_payout = {"amount": payout_amount, "date_label": payout_date}

    latest = sorted(payments, key=lambda p: p["timeline"][-1]["time"], reverse=True)[:3]

    hour = now.hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"

    return {
        "merchant_name": MERCHANT_NAME,
        "user_name": MERCHANT_USER,
        "greeting": f"{greeting}, {MERCHANT_USER}",
        "date_label": now.strftime("%A %d %b"),
        "collected_today": collected_today,
        "collected_comparison": (
            f"vs AED {collected_last_week_same_day:,.0f} this time last week"
            if collected_today else "Nothing yet today"
        ),
        "last_7_days": last_7_days,
        "last_7_days_max": max_day,
        "chasing": {
            "count": len(chasing),
            "total": chasing_total,
            "oldest_days": chasing_oldest_days,
        } if chasing else None,
        "next_payout": next_payout,
        "latest": [_public_summary(p) for p in latest],
    }
