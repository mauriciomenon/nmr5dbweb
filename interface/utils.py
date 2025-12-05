# utils.py
# Funções utilitárias: normalização e serialização para DuckDB local search pipeline.

import re
import unicodedata
from datetime import datetime, date
import decimal

def normalize_text(s: str) -> str:
    """
    Normaliza texto:
      - remove acentos
      - lower-case
      - substitui pontuação por espaço
      - substitui hífen/underscore por espaço
      - colapsa espaços
    Retorna string vazia para None.
    """
    if s is None:
        return ""
    if not isinstance(s, str):
        try:
            s = str(s)
        except Exception:
            return ""
    # remover acentos
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = s.lower()
    # substituir pontuação por espaço (mantém letras, números e underscore)
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    # substituir underscores/hyphens por espaço
    s = re.sub(r"[_\-]+", " ", s)
    # colapsar espaços
    s = re.sub(r"\s+", " ", s).strip()
    return s

def serialize_value(v):
    """Converte tipos retornados pelo DuckDB em valores JSON-compatíveis (pronto para json.dumps)."""
    if v is None:
        return None
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, decimal.Decimal):
        # representamos decimal como float (pode ajustar para str se preferir precisão)
        return float(v)
    if isinstance(v, (bytes, bytearray, memoryview)):
        try:
            return bytes(v).decode("utf-8", errors="replace")
        except Exception:
            try:
                return v.tobytes().decode("utf-8", errors="replace")
            except Exception:
                return repr(v)
    if isinstance(v, (int, float, str, bool)):
        return v
    # fallback
    try:
        return str(v)
    except Exception:
        return None