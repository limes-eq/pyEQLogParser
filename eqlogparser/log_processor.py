from __future__ import annotations
import os

from eqlogparser.date_util import parse_standard_date, to_double
from eqlogparser.models import LineData
from eqlogparser.parsing import (
    chat_line_parser,
    pre_line_parser,
    damage_line_parser,
    healing_line_parser,
    misc_line_parser,
    cast_line_parser,
)


def process_line(line: str, line_number: int = 0) -> LineData | None:
    if len(line) <= 28:
        return None
    dt = parse_standard_date(line)
    if dt is None:
        return None
    begin_time = to_double(dt)
    return process_action(line[27:], begin_time, line_number)


def process_action(action: str, begin_time: float, line_number: int = 0) -> LineData | None:
    double_action: str | None = None
    double_time: float = 0.0
    bracket = action.find("[")
    if bracket > -1 and len(action) > bracket + 28 and action[bracket + 25] == "]":
        tail = action[bracket:]
        maybe = parse_standard_date(tail)
        if maybe is not None:
            double_action = tail[27:]
            double_time = to_double(maybe)
            action = action[:bracket]

    line_data = LineData(action=action, begin_time=begin_time, line_number=line_number)

    if chat_line_parser.parse_chat_type(line_data.action) is None:
        line_data.split = line_data.action.split(" ")
        if pre_line_parser.need_processing(line_data):
            if not damage_line_parser.process(line_data):
                if not healing_line_parser.process(line_data):
                    if not misc_line_parser.process(line_data):
                        cast_line_parser.process(line_data)

    if double_action is not None:
        process_action(double_action, double_time, line_number)

    return line_data


def _find_cutoff_offset(f, size: int, cutoff_time: float) -> int:
    """Binary search an open binary file for the first line with timestamp >= cutoff_time."""
    lo, hi = 0, size
    while hi - lo > 8192:
        mid = (lo + hi) // 2
        f.seek(mid)
        f.readline()  # align to next line boundary
        line = f.readline().decode("utf-8", errors="replace")
        if not line:
            break
        dt = parse_standard_date(line)
        if dt is None or to_double(dt) < cutoff_time:
            lo = f.tell()
        else:
            hi = mid
    return lo


def process_file(path: str, since: float = 0.0) -> None:
    offset = 0
    if since > 0:
        size = os.path.getsize(path)
        with open(path, "rb") as bf:
            # Peek at the first line — if the log starts after the cutoff, skip search
            first_line = bf.readline().decode("utf-8", errors="replace")
            first_dt = parse_standard_date(first_line)
            if first_dt is not None and to_double(first_dt) < since:
                offset = _find_cutoff_offset(bf, size, since)

    with open(path, encoding="utf-8", errors="replace", buffering=1 << 20) as fh:
        if offset > 0:
            fh.seek(offset)
        for line_number, line in enumerate(fh):
            process_line(line.rstrip("\n"), line_number)
