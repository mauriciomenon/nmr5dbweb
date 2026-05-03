def quote_identifier(value):
    text = str(value)
    if "\x00" in text:
        raise ValueError("identificador contem caractere invalido")
    return '"' + text.replace('"', '""') + '"'


def quote_engine_identifier(engine, value):
    if engine != "access":
        return quote_identifier(value)
    text = str(value)
    if "\x00" in text:
        raise ValueError("identificador contem caractere invalido")
    return "[" + text.replace("]", "]]") + "]"


def select_known_identifier(value, known_values):
    for known_value in known_values:
        if known_value == value:
            return known_value
    return None
