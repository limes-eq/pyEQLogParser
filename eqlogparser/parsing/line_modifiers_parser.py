from __future__ import annotations

_ALL_MODIFIERS: dict[str, int] = {
    "Assassinate": 1, "Crippling Blow": 1, "Critical": 1, "Deadly Strike": 1,
    "Double Bow Shot": 1, "Finishing Blow": 1, "Flurry": 1, "Headshot": 1,
    "Lucky": 1, "Rampage": 1, "Riposte": 1, "Slay Undead": 1,
    "Strikethrough": 1, "Twincast": 1, "Wild Rampage": 1,
}

_CRIT_MODIFIERS: dict[str, int] = {
    "Crippling Blow": 1, "Critical": 1, "Deadly Strike": 1, "Finishing Blow": 1,
}

NONE: int = -1
CRIT: int = 2
_TWINCAST: int = 1
_LUCKY: int = 4
_RAMPAGE: int = 8
_STRIKETHROUGH: int = 16
_RIPOSTE: int = 32
_ASSASSINATE: int = 64
_HEADSHOT: int = 128
_SLAY: int = 256
_DOUBLEBOW: int = 512
_FLURRY: int = 1024
_FINISHING: int = 2048

_mask_cache: dict[str, int] = {}


def is_assassinate(mask: int) -> bool: return mask > -1 and bool(mask & _ASSASSINATE)
def is_crit(mask: int) -> bool:        return mask > -1 and bool(mask & CRIT)
def is_double_bow_shot(mask: int) -> bool: return mask > -1 and bool(mask & _DOUBLEBOW)
def is_finishing_blow(mask: int) -> bool:  return mask > -1 and bool(mask & _FINISHING)
def is_flurry(mask: int) -> bool:      return mask > -1 and bool(mask & _FLURRY)
def is_headshot(mask: int) -> bool:    return mask > -1 and bool(mask & _HEADSHOT)
def is_lucky(mask: int) -> bool:       return mask > -1 and bool(mask & _LUCKY)
def is_twincast(mask: int) -> bool:    return mask > -1 and bool(mask & _TWINCAST)
def is_slay_undead(mask: int) -> bool: return mask > -1 and bool(mask & _SLAY)
def is_rampage(mask: int) -> bool:     return mask > -1 and bool(mask & _RAMPAGE)
def is_riposte(mask: int) -> bool:     return mask > -1 and bool(mask & _RIPOSTE) and not bool(mask & _STRIKETHROUGH)
def is_strikethrough(mask: int) -> bool: return mask > -1 and bool(mask & _STRIKETHROUGH)


def parse_damage(player: str, modifiers: str, current_time: float, is_player: bool) -> int:
    result = _parse(modifiers)
    if is_player:
        from eqlogparser.player_manager import PlayerManager
        if is_assassinate(result):
            PlayerManager.instance().add_verified_player(player, current_time)
            PlayerManager.instance().set_active_player_class(player, "ROG", 1, current_time)
        elif is_headshot(result) or is_double_bow_shot(result):
            PlayerManager.instance().add_verified_player(player, current_time)
            PlayerManager.instance().set_active_player_class(player, "RNG", 1, current_time)
        elif is_slay_undead(result):
            PlayerManager.instance().add_verified_player(player, current_time)
            PlayerManager.instance().set_active_player_class(player, "PAL", 1, current_time)
    return result


def parse_heal(player: str, modifiers: str, current_time: float) -> int:
    result = _parse(modifiers)
    if is_twincast(result):
        from eqlogparser.player_manager import PlayerManager
        PlayerManager.instance().add_verified_player(player, current_time)
    return result


def _parse(modifiers: str) -> int:
    if not modifiers:
        return -1
    if modifiers in _mask_cache:
        return _mask_cache[modifiers]
    result = _build_vector(modifiers)
    _mask_cache[modifiers] = result
    return result


def _build_vector(modifiers: str) -> int:
    result = 0
    temp = ""
    for word in modifiers.split(" "):
        temp += word
        if temp in _ALL_MODIFIERS:
            if temp in _CRIT_MODIFIERS:
                result |= CRIT
            if temp == "Lucky":
                result |= _LUCKY
            elif temp == "Assassinate":
                result |= _ASSASSINATE
            elif temp == "Double Bow Shot":
                result |= _DOUBLEBOW
            elif temp == "Finishing Blow":
                result |= _FINISHING
            elif temp == "Flurry":
                result |= _FLURRY
            elif temp == "Headshot":
                result |= _HEADSHOT
            elif temp == "Twincast":
                result |= _TWINCAST
            elif temp in ("Rampage", "Wild Rampage"):
                result |= _RAMPAGE
            elif temp == "Riposte":
                result |= _RIPOSTE
            elif temp == "Strikethrough":
                result |= _STRIKETHROUGH
            elif temp == "Slay Undead":
                result |= _SLAY
            temp = ""
        else:
            temp += " "
    return result
