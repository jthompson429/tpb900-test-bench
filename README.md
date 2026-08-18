# TPB9000 Test Bench

A deliberately small, safety-focused Raspberry Pi application for repeatedly exercising the TPB9000 feeder-cover motor and mechanism. It is a bench fixture, not production feeder firmware. It provides limit-aware manual jogging, automated close/open cycles, travel-time logging, timeouts, summaries, and safe shutdown.

> **Do not connect the mechanism until the direction-selective hardware interlocks described below have been built and tested.** Raspberry Pi GPIO and this program are secondary protection only.

## Decisions that still require confirmation

The pin map below is a documented initial assignment, not a claim about an already-wired bench. Before hookup, confirm:

1. The exact IBT-2 board/schematic and its logic input-high specification. BTS7960 IC limits do not establish the behavior of every low-cost module or clone. If 3.3 V is not guaranteed as HIGH, use a 3.3-to-5 V non-inverting buffer such as a 74AHCT125 powered at 5 V. Do not use an inverting level shifter unless the logic is redesigned and tested.
2. Whether R_EN/L_EN on the actual module independently inhibit the matching bridge direction. Many IBT-2 boards expose two half-bridge enables, but they must not be assumed to provide a simple direction-selective safety function.
3. The limit-switch contact rating and the selected hard-interlock circuit. The small switch contacts should not interrupt motor current unless explicitly rated for the motor's DC stall current and inductive load.
4. Motor normal and stall current at 12 V, wire gauge, supply rating, and the actual module's credible continuous-current capability. The “43 A” marketing number is not a safe continuous design value without thermal validation.
5. Final OPEN/CLOSE polarity after the electronics-only test. `open_uses_rpwm` is deliberately configurable.

## Safety architecture

Two independent layers are required:

- **Primary hardware layer:** each normally-closed (NC) endpoint switch removes permission for motion farther into that endpoint, while the opposite direction remains possible. This must work with the Pi unplugged or frozen and a control signal stuck on.
- **Secondary software layer:** separate switch contacts (preferably DPDT switches, or safety-rated relays/isolated sensing) feed GPIO status. Software stops PWM, disables both enable outputs, detects impossible states, and applies travel timeouts.

An NC switch wired only between GPIO and ground is fail-aware sensing, **not** a hard motor interlock. Also, simply putting one NC switch in series with the motor blocks both directions at the endpoint. A correct reversible-DC design needs direction-selective inhibit logic. Recommended implementation: have an electrician/electronics designer produce a small interlock using DPDT endpoint switches or appropriately rated interposing relays/logic gates that gate the CLOSE and OPEN command paths separately. Validate it on the exact IBT-2: hold each endpoint switch active and deliberately command both directions, including with a simulated stuck GPIO.

```text
Pi GPIO commands     level buffer if needed      hardware permission gates
 RPWM/L_PWM  ------>  3.3 V -> valid HIGH  ----> OPEN_NC / CLOSED_NC ----> IBT-2 inputs
 R_EN/L_EN  ------->  (fail OFF on Pi reset)  --------------------------> enables

Endpoint switches (second NC pole or isolated auxiliary contact)
 OPEN_NC   ---- GPIO5 with pull-up       (open wire/contact => active)
 CLOSED_NC ---- GPIO6 with pull-up       (open wire/contact => active)

12 V supply -- correctly sized fuse -- master E-stop/isolator -- IBT-2 B+/B-
IBT-2 M+/M- ---------------------------------------------------- motor
Pi GND --------------------------------------------------------- IBT-2 logic GND
```

A mushroom emergency-stop/master isolator that physically removes motor power is strongly recommended. Fuse the 12 V branch near the source. Select a DC-rated fuse above measured normal running current but below the safe ampacity of the smallest wire/component; starting/stall current and fuse time-delay must be measured before choosing a final value. Never fuse by guessing from average current. Keep Pi power stable when the E-stop removes motor power if status visibility is desired. Add appropriate suppression/decoupling per the driver and supply documentation, route motor wiring away from switch/GPIO wiring, and use a common logic ground unless galvanic isolation is deliberately designed.

## GPIO map (BCM numbering)

| Function | BCM GPIO | Header pin | Direction | Startup/safe state |
|---|---:|---:|---|---|
| RPWM | 18 | 12 | output/PWM | LOW |
| LPWM | 19 | 35 | output/PWM | LOW |
| R_EN | 23 | 16 | output | LOW/disabled |
| L_EN | 24 | 18 | output | LOW/disabled |
| OPEN limit sense | 5 | 29 | input, pull-up | NC to GND; open = active |
| CLOSED limit sense | 6 | 31 | input, pull-up | NC to GND; open = active |
| Logic ground | — | 6 (example) | — | common with IBT-2 logic GND |
| IBT-2 VCC | — | Pi 5 V pin 2 or regulated logic 5 V | power | verify module current/spec |

GPIO numbers are configured in `config/testbench.yaml`. R_IS/L_IS are unused in version 1; insulate them. Never put 5 V onto a Pi GPIO. Pi header pin numbering and BCM numbering are different.

