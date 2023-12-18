import pathlib as pl
import re

_RX_MARKDOWN_HEADING_ID_LEGAL_CHARS = re.compile(r"[^0-9a-z_-]")

HTML_SYMBOL_SUCCESS = "&#9989;"  # check mark
HTML_SYMBOL_FAILURE = "&#10060;"  # cross mark


def bool_to_emoji(x: bool) -> str:
    """Return a checkmark if x is True, a crossmark if x is False."""
    return HTML_SYMBOL_SUCCESS if x else HTML_SYMBOL_FAILURE


def file_tail(file: pl.Path, n: int = 10) -> str:
    """Return the last n lines of a file."""
    with open(file, "r", encoding="UTF-8") as f:
        lines = f.readlines()
        return "".join(lines[-n:])


def _markdown_heading_to_id(heading: str) -> str:
    """Convert a markdown heading to a valid id to link to via (my link)[#id]."""
    return _RX_MARKDOWN_HEADING_ID_LEGAL_CHARS.sub("", heading.lower())


def markdown_heading_to_link(heading: str, title: str | None = None) -> str:
    """Convert a markdown heading to a link."""
    title = heading if title is None else title
    return f"[{title}](#{_markdown_heading_to_id(heading)})"
