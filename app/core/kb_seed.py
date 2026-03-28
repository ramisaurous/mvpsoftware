

# app/core/kb_seed.py
from __future__ import annotations

from sqlmodel import Session, select

from app.models.triage_rule import TriageRule


def seed_kb(session: Session) -> None:
    """
    Idempotent KB seed.
    Inserts starter rules only when triage_rule table is empty.

    Broad coverage comes from:
      - DTC overlap (dtcs_any)
      - symptom tags (required_tags/optional_tags)
      - contexts (contexts_any)
      - thresholds (min_speed_mph)
    """
    exists = session.exec(select(TriageRule).limit(1)).first()
    if exists:
        return

    rules: list[TriageRule] = [
        # -------------------------
        # TIRES / WHEELS / CHASSIS
        # -------------------------
            TriageRule(
            name="Wheel/tire imbalance (vibration over highway speeds)",
            category="tires_wheels",
            required_tags=["vibration"],
            min_speed_mph=55,
            checks=[
                "Road test: confirm speed range; note if changes with throttle.",
                "Inspect tire wear (cupping/feathering), bulges, separated belts.",
                "Balance wheels; road-force balance if available.",
            ],
            likely_causes=["Wheel/tire imbalance", "Tire belt separation", "Cupped tires"],
            base_weight=1.2,
        ),
        TriageRule(
            name="Brake-related vibration (only when braking at speed)",
            category="brakes",
            required_tags=["vibration"],
            contexts_any=["when_braking"],
            min_speed_mph=45,
            checks=[
                "Confirm vibration only during braking (not steady cruise).",
                "Measure rotor runout/thickness variation; inspect caliper slides/pins.",
            ],
            likely_causes=["Rotor thickness variation", "Rotor runout", "Sticking caliper"],
            base_weight=1.05,
        ),
        TriageRule(
            name="Wheel bearing noise (hum/growl that changes with load)",
            category="tires_wheels",
            required_tags=["noise"],
            optional_tags=["vibration"],
            min_speed_mph=35,
            checks=[
                "Road test: steer left/right to shift load; listen for change.",
                "Check play/roughness; compare hub temps after drive.",
            ],
            likely_causes=["Wheel bearing wear", "Hub assembly wear"],
            base_weight=1.0,
        ),
    ]
        TriageRule(
            name="Wheel/tire imbalance (highway vibration)",
            category="tires_wheels",
            required_tags=["vibration"],
            min_speed_mph=55,
            checks=[
                "Road test: confirm speed range; note if changes with throttle.",
                "Inspect tire wear (cupping/feathering), bulges, separated belts.",
                "Balance wheels; road-force balance if available.",
            ],
            likely_causes=["Wheel/tire imbalance", "Tire belt separation", "Cupped tires"],
            base_weight=1.25,
        ),
        TriageRule(
            name="Bent wheel / out-of-round tire",
            category="tires_wheels",
            required_tags=["vibration"],
            min_speed_mph=50,
            checks=[
                "Inspect wheels for bends/impact damage; check runout.",
                "Check tire radial/lateral runout; rotate front/rear to see if symptom moves.",
            ],
            likely_causes=["Bent wheel", "Out-of-round tire"],
            base_weight=1.15,
        ),
        TriageRule(
            name="Tire separation / shifted belt",
            category="tires_wheels",
            required_tags=["vibration"],
            optional_tags=["noise"],
            min_speed_mph=40,
            checks=[
                "Inspect for bulge/hop; run hands over tread for separation.",
                "Swap suspect tire position; confirm symptom changes.",
            ],
            likely_causes=["Tire belt separation", "Manufacturing defect", "Impact damage"],
            base_weight=1.1,
        ),
        TriageRule(
            name="Alignment / radial pull (drifts/pulls)",
            category="tires_wheels",
            required_tags=["pulling"],
            checks=[
                "Road test on flat road; confirm direction and consistency.",
                "Inspect tire pressures and mismatched tires; rotate front tires to see if pull changes.",
                "Check alignment (camber/caster/toe).",
            ],
            likely_causes=["Alignment out of spec", "Tire radial pull", "Brake drag"],
            base_weight=1.1,
        ),
        TriageRule(
            name="Wheel bearing noise (hum/growl) that changes with load",
            category="tires_wheels",
            required_tags=["noise"],
            optional_tags=["vibration"],
            min_speed_mph=35,
            checks=[
                "Road test: steer left/right to shift load; listen for change.",
                "Check for play/roughness; compare hub temps after drive.",
            ],
            likely_causes=["Wheel bearing wear", "Hub assembly wear"],
            base_weight=1.15,
        ),
        TriageRule(
            name="Loose suspension/steering component (clunk/rattle/noise)",
            category="chassis",
            required_tags=["noise"],
            optional_tags=["pulling", "vibration"],
            checks=[
                "Inspect tie rods, ball joints, control arm bushings, sway bar links.",
                "Check for play with wheels off ground; torque check critical fasteners.",
            ],
            likely_causes=["Worn tie rod/ball joint", "Sway bar link", "Control arm bushing"],
            base_weight=1.0,
        ),
        TriageRule(
            name="Brake drag / seized caliper (pull + smell/heat)",
            category="brakes",
            required_tags=["pulling"],
            optional_tags=["noise"],
            checks=[
                "Check wheel temps after short drive; compare side-to-side.",
                "Inspect pads/caliper slides; verify piston retracts.",
            ],
            likely_causes=["Sticking caliper", "Collapsed brake hose", "Seized slide pins"],
            base_weight=1.0,
        ),

        # -------------------------
        # BRAKES
        # -------------------------
        TriageRule(
            name="Brake pulsation / vibration during braking",
            category="brakes",
            required_tags=["brake_pulsation"],
            contexts_any=["when_braking"],
            min_speed_mph=35,
            checks=[
                "Confirm symptom only during braking.",
                "Measure rotor runout and thickness variation; inspect pad deposits.",
            ],
            likely_causes=["Rotor thickness variation", "Rotor runout", "Pad material transfer"],
            base_weight=1.2,
        ),
        TriageRule(
            name="Brake-related vibration (driver reports 'shake when braking')",
            category="brakes",
            required_tags=["vibration"],
            contexts_any=["when_braking"],
            min_speed_mph=45,
            checks=[
                "Confirm vibration is braking-only vs steady cruise.",
                "Measure rotor runout/thickness variation; inspect caliper slides and torque.",
            ],
            likely_causes=["Rotor thickness variation", "Rotor runout", "Sticking caliper"],
            base_weight=1.15,
        ),
        TriageRule(
            name="Brake noise (squeal/grind) basic checks",
            category="brakes",
            required_tags=["noise"],
            contexts_any=["when_braking"],
            checks=[
                "Inspect pad thickness and wear indicators.",
                "Inspect rotors for scoring/rust ridge; check backing plates.",
            ],
            likely_causes=["Worn pads", "Glazed pads/rotors", "Debris between pad/rotor"],
            base_weight=1.0,
        ),

        # -------------------------
        # DRIVELINE / TRANS
        # -------------------------
        TriageRule(
            name="Driveline vibration (changes on accel/decel)",
            category="driveline",
            required_tags=["vibration"],
            contexts_any=["when_accelerating", "when_decelerating"],
            min_speed_mph=30,
            checks=[
                "Verify if vibration changes on accel vs coast.",
                "Inspect driveshaft/U-joints/CV joints; check mounts and angles.",
            ],
            likely_causes=["Worn U-joint", "CV joint wear", "Driveshaft imbalance/angle"],
            base_weight=1.1,
        ),
        TriageRule(
            name="Torque converter shudder / trans shudder (often feels like vibration)",
            category="transmission",
            required_tags=["vibration"],
            optional_tags=["hesitation"],
            dtcs_any=["P0741", "P0796", "P07A3", "P07A5"],
            min_speed_mph=30,
            checks=[
                "Road test with scan tool: look for TCC slip events.",
                "Check fluid level/condition; verify correct fluid type.",
                "Check for TCM updates and relearn procedure if applicable.",
            ],
            likely_causes=["TCC shudder", "Fluid condition", "Valve body/solenoid"],
            base_weight=1.05,
        ),
        TriageRule(
            name="Harsh shift / flare / slip (trans concerns)",
            category="transmission",
            required_tags=["hesitation"],
            dtcs_any=["P0700", "P0711", "P0717", "P0722", "P0730", "P0741", "P0796"],
            checks=[
                "Confirm complaint: harsh shift/flare/slip; capture data log.",
                "Check for TCM codes and service bulletins; verify fluid level/condition.",
            ],
            likely_causes=["Low/dirty fluid", "Valve body/solenoid", "Software/adapts"],
            base_weight=0.95,
        ),

        # -------------------------
        # ENGINE: MISFIRE / IDLE / FUEL / AIR
        # -------------------------
        TriageRule(
            name="Random/multiple misfire pattern",
            category="engine",
            required_tags=["misfire"],
            optional_tags=["rough_idle"],
            dtcs_any=["P0300"],
            checks=[
                "Check freeze frame and Mode $06 misfire counters.",
                "Inspect plugs/coils; check injector balance if available.",
                "Smoke test intake for vacuum leaks; check fuel trims.",
            ],
            likely_causes=["Ignition issue", "Vacuum leak", "Fuel delivery/injector"],
            base_weight=1.2,
        ),
        TriageRule(
            name="Cylinder-specific misfire (P0301-P0308)",
            category="engine",
            required_tags=["misfire"],
            dtcs_any=["P0301", "P0302", "P0303", "P0304", "P0305", "P0306", "P0307", "P0308"],
            checks=[
                "Swap coil/plug with another cylinder to see if misfire follows.",
                "Compression/leakdown if persistent; check injector operation.",
            ],
            likely_causes=["Plug/coil failure", "Injector issue", "Mechanical compression issue"],
            base_weight=1.15,
        ),
        TriageRule(
            name="Rough idle without clear misfire code",
            category="engine",
            required_tags=["rough_idle"],
            optional_tags=["surging"],
            checks=[
                "Check fuel trims and vacuum leaks; inspect PCV and intake plumbing.",
                "Check MAF/MAP plausibility; verify throttle body cleanliness.",
            ],
            likely_causes=["Vacuum leak", "MAF contamination", "Throttle body deposits"],
            base_weight=1.05,
        ),
        TriageRule(
            name="Lean condition / fuel trim high (Bank 1/2)",
            category="engine",
            required_tags=["hesitation"],
            dtcs_any=["P0171", "P0174"],
            checks=[
                "Smoke test intake for unmetered air.",
                "Check fuel pressure under load; verify MAF readings.",
            ],
            likely_causes=["Vacuum leak", "Low fuel pressure", "MAF issue"],
            base_weight=1.1,
        ),
        TriageRule(
            name="Rich condition / fuel trim negative",
            category="engine",
            required_tags=["hesitation"],
            dtcs_any=["P0172", "P0175"],
            checks=[
                "Check for leaking injector; fuel pressure regulator issues.",
                "Inspect air filter/intake restriction; verify O2 sensor response.",
            ],
            likely_causes=["Leaking injector", "High fuel pressure", "Air restriction"],
            base_weight=1.0,
        ),
        TriageRule(
            name="MAF sensor performance / plausibility",
            category="engine",
            required_tags=["hesitation"],
            dtcs_any=["P0101", "P0102", "P0103"],
            checks=[
                "Inspect intake for leaks after MAF; verify filter and ducting.",
                "Clean/inspect MAF; compare g/s to expected at idle and load.",
            ],
            likely_causes=["MAF contamination", "Intake leak", "Wiring/connector issue"],
            base_weight=1.05,
        ),
        TriageRule(
            name="MAP sensor circuit / plausibility",
            category="engine",
            required_tags=["hesitation"],
            dtcs_any=["P0106", "P0107", "P0108"],
            checks=[
                "Compare MAP to barometric key-on engine-off.",
                "Inspect MAP hose/port; check wiring.",
            ],
            likely_causes=["MAP sensor issue", "Wiring/connector issue", "Vacuum leak"],
            base_weight=1.0,
        ),
        TriageRule(
            name="Throttle actuator / electronic throttle concern",
            category="engine",
            required_tags=["hesitation"],
            dtcs_any=["P0121", "P0221", "P2101", "P2119"],
            checks=[
                "Check throttle body for carbon; verify pedal and throttle position correlation.",
                "Inspect connectors and grounds; follow pinpoint tests.",
            ],
            likely_causes=["Throttle body issue", "Wiring/connector", "Pedal sensor issue"],
            base_weight=1.05,
        ),
        TriageRule(
            name="O2 sensor low voltage / slow response",
            category="engine",
            required_tags=["hesitation"],
            dtcs_any=["P0131", "P0151", "P0137", "P0157", "P0133", "P0153"],
            checks=[
                "Check exhaust leaks upstream of sensors.",
                "Verify sensor response with snap throttle; inspect wiring/heat damage.",
            ],
            likely_causes=["Exhaust leak", "A/F sensor aging", "Wiring issue"],
            base_weight=1.0,
        ),
        TriageRule(
            name="Catalyst efficiency below threshold",
            category="engine",
            required_tags=["hesitation"],
            dtcs_any=["P0420", "P0430"],
            checks=[
                "Check for misfire/fuel trim root causes first.",
                "Compare upstream/downstream O2 waveforms; check exhaust leaks.",
            ],
            likely_causes=["Catalyst degradation", "Upstream misfire/rich/lean", "Exhaust leak"],
            base_weight=0.95,
        ),

        # -------------------------
        # EVAP
        # -------------------------
        TriageRule(
            name="EVAP small leak",
            category="evap",
            required_tags=["hesitation"],
            dtcs_any=["P0442", "P0456"],
            checks=[
                "Inspect gas cap/seal; run smoke test on EVAP system.",
                "Check vent valve/canister for debris or saturation.",
            ],
            likely_causes=["Loose cap/seal", "Small leak in EVAP lines", "Vent valve issue"],
            base_weight=0.95,
        ),
        TriageRule(
            name="EVAP large leak",
            category="evap",
            required_tags=["hesitation"],
            dtcs_any=["P0455"],
            checks=[
                "Verify cap is present/tight; inspect filler neck and EVAP lines.",
                "Smoke test EVAP; check vent valve stuck open.",
            ],
            likely_causes=["Cap off/failed seal", "Disconnected EVAP line", "Vent valve stuck open"],
            base_weight=0.95,
        ),
        TriageRule(
            name="EVAP purge flow / purge valve stuck",
            category="evap",
            required_tags=["rough_idle"],
            dtcs_any=["P0496", "P0441"],
            checks=[
                "Command purge; observe STFT response. Check purge valve for leaking at idle.",
                "Inspect purge line routing and valve electrical.",
            ],
            likely_causes=["Purge valve stuck open", "Incorrect purge flow", "Vacuum leak via purge"],
            base_weight=1.0,
        ),

        # -------------------------
        # COOLING / OVERHEAT
        # -------------------------
        TriageRule(
            name="Engine overheating (general)",
            category="cooling",
            required_tags=["overheating"],
            checks=[
                "Check coolant level and pressure test cooling system.",
                "Verify fan operation and thermostat behavior; check for air pockets.",
            ],
            likely_causes=["Low coolant/leak", "Thermostat issue", "Fan control issue"],
            base_weight=1.2,
        ),
        TriageRule(
            name="Coolant temp sensor / circuit",
            category="cooling",
            required_tags=["overheating"],
            dtcs_any=["P0117", "P0118", "P0119"],
            checks=[
                "Verify ECT reading vs ambient when cold.",
                "Inspect sensor connector and wiring; check for corrosion.",
            ],
            likely_causes=["ECT sensor failure", "Wiring/connector issue"],
            base_weight=1.05,
        ),
        TriageRule(
            name="Cooling fan control / performance",
            category="cooling",
            required_tags=["overheating"],
            dtcs_any=["P0480", "P0481", "P0691", "P0692", "P0526"],
            checks=[
                "Command fans on with scan tool; verify relay/module operation.",
                "Inspect fan connectors for heat damage; verify power/ground.",
            ],
            likely_causes=["Fan relay/module issue", "Fan motor failure", "Wiring issue"],
            base_weight=1.05,
        ),

        # -------------------------
        # START / NO-START / HARD START
        # -------------------------
        TriageRule(
            name="No-start / crank-no-start (basic fuel/spark/air)",
            category="starting",
            required_tags=["no_start"],
            checks=[
                "Verify crank speed and battery voltage under load.",
                "Check fuel pressure and injector pulse; verify spark.",
                "Scan for immobilizer/security codes.",
            ],
            likely_causes=["Fuel delivery issue", "Ignition/spark issue", "Security/immobilizer"],
            base_weight=1.1,
        ),
        TriageRule(
            name="Hard start / long crank (fuel pressure bleed-down)",
            category="starting",
            required_tags=["hard_start"],
            checks=[
                "Check fuel pressure prime and residual pressure after key-off.",
                "Inspect for leaking injectors; check pump check valve.",
            ],
            likely_causes=["Fuel pressure bleed-down", "Leaking injector", "Weak fuel pump"],
            base_weight=1.05,
        ),
        TriageRule(
            name="Crankshaft position sensor / signal",
            category="starting",
            required_tags=["no_start"],
            dtcs_any=["P0335", "P0336"],
            checks=[
                "Verify RPM signal while cranking on scan tool.",
                "Inspect CKP sensor wiring and connector; check sensor gap.",
            ],
            likely_causes=["CKP sensor failure", "Wiring/connector issue"],
            base_weight=1.05,
        ),
        TriageRule(
            name="Camshaft position sensor / correlation",
            category="starting",
            required_tags=["hard_start"],
            dtcs_any=["P0340", "P0341", "P0016", "P0017"],
            checks=[
                "Check cam/crank correlation; inspect sensor connectors.",
                "If correlation codes persist, inspect timing components.",
            ],
            likely_causes=["CMP sensor issue", "Timing chain stretch", "VVT actuator concern"],
            base_weight=1.0,
        ),

        # -------------------------
        # ELECTRICAL / CHARGING / NETWORK
        # -------------------------
        TriageRule(
            name="Battery / low voltage symptoms (many lights / weird behavior)",
            category="electrical",
            required_tags=["no_start"],
            optional_tags=["rough_idle"],
            dtcs_any=["U0100", "U0121", "U0140", "U0151"],
            checks=[
                "Load test battery; check terminals and grounds.",
                "Check voltage drop on crank; inspect main grounds and body grounds.",
            ],
            likely_causes=["Weak battery", "Corroded terminals/grounds", "Voltage drop"],
            base_weight=1.05,
        ),
        TriageRule(
            name="Charging system / alternator performance",
            category="electrical",
            required_tags=["no_start"],
            dtcs_any=["P0562", "P0563"],
            checks=[
                "Check alternator output and ripple; inspect belt and connections.",
                "Verify battery health; confirm charging voltage under load.",
            ],
            likely_causes=["Alternator failure", "Belt slip", "Wiring/connection issue"],
            base_weight=1.0,
        ),
        TriageRule(
            name="Network U-codes / loss of communication",
            category="network",
            required_tags=["no_start"],
            dtcs_any=["U0100", "U0121", "U0140", "U0151", "U0184", "U0401", "U0415"],
            checks=[
                "Check battery/grounds first; then inspect CAN wiring/connectors.",
                "Identify which modules are offline; follow topology/pinpoint tests.",
            ],
            likely_causes=["Low voltage", "CAN wiring/connectors", "Module software anomaly"],
            base_weight=1.0,
        ),

        # -------------------------
        # ENGINE: VVT / OIL / PERFORMANCE
        # -------------------------
        TriageRule(
            name="VVT actuator / cam timing performance",
            category="engine",
            required_tags=["hesitation"],
            dtcs_any=["P0010", "P0011", "P0013", "P0014", "P0016", "P0017"],
            checks=[
                "Check oil level/condition; verify correct viscosity.",
                "Inspect VVT solenoids for debris; check actuator commands vs actual.",
            ],
            likely_causes=["Dirty oil/sludge", "VVT solenoid sticking", "Timing component wear"],
            base_weight=1.0,
        ),
        TriageRule(
            name="Oil pressure / sensor concerns",
            category="engine",
            required_tags=["hesitation"],
            dtcs_any=["P0520", "P0521", "P0522", "P0523"],
            checks=[
                "Verify oil level and mechanical oil pressure if suspect.",
                "Inspect oil pressure sensor and connector.",
            ],
            likely_causes=["Oil pressure sensor failure", "Low oil pressure mechanical", "Wiring issue"],
            base_weight=0.95,
        ),

        # -------------------------
        # AIR INDUCTION / VACUUM / PCV
        # -------------------------
        TriageRule(
            name="Vacuum leak / unmetered air (rough idle/lean/hesitation)",
            category="engine",
            required_tags=["rough_idle"],
            optional_tags=["hesitation"],
            dtcs_any=["P0171", "P0174"],
            checks=[
                "Smoke test intake; inspect PCV hoses and brake booster line.",
                "Check STFT/LTFT at idle vs 2500 rpm for leak signature.",
            ],
            likely_causes=["Intake leak", "PCV hose leak", "Brake booster leak"],
            base_weight=1.1,
        ),

        # -------------------------
        # EXHAUST / EGR-ish symptoms (generic)
        # -------------------------
        TriageRule(
            name="Exhaust restriction / performance loss",
            category="engine",
            required_tags=["hesitation"],
            optional_tags=["misfire"],
            dtcs_any=["P0420", "P0430"],
            checks=[
                "Check exhaust backpressure if power loss severe.",
                "Verify misfire/fuel trim issues are not primary cause.",
            ],
            likely_causes=["Catalyst restriction", "Collapsed exhaust component"],
            base_weight=0.9,
        ),

        # -------------------------
        # MORE VIBRATION / NOISE BUCKETS
        # -------------------------
        TriageRule(
            name="Vibration at idle (engine mount / misfire / accessory)",
            category="engine",
            required_tags=["vibration"],
            contexts_any=["at_idle"],
            optional_tags=["rough_idle", "misfire"],
            checks=[
                "Confirm vibration at idle in gear vs park.",
                "Inspect engine/trans mounts; check misfire data; inspect accessory drive.",
            ],
            likely_causes=["Engine mount wear", "Idle misfire", "Accessory/belt issue"],
            base_weight=1.0,
        ),
        TriageRule(
            name="Noise when turning (CV/axle or steering component)",
            category="driveline",
            required_tags=["noise"],
            contexts_any=["when_turning"],
            checks=[
                "Confirm click/pop vs groan; inspect CV boots and axle play.",
                "Inspect steering stops and suspension joints.",
            ],
            likely_causes=["CV joint wear", "Axle issue", "Steering/suspension joint"],
            base_weight=1.0,
        ),
        TriageRule(
            name="Noise on acceleration (driveline/clunk)",
            category="driveline",
            required_tags=["noise"],
            contexts_any=["when_accelerating"],
            checks=[
                "Inspect driveshaft/U-joints; check mounts and differential lash.",
                "Check for loose heat shields contacting under load.",
            ],
            likely_causes=["U-joint wear", "Mount failure", "Exhaust/heat shield contact"],
            base_weight=0.95,
        ),
        TriageRule(
            name="Noise on deceleration (driveline/diff)",
            category="driveline",
            required_tags=["noise"],
            contexts_any=["when_decelerating"],
            checks=[
                "Inspect differential fluid/condition and backlash.",
                "Inspect driveshaft and mounts; check for bearing noise.",
            ],
            likely_causes=["Differential wear", "Bearing noise", "Driveshaft/mount issue"],
            base_weight=0.95,
        ),

        # -------------------------
        # EXTRA COMMON DTC BUCKETS (broad)
        # -------------------------
        TriageRule(
            name="Fuel pressure / rail system performance",
            category="fuel",
            required_tags=["hesitation"],
            dtcs_any=["P0087", "P0089", "P0191"],
            checks=[
                "Verify fuel pressure actual vs desired under load.",
                "Inspect fuel supply (pump/filter) and electrical to pump.",
            ],
            likely_causes=["Weak pump", "Restriction", "Sensor issue"],
            base_weight=1.0,
        ),
        TriageRule(
            name="Injector circuit / balance issue",
            category="fuel",
            required_tags=["misfire"],
            dtcs_any=["P0201", "P0202", "P0203", "P0204", "P0205", "P0206", "P0207", "P0208"],
            checks=[
                "Check injector electrical (resistance, control signal).",
                "Perform injector balance/disable test if supported.",
            ],
            likely_causes=["Injector failure", "Wiring issue", "ECM driver concern"],
            base_weight=0.95,
        ),
        TriageRule(
            name="Knock sensor / performance / spark retard",
            category="engine",
            required_tags=["hesitation"],
            dtcs_any=["P0327", "P0332", "P0328", "P0333"],
            checks=[
                "Inspect knock sensor wiring/connectors; check for water intrusion.",
                "Verify fuel quality; check for pinging under load.",
            ],
            likely_causes=["Sensor/wiring issue", "Fuel quality", "Mechanical noise"],
            base_weight=0.9,
        ),
        TriageRule(
            name="Engine coolant thermostat rationality",
            category="cooling",
            required_tags=["overheating"],
            dtcs_any=["P0128"],
            checks=[
                "Verify warm-up curve; check thermostat operation.",
                "Check coolant level and trapped air.",
            ],
            likely_causes=["Thermostat stuck open/closed", "Low coolant", "Sensor bias"],
            base_weight=1.0,
        ),
        TriageRule(
            name="Misfire damage prevention / catalyst protection",
            category="engine",
            required_tags=["misfire"],
            dtcs_any=["P0420", "P0430"],
            checks=[
                "Resolve misfire root cause before replacing catalyst.",
                "Check fuel trims and O2 sensor response after repair.",
            ],
            likely_causes=["Prolonged misfire damaging catalyst", "Rich running condition"],
            base_weight=0.9,
        ),

        # -------------------------
        # COLD START BUCKETS (if your parser includes cold_start)
        # -------------------------
        TriageRule(
            name="Cold-start rough idle / misfire tendency",
            category="engine",
            required_tags=["rough_idle"],
            optional_tags=["misfire"],
            contexts_any=["cold_start"],
            checks=[
                "Compare cold vs hot trims; check for intake leaks and injector leak-down.",
                "Verify plug condition and coil performance under cold conditions.",
            ],
            likely_causes=["Injector leak-down", "Ignition weakness", "Vacuum leak"],
            base_weight=0.95,
        ),
    ]

    # Add a handful of generic “catch-all” rules to ensure something useful appears.
    rules.extend(
        [
            TriageRule(
                name="Generic engine performance complaint (start here)",
                category="engine",
                required_tags=["hesitation"],
                checks=[
                    "Scan for DTCs and freeze frame; verify fuel trims.",
                    "Check intake leaks, ignition condition, and fuel pressure.",
                ],
                likely_causes=["Fuel/air imbalance", "Ignition issue", "Sensor plausibility issue"],
                base_weight=0.85,
            ),
            TriageRule(
                name="Generic abnormal noise complaint (start here)",
                category="general",
                required_tags=["noise"],
                checks=[
                    "Clarify when noise occurs (braking/turning/accelerating).",
                    "Inspect for loose shields, fasteners, and worn chassis joints.",
                ],
                likely_causes=["Loose component", "Wear in chassis/driveline", "Brake wear"],
                base_weight=0.85,
            ),
            TriageRule(
                name="Generic vibration complaint (start here)",
                category="general",
                required_tags=["vibration"],
                checks=[
                    "Clarify speed range and whether braking/accel affects it.",
                    "Start with tires/wheels, then driveline and braking checks.",
                ],
                likely_causes=["Tires/wheels", "Driveline", "Brakes"],
                base_weight=0.85,
            ),
        ]
    )

    for r in rules:
        session.add(r)
    session.commit()
