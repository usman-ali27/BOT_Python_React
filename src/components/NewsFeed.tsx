import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { TrendingUp, TrendingDown, Info, ShieldAlert } from 'lucide-react';

interface NewsItem {
  id: string;
  title: string;
  impact: 'HIGH' | 'MEDIUM' | 'LOW';
  sentiment: number;
}

export const NewsFeed: React.FC<{ items: NewsItem[] }> = ({ items }) => {
  return (
    <div className="flex flex-col gap-4">
      <div className="space-y-4 max-h-[500px] overflow-y-auto pr-2 custom-scrollbar">
        <AnimatePresence mode="popLayout">
          {items.map((item) => (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="p-4 bg-[#16181D] border border-[rgba(255,255,255,0.05)] rounded-[6px] group hover:border-[#D4AF37]/30 transition-all duration-300"
            >
              <div className="flex gap-4">
                <div className={`mt-1 flex items-center justify-center w-8 h-8 rounded-full ${item.sentiment > 0 ? 'bg-[rgba(0,255,133,0.05)] text-[#00FF85]' : 'bg-[rgba(255,77,77,0.05)] text-[#FF4D4D]'}`}>
                  {item.sentiment > 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <span className={`tag ${
                      item.impact === 'HIGH' ? 'tag-gold' : 
                      item.impact === 'MEDIUM' ? 'tag-blue' : 
                      'bg-[#23262D] text-[#888888]'
                    }`}>
                      {item.impact} IMPACT
                    </span>
                    <span className="text-[0.6rem] text-[#888888] font-bold uppercase tracking-widest">Global Economics</span>
                  </div>
                  <p className="text-[0.8rem] text-[#E0E0E0] leading-snug font-medium line-clamp-2">{item.title}</p>
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
      {items.length === 0 && (
        <div className="text-center py-10 text-[#888888] flex flex-col items-center gap-3">
          <ShieldAlert size={24} className="opacity-20" />
          <p className="text-[0.65rem] font-bold uppercase tracking-[2px]">News Guard: Buffer Clear</p>
        </div>
      )}
    </div>
  );
};
