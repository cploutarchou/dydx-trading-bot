import React from 'react';

type PageContainerSize = 'narrow' | 'default' | 'wide' | 'full';

interface PageContainerProps {
  children: React.ReactNode;
  className?: string;
  size?: PageContainerSize;
}

const sizeClasses: Record<PageContainerSize, string> = {
  narrow: 'max-w-5xl',
  default: 'max-w-6xl',
  wide: 'max-w-[1440px]',
  full: 'max-w-none',
};

export const PageContainer: React.FC<PageContainerProps> = ({
  children,
  className = '',
  size = 'default',
}) => {
  return (
    <div
      className={`page-reveal mx-auto w-full ${sizeClasses[size]} px-4 py-6 sm:px-6 sm:py-7 lg:px-8 lg:py-10 ${className}`.trim()}
    >
      {children}
    </div>
  );
};
