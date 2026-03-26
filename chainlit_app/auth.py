"""Authentication callbacks for Chainlit."""

import chainlit as cl


@cl.password_auth_callback
def auth_callback(username: str, password: str):
    """Simple auth — accepts any username/password for local use.
    Required so Chainlit can track thread ownership.
    """
    return cl.User(identifier=username, metadata={"role": "user"})
