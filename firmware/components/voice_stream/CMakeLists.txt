idf_component_register(SRCS "voice_stream.c" "voice_playback.c" "voice_setup.c" "setup_config.c"
        "captive_dns.c" "captive_portal.c" "portal_address.c"
        "setup_scan.c" "setup_networks.c"
    INCLUDE_DIRS "include" EMBED_TXTFILES "setup.html"
    PRIV_REQUIRES audio_input audio_output display esp_http_client esp_http_server esp_wifi
        esp_event esp_netif esp_system esp_hw_support nvs_flash lwip)
