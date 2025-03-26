import json
import random
import uuid
import datetime
import geojson
import sys

def notExpiredValue():
    """returns value to be as the default very large integer to be used for the expired property"""
    return sys.maxsize

def generateLocations(num_locations=5):
    """Generate Real Locations with GeoJSON and store in Location.json."""
    locations = []
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
            "location": geojson.Point((loc_data["lon"], loc_data["lat"]))
        }
        locations.append(location)
    with open("./data/Location.json", "w") as f:
        json.dump(locations, f, indent=2, default=lambda o: geojson.dumps(o) if isinstance(o, geojson.geometry.Geometry) else o)
    return locations

def generateDevices(locations, num_devices=20,num_config_changes=5):
    """Generate device data and store in Device.json."""
    devices = []
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
        model = f"{device_type.capitalize()} Model {random.randint(100, 999)}"
        device = {
            "_key": f"device{i+1}",
            "name" : device_type+" "+model,
            "type": device_type,
            "model": model,
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
        current_config = {"hostname": f"device{i+1}", "firewallRules": ["allow 80", "allow 443"], "created": datetime.datetime.now().timestamp(), "expired": notExpiredValue()}
        device["configurationHistory"].append(current_config)
        for changeNo in range(num_config_changes):
            created = datetime.datetime.now() - datetime.timedelta(days=random.randint(changeNo*5+1, (changeNo+1)*5))
            previous_config = current_config.copy()
            if random.random() < 0.5:
                # Add/remove firewall rule
                if random.random() < 0.5:
                    previous_config["firewallRules"].append(f"allow {random.randint(1000, 9000)}")
                else:
                    if len(previous_config["firewallRules"]) > 0:
                        previous_config["firewallRules"].pop(random.randint(0, len(previous_config["firewallRules"]) - 1))
            else:
                # Change hostname
                previous_config["hostname"] = f"new-device-{random.randint(100, 999)}"
            expired = previous_config["created"]
            previous_config["expired"] = expired
            previous_config["created"] = created.timestamp()
            device["configurationHistory"].append(previous_config)
            current_config = previous_config
    with open("./data/Device.json", "w") as f:
        json.dump(devices, f, indent=2)
    return devices

def generateHasLocation(devices):
    """Generate hasLocation edge data and store in hasLocation.json."""
    hasLocations = []
    # Connections 
    for device in devices:
        _from = "Device/"+device["_key"]
        _to = "Location/"+device["locationId"]
        hasLocation = {
            "_key": f"hasLocation{len(hasLocations) + 1}",
            "_from": _from,
            "_to": _to,
            "created" : datetime.datetime.now().timestamp(),
            "expired": notExpiredValue()
        }
        hasLocations.append(hasLocation)
    with open("./data/hasLocation.json", "w") as f:
        json.dump(hasLocations, f, indent=2)
    return hasLocations

def generateSoftware(num_software=30, num_config_changes=5):
    """Generate software data and store in Software.json."""
    software = []
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
        current_config = {"port": random.randint(8000, 9000), "enabled": True, "created": datetime.datetime.now().timestamp(), "expired": notExpiredValue()}
        soft["configurationHistory"].append(current_config)
        for changeNo in range(num_config_changes):
            created = datetime.datetime.now() - datetime.timedelta(days=random.randint(changeNo*5+1, (changeNo+1)*5))
            previous_config = current_config.copy()
            if random.random() < 0.5:
                previous_config["port"] = random.randint(8000, 9000)
            else:
                previous_config["enabled"] = not previous_config["enabled"]
            expired = previous_config["created"]
            previous_config["expired"] = expired
            previous_config["created"] = created.timestamp()
            soft["configurationHistory"].append(previous_config)
            current_config = previous_config

    with open("./data/Software.json", "w") as f:
        json.dump(software, f, indent=2)
    return software

def generateConnections(devices,num_connections=30):
    """Generate connection data and store in connection.json."""
    connections = []
    # Connections 
    while len(connections) < num_connections:
        _from = "Device/"+random.choice(devices)["_key"]
        _to = "Device/"+random.choice(devices)["_key"]
        if _from != _to: # prevent self loops
            connection = {
                # "_key": f"connection{i+1}",
                "_key": f"connection{len(connections) + 1}",
                "_from": _from,
                "_to": _to,
                "type": random.choice(["ethernet", "wifi", "fiber"]),
                "bandwidth": f"{random.randint(10, 1000)}Mbps",
                "latency": f"{random.randint(1, 10)}ms",
                "created" : datetime.datetime.now().timestamp(),
                "expired": notExpiredValue()
            }
            connections.append(connection)
    with open("./data/hasConnection.json", "w") as f:
        json.dump(connections, f, indent=2)
    return connections

def generateHasSoftware(devices, software, num_hasSoftware=40):
    """Generate hasSoftware edge data and store in hasSoftware.json."""
    hasSoftwares = []
    while len(hasSoftwares) < num_hasSoftware:
        device = random.choice(devices)
        if device["type"] != "router":
            _from = "Device/"+device["_key"]
            hasSoftware = {
                "_key": f"hasSoftware{len(hasSoftwares) + 1}",
                "_from": _from,
                "_to": "Software/"+random.choice(software)["_key"],
                "created" : datetime.datetime.now().timestamp(),
                "expired": notExpiredValue()
            }
            hasSoftwares.append(hasSoftware)
    with open("./data/hasSoftware.json", "w") as f:
        json.dump(hasSoftwares, f, indent=2)
    return hasSoftwares

def generate_network_asset_data(num_devices=20, num_locations=5, num_software=30, num_connections=30, num_hasSoftware=40, num_config_changes=5):
    """Generate network asset data and store in individual vertex and edge .json files"""
    locations = generateLocations(num_locations)
    devices = generateDevices(locations, num_devices=num_devices, num_config_changes=num_config_changes)
    software = generateSoftware(num_software=num_software, num_config_changes=num_config_changes)
    connections = generateConnections(devices, num_connections=30)
    hasSoftware = generateHasSoftware(devices, software, num_hasSoftware=num_hasSoftware)
    hasLocation = generateHasLocation(devices)

def main():
    """Generates data and stores in separate JSON files."""
    generate_network_asset_data(num_devices=20, num_locations=5, num_software=30, num_connections=30, num_hasSoftware=40, num_config_changes=5)

if __name__ == "__main__":
    main()