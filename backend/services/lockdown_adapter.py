"""Lockdown Database Adapter — Abstract base for integrating with ANY user database.

PhishGuard's lockdown engine is database-agnostic. Implement one of these adapters
to connect to your organization's existing user management system.

Supported out of the box:
  - SQLiteAdapter (default, uses PhishGuard's built-in SQLite)
  - PostgreSQLAdapter (connect to existing PostgreSQL user tables)
  - MySQLAdapter (connect to existing MySQL/MariaDB user tables)
  - LDAPAdapter (Active Directory / OpenLDAP lockdown)
  - APIAdapter (REST API integration for SaaS platforms)

To add your own: subclass LockdownAdapter and implement the 5 methods.
"""

import os
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class LockdownAdapter(ABC):
    """Abstract base class — implement this to plug into any user database."""

    @abstractmethod
    def disable_account(self, account_id: str) -> bool:
        """Disable user login (e.g., set active=false, disable AD account)."""
        ...

    @abstractmethod
    def revoke_sessions(self, account_id: str) -> int:
        """Kill all active sessions. Returns count of revoked sessions."""
        ...

    @abstractmethod
    def freeze_credentials(self, account_id: str) -> int:
        """Freeze/revoke API keys, tokens, cards, etc. Returns count."""
        ...

    @abstractmethod
    def restore_account(self, account_id: str) -> bool:
        """Re-enable the account (manual card/token restore is separate)."""
        ...

    @abstractmethod
    def get_account_info(self, account_id: str) -> Optional[dict]:
        """Get account details for display. Return None if not found."""
        ...


# ─── Built-in SQLite Adapter (default) ────────────────────────
class SQLiteAdapter(LockdownAdapter):
    """Uses PhishGuard's built-in SQLAlchemy models."""

    def __init__(self, db_session):
        self.db = db_session

    def _get_account(self, account_id):
        from backend.models.account import Account
        return self.db.query(Account).filter(Account.id == int(account_id)).first()

    def disable_account(self, account_id: str) -> bool:
        account = self._get_account(account_id)
        if not account:
            return False
        account.is_active = False
        account.is_locked = True
        account.locked_at = datetime.utcnow()
        self.db.commit()
        return True

    def revoke_sessions(self, account_id: str) -> int:
        from backend.models.account import Session as SessionModel
        sessions = self.db.query(SessionModel).filter(
            SessionModel.account_id == int(account_id),
            SessionModel.status == "active"
        ).all()
        now = datetime.utcnow()
        for s in sessions:
            s.status = "revoked"
            s.revoked_at = now
        self.db.commit()
        return len(sessions)

    def freeze_credentials(self, account_id: str) -> int:
        from backend.models.account import Card, ApiToken
        count = 0
        now = datetime.utcnow()

        cards = self.db.query(Card).filter(
            Card.account_id == int(account_id), Card.status == "active"
        ).all()
        for c in cards:
            c.status = "frozen"
            c.frozen_at = now
            count += 1

        tokens = self.db.query(ApiToken).filter(
            ApiToken.account_id == int(account_id), ApiToken.status == "active"
        ).all()
        for t in tokens:
            t.status = "revoked"
            t.revoked_at = now
            count += 1

        self.db.commit()
        return count

    def restore_account(self, account_id: str) -> bool:
        account = self._get_account(account_id)
        if not account:
            return False
        account.is_active = True
        account.is_locked = False
        self.db.commit()
        return True

    def get_account_info(self, account_id: str) -> Optional[dict]:
        account = self._get_account(account_id)
        if not account:
            return None
        return account.to_dict(include_resources=True)


