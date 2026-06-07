"""Network mapping + WiGLE export tests."""


def test_record_network_new_then_duplicate(temp_db):
    assert temp_db.record_network("AA:BB:CC:DD:EE:FF", "Net", "WPA2", 6, -50) is True
    # same BSSID, different case + stronger RSSI -> not new, merged
    assert temp_db.record_network("aa:bb:cc:dd:ee:ff", "Net", "WPA2", 6, -40) is False
    assert temp_db.count_networks() == 1
    n = temp_db.get_networks()[0]
    assert n["times_seen"] == 2
    assert n["best_rssi"] == -40  # keeps the strongest signal


def test_record_network_blank_bssid(temp_db):
    assert temp_db.record_network("") is False
    assert temp_db.count_networks() == 0


def test_record_connection_dedupe(temp_db):
    assert temp_db.record_connection("Home", "AA:BB:CC:DD:EE:FF") is True
    assert temp_db.record_connection("Home") is False        # same network
    assert temp_db.record_connection("Cafe") is True         # new network
    rows = temp_db.get_connections()
    assert len(rows) == 2


def test_wigle_csv_format(temp_db):
    temp_db.record_network("AA:BB:CC:DD:EE:FF", "My,Net", "WPA2", 6, -50)
    temp_db.record_network("11:22:33:44:55:66", "OpenCafe", None, 11, -70)
    lines = temp_db.wigle_csv().strip().split("\n")
    assert lines[0].startswith("WigleWifi-1.4")
    assert lines[1].startswith("MAC,SSID,AuthMode,FirstSeen,Channel,RSSI")
    body = "\n".join(lines[2:])
    assert "AA:BB:CC:DD:EE:FF" in body
    assert '"My,Net"' in body          # comma SSID gets quoted
    assert "[WPA2][ESS]" in body
    assert "[OPEN][ESS]" in body       # no security -> OPEN
    assert "WIFI" in body
