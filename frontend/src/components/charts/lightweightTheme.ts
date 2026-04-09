import {
    ColorType,
    createChart,
    type ChartOptions,
    type DeepPartial,
    type IChartApi,
} from 'lightweight-charts';

const BASE_CHART_OPTIONS: DeepPartial<ChartOptions> = {
  layout: {
    background: { type: ColorType.Solid, color: '#0f172a' },
    textColor: '#cbd5e1',
    attributionLogo: false,
  },
  grid: {
    vertLines: { color: 'rgba(51, 65, 85, 0.25)' },
    horzLines: { color: 'rgba(51, 65, 85, 0.25)' },
  },
  rightPriceScale: {
    borderColor: '#334155',
  },
  leftPriceScale: {
    borderColor: '#334155',
  },
  timeScale: {
    borderColor: '#334155',
    timeVisible: false,
    secondsVisible: false,
  },
  crosshair: {
    vertLine: { color: 'rgba(148, 163, 184, 0.35)' },
    horzLine: { color: 'rgba(148, 163, 184, 0.35)' },
  },
  handleScroll: true,
  handleScale: true,
};

export const createTradingChart = (
  container: HTMLElement,
  height: number,
  options?: DeepPartial<ChartOptions>
): IChartApi => {
  return createChart(container, {
    width: container.clientWidth,
    height,
    ...BASE_CHART_OPTIONS,
    ...options,
  });
};
