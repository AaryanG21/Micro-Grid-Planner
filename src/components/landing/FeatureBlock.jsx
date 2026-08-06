import React from 'react';
import { motion } from 'framer-motion';
import { useReducedMotionSafe } from '../../hooks/useReducedMotionSafe';

export default function FeatureBlock({ title, caption, children }) {
  const prefersReduced = useReducedMotionSafe();

  return (
    <motion.div
      className="flex flex-col items-center bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-xl"
      initial={prefersReduced ? false : { opacity: 0, y: 60 }}
      whileInView={prefersReduced ? undefined : { opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.7, ease: 'easeOut' }}
    >
      <div className="w-full flex items-center justify-center mb-8 overflow-hidden rounded-xl bg-slate-950 p-4 border border-slate-800">
        {children}
      </div>
      <h3 className="text-xl md:text-2xl font-bold font-heading text-white mb-2 text-center tracking-tight">
        {title}
      </h3>
      <p className="text-slate-400 font-body text-sm md:text-base text-center leading-relaxed max-w-md">
        {caption}
      </p>
    </motion.div>
  );
}
