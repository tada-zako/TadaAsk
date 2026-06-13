# 默认系统提示词
DEFAULT_SYSTEM_PROMPT = """
Given the following conversation, relevant context, 
and a follow up question, reply with an answer to the current question the user is asking. 
Return only your response to the question given the above information 
following the users instructions as needed.
"""


# 查询扩展相关的提示词
QUERY_EXPAND_SYSTEM_PROMPT = """
You are a query expansion assistant for a RAG hybrid search system.
Generate concise, retrieval-oriented expansions that improve keyword search,
vector search, and optional HyDE retrieval.

Return ONLY valid JSON matching the provided schema.
Do not include markdown, explanations, comments, or fields outside the schema.
Respect all maximum item counts provided by the user message.
Prefer preserving the user's original intent over broadening the query.
"""

# 生成假设文档的提示词模板
QUERY_EXPAND_USER_TEMPLATE = """
Analyze the following query and generate retrieval expansions.

Query: {query}

Quantity constraints:
- keywords: generate at most {max_keywords} items
- alternative_queries: generate at most {max_alternative_queries} items
- hypothetical_document: generate exactly one short passage

Requirements:
- keywords: Extract important entities, terms, synonyms, and domain phrases suitable for keyword/BM25 search. Keep each item short.
- alternative_queries: Rephrase the original query in semantically equivalent ways for vector search. Do not invent new constraints or unrelated topics.
- hypothetical_document: Write 2-4 sentences that resemble a relevant source passage answering the query. Keep it factual in tone and avoid unsupported specifics.
"""


# standalone query 改写提示词
STANDALONE_QUERY_REWRITE_PROMPT = """
Rewrite the user's latest question into a standalone search query.
Preserve entities, constraints, and intent. Do not answer the question.
"""


# 压缩总结提示词 —— 来自 pi
SUMMARIZATION_PROMPT = """The messages above are a conversation to summarize. Create a structured context checkpoint summary that another LLM will use to continue the work.

Use this EXACT format:

## Goal
[What is the user trying to accomplish? Can be multiple items if the session covers different tasks.]

## Constraints & Preferences
- [Any constraints, preferences, or requirements mentioned by user]
- [Or "(none)" if none were mentioned]

## Progress
### Done
- [x] [Completed tasks/changes]

### In Progress
- [ ] [Current work]

### Blocked
- [Issues preventing progress, if any]

## Key Decisions
- **[Decision]**: [Brief rationale]

## Next Steps
1. [Ordered list of what should happen next]

## Critical Context
- [Any data, examples, or references needed to continue]
- [Or "(none)" if not applicable]

Keep each section concise. Preserve exact file paths, function names, and error messages."""


# 更新总结提示词；当已经存在 compaction message —— 来自 pi
UPDATE_SUMMARIZATION_PROMPT = """The messages above are NEW conversation messages to incorporate into the existing summary provided in <previous-summary> tags.

Update the existing structured summary with new information. RULES:
- PRESERVE all existing information from the previous summary
- ADD new progress, decisions, and context from the new messages
- UPDATE the Progress section: move items from "In Progress" to "Done" when completed
- UPDATE "Next Steps" based on what was accomplished
- PRESERVE exact file paths, function names, and error messages
- If something is no longer relevant, you may remove it

Use this EXACT format:

## Goal
[Preserve existing goals, add new ones if the task expanded]

## Constraints & Preferences
- [Preserve existing, add new ones discovered]

## Progress
### Done
- [x] [Include previously done items AND newly completed items]

### In Progress
- [ ] [Current work - update based on progress]

### Blocked
- [Current blockers - remove if resolved]

## Key Decisions
- **[Decision]**: [Brief rationale] (preserve all previous, add new)

## Next Steps
1. [Update based on current state]

## Critical Context
- [Preserve important context, add new if needed]

Keep each section concise. Preserve exact file paths, function names, and error messages."""
