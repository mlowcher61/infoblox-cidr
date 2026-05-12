"""
Standalone unit tests for the alignment filter.

Run with:
    python -m pytest roles/infoblox_cidr_allocate/tests/test_alignment.py

These tests will FAIL until you implement find_next_aligned_block. That is
intentional — they describe the contract.
"""

import os
import sys
import pytest

# Make the sibling filter_plugins/ dir importable when running pytest directly.
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, "filter_plugins"))

import cidr_allocation as ca  # noqa: E402


# ─── first-fit ─────────────────────────────────────────────────────────────

def test_first_fit_empty_parent_returns_first_aligned_slot():
    assert ca.find_next_aligned_block("10.217.0.0/16", 22, []) == "10.217.0.0/22"


def test_first_fit_skips_occupied_blocks():
    occupied = ["10.217.0.0/22", "10.217.4.0/22"]
    assert ca.find_next_aligned_block("10.217.0.0/16", 22, occupied) == "10.217.8.0/22"


def test_first_fit_respects_alignment_even_when_a_24_is_taken():
    # A taken /24 inside the first /22 must block the *entire* /22.
    occupied = ["10.217.0.0/24"]
    assert ca.find_next_aligned_block("10.217.0.0/16", 22, occupied) == "10.217.4.0/22"


def test_returns_none_when_parent_is_full():
    # /24 inside /24: only one candidate (the parent itself); occupying it
    # leaves nothing.
    assert ca.find_next_aligned_block("10.217.0.0/24", 24, ["10.217.0.0/24"]) is None


def test_returns_none_when_prefix_smaller_than_parent():
    # Asking for a /8 from a /16 is nonsense — no candidates exist.
    assert ca.find_next_aligned_block("10.217.0.0/16", 8, []) is None


# ─── last-fit (optional — enable when you implement it) ───────────────────

@pytest.mark.xfail(reason="enable once last-fit is implemented", strict=False)
def test_last_fit_picks_top_of_parent():
    assert ca.find_next_aligned_block("10.217.0.0/16", 22, [], policy="last-fit") == "10.217.252.0/22"


# ─── preview ───────────────────────────────────────────────────────────────

def test_list_aligned_blocks_preview_excludes_occupied_and_limits():
    occupied = ["10.217.0.0/22"]
    preview = ca.list_aligned_blocks("10.217.0.0/16", 22, occupied, limit=3)
    assert preview == ["10.217.4.0/22", "10.217.8.0/22", "10.217.12.0/22"]


def test_unknown_policy_raises_value_error():
    with pytest.raises((ValueError, NotImplementedError)):
        ca.find_next_aligned_block("10.217.0.0/16", 22, [], policy="zigzag")
