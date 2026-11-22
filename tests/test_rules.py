"""Each SPEC.md sorting rule, and that earlier rules win over later ones."""

import unittest
from datetime import date, timedelta
from unittest import mock

from bes import sort
from tests.helpers import NOON, TreeTest


class RuleTest(TreeTest):
    def plan(self, cfg=None):
        return {m.src.name: m for m in sort.plan(self.root, cfg, warn=lambda _: None)}

    def where(self, name, cfg=None):
        """(folder relative to root, rule) for one Inbox item, or None if untouched."""
        m = self.plan(cfg).get(name)
        if m is None:
            return None
        return m.dest.parent.relative_to(self.root).as_posix(), m.rule

    # 1. Let Go -----------------------------------------------------------

    def test_letgo_old_partial_download(self):
        self.put("movie.mp4.crdownload", days_old=3)
        self.put("thing.part", days_old=3)
        self.put("x.tmp", days_old=3)
        for n in ("movie.mp4.crdownload", "thing.part", "x.tmp"):
            self.assertEqual(self.where(n), ("4 Let Go", "letgo:partial"))

    def test_fresh_partial_download_is_left_alone(self):
        self.put("movie.mp4.crdownload", days_old=0)
        self.assertIsNone(self.where("movie.mp4.crdownload"))

    def test_letgo_empty_file_beats_records(self):
        self.put("receipt.pdf", content="")
        self.assertEqual(self.where("receipt.pdf"), ("4 Let Go", "letgo:empty"))

    def test_letgo_empty_folder(self):
        (self.inbox / "Empty").mkdir()
        self.assertEqual(self.where("Empty"), ("4 Let Go", "letgo:empty"))

    def test_letgo_duplicate_of_kept_file(self):
        self.put("2025-01-01 Photo.jpg", content="same bytes", folder=self.root / "2 Keep" / "2025")
        self.put("copy of receipt.jpg", content="same bytes")
        self.assertEqual(self.where("copy of receipt.jpg"), ("4 Let Go", "letgo:duplicate"))

    def test_duplicate_within_one_run(self):
        self.put("homework a.txt", content="same", when=NOON)
        self.put("homework b.txt", content="same", when=NOON)
        p = self.plan()
        self.assertEqual(p["homework a.txt"].rule, "do")
        self.assertEqual(p["homework b.txt"].rule, "letgo:duplicate")

    def test_same_size_different_bytes_is_not_duplicate(self):
        self.put("kept.txt", content="aaaa", folder=self.root / "1 Do")
        self.put("homework.txt", content="bbbb")
        self.assertEqual(self.where("homework.txt"), ("1 Do", "do"))

    def test_letgo_old_installer_only(self):
        self.put("setup.exe", days_old=10)
        self.put("tool.AppImage", days_old=8)
        self.put("new.dmg", days_old=2)
        self.assertEqual(self.where("setup.exe"), ("4 Let Go", "letgo:installer"))
        self.assertEqual(self.where("tool.AppImage"), ("4 Let Go", "letgo:installer"))
        self.assertEqual(self.where("new.dmg"), ("0 Inbox", "stay"))

    def test_letgo_old_screenshot_only(self):
        old = date.today() - timedelta(days=40)
        self.put(f"Screenshot {old.isoformat()} at 10.15.32.png")
        self.put("Screenshot 2099-01-01 at 10.15.32.png")
        self.assertEqual(self.where(f"Screenshot {old.isoformat()} at 10.15.32.png"),
                         ("4 Let Go", "letgo:screenshot"))
        self.assertEqual(self.where("Screenshot 2099-01-01 at 10.15.32.png"), ("0 Inbox", "stay"))

    # 2. Keep/Records -----------------------------------------------------

    def test_records_by_name(self):
        for name in ("W-2 2025.pdf", "1099-INT.pdf", "Car insurance card.pdf", "lease_2026.pdf",
                     "Birth_Certificate.pdf", "taxes 2025.zip", "Passport scan.jpg"):
            self.put(name, when=NOON)
        p = self.plan()
        for name in ("W-2 2025.pdf", "1099-INT.pdf", "Car insurance card.pdf", "lease_2026.pdf",
                     "Birth_Certificate.pdf", "taxes 2025.zip", "Passport scan.jpg"):
            self.assertEqual(p[name].rule, "keep:records", name)
            self.assertEqual(p[name].dest.parent, self.root / "2 Keep" / "Records")

    def test_records_beats_camera(self):
        self.put("IMG_20250704_120000 receipt.jpg")
        self.assertEqual(self.where("IMG_20250704_120000 receipt.jpg"), ("2 Keep/Records", "keep:records"))

    def test_records_by_text(self):
        self.put("scan.txt", content="ACME Corp\nINVOICE #4411\nTotal due: $40")
        self.assertEqual(self.where("scan.txt"), ("2 Keep/Records", "keep:records"))

    def test_records_by_pdf_text_when_pdftotext_present(self):
        self.put("SCN_20261121_1650.pdf", content="%PDF-1.4 fake")
        with mock.patch("bes.tools.which", lambda name: "/usr/bin/" + name if name == "pdftotext" else None), \
             mock.patch("bes.tools.run", return_value="Form W-2 Wage and Tax Statement"):
            m = self.plan()["SCN_20261121_1650.pdf"]
        self.assertEqual(m.rule, "keep:records")
        self.assertEqual(m.dest.name, "2026-11-21 Scan 1650.pdf")

    def test_no_false_match_inside_words(self):
        self.put("subtitles.srt", when=NOON)  # contains "title", not the word
        self.assertEqual(self.where("subtitles.srt"), ("0 Inbox", "stay"))

    # 3. Keep/<year> --------------------------------------------------------

    def test_camera_media_by_year(self):
        self.put("IMG_20250704_120000.jpg")
        self.put("PXL_20240101_090000000.mp4")
        self.put("DSC_0042.jpg", when=NOON)
        self.put("IMG_1234.HEIC", when=NOON)
        p = self.plan()
        self.assertEqual(p["IMG_20250704_120000.jpg"].dest,
                         self.root / "2 Keep" / "2025" / "2025-07-04 Photo 1200.jpg")
        self.assertEqual(p["PXL_20240101_090000000.mp4"].dest,
                         self.root / "2 Keep" / "2024" / "2024-01-01 Video 0900.mp4")
        self.assertEqual(p["DSC_0042.jpg"].dest, self.root / "2 Keep" / "2026" / "2026-03-04 Photo 0042.jpg")
        self.assertEqual(p["IMG_1234.HEIC"].dest, self.root / "2 Keep" / "2026" / "2026-03-04 Photo 1234.heic")

    def test_exif_camera_and_date(self):
        self.put("beach.jpg", when=NOON)
        with mock.patch("bes.textread.exif", return_value=(date(2023, 8, 9), True)):
            m = self.plan()["beach.jpg"]
        self.assertEqual(m.rule, "keep:media")
        self.assertEqual(m.dest, self.root / "2 Keep" / "2023" / "2023-08-09 beach.jpg")

    def test_personal_items(self):
        self.put("Voicemail (Mom).m4a", when=NOON)
        self.put("journal march.txt", content="dear diary", when=NOON)
        self.put("Letter to Grandpa.docx", when=NOON)
        self.put("call log export.csv", when=NOON)
        self.put("New voice note.amr", when=NOON)
        p = self.plan()
        self.assertEqual(p["Voicemail (Mom).m4a"].dest,
                         self.root / "2 Keep" / "2026" / "2026-03-04 Voicemail (Mom).m4a")
        for name in ("journal march.txt", "Letter to Grandpa.docx", "call log export.csv",
                     "New voice note.amr"):
            self.assertEqual(p[name].rule, "keep:personal", name)

    def test_personal_beats_know(self):
        self.put("lecture journal.txt", when=NOON)
        self.assertEqual(self.where("lecture journal.txt"), ("2 Keep/2026", "keep:personal"))

    # 4. Know ---------------------------------------------------------------

    def test_know(self):
        cases = {
            "Moby Dick.epub": ("3 Know", "know:book"),
            "paper 10.1038_nature12373.pdf": ("3 Know", "know:paper"),
            "2301.12345v2.pdf": ("3 Know", "know:paper"),
            "Week 3.pptx": ("3 Know", "know:class"),
            "Chem syllabus.pdf": ("3 Know", "know:class"),
            "lecture_notes_ch4.pdf": ("3 Know", "know:class"),
            "refs.bib": ("3 Know/Citations", "know:citation"),
        }
        for name in cases:
            self.put(name, when=NOON)
        for name, want in cases.items():
            self.assertEqual(self.where(name), want, name)

    def test_know_by_doi_in_text(self):
        self.put("download.txt", content="Journal of Things\nhttps://doi.org/10.1000/xyz123\n")
        self.assertEqual(self.where("download.txt"), ("3 Know", "know:paper"))

    def test_know_beats_do(self):
        self.put("lecture homework.pdf", when=NOON)
        self.assertEqual(self.where("lecture homework.pdf"), ("3 Know", "know:class"))

    # 5. Do -----------------------------------------------------------------

    def test_do(self):
        for name in ("homework 3 due.docx", "Job application.pdf", "draft essay.md",
                     "RSVP party.txt", "permission_form.pdf", "todo.txt"):
            self.put(name, when=NOON)
        p = self.plan()
        for name in ("homework 3 due.docx", "Job application.pdf", "draft essay.md",
                     "RSVP party.txt", "permission_form.pdf", "todo.txt"):
            self.assertEqual(p[name].rule, "do", name)
            self.assertEqual(p[name].dest.parent, self.root / "1 Do")

    def test_do_by_text(self):
        self.put("note.txt", content="Please sign and return by Friday.")
        self.assertEqual(self.where("note.txt"), ("1 Do", "do"))

    # 6. Stay ---------------------------------------------------------------

    def test_stays_and_is_renamed(self):
        self.put("random.bin", when=NOON)
        m = self.plan()["random.bin"]
        self.assertEqual((m.dest.parent, m.dest.name, m.rule),
                         (self.inbox, "2026-03-04 random.bin", "stay"))

    def test_already_named_leftover_is_untouched(self):
        self.put("2026-03-04 random.bin", when=NOON)
        self.assertIsNone(self.where("2026-03-04 random.bin"))

    def test_hidden_files_are_ignored(self):
        self.put(".DS_Store")
        self.put("desktop.ini")
        self.assertEqual(self.plan(), {})


if __name__ == "__main__":
    unittest.main()
