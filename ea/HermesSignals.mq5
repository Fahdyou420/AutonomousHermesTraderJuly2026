//+------------------------------------------------------------------+
//|                                            HermesSignals.mq5     |
//|          Hermes AI Agent - Trade Signal Visualiser               |
//|  Paints on the chart:                                            |
//|    - Agent entry arrows (BUY=up green, SELL=down red)            |
//|    - SL line (red dash)                                          |
//|    - TP line (green dash)                                        |
//|    - Trade outcome markers (won=star, lost=cross)                |
//|    - Current bias label (top-left corner)                        |
//+------------------------------------------------------------------+
#property copyright "Hermes Team"
#property version   "1.00"
#property indicator_chart_window
#property indicator_plots 0

string PREFIX = "HMS_SIG_";

input color InpBuyColor   = clrLimeGreen;
input color InpSellColor  = clrRed;
input color InpSLColor    = clrOrangeRed;
input color InpTPColor    = clrMediumSeaGreen;
input color InpBiasColor  = clrWhite;
input int   InpArrowSize  = 2;
input bool  InpShowBias   = true;

//+------------------------------------------------------------------+
int OnInit()
{
   ObjectsDeleteAll(0, PREFIX);
   if(InpShowBias) DrawBiasLabel("NEUTRAL");
   Print("[HermesSignals] Initialised. Waiting for signal commands.");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   Print("[HermesSignals] Detached.");
}

//+------------------------------------------------------------------+
void DrawBiasLabel(string bias)
{
   string name = PREFIX + "BIAS_LABEL";
   ObjectDelete(0, name);
   color c = clrGold;
   if(bias == "BULLISH")  c = clrLimeGreen;
   if(bias == "BEARISH")  c = clrCrimson;
   if(bias == "NEUTRAL")  c = clrSilver;
   if(ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0))
   {
      ObjectSetString(0,  name, OBJPROP_TEXT,      "HERMES BIAS: " + bias);
      ObjectSetInteger(0, name, OBJPROP_COLOR,     c);
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE,  9);
      ObjectSetInteger(0, name, OBJPROP_CORNER,    CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_XDISTANCE, 10);
      ObjectSetInteger(0, name, OBJPROP_YDISTANCE, 20);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE,false);
   }
}

