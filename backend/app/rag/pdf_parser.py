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
    async def playwright_download(url: str) -> bytes:
        """
        Playwright 方式请求下载 PDF 文件内容
        NOTE: 该方法存在一些 bug，在尝试请求某些 PDF url 时会超时，暂时不使用
        """
        from playwright.async_api import async_playwright

        logger.debug(f"正在使用 Playwright 下载 PDF 文件: {url}")
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
            page = await context.new_page()
            async with page.expect_download() as download_info:
                await page.goto(url)
            # await (
            #     page.locator('iframe[type="application/pdf"]')
            #     .content_frame.get_by_role("button", name="下载")
            #     .click()
            # )
            download = await download_info.value
            temp_path = await download.path()

            with open(temp_path, "rb") as f:
                pdf_bytes = f.read()
            await browser.close()

            return pdf_bytes

            # 方法二：监听响应，捕获 PDF 内容
            # pdf_content = None

            # async def handle_response(response):
            #     if (
            #         # "article/S0022-202X" in response.url
            #         "application/pdf" in response.headers.get("content-type", "")
            #     ):
            #         nonlocal pdf_content
            #         logger.debug(f"捕获到 PDF 响应: {response.url}")
            #         pdf_content = await response.body()  # 确保响应体被完全接收

            # page.on("response", handle_response)

            # try:
            #     await page.goto(url, wait_until="networkidle", timeout=60000)
            #     # 等待 PDF 内容被捕获
            #     for _ in range(10):  # 最多等待 10 秒
            #         if pdf_content is not None:
            #             break
            #         await asyncio.sleep(1)
            #     else:
            #         raise TimeoutError("未能在指定时间内捕获到 PDF 内容")
            # except Exception as e:
            #     logger.error(f"下载 PDF 文件失败: {e}")
            #     raise
            # finally:
            #     await browser.close()

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
