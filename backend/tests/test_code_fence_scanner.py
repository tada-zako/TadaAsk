from app.rag.utils.code_fence_scanner import CodeFenceScanner


def test_code_fence_scanner():
    """测试 CodeFenceScanner 是否正确识别文本中的代码块"""
    scanner = CodeFenceScanner()

    # 测试文本
    text = """
    这是一些文本。

    ```python
    def foo():
        return "bar"
    ```

    这是更多的文本。

    ```javascript
    function foo() {
        return "bar";
    }
    ```
    """

    code_fences = scanner.scan(text)

    assert len(code_fences) == 2
    assert (
        text[code_fences[0].start_pos : code_fences[0].end_pos]
        == """```python
                def foo():
                    return "bar"
                ```"""
    )
    assert (
        text[code_fences[1].start_pos : code_fences[1].end_pos]
        == """```javascript
                function foo() {
                    return "bar";
                }
                ```"""
    )
