//+------------------------------------------------------------------+
//|                                                     HermesEA.mq5 |
//|                             Hermes Autonomous AI Trading Agent   |
//+------------------------------------------------------------------+
#property copyright "Hermes Team"
#property link      "https://github.com/google/ai-studio"
#property version   "1.10"
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\SymbolInfo.mqh>
#include <Zmq/Zmq.mqh>

//--- Inputs
input string   InpDataHost         = "127.0.0.1";
input int      InpDataPort         = 5555;
input int      InpDrawPort         = 5556;
input int      InpOrderPort        = 5557;
input ulong    InpMagicNumber      = 20250001;
input int      InpMaxSlippage      = 10;
input int      InpHistoricalBars   = 500;
input bool     InpPushOnEveryTick  = false;

//--- Globals
CTrade         m_trade;
CPositionInfo  m_position;
CSymbolInfo    m_symbol;
Context        g_zmq_context;
Socket*        g_socket_data;
Socket*        g_socket_draw;
Socket*        g_socket_order;
datetime       g_last_bar_time;
string         g_instrument;
ENUM_TIMEFRAMES g_timeframe;

string GetSession(datetime time)
{
   MqlDateTime dt; TimeToStruct(time,dt); int hour=dt.hour;
   if(hour>=22||hour<7)  return "asian";
   if(hour>=7&&hour<12)  return "london";
   if(hour>=12&&hour<15) return "overlap";
   if(hour>=15&&hour<21) return "newyork";
   return "off";
}

string ExtractJsonString(string json,string key)
{
   string kp="\""+key+"\":"; int pos=StringFind(json,kp); if(pos==-1) return "";
   int start=pos+StringLen(kp);
   while(start<StringLen(json)){ushort ch=StringGetCharacter(json,start);if(ch==' '||ch==':'||ch=='"')start++;else break;}
   int end=start;
   while(end<StringLen(json)){ushort ch=StringGetCharacter(json,end);if(ch=='"'||ch==','||ch=='}'||ch=='\r'||ch=='\n')break;end++;}
   return StringSubstr(json,start,end-start);
}
double ExtractJsonDouble(string json,string key){string v=ExtractJsonString(json,key);return v==""?0.0:StringToDouble(v);}
int    ExtractJsonInt(string json,string key){string v=ExtractJsonString(json,key);return v==""?0:(int)StringToInteger(v);}

string EscapeString(string txt)
{
   StringReplace(txt,"\\","\\\\"); StringReplace(txt,"\"","\\\"");
   StringReplace(txt,"\n","\\n");  StringReplace(txt,"\r","\\r"); StringReplace(txt,"\t","\\t");
   return txt;
}

bool SendJson(string json)
{
   if(g_socket_data==NULL) return false;
   if(!g_socket_data.send(json)){Print("[!] ZMQ send fail: ",GetLastError());return false;}
   return true;
}

void PushAccountState()
{
   string p="{"
      +"\"type\":\"account\","
      +"\"login\":"+IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN))+","
      +"\"name\":\""+EscapeString(AccountInfoString(ACCOUNT_NAME))+"\","
      +"\"server\":\""+EscapeString(AccountInfoString(ACCOUNT_SERVER))+"\","
      +"\"currency\":\""+AccountInfoString(ACCOUNT_CURRENCY)+"\","
      +"\"leverage\":"+IntegerToString(AccountInfoInteger(ACCOUNT_LEVERAGE))+","
      +"\"balance\":"+DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE),2)+","
      +"\"equity\":"+DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY),2)+","
      +"\"margin\":"+DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN),2)+","
      +"\"free_margin\":"+DoubleToString(AccountInfoDouble(ACCOUNT_FREEMARGIN),2)+","
      +"\"profit\":"+DoubleToString(AccountInfoDouble(ACCOUNT_PROFIT),2)
      +"}";
   if(SendJson(p)) Print("[+] Account state pushed");
}

