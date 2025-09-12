"""
# models/event.py
"""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict

EventAction = Literal["created", "deleted", "modified", "moved"]
EventType = Literal["file", "directory"]


class DirEvent(TypedDict, total=True):
    """
    DirEvent _summary_

    _extended_summary_

    Args:
        TypedDict (_type_): _description_
        total (bool, optional): _description_. Defaults to True.
    """

    type: Literal["directory"]
    action: EventAction
    path: str
    src_path: NotRequired[str]


class Event(TypedDict, total=True):
    """
    Event _summary_

    _extended_summary_

    Args:
        TypedDict (_type_): _description_
        total (bool, optional): _description_. Defaults to True.
    """

    type: EventType
    action: EventAction
    path: str
    # Clés optionnelles selon action/type
    src_path: NotRequired[str]
    note_id: NotRequired[int | None]
    new_path: NotRequired[str]  # legacy (si jamais encore utilisé)
