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
# from clerk_backend_api import Clerk
# from flask_jwt_extended import JWTManager, jwt_required, get_jwt_identity
from prompt_templates import *

load_dotenv()
app = Flask(__name__)
# app.config['JWT_SECRET_KEY'] = os.getenv("JWT_SECRET_KEY")
# jwt = JWTManager(app)
CORS(app)

# clerk
# bearer_auth = os.getenv("CLERK_BEARER_TOKEN")
# clerk = Clerk(bearer_auth=bearer_auth)

# openai
openai_api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI()

# firebase
cred_path = os.path.join('config', os.getenv("FIREBASE_CRED_FN"))
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

    def __init__(self, id=None, title=None, front=None, back=None,
                 front_image_url=None, back_image_url=None):
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


# ========= ENDPOINTS =========
@app.route('/hello', methods=['POST'])
def hello():
    return jsonify({'hello': 'world'}), 200


@app.route('/add-user', methods=['POST'])
# @jwt_required()
def add_user_endpoint():
    data = request.json
    clerk_user_id = data.get('user_id')
    name = data.get('name')
    new_user_id = add_user(clerk_user_id, name)
    return jsonify({'user_id': new_user_id}), 200


@app.route('/delete-user', methods=['POST'])
# @jwt_required()
def delete_user_endpoint():
    data = request.json
    clerk_user_id = data.get('user_id')
    if not verify_user_exists(clerk_user_id):
        return jsonify({'error': 'Invalid user credentials.'}), 401
    deleted_user_id = delete_user(clerk_user_id)
    return jsonify({'user_id': deleted_user_id}), 200


@app.route('/create-deck', methods=['POST'])
# @jwt_required()
def create_deck_endpoint():
    data = request.json
    clerk_user_id = data.get('user_id')
    if not verify_user_exists(clerk_user_id):
        return jsonify({'error': 'Invalid user credentials.'}), 401
    deck_name = data.get('deck_name')
    description = data.get('description')
    new_deck_id = create_deck(clerk_user_id, deck_name, description)
    return jsonify({'deck_id': new_deck_id}), 200


@app.route('/modify-deck', methods=['POST'])
# @jwt_required()
def modify_deck_endpoint():
    data = request.json
    clerk_user_id = data.get('user_id')
    if not verify_user_exists(clerk_user_id):
        return jsonify({'error': 'Invalid user credentials.'}), 401
    if not verify_user_has_deck(clerk_user_id, data.get('deck_id')):
        return jsonify(
            {'error': 'User does not have access to this deck.'}), 403
    deck_id = data.get('deck_id')
    deck_name = data.get('deck_name')
    description = data.get('description')
    updated_deck_id = modify_deck(deck_id, deck_name, description)
    return jsonify({'deck_id': updated_deck_id}), 200


@app.route('/add-deck-to-user', methods=['POST'])
# @jwt_required()
def add_deck_to_user_endpoint():
    data = request.json
    clerk_user_id = data.get('user_id')
    if not verify_user_exists(clerk_user_id):
        return jsonify({'error': 'Invalid user credentials.'}), 401
    deck_id = data.get('deck_id')
    added_deck_id = add_deck_to_user(clerk_user_id, deck_id)
    return jsonify({'deck_id': added_deck_id}), 200


@app.route('/remove-deck-from-user', methods=['POST'])
# @jwt_required()
def remove_deck_from_user_endpoint():
    data = request.json
    clerk_user_id = data.get('user_id')
    if not verify_user_exists(clerk_user_id):
        return jsonify({'error': 'Invalid user credentials.'}), 401
    deck_id = data.get('deck_id')
    removed_deck_id = remove_deck_from_user(clerk_user_id, deck_id)
    return jsonify({'deck_id': removed_deck_id}), 200


@app.route('/get-decks', methods=['GET'])
# @jwt_required()
def get_decks_endpoint():
    clerk_user_id = request.args.get('user_id')
    if not verify_user_exists(clerk_user_id):
        return jsonify({'error': 'Invalid user credentials.'}), 401
    decks = get_decks(clerk_user_id)
    return jsonify({'decks': decks}), 200


