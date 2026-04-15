"""
Stage 0: Explore the Cala API to discover what fields and entity types
work for querying NASDAQ-listed companies.

Run this script first — output goes to output/api_schema_notes.md
"""

import json
import os
import time
from pathlib import Path

import requests

# ── Auth ──────────────────────────────────────────────────────────────────────

def load_api_key() -> str:
    api_key = os.getenv("API_KEY") or os.getenv("CALA_API_KEY")
    if api_key:
        return api_key
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, value = raw.split("=", 1)
            if key.strip() in {"API_KEY", "CALA_API_KEY"}:
                return value.strip().strip('"').strip("'")
    raise ValueError("Missing API key. Set API_KEY/CALA_API_KEY in env or .env")


API_KEY = load_api_key()
BASE_URL = "https://api.cala.ai"
HEADERS = {"X-API-KEY": API_KEY, "Content-Type": "application/json"}
OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def cala_query(query: str) -> dict:
    """POST /v1/knowledge/query — structured dot-notation filtering."""
    resp = requests.post(
        f"{BASE_URL}/v1/knowledge/query",
        json={"input": query},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def cala_search(query: str) -> dict:
    """POST /v1/knowledge/search — natural language research."""
    resp = requests.post(
        f"{BASE_URL}/v1/knowledge/search",
        json={"input": query},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def entity_search(name: str, limit: int = 5) -> dict:
    """GET /v1/entities — fuzzy name lookup."""
    resp = requests.get(
        f"{BASE_URL}/v1/entities",
        params={"name": name, "limit": limit},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def entity_introspect(entity_id: str) -> dict:
    """GET /v1/entities/{id}/introspection — discover available fields."""
    resp = requests.get(
        f"{BASE_URL}/v1/entities/{entity_id}/introspection",
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def retrieve_entity(entity_id: str) -> dict:
    """POST /v1/entities/{id} — full entity profile."""
    resp = requests.post(
        f"{BASE_URL}/v1/entities/{entity_id}",
        json={},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# ── Probe functions ───────────────────────────────────────────────────────────

def probe_query_formats() -> dict:
    """Try different query formats to find what works for NASDAQ companies."""
    candidates = [
        "companies.exchange=NASDAQ",
        "stocks.exchange=NASDAQ",
        "public_companies.exchange=NASDAQ",
        "companies.listed_exchange=NASDAQ",
        "companies.stock_exchange=NASDAQ",
        "companies.exchange=NASDAQ.sector=Technology",
        "companies.exchange=NASDAQ.industry=semiconductors",
        "companies.exchange=NASDAQ.revenue_growth>20",
        "nasdaq.companies",
    ]

    results = {}
    for query in candidates:
        print(f"\n  Testing query: {query}")
        try:
            data = cala_query(query)
            count = len(data.get("results", []))
            entity_count = len(data.get("entities", []))
            results[query] = {
                "status": "OK",
                "result_count": count,
                "entity_count": entity_count,
                "sample": data.get("results", [])[:2],
            }
            print(f"    → {count} results, {entity_count} entities")
        except requests.HTTPError as e:
            results[query] = {"status": f"HTTP {e.response.status_code}", "error": str(e)}
            print(f"    → ERROR {e.response.status_code}")
        except Exception as e:
            results[query] = {"status": "ERROR", "error": str(e)}
            print(f"    → ERROR {e}")
        time.sleep(0.5)  # be gentle with rate limits

    return results


def probe_known_companies() -> dict:
    """
    Look up 3 well-known NASDAQ companies by name, then introspect their
    available fields to understand what financial data Cala exposes.
    """
    known = ["Nvidia", "Apple", "Microsoft"]
    findings = {}

    for name in known:
        print(f"\n  Looking up: {name}")
        try:
            search_result = entity_search(name, limit=3)
            entities = search_result if isinstance(search_result, list) else search_result.get("entities", [])
            if not entities:
                print(f"    → no entities found")
                findings[name] = {"error": "not found"}
                continue

            # Take the first Company-type result
            entity = next(
                (e for e in entities if e.get("entity_type") == "Company"),
                entities[0],
            )
            eid = entity.get("id")
            print(f"    → found entity {eid} ({entity.get('entity_type')})")

            # Introspect available fields
            intro = entity_introspect(eid)
            findings[name] = {
                "id": eid,
                "entity_type": entity.get("entity_type"),
                "introspection": intro,
            }
            time.sleep(0.5)

        except Exception as e:
            findings[name] = {"error": str(e)}
            print(f"    → ERROR {e}")

    return findings


def probe_search_endpoint() -> dict:
    """
    Test the /knowledge/search endpoint with a NASDAQ-relevant query to see
    what kind of narrative + sourced data it returns.
    """
    queries = [
        "What NASDAQ technology companies have the highest revenue growth in 2024-2025?",
        "Which NASDAQ-listed AI semiconductor companies are growing fastest?",
    ]
    results = {}
    for q in queries:
        print(f"\n  Search: {q[:60]}...")
        try:
            data = cala_search(q)
            results[q] = {
                "answer_length": len(data.get("answer", {}).get("content", "")),
                "context_count": len(data.get("answer", {}).get("context", [])),
                "entity_count": len(data.get("answer", {}).get("entities", [])),
                "entities": [e.get("name") for e in data.get("answer", {}).get("entities", [])[:10]],
                "sample_answer": data.get("answer", {}).get("content", "")[:500],
            }
            print(f"    → answer {results[q]['answer_length']} chars, "
                  f"{results[q]['entity_count']} entities: {results[q]['entities']}")
        except Exception as e:
            results[q] = {"error": str(e)}
            print(f"    → ERROR {e}")
        time.sleep(1)
    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    notes = {}

    print("=" * 60)
    print("STAGE 0: Cala API Exploration")
    print("=" * 60)

    print("\n[1/3] Probing query formats for NASDAQ companies...")
    notes["query_formats"] = probe_query_formats()

    print("\n[2/3] Introspecting known NASDAQ companies...")
    notes["known_companies"] = probe_known_companies()

    print("\n[3/3] Testing /knowledge/search endpoint...")
    notes["search_results"] = probe_search_endpoint()

    # Save raw JSON for inspection
    raw_path = OUTPUT_DIR / "exploration_raw.json"
    raw_path.write_text(json.dumps(notes, indent=2, default=str))
    print(f"\n  Raw output saved to: {raw_path}")

    # Write human-readable notes
    write_schema_notes(notes)


def write_schema_notes(notes: dict):
    lines = ["# Cala API Schema Notes\n", "_Generated by src/explore_cala.py_\n\n"]

    lines.append("## Query Format Results\n\n")
    for query, result in notes.get("query_formats", {}).items():
        status = result.get("status", "?")
        count = result.get("result_count", "-")
        lines.append(f"- `{query}` → **{status}** ({count} results)\n")
        if result.get("sample"):
            lines.append(f"  - Sample: `{json.dumps(result['sample'][0])[:120]}`\n")

    lines.append("\n## Known Company Introspection\n\n")
    for name, data in notes.get("known_companies", {}).items():
        lines.append(f"### {name}\n")
        if "error" in data:
            lines.append(f"- Error: {data['error']}\n")
        else:
            lines.append(f"- Entity ID: `{data.get('id')}`\n")
            lines.append(f"- Type: `{data.get('entity_type')}`\n")
            intro = data.get("introspection", {})
            props = intro.get("properties", intro.get("available_properties", []))
            if props:
                lines.append(f"- Available properties: {props}\n")
            obs = intro.get("numerical_observations", [])
            if obs:
                lines.append(f"- Numerical observations: {obs}\n")
            rels = intro.get("relationships", [])
            if rels:
                lines.append(f"- Relationships: {rels}\n")
            # dump everything we got in case structure is different
            lines.append(f"- Raw introspection keys: {list(intro.keys())}\n")
        lines.append("\n")

    lines.append("\n## Search Endpoint Results\n\n")
    for q, result in notes.get("search_results", {}).items():
        lines.append(f"**Query:** {q}\n\n")
        if "error" in result:
            lines.append(f"- Error: {result['error']}\n")
        else:
            lines.append(f"- Entities found: {result.get('entities')}\n")
            lines.append(f"- Answer excerpt:\n\n```\n{result.get('sample_answer', '')}\n```\n")
        lines.append("\n")

    out_path = OUTPUT_DIR / "api_schema_notes.md"
    out_path.write_text("".join(lines))
    print(f"  Schema notes saved to: {out_path}")


if __name__ == "__main__":
    main()
