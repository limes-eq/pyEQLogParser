from __future__ import annotations

_SECOND_PERSON = frozenset(["you", "yourself", "your"])
_THIRD_PERSON = frozenset(["himself", "herself", "itself"])


class PlayerManager:
    _instance: PlayerManager | None = None

    def __init__(self):
        self._verified_players: dict[str, float] = {}
        self._verified_pets: set[str] = set()
        self._pet_to_player: dict[str, str] = {}
        self._mercs: set[str] = set()
        self._player_classes: dict[str, str] = {}

    @classmethod
    def instance(cls) -> PlayerManager:
        if cls._instance is None:
            cls._instance = PlayerManager()
        return cls._instance

    def add_verified_player(self, name: str, begin_time: float) -> None:
        if name:
            self._verified_players[name] = begin_time

    def add_verified_pet(self, name: str) -> None:
        if name:
            self._verified_pets.add(name)

    def add_pet_to_player(self, pet: str, player: str) -> None:
        if pet and player:
            self._pet_to_player[pet] = player

    def add_merc(self, name: str) -> None:
        if name:
            self._mercs.add(name)

    def is_verified_player(self, name: str) -> bool:
        if not name:
            return False
        return (name in self._verified_players or
                name.lower() in _SECOND_PERSON)

    def is_verified_pet(self, name: str) -> bool:
        return bool(name) and name in self._verified_pets

    def get_player_from_pet(self, pet: str) -> str | None:
        return self._pet_to_player.get(pet)

    def set_active_player_class(self, name: str, class_name: str, confidence: int, begin_time: float) -> None:
        if name and class_name:
            self._player_classes[name] = class_name

    def get_player_classes(self) -> dict[str, str]:
        return dict(self._player_classes)

    @staticmethod
    def replace_player(name: str, alternative: str) -> str:
        if not name:
            return name
        if name.lower() in _THIRD_PERSON:
            return alternative
        if name.lower() in _SECOND_PERSON:
            from eqlogparser.config import Config
            return Config.player_name
        return name

    @staticmethod
    def is_possible_player_name(part: str, stop: int = -1) -> bool:
        return PlayerManager.find_possible_player_name(part, stop=stop) > -1

    @staticmethod
    def find_possible_player_name(part: str, start: int = 0, stop: int = -1,
                                   end: str = "") -> int:
        if not part:
            return -1
        if stop == -1:
            stop = len(part)
        if stop - start < 3:
            return -1

        dot_count = 0
        for i in range(start, stop):
            if end and part[i] == end:
                return i
            if i > 2 and part[i] == ".":
                dot_count += 1
                if dot_count > 1:
                    return -1
            elif not part[i].isalpha():
                return -1
        return stop
