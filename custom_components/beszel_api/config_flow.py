import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN, CONF_URL, CONF_USERNAME, CONF_PASSWORD, CONF_VERIFY_SSL, CONF_UPDATE_CHECK

class BeszelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2
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
                vol.Optional(CONF_VERIFY_SSL, default=True): bool,
                vol.Optional(CONF_UPDATE_CHECK, default=False): bool,
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
                    CONF_UPDATE_CHECK,
                    default=self._config_entry.data.get(CONF_UPDATE_CHECK, False)
                ): bool,
                vol.Optional(
                    CONF_VERIFY_SSL,
                    default=self._config_entry.data.get(CONF_VERIFY_SSL, True)
                ): bool,
            }),
        )