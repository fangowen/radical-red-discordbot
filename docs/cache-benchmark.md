# Trainer Search Cache Benchmark

Measured on October 28, 2026 using isolated local PostgreSQL and Redis instances
over Unix sockets. These are backend handler measurements, not production EC2
or Discord response times.

## Method

- Loaded the repository snapshot: 186 encounters and 3,731 team-member move
  entries (not distinct move names).
- Called the actual `search_trainers` handler with a fresh session per request.
- Compared Redis bypassed entirely against a prepopulated Redis cache.
- Used 20 warmup pairs followed by 200 samples per mode for each search.
- Alternated execution order and included JSON encoding and session cleanup.
- Verified identical responses and one SQL statement per uncached request versus
  zero per cached request.
- Used unique benchmark cache keys, removed after completion.

## Results

| Search | Uncached Median | Cached Median | Median Reduction | Uncached p95 | Cached p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Brock | 0.2749 ms | 0.1017 ms | 63.01% | 0.3063 ms | 0.1244 ms |
| Misty | 0.2749 ms | 0.1018 ms | 62.96% | 0.2930 ms | 0.1169 ms |
| Giovanni | 0.2748 ms | 0.1034 ms | 62.36% | 0.2890 ms | 0.1169 ms |

## Interpretation

Warm Redis reduced median handler latency by approximately 62-63% in this local
benchmark, saving about 0.17 ms per lookup. The comparison uses warmed database
and connection state, no concurrent workload, and excludes HTTP, Discord,
deployment topology, cold-cache misses, and production cache-hit rates. It does
not establish a 63% improvement in user-visible response time.

## Reproduce

With the configured database populated and Redis reachable, run from the root:

```bash
python3 -m scripts.benchmark_cache
```

For an isolated Redis instance listening on a Unix socket:

```bash
python3 -m scripts.benchmark_cache --redis-socket /path/to/redis.sock
```

The script reads database records without changing them. It creates and deletes
only its own prefixed Redis keys. A connection or cache failure aborts the
measurement rather than being counted as a cache hit.
