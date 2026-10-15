idf_component_register(
    SRCS "audio_bus.c"
    INCLUDE_DIRS "include"
    REQUIRES esp_common
    PRIV_REQUIRES board esp_driver_i2s
)
