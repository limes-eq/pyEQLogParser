from __future__ import annotations
import logging
import math
import re
from dataclasses import dataclass
from typing import Callable

from eqlogparser.labels import Labels
from eqlogparser.models import DamageRecord, LineData, DeathRecord, SpecialRecord, TauntRecord
from eqlogparser.stats_util import parse_uint, UINT_MAX
from eqlogparser.text_utils import to_upper, s_compare, parse_spell_or_npc

log = logging.getLogger(__name__)

_CHECK_EYE_RE = re.compile(r"^Eye of (\w+)")

_HIT_MAP: dict[str, str] = {
    "bash": "bashes", "backstab": "backstabs", "bite": "bites", "claw": "claws",
    "crush": "crushes", "frenzy": "frenzies", "gore": "gores", "hit": "hits",
    "kick": "kicks", "learn": "learns", "maul": "mauls", "punch": "punches",
    "pierce": "pierces", "rend": "rends", "shoot": "shoots", "slash": "slashes",
    "slam": "slams", "slice": "slices", "smash": "smashes", "stab": "stabs",
    "sting": "stings", "strike": "strikes", "sweep": "sweeps",
}
_HIT_ADDITIONAL_MAP: dict[str, str] = {"frenzy": "frenzies", "frenzies": "frenzies"}
_REVERSE_HIT_MAP: dict[str, bool] = {v: True for v in _HIT_MAP.values()}

_CHEST_TYPES = [" chest", " cache", " satchel", " treasure box", " lost treasure"]

_SPELL_RESIST_MAP: dict[str, str] = {
    "fire": "fire", "cold": "cold", "poison": "poison", "magic": "magic",
    "disease": "disease", "unresistable": "unresistable", "chromatic": "lowest",
    "physical": "physical", "corruption": "corruption", "prismatic": "average",
}

_SPECIAL_CODES: dict[str, str] = {"Mana Burn": "M", "Harm Touch": "H", "Life Burn": "L"}

_slain_queue: list[str] = []
_slain_time: float = float("nan")
_previous_action: str | None = None
_last_crit: _OldCritData | None = None
_delay_crit_record: _DelayCritRecord | None = None
_pending_dd: tuple[str, DamageRecord, float] | None = None  # (defender, record, begin_time)

events_damage_processed: list[Callable] = []
events_new_taunt: list[Callable] = []


def reset() -> None:
    global _slain_queue, _slain_time, _previous_action, _last_crit, _delay_crit_record, _pending_dd
    _slain_queue = []
    _slain_time = float("nan")
    _previous_action = None
    _last_crit = None
    _delay_crit_record = None
    _pending_dd = None


@dataclass
class _OldCritData:
    attacker: str = ""
    begin_time: float = 0.0
    value: str = ""


@dataclass
class _DelayCritRecord:
    record: DamageRecord | None = None
    begin_time: float = 0.0


def check_slain_queue(current_time: float) -> None:
    global _slain_queue, _slain_time
    if not math.isnan(_slain_time) and current_time > _slain_time:
        from eqlogparser.data_manager import DataManager
        for slain in _slain_queue:
            DataManager.instance().remove_active_fight(slain)
        _slain_queue.clear()
        _slain_time = float("nan")


def process(line_data: LineData) -> bool:
    global _previous_action, _pending_dd
    processed = False
    try:
        if _pending_dd is not None:
            defender, record, dd_time = _pending_dd
            _pending_dd = None
            action = line_data.action
            if action.startswith(defender):
                suffix = action[len(defender):]
                from eqlogparser.data_manager import DataManager
                candidates = DataManager.instance().get_spells_by_cast_on_other(suffix)
                if candidates:
                    spell_data = _pick_spell_by_recent_cast(record.attacker, candidates, dd_time)
                    record.sub_type = spell_data.name

        split = line_data.split
        if split and len(split) >= 2:
            stop = _find_stop(split)
            if len(split) > 1 and stop >= 1 and split[stop] == "died.":
                candidate = " ".join(split[:stop])
                if candidate:
                    _update_slain(candidate, "", line_data)
                    processed = True
            else:
                if _parse_line(False, line_data, split, stop) is not None:
                    processed = True
        _previous_action = line_data.action
    except Exception:
        log.exception("damage_line_parser.process")
    return processed


def _find_stop(split: list[str]) -> int:
    stop = len(split) - 1
    if split[stop] and split[stop][-1] == ")":
        for i in range(stop, -1, -1):
            if stop <= 2:
                break
            if split[i] and split[i][0] == "(":
                stop = i - 1
                break
    return stop


