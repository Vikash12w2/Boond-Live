"""Web Push (VAPID) delivery."""
import logging

import requests
from pywebpush import WebPushException, webpush

from boond.util import dumps

log = logging.getLogger(__name__)

TTL_SECONDS = 12 * 3600  # a morning notice is useless by evening


def load_private_key(ssm, name):
    return ssm.get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"]


class Pusher:
    def __init__(self, private_key, contact, send=webpush):
        self.private_key, self.contact, self._send = private_key, contact, send

    def send(self, subscription, payload):
        """'sent', 'gone' (subscription expired: delete it) or 'failed'."""
        try:
            self._send(subscription_info=subscription, data=dumps(payload), vapid_private_key=self.private_key,
                       vapid_claims={"sub": self.contact}, ttl=TTL_SECONDS, timeout=10)
            return "sent"
        except WebPushException as error:
            status = getattr(error.response, "status_code", None)
            if status in (404, 410):
                return "gone"
            log.warning("push failed: status %s", status)
            return "failed"
        except requests.RequestException as error:
            log.warning("push failed: %s", type(error).__name__)
            return "failed"
