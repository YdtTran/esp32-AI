#include "captive_portal.h"
#include "captive_dns.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "lwip/sockets.h"
#include <errno.h>

static void dns_task(void *argument)
{
    int sock = (int)(intptr_t)argument;
    uint8_t query[513], reply[512];
    for (;;) {
        struct sockaddr_in peer;
        socklen_t peer_size = sizeof(peer);
        int received = recvfrom(sock, query, sizeof(query), 0, (struct sockaddr *)&peer, &peer_size);
        if (received < 0) {
            if (errno == EINTR) continue;
            ESP_LOGE("setup_dns", "Receive failed (%d)", errno);
            break;
        }
        /* Bound replies to directly attached setup clients. */
        if ((ntohl(peer.sin_addr.s_addr) & 0xffffff00) != 0xc0a80400) continue;
        size_t length = captive_dns_reply(query, received, reply, sizeof(reply));
        if (length) sendto(sock, reply, length, 0, (struct sockaddr *)&peer, peer_size);
        vTaskDelay(1);
    }
    close(sock);
    vTaskDelete(NULL);
}

esp_err_t captive_portal_dns_start(void)
{
    int sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (sock < 0) return ESP_FAIL;
    struct sockaddr_in local = {
        .sin_family = AF_INET, .sin_port = htons(53),
        .sin_addr.s_addr = inet_addr("192.168.4.1")
    };
    if (bind(sock, (struct sockaddr *)&local, sizeof(local)) != 0) {
        close(sock);
        return ESP_FAIL;
    }
    if (xTaskCreate(dns_task, "setup_dns", 4096, (void *)(intptr_t)sock, 3, NULL) != pdPASS) {
        close(sock);
        return ESP_ERR_NO_MEM;
    }
    ESP_LOGI("setup_dns", "Captive DNS ready on 192.168.4.1:53");
    return ESP_OK;
}
