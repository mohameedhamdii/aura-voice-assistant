/**
 * @file matter_controller.h
 * @brief Matter protocol controller for smart device management.
 *
 * Handles Matter fabric setup, device commissioning, and sending
 * cluster commands (On/Off, Level Control, Color Control) to
 * commissioned devices.
 */

#ifndef MATTER_CONTROLLER_H
#define MATTER_CONTROLLER_H

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Initialise the Matter controller.
 *
 * Sets up the Matter stack, loads fabric credentials from NVS,
 * and prepares for device communication.
 *
 * @return ESP_OK on success.
 */
esp_err_t matter_controller_init(void);

/**
 * Start the Matter controller.
 *
 * Begins the Matter event loop and enables device discovery.
 *
 * @return ESP_OK on success.
 */
esp_err_t matter_controller_start(void);

/**
 * Send an On/Off cluster command to a device.
 *
 * @param node_id   Matter node ID of the target device.
 * @param endpoint  Endpoint number on the target device.
 * @param on        true to turn on, false to turn off.
 * @return ESP_OK on success.
 */
esp_err_t matter_send_on_off(uint16_t node_id, uint8_t endpoint, bool on);

/**
 * Send a Level Control (brightness) command to a device.
 *
 * @param node_id      Matter node ID of the target device.
 * @param endpoint     Endpoint number on the target device.
 * @param level        Brightness level (0-254).
 * @param transition_s Transition time in seconds (0 for immediate).
 * @return ESP_OK on success.
 */
esp_err_t matter_send_level(uint16_t node_id, uint8_t endpoint,
                             uint8_t level, uint16_t transition_s);

/**
 * Send a Color Control command to a device.
 *
 * @param node_id      Matter node ID of the target device.
 * @param endpoint     Endpoint number on the target device.
 * @param hue          Hue value (0-254).
 * @param saturation   Saturation value (0-254).
 * @param transition_s Transition time in seconds.
 * @return ESP_OK on success.
 */
esp_err_t matter_send_color(uint16_t node_id, uint8_t endpoint,
                             uint8_t hue, uint8_t saturation,
                             uint16_t transition_s);

/**
 * Commission a new device into the Matter fabric.
 *
 * @param setup_code The device's setup code (e.g., "34970112332").
 * @param discriminator The device's discriminator value.
 * @return ESP_OK on success.
 */
esp_err_t matter_commission_device(const char *setup_code,
                                    uint16_t discriminator);

/**
 * Check if a commissioned device is reachable.
 *
 * @param node_id Matter node ID to check.
 * @return true if the device is reachable.
 */
bool matter_is_device_reachable(uint16_t node_id);

/**
 * Stop the Matter controller and free resources.
 */
void matter_controller_stop(void);

#ifdef __cplusplus
}
#endif

#endif /* MATTER_CONTROLLER_H */