def _parse_line(check_line_type: bool, line_data: LineData, split: list[str], stop: int) -> DamageRecord | None:
    global _last_crit, _delay_crit_record, _pending_dd

    record: DamageRecord | None = None
    resist = ""
    attacker: str | None = None
    defender: str | None = None

    is_you = split[0] in ("You", "Your")
    cripple_damage_fix: int = -1

    by_index = for_index = points_of_index = end_damage = by_damage = extra_index = -1
    from_damage = has_index = have_index = hit_type_index = hit_type_add = slain_index = -1
    taken_index = try_index = your_index = is_index = non_melee_index = but_index = -1
    miss_type = attention_index = failed_index = harmed_index = emu_absorbed_index = -1
    emu_pet_index = shielded_index = absorbs_index = old_crit_index = -1
    sub_type: str | None = None
    found_type = False
    found = False

    for i in range(min(stop + 1, len(split))):
        if found:
            break
        w = split[i]
        if not w:
            continue

        if w[0] == "(":
            if w == "(Owner:":
                emu_pet_index = i
                continue
            return None  # short-circuit over-heal

        if w == "absorbs":
            if i > 2 and split[i - 1] == "skin" and split[i - 2] == "magical":
                absorbs_index = i - 2
        elif w == "absorbed":
            emu_absorbed_index = i
        elif w in ("attention!", "attention."):
            attention_index = i
        elif w in ("healed", "casting"):
            return None
        elif w == "but":
            but_index = i
        elif w == "failed":
            failed_index = i
        elif w in ("are", "is", "was", "were"):
            is_index = i
        elif w == "has":
            has_index = i
        elif w == "have":
            have_index = i
        elif w == "by":
            by_index = i
            if slain_index > -1:
                found = True
            elif i > 4 and split[i - 1] == "damage":
                by_damage = i - 1
        elif w == "from":
            if i > 3 and split[i - 1] == "damage":
                from_damage = i - 1
                if points_of_index > -1 and extra_index > -1:
                    found = True
                elif stop > (i + 1) and split[i + 1] == "your":
                    your_index = i + 1
        elif w == "damage.":
            if i == stop:
                end_damage = i
        elif w == "harmed":
            if i > 0 and split[i - 1] == "has":
                harmed_index = i + 1
        elif w == "non-melee":
            non_melee_index = i
        elif w in ("point", "points"):
            if stop >= (i + 1) and split[i + 1] == "of":
                points_of_index = i
                if i > 2 and split[i - 2] == "for":
                    for_index = i - 2
        elif w == "blocks!":
            if stop == i and but_index > -1 and i > try_index:
                miss_type = 0
        elif w == "shielded":
            shielded_index = i
        elif w in ("shield!", "staff!"):
            if (i > 5 and stop == i and but_index > -1 and i > try_index
                    and split[i - 2] == "with"
                    and split[i - 3].lower().startswith("block")):
                miss_type = 0
        elif w in ("dodge!", "dodges!"):
            if stop == i and but_index > -1 and i > try_index:
                miss_type = 1
        elif w in ("miss!", "misses!"):
            if stop == i and but_index > -1 and i > try_index:
                miss_type = 2
        elif w in ("parry!", "parries!"):
            if stop == i and but_index > -1 and i > try_index:
                miss_type = 3
        elif w == "INVULNERABLE!":
            if stop == i and but_index > -1 and i > try_index:
                miss_type = 4
        elif w in ("riposte!", "ripostes!"):
            if (stop == i and but_index > -1 and i > try_index
                    and (len(split) == 0 or split[-1] != "(Strikethrough)")):
                miss_type = 5
        elif w == "blow!":
            if (stop == i and but_index > -1 and i > try_index
                    and i >= 2 and split[i - 2] == "absorbs"):
                miss_type = 6
        elif w == "slain":
            slain_index = i
        elif w == "taken":
            if i > 1 and (has_index == i - 1 or have_index == i - 1):
                taken_index = i - 1
                if stop > (i + 2) and split[i + 1] == "an" and split[i + 2] == "extra":
                    extra_index = i + 2
        elif w == "blast!":
            if stop == i and i > 3 and len(split) > stop and split[i - 1] == "critical" and split[i - 3] == "delivers":
                att = " ".join(split[:i - 3])
                att = _update_attacker(att, Labels.Dd)
                val = split[stop + 1] if len(split) > stop + 1 else ""
                _last_crit = _OldCritData(attacker=att, begin_time=line_data.begin_time, value=val)
                return None
        elif w == "hit!":
            if stop == i and i > 3 and len(split) > stop and split[i - 1] == "critical" and split[i - 3] == "scores":
                old_crit_index = i - 3
        elif w == "Crippling":
            if (stop == i + 1 and i > 2 and len(split) > stop
                    and split[i - 1] == "a" and split[i - 2] == "lands"
                    and split[i + 1].startswith("Blow!")):
                idx = split[i + 1].find("(")
                if idx > -1:
                    cripple_damage_fix = parse_uint(split[i + 1][idx + 1:-1])
                old_crit_index = i - 2
        elif w == "Blow!!":
            if stop == i and i > 3 and split[i - 1] == "Finishing" and split[i - 3] == "scores":
                att = " ".join(split[:i - 3])
                att = _update_attacker(att, Labels.Unk)
                _last_crit = _OldCritData(attacker=att, begin_time=line_data.begin_time)
                return None
        else:
            if slain_index == -1 and i > 0 and i < stop and try_index == -1 and not found_type:
                if (i + 3) < stop and split[i + 1] == "for" and split[i + 3] == "points":
                    found_type = hit_type_index > -1
                    continue
                elif split[i] in _HIT_MAP:
                    hit_type_index = i
                    sub_type = _HIT_MAP[split[i]]
                    found_type = True
                elif split[i] in _REVERSE_HIT_MAP:
                    hit_type_index = i
                    sub_type = split[i]
                    found_type = True

                if found_type:
                    if i > 2 and split[i - 1] == "to" and split[i - 2] in ("tries", "try"):
                        try_index = i - 2
                    if sub_type == "hits":
                        hit_type_index = i
                        found_type = False

                if hit_type_index > -1 and split[i] in _HIT_ADDITIONAL_MAP:
                    hit_type_add = i + i

    # DS: "X is pierced by Y's thorns for N points of non-melee damage."
    if (is_index > -1 and by_index > is_index and (for_index + 2) == points_of_index
            and non_melee_index > points_of_index and end_damage > -1):
        valid = False
        for i in range(by_index + 1, for_index):
            if split[i] == "YOUR":
                attacker = split[i]
                valid = True
                break
            elif split[i].endswith("'s") and (for_index - by_index - 2) > 0:
                end_span = for_index - by_index - 2
                attacker = " ".join(split[by_index + 1:by_index + 1 + end_span])[:-2]
                valid = True
                break
        if valid:
            defender = " ".join(split[:is_index])
            damage = parse_uint(split[points_of_index - 1])
            attacker = _update_attacker(attacker, Labels.Ds)
            defender = _update_defender(defender, attacker)
            record = _create_damage_record(line_data, split, stop, attacker, defender, damage, Labels.Ds, Labels.Ds)

    # Bane/extra: "X has taken an extra N points of non-melee damage from Y's Z spell."
    elif (extra_index > -1 and points_of_index == extra_index + 2
          and from_damage == points_of_index + 3 and split[stop] == "spell."):
        is_extra = False
        attacker_split_word = split[from_damage + 2]
        if attacker_split_word.endswith("'s"):
            attacker = split[from_damage + 2][:-2]
            defender = " ".join(split[:taken_index])
            is_extra = True
        elif attacker_split_word == "your":
            if harmed_index > 1 and split[harmed_index - 2] == "has" and harmed_index < taken_index - 1:
                attacker = " ".join(split[:harmed_index - 2])
                defender = " ".join(split[harmed_index:taken_index - 1]).strip(".")
            else:
                from eqlogparser.config import Config
                attacker = Config.player_name
                defender = " ".join(split[:taken_index])
            is_extra = True
        if is_extra:
            damage = parse_uint(split[extra_index + 1])
            spell = " ".join(split[from_damage + 3:stop - (from_damage + 3 - (stop + 1))])
            # simpler: join from from_damage+3 to stop (exclusive)
            spell = " ".join(split[from_damage + 3:stop])
            from eqlogparser.data_manager import DataManager
            spell_data = DataManager.instance().get_damaging_spell_by_name(spell)
            resist = spell_data.resist if spell_data else ""
            attacker = _update_attacker(attacker, spell)
            defender = _update_defender(defender, attacker)
            record = _create_damage_record(line_data, split, stop, attacker, defender, damage, Labels.Bane, spell)

    # Melee: "X crushes Y for N points of damage."
    elif (sub_type and is_index == -1 and points_of_index == end_damage - 2
          and for_index > -1 and hit_type_index < for_index and non_melee_index == -1):
        hit_type_mod = 1 if hit_type_add > 0 else 0
        attacker = " ".join(split[:hit_type_index])
        defender = " ".join(split[hit_type_index + hit_type_mod + 1:for_index])
        sub_type = to_upper(sub_type)
        damage = parse_uint(split[points_of_index - 1])
        attacker = _update_attacker(attacker, sub_type)
        defender = _update_defender(defender, attacker)
        record = _create_damage_record(line_data, split, stop, attacker, defender, damage, Labels.Melee, sub_type)

        if (record is not None and _last_crit is not None
                and _last_crit.attacker.lower() == record.attacker.lower()
                and (line_data.begin_time - _last_crit.begin_time) <= 1
                and not _last_crit.value):
            from eqlogparser.parsing.line_modifiers_parser import CRIT
            record.modifiers_mask = CRIT
            _last_crit = None

    # Spell hit: "X hit Y for N points of Z damage by SpellName."
    elif (by_damage > 3 and points_of_index == by_damage - 3 and by_index == by_damage + 1
          and for_index > -1 and hit_type_index > 0
          and split[hit_type_index] == "hit" and hit_type_index < for_index
          and split[stop] and split[stop][-1] == "."):
        spell = " ".join(split[by_index + 1:stop + 1])
        if spell and spell[-1] == ".":
            spell = spell[:-1]
            attacker = " ".join(split[:hit_type_index])
            defender = " ".join(split[hit_type_index + 1:for_index])
            type_ = _get_type_from_spell(spell, Labels.Dd)
            damage = parse_uint(split[points_of_index - 1])
            resist = _SPELL_RESIST_MAP.get(split[by_damage - 1], "")
            if spell.startswith("Elemental Conversion"):
                from eqlogparser.player_manager import PlayerManager
                PlayerManager.instance().add_verified_pet(defender)
            attacker = _update_attacker(attacker, spell)
            defender = _update_defender(defender, attacker)
            record = _create_damage_record(line_data, split, stop, attacker, defender, damage, type_, spell)

    # DoT / taken damage: "X has taken N damage from Spell by Attacker."
    elif (from_damage > 3 and taken_index == from_damage - 3
          and (by_index > from_damage or your_index > from_damage or is_you)):
        spell = None
        attacker_is_spell = False
        if by_index > -1:
            spell = " ".join(split[from_damage + 2:by_index])
            attacker = " ".join(split[by_index + 1:stop + 1])
            if attacker == ".":
                attacker = spell
                attacker_is_spell = True
            elif not spell:
                spell = attacker
            elif attacker and attacker[-1] == ".":
                attacker = attacker[:-1]
        elif your_index > -1:
            attacker = split[your_index]
            spell = " ".join(split[your_index + 1:stop + 1])
            spell = spell[:-1] if spell and spell[-1] == "." else Labels.Dot
        elif is_you:
            spell = " ".join(split[from_damage + 2:stop + 1])
            spell = spell[:-1] if spell and spell[-1] == "." else spell
            attacker = spell

        from eqlogparser.config import Config
        if spell and attacker and by_index > -1:
            attacker, spell = spell, attacker

        if attacker and spell:
            from eqlogparser.data_manager import DataManager
            spell_data = DataManager.instance().get_damaging_spell_by_name(spell)
            if spell_data is None and DataManager.instance().is_old_spell(attacker):
                attacker, spell = spell, attacker
                type_ = Labels.Dot
            else:
                type_ = Labels.OtherDmg if spell == attacker else _get_type_from_spell(spell, Labels.Dot)
            defender = " ".join(split[:taken_index])
            damage = parse_uint(split[from_damage - 1])
            resist = spell_data.resist if spell_data else ""
            attacker = _update_attacker(attacker, spell)
            defender = _update_defender(defender, attacker)
            record = _create_damage_record(line_data, split, stop, attacker, defender, damage, type_, spell, attacker_is_spell)

    # "X has taken N damage by Spell."
    elif by_damage > -1 and taken_index == by_damage - 3:
        defender = " ".join(split[:taken_index])
        damage = parse_uint(split[by_damage - 1])
        spell = " ".join(split[by_damage + 2:stop + 1])
        if spell and spell[-1] == ".":
            spell = spell[:-1]
        from eqlogparser.data_manager import DataManager
        label = Labels.OtherDmg
        spell_data = DataManager.instance().get_damaging_spell_by_name(spell)
        if spell_data:
            resist = spell_data.resist
            if spell_data.level < 255:
                label = Labels.Dot
        attacker = _update_attacker("", spell)
        defender = _update_defender(defender, attacker)
        record = _create_damage_record(line_data, split, stop, attacker, defender, damage, label, spell, True)

    # Reverse DS / environmental: "X was chilled to the bone for N points of non-melee damage."
    elif (is_index > -1 and by_index == -1 and (for_index + 2) == points_of_index
          and non_melee_index > points_of_index
          and split[stop].lower().startswith("damage")):
        defender = " ".join(split[:is_index])
        damage = parse_uint(split[points_of_index - 1])
        attacker = Labels.Rs
        defender = _update_defender(defender, attacker)
        record = _create_damage_record(line_data, split, stop, attacker, defender, damage, Labels.Ds, Labels.Ds)

    # Non-melee hit: "X was hit by non-melee for N points of damage."
    elif (for_index > -1 and for_index < points_of_index and non_melee_index < points_of_index
          and by_index == non_melee_index - 1 and is_index > -1 and split[is_index + 1] == "hit"):
        defender = " ".join(split[:is_index])
        from eqlogparser.config import Config
        attacker = Config.player_name
        damage = parse_uint(split[points_of_index - 1])
        defender = _update_defender(defender, attacker)
        record = _create_damage_record(line_data, split, stop, attacker, defender, damage, Labels.Dd, Labels.Dd)

    # Falling damage: "You were hit by non-melee for N damage"
    elif (is_index > -1 and non_melee_index == is_index + 3 and split[is_index + 1] == "hit"
          and end_damage == stop and points_of_index == -1):
        damage = parse_uint(split[end_damage - 1])
        attacker = Labels.Unk
        from eqlogparser.config import Config
        defender = Config.player_name if is_you else " ".join(split[:is_index])
        defender = _update_defender(defender, attacker)
        record = _create_damage_record(line_data, split, stop, attacker, defender, damage, Labels.Dd, Labels.Dd)

    # Magical skin absorb: "X's magical skin absorbs the damage of Y's thorns."
    elif (absorbs_index > -1 and len(split) > absorbs_index + 6
          and split[absorbs_index + 4] == "damage" and split[absorbs_index + 5] == "of"
          and split[stop - 1].endswith("'s")):
        defender = " ".join(split[:absorbs_index])
        if defender.endswith("'s"):
            defender = defender[:-2]
        attacker = " ".join(split[absorbs_index + 6:stop])
        attacker = attacker[:-2]
        attacker = _update_attacker(attacker, sub_type)
        defender = _update_defender(defender, attacker)
        record = _create_damage_record(line_data, split, stop, attacker, defender, 0, Labels.Absorb, "Hits")

    # Direct damage: "X hit Y for N points of non-melee damage."
    elif (for_index > -1 and hit_type_index > -1
          and split[hit_type_index] == "hit" and for_index < points_of_index
          and non_melee_index > points_of_index):
        if emu_pet_index > -1:
            attacker = " ".join(split[:emu_pet_index])
            if split[emu_pet_index + 1].endswith(")"):
                player = split[emu_pet_index + 1][:-1]
                from eqlogparser.player_manager import PlayerManager
                PlayerManager.instance().add_verified_player(player, line_data.begin_time)
                PlayerManager.instance().add_verified_pet(attacker)
                PlayerManager.instance().add_pet_to_player(attacker, player)
        else:
            attacker = " ".join(split[:hit_type_index])
        defender = " ".join(split[hit_type_index + 1:for_index])
        damage = parse_uint(split[points_of_index - 1])
        attacker = _update_attacker(attacker, Labels.Dd)
        defender = _update_defender(defender, attacker)
        sub_type2 = Labels.Dd
        end_idx = stop + 1
        if len(split) > end_idx and split[end_idx].startswith("("):
            old_spell = " ".join(split[end_idx:len(split)])
            if len(old_spell) > 2:
                sub_type2 = to_upper(old_spell[1:-1])
        defender_raw = " ".join(split[hit_type_index + 1:for_index])
        record = _create_damage_record(line_data, split, stop, attacker, defender, damage, Labels.Dd, sub_type2)
        if record is not None:
            if (record and _last_crit
                    and _last_crit.attacker.lower() == record.attacker.lower()
                    and (line_data.begin_time - _last_crit.begin_time) <= 1
                    and _last_crit.value and len(_last_crit.value) > 2
                    and _last_crit.value[1:-1] == split[points_of_index - 1]):
                from eqlogparser.parsing.line_modifiers_parser import CRIT
                record.modifiers_mask = CRIT
                _last_crit = None
            if sub_type2 == Labels.Dd:
                _pending_dd = (defender_raw, record, line_data.begin_time)

    # Absorbed
    elif (emu_absorbed_index > -1
          and points_of_index > emu_absorbed_index and split[stop] == "damage"):
        from eqlogparser.config import Config
        defender = Config.player_name
        record = _create_damage_record(line_data, split, stop, Labels.Unk, defender, 0, Labels.Absorb, "Hits")

    # Aura damage
    elif (have_index > -1 and have_index == taken_index
          and points_of_index == taken_index + 3 and split[have_index - 1] == "You"):
        damage = parse_uint(split[points_of_index - 1])
        from eqlogparser.config import Config
        record = _create_damage_record(line_data, split, stop, Labels.Unk, Config.player_name, damage, Labels.Dot, Labels.Dot)

    # Shielded
    elif (has_index > -1 and shielded_index == has_index + 1
          and points_of_index == stop - 2):
        if emu_pet_index > -1 and emu_pet_index < has_index:
            defender = " ".join(split[:emu_pet_index])
            if split[emu_pet_index + 1].endswith(")"):
                player = split[emu_pet_index + 1][:-1]
                from eqlogparser.player_manager import PlayerManager
                PlayerManager.instance().add_verified_player(player, line_data.begin_time)
                PlayerManager.instance().add_verified_pet(defender)
                PlayerManager.instance().add_pet_to_player(defender, player)
        else:
            defender = " ".join(split[:has_index])
        defender = _update_defender(defender, Labels.Unk)
        record = _create_damage_record(line_data, split, stop, Labels.Unk, defender, 0, Labels.Absorb, "Hits")

    # Old-style critical melee: "X scores a critical hit! (780)"
    elif (old_crit_index > -1
          and (cripple_damage_fix > -1 or (len(split) > stop + 1 and len(split[stop + 1]) > 2))):
        if cripple_damage_fix != -1:
            damage = cripple_damage_fix
        else:
            damage = parse_uint(split[stop + 1][1:-1])
        if damage != UINT_MAX:
            attacker = " ".join(split[:old_crit_index])
            attacker = _update_attacker(attacker, Labels.Unk)
            dmg_record = _create_damage_record(line_data, split, stop, attacker, Labels.Unk, damage, Labels.Melee, "Hits")
            if dmg_record:
                from eqlogparser.parsing.line_modifiers_parser import CRIT
                dmg_record.modifiers_mask = CRIT
            _delay_crit_record = _DelayCritRecord(record=dmg_record, begin_time=line_data.begin_time)

    # Miss/dodge/parry/block/riposte
    elif try_index > -1 and but_index > try_index and miss_type > -1:
        labels = {0: Labels.Block, 1: Labels.Dodge, 2: Labels.Miss, 3: Labels.Parry,
                  4: Labels.Invulnerable, 5: Labels.Riposte, 6: Labels.Absorb}
        label = labels.get(miss_type)
        if label:
            hit_type_mod = 1 if hit_type_add > 0 else 0
            defender = " ".join(split[hit_type_index + hit_type_mod + 1:but_index])
            if defender and defender[-1] == ",":
                defender = defender[:-1]
                attacker = " ".join(split[:try_index])
                sub_type = to_upper(sub_type) if sub_type else sub_type
                attacker = _update_attacker(attacker, sub_type)
                defender = _update_defender(defender, attacker)
                record = _create_damage_record(line_data, split, stop, attacker, defender, 0, label, sub_type)

    # Slain messages
    elif not check_line_type and slain_index > -1 and by_index == slain_index + 1 and is_index > 0 and stop > slain_index + 1 and split[is_index] == "was":
        killer = " ".join(split[by_index + 1:stop + 1])
        killer = killer[:-1] if len(killer) > 1 and killer[-1] == "!" else killer
        slain = " ".join(split[:is_index])
        _update_slain(slain, killer, line_data)
        _check_owner(slain)
        _check_owner(killer)

    elif not check_line_type and slain_index > -1 and by_index == slain_index + 1 and has_index > 0 and stop > slain_index + 1 and split[has_index + 1] == "been":
        killer = " ".join(split[by_index + 1:stop + 1])
        killer = killer[:-1] if len(killer) > 1 and killer[-1] == "!" else killer
        slain = " ".join(split[:has_index])
        _update_slain(slain, killer, line_data)
        _check_owner(slain)
        _check_owner(killer)

    elif not check_line_type and stop > 4 and slain_index == 3 and by_index == 4 and is_you and split[1] == "have" and split[2] == "been":
        killer = " ".join(split[5:stop + 1])
        killer = killer[:-1] if len(killer) > 1 and killer[-1] == "!" else killer
        from eqlogparser.config import Config
        _update_slain(Config.player_name, killer, line_data)

    elif not check_line_type and slain_index == 2 and is_you and split[1] == "have":
        from eqlogparser.config import Config
        slain = " ".join(split[3:stop + 1])
        slain = slain[:-1] if len(slain) > 1 and slain[-1] == "!" else slain
        _update_slain(slain, Config.player_name, line_data)

    elif not check_line_type:
        _handle_taunts(line_data, split, stop, is_you, attention_index, failed_index)

    if record is not None:
        if (_delay_crit_record is not None
                and (line_data.begin_time - _delay_crit_record.begin_time) <= 1
                and record.attacker.lower() == _delay_crit_record.record.attacker.lower()):
            record.modifiers_mask = _delay_crit_record.record.modifiers_mask
            _delay_crit_record = None

        if not check_line_type and not _in_ignore_list(defender):
            from eqlogparser.data_manager import DataManager
            from eqlogparser.record_manager import RecordManager
            from eqlogparser.config import Config
            from eqlogparser.player_manager import PlayerManager
            if (resist and defender != attacker and (
                    attacker == Config.player_name
                    or PlayerManager.instance().get_player_from_pet(attacker) == Config.player_name)):
                RecordManager.instance().update_npc_spell_stats(defender, resist)

            if not math.isnan(line_data.begin_time):
                check_slain_queue(line_data.begin_time)
                for cb in events_damage_processed:
                    cb(record, line_data.begin_time)
                RecordManager.instance().add_damage(record, line_data.begin_time)

                if record.type == Labels.Dd:
                    for key in _SPECIAL_CODES:
                        if record.sub_type and key in record.sub_type:
                            RecordManager.instance().add_special(
                                SpecialRecord(code=_SPECIAL_CODES[key], player=record.attacker),
                                line_data.begin_time,
                            )
                            break

    return record


