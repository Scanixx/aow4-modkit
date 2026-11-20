"""Readable function groups. Named arguments keep context and side effects clear."""
from .constants import ListKind, DataType
from .expressions import call, group, Expr


class events:
    @staticmethod
    def new_turn():
        return call("events.new_turn", group(ListKind.CONDITIONS))

    @staticmethod
    def new_round():
        return call("events.new_round", group(ListKind.CONDITIONS))

    @staticmethod
    def victorious():
        return call("events.victorious", group(ListKind.CONDITIONS))


class core:
    @staticmethod
    def current_round():
        return call("core.current_round")


class players:
    @staticmethod
    def all():
        return call("players.all")

    @staticmethod
    def iterator(depth=0):
        return call("players.iterator", depth)

    @staticmethod
    def triggering():
        return call("players.triggering")

    @staticmethod
    def victorious():
        return call("players.victorious")

    @staticmethod
    def is_valid(player):
        return call("players.is_valid", player)

    @staticmethod
    def is_ai(player):
        return call("players.is_ai", player)

    @staticmethod
    def has_property(player, property):
        return call("players.has_property", player, property)

    @staticmethod
    def token_count(player, token):
        return call("players.token_count", player, call("tokens.definition", token))


class races:
    @staticmethod
    def of_player(player):
        return call("races.of_player", player)

    @staticmethod
    def is_valid(race):
        return call("races.is_valid", race)

    @staticmethod
    def has_transformation(race, transformation):
        return call("races.has_transformation", race, transformation)


class conditions:
    @staticmethod
    def all(*values):
        return call("conditions.all", group(ListKind.CONDITIONS, values))

    @staticmethod
    def any(*values):
        return call("conditions.any", group(ListKind.CONDITIONS, values))


class actions:
    @staticmethod
    def for_each_player(body):
        """Loop over all players; use players.iterator() in the body."""
        return call("actions.for_each", players.all(), group(ListKind.ACTIONS, body))

    @staticmethod
    def guard(checks, *, then, otherwise=()):
        """Build nested branches, preserving safe evaluation order."""
        body = list(then)
        for check in reversed(tuple(checks)):
            body = [actions.when(check, then=body, otherwise=otherwise)]
        return body

    @staticmethod
    def log(message: str):
        """Native diagnostics only; this does not open an in-game dialog."""
        return call("actions.log", message)

    @staticmethod
    def when(condition, *, then, otherwise=()):
        """Explicit branching; nest these to protect invalid references."""
        return call("actions.when", group(ListKind.CONDITIONS, [condition]),
                    group(ListKind.ACTIONS, then), group(ListKind.ACTIONS, otherwise))

    @staticmethod
    def add_property(*, player, property):
        return call("actions.add_property", player, property)

    @staticmethod
    def add_transformation(*, race, transformation):
        return call("actions.add_transformation", race, transformation)

    @staticmethod
    def give_token(*, player, token, amount=1):
        return call("actions.give_token", player, token, amount)

    @staticmethod
    def hide_token(*, player, token):
        return call("actions.hide_token", player, call("tokens.definition", token))


class variables:
    @staticmethod
    def player_pool(player):
        return call("variables.player_pool", player)

    @staticmethod
    def name(name: str):
        return call("variables.name", Expr(DataType.VARIABLE_NAME_PRESET, value=name))

    @staticmethod
    def exists(pool, name: str):
        return call("variables.exists", pool, variables.name(name))

    @staticmethod
    def set_integer(pool, name: str, value: int):
        return call("variables.set", pool, variables.name(name), call("variables.integer", value))
