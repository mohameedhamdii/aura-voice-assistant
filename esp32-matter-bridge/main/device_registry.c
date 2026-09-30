/**
 * @file device_registry.c
 * @brief Local device registry implementation.
 *
 * Manages a static array of device entries with NVS persistence support.
 * Pre-populates with the three default demo devices on first boot.
 */

#include "device_registry.h"

#include <string.h>
#include <stdio.h>

#include "esp_log.h"
#include "nvs_flash.h"
#include "nvs.h"

static const char *TAG = "device_reg";

/** Static device registry array. */
static device_entry_t s_devices[DEVICE_REGISTRY_MAX_DEVICES];

/** Number of devices currently in the registry. */
static int s_device_count = 0;

/** NVS namespace for device state persistence. */
#define NVS_NAMESPACE "dev_registry"

/* -------------------------------------------------------------------------- */
/* Default device setup                                                       */
/* -------------------------------------------------------------------------- */

/**
 * Populate the registry with the default demo devices.
 */
static void load_default_devices(void)
{
    ESP_LOGI(TAG, "Loading default devices...");

    /* Living room light — full capabilities */
    device_registry_add(
        "living_room_light",
        DEVICE_TYPE_LIGHT,
        1,  /* node_id */
        1,  /* endpoint */
        DEVICE_CAP_ON_OFF | DEVICE_CAP_BRIGHTNESS | DEVICE_CAP_COLOR
    );

    /* Bedroom light — on/off + brightness only */
    device_registry_add(
        "bedroom_light",
        DEVICE_TYPE_LIGHT,
        2,
        1,
        DEVICE_CAP_ON_OFF | DEVICE_CAP_BRIGHTNESS
    );

    /* Smart plug — on/off only */
    device_registry_add(
        "smart_plug_1",
        DEVICE_TYPE_PLUG,
        3,
        1,
        DEVICE_CAP_ON_OFF
    );

    ESP_LOGI(TAG, "Loaded %d default devices", s_device_count);
}

/* -------------------------------------------------------------------------- */
/* Public API                                                                 */
/* -------------------------------------------------------------------------- */

esp_err_t device_registry_init(void)
{
    memset(s_devices, 0, sizeof(s_devices));
    s_device_count = 0;

    /* Try to load from NVS first */
    nvs_handle_t nvs;
    esp_err_t err = nvs_open(NVS_NAMESPACE, NVS_READONLY, &nvs);

    if (err == ESP_OK) {
        size_t required_size = sizeof(s_devices);
        err = nvs_get_blob(nvs, "devices", s_devices, &required_size);

        if (err == ESP_OK) {
            /* Restore device count */
            size_t count_size = sizeof(s_device_count);
            nvs_get_blob(nvs, "dev_count", &s_device_count, &count_size);
            ESP_LOGI(TAG, "Loaded %d devices from NVS", s_device_count);
        } else {
            ESP_LOGI(TAG, "No saved device state, loading defaults");
            load_default_devices();
        }

        nvs_close(nvs);
    } else {
        ESP_LOGI(TAG, "NVS not available, loading defaults");
        load_default_devices();
    }

    return ESP_OK;
}

esp_err_t device_registry_add(const char *name, device_type_t type,
                               uint16_t node_id, uint8_t endpoint,
                               uint8_t capabilities)
{
    if (s_device_count >= DEVICE_REGISTRY_MAX_DEVICES) {
        ESP_LOGE(TAG, "Device registry full (max %d)", DEVICE_REGISTRY_MAX_DEVICES);
        return ESP_ERR_NO_MEM;
    }

    /* Check for duplicate */
    if (device_registry_find(name) != NULL) {
        ESP_LOGW(TAG, "Device '%s' already registered", name);
        return ESP_ERR_INVALID_ARG;
    }

    device_entry_t *dev = &s_devices[s_device_count];
    memset(dev, 0, sizeof(*dev));

    strncpy(dev->name, name, DEVICE_NAME_MAX_LEN - 1);
    dev->name[DEVICE_NAME_MAX_LEN - 1] = '\0';
    dev->type = type;
    dev->matter_node_id = node_id;
    dev->matter_endpoint = endpoint;
    dev->capabilities = capabilities;
    dev->is_on = false;
    dev->brightness = 254;  /* Default to full brightness */
    dev->hue = 0;
    dev->saturation = 0;
    dev->is_reachable = true;

    s_device_count++;

    ESP_LOGI(TAG, "Added device '%s' (node=%d, ep=%d, caps=0x%02x)",
             name, node_id, endpoint, capabilities);

    return ESP_OK;
}

device_entry_t *device_registry_find(const char *name)
{
    for (int i = 0; i < s_device_count; i++) {
        if (strcmp(s_devices[i].name, name) == 0) {
            return &s_devices[i];
        }
    }
    return NULL;
}

device_entry_t *device_registry_find_by_node_id(uint16_t node_id)
{
    for (int i = 0; i < s_device_count; i++) {
        if (s_devices[i].matter_node_id == node_id) {
            return &s_devices[i];
        }
    }
    return NULL;
}

const device_entry_t *device_registry_get(int index)
{
    if (index < 0 || index >= s_device_count) {
        return NULL;
    }
    return &s_devices[index];
}

int device_registry_count(void)
{
    return s_device_count;
}

esp_err_t device_registry_save(void)
{
    nvs_handle_t nvs;
    esp_err_t err = nvs_open(NVS_NAMESPACE, NVS_READWRITE, &nvs);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to open NVS: %s", esp_err_to_name(err));
        return err;
    }

    err = nvs_set_blob(nvs, "devices", s_devices, sizeof(s_devices));
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to save devices: %s", esp_err_to_name(err));
        nvs_close(nvs);
        return err;
    }

    err = nvs_set_blob(nvs, "dev_count", &s_device_count, sizeof(s_device_count));
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Failed to save device count: %s", esp_err_to_name(err));
        nvs_close(nvs);
        return err;
    }

    err = nvs_commit(nvs);
    nvs_close(nvs);

    ESP_LOGI(TAG, "Saved %d devices to NVS", s_device_count);
    return err;
}

void device_registry_clear(void)
{
    memset(s_devices, 0, sizeof(s_devices));
    s_device_count = 0;
    ESP_LOGI(TAG, "Device registry cleared");
}
