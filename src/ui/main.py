#!/usr/bin/env python3
from contextlib import suppress
from os import _exit, getenv, sep
from os.path import join
from secrets import token_urlsafe
from sys import path as sys_path
from pathlib import Path

for deps_path in [join(sep, "usr", "share", "bunkerweb", *paths) for paths in (("deps", "python"), ("utils",), ("api",), ("db",))]:
    if deps_path not in sys_path:
        sys_path.append(deps_path)

from datetime import datetime, timedelta, timezone
from flask import Flask, Response, flash, jsonify, make_response, redirect, render_template, request, session, url_for
from flask_login import current_user, LoginManager, login_required, logout_user
from flask_principal import ActionNeed, identity_loaded, Permission, Principal, RoleNeed, TypeNeed, UserNeed
from flask_wtf.csrf import CSRFProtect, CSRFError
from json import JSONDecodeError, dumps, loads as json_loads
from signal import SIGINT, signal, SIGTERM
from subprocess import PIPE, Popen, call
from time import time

from logger import setup_logger  # type: ignore

from src.instance import InstancesUtils
from src.custom_config import CustomConfig
from src.config import Config
from src.reverse_proxied import ReverseProxied
from src.totp import Totp
from src.ui_data import UIData

from pages.bans import bans
from pages.cache import cache
from pages.configs import configs
from pages.global_config import global_config
from pages.home import home
from pages.instances import instances
from pages.jobs import jobs
from pages.modes import modes
from pages.login import login
from pages.logout import logout, logout_page
from pages.logs import logs
from pages.plugins import plugins
from pages.profile import profile
from pages.reports import reports
from pages.services import services
from pages.setup import setup
from pages.totp import totp

from models import AnonymousUser
from ui_database import UIDatabase
from utils import check_settings

TMP_DIR = Path(sep, "var", "tmp", "bunkerweb")
LIB_DIR = Path(sep, "var", "lib", "bunkerweb")


def stop_gunicorn():
    p = Popen(["pgrep", "-f", "gunicorn"], stdout=PIPE)
    out, _ = p.communicate()
    pid = out.strip().decode().split("\n")[0]
    call(["kill", "-SIGTERM", pid])


def stop(status, _stop=True):
    Path(sep, "var", "run", "bunkerweb", "ui.pid").unlink(missing_ok=True)
    TMP_DIR.joinpath("ui.healthy").unlink(missing_ok=True)
    if _stop is True:
        stop_gunicorn()
    _exit(status)


def handle_stop(signum, frame):
    app.logger.info("Caught stop operation")
    app.logger.info("Stopping web ui ...")
    stop(0, False)


signal(SIGINT, handle_stop)
signal(SIGTERM, handle_stop)

sbin_nginx_path = Path(sep, "usr", "sbin", "nginx")

# Flask app
app = Flask(__name__, static_url_path="/", static_folder="static", template_folder="templates")

