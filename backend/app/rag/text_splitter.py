from typing import Protocol, Literal
from dataclasses import dataclass

from loguru import logger

from .utils import (
    MarkdownBreakpointScanner,
    CodeFenceScanner,
    Breakpoint,
    CodeFence,
    EmbeddingTokenizer,
)
from app.core.config import settings


AVG_CHARS_PER_TOKEN_ESTIMATE = 3  # 粗略估计平均每个 token 约为 3 个字符


@dataclass
class TextChunk:
    """文本块数据类"""

    content: str
    pos: int  # 切片在原始文档中的起始位置


class TextSplitter(Protocol):
    async def split_text(
        self,
        text: str,
        file_path: str,
    ) -> list[TextChunk]:
        """将输入文本切割成多个块，返回切割后的文本块列表"""
        ...


class RecursiveCharacterTextSplitter: ...


class TokenAwareTextSplitter:
    """基于Token的文本切割器：适用于自然语言文本的切割，优先在Token边界进行切割"""

    def __init__(
        self,
        tokenizer: EmbeddingTokenizer,
        chunk_tokens: int = settings.chunk_size_tokens,
        overlap_tokens: int = settings.chunk_overlap_tokens,
        window_tokens: int = settings.chunk_window_tokens,
        splitter_strategy: Literal["ast", "markdown"] = "ast",
    ):
        """
        Args:
            tokenizer: Tokenizer 实例，用于计算文本的 Token 数和进行 Token 切割
            chunk_tokens: 目标文本块大小（Token 数）
            overlap_tokens: 文本块之间的重叠大小（Token 数）
            window_tokens: 切割窗口大小（Token 数），在窗口范围内寻找切割点
            splitter_strategy: 断点扫描策略，可调整不使用 AST 断点扫描，可选值为 "ast" 或 "markdown"
        """
        self.tokenizer = tokenizer
        self.chunk_tokens = chunk_tokens
        self.overlap_tokens = overlap_tokens
        self.window_tokens = window_tokens
        self.splitter_strategy: Literal["ast", "markdown"] = splitter_strategy

        # 确保配置合法
        if self.overlap_tokens >= self.chunk_tokens:
            raise ValueError(
                f"Overlap tokens ({self.overlap_tokens}) must be less than chunk size tokens "
                f"({self.chunk_tokens})"
            )

        if self.window_tokens >= self.chunk_tokens:
            logger.warning(
                "Window size is larger than chunk size, checking if this is intentional."
            )

        # 实例化 ASTAware 文本切割引擎，复用内部处理逻辑
        self.ast_engine = _ASTAwareSplittingEngine(splitter_strategy=splitter_strategy)

    async def _push_chunk_with_token_limit(
        self, chunk: TextChunk, final_chunks: list[TextChunk], file_path: str
    ):
        tokens = self.tokenizer.tokenize(chunk.content)
        if len(tokens) <= self.chunk_tokens or len(tokens) <= 1:
            final_chunks.append(chunk)
            return

        # 如果块的 Token 数超过上限，则进一步切割
        actual_char_per_token = len(chunk.content) / len(tokens)
        safe_chunk_size_chars = max(
            1,
            min(
                len(chunk.content) - 1,
                int(self.chunk_tokens * actual_char_per_token * 0.95),
            ),  # 留出一定余量避免切割点过于接近边界
        )
        safe_chunk_overlap_chars = int(
            self.overlap_tokens * actual_char_per_token * 0.5
        )  # 重叠部分折半处理 —— 经验主义...
        safe_window_size_chars = int(self.window_tokens * actual_char_per_token * 0.5)

        # 重新进行断点切割
        sub_chunks = await self.ast_engine.split(
            chunk.content,
            file_path,
            chunk_size=safe_chunk_size_chars,
            chunk_overlap=safe_chunk_overlap_chars,
            window_size=safe_window_size_chars,
            splitter_strategy="markdown",  # 内部切割时仅使用 Markdown 断点扫描，避免过度切割
        )

        # 回落机制：如果切割结果失效，执行 Token 暴力切割
        if len(sub_chunks) == 1 and len(sub_chunks[0].content) == len(chunk.content):
            logger.debug(
                f"Chunk at pos {chunk.pos} with length {len(chunk.content)} chars "
                f"exceeds token limit but no breakpoints found, applying token-based fallback."
            )
            fallback_tokens = tokens[: self.chunk_tokens]
            fallback_content = self.tokenizer.detokenize(fallback_tokens)
            final_chunks.append(
                TextChunk(
                    content=fallback_content,
                    pos=chunk.pos,
                )
            )
            # 放弃当前块剩余部分的切割，直接返回
            return

        # 正常递归
        for sub_chunk in sub_chunks:
            await self._push_chunk_with_token_limit(
                TextChunk(
                    content=sub_chunk.content,
                    pos=chunk.pos + sub_chunk.pos,
                ),
                final_chunks,
                file_path,
            )

    async def split_text(
        self,
        text: str,
        file_path: str,
    ) -> list[TextChunk]:
        """将输入文本切割成多个块，返回切割后的文本块列表"""

        # 初步调用 ASTAwareTextSplitter 获取基于断点切割的文本块
        initial_chunks = await self.ast_engine.split(
            text,
            file_path,
            chunk_size=self.chunk_tokens * AVG_CHARS_PER_TOKEN_ESTIMATE,
            chunk_overlap=self.overlap_tokens * AVG_CHARS_PER_TOKEN_ESTIMATE,
            window_size=self.window_tokens * AVG_CHARS_PER_TOKEN_ESTIMATE,
            splitter_strategy=self.splitter_strategy,
        )

        # 进一步基于 Token 上限进行切割，确保每个块的 Token 数不超过 chunk_size
        final_chunks: list[TextChunk] = []

        # 递归处理初步切割结果
        for chunk in initial_chunks:
            await self._push_chunk_with_token_limit(chunk, final_chunks, file_path)
        return final_chunks


