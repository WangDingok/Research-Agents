import os
import json
import praw
import time
import asyncio
import logging
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger('ResearchAgentLogger')

try:
    reddit_client = praw.Reddit(
        client_id=os.environ.get("REDDIT_CLIENT_ID"),
        client_secret=os.environ.get("REDDIT_CLIENT_SECRET"),
        user_agent=os.environ.get("REDDIT_USER_AGENT", "script:trend-checker:v1.0"),
    )
    _reddit_client_available = True
except Exception as e:
    logger.warning(f"Could not initialize Reddit client, Reddit tools will not be available: {e}")
    _reddit_client_available = False

def _compute_reddit_viral_score(post):
    """Computes a viral score for a Reddit post."""
    age_hours = (time.time() - post.created_utc) / 3600
    if age_hours < 1: # Avoid division by zero or artificially high scores for brand new posts
        age_hours = 1
    # Score is upvotes + comments per hour
    return (post.score + post.num_comments) / age_hours

@tool
async def check_reddit_viral_posts(keyword: str, limit: int = 20) -> str:
    """
    Searches for a keyword on Reddit within the last week and returns posts
    sorted by a 'viral score'. This helps identify topics generating significant discussion.
    """
    if not _reddit_client_available:
        return json.dumps({"error": "Reddit client is not available. Please check configuration."})

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
    logger.info(f"Raw output from Reddit for keyword '{keyword}':\n{json.dumps(results, ensure_ascii=False, indent=2)}") # Log raw output
    return json.dumps(results[:10], ensure_ascii=False) # Return top 10 results

reddit_tools = [check_reddit_viral_posts] if _reddit_client_available else []
