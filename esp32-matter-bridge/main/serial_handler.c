/**
 * @file serial_handler.c
 * @brief Serial command handler implementation.
 *
 * Handles UART communication with the Raspberry Pi, parsing JSON commands
 * and sending JSON responses/heartbeats.
 */

#include "serial_handler.h"
#include "device_registry.h"

#include <string.h>
#include <stdio.h>
#include <stdlib.h>

#include "driver/uart.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "cJSON.h"

static const char *TAG = "serial_handler";

/** Command callback function pointer. */
static serial_cmd_callback_t s_cmd_callback = NULL;

/** Serial handler task handle. */
static TaskHandle_t s_serial_task_handle = NULL;

/** Heartbeat timer handle. */
static esp_timer_handle_t s_heartbeat_timer = NULL;

/** Running flag. */
static bool s_running = false;

/* -------------------------------------------------------------------------- */
/* Internal helpers                                                           */
/* -------------------------------------------------------------------------- */

/**
 * Parse a JSON command string into a serial_command_t structure.
 */
static bool parse_command(const char *json_str, serial_command_t *cmd)
{
    cJSON *root = cJSON_Parse(json_str);
    if (root == NULL) {
        ESP_LOGE(TAG, "Failed to parse command JSON: %s", json_str);
        return false;
    }

    /* Extract device name */
    cJSON *device = cJSON_GetObjectItem(root, "device");
    if (device == NULL || !cJSON_IsString(device)) {
        ESP_LOGE(TAG, "Missing 'device' field in command");
        cJSON_Delete(root);
        return false;
    }
    strncpy(cmd->device, device->valuestring, sizeof(cmd->device) - 1);
    cmd->device[sizeof(cmd->device) - 1] = '\0';

    /* Extract action */
    cJSON *action = cJSON_GetObjectItem(root, "action");
    if (action == NULL || !cJSON_IsString(action)) {
        ESP_LOGE(TAG, "Missing 'action' field in command");
        cJSON_Delete(root);
        return false;
    }
    strncpy(cmd->action, action->valuestring, sizeof(cmd->action) - 1);
    cmd->action[sizeof(cmd->action) - 1] = '\0';

    /* Extract optional value */
    cJSON *value = cJSON_GetObjectItem(root, "value");
    if (value != NULL && cJSON_IsString(value)) {
        strncpy(cmd->value, value->valuestring, sizeof(cmd->value) - 1);
        cmd->value[sizeof(cmd->value) - 1] = '\0';
        cmd->has_value = true;
    } else if (value != NULL && cJSON_IsNumber(value)) {
        snprintf(cmd->value, sizeof(cmd->value), "%d", value->valueint);
        cmd->has_value = true;
    } else {
        cmd->value[0] = '\0';
        cmd->has_value = false;
    }

    cJSON_Delete(root);
    return true;
}

/**
 * Process a single received line from UART.
 */
static void process_line(const char *line)
{
    /* Check for CMD: prefix */
    if (strncmp(line, "CMD:", 4) == 0) {
        const char *json_str = line + 4;
        serial_command_t cmd;
        memset(&cmd, 0, sizeof(cmd));

        if (parse_command(json_str, &cmd)) {
            ESP_LOGI(TAG, "Received command: device=%s, action=%s, value=%s",
                     cmd.device, cmd.action, cmd.has_value ? cmd.value : "none");

            /* Dispatch to callback */
            if (s_cmd_callback != NULL) {
                bool success = s_cmd_callback(&cmd);
                if (!success) {
                    serial_send_response("error", cmd.device, "unknown",
                                          "Command execution failed");
                }
            } else {
                serial_send_response("error", cmd.device, "unknown",
                                      "No command handler registered");
            }
        } else {
            /* Send error response for unparseable commands */
            serial_send_response("error", "unknown", "unknown",
                                  "Invalid command JSON");
        }
    } else {
        ESP_LOGD(TAG, "Ignoring non-command line: %s", line);
    }
}

/**
 * Serial handler FreeRTOS task — reads lines from UART.
 */
static void serial_task(void *arg)
{
    char line_buffer[SERIAL_MAX_LINE_LENGTH];
    int line_pos = 0;
    uint8_t byte;

    ESP_LOGI(TAG, "Serial handler task started");

    while (s_running) {
        /* Read one byte at a time */
        int len = uart_read_bytes(SERIAL_UART_PORT_NUM, &byte, 1,
                                   pdMS_TO_TICKS(100));
        if (len <= 0) {
            continue;
        }

        if (byte == '\n' || byte == '\r') {
            if (line_pos > 0) {
                line_buffer[line_pos] = '\0';
                process_line(line_buffer);
                line_pos = 0;
            }
        } else {
            if (line_pos < SERIAL_MAX_LINE_LENGTH - 1) {
                line_buffer[line_pos++] = (char)byte;
            } else {
                /* Line too long — discard */
                ESP_LOGW(TAG, "Line buffer overflow, discarding");
                line_pos = 0;
            }
        }
    }

    ESP_LOGI(TAG, "Serial handler task stopped");
    vTaskDelete(NULL);
}

/**
 * Heartbeat timer callback.
 */
static void heartbeat_timer_callback(void *arg)
{
    serial_send_heartbeat();
}

