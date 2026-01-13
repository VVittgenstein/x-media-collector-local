"""
推文来源类型分类（纯逻辑）。

规则（来自 read_only.md / EVID-001）：
- 只要是 Reply 就归 Reply（即使同时 Quote）
- Quote 仅指：非 Reply 且存在引用关系的推文
"""

from __future__ import annotations

from .models import Tweet, TweetSourceType


def is_reply_plus_quote(tweet: Tweet) -> bool:
    return bool(tweet.is_reply and tweet.quoted_tweet is not None)


def classify_tweet_source_type(tweet: Tweet) -> TweetSourceType:
    if tweet.is_reply:
        return TweetSourceType.REPLY
    if tweet.is_retweet:
        return TweetSourceType.RETWEET
    if tweet.quoted_tweet is not None:
        return TweetSourceType.QUOTE
    return TweetSourceType.ORIGINAL

