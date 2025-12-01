# Installation
As this repository is not yet added in the default HACS repository you have to add the repository beforehand.

1. Go to the HACS Tab
2. Click on the three dot menu in the top right and select Custom repositories
3. Add ```https://github.com/Ronjar/beszel-ha```
4. Restart HomeAssistant
5. Go to integrations, press Add integration and search for BeszelAPI
6. In the Setup Dialog use the following values
    - *URL*: The root url / IP of your Beszel instance, like http://beszel.example.com or https://beszel.example.com
    - *user*: Either your default admin username / email or (recommended) create another user with the role user and assigning the agents you want to expose to it.
    - *password*: The password to the user
7. The API will pull the data and reload every 2 minutes

Currently all machines are added, selection will be added later (you can change this yourself by creating a new user in Beszels Pocketbas and adding this user only to the machines you want to be monitored).

# Usage
After installing the following entities will exposed as sensors (more to come):
- Status (Connection)
- Uptime (Minutes)
- CPU (Percentage)
- Disk usage (Percentage)
- Temperature (°C)
- Bandwidth (Mbit/s)
- RAM (Percentage)
- Battery (Percentage)

For example if your machine is named *test*, CPU will be available as ```sensor.test_cpu```

# Examples
Here is one of my machines with the entities the integration currently exports
![Screenshot from HomeAssistant settings page of my device and its entities](/pictures/sensors.png)

And here one card I created for myself using those sensors:
![Screenshot from HomeAssistant dashboard with a card showing CPU, RAM and Disk usage as bar charts](/pictures/example_card.png)

The YAML for this card layout:
``` YAML
type: custom:vertical-stack-in-card
cards:
  - type: horizontal-stack
    cards:
      - type: custom:mushroom-template-card
        primary: Evergreen
        icon: mdi:server
        secondary: ""
        icon_color: |-
          {% if states('binary_sensor.evergreen_status') | bool %}
            green
          {% else %}
            red
          {% endif %}
        fill_container: false
        multiline_secondary: false
        entity: binary_sensor.evergreen_status
      - type: custom:mushroom-template-card
        entity: sensor.evergreen_uptime
        icon: mdi:sort-clock-descending
        primary: "{{ (states('sensor.evergreen_uptime') | int / 1440) | int  }} Days"
        secondary: ""
        icon_color: blue
        card_mod:
          style: |
            ha-card {
              margin: 0 10px;
              align-items: end;
              box-shadow: none;
            }
  - type: custom:bar-card
    entities:
      - entity: sensor.evergreen_cpu
        name: CPU
        color: "#4caf50"
      - entity: sensor.evergreen_ram
        name: RAM
        color: "#2196f3"
      - entity: sensor.evergreen_disk
        name: Disk
        color: "#f44336"
    positions:
      indicator: "off"
```
