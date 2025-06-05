# ANSI color codes
class Colors:
    RESET = "\033[0m"
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

def printc(msg: str, color: str = Colors.RESET) -> None:
    """
    Prints a message with the specified color.

    Args:
        msg (str): The message to print.
        color (str): The ANSI color code to use for the message. Defaults to RESET (no color).

    Returns:
        None
    """
    if color != Colors.RESET:
        print(f"{color}{msg}{Colors.RESET}")
    else:
        print(msg)