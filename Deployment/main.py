from fastapi import FastAPI
from pydantic import BaseModel
import joblib
import re
import pandas as pd

app = FastAPI()

tfidf = joblib.load(r'D:\Computer science\python lib\project\CyberShield-Threat Detector\model\tfidf_vectorizer.pkl')
email_model = joblib.load(r'D:\Computer science\python lib\project\CyberShield-Threat Detector\model\email_model.pkl')
url_model = joblib.load(r'D:\Computer science\python lib\project\CyberShield-Threat Detector\model\url_model.pkl')

class EmailInput(BaseModel):
    email_text:str

class URLInput(BaseModel):
    link:str


def extract_url_feature(url):
    features = {}

    features['url_length'] = len(url)
    features['hyphen_count'] = url.count('-')
    features['dot_count'] = url.count('.')
    features['slash_count'] = url.count('/')
    features['special_char_count'] = len(re.findall(r'[@?=&%]',url))

    features['has_https'] = int(url.startswith('https'))
    features['has_at'] = int('@' in url)
    features['has_double_slash'] = int('//' in url)

    domain_only = re.sub(r'https?//','',url).split('/')[0]

    features['subdomain_count'] = domain_only.count(".")

    if '?' in url:
        features['query_length'] = len(url.split('?',1)[1])


    else:
        features['query_length'] = 0


    path_match = re.search(r'^https?://[^/]+(/[^?]*)',url)

    if path_match:
        features['path_length'] = len(path_match.group(1))
    else:
        features['path_length'] = 0

    keyword_pattern = r'login|verify|secure|bank|paypal|update|account|signin'

    features['phishing_keyword'] = int(
        bool(re.search(keyword_pattern,url,re.IGNORECASE))
    )

    ip_pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'

    features['has_ip'] = int(bool(re.search(ip_pattern,url)))

    feature_columns = [
    "url_length",
    "hyphen_count",
    "dot_count",
    "slash_count",
    "special_char_count",
    "has_https",
    "has_at",
    "has_double_slash",
    "subdomain_count",
    "query_length",
    "path_length",
    "phishing_keyword",
    "has_ip"
]

    return pd.DataFrame([features])[feature_columns]


@app.post('/scan-email')
def check_email_logic(request: EmailInput):
    text = request.email_text
    vectorized_data = tfidf.transform([text])

    proba = email_model.predict_proba(vectorized_data)[0][1]
    prediction = 'phishing' if proba >= 0.3 else'safe'

    return {'status': prediction,'confidence':f'{proba * 100}%'}

@app.post("/scan-url")
def check_url(request: URLInput):

    link = request.link

    features = extract_url_feature(link)

    prediction = url_model.predict(features)[0]

    return {
        "status": str(prediction),
        "url": link
    }