# ─── PostgreSQL Adapter ───────────────────────────────────────
class PostgreSQLAdapter(LockdownAdapter):
    """Connect to an existing PostgreSQL user/account database.

    Config via env vars:
      LOCKDOWN_PG_DSN=postgresql://user:pass@host:5432/dbname
      LOCKDOWN_PG_TABLE=users
      LOCKDOWN_PG_ID_COLUMN=id
      LOCKDOWN_PG_ACTIVE_COLUMN=is_active
      LOCKDOWN_PG_LOCKED_COLUMN=is_locked
      LOCKDOWN_PG_SESSIONS_TABLE=sessions
    """

    def __init__(self):
        self.dsn = os.getenv("LOCKDOWN_PG_DSN", "")
        self.table = os.getenv("LOCKDOWN_PG_TABLE", "users")
        self.id_col = os.getenv("LOCKDOWN_PG_ID_COLUMN", "id")
        self.active_col = os.getenv("LOCKDOWN_PG_ACTIVE_COLUMN", "is_active")
        self.locked_col = os.getenv("LOCKDOWN_PG_LOCKED_COLUMN", "is_locked")
        self.sessions_table = os.getenv("LOCKDOWN_PG_SESSIONS_TABLE", "sessions")

    def _connect(self):
        import psycopg2
        return psycopg2.connect(self.dsn)

    def disable_account(self, account_id: str) -> bool:
        try:
            conn = self._connect()
            cur = conn.cursor()
            cur.execute(
                f"UPDATE {self.table} SET {self.active_col}=FALSE, {self.locked_col}=TRUE "
                f"WHERE {self.id_col}=%s",
                (account_id,)
            )
            conn.commit()
            affected = cur.rowcount
            conn.close()
            logger.info(f"PostgreSQL: disabled account {account_id} ({affected} rows)")
            return affected > 0
        except Exception as e:
            logger.error(f"PostgreSQL lockdown failed: {e}")
            return False

    def revoke_sessions(self, account_id: str) -> int:
        try:
            conn = self._connect()
            cur = conn.cursor()
            cur.execute(
                f"UPDATE {self.sessions_table} SET status='revoked', revoked_at=NOW() "
                f"WHERE account_id=%s AND status='active'",
                (account_id,)
            )
            count = cur.rowcount
            conn.commit()
            conn.close()
            return count
        except Exception as e:
            logger.error(f"PostgreSQL session revoke failed: {e}")
            return 0

    def freeze_credentials(self, account_id: str) -> int:
        # Override with your org's token/key tables
        logger.info(f"PostgreSQL: credential freeze for {account_id} (implement per your schema)")
        return 0

    def restore_account(self, account_id: str) -> bool:
        try:
            conn = self._connect()
            cur = conn.cursor()
            cur.execute(
                f"UPDATE {self.table} SET {self.active_col}=TRUE, {self.locked_col}=FALSE "
                f"WHERE {self.id_col}=%s",
                (account_id,)
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"PostgreSQL restore failed: {e}")
            return False

    def get_account_info(self, account_id: str) -> Optional[dict]:
        try:
            conn = self._connect()
            cur = conn.cursor()
            cur.execute(f"SELECT * FROM {self.table} WHERE {self.id_col}=%s", (account_id,))
            row = cur.fetchone()
            if not row:
                return None
            cols = [desc[0] for desc in cur.description]
            conn.close()
            return dict(zip(cols, row))
        except Exception as e:
            logger.error(f"PostgreSQL get_account failed: {e}")
            return None


