import requests
from groq import Groq
import google.generativeai as genai
import streamlit as st
from datetime import datetime, timedelta
from fpdf import FPDF
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import re
from dotenv import load_dotenv
import os

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GUARDIAN_API_KEY = os.getenv("GUARDIAN_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_APP_PASSWORD = os.getenv("SENDER_APP_PASSWORD")

client = Groq(api_key=GROQ_API_KEY)

gemini_model = None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-2.5-flash-lite")

GROQ_MODEL = "llama-3.3-70b-versatile"
FONT_PATH = "NotoSans-Regular.ttf"

CATEGORIES = {
    "Technology": "technology",
    "Sports": "sport",
    "Business & Finance": "business",
    "Politics": "politics",
    "World News": "world",
    "Science & Environment": "environment",
    "Health & Fitness": "lifeandstyle",
    "Entertainment & Culture": "culture",
}

def remove_markdown(text):
    if not text:
        return ""
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'#{1,6}\s?', '', text)
    text = re.sub(r'`(.*?)`', r'\1', text)
    return text.strip()

def call_llm(prompt):
    """Try Groq first; fall back to Gemini if Groq fails."""
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as groq_error:
        if gemini_model:
            try:
                response = gemini_model.generate_content(prompt)
                return response.text
            except Exception as gemini_error:
                return f"(AI summary unavailable. Groq error: {groq_error}. Gemini error: {gemini_error})"
        return f"(AI summary unavailable due to API limit: {groq_error})"

def get_news(category_section, keyword, date_filter):
    if date_filter == "Today":
        from_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    elif date_filter == "This Week":
        from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    else:
        from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    base_url = "https://content.guardianapis.com/search"
    params = {
        "section": category_section,
        "from-date": from_date,
        "page-size": 50,
        "order-by": "newest",
        "api-key": GUARDIAN_API_KEY,
        "show-fields": "bodyText,trailText"
    }
    if keyword:
        params["q"] = keyword

    try:
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Could not reach the news service. Please try again later. ({e})")
        return []
    except ValueError:
        st.error("Received an invalid response from the news service. Please try again later.")
        return []

    if data.get("response", {}).get("status") != "ok":
        st.error(f"Guardian API error: {data}")
        return []

    results = data.get("response", {}).get("results", [])

    articles = []
    for r in results:
        title = r.get("webTitle", "No title")
        if keyword and keyword.lower() not in title.lower():
            continue
        full_content = r.get("fields", {}).get("bodyText", "") or r.get("fields", {}).get("trailText", "")
        articles.append({
            "title": title,
            "content": full_content[:1500],
            "url": r.get("webUrl", ""),
            "publishedAt": r.get("webPublicationDate", "")
        })

    return articles

def summarize_article(title, content, language):
    if language == "English":
        prompt = f"Summarize this news article in 3 bullet points in English. Do not use any markdown formatting like ** or ##.\n\nTitle: {title}\n\nContent: {content}"
    else:
        prompt = f"You must respond ONLY in {language} language. Summarize this news article in 3 bullet points in {language}. Do not use any markdown formatting like ** or ##.\n\nTitle: {title}\n\nContent: {content}"
    return call_llm(prompt)

def get_takeaways(all_summaries, language):
    if language == "English":
        prompt = f"Based on these news summaries, give me 5 key takeaways in English. Format each takeaway as a separate line starting with '- '. Do not use any other markdown formatting like ** or ##.\n\n{all_summaries}"
    else:
        prompt = f"You must respond ONLY in {language} language. Based on these news summaries, give me 5 key takeaways in {language}. Format each takeaway as a separate line starting with '- '. Do not use any other markdown formatting like ** or ##.\n\n{all_summaries}"
    return call_llm(prompt)

