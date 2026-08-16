"""Unread count for the dictation inbox (B-021)."""

from __future__ import annotations


def inbox_unread_count(config: dict, history_len: int) -> int:
    ack = int(config.get("inbox_ack_len", 0) or 0)
    if history_len <= ack:
        return 0
    return history_len - ack


def ack_inbox(config: dict, history_len: int) -> None:
    config["inbox_ack_len"] = history_len
