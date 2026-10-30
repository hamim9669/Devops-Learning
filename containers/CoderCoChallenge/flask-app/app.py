import os
from flask import Flask, jsonify
import redis

app = Flask(__name__)

redis_host = os.environ.get("REDIS_HOST", "redis")
redis_port = int(os.environ.get("REDIS_PORT", 6379))

cache = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)


@app.route("/")
def welcome():
    return jsonify(message="Welcome to the CoderCo Containers Challenge!")


@app.route("/count")
def count():
    visits = cache.incr("visits")
    return jsonify(visits=visits)


if __name__ == "__main__":
   app.run(host="0.0.0.0", port=5000)


            
