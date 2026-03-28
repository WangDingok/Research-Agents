import json
import praw
import time
import asyncio
from langchain_core.tools import tool

from research_agent.base.base import BaseToolkit
from research_agent.config import AppConfig, config as default_config


def _compute_reddit_viral_score(post):
    """Computes a viral score for a Reddit post."""
    age_hours = (time.time() - post.created_utc) / 3600
    if age_hours < 1:
        age_hours = 1
    return (post.score + post.num_comments) / age_hours


class RedditToolkit(BaseToolkit):
    """Toolkit for Reddit trend analysis tools."""

    def __init__(self, config: AppConfig = None):
        super().__init__(config or default_config)
        cfg = self.config.reddit if hasattr(self.config, 'reddit') else self.config
        self._client = None
        self._tools = None

        if cfg.is_available:
            try:
                self._client = praw.Reddit(
                    client_id=cfg.client_id,
                    client_secret=cfg.client_secret,
                    user_agent=cfg.user_agent,
                )
            except Exception as e:
                self.logger.warning(f"Could not initialize Reddit client: {e}")

    @property
    def is_available(self) -> bool:
        return self._client is not None

    def get_tools(self) -> list:
        if self._tools is not None:
            return self._tools
        if not self.is_available:
            self._tools = []
            return self._tools

        reddit_client = self._client
        logger = self.logger

        @tool
        async def check_reddit_viral_posts(keyword: str, limit: int = 20) -> str:
            """
            Searches for a keyword on Reddit within the last week and returns posts
            sorted by a 'viral score'. This helps identify topics generating significant discussion.
            """
            def sync_search():
                posts = reddit_client.subreddit("all").search(keyword, sort="new", time_filter="week", limit=limit)
                results = []
                for post in posts:
                    score = _compute_reddit_viral_score(post)
                    results.append({
                        "title": post.title, "subreddit": str(post.subreddit), "upvotes": post.score,
                        "comments": post.num_comments, "url": post.url,
                        "permalink": f"https://www.reddit.com{post.permalink}",
                        "age_hours": round((time.time() - post.created_utc) / 3600, 2), "viral_score": round(score, 2)
                    })
                results.sort(key=lambda x: x["viral_score"], reverse=True)
                return results

            loop = asyncio.get_running_loop()
            results = await loop.run_in_executor(None, sync_search)
            logger.info(f"Raw output from Reddit for keyword '{keyword}':\n{json.dumps(results, ensure_ascii=False, indent=2)}")
            return json.dumps(results[:10], ensure_ascii=False)

        self._tools = [check_reddit_viral_posts]
        return self._tools


# --- Backward-compatible module-level exports ---
_reddit_toolkit = RedditToolkit()
reddit_tools = _reddit_toolkit.get_tools()
