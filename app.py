from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, db
import os
import sys
import json
from dotenv import load_dotenv
import openai
from pydantic import BaseModel

app = Flask(__name__)
CORS(app)

load_dotenv()

# openai
openai_api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI()

# firebase
cred_path = os.getenv("FIREBASE_CRED_PATH")
url = os.getenv("FIREBASE_URL")
cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred, {
    'databaseURL': url
})


class Flashcard:
    TITLE_LENGTH_LIMIT = 50
    FRONT_TEXT_LIMIT = 200
    BACK_TEXT_LIMIT = 200
    FRONT_IMAGE_TEXT_LIMIT = 100
    BACK_IMAGE_TEXT_LIMIT = 100

    def __init__(self, title=None, front=None, back=None, front_image_url=None, back_image_url=None):
        self.update_title(title)
        self.update_front(front)
        self.update_back(back)
        self.update_front_image_url(front_image_url)
        self.update_back_image_url(back_image_url)

    def update_title(self, title):
        self.title = title[:Flashcard.TITLE_LENGTH_LIMIT]

    def update_front(self, front):
        self.front = front[:Flashcard.FRONT_IMAGE_TEXT_LIMIT] if self.front_image_url else front[:Flashcard.FRONT_TEXT_LIMIT]

    def update_back(self, back):
        self.back = back[:Flashcard.BACK_IMAGE_TEXT_LIMIT] if self.back_image_url else back[:Flashcard.BACK_TEXT_LIMIT]

    def update_front_image_url(self, front_image_url):
        self.front_image_url = front_image_url

    def update_back_image_url(self, back_image_url):
        self.back_image_url = back_image_url

    def to_dict(self):
        return {
            "title": self.title,
            "front": self.front,
            "back": self.back,
            "front_image_url": self.front_image_url,
            "back_image_url": self.back_image_url
        }

    def to_json(self):
        """
        Serializes the object to a JSON-formatted str.
        """
        return json.dumps(self.to_dict())

    @staticmethod
    def from_dict(data):
        return Flashcard(
            title=data.get("title"),
            front=data.get("front"),
            back=data.get("back"),
            front_image_url=data.get("front_image_url"),
            back_image_url=data.get("back_image_url")
        )

    @staticmethod
    def from_json(json_str):
        """
        Deserializes the JSON string to a Flashcard object.
        """
        data = json.loads(json_str)
        return Flashcard(**data)

    def __str__(self):
        return f"Flashcard\nTitle: {self.title}\nFront: {self.front}\nBack: {self.back}\nFront Image: {self.front_image_url}\nBack Image:{self.back_image_url}"


class FlashcardSchema(BaseModel):
    title: str
    front: str
    back: str
    front_image_url: str
    back_image_url: str


class FlashcardCollection(BaseModel):
    flashcards: list[FlashcardSchema]


@app.route('/hello', methods=['POST'])
def hello():
    return jsonify({'hello': 'world'}), 200


def generate_flashcards(n, topic=None, reference=None):
    if topic:
        prompt = f"Generate {n} flashcards on the topic of {topic} with the following information: \n"
    elif reference:
        prompt = f"Generate {n} additional flashcards based on the following reference: \n{reference}\n"

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": prompt}
        ],
        response_format=FlashcardCollection,
    )

    flashcards = completion.choices[0].message.parsed
    return flashcards.flashcards


flashcards = generate_flashcards(5, topic="Python programming")
for flashcard in flashcards:
    print(flashcard)
    print()