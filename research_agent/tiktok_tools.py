import os
import asyncio
from TikTokApi import TikTokApi
from datetime import datetime, timezone
import json
import logging
from langchain_core.tools import tool

logger = logging.getLogger('ResearchAgentLogger')

class TikTokTool:
    def __init__(self, ms_token: str = None):
        self.ms_token = ms_token or os.getenv("TIKTOK_MS_TOKEN")
        # Cache
        self._api_instance = None

    async def _get_api(self):
        if self._api_instance:
            return self._api_instance

        api = TikTokApi()
        await api.create_sessions(
            ms_tokens=[self.ms_token],
            num_sessions=1,
            sleep_after=3,
            browser="chromium",
            headless=True
        )

        if not api.sessions:
            # Clean up before raising an error to prevent resource leaks
            await api.close_sessions()
            await api.stop_playwright()
            raise Exception("Could not create TikTok session. Please check TIKTOK_MS_TOKEN or network connection.")

        self._api_instance = api
        return api

    # 1. Trending videos
    async def get_trending(self, count=10):
        try:
            api = await self._get_api()
            results = []

            async for video in api.trending.videos(count=count):
                data = video.as_dict
                results.append({
                    "id": data.get("id"),
                    "desc": data.get("desc"),
                    "author": data.get("author", {}).get("uniqueId"),
                    "stats": data.get("stats"),
                })

            return results
        except Exception as e:
            print(f"[TikTokTool ERROR] Error fetching trending videos: {e}")
            return []

    # 2. User videos
    async def get_user_videos(self, username, count=10):
        try:
            api = await self._get_api()
            results = []

            async for video in api.user(username=username).videos(count=count):
                data = video.as_dict
                results.append({
                    "id": data.get("id"),
                    "desc": data.get("desc"),
                    "stats": data.get("stats"),
                })

            return results
        except Exception as e:
            print(f"[TikTokTool ERROR] Error fetching videos for user '{username}': {e}")
            return []

    # 3. Hashtag videos
    async def get_hashtag_videos(self, hashtag, count=10):
        try:
            api = await self._get_api()
            results = []

            async for video in api.hashtag(name=hashtag).videos(count=count):
                data = video.as_dict
                results.append({
                    "id": data.get("id"),
                    "desc": data.get("desc"),
                    "stats": data.get("stats"),
                })

            return results
        except Exception as e:
            print(f"[TikTokTool ERROR] Error fetching videos for hashtag '{hashtag}': {e}")
            return []

    # 4. Video detail
    async def get_video_info(self, url):
        try:
            api = await self._get_api()
            video = api.video(url=url)
            data = await video.info()

            return {
                "id": data.get("id"),
                "desc": data.get("desc"),
                "stats": data.get("stats"),
                "author": data.get("author"),
            }
        except Exception as e:
            print(f"[TikTokTool ERROR] Error fetching video information from URL '{url}': {e}")
            return {}

    # 5. Comments
    async def get_comments(self, video_id, count=10):
        try:
            api = await self._get_api()
            comments = []

            async for c in api.video(id=video_id).comments(count=count):
                comments.append({
                    "text": c.text,
                    "likes": c.likes_count,
                })

            return comments
        except Exception as e:
            print(f"[TikTokTool ERROR] Error fetching comments for video ID '{video_id}': {e}")
            return []

    async def close(self):
        """Cleans up the TikTokApi session and browser to prevent resource leaks."""
        if self._api_instance:
            await self._api_instance.close_sessions()
            await self._api_instance.stop_playwright()
            self._api_instance = None

    def _parse_video(self, video_data: dict) -> dict:
        """
        Extracts relevant information from a TikTok video.
        """
        author_info = video_data.get("author", {})
        stats_info = video_data.get("stats", {})
        music_info = video_data.get("music", {})

        return {
            "id": video_data.get("id"),
            "desc": video_data.get("desc", ""),
            "createTime": video_data.get("createTime"),
            "author": author_info.get("uniqueId"),
            "author_followers": video_data.get("authorStats", {}).get("followerCount", 0),
            "stats": {
                "likes": stats_info.get("diggCount", 0),
                "shares": stats_info.get("shareCount", 0),
                "comments": stats_info.get("commentCount", 0),
                "views": stats_info.get("playCount", 0),
            },
            "music_title": music_info.get("title"),
            "video_url": f"https://www.tiktok.com/@{author_info.get('uniqueId')}/video/{video_data.get('id')}",
        }

    def _trend_score(self, parsed_video: dict) -> float:
        """
        Calculates a trend score based on video engagement and recency.
        This formula prioritizes videos with high engagement in a short period.
        """
        stats = parsed_video["stats"]
        create_time = parsed_video["createTime"]

        if not create_time:
            return 0.0

        # Calculate video age (in days)
        now = datetime.now(timezone.utc).timestamp()
        age_days = (now - create_time) / (60 * 60 * 24)

        # Weights for different types of engagement
        # Shares have the highest weight as they indicate strong virality
        engagement_score = (
            stats["likes"] * 0.2
            + stats["comments"] * 0.3
            + stats["shares"] * 0.5
        )

        # Normalize score by views to evaluate engagement effectiveness
        # Add 1 to the denominator to avoid division by zero
        engagement_rate = (engagement_score / (stats["views"] + 1)) * 1000

        # Calculate the final score, which decreases over time
        # Older videos have lower scores
        # Add 1 to age_days to avoid division by zero and reduce the impact of very new videos
        score = engagement_rate / (age_days + 1)

        return score

    async def get_trending_by_keyword(self, keyword: str, count_per_source=10):
        """
        Aggregates and analyzes trending videos for a specific topic (keyword).
        This function searches from multiple sources (hashtag, search) for comprehensive results,
        then calculates a trend score for ranking.

        Args:
            keyword: Chủ đề cần tìm kiếm.
            count_per_source: Số lượng video tối đa lấy từ mỗi nguồn.

        Returns:
            A list of videos (as dicts) that have been analyzed and ranked by trend score.
        """
        try:
            api = await self._get_api()
            processed_videos = {}  # Used to remove duplicate videos

            async def process_stream(stream_name, stream, keyword, video_dict):
                try:
                    # print(f"\n[INFO] Processing stream: {stream_name}")
                    async for video in stream:
                        video_data = video.as_dict
                        video_id = video_data.get("id")

                        # print("\n" + "="*20 + f" RAW VIDEO DATA (ID: {video_id}) " + "="*20)
                        # pprint(video_data)

                        if not video_id or video_id in video_dict:
                            # print(f"--- SKIPPING: Video {video_id} is a duplicate or has no ID.")
                            continue

                        parsed = self._parse_video(video_data)
                        # print("\n" + "-"*20 + f" PARSED VIDEO DATA (ID: {video_id}) " + "-"*20)
                        # pprint(parsed)

                        if keyword.lower() in parsed["desc"].lower():
                            # print(f"--- FILTER: PASSED. Keyword '{keyword}' found in description.")
                            parsed["trend_score"] = self._trend_score(parsed)
                            # print(f"--- SCORE: Calculated trend score is {parsed['trend_score']:.2f}")
                            video_dict[video_id] = parsed
                        # else:
                            # print(f"--- FILTER: FAILED. Keyword '{keyword}' not in description.") # Filter: Failed. Keyword not in description.
                except Exception as e:
                    # Instead of just printing, we could log or let the exception propagate
                    # to be handled at a higher level. Here, we log the error and continue.
                    print(f"[TikTokTool WARNING] Error processing stream '{stream_name}' for keyword '{keyword}': {e}")

            # 🔎 1. Fetch videos from multiple sources in parallel
            # print(f"\n[INFO] Starting data fetch for keyword: '{keyword}'")
            hashtag_stream = api.hashtag(name=keyword).videos(count=count_per_source)
            search_stream = api.search.search_type(search_term=keyword, obj_type='video', count=count_per_source)

            await asyncio.gather(
                process_stream("hashtag", hashtag_stream, keyword, processed_videos),
                process_stream("search", search_stream, keyword, processed_videos)
            )

            # 🔎 2. Sort results by trend_score from highest to lowest
            sorted_results = sorted(processed_videos.values(), key=lambda x: x.get("trend_score", 0), reverse=True)

            return sorted_results[:20]
        except Exception as e:
            print(f"[TikTokTool ERROR] A critical error occurred while searching for trends for keyword '{keyword}': {e}")
            return []


