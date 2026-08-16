"""Tests for core.inbox_ui unread counter."""

from core.inbox_ui import ack_inbox, inbox_unread_count


def test_unread_zero_when_ack_matches():
    cfg = {"inbox_ack_len": 3}
    assert inbox_unread_count(cfg, 3) == 0


def test_unread_counts_new_items():
    cfg = {"inbox_ack_len": 1}
    assert inbox_unread_count(cfg, 4) == 3


def test_ack_sets_length():
    cfg = {}
    ack_inbox(cfg, 5)
    assert cfg["inbox_ack_len"] == 5
