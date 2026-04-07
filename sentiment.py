"""Sentiment analysis for scraped reviews using a transformer model."""

import re
from typing import Callable

from models import ReviewData

# Model is loaded lazily on first use to avoid slow imports at startup.
_pipeline = None

MODEL_NAME = "nlptown/bert-base-multilingual-uncased-sentiment"
MAX_TOKENS = 512  # BERT limit

LABEL_MAP = {
    "1 star": ("Very Negative", 1.0),
    "2 stars": ("Negative", 2.0),
    "3 stars": ("Neutral", 3.0),
    "4 stars": ("Positive", 4.0),
    "5 stars": ("Very Positive", 5.0),
}


def _load_model():
    """Load the sentiment pipeline (downloads model on first run)."""
    global _pipeline
    if _pipeline is None:
        from transformers import pipeline
        _pipeline = pipeline(
            "sentiment-analysis",
            model=MODEL_NAME,
            tokenizer=MODEL_NAME,
            truncation=True,
            max_length=MAX_TOKENS,
        )
    return _pipeline


# ------------------------------------------------------------------
# Text cleaning
# ------------------------------------------------------------------

_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")

MIN_TEXT_LENGTH = 10  # skip very short / empty reviews


def clean_text(text: str) -> str:
    """Clean review text for sentiment analysis."""
    text = _HTML_TAG_RE.sub(" ", text)
    text = _URL_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


# ------------------------------------------------------------------
# Analysis
# ------------------------------------------------------------------

def analyze_one(text: str) -> tuple[float, str]:
    """Return (score 1-5, label) for a single piece of text."""
    cleaned = clean_text(text)
    if len(cleaned) < MIN_TEXT_LENGTH:
        return 0.0, ""

    pipe = _load_model()
    result = pipe(cleaned[:2000])[0]  # truncate very long texts before tokenizer
    label = result["label"]
    return LABEL_MAP.get(label, ("", 0.0))[::-1]  # -> (score, label)


def analyze_reviews(
    reviews: list[ReviewData],
    on_progress: Callable[[int, int], None] | None = None,
) -> list[ReviewData]:
    """
    Run sentiment analysis on a list of reviews, populating
    sentiment_score and sentiment_label fields in-place.

    Args:
        reviews:     List of ReviewData (modified in-place).
        on_progress: Optional callback(current, total).

    Returns:
        The same list, with sentiment fields filled in.
    """
    # Ensure model is loaded before the loop (so the progress bar
    # reflects only inference time, not download time).
    _load_model()

    total = len(reviews)
    for i, review in enumerate(reviews):
        cleaned = clean_text(review.text)
        if len(cleaned) < MIN_TEXT_LENGTH:
            review.sentiment_score = 0.0
            review.sentiment_label = "Too Short"
        else:
            score, label = analyze_one(review.text)
            review.sentiment_score = score
            review.sentiment_label = label

        if on_progress:
            on_progress(i + 1, total)

    return reviews
