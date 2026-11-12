"""Public battle endpoints; dependencies resolve from application configuration."""
import sqlite3
from flask import Blueprint, current_app, jsonify, request
from aoe2x.js_simulation.scenario_config import build_arena_preview_payload
from ..services.battles import build_battle_config
from ..services.army_context import ArmyContext, ContextUnavailable

def create_blueprint(connect, valid_civs):
    bp = Blueprint('battles', __name__)

    def context_store():
        return ArmyContext(current_app.config.get('ARMY_CONTEXT_DB'),
                           current_app.config.get('ARMY_ECONOMICS_MODE', 'off'))

    def resolve(document, *, require_context=False):
        store = None
        if require_context or current_app.config.get('ARMY_ECONOMICS_MODE', 'off') != 'off':
            try:
                store = context_store()
            except ContextUnavailable:
                if require_context:
                    raise
        try:
            config = build_battle_config(document, connect=connect, valid_civs=valid_civs,
                                        cost_resolver=store.apply_cost if store else None)
        except ContextUnavailable:
            if require_context:
                raise
            # Context failure must not break combat or leave a partially
            # corrected pair. Re-resolve both sides using the existing policy.
            store = None
            config = build_battle_config(document, connect=connect, valid_civs=valid_civs)
        config['armyContextVersion'] = store.metadata['contextVersion'] if store else None
        return config, store

    @bp.get('/api/v3/arena-preview')
    def arena_preview():
        return jsonify(build_arena_preview_payload())

    @bp.post('/api/v3/battle-config')
    def battle_config():
        try:
            return jsonify(resolve(request.get_json(silent=True))[0])
        except (LookupError, RuntimeError, sqlite3.DatabaseError) as exc:
            current_app.logger.error('V3 mechanics unavailable: %s', exc)
            return jsonify(error='V3 mechanics unavailable', detail=str(exc)), 503
        except ValueError as exc:
            return jsonify(error=str(exc)), 400

    @bp.post('/api/v3/army-context')
    def army_context():
        if current_app.config.get('ARMY_ECONOMICS_MODE', 'off') == 'off':
            return jsonify(error='Army economics is disabled'), 404
        try:
            document = request.get_json(silent=True)
            config, store = resolve(document, require_context=True)
            version = document.get('contextVersion')
            if version is not None and version != store.metadata['contextVersion']:
                return jsonify(error='Army context changed; reload the comparison'), 409
            return jsonify(store.response(config, document.get('convertedVillagers')))
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        except (LookupError, RuntimeError, sqlite3.DatabaseError) as exc:
            current_app.logger.warning('Army context unavailable: %s', exc)
            return jsonify(error='Army economics is awaiting compatible, validated data'), 503
    return bp
