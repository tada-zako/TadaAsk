import re
from pathlib import Path
from typing import Protocol, runtime_checkable

import jieba
import jieba.analyse


# 中文正则匹配
CHINESE_RE = re.compile(r"([\u4e00-\u9fff\u3400-\u4dbf]+)")

_PUNCT_ONLY_RE = re.compile(r"^[\s\W_]+$")  # 纯标点 / 空白 token
_SPECIAL_EN_RE = re.compile(
    r"[_.\-]"
)  # 含特殊字符的英文 token（路径、版本号等，不加 * 后缀）
_FTS5_UNSAFE_RE = re.compile(r'["()\^]')  # FTS5 MATCH 语法保留字符，需清除

# 长查询阈值
# 字符数快速预检：超过此值直接走 extract_tags，跳过全量 jieba 分词
_FAST_CHECK_CHARS = 300
# 全量分词后 token 数阈值：超过时降级到 extract_tags 路径
MAX_QUERY_TOKENS = 20

# 默认停用词文件路径
DEFAULT_STOP_WORDS_DIR = Path(__file__).parent / "resources"
HYBRID_STOP_WORDS_FILE = (
    DEFAULT_STOP_WORDS_DIR / "hybrid_stopwords.txt"
)  # 中英文混合停用词
HIT_STOP_WORDS_FILE = (
    DEFAULT_STOP_WORDS_DIR / "hit_stopwords.txt"
)  # jieba.analyse 停用词


def _get_stop_words(input_file: str | None = None) -> set[str]:
    """从文件中加载停用词列表"""
    file_path = Path(input_file) if input_file else HYBRID_STOP_WORDS_FILE

    if not file_path.is_file():
        raise FileNotFoundError(f"stop words file not found: {file_path}")

    stop_words: set[str] = set()
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            word = line.strip()
            if word and not word.startswith("#"):
                stop_words.add(word)
    return stop_words


def _sanitize_fts5(token: str) -> str:
    """清除 FTS5 MATCH 表达式中的语法保留字符，防止构造无效查询"""
    return _FTS5_UNSAFE_RE.sub("", token)


@runtime_checkable
class FTSTokenizer(Protocol):
    """FTS 分词器接口"""

    def tokenize(self, text: str) -> str:
        """将原始文本处理为空格分隔的 token 串（用于构建 FTS 索引）"""
        ...

    def tokenize_for_query(self, text: str) -> str:
        """将查询文本处理为 FTS5 MATCH 表达式（用于构建 FTS 查询语句）"""
        ...

    def build_match_expr_from_expanded_tokens(self, tokens: list[str]) -> str:
        """从扩展查询生成的关键词列表构建 MATCH 表达式"""
        ...


