from asyncio import Queue, Task

inference_queue:     Queue = None
producer_task:       Task  = None
consumer_task:       Task  = None
current_session_id:  str   = ""
current_use_case:    str   = ""
last_warned_tier:    int   = 0
stuck_warning_fired: bool  = False
session_start_ts:    float = 0.0
total_captured:      int   = 0
total_inferred:      int   = 0
