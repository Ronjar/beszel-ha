import logging

import httpx
from pocketbase import PocketBase

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

    def _ensure_client(self):
        """Initialize the PocketBase client if not already done"""
        if self._client is None:
            try:
                httpx_client = httpx.Client(verify=self._verify_ssl)
                self._client = PocketBase(self._url, http_client=httpx_client)
                if self._username and self._password:
                    self._client.collection("users").auth_with_password(
                        self._username,
                        self._password,
                    )
            except Exception as e:
                LOGGER.error(f"Failed to initialize PocketBase client: {e}")
                raise

    def get_systems(self):
        try:
            self._ensure_client()
            records = self._client.collection("systems").get_full_list()
            return records
        except Exception as e:
            LOGGER.error(f"Failed to fetch systems: {e}")
            raise

    def get_system_stats(self, system_id):
        """Get the latest system stats for a specific system"""
        try:
            self._ensure_client()
            # Get the latest record for the specific system
            records = self._client.collection("system_stats").get_list(
                1, 1, {"filter": f"system = '{system_id}'", "sort": "-created"}
            )
            if records.items:
                return records.items[0]
            return None
        except Exception as e:
            LOGGER.error(f"Failed to fetch stats for system {system_id}: {e}")
            # Return None if no stats found or error occurs
            return None

    def get_smart_devices(self, system_id=None):
        """Get S.M.A.R.T. data for disks"""
        try:
            self._ensure_client()
            if system_id:
                # Get devices for specific system
                records = self._client.collection("smart_devices").get_full_list(
                    query_params={"filter": f"system = '{system_id}'"}
                )
            else:
                # Get all devices
                records = self._client.collection("smart_devices").get_full_list()
            return records
        except Exception as e:
            LOGGER.error(f"Failed to fetch S.M.A.R.T. devices: {e}")
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
        try:
            self.api_client._ensure_client()
            
            info_res = self.api_client._client.send("/api/beszel/info", {"method": "GET"})
            hub_version = self._remove_version_prefix(info_res.get("v"))
            check_update = info_res.get("cu", False)

            latest_version = None
            latest_release_url = None

            if check_update:
                update_res = self.api_client._client.send("/api/beszel/update", {"method": "GET"})
                latest_version = self._remove_version_prefix(update_res.get("v"))
                latest_release_url = update_res.get("url")

            installed_t = self._to_tuple(hub_version)
            latest_t = self._to_tuple(latest_version)

            update_available = False
            if installed_t and latest_t:
                update_available = latest_t > installed_t
            
            if not update_available:
                latest_version = hub_version

            result = {
                "hub_version": hub_version,
                "latest_version": latest_version,
                "latest_release_url": latest_release_url,
                "update_available": update_available,
                "check_update": check_update,
            }
            return result
        except Exception as e:
            LOGGER.error("Error fetching update info from PocketBase API: %s", e)
            return {
                "hub_version": None,
                "latest_version": None,
                "latest_release_url": None,
                "update_available": False,
                "check_update": False,
            }