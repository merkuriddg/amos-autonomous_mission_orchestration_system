"""AMOS Auth Routes — Login / Logout."""

from flask import Blueprint, request, render_template, redirect, session
from werkzeug.security import check_password_hash

from web.extensions import _audit
from web.state import USERS, DB_AUTH, hmt_engine

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u, p = request.form.get("username", ""), request.form.get("password", "")
        usr = USERS.get(u)
        if usr:
            ok = False
            if DB_AUTH and "password_hash" in usr:
                ok = check_password_hash(usr["password_hash"], p)
            elif "password" in usr:
                ok = (usr["password"] == p)
            if ok:
                session["user"] = u
                _audit(u, "login", "user", u)
                if hmt_engine:
                    hmt_engine.register_operator(u, usr.get("name", u), usr.get("role", "operator"))
                return redirect("/field" if usr["role"] == "field_op" else "/")
        return render_template("login.html", error="Invalid credentials", users=USERS)
    return render_template("login.html", error=None, users=USERS)


@bp.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/login")
