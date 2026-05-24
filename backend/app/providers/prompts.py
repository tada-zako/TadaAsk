# 默认系统提示词
DEFAULT_SYSTEM_PROMPT = """
Given the following conversation, relevant context, 
and a follow up question, reply with an answer to the current question the user is asking. 
Return only your response to the question given the above information 
following the users instructions as needed.
"""


# 查询扩展相关的提示词
QUERY_EXPAND_SYSTEM_PROMPT = """
You are a search query optimization assistant. 
Given a user's question, generate structured expansions to improve document retrieval.
Respond ONLY with valid JSON matching the provided schema.
"""

# 根据是否启用 HYDE 生成假设文档的提示词模板
QUERY_EXPAND_USER_TEMPLATE = """
Analyze the following query and provide expansions:

Query: {query}

Requirements:
- keywords: Extract and expand key terms suitable for keyword/BM25 search (3-8 terms)
- alternative_queries: Rephrase the query in 2-3 semantically equivalent ways for vector search
- hypothetical_document: Write a short passage (2-4 sentences) that would directly answer this query.
"""
