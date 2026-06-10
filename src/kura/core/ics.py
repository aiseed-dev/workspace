"""ICS 購読フィードの生成（spec 4.6）。

カレンダー＝ディレクトリ、イベント＝その中の .ics ファイル。権限は xattr モデルそのまま。
配信は読み取り専用フィード：ディレクトリ内の .ics から VEVENT（と VTIMEZONE）を集めて
一つの VCALENDAR にする。パースはブロックの切り出しに留め、中身は素通しする——
保存形式が標準（.ics）であることが互換性を担保する。
"""

PRODID = "-//aiseed//kura//JA"


def _blocks(text: str, kind: str) -> list[str]:
    lines = text.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    buf: list[str] | None = None
    for line in lines:
        if line == f"BEGIN:{kind}":
            buf = [line]
        elif line == f"END:{kind}" and buf is not None:
            buf.append(line)
            out.append("\n".join(buf))
            buf = None
        elif buf is not None:
            buf.append(line)
    return out


def merge_feed(name: str, ics_texts: list[str]) -> str:
    """複数の .ics を一つの購読フィード（VCALENDAR）にまとめる。"""
    timezones: dict[str, str] = {}
    events: list[str] = []
    for text in ics_texts:
        for tz in _blocks(text, "VTIMEZONE"):
            tzid = next((line.split(":", 1)[1] for line in tz.split("\n")
                         if line.startswith("TZID")), tz)
            timezones.setdefault(tzid, tz)
        events.extend(_blocks(text, "VEVENT"))

    parts = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{name}",
        *timezones.values(),
        *events,
        "END:VCALENDAR",
    ]
    return "\r\n".join("\n".join(parts).split("\n")) + "\r\n"
