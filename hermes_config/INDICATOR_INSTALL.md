# Installing Hermes MT5 Custom Indicators

Two indicator files are in the `ea/` folder of this project.
Install them in MT5 so they paint the agent's analysis directly on your charts,
even when Hermes Desktop is not actively talking to the chart.

## Files

- `HermesStructure.mq5` — Paints FVGs, Order Blocks, BOS/CHoCH, Liquidity levels
- `HermesSignals.mq5`   — Paints trade entry arrows, SL/TP lines, bias label

## Install Steps

1. In MT5: **File → Open Data Folder**
2. Navigate to `MQL5\Indicators\`
3. Copy both `.mq5` files there
4. In MetaEditor (F4): open each file and press **F7** to compile
5. Back in MT5 chart: **Insert → Indicators → Custom** → find `HermesStructure` and `HermesSignals`
6. Add both to the same XAUUSD M15 chart where HermesEA is running

## What Each Indicator Does

### HermesStructure
Receives draw commands from the Hermes MCP server via the ZMQ draw socket (port 5556).
When the agent calls `visualise_analysis`, this indicator paints:
- Blue/orange boxes for bullish/bearish FVGs
- Green/red boxes for bullish/bearish Order Blocks
- Yellow dashed lines for BOS
- Cyan dashed lines for CHoCH
- Purple dots for liquidity pools

### HermesSignals
Receives signal commands from the MCP server.
When the agent calls `draw_trade_signal`, this paints:
- Green up arrow for BUY entries, red down arrow for SELL entries
- Red dotted line for Stop Loss
- Green dotted line for Take Profit
- Corner label showing current bias (BULLISH/BEARISH/NEUTRAL)

## Inputs (configurable in MT5 indicator settings)

HermesStructure:
- `InpDrawPort`: 5556 (must match EA's InpDrawPort)
- `InpShowFVG/OB/BOS/Liq`: toggle individual layers on/off
- Colors are fully customisable

HermesSignals:
- Colors for BUY/SELL/SL/TP lines
- Arrow size
- `InpShowBias`: toggle the corner bias label

## Notes

- The indicators do NOT need to run in the EA's window. They can be separate indicator panes.
- Objects remain on the chart even if you detach the indicator (for study purposes).
- To clear all agent objects: in the MT5 Objects List, filter by "HMS_" prefix and delete.
- Both indicators are passive — they receive draw commands, they don't generate signals themselves.
