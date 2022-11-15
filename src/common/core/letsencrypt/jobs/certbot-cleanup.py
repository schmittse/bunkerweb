#!/usr/bin/python3

import sys, os, traceback

sys.path.append("/usr/share/bunkerweb/deps/python")
sys.path.append("/usr/share/bunkerweb/utils")
sys.path.append("/usr/share/bunkerweb/api")

from logger import setup_logger
from API import API

logger = setup_logger("Lets-encrypt", os.getenv("LOG_LEVEL", "INFO"))
status = 0

try:
    # Get env vars
    is_kubernetes_mode = os.getenv("KUBERNETES_MODE") == "yes"
    is_swarm_mode = os.getenv("SWARM_MODE") == "yes"
    is_autoconf_mode = os.getenv("AUTOCONF_MODE") == "yes"
    token = os.getenv("CERTBOT_TOKEN")

    # Cluster case
    if is_kubernetes_mode or is_swarm_mode or is_autoconf_mode:
        for variable, value in os.environ.items():
            if not variable.startswith("CLUSTER_INSTANCE_"):
                continue
            endpoint = value.split(" ")[0]
            host = value.split(" ")[1]
            api = API(endpoint, host=host)
            sent, err, status, resp = api.request(
                "DELETE", "/lets-encrypt/challenge", data={"token": token}
            )
            if not sent:
                status = 1
                logger.error(
                    f"Can't send API request to {api.get_endpoint()}/lets-encrypt/challenge : {err}"
                )
            else:
                if status != 200:
                    status = 1
                    logger.error(
                        f"Error while sending API request to {api.get_endpoint()}/lets-encrypt/challenge : status = {resp['status']}, msg = {resp['msg']}",
                    )
                else:
                    logger.info(
                        f"Successfully sent API request to {api.get_endpoint()}/lets-encrypt/challenge",
                    )

    # Docker or Linux case
    else:
        challenge_path = (
            f"/var/tmp/bunkerweb/lets-encrypt/.well-known/acme-challenge/{token}"
        )
        if os.path.isfile(challenge_path):
            os.remove(challenge_path)
except:
    status = 1
    logger.error("Exception while running certbot-cleanup.py :")
    print(traceback.format_exc())

sys.exit(status)