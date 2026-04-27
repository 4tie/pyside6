'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, BacktestRunsRequest, LatestBacktestRun } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import Link from 'next/link';
import { ArrowLeft, ArrowUpDown, Search } from 'lucide-react';

export default function BacktestRunsPage() {
  const [filters, setFilters] = useState<BacktestRunsRequest>({
    strategy: undefined,
    sort_by: 'saved_at',
    order: 'desc',
    limit: 50,
    offset: 0,
  });
  const [searchQuery, setSearchQuery] = useState('');

  // Fetch all strategies for filter dropdown
  const { data: allRunsData, isLoading: isLoadingRuns } = useQuery({
    queryKey: ['backtest-runs', filters],
    queryFn: () => api.getBacktestRuns(filters),
  });

  // Extract unique strategies from runs
  const strategies = allRunsData?.runs
    ? Array.from(new Set(allRunsData.runs.map((run) => run.strategy).filter(Boolean)))
    : [];

  // Filter by search query (search in strategy name)
  const filteredRuns = allRunsData?.runs
    ? allRunsData.runs.filter((run) =>
        run.strategy?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : [];

  // Handle sort change
  const handleSort = (field: string) => {
    if (filters.sort_by === field) {
      // Toggle order if same field
      setFilters({ ...filters, order: filters.order === 'desc' ? 'asc' : 'desc' });
    } else {
      // New field, default to desc
      setFilters({ ...filters, sort_by: field, order: 'desc' });
    }
  };

  // Handle sort_by select change
  const handleSortByChange = (value: string | null) => {
    setFilters({ ...filters, sort_by: value || 'saved_at' });
  };

  // Handle order select change
  const handleOrderChange = (value: string | null) => {
    setFilters({ ...filters, order: (value === 'asc' || value === 'desc') ? value : 'desc' });
  };

  // Handle strategy filter
  const handleStrategyFilter = (strategy: string | null) => {
    setFilters({ ...filters, strategy: strategy === 'all' || strategy === null ? undefined : strategy });
  };

  // Calculate days run
  const calculateDaysRun = (backtestStart?: string, backtestEnd?: string): number => {
    if (!backtestStart || !backtestEnd) return 0;
    return Math.ceil((new Date(backtestEnd).getTime() - new Date(backtestStart).getTime()) / (1000 * 60 * 60 * 24));
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="container mx-auto p-6">
        <div className="mb-6">
          <Link href="/backtest" className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100 mb-4">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Backtest
          </Link>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">Backtest Runs History</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-2">View all backtest runs with detailed metrics</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Filter & Sort</CardTitle>
            <CardDescription>Filter by strategy or search, sort by different metrics</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-4">
              <div className="flex-1 min-w-[200px]">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <Input
                    placeholder="Search by strategy..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10"
                  />
                </div>
              </div>
              <div className="min-w-[200px]">
                <Select value={filters.strategy || 'all'} onValueChange={handleStrategyFilter}>
                  <SelectTrigger>
                    <SelectValue placeholder="All Strategies" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Strategies</SelectItem>
                    {strategies.map((strategy) => (
                      <SelectItem key={strategy} value={strategy}>
                        {strategy}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="min-w-[150px]">
                <Select value={filters.sort_by} onValueChange={handleSortByChange}>
                  <SelectTrigger>
                    <SelectValue placeholder="Sort by" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="saved_at">Date</SelectItem>
                    <SelectItem value="profit_total_pct">Profit %</SelectItem>
                    <SelectItem value="win_rate_pct">Win Rate %</SelectItem>
                    <SelectItem value="max_drawdown_pct">Drawdown %</SelectItem>
                    <SelectItem value="trades_count">Trades Count</SelectItem>
                    <SelectItem value="sharpe">Sharpe Ratio</SelectItem>
                    <SelectItem value="sortino">Sortino Ratio</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="min-w-[120px]">
                <Select value={filters.order} onValueChange={handleOrderChange}>
                  <SelectTrigger>
                    <SelectValue placeholder="Order" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="desc">Descending</SelectItem>
                    <SelectItem value="asc">Ascending</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="mt-6">
          <CardHeader>
            <CardTitle>All Backtest Runs</CardTitle>
            <CardDescription>
              Showing {filteredRuns.length} of {allRunsData?.total || 0} runs
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoadingRuns ? (
              <div className="text-center py-8 text-gray-500">Loading...</div>
            ) : filteredRuns.length === 0 ? (
              <div className="text-center py-8 text-gray-500 dark:text-gray-400">
                No backtest runs found. Run your first backtest to see results here.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleSort('strategy')}
                          className="font-semibold"
                        >
                          Strategy <ArrowUpDown className="w-3 h-3 ml-2" />
                        </Button>
                      </TableHead>
                      <TableHead>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleSort('profit_total_pct')}
                          className="font-semibold"
                        >
                          Profit % <ArrowUpDown className="w-3 h-3 ml-2" />
                        </Button>
                      </TableHead>
                      <TableHead>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleSort('win_rate_pct')}
                          className="font-semibold"
                        >
                          Win Rate % <ArrowUpDown className="w-3 h-3 ml-2" />
                        </Button>
                      </TableHead>
                      <TableHead>Start / End Balance</TableHead>
                      <TableHead>Days Run</TableHead>
                      <TableHead>Timerange</TableHead>
                      <TableHead>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleSort('trades_count')}
                          className="font-semibold"
                        >
                          Trades <ArrowUpDown className="w-3 h-3 ml-2" />
                        </Button>
                      </TableHead>
                      <TableHead>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleSort('max_drawdown_pct')}
                          className="font-semibold"
                        >
                          Drawdown % <ArrowUpDown className="w-3 h-3 ml-2" />
                        </Button>
                      </TableHead>
                      <TableHead>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleSort('sharpe')}
                          className="font-semibold"
                        >
                          Sharpe <ArrowUpDown className="w-3 h-3 ml-2" />
                        </Button>
                      </TableHead>
                      <TableHead>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleSort('sortino')}
                          className="font-semibold"
                        >
                          Sortino <ArrowUpDown className="w-3 h-3 ml-2" />
                        </Button>
                      </TableHead>
                      <TableHead>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleSort('saved_at')}
                          className="font-semibold"
                        >
                          Date <ArrowUpDown className="w-3 h-3 ml-2" />
                        </Button>
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredRuns.map((run) => {
                      const daysRun = calculateDaysRun(run.backtest_start, run.backtest_end);
                      return (
                        <TableRow key={run.run_id}>
                          <TableCell className="font-medium">{run.strategy}</TableCell>
                          <TableCell>
                            <Badge variant={run.profit_total_pct && run.profit_total_pct > 0 ? "default" : "secondary"}>
                              {run.profit_total_pct?.toFixed(2) ?? 'N/A'}%
                            </Badge>
                          </TableCell>
                          <TableCell>{run.win_rate_pct?.toFixed(2) ?? 'N/A'}%</TableCell>
                          <TableCell className="text-xs">
                            {run.starting_balance?.toFixed(2) ?? 'N/A'} → {run.final_balance?.toFixed(2) ?? 'N/A'}
                          </TableCell>
                          <TableCell className="text-xs">{daysRun}</TableCell>
                          <TableCell className="text-xs">{run.timerange || 'N/A'}</TableCell>
                          <TableCell>{run.trades_count ?? 'N/A'}</TableCell>
                          <TableCell>{run.max_drawdown_pct?.toFixed(2) ?? 'N/A'}%</TableCell>
                          <TableCell>{run.sharpe?.toFixed(2) ?? 'N/A'}</TableCell>
                          <TableCell>{run.sortino?.toFixed(2) ?? 'N/A'}</TableCell>
                          <TableCell className="text-xs">{run.saved_at ? new Date(run.saved_at).toLocaleDateString() : 'N/A'}</TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
