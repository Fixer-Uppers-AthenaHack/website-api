from datetime import datetime as dt
from typing import Literal

import requests
from bson.objectid import ObjectId
from flask import Flask, jsonify, request, session, render_template, redirect, url_for
from flask_pymongo import PyMongo as Mongo

import config


app = Flask(__name__)
app.secret_key = config.SECRET_KEY
mongo = Mongo(app, uri=config.DB_CONNECTION_STRING).db


# Main pages


@app.route("/", methods=["GET"])
def index():
    return redirect("/listings")


@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "GET":
        if "user" in session:
            session.pop("user")
        return render_template("login.html")
    elif request.method == "POST":
        user = utils_get_user(request.form["user_id"])
        if user:
            session["user"] = user
        return redirect("/", 302)


@app.route("/listings", methods=["GET"])
def listings():
    listing_list = requests.get("http://127.0.0.1:5000/api/listings").json()
    shorten_to = lambda s, max: s if len(s) < max else f"{s[:max -3]}..."
    enum_mapping = {
        "partsWanted": "Parts wanted",
        "partsAvailable": "Parts available",
        "skillsWanted": "Skills wanted",
        "skillsAvailable": "Skills available",
    }
    for listing in listing_list:
        listing.update(
            {
                "title": shorten_to(listing["title"], 64),
                "description": shorten_to(listing["description"], 100),
                "type": enum_mapping[listing["type"]],
            }
        )
    return render_template("listings.html", listings=listing_list)


@app.route("/create-listing", methods=["GET", "POST"])
def create_listing():
    if request.method == "GET":
        return render_template("create_listing.html")
    elif request.method == "POST":
        return redirect("/", 302)


# API stuff


@app.route("/api/search", methods=["GET"])
def api_index():
    """Search for resources"""
    search_term = request.args.get("query")
    if not search_term:
        return {"message": "Missing argument 'query' in request"}, 400

    data = []
    ifixit_data = utils_ifixit_search(search_term)
    if ifixit_data:
        data.extend(ifixit_data)
    return jsonify(data), 200


@app.route("/api/user/<string:user_id>", methods=["GET"])
def api_user(user_id: str):
    """Fetch a single user object"""
    user_data = utils_get_user(user_id)
    if not user_data:
        return {"message": "User not found"}, 404
    return dict(user_data), 200


@app.route("/api/create-listing", methods=["POST"])
def api_create_listing():
    """Create a listing object"""
    user_id = request.headers["authorisation"]
    user_exists = bool(utils_get_user(user_id))
    if not user_exists:
        return {"message": "Invalid authorisation header"}, 400

    data = request.get_json()
    for key in ("title", "description", "listing_type"):
        if key not in data:
            return {"message": f"Missing '{key}' field in body"}, 400
    if data["listing_type"] not in ("partsWanted", "partsAvailable", "skillsWanted", "skillsAvailable"):
        return {"message": f"listing_type not in valid enum values for this field"}, 400

    listing_id = utils_create_listing(
        author_id=request.headers["authorisation"],
        title=data["title"],
        description=data.get("description"),
        listing_type=data["listing_type"],
    )
    return {"message": "listing created", "id": listing_id}, 201


@app.route("/api/listing/<string:listing_id>", methods=["GET"])
def api_get_listing(listing_id: str):
    """Fetch a single listing object"""
    listing = utils_get_listing(listing_id)
    if not listing:
        return {"message": "Listing not found"}, 404

    return listing


@app.route("/api/listings", methods=["GET"])
def api_all_listings():
    """Fetch all listings"""
    listings = utils_get_listings()
    print("listings", listings)
    return jsonify(list(listings)), 200


def utils_ifixit_search(search_term: str) -> dict:
    r = requests.get(f"https://www.ifixit.com/api/2.0/search/{search_term}")
    data = r.json()
    if not data.get("totalResults"):
        return None

    return [{"source": "iFixit", "title": i["title"], "url": i["url"]} for i in data["results"]]


def utils_get_user(user_id: str) -> dict:
    """Fetch a user by ID"""
    user = mongo.users.find_one({"id": user_id})
    if not user:
        return {}
    assert isinstance(user, dict)
    user.pop("_id")
    return user


def utils_create_listing(
    author_id: str,
    title: str,
    description: str,
    listing_type: Literal["partsWanted", "partsAvailable", "skillsWanted", "skillsAvailable"],
) -> str:
    insert = mongo.listings.insert_one(
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


def utils_get_listing(listing_id: str) -> dict:
    """Fetch a listing by ID"""
    try:
        object_id = ObjectId(listing_id)
    except:
        return None

    listing = mongo.listings.find_one({"_id": object_id})
    utils_morph_id(listing)
    user = utils_get_user(listing.pop("author_id"))
    if user:
        listing.update({"author": user})
    return listing


def utils_get_listings():
    cursor = mongo.listings.find()
    listings = []
    for listing in cursor:
        utils_morph_id(listing)
        user = utils_get_user(listing.pop("author_id"))
        if user:
            listing.update({"author": user})
        listings.append(listing)
    return listings


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
