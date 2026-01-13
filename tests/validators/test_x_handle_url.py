"""
为账号 URL 严格校验补齐自动化测试用例。

验收标准：
1. 测试通过：https://x.com/shanghaixc2
2. 测试失败：末尾 /、twitter.com、带 query、@handle、额外路径 /media
3. 失败用例断言包含具体错误原因（可面向用户展示）
"""

import unittest

from src.shared.validators.x_handle_url import ValidationResult, validate_x_url


class TestValidateXUrl(unittest.TestCase):
    """X 账号 URL 严格校验测试"""

    # -------------------------------------------------------------------------
    # 合法 URL 测试
    # -------------------------------------------------------------------------

    def test_valid_url_basic(self) -> None:
        """验收: https://x.com/shanghaixc2 应通过"""
        result = validate_x_url("https://x.com/shanghaixc2")
        self.assertTrue(result.valid)
        self.assertEqual(result.handle, "shanghaixc2")
        self.assertIsNone(result.error)

    def test_valid_url_short_handle(self) -> None:
        """单字符 handle 应通过"""
        result = validate_x_url("https://x.com/a")
        self.assertTrue(result.valid)
        self.assertEqual(result.handle, "a")

    def test_valid_url_max_length_handle(self) -> None:
        """15 字符 handle（最大长度）应通过"""
        result = validate_x_url("https://x.com/abcdefghij12345")
        self.assertTrue(result.valid)
        self.assertEqual(result.handle, "abcdefghij12345")

    def test_valid_url_underscore_handle(self) -> None:
        """包含下划线的 handle 应通过"""
        result = validate_x_url("https://x.com/user_name_123")
        self.assertTrue(result.valid)
        self.assertEqual(result.handle, "user_name_123")

    def test_valid_url_numeric_handle(self) -> None:
        """纯数字 handle 应通过"""
        result = validate_x_url("https://x.com/123456789")
        self.assertTrue(result.valid)
        self.assertEqual(result.handle, "123456789")

    def test_valid_url_with_whitespace_trimmed(self) -> None:
        """前后空白应被自动去除"""
        result = validate_x_url("  https://x.com/testuser  ")
        self.assertTrue(result.valid)
        self.assertEqual(result.handle, "testuser")

    def test_valid_url_case_preserved(self) -> None:
        """handle 大小写应保留"""
        result = validate_x_url("https://x.com/ElonMusk")
        self.assertTrue(result.valid)
        self.assertEqual(result.handle, "ElonMusk")

    # -------------------------------------------------------------------------
    # 非法 URL 测试 - 末尾斜杠
    # -------------------------------------------------------------------------

    def test_invalid_trailing_slash(self) -> None:
        """验收: 末尾 / 应失败"""
        result = validate_x_url("https://x.com/shanghaixc2/")
        self.assertFalse(result.valid)
        self.assertIsNone(result.handle)
        self.assertIsNotNone(result.error)
        self.assertIn("斜杠", result.error)

    # -------------------------------------------------------------------------
    # 非法 URL 测试 - twitter.com 域名
    # -------------------------------------------------------------------------

    def test_invalid_twitter_com(self) -> None:
        """验收: twitter.com 应失败"""
        result = validate_x_url("https://twitter.com/shanghaixc2")
        self.assertFalse(result.valid)
        self.assertIsNone(result.handle)
        self.assertIsNotNone(result.error)
        self.assertIn("x.com", result.error)
        self.assertIn("twitter.com", result.error)

    def test_invalid_www_twitter_com(self) -> None:
        """www.twitter.com 应失败"""
        result = validate_x_url("https://www.twitter.com/shanghaixc2")
        self.assertFalse(result.valid)
        self.assertIn("twitter.com", result.error)

    # -------------------------------------------------------------------------
    # 非法 URL 测试 - Query 参数
    # -------------------------------------------------------------------------

    def test_invalid_with_query_params(self) -> None:
        """验收: 带 query 参数应失败"""
        result = validate_x_url("https://x.com/shanghaixc2?ref=home")
        self.assertFalse(result.valid)
        self.assertIsNone(result.handle)
        self.assertIsNotNone(result.error)
        self.assertIn("查询参数", result.error)

    def test_invalid_with_empty_query(self) -> None:
        """带空 query 参数（尾部 ?）也应失败"""
        result = validate_x_url("https://x.com/shanghaixc2?")
        self.assertFalse(result.valid)
        self.assertIsNone(result.handle)
        self.assertIsNotNone(result.error)
        self.assertIn("查询参数", result.error)

    def test_invalid_with_multiple_query_params(self) -> None:
        """多个 query 参数应失败"""
        result = validate_x_url("https://x.com/shanghaixc2?a=1&b=2")
        self.assertFalse(result.valid)
        self.assertIn("查询参数", result.error)

    # -------------------------------------------------------------------------
    # 非法 URL 测试 - @handle 格式
    # -------------------------------------------------------------------------

    def test_invalid_at_handle_format(self) -> None:
        """验收: @handle 格式应失败"""
        result = validate_x_url("@shanghaixc2")
        self.assertFalse(result.valid)
        self.assertIsNone(result.handle)
        self.assertIsNotNone(result.error)
        self.assertIn("@handle", result.error)
        self.assertIn("https://x.com/", result.error)

    def test_invalid_at_handle_with_space(self) -> None:
        """带空格的 @handle 应失败"""
        result = validate_x_url("@ shanghaixc2")
        self.assertFalse(result.valid)
        self.assertIn("@handle", result.error)

    # -------------------------------------------------------------------------
    # 非法 URL 测试 - 额外路径
    # -------------------------------------------------------------------------

    def test_invalid_extra_path_media(self) -> None:
        """验收: /media 额外路径应失败"""
        result = validate_x_url("https://x.com/shanghaixc2/media")
        self.assertFalse(result.valid)
        self.assertIsNone(result.handle)
        self.assertIsNotNone(result.error)
        self.assertIn("额外路径", result.error)

    def test_invalid_extra_path_likes(self) -> None:
        """/likes 额外路径应失败"""
        result = validate_x_url("https://x.com/shanghaixc2/likes")
        self.assertFalse(result.valid)
        self.assertIn("额外路径", result.error)

    def test_invalid_extra_path_status(self) -> None:
        """/status/<id> 额外路径应失败"""
        result = validate_x_url("https://x.com/shanghaixc2/status/123456789")
        self.assertFalse(result.valid)
        self.assertIn("额外路径", result.error)

    def test_invalid_extra_path_with_replies(self) -> None:
        """/with_replies 额外路径应失败"""
        result = validate_x_url("https://x.com/shanghaixc2/with_replies")
        self.assertFalse(result.valid)
        self.assertIn("额外路径", result.error)

    # -------------------------------------------------------------------------
    # 其他非法 URL 测试
    # -------------------------------------------------------------------------

    def test_invalid_empty_url(self) -> None:
        """空 URL 应失败"""
        result = validate_x_url("")
        self.assertFalse(result.valid)
        self.assertIn("空", result.error)

    def test_invalid_whitespace_only(self) -> None:
        """仅空白字符应失败"""
        result = validate_x_url("   ")
        self.assertFalse(result.valid)
        self.assertIn("空", result.error)

    def test_invalid_http_protocol(self) -> None:
        """http:// 协议应失败"""
        result = validate_x_url("http://x.com/shanghaixc2")
        self.assertFalse(result.valid)
        self.assertIn("https", result.error)

    def test_invalid_www_x_com(self) -> None:
        """www.x.com 应失败"""
        result = validate_x_url("https://www.x.com/shanghaixc2")
        self.assertFalse(result.valid)
        self.assertIn("www", result.error)

    def test_invalid_missing_handle(self) -> None:
        """缺少 handle 应失败"""
        result = validate_x_url("https://x.com/")
        self.assertFalse(result.valid)
        # Should mention missing username or trailing slash
        self.assertTrue(result.error is not None)

    def test_invalid_root_url_only(self) -> None:
        """仅根 URL 应失败"""
        result = validate_x_url("https://x.com")
        self.assertFalse(result.valid)
        self.assertIn("用户名", result.error)

    def test_invalid_handle_too_long(self) -> None:
        """超过 15 字符的 handle 应失败"""
        result = validate_x_url("https://x.com/abcdefghij123456")  # 16 chars
        self.assertFalse(result.valid)
        self.assertIn("过长", result.error)

    def test_invalid_handle_with_special_chars(self) -> None:
        """包含特殊字符的 handle 应失败"""
        result = validate_x_url("https://x.com/user-name")
        self.assertFalse(result.valid)
        self.assertIn("非法字符", result.error)

    def test_invalid_handle_with_chinese(self) -> None:
        """包含中文字符的 handle 应失败"""
        result = validate_x_url("https://x.com/用户名")
        self.assertFalse(result.valid)
        self.assertIn("非法字符", result.error)

    def test_invalid_with_fragment(self) -> None:
        """带锚点(#)应失败"""
        result = validate_x_url("https://x.com/shanghaixc2#section")
        self.assertFalse(result.valid)
        self.assertIn("锚点", result.error)

    def test_invalid_other_domain(self) -> None:
        """其他域名应失败"""
        result = validate_x_url("https://facebook.com/shanghaixc2")
        self.assertFalse(result.valid)
        self.assertIn("x.com", result.error)

    def test_invalid_no_protocol(self) -> None:
        """无协议应失败"""
        result = validate_x_url("x.com/shanghaixc2")
        self.assertFalse(result.valid)
        # Should indicate missing protocol or scheme

    # -------------------------------------------------------------------------
    # ValidationResult 行为测试
    # -------------------------------------------------------------------------

    def test_validation_result_bool_true(self) -> None:
        """ValidationResult valid=True 时 bool 为 True"""
        result = ValidationResult(valid=True, handle="test")
        self.assertTrue(bool(result))

    def test_validation_result_bool_false(self) -> None:
        """ValidationResult valid=False 时 bool 为 False"""
        result = ValidationResult(valid=False, error="test error")
        self.assertFalse(bool(result))


