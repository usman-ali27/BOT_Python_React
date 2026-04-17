import { format } from 'date-fns';

export interface Trade {
  id: string;
  symbol: string;
  type: 'BUY' | 'SELL';
  entryPrice: number;
  exitPrice?: number;
  lotSize: number;
  stopLoss: number;
  takeProfit: number;
  status: 'OPEN' | 'CLOSED';
  pnl: number;
  timestamp: Date;
}

export interface MarketData {
  price: number;
  timestamp: Date;
  high: number;
  low: number;
}

export interface AccountStatus {
  balance: number;
  equity: number;
  initialBalance: number;
  phase: 1 | 2;
  dailyLoss: number;
  totalLoss: number;
  targetReached: boolean;
}

export interface NewsEvent {
  id: string;
  title: string;
  impact: 'HIGH' | 'MEDIUM' | 'LOW';
  timestamp: Date;
  sentiment?: number; // -1 to 1
}

export interface EngineConfig {
  gridSpacing: number; // In $ for XAU/USD (min $15 per user req)
  levels: number;
  minLotSize: number;
  maxLotSize: number;
  trailingStopDistance: number;
  takeProfitDistance: number;
  stopLossDistance: number;
  htfBias: 'BULLISH' | 'BEARISH' | 'NEUTRAL'; // 1H/15M Analysis
  executionTF: '1M' | '5M';
}

export class TradingEngine {
  private trades: Trade[] = [];
  private balance: number;
  private initialBalance: number;
  private phase: 1 | 2;
  private config: EngineConfig = {
    gridSpacing: 15.0, // $15 Difference as requested
    levels: 8,
    minLotSize: 0.01,
    maxLotSize: 0.04,
    trailingStopDistance: 2.0,
    takeProfitDistance: 6.0,
    stopLossDistance: 4.5,
    htfBias: 'NEUTRAL',
    executionTF: '1M'
  };
  
  // Market State for ICT Simulation
  private marketEvents: string[] = [];
  private lastFvgPrice: number | null = null;
  
  // Prop Firm Specs
  private readonly MAX_DAILY_LOSS_PCT = 0.05;
  private readonly MAX_TOTAL_LOSS_PCT = 0.10;
  private readonly PHASE1_TARGET_PCT = 0.10;
  private readonly PHASE2_TARGET_PCT = 0.05;

  private dailyStartEquity: number;

  constructor(initialBalance: number, phase: 1 | 2 = 1, config?: Partial<EngineConfig>) {
    this.initialBalance = initialBalance;
    this.balance = initialBalance;
    this.dailyStartEquity = initialBalance;
    this.phase = phase;
    if (config) {
      this.config = { ...this.config, ...config };
    }
  }

  public setConfig(newConfig: Partial<EngineConfig>) {
    this.config = { ...this.config, ...newConfig };
  }

  public getConfig() {
    return this.config;
  }

  public setBalance(newBalance: number) {
    this.initialBalance = newBalance;
    this.balance = newBalance;
    this.dailyStartEquity = newBalance;
    this.trades = []; // Reset current simulation to match MT5 state
  }

  public getStatus(): AccountStatus {
    const pnl = this.trades.reduce((sum, t) => sum + t.pnl, 0);
    const equity = this.balance + pnl;
    const totalLoss = (this.initialBalance - equity) / this.initialBalance;
    const dailyLoss = (this.dailyStartEquity - equity) / this.dailyStartEquity;
    
    const target = this.phase === 1 ? this.PHASE1_TARGET_PCT : this.PHASE2_TARGET_PCT;
    const currentProfit = (equity - this.initialBalance) / this.initialBalance;

    return {
      balance: this.balance,
      equity,
      initialBalance: this.initialBalance,
      phase: this.phase,
      dailyLoss: Math.max(0, dailyLoss),
      totalLoss: Math.max(0, totalLoss),
      targetReached: currentProfit >= target
    };
  }

