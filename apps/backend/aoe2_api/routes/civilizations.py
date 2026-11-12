"""Civilization JSON route; the published civilization pages share its analysis service."""
from flask import Blueprint, request, jsonify
from ..services.civilizations import civilization_page_analysis

def create_blueprint(_get_page_civs, current_build):
    bp = Blueprint('civilizations', __name__)

    @bp.route('/api/civilizations/<civ_name>')
    def api_civilization(civ_name):
        if civ_name not in _get_page_civs():
            return jsonify(error=f"Unknown civilization: {civ_name!r}"), 400
        age = request.args.get('age', 'imperial').lower()
        if age != 'imperial':
            return jsonify(error=f"Invalid age: {age!r}. Must be 'imperial'."), 400
        try:
            return jsonify(civilization_page_analysis(civ_name, age, build_number=current_build()))
        except FileNotFoundError as exc:
            return jsonify(error=str(exc)), 500
        except LookupError as exc:
            return jsonify(error=str(exc)), 404

    return bp
