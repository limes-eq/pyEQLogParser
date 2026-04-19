from __future__ import annotations
from dataclasses import dataclass, field


class ChatChannels:
    Auction = "auction"
    Say = "say"
    Guild = "guild"
    Fellowship = "fellowship"
    Tell = "tell"
    Shout = "shout"
    Group = "group"
    Raid = "raid"
    Ooc = "ooc"


@dataclass
class ChatType:
    YOU = "You"

    channel: str = ""
    sender: str = ""
    receiver: str = ""
    sender_is_you: bool = False
    text: str = ""
    text_start: int = 0
    keyword_start: int = 0
    begin_time: float = 0.0

    def __init__(self, channel: str = "", sender: str = "", text_start: int = 0, receiver: str = ""):
        from eqlogparser.config import Config
        self.channel = channel
        self.sender = sender
        self.text_start = text_start
        self.receiver = receiver
        self.sender_is_you = sender == self.YOU or sender == Config.player_name
        self.text = ""
        self.keyword_start = 0
        self.begin_time = 0.0


def parse_chat_type(action: str) -> ChatType | None:
    if not action:
        return None
    if action.startswith("You "):
        return _check_you_criteria(action)
    # Fast reject: non-"You" chat lines always contain ", '" (says/auctions/shouts/tells)
    # or " -> " (cross-server tell) or "'My leader is" (pet speech)
    if ", '" not in action and " -> " not in action and "'My leader is" not in action:
        return None
    return _check_other_criteria(action)


def _starts_with_quote(s: str, prefix: str) -> int:
    if s.startswith(prefix):
        idx = s.find("'", len(prefix))
        if idx > -1:
            return idx + 1 if len(s) > idx + 1 else idx
    return -1


def _match_any_player(s: str) -> tuple[str, int]:
    dot_index = -1
    for i, c in enumerate(s):
        if c == ".":
            if dot_index != -1:
                return "", -1
            dot_index = i + 1
        elif c in (" ", ":"):
            receiver = s[dot_index:i] if dot_index != -1 else s[:i]
            return receiver, i
    return "", -1


def _match_tell_player(s: str) -> tuple[str, int]:
    dot_index = -1
    ws_index = -1
    for i, c in enumerate(s):
        if c == ".":
            if dot_index != -1:
                return "", -1
            dot_index = i + 1
        elif c == "'" or c == ":":
            receiver = s[dot_index:ws_index] if dot_index != -1 else s[:ws_index]
            return receiver, (i + 1 if len(s) > i + 1 else i)
        elif (ws_index == -1 and c.isspace()) or c == ",":
            ws_index = i
    return "", -1


def _match_tell_channel(s: str) -> tuple[str, int]:
    colon_index = -1
    digits_count = 0
    for i, c in enumerate(s):
        if c == ":":
            colon_index = i
            continue
        if colon_index != -1 or c == ",":
            if c.isdigit():
                digits_count += 1
                if digits_count > 2:
                    return "", -1
                continue
            if digits_count in (0, 1, 2) and len(s) > i + 2:
                found = s.find("'")
                if found > -1:
                    stop = colon_index if colon_index != -1 else i
                    channel = s[:stop].lower()
                    return channel, (found + 1 if len(s) > found + 1 else found)
            return "", -1
        if not (c.isalnum() or c in (".", ",")):
            return "", -1
    return "", -1


