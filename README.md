\# AI News Digest Bot



A small project I built to fetch news on any topic and get quick AI-generated summaries instead of reading full articles. It also has a "key takeaways" section and can email you a PDF digest.



Live app: https://news-digest-box-jzfepdm5zbxa7abkqnneen.streamlit.app/



\## What it does



\- Pick a category (Technology, Sports, Business, Politics, etc.)

\- Optionally narrow it down with a specific keyword (like "cricket" or "bitcoin")

\- It pulls recent, relevant articles from The Guardian's API

\- Each article gets summarized into 3 bullet points using an LLM

\- It also generates 5 overall takeaways from all the articles combined

\- You can download everything as a PDF or get it emailed to you

\- Supports English, Hindi, Spanish, French and German



\## Tech used



\- Streamlit for the UI

\- The Guardian Open Platform API for news (using their tag system for accurate topic matching)

\- Groq (Llama 3.3 70B) for summarization, with Gemini as a backup if Groq's limits are hit

\- FPDF2 for generating PDFs (with a custom font so non-English text renders properly)

\- Gmail SMTP for sending the email digest



\## Running it locally



Clone the repo and install dependencies:



git clone https://github.com/rudragupta01/news-digest-box.git

cd news-digest-box

pip install -r requirements.txt



You'll need a `.env` file with these keys:



GROQ\_API\_KEY=

GEMINI\_API\_KEY=

GUARDIAN\_API\_KEY=

SENDER\_EMAIL=

SENDER\_APP\_PASSWORD=



Then run:



streamlit run streamlit\_app.py



\## Notes



\- Guardian API keys are free, you just need to register for one

\- The Gmail app password (not your normal password) is needed for the email feature

\- Free tier API limits mean you can only generate a limited number of digests per day, that's why there's a fallback between Groq and Gemini



\## Possible improvements



\- Add more news sources

\- Schedule automatic daily digests

\- Cache results so repeated searches don't use up API calls

