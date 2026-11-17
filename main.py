import streamlit as st
from google import genai

from book_search import BooksServiceError, cover_url, fetch_verified_books, parse_book_match

APP_TITLE = "ShelfSense Ultra"
GEMINI_MODEL = "gemini-2.5-flash"

st.set_page_config(page_title=APP_TITLE, page_icon=":books:", layout="centered")
try:
    GEMINI_KEY = st.secrets["GEMINI_KEY"].strip()
    BOOKS_KEY = st.secrets["BOOKS_KEY"].strip()
    if not GEMINI_KEY or not BOOKS_KEY:
        raise ValueError("Empty secret")
except (KeyError, ValueError, AttributeError, st.errors.StreamlitSecretNotFoundError):
    st.error(
        "Configure non-empty GEMINI_KEY and BOOKS_KEY values in "
        ".streamlit/secrets.toml locally, or in your hosted app's Secrets settings."
    )
    st.stop()


@st.cache_resource
def get_client(api_key):
    return genai.Client(api_key=api_key)


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_library(title, author, language, api_key):
    # Key participates in cache identity; correcting it cannot reuse old results.
    return fetch_verified_books(title, author, language, api_key)


@st.cache_data(show_spinner=False, ttl=3600)
def identify_book(user_query, api_key, model=GEMINI_MODEL):
    prompt = (
        f"User Description: {user_query}\n"
        "Task: Identify the single most likely real book.\n"
        "Rules:\n"
        "1. Return exactly: Title by Author [lang_code]\n"
        "2. Use ISO 639-1 language codes, such as [en], [fr], or [es].\n"
        "3. If the user writes in English, use [en].\n"
        "4. If unsure, return UNKNOWN.\n"
        "Example: Harry Potter and the Sorcerer's Stone by J.K. Rowling [en]"
    )
    response = get_client(api_key).models.generate_content(model=model, contents=prompt)
    return parse_book_match(response.text)


def render_book(item, target_lang):
    vol = item.get("volumeInfo") or {}
    authors = vol.get("authors") or ["Unknown"]
    api_lang = vol.get("language") or "unknown"
    cover = cover_url(vol)
    with st.container(border=True):
        if cover:
            col1, details = st.columns([1, 2])
            with col1:
                st.image(cover, width="stretch")
        else:
            # Keep the details without a blank cover column or an alarming label.
            details = st.container()
        with details:
            st.subheader(vol.get("title") or "Unknown Title")
            st.write(f"**Author:** {', '.join(authors)}")
            st.write(f"**API Language:** {api_lang.upper()} / target {target_lang.upper()}")
            with st.expander("Details"):
                st.write(vol.get("description") or "No summary available.")


st.title(APP_TITLE)
st.write("Precision Global Engine - v9.1")
query = st.text_input(
    "Describe a book, plot, or character:",
    placeholder="e.g. A book about a boy with a lightning scar",
).strip()

if query:
    try:
        with st.spinner("Finding your book and loading its details..."):
            match = identify_book(query, GEMINI_KEY)
            result = (
                fetch_library(match.title, match.author, match.language, BOOKS_KEY)
                if match else None
            )
        if not match:
            st.warning("No definitive match found. Try adding a plot or character detail.")
        else:
            if result.items:
                st.success(f"Library match: {match.display_name} (Target: {match.language.upper()})")
                # Prefer illustrated editions, without fetching covers individually.
                for item in sorted(
                    result.items,
                    key=lambda item: not bool(cover_url(item.get("volumeInfo") or {})),
                ):
                    render_book(item, match.language)
            elif result.retrieved == 0:
                st.info("Google Books returned no records for this title and author.")
            elif result.author_matches == 0:
                st.info("Library records were found, but none matched the identified author.")
            else:
                st.info(
                    "Records matching the author were found, but none had confirmed "
                    f"{match.language.upper()} language metadata."
                )
    except BooksServiceError as error:
        st.error(str(error))
    except ValueError:
        st.warning("The AI returned an unreadable book identification. Please try again.")
    except Exception:
        # Never display raw provider exceptions: request URLs can contain credentials.
        st.error("Book identification or display failed. Please try again later.")

st.divider()
st.caption("ShelfSense Ultra | Powered by Gemini 2.5 and Google Books API")
