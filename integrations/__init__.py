"""AMOS Integration Bridges

Platform bridges for connecting AMOS to real hardware and systems:

Air Domain:
  - px4_bridge       : PX4 autopilot (drones via MAVLink)
  - ardupilot_bridge : ArduPilot autopilot (drones/rovers via MAVLink)
  - adsb_receiver    : ADS-B aircraft surveillance (dump1090/readsb)
  - remoteid_bridge  : FAA RemoteID drone identification

Maritime Domain:
  - moos_bridge      : MOOS-IvP for autonomous marine vehicles
  - ais_receiver     : AIS vessel tracking
  - nmea_bridge      : NMEA 0183 marine electronics / GPS

Ground Domain:
  - ros2_integration : Full ROS 2 Humble pub/sub integration
  - nav2_bridge      : ROS 2 Navigation2 stack for ground UGVs

Comms & Tactical:
  - tak_bridge       : TAK (Android Team Awareness Kit) CoT feed
  - link16_sim       : Link-16 tactical data link simulator
  - aprs_bridge      : APRS amateur radio position/messaging
  - lora_bridge      : LoRa / Meshtastic mesh networking
  - sdr_bridge       : Software-Defined Radio (GNU Radio / HackRF)

SDR Platform:
  - dragonos_bridge  : DragonOS / WarDragon SDR (MQTT + Kismet)

ISR Metadata:
  - zmeta_bridge     : ZMeta v1.0 ISR metadata standard (UDP ingest + egress)

Data Transport:
  - mqtt_adapter     : MQTT pub/sub
  - dds_adapter      : DDS (Data Distribution Service)
  - kafka_adapter    : Apache Kafka streaming

Standards:
  - stanag4586_adapter : STANAG 4586 UAV interoperability
  - nffi_adapter       : NATO Friendly Force Information
  - vmf_adapter        : Variable Message Format
  - ogc_client         : OGC WMS/WFS geospatial services
"""