class JiebaFTSTokenizer:
    """基于 jieba 的中英文混合分词器"""

    def __init__(
        self,
        *,
        cut_all: bool = False,
        use_hmm: bool = True,
        stop_words_file: str | None = None,
        jieba_stop_words_path: str | None = None,
        jieba_idf_path: str | None = None,
    ):
        """
        Args:
            cut_all: 是否使用全模式分词
            use_hmm: 是否使用 HMM 模型进行新词识别
            stop_words_file: 组件内部停用词文件路径
            jieba_stop_words_path: jieba.analyse 的停用词文件路径
            jieba_idf_path: jieba.analyse 的 idf 文件路径，默认 jieba 内置的 idf 文件
        """
        self._cut_all = cut_all
        self._use_hmm = use_hmm

        # 载入组件内部停用词（用于 tokenize_for_query 的 jieba.cut 路径）
        self._stop_words = _get_stop_words(stop_words_file)

        # 初始化 jieba.analyse 停用词与 IDF 语料库
        if jieba_idf_path:
            jieba.analyse.set_idf_path(jieba_idf_path)
        jieba.analyse.set_stop_words(jieba_stop_words_path or HIT_STOP_WORDS_FILE)

        # 预加载 jieba 词典，避免首次分词时的延迟
        jieba.initialize()

    def tokenize(self, text: str) -> str:
        """
        将原始文本处理为空格分隔的 token 串（用于构建 FTS 索引）。

        文本处理策略：
            - 使用正则表达式将文本分割成中文和非中文两部分
            - 中文部分使用 jieba 分词
                非中文部分转换成小写,并按空格进行分词,
                对于特殊字符(如下划线、点、连字符等)不进行额外处理,保留原样

        索引路径不过滤停用词：确保停用词所在的文档也能被 FTS 召回，
        停用词过滤仅在查询路径（tokenize_for_query）中进行。
        """
        tokens: list[str] = []
        for part in CHINESE_RE.split(text.strip()):
            if not part:
                continue

            if CHINESE_RE.match(part):
                # 中文 jieba 分词
                tokens.extend(jieba.cut(part, cut_all=self._cut_all, HMM=self._use_hmm))
            else:
                # 非中文文本处理
                tokens.extend(part.lower().split())

        # 去除纯标点/空白 token，保留其他特殊字符（路径、版本号等）
        return " ".join(t for t in tokens if not _PUNCT_ONLY_RE.match(t))

    def tokenize_for_query(self, text: str) -> str:
        """
        将查询文本处理为 FTS5 MATCH 表达式。

        文本处理策略：
            1. 字符数快速预检（>_FAST_CHECK_CHARS）→ 跳过全量分词，直接走 extract_tags
            2. 正常分词路径：中文 jieba + 停用词过滤；英文小写 + FTS5 特殊字符清理
            3. 分词后 token 数超过 MAX_QUERY_TOKENS → 降级到 extract_tags 路径
            4. MATCH 表达式连接策略（由 _build_match_expr 决定）：
                ≤2 tokens               → AND（精确匹配）
                ≤5 tokens 且每词长度 >3  → AND（关键词重要性高）
                其他                     → OR（扩大召回，配合下游 rerank）
        """
        text = text.strip()
        if not text:
            return ""

        # 快速预检：超过字符阈值直接走长查询路径
        if len(text) > _FAST_CHECK_CHARS:
            return self._long_query_expr(text)

        # 正常分词路径
        cn_tokens, en_tokens = self._tokenize_parts(text)

        # 去重后检查 token 数
        all_tokens = list(dict.fromkeys(cn_tokens + en_tokens))
        if len(all_tokens) > MAX_QUERY_TOKENS:
            # 已有英文 clean tokens，直接传入避免重复解析
            return self._long_query_expr(text, en_tokens=en_tokens)

        return self._build_match_expr(cn_tokens, en_tokens)

    def _tokenize_parts(self, text: str) -> tuple[list[str], list[str]]:
        """
        中英文混合分词，返回 (cn_tokens, en_tokens)

        - cn_tokens：jieba 分词结果，已过滤停用词和纯标点
        - en_tokens：小写化、已清理 FTS5 特殊字符，未添加 * 后缀
          (* 后缀在 _build_match_expr 中统一处理，保持 token 语义干净)
        """
        cn_tokens: list[str] = []
        en_tokens: list[str] = []

        for part in CHINESE_RE.split(text):
            if not part:
                continue

            if CHINESE_RE.match(part):
                # 中文文本处理：jieba 分词 + 停用词过滤 + 纯标点过滤
                cn_tokens.extend(
                    t
                    for t in jieba.cut(part, cut_all=self._cut_all, HMM=self._use_hmm)
                    if t.strip()
                    and t not in self._stop_words
                    and not _PUNCT_ONLY_RE.match(t)
                )
            else:
                # 英文文本处理：小写化 + FTS5 特殊字符清理 + 停用词过滤 + 纯标点过滤
                for raw in part.lower().split():
                    token = _sanitize_fts5(raw)
                    if (
                        token
                        and not _PUNCT_ONLY_RE.match(token)
                        and token not in self._stop_words
                    ):
                        en_tokens.append(token)

        return cn_tokens, en_tokens

    def _long_query_expr(
        self,
        text: str,
        *,
        en_tokens: list[str] | None = None,
    ) -> str:
        """
        长查询路径：TF-IDF extract_tags 提取中文关键词 + 英文 token，OR 连接。

        Args:
            text: 原始查询文本（用于 extract_tags 和英文重新解析）
            en_tokens: 调用方已解析的英文 clean tokens；
                       为 None 时在此处重新解析（字符数预检快速路径）
        """
        if en_tokens is None:
            # 字符数预检路径：还没有英文 token，快速解析一遍
            en_tokens = []
            for part in CHINESE_RE.split(text):
                if not part or CHINESE_RE.match(part):
                    continue
                # 只处理英文部分
                for raw in part.lower().split():
                    token = _sanitize_fts5(raw)
                    if (
                        token
                        and not _PUNCT_ONLY_RE.match(token)
                        and token not in self._stop_words
                    ):
                        en_tokens.append(token)

        # 英文 token 添加 * 后缀支持前缀匹配
        en_tokens = [t if _SPECIAL_EN_RE.search(t) else f"{t}*" for t in en_tokens]

        topK = max(3, MAX_QUERY_TOKENS - len(en_tokens))  # 中文关键词检索数量
        chinese_text = "".join(CHINESE_RE.findall(text))
        cn_keywords: list[str] = (
            jieba.analyse.extract_tags(chinese_text, topK=topK) if chinese_text else []
        )  # type: ignore

        keywords = list(dict.fromkeys(cn_keywords + en_tokens))
        return " OR ".join(keywords) if keywords else ""

    def _build_match_expr(self, cn_tokens: list[str], en_tokens: list[str]) -> str:
        """
        构建 FTS5 MATCH 表达式。

        - 中文 token：精确匹配（jieba 已在词边界切分，前缀匹配意义不大）
        - 英文 token：含特殊字符（路径、版本号）保留原样；其余加 * 支持前缀匹配
        - AND/OR 策略：≤2 tokens 或 ≤5 且每词长度 >3 时用 AND，其余用 OR
        """
        en_expr = [t if _SPECIAL_EN_RE.search(t) else f"{t}*" for t in en_tokens]
        # 去重保序，中文在前（通常更具区分性）
        expr_tokens = list(dict.fromkeys(cn_tokens + en_expr))
        if not expr_tokens:
            return ""

        n = len(expr_tokens)
        if n <= 2:
            return " AND ".join(expr_tokens)
        if n <= 5 and all(len(t.rstrip("*")) > 3 for t in expr_tokens):
            return " AND ".join(expr_tokens)
        return " OR ".join(expr_tokens)

    def build_match_expr_from_expanded_tokens(self, tokens: list[str]) -> str:
        """
        从扩展查询生成的关键词列表构建 MATCH 表达式。
        """
        # 区分中英文 token
        cn_tokens = []
        en_tokens = []
        for t in tokens:
            if CHINESE_RE.search(t):
                cn_tokens.append(t)
            else:
                token = _sanitize_fts5(t.lower())
                if token and not _PUNCT_ONLY_RE.match(token):
                    en_tokens.append(
                        token if _SPECIAL_EN_RE.search(token) else f"{token}*"
                    )

        # 构建 MATCH 表达式
        return self._build_match_expr(cn_tokens, en_tokens)
