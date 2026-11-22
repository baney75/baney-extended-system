import io
import json
import unittest
from contextlib import redirect_stdout
from datetime import date
from unittest import mock

from bes import cite, cli
from tests.helpers import TreeTest

ACCESSED = date(2026, 11, 22)
YT_URL = "https://www.youtube.com/watch?v=abc123"
YT_JSON = json.dumps({
    "title": "How Cells Divide",
    "channel": "Amoeba Sisters",
    "uploader": "Amoeba Sisters",
    "upload_date": "20240105",
    "duration": 754,
    "webpage_url": YT_URL,
})
PAGE = """<!doctype html><html><head>
<title>Why Sleep Matters | Science Daily</title>
<meta property="og:title" content="Why Sleep Matters">
<meta property="og:site_name" content="Science Daily">
<meta name="author" content="Jane Doe">
<meta property="article:published_time" content="2025-03-03T08:00:00Z">
</head><body>hi</body></html>"""


def fake_ytdlp():
    calls = []

    def which(name):
        return "/usr/bin/yt-dlp" if name == "yt-dlp" else None

    def run(args, input_text=None, timeout=60):
        calls.append(args)
        return YT_JSON + "\n"
    return which, run, calls


class YouTubeCardTest(unittest.TestCase):
    def meta(self):
        which, run, calls = fake_ytdlp()
        with mock.patch("bes.tools.which", which), mock.patch("bes.tools.run", run), \
             mock.patch("bes.cite.fetch", side_effect=AssertionError("no network with yt-dlp")):
            meta = cite.lookup(YT_URL)
        self.assertEqual(calls[0][0], "yt-dlp")
        self.assertIn("-j", calls[0])
        return meta

    def test_front_matter(self):
        text = cite.card(self.meta(), ACCESSED)
        head = text.split("---")[1].strip().splitlines()
        self.assertEqual(head, [
            "type: video",
            'title: "How Cells Divide"',
            'author: "Amoeba Sisters"',
            "published: 2024-01-05",
            "accessed: 2026-11-22",
            f'url: "{YT_URL}"',
            'duration: "12:34"',
        ])

    def test_citations(self):
        apa, mla, chi = cite.citations(self.meta(), ACCESSED)
        self.assertEqual(apa, f"Amoeba Sisters. (2024, January 5). *How Cells Divide* [Video]. YouTube. {YT_URL}")
        self.assertEqual(mla, "“How Cells Divide.” *YouTube*, uploaded by Amoeba Sisters, "
                              "5 Jan. 2024, www.youtube.com/watch?v=abc123.")
        self.assertEqual(chi, "Amoeba Sisters. 2024. “How Cells Divide.” YouTube video, 12:34. "
                              f"January 5, 2024. {YT_URL}.")

    def test_card_sections(self):
        text = cite.card(self.meta(), ACCESSED, subject="Biology")
        self.assertIn('subject: "Biology"', text)
        for heading in ("# How Cells Divide", "## Citations", "APA 7:", "MLA 9:", "Chicago (author-date):",
                        "## Quotes"):
            self.assertIn(heading, text)
        quotes = text.split("## Quotes", 1)[1].strip()
        self.assertTrue(quotes.startswith("<!--") and quotes.endswith("-->"))  # empty but for the example
        self.assertIn("[12:34]", quotes)

    def test_file_name(self):
        self.assertEqual(cite.card_name(self.meta(), ACCESSED), "2024-01-05 How Cells Divide (Amoeba Sisters).md")


class WebCardTest(unittest.TestCase):
    def meta(self, page=PAGE, url="https://example.com/sleep"):
        with mock.patch("bes.cite.fetch", return_value=page):
            return cite.lookup(url)

    def test_meta_tags(self):
        m = self.meta()
        self.assertEqual((m["type"], m["title"], m["authors"], m["published"], m["site"]),
                         ("webpage", "Why Sleep Matters", ["Jane Doe"], date(2025, 3, 3), "Science Daily"))

    def test_citations(self):
        apa, mla, chi = cite.citations(self.meta(), ACCESSED)
        self.assertEqual(apa, "Doe, J. (2025, March 3). *Why Sleep Matters*. Science Daily. https://example.com/sleep")
        self.assertEqual(mla, "Doe, Jane. “Why Sleep Matters.” *Science Daily*, 3 Mar. 2025, example.com/sleep.")
        self.assertEqual(chi, "Doe, Jane. 2025. “Why Sleep Matters.” Science Daily, March 3, 2025. "
                              "https://example.com/sleep.")

    def test_no_date_uses_access_date(self):
        page = "<html><head><title>Plain Page</title></head></html>"
        m = self.meta(page, "https://www.plain.org/a")
        self.assertEqual(cite.card_name(m, ACCESSED), "2026-11-22 Plain Page.md")
        apa, mla, chi = cite.citations(m, ACCESSED)
        self.assertEqual(apa, "*Plain Page*. (n.d.). plain.org. Retrieved November 22, 2026, from https://www.plain.org/a")
        self.assertTrue(mla.endswith("Accessed 22 Nov. 2026."))
        self.assertIn("n.d.", chi)
        self.assertIn("Accessed November 22, 2026.", chi)

    def test_json_ld(self):
        page = ('<html><head><title>T</title><script type="application/ld+json">'
                '{"@context":"https://schema.org","@graph":[{"@type":"NewsArticle",'
                '"author":[{"@type":"Person","name":"Ann Lee"}],"datePublished":"2024-02-29T10:00:00Z"}]}'
                "</script></head></html>")
        m = self.meta(page)
        self.assertEqual((m["authors"], m["published"]), (["Ann Lee"], date(2024, 2, 29)))

    def test_organization_author_is_not_inverted(self):
        m = {"type": "webpage", "title": "Report", "authors": ["World Health Organization"],
             "site": "WHO", "published": date(2024, 1, 2), "url": "https://who.int/r", "duration": None}
        apa, mla, _ = cite.citations(m, ACCESSED)
        self.assertTrue(apa.startswith("World Health Organization. (2024"))
        self.assertTrue(mla.startswith("World Health Organization."))


