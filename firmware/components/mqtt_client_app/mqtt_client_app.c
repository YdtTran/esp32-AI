#include "mqtt_client_app.h"
#include "esp_log.h"
#include "mqtt_client.h"
#include "mqtt_client_app.h"
#include <stdio.h>

#define MQTT_BROKER_URI "mqtt://192.168.1.4:1883"
#define DEVICE_TOKEN "REPLACE_WITH_DEVICE_TOKEN"

const static char* TAG = "MQTT_CLIENT_APP";


static void
mqtt_event_handler (void* handler_args, esp_event_base_t base, int32_t event_id, void* event_data) {
	ESP_LOGI (TAG, "Event: %d", event_id);

	esp_mqtt_event_handle_t event	= event_data;
	esp_mqtt_client_handle_t client = event->client;

	switch (event_id) {
	case MQTT_EVENT_CONNECTED:
		/* code */
		ESP_LOGI (TAG, "MQTT_EVENT_CONNECTED");

		esp_mqtt_client_publish (client, "v1/devices/me/telemetry",
		"{\"temperature\":25.5,\"status\":\"online\"}", 0, 1, 0);

		esp_mqtt_client_subscribe (client, "v1/devices/me/rpc/request/+", 1);
		break;

	case MQTT_EVENT_DATA:
		ESP_LOGI (TAG, "Received: %.*s", event->data_len, event->data);
		break;

	case MQTT_EVENT_DISCONNECTED: ESP_LOGW (TAG, "Disconnected"); break;

	default: break;
	}
}

esp_err_t mqtt_app_start (void) {
	esp_mqtt_client_config_t mqtt_cfg = {
		.broker.address.uri	  = MQTT_BROKER_URI,
		.credentials.username = DEVICE_TOKEN,
	};

	esp_mqtt_client_handle_t client = esp_mqtt_client_init (&mqtt_cfg);

	ESP_ERROR_CHECK (esp_mqtt_client_register_event (
	client, ESP_EVENT_ANY_ID, mqtt_event_handler, NULL));

	return esp_mqtt_client_start (client);
}