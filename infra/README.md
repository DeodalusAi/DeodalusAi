# Monitoring Infrastructure

This directory contains the configuration used by the optional local Prometheus and Grafana stack.

## Files

- `prometheus.yml` tells Prometheus where to scrape the DaedalusOS `/metrics` endpoint.
- `grafana/provisioning/` registers the Prometheus datasource and dashboard provider.
- `grafana/dashboards/daedalus-overview.json` contains the prebuilt workflow overview dashboard.

Start the stack from the repository root:

```bash
docker compose -f docker-compose.monitoring.yml up -d
```

The API should be running on port `8000` before Prometheus can collect application metrics. Prometheus is exposed on `9090`; Grafana is exposed on `3000` with the local demo credentials configured in `docker-compose.monitoring.yml`.