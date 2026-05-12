"""
Filter plugins backing the alignment-aware CIDR selector.

Exposed filters
---------------
find_next_aligned_block(parent_cidr, prefix_length, occupied, policy='first-fit')
    Return the first /prefix_length sub-CIDR of parent_cidr that
       (a) is aligned on a /prefix_length boundary AND
       (b) does not overlap any CIDR in `occupied`,
    chosen according to `policy`. Return None when no such block exists.

list_aligned_blocks(parent_cidr, prefix_length, occupied, limit=5)
    Return up to `limit` non-overlapping, aligned candidates for preview.

Why a Python filter and not pure Jinja
--------------------------------------
CIDR alignment is a bit-mask check ((net.network_address) % size == 0) and
overlap detection is a pairwise interval check. Both are trivial in Python's
ipaddress module; the Jinja equivalents using `ansible.utils.ipaddr` are
either O(n^2) string-ops or impossible to express cleanly. Keeping the
algorithm here also makes it unit-testable (see tests/test_alignment.py).
"""

from __future__ import annotations

import ipaddress
from typing import Iterable, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — fully implemented; the contribution point is below.
# ─────────────────────────────────────────────────────────────────────────────

def _to_net(cidr) -> ipaddress._BaseNetwork:
    """Coerce 'a.b.c.d/n' (or an IPv6 form) to a strict ipaddress network."""
    return ipaddress.ip_network(str(cidr).strip(), strict=False)


def _iter_aligned_candidates(parent, prefix_length: int) -> Iterable[ipaddress._BaseNetwork]:
    """
    Yield every aligned sub-network of size /prefix_length inside parent,
    in ascending address order. `ipaddress.subnets()` already enforces
    alignment, so we get correctness for free.
    """
    if prefix_length < parent.prefixlen:
        return
    yield from parent.subnets(new_prefix=prefix_length)


def _overlaps_any(candidate, occupied_nets) -> bool:
    """True if `candidate` shares any address with any net in `occupied_nets`."""
    return any(candidate.overlaps(o) for o in occupied_nets)


# ─────────────────────────────────────────────────────────────────────────────
# ❶ CONTRIBUTION POINT — implement the selection algorithm here.
#
# Contract:
#   parent_cidr      str       e.g. "10.217.0.0/16"
#   prefix_length    int       e.g. 22
#   occupied         list[str] e.g. ["10.217.0.0/22", "10.217.4.0/24"]
#   policy           str       "first-fit"  → first aligned, non-overlapping
#                              "last-fit"   → last aligned, non-overlapping
#                              (extend with your own policies if you want;
#                               "best-fit" doesn't really apply here because
#                               every aligned slot of the requested size has
#                               identical size — only position differs.)
#
# Return:
#   str ("a.b.c.d/N") on success, or None when no candidate fits.
#
# Trade-offs to consider:
#   * first-fit packs allocations toward the low end of the parent,
#     leaving large contiguous holes at the high end — good for later
#     summarisation, bad for human-memorable spacing.
#   * last-fit packs toward the top, useful when policy carves "stable"
#     space at the bottom and "ephemeral" space at the top.
#   * Should an `occupied` block at a *coarser* prefix (e.g. a /20 we
#     can't subdivide) block all four /22s inside it? With this contract
#     and `overlaps()`, yes — which is almost always what you want.
#   * 5–10 lines of real logic is plenty. Don't over-engineer.
# ─────────────────────────────────────────────────────────────────────────────

def find_next_aligned_block(parent_cidr: str,
                            prefix_length: int,
                            occupied: Optional[List[str]] = None,
                            policy: str = "first-fit") -> Optional[str]:
    """
    See module docstring for the contract.

    The helpers above give you:
      - _to_net(cidr)                         → ipaddress.IPv4Network / IPv6Network
      - _iter_aligned_candidates(parent, n)   → generator of aligned /n subnets
      - _overlaps_any(candidate, occupied_nets) → bool
    """
    parent = _to_net(parent_cidr)
    occupied_nets = [_to_net(o) for o in (occupied or [])]

    # TODO (user): implement the selection algorithm.
    #
    # Reference skeleton — uncomment and adapt:
    #
    # if policy == "first-fit":
    #     for candidate in _iter_aligned_candidates(parent, prefix_length):
    #         if not _overlaps_any(candidate, occupied_nets):
    #             return str(candidate)
    #     return None
    #
    # elif policy == "last-fit":
    #     ...
    #
    # else:
    #     raise ValueError(f"Unknown allocation policy: {policy!r}")

    raise NotImplementedError(
        "find_next_aligned_block is not implemented yet — see the TODO "
        "in roles/infoblox_cidr_allocate/filter_plugins/cidr_allocation.py"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Preview filter — re-uses find_next_aligned_block under the hood by
# repeatedly excluding the previous choice. Useful for the summary report
# to show "here are 5 other options we could have picked".
# ─────────────────────────────────────────────────────────────────────────────

def list_aligned_blocks(parent_cidr: str,
                        prefix_length: int,
                        occupied: Optional[List[str]] = None,
                        limit: int = 5) -> List[str]:
    """Return up to `limit` aligned, non-overlapping candidates, in policy order.

    Uses first-fit ordering regardless of the policy used for selection —
    this is just a preview for the operator.
    """
    parent = _to_net(parent_cidr)
    occupied_nets = [_to_net(o) for o in (occupied or [])]
    out: List[str] = []
    for candidate in _iter_aligned_candidates(parent, prefix_length):
        if len(out) >= limit:
            break
        if not _overlaps_any(candidate, occupied_nets):
            out.append(str(candidate))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Ansible filter-plugin wiring
# ─────────────────────────────────────────────────────────────────────────────

class FilterModule(object):
    def filters(self):
        return {
            "find_next_aligned_block": find_next_aligned_block,
            "list_aligned_blocks": list_aligned_blocks,
        }
