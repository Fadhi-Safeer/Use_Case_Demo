'use strict';

const state = {
  activeTab: 'gear',
  activeRunningTab: null,   // 'gear' | 'weapon' | 'custom' | null

  tabs: {
    gear:   { liveSessionId: null, lastResult: null, lastSeenSeq: 0, cardCount: 0 },
    weapon: { liveSessionId: null, lastResult: null, lastSeenSeq: 0, cardCount: 0 },
    custom: { liveSessionId: null, lastResult: null, lastSeenSeq: 0, cardCount: 0 },
  },

  camera: { ok: false },
  showDuplicates: false,   // mirrors backend show_duplicate_results setting
};
