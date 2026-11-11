"""Protects your budget: a per-visitor rate limit, a daily question cap and an answer cache."""
import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, limit, window=60):
        self.limit, self.window = limit, window
        self.hits = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key):
        now = time.time()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True


class DailyCap:
    def __init__(self, limit):
        self.limit, self.day, self.used = limit, time.strftime("%Y-%m-%d"), 0
        self.lock = threading.Lock()

    def take(self):
        with self.lock:
            today = time.strftime("%Y-%m-%d")
            if today != self.day:
                self.day, self.used = today, 0
            if self.used >= self.limit:
                return False
            self.used += 1
            return True

    def remaining(self):
        with self.lock:
            return max(0, self.limit - self.used)


class AnswerCache:
    def __init__(self, ttl=3600, size=200):
        self.ttl, self.size, self.data, self.lock = ttl, size, {}, threading.Lock()

    @staticmethod
    def key(question):
        return " ".join(question.lower().split()).rstrip("?. ")

    def get(self, question):
        with self.lock:
            hit = self.data.get(self.key(question))
            if hit and time.time() - hit[0] < self.ttl:
                return hit[1]
        return None

    def put(self, question, value):
        with self.lock:
            if len(self.data) >= self.size:
                self.data.pop(min(self.data, key=lambda k: self.data[k][0]))
            self.data[self.key(question)] = (time.time(), value)
