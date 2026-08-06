import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useReducedMotionSafe } from '../../hooks/useReducedMotionSafe';

export default function MiniCalculator() {
  const [demoLoad, setDemoLoad] = useState(1000);
  const prefersReduced = useReducedMotionSafe();

  const estimatedSavings = Math.round(demoLoad * 0.42 * 365);
  const formattedSavings = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(estimatedSavings);

  return (
    <div className="w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-3xl p-8 md:p-12 shadow-2xl text-center my-16">
      <div className="inline-block px-4 py-2 bg-slate-800 border border-slate-700 rounded-full text-emerald-400 text-xs font-bold uppercase tracking-wider mb-4 font-body">
        Interactive Calculator
      </div>
      <h3 className="text-2xl md:text-3xl font-extrabold font-heading text-white mb-2">
        Instant ROI Estimator
      </h3>
      <p className="text-slate-400 font-body text-sm md:text-base mb-8 max-w-lg mx-auto leading-relaxed">
        Adjust your facility's average daily power load (kWh) to estimate potential annual grid offset savings.
      </p>

      <div className="space-y-8">
        <div className="flex flex-col space-y-2">
          <div className="flex justify-between items-center text-sm font-medium font-body">
            <span className="text-slate-400">Daily Energy Demand</span>
            <span className="text-emerald-400 text-lg font-bold font-heading">{demoLoad.toLocaleString()} kWh/day</span>
          </div>
          <input
            type="range"
            min="200"
            max="5000"
            step="50"
            value={demoLoad}
            onChange={(e) => setDemoLoad(Number(e.target.value))}
            className="w-full h-3 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
          />
          <div className="flex justify-between text-xs text-slate-500 font-body">
            <span>200 kWh</span>
            <span>2,500 kWh</span>
            <span>5,000 kWh</span>
          </div>
        </div>

        <div className="pt-8 border-t border-slate-800">
          <div className="text-xs uppercase font-bold text-slate-400 tracking-wider mb-2 font-body">
            Estimated Annual Savings
          </div>
          <motion.div
            key={demoLoad}
            initial={prefersReduced ? false : { scale: 0.9, opacity: 0 }}
            animate={prefersReduced ? false : { scale: 1, opacity: 1 }}
            transition={{ duration: 0.25, ease: 'easeOut' }}
            className="text-4xl md:text-5xl font-black font-heading text-emerald-400 py-2"
          >
            {formattedSavings}
          </motion.div>
          {/* Visible disclaimer line - NON-NEGOTIABLE */}
          <p className="text-xs text-slate-400 font-body mt-4 italic">
            Illustrative estimate — run a full site analysis for accurate figures.
          </p>
        </div>
      </div>
    </div>
  );
}
