'use strict';

const state = {
  activePreset: null,   // button element currently active
  pendingCards: {},     // job_id → true, for jobs not yet in history
  liveJobId: null,      // job_id of the current live session
  lastLiveResult: null, // last result text seen — used to detect new results
  liveCardCount: 0,     // counts how many cards have been added this session
};
