"""Public battle endpoints; dependencies resolve from application configuration."""
import sqlite3
from flask import Blueprint, current_app, jsonify, request
from aoe2x.js_simulation.scenario_config import build_arena_preview_payload
from ..services.battles import build_battle_config

def create_blueprint(connect, valid_civs):
    bp = Blueprint('battles', __name__)

    @bp.get('/api/v3/arena-preview')
    def arena_preview():
        return jsonify(build_arena_preview_payload())

    @bp.post('/api/v3/battle-config')
    def battle_config():
        try:
            return jsonify(build_battle_config(request.get_json(silent=True), connect=connect, valid_civs=valid_civs))
        except (LookupError, RuntimeError, sqlite3.DatabaseError) as exc:
            current_app.logger.error('V3 mechanics unavailable: %s', exc)
            return jsonify(error='V3 mechanics unavailable', detail=str(exc)), 503
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
    return bp
