#!/usr/bin/env python3
from __future__ import annotations

"""
Spike：用登录 Cookies 访问 X 内部接口并抓取媒体推文样本。

目标（对齐 record.json / T-20260113-act-002-spike-cookie-scrape）：
- 通过登录态 Cookie（auth_token/ct0）调用 X 网页内部 GraphQL（通过 twscrape）
- 拉取指定账号的媒体推文（UserMedia）并下载图片/视频样本到本地目录
- 记录错误类型（401/403/429/网络错误等）、重试与耗时，并保存脱敏后的 JSON 响应样本

依赖：
- twscrape>=0.17.0（内部依赖 httpx 等）

凭证来源（优先级）：
1) CLI 参数：--auth-token / --ct0 / --twid
2) 环境变量：XMC_AUTH_TOKEN / XMC_CT0 / XMC_TWID
3) Settings 配置文件：data/config.json（WebUI 保存全局设置后生成）

示例：
  python3 scripts/spike_scrape_sample.py --handle XDevelopers --limit 50

注意：
- 本脚本不会打印或写入 auth_token/ct0 原文；日志仅记录长度与脱敏后的片段。
- 请自担使用风险；建议用非主账号、保守频率、必要时配置代理。
"""

import argparse
import asyncio
import json
import os
import re
import sqlite3
import sys
import tempfile
import time
from contextlib import aclosing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


SENSITIVE_KEYS = {
    "auth_token",
    "ct0",
    "cookie",
    "authorization",
    "x-csrf-token",
}

SENSITIVE_VALUE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(auth_token=)[^;\s]+", re.IGNORECASE), r"\1REDACTED"),
    (re.compile(r"(ct0=)[^;\s]+", re.IGNORECASE), r"\1REDACTED"),
]


@dataclass(frozen=True)
class Credentials:
    auth_token: str
    ct0: str
    twid: Optional[str] = None

    def is_complete(self) -> bool:
        return bool(self.auth_token.strip()) and bool(self.ct0.strip())

    def to_cookie_string(self) -> str:
        parts = [
            f"auth_token={self.auth_token.strip()}",
            f"ct0={self.ct0.strip()}",
        ]
        if self.twid and self.twid.strip():
            parts.append(f"twid={self.twid.strip()}")
        return "; ".join(parts)

    def to_safe_debug_dict(self) -> dict[str, Any]:
        def safe(v: Optional[str]) -> dict[str, Any]:
            v = (v or "").strip()
            if not v:
                return {"set": False}
            return {"set": True, "len": len(v), "prefix": v[:3], "suffix": v[-3:]}

        return {
            "auth_token": safe(self.auth_token),
            "ct0": safe(self.ct0),
            "twid": safe(self.twid),
        }


def utc_now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%SZ")


def redact_obj(obj: Any) -> Any:
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if str(k).lower() in SENSITIVE_KEYS:
                out[k] = "REDACTED"
            else:
                out[k] = redact_obj(v)
        return out
    if isinstance(obj, list):
        return [redact_obj(v) for v in obj]
    if isinstance(obj, str):
        s = obj
        for pattern, repl in SENSITIVE_VALUE_PATTERNS:
            s = pattern.sub(repl, s)
        return s
    return obj


