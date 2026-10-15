idf_component_register(
    SRCS "app_main.c"
    INCLUDE_DIRS "."
    PRIV_REQUIRES
        log
        audio_input
        audio_output
        nvs_flash
        voice_stream
        display
)
