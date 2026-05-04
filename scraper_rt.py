"""Rotten Tomatoes review scraper using internal API."""

import html
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup

from models import MovieResult, MovieInfo, ReviewData, SeasonInfo


class RTScraper:
    BASE_URL = "https://www.rottentomatoes.com"
    # The internal RT review API (discovered by inspecting the `reviews.js`
    # bundle): movies live at one path, TV seasons at another, TV episodes at
    # a third. Show-level (`tvSeries`) endpoints don't exist — TV reviews on
    # RT are always per-season.
    REVIEW_API_MOVIE = "/napi/rtcf/v1/movies/{ems_id}/reviews"
    REVIEW_API_SEASON = "/napi/rtcf/v1/tv/seasons/{ems_id}/reviews"

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
        # Try a few candidate pages in order: the basic /reviews page works for
        # both movies and TV shows. The "?type=user" suffix only works for
        # movies — TV shows use "?type=verified_audience" and 404 on "type=user".
        # Falling back to the main title page is safe because the emsId is also
        # embedded in scripts like `mediaScorecard` there.
        base = movie_url.rstrip("/")
        candidates = [f"{base}/reviews", base]

        for url in candidates:
            try:
                resp = self.session.get(url, timeout=15)
                resp.raise_for_status()
            except requests.HTTPError:
                continue

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
        """Return the API media type based on URL pattern.

        - `season`: TV season URL (`/tv/<show>/sNN[/...]`). RT's review API only
          serves season-level reviews for TV; the show-level `tvSeries` endpoint
          returns 404.
        - `movies`: anything else (movies live under `/m/`).
        """
        if re.search(r"/tv/[^/]+/s\d+", url):
            return "season"
        return "movies"

    @staticmethod
    def _is_tv_show_url(url: str) -> bool:
        """Return True for the show root URL (`/tv/<show>` without season)."""
        return "/tv/" in url and not re.search(r"/tv/[^/]+/s\d+", url)

    # ------------------------------------------------------------------
    # Seasons (TV only)
    # ------------------------------------------------------------------

    def get_seasons(self, tv_url: str) -> list[SeasonInfo]:
        """Return the list of seasons for a TV show, sorted by season number.

        RT renders seasons inside a `<carousel-slider>` as `<tile-season
        href="/tv/<show>/sNN">` web components. We scan for those first;
        fall back to JSON-LD `containsSeason` and any anchor tag matching
        the season URL pattern.
        """
        resp = self.session.get(tv_url, timeout=15)
        resp.raise_for_status()
        html = resp.text
        soup = BeautifulSoup(html, "lxml")

        seasons: list[SeasonInfo] = []
        seen: set[int] = set()
        show_path = tv_url.split(self.BASE_URL)[-1].rstrip("/")
        season_re = re.compile(re.escape(show_path) + r"/s(\d+)/?$")

        # Primary: <tile-season href="..."> (BeautifulSoup picks up arbitrary
        # tag names just fine).
        for tile in soup.find_all("tile-season"):
            href = tile.get("href", "")
            m = season_re.search(href)
            if not m:
                continue
            num = int(m.group(1))
            if num in seen:
                continue
            seen.add(num)
            full = href if href.startswith("http") else self.BASE_URL + href
            seasons.append(SeasonInfo(
                number=num,
                name=f"Season {num}",
                url=full,
            ))

        # Fallback 1: regex over raw HTML (in case the parser drops custom
        # elements on some Python/lxml versions).
        if not seasons:
            for m in re.finditer(
                r'<tile-season[^>]+href="(' + re.escape(show_path) + r'/s(\d+))"',
                html,
            ):
                href, num_str = m.group(1), m.group(2)
                num = int(num_str)
                if num in seen:
                    continue
                seen.add(num)
                seasons.append(SeasonInfo(
                    number=num,
                    name=f"Season {num}",
                    url=self.BASE_URL + href,
                ))

        # Fallback 2: JSON-LD containsSeason
        if not seasons:
            for script in soup.select('script[type="application/ld+json"]'):
                if not script.string:
                    continue
                try:
                    data = json.loads(script.string)
                except (json.JSONDecodeError, TypeError):
                    continue
                blocks = data if isinstance(data, list) else [data]
                for block in blocks:
                    if not isinstance(block, dict):
                        continue
                    for season in block.get("containsSeason", []) or []:
                        if not isinstance(season, dict):
                            continue
                        s_url = season.get("url", "")
                        if s_url and not s_url.startswith("http"):
                            s_url = self.BASE_URL + s_url
                        s_num_raw = season.get("seasonNumber", 0)
                        try:
                            s_num = int(s_num_raw)
                        except (TypeError, ValueError):
                            mm = re.search(r"/s(\d+)", s_url or "")
                            s_num = int(mm.group(1)) if mm else 0
                        if s_num in seen:
                            continue
                        seen.add(s_num)
                        eps_raw = season.get("numberOfEpisodes", 0)
                        try:
                            eps = int(eps_raw)
                        except (TypeError, ValueError):
                            eps = 0
                        seasons.append(SeasonInfo(
                            number=s_num,
                            name=season.get("name") or f"Season {s_num}",
                            url=s_url,
                            episode_count=eps,
                        ))

        # Fallback 3: any anchor pointing at /tv/<show>/sNN
        if not seasons:
            for link in soup.select("a[href]"):
                href = link.get("href", "")
                m = season_re.search(href)
                if not m:
                    continue
                num = int(m.group(1))
                if num in seen:
                    continue
                seen.add(num)
                full = href if href.startswith("http") else self.BASE_URL + href
                seasons.append(SeasonInfo(
                    number=num,
                    name=f"Season {num}",
                    url=full,
                ))

        seasons.sort(key=lambda s: s.number)
        return seasons

    def _enrich_season(self, season: SeasonInfo) -> None:
        """Fetch a season's page once and populate ems_id, episode_count,
        tomatometer + count, popcornmeter + count.

        On a season page RT exposes TWO different emsIds:
        - `props.vanity.emsId` -> the SEASON's id (what the review API wants)
        - `props.media.emsId`  -> the SHOW's id (would 404 the review API)
        We always read vanity.emsId.
        """
        base = season.url.rstrip("/")
        # The season ROOT page is the only one with `mediaScorecard` (which
        # has the exact review counts). /reviews is lighter but lacks it.
        for url in [base, f"{base}/reviews"]:
            try:
                resp = self.session.get(url, timeout=15)
                resp.raise_for_status()
                break
            except requests.HTTPError:
                continue
        else:
            return

        html_text = resp.text
        soup = BeautifulSoup(html_text, "lxml")

        # The season's emsId lives in different scripts depending on which
        # page we landed on:
        # 1) Season root page: a dedicated `<script data-json="vanity">` with
        #    emsId at the top level.
        # 2) /reviews subpage: nested as `props.vanity.emsId` — and there are
        #    multiple "props" scripts on the page; only one contains vanity,
        #    so we must iterate them all.
        # 3) Last resort: `reviewsData.media.emsId` (may be the SHOW emsId,
        #    which 404s the review API, but better than nothing).
        vanity_script = soup.select_one('script[data-json="vanity"]')
        if vanity_script and vanity_script.string:
            try:
                data = json.loads(vanity_script.string)
                if isinstance(data, dict) and data.get("emsId"):
                    season.ems_id = data["emsId"]
            except (json.JSONDecodeError, TypeError):
                pass

        if not season.ems_id:
            for props_script in soup.select('script[data-json="props"]'):
                if not props_script.string:
                    continue
                try:
                    data = json.loads(props_script.string)
                except (json.JSONDecodeError, TypeError):
                    continue
                if isinstance(data, dict):
                    vanity = data.get("vanity") or {}
                    if vanity.get("emsId"):
                        season.ems_id = vanity["emsId"]
                        break

        if not season.ems_id:
            rd_script = soup.select_one('script[data-json="reviewsData"]')
            if rd_script and rd_script.string:
                try:
                    rd = json.loads(rd_script.string)
                    season.ems_id = rd.get("media", {}).get("emsId", "")
                except (json.JSONDecodeError, TypeError):
                    pass

        # Scores + exact review counts from mediaScorecard
        sc_script = soup.select_one('script[data-json="mediaScorecard"]')
        if sc_script and sc_script.string:
            try:
                sc = json.loads(sc_script.string)
                cs = sc.get("criticsScore", {})
                if isinstance(cs, dict):
                    score_val = cs.get("score")
                    if score_val is not None:
                        season.tomatometer = f"{score_val}%"
                    count_val = cs.get("reviewCount", cs.get("likedCount", ""))
                    if count_val:
                        season.tomatometer_num = self._parse_count(str(count_val))
                aus = sc.get("audienceScore", {})
                if isinstance(aus, dict):
                    score_val = aus.get("score")
                    if score_val is not None:
                        season.popcornmeter = f"{score_val}%"
                    # Prefer reviewCount (text reviews) over ratingCount
                    # (stars-only) — it's what the review API actually returns.
                    count_val = aus.get("reviewCount", aus.get("ratingCount", ""))
                    if count_val:
                        season.popcornmeter_num = self._parse_count(str(count_val))
            except (json.JSONDecodeError, TypeError):
                pass

        # Episode count: try JSON-LD `numberOfEpisodes`, then fall back to
        # counting `<tile-episode>` elements (one per episode card).
        for ld in soup.select('script[type="application/ld+json"]'):
            if not ld.string or season.episode_count:
                continue
            try:
                data = json.loads(ld.string)
            except (json.JSONDecodeError, TypeError):
                continue
            blocks = data if isinstance(data, list) else [data]
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                if b.get("@type") in ("TVSeason", "TVSeries"):
                    eps = b.get("numberOfEpisodes")
                    if eps:
                        try:
                            season.episode_count = int(eps)
                        except (TypeError, ValueError):
                            pass

        if not season.episode_count:
            # Distinct episode hrefs (each episode card appears as
            # <tile-episode href="/tv/<show>/sNN/eNN">). Use a set to
            # de-dupe in case RT renders the same episode in multiple
            # carousels.
            ep_hrefs = set(re.findall(
                r'<tile-episode[^>]+href="(/tv/[^"]+/s\d+/e\d+)"', html_text,
            ))
            if ep_hrefs:
                season.episode_count = len(ep_hrefs)

    def enrich_seasons(self, seasons: list[SeasonInfo], max_workers: int = 5) -> None:
        """Populate ems_id, episode_count, scores and counts in parallel."""
        if not seasons:
            return
        with ThreadPoolExecutor(max_workers=min(max_workers, len(seasons))) as ex:
            list(ex.map(self._enrich_season, seasons))

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
        seasons: list[SeasonInfo] | None = None,
        on_batch=None,
        on_progress=None,
        should_stop=None,
    ) -> list[ReviewData]:
        """
        Scrape both critic (Tomatometer) and audience (Popcornmeter) reviews.

        For movies the number of reviews per type is taken from MovieInfo. For
        TV shows the caller must pass the `seasons` list (one or more
        SeasonInfo): RT only exposes reviews at the season level, never at the
        whole-show level.

        Args:
            movie_url:    Full RT URL
            movie_info:   Pre-fetched MovieInfo (avoids re-downloading movie page)
            seasons:      For TV shows, the seasons whose reviews to scrape
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

        # TV show -> per-season scraping
        if self._is_tv_show_url(movie_url) or self._detect_media_type(movie_url) == "season":
            if not seasons:
                raise ValueError(
                    "TV shows require a list of seasons to scrape. "
                    "Use get_seasons(url) and pass the chosen ones."
                )
            return self._scrape_tv_reviews(
                seasons, title, genre,
                on_batch=on_batch,
                on_progress=on_progress,
                should_stop=should_stop,
            )

        # --- Movie path ---
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

        api_url = self.BASE_URL + self.REVIEW_API_MOVIE.format(ems_id=ems_id)

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

    def _scrape_tv_reviews(
        self,
        seasons: list[SeasonInfo],
        title: str,
        genre: str,
        on_batch=None,
        on_progress=None,
        should_stop=None,
    ) -> list[ReviewData]:
        """Scrape critic + audience reviews for one or more TV seasons."""
        # Resolve emsId for any season that wasn't enriched upfront.
        for s in seasons:
            if not s.ems_id:
                self._enrich_season(s)
            if not s.ems_id:
                raise ValueError(
                    f"Could not find EMS ID for {s.name} ({s.url}). "
                    "The page structure may have changed."
                )

        # Exact total taken from each season's mediaScorecard (populated by
        # enrich_seasons). Fallback to a generous estimate only when counts
        # are missing.
        total = sum(s.tomatometer_num + s.popcornmeter_num for s in seasons)
        if total == 0:
            total = len(seasons) * 400

        per_season_cap = 5000

        all_reviews: list[ReviewData] = []
        running = 0

        def make_on_progress(offset: int):
            def _cb(current, _total):
                if on_progress:
                    actual = offset + current
                    # Keep the displayed total in sync with reality if the
                    # API returns more than mediaScorecard advertised.
                    on_progress(actual, max(total, actual))
            return _cb

        for season in seasons:
            if should_stop and should_stop():
                break

            api_url = self.BASE_URL + self.REVIEW_API_SEASON.format(
                ems_id=season.ems_id,
            )

            season_title = f"{title} — {season.name}"

            # Critics
            critic_cap = season.tomatometer_num or per_season_cap
            critics = self._scrape_one_type(
                api_url, "critic", season_title, genre, critic_cap,
                on_batch=on_batch,
                on_progress=make_on_progress(running),
                should_stop=should_stop,
            )
            all_reviews.extend(critics)
            running += len(critics)

            if should_stop and should_stop():
                break

            # Audience
            audience_cap = season.popcornmeter_num or per_season_cap
            audience = self._scrape_one_type(
                api_url, "audience", season_title, genre, audience_cap,
                on_batch=on_batch,
                on_progress=make_on_progress(running),
                should_stop=should_stop,
            )
            all_reviews.extend(audience)
            running += len(audience)

        # Snap final progress to the actual collected count.
        if on_progress:
            on_progress(len(all_reviews), len(all_reviews))

        return all_reviews

    # ------------------------------------------------------------------

    def close(self):
        self.session.close()
