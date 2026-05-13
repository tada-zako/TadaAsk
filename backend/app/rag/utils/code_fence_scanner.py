from dataclasses import dataclass


@dataclass
class CodeFence:
    """代码块数据类"""

    start_pos: int  # 代码块起始位置
    end_pos: int  # 代码块结束位置


class CodeFenceScanner:
    """
    扫描文本中的代码块，提取代码块的起始和结束位置。
    NOTE: 只支持 Markdown 风格的代码块（即以 ``` 开始和结束的代码块），不支持行内代码块。
    """

    def scan(self, text: str) -> list[CodeFence]:
        """扫描输入文本，返回代码块列表"""
        code_fences: list[CodeFence] = []
        pos = 0
        in_fence = False

        while True:
            start_pos = text.find("```", pos)
            if start_pos == -1:
                break
            in_fence = True  # 切换代码块状态

            end_pos = text.find("```", start_pos + 3)
            if end_pos == -1:
                break

            code_fences.append(CodeFence(start_pos=start_pos, end_pos=end_pos + 3))
            pos = end_pos + 3
            in_fence = False  # 切换代码块状态

        # 处理未闭合的代码块
        if in_fence:
            code_fences.append(CodeFence(start_pos=start_pos, end_pos=len(text)))

        return code_fences
