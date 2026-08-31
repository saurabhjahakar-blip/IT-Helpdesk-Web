"""Manual sanity check: fires concurrent requests at a running instance to
see whether SQLite/WAL holds up under realistic per-machine load. Not part
of the pytest suite — run by hand against a live server.

Usage:
    python scripts/loadtest.py --base-url http://127.0.0.1:8000 \\
        --email tech@company.local --password ChangeMe123! --requests 200 --concurrency 20
"""

import argparse
import asyncio
import statistics
import time

import httpx


async def _worker(client: httpx.AsyncClient, path: str, latencies: list[float], errors: list[str]) -> None:
    start = time.perf_counter()
    try:
        response = await client.get(path)
        latencies.append(time.perf_counter() - start)
        if response.status_code != 200:
            errors.append(f"{path} -> HTTP {response.status_code}")
    except Exception as exc:
        detail = str(exc) or "(no message)"
        errors.append(f"{path} -> {type(exc).__name__}: {detail}")


async def run(base_url: str, email: str, password: str, total_requests: int, concurrency: int) -> None:
    # Match the client's own connection pool to the requested concurrency —
    # otherwise httpx's default pool cap (100 connections) becomes the
    # bottleneck being measured instead of the server's.
    limits = httpx.Limits(max_connections=concurrency + 10, max_keepalive_connections=concurrency + 10)
    async with httpx.AsyncClient(base_url=base_url, timeout=30, limits=limits) as client:
        login = await client.post("/login", data={"email": email, "password": password, "next": "/"})
        if login.status_code not in (200, 303):
            print(f"Login failed: HTTP {login.status_code}")
            return

        latencies: list[float] = []
        errors: list[str] = []
        semaphore = asyncio.Semaphore(concurrency)

        async def bounded(path: str) -> None:
            async with semaphore:
                await _worker(client, path, latencies, errors)

        paths = ["/api/system/info", "/api/reports/", "/api/assets/"]
        tasks = [bounded(paths[i % len(paths)]) for i in range(total_requests)]
        started = time.perf_counter()
        await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - started

        print(f"{total_requests} requests, concurrency={concurrency}, elapsed={elapsed:.2f}s")
        if latencies:
            print(
                f"latency: min={min(latencies)*1000:.0f}ms "
                f"p50={statistics.median(latencies)*1000:.0f}ms "
                f"max={max(latencies)*1000:.0f}ms"
            )
        print(f"errors: {len(errors)}/{total_requests}")
        for err in errors[:10]:
            print(f"  - {err}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=20)
    args = parser.parse_args()

    asyncio.run(run(args.base_url, args.email, args.password, args.requests, args.concurrency))


if __name__ == "__main__":
    main()
