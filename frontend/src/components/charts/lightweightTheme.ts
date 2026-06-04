import {
    ColorType,
    createChart,
    type ChartOptions,
    type DeepPartial,
    type IChartApi,
} from 'lightweight-charts';

export interface TradingChartTheme {
  background: string;
  text: string;
  grid: string;
  border: string;
  crosshair: string;
}

const readThemeToken = (name: string, fallback: string): string => {
  if (typeof window === 'undefined') {
    return fallback;
  }
  const value = window.getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
};

export const getTradingChartTheme = (): TradingChartTheme => ({
  background: readThemeToken('--chart-bg', '#0f172a'),
  text: readThemeToken('--chart-text', '#cbd5e1'),
  grid: readThemeToken('--chart-grid', 'rgba(51, 65, 85, 0.25)'),
  border: readThemeToken('--chart-border', '#334155'),
  crosshair: readThemeToken('--chart-crosshair', 'rgba(148, 163, 184, 0.35)'),
});

const getBaseChartOptions = (): DeepPartial<ChartOptions> => {
  const theme = getTradingChartTheme();

  return {
    layout: {
      background: { type: ColorType.Solid, color: theme.background },
      textColor: theme.text,
      attributionLogo: false,
    },
    grid: {
      vertLines: { color: theme.grid },
      horzLines: { color: theme.grid },
    },
    rightPriceScale: {
      borderColor: theme.border,
    },
    leftPriceScale: {
      borderColor: theme.border,
    },
    timeScale: {
      borderColor: theme.border,
      timeVisible: false,
      secondsVisible: false,
    },
    crosshair: {
      vertLine: { color: theme.crosshair },
      horzLine: { color: theme.crosshair },
    },
    handleScroll: true,
    handleScale: true,
  };
};

export const createTradingChart = (
  container: HTMLElement,
  height: number,
  options?: DeepPartial<ChartOptions>
): IChartApi => {
  return createChart(container, {
    autoSize: true,
    height,
    ...getBaseChartOptions(),
    ...options,
  });
};
