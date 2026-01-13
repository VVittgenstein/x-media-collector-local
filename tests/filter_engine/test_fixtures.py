import json
import unittest
from pathlib import Path

from src.shared.filter_engine import FilterConfig, Tweet, apply_filters


class TestFilterEngineFixtures(unittest.TestCase):
    def test_json_fixtures_regression(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        fixture_dir = repo_root / "artifacts" / "fixtures" / "tweets"

        fixture_files = sorted(fixture_dir.glob("*.json"))
        self.assertGreaterEqual(
            len(fixture_files),
            5,
            f"fixtures 数量不足，当前={len(fixture_files)}（期望>=5）",
        )

        for fixture_path in fixture_files:
            with self.subTest(fixture=fixture_path.name):
                fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
                config = FilterConfig.from_dict(fixture["config"])
                tweets = [Tweet.from_dict(t) for t in fixture["tweets"]]

                actual = apply_filters(tweets, config).to_dict()
                expected = fixture["expected"]
                self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()

