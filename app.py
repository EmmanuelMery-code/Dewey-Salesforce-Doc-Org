from __future__ import annotations

import argparse
import sys

from src.ui.app_cli_actions_mixin import CLI_ACTIONS
from src.ui.application import Application


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="app.py",
        description="Dewey - Salesforce org documentation tool.",
    )
    parser.add_argument(
        "--configuration",
        dest="configuration",
        default=None,
        help=(
            "Chemin vers un fichier de configuration app_settings.json a "
            "utiliser a la place de celui du repertoire de l'application."
        ),
    )
    parser.add_argument(
        "--action",
        dest="action",
        default=None,
        choices=CLI_ACTIONS,
        help=(
            "Action a executer au demarrage pour la derniere org utilisee du "
            "fichier de configuration : manifest, retrieve, documentation, all "
            "ou retrivation (retrieve puis documentation ; genere aussi le "
            "manifest au prealable s'il est absent)."
        ),
    )
    parser.add_argument(
        "--silent",
        dest="silent",
        action="store_true",
        default=False,
        help=(
            "Executer l'action sans afficher la fenetre de l'application "
            "(mode automatisation) ; ignore si --action n'est pas fourni."
        ),
    )
    return parser.parse_args(argv)


def main() -> None:
    args = _parse_args()

    app = Application(
        config_path=args.configuration,
        cli_action=args.action,
        cli_silent=args.silent,
    )

    if args.action and args.silent:
        exit_code = app.cli_exit_code if app.cli_exit_code is not None else 1
        app.destroy()
        sys.exit(exit_code)

    app.mainloop()


if __name__ == "__main__":
    main()
