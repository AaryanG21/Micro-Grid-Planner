import React, { useEffect } from 'react';
import { motion } from 'framer-motion';
import { useReducedMotionSafe } from '../../hooks/useReducedMotionSafe';

export default function SolarAssemblyIntro({ onComplete }) {
  const prefersReduced = useReducedMotionSafe();

  useEffect(() => {
    const duration = prefersReduced ? 800 : 3600;
    const timer = setTimeout(() => {
      if (onComplete) {
        onComplete();
      }
    }, duration);
    return () => clearTimeout(timer);
  }, [onComplete, prefersReduced]);

  if (prefersReduced) {
    return (
      <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-slate-950 text-emerald-400 font-body p-4">
        <svg viewBox="0 0 1000 600" className="w-full max-w-4xl h-auto overflow-visible">
          {/* Sun */}
          <circle cx="200" cy="90" r="45" fill="#f59e0b" opacity="0.9" />
          {/* Ground Line */}
          <line x1="100" y1="480" x2="900" y2="480" stroke="#334155" strokeWidth="4" strokeLinecap="round" />
          {/* Pole */}
          <rect x="390" y="240" width="20" height="240" rx="4" fill="#64748b" />
          {/* Bracket */}
          <rect x="280" y="230" width="240" height="12" rx="3" fill="#94a3b8" />
          {/* Solar Panels */}
          <g fill="#0284c7" stroke="#38bdf8" strokeWidth="2">
            <rect x="355" y="90" width="90" height="130" rx="6" />
            <rect x="255" y="90" width="90" height="130" rx="6" />
            <rect x="455" y="90" width="90" height="130" rx="6" />
          </g>
          {/* Wire */}
          <path d="M 400 240 L 400 480 L 700 480" fill="none" stroke="#10b981" strokeWidth="4" strokeDasharray="8 4" />
          {/* Battery */}
          <g transform="translate(700, 440)">
            <rect x="0" y="0" width="60" height="40" rx="6" fill="#059669" stroke="#34d399" strokeWidth="2" />
            <rect x="60" y="12" width="6" height="16" rx="2" fill="#34d399" />
          </g>
          {/* Status text */}
          <text x="500" y="550" textAnchor="middle" fill="#10b981" fontSize="22" fontWeight="600" className="font-heading tracking-wide">
            MICROGRID SYSTEM ONLINE
          </text>
        </svg>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-slate-950 text-emerald-400 font-body p-4 select-none">
      <div className="relative w-full max-w-4xl h-auto flex flex-col items-center justify-center">
        <svg viewBox="0 0 1000 600" className="w-full h-auto overflow-visible">
          {/* Sun Rise */}
          <g>
            <motion.circle
              cx="200"
              cy={480}
              r="45"
              fill="#f59e0b"
              initial={{ cy: 480, opacity: 0 }}
              animate={{ cy: 90, opacity: 1 }}
              transition={{ duration: 1.6, delay: 1.6, ease: 'easeOut' }}
            />
            {/* Sun Rays Rotation */}
            <motion.g
              style={{ transformOrigin: '200px 90px' }}
              initial={{ rotate: 0, opacity: 0 }}
              animate={{ rotate: 360, opacity: 1 }}
              transition={{
                rotate: { duration: 8, delay: 2.4, ease: 'linear', repeat: Infinity },
                opacity: { duration: 0.5, delay: 2.4 }
              }}
            >
              {[0, 45, 90, 135, 180, 225, 270, 315].map((deg) => (
                <line
                  key={deg}
                  x1="200"
                  y1="32"
                  x2="200"
                  y2="20"
                  stroke="#fbbf24"
                  strokeWidth="3"
                  strokeLinecap="round"
                  transform={`rotate(${deg} 200 90)`}
                />
              ))}
            </motion.g>
          </g>

          {/* Ground Line */}
          <motion.line
            x1="100"
            y1="480"
            x2="900"
            y2="480"
            stroke="#334155"
            strokeWidth="4"
            strokeLinecap="round"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.5, delay: 0 }}
          />

          {/* Pole */}
          <motion.rect
            x="390"
            y="240"
            width="20"
            height="240"
            rx="4"
            fill="#64748b"
            style={{ transformOrigin: '400px 480px' }}
            initial={{ scaleY: 0 }}
            animate={{ scaleY: 1 }}
            transition={{ duration: 0.6, delay: 0.4, ease: 'easeOut' }}
          />

          {/* Mounting Bracket */}
          <motion.g
            style={{ transformOrigin: '400px 240px' }}
            initial={{ rotate: -90, opacity: 0 }}
            animate={{ rotate: 0, opacity: 1 }}
            transition={{ duration: 0.5, delay: 1.0, type: 'spring', stiffness: 120 }}
          >
            <rect x="230" y="234" width="340" height="12" rx="4" fill="#94a3b8" />
          </motion.g>

          {/* Panel 1 */}
          <motion.g
            initial={{ y: -150, rotate: -8 }}
            animate={{ y: 90, rotate: 0 }}
            transition={{ duration: 0.6, delay: 1.3, type: 'spring', bounce: 0.5 }}
          >
            <rect x="355" y="0" width="90" height="135" rx="6" fill="#0284c7" stroke="#38bdf8" strokeWidth="2" />
            <line x1="385" y1="0" x2="385" y2="135" stroke="#38bdf8" strokeWidth="1" strokeOpacity="0.5" />
            <line x1="415" y1="0" x2="415" y2="135" stroke="#38bdf8" strokeWidth="1" strokeOpacity="0.5" />
            <line x1="355" y1="45" x2="445" y2="45" stroke="#38bdf8" strokeWidth="1" strokeOpacity="0.5" />
            <line x1="355" y1="90" x2="445" y2="90" stroke="#38bdf8" strokeWidth="1" strokeOpacity="0.5" />
          </motion.g>

          {/* Panel 2 */}
          <motion.g
            initial={{ x: -300 }}
            animate={{ x: 255 }}
            transition={{ duration: 0.6, delay: 1.5, type: 'spring', bounce: 0.5 }}
          >
            <rect x="0" y="90" width="90" height="135" rx="6" fill="#0284c7" stroke="#38bdf8" strokeWidth="2" />
            <line x1="30" y1="90" x2="30" y2="225" stroke="#38bdf8" strokeWidth="1" strokeOpacity="0.5" />
            <line x1="60" y1="90" x2="60" y2="225" stroke="#38bdf8" strokeWidth="1" strokeOpacity="0.5" />
            <line x1="0" y1="135" x2="90" y2="135" stroke="#38bdf8" strokeWidth="1" strokeOpacity="0.5" />
            <line x1="0" y1="180" x2="90" y2="180" stroke="#38bdf8" strokeWidth="1" strokeOpacity="0.5" />
          </motion.g>

          {/* Panel 3 */}
          <motion.g
            initial={{ x: 1000 }}
            animate={{ x: 455 }}
            transition={{ duration: 0.6, delay: 1.7, type: 'spring', bounce: 0.5 }}
          >
            <rect x="0" y="90" width="90" height="135" rx="6" fill="#0284c7" stroke="#38bdf8" strokeWidth="2" />
            <line x1="30" y1="90" x2="30" y2="225" stroke="#38bdf8" strokeWidth="1" strokeOpacity="0.5" />
            <line x1="60" y1="90" x2="60" y2="225" stroke="#38bdf8" strokeWidth="1" strokeOpacity="0.5" />
            <line x1="0" y1="135" x2="90" y2="135" stroke="#38bdf8" strokeWidth="1" strokeOpacity="0.5" />
            <line x1="0" y1="180" x2="90" y2="180" stroke="#38bdf8" strokeWidth="1" strokeOpacity="0.5" />
          </motion.g>

          {/* Wire Draw */}
          <motion.path
            d="M 400 240 L 400 480 L 700 480"
            fill="none"
            stroke="#10b981"
            strokeWidth="4"
            strokeLinecap="round"
            strokeDasharray="8 4"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.6, delay: 2.1 }}
          />

          {/* Battery Icon */}
          <motion.g
            transform="translate(700, 440)"
            style={{ transformOrigin: '730px 460px' }}
            initial={{ scale: 0.4 }}
            animate={{ scale: 1 }}
            transition={{ duration: 0.4, delay: 2.5, type: 'spring' }}
          >
            <rect x="0" y="0" width="60" height="40" rx="6" fill="#059669" stroke="#34d399" strokeWidth="2" />
            <rect x="60" y="12" width="6" height="16" rx="2" fill="#34d399" />
            <path d="M 22 20 L 32 10 L 28 20 L 38 20 L 28 30 L 32 20 Z" fill="#fef08a" />
          </motion.g>

          {/* Pulse Ring */}
          <motion.circle
            cx="730"
            cy="460"
            r="30"
            fill="none"
            stroke="#34d399"
            strokeWidth="2"
            style={{ transformOrigin: '730px 460px' }}
            initial={{ scale: 0.5, opacity: 0 }}
            animate={{ scale: [0.5, 3, 0.5], opacity: [0, 1, 0] }}
            transition={{ duration: 1, delay: 2.7, repeat: Infinity }}
          />

          {/* Status text */}
          <motion.text
            x="500"
            y="520"
            textAnchor="middle"
            fill="#10b981"
            fontSize="22"
            fontWeight="700"
            letterSpacing="0.1em"
            className="font-heading"
            initial={{ y: 520, opacity: 0 }}
            animate={{ y: 530, opacity: 1 }}
            transition={{ duration: 0.5, delay: 2.9 }}
          >
            MICROGRID SYSTEM ONLINE
          </motion.text>
        </svg>
      </div>
    </div>
  );
}