void DrawSignal(string id, datetime t, double entry, double sl, double tp, bool is_buy, string notes)
{
   // Entry arrow
   string arr_name = PREFIX + "ENTRY_" + id;
   ObjectDelete(0, arr_name);
   ENUM_OBJECT arrow = is_buy ? OBJ_ARROW_UP : OBJ_ARROW_DOWN;
   double arr_price  = is_buy ? (entry - Point()*30) : (entry + Point()*30);
   color arr_color   = is_buy ? InpBuyColor : InpSellColor;
   if(ObjectCreate(0, arr_name, arrow, 0, t, arr_price))
   {
      ObjectSetInteger(0, arr_name, OBJPROP_COLOR,    arr_color);
      ObjectSetInteger(0, arr_name, OBJPROP_WIDTH,    InpArrowSize);
      ObjectSetString(0,  arr_name, OBJPROP_TOOLTIP,  (is_buy ? "BUY" : "SELL") + " | " + notes);
   }

   // Entry dashed line
   string ent_name = PREFIX + "ENT_" + id;
   ObjectDelete(0, ent_name);
   if(ObjectCreate(0, ent_name, OBJ_HLINE, 0, t, entry))
   {
      ObjectSetInteger(0, ent_name, OBJPROP_COLOR, arr_color);
      ObjectSetInteger(0, ent_name, OBJPROP_STYLE, STYLE_DASH);
      ObjectSetInteger(0, ent_name, OBJPROP_WIDTH, 1);
   }

   // SL line
   if(sl > 0)
   {
      string sl_name = PREFIX + "SL_" + id;
      ObjectDelete(0, sl_name);
      if(ObjectCreate(0, sl_name, OBJ_HLINE, 0, t, sl))
      {
         ObjectSetInteger(0, sl_name, OBJPROP_COLOR, InpSLColor);
         ObjectSetInteger(0, sl_name, OBJPROP_STYLE, STYLE_DOT);
         ObjectSetInteger(0, sl_name, OBJPROP_WIDTH, 1);
         ObjectSetString(0,  sl_name, OBJPROP_TOOLTIP, "SL: " + DoubleToString(sl, _Digits));
      }
      string sl_lbl = PREFIX + "SL_LBL_" + id;
      ObjectDelete(0, sl_lbl);
      if(ObjectCreate(0, sl_lbl, OBJ_TEXT, 0, t, sl))
      {
         ObjectSetString(0,  sl_lbl, OBJPROP_TEXT,     "SL");
         ObjectSetInteger(0, sl_lbl, OBJPROP_COLOR,    InpSLColor);
         ObjectSetInteger(0, sl_lbl, OBJPROP_FONTSIZE, 7);
      }
   }

   // TP line
   if(tp > 0)
   {
      string tp_name = PREFIX + "TP_" + id;
      ObjectDelete(0, tp_name);
      if(ObjectCreate(0, tp_name, OBJ_HLINE, 0, t, tp))
      {
         ObjectSetInteger(0, tp_name, OBJPROP_COLOR, InpTPColor);
         ObjectSetInteger(0, tp_name, OBJPROP_STYLE, STYLE_DOT);
         ObjectSetInteger(0, tp_name, OBJPROP_WIDTH, 1);
         ObjectSetString(0,  tp_name, OBJPROP_TOOLTIP, "TP: " + DoubleToString(tp, _Digits));
      }
      string tp_lbl = PREFIX + "TP_LBL_" + id;
      ObjectDelete(0, tp_lbl);
      if(ObjectCreate(0, tp_lbl, OBJ_TEXT, 0, t, tp))
      {
         ObjectSetString(0,  tp_lbl, OBJPROP_TEXT,     "TP");
         ObjectSetInteger(0, tp_lbl, OBJPROP_COLOR,    InpTPColor);
         ObjectSetInteger(0, tp_lbl, OBJPROP_FONTSIZE, 7);
      }
   }

   ChartRedraw(0);
}

void DrawTradeOutcome(string id, datetime t, double price, bool won)
{
   string name = PREFIX + "OUTCOME_" + id;
   ObjectDelete(0, name);
   ENUM_OBJECT marker = won ? OBJ_ARROW_CHECK : OBJ_ARROW_STOP;
   color c = won ? clrLimeGreen : clrRed;
   if(ObjectCreate(0, name, marker, 0, t, price))
   {
      ObjectSetInteger(0, name, OBJPROP_COLOR,    c);
      ObjectSetInteger(0, name, OBJPROP_WIDTH,    2);
      ObjectSetString(0,  name, OBJPROP_TOOLTIP,  won ? "WIN" : "LOSS");
   }
   ChartRedraw(0);
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

void ProcessCommand(string json)
{
   string cmd  = ExtractField(json, "cmd");
   string type = ExtractField(json, "type");
   string id   = ExtractField(json, "id");

   if(cmd == "clear_signals")
   {
      ObjectsDeleteAll(0, PREFIX);
      ChartRedraw(0);
      return;
   }

   if(cmd == "update_bias")
   {
      DrawBiasLabel(ExtractField(json, "bias"));
      return;
   }

   if(type == "signal" && cmd == "draw")
   {
      datetime t    = (datetime)StringToInteger(ExtractField(json, "time1"));
      if(t == 0) t  = TimeCurrent();
      double entry  = StringToDouble(ExtractField(json, "entry_price"));
      double sl     = StringToDouble(ExtractField(json, "sl"));
      double tp     = StringToDouble(ExtractField(json, "tp"));
      bool   is_buy = (ExtractField(json, "direction") == "BUY");
      string notes  = ExtractField(json, "notes");
      DrawSignal(id, t, entry, sl, tp, is_buy, notes);
   }
   else if(type == "outcome" && cmd == "draw")
   {
      datetime t   = (datetime)StringToInteger(ExtractField(json, "time1"));
      double price = StringToDouble(ExtractField(json, "price1"));
      bool   won   = (ExtractField(json, "result") == "win");
      DrawTradeOutcome(id, t, price, won);
   }
}

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
