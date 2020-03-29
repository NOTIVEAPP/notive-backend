import time

from flask import (
    Blueprint, g, request, jsonify, make_response, Response
)
from sqlalchemy import Table
from sqlalchemy.exc import SQLAlchemyError
from .util import validate_auth_key, get_json_from_keys
from .db import get_db
from .auth import login_required

bp = Blueprint('list', __name__, url_prefix='/list')


@bp.route('/', methods=['GET', 'POST'], strict_slashes=False)
@login_required
def index():
    if not validate_auth_key(request):
        return Response(status=401)
    else:
        if request.method == 'POST':
            json_data = get_json_from_keys(request, ['name'])
            if json_data is False:
                return make_response(jsonify(
                    {"message": "Request body must be JSON."}), 400)
            elif json_data is None:
                return make_response(jsonify({"message": "Invalid parameters."}), 400)
            else:
                name = json_data['name']

                if not name:
                    msg = {"message": "Error: Provide a name for this list!"}
                    return make_response(jsonify(msg), 400)

                user_id = g.user['id']
                created_at = int(time.time())
                try:
                    db = get_db()
                    con, engine, metadata = db['con'], db['engine'], db['metadata']
                    list_table = Table('List', metadata, autoload=True)

                    res = con.execute(list_table.insert(), name=name, user_id=user_id, created_at=created_at)

                    result = {'list_id': res.lastrowid,
                              'created_at': created_at}
                    msg = {"message": "New list is created successfully!",
                           "data": result}
                    return make_response(jsonify(msg), 200)
                except SQLAlchemyError as e:
                    error = e.__dict__['orig']
                    print("DB ERROR: " + str(error))
                    msg = {"message": "A server error has been occurred. "
                                      "Please try again later and contact us if the error persists. (Error code: "
                                      + str(error.args[0]) + ")",
                           "data": str(error)}
                    return make_response(jsonify(msg), 500)
        else:
            try:
                db = get_db()
                con, engine, metadata = db['con'], db['engine'], db['metadata']
                list_table = Table('List', metadata, autoload=True)
                user = g.user
                lists = list_table.select(list_table.c.user_id == user['id']).execute()
            except SQLAlchemyError as e:
                error = e.__dict__['orig']
                print("DB ERROR: " + str(error))
                msg = {"message": "A server error has been occurred. "
                                  "Please try again later and contact us if the error persists. (Error code: "
                                  + str(error.args[0]) + ")",
                       "data": str(error)}
                return make_response(jsonify(msg), 500)
            result = dict()
            result["lists"] = []
            count = 0
            for l in lists:
                result["lists"].append(dict(l))
                count += 1
            result["number_of_lists"] = count

            msg = {"message": "Success!",
                   "data": result}
            return make_response(jsonify(msg), 200)


def get_list(l_id, check_user=True):
    db = get_db()
    con, engine, metadata = db['con'], db['engine'], db['metadata']
    list_table = Table('List', metadata, autoload=True)
    user_list = list_table.select(list_table.c.id == l_id).execute().first()

    if not user_list:
        status = 404
        return user_list, status
    elif check_user and user_list['user_id'] != g.user['id']:
        status = 403
        return user_list, status
    elif user_list is not None:
        status = 200
        return user_list, status

    return user_list, 500


@bp.route('/<int:l_id>', methods=['GET'], strict_slashes=False)
@login_required
def get_list_with_id(l_id):
    if not validate_auth_key(request):
        return Response(status=401)
    else:
        user_list, status = get_list(l_id)
        if user_list is None or status is 404:
            msg = {"message": "List does not exist!"}
            return make_response(jsonify(msg), status)
        elif status is 403:
            msg = {"message": "List is not yours!"}
            return make_response(jsonify(msg), status)
        else:
            data = {"data": user_list}
            return make_response(jsonify(data), status)


@bp.route('/<int:l_id>', methods=['PUT'], strict_slashes=False)
@login_required
def update(l_id):
    if not validate_auth_key(request):
        return Response(status=401)
    else:
        user_list, status = get_list(l_id)
        if user_list is None or status is 404:
            msg = {"message": "List does not exist!"}
            return make_response(jsonify(msg), status)
        elif status is 403:
            msg = {"message": "List is not yours!"}
            return make_response(jsonify(msg), status)
        else:
            json_data = get_json_from_keys(request, ['name'])
            if json_data is False:
                return make_response(jsonify(
                    {"message": "Request body must be JSON."}), 400)
            elif json_data is None:
                return make_response(jsonify({"message": "Invalid parameters."}), 400)
            else:
                name = json_data['name']

                if name is None:
                    msg = {"message": "Please provide a name!"}
                    return make_response(jsonify(msg), 400)
                try:
                    db = get_db()
                    con, engine, metadata = db['con'], db['engine'], db['metadata']
                    list_table = Table('List', metadata, autoload=True)
                    con.execute(list_table.update().where(list_table.c.id == l_id).values(name=name))

                    msg = {"message": "Success! List name is updated."}
                    return make_response(jsonify(msg), 200)
                except SQLAlchemyError as e:
                    error = e.__dict__['orig']
                    print("DB ERROR: " + str(error))
                    msg = {"message": "A server error has been occurred. "
                                      "Please try again later and contact us if the error persists. (Error code: "
                                      + str(error.args[0]) + ")",
                           "data": str(error)}
                    return make_response(jsonify(msg), 500)


