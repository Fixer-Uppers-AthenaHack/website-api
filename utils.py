import aiohttp
from typing import Literal
import config
from datetime import datetime as dt
import bson
from bson.objectid import ObjectId


async def ifixit_search(search_term: str) -> dict:
    async with aiohttp.request("GET", f"https://www.ifixit.com/api/2.0/search/{search_term}") as response:
        data = await response.json()
    if not data.get("totalResults"):
        return None

    return [{"source": "iFixit", "title": i["title"], "url": i["url"]} for i in data["results"]]


async def get_user(user_id: str) -> dict:
    """Fetch a user by ID"""
    try:
        object_id = ObjectId(user_id)
    except bson.errors.InvalidId:
        return None
    user = await config.db.users.find_one({"_id": object_id})
    if not user:
        return user

    morph_id(user)
    assert isinstance(user, dict)
    return user


async def create_listing(
    author_id: str,
    title: str,
    description: str,
    listing_type: Literal["partsWanted", "partsAvailable", "skillsWanted", "skillsAvailable"],
) -> str:
    insert = await config.db.listings.insert_one(
        {
            "title": title,
            "description": description,
            "listing_type": listing_type,
            "author_id": author_id,
            "created_at": int(dt.timestamp(dt.utcnow())),
        }
    )
    return str(insert.inserted_id)


def morph_id(d: dict):
    """Replace _id with id in dict"""
    d.update({"id": str(d.pop("_id"))})


async def get_listing(listing_id: str) -> dict:
    """Fetch a listing by ID"""
    try:
        object_id = ObjectId(listing_id)
    except:
        return None

    listing = await config.db.listings.find_one({"_id": object_id})
    morph_id(listing)
    user = await get_user(listing.pop("author_id"))
    if user:
        listing.update({"author": user})
    return listing


async def get_listings():
    cursor = config.db.listings.find().sort("created_at", -1)
    listings = await cursor.to_list(length=100)
    return listings