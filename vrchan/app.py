import httpx
from upstash_redis import Redis
import json
import traceback
from datetime import datetime, timezone, timedelta
from typing import Any
from vrchan.api import VRChatAPI
from vrchan.config import AppConfig


def send_discord_message(
    url: str,
    message: str,
    embeds: list[dict] | None = None,
    components: list[dict] | None = None,
):
    data: dict[str, Any] = {"content": message}
    if embeds:
        data["embeds"] = embeds
    if components:
        data["components"] = components
    httpx.post(url, json=data)


def notify_group_announcements(
    group_id: str, api: VRChatAPI, redis: Redis, webhook_url: str
):
    announcements = api.get_announcement(group_id)
    print(announcements)


def notify_group_posts(group_id: str, api: VRChatAPI, redis: Redis, webhook_url: str):
    posts = api.get_posts(group_id)
    print(posts)


def notify_group_instances(
    group_id: str,
    api: VRChatAPI,
    redis: Redis,
    webhook_url: str,
    embed_thumbnail_url: str | None,
):
    instances = api.get_group_instances(group_id)

    for instance in instances:
        instance_id = instance["instanceId"]
        if redis.get(f"instance_{instance_id}"):
            continue

        world = instance["world"]
        world_id = world["id"]
        world_name = world["name"] or "(NO TITLE)"
        world_description = world["description"]
        world_url = f"https://vrchat.com/home/launch?worldId={world_id}"
        instance_url = f"https://vrchat.com/home/launch?worldId={world_id}&instanceId={instance_id}"
        thumbnail_image_url = world["thumbnailImageUrl"]
        created_at = datetime.fromisoformat(world["created_at"]).astimezone(
            timezone(timedelta(hours=9))
        )

        redis.set(
            f"instance_{instance_id}",
            json.dumps(
                {
                    "world_created_at": created_at.strftime("%Y/%m/%d %H:%M:%S"),
                    "world_id": world_id,
                    "world_name": world_name,
                    "world_description": world_description,
                    "world_url": world_url,
                    "thumbnail_image_url": thumbnail_image_url,
                }
            ),
            ex=60 * 60 * 24 * 7,  # 7 days
        )

        embeds = [
            {
                "title": world_name,
                "url": world_url,
                "description": world_description,
                "image": {"url": thumbnail_image_url},
                "fields": [
                    {
                        "name": "ワールド公開日",
                        "value": created_at.strftime("%Y年%m月%d日"),
                        "inline": False,
                    },
                    {
                        "name": ":fire: Popularity",
                        "value": world["popularity"],
                        "inline": True,
                    },
                    {
                        "name": ":bookmark: Bookmarks",
                        "value": world["favorites"],
                        "inline": True,
                    },
                ],
            }
        ]

        if embed_thumbnail_url:
            embeds[0]["thumbnail"] = {"url": embed_thumbnail_url}

        components = [
            {
                "type": 1,
                "components": [
                    {
                        "type": 2,
                        "style": 5,
                        "url": instance_url,
                        "label": "Launch Instance",
                    },
                ],
            }
        ]

        send_discord_message(
            webhook_url,
            "グループインスタンス通知",
            embeds=embeds,
            components=components,
        )

    if len(instances) == 0:
        print("No instances found")


def notify_hot_worlds(_group_id: str, api: VRChatAPI, redis: Redis, webhook_url: str):
    worlds = api.search_world(
        sort="hotness", tag="system_approved,system_published_recently"
    )
    hot_worlds = json.loads(redis.get("hot_worlds") or "[]")

    # remove old hot worlds
    hot_worlds = [
        world
        for world in hot_worlds
        if datetime.fromisoformat(world["date"]) > datetime.now() - timedelta(days=30)
    ]
    hot_world_ids = [world["id"] for world in hot_worlds]

    # まだ紹介していないワールドを3つピックする
    # 足りない場合はいったん未対応 (search_worldで続きを取得するべき)
    picks = 3
    picked_worlds = []
    for world in worlds:
        if world["id"] in hot_world_ids:
            print(f"skip {world['id']}")
            continue

        picked_worlds.append(world)
        hot_worlds.append({"id": world["id"], "date": datetime.now().isoformat()})
        if len(picked_worlds) == picks:
            break

    redis.set("hot_worlds", json.dumps(hot_worlds))

    if len(picked_worlds) == 0:
        print("No hot worlds found")
        return

    embeds = []
    for world in picked_worlds:
        world_name = world["name"] or "(NO TITLE)"
        world_url = f"https://vrchat.com/home/launch?worldId={world['id']}"
        # world_description = world["description"]
        thumbnail_image_url = world["thumbnailImageUrl"]
        created_at = datetime.fromisoformat(world["created_at"]).astimezone(
            timezone(timedelta(hours=9))
        )
        embeds.append(
            {
                "title": world_name,
                "url": world_url,
                # "description": world_description,
                "image": {"url": thumbnail_image_url},
                "fields": [
                    {
                        "name": "ワールド公開日",
                        "value": created_at.strftime("%Y年%m月%d日"),
                        "inline": False,
                    },
                    {
                        "name": ":fire: Popularity",
                        "value": world["popularity"],
                        "inline": True,
                    },
                    {
                        "name": ":bookmark: Bookmarks",
                        "value": world["favorites"],
                        "inline": True,
                    },
                ],
            }
        )

    send_discord_message(webhook_url, "VRCおすすめワールドピックアップ", embeds=embeds)


def main(
    username: str,
    password: str,
    user_agent: str,
    otp_secret: str,
    group_id: str,
    webhook_url: str,
    embed_thumbnail_url: str | None,
    redis: Redis,
    runs: str,
):
    api = VRChatAPI(
        username,
        password,
        totp_secret=otp_secret,
    )

    # 認証Cookieを取得
    if cookie := redis.get(f"cookie_{username}"):
        api.set_cookies(json.loads(cookie))

    try:
        if "group_instances" in runs:
            notify_group_instances(
                group_id, api, redis, webhook_url, embed_thumbnail_url
            )
        if "hot_worlds" in runs:
            notify_hot_worlds(group_id, api, redis, webhook_url)
        # notify_group_posts(group_id, api, redis, webhook_url)
    except Exception:
        traceback.print_exc()
    finally:
        # Cookieを更新
        redis.set(
            f"cookie_{username}", json.dumps(api.get_cookies()), ex=60 * 60 * 24 * 30
        )


def lambda_handler_group_instances(event, context):
    config = AppConfig()
    redis = Redis(config.upstash_redis_rest_url, config.upstash_redis_rest_token)

    main(
        config.vrc_username,
        config.vrc_password,
        config.vrc_user_agent,
        config.otp_secret,
        config.vrc_group_id,
        config.discord_webhook_url,
        config.thumbnail_url,
        redis,
        "group_instances",
    )


def lambda_handler_hot_worlds(event, context):
    config = AppConfig()
    redis = Redis(config.upstash_redis_rest_url, config.upstash_redis_rest_token)

    main(
        config.vrc_username,
        config.vrc_password,
        config.vrc_user_agent,
        config.otp_secret,
        config.vrc_group_id,
        config.discord_webhook_url,
        config.thumbnail_url,
        redis,
        "hot_worlds",
    )


if __name__ == "__main__":
    config = AppConfig()
    redis = Redis(config.upstash_redis_rest_url, config.upstash_redis_rest_token)

    main(
        config.vrc_username,
        config.vrc_password,
        config.vrc_user_agent,
        config.otp_secret,
        config.vrc_group_id,
        config.discord_webhook_url,
        config.thumbnail_url,
        redis,
        runs="group_instances,hot_worlds",
    )