def _handle_taunts(line_data: LineData, split: list[str], stop: int, is_you: bool,
                   attention_index: int, failed_index: int) -> None:
    from eqlogparser.config import Config
    from eqlogparser.record_manager import RecordManager

    if is_you:
        if attention_index == len(split) - 1 and len(split) > 3 and split[1] == "capture":
            npc_out: list[str] = []
            if _parse_npc_name(split, 3, npc_out):
                rec = TauntRecord(player=Config.player_name, success=True, npc=to_upper(npc_out[0]))
                RecordManager.instance().add_taunt(rec, line_data.begin_time)
                for cb in events_new_taunt:
                    cb(rec, line_data.begin_time)
        elif (attention_index == len(split) - 1 and failed_index == 2
              and len(split) > 6 and split[1] == "have" and split[3] == "to"):
            rec = TauntRecord(player=Config.player_name, success=False,
                              npc=to_upper(parse_spell_or_npc(split, 5)))
            RecordManager.instance().add_taunt(rec, line_data.begin_time)
            for cb in events_new_taunt:
                cb(rec, line_data.begin_time)
    elif attention_index > -1 and attention_index == len(split) - 1:
        i = 2 if (split[1] == "warder" and split[0].endswith("`s")) else 1
        name = split[0] + " " + split[1] if i == 2 else split[0]
        if split[i] == "has" and split[i + 1] == "captured":
            npc_out = []
            if _parse_npc_name(split, 3 + i, npc_out):
                rec = TauntRecord(player=name, success=True, npc=to_upper(npc_out[0]))
                RecordManager.instance().add_taunt(rec, line_data.begin_time)
                for cb in events_new_taunt:
                    cb(rec, line_data.begin_time)
    elif len(split) > 4:
        i = 2 if (split[1] == "warder" and split[0].endswith("`s")) else 1
        name = split[0] + " " + split[1] if i == 2 else split[0]
        if failed_index == i and split[i + 1] == "to" and split[i + 2] == "taunt":
            rec = TauntRecord(player=name, success=False, npc=to_upper(parse_spell_or_npc(split, 3 + i)))
            RecordManager.instance().add_taunt(rec, line_data.begin_time)
            for cb in events_new_taunt:
                cb(rec, line_data.begin_time)
        elif (len(split) > 10 and split[-1] == "taunt." and split[-2] == "improved"
              and split[-3] == "an" and split[-4] == "to" and split[-5] == "due"):
            last = len(split) - 5
            for j in range(len(split) - 9):
                p_idx = j + 4
                if split[j] == "is" and split[j+1] == "focused" and split[j+2] == "on" and split[j+3] == "attacking" and p_idx < last:
                    npc = " ".join(split[:j])
                    taunter = " ".join(split[p_idx:last])
                    rec = TauntRecord(player=taunter, success=True, is_improved=True, npc=to_upper(npc))
                    RecordManager.instance().add_taunt(rec, line_data.begin_time)
                    for cb in events_new_taunt:
                        cb(rec, line_data.begin_time)


