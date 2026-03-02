📌 Overview

This repository presents a deterministic, hardware-native Intrusion Detection System (IDS) IP core for Controller Area Network (CAN) security in automotive systems.

Unlike software-based IDS solutions, this design integrates directly into the CAN MAC datapath, enabling:

⚡ Wire-speed inspection (1 Mbps CAN)

⏱ Deterministic 43 ns inference latency

🛡 Active frame-level prevention

🔋 Ultra-low power consumption (13 mW)

🧠 99.2% F1-score detection accuracy

The architecture transforms a 21-tree Random Forest model into a pure combinational logic engine — eliminating DSPs, BRAMs, and software jitter.

🏗 System Architecture
📍 Hardware Integration

The IDS IP core is positioned:

CAN Transceiver → CAN MAC → [IDS IP Core] → RX FIFO → Host CPU

This inline placement ensures that every incoming CAN frame is inspected before reaching memory.

If an attack is detected, a Kill-Signal is generated to invalidate the frame within the prevention window.

🧠 Core Design Principles
1️⃣ Hardware-Native Machine Learning

21-tree Random Forest

Max depth: 10

Integer-only thresholds

Multiplier-free architecture

Fully deterministic 10-cycle pipeline

2️⃣ 74-bit Feature Manifold

Extracted directly from CAN frame:

Feature	Bit-width
Arbitration ID	11
DLC	4
First Byte	8
Last Byte	8
Byte Sum	11
Time Delta	32
Total	74 bits

Feature scaling uses:

Arithmetic shifters

LUT-based constant multiplier (×134)

No DSP slices used

⚙️ Microarchitecture

The IP core consists of three pipeline stages:

Feature Scaling (Multiplier-Free)

Parallel Tree Traversal Engine

Voting Aggregator (Majority Decision)

Inference Latency:

10 clock cycles @ 230.8 MHz = 43 ns

This provides a ~23× timing margin compared to 1 µs CAN bit-time.

📊 Implementation Results

Platform:
PYNQ-Z2 (Zynq-7020 FPGA)

🔧 Hardware Resource Utilization
Resource	Used	Utilization
LUTs	2,746	5.16%
FFs	1,170	1.10%
DSP	0	0%
BRAM	0	0%
🚀 Performance
Metric	Value
Fmax	230.8 MHz
Latency	43 ns
Dynamic Power	13 mW
Avg. F1-score	99.2%
🎯 Detection Performance
Attack Type	F1-score
DoS	99.98%
Fuzzing	99.10%
Spoofing	98.67%
Replay	99.09%

Dataset:
can-train-and-test

🆚 Comparison with State-of-the-Art
Work	Platform	Latency	Accuracy
BNN (FPGA)	Zynq	1.28 µs	98.4%
QNN (FPGA)	UltraScale+	210 ns	99.1%
ASIC RF	MPW	1.86 µs	99.2%
This Work	Zynq	43 ns	99.2%

✔ 43× faster than recent ASIC RF
✔ 30× faster than BNN FPGA solutions
✔ Zero DSP / BRAM usage

🔒 Threat Model

Assumed attacker:

Compromised internal ECU

Capable of injecting CAN frames

Detected attacks:

DoS (High-frequency injection)

Fuzzing

Spoofing

Replay

🏎 Functional Safety

Designed to comply with:

ISO 26262

Deterministic hardware execution simplifies formal safety verification.

📂 Repository Structure (Suggested)
├── rtl/
│   ├── feature_scaler.v
│   ├── tree_engine.v
│   ├── voting_aggregator.v
│   ├── ids_top.v
│
├── rom/
│   ├── tree_mem_init.hex
│
├── tb/
│   ├── ids_tb.v
│
├── dataset/
│   ├── preprocessing_scripts/
│
├── docs/
│   ├── architecture.pdf
│
└── README.md
🛠 How to Use
1️⃣ Synthesis

Tested on:

Vivado (Zynq-7020)

Target board: PYNQ-Z2

Add RTL → Set 230 MHz clock → Synthesize → Implement
2️⃣ Integration into CAN Controller

Connect:

feature_vector[73:0]
clk
rst_n
start

Outputs:

is_attack
valid_out
attack_votes[4:0]
🌍 Why This Matters

Traditional IDS systems:

Run in software

Non-deterministic latency

Cannot prevent frame commitment

This design:

Moves ML directly into silicon datapath

Guarantees fixed-time execution

Enables true active prevention

This bridges the gap between:

Machine Learning × Real-Time Automotive Safety × Hardware Design

📖 Citation

If you use this work, please cite:

Duong et al., Deterministic Hardware-Native IP Core for Wire-Speed CAN Intrusion Detection, 2026.

👨‍🔬 Authors

Vietnam-Korea University of Information and Communication Technology
University of Danang

📜 License

[Add your chosen license here]

🚀 Future Work

Support CAN-FD

ASIC tape-out optimization

Formal verification integration

Adaptive RF retraining flow
