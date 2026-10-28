"""Measure trainer handler latency with caching bypassed versus warm Redis.

Run against a populated database: python3 -m scripts.benchmark_cache
Only uniquely prefixed benchmark cache keys are written and removed.
"""

import argparse
from contextlib import ExitStack
import json
import math
from statistics import median
from time import perf_counter
from unittest.mock import patch
from uuid import uuid4

import redis
from sqlalchemy import event, func

from api import main as api
from cache import redis as cache
from db.models import TrainerEncounter, TrainerPokemonMove
from db.session import SessionLocal, engine


def summarize(samples):
    ordered = sorted(samples)
    return {
        "median_ms": round(median(ordered), 4),
        "p95_ms": round(ordered[math.ceil(len(ordered) * 0.95) - 1], 4),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--names", nargs="+", default=["Brock", "Misty", "Giovanni"])
    parser.add_argument("--samples", type=int, default=200)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--redis-socket", help="Optional Unix socket for isolated Redis")
    args = parser.parse_args()
    if args.samples < 1 or args.warmup < 0:
        parser.error("samples must be positive and warmup nonnegative")

    client = (
        redis.Redis(unix_socket_path=args.redis_socket, socket_timeout=2)
        if args.redis_socket
        else redis.Redis(
            host=cache.client.connection_pool.connection_kwargs["host"],
            port=cache.client.connection_pool.connection_kwargs["port"],
            db=cache.client.connection_pool.connection_kwargs["db"],
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    )
    prefix = f"benchmark:{uuid4().hex}:"
    keys = [prefix + "trainer:search:" + api.normalize_query(n) for n in args.names]
    statement_count = 0

    def count_statement(conn, cursor, statement, parameters, context, executemany):
        nonlocal statement_count
        statement_count += 1

    def lookup(name, cached):
        nonlocal statement_count
        with ExitStack() as stack:
            if cached:
                stack.enter_context(patch.object(api, "get_cache", lambda k: cache.get_cache(prefix + k)))
                stack.enter_context(patch.object(api, "set_cache", lambda k, v: cache.set_cache(prefix + k, v)))
            else:
                stack.enter_context(patch.object(api, "get_cache", lambda k: None))
                stack.enter_context(patch.object(api, "set_cache", lambda *a: None))
            statement_count = 0
            start = perf_counter()
            with SessionLocal() as db:
                result = api.search_trainers(name, db=db)
                encoded = json.dumps(sorted(result, key=lambda row: row["id"]), sort_keys=True)
            elapsed_ms = (perf_counter() - start) * 1000
        return elapsed_ms, statement_count, encoded

    listening = False
    try:
        client.ping()
        with SessionLocal() as db:
            dataset = {
                "encounters": db.query(func.count(TrainerEncounter.id)).scalar(),
                "team_member_move_entries": db.query(func.count(TrainerPokemonMove.id)).scalar(),
            }
        event.listen(engine, "before_cursor_execute", count_statement)
        listening = True
        results = []
        with patch.object(cache, "client", client):
            for name in args.names:
                _, _, expected = lookup(name, False)
                lookup(name, True)
                key = prefix + "trainer:search:" + api.normalize_query(name)
                if not client.exists(key):
                    raise AssertionError("Redis cache population failed")
                samples = {False: [], True: []}
                for i in range(args.warmup + args.samples):
                    # Alternate order to reduce systematic ordering bias.
                    for cached in ([False, True] if i % 2 == 0 else [True, False]):
                        elapsed, queries, payload = lookup(name, cached)
                        if payload != expected:
                            raise AssertionError("Cached and uncached responses differ")
                        if queries != (0 if cached else 1):
                            raise AssertionError(f"Unexpected query count: {queries}")
                        if i >= args.warmup:
                            samples[cached].append(elapsed)
                off = summarize(samples[False])
                on = summarize(samples[True])
                results.append({
                    "name": name,
                    "matching_trainers": len(json.loads(expected)),
                    "cache_bypassed": off,
                    "warm_cache": on,
                    "median_reduction_percent": round(
                        (1 - median(samples[True]) / median(samples[False])) * 100, 2
                    ),
                    "sql_queries_bypassed_vs_cached": [1, 0],
                })
        print(json.dumps({
            "database_dialect": engine.dialect.name,
            "redis_version": client.info("server")["redis_version"],
            "dataset": dataset,
            "samples_per_mode_per_name": args.samples,
            "warmup_pairs": args.warmup,
            "scope": "Handler + JSON encoding + session cleanup; excludes HTTP and Discord",
            "results": results,
        }, indent=2))
    finally:
        if listening:
            event.remove(engine, "before_cursor_execute", count_statement)
        try:
            client.delete(*keys)
        finally:
            client.close()
            engine.dispose()


if __name__ == "__main__":
    main()
