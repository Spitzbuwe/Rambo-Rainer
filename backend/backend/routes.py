from flask import Blueprint, jsonify, request
api = Blueprint('api', __name__, url_prefix='/api')

@api.route('/items', methods=['GET'])
def get_items():
    return jsonify({'items': []}), 200
