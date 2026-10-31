from typing import Annotated

from fastapi import Path, Query

Symbol = Annotated[str, Path(pattern=r"^[A-Za-z0-9.^=\-]{1,20}$")]
SymbolList = Annotated[str, Query(pattern=r"^[A-Za-z0-9.^=\-]{1,20}(,[A-Za-z0-9.^=\-]{1,20}){0,29}$")]


def split_symbols(value: str) -> list[str]:
    return list(dict.fromkeys(s.strip().upper() for s in value.split(",")))
