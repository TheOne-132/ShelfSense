"""Book parsing and verified Google Books searches, independent of the UI."""

import re
import unicodedata
from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit

import requests

BOOKS_API_URL = "https://www.googleapis.com/books/v1/volumes"
REQUEST_TIMEOUT = 8
MAX_RESULTS = 10
DEFAULT_LANG = "en"


class BooksServiceError(Exception):
    """A safe user-facing error with no request URLs or credentials."""


@dataclass(frozen=True)
class BookMatch:
    title: str
    author: str
    language: str = DEFAULT_LANG

    @property
    def display_name(self):
        return f"{self.title} by {self.author}"


@dataclass
class SearchResult:
    items: list = field(default_factory=list)
    retrieved: int = 0
    author_matches: int = 0


def normalize_language(value):
    # Missing metadata is unknown, not implicitly English.
    lang = (value or "").strip().lower().replace("_", "-")
    return lang if re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9]{2,8})*", lang) else ""


def normalize_text(value):
    return re.sub(r"\s+", " ", (value or "").replace("&", "and")).strip()


def comparable_text(value):
    normalized = unicodedata.normalize("NFKD", normalize_text(value).casefold())
    return "".join(char for char in normalized if char.isalnum())


def parse_book_match(raw_output):
    if not raw_output or not raw_output.strip():
        raise ValueError("Empty identification")
    lines = [line.strip().strip("`\"'*") for line in raw_output.splitlines() if line.strip()]
    for output in reversed(lines):
        if output.upper().rstrip(".") == "UNKNOWN":
            return None
        match = re.fullmatch(
            r"(?P<title>.+?)\s+by\s+(?P<author>.+?)\s*\[(?P<lang>[a-zA-Z_-]+)\]",
            output, flags=re.IGNORECASE,
        )
        if match:
            language = normalize_language(match.group("lang"))
            if not language:
                raise ValueError("Invalid identification language")
            return BookMatch(
                normalize_text(match.group("title")),
                normalize_text(match.group("author")), language,
            )
    raise ValueError("Malformed identification")


def author_matches(expected_author, actual_authors):
    expected = comparable_text(expected_author)
    if not expected:
        return False
    for actual in actual_authors:
        if not actual:
            continue
        if expected == comparable_text(actual):
            return True
        # Allow initials vs full given names, never surname-only substrings.
        expected_parts = re.findall(r"[^\W_]+", normalize_text(expected_author), re.UNICODE)
        actual_parts = re.findall(r"[^\W_]+", normalize_text(actual), re.UNICODE)
        expected_parts = [comparable_text(part) for part in expected_parts]
        actual_parts = [comparable_text(part) for part in actual_parts]
        if len(expected_parts) != len(actual_parts) or len(expected_parts) < 2:
            continue
        if expected_parts[-1] != actual_parts[-1]:
            continue
        if all(
            a == b or (min(len(a), len(b)) == 1 and a[:1] == b[:1])
            for a, b in zip(expected_parts[:-1], actual_parts[:-1])
        ):
            return True
    return False


def language_matches(expected_lang, actual_lang):
    expected, actual = normalize_language(expected_lang), normalize_language(actual_lang)
    return bool(expected and actual and (actual == expected or actual.startswith(f"{expected}-")))


def google_books_request(query, lang_code, api_key):
    try:
        response = requests.get(
            BOOKS_API_URL,
            params={
                "q": query, "printType": "books", "maxResults": MAX_RESULTS,
                "langRestrict": normalize_language(lang_code).split("-")[0], "key": api_key,
            },
            timeout=REQUEST_TIMEOUT,
        )
        try:
            payload = response.json()
        except ValueError:
            payload = None
        status = response.status_code
        error = payload.get("error") if isinstance(payload, dict) else None
        if status == 429 or (isinstance(error, dict) and (
            error.get("status") == "RESOURCE_EXHAUSTED" or any(
                entry.get("reason") in {"dailyLimitExceeded", "quotaExceeded", "rateLimitExceeded", "userRateLimitExceeded"}
                for entry in (error.get("errors") or []) if isinstance(entry, dict)
            )
        )):
            raise BooksServiceError("Google Books quota or rate limit reached. Please try again later.")
        if status in {400, 401, 403}:
            raise BooksServiceError(
                "Google Books rejected the request. Check the BOOKS_KEY secret, "
                "Books API access, and key restrictions in the deployment environment."
            )
        response.raise_for_status()
        if error or not isinstance(payload, dict):
            raise BooksServiceError("Google Books returned an unreadable or unsuccessful response. Please try again later.")
        items = payload.get("items", [])
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise BooksServiceError("Google Books returned invalid book records. Please try again later.")
        return items
    except requests.Timeout:
        raise BooksServiceError("Google Books timed out. Please try again.") from None
    except requests.RequestException:
        raise BooksServiceError("Google Books is temporarily unavailable. Please try again later.") from None


def fetch_verified_books(title, author, lang_code, api_key):
    title, author = normalize_text(title), normalize_text(author)
    result = SearchResult()
    if not title or not author or not normalize_language(lang_code):
        return result
    safe_title, safe_author = title.replace('"', ''), author.replace('"', '')
    queries = [f'intitle:"{safe_title}" inauthor:"{safe_author}"', f"{title} {author}"]
    seen = set()
    for query in queries:
        for item in google_books_request(query, lang_code, api_key):
            vol = item.get("volumeInfo") or {}
            identity = item.get("id") or repr(vol)
            if identity in seen:
                continue
            seen.add(identity)
            result.retrieved += 1
            if not author_matches(author, vol.get("authors") or []):
                continue
            result.author_matches += 1
            if language_matches(lang_code, vol.get("language")):
                result.items.append(item)
        if result.items:
            break
    return result


def cover_url(volume_info):
    links = volume_info.get("imageLinks") or {}
    for size in ("thumbnail", "smallThumbnail", "small", "medium", "large", "extraLarge"):
        candidate = links.get(size)
        if not isinstance(candidate, str):
            continue
        try:
            parts = urlsplit(candidate.strip())
            if parts.scheme in {"http", "https"} and parts.hostname and not parts.username and not parts.password:
                return urlunsplit(parts._replace(scheme="https"))
        except ValueError:
            continue
    return ""