with app.app_context():
    PROXY_NUMBERS = int(getenv("PROXY_NUMBERS", "1"))
    app.wsgi_app = ReverseProxied(app.wsgi_app, x_for=PROXY_NUMBERS, x_proto=PROXY_NUMBERS, x_host=PROXY_NUMBERS, x_prefix=PROXY_NUMBERS)
    app.logger = setup_logger("UI", getenv("CUSTOM_LOG_LEVEL", getenv("LOG_LEVEL", "INFO")))

    FLASK_SECRET = getenv("FLASK_SECRET")
    if not FLASK_SECRET:
        if not TMP_DIR.joinpath(".flask_secret").is_file():
            app.logger.error("The FLASK_SECRET environment variable is missing and the .flask_secret file is missing, exiting ...")
            stop(1)
        FLASK_SECRET = TMP_DIR.joinpath(".flask_secret").read_text(encoding="utf-8").strip()

    TOTP_SECRETS = getenv("TOTP_SECRETS", "")
    if TOTP_SECRETS:
        try:
            TOTP_SECRETS = json_loads(TOTP_SECRETS)
        except JSONDecodeError:
            x = 1
            tmp_secrets = {}
            for secret in TOTP_SECRETS.strip().split(" "):
                if secret:
                    tmp_secrets[x] = secret
                    x += 1
            TOTP_SECRETS = tmp_secrets.copy()
            del tmp_secrets

    if not TOTP_SECRETS:
        if not LIB_DIR.joinpath(".totp_secrets.json").is_file():
            app.logger.error("The TOTP_SECRETS environment variable is missing and the .totp_secrets.json file is missing, exiting ...")
            stop(1)
        TOTP_SECRETS = json_loads(LIB_DIR.joinpath(".totp_secrets.json").read_text(encoding="utf-8"))

    app.config["SECRET_KEY"] = FLASK_SECRET

    app.config["SESSION_COOKIE_NAME"] = "__Host-bw_ui_session"
    app.config["SESSION_COOKIE_PATH"] = "/"
    app.config["SESSION_COOKIE_SECURE"] = True  # Required for __Host- prefix
    app.config["SESSION_COOKIE_HTTPONLY"] = True  # Recommended for security
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    app.config["WTF_CSRF_SSL_STRICT"] = False
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 86400
    app.config["SCRIPT_NONCE"] = ""

    principal = Principal()
    principal.init_app(app)

    admin_permission = Permission(TypeNeed("super_admin"))
    manage_permission = Permission(TypeNeed("super_admin"), ActionNeed("manage"))
    edit_permission = Permission(TypeNeed("super_admin"), ActionNeed("manage"), ActionNeed("write"))
    read_permission = Permission(TypeNeed("super_admin"), ActionNeed("manage"), ActionNeed("write"), ActionNeed("read"))

    login_manager = LoginManager()
    login_manager.session_protection = "strong"
    login_manager.init_app(app)
    login_manager.login_view = "login.login_page"
    login_manager.anonymous_user = AnonymousUser

    app.db = UIDatabase(app.logger, log=False)

    # Declare functions for jinja2
    app.jinja_env.globals.update(
        check_settings=check_settings,
        url_for=lambda *args, **kwargs: url_for(
            f"{args[0]}.{args[0]}_page" if args[0] not in ("index", "loading", "check", "check_reloading") and "_page" not in args[0] else args[0], **kwargs
        ),
    )

    # CSRF protection
    csrf = CSRFProtect()
    csrf.init_app(app)

    app.bw_instances_utils = InstancesUtils(app.db)
    app.bw_config = Config(app.db)
    app.bw_custom_configs = CustomConfig()
    app.data = UIData(TMP_DIR.joinpath("ui_data.json"))
    app.totp = Totp(app, TOTP_SECRETS)


@app.context_processor
def inject_variables():
    app.data.load_from_file()
    metadata = app.db.get_metadata()

    changes_ongoing = any(
        v
        for k, v in app.db.get_metadata().items()
        if k in ("custom_configs_changed", "external_plugins_changed", "pro_plugins_changed", "plugins_config_changed", "instances_changed")
    )

    if not changes_ongoing and app.data.get("PRO_LOADING"):
        app.data["PRO_LOADING"] = False

    if not changes_ongoing and metadata["failover"]:
        flash(
            "The last changes could not be applied because it creates a configuration error on NGINX, please check the logs for more information. The configured fell back to the last working one.",
            "error",
        )
    elif not changes_ongoing and not metadata["failover"] and app.data.get("CONFIG_CHANGED", False):
        flash("The last changes have been applied successfully.", "success")
        app.data["CONFIG_CHANGED"] = False

    # Keep only plugins with a page to display on sidebar
    plugins_page = [{"id": plugin.get("id"), "name": plugin.get("name")} for plugin in app.bw_config.get_plugins() if plugin.get("page", False)]

    # check that is value is in tuple
    return dict(
        data_server_global=dumps({"username": current_user.get_id() if current_user.is_authenticated else "", "plugins_page": plugins_page}),
        script_nonce=app.config["SCRIPT_NONCE"],
        is_pro_version=metadata["is_pro"],
        pro_status=metadata["pro_status"],
        pro_services=metadata["pro_services"],
        pro_expire=metadata["pro_expire"].strftime("%Y-%m-%d") if metadata["pro_expire"] else "Unknown",
        pro_overlapped=metadata["pro_overlapped"],
        plugins=app.bw_config.get_plugins(),
        pro_loading=app.data.get("PRO_LOADING", False),
        bw_version=metadata["version"],
        is_readonly=app.data.get("READONLY_MODE", False),
        username=current_user.get_id() if current_user.is_authenticated else "",
    )