class TestErrorMessagesUserFriendly(unittest.TestCase):
    """验证错误消息对用户友好、可理解"""

    def test_error_messages_are_chinese(self) -> None:
        """错误消息应为中文，便于用户理解"""
        test_cases = [
            "",  # empty
            "@handle",  # @handle format
            "https://twitter.com/user",  # twitter.com
            "https://x.com/user/",  # trailing slash
            "https://x.com/user?q=1",  # query params
            "https://x.com/user/media",  # extra path
        ]
        for url in test_cases:
            result = validate_x_url(url)
            if not result.valid:
                # Check error contains Chinese characters
                has_chinese = any('\u4e00' <= char <= '\u9fff' for char in (result.error or ""))
                self.assertTrue(
                    has_chinese,
                    f"URL '{url}' 的错误消息应包含中文: {result.error}"
                )

    def test_error_messages_not_technical(self) -> None:
        """错误消息不应包含过于技术性的术语"""
        technical_terms = ["exception", "error code", "null", "undefined", "traceback"]
        test_urls = [
            "",
            "@test",
            "https://twitter.com/test",
            "https://x.com/test/",
            "https://x.com/test?a=1",
        ]
        for url in test_urls:
            result = validate_x_url(url)
            if not result.valid and result.error:
                error_lower = result.error.lower()
                for term in technical_terms:
                    self.assertNotIn(
                        term,
                        error_lower,
                        f"错误消息不应包含技术术语 '{term}': {result.error}"
                    )


if __name__ == "__main__":
    unittest.main()
