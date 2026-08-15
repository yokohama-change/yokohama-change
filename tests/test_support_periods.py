import importlib.util
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
p = SCRIPTS / "enrich_support_periods.py"
spec = importlib.util.spec_from_file_location("support_periods", p)
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
JST = timezone(timedelta(hours=9))


class SupportPeriodsTests(unittest.TestCase):
    def setUp(self):
        self.item = {"title": "展示会出展費用助成金", "source_updated": "Wed, 12 Aug 2026 07:00:00 GMT"}
        self.text = """①申請書の提出について
申請期間※原則、助成対象事業の出展日の１か月前までに提出してください。
【申請期間：第１期】
令和８年４月22日（水曜日）９時00分～令和８年８月31日（月曜日）17時00分
＜参考＞
【申請期間：第２期】
令和８年９月１日（火曜日）９時00分～令和９年２月24日（水曜日）17時00分
指定様式のダウンロード"""

    def test_first_phase_active(self):
        out = s.active_period_from_text(self.text, self.item, datetime(2026, 8, 15, 22, 0, tzinfo=JST))
        self.assertIsNotNone(out)
        cutoff, source = out
        self.assertEqual(cutoff.isoformat(timespec="minutes"), "2026-08-31T17:00+09:00")
        self.assertIn("申請期間", source)

    def test_second_phase_active(self):
        out = s.active_period_from_text(self.text, self.item, datetime(2026, 10, 1, 12, 0, tzinfo=JST))
        self.assertIsNotNone(out)
        cutoff, _ = out
        self.assertEqual(cutoff.isoformat(timespec="minutes"), "2027-02-24T17:00+09:00")

    def test_after_all_periods_not_active(self):
        out = s.active_period_from_text(self.text, self.item, datetime(2027, 3, 1, 12, 0, tzinfo=JST))
        self.assertIsNone(out)


if __name__ == "__main__":
    unittest.main()