def _parse_npc_name(parts: list[str], length: int, out: list[str]) -> bool:
    npc = " ".join(parts[length - 1:])
    segments = npc.split("'s")
    if len(segments) == 2:
        out.append(segments[0])
        return True
    return False


def _update_slain(slain: str, killer: str, line_data: LineData) -> None:
    global _slain_queue, _slain_time, _previous_action
    if not slain or killer is None:
        return
    if _in_ignore_list(slain):
        return

    from eqlogparser.player_manager import PlayerManager
    from eqlogparser.config import Config
    from eqlogparser.data_manager import DataManager
    from eqlogparser.record_manager import RecordManager

    if len(killer) > 2:
        killer = PlayerManager.replace_player(killer, killer)
    slain = PlayerManager.replace_player(slain, slain)

    if slain == Config.player_name:
        DataManager.instance().clear_active_adps()

    current_time = line_data.begin_time
    if not math.isnan(current_time):
        check_slain_queue(current_time)
        slain_up = to_upper(slain)
        if slain_up not in _slain_queue and DataManager.instance().get_fight(slain_up) is not None:
            _slain_queue.append(slain_up)
            _slain_time = current_time

        killer_up = to_upper(killer)
        death = DeathRecord(
            killed=slain_up,
            killer=killer_up,
            message=line_data.action,
            previous=_previous_action or "",
        )
        RecordManager.instance().add_death(death, current_time)


