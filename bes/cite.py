"""`bes cite URL`: a Markdown citation card for a YouTube video or web page.

YouTube: `yt-dlp -j` when present, else the oEmbed endpoint plus the
page's own meta tags. Other pages: <title>, author and date meta tags
(including the citation_* tags that journals and arXiv use), and JSON-LD,
read with urllib.
"""

import json
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from . import journal, tools
from .layout import CITATIONS
from .naming import clean_title

USER_AGENT = "Mozilla/5.0 (compatible; bes-cite/1.0)"
MAX_BYTES = 2_000_000
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]
MLA_MONTHS = ["Jan.", "Feb.", "Mar.", "Apr.", "May", "June", "July", "Aug.", "Sept.",
              "Oct.", "Nov.", "Dec."]
YOUTUBE = re.compile(r"^https?://(?:www\.|m\.|music\.)?(?:youtube\.com/(?:watch|shorts/|live/)|youtu\.be/)", re.I)
OPEN_Q, CLOSE_Q = "“", "”"


# Fetching --------------------------------------------------------------

def is_youtube(url):
    return bool(YOUTUBE.match(url))


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept-Language": "en-US,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read(MAX_BYTES).decode(charset, errors="replace")


def iso_day(text, utc=False):
    """A date from 2024-01-05T..., 2024/01/05, or 20240105.

    With utc=True a full timestamp is converted to its UTC date, which is
    what yt-dlp reports for YouTube uploads.
    """
    if not text:
        return None
    text = str(text).strip()
    if utc:
        try:
            when = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if when.tzinfo:
                return when.astimezone(timezone.utc).date()
        except ValueError:
            pass
    m = re.match(r"(\d{4})[-/]?(\d{2})[-/]?(\d{2})", text)
    if not m:
        return None
    try:
        return date(*map(int, m.groups()))
    except ValueError:
        return None


def iso_duration(text):
    """Seconds from an ISO 8601 duration like PT1H2M3S."""
    m = re.match(r"P(?:\d+D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", str(text or ""))
    if not m or not any(m.groups()):
        return None
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


