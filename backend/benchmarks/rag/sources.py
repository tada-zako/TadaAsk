from dataclasses import dataclass
from pathlib import Path

import httpx


CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True, slots=True)
class PublicSource:
    filename: str
    url: str
    license: str


PUBLIC_SOURCES = {
    "cmrc2018": PublicSource(
        filename="cmrc2018_dev.json",
        url=(
            "https://raw.githubusercontent.com/ymcui/cmrc2018/master/"
            "squad-style-data/cmrc2018_dev.json"
        ),
        license="CC BY-SA 4.0",
    ),
    "squad_v2": PublicSource(
        filename="squad_dev_v2.json",
        url="https://rajpurkar.github.io/SQuAD-explorer/dataset/dev-v2.0.json",
        license="CC BY-SA 4.0",
    ),
    "techqa_train": PublicSource(
        filename="techqa_rag_eval_train.json",
        url=(
            "https://huggingface.co/datasets/nvidia/TechQA-RAG-Eval/resolve/"
            "main/train.json?download=true"
        ),
        license="Apache-2.0",
    ),
    "techqa_corpus": PublicSource(
        filename="techqa_rag_eval_corpus.zip",
        url=(
            "https://huggingface.co/datasets/nvidia/TechQA-RAG-Eval/resolve/"
            "main/corpus.zip?download=true"
        ),
        license="Apache-2.0",
    ),
}


def download_sources(
    source_names: list[str], output_dir: Path
) -> list[dict[str, object]]:
    """分块下载选中文件。

    Args:
        source_names: Keys from PUBLIC_SOURCES.
        output_dir: Directory that receives the downloaded files.

    Returns:
        适合 CLI 输出的下载摘要列表。
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, object]] = []
    for source_name in source_names:
        source = PUBLIC_SOURCES[source_name]
        destination = output_dir / source.filename
        partial = destination.with_suffix(f"{destination.suffix}.part")
        size = 0
        try:
            with httpx.stream(
                "GET",
                source.url,
                follow_redirects=True,
                timeout=httpx.Timeout(30.0, read=300.0),
            ) as response:
                response.raise_for_status()
                with partial.open("wb") as handle:
                    for chunk in response.iter_bytes(CHUNK_SIZE):
                        handle.write(chunk)
                        size += len(chunk)
            partial.replace(destination)
        finally:
            # 清理下载失败的临时文件
            partial.unlink(missing_ok=True)
        summaries.append(
            {
                "source": source_name,
                "bytes": size,
                "path": destination.as_posix(),
            }
        )
    return summaries
