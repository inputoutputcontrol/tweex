import argparse
import asyncio
from playwright.async_api import async_playwright
import jmespath
import re


def parsetweet(data):
    return {
        "ID": data["rest_id"],
        "Name": data["legacy"]["name"],
        "Screen Name": data["legacy"]["screen_name"],
        "Description": data["legacy"]["description"],
        "Verified": data["legacy"]["verified"],
        "Followers": data["legacy"]["followers_count"],
        "Friends": data["legacy"]["friends_count"],
        "Statuses": data["legacy"]["statuses_count"],
        "Profile URL": data["legacy"]["profile_image_url_https"],
        "Posted at": data["legacy"]["created_at"],
    }


def printtweet(d):
    for k, v in d.items():
        if isinstance(v, dict):
            print(f"{k}:")
            printtweet(v)
        else:
            print(f"{k}: {v}")


def parseuserprofile(data):
    userdata = data["legacy"]
    profile = {
        "Profile URL": userdata.get("profile_image_url_https"),
        "Verified": data.get("verification_info", {}).get("is_identity_verified"),
        "Profile Banner URL": userdata.get("profile_banner_url"),
        "Name": userdata.get("name"),
        "Media Count": userdata.get("media_count"),
        "ID": data.get("id"),
        "Display URL": userdata.get("entities", {})
        .get("url", {})
        .get("urls", [{}])[0]
        .get("display_url"),
        "Description": userdata.get("description"),
        "Created At": userdata.get("created_at"),
    }
    return profile


def printuserprofile(profile):
    for key, value in profile.items():
        print(f"{key}: {value}")


async def sct(url):
    calls = []

    async with async_playwright() as pw:
        b = await pw.chromium.launch(headless=True)
        c = await b.new_context(viewport={"width": 1920, "height": 1080})
        p = await c.new_page()
        p.on(
            "response",
            lambda response: calls.append(response)
            if response.request.resource_type == "xhr"
            else None,
        )
        await p.goto(url)
        await p.wait_for_selector("[data-testid='tweet']")
        tweetcalls = [f for f in calls if "TweetResultByRestId" in f.url]
        for xhr in tweetcalls:
            data = await xhr.json()
            result = data["data"]["tweetResult"]["result"]

            parsedtweet = {
                "Posted at": jmespath.search("legacy.created_at", result),
                "Attached URLS": jmespath.search(
                    "legacy.entities.urls[].expanded_url", result
                )
                or [],
                "Attached URLS": jmespath.search(
                    "legacy.entities.url.urls[].expanded_url", result
                )
                or [],
                "Attached Media": jmespath.search(
                    "legacy.entities.media[].media_url_https", result
                )
                or [],
                "Tagged Users": [
                    user["screen_name"]
                    for user in jmespath.search(
                        "legacy.entities.user_mentions[]", result
                    )
                    or []
                ],
                "Tagged Hashtags": [
                    hashtag["text"]
                    for hashtag in jmespath.search("legacy.entities.hashtags[]", result)
                    or []
                ],
                "Likes": jmespath.search("legacy.favorite_count", result),
                "Bookmarks": jmespath.search("legacy.bookmark_count", result),
                "Quotes": jmespath.search("legacy.quote_count", result),
                "Replies": jmespath.search("legacy.reply_count", result),
                "Retweets": jmespath.search("legacy.retweet_count", result),
                "Text": jmespath.search("legacy.full_text", result),
                "Is a quote tweet": jmespath.search("legacy.is_quote_status", result),
                "Is a retweet": jmespath.search("legacy.retweeted", result),
                "Language": jmespath.search("legacy.lang", result),
                "User ID": jmespath.search("legacy.user_id_str", result),
                "ID": jmespath.search("legacy.id_str", result),
                "Conversation ID": jmespath.search(
                    "legacy.conversation_id_str", result
                ),
                "Source": jmespath.search("source", result),
                "Views": jmespath.search("views.count", result),
                "Poll": {},
            }

            polldata = jmespath.search("card.legacy.binding_values", result) or []
            for pollentry in polldata:
                key, value = pollentry["key"], pollentry["value"]
                if "choice" in key:
                    parsedtweet["poll"][key] = value["string_value"]
                elif "end_datetime" in key:
                    parsedtweet["poll"]["end"] = value["string_value"]
                elif "last_updated_datetime" in key:
                    parsedtweet["poll"]["updated"] = value["string_value"]
                elif "counts_are_final" in key:
                    parsedtweet["poll"]["ended"] = value["boolean_value"]
                elif "duration_minutes" in key:
                    parsedtweet["poll"]["duration"] = value["string_value"]

            udata = jmespath.search("core.user_results.result", result)
            if udata:
                parsedtweet["user"] = parsetweet(udata)

            printtweet(parsedtweet)

        await c.close()
        await b.close()


async def scp(url: str) -> dict:
    calls = []

    def intercept(response):
        if response.request.resource_type == "xhr":
            calls.append(response)
        return response

    async with async_playwright() as pw:
        b = await pw.chromium.launch(headless=True)
        c = await b.new_context(viewport={"width": 1920, "height": 1080})
        p = await c.new_page()
        p.on("response", intercept)
        await p.goto(url)
        await p.wait_for_selector("[data-testid='primaryColumn']")
        tweetcalls = [f for f in calls if "UserBy" in f.url]
        for xhr in tweetcalls:
            data = await xhr.json()
            return data["data"]["user"]["result"]

    await c.close()
    await b.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="scrape twitter data")
    parser.add_argument("-url", type=str, help="tweet url to scrape")
    parser.add_argument("-user", type=str, help="twitter user url to scrape")
    args = parser.parse_args()
    if args.url:
        asyncio.run(sct(args.url))
    elif args.user:
        pattern = r"^https?://"
        if re.match(pattern, args.user):
            uurl = args.user
        else:
            uurl = f"https://x.com/{args.user}"
        userdata = asyncio.run(scp(uurl))
        userprofile = parseuserprofile(userdata)
        printuserprofile(userprofile)
    else:
        parser.print_help()