void PushOpenPositions()
{
   int total=PositionsTotal();
   if(total==0){SendJson("{\"type\":\"positions\",\"positions\":[]}");return;}
   string arr="[";
   for(int i=0;i<total;i++)
   {
      if(!m_position.SelectByIndex(i)) continue;
      if(i>0) arr+=",";
      arr+="{"
         +"\"ticket\":"+IntegerToString(m_position.Ticket())+","
         +"\"symbol\":\""+m_position.Symbol()+"\","
         +"\"type\":\""+(m_position.PositionType()==POSITION_TYPE_BUY?"BUY":"SELL")+"\","
         +"\"lots\":"+DoubleToString(m_position.Volume(),2)+","
         +"\"open_price\":"+DoubleToString(m_position.PriceOpen(),Digits())+","
         +"\"current_price\":"+DoubleToString(m_position.PriceCurrent(),Digits())+","
         +"\"sl\":"+DoubleToString(m_position.StopLoss(),Digits())+","
         +"\"tp\":"+DoubleToString(m_position.TakeProfit(),Digits())+","
         +"\"profit\":"+DoubleToString(m_position.Profit(),2)+","
         +"\"swap\":"+DoubleToString(m_position.Swap(),2)+","
         +"\"open_time\":"+IntegerToString((long)m_position.Time())+","
         +"\"magic\":"+IntegerToString(m_position.Magic())+","
         +"\"comment\":\""+EscapeString(m_position.Comment())+"\""
         +"}";
   }
   arr+="]";
   if(SendJson("{\"type\":\"positions\",\"positions\":"+arr+"}"))
      Print("[+] Positions pushed: ",total);
}

void PushTradeHistory()
{
   datetime from=TimeCurrent()-90*86400;
   HistorySelect(from,TimeCurrent());
   int total=HistoryDealsTotal();
   if(total==0){SendJson("{\"type\":\"history\",\"deals\":[]}");return;}
   int chunk_size=100,chunk_idx=0,count=0;
   string arr="[";
   for(int i=0;i<total;i++)
   {
      ulong ticket=HistoryDealGetTicket(i); if(ticket==0) continue;
      string sym=HistoryDealGetString(ticket,DEAL_SYMBOL); if(sym=="") continue;
      if(count>0) arr+=",";
      arr+="{"
         +"\"ticket\":"+IntegerToString((long)ticket)+","
         +"\"symbol\":\""+sym+"\","
         +"\"type\":"+IntegerToString((int)HistoryDealGetInteger(ticket,DEAL_TYPE))+","
         +"\"entry\":"+IntegerToString((int)HistoryDealGetInteger(ticket,DEAL_ENTRY))+","
         +"\"lots\":"+DoubleToString(HistoryDealGetDouble(ticket,DEAL_VOLUME),2)+","
         +"\"price\":"+DoubleToString(HistoryDealGetDouble(ticket,DEAL_PRICE),5)+","
         +"\"profit\":"+DoubleToString(HistoryDealGetDouble(ticket,DEAL_PROFIT),2)+","
         +"\"swap\":"+DoubleToString(HistoryDealGetDouble(ticket,DEAL_SWAP),2)+","
         +"\"commission\":"+DoubleToString(HistoryDealGetDouble(ticket,DEAL_COMMISSION),2)+","
         +"\"time\":"+IntegerToString(HistoryDealGetInteger(ticket,DEAL_TIME))+","
         +"\"comment\":\""+EscapeString(HistoryDealGetString(ticket,DEAL_COMMENT))+"\""
         +"}";
      count++;
      if(count>=chunk_size||i==total-1)
      {
         arr+="]";
         SendJson("{\"type\":\"history\",\"chunk_id\":"+IntegerToString(chunk_idx)+",\"deals\":"+arr+"}");
         chunk_idx++; arr="["; count=0;
      }
   }
   Print("[+] Trade history pushed: ",total," deals");
}

void PushHistoricalBars(int num_bars)
{
   if(num_bars<=0) return;
   MqlRates rates[]; ArraySetAsSeries(rates,false);
   int copied=CopyRates(g_instrument,g_timeframe,0,num_bars,rates);
   if(copied<=0){Print("[!] CopyRates failed: ",GetLastError());return;}
   Print("[*] Pushing ",copied," historical bars...");
   int chunk_size=200,total_chunks=(copied+chunk_size-1)/chunk_size;
   for(int ci=0;ci<total_chunks;ci++)
   {
      int start=ci*chunk_size,take=MathMin(chunk_size,copied-start);
      string body="{\"type\":\"historical_bars\","
         +"\"instrument\":\""+g_instrument+"\","
         +"\"timeframe\":\""+EnumToString(g_timeframe)+"\","
         +"\"chunk_id\":"+IntegerToString(ci)+","
         +"\"total_chunks\":"+IntegerToString(total_chunks)+","
         +"\"bars\":[";
      for(int i=0;i<take;i++)
      {
         int idx=start+i; if(i>0) body+=",";
         body+="{"
            +"\"t\":"+IntegerToString((long)rates[idx].time)+","
            +"\"o\":"+DoubleToString(rates[idx].open,Digits())+","
            +"\"h\":"+DoubleToString(rates[idx].high,Digits())+","
            +"\"l\":"+DoubleToString(rates[idx].low,Digits())+","
            +"\"c\":"+DoubleToString(rates[idx].close,Digits())+","
            +"\"v\":"+IntegerToString(rates[idx].tick_volume)+","
            +"\"s\":"+IntegerToString(rates[idx].spread)
            +"}";
      }
      body+="]}";
      if(!SendJson(body)){Print("[!] Bar chunk ",ci," failed.");return;}
      Sleep(10);
   }
   SendJson("{\"type\":\"historical_bars_complete\","
      +"\"instrument\":\""+g_instrument+"\","
      +"\"timeframe\":\""+EnumToString(g_timeframe)+"\","
      +"\"total_bars\":"+IntegerToString(copied)+"}");
   Print("[+] Historical bars done: ",copied);
}