@app.route('/get-flashcards', methods=['GET'])
def get_flashcards_endpoint():
    deck_id = request.args.get('deck_id')
    flashcards = get_flashcards(deck_id)
    if not flashcards:
        return jsonify({'error': 'Deck does not exist.'}), 404
    return jsonify({'flashcards': flashcards}), 200


@app.route('/add-flashcard', methods=['POST'])
# @jwt_required()
def add_flashcard_endpoint():
    data = request.json
    clerk_user_id = data.get('user_id')
    if not verify_user_exists(clerk_user_id):
        return jsonify({'error': 'Invalid user credentials.'}), 401
    deck_id = data.get('deck_id')
    if not verify_user_has_deck(clerk_user_id, deck_id):
        return jsonify(
            {'error': 'User does not have access to this deck.'}), 403
    flashcard_json = data.get('flashcard')
    new_flashcard_id = add_flashcard(deck_id, flashcard_json)
    return jsonify({'flashcard_id': new_flashcard_id}), 200


@app.route('/edit-flashcard', methods=['POST'])
# @jwt_required()
def edit_flashcard_endpoint():
    data = request.json
    clerk_user_id = data.get('user_id')
    if not verify_user_exists(clerk_user_id):
        return jsonify({'error': 'Invalid user credentials.'}), 401
    deck_id = data.get('deck_id')
    if not verify_user_has_deck(clerk_user_id, deck_id):
        return jsonify(
            {'error': 'User does not have access to this deck.'}), 403
    flashcard_id = data.get('flashcard_id')
    flashcard_json = data.get('flashcard')
    edited_flashcard_id = edit_flashcard(deck_id, flashcard_id, flashcard_json)
    return jsonify({'flashcard_id': edited_flashcard_id}), 200


@app.route('/delete-flashcard', methods=['POST'])
# @jwt_required()
def delete_flashcard_endpoint():
    data = request.json
    clerk_user_id = data.get('user_id')
    if not verify_user_exists(clerk_user_id):
        return jsonify({'error': 'Invalid user credentials.'}), 401
    # clerk_user_id = get_jwt_identity()
    deck_id = data.get('deck_id')
    if not verify_user_has_deck(clerk_user_id, deck_id):
        return jsonify(
            {'error': 'User does not have access to this deck.'}), 403
    flashcard_id = data.get('flashcard_id')
    deleted_flashcard_id = delete_flashcard(deck_id, flashcard_id)
    return jsonify({'flashcard_id': deleted_flashcard_id}), 200


@app.route('/generate-flashcards', methods=['POST'])
def generate_flashcards_endpoint():
    data = request.json
    clerk_user_id = data.get('user_id')
    if not verify_user_exists(clerk_user_id):
        return jsonify({'error': 'Invalid user credentials.'}), 401
    n = data.get('n')
    topic = data.get('topic')
    reference = data.get('reference')
    flashcards = generate_flashcards(n, topic, reference)
    flashcards = [flashcard.model_dump() for flashcard in flashcards]
    return jsonify({'flashcards': flashcards}), 200


# ========= FIREBASE =========
def add_user(clerk_user_id, name):
    name = name[:30]
    user_ref = db.reference(f'users/{clerk_user_id}')
    user_ref.set({
        'name': name,
        'decks': [],
    })
    print(
        f"New user {name} added with Clerk ID {clerk_user_id}. User initialized with empty flashcard collection.")
    return clerk_user_id


def verify_user_exists(user_id):
    user_ref = db.reference(f'users/{user_id}')
    user_data = user_ref.get()
    if user_data:
        return True
    else:
        print(f"User {user_id} does not exist.")
        return False


def delete_user(user_id):
    user_ref = db.reference(f'users/{user_id}')
    user_data = user_ref.get()
    if user_data:
        user_ref.delete()
        print(
            f"User {user_id} and all associated flashcards have been deleted.")
        return user_id
    else:
        print(f"User {user_id} does not exist.")
        return None


