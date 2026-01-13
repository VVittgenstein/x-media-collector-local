import json
import unittest
from pathlib import Path

from src.backend.scraper.user_media_parser import parse_user_media_tweets
from src.shared.filter_engine import FilterConfig, apply_filters


class TestUserMediaParser(unittest.TestCase):
    def test_parse_user_media_sample_extracts_video_variant(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        sample_path = repo_root / "artifacts" / "samples" / "x_timeline_user_media_sample.json"
        page = json.loads(sample_path.read_text(encoding="utf-8"))

        tweets = parse_user_media_tweets(page)
        self.assertGreater(len(tweets), 0)

        # The sample contains a tweet with a video + 3 mp4 variants. We must pick the highest bitrate.
        target = next((t for t in tweets if t.tweet_id == "1782199752874246406"), None)
        self.assertIsNotNone(target, "sample 中应包含 tweet_id=1782199752874246406 的视频推文")

        video_urls = [m.url for m in target.media if m.kind.value == "video"]
        self.assertEqual(len(video_urls), 1, "应只选择一个 mp4 变体作为下载 URL")
        self.assertIn("/1280x720/", video_urls[0], "应选择最高码率对应的 1280x720 mp4 变体")

    def test_min_short_side_filter_works_on_parsed_dimensions(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        sample_path = repo_root / "artifacts" / "samples" / "x_timeline_user_media_sample.json"
        page = json.loads(sample_path.read_text(encoding="utf-8"))

        tweets = parse_user_media_tweets(page)
        config = FilterConfig.from_dict(
            {
                "media_type": "both",
                "min_short_side": 2000,
            }
        )

        result = apply_filters(tweets, config)
        self.assertGreater(result.filtered_counts.get("min_short_side", 0), 0, "应产生 min_short_side 过滤计数")

        for intent in result.intents:
            if intent.width is None or intent.height is None:
                self.assertTrue(
                    intent.needs_post_min_short_side_check,
                    "无尺寸信息时应标记 needs_post_min_short_side_check",
                )
                continue
            self.assertGreaterEqual(min(intent.width, intent.height), 2000)


if __name__ == "__main__":
    unittest.main()