def generate_pdf(topic_label, articles_data, takeaways):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(15, 15, 15)
    pdf.add_font("NotoSans", "", FONT_PATH, uni=True)
    pdf.set_font("NotoSans", "", 16)
    pdf.cell(0, 10, f"News Digest: {topic_label}", ln=True)
    pdf.set_font("NotoSans", "", 10)
    pdf.cell(0, 8, f"Generated on: {datetime.now().strftime('%Y-%m-%d')}", ln=True)
    pdf.ln(5)
    for i, (title, summary, url, date) in enumerate(articles_data):
        pdf.set_font("NotoSans", "", 12)
        pdf.multi_cell(0, 8, f"Article {i+1}: {remove_markdown(title)}")
        pdf.set_font("NotoSans", "", 9)
        pdf.cell(0, 6, f"Date: {date}", ln=True)
        pdf.set_font("NotoSans", "", 10)
        pdf.multi_cell(0, 7, remove_markdown(summary))
        pdf.set_font("NotoSans", "", 9)
        pdf.cell(0, 6, f"Source: {url[:60]}...", ln=True)
        pdf.ln(4)
    pdf.set_font("NotoSans", "", 13)
    pdf.cell(0, 10, "Key Takeaways", ln=True)
    pdf.set_font("NotoSans", "", 10)
    pdf.multi_cell(0, 7, remove_markdown(takeaways))
    return bytes(pdf.output())

def send_email(recipient_email, topic_label, articles_data, takeaways):
    try:
        pdf_data = generate_pdf(topic_label, articles_data, takeaways)
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = recipient_email
        msg['Subject'] = f"Daily News Digest: {topic_label} - {datetime.now().strftime('%Y-%m-%d')}"
        body = f"Hi,\n\nHere is your daily news digest on '{topic_label}'.\n\nKey Takeaways:\n{remove_markdown(takeaways)}\n\nFind the full digest attached as a PDF.\n\nPowered by AI News Digest Bot"
        msg.attach(MIMEText(body, 'plain'))
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(pdf_data)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename=news_digest_{topic_label}.pdf')
        msg.attach(part)
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, recipient_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        st.error(f"Email error: {e}")
        return False

st.set_page_config(page_title="AI News Digest Bot", page_icon="📰", layout="wide")
st.title("📰 AI News Digest Bot")
st.write("Pick a category and (optionally) a specific topic to get an AI-powered news summary.")

language = st.selectbox("Select Summary Language:", ["English", "Hindi", "Spanish", "French", "German"])
date_filter = st.selectbox("Select News From:", ["Today", "This Week", "This Month"])
category_label = st.selectbox("Select Category:", list(CATEGORIES.keys()))
keyword = st.text_input("Optional: narrow down with a specific topic (e.g. cricket, bitcoin, elections)", placeholder="Leave blank for general category news")

st.subheader("Email Digest")
recipient_email = st.text_input("Enter email to send digest to:", placeholder="example@gmail.com")

if st.button("Generate Digest"):
    category_section = CATEGORIES[category_label]
    topic_label = f"{category_label}" + (f" - {keyword}" if keyword else "")

    with st.spinner("Fetching and summarizing news..."):
        articles = get_news(category_section, keyword, date_filter)
        all_summaries = ""
        articles_data = []
        st.subheader(f"News Digest: {topic_label}")
        if not articles:
            st.warning("No articles found. Try a different category, keyword, or filter.")
        else:
            for i, article in enumerate(articles[:3]):
                title = article.get("title", "No title")
                content = article.get("content") or article.get("title") or "No content"
                published_at = article.get("publishedAt", "")[:10]
                url = article.get("url", "")
                summary = summarize_article(title, content, language)
                all_summaries += summary + "\n\n"
                articles_data.append((title, summary, url, published_at))
                with st.expander(f"Article {i+1}: {title} | {published_at}"):
                    st.write(summary)
                    st.markdown(f"[Read full article]({url})")
            st.subheader("Key Takeaways")
            takeaways = get_takeaways(all_summaries, language)
            st.markdown(takeaways)
            st.divider()
            pdf_data = generate_pdf(topic_label, articles_data, takeaways)
            st.download_button(
                label="Download Digest as PDF",
                data=pdf_data,
                file_name=f"news_digest_{category_section}_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf"
            )
            if recipient_email:
                with st.spinner("Sending email..."):
                    success = send_email(recipient_email, topic_label, articles_data, takeaways)
                    if success:
                        st.success(f"Digest sent to {recipient_email}!")
                    else:
                        st.error("Failed to send email. Check your credentials.")