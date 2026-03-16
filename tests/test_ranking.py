"""
Tests for BM25 ranking.

ranking.py is a pure function with no I/O — no mocking needed.
"""

import pytest

from ranking import rank_results
from search import SearchResult


def make_result(title: str, snippet: str, url: str = "https://example.com") -> SearchResult:
    return SearchResult(title=title, url=url, snippet=snippet)


class TestRankResults:
    def test_most_relevant_result_ranked_first(self):
        # Three documents are required: BM25Okapi IDF collapses to log(1)=0
        # when a query term appears in exactly half of a 2-doc corpus, making
        # all scores equal. A third document ensures non-zero IDF values.
        results = [
            make_result(
                "Unrelated gardening tips",
                "How to grow tomatoes and water plants in your garden.",
                url="https://example.com/gardening",
            ),
            make_result(
                "Python asyncio tutorial",
                "asyncio is used for concurrent Python programming with async await.",
                url="https://example.com/asyncio",
            ),
            make_result(
                "Recipe collection",
                "Delicious food recipes for breakfast lunch and dinner.",
                url="https://example.com/recipes",
            ),
        ]

        ranked = rank_results(results, query="asyncio Python concurrent", top_n=1)

        assert len(ranked) == 1
        assert "asyncio" in ranked[0].url

    def test_top_n_limits_output_length(self, sample_search_results):
        ranked = rank_results(sample_search_results, query="python async", top_n=2)
        assert len(ranked) == 2

    def test_empty_input_returns_empty_list(self):
        ranked = rank_results([], query="anything", top_n=3)
        assert ranked == []

    def test_single_result_returned_without_ranking(self):
        single = [make_result("Only result", "some content")]
        ranked = rank_results(single, query="anything", top_n=3)
        # top_n > len(results) — should return the original list unchanged
        assert len(ranked) == 1
        assert ranked[0].title == "Only result"

    def test_top_n_larger_than_results_returns_all(self, sample_search_results):
        ranked = rank_results(sample_search_results, query="python", top_n=100)
        # All results should be returned when top_n exceeds len
        assert len(ranked) == len(sample_search_results)

    def test_gardening_result_ranked_below_python_results(self, sample_search_results):
        ranked = rank_results(sample_search_results, query="python async programming", top_n=3)
        urls = [r.url for r in ranked]

        # The gardening result should not be first
        assert "gardening" not in ranked[0].url
