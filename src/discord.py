from __future__ import annotations
import time
from typing import Optional
try:
    from pypresence import Presence
except Exception:
    Presence = None
DISCORD_CLIENT_ID = 'YOURCLIENTIDGOESINHERE' # what you think i wanna share my client id with you.

class _DiscordRPC:

    def __init__(self) -> None:
        self.client_id: Optional[str] = None
        self.rpc = None
        self.enabled: bool = False
        self._last_details: Optional[str] = None
        self._last_state: Optional[str] = None
        self._last_attempt: float = 0.0

    def init(self, client_id: Optional[str]=None) -> None:
        if self.enabled:
            return
        if Presence is None:
            return
        cid = client_id or DISCORD_CLIENT_ID
        self.client_id = cid
        try:
            self.rpc = Presence(cid)
            self.rpc.connect()
            self.enabled = True
            self.update(details='In the Menus', state=None)
        except Exception:
            self.rpc = None
            self.enabled = False
            self._last_attempt = time.time()

    def _maybe_reconnect(self) -> None:
        if self.enabled or Presence is None or (not self.client_id):
            return
        now = time.time()
        if now - self._last_attempt < 30.0:
            return
        self._last_attempt = now
        try:
            self.rpc = Presence(self.client_id)
            self.rpc.connect()
            self.enabled = True
        except Exception:
            self.rpc = None
            self.enabled = False

    def update(self, *, details: str, state: Optional[str]) -> None:
        if Presence is None:
            return
        if not self.enabled:
            self._maybe_reconnect()
            if not self.enabled:
                return
        if details == self._last_details and state == self._last_state:
            return
        payload = {'details': details, 'large_image': 'dg'}
        if state:
            payload['state'] = state
        try:
            self.rpc.update(**payload)
            self._last_details = details
            self._last_state = state
        except Exception:
            self.enabled = False
            self.rpc = None
            self._maybe_reconnect()

    def update_for_menu(self) -> None:
        self.update(details='In the Menus', state=None)

    def update_for_sandbox(self, plugin_count: int) -> None:
        self.update(details='In the Sandbox', state=f'{plugin_count} Plugins loaded')

    def shutdown(self) -> None:
        try:
            if self.rpc is not None:
                self.rpc.close()
        except Exception:
            pass
        finally:
            self.rpc = None
            self.enabled = False
            self._last_details = None
            self._last_state = None
_rpc = _DiscordRPC()

def init(client_id: Optional[str]=None) -> None:
    _rpc.init(client_id)

def update_for_menu() -> None:
    _rpc.update_for_menu()

def update_for_sandbox(plugin_count: int) -> None:
    _rpc.update_for_sandbox(plugin_count)

def shutdown() -> None:
    _rpc.shutdown()
