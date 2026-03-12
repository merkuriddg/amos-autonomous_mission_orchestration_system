"""AMOS Page Routes — All HTML page endpoints."""

from flask import Blueprint, render_template
from web.extensions import login_required, ctx

bp = Blueprint("pages", __name__)


@bp.route("/")
@login_required
def index(): return render_template("index.html", **ctx())

@bp.route("/dashboard")
@login_required
def dashboard(): return render_template("dashboard.html", **ctx())

@bp.route("/ew")
@login_required
def ew(): return render_template("ew.html", **ctx())

@bp.route("/sigint")
@login_required
def sigint(): return render_template("sigint.html", **ctx())

@bp.route("/cyber")
@login_required
def cyber(): return render_template("cyber.html", **ctx())

@bp.route("/countermeasures")
@login_required
def countermeasures(): return render_template("countermeasures.html", **ctx())

@bp.route("/hal")
@login_required
def hal(): return render_template("hal.html", **ctx())

@bp.route("/planner")
@login_required
def planner(): return render_template("planner.html", **ctx())

@bp.route("/aar")
@login_required
def aar(): return render_template("aar.html", **ctx())

@bp.route("/awacs")
@login_required
def awacs(): return render_template("awacs.html", **ctx())

@bp.route("/field")
@login_required
def field(): return render_template("field.html", **ctx())

@bp.route("/fusion")
@login_required
def fusion(): return render_template("fusion.html", **ctx())

@bp.route("/cognitive")
@login_required
def cognitive(): return render_template("cognitive.html", **ctx())

@bp.route("/contested")
@login_required
def contested(): return render_template("contested.html", **ctx())

@bp.route("/redforce")
@login_required
def redforce(): return render_template("redforce.html", **ctx())

@bp.route("/readiness")
@login_required
def readiness(): return render_template("readiness.html", **ctx())

@bp.route("/killweb")
@login_required
def killweb_page(): return render_template("killweb.html", **ctx())

@bp.route("/roe")
@login_required
def roe_page(): return render_template("roe.html", **ctx())

@bp.route("/predictions")
@login_required
def predictions_page(): return render_template("predictions.html", **ctx())

@bp.route("/automation")
@login_required
def automation(): return render_template("automation.html", **ctx())

@bp.route("/settings")
@login_required
def settings_page(): return render_template("settings.html", **ctx())

@bp.route("/tactical")
@login_required
def tactical(): return render_template("tactical.html", **ctx())

@bp.route("/docs")
@login_required
def docs_page(): return render_template("docs.html", **ctx())

@bp.route("/integrations")
@login_required
def integrations_page(): return render_template("integrations.html", **ctx())

@bp.route("/video")
@login_required
def video_page(): return render_template("video.html", **ctx())

@bp.route("/analytics")
@login_required
def analytics_page(): return render_template("analytics.html", **ctx())

@bp.route("/missionplan")
@login_required
def missionplan_page(): return render_template("missionplan.html", **ctx())

@bp.route("/syscmd")
@login_required
def syscmd_page(): return render_template("syscmd.html", **ctx())

@bp.route("/training")
@login_required
def training_page(): return render_template("training.html", **ctx())

@bp.route("/commsnet")
@login_required
def commsnet_page(): return render_template("commsnet.html", **ctx())

# Phase 10+ pages
@bp.route("/logistics")
@login_required
def page_logistics(): return render_template("logistics.html", **ctx())

@bp.route("/weather")
@login_required
def page_weather(): return render_template("weather.html", **ctx())

@bp.route("/bda")
@login_required
def page_bda(): return render_template("bda.html", **ctx())

@bp.route("/eob")
@login_required
def page_eob(): return render_template("eob.html", **ctx())

# Phase 16-22 pages
@bp.route("/wargame")
@login_required
def wargame_page(): return render_template("wargame.html", **ctx())

@bp.route("/swarm")
@login_required
def swarm_page(): return render_template("swarm.html", **ctx())

@bp.route("/isr")
@login_required
def isr_page(): return render_template("isr.html", **ctx())

@bp.route("/effects")
@login_required
def effects_page(): return render_template("effects.html", **ctx())

@bp.route("/space")
@login_required
def space_page(): return render_template("space.html", **ctx())

@bp.route("/hmt")
@login_required
def hmt_page(): return render_template("hmt.html", **ctx())

@bp.route("/mesh")
@login_required
def mesh_page(): return render_template("mesh.html", **ctx())

@bp.route("/scripts")
@login_required
def scripts_page(): return render_template("scripts.html", **ctx())

@bp.route("/edition")
@login_required
def edition_page(): return render_template("edition.html", **ctx())

@bp.route("/manual")
@login_required
def manual_page(): return render_template("manual.html", **ctx())

@bp.route("/mobile")
@login_required
def mobile_page(): return render_template("mobile.html", **ctx())

@bp.route("/drone-reference")
@login_required
def drone_reference_page(): return render_template("drone_reference.html", **ctx())
