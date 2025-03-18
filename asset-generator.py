import json
import random
import uuid
import datetime
import geojson

def generate_network_asset_data(num_devices=20, num_locations=5, num_software=30, num_connections=30, num_runs_on=40, num_config_changes=5):
    locations = []
    devices = []
    software = []
    connections = []
    runs_ons = []

    # Real Locations with GeoJSON
    locations_data = [
        {"name": "New York Data Center", "address": "123 Broadway, New York, NY", "lat": 40.7128, "lon": -74.0060},
        {"name": "London Office", "address": "456 Oxford St, London", "lat": 51.5074, "lon": -0.1278},
        {"name": "Tokyo HQ", "address": "789 Ginza, Tokyo", "lat": 35.6895, "lon": 139.6917},
        {"name": "Sydney Warehouse", "address": "101 George St, Sydney", "lat": -33.8688, "lon": 151.2093},
        {"name": "Frankfurt Cloud Region", "address": "222 Mainzer Landstr, Frankfurt", "lat": 50.1109, "lon": 8.6821}
    ]

    for i, loc_data in enumerate(locations_data):
        location = {
            "_key": f"location{i+1}",
            "name": loc_data["name"],
            "address": loc_data["address"],
            "geojson": geojson.Point((loc_data["lon"], loc_data["lat"]))
        }
        locations.append(location)

    # Devices (with real OS and configuration history)
    device_types = ["server", "router", "laptop", "IoT", "firewall"]
    os_versions = {
        "server": ["CentOS 7.9.2009", "Ubuntu 20.04.3 LTS", "Windows Server 2019 Datacenter"],
        "router": ["IOS XE 17.6.4a", "JUNOS 21.2R3-S1"],
        "laptop": ["Windows 10 Pro 21H2", "macOS Monterey 12.4", "Ubuntu 22.04 LTS"],
        "IoT": ["Embedded Linux 4.14.247", "FreeRTOS 10.4.6"],
        "firewall": ["FortiOS 7.0.9", "pfSense 2.5.2"]
    }

    for i in range(num_devices):
        device_type = random.choice(device_types)
        os_version = random.choice(os_versions[device_type])
        device = {
            "_key": f"device{i+1}",
            "type": device_type,
            "model": f"{device_type.capitalize()} Model {random.randint(100, 999)}",
            "serialNumber": str(uuid.uuid4()),
            "ipAddress": f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}",
            "macAddress": ":".join(f"{random.randint(0, 255):02x}" for _ in range(6)),
            "os": os_version.split(" ")[0],
            "osVersion": os_version,
            "locationId": random.choice(locations)["_key"],
            "configurationHistory": []
        }
        devices.append(device)

        # Generate configuration history
        current_config = {"hostname": f"device{i+1}", "firewallRules": ["allow 80", "allow 443"], "timestamp": datetime.datetime.now().isoformat()}
        device["configurationHistory"].append(current_config)

        for _ in range(num_config_changes):
            change_time = datetime.datetime.now() + datetime.timedelta(days=random.randint(1, 30))
            new_config = current_config.copy()
            if random.random() < 0.5:
                # Add/remove firewall rule
                if random.random() < 0.5:
                    new_config["firewallRules"].append(f"allow {random.randint(1000, 9000)}")
                else:
                    if len(new_config["firewallRules"]) > 0:
                        new_config["firewallRules"].pop(random.randint(0, len(new_config["firewallRules"]) - 1))
            else:
                # Change hostname
                new_config["hostname"] = f"new-device-{random.randint(100, 999)}"
            new_config["timestamp"] = change_time.isoformat()
            device["configurationHistory"].append(new_config)
            current_config = new_config

    # Software (with real software versions and configuration history)
    software_types = ["application", "database", "service"]
    software_versions = {
        "application": ["Apache HTTP Server 2.4.53", "Nginx 1.22.0", "Python 3.10.6"],
        "database": ["MySQL 8.0.30", "PostgreSQL 14.5", "MongoDB 6.0.2"],
        "service": ["OpenSSH 8.9p1", "Docker 20.10.17", "Kubernetes 1.25.2"]
    }

    for i in range(num_software):
        software_type = random.choice(software_types)
        software_version = random.choice(software_versions[software_type])
        soft = {
            "_key": f"software{i+1}",
            "name": software_version.split(" ")[0],
            "type": software_type,
            "softwareVersion": software_version,
            "configurationHistory": []
        }
        software.append(soft)

        # Generate software configuration history
        current_config = {"port": random.randint(8000, 9000), "enabled": True, "timestamp": datetime.datetime.now().isoformat()}
        soft["configurationHistory"].append(current_config)

        for _ in range(num_config_changes):
            change_time = datetime.datetime.now() + datetime.timedelta(days=random.randint(1, 30))
            new_config = current_config.copy()
            if random.random() < 0.5:
                new_config["port"] = random.randint(8000, 9000)
            else:
                new_config["enabled"] = not new_config["enabled"]
            new_config["timestamp"] = change_time.isoformat()
            soft["configurationHistory"].append(new_config)
            current_config = new_config

    # Connections and RunsOn (unchanged)
    for i in range(num_connections):
        connection = {
            "_key": f"connection{i+1}",
            "_from": random.choice(devices)["_key"],
            "_to": random.choice(devices)["_key"],
            "type": random.choice(["ethernet", "wifi", "fiber"]),
            "bandwidth": f"{random.randint(10, 1000)}Mbps",
            "latency": f"{random.randint(1, 10)}ms"
        }
        connections.append(connection)

    for i in range(num_runs_on):
        runs_on = {
            "_key": f"runsOn{i+1}",
            "_from": random.choice(devices)["_key"],
            "_to": random.choice(software)["_key"]
        }
        runs_ons.append(runs_on)

    # Write to separate JSON files
    with open("./data/locations.json", "w") as f:
        json.dump(locations, f, indent=2, default=lambda o: geojson.dumps(o) if isinstance(o, geojson.geometry.Geometry) else o)
    with open("./data/devices.json", "w") as f:
        json.dump(devices, f, indent=2)
    with open("./data/software.json", "w") as f:
        json.dump(software, f, indent=2)
    with open("./data/connections.json", "w") as f:
        json.dump(connections, f, indent=2)
    with open("./data/runs_on.json", "w") as f:
        json.dump(runs_on, f, indent=2)

if __name__ == "__main__":
    asset_data = generate_network_asset_data()
    with open("network_assets.json", "w") as f:
        json.dump(asset_data, f, indent=2, default=lambda o: geojson.dumps(o) if isinstance(o, geojson.geometry.Geometry) else o)
    print("Data generated and saved to network_assets.json")