def _check_other_criteria(span: str) -> ChatType | None:
    sender, end = _match_any_player(span)
    if end == -1:
        return None

    rest = span[end:]

    if rest.startswith(" -> "):
        rest2 = rest[4:]
        receiver, end2 = _match_any_player(rest2)
        if end2 > -1:
            return ChatType(ChatChannels.Tell, sender, 27 + end + end2 + 4, receiver)

    start = _starts_with_quote(rest, " auctions, ")
    if start > -1:
        return ChatType(ChatChannels.Auction, sender, 27 + end + len(" auctions, ") + start - 1)

    if rest.startswith(" says"):
        rest2 = rest[5:]
        s2 = _starts_with_quote(rest2, ", ")
        if s2 > -1:
            return ChatType(ChatChannels.Say, sender, 27 + end + len(" says, ") + s2 - 1)
        s3 = _starts_with_quote(rest2, " out of character, ")
        if s3 > -1:
            return ChatType(ChatChannels.Ooc, sender, 27 + end + len(" says out of character, ") + s3 - 1)

    if rest.startswith(" tells "):
        rest2 = rest[7:]
        if rest2.startswith("the "):
            rest3 = rest2[4:]
            for ch_str, ch_name in [("fellowship, ", ChatChannels.Fellowship),
                                      ("group, ", ChatChannels.Group),
                                      ("guild, ", ChatChannels.Guild),
                                      ("raid, ", ChatChannels.Raid)]:
                s = _starts_with_quote(rest3, ch_str)
                if s > -1:
                    return ChatType(ch_name, sender, 27 + end + len(" tells the ") + len(ch_str) + s - 1)
        elif rest2.startswith("you, "):
            s = rest2.find("'", 5)
            if s > -1:
                return ChatType(ChatChannels.Tell, sender, 27 + end + len(" tells you, ") + (s - 4), ChatType.YOU)
        else:
            channel, s = _match_tell_channel(rest2)
            if s > -1:
                return ChatType(channel, sender, 27 + end + len(" tells ") + s)

    s = _starts_with_quote(rest, " told you, ")
    if s > -1:
        return ChatType(ChatChannels.Tell, sender, 27 + end + len(" told you, ") + s - 1)

    s = _starts_with_quote(rest, " shouts, ")
    if s > -1:
        return ChatType(ChatChannels.Shout, sender, 27 + end + len(" shouts, ") + s - 1)

    # check for pet saying "My leader is X"
    for i in range(len(span) - 1, -1, -1):
        if span[i] == " ":
            start_part = span[:i]
            if start_part.endswith("'My leader is") and len(start_part) > len("'My leader is"):
                start_part2 = start_part[:-(len(" 'My leader is"))]
                if start_part2.endswith(" says"):
                    last = start_part2.rfind(" ")
                    if last > -1:
                        pet_sender = start_part2[:last]
                        return ChatType(ChatChannels.Say, pet_sender, 27 + len(start_part2) + 2)

    return None


def _check_you_criteria(span: str) -> ChatType | None:
    rest = span[4:]  # skip "You "

    s = _starts_with_quote(rest, "auction, ")
    if s > -1:
        return ChatType(ChatChannels.Auction, ChatType.YOU, 27 + len("You auction, ") + s - 1)

    if rest.startswith("say"):
        rest2 = rest[3:]
        s2 = _starts_with_quote(rest2, ", ")
        if s2 > -1:
            return ChatType(ChatChannels.Say, ChatType.YOU, 27 + len("You say, ") + s2 - 1)
        if rest2.startswith(" to your "):
            rest3 = rest2[9:]
            for ch_str, ch_name in [("fellowship, ", ChatChannels.Fellowship),
                                      ("guild, ", ChatChannels.Guild)]:
                s = _starts_with_quote(rest3, ch_str)
                if s > -1:
                    return ChatType(ch_name, ChatType.YOU, 27 + len("You say to your ") + len(ch_str) + s - 1)
        s3 = _starts_with_quote(rest2, " out of character, ")
        if s3 > -1:
            return ChatType(ChatChannels.Ooc, ChatType.YOU, 27 + len("You say out of character, ") + s3 - 1)

    s = _starts_with_quote(rest, "shout, ")
    if s > -1:
        return ChatType(ChatChannels.Shout, ChatType.YOU, 27 + len("You shout, ") + s - 1)

    if rest.startswith("tell "):
        rest2 = rest[5:]
        channel, s = _match_tell_channel(rest2)
        if s > -1:
            return ChatType(channel, ChatType.YOU, 27 + len("You tell ") + s)
        if rest2.startswith("your "):
            rest3 = rest2[5:]
            for ch_str, ch_name in [("party, ", ChatChannels.Group), ("raid, ", ChatChannels.Raid)]:
                s = _starts_with_quote(rest3, ch_str)
                if s > -1:
                    return ChatType(ch_name, ChatType.YOU, 27 + len("You tell your ") + len(ch_str) + s - 1)

    if rest.startswith("told "):
        rest2 = rest[5:]
        receiver, s = _match_tell_player(rest2)
        if s > -1:
            return ChatType(ChatChannels.Tell, ChatType.YOU, 27 + len("You told ") + s, receiver)

    return None
