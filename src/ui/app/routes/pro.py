from datetime import datetime
from threading import Thread
from time import time
from typing import Dict
from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import login_required

from app.dependencies import BW_CONFIG, DATA, DB
from app.routes.utils import get_remain, handle_error, manage_bunkerweb, verify_data_in_form, wait_applying
from app.utils import LOGGER, flash


pro = Blueprint("pro", __name__)


@pro.route("/pro", methods=["GET"])
@login_required
def pro_page():
    online_services = 0
    draft_services = 0
    for service in DB.get_services(with_drafts=True):
        if service["is_draft"]:
            draft_services += 1
            continue
        online_services += 1

    metadata = DB.get_metadata()
    current_day = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    pro_expires_in = "Unknown"
    if metadata["pro_expire"]:
        exp = (metadata["pro_expire"].astimezone() - current_day).total_seconds()
        remain = ("Unknown", "Unknown") if exp <= 0 else get_remain(exp)
        pro_expires_in = remain[0]

    return render_template(
        "pro.html",
        online_services=online_services,
        draft_services=draft_services,
        pro_expires_in=pro_expires_in,
    )


@pro.route("/pro/key", methods=["POST"])
@login_required
def pro_key():
    if DB.readonly:
        return handle_error("Database is in read-only mode", "pro")

    verify_data_in_form(
        data={"PRO_LICENSE_KEY": None},
        err_message="Missing license key parameter on /pro/key.",
        redirect_url="pro",
        next=True,
    )
    license_key = request.form["PRO_LICENSE_KEY"]
    if not license_key:
        return handle_error("Invalid license key", "pro")

    global_config = DB.get_config(global_only=True, methods=True, filtered_settings=("PRO_LICENSE_KEY"))
    variables = BW_CONFIG.check_variables({"PRO_LICENSE_KEY": license_key}, global_config, global_config=True)

    if not variables:
        flash("The license key is the same as the current one.", "warning")
        return redirect(url_for("pro.pro_page"))

    DATA.load_from_file()

    def update_license_key(license_key: str):
        wait_applying()
        manage_bunkerweb("global_config", {"PRO_LICENSE_KEY": license_key}, threaded=True)

    DATA.update(
        {
            "RELOADING": True,
            "LAST_RELOAD": time(),
            "CONFIG_CHANGED": True,
            "PRO_LOADING": True,
        }
    )
    flash("Checking license key.")
    Thread(target=update_license_key, args=(license_key,)).start()
    return redirect(
        url_for(
            "loading",
            next=url_for("pro.pro_page"),
            message="Updating license key",
        )
    )
