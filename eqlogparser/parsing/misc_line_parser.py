from __future__ import annotations
import logging

from eqlogparser.models import (LineData, LootRecord, RandomRecord, ResistRecord,
                                  MezBreakRecord)
from eqlogparser.stats_util import parse_uint, UINT_MAX
from eqlogparser.text_utils import to_upper

log = logging.getLogger(__name__)

_CURRENCY = ["Platinum", "Gold", "Silver", "Copper"]
_RATES: dict[str, int] = {"p": 1000, "g": 100, "s": 10, "c": 1}
_LOOTED_FROM_TRIM = "-."

_STRUCK_BY_TYPES = frozenset([
    "afflicted", "angered", "assaulted", "beset", "bound", "burned", "consumed", "cursed",
    "crushed", "cut", "drained", "engulfed", "enveloped", "chilled", "frozen", "hit",
    "immolated", "impaled", "pierced", "pummeled", "rent", "seared", "shaken", "slashed",
    "sliced", "stabbed", "surrounded", "struck", "stunned", "targeted", "withered",
])

_random_player: str | None = None
_last_line: int = -1


def process(line_data: LineData) -> bool:
    global _random_player, _last_line
    handled = False
    try:
        split = line_data.split
        if not split or len(split) < 2:
            return False

        from eqlogparser.config import Config
        from eqlogparser.player_manager import PlayerManager
        from eqlogparser.record_manager import RecordManager
        from eqlogparser.data_manager import DataManager

        looter: str | None = None
        awak_index = left_index = looted_index = master_loot_index = receive_index = -1
        is_index = items_index = -1
        old_random = False

        for i in range(len(split)):
            if handled:
                break
            w = split[i]

            if i == 0 and w.startswith("--"):
                looter = Config.player_name if w == "--You" else w.lstrip("-")

            elif i == 0 and (
                (w == "" and len(split) > 2 and split[1] == "AFK" and _parse_who(split, 2))
                or (w.startswith("[") and _parse_who(split, 0))
            ):
                result = _parse_who(split, 2 if (w == "" and len(split) > 2 and split[1] == "AFK") else 0)
                if result:
                    who, who_class = result
                    PlayerManager.instance().add_verified_player(who, line_data.begin_time)
                    if DataManager.instance().is_valid_class_name(who_class):
                        PlayerManager.instance().set_active_player_class(who, who_class, 1, line_data.begin_time)
                handled = True

            else:
                if w == "**A":
                    if (i == 0 and len(split) > 6 and split[1] == "Magic" and split[2] == "Die"
                            and split[4] == "rolled" and len(split[6]) > 2):
                        player = split[6][:-1]
                        if len(split) == 25 and split[12] == "number" and len(split[16]) > 1 and len(split[24]) > 1:
                            to_s = split[16][:-1]
                            rolled_s = split[24][:-1]
                            from_n = parse_uint(split[14])
                            to_n = parse_uint(to_s)
                            rolled_n = parse_uint(rolled_s)
                            if from_n != UINT_MAX and to_n != UINT_MAX and rolled_n != UINT_MAX:
                                rec = RandomRecord(player=player, rolled=rolled_n, to=to_n, from_num=from_n)
                                RecordManager.instance().add_random(rec, line_data.begin_time)
                                handled = True
                        elif len(split) == 7:
                            old_random = True
                            _random_player = player
                            _last_line = line_data.line_number

                elif w == "**It":
                    if (_random_player and (_last_line + 1) == line_data.line_number
                            and len(split) == 18 and split[5] == "number"
                            and len(split[9]) > 1 and len(split[17]) > 1):
                        to_s = split[9][:-1]
                        rolled_s = split[17][:-1]
                        from_n = parse_uint(split[7])
                        to_n = parse_uint(to_s)
                        rolled_n = parse_uint(rolled_s)
                        if from_n != UINT_MAX and to_n != UINT_MAX and rolled_n != UINT_MAX:
                            rec = RandomRecord(player=_random_player, rolled=rolled_n, to=to_n, from_num=from_n)
                            RecordManager.instance().add_random(rec, line_data.begin_time)
                            handled = True

                elif w == "awakened":
                    awak_index = i
                elif w == "is":
                    is_index = i
                elif w == "left":
                    left_index = i
                elif w == "looted":
                    looted_index = i
                elif w == "resisted":
                    if len(split) > i + 3 and len(split[i + 1]) > 2 and split[-1].endswith("!"):
                        npc = to_upper(" ".join(split[:i]))
                        if split[i + 1] != "your":
                            if split[i + 2] == "pet's":
                                atk = split[i + 1] + " pet"
                                spell = " ".join(split[i + 3:len(split) - (i + 3)]).rstrip("!")
                                # simpler
                                spell = " ".join(split[i + 3:]).rstrip("!")
                            else:
                                atk = split[i + 1][:-2]
                                spell = " ".join(split[i + 2:]).rstrip("!")
                        else:
                            atk = Config.player_name
                            spell = " ".join(split[i + 2:]).rstrip("!")
                        rec = ResistRecord(attacker=atk, defender=npc, spell=spell)
                        RecordManager.instance().add_resist(rec, line_data.begin_time)
                        spell_data = DataManager.instance().get_det_spell_by_name(rec.spell)
                        if spell_data and spell_data.resist:
                            RecordManager.instance().update_npc_spell_stats(rec.defender, spell_data.resist, True)
                        handled = True

                elif w == "item(s):":
                    if len(split) > 9 and split[1] == "won" and split[4] == "roll":
                        items_index = i

                elif w == "loaded":
                    if (len(split) >= 7 and i == 2 and split[-1] == "set." and split[3] == "your"
                            and split[1] == "successfully" and split[0] == "You"):
                        class_name = " ".join(split[4:1 + (len(split) - 7) + 4])
                        if DataManager.instance().is_valid_class_name(class_name):
                            PlayerManager.instance().set_active_player_class(Config.player_name, class_name, 1, line_data.begin_time)
                        handled = True

                elif w == "looter,":
                    master_loot_index = (i + 1) if (i == 2 and split[1] == "master" and split[0] == "The") else -1

                elif w == "receive":
                    receive_index = i if (i == 1 and split[0] == "You") else -1

                elif w == "with":
                    if items_index > -1 and len(split) > i + 2 and split[i + 2] == "roll":
                        looter = Config.player_name if split[0].lower() == "you" else split[0]
                        item = " ".join(split[items_index + 1:i])
                        PlayerManager.instance().add_verified_player(looter, line_data.begin_time)
                        rec = LootRecord(item=item, player=looter, quantity=0, is_currency=False, npc="Won Roll (Not Looted)")
                        RecordManager.instance().add_loot(rec, line_data.begin_time)
                        handled = True

                elif w == "reflected":
                    if (len(split) > 6 and i >= 6 and i + 2 < len(split)
                            and split[0].startswith(Config.player_name)
                            and split[i - 1] == "been" and split[i - 2] == "has"
                            and split[i - 3] == "spell" and split[i + 1] == "by"):
                        npc = to_upper(" ".join(split[i + 2:]).rstrip("."))
                        RecordManager.instance().update_npc_spell_stats(npc, "reflected", True)
                        handled = True

                elif w == "by":
                    if (awak_index > -1 and awak_index == i - 1 and len(split) > 5
                            and split[i - 2] == "been" and split[i - 3] == "has"):
                        awakened = to_upper(" ".join(split[:i - 3]))
                        breaker = to_upper(" ".join(split[i + 1:]).rstrip("."))
                        RecordManager.instance().add_mez_break(MezBreakRecord(breaker=breaker, awakened=awakened), line_data.begin_time)
                        handled = True
                    elif is_index > 0 and split[i - 1] in _STRUCK_BY_TYPES:
                        return False

                elif w == "on":
                    if looter and left_index == 1 and len(split) > 4:
                        item = " ".join(split[3:i])
                        npc = to_upper(" ".join(split[i + 1:]).strip(_LOOTED_FROM_TRIM).replace("'s corpse", "").strip())
                        rec = LootRecord(item=item, player=looter, quantity=0, is_currency=False, npc=f"{npc} (Left on Chest)")
                        RecordManager.instance().add_loot(rec, line_data.begin_time)
                        handled = True

                elif w == "from":
                    if master_loot_index > -1 and looted_index > master_loot_index and len(split) > looted_index + 1 and len(split) > 5:
                        name = split[3].rstrip(",") or Config.player_name
                        item_out, count_out = _parse_currency(split, looted_index + 1, i)
                        if item_out:
                            PlayerManager.instance().add_verified_player(name, line_data.begin_time)
                            rec = LootRecord(item=item_out, player=name, quantity=count_out, is_currency=True)
                            RecordManager.instance().add_loot(rec, line_data.begin_time)
                            handled = True
                    elif looter and looted_index == 2 and len(split) > 4:
                        count = 1 if split[3][0] == "a" else parse_uint(split[3])
                        item = " ".join(split[4:i])
                        npc = to_upper(" ".join(split[i + 1:]).strip(_LOOTED_FROM_TRIM).replace("'s corpse", "").strip())
                        if 0 < count < UINT_MAX:
                            PlayerManager.instance().add_verified_player(looter, line_data.begin_time)
                            rec = LootRecord(item=item, player=looter, quantity=count, is_currency=False, npc=npc)
                            RecordManager.instance().add_loot(rec, line_data.begin_time)
                            handled = True
                    elif receive_index > -1 and i > receive_index and not looter:
                        item_out, count_out = _parse_currency(split, 2, i)
                        if item_out:
                            rec = LootRecord(item=item_out, player=Config.player_name, quantity=count_out, is_currency=True)
                            RecordManager.instance().add_loot(rec, line_data.begin_time)
                            handled = True

                elif w == "given":
                    if split[i - 1] == "was" and len(split) == i + 3 and split[i + 1] == "to":
                        player_name = split[i + 2]
                        if len(player_name) > 3:
                            p = player_name[:-1]
                            p = Config.player_name if p.lower() == "you" else p
                            PlayerManager.instance().add_verified_player(p, line_data.begin_time)
                            item = " ".join(split[1:i - 1])
                            rec = LootRecord(item=item, player=p, quantity=0, is_currency=False, npc="Given (Not Looted)")
                            RecordManager.instance().add_loot(rec, line_data.begin_time)
                            handled = True

                elif w in ("split.", "split"):
                    if receive_index > -1 and split[i - 1] == "your" and split[i - 2] == "as":
                        item_out, count_out = _parse_currency(split, 2, i - 2)
                        if item_out:
                            rec = LootRecord(item=item_out, player=Config.player_name, quantity=count_out, is_currency=True)
                            RecordManager.instance().add_loot(rec, line_data.begin_time)
                            handled = True

            if not old_random:
                _random_player = None
                _last_line = -1

        if not handled and looter and looted_index == 2 and len(split) > 4:
            item = " ".join(split[4:])
            if len(item) > 3 and item.endswith(".--"):
                count = 1 if split[3][0] == "a" else parse_uint(split[3])
                item = item[:-3]
                if 0 < count < UINT_MAX:
                    from eqlogparser.player_manager import PlayerManager
                    from eqlogparser.record_manager import RecordManager
                    PlayerManager.instance().add_verified_player(looter, line_data.begin_time)
                    rec = LootRecord(item=item, player=looter, quantity=count, is_currency=False, npc="")
                    RecordManager.instance().add_loot(rec, line_data.begin_time)
                    handled = True

    except Exception:
        log.exception("misc_line_parser.process")

    return handled


