from __future__ import annotations

from eqlogparser.models import LineData


def need_processing(line_data: LineData) -> bool:
    from eqlogparser.player_manager import PlayerManager
    action = line_data.action
    if len(action) <= 10:
        return True

    action_lower = action.lower()
    found = False

    if len(action) > 20 and action_lower.startswith("targeted (player)"):
        PlayerManager.instance().add_verified_player(action[19:], line_data.begin_time)
        found = True

    elif action_lower.endswith(" joined the raid.") and not action_lower.startswith("you have"):
        test = action[:-17]
        if PlayerManager.is_possible_player_name(test, len(test)):
            PlayerManager.instance().add_verified_player(test, line_data.begin_time)
            found = True

    elif action_lower.endswith(" has joined the group."):
        test = action[:-22]
        if PlayerManager.is_possible_player_name(test):
            PlayerManager.instance().add_verified_player(test, line_data.begin_time)
        else:
            PlayerManager.instance().add_merc(test)
        found = True

    elif action_lower.endswith(" has left the raid."):
        test = action[:-19]
        if PlayerManager.is_possible_player_name(test):
            PlayerManager.instance().add_verified_player(test, line_data.begin_time)
            found = True

    elif action_lower.endswith(" has left the group."):
        test = action[:-20]
        if PlayerManager.is_possible_player_name(test):
            PlayerManager.instance().add_verified_player(test, line_data.begin_time)
        else:
            PlayerManager.instance().add_merc(test)
        found = True

    elif action_lower.endswith(" is now the leader of your raid."):
        test = action[:-32]
        if PlayerManager.is_possible_player_name(test):
            PlayerManager.instance().add_verified_player(test, line_data.begin_time)
            found = True

    elif action_lower.startswith("glug, glug, glug...  "):
        end = PlayerManager.find_possible_player_name(action, start=21, end=" ")
        if end != -1:
            remaining = action[end:]
            if remaining.lower().startswith(" takes a drink "):
                PlayerManager.instance().add_verified_player(action[21:end], line_data.begin_time)
                found = True

    return not found
