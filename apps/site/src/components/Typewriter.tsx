import { useState, useEffect } from 'react';

const roles = ['trading desks', 'hedge funds', 'quant teams', 'equity research', 'private equity'];

const HOLD_DURATION = 2500;
const FLIP_DURATION = 400; // ms for the flip animation

export default function Typewriter() {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [flipping, setFlipping] = useState(false);

  useEffect(() => {
    const holdTimer = setTimeout(() => {
      setFlipping(true);
      const flipTimer = setTimeout(() => {
        setCurrentIndex((prev) => (prev + 1) % roles.length);
        setFlipping(false);
      }, FLIP_DURATION);
      return () => clearTimeout(flipTimer);
    }, HOLD_DURATION);

    return () => clearTimeout(holdTimer);
  }, [currentIndex]);

  return (
    <span className="typewriter-line">
      <span className={`flip-text ${flipping ? 'flip-out' : 'flip-in'}`}>
        {roles[currentIndex]}
      </span>
    </span>
  );
}
