//+------------------------------------------------------------------+
//|                                          HermesStructure.mq5     |
//|          Hermes AI Agent - SMC Structure Visualiser              |
//|  Reads from the Hermes mt5_bridge feed and paints:              |
//|    - Fair Value Gaps (bullish=blue, bearish=orange)              |
//|    - Order Blocks   (bullish=green box, bearish=red box)         |
//|    - BOS/CHoCH markers                                           |
//|    - Liquidity levels (dashed lines)                             |
//|  Run alongside HermesEA on the same chart.                       |
//+------------------------------------------------------------------+
#property copyright "Hermes Team"
#property version   "1.00"
#property indicator_chart_window
#property indicator_plots 0

#include <Zmq/Zmq.mqh>

input int    InpDrawPort      = 5556;   // Draw command port (must match EA)
input int    InpMaxFVG        = 10;     // Max FVGs to keep visible
input int    InpMaxOB         = 8;      // Max Order Blocks to keep
input color  InpBullFVGColor  = clrDeepSkyBlue;
input color  InpBearFVGColor  = clrOrange;
input color  InpBullOBColor   = clrMediumSeaGreen;
input color  InpBearOBColor   = clrCrimson;
input color  InpBOSColor      = clrYellow;
input color  InpLiqColor      = clrViolet;
input bool   InpShowFVG       = true;
input bool   InpShowOB        = true;
input bool   InpShowBOS       = true;
input bool   InpShowLiq       = true;
input int    InpFVGOpacity    = 20;     // Box fill opacity 0-100

string PREFIX = "HMS_";
int    g_object_count = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   ObjectsDeleteAll(0, PREFIX);
   Print("[HermesStructure] Initialised. Waiting for draw commands on port ", InpDrawPort, ".");
   Print("[HermesStructure] Objects will be prefixed: ", PREFIX);
   Print("[HermesStructure] Toggle layers: FVG=", InpShowFVG, " OB=", InpShowOB,
         " BOS=", InpShowBOS, " Liq=", InpShowLiq);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   // Keep objects on chart when indicator is removed so user can study them
   // ObjectsDeleteAll(0, PREFIX);
   Print("[HermesStructure] Detached. Drawn objects remain on chart.");
}

//+------------------------------------------------------------------+
// Draw helpers
//+------------------------------------------------------------------+

void DrawFVG(string id, datetime t1, datetime t2, double hi, double lo, bool bullish)
{
   if(!InpShowFVG) return;
   string name = PREFIX + "FVG_" + id;
   color  c    = bullish ? InpBullFVGColor : InpBearFVGColor;
   ObjectDelete(0, name);
   if(ObjectCreate(0, name, OBJ_RECTANGLE, 0, t1, hi, t2, lo))
   {
      ObjectSetInteger(0, name, OBJPROP_COLOR,   c);
      ObjectSetInteger(0, name, OBJPROP_STYLE,   STYLE_DOT);
      ObjectSetInteger(0, name, OBJPROP_WIDTH,   1);
      ObjectSetInteger(0, name, OBJPROP_FILL,    true);
      ObjectSetInteger(0, name, OBJPROP_BACK,    true);
      ObjectSetString(0,  name, OBJPROP_TOOLTIP, (bullish ? "Bullish" : "Bearish") + " FVG");
   }
}

void DrawOrderBlock(string id, datetime t1, datetime t2, double hi, double lo, bool bullish)
{
   if(!InpShowOB) return;
   string name = PREFIX + "OB_" + id;
   color  c    = bullish ? InpBullOBColor : InpBearOBColor;
   ObjectDelete(0, name);
   if(ObjectCreate(0, name, OBJ_RECTANGLE, 0, t1, hi, t2, lo))
   {
      ObjectSetInteger(0, name, OBJPROP_COLOR,   c);
      ObjectSetInteger(0, name, OBJPROP_STYLE,   STYLE_SOLID);
      ObjectSetInteger(0, name, OBJPROP_WIDTH,   2);
      ObjectSetInteger(0, name, OBJPROP_FILL,    true);
      ObjectSetInteger(0, name, OBJPROP_BACK,    true);
      ObjectSetString(0,  name, OBJPROP_TOOLTIP, (bullish ? "Bullish" : "Bearish") + " Order Block");
   }
   // Label
   string lbl = PREFIX + "OB_LBL_" + id;
   ObjectDelete(0, lbl);
   if(ObjectCreate(0, lbl, OBJ_TEXT, 0, t1, bullish ? lo - Point()*10 : hi + Point()*10))
   {
      ObjectSetString(0,  lbl, OBJPROP_TEXT,      bullish ? "OB+" : "OB-");
      ObjectSetInteger(0, lbl, OBJPROP_COLOR,     c);
      ObjectSetInteger(0, lbl, OBJPROP_FONTSIZE,  7);
   }
}

