from app.core.constants import CrawlEntryType
from app.db.schemas import WebCrawlConfig
from app.ingestion.crawler import HTMLPageParser, WebCrawler
from app.ingestion.crawler.models import FetchedPage


def test_url_discovery_respects_domain_and_path_scope() -> None:
    crawler = WebCrawler()
    config = WebCrawlConfig(
        entry_type=CrawlEntryType.URL_LIST,
        urls=[
            "https://docs.example.test/guide/start",
            "https://docs.example.test/private/secret",
            "https://other.example.test/guide/nope",
            "https://docs.example.test/guide/start",
        ],
        allowed_domains=["docs.example.test"],
        include_paths=["/guide"],
        exclude_paths=["/private"],
    )

    discovered = crawler._discover_url_list(config)

    assert [item.discovered_url for item in discovered] == ["https://docs.example.test/guide/start"]


def test_html_parser_extracts_selected_content_and_sections() -> None:
    page = FetchedPage(
        item_key="https://docs.example.test/guide",
        discovered_url="https://docs.example.test/guide",
        final_url="https://docs.example.test/guide",
        status_code=200,
        html="""<html><head><title>Documentation</title></head><body>
        <nav>navigation</nav><main><h1 id='intro'>Intro</h1><p>Useful text</p>
        <script>ignored()</script><h2>Next</h2><p>More text</p></main></body></html>""",
        content_type="text/html",
        etag=None,
        last_modified=None,
        not_modified=False,
    )
    options = WebCrawler().resolve_extraction_options(
        config=WebCrawlConfig(entry_type=CrawlEntryType.URL_LIST, urls=[page.discovered_url]),
        url=page.discovered_url,
    )

    parsed = HTMLPageParser().parse(page, options=options)

    assert parsed.parsed_document.title == "Documentation"
    assert "Useful text" in parsed.parsed_document.text
    assert "navigation" not in parsed.parsed_document.text
    assert [section.header for section in parsed.parsed_document.sections] == ["Intro", "Next"]
    assert parsed.parsed_document.sections[0].anchor == "#intro"
