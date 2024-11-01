import os
from colorama import Fore, Style, init
import emoji

# Initialize colorama for Windows compatibility
init(autoreset=True)


class ShellPrinter:
    """
    A class to handle formatted output to the shell with colorama and emojis.
    Provides methods for success, info, error messages, and user input prompts.
    """

    def __init__(self):
        self.default_style = Fore.WHITE + Style.NORMAL

    def success(self, message):
        """Prints a success message in green with a check emoji."""
        print(Fore.GREEN + emoji.emojize("✅ ") + message + Style.RESET_ALL)

    def info(self, message):
        """Prints an informational message in blue with an info emoji."""
        print(Fore.BLUE + emoji.emojize("ℹ️ ") + message + Style.RESET_ALL)

    def error(self, message):
        """Prints an error message in red with a cross emoji."""
        print(Fore.RED + emoji.emojize("❌ ") + message + Style.RESET_ALL)

    def user_input(self, message):
        """Prompts the user for input with a question emoji in yellow."""
        return input(Fore.YELLOW + emoji.emojize("❓ ") + message + Style.RESET_ALL)

    def custom_print(self, message, color=Fore.WHITE):
        """Prints a message in a custom color."""
        print(color + message + Style.RESET_ALL)

    def separator(self, character="-", length=50):
        """Prints a separator line of a given character and length."""
        print(self.default_style + character * length + Style.RESET_ALL)