def _parse_currency(pieces: list[str], start_index: int, to_index: int) -> tuple[str | None, int]:
    items: list[str] = []
    count = 0
    i = start_index
    while i < to_index:
        if pieces[i] == "and":
            i += 1
            continue
        if i + 1 >= to_index:
            return None, 0
        value = parse_uint(pieces[i])
        currency_type = next((c for c in _CURRENCY if pieces[i + 1].lower().startswith(c.lower())), None)
        if value == UINT_MAX or currency_type is None:
            return None, 0
        items.append(pieces[i] + " " + currency_type)
        rate = _RATES.get(pieces[i + 1][0].lower(), 0)
        count += value * rate
        i += 2

    return (", ".join(items) if items else None), count


def _parse_who(split: list[str], start: int) -> tuple[str, str] | None:
    if start >= len(split):
        return None
    w = split[start]
    if not w.startswith("[") or len(w) <= 1 or len(split) <= start + 4:
        return None
    if w == "[ANONYMOUS]":
        if start + 1 < len(split):
            return split[start + 1], ""
        return None
    level_s = w[1:]
    try:
        int(level_s)
    except ValueError:
        return None
    class_start = -1
    for i in range(start + 1, len(split)):
        if split[i].startswith("("):
            class_start = i
        if class_start > -1 and split[i].endswith(")]"):
            class_name = " ".join(split[class_start:i + 1])
            if len(class_name) > 4:
                class_name = class_name[1:-2]
            player = split[i + 1] if i + 1 < len(split) else ""
            return player, class_name
    return None
