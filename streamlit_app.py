import requests
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

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GUARDIAN_API_KEY = os.getenv("GUARDIAN_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_APP_PASSWORD = os.getenv("SENDER_APP_PASSWORD")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

FONT_PATH = "NotoSans-Regular.ttf"

def remove_markdown(text):
    if not text:
        return ""
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'#{1,6}\s?', '', text)
    text = re.sub(r'`(.*?)`', r'\1', text)
    return text.strip()

def get_news(topic, date_filter):
    if date_filter == "Today":
        from_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    elif date_filter == "This Week":
        from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    else:
        from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    url = f"https://content.guardianapis.com/search?q={topic}&from-date={from_date}&page-size=5&order-by=newest&api-key={GUARDIAN_API_KEY}&show-fields=bodyText,trailText"
    response = requests.get(url)
    data = response.json()

    if data.get("response", {}).get("status") != "ok":
        st.error(f"Guardian API error: {data}")
        return []

    results = data.get("response", {}).get("results", [])

    articles = []
    for r in results:
        content = (r.get("fields", {}).get("bodyText", "") or r.get("fields", {}).get("trailText", ""))[:1500]
        articles.append({
            "title": r.get("webTitle", "No title"),
            "content": content,
            "url": r.get("webUrl", ""),
            "publishedAt": r.get("webPublicationDate", "")
        })

    return articles

def summarize_article(title, content, language):
    if language == "English":
        prompt = f"Summarize this news article in 3 bullet points in English. Do not use any markdown formatting like ** or ##.\n\nTitle: {title}\n\nContent: {content}"
    else:
        prompt = f"You must respond ONLY in {language} language. Summarize this news article in 3 bullet points in {language}. Do not use any markdown formatting like ** or ##.\n\nTitle: {title}\n\nContent: {content}"
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"(Summary unavailable due to API limit: {e})"

def get_takeaways(all_summaries, language):
    if language == "English":
        prompt = f"Based on these news summaries, give me 5 key takeaways in English. Do not use any markdown formatting like ** or ##.\n\n{all_summaries}"
    else:
        prompt = f"You must respond ONLY in {language} language. Based on these news summaries, give me 5 key takeaways in {language}. Do not use any markdown formatting like ** or ##.\n\n{all_summaries}"
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"(Takeaways unavailable due to API limit: {e})"

def generate_pdf(topic, articles_data, takeaways):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(15, 15, 15)
    pdf.add_font("NotoSans", "", FONT_PATH, uni=True)
    pdf.set_font("NotoSans", "", 16)
    pdf.cell(0, 10, f"News Digest: {topic}", ln=True)
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

def send_email(recipient_email, topic, articles_data, takeaways):
    try:
        pdf_data = generate_pdf(topic, articles_data, takeaways)
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = recipient_email
        msg['Subject'] = f"Daily News Digest: {topic} - {datetime.now().strftime('%Y-%m-%d')}"
        body = f"Hi,\n\nHere is your daily news digest on '{topic}'.\n\nKey Takeaways:\n{remove_markdown(takeaways)}\n\nFind the full digest attached as a PDF.\n\nPowered by AI News Digest Bot"
        msg.attach(MIMEText(body, 'plain'))
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(pdf_data)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename=news_digest_{topic}.pdf')
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
st.write("Enter a topic and get an AI-powered news summary instantly.")

language = st.selectbox("Select Summary Language:", ["English", "Hindi", "Spanish", "French", "German"])
date_filter = st.selectbox("Select News From:", ["Today", "This Week", "This Month"])
topic = st.text_input("Enter a topic:", placeholder="e.g. artificial intelligence, bitcoin, cricket")

st.subheader("Email Digest")
recipient_email = st.text_input("Enter email to send digest to:", placeholder="example@gmail.com")

if st.button("Generate Digest"):
    if topic:
        with st.spinner("Fetching and summarizing news..."):
            articles = get_news(topic, date_filter)
            all_summaries = ""
            articles_data = []
            st.subheader(f"News Digest: {topic}")
            if not articles:
                st.warning("No articles found. Try a different topic or filter.")
            else:
                for i, article in enumerate(articles[:5]):
                    title = article.get("title", "No title")
                    content = article.get("content") or article.get("description") or article.get("title") or "No content"
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
                st.write(takeaways)
                st.divider()
                pdf_data = generate_pdf(topic, articles_data, takeaways)
                st.download_button(
                    label="Download Digest as PDF",
                    data=pdf_data,
                    file_name=f"news_digest_{topic}_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf"
                )
                if recipient_email:
                    with st.spinner("Sending email..."):
                        success = send_email(recipient_email, topic, articles_data, takeaways)
                        if success:
                            st.success(f"Digest sent to {recipient_email}!")
                        else:
                            st.error("Failed to send email. Check your credentials.")
    else:
        st.warning("Please enter a topic first!")