/**
 * @file serial_handler.h
 * @brief Serial command handler for Pi <-> ESP32-C6 communication.
 *
 * Protocol:
 *   Pi -> ESP32:  CMD:{"device":"living_room_light","action":"on"}\n
 *   ESP32 -> Pi:  RSP:{"status":"ok","device":"living_room_light","state":"on"}\n
 *   ESP32 -> Pi:  HBT:{"devices":[...],"timestamp":...}\n
 */

#ifndef SERIAL_HANDLER_H
#define SERIAL_HANDLER_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** Maximum length of a serial command/response line. */
#define SERIAL_MAX_LINE_LENGTH 512

/** UART port number used for Pi communication. */
#define SERIAL_UART_PORT_NUM 0

/** UART baud rate. */
#define SERIAL_UART_BAUD_RATE 115200

/** Heartbeat interval in seconds. */
#define SERIAL_HEARTBEAT_INTERVAL_S 10

/**
 * Parsed command structure received from the Raspberry Pi.
 */
typedef struct {
    char device[64];     /**< Target device name */
    char action[32];     /**< Action to perform (on, off, brightness, color) */
    char value[32];      /**< Optional value parameter */
    bool has_value;      /**< Whether the value field is populated */
} serial_command_t;

/**
 * Callback type for received commands.
 *
 * @param cmd Pointer to the parsed command structure.
 * @return true if the command was executed successfully.
 */
typedef bool (*serial_cmd_callback_t)(const serial_command_t *cmd);

/**
 * Initialise the serial handler.
 *
 * Sets up UART0 for communication with the Raspberry Pi.
 *
 * @param cmd_callback Function to call when a command is received.
 * @return ESP_OK on success.
 */
esp_err_t serial_handler_init(serial_cmd_callback_t cmd_callback);

/**
 * Start the serial handler task.
 *
 * Launches a FreeRTOS task that continuously reads from UART
 * and dispatches received commands.
 *
 * @return ESP_OK on success.
 */
esp_err_t serial_handler_start(void);

/**
 * Send a response back to the Raspberry Pi.
 *
 * @param status "ok" or "error"
 * @param device Device name
 * @param state Current device state
 * @param error_msg Optional error message (NULL if no error)
 */
void serial_send_response(const char *status, const char *device,
                           const char *state, const char *error_msg);

/**
 * Send a heartbeat message to the Raspberry Pi.
 *
 * Includes the current state of all registered devices.
 */
void serial_send_heartbeat(void);

/**
 * Stop the serial handler and free resources.
 */
void serial_handler_stop(void);

#ifdef __cplusplus
}
#endif

#endif /* SERIAL_HANDLER_H */