@bp.route('/<int:l_id>', methods=['DELETE'], strict_slashes=False)
@login_required
def delete(l_id):
    if not validate_auth_key(request):
        return Response(status=401)
    else:
        user_list, status = get_list(l_id)
        if user_list is None or status is 404:
            msg = {"message": "List does not exist!"}
            return make_response(jsonify(msg), status)
        elif status is 403:
            msg = {"message": "List is not yours!"}
            return make_response(jsonify(msg), status)
        else:
            try:
                db = get_db()
                con, engine, metadata = db['con'], db['engine'], db['metadata']

                item_table = Table('Item', metadata, autoload=True)
                con.execute(item_table.delete().where(item_table.c.list_id == l_id))

                list_table = Table('List', metadata, autoload=True)
                con.execute(list_table.delete().where(list_table.c.id == l_id))

                msg = {"message": "List is deleted successfully."}
                return make_response(jsonify(msg), 200)
            except SQLAlchemyError as e:
                error = e.__dict__['orig']
                print("DB ERROR: " + str(error))
                msg = {"message": "A server error has been occurred. "
                                  "Please try again later and contact us if the error persists. (Error code: "
                                  + str(error.args[0]) + ")",
                       "data": str(error)}
                return make_response(jsonify(msg), 500)


@bp.route('/<int:l_id>/mute', methods=['PUT'], strict_slashes=False)
@login_required
def mute(l_id):
    if not validate_auth_key(request):
        return Response(status=401)
    else:
        user_list, status = get_list(l_id)
        if user_list is None or status is 404:
            msg = {"message": "List does not exist!"}
            return make_response(jsonify(msg), status)
        elif status is 403:
            msg = {"message": "List is not yours!"}
            return make_response(jsonify(msg), status)
        else:
            try:
                is_muted = bool(user_list['is_muted'])
                db = get_db()
                con, engine, metadata = db['con'], db['engine'], db['metadata']
                list_table = Table('List', metadata, autoload=True)

                if not is_muted:
                    con.execute(list_table.update().where(list_table.c.id == l_id)
                                .values(is_muted=1))
                    msg = {"message": "List is muted."}
                else:
                    con.execute(list_table.update().where(list_table.c.id == list_table).values(is_muted=0))
                    msg = {"message": "List is unmuted."}
                return make_response(jsonify(msg), 200)
            except SQLAlchemyError as e:
                error = e.__dict__['orig']
                print("DB ERROR: " + str(error))
                msg = {"message": "A server error has been occurred. "
                                  "Please try again later and contact us if the error persists. (Error code: "
                                  + str(error.args[0]) + ")",
                       "data": str(error)}
                return make_response(jsonify(msg), 500)


@bp.route('/<int:l_id>/archive', methods=['PUT'], strict_slashes=False)
@login_required
def archive(l_id):
    if not validate_auth_key(request):
        return Response(status=401)
    else:
        user_list, status = get_list(l_id)
        if user_list is None or status is 404:
            msg = {"message": "List does not exist!"}
            return make_response(jsonify(msg), status)
        elif status is 403:
            msg = {"message": "List is not yours!"}
            return make_response(jsonify(msg), status)
        else:
            try:
                is_archived = bool(user_list['is_archived'])
                db = get_db()
                con, engine, metadata = db['con'], db['engine'], db['metadata']
                list_table = Table('List', metadata, autoload=True)

                if not is_archived:
                    con.execute(list_table.update().where(list_table.c.id == l_id)
                                .values(is_archived=1))
                    msg = {"message": "List is archived."}
                else:
                    con.execute(list_table.update().where(list_table.c.id == list_table).values(is_archived=0))
                    msg = {"message": "List is active."}
                return make_response(jsonify(msg), 200)
            except SQLAlchemyError as e:
                error = e.__dict__['orig']
                print("DB ERROR: " + str(error))
                msg = {"message": "A server error has been occurred. "
                                  "Please try again later and contact us if the error persists. (Error code: "
                                  + str(error.args[0]) + ")",
                       "data": str(error)}
                return make_response(jsonify(msg), 500)
