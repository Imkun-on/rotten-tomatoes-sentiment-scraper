```
    ____        __  __                ______                      __                     ____            _                  
   / __ \____  / /_/ /____  ____     /_  __/___  ____ ___  ____ _/ /_____  ___  _____   / __ \___ _   __(_)__ _      _______
  / /_/ / __ \/ __/ __/ _ \/ __ \     / / / __ \/ __ `__ \/ __ `/ __/ __ \/ _ \/ ___/  / /_/ / _ \ | / / / _ \ | /| / / ___/
 / _, _/ /_/ / /_/ /_/  __/ / / /    / / / /_/ / / / / / / /_/ / /_/ /_/ /  __(__  )  / _, _/  __/ |/ / /  __/ |/ |/ (__  ) 
/_/ |_|\____/\__/\__/\___/_/ /_/    /_/  \____/_/ /_/ /_/\__,_/\__/\____/\___/____/  /_/ |_|\___/|___/_/\___/|__/|__/____/  
```

<h1 align="center">Rotten Tomatoes Reviews Scraper & Sentiment Analyzer</h1>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Hugging%20Face-Transformers-FFD21E?logo=huggingface&logoColor=black" alt="Hugging Face">
  <img src="https://img.shields.io/badge/PyTorch-2.1+-EE4C2C?logo=pytorch&logoColor=white" alt="PyTorch">
  <img src="https://img.shields.io/badge/BeautifulSoup-4.12+-3776AB?logo=python&logoColor=white" alt="BeautifulSoup">
  <img src="https://img.shields.io/badge/Rich-13.0+-000000?logo=terminal&logoColor=white" alt="Rich">
  <img src="https://img.shields.io/badge/OpenPyXL-3.1+-217346?logo=microsoftexcel&logoColor=white" alt="OpenPyXL">
  <img src="https://img.shields.io/badge/Requests-2.31+-3776AB?logo=python&logoColor=white" alt="Requests">
  <img src="https://img.shields.io/badge/lxml-4.9+-3776AB?logo=python&logoColor=white" alt="lxml">
</p>

<p align="center">
  An interactive CLI tool that scrapes movie and TV show reviews from <b>Rotten Tomatoes</b>,<br>
  performs <b>sentiment analysis</b> using a pre-trained transformer model,<br>
  and exports results to <b>CSV</b>, <b>JSON</b>, or <b>Excel</b>.
</p>

```bash
git clone https://github.com/Imkun-on/rotten-tomatoes-sentiment-scraper.git
cd rotten-tomatoes-sentiment-scraper
pip install -r requirements.txt
python cli.py
```

---

## Table of Contents

