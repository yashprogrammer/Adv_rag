"""03_generate_k8s_ops_db.py — Generate synthetic K8s operational SQL seed data.

Uses `faker` to produce realistic-looking K8s operational telemetry and writes
it to seed/migrations/003_seed_k8s_ops.sql.

Tables generated
----------------
  clusters    (50 rows)   — cluster inventory
  nodes       (5 000 rows) — node pool details
  deployments (10 000 rows) — workload manifests
  pods        (50 000 rows) — pod lifecycle snapshots
  incidents   (2 000 rows)  — SRE incident records
  alerts      (100 000 rows) — Alertmanager-style alert log
  oncall_logs (20 000 rows)  — on-call paging records

The script targets a ~20 MB SQL file.  Actual size will vary slightly based
on the random data; a summary is printed at the end.

This script is **idempotent**: if the output file already exists, the script
skips generation unless --force is passed.

Usage:
    uv run python scripts/data_pipeline/03_generate_k8s_ops_db.py
    uv run python scripts/data_pipeline/03_generate_k8s_ops_db.py --force
    uv run python scripts/data_pipeline/03_generate_k8s_ops_db.py --fast   # smaller counts for smoke-test
"""

from __future__ import annotations

import argparse
import io
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
CONFIG_PATH = SCRIPT_DIR / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH) as fh:
        return yaml.safe_load(fh)


def log(msg: str, *, indent: int = 0) -> None:
    prefix = "  " * indent
    print(f"[03_k8s_db] {prefix}{msg}", flush=True)