int OnInit()
{
   g_instrument=Symbol(); g_timeframe=Period(); g_last_bar_time=0;
   m_trade.SetExpertMagicNumber(InpMagicNumber);
   if(!m_symbol.Name(g_instrument)){Print("[!] Symbol init failed");return INIT_FAILED;}
   Print("[*] Booting HermesEA on ",g_instrument," (",EnumToString(g_timeframe),")");

   g_socket_data =new Socket(g_zmq_context,ZMQ_PUSH);
   g_socket_draw =new Socket(g_zmq_context,ZMQ_PULL);
   g_socket_order=new Socket(g_zmq_context,ZMQ_PULL);
   g_socket_data.setLinger(1000); g_socket_draw.setLinger(1000); g_socket_order.setLinger(1000);

   string da="tcp://"+InpDataHost+":"+IntegerToString(InpDataPort);
   string dra="tcp://0.0.0.0:"+IntegerToString(InpDrawPort);
   string oa="tcp://0.0.0.0:"+IntegerToString(InpOrderPort);

   Print("[*] Connecting data socket to ",da);
   if(!g_socket_data.connect(da)){Print("[!] Data connect failed: ",GetLastError());return INIT_FAILED;}
   Print("[*] Binding draw socket to ",dra);
   if(!g_socket_draw.bind(dra)){Print("[!] Draw bind failed: ",GetLastError());return INIT_FAILED;}
   Print("[*] Binding order socket to ",oa);
   if(!g_socket_order.bind(oa)){Print("[!] Order bind failed: ",GetLastError());return INIT_FAILED;}

   Print("[+] Sockets ready. Pushing startup snapshot...");
   Sleep(500);
   PushAccountState(); Sleep(100);
   PushOpenPositions(); Sleep(100);
   PushTradeHistory(); Sleep(100);
   PushHistoricalBars(InpHistoricalBars);
   Print("[+] HermesEA v1.10 ready on ",g_instrument);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(g_socket_data !=NULL){delete g_socket_data; g_socket_data =NULL;}
   if(g_socket_draw !=NULL){delete g_socket_draw; g_socket_draw =NULL;}
   if(g_socket_order!=NULL){delete g_socket_order;g_socket_order=NULL;}
   Print("[+] HermesEA offline.");
}

