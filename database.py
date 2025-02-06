# database.py
import sqlite3
from sqlite3 import Error

class Database:
    def __init__(self, db_file='expenses.db'):
        self.db_file = db_file
        self.conn = self.create_connection()
        self.create_tables()
    
    def create_connection(self):
        conn = None
        try:
            # Cho phép dùng connection trên nhiều thread (dùng cho Job Queue)
            conn = sqlite3.connect(self.db_file, check_same_thread=False)
        except Error as e:
            print(e)
        return conn
    
    def create_tables(self):
        try:
            cursor = self.conn.cursor()
            # Bảng lưu giao dịch chi tiêu
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    category TEXT,
                    currency TEXT DEFAULT 'VND'
                )
            ''')
            # Bảng lưu thông tin người dùng (cho việc nhắc nhở, v.v.)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    chat_id TEXT NOT NULL
                )
            ''')
            # Bảng lưu thông tin cá nhân, bao gồm cả mục tiêu sử dụng
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS profiles (
                    user_id TEXT PRIMARY KEY,
                    name TEXT,
                    income REAL,
                    budget REAL,
                    savings_goal REAL,
                    spending_targets TEXT
                )
            ''')
            self.conn.commit()
        except Error as e:
            print(e)
    
    def add_user(self, user_id, chat_id):
        try:
            cursor = self.conn.cursor()
            cursor.execute("INSERT OR IGNORE INTO users (user_id, chat_id) VALUES (?, ?)", (user_id, chat_id))
            self.conn.commit()
        except Error as e:
            print(e)
    
    def add_expense(self, user_id, date, amount, category, currency="VND"):
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO expenses (user_id, date, amount, category, currency)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, date, amount, category, currency))
            self.conn.commit()
        except Error as e:
            print(e)
    
    def get_expenses_by_date(self, user_id, date):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM expenses WHERE user_id = ? AND date = ?
        ''', (user_id, date))
        return cursor.fetchall()
    
    def get_expenses_by_period(self, user_id, start_date, end_date):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM expenses WHERE user_id = ? AND date BETWEEN ? AND ?
        ''', (user_id, start_date, end_date))
        return cursor.fetchall()
    
    def get_total_expense_by_date(self, user_id, date):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT SUM(amount) FROM expenses WHERE user_id = ? AND date = ?
        ''', (user_id, date))
        result = cursor.fetchone()[0]
        return result if result else 0.0
    
    def get_all_users(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM users')
        return cursor.fetchall()
    
    def add_profile(self, user_id, name, income, budget, savings_goal, spending_targets):
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO profiles (user_id, name, income, budget, savings_goal, spending_targets)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, name, income, budget, savings_goal, spending_targets))
            self.conn.commit()
        except Error as e:
            print(e)
    
    def get_profile(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT name, income, budget, savings_goal, spending_targets FROM profiles WHERE user_id = ?
        ''', (user_id,))
        return cursor.fetchone()
