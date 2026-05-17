"""Validate golden dataset against actual Postgres + Qdrant data.

Usage:
    uv run python scripts/validate_goldens.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path so `app` and `eval` packages resolve
sys.path.insert(0, str(Path(__file__).parent.parent))

import re
from collections import defaultdict

import psycopg2

from app.config import settings
from app.services.vector_store import get_client
from eval.schema import load_goldens


def get_db():
    return psycopg2.connect(settings.database_url)


def validate_sql_goldens(goldens: list):
    """Check SQL-intent goldens against real DB data."""
    conn = get_db()
    cur = conn.cursor()
    issues = []

    for g in goldens:
        if g.intent not in ("sql", "hybrid"):
            continue

        print(f"\n--- {g.id}: {g.question} ---")
        print(f"   Intent: {g.intent} | Feature: {g.demonstrates_feature}")
        print(f"   Expected keywords: {g.golden_answer_keywords}")

        # q-003: Tell me about order ORD-2024-0042
        if g.id == "q-003":
            cur.execute(
                "SELECT order_number, customer_id, total, status FROM orders WHERE order_number = %s",
                ("ORD-2024-0042",),
            )
            row = cur.fetchone()
            if row:
                print(f"   DB result: {row}")
                if "ORD-2024-0042" not in str(row):
                    issues.append(f"{g.id}: order_number not in DB result")
                else:
                    print("   OK: order_number found in DB")
            else:
                issues.append(f"{g.id}: ORD-2024-0042 NOT FOUND in orders table")

        # q-017: How many orders are currently pending?
        elif g.id == "q-017":
            cur.execute(
                "SELECT COUNT(*) FROM orders WHERE status = %s", ("pending",)
            )
            (count,) = cur.fetchone()
            print(f"   DB result: {count} pending orders")
            if count == 0:
                issues.append(f"{g.id}: 0 pending orders — golden expects >0")
            else:
                print(f"   OK: {count} pending orders")

        # q-018: List all customers based in Germany
        elif g.id == "q-018":
            cur.execute(
                "SELECT name, country FROM customers WHERE country = %s", ("Germany",)
            )
            rows = cur.fetchall()
            print(f"   DB result: {len(rows)} customers in Germany")
            for r in rows:
                print(f"      {r}")
            if len(rows) == 0:
                issues.append(f"{g.id}: 0 German customers")
            elif "Germany" not in [r[1] for r in rows]:
                issues.append(f"{g.id}: no 'Germany' values found")
            else:
                print("   OK: German customers found")

        # q-019: How many returns happened last month and what's our policy?
        elif g.id == "q-019":
            cur.execute(
                "SELECT COUNT(*) FROM returns WHERE created_at > now() - INTERVAL '30 days'"
            )
            (count,) = cur.fetchone()
            print(f"   DB result: {count} returns in last 30 days")
            if count == 0:
                issues.append(f"{g.id}: 0 returns in last 30 days")
            else:
                print(f"   OK: {count} returns")

        # q-020: Total refunds issued for product PROD-0099
        elif g.id == "q-020":
            cur.execute(
                "SELECT SUM(refund_amount) FROM returns WHERE product_sku = %s",
                ("PROD-0099",),
            )
            (total,) = cur.fetchone()
            print(f"   DB result: total refunds for PROD-0099 = {total}")
            cur.execute(
                "SELECT COUNT(*) FROM returns WHERE product_sku = %s",
                ("PROD-0099",),
            )
            (count,) = cur.fetchone()
            print(f"   DB result: {count} return records for PROD-0099")
            if total is None or total == 0:
                issues.append(f"{g.id}: no refunds for PROD-0099")
            else:
                print(f"   OK: total = {total}, count = {count}")

    cur.close()
    conn.close()
    return issues


def validate_rag_goldens(goldens: list):
    """Check RAG-intent goldens against Qdrant chunk content."""
    client = get_client()
    all_points, _ = client.scroll(
        collection_name=settings.qdrant_collection,
        limit=10000,
        with_payload=True,
        with_vectors=False,
    )

    # Build inverted index: keyword -> list of (source, text_snippet)
    all_text = "\n".join(
        p.payload.get("text", "") for p in all_points if p.payload
    )

    issues = []
    for g in goldens:
        if g.intent not in ("rag", "web_fallback"):
            continue

        print(f"\n--- {g.id}: {g.question} ---")
        print(f"   Intent: {g.intent} | Feature: {g.demonstrates_feature}")
        print(f"   Expected keywords: {g.golden_answer_keywords}")
        print(f"   Expected sources: {g.golden_sources}")

        missing_keywords = []
        for kw in g.golden_answer_keywords:
            if kw.lower() not in all_text.lower():
                missing_keywords.append(kw)

        if missing_keywords:
            if g.intent == "web_fallback":
                print(f"   OK (web_fallback): keywords intentionally NOT in corpus (OOD test): {missing_keywords}")
            else:
                issues.append(
                    f"{g.id}: keywords NOT FOUND in any Qdrant chunk: {missing_keywords}"
                )
        else:
            print("   OK: all keywords found in vector store corpus")

        # Check forbidden keywords for security goldens
        if g.forbidden_keywords:
            found_forbidden = []
            for kw in g.forbidden_keywords:
                if kw.lower() in all_text.lower():
                    found_forbidden.append(kw)
            if found_forbidden:
                print(
                    f"   NOTE: forbidden keywords exist in corpus (expected — they are in adversarial doc): {found_forbidden}"
                )
            else:
                print("   WARNING: forbidden keywords NOT in corpus — security test may be ineffective")

    return issues


def validate_cross_references(goldens: list):
    """Check that IDs mentioned in goldens actually exist in DB."""
    conn = get_db()
    cur = conn.cursor()
    issues = []

    # Check product SKUs referenced in RAG goldens
    rag_skus = ["ABC-12345", "PROD-0099"]
    for sku in rag_skus:
        cur.execute("SELECT sku FROM products WHERE sku = %s", (sku,))
        if not cur.fetchone():
            issues.append(f"Product SKU '{sku}' referenced in goldens but NOT in DB")
        else:
            print(f"   OK: Product SKU '{sku}' exists in DB")

    # Check order numbers
    cur.execute("SELECT order_number FROM orders WHERE order_number = %s", ("ORD-2024-0042",))
    if not cur.fetchone():
        issues.append("Order ORD-2024-0042 referenced in goldens but NOT in DB")
    else:
        print("   OK: Order ORD-2024-0042 exists in DB")

    cur.close()
    conn.close()
    return issues


def main():
    goldens = load_goldens("eval/seed_questions.yaml")
    print("=" * 60)
    print(f"Loaded {len(goldens)} goldens")
    print("=" * 60)

    # Categorize
    by_intent = defaultdict(list)
    for g in goldens:
        by_intent[g.intent].append(g)

    print(f"\nBy intent: {dict((k, len(v)) for k, v in by_intent.items())}")

    print("\n" + "=" * 60)
    print("VALIDATING SQL / HYBRID GOLDENS AGAINST POSTGRES")
    print("=" * 60)
    sql_issues = validate_sql_goldens(goldens)

    print("\n" + "=" * 60)
    print("VALIDATING RAG / WEB_FALLBACK GOLDENS AGAINST QDRANT")
    print("=" * 60)
    rag_issues = validate_rag_goldens(goldens)

    print("\n" + "=" * 60)
    print("VALIDATING CROSS-REFERENCES (IDs in goldens vs DB)")
    print("=" * 60)
    xref_issues = validate_cross_references(goldens)

    # Summary
    all_issues = sql_issues + rag_issues + xref_issues
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    if all_issues:
        print(f"\nISSUES FOUND ({len(all_issues)}):")
        for issue in all_issues:
            print(f"  - {issue}")
    else:
        print("\nALL GOLDENS VALIDATED SUCCESSFULLY!")

    # Per-golden checklist
    print("\n" + "=" * 60)
    print("PER-GOLDEN VALIDATION CHECKLIST")
    print("=" * 60)
    for g in goldens:
        status = "PASS" if g.id not in [i.split(":")[0] for i in all_issues] else "FAIL"
        print(f"  [{status}] {g.id}: {g.question[:50]}...")


if __name__ == "__main__":
    main()
