"""
Filter Engine 的稳定领域模型（纯逻辑层）。

目标：
- 用最少的字段表达筛选与分类所需信息
- 便于从 JSON fixtures 解析并做回归
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional, Sequence


class MediaKind(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class MediaTypeFilter(str, Enum):
    IMAGES = "images"
    VIDEOS = "videos"
    BOTH = "both"


class TweetSourceType(str, Enum):
    ORIGINAL = "Original"
    REPLY = "Reply"
    RETWEET = "Retweet"
    QUOTE = "Quote"


def parse_iso_datetime(value: str) -> datetime:
    """
    解析 ISO8601 datetime（支持 Z），并保证返回 tz-aware（UTC）。
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("created_at 必须是非空字符串")

    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"

    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_iso_datetime_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso_date(value: Optional[str]) -> Optional[date]:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("日期必须是 YYYY-MM-DD 或 null")
    return date.fromisoformat(value.strip())


@dataclass(frozen=True)
class MediaCandidate:
    media_id: str
    kind: MediaKind
    url: str
    width: Optional[int] = None
    height: Optional[int] = None

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "MediaCandidate":
        return MediaCandidate(
            media_id=str(data["media_id"]),
            kind=MediaKind(str(data["kind"])),
            url=str(data["url"]),
            width=(int(data["width"]) if data.get("width") is not None else None),
            height=(int(data["height"]) if data.get("height") is not None else None),
        )


@dataclass(frozen=True)
class Tweet:
    tweet_id: str
    created_at: datetime
    is_reply: bool = False
    is_retweet: bool = False
    quoted_tweet: Optional["Tweet"] = None
    media: tuple[MediaCandidate, ...] = ()

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "Tweet":
        quoted = data.get("quoted_tweet")
        return Tweet(
            tweet_id=str(data["tweet_id"]),
            created_at=parse_iso_datetime(str(data["created_at"])),
            is_reply=bool(data.get("is_reply", False)),
            is_retweet=bool(data.get("is_retweet", False)),
            quoted_tweet=(Tweet.from_dict(quoted) if isinstance(quoted, Mapping) else None),
            media=tuple(MediaCandidate.from_dict(m) for m in data.get("media", []) or []),
        )


@dataclass(frozen=True)
class FilterConfig:
    """
    筛选配置（Account Config 的子集）。
    """

    start_date: Optional[date] = None
    end_date: Optional[date] = None
    media_type: MediaTypeFilter = MediaTypeFilter.BOTH
    source_types: frozenset[TweetSourceType] = frozenset(
        (
            TweetSourceType.ORIGINAL,
            TweetSourceType.REPLY,
            TweetSourceType.RETWEET,
            TweetSourceType.QUOTE,
        )
    )
    include_quote_media_in_reply: bool = False
    min_short_side: Optional[int] = None

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "FilterConfig":
        raw_source_types = data.get("source_types", None)
        if raw_source_types is None:
            source_types = FilterConfig.source_types
        else:
            if not isinstance(raw_source_types, Sequence) or isinstance(raw_source_types, (str, bytes)):
                raise ValueError("source_types 必须是数组")
            source_types = frozenset(TweetSourceType(str(v)) for v in raw_source_types)

        min_short_side = data.get("min_short_side", None)
        if min_short_side is not None:
            min_short_side = int(min_short_side)
            if min_short_side <= 0:
                min_short_side = None

        return FilterConfig(
            start_date=parse_iso_date(data.get("start_date")),
            end_date=parse_iso_date(data.get("end_date")),
            media_type=MediaTypeFilter(str(data.get("media_type", MediaTypeFilter.BOTH.value))),
            source_types=source_types,
            include_quote_media_in_reply=bool(data.get("include_quote_media_in_reply", False)),
            min_short_side=min_short_side,
        )


@dataclass(frozen=True)
class DownloadIntent:
    """
    “下载意图” = 业务层决定要下载的一个具体媒体（image/video）。
    """

    media_id: str
    kind: MediaKind
    url: str
    width: Optional[int]
    height: Optional[int]
    tweet_id: str
    tweet_created_at: datetime
    trigger_tweet_id: str
    trigger_created_at: datetime
    origin: str  # "self" | "quoted"
    needs_post_min_short_side_check: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "media_id": self.media_id,
            "kind": self.kind.value,
            "url": self.url,
            "width": self.width,
            "height": self.height,
            "tweet_id": self.tweet_id,
            "tweet_created_at": format_iso_datetime_z(self.tweet_created_at),
            "trigger_tweet_id": self.trigger_tweet_id,
            "trigger_created_at": format_iso_datetime_z(self.trigger_created_at),
            "origin": self.origin,
            "needs_post_min_short_side_check": self.needs_post_min_short_side_check,
        }


@dataclass(frozen=True)
class FilterResult:
    intents: tuple[DownloadIntent, ...]
    filtered_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "intents": [intent.to_dict() for intent in self.intents],
            "filtered_counts": dict(self.filtered_counts),
        }

