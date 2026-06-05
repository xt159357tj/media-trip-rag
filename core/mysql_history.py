import json
import pymysql
import uuid
import hashlib
from datetime import datetime
from core.logger import get_logger

logger = get_logger(__name__)

# ----------------- 统一数据库配置 -----------------
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "159357",
    "db": "chat_history_db",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor
}


def get_db_conn():
    return pymysql.connect(**DB_CONFIG)


# ----------------- 用户信息与鉴权管理 -----------------
class UserManager:
    @staticmethod
    def init_users_table():
        create_table_sql = """
                           CREATE TABLE IF NOT EXISTS users \
                           ( \
                               uid        VARCHAR(50) PRIMARY KEY COMMENT '用户唯一ID', \
                               uname      VARCHAR(50) UNIQUE NOT NULL COMMENT '用户名', \
                               password   VARCHAR(100)       NOT NULL COMMENT '加密密码', \
                               created_at DATETIME DEFAULT CURRENT_TIMESTAMP \
                           ) ENGINE = InnoDB \
                             DEFAULT CHARSET = utf8mb4; \
                           """
        try:
            conn = get_db_conn()
            with conn.cursor() as cursor:
                cursor.execute(create_table_sql)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"初始化用户表失败: {e}")

    @staticmethod
    def hash_password(password: str) -> str:
        """密码哈希处理"""
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    @staticmethod
    def register(uname: str, password: str):
        """处理用户注册逻辑"""
        conn = get_db_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT uid FROM users WHERE uname = %s", (uname,))
                if cursor.fetchone():
                    return False, "用户名已存在"

                uid = uuid.uuid4().hex
                hashed_pw = UserManager.hash_password(password)
                cursor.execute(
                    "INSERT INTO users (uid, uname, password) VALUES (%s, %s, %s)",
                    (uid, uname, hashed_pw)
                )
            conn.commit()
            return True, uid
        except Exception as e:
            return False, str(e)
        finally:
            conn.close()

    @staticmethod
    def login(uname: str, password: str):
        """处理用户登录逻辑"""
        conn = get_db_conn()
        try:
            with conn.cursor() as cursor:
                hashed_pw = UserManager.hash_password(password)
                cursor.execute(
                    "SELECT uid FROM users WHERE uname = %s AND password = %s",
                    (uname, hashed_pw)
                )
                user = cursor.fetchone()
                if not user:
                    return False, "用户名或密码错误"
            return True, user["uid"]
        except Exception as e:
            return False, str(e)
        finally:
            conn.close()


# ----------------- 聊天历史管理 -----------------
class UserMySQLHistoryManager:
    def __init__(self, uid: str, host=DB_CONFIG["host"], user=DB_CONFIG["user"], password=DB_CONFIG["password"],
                 db=DB_CONFIG["db"]):
        self.db_config = {
            "host": host,
            "user": user,
            "password": password,
            "db": db,
            "charset": "utf8mb4",
            "cursorclass": pymysql.cursors.DictCursor
        }
        self.table_name = f"{uid}_chat_history"
        self._init_table()

    def _get_conn(self):
        return pymysql.connect(**self.db_config)

    def _init_table(self):
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            session_id VARCHAR(100) PRIMARY KEY COMMENT '会话ID',
            history_data JSON COMMENT '历史记录内容',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_updated_at (updated_at DESC)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        try:
            conn = self._get_conn()
            with conn.cursor() as cursor:
                cursor.execute(create_table_sql)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"初始化用户历史记录表失败: {e}")

    def load(self, session_id):
        if not session_id or session_id.strip() == "":
            return []
        sql = f"SELECT history_data FROM {self.table_name} WHERE session_id = %s"
        try:
            conn = self._get_conn()
            with conn.cursor() as cursor:
                cursor.execute(sql, (session_id,))
                result = cursor.fetchone()
            conn.close()
            if result and result["history_data"]:
                data = result["history_data"]
                return json.loads(data) if isinstance(data, str) else data
            return []
        except Exception as e:
            logger.error(f"读取历史记录失败: {e}")
            return []

    def save(self, session_id, qa:list[dict]):
        if not session_id:
            session_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        history = self.load(session_id)
        history.extend(qa)
        history_json = json.dumps(history, ensure_ascii=False)


        sql = f"""
        INSERT INTO {self.table_name} (session_id, history_data)
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE history_data = VALUES(history_data)
        """
        try:
            conn = self._get_conn()
            with conn.cursor() as cursor:
                cursor.execute(sql, (session_id, history_json))
            conn.commit()
            conn.close()
            return session_id
        except Exception as e:
            logger.error(f"保存历史记录失败: {e}")
            return session_id

    def get_all_sessions(self):
        """获取该用户的所有会话ID列表"""
        sql = f"SELECT session_id FROM {self.table_name} ORDER BY updated_at DESC"
        try:
            conn = self._get_conn()
            with conn.cursor() as cursor:
                cursor.execute(sql)
                results = cursor.fetchall()
            conn.close()
            return [row["session_id"] for row in results]
        except Exception as e:
            logger.error(f"获取历史列表失败: {e}")
            return []

    def delete_session(self, session_id):
        """删除指定的会话"""
        sql = f"DELETE FROM {self.table_name} WHERE session_id = %s"
        try:
            conn = self._get_conn()
            with conn.cursor() as cursor:
                cursor.execute(sql, (session_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"删除历史记录失败: {e}")
            return False