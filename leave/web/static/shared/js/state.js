/* Global State Management - Single source of truth */

export const state = {
  runs: [],
  selectedRun: null,
  strategies: [],
  loopStatus: { running: false, currentIteration: null },
  theme: "dark"
};

export function setState(newState) {
  Object.assign(state, newState);
}

export function getState() {
  return { ...state };
}
