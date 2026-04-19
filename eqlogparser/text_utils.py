def s_compare(s: str, start: int, count: int, test: str) -> bool:
    return s[start:start + count] == test


def parse_spell_or_npc(split: list[str], index: int) -> str:
    return " ".join(split[index:]).rstrip(".")


def to_lower(name: str) -> str:
    return "" if not name else name.lower()


def to_upper(name: str) -> str:
    if not name:
        return ""
    return name[0].upper() + name[1:]
