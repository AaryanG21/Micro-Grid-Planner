import React from 'react';
import { motion } from 'framer-motion';
import { useReducedMotionSafe } from '../../hooks/useReducedMotionSafe';

export default function OrbitRing({ size = 340 }) {
  const prefersReduced = useReducedMotionSafe();

  const radius = 110;
  const center = size / 2;

  // 4 icons: Solar, Wind, Battery, Grid (No purple/violet, no gradients)
  const icons = [
    {
      id: 'solar',
      angle: 0,
      label: 'Solar PV',
      color: '#f59e0b',
      svgPath: (
        <path
          d="M12 3v2m0 14v2m9-9h-2M5 12H3m15.364-6.364l-1.414 1.414M7.05 16.95l-1.414 1.414M18.364 18.364l-1.414-1.414M7.05 7.05L5.636 5.636M12 8a4 4 0 100 8 4 4 0 000-8z"
          stroke="#f59e0b"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      ),
    },
    {
      id: 'wind',
      angle: 90,
      label: 'Wind',
      color: '#06b6d4',
      svgPath: (
        <path
          d="M14.828 14.828a4 4 0 10-5.656-5.656l-4.242 4.242a8 8 0 1111.314 0l-1.416-1.416zM12 12m-2 0a2 2 0 104 0 2 2 0 10-4 0"
          stroke="#06b6d4"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      ),
    },
    {
      id: 'battery',
      angle: 180,
      label: 'Battery',
      color: '#10b981',
      svgPath: (
        <g stroke="#10b981" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round">
          <rect x="2" y="7" width="16" height="10" rx="2" />
          <path d="M18 10v4" />
          <path d="M6 12h4" />
        </g>
      ),
    },
    {
      id: 'grid',
      angle: 270,
      label: 'Grid',
      color: '#38bdf8',
      svgPath: (
        <path
          d="M13 10V3L4 14h7v7l9-11h-7z"
          stroke="#38bdf8"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      ),
    },
  ];

  return (
    <div
      className="relative flex items-center justify-center select-none"
      style={{ width: `${size}px`, height: `${size}px` }}
    >
      <svg
        viewBox={`0 0 ${size} ${size}`}
        className="w-full h-full overflow-visible"
      >
        {/* Outer Dashed Halo */}
        <motion.circle
          cx={center}
          cy={center}
          r={radius + 30}
          fill="none"
          stroke="#334155"
          strokeWidth="1.5"
          strokeDasharray="6 8"
          style={{ transformOrigin: `${center}px ${center}px` }}
          animate={prefersReduced ? {} : { rotate: -360 }}
          transition={{ duration: 40, ease: 'linear', repeat: Infinity }}
        />

        {/* Orbit Path Guide Ring */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="#1e293b"
          strokeWidth="2"
        />

        {/* Spokes (SVG Lines) */}
        {icons.map((icon, i) => {
          const rad = (icon.angle * Math.PI) / 180;
          const x2 = center + radius * Math.cos(rad);
          const y2 = center + radius * Math.sin(rad);

          return (
            <motion.line
              key={`spoke-${icon.id}`}
              x1={center}
              y1={center}
              x2={x2}
              y2={y2}
              stroke="#64748b"
              strokeWidth="1.5"
              strokeDasharray="4 4"
              initial={{ opacity: 0.15 }}
              animate={prefersReduced ? {} : { opacity: [0.15, 0.4, 0.15] }}
              transition={{
                duration: 2.4,
                ease: 'easeInOut',
                repeat: Infinity,
                delay: i * 0.3,
              }}
            />
          );
        })}

        {/* Central Hub (Solid fill, no gradients, no purple) */}
        <motion.g
          style={{ transformOrigin: `${center}px ${center}px` }}
          animate={prefersReduced ? {} : { scale: [1, 1.08, 1] }}
          transition={{ duration: 2.4, ease: 'easeInOut', repeat: Infinity }}
        >
          <circle
            cx={center}
            cy={center}
            r="28"
            fill="#0f172a"
            stroke="#10b981"
            strokeWidth="2"
          />
          <g transform={`translate(${center - 12}, ${center - 12})`}>
            <path
              d="M13 10V3L4 14h7v7l9-11h-7z"
              fill="#10b981"
              stroke="#34d399"
              strokeWidth="1.5"
              transform="scale(0.8) translate(3, 3)"
            />
          </g>
        </motion.g>

        {/* Orbit Group */}
        <motion.g
          style={{ transformOrigin: `${center}px ${center}px` }}
          animate={prefersReduced ? {} : { rotate: 360 }}
          transition={{ duration: 24, ease: 'linear', repeat: Infinity }}
        >
          {icons.map((icon) => {
            const rad = (icon.angle * Math.PI) / 180;
            const cx = center + radius * Math.cos(rad);
            const cy = center + radius * Math.sin(rad);

            return (
              <motion.g
                key={`icon-node-${icon.id}`}
                style={{ transformOrigin: `${cx}px ${cy}px` }}
                animate={prefersReduced ? {} : { rotate: -360 }}
                transition={{ duration: 24, ease: 'linear', repeat: Infinity }}
              >
                <circle
                  cx={cx}
                  cy={cy}
                  r="22"
                  fill="#0f172a"
                  stroke={icon.color}
                  strokeWidth="2"
                />
                <g transform={`translate(${cx - 10}, ${cy - 10})`}>
                  {React.cloneElement(icon.svgPath, {
                    width: 20,
                    height: 20,
                    viewBox: '0 0 24 24',
                  })}
                </g>
              </motion.g>
            );
          })}
        </motion.g>
      </svg>
    </div>
  );
}
