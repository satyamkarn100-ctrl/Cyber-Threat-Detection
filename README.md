# 🛡️ Cyber Threat Detection

**A dual-layer phishing detection system — one model for emails, one for URLs — built with classical NLP and Machine Learning.**

## What this is

This project started as a simple question: can a phishing email or a malicious link be caught using nothing but classical ML — no LLMs, no transformers, just TF-IDF, feature engineering, and models like Logistic Regression, Random Forest, and XGBoost?

It turned into two full pipelines:

- **Email layer** — reads the text of an email and decides if it's phishing
- **URL layer** — reads the URL string itself and classifies it as benign, phishing, defacement, or malware

Both are served through a FastAPI backend, with a frontend on top for actually using it.

---

## The problem that shaped this project

Training accuracy alone doesn't tell you if a model works. Early on, both models scored well on their held-out test sets — 97%+ on email, ~88–94% on URLs — but real-world testing told a different story:

```
"Hi"                          → predicted PHISHING
"How are you?"                → predicted PHISHING
https://google.com            → predicted PHISHING
https://youtube.com           → predicted PHISHING
```

Digging into this became a big part of the project. A few root causes surfaced:

- **Short text has almost no signal.** TF-IDF on a 2-word message is a near-empty vector, and the model falls back on whatever bias it picked up from training. Short messages in the original training data skewed heavily toward scam/spam patterns, so the model quietly learned "short = suspicious" — and a single strongly-weighted word (like *"you"*) could swing the whole prediction on its own.
- **URL features were inconsistent between training and real input.** Training URLs were often bare domains without `http://`, but real-world requests always include a protocol — so features like `has_https` meant different things in training vs. inference and had to be dropped once the mismatch was traced.
- **80,000+ existing emails drown out a small fix.** Adding a few hundred short, natural examples on top of an 82k-row dataset barely moved the needle — the fix had to happen in the feature pipeline and the inference logic, not just in the data.

None of this was solved by throwing more data at it. The real fixes were **targeted**: making sure training-time and inference-time feature extraction actually matched, and adding a confidence-aware guard so the model doesn't trust its own prediction when there's barely any input to go on. That process — finding the mismatch, proving it, then fixing the minimum necessary thing — is most of what this repo represents.

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
                    │                  (RF / XGBoost)
                    ▼                       │
          Logistic Regression               │
                    │                       │
                    ▼                       ▼
         Safe / Phishing            Benign / Phishing /
          + confidence               Defacement / Malware
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
├── frontend/                              # UI for interacting with the API
├── dataset/sample_data/                   # Local sample data referenced by the notebooks
└── .gitignore
```

---

## Datasets

### Email model

Six real-world sources merged into one training set:

| Source | What it adds |
|---|---|
| Enron | Legitimate corporate email traffic |
| CEAS 2008 | Labeled spam/ham challenge data |
| Ling | Clean academic mailing-list email |
| Nazario | Hand-verified real phishing emails |
| Nigerian Fraud | Classic advance-fee scam emails |
| SpamAssassin | General spam/ham corpus |

After merging and deduplication: **~82,000 emails**, roughly 58% safe / 42% phishing.

**Augmentation set:** [Email Threat Detection Dataset (Kaggle)](https://www.kaggle.com/datasets/satyamkarn100/email-threat-detection-dataset) — a smaller, hand-curated set built specifically for this project after the false-positive problem above was diagnosed. It's made of short, natural conversational messages ("Hi", "How are you?", "Can you send me the notes?") alongside varied phishing examples, meant to teach the model that brevity by itself isn't a phishing signal. Uploaded to Kaggle so the fix is reproducible and the reasoning behind it is documented, not just the code.

### URL model

[Malicious URLs Dataset (Kaggle)](https://www.kaggle.com/datasets/sid321axn/malicious-urls-dataset) — **~640,000 URLs** across four classes:

| Class | Share |
|---|---|
| Benign | 66.8% |
| Defacement | 14.9% |
| Phishing | 14.7% |
| Malware | 3.7% |

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

The URL string itself is treated as text and turned into engineered features: length, hyphen/dot/slash counts, special character density, subdomain depth, path and query length, presence of an IP address, presence of common phishing keywords, and TLD frequency (learned from the training set, not hardcoded).

Two early features — `has_https` and `has_protocol` — were removed after real-world testing showed they caused more harm than good: the training data's benign URLs were mostly bare domains without a protocol, so the model associated *having* `https://` with being suspicious. Every real request comes with a protocol, so this feature was actively working against the model in production.

