import unittest
from datetime import date

from bes.naming import build_name, parse_stem


class ParseTest(unittest.TestCase):
    def check(self, stem, ext, day, title, people=()):
        p = parse_stem(stem, ext)
        self.assertEqual(p.date, day, stem)
        self.assertEqual(p.title, title, stem)
        self.assertEqual(p.people, list(people), stem)

    def test_scanner(self):
        self.check("SCN_20261121_1650", ".pdf", date(2026, 11, 21), "Scan 1650")
        self.check("SCN_20261121", ".pdf", date(2026, 11, 21), "Scan")

    def test_camera(self):
        self.check("IMG_20250704_120000", ".jpg", date(2025, 7, 4), "Photo 1200")
        self.check("PXL_20250704_120000123", ".jpg", date(2025, 7, 4), "Photo 1200")
        self.check("PXL_20250704_120000123", ".mp4", date(2025, 7, 4), "Video 1200")
        self.check("VID_20250704_093015", ".mp4", date(2025, 7, 4), "Video 0930")
        self.check("IMG-20250704-WA0001", ".jpg", date(2025, 7, 4), "Photo WA0001")

    def test_camera_without_date(self):
        self.check("IMG_1234", ".heic", None, "Photo 1234")
        self.check("DSC_0042", ".jpg", None, "Photo 0042")
        self.check("DSCN0042", ".jpg", None, "Photo 0042")

    def test_screenshots(self):
        self.check("Screenshot 2026-11-21 at 10.15.32", ".png", date(2026, 11, 21), "Screenshot 1015")
        self.check("Screen Shot 2026-11-21 at 10.15.32 AM", ".png", date(2026, 11, 21), "Screenshot 1015")
        self.check("Screenshot_20261121-101532", ".png", date(2026, 11, 21), "Screenshot 1015")
        self.check("Screenshot from 2026-11-21 10-15-32", ".png", date(2026, 11, 21), "Screenshot 1015")

    def test_iso_dates(self):
        self.check("Report 2026-11-21 final", ".pdf", date(2026, 11, 21), "Report final")
        self.check("2026_11_21_meeting_notes", ".txt", date(2026, 11, 21), "meeting notes")
        self.check("20261121 Trip", ".txt", date(2026, 11, 21), "Trip")

    def test_no_date(self):
        self.check("Chem_syllabus", ".pdf", None, "Chem syllabus")
        self.check("W-2 2025", ".pdf", None, "W-2 2025")

    def test_invalid_date_is_not_a_date(self):
        self.check("Report 2026-13-45", ".pdf", None, "Report 2026-13-45")

    def test_people_and_counters(self):
        self.check("2026-11-22 Voicemail (Mom)", ".m4a", date(2026, 11, 22), "Voicemail", ["Mom"])
        self.check("2026-11-22 Lunch (Mom, Dad) (2)", ".jpg", date(2026, 11, 22), "Lunch", ["Mom", "Dad"])
        self.check("Notes (3)", ".txt", None, "Notes")

    def test_already_named_is_stable(self):
        name = build_name(date(2026, 11, 21), "Scan 1650", [], ".pdf")
        self.assertEqual(name, "2026-11-21 Scan 1650.pdf")
        p = parse_stem(name[:-4], ".pdf")
        self.assertEqual(build_name(p.date, p.title, p.people, ".pdf"), name)


class BuildTest(unittest.TestCase):
    def test_build(self):
        self.assertEqual(build_name(date(2026, 12, 1), "Pay Verizon", [], ".PDF"), "2026-12-01 Pay Verizon.pdf")
        self.assertEqual(build_name(date(2026, 11, 22), "Voicemail", ["Mom"], ".m4a"),
                         "2026-11-22 Voicemail (Mom).m4a")
        self.assertEqual(build_name(date(2026, 1, 2), "", [], ".bin"), "2026-01-02 Untitled.bin")

    def test_unsafe_characters(self):
        self.assertEqual(build_name(date(2026, 1, 2), 'a/b:c*"d"', [], ".txt"), "2026-01-02 a b c d.txt")


if __name__ == "__main__":
    unittest.main()
