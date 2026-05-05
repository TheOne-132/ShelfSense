import streamlit as st
from google import genai
import requests
import time

# --- 1. CONFIGURATION ---
try:
    GEMINI_KEY = st.secrets["GEMINI_KEY"]
    BOOKS_KEY = st.secrets["BOOKS_KEY"]
except KeyError:
    st.error("Secrets not found! Ensure .streamlit/secrets.toml exists.")
    st.stop()

@st.cache_resource
def get_client():
    return genai.Client(api_key=GEMINI_KEY)

client = get_client()

# --- 2. UI SETUP ---
st.set_page_config(page_title="ShelfSense Ultra", page_icon="📚", layout="centered")
st.title("📚 ShelfSense Ultra")
st.write("Precision Global Engine • v9.0 (Stable)")

# --- 3. PRECISION SEARCH LOGIC ---
@st.cache_data(show_spinner=False)
def fetch_library(search_query, lang_code="en"):
    try:
        # CLEANING: Strip apostrophes to prevent API field mismatches
        clean_query = search_query.replace("'", "").replace("’", "")
        title, author = clean_query.split(" by ")
        query = f'intitle:"{title}"+inauthor:"{author}"'
        
        # MANDATORY langRestrict added to the base URL
        # Increased maxResults to 10 to give the local filter more to work with
        url = (
            f"https://www.googleapis.com/books/v1/volumes?q={query}"
            f"&printType=books&maxResults=10&langRestrict={lang_code}&key={BOOKS_KEY}"
        )
        
        res = requests.get(url, timeout=5).json()
        return res.get("items", []), author 
    except:
        url = f"https://www.googleapis.com/books/v1/volumes?q={search_query}&printType=books&maxResults=10&langRestrict={lang_code}&key={BOOKS_KEY}"
        res = requests.get(url, timeout=5).json()
        return res.get("items", []), ""

# --- 4. THE APP FLOW ---
query = st.text_input("Describe a book, plot, or character:", placeholder="e.g. A book about a boy with a lightning scar")

if query:
    with st.spinner("AI is verifying language and records..."):
        try:
            time.sleep(1) 
            
            prompt = (
                f"User Description: {query}. "
                "Task: Identify the book. "
                "1. If the user writes in English, the language is 'en'. "
                "2. Format result exactly as: 'Title by Author [lang_code]'. "
                "Example: 'Harry Potter and the Sorcerer's Stone by J.K. Rowling [en]'. "
                "3. If unsure of book, return 'UNKNOWN'."
            )
            
            response = client.models.generate_content(
                model="gemini-2.5-flash-lite", 
                contents=prompt
            )
            
            raw_output = response.text.strip().split('\n')[-1]
            
            if "UNKNOWN" in raw_output.upper():
                st.warning("🧐 No definitive match found.")
            else:
                lang_code = "en"
                if "[" in raw_output and "]" in raw_output:
                    lang_code = raw_output.split("[")[-1].split("]")[0]
                    identified_item = raw_output.split(" [")[0].replace("&", "and")
                else:
                    identified_item = raw_output.replace("&", "and")

                st.success(f"Discovered: {identified_item} (Target: {lang_code.upper()})")

                # LIBRARY FETCH
                items, expected_author = fetch_library(identified_item, lang_code)
                
                if items:
                    displayed_count = 0
                    for item in items:
                        vol = item.get("volumeInfo", {})
                        actual_authors = vol.get("authors", ["Unknown"])
                        api_lang = vol.get('language', '??').lower()
                        
                        # GATE 1: Author Verification
                        if expected_author and not any(expected_author.lower() in a.lower() for a in actual_authors):
                            continue
                        
                        # GATE 2: Flexible Language Match (allows 'en-US' for 'en')
                        if lang_code.lower() not in api_lang:
                            continue

                        displayed_count += 1
                        with st.container(border=True):
                            col1, col2 = st.columns([1, 2])
                            with col1:
                                cover = vol.get("imageLinks", {}).get("thumbnail", "").replace("http://", "https://")
                                if cover: st.image(cover, use_container_width=True)
                            with col2:
                                st.subheader(vol.get("title", "Unknown Title"))
                                st.write(f"**Author:** {', '.join(actual_authors)}")
                                st.write(f"**API Language:** {api_lang.upper()}")
                                with st.expander("Details"):
                                    st.write(vol.get("description", "No summary available."))
                    
                    if displayed_count == 0:
                        st.info(f"Verified match found, but no '{lang_code.upper()}' edition is currently indexed.")
                else:
                    st.info("No library record matches this specific language/author combination.")
                
        except Exception as e:
            st.error(f"Error: {e}")

# --- FOOTER ---
st.divider()
st.caption("ShelfSense Ultra | Powered by Gemini 2.5 & Google Books API")