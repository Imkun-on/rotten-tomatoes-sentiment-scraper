"""Shared data models for all scrapers."""

from dataclasses import dataclass, field


@dataclass
class MovieResult:
    title: str
    year: str
    url: str
    score: str  # percentage or rating string


@dataclass
class MovieInfo:
    title: str
    year: str
    genre: str
    director: str
    producer: str
    screenwriter: str
    cast: list[str]
    runtime: str
    content_rating: str
    rating_detail: str
    original_language: str
    distributor: str
    production_co: str
    release_date_theaters: str
    release_date_streaming: str
    box_office: str
    sound_mix: str
    aspect_ratio: str
    # RT-specific
    tomatometer: str = "N/A"
    tomatometer_count: str = ""
    tomatometer_num: int = 0
    popcornmeter: str = "N/A"
    popcornmeter_count: str = ""
    popcornmeter_num: int = 0
    # IMDb-specific
    imdb_rating: str = "N/A"
    imdb_votes: str = ""
    imdb_votes_num: int = 0
    popularity: str = ""
    metascore: str = ""
    country: str = ""
    budget: str = ""
    plot: str = ""


@dataclass
class ReviewData:
    title: str
    genre: str
    author: str
    rating: str          # display: "4.5 / 5" or "9/10" or "Fresh"
    rating_value: float  # normalized 0.0-5.0 for sorting
    text: str
    date: str
    review_type: str     # e.g. "Tomatometer", "Popcornmeter", "User", "Critic"
    full_review_url: str
    # IMDb-specific (optional)
    spoiler: bool = False
    headline: str = ""
    likes: int = 0
    dislikes: int = 0
    # Sentiment analysis (populated by sentiment.py)
    sentiment_score: float = 0.0    # 1.0-5.0 (stars)
    sentiment_label: str = ""       # "Very Negative" / "Negative" / "Neutral" / "Positive" / "Very Positive"
