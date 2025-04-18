def clear_indentation(text: str) -> str:
    """
    Clear indentation from the text.
    :param text: The text to clear indentation from.
    :return: The text without indentation.
    """
    lines = text.splitlines()
    return "\n".join(line.strip() for line in lines if line.strip()) + "\n"