# ─── MySQL/MariaDB Adapter ─────────────────────────────────────
class MySQLAdapter(LockdownAdapter):
    """Connect to an existing MySQL/MariaDB user database.

    Config via env vars:
      LOCKDOWN_MYSQL_HOST, LOCKDOWN_MYSQL_PORT,
      LOCKDOWN_MYSQL_USER, LOCKDOWN_MYSQL_PASS, LOCKDOWN_MYSQL_DB
      LOCKDOWN_MYSQL_TABLE=users
    """

    def __init__(self):
        self.config = {
            "host": os.getenv("LOCKDOWN_MYSQL_HOST", "localhost"),
            "port": int(os.getenv("LOCKDOWN_MYSQL_PORT", "3306")),
            "user": os.getenv("LOCKDOWN_MYSQL_USER", "root"),
            "password": os.getenv("LOCKDOWN_MYSQL_PASS", ""),
            "database": os.getenv("LOCKDOWN_MYSQL_DB", ""),
        }
        self.table = os.getenv("LOCKDOWN_MYSQL_TABLE", "users")

    def _connect(self):
        import mysql.connector
        return mysql.connector.connect(**self.config)

    def disable_account(self, account_id: str) -> bool:
        try:
            conn = self._connect()
            cur = conn.cursor()
            cur.execute(f"UPDATE {self.table} SET is_active=0, is_locked=1 WHERE id=%s", (account_id,))
            conn.commit()
            affected = cur.rowcount
            conn.close()
            return affected > 0
        except Exception as e:
            logger.error(f"MySQL lockdown failed: {e}")
            return False

    def revoke_sessions(self, account_id: str) -> int:
        logger.info(f"MySQL: session revoke for {account_id}")
        return 0

    def freeze_credentials(self, account_id: str) -> int:
        logger.info(f"MySQL: credential freeze for {account_id}")
        return 0

    def restore_account(self, account_id: str) -> bool:
        try:
            conn = self._connect()
            cur = conn.cursor()
            cur.execute(f"UPDATE {self.table} SET is_active=1, is_locked=0 WHERE id=%s", (account_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"MySQL restore failed: {e}")
            return False

    def get_account_info(self, account_id: str) -> Optional[dict]:
        try:
            conn = self._connect()
            cur = conn.cursor(dictionary=True)
            cur.execute(f"SELECT * FROM {self.table} WHERE id=%s", (account_id,))
            row = cur.fetchone()
            conn.close()
            return row
        except Exception as e:
            logger.error(f"MySQL get_account failed: {e}")
            return None


# ─── LDAP / Active Directory Adapter ──────────────────────────
class LDAPAdapter(LockdownAdapter):
    """Lock accounts in Active Directory / OpenLDAP.

    Config via env vars:
      LOCKDOWN_LDAP_URL=ldap://dc.company.com:389
      LOCKDOWN_LDAP_BIND_DN=cn=admin,dc=company,dc=com
      LOCKDOWN_LDAP_BIND_PW=secret
      LOCKDOWN_LDAP_BASE_DN=ou=users,dc=company,dc=com
    """

    def __init__(self):
        self.url = os.getenv("LOCKDOWN_LDAP_URL", "")
        self.bind_dn = os.getenv("LOCKDOWN_LDAP_BIND_DN", "")
        self.bind_pw = os.getenv("LOCKDOWN_LDAP_BIND_PW", "")
        self.base_dn = os.getenv("LOCKDOWN_LDAP_BASE_DN", "")

    def disable_account(self, account_id: str) -> bool:
        try:
            import ldap3
            server = ldap3.Server(self.url)
            conn = ldap3.Connection(server, self.bind_dn, self.bind_pw, auto_bind=True)
            # AD: set userAccountControl to disabled (514)
            dn = f"cn={account_id},{self.base_dn}"
            conn.modify(dn, {"userAccountControl": [(ldap3.MODIFY_REPLACE, [514])]})
            logger.info(f"LDAP: disabled account {account_id}")
            conn.unbind()
            return True
        except Exception as e:
            logger.error(f"LDAP lockdown failed: {e}")
            return False

    def revoke_sessions(self, account_id: str) -> int:
        logger.info(f"LDAP: session revoke not applicable for {account_id}")
        return 0

    def freeze_credentials(self, account_id: str) -> int:
        logger.info(f"LDAP: credential freeze for {account_id} (reset password via AD)")
        return 0

    def restore_account(self, account_id: str) -> bool:
        try:
            import ldap3
            server = ldap3.Server(self.url)
            conn = ldap3.Connection(server, self.bind_dn, self.bind_pw, auto_bind=True)
            dn = f"cn={account_id},{self.base_dn}"
            conn.modify(dn, {"userAccountControl": [(ldap3.MODIFY_REPLACE, [512])]})
            conn.unbind()
            return True
        except Exception as e:
            logger.error(f"LDAP restore failed: {e}")
            return False

    def get_account_info(self, account_id: str) -> Optional[dict]:
        try:
            import ldap3
            server = ldap3.Server(self.url)
            conn = ldap3.Connection(server, self.bind_dn, self.bind_pw, auto_bind=True)
            conn.search(self.base_dn, f"(cn={account_id})", attributes=["*"])
            if conn.entries:
                return dict(conn.entries[0].entry_attributes_as_dict)
            conn.unbind()
            return None
        except Exception as e:
            logger.error(f"LDAP query failed: {e}")
            return None


# ─── REST API Adapter ──────────────────────────────────────────
class APIAdapter(LockdownAdapter):
    """Integrate with any SaaS user management API (Okta, Auth0, custom).

    Config via env vars:
      LOCKDOWN_API_BASE_URL=https://api.yourservice.com
      LOCKDOWN_API_TOKEN=Bearer xxx
      LOCKDOWN_API_DISABLE_ENDPOINT=/users/{id}/disable   (POST)
      LOCKDOWN_API_RESTORE_ENDPOINT=/users/{id}/enable     (POST)
    """

    def __init__(self):
        self.base_url = os.getenv("LOCKDOWN_API_BASE_URL", "").rstrip("/")
        self.token = os.getenv("LOCKDOWN_API_TOKEN", "")
        self.disable_ep = os.getenv("LOCKDOWN_API_DISABLE_ENDPOINT", "/users/{id}/disable")
        self.restore_ep = os.getenv("LOCKDOWN_API_RESTORE_ENDPOINT", "/users/{id}/enable")

    def _request(self, method: str, endpoint: str, account_id: str) -> bool:
        import urllib.request
        url = self.base_url + endpoint.replace("{id}", account_id)
        req = urllib.request.Request(url, method=method, data=b"")
        req.add_header("Authorization", self.token)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status < 400
        except Exception as e:
            logger.error(f"API adapter error: {e}")
            return False

    def disable_account(self, account_id: str) -> bool:
        return self._request("POST", self.disable_ep, account_id)

    def revoke_sessions(self, account_id: str) -> int:
        ep = os.getenv("LOCKDOWN_API_REVOKE_SESSIONS_ENDPOINT", "")
        if ep:
            self._request("POST", ep, account_id)
        return 0

    def freeze_credentials(self, account_id: str) -> int:
        return 0

    def restore_account(self, account_id: str) -> bool:
        return self._request("POST", self.restore_ep, account_id)

    def get_account_info(self, account_id: str) -> Optional[dict]:
        import urllib.request, json
        url = self.base_url + f"/users/{account_id}"
        req = urllib.request.Request(url)
        req.add_header("Authorization", self.token)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except Exception:
            return None


# ─── MongoDB Adapter ──────────────────────────────────────────
class MongoDBAdapter(LockdownAdapter):
    """Connect to an existing MongoDB user collection."""
    def __init__(self):
        self.uri = os.getenv("LOCKDOWN_MONGO_URI", "mongodb://localhost:27017/")
        self.db_name = os.getenv("LOCKDOWN_MONGO_DB", "")
        self.collection_name = os.getenv("LOCKDOWN_MONGO_COLLECTION", "users")
        self.id_field = os.getenv("LOCKDOWN_MONGO_ID_FIELD", "_id")

    def _get_collection(self):
        import pymongo
        client = pymongo.MongoClient(self.uri)
        return client[self.db_name][self.collection_name]

    def disable_account(self, account_id: str) -> bool:
        try:
            from bson.objectid import ObjectId
            coll = self._get_collection()
            query_id = ObjectId(account_id) if self.id_field == "_id" and len(account_id) == 24 else account_id
            res = coll.update_one({self.id_field: query_id}, {"$set": {"is_active": False, "is_locked": True}})
            return res.modified_count > 0
        except Exception as e:
            logger.error(f"MongoDB lockdown failed: {e}")
            return False

    def revoke_sessions(self, account_id: str) -> int:
        return 0

    def freeze_credentials(self, account_id: str) -> int:
        return 0

    def restore_account(self, account_id: str) -> bool:
        try:
            from bson.objectid import ObjectId
            coll = self._get_collection()
            query_id = ObjectId(account_id) if self.id_field == "_id" and len(account_id) == 24 else account_id
            res = coll.update_one({self.id_field: query_id}, {"$set": {"is_active": True, "is_locked": False}})
            return res.modified_count > 0
        except Exception as e:
            logger.error(f"MongoDB restore failed: {e}")
            return False

    def get_account_info(self, account_id: str) -> Optional[dict]:
        try:
            from bson.objectid import ObjectId
            coll = self._get_collection()
            query_id = ObjectId(account_id) if self.id_field == "_id" and len(account_id) == 24 else account_id
            doc = coll.find_one({self.id_field: query_id})
            if doc:
                doc['_id'] = str(doc['_id'])
            return doc
        except Exception as e:
            logger.error(f"MongoDB get_account failed: {e}")
            return None


# ─── Redis Adapter ────────────────────────────────────────────
class RedisAdapter(LockdownAdapter):
    """Integrate with systems where active user state is stored in Redis."""
    def __init__(self):
        self.url = os.getenv("LOCKDOWN_REDIS_URL", "redis://localhost:6379/1")
        self.user_prefix = os.getenv("LOCKDOWN_REDIS_USER_PREFIX", "user:")
        self.session_prefix = os.getenv("LOCKDOWN_REDIS_SESSION_PREFIX", "session:")

    def _get_client(self):
        import redis
        return redis.from_url(self.url, decode_responses=True)

    def disable_account(self, account_id: str) -> bool:
        try:
            r = self._get_client()
            key = f"{self.user_prefix}{account_id}"
            r.hset(key, "is_active", "0")
            r.hset(key, "is_locked", "1")
            return True
        except Exception as e:
            logger.error(f"Redis lockdown failed: {e}")
            return False

    def revoke_sessions(self, account_id: str) -> int:
        try:
            r = self._get_client()
            keys = r.keys(f"{self.session_prefix}{account_id}:*")
            if keys:
                r.delete(*keys)
            return len(keys)
        except Exception as e:
            logger.error(f"Redis session revoke failed: {e}")
            return 0

    def freeze_credentials(self, account_id: str) -> int:
        return 0

    def restore_account(self, account_id: str) -> bool:
        try:
            r = self._get_client()
            r.hset(f"{self.user_prefix}{account_id}", mapping={"is_active": "1", "is_locked": "0"})
            return True
        except Exception as e:
            logger.error(f"Redis restore failed: {e}")
            return False

    def get_account_info(self, account_id: str) -> Optional[dict]:
        try:
            r = self._get_client()
            info = r.hgetall(f"{self.user_prefix}{account_id}")
            return info if info else None
        except Exception as e:
            logger.error(f"Redis get_account failed: {e}")
            return None


# ─── Factory ─────────────────────────────────────────────────
ADAPTER_MAP = {
    "sqlite": "SQLiteAdapter",
    "postgresql": "PostgreSQLAdapter",
    "mysql": "MySQLAdapter",
    "ldap": "LDAPAdapter",
    "api": "APIAdapter",
    "mongodb": "MongoDBAdapter",
    "redis": "RedisAdapter",
}


def get_adapter(db_session=None) -> LockdownAdapter:
    """Get the configured lockdown adapter based on LOCKDOWN_BACKEND env var.

    LOCKDOWN_BACKEND=sqlite (default) | postgresql | mysql | ldap | api | mongodb | redis
    """
    backend = os.getenv("LOCKDOWN_BACKEND", "sqlite").lower()

    if backend == "sqlite":
        if db_session is None:
            from backend.database import SessionLocal
            db_session = SessionLocal()
        return SQLiteAdapter(db_session)
    elif backend == "postgresql":
        return PostgreSQLAdapter()
    elif backend == "mysql":
        return MySQLAdapter()
    elif backend == "ldap":
        return LDAPAdapter()
    elif backend == "api":
        return APIAdapter()
    elif backend == "mongodb":
        return MongoDBAdapter()
    elif backend == "redis":
        return RedisAdapter()
    else:
        logger.warning(f"Unknown lockdown backend '{backend}', falling back to SQLite")
        if db_session is None:
            from backend.database import SessionLocal
            db_session = SessionLocal()
        return SQLiteAdapter(db_session)
