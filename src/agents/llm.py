from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
from .config import MODEL
from .db import client


def llm(system, user, max_tokens=600):
    r = client().serving_endpoints.query(
        name=MODEL, max_tokens=max_tokens, temperature=0,
        messages=[ChatMessage(role=ChatMessageRole.SYSTEM, content=system),
                  ChatMessage(role=ChatMessageRole.USER, content=user)])
    return r.choices[0].message.content
