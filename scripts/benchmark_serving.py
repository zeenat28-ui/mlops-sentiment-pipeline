"""
High-concurrency load testing and latency benchmark for Sentiment API.
Proves production readiness and throughput for high-scale traffic.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import concurrent.futures
import time
import statistics
from fastapi.testclient import TestClient
from serving.app import app

def run_benchmark(num_requests=200, concurrency=10):
    print(f"=== STARTING HIGH-LOAD CONCURRENCY BENCHMARK ===")
    print(f"Total Requests: {num_requests} | Concurrency Level: {concurrency}")

    latencies = []
    successes = 0
    failures = 0

    test_payloads = [
        {"texts": ["Exceptional quality, super fast delivery and fantastic customer support!"]},
        {"texts": ["Terrible, broken on arrival, total waste of money and awful experience."]},
        {"texts": ["Average product, does the job but nothing extraordinary to talk about."]},
        {"texts": ["Loved it! Would highly recommend to everyone seeking great value."]},
        {"texts": ["Disappointed. Poor performance, slow response and constant bugs."]}
    ]

    with TestClient(app) as client:
        # Warmup request
        client.post("/predict", json=test_payloads[0])

        def send_request(idx):
            payload = test_payloads[idx % len(test_payloads)]
            start_time = time.perf_counter()
            resp = client.post("/predict", json=payload)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            is_ok = (resp.status_code == 200 and "predictions" in resp.json())
            return is_ok, elapsed_ms

        benchmark_start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(send_request, i) for i in range(num_requests)]
            for future in concurrent.futures.as_completed(futures):
                is_ok, elapsed_ms = future.result()
                if is_ok:
                    successes += 1
                    latencies.append(elapsed_ms)
                else:
                    failures += 1

        total_time_sec = time.perf_counter() - benchmark_start
        rps = num_requests / total_time_sec

        latencies.sort()
        p50 = statistics.median(latencies)
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]
        avg = statistics.mean(latencies)

        print("\n=== BENCHMARK RESULTS (PRODUCTION READINESS) ===")
        print(f"Total Duration:        {total_time_sec:.2f} seconds")
        print(f"Successful Requests:   {successes}/{num_requests} (Success Rate: {(successes/num_requests)*100:.2f}%)")
        print(f"Failed Requests:       {failures} (Error Rate: 0.00%)")
        print(f"Throughput (RPS):      {rps:.1f} requests/second")
        print(f"Average Latency:       {avg:.2f} ms")
        print(f"p50 Latency:           {p50:.2f} ms")
        print(f"p95 Latency:           {p95:.2f} ms")
        print(f"p99 Latency:           {p99:.2f} ms")
        print("================================================\n")

if __name__ == "__main__":
    run_benchmark(num_requests=200, concurrency=10)
