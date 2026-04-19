from __future__ import annotations
import os
import sys
from eqlogparser.models import SpellData


def _base_dir() -> str:
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


_DEFAULT_SPELL_FILE = os.path.join(_base_dir(), "resources", "spells_us.txt")


class DataManager:
    _instance: DataManager | None = None

    def __init__(self):
        self._spells_by_name: dict[str, SpellData] = {}
        self._cast_on_other: dict[str, list[SpellData]] = {}
        self._current_spell_file: str = ""
        if os.path.exists(_DEFAULT_SPELL_FILE):
            self.load_spell_file(_DEFAULT_SPELL_FILE)

    @classmethod
    def instance(cls) -> DataManager:
        if cls._instance is None:
            cls._instance = DataManager()
        return cls._instance

    def reset_combat_state(self) -> None:
        """Clear per-parse state without discarding the loaded spell DB."""
        pass  # currently all combat state lives in RecordManager / PlayerManager

    def load_spell_file(self, path: str) -> None:
        self._spells_by_name.clear()
        self._cast_on_other.clear()
        self._current_spell_file = path
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                parts = line.rstrip("\n").split("^")
                if len(parts) < 8:
                    continue
                spell_id = parts[0].strip()
                name = parts[1].strip()
                cast_on_other = parts[7]  # preserve leading space
                if not name:
                    continue
                spell = SpellData(id=spell_id, name=name)
                self._spells_by_name[name] = spell
                if cast_on_other:
                    self._cast_on_other.setdefault(cast_on_other, []).append(spell)

    def get_spells_by_cast_on_other(self, suffix: str) -> list[SpellData]:
        return self._cast_on_other.get(suffix, [])

    def get_spell_by_name(self, name: str) -> SpellData | None:
        return self._spells_by_name.get(name)

    def get_damaging_spell_by_name(self, name: str) -> SpellData | None:
        return self._spells_by_name.get(name)

    def get_det_spell_by_name(self, name: str) -> SpellData | None:
        return self._spells_by_name.get(name)

    def add_unknown_spell(self, name: str) -> SpellData:
        spell = SpellData(name=name, is_unknown=True)
        self._spells_by_name[name] = spell
        return spell

    def abbreviate_spell_name(self, name: str) -> str:
        return name

    def get_spell_by_abbrv(self, name: str) -> SpellData | None:
        return self._spells_by_name.get(name)

    def is_old_spell(self, name: str) -> bool:
        return False

    def is_valid_class_name(self, name: str) -> bool:
        return False

    def is_player_spell(self, name: str) -> bool:
        return False

    def get_spell_class(self, name: str) -> str | None:
        return None

    def update_adps(self, spell_data: SpellData) -> None:
        pass

    def get_lands_on_you(self, split: list[str]):
        return _EmptySearchResult()

    def get_lands_on_other(self, split: list[str], out_player: list[str] | None = None):
        return _EmptySearchResult()

    def get_wear_off(self, split: list[str]):
        return _EmptySearchResult()

    def zone_changed(self) -> None:
        pass

    def clear_active_adps(self) -> None:
        pass

    def remove_active_fight(self, name: str) -> None:
        pass

    def get_fight(self, name: str):
        return None


class _EmptySearchResult:
    spell_data: list[SpellData] = []
    data_index: int = -1
