from dataclasses import dataclass
import re


@dataclass
class Breakpoint:
    """断点数据类"""

    pos: int  # 断点在文本中的位置
    score: float  # 断点优先级评分，数值越大优先级越高
    type: str  # 断点类型，例如 'newline', 'punctuation', 'space' 等


class MarkdownBreakpointScanner:
    """扫描文本中的Markdown断点位置，支持代码块、标题、段落等"""

    def __init__(self) -> None:
        self.breakpoint_patterns = [
            (r"\n#{1}(?!#)", 100, "markdown_h1"),  # 一级标题
            (r"\n#{2}(?!#)", 90, "markdown_h2"),  # 二级标题
            (r"\n#{3}(?!#)", 80, "markdown_h3"),  # 三级标题
            (r"\n#{4}(?!#)", 70, "markdown_h4"),  # 四级标题
            (r"\n#{5}(?!#)", 60, "markdown_h5"),  # 五级标题
            (r"\n#{6}(?!#)", 50, "markdown_h6"),  # 六级标题
            (r"\n```", 80, "markdown_code_fence"),  # 代码块
            (r"\n(?:---|\*\*\*|___)\s*\n", 60, "markdown_hr"),  # 分割线
            (r"\n\n+", 20, "markdown_blank"),  # 多个换行符
            (r"\n[-*]\s", 5, "markdown_list"),  # 无序列表
            (r"\n\d+\.\s", 5, "markdown_olist"),  # 有序列表
            (r"\n", 1, "newline"),  # 换行符
        ]

    def scan(self, text: str) -> list[Breakpoint]:
        """扫描输入文本，返回断点列表"""
        seen: dict[int, Breakpoint] = {}  # pos -> Breakpoint

        for pattern, score, bp_type in self.breakpoint_patterns:
            for match in re.finditer(pattern, text):
                pos = match.start()

                # 如果位置已存在，则保留评分更高的断点
                if pos not in seen or score > seen[pos].score:
                    seen[pos] = Breakpoint(pos=pos, score=score, type=bp_type)

        # 按位置排序断点列表
        breakpoints = sorted(seen.values(), key=lambda x: x.pos)
        return breakpoints


class ASTBreakpointScanner:
    """扫描代码文本中的断点位置，基于抽象语法树（AST）分析"""

    ...
