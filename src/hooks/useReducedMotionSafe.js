import { useReducedMotion } from 'framer-motion';

export function useReducedMotionSafe() {
  const prefersReduced = useReducedMotion();
  return prefersReduced;
}