def _create_damage_record(line_data: LineData, split: list[str], stop: int,
                           attacker: str, defender: str, damage: int,
                           type_: str, sub_type: str,
                           attacker_is_spell: bool = False) -> DamageRecord | None:
    if damage == UINT_MAX or not type_ or not sub_type:
        return None

    current_time = line_data.begin_time
    modifiers_mask = -1
    if len(split) > stop + 1:
        modifiers = " ".join(split[stop + 1:])
        if modifiers and modifiers[0] == "(" and modifiers[-1] == ")":
            from eqlogparser.parsing.line_modifiers_parser import parse_damage
            modifiers_mask = parse_damage(attacker, modifiers[1:-1], current_time, not attacker_is_spell)

    attacker_owner = _check_owner(attacker)
    defender_owner = _check_owner(defender)

    if len(attacker) <= 64 and len(defender) <= 64:
        return DamageRecord(
            attacker=attacker,
            defender=defender,
            type=type_,
            sub_type=sub_type,
            total=damage,
            attacker_owner=attacker_owner,
            defender_owner=defender_owner,
            modifiers_mask=modifiers_mask,
            attacker_is_spell=attacker_is_spell,
        )
    return None


def _update_attacker(attacker: str, sub_type: str | None) -> str:
    from eqlogparser.player_manager import PlayerManager
    if not attacker:
        attacker = sub_type or ""
    elif attacker.endswith("'s corpse") or attacker.endswith("`s corpse"):
        attacker = attacker[:-9]
    else:
        attacker = PlayerManager.replace_player(attacker, attacker)
    return to_upper(attacker)


