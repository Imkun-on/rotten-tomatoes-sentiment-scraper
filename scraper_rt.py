"""Rotten Tomatoes review scraper using internal API."""

import html
import json
import re
import time

import requests
from bs4 import BeautifulSoup

from models import MovieResult, MovieInfo, ReviewData


class RTScraper:
    BASE_URL = "https://www.rottentomatoes.com"
    REVIEW_API = "/napi/rtcf/v1/{media_type}/{ems_id}/reviews"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self._initialized = False

    @staticmethod
    def _parse_count(text: str) -> int:
        """Extract number from strings like '377 Reviews' or '1,000+ Verified Ratings'."""
        if not text:
            return 0
        m = re.search(r"([\d,]+)", text.replace(",", ""))
        if m:
            return int(m.group(1))
        return 0

    def _ensure_session(self):
        """Visit RT homepage once to establish cookies."""
        if not self._initialized:
            self.session.get(self.BASE_URL, timeout=10)
            self._initialized = True

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str) -> list[MovieResult]:
        self._ensure_session()
        resp = self.session.get(
            f"{self.BASE_URL}/search",
            params={"search": query},
            timeout=15,
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        rows = soup.select('search-page-media-row[data-qa="data-row"]')

        results: list[MovieResult] = []
        for row in rows:
            link = row.select_one('a[data-qa="info-name"]')
            if not link:
                continue
            title = link.get_text(strip=True)
            url = link.get("href", "")
            if not url.startswith("http"):
                url = self.BASE_URL + url
            year = row.get("release-year", row.get("start-year", "N/A"))
            score = row.get("tomatometer-score", "N/A")
            results.append(MovieResult(title=title, year=year, url=url, score=score))

        return results

    # ------------------------------------------------------------------
    # Movie / TV info
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_duration(iso_duration: str) -> str:
        """Convert ISO 8601 duration 'PT2H28M' to '2h 28m'."""
        if not iso_duration:
            return ""
        m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", iso_duration)
        if m:
            hours = m.group(1) or ""
            mins = m.group(2) or ""
            parts = []
            if hours:
                parts.append(f"{hours}h")
            if mins:
                parts.append(f"{mins}m")
            return " ".join(parts)
        return iso_duration

    @staticmethod
    def _extract_people(data, key: str) -> str:
        """Extract comma-separated names from JSON-LD person list."""
        people = data.get(key, [])
        if isinstance(people, list):
            return ", ".join(
                p.get("name", "") for p in people
                if isinstance(p, dict) and p.get("name")
            )
        if isinstance(people, dict):
            return people.get("name", "")
        return ""

    @staticmethod
    def _parse_info_section(soup) -> dict[str, str]:
        """Parse the Movie Info section from RT HTML into a label->value dict."""
        info: dict[str, str] = {}
        # Try data-qa based structure
        items = soup.select('[data-qa="movie-info-item"], li.info-item')
        for item in items:
            label_el = item.select_one(
                '[data-qa="movie-info-item-label"], b, dt, .info-item-label'
            )
            value_el = item.select_one(
                '[data-qa="movie-info-item-value"], span, dd, .info-item-value'
            )
            if label_el and value_el:
                label = label_el.get_text(strip=True).rstrip(":").lower()
                value = html.unescape(value_el.get_text(" ", strip=True))
                info[label] = value

        # Also try drawer-media-info or similar containers
        if not info:
            for dt in soup.select("dt"):
                dd = dt.find_next_sibling("dd")
                if dd:
                    label = dt.get_text(strip=True).rstrip(":").lower()
                    value = html.unescape(dd.get_text(" ", strip=True))
                    info[label] = value

        return info

    def get_movie_info(self, url: str) -> MovieInfo:
        """Return full MovieInfo including scores for a movie or TV show."""
        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        title, genre, year = "", "", ""
        director, producer, screenwriter = "", "", ""
        cast: list[str] = []
        runtime, content_rating, rating_detail = "", "", ""
        original_language, distributor, production_co = "", "", ""
        release_theaters, release_streaming = "", ""
        box_office, sound_mix, aspect_ratio = "", "", ""

        # --- JSON-LD ---
        ld_script = soup.select_one('script[type="application/ld+json"]')
        if ld_script and ld_script.string:
            try:
                data = json.loads(ld_script.string)
                title = data.get("name", "")
                genres = data.get("genre", [])
                genre = ", ".join(genres) if isinstance(genres, list) else str(genres)
                year = str(data.get("dateCreated", ""))[:4]
                content_rating = data.get("contentRating", "")
                runtime = self._parse_duration(data.get("duration", ""))
                director = self._extract_people(data, "director")
                producer = self._extract_people(data, "producer")
                screenwriter = self._extract_people(data, "author")

                actors = data.get("actor", [])
                if isinstance(actors, list):
                    cast = [
                        a.get("name", "") for a in actors
                        if isinstance(a, dict) and a.get("name")
                    ]
            except (json.JSONDecodeError, TypeError):
                pass

        # --- HTML info section (has fields not in JSON-LD) ---
        info = self._parse_info_section(soup)

        if not director:
            director = info.get("director", info.get("directors", ""))
        if not producer:
            producer = info.get("producer", info.get("producers", ""))
        if not screenwriter:
            screenwriter = info.get("screenwriter", info.get("screenwriters",
                           info.get("writer", info.get("writers", ""))))
        if not runtime:
            runtime = info.get("runtime", "")
        if not genre:
            genre = info.get("genre", "N/A")

        distributor = info.get("distributor", info.get("distributors", ""))
        production_co = info.get("production co", info.get("production company",
                        info.get("production companies", "")))
        original_language = info.get("original language", info.get("language", ""))
        release_theaters = info.get("release date (theaters)",
                           info.get("release date", info.get("theatrical release date", "")))
        release_streaming = info.get("release date (streaming)",
                            info.get("streaming release date", ""))
        box_office = info.get("box office (gross usa)",
                    info.get("box office", info.get("box office (gross)", "")))
        sound_mix = info.get("sound mix", "")
        aspect_ratio = info.get("aspect ratio", "")

        rating_raw = info.get("rating", "")
        if rating_raw:
            rating_detail = rating_raw
            if not content_rating:
                m = re.match(r"([\w-]+)", rating_raw)
                if m:
                    content_rating = m.group(1)
        elif content_rating:
            rating_detail = content_rating

        # Fallback: HTML elements for title/genre
        if not title:
            title_el = soup.select_one('rt-text[slot="title"]')
            title = title_el.get_text(strip=True) if title_el else "Unknown"
        if not genre or genre == "N/A":
            genre_els = soup.select('rt-text[slot="metadata-genre"]')
            if genre_els:
                genre = ", ".join(g.get_text(strip=True) for g in genre_els)

        # Fallback: metadata props
        if not runtime or not content_rating:
            props = soup.select('rt-text[slot="metadata-prop"]')
            for p in props:
                txt = p.get_text(strip=True)
                if re.match(r"\d+h", txt) and not runtime:
                    runtime = txt
                elif re.match(r"(G|PG|PG-13|R|NC-17|TV-)", txt) and not content_rating:
                    content_rating = txt

        # --- Scores from mediaScorecard JSON ---
        tomatometer, tomatometer_count = "N/A", ""
        popcornmeter, popcornmeter_count = "N/A", ""

        sc_script = soup.select_one('script[data-json="mediaScorecard"]')
        if sc_script and sc_script.string:
            try:
                sc = json.loads(sc_script.string)
                # Critics score
                cs = sc.get("criticsScore", sc)
                if isinstance(cs, dict):
                    score_val = cs.get("score")
                    if score_val is not None:
                        tomatometer = f"{score_val}%"
                    count_val = cs.get("reviewCount", cs.get("likedCount", ""))
                    if count_val:
                        tomatometer_count = f"{count_val} Reviews"
                # Audience score
                aus = sc.get("audienceScore", sc)
                if isinstance(aus, dict):
                    score_val = aus.get("score")
                    if score_val is not None:
                        popcornmeter = f"{score_val}%"
                    count_val = aus.get("ratingCount", aus.get("reviewCount", ""))
                    if count_val:
                        popcornmeter_count = f"{count_val} Verified Ratings"
            except (json.JSONDecodeError, TypeError):
                pass

        # Fallback: HTML score elements
        # --- Plot / Synopsis ---
        plot = ""
        synopsis_el = soup.select_one('rt-text[slot="content"]')
        if synopsis_el:
            plot = synopsis_el.get_text(strip=True)

        if tomatometer == "N/A":
            el = soup.select_one('rt-text[slot="criticsScore"]')
            if not el:
                el = soup.select_one('rt-text[slot="critics-score"]')
            if el:
                tomatometer = el.get_text(strip=True)
        if popcornmeter == "N/A":
            el = soup.select_one('rt-text[slot="audienceScore"]')
            if not el:
                el = soup.select_one('rt-text[slot="audience-score"]')
            if el:
                popcornmeter = el.get_text(strip=True)

        return MovieInfo(
            title=title,
            year=year,
            genre=genre,
            director=director,
            producer=producer,
            screenwriter=screenwriter,
            cast=cast,
            runtime=runtime,
            content_rating=content_rating,
            rating_detail=rating_detail,
            original_language=original_language,
            distributor=distributor,
            production_co=production_co,
            release_date_theaters=release_theaters,
            release_date_streaming=release_streaming,
            box_office=box_office,
            sound_mix=sound_mix,
            aspect_ratio=aspect_ratio,
            tomatometer=tomatometer,
            tomatometer_count=tomatometer_count,
            tomatometer_num=self._parse_count(tomatometer_count),
            popcornmeter=popcornmeter,
            popcornmeter_count=popcornmeter_count,
            popcornmeter_num=self._parse_count(popcornmeter_count),
            plot=plot,
        )

    # ------------------------------------------------------------------
    # EMS ID (needed for review API)
    # ------------------------------------------------------------------

    def _get_ems_id(self, movie_url: str) -> str:
        reviews_url = movie_url.rstrip("/") + "/reviews?type=user"
        resp = self.session.get(reviews_url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        script = soup.select_one('script[data-json="reviewsData"]')
        if script and script.string:
            try:
                data = json.loads(script.string)
                ems_id = data.get("media", {}).get("emsId", "")
                if ems_id:
                    return ems_id
            except (json.JSONDecodeError, TypeError):
                pass

        # Fallback: regex search across all scripts
        for s in soup.select("script"):
            if s.string and "emsId" in s.string:
                match = re.search(r'"emsId"\s*:\s*"([^"]+)"', s.string)
                if match:
                    return match.group(1)
        return ""

    # ------------------------------------------------------------------
    # Rating helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_rating(rating_str: str) -> float:
        """Convert 'STAR_4_5' -> 4.5, 'STAR_3' -> 3.0, etc."""
        if not rating_str:
            return 0.0
        m = re.match(r"STAR_(\d+)(?:_(\d+))?", rating_str)
        if m:
            whole = int(m.group(1))
            frac = int(m.group(2)) / 10 if m.group(2) else 0.0
            return whole + frac
        return 0.0

    @staticmethod
    def _detect_media_type(url: str) -> str:
        """Return 'movies' or 'tvSeries' based on URL pattern."""
        if "/tv/" in url:
            return "tvSeries"
        return "movies"

    # ------------------------------------------------------------------
    # Review scraping
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_original_score(score_str: str) -> float:
        """Try to normalize a critic score string to 0.0-5.0 scale."""
        if not score_str:
            return 0.0
        # "9/10" style
        m = re.match(r"([\d.]+)\s*/\s*([\d.]+)", score_str)
        if m:
            num, den = float(m.group(1)), float(m.group(2))
            if den > 0:
                return round(num / den * 5, 1)
        # "A+", "B-" etc -> rough mapping
        grade_map = {
            "A+": 5.0, "A": 4.7, "A-": 4.3,
            "B+": 4.0, "B": 3.7, "B-": 3.3,
            "C+": 3.0, "C": 2.7, "C-": 2.3,
            "D+": 2.0, "D": 1.7, "D-": 1.3,
            "F": 0.5,
        }
        if score_str.strip().upper() in grade_map:
            return grade_map[score_str.strip().upper()]
        # Try plain number — assume /10 scale if > 5
        try:
            val = float(score_str)
            if val > 5:
                return round(val / 10 * 5, 1)
            return val
        except ValueError:
            return 0.0

    def _parse_critic_review(self, r: dict, title: str, genre: str) -> ReviewData:
        """Parse a single critic review from the API response."""
        sentiment = r.get("scoreSentiment", "")
        original_score = r.get("originalScore", "")

        if original_score:
            rating_display = original_score
            rating_value = self._parse_original_score(original_score)
        elif sentiment:
            rating_display = "Fresh" if sentiment == "POSITIVE" else "Rotten"
            rating_value = 0.0
        else:
            rating_display = "N/A"
            rating_value = 0.0

        critic = r.get("critic", {})
        publication = r.get("publication", {})
        author = html.unescape(critic.get("displayName", "Unknown"))
        pub_name = html.unescape(publication.get("name", ""))
        if pub_name:
            author = f"{author} ({pub_name})"

        date_str = r.get("createDate", "")
        if date_str:
            date_str = date_str[:10]

        full_url = r.get("publicationReviewUrl", "")
        if not full_url:
            vanity = critic.get("vanity", "")
            if vanity:
                full_url = f"{self.BASE_URL}/critics/{vanity}"

        return ReviewData(
            title=title,
            genre=genre,
            author=author,
            rating=rating_display,
            rating_value=rating_value,
            text=html.unescape(r.get("reviewQuote", r.get("review", "")).strip()),
            date=date_str,
            review_type="Tomatometer",
            full_review_url=full_url,
        )

    def _parse_audience_review(self, r: dict, title: str, genre: str) -> ReviewData:
        """Parse a single audience review from the API response."""
        rating_value = self._parse_rating(r.get("rating", ""))
        rating_display = f"{rating_value:.1f} / 5" if rating_value > 0 else "N/A"

        user = r.get("user", {})
        author = html.unescape(r.get("displayName", ""))
        if not author:
            author = html.unescape(user.get("displayName", user.get("fullName", "Anonymous")))

        handle = user.get("profileHandle", user.get("vanity", ""))
        full_url = f"{self.BASE_URL}/profiles/{handle}" if handle else ""

        date_str = r.get("createDate", "")
        if date_str:
            date_str = date_str[:10]

        return ReviewData(
            title=title,
            genre=genre,
            author=author,
            rating=rating_display,
            rating_value=rating_value,
            text=html.unescape(r.get("review", "").strip()),
            date=date_str,
            review_type="Popcornmeter",
            full_review_url=full_url,
        )

    def _scrape_one_type(
        self,
        api_url: str,
        api_type: str,
        title: str,
        genre: str,
        max_count: int,
        on_batch=None,
        on_progress=None,
        should_stop=None,
        progress_offset: int = 0,
        progress_total: int = 0,
    ) -> list[ReviewData]:
        """Scrape reviews of a single type (critic or audience)."""
        reviews: list[ReviewData] = []
        cursor = None

        while len(reviews) < max_count:
            if should_stop and should_stop():
                break

            params: dict = {"type": api_type}
            if cursor:
                params["after"] = cursor

            resp = self.session.get(
                api_url,
                params=params,
                headers={"Accept": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            page_info = data.get("pageInfo", {})
            review_list = data.get("reviews", [])

            if not review_list:
                break

            batch: list[ReviewData] = []
            for r in review_list:
                if len(reviews) + len(batch) >= max_count:
                    break
                if api_type == "critic":
                    batch.append(self._parse_critic_review(r, title, genre))
                else:
                    batch.append(self._parse_audience_review(r, title, genre))

            if on_batch:
                on_batch(batch)

            reviews.extend(batch)

            if on_progress:
                on_progress(progress_offset + len(reviews), progress_total)

            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")

            time.sleep(0.5)

        return reviews

    def scrape_reviews(
        self,
        movie_url: str,
        movie_info: MovieInfo | None = None,
        on_batch=None,
        on_progress=None,
        should_stop=None,
    ) -> list[ReviewData]:
        """
        Scrape both critic (Tomatometer) and audience (Popcornmeter) reviews.
        The number of reviews per type is determined by the counts in MovieInfo.

        Args:
            movie_url:    Full RT URL
            movie_info:   Pre-fetched MovieInfo (avoids re-downloading movie page)
            on_batch:     Callback(list[ReviewData]) for each page of results
            on_progress:  Callback(current_count, total)
            should_stop:  Callable() -> bool — return True to abort early

        Returns:
            list[ReviewData]
        """
        if movie_info is None:
            movie_info = self.get_movie_info(movie_url)
        title = movie_info.title
        genre = movie_info.genre

        critic_max = movie_info.tomatometer_num
        audience_max = movie_info.popcornmeter_num
        total = critic_max + audience_max

        if total == 0:
            total = 200
            critic_max = 100
            audience_max = 100

        ems_id = self._get_ems_id(movie_url)
        if not ems_id:
            raise ValueError(
                "Could not find EMS ID for this title. "
                "The page structure may have changed."
            )

        media_type = self._detect_media_type(movie_url)
        api_path = self.REVIEW_API.format(media_type=media_type, ems_id=ems_id)
        api_url = self.BASE_URL + api_path

        all_reviews: list[ReviewData] = []

        # --- Critics (Tomatometer) ---
        critics = self._scrape_one_type(
            api_url, "critic", title, genre, critic_max,
            on_batch=on_batch,
            on_progress=on_progress,
            should_stop=should_stop,
            progress_offset=0,
            progress_total=total,
        )
        all_reviews.extend(critics)

        if should_stop and should_stop():
            return all_reviews

        # --- Audience (Popcornmeter) ---
        audience = self._scrape_one_type(
            api_url, "audience", title, genre, audience_max,
            on_batch=on_batch,
            on_progress=on_progress,
            should_stop=should_stop,
            progress_offset=len(all_reviews),
            progress_total=total,
        )
        all_reviews.extend(audience)

        return all_reviews

    # ------------------------------------------------------------------

    def close(self):
        self.session.close()
