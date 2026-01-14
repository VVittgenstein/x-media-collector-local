from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional, Sequence
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from src.shared.filter_engine.models import MediaCandidate, MediaKind, Tweet


def _parse_created_at(value: Any) -> datetime:
    """
    Parse X legacy `created_at`.

    Examples:
    - "Mon Apr 22 14:41:30 +0000 2024"
    - ISO-8601 variants (fallback)
    """

    if not isinstance(value, str) or not value.strip():
        raise ValueError("created_at missing")

    raw = value.strip()

    # X legacy format (Twitter API style)
    try:
        dt = datetime.strptime(raw, "%a %b %d %H:%M:%S %z %Y")
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass

    # Fallback: ISO8601 (support trailing Z)
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _upgrade_pbs_image_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc != "pbs.twimg.com":
        return url

    qs = parse_qs(parsed.query)
    qs["name"] = ["orig"]
    return urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))


def _unwrap_tweet_result(raw: Any) -> Optional[Mapping[str, Any]]:
    if not isinstance(raw, Mapping):
        return None

    typename = raw.get("__typename")
    if typename == "Tweet":
        return raw
    # Some endpoints wrap the Tweet in a visibility container.
    if typename == "TweetWithVisibilityResults":
        inner = raw.get("tweet")
        if isinstance(inner, Mapping):
            # Newer responses may omit __typename on the inner tweet object.
            if inner.get("__typename") == "Tweet":
                return inner
            if "rest_id" in inner and "legacy" in inner:
                return inner
    return None