def atomic_write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def append_jsonl(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def load_credentials_from_config(path: Path) -> Optional[Credentials]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None

    creds = raw.get("credentials")
    if not isinstance(creds, dict):
        return None

    auth_token = str(creds.get("auth_token", "") or "").strip()
    ct0 = str(creds.get("ct0", "") or "").strip()
    twid = creds.get("twid")
    twid = str(twid).strip() if twid is not None and str(twid).strip() else None
    c = Credentials(auth_token=auth_token, ct0=ct0, twid=twid)
    return c if c.is_complete() else None


def resolve_credentials(args: argparse.Namespace) -> Optional[Credentials]:
    auth_token = (args.auth_token or os.getenv("XMC_AUTH_TOKEN") or "").strip()
    ct0 = (args.ct0 or os.getenv("XMC_CT0") or "").strip()
    twid = (args.twid or os.getenv("XMC_TWID") or "").strip() or None

    if auth_token and ct0:
        return Credentials(auth_token=auth_token, ct0=ct0, twid=twid)

    if args.config:
        from_cfg = load_credentials_from_config(Path(args.config))
        if from_cfg:
            return from_cfg

    return None


def _upgrade_pbs_image_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc != "pbs.twimg.com":
        return url

    qs = parse_qs(parsed.query)
    # Try to fetch the original size when possible.
    qs["name"] = ["orig"]
    new_query = urlencode(qs, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def _infer_ext_from_url(url: str, default: str) -> str:
    parsed = urlparse(url)
    path = parsed.path
    if "." in path.rsplit("/", 1)[-1]:
        ext = path.rsplit(".", 1)[-1].lower()
        if 1 <= len(ext) <= 8:
            return ext

    qs = parse_qs(parsed.query)
    fmt = (qs.get("format") or [None])[0]
    if isinstance(fmt, str) and 1 <= len(fmt) <= 8:
        return fmt.lower()

    return default


def _download_with_retries(
    *,
    url: str,
    dest: Path,
    user_agent: str,
    timeout_s: float,
    retries: int,
    backoff_s: float,
) -> tuple[bool, int, Optional[int], Optional[str]]:
    if dest.exists():
        return True, int(dest.stat().st_size), None, "exists"

    dest.parent.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": user_agent,
        "Accept": "*/*",
        "Referer": "https://x.com/",
    }

    last_err: Optional[str] = None
    last_status: Optional[int] = None
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout_s) as resp:
                tmp_fd, tmp_path = tempfile.mkstemp(
                    prefix=dest.name + ".", suffix=".tmp", dir=str(dest.parent)
                )
                os.close(tmp_fd)
                tmp = Path(tmp_path)
                try:
                    size = 0
                    with tmp.open("wb") as f:
                        while True:
                            chunk = resp.read(1024 * 128)
                            if not chunk:
                                break
                            f.write(chunk)
                            size += len(chunk)
                    tmp.replace(dest)
                finally:
                    if tmp.exists() and not dest.exists():
                        tmp.unlink(missing_ok=True)
            return True, size, None, None
        except HTTPError as exc:
            last_status = int(getattr(exc, "code", 0) or 0) or None
            last_err = f"HTTPError: {exc}"
            if last_status in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(backoff_s * (2**attempt))
                continue
            return False, 0, last_status, last_err
        except URLError as exc:
            last_err = f"URLError: {exc}"
            if attempt < retries:
                time.sleep(backoff_s * (2**attempt))
                continue
            return False, 0, last_status, last_err
        except TimeoutError as exc:
            last_err = f"TimeoutError: {exc}"
            if attempt < retries:
                time.sleep(backoff_s * (2**attempt))
                continue
            return False, 0, last_status, last_err

    return False, 0, last_status, last_err or "unknown error"


def _flatten_media(tweet: Any) -> list[dict[str, Any]]:
    media_items: list[dict[str, Any]] = []
    media = getattr(tweet, "media", None)
    if not media:
        return media_items

    for p in getattr(media, "photos", []) or []:
        url = getattr(p, "url", None)
        if isinstance(url, str) and url.strip():
            media_items.append({"kind": "image", "url": _upgrade_pbs_image_url(url.strip())})

    for v in getattr(media, "videos", []) or []:
        variants = getattr(v, "variants", []) or []
        best = None
        for vv in variants:
            bitrate = getattr(vv, "bitrate", None)
            if bitrate is None:
                continue
            if best is None or bitrate > getattr(best, "bitrate", -1):
                best = vv
        if best is not None:
            url = getattr(best, "url", None)
            if isinstance(url, str) and url.strip():
                media_items.append(
                    {"kind": "video", "url": url.strip(), "bitrate": getattr(best, "bitrate", None)}
                )

    for a in getattr(media, "animated", []) or []:
        url = getattr(a, "videoUrl", None)
        if isinstance(url, str) and url.strip():
            media_items.append({"kind": "animated", "url": url.strip()})

    return media_items


def _is_unique_username_violation(exc: BaseException) -> bool:
    msg = f"{type(exc).__name__}: {exc}".lower()
    return "unique" in msg and "username" in msg


def _quote_sqlite_ident(ident: str) -> str:
    # Table/column names come from sqlite_master / PRAGMA, but still quote defensively.
    return f"\"{ident.replace('\"', '\"\"')}\""


