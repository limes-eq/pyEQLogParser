from datetime import datetime

# EQ log format: [Wed Jan 17 23:35:13 2024] action
# Slice [5:25] = "Jan 17 23:35:13 2024"

_FMT = "%b %d %H:%M:%S %Y"

_MONTH_MAP = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def parse_standard_date(line: str) -> datetime | None:
    if len(line) < 27 or line[0] != "[":
        return None
    try:
        # "Jan 17 23:35:13 2024"
        #  0   4  7        16
        s = line[5:25]
        month = _MONTH_MAP.get(s[0:3])
        if month is None:
            return None
        day   = int(s[4:6])
        hour  = int(s[7:9])
        minute = int(s[10:12])
        second = int(s[13:15])
        year  = int(s[16:20])
        return datetime(year, month, day, hour, minute, second)
    except (ValueError, IndexError):
        return None


def to_double(dt: datetime) -> float:
    return dt.timestamp()
