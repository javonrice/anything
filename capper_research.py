"""
Capper Twitter Research
Pulls profile stats + recent tweets for target accounts,
extracts posting patterns and engagement data, saves to CSV.
"""

import csv
import http.client
import json
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

API_KEY  = "4809f29274msh8fc3b37e2f08a5cp1f44f9jsn4f902fb893c0"
API_HOST = "twitter241.p.rapidapi.com"

HEADERS = {
    "x-rapidapi-key":  API_KEY,
    "x-rapidapi-host": API_HOST,
    "Content-Type":    "application/json",
}

ACCOUNTS = [
    "MJCLocks",
    "MCbets__",
    "TheProfessor305",
    "DanGambleAI",
    "ParlayScience",
    "CodyBrownBets",
]

TWEETS_PER_USER = 100   # up to 100 per call; increase if needed


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def api_get(path: str) -> dict:
    conn = http.client.HTTPSConnection(API_HOST)
    conn.request("GET", path, headers=HEADERS)
    res  = conn.getresponse()
    body = res.read().decode("utf-8")
    if res.status == 429:
        raise RuntimeError("Rate limit hit")
    if res.status != 200:
        raise RuntimeError(f"HTTP {res.status}: {body[:200]}")
    return json.loads(body)


def get_user(username: str) -> dict:
    data = api_get(f"/user?username={username}")
    # navigate to user object
    user = (
        data.get("result", {})
            .get("data", {})
            .get("user", {})
            .get("result", {})
    )
    legacy = user.get("legacy", {})
    return {
        "username":        username,
        "display_name":    legacy.get("name", ""),
        "followers":       legacy.get("followers_count", 0),
        "following":       legacy.get("friends_count", 0),
        "tweets_count":    legacy.get("statuses_count", 0),
        "likes_given":     legacy.get("favourites_count", 0),
        "listed_count":    legacy.get("listed_count", 0),
        "account_created": legacy.get("created_at", ""),
        "verified":        legacy.get("verified", False),
        "bio":             legacy.get("description", "").replace("\n", " "),
        "location":        legacy.get("location", ""),
        "user_id":         user.get("rest_id", ""),
    }


def extract_tweet(tweet_result: dict, username: str) -> dict | None:
    if tweet_result.get("__typename") == "TweetWithVisibilityResults":
        tweet_result = tweet_result.get("tweet", {})

    legacy = tweet_result.get("legacy", {})
    if not legacy:
        return None

    # long tweets use note_tweet for full text
    note = tweet_result.get("note_tweet", {})
    if note:
        full_text = note.get("note_tweet_results", {}).get("result", {}).get("text", "") or legacy.get("full_text", "")
    else:
        full_text = legacy.get("full_text", "")

    created_raw = legacy.get("created_at", "")
    try:
        dt = datetime.strptime(created_raw, "%a %b %d %H:%M:%S +0000 %Y").replace(tzinfo=timezone.utc)
    except ValueError:
        dt = None

    is_retweet = full_text.startswith("RT @")
    is_reply   = bool(legacy.get("in_reply_to_screen_name"))
    has_media  = "media" in legacy.get("entities", {}) or "media" in legacy.get("extended_entities", {})
    has_url    = bool(legacy.get("entities", {}).get("urls"))
    hashtags   = [h["text"] for h in legacy.get("entities", {}).get("hashtags", [])]
    mentions   = [m["screen_name"] for m in legacy.get("entities", {}).get("user_mentions", [])]
    views      = tweet_result.get("views", {}).get("count", "")

    return {
        "username":       username,
        "tweet_id":       legacy.get("id_str", ""),
        "created_at_raw": created_raw,
        "date":           dt.strftime("%Y-%m-%d") if dt else "",
        "time_utc":       dt.strftime("%H:%M") if dt else "",
        "hour_utc":       dt.hour if dt else "",
        "day_of_week":    dt.strftime("%A") if dt else "",
        "type":           "retweet" if is_retweet else ("reply" if is_reply else "original"),
        "has_media":      has_media,
        "has_url":        has_url,
        "hashtags":       "|".join(hashtags),
        "mentions":       "|".join(mentions),
        "views":          views,
        "likes":          legacy.get("favorite_count", 0),
        "retweets":       legacy.get("retweet_count", 0),
        "replies":        legacy.get("reply_count", 0),
        "quotes":         legacy.get("quote_count", 0),
        "bookmarks":      legacy.get("bookmark_count", 0),
        "text":           full_text.replace("\n", " "),
    }


