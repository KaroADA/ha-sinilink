# Sinilink Amplifier Home Assistant Integration

This is a custom integration for Home Assistant to control Sinilink Bluetooth audio amplifiers. It allows you to manage power, volume, and input sources directly from Home Assistant.

## Features

* **Power Control**: Turn the amplifier on and off.
* **Volume Control**: Set the volume, step volume up/down, and mute/unmute.
* **Source Selection**: Switch between "AUX" and "Bluetooth" inputs.

## Prerequisites

* A working **Home Assistant Bluetooth** integration.
* The **MAC address** of your Sinilink amplifier. You can usually find this using a Bluetooth scanning app on your phone. The device often broadcasts as "Sinilink-APP".

## Installation

### Method 1: HACS (Recommended)

Click the button below to add this repository to HACS:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=KaroADA&repository=ha-sinilink&category=integration)

**Manual HACS Installation:**

1.  Go to your HACS (Home Assistant Community Store) panel.
2.  Go to **Integrations** and click the three-dot menu in the top right.
3.  Select **Custom repositories**.
4.  Enter the URL for this repository.
5.  Select the category **Integration**.
6.  Click **Add**.
7.  Find the "Sinilink Amplifier" integration in the list and click **Install**.
8.  Restart Home Assistant.

### Method 2: Manual Installation

1.  Download the latest release or clone this repository.
2.  Copy the entire `custom_components/sinilink` directory into your Home Assistant `config/custom_components/` directory.
3.  Restart Home Assistant.

## Configuration

Configuration is done via the Home Assistant UI.

1.  Go to **Settings** \> **Devices & Services**.
2.  The integration will try to discover your device.
      * **If discovered:** You will see a "Discovered" card showing "Sinilink Amplifier". Click **Configure**.
      * **If not discovered:** Click the **Add Integration** button and search for **"Sinilink Amplifier"**.
3.  A configuration window will appear:
      * **Name (Optional)**: You can enter a friendly name for your amplifier (e.g., "Living Room Amp"). If left blank, the MAC address will be used.
      * **MAC**: This list will show any discovered devices by their MAC address, along with a "manual" option.
4.  Select the radio button for your device's MAC address (e.g., `AA:BB:CC:11:22:33`).
      * If your device was not listed, select **manual**.
5.  Click **Submit**.
6.  If you selected "manual", you will be prompted to enter the MAC address manually on the next screen. Click **Submit** again.
7.  The integration will be set up, and a new `media_player` entity will be created.

## Usage

Once configured, you can use the `media_player` entity like any other. Add it to your dashboards using a Media Control card or use it in automations and scripts.

* **Power:** Use the `media_player.turn_on` and `media_player.turn_off` services.
* **Volume:** Use the `media_player.volume_set`, `media_player.volume_up`, `media_player.volume_down`, and `media_player.volume_mute` services.
* **Source:** Use the `media_player.select_source` service with `AUX` or `Bluetooth` as the source.