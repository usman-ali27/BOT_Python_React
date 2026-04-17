import React from 'react';
import { motion } from 'framer-motion';

export const AccountStats = ({ 
  status, progressToTarget, targetAmount, currentProfit,
  totalPnL, activeTradesCount, calculateVolatility,
  mt5Status, autoTrading
}: any) => {
  return (
    <>
      <div>
        <div className="text-[0.7rem] font-bold uppercase text-[#888888] mb-4 flex justify-between items-center tracking-widest">
          Account Phase {status.phase}
          <span className="tag tag-gold">Prop Eval</span>
        </div>
        
        <div className="mb-6">
          <div className="flex justify-between items-end mb-2">
            <span className="text-[0.65rem] text-[#888888] uppercase font-bold">Target Profit</span>
            <span className="text-[0.8rem] font-mono text-[#D4AF37]">{progressToTarget.toFixed(1)}%</span>
          </div>
          <div className="h-[4px] bg-[#23262D] rounded-full overflow-hidden">
            <motion.div 
              initial={{ width: 0 }}
              animate={{ width: `${progressToTarget}%` }}
              className="h-full bg-gradient-to-r from-[#D4AF37] to-[#D4AF37]/50"
            />
          </div>
          <div className="mt-2 font-mono text-[0.85rem] text-right">
            ${currentProfit.toFixed(2)} / ${targetAmount.toLocaleString()}
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <div className="flex justify-between items-center mb-1">
              <span className="text-[0.65rem] text-[#888888] uppercase font-bold">Daily Drawdown</span>
              <span className={`text-[0.7rem] font-mono ${status.dailyLoss > 0.04 ? 'text-[#FF4D4D]' : 'text-zinc-500'}`}>
                {(status.dailyLoss * 100).toFixed(2)}%
              </span>
            </div>
            <div className="h-[2px] bg-[#23262D] rounded-full overflow-hidden">
              <div className="h-full bg-[#FF4D4D]" style={{ width: `${(status.dailyLoss / 0.045) * 100}%` }}></div>
            </div>
          </div>

          <div>
            <div className="flex justify-between items-center mb-1">
              <span className="text-[0.65rem] text-[#888888] uppercase font-bold">Max Drawdown</span>
              <span className={`text-[0.7rem] font-mono ${status.totalLoss > 0.08 ? 'text-[#FF4D4D]' : 'text-zinc-500'}`}>
                {(status.totalLoss * 100).toFixed(2)}%
              </span>
            </div>
            <div className="h-[2px] bg-[#23262D] rounded-full overflow-hidden">
              <div className="h-full bg-[#FF4D4D]" style={{ width: `${(status.totalLoss / 0.10) * 100}%` }}></div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 mt-2">
          <div className="bg-[#16181D] p-3 rounded-[6px] border border-[rgba(255,255,255,0.05)]">
            <div className="text-[0.6rem] text-[#888888] mb-1 uppercase font-bold tracking-widest">Equity</div>
            <div className="font-mono text-[0.85rem] font-bold text-[#E0E0E0]">${status.equity.toLocaleString()}</div>
          </div>
          <div className="bg-[#16181D] p-3 rounded-[6px] border border-[rgba(255,255,255,0.05)]">
            <div className="text-[0.6rem] text-[#888888] mb-1 uppercase font-bold tracking-widest">PnL</div>
            <div className={`font-mono text-[0.85rem] font-bold ${totalPnL >= 0 ? 'text-[#00FF85]' : 'text-[#FF4D4D]'}`}>
              {totalPnL >= 0 ? '+' : ''}{totalPnL.toFixed(2)}
            </div>
          </div>
          <div className="bg-[#16181D] p-3 rounded-[6px] border border-[rgba(255,255,255,0.05)]">
            <div className="text-[0.6rem] text-[#888888] mb-1 uppercase font-bold tracking-widest">Orders</div>
            <div className="font-mono text-[0.85rem] font-bold text-[#E0E0E0]">{activeTradesCount}</div>
          </div>
          <div className="bg-[#16181D] p-3 rounded-[6px] border border-[rgba(255,255,255,0.05)]">
            <div className="text-[0.6rem] text-[#888888] mb-1 uppercase font-bold tracking-widest">Volatility</div>
            <div className="font-mono text-[0.85rem] font-bold text-[#D4AF37]">{calculateVolatility()}</div>
          </div>
        </div>
      </div>
      
      <div className="mt-auto border-t border-[rgba(255,255,255,0.05)] pt-6">
        <div className="text-[0.7rem] font-bold uppercase text-[#888888] mb-3 tracking-widest flex justify-between">
           Bot Status 
           <span className={`text-[0.6rem] ${mt5Status === 'CONNECTED' ? 'text-[#00FF85]' : 'text-[#FF4D4D]'}`}>
             ● {mt5Status}
           </span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div className="bg-[#23262D] p-2 rounded-[4px] text-center border border-[rgba(255,255,255,0.05)]">
            <div className="text-[0.6rem] text-[#888888] uppercase">Grid Mode</div>
            <div className="text-[0.7rem] text-[#00FF85] font-bold">{autoTrading ? 'Active' : 'Standby'}</div>
          </div>
          {/* <div className="bg-[#23262D] p-2 rounded-[4px] text-center border border-[rgba(255,255,255,0.05)]">
            <div className="text-[0.6rem] text-[#888888] uppercase">Leverage</div>
            <div className="text-[0.7rem] text-[#00D1FF] font-bold">1:500</div>
          </div> */}
        </div>
      </div>
    </>
  );
};
