from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class LineData:
    action: str = ""
    begin_time: float = float("nan")
    line_number: int = 0
    split: Optional[List[str]] = None


@dataclass
class HitRecord:
    total: int = 0
    over_total: int = 0
    type: str = ""
    sub_type: str = ""
    modifiers_mask: int = -1


@dataclass
class HealRecord(HitRecord):
    healer: str = ""
    healed: str = ""


@dataclass
class DamageRecord(HitRecord):
    attacker: str = ""
    attacker_owner: Optional[str] = None
    defender: str = ""
    defender_owner: Optional[str] = None
    attacker_is_spell: bool = False


@dataclass
class DeathRecord:
    killed: str = ""
    killer: str = ""
    message: str = ""
    previous: str = ""


@dataclass
class LootRecord:
    player: str = ""
    item: str = ""
    quantity: int = 0
    npc: str = ""
    is_currency: bool = False


@dataclass
class ResistRecord:
    attacker: str = ""
    spell: str = ""
    defender: str = ""


@dataclass
class RandomRecord:
    player: str = ""
    rolled: int = 0
    to: int = 0
    from_num: int = 0


@dataclass
class MezBreakRecord:
    breaker: str = ""
    awakened: str = ""


@dataclass
class SpecialRecord:
    code: str = ""
    player: str = ""


@dataclass
class TauntRecord:
    player: str = ""
    npc: str = ""
    success: bool = False
    is_improved: bool = False


@dataclass
class ZoneRecord:
    zone: str = ""


@dataclass
class SpellData:
    id: str = ""
    name: str = ""
    duration: int = 0
    is_beneficial: bool = False
    resist: str = ""
    damaging: int = 0
    target: int = 0
    class_mask: int = 0
    level: int = 0
    lands_on_you: str = ""
    lands_on_other: str = ""
    wear_off: str = ""
    proc: int = 0
    adps: int = 0
    is_unknown: bool = False
    seen_recently: bool = False


@dataclass
class SpellCast:
    spell: str = ""
    caster: str = ""
    spell_data: Optional[SpellData] = None
    interrupted: bool = False


@dataclass
class ReceivedSpell:
    receiver: str = ""
    is_wear_off: bool = False
    spell_data: Optional[SpellData] = None
    ambiguity: List[SpellData] = field(default_factory=list)
