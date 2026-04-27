'use client';

import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, BacktestRequest, PairsResponse } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import Link from 'next/link';

export default function BacktestPage() {
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
      setFormData(savedConfig);
      setSelectedPairs(savedConfig.pairs || []);
    }
  }, [savedConfig]);

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

  const handleStopBacktest = () => {
    stopMutation.mutate();
  };

  const togglePair = (pair: string) => {
    setSelectedPairs(prev =>
      prev.includes(pair) ? prev.filter(p => p !== pair) : [...prev, pair]
    );
  };

  const isRunning = backtestStatus?.status === 'running';

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
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
                    value={formData.strategy || undefined}
                    onValueChange={(value) => setFormData({ ...formData, strategy: value })}
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
                      value={formData.timeframe || undefined}
                      onValueChange={(value) => setFormData({ ...formData, timeframe: value })}
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
                    <Input
                      id="timerange"
                      placeholder="e.g., 20240101-20241231"
                      value={formData.timerange}
                      onChange={(e) => setFormData({ ...formData, timerange: e.target.value })}
                      disabled={isRunning}
                    />
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
                  <div className="flex flex-wrap gap-2">
                    {pairsData?.pairs.map((pair) => (
                      <Badge
                        key={pair}
                        variant={selectedPairs.includes(pair) ? "default" : "outline"}
                        className="cursor-pointer"
                        onClick={() => !isRunning && togglePair(pair)}
                      >
                        {pair}
                      </Badge>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            <div className="flex gap-4">
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
