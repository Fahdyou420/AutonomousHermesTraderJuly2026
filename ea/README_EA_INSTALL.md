# Hermes Expert Advisor (EA) MetaTrader 5 Socket Installation Guide

This document describes the step-by-step procedure to compile, deploy, and configure the C++ ZeroMQ-backed Expert Advisor (`HermesEA.mq5`) within the MetaTrader 5 (MT5) environment on Windows.

---

## 1. Prerequisites & Library Downloads

The Hermes EA communicates with containerized python services via ZeroMQ sockets. This requires the `mql5-zmq` binding layer, which wraps the official C++ ZeroMQ DLL libraries for MQL5 compatibility.

### step 1.1: Download ZMQ bindings for MQL5
* Download the open-source **mql5-zmq** wrapper package from its repository on GitHub, or obtain the matching artifacts:
  - Repositories: [mql5-zmq (by Austin666)](https://github.com/austinj666/mql5-zmq) or [mql4-5-zmq (by dingmaotu)](https://github.com/dingmaotu/mql4-5-zmq).
* Specifically download:
  1. `Zmq.mqh` - The core MQL5 include header file.
  2. Compiled stable architecture binaries: `libzmq.dll` and `libsodium.dll` (usually available in the release downloads or repository bin folder, compiled for **64-bit Windows** matching MT5 terminal).

---

## 2. Placing File Assets into MT5 folder structures

Inside MetaTrader 5, locate your **Data Folder**:
1. Open your MT5 terminal on your Windows host.
2. At the top menu bar, click **File** -> **Open Data Folder**.
3. We will refer to this opened folder path as your `[MQL5_DATA_DIR]`.

Now, distribute the downloaded assets into their correct file locations exactly as listed below:

| Asset Name | Target Directory in `[MQL5_DATA_DIR]` | Purpose |
|:---|:---|:---|
| `Zmq.mqh` | `MQL5\Include\Zmq\Zmq.mqh` | Wrapper classes for Socket initializations. |
| `libzmq.dll` | `MQL5\Libraries\libzmq.dll` | Core ZeroMQ library wrapper. |
| `libsodium.dll` | `MQL5\Libraries\libsodium.dll` | Cryptographic/security dependencies for libzmq. |
| `HermesEA.mq5` | `MQL5\Experts\HermesEA.mq5` | Our custom SMC order processing agent EA. |

> **IMPORTANT PATH NOTE**: Make sure to create the `Zmq` directory inside `MQL5\Include\`, resulting in `MQL5\Include\Zmq` folder, then place `Zmq.mqh` inside it. This matches the EA code compilation line: `#include <Zmq/Zmq.mqh>`.

---

## 3. Compiling HermesEA in MetaEditor

Once all files are positioned in their folders:
1. Return to the MetaTrader 5 Terminal.
2. Press **F4** on your keyboard, or navigate to **Tools** -> **MetaQuotes Language Editor** to open MetaEditor.
3. In the left-hand **Navigator** panel of MetaEditor, expand `Experts` tree.
4. Double-click to open `HermesEA.mq5`.
5. Locate the **Compile** button at the top toolbar (or press **F7** on your keyboard).
6. Verify output logs in the "Errors" tab at the bottom.
   - If configured correctly, compilation will finish with `0 error(s), 0 warning(s)`.
   - This creates the executable file `HermesEA.ex5` in the same directory.

---

## 4. Configuring MT5 Permission Rules

To allow DLL imports so that MT5 can execute ZeroMQ client sockets:
1. In the MT5 Terminal menu bar, select **Tools** -> **Options** (or press `Ctrl+O`).
2. Select the **Expert Advisors** tab.
3. Tick the check box labeled **Allow DLL imports**.
4. *(Optional / Recommended)* Check **Allow WebRequest for listed URL** and add `http://host.docker.internal:7778` and `http://127.0.0.1:7778` to white-label host-level queries directly.
5. Click **OK**.

---

## 5. Attaching to a Chart and Input Configurations

1. Open a chart for **XAUUSD** (Gold / Dollar) in MT5.
2. Select the **M15** or **H1** timeframe as required.
3. Drag the compiled **HermesEA** expert from the Navigator window onto the active chart (or right-click and choose *Attach to Chart*).
4. A settings dialog window will open. Click on the **Inputs** tab to adjust parameters:

   * **InpDataHost**: Set to `127.0.0.1` (since the Docker host forwards port 5555, 5556, and 5557 directly to localhost).
   * **InpDataPort**: Set to `5555` (SMC Tick and Candlestick stream PUSH).
   * **InpDrawPort**: Set to `5556` (Drawing/lines subscriber PULL - binds in python).
   * **InpOrderPort**: Set to `5557` (Autonomous risk execution PULL - binds in python).
   * **InpMagicNumber**: `20250001` (A unique ID identifier prevent position overlaps).
   * **InpMaxSlippage**: `10` (Maximum allowable executing slip in standard pips).

5. In the **Common** tab, toggle **Allow Algo Trading** to *On*.
6. Click **OK** to activate the EA. You should see a hat icon turn blue or a status message on the upper right corner.

---

## 6. Historical Data Injection (Running a Backtest)

The Hermes EA supports backtesting, where it streams historical bars through the same ZeroMQ channel. This is used by the Hermes system to build backtest indicators or pre-populate ChromaDB vector indexes with older price action structure.

1. Open MT5 **Strategy Tester** window (`Ctrl+R`).
2. Select **HermesEA.ex5** in the *Expert Advisor* field.
3. Set *Symbol* to `XAUUSD`, and *Timeframe* to `M15` or `H1`.
4. Set *Date/Period* (e.g. Last Month, or a custom interval in 2025/2026).
5. Set *Execution* to match normal trading or **Every Tick** for highest structural fidelity.
6. Toggle **Visual mode with 3D display** to *On* if you want to inspect algorithmic drawings in real-time.
7. Click **Start**. The EA will stream bars back to the Docker containers via port 5555, where the `preprocessor` and `backtester` service containers consume them.

---

## 7. Common Errors and Troubleshooting

### Case A: "cannot open file Zmq/Zmq.mqh"
* **Check**: You placed `Zmq.mqh` in the wrong directory.
* **Fix**: Ensure the header file is located within a nested folder namely `MQL5\Include\Zmq\`, not directly under `Include`, and make sure it has the exact casing `.mqh` extension name.

### Case B: "Cannot call 'zmq_ctx_new' in DLL libraries" or "DLL loading safe-check failed"
* **Check**: DLL imports are disabled in MT5 options or the DLL is missing.
* **Fix**: Tick the **Allow DLL imports** setting under MT5 Options -> Expert Advisors. Also ensure `libzmq.dll` and `libsodium.dll` are both placed inside `MQL5\Libraries\`.

### Case C: Compiled EA keeps reconnecting or reporting socket errors
* **Check**: ZeroMQ socket port collisions or Docker is stopped.
* **Fix**: Run `docker-compose ps` to ensure that `hermes_redis` and `hermes_preprocessor` are running. Ensure no other applications are holding port 5555, 5556, or 5557.

### Case D: "Symbol info not initialized for XAUUSD"
* **Check**: You attached the EA to an unsupported instrument first.
* **Fix**: Change chart symbol to `XAUUSD` and re-attach the expert. Make sure `Market Watch` in MT5 includes the symbol `XAUUSD` active.
