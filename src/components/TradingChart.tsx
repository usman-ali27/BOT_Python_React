import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { motion } from 'framer-motion';

interface ChartProps {
  data: { time: string; price: number }[];
}

export const TradingChart: React.FC<ChartProps> = ({ data }) => {
  const minPrice = Math.min(...data.map(d => d.price)) - 2;
  const maxPrice = Math.max(...data.map(d => d.price)) + 2;

  return (
    <div className="w-full h-full min-h-[300px] p-4 overflow-hidden flex flex-col" style={{ minWidth: 0, minHeight: 0 }}>
      <ResponsiveContainer width="100%" height="100%" minHeight={300}>
        <AreaChart data={data} margin={{ top: 10, right: 0, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#D4AF37" stopOpacity={0.15}/>
              <stop offset="100%" stopColor="#D4AF37" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
          <XAxis 
            dataKey="time" 
            axisLine={false} 
            tickLine={false} 
            tick={{ fontSize: 9, fill: '#888888', fontWeight: 'bold' }}
            interval={Math.round(data.length / 4)} 
          />
          <YAxis 
            domain={[minPrice, maxPrice]} 
            orientation="right" 
            axisLine={false} 
            tickLine={false} 
            tick={{ fontSize: 9, fill: '#888888', fontWeight: 'bold' }}
            width={45}
          />
          <Tooltip 
            contentStyle={{ backgroundColor: '#16181D', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '4px', fontSize: '10px' }}
            labelStyle={{ color: '#888888', marginBottom: '4px' }}
            itemStyle={{ color: '#D4AF37', fontWeight: 'bold' }}
            cursor={{ stroke: 'rgba(255,215,0,0.2)', strokeWidth: 1 }}
          />
          <Area 
            type="monotone" 
            dataKey="price" 
            stroke="#D4AF37" 
            fillOpacity={1} 
            fill="url(#colorPrice)" 
            strokeWidth={1.5}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};
