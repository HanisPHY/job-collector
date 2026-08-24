# -*- coding: utf-8 -*-
"""Evaluator A - rubric item 7: does open_plan satisfy
    min(FLOOR, supply) <= open <= CEIL
for ANY cap2, not just the ones seen in the real corpus?  Try to construct a
counterexample (design_v1.md's own hint: "1a_t3 much, B1 little, 1a_t2 zero"),
then brute-force a large adversarial search.
"""
import random

from _evalA_base import ALWAYS_OPEN, CEIL, FLOOR, OPEN_ORDER, banner, open_plan


def supply_of(cap2):
    return sum(cap2.get(s, 0) for s in OPEN_ORDER)


def check(cap2, label=""):
    plan, opened = open_plan(cap2)
    supply = supply_of(cap2)
    lo_ok = opened >= min(FLOOR, supply)
    hi_ok = opened <= CEIL
    status = "OK" if (lo_ok and hi_ok) else "*** VIOLATION ***"
    print("   %-40s cap2=%-40s supply=%-4d open=%-4d %s" %
          (label, cap2, supply, opened, status))
    return lo_ok and hi_ok


def main():
    banner("open_plan(cap2) invariants: min(FLOOR,supply) <= open <= CEIL  (FLOOR=%d CEIL=%d)"
           % (FLOOR, CEIL))

    print("\n-- hand-picked adversarial cases (design_v1.md's own hint) --")
    cases = [
        ("(1) a lot, (4) little, (2) zero", {"1a_t3": 1000, "B1": 1, "1a_t2": 0}),
        ("(1) zero, (4) a lot, (2) zero", {"1a_t3": 0, "B1": 1000, "1a_t2": 0}),
        ("(1)(4) both zero, (2) huge", {"1a_t3": 0, "B1": 0, "1a_t2": 100000}),
        ("all zero", {"1a_t3": 0, "B1": 0, "1a_t2": 0}),
        ("(1) exactly at cap, others zero", {"1a_t3": 35, "B1": 0, "1a_t2": 0}),
        ("(1) just under FLOOR, (2) tiny filler", {"1a_t3": 29, "B1": 0, "1a_t2": 1}),
        ("(1) just under FLOOR, (2) filler overshoots", {"1a_t3": 29, "B1": 0, "1a_t2": 5}),
        ("(1)+(4) already over FLOOR, (2) huge (must NOT add)",
         {"1a_t3": 20, "B1": 15, "1a_t2": 100000}),
        ("negative-ish / missing keys", {}),
        ("only (2) present, no (1)/(4) keys at all", {"1a_t2": 40}),
        ("(1) between FLOOR and CEIL, (4) present too", {"1a_t3": 32, "B1": 10, "1a_t2": 0}),
        ("supply < FLOOR entirely (thin day)", {"1a_t3": 2, "B1": 1, "1a_t2": 1}),
    ]
    all_ok = True
    for label, cap2 in cases:
        all_ok &= check(cap2, label)

    print("\n-- brute-force random search, 500,000 samples, cap2 in [0,200] each --")
    random.seed(20260821)
    worst_lo = 10 ** 9
    worst_hi = -1
    violations = 0
    for _ in range(500000):
        cap2 = {"1a_t3": random.randint(0, 200),
                 "B1": random.randint(0, 200),
                 "1a_t2": random.randint(0, 200)}
        plan, opened = open_plan(cap2)
        supply = supply_of(cap2)
        lo_bound = min(FLOOR, supply)
        if opened < lo_bound or opened > CEIL:
            violations += 1
            if violations <= 5:
                print("   COUNTEREXAMPLE: cap2=%s open=%d bounds=[%d,%d]"
                      % (cap2, opened, lo_bound, CEIL))
        worst_lo = min(worst_lo, opened - lo_bound)
        worst_hi = max(worst_hi, opened - CEIL)
    print("   violations found: %d / 500000" % violations)
    print("   tightest margin above floor (min observed open-lo_bound): %d" % worst_lo)
    print("   largest margin above ceiling (max observed open-CEIL, should be <=0): %d"
          % worst_hi)

    print("\n-- extreme values (very large, to rule out overflow-style edge behaviour) --")
    for v in (0, 1, 34, 35, 36, 46, 47, 48, 10 ** 6, 10 ** 9):
        cap2 = {"1a_t3": v, "B1": v, "1a_t2": v}
        check(cap2, "uniform cap2=%d" % v)

    print("\nRESULT: %s" % ("all hand-picked + brute-force cases satisfy both bounds"
                             if all_ok and violations == 0 else
                             "COUNTEREXAMPLE(S) FOUND -- see above"))


if __name__ == "__main__":
    main()
