import React from 'react';
import { motion } from 'framer-motion';
import { ArrowRight, LogIn, Zap } from 'lucide-react';
import ScrollExpand from '../ScrollExpand';
import heroImage from '../../assets/hero-microgrid.svg';

/**
 * Scroll-driven hero. The frame starts as a small rounded card and expands to
 * full-bleed as the user scrolls, at which point the Sign In prompt fades in
 * over the image. Clicking either button hands off to the app's existing,
 * fully-wired login/dashboard flow (handleStart) rather than duplicating
 * auth logic here.
 */
export default function Hero({ onSignIn, onTryDemo }) {
  return (
    <div className="relative">
      <ScrollExpand
        src={heroImage}
        alt="Solar panel array on a green hillside microgrid site"
        title="Plan Your Microgrid"
        scrollHint="Scroll to sign in"
        useWindowScroll
        startWidth={46}
        startHeight={62}
        startRadius={28}
        endRadius={0}
        mediaZoom={1.25}
        scrollDistance={1.15}
        holdDistance={0.85}
        overlayScrim={0.5}
      >
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="flex flex-col items-center gap-6 px-6"
        >
          <div className="flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/10 border border-white/20 text-emerald-300 text-xs font-bold tracking-wider uppercase backdrop-blur-sm">
            <Zap className="w-3.5 h-3.5" />
            Microgrid Feasibility Engine
          </div>

          <h2 className="text-2xl sm:text-3xl md:text-4xl font-black text-white text-center tracking-tight max-w-2xl">
            Sign in to save projects and portfolio history
          </h2>

          <div className="flex flex-col sm:flex-row items-center gap-4">
            <button
              type="button"
              onClick={onSignIn}
              className="px-8 py-3.5 bg-gradient-to-r from-amber-500 to-emerald-500 hover:from-amber-400 hover:to-emerald-400 text-slate-950 font-bold rounded-xl text-sm transition shadow-xl shadow-amber-500/30 flex items-center gap-2"
            >
              <LogIn className="w-4 h-4" /> Sign In
            </button>
            <button
              type="button"
              onClick={onTryDemo}
              className="px-8 py-3.5 border border-white/30 hover:border-white/60 bg-white/5 hover:bg-white/10 text-white font-semibold rounded-xl text-sm transition flex items-center gap-2 backdrop-blur-sm"
            >
              Continue as Guest <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </motion.div>
      </ScrollExpand>
    </div>
  );
}
