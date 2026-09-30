/**
 * @file main.c
 * @brief ESP32-C6 Matter Bridge — Main application entry point.
 *
 * This firmware runs on the ESP32-C6 and acts as a bridge between
 * the Raspberry Pi (connected via UART) and Matter-compatible smart
 * devices (connected via Thread/BLE).
 *
 * Flow:
 *   1. Initialise NVS, device registry, Matter stack, and serial handler.
 *   2. Listen for JSON commands from the Pi on UART0.
 *   3. Map commands to Matter cluster operations (On/Off, Level, Color).
 *   4. Send status responses back to the Pi.
 *   5. Send periodic heartbeats with device states.
 */

#include <stdio.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_system.h"
#include "nvs_flash.h"

#include "serial_handler.h"
#include "matter_controller.h"
#include "device_registry.h"

static const char *TAG = "main";

/* -------------------------------------------------------------------------- */
/* Command handler                                                            */
/* -------------------------------------------------------------------------- */

/**
 * Map a colour name string to hue and saturation values.
 */
static bool color_name_to_hsv(const char *name, uint8_t *hue, uint8_t *sat)
{
    typedef struct { const char *n; uint8_t h; uint8_t s; } cmap_t;
    static const cmap_t map[] = {
        {"red",    0,   254}, {"orange", 21,  254}, {"yellow", 42,  254},
        {"green",  85,  254}, {"blue",   169, 254}, {"purple", 212, 254},
        {"white",  0,   0},   {"warm",   21,  140}, {"cool",   148, 80},
    };
    for (int i = 0; i < sizeof(map)/sizeof(map[0]); i++) {
        if (strcasecmp(name, map[i].n) == 0) {
            *hue = map[i].h;
            *sat = map[i].s;
            return true;
        }
    }
    return false;
}

/**
 * Handle a command received from the Raspberry Pi via serial.
 *
 * @param cmd Parsed command structure.
 * @return true if the command was executed successfully.
 */
static bool handle_command(const serial_command_t *cmd)
{
    ESP_LOGI(TAG, "Handling command: device=%s, action=%s", cmd->device, cmd->action);

    /* Look up the device in the registry */
    device_entry_t *dev = device_registry_find(cmd->device);
    if (dev == NULL) {
        ESP_LOGW(TAG, "Unknown device: %s", cmd->device);
        serial_send_response("error", cmd->device, "unknown", "Device not found");
        return false;
    }

    esp_err_t err = ESP_OK;
    char state_str[32] = "unknown";

    /* Dispatch based on action */
    if (strcmp(cmd->action, "on") == 0) {
        /* On/Off: Turn on */
        if (!(dev->capabilities & DEVICE_CAP_ON_OFF)) {
            serial_send_response("error", cmd->device, state_str,
                                  "Device does not support on/off");
            return false;
        }
        err = matter_send_on_off(dev->matter_node_id, dev->matter_endpoint, true);
        dev->is_on = true;
        snprintf(state_str, sizeof(state_str), "on");

    } else if (strcmp(cmd->action, "off") == 0) {
        /* On/Off: Turn off */
        if (!(dev->capabilities & DEVICE_CAP_ON_OFF)) {
            serial_send_response("error", cmd->device, state_str,
                                  "Device does not support on/off");
            return false;
        }
        err = matter_send_on_off(dev->matter_node_id, dev->matter_endpoint, false);
        dev->is_on = false;
        snprintf(state_str, sizeof(state_str), "off");

    } else if (strcmp(cmd->action, "brightness") == 0) {
        /* Level Control: Set brightness */
        if (!(dev->capabilities & DEVICE_CAP_BRIGHTNESS)) {
            serial_send_response("error", cmd->device, state_str,
                                  "Device does not support brightness");
            return false;
        }
        int level = 127; /* Default to 50% */
        if (cmd->has_value) {
            int pct = atoi(cmd->value);
            if (pct < 0) pct = 0;
            if (pct > 100) pct = 100;
            level = (pct * 254) / 100;
        }
        err = matter_send_level(dev->matter_node_id, dev->matter_endpoint,
                                 (uint8_t)level, 0);
        dev->brightness = (uint8_t)level;
        dev->is_on = (level > 0);
        snprintf(state_str, sizeof(state_str), "brightness_%d", (level * 100) / 254);

    } else if (strcmp(cmd->action, "color") == 0) {
        /* Color Control: Set colour */
        if (!(dev->capabilities & DEVICE_CAP_COLOR)) {
            serial_send_response("error", cmd->device, state_str,
                                  "Device does not support color");
            return false;
        }
        uint8_t hue = 0, sat = 254;
        if (cmd->has_value) {
            if (!color_name_to_hsv(cmd->value, &hue, &sat)) {
                serial_send_response("error", cmd->device, state_str,
                                      "Unknown color name");
                return false;
            }
        }
        err = matter_send_color(dev->matter_node_id, dev->matter_endpoint,
                                 hue, sat, 0);
        dev->hue = hue;
        dev->saturation = sat;
        dev->is_on = true;
        snprintf(state_str, sizeof(state_str), "color_%s",
                 cmd->has_value ? cmd->value : "unknown");

    } else {
        ESP_LOGW(TAG, "Unknown action: %s", cmd->action);
        serial_send_response("error", cmd->device, state_str, "Unknown action");
        return false;
    }

    if (err != ESP_OK) {
        serial_send_response("error", cmd->device, state_str,
                              "Matter command failed");
        return false;
    }

    /* Send success response */
    serial_send_response("ok", cmd->device, state_str, NULL);

    /* Save updated state */
    device_registry_save();

    return true;
}

/* -------------------------------------------------------------------------- */
/* Main application                                                           */
/* -------------------------------------------------------------------------- */

void app_main(void)
{
    ESP_LOGI(TAG, "===========================================");
    ESP_LOGI(TAG, "  Matter Bridge for Voice Assistant");
    ESP_LOGI(TAG, "  ESP32-C6 Firmware v1.0.0");
    ESP_LOGI(TAG, "===========================================");

    /* Step 1: Initialise device registry */
    ESP_LOGI(TAG, "Step 1: Initialising device registry...");
    esp_err_t err = device_registry_init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Device registry init failed!");
        return;
    }
    ESP_LOGI(TAG, "  Registered %d devices", device_registry_count());

    /* Step 2: Initialise Matter controller */
    ESP_LOGI(TAG, "Step 2: Initialising Matter controller...");
    err = matter_controller_init();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Matter controller init failed!");
        return;
    }

    /* Step 3: Start Matter controller */
    ESP_LOGI(TAG, "Step 3: Starting Matter controller...");
    err = matter_controller_start();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Matter controller start failed!");
        return;
    }

    /* Step 4: Initialise serial handler */
    ESP_LOGI(TAG, "Step 4: Initialising serial handler...");
    err = serial_handler_init(handle_command);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Serial handler init failed!");
        return;
    }

    /* Step 5: Start serial handler */
    ESP_LOGI(TAG, "Step 5: Starting serial handler...");
    err = serial_handler_start();
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Serial handler start failed!");
        return;
    }

    ESP_LOGI(TAG, "===========================================");
    ESP_LOGI(TAG, "  Matter Bridge is READY");
    ESP_LOGI(TAG, "  Waiting for commands from Raspberry Pi...");
    ESP_LOGI(TAG, "===========================================");

    /* Main loop — keep the task alive */
    while (1) {
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
