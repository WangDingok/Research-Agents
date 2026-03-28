"""Authentication callbacks for Chainlit."""

import os
import chainlit as cl

# Set AUTO_LOGIN_AS_ADMIN=true in .env to skip the login screen and
# automatically sign in as "admin".
_AUTO_LOGIN = os.getenv("AUTO_LOGIN_AS_ADMIN", "false").lower() in ("1", "true", "yes")


@cl.header_auth_callback
def header_auth_callback(headers: dict):
    """Auto-login as admin when AUTO_LOGIN_AS_ADMIN=true."""
    if _AUTO_LOGIN:
        return cl.User(identifier="admin", metadata={"role": "admin"})
    return None


@cl.password_auth_callback
def auth_callback(username: str, password: str):
    """Simple auth — accepts any username/password for local use.
    Required so Chainlit can track thread ownership.
    """
    return cl.User(identifier=username, metadata={"role": "user"})