@app.after_request
def set_security_headers(response):
    """Set the security headers."""
    # * Content-Security-Policy header to prevent XSS attacks
    response.headers["Content-Security-Policy"] = (
        "object-src 'none';"
        + " frame-ancestors 'self';"
        + " default-src 'self' https://www.bunkerweb.io https://assets.bunkerity.com https://bunkerity.us1.list-manage.com;"
        + f" script-src 'self' 'nonce-{app.config['SCRIPT_NONCE']}';"
        + " style-src 'self' 'unsafe-inline';"
        + " img-src 'self' data: https://assets.bunkerity.com;"
        + " font-src 'self' data:;"
        + " base-uri 'self';"
        + " block-all-mixed-content;"
        + (" connect-src *;" if request.path.startswith(("/check", "/setup")) else "")
    )

    if request.headers.get("X-Forwarded-Proto") == "https":
        if not request.path.startswith("/setup/loading"):
            response.headers["Content-Security-Policy"] += " upgrade-insecure-requests;"

        # * Strict-Transport-Security header to force HTTPS if accessed via a reverse proxy
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"

    # * X-Frames-Options header to prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"

    # * X-Content-Type-Options header to prevent MIME sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"

    # * Referrer-Policy header to prevent leaking of sensitive data
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    return response


@login_manager.user_loader
def load_user(username):
    ui_user = app.db.get_ui_user(username=username)
    if not ui_user:
        app.logger.warning(f"Couldn't get the user {username} from the database.")
        return None

    ui_user.list_roles = [role.role_name for role in ui_user.roles]
    for role in ui_user.list_roles:
        ui_user.list_permissions.extend(app.db.get_ui_role_permissions(role))

    if ui_user.totp_secret:
        ui_user.list_recovery_codes = [recovery_code.code for recovery_code in ui_user.recovery_codes]

    return ui_user


@identity_loaded.connect_via(app)
def on_identity_loaded(sender, identity):
    # Set the identity user object
    identity.user = current_user

    # Add the UserNeed to the identity
    identity.provides.add(UserNeed(current_user.get_id()))

    for role in current_user.list_roles:
        identity.provides.add(RoleNeed(role))

    for action in current_user.list_permissions:
        identity.provides.add(ActionNeed(action))

    if current_user.admin:
        identity.provides.add(TypeNeed("super_admin"))


@app.errorhandler(CSRFError)
def handle_csrf_error(_):
    """
    It takes a CSRFError exception as an argument, and returns a Flask response

    :param e: The exception object
    :return: A template with the error message and a 401 status code.
    """
    app.logger.error(f"CSRF token is missing or invalid for {request.path} by {current_user.get_id()}")
    session.clear()
    logout_user()
    flash("Wrong CSRF token !", "error")
    if not current_user:
        return render_template("setup.html"), 403
    return render_template("login.html", is_totp=bool(current_user.totp_secret)), 403