---

## Model results

### Email — Logistic Regression (final)

| Model | Accuracy | F1 | Notes |
|---|---|---|---|
| Naive Bayes | 97.0% | 0.97 | Fast baseline |
| Random Forest (tuned) | 98.0% | 0.98 | Best raw accuracy, but 26 min to train and heavy to deploy |
| XGBoost | 98.0% | 0.98 | Solid, GPU-trained |
| **Logistic Regression** | **98.55%** | **0.985** | **Chosen** — best accuracy-to-deployment-cost ratio |

Final config: `solver='saga'`, `C=10`, custom decision threshold of `0.3` (lowered from the default `0.5` to catch more phishing, since a missed phishing email is worse than a false alarm).

### URL — XGBoost (final)

| Model | Accuracy | Macro F1 |
|---|---|---|
| Naive Bayes | 78.0% | 0.65 |
| Logistic Regression | 83.6% | 0.71 |
| Random Forest (GridSearch) | 93.2% | 0.91 |
| **XGBoost (GridSearch)** | **94.4%** | **0.92** |

Best params: `learning_rate=0.25, max_depth=7, n_estimators=70`, trained with class-balanced sample weights to handle the 66.8% benign skew.

---

## Handling the gap between benchmark and reality

A model scoring 97%+ on its own test split can still fail badly on inputs that don't look like anything in that split. This project treats that as a first-class problem rather than an afterthought:

- **Zero/low-signal guard (email):** if a cleaned message produces almost no active TF-IDF features, the model's raw probability isn't trusted — the system defaults to a safe/conservative call instead of letting a single strong coefficient decide the outcome.
- **Feature consistency (URL):** every feature computed during training is recomputed identically at inference time, using the same normalization, so the model never sees a distribution it wasn't trained on.
- **Known-domain safeguard (URL, deployment layer):** a small list of major legitimate domains sits in front of the ML model — not as a replacement for it, but as a practical hybrid layer, the same way production systems combine simple rules with ML rather than relying on either alone.

None of this claims the models are "production-grade" in the enterprise sense. They're trained on public Kaggle/research datasets, and distribution shift on genuinely novel inputs is a real, documented limitation — not a hidden one.

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
| Frontend | see `/frontend` |
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

# frontend (separate terminal)
cd ../frontend
# see frontend/README or package.json for its own setup
```

### API

```
POST /scan-email
{ "email_text": "..." }
→ { "status": "safe" | "phishing", "confidence": "..." }

POST /scan-url
{ "link": "..." }
→ { "status": "benign" | "phishing" | "defacement" | "malware", "url": "..." }
```

---

## Links

| Resource | Link |
|---|---|
| Email augmentation dataset | [Kaggle — Email Threat Detection Dataset](https://www.kaggle.com/datasets/satyamkarn100/email-threat-detection-dataset) |
| URL training dataset | [Kaggle — Malicious URLs Dataset](https://www.kaggle.com/datasets/sid321axn/malicious-urls-dataset) |
| Model hub | [Hugging Face — Cyber-Threat-Detection](https://huggingface.co/Satyamkarn100/Cyber-Threat-Detection) |

---

## What's next

- Expand the URL model's training distribution with more short, real-world benign domains to reduce dependence on the domain safeguard layer
- Domain-holdout validation split to check generalization beyond the current random train/test split
- Publish trained model weights and a proper model card to the Hugging Face repo above

---

## Author

**Satyam** — dataset curation, feature engineering, model training, and deployment.

---

## License

MIT — free to use, modify, and learn from.
