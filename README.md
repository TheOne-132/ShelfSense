# 📚 ShelfSense Ultra

ShelfSense Ultra is a precision book discovery engine designed to bridge the gap between vague human descriptions and verified literary records. Developed as a high-performance search tool, it utilizes Generative AI to decode intent and API-driven metadata validation to eliminate hallucinations.

## 🚀 Key Features

*   **Semantic Plot Analysis:** Describe a book through plot points, character traits, or settings, and let Gemini 2.5 Flash-lite identify the most likely title.
*   **Hybrid Verification Gate:** Unlike standard LLMs, ShelfSense cross-references AI suggestions with the Google Books API to ensure only real, physical editions are displayed.
*   **Language-Aware Filtering:** Automatically detects the intended language of the query to prevent "metadata bleed" (e.g., showing Spanish editions for English queries).
*   **Author Validation:** Surgical filtering logic prevents the inclusion of teacher guides, summaries, or study aids, focusing strictly on primary texts.

## 🛠️ Tech Stack

*   **Frontend:** Streamlit
*   **AI Model:** Google Gemini 2.5 Flash-lite
*   **Data Source:** Google Books API (v1)
*   **Security:** TOML-based Secrets Management

## 📦 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/TheOne-132/ShelfSense.git](https://github.com/TheOne-132/ShelfSense.git)
   cd ShelfSense

2. **Install dependencies:**
    ```bash
    pip install -r requirements.txt

3. **Configure Secrets:**
   Create a `.streamlit/secrets.toml` file and add your API keys:
   ```toml
   GEMINI_KEY = "your_gemini_api_key"
   BOOKS_KEY = "your_google_books_key"

4. **Run the App:**
    ```bash
    streamlit run app.py

## 🛡️ Security
This project implements strict security protocols. API keys are managed via Streamlit Secrets and are never committed to version control, protected by a root-level `.gitignore`.

---
**Developed by ADEWALE Victor Ayodele | ©2026