- [Features](#features)
- [Project Architecture](#project-architecture)
- [Requirements & Installation](#requirements--installation)
- [Usage & Examples](#usage--examples)
- [How the Scraping Works](#how-the-scraping-works)
- [Rating Normalization](#rating-normalization)
- [Sentiment Analysis](#sentiment-analysis)
- [Why nlptown BERT](#why-nlptown-bert)
- [Output Columns](#output-columns)
- [License](#license)

---

## Features

- **Search movies/TV shows** on Rotten Tomatoes by name or direct URL
- **View movie details**: title, year, genre, plot, cast, director, Tomatometer, Popcornmeter, box office, and more
- **Full review scraping** of both critic (Tomatometer) and audience (Popcornmeter) reviews
- **Sentiment analysis** with an NLP transformer model (1-5 star scale)
- **Export** to CSV, JSON, or Excel (.xlsx) with styled headers
- **Real-time progress bars** for both scraping and sentiment analysis
- **Paginated review browsing** in the terminal

---

## Project Architecture

```
rotten-tomatoes-sentiment-scraper/
├── cli.py            # Interactive CLI interface (Rich)
├── scraper_rt.py     # Rotten Tomatoes scraper (requests + BeautifulSoup)
├── models.py         # Shared dataclasses (MovieInfo, ReviewData, MovieResult)
├── sentiment.py      # Sentiment analysis module (transformers + nlptown BERT)
├── requirements.txt  # Python dependencies
├── exports/          # Output folder for exported files (created automatically)
└── README.md
```

---

## Requirements & Installation

### Python

Requires **Python 3.10+**.

### Install dependencies

```bash
pip install -r requirements.txt
```

Or manually:

```bash
pip install requests beautifulsoup4 lxml rich transformers torch openpyxl
```

| Library | Version | Purpose |
|---------|---------|---------|
| `requests` | >= 2.31 | HTTP client for Rotten Tomatoes requests |
| `beautifulsoup4` | >= 4.12 | HTML parsing of RT pages |
| `lxml` | >= 4.9 | Fast HTML parser backend for BeautifulSoup |
| `rich` | >= 13.0 | CLI interface with tables, progress bars, colored panels |
| `transformers` | >= 4.36 | Hugging Face pipeline for the sentiment model |
| `torch` | >= 2.1 | Backend for the transformer model (CPU is sufficient) |
| `openpyxl` | >= 3.1 | Excel (.xlsx) file generation with styles |

### Note on PyTorch

PyTorch is used as the backend for the transformer model. The **CPU-only** version is sufficient and significantly smaller:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

This reduces the download from ~2GB (with CUDA) to ~200MB.

### First Run

On the first use of sentiment analysis, the model `nlptown/bert-base-multilingual-uncased-sentiment` is automatically downloaded from Hugging Face (~500MB). Subsequent runs load it from the local cache (`~/.cache/huggingface/`), making startup nearly instant.

---

## Usage & Examples

```bash
python cli.py
```

### Interactive Flow

1. **Choose search mode**: search by query or paste a direct URL
2. **If searching by query**: select the movie from the results list
3. **View movie info**: plot, cast, director, Tomatometer, Popcornmeter, etc.
4. **Scrape reviews**: scrapes all critic and audience reviews with a real-time progress bar
5. **Sentiment analysis** (optional): assigns a 1-5 star sentiment score to each review
6. **Browse reviews**: paginated display with original rating and sentiment score
7. **Export** (optional): save to CSV, JSON, or Excel in the `exports/` folder

---

### Example 1: Search by Query

```
Search mode
  1  →  Search by query
  2  →  Paste a Rotten Tomatoes URL
  Choose [1/2] (1): 1

──────────────────── → Search on Rotten Tomatoes ────────────────────
  Query: The Substance

                    Search Results (5)
  ┌────┬──────────────────────────────┬──────┬──────────┐
  │ #  │ Title                        │ Year │  Score   │
  ├────┼──────────────────────────────┼──────┼──────────┤
  │ 1  │ The Substance                │ 2024 │ 89       │
  │ 2  │ The Substance: Albert...     │ 2015 │ N/A      │
  │ 3  │ Substance of Fire            │ 1996 │ 50       │
  └────┴──────────────────────────────┴──────┴──────────┘

  Select a result (number) (1): 1

  ✔ Selected: The Substance (2024)

  ╭─────────────── The Substance ───────────────╮
  │  • Title:         The Substance              │
  │  • Year:          2024                       │
  │  • Genre:         Horror, Drama              │
  │  • Plot:          Have you ever dreamt of a  │
  │    better version of yourself? You, only     │
  │    better in every way...                    │
  │  • Director:      Coralie Fargeat            │
  │  • Screenwriter:  Coralie Fargeat            │
  │  • Cast:          Demi Moore, Margaret       │
  │    Qualley, Dennis Quaid...                  │
  │  • Runtime:       2h 21m                     │
  │  • Rating:        R                          │
  │  • Tomatometer:   89%  (377 Reviews)         │
  │  • Popcornmeter:  65%  (5,000+ Ratings)      │
  ╰──────────────────────────────────────────────╯

  Scrape reviews? [y/n] (y): y

────────────────────── ⚙ Scraping reviews ──────────────────────
  ⠋ Scraping  ████████████████████████████  100%  5377/5377  │ 0:04:32 → 0:00:00

  Run sentiment analysis? [y/n] (y): y

──────────────────── 🧠 Sentiment Analysis ────────────────────
  ⠋ Analyzing sentiment  ██████████████████  100%  5377/5377  │ 0:12:15 → 0:00:00

  ╔══════════════ 🧠 Sentiment Summary ══════════════╗
  ║  Avg sentiment    3.72 / 5                       ║
  ║  Analyzed         5204 / 5377                    ║
  ║    Very Positive  1823                           ║
  ║    Positive       1456                           ║
  ║    Neutral        987                            ║
  ║    Negative       614                            ║
  ║    Very Negative  324                            ║
  ╚══════════════════════════════════════════════════╝

  ╔════════════════ ✔ Summary ════════════════╗
  ║  ✔ Reviews scraped    5377               ║
  ║  Movie                The Substance      ║
  ╚══════════════════════════════════════════╝

────── Reviews 1-10 of 5377  (page 1/538) ──────

  • Peter Bradshaw (The Guardian)  [5/5]  2024-09-20  (Tomatometer)
      Sentiment: Very Positive (5.0/5)
      A grotesque and blackly hilarious body-horror satire...

  • Manohla Dargis (New York Times)  [Fresh]  2024-09-19  (Tomatometer)
      Sentiment: Positive (4.0/5)
      Fargeat has made something fierce, outrageous and...

  • Anonymous  [4.5 / 5]  2024-10-03  (Popcornmeter)
      Sentiment: Very Positive (5.0/5)
      One of the best horror films of the decade...

  next / quit (q): q

  Export reviews? [y/n] (n): y

  Export format
    1  →  CSV
    2  →  JSON
    3  →  Excel (.xlsx)
    4  →  Cancel
  Choose [1/2/3/4] (4): 3
  Filename (without extension) (The_Substance_reviews):
  ✔ Saved to exports/The_Substance_reviews.xlsx

  Search again? [y/n] (y): n

  ╭─── Bye! ───╮
  ╰────────────╯
```

---

### Example 2: Direct URL

```
Search mode
  1  →  Search by query
  2  →  Paste a Rotten Tomatoes URL
  Choose [1/2] (1): 2

  Rotten Tomatoes URL: https://www.rottentomatoes.com/m/the_substance

  ╭─────────────── The Substance ───────────────╮
  │  • Title:         The Substance              │
  │  • Year:          2024                       │
  │  • Genre:         Horror, Drama              │
  │  • Plot:          Have you ever dreamt of... │
  │  ...                                         │
  ╰──────────────────────────────────────────────╯

  Scrape reviews? [y/n] (y): y
  ...
```

> With a direct URL, the tool skips the search step and goes straight to the movie info page.

---

## How the Scraping Works

### 1. Search

The scraper sends a GET request to `https://www.rottentomatoes.com/search?search=<query>` and parses the results from the HTML page using BeautifulSoup. Each result contains the title, year, URL, and Tomatometer score.

### 2. Movie Info

From the movie page, the scraper extracts data from **three sources**:

- **JSON-LD** (`<script type="application/ld+json">`): title, genre, year, director, producer, screenwriter, cast, runtime, content rating
- **HTML "Movie Info" section**: distributor, production company, original language, release dates (theaters/streaming), box office, sound mix, aspect ratio
- **mediaScorecard JSON** (`<script data-json="mediaScorecard">`): Tomatometer and Popcornmeter scores with review counts

### 3. Review Scraping

Reviews are **not** scraped from the HTML page. Rotten Tomatoes exposes an **internal API** (undocumented):

```
GET /napi/rtcf/v1/{media_type}/{ems_id}/reviews?type={critic|audience}
```

Where:
- `media_type`: `movies` or `tvSeries` (detected from the URL)
- `ems_id`: internal movie identifier, extracted from the reviews page (`<script data-json="reviewsData">` tag)
- `type`: `critic` for Tomatometer reviews, `audience` for Popcornmeter reviews

The API returns reviews in JSON pages with **cursor-based pagination** (`pageInfo.endCursor`, `pageInfo.hasNextPage`). The scraper automatically follows all pages until exhaustion, with a **0.5-second delay** between requests to avoid rate limiting.

### 4. Review Data Format

Each review from the API contains:

**Critic reviews:**
- `scoreSentiment`: `"POSITIVE"` (Fresh) or `"NEGATIVE"` (Rotten)
- `originalScore`: the critic's original score (e.g., `"9/10"`, `"A+"`, `"3.5/4"`, or empty)
- `reviewQuote`: review text (often a quote/excerpt)
- `critic.displayName`: critic's name
- `publication.name`: publication name
- `createDate`: review date
- `publicationReviewUrl`: link to the full review

**Audience reviews:**
- `rating`: format `"STAR_X_Y"` (e.g., `"STAR_4_5"` = 4.5/5)
- `review`: full review text
- `displayName` / `user.displayName`: username
- `createDate`: date

---

## Rating Normalization

Ratings on Rotten Tomatoes come in highly heterogeneous formats. The scraper normalizes all of them to a **0.0-5.0 scale**:

| Original Format | Example | rating_value | Logic |
|----------------|---------|-------------|-------|
| Fractions | `9/10` | 4.5 | `(9/10) * 5` |
| Fractions | `3.5/4` | 4.4 | `(3.5/4) * 5` |
| Letter grades | `A+` | 5.0 | Fixed mapping: A+=5.0, A=4.7, A-=4.3, ..., F=0.5 |
| Letter grades | `B-` | 3.3 | Fixed mapping |
| Stars (audience) | `STAR_4_5` | 4.5 | Direct parsing |
| Number > 5 | `8` | 4.0 | Assumed /10 scale: `(8/10) * 5` |
| Number <= 5 | `3` | 3.0 | Used directly |
| Fresh/Rotten only | `Fresh` | 0.0 | **Not converted** — not a numeric score |
| Missing | - | 0.0 | No rating available |

### Important Note on Fresh/Rotten

When a critic does not provide a numeric score and RT only shows "Fresh" or "Rotten", the `rating_value` is left at **0.0** (not 5.0 or 1.0). This is because "Fresh" is a binary label, not a score. In these cases, the `sentiment_score` computed by the NLP model becomes the numeric reference for the actual review sentiment.

---

## Sentiment Analysis

### Pipeline

The `sentiment.py` module performs three steps on each review:

#### 1. Text Cleaning

Before analysis, the text is preprocessed:
- **HTML tag removal**: strips residual tags (`<br>`, `<b>`, etc.)
- **URL removal**: removes http://, https://, www. links
- **Whitespace normalization**: collapses multiple spaces, newlines, tabs into a single space
- **Short review skip**: reviews shorter than 10 characters are labeled as "Too Short"

**Not removed**: punctuation, stopwords, capitalization. The transformer model uses these for context understanding (e.g., "NOT good" vs "good" — removing "NOT" would change the meaning entirely).

#### 2. Model Inference

The cleaned text is passed to the `nlptown/bert-base-multilingual-uncased-sentiment` model, which returns:
- A **label**: one of `1 star`, `2 stars`, `3 stars`, `4 stars`, `5 stars`
- A **confidence score** (0.0-1.0) indicating how certain the model is about its classification

#### 3. Label Mapping

The model's output label is converted to:

| Model Output | sentiment_label | sentiment_score |
|-------------|----------------|-----------------|
| 1 star | Very Negative | 1.0 |
| 2 stars | Negative | 2.0 |
| 3 stars | Neutral | 3.0 |
| 4 stars | Positive | 4.0 |
| 5 stars | Very Positive | 5.0 |

### Lazy Loading

The model is loaded into memory only when the user chooses to run sentiment analysis. The first time it is downloaded from Hugging Face (~500MB); subsequent runs load it from the local cache (`~/.cache/huggingface/`).

---

## Why nlptown BERT

### The Model: `nlptown/bert-base-multilingual-uncased-sentiment`

This model was chosen after evaluating several alternatives:

| Model | Output | Languages | Size | Suited for Reviews |
|-------|--------|-----------|------|-------------------|
| **nlptown BERT** (chosen) | 1-5 stars | Multilingual (6 languages) | ~500MB | Yes — fine-tuned on reviews |
| cardiffnlp/twitter-roberta | 3 classes (pos/neu/neg) | English only | ~500MB | No — trained on tweets |
| cardiffnlp/xlm-roberta (multilingual) | 3 classes | ~100 languages | ~1.1GB | Partial — generic |
| siebert/sentiment-roberta-large | 2 classes (pos/neg) | English only | ~1.4GB | Partial — binary only |
| distilbert-base-uncased-finetuned-sst-2 | 2 classes | English only | ~250MB | No — too simplistic |
| DeBERTa v3 (aspect-based) | 3 classes per aspect | English only | ~1.5GB | Yes — but complex setup |
| LLM (Claude, GPT) | Any | All | Cloud API | Best quality, but expensive |

### Reasons for Our Choice

1. **1-5 Star Scale**: it is the only pre-trained model that directly outputs a 5-level scale, which maps naturally to Rotten Tomatoes' rating system. Alternatives only provide 2 or 3 classes, losing nuance.

2. **Fine-tuned on Reviews**: the model was trained on product and service reviews in 6 languages (English, Dutch, German, French, Spanish, Italian). This makes it significantly more accurate on opinionated text compared to generic models.

3. **Multilingual**: supports reviews in multiple languages, which is useful for international films where reviews may be written in different languages.

4. **Reasonable Size**: ~500MB, runs on CPU without issues. No GPU required.

5. **Simple Integration**: one line to load, one line to predict. No complex preprocessing or configuration needed.

### Known Limitations

- **Academic/critical language**: the model may struggle with critic reviews that use complex or indirect language. For example, a review that criticizes society through the film (negative tone in the text, but a positive opinion of the film) can be misclassified. A critic might write a scathing social commentary while rating the film 5/5 — the model reads the negative tone, not the positive intent.
- **Sarcasm**: like all BERT-based models, heavy sarcasm can be misinterpreted.
- **Granularity**: the 1-5 scale is discrete (not continuous). A true 3.7 gets rounded to 4 stars.

For more sophisticated analysis (sarcasm comprehension, aspect-level sentiment, score justification), the only significant upgrade would be using an LLM (Claude/GPT) via API, at the cost of higher latency and per-call pricing.

---

## Output Columns

Exported files (CSV, JSON, Excel) contain the following columns:

| Column | Type | Description |
|--------|------|-------------|
| `title` | str | Movie/TV show title |
| `genre` | str | Genre (e.g., "Action, Sci-Fi") |
| `author` | str | Review author's name (for critics, includes the publication) |
| `rating` | str | Original rating as displayed on RT (e.g., "9/10", "A+", "Fresh", "4.5 / 5") |
| `rating_value` | float | Normalized rating on a 0.0-5.0 scale (0.0 if absent or Fresh/Rotten only) |
| `sentiment_score` | float | NLP model sentiment score (1.0-5.0; 0.0 if not analyzed) |
| `sentiment_label` | str | Sentiment label: Very Negative / Negative / Neutral / Positive / Very Positive |
| `text` | str | Full review text |
| `review_type` | str | "Tomatometer" (critic) or "Popcornmeter" (audience) |
| `full_review_url` | str | URL to the full review or the author's profile |
| `date` | str | Review date (YYYY-MM-DD format) |

### Notes

- The `date` column is placed last for easier sorting in Excel.
- Excel files include styled headers (blue background, white bold text) and auto-fitted column widths.
- All exported files are saved in the `exports/` folder, which is created automatically on first export.

---

## License

This project is intended for educational and research purposes. Scraping Rotten Tomatoes is subject to their Terms of Service. The nlptown BERT model is distributed under the MIT license on Hugging Face.
