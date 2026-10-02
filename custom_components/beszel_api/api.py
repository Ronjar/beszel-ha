import logging

import httpx
from pocketbase import PocketBase
from homeassistant.exceptions import ConfigEntryAuthFailed

LOGGER = logging.getLogger(__name__)


class BeszelApiClient:
    def __init__(
        self,
        url,
        username: str | None = None,
        password: str | None = None,
        verify_ssl: bool = True,
    ):
        self._url = url.rstrip("/")
        self._username = username
        self._password = password
        self._verify_ssl = verify_ssl
        self._client = None

    def _reset_client(self):
        """Reset the PocketBase client so a fresh session and connection pool is used."""
        self._client = None

    def _ensure_client(self):
        """Initialize or re-authenticate the PocketBase client if session is invalid."""
        if self._client is None:
            self._client = PocketBase(self._url, verify=self._verify_ssl)

        if not self._client.auth_store.is_valid:
            if self._username and self._password:
                try:
                    self._client.auth_store.clear()
                    self._client.collection("users").auth_with_password(
                        self._username,
                        self._password,
                    )
                    LOGGER.info("Authenticated with Beszel Hub")
                except Exception as e:
                    if getattr(e, "status", None) == 400:
                        raise ConfigEntryAuthFailed(f"Invalid username or password for Beszel Hub: {e}") from e
                    LOGGER.error(f"Failed to authenticate with Beszel Hub: {e}")
                    raise

    def _execute_with_retry(self, operation):
        """Execute an API operation with automatic reconnection and re-authentication on failure."""
        self._ensure_client()
        try:
            return operation(self._client)
        except ConfigEntryAuthFailed:
            raise
        except Exception as e:
            LOGGER.warning("API operation failed (%s), attempting reconnect and re-authentication...", e)
            self._reset_client()
            self._ensure_client()
            return operation(self._client)

    def get_systems(self):
        def _fetch(client):
            return client.collection("systems").get_full_list()

        records = self._execute_with_retry(_fetch)

        # PocketBase returns HTTP 200 with [] if the auth token is invalid on the server.
        # If records is empty, check whether the token is actually still valid:
        if not records and self._username and self._password:
            try:
                self._client.collection("users").auth_refresh()
            except ConfigEntryAuthFailed:
                raise
            except Exception:
                LOGGER.info("Session invalid on server; re-authenticating...")
                self._reset_client()
                self._ensure_client()
                records = self._client.collection("systems").get_full_list()

        return records

    def get_system_stats(self, system_id):
        """Get the latest system stats for a specific system"""
        def _fetch(client):
            records = client.collection("system_stats").get_list(
                1, 1, {"filter": f"system = '{system_id}'", "sort": "-created"}
            )
            if records.items:
                return records.items[0]
            return None

        try:
            return self._execute_with_retry(_fetch)
        except Exception as e:
            LOGGER.error("Failed to fetch stats for system %s: %s", system_id, e)
            return None

    def get_smart_devices(self, system_id=None):
        """Get S.M.A.R.T. data for disks"""
        def _fetch(client):
            if system_id:
                return client.collection("smart_devices").get_full_list(
                    query_params={"filter": f"system = '{system_id}'"}
                )
            return client.collection("smart_devices").get_full_list()

        try:
            return self._execute_with_retry(_fetch)
        except Exception as e:
            LOGGER.error("Failed to fetch S.M.A.R.T. devices: %s", e)
            return []


class BeszelUpdateApi:
    def __init__(self, api_client: BeszelApiClient):
        self.api_client = api_client

    def _remove_version_prefix(self, v: str | None) -> str | None:
        if not v:
            return None
        return v.lstrip("v").strip()

    def _to_tuple(self, v: str | None) -> tuple:
        """
        Converts "0.16.1" into a tuple of ints (0,16,1).
        """
        if not v:
            return ()
        parts = []
        for p in v.split("."):
            try:
                parts.append(int(p))
            except Exception:
                break
        return tuple(parts)

    def get_update_info(self) -> dict:
        """
        Returns:
          {
            "hub_version": <installed version or None>,
            "latest_version": <latest release tag or None>,
            "latest_release_url": <html_url or None>,
            "update_available": <bool>,
            "check_update": <bool>
          }
        """
        def _fetch(client):
            info_res = client.send("/api/beszel/info", {"method": "GET"})
            hub_version = self._remove_version_prefix(info_res.get("v"))
            check_update = info_res.get("cu", False)

            latest_version = None
            latest_release_url = None

            if check_update:
                update_res = client.send("/api/beszel/update", {"method": "GET"})
                latest_version = self._remove_version_prefix(update_res.get("v"))
                latest_release_url = update_res.get("url")

            installed_t = self._to_tuple(hub_version)
            latest_t = self._to_tuple(latest_version)

            update_available = False
            if installed_t and latest_t:
                update_available = latest_t > installed_t
            
            if not update_available:
                latest_version = hub_version

            return {
                "hub_version": hub_version,
                "latest_version": latest_version,
                "latest_release_url": latest_release_url,
                "update_available": update_available,
                "check_update": check_update,
            }

        try:
            return self.api_client._execute_with_retry(_fetch)
        except Exception as e:
            LOGGER.error("Error fetching update info from PocketBase API: %s", e)
            return {
                "hub_version": None,
                "latest_version": None,
                "latest_release_url": None,
                "update_available": False,
                "check_update": False,
            }