/* -------------------------------------------------------------------------- */
/* Public API                                                                 */
/* -------------------------------------------------------------------------- */

esp_err_t serial_handler_init(serial_cmd_callback_t cmd_callback)
{
    s_cmd_callback = cmd_callback;

    /* Configure UART */
    uart_config_t uart_config = {
        .baud_rate = SERIAL_UART_BAUD_RATE,
        .data_bits = UART_DATA_8_BITS,
        .parity    = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .source_clk = UART_SCLK_DEFAULT,
    };

    esp_err_t err;
    err = uart_param_config(SERIAL_UART_PORT_NUM, &uart_config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "UART param config failed: %s", esp_err_to_name(err));
        return err;
    }

    err = uart_driver_install(SERIAL_UART_PORT_NUM,
                               SERIAL_MAX_LINE_LENGTH * 2, /* RX buffer */
                               SERIAL_MAX_LINE_LENGTH * 2, /* TX buffer */
                               0, NULL, 0);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "UART driver install failed: %s", esp_err_to_name(err));
        return err;
    }

    /* Set up heartbeat timer */
    const esp_timer_create_args_t timer_args = {
        .callback = heartbeat_timer_callback,
        .name = "heartbeat",
    };
    err = esp_timer_create(&timer_args, &s_heartbeat_timer);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "Failed to create heartbeat timer: %s", esp_err_to_name(err));
    }

    ESP_LOGI(TAG, "Serial handler initialised on UART%d at %d baud",
             SERIAL_UART_PORT_NUM, SERIAL_UART_BAUD_RATE);

    return ESP_OK;
}

esp_err_t serial_handler_start(void)
{
    s_running = true;

    /* Create the serial reader task */
    BaseType_t ret = xTaskCreate(serial_task, "serial_handler",
                                  4096, NULL, 5, &s_serial_task_handle);
    if (ret != pdPASS) {
        ESP_LOGE(TAG, "Failed to create serial handler task");
        return ESP_FAIL;
    }

    /* Start heartbeat timer */
    if (s_heartbeat_timer != NULL) {
        esp_timer_start_periodic(s_heartbeat_timer,
                                  SERIAL_HEARTBEAT_INTERVAL_S * 1000000ULL);
        ESP_LOGI(TAG, "Heartbeat timer started (%ds interval)",
                 SERIAL_HEARTBEAT_INTERVAL_S);
    }

    return ESP_OK;
}

void serial_send_response(const char *status, const char *device,
                            const char *state, const char *error_msg)
{
    cJSON *root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "status", status);
    cJSON_AddStringToObject(root, "device", device);
    cJSON_AddStringToObject(root, "state", state);
    if (error_msg != NULL && strlen(error_msg) > 0) {
        cJSON_AddStringToObject(root, "error", error_msg);
    }

    char *json_str = cJSON_PrintUnformatted(root);
    if (json_str != NULL) {
        char line[SERIAL_MAX_LINE_LENGTH];
        snprintf(line, sizeof(line), "RSP:%s\n", json_str);
        uart_write_bytes(SERIAL_UART_PORT_NUM, line, strlen(line));
        ESP_LOGD(TAG, "Sent response: %s", line);
        free(json_str);
    }

    cJSON_Delete(root);
}

void serial_send_heartbeat(void)
{
    cJSON *root = cJSON_CreateObject();
    cJSON *devices_arr = cJSON_CreateArray();

    /* Add all registered devices and their states */
    for (int i = 0; i < device_registry_count(); i++) {
        const device_entry_t *dev = device_registry_get(i);
        if (dev != NULL) {
            cJSON *dev_obj = cJSON_CreateObject();
            cJSON_AddStringToObject(dev_obj, "name", dev->name);
            cJSON_AddStringToObject(dev_obj, "state",
                                     dev->is_on ? "on" : "off");
            cJSON_AddNumberToObject(dev_obj, "brightness", dev->brightness);
            cJSON_AddItemToArray(devices_arr, dev_obj);
        }
    }

    cJSON_AddItemToObject(root, "devices", devices_arr);
    cJSON_AddNumberToObject(root, "timestamp",
                             (double)(esp_timer_get_time() / 1000000ULL));

    char *json_str = cJSON_PrintUnformatted(root);
    if (json_str != NULL) {
        char line[SERIAL_MAX_LINE_LENGTH];
        snprintf(line, sizeof(line), "HBT:%s\n", json_str);
        uart_write_bytes(SERIAL_UART_PORT_NUM, line, strlen(line));
        ESP_LOGD(TAG, "Sent heartbeat: %d devices", device_registry_count());
        free(json_str);
    }

    cJSON_Delete(root);
}

void serial_handler_stop(void)
{
    s_running = false;

    if (s_heartbeat_timer != NULL) {
        esp_timer_stop(s_heartbeat_timer);
        esp_timer_delete(s_heartbeat_timer);
        s_heartbeat_timer = NULL;
    }

    if (s_serial_task_handle != NULL) {
        /* Wait for task to finish */
        vTaskDelay(pdMS_TO_TICKS(200));
        s_serial_task_handle = NULL;
    }

    uart_driver_delete(SERIAL_UART_PORT_NUM);
    ESP_LOGI(TAG, "Serial handler stopped");
}
