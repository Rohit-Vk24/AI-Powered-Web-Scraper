import requests
import json
import asyncio
import re
import nest_asyncio
from urllib.parse import urlparse
from flask import Flask, request, render_template, session, jsonify
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler

nest_asyncio.apply()

app = Flask(__name__)
app.secret_key = "supersecretkey" 

# -----------------------------
# OpenRouter API Configuration
# -----------------------------
OPENROUTER_API_KEY = "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"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# -----------------------------
# Data Cleaning / Formatting
# -----------------------------

def format_response(text):
    """
    Cleans and formats the AI response to make it more readable.
    """
    if not text:
        return "No response received."

   
    text = re.sub(r'\n+', '\n', text.strip())

    
    text = re.sub(r'(?m)^\d+\.\s+', '• ', text)  
    text = re.sub(r'(?m)^-\s+', '• ', text)      

    
    text = text.replace("\n", "\n\n")

    return text

def clean_and_format_text(html):
    """
    Extracts, cleans, and formats text into structured sections.
    Removes scripts, styles, images, and URLs. Uppercases headings.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "img"]):
        tag.decompose()

    formatted_text = []
    for element in soup.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
        text = element.get_text(strip=True)
        text = re.sub(r"\s+", " ", text)            
        text = re.sub(r"[^\x20-\x7E]", "", text)      
        text = re.sub(r"\b(?:http|https)://\S+\b", "", text)  

        if text:
            if element.name.startswith("h"):
                formatted_text.append(f"\n{text.upper()}\n" + "=" * len(text))
            else:
                formatted_text.append(text)

    return "\n\n".join(formatted_text)

# -----------------------------
# Async Web Scraping
# -----------------------------
async def scrape_url(url):
    try:
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url)
            raw_html = result.html
            return clean_and_format_text(raw_html)
    except Exception as e:
        return f"Error scraping {url}: {e}"

async def scrape_multiple_urls(urls):
    tasks = [scrape_url(u) for u in urls]
    results = await asyncio.gather(*tasks)
    return dict(zip(urls, results))

def get_domain(url: str) -> str:
    """Extract the domain name from a full URL."""
    parsed = urlparse(url)
    return parsed.netloc or url

# -----------------------------
# Query OpenRouter API
# -----------------------------
def query_openrouter(context, conversation):
    """
    Sends the conversation (including scraped context) to OpenRouter’s API
    and returns a neatly formatted response only if a valid response is received.
    """
    messages = [
        {
            "role": "system",
            "content": (
                "You are an AI that has the following context from the scraped data:\n"
                f"{context}\n\n"
                "You must answer the user's questions using only the above context. "
                "If the answer is not in the context, say 'I don't know.'"
            )
        }
    ]
    messages.extend(conversation)

    payload = {
        "model": "deepseek/deepseek-r1:free",
        "messages": messages
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload)

    if response.status_code == 200:
        data = response.json()
        try:
            raw_response = data["choices"][0]["message"]["content"]

            
            if raw_response and raw_response.strip():
                return format_response(raw_response)
            else:
                return "Received an empty response from the model."
        except (KeyError, IndexError):
            return "[Error parsing response]"
    else:
        return f"Error {response.status_code}: {response.text}"



# -----------------------------
# Flask Routes
# -----------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    """
    Main interface:
      1) Scrape URLs from user input.
      2) Provide a chat interface that uses AJAX to call /ask.
    """
    if "scraped_data" not in session:
        session["scraped_data"] = {}  
    if "conversation" not in session:
        session["conversation"] = []  

    if request.method == "POST":
        if "urls" in request.form:
           
            session["scraped_data"] = {}
            session["conversation"] = []
            urls = [u.strip() for u in request.form["urls"].split(",") if u.strip()]
            if urls:
                results = asyncio.run(scrape_multiple_urls(urls))
                for url, text in results.items():
                    domain = get_domain(url)
                    session["scraped_data"][domain] = text


    return render_template("index.html")
    
   
@app.route("/reset", methods=["POST"])
def reset_chat():
    session["conversation"] = []
    return redirect("/")

@app.route("/ask", methods=["POST"])
def ask():
    """AJAX endpoint for handling chat queries."""
    user_msg = request.form.get("user_message", "").strip()
    if not user_msg:
        return jsonify({"assistant": "No message provided."})
    
    
    conversation = session.get("conversation", [])
    conversation.append({"role": "user", "content": user_msg})
    session["conversation"] = conversation

    
    scraped_data = session.get("scraped_data", {})
    big_context = "\n\n".join(
        f"===[{get_domain(domain)}]===\n\n{text}"
        for domain, text in scraped_data.items()
    )
    
    
    model_reply = query_openrouter(big_context, conversation)
    
    conversation.append({"role": "assistant", "content": model_reply})
    session["conversation"] = conversation

    return jsonify({"assistant": model_reply})

@app.route('/process', methods=['POST'])
def process():
    data = request.json
    url = data.get('url')
    
   
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Summarize this text: {content}"}
        ]
    )
    
    
    raw_text = response.choices[0].message['content']
    
    
    formatted_text = format_text(raw_text)
    
    return jsonify({"summary": formatted_text})

def format_text(text):
    """
    Format the text to preserve paragraph structure and line breaks
    similar to how the model would present it.
    """
    
    paragraphs = text.split('\n\n')
    
    
    formatted_paragraphs = []
    for para in paragraphs:
        
        if para.strip().startswith(('•', '-', '*')) or re.match(r'^\d+\.', para.strip()):
            
            formatted_paragraphs.append(para)
        else:
           
            sentences = re.split(r'(?<=[.!?])\s+', para)
            chunks = []
            current_chunk = ""
            
            for sentence in sentences:
                if len(current_chunk) + len(sentence) > 100:  
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = sentence
                else:
                    if current_chunk:
                        current_chunk += " " + sentence
                    else:
                        current_chunk = sentence
            
            if current_chunk:
                chunks.append(current_chunk)
            
            formatted_paragraphs.extend(chunks)
    
   
    return "\n\n".join(formatted_paragraphs)

if __name__ == "__main__":
    app.run(debug=True)
