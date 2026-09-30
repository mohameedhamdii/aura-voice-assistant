/**
 * @file matter_controller.c
 * @brief Matter protocol controller implementation.
 *
 * Manages the Matter stack, handles commissioning, and dispatches
 * cluster commands to connected smart devices over Thread/BLE.
 *
 * Note: This is a scaffold implementation. The actual ESP-Matter SDK
 * integration requires the connectedhomeip (CHIP) library which is
 * included via the ESP-Matter component. The function bodies below
 * contain the structural framework — the specific CHIP API calls
 * will need to be connected during the hardware integration phase.
 */

#include "matter_controller.h"
#include "device_registry.h"

#include <string.h>
#include "esp_log.h"
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

static const char *TAG = "matter_ctrl";

/** Matter fabric initialisation state. */
static bool s_matter_initialised = false;

/* -------------------------------------------------------------------------- */
/* Colour name to HSV mapping                                                 */
/* -------------------------------------------------------------------------- */

typedef struct {
    const char *name;
    uint8_t hue;        /* 0-254 (maps to 0-360°) */
    uint8_t saturation; /* 0-254 */
} color_preset_t;

static const color_preset_t COLOR_PRESETS[] = {
    {"red",    0,   254},
    {"orange", 21,  254},
    {"yellow", 42,  254},
    {"green",  85,  254},
    {"blue",   169, 254},
    {"purple", 212, 254},
    {"white",  0,   0},
    {"warm",   21,  140},
    {"cool",   148, 80},
};

#define NUM_COLOR_PRESETS (sizeof(COLOR_PRESETS) / sizeof(COLOR_PRESETS[0]))

/**
 * Look up a colour name and return its HSV values.
 */
static bool lookup_color(const char *name, uint8_t *hue, uint8_t *saturation)
{
    for (int i = 0; i < NUM_COLOR_PRESETS; i++) {
        if (strcasecmp(name, COLOR_PRESETS[i].name) == 0) {
            *hue = COLOR_PRESETS[i].hue;
            *saturation = COLOR_PRESETS[i].saturation;
            return true;
        }
    }
    return false;
}

/* -------------------------------------------------------------------------- */
/* Public API                                                                 */
/* -------------------------------------------------------------------------- */

esp_err_t matter_controller_init(void)
{
    ESP_LOGI(TAG, "Initialising Matter controller...");

    /* Initialise NVS for storing fabric credentials */
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES ||
        err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_LOGW(TAG, "Erasing NVS partition for fresh start");
        nvs_flash_erase();
        err = nvs_flash_init();
    }
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "NVS init failed: %s", esp_err_to_name(err));
        return err;
    }

    /*
     * TODO: Initialise the ESP-Matter SDK here.
     *
     * This would typically involve:
     *   1. esp_matter::start() — Start the Matter stack
     *   2. Set up the controller node
     *   3. Load previously commissioned device list from NVS
     *   4. Set up the Thread/BLE transport
     *
     * The exact API depends on the ESP-Matter SDK version.
     * Refer to: https://github.com/espressif/esp-matter
     *
     * Example (pseudo-code):
     *   node_t *node = node::create(...);
     *   esp_matter::start(on_matter_event);
     */

    s_matter_initialised = true;
    ESP_LOGI(TAG, "Matter controller initialised");

    return ESP_OK;
}

esp_err_t matter_controller_start(void)
{
    if (!s_matter_initialised) {
        ESP_LOGE(TAG, "Matter controller not initialised");
        return ESP_ERR_INVALID_STATE;
    }

    ESP_LOGI(TAG, "Matter controller started — ready for commands");

    /*
     * TODO: Start the Matter event loop / task.
     * The ESP-Matter SDK typically runs its own FreeRTOS task.
     */

    return ESP_OK;
}