@app.before_request
def before_request():
    app.data.load_from_file()
    if app.data.get("SERVER_STOPPING", False):
        response = make_response(jsonify({"message": "Server is shutting down, try again later."}), 503)
        response.headers["Retry-After"] = 30  # Clients should retry after 30 seconds # type: ignore
        return response

    app.config["SCRIPT_NONCE"] = token_urlsafe(32)

    if not request.path.startswith(("/css", "/images", "/js", "/json", "/webfonts")):
        if (
            app.db.database_uri
            and app.db.readonly
            and (
                datetime.now(timezone.utc) - datetime.fromisoformat(app.data.get("LAST_DATABASE_RETRY", "1970-01-01T00:00:00")).replace(tzinfo=timezone.utc)
                > timedelta(minutes=1)
            )
        ):
            try:
                app.db.retry_connection(pool_timeout=1)
                app.db.retry_connection(log=False)
                app.data["READONLY_MODE"] = False
                app.logger.info("The database is no longer read-only, defaulting to read-write mode")
            except BaseException:
                try:
                    app.db.retry_connection(readonly=True, pool_timeout=1)
                    app.db.retry_connection(readonly=True, log=False)
                except BaseException:
                    if app.db.database_uri_readonly:
                        with suppress(BaseException):
                            app.db.retry_connection(fallback=True, pool_timeout=1)
                            app.db.retry_connection(fallback=True, log=False)
                app.data["READONLY_MODE"] = True
            app.data["LAST_DATABASE_RETRY"] = (
                app.db.last_connection_retry.isoformat() if app.db.last_connection_retry else datetime.now(timezone.utc).isoformat()
            )
        elif not app.data.get("READONLY_MODE", False) and request.method == "POST" and not ("/totp" in request.path or "/login" in request.path):
            try:
                app.db.test_write()
                app.data["READONLY_MODE"] = False
            except BaseException:
                app.data["READONLY_MODE"] = True
                app.data["LAST_DATABASE_RETRY"] = (
                    app.db.last_connection_retry.isoformat() if app.db.last_connection_retry else datetime.now(timezone.utc).isoformat()
                )
        else:
            try:
                app.db.test_read()
            except BaseException:
                app.data["LAST_DATABASE_RETRY"] = (
                    app.db.last_connection_retry.isoformat() if app.db.last_connection_retry else datetime.now(timezone.utc).isoformat()
                )

        app.db.readonly = app.data.get("READONLY_MODE", False)

        if app.db.readonly:
            flash("Database connection is in read-only mode : no modification possible.", "error")

        if current_user.is_authenticated:
            passed = True

            # Case not login page, keep on 2FA before any other access
            if not session.get("totp_validated", False) and bool(current_user.totp_secret) and "/totp" not in request.path:
                if not request.path.endswith("/login"):
                    return redirect(url_for("totp.totp_page", next=request.form.get("next")))
                passed = False
            elif current_user.last_login_ip != request.remote_addr:
                app.logger.warning(f"User {current_user.get_id()} tried to access his session with a different IP address.")
                passed = False
            elif session.get("user_agent") != request.headers.get("User-Agent"):
                app.logger.warning(f"User {current_user.get_id()} tried to access his session with a different User-Agent.")
                passed = False

            if not passed:
                return logout_page()


### * MISC ROUTES * ###


@app.route("/", strict_slashes=False)
def index():
    if app.db.get_ui_user():
        if current_user.is_authenticated:  # type: ignore
            return redirect(url_for("home.home_page"))
        return redirect(url_for("login.login_page"), 301)
    return redirect(url_for("setup.setup_page"), 301)


@app.route("/loading")
@login_required
def loading():
    return render_template("loading.html", message=request.values.get("message", "Loading"), next=request.values.get("next", None) or url_for("home.home_page"))


@app.route("/check", methods=["GET"])
def check():
    # deepcode ignore TooPermissiveCors: We need to allow all origins for the wizard
    return Response(status=200, headers={"Access-Control-Allow-Origin": "*"}, response=dumps({"message": "ok"}), content_type="application/json")


@app.route("/check_reloading")
@login_required
def check_reloading():
    app.data.load_from_file()

    if not app.data.get("RELOADING", False) or app.data.get("LAST_RELOAD", 0) + 60 < time():
        if app.data.get("RELOADING", False):
            app.logger.warning("Reloading took too long, forcing the state to be reloaded")
            flash("Forced the status to be reloaded", "error")
            app.data["RELOADING"] = False

        for f in app.data.get("TO_FLASH", []):
            if f["type"] == "error":
                flash(f["content"], "error")
            else:
                flash(f["content"])

        app.data["TO_FLASH"] = []

    return jsonify({"reloading": app.data.get("RELOADING", False)})


BLUEPRINTS = (bans, cache, configs, global_config, home, instances, jobs, modes, login, logout, logs, plugins, profile, reports, services, setup, totp)
for blueprint in BLUEPRINTS:
    app.register_blueprint(blueprint)