def _update_defender(defender: str, attacker: str) -> str:
    from eqlogparser.player_manager import PlayerManager
    return to_upper(PlayerManager.replace_player(defender, attacker))


def _check_owner(name: str) -> str | None:
    if not name:
        return None
    from eqlogparser.player_manager import PlayerManager
    p_index = name.find("`s ")
    if p_index > -1 and _is_pet_or_mount(name, p_index + 3):
        verified_pet = PlayerManager.instance().is_verified_pet(name)
        if verified_pet or PlayerManager.is_possible_player_name(name, p_index):
            owner = name[:p_index]
            if not verified_pet and PlayerManager.instance().is_verified_player(owner):
                PlayerManager.instance().add_verified_pet(name)
                PlayerManager.instance().add_pet_to_player(name, owner)
            return owner
    else:
        p_index = name.rfind(" pet")
        if p_index > -1:
            verified_pet = PlayerManager.instance().is_verified_pet(name)
            if verified_pet or PlayerManager.is_possible_player_name(name, p_index):
                owner = name[:p_index]
                if not verified_pet and PlayerManager.instance().is_verified_player(owner):
                    PlayerManager.instance().add_verified_pet(name)
                    PlayerManager.instance().add_pet_to_player(name, owner)
                return owner
    return None


def _is_pet_or_mount(part: str, start: int) -> bool:
    for test in ("pet", "ward", "Mount", "warder", "Warder"):
        end = start + len(test)
        if len(part) >= end and s_compare(part, start, len(test), test):
            if test == "ward" and len(part) > end + 1 and part[end] != "e":
                continue
            return True
    return False


