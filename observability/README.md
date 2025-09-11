# EDBotv8 Observability Stack

Comprehensive monitoring, alerting, and dashboards for the medical AI system with focus on clinical safety and performance.

## Overview

This observability stack provides:

- **Medical Safety Monitoring**: Critical alerts for medication safety, clinical confidence, and PHI protection
- **Performance Monitoring**: Query response times, LLM backend performance, and system health
- **Clinical Quality Metrics**: Specialty-specific confidence scoring, protocol adherence, and citation quality
- **Infrastructure Monitoring**: Database, cache, search backend, and system resource monitoring
- **Alerting & Escalation**: Automated alert routing with medical emergency escalation

## Components

### Prometheus (Port 9090)
- Metrics collection and storage
- Medical AI specific recording rules
- Alert rule evaluation
- 30-day retention for historical analysis

### Grafana (Port 3000) 
- Medical AI Overview Dashboard
- System Performance Dashboard  
- Medical Safety & Quality Dashboard
- Alert visualization and annotations

### AlertManager (Port 9093)
- Medical emergency alert routing
- Escalation to clinical teams
- Integration with Slack/PagerDuty/Email

### Exporters
- Node Exporter (9100): System metrics
- Postgres Exporter (9187): Database metrics
- Redis Exporter (9121): Cache metrics

## Quick Start

### 1. Environment Configuration

```bash
# Copy and configure environment variables
cp observability/.env.monitoring.example observability/.env.monitoring

# Edit configuration
vim observability/.env.monitoring
```

Required variables:
```bash
# Grafana
GRAFANA_USER=admin
GRAFANA_PASSWORD=secure_password
GRAFANA_DOMAIN=grafana.edbot.local

# SMTP for alerts
SMTP_HOST=smtp.gmail.com:587
SMTP_USER=alerts@edbot.com
SMTP_PASSWORD=app_password
SMTP_FROM=edbot-alerts@edbot.com

# Alert recipients
MEDICAL_EMERGENCY_EMAIL=medical-safety@hospital.com
INFRASTRUCTURE_EMAIL=infra@edbot.com
SECURITY_EMAIL=security@edbot.com
OPERATIONS_EMAIL=ops@edbot.com
```

### 2. Start Monitoring Stack

```bash
# Start observability services
docker-compose -f observability/docker-compose.monitoring.yml up -d

# Verify all services are running
docker-compose -f observability/docker-compose.monitoring.yml ps
```

### 3. Access Dashboards

- **Grafana**: http://localhost:3000 (admin/password)
- **Prometheus**: http://localhost:9090
- **AlertManager**: http://localhost:9093

### 4. Import Dashboards

Dashboards are automatically provisioned from `observability/grafana/dashboards/`:

1. **Medical AI Overview** - High-level medical system monitoring
2. **System Performance** - Technical performance metrics  
3. **Medical Safety & Quality** - Clinical safety and quality metrics

## Medical Safety Alerts

### Critical Alerts (Immediate Response)
- **High Medical Safety Alerts**: >5 safety alerts in 5 minutes
- **Critical Medication Safety**: Any medication safety warning
- **Production Safety Flag Disabled**: Critical safety features disabled

### Warning Alerts (Review Required)
- **Low Clinical Confidence**: Confidence <70% for critical specialties
- **Time-Sensitive Protocol Slow**: STEMI/stroke/sepsis >2s response time
- **High PHI Scrubbing**: >100 PHI events in 10 minutes

### Alert Escalation

```
Medical Emergency → medical-safety@hospital.com (immediate)
System Critical → infra@edbot.com + PagerDuty
Security Issues → security@edbot.com
Performance → ops@edbot.com  
Clinical Quality → clinical@edbot.com
```

## Key Metrics

### Medical Safety Metrics
```
edbot_safety_alerts_total - Medical safety alerts by type/severity
edbot_dosage_safety_checks_total - Medication safety validations  
edbot_clinical_confidence - Clinical response confidence by specialty
edbot_phi_scrubbing_total - PHI scrubbing events by component
```

### Performance Metrics
```
edbot_query_duration_seconds - Query response time histograms
edbot_llm_duration_seconds - LLM backend response times
edbot_system_health - Overall system health score (0-1)
edbot_component_health - Individual component status
```

