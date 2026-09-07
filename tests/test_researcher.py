from app.producer.researcher import ResearcherAgent


def test_researcher_terms_do_not_match_unrelated_guidance():
    query_terms = ResearcherAgent._content_terms("temperature conversion")
    rate_limiter_terms = ResearcherAgent._content_terms(
        "Clean Rate Limiter Design Token bucket HTTP 429"
    )

    assert query_terms
    assert not query_terms.intersection(rate_limiter_terms)


def test_researcher_ignores_shared_framework_terms():
    query_terms = ResearcherAgent._content_terms("Python utility with pytest tests")

    assert query_terms == {"utility"}