import { describe, expect, it } from "vitest";
import { renderChatMarkdown } from "@/shared/services/chat-markdown";

const options = { copyCodeLabel: "Copy" };

describe("renderChatMarkdown", () => {
  it("渲染基础 Markdown 和带复制操作的代码块", () => {
    const html = renderChatMarkdown(
      "** hello **\n\n```ts\nconst answer = 42;\n```",
      options,
    );

    expect(html).toContain("<strong>hello</strong>");
    expect(html).toContain('data-chat-code-lang="TypeScript"');
    expect(html).toContain("data-chat-code-copy");
    expect(html).toContain("Copy");
  });

  it("清理 HTML 主动内容和危险链接协议", () => {
    const html = renderChatMarkdown(
      "<script>alert(1)</script> [bad](javascript:alert(1)) [safe](https://example.com)",
      options,
    );

    expect(html).not.toContain("<script>");
    // markdown-it 会把无效链接保留为纯文本；关键安全边界是不能形成危险 href。
    expect(html).not.toContain('href="javascript:');
    expect(html).toContain('href="https://example.com"');
    expect(html).toContain('rel="noopener noreferrer"');
  });

  it("将图片变为安全文本链接，拒绝 data 图片", () => {
    const html = renderChatMarkdown(
      "![diagram](https://example.com/diagram.png) ![bad](data:image/svg+xml,x)",
      options,
    );

    expect(html).not.toContain("<img");
    expect(html).toContain('class="chat-md-image-link"');
    expect(html).toContain("diagram");
    expect(html).toContain("bad");
    expect(html).not.toContain('href="data:image');
  });

  it("只发布已知 citation，并在流式阶段隐藏未完成 marker", () => {
    const finalHtml = renderChatMarkdown(
      "Answer [[citation:2]] [[citation:9]]",
      {
        ...options,
        citationIds: [2],
        citationLabel: () => "A",
        stripUnknownCitationMarkers: true,
      },
    );
    const streamingHtml = renderChatMarkdown("Answer [[citation:2", {
      ...options,
      citationIds: [2],
      streaming: true,
    });

    expect(finalHtml).toContain('data-chat-citation-id="2"');
    expect(finalHtml).toContain(">A</span></button>");
    expect(finalHtml).not.toContain("citation:9");
    expect(streamingHtml).toContain("Answer");
    expect(streamingHtml).not.toContain("citation:");
  });
});
