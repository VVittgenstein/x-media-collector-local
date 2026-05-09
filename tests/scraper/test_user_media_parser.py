import unittest

from src.backend.scraper.user_media_parser import parse_user_media_tweets
from src.shared.filter_engine import FilterConfig, apply_filters


def _timeline_page(*tweets: dict) -> dict:
    return {
        "data": {
            "user": {
                "result": {
                    "timeline_v2": {
                        "timeline": {
                            "instructions": [
                                {
                                    "type": "TimelineAddEntries",
                                    "entries": [
                                        {
                                            "entryId": "profile-grid-0",
                                            "content": {
                                                "entryType": "TimelineTimelineModule",
                                                "items": [
                                                    {
                                                        "item": {
                                                            "itemContent": {
                                                                "itemType": "TimelineTweet",
                                                                "tweet_results": {
                                                                    "result": tweet
                                                                },
                                                            }
                                                        }
                                                    }
                                                    for tweet in tweets
                                                ],
                                            },
                                        }
                                    ],
                                }
                            ]
                        }
                    }
                }
            }
        }
    }


def _tweet_result(*, tweet_id: str, media: list[dict]) -> dict:
    return {
        "__typename": "Tweet",
        "rest_id": tweet_id,
        "legacy": {
            "created_at": "Mon Apr 22 14:41:30 +0000 2024",
            "extended_entities": {"media": media},
        },
    }


class TestUserMediaParser(unittest.TestCase):
    def test_parse_user_media_sample_extracts_video_variant(self) -> None:
        page = _timeline_page(
            _tweet_result(
                tweet_id="1782199752874246406",
                media=[
                    {
                        "id_str": "video_1",
                        "type": "video",
                        "original_info": {"width": 1280, "height": 720},
                        "video_info": {
                            "variants": [
                                {
                                    "content_type": "video/mp4",
                                    "bitrate": 256000,
                                    "url": "https://video.example/320x180/low.mp4",
                                },
                                {
                                    "content_type": "video/mp4",
                                    "bitrate": 2176000,
                                    "url": "https://video.example/1280x720/high.mp4",
                                },
                                {
                                    "content_type": "application/x-mpegURL",
                                    "url": "https://video.example/playlist.m3u8",
                                },
                            ]
                        },
                    }
                ],
            )
        )

        tweets = parse_user_media_tweets(page)
        self.assertGreater(len(tweets), 0)

        # The sample contains a tweet with a video + 3 mp4 variants. We must pick the highest bitrate.
        target = next((t for t in tweets if t.tweet_id == "1782199752874246406"), None)
        self.assertIsNotNone(target, "sample 中应包含 tweet_id=1782199752874246406 的视频推文")

        video_urls = [m.url for m in target.media if m.kind.value == "video"]
        self.assertEqual(len(video_urls), 1, "应只选择一个 mp4 变体作为下载 URL")
        self.assertIn("/1280x720/", video_urls[0], "应选择最高码率对应的 1280x720 mp4 变体")

    def test_min_short_side_filter_works_on_parsed_dimensions(self) -> None:
        page = _timeline_page(
            _tweet_result(
                tweet_id="large_image",
                media=[
                    {
                        "id_str": "large_img_1",
                        "type": "photo",
                        "media_url_https": "https://pbs.twimg.com/media/large.jpg?name=small",
                        "original_info": {"width": 3000, "height": 2100},
                    }
                ],
            ),
            _tweet_result(
                tweet_id="small_image",
                media=[
                    {
                        "id_str": "small_img_1",
                        "type": "photo",
                        "media_url_https": "https://pbs.twimg.com/media/small.jpg?name=small",
                        "original_info": {"width": 1000, "height": 800},
                    }
                ],
            ),
        )

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

