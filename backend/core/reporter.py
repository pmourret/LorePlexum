"""Collecteur de messages découplé du terminal.

Le cœur métier n'appelle plus `print()` ni `input()` : il *rapporte* des messages
horodatés (niveau + texte) à un Reporter. Selon le contexte, ces messages sont :
  - affichés en console (CLI) via `echo=True` ;
  - renvoyés à la couche web pour être rendus en toasts / journal d'exécution.

C'est la brique qui permet au même pipeline de servir le CLI et l'interface web.
Contrairement à l'ancien ShellPrinter, ce Reporter ne demande jamais de saisie :
toutes les décisions utilisateur sont désormais des paramètres du pipeline.
"""

from datetime import datetime


# Niveaux de message, réutilisés par la couche d'affichage (couleur / icône).
INFO = "info"
SUCCESS = "success"
ERROR = "error"
WARNING = "warning"


class Reporter:
    def __init__(self, echo=False):
        # echo=True : on imprime aussi en console (utile pour le CLI et le debug).
        self.echo = echo
        self.messages = []

    def _add(self, level, message):
        entry = {
            "level": level,
            "message": message,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        self.messages.append(entry)
        if self.echo:
            self._print(entry)
        return entry

    def info(self, message):
        return self._add(INFO, message)

    def success(self, message):
        return self._add(SUCCESS, message)

    def error(self, message):
        return self._add(ERROR, message)

    def warning(self, message):
        return self._add(WARNING, message)

    def has_errors(self):
        return any(m["level"] == ERROR for m in self.messages)

    def _print(self, entry):
        """Affichage console optionnel (CLI / debug). Import local pour ne pas
        imposer colorama/emoji à la couche web qui n'en a pas besoin."""
        try:
            from colorama import Fore, Style
            colors = {
                INFO: Fore.BLUE,
                SUCCESS: Fore.GREEN,
                ERROR: Fore.RED,
                WARNING: Fore.YELLOW,
            }
            icons = {INFO: "ℹ️ ", SUCCESS: "✅ ", ERROR: "❌ ", WARNING: "⚠️ "}
            color = colors.get(entry["level"], "")
            icon = icons.get(entry["level"], "")
            print(color + icon + entry["message"] + Style.RESET_ALL)
        except Exception:
            # Jamais faire échouer le pipeline pour un souci d'affichage.
            print(f"[{entry['level']}] {entry['message']}")