def _try_update_twscrape_account_db(
    db_path: Path,
    *,
    username: str,
    cookies: str,
    user_agent: str,
) -> bool:
    if not db_path.exists() or not db_path.is_file():
        return False

    try:
        conn = sqlite3.connect(str(db_path), timeout=1.0)
    except sqlite3.Error:
        return False

    try:
        cur = conn.cursor()
        tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()

        for (table_name,) in tables:
            quoted_table = _quote_sqlite_ident(str(table_name))
            cols = cur.execute(f"PRAGMA table_info({quoted_table})").fetchall()
            col_names = {str(r[1]) for r in cols}

            if "username" not in col_names:
                continue

            cookie_col = "cookies" if "cookies" in col_names else ("cookie" if "cookie" in col_names else None)
            if cookie_col is None:
                continue

            set_parts = [f"{_quote_sqlite_ident(cookie_col)} = ?"]
            params: list[Any] = [cookies]

            if "user_agent" in col_names:
                set_parts.append(f"{_quote_sqlite_ident('user_agent')} = ?")
                params.append(user_agent)

            if "active" in col_names:
                set_parts.append(f"{_quote_sqlite_ident('active')} = ?")
                params.append(1)

            params.append(username)
            sql = (
                f"UPDATE {quoted_table} "
                f"SET {', '.join(set_parts)} "
                f"WHERE {_quote_sqlite_ident('username')} = ?"
            )

            cur.execute(sql, params)
            if cur.rowcount:
                conn.commit()
                return True

        return False
    except sqlite3.Error:
        return False
    finally:
        conn.close()


