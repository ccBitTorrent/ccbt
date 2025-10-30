# Monitoring & Observability

## Components
- MetricsCollector: system/performance metrics collection
- AlertManager: rule-based alerts with active alerts tracking
- Terminal Dashboard (Textual): live view (via `ccbt dashboard`)

## Alerts
Rules consist of name, metric_name, condition (e.g. "value > 80"), and severity.

CLI examples:
```bash
ccbt alerts --add --name cpu_high --metric system.cpu --condition "value > 80" --severity warning
ccbt alerts --list
ccbt alerts --test --name cpu_high --value 95
ccbt alerts --list-active
ccbt alerts --clear-active
```

## Metrics
Export metrics in JSON or Prometheus formats:
```bash
ccbt metrics --format json --include-system --include-performance
ccbt metrics --format prometheus > metrics.txt
```

## Dashboard
Start the terminal dashboard:
```bash
ccbt dashboard --refresh 1.0
```

## Test Artifacts and Coverage (CI)

During pre-push and CI runs, pytest writes artifacts for analysis:

- JUnit XML: `tests/.reports/junit.xml`
- Pytest Log: `tests/.reports/pytest.log`
- Coverage XML: `coverage.xml` (consumed by Codecov)

Selective pre-commit runs remain fast and log to stderr only. Coverage thresholds are enforced via `CCBT_COV_FAIL_UNDER` (default 80) on pre-push.