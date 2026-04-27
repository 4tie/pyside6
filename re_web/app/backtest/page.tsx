'use client';

import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { usePathname } from 'next/navigation';
import { api, BacktestRequest, PairsResponse, LatestBacktestRun } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Checkbox } from '@/components/ui/checkbox';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';
import Link from 'next/link';
import { Search, Heart, Lock, Unlock, ChevronDown, ChevronUp, Download, BarChart3, Play, Settings } from 'lucide-react';

export default function BacktestPage() {
  const pathname = usePathname();
  const queryClient = useQueryClient();
  
  const [formData, setFormData] = useState<BacktestRequest>({
    strategy: '',
    timeframe: '1h',
    timerange: '',
    pairs: [],
    max_open_trades: 5,
    dry_run_wallet: 1000,
  });

  const [selectedPairs, setSelectedPairs] = useState<string[]>([]);
  const [lockedPairs, setLockedPairs] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set(['Tier 1: Major cryptocurrencies']));
  const [favorites, setFavorites] = useState<string[]>([]);

  // Fetch strategies
  const { data: strategies = [], isLoading: strategiesLoading } = useQuery({
    queryKey: ['strategies'],
    queryFn: () => api.getStrategies(),
  });

  // Fetch pairs
  const { data: pairsData, isLoading: pairsLoading } = useQuery<PairsResponse>({
    queryKey: ['pairs'],
    queryFn: () => api.getPairs(),
  });

  // Fetch latest backtest run
  const { data: latestRun, isLoading: latestRunLoading } = useQuery<LatestBacktestRun>({
    queryKey: ['latest-backtest-run'],
    queryFn: () => api.getLatestBacktestRun(),
    refetchInterval: 5000,
  });

  // Fetch data availability
  const { data: dataAvailability, isLoading: dataCheckLoading } = useQuery({
    queryKey: ['data-availability', selectedPairs, formData.timeframe, formData.timerange],
    queryFn: () => api.checkDataAvailability(selectedPairs, formData.timeframe, formData.timerange),
    enabled: selectedPairs.length > 0 && formData.timeframe !== '',
  });

  // Fetch saved config
  const { data: savedConfig } = useQuery({
    queryKey: ['backtest-config'],
    queryFn: () => api.getBacktestConfig(),
  });

  // Fetch backtest status
  const { data: backtestStatus } = useQuery({
    queryKey: ['backtest-status'],
    queryFn: () => api.getBacktestStatus(),
    refetchInterval: 2000,
  });

  // Execute backtest mutation
  const executeMutation = useMutation({
    mutationFn: (data: BacktestRequest) => api.executeBacktest(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['backtest-status'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });

  // Stop backtest mutation
  const stopMutation = useMutation({
    mutationFn: () => api.stopBacktest(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['backtest-status'] });
    },
  });

  // Load saved config on mount
  useEffect(() => {
    if (savedConfig) {
      setFormData({
        strategy: savedConfig.strategy || '',
        timeframe: savedConfig.timeframe || '1h',
        timerange: savedConfig.timerange || '',
        pairs: savedConfig.pairs || [],
        max_open_trades: savedConfig.max_open_trades || 5,
        dry_run_wallet: savedConfig.dry_run_wallet || 1000,
      });
      setSelectedPairs(savedConfig.pairs || []);
    }
    // Load favorites from pairs data
    if (pairsData?.favorites) {
      setFavorites(pairsData.favorites);
    }
  }, [savedConfig, pairsData]);

  // Save config mutation
  const saveConfigMutation = useMutation({
    mutationFn: (data: BacktestRequest) => api.saveBacktestConfig(data),
  });

  const handleSaveConfig = () => {
    saveConfigMutation.mutate({ ...formData, pairs: selectedPairs });
  };

  const handleExecuteBacktest = () => {
    if (!formData.strategy) {
      alert('Please select a strategy');
      return;
    }
    if (selectedPairs.length === 0) {
      alert('Please select at least one trading pair');
      return;
    }
    executeMutation.mutate({ ...formData, pairs: selectedPairs });
  };

  // Download data mutation
  const downloadDataMutation = useMutation({
    mutationFn: (data: { pairs: string[]; timeframe: string; timerange?: string }) => 
      api.downloadData({ pairs: data.pairs, timeframe: data.timeframe, timerange: data.timerange }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['data-availability'] });
    },
  });

  const handleDownloadData = () => {
    downloadDataMutation.mutate({
      pairs: dataAvailability?.missing_pairs || selectedPairs,
      timeframe: formData.timeframe,
      timerange: formData.timerange,
    });
  };

  const handleStopBacktest = () => {
    stopMutation.mutate();
  };

  const togglePair = (pair: string) => {
    setSelectedPairs(prev =>
      prev.includes(pair) ? prev.filter(p => p !== pair) : [...prev, pair]
    );
  };

  const toggleFavorite = (pair: string) => {
    const newFavorites = favorites.includes(pair)
      ? favorites.filter(p => p !== pair)
      : [...favorites, pair];
    setFavorites(newFavorites);
    api.saveFavorites(newFavorites);
  };

  const toggleLock = (pair: string) => {
    setLockedPairs(prev => {
      const newLocked = new Set(prev);
      if (newLocked.has(pair)) {
        newLocked.delete(pair);
      } else {
        newLocked.add(pair);
      }
      return newLocked;
    });
  };

  const randomizePairs = () => {
    if (!pairsData) return;
    const allPairs = pairsData.all_pairs.filter(p => !lockedPairs.has(p));
    const count = Math.min(5, allPairs.length);
    const shuffled = [...allPairs].sort(() => Math.random() - 0.5);
    const newSelected = [...lockedPairs, ...shuffled.slice(0, count)];
    setSelectedPairs(newSelected);
  };

  const toggleCategory = (category: string) => {
    setExpandedCategories(prev => {
      const newExpanded = new Set(prev);
      if (newExpanded.has(category)) {
        newExpanded.delete(category);
      } else {
        newExpanded.add(category);
      }
      return newExpanded;
    });
  };

  const applyTimeRangePreset = (preset: string) => {
    const now = new Date();
    let startDate: Date;
    
    switch (preset) {
      case '30d':
        startDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
        break;
      case '90d':
        startDate = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000);
        break;
      case '1y':
        startDate = new Date(now.getTime() - 365 * 24 * 60 * 60 * 1000);
        break;
      case 'ytd':
        startDate = new Date(now.getFullYear(), 0, 1);
        break;
      default:
        return;
    }
    
    const format = (date: Date) => date.toISOString().slice(0, 10).replace(/-/g, '');
    setFormData({ ...formData, timerange: `${format(startDate)}-${format(now)}` });
  };

  const isRunning = backtestStatus?.status === 'running';

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
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold text-gray-900 dark:text-white mb-2">
                Backtest Configuration
              </h1>
              <p className="text-gray-600 dark:text-gray-400">
                Configure and run strategy backtests
              </p>
            </div>
            <Link href="/">
              <Button variant="outline">Back to Dashboard</Button>
            </Link>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Configuration Form */}
          <div className="lg:col-span-2 space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Strategy Settings</CardTitle>
                <CardDescription>Configure your backtest parameters</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="strategy">Strategy</Label>
                  <Select
                    value={formData.strategy || ''}
                    onValueChange={(value: string | null) => setFormData({ ...formData, strategy: value || '' })}
                    disabled={strategiesLoading || isRunning}
                  >
                    <SelectTrigger id="strategy">
                      <SelectValue placeholder="Select a strategy" />
                    </SelectTrigger>
                    <SelectContent>
                      {strategies.map((s) => (
                        <SelectItem key={s.name} value={s.name}>
                          {s.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="timeframe">Timeframe</Label>
                    <Select
                      value={formData.timeframe || ''}
                      onValueChange={(value: string | null) => setFormData({ ...formData, timeframe: value || '' })}
                      disabled={isRunning}
                    >
                      <SelectTrigger id="timeframe">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="1m">1m</SelectItem>
                        <SelectItem value="5m">5m</SelectItem>
                        <SelectItem value="15m">15m</SelectItem>
                        <SelectItem value="1h">1h</SelectItem>
                        <SelectItem value="4h">4h</SelectItem>
                        <SelectItem value="1d">1d</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="timerange">Timerange</Label>
                    <div className="space-y-2">
                      <Input
                        id="timerange"
                        placeholder="e.g., 20240101-20241231"
                        value={formData.timerange}
                        onChange={(e) => setFormData({ ...formData, timerange: e.target.value })}
                        disabled={isRunning}
                      />
                      <div className="flex gap-2 flex-wrap">
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => applyTimeRangePreset('30d')}
                          disabled={isRunning}
                        >
                          Last 30 days
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => applyTimeRangePreset('90d')}
                          disabled={isRunning}
                        >
                          Last 90 days
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => applyTimeRangePreset('1y')}
                          disabled={isRunning}
                        >
                          Last year
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => applyTimeRangePreset('ytd')}
                          disabled={isRunning}
                        >
                          YTD
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="maxOpenTrades">Max Open Trades</Label>
                    <Input
                      id="maxOpenTrades"
                      type="number"
                      value={formData.max_open_trades}
                      onChange={(e) => setFormData({ ...formData, max_open_trades: parseInt(e.target.value) || 5 })}
                      disabled={isRunning}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="dryRunWallet">Dry Run Wallet (USDT)</Label>
                    <Input
                      id="dryRunWallet"
                      type="number"
                      value={formData.dry_run_wallet}
                      onChange={(e) => setFormData({ ...formData, dry_run_wallet: parseFloat(e.target.value) || 1000 })}
                      disabled={isRunning}
                    />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Trading Pairs</CardTitle>
                <CardDescription>Select pairs to backtest ({selectedPairs.length} selected)</CardDescription>
              </CardHeader>
              <CardContent>
                {pairsLoading ? (
                  <div className="text-center py-4">Loading pairs...</div>
                ) : (
                  <div className="space-y-4">
                    {/* Search input */}
                    <div className="relative">
                      <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={16} />
                      <Input
                        placeholder="Search pairs..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="pl-10"
                      />
                    </div>

                    {/* Randomize button */}
                    <Button
                      onClick={randomizePairs}
                      variant="outline"
                      size="sm"
                      className="w-full"
                      disabled={isRunning}
                    >
                      Randomize Pairs
                    </Button>

                    {/* Categorized pairs */}
                    {pairsData?.categories && Object.entries(pairsData.categories).map(([category, pairs]) => {
                      const filteredPairs = pairs.filter((pair: string) =>
                        pair.toLowerCase().includes(searchQuery.toLowerCase())
                      );
                      if (filteredPairs.length === 0) return null;

                      const isExpanded = expandedCategories.has(category);

                      return (
                        <Collapsible key={category} open={isExpanded} onOpenChange={() => toggleCategory(category)}>
                          <CollapsibleTrigger className="w-full">
                            <div className="flex items-center justify-between p-2 bg-gray-100 dark:bg-gray-800 rounded-md cursor-pointer hover:bg-gray-200 dark:hover:bg-gray-700">
                              <span className="font-medium text-sm">{category}</span>
                              {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                            </div>
                          </CollapsibleTrigger>
                          <CollapsibleContent className="space-y-2 mt-2">
                            {filteredPairs.map((pair: string) => {
                              const isSelected = selectedPairs.includes(pair);
                              const isFavorite = favorites.includes(pair);
                              const isLocked = lockedPairs.has(pair);

                              return (
                                <div key={pair} className="flex items-center gap-2 p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800">
                                  <Checkbox
                                    id={pair}
                                    checked={isSelected}
                                    onCheckedChange={() => !isRunning && togglePair(pair)}
                                    disabled={isRunning}
                                  />
                                  <Label htmlFor={pair} className="flex-1 cursor-pointer">
                                    {pair}
                                  </Label>
                                  {isFavorite && <Heart size={16} className="fill-red-500 text-red-500" />}
                                  {isSelected && (
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      onClick={() => toggleLock(pair)}
                                      disabled={isRunning}
                                    >
                                      {isLocked ? <Lock size={16} /> : <Unlock size={16} />}
                                    </Button>
                                  )}
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={() => toggleFavorite(pair)}
                                    disabled={isRunning}
                                  >
                                    <Heart size={16} className={isFavorite ? "fill-red-500 text-red-500" : ""} />
                                  </Button>
                                </div>
                              );
                            })}
                          </CollapsibleContent>
                        </Collapsible>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>

            <div className="flex gap-4 flex-wrap">
              {/* Download data button */}
              {dataAvailability && !dataAvailability.available && dataAvailability.missing_pairs.length > 0 && (
                <Button
                  onClick={handleDownloadData}
                  variant="outline"
                  disabled={downloadDataMutation.isPending || isRunning}
                  className="flex items-center gap-2"
                >
                  <Download size={16} />
                  {downloadDataMutation.isPending ? 'Downloading...' : `Download Data (${dataAvailability.missing_pairs.length} pairs)`}
                </Button>
              )}
              
              <Button
                onClick={handleSaveConfig}
                variant="outline"
                disabled={saveConfigMutation.isPending}
              >
                {saveConfigMutation.isPending ? 'Saving...' : 'Save Configuration'}
              </Button>
              <Button
                onClick={handleExecuteBacktest}
                disabled={isRunning || executeMutation.isPending}
                className="flex-1"
              >
                {executeMutation.isPending ? 'Starting...' : 'Run Backtest'}
              </Button>
              {isRunning && (
                <Button
                  onClick={handleStopBacktest}
                  variant="destructive"
                  disabled={stopMutation.isPending}
                >
                  {stopMutation.isPending ? 'Stopping...' : 'Stop'}
                </Button>
              )}
            </div>
          </div>

          {/* Status Panel */}
          <div className="space-y-6">
            {/* Results Panel */}
            {latestRun?.exists && latestRun.run_id && (
              <Card>
                <CardHeader>
                  <CardTitle>Latest Results</CardTitle>
                  <CardDescription>
                    {latestRun.strategy} - {latestRun.timeframe} - {latestRun.saved_at?.split('T')[0]}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Metrics */}
                  <div className="grid grid-cols-2 gap-2">
                    <div className="p-2 bg-gray-100 dark:bg-gray-800 rounded">
                      <div className="text-xs text-gray-500">Profit</div>
                      <div className="text-lg font-bold">{latestRun.profit_total_pct?.toFixed(2)}%</div>
                    </div>
                    <div className="p-2 bg-gray-100 dark:bg-gray-800 rounded">
                      <div className="text-xs text-gray-500">Win Rate</div>
                      <div className="text-lg font-bold">{latestRun.win_rate_pct?.toFixed(2)}%</div>
                    </div>
                    <div className="p-2 bg-gray-100 dark:bg-gray-800 rounded">
                      <div className="text-xs text-gray-500">Drawdown</div>
                      <div className="text-lg font-bold">{latestRun.max_drawdown_pct?.toFixed(2)}%</div>
                    </div>
                    <div className="p-2 bg-gray-100 dark:bg-gray-800 rounded">
                      <div className="text-xs text-gray-500">Trades</div>
                      <div className="text-lg font-bold">{latestRun.trades_count}</div>
                    </div>
                    <div className="p-2 bg-gray-100 dark:bg-gray-800 rounded">
                      <div className="text-xs text-gray-500">Sharpe</div>
                      <div className="text-lg font-bold">{latestRun.sharpe?.toFixed(2) || 'N/A'}</div>
                    </div>
                    <div className="p-2 bg-gray-100 dark:bg-gray-800 rounded">
                      <div className="text-xs text-gray-500">Profit Factor</div>
                      <div className="text-lg font-bold">{latestRun.profit_factor?.toFixed(2) || 'N/A'}</div>
                    </div>
                  </div>

                  {/* Charts */}
                  {latestRun.trades && latestRun.trades.length > 0 && (
                    <div className="space-y-4">
                      <div className="h-40">
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart data={latestRun.trades.map((t, i) => ({ index: i, profit: t.profit }))}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="index" />
                            <YAxis />
                            <Tooltip />
                            <Line type="monotone" dataKey="profit" stroke="#8884d8" strokeWidth={2} />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                      <div className="text-xs text-gray-500 text-center">Cumulative Profit per Trade</div>
                    </div>
                  )}

                  {/* Recent Trades */}
                  {latestRun.trades && latestRun.trades.length > 0 && (
                    <div>
                      <h4 className="text-sm font-medium mb-2">Recent Runs for Strategy</h4>
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Pair</TableHead>
                            <TableHead>Profit</TableHead>
                            <TableHead>Exit Reason</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {latestRun.trades.slice(-10).reverse().map((trade, i) => (
                            <TableRow key={i}>
                              <TableCell>{trade.pair}</TableCell>
                              <TableCell className={trade.profit > 0 ? 'text-green-600' : 'text-red-600'}>
                                {trade.profit.toFixed(2)}%
                              </TableCell>
                              <TableCell className="text-xs">{trade.exit_reason}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            <Card>
              <CardHeader>
                <CardTitle>Backtest Status</CardTitle>
              </CardHeader>
              <CardContent>
                {backtestStatus ? (
                  <div className="space-y-4">
                    <div className="flex items-center gap-2">
                      <div
                        className={`w-3 h-3 rounded-full ${
                          backtestStatus.status === 'running'
                            ? 'bg-green-500 animate-pulse'
                            : backtestStatus.status === 'complete'
                            ? 'bg-blue-500'
                            : backtestStatus.status === 'error'
                            ? 'bg-red-500'
                            : 'bg-gray-500'
                        }`}
                      />
                      <span className="font-medium capitalize">{backtestStatus.status}</span>
                    </div>
                    {backtestStatus.message && (
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        {backtestStatus.message}
                      </p>
                    )}
                    {backtestStatus.run_id && (
                      <p className="text-xs text-gray-500">
                        Run ID: {backtestStatus.run_id}
                      </p>
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">No status available</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Quick Actions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <Link href="/" className="block">
                  <Button variant="outline" className="w-full" size="sm">
                    View Dashboard
                  </Button>
                </Link>
                <Separator />
                <p className="text-xs text-gray-500 mt-2">
                  Configure your strategy and pairs, then run a backtest to see results on the dashboard.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
