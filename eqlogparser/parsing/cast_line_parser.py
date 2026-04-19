from __future__ import annotations
import logging

from eqlogparser.models import LineData, SpellCast, ReceivedSpell, SpecialRecord, ZoneRecord
from eqlogparser.text_utils import parse_spell_or_npc

log = logging.getLogger(__name__)

_SPECIAL_CAST_CODES: dict[str, str] = {
    "Glyph of Ultimate Power": "G", "Glyph of Destruction": "G", "Glyph of Dragon": "D",
    "Intensity of the Resolute": "7", "Staunch Recovery": "6", "Glyph of Arcane Secrets": "S",
}

_PET_SPELLS: set[str] = {
    "Fortify Companion", "Zeal of the Elements", "Frenzied Burnout", "Frenzy of the Dead",
}

_OLD_SPELL_CHARS = frozenset(("<", ">"))


def process(line_data: LineData) -> bool:
    try:
        split = line_data.split
        if not split or len(split) <= 1:
            return False
        if "." in split[0]:
            return False
        if split[-1].endswith(")"):
            return False
        if _check_lands_on_messages(split, line_data.begin_time):
            return False

        player: str | None = None
        spell_name: str | None = None
        is_casting = False
        is_interrupted = False
        is_you = False

        if split[0] == "You":
            is_you = True
            from eqlogparser.config import Config
            player = Config.player_name
            if split[1] == "activate" and len(split) > 2:
                spell_name = parse_spell_or_npc(split, 2)
            elif split[1] == "begin" and len(split) > 3:
                if split[2] == "casting":
                    spell_name = parse_spell_or_npc(split, 3)
                    is_casting = True
                elif split[2] == "singing":
                    spell_name = parse_spell_or_npc(split, 3)
        elif split[1] == "activates":
            player = split[0]
            spell_name = parse_spell_or_npc(split, 2)
        else:
            b_index = -1
            for idx in range(1, len(split)):
                if split[idx] == "begins":
                    b_index = idx
                    break
            if b_index > -1 and len(split) > 3 and (b_index + 2) < len(split):
                if split[b_index + 1] == "casting":
                    player = " ".join(split[:b_index])
                    spell_name = parse_spell_or_npc(split, b_index + 2)
                    is_casting = True
                elif split[b_index + 1] == "singing":
                    player = " ".join(split[:b_index])
                    spell_name = parse_spell_or_npc(split, b_index + 2)
                elif (len(split) > 5 and split[2] == "to" and split[4] == "a"):
                    if split[3] == "cast" and split[5] == "spell.":
                        player = split[0]
                        spell_name = _parse_old_spell_name(split, 6)
                        is_casting = True
                    elif split[3] == "sing" and split[5] == "song.":
                        player = split[0]
                        spell_name = _parse_old_spell_name(split, 6)
            elif (len(split) > 4 and split[-1] == "interrupted."
                  and split[-2] == "is" and split[-3] == "spell"):
                is_interrupted = True
                spell_name = " ".join(split[1:len(split) - 3])
                if split[0] == "Your":
                    from eqlogparser.config import Config
                    player = Config.player_name
                elif len(split[0]) > 3 and split[0][-1] == "s" and split[0][-2] == "'":
                    player = split[0][:-2]

        if player and spell_name:
            current_time = line_data.begin_time
            from eqlogparser.data_manager import DataManager
            from eqlogparser.record_manager import RecordManager
            from eqlogparser.player_manager import PlayerManager

            if not is_interrupted:
                special_key = None
                if is_casting:
                    found = _check_for_special(_SPECIAL_CAST_CODES, spell_name, player, current_time)
                    if found and is_you:
                        special_key = found

                spell_data = DataManager.instance().get_spell_by_name(spell_name)
                if spell_data is not None:
                    spell_data.seen_recently = True
                else:
                    spell_data = DataManager.instance().add_unknown_spell(spell_name)

                cast = SpellCast(caster=player, spell=spell_name, spell_data=spell_data)
                RecordManager.instance().add_spell_cast(cast, current_time)

                if not spell_data.is_unknown:
                    class_name = DataManager.instance().get_spell_class(spell_data.name)
                    if class_name:
                        PlayerManager.instance().set_active_player_class(player, class_name, 2, current_time)

                if special_key and spell_data:
                    DataManager.instance().update_adps(spell_data)
            else:
                for begin_time, action in RecordManager.instance().get_spells_during(current_time - 10, current_time, True):
                    if isinstance(action, SpellCast) and action.spell == spell_name and action.caster == player:
                        action.interrupted = True
                        break

            return True

    except Exception:
        log.exception("cast_line_parser.process")

    return False


def _check_lands_on_messages(split: list[str], begin_time: float) -> bool:
    from eqlogparser.config import Config
    from eqlogparser.data_manager import DataManager
    from eqlogparser.record_manager import RecordManager
    from eqlogparser.player_manager import PlayerManager

    player = Config.player_name

    # trim at sentence boundary (but not "Rk.")
    trimmed = list(split)
    for i, w in enumerate(trimmed):
        if w.endswith("."):
            if i != len(trimmed) - 1 and w == "Rk.":
                return False
            if i < len(trimmed) - 1:
                trimmed = trimmed[:i + 1]
            break

    search = DataManager.instance().get_lands_on_you(trimmed)
    if not search.spell_data or search.data_index != 0:
        search = DataManager.instance().get_wear_off(trimmed)
        if search.spell_data and search.data_index == 0:
            if player:
                spell = ReceivedSpell(receiver=player, is_wear_off=True)
                if len(search.spell_data) == 1:
                    spell.spell_data = search.spell_data[0]
                else:
                    spell.ambiguity.extend(search.spell_data)
                RecordManager.instance().add_received_spell(spell, begin_time)
            return True

        out_player: list[str] = []
        search = DataManager.instance().get_lands_on_other(trimmed, out_player)
        if out_player:
            player = out_player[0]
        if search.spell_data and len(search.spell_data) == 1 and player:
            sp = search.spell_data[0]
            # target == Pet (6) or Pet2 (18)
            if sp.target in (6, 18) and not PlayerManager.instance().is_verified_pet(player):
                if PlayerManager.is_possible_player_name(player) and not PlayerManager.instance().is_verified_player(player):
                    for pet_spell in _PET_SPELLS:
                        if sp.name.startswith(pet_spell):
                            PlayerManager.instance().add_verified_pet(player)

    if search.spell_data and player:
        spell = ReceivedSpell(receiver=player)
        if len(search.spell_data) == 1:
            spell.spell_data = search.spell_data[0]
        else:
            spell.ambiguity.extend(search.spell_data)
        RecordManager.instance().add_received_spell(spell, begin_time)
        return True

    # zone event
    if len(split) > 3 and split[1] == "have" and split[2] == "entered":
        zone = " ".join(split[3:]).rstrip(".")
        RecordManager.instance().add_zone(ZoneRecord(zone=zone), begin_time)
        if not zone.lower().startswith("an area"):
            DataManager.instance().zone_changed()
            return True

    return False


def _check_for_special(codes: dict[str, str], spell_name: str, player: str, current_time: float) -> str | None:
    from eqlogparser.record_manager import RecordManager
    for key, code in codes.items():
        if spell_name and key in spell_name:
            RecordManager.instance().add_special(SpecialRecord(code=code, player=player), current_time)
            return key
    return None


def _parse_old_spell_name(split: list[str], spell_index: int) -> str:
    return " ".join(split[spell_index:]).strip("<>")
