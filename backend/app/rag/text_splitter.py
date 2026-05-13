from typing import Protocol
from dataclasses import dataclass

from loguru import logger

from app.core.config import settings


@dataclass
class TextChunk:
    """文本块数据类"""

    content: str
    pos: int  # 切片在原始文档中的起始位置
    metadata: dict[str, str] | None = None


@dataclass
class Breakpoint:
    """断点数据类"""

    pos: int  # 断点在文本中的位置
    score: float  # 断点优先级评分，数值越大优先级越高
    type: str  # 断点类型，例如 'newline', 'punctuation', 'space' 等


@dataclass
class CodeFence:
    """代码块数据类"""

    start_pos: int  # 代码块起始位置
    end_pos: int  # 代码块结束位置


class TextSplitter(Protocol):
    def split_text(self, text: str) -> list[TextChunk]:
        """将输入文本切割成多个块，返回切割后的文本块列表"""
        ...


class RecursiveCharacterTextSplitter: ...


class TokenAwareTextSplitter:
    """基于Token的文本切割器：适用于自然语言文本的切割，优先在Token边界进行切割"""

    ...


class ASTAwareTextSplitter:
    """基于抽象语法树（AST）的文本切割器：适用于代码文本的切割"""

    ...


class BreakpointAwareTextSplitter:
    """基于断点的文本切割器，优先在指定断点进行切割"""

    def __init__(
        self,
        breakpoints: list[Breakpoint],
        code_fences: list[CodeFence],
        chunk_size: int = settings.chunk_size_chars,
        chunk_overlap: int = settings.chunk_overlap_chars,
        window_size: int = settings.chunk_window_chars,
    ):
        """
        Args:
            breakpoints: 断点列表，切割器将基于 breakpoint.score 在这些位置进行切割
            code_fences: 代码块列表，切割器将避免在代码块内进行切割
            chunk_size: 目标文本块大小（字符数）
            chunk_overlap: 文本块之间的重叠大小（字符数）
            window_size: 切割窗口大小（字符数），在窗口范围内寻找切割点
        """
        self.breakpoints = breakpoints
        self.code_fences = code_fences
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.window_size = window_size

        # 确保配置合法
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"Overlap tokens ({self.chunk_overlap}) must be less than chunk size tokens "
                f"({self.chunk_size})"
            )
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"Overlap chars ({self.chunk_overlap}) must be less than chunk size chars "
                f"({self.chunk_size})"
            )

        if self.window_size >= self.chunk_size:
            logger.warning(
                "Window size is larger than chunk size, checking if this is intentional."
            )

    def is_within_code_fence(self, pos: int) -> bool:
        """判断给定位置是否在代码块内"""
        for fence in self.code_fences:
            if fence.start_pos <= pos < fence.end_pos:
                return True
        return False

    def _find_best_breakpoint(
        self, target_pos: int, bp_ptr: int, decay_factor: float = 0.7
    ) -> tuple[int, int]:
        """
        在 target_pos 左侧的窗口范围内寻找最佳断点位置。
        断点优先级评分根据距离 target_pos 远近进行衰减，
            计算方式为：
                score = breakpoint.score * (1 - ((distance / window_size) ** 2) * decay_factor)

        Args:
            target_pos: 目标切割位置
            bp_ptr: 断点扫描游标
            decay_factor: 衰减因子，数值越大表示距离越远的断点优先级衰减越快

        Returns:
            最佳断点位置，如果没有合适的断点则返回 target_pos
            以及更新后的断点扫描游标位置
        """
        window_start = max(0, target_pos - self.window_size)
        best_score = -1.0
        best_pos = target_pos

        # 将游标推进到窗口起始位置，跳过已确定落后于窗口的断点
        while (
            bp_ptr < len(self.breakpoints)
            and self.breakpoints[bp_ptr].pos < window_start
        ):
            bp_ptr += 1

        for i in range(bp_ptr, len(self.breakpoints)):
            bp = self.breakpoints[i]
            if bp.pos >= target_pos:
                break  # 断点超过目标位置，停止搜索

            if self.is_within_code_fence(bp.pos):
                continue  # 断点在代码块内，跳过

            # 计算衰减后的评分
            distance = target_pos - bp.pos
            multiplier = 1 - ((distance / self.window_size) ** 2) * decay_factor
            score = bp.score * multiplier

            if score > best_score:
                best_score = score
                best_pos = bp.pos

        return best_pos, bp_ptr

    def split_text(self, text: str) -> list[TextChunk]:
        """将输入文本切割成多个块，返回切割后的文本块列表"""

        chunks: list[TextChunk] = []
        char_pos = 0  # 当前字符位置
        bp_ptr = 0  # 断点扫描游标

        while char_pos < len(text):
            target_end = min(char_pos + self.chunk_size, len(text))
            end_pos = target_end

            if target_end < len(text):
                # 寻找最合适的断点位置
                best_bp_pos, bp_ptr = self._find_best_breakpoint(
                    target_end, bp_ptr=bp_ptr, decay_factor=0.7
                )

                if best_bp_pos > char_pos and best_bp_pos <= target_end:
                    end_pos = best_bp_pos
                else:
                    end_pos = target_end

            chunks.append(TextChunk(content=text[char_pos:end_pos], pos=char_pos))

            if end_pos >= len(text):
                # 已到达文本末尾，切割完成
                break
            # 更新下一个块的起始位置，考虑重叠
            char_pos = end_pos - self.chunk_overlap

        return chunks