class ASTAwareTextSplitter:
    """基于抽象语法树（AST）的文本切割器：适用于代码文本的切割"""

    def __init__(
        self,
        chunk_size: int = settings.chunk_size_chars,
        chunk_overlap: int = settings.chunk_overlap_chars,
        window_size: int = settings.chunk_window_chars,
        splitter_strategy: Literal["ast", "markdown"] = "ast",
    ):
        """
        Args:
            chunk_size: 目标文本块大小（字符数）
            chunk_overlap: 文本块之间的重叠大小（字符数）
            window_size: 切割窗口大小（字符数），在窗口范围内寻找切割点
            splitter_strategy: 断点扫描策略，可调整不使用 AST 断点扫描，可选值为 "ast" 或 "markdown"
        """

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.window_size = window_size
        self.splitter_strategy: Literal["ast", "markdown"] = splitter_strategy

        # 确保配置合法
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"Overlap tokens ({self.chunk_overlap}) must be less than chunk size tokens "
                f"({self.chunk_size})"
            )
        if self.window_size >= self.chunk_size:
            logger.warning(
                "Window size is larger than chunk size, checking if this is intentional."
            )

        # 实例化基于断点的文本切割器
        self.breakpoint_engine = _ASTAwareSplittingEngine(splitter_strategy)

    async def split_text(self, text: str, file_path: str) -> list[TextChunk]:
        return await self.breakpoint_engine.split(
            text, file_path, self.chunk_size, self.chunk_overlap, self.window_size
        )


class _ASTAwareSplittingEngine:
    """基于断点的文本切割引擎（内部组件，不对外暴露）"""

    def __init__(self, splitter_strategy: Literal["ast", "markdown"] = "ast"):
        self.splitter_strategy: Literal["ast", "markdown"] = splitter_strategy

        # 断点扫描器实例
        self.markdown_scanner = MarkdownBreakpointScanner()
        self.code_fence_scanner = CodeFenceScanner()

        if splitter_strategy == "ast":
            from .utils import ASTBreakpointScanner

            self.ast_scanner: ASTBreakpointScanner | None = ASTBreakpointScanner()
        else:
            self.ast_scanner = None

        # 实例化基于断点的文本切割器
        self.breakpoint_engine = _BreakpointAwareSplittingEngine()

    def _merge_breakpoints(
        self, markdown_bps: list[Breakpoint], ast_bps: list[Breakpoint]
    ) -> list[Breakpoint]:
        """
        合并 Markdown 和 AST 断点列表。
        基于 score 进行去重，并基于位置进行排序。
        """
        bp_seen = {}

        for bp in markdown_bps:
            bp_seen[bp.pos] = bp

        for bp in ast_bps:
            if bp.pos not in bp_seen:
                bp_seen[bp.pos] = bp
            else:
                # 如果位置相同，保留评分更高的断点
                if bp.score > bp_seen[bp.pos].score:
                    bp_seen[bp.pos] = bp

        # 返回按位置排序的断点列表
        return sorted(bp_seen.values(), key=lambda x: x.pos)

    async def split(
        self,
        text: str,
        file_path: str,
        chunk_size: int,
        chunk_overlap: int,
        window_size: int,
        splitter_strategy: Literal["ast", "markdown"] | None = None,
    ) -> list[TextChunk]:
        """将输入文本切割成多个块，返回切割后的文本块列表"""

        # 覆盖实例级别的切割策略
        splitter_strategy = splitter_strategy or self.splitter_strategy

        # 获取预扫描的断点和代码块信息
        markdown_breakpoints = self.markdown_scanner.scan(text)
        code_fences = self.code_fence_scanner.scan(text)

        breakpoints = markdown_breakpoints
        if splitter_strategy == "ast":
            if self.ast_scanner is None:
                raise RuntimeError(
                    "Engine initialized with strategy='markdown' but split() called with "
                    "strategy='ast'. Re-initialize _ASTAwareSplittingEngine with strategy='ast'."
                )
            ast_breakpoints = await self.ast_scanner.scan(text, file_path)

            if ast_breakpoints:
                # 合并断点列表，去重并按位置排序
                breakpoints = self._merge_breakpoints(
                    markdown_breakpoints, ast_breakpoints
                )

        # 基于断点进行切割
        return self.breakpoint_engine.split(
            text, chunk_size, chunk_overlap, window_size, breakpoints, code_fences
        )