class MetaReader(HTMLParser):
    """Collects every <meta> value (repeated keys kept in order), <title> and JSON-LD."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta = {}
        self.title = ""
        self.in_title = False
        self.in_ld = False
        self.ld = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta":
            key = (a.get("property") or a.get("name") or a.get("itemprop") or "").lower()
            if key and a.get("content", "").strip():
                self.meta.setdefault(key, []).append(a["content"].strip())
        elif tag == "title" and not self.title:
            self.in_title = True
        elif tag == "script" and "ld+json" in a.get("type", ""):
            self.in_ld = True
            self.ld.append("")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        elif tag == "script":
            self.in_ld = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif self.in_ld:
            self.ld[-1] += data

    def first(self, *keys):
        for k in keys:
            if self.meta.get(k):
                return self.meta[k][0]
        return None


def ld_objects(blobs):
    out = []
    for blob in blobs:
        try:
            data = json.loads(blob)
        except ValueError:
            continue
        stack = [data]
        while stack:
            item = stack.pop()
            if isinstance(item, list):
                stack.extend(reversed(item))
            elif isinstance(item, dict):
                out.append(item)
                if "@graph" in item:
                    stack.append(item["@graph"])
    return out


def ld_authors(obj):
    found = obj.get("author") or []
    if not isinstance(found, list):
        found = [found]
    names = []
    for a in found:
        name = a.get("name") if isinstance(a, dict) else a
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return names


def tidy_author(name):
    name = re.sub(r"(?i)^by\s+", "", " ".join(name.split()))
    return "" if name.startswith("http") else name  # article:author is sometimes a profile URL


def page_meta(html_text, url):
    r = MetaReader()
    r.feed(html_text)
    ld = ld_objects(r.ld)
    title = (r.first("citation_title", "og:title", "twitter:title")
             or " ".join(r.title.split()))
    authors = r.meta.get("citation_author") or r.meta.get("dc.creator") or []
    if not authors:
        single = r.first("author", "article:author", "parsely-author", "sailthru.author")
        authors = [single] if single else []
    for obj in ld:
        authors = authors or ld_authors(obj)
    published = r.first("citation_publication_date", "citation_date", "citation_online_date",
                        "article:published_time", "datepublished", "uploaddate",
                        "dc.date.issued", "dc.date", "prism.publicationdate", "date",
                        "pubdate", "sailthru.date")
    for obj in ld:
        published = published or obj.get("datePublished") or obj.get("uploadDate")
    host = urllib.parse.urlparse(url).hostname or ""
    site = r.first("og:site_name", "citation_journal_title") or re.sub(r"^www\.", "", host)
    return {
        "title": title.strip() or url,
        "authors": [a for a in map(tidy_author, authors) if a],
        "published": iso_day(published),
        "site": site.strip(),
        "duration": iso_duration(r.first("duration")),
    }


def youtube_meta(url):
    if tools.which("yt-dlp"):
        out = tools.run(["yt-dlp", "-j", "--no-playlist", "--skip-download", "--no-warnings", url],
                        timeout=90)
        try:
            d = json.loads(out.splitlines()[0]) if out else None
        except (ValueError, IndexError):
            d = None
        if d:
            channel = d.get("channel") or d.get("uploader")
            return {
                "title": d.get("title") or url,
                "authors": [channel] if channel else [],
                "published": iso_day(d.get("upload_date")),
                "site": "YouTube",
                "duration": d.get("duration"),
                "url": d.get("webpage_url") or url,
            }
    meta = {"title": url, "authors": [], "published": None, "site": "YouTube", "duration": None}
    try:
        api = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(url, safe="")
        o = json.loads(fetch(api))
        meta["title"] = o.get("title") or url
        meta["authors"] = [o["author_name"]] if o.get("author_name") else []
    except (OSError, ValueError):
        pass
    try:
        r = MetaReader()
        r.feed(fetch(url))
        meta["published"] = iso_day(r.first("datepublished", "uploaddate"), utc=True)
        meta["duration"] = iso_duration(r.first("duration"))
    except (OSError, ValueError):
        pass
    return meta


def lookup(url):
    if is_youtube(url):
        meta = youtube_meta(url)
        meta["type"] = "video"
    else:
        meta = page_meta(fetch(url), url)
        meta["type"] = "webpage"
    meta.setdefault("url", url)
    if isinstance(meta.get("duration"), float):
        meta["duration"] = int(meta["duration"])
    return meta


# Names -----------------------------------------------------------------

ORG_WORDS = re.compile(
    r"(?i)\b(news|inc|llc|ltd|co|corp|corporation|company|media|university|college|school|press|"
    r"tv|channel|official|organization|organisation|association|institute|foundation|society|"
    r"council|department|agency|center|centre|committee|group|museum|library|times|post|"
    r"journal|magazine|daily|network|studios?|team|staff|editors?|the)\b")


def capitalized(word):
    return word[:1].isupper() and all(c.isalpha() or c in "'.-" for c in word)


class Author:
    """One author. A person has first and last names; a channel or company does not."""

    def __init__(self, name, may_be_person=True):
        self.name = " ".join(name.split())
        self.first = self.last = None
        if not may_be_person or ORG_WORDS.search(self.name):
            return
        if "," in self.name:
            last, _, first = (p.strip() for p in self.name.partition(","))
            parts = first.split() + last.split()
            if first and last and 2 <= len(parts) <= 4 and all(map(capitalized, parts)):
                self.first, self.last = first, last
        else:
            parts = self.name.split()
            if 2 <= len(parts) <= 3 and all(map(capitalized, parts)):
                self.first, self.last = " ".join(parts[:-1]), parts[-1]

    @property
    def display(self):
        return f"{self.first} {self.last}" if self.last else self.name

    @property
    def inverted(self):
        return f"{self.last}, {self.first}" if self.last else self.name

    @property
    def apa(self):
        if not self.last:
            return self.name
        initials = " ".join(w if re.fullmatch(r"[A-Z]\.", w) else w[0] + "." for w in self.first.split())
        return f"{self.last}, {initials}"


def authors_of(meta):
    person_ok = meta.get("type") != "video"  # a YouTube channel name is never inverted
    return [Author(a, person_ok) for a in meta.get("authors", []) if a.strip()]


def apa_list(people):
    names = [p.apa for p in people]
    if len(names) == 1:
        return names[0]
    if len(names) <= 20:
        return ", ".join(names[:-1]) + ", & " + names[-1]
    return ", ".join(names[:19]) + ", . . . " + names[-1]


def mla_list(people):
    if len(people) == 1:
        return people[0].inverted
    if len(people) == 2:
        return f"{people[0].inverted}, and {people[1].display}"
    return f"{people[0].inverted}, et al"


def chicago_list(people):
    if len(people) == 1:
        return people[0].inverted
    if len(people) <= 10:
        rest = [p.display for p in people[1:]]
        return people[0].inverted + ", " + ", ".join(rest[:-1]) + (", " if rest[:-1] else "") + "and " + rest[-1]
    return people[0].inverted + ", " + ", ".join(p.display for p in people[1:7]) + ", et al"


# Formatting ------------------------------------------------------------

def clock(seconds):
    if not seconds:
        return ""
    h, rest = divmod(int(seconds), 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def end(text):
    return text if text.endswith((".", "?", "!")) else text + "."


def long_date(d):
    return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"


def mla_date(d):
    return f"{d.day} {MLA_MONTHS[d.month - 1]} {d.year}"


def citations(meta, accessed):
    """(APA 7, MLA 9, Chicago author-date) strings, with *italics* in Markdown."""
    title, site, url, pub = meta["title"], meta.get("site", ""), meta["url"], meta.get("published")
    people = authors_of(meta)
    video = meta.get("type") == "video"
    sole = people[0].name if len(people) == 1 else ""
    bare_url = re.sub(r"^https?://", "", url)

    # APA 7
    when = f"({pub.year}, {MONTHS[pub.month - 1]} {pub.day})" if pub else "(n.d.)"
    label = " [Video]" if video else ""
    site_part = f" {end(site)}" if site and site != sole else ""
    if people:
        apa = f"{end(apa_list(people))} {when}. *{title}*{label}.{site_part}"
    else:
        apa = f"*{title}*{label}. {when}.{site_part}"
    apa += f" {url}" if pub else f" Retrieved {long_date(accessed)}, from {url}"

    # MLA 9 (a YouTube channel goes after the site as "uploaded by")
    head = "" if video or not people else end(mla_list(people)) + " "
    tail = [f"*{site}*"] if site and site != sole else []
    if video and people:
        tail.append(f"uploaded by {people[0].name}")
    if pub:
        tail.append(mla_date(pub))
    tail.append(bare_url)
    mla = f"{head}{OPEN_Q}{end(title)}{CLOSE_Q} " + ", ".join(tail) + "."
    if not pub:
        mla += f" Accessed {mla_date(accessed)}."

    # Chicago author-date
    year = f"{pub.year}." if pub else "n.d."
    who = chicago_list(people) if people else (site or title)
    chi = f"{end(who)} {year} {OPEN_Q}{end(title)}{CLOSE_Q}"
    if video:
        length = clock(meta.get("duration"))
        chi += " YouTube video" + (f", {length}." if length else ".")
        if pub:
            chi += f" {long_date(pub)}."
    elif site and site not in (who, sole):
        chi += f" {site}" + (f", {long_date(pub)}." if pub else ".")
    elif pub:
        chi += f" {long_date(pub)}."
    if not pub:
        chi += f" Accessed {long_date(accessed)}."
    chi += f" {url}."
    return apa, mla, chi


def yaml_str(value):
    return json.dumps(value or "", ensure_ascii=False)


def author_line(meta):
    return "; ".join(a.display for a in authors_of(meta))


def card(meta, accessed, subject=""):
    apa, mla, chi = citations(meta, accessed)
    pub = meta.get("published")
    length = clock(meta.get("duration"))
    lines = [
        "---",
        f"type: {meta.get('type', 'webpage')}",
        f"title: {yaml_str(meta['title'])}",
        f"author: {yaml_str(author_line(meta))}",
        f"published: {pub.isoformat() if pub else ''}",
        f"accessed: {accessed.isoformat()}",
        f"url: {yaml_str(meta['url'])}",
        f"duration: {yaml_str(length)}",
    ]
    if subject:
        lines.append(f"subject: {yaml_str(subject)}")
    lines += ["---", "", f"# {meta['title']}", ""]
    facts = [author_line(meta) or meta.get("site") or "Unknown author",
             f"published {pub.isoformat()}" if pub else "date unknown"]
    if length:
        facts.append(length)
    lines += [", ".join(facts) + ".", "", f"<{meta['url']}>", "",
              "## Citations", "", "APA 7:", "", f"> {apa}", "", "MLA 9:", "", f"> {mla}", "",
              "Chicago (author-date):", "", f"> {chi}", "", "## Quotes", ""]
    if meta.get("type") == "video":
        lines.append('<!-- One quote per line with its time, for example: - [12:34] "The exact words." -->')
    else:
        lines.append('<!-- One quote per line with where it sits, for example: - (para. 4) "The exact words." -->')
    return "\n".join(lines) + "\n"


def card_name(meta, accessed):
    day = meta.get("published") or accessed
    title = clean_title(meta["title"])[:100].strip() or "Untitled"
    people = authors_of(meta)
    author = ""
    if people:
        author = clean_title(people[0].display.replace(",", ""))[:60].strip()
        author += " et al" if len(people) > 1 else ""
    return f"{day.isoformat()} {title}" + (f" ({author})" if author else "") + ".md"


def write(root, meta, accessed, subject=""):
    folder = Path(root) / CITATIONS
    folder.mkdir(parents=True, exist_ok=True)
    path = journal.unique_path(folder / card_name(meta, accessed))
    path.write_text(card(meta, accessed, subject), encoding="utf-8")
    return path
