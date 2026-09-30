/**
 * @file device_registry.h
 * @brief Local device registry for tracking Matter device states.
 *
 * Maintains a list of commissioned devices with their current states
 * (on/off, brightness, colour). States are stored in RAM and optionally
 * persisted to NVS.
 */

#ifndef DEVICE_REGISTRY_H
#define DEVICE_REGISTRY_H

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

/** Maximum number of devices in the registry. */
#define DEVICE_REGISTRY_MAX_DEVICES 16

/** Maximum length of device name. */
#define DEVICE_NAME_MAX_LEN 64

/**
 * Device type enumeration.
 */
typedef enum {
    DEVICE_TYPE_LIGHT = 0,
    DEVICE_TYPE_PLUG  = 1,
    DEVICE_TYPE_UNKNOWN = 255,
} device_type_t;

/**
 * Device capability flags.
 */
typedef enum {
    DEVICE_CAP_ON_OFF     = (1 << 0),
    DEVICE_CAP_BRIGHTNESS = (1 << 1),
    DEVICE_CAP_COLOR      = (1 << 2),
} device_capability_t;

/**
 * Device registry entry.
 */
typedef struct {
    char name[DEVICE_NAME_MAX_LEN]; /**< Device name (e.g., "living_room_light") */
    device_type_t type;              /**< Device type */
    uint16_t matter_node_id;         /**< Matter fabric node ID */
    uint8_t matter_endpoint;         /**< Matter endpoint number */
    uint8_t capabilities;            /**< Bitmask of device_capability_t */
    bool is_on;                      /**< Current on/off state */
    uint8_t brightness;              /**< Current brightness (0-254) */
    uint8_t hue;                     /**< Current hue (0-254) */
    uint8_t saturation;              /**< Current saturation (0-254) */
    bool is_reachable;               /**< Whether the device is currently reachable */
} device_entry_t;

/**
 * Initialise the device registry.
 *
 * Loads default devices and any persisted state from NVS.
 *
 * @return ESP_OK on success.
 */
esp_err_t device_registry_init(void);

/**
 * Add a device to the registry.
 *
 * @param name         Device name.
 * @param type         Device type.
 * @param node_id      Matter node ID.
 * @param endpoint     Matter endpoint.
 * @param capabilities Capability bitmask.
 * @return ESP_OK on success, ESP_ERR_NO_MEM if registry is full.
 */
esp_err_t device_registry_add(const char *name, device_type_t type,
                               uint16_t node_id, uint8_t endpoint,
                               uint8_t capabilities);

/**
 * Find a device by name.
 *
 * @param name Device name to search for.
 * @return Pointer to the device entry, or NULL if not found.
 */
device_entry_t *device_registry_find(const char *name);

/**
 * Find a device by Matter node ID.
 *
 * @param node_id Matter node ID to search for.
 * @return Pointer to the device entry, or NULL if not found.
 */
device_entry_t *device_registry_find_by_node_id(uint16_t node_id);

/**
 * Get a device by index.
 *
 * @param index Device index (0-based).
 * @return Pointer to the device entry, or NULL if index is out of range.
 */
const device_entry_t *device_registry_get(int index);

/**
 * Get the number of registered devices.
 *
 * @return Number of devices in the registry.
 */
int device_registry_count(void);

/**
 * Save device states to NVS for persistence across reboots.
 *
 * @return ESP_OK on success.
 */
esp_err_t device_registry_save(void);

/**
 * Clear the device registry.
 */
void device_registry_clear(void);

#ifdef __cplusplus
}
#endif

#endif /* DEVICE_REGISTRY_H */