  public simulateGrid(currentPrice: number) {
    const openTrades = this.trades.filter(t => t.status === 'OPEN');
    if (openTrades.length >= this.config.levels) return;

    // HTF Alignment: Only open trades in direction of bias
    const lastTrade = openTrades[openTrades.length - 1];
    if (lastTrade && Math.abs(currentPrice - lastTrade.entryPrice) < this.config.gridSpacing) return;

    // ICT Concept Simulation: Detect FVG or Liquidity Sweep
    const roll = Math.random();
    let entryType: 'BUY' | 'SELL' | null = null;
    let eventLabel = "";

    if (roll > 0.92) {
      entryType = 'BUY';
      eventLabel = "FVG_LONG_REFILL [ICT]";
      this.lastFvgPrice = currentPrice;
    } else if (roll < 0.08) {
      entryType = 'SELL';
      eventLabel = "LIQUIDITY_SWEEP_REJECTION [ICT]";
    } else if (openTrades.length === 0) {
      // Manual/Engine opening based on HTF Bias
      if (this.config.htfBias === 'BULLISH') entryType = 'BUY';
      if (this.config.htfBias === 'BEARISH') entryType = 'SELL';
    }

    if (!entryType) return;
    if (this.config.htfBias !== 'NEUTRAL' && entryType !== (this.config.htfBias === 'BULLISH' ? 'BUY' : 'SELL')) return;

    const lotSize = entryType === 'BUY' ? this.config.minLotSize : this.config.maxLotSize; // Simulating "strength" scaling
    
    this.marketEvents.push(eventLabel || "GRID_LEVEL_REACHED");
    if (this.marketEvents.length > 5) this.marketEvents.shift();

    this.trades.push({
      id: Math.random().toString(36).substr(2, 6).toUpperCase(),
      symbol: 'XAUUSD',
      type: entryType,
      entryPrice: currentPrice,
      lotSize: lotSize,
      stopLoss: entryType === 'BUY' ? currentPrice - this.config.stopLossDistance : currentPrice + this.config.stopLossDistance,
      takeProfit: entryType === 'BUY' ? currentPrice + this.config.takeProfitDistance : currentPrice - this.config.takeProfitDistance,
      status: 'OPEN',
      pnl: 0,
      timestamp: new Date()
    });
  }

  public getEvents() { return this.marketEvents; }

  public updateTrades(currentPrice: number) {
    this.trades = this.trades.map(trade => {
      if (trade.status !== 'OPEN') return trade;

      let tradeCopy = { ...trade };

      // Update Trailing Stop
      if (tradeCopy.type === 'BUY') {
        const potentialSL = currentPrice - this.config.trailingStopDistance;
        if (potentialSL > tradeCopy.stopLoss && currentPrice > tradeCopy.entryPrice) {
          tradeCopy.stopLoss = potentialSL;
        }
      } else {
        const potentialSL = currentPrice + this.config.trailingStopDistance;
        if (potentialSL < tradeCopy.stopLoss && currentPrice < tradeCopy.entryPrice) {
          tradeCopy.stopLoss = potentialSL;
        }
      }

      const multiplier = tradeCopy.type === 'BUY' ? 1 : -1;
      const pnl = (currentPrice - tradeCopy.entryPrice) * tradeCopy.lotSize * 100 * multiplier;
      tradeCopy.pnl = pnl;

      // Check SL/TP
      if (tradeCopy.type === 'BUY') {
        if (currentPrice >= tradeCopy.takeProfit || currentPrice <= tradeCopy.stopLoss) tradeCopy.status = 'CLOSED';
      } else {
        if (currentPrice <= tradeCopy.takeProfit || currentPrice >= tradeCopy.stopLoss) tradeCopy.status = 'CLOSED';
      }

      if (tradeCopy.status === 'CLOSED') {
        this.balance += tradeCopy.pnl;
      }
      return tradeCopy;
    });
  }

  public getTrades() { return this.trades; }
}
