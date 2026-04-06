import io
import asyncio

import httpx
from pypdf import PdfReader
from langchain_core.documents import Document
from loguru import logger


class PDFParser:
    @staticmethod
    async def httpx_download(url: str) -> bytes:
        """
        httpx 方式请求下载 PDF 文件内容
        """
        logger.debug(f"正在下载 PDF 文件: {url}")
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()  # 确保请求成功

        return response.content

    @staticmethod
    def parse(file_input: bytes, filename: str) -> list[Document]:
        """
        解析 PDF 文件内容为 Document 对象

        Args:
            file_input: PDF 文件内容
            filename: PDF 文件名，网络爬取的 PDF 传入 url 的最后一部分

        Returns:
            Document 对象列表，每个对象包含页面内容和元数据
        """
        documents = []
        try:
            pdf_reader = PdfReader(io.BytesIO(file_input))

            for i, page in enumerate(pdf_reader.pages):
                text = page.extract_text()
                if text.strip():
                    doc = Document(
                        page_content=text,
                        metadata={"filename": filename, "page_number": i + 1},
                    )
                    documents.append(doc)

            logger.debug(f"成功解析 PDF 内容，共 {len(documents)} 个文本块")
        except Exception as e:
            logger.error(f"解析 PDF 文件失败: {e}")
            raise

        return documents


if __name__ == "__main__":
    import asyncio

    url = "https://arxiv.org/pdf/2505.00272"
    documents = asyncio.run(PDFParser.httpx_download(url))
    # for doc in documents:
    #     print(f"Page {doc.metadata['page_number']}: {doc.page_content[:100]}...")
