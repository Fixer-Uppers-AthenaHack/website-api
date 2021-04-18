import aiohttp
from quart import Quart, jsonify, request

import config
import utils

app = Quart(__name__)
app.db = config.db


@app.route("/api/search", methods=["GET"])
async def api_index():
    """Search for resources"""
    search_term = request.args.get("query")
    if not search_term:
        return {"message": "Missing argument 'query' in request"}, 400

    data = []
    ifixit_data = await utils.ifixit_search(search_term)
    if ifixit_data:
        data.extend(ifixit_data)
    return jsonify(data), 200


@app.route("/api/user/<string:user_id>", methods=["GET"])
async def api_user(user_id: str):
    """Fetch a single user object"""
    user_data = await utils.get_user(user_id)
    if not user_data:
        return {"message": "User not found"}, 404
    return dict(user_data), 200


@app.route("/api/create-listing", methods=["POST"])
async def api_create_listing():
    """Create a listing object"""
    user_id = request.headers["authorisation"]
    user_exists = bool(await utils.get_user(user_id))
    if not user_exists:
        return {"message": "Invalid authorisation header"}, 400
    data = request.get_json()
    for key in ("title", "description", "listing_type"):
        if key not in data:
            return {"message": f"Missing '{key}' field in body"}, 400
    if data["listing_type"] not in ("partsWanted", "partsAvailable", "skillsWanted", "skillsAvailable"):
        return {"message": f"listing_type not in valid enum values for this field"}, 400

    listing_id = await utils.create_listing(
        author_id=request.headers["authorisation"],
        title=data["title"],
        description=data.get("description"),
        listing_type=data["listing_type"],
    )
    return {"message": "listing created", "id": listing_id}, 201


@app.route("/api/listing/<string:listing_id>", methods=["GET"])
async def api_get_listing(listing_id: str):
    """Fetch a single listing object"""
    listing = await utils.get_listing(listing_id)
    if not listing:
        return {"message": "Listing not found"}, 404

    return listing


@app.route("/api/listings", methods=["GET"])
async def api_all_listings():
    """Fetch all listings"""
    listings = await utils.get_listings()
    return jsonify(list(listings)), 200


if __name__ == "__main__":
    app.run(debug=True, port=5000)
