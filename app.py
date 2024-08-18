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

    def __init__(self, id=None, title=None, front=None, back=None, front_image_url=None, back_image_url=None):
        self.id = id
        self.update_front_image_url(front_image_url)
        self.update_back_image_url(back_image_url)
        self.update_title(title)
        self.update_front(front)
        self.update_back(back)

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
            id=data.get("id"),
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
        return f"Flashcard\nID: {self.id}\nTitle: {self.title}\nFront: {self.front}\nBack: {self.back}\nFront Image: {self.front_image_url}\nBack Image:{self.back_image_url}"


class FlashcardSchema(BaseModel):
    id: int
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


# ========= FIREBASE =========
def add_user(name):
    def increment_counter(current_value):
        if current_value is None:
            return 1
        else:
            return current_value + 1

    counter_ref = db.reference('user_counter')
    new_user_id = counter_ref.transaction(increment_counter)
    name = name[:30]

    user_ref = db.reference(f'users/{new_user_id}')
    user_ref.set({
        'name': name,
        'flashcards': {},
        'card_counter': 0
    })
    print(f"New user {name} added with ID {new_user_id}. User initialized with empty flashcard collection and a card counter set to 0.")
    return new_user_id


def delete_user(user_id):
    user_ref = db.reference(f'users/{user_id}')
    user_data = user_ref.get()
    if user_data:
        user_ref.delete()
        print(f"User {user_id} and all associated flashcards have been deleted.")
        return user_id
    else:
        print(f"User {user_id} does not exist.")


def add_flashcard(user_id, flashcard_json):
    flashcard = Flashcard.from_json(flashcard_json)

    user_ref = db.reference(f'users/{user_id}')
    user_data = user_ref.get()
    if user_data:
        card_counter = user_data.get('card_counter', 0)
        flashcard.id = card_counter
        flashcards_ref = user_ref.child('flashcards')
        flashcards_ref.update({
            card_counter: flashcard.to_dict()
        })
        user_ref.update({'card_counter': card_counter + 1})
        print(f"Added new flashcard with ID {card_counter} to user {user_id}.")
        return card_counter
    else:
        print(f"User {user_id} does not exist.")


def edit_flashcard(user_id, flashcard_id, flashcard_json):
    flashcard_ref = db.reference(f'users/{user_id}/flashcards/{flashcard_id}')
    flashcard_data = flashcard_ref.get()
    if flashcard_data:
        updated_flashcard = Flashcard.from_json(flashcard_json)
        updated_flashcard.id = flashcard_id
        flashcard_ref.set(updated_flashcard.to_dict())
        print(f"Flashcard ID {flashcard_id} for user {user_id} has been updated.")
        return flashcard_id
    else:
        print(f"Flashcard ID {flashcard_id} for user {user_id} does not exist or has already been deleted.")


def delete_flashcard(user_id, flashcard_id):
    flashcard_ref = db.reference(f'users/{user_id}/flashcards/{flashcard_id}')
    flashcard_data = flashcard_ref.get()
    if flashcard_data:
        flashcard_ref.delete()
        print(f"Flashcard ID {flashcard_id} for user {user_id} has been deleted.")
        return flashcard_id
    else:
        print(f"Flashcard ID {flashcard_id} for user {user_id} does not exist or has already been deleted.")


# ========= GEN AI =========
def generate_flashcards(n, topic=None, reference=None):
    if topic:
        prompt = f"Generate {n} flashcards on the topic of {topic}. Make sure the title is <=50 chars and the front and back are <=200 chars long. \n"
    elif reference:
        prompt = f"Generate {n} additional flashcards based on the following reference: \n{reference}\nMake sure the title is <=50 chars and the front and back are <=200 chars long."

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": prompt}
        ],
        response_format=FlashcardCollection,
    )

    flashcards = completion.choices[0].message.parsed
    return flashcards.flashcards


# test generate flashcards
flashcards = generate_flashcards(2, topic="Python programming")
flashcards = [Flashcard.from_dict(flashcard.model_dump()) for flashcard in flashcards]
for flashcard in flashcards:
    print(flashcard)

# test adding user
new_user_id = add_user("Alice")

# test adding flashcard
new_flashcard_id = add_flashcard(new_user_id, flashcards[0].to_json())

# test editing flashcard
edit_flashcard(new_user_id, new_flashcard_id, flashcards[1].to_json())

# test deleting flashcard
delete_flashcard(new_user_id, new_flashcard_id)

# test deleting user
delete_user(new_user_id)



