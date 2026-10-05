import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from .const import DOMAIN, CONF_URL, CONF_USERNAME, CONF_PASSWORD, CONF_UPDATE_INTERVAL, CONF_VERIFY_SSL
from .api import BeszelApiClient

class BeszelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 3
    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            return self.async_create_entry(
                title="Beszel API",
                data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_URL): str,
                vol.Optional(CONF_USERNAME): str,
                vol.Optional(CONF_PASSWORD): str,
                vol.Optional(CONF_UPDATE_INTERVAL, default=120): int,
                vol.Optional(CONF_VERIFY_SSL, default=True): bool,
            }),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data=None):
        """Handle initiation of re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Handle re-authentication confirmation."""
        errors = {}
        reauth_entry = (
            self._get_reauth_entry()
            if hasattr(self, "_get_reauth_entry")
            else self.hass.config_entries.async_get_entry(self.context["entry_id"])
        )
        if user_input is not None:
            client = BeszelApiClient(
                reauth_entry.data[CONF_URL],
                user_input.get(CONF_USERNAME),
                user_input.get(CONF_PASSWORD),
                reauth_entry.data.get(CONF_VERIFY_SSL, True),
            )
            try:
                await self.hass.async_add_executor_job(client.get_systems)
            except ConfigEntryAuthFailed:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={**reauth_entry.data, **user_input},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_USERNAME,
                    default=reauth_entry.data.get(CONF_USERNAME) or "",
                ): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return BeszelOptionsFlow(config_entry)


class BeszelOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        super().__init__()
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                self._config_entry,
                data={**self._config_entry.data, **user_input}
            )
            await self.hass.config_entries.async_reload(self._config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_URL,
                    default=self._config_entry.data.get(CONF_URL)
                ): str,
                vol.Optional(
                    CONF_USERNAME,
                    default=self._config_entry.data.get(CONF_USERNAME)
                ): str,
                vol.Optional(
                    CONF_PASSWORD,
                    default=self._config_entry.data.get(CONF_PASSWORD)
                ): str,
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    default=self._config_entry.data.get(CONF_UPDATE_INTERVAL, 120)
                ): int,
                vol.Optional(
                    CONF_VERIFY_SSL,
                    default=self._config_entry.data.get(CONF_VERIFY_SSL, True)
                ): bool,
            }),
        )