"""Rich-based rendering helpers shared by CLI commands."""

import platform

import typer
from rich import print
from rich.tree import Tree


def print_session_tree(root_label: str, animals: dict[str, tuple[int, list[str]]]) -> None:
    """
    Print sessions grouped by animal as a tree: root -> animal (count) -> session leaves.

    `animals` maps an animal name to a `(count, leaves)` pair, where `count` is shown next
    to the animal name and `leaves` are the (already Rich-styled) lines added below it.
    """
    tree = Tree(root_label)
    for animal, (count, leaves) in animals.items():
        branch = tree.add(f"[bold cyan]{animal}[/] [dim]({count})")
        for leaf in leaves:
            branch.add(leaf)
        if not leaves:
            branch.add("[dim]no sessions")

    print(tree)


def confirm(prompt: str) -> bool:
    """
    Ask for y/n confirmation, always reading from the controlling terminal.

    This bypasses `stdin`, so a piped answer (e.g. `yes | bnd ks ...`) cannot
    auto-confirm it: a human at the keyboard must actually respond.
    """
    tty_path = "CON" if platform.system() == "Windows" else "/dev/tty"
    try:
        with open(tty_path, "r") as tty:
            print(prompt, end="")
            response = tty.readline().strip().lower()
    except OSError:
        print("[red]No interactive terminal available to confirm. Aborting.")
        raise typer.Exit(code=1)

    return response.startswith("y")
