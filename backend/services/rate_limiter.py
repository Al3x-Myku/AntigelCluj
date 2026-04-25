"""Rate limiter — Fail2Ban-style tracking with Redis or in-memory fallback."""

import os
import time
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# Config
SOFT_BAN_THRESHOLD = int(os.getenv("SOFT_BAN_THRESHOLD", "5"))
HARD_BAN_THRESHOLD = int(os.getenv("HARD_BAN_THRESHOLD", "10"))
BAN_WINDOW = int(os.getenv("BAN_WINDOW_SECONDS", "60"))
SOFT_BAN_DURATION = int(os.getenv("SOFT_BAN_DURATION_SECONDS", "300"))
HARD_BAN_DURATION = int(os.getenv("HARD_BAN_DURATION_SECONDS", "3600"))

# In-memory fallback (used when Redis is unavailable)
_failures = defaultdict(list)  # key -> [timestamps]
_bans = {}  # key -> {"type": "soft"|"hard", "until": timestamp, "reason": str}

# Redis connection (lazy init)
_redis = None


def _get_redis():
    """Try to connect to Redis, return None if unavailable."""
    global _redis
    if _redis is not None:
        try:
            _redis.ping()
            return _redis
        except Exception:
            _redis = None
            return None
    try:
        import redis as redis_lib
        r = redis_lib.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), socket_connect_timeout=1)
        r.ping()
        _redis = r
        logger.info("Rate limiter connected to Redis")
        return _redis
    except Exception:
        logger.info("Redis unavailable — using in-memory rate limiter")
        return None


def record_failure(ip: str, username: str = None):
    """Record a failed login attempt. Returns ban info if threshold exceeded."""
    now = time.time()
    r = _get_redis()

    keys = [f"fail:ip:{ip}"]
    if username:
        keys.append(f"fail:user:{username}")

    ban_result = None

    for key in keys:
        try:
            if r:
                r.zadd(key, {str(now): now})
                r.zremrangebyscore(key, 0, now - BAN_WINDOW)
                count = r.zcard(key)
                r.expire(key, BAN_WINDOW * 2)
            else:
                raise Exception("no redis")
        except Exception:
            # In-memory fallback
            _failures[key] = [t for t in _failures[key] if t > now - BAN_WINDOW]
            _failures[key].append(now)
            count = len(_failures[key])

        # Check thresholds
        if count >= HARD_BAN_THRESHOLD:
            ban_result = _apply_ban(key.replace("fail:", ""), "hard", ip, username)
        elif count >= SOFT_BAN_THRESHOLD:
            ban_result = _apply_ban(key.replace("fail:", ""), "soft", ip, username)

    return ban_result


def _apply_ban(key_suffix: str, ban_type: str, ip: str, username: str = None):
    """Apply a ban (soft or hard)."""
    now = time.time()
    duration = HARD_BAN_DURATION if ban_type == "hard" else SOFT_BAN_DURATION
    until = now + duration
    reason = f"{'Hard' if ban_type == 'hard' else 'Soft'} ban: {HARD_BAN_THRESHOLD if ban_type == 'hard' else SOFT_BAN_THRESHOLD}+ failures in {BAN_WINDOW}s"

    ban_info = {
        "type": ban_type,
        "ip": ip,
        "username": username,
        "until": until,
        "until_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(until)),
        "reason": reason,
        "remaining_seconds": int(duration),
    }

    r = _get_redis()
    ban_key = f"ban:{key_suffix}"

    try:
        if r:
            import json
            r.setex(ban_key, duration, json.dumps(ban_info))
        else:
            raise Exception("no redis")
    except Exception:
        _bans[ban_key] = ban_info

    logger.warning(f"🚫 {ban_type.upper()} BAN applied: {key_suffix} — {reason}")
    return ban_info


def apply_explicit_ban(ip: str, reason: str, username: str = None):
    """Directly ban an IP (and optionally user) e.g., for direct fraud detection."""
    ban_info = _apply_ban(f"ip:{ip}", "hard", ip, username)
    if username:
        _apply_ban(f"user:{username}", "hard", ip, username)
    return ban_info


def check_ban(ip: str, username: str = None) -> dict | None:
    """Check if an IP or username is currently banned."""
    now = time.time()
    r = _get_redis()

    keys_to_check = [f"ban:ip:{ip}"]
    if username:
        keys_to_check.append(f"ban:user:{username}")

    for key in keys_to_check:
        try:
            if r:
                import json
                data = r.get(key)
                if data:
                    return json.loads(data)
            else:
                raise Exception("no redis")
        except Exception:
            if key in _bans:
                ban = _bans[key]
                if ban["until"] > now:
                    ban["remaining_seconds"] = int(ban["until"] - now)
                    return ban
                else:
                    del _bans[key]

    return None


def get_all_bans() -> list[dict]:
    """Return all currently active bans."""
    now = time.time()
    r = _get_redis()
    bans = []

    try:
        if r:
            import json
            for key in r.scan_iter("ban:*"):
                data = r.get(key)
                if data:
                    ban = json.loads(data)
                    ban["remaining_seconds"] = max(0, int(ban["until"] - now))
                    if ban["remaining_seconds"] > 0:
                        bans.append(ban)
            return bans
    except Exception:
        pass

    # In-memory fallback
    for key, ban in list(_bans.items()):
        if ban["until"] > now:
            ban["remaining_seconds"] = int(ban["until"] - now)
            bans.append(ban)
        else:
            del _bans[key]

    return bans


def clear_ban(ip: str = None, username: str = None):
    """Manually clear a ban."""
    r = _get_redis()
    keys = []
    if ip:
        keys.append(f"ban:ip:{ip}")
    if username:
        keys.append(f"ban:user:{username}")

    for key in keys:
        try:
            if r:
                r.delete(key)
            else:
                raise Exception("no redis")
        except Exception:
            if key in _bans:
                del _bans[key]

    logger.info(f"Ban cleared: ip={ip}, username={username}")

