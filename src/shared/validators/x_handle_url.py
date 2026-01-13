"""
X (Twitter) 账号 URL 严格校验与 handle 解析。

验收标准：
- 仅接受严格匹配 `https://x.com/<handle>`
- 不允许：末尾 /、query 参数、额外路径、twitter.com、@handle 格式
- 合法输入返回解析后的 handle
- 非法输入返回可理解的错误原因
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse


@dataclass(frozen=True)
class ValidationResult:
    """URL 校验结果"""

    valid: bool
    handle: Optional[str] = None
    error: Optional[str] = None

    def __bool__(self) -> bool:
        return self.valid


# X handle 合法字符：字母、数字、下划线，长度 1-15
# 参考：https://help.twitter.com/en/managing-your-account/twitter-username-rules
HANDLE_PATTERN = re.compile(r"^[A-Za-z0-9_]{1,15}$")


def validate_x_url(url: str) -> ValidationResult:
    """
    严格校验 X 账号 URL 并提取 handle。

    合法格式：https://x.com/<handle>
    - handle 仅包含字母、数字、下划线，长度 1-15
    - 不允许 http://、twitter.com、末尾 /、query 参数、额外路径段

    Args:
        url: 待校验的 URL 字符串

    Returns:
        ValidationResult: 包含 valid、handle（成功时）、error（失败时）
    """
    if not url:
        return ValidationResult(valid=False, error="URL 不能为空")

    url = url.strip()

    if not url:
        return ValidationResult(valid=False, error="URL 不能为空")

    # 检查是否以 @ 开头（@handle 格式）
    if url.startswith("@"):
        return ValidationResult(
            valid=False,
            error="请输入完整 URL，不要使用 @handle 格式（应为 https://x.com/handle）"
        )

    # 尝试解析 URL
    try:
        parsed = urlparse(url)
    except Exception:
        return ValidationResult(valid=False, error="URL 格式无效")

    # 检查 scheme（必须是 https）
    if parsed.scheme != "https":
        if parsed.scheme == "http":
            return ValidationResult(
                valid=False,
                error="请使用 https:// 协议（不支持 http://）"
            )
        if not parsed.scheme:
            return ValidationResult(
                valid=False,
                error="URL 缺少协议，应为 https://x.com/handle"
            )
        return ValidationResult(
            valid=False,
            error=f"不支持的协议 {parsed.scheme}://，请使用 https://"
        )

    # 检查域名（必须是 x.com）
    netloc_lower = parsed.netloc.lower()
    if netloc_lower != "x.com":
        if netloc_lower in ("twitter.com", "www.twitter.com"):
            return ValidationResult(
                valid=False,
                error="请使用 x.com 域名（不支持 twitter.com）"
            )
        if netloc_lower == "www.x.com":
            return ValidationResult(
                valid=False,
                error="请使用 x.com 域名（不要带 www）"
            )
        return ValidationResult(
            valid=False,
            error=f"域名必须是 x.com（当前为 {parsed.netloc}）"
        )

    # 检查 query 参数（不允许）
    if parsed.query:
        return ValidationResult(
            valid=False,
            error="URL 不能包含查询参数（? 后的内容）"
        )

    # 检查 fragment（不允许）
    if parsed.fragment:
        return ValidationResult(
            valid=False,
            error="URL 不能包含锚点（# 后的内容）"
        )

    # 解析路径
    path = parsed.path

    # 检查末尾斜杠
    if path.endswith("/") and len(path) > 1:
        return ValidationResult(
            valid=False,
            error="URL 末尾不能有斜杠 /"
        )

    # 去掉开头的 /
    if path.startswith("/"):
        path = path[1:]

    # 检查是否为空路径
    if not path:
        return ValidationResult(
            valid=False,
            error="缺少用户名，请输入完整 URL（如 https://x.com/elonmusk）"
        )

    # 检查是否有额外路径段
    if "/" in path:
        return ValidationResult(
            valid=False,
            error="URL 包含额外路径（如 /media、/likes 等），请仅保留账号主页 URL"
        )

    # 此时 path 应该就是 handle
    handle = path

    # 校验 handle 格式
    if not HANDLE_PATTERN.match(handle):
        # 检查具体原因
        if len(handle) > 15:
            return ValidationResult(
                valid=False,
                error=f"用户名过长（最多 15 字符，当前 {len(handle)} 字符）"
            )
        if not handle:
            return ValidationResult(
                valid=False,
                error="用户名不能为空"
            )
        # 检查非法字符
        invalid_chars = set(re.findall(r"[^A-Za-z0-9_]", handle))
        if invalid_chars:
            return ValidationResult(
                valid=False,
                error=f"用户名包含非法字符：{', '.join(sorted(invalid_chars))}（仅允许字母、数字、下划线）"
            )
        return ValidationResult(
            valid=False,
            error="用户名格式无效（仅允许字母、数字、下划线，长度 1-15）"
        )

    return ValidationResult(valid=True, handle=handle)
