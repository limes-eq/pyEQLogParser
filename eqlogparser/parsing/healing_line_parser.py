from __future__ import annotations
import logging

from eqlogparser.labels import Labels
from eqlogparser.models import HealRecord, LineData
from eqlogparser.stats_util import parse_uint

log = logging.getLogger(__name__)


def process(line_data: LineData) -> bool:
    action = line_data.action
    try:
        index = action.rfind(" healed ")
        if len(action) >= 23 and index > -1:
            record = _handle_healed(action, index, line_data.begin_time)
            if record is not None:
                from eqlogparser.player_manager import PlayerManager
                from eqlogparser.record_manager import RecordManager
                record.healer = PlayerManager.replace_player(record.healer, record.healed)
                record.healed = PlayerManager.replace_player(record.healed, record.healer)
                RecordManager.instance().add_heal(record, line_data.begin_time)
                return True
    except Exception:
        log.exception("healing_line_parser.process")
    return False


def _handle_healed(part: str, optional: int, begin_time: float) -> HealRecord | None:
    test = part[:optional]

    done = False
    healer = ""
    healed = ""
    spell = None
    sub_type = None
    type_ = Labels.Heal
    heal = parse_uint("")  # UINT_MAX
    over_heal = 0

    previous = test.rfind(" ", 0, len(test) - 1) if len(test) >= 2 else -1

    if previous > -1:
        seg = test[previous + 1:]
        if "are " in seg:
            done = True
        elif (previous >= 1 and test[previous - 1] in (".", "!")) or (
            previous >= 9 and "fulfilled" in test[max(0, previous - 9):previous + 1]
        ):
            healer = test[previous + 1:]
        elif previous >= 3 and "has been" in test[max(0, previous - 3):previous + 1]:
            healed = test[:previous - 4]
            if len(part) > optional + 17 and "over time" in part[optional + 8:optional + 17]:
                type_ = Labels.Hot
        elif previous >= 0 and "has" in test[previous:]:
            healer = test[:previous]
            type_ = Labels.Heal
            sub_type = Labels.Heal
        elif previous >= 4 and "have been" in test[max(0, previous - 4):previous + 1]:
            healed = test[:previous - 5]
            if len(part) > optional + 17 and "over time" in part[optional + 8:optional + 17]:
                type_ = Labels.Hot
        else:
            ward_index = test.lower().find("`s ward")
            if ward_index > 0:
                healer = test[:ward_index]
    else:
        healer = test[:optional]

    if not done:
        amount_index = -1
        if not healed:
            after_healed = optional + 8
            for_index = part.find(" for ", after_healed)
            if for_index > 1:
                if for_index >= 9 and "over time" in part[for_index - 9:for_index]:
                    type_ = Labels.Hot
                    healed = part[after_healed:for_index - 10]
                else:
                    healed = part[after_healed:for_index]
                amount_index = for_index + 5
        else:
            if type_ == Labels.Heal:
                amount_index = optional + 12
            elif type_ == Labels.Hot:
                amount_index = optional + 22

        if amount_index > -1:
            amount_end = part.find(" ", amount_index)
            if amount_end > -1:
                value = parse_uint(part[amount_index:amount_end])
                if value != parse_uint(""):
                    heal = value

                over_end = -1
                if len(part) > amount_end + 1 and part[amount_end + 1] == "(":
                    over_end = part.find(")", amount_end + 2)
                    if over_end > -1:
                        value2 = parse_uint(part[amount_end + 2:over_end])
                        if value2 != parse_uint(""):
                            over_heal = value2

                rest = over_end if over_end > -1 else amount_end
                by_index = part.find(" by ", rest)
                if by_index > -1:
                    period_index = part.rfind(".")
                    if period_index > -1 and period_index - by_index - 4 > 0:
                        spell = part[by_index + 4:period_index]

        if healed:
            from eqlogparser.config import Config
            if healed.lower() == "you":
                healed = Config.player_name

            from eqlogparser.player_manager import PlayerManager
            possessive = healed.find("`s ")
            if possessive > -1:
                if PlayerManager.instance().is_verified_player(healed[:possessive]):
                    PlayerManager.instance().add_verified_pet(healed)
            elif healer and spell and spell.startswith("Mend Companion"):
                PlayerManager.instance().add_verified_pet(healed)
            elif not healer and spell and spell.lower().startswith("theft of essence"):
                healer = Labels.Unk

            if healer and heal != parse_uint("") and len(healer) <= 64:
                if sub_type is None:
                    sub_type = Labels.SelfHeal if not spell else spell

                from eqlogparser.parsing.line_modifiers_parser import parse_heal
                record = HealRecord(
                    total=heal,
                    over_total=over_heal,
                    healer=healer,
                    healed=healed,
                    type=type_,
                    modifiers_mask=-1,
                    sub_type=sub_type,
                )

                if part[-1] == ")":
                    first_paren = part.rfind("(", 0, len(part) - 4)
                    if first_paren > -1:
                        record.modifiers_mask = parse_heal(
                            record.healer,
                            part[first_paren + 1:len(part) - 1],
                            begin_time,
                        )

                return record

    return None
