import pytest
from fastapi.testclient import TestClient

from kura.api.app import create_app
from kura.auth.base import Identity
from kura.auth.static import StaticTokenVerifier
from kura.core.ics import merge_feed

from conftest import ADMIN

EVENT_A = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//x//
BEGIN:VTIMEZONE
TZID:Asia/Tokyo
BEGIN:STANDARD
TZOFFSETFROM:+0900
TZOFFSETTO:+0900
TZNAME:JST
DTSTART:19700101T000000
END:STANDARD
END:VTIMEZONE
BEGIN:VEVENT
UID:a@example.jp
DTSTAMP:20260610T000000Z
DTSTART;TZID=Asia/Tokyo:20260615T100000
SUMMARY:定例会議
END:VEVENT
END:VCALENDAR
"""

EVENT_B = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//x//
BEGIN:VEVENT
UID:b@example.jp
DTSTAMP:20260610T000000Z
DTSTART:20260620T010000Z
SUMMARY:納品
END:VEVENT
END:VCALENDAR
"""


def test_merge_feed_collects_events_and_timezones():
    feed = merge_feed("行事", [EVENT_A, EVENT_B, EVENT_A])
    assert feed.count("BEGIN:VEVENT") == 3
    # VTIMEZONE は TZID ごとに一つ
    assert feed.count("BEGIN:VTIMEZONE") == 1
    assert "X-WR-CALNAME:行事" in feed
    assert feed.startswith("BEGIN:VCALENDAR\r\n")
    assert feed.endswith("END:VCALENDAR\r\n")


def test_feed_endpoint(engine):
    client = TestClient(create_app(engine, StaticTokenVerifier(
        {"t": Identity(ADMIN, "管理者", "a@example.jp")})))
    h = {"Authorization": "Bearer t"}

    # カレンダー＝ディレクトリ、イベント＝.ics ファイル。既存のファイル API で書ける
    client.post("/api/dir", params={"path": "行事"}, headers=h)
    client.put("/api/file", params={"path": "行事/a.ics"},
               content=EVENT_A.encode(), headers=h)
    client.put("/api/file", params={"path": "行事/b.ics"},
               content=EVENT_B.encode(), headers=h)
    client.put("/api/file", params={"path": "行事/メモ.txt"},
               content="ics ではない".encode(), headers=h)

    token = client.post("/api/links", json={"path": "行事", "perm": "r"},
                        headers=h).json()["token"]

    r = client.get(f"/feed/{token}.ics")  # 認証ヘッダなし＝購読クライアント
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/calendar")
    assert "定例会議" in r.text and "納品" in r.text
    assert "ics ではない" not in r.text

    assert client.get("/feed/garbage.ics").status_code == 404


def test_feed_requires_dir_target(engine):
    engine.mkdir(ADMIN, "d")
    engine.write_file(ADMIN, "d/f.ics", EVENT_B.encode())
    _, token = engine.create_link(ADMIN, "d/f.ics", "r")
    with pytest.raises(Exception):
        engine.ics_feed(token)
