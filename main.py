#!/usr/bin/env python3
"""EQLogParser CLI — parse an EverQuest log file and print a summary."""
from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
import json

from eqlogparser.config import Config
from eqlogparser.log_processor import process_file
from eqlogparser.record_manager import RecordManager


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse an EverQuest log file.")
    parser.add_argument("logfile", help="Path to the EQ log file")
    parser.add_argument("--player", default="", help="Your character name")
    parser.add_argument("--emu", action="store_true", help="Enable EMU parsing mode")
    parser.add_argument(
        "--output",
        choices=["summary", "json"],
        default="summary",
        help="Output format (default: summary)",
    )
    args = parser.parse_args()

    player = args.player
    if not player:
        import os, re
        m = re.match(r"eqlog_([^_]+)_", os.path.basename(args.logfile), re.IGNORECASE)
        if m:
            player = m.group(1)
    Config.player_name = player
    Config.is_emu_parsing_enabled = args.emu

    print(f"Parsing: {args.logfile}", file=sys.stderr)
    process_file(args.logfile)

    rm = RecordManager.instance()

    if args.output == "json":
        out: dict = {}
        for key in ("damage", "heal", "death", "loot", "spell_cast",
                    "received_spell", "resist", "random", "mez_break",
                    "special", "zone", "taunt"):
            records = rm.get_all(key)
            out[key] = [{"time": t, "record": asdict(r)} for t, r in records]
        print(json.dumps(out, indent=2, default=str))
    else:
        _print_summary(rm)


def _print_summary(rm: RecordManager) -> None:
    damage = rm.get_all("damage")
    heals = rm.get_all("heal")
    deaths = rm.get_all("death")
    loots = rm.get_all("loot")
    casts = rm.get_all("spell_cast")
    zones = rm.get_all("zone")
    taunts = rm.get_all("taunt")

    print(f"\n{'='*50}")
    print(f"  PARSE SUMMARY")
    print(f"{'='*50}")
    print(f"  Damage events   : {len(damage):,}")
    print(f"  Healing events  : {len(heals):,}")
    print(f"  Deaths          : {len(deaths):,}")
    print(f"  Loot records    : {len(loots):,}")
    print(f"  Spell casts     : {len(casts):,}")
    print(f"  Zone changes    : {len(zones):,}")
    print(f"  Taunts          : {len(taunts):,}")

    if damage:
        from collections import defaultdict
        dmg_by_attacker: dict[str, int] = defaultdict(int)
        for _, r in damage:
            dmg_by_attacker[r.attacker] += r.total
        top = sorted(dmg_by_attacker.items(), key=lambda x: x[1], reverse=True)[:10]
        print(f"\n  Top Damage Dealers:")
        for name, total in top:
            print(f"    {name:<30} {total:>15,}")

    if heals:
        from collections import defaultdict
        heal_by_healer: dict[str, int] = defaultdict(int)
        for _, r in heals:
            heal_by_healer[r.healer] += r.total
        top_h = sorted(heal_by_healer.items(), key=lambda x: x[1], reverse=True)[:10]
        print(f"\n  Top Healers:")
        for name, total in top_h:
            print(f"    {name:<30} {total:>15,}")

    if deaths:
        print(f"\n  Deaths:")
        for _, r in deaths[-10:]:
            print(f"    {r.killed} was slain by {r.killer}")

    if zones:
        print(f"\n  Zones visited:")
        seen = []
        for _, r in zones:
            if r.zone not in seen:
                seen.append(r.zone)
                print(f"    {r.zone}")

    print()


if __name__ == "__main__":
    main()
