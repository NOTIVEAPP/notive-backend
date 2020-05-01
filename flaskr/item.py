import time
from flask import (
    Blueprint, g, request, jsonify, make_response, Response
)
from sqlalchemy import Table
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import and_
from .util import validate_auth_key, get_json_from_keys
from .db import get_db
from .auth import login_required
from .list import get_list

bp = Blueprint('item', __name__, url_prefix='/item')


@bp.route('/', methods=['GET'], strict_slashes=False)
@login_required
def get_all():
    user = g.user
    db = get_db()
    con, engine, metadata = db['con'], db['engine'], db['metadata']

    result = dict()
    result_dict = {}

    query_res = engine.execute("""
    SELECT
    item.*
    FROM Item as item
    INNER JOIN List as list
    ON item.list_id = list.id WHERE list.user_id = """ + str(user['id']) + """;
    """)

    for qr in query_res:
        if qr.list_id in result_dict:
            result_dict[qr.list_id].append(dict(qr))
        else:
            result_dict[qr.list_id] = [dict(qr)]
    result["items"] = result_dict

    msg = {"message": "Success!",
           "data": result_dict}
    return make_response(jsonify(msg), 200)


@bp.route('/<int:list_id>', methods=['GET'], strict_slashes=False)
@login_required
def get_list_items(list_id):
    user_list, status = get_list(list_id)
    if user_list is None or status is 404:
        msg = {"message": "List does not exist!"}
        return make_response(jsonify(msg), status)
    elif status is 403:
        msg = {"message": "List is not yours!"}
        return make_response(jsonify(msg), status)
    else:
        db = get_db()
        con, engine, metadata = db['con'], db['engine'], db['metadata']
        item_table = Table('Item', metadata, autoload=True)
        result = dict()
        result["items"] = []
        count = 0
        items = item_table.select(item_table.c.list_id == list_id).execute()

        for i in items:
            result["items"].append(dict(i))
            count += 1

        result["number_of_items"] = count
        msg = {"message": "Success!",
               "data": result}
        return make_response(jsonify(msg), 200)


@bp.route('/<int:list_id>/<int:item_id>', methods=['GET'], strict_slashes=False)
@login_required
def get_item_only(list_id, item_id):
    user_item, status = get_item(list_id, item_id)
    if user_item is None or status is 404:
        msg = {"message": "Item does not exist!"}
        return make_response(jsonify(msg), status)
    elif status is 403:
        msg = {"message": "Item is not yours!"}
        return make_response(jsonify(msg), status)
    else:
        db = get_db()
        con, engine, metadata = db['con'], db['engine'], db['metadata']
        item_table = Table('Item', metadata, autoload=True)
        item = item_table.select(item_table.c.id == item_id).execute().first()
        result = {"item": {"id": item['id'],
                           "name": item['name'],
                           "list_id": list_id,
                           "is_done": item['is_done'],
                           "finished_att": item['finished_at'],
                           "created_at": item['created_at'],
                           "distance": item['distance'],
                           "frequency": item['frequency']}
                  }
        data = {'data': result}
        return make_response(jsonify(data), status)


@bp.route('/', methods=['POST'], strict_slashes=False)
@login_required
def create():
    if not validate_auth_key(request):
        return Response(status=401)
    else:
        json_data = get_json_from_keys(request, ['name', 'list_id'])
        if json_data is False:
            return make_response(jsonify(
                {"message": "Request body must be JSON."}), 400)
        elif json_data is None:
            return make_response(jsonify({"message": "Invalid parameters."}), 400)
        else:
            name = json_data['name']
            list_id = json_data['list_id']
            distance = 5000  # meters default
            frequency = 60  # minutes default
            created_at = int(time.time())

            if name is None:
                msg = {"message": "Please provide a name for the item."}
                return make_response(jsonify(msg), 400)

            user_list, status = get_list(list_id)
            if user_list is None or status is 404:
                msg = {"message": "List does not exist!"}
                return make_response(jsonify(msg), status)
            elif status is 403:
                msg = {"message": "List is not yours!"}
                return make_response(jsonify(msg), status)
            else:
                list_name = user_list['name']
                db = get_db()
                con, engine, metadata = db['con'], db['engine'], db['metadata']
                item_table = Table('Item', metadata, autoload=True)
                try:
                    res = con.execute(item_table.insert(), name=name, list_id=list_id, created_at=created_at,
                                      distance=distance, frequency=frequency)
                    data = {'item_id': res.lastrowid,
                            'created_at': created_at}
                    msg = {"message": "An item has been successfully added to list named '" + list_name + "'.",
                           "data": data}
                except SQLAlchemyError as e:
                    error = e.__dict__['orig']
                    print("DB ERROR: " + str(error))
                    msg = {"message": "A server error has been occurred. "
                                      "Please try again later and contact us if the error persists. (Error code: "
                                      + str(error.args[0]) + ")",
                           "data": str(error)}
                    return make_response(jsonify(msg), 500)
                return make_response(jsonify(msg), 200)


def get_item(list_id, item_id, check_user=True):
    db = get_db()
    con, engine, metadata = db['con'], db['engine'], db['metadata']
    item_table = Table('Item', metadata, autoload=True)
    list_table = Table('List', metadata, autoload=True)
    joined_table = item_table.join(list_table, list_table.c.id == item_table.c.list_id)
    item = joined_table.select(and_(item_table.c.id == item_id, list_table.c.id == list_id)).with_only_columns(
            [item_table.c.id, item_table.c.name, item_table.c.list_id, item_table.c.is_done,
             item_table.c.created_at, item_table.c.distance, item_table.c.frequency, item_table.c.finished_at,
             list_table.c.user_id]).execute().first()

    if not item:
        status = 404
        return item, status
    elif check_user and item['user_id'] != g.user['id']:
        status = 403
        return item, status
    elif item is not None:
        status = 200
        return item, status

    return item, 500


