import importlib
import asyncio
from dataclasses import dataclass
from typing import Literal, Callable
import re

from tree_sitter import Language, Parser, Query, QueryCursor, Node
from loguru import logger


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


# 支持的语言类型
SupportedLanguages = Literal[
    "python", "javascript", "java", "rust", "go", "typescript", "tsx"
]


# ======================================
# Grammar 映射
#
# SupportedLanguages -> (模块名，函数名)
# tree-sitter-typescript 提供两种函数名：
#  - Language_typescript() -> TypesScript
#  - Language_tsx() -> TSX
# ======================================
GRAMMAR_MAP: dict[SupportedLanguages, tuple[str, str]] = {
    "typescript": ("tree_sitter_typescript", "language_typescript"),
    "tsx": ("tree_sitter_typescript", "language_tsx"),
    "javascript": ("tree_sitter_javascript", "language"),
    "python": ("tree_sitter_python", "language"),
    "go": ("tree_sitter_go", "language"),
    "rust": ("tree_sitter_rust", "language"),
    "java": ("tree_sitter_java", "language"),
}


# ======================================
# Query 查询规则定义（S-Expressions）
# ======================================
LANGUAGE_QUERIES: dict[SupportedLanguages, str] = {
    "typescript": """
        (export_statement) @export
        (class_declaration) @class
        (function_declaration) @func
        (method_definition) @method
        (interface_declaration) @iface
        (type_alias_declaration) @type
        (enum_declaration) @enum
        (import_statement) @import
        (lexical_declaration (variable_declarator value: (arrow_function))) @func
        (lexical_declaration (variable_declarator value: (function_expression))) @func
    """,
    "tsx": """
        (export_statement) @export
        (class_declaration) @class
        (function_declaration) @func
        (method_definition) @method
        (interface_declaration) @iface
        (type_alias_declaration) @type
        (enum_declaration) @enum
        (import_statement) @import
        (lexical_declaration (variable_declarator value: (arrow_function))) @func
        (lexical_declaration (variable_declarator value: (function_expression))) @func
    """,
    "javascript": """
        (export_statement) @export
        (class_declaration) @class
        (function_declaration) @func
        (method_definition) @method
        (import_statement) @import
        (lexical_declaration (variable_declarator value: (arrow_function))) @func
        (lexical_declaration (variable_declarator value: (function_expression))) @func
    """,
    "python": """
        (class_definition) @class
        (function_definition) @func
        (decorated_definition) @decorated
        (import_statement) @import
        (import_from_statement) @import
    """,
    "go": """
        (type_declaration) @type
        (function_declaration) @func
        (method_declaration) @method
        (import_declaration) @import
    """,
    "rust": """
        (struct_item) @struct
        (impl_item) @impl
        (function_item) @func
        (trait_item) @trait
        (enum_item) @enum
        (use_declaration) @import
        (type_item) @type
        (mod_item) @mod
    """,
    "java": """
        (class_declaration) @class
        (interface_declaration) @iface
        (method_declaration) @method
        (enum_declaration) @enum
        (import_declaration) @import
    """,
}

# 断点类型优先级映射
SCORE_MAP: dict[str, int] = {
    "class": 100,
    "iface": 100,
    "struct": 100,
    "trait": 100,
    "impl": 100,
    "mod": 100,
    "export": 90,
    "func": 90,
    "method": 90,
    "decorated": 90,
    "type": 80,
    "enum": 80,
    "import": 60,
}


@dataclass
class _BreakpointInfo:
    """内部使用的断点信息类，临时存储断点的行列信息"""

    start_point: tuple[int, int]  # (row, column) 临时存储行列信息
    score: int
    type: str


