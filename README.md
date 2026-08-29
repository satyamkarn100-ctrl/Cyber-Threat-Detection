# 🛡️ Cyber Threat Detection

**A dual-layer phishing detection system — one model for emails, one for URLs — built with classical NLP and Machine Learning.**

## What this is

This project started as a simple question: can a phishing email or a malicious link be caught using nothing but classical ML — no LLMs, no transformers, just TF-IDF, feature engineering, and models like Logistic Regression, Random Forest, and XGBoost?

It turned into two full pipelines:

- **Email layer** — reads the text of an email and decides if it's phishing
- **URL layer** — reads the URL string itself and classifies it as benign, phishing, defacement, or malware

Both are served through a FastAPI backend, with a small HTML/JS frontend on top for actually using it.

---

## The problem that shaped this project

Training accuracy alone doesn't tell you if a model works. Early versions of both models scored well on their own held-out test sets, but real-world testing told a different story:

```
"Hi"                          → predicted PHISHING
"How are you?"                → predicted PHISHING
https://google.com            → predicted PHISHING
https://youtube.com           → predicted PHISHING
```

Digging into this became a big part of the project, and it's the reason both notebooks look the way they do — data collection, feature engineering, and even the final model choice were all shaped by chasing this gap between benchmark scores and actual behavior:

- **Short text has almost no signal.** TF-IDF on a 2-word message is a near-empty vector, and the model falls back on whatever bias it picked up from training. Short messages in the original training data skewed toward scam/spam patterns, so the model quietly learned "short = suspicious."
- **The public URL dataset didn't cover real benign URL patterns well.** Testing showed legitimate, everyday URLs getting flagged as phishing simply because nothing like them existed in the training distribution.
- **URL features were inconsistent between training and real input.** Training URLs were often bare domains without `http://`, but real-world requests always include a protocol — so features like `has_https` meant different things in training vs. inference and had to be dropped.

The fix in both cases was the same idea applied twice: collect a small, targeted, hand-built dataset aimed directly at the failure pattern, merge it with the original data, and retrain — rather than assuming more of the same public data would fix a gap that public data itself had caused.

---

## How it works

```
                            User Input
                    ┌───────────┴───────────┐
              📧 Email Text             🔗 URL String
                    │                       │
                    ▼                       ▼
          Text Cleaning Pipeline    Feature Extraction
       (stopwords, vowel filter,   (length, entropy, TLD
        base64-garbage removal)    frequency, IP check, etc.)
                    │                       │
                    ▼                       ▼
           TF-IDF Vectorizer         Trained Classifier
                    │                  (Random Forest)
                    ▼                       │
           Random Forest                    │
                    │                       │
                    ▼                       ▼
      Safe / Suspicious / Phishing   Benign / Phishing /
          + probability               Defacement / Malware
                    │                       │
                    └───────────┬───────────┘
                                 ▼
                  FastAPI  (/scan-email, /scan-url)
                                 ▼
                             Frontend
```

---

## Repository structure

```
Cyber-Threat-Detection/
├── Email-Phishing-Threat-Detector.ipynb   # Email model: EDA → cleaning → TF-IDF → training
├── URL-Phishing.ipynb                     # URL model: feature engineering → training
├── backend/                               # FastAPI app — serves both models
├── frontend/                              # HTML/CSS/JS UI for interacting with the API
├── dataset/sample_data/                   # Local sample data referenced by the notebooks
└── .gitignore
```

---

## Datasets

### Email model

Six real-world sources merged as the base training set:

| Source | What it adds |
|---|---|
| Enron | Legitimate corporate email traffic |
| CEAS 2008 | Labeled spam/ham challenge data |
| Ling | Clean academic mailing-list email |
| Nazario | Hand-verified real phishing emails |
| Nigerian Fraud | Classic advance-fee scam emails |
| SpamAssassin | General spam/ham corpus |

Combined: **~82,500 emails**, roughly balanced between safe and phishing.

