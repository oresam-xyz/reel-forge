"""Phase 1: Web research — gather facts and sources for the given topic."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from reelforge.agent.brand import BrandIdentity
from reelforge.agent.project import Project
from reelforge.providers.base import Providers, ResearchNotes, ResearchSource

logger = logging.getLogger(__name__)

SEARCH_QUERY_PROMPT = """\
You are a research assistant. Given the following topic and content niche, \
generate {num_queries} distinct web search queries that would surface the most \
relevant, recent, and interesting information for creating a short-form video.

Topic: {topic}
Niche context: {character}

Return a JSON object with a single key "queries" containing a list of search query strings.
Example: {{"queries": ["query one", "query two", "query three"]}}
"""

SUMMARISE_PROMPT = """\
You are a research assistant preparing notes for a short-form video script.

Topic: {topic}

Below are search results. Extract the most relevant facts, statistics, and \
interesting angles. Ignore irrelevant results.

Search results:
{results_text}

Return a JSON object with:
- "key_facts": a list of concise factual statements (strings) relevant to the topic
- "needs_more_research": a boolean — true if the facts are insufficient to write a compelling video script

Example:
{{
  "key_facts": ["Fact one", "Fact two"],
  "needs_more_research": false
}}
"""


def _search_web(query: str) -> list[dict]:
    """Run a single DuckDuckGo search and return results."""
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        raise ImportError(
            "The 'duckduckgo-search' package is required for web research. "
            "Install it with: pip install duckduckgo-search"
        )

    results = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=5):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "body": r.get("body", ""),
            })
    return results


def run(project: Project, brand: BrandIdentity, providers: Providers) -> None:
    """Execute the research phase."""
    topic = project.state.topic
    llm = providers.llm

    # Step 1: Generate search queries
    logger.info("Generating search queries for topic: %s", topic)
    query_prompt = SEARCH_QUERY_PROMPT.format(
        num_queries=3,
        topic=topic,
        character=brand.data.persona.character,
    )
    query_data = llm.generate_json(query_prompt, system="You are a research assistant.")
    queries = query_data.get("queries", [topic])
    if not queries:
        queries = [topic]
    logger.info("Generated %d search queries", len(queries))

    # Step 2: Execute searches
    all_sources: list[ResearchSource] = []
    all_results_text_parts: list[str] = []

    for query in queries:
        logger.info("Searching: %s", query)
        try:
            results = _search_web(query)
        except Exception as e:
            logger.warning("Search failed for '%s': %s", query, e)
            continue

        for r in results:
            all_sources.append(ResearchSource(
                url=r["url"],
                title=r["title"],
                summary=r["body"],
            ))
            all_results_text_parts.append(
                f"Title: {r['title']}\nURL: {r['url']}\nSnippet: {r['body']}"
            )

    if not all_sources:
        logger.warning("No search results found, proceeding with topic only")

    # Step 3: Summarise findings
    results_text = "\n\n---\n\n".join(all_results_text_parts) if all_results_text_parts else "(no results)"
    summarise_prompt = SUMMARISE_PROMPT.format(
        topic=topic,
        results_text=results_text,
    )
    summary_data = llm.generate_json(summarise_prompt, system="You are a research assistant.")
    key_facts = summary_data.get("key_facts", [])

    # Step 4: If LLM says more research is needed, do one more round
    if summary_data.get("needs_more_research", False) and len(queries) < 5:
        logger.info("LLM suggests more research — running additional queries")
        extra_prompt = SEARCH_QUERY_PROMPT.format(
            num_queries=2,
            topic=f"{topic} (focusing on gaps: need more specific data/stats)",
            character=brand.data.persona.character,
        )
        extra_data = llm.generate_json(extra_prompt, system="You are a research assistant.")
        extra_queries = extra_data.get("queries", [])

        for query in extra_queries:
            logger.info("Extra search: %s", query)
            queries.append(query)
            try:
                results = _search_web(query)
            except Exception as e:
                logger.warning("Extra search failed for '%s': %s", query, e)
                continue

            for r in results:
                all_sources.append(ResearchSource(
                    url=r["url"],
                    title=r["title"],
                    summary=r["body"],
                ))
                all_results_text_parts.append(
                    f"Title: {r['title']}\nURL: {r['url']}\nSnippet: {r['body']}"
                )

        # Re-summarise with all results
        results_text = "\n\n---\n\n".join(all_results_text_parts)
        summarise_prompt = SUMMARISE_PROMPT.format(
            topic=topic,
            results_text=results_text,
        )
        summary_data = llm.generate_json(summarise_prompt, system="You are a research assistant.")
        key_facts = summary_data.get("key_facts", [])

    # Step 5: Save research notes
    notes = ResearchNotes(
        queries=queries,
        sources=all_sources,
        key_facts=key_facts,
        completed_at=datetime.now(timezone.utc).isoformat(),
    )
    project.save_research(notes)
    logger.info("Research complete: %d sources, %d key facts", len(all_sources), len(key_facts))
