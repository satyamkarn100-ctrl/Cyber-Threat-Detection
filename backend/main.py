from fastapi import FastAPI
from pydantic import BaseModel
import joblib
import re
import pandas as pd
from urllib.parse import urlparse
import os
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MODEL PATHS

# BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# LOAD MODELS
tfidf = joblib.load(r'D:\Computer science\python lib\project\Cyber-Threat-Detection\model\tfidf_vectorizer.pkl')
email_model = joblib.load(r'D:\Computer science\python lib\project\Cyber-Threat-Detection\model\email_rf_model.pkl')
url_model = joblib.load(r'D:\Computer science\python lib\project\Cyber-Threat-Detection\model\url_model.pkl')
tld_encoded = joblib.load(r'D:\Computer science\python lib\project\Cyber-Threat-Detection\model\tld_freq.pkl')

# INPUT SCHEMAS
class EmailInput(BaseModel):
    email_text: str

class URLInput(BaseModel):
    link: str

# URL FEATURE ENGINEERING
def extract_url_feature(url):
    url = str(url)

    url_clean = re.sub(r'^https?://', '', url, flags=re.IGNORECASE)

    f = {}

    f['url_length'] = len(url_clean)
    f['hyphen_count'] = url_clean.count('-')
    f['dot_count'] = url_clean.count('.')
    f['slash_count'] = url_clean.count('/')
    f['special_char_count'] = len(re.findall(r'[@?=&%]', url_clean))

    f['has_at'] = int('@' in url_clean)
    f['has_double_slash'] = int('//' in url_clean)

    domain_only = url_clean.split('/')[0]

    f['subdomain_count'] = max(domain_only.count('.') - 1, 0)

    if '?' in url_clean:
        before_query, after_query = url_clean.split('?', 1)

        f['query_length'] = len(after_query)

        f['path_length'] = len(before_query.split('/', 1)[1]) if '/' in before_query else 0

    else:
        f['query_length'] = 0

        f['path_length'] = len(url_clean.split('/', 1)[1]) if '/' in url_clean else 0

    keyword_pattern = r'login|verify|secure|bank|paypal|update|account|signin'

    f['phishing_keyword'] = int(bool(re.search(keyword_pattern, url_clean, re.IGNORECASE)))

    ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'

    f['has_ip'] = int(bool(re.search(ip_pattern, url_clean)))

    try:
        hostname = urlparse('http://' + url_clean).hostname

        if hostname and '.' in hostname:
            tld = hostname.split('.')[-1].lower()

            f['tld_encoded'] = tld_encoded.get(tld, 0)

        else:
            f['tld_encoded'] = 0

    except Exception:
        f['tld_encoded'] = 0

    feature_columns = [
        "url_length", "hyphen_count", "dot_count", "slash_count",
        "special_char_count", "has_at", "has_double_slash",
        "subdomain_count", "query_length", "path_length",
        "phishing_keyword", "has_ip", "tld_encoded"
    ]

    return pd.DataFrame([f])[feature_columns]

# EMAIL SCANNER
@app.post("/scan-email")
def check_email_logic(request: EmailInput):

    text = request.email_text

    vectorized_data = tfidf.transform([text])

    if vectorized_data.nnz == 0:
        return {
            "status": "low_signal",
            "phishing_probability": "N/A"
        }

    proba = email_model.predict_proba(vectorized_data)[0][1]

    if proba >= 0.70:
        status = "high_risk_phishing"

    elif proba >= 0.40:
        status = "suspicious"

    else:
        status = "Safe"

    return {
        "status": status,
        "phishing_probability": f"{proba * 100:.2f}%"
    }

# URL SCANNER
@app.post('/scan-url')
def check_url(request: URLInput):

    link = request.link

    features = extract_url_feature(link)

    prediction = int(url_model.predict(features)[0])

    label_map = {
        0: "benign",
        1: "phishing",
        2: "defacement",
        3: "malware"
    }

    status = label_map.get(prediction, "unknown")

    return {
        "status": status,
        "url": link
    }
