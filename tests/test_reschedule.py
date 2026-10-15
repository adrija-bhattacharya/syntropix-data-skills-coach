"""Calendar feedback loop (claim F): reading the calendar back, adherence,
fatigue, micro-blocks and earliest-fit re-planning."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import api
from algorithms.reschedule import (
    MIN_BLOCK,
    LogEntry,
    Work,
    adherence,
    availability_windows,
    by_day,
    fatigue_index,
    naive_shift,
    parse_ics_busy,
    reschedule,
    typical_busy,
)

MON = date(2026, 1, 5)
ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART:20260105T183000Z
DTEND:20260105T200000Z
SUMMARY:Team dinner
END:VEVENT
BEGIN:VEVENT
DTSTART;TZID=Asia/Kolkata:20260106T090000
DTEND;TZID=Asia/Kolkata:20260106T173000
SUMMARY:Work
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:20260110
DTEND;VALUE=DATE:20260111
SUMMARY:Wedding
END:VEVENT
BEGIN:VEVENT
DTSTART:20260107T190000
DTEND:20260107T200000
TRANSP:TRANSPARENT
SUMMARY:Marked free
END:VEVENT
BEGIN:VEVENT
DTSTART:20260108T100000
DTEND:20260108T1
 10000
SUMMARY:Folded line
END:VEVENT
END:VCALENDAR"""


def office(d: date) -> tuple[datetime, datetime]:
    """A 09:00-17:30 workday."""
    base = datetime.combine(d, datetime.min.time())
    return base + timedelta(hours=9), base + timedelta(hours=17, minutes=30)


def work(*minutes: float) -> list[Work]:
    return [Work(f"w{i}", f"c{i}", f"lesson {i}", m) for i, m in enumerate(minutes)]


def test_ics_reader_handles_timed_all_day_free_and_folded_events() -> None:
    busy = parse_ics_busy(ICS)
    assert (datetime(2026, 1, 5, 18, 30), datetime(2026, 1, 5, 20, 0)) in busy
    assert (datetime(2026, 1, 6, 9, 0), datetime(2026, 1, 6, 17, 30)) in busy
    assert (datetime(2026, 1, 10), datetime(2026, 1, 11)) in busy  # all day
    assert (datetime(2026, 1, 8, 10, 0), datetime(2026, 1, 8, 11, 0)) in busy  # folded
    assert not any(a.day == 7 for a, _ in busy)  # "free" events don't block time


def test_adherence_tracks_recent_behaviour() -> None:
    assert adherence([]) == 1.0
    good = [LogEntry(MON + timedelta(days=i), 60, 60) for i in range(5)]
    bad = [LogEntry(MON + timedelta(days=i), 60, 0) for i in range(5)]
    assert adherence(good) == pytest.approx(1.0)
    assert adherence(bad) < 0.3
    late_slip = [*good, LogEntry(MON + timedelta(days=9), 60, 0)]
    early_slip = [LogEntry(MON - timedelta(days=9), 60, 0), *good]
    assert adherence(late_slip) < adherence(early_slip)  # recent days weigh more


def test_fatigue_is_relative_to_the_usual_day() -> None:
    busy = parse_ics_busy(ICS)
    b = by_day(busy)
    usual = typical_busy(b, MON, MON + timedelta(days=27))
    assert (
        fatigue_index(MON + timedelta(days=1), b[MON + timedelta(days=1)], 510) == 0.0
    )  # just a workday
    assert fatigue_index(MON, b[MON], usual[0]) > 0.0  # an extra evening event
    assert fatigue_index(date(2026, 1, 10), b[date(2026, 1, 10)], 0) == 1.0  # all-day wedding


def test_blocks_avoid_busy_time_respect_caps_and_keep_order() -> None:
    busy = parse_ics_busy(ICS)
    w = work(45, 120, 30, 90, 25)
    r = reschedule(w, start=MON, deadline=MON + timedelta(days=21), windows=availability_windows(),
                   busy=busy, base_cap=90, weekly_cap=300)  # fmt: skip
    assert r.feasible
    for blk in r.blocks:
        s = datetime.combine(blk.day, datetime.min.time()) + timedelta(minutes=blk.start)
        e = datetime.combine(blk.day, datetime.min.time()) + timedelta(minutes=blk.end)
        assert not any(a < e and z > s for a, z in busy), blk
        assert blk.end - blk.start >= MIN_BLOCK or blk.part == blk.parts
    # prerequisite order: no block of lesson k+1 before the last block of lesson k
    order = [int(b.work_id[1:]) for b in r.blocks]
    assert order == sorted(order)
    # the 120-minute lesson had to be split
    assert max(b.parts for b in r.blocks if b.work_id == "w1") > 1
    # no week over the offered hours, no day over its cap
    weeks: dict[tuple[int, int], int] = {}
    for b in r.blocks:
        k = b.day.isocalendar()[:2]
        weeks[k] = weeks.get(k, 0) + b.end - b.start
    assert max(weeks.values()) <= 300
    assert all(d.study_minutes <= d.cap_minutes + 1 for d in r.days)
    assert all(b.day != date(2026, 1, 10) for b in r.blocks)  # the wedding day stays free


