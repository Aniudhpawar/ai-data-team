from . import config


def llm(system, user, max_tokens=600):
    """One model call. Databricks-hosted model by default; LLM_BACKEND=anthropic or mock to switch."""
    backend = config.LLM_BACKEND
    if backend == "mock":
        from .mock_llm import respond
        return respond(system, user)
    if backend == "anthropic":
        import anthropic
        r = anthropic.Anthropic().messages.create(
            model=config.ANTHROPIC_MODEL, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}])
        return "".join(b.text for b in r.content if b.type == "text")

    from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
    from .db import client
    r = client().serving_endpoints.query(
        name=config.MODEL, max_tokens=max_tokens, temperature=0,
        messages=[ChatMessage(role=ChatMessageRole.SYSTEM, content=system),
                  ChatMessage(role=ChatMessageRole.USER, content=user)])
    return r.choices[0].message.content