async def run(args: argparse.Namespace) -> int:
    try:
        from twscrape import API, NoAccountError  # type: ignore
        from twscrape.models import parse_tweets  # type: ignore
    except Exception as exc:
        print(
            "缺少依赖 twscrape（或其依赖未安装）。请先安装依赖后重试：\n"
            "  pip install -r requirements.txt\n"
            f"导入错误：{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2

    handle = (args.handle or "").strip().lstrip("@")
    if not handle:
        print("--handle 不能为空", file=sys.stderr)
        return 2

    creds = resolve_credentials(args)
    if not creds:
        print(
            "未找到可用凭证（需要 auth_token + ct0）。\n"
            "可选方式：\n"
            "- 通过 WebUI 保存凭证到 data/config.json\n"
            "- 或设置环境变量 XMC_AUTH_TOKEN / XMC_CT0\n"
            "- 或使用命令行参数 --auth-token / --ct0",
            file=sys.stderr,
        )
        return 2

    samples_dir = Path(args.samples_dir)
    out_dir = Path(args.out_dir)
    run_id = utc_run_id()
    log_path = samples_dir / f"{run_id}_{handle}_log.jsonl"
    report_path = samples_dir / f"{run_id}_{handle}_report.json"

    t0 = time.perf_counter()
    append_jsonl(
        log_path,
        {
            "ts": utc_now_str(),
            "event": "start",
            "handle": handle,
            "limit": args.limit,
            "credentials": creds.to_safe_debug_dict(),
        },
    )

    tmpdir_cm: Optional[tempfile.TemporaryDirectory[str]] = None
    accounts_db: Path
    if args.accounts_db:
        accounts_db = Path(args.accounts_db)
        accounts_db.parent.mkdir(parents=True, exist_ok=True)
    else:
        tmpdir_cm = tempfile.TemporaryDirectory(prefix="xmc_twscrape_")
        accounts_db = Path(tmpdir_cm.name) / "accounts.db"

    try:
        account_cookies = creds.to_cookie_string()
        existing_account_updated = _try_update_twscrape_account_db(
            accounts_db,
            username=args.account_username,
            cookies=account_cookies,
            user_agent=DEFAULT_USER_AGENT,
        )

        api = API(
            pool=str(accounts_db),
            debug=bool(args.debug),
            proxy=(args.proxy or None),
            raise_when_no_account=True,
        )

        if not existing_account_updated:
            try:
                await api.pool.add_account(
                    args.account_username,
                    "x",
                    "xmc@example.com",
                    "x",
                    cookies=account_cookies,
                    user_agent=DEFAULT_USER_AGENT,
                )
            except Exception as exc:
                if _is_unique_username_violation(exc) and _try_update_twscrape_account_db(
                    accounts_db,
                    username=args.account_username,
                    cookies=account_cookies,
                    user_agent=DEFAULT_USER_AGENT,
                ):
                    pass
                else:
                    raise

        user = await api.user_by_login(handle)
        if user is None:
            append_jsonl(
                log_path,
                {"ts": utc_now_str(), "event": "error", "stage": "user_by_login", "error": "not_found"},
            )
            return 1

        user_id = int(getattr(user, "id", 0) or 0)
        append_jsonl(
            log_path,
            {
                "ts": utc_now_str(),
                "event": "user_resolved",
                "handle": handle,
                "user_id": user_id,
                "user_url": getattr(user, "url", None),
            },
        )

        tweets: list[Any] = []
        saved_pages: list[str] = []
        raw_pages_saved = 0

        async with aclosing(api.user_media_raw(user_id, limit=-1)) as gen:
            async for rep in gen:
                if raw_pages_saved < int(args.save_pages):
                    raw_pages_saved += 1
                    sample_path = samples_dir / f"{run_id}_{handle}_user_media_p{raw_pages_saved}.json"
                    try:
                        sample_obj = redact_obj(rep.json())
                        atomic_write_json(sample_path, sample_obj)
                        saved_pages.append(str(sample_path))
                        append_jsonl(
                            log_path,
                            {
                                "ts": utc_now_str(),
                                "event": "saved_sample",
                                "path": str(sample_path),
                                "status_code": getattr(rep, "status_code", None),
                            },
                        )
                    except Exception as exc:
                        append_jsonl(
                            log_path,
                            {
                                "ts": utc_now_str(),
                                "event": "error",
                                "stage": "save_sample",
                                "error": f"{type(exc).__name__}: {exc}",
                            },
                        )

                for tw in parse_tweets(rep, limit=-1):
                    media_items = _flatten_media(tw)
                    if not media_items:
                        continue
                    tweets.append(tw)
                    if len(tweets) >= int(args.limit):
                        break

                if len(tweets) >= int(args.limit):
                    break

        append_jsonl(
            log_path,
            {
                "ts": utc_now_str(),
                "event": "tweets_collected",
                "count": len(tweets),
                "saved_pages": saved_pages,
            },
        )

        if args.dry_run:
            elapsed = time.perf_counter() - t0
            atomic_write_json(
                report_path,
                {
                    "run_id": run_id,
                    "started_at_utc": utc_now_str(),
                    "handle": handle,
                    "user_id": user_id,
                    "limit": args.limit,
                    "dry_run": True,
                    "tweets_with_media": len(tweets),
                    "saved_samples": saved_pages,
                    "elapsed_s": round(elapsed, 3),
                },
            )
            return 0

        handle_dir = out_dir / handle
        images_dir = handle_dir / "images"
        videos_dir = handle_dir / "videos"
        images_dir.mkdir(parents=True, exist_ok=True)
        videos_dir.mkdir(parents=True, exist_ok=True)

        total_bytes = 0
        counts = {"image": 0, "video": 0, "animated": 0, "failed": 0, "skipped": 0}
        seen_urls: set[str] = set()

        for tw in tweets:
            tweet_id = int(getattr(tw, "id", 0) or 0)
            media = _flatten_media(tw)
            if args.max_media_per_tweet and int(args.max_media_per_tweet) > 0:
                media = media[: int(args.max_media_per_tweet)]

            for idx, m in enumerate(media, start=1):
                url = str(m.get("url", "") or "")
                if not url or url in seen_urls:
                    counts["skipped"] += 1
                    continue
                seen_urls.add(url)

                kind = str(m.get("kind"))
                bitrate = m.get("bitrate")

                if kind == "image":
                    ext = _infer_ext_from_url(url, default="jpg")
                    dest = images_dir / f"{tweet_id}_img_{idx}.{ext}"
                elif kind == "video":
                    ext = _infer_ext_from_url(url, default="mp4")
                    br = str(int(bitrate)) if isinstance(bitrate, int) else "na"
                    dest = videos_dir / f"{tweet_id}_vid_{idx}_{br}.{ext}"
                else:
                    ext = _infer_ext_from_url(url, default="mp4")
                    dest = videos_dir / f"{tweet_id}_anim_{idx}.{ext}"

                started = time.perf_counter()
                ok, size, status, err = _download_with_retries(
                    url=url,
                    dest=dest,
                    user_agent=DEFAULT_USER_AGENT,
                    timeout_s=float(args.timeout_s),
                    retries=int(args.download_retries),
                    backoff_s=float(args.download_backoff_s),
                )
                elapsed = time.perf_counter() - started

                if ok and err != "exists":
                    counts[kind] = counts.get(kind, 0) + 1
                    total_bytes += int(size or 0)
                elif ok and err == "exists":
                    counts["skipped"] += 1
                else:
                    counts["failed"] += 1

                append_jsonl(
                    log_path,
                    {
                        "ts": utc_now_str(),
                        "event": "download",
                        "tweet_id": tweet_id,
                        "kind": kind,
                        "url": url,
                        "dest": str(dest),
                        "ok": ok,
                        "size": size,
                        "status": status,
                        "error": err,
                        "elapsed_s": round(elapsed, 3),
                    },
                )

                if float(args.sleep_s) > 0:
                    time.sleep(float(args.sleep_s))

        elapsed = time.perf_counter() - t0
        report = {
            "run_id": run_id,
            "handle": handle,
            "user_id": user_id,
            "limit": int(args.limit),
            "tweets_with_media": len(tweets),
            "saved_samples": saved_pages,
            "download_root": str(handle_dir),
            "counts": counts,
            "total_bytes": total_bytes,
            "elapsed_s": round(elapsed, 3),
        }
        atomic_write_json(report_path, report)
        append_jsonl(log_path, {"ts": utc_now_str(), "event": "done", "report_path": str(report_path)})
        return 0

    except NoAccountError as exc:
        append_jsonl(log_path, {"ts": utc_now_str(), "event": "error", "stage": "twscrape", "error": str(exc)})
        return 1
    except Exception as exc:
        append_jsonl(
            log_path,
            {
                "ts": utc_now_str(),
                "event": "error",
                "stage": "unknown",
                "error": f"{type(exc).__name__}: {exc}",
            },
        )
        return 1
    finally:
        if tmpdir_cm is not None:
            tmpdir_cm.cleanup()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="spike_scrape_sample",
        description="Spike：用登录 Cookies 访问 X 内部接口并抓取媒体推文样本（twscrape）",
    )

    p.add_argument("--handle", required=True, help="目标账号 handle（如 XDevelopers）")
    p.add_argument("--limit", type=int, default=50, help="目标：至少抓取多少条“含媒体”推文（默认 50）")

    p.add_argument("--config", default="data/config.json", help="Settings 配置文件路径（默认 data/config.json）")
    p.add_argument("--auth-token", default="", help="Cookie 字段 auth_token（优先于 config/env）")
    p.add_argument("--ct0", default="", help="Cookie 字段 ct0（优先于 config/env）")
    p.add_argument("--twid", default="", help="Cookie 字段 twid（可选；优先于 config/env）")

    p.add_argument("--samples-dir", default="artifacts/samples", help="保存 JSON 样本与日志目录")
    p.add_argument("--save-pages", type=int, default=3, help="保存前 N 个 UserMedia 原始响应样本（默认 3）")

    p.add_argument("--out-dir", default="artifacts/spike_downloads", help="下载媒体的输出根目录")
    p.add_argument("--dry-run", action="store_true", help="只抓取与保存样本，不下载媒体")
    p.add_argument("--max-media-per-tweet", type=int, default=0, help="每条推文最多下载多少个媒体（0=不限）")

    p.add_argument("--sleep-s", type=float, default=0.5, help="每次媒体下载之间的 sleep 秒数（默认 0.5）")
    p.add_argument("--timeout-s", type=float, default=30.0, help="单次下载超时秒数（默认 30）")
    p.add_argument("--download-retries", type=int, default=2, help="下载重试次数（默认 2）")
    p.add_argument("--download-backoff-s", type=float, default=1.5, help="下载重试指数退避基准秒数（默认 1.5）")

    p.add_argument("--proxy", default="", help="可选代理（传给 twscrape，例如 http://127.0.0.1:7890）")
    p.add_argument("--debug", action="store_true", help="开启 twscrape debug（会 dump 响应到 /tmp）")
    p.add_argument("--accounts-db", default="", help="twscrape accounts.db 路径（默认使用临时文件）")
    p.add_argument(
        "--account-username",
        default="xmc_cookie",
        help="twscrape 账号池中的 username（仅作为标识；Cookie 模式下可用默认值）",
    )
    return p


def main() -> int:
    args = build_parser().parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
