"""
Locust workload generator for muBench benchmarking.

Supports two benchmark patterns:
1. Stochastic benchmarks: GET requests to ingress service (s0, s1, etc.)
   - Triggers random service calls per workmodel.json probabilities
2. Trace-driven benchmarks: POST requests with JSON trace body
   - Defines exact service call sequences

Gateway access: http://localhost:9090 (via SSH tunnel)
"""

from locust import HttpUser, task, between, events
import json
import random

# Track request count for logging
request_count = {"value": 0}


class StochasticBenchmarkUser(HttpUser):
    """
    User class for stochastic-driven benchmarks.
    Sends GET requests to ingress service (typically s0) which triggers
    random service calls according to workmodel.json probabilities.
    """
    
    # Wait between 1 and 3 seconds between requests
    wait_time = between(1, 3)
    
    def on_start(self):
        """Called when a simulated user starts."""
        # Default ingress service is s0
        self.ingress_service = "s0"
    
    @task(1)
    def call_ingress_service(self):
        """
        Send GET request to ingress service.
        This triggers stochastic service calls per workmodel.json.
        """
        with self.client.get(
            f"/{self.ingress_service}",
            name=f"GET /{self.ingress_service}",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
                # Log first few successful requests for verification
                request_count["value"] += 1
                if request_count["value"] <= 5:
                    print(f"✅ Request {request_count['value']}: "
                          f"GET /{self.ingress_service} -> {response.status_code} "
                          f"({response.elapsed.total_seconds()*1000:.0f}ms)")
            else:
                response.failure(f"Status code: {response.status_code}")
                print(f"❌ Request failed: GET /{self.ingress_service} -> {response.status_code}")


class TraceDrivenBenchmarkUser(HttpUser):
    """
    User class for trace-driven benchmarks.
    Sends POST requests with JSON trace body defining exact service call sequences.
    """
    
    # Wait between 1 and 3 seconds between requests
    wait_time = between(1, 3)
    
    def on_start(self):
        """Called when a simulated user starts."""
        # Default ingress service is s0
        self.ingress_service = "s0"
        # Example trace structure (can be loaded from file)
        self.example_trace = {
            "s0__47072": [{
                "s24__71648": [{}],
                "s28__64944": [{
                    "s6__5728": [{}],
                    "s20__61959": [{}]
                }]
            }]
        }
    
    @task(1)
    def send_trace_request(self):
        """
        Send POST request with trace JSON body.
        This triggers exact service call sequence defined in trace.
        """
        with self.client.post(
            f"/{self.ingress_service}",
            json=self.example_trace,
            name=f"POST /{self.ingress_service} (trace-driven)",
            headers={"Content-Type": "application/json"},
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
                # Log first few successful requests for verification
                request_count["value"] += 1
                if request_count["value"] <= 5:
                    print(f"✅ Request {request_count['value']}: "
                          f"POST /{self.ingress_service} -> {response.status_code} "
                          f"({response.elapsed.total_seconds()*1000:.0f}ms)")
            else:
                response.failure(f"Status code: {response.status_code}")
                print(f"❌ Request failed: POST /{self.ingress_service} -> {response.status_code}")


# Default user class for simple stochastic benchmarks
class WebsiteUser(StochasticBenchmarkUser):
    """
    Default user class for stochastic benchmarks.
    Alias for StochasticBenchmarkUser for backward compatibility.
    """
    pass