def _get_type_from_spell(name: str, type_: str) -> str:
    from eqlogparser.data_manager import DataManager
    from eqlogparser.stats_util import create_record_key
    key = create_record_key(type_, name)
    if not key:
        return type_
    spell = DataManager.instance().get_spell_by_abbrv(DataManager.instance().abbreviate_spell_name(name))
    if spell:
        if spell.damaging == 2:
            return Labels.Bane
        if spell.proc == 1:
            return Labels.Proc
    return type_


def _in_ignore_list(name: str) -> bool:
    if not name:
        return False
    if name.lower().endswith("`s mount"):
        return True
    for chest in _CHEST_TYPES:
        if name.lower().endswith(chest):
            return True
    m = _CHECK_EYE_RE.match(name)
    if m:
        return not (name.endswith("Veeshan") or name.endswith("Despair") or name.endswith("Mother"))
    return False


def _pick_spell_by_recent_cast(attacker: str, candidates: list, begin_time: float):
    from eqlogparser.record_manager import RecordManager
    from eqlogparser.models import SpellCast
    candidate_names = {s.name for s in candidates}
    casts = RecordManager.instance().get_spells_during(begin_time - 60, begin_time, reverse=True)
    for _, cast in casts:
        if isinstance(cast, SpellCast) and cast.caster == attacker and cast.spell in candidate_names:
            return next(s for s in candidates if s.name == cast.spell)
    return candidates[0]


