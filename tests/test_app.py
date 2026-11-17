"""Interface checks with fake credentials and mocked providers; no API calls."""

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import streamlit as st
from streamlit.testing.v1 import AppTest

from book_search import BooksServiceError, SearchResult

APP_FILE = Path(__file__).resolve().parents[1] / "main.py"


class AppTests(unittest.TestCase):
    def setUp(self):
        st.cache_data.clear()
        st.cache_resource.clear()

    def run_search(self, result=None, provider_error=None):
        app = AppTest.from_file(str(APP_FILE), default_timeout=15)
        app.secrets["GEMINI_KEY"] = "fake-gemini-key"
        app.secrets["BOOKS_KEY"] = "fake-books-key"
        client = Mock()
        client.models.generate_content.return_value.text = "Harry Potter by J.K. Rowling [en]"
        if provider_error:
            client.models.generate_content.side_effect = provider_error
        with patch("google.genai.Client", return_value=client), patch(
            "book_search.fetch_verified_books", return_value=result,
        ) as search:
            app.run()
            app.text_input[0].set_value("A boy with a lightning scar").run()
        self.assertFalse(app.exception)
        return app, search

    def test_details_and_fallback_cover_render(self):
        item = {"volumeInfo": {
            "title": "Harry Potter", "authors": ["J. K. Rowling"], "language": "en",
            "description": "A young wizard's story.",
            "imageLinks": {"smallThumbnail": "http://books.google.com/cover"},
        }}
        app, search = self.run_search(SearchResult([item], 1, 1))
        self.assertEqual(app.subheader[0].value, "Harry Potter")
        self.assertEqual(len(app.success), 1)
        self.assertEqual(len(app.get("image")), 1)
        self.assertEqual(app.get("image")[0].value, ["https://books.google.com/cover"])
        self.assertTrue(any("young wizard" in element.value for element in app.markdown))
        self.assertEqual(search.call_args.args[-1], "fake-books-key")

    def test_missing_cover_keeps_book_details(self):
        item = {"volumeInfo": {"title": "Harry Potter", "authors": ["J.K. Rowling"], "language": "en"}}
        app, _ = self.run_search(SearchResult([item], 1, 1))
        self.assertFalse(any(element.value == "Cover unavailable" for element in app.caption))
        self.assertFalse(app.get("image"))
        self.assertEqual(app.subheader[0].value, "Harry Potter")

    def test_illustrated_editions_are_displayed_first(self):
        plain = {"volumeInfo": {"title": "Plain edition", "authors": ["J.K. Rowling"], "language": "en"}}
        illustrated = {"volumeInfo": {
            "title": "Illustrated edition", "authors": ["J.K. Rowling"], "language": "en",
            "imageLinks": {"thumbnail": "https://books.google.com/cover"},
        }}
        app, _ = self.run_search(SearchResult([plain, illustrated], 2, 2))
        self.assertEqual([element.value for element in app.subheader], ["Illustrated edition", "Plain edition"])

    def test_rerun_reuses_identification_and_library_results(self):
        app = AppTest.from_file(str(APP_FILE), default_timeout=15)
        app.secrets["GEMINI_KEY"] = "fake-gemini-key"
        app.secrets["BOOKS_KEY"] = "fake-books-key"
        client = Mock()
        client.models.generate_content.return_value.text = "Harry Potter by J.K. Rowling [en]"
        with patch("google.genai.Client", return_value=client), patch(
            "book_search.fetch_verified_books", return_value=SearchResult(),
        ) as search:
            app.run()
            app.text_input[0].set_value("A young wizard").run()
            app.run()
            self.assertFalse(app.exception)
            self.assertEqual(client.models.generate_content.call_count, 1)
            self.assertEqual(search.call_count, 1)

    def test_empty_author_and_language_messages(self):
        for result, text in (
            (SearchResult(), "returned no records"),
            (SearchResult(retrieved=1), "none matched the identified author"),
            (SearchResult(retrieved=1, author_matches=1), "none had confirmed EN"),
        ):
            with self.subTest(text=text):
                st.cache_data.clear()
                app, _ = self.run_search(result)
                self.assertFalse(app.success)
                self.assertTrue(any(text in element.value for element in app.info))

    def test_provider_errors_never_display_credentials(self):
        app, _ = self.run_search(provider_error=RuntimeError("url?key=private-key"))
        self.assertEqual(len(app.error), 1)
        self.assertNotIn("private-key", app.error[0].value)

    def test_books_errors_are_displayed_without_success(self):
        app = AppTest.from_file(str(APP_FILE), default_timeout=15)
        app.secrets["GEMINI_KEY"] = "fake-gemini-key"
        app.secrets["BOOKS_KEY"] = "fake-books-key"
        client = Mock()
        client.models.generate_content.return_value.text = "Harry Potter by J.K. Rowling [en]"
        with patch("google.genai.Client", return_value=client), patch(
            "book_search.fetch_verified_books", side_effect=BooksServiceError("Google Books quota reached."),
        ):
            app.run()
            app.text_input[0].set_value("A young wizard").run()
        self.assertFalse(app.exception)
        self.assertFalse(app.success)
        self.assertIn("quota", app.error[0].value)


if __name__ == "__main__":
    unittest.main()