def create_deck(user_id, deck_name, description=""):
    def increment_counter(current_value):
        if current_value is None:
            return 1
        else:
            return current_value + 1

    counter_ref = db.reference('deck_counter')
    new_deck_id = counter_ref.transaction(increment_counter)
    deck_name = deck_name[:30]

    deck_ref = db.reference(f'decks/{new_deck_id}')
    deck_ref.set({
        'owner': user_id,
        'name': deck_name,
        'description': description,
        'flashcards': {},
        'card_counter': 0
    })
    print(
        f"New deck {deck_name} added with ID {new_deck_id}. Deck initialized with empty flashcard collection.")
    return new_deck_id


def modify_deck(deck_id, deck_name, description):
    deck_ref = db.reference(f'decks/{deck_id}')
    deck_data = deck_ref.get()
    if deck_data:
        deck_ref.update({
            'name': deck_name,
            'description': description
        })
        print(f"Deck {deck_id} has been updated.")
        return deck_id
    else:
        print(f"Deck {deck_id} does not exist.")
        return None


def delete_deck(deck_id):
    deck_ref = db.reference(f'decks/{deck_id}')
    deck_data = deck_ref.get()
    if deck_data:
        deck_ref.delete()
        print(
            f"Deck {deck_id} and all associated flashcards have been deleted.")
        return deck_id
    else:
        print(f"Deck {deck_id} does not exist.")
        return None


def add_deck_to_user(user_id, deck_id):
    user_ref = db.reference(f'users/{user_id}')
    user_data = user_ref.get()
    if user_data:
        decks = user_data.get('decks', [])
        decks.append(deck_id)
        user_ref.update({'decks': decks})
        print(f"Deck {deck_id} added to user {user_id}.")
        return deck_id
    else:
        print(f"User {user_id} does not exist.")
        return None


def verify_user_has_deck(user_id, deck_id):
    user_ref = db.reference(f'users/{user_id}')
    user_data = user_ref.get()
    if user_data:
        decks = user_data.get('decks', [])
        if deck_id in decks:
            if check_deck_exists(deck_id):
                deck = db.reference(f'decks/{deck_id}').get()
                if deck['owner'] == user_id:
                    return True
        else:
            print(f"User {user_id} does not have deck {deck_id}.")
            return False
    else:
        print(f"User {user_id} does not exist.")
        return False


def remove_deck_from_user(user_id, deck_id):
    user_ref = db.reference(f'users/{user_id}')
    user_data = user_ref.get()
    if user_data:
        decks = user_data.get('decks', [])
        if deck_id in decks:
            decks.remove(deck_id)
            user_ref.update({'decks': decks})
            print(f"Deck {deck_id} removed from user {user_id}.")
            return deck_id
        else:
            print(f"Deck {deck_id} is not associated with user {user_id}.")
    else:
        print(f"User {user_id} does not exist.")
        return None


def get_decks(user_id):
    user_ref = db.reference(f'users/{user_id}')
    user_data = user_ref.get()
    if user_data:
        decks = user_data.get('decks', [])
        named_decks = {}
        for deck_id in decks:
            deck_owner, deck_name, deck_description = check_deck_exists(deck_id)
            if not deck_name and not deck_description:
                decks.remove(deck_id)
            else:
                named_decks.update(
                    {"deck_id": deck_id, "deck_owner": deck_owner, "deck_name": deck_name, "deck_description": deck_description})
        user_ref.update({'decks': decks})
        print(f"User {user_id} has the following decks: {named_decks}")
        return named_decks
    else:
        print(f"User {user_id} does not exist.")
        return None


def add_flashcard(deck_id, flashcard_json):
    flashcard = Flashcard.from_json(flashcard_json)

    deck_ref = db.reference(f'decks/{deck_id}')
    deck_data = deck_ref.get()
    if deck_data:
        card_counter = deck_data.get('card_counter', 0)
        flashcard.id = card_counter
        flashcards_ref = deck_ref.child('flashcards')
        flashcards_ref.update({
            card_counter: flashcard.to_dict()
        })
        deck_ref.update({'card_counter': card_counter + 1})
        print(f"Added new flashcard with ID {card_counter} to deck {deck_id}.")
        return card_counter
    else:
        print(f"Deck {deck_id} does not exist.")
        return None