void DrawObject(string j)
{
   string cmd=ExtractJsonString(j,"cmd"),t=ExtractJsonString(j,"type"),id="hermes_"+ExtractJsonString(j,"id");
   if(cmd=="clear"){ObjectsDeleteAll(0,"hermes_",-1,-1);ChartRedraw(0);return;}
   if(cmd=="delete"){ObjectDelete(0,id);ChartRedraw(0);return;}
   if(cmd!="draw") return;
   double p1=ExtractJsonDouble(j,"price1"),p2=ExtractJsonDouble(j,"price2");
   datetime t1=(datetime)ExtractJsonInt(j,"time1"),t2=(datetime)ExtractJsonInt(j,"time2");
   if(!t1)t1=TimeCurrent(); if(!t2)t2=TimeCurrent();
   string cn=ExtractJsonString(j,"color"),lbl=ExtractJsonString(j,"label"),sn=ExtractJsonString(j,"style");
   int w=ExtractJsonInt(j,"width"); if(w<=0)w=1;
   color c=clrSkyBlue;
   if(cn=="green")c=clrMediumSeaGreen; if(cn=="red")c=clrCrimson; if(cn=="blue")c=clrBlue;
   if(cn=="orange")c=clrDarkOrange;    if(cn=="cyan")c=clrCyan;   if(cn=="magenta")c=clrMagenta;
   if(cn=="yellow")c=clrYellow;
   ENUM_LINE_STYLE ls=STYLE_SOLID; if(sn=="dashed")ls=STYLE_DASH; if(sn=="dotted")ls=STYLE_DOT;
   ObjectDelete(0,id);
   if(t=="rect"&&ObjectCreate(0,id,OBJ_RECTANGLE,0,t1,p1,t2,p2))
      {ObjectSetInteger(0,id,OBJPROP_COLOR,c);ObjectSetInteger(0,id,OBJPROP_STYLE,ls);ObjectSetInteger(0,id,OBJPROP_WIDTH,w);ObjectSetString(0,id,OBJPROP_TOOLTIP,lbl);}
   else if(t=="hline"&&ObjectCreate(0,id,OBJ_HLINE,0,t1,p1))
      {ObjectSetInteger(0,id,OBJPROP_COLOR,c);ObjectSetInteger(0,id,OBJPROP_STYLE,ls);ObjectSetInteger(0,id,OBJPROP_WIDTH,w);}
   else if(t=="trendline"&&ObjectCreate(0,id,OBJ_TREND,0,t1,p1,t2,p2))
      {ObjectSetInteger(0,id,OBJPROP_COLOR,c);ObjectSetInteger(0,id,OBJPROP_STYLE,ls);ObjectSetInteger(0,id,OBJPROP_WIDTH,w);ObjectSetInteger(0,id,OBJPROP_RAY_RIGHT,false);}
   else if(t=="arrow")
      {ENUM_OBJECT at=cn=="red"?OBJ_ARROW_DOWN:OBJ_ARROW_UP;if(ObjectCreate(0,id,at,0,t1,p1)){ObjectSetInteger(0,id,OBJPROP_COLOR,c);ObjectSetString(0,id,OBJPROP_TEXT,lbl);}}
   else if(t=="label"&&ObjectCreate(0,id,OBJ_TEXT,0,t1,p1))
      {ObjectSetString(0,id,OBJPROP_TEXT,lbl);ObjectSetInteger(0,id,OBJPROP_COLOR,c);ObjectSetInteger(0,id,OBJPROP_FONTSIZE,10);}
   ChartRedraw(0);
}

void ExecuteOrder(string j)
{
   string action=ExtractJsonString(j,"action"),symbol=ExtractJsonString(j,"instrument");
   double lots=ExtractJsonDouble(j,"lots"),sl=ExtractJsonDouble(j,"sl"),tp=ExtractJsonDouble(j,"tp");
   string comment=ExtractJsonString(j,"comment"); int magic=ExtractJsonInt(j,"magic");
   if(symbol=="")symbol=g_instrument; if(magic<=0)magic=(int)InpMagicNumber;
   if(action=="REFRESH_ACCOUNT"){PushAccountState();PushOpenPositions();return;}
   if(action=="REFRESH_HISTORY"){PushTradeHistory();return;}
   if(action=="REFRESH_BARS"){int n=ExtractJsonInt(j,"bars");if(n<=0)n=InpHistoricalBars;PushHistoricalBars(n);return;}
   if(action=="CLEAR_CHART"){ObjectsDeleteAll(0,"hermes_");ObjectsDeleteAll(0,"HMS_");ChartRedraw(0);Print("[*] Chart objects cleared.");return;}
   if(action=="RUN_STRATEGY_TESTER")
   {
      // Cannot trigger MT5 Strategy Tester programmatically from EA context.
      // Instead we push the last N bars immediately so the Python backtester can use them.
      int n=ExtractJsonInt(j,"bars"); if(n<=0) n=5000;
      Print("[*] Strategy Tester data request: pushing ",n," bars via OnTester pipeline...");
      PushHistoricalBars(n);
      SendJson("{\"type\":\"strategy_tester_ready\",\"instrument\":\""+g_instrument+"\","
         +"\"timeframe\":\""+EnumToString(g_timeframe)+"\","
         +"\"bars\":"+IntegerToString(n)+"}");
      return;
   }
   bool res=false; ulong ticket=0;
   Print("[*] Order: ",action," ",symbol," lots=",lots);
   if(action=="BUY"){double ask=SymbolInfoDouble(symbol,SYMBOL_ASK);res=m_trade.Buy(lots,symbol,ask,sl,tp,comment);if(res)ticket=m_trade.ResultDeal();}
   else if(action=="SELL"){double bid=SymbolInfoDouble(symbol,SYMBOL_BID);res=m_trade.Sell(lots,symbol,bid,sl,tp,comment);if(res)ticket=m_trade.ResultDeal();}
   else if(action=="CLOSE"){for(int i=PositionsTotal()-1;i>=0;i--)if(m_position.SelectByIndex(i)&&m_position.Symbol()==symbol&&(m_position.Magic()==magic||m_position.Comment()==comment))if(m_trade.PositionClose(m_position.Ticket(),InpMaxSlippage))res=true;}
   else if(action=="MODIFY"){for(int i=PositionsTotal()-1;i>=0;i--)if(m_position.SelectByIndex(i)&&m_position.Symbol()==symbol&&(m_position.Magic()==magic||m_position.Comment()==comment))if(m_trade.PositionModify(m_position.Ticket(),sl,tp))res=true;}
   SendJson("{\"type\":\"trade_event\",\"action\":\""+action+"\",\"symbol\":\""+symbol+"\",\"result\":"+(res?"true":"false")+",\"ticket\":"+IntegerToString((long)ticket)+",\"comment\":\""+EscapeString(comment)+"\"}");
   Sleep(200); PushAccountState(); PushOpenPositions();
}