## Project layout

```text
config/testbench.yaml       operator settings and pin map
src/tpb9000_testbench/      CLI, controller, GPIO adapter, reports
tests/                      hardware-independent unit tests
logs/                       timestamped logs and JSON summaries
scripts/install.sh          repeatable virtual-environment install
```

## Fresh Raspberry Pi setup

Use Raspberry Pi Imager to install current Raspberry Pi OS, set hostname `TPB9000-test-bench`, user `pi`, Wi-Fi `Trash Panda Blocker 9000`, and enable SSH. A DHCP reservation for `192.168.20.203` is preferable to configuring a duplicate-prone static address on the Pi.

```bash
sudo apt update
sudo apt install -y git python3-venv
git clone https://github.com/jthompson429/tpb9000-test-bench.git
cd tpb9000-test-bench
chmod +x scripts/install.sh
./scripts/install.sh
.venv/bin/tpb9000-testbench status
```

The application does not start at boot and never moves on startup. It initializes outputs OFF, reports status, and only moves for an explicit command. Run it from the repository root so the default config path resolves correctly. No root login should normally be needed on current Raspberry Pi OS when GPIO permissions are configured normally.

## Commands

```bash
.venv/bin/tpb9000-testbench status
.venv/bin/tpb9000-testbench jog-open --seconds 1
.venv/bin/tpb9000-testbench jog-close --seconds 1
.venv/bin/tpb9000-testbench test
.venv/bin/tpb9000-testbench test --cycles 100
```

Jog commands stop at the relevant limit or requested/configured safety time. Start with sub-second/one-second jogs while watching the mechanism. A jog safety-timeout is reported as an error because reaching an endpoint is the only normal movement completion. `Ctrl+C` and SIGTERM immediately request STOP; every command also disables PWM/enables in `finally` cleanup. A failed or aborted test exits and cannot auto-resume. Starting again requires a new operator command.

Configuration defaults are 25 cycles, 20-second endpoint pauses, 30-second close/open travel timeouts, a 5-second maximum jog, 20 ms polling, and 65% PWM. Tune PWM only after measuring reliable starting torque and checking driver/motor heating.

Full logs and `*-summary.json` files appear in `logs/`. The summary contains cycle counts, total duration, min/mean/max travel times in both directions, final result, and fault reason.

## Commissioning

### Stage 1 — electronics only

Disconnect the motor from the mechanism. Put the fused 12 V supply behind a physical isolator/E-stop. Confirm outputs remain off at boot and on `status`; verify OPEN and CLOSE polarity with brief jogs; verify STOP and Ctrl+C. Operate each limit by hand: it must block only motion farther into that limit and permit motion away. Repeat with the relevant Pi command deliberately held/stuck to prove the hardware layer is authoritative. Confirm a disconnected limit-sense wire reports active/fault-safe.

### Stage 2 — mechanical jogging

Connect the mechanism and use only short manual jogs. Confirm coupling concentricity, smooth lead-screw/carriage travel, limit activation before hard stops, protected wiring/cable-carrier travel, mesh tracking, and correct direction labels. Reposition switches as needed with motor power isolated.

### Stage 3 — 25 cycles

Run `test --cycles 25`, then isolate power and inspect fasteners, motor/driver temperature, coupling, screw, guides, switch mounts, wiring, carrier, mesh, leading edge, and feeder contact points. Review travel-time spread/trend.

### Stage 4 — 100 cycles

Repeat the inspection and travel-time review after 100 cycles.

### Stage 5 — extended endurance

Only after earlier stages pass, increase to several hundred cycles. Do not leave an uncommissioned fixture unattended.

## Troubleshooting and safe shutdown

- **Both limits active:** motor remains off. Check switch adjustment, NC/NO terminal selection, broken wires, and `active_low` configuration. Do not bypass the fault in code.
- **Direction reversed:** isolate motor power, verify wiring, then change `open_uses_rpwm`; repeat Stage 1.
- **Limit shown active while released:** verify the NC common/contact terminals and GPIO-to-ground sense wiring. With the documented NC scheme, an open circuit intentionally reads active.
- **Timeout:** inspect binding, coupling, power, fuse, hard-interlock state, switch wiring, and travel-time configuration. A timeout is a fault, not a reason to increase it blindly.
- **Pi resets/noisy limits:** inspect common ground, supply separation, motor suppression, cable routing, shielding, and decoupling.
- **No GPIO access:** confirm the virtual environment includes `gpiozero`, the OS GPIO packages/permissions, and that no other process owns the pins.

To stop, press Ctrl+C, verify the CLI exits and motor is stopped, then open the physical 12 V isolator/E-stop before touching the mechanism. Shut down the Pi with `sudo shutdown -h now`; wait for activity to cease before removing Pi power. The physical motor isolator remains the authoritative safe state.

## Development verification

Tests do not require Raspberry Pi hardware:

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/pytest
```

The fake hardware tests cover config validation, target-limit stopping, timeout cleanup, impossible dual-limit failure, and a complete close/open cycle. Final acceptance still requires the staged physical commissioning above.
