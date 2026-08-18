#!/usr/bin/env python3
"""PRE deep-sieve benchmark and Proth-prime search.

This is a standalone standard-library program.  It compares two trial-division
sieve bounds on exactly the same Proth search starts.  Candidates have the form

    N = k * 2**m + 1

where k is odd and k < 2**m.  Surviving candidates are certified with Proth's
theorem.  A separate Miller-Rabin pass is available as an implementation sanity
check; it is not part of discovery cost and is not the primality proof.

Examples
--------
Run the built-in correctness checks

    python pre_proth_deep_sieve.py --self-test

Run a matched 100-digit benchmark

    python pre_proth_deep_sieve.py --digits 100 --rounds 200

Run several sizes with a separate round count for each size

    python pre_proth_deep_sieve.py \
        --digits 100 500 1000 --rounds 200 40 10 \
        --output pre_proth_results.json
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


sys.set_int_max_str_digits(100_000)

DEFAULT_SEED = 36_808_343
DEFAULT_BOUNDS = (12_841, 368_083)
DEFAULT_SEGMENT_SIZE = 256
MILLER_BASES = (2, 3, 5, 7, 11, 13, 17)


def primes_upto(limit: int) -> list[int]:
    """Return odd primes not exceeding limit."""
    if limit < 3:
        return []
    flags = bytearray(b"\x01") * (limit + 1)
    flags[0:2] = b"\x00\x00"
    for p in range(2, math.isqrt(limit) + 1):
        if flags[p]:
            count = (limit - p * p) // p + 1
            flags[p * p : limit + 1 : p] = b"\x00" * count
    return [p for p in range(3, limit + 1, 2) if flags[p]]


def jacobi(a: int, n: int) -> int:
    """Compute the Jacobi symbol (a/n) for positive odd n."""
    if n <= 0 or n % 2 == 0:
        raise ValueError("Jacobi denominator must be positive and odd")
    a %= n
    result = 1
    while a:
        while a % 2 == 0:
            a //= 2
            if n % 8 in (3, 5):
                result = -result
        a, n = n, a
        if a % 4 == 3 and n % 4 == 3:
            result = -result
        a %= n
    return result if n == 1 else 0


def miller_rabin(n: int, bases: Sequence[int] = MILLER_BASES) -> tuple[bool, int]:
    """Return probable-prime status and the number of modular powers used."""
    if n < 2:
        return False, 0
    small = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)
    for p in small:
        if n == p:
            return True, 0
        if n % p == 0:
            return False, 0

    d = n - 1
    s = 0
    while d % 2 == 0:
        d //= 2
        s += 1

    powers = 0
    for base in bases:
        if base >= n:
            continue
        powers += 1
        x = pow(base, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = x * x % n
            if x == n - 1:
                break
        else:
            return False, powers
    return True, powers


def proth_certificate(n: int) -> tuple[bool, int, int, int | None]:
    """Certify a Proth candidate.

    Return certified_prime, expensive_power_calls, Jacobi_trials, witness.
    For a valid Proth number, a True result is a deterministic primality proof.
    """
    root = math.isqrt(n)
    if root * root == n:
        return False, 0, 0, None

    witness = 2
    trials = 0
    while True:
        trials += 1
        symbol = jacobi(witness, n)
        if symbol == -1:
            certified = pow(witness, (n - 1) // 2, n) == n - 1
            return certified, 1, trials, witness if certified else None
        witness += 1


def proth_limits(digits: int, m: int) -> tuple[int, int]:
    """Return the odd-k interval producing exactly the requested digit count."""
    scale = 1 << m
    low = (10 ** (digits - 1) - 1 + scale - 1) // scale
    high = min(scale - 1, (10**digits - 2) // scale)
    if low % 2 == 0:
        low += 1
    if high % 2 == 0:
        high -= 1
    if low > high:
        raise RuntimeError("No valid Proth interval for this digit count and exponent")
    return low, high


@dataclass(frozen=True)
class SievePlan:
    bound: int
    m: int
    primes: tuple[int, ...]
    inverse_steps: tuple[int, ...]
    step_n: int
    setup_ms: float


def build_plan(m: int, bound: int) -> SievePlan:
    """Precompute one segmented sieve plan."""
    if m < 1:
        raise ValueError("m must be positive")
    if bound < 3:
        raise ValueError("sieve bound must be at least 3")

    started = time.perf_counter()
    primes = tuple(primes_upto(bound))
    step_n = 1 << (m + 1)
    inverse_steps = tuple(pow(step_n % p, -1, p) for p in primes)
    return SievePlan(
        bound=bound,
        m=m,
        primes=primes,
        inverse_steps=inverse_steps,
        step_n=step_n,
        setup_ms=(time.perf_counter() - started) * 1000,
    )


def sieve_segment(first_k: int, length: int, plan: SievePlan) -> bytearray:
    """Return one byte per candidate where one means survives the sieve.

    The equality guard preserves a candidate that is itself one of the sieve
    primes.  It is irrelevant for large searches but makes the sieve correct
    for small-number tests and general reuse.
    """
    if first_k <= 0 or first_k % 2 == 0:
        raise ValueError("first_k must be a positive odd integer")
    if length <= 0:
        raise ValueError("segment length must be positive")

    scale = 1 << plan.m
    first_n = first_k * scale + 1
    flags = bytearray(b"\x01") * length

    for p, inverse_step in zip(plan.primes, plan.inverse_steps):
        index = (-first_n * inverse_step) % p
        if index >= length:
            continue

        # Do not remove p merely because p divides itself.
        if first_n + index * plan.step_n == p:
            index += p
            if index >= length:
                continue

        count = (length - 1 - index) // p + 1
        flags[index:length:p] = b"\x00" * count

    return flags


def search_first_prime(
    start_k: int,
    k_high: int,
    plan: SievePlan,
    segment_size: int,
) -> dict[str, int | float]:
    """Find and certify the first Proth prime at or after start_k."""
    if start_k % 2 == 0:
        start_k += 1
    if start_k <= 0 or start_k > k_high:
        raise ValueError("start_k is outside the configured interval")

    scale = 1 << plan.m
    started = time.perf_counter()
    candidates_tested = 0
    expensive_powers = 0
    jacobi_trials = 0
    segments = 0

    while True:
        first_k = start_k + 2 * segments * segment_size
        remaining = (k_high - first_k) // 2 + 1
        if remaining <= 0:
            raise RuntimeError("Proth search reached the configured upper boundary")
        length = min(segment_size, remaining)
        flags = sieve_segment(first_k, length, plan)

        for index, survives in enumerate(flags):
            if not survives:
                continue
            k = first_k + 2 * index
            n = k * scale + 1
            candidates_tested += 1
            certified, powers, trials, witness = proth_certificate(n)
            expensive_powers += powers
            jacobi_trials += trials
            if certified:
                return {
                    "prime": n,
                    "k": k,
                    "m": plan.m,
                    "witness": int(witness),
                    "candidate_tests": candidates_tested,
                    "expensive_power_calls": expensive_powers,
                    "jacobi_trials": jacobi_trials,
                    "segments": segments + 1,
                    "elapsed_ms": (time.perf_counter() - started) * 1000,
                }
        segments += 1


def summarize(rows: Sequence[dict[str, int | float]], plan: SievePlan) -> dict:
    """Summarize matched search rows for one sieve bound."""
    return {
        "average_candidate_tests": statistics.mean(r["candidate_tests"] for r in rows),
        "median_candidate_tests": statistics.median(r["candidate_tests"] for r in rows),
        "maximum_candidate_tests": max(r["candidate_tests"] for r in rows),
        "average_expensive_power_calls": statistics.mean(
            r["expensive_power_calls"] for r in rows
        ),
        "average_jacobi_trials": statistics.mean(r["jacobi_trials"] for r in rows),
        "average_segments": statistics.mean(r["segments"] for r in rows),
        "average_search_ms": statistics.mean(r["elapsed_ms"] for r in rows),
        "median_search_ms": statistics.median(r["elapsed_ms"] for r in rows),
        "sieve_primes": len(plan.primes),
        "one_time_plan_setup_ms": plan.setup_ms,
    }


def matched_benchmark(
    digits: int,
    rounds: int,
    bounds: Sequence[int],
    segment_size: int,
    rng: random.Random,
    validate: bool,
) -> dict:
    """Compare all bounds on identical starts and return a JSON-safe result."""
    m = math.ceil(digits * math.log2(10) / 2)
    k_low, k_high = proth_limits(digits, m)
    margin = 2 * segment_size * 20_000
    if k_high - k_low <= margin:
        margin = max(2 * segment_size, (k_high - k_low) // 10)
    start_high = k_high - margin
    if start_high <= k_low:
        raise RuntimeError("Proth interval is too small for safe matched starts")

    starts = [rng.randrange(k_low, start_high + 1, 2) for _ in range(rounds)]
    plans = {bound: build_plan(m, bound) for bound in bounds}
    rows: dict[int, list[dict[str, int | float]]] = {bound: [] for bound in bounds}
    output_mismatches = 0
    validation_failures = 0
    validation_calls = 0

    print(f"START digits={digits} rounds={rounds} m={m}")
    for round_index, start_k in enumerate(starts):
        # Alternate order to reduce timing-order bias.
        order = tuple(bounds) if round_index % 2 == 0 else tuple(reversed(bounds))
        outputs: dict[int, int] = {}
        for bound in order:
            row = search_first_prime(start_k, k_high, plans[bound], segment_size)
            rows[bound].append(row)
            outputs[bound] = int(row["prime"])

        if len(set(outputs.values())) != 1:
            output_mismatches += 1

        if validate:
            validation_calls += 1
            probable, _ = miller_rabin(next(iter(outputs.values())))
            validation_failures += int(not probable)

        report_step = max(1, rounds // 5)
        if (round_index + 1) % report_step == 0 or round_index + 1 == rounds:
            print(f"PROGRESS digits={digits} done={round_index + 1}/{rounds}")

    summaries = {str(bound): summarize(rows[bound], plans[bound]) for bound in bounds}
    base = summaries[str(bounds[0])]
    deep = summaries[str(bounds[-1])]
    base_powers = base["average_expensive_power_calls"]
    deep_powers = deep["average_expensive_power_calls"]

    return {
        "digits": digits,
        "rounds": rounds,
        "proth_exponent_m": m,
        "results": summaries,
        "deep_vs_base": {
            "expensive_power_reduction_percent": 100 * (1 - deep_powers / base_powers),
            "search_time_change_percent": 100
            * (deep["average_search_ms"] / base["average_search_ms"] - 1),
            "average_expensive_powers_saved_per_prime": base_powers - deep_powers,
            "output_mismatches": output_mismatches,
        },
        "separate_validation": {
            "enabled": validate,
            "miller_calls": validation_calls,
            "validation_failures": validation_failures,
            "included_in_discovery_cost": False,
        },
        "all_outputs_exact_digits": all(
            len(str(row["prime"])) == digits
            for bound_rows in rows.values()
            for row in bound_rows
        ),
    }


def run_self_test() -> None:
    """Run fast checks for false removal and search-order preservation."""
    print("SELF_TEST_START")

    # Regression test for the candidate-equals-sieve-prime edge case.
    plan = build_plan(m=10, bound=20_000)
    flags = sieve_segment(first_k=13, length=1, plan=plan)
    assert flags[0] == 1  # 13 * 2**10 + 1 == 13313, which is prime.

    # Compare sieve decisions with direct divisibility on a large-number segment.
    plan = build_plan(m=50, bound=50_000)
    first_k = 1_000_001
    length = 96
    flags = sieve_segment(first_k, length, plan)
    first_n = first_k * (1 << plan.m) + 1
    for index, survives in enumerate(flags):
        n = first_n + index * plan.step_n
        expected = not any(n % p == 0 and n != p for p in plan.primes)
        assert bool(survives) == expected

    # The deep sieve must return the same first certified prime as no sieve.
    m = 50
    deep = build_plan(m=m, bound=50_000)
    start_k = 1_100_001
    k_high = (1 << m) - 1
    k = start_k
    while True:
        n = k * (1 << m) + 1
        certified, _, _, _ = proth_certificate(n)
        if certified:
            direct_prime = n
            break
        k += 2
    row = search_first_prime(start_k, k_high, deep, segment_size=128)
    assert row["prime"] == direct_prime

    print("SELF_TEST_OK")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Standalone PRE segmented sieve for matched Proth-prime search"
    )
    parser.add_argument("--digits", nargs="+", type=int, default=[100])
    parser.add_argument("--rounds", nargs="+", type=int, default=[200])
    parser.add_argument("--bounds", nargs="+", type=int, default=list(DEFAULT_BOUNDS))
    parser.add_argument("--segment-size", type=int, default=DEFAULT_SEGMENT_SIZE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--output", type=Path, default=Path("pre_proth_results.json"))
    parser.add_argument("--skip-validation", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def normalize_config(args: argparse.Namespace) -> tuple[list[int], list[int], list[int]]:
    digits = list(args.digits)
    rounds = list(args.rounds)
    bounds = sorted(set(args.bounds))

    if len(rounds) == 1:
        rounds *= len(digits)
    if len(rounds) != len(digits):
        raise ValueError("rounds must contain one value or one value per digit count")
    if any(d < 2 for d in digits):
        raise ValueError("every digit count must be at least 2")
    if any(r < 1 for r in rounds):
        raise ValueError("every round count must be positive")
    if len(bounds) < 2 or any(b < 3 for b in bounds):
        raise ValueError("provide at least two sieve bounds of 3 or greater")
    if args.segment_size < 1:
        raise ValueError("segment size must be positive")
    return digits, rounds, bounds


def main() -> None:
    args = parse_args()
    if args.self_test:
        run_self_test()
        return

    digits, rounds, bounds = normalize_config(args)
    rng = random.Random(args.seed)
    started = time.perf_counter()
    results = []

    for digit_count, round_count in zip(digits, rounds):
        result = matched_benchmark(
            digits=digit_count,
            rounds=round_count,
            bounds=bounds,
            segment_size=args.segment_size,
            rng=rng,
            validate=not args.skip_validation,
        )
        results.append(result)
        payload = {
            "configuration": {
                "seed": args.seed,
                "bounds": bounds,
                "segment_size": args.segment_size,
                "digits": digits,
                "rounds": rounds,
                "alternating_execution_order": True,
                "precomputed_sieve_plans": True,
                "hidden_miller_calls": 0,
            },
            "results": results,
            "elapsed_seconds": time.perf_counter() - started,
        }
        args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print("RESULT", json.dumps(result))

    print(f"COMPLETE output={args.output} elapsed={time.perf_counter() - started:.3f}s")


if __name__ == "__main__":
    main()
