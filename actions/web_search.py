



        # web_search.py

import json
import sys
from pathlib import Path


def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = _get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"


def _get_api_key() -> str:
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]


# =========================
# GEMINI SEARCH
# =========================

def _gemini_search(query: str) -> str:
    try:
        from google import genai

        client = genai.Client(api_key=_get_api_key())

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=query,
            config={
                "tools": [{"google_search": {}}],
                "temperature": 0.3,
            },
        )

        text = response.text.strip()

        if not text:
            raise ValueError("Empty Gemini response.")

        return text

    except Exception as e:
        raise Exception(f"Gemini failed: {e}")


# =========================
# DDGS SEARCH
# =========================

def _ddg_search(query: str, max_results: int = 6) -> list[dict]:
    try:
        from ddgs import DDGS

        results = []

        with DDGS() as ddgs:
            search_results = ddgs.text(
                query,
                region="in-en",
                safesearch="off",
                max_results=max_results
            )

            for r in search_results:
                results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "url": r.get("href", ""),
                })

        return results

    except Exception as e:
        print(f"[DDGS] ❌ Error: {e}")
        return []


# =========================
# FORMAT DDGS RESULTS
# =========================

def _format_ddg(query: str, results: list[dict]) -> str:
    if not results:
        return f"No results found for: {query}"

    lines = [f"Search results for: {query}\n"]

    for i, r in enumerate(results, 1):

        title = r.get("title", "")
        snippet = r.get("snippet", "")
        url = r.get("url", "")

        if title:
            lines.append(f"{i}. {title}")

        if snippet:
            lines.append(f"   {snippet}")

        if url:
            lines.append(f"   {url}")

        lines.append("")

    return "\n".join(lines).strip()


# =========================
# COMPARE FUNCTION
# =========================

def _compare(items: list[str], aspect: str) -> str:

    query = (
        f"Compare {', '.join(items)} "
        f"in terms of {aspect}. "
        f"Give specific facts and data."
    )

    try:
        return _gemini_search(query)

    except Exception as e:
        print(f"[Compare] ⚠️ Gemini failed: {e}")

    # DDGS fallback

    all_results = {}

    for item in items:
        try:
            all_results[item] = _ddg_search(
                f"{item} {aspect}",
                max_results=3
            )
        except Exception:
            all_results[item] = []

    lines = [
        f"Comparison — {aspect.upper()}",
        "─" * 40
    ]

    for item in items:

        lines.append(f"\n▸ {item}")

        for r in all_results.get(item, [])[:2]:

            snippet = r.get("snippet")

            if snippet:
                lines.append(f"  • {snippet}")

    return "\n".join(lines)


# =========================
# MAIN WEB SEARCH
# =========================

def web_search(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:

    params = parameters or {}

    query = params.get("query", "").strip()
    mode = params.get("mode", "search").lower().strip()

    items = params.get("items", [])
    aspect = params.get("aspect", "general").strip() or "general"

    if not query and not items:
        return "Please provide a search query, sir."

    if items and mode != "compare":
        mode = "compare"

    if player:
        player.write_log(f"[Search] {query or ', '.join(items)}")

    print(f"[WebSearch] 🔍 Query: {query!r}  Mode: {mode}")

    # =========================
    # COMPARE MODE
    # =========================

    if mode == "compare" and items:
        return _compare(items, aspect)

    # =========================
    # 1️⃣ OPENROUTER
    # =========================

    try:
        from or_client import client

        result = client.chat(
            query,
            system="You are a factual web search assistant."
        )

        if result and len(result.strip()) > 10:
            print("[WebSearch] ✅ OpenRouter OK.")
            return result

    except Exception as e:
        print(f"[WebSearch] ⚠️ OpenRouter failed: {e}")

    # =========================
    # 2️⃣ GEMINI SEARCH
    # =========================

    try:
        print("[WebSearch] 🔍 Trying Gemini Search...")

        result = _gemini_search(query)

        if result:
            print("[WebSearch] ✅ Gemini OK.")
            return result

    except Exception as e:
        print(f"[WebSearch] ⚠️ Gemini failed: {e}")

    # =========================
    # 3️⃣ DDGS SEARCH
    # =========================

    try:
        print("[WebSearch] 🔍 Trying DDGS...")

        results = _ddg_search(query)

        if results:
            print(f"[WebSearch] ✅ DDGS OK ({len(results)} results)")
            return _format_ddg(query, results)

        return f"No results found for: {query}"

    except Exception as e:
        print(f"[WebSearch] ❌ All backends failed: {e}")
        return f"Search failed, sir: {e}"