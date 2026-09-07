# Observability

`metrics.py` exposes Prometheus instrumentation for the workflow and HTTP API. The FastAPI application mounts the exporter at `/metrics`.

## Metrics

- `daedalus_node_duration_seconds`: execution time for each LangGraph node.
- `daedalus_healing_cycles_total`: number of attempted self-healing cycles.
- `daedalus_test_runs_total`: passed and failed sandbox test runs.
- `daedalus_llm_token_usage_total`: provider-reported prompt, completion, and total tokens.
- `daedalus_http_requests_total`: request count by method, path, and status.
- `daedalus_http_request_duration_seconds`: HTTP latency by method and path.

Start the local monitoring stack with:

```bash
docker compose -f docker-compose.monitoring.yml up -d
```

Prometheus scrapes the API according to `infra/prometheus.yml`; Grafana provisions the dashboard shipped in `infra/grafana/dashboards/`.