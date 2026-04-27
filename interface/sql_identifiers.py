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
