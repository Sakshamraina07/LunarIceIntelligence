import React, { useState } from 'react';
import { HelpCircle } from 'lucide-react';

interface TooltipProps {
  term: string;
  definition: string;
  children?: React.ReactNode;
}

export const Tooltip: React.FC<TooltipProps> = ({ term, definition, children }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <span className="relative inline-flex items-center gap-1 group">
      {children || <span className="font-semibold text-slate-200">{term}</span>}
      <button
        type="button"
        onMouseEnter={() => setIsOpen(true)}
        onMouseLeave={() => setIsOpen(false)}
        onClick={() => setIsOpen(!isOpen)}
        className="inline-flex items-center justify-center text-cyan-400/80 hover:text-cyan-300 transition focus:outline-none"
        aria-label={`Definition of ${term}`}
      >
        <HelpCircle className="w-3.5 h-3.5" />
      </button>

      {/* Hover Popup */}
      <span
        className={`absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-2.5 rounded-xl bg-slate-950/95 border border-cyan-500/40 text-slate-200 text-xs shadow-2xl backdrop-blur-xl z-50 pointer-events-none transition-all duration-200 ${
          isOpen ? 'opacity-100 scale-100' : 'opacity-0 scale-95 invisible'
        }`}
      >
        <span className="block font-bold text-cyan-300 mb-1 border-b border-slate-800 pb-1 text-[11px]">
          {term}
        </span>
        <span className="block text-[11px] text-slate-300 leading-relaxed font-normal">
          {definition}
        </span>
        {/* Caret */}
        <span className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 border-4 border-transparent border-t-slate-950" />
      </span>
    </span>
  );
};

export default Tooltip;
