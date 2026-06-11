from typing import Literal

# Chat 流式输出事件定义
ChatStreamEventType = Literal[
    "generation_start",
    "message_start",
    "rag_start",
    "rag_done",
    "delta",
    "cancelled",
    "message_done",
    "error",
    "done",
]
