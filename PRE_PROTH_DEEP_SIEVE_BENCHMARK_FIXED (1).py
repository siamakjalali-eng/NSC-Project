#!/usr/bin/env python3
"""Paired and auditable PRE Proth deep-sieve benchmark.

Discovery uses only trial-division sieves, Jacobi symbols, and the Proth test.
Miller-Rabin is called exactly once after each discovered prime and is reported
outside discovery cost.  Every round is saved so statistical claims can be
checked later.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


GLOBAL = {
    "proth_pow_calls": 0,
    "jacobi_calls": 0,
    "miller_validation_events": 0,
    "miller_bases_tested": 0,
}


def prime_list(limit: int) -> list[int]:
    sieve = bytearray(b"\x01") * (limit + 1)
    sieve[:2] = b"\x00\x00"
    for p in range(2, math.isqrt(limit) + 1):
        if sieve[p]:
            sieve[p * p : limit + 1 : p] = b"\x00" * (((limit - p * p) // p) + 1)
    return [p for p in range(3, limit + 1, 2) if sieve[p]]


def jacobi(a: int, n: int) -> int:
    GLOBAL["jacobi_calls"] += 1
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


@dataclass(frozen=True)
class SievePlan:
    bound: int
    exponent_m: int
    primes: tuple[int, ...]
    forbidden_k: tuple[int, ...]
    setup_ms: float


def build_plan(bound: int, exponent_m: int) -> SievePlan:
    started = time.perf_counter_ns()
    ps = prime_list(bound)
    forbidden = [(-pow(pow(2, exponent_m, p), -1, p)) % p for p in ps]
    elapsed = (time.perf_counter_ns() - started) / 1e6
    return SievePlan(bound, exponent_m, tuple(ps), tuple(forbidden), elapsed)


def exact_digit_k_start(digits: int, m: int, rng: random.Random) -> int:
    low_n = 10 ** (digits - 1)
    high_n = 10**digits - 1
    two_m = 1 << m
    low_k = max(1, (low_n - 1 + two_m - 1) // two_m)
    high_k = min(two_m - 1, (high_n - 1) // two_m)
    if low_k > high_k:
        raise ValueError("Chosen exponent cannot produce the requested digits")
    low_k |= 1
    high_k -= (high_k + 1) % 2
    count = ((high_k - low_k) // 2) + 1
    return low_k + 2 * rng.randrange(count)


def segment_survivors(k0: int, size: int, plan: SievePlan) -> list[int]:
    alive = bytearray(b"\x01") * size
    for p, forbidden in zip(plan.primes, plan.forbidden_k):
        inv2 = (p + 1) // 2
        first = ((forbidden - (k0 % p)) * inv2) % p
        if first < size:
            alive[first:size:p] = b"\x00" * (((size - 1 - first) // p) + 1)
    return [k0 + 2 * i for i, flag in enumerate(alive) if flag]


def proth_certificate(n: int, k: int, m: int, bases: Iterable[int]) -> tuple[bool, int, int | None, int]:
    if n != k * (1 << m) + 1 or k % 2 == 0 or not (0 < k < (1 << m)):
        raise ValueError("Invalid Proth form")
    trials = 0
    for a in bases:
        if a >= n:
            break
        trials += 1
        j = jacobi(a, n)
        if j == 0:
            return False, trials, None, 0
        if j == -1:
            GLOBAL["proth_pow_calls"] += 1
            return pow(a, (n - 1) // 2, n) == n - 1, trials, a, 1
    return False, trials, None, 0


def deterministic_bases() -> tuple[int, ...]:
    return (3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59,
            61, 67, 71, 73, 79, 83, 89, 97, 101, 103, 107, 109, 113, 127, 131)


@dataclass
class Discovery:
    prime: int
    found_k: int
    candidate_tests: int
    expensive_pow_calls: int
    jacobi_trials: int
    segments: int
    search_ms: float
    certificate_base: int


def discover(start_k: int, m: int, plan: SievePlan, segment_size: int) -> Discovery:
    start_ns = time.perf_counter_ns()
    k0 = start_k
    tests = pow_calls = jacobi_trials = segments = 0
    bases = deterministic_bases()
    while True:
        if k0 >= (1 << m):
            raise RuntimeError("Search exhausted the Proth condition k < 2^m")
        size = min(segment_size, (((1 << m) - k0) + 1) // 2)
        segments += 1
        for k in segment_survivors(k0, size, plan):
            n = k * (1 << m) + 1
            tests += 1
            passed, trials, cert_base, used_pow = proth_certificate(n, k, m, bases)
            pow_calls += used_pow
            jacobi_trials += trials
            if passed:
                return Discovery(
                    n, k, tests, pow_calls, jacobi_trials, segments,
                    (time.perf_counter_ns() - start_ns) / 1e6,
                    int(cert_base),
                )
        k0 += 2 * size


def miller_rabin_validation(n: int, bases: tuple[int, ...]) -> bool:
    GLOBAL["miller_validation_events"] += 1
    if n < 2 or n % 2 == 0:
        return n == 2
    d, s = n - 1, 0
    while d % 2 == 0:
        d //= 2
        s += 1
    for a in bases:
        if a >= n:
            continue
        GLOBAL["miller_bases_tested"] += 1
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def summary(values: list[float]) -> dict:
    if not values:
        return {}
    mean = statistics.fmean(values)
    sd = statistics.stdev(values) if len(values) > 1 else 0.0
    ci = 1.96 * sd / math.sqrt(len(values)) if len(values) > 1 else 0.0
    return {
        "mean": mean,
        "median": statistics.median(values),
        "minimum": min(values),
        "maximum": max(values),
        "standard_deviation": sd,
        "mean_ci95_low": mean - ci,
        "mean_ci95_high": mean + ci,
    }


def run(args: argparse.Namespace) -> dict:
    rng = random.Random(args.seed)
    configs = [(100, args.rounds100), (500, args.rounds500), (1000, args.rounds1000)]
    full_report = {
        "configuration": vars(args),
        "accounting_rule": {
            "discovery_miller_calls": 0,
            "validation_is_outside_discovery": True,
            "one_validation_event_per_output": True,
            "paired_same_start_for_both_engines": True,
        },
        "results": [],
    }
    total_started = time.perf_counter_ns()

    for digits, rounds in configs:
        if rounds <= 0:
            continue
        m = math.ceil(digits * math.log2(10) / 2)
        base_plan = build_plan(args.base_bound, m)
        deep_plan = build_plan(args.deep_bound, m)
        rows = []

        for round_id in range(rounds):
            start_k = exact_digit_k_start(digits, m, rng)
            order = (("base", base_plan), ("deep", deep_plan))
            if round_id % 2:
                order = tuple(reversed(order))
            found = {}
            before_global = dict(GLOBAL)
            for name, plan in order:
                found[name] = discover(start_k, m, plan, args.segment_size)

            same_output = found["base"].prime == found["deep"].prime
            validation_started = time.perf_counter_ns()
            valid = miller_rabin_validation(found["deep"].prime, deterministic_bases()[: args.miller_bases])
            validation_ms = (time.perf_counter_ns() - validation_started) / 1e6
            if not same_output or not valid:
                raise AssertionError(f"Round {round_id} mismatch or failed validation")

            rows.append({
                "round": round_id + 1,
                "digits": digits,
                "start_k": str(start_k),
                "found_k": str(found["deep"].found_k),
                "prime": str(found["deep"].prime),
                "output_digits": len(str(found["deep"].prime)),
                "same_output": same_output,
                "base": asdict(found["base"]),
                "deep": asdict(found["deep"]),
                "paired_saved_pow_calls": found["base"].expensive_pow_calls - found["deep"].expensive_pow_calls,
                "paired_time_change_ms": found["deep"].search_ms - found["base"].search_ms,
                "validation": {
                    "miller_event_count": 1,
                    "miller_bases_requested": args.miller_bases,
                    "passed": valid,
                    "time_ms": validation_ms,
                    "included_in_discovery_cost": False,
                },
                "global_counter_delta": {key: GLOBAL[key] - before_global[key] for key in GLOBAL},
            })

        base_candidates = [r["base"]["candidate_tests"] for r in rows]
        deep_candidates = [r["deep"]["candidate_tests"] for r in rows]
        base_pow = [r["base"]["expensive_pow_calls"] for r in rows]
        deep_pow = [r["deep"]["expensive_pow_calls"] for r in rows]
        base_ms = [r["base"]["search_ms"] for r in rows]
        deep_ms = [r["deep"]["search_ms"] for r in rows]
        saved = [r["paired_saved_pow_calls"] for r in rows]
        time_delta = [r["paired_time_change_ms"] for r in rows]
        base_mean, deep_mean = statistics.fmean(base_pow), statistics.fmean(deep_pow)
        base_time_mean, deep_time_mean = statistics.fmean(base_ms), statistics.fmean(deep_ms)

        full_report["results"].append({
            "digits": digits,
            "rounds": rounds,
            "proth_exponent_m": m,
            "plans": {
                "base": {"bound": base_plan.bound, "sieve_primes": len(base_plan.primes), "setup_ms": base_plan.setup_ms},
                "deep": {"bound": deep_plan.bound, "sieve_primes": len(deep_plan.primes), "setup_ms": deep_plan.setup_ms},
            },
            "aggregate": {
                "base_candidate_tests": summary(base_candidates),
                "deep_candidate_tests": summary(deep_candidates),
                "base_expensive_pow_calls": summary(base_pow),
                "deep_expensive_pow_calls": summary(deep_pow),
                "paired_pow_saved": summary(saved),
                "pow_reduction_percent": 100 * (base_mean - deep_mean) / base_mean,
                "base_search_ms": summary(base_ms),
                "deep_search_ms": summary(deep_ms),
                "paired_time_change_ms": summary(time_delta),
                "time_change_percent": 100 * (deep_time_mean - base_time_mean) / base_time_mean,
                "output_mismatches": sum(not r["same_output"] for r in rows),
                "validation_failures": sum(not r["validation"]["passed"] for r in rows),
                "all_outputs_exact_digits": all(r["output_digits"] == digits for r in rows),
            },
            "raw_rounds": rows,
        })

    full_report["global_counters"] = dict(GLOBAL)
    full_report["elapsed_seconds"] = (time.perf_counter_ns() - total_started) / 1e9
    return full_report


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=36808343)
    p.add_argument("--base-bound", type=int, default=12841)
    p.add_argument("--deep-bound", type=int, default=368083)
    p.add_argument("--segment-size", type=int, default=256)
    p.add_argument("--rounds100", type=int, default=1000)
    p.add_argument("--rounds500", type=int, default=200)
    p.add_argument("--rounds1000", type=int, default=50)
    p.add_argument("--miller-bases", type=int, default=16, choices=range(1, 33))
    p.add_argument("--output", default="PRE_PROTH_DEEP_SIEVE_BENCHMARK_FIXED.json")
    return p.parse_args()


if __name__ == "__main__":
    options = parse_args()
    report = run(options)
    output = Path(options.output)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(output.resolve()),
        "elapsed_seconds": report["elapsed_seconds"],
        "global_counters": report["global_counters"],
    }, indent=2))