esp_err_t matter_send_on_off(uint16_t node_id, uint8_t endpoint, bool on)
{
    ESP_LOGI(TAG, "Sending On/Off command: node=%d, ep=%d, on=%s",
             node_id, endpoint, on ? "true" : "false");

    /*
     * TODO: Send the actual Matter On/Off cluster command.
     *
     * Using the ESP-Matter controller API:
     *   esp_matter::controller::send_invoke_cluster_command(
     *       node_id, endpoint,
     *       chip::app::Clusters::OnOff::Id,
     *       on ? chip::app::Clusters::OnOff::Commands::On::Id
     *          : chip::app::Clusters::OnOff::Commands::Off::Id,
     *       NULL  // no additional data
     *   );
     */

    /* Update local device registry state */
    device_entry_t *dev = device_registry_find_by_node_id(node_id);
    if (dev != NULL) {
        dev->is_on = on;
        ESP_LOGI(TAG, "Device '%s' state updated: %s", dev->name,
                 on ? "ON" : "OFF");
    }

    return ESP_OK;
}

esp_err_t matter_send_level(uint16_t node_id, uint8_t endpoint,
                             uint8_t level, uint16_t transition_s)
{
    ESP_LOGI(TAG, "Sending Level command: node=%d, ep=%d, level=%d, trans=%ds",
             node_id, endpoint, level, transition_s);

    /*
     * TODO: Send Matter Level Control MoveToLevel command.
     *
     * chip::app::Clusters::LevelControl::Commands::MoveToLevel::Type cmd;
     * cmd.level = level;
     * cmd.transitionTime = transition_s * 10;  // tenths of a second
     * cmd.optionsMask = 0;
     * cmd.optionsOverride = 0;
     */

    /* Update local state */
    device_entry_t *dev = device_registry_find_by_node_id(node_id);
    if (dev != NULL) {
        dev->brightness = level;
        if (level > 0) dev->is_on = true;
    }

    return ESP_OK;
}

esp_err_t matter_send_color(uint16_t node_id, uint8_t endpoint,
                             uint8_t hue, uint8_t saturation,
                             uint16_t transition_s)
{
    ESP_LOGI(TAG, "Sending Color command: node=%d, ep=%d, hue=%d, sat=%d",
             node_id, endpoint, hue, saturation);

    /*
     * TODO: Send Matter Color Control MoveToHueAndSaturation command.
     *
     * chip::app::Clusters::ColorControl::Commands::MoveToHueAndSaturation::Type cmd;
     * cmd.hue = hue;
     * cmd.saturation = saturation;
     * cmd.transitionTime = transition_s * 10;
     * cmd.optionsMask = 0;
     * cmd.optionsOverride = 0;
     */

    return ESP_OK;
}

esp_err_t matter_commission_device(const char *setup_code,
                                    uint16_t discriminator)
{
    ESP_LOGI(TAG, "Commissioning device: code=%s, disc=%d",
             setup_code, discriminator);

    /*
     * TODO: Initiate Matter commissioning over BLE/Thread.
     *
     * This is a complex operation involving:
     *   1. BLE advertising/scanning to find the device
     *   2. PASE (Passcode-Authenticated Session Establishment)
     *   3. Certificate provisioning
     *   4. Network provisioning (Thread credentials)
     *   5. Saving fabric info to NVS
     *
     * The ESP-Matter SDK provides helper functions for this.
     * Refer to the ESP-Matter controller example.
     */

    return ESP_OK;
}

bool matter_is_device_reachable(uint16_t node_id)
{
    /*
     * TODO: Send a ping or read attribute to check reachability.
     * For now, assume all registered devices are reachable.
     */
    return device_registry_find_by_node_id(node_id) != NULL;
}

void matter_controller_stop(void)
{
    ESP_LOGI(TAG, "Stopping Matter controller...");

    /*
     * TODO: Gracefully shut down the Matter stack.
     * Save any pending state to NVS.
     */

    s_matter_initialised = false;
    ESP_LOGI(TAG, "Matter controller stopped");
}