### Clinical Metrics
```  
edbot_medical_queries_by_specialty - Queries by medical specialty
edbot_time_sensitive_response_seconds - Critical protocol response times
edbot_medication_dosage_queries - Medication queries by drug/route
edbot_protocol_adherence_score - Protocol adherence scoring
```

## Configuration

### Prometheus Configuration

Edit `prometheus/prometheus.yml`:

```yaml
# Adjust scrape intervals for different services
scrape_configs:
  - job_name: 'edbot-api'
    scrape_interval: 10s  # Frequent for medical metrics
  - job_name: 'node-exporter'  
    scrape_interval: 30s  # Less frequent for system metrics
```

### Alert Rules

Medical alerts in `prometheus/alerts.yml`:

```yaml
# Add custom medical alerts
- alert: CustomMedicalAlert
  expr: your_metric > threshold  
  for: 1m
  labels:
    severity: critical
    component: medical_safety
  annotations:
    summary: "Custom medical safety condition"
    runbook_url: "https://docs.edbot.com/runbooks/custom"
```

### Grafana Dashboards

Custom panels for medical metrics:

```json
{
  "targets": [
    {
      "expr": "rate(edbot_clinical_confidence{clinical_area=\"cardiology\"}[5m])",
      "legendFormat": "Cardiology Confidence"
    }
  ]
}
```

## Production Deployment

### Security Hardening

1. **Enable TLS**:
```bash
# Generate certificates
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout grafana.key -out grafana.crt

# Update docker-compose with TLS mounts
```

2. **Authentication**:
```yaml
# grafana.ini
[auth.ldap]
enabled = true
config_file = /etc/grafana/ldap.toml
```

3. **Network Security**:
```yaml
# Restrict network access
networks:
  monitoring:
    internal: true  # No external access
```

### High Availability

1. **Prometheus Clustering**:
```yaml
# Add Prometheus replicas
prometheus-1:
  command: ['--web.external-url=http://prometheus-1:9090']
prometheus-2:  
  command: ['--web.external-url=http://prometheus-2:9090']
```

2. **Grafana Database**:
```yaml
# Use external PostgreSQL for Grafana
environment:
  - GF_DATABASE_TYPE=postgres
  - GF_DATABASE_HOST=grafana-db:5432
```

### Data Retention

```yaml
# Prometheus retention policies
command:
  - '--storage.tsdb.retention.time=90d'  # Production: 90 days
  - '--storage.tsdb.retention.size=50GB' # Size limit
```

## Troubleshooting

### Common Issues

1. **Metrics Not Appearing**:
```bash
# Check metric endpoint
curl http://localhost:8001/metrics

# Verify Prometheus targets  
# Go to http://localhost:9090/targets
```

2. **Alerts Not Firing**:
```bash
# Check alert rules
curl http://localhost:9090/api/v1/rules

# Check AlertManager config
curl http://localhost:9093/api/v1/status
```

3. **Dashboard Panels Empty**:
```bash
# Verify data source connection in Grafana
# Check Prometheus query syntax
# Confirm metric names and labels
```

### Log Locations

```bash
# Container logs
docker logs edbot_prometheus
docker logs edbot_grafana
docker logs edbot_alertmanager

# Grafana logs
docker exec edbot_grafana cat /var/log/grafana/grafana.log
```

## Medical Compliance

### HIPAA Considerations

1. **Data Minimization**: Metrics exclude PHI by design
2. **Access Controls**: Authentication required for all dashboards  
3. **Audit Logging**: All access to dashboards is logged
4. **Data Retention**: Configurable retention periods
5. **Encryption**: TLS for all communications

### Clinical Safety

1. **Alert Escalation**: Medical emergencies route to clinical staff
2. **Confidence Monitoring**: Low-confidence responses flagged
3. **Medication Safety**: High-risk drug monitoring  
4. **Protocol Compliance**: Time-sensitive protocol tracking
5. **Quality Assurance**: Citation quality and accuracy metrics

## Support

For issues with the observability stack:

1. Check this README and troubleshooting section
2. Review container logs for errors  
3. Verify metric collection with `/metrics` endpoint
4. Test alert rules in Prometheus UI
5. Contact the infrastructure team for escalation

For medical safety alerts:
1. Follow emergency escalation procedures
2. Review runbook links in alert messages
3. Contact medical safety team immediately for critical alerts