from __future__ import annotations

from sqlmodel import Session, select
from app.models.triage_rule import TriageRule


def _rules() -> list[dict]:
    return [
        # =========================
        # STALL / START / IDLE
        # =========================
        {
            "name": "Stalls at stop / dies when braking to a stop",
            "category": "engine_idle",
            "required_tags": ["stall"],
            "optional_tags": ["rough_idle", "hesitation", "stalling"],
            "required_dtcs": [],
            "likely_causes": [
                "Vacuum leak",
                "Throttle body deposits",
                "EVAP purge valve stuck open",
                "MAF sensor skew",
                "Brake booster vacuum leak",
            ],
            "checks": [
                "Check fuel trims at idle and during decel to stop.",
                "Inspect for intake and vacuum leaks.",
                "Inspect throttle body for carbon buildup.",
                "Check EVAP purge valve for stuck-open condition.",
                "Verify MAF airflow values and intake duct sealing.",
            ],
            "base_weight": 1.35,
        },
        {
            "name": "Stalls with rough idle",
            "category": "engine_idle",
            "required_tags": ["stall", "rough_idle"],
            "optional_tags": ["misfire", "hesitation"],
            "required_dtcs": [],
            "likely_causes": [
                "Vacuum leak",
                "Ignition misfire",
                "Throttle body contamination",
                "Low fuel pressure",
            ],
            "checks": [
                "Check misfire counters and fuel trims.",
                "Inspect plugs and coils.",
                "Inspect intake for leaks.",
                "Verify fuel pressure during idle and tip-in.",
            ],
            "base_weight": 1.30,
        },
        {
            "name": "Hard start / long crank",
            "category": "starting",
            "required_tags": ["hard_start"],
            "optional_tags": ["no_start", "stall"],
            "required_dtcs": [],
            "likely_causes": [
                "Low fuel pressure",
                "Fuel pump issue",
                "Weak battery",
                "Crank sensor fault",
            ],
            "checks": [
                "Check battery voltage during crank.",
                "Verify fuel pressure build-up.",
                "Check RPM signal during crank.",
                "Inspect fuel pump command and delivery.",
            ],
            "base_weight": 1.20,
        },
        {
            "name": "No start / crank no start",
            "category": "starting",
            "required_tags": ["no_start"],
            "optional_tags": ["hard_start"],
            "required_dtcs": [],
            "likely_causes": [
                "Fuel delivery failure",
                "Ignition reference issue",
                "Battery / voltage issue",
                "Communication or immobilizer issue",
            ],
            "checks": [
                "Verify crank/no-start condition and scan for DTCs.",
                "Check spark, injector pulse, and fuel pressure.",
                "Test battery and grounds.",
                "Check communication with ECM and related modules.",
            ],
            "base_weight": 1.30,
        },
        {
            "name": "Rough idle",
            "category": "engine_idle",
            "required_tags": ["rough_idle"],
            "optional_tags": ["misfire", "surging", "stall"],
            "required_dtcs": [],
            "likely_causes": [
                "Vacuum leak",
                "Throttle body deposits",
                "Ignition issue",
                "Injector imbalance",
            ],
            "checks": [
                "Check fuel trims and misfire counters.",
                "Inspect throttle body and air path.",
                "Inspect coils and spark plugs.",
                "Check injector balance if available.",
            ],
            "base_weight": 1.10,
        },
        {
            "name": "Surging / hunting idle",
            "category": "engine_idle",
            "required_tags": ["surging"],
            "optional_tags": ["rough_idle", "hesitation"],
            "required_dtcs": [],
            "likely_causes": [
                "Vacuum leak",
                "Throttle body contamination",
                "MAF issue",
                "Idle airflow instability",
            ],
            "checks": [
                "Watch STFT/LTFT for oscillation.",
                "Smoke test intake system.",
                "Inspect throttle body.",
                "Verify MAF readings.",
            ],
            "base_weight": 1.10,
        },

        # =========================
        # MISFIRE / LEAN / RICH / AIRFLOW
        # =========================
        {
            "name": "Random misfire",
            "category": "engine_performance",
            "required_tags": ["misfire"],
            "optional_tags": ["rough_idle", "hesitation"],
            "required_dtcs": ["P0300"],
            "likely_causes": [
                "Ignition coil fault",
                "Spark plug wear",
                "Fuel injector issue",
                "Vacuum leak",
            ],
            "checks": [
                "Check misfire counters by cylinder.",
                "Inspect coils and spark plugs.",
                "Review fuel trims.",
                "Check injector contribution.",
            ],
            "base_weight": 1.25,
        },
        {
            "name": "Cylinder-specific misfire",
            "category": "engine_performance",
            "required_tags": ["misfire"],
            "optional_tags": ["rough_idle"],
            "required_dtcs": ["P0301", "P0302", "P0303", "P0304", "P0305", "P0306", "P0307", "P0308"],
            "likely_causes": [
                "Single ignition coil failure",
                "Spark plug issue",
                "Injector fault",
                "Mechanical cylinder issue",
            ],
            "checks": [
                "Swap coil to see if misfire follows.",
                "Inspect spark plug condition.",
                "Check injector operation.",
                "Run compression or relative compression if needed.",
            ],
            "base_weight": 1.35,
        },
        {
            "name": "Lean condition bank 1 / bank 2",
            "category": "fuel_air",
            "required_tags": [],
            "optional_tags": ["rough_idle", "stall", "hesitation"],
            "required_dtcs": ["P0171", "P0174"],
            "likely_causes": [
                "Vacuum leak",
                "MAF sensor skew",
                "Low fuel pressure",
                "Unmetered air leak",
            ],
            "checks": [
                "Check STFT/LTFT at idle and 2500 RPM.",
                "Inspect intake duct and vacuum lines.",
                "Inspect MAF sensor and air filter housing.",
                "Verify fuel pressure.",
            ],
            "base_weight": 1.30,
        },
        {
            "name": "Rich condition",
            "category": "fuel_air",
            "required_tags": [],
            "optional_tags": ["rough_idle", "misfire"],
            "required_dtcs": ["P0172", "P0175"],
            "likely_causes": [
                "Leaking injector",
                "Biased fuel pressure",
                "MAF sensor issue",
                "Purge valve fault",
            ],
            "checks": [
                "Inspect fuel trims and O2 behavior.",
                "Check injector leakage.",
                "Verify MAF plausibility.",
                "Check purge valve operation.",
            ],
            "base_weight": 1.20,
        },
        {
            "name": "MAF performance issue",
            "category": "fuel_air",
            "required_tags": [],
            "optional_tags": ["hesitation", "rough_idle", "stall"],
            "required_dtcs": ["P0101"],
            "likely_causes": [
                "Contaminated MAF sensor",
                "Air intake leak",
                "Improper airflow reading",
                "Air filter / duct issue",
            ],
            "checks": [
                "Inspect MAF sensor and housing.",
                "Inspect intake duct for leaks after MAF.",
                "Compare MAF g/s to expected load.",
                "Inspect air filter and duct sealing.",
            ],
            "base_weight": 1.30,
        },
        {
            "name": "Throttle actuator / throttle correlation issue",
            "category": "fuel_air",
            "required_tags": ["hesitation"],
            "optional_tags": ["lack_of_power", "surging"],
            "required_dtcs": ["P0121", "P0221", "P1516", "P2101", "P2176"],
            "likely_causes": [
                "Throttle body fault",
                "Throttle position sensor issue",
                "Connector / wiring issue",
                "Throttle relearn needed",
            ],
            "checks": [
                "Check APP and throttle position correlation.",
                "Inspect throttle body and connector.",
                "Check for reduced power history.",
                "Perform throttle relearn if applicable.",
            ],
            "base_weight": 1.35,
        },
        {
            "name": "Catalyst efficiency issue",
            "category": "exhaust",
            "required_tags": [],
            "optional_tags": ["lack_of_power", "misfire"],
            "required_dtcs": ["P0420", "P0430"],
            "likely_causes": [
                "Catalyst deterioration",
                "Upstream engine issue causing catalyst stress",
                "O2 sensor reporting issue",
            ],
            "checks": [
                "Inspect for prior misfire history.",
                "Check upstream/downstream O2 switching behavior.",
                "Inspect for exhaust leaks.",
                "Evaluate exhaust backpressure if power loss exists.",
            ],
            "base_weight": 1.10,
        },
        {
            "name": "O2 sensor response issue",
            "category": "exhaust",
            "required_tags": [],
            "optional_tags": ["rough_idle", "misfire"],
            "required_dtcs": ["P0131", "P0137", "P0151", "P0157"],
            "likely_causes": [
                "O2 sensor fault",
                "Wiring / connector issue",
                "Lean condition",
                "Exhaust leak",
            ],
            "checks": [
                "Inspect O2 sensor voltage activity.",
                "Inspect harness and connector.",
                "Check for exhaust leaks ahead of sensor.",
                "Compare trims and sensor behavior.",
            ],
            "base_weight": 1.10,
        },
        {
            "name": "EVAP purge issue affecting drivability",
            "category": "evap",
            "required_tags": ["stall"],
            "optional_tags": ["rough_idle", "hard_start"],
            "required_dtcs": ["P0496"],
            "likely_causes": [
                "Purge valve stuck open",
                "EVAP flow control fault",
                "Fuel vapor loading at idle",
            ],
            "checks": [
                "Command purge valve and monitor response.",
                "Check for vacuum at purge line when not commanded.",
                "Inspect EVAP plumbing.",
            ],
            "base_weight": 1.35,
        },

        # =========================
        # POWER / HESITATION / REDUCED PERFORMANCE
        # =========================
        {
            "name": "Hesitation on acceleration",
            "category": "drivability",
            "required_tags": ["hesitation"],
            "optional_tags": ["lack_of_power", "surging"],
            "required_dtcs": [],
            "likely_causes": [
                "Airflow metering issue",
                "Throttle response issue",
                "Fuel delivery weakness",
                "Ignition miss under load",
            ],
            "checks": [
                "Check MAF and fuel trims under load.",
                "Check throttle angle response.",
                "Check misfire counters during acceleration.",
                "Verify fuel pressure.",
            ],
            "base_weight": 1.20,
        },
        {
            "name": "Lack of power / reduced power feel",
            "category": "drivability",
            "required_tags": ["lack_of_power"],
            "optional_tags": ["hesitation", "misfire"],
            "required_dtcs": [],
            "likely_causes": [
                "Throttle limitation",
                "Fuel delivery issue",
                "Exhaust restriction",
                "Ignition or airflow fault",
            ],
            "checks": [
                "Check throttle opening and APP response.",
                "Check fuel trims and fuel pressure.",
                "Inspect for catalyst restriction signs.",
                "Check for active or pending misfire codes.",
            ],
            "base_weight": 1.15,
        },
        {
            "name": "Reduced engine power mode",
            "category": "drivability",
            "required_tags": ["lack_of_power"],
            "optional_tags": ["hesitation"],
            "required_dtcs": ["P1516", "P2101", "P2135"],
            "likely_causes": [
                "Throttle body failure",
                "APP sensor correlation fault",
                "Wiring / connector issue",
            ],
            "checks": [
                "Inspect throttle body and APP sensor data.",
                "Check 5V reference and grounds.",
                "Inspect connector terminals.",
            ],
            "base_weight": 1.40,
        },

        # =========================
        # COOLING / TEMP
        # =========================
        {
            "name": "Overheating",
            "category": "cooling",
            "required_tags": ["overheat"],
            "optional_tags": [],
            "required_dtcs": [],
            "likely_causes": [
                "Low coolant",
                "Thermostat fault",
                "Cooling fan issue",
                "Water pump issue",
            ],
            "checks": [
                "Check coolant level and signs of leakage.",
                "Verify fan operation.",
                "Monitor thermostat opening behavior.",
                "Inspect water pump flow and belt drive.",
            ],
            "base_weight": 1.30,
        },
        {
            "name": "Engine running cold / thermostat performance",
            "category": "cooling",
            "required_tags": [],
            "optional_tags": [],
            "required_dtcs": ["P0128"],
            "likely_causes": [
                "Thermostat stuck open",
                "Cooling system temp reporting issue",
            ],
            "checks": [
                "Monitor ECT warm-up curve.",
                "Verify thermostat operation.",
                "Compare ECT to actual engine temperature.",
            ],
            "base_weight": 1.15,
        },

        # =========================
        # BRAKES / WHEELS / NOISE / VIBRATION
        # =========================
        {
            "name": "Brake pull / pulls while braking",
            "category": "brakes",
            "required_tags": ["pulling"],
            "optional_tags": [],
            "required_dtcs": [],
            "likely_causes": [
                "Sticking caliper",
                "Brake hose restriction",
                "Uneven pad friction",
                "Suspension issue under braking",
            ],
            "checks": [
                "Check rotor temp side to side.",
                "Inspect caliper slides and piston movement.",
                "Inspect brake hose restriction.",
                "Check front suspension for looseness.",
            ],
            "base_weight": 1.20,
        },
        {
            "name": "Brake pulsation",
            "category": "brakes",
            "required_tags": ["vibration"],
            "optional_tags": [],
            "required_dtcs": [],
            "likely_causes": [
                "Rotor thickness variation",
                "Rotor runout",
                "Improper wheel torque history",
            ],
            "checks": [
                "Confirm vibration occurs only while braking.",
                "Measure rotor runout and thickness variation.",
                "Inspect pad transfer pattern.",
            ],
            "base_weight": 1.05,
        },
        {
            "name": "Wheel bearing / hub noise",
            "category": "chassis",
            "required_tags": ["noise"],
            "optional_tags": ["vibration"],
            "required_dtcs": [],
            "likely_causes": [
                "Wheel bearing wear",
                "Hub assembly issue",
                "Tire noise mistaken for bearing noise",
            ],
            "checks": [
                "Road test for growl/hum change while turning.",
                "Check wheel play and roughness.",
                "Inspect tire wear pattern.",
            ],
            "base_weight": 1.05,
        },
        {
            "name": "Tire / road force vibration",
            "category": "chassis",
            "required_tags": ["vibration"],
            "optional_tags": [],
            "required_dtcs": [],
            "likely_causes": [
                "Tire balance issue",
                "Road force variation",
                "Bent wheel",
                "Tire irregular wear",
            ],
            "checks": [
                "Determine speed range of vibration.",
                "Inspect tires for cupping or separation.",
                "Check wheel balance and road force.",
                "Inspect wheels for bends.",
            ],
            "base_weight": 1.10,
        },
        {
            "name": "Driveline shudder / acceleration vibration",
            "category": "chassis",
            "required_tags": ["vibration"],
            "optional_tags": ["hesitation"],
            "required_dtcs": [],
            "likely_causes": [
                "Driveshaft imbalance",
                "U-joint / driveline issue",
                "Engine or transmission mount issue",
            ],
            "checks": [
                "Confirm vibration under load vs coast.",
                "Inspect driveshaft and joints.",
                "Inspect mounts.",
            ],
            "base_weight": 1.05,
        },
        {
            "name": "Clunk noise on takeoff / stop",
            "category": "chassis",
            "required_tags": ["clunk"],
            "optional_tags": ["noise"],
            "required_dtcs": [],
            "likely_causes": [
                "Mount wear",
                "Suspension joint play",
                "Driveshaft lash",
            ],
            "checks": [
                "Inspect engine/trans mounts.",
                "Inspect control arm bushings and sway links.",
                "Inspect driveline lash.",
            ],
            "base_weight": 1.05,
        },

        # =========================
        # TRANSMISSION / SHIFTING
        # =========================
        {
            "name": "Harsh shift feel",
            "category": "transmission",
            "required_tags": [],
            "optional_tags": ["clunk"],
            "required_dtcs": [],
            "likely_causes": [
                "Adapt shift issue",
                "Fluid quality issue",
                "Solenoid / valve body issue",
            ],
            "checks": [
                "Confirm which shift event is harsh.",
                "Check fluid condition.",
                "Scan transmission data and adapt values.",
            ],
            "base_weight": 1.00,
        },
        {
            "name": "Transmission slip / flare",
            "category": "transmission",
            "required_tags": [],
            "optional_tags": ["lack_of_power"],
            "required_dtcs": ["P0700", "P0796"],
            "likely_causes": [
                "Low or degraded fluid",
                "Pressure control issue",
                "Internal clutch slip",
            ],
            "checks": [
                "Confirm slip event by gear/range.",
                "Check fluid condition and level.",
                "Scan for transmission pressure control data.",
            ],
            "base_weight": 1.20,
        },
        {
            "name": "Torque converter shudder type complaint",
            "category": "transmission",
            "required_tags": ["vibration"],
            "optional_tags": [],
            "required_dtcs": [],
            "likely_causes": [
                "Torque converter clutch shudder",
                "Fluid deterioration",
                "Driveline vibration mistaken for TCC shudder",
            ],
            "checks": [
                "Confirm complaint during light throttle lockup.",
                "Monitor TCC apply state.",
                "Compare to driveline vibration conditions.",
            ],
            "base_weight": 1.05,
        },

        # =========================
        # ELECTRICAL / COMMUNICATION / VOLTAGE
        # =========================
        {
            "name": "Low voltage / battery issue",
            "category": "electrical",
            "required_tags": [],
            "optional_tags": ["no_start", "hard_start"],
            "required_dtcs": ["B1325"],
            "likely_causes": [
                "Weak battery",
                "Charging system issue",
                "High resistance cable or ground",
            ],
            "checks": [
                "Test battery state of health.",
                "Verify charging voltage.",
                "Check voltage drop across major cables and grounds.",
            ],
            "base_weight": 1.25,
        },
        {
            "name": "Module communication fault",
            "category": "electrical",
            "required_tags": [],
            "optional_tags": ["no_start"],
            "required_dtcs": ["U0100", "U0140", "U0151"],
            "likely_causes": [
                "Low voltage event",
                "Module power/ground issue",
                "CAN communication fault",
            ],
            "checks": [
                "Check battery voltage and system grounds first.",
                "Identify which module is offline.",
                "Inspect CAN wiring and connector integrity.",
            ],
            "base_weight": 1.30,
        },
        {
            "name": "Intermittent electrical weirdness",
            "category": "electrical",
            "required_tags": [],
            "optional_tags": ["no_start"],
            "required_dtcs": [],
            "likely_causes": [
                "Weak battery",
                "Ground issue",
                "Fuse block connection issue",
                "Intermittent module wake-up issue",
            ],
            "checks": [
                "Check battery and charging system.",
                "Inspect main grounds and power feeds.",
                "Inspect fuse block connections.",
                "Check for communication history codes.",
            ],
            "base_weight": 1.00,
        },

        # =========================
        # FUEL SYSTEM
        # =========================
        {
            "name": "Fuel rail / pressure performance",
            "category": "fuel_system",
            "required_tags": ["hard_start"],
            "optional_tags": ["hesitation", "lack_of_power"],
            "required_dtcs": ["P0087", "P0191"],
            "likely_causes": [
                "Low fuel pressure",
                "Fuel pump weakness",
                "Pressure sensor issue",
                "Fuel supply restriction",
            ],
            "checks": [
                "Verify commanded vs actual fuel pressure.",
                "Check supply pressure and volume.",
                "Inspect sensor plausibility.",
                "Inspect fuel delivery path.",
            ],
            "base_weight": 1.35,
        },
        {
            "name": "Injector performance issue",
            "category": "fuel_system",
            "required_tags": ["misfire"],
            "optional_tags": ["rough_idle", "hard_start"],
            "required_dtcs": ["P0201", "P0202", "P0203", "P0204", "P0205", "P0206", "P0207", "P0208"],
            "likely_causes": [
                "Injector circuit fault",
                "Injector mechanical fault",
                "Connector or harness issue",
            ],
            "checks": [
                "Check injector balance and electrical command.",
                "Inspect connector fit and wiring.",
                "Compare cylinder contribution.",
            ],
            "base_weight": 1.30,
        },

        # =========================
        # EXHAUST / EMISSIONS / EVAP
        # =========================
        {
            "name": "Small EVAP leak",
            "category": "evap",
            "required_tags": [],
            "optional_tags": [],
            "required_dtcs": ["P0442", "P0455", "P0456"],
            "likely_causes": [
                "Loose or faulty fuel cap",
                "EVAP line leak",
                "Canister vent / purge plumbing leak",
            ],
            "checks": [
                "Check fuel cap seal and tightness.",
                "Smoke test EVAP system.",
                "Inspect canister, lines, and vent valve.",
            ],
            "base_weight": 1.10,
        },
        {
            "name": "EVAP vent control issue",
            "category": "evap",
            "required_tags": [],
            "optional_tags": [],
            "required_dtcs": ["P0446"],
            "likely_causes": [
                "Vent valve fault",
                "Blocked vent path",
                "Wiring / connector issue",
            ],
            "checks": [
                "Command vent valve and monitor response.",
                "Inspect vent path for blockage.",
                "Inspect connector and harness.",
            ],
            "base_weight": 1.15,
        },

        # =========================
        # SENSORS / TIMING / ENGINE CONTROL
        # =========================
        {
            "name": "Crankshaft position sensor issue",
            "category": "engine_control",
            "required_tags": ["hard_start"],
            "optional_tags": ["stall", "no_start"],
            "required_dtcs": ["P0335"],
            "likely_causes": [
                "Crankshaft position sensor failure",
                "Sensor wiring issue",
                "Intermittent signal loss",
            ],
            "checks": [
                "Check RPM signal during crank and stall event.",
                "Inspect CKP sensor connector and harness.",
                "Review freeze frame for loss of sync behavior.",
            ],
            "base_weight": 1.35,
        },
        {
            "name": "Camshaft position / timing correlation issue",
            "category": "engine_control",
            "required_tags": ["misfire"],
            "optional_tags": ["hard_start", "rough_idle"],
            "required_dtcs": ["P0016", "P0017", "P0018", "P0019"],
            "likely_causes": [
                "Timing correlation issue",
                "Cam / crank sensor reporting fault",
                "Mechanical timing concern",
            ],
            "checks": [
                "Review correlation data.",
                "Inspect related sensors and connectors.",
                "Evaluate timing system if correlation persists.",
            ],
            "base_weight": 1.35,
        },
        {
            "name": "VVT / cam actuator performance issue",
            "category": "engine_control",
            "required_tags": [],
            "optional_tags": ["rough_idle", "lack_of_power"],
            "required_dtcs": ["P0011", "P0014", "P0021", "P0024"],
            "likely_causes": [
                "Cam actuator sticking",
                "Oil flow or oil quality issue",
                "Solenoid issue",
            ],
            "checks": [
                "Check engine oil level and condition.",
                "Command cam actuator if supported.",
                "Inspect actuator solenoid and response.",
            ],
            "base_weight": 1.25,
        },

        # =========================
        # AC / ACCESSORY / BELT NOISE
        # =========================
        {
            "name": "Accessory / belt noise",
            "category": "accessory_drive",
            "required_tags": ["noise"],
            "optional_tags": [],
            "required_dtcs": [],
            "likely_causes": [
                "Belt wear or slip",
                "Tensioner issue",
                "Accessory bearing noise",
            ],
            "checks": [
                "Identify if noise changes with accessory load.",
                "Inspect belt and tensioner.",
                "Inspect pulleys and accessory bearings.",
            ],
            "base_weight": 1.00,
        },

        # =========================
        # STEERING / FRONT END
        # =========================
        {
            "name": "Front end clunk / suspension noise",
            "category": "suspension",
            "required_tags": ["clunk"],
            "optional_tags": ["noise"],
            "required_dtcs": [],
            "likely_causes": [
                "Sway bar links",
                "Control arm bushings",
                "Ball joint play",
                "Strut mount issue",
            ],
            "checks": [
                "Inspect sway links and bushings.",
                "Inspect control arms and ball joints.",
                "Check strut mounts and fastener torque.",
            ],
            "base_weight": 1.05,
        },
        {
            "name": "Steering vibration / shimmy",
            "category": "steering",
            "required_tags": ["vibration"],
            "optional_tags": [],
            "required_dtcs": [],
            "likely_causes": [
                "Wheel balance issue",
                "Tire issue",
                "Front suspension looseness",
                "Brake pulsation if under braking",
            ],
            "checks": [
                "Confirm speed range and braking relation.",
                "Inspect balance, tire condition, and wheel runout.",
                "Inspect steering and suspension components.",
            ],
            "base_weight": 1.00,
        },
    ]


def seed_kb(session: Session) -> None:
    existing = {row.name: row for row in session.exec(select(TriageRule)).all()}

    for data in _rules():
        row = existing.get(data["name"])
        if row:
            for key, value in data.items():
                setattr(row, key, value)
            session.add(row)
        else:
            session.add(TriageRule(**data))

    session.commit()
