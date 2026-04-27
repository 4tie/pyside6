'use client';

import { useQuery } from '@tanstack/react-query';
import { usePathname } from 'next/navigation';
import { api, DashboardSummary } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';
import Link from 'next/link';
import { BarChart3, Play, Settings } from 'lucide-react';

export default function Dashboard() {
  const pathname = usePathname();
  const { data: summary, isLoading, error } = useQuery<DashboardSummary>({
    queryKey: ['dashboard'],
    queryFn: () => api.getDashboardSummary(),
    refetchInterval: 30000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg">Loading dashboard...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-red-500">Error loading dashboard: {(error as Error).message}</div>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg">No data available</div>
      </div>
    );
  }

  const metrics = summary.metrics;
  const recentRuns = summary.recent_runs || [];

  // Prepare chart data
  const chartData = recentRuns.slice(0, 10).map(run => ({
    name: run.strategy.substring(0, 15),
    profit: run.profit_total_pct || 0,
    winRate: run.win_rate_pct || 0,
    drawdown: run.max_drawdown_pct || 0,
  }));

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* Navigation Bar */}
      <nav className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-50">
        <div className="container mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <BarChart3 className="text-blue-600" size={24} />
              <h1 className="text-xl font-bold text-gray-900 dark:text-white">Strategy Optimizer</h1>
            </div>
            <div className="flex items-center gap-4">
              <Link href="/">
                <Button variant={pathname === '/' ? 'default' : 'ghost'} className="flex items-center gap-2">
                  <BarChart3 size={16} />
                  Dashboard
                </Button>
              </Link>
              <Link href="/backtest">
                <Button variant={pathname === '/backtest' ? 'default' : 'ghost'} className="flex items-center gap-2">
                  <Play size={16} />
                  Backtest
                </Button>
              </Link>
              <Link href="/settings">
                <Button variant="ghost" className="flex items-center gap-2">
                  <Settings size={16} />
                  Settings
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </nav>

      <div className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-gray-900 dark:text-white mb-2">
            Strategy Optimization Dashboard
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Overview of backtest results and strategy performance
          </p>
        </div>

        {/* Metrics Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                Total Runs
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-gray-900 dark:text-white">
                {metrics.total_runs}
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Across {metrics.total_strategies} strategies
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                Best Profit
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-green-600 dark:text-green-400">
                {metrics.best_profit_pct.toFixed(2)}%
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Highest performing run
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                Best Win Rate
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-blue-600 dark:text-blue-400">
                {metrics.best_win_rate_pct.toFixed(2)}%
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Most consistent strategy
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600 dark:text-gray-400">
                Min Drawdown
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-red-600 dark:text-red-400">
                {metrics.min_drawdown_pct.toFixed(2)}%
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Lowest risk strategy
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          <Card>
            <CardHeader>
              <CardTitle>Profit by Strategy</CardTitle>
              <CardDescription>Recent backtest results</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="profit" fill="#10b981" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Win Rate & Drawdown</CardTitle>
              <CardDescription>Performance metrics comparison</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Line type="monotone" dataKey="winRate" stroke="#3b82f6" name="Win Rate %" />
                  <Line type="monotone" dataKey="drawdown" stroke="#ef4444" name="Drawdown %" />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>

        {/* Recent Runs Table */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Backtest Runs</CardTitle>
            <CardDescription>Latest strategy backtest results</CardDescription>
          </CardHeader>
          <CardContent>
            {recentRuns.length === 0 ? (
              <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                No backtest runs found. Run your first backtest to see results here.
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Strategy</TableHead>
                    <TableHead>Profit %</TableHead>
                    <TableHead>Win Rate %</TableHead>
                    <TableHead>Drawdown %</TableHead>
                    <TableHead>Trades</TableHead>
                    <TableHead>Date</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recentRuns.map((run) => (
                    <TableRow key={run.run_id}>
                      <TableCell className="font-medium">{run.strategy}</TableCell>
                      <TableCell>
                        <Badge variant={run.profit_total_pct && run.profit_total_pct > 0 ? "default" : "secondary"}>
                          {run.profit_total_pct?.toFixed(2) ?? 'N/A'}%
                        </Badge>
                      </TableCell>
                      <TableCell>{run.win_rate_pct?.toFixed(2) ?? 'N/A'}%</TableCell>
                      <TableCell>{run.max_drawdown_pct?.toFixed(2) ?? 'N/A'}%</TableCell>
                      <TableCell>{run.trades_count ?? 'N/A'}</TableCell>
                      <TableCell>{new Date(run.saved_at).toLocaleDateString()}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
