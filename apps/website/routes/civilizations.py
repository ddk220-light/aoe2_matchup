"""Civilization HTML routes; JSON and HTML share the analysis service."""
from flask import Blueprint, render_template, redirect, abort
from ..services.civilizations import civilization_analysis
from ..services.catalog import grouped_units

def create_blueprint(_get_ref_civs, get_civ_detail, get_civ_overview_data, current_build):
    bp = Blueprint('civilizations', __name__)
    @bp.route("/civilizations")
    def civ_view():
        """Civilization analysis page — shows power units, strengths, and strategic identity."""
        civs = _get_ref_civs()
        return render_template(
            "civ_overview.html",
            civs=civs,
            civ_overview=get_civ_overview_data(),
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
        meta_desc = (f"{civ['name']} in Age of Empires II — strongest fully-upgraded "
                     f"units by role, tiers, and strategy. {first_sentence}").strip()[:250]
        analysis = civilization_analysis(civ["name"], build_number=current_build())
        return render_template("civ_detail.html", civ=civ, civs=_get_ref_civs(),
                               meta_desc=meta_desc, active_nav="civ_select",
                               analysis=analysis, civ_buildings=grouped_units(analysis))


    @bp.route("/civ")
    def civ_redirect():
        """Backward compat redirect."""
        return redirect("/civilizations", code=301)


    @bp.route("/civ/<civ_name>")
    def civ_detail_redirect(civ_name):
        """Backward compat redirect."""
        return redirect(f"/civilizations/{civ_name.lower()}", code=301)



    return bp
