# ESP32-C6 Matter Bridge Firmware
# For use with ESP-IDF 5.x and ESP-Matter SDK

cmake_minimum_required(VERSION 3.16)

# Set the target chip
set(IDF_TARGET "esp32c6")

# Include ESP-IDF and ESP-Matter components
include($ENV{IDF_PATH}/tools/cmake/project.cmake)

# Include the ESP-Matter SDK
set(EXTRA_COMPONENT_DIRS
    $ENV{ESP_MATTER_PATH}/components
    $ENV{ESP_MATTER_PATH}/device_hal/device
    ${CMAKE_CURRENT_LIST_DIR}/main
)

project(matter_bridge)
