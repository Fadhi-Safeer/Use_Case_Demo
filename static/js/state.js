'use strict';

const state = {
  activeTab: 'gear',
  activeRunningTab: null,   // 'gear' | 'weapon' | 'custom' | null

  tabs: {
    gear:   { liveJobId: null, lastResult: null, lastTimestamp: null, cardCount: 0 },
    weapon: { liveJobId: null, lastResult: null, lastTimestamp: null, cardCount: 0 },
    custom: { liveJobId: null, lastResult: null, lastTimestamp: null, cardCount: 0 },
  },

  camera: { ok: false },
  showDuplicates: false,   // mirrors backend show_duplicate_results setting
};
