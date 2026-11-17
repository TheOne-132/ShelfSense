import unittest
from unittest.mock import Mock, patch

import requests

from book_search import (
    BooksServiceError, author_matches, cover_url, fetch_verified_books,
    google_books_request, language_matches, parse_book_match,
)


def book(volume_id="one", author="J. K. Rowling", language="en", **extra):
    return {"id": volume_id, "volumeInfo": {
        "title": "Harry Potter", "authors": [author], "language": language, **extra,
    }}


class MatchingTests(unittest.TestCase):
    def test_author_punctuation_and_spacing(self):
        self.assertTrue(author_matches("J.K. Rowling", ["J. K. Rowling"]))
        self.assertTrue(author_matches("J. K. Rowling", ["Joanne Kathleen Rowling"]))
        self.assertTrue(author_matches("Gabriel García Márquez", ["Gabriel Garcia Marquez"]))

    def test_short_or_different_author_is_not_accepted(self):
        for author in ("Rowling", "J", "Anne Rowling", "Not J.K. Rowling"):
            with self.subTest(author=author):
                self.assertFalse(author_matches("J.K. Rowling", [author]))
        self.assertFalse(author_matches("", ["Some Author"]))

    def test_missing_and_wrong_language_rejected(self):
        for language in (None, "", "unknown", "fr", "bengali"):
            self.assertFalse(language_matches("en", language))
        self.assertTrue(language_matches("EN", "en-US"))
        self.assertTrue(language_matches("en", "en_GB"))

    def test_parsing_wrappers_spacing_and_multiline(self):
        match = parse_book_match('Here is the match:\n**Harry Potter BY J.K. Rowling [EN]**')
        self.assertEqual((match.title, match.author, match.language), ("Harry Potter", "J.K. Rowling", "en"))
        self.assertIsNone(parse_book_match("UNKNOWN"))
        self.assertEqual(parse_book_match("Unknown Pleasures by Some Author [en]").title, "Unknown Pleasures")

    def test_invalid_output_not_treated_as_unknown_or_english(self):
        for value in (None, "", "Some title", "Title by Author", "Title by Author [invalid]"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_book_match(value)

    def test_cover_fallback_https_and_missing(self):
        self.assertEqual(cover_url({"imageLinks": {"smallThumbnail": "http://books.google.com/cover"}}), "https://books.google.com/cover")
        self.assertEqual(cover_url({}), "")
        self.assertEqual(cover_url({"imageLinks": None}), "")
        self.assertEqual(cover_url({"imageLinks": {"thumbnail": "javascript:bad", "medium": "https://books.google.com/m"}}), "https://books.google.com/m")


class SearchTests(unittest.TestCase):
    @patch("book_search.google_books_request")
    def test_precise_success_skips_fallback(self, request):
        request.return_value = [book()]
        result = fetch_verified_books("Harry Potter", "J.K. Rowling", "en", "test-key")
        self.assertEqual(len(result.items), 1)
        self.assertEqual(request.call_count, 1)

    @patch("book_search.google_books_request")
    def test_empty_precise_search_tries_broader_query(self, request):
        request.side_effect = [[], [book()]]
        result = fetch_verified_books("Harry Potter", "J.K. Rowling", "en", "test-key")
        self.assertEqual(len(result.items), 1)
        self.assertEqual(request.call_args.args[0], "Harry Potter J.K. Rowling")

    @patch("book_search.google_books_request")
    def test_rejected_results_also_trigger_fallback(self, request):
        for rejected in (book(author="Other Author"), book(language="fr"), book(language=None)):
            with self.subTest(rejected=rejected):
                request.side_effect = [[rejected], [book("two")]]
                result = fetch_verified_books("Harry Potter", "J.K. Rowling", "en", "test-key")
                self.assertEqual([item["id"] for item in result.items], ["two"])

    @patch("book_search.google_books_request")
    def test_empty_and_rejected_results_have_distinct_counts(self, request):
        for items, expected_counts in (([], (0, 0)), ([book(author="Other")], (1, 0)), ([book(language="fr")], (1, 1))):
            request.side_effect = [items, items]
            result = fetch_verified_books("Harry Potter", "J.K. Rowling", "en", "test-key")
            self.assertEqual((result.retrieved, result.author_matches), expected_counts)
            self.assertFalse(result.items)


class RequestTests(unittest.TestCase):
    @patch("book_search.requests.get")
    def test_request_parameters_and_empty_success(self, get):
        response = Mock(status_code=200)
        response.json.return_value = {"totalItems": 0}
        get.return_value = response
        self.assertEqual(google_books_request("a & b", "en-US", "test-key"), [])
        self.assertEqual(get.call_args.kwargs["params"]["q"], "a & b")
        self.assertEqual(get.call_args.kwargs["params"]["langRestrict"], "en")

    @patch("book_search.requests.get")
    def test_http_failures_are_distinct_and_do_not_leak_key(self, get):
        for status, payload, text in (
            (400, {"error": {}}, "rejected"),
            (401, {"error": {}}, "rejected"),
            (403, {"error": {}}, "rejected"),
            (429, {"error": {}}, "quota"),
            (403, {"error": {"errors": [{"reason": "dailyLimitExceeded"}]}}, "quota"),
            (503, {}, "unavailable"),
        ):
            with self.subTest(status=status, payload=payload):
                response = Mock(status_code=status)
                response.json.return_value = payload
                response.raise_for_status.side_effect = requests.HTTPError("url?key=private-key")
                get.return_value = response
                with self.assertRaises(BooksServiceError) as caught:
                    google_books_request("Title", "en", "private-key")
                self.assertIn(text, str(caught.exception))
                self.assertNotIn("private-key", str(caught.exception))

    @patch("book_search.requests.get")
    def test_timeout_and_connection_failure_are_safe(self, get):
        for error, text in ((requests.Timeout("private-key"), "timed out"), (requests.ConnectionError("private-key"), "unavailable")):
            get.side_effect = error
            with self.assertRaises(BooksServiceError) as caught:
                google_books_request("Title", "en", "private-key")
            self.assertIn(text, str(caught.exception))
            self.assertNotIn("private-key", str(caught.exception))

    @patch("book_search.requests.get")
    def test_invalid_json_and_payload_are_not_empty_results(self, get):
        for payload in (None, [], {"items": None}, {"items": ["bad"]}):
            response = Mock(status_code=200)
            response.json.return_value = payload
            get.return_value = response
            with self.assertRaises(BooksServiceError):
                google_books_request("Title", "en", "test-key")
        response.json.side_effect = ValueError("invalid json")
        with self.assertRaises(BooksServiceError):
            google_books_request("Title", "en", "test-key")


if __name__ == "__main__":
    unittest.main()