def human_size(total_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if total_bytes < 1024:
            return f"{total_bytes:.1f} {unit}"
        total_bytes /= 1024  # type: ignore[assignment]
    return f"{total_bytes:.1f} TB"


# ---------------------------------------------------------------------------
# SQL helpers
# ---------------------------------------------------------------------------

def _q(value: str | None) -> str:
    """Single-quote a string for SQL, escaping internal quotes."""
    if value is None:
        return "NULL"
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


def _ts(dt: datetime) -> str:
    return _q(dt.strftime("%Y-%m-%d %H:%M:%S+00"))


# ---------------------------------------------------------------------------
# Data generators
# ---------------------------------------------------------------------------

# Constants / value pools

REGIONS = [
    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
    "eu-west-1", "eu-central-1", "ap-southeast-1", "ap-northeast-1",
    "ca-central-1", "sa-east-1",
]
ENVIRONMENTS = ["production", "staging", "development", "canary", "dr"]
K8S_VERSIONS = ["1.27.14", "1.28.10", "1.29.6", "1.30.2", "1.31.0"]
NODE_TYPES = [
    "m5.xlarge", "m5.2xlarge", "m5.4xlarge",
    "c5.2xlarge", "c5.4xlarge",
    "r5.xlarge", "r5.2xlarge",
    "t3.large", "t3.xlarge",
    "g4dn.xlarge",  # GPU node for ML workloads
]
NODE_CPU = {
    "m5.xlarge": 4, "m5.2xlarge": 8, "m5.4xlarge": 16,
    "c5.2xlarge": 8, "c5.4xlarge": 16,
    "r5.xlarge": 4, "r5.2xlarge": 8,
    "t3.large": 2, "t3.xlarge": 4,
    "g4dn.xlarge": 4,
}
NODE_MEM = {
    "m5.xlarge": 16, "m5.2xlarge": 32, "m5.4xlarge": 64,
    "c5.2xlarge": 16, "c5.4xlarge": 32,
    "r5.xlarge": 32, "r5.2xlarge": 64,
    "t3.large": 8, "t3.xlarge": 16,
    "g4dn.xlarge": 16,
}
NODE_STATUSES = ["Ready", "Ready", "Ready", "Ready", "NotReady", "SchedulingDisabled"]
POD_STATUSES = [
    "Running", "Running", "Running", "Running", "Running",
    "Running", "Running", "Running",  # ~80 % Running
    "Pending", "Pending",             # ~10 % Pending
    "CrashLoopBackOff",               # ~5 %
    "Failed",                         # ~3 %
    "Completed",                      # ~2 %
]
NAMESPACES = [
    "default", "kube-system", "monitoring", "logging", "ingress-nginx",
    "cert-manager", "argocd", "production", "staging", "data-platform",
    "ml-serving", "security", "databases",
]
APP_NAMES = [
    "api-gateway", "user-service", "order-service", "payment-service",
    "inventory-service", "notification-service", "auth-service",
    "search-service", "recommendation-engine", "analytics-collector",
    "kafka-consumer", "elasticsearch", "redis-cache", "postgres-primary",
    "prometheus", "grafana", "alertmanager", "loki", "tempo",
    "argocd-server", "vault-agent", "cert-manager",
    "ingress-controller", "fluentd", "vector",
]
IMAGES = [
    "nginx", "redis", "postgres", "kafka", "zookeeper",
    "prometheus", "grafana", "elasticsearch", "kibana",
    "fluentd", "jaeger", "envoy",
]
INTERNAL_IMAGES = [
    "gcr.io/acme-corp/api-gateway",
    "gcr.io/acme-corp/user-service",
    "gcr.io/acme-corp/order-service",
    "gcr.io/acme-corp/payment-service",
    "ecr.aws/acme/ml-serving",
]
SEVERITIES = ["P1", "P1", "P2", "P2", "P2", "P3", "P3", "P3", "P3", "P4"]
ALERT_NAMES = [
    "HighCPUUsage", "HighMemoryUsage", "PodCrashLooping", "NodeNotReady",
    "DiskPressure", "HighLatency", "ErrorRateHigh", "DeploymentReplicasMismatch",
    "PersistentVolumeFillingUp", "CertificateExpiringSoon",
    "EtcdHighCommitDurations", "APIServerHighRequestRate",
    "KubeSchedulerDown", "KubeControllerManagerDown",
    "NetworkPolicyViolation",
]
RCA_SUMMARIES = [
    "OOMKilled due to memory leak in connection pool; patched with limit increase.",
    "Node taint misconfiguration caused scheduling cascade failure.",
    "Config map update rolled back — env var regression broke health check.",
    "Downstream DB connection pool exhausted during flash sale traffic spike.",
    "Cert rotation script failed silently; manual renewal applied.",
    "Persistent volume mount race condition on node restart.",
    "Horizontal Pod Autoscaler scaling lag during sudden load increase.",
    "Image pull backoff due to ECR token expiry in CI/CD pipeline.",
    "Ingress controller OOM after nginx worker_processes misconfiguration.",
    "etcd compaction missed, leading to disk saturation on control plane.",
    "DNS resolution failure caused by CoreDNS pod eviction.",
    "Fluentd log buffer overflow dropped 12 min of logs during peak traffic.",
]
ENGINEERS = [
    "alice.chen", "bob.kumar", "carol.osei", "dave.lim", "eve.patel",
    "frank.nguyen", "grace.sato", "henry.olawale", "iris.rodrigues", "jake.murphy",
]


def _rand_dt(rng: random.Random, start_days_ago: int = 365) -> datetime:
    """Random UTC datetime within the last *start_days_ago* days."""
    offset = timedelta(
        seconds=rng.randint(0, start_days_ago * 86400)
    )
    return datetime.now(timezone.utc) - offset


def generate_clusters(rng: random.Random, count: int) -> list[dict]:
    log(f"Generating {count} clusters …")
    clusters = []
    for i in range(1, count + 1):
        clusters.append({
            "cluster_id": i,
            "name": f"k8s-{rng.choice(ENVIRONMENTS)}-{rng.choice(REGIONS).replace('-', '')}-{i:03d}",
            "region": rng.choice(REGIONS),
            "environment": rng.choice(ENVIRONMENTS),
            "k8s_version": rng.choice(K8S_VERSIONS),
            "created_at": _rand_dt(rng, start_days_ago=730),
        })
    return clusters


def generate_nodes(rng: random.Random, count: int, cluster_ids: list[int]) -> list[dict]:
    log(f"Generating {count} nodes …")
    nodes = []
    for i in range(1, count + 1):
        ntype = rng.choice(NODE_TYPES)
        nodes.append({
            "node_id": i,
            "cluster_id": rng.choice(cluster_ids),
            "node_type": ntype,
            "cpu_cores": NODE_CPU[ntype],
            "memory_gb": NODE_MEM[ntype],
            "status": rng.choice(NODE_STATUSES),
            "created_at": _rand_dt(rng, start_days_ago=365),
        })
    return nodes


def generate_deployments(rng: random.Random, count: int, cluster_ids: list[int]) -> list[dict]:
    log(f"Generating {count} deployments …")
    deployments = []
    for i in range(1, count + 1):
        app = rng.choice(APP_NAMES)
        image_base = rng.choice(INTERNAL_IMAGES) if rng.random() > 0.4 else rng.choice(IMAGES)
        major = rng.randint(0, 3)
        minor = rng.randint(0, 15)
        patch = rng.randint(0, 30)
        deployments.append({
            "deployment_id": i,
            "name": f"{app}-{i}",
            "namespace": rng.choice(NAMESPACES),
            "replicas": rng.choice([1, 1, 2, 3, 3, 5, 10]),
            "image": image_base,
            "version": f"{major}.{minor}.{patch}",
            "cluster_id": rng.choice(cluster_ids),
            "created_at": _rand_dt(rng, start_days_ago=365),
        })
    return deployments


def generate_pods(
    rng: random.Random, count: int,
    deployment_ids: list[int], node_ids: list[int],
) -> list[dict]:
    log(f"Generating {count} pods (this may take a moment) …")
    pods = []
    for i in range(1, count + 1):
        dep_id = rng.choice(deployment_ids)
        node_id = rng.choice(node_ids)
        status = rng.choice(POD_STATUSES)
        pods.append({
            "pod_id": i,
            "namespace": rng.choice(NAMESPACES),
            "deployment_id": dep_id,
            "status": status,
            "node_id": node_id,
            "created_at": _rand_dt(rng, start_days_ago=90),
        })
        if i % 10000 == 0:
            log(f"  … {i:,}/{count:,} pods", indent=1)
    return pods


def generate_incidents(rng: random.Random, count: int, cluster_ids: list[int]) -> list[dict]:
    log(f"Generating {count} incidents …")
    incidents = []
    for i in range(1, count + 1):
        started = _rand_dt(rng, start_days_ago=365)
        mttr = rng.randint(5, 480)
        resolved = started + timedelta(minutes=mttr)
        severity = rng.choice(SEVERITIES)
        incidents.append({
            "incident_id": i,
            "severity": severity,
            "cluster_id": rng.choice(cluster_ids),
            "started_at": started,
            "resolved_at": resolved,
            "mttr_minutes": mttr,
            "rca_summary": rng.choice(RCA_SUMMARIES),
        })
    return incidents


def generate_alerts(
    rng: random.Random, count: int, pod_ids: list[int],
) -> list[dict]:
    log(f"Generating {count} alerts (this may take a moment) …")
    alerts = []
    for i in range(1, count + 1):
        fired_at = _rand_dt(rng, start_days_ago=180)
        resolved = rng.random() > 0.1  # 90 % resolved
        alerts.append({
            "alert_id": i,
            "fired_at": fired_at,
            "severity": rng.choice(SEVERITIES),
            "source_pod_id": rng.choice(pod_ids),
            "alertname": rng.choice(ALERT_NAMES),
            "resolved": resolved,
        })
        if i % 20000 == 0:
            log(f"  … {i:,}/{count:,} alerts", indent=1)
    return alerts


def generate_oncall_logs(
    rng: random.Random, count: int, incident_ids: list[int],
) -> list[dict]:
    log(f"Generating {count} oncall_logs …")
    logs = []
    for i in range(1, count + 1):
        paged_at = _rand_dt(rng, start_days_ago=365)
        logs.append({
            "log_id": i,
            "engineer": rng.choice(ENGINEERS),
            "paged_at": paged_at,
            "incident_id": rng.choice(incident_ids),
            "response_time_mins": rng.randint(1, 45),
        })
    return logs


# ---------------------------------------------------------------------------
# SQL writer
# ---------------------------------------------------------------------------

DDL = """\
-- =============================================================================
-- 003_seed_k8s_ops.sql
-- Synthetic Kubernetes operational data for Text2SQL demos and advanced RAG eval.
--
-- Generated by scripts/data_pipeline/03_generate_k8s_ops_db.py
-- DO NOT EDIT BY HAND — regenerate with: uv run python scripts/data_pipeline/03_generate_k8s_ops_db.py --force
--
-- Tables: clusters, nodes, deployments, pods, incidents, alerts, oncall_logs
-- =============================================================================

-- Run after 001_create_users.sql and 002_seed_ecommerce.sql

-- ---------------------------------------------------------------------------
-- DROP (idempotent re-run) — cascade handles FK deps
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS oncall_logs  CASCADE;
DROP TABLE IF EXISTS alerts       CASCADE;
DROP TABLE IF EXISTS pods         CASCADE;
DROP TABLE IF EXISTS incidents    CASCADE;
DROP TABLE IF EXISTS deployments  CASCADE;
DROP TABLE IF EXISTS nodes        CASCADE;
DROP TABLE IF EXISTS clusters     CASCADE;

-- ---------------------------------------------------------------------------
-- CREATE
-- ---------------------------------------------------------------------------

CREATE TABLE clusters (
    cluster_id   SERIAL PRIMARY KEY,
    name         VARCHAR(128) UNIQUE NOT NULL,
    region       VARCHAR(64)  NOT NULL,
    environment  VARCHAR(32)  NOT NULL,
    k8s_version  VARCHAR(16)  NOT NULL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE nodes (
    node_id     SERIAL PRIMARY KEY,
    cluster_id  INTEGER REFERENCES clusters(cluster_id),
    node_type   VARCHAR(32)  NOT NULL,
    cpu_cores   SMALLINT     NOT NULL,
    memory_gb   SMALLINT     NOT NULL,
    status      VARCHAR(32)  NOT NULL DEFAULT 'Ready',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE deployments (
    deployment_id  SERIAL PRIMARY KEY,
    name           VARCHAR(128) NOT NULL,
    namespace      VARCHAR(64)  NOT NULL,
    replicas       SMALLINT     NOT NULL DEFAULT 1,
    image          VARCHAR(256) NOT NULL,
    version        VARCHAR(32)  NOT NULL,
    cluster_id     INTEGER REFERENCES clusters(cluster_id),
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE pods (
    pod_id         SERIAL PRIMARY KEY,
    namespace      VARCHAR(64)  NOT NULL,
    deployment_id  INTEGER REFERENCES deployments(deployment_id),
    status         VARCHAR(32)  NOT NULL,
    node_id        INTEGER REFERENCES nodes(node_id),
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE incidents (
    incident_id    SERIAL PRIMARY KEY,
    severity       VARCHAR(4)   NOT NULL,
    cluster_id     INTEGER REFERENCES clusters(cluster_id),
    started_at     TIMESTAMPTZ  NOT NULL,
    resolved_at    TIMESTAMPTZ,
    mttr_minutes   INTEGER,
    rca_summary    TEXT
);

CREATE TABLE alerts (
    alert_id       SERIAL PRIMARY KEY,
    fired_at       TIMESTAMPTZ  NOT NULL,
    severity       VARCHAR(4)   NOT NULL,
    source_pod_id  INTEGER REFERENCES pods(pod_id),
    alertname      VARCHAR(128) NOT NULL,
    resolved       BOOLEAN      NOT NULL DEFAULT FALSE
);

CREATE TABLE oncall_logs (
    log_id              SERIAL PRIMARY KEY,
    engineer            VARCHAR(64)  NOT NULL,
    paged_at            TIMESTAMPTZ  NOT NULL,
    incident_id         INTEGER REFERENCES incidents(incident_id),
    response_time_mins  INTEGER      NOT NULL
);

-- Useful indexes for Text2SQL query performance
CREATE INDEX idx_nodes_cluster        ON nodes(cluster_id);
CREATE INDEX idx_pods_deployment      ON pods(deployment_id);
CREATE INDEX idx_pods_node            ON pods(node_id);
CREATE INDEX idx_pods_status          ON pods(status);
CREATE INDEX idx_incidents_cluster    ON incidents(cluster_id);
CREATE INDEX idx_incidents_severity   ON incidents(severity);
CREATE INDEX idx_alerts_fired_at      ON alerts(fired_at);
CREATE INDEX idx_alerts_severity      ON alerts(severity);
CREATE INDEX idx_oncall_incident      ON oncall_logs(incident_id);

"""

# Batch size for INSERT statements (affects file readability vs. parse speed)
BATCH_SIZE = 500


def _write_inserts(buf: io.StringIO, table: str, columns: list[str], rows: list[dict]) -> None:
    """Write batched INSERT statements into *buf*."""
    if not rows:
        return
    col_list = ", ".join(columns)
    buf.write(f"\n-- {table}: {len(rows):,} rows\n")
    for batch_start in range(0, len(rows), BATCH_SIZE):
        batch = rows[batch_start: batch_start + BATCH_SIZE]
        buf.write(f"INSERT INTO {table} ({col_list}) VALUES\n")
        value_lines = []
        for row in batch:
            vals = []
            for col in columns:
                v = row[col]
                if isinstance(v, bool):
                    vals.append("TRUE" if v else "FALSE")
                elif isinstance(v, (int, float)):
                    vals.append(str(v))
                elif isinstance(v, datetime):
                    vals.append(_ts(v))
                else:
                    vals.append(_q(str(v)))
            value_lines.append(f"  ({', '.join(vals)})")
        buf.write(",\n".join(value_lines))
        buf.write(";\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate K8s ops SQL seed data")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing SQL file")
    parser.add_argument("--fast", action="store_true",
                        help="Use tiny row counts for smoke-testing (1/10 scale)")
    args = parser.parse_args()

    cfg = load_config()
    out_path = PROJECT_ROOT / cfg["output"]["sql_migration"]
    seed: int = cfg["sql_generator"]["random_seed"]
    counts: dict = cfg["sql_generator"]["row_counts"]
    target_mb: int = cfg["sql_generator"]["target_size_mb"]

    # ------------------------------------------------------------------
    # Idempotency
    # ------------------------------------------------------------------
    # Auto-regenerate if the existing file is suspiciously small (e.g. leftover
    # from a previous --fast smoke-test run).  Threshold = 40 % of target size.
    if out_path.exists() and not args.force and not args.fast:
        size = out_path.stat().st_size
        size_mb = size / (1024 * 1024)
        min_acceptable_mb = target_mb * 0.4
        if size_mb < min_acceptable_mb:
            log(
                f"Existing file at {out_path} is only {human_size(size)} — "
                f"likely a leftover from --fast (< {min_acceptable_mb:.0f} MB threshold)."
            )
            log("Auto-regenerating at full scale …")
        else:
            log(f"Output already exists: {out_path} ({human_size(size)})")
            log("Use --force to regenerate.")
            return

    # ------------------------------------------------------------------
    # Scale for --fast mode
    # ------------------------------------------------------------------
    if args.fast:
        log("--fast mode: using 1/10 row counts for smoke-test")
        counts = {k: max(1, v // 10) for k, v in counts.items()}

    log("=" * 60)
    log("ADV RAG — Step 03: Generate K8s Ops SQL")
    log("=" * 60)
    log(f"Output: {out_path}")
    log(f"Random seed: {seed}")
    for table, count in counts.items():
        log(f"  {table:>15}: {count:>8,} rows", indent=1)

    rng = random.Random(seed)
    t0 = time.time()

    # ------------------------------------------------------------------
    # Generate data
    # ------------------------------------------------------------------
    clusters = generate_clusters(rng, counts["clusters"])
    cluster_ids = [c["cluster_id"] for c in clusters]

    nodes = generate_nodes(rng, counts["nodes"], cluster_ids)
    node_ids = [n["node_id"] for n in nodes]

    deployments = generate_deployments(rng, counts["deployments"], cluster_ids)
    deployment_ids = [d["deployment_id"] for d in deployments]

    pods = generate_pods(rng, counts["pods"], deployment_ids, node_ids)
    pod_ids = [p["pod_id"] for p in pods]

    incidents = generate_incidents(rng, counts["incidents"], cluster_ids)
    incident_ids = [i["incident_id"] for i in incidents]

    alerts = generate_alerts(rng, counts["alerts"], pod_ids)
    oncall_logs = generate_oncall_logs(rng, counts["oncall_logs"], incident_ids)

    elapsed_gen = time.time() - t0
    log(f"Data generation done in {elapsed_gen:.1f}s — writing SQL …")

    # ------------------------------------------------------------------
    # Write SQL
    # ------------------------------------------------------------------
    out_path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    buf.write(DDL)

    _write_inserts(buf, "clusters", [
        "cluster_id", "name", "region", "environment", "k8s_version", "created_at",
    ], clusters)

    _write_inserts(buf, "nodes", [
        "node_id", "cluster_id", "node_type", "cpu_cores", "memory_gb", "status", "created_at",
    ], nodes)

    _write_inserts(buf, "deployments", [
        "deployment_id", "name", "namespace", "replicas", "image", "version",
        "cluster_id", "created_at",
    ], deployments)

    _write_inserts(buf, "pods", [
        "pod_id", "namespace", "deployment_id", "status", "node_id", "created_at",
    ], pods)

    _write_inserts(buf, "incidents", [
        "incident_id", "severity", "cluster_id", "started_at", "resolved_at",
        "mttr_minutes", "rca_summary",
    ], incidents)

    _write_inserts(buf, "alerts", [
        "alert_id", "fired_at", "severity", "source_pod_id", "alertname", "resolved",
    ], alerts)

    _write_inserts(buf, "oncall_logs", [
        "log_id", "engineer", "paged_at", "incident_id", "response_time_mins",
    ], oncall_logs)

    sql_content = buf.getvalue()
    out_path.write_text(sql_content, encoding="utf-8")

    elapsed_total = time.time() - t0
    file_size = out_path.stat().st_size
    size_str = human_size(file_size)

    log("")
    log("─" * 50)
    log("K8S OPS DB SUMMARY")
    log("─" * 50)
    log(f"  Output file   : {out_path}")
    log(f"  File size     : {size_str}")
    log(f"  Target size   : ~{target_mb} MB")
    log(f"  Total rows    : {sum(counts.values()):,}")
    log(f"  Elapsed time  : {elapsed_total:.1f}s")

    if file_size < target_mb * 1024 * 1024 * 0.5:
        log(f"  WARNING: file is significantly smaller than target ({target_mb} MB)")
    elif file_size > target_mb * 1024 * 1024 * 2.0:
        log(f"  WARNING: file is significantly larger than target ({target_mb} MB)")
    else:
        log("  Size check: OK")
    log("─" * 50)


if __name__ == "__main__":
    main()
