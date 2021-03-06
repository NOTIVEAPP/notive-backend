import functools
import time
import bcrypt
from flask import (
    Blueprint, g, request, session, jsonify, make_response, Response
)
from sqlalchemy import Table
from sqlalchemy.exc import SQLAlchemyError
from .util import validate_auth_key, get_json_from_keys
from .db import get_db
from .env import FSQ_CLIENT_ID, FSQ_CLIENT_SECRET
from email_validator import validate_email, EmailNotValidError

bp = Blueprint('auth', __name__, url_prefix='/auth')


def get_hashed_password(plain_text_password):
    # Hash a password for the first time
    return bcrypt.hashpw(str(plain_text_password).encode('utf-8'), bcrypt.gensalt(12))


def check_password(plain_text_password, hashed_password):
    # Check hashed password. Using bcrypt, the salt is saved into the hash itself
    return bcrypt.checkpw(str(plain_text_password).encode('utf-8'), hashed_password.encode('utf-8'))


@bp.route('/register', methods=['POST'], strict_slashes=False)
def register():
    if not validate_auth_key(request):
        return Response(status=401)
    else:
        json_data = get_json_from_keys(request, ['name', 'password', 'email'])
        if json_data is False:
            return make_response(jsonify(
                {"message": "Request body must be JSON."}), 400)
        elif json_data is None:
            return make_response(jsonify({"message": "Invalid parameters."}), 400)
        else:
            name = json_data['name']
            password_plain = json_data['password']
            email = json_data['email']

            try:
                v = validate_email(email)  # validate and get info
                email = v["email"]  # replace with normalized form
            except EmailNotValidError as e:
                # email is not valid, exception message is human-readable
                return make_response(jsonify({"message": str(e)}), 400)

            db = get_db()
            con, engine, metadata = db['con'], db['engine'], db['metadata']
            users = Table('User', metadata, autoload=True)

            if not name or not password_plain or not email:
                msg = {"message": "Error: Missing parameters!"}
                return make_response(jsonify(msg), 400)

            if users.select(users.c.email == email).execute().first():
                msg = {"message": "There is an existing user with this e-mail address!"}
                return make_response(jsonify(msg), 400)
            try:
                con.execute(users.insert(), name=name, email=email,
                            password=get_hashed_password(json_data['password']).decode("utf-8"),
                            created_at=int(time.time()))
                msg = {"message": "You have registered successfully!"}
                return make_response(jsonify(msg), 200)
            except SQLAlchemyError as e:
                error = e.__dict__['orig']
                print("DB ERROR: " + str(error))
                msg = {"message": "A server error has been occurred. "
                                  "Please try again later and contact us if the error persists. (Error code: "
                                  + str(error.args[0]) + ")",
                       "data": str(error)}
                return make_response(jsonify(msg), 500)


@bp.route('/login', methods=['POST'], strict_slashes=False)
def login():
    if not validate_auth_key(request):
        return Response(status=401)
    else:
        json_data = get_json_from_keys(request, ['email', 'password'])
        if json_data is False:
            return make_response(jsonify(
                {"message": "Request body must be JSON."}), 400)
        elif json_data is None:
            return make_response(jsonify({"message": "Invalid parameters."}), 400)
        else:
            email = json_data['email']
            password = json_data['password']

            if not email or not password:
                msg = {"message": "Error: Missing parameters!"}
                return make_response(jsonify(msg), 400)

            db = get_db()
            con, engine, metadata = db['con'], db['engine'], db['metadata']
            users = Table('User', metadata, autoload=True)
            user = users.select(users.c.email == email).execute().first()
            if not user:
                msg = {"message": "Error: Invalid e-mail."}
                return make_response(jsonify(msg), 400)

            passcheck = check_password(password, user['password'])
            if email != user['email'] or passcheck is False:
                msg = {"message": "Error: Invalid e-mail or password!"}
                return make_response(jsonify(msg), 400)
            else:
                msg = {"message": "You have been logged in successfully!",
                       "data": {"user": {"id": user['id'],
                                         "email": user['email'],
                                         "name": user['name']}
                                }}
                session.clear()
                session['user_id'] = user['id']

                return make_response(jsonify(msg), 200)


@bp.route('/update_password', methods=['PUT'], strict_slashes=False)
def update_pass():
    if not validate_auth_key(request):
        return Response(status=401)
    else:
        json_data = get_json_from_keys(request, ['email', 'password'])
        if json_data is False:
            return make_response(jsonify(
                {"message": "Request body must be JSON."}), 400)
        elif json_data is None:
            return make_response(jsonify({"message": "Invalid parameters."}), 400)
        else:
            email = json_data['email']
            password = json_data['password']

            db = get_db()
            con, engine, metadata = db['con'], db['engine'], db['metadata']
            user_table = Table('User', metadata, autoload=True)
            try:
                con.execute(user_table.update().where(user_table.c.email == email).values(
                    password=get_hashed_password(password).decode("utf-8")))

                msg = {"message": "Success! User password is updated."}
                return make_response(jsonify(msg), 200)
            except SQLAlchemyError as e:
                error = e.__dict__['orig']
                print("DB ERROR: " + str(error))
                msg = {"message": "A server error has been occurred. "
                                  "Please try again later and contact us if the error persists. (Error code: "
                                  + str(error.args[0]) + ")",
                       "data": str(error)}
                return make_response(jsonify(msg), 500)


@bp.route('/fsq_access', methods=['GET'], strict_slashes=False)
def provide_fsq_access():
    if not validate_auth_key(request):
        return Response(status=401)
    else:
        data = {"FSQ_CLIENT_ID": FSQ_CLIENT_ID,
                "FSQ_CLIENT_SECRET": FSQ_CLIENT_SECRET}
        return make_response(jsonify(data), 200)


@bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        db = get_db()
        con, engine, metadata = db['con'], db['engine'], db['metadata']
        users = Table('User', metadata, autoload=True)
        g.user = users.select(users.c.id == user_id).execute().first()


@bp.route('/logout', methods=['GET'])
def logout():
    session.clear()
    msg = {"message": "Successfully logged out!"}
    return make_response(jsonify(msg), 200)


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            msg = {"message": "Error: Login is required!"}
            return make_response(jsonify(msg), 400)

        return view(**kwargs)

    return wrapped_view
