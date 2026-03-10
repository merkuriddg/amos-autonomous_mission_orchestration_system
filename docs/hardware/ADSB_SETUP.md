# ADS-B Setup Guide — RTL-SDR + dump1090

How to receive live ADS-B aircraft data and feed it into AMOS.

## Hardware Required

- **RTL-SDR dongle** (RTL2832U chipset) — ~$30
- **1090 MHz antenna** — the stock whip antenna works poorly at 1090 MHz; a dedicated ADS-B antenna greatly improves range
  - FlightAware 1090 MHz antenna (~$15)
  - DIY quarter-wave ground plane (6.9 cm element)
- USB extension cable (optional — keeps RF noise from the laptop away from the dongle)

## Software Setup (macOS)

### 1. Install librtlsdr dependency

```bash
brew install librtlsdr
```

### 2. Build dump1090 (FlightAware fork)

```bash
git clone https://github.com/flightaware/dump1090.git /tmp/dump1090
cd /tmp/dump1090 && make
```

### 3. Run dump1090

Basic interactive mode with network output:

```bash
/tmp/dump1090/dump1090 --net --interactive
```

With gain tuning (try different values: -10 = auto, or 20-50):

```bash
/tmp/dump1090/dump1090 --net --interactive --gain -10
```

Force a specific device (if multiple SDRs connected):

```bash
/tmp/dump1090/dump1090 --net --interactive --device-index 0
```

### 4. Verify it's working

You should see a table of aircraft in the terminal with ICAO hex codes, callsigns, altitude, speed, etc. If the table is empty:

- Make sure the antenna is connected
- Try increasing gain: `--gain 40`
- Plug the dongle directly into the laptop (not through a hub)
- Make sure no other SDR software is using the dongle
- Check `brew install librtlsdr && rtl_test` to verify the dongle is detected

### Network ports (opened by `--net`)

| Port  | Protocol | Description |
|-------|----------|-------------|
| 30001 | Raw      | Raw Mode S output |
| 30002 | Raw      | Raw Mode S input |
| 30003 | SBS      | SBS BaseStation format (CSV text) |
| 30005 | Beast    | Beast binary format |

**Note:** The FlightAware fork does NOT include the built-in HTTP/JSON server on port 8080. Use SBS (30003) or Beast (30005) for AMOS.

## Connect to AMOS

1. Start dump1090 (see above)
2. Open AMOS → **Integrations** page
3. In the **ADS-B** card:
   - Host: `localhost`
   - Port: `30003`
   - Mode: **SBS**
4. Click **CONNECT**
5. The status dot turns green and aircraft count updates every 5 seconds

### Verify via API

```bash
# Check connection status
curl http://localhost:2600/api/v1/bridge/adsb/status

# Get tracked aircraft
curl http://localhost:2600/api/v1/bridge/adsb/tracks
```

## Tips for St Pete Beach / Tampa Bay Area

- **PIE** (St. Pete-Clearwater Intl) is ~10 miles north
- **TPA** (Tampa Intl) is ~20 miles northeast
- **MCF** (MacDill AFB) is ~15 miles east
- Aircraft at cruise altitude (30,000+ ft) can be received 100+ miles away
- Low-altitude traffic needs line-of-sight — put the antenna near a window or outside
- A dedicated 1090 MHz antenna on a rooftop or balcony will pick up 50-200+ aircraft easily

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "No supported devices found" | Dongle not detected — try different USB port, `brew install librtlsdr && rtl_test` |
| Table empty | Antenna issue or gain too low — try `--gain 40` or `--gain -10` (auto) |
| "device busy" | Another app using the dongle — close SDR#, CubicSDR, etc. |
| AMOS shows 0 aircraft | dump1090 not running, or wrong port/mode in AMOS |
| Intermittent drops | USB power issue — use a powered hub or direct connection |

## Alternative: readsb

For a more maintained decoder:

```bash
git clone https://github.com/wiedehopf/readsb.git /tmp/readsb
cd /tmp/readsb && make
/tmp/readsb/readsb --net --interactive
```

Same ports and AMOS connection procedure.