def get_tweets(username: str, count: int = TWEETS_PER_USER) -> list[dict]:
    data = api_get(f"/user-tweets?username={username}&count={count}")

    instructions = (
        data.get("result", {})
            .get("timeline", {})
            .get("instructions", [])
    )

    tweets = []
    for instruction in instructions:
        inst_type = instruction.get("type", "")

        # pinned tweet
        if inst_type == "TimelinePinEntry":
            tr = (
                instruction.get("entry", {})
                           .get("content", {})
                           .get("itemContent", {})
                           .get("tweet_results", {})
                           .get("result", {})
            )
            t = extract_tweet(tr, username)
            if t:
                tweets.append(t)
            continue

        if inst_type != "TimelineAddEntries":
            continue

        for entry in instruction.get("entries", []):
            content = entry.get("content", {})
            entry_type = content.get("entryType", "")

            # single tweet
            if entry_type == "TimelineTimelineItem":
                tr = (
                    content.get("itemContent", {})
                           .get("tweet_results", {})
                           .get("result", {})
                )
                t = extract_tweet(tr, username)
                if t:
                    tweets.append(t)

            # thread / conversation module
            elif entry_type == "TimelineTimelineModule":
                for item in content.get("items", []):
                    tr = (
                        item.get("item", {})
                            .get("itemContent", {})
                            .get("tweet_results", {})
                            .get("result", {})
                    )
                    t = extract_tweet(tr, username)
                    if t:
                        tweets.append(t)

    return tweets


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("\n=== Capper Twitter Research ===\n")

    profiles   = []
    all_tweets = []

    for username in ACCOUNTS:
        print(f"Pulling @{username}...")
        try:
            profile = get_user(username)
            profiles.append(profile)
            print(f"  ✓ Profile: {profile['followers']:,} followers")
        except Exception as e:
            print(f"  ✗ Profile error: {e}")

        time.sleep(1.5)

        try:
            tweets = get_tweets(username)
            all_tweets.extend(tweets)
            print(f"  ✓ Tweets: {len(tweets)} pulled")
        except Exception as e:
            print(f"  ✗ Tweets error: {e}")

        time.sleep(1.5)

    # Save profiles
    if profiles:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        p_file = Path(f"capper_profiles_{ts}.csv")
        p_fields = list(profiles[0].keys())
        with open(p_file, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=p_fields)
            w.writeheader()
            w.writerows(profiles)
        print(f"\n✓ Profiles saved: {p_file}  ({len(profiles)} accounts)")

    # Save tweets
    if all_tweets:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        t_file = Path(f"capper_tweets_{ts}.csv")
        t_fields = list(all_tweets[0].keys())
        with open(t_file, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=t_fields)
            w.writeheader()
            w.writerows(all_tweets)
        print(f"✓ Tweets saved:   {t_file}  ({len(all_tweets)} tweets)\n")

        # Quick summary in terminal
        print("--- Quick engagement summary ---")
        print(f"{'Account':<20} {'Tweets':>7} {'Avg Likes':>10} {'Avg RTs':>8} {'% Original':>11}")
        print("-" * 60)
        for username in ACCOUNTS:
            ut = [t for t in all_tweets if t["username"] == username]
            if not ut:
                continue
            orig    = [t for t in ut if t["type"] == "original"]
            avg_lk  = sum(t["likes"] for t in ut) / len(ut)
            avg_rt  = sum(t["retweets"] for t in ut) / len(ut)
            pct_orig = len(orig) / len(ut) * 100
            print(f"@{username:<19} {len(ut):>7} {avg_lk:>10.1f} {avg_rt:>8.1f} {pct_orig:>10.1f}%")
    else:
        print("No tweet data collected.")


if __name__ == "__main__":
    main()