def edit_flashcard(deck_id, flashcard_id, flashcard_json):
    flashcard_ref = db.reference(f'decks/{deck_id}/flashcards/{flashcard_id}')
    flashcard_data = flashcard_ref.get()
    if flashcard_data:
        updated_flashcard = Flashcard.from_json(flashcard_json)
        updated_flashcard.id = flashcard_id
        flashcard_ref.set(updated_flashcard.to_dict())
        print(
            f"Flashcard ID {flashcard_id} for deck {deck_id} has been updated.")
        return flashcard_id
    else:
        print(
            f"Flashcard ID {flashcard_id} for deck {deck_id} does not exist or has already been deleted.")
        return None


def delete_flashcard(deck_id, flashcard_id):
    flashcard_ref = db.reference(f'decks/{deck_id}/flashcards/{flashcard_id}')
    flashcard_data = flashcard_ref.get()
    if flashcard_data:
        flashcard_ref.delete()
        print(
            f"Flashcard ID {flashcard_id} for deck {deck_id} has been deleted.")
        return flashcard_id
    else:
        print(
            f"Flashcard ID {flashcard_id} for deck {deck_id} does not exist or has already been deleted.")
        return None


def check_deck_exists(deck_id):
    deck_ref = db.reference(f'decks/{deck_id}')
    deck_data = deck_ref.get()
    if deck_data is not None:
        deck_owner = deck_data.get('owner')
        deck_name = deck_data.get('name')
        deck_description = deck_data.get('description')
    else:
        deck_owner = None
        deck_name = None
        deck_description = None
    return deck_owner, deck_name, deck_description


def get_flashcards(deck_id):
    deck_ref = db.reference(f'decks/{deck_id}')
    deck_data = deck_ref.get()
    if deck_data:
        flashcards = deck_data.get('flashcards', {})
        print(f"Deck {deck_id} has the following flashcards: {flashcards}")
        return flashcards
    else:
        print(f"Deck {deck_id} does not exist.")
        return None


# ========= GEN AI =========
def generate_flashcards(n, topic=None, reference=None, text=None):
    if topic:
        prompt = FLASHCARD_PROMPT_TOPIC.format(n=n, topic=topic)
    elif reference:
        prompt = FLASHCARD_PROMPT_REFERENCE.format(n=n, reference=reference)
    elif text:
        prompt = FLASHCARD_PROMPT_FROM_TEXT.format(n=n, text=text)
    else:
        raise ValueError(
            "You must provide a topic, reference, or text to generate flashcards.")

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": prompt}
        ],
        response_format=FlashcardCollection,
    )

    flashcards = completion.choices[0].message.parsed
    return flashcards.flashcards


# ========= UTILS =========
def clear_all_decks():
    db.reference('decks').delete()
    db.reference('deck_counter').set(0)
    print("All decks have been deleted.")


def clear_all_users():
    db.reference('users').delete()
    print("All users have been deleted.")


# ========= TESTS =========
def test_firebase_and_gen():
    # test generate flashcards
    flashcards = generate_flashcards(2, topic="Python programming")
    flashcards = [Flashcard.from_dict(flashcard.model_dump())
                  for flashcard in flashcards]
    for flashcard in flashcards:
        print(flashcard)

    # test adding users
    new_user_id_1 = add_user(0, "Alice")
    new_user_id_2 = add_user(1, "Bob")

    # test adding decks
    new_deck_id_1 = create_deck(0, "Python Programming")
    new_deck_id_2 = create_deck(1, "Data Science")

    # test adding deck to users
    add_deck_to_user(new_user_id_1, new_deck_id_1)
    add_deck_to_user(new_user_id_2, new_deck_id_1)

    # test adding flashcard
    new_flashcard_id = add_flashcard(new_deck_id_1, flashcards[0].to_json())

    # test editing flashcard
    edit_flashcard(new_deck_id_1, new_flashcard_id, flashcards[1].to_json())

    # # test deleting flashcard
    # delete_flashcard(new_deck_id_1, new_flashcard_id)

    # # test removing deck from user
    # remove_deck_from_user(new_user_id_1, new_deck_id_1)

    # # test deleting deck
    # delete_deck(new_deck_id_1)

    # # test deleting user
    # delete_user(new_user_id_1)


if __name__ == '__main__':
    app.run(debug=True)
