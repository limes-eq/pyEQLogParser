from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field

from eqlogparser.config import Config
from eqlogparser.player_manager import PlayerManager
from eqlogparser.record_manager import RecordManager

FIGHT_GAP_SECONDS = 30
MIN_FIGHT_EVENTS = 2
_TIMELINE_BUCKET = 6
_CRIT_MASK = 2  # matches line_modifiers_parser.CRIT


def _is_player_side(name: str) -> bool:
    if not name:
        return False
    pm = PlayerManager.instance()
    if pm.is_verified_player(name) or pm.is_verified_pet(name):
        return True
    if Config.player_name and name == Config.player_name:
        return True
    return PlayerManager.is_possible_player_name(name)


@dataclass
class Fight:
    id: int
    mob: str
    start_time: float
    end_time: float
    damage_dealt: list = field(default_factory=list)
    damage_taken: list = field(default_factory=list)
    heals: list = field(default_factory=list)

    @property
    def duration(self) -> float:
        return max(self.end_time - self.start_time, 1.0)

    @property
    def total_damage(self) -> int:
        return sum(r.total for _, r in self.damage_dealt)


def detect_fights(rm: RecordManager) -> list[Fight]:
    damage_records = rm.get_all("damage")
    heal_records = rm.get_all("heal")

    mob_state: dict[str, tuple[int, float]] = {}
    sessions: dict[str, list] = defaultdict(list)

    for t, rec in damage_records:
        attacker_is_player = rec.attacker_owner is not None or _is_player_side(rec.attacker)
        defender_is_player = rec.defender_owner is not None or _is_player_side(rec.defender)

        if attacker_is_player and not defender_is_player:
            mob, direction = rec.defender, "dealt"
        elif defender_is_player and not attacker_is_player:
            mob, direction = rec.attacker, "taken"
        else:
            continue

        if not mob:
            continue

        prev_id, prev_time = mob_state.get(mob, (0, None))
        if prev_time is None or (t - prev_time) > FIGHT_GAP_SECONDS:
            session_id = prev_id + 1
        else:
            session_id = prev_id
        mob_state[mob] = (session_id, t)

        key = f"{mob}\x00{session_id}"
        sessions[key].append((t, rec, direction))

    fights: list[Fight] = []
    fight_id = 0

    for key, records in sorted(sessions.items(), key=lambda x: x[1][0][0]):
        mob = key.split("\x00", 1)[0]
        times = [t for t, _, _ in records]
        start_t, end_t = min(times), max(times)

        dealt = [(t, r) for t, r, d in records if d == "dealt"]
        taken = [(t, r) for t, r, d in records if d == "taken"]

        if len(dealt) + len(taken) < MIN_FIGHT_EVENTS:
            continue

        fight_heals = [
            (t, r) for t, r in heal_records
            if start_t - 5 <= t <= end_t + 15
        ]

        fights.append(Fight(
            id=fight_id,
            mob=mob,
            start_time=start_t,
            end_time=end_t,
            damage_dealt=dealt,
            damage_taken=taken,
            heals=fight_heals,
        ))
        fight_id += 1

    return fights