@bp.route('/<int:list_id>/<int:item_id>', methods=['PUT'], strict_slashes=False)
@login_required
def update(list_id, item_id):
    if not validate_auth_key(request):
        return Response(status=401)
    else:
        json_data = get_json_from_keys(request, ['name'])
        if json_data is None:
            json_data = get_json_from_keys(request, ['distance'])
        if json_data is None:
            json_data = get_json_from_keys(request, ['frequency'])

        if json_data is False:
            return make_response(jsonify(
                {"message": "Request body must be JSON."}), 400)
        elif json_data is None:
            return make_response(jsonify({"message": "Invalid parameters."}), 400)
        else:
            name = None
            distance = None
            frequency = None
            if 'name' in json_data:
                name = json_data['name']
            if 'distance' in json_data:
                distance = json_data['distance']
            if 'frequency' in json_data:
                frequency = json_data['frequency']

            if name is None and distance is None and frequency is None:
                msg = {"message": "Please provide one of the following: name, distance, frequency!"}
                return make_response(jsonify(msg), 400)

            user_item, status = get_item(list_id, item_id)
            if user_item is None or status is 404:
                msg = {"message": "Item does not exist!"}
                return make_response(jsonify(msg), status)
            elif status is 403:
                msg = {"message": "Item is not yours!"}
                return make_response(jsonify(msg), status)
            else:
                try:
                    db = get_db()
                    con, engine, metadata = db['con'], db['engine'], db['metadata']
                    item_table = Table('Item', metadata, autoload=True)

                    if name is not None:
                        con.execute(item_table.update().where(item_table.c.id == item_id).values(name=name))
                    if distance is not None:
                        con.execute(item_table.update().where(item_table.c.id == item_id).values(distance=distance))
                    if frequency is not None:
                        con.execute(item_table.update().where(item_table.c.id == item_id).values(frequency=frequency))
                except SQLAlchemyError as e:
                    error = e.__dict__['orig']
                    print("DB ERROR: " + str(error))
                    msg = {"message": "A server error has been occurred. "
                                      "Please try again later and contact us if the error persists. (Error code: "
                                      + str(error.args[0]) + ")",
                           "data": str(error)}
                    return make_response(jsonify(msg), 500)
                msg = {"message": "Success! Item is updated."}
                return make_response(jsonify(msg), 200)


@bp.route('/<int:list_id>/<int:item_id>/check', methods=['PUT'], strict_slashes=False)
@login_required
def check(list_id, item_id):
    if not validate_auth_key(request):
        return Response(status=401)
    else:
        user_item, status = get_item(list_id, item_id)
        if user_item is None or status is 404:
            msg = {"message": "Item does not exist!"}
            return make_response(jsonify(msg), status)
        elif status is 403:
            msg = {"message": "Item is not yours!"}
            return make_response(jsonify(msg), status)
        else:
            try:
                is_done = bool(user_item['is_done'])
                db = get_db()
                con, engine, metadata = db['con'], db['engine'], db['metadata']
                item_table = Table('Item', metadata, autoload=True)

                if not is_done:
                    con.execute(item_table.update().where(item_table.c.id == item_id)
                                .values(is_done=1, finished_at=int(time.time())))
                    msg = {"message": "Item is marked as complete!"}
                else:
                    con.execute(item_table.update().where(item_table.c.id == item_id).values(is_done=0,
                                                                                             finished_at=None))
                    msg = {"message": "Item is marked as not completed!"}
                return make_response(jsonify(msg), 200)
            except SQLAlchemyError as e:
                error = e.__dict__['orig']
                print("DB ERROR: " + str(error))
                msg = {"message": "A server error has been occurred. "
                                  "Please try again later and contact us if the error persists. (Error code: "
                                  + str(error.args[0]) + ")",
                       "data": str(error)}
                return make_response(jsonify(msg), 500)


@bp.route('/<int:list_id>/<int:item_id>', methods=['DELETE'], strict_slashes=False)
@login_required
def delete(list_id, item_id):
    if not validate_auth_key(request):
        return Response(status=401)
    else:
        user_item, status = get_item(list_id, item_id)
        if user_item is None or status is 404:
            msg = {"message": "Item does not exist!"}
            return make_response(jsonify(msg), status)
        elif status is 403:
            msg = {"message": "Item is not yours!"}
            return make_response(jsonify(msg), status)
        else:
            try:
                db = get_db()
                con, engine, metadata = db['con'], db['engine'], db['metadata']
                item_table = Table('Item', metadata, autoload=True)
                con.execute(item_table.delete().where(item_table.c.id == item_id))

                msg = {"message": "Item is deleted successfully!"}
                return make_response(jsonify(msg), 200)
            except SQLAlchemyError as e:
                error = e.__dict__['orig']
                print("DB ERROR: " + str(error))
                msg = {"message": "A server error has been occurred. "
                                  "Please try again later and contact us if the error persists. (Error code: "
                                  + str(error.args[0]) + ")",
                       "data": str(error)}
                return make_response(jsonify(msg), 500)
