# 📚 ShelfSense Ultra

ShelfSense Ultra is a precision book discovery engine designed to bridge the gap between vague human descriptions and verified literary records. Developed as a high-performance search tool, it utilizes Generative AI to decode intent and API-driven metadata validation to eliminate hallucinations.

## 🚀 Key Features

*   **Semantic Plot Analysis:** Describe a book through plot points, character traits, or settings, and let Gemini 2.5 Flash identify the most likely title.
*   **Hybrid Verification Gate:** Unlike standard LLMs, ShelfSense cross-references AI suggestions with the Google Books API to ensure only real, physical editions are displayed.
*   **Language-Aware Filtering:** Automatically detects the intended language of the query to prevent "metadata bleed" (e.g., showing Spanish editions for English queries).
*   **Author Validation:** Surgical filtering logic prevents the inclusion of teacher guides, summaries, or study aids, focusing strictly on primary texts.

## 🛠️ Tech Stack

*   **Frontend:** Streamlit
*   **AI Model:** Google Gemini 2.5 Flash
*   **Data Source:** Google Books API (v1)
*   **Security:** TOML-based Secrets Management

## 📦 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/TheOne-132/ShelfSense.git
   cd ShelfSense
   ```

2. **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3. **Configure Secrets:**
   Create a `.streamlit/secrets.toml` file and add your API keys:
   ```toml
   GEMINI_KEY = "your_gemini_api_key"
   BOOKS_KEY = "your_google_books_key"
   ```

   Keep this file private: `.streamlit/` is already excluded by `.gitignore`.
   When deploying on Streamlit Community Cloud, configure both keys in the app's
   **Settings > Secrets**. The local secrets file is not uploaded through GitHub.

4. **Run the App:**
    ```bash
    streamlit run main.py
    ```

## Search behavior and troubleshooting

Gemini identifies a candidate first; the app only reports a library match after
Google Books records pass author and language checks. If a precise search returns
no verified records, it tries a broader title-and-author search. Missing language
metadata is treated as unknown, not English.

Cover images use the available Google Books image sizes over HTTPS. Editions
with image URLs appear first. A record without an image keeps its book details
without an empty image column. No extra API requests are made to find covers.
API access/key errors, quota limits, timeouts, empty results, author mismatches,
and unconfirmed language metadata have distinct messages. Raw provider errors and
request URLs are never shown in the interface because they can contain API keys.

Identifications and search results are cached for one hour, so reruns and repeated
descriptions do not repeat both provider calls. A first-time search still needs
Gemini followed by Google Books; a broader lookup is only made if the first one
finds no verified records. Actual response time depends on those services and
the network. After changing deployment secrets,
restart the hosted app and retry the same description.

## Regression checks

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

The checks use mocked services and fake credentials; they do not call Gemini or
Google Books or consume API quota.

## 🛡️ Security
This project implements strict security protocols. API keys are managed via Streamlit Secrets and are never committed to version control, protected by a root-level `.gitignore`.

---
**Developed by ADEWALE Victor Ayodele | ©2026