async def close_tiktok_instance():
    """Closes the global TikTokTool instance if it was created."""
    global _tiktok_tool_instance
    if _tiktok_tool_instance:
        await _tiktok_tool_instance.close()
        _tiktok_tool_instance = None

# --- Tool Definitions ---

_tiktok_tool_instance = None

def get_tiktok_instance():
    """Initializes and returns a singleton TikTokTool instance."""
    global _tiktok_tool_instance
    if _tiktok_tool_instance is None:
        try:
            ms_token = os.environ.get("TIKTOK_MS_TOKEN")
            if not ms_token:
                raise ValueError("TIKTOK_MS_TOKEN is not set in the environment.")
            _tiktok_tool_instance = TikTokTool(ms_token=ms_token)
        except Exception as e: # Could not initialize TikTokTool
            logger.warning(f"Could not initialize TikTokTool, TikTok tools will not be available: {e}")
            # We don't re-raise, instance remains None
    return _tiktok_tool_instance

@tool
async def get_tiktok_trending(count: int = 10) -> str:
    """Retrieves trending videos on TikTok."""
    instance = get_tiktok_instance()
    if not instance:
        return json.dumps({"error": "TikTok tool is not available."})
    result = await instance.get_trending(count=count)
    logger.info(f"Raw output from TikTok (Trending): \n{json.dumps(result, ensure_ascii=False, indent=2)}")
    return json.dumps(result, ensure_ascii=False)

