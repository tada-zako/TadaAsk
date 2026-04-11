from typing import Protocol, runtime_checkable


from langchain_core.documents import Document


@runtime_checkable
class FileParser(Protocol):
    """
    文件解析器协议：便于后期横向扩展不同类型的文件解析器（如 PDF、Word、文本等）
    """

    @staticmethod
    async def httpx_download(url: str) -> bytes:
        """
        httpx 方式请求下载文件内容
        """
        ...

    @staticmethod
    def parse(file_input: bytes, filename: str) -> list[Document]:
        """
        解析文件内容为文本块列表，每个文本块包含 page_content 和 metadata

        Args:
            file_input: 文件内容
            filename: 文件名，网络爬取的文件传入 url 的最后一部分

        Returns:
            文本块列表，每个文本块包含 page_content 和 metadata
        """
        ...