class ASTBreakpointScanner:
    """扫描代码文本中的断点位置，基于抽象语法树（AST）分析"""

    def __init__(self):
        self._grammar_task_cache: dict[
            SupportedLanguages, asyncio.Task[Language]
        ] = {}  # 缓存加载 grammar 异步任务
        self._grammar_result_cache: dict[
            SupportedLanguages, Language
        ] = {}  # 缓存加载成功的 grammar 结果
        self._query_cache: dict[SupportedLanguages, QueryCursor] = {}
        self._failed_languages: set[SupportedLanguages] = set()  # 记录加载失败的语言

    async def _load_grammar(self, language: SupportedLanguages) -> Language | None:
        """
        异步载入指定语言的 Tree-sitter 语法 grammar。
        使用缓存进行并发控制，避免重复载入以及加快后续访问。
        """
        if language in self._failed_languages:
            return None  # 已经记录为加载失败的语言
        if language in self._grammar_result_cache:
            return self._grammar_result_cache[language]  # 返回缓存的结果

        # 缓存未命中，创建新的 load task
        if language not in self._grammar_task_cache:
            # 载入函数
            def grammar_load_task() -> Language:
                module_name, func_name = GRAMMAR_MAP[language]
                module = importlib.import_module(module_name)
                lang_fn: Callable[[], object] = getattr(module, func_name)
                return Language(lang_fn())

            # 创建并缓存 load task
            self._grammar_task_cache[language] = asyncio.create_task(
                asyncio.to_thread(grammar_load_task)
            )

        try:
            # 并发控制：收缩到同一个 load task
            grammar = await self._grammar_task_cache[language]
            self._grammar_result_cache[language] = grammar  # 缓存成功结果
            return grammar
        except Exception as e:
            self._failed_languages.add(language)  # 记录加载失败的语言
            self._grammar_task_cache.pop(language, None)  # 移除失败的缓存项
            logger.error(f"Failed to load grammar for language {language}: {e}")
            return None

    def _get_query_cursor(
        self, language: SupportedLanguages, grammar: Language
    ) -> QueryCursor:
        """获取指定语言的 QueryCursor，使用缓存避免重复创建"""
        if language not in self._query_cache:
            query_str = LANGUAGE_QUERIES.get(language, "")
            query = Query(grammar, query_str)
            self._query_cache[language] = QueryCursor(query)
        return self._query_cache[language]

    def _extract_breakpoints_from_ast(
        self, root_node: Node, cursor: QueryCursor, text: str
    ) -> list[Breakpoint]:
        """从 AST 根节点提取断点信息，返回断点列表"""
        captures: dict[str, list[Node]] = cursor.captures(root_node)

        # 去重：同一位置保留评分最高的断点
        seen: dict[int, _BreakpointInfo] = {}  # pos -> (row, col), score, type
        for capture_name, nodes in captures.items():
            score = SCORE_MAP.get(capture_name, 20)
            bp_type = capture_name
            for node in nodes:
                pos = node.start_byte
                # 如果位置已存在，则保留评分更高的断点
                if pos not in seen or score > seen[pos].score:
                    seen[pos] = _BreakpointInfo(
                        start_point=node.start_point, score=score, type=bp_type
                    )

        if not seen:
            return []  # 没有捕获到任何断点

        # 按位置排序断点列表
        sorted_items = sorted(seen.items(), key=lambda x: x[0])

        # 快路径：如果文本全是 ASCII 字符，无需转换
        if text.isascii():
            return [
                Breakpoint(pos=pos, score=info.score, type=info.type)
                for pos, info in sorted_items
            ]

        # 非 ASCII 字符路径：需要将 byte_offset 转换成 char_offset
        lines = text.split(
            "\n"
        )  # 这里只在 \n 处切分，是因为 tree-sitter 只识别 \r\n 或 \n 作为换行符
        line_char_starts = [0]
        for line in lines[:-1]:
            line_char_starts.append(line_char_starts[-1] + len(line) + 1)

        result: list[Breakpoint] = []
        for byte_pos, bp_info in sorted_items:
            row, col_bytes = bp_info.start_point
            col_chars = len(
                lines[row].encode("utf-8")[:col_bytes].decode("utf-8", errors="ignore")
            )
            result.append(
                Breakpoint(
                    pos=line_char_starts[row] + col_chars,
                    score=bp_info.score,
                    type=bp_info.type,
                )
            )
        return result

    async def ensure_grammar_loaded(self, language: SupportedLanguages) -> bool:
        """确保指定文件类型的 grammar 已经加载完成，返回是否成功"""
        # 载入对应的 tree-sitter grammar
        grammar: Language | None = await self._load_grammar(language)
        if grammar is None:
            logger.warning(f"Grammar for language {language} is not available.")
            return False
        return True  # grammar 已成功加载

    def sync_scan(self, text: str, language: SupportedLanguages) -> list[Breakpoint]:
        """
        扫描输入代码文本，返回断点列表。
        同步接口：要求 grammar 已经预先加载完成，上层调用者保证
        """
        grammar = self._grammar_result_cache[language]
        try:
            parser = Parser(grammar)
            tree = parser.parse(bytes(text, "utf8"))
            if not tree:
                logger.warning(f"Failed to parse code for language {language}.")
                return []

            query_cursor = self._get_query_cursor(language, grammar)
            return self._extract_breakpoints_from_ast(
                tree.root_node, query_cursor, text
            )

        except Exception as e:
            logger.error(f"Error scanning AST for language {language}: {e}")
            return []  # 扫描过程中发生错误，返回空列表
