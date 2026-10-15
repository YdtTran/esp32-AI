idf_component_register(
    SRCS "audio_output.c"
    INCLUDE_DIRS "include"
    REQUIRES esp_common
    PRIV_REQUIRES audio_bus
)
