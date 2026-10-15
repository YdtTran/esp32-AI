idf_component_register(SRCS "display.c" "display_scene.c" INCLUDE_DIRS "include"
    REQUIRES esp_common
    PRIV_REQUIRES board audio_output esp_driver_gpio esp_driver_spi esp_lcd esp_timer esp_wifi esp_netif)
