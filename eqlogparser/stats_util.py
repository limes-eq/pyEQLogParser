UINT_MAX = 2**32 - 1


def parse_uint(s: str, default: int = UINT_MAX) -> int:
    if not s:
        return default
    result = 0
    for c in s:
        if not c.isdigit():
            return default
        result = result * 10 + ord(c) - 48
    return result


def create_record_key(type_: str, sub_type: str) -> str:
    from eqlogparser.labels import Labels
    key = sub_type
    if type_ in (Labels.Dd, Labels.Dot):
        key = type_ + "=" + key
    return key
