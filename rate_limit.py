import os, time, threading, hashlib
from collections import defaultdict, deque

class RateLimiter:
    def __init__(self):
        self.backend=os.getenv('SALUS_RATE_LIMIT_BACKEND','memory').strip().lower()
        self.requests=int(os.getenv('SALUS_RATE_LIMIT_REQUESTS','240'))
        self.window=int(os.getenv('SALUS_RATE_LIMIT_WINDOW_SECONDS','60'))
        self.enabled=os.getenv('SALUS_RATE_LIMIT_ENABLED','1').strip().lower() in ('1','true','yes')
        self._events=defaultdict(deque)
        self._lock=threading.Lock()
        self._redis=None
        if self.backend=='redis':
            try:
                import redis
                url=os.getenv('SALUS_REDIS_URL','')
                if url: self._redis=redis.Redis.from_url(url,decode_responses=True,socket_timeout=2)
            except Exception:
                self._redis=None

    def key(self, ip: str, session_token: str='') -> str:
        ident=hashlib.sha256(session_token.encode()).hexdigest()[:20] if session_token else ip or 'unknown'
        return ident

    def allow(self, key: str):
        if not self.enabled:
            return True, self.requests, 0
        now=time.time()
        if self.backend=='redis' and self._redis is not None:
            bucket=int(now//self.window)
            rkey=f'salus:rl:{bucket}:{key}'
            try:
                count=self._redis.incr(rkey)
                if count==1: self._redis.expire(rkey,self.window+5)
                return count<=self.requests, max(self.requests-count,0), self.window-int(now%self.window)
            except Exception:
                pass
        cutoff=now-self.window
        with self._lock:
            q=self._events[key]
            while q and q[0] < cutoff: q.popleft()
            if len(q)>=self.requests:
                retry=max(1,int(self.window-(now-q[0]))) if q else self.window
                return False,0,retry
            q.append(now)
            return True,max(self.requests-len(q),0),0

    def health(self):
        if not self.enabled:
            return {'enabled':False,'backend':self.backend,'healthy':True,'detail':'Rate limiting disabled'}
        if self.backend=='redis':
            if self._redis is None:
                return {'enabled':True,'backend':'redis','healthy':False,'detail':'Redis backend not configured or library unavailable'}
            try:
                self._redis.ping(); return {'enabled':True,'backend':'redis','healthy':True,'detail':'Redis reachable'}
            except Exception as exc:
                return {'enabled':True,'backend':'redis','healthy':False,'detail':f'Redis unavailable: {exc}'}
        return {'enabled':True,'backend':'memory','healthy':True,'detail':'Single-process memory limiter'}
