// markdown-it-katex 类型声明：markdown-it 的 KaTeX 数学公式渲染插件
declare module "markdown-it-katex" {
  import type MarkdownIt from "markdown-it";

  export interface MarkdownItKatexOptions {
    /** 解析错误时是否抛出异常（false 则渲染为红色错误文本） */
    throwOnError?: boolean;
    /** 错误文本颜色 */
    errorColor?: string;
    /** LaTeX 严格模式 */
    strict?:
      boolean | string | ((errorCode: string, errorMsg: string) => string);
    /** 是否信任输入（false 时禁止 \\input 等命令，防御任意文件读取） */
    trust?: boolean | ((context: unknown) => boolean);
    /** 自定义 LaTeX 宏 */
    macros?: Record<string, string>;
  }

  const markdownItKatex: MarkdownIt.PluginWithOptions<MarkdownItKatexOptions>;

  export default markdownItKatex;
}