def aggregate_fights(fights: list[Fight]) -> dict:
    if not fights:
        return {
            "dps": [], "healing": [], "tanking": [],
            "duration": 0, "total_damage": 0,
            "dps_timeline": {}, "timeline_bucket": _TIMELINE_BUCKET,
        }

    total_duration = max(sum(f.duration for f in fights), 1.0)

    # DPS
    def _new_dps_entry():
        return {
            "total": 0, "hits": 0, "crits": 0, "max_hit": 0,
            "by_type": defaultdict(int),
            "by_spell": defaultdict(lambda: {"total": 0, "type": "", "hits": 0, "crits": 0, "max_hit": 0}),
        }

    dps_totals: dict[str, dict] = defaultdict(_new_dps_entry)
    for f in fights:
        for _, rec in f.damage_dealt:
            name = rec.attacker_owner or rec.attacker
            dps_totals[name]["total"] += rec.total
            dps_totals[name]["by_type"][rec.type] += rec.total
            spell_key = rec.sub_type if rec.sub_type else rec.type
            sp = dps_totals[name]["by_spell"][spell_key]
            sp["total"] += rec.total
            if rec.total > 0:
                dps_totals[name]["hits"] += 1
                sp["hits"] += 1
                if rec.total > dps_totals[name]["max_hit"]:
                    dps_totals[name]["max_hit"] = rec.total
                if rec.total > sp["max_hit"]:
                    sp["max_hit"] = rec.total
                if rec.modifiers_mask != -1 and (rec.modifiers_mask & _CRIT_MASK):
                    dps_totals[name]["crits"] += 1
                    sp["crits"] += 1
                sp["type"] = rec.type

    grand_dmg = sum(v["total"] for v in dps_totals.values()) or 1
    dps_rows = sorted([
        {
            "name": name,
            "total": d["total"],
            "dps": round(d["total"] / total_duration, 1),
            "hits": d["hits"],
            "avg_hit": round(d["total"] / d["hits"]) if d["hits"] > 0 else 0,
            "max_hit": d["max_hit"],
            "crit_rate": round(d["crits"] / d["hits"] * 100, 1) if d["hits"] > 0 else 0.0,
            "pct": round(d["total"] / grand_dmg * 100, 1),
            "by_type": {k: v for k, v in sorted(d["by_type"].items(), key=lambda x: -x[1])},
            "by_spell": {
                k: {
                    **v,
                    "avg_hit": round(v["total"] / v["hits"]) if v["hits"] > 0 else 0,
                    "crit_rate": round(v["crits"] / v["hits"] * 100, 1) if v["hits"] > 0 else 0.0,
                }
                for k, v in sorted(d["by_spell"].items(), key=lambda x: -x[1]["total"])
            },
        }
        for name, d in dps_totals.items()
    ], key=lambda x: -x["total"])

    # Healing
    heal_totals: dict[str, int] = defaultdict(int)
    for f in fights:
        for _, rec in f.heals:
            heal_totals[rec.healer] += rec.total

    grand_heal = sum(heal_totals.values()) or 1
    heal_rows = sorted([
        {
            "name": name,
            "total": total,
            "hps": round(total / total_duration, 1),
            "pct": round(total / grand_heal * 100, 1),
        }
        for name, total in heal_totals.items()
    ], key=lambda x: -x["total"])

    # Tanking
    tank_totals: dict[str, dict] = defaultdict(lambda: {"total": 0, "by_type": defaultdict(int)})
    for f in fights:
        for _, rec in f.damage_taken:
            name = rec.defender
            tank_totals[name]["total"] += rec.total
            tank_totals[name]["by_type"][rec.type] += rec.total

    grand_taken = sum(v["total"] for v in tank_totals.values()) or 1
    tank_rows = sorted([
        {
            "name": name,
            "total": d["total"],
            "dtps": round(d["total"] / total_duration, 1),
            "pct": round(d["total"] / grand_taken * 100, 1),
            "by_type": {k: v for k, v in sorted(d["by_type"].items(), key=lambda x: -x[1])},
        }
        for name, d in tank_totals.items()
    ], key=lambda x: -x["total"])

    return {
        "dps": dps_rows,
        "healing": heal_rows,
        "tanking": tank_rows,
        "duration": round(total_duration),
        "total_damage": sum(f.total_damage for f in fights),
        "dps_timeline": _build_dps_timeline(fights),
        "timeline_bucket": _TIMELINE_BUCKET,
    }


def _build_dps_timeline(fights: list[Fight]) -> dict:
    if not fights:
        return {}
    start = min(f.start_time for f in fights)
    end = max(f.end_time for f in fights)
    n_buckets = int((end - start) / _TIMELINE_BUCKET) + 2

    player_buckets: dict[str, list[int]] = {}
    for f in fights:
        for t, rec in f.damage_dealt:
            if rec.total <= 0:
                continue
            name = rec.attacker_owner or rec.attacker
            if name not in player_buckets:
                player_buckets[name] = [0] * n_buckets
            idx = min(int((t - start) / _TIMELINE_BUCKET), n_buckets - 1)
            player_buckets[name][idx] += rec.total

    return {
        name: [[i * _TIMELINE_BUCKET, round(dmg / _TIMELINE_BUCKET)]
               for i, dmg in enumerate(buckets)]
        for name, buckets in player_buckets.items()
    }
