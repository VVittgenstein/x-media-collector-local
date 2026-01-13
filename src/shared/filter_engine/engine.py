"""
Filter Engine（纯逻辑）。

输入：Tweets（含 media 与可选 quoted_tweet） + FilterConfig
输出：DownloadIntent 列表（稳定可复现） + 可计数的过滤原因
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Iterable, Sequence

from .classifier import classify_tweet_source_type, is_reply_plus_quote
from .models import DownloadIntent, FilterConfig, FilterResult, MediaCandidate, MediaKind, Tweet


FILTER_REASON_MIN_SHORT_SIDE = "min_short_side"


def _dt_to_sort_int(dt: datetime) -> int:
    return int(dt.timestamp() * 1_000_000)


def _media_kind_allowed(kind: MediaKind, media_type: str) -> bool:
    if media_type == "both":
        return True
    if media_type == "images":
        return kind == MediaKind.IMAGE
    if media_type == "videos":
        return kind == MediaKind.VIDEO
    raise ValueError(f"未知 media_type: {media_type}")


def _in_date_closed_interval(tweet: Tweet, config: FilterConfig) -> bool:
    if config.start_date is None and config.end_date is None:
        return True

    tweet_date = tweet.created_at.date()
    if config.start_date is not None and tweet_date < config.start_date:
        return False
    if config.end_date is not None and tweet_date > config.end_date:
        return False
    return True


def _iter_candidate_media(
    tweet: Tweet, *, include_quoted_media: bool
) -> Iterable[tuple[MediaCandidate, str, Tweet]]:
    for m in tweet.media:
        yield (m, "self", tweet)

    if include_quoted_media and tweet.quoted_tweet is not None:
        for m in tweet.quoted_tweet.media:
            yield (m, "quoted", tweet.quoted_tweet)


def apply_filters(tweets: Sequence[Tweet], config: FilterConfig) -> FilterResult:
    """
    根据配置对推文集合做分类与过滤，并输出“下载意图列表”。

    约定：
    - 日期/来源类型筛选作用于“触发推文”（即当前 tweet）
    - Reply+Quote 开关仅对 Reply+Quote 生效；开启时可额外纳入被引用推文的媒体
    - MIN_SHORT_SIDE：有 width/height 则前置过滤；无尺寸信息则保留并标记 needs_post_min_short_side_check
    """

    if config.start_date and config.end_date and config.start_date > config.end_date:
        raise ValueError("start_date 不能晚于 end_date")

    filtered_counts: dict[str, int] = defaultdict(int)
    intents: list[DownloadIntent] = []

    for tweet in tweets:
        if not _in_date_closed_interval(tweet, config):
            continue

        source_type = classify_tweet_source_type(tweet)
        if source_type not in config.source_types:
            continue

        include_quoted_media = bool(is_reply_plus_quote(tweet) and config.include_quote_media_in_reply)

        for media, origin, media_tweet in _iter_candidate_media(tweet, include_quoted_media=include_quoted_media):
            if not _media_kind_allowed(media.kind, config.media_type.value):
                continue

            needs_post_check = False
            if config.min_short_side is not None:
                if media.width is not None and media.height is not None:
                    if min(media.width, media.height) < config.min_short_side:
                        filtered_counts[FILTER_REASON_MIN_SHORT_SIDE] += 1
                        continue
                else:
                    needs_post_check = True

            intents.append(
                DownloadIntent(
                    media_id=media.media_id,
                    kind=media.kind,
                    url=media.url,
                    width=media.width,
                    height=media.height,
                    tweet_id=media_tweet.tweet_id,
                    tweet_created_at=media_tweet.created_at,
                    trigger_tweet_id=tweet.tweet_id,
                    trigger_created_at=tweet.created_at,
                    origin=origin,
                    needs_post_min_short_side_check=needs_post_check,
                )
            )

    origin_rank = {"self": 0, "quoted": 1}
    kind_rank = {MediaKind.IMAGE: 0, MediaKind.VIDEO: 1}

    intents_sorted = tuple(
        sorted(
            intents,
            key=lambda it: (
                -_dt_to_sort_int(it.trigger_created_at),
                it.trigger_tweet_id,
                origin_rank.get(it.origin, 9),
                kind_rank.get(it.kind, 9),
                it.tweet_id,
                it.media_id,
            ),
        )
    )

    return FilterResult(intents=intents_sorted, filtered_counts=dict(filtered_counts))

