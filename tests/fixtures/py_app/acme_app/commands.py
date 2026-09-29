"""Command handlers, picked by name from a dispatch table."""


def _cmd_hello(args):
    print("hello", args)


def _cmd_bye(args):
    print("bye", args)


def cmd_list(args):
    print("list", args)


COMMANDS = {
    "hello": _cmd_hello,
    "bye": _cmd_bye,
    "list": cmd_list,
}


def dispatch(name: str, args: list[str]) -> None:
    COMMANDS[name](args)
