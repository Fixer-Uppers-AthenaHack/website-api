from datetime import datetime as dt
from typing import Literal

import aiohttp
import bson
from bson.objectid import ObjectId
from quart import Quart, jsonify, request
from quart_motor import Motor

import config
import utils

app = Quart(__name__)
mongo = Motor(app, uri=config.DB_CONNECTION_STRING).db


@app.route("/api/search", methods=["GET"])
async def api_index():
    """Search for resources"""
    search_term = request.args.get("query")
    if not search_term:
        return {"message": "Missing argument 'query' in request"}, 400

    data = []
    ifixit_data = await utils_ifixit_search(search_term)
    if ifixit_data:
        data.extend(ifixit_data)
    return jsonify(data), 200


@app.route("/api/user/<string:user_id>", methods=["GET"])
async def api_user(user_id: str):
    """Fetch a single user object"""
    user_data = await utils_get_user(user_id)
    if not user_data:
        return {"message": "User not found"}, 404
    return dict(user_data), 200


@app.route("/api/create-listing", methods=["POST"])
async def api_create_listing():
    """Create a listing object"""
    user_id = request.headers["authorisation"]
    user_exists = bool(await utils_get_user(user_id))
    if not user_exists:
        return {"message": "Invalid authorisation header"}, 400

    data = request.get_json()
    for key in ("title", "description", "listing_type"):
        if key not in data:
            return {"message": f"Missing '{key}' field in body"}, 400
    if data["listing_type"] not in ("partsWanted", "partsAvailable", "skillsWanted", "skillsAvailable"):
        return {"message": f"listing_type not in valid enum values for this field"}, 400

    listing_id = await utils_create_listing(
        author_id=request.headers["authorisation"],
        title=data["title"],
        description=data.get("description"),
        listing_type=data["listing_type"],
    )
    return {"message": "listing created", "id": listing_id}, 201


@app.route("/api/listing/<string:listing_id>", methods=["GET"])
async def api_get_listing(listing_id: str):
    """Fetch a single listing object"""
    listing = await utils_get_listing(listing_id)
    if not listing:
        return {"message": "Listing not found"}, 404

    return listing


@app.route("/api/listings", methods=["GET"])
async def api_all_listings():
    """Fetch all listings"""
    listings = await utils_get_listings()
    return jsonify(list(listings)), 200


async def utils_ifixit_search(search_term: str) -> dict:
    async with aiohttp.request("GET", f"https://www.ifixit.com/api/2.0/search/{search_term}") as response:
        data = await response.json()
    if not data.get("totalResults"):
        return None

    return [{"source": "iFixit", "title": i["title"], "url": i["url"]} for i in data["results"]]


async def utils_get_user(user_id: str) -> dict:
    """Fetch a user by ID"""
    user = await mongo.users.find_one({"id": user_id})
    if not user:
        return {}
    assert isinstance(user, dict)
    user.pop("_id")
    return user


async def utils_create_listing(
    author_id: str,
    title: str,
    description: str,
    listing_type: Literal["partsWanted", "partsAvailable", "skillsWanted", "skillsAvailable"],
) -> str:
    insert = await mongo.listings.insert_one(
        {
            "title": title,
            "description": description,
            "listing_type": listing_type,
            "author_id": author_id,
            "created_at": int(dt.timestamp(dt.utcnow())),
        }
    )
    return str(insert.inserted_id)


def utils_morph_id(d: dict):
    """Replace _id with id in dict"""
    d.update({"id": str(d.pop("_id"))})


async def utils_get_listing(listing_id: str) -> dict:
    """Fetch a listing by ID"""
    try:
        object_id = ObjectId(listing_id)
    except:
        return None

    listing = await mongo.listings.find_one({"_id": object_id})
    utils_morph_id(listing)
    user = await utils_get_user(listing.pop("author_id"))
    if user:
        listing.update({"author": user})
    return listing


async def utils_get_listings():
    cursor = mongo.listings.find().sort("created_at", -1)
    listings = []
    async for listing in cursor:
        utils_morph_id(listing)
        user = await utils_get_user(listing.pop("author_id"))
        if user:
            listing.update({"author": user})
        listings.append(listing)
    return listings


if __name__ == "__main__":
    app.run(debug=True, port=5000)