def test_low_adherence_plans_more_time_and_week_done_counts() -> None:
    w = work(60, 60, 60)
    full = reschedule(
        w, start=MON, deadline=MON + timedelta(days=30), windows=availability_windows()
    )
    half = reschedule(
        w,
        start=MON,
        deadline=MON + timedelta(days=30),
        windows=availability_windows(),
        adherence_rate=0.5,
    )
    assert half.remaining_minutes == pytest.approx(2 * full.remaining_minutes)
    wed = MON + timedelta(days=2)
    spent = reschedule(
        w, start=wed, deadline=wed + timedelta(days=30), windows=availability_windows(),
        weekly_cap=200, week_done=180,
    )  # fmt: skip
    first_week = sum(
        b.end - b.start for b in spent.blocks if b.day.isocalendar()[:2] == wed.isocalendar()[:2]
    )
    assert first_week <= 20


def test_earliest_fit_never_finishes_a_prefix_later_than_the_fixed_calendar() -> None:
    w = work(40, 40, 40, 40, 40, 40)
    windows = availability_windows()
    smart = reschedule(w, start=MON, deadline=MON + timedelta(days=40), windows=windows)
    fixed = naive_shift(w, start=MON, deadline=MON + timedelta(days=40), windows=windows)

    def finish(blocks) -> dict[str, tuple[date, int]]:  # type: ignore[no-untyped-def]
        out: dict[str, tuple[date, int]] = {}
        for b in blocks:
            out[b.work_id] = max(out.get(b.work_id, (b.day, b.end)), (b.day, b.end))
        return out

    a, b = finish(smart.blocks), finish(fixed.blocks)
    assert all(a[k] <= b[k] for k in a)


def test_infeasible_reports_the_hours_needed() -> None:
    r = reschedule(work(*[90] * 20), start=MON, deadline=MON + timedelta(days=6),
                   windows=availability_windows(), weekly_cap=180)  # fmt: skip
    assert not r.feasible and r.unplaced_minutes > 0 and r.hours_per_week_needed > 3
    assert any("hours a week" in x for x in r.reasons)


def test_api_reads_back_the_log_and_the_calendar() -> None:
    client = TestClient(api.app)
    goals = client.post("/resolve", json={"goal": "sql"}).json()["goals"]
    today = date.today()
    body = {
        "learner_id": "loop", "goals": goals, "goal": "sql",
        "deadline": (today + timedelta(days=60)).isoformat(), "hours_per_week": 6,
        "plan_start": (today - timedelta(days=7)).isoformat(),
    }  # fmt: skip
    base = client.post("/reschedule", json=body).json()
    assert base["past_days"] and base["blocks"] and base["adherence"] == 1.0
    log = [
        {"day": d["day"], "planned_minutes": d["planned_minutes"], "done_minutes": 0}
        for d in base["past_days"]
    ]
    missed = client.post("/reschedule", json={**body, "log": log}).json()
    assert missed["adherence"] < 0.5
    assert missed["remaining_minutes"] > base["remaining_minutes"]
    assert any("planned time" in x for x in missed["reasons"])
    t = today + timedelta(days=1)
    ics = (
        "BEGIN:VCALENDAR\nBEGIN:VEVENT\n"
        f"DTSTART:{t:%Y%m%d}T000000\nDTEND:{t:%Y%m%d}T235900\nSUMMARY:Busy all day\n"
        "END:VEVENT\nEND:VCALENDAR"
    )
    busy = client.post("/reschedule", json={**body, "busy_ics": ics}).json()
    assert busy["busy_events"] == 1 and t.isoformat() in busy["busy_spans"]
    assert all(b["day"] != t.isoformat() for b in busy["blocks"])


def test_short_block_days_still_take_mid_sized_lessons() -> None:
    # a normal work week, plus an evening event that makes Monday dense (15-minute
    # blocks): a 25-minute lesson must still be placed on Monday, not skipped
    days = [MON + timedelta(days=k) for k in range(5)]
    busy = [office(d) for d in days]
    busy.append((datetime(2026, 1, 5, 18), datetime(2026, 1, 5, 21, 30)))
    r = reschedule(work(25), start=MON, deadline=MON + timedelta(days=3),
                   windows=availability_windows(), busy=busy, base_cap=90)  # fmt: skip
    assert r.days[0].max_block == MIN_BLOCK and r.blocks and r.blocks[0].day == MON


def test_a_normal_workday_is_not_busy_when_the_calendar_covers_only_a_few_weeks() -> None:
    work_days = [
        MON + timedelta(days=k) for k in range(21) if (MON + timedelta(days=k)).weekday() < 5
    ]
    busy = [office(d) for d in work_days]
    r = reschedule(work(60, 60), start=MON, deadline=MON + timedelta(days=120),
                   windows=availability_windows(), busy=busy)  # fmt: skip
    assert all(d.fatigue == 0.0 for d in r.days if d.day in work_days)
    assert not any("busy day" in x for x in r.reasons)