class _BreakpointAwareSplittingEngine:
    """
    基于断点的文本切割引擎，提供核心的切割逻辑和算法实现
    作为 ASTAwareTextSplitter 和 TokenAwareTextSplitter 的内部组件
    不对外暴露
    """

    def is_within_code_fence(self, pos: int, code_fences: list[CodeFence]) -> bool:
        """判断给定位置是否在代码块内"""
        for fence in code_fences:
            if fence.start_pos <= pos < fence.end_pos:
                return True
        return False

    def _find_best_breakpoint(
        self,
        breakpoints: list[Breakpoint],
        code_fences: list[CodeFence],
        target_pos: int,
        bp_ptr: int,
        window_size: int,
        decay_factor: float = 0.7,
    ) -> tuple[int, int]:
        """
        在 target_pos 左侧的窗口范围内寻找最佳断点位置。
        断点优先级评分根据距离 target_pos 远近进行衰减，
            计算方式为：
                score = breakpoint.score * (1 - ((distance / window_size) ** 2) * decay_factor)

        Args:
            breakpoints: 断点列表
            code_fences: 代码块列表
            target_pos: 目标切割位置
            bp_ptr: 断点扫描游标
            window_size: 窗口大小，外部传入
            decay_factor: 衰减因子，数值越大表示距离越远的断点优先级衰减越快

        Returns:
            最佳断点位置，如果没有合适的断点则返回 target_pos
            以及更新后的断点扫描游标位置
        """
        window_start = max(0, target_pos - window_size)
        best_score = -1.0
        best_pos = target_pos

        # 将游标推进到窗口起始位置，跳过已确定落后于窗口的断点
        while bp_ptr < len(breakpoints) and breakpoints[bp_ptr].pos < window_start:
            bp_ptr += 1

        for i in range(bp_ptr, len(breakpoints)):
            bp = breakpoints[i]
            if bp.pos >= target_pos:
                break  # 断点超过目标位置，停止搜索

            if self.is_within_code_fence(bp.pos, code_fences):
                continue  # 断点在代码块内，跳过

            # 计算衰减后的评分
            distance = target_pos - bp.pos
            multiplier = 1 - ((distance / window_size) ** 2) * decay_factor
            score = bp.score * multiplier

            if score > best_score:
                best_score = score
                best_pos = bp.pos

        return best_pos, bp_ptr

    def split(
        self,
        text: str,
        chunk_size: int,
        chunk_overlap: int,
        window_size: int,
        breakpoints: list[Breakpoint],
        code_fences: list[CodeFence],
    ) -> list[TextChunk]:
        """
        将输入文本切割成多个块，返回切割后的文本块列表

        Args:
            text: 待切割的输入文本
            chunk_size: 目标文本块大小（字符数）
            chunk_overlap: 文本块之间的重叠大小（字符数）
            window_size: 切割窗口大小（字符数），在窗口范围内寻找切割点
            breakpoints: 断点列表
            code_fences: 代码块列表
        """
        # 确保配置合法
        if chunk_overlap >= chunk_size:
            raise ValueError(
                f"Overlap tokens ({chunk_overlap}) must be less than chunk size tokens "
                f"({chunk_size})"
            )
        if window_size >= chunk_size:
            logger.warning(
                "Window size is larger than chunk size, checking if this is intentional."
            )

        chunks: list[TextChunk] = []
        char_pos = 0  # 当前字符位置
        bp_ptr = 0  # 断点扫描游标

        while char_pos < len(text):
            target_end = min(char_pos + chunk_size, len(text))
            end_pos = target_end

            if target_end < len(text):
                # 寻找最合适的断点位置
                best_bp_pos, bp_ptr = self._find_best_breakpoint(
                    breakpoints,
                    code_fences,
                    target_end,
                    bp_ptr=bp_ptr,
                    window_size=window_size,
                    decay_factor=0.7,
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
            char_pos = end_pos - chunk_overlap

        return chunks
