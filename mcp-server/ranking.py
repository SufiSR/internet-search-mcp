"""
BM25 result ranking.

Provides a pure function that re-ranks a list of SearchResult objects using
the BM25Okapi algorithm. Combining title and snippet text gives the ranker
enough signal to prioritise results that are most relevant to the query.

This module has no I/O and no side effects — it is straightforward to test
in isolation.
"""

import logging

from rank_bm25 import BM25Okapi

from search import SearchResult

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> list[str]:
    """
    Split text into lowercase tokens on whitespace.

    Simple whitespace splitting is intentional: it avoids introducing an NLTK
    or spaCy dependency for marginal ranking quality improvement at this scale.
    """
    return text.lower().split()


def rank_results(
    results: list[SearchResult],
    query: str,
    top_n: int,
) -> list[SearchResult]:
    """
    Re-rank search results using BM25 and return the top N.

    Args:
        results: List of SearchResult objects from SearXNG.
        query:   The original search query used to score relevance.
        top_n:   Number of top results to return.

    Returns:
        Up to top_n results sorted by BM25 score descending.
        Returns the original list (truncated) if ranking cannot be performed.
    """
    if not results:
        return []

    if len(results) <= top_n:
        # Not enough results to warrant ranking; return what we have
        logger.debug("Fewer results than top_n (%d <= %d); skipping BM25", len(results), top_n)
        return results

    # Build corpus: each document is the concatenation of title + snippet
    corpus = [_tokenize(f"{result.title} {result.snippet}") for result in results]
    query_tokens = _tokenize(query)

    try:
        bm25 = BM25Okapi(corpus)
        scores = bm25.get_scores(query_tokens)
    except Exception as exc:
        logger.warning("BM25 ranking failed: %s — returning first %d results", exc, top_n)
        return results[:top_n]

    # Pair each result with its score and sort descending
    scored = sorted(zip(scores, results), key=lambda pair: pair[0], reverse=True)

    top_results = [result for _, result in scored[:top_n]]
    logger.debug("BM25 selected %d results from %d candidates", len(top_results), len(results))

    return top_results