def _iter_timeline_tweet_results(page: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    """
    Yield top-level Tweet result objects from a UserMedia timeline page.

    This intentionally only returns tweets present as timeline items, not nested
    quoted/retweeted tweets, to avoid treating embedded tweets as separate items.
    """

    data = page.get("data")
    if not isinstance(data, Mapping):
        return

    user = data.get("user")
    if not isinstance(user, Mapping):
        return

    result = user.get("result")
    if not isinstance(result, Mapping):
        return

    # X 的 GraphQL 响应结构存在版本差异：
    # - 旧：data.user.result.timeline_v2.timeline.instructions
    # - 新：data.user.result.timeline.timeline.instructions
    timeline_container = None
    timeline_v2 = result.get("timeline_v2")
    if isinstance(timeline_v2, Mapping):
        timeline_container = timeline_v2
    else:
        timeline = result.get("timeline")
        if isinstance(timeline, Mapping):
            timeline_container = timeline

    if not isinstance(timeline_container, Mapping):
        return

    timeline = timeline_container.get("timeline")
    if not isinstance(timeline, Mapping):
        return

    instructions = timeline.get("instructions") or []
    if not isinstance(instructions, Sequence):
        return

    def from_item_content(item_content: Any) -> Optional[Mapping[str, Any]]:
        if not isinstance(item_content, Mapping):
            return None
        if item_content.get("itemType") != "TimelineTweet":
            return None
        tweet_results = item_content.get("tweet_results")
        if not isinstance(tweet_results, Mapping):
            return None
        return _unwrap_tweet_result(tweet_results.get("result"))

    for ins in instructions:
        if not isinstance(ins, Mapping):
            continue

        ins_type = ins.get("type")
        if ins_type == "TimelineAddEntries":
            entries = ins.get("entries") or []
            if not isinstance(entries, Sequence):
                continue
            for entry in entries:
                if not isinstance(entry, Mapping):
                    continue
                content = entry.get("content")
                if not isinstance(content, Mapping):
                    continue

                # Grid/module style: content.items[]
                items = content.get("items")
                if isinstance(items, Sequence):
                    for it in items:
                        if not isinstance(it, Mapping):
                            continue
                        item = it.get("item")
                        if not isinstance(item, Mapping):
                            continue
                        item_content = item.get("itemContent")
                        tw = from_item_content(item_content)
                        if tw is not None:
                            yield tw
                    continue

                # Single item style: content.itemContent
                item_content = content.get("itemContent")
                tw = from_item_content(item_content)
                if tw is not None:
                    yield tw

        elif ins_type == "TimelineAddToModule":
            module_items = ins.get("moduleItems") or []
            if not isinstance(module_items, Sequence):
                continue
            for mi in module_items:
                if not isinstance(mi, Mapping):
                    continue
                item_content = mi.get("item", {}).get("itemContent")
                tw = from_item_content(item_content)
                if tw is not None:
                    yield tw


def extract_bottom_cursor(page: Mapping[str, Any]) -> Optional[str]:
    """
    Extract the Bottom cursor value from a UserMedia page, if present.
    """

    data = page.get("data")
    if not isinstance(data, Mapping):
        return None

    user = data.get("user")
    if not isinstance(user, Mapping):
        return None

    result = user.get("result")
    if not isinstance(result, Mapping):
        return None

    # X 的 GraphQL 响应结构存在版本差异：
    # - 旧：data.user.result.timeline_v2.timeline.instructions
    # - 新：data.user.result.timeline.timeline.instructions
    timeline_container = None
    timeline_v2 = result.get("timeline_v2")
    if isinstance(timeline_v2, Mapping):
        timeline_container = timeline_v2
    else:
        timeline = result.get("timeline")
        if isinstance(timeline, Mapping):
            timeline_container = timeline

    if not isinstance(timeline_container, Mapping):
        return None

    timeline = timeline_container.get("timeline")
    if not isinstance(timeline, Mapping):
        return None

    instructions = timeline.get("instructions") or []
    if not isinstance(instructions, Sequence):
        return None

    for ins in instructions:
        if not isinstance(ins, Mapping):
            continue
        if ins.get("type") != "TimelineAddEntries":
            continue
        entries = ins.get("entries") or []
        if not isinstance(entries, Sequence):
            continue
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            content = entry.get("content")
            if not isinstance(content, Mapping):
                continue
            if content.get("entryType") != "TimelineTimelineCursor":
                continue
            if content.get("cursorType") != "Bottom":
                continue
            value = content.get("value")
            return str(value) if isinstance(value, str) and value.strip() else None

    return None


def _pick_best_video_variant(video_info: Mapping[str, Any]) -> Optional[str]:
    variants = video_info.get("variants") or []
    if not isinstance(variants, Sequence):
        return None

    best_url: Optional[str] = None
    best_bitrate: int = -1
    for v in variants:
        if not isinstance(v, Mapping):
            continue
        if str(v.get("content_type") or "") != "video/mp4":
            continue
        url = v.get("url")
        if not isinstance(url, str) or not url.strip():
            continue
        bitrate = v.get("bitrate")
        try:
            bitrate_int = int(bitrate) if bitrate is not None else 0
        except (TypeError, ValueError):
            bitrate_int = 0
        if bitrate_int > best_bitrate:
            best_bitrate = bitrate_int
            best_url = url.strip()

    return best_url


def _extract_media_candidates(tweet_result: Mapping[str, Any]) -> tuple[MediaCandidate, ...]:
    legacy = tweet_result.get("legacy")
    if not isinstance(legacy, Mapping):
        return ()

    entities = legacy.get("extended_entities")
    if not isinstance(entities, Mapping):
        return ()

    media_list = entities.get("media") or []
    if not isinstance(media_list, Sequence):
        return ()

    candidates: list[MediaCandidate] = []
    for idx, media in enumerate(media_list):
        if not isinstance(media, Mapping):
            continue

        media_type = str(media.get("type") or "").strip().lower()
        media_id = media.get("id_str") or media.get("media_key") or f"m{idx}"
        media_id = str(media_id)

        original_info = media.get("original_info")
        width = height = None
        if isinstance(original_info, Mapping):
            try:
                width = int(original_info.get("width")) if original_info.get("width") is not None else None
            except (TypeError, ValueError):
                width = None
            try:
                height = int(original_info.get("height")) if original_info.get("height") is not None else None
            except (TypeError, ValueError):
                height = None

        if media_type == "photo":
            url = media.get("media_url_https") or media.get("media_url")
            if not isinstance(url, str) or not url.strip():
                continue
            candidates.append(
                MediaCandidate(
                    media_id=media_id,
                    kind=MediaKind.IMAGE,
                    url=_upgrade_pbs_image_url(url.strip()),
                    width=width,
                    height=height,
                )
            )
            continue

        if media_type in ("video", "animated_gif"):
            video_info = media.get("video_info")
            if not isinstance(video_info, Mapping):
                continue
            best = _pick_best_video_variant(video_info)
            if not best:
                continue
            candidates.append(
                MediaCandidate(
                    media_id=media_id,
                    kind=MediaKind.VIDEO,
                    url=best,
                    width=width,
                    height=height,
                )
            )
            continue

    return tuple(candidates)


def _build_tweet_from_result(tweet_result: Mapping[str, Any], *, _depth: int) -> Optional[Tweet]:
    legacy = tweet_result.get("legacy")
    if not isinstance(legacy, Mapping):
        return None

    tweet_id = tweet_result.get("rest_id")
    if not isinstance(tweet_id, str) or not tweet_id.strip():
        return None

    created_at = _parse_created_at(legacy.get("created_at"))

    is_reply = bool(
        legacy.get("in_reply_to_status_id_str")
        or legacy.get("in_reply_to_user_id_str")
        or legacy.get("in_reply_to_screen_name")
    )

    retweeted_result = None
    retweeted_container = tweet_result.get("retweeted_status_result")
    if isinstance(retweeted_container, Mapping):
        retweeted_result = _unwrap_tweet_result(retweeted_container.get("result"))

    is_retweet = bool(retweeted_result is not None or legacy.get("retweeted_status_id_str"))

    # For retweets, media usually lives in the retweeted tweet.
    media_source = retweeted_result or tweet_result
    media = _extract_media_candidates(media_source)

    quoted_tweet: Optional[Tweet] = None
    quoted_container = tweet_result.get("quoted_status_result")
    if _depth < 1 and isinstance(quoted_container, Mapping):
        quoted_result = _unwrap_tweet_result(quoted_container.get("result"))
        if quoted_result is not None:
            quoted_tweet = _build_tweet_from_result(quoted_result, _depth=_depth + 1)

    return Tweet(
        tweet_id=tweet_id.strip(),
        created_at=created_at,
        is_reply=is_reply,
        is_retweet=is_retweet,
        quoted_tweet=quoted_tweet,
        media=media,
    )


def parse_user_media_tweets(page: Mapping[str, Any]) -> list[Tweet]:
    """
    Parse a (GraphQL) UserMedia timeline page into FilterEngine Tweets.

    Returns:
        Tweets sorted newest -> oldest for stability.
    """

    tweets: list[Tweet] = []
    for raw in _iter_timeline_tweet_results(page):
        tw = _build_tweet_from_result(raw, _depth=0)
        if tw is None:
            continue
        if not tw.media:
            continue
        tweets.append(tw)

    tweets.sort(key=lambda t: (-int(t.created_at.timestamp() * 1_000_000), t.tweet_id))
    return tweets
