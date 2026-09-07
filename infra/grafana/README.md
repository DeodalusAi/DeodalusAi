# Grafana Configuration

This directory contains the dashboard and provisioning files used by the local monitoring stack.

- `provisioning/datasources/` registers Prometheus as Grafana's data source.
- `provisioning/dashboards/` tells Grafana where to load dashboard JSON files.
- `dashboards/daedalus-overview.json` is the prebuilt DaedalusOS workflow overview.

The Docker Compose file mounts these directories read-only into Grafana. Start the complete stack from the repository root with:

```bash
docker compose -f docker-compose.monitoring.yml up -d
```

Open Grafana at `http://127.0.0.1:3000`; the local compose configuration uses `admin` / `admin` as the initial credentials.