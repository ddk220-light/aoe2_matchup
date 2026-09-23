"""Civilization HTML routes; JSON and HTML share the analysis service."""
from flask import Blueprint, render_template, redirect, abort, request, jsonify
from ..services.civilizations import civilization_page_analysis, load_civilization_supplement
from ..services.catalog import grouped_units

def create_blueprint(_get_page_civs, get_civ_detail, get_civ_overview_data, current_build):
    bp = Blueprint('civilizations', __name__)
    @bp.route("/civilizations")
    def civ_view():
        """Civilization analysis page — shows power units, strengths, and strategic identity."""
        civs = _get_page_civs()
        overview = get_civ_overview_data()
        return render_template(
            "civ_overview.html",
            civs=civs,
            civ_overview=overview,
            civ_emblems={item['name']: item['emblem_url'] for item in overview if item['emblem_url']},
            civ_page_footer=True,
            active_nav="civ_select",
        )


    @bp.route("/civilizations/<civ_name>")
    def civ_detail(civ_name):
        """Per-civ landing page ("aoe2 <civ>" searches) — SSR identity + power
        units, with the interactive analyzer preselected. Canonical is lowercase."""
        slug = civ_name.lower()
        if civ_name != slug:
            return redirect(f"/civilizations/{slug}", code=301)
        civ = get_civ_detail(slug)
        if civ is None:
            abort(404)
        first_sentence = (civ["description"].split(". ")[0].strip().rstrip(".") + ".") \
            if civ["description"] else ""
        meta_desc = (f"{civ['name']} in Age of Empires II — units, bonuses, and strategy. "
                     f"{first_sentence}").strip()[:250]
        analysis = civilization_page_analysis(civ["name"], build_number=current_build())
        supplement = load_civilization_supplement()['civilizations']
        return render_template("civ_detail.html", civ=civ, civs=_get_page_civs(),
                               meta_desc=meta_desc, active_nav="civ_select",
                               analysis=analysis, civ_buildings=grouped_units(analysis),
                               civ_emblems={name: item['emblem_url'] for name, item in supplement.items()
                                            if item['emblem_url']},
                               civ_page_footer=True)


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


    @bp.route("/civ")
    def civ_redirect():
        """Backward compat redirect."""
        return redirect("/civilizations", code=301)


    @bp.route("/civ/<civ_name>")
    def civ_detail_redirect(civ_name):
        """Backward compat redirect."""
        return redirect(f"/civilizations/{civ_name.lower()}", code=301)



    return bp
