from google import genai
from google.genai import types
import streamlit as st
import requests

# --- CONFIGURATION ---
# These are safe! They pull from your hidden secrets file.
GEMINI_KEY = st.secrets["GEMINI_KEY"]
BOOKS_KEY = st.secrets["BOOKS_KEY"]

client = genai.Client(api_key=GEMINI_KEY)

def get_live_details(isbn):
    url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}&key={BOOKS_KEY}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "items" in data:
                return data["items"][0]["volumeInfo"]
    except:
        return None
    return None

# --- UI SETUP ---
st.title("📚 ShelfSense Ultra")
st.subheader("Grounded Book Discovery Engine (2026 Edition)")
st.write("---")

user_query = st.text_input("Describe ANY book (plot, characters, or setting):", placeholder="e.g., A book about a boy in a school for wizards")

if user_query:
    with st.spinner("Searching global archives..."):
        try:
            # AI logic with Google Search grounding
            prompt = f"Identify this book: {user_query}. If it's a new 2025/2026 book, search the web. Return the result in this EXACT format: 'Title: [Name], Author: [Name], ISBN: [13-digit number]'"
            
            response = client.models.generate_content(
                model="gemini-2.0-flash", # Note: 2.0 is the current stable flash model
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                )
            )
            
            ai_output = response.text.strip()
            st.info(f"**AI Discovery:** {ai_output}")

            # Extract ISBN
            isbn = "".join(filter(str.isdigit, ai_output.split("ISBN:")[-1]))
            
            if len(isbn) >= 10:
                details = get_live_details(isbn)
                if details:
                    st.success("✅ **OFFICIAL VERIFICATION FOUND**")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Official Title:** {details.get('title')}")
                        st.write(f"**Authors:** {', '.join(details.get('authors', ['Unknown']))}")
                    with col2:
                        st.write(f"**Pages:** {details.get('pageCount', 'N/A')}")
                        st.write(f"**Publisher:** {details.get('publisher', 'N/A')}")
                    
                    st.write(f"**Summary:** {details.get('description', 'No summary available.')[:500]}...")
                else:
                    st.warning("⚠️ Identified, but not yet indexed in Google's official metadata library.")
            else:
                st.warning("⚠️ No valid ISBN found for this version yet.")
                
        except Exception as e:
            st.error(f"System Error: {e}")

st.sidebar.markdown("---")
st.sidebar.write("Developed by Adewale Victor | © 2026")