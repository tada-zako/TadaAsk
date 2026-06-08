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

# 根据是否启用 HYDE 生成假设文档的提示词模板
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