class PaperCardTest(unittest.TestCase):
    PAGE = """<html><head>
<meta name="citation_title" content="Attention Is All You Need">
<meta name="citation_author" content="Vaswani, Ashish">
<meta name="citation_author" content="Shazeer, Noam">
<meta name="citation_author" content="Parmar, Niki">
<meta name="citation_date" content="2017/06/12">
<meta property="og:site_name" content="arXiv.org">
</head></html>"""

    def meta(self, authors=3):
        page = self.PAGE
        for name in ("Parmar, Niki", "Shazeer, Noam")[: 3 - authors]:
            page = page.replace(f'<meta name="citation_author" content="{name}">', "")
        with mock.patch("bes.cite.fetch", return_value=page):
            return cite.lookup("https://arxiv.org/abs/1706.03762")

    def test_three_authors(self):
        m = self.meta()
        self.assertEqual(m["published"], date(2017, 6, 12))
        apa, mla, chi = cite.citations(m, ACCESSED)
        self.assertEqual(apa, "Vaswani, A., Shazeer, N., & Parmar, N. (2017, June 12). "
                              "*Attention Is All You Need*. arXiv.org. https://arxiv.org/abs/1706.03762")
        self.assertEqual(mla, "Vaswani, Ashish, et al. \u201cAttention Is All You Need.\u201d *arXiv.org*, "
                              "12 June 2017, arxiv.org/abs/1706.03762.")
        self.assertEqual(chi, "Vaswani, Ashish, Noam Shazeer, and Niki Parmar. 2017. "
                              "\u201cAttention Is All You Need.\u201d arXiv.org, June 12, 2017. "
                              "https://arxiv.org/abs/1706.03762.")
        self.assertEqual(cite.card_name(m, ACCESSED), "2017-06-12 Attention Is All You Need (Ashish Vaswani et al).md")
        self.assertIn('author: "Ashish Vaswani; Noam Shazeer; Niki Parmar"', cite.card(m, ACCESSED))

    def test_two_and_one_authors(self):
        _, mla, chi = cite.citations(self.meta(2), ACCESSED)
        self.assertTrue(mla.startswith("Vaswani, Ashish, and Noam Shazeer. "))
        self.assertTrue(chi.startswith("Vaswani, Ashish, and Noam Shazeer. 2017. "))
        apa, _, _ = cite.citations(self.meta(1), ACCESSED)
        self.assertTrue(apa.startswith("Vaswani, A. (2017, June 12). "))

    def test_no_date_has_single_period(self):
        page = '<html><head><title>Notes</title><meta name="author" content="Ann Lee"></head></html>'
        with mock.patch("bes.cite.fetch", return_value=page):
            m = cite.lookup("https://ann.example/notes")
        _, _, chi = cite.citations(m, ACCESSED)
        self.assertEqual(chi, "Lee, Ann. n.d. \u201cNotes.\u201d ann.example. Accessed November 22, 2026. "
                              "https://ann.example/notes.")


class CiteCommandTest(TreeTest):
    def test_writes_card_to_citations(self):
        which, run, _ = fake_ytdlp()
        buf = io.StringIO()
        with mock.patch("bes.tools.which", which), mock.patch("bes.tools.run", run), redirect_stdout(buf):
            self.assertEqual(cli.main(["cite", YT_URL, "--root", str(self.root)]), 0)
            self.assertEqual(cli.main(["cite", YT_URL, "--root", str(self.root)]), 0)
        folder = self.root / "3 Know" / "Citations"
        self.assertEqual(sorted(p.name for p in folder.iterdir()), [
            "2024-01-05 How Cells Divide (Amoeba Sisters) (2).md",
            "2024-01-05 How Cells Divide (Amoeba Sisters).md",
        ])

    def test_prints_card_without_root(self):
        which, run, _ = fake_ytdlp()
        buf = io.StringIO()
        with mock.patch("bes.tools.which", which), mock.patch("bes.tools.run", run), redirect_stdout(buf):
            self.assertEqual(cli.main(["cite", YT_URL]), 0)
        self.assertTrue(buf.getvalue().startswith("---\ntype: video\n"))
        self.assertEqual(list((self.root / "3 Know" / "Citations").iterdir()), [])

    def test_oembed_fallback_without_ytdlp(self):
        responses = {
            "oembed": json.dumps({"title": "How Cells Divide", "author_name": "Amoeba Sisters"}),
            "watch": '<meta itemprop="datePublished" content="2024-01-04T20:00:00-07:00">'
                     '<meta itemprop="duration" content="PT12M34S">',
        }
        with mock.patch("bes.cite.fetch", side_effect=lambda u: responses["oembed" if "oembed" in u else "watch"]):
            m = cite.lookup(YT_URL)
        self.assertEqual((m["title"], m["authors"], m["published"], m["duration"]),
                         ("How Cells Divide", ["Amoeba Sisters"], date(2024, 1, 5), 754))  # UTC date, like yt-dlp


if __name__ == "__main__":
    unittest.main()