**On top of that**, a self-collected dataset — [Email Threat Detection Dataset (Kaggle)](https://www.kaggle.com/datasets/satyamkarn100/email-threat-detection-dataset) — was merged in after real-world testing exposed the short-message false-positive problem above. This isn't a minor top-up: at **103,518 rows**, it's actually larger than all six public sources combined, and after merging it makes up the majority of what the final model trains on (final merged set: **186,004 emails**, ~52% safe / ~48% phishing). It was built and uploaded to Kaggle specifically to give the model exposure to short, natural, everyday messages that the public spam/phishing corpora didn't represent well.

### URL model

Base dataset: [Malicious URLs Dataset (Kaggle)](https://www.kaggle.com/datasets/sid321axn/malicious-urls-dataset) — ~640,000 URLs across four classes (benign, phishing, defacement, malware).

Same story as the email model: initial testing showed the base dataset wasn't diverse enough in its benign URL patterns, causing real legitimate sites to be misclassified. A small, manually collected set of realistic benign URLs was added and merged in before the final training run. After merging and deduplication, the working dataset is **641,172 rows**:

| Class | Count | Share |
|---|---|---|
| Benign | 428,098 | 66.8% |
| Defacement | 95,308 | 14.9% |
| Phishing | 94,106 | 14.7% |
| Malware | 23,660 | 3.7% |

---

## What the models actually learn

### Email — feature engineering

Raw text goes through a cleaning pipeline before TF-IDF ever sees it:

```
lowercase → strip URLs/emails/digits → remove stopwords
→ drop tokens under 3 characters → drop tokens with no vowels
  (catches base64/encoding garbage from raw email dumps)
```

TF-IDF is configured with `max_df=0.85` specifically to stop the model from latching onto dataset-specific noise — words like `enron` or `ect` that show up constantly in one source but say nothing about whether an email is phishing.

### URL — feature engineering

The URL string itself is treated as text and turned into structural features: length, hyphen/dot/slash counts, special character density, subdomain depth, path and query length, presence of an IP address, presence of common phishing keywords, and TLD frequency (learned from the training set, not hardcoded).

Two early features — `has_https` and `has_protocol` — were tested and dropped: the base dataset's benign URLs were mostly bare domains without a protocol, so the model associated *having* `https://` with being suspicious. Every real request comes with a protocol, so that feature was actively working against the model in production. The final feature set (saved alongside the model as `model_cols.pkl`) is: `url_length, hyphen_count, dot_count, slash_count, special_char_count, has_at, has_double_slash, subdomain_count, query_length, path_length, phishing_keyword, has_ip, tld_encoded`.

---

## Model results

### Email — Random Forest (final)

| Model | Accuracy | F1 (macro) | Notes |
|---|---|---|---|
| Naive Bayes | 92.3% | 0.92 | Fast baseline |
| Logistic Regression | 96.6% | 0.97 | Fast and light, close to RF on accuracy |
| XGBoost | 95.4% | 0.95 | Solid middle ground |
| **Random Forest (RandomizedSearchCV)** | **97.4%** | **0.97** | **Chosen** — highest accuracy of the four |

Best params: `n_estimators=200`, `min_samples_split=10`, `max_depth=None`. The deployed API doesn't use a single cutoff — it returns tiered risk: probability ≥70% is flagged high-risk phishing, 40–70% as suspicious, below that as safe, and a message with no usable TF-IDF signal at all returns `low_signal` rather than a forced guess.

### URL — Random Forest (final)

Two strong candidates came out of tuning, and the choice between them came down to something the accuracy number alone doesn't show:

| Model | Accuracy | Macro F1 | Phishing Recall |
|---|---|---|---|
| Logistic Regression | 73.2% | — | — |
| Naive Bayes | 72.0% | — | — |
| XGBoost (RandomizedSearch) | 86.9% | 0.81 | 61% |
| XGBoost (GridSearch) | **88.63%** | 0.84 | 66% |
| **Random Forest (GridSearch)** | 87.69% | 0.84 | **82%** |

XGBoost technically scored higher on raw accuracy, but Random Forest caught noticeably more actual phishing URLs — 82% recall vs. 66%. For a security tool, missing a phishing URL is worse than a slightly lower accuracy number, so Random Forest was chosen as the deployed model despite XGBoost's edge on the headline metric.

---

## Handling the gap between benchmark and reality

A model scoring well on its own test split can still fail badly on inputs that don't look like anything in that split. This project treats that as a first-class problem rather than an afterthought:

- **Targeted data collection, not blind augmentation.** Both the email and URL models had a hand-built dataset added specifically after real-world testing identified a concrete failure pattern — not a generic "add more data" pass.
- **Feature consistency (URL):** every feature computed during training is recomputed identically at inference time, using the same normalization, so the model never sees a distribution it wasn't trained on.
- **Tiered risk output (email):** rather than a binary safe/phishing label, the API returns graded confidence so a borderline case isn't forced into a false-confidence bucket.

None of this claims the models are "production-grade" in the enterprise sense. They're trained on public Kaggle datasets plus self-collected supplements, and distribution shift on genuinely novel inputs remains a real, documented limitation — not a hidden one.

---

## Tech stack

| Layer | Tools |
|---|---|
| Language | Python 3.10+ |
| NLP | NLTK, TF-IDF (scikit-learn) |
| ML | scikit-learn, XGBoost |
| Tuning | GridSearchCV, RandomizedSearchCV |
| EDA | Pandas, Matplotlib, Seaborn, WordCloud |
| URL parsing | tldextract |
| Backend | FastAPI |
| Frontend | HTML, CSS, vanilla JS |
| Model storage | joblib |

---

## Running it locally

```bash
git clone https://github.com/satyamkarn100-ctrl/Cyber-Threat-Detection.git
cd Cyber-Threat-Detection

# backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# frontend (separate terminal or just open in browser)
cd ../frontend
# open index.html directly, or serve it with e.g. VS Code Live Server
```

### API

```
POST /scan-email
{ "email_text": "..." }
→ { "status": "high_risk_phishing" | "suspicious" | "Safe" | "low_signal",
    "phishing_probability": "..." }

POST /scan-url
{ "link": "..." }
→ { "status": "Safe" | "phishing" | "defacement" | "malware", "url": "..." }
```

---

## Links

| Resource | Link |
|---|---|
| Email augmentation dataset (self-collected) | [Kaggle — Email Threat Detection Dataset](https://www.kaggle.com/datasets/satyamkarn100/email-threat-detection-dataset) |
| Email base dataset | [Kaggle — Phishing Email Dataset](https://www.kaggle.com/datasets/naserabdullahalam/phishing-email-dataset) |
| URL dataset | [Kaggle — Malicious URLs Dataset](https://www.kaggle.com/datasets/sid321axn/malicious-urls-dataset) |
| Model hub | [Hugging Face — Cyber-Threat-Detection](https://huggingface.co/Satyamkarn100/Cyber-Threat-Detection) |

---

## What's next

- Continue expanding the URL model's benign coverage to reduce reliance on the manually added supplement
- Domain-holdout validation split to check generalization beyond the current random train/test split
- Publish trained model weights and a proper model card to the Hugging Face repo above

---

## Author

**Satyam** — dataset curation, feature engineering, model training, and deployment.

---

## License

MIT — free to use, modify, and learn from.