void OnTick()
{
   datetime cur=(datetime)SeriesInfoInteger(g_instrument,g_timeframe,SERIES_LASTBAR_DATE);
   if(cur!=g_last_bar_time && g_last_bar_time!=0)
   {
      // Push the just-closed bar (index 1 = previous bar = the one that just closed)
      string body="{"
         +"\"type\":\"bar_event\","
         +"\"instrument\":\""+g_instrument+"\","
         +"\"timeframe\":\""+EnumToString(g_timeframe)+"\","
         +"\"timestamp\":"+IntegerToString((long)g_last_bar_time)+","
         +"\"open\":"+DoubleToString(iOpen(g_instrument,g_timeframe,1),Digits())+","
         +"\"high\":"+DoubleToString(iHigh(g_instrument,g_timeframe,1),Digits())+","
         +"\"low\":"+DoubleToString(iLow(g_instrument,g_timeframe,1),Digits())+","
         +"\"close\":"+DoubleToString(iClose(g_instrument,g_timeframe,1),Digits())+","
         +"\"volume\":"+IntegerToString(iVolume(g_instrument,g_timeframe,1))+","
         +"\"spread\":"+IntegerToString(SymbolInfoInteger(g_instrument,SYMBOL_SPREAD))+","
         +"\"session\":\""+GetSession(g_last_bar_time)+"\""
         +"}";
      Print("[*] Bar closed: ",g_instrument," ",EnumToString(g_timeframe));
      SendJson(body);
      PushAccountState();
   }
   g_last_bar_time=cur;

   if(InpPushOnEveryTick)
   {
      string tick="{\"type\":\"tick\",\"instrument\":\""+g_instrument+"\","
         +"\"bid\":"+DoubleToString(SymbolInfoDouble(g_instrument,SYMBOL_BID),Digits())+","
         +"\"ask\":"+DoubleToString(SymbolInfoDouble(g_instrument,SYMBOL_ASK),Digits())+","
         +"\"timestamp\":"+IntegerToString((long)TimeCurrent())+"}";
      SendJson(tick);
   }

   ZmqMsg dm; while(g_socket_draw.recv(dm,true)){string s=dm.getData();if(s!="")DrawObject(s);}
   ZmqMsg om; while(g_socket_order.recv(om,true)){string s=om.getData();if(s!="")ExecuteOrder(s);}
}

double OnTester()
{
   MqlRates rates[]; ArraySetAsSeries(rates,false);
   int cc=CopyRates(g_instrument,g_timeframe,0,50000,rates);
   if(cc<=0) return 0.0;
   int cs=500,tc=(cc+cs-1)/cs;
   for(int ci=0;ci<tc;ci++)
   {
      int s=ci*cs,take=MathMin(cs,cc-s);
      string b="{\"type\":\"backtest_chunk\",\"chunk_id\":"+IntegerToString(ci)+",\"total_chunks\":"+IntegerToString(tc)+",\"rates\":[";
      for(int i=0;i<take;i++){int idx=s+i;if(i>0)b+=",";b+="{\"t\":"+IntegerToString((long)rates[idx].time)+",\"o\":"+DoubleToString(rates[idx].open,Digits())+",\"h\":"+DoubleToString(rates[idx].high,Digits())+",\"l\":"+DoubleToString(rates[idx].low,Digits())+",\"c\":"+DoubleToString(rates[idx].close,Digits())+",\"v\":"+IntegerToString(rates[idx].tick_volume)+",\"s\":"+IntegerToString(rates[idx].spread)+"}";}
      b+="]}";
      if(!SendJson(b)) return 0.0;
      Sleep(20);
   }
   SendJson("{\"type\":\"backtest_end\",\"instrument\":\""+g_instrument+"\",\"timeframe\":\""+EnumToString(g_timeframe)+"\"}");
   return 100.0;
}
