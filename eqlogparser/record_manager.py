from __future__ import annotations
from collections import defaultdict
from typing import Any


class RecordManager:
    _instance: RecordManager | None = None

    def __init__(self):
        self._records: dict[str, list[tuple[float, Any]]] = defaultdict(list)

    @classmethod
    def instance(cls) -> RecordManager:
        if cls._instance is None:
            cls._instance = RecordManager()
        return cls._instance

    def _add(self, key: str, record: Any, begin_time: float) -> None:
        self._records[key].append((begin_time, record))

    def add_damage(self, record, begin_time: float) -> None:
        self._add("damage", record, begin_time)

    def add_heal(self, record, begin_time: float) -> None:
        self._add("heal", record, begin_time)

    def add_death(self, record, begin_time: float) -> None:
        self._add("death", record, begin_time)

    def add_loot(self, record, begin_time: float) -> None:
        self._add("loot", record, begin_time)

    def add_spell_cast(self, record, begin_time: float) -> None:
        self._add("spell_cast", record, begin_time)

    def add_received_spell(self, record, begin_time: float) -> None:
        self._add("received_spell", record, begin_time)

    def add_resist(self, record, begin_time: float) -> None:
        self._add("resist", record, begin_time)

    def add_random(self, record, begin_time: float) -> None:
        self._add("random", record, begin_time)

    def add_mez_break(self, record, begin_time: float) -> None:
        self._add("mez_break", record, begin_time)

    def add_special(self, record, begin_time: float) -> None:
        self._add("special", record, begin_time)

    def add_zone(self, record, begin_time: float) -> None:
        self._add("zone", record, begin_time)

    def add_taunt(self, record, begin_time: float) -> None:
        self._add("taunt", record, begin_time)

    def get_all(self, key: str) -> list[tuple[float, Any]]:
        return list(self._records.get(key, []))

    def get_spells_during(self, begin_time: float, end_time: float, reverse: bool = False):
        spells = [
            (t, r) for t, r in self._records.get("spell_cast", [])
            if begin_time <= t <= end_time
        ]
        if reverse:
            spells.reverse()
        return spells

    def update_npc_spell_stats(self, npc: str, resist, landed: bool = False) -> None:
        pass

    def clear(self) -> None:
        self._records.clear()