@tool
async def get_tiktok_user_videos(username: str, count: int = 10) -> str: # Get videos from a TikTok user.
    """Retrieves videos from a TikTok user."""
    instance = get_tiktok_instance()
    if not instance:
        return json.dumps({"error": "TikTok tool is not available."})
    result = await instance.get_user_videos(username=username, count=count)
    logger.info(f"Raw output from TikTok (User Videos for '{username}'): \n{json.dumps(result, ensure_ascii=False, indent=2)}")
    return json.dumps(result, ensure_ascii=False)

@tool
async def get_tiktok_hashtag_videos(hashtag: str, count: int = 10) -> str: # Get videos for a specific hashtag on TikTok.
    """Retrieves videos for a specific hashtag on TikTok."""
    instance = get_tiktok_instance()
    if not instance:
        return json.dumps({"error": "TikTok tool is not available."})
    result = await instance.get_hashtag_videos(hashtag=hashtag, count=count)
    logger.info(f"Raw output from TikTok (Hashtag Videos for '{hashtag}'): \n{json.dumps(result, ensure_ascii=False, indent=2)}")
    return json.dumps(result, ensure_ascii=False)

@tool
async def get_tiktok_video_info(url: str) -> str: # Get detailed information for a specific TikTok video URL.
    """Retrieves detailed information for a specific TikTok video URL."""
    instance = get_tiktok_instance()
    if not instance:
        return json.dumps({"error": "TikTok tool is not available."})
    result = await instance.get_video_info(url=url)
    logger.info(f"Raw output from TikTok (Video Info for '{url}'): \n{json.dumps(result, ensure_ascii=False, indent=2)}")
    return json.dumps(result, ensure_ascii=False)

@tool
async def get_tiktok_comments(video_id: str, count: int = 20) -> str: # Get comments for a specific TikTok video ID.
    """Retrieves comments for a specific TikTok video ID."""
    instance = get_tiktok_instance()
    if not instance:
        return json.dumps({"error": "TikTok tool is not available."})
    result = await instance.get_comments(video_id=video_id, count=count)
    logger.info(f"Raw output from TikTok (Comments for video ID '{video_id}'): \n{json.dumps(result, ensure_ascii=False, indent=2)}")
    return json.dumps(result, ensure_ascii=False)

@tool
async def get_tiktok_trending_by_keyword(keyword: str, count_per_source: int = 5) -> str: # Get and analyze trending videos for a specific keyword on TikTok.
    """Retrieves and analyzes trending videos for a specific keyword on TikTok."""
    instance = get_tiktok_instance()
    if not instance:
        return json.dumps({"error": "TikTok tool is not available."})
    result = await instance.get_trending_by_keyword(keyword=keyword, count_per_source=count_per_source)
    logger.info(f"Raw output from TikTok (Trending for keyword '{keyword}'): \n{json.dumps(result, ensure_ascii=False, indent=2)}")
    return json.dumps(result, ensure_ascii=False)

# Check availability and collect tools
if get_tiktok_instance() is not None:
    tiktok_tools = [
        get_tiktok_trending, get_tiktok_user_videos, get_tiktok_hashtag_videos,
        get_tiktok_video_info, get_tiktok_comments, get_tiktok_trending_by_keyword
    ]
else:
    tiktok_tools = []