void DrawBOS(string id, datetime t, double price, bool is_bos)
{
   if(!InpShowBOS) return;
   string name = PREFIX + (is_bos ? "BOS_" : "CHOCH_") + id;
   ObjectDelete(0, name);
   if(ObjectCreate(0, name, OBJ_HLINE, 0, t, price))
   {
      ObjectSetInteger(0, name, OBJPROP_COLOR,   InpBOSColor);
      ObjectSetInteger(0, name, OBJPROP_STYLE,   STYLE_DASH);
      ObjectSetInteger(0, name, OBJPROP_WIDTH,   1);
      ObjectSetString(0,  name, OBJPROP_TOOLTIP, is_bos ? "BOS" : "CHoCH");
   }
   string lbl = PREFIX + (is_bos ? "BOS_" : "CHOCH_") + id + "_LBL";
   ObjectDelete(0, lbl);
   if(ObjectCreate(0, lbl, OBJ_TEXT, 0, t, price))
   {
      ObjectSetString(0,  lbl, OBJPROP_TEXT,      is_bos ? "BOS" : "CHoCH");
      ObjectSetInteger(0, lbl, OBJPROP_COLOR,     InpBOSColor);
      ObjectSetInteger(0, lbl, OBJPROP_FONTSIZE,  8);
      ObjectSetInteger(0, lbl, OBJPROP_ANCHOR,    ANCHOR_LEFT_LOWER);
   }
}

void DrawLiquidity(string id, datetime t, double price, bool is_high)
{
   if(!InpShowLiq) return;
   string name = PREFIX + "LIQ_" + id;
   ObjectDelete(0, name);
   if(ObjectCreate(0, name, OBJ_HLINE, 0, t, price))
   {
      ObjectSetInteger(0, name, OBJPROP_COLOR, InpLiqColor);
      ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DOT);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
      ObjectSetString(0,  name, OBJPROP_TOOLTIP, (is_high ? "Buy-side" : "Sell-side") + " Liquidity");
   }
   string lbl = PREFIX + "LIQ_LBL_" + id;
   ObjectDelete(0, lbl);
   if(ObjectCreate(0, lbl, OBJ_TEXT, 0, t, price))
   {
      ObjectSetString(0,  lbl, OBJPROP_TEXT,     is_high ? "BSL" : "SSL");
      ObjectSetInteger(0, lbl, OBJPROP_COLOR,    InpLiqColor);
      ObjectSetInteger(0, lbl, OBJPROP_FONTSIZE, 7);
   }
}

//+------------------------------------------------------------------+
// Parse a draw-command JSON and dispatch to the right draw function
//+------------------------------------------------------------------+
void ProcessDrawCommand(string json)
{
   // Reuse the same JSON helpers as in HermesEA
   string cmd  = ExtractField(json, "cmd");
   string type = ExtractField(json, "type");
   string id   = ExtractField(json, "id");

   if(cmd == "clear")
   {
      ObjectsDeleteAll(0, PREFIX);
      ChartRedraw(0);
      Print("[HermesStructure] Chart cleared.");
      return;
   }

   if(cmd == "delete")
   {
      ObjectsDeleteAll(0, PREFIX + "_" + id);
      ChartRedraw(0);
      return;
   }

   if(cmd != "draw") return;

   double price1 = StringToDouble(ExtractField(json, "price1"));
   double price2 = StringToDouble(ExtractField(json, "price2"));
   datetime t1   = (datetime)StringToInteger(ExtractField(json, "time1"));
   datetime t2   = (datetime)StringToInteger(ExtractField(json, "time2"));
   if(t1 == 0) t1 = TimeCurrent();
   if(t2 == 0) t2 = TimeCurrent() + PeriodSeconds()*5;

   string sub = ExtractField(json, "subtype");
   bool   bullish = (ExtractField(json, "direction") == "bullish" ||
                     ExtractField(json, "color") == "green");

   if(type == "fvg")
      DrawFVG(id, t1, t2, MathMax(price1, price2), MathMin(price1, price2), bullish);
   else if(type == "ob")
      DrawOrderBlock(id, t1, t2, MathMax(price1, price2), MathMin(price1, price2), bullish);
   else if(type == "bos")
      DrawBOS(id, t1, price1, true);
   else if(type == "choch")
      DrawBOS(id, t1, price1, false);
   else if(type == "liquidity")
      DrawLiquidity(id, t1, price1, bullish);
   else
   {
      // Generic fallback: hline
      string name = PREFIX + type + "_" + id;
      ObjectDelete(0, name);
      if(ObjectCreate(0, name, OBJ_HLINE, 0, t1, price1))
      {
         ObjectSetInteger(0, name, OBJPROP_COLOR, clrSilver);
         ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DOT);
      }
   }

   ChartRedraw(0);
   g_object_count++;
}

string ExtractField(string json, string key)
{
   string kp = "\"" + key + "\":";
   int pos = StringFind(json, kp);
   if(pos == -1) return "";
   int start = pos + StringLen(kp);
   while(start < StringLen(json))
   {
      ushort ch = StringGetCharacter(json, start);
      if(ch == ' ' || ch == '"') start++;
      else break;
   }
   int end = start;
   while(end < StringLen(json))
   {
      ushort ch = StringGetCharacter(json, end);
      if(ch == '"' || ch == ',' || ch == '}' || ch == '\r' || ch == '\n') break;
      end++;
   }
   return StringSubstr(json, start, end - start);
}

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
{
   return rates_total;
}
