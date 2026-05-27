import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BacktestPage } from "@/pages/BacktestPage";
import { ModelPage } from "@/pages/ModelPage";
import { RiskPage } from "@/pages/RiskPage";
import { useSessionStore } from "@/hooks/useSessionStore";

const useActionsMock = vi.fn();
const useModelInfoQueryMock = vi.fn();
const useModelCalibrationQueryMock = vi.fn();
const useModelDriftQueryMock = vi.fn();
const useRiskStatusQueryMock = vi.fn();
const useLatestBacktestQueryMock = vi.fn();

vi.mock("@/hooks/useApiQueries", () => ({
  useActions: () => useActionsMock(),
  useModelInfoQuery: () => useModelInfoQueryMock(),
  useModelCalibrationQuery: () => useModelCalibrationQueryMock(),
  useModelDriftQuery: () => useModelDriftQueryMock(),
  useRiskStatusQuery: () => useRiskStatusQueryMock(),
  useLatestBacktestQuery: () => useLatestBacktestQueryMock(),
}));

vi.mock("@/components/backtest/EquityCurveChart", () => ({
  EquityCurveChart: () => <div>equity-curve-chart</div>,
}));

vi.mock("@/components/backtest/DrawdownCurveChart", () => ({
  DrawdownCurveChart: () => <div>drawdown-curve-chart</div>,
}));

vi.mock("@/components/backtest/WaitReasonChart", () => ({
  WaitReasonChart: () => <div>wait-reason-chart</div>,
}));

describe("Research dashboard pages", () => {
  beforeEach(() => {
    useSessionStore.setState({ latestSignal: null, latestBacktest: null });
    useActionsMock.mockReturnValue({
      runBacktest: {
        isPending: false,
        mutateAsync: vi.fn(),
      },
    });
    useModelInfoQueryMock.mockReturnValue({ data: null });
    useModelCalibrationQueryMock.mockReturnValue({ data: null });
    useModelDriftQueryMock.mockReturnValue({ data: null, isFetching: false, refetch: vi.fn() });
    useRiskStatusQueryMock.mockReturnValue({ data: null, isFetching: false, refetch: vi.fn() });
    useLatestBacktestQueryMock.mockReturnValue({ data: null, isFetching: false });
  });

  it("renders backtest slice table", () => {
    useSessionStore.setState({
      latestBacktest: {
        ml_enhanced: {
          symbol: "BTC/USDT",
          timeframe: "15m",
          total_trades: 12,
          winrate: 0.58,
          net_profit: 123.45,
          profit_factor: 1.6,
          max_drawdown: 4.2,
          expectancy: 10.1,
          grouped: {
            by_strategy: {
              TREND_FOLLOWING: {
                total_trades: 8,
                winrate: 0.62,
                net_profit: 90,
                profit_factor: 1.8,
                expectancy: 11.25,
              },
            },
          },
          trades: [],
        },
      },
    });

    render(<BacktestPage />);

    expect(screen.getByText("By Strategy")).toBeInTheDocument();
    expect(screen.getByText("TREND_FOLLOWING")).toBeInTheDocument();
  });

  it("shows drift HIGH warning", () => {
    useModelInfoQueryMock.mockReturnValue({
      data: {
        model_version: "v2.4.1",
        drift_report: {
          drift_level: "HIGH",
          recommended_action: "RETRAIN_CANDIDATE",
          drift_score: 0.92,
          drifted_features: [],
        },
      },
    });

    render(<ModelPage />);

    expect(screen.getByText(/High drift detected/i)).toBeInTheDocument();
  });

  it("shows risk BLOCKED state", () => {
    useRiskStatusQueryMock.mockReturnValue({
      data: {
        enabled: true,
        state: "BLOCKED",
        reasons: ["Daily drawdown limit breached"],
        daily_trade_count: 3,
        open_positions: 0,
        consecutive_losses: 4,
        daily_drawdown_pct: 0.08,
        weekly_drawdown_pct: 0.11,
      },
      isFetching: false,
      refetch: vi.fn(),
    });

    render(<RiskPage />);

    expect(screen.getByText("BLOCKED")).toBeInTheDocument();
    expect(screen.getByText(/Daily drawdown limit breached/i)).toBeInTheDocument();
  });

  it("does not crash on empty data", () => {
    render(
      <>
        <BacktestPage />
        <ModelPage />
        <RiskPage />
      </>,
    );

    expect(screen.getByText(/No backtest report yet/i)).toBeInTheDocument();
    expect(screen.getByText(/No drifted features detected/i)).toBeInTheDocument();
    expect(screen.getByText(/No paper trading analytics available yet/i)).toBeInTheDocument();
  });
});
