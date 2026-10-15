"""Opt-in device check. Join the ESP32 setup Wi-Fi before running this script.

Uses no credentials and never saves settings. No Wi-Fi/profile changes are made.
Run from firmware/: python tests/probe_captive_portal.py
"""
import http.client
import json
import socket
import struct
import time

AP = "192.168.4.1"
URL = f"http://{AP}/"


def request(method, path, host=AP, origin=None, body=None):
    headers = {"Host": host}
    if origin:
        headers["Origin"] = origin
    if body is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    connection = http.client.HTTPConnection(AP, timeout=3)
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        return response.status, response.getheader("Location"), response.read()
    finally:
        connection.close()


def main():
    name = b"\x03www\x0fmsftconnecttest\x03com\x00"
    for kind in (1, 28):
        query = struct.pack("!6H", 0x9876, 0x100, 1, 0, 0, 0) + name + struct.pack("!2H", kind, 1)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(3)
            client.sendto(query, (AP, 53))
            reply, source = client.recvfrom(512)
        assert source[0] == AP and reply[:2] == query[:2]
        assert struct.unpack("!H", reply[6:8])[0] == (1 if kind == 1 else 0)
        if kind == 1:
            assert reply[-4:] == socket.inet_aton(AP)
    print("PASS DNS: wildcard A points to AP; AAAA has no invalid IPv6 answer")

    probes = (
        ("www.msftconnecttest.com", "/connecttest.txt"),
        ("www.msftconnecttest.com", "/redirect"),
        ("www.msftncsi.com", "/ncsi.txt"),
        ("connectivitycheck.gstatic.com", "/generate_204"),
        ("captive.apple.com", "/hotspot-detect.html"),
        ("example.com", "/"),
    )
    for host, path in probes:
        status, location, content = request("GET", path, host)
        assert status == 302 and location == URL and content, (host, path, status, location)
    print("PASS HTTP: Windows/Android/Apple probes redirect to canonical setup URL")

    status, _, content = request("GET", "/")
    assert status == 200 and all(field in content for field in (b'name="ssid"', b'name="password"', b'name="pc"'))
    status, _, content = request("GET", "/captive-portal")
    assert status == 200 and json.loads(content) == {"captive": True, "user-portal-url": URL}
    print("PASS page: setup fields and captive API served")

    status, _, content = request("GET", "/networks?refresh=1")
    assert status == 200
    networks = json.loads(content)
    for _ in range(12):
        if not networks["scanning"]:
            break
        time.sleep(1)
        status, _, content = request("GET", "/networks")
        assert status == 200
        networks = json.loads(content)
    assert not networks["scanning"] and not networks["error"], networks
    assert len(networks["networks"]) <= 16
    for item in networks["networks"]:
        assert isinstance(item["ssid"], str) and 1 <= len(item["ssid"].encode("utf-8")) <= 32
        assert isinstance(item["rssi"], int) and isinstance(item["supported"], bool)
    print("PASS scan: background scan returned", len(networks["networks"]), "networks without blocking the portal")

    assert request("POST", "/save", host="example.com", body=b"bad=request")[0] == 403
    assert request("POST", "/save", origin="http://example.com", body=b"bad=request")[0] == 403
    assert request("POST", "/save", body=b"bad=request")[0] == 400
    print("PASS writes: foreign Host/Origin and malformed forms rejected; no settings saved")


if __name__ == "__main__":
    main()
